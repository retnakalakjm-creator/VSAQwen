"""Audit-only design matrix for detector correction candidates.

L5 consumes canonical L3/L4B artifacts. It does not replay market data and it
does not modify production detector semantics. The purpose is to separate
ledger-projectable correction candidates from changes that require a fresh
causal replay before they can be evaluated.
"""

from __future__ import annotations

import ast
import inspect
import itertools
import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable

import pandas as pd

import evidence.rules as rules_module
from audit.daily_event_confirmation_counterfactual import (
    DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID,
)
from audit.daily_event_confirmation_semantics import (
    DAILY_DETECTOR_CONFIRMATION_SEMANTICS_AUDIT_ID,
)


DAILY_DETECTOR_CORRECTION_DESIGN_AUDIT_ID = (
    "daily-event-detector-correction-design-v1"
)

_FINDING_MANDATORY_COLLISION = "IDENTICAL_MANDATORY_CONTRACT"
_FINDING_ENV_POLARITY = "ENVIRONMENT_LABEL_PREDICATE_POLARITY_MISMATCH"
_FINDING_REDUNDANT_CONFIRMATION = (
    "REDUNDANT_CONFIRMATION_IMPLIED_BY_MANDATORY"
)


@dataclass(frozen=True, slots=True)
class DailyCorrectionDesignSourceLineage:
    l4b_audit_id: str
    l4b_summary_sha256: str
    l4b_detectors_sha256: str
    l4b_contracts_sha256: str
    l4b_requirement_rates_sha256: str
    l4b_patterns_sha256: str
    l3_audit_id: str
    l3_summary_sha256: str
    l3_observations_sha256: str
    snapshot_manifest_sha256: str
    l1_summary_sha256: str
    l1_emissions_sha256: str
    l2_summary_sha256: str


@dataclass(frozen=True, slots=True)
class DailyCorrectionFinding:
    finding_id: str
    issue_type: str
    codes: tuple[str, ...]
    requirement_kind: str
    requirement_name: str
    passed_expression: str
    related_requirement_name: str
    related_passed_expression: str
    evidence_class: str
    requires_replay_for_semantic_change: bool
    description: str


@dataclass(frozen=True, slots=True)
class DailyCollisionGateCandidate:
    collision_id: str
    code: str
    candidate_id: str
    required_confirmations: tuple[str, ...]
    required_confirmation_count: int
    retained_event_count: int
    retained_event_rate: float
    symbol_count: int
    is_distinctive_only: bool


@dataclass(frozen=True, slots=True)
class DailyCollisionProjectionRow:
    collision_id: str
    code_a: str
    candidate_a_id: str
    code_b: str
    candidate_b_id: str
    code_a_count: int
    code_b_count: int
    overlap_count: int
    union_count: int
    jaccard: float
    code_a_only_count: int
    code_b_only_count: int
    current_union_count: int
    covered_current_count: int
    covered_current_rate: float
    is_distinctive_pair: bool


@dataclass(frozen=True, slots=True)
class DailyCorrectionCandidate:
    candidate_id: str
    finding_id: str
    code: str
    effect_class: str
    data_sufficiency: str
    requires_replay: bool
    changes_current_emissions: bool | None
    current_event_count: int
    projected_event_count: int | None
    projected_any_count: int | None
    projected_strict_majority_count: int | None
    projected_all_count: int | None
    description: str


