from pathlib import Path

DATASET_FIXTURE_PATH = Path("frontend/app/effort-result-replay-dataset-fixture.ts")
ADAPTER_PATH = Path("frontend/app/effort-result-replay-dataset-adapter.ts")
HARNESS_PATH = Path("frontend/app/effort-result-replay-demo-harness.tsx")
ROUTE_PATH = Path("frontend/app/replay/effort-result/page.tsx")


def dataset_fixture_source() -> str:
    return DATASET_FIXTURE_PATH.read_text(encoding="utf-8")


def adapter_source() -> str:
    return ADAPTER_PATH.read_text(encoding="utf-8")


def harness_source() -> str:
    return HARNESS_PATH.read_text(encoding="utf-8")


def route_source() -> str:
    return ROUTE_PATH.read_text(encoding="utf-8")


def test_dataset_backed_preview_fixture_matches_audit_builder_contract() -> None:
    text = dataset_fixture_source()

    for snippet in [
        "report_type: \"effort_result_shadow_replay_dataset\"",
        "report_schema_version: 1",
        "source_report_type: \"effort_result_shadow_observations\"",
        "source_shadow_observation_status: \"shadow_observation_ready\"",
        "replay_dataset_status: \"shadow_replay_dataset_ready\"",
        "next_stage: \"shadow_replay_contract_review\"",
        "replay_sequences:",
        "frames:",
        "shadow_marker:",
        "source_gate_status:",
        "manual_review_status:",
    ]:
        assert snippet in text


def test_dataset_backed_preview_keeps_production_boundaries_closed() -> None:
    combined_text = "\n".join([dataset_fixture_source(), adapter_source(), harness_source()])

    for snippet in [
        "offlineDatasetFixtureOnly: true",
        "readOnlyAdapterOnly: true",
        "consumesProvidedJsonOnly: true",
        "usesDatasetAdapter: true",
        "liveApiFetchAllowed: false",
        "routeActivationAllowed: false",
        "productionSignalAllowed: false",
        "scoringAllowed: false",
        "rankingAllowed: false",
        "actionabilityAllowed: false",
        "detectorActivationAllowed: false",
        "scannerStateAllowed: false",
        "persistenceAllowed: false",
        "alertingAllowed: false",
        "orderExecutionAllowed: false",
        "automatic_promotion_allowed: false",
        "production_change_allowed: false",
        "may_change_scoring: false",
        "may_change_ranking: false",
        "may_change_actionability: false",
        "may_activate_detector: false",
        "may_change_api: false",
        "may_change_frontend: false",
        "emit_alert: false",
        "place_order: false",
        "persist_as_production_signal: false",
    ]:
        assert snippet in combined_text

    for forbidden in [
        "fetch(",
        "NEXT_PUBLIC_API_URL",
        "/api/",
        "submit_order(",
        "emitAlert(",
        "placeOrder(",
        "localStorage",
        "sessionStorage",
    ]:
        assert forbidden not in combined_text


def test_dataset_fixture_is_adapted_before_rendering() -> None:
    dataset_text = dataset_fixture_source()
    harness_text = harness_source()

    assert "isEffortResultShadowReplayDatasetReady(offlineEffortResultShadowReplayDatasetFixture)" in dataset_text
    assert "adaptEffortResultShadowReplayDataset(offlineEffortResultShadowReplayDatasetFixture)" in dataset_text
    assert "offlineEffortResultDatasetReplaySequences" in harness_text
    assert "offlineEffortResultReplayPreviewSequences" in harness_text
    assert "const replaySequences = getOfflineEffortResultReplayPreviewSequences();" in harness_text
    assert "<EffortResultReplayBar replaySequences={replaySequences} />" in harness_text


def test_route_still_uses_gated_preview_entrypoint_only() -> None:
    text = route_source()

    assert "EffortResultReplayPreviewEntrypoint" in text
    assert "isEffortResultReplayPreviewRouteEnabled" in text
    assert "data-dev-only-offline-preview=\"true\"" in text
    assert "data-live-api-fetch-allowed=\"false\"" in text
    assert "data-production-change-allowed=\"false\"" in text
    assert "effort-result-replay-dataset-fixture" not in text
    assert "adaptEffortResultShadowReplayDataset" not in text
