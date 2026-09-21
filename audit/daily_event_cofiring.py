"""Frozen L1 daily-event frequency, co-firing, and gate-semantics audit.

L2 consumes the read-only L1 emission ledger. It does not replay market data or
change detector behavior. Raw duplicate emissions remain measurable, while
frequency/co-firing uses unique symbol + bar + session + code identities.
"""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import combinations
from pathlib import Path

import pandas as pd

from config import FULL_HISTORY_PERIOD
from evidence.absorption import collect_absorption
from evidence.demand import (
    _collect_increasing_demand,
    _collect_no_supply,
    _collect_selling_climax,
    _collect_shakeout,
    _collect_stopping_volume,
    _collect_test,
)
from evidence.demand_coming_in import collect_demand_coming_in
from evidence.helpers import evaluate_detector
from evidence.supply import (
    _collect_buying_climax,
    _collect_no_demand,
    _collect_supply_coming_in,
    _collect_upthrust,
)
from models import EvidenceCode


DAILY_EVENT_COFIRING_AUDIT_ID = "daily-event-frequency-cofiring-gates-v1"
EXPECTED_L1_AUDIT_ID = "daily-event-inventory-point-in-time-v1"
EXPECTED_L1_INPUT_SNAPSHOT_AUDIT_ID = "daily-audit-input-snapshot-v1"
_EVENT_KEY = ("symbol", "bar_index", "session")


DetectorFunction = Callable[..., object]

DETECTOR_GATE_FUNCTIONS: tuple[
    tuple[EvidenceCode, DetectorFunction],
    ...,
] = (
    (EvidenceCode.BUYING_CLIMAX, _collect_buying_climax),
    (EvidenceCode.SUPPLY_COMING_IN, _collect_supply_coming_in),
    (EvidenceCode.NO_DEMAND, _collect_no_demand),
    (EvidenceCode.UPTHRUST, _collect_upthrust),
    (EvidenceCode.INCREASING_DEMAND, _collect_increasing_demand),
    (EvidenceCode.DEMAND_COMING_IN, collect_demand_coming_in),
    (EvidenceCode.STOPPING_VOLUME, _collect_stopping_volume),
    (EvidenceCode.SELLING_CLIMAX, _collect_selling_climax),
    (EvidenceCode.TEST, _collect_test),
    (EvidenceCode.SHAKEOUT, _collect_shakeout),
    (EvidenceCode.NO_SUPPLY, _collect_no_supply),
    (EvidenceCode.ABSORPTION, collect_absorption),
)


@dataclass(frozen=True, slots=True)
class FrozenDailyEventLedgerLineage:
    input_source: str
    snapshot_audit_id: str
    snapshot_manifest_sha256: str
    snapshot_basket_name: str
    snapshot_period: str
    snapshot_cutoff: str
    l1_summary_sha256: str
    l1_emissions_sha256: str


@dataclass(frozen=True, slots=True)
class FrozenDailyEventLedger:
    source_audit_id: str
    requested_symbol_count: int
    succeeded_symbol_count: int
    failed_symbol_count: int
    evaluated_bar_count: int
    evidence_emission_count: int
    event_bar_count: int
    emissions: pd.DataFrame
    source_lineage: FrozenDailyEventLedgerLineage | None = None


@dataclass(frozen=True, slots=True)
class DailyEventFrequencyRow:
    code: str
    raw_emission_count: int
    unique_event_count: int
    duplicate_extra_emission_count: int
    evaluated_bar_rate: float
    symbol_count: int
    top_symbol: str | None
    top_symbol_event_count: int
    top_symbol_share: float


@dataclass(frozen=True, slots=True)
class DailyEventPairwiseRow:
    code_a: str
    code_b: str
    code_a_count: int
    code_b_count: int
    overlap_count: int
    pct_a_with_b: float
    pct_b_with_a: float
    jaccard: float
    relationship: str


