"""SQLite-backed conversation history and notes."""

import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from divyaraj.config import load_settings


@dataclass(frozen=True)
class Message:
    """One message in the conversation history."""

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Note:
    """A note stored for later retrieval."""

    id: int
    title: str
    content: str


class Memory:
    """Persist conversation history and searchable notes in SQLite."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        """Initialize database tables at the configured or supplied path."""
        self.database_path = Path(
            database_path or load_settings().database_path
        ).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def add_user_message(self, content: str) -> None:
        """Append a user message to the persistent conversation history."""
        self._add_message("user", content)

    def add_assistant_message(self, content: str) -> None:
        """Append an assistant message to the persistent conversation history."""
        self._add_message("assistant", content)

    def history(self) -> tuple[Message, ...]:
        """Return conversation messages in insertion order."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT role, content FROM messages ORDER BY id"
            ).fetchall()
        return tuple(Message(role=row["role"], content=row["content"]) for row in rows)

    def create_note(self, title: str, content: str) -> Note:
        """Create and return a note."""
        normalized_title = title.strip()
        normalized_content = content.strip()
        if not normalized_title or not normalized_content:
            raise ValueError("Note title and content must not be empty.")
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO notes (title, content) VALUES (?, ?)",
                (normalized_title, normalized_content),
            )
            note_id = cursor.lastrowid
        if note_id is None:
            raise RuntimeError("SQLite did not return an ID for the created note.")
        return Note(id=note_id, title=normalized_title, content=normalized_content)

    def list_notes(self) -> tuple[Note, ...]:
        """Return all notes in creation order."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, title, content FROM notes ORDER BY id"
            ).fetchall()
        return tuple(_row_to_note(row) for row in rows)

    def search_notes(self, query: str) -> tuple[Note, ...]:
        """Return notes whose title or content contains the query text."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty.")
        escaped_query = (
            normalized_query.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{escaped_query}%"
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, title, content FROM notes
                WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'
                ORDER BY id
                """,
                (pattern, pattern),
            ).fetchall()
        return tuple(_row_to_note(row) for row in rows)

    def _add_message(self, role: Literal["user", "assistant"], content: str) -> None:
        """Append one validated conversation message."""
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Message content must not be empty.")
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO messages (role, content) VALUES (?, ?)",
                (role, normalized_content),
            )

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Open a SQLite connection with row access by column name."""
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            with connection:
                yield connection


def _row_to_note(row: sqlite3.Row) -> Note:
    """Convert a database row into a note value."""
    return Note(id=row["id"], title=row["title"], content=row["content"])
