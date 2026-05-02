"""Background skill evolution for turning reusable work into skills."""

from __future__ import annotations

import json
import re
import shutil
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
                        "description": "Stable reusable skill family slug. Prefer a broad category that can hold multiple related techniques.",
                    },
                    "description": {
                        "type": "string",
                        "description": "One-sentence summary of what the merged skill family helps with.",
                    },
                    "reference_name": {
                        "type": "string",
                        "description": "Short slug-like name for the specific technique/reference to add under references/.",
                    },
                    "reference_title": {
                        "type": "string",
                        "description": "Human-readable title for the specific technique/reference file.",
                    },
                    "trigger_cues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Concise trigger cues that tell the agent when to use this merged skill family.",
                    },
                    "body_markdown": {
                        "type": "string",
                        "description": "Markdown body for the detailed reference file without YAML frontmatter. Include the concrete reusable technique, not task-specific notes.",
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
_REFERENCE_HEADING_RE = re.compile(r"^\s{0,3}#\s+(.+?)\s*$", re.MULTILINE)
_GENERIC_SKILL_NAME_TOKENS = {"auto", "skill", "skills", "workflow", "workflows", "checklist", "checklists", "guide", "guides", "playbook", "playbooks", "pattern", "patterns", "reference", "references"}
_DOMAIN_PREFIX_MIN_MEMBERS = 3
_DOMAIN_PREFIX_MIN_TOKENS = 2
_DOMAIN_PREFIX_MAX_TOKENS = 4


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
        provider: LLMProvider | None = None,
        model: str = "",
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
        if self.provider is None:
            logger.warning("Skill evolution review skipped for {} because no provider is configured", self.agent_id)
            return None

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

        base_skills_summary = SkillsLoader(
            workspace=self.workspace,
            agent_id=self.agent_id,
            skills_dir=self.skills_dir,
        ).build_skills_summary()
        generated_families_summary = self._build_generated_family_summary()
        skills_summary = "\n".join(
            part for part in [base_skills_summary, generated_families_summary] if part.strip()
        )
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
        reference_name = str(args.get("reference_name") or "").strip()
        reference_title = str(args.get("reference_title") or "").strip()
        trigger_cues_raw = args.get("trigger_cues")
        body_markdown = str(args.get("body_markdown") or "").strip()
        trigger_cues = [
            str(item).strip()
            for item in (trigger_cues_raw if isinstance(trigger_cues_raw, list) else [])
            if str(item).strip()
        ]
        skill_name = self._resolve_skill_family_name(raw_name, description)
        if not skill_name or not description or not body_markdown:
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "skipped",
                "reason": "incomplete_skill_draft",
            })
            return None

        skill_dir = self.skills_dir / skill_name
        skill_path = skill_dir / "SKILL.md"
        previous = skill_path.read_text(encoding="utf-8") if skill_path.exists() else None
        migrated = self._migrate_existing_generated_skill_to_references(skill_name, previous)
        consolidated_skill_names = self._consolidate_related_generated_skills(
            target_skill_name=skill_name,
            description=description,
        )
        reference_slug = self._normalize_reference_name(reference_name or reference_title or raw_name or skill_name)
        if not reference_slug:
            reference_slug = f"note-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        reference_path, reference_changed = self._write_reference_file(
            skill_name=skill_name,
            reference_slug=reference_slug,
            reference_title=reference_title,
            body_markdown=body_markdown,
        )
        content = self._build_skill_content(
            skill_name=skill_name,
            description=description,
            trigger_cues=trigger_cues,
        )
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

        skill_validation = validate_skill_content(content, expected_name=skill_name, root=skill_dir)
        if not skill_validation["valid"]:
            logger.warning(
                "Skill evolution generated invalid indexed skill {} for {}: {}",
                skill_name,
                self.agent_id,
                skill_validation["issues"],
            )
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "invalid",
                "skill_name": skill_name,
                "reason": " ".join(skill_validation["issues"]),
            })
            return None

        skill_changed = previous != content
        changed = migrated or bool(consolidated_skill_names) or reference_changed or skill_changed
        if skill_changed:
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(content, encoding="utf-8")
        if changed:
            logger.info(
                "Skill evolution {}d skill family for {}: {} (reference: {})",
                "create" if previous is None else "update",
                self.agent_id,
                skill_name,
                reference_path.name,
            )

        self._append_review_log({
            "timestamp": self._now_iso(),
            "trigger": trigger,
            "status": "saved" if changed else "unchanged",
            "action": action,
            "skill_name": skill_name,
            "path": str(skill_path),
            "reference_path": str(reference_path),
            "merged_skills": consolidated_skill_names,
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

    def save_skill_draft(
        self,
        *,
        skill_name: str,
        description: str,
        reference_name: str = "",
        reference_title: str = "",
        trigger_cues: list[str] | None = None,
        body_markdown: str,
        reason: str = "manual_skill_request",
        action: str = "update",
        trigger: str = "manual_request",
    ) -> SkillEvolutionResult | None:
        """Create or update a generated skill family from an already prepared draft."""
        raw_name = str(skill_name or "").strip()
        description = str(description or "").strip()
        body_markdown = str(body_markdown or "").strip()
        if not raw_name or not description or not body_markdown:
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "skipped",
                "reason": "incomplete_skill_draft",
            })
            return None

        normalized_action = "create" if str(action or "").strip().lower() == "create" else "update"
        trigger_cues = [
            str(item).strip()
            for item in (trigger_cues or [])
            if str(item).strip()
        ]
        resolved_skill_name = self._resolve_skill_family_name(raw_name, description)
        if not resolved_skill_name:
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "skipped",
                "reason": "invalid_skill_name",
            })
            return None

        skill_dir = self.skills_dir / resolved_skill_name
        skill_path = skill_dir / "SKILL.md"
        previous = skill_path.read_text(encoding="utf-8") if skill_path.exists() else None
        migrated = self._migrate_existing_generated_skill_to_references(resolved_skill_name, previous)
        consolidated_skill_names = self._consolidate_related_generated_skills(
            target_skill_name=resolved_skill_name,
            description=description,
        )

        reference_slug = self._normalize_reference_name(reference_name or reference_title or raw_name or resolved_skill_name)
        if not reference_slug:
            reference_slug = f"note-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        reference_path, reference_changed = self._write_reference_file(
            skill_name=resolved_skill_name,
            reference_slug=reference_slug,
            reference_title=reference_title,
            body_markdown=body_markdown,
        )
        content = self._build_skill_content(
            skill_name=resolved_skill_name,
            description=description,
            trigger_cues=trigger_cues,
        )
        validation = validate_skill_content(content, expected_name=resolved_skill_name, root=skill_dir)
        if not validation["valid"]:
            logger.warning(
                "Manual skill draft produced invalid skill {} for {}: {}",
                resolved_skill_name,
                self.agent_id,
                validation["issues"],
            )
            self._append_review_log({
                "timestamp": self._now_iso(),
                "trigger": trigger,
                "status": "invalid",
                "skill_name": resolved_skill_name,
                "reason": " ".join(validation["issues"]),
            })
            return None

        skill_changed = previous != content
        changed = migrated or bool(consolidated_skill_names) or reference_changed or skill_changed
        if skill_changed:
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(content, encoding="utf-8")
        if changed:
            logger.info(
                "Manual skill draft {}d skill family for {}: {} (reference: {})",
                "create" if previous is None else "update",
                self.agent_id,
                resolved_skill_name,
                reference_path.name,
            )

        self._append_review_log({
            "timestamp": self._now_iso(),
            "trigger": trigger,
            "status": "saved" if changed else "unchanged",
            "action": normalized_action,
            "skill_name": resolved_skill_name,
            "path": str(skill_path),
            "reference_path": str(reference_path),
            "merged_skills": consolidated_skill_names,
            "reason": reason,
            "source": "manual_agent_tool",
        })
        self._record_memory_feedback(
            action=normalized_action,
            skill_name=resolved_skill_name,
            description=description,
            reason=reason,
            changed=changed,
        )
        return SkillEvolutionResult(
            action=normalized_action,
            skill_name=resolved_skill_name,
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
- Prefer updating an existing auto-generated skill family instead of creating duplicates.
- Use a broad skill family name when multiple related techniques belong together.
- Put technique-specific details in a reference file under `references/`; keep `SKILL.md` lean and navigational.
- If you save a skill, the markdown must be generic, reusable, concise, and must not include YAML frontmatter.
- Do not include secrets, tokens, private URLs, or absolute local file paths in the skill.

## Existing skills summary
{skills_summary or "(none)"}

## Execution log
{json.dumps(execution_log, ensure_ascii=False, indent=2)}

## Recent conversation excerpt
{conversation_excerpt or "(none)"}

## Skill body requirements
- The reference body must start with a title heading.
- Include a short "When to use" section.
- Include concrete steps, checks, and pitfalls.
- Keep the instructions actionable for future tasks.
- Return trigger cues for the merged skill family when useful.

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

    def _normalize_reference_name(self, value: str) -> str:
        slug = _SKILL_NAME_SANITIZER.sub("-", value.strip().lower()).strip("-_")
        slug = slug[:64].rstrip("-_")
        return slug

    def _skill_name_tokens(self, skill_name: str) -> list[str]:
        normalized = skill_name.replace("auto-", "", 1)
        return [
            token
            for token in re.split(r"[^a-z0-9]+", normalized.lower())
            if len(token) >= 2
        ]

    def _resolve_skill_family_name(self, raw_name: str, description: str) -> str:
        requested_name = self._normalize_skill_name(raw_name)
        if not requested_name:
            return ""

        generated_skills = self._list_generated_skill_families()
        if requested_name in {item["name"] for item in generated_skills}:
            return requested_name

        if len(self._skill_similarity_tokens(f"{requested_name} {description}")) < 2:
            return requested_name

        best_name = requested_name
        best_score = 0.0
        strong_candidates = 0
        for candidate in generated_skills:
            score = self._family_similarity_score(
                f"{requested_name} {description}",
                f"{candidate['name']} {candidate['description']}",
            )
            if score >= 0.34:
                strong_candidates += 1
            if score > best_score:
                best_score = score
                best_name = candidate["name"]

        if strong_candidates > 1:
            return requested_name
        return best_name if best_score >= 0.34 else requested_name

    def _skill_similarity_tokens(self, value: str) -> set[str]:
        tokens = {
            token
            for token in re.split(r"[^a-z0-9]+", value.lower())
            if len(token) >= 3 and token not in _GENERIC_SKILL_NAME_TOKENS
        }
        return tokens

    def _family_similarity_score(self, left: str, right: str) -> float:
        left_tokens = self._skill_similarity_tokens(left)
        right_tokens = self._skill_similarity_tokens(right)
        if len(left_tokens) < 2 or len(right_tokens) < 2:
            return 0.0
        overlap = left_tokens & right_tokens
        union = left_tokens | right_tokens
        if len(overlap) < 2 or not union:
            return 0.0
        return len(overlap) / len(union)

    def _candidate_domain_prefixes(self, skill_name: str) -> list[tuple[str, ...]]:
        tokens = self._skill_name_tokens(skill_name)
        upper = min(_DOMAIN_PREFIX_MAX_TOKENS, len(tokens) - 1)
        if upper < _DOMAIN_PREFIX_MIN_TOKENS:
            return []
        return [tuple(tokens[:size]) for size in range(_DOMAIN_PREFIX_MIN_TOKENS, upper + 1)]

    def _build_domain_family_description(
        self,
        prefix_tokens: tuple[str, ...],
        cluster: list[dict[str, str]],
    ) -> str:
        prefix_label = " ".join(prefix_tokens).strip()
        if not prefix_label:
            return "Reusable techniques, troubleshooting workflows, and reference notes for related recurring tasks."

        topical_terms: list[str] = []
        common_prefix = set(prefix_tokens)
        for item in cluster:
            for token in sorted(self._skill_similarity_tokens(f"{item['name']} {item['description']}")):
                if token in common_prefix or token in topical_terms:
                    continue
                topical_terms.append(token)
                if len(topical_terms) >= 3:
                    break
            if len(topical_terms) >= 3:
                break

        if topical_terms:
            return (
                f"Reusable techniques, troubleshooting workflows, and reference notes for {prefix_label} tasks, "
                f"including {', '.join(topical_terms)}."
            )

        return f"Reusable techniques, troubleshooting workflows, and reference notes for {prefix_label} tasks."

    def _plan_domain_family_clusters(
        self,
        families: list[dict[str, str]],
        *,
        processed: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        prefix_members: dict[tuple[str, ...], list[dict[str, str]]] = {}
        blocked = processed or set()

        for family in families:
            if family["name"] in blocked:
                continue
            for prefix in self._candidate_domain_prefixes(family["name"]):
                prefix_members.setdefault(prefix, []).append(family)

        ranked_prefixes = sorted(
            (
                (prefix, members)
                for prefix, members in prefix_members.items()
                if len(members) >= _DOMAIN_PREFIX_MIN_MEMBERS
            ),
            key=lambda item: (-len(item[1]), len(item[0]), item[0]),
        )

        claimed: set[str] = set(blocked)
        clusters: list[dict[str, Any]] = []
        for prefix, members in ranked_prefixes:
            available = [
                member
                for member in members
                if member["name"] not in claimed and (self.skills_dir / member["name"]).exists()
            ]
            if len(available) < _DOMAIN_PREFIX_MIN_MEMBERS:
                continue
            clusters.append({
                "prefix_tokens": prefix,
                "target_name": f"auto-{'-'.join(prefix)}",
                "description": self._build_domain_family_description(prefix, available),
                "members": available,
            })
            claimed.update(member["name"] for member in available)

        return clusters

    def _write_generated_family(
        self,
        *,
        target_name: str,
        description: str,
        merged_names: list[str],
    ) -> dict[str, Any] | None:
        target_path = self.skills_dir / target_name / "SKILL.md"
        previous = target_path.read_text(encoding="utf-8") if target_path.exists() else None
        migrated = self._migrate_existing_generated_skill_to_references(target_name, previous)
        content = self._build_skill_content(
            skill_name=target_name,
            description=description or target_name,
            trigger_cues=[],
        )
        validation = validate_skill_content(content, expected_name=target_name, root=self.skills_dir / target_name)
        if not validation["valid"]:
            logger.warning(
                "Manual generated-skill consolidation produced invalid family {} for {}: {}",
                target_name,
                self.agent_id,
                validation["issues"],
            )
            return None

        changed = migrated or bool(merged_names) or previous != content
        if previous != content:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

        if not changed:
            return None

        return {
            "skill_name": target_name,
            "merged_skills": merged_names,
        }

    def _extract_frontmatter(self, content: str) -> tuple[dict[str, str], str]:
        if not content.startswith("---"):
            return {}, content

        match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
        if not match:
            return {}, content

        metadata: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'")
        return metadata, match.group(2).strip()

    def _list_generated_skill_families(self) -> list[dict[str, str]]:
        if not self.skills_dir.exists():
            return []

        results: list[dict[str, str]] = []
        for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
            content = skill_file.read_text(encoding="utf-8")
            frontmatter, _ = self._extract_frontmatter(content)
            if frontmatter.get("generated_by") != "skill-evolution":
                continue
            results.append({
                "name": skill_file.parent.name,
                "description": frontmatter.get("description", "").strip(),
                "path": str(skill_file.parent),
            })
        return results

    def _build_generated_family_summary(self) -> str:
        families = []
        if not self.skills_dir.exists():
            return ""

        for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
            content = skill_file.read_text(encoding="utf-8")
            frontmatter, _ = self._extract_frontmatter(content)
            if frontmatter.get("generated_by") != "skill-evolution":
                continue
            references = sorted(
                path.stem
                for path in (skill_file.parent / "references").glob("*.md")
            ) if (skill_file.parent / "references").exists() else []
            families.append(
                f"- {skill_file.parent.name}: {frontmatter.get('description', '').strip() or 'No description'}"
                + (f" | references={', '.join(references[:6])}" if references else " | references=(none)")
            )

        if not families:
            return ""

        return "## Existing auto-generated skill families\n" + "\n".join(families)

    def _infer_reference_title(self, body_markdown: str, fallback: str) -> str:
        match = _REFERENCE_HEADING_RE.search(body_markdown)
        if match:
            return match.group(1).strip()
        return fallback.replace("-", " ").replace("_", " ").strip().title() or "Reference Note"

    def _build_reference_content(
        self,
        *,
        reference_title: str,
        body_markdown: str,
    ) -> str:
        body = body_markdown.strip()
        if not _REFERENCE_HEADING_RE.search(body):
            body = f"# {reference_title}\n\n{body}"
        return f"{body.rstrip()}\n"

    def _write_reference_file(
        self,
        *,
        skill_name: str,
        reference_slug: str,
        reference_title: str,
        body_markdown: str,
    ) -> tuple[Path, bool]:
        skill_dir = self.skills_dir / skill_name
        references_dir = skill_dir / "references"
        references_dir.mkdir(parents=True, exist_ok=True)
        resolved_title = reference_title.strip() or self._infer_reference_title(body_markdown, reference_slug)
        content = self._build_reference_content(reference_title=resolved_title, body_markdown=body_markdown)
        path = references_dir / f"{reference_slug}.md"
        previous = path.read_text(encoding="utf-8") if path.exists() else None
        changed = previous != content
        if changed:
            path.write_text(content, encoding="utf-8")
        return path, changed

    def _ensure_unique_reference_slug(self, skill_name: str, reference_slug: str) -> str:
        slug = self._normalize_reference_name(reference_slug) or "reference"
        references_dir = self.skills_dir / skill_name / "references"
        candidate = slug
        suffix = 2
        while (references_dir / f"{candidate}.md").exists():
            candidate = f"{slug}-{suffix}"
            suffix += 1
        return candidate

    def _migrate_existing_generated_skill_to_references(self, skill_name: str, previous: str | None) -> bool:
        if not previous:
            return False

        skill_dir = self.skills_dir / skill_name
        references_dir = skill_dir / "references"
        existing_refs = list(references_dir.glob("*.md")) if references_dir.exists() else []
        if existing_refs:
            return False

        frontmatter, body = self._extract_frontmatter(previous)
        if frontmatter.get("generated_by") != "skill-evolution":
            return False

        if not body.strip():
            return False

        legacy_slug = self._normalize_reference_name(skill_name.replace("auto-", "", 1) or "overview") or "overview"
        _, changed = self._write_reference_file(
            skill_name=skill_name,
            reference_slug=legacy_slug,
            reference_title=self._infer_reference_title(body, legacy_slug),
            body_markdown=body,
        )
        return changed

    def _absorb_generated_skill_into_family(self, source_skill_name: str, target_skill_name: str) -> bool:
        if source_skill_name == target_skill_name:
            return False

        source_dir = self.skills_dir / source_skill_name
        source_skill_file = source_dir / "SKILL.md"
        if not source_skill_file.exists():
            return False

        source_content = source_skill_file.read_text(encoding="utf-8")
        frontmatter, body = self._extract_frontmatter(source_content)
        if frontmatter.get("generated_by") != "skill-evolution":
            return False

        changed = False
        source_references_dir = source_dir / "references"
        if source_references_dir.exists():
            for ref_file in sorted(source_references_dir.glob("*.md")):
                ref_content = ref_file.read_text(encoding="utf-8")
                unique_slug = self._ensure_unique_reference_slug(target_skill_name, ref_file.stem)
                _, ref_changed = self._write_reference_file(
                    skill_name=target_skill_name,
                    reference_slug=unique_slug,
                    reference_title=self._infer_reference_title(ref_content, unique_slug),
                    body_markdown=ref_content,
                )
                changed = changed or ref_changed

        if body.strip():
            legacy_slug_base = self._normalize_reference_name(source_skill_name.replace("auto-", "", 1)) or "reference"
            unique_slug = self._ensure_unique_reference_slug(target_skill_name, legacy_slug_base)
            _, ref_changed = self._write_reference_file(
                skill_name=target_skill_name,
                reference_slug=unique_slug,
                reference_title=self._infer_reference_title(body, unique_slug),
                body_markdown=body,
            )
            changed = changed or ref_changed

        shutil.rmtree(source_dir, ignore_errors=True)
        return True

    def _consolidate_related_generated_skills(
        self,
        *,
        target_skill_name: str,
        description: str,
    ) -> list[str]:
        generated_skills = self._list_generated_skill_families()
        merged_names: list[str] = []
        target_descriptor = f"{target_skill_name} {description}"

        for candidate in generated_skills:
            candidate_name = candidate["name"]
            if candidate_name == target_skill_name:
                continue
            score = self._family_similarity_score(
                target_descriptor,
                f"{candidate_name} {candidate['description']}",
            )
            if score < 0.34:
                continue
            if self._absorb_generated_skill_into_family(candidate_name, target_skill_name):
                merged_names.append(candidate_name)

        return merged_names

    def _choose_manual_family_target(self, families: list[dict[str, str]]) -> str:
        ranked = sorted(
            families,
            key=lambda item: (
                len(self._skill_similarity_tokens(f"{item['name']} {item['description']}")),
                len(item["name"]),
                item["name"],
            ),
        )
        return ranked[0]["name"]

    def consolidate_generated_skills(self) -> dict[str, Any]:
        generated_skills = self._list_generated_skill_families()
        if not generated_skills:
            return {
                "family_count_before": 0,
                "family_count_after": 0,
                "merged_skill_count": 0,
                "updated_families": [],
            }

        family_count_before = len(generated_skills)
        updated_families: list[dict[str, Any]] = []
        processed: set[str] = set()

        domain_clusters = self._plan_domain_family_clusters(generated_skills)
        for cluster in domain_clusters:
            target_name = cluster["target_name"]
            merged_names: list[str] = []
            for member in cluster["members"]:
                candidate_name = member["name"]
                if candidate_name == target_name:
                    continue
                if self._absorb_generated_skill_into_family(candidate_name, target_name):
                    merged_names.append(candidate_name)
                    processed.add(candidate_name)
            written = self._write_generated_family(
                target_name=target_name,
                description=cluster["description"],
                merged_names=merged_names,
            )
            if written:
                updated_families.append(written)
            processed.add(target_name)

        generated_skills = self._list_generated_skill_families()
        for family in generated_skills:
            family_name = family["name"]
            family_dir = self.skills_dir / family_name
            if family_name in processed or not family_dir.exists():
                continue

            cluster = [family]
            for candidate in generated_skills:
                candidate_name = candidate["name"]
                candidate_dir = self.skills_dir / candidate_name
                if candidate_name == family_name or candidate_name in processed or not candidate_dir.exists():
                    continue
                score = self._family_similarity_score(
                    f"{family_name} {family['description']}",
                    f"{candidate_name} {candidate['description']}",
                )
                if score >= 0.34:
                    cluster.append(candidate)

            if len(cluster) == 1:
                continue

            target_name = self._choose_manual_family_target(cluster)
            target_entry = next(item for item in cluster if item["name"] == target_name)

            merged_names: list[str] = []
            for candidate in cluster:
                candidate_name = candidate["name"]
                if candidate_name == target_name:
                    continue
                if self._absorb_generated_skill_into_family(candidate_name, target_name):
                    merged_names.append(candidate_name)
                    processed.add(candidate_name)

            written = self._write_generated_family(
                target_name=target_name,
                description=target_entry["description"] or target_name,
                merged_names=merged_names,
            )
            if written:
                updated_families.append(written)
            processed.add(target_name)

        family_count_after = len(self._list_generated_skill_families())
        return {
            "family_count_before": family_count_before,
            "family_count_after": family_count_after,
            "merged_skill_count": sum(len(item["merged_skills"]) for item in updated_families),
            "updated_families": updated_families,
        }

    def _collect_reference_entries(self, skill_name: str) -> list[dict[str, str]]:
        skill_dir = self.skills_dir / skill_name
        references_dir = skill_dir / "references"
        if not references_dir.exists():
            return []

        entries: list[dict[str, str]] = []
        for path in sorted(references_dir.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            title = self._infer_reference_title(content, path.stem)
            summary = ""
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                summary = stripped
                break
            entries.append({
                "title": title,
                "path": f"references/{path.name}",
                "summary": summary[:180],
            })
        return entries

    def _build_skill_heading(self, skill_name: str, description: str) -> str:
        heading = skill_name.replace("auto-", "", 1).replace("-", " ").replace("_", " ").strip().title()
        if heading:
            return heading
        return description.strip() or "Auto Generated Skill"

    def _build_skill_content(self, *, skill_name: str, description: str, trigger_cues: list[str]) -> str:
        metadata = json.dumps({"horbot": {"enabled": True}}, ensure_ascii=False, separators=(",", ":"))
        references = self._collect_reference_entries(skill_name)
        heading = self._build_skill_heading(skill_name, description)
        normalized_cues = list(dict.fromkeys([cue.strip() for cue in trigger_cues if cue.strip()]))[:8]
        if not normalized_cues:
            normalized_cues = [
                "A repeated task or failure pattern matches this skill family.",
                "The user asks for a reusable checklist, playbook, or troubleshooting workflow.",
                "You need detailed steps from one of the reference notes before acting.",
            ]

        reference_lines = [
            f"- [{item['title']}]({item['path']})"
            + (f" - {item['summary']}" if item["summary"] else "")
            for item in references
        ] or ["- No reference notes yet."]

        skill_body = "\n".join([
            f"# {heading}",
            "",
            description.strip(),
            "",
            "## When To Use",
            "- Use this skill family when the task matches one of the trigger cues below and you need a proven reusable workflow.",
            "- Read the relevant reference note before executing or advising on the detailed steps.",
            "",
            "## Trigger Cues",
            *[f"- {cue}" for cue in normalized_cues],
            "",
            "## How To Navigate",
            "1. Scan the reference list below to find the closest technique.",
            "2. Open the matching file under `references/`.",
            "3. Apply or adapt that technique, and avoid mixing unrelated references.",
            "",
            "## Reference Library",
            *reference_lines,
        ])
        return (
            "---\n"
            f"name: {skill_name}\n"
            f"description: {description}\n"
            "generated_by: skill-evolution\n"
            f"generated_at: {self._now_iso()}\n"
            f"metadata: {metadata}\n"
            "---\n\n"
            f"{skill_body.rstrip()}\n"
        )

    def _append_review_log(self, payload: dict[str, Any]) -> None:
        self.review_log.parent.mkdir(parents=True, exist_ok=True)
        with self.review_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
