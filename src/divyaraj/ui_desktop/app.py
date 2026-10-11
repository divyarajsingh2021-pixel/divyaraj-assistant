"""CustomTkinter chat window for Divyaraj Assistant."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
import webbrowser
from queue import SimpleQueue
from threading import Event, Thread
from tkinter import messagebox

import customtkinter as ctk

from divyaraj.config import Settings, load_settings
from divyaraj.core.agent import Agent
from divyaraj.core.llm import OllamaClient
from divyaraj.first_run import (
    OLLAMA_DOWNLOAD_URL,
    SetupCancelled,
    SetupError,
    prepare_first_run,
)
from divyaraj.stt import SpeechToText
from divyaraj.tts import TextToSpeech
from divyaraj.ui_desktop.controller import (
    ConfirmationBroker,
    ConfirmationRequest,
    DesktopController,
    DesktopEvent,
    DesktopJob,
)
from divyaraj.ui_desktop.hotkey import GlobalHotkey, normalize_hotkey
from divyaraj.ui_desktop.settings import save_desktop_settings
from divyaraj.ui_desktop.single_instance import SingleInstanceGuard
from divyaraj.ui_desktop.startup import set_start_with_windows
from divyaraj.ui_desktop.tray import TrayController

LOGGER = logging.getLogger(__name__)


class DesktopWindow(ctk.CTk):
    """Render chat and route UI actions to background assistant services."""

    def __init__(
        self,
        settings: Settings,
        runtime_events: SimpleQueue[str] | None = None,
        instance_guard: SingleInstanceGuard | None = None,
    ) -> None:
        """Build the window, assistant services, and background worker."""
        super().__init__()
        self.settings = settings
        self.runtime_events = runtime_events or SimpleQueue()
        self.instance_guard = instance_guard
        self.tray: TrayController | None = None
        self.hotkey: GlobalHotkey | None = None
        self.shutting_down = False
        self.setup_ready = False
        self.setup_events: queue.Queue[tuple[str, str, float | None]] = queue.Queue()
        self.setup_cancel = Event()
        self.setup_thread: Thread | None = None
        self.setup_window: ctk.CTkToplevel | None = None
        self.setup_label: ctk.CTkLabel | None = None
        self.setup_progress: ctk.CTkProgressBar | None = None
        self.setup_retry_button: ctk.CTkButton | None = None
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
        self._start_integrations()
        self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        self.bind("<Control-Return>", self._send_shortcut)
        self.after(250, self._begin_first_run_setup)
        self.after(100, self._poll_events)

    def _start_integrations(self) -> None:
        """Start tray and hotkey integrations, reporting optional failures."""
        try:
            self.tray = TrayController(
                on_open=lambda: self.runtime_events.put("open"),
                on_toggle_mute=lambda: self.runtime_events.put("toggle-mute"),
                on_quit=lambda: self.runtime_events.put("quit"),
                is_muted=lambda: self.muted,
                on_error=lambda text: self.runtime_events.put(f"tray-error:{text}"),
            )
            self.tray.start()
        except (ImportError, OSError, RuntimeError) as error:
            self.tray = None
            messagebox.showerror(
                "System tray unavailable",
                f"Divyaraj could not start its system tray icon: {error}",
                parent=self,
            )
        self._restart_hotkey(show_error=True)

    def _restart_hotkey(self, *, show_error: bool) -> bool:
        """Apply the configured global shortcut without failing app startup."""
        if self.hotkey is not None:
            self.hotkey.stop()
            self.hotkey = None
        try:
            listener = GlobalHotkey(
                self.settings.global_hotkey,
                lambda: self.runtime_events.put("hotkey"),
            )
            listener.start()
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.status_label.configure(text="Global hotkey unavailable")
            if show_error:
                messagebox.showwarning(
                    "Global hotkey unavailable",
                    f"Divyaraj is still available from its window or tray. {error}",
                    parent=self,
                )
            return False
        self.hotkey = listener
        return True

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
        if self.busy or not self.setup_ready:
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
        if self.busy or not self.setup_ready:
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

    def _show_window(self) -> None:
        """Restore and focus the chat window."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _should_speak(self) -> bool:
        """Return whether this turn should be spoken."""
        return self.voice_enabled and not self.muted

    def _open_settings(self) -> None:
        """Open a small preferences window for model and voice options."""
        window = ctk.CTkToplevel(self)
        window.title("Divyaraj Settings")
        window.geometry("440x430")
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
        ctk.CTkLabel(window, text="Global hotkey").grid(
            row=5, column=0, sticky="w", padx=20, pady=(4, 4)
        )
        hotkey_entry = ctk.CTkEntry(window)
        hotkey_entry.insert(0, self.settings.global_hotkey)
        hotkey_entry.grid(row=6, column=0, sticky="ew", padx=20)
        startup_switch = ctk.CTkSwitch(window, text="Start with Windows")
        if self.settings.start_with_windows:
            startup_switch.select()
        startup_switch.grid(row=7, column=0, sticky="w", padx=20, pady=14)

        def save() -> None:
            try:
                model_name = model_entry.get().strip()
                whisper_model = whisper_entry.get().strip()
                voice_enabled = bool(voice_switch.get())
                global_hotkey = hotkey_entry.get().strip()
                normalize_hotkey(global_hotkey)
                start_with_windows = bool(startup_switch.get())
                if start_with_windows or self.settings.start_with_windows:
                    set_start_with_windows(start_with_windows)
                save_desktop_settings(
                    model_name,
                    voice_enabled,
                    whisper_model,
                    self.settings.settings_path,
                    global_hotkey,
                    start_with_windows,
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
                    "global_hotkey": global_hotkey,
                    "start_with_windows": start_with_windows,
                }
            )
            self.llm.model = model_name
            self.speech_to_text.settings = self.settings
            self.speech_to_text._model = None
            self.text_to_speech.settings = self.settings
            self.voice_enabled = voice_enabled
            self._restart_hotkey(show_error=True)
            window.destroy()

        ctk.CTkButton(window, text="Save", command=save).grid(
            row=8, column=0, sticky="ew", padx=20, pady=(0, 18)
        )

    def _poll_events(self) -> None:
        """Handle background events on Tk's main thread."""
        self._poll_setup_events()
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
        while True:
            try:
                action = self.runtime_events.get_nowait()
            except queue.Empty:
                break
            if action == "open":
                self._show_window()
            elif action == "toggle-mute":
                self._toggle_mute()
            elif action == "hotkey":
                self._show_window()
                if self.recording:
                    self._toggle_recording()
                elif not self.busy:
                    self._toggle_recording()
            elif action == "quit":
                self._quit()
                return
            elif action.startswith("tray-error:"):
                self.tray = None
                self.status_label.configure(text="System tray unavailable")
                messagebox.showerror(
                    "System tray unavailable",
                    action.removeprefix("tray-error:"),
                    parent=self,
                )
        self.after(100, self._poll_events)

    def _begin_first_run_setup(self) -> None:
        """Show setup progress and run model checks outside the UI thread."""
        if self.shutting_down:
            return
        if self.setup_thread is not None and self.setup_thread.is_alive():
            return
        self.setup_cancel.clear()
        self._show_setup_window()
        self._set_setup_progress("Checking Ollama and local speech models…", None)
        self.setup_retry_button.grid_remove()

        def run_setup() -> None:
            try:
                prepare_first_run(
                    self.settings,
                    lambda stage, text, percent: self.setup_events.put(
                        (stage, text, percent)
                    ),
                    self.setup_cancel,
                )
            except SetupCancelled:
                return
            except SetupError as error:
                self.setup_events.put(("error", str(error), None))
            except Exception as error:
                LOGGER.exception("Unexpected first-run setup failure.")
                self.setup_events.put(
                    (
                        "error",
                        f"Setup failed unexpectedly. Check the installation and "
                        f"retry: {error}",
                        None,
                    )
                )

        self.setup_thread = Thread(
            target=run_setup,
            name="divyaraj-first-run-setup",
            daemon=True,
        )
        self.setup_thread.start()

    def _show_setup_window(self) -> None:
        """Build or restore the first-run progress and recovery dialog."""
        if self.setup_window is not None and self.setup_window.winfo_exists():
            self.setup_window.deiconify()
            self.setup_window.lift()
            return
        window = ctk.CTkToplevel(self)
        window.title("Divyaraj setup")
        window.geometry("480x245")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            window,
            text="Preparing Divyaraj",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 8))
        self.setup_label = ctk.CTkLabel(
            window,
            text="Checking Ollama…",
            wraplength=430,
            justify="left",
        )
        self.setup_label.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
        self.setup_progress = ctk.CTkProgressBar(window, mode="indeterminate")
        self.setup_progress.grid(row=2, column=0, sticky="ew", padx=24, pady=8)
        self.setup_progress.start()
        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=24, pady=(10, 20))
        buttons.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(
            buttons,
            text="Download Ollama",
            command=lambda: webbrowser.open(OLLAMA_DOWNLOAD_URL),
        ).grid(row=0, column=0, padx=(0, 6))
        self.setup_retry_button = ctk.CTkButton(
            buttons,
            text="Retry",
            command=self._begin_first_run_setup,
        )
        self.setup_retry_button.grid(row=0, column=1, padx=6)
        ctk.CTkButton(
            buttons,
            text="Quit",
            fg_color="#414957",
            command=self._quit,
        ).grid(row=0, column=2, padx=(6, 0))
        self.setup_retry_button.grid_remove()
        window.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        self.setup_window = window

    def _poll_setup_events(self) -> None:
        """Apply model-download progress and errors on Tk's main thread."""
        while True:
            try:
                stage, text, percent = self.setup_events.get_nowait()
            except queue.Empty:
                return
            if stage == "error":
                self._set_setup_progress(text, None)
                self.setup_progress.stop()
                self.setup_retry_button.grid_remove()
                self.setup_retry_button.grid(row=0, column=1, padx=6, sticky="ew")
                self.setup_ready = False
            elif stage == "complete":
                self.setup_ready = True
                if self.setup_progress is not None:
                    self.setup_progress.stop()
                if self.setup_window is not None:
                    self.setup_window.grab_release()
                    self.setup_window.destroy()
                    self.setup_window = None
                self.status_label.configure(text="Idle")
                self._update_controls()
            else:
                self._set_setup_progress(text, percent)

    def _set_setup_progress(self, text: str, percent: float | None) -> None:
        """Update setup label and determinate/indeterminate progress display."""
        if self.setup_label is not None and self.setup_label.winfo_exists():
            self.setup_label.configure(text=text)
        bar = self.setup_progress
        if bar is None or not bar.winfo_exists():
            return
        if percent is None:
            bar.configure(mode="indeterminate")
            bar.start()
        else:
            bar.stop()
            bar.configure(mode="determinate")
            bar.set(max(0.0, min(1.0, percent / 100)))

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
        enabled = self.setup_ready and not self.busy
        self.send_button.configure(state="normal" if enabled else "disabled")
        self.mic_button.configure(
            text="■  Stop listening" if self.recording else "🎙  Start listening",
            state=("normal" if self.recording else "normal" if enabled else "disabled"),
        )

    def _minimize_to_tray(self) -> None:
        """Hide the window while keeping the tray assistant running."""
        if self.tray is None:
            messagebox.showwarning(
                "System tray unavailable",
                "Divyaraj cannot minimize safely because its tray icon did not "
                "start. Keep the window open until the tray integration is available.",
                parent=self,
            )
            return
        self.withdraw()

    def _quit(self) -> None:
        """Stop global integrations, deny pending confirmations, and exit."""
        if self.shutting_down:
            return
        self.shutting_down = True
        self.setup_cancel.set()
        if self.setup_thread is not None:
            self.setup_thread.join(timeout=2)
        if self.hotkey is not None:
            self.hotkey.stop()
            self.hotkey = None
        self.confirmations.close()
        worker_stopped = self.controller.close()
        if not worker_stopped:
            messagebox.showwarning(
                "Assistant is still stopping",
                "The assistant worker did not stop in time. It will be terminated "
                "when this process exits.",
                parent=self,
            )
        if self.tray is not None:
            self.tray.stop()
            self.tray = None
        if self.instance_guard is not None:
            self.instance_guard.close()
        self.destroy()


def run_desktop(settings: Settings | None = None) -> None:
    """Start the desktop application using the supplied or loaded settings."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    runtime_events: SimpleQueue[str] = SimpleQueue()
    instance_guard = SingleInstanceGuard(on_show=lambda: runtime_events.put("open"))
    if not instance_guard.start():
        return
    try:
        window = DesktopWindow(
            settings or load_settings(), runtime_events, instance_guard
        )
        window.mainloop()
    finally:
        instance_guard.close()
