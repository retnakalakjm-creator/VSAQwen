"""Detector-specific confirmation semantics audit built from canonical L3.

This module is audit-only. It does not replay market data and does not alter
production detector behavior. It joins the static detector contract to the
canonical L3 confirmation observations.
"""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import pandas as pd

from audit.daily_event_cofiring import DETECTOR_GATE_FUNCTIONS
from audit.daily_event_confirmation_counterfactual import (
    CONFIRMATION_SENSITIVE_CODES,
    DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID,
)


DAILY_DETECTOR_CONFIRMATION_SEMANTICS_AUDIT_ID = (
    "daily-event-detector-confirmation-semantics-v1"
)

_IDENTITY_COLUMNS = ("symbol", "session", "code")


@dataclass(frozen=True, slots=True)
class DailyConfirmationContractRow:
    code: str
    detector_function: str
    requirement_kind: str
    ordinal: int
    requirement_name: str
    passed_expression: str


@dataclass(frozen=True, slots=True)
class DailyConfirmationDetectorSummary:
    code: str
    detector_function: str
    current_event_count: int
    symbol_count: int
    mandatory_requirement_count: int
    mandatory_requirements: tuple[str, ...]
    confirmation_requirement_count: int
    confirmation_requirements: tuple[str, ...]
    mandatory_contract_sha256: str
    confirmation_contract_sha256: str
    same_mandatory_codes: tuple[str, ...]
    distinct_confirmation_pattern_count: int
    zero_confirmation_count: int
    zero_confirmation_rate: float
    any_confirmation_count: int
    any_confirmation_rate: float
    strict_majority_count: int
    strict_majority_rate: float
    all_confirmation_count: int
    all_confirmation_rate: float
    mean_passed_confirmation_count: float
    mean_pass_fraction: float


@dataclass(frozen=True, slots=True)
class DailyConfirmationRequirementRateRow:
    code: str
    confirmation_name: str
    passed_count: int
    failed_count: int
    pass_rate: float
    symbol_count_passed: int


@dataclass(frozen=True, slots=True)
class DailyConfirmationPatternRow:
    code: str
    confirmation_count: int
    passed_confirmation_count: int
    passed_confirmations: tuple[str, ...]
    failed_confirmations: tuple[str, ...]
    event_count: int
    event_share: float
    symbol_count: int


@dataclass(frozen=True, slots=True)
class DailyConfirmationSemanticsSourceLineage:
    l3_audit_id: str
    l3_summary_sha256: str
    l3_observations_sha256: str
    snapshot_manifest_sha256: str
    l1_summary_sha256: str
    l1_emissions_sha256: str
    l2_summary_sha256: str


@dataclass(frozen=True, slots=True)
class DailyDetectorConfirmationSemanticsAudit:
    audit_id: str
    source_lineage: DailyConfirmationSemanticsSourceLineage
    requested_symbol_count: int
    detector_count: int
    event_count: int
    contract_row_count: int
    confirmation_requirement_row_count: int
    pattern_row_count: int
    detector_rows: tuple[DailyConfirmationDetectorSummary, ...]
    contract_rows: tuple[DailyConfirmationContractRow, ...]
    requirement_rate_rows: tuple[DailyConfirmationRequirementRateRow, ...]
    pattern_rows: tuple[DailyConfirmationPatternRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyDetectorConfirmationSemanticsPaths:
    summary_json: Path
    detectors_csv: Path
    contracts_csv: Path
    requirement_rates_csv: Path
    patterns_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "detectors_csv": str(self.detectors_csv),
            "contracts_csv": str(self.contracts_csv),
            "requirement_rates_csv": str(self.requirement_rates_csv),
            "patterns_csv": str(self.patterns_csv),
        }


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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


