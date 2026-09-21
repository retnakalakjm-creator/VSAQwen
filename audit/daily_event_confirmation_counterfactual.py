"""Counterfactual audit for daily detector confirmation semantics.

L3 replays the canonical frozen daily-input snapshots and instruments the
existing K5 prefix-only evidence path. Production detector behavior is never
changed; confirmation outcomes are measured as read-only counterfactuals.
"""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pandas as pd

import evidence.demand as demand_module
import evidence.supply as supply_module
from audit.daily_event_cofiring import (
    DAILY_EVENT_COFIRING_AUDIT_ID,
    FrozenDailyEventLedgerLineage,
    load_frozen_daily_event_ledger,
)
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    daily_audit_input_manifest_sha256,
    load_daily_audit_input_bundle,
)
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    evaluate_daily_evidence_prefix,
    produce_offline_daily_evidence,
)
from evidence.helpers import evaluate_detector as production_evaluate_detector
from evidence.helpers import requirements_passed
from models import BackgroundContext, Evidence, EvidenceCode, Requirement


DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID = (
    "daily-event-confirmation-counterfactual-v1"
)

CONFIRMATION_SENSITIVE_CODES = frozenset(
    {
        EvidenceCode.BUYING_CLIMAX,
        EvidenceCode.NO_DEMAND,
        EvidenceCode.UPTHRUST,
        EvidenceCode.STOPPING_VOLUME,
        EvidenceCode.SELLING_CLIMAX,
        EvidenceCode.TEST,
        EvidenceCode.NO_SUPPLY,
    }
)

POLICY_CURRENT = "CURRENT_NO_CONFIRMATION_GATE"
POLICY_ANY = "ANY_CONFIRMATION"
POLICY_MAJORITY = "STRICT_MAJORITY_CONFIRMATIONS"
POLICY_ALL = "ALL_CONFIRMATIONS"
POLICIES = (
    POLICY_CURRENT,
    POLICY_ANY,
    POLICY_MAJORITY,
    POLICY_ALL,
)


def _normalize_session_identity(value: object) -> str:
    return pd.Timestamp(value).isoformat()


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class DailyConfirmationSourceLineage:
    snapshot_audit_id: str
    snapshot_manifest_sha256: str
    snapshot_basket_name: str
    snapshot_period: str
    snapshot_cutoff: str
    l1_audit_id: str
    l1_summary_sha256: str
    l1_emissions_sha256: str
    l2_audit_id: str
    l2_summary_sha256: str


@dataclass(frozen=True, slots=True)
class DailyConfirmationSources:
    lineage: DailyConfirmationSourceLineage
    bundle: DailyAuditInputBundle
    baseline: pd.DataFrame


@dataclass(frozen=True, slots=True)
class DailyConfirmationAuditFailure:
    symbol: str
    exception_type: str
    reason: str


@dataclass(frozen=True, slots=True)
class DailyConfirmationObservation:
    symbol: str
    bar_index: int
    session: str
    code: str
    confirmation_count: int
    passed_confirmation_count: int
    passed_confirmations: tuple[str, ...]
    failed_confirmations: tuple[str, ...]
    survives_any: bool
    survives_strict_majority: bool
    survives_all: bool


@dataclass(frozen=True, slots=True)
class DailyConfirmationPolicySummary:
    code: str
    policy: str
    current_event_count: int
    surviving_event_count: int
    removed_event_count: int
    survival_rate: float
    symbol_count: int


@dataclass(frozen=True, slots=True)
class DailyConfirmationPairwiseRow:
    policy: str
    code_a: str
    code_b: str
    code_a_count: int
    code_b_count: int
    overlap_count: int
    jaccard: float
    relationship: str


@dataclass(frozen=True, slots=True)
class DailyConfirmationBarIndexDrift:
    symbol: str
    session: str
    code: str
    baseline_bar_index: int
    captured_bar_index: int
    index_delta: int


