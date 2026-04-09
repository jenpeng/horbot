"""Agent status management for real-time status tracking."""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import asyncio

from loguru import logger


class AgentStatus(Enum):
    ONLINE = "online"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class AgentStatusInfo:
    agent_id: str
    agent_name: str
    status: AgentStatus = AgentStatus.ONLINE
    current_task: Optional[str] = None
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "current_task": self.current_task,
            "last_activity": self.last_activity,
            "metadata": self.metadata,
        }


class AgentStatusManager:
    _instance: Optional["AgentStatusManager"] = None
    
    def __init__(self):
        self._statuses: Dict[str, AgentStatusInfo] = {}
        self._status_change_callbacks: List[callable] = []
        self._typing_agents: Dict[str, List[str]] = {}
    
    @classmethod
    def get_instance(cls) -> "AgentStatusManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        initial_status: AgentStatus = AgentStatus.ONLINE,
    ) -> AgentStatusInfo:
        info = AgentStatusInfo(
            agent_id=agent_id,
            agent_name=agent_name,
            status=initial_status,
        )
        self._statuses[agent_id] = info
        return info
    
    def update_status(
        self,
        agent_id: str,
        status: AgentStatus,
        current_task: Optional[str] = None,
    ) -> Optional[AgentStatusInfo]:
        if agent_id not in self._statuses:
            return None
        
        info = self._statuses[agent_id]
        old_status = info.status
        info.status = status
        info.current_task = current_task
        info.last_activity = datetime.now().isoformat()
        
        if old_status != status:
            self._notify_status_change(info)
        
        return info
    
    def get_status(self, agent_id: str) -> Optional[AgentStatusInfo]:
        return self._statuses.get(agent_id)
    
    def get_all_statuses(self) -> List[AgentStatusInfo]:
        return list(self._statuses.values())
    
    def set_busy(self, agent_id: str, task: str) -> Optional[AgentStatusInfo]:
        return self.update_status(agent_id, AgentStatus.BUSY, task)
    
    def set_online(self, agent_id: str) -> Optional[AgentStatusInfo]:
        return self.update_status(agent_id, AgentStatus.ONLINE)
    
    def set_offline(self, agent_id: str) -> Optional[AgentStatusInfo]:
        return self.update_status(agent_id, AgentStatus.OFFLINE)
    
    def on_status_change(self, callback: callable):
        self._status_change_callbacks.append(callback)
    
    def _notify_status_change(self, info: AgentStatusInfo):
        for callback in self._status_change_callbacks:
            try:
                callback(info)
            except Exception as e:
                logger.error(f"Error in status change callback: {e}")
    
    def start_typing(self, agent_id: str, conversation_id: str):
        if conversation_id not in self._typing_agents:
            self._typing_agents[conversation_id] = []
        if agent_id not in self._typing_agents[conversation_id]:
            self._typing_agents[conversation_id].append(agent_id)
    
    def stop_typing(self, agent_id: str, conversation_id: str):
        if conversation_id in self._typing_agents:
            if agent_id in self._typing_agents[conversation_id]:
                self._typing_agents[conversation_id].remove(agent_id)
    
    def get_typing_agents(self, conversation_id: str) -> List[str]:
        return self._typing_agents.get(conversation_id, [])
    
    def is_typing(self, agent_id: str, conversation_id: str) -> bool:
        return agent_id in self._typing_agents.get(conversation_id, [])


def get_agent_status_manager() -> AgentStatusManager:
    return AgentStatusManager.get_instance()
