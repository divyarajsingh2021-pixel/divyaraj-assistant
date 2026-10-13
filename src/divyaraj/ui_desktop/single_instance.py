"""Loopback-based single-instance coordination for the desktop application."""

from __future__ import annotations

import getpass
import logging
import socket
import threading
import zlib
from collections.abc import Callable

LOGGER = logging.getLogger(__name__)
_HOST = "127.0.0.1"
_APP_ID = "divyaraj-assistant"
_ACKNOWLEDGEMENT = b"DIVYARAJ"


def instance_port(username: str | None = None) -> int:
    """Return a stable, per-user local port for instance coordination."""
    user = username or getpass.getuser()
    port_span = 65_535 - 49_152
    return 49_152 + zlib.crc32(f"{_APP_ID}:{user}".encode()) % port_span


class SingleInstanceGuard:
    """Forward second launches to the already-running desktop process."""

    def __init__(
        self,
        on_show: Callable[[], None],
        *,
        port: int | None = None,
    ) -> None:
        """Prepare the loopback listener and main-thread show callback."""
        self._on_show = on_show
        self._port = port or instance_port()
        self._server: socket.socket | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        """Start as primary, or notify the existing process and return False."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind((_HOST, self._port))
            server.listen()
        except OSError as bind_error:
            server.close()
            try:
                with socket.create_connection((_HOST, self._port), timeout=1) as client:
                    client.sendall(b"SHOW")
                    if client.recv(len(_ACKNOWLEDGEMENT)) != _ACKNOWLEDGEMENT:
                        raise OSError("The port is not owned by Divyaraj.")
            except OSError:
                raise RuntimeError(
                    "Could not safely check whether Divyaraj is already running. "
                    "Close any process using its local instance port and try again."
                ) from bind_error
            return False

        server.settimeout(0.2)
        self._server = server
        self._thread = threading.Thread(
            target=self._serve,
            name="divyaraj-single-instance",
            daemon=True,
        )
        self._thread.start()
        return True

    def close(self) -> None:
        """Stop the local listener and its background thread."""
        self._stop.set()
        server = self._server
        if server is not None:
            server.close()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)

    def _serve(self) -> None:
        """Receive show requests until the primary instance is closed."""
        server = self._server
        if server is None:
            return
        while not self._stop.is_set():
            try:
                accepted = server.accept()
            except TimeoutError:
                continue
            except OSError:
                if not self._stop.is_set():
                    LOGGER.exception("Single-instance listener stopped unexpectedly.")
                return
            connection = accepted[0]
            with connection:
                try:
                    if connection.recv(16) == b"SHOW":
                        self._on_show()
                        connection.sendall(_ACKNOWLEDGEMENT)
                except OSError:
                    LOGGER.exception("Could not read a single-instance request.")
