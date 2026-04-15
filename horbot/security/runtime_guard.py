"""Runtime security guards for user input, tool output, and durable writes."""

from __future__ import annotations

from dataclasses import dataclass, field
import re


_REDACTED = "********"
_SECRET_INLINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"authorization\s*:\s*bearer\s+[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password)\b\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
)
_TOOL_RESULT_BLOCK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction override content",
        re.compile(
            r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above|system|developer)\s+instructions",
            re.IGNORECASE,
        ),
    ),
    (
        "system prompt extraction content",
        re.compile(
            r"(?:reveal|show|print|dump|expose).{0,48}(?:system prompt|developer prompt|hidden prompt|secret|token|api[_ -]?key)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "command execution instructions",
        re.compile(
            r"(?:execute|run|launch|copy and run).{0,36}(?:curl|wget|bash|sh|python|powershell|base64)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "embedded credentials",
        re.compile(
            r"authorization\s*:\s*bearer\s+[^\s,;]+|\bsk-[A-Za-z0-9_\-]{8,}\b|\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password)\b\s*[:=]\s*[^\s,;]+",
            re.IGNORECASE,
        ),
    ),
)
_MEMORY_WRITE_BLOCK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction override memory",
        re.compile(
            r"(?:always|must|from now on).{0,40}(?:ignore|override).{0,40}(?:user|system|developer|instruction)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "prompt extraction memory",
        re.compile(
            r"(?:reveal|show|print|dump|expose).{0,48}(?:system prompt|developer prompt|hidden prompt|secret|token|api[_ -]?key)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "command payload memory",
        re.compile(
            r"(?:run|execute|launch).{0,36}(?:curl|wget|bash|sh|python|powershell|base64)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "embedded credentials memory",
        re.compile(
            r"authorization\s*:\s*bearer\s+[^\s,;]+|\bsk-[A-Za-z0-9_\-]{8,}\b|\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password)\b\s*[:=]\s*[^\s,;]+",
            re.IGNORECASE,
        ),
    ),
)
_BOOTSTRAP_WRITE_BLOCK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction override bootstrap",
        re.compile(
            r"(?:always|must|from now on|始终|必须|以后都要).{0,40}(?:ignore|override|忽略|覆盖).{0,40}(?:user|system|developer|instruction|用户|系统|开发者|指令)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "prompt extraction bootstrap",
        re.compile(
            r"(?:reveal|show|print|dump|expose|显示|泄露|输出).{0,48}(?:system prompt|developer prompt|hidden prompt|系统提示词|系统 prompt|开发者提示词|secret|token|api[_ -]?key)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "command payload bootstrap",
        re.compile(
            r"(?:run|execute|launch|copy and run|执行|运行).{0,36}(?:curl|wget|bash|sh|python|powershell|base64)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "embedded credentials bootstrap",
        re.compile(
            r"authorization\s*:\s*bearer\s+[^\s,;]+|\bsk-[A-Za-z0-9_\-]{8,}\b|\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|password|口令|密钥|令牌)\b\s*[:=：]\s*[^\s,;]+",
            re.IGNORECASE,
        ),
    ),
)
_USER_INPUT_BLOCK_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction override intent",
        re.compile(
            r"(?:ignore|bypass|forget|skip|忽略|绕过|无视).{0,40}(?:system|developer|safety|guard|policy|instruction|系统|开发者|安全|守卫|策略|指令)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "prompt extraction intent",
        re.compile(
            r"(?:reveal|show|print|dump|expose|告诉我|显示|输出|泄露).{0,56}(?:system prompt|developer prompt|hidden prompt|系统提示词|开发者提示词|隐藏提示词)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "secret exfiltration intent",
        re.compile(
            r"(?:reveal|show|print|dump|expose|export|发送给我|发给我|显示|输出|泄露).{0,56}(?:api[_ -]?key|token|password|secret|credential|密钥|令牌|口令|凭证)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


@dataclass
class GuardDecision:
    """Decision returned by a runtime guard inspection."""

    blocked: bool
    output: str
    reasons: list[str] = field(default_factory=list)


def _redact_inline_secrets(text: str) -> str:
    redacted = text
    for pattern in _SECRET_INLINE_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted


def _collect_matches(text: str, rules: tuple[tuple[str, re.Pattern[str]], ...]) -> list[str]:
    reasons: list[str] = []
    for label, pattern in rules:
        if pattern.search(text):
            reasons.append(label)
    return reasons


def inspect_tool_result(tool_name: str, output: str) -> GuardDecision:
    """Inspect tool output before it is persisted or sent back into model context."""
    if not isinstance(output, str) or not output.strip():
        return GuardDecision(blocked=False, output=output)

    reasons = _collect_matches(output, _TOOL_RESULT_BLOCK_RULES)
    if reasons:
        return GuardDecision(
            blocked=True,
            output=(
                f"[Security notice] Tool output from '{tool_name}' was withheld because it appears "
                f"to contain unsafe instructions or sensitive data ({', '.join(reasons[:2])})."
            ),
            reasons=reasons,
        )

    redacted = _redact_inline_secrets(output)
    return GuardDecision(blocked=False, output=redacted, reasons=["secret_redacted"] if redacted != output else [])


def inspect_memory_write(memory_kind: str, content: str) -> GuardDecision:
    """Inspect memory content before writing durable state to disk."""
    if not isinstance(content, str) or not content.strip():
        return GuardDecision(blocked=False, output=content)

    reasons = _collect_matches(content, _MEMORY_WRITE_BLOCK_RULES)
    if reasons:
        return GuardDecision(
            blocked=True,
            output="",
            reasons=reasons,
        )

    redacted = _redact_inline_secrets(content)
    return GuardDecision(blocked=False, output=redacted, reasons=["secret_redacted"] if redacted != content else [])


def inspect_user_input(content: str) -> GuardDecision:
    """Inspect user input before it enters the model/tool execution pipeline."""
    if not isinstance(content, str) or not content.strip():
        return GuardDecision(blocked=False, output=content)

    reasons = _collect_matches(content, _USER_INPUT_BLOCK_RULES)
    if reasons:
        return GuardDecision(blocked=True, output="", reasons=reasons)

    return GuardDecision(blocked=False, output=content)


def inspect_bootstrap_write(file_kind: str, content: str) -> GuardDecision:
    """Inspect AGENTS.md / SOUL.md / USER.md content before persisting bootstrap state."""
    if not isinstance(content, str) or not content.strip():
        return GuardDecision(blocked=False, output=content)

    reasons = _collect_matches(content, _BOOTSTRAP_WRITE_BLOCK_RULES)
    if reasons:
        return GuardDecision(
            blocked=True,
            output="",
            reasons=reasons,
        )

    redacted = _redact_inline_secrets(content)
    return GuardDecision(blocked=False, output=redacted, reasons=["secret_redacted"] if redacted != content else [])
