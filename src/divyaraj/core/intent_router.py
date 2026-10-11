"""Small deterministic router for requests with reliable local tool matches."""

import re
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolIntent:
    """A clear user intent mapped to a tool and its arguments."""

    tool_name: str
    arguments: dict[str, object]
    clarification: str | None = None


_TIME_OR_DATE_PATTERNS = (
    r"\bwhat(?:'s| is) the time\b",
    r"\bwhat time is it\b",
    r"\btime is it\b",
    r"\bcurrent time\b",
    r"\btell me the time\b",
    r"\btime now\b",
    r"\btoday(?:'s)? date\b",
    r"\bcurrent date\b",
    r"\bwhat date is it\b",
    r"\bdate today\b",
    r"\bwhat day is it\b",
)
_LIST_NOTE_PATTERNS = (
    r"\bmy notes\b",
    r"\blist (?:all )?(?:my )?notes\b",
    r"\bshow (?:all )?(?:my )?notes\b",
    r"\bwhat notes do i have\b",
)
_CREATE_NOTE_PREFIX = re.compile(
    r"^\s*(?:make|add|create) (?:me )?a note\b\s*[:,-]?\s*",
    re.IGNORECASE,
)


def route_intent(
    text: str,
    allowed_apps: Mapping[str, str] | None = None,
) -> ToolIntent | None:
    """Return a deterministic tool intent for clearly phrased requests."""
    normalized = text.casefold().replace("’", "'")
    if any(re.search(pattern, normalized) for pattern in _TIME_OR_DATE_PATTERNS):
        return ToolIntent("get_time", {})

    if any(re.search(pattern, normalized) for pattern in _LIST_NOTE_PATTERNS):
        return ToolIntent("list_notes", {})

    note_match = _CREATE_NOTE_PREFIX.match(text)
    if note_match:
        content = text[note_match.end() :].strip()
        if not content:
            return ToolIntent(
                "create_note",
                {},
                clarification="What would you like me to note?",
            )
        return ToolIntent("create_note", {"title": "Note", "content": content})

    search_match = re.match(
        r"^\s*(?:search|look up|find)\s+(?:the\s+)?(?:web|online)\s+(?:for\s+)?(.+)",
        text,
        re.IGNORECASE,
    )
    if search_match:
        return ToolIntent("web_search", {"query": search_match.group(1).strip()})

    if allowed_apps:
        app_names = "|".join(
            re.escape(app) for app in sorted(allowed_apps, key=len, reverse=True)
        )
        app_match = re.search(
            rf"\bopen\s+(?:the\s+)?({app_names})\b",
            text,
            re.IGNORECASE,
        )
        if app_match:
            return ToolIntent("open_app", {"app": app_match.group(1).casefold()})

    return None


def detect_function_call_instruction(
    reply: str,
    tool_names: set[str],
) -> str | None:
    """Find a named function-call instruction in user-facing model text."""
    if not has_function_call_instruction(reply):
        return None
    folded_reply = reply.casefold()
    for tool_name in sorted(tool_names, key=len, reverse=True):
        if re.search(
            rf"(?<![\w]){re.escape(tool_name.casefold())}(?![\w])", folded_reply
        ):
            return tool_name
    return None


def has_function_call_instruction(reply: str) -> bool:
    """Return whether model text tells the user to invoke a tool themselves."""
    return bool(
        re.search(
            r"\b(?:please\s+)?(?:call|invoke|run|use)\s+(?:the\s+)?"
            r"(?:function|tool)\b",
            reply,
            re.IGNORECASE,
        )
    )