@dataclass(frozen=True, slots=True)
class DailyDetectorCorrectionDesignAudit:
    audit_id: str
    source_lineage: DailyCorrectionDesignSourceLineage
    requested_symbol_count: int
    event_count: int
    finding_count: int
    mandatory_collision_pair_count: int
    gate_candidate_count: int
    collision_projection_row_count: int
    correction_candidate_count: int
    findings: tuple[DailyCorrectionFinding, ...]
    gate_candidates: tuple[DailyCollisionGateCandidate, ...]
    collision_rows: tuple[DailyCollisionProjectionRow, ...]
    correction_candidates: tuple[DailyCorrectionCandidate, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyDetectorCorrectionDesignPaths:
    summary_json: Path
    findings_csv: Path
    gate_candidates_csv: Path
    collision_matrix_csv: Path
    correction_candidates_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "findings_csv": str(self.findings_csv),
            "gate_candidates_csv": str(self.gate_candidates_csv),
            "collision_matrix_csv": str(self.collision_matrix_csv),
            "correction_candidates_csv": str(
                self.correction_candidates_csv
            ),
        }


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _split_names(value: object) -> tuple[str, ...]:
    if value is None or pd.isna(value):
        return ()
    text = str(value).strip()
    if not text:
        return ()
    return tuple(item for item in text.split("|") if item)


def _validate_l4b_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_DETECTOR_CONFIRMATION_SEMANTICS_AUDIT_ID
    ):
        raise ValueError("unexpected L4B audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L5 requires a non-actionable L4B source")
    if int(summary.get("requested_symbol_count", -1)) < 1:
        raise ValueError("L4B requested_symbol_count must be positive")
    if int(summary.get("detector_count", -1)) != 7:
        raise ValueError("L5 requires the canonical seven detectors")
    if int(summary.get("event_count", -1)) < 1:
        raise ValueError("L4B event_count must be positive")


def _validate_l3_summary(summary: dict[str, object]) -> None:
    if (
        summary.get("audit_id")
        != DAILY_EVENT_CONFIRMATION_COUNTERFACTUAL_AUDIT_ID
    ):
        raise ValueError("unexpected L3 audit_id")
    if summary.get("is_actionable") is not False:
        raise ValueError("L5 requires a non-actionable L3 source")
    if int(summary.get("failed_symbol_count", -1)) != 0:
        raise ValueError("L5 requires zero-failure L3 source")
    if int(summary.get("identity_mismatch_count", -1)) != 0:
        raise ValueError("L5 requires exact L3 identity parity")
    if int(summary.get("bar_index_mismatch_count", -1)) != 0:
        raise ValueError("L5 requires exact L3 bar-index parity")


def _read_csv(path: Path, expected_rows: int | None = None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path)
    if expected_rows is not None and len(frame) != expected_rows:
        raise ValueError(
            f"{path.name} row count {len(frame)} != {expected_rows}"
        )
    return frame


