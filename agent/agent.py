# agent/agent.py
import asyncio
import logging
import sounddevice as sd
import websockets
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
SAMPLE_RATE = 16000
BLOCK_SIZE = 1024
CHANNELS = 1
DTYPE = 'int16'
SERVER_URI = "ws://127.0.0.1:8000/ws/audio"
CONTROL_SERVER_URI = "ws://127.0.0.1:8000/ws/data"
# DEVICE_ID = 12 # Index for 'ChromeAudioRecorder' - no longer hardcoded
AUDIO_DEVICE_NAME = "ChromeAudioRecorder"

# An asyncio queue to bridge the synchronous audio callback and the async WebSocket sender
audio_queue = asyncio.Queue()

# --- Global State ---
# Use a simple boolean for mute state, as it will be controlled by a separate thread
is_muted = False
is_paused = False # New global state for pause/resume

def find_audio_device_by_name(name: str):
    """
    Finds an audio device by its name and returns its index.
    """
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if name in device['name'] and device['max_input_channels'] > 0:
            logger.info(f"Found audio device '{name}' at index {i}")
            return i
    logger.error(f"Audio device '{name}' not found. Please ensure it is connected and recognized by your system.")
    return None

def audio_callback(indata, frames, time, status):
    """
    This is called by a separate thread for each audio block.
    """
    global is_muted, is_paused # Access global variables
    if is_muted or is_paused: # Check both mute and pause states
        return
    if status:
        logger.warning(f"Audio callback status: {status}")
    audio_queue.put_nowait(indata.tobytes())

async def control_listener():
    """
    Connects to the control server and listens for commands.
    """
    global is_muted, is_paused # Access global variables
    while True:
        try:
            logger.info(f"Attempting to connect to control server at {CONTROL_SERVER_URI}")
            async with websockets.connect(CONTROL_SERVER_URI) as websocket:
                logger.info("Successfully connected to control server.")
                # Send initial mute status
                await websocket.send(json.dumps({"type": "mute_status", "is_muted": is_muted}))
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    if data.get("type") == "mute_toggle":
                        command = data.get("command")
                        if command == "mute":
                            is_muted = True
                            logger.info("Mute command received from control server.")
                        elif command == "unmute":
                            is_muted = False
                            logger.info("Unmute command received from control server.")
                        # Send updated mute status back to the backend
                        await websocket.send(json.dumps({"type": "mute_status", "is_muted": is_muted}))
                    elif data.get("type") == "pause_toggle": # New: Handle pause/resume
                        command = data.get("command")
                        if command == "pause":
                            is_paused = True
                            logger.info("Pause command received from control server.")
                        elif command == "resume":
                            is_paused = False
                            logger.info("Resume command received from control server.")
                        # No need to send status back for pause/resume, frontend manages its own state
                        # based on the button click and F8 shortcut.
                        # If backend needs to know agent's pause state, we'd add a message here.

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Control connection to server closed: {e}. Retrying in 5 seconds...")
        except Exception as e:
            logger.error(f"An error occurred in the control listener: {e}. Retrying in 5 seconds...")
        await asyncio.sleep(5)

async def audio_sender():
    """
    Connects to the server and sends audio from the queue.
    """
    global is_paused # Access global variable
    while True: # Outer loop for reconnection
        try:
            logger.info(f"Attempting to connect to server at {SERVER_URI}")
            async with websockets.connect(SERVER_URI) as websocket:
                logger.info("Successfully connected to server.")
                while True:
                    audio_chunk = await audio_queue.get()
                    if not is_muted and not is_paused: # Check both mute and pause states
                        await websocket.send(audio_chunk)

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection to server closed: {e}. Retrying in 5 seconds...")
        except Exception as e:
            logger.error(f"An error occurred in the sender: {e}. Retrying in 5 seconds...")

        await asyncio.sleep(5)

async def main():
    """
    Sets up the audio stream and the WebSocket sender task.
    """
    logger.info("Starting audio agent...")

    device_id = find_audio_device_by_name(AUDIO_DEVICE_NAME)
    if device_id is None:
        logger.error("Could not start audio stream: Specified audio device not found.")
        return # Exit if device not found

    sender_task = asyncio.create_task(audio_sender())
    control_task = asyncio.create_task(control_listener())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=audio_callback,
        device=device_id
    )
    with stream:
        await asyncio.gather(sender_task, control_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user.")
    except Exception as e:
        logger.error(f"Unhandled error in main: {e}")