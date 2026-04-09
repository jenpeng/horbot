"""Skill loader module - on-demand skill loading for reduced initial context."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json

from loguru import logger


@dataclass
class SkillMetadata:
    """Metadata extracted from a skill file."""
    
    name: str
    description: str = ""
    version: str = "1.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    always_active: bool = False
    file_path: Path | None = None
    loaded_at: datetime | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "requires": self.requires,
            "always_active": self.always_active,
            "file_path": str(self.file_path) if self.file_path else None,
        }


@dataclass
class LoadedSkill:
    """A fully loaded skill with content."""
    
    metadata: SkillMetadata
    content: str
    loaded_at: datetime = field(default_factory=datetime.now)
    
    def to_context_block(self) -> str:
        """Format as context block for LLM."""
        return f"""### Skill: {self.metadata.name}

{self.content}"""


class SkillLoader:
    """On-demand skill loader for reduced initial context.
    
    Instead of loading all skills upfront, this loader:
    1. Builds a lightweight summary of available skills
    2. Loads full skill content only when needed
    3. Caches loaded skills for the session
    
    This reduces initial context usage while keeping skills accessible.
    
    Example:
        loader = SkillLoader(skills_dir=Path(".horbot/agents/main/workspace/skills"))
        
        # Get lightweight summary for initial context
        summary = loader.build_skills_summary()
        
        # Load specific skill on demand
        skill = loader.load_skill("pdf")
        if skill:
            context_block = skill.to_context_block()
    """
    
    def __init__(
        self,
        skills_dir: Path | None = None,
        builtin_skills_dir: Path | None = None,
        cache_loaded: bool = True,
    ):
        """Initialize skill loader.
        
        Args:
            skills_dir: Directory for user-defined skills (defaults to workspace/skills/)
            builtin_skills_dir: Directory for built-in skills (defaults to horbot/skills/)
            cache_loaded: Whether to cache loaded skills
        """
        if skills_dir is None:
            from horbot.utils.paths import get_skills_dir
            skills_dir = get_skills_dir()
        
        if builtin_skills_dir is None:
            from horbot.utils.paths import get_horbot_root
            builtin_skills_dir = get_horbot_root().parent / "horbot" / "skills"
        
        self.skills_dir = skills_dir
        self.builtin_skills_dir = builtin_skills_dir
        self.cache_loaded = cache_loaded
        
        self._metadata_cache: dict[str, SkillMetadata] = {}
        self._loaded_cache: dict[str, LoadedSkill] = {}
        self._scanned = False
    
    def scan_skills(self, force: bool = False) -> dict[str, SkillMetadata]:
        """Scan all available skills and cache metadata.
        
        Args:
            force: Force rescan even if already scanned
            
        Returns:
            Dict of skill name -> metadata
        """
        if self._scanned and not force:
            return self._metadata_cache
        
        self._metadata_cache.clear()
        
        # Scan built-in skills
        if self.builtin_skills_dir and self.builtin_skills_dir.exists():
            for skill_file in self.builtin_skills_dir.glob("*/SKILL.md"):
                metadata = self._parse_skill_file(skill_file)
                if metadata:
                    self._metadata_cache[metadata.name] = metadata
        
        # Scan user skills
        if self.skills_dir and self.skills_dir.exists():
            for skill_file in self.skills_dir.glob("*/SKILL.md"):
                metadata = self._parse_skill_file(skill_file)
                if metadata:
                    self._metadata_cache[metadata.name] = metadata
        
        self._scanned = True
        logger.debug(f"Scanned {len(self._metadata_cache)} skills")
        return self._metadata_cache
    
    def _parse_skill_file(self, file_path: Path) -> SkillMetadata | None:
        """Parse a skill file and extract metadata.
        
        Args:
            file_path: Path to SKILL.md file
            
        Returns:
            SkillMetadata or None
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Extract frontmatter
            metadata = SkillMetadata(
                name=file_path.parent.name,
                file_path=file_path,
            )
            
            if content.startswith("---"):
                match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if match:
                    frontmatter = match.group(1)
                    for line in frontmatter.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip().lower()
                            value = value.strip()
                            
                            if key == "name":
                                metadata.name = value
                            elif key == "description":
                                metadata.description = value
                            elif key == "version":
                                metadata.version = value
                            elif key == "author":
                                metadata.author = value
                            elif key == "tags":
                                metadata.tags = [t.strip() for t in value.split(",")]
                            elif key == "requires":
                                metadata.requires = [r.strip() for r in value.split(",")]
                            elif key == "always_active":
                                metadata.always_active = value.lower() in ("true", "yes", "1")
            
            # Extract description from first paragraph if not in frontmatter
            if not metadata.description:
                content_without_frontmatter = self._strip_frontmatter(content)
                first_para = content_without_frontmatter.split("\n\n")[0]
                metadata.description = first_para.strip()[:200]
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Failed to parse skill file {file_path}: {e}")
            return None
    
    def _strip_frontmatter(self, content: str) -> str:
        """Remove frontmatter from content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():]
        return content
    
    def list_skills(self) -> list[SkillMetadata]:
        """List all available skills.
        
        Returns:
            List of SkillMetadata
        """
        self.scan_skills()
        return list(self._metadata_cache.values())
    
    def get_skill_metadata(self, name: str) -> SkillMetadata | None:
        """Get metadata for a specific skill.
        
        Args:
            name: Skill name
            
        Returns:
            SkillMetadata or None
        """
        self.scan_skills()
        return self._metadata_cache.get(name)
    
    def load_skill(self, name: str) -> LoadedSkill | None:
        """Load a skill's full content.
        
        Args:
            name: Skill name
            
        Returns:
            LoadedSkill or None
        """
        # Check cache first
        if self.cache_loaded and name in self._loaded_cache:
            return self._loaded_cache[name]
        
        # Get metadata
        metadata = self.get_skill_metadata(name)
        if not metadata or not metadata.file_path:
            return None
        
        try:
            content = metadata.file_path.read_text(encoding="utf-8")
            content = self._strip_frontmatter(content)
            
            skill = LoadedSkill(
                metadata=metadata,
                content=content,
            )
            
            if self.cache_loaded:
                self._loaded_cache[name] = skill
            
            logger.debug(f"Loaded skill: {name}")
            return skill
            
        except Exception as e:
            logger.error(f"Failed to load skill {name}: {e}")
            return None
    
    def load_skills_for_context(self, names: list[str]) -> str:
        """Load multiple skills and format for context.
        
        Args:
            names: List of skill names
            
        Returns:
            Formatted skills content
        """
        parts = []
        for name in names:
            skill = self.load_skill(name)
            if skill:
                parts.append(skill.to_context_block())
        
        return "\n\n---\n\n".join(parts) if parts else ""
    
    def build_skills_summary(self) -> str:
        """Build a lightweight summary of all skills.
        
        This is used for initial context - shows what skills are available
        without loading their full content.
        
        Returns:
            XML-formatted skills summary
        """
        skills = self.list_skills()
        if not skills:
            return ""
        
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        lines = ["<skills>"]
        for s in skills:
            name = escape_xml(s.name)
            desc = escape_xml(s.description[:100] if s.description else "")
            path = str(s.file_path) if s.file_path else ""
            
            lines.append(f'  <skill name="{name}" path="{path}">')
            if desc:
                lines.append(f"    <description>{desc}</description>")
            if s.tags:
                lines.append(f'    <tags>{", ".join(s.tags)}</tags>')
            if s.always_active:
                lines.append('    <always_active>true</always_active>')
            lines.append("  </skill>")
        
        lines.append("</skills>")
        return "\n".join(lines)
    
    def get_always_active_skills(self) -> list[str]:
        """Get list of skills that should always be active.
        
        Returns:
            List of skill names marked as always_active
        """
        self.scan_skills()
        return [
            name for name, metadata in self._metadata_cache.items()
            if metadata.always_active
        ]
    
    def clear_cache(self) -> None:
        """Clear the loaded skills cache."""
        self._loaded_cache.clear()
        logger.debug("Skill cache cleared")
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dict with cache stats
        """
        return {
            "metadata_cached": len(self._metadata_cache),
            "skills_loaded": len(self._loaded_cache),
            "cache_enabled": self.cache_loaded,
        }
