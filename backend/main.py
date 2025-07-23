# backend/main.py
import asyncio
import logging
from datetime import datetime
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from typing import List
from prometheus_fastapi_instrumentator import Instrumentator

from .connection_manager import ConnectionManager, manager
from .local_client import LocalSpeechProcessor
from .config import settings
from .logging_config import setup_logging

# --- Pre-startup Configuration ---
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Live Interpreter Backend")

# --- Global State ---
agent_manager = ConnectionManager()
processor: LocalSpeechProcessor = None

@app.on_event("startup")
async def startup_event():
    """On startup, initialize the speech processor, instrumentator, and background tasks."""
    global processor
    
    # Expose default metrics
    Instrumentator().instrument(app).expose(app)

    def result_callback(event_type: str, text: str, translations: dict, lang: str):
        """A thread-safe callback to broadcast results to clients."""
        asyncio.run_coroutine_threadsafe(
            broadcast_result(event_type, text, translations, lang),
            loop
        )

    loop = asyncio.get_running_loop()
    logger.info("Initializing LocalSpeechProcessor...")
    processor = LocalSpeechProcessor(result_callback=result_callback)
    
    logger.info("Starting background tasks...")
    asyncio.create_task(broadcast_data_periodically())

async def broadcast_result(event_type: str, text: str, translations: dict, lang: str):
    """Formats the result and broadcasts it to all connected data clients."""
    message_type = ""
    if event_type == 'final':
        message_type = "transcript_translation"
    elif event_type == 'interim':
        message_type = "interim_transcript"

    if message_type and text:
        message = {
            "type": message_type,
            "text": text,
            "translations": translations,
            "lang": lang,
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast(message)

async def broadcast_data_periodically():
    """Broadcasts a ping message to all clients every 2 seconds."""
    while True:
        await asyncio.sleep(2)
        now = datetime.now()
        message = {"type": "ping", "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")}
        await manager.broadcast(message)

@app.get("/health")
async def health_check():
    """Health check endpoint to verify model loading."""
    if processor and processor.is_ready:
        return {"status": "ok", "message": "Services are ready."}
    else:
        logger.warning("Health check failed: processor not ready.")
        raise HTTPException(status_code=503, detail="Services are not ready. Models may be loading or have failed.")

@app.websocket("/ws/data")
async def websocket_data_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info("Client connected to /ws/data", extra={"client": websocket.client})
    try:
        is_agent_connected = len(agent_manager.active_connections) > 0
        await websocket.send_json({"type": "status", "agent_connected": is_agent_connected})
        while True:
            data = await websocket.receive_json()
            logger.debug("Received message from client", extra={"client": websocket.client, "data_type": data.get("type")})
            # Handle incoming messages (config updates, etc.)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from /ws/data", extra={"client": websocket.client})
    except Exception as e:
        logger.error("Error in data endpoint", exc_info=True, extra={"client": websocket.client})
        manager.disconnect(websocket)

@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    global processor
    if not processor or not processor.is_ready:
        logger.warning("Attempted to connect to /ws/audio, but processor is not ready.", extra={"client": websocket.client})
        await websocket.close(code=1011, reason="Backend processor not ready")
        return

    await agent_manager.connect(websocket)
    await manager.broadcast({"type": "status", "agent_connected": True})
    logger.info("Agent connected to /ws/audio", extra={"client": websocket.client})
    
    processor.start()
    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            processor.push_audio_chunk(audio_chunk)
    except WebSocketDisconnect:
        logger.info("Audio agent disconnected", extra={"client": websocket.client})
    except Exception as e:
        logger.error("Error in audio endpoint", exc_info=True, extra={"client": websocket.client})
    finally:
        agent_manager.disconnect(websocket)
        await manager.broadcast({"type": "status", "agent_connected": False})
        processor.stop()