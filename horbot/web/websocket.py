"""WebSocket routes."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from typing import Dict, Any
from loguru import logger

from horbot.web.security import authorize_websocket

router = APIRouter()

websocket_connections: Dict[str, WebSocket] = {}
session_subscriptions: Dict[str, list[str]] = {}


async def broadcast_to_session(session_key: str, message: dict[str, Any]) -> None:
    """Broadcast a message to all connections subscribed to the exact session."""
    conn_ids = list(session_subscriptions.get(session_key, []))
    for conn_id in conn_ids:
        if conn_id not in websocket_connections:
            continue
        try:
            await websocket_connections[conn_id].send_json(message)
        except Exception as e:
            logger.warning("Failed to send WebSocket message: {}", e)
            websocket_connections.pop(conn_id, None)
            if conn_id in session_subscriptions.get(session_key, []):
                session_subscriptions[session_key].remove(conn_id)


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for chat with session subscription."""
    await authorize_websocket(websocket)
    if websocket.client_state.name != "CONNECTED":
        return
    connection_id = f"chat_{id(websocket)}"
    websocket_connections[connection_id] = websocket
    current_session: str | None = None
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "subscribe":
                current_session = data.get("session_key")
                if current_session:
                    if current_session.endswith(":*"):
                        await websocket.send_json({"type": "error", "message": "Wildcard session subscriptions are not allowed"})
                        continue
                    if current_session not in session_subscriptions:
                        session_subscriptions[current_session] = []
                    session_subscriptions[current_session].append(connection_id)
                    logger.info("WebSocket subscribed to session: {}", current_session)
                    await websocket.send_json({"type": "subscribed", "session_key": current_session})
            elif data.get("type") == "unsubscribe":
                if current_session and current_session in session_subscriptions:
                    if connection_id in session_subscriptions[current_session]:
                        session_subscriptions[current_session].remove(connection_id)
                    await websocket.send_json({"type": "unsubscribed"})
            elif data.get("content"):
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error: {}", e)
    finally:
        if connection_id in websocket_connections:
            del websocket_connections[connection_id]
        if current_session and current_session in session_subscriptions:
            if connection_id in session_subscriptions[current_session]:
                session_subscriptions[current_session].remove(connection_id)


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for logs."""
    await authorize_websocket(websocket)
    if websocket.client_state.name != "CONNECTED":
        return
    connection_id = f"logs_{id(websocket)}"
    websocket_connections[connection_id] = websocket
    
    try:
        while True:
            await asyncio.sleep(5)
            await websocket.send_json({"log": "Test log message"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error: {}", e)
    finally:
        if connection_id in websocket_connections:
            del websocket_connections[connection_id]
