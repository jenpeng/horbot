"""Shared helpers for agent bootstrap file detection, parsing, and repair."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

SETUP_PENDING_MARKER = "HORBOT_SETUP_PENDING"

DEFAULT_SOUL_TEMPLATE_SIGNATURES = ["# Soul", "# 灵魂"]
DEFAULT_USER_TEMPLATE_SIGNATURES = ["# User Profile", "# 用户档案"]

DEFAULT_USER_MARKERS = [
    "（你的名字）",
    "（你的时区",
    "(your name)",
    "(your timezone",
]

BOOTSTRAP_NOISE_PATTERNS = (
    SETUP_PENDING_MARKER,
    "完成首次引导后",
    "这是系统根据当前画像",
    "首轮对话时，优先帮助用户明确职责",
    "首次私聊待确认",
    "首次私聊优先确认",
    "推荐开场",
)

BOOTSTRAP_START_PATTERNS = (
    "开始完善配置",
    "完善配置",
    "开始配置",
    "开始首轮引导",
    "开始引导",
    "继续完善配置",
    "继续配置",
    "继续引导",
    "开始对你进行配置",
)

ROLE_PATTERNS = (
    re.compile(r"(?:我是|我是一名|我是一位|我的角色是|我的工作是)([^，,。；;\n]+)"),
)
NAME_PATTERNS = (
    re.compile(r"(?:称呼我|叫我|你可以叫我|喊我)([^，,。；;\n]+)"),
)
TIMEZONE_PATTERNS = (
    re.compile(r"(?:时区(?:是|为)?|timezone(?:\s+is)?)[：:\s]*([A-Za-z]+[+-]?\d{0,2}(?::\d{2})?|UTC[+-]?\d{1,2}|GMT[+-]?\d{1,2}|Asia/[A-Za-z_]+|北京时间|CST)", re.IGNORECASE),
)
LANGUAGE_PATTERNS = (
    re.compile(r"(?:语言|language|使用)(?:偏好|交流|沟通|回复)?(?:是|为|用)?[：:\s]*(中文|汉语|英文|英语|Chinese|English)", re.IGNORECASE),
)
STYLE_KEYWORDS = {
    "简洁": "回复风格：简洁明了",
    "详细": "回复风格：详细解释",
    "结构化": "回复风格：结构化输出",
    "先给结论": "回复习惯：先给结论再展开",
    "直接": "沟通方式：直接明确",
    "耐心": "沟通方式：耐心解释",
    "专业": "沟通方式：专业严谨",
}
TECH_LEVEL_KEYWORDS = {
    "初学者": "技术水平：初学者",
    "中级": "技术水平：中级",
    "专家": "技术水平：专家",
}


def strip_message_wrapper(content: str) -> str:
    """Remove stored <message from=...> wrappers from assistant content."""
    text = content or ""
    text = re.sub(r"<message\s+from=\"[^\"]*\"(?:\s+to=\"[^\"]*\")?>\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</message>\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def bootstrap_file_needs_setup(content: str, file_kind: str) -> bool:
    """Detect whether a single bootstrap file still looks like a template."""
    normalized_kind = (file_kind or "").strip().lower()
    text = (content or "").strip()
    if not text:
        return True

    if SETUP_PENDING_MARKER in text:
        return True

    lines = text.splitlines()
    first_line = lines[0].strip() if lines else ""
    second_line = lines[1].strip() if len(lines) > 1 else ""

    if normalized_kind == "user":
        for marker in DEFAULT_USER_MARKERS:
            if marker in text:
                return True
        if first_line in DEFAULT_USER_TEMPLATE_SIGNATURES and (
            "（你的名字）" in second_line or "(your name)" in second_line.lower()
        ):
            return True

    if normalized_kind == "soul":
        if first_line in DEFAULT_SOUL_TEMPLATE_SIGNATURES and "我是 horbot" in second_line:
            return True

    return False


def bootstrap_content_needs_setup(soul_content: str, user_content: str) -> bool:
    """Detect whether SOUL.md + USER.md are still in first-time-setup state."""
    return bootstrap_file_needs_setup(soul_content, "soul") or bootstrap_file_needs_setup(user_content, "user")


def remove_setup_pending_marker(content: str) -> str:
    """Drop the setup marker but preserve other content."""
    rendered = "\n".join(
        line for line in (content or "").splitlines()
        if SETUP_PENDING_MARKER not in line
    ).strip()
    return f"{rendered}\n" if rendered else ""


def normalize_bootstrap_file_content(content: str, file_kind: str) -> str:
    """Normalize explicit bootstrap writes before persisting."""
    normalized_kind = (file_kind or "").strip().lower()
    if normalized_kind not in {"soul", "user"}:
        return content or ""
    return remove_setup_pending_marker(content or "")


def parse_markdown_sections(content: str) -> tuple[str, dict[str, list[str]]]:
    title = ""
    sections: dict[str, list[str]] = {"__root__": []}
    current_section = "__root__"

    for raw_line in (content or "").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            heading = stripped[2:].strip()
            if not title:
                title = heading
            current_section = heading
            sections.setdefault(current_section, [])
            continue
        if stripped.startswith("## ") or stripped.startswith("### "):
            heading = stripped.lstrip("#").strip()
            current_section = heading
            sections.setdefault(current_section, [])
            continue
        sections.setdefault(current_section, []).append(stripped)

    return title, sections


def normalize_markdown_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        normalized = line.strip()
        if not normalized:
            continue
        normalized = normalized.lstrip("-*").strip()
        if normalized.startswith("[x]") or normalized.startswith("[X]"):
            normalized = normalized[3:].strip()
        elif normalized.startswith("[ ]"):
            continue
        if normalized.startswith("**") and "**：" in normalized:
            normalized = normalized.replace("**", "")
        if normalized.startswith("**") and "**:" in normalized:
            normalized = normalized.replace("**", "")
        normalized = normalized.replace("**", "").strip()
        if "：" in normalized:
            key, value = normalized.split("：", 1)
            normalized = f"{key.strip()}：{value.strip()}"
        elif ":" in normalized:
            key, value = normalized.split(":", 1)
            normalized = f"{key.strip()}：{value.strip()}"
        if normalized and normalized not in items:
            items.append(normalized)
    return items


def clean_summary_items(items: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        normalized = str(item or "").strip()
        if any(pattern in normalized for pattern in BOOTSTRAP_NOISE_PATTERNS):
            continue
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def merge_bootstrap_summaries(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge two bootstrap summary payloads while preserving ordering and deduplication."""
    merged = {
        "identity": clean_summary_items([*(base.get("identity") or []), *(incoming.get("identity") or [])]),
        "role_focus": clean_summary_items([*(base.get("role_focus") or []), *(incoming.get("role_focus") or [])]),
        "communication_style": clean_summary_items([*(base.get("communication_style") or []), *(incoming.get("communication_style") or [])]),
        "boundaries": clean_summary_items([*(base.get("boundaries") or []), *(incoming.get("boundaries") or [])]),
        "user_preferences": clean_summary_items([*(base.get("user_preferences") or []), *(incoming.get("user_preferences") or [])]),
        "source_titles": dict(base.get("source_titles") or incoming.get("source_titles") or {}),
    }
    merged["is_structured"] = any(bool(merged[key]) for key in ("identity", "role_focus", "communication_style", "boundaries", "user_preferences"))
    return merged


