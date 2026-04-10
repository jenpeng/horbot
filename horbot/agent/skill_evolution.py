"""Background skill evolution for turning reusable work into skills."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from horbot.agent.memory import MemoryStore
from horbot.agent.skill_package import validate_skill_content
from horbot.agent.skills import SkillsLoader, resolve_skills_dir
from horbot.providers.base import LLMProvider

_SAVE_SKILL_REVIEW_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_skill_review",
            "description": "Decide whether the completed work should become a reusable skill, and provide the skill draft when it should.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "create", "update"],
                        "description": "Skip when the work is too one-off, otherwise create or update an auto-generated skill.",
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "Lowercase reusable skill slug. Prefer concise nouns or verb-noun names.",
                    },
                    "description": {
                        "type": "string",
                        "description": "One-sentence summary of what the skill helps with.",
                    },
                    "body_markdown": {
                        "type": "string",
                        "description": "Markdown body for SKILL.md without YAML frontmatter. Include concrete reusable guidance, not task-specific notes.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Short explanation for why this should or should not become a skill.",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence from 0 to 1.",
                    },
                },
                "required": ["action", "reason"],
            },
        },
    }
]

_SKILL_NAME_SANITIZER = re.compile(r"[^a-z0-9_-]+")


@dataclass
class SkillEvolutionResult:
    action: str
    skill_name: str | None
    path: Path | None
    reason: str
    changed: bool


class SkillEvolutionEngine:
    """Review recent work and quietly distill it into reusable skills."""

    def __init__(
        self,
        *,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        agent_id: str | None = None,
        skills_dir: Path | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.agent_id = agent_id or "main"
        self.skills_dir = Path(skills_dir) if skills_dir is not None else resolve_skills_dir(workspace, agent_id=self.agent_id)
        self.review_log = workspace / ".skill_evolution" / "reviews.jsonl"
        self.memory_store = memory_store

    async def review_execution(
        self,
        execution_log: dict[str, Any],
        *,
        recent_messages: list[dict[str, Any]] | None = None,
        trigger: str = "turn_complete",
    ) -> SkillEvolutionResult | None:
        """Review a completed execution and optionally create/update a skill."""
        task_text = str(execution_log.get("task") or "").strip()
        result_text = str(execution_log.get("result") or "").strip()
        if not task_text or not result_text:
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "skipped",
                "reason": "missing_task_or_result",
            })
            return None

        skills_summary = SkillsLoader(
            workspace=self.workspace,
            agent_id=self.agent_id,
            skills_dir=self.skills_dir,
        ).build_skills_summary()
        conversation_excerpt = self._format_recent_messages(recent_messages or [])
        prompt = self._build_review_prompt(
            execution_log=execution_log,
            skills_summary=skills_summary,
            conversation_excerpt=conversation_excerpt,
        )

        try:
            response = await self.provider.chat(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You review completed work and decide whether it should become a reusable Horbot skill. "
                            "Be conservative: skip one-off work. When it is reusable, call save_skill_review."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_SKILL_REVIEW_TOOL,
                model=self.model,
            )
        except Exception as exc:
            logger.warning("Skill evolution review failed for {}: {}", self.agent_id, exc)
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "error",
                "reason": f"provider_error: {exc}",
            })
            return None

        if not response.has_tool_calls:
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "skipped",
                "reason": "no_tool_call",
            })
            return None

        args = response.tool_calls[0].arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}

        action = str(args.get("action") or "skip").strip().lower()
        reason = str(args.get("reason") or "no_reason").strip() or "no_reason"
        if action == "skip":
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "skipped",
                "reason": reason,
            })
            return SkillEvolutionResult(
                action="skip",
                skill_name=None,
                path=None,
                reason=reason,
                changed=False,
            )

        raw_name = str(args.get("skill_name") or "").strip()
        description = str(args.get("description") or "").strip()
        body_markdown = str(args.get("body_markdown") or "").strip()
        skill_name = self._normalize_skill_name(raw_name)
        if not skill_name or not description or not body_markdown:
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "skipped",
                "reason": "incomplete_skill_draft",
            })
            return None

        skill_path = self.skills_dir / skill_name / "SKILL.md"
        content = self._build_skill_content(skill_name, description, body_markdown)
        validation = validate_skill_content(content, expected_name=skill_name)
        if not validation["valid"]:
            logger.warning(
                "Skill evolution generated invalid skill {} for {}: {}",
                skill_name,
                self.agent_id,
                validation["issues"],
            )
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "invalid",
                "skill_name": skill_name,
                "reason": " ".join(validation["issues"]),
            })
            return None

        previous = skill_path.read_text(encoding="utf-8") if skill_path.exists() else None
        changed = previous != content
        if changed:
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(content, encoding="utf-8")
            logger.info(
                "Skill evolution {}d skill for {}: {}",
                "create" if previous is None else "update",
                self.agent_id,
                skill_name,
            )

        self._append_review_log({
            "timestamp": self._now_iso(),
            "trigger": trigger,
            "status": "saved" if changed else "unchanged",
            "action": action,
            "skill_name": skill_name,
            "path": str(skill_path),
            "reason": reason,
        })
        self._record_memory_feedback(
            action=action,
            skill_name=skill_name,
            description=description,
            reason=reason,
            changed=changed,
        )
        return SkillEvolutionResult(
            action=action,
            skill_name=skill_name,
            path=skill_path,
            reason=reason,
            changed=changed,
        )

    def _record_memory_feedback(
        self,
        *,
        action: str,
        skill_name: str,
        description: str,
        reason: str,
        changed: bool,
    ) -> None:
        if self.memory_store is None:
            return

        status_text = "updated" if action == "update" else "created"
        strategy = f"Skill `{skill_name}` now captures this reusable workflow: {description}"
        observation = (
            f"Background skill review {status_text} `{skill_name}` after a tool-backed task because the result was reusable."
            if changed else
            f"Background skill review confirmed `{skill_name}` is still the right reusable workflow."
        )

        self.memory_store.merge_reflection_entries(
            stable_observations=[observation],
            reusable_strategies=[strategy],
        )
        self.memory_store.append_history(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Skill evolution {status_text} `{skill_name}`. Reason: {reason}"
        )

    def _build_review_prompt(
        self,
        *,
        execution_log: dict[str, Any],
        skills_summary: str,
        conversation_excerpt: str,
    ) -> str:
        return f"""Review whether this completed work should become a reusable Horbot skill.