def load_correction_design_sources(
    *,
    semantics_dir: str | Path,
    confirmation_dir: str | Path,
) -> tuple[
    dict[str, object],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    DailyCorrectionDesignSourceLineage,
]:
    l4b_root = Path(semantics_dir)
    l3_root = Path(confirmation_dir)

    l4b_summary_path = l4b_root / "daily_confirmation_semantics_summary.json"
    l3_summary_path = (
        l3_root / "daily_confirmation_counterfactual_summary.json"
    )
    l3_observations_path = (
        l3_root / "daily_confirmation_observations.csv"
    )

    if not l4b_summary_path.exists():
        raise FileNotFoundError(l4b_summary_path)
    if not l3_summary_path.exists():
        raise FileNotFoundError(l3_summary_path)
    if not l3_observations_path.exists():
        raise FileNotFoundError(l3_observations_path)

    l4b_summary = json.loads(
        l4b_summary_path.read_text(encoding="utf-8")
    )
    l3_summary = json.loads(
        l3_summary_path.read_text(encoding="utf-8")
    )
    _validate_l4b_summary(l4b_summary)
    _validate_l3_summary(l3_summary)

    l4b_lineage = l4b_summary.get("source_lineage")
    if not isinstance(l4b_lineage, dict):
        raise ValueError("L4B source lineage is missing")

    actual_l3_summary_sha = _sha256_file(l3_summary_path)
    actual_l3_observations_sha = _sha256_file(l3_observations_path)
    if l4b_lineage.get("l3_audit_id") != l3_summary.get("audit_id"):
        raise ValueError("L4B/L3 audit lineage mismatch")
    if l4b_lineage.get("l3_summary_sha256") != actual_l3_summary_sha:
        raise ValueError("L4B points to a different L3 summary")
    if (
        l4b_lineage.get("l3_observations_sha256")
        != actual_l3_observations_sha
    ):
        raise ValueError("L4B points to a different L3 observation ledger")

    event_count = int(l4b_summary["event_count"])
    if event_count != int(l3_summary.get("captured_event_count", -1)):
        raise ValueError("L4B/L3 event count mismatch")

    detectors_path = l4b_root / "daily_confirmation_detector_summary.csv"
    contracts_path = l4b_root / "daily_confirmation_detector_contracts.csv"
    rates_path = l4b_root / "daily_confirmation_requirement_rates.csv"
    patterns_path = (
        l4b_root / "daily_confirmation_pattern_distribution.csv"
    )

    detectors = _read_csv(
        detectors_path,
        int(l4b_summary["detector_count"]),
    )
    contracts = _read_csv(
        contracts_path,
        int(l4b_summary["contract_row_count"]),
    )
    rates = _read_csv(
        rates_path,
        int(l4b_summary["confirmation_requirement_row_count"]),
    )
    patterns = _read_csv(
        patterns_path,
        int(l4b_summary["pattern_row_count"]),
    )
    observations = _read_csv(l3_observations_path, event_count)

    required_observation_columns = {
        "symbol",
        "session",
        "code",
        "passed_confirmations",
        "failed_confirmations",
    }
    missing = sorted(
        required_observation_columns - set(observations.columns)
    )
    if missing:
        raise ValueError(f"L3 observations missing columns: {missing}")
    if observations[["symbol", "session", "code"]].duplicated().any():
        raise ValueError("L3 observations contain duplicate identities")

    l3_lineage = l3_summary.get("source_lineage")
    if not isinstance(l3_lineage, dict):
        raise ValueError("L3 source lineage is missing")

    for key in (
        "snapshot_manifest_sha256",
        "l1_summary_sha256",
        "l1_emissions_sha256",
        "l2_summary_sha256",
    ):
        if str(l4b_lineage.get(key, "")) != str(l3_lineage.get(key, "")):
            raise ValueError(f"L4B/L3 lineage mismatch for {key}")

    lineage = DailyCorrectionDesignSourceLineage(
        l4b_audit_id=str(l4b_summary["audit_id"]),
        l4b_summary_sha256=_sha256_file(l4b_summary_path),
        l4b_detectors_sha256=_sha256_file(detectors_path),
        l4b_contracts_sha256=_sha256_file(contracts_path),
        l4b_requirement_rates_sha256=_sha256_file(rates_path),
        l4b_patterns_sha256=_sha256_file(patterns_path),
        l3_audit_id=str(l3_summary["audit_id"]),
        l3_summary_sha256=actual_l3_summary_sha,
        l3_observations_sha256=actual_l3_observations_sha,
        snapshot_manifest_sha256=str(
            l3_lineage["snapshot_manifest_sha256"]
        ),
        l1_summary_sha256=str(l3_lineage["l1_summary_sha256"]),
        l1_emissions_sha256=str(l3_lineage["l1_emissions_sha256"]),
        l2_summary_sha256=str(l3_lineage["l2_summary_sha256"]),
    )
    return (
        l4b_summary,
        detectors,
        contracts,
        rates,
        patterns,
        observations,
        lineage,
    )


def _direct_rule_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for name, value in vars(rules_module).items():
        if not inspect.isfunction(value):
            continue
        if value.__module__ != rules_module.__name__:
            continue
        try:
            tree = ast.parse(inspect.getsource(value))
        except (OSError, TypeError, IndentationError):
            continue
        function = next(
            (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            ),
            None,
        )
        if function is None or len(function.body) != 1:
            continue
        statement = function.body[0]
        if not isinstance(statement, ast.Return):
            continue
        call = statement.value
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name):
            continue
        aliases[name] = call.func.id
    return aliases


