"""Scan-result table component."""

from __future__ import annotations

import customtkinter as ctk
from tkinter import ttk


class ResultsTable(ctk.CTkFrame):
    COLUMNS = ("symbol", "status", "qualification", "score", "pressure", "confidence", "vsa", "week")

    def __init__(self, master, on_selected=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_selected = on_selected
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.table = ttk.Treeview(self, columns=self.COLUMNS, show="headings")
        headings = ("Symbol", "Status", "Qualification", "Score", "Pressure", "Confidence", "VSA Evidence", "Week")
        for column, heading in zip(self.COLUMNS, headings):
            self.table.heading(column, text=heading)
            self.table.column(column, anchor="w")
        self.table.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.table.bind("<<TreeviewSelect>>", self._selected)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=8)
        self.table.configure(yscrollcommand=scrollbar.set)

    def clear(self) -> None:
        for item in self.table.get_children():
            self.table.delete(item)

    def show(self, rows) -> None:
        self.clear()
        for row in rows:
            self.table.insert("", "end", iid=row[0], values=row)

    def selected_symbol(self):
        selected = self.table.selection()
        return selected[0] if selected else None

    def _selected(self, _event=None) -> None:
        if self._on_selected:
            self._on_selected(self.selected_symbol())
