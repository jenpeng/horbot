"""Message tool for sending messages to users."""

from contextvars import ContextVar
from datetime import datetime
from typing import Any, Awaitable, Callable

from horbot.agent.tools.base import Tool
from horbot.bus.events import OutboundMessage


class MessageTool(Tool):
    """Tool to send messages to users on chat channels."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = "",
        default_message_id: str | None = None,
        default_channel_instance_id: str | None = None,
        default_target_agent_id: str | None = None,
    ):
        self._send_callback = send_callback
        self._default_channel_var: ContextVar[str] = ContextVar(
            f"message_default_channel_{id(self)}",
            default=default_channel,
        )
        self._default_chat_id_var: ContextVar[str] = ContextVar(
            f"message_default_chat_id_{id(self)}",
            default=default_chat_id,
        )
        self._default_message_id_var: ContextVar[str | None] = ContextVar(
            f"message_default_message_id_{id(self)}",
            default=default_message_id,
        )
        self._default_channel_instance_id_var: ContextVar[str | None] = ContextVar(
            f"message_default_channel_instance_id_{id(self)}",
            default=default_channel_instance_id,
        )
        self._default_target_agent_id_var: ContextVar[str | None] = ContextVar(
            f"message_default_target_agent_id_{id(self)}",
            default=default_target_agent_id,
        )
        self._sent_in_turn_var: ContextVar[bool] = ContextVar(
            f"message_sent_in_turn_{id(self)}",
            default=False,
        )
        self._last_target_channel_var: ContextVar[str | None] = ContextVar(
            f"message_last_target_channel_{id(self)}",
            default=None,
        )
        self._outbound_traces_var: ContextVar[list[dict[str, Any]]] = ContextVar(
            f"message_outbound_traces_{id(self)}",
            default=[],
        )

    @property
    def _sent_in_turn(self) -> bool:
        return self._sent_in_turn_var.get()

    @_sent_in_turn.setter
    def _sent_in_turn(self, value: bool) -> None:
        self._sent_in_turn_var.set(value)

    @property
    def _last_target_channel(self) -> str | None:
        return self._last_target_channel_var.get()

    @_last_target_channel.setter
    def _last_target_channel(self, value: str | None) -> None:
        self._last_target_channel_var.set(value)

    def set_context(
        self,
        channel: str,
        chat_id: str,
        message_id: str | None = None,
        channel_instance_id: str | None = None,
        target_agent_id: str | None = None,
    ) -> None:
        """Set the current message context."""
        self._default_channel_var.set(channel)
        self._default_chat_id_var.set(chat_id)
        self._default_message_id_var.set(message_id)
        self._default_channel_instance_id_var.set(channel_instance_id)
        self._default_target_agent_id_var.set(target_agent_id)

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback

    def start_turn(self) -> None:
        """Reset per-turn send tracking."""
        self._sent_in_turn = False
        self._last_target_channel = None
        self._outbound_traces_var.set([])

    def get_outbound_traces(self) -> list[dict[str, Any]]:
        """Return a copy of outbound traces captured in the current turn."""
        return [dict(trace) for trace in self._outbound_traces_var.get()]

    def _record_outbound_trace(self, msg: OutboundMessage) -> None:
        metadata = dict(msg.metadata or {})
        trace: dict[str, Any] = {
            "outbound_channel_type": metadata.get("outbound_channel_type") or msg.channel,
            "outbound_chat_id": metadata.get("outbound_chat_id") or msg.chat_id,
            "outbound_via": metadata.get("outbound_via") or "bus",
            "outbound_content_preview": (msg.content or "")[:200],
            "outbound_timestamp": metadata.get("outbound_timestamp") or datetime.now().isoformat(),
        }
        if msg.channel_instance_id:
            trace["outbound_channel_instance_id"] = msg.channel_instance_id
        if msg.target_agent_id:
            trace["outbound_target_agent_id"] = msg.target_agent_id
        if metadata.get("outbound_endpoint_name"):
            trace["outbound_endpoint_name"] = metadata["outbound_endpoint_name"]
        if msg.media:
            trace["outbound_media_count"] = len(msg.media)

        traces = self._outbound_traces_var.get()
        traces.append(trace)

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return """Send a message to the user.

