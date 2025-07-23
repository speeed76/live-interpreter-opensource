# backend/main.py
import asyncio
import logging
from datetime import datetime
import uuid # Import uuid module
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from .connection_manager import ConnectionManager, manager
from .local_client import LocalSpeechProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# --- Global Configuration ---
TARGET_LANGUAGES: List[str] = ["en", "pl"]

agent_manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    """On startup, create a background task to broadcast data."""
    asyncio.create_task(broadcast_data_periodically())

async def broadcast_data_periodically():
    """Broadcasts a ping message to all clients every 2 seconds."""
    while True:
        await asyncio.sleep(2)
        now = datetime.now()
        message = {
            "type": "ping",
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
        }
        # logger.info(f"Broadcasting message to {len(manager.active_connections)} clients.")
        await manager.broadcast(message)

@app.websocket("/ws/data")
async def websocket_data_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info(f"[ws/data] Client {websocket.client} connected.")
    try:
        # Immediately inform the new client about the current agent status.
        is_agent_connected = len(agent_manager.active_connections) > 0
        logger.info(f"[ws/data] Sending initial status to {websocket.client}: agent_connected={is_agent_connected}")
        await websocket.send_json({"type": "status", "agent_connected": is_agent_connected})
        while True:
            data = await websocket.receive_json()
            logger.info(f"[ws/data] Received message from {websocket.client}: {data.get("type")}")
            if data.get("type") == "config_update":
                global TARGET_LANGUAGES
                new_languages = data.get("languages", [])
                if isinstance(new_languages, list):
                    TARGET_LANGUAGES = new_languages
                    logger.info(f"Updated target languages to: {TARGET_LANGUAGES}")
                    await manager.broadcast({
                        "type": "config_updated",
                        "languages": TARGET_LANGUAGES
                    })
            elif data.get("type") == "mute_toggle":
                command = data.get("command")
                if command in ["mute", "unmute"]:
                    logger.info(f"Relaying command to agents: {command}")
                    await agent_manager.broadcast({"command": command})
            elif data.get("type") == "pause_toggle": # New: Handle pause/resume
                command = data.get("command")
                if command in ["pause", "resume"]:
                    logger.info(f"Relaying pause/resume command to agents: {command}")
                    await agent_manager.broadcast({"type": "pause_toggle", "command": command})
            elif data.get("type") == "mute_status":
                is_muted = data.get("is_muted")
                logger.info(f"Agent mute status received: {is_muted}")
                await manager.broadcast({"type": "mute_status", "is_muted": is_muted})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Error in data endpoint: {e}")
        manager.disconnect(websocket)

@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    await agent_manager.connect(websocket)
    await manager.broadcast({"type": "status", "agent_connected": True})
    try:
        async def broadcast_result_callback(event_type: str, text: str, translations: dict, lang: str):
            """Formats the result and broadcasts it."""
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
                    "id": str(uuid.uuid4()), # Add unique ID
                    "timestamp": datetime.now().isoformat() # Add timestamp
                }
                await manager.broadcast(message)

        loop = asyncio.get_running_loop()
        def thread_safe_callback(event_type: str, text: str, translations: dict, lang: str):
            asyncio.run_coroutine_threadsafe(
                broadcast_result_callback(event_type, text, translations, lang), loop
            )

        processor = LocalSpeechProcessor(
            result_callback=thread_safe_callback,
            target_languages=TARGET_LANGUAGES
        )
        processor.start()

        while True:
            audio_chunk = await websocket.receive_bytes()
            processor.push_audio_chunk(audio_chunk)

    except WebSocketDisconnect:
        logger.info(f"Audio agent disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"Error in audio endpoint: {e}")
    finally:
        agent_manager.disconnect(websocket)
        await manager.broadcast({"type": "status", "agent_connected": False})
        if 'processor' in locals() and processor:
            processor.stop()
