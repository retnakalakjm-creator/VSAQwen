"""Exact parity audit for cached versus legacy daily-event inventory replay."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import pandas as pd

from audit.daily_event_inventory import DAILY_EVENT_INVENTORY_AUDIT_ID


DAILY_EVENT_INVENTORY_REPLAY_PARITY_AUDIT_ID = (
    "daily-event-inventory-replay-parity-v1"
)



@dataclass(frozen=True, slots=True)
class InventoryReplayParityLineage:
    reference_summary_sha256: str
    candidate_summary_sha256: str
    reference_inventory_sha256: str
    candidate_inventory_sha256: str
    reference_emissions_sha256: str
    candidate_emissions_sha256: str
    reference_duplicates_sha256: str
    candidate_duplicates_sha256: str
    snapshot_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class InventoryReplayParityAudit:
    audit_id: str
    source_lineage: InventoryReplayParityLineage
    summary_equal: bool
    inventory_equal: bool
    emissions_equal: bool
    duplicates_equal: bool
    reference_evidence_emission_count: int
    candidate_evidence_emission_count: int
    reference_event_bar_count: int
    candidate_event_bar_count: int
    inventory_row_symmetric_difference_count: int
    emission_row_symmetric_difference_count: int
    duplicate_row_symmetric_difference_count: int

    @property
    def exact_match(self) -> bool:
        return (
            self.summary_equal
            and self.inventory_equal
            and self.emissions_equal
            and self.duplicates_equal
            and self.inventory_row_symmetric_difference_count == 0
            and self.emission_row_symmetric_difference_count == 0
            and self.duplicate_row_symmetric_difference_count == 0
        )

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class InventoryReplayParityPaths:
    summary_json: Path

    def as_dict(self) -> dict[str, str]:
        return {"summary_json": str(self.summary_json)}


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_summary(root: Path) -> tuple[dict[str, object], Path]:
    path = root / "daily_event_inventory_summary.json"
    if not path.exists():
        raise FileNotFoundError(path)
    summary = json.loads(path.read_text(encoding="utf-8"))
    if summary.get("audit_id") != DAILY_EVENT_INVENTORY_AUDIT_ID:
        raise ValueError(f"unexpected inventory audit_id in {root}")
    if summary.get("is_actionable") is not False:
        raise ValueError(f"inventory source must be non-actionable: {root}")
    return summary, path


def _normalize_scalar(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("artifact contains non-finite float")
        return round(value, 12)
    if isinstance(value, (bool, int, str)):
        return value
    return str(value)


def _normalized_rows(path: Path) -> frozenset[tuple[object, ...]]:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    columns = tuple(map(str, frame.columns))
    return frozenset(
        (columns, *tuple(_normalize_scalar(value) for value in row))
        for row in frame.itertuples(index=False, name=None)
    )


def _manifest(summary: dict[str, object]) -> str:
    provenance = summary.get("input_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("inventory input_provenance is missing")
    manifest = str(provenance.get("snapshot_manifest_sha256", ""))
    if not manifest:
        raise ValueError("snapshot manifest hash is missing")
    return manifest


def build_inventory_replay_parity_audit(
    *,
    reference_dir: str | Path,
    candidate_dir: str | Path,
) -> InventoryReplayParityAudit:
    reference_root = Path(reference_dir)
    candidate_root = Path(candidate_dir)

    reference_summary, reference_summary_path = _load_summary(reference_root)
    candidate_summary, candidate_summary_path = _load_summary(candidate_root)

    reference_manifest = _manifest(reference_summary)
    candidate_manifest = _manifest(candidate_summary)
    if reference_manifest != candidate_manifest:
        raise ValueError("reference/candidate snapshot manifests differ")

    reference_inventory_path = reference_root / "daily_event_inventory.csv"
    candidate_inventory_path = candidate_root / "daily_event_inventory.csv"
    reference_emissions_path = reference_root / "daily_event_emissions.csv"
    candidate_emissions_path = candidate_root / "daily_event_emissions.csv"
    reference_duplicates_path = reference_root / "daily_event_duplicates.csv"
    candidate_duplicates_path = candidate_root / "daily_event_duplicates.csv"

    reference_inventory = _normalized_rows(reference_inventory_path)
    candidate_inventory = _normalized_rows(candidate_inventory_path)
    reference_emissions = _normalized_rows(reference_emissions_path)
    candidate_emissions = _normalized_rows(candidate_emissions_path)
    reference_duplicates = _normalized_rows(reference_duplicates_path)
    candidate_duplicates = _normalized_rows(candidate_duplicates_path)

    return InventoryReplayParityAudit(
        audit_id=DAILY_EVENT_INVENTORY_REPLAY_PARITY_AUDIT_ID,
        source_lineage=InventoryReplayParityLineage(
            reference_summary_sha256=_sha256_file(reference_summary_path),
            candidate_summary_sha256=_sha256_file(candidate_summary_path),
            reference_inventory_sha256=_sha256_file(reference_inventory_path),
            candidate_inventory_sha256=_sha256_file(candidate_inventory_path),
            reference_emissions_sha256=_sha256_file(reference_emissions_path),
            candidate_emissions_sha256=_sha256_file(candidate_emissions_path),
            reference_duplicates_sha256=_sha256_file(reference_duplicates_path),
            candidate_duplicates_sha256=_sha256_file(candidate_duplicates_path),
            snapshot_manifest_sha256=reference_manifest,
        ),
        summary_equal=reference_summary == candidate_summary,
        inventory_equal=reference_inventory == candidate_inventory,
        emissions_equal=reference_emissions == candidate_emissions,
        duplicates_equal=reference_duplicates == candidate_duplicates,
        reference_evidence_emission_count=int(
            reference_summary["evidence_emission_count"]
        ),
        candidate_evidence_emission_count=int(
            candidate_summary["evidence_emission_count"]
        ),
        reference_event_bar_count=int(reference_summary["event_bar_count"]),
        candidate_event_bar_count=int(candidate_summary["event_bar_count"]),
        inventory_row_symmetric_difference_count=len(
            reference_inventory ^ candidate_inventory
        ),
        emission_row_symmetric_difference_count=len(
            reference_emissions ^ candidate_emissions
        ),
        duplicate_row_symmetric_difference_count=len(
            reference_duplicates ^ candidate_duplicates
        ),
    )


def write_inventory_replay_parity_audit(
    audit: InventoryReplayParityAudit,
    output_dir: str | Path,
) -> InventoryReplayParityPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = InventoryReplayParityPaths(
        summary_json=root / "daily_event_inventory_replay_parity_summary.json"
    )
    payload = {
        "audit_id": audit.audit_id,
        "summary_equal": audit.summary_equal,
        "inventory_equal": audit.inventory_equal,
        "emissions_equal": audit.emissions_equal,
        "duplicates_equal": audit.duplicates_equal,
        "exact_match": audit.exact_match,
        "reference_evidence_emission_count": (
            audit.reference_evidence_emission_count
        ),
        "candidate_evidence_emission_count": (
            audit.candidate_evidence_emission_count
        ),
        "reference_event_bar_count": audit.reference_event_bar_count,
        "candidate_event_bar_count": audit.candidate_event_bar_count,
        "inventory_row_symmetric_difference_count": (
            audit.inventory_row_symmetric_difference_count
        ),
        "emission_row_symmetric_difference_count": (
            audit.emission_row_symmetric_difference_count
        ),
        "duplicate_row_symmetric_difference_count": (
            audit.duplicate_row_symmetric_difference_count
        ),
        "source_lineage": asdict(audit.source_lineage),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return paths


__all__ = [
    "DAILY_EVENT_INVENTORY_REPLAY_PARITY_AUDIT_ID",
    "InventoryReplayParityAudit",
    "InventoryReplayParityLineage",
    "InventoryReplayParityPaths",
    "build_inventory_replay_parity_audit",
    "write_inventory_replay_parity_audit",
]