def _normalize_contract_expression(
    expression: str,
    aliases: dict[str, str],
) -> str:
    try:
        node = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return expression
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in aliases
    ):
        node.func.id = aliases[node.func.id]
        return ast.unparse(node)
    return ast.unparse(node)


def _collision_findings(
    detectors: pd.DataFrame,
) -> tuple[DailyCorrectionFinding, ...]:
    rows: list[DailyCorrectionFinding] = []
    groups = detectors.groupby("mandatory_contract_sha256", sort=True)
    index = 1
    for _, frame in groups:
        codes = tuple(sorted(map(str, frame["code"])))
        if len(codes) < 2:
            continue
        for code_a, code_b in itertools.combinations(codes, 2):
            rows.append(
                DailyCorrectionFinding(
                    finding_id=f"mandatory-collision-{index:02d}",
                    issue_type=_FINDING_MANDATORY_COLLISION,
                    codes=(code_a, code_b),
                    requirement_kind="MANDATORY",
                    requirement_name="",
                    passed_expression="",
                    related_requirement_name="",
                    related_passed_expression="",
                    evidence_class="LEDGER_PROJECTABLE",
                    requires_replay_for_semantic_change=False,
                    description=(
                        "Detectors share the exact mandatory source contract; "
                        "existing L3 confirmation observations can project "
                        "candidate confirmation gates without replay."
                    ),
                )
            )
            index += 1
    return tuple(rows)


def _environment_polarity_findings(
    contracts: pd.DataFrame,
) -> tuple[DailyCorrectionFinding, ...]:
    rows: list[DailyCorrectionFinding] = []
    index = 1
    for item in contracts.itertuples(index=False):
        if str(item.requirement_kind) != "MANDATORY":
            continue
        name = str(item.requirement_name)
        expression = str(item.passed_expression)
        name_lower = name.lower()
        expression_lower = expression.lower()
        mismatch = (
            "bullish" in name_lower and "bearish" in expression_lower
        ) or (
            "bearish" in name_lower and "bullish" in expression_lower
        )
        if not mismatch:
            continue
        rows.append(
            DailyCorrectionFinding(
                finding_id=f"environment-polarity-{index:02d}",
                issue_type=_FINDING_ENV_POLARITY,
                codes=(str(item.code),),
                requirement_kind="MANDATORY",
                requirement_name=name,
                passed_expression=expression,
                related_requirement_name="",
                related_passed_expression="",
                evidence_class="SOURCE_ONLY",
                requires_replay_for_semantic_change=True,
                description=(
                    "Requirement label and predicate express opposite "
                    "environment polarity. Renaming the label preserves "
                    "events; changing the predicate requires causal replay."
                ),
            )
        )
        index += 1
    return tuple(rows)


def _redundant_confirmation_findings(
    contracts: pd.DataFrame,
) -> tuple[DailyCorrectionFinding, ...]:
    aliases = _direct_rule_aliases()
    rows: list[DailyCorrectionFinding] = []
    index = 1
    for code, frame in contracts.groupby("code", sort=True):
        mandatory = frame.loc[frame["requirement_kind"] == "MANDATORY"]
        confirmations = frame.loc[
            frame["requirement_kind"] == "CONFIRMATION"
        ]
        for confirmation in confirmations.itertuples(index=False):
            normalized_confirmation = _normalize_contract_expression(
                str(confirmation.passed_expression),
                aliases,
            )
            for requirement in mandatory.itertuples(index=False):
                normalized_mandatory = _normalize_contract_expression(
                    str(requirement.passed_expression),
                    aliases,
                )
                if normalized_confirmation != normalized_mandatory:
                    continue
                rows.append(
                    DailyCorrectionFinding(
                        finding_id=f"redundant-confirmation-{index:02d}",
                        issue_type=_FINDING_REDUNDANT_CONFIRMATION,
                        codes=(str(code),),
                        requirement_kind="CONFIRMATION",
                        requirement_name=str(
                            confirmation.requirement_name
                        ),
                        passed_expression=str(
                            confirmation.passed_expression
                        ),
                        related_requirement_name=str(
                            requirement.requirement_name
                        ),
                        related_passed_expression=str(
                            requirement.passed_expression
                        ),
                        evidence_class="SOURCE_AND_LEDGER",
                        requires_replay_for_semantic_change=False,
                        description=(
                            "Confirmation normalizes to the same source "
                            "predicate as a mandatory requirement and is "
                            "therefore implied once the detector candidate "
                            "passes the mandatory gate."
                        ),
                    )
                )
                index += 1
    return tuple(rows)