@dataclass(frozen=True, slots=True)
class DailyConfirmationCounterfactualAudit:
    audit_id: str
    source_audit_id: str
    requested_symbol_count: int
    succeeded_symbol_count: int
    failed_symbol_count: int
    confirmation_sensitive_code_count: int
    physical_observation_count: int
    captured_event_count: int
    duplicate_observation_count: int
    baseline_event_count: int
    identity_mismatch_count: int
    bar_index_mismatch_count: int
    snapshot_worker_count: int
    source_lineage: DailyConfirmationSourceLineage
    policy_rows: tuple[DailyConfirmationPolicySummary, ...]
    pairwise_rows: tuple[DailyConfirmationPairwiseRow, ...]
    observations: tuple[DailyConfirmationObservation, ...]
    bar_index_drifts: tuple[DailyConfirmationBarIndexDrift, ...]
    failures: tuple[DailyConfirmationAuditFailure, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyConfirmationCounterfactualPaths:
    summary_json: Path
    observations_csv: Path
    policy_summary_csv: Path
    pairwise_csv: Path
    index_drift_csv: Path
    failures_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "observations_csv": str(self.observations_csv),
            "policy_summary_csv": str(self.policy_summary_csv),
            "pairwise_csv": str(self.pairwise_csv),
            "index_drift_csv": str(self.index_drift_csv),
            "failures_csv": str(self.failures_csv),
        }


@dataclass(slots=True)
class _ConfirmationRecorder:
    symbol: str = ""
    target_index: int = -1
    observations: list[DailyConfirmationObservation] | None = None

    def __post_init__(self) -> None:
        if self.observations is None:
            self.observations = []

    def set_target(self, *, symbol: str, target_index: int) -> None:
        self.symbol = symbol
        self.target_index = target_index

    def evaluate(
        self,
        *,
        evidence: list[Evidence],
        ctx: BackgroundContext,
        code: EvidenceCode,
        requirements: tuple[Requirement, ...],
        confirmations: tuple[Requirement, ...] = (),
        test_index: int | None = None,
        recovery_index: int | None = None,
        quality: float = 1.0,
    ) -> bool:
        if (
            code in CONFIRMATION_SENSITIVE_CODES
            and confirmations
            and ctx.current.bar_index == self.target_index
            and requirements_passed(requirements)
        ):
            passed = tuple(
                item.name for item in confirmations if item.passed
            )
            failed = tuple(
                item.name for item in confirmations if not item.passed
            )
            assert self.observations is not None
            self.observations.append(
                DailyConfirmationObservation(
                    symbol=self.symbol,
                    bar_index=ctx.current.bar_index,
                    session=_normalize_session_identity(
                        ctx.current.week_beginning
                    ),
                    code=code.value,
                    confirmation_count=len(confirmations),
                    passed_confirmation_count=len(passed),
                    passed_confirmations=passed,
                    failed_confirmations=failed,
                    survives_any=_policy_survives(
                        POLICY_ANY,
                        len(passed),
                        len(confirmations),
                    ),
                    survives_strict_majority=_policy_survives(
                        POLICY_MAJORITY,
                        len(passed),
                        len(confirmations),
                    ),
                    survives_all=_policy_survives(
                        POLICY_ALL,
                        len(passed),
                        len(confirmations),
                    ),
                )
            )

        return production_evaluate_detector(
            evidence=evidence,
            ctx=ctx,
            code=code,
            requirements=requirements,
            confirmations=confirmations,
            test_index=test_index,
            recovery_index=recovery_index,
            quality=quality,
        )


def _policy_survives(
    policy: str,
    passed_count: int,
    confirmation_count: int,
) -> bool:
    if confirmation_count <= 0:
        raise ValueError("confirmation_count must be positive")
    if not 0 <= passed_count <= confirmation_count:
        raise ValueError("passed_count outside confirmation range")

    if policy == POLICY_CURRENT:
        return True
    if policy == POLICY_ANY:
        return passed_count >= 1
    if policy == POLICY_MAJORITY:
        return passed_count * 2 > confirmation_count
    if policy == POLICY_ALL:
        return passed_count == confirmation_count
    raise ValueError(f"unsupported confirmation policy: {policy}")


