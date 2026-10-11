"""Tests for deterministic user-intent routing."""

from divyaraj.core.intent_router import (
    detect_function_call_instruction,
    has_function_call_instruction,
    route_intent,
)


def test_router_matches_time_and_date_requests() -> None:
    """Recognized clock requests always select the clock tool."""
    for text in ("What time is it?", "time is it", "today's date", "current date"):
        intent = route_intent(text)
        assert intent is not None
        assert (intent.tool_name, intent.arguments) == ("get_time", {})


def test_router_matches_list_and_create_note_requests() -> None:
    """Clear note commands resolve to listing, creation, or clarification."""
    list_intent = route_intent("show my notes")
    create_intent = route_intent("make a note: call the dentist")
    needs_content = route_intent("add a note")

    assert list_intent is not None
    assert (list_intent.tool_name, list_intent.arguments) == ("list_notes", {})
    assert create_intent is not None
    assert create_intent.tool_name == "create_note"
    assert create_intent.arguments == {
        "title": "Note",
        "content": "call the dentist",
    }
    assert needs_content is not None
    assert needs_content.clarification == "What would you like me to note?"


def test_router_matches_web_search_and_allowlisted_app() -> None:
    """Explicit web lookup and allowed app requests select their tools."""
    search_intent = route_intent("search the web for local weather")
    app_intent = route_intent("open calculator", {"calculator": "calc.exe"})

    assert search_intent is not None
    assert search_intent.arguments == {"query": "local weather"}
    assert app_intent is not None
    assert app_intent.arguments == {"app": "calculator"}
    assert route_intent("open powershell", {"calculator": "calc.exe"}) is None


def test_router_leaves_other_messages_to_the_model() -> None:
    """Unmatched requests are not interpreted as tool commands."""
    assert route_intent("Tell me a joke.") is None


def test_function_call_instruction_detection_requires_a_tool_name() -> None:
    """Call-yourself language is detected and mapped only to known tools."""
    reply = "Please call the function web_search to continue."

    assert has_function_call_instruction(reply)
    assert detect_function_call_instruction(reply, {"web_search", "get_time"}) == (
        "web_search"
    )
    assert detect_function_call_instruction(reply, {"get_time"}) is None
    assert not has_function_call_instruction("I will use web_search now.")
