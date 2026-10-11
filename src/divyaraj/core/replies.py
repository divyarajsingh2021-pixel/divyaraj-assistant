"""User-facing formatting for tool results."""

from datetime import datetime


def format_tool_reply(tool_name: str, result: str) -> str:
    """Format machine-oriented tool results as concise human-friendly replies."""
    if tool_name != "get_time":
        return result
    raw_result = result.strip()
    if "T" not in raw_result:
        return result
    try:
        local_time = datetime.fromisoformat(raw_result)
    except ValueError:
        return result
    hour_and_minute = local_time.strftime("%I:%M %p").lstrip("0")
    return (
        f"It's {hour_and_minute} on {local_time.strftime('%A')}, "
        f"{local_time.day} {local_time.strftime('%B')}."
    )
