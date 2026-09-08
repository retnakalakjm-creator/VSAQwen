"""Selected-result detail component."""

from __future__ import annotations

import customtkinter as ctk


class ResultDetail(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            self,
            text="Decision Detail",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))
        self.text = ctk.CTkTextbox(self, wrap="word")
        self.text.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.show("Select a scan result.")

    def show(self, value: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.configure(state="disabled")
