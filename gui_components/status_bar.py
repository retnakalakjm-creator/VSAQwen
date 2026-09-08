"""Status/progress UI component."""

from __future__ import annotations

import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status.grid(row=0, column=0, sticky="ew", padx=8, pady=4)
        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.progress.set(0)

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def set_progress(self, value: float) -> None:
        self.progress.set(max(0.0, min(1.0, value)))
