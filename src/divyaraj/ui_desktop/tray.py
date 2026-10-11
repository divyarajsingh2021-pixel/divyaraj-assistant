"""Generated-icon system tray integration with lazily loaded dependencies."""

from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Thread
from typing import Protocol

LOGGER = logging.getLogger(__name__)


class TrayIcon(Protocol):
    """Minimal pystray icon interface used by the desktop application."""

    def run(self) -> None:
        """Run the platform tray event loop."""

    def stop(self) -> None:
        """Stop the tray event loop."""


class TrayController:
    """Run a pystray icon on a dedicated daemon thread."""

    def __init__(
        self,
        on_open: Callable[[], None],
        on_toggle_mute: Callable[[], None],
        on_quit: Callable[[], None],
        is_muted: Callable[[], bool],
        on_error: Callable[[str], None],
    ) -> None:
        """Create a generated icon and Open/Mute voice/Quit menu."""
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError as error:
            raise RuntimeError(
                "The system tray is unavailable. Reinstall Divyaraj with "
                "'python -m pip install -e .'."
            ) from error

        image = Image.new("RGB", (64, 64), color="#10131a")
        drawing = ImageDraw.Draw(image)
        drawing.ellipse((5, 5, 59, 59), fill="#2763cf")
        drawing.text((23, 16), "D", fill="white")
        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda _icon, _item: on_open(), default=True),
            pystray.MenuItem(
                "Mute voice",
                lambda _icon, _item: on_toggle_mute(),
                checked=lambda _item: is_muted(),
            ),
            pystray.MenuItem("Quit", lambda _icon, _item: on_quit()),
        )
        self._icon: TrayIcon = pystray.Icon(
            "Divyaraj Assistant",
            image,
            "Divyaraj Assistant",
            menu,
        )
        self._thread = Thread(
            target=self._run,
            name="divyaraj-tray",
            daemon=True,
        )
        self._on_error = on_error

    def start(self) -> None:
        """Start the tray event loop in the background."""
        self._thread.start()

    def stop(self) -> None:
        """Stop the tray icon and wait for its thread to exit."""
        self._icon.stop()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        """Report tray backend failures back to the UI event queue."""
        try:
            self._icon.run()
        except (OSError, RuntimeError) as error:
            LOGGER.exception("System tray event loop failed.")
            self._on_error(str(error))