@contextmanager
def _capture_confirmation_calls(
    recorder: _ConfirmationRecorder,
) -> Iterator[None]:
    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                supply_module,
                "evaluate_detector",
                recorder.evaluate,
            )
        )
        stack.enter_context(
            patch.object(
                demand_module,
                "evaluate_detector",
                recorder.evaluate,
            )
        )
        yield


def capture_symbol_confirmation_observations(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: str,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
) -> tuple[DailyConfirmationObservation, ...]:
    clean_symbol = str(symbol).strip().upper()
    recorder = _ConfirmationRecorder()

    def evaluator(prefix: pd.DataFrame) -> tuple[Evidence, ...]:
        recorder.set_target(
            symbol=clean_symbol,
            target_index=len(prefix) - 1,
        )
        return evaluate_daily_evidence_prefix(prefix)

    with _capture_confirmation_calls(recorder):
        produce_offline_daily_evidence(
            symbol=clean_symbol,
            daily=daily,
            now=now,
            min_target_index=min_target_index,
            prefix_evaluator=evaluator,
        )

    assert recorder.observations is not None
    return tuple(recorder.observations)


def _validate_l2_lineage(
    *,
    l2_dir: Path,
    l1_lineage: FrozenDailyEventLedgerLineage,
    requested_symbol_count: int,
) -> str:
    summary_path = l2_dir / "daily_event_cofiring_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing L2 summary: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != DAILY_EVENT_COFIRING_AUDIT_ID:
        raise ValueError("unexpected L2 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L2 source must remain non-actionable")
    if int(summary.get("requested_symbol_count", -1)) != requested_symbol_count:
        raise ValueError("L2 requested symbol count does not match L1")
    if int(summary.get("succeeded_symbol_count", -1)) != requested_symbol_count:
        raise ValueError("L3 requires a complete zero-failure L2 source")
    if int(summary.get("confirmation_sensitive_detector_count", -1)) != len(
        CONFIRMATION_SENSITIVE_CODES
    ):
        raise ValueError("L2 confirmation-sensitive detector count changed")
    if int(summary.get("non_gating_confirmation_detector_count", -1)) != len(
        CONFIRMATION_SENSITIVE_CODES
    ):
        raise ValueError("L2 non-gating confirmation finding changed")

    expected_lineage = asdict(l1_lineage)
    if summary.get("source_lineage") != expected_lineage:
        raise ValueError("L2 source lineage does not match canonical L1")

    return _sha256_file(summary_path)


