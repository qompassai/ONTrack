"""
gui/components/voice_button.py — Mic button widget for the OnTrack desktop GUI.

Embeds into any CustomTkinter parent frame.
Calls a callback with the transcribed text string when recording completes.

Usage:
    from gui.components.voice_button import VoiceButton

    btn = VoiceButton(
        parent,
        on_result=lambda text: my_entry.insert(tk.END, text),
        model_size="base",
    )
    btn.pack(side="left", padx=4)
"""

from __future__ import annotations

import tkinter as tk
import threading
from typing import Callable, Optional

import customtkinter as ctk

from core.voice import VoiceRecognizer, VoiceResult, RecordingState

TDS_BLUE    = "#0057A8"
TDS_NAVY    = "#002855"
TDS_ORANGE  = "#F26522"
TDS_RED     = "#EF4444"
TDS_GREEN   = "#22C55E"
TDS_SURFACE = "#1A2535"
TDS_GRAY    = "#6B7280"
TDS_WHITE   = "#FFFFFF"


class VoiceButton(ctk.CTkFrame):
    """
    A mic button + status label widget.

    States:
      IDLE       — grey mic icon, "Hold to speak" or "Click to speak"
      RECORDING  — red pulsing mic, "Listening…"
      PROCESSING — spinner, "Transcribing…"
      ERROR      — red ✗, error message
    """

    def __init__(
        self,
        parent,
        on_result:   Callable[[str], None],
        model_size:  str = "base",
        language:    Optional[str] = None,
        hold_to_talk: bool = False,
        width:       int = 120,
        **kwargs,
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._on_result   = on_result
        self._hold        = hold_to_talk
        self._recognizer  = VoiceRecognizer(model_size=model_size, language=language)
        self._status_var  = tk.StringVar(value="🎤 Speak")
        self._blink_job:  Optional[str] = None
        self._blink_state = False

        # Preload model in background so first use is fast
        VoiceRecognizer.preload_model(model_size)

        self._build(width)

    def _build(self, width: int):
        self._btn = ctk.CTkButton(
            self,
            textvariable = self._status_var,
            width        = width,
            height       = 38,
            fg_color     = TDS_SURFACE,
            hover_color  = "#2A3A50",
            text_color   = TDS_WHITE,
            corner_radius= 8,
            font         = ctk.CTkFont(size=13),
            command      = self._on_click,
        )
        self._btn.pack()

        self._error_lbl = ctk.CTkLabel(
            self,
            text       = "",
            font       = ctk.CTkFont(size=10),
            text_color = TDS_RED,
        )
        self._error_lbl.pack()

        if self._hold:
            self._btn.bind("<ButtonPress-1>",   lambda e: self._start())
            self._btn.bind("<ButtonRelease-1>", lambda e: self._stop())
            self._status_var.set("🎤 Hold")

    # ── State transitions ──────────────────────────────────────────────────

    def _on_click(self):
        if self._hold:
            return  # handled by bind
        state = self._recognizer.state
        if state == RecordingState.IDLE:
            self._start()
        elif state == RecordingState.RECORDING:
            self._stop()

    def _start(self):
        self._error_lbl.configure(text="")
        self._recognizer.start_recording()
        self._set_recording_ui()

    def _stop(self):
        self._cancel_blink()
        self._status_var.set("⏳ Transcribing…")
        self._btn.configure(fg_color=TDS_NAVY, state="disabled")

        self._recognizer.stop_and_transcribe_async(
            callback=lambda result: self.after(0, lambda r=result: self._on_done(r))
        )

    def _on_done(self, result: VoiceResult):
        self._btn.configure(state="normal")
        if result.error:
            self._status_var.set("🎤 Speak")
            self._btn.configure(fg_color=TDS_SURFACE)
            self._error_lbl.configure(text=f"Error: {result.error[:60]}")
        elif result.text.strip():
            self._status_var.set("✓ Done")
            self._btn.configure(fg_color=TDS_GREEN)
            self._on_result(result.text.strip())
            # Reset after 2s
            self.after(2000, self._reset_ui)
        else:
            self._status_var.set("🎤 Speak")
            self._btn.configure(fg_color=TDS_SURFACE)
            self._error_lbl.configure(text="No speech detected.")

    def _set_recording_ui(self):
        self._btn.configure(fg_color=TDS_RED)
        self._blink()

    def _blink(self):
        self._blink_state = not self._blink_state
        self._status_var.set("● Listening…" if self._blink_state else "○ Listening…")
        self._blink_job = self.after(500, self._blink)

    def _cancel_blink(self):
        if self._blink_job:
            self.after_cancel(self._blink_job)
            self._blink_job = None

    def _reset_ui(self):
        label = "🎤 Hold" if self._hold else "🎤 Speak"
        self._status_var.set(label)
        self._btn.configure(fg_color=TDS_SURFACE)

    # ── Public helpers ─────────────────────────────────────────────────────

    def set_language(self, lang: Optional[str]):
        self._recognizer.language = lang

    def set_model(self, model_size: str):
        self._recognizer.model_size = model_size
        VoiceRecognizer.preload_model(model_size)
