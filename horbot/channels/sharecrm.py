"""ShareCRM (纷享销客) channel implementation using SSE + REST."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx
from loguru import logger

from horbot.bus.events import OutboundMessage
from horbot.bus.queue import MessageBus
from horbot.channels.base import BaseChannel
from horbot.config.schema import ShareCrmConfig

# Constants
RECONNECT_DELAY_MS = 3000
TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000  # 5 minutes buffer before token expires
DEFAULT_GATEWAY_BASE_URL = "https://open.fxiaoke.com"


@dataclass
class ShareCrmMessage:
    """ShareCRM message data."""

    chat_id: str
    chat_type: str  # "direct" or "group"
    sender_id: str
    sender_name: str
    message_id: str
    text: str
    timestamp: int


@dataclass
class ShareCrmAccount:
    """Resolved ShareCRM account configuration."""

    account_id: str
    enabled: bool
    configured: bool
    name: Optional[str]
    gateway_base_url: str
    app_id: str
    app_secret: str
    config: ShareCrmConfig


class ShareCrmClient:
    """ShareCRM IM Gateway client with SSE connection and REST messaging."""

    def __init__(
        self,
        account: ShareCrmAccount,
        on_connected: Callable,
        on_message: Callable,
        on_disconnected: Callable,
        on_error: Optional[Callable] = None,
        log: Optional[Callable] = None,
    ):
        self.account = account
        self.on_connected = on_connected
        self.on_message = on_message
        self.on_disconnected = on_disconnected
        self.on_error = on_error
        self.log = log or logger.info

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._should_reconnect: bool = True
        self._reconnect_timer: Optional[asyncio.Task] = None
        self._connected: bool = False
        self._connecting: bool = False
        self._sse_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def connected(self) -> bool:
        return self._connected

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=60.0)
        return self._http_client

    async def fetch_access_token(self) -> str:
        """Fetch access token from ShareCRM IM Gateway."""
        client = await self._get_http_client()
        url = f"{self.account.gateway_base_url}/im-gateway/auth/token"
        
        response = await client.post(
            url,
            json={"appId": self.account.app_id, "appSecret": self.account.app_secret},
            headers={"Content-Type": "application/json"},
        )
        
        data = response.json()
        if data.get("code") != 0 or not data.get("data"):
            raise Exception(data.get("msg", "Failed to get access token"))
        
        self._access_token = data["data"]["accessToken"]
        self._token_expires_at = time.time() + data["data"]["expiresIn"] - TOKEN_REFRESH_BUFFER_MS / 1000
        self.log(f"sharecrm[{self.account.account_id}]: Access token obtained, expires in {data['data']['expiresIn']}s")
        return self._access_token

    async def ensure_token(self) -> str:
        """Ensure we have a valid access token."""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        return await self.fetch_access_token()

    async def connect(self):
        """Connect to ShareCRM IM Gateway via SSE."""
        if self._sse_task or self._connecting:
            return
        
        self._connecting = True
        self._should_reconnect = True
        
        try:
            token = await self.ensure_token()
            url = f"{self.account.gateway_base_url}/im-gateway/bot/events?token={token}"
            self.log(f"sharecrm[{self.account.account_id}]: Connecting to SSE {url.split('?')[0]}?token=***")
            
            client = await self._get_http_client()
            
            async with client.stream("GET", url, headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }) as response:
                self._connecting = False
                
                if response.status_code != 200:
                    self.log(f"sharecrm[{self.account.account_id}]: SSE connection failed, status={response.status_code}")
                    self._schedule_reconnect()
                    return
                
                self.log(f"sharecrm[{self.account.account_id}]: SSE connection established")
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    buffer = await self._parse_sse_buffer(buffer)
                
                self.log(f"sharecrm[{self.account.account_id}]: SSE connection closed")
                was_connected = self._connected
                self._connected = False
                if was_connected:
                    self.on_disconnected("SSE connection closed")
                self._schedule_reconnect()
                
        except Exception as e:
            self._connecting = False
            self.log(f"sharecrm[{self.account.account_id}]: Connection error: {e}")
            self._connected = False
            if self.on_error:
                self.on_error(e)
            self._schedule_reconnect()

    async def _parse_sse_buffer(self, buffer: str) -> str:
        """Parse SSE event stream buffer."""
        blocks = buffer.split("\n\n")
        remaining = blocks.pop() if blocks else ""
        
        for block in blocks:
            if not block.strip():
                continue
            
            event_name = "message"
            data_lines = []
            
            for line in block.split("\n"):
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].strip())
            
            if data_lines:
                await self._handle_event(event_name, "\n".join(data_lines))
        
        return remaining

    async def _handle_event(self, event_name: str, data: str):
        """Handle parsed SSE event."""
        try:
            msg = json.loads(data)
            
            # Debug: log all events except ping
            if msg.get("type") != "ping":
                self.log(f"sharecrm[{self.account.account_id}]: Received event '{event_name}': {json.dumps(msg)[:200]}")
            
            if event_name == "connected" or msg.get("type") == "connected":
                self._connected = True
                bot_id = msg.get("data", {}).get("bot_id", "unknown")
                self.log(f"sharecrm[{self.account.account_id}]: Authenticated as {bot_id}")
                self.on_connected(bot_id)
            
            elif msg.get("type") == "message":
                await self.on_message(msg)
            
            elif msg.get("type") == "error":
                error_info = msg.get("error", {})
                self.log(f"sharecrm[{self.account.account_id}]: Error [{error_info.get('code')}]: {error_info.get('message')}")
                if self.on_error:
                    self.on_error(Exception(f"[{error_info.get('code')}] {error_info.get('message')}"))
            
            elif msg.get("type") == "ping":
                pass  # Don't log ping events
            
        except json.JSONDecodeError as e:
            self.log(f"sharecrm[{self.account.account_id}]: Failed to parse event: {e}")

    async def send_message(self, chat_id: str, text: str) -> Optional[dict]:
        """Send a message to a chat via REST API."""
        try:
            token = await self.ensure_token()
            client = await self._get_http_client()
            url = f"{self.account.gateway_base_url}/im-gateway/qixin/message/send"
            
            payload = {"chat_id": chat_id, "text": text}
            logger.info("ShareCRM API call: url={}, chat_id={}, text_length={}", url, chat_id, len(text))
            
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            
            data = response.json()
            logger.info("ShareCRM API response: status_code={}, response={}", response.status_code, data)
            
            if data.get("code") == 0 and data.get("data", {}).get("message_id"):
                return {"messageId": data["data"]["message_id"], "chatId": chat_id}
            
            self.log(f"sharecrm[{self.account.account_id}]: Failed to send message: {data.get('msg', 'Unknown error')}")
            return None
            
        except Exception as e:
            self.log(f"sharecrm[{self.account.account_id}]: Send message error: {e}")
            return None

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt."""
        if not self._should_reconnect:
            return
        
        if self._reconnect_timer:
            return
        
        self.log(f"sharecrm[{self.account.account_id}]: Reconnecting in {RECONNECT_DELAY_MS}ms...")
        
        async def do_reconnect():
            await asyncio.sleep(RECONNECT_DELAY_MS / 1000)
            self._reconnect_timer = None
            if self._should_reconnect:
                await self.connect()
        
        self._reconnect_timer = asyncio.create_task(do_reconnect())

    async def disconnect(self):
        """Disconnect and stop reconnecting."""
        self._should_reconnect = False
        
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None
        
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        self._connected = False