def load_confirmation_sources(
    *,
    l1_dir: str | Path,
    l2_dir: str | Path,
    input_snapshot_dir: str | Path,
    basket_name: str,
) -> DailyConfirmationSources:
    l1_root = Path(l1_dir)
    l2_root = Path(l2_dir)
    snapshot_root = Path(input_snapshot_dir)

    ledger = load_frozen_daily_event_ledger(l1_root)
    if ledger.source_lineage is None:
        raise ValueError("L3 requires frozen L1 source lineage")
    l1_lineage = ledger.source_lineage

    bundle = load_daily_audit_input_bundle(snapshot_root)
    manifest_sha256 = daily_audit_input_manifest_sha256(snapshot_root)
    if bundle.basket_name != basket_name:
        raise ValueError("snapshot basket does not match requested basket")
    if l1_lineage.snapshot_basket_name != basket_name:
        raise ValueError("L1 snapshot basket does not match requested basket")
    if bundle.audit_id != l1_lineage.snapshot_audit_id:
        raise ValueError("snapshot audit id does not match L1 lineage")
    if manifest_sha256 != l1_lineage.snapshot_manifest_sha256:
        raise ValueError("snapshot manifest hash does not match L1 lineage")
    if bundle.period != l1_lineage.snapshot_period:
        raise ValueError("snapshot period does not match L1 lineage")
    if bundle.cutoff != l1_lineage.snapshot_cutoff:
        raise ValueError("snapshot cutoff does not match L1 lineage")
    if bundle.symbol_count != ledger.requested_symbol_count:
        raise ValueError("snapshot symbol count does not match L1")

    l2_summary_sha256 = _validate_l2_lineage(
        l2_dir=l2_root,
        l1_lineage=l1_lineage,
        requested_symbol_count=ledger.requested_symbol_count,
    )

    affected_values = {
        code.value for code in CONFIRMATION_SENSITIVE_CODES
    }
    baseline = (
        ledger.emissions.loc[
            ledger.emissions["code"].isin(affected_values),
            ["symbol", "bar_index", "session", "code"],
        ]
        .drop_duplicates()
        .sort_values(["symbol", "bar_index", "session", "code"])
        .reset_index(drop=True)
    )

    lineage = DailyConfirmationSourceLineage(
        snapshot_audit_id=l1_lineage.snapshot_audit_id,
        snapshot_manifest_sha256=l1_lineage.snapshot_manifest_sha256,
        snapshot_basket_name=l1_lineage.snapshot_basket_name,
        snapshot_period=l1_lineage.snapshot_period,
        snapshot_cutoff=l1_lineage.snapshot_cutoff,
        l1_audit_id=ledger.source_audit_id,
        l1_summary_sha256=l1_lineage.l1_summary_sha256,
        l1_emissions_sha256=l1_lineage.l1_emissions_sha256,
        l2_audit_id=DAILY_EVENT_COFIRING_AUDIT_ID,
        l2_summary_sha256=l2_summary_sha256,
    )
    return DailyConfirmationSources(
        lineage=lineage,
        bundle=bundle,
        baseline=baseline,
    )


def _observation_identity(
    item: DailyConfirmationObservation,
) -> tuple[str, str, str]:
    return (
        item.symbol,
        _normalize_session_identity(item.session),
        item.code,
    )


def _frame_identity(row: object) -> tuple[str, str, str]:
    return (
        str(getattr(row, "symbol")),
        _normalize_session_identity(getattr(row, "session")),
        str(getattr(row, "code")),
    )


def _deduplicate_observations(
    observations: tuple[DailyConfirmationObservation, ...],
) -> tuple[DailyConfirmationObservation, ...]:
    by_identity: dict[
        tuple[str, str, str],
        DailyConfirmationObservation,
    ] = {}
    for item in observations:
        identity = _observation_identity(item)
        existing = by_identity.get(identity)
        if existing is None:
            by_identity[identity] = item
            continue
        if existing != item:
            raise ValueError(
                "conflicting confirmation observations for stable identity "
                f"{identity!r}"
            )

    return tuple(
        by_identity[identity]
        for identity in sorted(by_identity)
    )


def _baseline_index_by_identity(
    baseline: pd.DataFrame,
) -> dict[tuple[str, str, str], int]:
    return {
        _frame_identity(row): int(row.bar_index)
        for row in baseline.itertuples(index=False)
    }


def _captured_index_by_identity(
    observations: tuple[DailyConfirmationObservation, ...],
) -> dict[tuple[str, str, str], int]:
    return {
        _observation_identity(item): item.bar_index
        for item in observations
    }


def _survives(
    item: DailyConfirmationObservation,
    policy: str,
) -> bool:
    return _policy_survives(
        policy,
        item.passed_confirmation_count,
        item.confirmation_count,
    )