def build_correction_findings(
    detectors: pd.DataFrame,
    contracts: pd.DataFrame,
) -> tuple[DailyCorrectionFinding, ...]:
    rows = (
        *_collision_findings(detectors),
        *_environment_polarity_findings(contracts),
        *_redundant_confirmation_findings(contracts),
    )
    return tuple(
        sorted(rows, key=lambda item: (item.issue_type, item.finding_id))
    )


def _confirmation_names(
    contracts: pd.DataFrame,
    code: str,
) -> tuple[str, ...]:
    frame = contracts.loc[
        (contracts["code"] == code)
        & (contracts["requirement_kind"] == "CONFIRMATION")
    ].sort_values("ordinal")
    return tuple(map(str, frame["requirement_name"]))


def _passed_set(value: object) -> frozenset[str]:
    return frozenset(_split_names(value))


def _candidate_id(required: Iterable[str]) -> str:
    parts = [
        "".join(
            character.lower() if character.isalnum() else "-"
            for character in name
        ).strip("-")
        for name in required
    ]
    return "and__" + "__".join(parts)


def _identity_set(
    frame: pd.DataFrame,
    required: frozenset[str],
) -> set[tuple[str, str]]:
    return {
        (str(row.symbol), str(row.session))
        for row in frame.itertuples(index=False)
        if required <= _passed_set(row.passed_confirmations)
    }


def _collision_gate_candidates(
    findings: tuple[DailyCorrectionFinding, ...],
    contracts: pd.DataFrame,
    observations: pd.DataFrame,
) -> tuple[
    tuple[DailyCollisionGateCandidate, ...],
    dict[tuple[str, str, str], set[tuple[str, str]]],
    dict[str, tuple[str, str]],
    dict[str, tuple[str, ...]],
]:
    candidates: list[DailyCollisionGateCandidate] = []
    identity_sets: dict[
        tuple[str, str, str],
        set[tuple[str, str]],
    ] = {}
    collision_codes: dict[str, tuple[str, str]] = {}
    distinctive_by_key: dict[str, tuple[str, ...]] = {}

    collision_findings = [
        item
        for item in findings
        if item.issue_type == _FINDING_MANDATORY_COLLISION
    ]
    for finding in collision_findings:
        if len(finding.codes) != 2:
            continue
        code_a, code_b = finding.codes
        collision_codes[finding.finding_id] = (code_a, code_b)
        names_a = _confirmation_names(contracts, code_a)
        names_b = _confirmation_names(contracts, code_b)
        shared = set(names_a) & set(names_b)
        distinctive_a = tuple(name for name in names_a if name not in shared)
        distinctive_b = tuple(name for name in names_b if name not in shared)
        distinctive_by_key[f"{finding.finding_id}:{code_a}"] = distinctive_a
        distinctive_by_key[f"{finding.finding_id}:{code_b}"] = distinctive_b

        for code, names, distinctive in (
            (code_a, names_a, distinctive_a),
            (code_b, names_b, distinctive_b),
        ):
            frame = observations.loc[observations["code"] == code]
            total = len(frame)
            for size in range(1, len(names) + 1):
                for subset in itertools.combinations(names, size):
                    required = frozenset(subset)
                    candidate_id = _candidate_id(subset)
                    identities = _identity_set(frame, required)
                    identity_sets[
                        (finding.finding_id, code, candidate_id)
                    ] = identities
                    candidates.append(
                        DailyCollisionGateCandidate(
                            collision_id=finding.finding_id,
                            code=code,
                            candidate_id=candidate_id,
                            required_confirmations=tuple(subset),
                            required_confirmation_count=len(subset),
                            retained_event_count=len(identities),
                            retained_event_rate=(
                                len(identities) / total if total else 0.0
                            ),
                            symbol_count=len(
                                {symbol for symbol, _ in identities}
                            ),
                            is_distinctive_only=(
                                bool(distinctive)
                                and tuple(subset) == distinctive
                            ),
                        )
                    )

    return (
        tuple(
            sorted(
                candidates,
                key=lambda item: (
                    item.collision_id,
                    item.code,
                    item.required_confirmation_count,
                    item.candidate_id,
                ),
            )
        ),
        identity_sets,
        collision_codes,
        distinctive_by_key,
    )