@dataclass(frozen=True, slots=True)
class DailyEventClusterSignatureRow:
    signature: str
    code_count: int
    bar_count: int
    symbol_count: int
    share_of_event_bars: float


@dataclass(frozen=True, slots=True)
class DailyEventGateSemanticsRow:
    code: str
    detector_function: str
    mandatory_requirement_count: int
    mandatory_requirements: tuple[str, ...]
    confirmation_requirement_count: int
    confirmation_requirements: tuple[str, ...]
    shared_confirmation_gate_enforced: bool
    gate_status: str


@dataclass(frozen=True, slots=True)
class DailyEventCofiringAudit:
    audit_id: str
    source_audit_id: str
    requested_symbol_count: int
    succeeded_symbol_count: int
    evaluated_bar_count: int
    raw_emission_count: int
    unique_event_count: int
    event_bar_count: int
    emitted_code_count: int
    pair_count: int
    identical_pair_count: int
    strict_subset_pair_count: int
    partial_overlap_pair_count: int
    disjoint_pair_count: int
    multi_code_bar_count: int
    three_plus_code_bar_count: int
    max_codes_on_bar: int
    cluster_signature_count: int
    confirmation_sensitive_detector_count: int
    non_gating_confirmation_detector_count: int
    frequency_rows: tuple[DailyEventFrequencyRow, ...]
    pairwise_rows: tuple[DailyEventPairwiseRow, ...]
    cluster_rows: tuple[DailyEventClusterSignatureRow, ...]
    gate_rows: tuple[DailyEventGateSemanticsRow, ...]
    source_lineage: FrozenDailyEventLedgerLineage | None = None

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyEventCofiringAuditPaths:
    summary_json: Path
    frequencies_csv: Path
    pairwise_csv: Path
    clusters_csv: Path
    gate_semantics_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "frequencies_csv": str(self.frequencies_csv),
            "pairwise_csv": str(self.pairwise_csv),
            "clusters_csv": str(self.clusters_csv),
            "gate_semantics_csv": str(self.gate_semantics_csv),
        }


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _valid_sha256(value: object) -> bool:
    text = str(value)
    if len(text) != 64:
        return False
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def _load_l1_source_lineage(
    summary: dict[str, object],
    *,
    summary_path: Path,
    emissions_path: Path,
) -> FrozenDailyEventLedgerLineage:
    provenance = summary.get("input_provenance")
    if not isinstance(provenance, dict):
        raise ValueError(
            "L2 requires L1 frozen snapshot input provenance"
        )
    source = str(provenance.get("source", ""))
    if source != "FROZEN_DAILY_INPUT_SNAPSHOT":
        raise ValueError(
            "L2 requires L1 source=FROZEN_DAILY_INPUT_SNAPSHOT"
        )
    snapshot_audit_id = str(
        provenance.get("snapshot_audit_id", "")
    )
    if snapshot_audit_id != EXPECTED_L1_INPUT_SNAPSHOT_AUDIT_ID:
        raise ValueError("L1 snapshot audit_id does not match expected audit")
    snapshot_manifest_sha256 = str(
        provenance.get("snapshot_manifest_sha256", "")
    )
    if not _valid_sha256(snapshot_manifest_sha256):
        raise ValueError("L1 snapshot manifest SHA-256 is invalid")

    snapshot_basket_name = str(
        provenance.get("snapshot_basket_name", "")
    )
    snapshot_period = str(provenance.get("snapshot_period", ""))
    snapshot_cutoff = str(provenance.get("snapshot_cutoff", ""))
    if not snapshot_basket_name:
        raise ValueError("L1 snapshot basket name is missing")
    if snapshot_period != FULL_HISTORY_PERIOD:
        raise ValueError(
            "L2 requires the full-history frozen L1 snapshot period"
        )
    if not snapshot_cutoff:
        raise ValueError("L1 snapshot cutoff is missing")

    return FrozenDailyEventLedgerLineage(
        input_source=source,
        snapshot_audit_id=snapshot_audit_id,
        snapshot_manifest_sha256=snapshot_manifest_sha256,
        snapshot_basket_name=snapshot_basket_name,
        snapshot_period=snapshot_period,
        snapshot_cutoff=snapshot_cutoff,
        l1_summary_sha256=_sha256_file(summary_path),
        l1_emissions_sha256=_sha256_file(emissions_path),
    )


