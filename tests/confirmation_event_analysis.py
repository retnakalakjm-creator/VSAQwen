from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True, slots=True)
class EventGroupResult:
    code: str
    cases: int
    true_to_false: int
    false_to_true: int
    mean_return: float | None
    mean_return_true_to_false: float | None
    mean_return_false_to_true: float | None
    mean_mfe: float | None
    mean_mae: float | None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _float(value: str) -> float | None:
    if value == "" or value.lower() == "none":
        return None
    return float(value)


def load_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def analyze_confirmation_events(rows: list[dict[str, str]]) -> list[EventGroupResult]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        codes = [code.strip() for code in row["confirmation_only_codes"].split(",") if code.strip()]
        for code in codes:
            groups[code].append(row)

    results: list[EventGroupResult] = []
    for code in sorted(groups):
        group = groups[code]
        returns = [v for row in group if (v := _float(row["forward_return"])) is not None]
        mfe = [v for row in group if (v := _float(row["mfe"])) is not None]
        mae = [v for row in group if (v := _float(row["mae"])) is not None]
        ttf_rows = [row for row in group if row["change"] == "True->False"]
        ftt_rows = [row for row in group if row["change"] == "False->True"]
        ttf_returns = [v for row in ttf_rows if (v := _float(row["forward_return"])) is not None]
        ftt_returns = [v for row in ftt_rows if (v := _float(row["forward_return"])) is not None]
        results.append(
            EventGroupResult(
                code=code,
                cases=len(group),
                true_to_false=len(ttf_rows),
                false_to_true=len(ftt_rows),
                mean_return=_mean(returns),
                mean_return_true_to_false=_mean(ttf_returns),
                mean_return_false_to_true=_mean(ftt_returns),
                mean_mfe=_mean(mfe),
                mean_mae=_mean(mae),
            )
        )
    return results


def render(results: list[EventGroupResult]) -> str:
    lines = [
        "=== CONFIRMATION EVENT ANALYSIS ===",
        f"{'Code':<24}{'Cases':>7}{'T->F':>7}{'F->T':>7}{'MeanRet':>12}{'T->F Ret':>12}{'F->T Ret':>12}{'MeanMFE':>12}{'MeanMAE':>12}",
    ]
    for item in results:
        fmt = lambda value: "n/a" if value is None else f"{value:+.4%}"
        lines.append(
            f"{item.code:<24}{item.cases:>7}{item.true_to_false:>7}{item.false_to_true:>7}"
            f"{fmt(item.mean_return):>12}{fmt(item.mean_return_true_to_false):>12}"
            f"{fmt(item.mean_return_false_to_true):>12}{fmt(item.mean_mfe):>12}{fmt(item.mean_mae):>12}"
        )
    return "\n".join(lines)


def analyze_file(path: str | Path) -> list[EventGroupResult]:
    return analyze_confirmation_events(load_rows(path))