def _collision_projection_rows(
    *,
    gate_candidates: tuple[DailyCollisionGateCandidate, ...],
    identity_sets: dict[
        tuple[str, str, str],
        set[tuple[str, str]],
    ],
    collision_codes: dict[str, tuple[str, str]],
    observations: pd.DataFrame,
) -> tuple[DailyCollisionProjectionRow, ...]:
    rows: list[DailyCollisionProjectionRow] = []
    for collision_id, (code_a, code_b) in collision_codes.items():
        candidates_a = [
            item
            for item in gate_candidates
            if item.collision_id == collision_id and item.code == code_a
        ]
        candidates_b = [
            item
            for item in gate_candidates
            if item.collision_id == collision_id and item.code == code_b
        ]
        current_a = {
            (str(row.symbol), str(row.session))
            for row in observations.loc[
                observations["code"] == code_a
            ].itertuples(index=False)
        }
        current_b = {
            (str(row.symbol), str(row.session))
            for row in observations.loc[
                observations["code"] == code_b
            ].itertuples(index=False)
        }
        current_union = current_a | current_b
        for candidate_a in candidates_a:
            set_a = identity_sets[
                (collision_id, code_a, candidate_a.candidate_id)
            ]
            for candidate_b in candidates_b:
                set_b = identity_sets[
                    (collision_id, code_b, candidate_b.candidate_id)
                ]
                overlap = set_a & set_b
                union = set_a | set_b
                rows.append(
                    DailyCollisionProjectionRow(
                        collision_id=collision_id,
                        code_a=code_a,
                        candidate_a_id=candidate_a.candidate_id,
                        code_b=code_b,
                        candidate_b_id=candidate_b.candidate_id,
                        code_a_count=len(set_a),
                        code_b_count=len(set_b),
                        overlap_count=len(overlap),
                        union_count=len(union),
                        jaccard=(
                            len(overlap) / len(union) if union else 0.0
                        ),
                        code_a_only_count=len(set_a - set_b),
                        code_b_only_count=len(set_b - set_a),
                        current_union_count=len(current_union),
                        covered_current_count=len(union),
                        covered_current_rate=(
                            len(union) / len(current_union)
                            if current_union
                            else 0.0
                        ),
                        is_distinctive_pair=(
                            candidate_a.is_distinctive_only
                            and candidate_b.is_distinctive_only
                        ),
                    )
                )
    return tuple(
        sorted(
            rows,
            key=lambda item: (
                item.collision_id,
                item.candidate_a_id,
                item.candidate_b_id,
            ),
        )
    )


