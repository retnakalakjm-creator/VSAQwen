from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WEIGHT_FILE = ROOT / "trend_weight_counterfactual.csv"
OUTCOME_FILE = ROOT / "trend_outcome_audit.csv"
OUTPUT_FILE = ROOT / "trend_outcome_clamp_audit.csv"

UPPER_LIMIT = 2.00
LOWER_LIMIT = 0.50
WEIGHT_TOLERANCE = 1e-9

KEYS = [
    "event",
    "trend_state",
    "symbol",
    "week",
]

FOCUS = {
    ("UPTHRUST", "HEALTHY"),
    ("UPTHRUST", "EXHAUSTED"),
    ("SUPPLY_COMING_IN", "HEALTHY"),
    ("SUPPLY_COMING_IN", "EXHAUSTED"),
}


def normalize_keys(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for column in ("event", "trend_state", "symbol"):
        df[column] = (
            df[column]
            .astype(str)
            .str.strip()
        )

    df["event"] = df["event"].str.upper()
    df["trend_state"] = df["trend_state"].str.upper()
    df["week"] = pd.to_datetime(
        df["week"],
        errors="raise",
    ).dt.normalize()

    return df


def classify_clamp(raw_weight: float) -> str:
    if raw_weight >= UPPER_LIMIT:
        return "UPPER"

    if raw_weight <= LOWER_LIMIT:
        return "LOWER"

    return "NONE"


# --------------------------------------------------
# Load
# --------------------------------------------------

weights = pd.read_csv(WEIGHT_FILE)
outcomes = pd.read_csv(OUTCOME_FILE)

weight_required = {
    *KEYS,
    "weight",
    "weight_without_trend",
    "trend_adjustment",
}

outcome_required = {
    *KEYS,
    "weight",
    "return_1w",
    "return_2w",
    "return_4w",
    "return_8w",
    "mfe_8w",
    "mae_8w",
}

missing = weight_required - set(weights.columns)

if missing:
    raise ValueError(
        f"Weight file missing columns: {sorted(missing)}"
    )

missing = outcome_required - set(outcomes.columns)

if missing:
    raise ValueError(
        f"Outcome file missing columns: {sorted(missing)}"
    )

weights = normalize_keys(weights)
outcomes = normalize_keys(outcomes)


# --------------------------------------------------
# Reconstruct pre-clamp weight
# --------------------------------------------------

weights["raw_weight"] = (
    weights["weight_without_trend"]
    + weights["trend_adjustment"]
)

weights["clamp_state"] = weights["raw_weight"].map(
    classify_clamp
)


# --------------------------------------------------
# Collapse duplicate observations belonging to the
# same event case.
#
# The weight audit may contain several rows for the
# same (event, trend_state, symbol, week), because the
# underlying historical scan can observe the same weekly
# event on more than one source bar.
#
# These rows are NOT separate trading cases. We therefore
# deduplicate only when all scoring-relevant fields agree.
# bar_index is deliberately excluded from the identity.
# --------------------------------------------------

case_columns = KEYS + [
    "weight",
    "raw_weight",
    "weight_without_trend",
    "trend_adjustment",
    "trend_direction",
    "structural_pattern",
    "quality",
    "base_weight",
    "environment_adjustment",
    "structural_adjustment",
    "trend_effect_pct",
    "clamp_state",
]

available_case_columns = [
    column
    for column in case_columns
    if column in weights.columns
]

scoring_columns = [
    column
    for column in available_case_columns
    if column not in KEYS
]

# First verify that duplicate case keys never contain conflicting
# scoring information. If they do, the audit must stop rather than
# arbitrarily selecting or averaging different weights.
conflicts = []

for key, group in weights.groupby(KEYS, dropna=False):
    if len(group) <= 1:
        continue

    distinct = group[scoring_columns].drop_duplicates()

    if len(distinct) > 1:
        conflicts.append((*key, len(group), len(distinct)))

if conflicts:
    conflict_df = pd.DataFrame(
        conflicts,
        columns=[*KEYS, "rows", "distinct_scoring_rows"],
    )

    raise ValueError(
        "Conflicting scoring rows exist for the same event case. "
        "Do not deduplicate these automatically.\n"
        f"{conflict_df.head(20).to_string(index=False)}"
    )

before = len(weights)

weights = weights.drop_duplicates(
    subset=available_case_columns,
).copy()

deduplicated = before - len(weights)


# --------------------------------------------------
# Match each selected outcome case.
#
# The outcome file contains one trading case per event/week.
# The weight file may contain repeated observations of that
# same case, which were collapsed above.
# Production weight remains part of the match validation.
# --------------------------------------------------

candidate_columns = KEYS + [
    "weight",
    "raw_weight",
    "weight_without_trend",
    "trend_adjustment",
    "clamp_state",
]

candidates = weights[candidate_columns].copy()

merged = outcomes.merge(
    candidates,
    on=KEYS,
    how="left",
    suffixes=("_outcome", "_weight"),
)

merged["weight_difference"] = (
    merged["weight_outcome"]
    - merged["weight_weight"]
).abs()

matched = merged[
    merged["weight_difference"] <= WEIGHT_TOLERANCE
].copy()


# --------------------------------------------------
# Validate that every outcome case resolves to one
# unambiguous weight record.
# --------------------------------------------------

match_counts = (
    matched.groupby(KEYS, dropna=False)
    .size()
)

ambiguous = match_counts[match_counts > 1]

if not ambiguous.empty:
    examples = ambiguous.reset_index(name="matches")

    raise ValueError(
        "Ambiguous weight matches remain after deduplication and "
        "matching on production weight.\n"
        f"{examples.head(20).to_string(index=False)}"
    )


outcome_counts = (
    outcomes.groupby(KEYS, dropna=False)
    .size()
)

duplicate_outcomes = outcome_counts[outcome_counts > 1]

if not duplicate_outcomes.empty:
    examples = duplicate_outcomes.reset_index(name="rows")

    raise ValueError(
        "Outcome file contains duplicate trading cases.\n"
        f"{examples.head(20).to_string(index=False)}"
    )


outcome_keys = outcomes.set_index(KEYS).index
matched_keys = matched.set_index(KEYS).index

missing_keys = outcome_keys.difference(matched_keys)

if len(missing_keys):
    missing_rows = outcomes.set_index(KEYS).loc[
        missing_keys
    ].reset_index()

    raise ValueError(
        "Some outcome cases could not be matched to their "
        "weight record.\n"
        f"{missing_rows.head(20).to_string(index=False)}"
    )


# Restore outcome columns and selected weight columns.
merged = matched[
    KEYS
    + [
        "weight_outcome",
        "raw_weight",
        "weight_without_trend",
        "trend_adjustment",
        "clamp_state",
    ]
].copy()

merged = merged.rename(
    columns={
        "weight_outcome": "weight",
    }
)

# Add outcome measurements back using the normalized keys.
merged = merged.merge(
    outcomes,
    on=KEYS + ["weight"],
    how="left",
    validate="one_to_one",
    suffixes=("", "_outcome"),
)


# --------------------------------------------------
# Focused audit
# --------------------------------------------------

focus = merged[
    merged[["event", "trend_state"]]
    .apply(tuple, axis=1)
    .isin(FOCUS)
].copy()


# --------------------------------------------------
# Outcome summary
# --------------------------------------------------

summary = (
    focus.groupby(
        ["event", "trend_state", "clamp_state"],
        dropna=False,
    )
    .agg(
        cases=("weight", "count"),
        avg_weight=("weight", "mean"),
        avg_raw_weight=("raw_weight", "mean"),
        avg_return_1w=("return_1w", "mean"),
        median_return_1w=("return_1w", "median"),
        avg_return_2w=("return_2w", "mean"),
        median_return_2w=("return_2w", "median"),
        avg_return_4w=("return_4w", "mean"),
        median_return_4w=("return_4w", "median"),
        avg_return_8w=("return_8w", "mean"),
        median_return_8w=("return_8w", "median"),
        avg_mfe_8w=("mfe_8w", "mean"),
        median_mfe_8w=("mfe_8w", "median"),
        avg_mae_8w=("mae_8w", "mean"),
        median_mae_8w=("mae_8w", "median"),
    )
    .reset_index()
)


# --------------------------------------------------
# Detailed UPTHRUST / EXHAUSTED cases that hit
# the upper clamp.
# --------------------------------------------------

clamped = focus[
    (focus["event"] == "UPTHRUST")
    & (focus["trend_state"] == "EXHAUSTED")
    & (focus["clamp_state"] == "UPPER")
].copy()

columns = [
    "symbol",
    "week",
    "weight",
    "raw_weight",
    "trend_adjustment",
    "return_1w",
    "return_2w",
    "return_4w",
    "return_8w",
    "mfe_8w",
    "mae_8w",
]


print()
print("=" * 130)
print("CLAMP vs OUTCOME AUDIT")
print("=" * 130)
print()
print(f"Outcome cases: {len(outcomes)}")
print(f"Weight rows after case deduplication: {len(weights)}")
print(f"Duplicate observation rows removed: {deduplicated}")
print(f"Matched cases: {len(merged)}")
print(f"Focused cases: {len(focus)}")
print()

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.3f}",
    )
)

print()
print("=" * 130)
print("UPTHRUST / EXHAUSTED — UPPER-CLAMPED CASES")
print("=" * 130)
print()

print(
    clamped[columns]
    .sort_values("raw_weight", ascending=False)
    .to_string(
        index=False,
        float_format=lambda x: f"{x:.3f}",
    )
)


# --------------------------------------------------
# Save
# --------------------------------------------------

summary.to_csv(
    OUTPUT_FILE,
    index=False,
)

print()
print(f"Output: {OUTPUT_FILE}")