def _assignment_items(
    function: object,
    variable_name: str,
) -> tuple[tuple[str, str], ...]:
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    assignment_value: ast.AST | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(
            isinstance(target, ast.Name)
            and target.id == variable_name
            for target in targets
        ):
            assignment_value = node.value
            break

    if assignment_value is None:
        return ()

    if not isinstance(assignment_value, (ast.Tuple, ast.List)):
        raise ValueError(
            f"{function.__name__}.{variable_name} must be tuple/list"
        )

    items: list[tuple[str, str]] = []
    for element in assignment_value.elts:
        if not isinstance(element, ast.Call):
            raise ValueError(
                f"{function.__name__}.{variable_name} contains non-call"
            )
        name_value: str | None = None
        passed_expression: str | None = None
        for keyword in element.keywords:
            if keyword.arg == "name":
                if not isinstance(keyword.value, ast.Constant):
                    raise ValueError("requirement name must be constant")
                name_value = str(keyword.value.value)
            elif keyword.arg == "passed":
                passed_expression = ast.unparse(keyword.value)
        if name_value is None or passed_expression is None:
            raise ValueError(
                f"{function.__name__}.{variable_name} requirement incomplete"
            )
        items.append((name_value, passed_expression))
    return tuple(items)


def build_confirmation_contract_rows(
) -> tuple[DailyConfirmationContractRow, ...]:
    affected = {code.value for code in CONFIRMATION_SENSITIVE_CODES}
    rows: list[DailyConfirmationContractRow] = []

    for code, function in DETECTOR_GATE_FUNCTIONS:
        if code.value not in affected:
            continue
        detector_function = f"{function.__module__}.{function.__name__}"
        for requirement_kind, variable_name in (
            ("MANDATORY", "requirements"),
            ("CONFIRMATION", "confirmations"),
        ):
            for ordinal, (name, expression) in enumerate(
                _assignment_items(function, variable_name),
                start=1,
            ):
                rows.append(
                    DailyConfirmationContractRow(
                        code=code.value,
                        detector_function=detector_function,
                        requirement_kind=requirement_kind,
                        ordinal=ordinal,
                        requirement_name=name,
                        passed_expression=expression,
                    )
                )

    observed_codes = {row.code for row in rows}
    if observed_codes != affected:
        raise ValueError(
            "detector contract extraction does not cover all L3 codes"
        )
    return tuple(rows)


def _contract_by_code(
    rows: tuple[DailyConfirmationContractRow, ...],
) -> dict[str, tuple[DailyConfirmationContractRow, ...]]:
    grouped: dict[str, list[DailyConfirmationContractRow]] = {}
    for row in rows:
        grouped.setdefault(row.code, []).append(row)
    return {
        code: tuple(
            sorted(
                items,
                key=lambda item: (
                    item.requirement_kind != "MANDATORY",
                    item.ordinal,
                ),
            )
        )
        for code, items in grouped.items()
    }


def _contract_signature(
    rows: tuple[DailyConfirmationContractRow, ...],
    kind: str,
) -> str:
    payload = [
        {
            "ordinal": row.ordinal,
            "name": row.requirement_name,
            "passed_expression": row.passed_expression,
        }
        for row in rows
        if row.requirement_kind == kind
    ]
    return _sha256_payload(payload)


def _validate_source_summary(
    summary: dict[str, object],
) -> None:
    if (
        summary.get("audit_id")
        != DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID
    ):
        raise ValueError("unexpected L3 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L4B requires non-actionable L3 source")
    if int(summary.get("failed_symbol_count", -1)) != 0:
        raise ValueError("L4B requires zero-failure L3 source")
    if int(summary.get("identity_mismatch_count", -1)) != 0:
        raise ValueError("L4B requires exact L3 identity parity")
    if int(summary.get("bar_index_mismatch_count", -1)) != 0:
        raise ValueError("L4B requires exact frozen L3 bar-index parity")
    requested = int(summary.get("requested_symbol_count", -1))
    succeeded = int(summary.get("succeeded_symbol_count", -2))
    if requested < 1 or requested != succeeded:
        raise ValueError("L4B requires all requested L3 symbols to succeed")
    baseline = int(summary.get("baseline_event_count", -1))
    captured = int(summary.get("captured_event_count", -2))
    if baseline < 1 or baseline != captured:
        raise ValueError("L4B requires exact L3 baseline/captured parity")
    physical = int(summary.get("physical_observation_count", -1))
    duplicates = int(summary.get("duplicate_observation_count", -1))
    if physical != captured + duplicates:
        raise ValueError("L3 physical observation accounting does not close")


