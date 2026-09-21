"""BUYING_CLIMAX vs UPTHRUST identity-separation audit.

This audit is intentionally narrow. It consumes the frozen L3 confirmation
ledger, verifies that BUYING_CLIMAX and UPTHRUST share an identical production
mandatory contract and firing set, then applies exactly one counterfactual:
require each detector's unique confirmation clause.

No market-data replay and no production mutation are performed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import pandas as pd

from audit.daily_event_confirmation_counterfactual import (
    DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID,
)
from audit.daily_event_confirmation_semantics import (
    build_confirmation_contract_rows,
    load_canonical_l3_observations,
)
from models import EvidenceCode


DAILY_BC_UPTHRUST_IDENTITY_SEPARATION_AUDIT_ID = (
    "daily-event-bc-upthrust-identity-separation-v1"
)

BC_CODE = EvidenceCode.BUYING_CLIMAX.value
UT_CODE = EvidenceCode.UPTHRUST.value

BC_UNIQUE_CONFIRMATION = "Increasing Volume"
UT_UNIQUE_CONFIRMATION = "Lower Close Than Previous"

SHARED_MANDATORY_REQUIREMENTS = (
    "Buying Campaign",
    "Bullish Bar",
    "Very High Volume",
    "Above Average Spread",
)

SHARED_CONFIRMATIONS = (
    "Wide Spread",
    "Weak Close",
)

PARTITION_BC_ONLY = "BC_UNIQUE_ONLY"
PARTITION_UT_ONLY = "UT_UNIQUE_ONLY"
PARTITION_BOTH = "BOTH_UNIQUE"
PARTITION_NEITHER = "NEITHER_UNIQUE"
PARTITION_ORDER = (
    PARTITION_BC_ONLY,
    PARTITION_UT_ONLY,
    PARTITION_BOTH,
    PARTITION_NEITHER,
)


@dataclass(frozen=True, slots=True)
class BcUpthrustSourceLineage:
    l3_audit_id: str
    l3_summary_sha256: str
    l3_observations_sha256: str
    snapshot_manifest_sha256: str
    l1_summary_sha256: str
    l1_emissions_sha256: str
    l2_summary_sha256: str
    source_contract_sha256: str


@dataclass(frozen=True, slots=True)
class BcUpthrustPartitionRow:
    partition: str
    event_count: int
    event_share: float
    symbol_count: int


@dataclass(frozen=True, slots=True)
class BcUpthrustSymbolRow:
    symbol: str
    baseline_event_count: int
    bc_unique_gate_count: int
    ut_unique_gate_count: int
    both_unique_count: int
    bc_only_count: int
    ut_only_count: int
    neither_count: int


@dataclass(frozen=True, slots=True)
class BcUpthrustIdentityRow:
    symbol: str
    bar_index: int
    session: str
    bc_unique_confirmation_passed: bool
    ut_unique_confirmation_passed: bool
    partition: str


@dataclass(frozen=True, slots=True)
class BcUpthrustIdentitySeparationAudit:
    audit_id: str
    source_lineage: BcUpthrustSourceLineage
    requested_symbol_count: int
    baseline_bc_event_count: int
    baseline_ut_event_count: int
    baseline_overlap_count: int
    baseline_identical_firing_set: bool
    shared_mandatory_contract: bool
    mandatory_requirement_count: int
    shared_confirmation_count: int
    bc_unique_confirmation: str
    ut_unique_confirmation: str
    bc_unique_gate_event_count: int
    bc_unique_gate_survival_rate: float
    ut_unique_gate_event_count: int
    ut_unique_gate_survival_rate: float
    unique_gate_overlap_count: int
    unique_gate_union_count: int
    unique_gate_jaccard: float
    unique_gate_identical_firing_set: bool
    partition_rows: tuple[BcUpthrustPartitionRow, ...]
    symbol_rows: tuple[BcUpthrustSymbolRow, ...]
    identity_rows: tuple[BcUpthrustIdentityRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class BcUpthrustIdentitySeparationPaths:
    summary_json: Path
    partitions_csv: Path
    symbols_csv: Path
    identities_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "partitions_csv": str(self.partitions_csv),
            "symbols_csv": str(self.symbols_csv),
            "identities_csv": str(self.identities_csv),
        }


def _sha256_payload(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _split_names(value: object) -> tuple[str, ...]:
    if value is None or pd.isna(value):
        return ()
    text = str(value).strip()
    if not text:
        return ()
    return tuple(item for item in text.split("|") if item)


def _stable_identity(row: object) -> tuple[str, int, str]:
    return (
        str(getattr(row, "symbol")).strip().upper(),
        int(getattr(row, "bar_index")),
        pd.Timestamp(getattr(row, "session")).isoformat(),
    )


def _contract_payload() -> tuple[
    tuple[str, str, str, int, str, str],
    ...,
]:
    rows = build_confirmation_contract_rows()
    selected = [
        row
        for row in rows
        if row.code in {BC_CODE, UT_CODE}
    ]
    return tuple(
        (
            row.code,
            row.detector_function,
            row.requirement_kind,
            row.ordinal,
            row.requirement_name,
            row.passed_expression,
        )
        for row in selected
    )


def _contract_names(
    *,
    code: str,
    kind: str,
) -> tuple[str, ...]:
    rows = build_confirmation_contract_rows()
    return tuple(
        row.requirement_name
        for row in rows
        if row.code == code and row.requirement_kind == kind
    )


def _validate_contract() -> tuple[bool, int, int]:
    bc_mandatory = _contract_names(code=BC_CODE, kind="MANDATORY")
    ut_mandatory = _contract_names(code=UT_CODE, kind="MANDATORY")
    if bc_mandatory != SHARED_MANDATORY_REQUIREMENTS:
        raise ValueError(
            "BUYING_CLIMAX mandatory contract changed: "
            f"{bc_mandatory!r}"
        )
    if ut_mandatory != SHARED_MANDATORY_REQUIREMENTS:
        raise ValueError(
            "UPTHRUST mandatory contract changed: "
            f"{ut_mandatory!r}"
        )

    bc_confirmation = _contract_names(
        code=BC_CODE,
        kind="CONFIRMATION",
    )
    ut_confirmation = _contract_names(
        code=UT_CODE,
        kind="CONFIRMATION",
    )

    expected_bc = (
        *SHARED_CONFIRMATIONS,
        BC_UNIQUE_CONFIRMATION,
    )
    expected_ut = (
        *SHARED_CONFIRMATIONS,
        UT_UNIQUE_CONFIRMATION,
    )
    if bc_confirmation != expected_bc:
        raise ValueError(
            "BUYING_CLIMAX confirmation contract changed: "
            f"{bc_confirmation!r}"
        )
    if ut_confirmation != expected_ut:
        raise ValueError(
            "UPTHRUST confirmation contract changed: "
            f"{ut_confirmation!r}"
        )

    return (
        bc_mandatory == ut_mandatory,
        len(bc_mandatory),
        len(SHARED_CONFIRMATIONS),
    )


def _passed_unique(
    row: object,
    confirmation_name: str,
) -> bool:
    return confirmation_name in _split_names(
        getattr(row, "passed_confirmations")
    )


def partition_unique_confirmations(
    *,
    bc_passed: bool,
    ut_passed: bool,
) -> str:
    if bc_passed and ut_passed:
        return PARTITION_BOTH
    if bc_passed:
        return PARTITION_BC_ONLY
    if ut_passed:
        return PARTITION_UT_ONLY
    return PARTITION_NEITHER


def build_bc_upthrust_identity_separation_audit(
    input_dir: str | Path,
) -> BcUpthrustIdentitySeparationAudit:
    summary, observations, l3_lineage = load_canonical_l3_observations(
        input_dir
    )
    if (
        str(summary["audit_id"])
        != DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID
    ):
        raise ValueError("unexpected L3 source audit")

    shared_mandatory, mandatory_count, shared_confirmation_count = (
        _validate_contract()
    )

    pair = observations.loc[
        observations["code"].isin((BC_CODE, UT_CODE))
    ].copy()
    pair["symbol"] = pair["symbol"].map(
        lambda value: str(value).strip().upper()
    )
    pair["session"] = pair["session"].map(
        lambda value: pd.Timestamp(value).isoformat()
    )

    bc = pair.loc[pair["code"] == BC_CODE].copy()
    ut = pair.loc[pair["code"] == UT_CODE].copy()

    bc_by_identity = {
        _stable_identity(row): row
        for row in bc.itertuples(index=False)
    }
    ut_by_identity = {
        _stable_identity(row): row
        for row in ut.itertuples(index=False)
    }
    bc_ids = set(bc_by_identity)
    ut_ids = set(ut_by_identity)
    overlap = bc_ids & ut_ids

    baseline_identical = bc_ids == ut_ids
    if not baseline_identical:
        raise ValueError(
            "canonical BC/UT firing sets are no longer identical"
        )
    if len(bc_ids) != 4497 or len(ut_ids) != 4497:
        raise ValueError(
            "canonical BC/UT event count changed: "
            f"{len(bc_ids)}/{len(ut_ids)}"
        )

    identity_rows: list[BcUpthrustIdentityRow] = []
    for identity in sorted(bc_ids):
        bc_row = bc_by_identity[identity]
        ut_row = ut_by_identity[identity]
        bc_passed = _passed_unique(
            bc_row,
            BC_UNIQUE_CONFIRMATION,
        )
        ut_passed = _passed_unique(
            ut_row,
            UT_UNIQUE_CONFIRMATION,
        )
        partition = partition_unique_confirmations(
            bc_passed=bc_passed,
            ut_passed=ut_passed,
        )

        symbol, bar_index, session = identity
        identity_rows.append(
            BcUpthrustIdentityRow(
                symbol=symbol,
                bar_index=bar_index,
                session=session,
                bc_unique_confirmation_passed=bc_passed,
                ut_unique_confirmation_passed=ut_passed,
                partition=partition,
            )
        )

    identity_frame = pd.DataFrame(
        [asdict(row) for row in identity_rows]
    )

    partition_rows: list[BcUpthrustPartitionRow] = []
    for partition in PARTITION_ORDER:
        selected = identity_frame.loc[
            identity_frame["partition"] == partition
        ]
        partition_rows.append(
            BcUpthrustPartitionRow(
                partition=partition,
                event_count=len(selected),
                event_share=len(selected) / len(identity_frame),
                symbol_count=int(selected["symbol"].nunique()),
            )
        )

    symbol_rows: list[BcUpthrustSymbolRow] = []
    for symbol, frame in identity_frame.groupby("symbol", sort=True):
        symbol_rows.append(
            BcUpthrustSymbolRow(
                symbol=str(symbol),
                baseline_event_count=len(frame),
                bc_unique_gate_count=int(
                    frame["bc_unique_confirmation_passed"].sum()
                ),
                ut_unique_gate_count=int(
                    frame["ut_unique_confirmation_passed"].sum()
                ),
                both_unique_count=int(
                    (frame["partition"] == PARTITION_BOTH).sum()
                ),
                bc_only_count=int(
                    (frame["partition"] == PARTITION_BC_ONLY).sum()
                ),
                ut_only_count=int(
                    (frame["partition"] == PARTITION_UT_ONLY).sum()
                ),
                neither_count=int(
                    (frame["partition"] == PARTITION_NEITHER).sum()
                ),
            )
        )

    bc_unique_ids = {
        (
            row.symbol,
            row.bar_index,
            row.session,
        )
        for row in identity_rows
        if row.bc_unique_confirmation_passed
    }
    ut_unique_ids = {
        (
            row.symbol,
            row.bar_index,
            row.session,
        )
        for row in identity_rows
        if row.ut_unique_confirmation_passed
    }
    unique_overlap = bc_unique_ids & ut_unique_ids
    unique_union = bc_unique_ids | ut_unique_ids

    requested_symbol_count = int(summary["requested_symbol_count"])
    if requested_symbol_count != 30:
        raise ValueError("canonical L3 symbol count changed")
    if len(symbol_rows) != requested_symbol_count:
        raise ValueError("BC/UT identities do not span all canonical symbols")

    source_lineage = BcUpthrustSourceLineage(
        l3_audit_id=l3_lineage.l3_audit_id,
        l3_summary_sha256=l3_lineage.l3_summary_sha256,
        l3_observations_sha256=l3_lineage.l3_observations_sha256,
        snapshot_manifest_sha256=l3_lineage.snapshot_manifest_sha256,
        l1_summary_sha256=l3_lineage.l1_summary_sha256,
        l1_emissions_sha256=l3_lineage.l1_emissions_sha256,
        l2_summary_sha256=l3_lineage.l2_summary_sha256,
        source_contract_sha256=_sha256_payload(_contract_payload()),
    )

    return BcUpthrustIdentitySeparationAudit(
        audit_id=DAILY_BC_UPTHRUST_IDENTITY_SEPARATION_AUDIT_ID,
        source_lineage=source_lineage,
        requested_symbol_count=requested_symbol_count,
        baseline_bc_event_count=len(bc_ids),
        baseline_ut_event_count=len(ut_ids),
        baseline_overlap_count=len(overlap),
        baseline_identical_firing_set=baseline_identical,
        shared_mandatory_contract=shared_mandatory,
        mandatory_requirement_count=mandatory_count,
        shared_confirmation_count=shared_confirmation_count,
        bc_unique_confirmation=BC_UNIQUE_CONFIRMATION,
        ut_unique_confirmation=UT_UNIQUE_CONFIRMATION,
        bc_unique_gate_event_count=len(bc_unique_ids),
        bc_unique_gate_survival_rate=len(bc_unique_ids) / len(bc_ids),
        ut_unique_gate_event_count=len(ut_unique_ids),
        ut_unique_gate_survival_rate=len(ut_unique_ids) / len(ut_ids),
        unique_gate_overlap_count=len(unique_overlap),
        unique_gate_union_count=len(unique_union),
        unique_gate_jaccard=(
            len(unique_overlap) / len(unique_union)
            if unique_union
            else 0.0
        ),
        unique_gate_identical_firing_set=(
            bc_unique_ids == ut_unique_ids
        ),
        partition_rows=tuple(partition_rows),
        symbol_rows=tuple(symbol_rows),
        identity_rows=tuple(identity_rows),
    )


def write_bc_upthrust_identity_separation_audit(
    audit: BcUpthrustIdentitySeparationAudit,
    output_dir: str | Path,
) -> BcUpthrustIdentitySeparationPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    paths = BcUpthrustIdentitySeparationPaths(
        summary_json=root / "daily_bc_upthrust_identity_summary.json",
        partitions_csv=root / "daily_bc_upthrust_identity_partitions.csv",
        symbols_csv=root / "daily_bc_upthrust_identity_symbols.csv",
        identities_csv=root / "daily_bc_upthrust_identity_rows.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "baseline_bc_event_count": audit.baseline_bc_event_count,
        "baseline_ut_event_count": audit.baseline_ut_event_count,
        "baseline_overlap_count": audit.baseline_overlap_count,
        "baseline_identical_firing_set": (
            audit.baseline_identical_firing_set
        ),
        "shared_mandatory_contract": audit.shared_mandatory_contract,
        "mandatory_requirement_count": audit.mandatory_requirement_count,
        "shared_confirmation_count": audit.shared_confirmation_count,
        "bc_unique_confirmation": audit.bc_unique_confirmation,
        "ut_unique_confirmation": audit.ut_unique_confirmation,
        "bc_unique_gate_event_count": audit.bc_unique_gate_event_count,
        "bc_unique_gate_survival_rate": audit.bc_unique_gate_survival_rate,
        "ut_unique_gate_event_count": audit.ut_unique_gate_event_count,
        "ut_unique_gate_survival_rate": audit.ut_unique_gate_survival_rate,
        "unique_gate_overlap_count": audit.unique_gate_overlap_count,
        "unique_gate_union_count": audit.unique_gate_union_count,
        "unique_gate_jaccard": audit.unique_gate_jaccard,
        "unique_gate_identical_firing_set": (
            audit.unique_gate_identical_firing_set
        ),
        "partition_row_count": len(audit.partition_rows),
        "symbol_row_count": len(audit.symbol_rows),
        "identity_row_count": len(audit.identity_rows),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame(
        [asdict(row) for row in audit.partition_rows]
    ).to_csv(paths.partitions_csv, index=False)
    pd.DataFrame(
        [asdict(row) for row in audit.symbol_rows]
    ).to_csv(paths.symbols_csv, index=False)
    pd.DataFrame(
        [asdict(row) for row in audit.identity_rows]
    ).to_csv(paths.identities_csv, index=False)
    return paths


__all__ = [
    "BC_CODE",
    "BC_UNIQUE_CONFIRMATION",
    "DAILY_BC_UPTHRUST_IDENTITY_SEPARATION_AUDIT_ID",
    "PARTITION_BC_ONLY",
    "PARTITION_BOTH",
    "PARTITION_NEITHER",
    "PARTITION_UT_ONLY",
    "SHARED_CONFIRMATIONS",
    "SHARED_MANDATORY_REQUIREMENTS",
    "UT_CODE",
    "UT_UNIQUE_CONFIRMATION",
    "BcUpthrustIdentityRow",
    "BcUpthrustIdentitySeparationAudit",
    "BcUpthrustIdentitySeparationPaths",
    "BcUpthrustPartitionRow",
    "BcUpthrustSourceLineage",
    "BcUpthrustSymbolRow",
    "build_bc_upthrust_identity_separation_audit",
    "partition_unique_confirmations",
    "write_bc_upthrust_identity_separation_audit",
]