def _policy_rows(
    observations: tuple[DailyConfirmationObservation, ...],
) -> tuple[DailyConfirmationPolicySummary, ...]:
    rows: list[DailyConfirmationPolicySummary] = []
    codes = sorted({item.code for item in observations})
    for code in codes:
        current = tuple(item for item in observations if item.code == code)
        for policy in POLICIES:
            surviving = tuple(
                item for item in current if _survives(item, policy)
            )
            rows.append(
                DailyConfirmationPolicySummary(
                    code=code,
                    policy=policy,
                    current_event_count=len(current),
                    surviving_event_count=len(surviving),
                    removed_event_count=len(current) - len(surviving),
                    survival_rate=(
                        len(surviving) / len(current)
                        if current
                        else 0.0
                    ),
                    symbol_count=len(
                        {item.symbol for item in surviving}
                    ),
                )
            )
    return tuple(rows)


def _relationship(
    first: set[tuple[str, str]],
    second: set[tuple[str, str]],
) -> str:
    if not first & second:
        return "DISJOINT"
    if first == second:
        return "IDENTICAL_FIRING_SET"
    if first < second:
        return "A_STRICT_SUBSET_OF_B"
    if second < first:
        return "B_STRICT_SUBSET_OF_A"
    return "PARTIAL_OVERLAP"


def _pairwise_rows(
    observations: tuple[DailyConfirmationObservation, ...],
) -> tuple[DailyConfirmationPairwiseRow, ...]:
    rows: list[DailyConfirmationPairwiseRow] = []
    codes = sorted({item.code for item in observations})
    for policy in POLICIES:
        sets: dict[str, set[tuple[str, str]]] = {}
        for code in codes:
            sets[code] = {
                (
                    item.symbol,
                    _normalize_session_identity(item.session),
                )
                for item in observations
                if item.code == code and _survives(item, policy)
            }

        for index, code_a in enumerate(codes):
            for code_b in codes[index + 1 :]:
                set_a = sets[code_a]
                set_b = sets[code_b]
                overlap = len(set_a & set_b)
                union = len(set_a | set_b)
                rows.append(
                    DailyConfirmationPairwiseRow(
                        policy=policy,
                        code_a=code_a,
                        code_b=code_b,
                        code_a_count=len(set_a),
                        code_b_count=len(set_b),
                        overlap_count=overlap,
                        jaccard=overlap / union if union else 0.0,
                        relationship=_relationship(set_a, set_b),
                    )
                )
    return tuple(rows)


def build_confirmation_counterfactual_audit(
    *,
    source_audit_id: str,
    source_lineage: DailyConfirmationSourceLineage,
    requested_symbols: tuple[str, ...],
    baseline: pd.DataFrame,
    observations: tuple[DailyConfirmationObservation, ...],
    failures: tuple[DailyConfirmationAuditFailure, ...] = (),
    snapshot_worker_count: int = 1,
) -> DailyConfirmationCounterfactualAudit:
    clean_symbols = tuple(
        str(symbol).strip().upper() for symbol in requested_symbols
    )
    if len(set(clean_symbols)) != len(clean_symbols):
        raise ValueError("requested symbols must be unique")
    if snapshot_worker_count < 1:
        raise ValueError("snapshot_worker_count must be positive")

    failure_symbols = {item.symbol for item in failures}
    if not failure_symbols <= set(clean_symbols):
        raise ValueError("failure symbols must belong to requested symbols")

    selected_baseline = baseline[
        baseline["symbol"].isin(clean_symbols)
    ]
    unique_observations = _deduplicate_observations(observations)
    baseline_identities = {
        _frame_identity(row)
        for row in selected_baseline.itertuples(index=False)
    }
    captured_identities = {
        _observation_identity(item) for item in unique_observations
    }
    mismatch_count = len(
        baseline_identities.symmetric_difference(captured_identities)
    )

    baseline_indexes = _baseline_index_by_identity(selected_baseline)
    captured_indexes = _captured_index_by_identity(unique_observations)
    drift_rows = tuple(
        DailyConfirmationBarIndexDrift(
            symbol=identity[0],
            session=identity[1],
            code=identity[2],
            baseline_bar_index=baseline_indexes[identity],
            captured_bar_index=captured_indexes[identity],
            index_delta=(
                captured_indexes[identity]
                - baseline_indexes[identity]
            ),
        )
        for identity in sorted(
            baseline_identities & captured_identities
        )
        if baseline_indexes[identity] != captured_indexes[identity]
    )

    return DailyConfirmationCounterfactualAudit(
        audit_id=DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID,
        source_audit_id=source_audit_id,
        requested_symbol_count=len(clean_symbols),
        succeeded_symbol_count=len(clean_symbols) - len(failures),
        failed_symbol_count=len(failures),
        confirmation_sensitive_code_count=len(
            CONFIRMATION_SENSITIVE_CODES
        ),
        physical_observation_count=len(observations),
        captured_event_count=len(captured_identities),
        duplicate_observation_count=(
            len(observations) - len(unique_observations)
        ),
        baseline_event_count=len(baseline_identities),
        identity_mismatch_count=mismatch_count,
        bar_index_mismatch_count=len(drift_rows),
        snapshot_worker_count=snapshot_worker_count,
        source_lineage=source_lineage,
        policy_rows=_policy_rows(unique_observations),
        pairwise_rows=_pairwise_rows(unique_observations),
        observations=unique_observations,
        bar_index_drifts=drift_rows,
        failures=tuple(
            sorted(failures, key=lambda item: item.symbol)
        ),
    )


