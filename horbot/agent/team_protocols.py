"""Team protocols module - standardized agent communication protocols."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import uuid

from loguru import logger


class ActionType(Enum):
    """Standard action types for agent communication."""
    
    TASK_ASSIGN = "task_assign"
    TASK_UPDATE = "task_update"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    TASK_CLAIM = "task_claim"
    TASK_RELEASE = "task_release"
    TASK_QUERY = "task_query"
    STATUS_QUERY = "status_query"
    STATUS_RESPONSE = "status_response"
    CHAT_MESSAGE = "chat_message"
    CHAT_BROADCAST = "chat_broadcast"
    AGENT_INTRODUCE = "agent_introduce"
    COLLABORATION_REQUEST = "collaboration_request"
    COLLABORATION_ACCEPT = "collaboration_accept"
    COLLABORATION_REJECT = "collaboration_reject"
    COLLABORATION_END = "collaboration_end"
    KNOWLEDGE_SHARE = "knowledge_share"
    KNOWLEDGE_REQUEST = "knowledge_request"
    SHUTDOWN = "shutdown"
    HEARTBEAT = "heartbeat"
    PLAN_APPROVAL = "plan_approval"
    PLAN_REJECTED = "plan_rejected"


class MessagePriority(Enum):
    """Message priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgentMessage:
    """Standardized message format for agent communication.
    
    Attributes:
        sender: Sender agent ID
        receiver: Receiver agent ID (or "broadcast" for all)
        action: Action type
        payload: Message payload
        timestamp: Message timestamp
        correlation_id: ID for correlating request/response
        priority: Message priority
        ttl: Time-to-live in seconds (0 = no expiry)
    """
    
    sender: str
    receiver: str
    action: ActionType
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str | None = None
    priority: MessagePriority = MessagePriority.NORMAL
    ttl: int = 0
    
    def __post_init__(self):
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())[:8]
    
    def to_json(self) -> dict:
        """Serialize message to JSON-serializable dict."""
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "action": self.action.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "priority": self.priority.value,
            "ttl": self.ttl,
        }
    
    @classmethod
    def from_json(cls, data: dict) -> "AgentMessage":
        """Deserialize message from dict."""
        return cls(
            sender=data["sender"],
            receiver=data["receiver"],
            action=ActionType(data["action"]),
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data.get("correlation_id"),
            priority=MessagePriority(data.get("priority", "normal")),
            ttl=data.get("ttl", 0),
        )
    
    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.ttl == 0:
            return False
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > self.ttl