def _no_supply_correction_candidates(
    findings: tuple[DailyCorrectionFinding, ...],
    contracts: pd.DataFrame,
    observations: pd.DataFrame,
) -> tuple[DailyCorrectionCandidate, ...]:
    code = "no_supply"
    frame = observations.loc[observations["code"] == code]
    if frame.empty:
        return ()
    current = len(frame)
    rows: list[DailyCorrectionCandidate] = []

    environment = next(
        (
            item
            for item in findings
            if item.issue_type == _FINDING_ENV_POLARITY
            and item.codes == (code,)
        ),
        None,
    )
    if environment is not None:
        rows.extend(
            (
                DailyCorrectionCandidate(
                    candidate_id="no-supply-align-label-to-bearish-predicate",
                    finding_id=environment.finding_id,
                    code=code,
                    effect_class="LABEL_ONLY",
                    data_sufficiency="SOURCE_DETERMINISTIC",
                    requires_replay=False,
                    changes_current_emissions=False,
                    current_event_count=current,
                    projected_event_count=current,
                    projected_any_count=None,
                    projected_strict_majority_count=None,
                    projected_all_count=None,
                    description=(
                        "Rename the requirement label to match the existing "
                        "bearish-environment predicate. Detector behavior is "
                        "unchanged."
                    ),
                ),
                DailyCorrectionCandidate(
                    candidate_id="no-supply-align-predicate-to-bullish-label",
                    finding_id=environment.finding_id,
                    code=code,
                    effect_class="MANDATORY_PREDICATE_CHANGE",
                    data_sufficiency="REPLAY_REQUIRED",
                    requires_replay=True,
                    changes_current_emissions=None,
                    current_event_count=current,
                    projected_event_count=None,
                    projected_any_count=None,
                    projected_strict_majority_count=None,
                    projected_all_count=None,
                    description=(
                        "Change the predicate to bullish environment to match "
                        "the existing label. L3 did not record alternate "
                        "environment eligibility, so event impact cannot be "
                        "projected from the ledger."
                    ),
                ),
            )
        )

    redundancy = next(
        (
            item
            for item in findings
            if item.issue_type == _FINDING_REDUNDANT_CONFIRMATION
            and item.codes == (code,)
        ),
        None,
    )
    if redundancy is not None:
        all_names = _confirmation_names(contracts, code)
        remaining = tuple(
            name
            for name in all_names
            if name != redundancy.requirement_name
        )
        passed_sets = frame["passed_confirmations"].map(_passed_set)
        any_count = int(
            passed_sets.map(
                lambda values: bool(set(remaining) & set(values))
            ).sum()
        )
        all_count = int(
            passed_sets.map(
                lambda values: set(remaining) <= set(values)
            ).sum()
        )
        strict_count = int(
            passed_sets.map(
                lambda values: (
                    sum(name in values for name in remaining) * 2
                    > len(remaining)
                )
            ).sum()
        )
        rows.append(
            DailyCorrectionCandidate(
                candidate_id="no-supply-remove-redundant-weak-spread",
                finding_id=redundancy.finding_id,
                code=code,
                effect_class="CONFIRMATION_CONTRACT_CHANGE",
                data_sufficiency="LEDGER_PROJECTABLE",
                requires_replay=False,
                changes_current_emissions=False,
                current_event_count=current,
                projected_event_count=current,
                projected_any_count=any_count,
                projected_strict_majority_count=strict_count,
                projected_all_count=all_count,
                description=(
                    "Remove the confirmation already implied by mandatory "
                    "Narrow Spread. CURRENT emissions stay unchanged because "
                    "confirmations are non-gating; future threshold arithmetic "
                    "would use the remaining confirmation clauses."
                ),
            )
        )

    return tuple(rows)