class ShareCrmChannel(BaseChannel):
    """ShareCRM channel implementation."""

    name = "sharecrm"

    def __init__(self, config: ShareCrmConfig, bus: MessageBus, **channel_kwargs):
        super().__init__(config, bus, **channel_kwargs)
        self.config: ShareCrmConfig = config
        self._client: Optional[ShareCrmClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._processed_message_ids: OrderedDict[str, None] = OrderedDict()
        self._recent_contents: OrderedDict[str, float] = OrderedDict()
        self._direct_chat_by_user: dict[str, str] = {}  # user_id -> chat_id mapping

    @property
    def channel_name(self) -> str:
        return "sharecrm"

    async def start(self) -> None:
        """Start the ShareCRM channel."""
        if not self.config.app_id or not self.config.app_secret:
            logger.error("ShareCRM app_id and app_secret not configured")
            return
        
        self._loop = asyncio.get_running_loop()
        
        account = ShareCrmAccount(
            account_id="default",
            enabled=self.config.enabled,
            configured=True,
            name=None,
            gateway_base_url=self.config.gateway_base_url or DEFAULT_GATEWAY_BASE_URL,
            app_id=self.config.app_id,
            app_secret=self.config.app_secret,
            config=self.config,
        )
        
        self._client = ShareCrmClient(
            account=account,
            on_connected=self._on_connected,
            on_message=self._on_message,
            on_disconnected=self._on_disconnected,
            on_error=self._on_error,
            log=logger.info,
        )
        
        await self._client.connect()

    async def stop(self) -> None:
        """Stop the ShareCRM channel."""
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def send(self, message: OutboundMessage) -> None:
        """Send a message to ShareCRM."""
        logger.info("ShareCRM send called: channel={}, chat_id={}, content_length={}", 
                    message.channel, message.chat_id, len(message.content or ""))
        
        if not self._client:
            logger.error("ShareCRM client not connected")
            return
        
        text = message.content or ""
        if not text.strip():
            logger.warning("ShareCRM: Empty message content, skipping")
            return
        
        # Use chat_id from message (may need to resolve user_id to chat_id)
        chat_id = message.chat_id
        
        # If chat_id looks like a user_id, try to resolve it
        if chat_id.startswith("E.fs.") or chat_id in self._direct_chat_by_user:
            chat_id = self._direct_chat_by_user.get(chat_id, message.chat_id)
        
        if not chat_id:
            logger.error(f"ShareCRM: Cannot resolve chat_id for {message.chat_id}")
            return
        
        logger.info("ShareCRM sending to chat_id: {}", chat_id)
        
        # Chunk message if needed
        chunk_limit = self.config.text_chunk_limit
        chunks = self._chunk_text(text, chunk_limit)
        
        for chunk in chunks:
            result = await self._client.send_message(chat_id, chunk)
            if result:
                logger.info(f"ShareCRM message sent to {chat_id}: {result.get('messageId')}")
            else:
                logger.error(f"ShareCRM failed to send message to {chat_id}")

    def _resolve_chat_id(self, target: str) -> Optional[str]:
        """Resolve chat_id from target string."""
        if not target:
            return None
        
        target = target.strip()
        
        # chat:<chat_id> format
        if target.startswith("chat:"):
            return target[5:].strip()
        
        # user:<user_id> format - lookup direct chat mapping
        if target.startswith("user:"):
            user_id = target[5:].strip()
            return self._direct_chat_by_user.get(user_id)
        
        # Direct chat_id or user_id
        if target in self._direct_chat_by_user:
            return self._direct_chat_by_user[target]
        
        return target

    def _chunk_text(self, text: str, limit: int) -> list[str]:
        """Split text into chunks within the limit."""
        if len(text) <= limit:
            return [text]
        
        chunks = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            
            # Try to break at newline or space
            break_point = text.rfind("\n", 0, limit)
            if break_point == -1:
                break_point = text.rfind(" ", 0, limit)
            if break_point == -1:
                break_point = limit
            
            chunks.append(text[:break_point].strip())
            text = text[break_point:].strip()
        
        return chunks

    def _on_connected(self, bot_id: str):
        """Handle SSE connection established."""
        logger.info(f"ShareCRM connected as bot {bot_id}")

    def _on_disconnected(self, reason: str):
        """Handle SSE disconnection."""
        logger.warning(f"ShareCRM disconnected: {reason}")

    def _on_error(self, error: Exception):
        """Handle connection error."""
        logger.error(f"ShareCRM error: {error}")

    async def _on_message(self, event: dict):
        """Handle incoming message from ShareCRM."""
        try:
            data = event.get("data", {})
            
            chat_id = data.get("chat_id")
            chat_type = data.get("chat_type", "direct")
            sender = data.get("from", {})
            sender_id = sender.get("id")
            sender_name = sender.get("name", sender_id)
            message_id = data.get("message_id")
            text = data.get("text", "")
            timestamp = data.get("date", int(time.time()))
            
            if not sender_id or not chat_id or not message_id:
                return
            
            # Deduplication by message_id
            if message_id in self._processed_message_ids:
                return
            self._processed_message_ids[message_id] = None
            while len(self._processed_message_ids) > 1000:
                self._processed_message_ids.popitem(last=False)
            
            # Content-based deduplication (5 minute window)
            import hashlib
            content_hash = hashlib.md5(f"{sender_id}:{text}".encode()).hexdigest()
            current_time = time.time()
            if content_hash in self._recent_contents:
                last_time = self._recent_contents[content_hash]
                if current_time - last_time < 300:
                    logger.debug(f"Skipping duplicate content from {sender_id}")
                    return
            self._recent_contents[content_hash] = current_time
            while len(self._recent_contents) > 100:
                oldest_key, oldest_time = next(iter(self._recent_contents.items()))
                if current_time - oldest_time > 300:
                    self._recent_contents.popitem(last=False)
                else:
                    break
            
            is_group = chat_type == "group"
            
            # Remember direct chat mapping
            if not is_group:
                self._direct_chat_by_user[sender_id] = chat_id
            
            # Check permissions
            if not self._check_permission(is_group, chat_id, sender_id, sender_name):
                return
            
            logger.info(f"ShareCRM message from {sender_name} ({sender_id}) in {chat_type} {chat_id}: {text[:50]}...")
            
            # Create inbound message
            from horbot.bus.events import InboundMessage
            
            message = InboundMessage(
                channel="sharecrm",
                sender_id=sender_id,
                chat_id=chat_id,
                content=text,
                channel_instance_id=self.endpoint_id,
                target_agent_id=self.target_agent_id,
                metadata={
                    "channel_instance_id": self.endpoint_id,
                    "target_agent_id": self.target_agent_id,
                    "channel_type": self.name,
                    "channel_endpoint_name": self.endpoint_name,
                    "sender_name": sender_name,
                    "chat_type": chat_type,
                    "message_id": message_id,
                    "timestamp": timestamp,
                    "raw_event": event,
                },
            )
            
            # Publish to message bus
            await self.bus.publish_inbound(message)
            
        except Exception as e:
            logger.error(f"ShareCRM message handling error: {e}")

    def _check_permission(self, is_group: bool, chat_id: str, sender_id: str, sender_name: str) -> bool:
        """Check if the message is allowed based on policy."""
        if is_group:
            group_policy = self.config.group_policy
            
            if group_policy == "disabled":
                logger.debug(f"ShareCRM: Group chat disabled, ignoring {chat_id}")
                return False
            
            if group_policy == "allowlist":
                group_allow = self.config.group_allow_from
                if chat_id not in group_allow and "*" not in group_allow:
                    logger.debug(f"ShareCRM: Group {chat_id} not in allowlist")
                    return False
        else:
            dm_policy = self.config.dm_policy
            
            if dm_policy == "disabled":
                logger.debug(f"ShareCRM: DM disabled, ignoring {sender_id}")
                return False
            
            if dm_policy == "allowlist":
                allow_from = self.config.allow_from
                if sender_id not in allow_from and sender_name not in allow_from and "*" not in allow_from:
                    logger.debug(f"ShareCRM: User {sender_id} not in allowlist")
                    return False
            
            # Note: pairing mode would require additional state management
            # For now, treat pairing as allowlist
            if dm_policy == "pairing":
                allow_from = self.config.allow_from
                if sender_id not in allow_from and "*" not in allow_from:
                    logger.debug(f"ShareCRM: User {sender_id} not paired")
                    return False
        
        return True
