"""WebSocket routes."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from typing import Dict, Any, Set
from loguru import logger

from horbot.web.security import authorize_websocket

router = APIRouter()

websocket_connections: Dict[str, WebSocket] = {}
session_subscriptions: Dict[str, Set[str]] = {}
connection_subscriptions: Dict[str, Set[str]] = {}


async def broadcast_to_session(session_key: str, message: dict[str, Any]) -> None:
    """Broadcast a message to all connections subscribed to the exact session."""
    conn_ids = list(session_subscriptions.get(session_key, set()))
    for conn_id in conn_ids:
        if conn_id not in websocket_connections:
            continue
        try:
            await websocket_connections[conn_id].send_json({
                **message,
                "session_key": session_key,
            })
        except Exception as e:
            logger.warning("Failed to send WebSocket message: {}", e)
            websocket_connections.pop(conn_id, None)
            if conn_id in session_subscriptions.get(session_key, set()):
                session_subscriptions[session_key].discard(conn_id)
            if conn_id in connection_subscriptions:
                connection_subscriptions[conn_id].discard(session_key)


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for chat with session subscription."""
    await authorize_websocket(websocket)
    if websocket.client_state.name != "CONNECTED":
        return
    connection_id = f"chat_{id(websocket)}"
    websocket_connections[connection_id] = websocket
    connection_subscriptions[connection_id] = set()
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "subscribe":
                requested_session = data.get("session_key")
                if requested_session:
                    if requested_session.endswith(":*"):
                        await websocket.send_json({"type": "error", "message": "Wildcard session subscriptions are not allowed"})
                        continue
                    if requested_session not in session_subscriptions:
                        session_subscriptions[requested_session] = set()
                    session_subscriptions[requested_session].add(connection_id)
                    connection_subscriptions.setdefault(connection_id, set()).add(requested_session)
                    logger.info("WebSocket subscribed to session: {}", requested_session)
                    await websocket.send_json({"type": "subscribed", "session_key": requested_session})
            elif data.get("type") == "unsubscribe":
                requested_session = data.get("session_key")
                target_sessions = (
                    [requested_session]
                    if requested_session
                    else list(connection_subscriptions.get(connection_id, set()))
                )
                for session_key in target_sessions:
                    if session_key in session_subscriptions:
                        session_subscriptions[session_key].discard(connection_id)
                    connection_subscriptions.get(connection_id, set()).discard(session_key)
                await websocket.send_json({"type": "unsubscribed", **({"session_key": requested_session} if requested_session else {})})
            elif data.get("content"):
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error: {}", e)
    finally:
        if connection_id in websocket_connections:
            del websocket_connections[connection_id]
        for session_key in list(connection_subscriptions.get(connection_id, set())):
            if session_key in session_subscriptions:
                session_subscriptions[session_key].discard(connection_id)
        connection_subscriptions.pop(connection_id, None)


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
