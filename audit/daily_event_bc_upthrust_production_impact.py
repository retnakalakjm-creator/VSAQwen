"""Production-impact audit for promoted BUYING_CLIMAX / UPTHRUST semantics.

The audit compares the canonical pre-change daily-event inventory with a
post-change inventory produced from the exact same frozen input snapshot.

Hard gates:
* post-change BUYING_CLIMAX identities exactly equal the frozen L17 exhaustion
  candidate;
* post-change UPTHRUST identities exactly equal the frozen L17 structural
  rejection candidate;
* every non-BC/UPTHRUST event identity remains unchanged;
* non-target attributes remain unchanged except for Spring quality changes that
  are exactly implied by Spring's existing same-bar BC/UPTHRUST conflict rule;
* the before inventory still contains the canonical 4,497 / 4,497 identical
  BC/UPTHRUST firing sets.

The score-impact section mirrors EvidenceAggregator._calculate_event_contribution
on each (symbol, bar_index, session, direction) event group. It is an event
contribution impact, not a trading score or actionability decision.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from statistics import fmean
import pandas as pd

import config
from audit.daily_event_bc_upthrust_semantic_replay import (
    BC_ACCEPTANCE_STRONG,
    DAILY_BC_UPTHRUST_SEMANTIC_REPLAY_AUDIT_ID,
)
from audit.daily_event_inventory import DAILY_EVENT_INVENTORY_AUDIT_ID
from models import EvidenceCode


DAILY_BC_UPTHRUST_PRODUCTION_IMPACT_AUDIT_ID = (
    "daily-event-bc-upthrust-production-impact-v1"
)

BC_CODE = EvidenceCode.BUYING_CLIMAX.value
UT_CODE = EvidenceCode.UPTHRUST.value
_CHANGED_CODES = frozenset((BC_CODE, UT_CODE))
SPRING_CODE = EvidenceCode.SPRING.value
_SPRING_CONFLICT_QUALITY = 0.50
_SPRING_BASE_QUALITY = 1.00

_GROUP_IDENTITY = ("symbol", "bar_index", "session", "direction")
_NON_TARGET_IDENTITY = (
    "symbol",
    "bar_index",
    "session",
    "code",
    "occurrence_on_bar_code",
)
_NON_TARGET_STABLE_ATTRIBUTES = (
    "category",
    "direction",
    "strength",
    "weight",
    "test_index",
    "recovery_index",
)


@dataclass(frozen=True, slots=True)
class ProductionImpactLineage:
    before_summary_sha256: str
    before_emissions_sha256: str
    after_summary_sha256: str
    after_emissions_sha256: str
    l17_summary_sha256: str
    l17_observations_sha256: str
    snapshot_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class ProductionCodeImpactRow:
    code: str
    before_count: int
    after_count: int
    count_delta: int
    before_symbol_count: int
    after_symbol_count: int
    removed_identity_count: int
    added_identity_count: int
    common_identity_count: int


@dataclass(frozen=True, slots=True)
class ProductionPairImpactRow:
    phase: str
    bc_count: int
    ut_count: int
    overlap_count: int
    union_count: int
    jaccard: float
    relationship: str


@dataclass(frozen=True, slots=True)
class ProductionContributionChangeRow:
    symbol: str
    bar_index: int
    session: str
    direction: str
    before_contribution: float
    after_contribution: float
    contribution_delta: float
    before_codes: tuple[str, ...]
    after_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductionSymbolImpactRow:
    symbol: str
    changed_event_group_count: int
    increased_event_group_count: int
    decreased_event_group_count: int
    before_contribution_sum: float
    after_contribution_sum: float
    contribution_delta_sum: float


@dataclass(frozen=True, slots=True)
class BcUpthrustProductionImpactAudit:
    audit_id: str
    source_lineage: ProductionImpactLineage
    requested_symbol_count: int
    evaluated_bar_count: int
    before_bc_count: int
    before_ut_count: int
    before_overlap_count: int
    after_bc_count: int
    after_ut_count: int
    after_overlap_count: int
    expected_bc_count: int
    expected_ut_count: int
    expected_overlap_count: int
    bc_candidate_identity_mismatch_count: int
    ut_candidate_identity_mismatch_count: int
    non_target_identity_drift_count: int
    unexpected_non_target_attribute_drift_count: int
    spring_conflict_quality_change_count: int
    non_target_emission_drift_count: int
    changed_event_group_count: int
    increased_event_group_count: int
    decreased_event_group_count: int
    total_before_event_contribution: float
    total_after_event_contribution: float
    total_event_contribution_delta: float
    mean_absolute_changed_group_delta: float
    max_absolute_changed_group_delta: float
    code_rows: tuple[ProductionCodeImpactRow, ...]
    pair_rows: tuple[ProductionPairImpactRow, ...]
    contribution_rows: tuple[ProductionContributionChangeRow, ...]
    symbol_rows: tuple[ProductionSymbolImpactRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class BcUpthrustProductionImpactPaths:
    summary_json: Path
    code_impact_csv: Path
    pair_impact_csv: Path
    contribution_changes_csv: Path
    symbol_impact_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _normalize_session(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"cannot parse boolean value: {value!r}")


def _load_inventory(
    root: Path,
) -> tuple[dict[str, object], pd.DataFrame, Path, Path]:
    summary_path = root / "daily_event_inventory_summary.json"
    emissions_path = root / "daily_event_emissions.csv"
    if not summary_path.exists():
        raise FileNotFoundError(summary_path)
    if not emissions_path.exists():
        raise FileNotFoundError(emissions_path)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != DAILY_EVENT_INVENTORY_AUDIT_ID:
        raise ValueError("unexpected daily-event inventory audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("inventory source must remain non-actionable")
    if int(summary.get("failed_symbol_count", -1)) != 0:
        raise ValueError("inventory source contains symbol failures")
    if int(summary.get("requested_symbol_count", -1)) != 30:
        raise ValueError("production impact requires canonical 30 symbols")
    if int(summary.get("evaluated_bar_count", -1)) != 198382:
        raise ValueError("production impact requires canonical evaluated bars")

    provenance = summary.get("input_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("inventory input provenance is missing")
    if provenance.get("source") != "FROZEN_DAILY_INPUT_SNAPSHOT":
        raise ValueError("production impact requires frozen snapshot inventory")
    if provenance.get("snapshot_period") != "max":
        raise ValueError("production impact requires full-history snapshot")

    frame = pd.read_csv(emissions_path)
    required = {
        "symbol",
        "bar_index",
        "session",
        "code",
        "category",
        "direction",
        "strength",
        "weight",
        "quality",
        "test_index",
        "recovery_index",
        "occurrence_on_bar_code",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"inventory emissions missing columns: {missing}")

    frame = frame.copy()
    frame["symbol"] = frame["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    frame["bar_index"] = frame["bar_index"].astype(int)
    frame["session"] = frame["session"].map(_normalize_session)
    frame["code"] = frame["code"].map(str)
    frame["direction"] = frame["direction"].map(str)
    frame["occurrence_on_bar_code"] = frame[
        "occurrence_on_bar_code"
    ].astype(int)

    if frame[
        ["symbol", "bar_index", "session", "code", "occurrence_on_bar_code"]
    ].duplicated().any():
        raise ValueError("inventory emission rows are not uniquely identified")

    return summary, frame, summary_path, emissions_path


def _load_l17_candidates(
    root: Path,
) -> tuple[
    dict[str, object],
    set[tuple[str, int, str]],
    set[tuple[str, int, str]],
    Path,
    Path,
]:
    summary_path = root / "daily_bc_upthrust_semantic_summary.json"
    observations_path = root / "daily_bc_upthrust_semantic_observations.csv"
    if not summary_path.exists():
        raise FileNotFoundError(summary_path)
    if not observations_path.exists():
        raise FileNotFoundError(observations_path)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        summary.get("audit_id")
        != DAILY_BC_UPTHRUST_SEMANTIC_REPLAY_AUDIT_ID
    ):
        raise ValueError("unexpected L17 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L17 source must remain non-actionable")

    frame = pd.read_csv(observations_path)
    required = {
        "symbol",
        "bar_index",
        "session",
        "bc_effort_core",
        "bc_acceptance",
        "ut_structural_rejection",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"L17 observations missing columns: {missing}")

    frame = frame.copy()
    frame["symbol"] = frame["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    frame["bar_index"] = frame["bar_index"].astype(int)
    frame["session"] = frame["session"].map(_normalize_session)
    frame["bc_effort_core"] = frame["bc_effort_core"].map(_parse_bool)
    frame["ut_structural_rejection"] = frame[
        "ut_structural_rejection"
    ].map(_parse_bool)

    bc_mask = (
        frame["bc_effort_core"]
        & (frame["bc_acceptance"].astype(str) != BC_ACCEPTANCE_STRONG)
    )
    ut_mask = frame["ut_structural_rejection"]

    def identities(mask: pd.Series) -> set[tuple[str, int, str]]:
        selected = frame.loc[mask, ["symbol", "bar_index", "session"]]
        return {
            (str(row.symbol), int(row.bar_index), str(row.session))
            for row in selected.itertuples(index=False)
        }

    bc_ids = identities(bc_mask)
    ut_ids = identities(ut_mask)
    if len(bc_ids) != 887 or len(ut_ids) != 10526:
        raise ValueError("L17 frozen candidate counts changed")
    if len(bc_ids & ut_ids) != 129:
        raise ValueError("L17 frozen candidate overlap changed")

    return summary, bc_ids, ut_ids, summary_path, observations_path


def _code_identity_set(
    frame: pd.DataFrame,
    code: str,
) -> set[tuple[str, int, str]]:
    selected = frame.loc[frame["code"] == code]
    return {
        (str(row.symbol), int(row.bar_index), str(row.session))
        for row in selected.itertuples(index=False)
    }


def _relation(
    a: set[tuple[str, int, str]],
    b: set[tuple[str, int, str]],
) -> str:
    if a == b:
        return "IDENTICAL_FIRING_SET"
    if not (a & b):
        return "DISJOINT"
    if a < b:
        return "BC_STRICT_SUBSET_OF_UT"
    if b < a:
        return "UT_STRICT_SUBSET_OF_BC"
    return "PARTIAL_OVERLAP"


def _pair_row(
    phase: str,
    bc_ids: set[tuple[str, int, str]],
    ut_ids: set[tuple[str, int, str]],
) -> ProductionPairImpactRow:
    overlap = bc_ids & ut_ids
    union = bc_ids | ut_ids
    return ProductionPairImpactRow(
        phase=phase,
        bc_count=len(bc_ids),
        ut_count=len(ut_ids),
        overlap_count=len(overlap),
        union_count=len(union),
        jaccard=len(overlap) / len(union) if union else 0.0,
        relationship=_relation(bc_ids, ut_ids),
    )


@dataclass(frozen=True, slots=True)
class _NonTargetChangeSummary:
    identity_drift_count: int
    unexpected_attribute_drift_count: int
    spring_conflict_quality_change_count: int

    @property
    def disallowed_drift_count(self) -> int:
        return (
            self.identity_drift_count
            + self.unexpected_attribute_drift_count
        )


def _values_equal(before: object, after: object) -> bool:
    if pd.isna(before) and pd.isna(after):
        return True
    if isinstance(before, float) or isinstance(after, float):
        try:
            return math.isclose(
                float(before),
                float(after),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        except (TypeError, ValueError):
            return before == after
    return before == after


def _non_target_row_map(
    frame: pd.DataFrame,
) -> dict[tuple[object, ...], object]:
    selected = frame.loc[~frame["code"].isin(_CHANGED_CODES)]
    return {
        tuple(getattr(row, column) for column in _NON_TARGET_IDENTITY): row
        for row in selected.itertuples(index=False)
    }


def _conflict_bar_identities(
    frame: pd.DataFrame,
) -> set[tuple[str, int, str]]:
    selected = frame.loc[
        frame["code"].isin(_CHANGED_CODES),
        ["symbol", "bar_index", "session"],
    ]
    return {
        (str(row.symbol), int(row.bar_index), str(row.session))
        for row in selected.itertuples(index=False)
    }


def _spring_quality_matches_conflict(
    quality: object,
    *,
    has_conflict: bool,
) -> bool:
    expected = (
        _SPRING_CONFLICT_QUALITY
        if has_conflict
        else _SPRING_BASE_QUALITY
    )
    try:
        return math.isclose(
            float(quality),
            expected,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    except (TypeError, ValueError):
        return False


def _non_target_change_summary(
    before: pd.DataFrame,
    after: pd.DataFrame,
) -> _NonTargetChangeSummary:
    before_rows = _non_target_row_map(before)
    after_rows = _non_target_row_map(after)
    before_keys = set(before_rows)
    after_keys = set(after_rows)

    identity_drift = len(before_keys ^ after_keys)
    unexpected_attribute_drift = 0
    spring_quality_changes = 0

    before_conflicts = _conflict_bar_identities(before)
    after_conflicts = _conflict_bar_identities(after)

    for key in before_keys & after_keys:
        before_row = before_rows[key]
        after_row = after_rows[key]

        stable_changed = any(
            not _values_equal(
                getattr(before_row, column),
                getattr(after_row, column),
            )
            for column in _NON_TARGET_STABLE_ATTRIBUTES
        )
        quality_changed = not _values_equal(
            before_row.quality,
            after_row.quality,
        )

        if not stable_changed and not quality_changed:
            continue

        code = str(key[3])
        if stable_changed or code != SPRING_CODE:
            unexpected_attribute_drift += 1
            continue

        bar_identity = (
            str(key[0]),
            int(key[1]),
            str(key[2]),
        )
        before_has_conflict = bar_identity in before_conflicts
        after_has_conflict = bar_identity in after_conflicts

        if before_has_conflict == after_has_conflict:
            unexpected_attribute_drift += 1
            continue

        if not _spring_quality_matches_conflict(
            before_row.quality,
            has_conflict=before_has_conflict,
        ):
            unexpected_attribute_drift += 1
            continue

        if not _spring_quality_matches_conflict(
            after_row.quality,
            has_conflict=after_has_conflict,
        ):
            unexpected_attribute_drift += 1
            continue

        spring_quality_changes += 1

    return _NonTargetChangeSummary(
        identity_drift_count=identity_drift,
        unexpected_attribute_drift_count=unexpected_attribute_drift,
        spring_conflict_quality_change_count=spring_quality_changes,
    )


def _code_rows(
    before: pd.DataFrame,
    after: pd.DataFrame,
) -> tuple[ProductionCodeImpactRow, ...]:
    codes = sorted(set(map(str, before["code"])) | set(map(str, after["code"])))
    rows: list[ProductionCodeImpactRow] = []
    for code in codes:
        before_ids = _code_identity_set(before, code)
        after_ids = _code_identity_set(after, code)
        rows.append(
            ProductionCodeImpactRow(
                code=code,
                before_count=int((before["code"] == code).sum()),
                after_count=int((after["code"] == code).sum()),
                count_delta=(
                    int((after["code"] == code).sum())
                    - int((before["code"] == code).sum())
                ),
                before_symbol_count=int(
                    before.loc[before["code"] == code, "symbol"].nunique()
                ),
                after_symbol_count=int(
                    after.loc[after["code"] == code, "symbol"].nunique()
                ),
                removed_identity_count=len(before_ids - after_ids),
                added_identity_count=len(after_ids - before_ids),
                common_identity_count=len(before_ids & after_ids),
            )
        )
    return tuple(rows)


def _event_contribution(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0

    primary_codes = {item.value for item in config.PRIMARY_VSA_CODES}
    supporting_codes = {item.value for item in config.SUPPORTING_VSA_CODES}
    effort_codes = {item.value for item in config.EFFORT_RESULT_CODES}
    structural_codes = {item.value for item in config.STRUCTURAL_CODES}

    frame = frame.copy()
    frame["weighted_strength"] = (
        frame["weight"].astype(float) * frame["strength"].astype(float)
    )

    primary = frame.loc[frame["code"].isin(primary_codes)]
    supporting = frame.loc[frame["code"].isin(supporting_codes)]
    effort = frame.loc[frame["code"].isin(effort_codes)]
    structural = frame.loc[frame["code"].isin(structural_codes)]

    primary_value = (
        float(primary["weighted_strength"].max())
        if not primary.empty
        else 0.0
    )
    supporting_value = (
        float(supporting["weighted_strength"].max())
        if not supporting.empty
        else 0.0
    )
    effort_value = (
        float(effort["weighted_strength"].max())
        if not effort.empty
        else 0.0
    )
    structural_value = (
        float(structural["weighted_strength"].max())
        if not structural.empty
        else 0.0
    )

    if not primary.empty:
        contribution = primary_value
        if not supporting.empty:
            contribution += (
                supporting_value * config.PRIMARY_SUPPORTING_MODIFIER
            )
        if not effort.empty:
            contribution += (
                effort_value * config.PRIMARY_EFFORT_RESULT_MODIFIER
            )
        if not structural.empty:
            contribution += (
                structural_value * config.PRIMARY_STRUCTURAL_MODIFIER
            )
        return contribution

    return (
        supporting_value * config.SUPPORTING_BASE_WEIGHT
        + effort_value * config.EFFORT_RESULT_BASE_WEIGHT
        + structural_value * config.STRUCTURAL_BASE_WEIGHT
    )


def _grouped_contributions(
    frame: pd.DataFrame,
) -> dict[tuple[str, int, str, str], tuple[float, tuple[str, ...]]]:
    result: dict[
        tuple[str, int, str, str],
        tuple[float, tuple[str, ...]],
    ] = {}
    for identity, group in frame.groupby(list(_GROUP_IDENTITY), sort=True):
        key = (
            str(identity[0]),
            int(identity[1]),
            str(identity[2]),
            str(identity[3]),
        )
        result[key] = (
            _event_contribution(group),
            tuple(sorted(map(str, group["code"]))),
        )
    return result


def _contribution_rows(
    before: pd.DataFrame,
    after: pd.DataFrame,
) -> tuple[
    tuple[ProductionContributionChangeRow, ...],
    tuple[ProductionSymbolImpactRow, ...],
    float,
    float,
]:
    before_groups = _grouped_contributions(before)
    after_groups = _grouped_contributions(after)
    all_keys = sorted(set(before_groups) | set(after_groups))

    changes: list[ProductionContributionChangeRow] = []
    symbol_accumulator: dict[str, dict[str, float | int]] = {}

    total_before = sum(value[0] for value in before_groups.values())
    total_after = sum(value[0] for value in after_groups.values())

    for key in all_keys:
        before_value, before_codes = before_groups.get(key, (0.0, ()))
        after_value, after_codes = after_groups.get(key, (0.0, ()))
        delta = after_value - before_value
        if math.isclose(delta, 0.0, abs_tol=1e-12):
            continue

        symbol, bar_index, session, direction = key
        changes.append(
            ProductionContributionChangeRow(
                symbol=symbol,
                bar_index=bar_index,
                session=session,
                direction=direction,
                before_contribution=before_value,
                after_contribution=after_value,
                contribution_delta=delta,
                before_codes=before_codes,
                after_codes=after_codes,
            )
        )

        acc = symbol_accumulator.setdefault(
            symbol,
            {
                "changed": 0,
                "increased": 0,
                "decreased": 0,
                "before": 0.0,
                "after": 0.0,
            },
        )
        acc["changed"] = int(acc["changed"]) + 1
        if delta > 0:
            acc["increased"] = int(acc["increased"]) + 1
        else:
            acc["decreased"] = int(acc["decreased"]) + 1
        acc["before"] = float(acc["before"]) + before_value
        acc["after"] = float(acc["after"]) + after_value

    symbol_rows = tuple(
        ProductionSymbolImpactRow(
            symbol=symbol,
            changed_event_group_count=int(values["changed"]),
            increased_event_group_count=int(values["increased"]),
            decreased_event_group_count=int(values["decreased"]),
            before_contribution_sum=float(values["before"]),
            after_contribution_sum=float(values["after"]),
            contribution_delta_sum=(
                float(values["after"]) - float(values["before"])
            ),
        )
        for symbol, values in sorted(symbol_accumulator.items())
    )
    return tuple(changes), symbol_rows, total_before, total_after


def build_bc_upthrust_production_impact_audit(
    *,
    before_dir: str | Path,
    after_dir: str | Path,
    semantic_dir: str | Path,
) -> BcUpthrustProductionImpactAudit:
    (
        before_summary,
        before,
        before_summary_path,
        before_emissions_path,
    ) = _load_inventory(Path(before_dir))
    (
        after_summary,
        after,
        after_summary_path,
        after_emissions_path,
    ) = _load_inventory(Path(after_dir))
    (
        _l17_summary,
        expected_bc,
        expected_ut,
        l17_summary_path,
        l17_observations_path,
    ) = _load_l17_candidates(Path(semantic_dir))

    before_provenance = before_summary["input_provenance"]
    after_provenance = after_summary["input_provenance"]
    before_manifest = str(
        before_provenance["snapshot_manifest_sha256"]
    )
    after_manifest = str(
        after_provenance["snapshot_manifest_sha256"]
    )
    if before_manifest != after_manifest:
        raise ValueError("before/after inventory snapshot manifests differ")
    if before_manifest != (
        "45bb7123d2b3b570cf58241f09cb6175f6052d792f92728b"
        "194fc587762fb8ff"
    ):
        raise ValueError("unexpected canonical snapshot manifest")

    before_bc = _code_identity_set(before, BC_CODE)
    before_ut = _code_identity_set(before, UT_CODE)
    if len(before_bc) != 4497 or len(before_ut) != 4497:
        raise ValueError("pre-change canonical BC/UT counts changed")
    if before_bc != before_ut:
        raise ValueError("pre-change BC/UT firing sets are no longer identical")

    after_bc = _code_identity_set(after, BC_CODE)
    after_ut = _code_identity_set(after, UT_CODE)
    bc_mismatch = len(after_bc ^ expected_bc)
    ut_mismatch = len(after_ut ^ expected_ut)
    if bc_mismatch:
        raise ValueError(
            f"post-change BUYING_CLIMAX differs from frozen candidate: "
            f"{bc_mismatch} symmetric-difference identities"
        )
    if ut_mismatch:
        raise ValueError(
            f"post-change UPTHRUST differs from frozen candidate: "
            f"{ut_mismatch} symmetric-difference identities"
        )

    non_target_changes = _non_target_change_summary(
        before,
        after,
    )
    non_target_drift = non_target_changes.disallowed_drift_count
    if non_target_drift:
        raise ValueError(
            "unexpected non-BC/UPTHRUST drift: "
            f"identity={non_target_changes.identity_drift_count}, "
            "attributes="
            f"{non_target_changes.unexpected_attribute_drift_count}"
        )

    code_rows = _code_rows(before, after)
    pair_rows = (
        _pair_row("BEFORE", before_bc, before_ut),
        _pair_row("AFTER", after_bc, after_ut),
    )
    (
        contribution_rows,
        symbol_rows,
        total_before,
        total_after,
    ) = _contribution_rows(before, after)

    deltas = [abs(row.contribution_delta) for row in contribution_rows]
    increased = sum(row.contribution_delta > 0 for row in contribution_rows)
    decreased = sum(row.contribution_delta < 0 for row in contribution_rows)

    return BcUpthrustProductionImpactAudit(
        audit_id=DAILY_BC_UPTHRUST_PRODUCTION_IMPACT_AUDIT_ID,
        source_lineage=ProductionImpactLineage(
            before_summary_sha256=_sha256_file(before_summary_path),
            before_emissions_sha256=_sha256_file(before_emissions_path),
            after_summary_sha256=_sha256_file(after_summary_path),
            after_emissions_sha256=_sha256_file(after_emissions_path),
            l17_summary_sha256=_sha256_file(l17_summary_path),
            l17_observations_sha256=_sha256_file(l17_observations_path),
            snapshot_manifest_sha256=before_manifest,
        ),
        requested_symbol_count=30,
        evaluated_bar_count=198382,
        before_bc_count=len(before_bc),
        before_ut_count=len(before_ut),
        before_overlap_count=len(before_bc & before_ut),
        after_bc_count=len(after_bc),
        after_ut_count=len(after_ut),
        after_overlap_count=len(after_bc & after_ut),
        expected_bc_count=len(expected_bc),
        expected_ut_count=len(expected_ut),
        expected_overlap_count=len(expected_bc & expected_ut),
        bc_candidate_identity_mismatch_count=bc_mismatch,
        ut_candidate_identity_mismatch_count=ut_mismatch,
        non_target_identity_drift_count=(
            non_target_changes.identity_drift_count
        ),
        unexpected_non_target_attribute_drift_count=(
            non_target_changes.unexpected_attribute_drift_count
        ),
        spring_conflict_quality_change_count=(
            non_target_changes.spring_conflict_quality_change_count
        ),
        non_target_emission_drift_count=non_target_drift,
        changed_event_group_count=len(contribution_rows),
        increased_event_group_count=increased,
        decreased_event_group_count=decreased,
        total_before_event_contribution=total_before,
        total_after_event_contribution=total_after,
        total_event_contribution_delta=total_after - total_before,
        mean_absolute_changed_group_delta=(
            fmean(deltas) if deltas else 0.0
        ),
        max_absolute_changed_group_delta=max(deltas, default=0.0),
        code_rows=code_rows,
        pair_rows=pair_rows,
        contribution_rows=contribution_rows,
        symbol_rows=symbol_rows,
    )


def write_bc_upthrust_production_impact_audit(
    audit: BcUpthrustProductionImpactAudit,
    output_dir: str | Path,
) -> BcUpthrustProductionImpactPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = BcUpthrustProductionImpactPaths(
        summary_json=root / "daily_bc_upthrust_production_impact_summary.json",
        code_impact_csv=root / "daily_bc_upthrust_production_code_impact.csv",
        pair_impact_csv=root / "daily_bc_upthrust_production_pair_impact.csv",
        contribution_changes_csv=(
            root / "daily_bc_upthrust_production_contribution_changes.csv"
        ),
        symbol_impact_csv=(
            root / "daily_bc_upthrust_production_symbol_impact.csv"
        ),
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "evaluated_bar_count": audit.evaluated_bar_count,
        "before_bc_count": audit.before_bc_count,
        "before_ut_count": audit.before_ut_count,
        "before_overlap_count": audit.before_overlap_count,
        "after_bc_count": audit.after_bc_count,
        "after_ut_count": audit.after_ut_count,
        "after_overlap_count": audit.after_overlap_count,
        "expected_bc_count": audit.expected_bc_count,
        "expected_ut_count": audit.expected_ut_count,
        "expected_overlap_count": audit.expected_overlap_count,
        "bc_candidate_identity_mismatch_count": (
            audit.bc_candidate_identity_mismatch_count
        ),
        "ut_candidate_identity_mismatch_count": (
            audit.ut_candidate_identity_mismatch_count
        ),
        "non_target_identity_drift_count": (
            audit.non_target_identity_drift_count
        ),
        "unexpected_non_target_attribute_drift_count": (
            audit.unexpected_non_target_attribute_drift_count
        ),
        "spring_conflict_quality_change_count": (
            audit.spring_conflict_quality_change_count
        ),
        "non_target_emission_drift_count": (
            audit.non_target_emission_drift_count
        ),
        "changed_event_group_count": audit.changed_event_group_count,
        "increased_event_group_count": audit.increased_event_group_count,
        "decreased_event_group_count": audit.decreased_event_group_count,
        "total_before_event_contribution": (
            audit.total_before_event_contribution
        ),
        "total_after_event_contribution": audit.total_after_event_contribution,
        "total_event_contribution_delta": audit.total_event_contribution_delta,
        "mean_absolute_changed_group_delta": (
            audit.mean_absolute_changed_group_delta
        ),
        "max_absolute_changed_group_delta": (
            audit.max_absolute_changed_group_delta
        ),
        "code_row_count": len(audit.code_rows),
        "pair_row_count": len(audit.pair_rows),
        "contribution_change_row_count": len(audit.contribution_rows),
        "symbol_impact_row_count": len(audit.symbol_rows),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [asdict(row) for row in audit.code_rows]
    ).to_csv(paths.code_impact_csv, index=False)
    pd.DataFrame(
        [asdict(row) for row in audit.pair_rows]
    ).to_csv(paths.pair_impact_csv, index=False)
    pd.DataFrame(
        [
            {
                **asdict(row),
                "before_codes": "|".join(row.before_codes),
                "after_codes": "|".join(row.after_codes),
            }
            for row in audit.contribution_rows
        ]
    ).to_csv(paths.contribution_changes_csv, index=False)
    pd.DataFrame(
        [asdict(row) for row in audit.symbol_rows]
    ).to_csv(paths.symbol_impact_csv, index=False)
    return paths


__all__ = [
    "BC_CODE",
    "DAILY_BC_UPTHRUST_PRODUCTION_IMPACT_AUDIT_ID",
    "UT_CODE",
    "BcUpthrustProductionImpactAudit",
    "BcUpthrustProductionImpactPaths",
    "ProductionCodeImpactRow",
    "ProductionContributionChangeRow",
    "ProductionImpactLineage",
    "ProductionPairImpactRow",
    "ProductionSymbolImpactRow",
    "build_bc_upthrust_production_impact_audit",
    "write_bc_upthrust_production_impact_audit",
]
