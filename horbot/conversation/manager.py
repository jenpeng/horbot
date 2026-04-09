"""Conversation management for internal chat sessions.

This module manages conversations between users and agents within Workhorse.
It is separate from the external channels (飞书, 钉钉, Slack, etc.) integration.

Key concepts:
- Conversation: A chat session between user and agent(s)
- DM (Direct Message): Private chat between user and single agent
- Team Chat: Group chat between user and multiple team agents
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

from loguru import logger


class ConversationType(Enum):
    DM = "dm"
    TEAM = "team"


@dataclass
class Conversation:
    id: str
    type: ConversationType
    target_id: str
    name: str
    description: Optional[str] = None
    agent_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def session_key(self) -> str:
        return f"web:{self.id}"
    
    @classmethod
    def create_dm(cls, agent_id: str, agent_name: str) -> "Conversation":
        conv_id = f"dm_{agent_id}"
        return cls(
            id=conv_id,
            type=ConversationType.DM,
            target_id=agent_id,
            name=agent_name,
            agent_ids=[agent_id],
        )
    
    @classmethod
    def create_team(
        cls,
        team_id: str,
        team_name: str,
        member_ids: List[str],
        description: Optional[str] = None,
    ) -> "Conversation":
        conv_id = f"team_{team_id}"
        return cls(
            id=conv_id,
            type=ConversationType.TEAM,
            target_id=team_id,
            name=team_name,
            description=description,
            agent_ids=member_ids,
        )
    
    def to_session_key(self, prefix: str = "web") -> str:
        return f"{prefix}:{self.id}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "target_id": self.target_id,
            "name": self.name,
            "description": self.description,
            "agent_ids": self.agent_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class ConversationManager:
    _instance: Optional["ConversationManager"] = None
    
    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}
    
    @classmethod
    def get_instance(cls) -> "ConversationManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_or_create_dm(
        self,
        agent_id: str,
        agent_name: str,
    ) -> Conversation:
        conv_id = f"dm_{agent_id}"
        if conv_id not in self._conversations:
            self._conversations[conv_id] = Conversation.create_dm(
                agent_id=agent_id,
                agent_name=agent_name,
            )
        return self._conversations[conv_id]
    
    def get_or_create_team(
        self,
        team_id: str,
        team_name: str,
        member_ids: List[str],
        description: Optional[str] = None,
    ) -> Conversation:
        conv_id = f"team_{team_id}"
        if conv_id not in self._conversations:
            self._conversations[conv_id] = Conversation.create_team(
                team_id=team_id,
                team_name=team_name,
                member_ids=member_ids,
                description=description,
            )
        return self._conversations[conv_id]
    
    def get(self, conv_id: str) -> Optional[Conversation]:
        return self._conversations.get(conv_id)
    
    def get_all(self) -> List[Conversation]:
        return list(self._conversations.values())
    
    def get_dm_list(self) -> List[Conversation]:
        return [
            conv for conv in self._conversations.values()
            if conv.type == ConversationType.DM
        ]
    
    def get_team_list(self) -> List[Conversation]:
        return [
            conv for conv in self._conversations.values()
            if conv.type == ConversationType.TEAM
        ]
    
    def parse_id(self, conv_id: str) -> tuple[ConversationType, str]:
        if conv_id.startswith("dm_"):
            return ConversationType.DM, conv_id[3:]
        elif conv_id.startswith("team_"):
            return ConversationType.TEAM, conv_id[5:]
        else:
            raise ValueError(f"Invalid conversation ID format: {conv_id}")
    
    def session_key_to_id(self, session_key: str) -> str:
        if session_key.startswith("web:"):
            return session_key[4:]
        return session_key


def get_conversation_manager() -> ConversationManager:
    return ConversationManager.get_instance()
