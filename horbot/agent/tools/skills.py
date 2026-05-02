"""Managed skill persistence tools for agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from horbot.agent.skill_evolution import SkillEvolutionEngine
from horbot.agent.tools.base import Tool, ToolCategory, register_tool


@register_tool(category=ToolCategory.FILESYSTEM, tags=["skills", "memory", "self-improvement"])
class SaveSkillTool(Tool):
    """Persist a reusable workflow as an agent-scoped skill family."""

    def __init__(self, *, workspace: Path, agent_id: str | None = None):
        self._workspace = Path(workspace)
        self._agent_id = agent_id or "main"

    @property
    def name(self) -> str:
        return "save_skill"

    @property
    def description(self) -> str:
        return (
            "Create or update an auto-generated Horbot skill family in the current agent's managed skill store. "
            "Use this when the user explicitly asks you to summarize prior work as a reusable skill, or when a "
            "manual conversation identifies a reusable workflow that should be retained. Do not use write_file "
            "for skill persistence."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Reusable skill family slug or phrase. It will be normalized and prefixed with auto- when needed.",
                    "minLength": 2,
                },
                "description": {
                    "type": "string",
                    "description": "One-sentence summary of what this skill family helps with.",
                    "minLength": 8,
                },
                "reference_name": {
                    "type": "string",
                    "description": "Short slug or phrase for this specific technique under references/.",
                },
                "reference_title": {
                    "type": "string",
                    "description": "Human-readable title for the reference note.",
                },
                "trigger_cues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Concise cues that tell the agent when to use this skill family.",
                },
                "body_markdown": {
                    "type": "string",
                    "description": "Markdown body for the reference note. Include reusable steps, checks, pitfalls, and examples. Do not include secrets or absolute local paths.",
                    "minLength": 20,
                },
                "reason": {
                    "type": "string",
                    "description": "Short explanation for why this should be saved as a reusable skill.",
                },
            },
            "required": ["skill_name", "description", "body_markdown"],
        }

    async def execute(
        self,
        *,
        skill_name: str,
        description: str,
        body_markdown: str,
        reference_name: str = "",
        reference_title: str = "",
        trigger_cues: list[str] | None = None,
        reason: str = "User requested reusable skill distillation.",
        **_: Any,
    ) -> str:
        engine = SkillEvolutionEngine(
            workspace=self._workspace,
            agent_id=self._agent_id,
        )
        result = engine.save_skill_draft(
            skill_name=skill_name,
            description=description,
            reference_name=reference_name,
            reference_title=reference_title,
            trigger_cues=trigger_cues or [],
            body_markdown=body_markdown,
            reason=reason,
            action="update",
            trigger="manual_save_skill_tool",
        )
        if result is None or result.path is None or result.skill_name is None:
            return "Error: Could not save the skill draft. Ensure skill_name, description, and body_markdown are complete and reusable."

        status = "updated" if result.changed else "already up to date"
        return (
            f"Saved skill family `{result.skill_name}` ({status}). "
            f"Definition: {result.path}. Detailed technique stored under its references directory."
        )