def load_frozen_daily_event_ledger(
    input_dir: str | Path,
) -> FrozenDailyEventLedger:
    root = Path(input_dir)
    summary_path = root / "daily_event_inventory_summary.json"
    emissions_path = root / "daily_event_emissions.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing L1 summary: {summary_path}")
    if not emissions_path.exists():
        raise FileNotFoundError(f"missing L1 emissions: {emissions_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != EXPECTED_L1_AUDIT_ID:
        raise ValueError("L1 audit_id does not match expected audit")
    if summary.get("is_actionable") is not False:
        raise ValueError("L1 source must remain non-actionable")
    if int(summary.get("failed_symbol_count", -1)) != 0:
        raise ValueError("L2 requires a zero-failure L1 source ledger")
    if int(summary.get("requested_symbol_count", -1)) != int(
        summary.get("succeeded_symbol_count", -2)
    ):
        raise ValueError(
            "L2 requires all requested L1 symbols to have succeeded"
        )
    source_lineage = _load_l1_source_lineage(
        summary,
        summary_path=summary_path,
        emissions_path=emissions_path,
    )

    emissions = pd.read_csv(emissions_path)
    required_columns = {
        "symbol",
        "bar_index",
        "session",
        "code",
        "direction",
        "occurrence_on_bar_code",
    }
    missing = sorted(required_columns - set(emissions.columns))
    if missing:
        raise ValueError(f"L1 emissions missing columns: {missing}")
    if len(emissions) != int(summary["evidence_emission_count"]):
        raise ValueError("L1 emission row count does not match summary")

    unique_bars = emissions.loc[:, list(_EVENT_KEY)].drop_duplicates()
    if len(unique_bars) != int(summary["event_bar_count"]):
        raise ValueError("L1 event-bar count does not match summary")

    return FrozenDailyEventLedger(
        source_audit_id=str(summary["audit_id"]),
        requested_symbol_count=int(summary["requested_symbol_count"]),
        succeeded_symbol_count=int(summary["succeeded_symbol_count"]),
        failed_symbol_count=0,
        evaluated_bar_count=int(summary["evaluated_bar_count"]),
        evidence_emission_count=int(summary["evidence_emission_count"]),
        event_bar_count=int(summary["event_bar_count"]),
        emissions=emissions.copy(),
        source_lineage=source_lineage,
    )


def _unique_events(emissions: pd.DataFrame) -> pd.DataFrame:
    columns = [*_EVENT_KEY, "code"]
    return (
        emissions.loc[:, columns]
        .drop_duplicates()
        .sort_values(columns)
        .reset_index(drop=True)
    )


def _event_sets(
    unique_events: pd.DataFrame,
) -> dict[str, set[tuple[str, int, str]]]:
    result: dict[str, set[tuple[str, int, str]]] = {}
    for code, frame in unique_events.groupby("code", sort=True):
        result[str(code)] = {
            (str(row.symbol), int(row.bar_index), str(row.session))
            for row in frame.itertuples(index=False)
        }
    return result


def _frequency_rows(
    *,
    ledger: FrozenDailyEventLedger,
    unique_events: pd.DataFrame,
) -> tuple[DailyEventFrequencyRow, ...]:
    rows: list[DailyEventFrequencyRow] = []
    raw_counts = ledger.emissions.groupby("code").size().to_dict()

    for code, frame in unique_events.groupby("code", sort=True):
        code_value = str(code)
        unique_count = len(frame)
        by_symbol = frame.groupby("symbol").size().sort_values(
            ascending=False,
        )
        top_symbol = str(by_symbol.index[0]) if len(by_symbol) else None
        top_count = int(by_symbol.iloc[0]) if len(by_symbol) else 0
        raw_count = int(raw_counts.get(code, 0))
        rows.append(
            DailyEventFrequencyRow(
                code=code_value,
                raw_emission_count=raw_count,
                unique_event_count=unique_count,
                duplicate_extra_emission_count=raw_count - unique_count,
                evaluated_bar_rate=(
                    unique_count / ledger.evaluated_bar_count
                    if ledger.evaluated_bar_count
                    else 0.0
                ),
                symbol_count=int(frame["symbol"].nunique()),
                top_symbol=top_symbol,
                top_symbol_event_count=top_count,
                top_symbol_share=(
                    top_count / unique_count if unique_count else 0.0
                ),
            )
        )
    return tuple(rows)


def _relationship(
    first: set[tuple[str, int, str]],
    second: set[tuple[str, int, str]],
) -> str:
    overlap = first & second
    if not overlap:
        return "DISJOINT"
    if first == second:
        return "IDENTICAL_FIRING_SET"
    if first < second:
        return "A_STRICT_SUBSET_OF_B"
    if second < first:
        return "B_STRICT_SUBSET_OF_A"
    return "PARTIAL_OVERLAP"


def _pairwise_rows(
    unique_events: pd.DataFrame,
) -> tuple[DailyEventPairwiseRow, ...]:
    event_sets = _event_sets(unique_events)
    rows: list[DailyEventPairwiseRow] = []
    for code_a, code_b in combinations(sorted(event_sets), 2):
        set_a = event_sets[code_a]
        set_b = event_sets[code_b]
        overlap_count = len(set_a & set_b)
        union_count = len(set_a | set_b)
        rows.append(
            DailyEventPairwiseRow(
                code_a=code_a,
                code_b=code_b,
                code_a_count=len(set_a),
                code_b_count=len(set_b),
                overlap_count=overlap_count,
                pct_a_with_b=(
                    overlap_count / len(set_a) if set_a else 0.0
                ),
                pct_b_with_a=(
                    overlap_count / len(set_b) if set_b else 0.0
                ),
                jaccard=(
                    overlap_count / union_count if union_count else 0.0
                ),
                relationship=_relationship(set_a, set_b),
            )
        )
    return tuple(rows)


def _cluster_rows(
    *,
    unique_events: pd.DataFrame,
    event_bar_count: int,
) -> tuple[DailyEventClusterSignatureRow, ...]:
    grouped = (
        unique_events.groupby(list(_EVENT_KEY))["code"]
        .agg(lambda values: "|".join(sorted(set(map(str, values)))))
        .reset_index(name="signature")
    )
    grouped["code_count"] = grouped["signature"].str.count(r"\|") + 1

    rows: list[DailyEventClusterSignatureRow] = []
    for signature, frame in grouped.groupby("signature", sort=False):
        bar_count = len(frame)
        rows.append(
            DailyEventClusterSignatureRow(
                signature=str(signature),
                code_count=int(frame["code_count"].iloc[0]),
                bar_count=bar_count,
                symbol_count=int(frame["symbol"].nunique()),
                share_of_event_bars=(
                    bar_count / event_bar_count if event_bar_count else 0.0
                ),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda item: (-item.bar_count, item.signature),
        )
    )


def _assignment_requirement_names(
    function: DetectorFunction,
    variable_name: str,
) -> tuple[str, ...]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
        )
        if not any(
            isinstance(target, ast.Name)
            and target.id == variable_name
            for target in targets
        ):
            continue
        value = node.value
        if value is None:
            continue
        for child in ast.walk(value):
            if not isinstance(child, ast.Call):
                continue
            if not (
                isinstance(child.func, ast.Name)
                and child.func.id == "requirement"
            ):
                continue
            for keyword in child.keywords:
                if keyword.arg != "name":
                    continue
                if isinstance(keyword.value, ast.Constant):
                    names.append(str(keyword.value.value))
    return tuple(names)


