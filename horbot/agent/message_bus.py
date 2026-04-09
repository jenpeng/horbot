"""Message bus for agent communication."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from loguru import logger

from horbot.agent.team_protocols import (
    ActionType,
    AgentMessage,
    MessagePriority,
)


@dataclass
class Subscription:
    """Message subscription."""
    subscriber_id: str
    callback: Callable[[AgentMessage], None]
    actions: set[ActionType] = field(default_factory=set)
    senders: set[str] = field(default_factory=set)


class MessageBus:
    """Central message bus for agent communication.
    
    Features:
    - Publish/subscribe pattern
    - Priority-based message handling
    - Message persistence
    - Team broadcast support
    """
    
    _instance: Optional["MessageBus"] = None
    
    def __new__(cls) -> "MessageBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscriptions: list[Subscription] = []
            cls._instance._queues: dict[str, asyncio.Queue] = {}
            cls._instance._message_history: list[AgentMessage] = []
            cls._instance._max_history = 1000
            cls._instance._initialized = False
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "MessageBus":
        return cls()
    
    def _get_queue(self, receiver_id: str) -> asyncio.Queue:
        if receiver_id not in self._queues:
            self._queues[receiver_id] = asyncio.Queue()
        return self._queues[receiver_id]
    
    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[AgentMessage], None],
        actions: set[ActionType] | None = None,
        senders: set[str] | None = None,
    ) -> Subscription:
        """Subscribe to messages.
        
        Args:
            subscriber_id: Subscriber identifier
            callback: Callback function for messages
            actions: Filter by action types (None = all)
            senders: Filter by senders (None = all)
            
        Returns:
            Subscription object
        """
        subscription = Subscription(
            subscriber_id=subscriber_id,
            callback=callback,
            actions=actions or set(),
            senders=senders or set(),
        )
        
        self._subscriptions.append(subscription)
        logger.debug(f"Subscribed {subscriber_id} to messages")
        
        return subscription
    
    def unsubscribe(self, subscription: Subscription) -> None:
        """Unsubscribe from messages."""
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)
    
    async def publish(self, message: AgentMessage) -> None:
        """Publish a message to all matching subscribers.
        
        Args:
            message: Message to publish
        """
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]
        
        for subscription in self._subscriptions:
            if subscription.actions and message.action not in subscription.actions:
                continue
            if subscription.senders and message.sender not in subscription.senders:
                continue
            
            try:
                if asyncio.iscoroutinefunction(subscription.callback):
                    await subscription.callback(message)
                else:
                    subscription.callback(message)
            except Exception as e:
                logger.error(f"Error in subscription callback: {e}")
        
        if message.receiver != "broadcast":
            queue = self._get_queue(message.receiver)
            await queue.put(message)
    
    async def receive(
        self,
        receiver_id: str,
        timeout: float | None = None,
    ) -> AgentMessage | None:
        """Receive next message for a receiver.
        
        Args:
            receiver_id: Receiver identifier
            timeout: Timeout in seconds
            
        Returns:
            Next message or None
        """
        try:
            queue = self._get_queue(receiver_id)
            if timeout:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            return await queue.get()
        except asyncio.TimeoutError:
            return None
    
    async def send_to_agent(
        self,
        sender_id: str,
        receiver_id: str,
        action: ActionType,
        payload: dict,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> None:
        """Send a message to a specific agent.
        
        Args:
            sender_id: Sender identifier
            receiver_id: Receiver identifier
            action: Action type
            payload: Message payload
            priority: Message priority
        """
        message = AgentMessage(
            sender=sender_id,
            receiver=receiver_id,
            action=action,
            payload=payload,
            priority=priority,
        )
        await self.publish(message)
    
    async def broadcast(
        self,
        sender_id: str,
        action: ActionType,
        payload: dict,
    ) -> None:
        """Broadcast a message to all agents.
        
        Args:
            sender_id: Sender identifier
            action: Action type
            payload: Message payload
        """
        message = AgentMessage(
            sender=sender_id,
            receiver="broadcast",
            action=action,
            payload=payload,
        )
        await self.publish(message)
    
    async def broadcast_to_team(
        self,
        sender_id: str,
        team_id: str,
        action: ActionType,
        payload: dict,
    ) -> None:
        """Broadcast a message to all members of a team.
        
        Args:
            sender_id: Sender identifier
            team_id: Team identifier
            action: Action type
            payload: Message payload
        """
        from horbot.team.manager import get_team_manager
        
        team_manager = get_team_manager()
        team = team_manager.get_team(team_id)
        
        if team:
            for member_id in team.members:
                if member_id != sender_id:
                    await self.send_to_agent(
                        sender_id=sender_id,
                        receiver_id=member_id,
                        action=action,
                        payload=payload,
                    )
    
    def get_history(
        self,
        agent_id: str | None = None,
        action: ActionType | None = None,
        limit: int = 100,
    ) -> list[AgentMessage]:
        """Get message history.
        
        Args:
            agent_id: Filter by agent (sender or receiver)
            action: Filter by action type
            limit: Maximum number of messages
            
        Returns:
            List of messages
        """
        messages = self._message_history
        
        if agent_id:
            messages = [
                m for m in messages
                if m.sender == agent_id or m.receiver == agent_id
            ]
        
        if action:
            messages = [m for m in messages if m.action == action]
        
        return messages[-limit:]
    
    def clear_queue(self, receiver_id: str) -> None:
        """Clear message queue for a receiver."""
        self._queues[receiver_id] = asyncio.Queue()
    
    def get_queue_size(self, receiver_id: str) -> int:
        """Get the number of pending messages for a receiver."""
        return self._get_queue(receiver_id).qsize()


def get_message_bus() -> MessageBus:
    """Get the singleton MessageBus instance."""
    return MessageBus.get_instance()
