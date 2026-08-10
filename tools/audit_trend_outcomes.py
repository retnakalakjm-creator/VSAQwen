from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "cache"
VALIDATION_FILE = ROOT / "historical_validation.csv"

EVENTS = {
    "UPTHRUST": {"HEALTHY": 10, "EXHAUSTED": 10},
    "SUPPLY_COMING_IN": {"HEALTHY": 10, "EXHAUSTED": 10},
}

HORIZONS = (1, 2, 4, 8)


def load_validation() -> pd.DataFrame:
    df = pd.read_csv(VALIDATION_FILE)

    required = {
        "symbol",
        "bar_index",
        "week",
        "event",
        "trend_direction",
        "trend_state",
        "structural_pattern",
        "quality",
        "weight",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Validation file missing columns: {sorted(missing)}"
        )

    return df


def load_cache(symbol: str) -> pd.DataFrame:
    path = CACHE_DIR / f"{symbol}.csv"

    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path)

    required = {
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{path.name} missing columns: {sorted(missing)}"
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    return df


def weekly_ohlcv(daily: pd.DataFrame) -> pd.DataFrame:
    weekly = (
        daily.set_index("date")
        .resample("W-FRI")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )

    return weekly


def select_cases(validation: pd.DataFrame) -> pd.DataFrame:
    selected = []

    for event, states in EVENTS.items():
        for state, count in states.items():
            candidates = validation[
                (validation["event"] == event)
                & (validation["trend_state"] == state)
            ].copy()

            if candidates.empty:
                continue

            # Deterministic distribution across the available history.
            candidates = candidates.sort_values(
                ["symbol", "week", "bar_index"]
            )

            if len(candidates) <= count:
                chosen = candidates
            else:
                positions = (
                    pd.Series(
                        range(count)
                    )
                    * (len(candidates) - 1)
                    / (count - 1)
                ).round().astype(int)

                chosen = candidates.iloc[positions].copy()

            selected.append(chosen)

    if not selected:
        raise ValueError("No matching historical cases found.")

    return pd.concat(selected, ignore_index=True)


def calculate_outcome(
    weekly: pd.DataFrame,
    event_week: pd.Timestamp,
) -> dict[str, float | None]:
    dates = weekly["date"]

    matches = weekly.index[
        dates == event_week
    ]

    if len(matches) == 0:
        # Fall back to the containing week.
        matches = weekly.index[
            weekly["date"].dt.to_period("W")
            == event_week.to_period("W")
        ]

    if len(matches) == 0:
        return {
            f"return_{h}w": None
            for h in HORIZONS
        } | {
            "mfe_8w": None,
            "mae_8w": None,
        }

    event_index = int(matches[0])
    event_close = float(weekly.iloc[event_index]["close"])

    result: dict[str, float | None] = {}

    future = weekly.iloc[event_index + 1 :]

    for horizon in HORIZONS:
        if len(future) < horizon:
            result[f"return_{horizon}w"] = None
            continue

        future_close = float(
            future.iloc[horizon - 1]["close"]
        )

        result[f"return_{horizon}w"] = (
            future_close / event_close - 1.0
        ) * 100.0

    window = future.iloc[:8]

    if window.empty:
        result["mfe_8w"] = None
        result["mae_8w"] = None
    else:
        result["mfe_8w"] = (
            float(window["high"].max()) / event_close - 1.0
        ) * 100.0

        result["mae_8w"] = (
            float(window["low"].min()) / event_close - 1.0
        ) * 100.0

    return result


def main() -> None:
    validation = load_validation()
    cases = select_cases(validation)

    rows = []

    cache = {}

    for _, case in cases.iterrows():
        symbol = case["symbol"]

        if symbol not in cache:
            cache[symbol] = weekly_ohlcv(
                load_cache(symbol)
            )

        weekly = cache[symbol]

        event_week = pd.to_datetime(case["week"])

        outcome = calculate_outcome(
            weekly,
            event_week,
        )

        row = {
            "symbol": symbol,
            "bar_index": int(case["bar_index"]),
            "week": event_week.date(),
            "event": case["event"],
            "trend_direction": case["trend_direction"],
            "trend_state": case["trend_state"],
            "structural_pattern": case[
                "structural_pattern"
            ],
            "quality": float(case["quality"]),
            "weight": float(case["weight"]),
        }

        row.update(outcome)

        rows.append(row)

    result = pd.DataFrame(rows)

    output = ROOT / "trend_outcome_audit.csv"
    result.to_csv(output, index=False)

    print(f"Cases selected: {len(result)}")
    print(f"Output: {output}")
    print()

    print(
        result[
            [
                "event",
                "trend_state",
                "symbol",
                "week",
                "weight",
                "return_1w",
                "return_2w",
                "return_4w",
                "return_8w",
                "mfe_8w",
                "mae_8w",
            ]
        ].to_string(index=False)
    )

    print()
    print("SUMMARY")
    print()

    summary = (
        result.groupby(
            ["event", "trend_state"],
            dropna=False,
        )[
            [
                "return_1w",
                "return_2w",
                "return_4w",
                "return_8w",
                "mfe_8w",
                "mae_8w",
            ]
        ]
        .agg(["count", "mean", "median"])
        .round(2)
    )

    print(summary.to_string())


if __name__ == "__main__":
    main()