╔══════════════════════════════════════════════════════════════════╗
║  THIS IS A TOOL - YOU MUST INVOKE IT, NOT WRITE IT AS TEXT      ║
╠══════════════════════════════════════════════════════════════════╣
║  ✓ CORRECT: Use your tool calling API to invoke this tool       ║
║  ✗ WRONG: Writing message("content") as text in your response   ║
╚══════════════════════════════════════════════════════════════════╝

CRITICAL INSTRUCTION: Call this tool ONCE per user turn. After calling this tool, STOP and wait for the user's next message. DO NOT call this tool multiple times in the same turn.

When you want to communicate with the user, invoke this tool using your native tool calling mechanism. The message will be displayed to the user automatically.

NEVER output Python-like function call syntax such as message("hello") in your response text. This is a tool that must be invoked through the tool calling API, not written as text."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message content to send"
                },
                "channel": {
                    "type": "string",
                    "description": "Optional: target channel (telegram, discord, etc.)"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Optional: target chat/user ID"
                },
                "channel_instance_id": {
                    "type": "string",
                    "description": "Optional: specific bound channel endpoint ID to route through"
                },
                "target_agent_id": {
                    "type": "string",
                    "description": "Optional: target agent ID used for outbound routing disambiguation"
                },
                "team_id": {
                    "type": "string",
                    "description": "Optional: target team ID when posting into a web team group chat"
                },
                "mentioned_agents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: agent IDs to trigger when posting into a team group chat"
                },
                "trigger_group_chat": {
                    "type": "boolean",
                    "description": "Optional: whether posting to a team group chat should trigger teammate follow-up processing"
                },
                "reply_to": {
                    "type": "string",
                    "description": "Optional: upstream message ID to reply to"
                },
                "media": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: list of file paths to attach (images, audio, documents)"
                }
            },
            "required": ["content"]
        }

    async def execute(
        self,
        content: str,
        channel: str | None = None,
        chat_id: str | None = None,
        message_id: str | None = None,
        channel_instance_id: str | None = None,
        target_agent_id: str | None = None,
        team_id: str | None = None,
        mentioned_agents: list[str] | None = None,
        trigger_group_chat: bool = False,
        reply_to: str | None = None,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> str:
        channel = channel or self._default_channel_var.get()
        chat_id = chat_id or self._default_chat_id_var.get()
        message_id = message_id or self._default_message_id_var.get()
        channel_instance_id = channel_instance_id or self._default_channel_instance_id_var.get()
        target_agent_id = target_agent_id or self._default_target_agent_id_var.get()
        reply_to = reply_to or message_id

        if not channel or not chat_id:
            return "Error: No target channel/chat specified"

        if not self._send_callback:
            return "Error: Message sending not configured"

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            channel_instance_id=channel_instance_id,
            target_agent_id=target_agent_id,
            reply_to=reply_to,
            media=media or [],
            metadata={
                **(metadata or {}),
                "message_id": message_id,
                "_source_channel": self._default_channel_var.get(),
                "_source_chat_id": self._default_chat_id_var.get(),
                "_source_channel_instance_id": self._default_channel_instance_id_var.get(),
                "_source_target_agent_id": self._default_target_agent_id_var.get(),
                **({"channel_instance_id": channel_instance_id} if channel_instance_id else {}),
                **({"target_agent_id": target_agent_id} if target_agent_id else {}),
                **({"team_id": team_id} if team_id else {}),
                **({"mentioned_agents": list(mentioned_agents or [])} if mentioned_agents else {}),
                **({"trigger_group_chat": True} if trigger_group_chat else {}),
            }
        )

        try:
            await self._send_callback(msg)
            self._sent_in_turn = True
            self._last_target_channel = channel_instance_id or channel
            self._record_outbound_trace(msg)
            media_info = f" with {len(media)} attachments" if media else ""
            endpoint_info = f" via {channel_instance_id}" if channel_instance_id else ""
            return f"Message sent to {channel}:{chat_id}{endpoint_info}{media_info}"
        except Exception as e:
            return f"Error sending message: {str(e)}"
