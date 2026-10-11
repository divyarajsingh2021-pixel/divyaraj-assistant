"""Tests for desktop hotkey, single-instance, and startup-folder helpers."""

import socket
from pathlib import Path
from threading import Event

import pytest

from divyaraj.ui_desktop.hotkey import normalize_hotkey
from divyaraj.ui_desktop.single_instance import SingleInstanceGuard, instance_port
from divyaraj.ui_desktop.startup import (
    STARTUP_SCRIPT_NAME,
    set_start_with_windows,
)


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("ctrl+space", "<ctrl>+<space>"),
        ("Control+Alt+F4", "<ctrl>+<alt>+<f4>"),
        ("shift+f", "<shift>+f"),
        ("win+space", "<cmd>+<space>"),
    ],
)
def test_normalize_hotkey(configured: str, expected: str) -> None:
    """Simple configurable key names map to pynput's documented syntax."""
    assert normalize_hotkey(configured) == expected


@pytest.mark.parametrize("configured", ["", "space", "ctrl+", "meta+space", "ctrl+alt"])
def test_normalize_hotkey_rejects_invalid_shortcuts(configured: str) -> None:
    """Invalid and modifier-only shortcuts are reported before registration."""
    with pytest.raises(ValueError, match="Hotkey"):
        normalize_hotkey(configured)


def test_single_instance_notifies_primary_instance() -> None:
    """A second guard requests window activation rather than binding another server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    show_requested = Event()
    primary = SingleInstanceGuard(show_requested.set, port=port)
    secondary = SingleInstanceGuard(lambda: None, port=port)
    assert primary.start()
    try:
        assert not secondary.start()
        assert show_requested.wait(timeout=2)
    finally:
        secondary.close()
        primary.close()


def test_instance_port_is_stable_and_unprivileged() -> None:
    """Each username receives a repeatable port in the dynamic/private range."""
    assert instance_port("test-user") == instance_port("test-user")
    assert 49_152 <= instance_port("test-user") <= 65_534


def test_startup_command_is_created_and_removed(tmp_path: Path) -> None:
    """The current-user Startup entry is easy to inspect and undo."""
    executable = Path("C:/Python311/python.exe")
    project = Path("C:/projects/divyaraj assistant")

    script = set_start_with_windows(
        True,
        startup_folder=tmp_path,
        executable=executable,
        working_directory=project,
    )

    assert script.name == STARTUP_SCRIPT_NAME
    assert f'cd /d "{project}"' in script.read_text(encoding="utf-8")
    assert f'"{executable}" -m divyaraj --gui' in script.read_text(encoding="utf-8")

    set_start_with_windows(False, startup_folder=tmp_path)

    assert not script.exists()


def test_disabling_missing_startup_entry_is_safe(tmp_path: Path) -> None:
    """Turning startup off is idempotent when the entry was already removed."""
    script = set_start_with_windows(False, startup_folder=tmp_path)

    assert script == tmp_path / STARTUP_SCRIPT_NAME
    assert not script.exists()
