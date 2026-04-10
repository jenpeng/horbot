"""Skills loader for agent capabilities."""

import json
import os
import re
import shutil
from pathlib import Path

from horbot.agent.skill_metadata_adapter import parse_skill_metadata
from horbot.workspace.manager import AGENT_METADATA_DIRNAME

# Default builtin skills directory (relative to this file)
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


def resolve_skills_dir(workspace: Path, agent_id: str | None = None) -> Path:
    """Resolve the user skills directory for a workspace/agent combination."""
    workspace = Path(workspace)

    override_metadata_root = workspace / AGENT_METADATA_DIRNAME
    if override_metadata_root.exists():
        return override_metadata_root / "skills"

    if agent_id:
        try:
            from horbot.agent.manager import get_agent_manager

            agent = get_agent_manager().get_agent(agent_id)
            if agent is not None:
                return agent.get_skills_dir()
        except Exception:
            pass

    return workspace / "skills"


class SkillsLoader:
    """
    Loader for agent skills.
    
    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.
    """
    
    def __init__(
        self,
        workspace: Path | None = None,
        builtin_skills_dir: Path | None = None,
        agent_id: str | None = None,
        skills_dir: Path | None = None,
    ):
        if workspace is None:
            from horbot.utils.paths import get_workspace_dir
            workspace = get_workspace_dir()
        self.workspace = workspace
        self.workspace_skills = Path(skills_dir) if skills_dir is not None else resolve_skills_dir(workspace, agent_id=agent_id)
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
    
    def list_skills(self, filter_unavailable: bool = True, include_disabled: bool = False) -> list[dict[str, str]]:
        """
        List all available skills.
        
        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.
            include_disabled: If False, filter out disabled skills.
        
        Returns:
            List of skill info dicts with 'name', 'path', 'source', 'enabled'.
        """
        skills = []
        
        # Workspace skills (highest priority)
        if self.workspace_skills.exists():
            for item in self.workspace_skills.iterdir():
                if item.is_dir():
                    # Directory structure: workspace/skills/{name}/SKILL.md
                    skill_file = item / "SKILL.md"
                    if skill_file.exists():
                        enabled = self._get_skill_enabled(item.name)
                        skills.append({"name": item.name, "path": str(skill_file), "source": "user", "enabled": enabled})
                elif item.is_file() and item.suffix == ".md":
                    # File structure: workspace/skills/{name}.md (legacy support)
                    skill_name = item.stem
                    enabled = self._get_skill_enabled(skill_name)
                    skills.append({"name": skill_name, "path": str(item), "source": "user", "enabled": enabled})
        
        # Built-in skills
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists() and not any(s["name"] == skill_dir.name for s in skills):
                        enabled = self._get_skill_enabled(skill_dir.name)
                        skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "builtin", "enabled": enabled})
        
        # Filter by enabled status
        if not include_disabled:
            skills = [s for s in skills if s.get("enabled", True)]
        
        # Filter by requirements
        if filter_unavailable:
            return [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
        return skills
    
    def load_skill(self, name: str) -> str | None:
        """
        Load a skill by name.
        
        Args:
            name: Skill name (directory name).
        
        Returns:
            Skill content or None if not found.
        """
        # Check workspace first (directory structure)
        workspace_skill_dir = self.workspace_skills / name / "SKILL.md"
        if workspace_skill_dir.exists():
            return workspace_skill_dir.read_text(encoding="utf-8")
        
        # Check workspace (file structure - legacy support)
        workspace_skill_file = self.workspace_skills / f"{name}.md"
        if workspace_skill_file.exists():
            return workspace_skill_file.read_text(encoding="utf-8")
        
        # Check built-in
        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")
        
        return None
    
    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        Load specific skills for inclusion in agent context.
        
        Args:
            skill_names: List of skill names to load.
        
        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")
        
        return "\n\n---\n\n".join(parts) if parts else ""
    
    def build_skills_summary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).
        
        This is used for progressive loading - the agent can read the full
        skill content using read_file when needed.
        
        Returns:
            XML-formatted skills summary.
        """
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""
        
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            path = s["path"]
            desc = escape_xml(self._get_skill_description(s["name"]))
            skill_meta = self._get_skill_meta(s["name"])
            available = self._check_requirements(skill_meta)
            
            lines.append(f"  <skill available=\"{str(available).lower()}\">")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")
            
            # Show missing requirements for unavailable skills
            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(', '.join(missing))}</requires>")
            
            lines.append(f"  </skill>")
        lines.append("</skills>")
        
        return "\n".join(lines)
    
    def _get_missing_requirements(self, skill_meta: dict) -> list[str]:
        """Get a description of missing requirements."""
        missing: list[str] = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return missing
    
    def _get_skill_description(self, name: str) -> str:
        """Get the description of a skill from its frontmatter."""
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # Fallback to skill name
    
    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content
    
    def _parse_skill_metadata(self, raw: str) -> dict:
        """Parse skill metadata JSON into Horbot's canonical format."""
        return parse_skill_metadata(raw)
    
    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars)."""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True
    
    def _get_skill_enabled(self, name: str) -> bool:
        """Get the enabled status of a skill from canonical metadata or frontmatter."""
        skill_meta = self._get_skill_meta(name)
        enabled = skill_meta.get("enabled")
        if enabled is None:
            meta = self.get_skill_metadata(name)
            if meta is None:
                return True
            enabled = meta.get("enabled")
        if enabled is None:
            return True
        return str(enabled).lower() in ("true", "1", "yes")
    
    def _get_skill_meta(self, name: str) -> dict:
        """Get horbot metadata for a skill (cached in frontmatter)."""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_skill_metadata(meta.get("metadata", ""))
    
    def get_always_skills(self) -> list[str]:
        """Get skills marked as always=true that meet requirements."""
        result = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_skill_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result
    
    def get_skill_metadata(self, name: str) -> dict | None:
        """
        Get metadata from a skill's frontmatter.
        
        Args:
            name: Skill name.
        
        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content:
            return None
        
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                # Simple YAML parsing
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip('"\'')
                return metadata
        
        return None