class AgentMailbox:
    """Async mailbox for agent message passing.
    
    Each agent has a mailbox for receiving messages from other agents.
    Messages are stored in a JSONL file for persistence.
    """
    
    def __init__(self, agent_id: str, mailbox_dir: str | Path = ".mailboxes"):
        """Initialize mailbox.
        
        Args:
            agent_id: Agent identifier
            mailbox_dir: Directory for mailbox files
        """
        self.agent_id = agent_id
        self.mailbox_dir = Path(mailbox_dir)
        self.mailbox_dir.mkdir(parents=True, exist_ok=True)
        self.mailbox_file = self.mailbox_dir / f"{agent_id}.jsonl"
        self._queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._running = False
        
    async def send(self, message: AgentMessage) -> None:
        """Send message to this mailbox.
        
        Args:
            message: Message to send
        """
        await self._queue.put(message)
        self._append_to_file(message)
        logger.debug(f"Message sent to {self.agent_id}: {message.action.value}")
    
    async def receive(self, timeout: float | None = None) -> AgentMessage | None:
        """Receive next message from mailbox.
        
        Args:
            timeout: Timeout in seconds (None = wait forever)
            
        Returns:
            Next message or None if timeout
        """
        try:
            if timeout:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None
    
    def _append_to_file(self, message: AgentMessage) -> None:
        """Append message to JSONL file for persistence."""
        try:
            with open(self.mailbox_file, "a") as f:
                f.write(json.dumps(message.to_json()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist message: {e}")
    
    def load_pending(self) -> list[AgentMessage]:
        """Load pending messages from file.
        
        Returns:
            List of pending messages
        """
        messages = []
        if self.mailbox_file.exists():
            try:
                with open(self.mailbox_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            msg = AgentMessage.from_json(json.loads(line))
                            if not msg.is_expired():
                                messages.append(msg)
            except Exception as e:
                logger.warning(f"Failed to load messages: {e}")
        return messages
    
    def clear(self) -> None:
        """Clear mailbox."""
        self._queue = asyncio.Queue()
        if self.mailbox_file.exists():
            self.mailbox_file.unlink()


class TeamCoordinator:
    """Coordinates communication between multiple agents.
    
    Manages agent registration, message routing, and task distribution.
    """
    
    def __init__(self, coordinator_id: str = "coordinator"):
        """Initialize coordinator.
        
        Args:
            coordinator_id: Coordinator identifier
        """
        self.coordinator_id = coordinator_id
        self._mailboxes: dict[str, AgentMailbox] = {}
        self._agent_capabilities: dict[str, set[str]] = {}
        self._agent_status: dict[str, str] = {}  # agent_id -> status
        
    def register_agent(
        self,
        agent_id: str,
        capabilities: set[str] | None = None,
    ) -> AgentMailbox:
        """Register a new agent.
        
        Args:
            agent_id: Agent identifier
            capabilities: Set of agent capabilities
            
        Returns:
            Agent's mailbox
        """
        if agent_id in self._mailboxes:
            logger.warning(f"Agent {agent_id} already registered")
            return self._mailboxes[agent_id]
        
        mailbox = AgentMailbox(agent_id)
        self._mailboxes[agent_id] = mailbox
        self._agent_capabilities[agent_id] = capabilities or set()
        self._agent_status[agent_id] = "idle"
        
        logger.info(f"Registered agent: {agent_id} with capabilities: {capabilities}")
        return mailbox
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent.
        
        Args:
            agent_id: Agent identifier
        """
        self._mailboxes.pop(agent_id, None)
        self._agent_capabilities.pop(agent_id, None)
        self._agent_status.pop(agent_id, None)
        logger.info(f"Unregistered agent: {agent_id}")
    
    async def send_message(self, message: AgentMessage) -> bool:
        """Send message to target agent(s).
        
        Args:
            message: Message to send
            
        Returns:
            True if message was sent successfully
        """
        receiver = message.receiver
        
        if receiver == "broadcast":
            for agent_id, mailbox in self._mailboxes.items():
                if agent_id != message.sender:
                    await mailbox.send(message)
            return True
        
        if receiver in self._mailboxes:
            await self._mailboxes[receiver].send(message)
            return True
        
        logger.warning(f"Unknown receiver: {receiver}")
        return False
    
    async def broadcast(self, sender: str, action: ActionType, payload: dict) -> None:
        """Broadcast message to all agents.
        
        Args:
            sender: Sender agent ID
            action: Action type
            payload: Message payload
        """
        message = AgentMessage(
            sender=sender,
            receiver="broadcast",
            action=action,
            payload=payload,
        )
        await self.send_message(message)
    
    def find_capable_agents(self, required_capabilities: set[str]) -> list[str]:
        """Find agents with required capabilities.
        
        Args:
            required_capabilities: Set of required capabilities
            
        Returns:
            List of capable agent IDs
        """
        capable = []
        for agent_id, capabilities in self._agent_capabilities.items():
            if required_capabilities.issubset(capabilities):
                capable.append(agent_id)
        return capable
    
    def get_idle_agents(self) -> list[str]:
        """Get list of idle agents.
        
        Returns:
            List of idle agent IDs
        """
        return [
            agent_id for agent_id, status in self._agent_status.items()
            if status == "idle"
        ]
    
    def update_status(self, agent_id: str, status: str) -> None:
        """Update agent status.
        
        Args:
            agent_id: Agent identifier
            status: New status
        """
        self._agent_status[agent_id] = status
        logger.debug(f"Agent {agent_id} status: {status}")
    
    def get_team_status(self) -> dict[str, Any]:
        """Get overall team status.
        
        Returns:
            Dict with team status information
        """
        return {
            "total_agents": len(self._mailboxes),
            "agents": {
                agent_id: {
                    "status": self._agent_status.get(agent_id, "unknown"),
                    "capabilities": list(self._agent_capabilities.get(agent_id, set())),
                }
                for agent_id in self._mailboxes
            },
        }


class TaskBoard:
    """Shared task board for autonomous task claiming.
    
    Agents can scan the board and claim tasks that match their capabilities.
    """
    
    def __init__(self, board_dir: str | Path = ".taskboard"):
        """Initialize task board.
        
        Args:
            board_dir: Directory for task board files
        """
        self.board_dir = Path(board_dir)
        self.board_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        
    def _task_file(self, task_id: str) -> Path:
        """Get task file path."""
        return self.board_dir / f"{task_id}.json"
    
    async def add_task(
        self,
        task_id: str,
        title: str,
        description: str,
        required_capabilities: set[str] | None = None,
        priority: str = "normal",
        dependencies: list[str] | None = None,
    ) -> dict:
        """Add a task to the board.
        
        Args:
            task_id: Task identifier
            title: Task title
            description: Task description
            required_capabilities: Required capabilities
            priority: Task priority
            dependencies: List of task IDs this task depends on
            
        Returns:
            Task dict
        """
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "required_capabilities": list(required_capabilities or set()),
            "priority": priority,
            "dependencies": dependencies or [],
            "status": "pending",
            "claimed_by": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        async with self._lock:
            with open(self._task_file(task_id), "w") as f:
                json.dump(task, f, indent=2)
        
        logger.info(f"Added task to board: {task_id}")
        return task
    
    async def get_task(self, task_id: str) -> dict | None:
        """Get task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task dict or None
        """
        task_file = self._task_file(task_id)
        if not task_file.exists():
            return None
        
        async with self._lock:
            with open(task_file, "r") as f:
                return json.load(f)
    
    async def list_tasks(self, status: str | None = None) -> list[dict]:
        """List all tasks, optionally filtered by status.
        
        Args:
            status: Filter by status (pending, claimed, completed, failed)
            
        Returns:
            List of task dicts
        """
        tasks = []
        async with self._lock:
            for task_file in self.board_dir.glob("*.json"):
                with open(task_file, "r") as f:
                    task = json.load(f)
                    if status is None or task.get("status") == status:
                        tasks.append(task)
        
        tasks.sort(key=lambda t: t.get("created_at", ""))
        return tasks
    
    async def claim_task(self, task_id: str, agent_id: str) -> bool:
        """Claim a task.
        
        Args:
            task_id: Task identifier
            agent_id: Agent claiming the task
            
        Returns:
            True if claim was successful
        """
        async with self._lock:
            task = await self.get_task(task_id)
            if task is None:
                return False
            
            if task.get("status") != "pending":
                return False
            
            task["status"] = "claimed"
            task["claimed_by"] = agent_id
            task["updated_at"] = datetime.now().isoformat()
            
            with open(self._task_file(task_id), "w") as f:
                json.dump(task, f, indent=2)
        
        logger.info(f"Task {task_id} claimed by {agent_id}")
        return True
    
    async def complete_task(self, task_id: str, result: Any = None) -> bool:
        """Mark task as completed.
        
        Args:
            task_id: Task identifier
            result: Task result
            
        Returns:
            True if successful
        """
        async with self._lock:
            task = await self.get_task(task_id)
            if task is None:
                return False
            
            task["status"] = "completed"
            task["result"] = result
            task["updated_at"] = datetime.now().isoformat()
            
            with open(self._task_file(task_id), "w") as f:
                json.dump(task, f, indent=2)
        
        logger.info(f"Task {task_id} completed")
        return True
    
    async def fail_task(self, task_id: str, error: str) -> bool:
        """Mark task as failed.
        
        Args:
            task_id: Task identifier
            error: Error message
            
        Returns:
            True if successful
        """
        async with self._lock:
            task = await self.get_task(task_id)
            if task is None:
                return False
            
            task["status"] = "failed"
            task["error"] = error
            task["updated_at"] = datetime.now().isoformat()
            
            with open(self._task_file(task_id), "w") as f:
                json.dump(task, f, indent=2)
        
        logger.warning(f"Task {task_id} failed: {error}")
        return True


class TaskGraph:
    """Manages task dependencies and execution order.
    
    Provides:
    - Dependency graph management
    - Topological sort for execution order
    - Ready task detection
    """
    
    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self.dependencies: dict[str, list[str]] = {}
        self.status: dict[str, str] = {}
    
    def add_task(self, task_id: str, dependencies: list[str] | None = None) -> None:
        """Add a task with optional dependencies.
        
        Args:
            task_id: Task identifier
            dependencies: List of task IDs this task depends on
        """
        self.tasks[task_id] = {"id": task_id}
        self.dependencies[task_id] = dependencies or []
        self.status[task_id] = "pending"
        logger.debug(f"Added task {task_id} with dependencies: {dependencies}")
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the graph.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task was removed
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            del self.dependencies[task_id]
            del self.status[task_id]
            return True
        return False
    
    def get_ready_tasks(self) -> list[str]:
        """Get all tasks that are ready to execute.
        
        A task is ready if:
        - Status is "pending"
        - All dependencies are completed
        
        Returns:
            List of ready task IDs
        """
        ready = []
        for task_id in self.tasks:
            if self.status[task_id] != "pending":
                continue
            
            deps = self.dependencies.get(task_id, [])
            all_completed = all(
                self.status.get(dep) == "completed"
                for dep in deps
            )
            
            if all_completed:
                ready.append(task_id)
        
        return ready
    
    def get_blocked_tasks(self) -> dict[str, list[str]]:
        """Get tasks that are blocked by incomplete dependencies.
        
        Returns:
            Dict of task_id -> list of blocking dependency IDs
        """
        blocked = {}
        for task_id in self.tasks:
            if self.status[task_id] != "pending":
                continue
            
            incomplete_deps = [
                dep for dep in self.dependencies.get(task_id, [])
                if self.status.get(dep) != "completed"
            ]
            
            if incomplete_deps:
                blocked[task_id] = incomplete_deps
        
        return blocked
    
    def mark_completed(self, task_id: str) -> bool:
        """Mark a task as completed.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if successful
        """
        if task_id not in self.tasks:
            return False
        
        self.status[task_id] = "completed"
        logger.debug(f"Task {task_id} marked as completed")
        return True
    
    def mark_failed(self, task_id: str) -> bool:
        """Mark a task as failed.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if successful
        """
        if task_id not in self.tasks:
            return False
        
        self.status[task_id] = "failed"
        logger.debug(f"Task {task_id} marked as failed")
        return True
    
    def topological_sort(self) -> list[str]:
        """Get tasks in topological order.
        
        Returns:
            List of task IDs in execution order
        """
        visited = set()
        order = []
        
        def visit(task_id: str):
            if task_id in visited:
                return
            visited.add(task_id)
            
            for dep in self.dependencies.get(task_id, []):
                visit(dep)
            
            order.append(task_id)
        
        for task_id in self.tasks:
            visit(task_id)
        
        return order
    
    def get_execution_plan(self) -> list[list[str]]:
        """Get execution plan as layers.
        
        Each layer contains tasks that can be executed in parallel.
        
        Returns:
            List of layers, each layer is a list of task IDs
        """
        layers = []
        remaining = set(self.tasks.keys())
        completed = set()
        
        while remaining:
            layer = []
            for task_id in list(remaining):
                deps = set(self.dependencies.get(task_id, []))
                if deps.issubset(completed):
                    layer.append(task_id)
            
            if not layer:
                break
            
            layers.append(layer)
            completed.update(layer)
            remaining -= set(layer)
        
        return layers
    
    def get_status_summary(self) -> dict:
        """Get summary of task statuses.
        
        Returns:
            Dict with status counts
        """
        summary = {"pending": 0, "completed": 0, "failed": 0, "total": len(self.tasks)}
        for status in self.status.values():
            if status in summary:
                summary[status] += 1
        return summary
