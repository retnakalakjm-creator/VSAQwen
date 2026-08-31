from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import csv


@dataclass(frozen=True, slots=True)
class ContextSummary:
    code: str
    direction: str
    change: str
    cases: int
    mean_return: float
    mean_mfe: float
    mean_mae: float


def _read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def analyze_context(path: str | Path) -> list[ContextSummary]:
    rows = _read_rows(path)
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        change = row["change"]
        codes = [code for code in row["confirmation_only_codes"].split(",") if code]
        if not codes:
            continue
        direction = row.get("direction", "unknown")
        for code in codes:
            groups[(code, direction, change)].append(row)

    summaries: list[ContextSummary] = []
    for (code, direction, change), grouped in sorted(groups.items()):
        returns = [float(row["forward_return"]) for row in grouped if row["forward_return"]]
        mfes = [float(row["mfe"]) for row in grouped if row["mfe"]]
        maes = [float(row["mae"]) for row in grouped if row["mae"]]
        summaries.append(
            ContextSummary(
                code=code,
                direction=direction,
                change=change,
                cases=len(grouped),
                mean_return=sum(returns) / len(returns) if returns else 0.0,
                mean_mfe=sum(mfes) / len(mfes) if mfes else 0.0,
                mean_mae=sum(maes) / len(maes) if maes else 0.0,
            )
        )
    return summaries