def load_canonical_l3_observations(
    input_dir: str | Path,
) -> tuple[
    dict[str, object],
    pd.DataFrame,
    DailyConfirmationSemanticsSourceLineage,
]:
    root = Path(input_dir)
    summary_path = root / "daily_confirmation_counterfactual_summary.json"
    observations_path = root / "daily_confirmation_observations.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing L3 summary: {summary_path}")
    if not observations_path.exists():
        raise FileNotFoundError(
            f"missing L3 observations: {observations_path}"
        )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    _validate_source_summary(summary)

    observations = pd.read_csv(observations_path)
    required = {
        "symbol",
        "bar_index",
        "session",
        "code",
        "confirmation_count",
        "passed_confirmation_count",
        "passed_confirmations",
        "failed_confirmations",
    }
    missing = sorted(required - set(observations.columns))
    if missing:
        raise ValueError(f"L3 observations missing columns: {missing}")

    captured = int(summary["captured_event_count"])
    if len(observations) != captured:
        raise ValueError(
            "L3 observation row count does not match captured_event_count"
        )
    if observations.loc[:, list(_IDENTITY_COLUMNS)].duplicated().any():
        raise ValueError("L3 observations contain duplicate stable identities")

    expected_codes = {
        code.value for code in CONFIRMATION_SENSITIVE_CODES
    }
    observed_codes = set(map(str, observations["code"].unique()))
    if observed_codes != expected_codes:
        raise ValueError("L3 observations do not contain the exact 7 codes")

    for row in observations.itertuples(index=False):
        passed = _split_names(row.passed_confirmations)
        failed = _split_names(row.failed_confirmations)
        if set(passed) & set(failed):
            raise ValueError("confirmation cannot both pass and fail")
        if len(passed) != int(row.passed_confirmation_count):
            raise ValueError("passed confirmation count does not reconcile")
        if len(passed) + len(failed) != int(row.confirmation_count):
            raise ValueError("confirmation count does not reconcile")

    raw_lineage = summary.get("source_lineage")
    if not isinstance(raw_lineage, dict):
        raise ValueError("L3 source lineage is missing")
    required_lineage = (
        "snapshot_manifest_sha256",
        "l1_summary_sha256",
        "l1_emissions_sha256",
        "l2_summary_sha256",
    )
    if any(not str(raw_lineage.get(key, "")) for key in required_lineage):
        raise ValueError("L3 source lineage is incomplete")

    lineage = DailyConfirmationSemanticsSourceLineage(
        l3_audit_id=str(summary["audit_id"]),
        l3_summary_sha256=_sha256_file(summary_path),
        l3_observations_sha256=_sha256_file(observations_path),
        snapshot_manifest_sha256=str(
            raw_lineage["snapshot_manifest_sha256"]
        ),
        l1_summary_sha256=str(raw_lineage["l1_summary_sha256"]),
        l1_emissions_sha256=str(
            raw_lineage["l1_emissions_sha256"]
        ),
        l2_summary_sha256=str(raw_lineage["l2_summary_sha256"]),
    )
    return summary, observations, lineage


def _confirmation_names(
    rows: tuple[DailyConfirmationContractRow, ...],
) -> tuple[str, ...]:
    return tuple(
        row.requirement_name
        for row in rows
        if row.requirement_kind == "CONFIRMATION"
    )


def _mandatory_names(
    rows: tuple[DailyConfirmationContractRow, ...],
) -> tuple[str, ...]:
    return tuple(
        row.requirement_name
        for row in rows
        if row.requirement_kind == "MANDATORY"
    )


def _validate_observations_against_contract(
    observations: pd.DataFrame,
    contracts: dict[str, tuple[DailyConfirmationContractRow, ...]],
) -> None:
    for code, frame in observations.groupby("code", sort=False):
        expected = _confirmation_names(contracts[str(code)])
        expected_set = set(expected)
        expected_count = len(expected)
        if not (frame["confirmation_count"] == expected_count).all():
            raise ValueError(
                f"{code} confirmation_count differs from source contract"
            )
        for row in frame.itertuples(index=False):
            actual = set(_split_names(row.passed_confirmations)) | set(
                _split_names(row.failed_confirmations)
            )
            if actual != expected_set:
                raise ValueError(
                    f"{code} confirmation names differ from source contract"
                )