## Decision rules
- Only create or update a skill if the work produced a repeatable workflow, checklist, debugging playbook, or operating pattern that will help on future tasks.
- Skip if the work is one-off, project-specific, secret-sensitive, or too vague.
- Prefer updating an existing auto-generated skill instead of creating duplicates.
- If you save a skill, the markdown must be generic, reusable, concise, and must not include YAML frontmatter.
- Do not include secrets, tokens, private URLs, or absolute local file paths in the skill.

## Existing skills summary
{skills_summary or "(none)"}

## Execution log
{json.dumps(execution_log, ensure_ascii=False, indent=2)}

## Recent conversation excerpt
{conversation_excerpt or "(none)"}

## Skill body requirements
- Start with a title heading.
- Include a short "When to use" section.
- Include concrete steps, checks, and pitfalls.
- Keep the instructions actionable for future tasks.

Call save_skill_review exactly once."""

    def _format_recent_messages(self, messages: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for message in messages[-8:]:
            role = str(message.get("role") or "unknown").upper()
            content = message.get("content")
            if isinstance(content, list):
                content = json.dumps(content, ensure_ascii=False)
            content_text = str(content or "").strip()
            if not content_text:
                continue
            lines.append(f"[{role}] {content_text[:600]}")
        return "\n".join(lines)

    def _normalize_skill_name(self, value: str) -> str:
        slug = _SKILL_NAME_SANITIZER.sub("-", value.strip().lower()).strip("-_")
        if not slug:
            return ""
        if not slug.startswith("auto-"):
            slug = f"auto-{slug}"
        slug = slug[:64].rstrip("-_")
        if len(slug) < 2:
            return ""
        return slug

    def _build_skill_content(self, skill_name: str, description: str, body_markdown: str) -> str:
        metadata = json.dumps({"horbot": {"enabled": True}}, ensure_ascii=False, separators=(",", ":"))
        return (
            "---\n"
            f"name: {skill_name}\n"
            f"description: {description}\n"
            "generated_by: skill-evolution\n"
            f"generated_at: {self._now_iso()}\n"
            f"metadata: {metadata}\n"
            "---\n\n"
            f"{body_markdown.strip()}\n"
        )

    def _append_review_log(self, payload: dict[str, Any]) -> None:
        self.review_log.parent.mkdir(parents=True, exist_ok=True)
        with self.review_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
