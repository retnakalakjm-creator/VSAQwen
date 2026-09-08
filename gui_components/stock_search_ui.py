"""Stock search UI component. UI only; search logic stays in stock_search.py."""

from __future__ import annotations

import customtkinter as ctk

from stock_search import StockSearchResult, normalize_symbol, resolve_stock, search_stocks


class StockSearchFrame(ctk.CTkFrame):
    """Search stocks by symbol/name and emit the selected NSE symbol."""

    def __init__(self, master, on_stock_selected=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_stock_selected = on_stock_selected
        self._suggestions: list[StockSearchResult] = []

        self.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="Search stock name or symbol...",
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=8)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self.entry.bind("<Return>", self._select_first)

        self.add_button = ctk.CTkButton(
            self,
            text="Add",
            width=60,
            command=self._select_first,
        )
        self.add_button.grid(row=0, column=1, padx=(4, 8), pady=8)

        self.listbox = ctk.CTkTextbox(self, height=110)
        self.listbox.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self.listbox.bind("<ButtonRelease-1>", self._select_clicked)
        self.listbox.configure(state="disabled")

    def _on_key_release(self, _event=None) -> None:
        query = self.entry.get().strip()
        self._suggestions = search_stocks(query, limit=8) if query else []
        self._render_suggestions()

    def _render_suggestions(self) -> None:
        self.listbox.configure(state="normal")
        self.listbox.delete("1.0", "end")
        for index, item in enumerate(self._suggestions):
            self.listbox.insert("end", f"{index + 1}. {item.name} ({item.symbol})\n")
        self.listbox.configure(state="disabled")

    def _select_first(self, _event=None) -> None:
        if self._suggestions:
            self._emit(self._suggestions[0])
            return

        symbol = resolve_stock(self.entry.get().strip())
        if symbol:
            self._emit(symbol)
            return

        raw = self.entry.get().strip()
        if raw:
            self._emit(normalize_symbol(raw))

    def _select_clicked(self, event) -> None:
        if not self._suggestions:
            return
        try:
            line = int(self.listbox.index(f"@{event.x},{event.y}").split(".")[0]) - 1
        except (ValueError, IndexError):
            return
        if 0 <= line < len(self._suggestions):
            self._emit(self._suggestions[line])

    def _emit(self, value: StockSearchResult | str) -> None:
        if isinstance(value, StockSearchResult):
            symbol = value.symbol
        else:
            symbol = normalize_symbol(value)

        if not symbol:
            return

        self.entry.delete(0, "end")
        self._suggestions = []
        self._render_suggestions()
        if self._on_stock_selected:
            self._on_stock_selected(symbol)