def _requirement_rate_rows(
    observations: pd.DataFrame,
    contracts: dict[str, tuple[DailyConfirmationContractRow, ...]],
) -> tuple[DailyConfirmationRequirementRateRow, ...]:
    rows: list[DailyConfirmationRequirementRateRow] = []
    for code in sorted(contracts):
        frame = observations.loc[observations["code"] == code]
        total = len(frame)
        for name in _confirmation_names(contracts[code]):
            passed_mask = frame["passed_confirmations"].fillna("").map(
                lambda value: name in _split_names(value)
            )
            passed_count = int(passed_mask.sum())
            rows.append(
                DailyConfirmationRequirementRateRow(
                    code=code,
                    confirmation_name=name,
                    passed_count=passed_count,
                    failed_count=total - passed_count,
                    pass_rate=passed_count / total if total else 0.0,
                    symbol_count_passed=int(
                        frame.loc[passed_mask, "symbol"].nunique()
                    ),
                )
            )
    return tuple(rows)


def _pattern_rows(
    observations: pd.DataFrame,
    contracts: dict[str, tuple[DailyConfirmationContractRow, ...]],
) -> tuple[DailyConfirmationPatternRow, ...]:
    rows: list[DailyConfirmationPatternRow] = []
    for code in sorted(contracts):
        frame = observations.loc[observations["code"] == code].copy()
        names = _confirmation_names(contracts[code])
        total = len(frame)

        def passed_tuple(value: object) -> tuple[str, ...]:
            actual = set(_split_names(value))
            return tuple(name for name in names if name in actual)

        frame["_passed_tuple"] = frame["passed_confirmations"].map(
            passed_tuple
        )
        for passed, group in frame.groupby("_passed_tuple", sort=False):
            passed_tuple_value = tuple(passed)
            failed = tuple(
                name for name in names if name not in passed_tuple_value
            )
            rows.append(
                DailyConfirmationPatternRow(
                    code=code,
                    confirmation_count=len(names),
                    passed_confirmation_count=len(passed_tuple_value),
                    passed_confirmations=passed_tuple_value,
                    failed_confirmations=failed,
                    event_count=len(group),
                    event_share=len(group) / total if total else 0.0,
                    symbol_count=int(group["symbol"].nunique()),
                )
            )

    return tuple(
        sorted(
            rows,
            key=lambda item: (
                item.code,
                -item.event_count,
                item.passed_confirmations,
            ),
        )
    )


def _detector_rows(
    observations: pd.DataFrame,
    contracts: dict[str, tuple[DailyConfirmationContractRow, ...]],
    patterns: tuple[DailyConfirmationPatternRow, ...],
) -> tuple[DailyConfirmationDetectorSummary, ...]:
    mandatory_hashes = {
        code: _contract_signature(rows, "MANDATORY")
        for code, rows in contracts.items()
    }
    confirmation_hashes = {
        code: _contract_signature(rows, "CONFIRMATION")
        for code, rows in contracts.items()
    }

    output: list[DailyConfirmationDetectorSummary] = []
    for code in sorted(contracts):
        frame = observations.loc[observations["code"] == code]
        total = len(frame)
        confirmation_count = len(_confirmation_names(contracts[code]))
        passed = frame["passed_confirmation_count"].astype(int)
        strict = passed * 2 > confirmation_count

        same_mandatory = tuple(
            sorted(
                other
                for other, digest in mandatory_hashes.items()
                if other != code and digest == mandatory_hashes[code]
            )
        )
        code_patterns = tuple(
            item for item in patterns if item.code == code
        )
        function_name = contracts[code][0].detector_function
        output.append(
            DailyConfirmationDetectorSummary(
                code=code,
                detector_function=function_name,
                current_event_count=total,
                symbol_count=int(frame["symbol"].nunique()),
                mandatory_requirement_count=len(
                    _mandatory_names(contracts[code])
                ),
                mandatory_requirements=_mandatory_names(contracts[code]),
                confirmation_requirement_count=confirmation_count,
                confirmation_requirements=_confirmation_names(
                    contracts[code]
                ),
                mandatory_contract_sha256=mandatory_hashes[code],
                confirmation_contract_sha256=confirmation_hashes[code],
                same_mandatory_codes=same_mandatory,
                distinct_confirmation_pattern_count=len(code_patterns),
                zero_confirmation_count=int((passed == 0).sum()),
                zero_confirmation_rate=(
                    float((passed == 0).mean()) if total else 0.0
                ),
                any_confirmation_count=int((passed >= 1).sum()),
                any_confirmation_rate=(
                    float((passed >= 1).mean()) if total else 0.0
                ),
                strict_majority_count=int(strict.sum()),
                strict_majority_rate=(
                    float(strict.mean()) if total else 0.0
                ),
                all_confirmation_count=int(
                    (passed == confirmation_count).sum()
                ),
                all_confirmation_rate=(
                    float((passed == confirmation_count).mean())
                    if total
                    else 0.0
                ),
                mean_passed_confirmation_count=(
                    float(passed.mean()) if total else 0.0
                ),
                mean_pass_fraction=(
                    float((passed / confirmation_count).mean())
                    if total and confirmation_count
                    else 0.0
                ),
            )
        )
    return tuple(output)


