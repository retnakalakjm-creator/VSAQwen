from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "frontend/app/progression-shadow-replay-preview-gate.ts"
FIXTURES = ROOT / "frontend/app/progression-shadow-replay-fixtures.ts"
ENTRYPOINT = ROOT / "frontend/app/progression-shadow-replay-preview-entrypoint.tsx"
ROUTE = ROOT / "frontend/app/replay/progression-semantic/page.tsx"
BOUNDARY = (
    ROOT
    / "frontend/app/replay/progression-semantic/preview-route-boundary.ts"
)
ROOT_PAGE = ROOT / "frontend/app/page.tsx"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_route_boundary_is_dev_only_offline_and_closed_to_production() -> None:
    text = _text(BOUNDARY)
    for snippet in (
        'route: "/replay/progression-semantic"',
        "devOnlyOfflinePreview: true",
        "enabledInProductionByDefault: false",
        "usesSyntheticFixtureOnly: true",
        "liveApiFetchAllowed: false",
        "productionSignalAllowed: false",
        "scoringAllowed: false",
        "rankingAllowed: false",
        "actionabilityAllowed: false",
        "qualificationMutationAllowed: false",
        "scannerStateAllowed: false",
        "persistenceAllowed: false",
        "alertingAllowed: false",
        "orderExecutionAllowed: false",
        'environment !== "production"',
    ):
        assert snippet in text


def test_preview_gate_defaults_closed_and_rejects_production_requests() -> None:
    text = _text(GATE)
    for snippet in (
        "enabledByDefault: false",
        "offlineSyntheticFixtureOnly: true",
        "liveApiFetchAllowed: false",
        "productionSignalAllowed: false",
        "actionabilityAllowed: false",
        "qualificationMutationAllowed: false",
        "persistenceAllowed: false",
        "orderExecutionAllowed: false",
        'reason: "blocked_for_production_boundary"',
        'reason: "disabled_by_default"',
    ):
        assert snippet in text


def test_fixture_preserves_k24_semantics_and_all_safety_flags() -> None:
    text = _text(FIXTURES)
    for role in (
        "TRANSITION_WARNING",
        "ALIGNED_PROGRESSION_OBSERVATION",
        "NEUTRAL_PROGRESSION_OBSERVATION",
    ):
        assert role in text

    for snippet in (
        "reversal_confirmed: false",
        "persistent_direction_claim: false",
        "affects_qualification: false",
        "affects_scoring: false",
        "is_actionable: false",
        "syntheticFixtureOnly: true",
        "liveApiFetchAllowed: false",
    ):
        assert snippet in text


def test_preview_is_causal_and_hides_future_frames() -> None:
    text = _text(ENTRYPOINT)
    assert "sequence.frames.slice(0, cursor + 1)" in text
    assert "semantic_role ??" in text
    assert "Next bar" in text
    assert "Previous bar" in text
    assert "Reset" in text


def test_route_and_preview_have_no_live_api_or_production_side_effects() -> None:
    combined = "\n".join(
        _text(path)
        for path in (GATE, FIXTURES, ENTRYPOINT, ROUTE, BOUNDARY)
    )
    for forbidden in (
        "fetch(",
        "NEXT_PUBLIC_API_URL",
        "/api/",
        "localStorage",
        "sessionStorage",
        "place_order",
        "submit_order(",
        "emit_alert",
    ):
        assert forbidden not in combined


def test_preview_is_not_imported_into_root_dashboard() -> None:
    if ROOT_PAGE.exists():
        text = _text(ROOT_PAGE)
        assert "ProgressionShadowReplayPreviewEntrypoint" not in text
        assert "/replay/progression-semantic" not in text