def build_detector_correction_design_audit(
    *,
    semantics_dir: str | Path,
    confirmation_dir: str | Path,
) -> DailyDetectorCorrectionDesignAudit:
    (
        l4b_summary,
        detectors,
        contracts,
        _rates,
        _patterns,
        observations,
        lineage,
    ) = load_correction_design_sources(
        semantics_dir=semantics_dir,
        confirmation_dir=confirmation_dir,
    )

    findings = build_correction_findings(detectors, contracts)
    (
        gate_candidates,
        identity_sets,
        collision_codes,
        _distinctive,
    ) = _collision_gate_candidates(findings, contracts, observations)
    collision_rows = _collision_projection_rows(
        gate_candidates=gate_candidates,
        identity_sets=identity_sets,
        collision_codes=collision_codes,
        observations=observations,
    )
    correction_candidates = _no_supply_correction_candidates(
        findings,
        contracts,
        observations,
    )

    collision_count = sum(
        item.issue_type == _FINDING_MANDATORY_COLLISION
        for item in findings
    )
    return DailyDetectorCorrectionDesignAudit(
        audit_id=DAILY_DETECTOR_CORRECTION_DESIGN_AUDIT_ID,
        source_lineage=lineage,
        requested_symbol_count=int(
            l4b_summary["requested_symbol_count"]
        ),
        event_count=int(l4b_summary["event_count"]),
        finding_count=len(findings),
        mandatory_collision_pair_count=collision_count,
        gate_candidate_count=len(gate_candidates),
        collision_projection_row_count=len(collision_rows),
        correction_candidate_count=len(correction_candidates),
        findings=findings,
        gate_candidates=gate_candidates,
        collision_rows=collision_rows,
        correction_candidates=correction_candidates,
    )


def write_detector_correction_design_audit(
    audit: DailyDetectorCorrectionDesignAudit,
    output_dir: str | Path,
) -> DailyDetectorCorrectionDesignPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = DailyDetectorCorrectionDesignPaths(
        summary_json=root / "daily_detector_correction_design_summary.json",
        findings_csv=root / "daily_detector_correction_findings.csv",
        gate_candidates_csv=(
            root / "daily_detector_collision_gate_candidates.csv"
        ),
        collision_matrix_csv=(
            root / "daily_detector_collision_projection_matrix.csv"
        ),
        correction_candidates_csv=(
            root / "daily_detector_correction_candidates.csv"
        ),
    )

    summary = {
        "audit_id": audit.audit_id,
        "requested_symbol_count": audit.requested_symbol_count,
        "event_count": audit.event_count,
        "finding_count": audit.finding_count,
        "mandatory_collision_pair_count": (
            audit.mandatory_collision_pair_count
        ),
        "gate_candidate_count": audit.gate_candidate_count,
        "collision_projection_row_count": (
            audit.collision_projection_row_count
        ),
        "correction_candidate_count": (
            audit.correction_candidate_count
        ),
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
                "codes": "|".join(item.codes),
            }
            for item in audit.findings
        ]
    ).to_csv(paths.findings_csv, index=False)

    pd.DataFrame(
        [
            {
                **asdict(item),
                "required_confirmations": "|".join(
                    item.required_confirmations
                ),
            }
            for item in audit.gate_candidates
        ]
    ).to_csv(paths.gate_candidates_csv, index=False)

    pd.DataFrame(
        [asdict(item) for item in audit.collision_rows]
    ).to_csv(paths.collision_matrix_csv, index=False)

    pd.DataFrame(
        [asdict(item) for item in audit.correction_candidates]
    ).to_csv(paths.correction_candidates_csv, index=False)
    return paths


__all__ = [
    "DAILY_DETECTOR_CORRECTION_DESIGN_AUDIT_ID",
    "DailyCollisionGateCandidate",
    "DailyCollisionProjectionRow",
    "DailyCorrectionCandidate",
    "DailyCorrectionDesignSourceLineage",
    "DailyCorrectionFinding",
    "DailyDetectorCorrectionDesignAudit",
    "DailyDetectorCorrectionDesignPaths",
    "build_correction_findings",
    "build_detector_correction_design_audit",
    "load_correction_design_sources",
    "write_detector_correction_design_audit",
]
