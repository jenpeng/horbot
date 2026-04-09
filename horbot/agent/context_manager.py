"""Hierarchical context manager for layered context loading."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from horbot.utils.helpers import ensure_dir


class HierarchicalContextManager:
    """分层上下文管理器，支持L0/L1/L2三层上下文加载。"""
    
    CONTEXT_DIR_NAME = "context"
    MEMORIES_DIR = "memories"
    RESOURCES_DIR = "resources"
    SKILLS_DIR = "skills"
    EXECUTIONS_DIR = "executions"
    
    L0_DIR = "L0"
    L1_DIR = "L1"
    L2_DIR = "L2"
    
    FILES_DIR = "files"
    CODE_DIR = "code"
    EXTERNAL_DIR = "external"
    
    ACTIVE_DIR = "active"
    ARCHIVED_DIR = "archived"
    
    RECENT_DIR = "recent"
    
    TOKEN_BUDGET_L0 = 0.60
    TOKEN_BUDGET_L1 = 0.30
    TOKEN_BUDGET_L2 = 0.10
    
    MAX_EXECUTIONS_RECENT = 50
    MAX_EXECUTIONS_ARCHIVED_DAYS = 30
    MEMORY_SEPARATOR_PATTERN = re.compile(r"\n\s*---\s*\n")
    MEMORY_HEADER_PATTERN = re.compile(r"^<!--\s*([^:>]+):\s*(.*?)\s*-->$")
    SEARCH_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9_]{2,}")
    TEMPORAL_TOKEN_PATTERN = re.compile(r"\b\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?\b")
    
    def __init__(
        self,
        workspace: Path,
        agent_id: str | None = None,
        team_ids: list[str] | None = None,
    ):
        self.workspace = workspace
        self.agent_id = agent_id
        self.team_ids = team_ids or []
        
        from horbot.config.loader import get_cached_config
        from horbot.utils.paths import get_agent_memory_dir, get_team_shared_memory_dir
        
        if agent_id:
            self.context_dir = get_agent_memory_dir(agent_id)
            logger.debug("HierarchicalContextManager initialized for agent: {}", agent_id)
        else:
            default_agent_id = next(iter(get_cached_config().agents.instances.keys()), "default")
            self.context_dir = get_agent_memory_dir(default_agent_id)
        
        self._team_context_dirs: dict[str, Path] = {}
        for team_id in self.team_ids:
            self._team_context_dirs[team_id] = get_team_shared_memory_dir(team_id)
        
        self._initialized = False
        self._last_search_stats: dict[str, Any] = {}
        self._init_context_structure()
    
    def _init_context_structure(self) -> None:
        """初始化上下文目录结构。"""
        if self._initialized:
            return
            
        dirs_to_create = [
            self.context_dir,
            self.context_dir / self.MEMORIES_DIR / self.L0_DIR,
            self.context_dir / self.MEMORIES_DIR / self.L1_DIR,
            self.context_dir / self.MEMORIES_DIR / self.L2_DIR,
            self.context_dir / self.RESOURCES_DIR / self.FILES_DIR,
            self.context_dir / self.RESOURCES_DIR / self.CODE_DIR,
            self.context_dir / self.RESOURCES_DIR / self.EXTERNAL_DIR,
            self.context_dir / self.SKILLS_DIR / self.ACTIVE_DIR,
            self.context_dir / self.SKILLS_DIR / self.ARCHIVED_DIR,
            self.context_dir / self.EXECUTIONS_DIR / self.RECENT_DIR,
            self.context_dir / self.EXECUTIONS_DIR / self.ARCHIVED_DIR,
        ]
        
        for dir_path in dirs_to_create:
            ensure_dir(dir_path)
        
        self._create_readme_files()
        self._initialized = True
        logger.info("Hierarchical context structure initialized at {}", self.context_dir)

    @staticmethod
    def _timestamp_slug() -> str:
        """Generate a collision-resistant timestamp slug for filenames."""
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    def _create_readme_files(self) -> None:
        """创建各目录的说明文件。"""
        readmes = {
            self.context_dir / self.MEMORIES_DIR / self.L0_DIR / "README.md": 
                "# L0 核心记忆\n\n当前会话的核心记忆，始终加载。\n",
            self.context_dir / self.MEMORIES_DIR / self.L1_DIR / "README.md":
                "# L1 相关记忆\n\n近期会话的相关记忆，按需加载。\n",
            self.context_dir / self.MEMORIES_DIR / self.L2_DIR / "README.md":
                "# L2 历史记忆\n\n长期历史记忆，检索加载。\n",
            self.context_dir / self.EXECUTIONS_DIR / self.RECENT_DIR / "README.md":
                "# 近期执行\n\n近期任务执行历史，自动归档。\n",
            self.context_dir / self.EXECUTIONS_DIR / self.ARCHIVED_DIR / "README.md":
                "# 归档执行\n\n已归档的任务执行历史。\n",
        }
        
        for path, content in readmes.items():
            if not path.exists():
                path.write_text(content, encoding="utf-8")
    
    @property
    def memories_l0_dir(self) -> Path:
        return self.context_dir / self.MEMORIES_DIR / self.L0_DIR
    
    @property
    def memories_l1_dir(self) -> Path:
        return self.context_dir / self.MEMORIES_DIR / self.L1_DIR
    
    @property
    def memories_l2_dir(self) -> Path:
        return self.context_dir / self.MEMORIES_DIR / self.L2_DIR
    
    @property
    def executions_recent_dir(self) -> Path:
        return self.context_dir / self.EXECUTIONS_DIR / self.RECENT_DIR
    
    @property
    def executions_archived_dir(self) -> Path:
        return self.context_dir / self.EXECUTIONS_DIR / self.ARCHIVED_DIR
    
    @property
    def skills_active_dir(self) -> Path:
        return self.context_dir / self.SKILLS_DIR / self.ACTIVE_DIR
    
    @property
    def resources_files_dir(self) -> Path:
        return self.context_dir / self.RESOURCES_DIR / self.FILES_DIR
    
    def load_context(
        self,
        session_key: str,
        levels: list[str] | None = None,
        max_tokens: int = 8000,
        include_team_context: bool = True,
    ) -> str:
        """
        分层加载上下文。
        
        Args:
            session_key: 会话标识
            levels: 要加载的层级列表，默认["L0", "L1"]
            max_tokens: 最大token预算
            include_team_context: 是否包含团队共享记忆
            
        Returns:
            组装后的上下文字符串
        """
        if levels is None:
            levels = ["L0", "L1"]
        
        context_parts = []
        remaining_tokens = max_tokens
        
        for level in levels:
            if remaining_tokens <= 0:
                break
                
            level_tokens = int(max_tokens * self._get_level_budget(level))
            level_context = self._load_level_context(level, session_key, level_tokens)
            
            if level_context:
                context_parts.append(f"## {level} Context\n\n{level_context}")
                remaining_tokens -= len(level_context) // 4
        
        if include_team_context and self._team_context_dirs:
            team_context = self._load_team_contexts(remaining_tokens // 2)
            if team_context:
                context_parts.append(team_context)
        
        return "\n\n---\n\n".join(context_parts)
    
    def _load_team_contexts(self, max_tokens: int) -> str:
        """加载所有团队共享记忆。"""
        if not self._team_context_dirs:
            return ""
        
        context_parts = []
        char_budget = max_tokens * 4
        
        for team_id, team_dir in self._team_context_dirs.items():
            if not team_dir.exists():
                continue
            
            team_memory_file = team_dir / "MEMORY.md"
            if team_memory_file.exists():
                content = team_memory_file.read_text(encoding="utf-8")
                if len(content) > char_budget:
                    content = content[:char_budget] + "\n... (truncated)"
                context_parts.append(f"## Team {team_id} Shared Memory\n\n{content}")
                char_budget -= len(content)
                
                if char_budget <= 0:
                    break
        
        return "\n\n".join(context_parts) if context_parts else ""
    
    def _get_level_budget(self, level: str) -> float:
        """获取指定层级的token预算比例。"""
        budgets = {
            "L0": self.TOKEN_BUDGET_L0,
            "L1": self.TOKEN_BUDGET_L1,
            "L2": self.TOKEN_BUDGET_L2,
        }
        return budgets.get(level, 0.1)
    
    def _load_level_context(
        self,
        level: str,
        session_key: str,
        max_tokens: int,
    ) -> str:
        """加载指定层级的上下文。"""
        level_dir = self.context_dir / self.MEMORIES_DIR / level
        if not level_dir.exists():
            return ""
        
        context_parts = []
        char_budget = max_tokens * 4
        
        if level == "L0":
            session_file = level_dir / f"{self._safe_filename(session_key)}.md"
            if session_file.exists():
                content = session_file.read_text(encoding="utf-8")
                context_parts.append(content)
        else:
            files = sorted(level_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            for file_path in files:
                if file_path.name == "README.md":
                    continue
                content = file_path.read_text(encoding="utf-8")
                if sum(len(p) for p in context_parts) + len(content) > char_budget:
                    break
                context_parts.append(f"### {file_path.stem}\n\n{content}")
        
        return "\n\n".join(context_parts)
    
    def add_memory(
        self,
        content: str,
        level: str = "L1",
        metadata: dict[str, Any] | None = None,
        session_key: str | None = None,
    ) -> Path:
        """
        添加记忆到指定层级。
        
        Args:
            content: 记忆内容
            level: 目标层级 (L0/L1/L2)
            metadata: 元数据
            session_key: 会话标识（L0层级必需）
            
        Returns:
            保存的文件路径
        """
        level_dir = self.context_dir / self.MEMORIES_DIR / level
        ensure_dir(level_dir)
        
        timestamp = self._timestamp_slug()
        
        if level == "L0" and session_key:
            filename = f"{self._safe_filename(session_key)}.md"
        else:
            filename = f"memory_{timestamp}.md"
        
        file_path = level_dir / filename
        
        header = self._build_memory_header(metadata)
        full_content = f"{header}\n\n{content}"
        
        if level == "L0" and file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            full_content = f"{existing}\n\n---\n\n{header}\n\n{content}"
        
        file_path.write_text(full_content, encoding="utf-8")
        logger.debug("Added memory to {}: {}", level, file_path.name)
        
        return file_path
    
    def _build_memory_header(self, metadata: dict[str, Any] | None) -> str:
        """构建记忆文件的头部信息。"""
        lines = [f"<!-- Created: {datetime.now().isoformat()} -->"]
        if metadata:
            for key, value in metadata.items():
                lines.append(f"<!-- {key}: {value} -->")
        return "\n".join(lines)
    
    def add_execution(
        self,
        execution_log: dict[str, Any],
        session_key: str,
    ) -> Path:
        """
        添加执行历史。
        
        Args:
            execution_log: 执行日志
            session_key: 会话标识
            
        Returns:
            保存的文件路径
        """
        timestamp = self._timestamp_slug()
        filename = f"{self._safe_filename(session_key)}_{timestamp}.json"
        file_path = self.executions_recent_dir / filename
        
        execution_log["created_at"] = datetime.now().isoformat()
        execution_log["session_key"] = session_key
        
        file_path.write_text(
            json.dumps(execution_log, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.debug("Added execution log: {}", filename)
        
        self._archive_old_executions()
        
        return file_path
    
    def _archive_old_executions(self) -> None:
        """归档旧的执行历史。"""
        recent_files = sorted(
            self.executions_recent_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if len(recent_files) > self.MAX_EXECUTIONS_RECENT:
            for old_file in recent_files[self.MAX_EXECUTIONS_RECENT:]:
                archive_path = self.executions_archived_dir / old_file.name
                old_file.rename(archive_path)
                logger.debug("Archived execution: {}", old_file.name)
    
    def search_context(
        self,
        query: str,
        levels: list[str] | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        搜索上下文。
        
        Args:
            query: 搜索查询
            levels: 搜索的层级列表
            max_results: 最大结果数
            
        Returns:
            匹配的结果列表
        """
        if levels is None:
            levels = ["L0", "L1", "L2"]
        
        results = []
        scanned_sections = 0
        query_lower = query.lower()
        query_terms = self._extract_search_terms(query)
        temporal_terms = self._extract_temporal_terms(query)
        
        for level in levels:
            level_dir = self.context_dir / self.MEMORIES_DIR / level
            if not level_dir.exists():
                continue
            
            for file_path in level_dir.glob("*.md"):
                if file_path.name == "README.md":
                    continue

                if not query_terms and not query_lower.strip():
                    file_payload = self._build_file_result(file_path, level)
                    if file_payload:
                        results.append(file_payload)
                    continue

                for section_index, metadata, content in self._iter_memory_sections(file_path):
                    if not content:
                        continue
                    scanned_sections += 1

                    analysis = self._analyze_segment_relevance(
                        content=content,
                        query=query_lower,
                        query_terms=query_terms,
                        temporal_terms=temporal_terms,
                        level=level,
                        metadata=metadata,
                    )
                    if not analysis["matched"]:
                        continue

                    snippet = self._extract_best_snippet(content, query_terms, query_lower, 220)
                    results.append({
                        "level": level,
                        "file": file_path.name,
                        "path": str(file_path),
                        "snippet": snippet,
                        "relevance": 0.0,
                        "metadata": metadata,
                        "section_index": section_index,
                        "title": analysis["title"],
                        "matched_terms": analysis["matched_terms"],
                        "reasons": analysis["reasons"],
                        "score_breakdown": analysis["score_breakdown"],
                        "_analysis": analysis,
                    })

        matched_count = len(results)
        self._apply_hybrid_fusion(results)
        for result in results:
            result.pop("_analysis", None)

        results.sort(key=lambda x: x["relevance"], reverse=True)
        trimmed = results[:max_results]
        self._last_search_stats = {
            "query": query,
            "levels": list(levels),
            "scanned_sections": scanned_sections,
            "matched_count": matched_count,
            "returned_count": len(trimmed),
        }
        return trimmed

    def get_last_search_stats(self) -> dict[str, Any]:
        """Return the most recent search stats snapshot."""
        return dict(self._last_search_stats)

    def _build_file_result(self, file_path: Path, level: str) -> dict[str, Any] | None:
        """Build a coarse result for file-level scans without a query."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to read memory file {}: {}", file_path.name, exc)
            return None

        section_index, metadata, body = next(self._iter_memory_sections(file_path), (0, {}, ""))
        created_at = self._parse_created_at(metadata) or datetime.fromtimestamp(file_path.stat().st_mtime)
        return {
            "level": level,
            "file": file_path.name,
            "path": str(file_path),
            "snippet": self._extract_best_snippet(body or content, [], "", 220),
            "relevance": self._calculate_time_decay(created_at, level),
            "metadata": metadata,
            "section_index": section_index,
            "title": self._extract_section_title(body or content, metadata),
            "matched_terms": [],
            "reasons": ["近期记忆加权"],
            "score_breakdown": {
                "exact_phrase": 0.0,
                "lexical": 0.0,
                "metadata": 0.0,
                "title": 0.0,
                "temporal": 0.0,
                "recency": self._calculate_time_decay(created_at, level),
                "rrf": 0.0,
            },
        }

    def _iter_memory_sections(self, file_path: Path):
        """Yield parsed memory sections from a markdown memory file."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to read memory file {}: {}", file_path.name, exc)
            return

        sections = self.MEMORY_SEPARATOR_PATTERN.split(raw_content)
        for index, section in enumerate(sections):
            metadata, content = self._parse_memory_section(section)
            if metadata or content:
                yield index, metadata, content

    def _parse_memory_section(self, raw_section: str) -> tuple[dict[str, Any], str]:
        """Parse metadata headers and content from a memory section."""
        metadata: dict[str, Any] = {}
        body_lines: list[str] = []
        in_header = True

        for raw_line in raw_section.splitlines():
            stripped = raw_line.strip()
            header_match = self.MEMORY_HEADER_PATTERN.match(stripped) if in_header else None
            if header_match:
                key = header_match.group(1).strip()
                value = header_match.group(2).strip()
                metadata[key] = value
                continue

            if in_header and not stripped:
                continue

            in_header = False
            body_lines.append(raw_line)

        return metadata, "\n".join(body_lines).strip()

    def _extract_search_terms(self, query: str) -> list[str]:
        """Extract normalized search terms from a query."""
        seen: set[str] = set()
        terms: list[str] = []
        for token in self.SEARCH_TOKEN_PATTERN.findall(query.lower()):
            if token not in seen:
                seen.add(token)
                terms.append(token)
        return terms

    def _extract_temporal_terms(self, query: str) -> list[str]:
        """Extract normalized temporal hints from a query."""
        seen: set[str] = set()
        terms: list[str] = []
        for token in self.TEMPORAL_TOKEN_PATTERN.findall(query):
            normalized = token.replace("/", "-").strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                terms.append(normalized)
        return terms

    def _parse_created_at(self, metadata: dict[str, Any]) -> datetime | None:
        """Parse creation time from memory metadata."""
        for key in ("Created", "created_at", "created"):
            value = metadata.get(key)
            if not value:
                continue
            try:
                return datetime.fromisoformat(str(value))
            except ValueError:
                continue
        return None

    def _extract_section_title(self, content: str, metadata: dict[str, Any]) -> str:
        """Extract a human-friendly section title from metadata or markdown body."""
        for key in ("Title", "title", "Topic", "topic", "Summary", "summary"):
            value = str(metadata.get(key, "")).strip()
            if value:
                return value[:120]

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                return line.lstrip("#").strip()[:120]
            if line.startswith("- "):
                return line[2:].strip()[:120]
            return line[:120]
        return ""

    def _analyze_segment_relevance(
        self,
        *,
        content: str,
        query: str,
        query_terms: list[str],
        temporal_terms: list[str],
        level: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Analyze a memory section using lexical, metadata, title, temporal, and recency signals."""
        content_lower = content.lower()
        metadata_text = " ".join(f"{k} {v}" for k, v in metadata.items()).lower()
        title = self._extract_section_title(content, metadata)
        title_lower = title.lower()

        exact_phrase_score = 2.4 if query and (
            query in content_lower or query in metadata_text or query in title_lower
        ) else 0.0
        unique_hits = sum(1 for term in query_terms if term in content_lower)
        metadata_hits = sum(1 for term in query_terms if term in metadata_text)
        title_hits = sum(1 for term in query_terms if term in title_lower)
        frequency_hits = sum(content_lower.count(term) for term in query_terms)
        temporal_hits = sum(
            1 for term in temporal_terms
            if term in content_lower or term in metadata_text or term in title_lower
        )

        lexical_score = 0.0
        if query_terms:
            lexical_score += (unique_hits / len(query_terms)) * 3.0
        lexical_score += min(2.0, frequency_hits * 0.35)
        metadata_score = min(1.4, metadata_hits * 0.45)
        title_score = min(1.2, title_hits * 0.6)
        temporal_score = min(1.8, temporal_hits * 0.9)

        created_at = self._parse_created_at(metadata)
        time_decay = self._calculate_time_decay(created_at, level)
        matched = bool(
            exact_phrase_score
            or unique_hits
            or metadata_hits
            or title_hits
            or temporal_hits
            or (not query and not query_terms and not temporal_terms)
        )

        matched_terms = [
            term for term in query_terms
            if term in content_lower or term in metadata_text or term in title_lower
        ]
        reasons: list[str] = []
        if exact_phrase_score:
            reasons.append("短语精确命中")
        if unique_hits:
            reasons.append(f"关键词命中 {unique_hits} 项")
        if title_hits:
            reasons.append("标题/主题命中")
        if metadata_hits:
            reasons.append("元数据命中")
        if temporal_hits:
            reasons.append("时间信息命中")
        if time_decay >= 0.45:
            reasons.append("近期记忆加权")

        return {
            "matched": matched,
            "title": title,
            "matched_terms": matched_terms,
            "reasons": reasons or ["基础相关性命中"],
            "score_breakdown": {
                "exact_phrase": round(exact_phrase_score, 4),
                "lexical": round(lexical_score, 4),
                "metadata": round(metadata_score, 4),
                "title": round(title_score, 4),
                "temporal": round(temporal_score, 4),
                "recency": round(time_decay, 4),
                "rrf": 0.0,
            },
        }

    def _apply_hybrid_fusion(self, results: list[dict[str, Any]]) -> None:
        """Fuse multiple ranking signals with a lightweight reciprocal-rank strategy."""
        if not results:
            return

        score_fields = ("lexical", "metadata", "title", "temporal", "recency")
        rank_index: dict[tuple[str, int], dict[str, int]] = {}
        k = 50.0

        for field in score_fields:
            ranked = sorted(
                (
                    result for result in results
                    if result.get("_analysis", {}).get("score_breakdown", {}).get(field, 0.0) > 0
                ),
                key=lambda item: item["_analysis"]["score_breakdown"][field],
                reverse=True,
            )
            for rank, result in enumerate(ranked, start=1):
                key = (result["path"], result.get("section_index", 0))
                rank_index.setdefault(key, {})[field] = rank

        for result in results:
            analysis = result.get("_analysis", {})
            score_breakdown = dict(analysis.get("score_breakdown", {}))
            key = (result["path"], result.get("section_index", 0))
            fused = 0.0
            for field, rank in rank_index.get(key, {}).items():
                fused += 1.0 / (k + rank)
            score_breakdown["rrf"] = round(fused, 4)
            exact_phrase = score_breakdown.get("exact_phrase", 0.0)
            raw_signal = (
                score_breakdown.get("lexical", 0.0)
                + score_breakdown.get("metadata", 0.0)
                + score_breakdown.get("title", 0.0)
                + score_breakdown.get("temporal", 0.0)
            )
            result["score_breakdown"] = score_breakdown
            result["relevance"] = round(exact_phrase + raw_signal * 0.35 + score_breakdown.get("recency", 0.0) * 0.4 + fused * 20.0, 4)

    def _calculate_time_decay(self, created_at: datetime | None, level: str) -> float:
        """Prefer fresher memories while still allowing durable L2 facts to surface."""
        if created_at is None:
            return {"L0": 0.8, "L1": 0.5, "L2": 0.25}.get(level, 0.2)

        age_hours = max(0.0, (datetime.now() - created_at).total_seconds() / 3600)
        half_life_hours = {"L0": 8.0, "L1": 72.0, "L2": 24.0 * 30.0}.get(level, 72.0)
        decay = math.exp(-age_hours / half_life_hours)
        base = {"L0": 1.1, "L1": 0.75, "L2": 0.45}.get(level, 0.3)
        return round(base * decay, 4)

    def _extract_best_snippet(
        self,
        content: str,
        query_terms: list[str],
        query: str,
        max_len: int,
    ) -> str:
        """Extract the most relevant snippet around the first matching term."""
        content_lower = content.lower()
        anchor = -1

        if query:
            anchor = content_lower.find(query)

        if anchor == -1:
            for term in query_terms:
                anchor = content_lower.find(term)
                if anchor != -1:
                    break

        if anchor == -1:
            compact = re.sub(r"\s+", " ", content).strip()
            return compact[:max_len] + "..." if len(compact) > max_len else compact

        start = max(0, anchor - max_len // 2)
        end = min(len(content), anchor + max_len // 2)
        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet
    
    def _extract_snippet(self, content: str, query: str, max_len: int) -> str:
        """提取包含查询词的片段。"""
        content_lower = content.lower()
        idx = content_lower.find(query)
        
        if idx == -1:
            return content[:max_len] + "..." if len(content) > max_len else content
        
        start = max(0, idx - max_len // 2)
        end = min(len(content), idx + max_len // 2)
        
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    def _calculate_relevance(self, content: str, query: str) -> float:
        """计算内容与查询的相关性分数。"""
        content_lower = content.lower()
        count = content_lower.count(query)
        density = count / len(content) if content else 0
        return min(1.0, density * 100 + count * 0.1)
    
    def get_execution_history(
        self,
        session_key: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        获取执行历史。
        
        Args:
            session_key: 会话标识（可选，用于过滤）
            limit: 最大返回数量
            
        Returns:
            执行历史列表
        """
        results = []
        
        for file_path in sorted(
            self.executions_recent_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit * 2]:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if session_key is None or data.get("session_key") == session_key:
                    results.append(data)
                    if len(results) >= limit:
                        break
            except (json.JSONDecodeError, Exception) as e:
                logger.warning("Failed to read execution log {}: {}", file_path.name, e)
        
        return results
    
    def extract_key_info_as_memory(
        self,
        execution_log: dict[str, Any],
    ) -> str | None:
        """
        从执行日志中提取关键信息作为长期记忆。
        
        Args:
            execution_log: 执行日志
            
        Returns:
            提取的关键信息，如果没有则返回None
        """
        key_info = []
        
        if "task" in execution_log:
            key_info.append(f"任务: {execution_log['task']}")
        
        if "result" in execution_log:
            result = execution_log["result"]
            if isinstance(result, str) and result and len(result) > 50:
                key_info.append(f"结果摘要: {result[:200]}...")
        
        if "tools_used" in execution_log:
            tools = execution_log["tools_used"]
            if isinstance(tools, list) and tools:
                key_info.append(f"使用工具: {', '.join(tools)}")
        
        if "errors" in execution_log:
            errors = execution_log["errors"]
            if errors:
                key_info.append(f"遇到问题: {errors}")
        
        if len(key_info) >= 2:
            return "\n".join(key_info)
        
        return None
    
    def promote_memory(self, file_path: Path, from_level: str, to_level: str) -> bool:
        """
        将记忆从一个层级提升到另一个层级。
        
        Args:
            file_path: 记忆文件路径
            from_level: 源层级
            to_level: 目标层级
            
        Returns:
            是否成功
        """
        try:
            from_dir = self.context_dir / self.MEMORIES_DIR / from_level
            to_dir = self.context_dir / self.MEMORIES_DIR / to_level
            
            if not file_path.exists():
                return False
            
            new_path = to_dir / file_path.name
            file_path.rename(new_path)
            logger.info("Promoted memory from {} to {}: {}", from_level, to_level, file_path.name)
            return True
        except Exception as e:
            logger.error("Failed to promote memory: {}", e)
            return False
    
    def clear_session_context(self, session_key: str) -> None:
        """
        清除指定会话的L0上下文。
        
        Args:
            session_key: 会话标识
        """
        session_file = self.memories_l0_dir / f"{self._safe_filename(session_key)}.md"
        if session_file.exists():
            session_file.unlink()
            logger.debug("Cleared L0 context for session: {}", session_key)
    
    def _safe_filename(self, name: str) -> str:
        """将字符串转换为安全的文件名。"""
        unsafe = '<>:"/\\|?*'
        for char in unsafe:
            name = name.replace(char, "_")
        return name.strip()
    
    def get_context_stats(self) -> dict[str, Any]:
        """获取上下文统计信息。"""
        stats = {
            "memories": {},
            "executions": {},
            "resources": {},
            "skills": {},
        }
        
        for level in ["L0", "L1", "L2"]:
            level_dir = self.context_dir / self.MEMORIES_DIR / level
            files = list(level_dir.glob("*.md"))
            stats["memories"][level] = {
                "count": len([f for f in files if f.name != "README.md"]),
                "total_size": sum(f.stat().st_size for f in files if f.name != "README.md"),
            }
        
        recent_execs = list(self.executions_recent_dir.glob("*.json"))
        archived_execs = list(self.executions_archived_dir.glob("*.json"))
        stats["executions"] = {
            "recent": len(recent_execs),
            "archived": len(archived_execs),
        }
        
        active_skills = list(self.skills_active_dir.glob("*.md"))
        stats["skills"]["active"] = len(active_skills)
        
        return stats
    
    # ============== Resources Management ==============
    
    def add_resource(
        self,
        content: str,
        resource_type: str = "file",
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """
        添加资源。
        
        Args:
            content: 资源内容（代码、文本、URL等）
            resource_type: 资源类型 (file/code/external)
            name: 资源名称（可选，默认自动生成）
            metadata: 元数据
            
        Returns:
            保存的文件路径
        """
        type_dir = self._get_resource_dir(resource_type)
        ensure_dir(type_dir)
        
        timestamp = self._timestamp_slug()
        
        if not name:
            name = f"resource_{timestamp}"
        
        ext = self._detect_extension(content, resource_type)
        filename = f"{self._safe_filename(name)}{ext}"
        file_path = type_dir / filename
        
        header = self._build_resource_header(resource_type, metadata)
        full_content = f"{header}\n\n{content}"
        
        file_path.write_text(full_content, encoding="utf-8")
        logger.debug("Added resource: {} ({})", filename, resource_type)
        
        return file_path
    
    def _get_resource_dir(self, resource_type: str) -> Path:
        """获取资源类型的目录。"""
        type_map = {
            "file": self.resources_files_dir,
            "code": self.context_dir / self.RESOURCES_DIR / self.CODE_DIR,
            "external": self.context_dir / self.RESOURCES_DIR / self.EXTERNAL_DIR,
        }
        return type_map.get(resource_type, self.resources_files_dir)
    
    def _detect_extension(self, content: str, resource_type: str) -> str:
        """根据内容检测文件扩展名。"""
        if resource_type == "code":
            if "def " in content or "import " in content:
                if ":" in content and "    " in content:
                    return ".py"
                if "function" in content or "const" in content:
                    return ".js"
            return ".txt"
        
        if resource_type == "external":
            if content.startswith("http"):
                return ".url"
            return ".txt"
        
        return ".txt"
    
    def _build_resource_header(self, resource_type: str, metadata: dict[str, Any] | None) -> str:
        """构建资源文件的头部信息。"""
        lines = [
            f"<!-- Resource Type: {resource_type} -->",
            f"<!-- Created: {datetime.now().isoformat()} -->",
        ]
        if metadata:
            for key, value in metadata.items():
                lines.append(f"<!-- {key}: {value} -->")
        return "\n".join(lines)
    
    def get_resource(
        self,
        name: str,
        resource_type: str | None = None,
    ) -> dict[str, Any] | None:
        """
        获取资源。
        
        Args:
            name: 资源名称
            resource_type: 资源类型（可选）
            
        Returns:
            资源信息，包含内容和元数据
        """
        if resource_type:
            type_dirs = [self._get_resource_dir(resource_type)]
        else:
            type_dirs = [
                self.resources_files_dir,
                self.context_dir / self.RESOURCES_DIR / self.CODE_DIR,
                self.context_dir / self.RESOURCES_DIR / self.EXTERNAL_DIR,
            ]
        
        for type_dir in type_dirs:
            for file_path in type_dir.glob(f"{self._safe_filename(name)}.*"):
                content = file_path.read_text(encoding="utf-8")
                return {
                    "name": file_path.stem,
                    "path": str(file_path),
                    "type": self._get_resource_type_from_path(file_path),
                    "content": self._strip_header(content),
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                }
        
        return None
    
    def _get_resource_type_from_path(self, path: Path) -> str:
        """从路径推断资源类型。"""
        parent = path.parent.name
        if parent == self.CODE_DIR:
            return "code"
        elif parent == self.EXTERNAL_DIR:
            return "external"
        return "file"
    
    def _strip_header(self, content: str) -> str:
        """移除资源文件的头部注释。"""
        lines = content.split("\n")
        result = []
        in_header = False
        
        for line in lines:
            if line.startswith("<!--") and not in_header:
                in_header = True
                continue
            if in_header and line.startswith("-->"):
                in_header = False
                continue
            if not in_header:
                result.append(line)
        
        return "\n".join(result).strip()
    
    def search_resources(
        self,
        query: str,
        resource_type: str | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """
        搜索资源。
        
        Args:
            query: 搜索查询
            resource_type: 资源类型过滤
            max_results: 最大结果数
            
        Returns:
            匹配的资源列表
        """
        results = []
        query_lower = query.lower()
        
        if resource_type:
            type_dirs = [self._get_resource_dir(resource_type)]
        else:
            type_dirs = [
                self.resources_files_dir,
                self.context_dir / self.RESOURCES_DIR / self.CODE_DIR,
                self.context_dir / self.RESOURCES_DIR / self.EXTERNAL_DIR,
            ]
        
        for type_dir in type_dirs:
            if not type_dir.exists():
                continue
            
            for file_path in type_dir.glob("*.*"):
                if file_path.name.startswith("."):
                    continue
                
                content = file_path.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    results.append({
                        "name": file_path.stem,
                        "path": str(file_path),
                        "type": self._get_resource_type_from_path(file_path),
                        "snippet": self._extract_snippet(content, query_lower, 150),
                    })
        
        results.sort(key=lambda x: len(x["snippet"]), reverse=True)
        return results[:max_results]
    
    def list_resources(
        self,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        列出资源。
        
        Args:
            resource_type: 资源类型过滤
            
        Returns:
            资源列表
        """
        resources = []
        
        if resource_type:
            type_dirs = [self._get_resource_dir(resource_type)]
        else:
            type_dirs = [
                self.resources_files_dir,
                self.context_dir / self.RESOURCES_DIR / self.CODE_DIR,
                self.context_dir / self.RESOURCES_DIR / self.EXTERNAL_DIR,
            ]
        
        for type_dir in type_dirs:
            if not type_dir.exists():
                continue
            
            for file_path in type_dir.glob("*.*"):
                if file_path.name.startswith("."):
                    continue
                
                resources.append({
                    "name": file_path.stem,
                    "path": str(file_path),
                    "type": self._get_resource_type_from_path(file_path),
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                })
        
        return sorted(resources, key=lambda x: x["modified"], reverse=True)
    
    # ============== Skills Management ==============
    
    def link_skill(
        self,
        skill_name: str,
        skill_path: Path | None = None,
        description: str | None = None,
    ) -> Path:
        """
        链接技能到活跃技能列表。
        
        Args:
            skill_name: 技能名称
            skill_path: 技能文件路径（可选）
            description: 技能描述
            
        Returns:
            创建的链接文件路径
        """
        ensure_dir(self.skills_active_dir)
        
        filename = f"{self._safe_filename(skill_name)}.md"
        file_path = self.skills_active_dir / filename
        
        content_parts = [
            f"# Skill: {skill_name}",
            f"<!-- Linked: {datetime.now().isoformat()} -->",
        ]
        
        if description:
            content_parts.append(f"\n{description}")
        
        if skill_path and skill_path.exists():
            content_parts.append(f"\n## Source\n\n`{skill_path}`")
            
            if skill_path.suffix == ".md":
                source_content = skill_path.read_text(encoding="utf-8")
                preview = source_content[:500] + "..." if len(source_content) > 500 else source_content
                content_parts.append(f"\n## Preview\n\n{preview}")
        
        file_path.write_text("\n".join(content_parts), encoding="utf-8")
        logger.info("Linked skill: {}", skill_name)
        
        return file_path
    
    def unlink_skill(self, skill_name: str) -> bool:
        """
        取消链接技能。
        
        Args:
            skill_name: 技能名称
            
        Returns:
            是否成功
        """
        filename = f"{self._safe_filename(skill_name)}.md"
        file_path = self.skills_active_dir / filename
        
        if file_path.exists():
            file_path.unlink()
            logger.info("Unlinked skill: {}", skill_name)
            return True
        return False
    
    def get_active_skills(self) -> list[dict[str, Any]]:
        """
        获取活跃技能列表。
        
        Returns:
            技能列表
        """
        skills = []
        
        if not self.skills_active_dir.exists():
            return skills
        
        for file_path in self.skills_active_dir.glob("*.md"):
            content = file_path.read_text(encoding="utf-8")
            skills.append({
                "name": file_path.stem,
                "path": str(file_path),
                "description": self._extract_skill_description(content),
                "linked_at": self._extract_linked_date(content),
            })
        
        return skills
    
    def _extract_skill_description(self, content: str) -> str:
        """从技能文件中提取描述。"""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("## ") and i + 1 < len(lines):
                return lines[i + 1].strip()
        return ""
    
    def _extract_linked_date(self, content: str) -> str | None:
        """从技能文件中提取链接日期。"""
        import re
        match = re.search(r"Linked: (.+?)(?:-->|$)", content, re.MULTILINE)
        return match.group(1).strip() if match else None
    
    def archive_skill(self, skill_name: str) -> bool:
        """
        归档技能。
        
        Args:
            skill_name: 技能名称
            
        Returns:
            是否成功
        """
        filename = f"{self._safe_filename(skill_name)}.md"
        source = self.skills_active_dir / filename
        
        if not source.exists():
            return False
        
        ensure_dir(self.context_dir / self.SKILLS_DIR / self.ARCHIVED_DIR)
        dest = self.context_dir / self.SKILLS_DIR / self.ARCHIVED_DIR / filename
        
        source.rename(dest)
        logger.info("Archived skill: {}", skill_name)
        return True
