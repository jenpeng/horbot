from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from horbot.bus.events import InboundMessage, OutboundMessage
from horbot.utils.helpers import parse_session_key_with_known_routes

if TYPE_CHECKING:
    from horbot.agent.loop import AgentLoop
    from horbot.session.manager import Session


class MessageProcessor:
    def __init__(self, agent_loop: "AgentLoop"):
        self.agent = agent_loop

    @staticmethod
    def _resolve_outbound_error_target(msg: InboundMessage) -> tuple[str, str]:
        """Map synthetic system messages back to the original outbound target."""
        if msg.channel != "system":
            return msg.channel, msg.chat_id

        if ":" in msg.chat_id:
            return parse_session_key_with_known_routes(msg.chat_id)

        return "cli", msg.chat_id

    async def dispatch(self, msg: InboundMessage) -> None:
        """Process a message under a per-session lock."""
        lock = self.agent._get_message_lock(msg.session_key)
        async with lock:
            try:
                response = await self.process_message(msg)
                if response is not None:
                    await self.agent.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.agent.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                channel, chat_id = self._resolve_outbound_error_target(msg)
                await self.agent.bus.publish_outbound(OutboundMessage(
                    channel=channel, chat_id=chat_id,
                    content="Sorry, I encountered an error.",
                ))
            finally:
                self.agent._prune_message_lock(msg.session_key, lock)

    @staticmethod
    def _tag_streamed_turn(
        session: "Session",
        start_index: int,
        metadata: dict[str, Any] | None,
    ) -> None:
        if not metadata:
            return

        turn_id = metadata.get("turn_id")
        assistant_message_id = metadata.get("assistant_message_id")
        request_id = metadata.get("request_id")
        if not turn_id and not assistant_message_id and not request_id:
            return

        saved_messages = session.messages[start_index:]
        if not saved_messages:
            return

        for entry in saved_messages:
            entry_meta = entry.setdefault("metadata", {})
            if turn_id:
                entry_meta.setdefault("turn_id", turn_id)
            if request_id:
                entry_meta.setdefault("request_id", request_id)

        for entry in reversed(saved_messages):
            if entry.get("role") != "assistant":
                continue
            entry_meta = entry.setdefault("metadata", {})
            if turn_id:
                entry_meta["turn_id"] = turn_id
            if request_id:
                entry_meta["request_id"] = request_id
            if assistant_message_id:
                entry["id"] = assistant_message_id
            break

    async def process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_tool_start: Callable[..., Awaitable[None]] | None = None,
        on_tool_result: Callable[..., Awaitable[None]] | None = None,
        on_status: Callable[..., Awaitable[None]] | None = None,
        on_thinking: Callable[..., Awaitable[None]] | None = None,
        on_step_start: Callable[..., Awaitable[None]] | None = None,
        on_step_complete: Callable[..., Awaitable[None]] | None = None,
        on_plan_created: Callable[..., Awaitable[None]] | None = None,
        on_plan_generating: Callable[..., Awaitable[None]] | None = None,
        on_plan_skipped: Callable[..., Awaitable[None]] | None = None,
        on_plan_progress: Callable[[str, str, str | None], Awaitable[None]] | None = None,
        speaking_to: str | None = None,
        conversation_type: str | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            channel, chat_id = (
                parse_session_key_with_known_routes(msg.chat_id)
                if ":" in msg.chat_id
                else ("cli", msg.chat_id)
            )
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.agent.sessions.get_or_create(key)
            self.agent._set_tool_context(channel, chat_id, msg.metadata.get("message_id") if msg.metadata else None)
            history = session.get_history(max_messages=self.agent.memory_window)
            messages = self.agent.context.build_messages(
                history=history,
                current_message=msg.content, channel=channel, chat_id=chat_id,
                session_key=key,
            )
            final_content, _, all_msgs, _, _ = await self.agent._run_agent_loop(messages, session_key=key)
            self.agent._save_turn(session, all_msgs, 1 + len(history))
            self.agent.sessions.save(session)
            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "Background task completed.")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.agent.sessions.get_or_create(key)
        
        if key in self.agent._active_plans:
            logger.info("Clearing previous planning context for session: {}", key)
            self.agent._active_plans.pop(key, None)

        if self.agent._is_new_task(msg.content, session):
            logger.info("Detected new task, clearing session context for: {}", key)
            session.clear()
            self.agent.sessions.save(session)
            if self.agent.use_hierarchical_context:
                self.agent.context.clear_session_context(key)

        cmd = msg.content.strip().lower()
        if cmd == "/new":
            lock = self.agent._get_consolidation_lock(session.key)
            self.agent._consolidating.add(session.key)
            try:
                async with lock:
                    snapshot = session.messages[session.last_consolidated:]
                    if snapshot:
                        from horbot.session.manager import Session
                        temp = Session(key=session.key)
                        temp.messages = list(snapshot)
                        if not await self.agent._consolidate_memory(temp, archive_all=True):
                            return OutboundMessage(
                                channel=msg.channel, chat_id=msg.chat_id,
                                content="Memory archival failed, session not cleared. Please try again.",
                            )
            except Exception:
                logger.exception("/new archival failed for {}", session.key)
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Memory archival failed, session not cleared. Please try again.",
                )
            finally:
                self.agent._consolidating.discard(session.key)
                self.agent._prune_consolidation_lock(session.key, lock)

            session.clear()
            self.agent.sessions.save(session)
            self.agent.sessions.invalidate(session.key)
            
            if self.agent.use_hierarchical_context:
                self.agent.context.clear_session_context(session.key)
            
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 horbot commands:\n/new — Start a new conversation\n/stop — Stop the current task\n/plan — Toggle planning mode for complex tasks\n/help — Show available commands")
        
        if cmd == "/plan":
            self.agent._planning_enabled = not self.agent._planning_enabled
            status = "enabled" if self.agent._planning_enabled else "disabled"
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                content=f"📋 Planning mode {status}."
            )
        
        if cmd in ("yes", "ok", "confirm") and session.key in self.agent._active_plans:
            plan = self.agent._active_plans.pop(session.key)
            return await self.agent._execute_plan(plan, msg, session)
        
        if cmd in ("no", "cancel") and session.key in self.agent._active_plans:
            self.agent._active_plans.pop(session.key)
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                content="📋 Plan cancelled."
            )

        pending_confirmations = getattr(session, '_pending_confirmations', {})
        confirmation_match = re.match(r'^(yes|no)\s+([a-f0-9]{8})$', cmd)
        if confirmation_match and pending_confirmations:
            action, confirm_id = confirmation_match.groups()
            if confirm_id in pending_confirmations:
                conf = pending_confirmations.pop(confirm_id)
                if action == "yes":
                    tool_name = conf["tool_name"]
                    arguments = conf["arguments"]
                    tool_call_id = conf["tool_call_id"]
                    messages = conf["messages"]
                    
                    logger.info("Tool {} confirmed by user: {}", tool_name, confirm_id)
                    result = await self.agent.tools.execute(tool_name, arguments)
                    messages = self.agent.context.add_tool_result(
                        messages, tool_call_id, tool_name, result
                    )
                    
                    async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
                        meta = dict(msg.metadata or {})
                        meta["_progress"] = True
                        meta["_tool_hint"] = tool_hint
                        await self.agent.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
                        ))
                    
                    final_content, _, all_msgs, _, error_info = await self.agent._run_agent_loop(
                        messages, on_progress=on_progress or _bus_progress,
                        pending_confirmations=pending_confirmations,
                        session_key=session.key,
                    )
                    
                    if final_content is None:
                        final_content = "I've completed processing but have no response to give."
                    
                    session._pending_confirmations = pending_confirmations
                    history = session.get_history(max_messages=self.agent.memory_window)
                    append_start = len(session.messages)
                    self.agent._save_turn(session, all_msgs, 1 + len(history))
                    self._tag_streamed_turn(session, append_start, msg.metadata)
                    self.agent.sessions.save(session)
                    
                    return OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=final_content,
                        metadata={
                            **(msg.metadata or {}),
                            **({"_provider_error": error_info} if error_info else {}),
                        },
                    )
                else:
                    logger.info("Tool {} cancelled by user: {}", conf["tool_name"], confirm_id)
                    pending_confirmations.pop(confirm_id, None)
                    session._pending_confirmations = pending_confirmations
                    self.agent.sessions.save(session)
                    return OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content=f"❌ Tool `{conf['tool_name']}` execution cancelled."
                    )

        unconsolidated = len(session.messages) - session.last_consolidated
        if (unconsolidated >= self.agent.memory_window and session.key not in self.agent._consolidating):
            self.agent._consolidating.add(session.key)
            lock = self.agent._get_consolidation_lock(session.key)

            async def _consolidate_and_unlock():
                try:
                    async with lock:
                        await self.agent._consolidate_memory(session)
                finally:
                    self.agent._consolidating.discard(session.key)
                    self.agent._prune_consolidation_lock(session.key, lock)
                    _task = asyncio.current_task()
                    if _task is not None:
                        self.agent._consolidation_tasks.discard(_task)

            _task = asyncio.create_task(_consolidate_and_unlock())
            self.agent._consolidation_tasks.add(_task)

        should_run_planning, force_legacy_planning = self.agent._resolve_planning_mode(msg)

        if should_run_planning:
            logger.info(
                "Planning mode triggered for message: legacy_mode={}, content='{}'",
                force_legacy_planning,
                (msg.content or "")[:80],
            )
            plan_result = await self.agent._run_planning_mode(
                msg, session, 
                on_plan_created=on_plan_created,
                on_plan_generating=on_plan_generating,
                on_plan_progress=on_plan_progress,
                on_progress=on_progress,
                on_thinking=on_thinking,
                on_step_start=on_step_start,
                on_step_complete=on_step_complete,
                force_legacy=force_legacy_planning,
            )
            if plan_result is None and session.key in self.agent._active_plans:
                return None
            if plan_result is not None:
                return plan_result
            logger.warning("Plan generation failed for task: {}", msg.content[:50])
            return OutboundMessage(
                channel=msg.channel, 
                chat_id=msg.chat_id,
                content="❌ 计划生成失败。请重试或简化您的请求。"
            )
        else:
            if on_plan_skipped:
                await on_plan_skipped()

        self.agent._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id") if msg.metadata else None)
        from horbot.agent.tools.message import MessageTool
        if message_tool := self.agent.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        raw_history = session.get_history(max_messages=self.agent.memory_window)
        
        conversation_ctx = None
        if msg.metadata and "conversation_context" in msg.metadata:
            from horbot.agent.conversation import ConversationContext
            try:
                conversation_ctx = ConversationContext.from_dict(msg.metadata["conversation_context"])
            except Exception as e:
                logger.warning(f"Failed to parse conversation_context: {e}")
        
        from horbot.agent.conversation import format_history_for_agent, ConversationType
        
        is_group_chat = (
            conversation_type == "group_chat"
            or (bool(msg.metadata.get("group_chat")) if msg.metadata else False)
            or (conversation_ctx and conversation_ctx.conversation_type == ConversationType.AGENT_TO_AGENT)
        )
        
        history = format_history_for_agent(
            raw_history,
            target_agent_id=self.agent._agent_id,
            target_agent_name=self.agent._agent_name or "horbot",
            conversation_ctx=conversation_ctx,
            is_group_chat=is_group_chat,
        )

        has_attachments = bool(
            msg.metadata and (msg.metadata.get("file_ids") or msg.metadata.get("files"))
        )
        use_fast_reply = self.agent.context.should_use_fast_reply(
            msg.content,
            history_size=len(history),
            has_media=bool(msg.media),
            has_attachments=has_attachments,
            web_search=bool(msg.metadata.get("web_search", False)) if msg.metadata else False,
        )

        if use_fast_reply:
            history_for_prompt = history[-self.agent.context.FAST_REPLY_HISTORY_LIMIT:]
            initial_messages = self.agent.context.build_fast_messages(
                history=history,
                current_message=msg.content,
                files=msg.metadata.get("files") if msg.metadata else None,
                channel=msg.channel,
                chat_id=msg.chat_id,
                runtime_hints=self.agent._build_bound_channel_runtime_hints(msg),
                speaking_to=speaking_to,
                conversation_type=conversation_type,
            )
            logger.info(
                "Using fast reply path for {}:{} (history trimmed to {})",
                msg.channel,
                msg.chat_id,
                len(history_for_prompt),
            )
        else:
            history_for_prompt = history
            initial_messages = self.agent.context.build_messages(
                history=history,
                current_message=msg.content,
                media=msg.media if msg.media else None,
                files=msg.metadata.get("files") if msg.metadata else None,
                channel=msg.channel, chat_id=msg.chat_id,
                session_key=session.key,
                runtime_hints=self.agent._build_bound_channel_runtime_hints(msg),
                speaking_to=speaking_to,
                conversation_type=conversation_type,
            )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.agent.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        final_content, _, all_msgs, confirmations, error_info = await self.agent._run_agent_loop(
            initial_messages, 
            on_progress=on_progress or _bus_progress,
            on_tool_start=on_tool_start,
            on_tool_result=on_tool_result,
            on_status=on_status,
            on_thinking=on_thinking,
            on_step_start=on_step_start,
            on_step_complete=on_step_complete,
            session_key=session.key,
            file_ids=msg.metadata.get("file_ids") if msg.metadata else None,
            web_search=msg.metadata.get("web_search", False) if msg.metadata else False,
            files=msg.metadata.get("files") if msg.metadata else None,
            tool_mode="none" if use_fast_reply else "smart",
            max_tokens_override=768 if use_fast_reply else None,
        )
        
        if confirmations:
            session._pending_confirmations = confirmations
            self.agent.sessions.save(session)
            
            confirm_id = list(confirmations.keys())[0]
            conf = confirmations[confirm_id]
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=final_content or "",
                metadata={
                    **(msg.metadata or {}),
                    "_confirmation_required": True,
                    "confirmation_id": confirm_id,
                    "tool_name": conf["tool_name"],
                    "tool_arguments": conf["arguments"],
                },
            )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        append_start = len(session.messages)
        self.agent._save_turn(session, all_msgs, 1 + len(history_for_prompt))
        self._tag_streamed_turn(session, append_start, msg.metadata)
        self.agent.sessions.save(session)

        if message_tool := self.agent.tools.get("message"):
            if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
                last_target = message_tool._last_target_channel
                if last_target and last_target != msg.channel:
                    if not final_content.strip():
                        final_content = f"✅ 消息已发送至 {last_target}"
                    return OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id, content=final_content,
                        metadata={
                            **(msg.metadata or {}),
                            **({"_provider_error": error_info} if error_info else {}),
                        },
                    )
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=final_content,
                    metadata={
                        **(msg.metadata or {}),
                        **({"_provider_error": error_info} if error_info else {}),
                    },
                )

        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata={
                **(msg.metadata or {}),
                **({"_provider_error": error_info} if error_info else {}),
            },
        )