def _find_first(patterns: tuple[re.Pattern[str], ...], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip(" ：:，,。；;` ")
    return ""


def _normalize_role(raw: str) -> str:
    value = raw.strip()
    value = re.sub(r"(，|,)?需要.*$", "", value).strip()
    value = re.sub(r"(，|,)?希望.*$", "", value).strip()
    return value


def _normalize_language(raw: str) -> str:
    lowered = raw.lower()
    if lowered in {"中文", "汉语", "chinese"}:
        return "语言：中文"
    if lowered in {"英文", "英语", "english"}:
        return "语言：英文"
    return f"语言：{raw}"


def _extract_tasks(text: str) -> list[str]:
    candidates: list[str] = []
    for pattern in (
        r"(?:需要你|希望你|想让你|最常需要我帮忙的(?:\*\*3\s*类)?任务(?:是|有)?)([^。；;\n]+)",
        r"(?:帮我|协助我|支持我)([^。；;\n]+)",
    ):
        for match in re.finditer(pattern, text):
            candidates.append(match.group(1))

    tasks: list[str] = []
    for candidate in candidates:
        normalized = candidate
        normalized = normalized.replace("以及", "和").replace("与", "和").replace("并", "和")
        normalized = normalized.replace("聊天和编码工作", "聊天、编码工作")
        for token in re.split(r"[、,，/]|和", normalized):
            item = token.strip(" ：:，,。；;` ")
            item = re.sub(r"^(我|你|帮我|帮助我|和我|与我|一起|负责|做|进行)+", "", item).strip()
            item = re.sub(r"(方面|相关任务)$", "", item).strip() or item
            if len(item) < 2:
                continue
            if item in {"事情", "任务", "工作"}:
                continue
            if item not in tasks:
                tasks.append(item)
    return tasks[:5]


def extract_bootstrap_summary_from_messages(messages: list[dict[str, Any]], agent_name: str | None = None) -> dict[str, Any]:
    """Extract a lightweight bootstrap summary from onboarding chat history."""
    user_preferences: list[str] = []
    role_focus: list[str] = []
    communication_style: list[str] = []
    boundaries: list[str] = []
    identity: list[str] = []

    name = ""
    timezone = ""
    role = ""
    setup_started = False

    for message in messages:
        if message.get("role") != "user":
            continue

        text = strip_message_wrapper(str(message.get("content") or ""))
        if not text or text.startswith("[Runtime Context"):
            continue

        compact = re.sub(r"\s+", "", text)
        if any(pattern in compact for pattern in BOOTSTRAP_START_PATTERNS):
            setup_started = True
            continue

        if not name:
            name = _find_first(NAME_PATTERNS, text)
        if not timezone:
            timezone = _find_first(TIMEZONE_PATTERNS, text)
        if not role:
            role = _normalize_role(_find_first(ROLE_PATTERNS, text))

        language = _find_first(LANGUAGE_PATTERNS, text)
        if language:
            user_preferences.append(_normalize_language(language))

        for keyword, rendered in STYLE_KEYWORDS.items():
            if keyword in text and rendered not in communication_style:
                communication_style.append(rendered)

        for keyword, rendered in TECH_LEVEL_KEYWORDS.items():
            if keyword in text and rendered not in user_preferences:
                user_preferences.append(rendered)

        for task in _extract_tasks(text):
            rendered_task = f"优先支持：{task}"
            if rendered_task not in role_focus:
                role_focus.append(rendered_task)

        if "不要擅自" in text:
            boundaries.append("未经确认不要擅自执行高风险操作。")
        if "先确认" in text or "先和我确认" in text:
            boundaries.append("涉及关键改动前先与用户确认。")

    if name:
        user_preferences.insert(0, f"称呼：{name}")
    if timezone:
        user_preferences.append(f"时区：{timezone}")
    if role:
        user_preferences.append(f"角色：{role}")
        role_context = f"服务对象角色：{role}"
        if role_context not in role_focus:
            role_focus.insert(0, role_context)

    if role and role_focus:
        identity.append(f"定位：面向 {role} 场景提供协作与执行支持。")
    elif role:
        identity.append(f"定位：优先支持 {role} 相关场景。")

    merged = {
        "identity": clean_summary_items(identity),
        "role_focus": clean_summary_items(role_focus),
        "communication_style": clean_summary_items(communication_style),
        "boundaries": clean_summary_items(boundaries),
        "user_preferences": clean_summary_items(user_preferences),
        "source_titles": {
            "soul": agent_name or "SOUL.md",
            "user": "USER.md",
        },
    }
    signal_count = sum(len(merged[key]) for key in ("role_focus", "communication_style", "boundaries", "user_preferences"))
    merged["is_structured"] = signal_count > 0
    merged["_setup_started"] = setup_started
    merged["_ready"] = setup_started and signal_count >= 4 and bool(merged["user_preferences"]) and bool(merged["role_focus"])
    return merged


def truncate_summary_items(items: list[str], limit: int = 4) -> list[str]:
    return items[:limit]


def upsert_markdown_section(content: str, heading: str, items: list[str], *, level: int = 2) -> str:
    heading_prefix = "#" * level
    normalized_items = clean_summary_items(items)
    section_block = ""
    if normalized_items:
        rendered_items = "\n".join(f"- {item}" for item in normalized_items)
        section_block = f"{heading_prefix} {heading}\n\n{rendered_items}\n"

    lines = (content or "").splitlines()
    output: list[str] = []
    i = 0
    found = False
    target_heading = f"{heading_prefix} {heading}"
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == target_heading:
            found = True
            if section_block:
                output.extend(section_block.strip().splitlines())
            i += 1
            while i < len(lines):
                candidate = lines[i].strip()
                if candidate.startswith("#") and candidate.count("#") <= level:
                    break
                i += 1
            continue
        output.append(lines[i])
        i += 1

    rendered = "\n".join(output).strip()
    if not found and section_block:
        rendered = f"{rendered}\n\n{section_block.strip()}".strip()
    return rendered.strip() + "\n"


def build_bootstrap_summary(agent_name: str | None, soul_content: str, user_content: str) -> dict[str, Any]:
    soul_title, soul_sections = parse_markdown_sections(soul_content)
    user_title, user_sections = parse_markdown_sections(user_content)

    def pick_section(sections: dict[str, list[str]], *names: str) -> list[str]:
        for name in names:
            if name in sections:
                return normalize_markdown_items(sections[name])
        return []

    identity: list[str] = []
    if soul_title and soul_title not in {"灵魂", "Soul", "SOUL"}:
        identity.append(f"Agent 名称：{soul_title}")
    elif agent_name:
        identity.append(f"Agent 名称：{agent_name}")

    explicit_identity = pick_section(soul_sections, "身份定位")
    root_identity = normalize_markdown_items(soul_sections.get("__root__", []))
    if explicit_identity:
        identity.extend(explicit_identity[:3])
    elif root_identity:
        identity.extend(root_identity[:2])

    role_focus = (
        pick_section(soul_sections, "职责重点", "核心能力", "当前默认画像", "个性")
        + pick_section(user_sections, "当前默认协作基线")
    )
    communication_style = (
        pick_section(soul_sections, "沟通风格")
        + pick_section(user_sections, "沟通风格", "回复长度", "技术水平")
    )
    boundaries = (
        pick_section(soul_sections, "边界约束", "工作约束", "当前权限边界")
        + pick_section(user_sections, "特别说明", "备注")
    )
    user_preferences = (
        pick_section(user_sections, "用户偏好", "基本信息", "偏好设置")
        + pick_section(user_sections, "工作背景", "兴趣主题")
    )

    return {
        "identity": truncate_summary_items(identity, 3),
        "role_focus": truncate_summary_items(role_focus, 4),
        "communication_style": truncate_summary_items(communication_style, 5),
        "boundaries": truncate_summary_items(boundaries, 5),
        "user_preferences": truncate_summary_items(user_preferences, 5),
        "is_structured": bool(identity or role_focus or communication_style or boundaries or user_preferences),
        "source_titles": {
            "soul": soul_title or "SOUL.md",
            "user": user_title or "USER.md",
        },
    }


def _summary_agent_title(agent_name: str | None, summary: dict[str, Any]) -> str:
    for item in summary.get("identity", []):
        if item.startswith("Agent 名称："):
            name = item.split("：", 1)[1].strip()
            if name:
                return name
    source_title = (summary.get("source_titles") or {}).get("soul", "").strip()
    if source_title and source_title not in {"SOUL.md", "Soul", "灵魂"}:
        return source_title
    return (agent_name or "Horbot").strip() or "Horbot"


def render_bootstrap_file_from_summary(file_kind: str, agent_name: str | None, summary: dict[str, Any]) -> str:
    """Render a minimal finalized peer bootstrap file from the current summary."""
    normalized_kind = (file_kind or "").strip().lower()
    agent_title = _summary_agent_title(agent_name, summary)

    if normalized_kind == "soul":
        identity = [
            item for item in clean_summary_items(summary.get("identity", []))
            if not item.startswith("Agent 名称：")
        ] or [f"定位：作为 {agent_title} 的专属 AI 协作助手。"]
        role_focus = clean_summary_items(summary.get("role_focus", [])) or ["根据当前任务提供分析、执行与协作支持。"]
        communication_style = clean_summary_items(summary.get("communication_style", [])) or ["默认先给结论，再补充必要细节。"]
        boundaries = clean_summary_items(summary.get("boundaries", [])) or ["涉及高风险操作前先确认。"]
        return (
            f"# {agent_title}\n\n"
            f"我是 {agent_title}，当前已经完成基础协作画像初始化，后续可以继续在私聊中迭代。\n\n"
            f"## 身份定位\n\n" + "\n".join(f"- {item}" for item in identity) + "\n\n"
            f"## 职责重点\n\n" + "\n".join(f"- {item}" for item in role_focus) + "\n\n"
            f"## 沟通风格\n\n" + "\n".join(f"- {item}" for item in communication_style) + "\n\n"
            f"## 边界约束\n\n" + "\n".join(f"- {item}" for item in boundaries) + "\n"
        )

    preferences = clean_summary_items(summary.get("user_preferences", [])) or ["默认使用中文交流，具体偏好可继续补充。"]
    communication_style = clean_summary_items(summary.get("communication_style", [])) or ["回复默认先给结论，再补关键细节。"]
    collaboration = clean_summary_items(summary.get("role_focus", [])) or [f"当前先按 {agent_title} 的通用协作方式配合用户。"]
    notes = clean_summary_items(summary.get("boundaries", [])) or ["涉及高风险改动或不可逆操作前先征得用户确认。"]
    return (
        "# 用户档案\n\n"
        f"这份 USER.md 记录用户与 {agent_title} 的当前协作约定，后续可以继续在私聊中补充。\n\n"
        "## 用户偏好\n\n" + "\n".join(f"- {item}" for item in preferences) + "\n\n"
        "## 沟通风格\n\n" + "\n".join(f"- {item}" for item in communication_style) + "\n\n"
        "## 当前默认协作基线\n\n" + "\n".join(f"- {item}" for item in collaboration) + "\n\n"
        "## 备注\n\n" + "\n".join(f"- {item}" for item in notes) + "\n"
    )


def reconcile_bootstrap_files(
    workspace: Path,
    *,
    agent_name: str | None = None,
    updated_file: str | None = None,
) -> dict[str, str]:
    """Auto-complete the untouched bootstrap peer file after an explicit write."""
    soul_path = workspace / "SOUL.md"
    user_path = workspace / "USER.md"
    soul_content = soul_path.read_text(encoding="utf-8") if soul_path.exists() else ""
    user_content = user_path.read_text(encoding="utf-8") if user_path.exists() else ""

    normalized_updated = (updated_file or "").strip().upper()
    if normalized_updated not in {"SOUL.MD", "USER.MD"}:
        return {"soul": soul_content, "user": user_content}

    if normalized_updated == "SOUL.MD":
        updated_kind = "soul"
        peer_kind = "user"
        updated_content = soul_content
        peer_content = user_content
        peer_path = user_path
    else:
        updated_kind = "user"
        peer_kind = "soul"
        updated_content = user_content
        peer_content = soul_content
        peer_path = soul_path

    if bootstrap_file_needs_setup(updated_content, updated_kind):
        return {"soul": soul_content, "user": user_content}
    if not bootstrap_file_needs_setup(peer_content, peer_kind):
        return {"soul": soul_content, "user": user_content}

    summary = build_bootstrap_summary(agent_name, soul_content, user_content)
    generated_peer = render_bootstrap_file_from_summary(peer_kind, agent_name, summary)
    peer_path.parent.mkdir(parents=True, exist_ok=True)
    peer_path.write_text(generated_peer, encoding="utf-8")

    return {
        "soul": soul_path.read_text(encoding="utf-8") if soul_path.exists() else "",
        "user": user_path.read_text(encoding="utf-8") if user_path.exists() else "",
    }


def materialize_bootstrap_from_messages(
    workspace: Path,
    *,
    agent_name: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> bool:
    """Persist onboarding chat details into SOUL.md / USER.md when enough info is confirmed."""
    soul_path = workspace / "SOUL.md"
    user_path = workspace / "USER.md"
    soul_content = soul_path.read_text(encoding="utf-8") if soul_path.exists() else ""
    user_content = user_path.read_text(encoding="utf-8") if user_path.exists() else ""

    if not bootstrap_content_needs_setup(soul_content, user_content):
        return False

    extracted = extract_bootstrap_summary_from_messages(messages or [], agent_name)
    if not extracted.get("_ready"):
        return False

    base_summary = build_bootstrap_summary(agent_name, soul_content, user_content)
    merged_summary = merge_bootstrap_summaries(base_summary, extracted)

    soul_rendered = render_bootstrap_file_from_summary("soul", agent_name, merged_summary)
    user_rendered = render_bootstrap_file_from_summary("user", agent_name, merged_summary)

    soul_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(soul_rendered, encoding="utf-8")
    user_path.write_text(user_rendered, encoding="utf-8")
    return True
