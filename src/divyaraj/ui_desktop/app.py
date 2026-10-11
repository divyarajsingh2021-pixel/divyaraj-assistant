"""CustomTkinter chat window for Divyaraj Assistant."""

from __future__ import annotations

import queue
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from divyaraj.config import Settings, load_settings
from divyaraj.core.agent import Agent
from divyaraj.core.llm import OllamaClient
from divyaraj.stt import SpeechToText
from divyaraj.tts import TextToSpeech
from divyaraj.ui_desktop.controller import (
    ConfirmationBroker,
    ConfirmationRequest,
    DesktopController,
    DesktopEvent,
    DesktopJob,
)
from divyaraj.ui_desktop.settings import save_desktop_settings


class DesktopWindow(ctk.CTk):
    """Render chat and route UI actions to background assistant services."""

    def __init__(self, settings: Settings) -> None:
        """Build the window, assistant services, and background worker."""
        super().__init__()
        self.settings = settings
        self.title("Divyaraj Assistant")
        self.geometry("900x720")
        self.minsize(640, 520)
        self.configure(fg_color="#10131a")

        self.events: queue.Queue[DesktopEvent] = queue.Queue()
        self.confirmations = ConfirmationBroker(self.events)
        self.llm = OllamaClient(settings)
        self.agent = Agent(
            llm=self.llm,
            confirmation_callback=self.confirmations.confirm,
        )
        self.speech_to_text = SpeechToText(settings)
        self.text_to_speech = TextToSpeech(settings)
        self.controller = DesktopController(
            self.agent,
            self.speech_to_text,
            self.text_to_speech,
            self.events,
        )
        self.voice_enabled = settings.voice_enabled
        self.muted = False
        self.busy = False
        self.recording = False
        self._retry_job: DesktopJob | None = None
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Control-Return>", self._send_shortcut)
        self.after(100, self._poll_events)

    def _build_layout(self) -> None:
        """Create the chat history, controls, and status bar."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Divyaraj",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#f3f4f6",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            header,
            text="Settings",
            width=100,
            command=self._open_settings,
        ).grid(row=0, column=1, padx=(8, 0))

        self.chat = ctk.CTkScrollableFrame(
            self,
            fg_color="#171b24",
            corner_radius=14,
        )
        self.chat.grid(row=1, column=0, sticky="nsew", padx=22, pady=8)
        self.chat.grid_columnconfigure(0, weight=1)
        self._add_message("assistant", "Hi! What can I help you with?")

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=22, pady=(8, 6))
        controls.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(
            controls,
            height=76,
            wrap="word",
            fg_color="#202632",
            border_color="#343d4d",
            border_width=1,
        )
        self.input_box.grid(row=0, column=0, rowspan=2, sticky="ew", padx=(0, 10))
        self.send_button = ctk.CTkButton(
            controls,
            text="Send",
            width=96,
            height=38,
            command=self._send,
        )
        self.send_button.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.mic_button = ctk.CTkButton(
            controls,
            text="🎙  Start listening",
            width=180,
            height=42,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2763cf",
            hover_color="#3476e8",
            command=self._toggle_recording,
        )
        self.mic_button.grid(row=1, column=1, sticky="ew", pady=(6, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)
        self.status_label = ctk.CTkLabel(
            footer,
            text="Idle",
            anchor="w",
            text_color="#aeb7c6",
        )
        self.status_label.grid(row=0, column=0, sticky="w")
        self.mute_button = ctk.CTkButton(
            footer,
            text="Mute voice",
            width=110,
            fg_color="#303846",
            hover_color="#414c5e",
            command=self._toggle_mute,
        )
        self.mute_button.grid(row=0, column=1, padx=(8, 0))
        self.retry_button = ctk.CTkButton(
            footer,
            text="Retry",
            width=80,
            command=self._retry,
        )

    def _add_message(self, role: str, text: str) -> None:
        """Append a left/right chat bubble to the scrollable history."""
        is_user = role == "user"
        row = ctk.CTkFrame(self.chat, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=6)
        bubble = ctk.CTkLabel(
            row,
            text=text,
            justify="left",
            anchor="w",
            wraplength=590,
            padx=14,
            pady=10,
            corner_radius=14,
            fg_color="#285bb5" if is_user else "#242b37",
            text_color="#ffffff",
        )
        bubble.pack(anchor="e" if is_user else "w")
        self.chat._parent_canvas.yview_moveto(1.0)

    def _send(self) -> None:
        """Queue the text currently entered by the user."""
        if self.busy:
            return
        message = self.input_box.get("1.0", "end-1c").strip()
        if not message:
            return
        self.input_box.delete("1.0", "end")
        self._add_message("user", message)
        self._clear_retry()
        self.busy = True
        self._update_controls()
        self.controller.submit_text(message, speak=self._should_speak())

    def _send_shortcut(self, event: tk.Event[tk.Misc]) -> str:
        """Send from the multiline input when Ctrl+Enter is pressed."""
        if event.keysym == "Return":
            self._send()
            return "break"
        return ""

    def _toggle_recording(self) -> None:
        """Start a voice job or signal the active recording to stop."""
        if self.recording:
            self.recording = False
            self.controller.stop_voice()
            self._update_controls()
            return
        if self.busy:
            return
        self.recording = True
        self.busy = True
        self.status_label.configure(text="Listening")
        self.controller.start_voice(speak=self._should_speak())
        self._update_controls()

    def _toggle_mute(self) -> None:
        """Toggle spoken replies without changing chat output."""
        self.muted = not self.muted
        self.mute_button.configure(text="Unmute voice" if self.muted else "Mute voice")

    def _should_speak(self) -> bool:
        """Return whether this turn should be spoken."""
        return self.voice_enabled and not self.muted

    def _open_settings(self) -> None:
        """Open a small preferences window for model and voice options."""
        window = ctk.CTkToplevel(self)
        window.title("Divyaraj Settings")
        window.geometry("420x330")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(window, text="Ollama model").grid(
            row=0, column=0, sticky="w", padx=20, pady=(22, 4)
        )
        model_entry = ctk.CTkEntry(window)
        model_entry.insert(0, self.settings.ollama_model)
        model_entry.grid(row=1, column=0, sticky="ew", padx=20)
        ctk.CTkLabel(window, text="Whisper model (for example: base or tiny)").grid(
            row=2, column=0, sticky="w", padx=20, pady=(16, 4)
        )
        whisper_entry = ctk.CTkEntry(window)
        whisper_entry.insert(0, self.settings.whisper_model)
        whisper_entry.grid(row=3, column=0, sticky="ew", padx=20)
        voice_switch = ctk.CTkSwitch(window, text="Voice replies")
        if self.voice_enabled:
            voice_switch.select()
        voice_switch.grid(row=4, column=0, sticky="w", padx=20, pady=18)

        def save() -> None:
            try:
                model_name = model_entry.get().strip()
                whisper_model = whisper_entry.get().strip()
                voice_enabled = bool(voice_switch.get())
                save_desktop_settings(
                    model_name,
                    voice_enabled,
                    whisper_model,
                    Path(".env"),
                )
            except (OSError, ValueError) as error:
                messagebox.showerror(
                    "Could not save settings", str(error), parent=window
                )
                return
            self.settings = self.settings.model_copy(
                update={
                    "ollama_model": model_name,
                    "whisper_model": whisper_model,
                    "voice_enabled": voice_enabled,
                }
            )
            self.llm.model = model_name
            self.speech_to_text.settings = self.settings
            self.speech_to_text._model = None
            self.text_to_speech.settings = self.settings
            self.voice_enabled = voice_enabled
            window.destroy()

        ctk.CTkButton(window, text="Save", command=save).grid(
            row=5, column=0, sticky="ew", padx=20, pady=(0, 18)
        )

    def _poll_events(self) -> None:
        """Handle background events on Tk's main thread."""
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event.kind == "status":
                self.status_label.configure(text=event.text)
                if event.text == "Idle":
                    self.busy = False
                    self.recording = False
                self._update_controls()
            elif event.kind == "transcript":
                self._add_message("user", event.text)
            elif event.kind == "reply":
                self._add_message("assistant", event.text)
            elif event.kind == "error":
                self._add_message("assistant", event.text)
            elif event.kind == "offline":
                self._add_message(
                    "assistant",
                    "I couldn't connect to Ollama. Start Ollama and make sure "
                    f"'{self.llm.model}' is installed, then retry.",
                )
                self._retry_job = event.retry_job
                self.retry_button.grid(row=0, column=2, padx=(8, 0), sticky="e")
            elif event.kind == "confirmation" and event.confirmation is not None:
                self._show_confirmation(event.confirmation)
        self.after(100, self._poll_events)

    def _show_confirmation(self, request: ConfirmationRequest) -> None:
        """Ask for explicit permission in a modal dialog without blocking Tk."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm action")
        dialog.geometry("380x170")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog,
            text=f"Allow the assistant to run '{request.tool.name}'?",
            wraplength=330,
        ).pack(padx=20, pady=(28, 22))
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack()

        def decide(approved: bool) -> None:
            self.controller.resolve_confirmation(request, approved)
            dialog.destroy()

        ctk.CTkButton(
            actions,
            text="No",
            fg_color="#414957",
            command=lambda: decide(False),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            actions,
            text="Yes",
            command=lambda: decide(True),
        ).pack(side="left", padx=8)
        dialog.protocol("WM_DELETE_WINDOW", lambda: decide(False))

    def _retry(self) -> None:
        """Resubmit the last turn after the user restarts Ollama."""
        if self._retry_job is None:
            return
        job = self._retry_job
        self._retry_job = None
        self.retry_button.grid_remove()
        self.busy = True
        self.status_label.configure(text="Thinking")
        self.controller.retry(job)
        self._update_controls()

    def _clear_retry(self) -> None:
        """Hide and forget any stale retry action when a new turn is submitted."""
        self._retry_job = None
        self.retry_button.grid_remove()

    def _update_controls(self) -> None:
        """Reflect the active worker/recording state in the buttons."""
        self.send_button.configure(state="disabled" if self.busy else "normal")
        self.mic_button.configure(
            text="■  Stop listening" if self.recording else "🎙  Start listening",
            state="normal" if self.recording or not self.busy else "disabled",
        )

    def _close(self) -> None:
        """Stop background recording and close the window."""
        self.controller.close()
        self.destroy()


def run_desktop(settings: Settings | None = None) -> None:
    """Start the desktop application using the supplied or loaded settings."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    window = DesktopWindow(settings or load_settings())
    window.mainloop()
