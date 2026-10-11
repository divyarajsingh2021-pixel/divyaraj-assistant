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
    r"\bwhat time (?:is it|it is)\b",
    r"\bwhat is the time\b",
    r"\btime is it\b",
    r"\btell me the time\b",
    r"\btime now\b",
    r"\bcurrent time\b",
    r"\btime kya (?:hai|hua)\b",
    r"\b(?:abhi )?time kya hai\b",
    r"\bsamay kya hai\b",
    r"\bkitne baje (?:hain|hai)\b",
    r"\btoday s date\b",
    r"\btoday date\b",
    r"\baaj ki date\b",
    r"\baaj ka date\b",
    r"\baaj (?:kya )?date (?:hai|hain)\b",
    r"\bcurrent date\b",
    r"\bwhat date (?:is it|it is)\b",
    r"\bdate today\b",
    r"\bwhat day (?:is it|it is)\b",
    r"\baaj kaun sa din hai\b",
)
_LIST_NOTE_PATTERNS = (
    r"\bmy notes\b",
    r"\blist (?:all )?(?:my )?notes\b",
    r"\bshow (?:all )?(?:my )?notes\b",
    r"\bwhat notes do i have\b",
)
_CREATE_NOTE_PREFIX = re.compile(
    r"^\s*(?:please[\W_]+)?"
    r"(?:(?:make|add|create)[\W_]+(?:me[\W_]+)?a[\W_]+note"
    r"(?:[\W_]+of)?|note[\W_]+down)\b[\s:,-]*",
    re.IGNORECASE,
)


def route_intent(
    text: str,
    allowed_apps: Mapping[str, str] | None = None,
) -> ToolIntent | None:
    """Return a deterministic tool intent for clearly phrased requests."""
    normalized = _normalize_text(text)
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


def has_clock_time_or_date(text: str) -> bool:
    """Detect common clock times or calendar dates in a model's final reply."""
    if re.search(
        r"(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d"
        r"(?:\s?(?:a\.?m\.?|p\.?m\.?))?(?!\d)"
        r"|\b(?:1[0-2]|0?[1-9])\s?(?:a\.?m\.?|p\.?m\.?)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
        r"|\b\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?\b",
        text,
    ):
        return True
    normalized = _normalize_text(text)
    return bool(
        re.search(
            r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"january|february|march|april|may|june|july|august|september|"
            r"october|november|december)\b",
            normalized,
        )
    )


def _normalize_text(text: str) -> str:
    """Normalize punctuation and common contractions in speech transcripts."""
    normalized = text.casefold().replace("’", "'")
    normalized = re.sub(r"\bwhat[' ]s\b", "what is", normalized)
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


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
