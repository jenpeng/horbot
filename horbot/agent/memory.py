"""Memory system for persistent agent memory with hierarchical storage."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from horbot.utils.helpers import ensure_dir

if TYPE_CHECKING:
    from horbot.providers.base import LLMProvider
    from horbot.session.manager import Session


class MemoryAccessError(Exception):
    """Exception raised when memory access is denied."""
    pass


class MemoryAccessControl:
    """Controls access to agent memories.
    
    Enforces:
    - Agent can only access its own memory
    - Agent can access team shared memory if it's a member
    - No access to other agents' private memories
    """
    
    def __init__(self, agent_id: Optional[str] = None, team_ids: Optional[list[str]] = None):
        self.agent_id = agent_id
        self.team_ids = team_ids or []
    
    def check_memory_access(
        self,
        target_agent_id: Optional[str] = None,
        target_team_id: Optional[str] = None,
        operation: str = "read",
    ) -> bool:
        """Check if the current agent can access target memory.
        
        Args:
            target_agent_id: Target agent's memory to access
            target_team_id: Target team's shared memory to access
            operation: Operation type (read/write)
            
        Returns:
            True if access is allowed
            
        Raises:
            MemoryAccessError: If access is denied
        """
        if target_agent_id is not None:
            if target_agent_id == self.agent_id:
                return True
            raise MemoryAccessError(
                f"Agent '{self.agent_id}' cannot access memory of agent '{target_agent_id}'"
            )
        
        if target_team_id is not None:
            if target_team_id in self.team_ids:
                return True
            raise MemoryAccessError(
                f"Agent '{self.agent_id}' is not a member of team '{target_team_id}'"
            )
        
        return True
    
    def can_access_agent_memory(self, target_agent_id: str) -> bool:
        """Check if can access another agent's memory."""
        return target_agent_id == self.agent_id
    
    def can_access_team_memory(self, team_id: str) -> bool:
        """Check if can access team's shared memory."""
        return team_id in self.team_ids


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                        "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "Optional fallback full updated long-term memory as markdown. "
                        "Prefer using structured_memory instead.",
                    },
                    "structured_memory": {
                        "type": "object",
                        "description": "Preferred structured long-term memory blocks. Return the full updated state, not only deltas.",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Short overall summary of the current long-term context.",
                            },
                            "facts": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Stable identities, capabilities, durable project truths, and factual background.",
                            },
                            "observations": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Stable observations learned from recent work patterns, but not hard facts.",
                            },
                            "decisions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Decisions already made and currently valid.",
                            },
                            "operating_rules": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Preferred collaboration rules, user preferences, and reusable operating constraints.",
                            },
                            "open_questions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Important unresolved questions or follow-ups.",
                            },
                            "recent_actions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Recent meaningful actions or progress worth preserving for future sessions.",
                            },
                        },
                    },
                    "reflect": {
                        "type": "object",
                        "description": "Optional lightweight reflection generated during consolidation.",
                        "properties": {
                            "stable_observations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "reusable_strategies": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "invalidated_observations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                    "level": {
                        "type": "string",
                        "description": "Memory level: L0 (current session), L1 (recent), L2 (long-term)",
                        "enum": ["L0", "L1", "L2"],
                    },
                },
                "required": ["history_entry"],
            },
        },
    }
]


