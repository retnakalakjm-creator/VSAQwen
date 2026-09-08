"""Scan control UI component."""

from __future__ import annotations

import customtkinter as ctk


class ScanControls(ctk.CTkFrame):
    def __init__(self, master, on_scan=None, on_single_scan=None, on_auto_changed=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_scan = on_scan
        self._on_single_scan = on_single_scan
        self._on_auto_changed = on_auto_changed
        self.grid_columnconfigure(0, weight=1)

        self.interval = ctk.CTkOptionMenu(
            self,
            values=["5 minutes", "15 minutes", "30 minutes", "60 minutes"],
        )
        self.interval.set("15 minutes")
        self.interval.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        self.scan_button = ctk.CTkButton(self, text="Scan Market", command=self._scan)
        self.scan_button.grid(row=1, column=0, sticky="ew", padx=8, pady=4)

        self.single_scan_button = ctk.CTkButton(self, text="Scan Selected Stock", command=self._single_scan)
        self.single_scan_button.grid(row=2, column=0, sticky="ew", padx=8, pady=4)

        self.auto = ctk.CTkSwitch(self, text="Auto scan", command=self._auto)
        self.auto.grid(row=3, column=0, sticky="w", padx=8, pady=8)

    def _scan(self) -> None:
        if self._on_scan:
            self._on_scan()

    def _single_scan(self) -> None:
        if self._on_single_scan:
            self._on_single_scan()

    def _auto(self) -> None:
        if self._on_auto_changed:
            self._on_auto_changed(bool(self.auto.get()), self.interval.get())
