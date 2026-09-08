"""ProVSA GUI application shell."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import customtkinter as ctk

from gui_components.result_detail import ResultDetail
from gui_components.results_table import ResultsTable
from gui_components.scan_controls import ScanControls
from gui_components.scan_service import MarketScanService, ScanItem
from gui_components.status_bar import StatusBar
from gui_components.stock_search_ui import StockSearchFrame
from gui_components.universe_panel import UniversePanel


class ProVSAApp(ctk.CTk):
    """Thin composition layer; VSA/scanner logic stays outside the GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.title("ProVSA — VSA Market Scanner")
        self.geometry("1400x850")
        self.minsize(1100, 700)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self._scan_service = MarketScanService()
        self._scanning = False
        self._auto_scan = False
        self._auto_after_id = None
        self._items: dict[str, ScanItem] = {}
        self._selected_symbol: str | None = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(sidebar, text="ProVSA", font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, sticky="w", padx=20, pady=(24, 4))
        ctk.CTkLabel(sidebar, text="Volume Spread Analysis", text_color="gray70").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 18))
        self.search = StockSearchFrame(sidebar, on_stock_selected=self._add_stock)
        self.search.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.universe = UniversePanel(sidebar)
        self.universe.grid(row=3, column=0, sticky="nsew", padx=12, pady=8)
        self.controls = ScanControls(sidebar, on_scan=self._scan_requested, on_single_scan=self._single_scan_requested, on_auto_changed=self._auto_changed)
        self.controls.grid(row=4, column=0, sticky="ew", padx=12, pady=8)
        self.status = StatusBar(sidebar)
        self.status.grid(row=5, column=0, sticky="ew", padx=12, pady=(4, 16))
        content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)
        self.results = ResultsTable(content, on_selected=self._result_selected)
        self.results.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.detail = ResultDetail(content)
        self.detail.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def _add_stock(self, symbol: str) -> None:
        self.universe.add_symbol(symbol)
        self._selected_symbol = symbol
        self.status.set_status(f"Selected {symbol}")

    def _scan_requested(self) -> None:
        self._start_scan(self.universe.get_symbols())

    def _single_scan_requested(self) -> None:
        symbol = self._selected_symbol
        if not symbol:
            symbols = self.universe.get_symbols()
            if len(symbols) == 1:
                symbol = symbols[0]
        if not symbol:
            self.status.set_status("Search and select one stock first")
            return
        self._start_scan([symbol])

    def _auto_changed(self, enabled: bool, interval: str) -> None:
        self._auto_scan = enabled
        if self._auto_after_id is not None:
            self.after_cancel(self._auto_after_id)
            self._auto_after_id = None
        if not enabled:
            self.status.set_status("Auto scan disabled")
            return
        self.status.set_status(f"Auto scan enabled • every {interval}")
        self._schedule_auto_scan(interval)

    def _schedule_auto_scan(self, interval: str) -> None:
        if not self._auto_scan:
            return
        minutes = int(interval.split()[0])
        self._auto_after_id = self.after(minutes * 60 * 1000, self._auto_tick)

    def _auto_tick(self) -> None:
        self._auto_after_id = None
        if not self._auto_scan:
            return
        self._scan_requested()
        self._schedule_auto_scan(self.controls.interval.get())

    def _start_scan(self, symbols: list[str]) -> None:
        if self._scanning:
            return
        symbols = list(dict.fromkeys(symbols))
        if not symbols:
            self.status.set_status("Add at least one stock")
            return
        self._scanning = True
        self.controls.scan_button.configure(state="disabled", text="Scanning...")
        self.controls.single_scan_button.configure(state="disabled")
        self.status.set_progress(0)
        self.status.set_status(f"Scanning {len(symbols)} symbol{'s' if len(symbols) != 1 else ''}...")
        threading.Thread(target=self._scan_worker, args=(symbols,), daemon=True).start()

    def _scan_worker(self, symbols: list[str]) -> None:
        items: list[ScanItem] = []
        max_workers = min(4, len(symbols))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._scan_service.scan_symbol, symbol): symbol for symbol in symbols}
            total = len(futures)
            for completed, future in enumerate(as_completed(futures), start=1):
                symbol = futures[future]
                try:
                    items.append(future.result())
                except Exception as exc:
                    items.append(ScanItem(symbol=symbol, error=str(exc)))
                self.after(0, self._scan_progress, completed, total, symbol)
        order = {symbol: index for index, symbol in enumerate(symbols)}
        items.sort(key=lambda item: order[item.symbol])
        self.after(0, self._scan_complete, items)

    def _scan_progress(self, completed: int, total: int, symbol: str) -> None:
        self.status.set_progress(completed / total)
        self.status.set_status(f"Scanned {symbol} • {completed}/{total}")

    def _scan_complete(self, items: list[ScanItem]) -> None:
        self._scanning = False
        self._items = {item.symbol: item for item in items}
        self.controls.scan_button.configure(state="normal", text="Scan Market")
        self.controls.single_scan_button.configure(state="normal")
        self._render_results(items)
        errors = sum(item.error is not None for item in items)
        actionable = sum(item.candidate is not None and item.candidate.actionable for item in items)
        self.status.set_progress(1.0)
        self.status.set_status(f"Scan complete • {len(items)} symbols • {actionable} actionable • {errors} errors")

    def _render_results(self, items: list[ScanItem]) -> None:
        rows = []
        for item in items:
            if item.error:
                rows.append((item.symbol, "ERROR", "ERROR", "—", "—", "—", item.error, "—"))
                continue
            candidate = item.candidate
            if candidate is None:
                rows.append((item.symbol, "WATCH", "NO RESULT", "—", "—", "—", "—", "—"))
                continue
            status = "ACTIONABLE" if candidate.actionable else "WATCH"
            rows.append((item.symbol, status, candidate.qualification.value, f"{candidate.base_score:.3f}", f"{candidate.net_pressure:.3f}", f"{candidate.confidence:.3f}", ", ".join(candidate.scoring_evidence_codes), candidate.week or "—"))
        self.results.show(rows)

    def _result_selected(self, symbol: str | None) -> None:
        if not symbol:
            return
        self._selected_symbol = symbol
        item = self._items.get(symbol)
        if item is None:
            return
        if item.error:
            self.detail.show(f"{symbol}\n\nERROR\n\n{item.error}")
            return
        candidate = item.candidate
        if candidate is None:
            self.detail.show(f"{symbol}\n\nNo scanner result.")
            return
        self.detail.show(f"{symbol}\n\nQualification: {candidate.qualification.value}\nActionable: {'YES' if candidate.actionable else 'NO'}\nScore: {candidate.base_score:.3f}\nNet pressure: {candidate.net_pressure:.3f}\nConfidence: {candidate.confidence:.3f}\n\nDecision:\n{candidate.reason}\n\nVSA evidence:\n{', '.join(candidate.scoring_evidence_codes) or 'None'}")

    def _close(self) -> None:
        self._auto_scan = False
        if self._auto_after_id is not None:
            self.after_cancel(self._auto_after_id)
        self.destroy()


def main() -> None:
    ProVSAApp().mainloop()


if __name__ == "__main__":
    main()
