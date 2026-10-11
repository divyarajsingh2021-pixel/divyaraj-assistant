"""Global hotkey parsing and lazy pynput integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol


def normalize_hotkey(hotkey: str) -> str:
    """Convert simple names such as ``ctrl+space`` to pynput syntax."""
    parts = [part.strip().casefold() for part in hotkey.split("+")]
    if len(parts) < 2 or any(not part for part in parts):
        raise ValueError("Hotkey must contain modifiers and a key, such as ctrl+space.")
    aliases = {
        "ctrl": "ctrl",
        "control": "ctrl",
        "alt": "alt",
        "shift": "shift",
        "win": "cmd",
        "cmd": "cmd",
    }
    modifiers = parts[:-1]
    if any(modifier not in aliases for modifier in modifiers):
        raise ValueError("Hotkey modifiers must be ctrl, alt, shift, or win.")
    key = parts[-1]
    if key in aliases:
        raise ValueError("Hotkey must end with a non-modifier key.")
    normalized_modifiers = [f"<{aliases[modifier]}>" for modifier in modifiers]
    normalized_key = f"<{key}>" if len(key) > 1 else key
    return "+".join((*normalized_modifiers, normalized_key))


class Listener(Protocol):
    """Minimal pynput listener interface used by the desktop app."""

    def start(self) -> None:
        """Start monitoring keyboard events."""

    def stop(self) -> None:
        """Stop monitoring keyboard events."""

    def join(self, timeout: float | None = None) -> None:
        """Wait for listener shutdown."""


class GlobalHotkey:
    """Start and stop a configurable system-wide hotkey listener."""

    def __init__(self, hotkey: str, callback: Callable[[], None]) -> None:
        """Store the key chord and callback without loading pynput."""
        self.hotkey = normalize_hotkey(hotkey)
        self.callback = callback
        self._listener: Listener | None = None

    def start(self) -> None:
        """Start pynput or raise an actionable error for unavailable hooks."""
        try:
            from pynput import keyboard
        except ImportError as error:
            raise RuntimeError(
                "Global hotkeys are unavailable. Install pynput with "
                "'python -m pip install pynput'."
            ) from error
        try:
            listener = keyboard.GlobalHotKeys({self.hotkey: self.callback})
            listener.start()
        except (OSError, RuntimeError) as error:
            raise RuntimeError(
                "Could not register the global hotkey. Check keyboard permissions "
                "and choose another shortcut in Settings."
            ) from error
        self._listener = listener

    def stop(self) -> None:
        """Stop the listener and wait briefly for its thread to finish."""
        listener = self._listener
        if listener is not None:
            listener.stop()
            listener.join(timeout=1)
            self._listener = None
