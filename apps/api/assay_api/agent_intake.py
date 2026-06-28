"""Deterministic facts detected from a submitted agent definition markdown.

When a user submits an ``agent.md`` / ``AGENTS.md`` (the agent's system
prompt/persona/tools) as the candidate under test, this module extracts a small
set of facts from the raw markdown without any LLM call: the agent's title/role,
the tools it references, and a rough token estimate. These facts are stored on
the candidate's metadata and returned to the caller so the demo path stays fully
deterministic and offline.
"""
from __future__ import annotations

import re
from typing import Any

_MAX_TOOLS = 12
_FALLBACK_TITLE = "Untitled agent"

# `# Heading` (single leading hash, not `##`).
_H1_RE = re.compile(r"^\s{0,3}#\s+(.+?)\s*#*\s*$")
# `role: ...` / `name: ...` (optionally bolded / bulleted).
_FIELD_RE = re.compile(r"^\s*[-*]?\s*\**(role|name)\**\s*:\s*(.+?)\s*$", re.IGNORECASE)
# A `## Tools` / `### Tools` section header, or a `Tools:` lead-in.
_TOOLS_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s+tools\b.*$", re.IGNORECASE)
_TOOLS_INLINE_RE = re.compile(r"^\s*\**tools\**\s*:\s*(.*)$", re.IGNORECASE)
_ANY_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
# Plausible tool identifier: word-ish token, dotted/namespaced allowed.
_TOOL_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]{1,63}$")


def detect_agent_facts(markdown: str) -> dict[str, Any]:
    """Extract title/role, tools, tool_count, and token_estimate from markdown."""

    text = markdown or ""
    lines = text.splitlines()

    title = _detect_title(lines)
    tools = _detect_tools(lines)
    return {
        "title": title,
        "role": title,
        "tools": tools,
        "tool_count": len(tools),
        "token_estimate": len(text) // 4,
    }


def _detect_title(lines: list[str]) -> str:
    for line in lines:
        match = _H1_RE.match(line)
        if match:
            heading = match.group(1).strip()
            if heading:
                return heading
    for line in lines:
        match = _FIELD_RE.match(line)
        if match:
            value = match.group(2).strip().strip("`*").strip()
            if value:
                return value
    return _FALLBACK_TITLE


def _detect_tools(lines: list[str]) -> list[str]:
    tools: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        name = candidate.strip().strip("`*_").strip()
        if not name or not _TOOL_TOKEN_RE.match(name):
            return
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        tools.append(name)

    in_tools_section = False
    for line in lines:
        inline = _TOOLS_INLINE_RE.match(line)
        if inline is not None and not _ANY_HEADER_RE.match(line):
            # `Tools: a, b, c` lead-in on a single line.
            for piece in re.split(r"[,;]", inline.group(1)):
                for token in _BACKTICK_RE.findall(piece) or [piece]:
                    add(token)
            continue

        if _TOOLS_HEADER_RE.match(line):
            in_tools_section = True
            continue
        if _ANY_HEADER_RE.match(line):
            # Any other header ends the tools section.
            in_tools_section = False

        if in_tools_section:
            bullet = _BULLET_RE.match(line)
            if bullet:
                content = bullet.group(1)
                backticked = _BACKTICK_RE.findall(content)
                if backticked:
                    for token in backticked:
                        add(token)
                else:
                    # Take the first word-ish token of the bullet.
                    add(content.split()[0] if content.split() else "")

    # Fall back to / supplement with backticked tokens anywhere in the doc.
    if len(tools) < _MAX_TOOLS:
        for match in _BACKTICK_RE.findall("\n".join(lines)):
            if len(tools) >= _MAX_TOOLS:
                break
            add(match)

    return tools[:_MAX_TOOLS]
