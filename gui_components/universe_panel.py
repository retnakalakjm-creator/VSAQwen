"""Market-universe UI component."""

from __future__ import annotations

import customtkinter as ctk

from market_universe import BUILTIN_UNIVERSES, MarketUniverse


class UniversePanel(ctk.CTkFrame):
    def __init__(self, master, on_symbols_changed=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_symbols_changed = on_symbols_changed
        self._custom_symbols: list[str] = []
        self._active_universe = "Custom"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.menu = ctk.CTkOptionMenu(
            self,
            values=list(BUILTIN_UNIVERSES) + ["Custom"],
            command=self._changed,
        )
        self.menu.set("Custom")
        self.menu.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        self.symbols = ctk.CTkTextbox(self, height=150)
        self.symbols.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 6))

        self.remove_entry = ctk.CTkEntry(
            self,
            placeholder_text="Symbol to remove...",
        )
        self.remove_entry.grid(row=2, column=0, sticky="ew", padx=8, pady=4)

        self.remove_button = ctk.CTkButton(
            self,
            text="Remove Stock",
            command=self.remove_symbol,
        )
        self.remove_button.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 8))

    def set_symbols(self, symbols: list[str]) -> None:
        normalized = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
        self.symbols.configure(state="normal")
        self.symbols.delete("1.0", "end")
        self.symbols.insert("1.0", "\n".join(normalized))

    def add_symbol(self, symbol: str) -> None:
        symbol = symbol.strip().upper()
        if not symbol:
            return

        if self._active_universe != "Custom":
            self._custom_symbols = self.get_symbols()
            self._active_universe = "Custom"
            self.menu.set("Custom")

        current = self.get_symbols()
        if symbol not in current:
            current.append(symbol)
            self._custom_symbols = current
            self.set_symbols(current)
            self._emit()

    def remove_symbol(self) -> None:
        symbol = self.remove_entry.get().strip().upper()
        if not symbol or self._active_universe != "Custom":
            return

        current = [item for item in self.get_symbols() if item != symbol]
        self._custom_symbols = current
        self.set_symbols(current)
        self.remove_entry.delete(0, "end")
        self._emit()

    def get_symbols(self) -> list[str]:
        return list(dict.fromkeys(
            item.strip().upper()
            for item in self.symbols.get("1.0", "end").splitlines()
            if item.strip()
        ))

    def _changed(self, value: str) -> None:
        # Preserve the custom universe independently from built-in universes.
        if self._active_universe == "Custom":
            self._custom_symbols = self.get_symbols()

        self._active_universe = value

        if value == "Custom":
            self.set_symbols(self._custom_symbols)
        else:
            self.set_symbols(list(MarketUniverse(BUILTIN_UNIVERSES[value]).symbols))

        self._emit()

    def _emit(self) -> None:
        if self._on_symbols_changed:
            self._on_symbols_changed(self.get_symbols())