def write_confirmation_counterfactual_audit(
    audit: DailyConfirmationCounterfactualAudit,
    output_dir: str | Path,
) -> DailyConfirmationCounterfactualPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyConfirmationCounterfactualPaths(
        summary_json=root / "daily_confirmation_counterfactual_summary.json",
        observations_csv=root / "daily_confirmation_observations.csv",
        policy_summary_csv=root / "daily_confirmation_policy_summary.csv",
        pairwise_csv=root / "daily_confirmation_pairwise.csv",
        index_drift_csv=root / "daily_confirmation_index_drift.csv",
        failures_csv=root / "daily_confirmation_failures.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "source_audit_id": audit.source_audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "succeeded_symbol_count": audit.succeeded_symbol_count,
        "failed_symbol_count": audit.failed_symbol_count,
        "confirmation_sensitive_code_count": (
            audit.confirmation_sensitive_code_count
        ),
        "physical_observation_count": audit.physical_observation_count,
        "captured_event_count": audit.captured_event_count,
        "duplicate_observation_count": audit.duplicate_observation_count,
        "baseline_event_count": audit.baseline_event_count,
        "identity_mismatch_count": audit.identity_mismatch_count,
        "bar_index_mismatch_count": audit.bar_index_mismatch_count,
        "snapshot_worker_count": audit.snapshot_worker_count,
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                **asdict(item),
                "passed_confirmations": "|".join(
                    item.passed_confirmations
                ),
                "failed_confirmations": "|".join(
                    item.failed_confirmations
                ),
            }
            for item in audit.observations
        ]
    ).to_csv(paths.observations_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.policy_rows]
    ).to_csv(paths.policy_summary_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.pairwise_rows]
    ).to_csv(paths.pairwise_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.bar_index_drifts]
    ).to_csv(paths.index_drift_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.failures]
    ).to_csv(paths.failures_csv, index=False)
    return paths


__all__ = [
    "CONFIRMATION_SENSITIVE_CODES",
    "DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID",
    "DailyConfirmationAuditFailure",
    "DailyConfirmationBarIndexDrift",
    "DailyConfirmationCounterfactualAudit",
    "DailyConfirmationObservation",
    "DailyConfirmationSourceLineage",
    "DailyConfirmationSources",
    "POLICIES",
    "POLICY_ALL",
    "POLICY_ANY",
    "POLICY_CURRENT",
    "POLICY_MAJORITY",
    "build_confirmation_counterfactual_audit",
    "capture_symbol_confirmation_observations",
    "load_confirmation_sources",
    "write_confirmation_counterfactual_audit",
]
