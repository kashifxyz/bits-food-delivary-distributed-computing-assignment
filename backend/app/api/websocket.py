import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.app.models.event import Event
from backend.app.distributed.event_manager import event_manager

logger = logging.getLogger("WebSocket")
router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining clients: {len(self.active_connections)}")

    async def broadcast_event(self, event: Event):
        if not self.active_connections:
            return
            
        payload = json.dumps({
            "type": "EVENT_CREATED",
            "data": event.model_dump()
        })
        
        dead_sockets = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_sockets.add(connection)
                
        for dead in dead_sockets:
            self.active_connections.discard(dead)

ws_manager = ConnectionManager()

# Hook event_manager subscriber to websocket broadcaster
def websocket_event_subscriber(event: Event):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(ws_manager.broadcast_event(event))
    except Exception as e:
        pass

event_manager.subscribe(websocket_event_subscriber)

@router.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming ping / messages if needed
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
