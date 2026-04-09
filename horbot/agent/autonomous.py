"""Autonomous agents module - idle loop and automatic task claiming."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger

from horbot.agent.team_protocols import (
    AgentMessage,
    AgentMailbox,
    ActionType,
    TaskBoard,
    TeamCoordinator,
)


class AgentState(Enum):
    """Autonomous agent states."""
    
    IDLE = "idle"
    SCANNING = "scanning"
    CLAIMING = "claiming"
    EXECUTING = "executing"
    REPORTING = "reporting"
    STOPPED = "stopped"


@dataclass
class AutonomousAgentConfig:
    """Configuration for autonomous agent behavior."""
    
    enabled: bool = True
    idle_interval: float = 30.0  # seconds between scans
    max_concurrent_tasks: int = 1
    task_timeout: float = 300.0  # seconds
    retry_failed_tasks: bool = True
    max_retries: int = 3
    capabilities: set[str] = field(default_factory=set)


class AutonomousAgent:
    """An agent that can autonomously scan for and claim tasks.
    
    The agent runs an idle loop that periodically checks the task board
    for tasks matching its capabilities. When found, it claims and executes
    the task.
    
    Example:
        agent = AutonomousAgent(
            agent_id="worker-1",
            capabilities={"file_ops", "shell"},
            task_executor=my_executor,
        )
        await agent.start()
    """
    
    def __init__(
        self,
        agent_id: str,
        capabilities: set[str],
        task_executor: Callable[[dict], Any],
        task_board: TaskBoard | None = None,
        coordinator: TeamCoordinator | None = None,
        config: AutonomousAgentConfig | None = None,
    ):
        """Initialize autonomous agent.
        
        Args:
            agent_id: Unique agent identifier
            capabilities: Set of capabilities this agent has
            task_executor: Async function to execute tasks
            task_board: Shared task board
            coordinator: Team coordinator for messaging
            config: Agent configuration
        """
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.task_executor = task_executor
        self.task_board = task_board or TaskBoard()
        self.coordinator = coordinator
        self.config = config or AutonomousAgentConfig(capabilities=capabilities)
        
        self._state = AgentState.IDLE
        self._current_task: dict | None = None
        self._running = False
        self._mailbox: AgentMailbox | None = None
        self._task: asyncio.Task | None = None
        
    @property
    def state(self) -> AgentState:
        """Current agent state."""
        return self._state
    
    @property
    def is_idle(self) -> bool:
        """Check if agent is idle."""
        return self._state == AgentState.IDLE and self._current_task is None
    
    async def start(self) -> None:
        """Start the autonomous agent loop."""
        if self._running:
            logger.warning(f"Agent {self.agent_id} already running")
            return
        
        self._running = True
        self._state = AgentState.IDLE
        
        if self.coordinator:
            self._mailbox = self.coordinator.register_agent(
                self.agent_id,
                self.capabilities,
            )
        
        self._task = asyncio.create_task(self._autonomous_loop())
        logger.info(f"Autonomous agent {self.agent_id} started")
    
    async def stop(self) -> None:
        """Stop the autonomous agent."""
        self._running = False
        self._state = AgentState.STOPPED
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        if self.coordinator:
            self.coordinator.unregister_agent(self.agent_id)
        
        logger.info(f"Autonomous agent {self.agent_id} stopped")
    
    async def _autonomous_loop(self) -> None:
        """Main autonomous loop - scan, claim, execute, report."""
        while self._running:
            try:
                if self._current_task is None:
                    await self._scan_and_claim()
                
                if self._current_task:
                    await self._execute_current_task()
                
                await self._check_messages()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Agent {self.agent_id} error: {e}")
                self._state = AgentState.IDLE
            
            await asyncio.sleep(self.config.idle_interval)
    
    async def _scan_and_claim(self) -> None:
        """Scan task board and claim a matching task."""
        self._state = AgentState.SCANNING
        
        if self.coordinator:
            self.coordinator.update_status(self.agent_id, "scanning")
        
        pending_tasks = await self.task_board.list_tasks(status="pending")
        
        for task in pending_tasks:
            if not self._running:
                break
            
            if self._can_handle(task):
                self._state = AgentState.CLAIMING
                
                claimed = await self.task_board.claim_task(
                    task["id"],
                    self.agent_id,
                )
                
                if claimed:
                    self._current_task = task
                    logger.info(f"Agent {self.agent_id} claimed task: {task['id']}")
                    
                    if self.coordinator:
                        await self.coordinator.broadcast(
                            sender=self.agent_id,
                            action=ActionType.TASK_CLAIM,
                            payload={"task_id": task["id"]},
                        )
                    return
        
        self._state = AgentState.IDLE
        if self.coordinator:
            self.coordinator.update_status(self.agent_id, "idle")
    
    def _can_handle(self, task: dict) -> bool:
        """Check if agent can handle a task.
        
        Args:
            task: Task dict
            
        Returns:
            True if agent has required capabilities
        """
        required = set(task.get("required_capabilities", []))
        return required.issubset(self.capabilities)
    
    async def _execute_current_task(self) -> None:
        """Execute the current claimed task."""
        if not self._current_task:
            return
        
        self._state = AgentState.EXECUTING
        task_id = self._current_task["id"]
        
        if self.coordinator:
            self.coordinator.update_status(self.agent_id, "executing")
        
        logger.info(f"Agent {self.agent_id} executing task: {task_id}")
        
        try:
            result = await asyncio.wait_for(
                self.task_executor(self._current_task),
                timeout=self.config.task_timeout,
            )
            
            await self.task_board.complete_task(task_id, result)
            logger.info(f"Agent {self.agent_id} completed task: {task_id}")
            
            if self.coordinator:
                await self.coordinator.broadcast(
                    sender=self.agent_id,
                    action=ActionType.TASK_COMPLETE,
                    payload={"task_id": task_id, "result": str(result)[:500]},
                )
            
        except asyncio.TimeoutError:
            error = f"Task {task_id} timed out after {self.config.task_timeout}s"
            await self.task_board.fail_task(task_id, error)
            logger.warning(f"Agent {self.agent_id} task timeout: {task_id}")
            
            if self.coordinator:
                await self.coordinator.broadcast(
                    sender=self.agent_id,
                    action=ActionType.TASK_FAILED,
                    payload={"task_id": task_id, "error": error},
                )
            
        except Exception as e:
            error = str(e)
            await self.task_board.fail_task(task_id, error)
            logger.error(f"Agent {self.agent_id} task failed: {task_id} - {error}")
            
            if self.coordinator:
                await self.coordinator.broadcast(
                    sender=self.agent_id,
                    action=ActionType.TASK_FAILED,
                    payload={"task_id": task_id, "error": error},
                )
        
        finally:
            self._current_task = None
            self._state = AgentState.IDLE
            
            if self.coordinator:
                self.coordinator.update_status(self.agent_id, "idle")
    
    async def _check_messages(self) -> None:
        """Check for incoming messages."""
        if not self._mailbox:
            return
        
        message = await self._mailbox.receive(timeout=0.1)
        if message:
            await self._handle_message(message)
    
    async def _handle_message(self, message: AgentMessage) -> None:
        """Handle incoming message.
        
        Args:
            message: Incoming message
        """
        logger.debug(f"Agent {self.agent_id} received: {message.action.value}")
        
        if message.action == ActionType.SHUTDOWN:
            await self.stop()
        
        elif message.action == ActionType.STATUS_QUERY:
            if self.coordinator:
                response = AgentMessage(
                    sender=self.agent_id,
                    receiver=message.sender,
                    action=ActionType.STATUS_RESPONSE,
                    payload={
                        "state": self._state.value,
                        "current_task": self._current_task["id"] if self._current_task else None,
                        "capabilities": list(self.capabilities),
                    },
                    correlation_id=message.correlation_id,
                )
                await self.coordinator.send_message(response)
    
    def get_status(self) -> dict:
        """Get agent status.
        
        Returns:
            Dict with agent status information
        """
        return {
            "agent_id": self.agent_id,
            "state": self._state.value,
            "capabilities": list(self.capabilities),
            "current_task": self._current_task["id"] if self._current_task else None,
            "running": self._running,
            "config": {
                "idle_interval": self.config.idle_interval,
                "max_concurrent_tasks": self.config.max_concurrent_tasks,
                "task_timeout": self.config.task_timeout,
            },
        }


class AutonomousAgentManager:
    """Manages multiple autonomous agents.
    
    Provides utilities for starting, stopping, and monitoring agents.
    """
    
    def __init__(self, task_board: TaskBoard | None = None):
        """Initialize manager.
        
        Args:
            task_board: Shared task board
        """
        self.task_board = task_board or TaskBoard()
        self.coordinator = TeamCoordinator()
        self._agents: dict[str, AutonomousAgent] = {}
    
    def create_agent(
        self,
        agent_id: str,
        capabilities: set[str],
        task_executor: Callable[[dict], Any],
        config: AutonomousAgentConfig | None = None,
    ) -> AutonomousAgent:
        """Create a new autonomous agent.
        
        Args:
            agent_id: Agent identifier
            capabilities: Agent capabilities
            task_executor: Task execution function
            config: Agent configuration
            
        Returns:
            Created agent
        """
        if agent_id in self._agents:
            raise ValueError(f"Agent {agent_id} already exists")
        
        agent = AutonomousAgent(
            agent_id=agent_id,
            capabilities=capabilities,
            task_executor=task_executor,
            task_board=self.task_board,
            coordinator=self.coordinator,
            config=config,
        )
        
        self._agents[agent_id] = agent
        return agent
    
    async def start_all(self) -> None:
        """Start all agents."""
        for agent in self._agents.values():
            await agent.start()
    
    async def stop_all(self) -> None:
        """Stop all agents."""
        for agent in self._agents.values():
            await agent.stop()
    
    async def start_agent(self, agent_id: str) -> bool:
        """Start a specific agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if agent was started
        """
        agent = self._agents.get(agent_id)
        if agent:
            await agent.start()
            return True
        return False
    
    async def stop_agent(self, agent_id: str) -> bool:
        """Stop a specific agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if agent was stopped
        """
        agent = self._agents.get(agent_id)
        if agent:
            await agent.stop()
            return True
        return False
    
    def get_agent(self, agent_id: str) -> AutonomousAgent | None:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> list[dict]:
        """List all agents with their status."""
        return [agent.get_status() for agent in self._agents.values()]
    
    def get_team_status(self) -> dict:
        """Get overall team status."""
        return {
            "total_agents": len(self._agents),
            "agents": self.list_agents(),
            "coordinator": self.coordinator.get_team_status(),
        }