def build_detector_confirmation_semantics_audit(
    input_dir: str | Path,
) -> DailyDetectorConfirmationSemanticsAudit:
    summary, observations, lineage = load_canonical_l3_observations(
        input_dir
    )
    contract_rows = build_confirmation_contract_rows()
    contracts = _contract_by_code(contract_rows)
    _validate_observations_against_contract(observations, contracts)

    requirement_rates = _requirement_rate_rows(observations, contracts)
    patterns = _pattern_rows(observations, contracts)
    detectors = _detector_rows(observations, contracts, patterns)

    return DailyDetectorConfirmationSemanticsAudit(
        audit_id=DAILY_DETECTOR_CONFIRMATION_SEMANTICS_AUDIT_ID,
        source_lineage=lineage,
        requested_symbol_count=int(summary["requested_symbol_count"]),
        detector_count=len(detectors),
        event_count=len(observations),
        contract_row_count=len(contract_rows),
        confirmation_requirement_row_count=len(requirement_rates),
        pattern_row_count=len(patterns),
        detector_rows=detectors,
        contract_rows=contract_rows,
        requirement_rate_rows=requirement_rates,
        pattern_rows=patterns,
    )


def write_detector_confirmation_semantics_audit(
    audit: DailyDetectorConfirmationSemanticsAudit,
    output_dir: str | Path,
) -> DailyDetectorConfirmationSemanticsPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyDetectorConfirmationSemanticsPaths(
        summary_json=root / "daily_confirmation_semantics_summary.json",
        detectors_csv=root / "daily_confirmation_detector_summary.csv",
        contracts_csv=root / "daily_confirmation_detector_contracts.csv",
        requirement_rates_csv=(
            root / "daily_confirmation_requirement_rates.csv"
        ),
        patterns_csv=root / "daily_confirmation_pattern_distribution.csv",
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "detector_count": audit.detector_count,
        "event_count": audit.event_count,
        "contract_row_count": audit.contract_row_count,
        "confirmation_requirement_row_count": (
            audit.confirmation_requirement_row_count
        ),
        "pattern_row_count": audit.pattern_row_count,
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
                "mandatory_requirements": "|".join(
                    item.mandatory_requirements
                ),
                "confirmation_requirements": "|".join(
                    item.confirmation_requirements
                ),
                "same_mandatory_codes": "|".join(
                    item.same_mandatory_codes
                ),
            }
            for item in audit.detector_rows
        ]
    ).to_csv(paths.detectors_csv, index=False)

    pd.DataFrame(
        [asdict(item) for item in audit.contract_rows]
    ).to_csv(paths.contracts_csv, index=False)

    pd.DataFrame(
        [asdict(item) for item in audit.requirement_rate_rows]
    ).to_csv(paths.requirement_rates_csv, index=False)

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
            for item in audit.pattern_rows
        ]
    ).to_csv(paths.patterns_csv, index=False)
    return paths


__all__ = [
    "DAILY_DETECTOR_CONFIRMATION_SEMANTICS_AUDIT_ID",
    "DailyConfirmationContractRow",
    "DailyConfirmationDetectorSummary",
    "DailyConfirmationPatternRow",
    "DailyConfirmationRequirementRateRow",
    "DailyConfirmationSemanticsSourceLineage",
    "DailyDetectorConfirmationSemanticsAudit",
    "DailyDetectorConfirmationSemanticsPaths",
    "build_confirmation_contract_rows",
    "build_detector_confirmation_semantics_audit",
    "load_canonical_l3_observations",
    "write_detector_confirmation_semantics_audit",
]