def _shared_confirmation_gate_enforced() -> bool:
    tree = ast.parse(textwrap.dedent(inspect.getsource(evaluate_detector)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        referenced = {
            child.id
            for child in ast.walk(node.test)
            if isinstance(child, ast.Name)
        }
        if referenced & {"confirmations", "confirmation_score"}:
            return True
    return False


def build_daily_event_gate_semantics(
) -> tuple[DailyEventGateSemanticsRow, ...]:
    shared_enforced = _shared_confirmation_gate_enforced()
    rows: list[DailyEventGateSemanticsRow] = []
    for code, function in DETECTOR_GATE_FUNCTIONS:
        mandatory = _assignment_requirement_names(function, "requirements")
        confirmations = _assignment_requirement_names(
            function,
            "confirmations",
        )
        if confirmations and shared_enforced:
            status = "CONFIRMATIONS_GATING"
        elif confirmations:
            status = "CONFIRMATIONS_PRESENT_NON_GATING"
        else:
            status = "NO_CONFIRMATION_GATE"
        rows.append(
            DailyEventGateSemanticsRow(
                code=code.value,
                detector_function=(
                    f"{function.__module__}.{function.__name__}"
                ),
                mandatory_requirement_count=len(mandatory),
                mandatory_requirements=mandatory,
                confirmation_requirement_count=len(confirmations),
                confirmation_requirements=confirmations,
                shared_confirmation_gate_enforced=shared_enforced,
                gate_status=status,
            )
        )
    return tuple(rows)


def build_daily_event_cofiring_audit(
    ledger: FrozenDailyEventLedger,
) -> DailyEventCofiringAudit:
    unique_events = _unique_events(ledger.emissions)
    unique_event_count = len(unique_events)
    event_bar_count = len(
        unique_events.loc[:, list(_EVENT_KEY)].drop_duplicates()
    )
    if event_bar_count != ledger.event_bar_count:
        raise ValueError("unique event-bar count changed from frozen L1 source")

    frequency_rows = _frequency_rows(
        ledger=ledger,
        unique_events=unique_events,
    )
    pairwise_rows = _pairwise_rows(unique_events)
    cluster_rows = _cluster_rows(
        unique_events=unique_events,
        event_bar_count=event_bar_count,
    )
    gate_rows = build_daily_event_gate_semantics()

    per_bar_code_counts = (
        unique_events.groupby(list(_EVENT_KEY))["code"].nunique()
    )
    relationship_counts = pd.Series(
        [item.relationship for item in pairwise_rows]
    ).value_counts()

    return DailyEventCofiringAudit(
        audit_id=DAILY_EVENT_COFIRING_AUDIT_ID,
        source_audit_id=ledger.source_audit_id,
        requested_symbol_count=ledger.requested_symbol_count,
        succeeded_symbol_count=ledger.succeeded_symbol_count,
        evaluated_bar_count=ledger.evaluated_bar_count,
        raw_emission_count=ledger.evidence_emission_count,
        unique_event_count=unique_event_count,
        event_bar_count=event_bar_count,
        emitted_code_count=len(frequency_rows),
        pair_count=len(pairwise_rows),
        identical_pair_count=int(
            relationship_counts.get("IDENTICAL_FIRING_SET", 0)
        ),
        strict_subset_pair_count=int(
            relationship_counts.get("A_STRICT_SUBSET_OF_B", 0)
            + relationship_counts.get("B_STRICT_SUBSET_OF_A", 0)
        ),
        partial_overlap_pair_count=int(
            relationship_counts.get("PARTIAL_OVERLAP", 0)
        ),
        disjoint_pair_count=int(
            relationship_counts.get("DISJOINT", 0)
        ),
        multi_code_bar_count=int((per_bar_code_counts >= 2).sum()),
        three_plus_code_bar_count=int((per_bar_code_counts >= 3).sum()),
        max_codes_on_bar=int(per_bar_code_counts.max()),
        cluster_signature_count=len(cluster_rows),
        confirmation_sensitive_detector_count=sum(
            item.confirmation_requirement_count > 0
            for item in gate_rows
        ),
        non_gating_confirmation_detector_count=sum(
            item.gate_status == "CONFIRMATIONS_PRESENT_NON_GATING"
            for item in gate_rows
        ),
        frequency_rows=frequency_rows,
        pairwise_rows=pairwise_rows,
        cluster_rows=cluster_rows,
        gate_rows=gate_rows,
        source_lineage=ledger.source_lineage,
    )


def write_daily_event_cofiring_audit(
    audit: DailyEventCofiringAudit,
    output_dir: str | Path,
) -> DailyEventCofiringAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyEventCofiringAuditPaths(
        summary_json=root / "daily_event_cofiring_summary.json",
        frequencies_csv=root / "daily_event_frequencies.csv",
        pairwise_csv=root / "daily_event_pairwise.csv",
        clusters_csv=root / "daily_event_cluster_signatures.csv",
        gate_semantics_csv=root / "daily_event_gate_semantics.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "source_audit_id": audit.source_audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "succeeded_symbol_count": audit.succeeded_symbol_count,
        "evaluated_bar_count": audit.evaluated_bar_count,
        "raw_emission_count": audit.raw_emission_count,
        "unique_event_count": audit.unique_event_count,
        "event_bar_count": audit.event_bar_count,
        "emitted_code_count": audit.emitted_code_count,
        "pair_count": audit.pair_count,
        "identical_pair_count": audit.identical_pair_count,
        "strict_subset_pair_count": audit.strict_subset_pair_count,
        "partial_overlap_pair_count": audit.partial_overlap_pair_count,
        "disjoint_pair_count": audit.disjoint_pair_count,
        "multi_code_bar_count": audit.multi_code_bar_count,
        "three_plus_code_bar_count": audit.three_plus_code_bar_count,
        "max_codes_on_bar": audit.max_codes_on_bar,
        "cluster_signature_count": audit.cluster_signature_count,
        "confirmation_sensitive_detector_count": (
            audit.confirmation_sensitive_detector_count
        ),
        "non_gating_confirmation_detector_count": (
            audit.non_gating_confirmation_detector_count
        ),
        "source_lineage": (
            None
            if audit.source_lineage is None
            else asdict(audit.source_lineage)
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [asdict(item) for item in audit.frequency_rows]
    ).to_csv(paths.frequencies_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.pairwise_rows]
    ).to_csv(paths.pairwise_csv, index=False)
    pd.DataFrame(
        [asdict(item) for item in audit.cluster_rows]
    ).to_csv(paths.clusters_csv, index=False)
    pd.DataFrame(
        [
            {
                **asdict(item),
                "mandatory_requirements": "|".join(
                    item.mandatory_requirements
                ),
                "confirmation_requirements": "|".join(
                    item.confirmation_requirements
                ),
            }
            for item in audit.gate_rows
        ]
    ).to_csv(paths.gate_semantics_csv, index=False)
    return paths


__all__ = [
    "DAILY_EVENT_COFIRING_AUDIT_ID",
    "EXPECTED_L1_AUDIT_ID",
    "EXPECTED_L1_INPUT_SNAPSHOT_AUDIT_ID",
    "DETECTOR_GATE_FUNCTIONS",
    "DailyEventCofiringAudit",
    "DailyEventCofiringAuditPaths",
    "DailyEventFrequencyRow",
    "DailyEventGateSemanticsRow",
    "DailyEventPairwiseRow",
    "FrozenDailyEventLedger",
    "FrozenDailyEventLedgerLineage",
    "build_daily_event_cofiring_audit",
    "build_daily_event_gate_semantics",
    "load_frozen_daily_event_ledger",
    "write_daily_event_cofiring_audit",
]
