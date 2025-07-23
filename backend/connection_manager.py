# backend/connection_manager.py
import logging
import asyncio
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[ConnectionManager] New connection: {websocket.client}. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"[ConnectionManager] Client disconnected: {websocket.client}. Total clients: {len(self.active_connections)}")
        else:
            logger.info(f"[ConnectionManager] Attempted to disconnect unknown client: {websocket.client}")

    async def broadcast(self, message: dict):
        # We create a list of tasks to send messages concurrently
        tasks = [
            connection.send_json(message)
            for connection in self.active_connections
        ]
        # We gather the results, which also handles exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        connections_to_remove = []
        for result, connection in zip(results, self.active_connections):
            if isinstance(result, Exception):
                logger.error(f"Failed to send message to {connection.client}: {result}")
                connections_to_remove.append(connection)
        for connection in connections_to_remove:
            self.active_connections.remove(connection)

# Create a single instance of the manager to be used by the app
manager = ConnectionManager()
