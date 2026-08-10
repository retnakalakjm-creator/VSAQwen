from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WEIGHT_FILE = ROOT / "trend_weight_counterfactual.csv"
OUTCOME_FILE = ROOT / "trend_outcome_audit.csv"
OUTPUT_FILE = ROOT / "trend_counterfactual_outcome_audit.csv"

KEYS = ["event", "trend_state", "symbol", "week"]
FOCUS = {
    ("UPTHRUST", "HEALTHY"),
    ("UPTHRUST", "EXHAUSTED"),
    ("SUPPLY_COMING_IN", "HEALTHY"),
    ("SUPPLY_COMING_IN", "EXHAUSTED"),
}
TOLERANCE = 1e-9


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ("event", "trend_state", "symbol"):
        df[col] = df[col].astype(str).str.strip()
    df["event"] = df["event"].str.upper()
    df["trend_state"] = df["trend_state"].str.upper()
    df["week"] = pd.to_datetime(df["week"], errors="raise").dt.normalize()
    return df


weights = normalize(pd.read_csv(WEIGHT_FILE))
outcomes = normalize(pd.read_csv(OUTCOME_FILE))

required_weights = set(KEYS) | {"weight", "weight_without_trend", "trend_adjustment"}
required_outcomes = set(KEYS) | {
    "weight", "return_1w", "return_2w", "return_4w", "return_8w", "mfe_8w", "mae_8w"
}

missing = required_weights - set(weights.columns)
if missing:
    raise ValueError(f"Weight file missing columns: {sorted(missing)}")
missing = required_outcomes - set(outcomes.columns)
if missing:
    raise ValueError(f"Outcome file missing columns: {sorted(missing)}")

# One historical trading case is one event/symbol/week/trend-state.
# Repeated source-bar observations are collapsed only when all scoring
# values agree.
scoring_cols = [
    "weight", "weight_without_trend", "trend_adjustment",
    *[c for c in [
        "trend_direction", "structural_pattern", "quality", "base_weight",
        "environment_adjustment", "structural_adjustment", "trend_effect_pct",
    ] if c in weights.columns],
]

conflicts = []
for key, group in weights.groupby(KEYS, dropna=False):
    if len(group) > 1 and len(group[scoring_cols].drop_duplicates()) > 1:
        conflicts.append((*key, len(group), len(group[scoring_cols].drop_duplicates())))

if conflicts:
    raise ValueError(
        "Conflicting scoring rows found for the same case:\n"
        + pd.DataFrame(
            conflicts, columns=[*KEYS, "rows", "distinct_scoring_rows"]
        ).head(20).to_string(index=False)
    )

weights = weights.drop_duplicates(subset=KEYS + scoring_cols).copy()

# Production outcome cases must be unique.
if outcomes.duplicated(KEYS).any():
    dup = outcomes[outcomes.duplicated(KEYS, keep=False)].sort_values(KEYS)
    raise ValueError("Duplicate outcome cases found:\n" + dup.head(20).to_string(index=False))

# Match on the case identity first, then verify the production weight.
merged = outcomes.merge(
    weights[KEYS + ["weight", "weight_without_trend", "trend_adjustment"]],
    on=KEYS,
    how="left",
    suffixes=("_outcome", "_weight"),
)

merged["weight_difference"] = (
    merged["weight_outcome"] - merged["weight_weight"]
).abs()

bad = merged[
    merged["weight_weight"].isna()
    | (merged["weight_difference"] > TOLERANCE)
]
if not bad.empty:
    raise ValueError(
        "Outcome cases with missing or inconsistent production weights:\n"
        + bad[KEYS + ["weight_outcome", "weight_weight"]].head(20).to_string(index=False)
    )

# Since the outcome file contains the selected production weight, retain it
# and calculate the counterfactual that removes only the trend adjustment.
merged["production_weight"] = merged["weight_outcome"]
merged["counterfactual_weight"] = (
    merged["production_weight"] - merged["trend_adjustment"]
)
merged["actual_trend_effect"] = (
    merged["production_weight"] - merged["counterfactual_weight"]
)

focus_mask = merged[["event", "trend_state"]].apply(tuple, axis=1).isin(FOCUS)
focus = merged.loc[focus_mask].copy()

# Counterfactual here is diagnostic only. It does NOT imply that historical
# returns should be mathematically reweighted. We compare outcomes of cases
# whose production weights differed because of the trend adjustment.
summary = (
    focus.groupby(["event", "trend_state"], dropna=False)
    .agg(
        cases=("production_weight", "count"),
        avg_trend_adjustment=("trend_adjustment", "mean"),
        avg_production_weight=("production_weight", "mean"),
        avg_counterfactual_weight=("counterfactual_weight", "mean"),
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

# Show the cases where the trend adjustment actually changed the production
# weight. This is the most useful inspection for the next tuning decision.
effective = focus[focus["trend_adjustment"].abs() > TOLERANCE].copy()

case_columns = [
    "event", "trend_state", "symbol", "week",
    "production_weight", "counterfactual_weight", "trend_adjustment",
    "return_1w", "return_2w", "return_4w", "return_8w", "mfe_8w", "mae_8w",
]

print()
print("=" * 130)
print("TREND ADJUSTMENT — COUNTERFACTUAL OUTCOME AUDIT")
print("=" * 130)
print()
print(f"Outcome cases: {len(outcomes)}")
print(f"Weight cases after deduplication: {len(weights)}")
print(f"Focused cases: {len(focus)}")
print(f"Cases with non-zero trend adjustment: {len(effective)}")
print()

print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

print()
print("=" * 130)
print("CASES ACTUALLY AFFECTED BY TREND ADJUSTMENT")
print("=" * 130)
print()

if effective.empty:
    print("No cases have a non-zero trend adjustment.")
else:
    print(
        effective[case_columns]
        .sort_values(["event", "trend_state", "symbol", "week"])
        .to_string(index=False, float_format=lambda x: f"{x:.3f}")
    )

summary.to_csv(OUTPUT_FILE, index=False)
print()
print(f"Output: {OUTPUT_FILE}")