class MemoryStore:
    """
    Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log).
    
    Now integrated with HierarchicalContextManager for layered storage:
    - L0: Current session memory (active context)
    - L1: Recent memories (related context)
    - L2: Long-term memories (historical context)
    
    Uses the unified paths module for directory locations.
    
    Supports Agent-level memory isolation:
    - Each agent has its own memory directory under agents/{agent_id}/memory/
    - Team shared memory under teams/{team_id}/shared_memory/
    - Default memory for main agent under context/memories/
    """
    
    _cache: dict[str, tuple[str, float]] = {}
    _CACHE_TTL = 60.0
    STRUCTURED_MEMORY_SECTIONS = (
        ("summary", "Summary"),
        ("facts", "Facts"),
        ("observations", "Observations"),
        ("decisions", "Decisions"),
        ("operating_rules", "Operating Rules"),
        ("open_questions", "Open Questions"),
        ("recent_actions", "Recent Actions"),
    )
    STRUCTURED_MEMORY_SECTION_ALIASES = {
        "summary": {"summary", "摘要", "概览", "总结"},
        "facts": {"facts", "fact", "事实", "长期事实", "关键事实"},
        "observations": {"observations", "observation", "观察", "稳定观察", "经验观察"},
        "decisions": {"decisions", "decision", "决策", "已定决策"},
        "operating_rules": {"operating rules", "operating rule", "preferences", "preference", "偏好", "协作规则", "操作规则", "工作规则"},
        "open_questions": {"open questions", "open question", "待解决问题", "开放问题", "未决问题"},
        "recent_actions": {"recent actions", "recent action", "近期动作", "最近动作", "近期进展", "最近进展"},
    }
    LEGACY_SECTION_HINTS = {
        "facts": ("对话参与者", "参与者", "人物", "角色", "用户偏好", "偏好", "背景", "档案"),
        "observations": ("观察", "经验", "模式", "习惯", "洞察"),
        "decisions": ("规划", "方案", "共识", "决策", "目标", "路线", "策略", "设计", "结论"),
        "operating_rules": ("约束", "规则", "风格", "偏好", "约定", "边界", "原则"),
        "open_questions": ("待办", "todo", "问题", "阻塞", "风险", "待解决", "下一步", "follow-up", "follow up"),
        "recent_actions": ("异常", "记录", "进展", "修复", "更新", "日志", "行动", "测试", "状态"),
    }
    REFLECTION_SECTIONS = (
        ("stable_observations", "Stable Observations"),
        ("reusable_strategies", "Reusable Strategies"),
        ("invalidated_observations", "Invalidated Observations"),
    )
    TEAM_MEMORY_SCOPES = (
        ("team_decisions", "Team Decisions"),
        ("shared_constraints", "Shared Constraints"),
        ("active_handoff", "Active Handoff"),
        ("unresolved_blockers", "Unresolved Blockers"),
    )
    TEAM_SCOPE_REASON_LABELS = {
        "team_decisions": "团队决策",
        "shared_constraints": "共享约束",
        "active_handoff": "交接上下文",
        "unresolved_blockers": "未决阻塞",
    }

    def __init__(
        self,
        workspace: Path | None = None,
        agent_id: str | None = None,
        team_ids: list[str] | None = None,
    ):
        from horbot.config.loader import get_cached_config
        from horbot.utils.paths import get_agent_memory_dir, get_team_shared_memory_dir
        
        self.agent_id = agent_id
        self.team_ids = team_ids or []
        self._access_control = MemoryAccessControl(agent_id, team_ids)
        
        if agent_id:
            self.memory_dir = get_agent_memory_dir(agent_id)
            logger.debug("MemoryStore initialized for agent: {}", agent_id)
        else:
            default_agent_id = next(iter(get_cached_config().agents.instances.keys()), "default")
            self.memory_dir = get_agent_memory_dir(default_agent_id)
        
        self.memory_file = self.memory_dir / "L2" / "MEMORY.md"
        self.history_file = self.memory_dir / "L1" / "HISTORY.md"
        self.reflection_file = self.memory_dir / "L1" / "REFLECTION.md"
        self.working_memory_file = self.memory_dir / "working_memory.json"
        self.metrics_file = self.memory_dir / "metrics.json"
        self._cache_key = str(self.memory_file.resolve())
        self._last_recall_metrics: dict[str, Any] = {}
        
        ensure_dir(self.memory_dir / "L0")
        ensure_dir(self.memory_dir / "L1")
        ensure_dir(self.memory_dir / "L2")
        
        self._hierarchical_enabled = True
        self._context_manager = None
        self._init_hierarchical_context(workspace)

    @staticmethod
    def _default_metrics() -> dict[str, Any]:
        return {
            "recall": {
                "count": 0,
                "avg_latency_ms": 0.0,
                "max_latency_ms": 0.0,
                "avg_candidates_count": 0.0,
                "last_selected_memory_ids": [],
                "last_samples": [],
                "last_recorded_at": None,
            },
            "consolidation": {
                "count": 0,
                "success_count": 0,
                "failure_count": 0,
                "avg_latency_ms": 0.0,
                "max_latency_ms": 0.0,
                "last_latency_ms": 0.0,
                "last_status": None,
                "last_samples": [],
                "last_recorded_at": None,
            },
            "growth": {
                "current_entries": 0,
                "current_size_bytes": 0,
                "history": [],
                "last_delta_entries": 0,
                "last_delta_bytes": 0,
                "last_recorded_at": None,
            },
        }

    def _read_metrics(self) -> dict[str, Any]:
        if not self.metrics_file.exists():
            return self._default_metrics()
        try:
            raw = self.metrics_file.read_text(encoding="utf-8")
            parsed = json.loads(raw) if raw else {}
            defaults = self._default_metrics()
            for key, default_value in defaults.items():
                current = parsed.get(key)
                if not isinstance(current, dict):
                    parsed[key] = default_value
                    continue
                merged = dict(default_value)
                merged.update(current)
                parsed[key] = merged
            return parsed
        except Exception as exc:
            logger.warning("Failed to read memory metrics: {}", exc)
            return self._default_metrics()

    def _write_metrics(self, metrics: dict[str, Any]) -> None:
        self.metrics_file.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _cap_samples(samples: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
        return samples[-limit:]

    @staticmethod
    def _update_average(previous_avg: float, previous_count: int, new_value: float) -> float:
        if previous_count <= 0:
            return round(new_value, 3)
        return round(((previous_avg * previous_count) + new_value) / (previous_count + 1), 3)

    def _capture_growth_snapshot(self, metrics: dict[str, Any]) -> None:
        growth = metrics.setdefault("growth", {})
        tracked_files = [self.memory_file, self.history_file, self.reflection_file]
        current_entries = 0
        current_size_bytes = 0
        for path in tracked_files:
            if path.exists():
                current_entries += 1
                current_size_bytes += path.stat().st_size

        previous_entries = int(growth.get("current_entries", 0) or 0)
        previous_size = int(growth.get("current_size_bytes", 0) or 0)
        timestamp = datetime.now().isoformat()
        history = list(growth.get("history", []) or [])
        history.append({
            "timestamp": timestamp,
            "entries": current_entries,
            "size_bytes": current_size_bytes,
        })
        growth.update({
            "current_entries": current_entries,
            "current_size_bytes": current_size_bytes,
            "history": history[-30:],
            "last_delta_entries": current_entries - previous_entries,
            "last_delta_bytes": current_size_bytes - previous_size,
            "last_recorded_at": timestamp,
        })

    def record_recall_metrics(
        self,
        *,
        latency_ms: float,
        candidates_count: int,
        selected_items: list[dict[str, Any]] | None = None,
        query: str | None = None,
    ) -> None:
        metrics = self._read_metrics()
        recall = metrics.setdefault("recall", {})
        previous_count = int(recall.get("count", 0) or 0)
        timestamp = datetime.now().isoformat()
        selected_memory_ids: list[str] = []
        for item in selected_items or []:
            path = str(item.get("path") or item.get("file") or "").strip()
            if not path:
                continue
            selected_memory_ids.append(f"{path}#{item.get('section_index', 0)}")

        samples = list(recall.get("last_samples", []) or [])
        latest_sample = {
            "timestamp": timestamp,
            "latency_ms": round(latency_ms, 3),
            "candidates_count": int(candidates_count),
            "selected_count": len(selected_memory_ids),
            "query": (query or "")[:160],
            "selected_memory_ids": selected_memory_ids[:8],
        }
        samples.append(latest_sample)
        recall.update({
            "count": previous_count + 1,
            "avg_latency_ms": self._update_average(float(recall.get("avg_latency_ms", 0.0) or 0.0), previous_count, latency_ms),
            "max_latency_ms": round(max(float(recall.get("max_latency_ms", 0.0) or 0.0), latency_ms), 3),
            "avg_candidates_count": self._update_average(float(recall.get("avg_candidates_count", 0.0) or 0.0), previous_count, float(candidates_count)),
            "last_selected_memory_ids": selected_memory_ids[:8],
            "last_samples": self._cap_samples(samples),
            "last_recorded_at": timestamp,
        })
        self._last_recall_metrics = dict(latest_sample)
        self._capture_growth_snapshot(metrics)
        self._write_metrics(metrics)

    def get_last_recall_metrics(self) -> dict[str, Any]:
        if self._last_recall_metrics:
            return dict(self._last_recall_metrics)
        metrics = self._read_metrics()
        samples = list(metrics.get("recall", {}).get("last_samples", []) or [])
        return dict(samples[-1]) if samples else {}

    def record_consolidation_metrics(
        self,
        *,
        latency_ms: float,
        success: bool,
        session_key: str | None = None,
        messages_processed: int = 0,
    ) -> None:
        metrics = self._read_metrics()
        consolidation = metrics.setdefault("consolidation", {})
        previous_count = int(consolidation.get("count", 0) or 0)
        timestamp = datetime.now().isoformat()
        samples = list(consolidation.get("last_samples", []) or [])
        samples.append({
            "timestamp": timestamp,
            "latency_ms": round(latency_ms, 3),
            "success": bool(success),
            "session_key": (session_key or "")[:120],
            "messages_processed": int(messages_processed),
        })
        consolidation.update({
            "count": previous_count + 1,
            "success_count": int(consolidation.get("success_count", 0) or 0) + (1 if success else 0),
            "failure_count": int(consolidation.get("failure_count", 0) or 0) + (0 if success else 1),
            "avg_latency_ms": self._update_average(float(consolidation.get("avg_latency_ms", 0.0) or 0.0), previous_count, latency_ms),
            "max_latency_ms": round(max(float(consolidation.get("max_latency_ms", 0.0) or 0.0), latency_ms), 3),
            "last_latency_ms": round(latency_ms, 3),
            "last_status": "success" if success else "failure",
            "last_samples": self._cap_samples(samples),
            "last_recorded_at": timestamp,
        })
        self._capture_growth_snapshot(metrics)
        self._write_metrics(metrics)

    def get_metrics_summary(self) -> dict[str, Any]:
        metrics = self._read_metrics()
        self._capture_growth_snapshot(metrics)
        self._write_metrics(metrics)
        return metrics
    
    def get_team_memory_dir(self, team_id: str) -> Path:
        """Get memory directory for a team (requires team membership)."""
        self._access_control.check_memory_access(target_team_id=team_id)
        from horbot.utils.paths import get_team_shared_memory_dir
        return get_team_shared_memory_dir(team_id)
    
    def check_memory_access(
        self,
        target_agent_id: str | None = None,
        target_team_id: str | None = None,
    ) -> bool:
        """Check if current agent can access target memory."""
        return self._access_control.check_memory_access(
            target_agent_id=target_agent_id,
            target_team_id=target_team_id,
        )
    
    def _init_hierarchical_context(self, workspace: Path) -> None:
        """Initialize hierarchical context manager."""
        try:
            from horbot.agent.context_manager import HierarchicalContextManager
            self._context_manager = HierarchicalContextManager(
                workspace,
                agent_id=self.agent_id,
                team_ids=self.team_ids,
            )
            logger.debug("MemoryStore initialized with hierarchical context support for agent: {}", self.agent_id)
        except Exception as e:
            logger.warning("Failed to initialize hierarchical context: {}", e)
            self._hierarchical_enabled = False

    def read_long_term(self, use_cache: bool = True) -> str:
        if not self.memory_file.exists():
            return ""
        
        if use_cache:
            cached = self._cache.get(self._cache_key)
            if cached:
                content, mtime = cached
                current_mtime = self.memory_file.stat().st_mtime
                if current_mtime == mtime:
                    return content
        
        content = self.memory_file.read_text(encoding="utf-8")
        
        if use_cache:
            self._cache[self._cache_key] = (content, self.memory_file.stat().st_mtime)
        
        return content

    def write_long_term(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")
        self._cache[self._cache_key] = (content, self.memory_file.stat().st_mtime)
        
        if self._hierarchical_enabled and self._context_manager:
            self._context_manager.add_memory(
                content=content,
                level="L2",
                metadata={"source": "long_term_memory", "type": "consolidated"},
            )

    def append_history(self, entry: str) -> None:
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")
        
        if self._hierarchical_enabled and self._context_manager:
            self._context_manager.add_memory(
                content=entry,
                level="L1",
                metadata={"source": "history", "type": "session_log"},
            )

    def get_memory_context(self, use_cache: bool = True) -> str:
        long_term = self.normalize_long_term_memory(use_cache=use_cache)
        reflection = self.build_reflection_context(max_chars=420, use_cache=use_cache)
        parts: list[str] = []
        if long_term:
            parts.append(f"## Long-term Memory\n{long_term}")
        if reflection:
            parts.append(f"## Reflection\n{reflection}")
        return "\n\n".join(parts)

    @staticmethod
    def _normalize_memory_items(value: Any) -> list[str]:
        """Normalize memory block items into a clean string list."""
        if value is None:
            return []
        if isinstance(value, str):
            parts = [
                line.strip().lstrip("-").strip()
                for line in value.splitlines()
                if line.strip()
            ]
            return [part for part in parts if part]
        if isinstance(value, list):
            items: list[str] = []
            for item in value:
                if item is None:
                    continue
                text = str(item).strip().lstrip("-").strip()
                if text:
                    items.append(text)
            return items
        text = str(value).strip()
        return [text] if text else []

    @classmethod
    def _render_structured_memory(cls, structured_memory: dict[str, Any]) -> str:
        """Render structured memory blocks into stable markdown."""
        sections: list[str] = ["# Long-term Memory"]

        summary = str(structured_memory.get("summary", "") or "").strip()
        if summary:
            sections.append(f"## Summary\n{summary}")

        for key, title in cls.STRUCTURED_MEMORY_SECTIONS[1:]:
            items = cls._normalize_memory_items(structured_memory.get(key))
            if not items:
                continue
            bullet_lines = "\n".join(f"- {item}" for item in items)
            sections.append(f"## {title}\n{bullet_lines}")

        return "\n\n".join(sections).strip()

    @classmethod
    def _normalize_section_name(cls, heading: str) -> str | None:
        normalized = re.sub(r"\s+", " ", heading.strip().lower())
        for key, aliases in cls.STRUCTURED_MEMORY_SECTION_ALIASES.items():
            if normalized in aliases:
                return key
        return None

    @classmethod
    def _parse_structured_long_term(cls, content: str) -> dict[str, str]:
        """Parse structured long-term memory markdown sections."""
        matches = list(re.finditer(r"^##\s+(.+?)\s*$", content, flags=re.MULTILINE))
        if not matches:
            return {}

        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            heading = match.group(1).strip()
            canonical = cls._normalize_section_name(heading)
            if canonical is None:
                continue
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            body = content[start:end].strip()
            if body:
                sections[canonical] = body
        return sections

    @classmethod
    def _render_reflection(cls, reflect: dict[str, Any]) -> str:
        sections: list[str] = ["# Reflection"]
        for key, title in cls.REFLECTION_SECTIONS:
            items = cls._normalize_memory_items(reflect.get(key))
            if not items:
                continue
            bullet_lines = "\n".join(f"- {item}" for item in items)
            sections.append(f"## {title}\n{bullet_lines}")
        return "\n\n".join(sections).strip()

    @classmethod
    def _parse_reflection(cls, content: str) -> dict[str, str]:
        matches = list(re.finditer(r"^##\s+(.+?)\s*$", content, flags=re.MULTILINE))
        if not matches:
            return {}
        alias_map = {
            "stable observations": "stable_observations",
            "reusable strategies": "reusable_strategies",
            "invalidated observations": "invalidated_observations",
        }
        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            heading = alias_map.get(match.group(1).strip().lower())
            if not heading:
                continue
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            body = content[start:end].strip()
            if body:
                sections[heading] = body
        return sections

    def read_reflection(self, use_cache: bool = True) -> str:
        if not self.reflection_file.exists():
            return ""
        return self.reflection_file.read_text(encoding="utf-8")

    def write_reflection(self, content: str) -> None:
        self.reflection_file.write_text(content, encoding="utf-8")

    def build_reflection_context(
        self,
        query: str | None = None,
        *,
        max_chars: int = 420,
        use_cache: bool = True,
    ) -> str:
        reflection = self.read_reflection(use_cache=use_cache)
        if not reflection:
            return ""
        sections = self._parse_reflection(reflection)
        if not sections:
            return self._truncate_text(reflection, max_chars)

        trace_items = self.build_reflection_trace(
            query=query,
            max_items=6,
            use_cache=use_cache,
        )
        selected_by_section: dict[str, list[str]] = {}
        for item in trace_items:
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            if not title or not snippet:
                continue
            selected_by_section.setdefault(title, []).append(snippet)

        parts: list[str] = []
        remaining = max_chars
        for key, title in self.REFLECTION_SECTIONS:
            body = sections.get(key)
            if not body or remaining <= 80:
                continue
            selected_items = selected_by_section.get(title, [])
            if not selected_items:
                continue
            rendered_body = "\n".join(f"- {item}" for item in selected_items)
            block = f"## {title}\n{rendered_body}"
            if len(block) > remaining:
                block = f"## {title}\n{self._truncate_markdown_lines(rendered_body, max(60, remaining - len(title) - 6))}"
            parts.append(block)
            remaining -= len(block)
        return "\n\n".join(parts).strip()

    def build_reflection_trace(
        self,
        query: str | None = None,
        *,
        max_items: int = 5,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        reflection = self.read_reflection(use_cache=use_cache)
        if not reflection:
            return []
        sections = self._parse_reflection(reflection)
        if not sections:
            compact = self._truncate_text(reflection, 180)
            return [{
                "category": "reflection",
                "level": "Reflect",
                "file": self.reflection_file.name,
                "path": str(self.reflection_file),
                "title": "Reflection",
                "snippet": compact,
                "relevance": 0.2,
                "reasons": ["反思归纳"],
                "matched_terms": [],
                "section_index": 0,
            }] if compact else []

        query_terms = self._extract_query_terms(query)
        trace_items: list[dict[str, Any]] = []
        global_index = 0

        for key, title in self.REFLECTION_SECTIONS:
            body = sections.get(key)
            if not body:
                continue
            items = self._normalize_memory_items(body)
            if not items:
                continue

            matched_items: list[tuple[str, list[str]]] = []
            fallback_items: list[tuple[str, list[str]]] = []
            for item in items:
                normalized = item.lower()
                matched_terms = [term for term in query_terms if term in normalized]
                if matched_terms:
                    matched_items.append((item, matched_terms))
                else:
                    fallback_items.append((item, []))

            if query_terms:
                selected_entries = matched_items
                if not selected_entries and key == "reusable_strategies":
                    selected_entries = fallback_items[:2]
            else:
                selected_entries = fallback_items[:2]

            for item_text, matched_terms in selected_entries[:2]:
                reasons: list[str] = []
                if matched_terms:
                    reasons.append("关键词命中")
                if key == "stable_observations":
                    reasons.append("稳定观察")
                elif key == "reusable_strategies":
                    reasons.append("可复用策略")
                elif key == "invalidated_observations":
                    reasons.append("失效经验校正")

                relevance = 0.45
                if key == "reusable_strategies":
                    relevance += 0.1
                elif key == "stable_observations":
                    relevance += 0.05
                relevance += min(len(matched_terms) * 0.12, 0.36)

                trace_items.append({
                    "category": "reflection",
                    "level": "Reflect",
                    "file": self.reflection_file.name,
                    "path": str(self.reflection_file),
                    "title": title,
                    "snippet": self._truncate_text(item_text, 180),
                    "relevance": round(relevance, 3),
                    "reasons": reasons,
                    "matched_terms": matched_terms[:6],
                    "section_index": global_index,
                })
                global_index += 1

        trace_items.sort(
            key=lambda item: (
                -float(item.get("relevance", 0.0) or 0.0),
                int(item.get("section_index", 0) or 0),
            )
        )
        return trace_items[:max_items]

    @staticmethod
    def _parse_generic_markdown_sections(content: str) -> list[tuple[str, str]]:
        """Parse generic markdown H2 sections for legacy memory files."""
        matches = list(re.finditer(r"^##\s+(.+?)\s*$", content, flags=re.MULTILINE))
        if not matches:
            compact = content.strip()
            return [("Long-term Memory", compact)] if compact else []

        sections: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            heading = match.group(1).strip()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            body = content[start:end].strip()
            if body:
                sections.append((heading, body))
        return sections

    @staticmethod
    def _extract_query_terms(query: str | None) -> list[str]:
        """Extract normalized lexical terms for long-term memory matching."""
        if not query:
            return []

        seen: set[str] = set()
        terms: list[str] = []
        for token in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{2,}", query.lower()):
            if token not in seen:
                seen.add(token)
                terms.append(token)
        return terms

    @staticmethod
    def _truncate_text(text: str, max_chars: int) -> str:
        """Truncate text while keeping it readable."""
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_chars:
            return compact
        return compact[:max_chars].rstrip() + "..."

    @staticmethod
    def _truncate_markdown_lines(text: str, max_chars: int) -> str:
        """Truncate markdown-ish text while preserving line structure."""
        if max_chars <= 0:
            return ""

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return ""

        output: list[str] = []
        used = 0
        for line in lines:
            compact = re.sub(r"\s+", " ", line).strip()
            candidate_len = len(compact) if not output else len(compact) + 1
            if used + candidate_len <= max_chars:
                output.append(compact)
                used += candidate_len
                continue

            remaining = max_chars - used
            if remaining > 12:
                slice_len = max(8, remaining - (0 if not output else 1) - 3)
                output.append(compact[:slice_len].rstrip() + "...")
            break

        return "\n".join(output)

    @staticmethod
    def _clean_markdown_inline(text: str) -> str:
        """Flatten inline markdown markers for compact memory items."""
        cleaned = text.strip()
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = cleaned.replace("|------|", "|")
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def _dedupe_memory_items(cls, items: list[str]) -> list[str]:
        """Deduplicate memory items while preserving order."""
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = re.sub(r"[\W_]+", "", cls._clean_markdown_inline(item).lower())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(item.strip())
        return deduped

    def build_long_term_context(
        self,
        query: str | None = None,
        *,
        max_chars: int = 900,
        use_cache: bool = True,
    ) -> str:
        """Build a compact long-term memory context, preferring structured sections."""
        long_term = self.normalize_long_term_memory(use_cache=use_cache)
        if not long_term:
            return ""

        sections = self._parse_structured_long_term(long_term)
        if not sections:
            generic_sections = self._parse_generic_markdown_sections(long_term)
            if not generic_sections:
                return self._truncate_text(long_term, max_chars)

            query_terms = self._extract_query_terms(query)
            selected_sections: list[tuple[str, str]] = []
            for heading, body in generic_sections:
                haystack = f"{heading}\n{body}".lower()
                if not query_terms or any(term in haystack for term in query_terms):
                    selected_sections.append((heading, body))

            if not selected_sections:
                selected_sections = generic_sections[:2]

            parts: list[str] = []
            remaining = max_chars
            for heading, body in selected_sections[:3]:
                if remaining <= 80:
                    break
                block_body = self._truncate_markdown_lines(body, max(80, remaining - len(heading) - 6))
                block = f"## {heading}\n{block_body}"
                parts.append(block)
                remaining -= len(block)

            return "\n\n".join(parts).strip() if parts else self._truncate_text(long_term, max_chars)

        query_terms = self._extract_query_terms(query)
        parts: list[str] = []
        remaining = max_chars

        summary = sections.get("summary")
        if summary:
            summary_block = f"## Summary\n{self._truncate_markdown_lines(summary, min(220, remaining))}"
            parts.append(summary_block)
            remaining -= len(summary_block)

        for key, title in self.STRUCTURED_MEMORY_SECTIONS[1:]:
            body = sections.get(key)
            if not body or remaining <= 80:
                continue

            items = self._normalize_memory_items(body)
            if query_terms:
                selected_items = [
                    item for item in items
                    if any(term in item.lower() for term in query_terms)
                ]
                if not selected_items and key == "open_questions":
                    selected_items = items[:2]
            else:
                default_limits = {
                    "facts": 4,
                    "observations": 3,
                    "decisions": 3,
                    "operating_rules": 3,
                    "open_questions": 3,
                    "recent_actions": 3,
                }
                selected_items = items[:default_limits.get(key, 3)]

            if not selected_items:
                continue

            rendered_body = "\n".join(f"- {item}" for item in selected_items)
            block = f"## {title}\n{rendered_body}"
            if len(block) > remaining:
                block = f"## {title}\n{self._truncate_markdown_lines(rendered_body, max(60, remaining - len(title) - 6))}"

            parts.append(block)
            remaining -= len(block)

        if not parts:
            return self._truncate_text(long_term, max_chars)

        return "\n\n".join(parts).strip()

    @classmethod
    def _classify_legacy_section(cls, heading: str, body: str) -> str:
        normalized_heading = heading.lower()
        normalized_body = body.lower()
        for key, hints in cls.LEGACY_SECTION_HINTS.items():
            if any(hint in normalized_heading for hint in hints):
                return key
        if any(marker in normalized_body for marker in ("待确认", "待补充", "未解决", "待跟进")):
            return "open_questions"
        return "recent_actions"

    @classmethod
    def _extract_legacy_section_items(cls, heading: str, body: str, category: str) -> list[str]:
        """Turn a legacy markdown section into structured memory bullets."""
        lines = body.splitlines()
        blocks: list[list[str]] = []
        current: list[str] = []

        for raw_line in lines:
            line = raw_line.rstrip()
            if not line.strip():
                if current:
                    blocks.append(current)
                    current = []
                continue
            if re.fullmatch(r"\s*\|?[-:\s|]+\|?\s*", line):
                continue
            current.append(line)
        if current:
            blocks.append(current)

        items: list[str] = []
        for block in blocks:
            stripped = [line.strip() for line in block if line.strip()]
            if not stripped:
                continue

            if all(re.match(r"^[-*]\s+", line) for line in stripped):
                block_items = [cls._clean_markdown_inline(re.sub(r"^[-*]\s+", "", line)) for line in stripped]
            elif all(line.startswith(">") for line in stripped):
                joined = " ".join(cls._clean_markdown_inline(re.sub(r"^>\s*", "", line)) for line in stripped)
                block_items = [joined]
            elif all(line.startswith("|") for line in stripped):
                table_rows = [cls._clean_markdown_inline(line) for line in stripped]
                block_items = [" ".join(table_rows)]
            else:
                joined = " ".join(
                    cls._clean_markdown_inline(re.sub(r"^(?:[-*]\s+|>\s*)", "", line))
                    for line in stripped
                )
                block_items = [joined]

            for item in block_items:
                item = item.strip()
                if not item:
                    continue
                if category != "facts":
                    item = f"[{heading}] {item}"
                items.append(item)

        return cls._dedupe_memory_items(items)

    @classmethod
    def _build_legacy_summary(cls, sections: list[tuple[str, str]]) -> str:
        """Create a compact summary from legacy sections when none exists."""
        fragments: list[str] = []
        for heading, body in sections:
            category = cls._classify_legacy_section(heading, body)
            if category == "facts":
                continue

            items = cls._extract_legacy_section_items(heading, body, category)
            if not items:
                continue

            preview = items[0]
            if preview.startswith(f"[{heading}] "):
                preview = preview[len(heading) + 3 :]
            preview = cls._truncate_text(preview, 120)
            if preview:
                fragments.append(f"{heading}: {preview}")
            if len(fragments) >= 2:
                break

        summary = "；".join(fragments)
        return cls._truncate_text(summary, 260) if summary else ""

    @classmethod
    def _normalize_legacy_long_term(cls, content: str) -> str:
        """Normalize legacy long-term memory markdown into the structured format."""
        sections = cls._parse_generic_markdown_sections(content)
        if not sections:
            return content.strip()

        structured: dict[str, Any] = {"summary": cls._build_legacy_summary(sections)}
        for key, _title in cls.STRUCTURED_MEMORY_SECTIONS[1:]:
            structured[key] = []

        for heading, body in sections:
            canonical = cls._normalize_section_name(heading)
            if canonical == "summary":
                structured["summary"] = cls._clean_markdown_inline(
                    cls._truncate_markdown_lines(body, 260).replace("\n", " ")
                )
                continue

            category = canonical or cls._classify_legacy_section(heading, body)
            structured.setdefault(category, [])
            structured[category].extend(cls._extract_legacy_section_items(heading, body, category))

        for key, _title in cls.STRUCTURED_MEMORY_SECTIONS[1:]:
            structured[key] = cls._dedupe_memory_items(structured.get(key, []))

        return cls._render_structured_memory(structured)

    def normalize_long_term_memory(self, use_cache: bool = True, *, persist: bool = False) -> str:
        """Return structured long-term memory, normalizing legacy markdown when needed."""
        long_term = self.read_long_term(use_cache=use_cache)
        if not long_term:
            return ""

        normalized = long_term.strip()
        if not self._parse_structured_long_term(long_term):
            normalized = self._normalize_legacy_long_term(long_term)
            if persist and normalized and normalized != long_term.strip():
                self.write_long_term(normalized)
        return normalized
    
    def clear_cache(self) -> None:
        if self._cache_key in self._cache:
            del self._cache[self._cache_key]
    
    def read_working_memory(self) -> dict[str, Any]:
        """Read working memory (short-term, JSON-based memory)."""
        if not self.working_memory_file.exists():
            return {}
        try:
            content = self.working_memory_file.read_text(encoding="utf-8")
            return json.loads(content) if content else {}
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to read working memory: {}", e)
            return {}
    
    def write_working_memory(self, data: dict[str, Any]) -> None:
        """Write working memory."""
        ensure_dir(self.working_memory_file.parent)
        self.working_memory_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def update_working_memory(self, key: str, value: Any) -> None:
        """Update a specific key in working memory."""
        data = self.read_working_memory()
        data[key] = value
        self.write_working_memory(data)
    
    def get_from_working_memory(self, key: str, default: Any = None) -> Any:
        """Get a specific key from working memory."""
        data = self.read_working_memory()
        return data.get(key, default)
    
    def read_team_memory(self, team_id: str) -> str:
        """Read team's shared long-term memory."""
        self._access_control.check_memory_access(target_team_id=team_id)
        from horbot.team.shared_memory import SharedMemoryManager

        manager = SharedMemoryManager(team_id)
        return manager.get_scoped_context()
    
    def write_team_memory(self, team_id: str, content: str) -> None:
        """Write to team's shared long-term memory."""
        self._access_control.check_memory_access(target_team_id=team_id, operation="write")
        from horbot.utils.paths import get_team_shared_memory_dir
        team_memory_dir = get_team_shared_memory_dir(team_id)
        ensure_dir(team_memory_dir)
        team_memory_file = team_memory_dir / "MEMORY.md"
        team_memory_file.write_text(content, encoding="utf-8")
        logger.info("Updated team {} shared memory", team_id)
    
    def append_team_history(self, team_id: str, entry: str) -> None:
        """Append to team's shared history."""
        self._access_control.check_memory_access(target_team_id=team_id, operation="write")
        from horbot.utils.paths import get_team_shared_memory_dir
        team_memory_dir = get_team_shared_memory_dir(team_id)
        ensure_dir(team_memory_dir)
        team_history_file = team_memory_dir / "HISTORY.md"
        with open(team_history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")
        logger.debug("Appended to team {} history", team_id)
    
    def get_team_context(self, team_id: str) -> str:
        """Get team's shared memory context."""
        team_memory = self.read_team_memory(team_id)
        if team_memory:
            return f"## Team {team_id} Shared Memory\n{team_memory}"
        return ""

    @classmethod
    def infer_team_memory_scopes(cls, query: str | None) -> list[str] | None:
        if not query:
            return ["active_handoff", "unresolved_blockers"]
        normalized = query.lower()
        scopes: list[str] = []
        if any(token in normalized for token in ("决策", "方案", "design", "decision", "plan")):
            scopes.append("team_decisions")
        if any(token in normalized for token in ("约束", "边界", "限制", "规则", "constraint", "permission")):
            scopes.append("shared_constraints")
        if any(token in normalized for token in ("交接", "接力", "handoff", "relay", "下一棒")):
            scopes.append("active_handoff")
        if any(token in normalized for token in ("阻塞", "问题", "失败", "风险", "blocker", "issue", "error")):
            scopes.append("unresolved_blockers")
        return scopes or None

    def get_all_team_contexts(self, query: str | None = None, *, max_chars_per_team: int = 720) -> str:
        """Get all accessible team shared memories using scoped retrieval."""
        from horbot.team.shared_memory import SharedMemoryManager

        contexts = []
        scopes = self.infer_team_memory_scopes(query)
        for team_id in self.team_ids:
            self._access_control.check_memory_access(target_team_id=team_id)
            manager = SharedMemoryManager(team_id)
            scoped = manager.get_scoped_context(
                scopes=scopes,
                query=query,
                max_chars_per_scope=max(160, max_chars_per_team // 2),
            )
            ctx = f"## Team {team_id} Shared Memory\n{scoped}" if scoped else ""
            if ctx:
                contexts.append(ctx)
        return "\n\n---\n\n".join(contexts) if contexts else ""

    def build_team_memory_trace(
        self,
        query: str | None = None,
        *,
        max_items: int = 5,
        max_chars_per_scope: int = 220,
    ) -> list[dict[str, Any]]:
        """Build retrieval trace items for scoped team shared memory."""
        from horbot.team.shared_memory import SharedMemoryManager

        query_terms = self._extract_query_terms(query)
        selected_scopes = self.infer_team_memory_scopes(query)
        trace_items: list[dict[str, Any]] = []
        global_index = 0

        for team_id in self.team_ids:
            self._access_control.check_memory_access(target_team_id=team_id)
            manager = SharedMemoryManager(team_id)
            scopes = selected_scopes or list(manager.SCOPES.keys())
            for scope in scopes:
                if scope not in manager.SCOPES:
                    continue
                content = manager.read_scope(scope)
                if not content.strip():
                    continue

                scope_file, scope_title = manager.SCOPES[scope]
                sections = self._parse_generic_markdown_sections(content)
                candidate_sections: list[tuple[str, str, list[str], float]] = []

                for section_heading, section_body in sections:
                    normalized_body = self._clean_markdown_inline(section_body)
                    if not normalized_body:
                        continue
                    lower_body = normalized_body.lower()
                    matched_terms = [term for term in query_terms if term in lower_body]
                    relevance = 0.48
                    if scope == "active_handoff":
                        relevance += 0.1
                    elif scope == "unresolved_blockers":
                        relevance += 0.08
                    elif scope == "team_decisions":
                        relevance += 0.06
                    relevance += min(len(matched_terms) * 0.12, 0.36)
                    candidate_sections.append((section_heading, normalized_body, matched_terms, relevance))

                if query_terms:
                    selected_sections = [item for item in candidate_sections if item[2]]
                    if not selected_sections and scope in {"active_handoff", "unresolved_blockers"}:
                        selected_sections = candidate_sections[:1]
                else:
                    selected_sections = candidate_sections[:1]

                for section_heading, normalized_body, matched_terms, relevance in selected_sections[:1]:
                    reasons: list[str] = []
                    if matched_terms:
                        reasons.append("关键词命中")
                    reasons.append("团队共享记忆")
                    reasons.append(self.TEAM_SCOPE_REASON_LABELS.get(scope, "团队共享记忆"))
                    title = f"{team_id} / {scope_title}"
                    if section_heading and section_heading != scope_title:
                        title = f"{title} / {section_heading}"
                    trace_items.append({
                        "category": "team",
                        "level": "Team",
                        "file": scope_file,
                        "path": str(manager.get_scope_path(scope)),
                        "title": title,
                        "snippet": self._truncate_text(normalized_body, max_chars_per_scope),
                        "relevance": round(relevance, 3),
                        "reasons": reasons,
                        "matched_terms": matched_terms[:6],
                        "section_index": global_index,
                        "origin": "team_shared",
                        "owner_id": team_id,
                        "scope": scope,
                        "scope_label": scope_title,
                    })
                    global_index += 1

        trace_items.sort(
            key=lambda item: (
                -float(item.get("relevance", 0.0) or 0.0),
                int(item.get("section_index", 0) or 0),
            )
        )
        return trace_items[:max_items]
    
    def add_session_memory(
        self,
        content: str,
        session_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add memory to L0 (current session) layer.
        
        Args:
            content: Memory content
            session_key: Session identifier
            metadata: Optional metadata
        """
        if self._hierarchical_enabled and self._context_manager:
            self._context_manager.add_memory(
                content=content,
                level="L0",
                session_key=session_key,
                metadata=metadata or {},
            )
    
    def get_hierarchical_context(
        self,
        session_key: str,
        levels: list[str] | None = None,
        max_tokens: int = 8000,
    ) -> str:
        """
        Get context from hierarchical memory layers.
        
        Args:
            session_key: Session identifier
            levels: Memory levels to load (default: L0, L1)
            max_tokens: Maximum token budget
            
        Returns:
            Combined context string
        """
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.load_context(
                session_key=session_key,
                levels=levels,
                max_tokens=max_tokens,
            )
        return self.get_memory_context()
    
    def search_memories(
        self,
        query: str,
        levels: list[str] | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search across memory layers.
        
        Args:
            query: Search query
            levels: Levels to search (default: all)
            max_results: Maximum results
            
        Returns:
            List of matching memories
        """
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.search_context(
                query=query,
                levels=levels,
                max_results=max_results,
            )
        results = []
        long_term = self.normalize_long_term_memory()
        if query.lower() in long_term.lower():
            results.append({
                "level": "L2",
                "file": "MEMORY.md",
                "snippet": long_term[:500],
                "relevance": 1.0,
            })
        return results
    
    def clear_session_memory(self, session_key: str) -> None:
        """
        Clear L0 memory for a session.
        
        Args:
            session_key: Session identifier
        """
        if self._hierarchical_enabled and self._context_manager:
            self._context_manager.clear_session_context(session_key)
    
    def promote_to_long_term(self, session_key: str) -> bool:
        """
        Promote L0/L1 memories to L2 (long-term).
        
        Args:
            session_key: Session identifier
            
        Returns:
            Success status
        """
        if not self._hierarchical_enabled or not self._context_manager:
            return False
        
        results = self._context_manager.search_context(
            query="",
            levels=["L0", "L1"],
            max_results=100,
        )
        
        for result in results:
            if session_key in result.get("file", ""):
                file_path = Path(result["path"])
                if file_path.exists():
                    content = file_path.read_text(encoding="utf-8")
                    self._context_manager.add_memory(
                        content=content,
                        level="L2",
                        metadata={"promoted_from": result["level"], "session": session_key},
                    )
        
        return True

    async def consolidate(
        self,
        session: Session,
        provider: LLMProvider,
        model: str,
        *,
        archive_all: bool = False,
        memory_window: int = 50,
    ) -> bool:
        """Consolidate old messages into MEMORY.md + HISTORY.md via LLM tool call.

        Returns True on success (including no-op), False on failure.
        """
        started_at = time.perf_counter()
        success = False
        if archive_all:
            old_messages = session.messages
            keep_count = 0
            logger.info("Memory consolidation (archive_all): {} messages", len(session.messages))
        else:
            keep_count = memory_window // 2
            if len(session.messages) <= keep_count:
                return True
            if len(session.messages) - session.last_consolidated <= 0:
                return True
            old_messages = session.messages[session.last_consolidated:-keep_count]
            if not old_messages:
                return True
            logger.info("Memory consolidation: {} to consolidate, {} keep", len(old_messages), keep_count)

        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")

        current_memory = self.normalize_long_term_memory(use_cache=False)
        
        level_hint = "\n- level: Choose L0 for current session context, L1 for recent memories, L2 for long-term facts" if self._hierarchical_enabled else ""
        
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{chr(10).join(lines)}

## Memory Level Guidelines{level_hint}
- L0: Current session's active context (task progress, immediate decisions)
- L1: Recent session memories (last few days, relevant context)
- L2: Long-term facts (persistent knowledge, important patterns)

## Output Rules
- Prefer filling structured_memory instead of raw memory_update.
- structured_memory must represent the FULL latest long-term state, not just deltas.
- facts: durable truths only.
- observations: stable patterns learned from recent work, but not guaranteed facts.
- decisions: decisions that remain valid now.
- operating_rules: user preferences, collaboration rules, and constraints worth reusing.
- open_questions: unresolved items worth revisiting later.
- recent_actions: recent progress/actions that help future continuity.
- reflect: lightweight reflection with stable_observations, reusable_strategies, invalidated_observations.
- Keep history_entry concrete and grep-friendly."""

        try:
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                model=model,
            )

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory, skipping")
                return False

            args = response.tool_calls[0].arguments
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                logger.warning("Memory consolidation: unexpected arguments type {}", type(args).__name__)
                return False

            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.append_history(entry)
            structured_memory = args.get("structured_memory")
            if isinstance(structured_memory, dict):
                update = self._render_structured_memory(structured_memory)
            else:
                update = args.get("memory_update")
            reflection = args.get("reflect")

            if update:
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.write_long_term(update)
            if isinstance(reflection, dict):
                reflection_content = self._render_reflection(reflection)
                if reflection_content:
                    self.write_reflection(reflection_content)
            
            level = args.get("level", "L1")
            if self._hierarchical_enabled and self._context_manager:
                session_key = getattr(session, 'key', 'unknown')
                if entry:
                    self._context_manager.add_memory(
                        content=entry,
                        level=level,
                        session_key=session_key,
                        metadata={"consolidated": True},
                    )

            session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
            logger.info("Memory consolidation done: {} messages, last_consolidated={}", len(session.messages), session.last_consolidated)
            success = True
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return False
        finally:
            self.record_consolidation_metrics(
                latency_ms=(time.perf_counter() - started_at) * 1000,
                success=success,
                session_key=getattr(session, "key", None),
                messages_processed=len(old_messages) if "old_messages" in locals() else 0,
            )
    
    def add_execution_memory(
        self,
        execution_log: dict[str, Any],
        session_key: str,
    ) -> None:
        """
        Add execution history as memory.
        
        Args:
            execution_log: Execution log dictionary
            session_key: Session identifier
        """
        if self._hierarchical_enabled and self._context_manager:
            self._context_manager.add_execution(execution_log, session_key)
            
            key_info = self._context_manager.extract_key_info_as_memory(execution_log)
            if key_info:
                execution_metadata = {
                    key: value
                    for key, value in execution_log.items()
                    if (key.startswith("source_") or key.startswith("outbound_"))
                    and not isinstance(value, (list, dict))
                }
                self._context_manager.add_memory(
                    content=key_info,
                    level="L1",
                    session_key=session_key,
                    metadata={
                        "source": "execution",
                        "type": "extracted",
                        **execution_metadata,
                    },
                )
    
    def get_execution_history(
        self,
        session_key: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get execution history.
        
        Args:
            session_key: Optional session filter
            limit: Maximum results
            
        Returns:
            List of execution logs
        """
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.get_execution_history(session_key, limit)
        return []
    
    def get_memory_stats(self) -> dict[str, Any]:
        """
        Get memory statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "agent_id": self.agent_id,
            "team_ids": self.team_ids,
            "memory_dir": str(self.memory_dir),
            "traditional": {
                "long_term_exists": self.memory_file.exists(),
                "history_exists": self.history_file.exists(),
                "working_memory_exists": self.working_memory_file.exists(),
            },
            "hierarchical": None,
            "teams": {},
            "metrics": self.get_metrics_summary(),
        }
        
        if self._hierarchical_enabled and self._context_manager:
            stats["hierarchical"] = self._context_manager.get_context_stats()
        
        for team_id in self.team_ids:
            try:
                team_memory = self.read_team_memory(team_id)
                stats["teams"][team_id] = {
                    "has_shared_memory": bool(team_memory),
                    "accessible": True,
                }
            except MemoryAccessError:
                stats["teams"][team_id] = {
                    "has_shared_memory": False,
                    "accessible": False,
                }
        
        return stats
    
    # ============== Resources Access ==============
    
    def add_resource(
        self,
        content: str,
        resource_type: str = "file",
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path | None:
        """
        添加资源。
        
        Args:
            content: 资源内容
            resource_type: 资源类型 (file/code/external)
            name: 资源名称
            metadata: 元数据
            
        Returns:
            保存的文件路径
        """
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.add_resource(content, resource_type, name, metadata)
        return None
    
    def get_resource(self, name: str, resource_type: str | None = None) -> dict[str, Any] | None:
        """获取资源。"""
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.get_resource(name, resource_type)
        return None
    
    def search_resources(
        self,
        query: str,
        resource_type: str | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """搜索资源。"""
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.search_resources(query, resource_type, max_results)
        return []
    
    def list_resources(self, resource_type: str | None = None) -> list[dict[str, Any]]:
        """列出资源。"""
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.list_resources(resource_type)
        return []
    
    # ============== Skills Access ==============
    
    def link_skill(
        self,
        skill_name: str,
        skill_path: Path | None = None,
        description: str | None = None,
    ) -> Path | None:
        """
        链接技能到活跃列表。
        
        Args:
            skill_name: 技能名称
            skill_path: 技能文件路径
            description: 技能描述
            
        Returns:
            创建的链接文件路径
        """
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.link_skill(skill_name, skill_path, description)
        return None
    
    def unlink_skill(self, skill_name: str) -> bool:
        """取消链接技能。"""
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.unlink_skill(skill_name)
        return False
    
    def get_active_skills(self) -> list[dict[str, Any]]:
        """获取活跃技能列表。"""
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.get_active_skills()
        return []
    
    def archive_skill(self, skill_name: str) -> bool:
        """归档技能。"""
        if self._hierarchical_enabled and self._context_manager:
            return self._context_manager.archive_skill(skill_name)
        return False
