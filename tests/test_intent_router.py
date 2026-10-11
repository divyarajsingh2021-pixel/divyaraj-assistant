"""Tests for deterministic user-intent routing."""

from divyaraj.core.intent_router import (
    detect_function_call_instruction,
    has_clock_time_or_date,
    has_function_call_instruction,
    route_intent,
)


def test_router_matches_time_and_date_requests() -> None:
    """Recognized clock requests always select the clock tool."""
    for text in ("What time is it?", "time is it", "today's date", "current date"):
        intent = route_intent(text)
        assert intent is not None
        assert (intent.tool_name, intent.arguments) == ("get_time", {})


def test_router_matches_speech_variants_for_time_and_date() -> None:
    """Transcription punctuation and common Hindi/Hinglish wording still route."""
    variants = (
        "what time it is?",
        "WHAT TIME IS IT!!!",
        "what's the time",
        "tell me the time.",
        "time now",
        "current time please",
        "today's date?",
        "What day is it?",
        "samay kya hai",
        "time kya hua",
        "aaj ki date",
        "abhi time kya hai?",
        "aaj kaun sa din hai",
    )
    for text in variants:
        intent = route_intent(text)
        assert intent is not None, text
        assert intent.tool_name == "get_time", text


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


def test_router_matches_speech_variants_for_notes() -> None:
    """Note-taking commands tolerate punctuation, capitalization, and variants."""
    for text in ("NOTE DOWN: buy milk", "note down, buy milk!", "Make a note"):
        intent = route_intent(text)
        assert intent is not None, text
        assert intent.tool_name == "create_note", text

    for text in ("my notes?", "show notes!", "Show my notes", "list notes"):
        intent = route_intent(text)
        assert intent is not None, text
        assert intent.tool_name == "list_notes", text


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


def test_clock_or_date_reply_detection() -> None:
    """Common time and calendar forms are detected, unrelated numbers are not."""
    for reply in (
        "It is 9:18 PM.",
        "The time is 21:18.",
        "Today is Sunday, 11 October.",
        "The date is 2026-10-11.",
        "Meet me on 10/11/2026.",
    ):
        assert has_clock_time_or_date(reply), reply
    assert not has_clock_time_or_date("The answer is version 3.11.")
