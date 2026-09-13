from pathlib import Path

FIXTURE_PATH = Path("frontend/app/effort-result-replay-fixtures.ts")
DATASET_FIXTURE_PATH = Path("frontend/app/effort-result-replay-dataset-fixture.ts")
HARNESS_PATH = Path("frontend/app/effort-result-replay-demo-harness.tsx")
ROOT_PAGE_PATH = Path("frontend/app/page.tsx")
REPLAY_ROUTE_PATH = Path("frontend/app/replay/page.tsx")


def fixture_source() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def dataset_fixture_source() -> str:
    return DATASET_FIXTURE_PATH.read_text(encoding="utf-8")


def harness_source() -> str:
    return HARNESS_PATH.read_text(encoding="utf-8")


def test_offline_replay_fixture_exports_static_sequences() -> None:
    text = fixture_source()

    assert 'import type { EffortResultReplaySequence } from "./effort-result-replay-bar";' in text
    assert "export const EFFORT_RESULT_REPLAY_FIXTURE_SOURCE" in text
    assert "export const offlineEffortResultReplaySequences: EffortResultReplaySequence[]" in text
    assert "offline-lt-2025-03-03-result-gt-effort" in text
    assert "offline-lt-2026-03-02-supply-pressure" in text
    assert "RESULT_GT_EFFORT" in text
    assert "SUPPLY_PRESSURE" in text
    assert "export function getOfflineEffortResultReplaySequences()" in text


def test_offline_fixture_keeps_all_production_boundaries_closed() -> None:
    text = fixture_source()

    for snippet in [
        "offlineFixtureOnly: true",
        "demoHarnessOnly: true",
        "liveApiFetchAllowed: false",
        "routeActivationAllowed: false",
        "productionSignalAllowed: false",
        "scoringAllowed: false",
        "rankingAllowed: false",
        "actionabilityAllowed: false",
        "detectorActivationAllowed: false",
        "scannerStateAllowed: false",
        "persistenceAllowed: false",
        "brokerOrOrderAllowed: false",
        "include_in_scoring: false",
        "include_in_ranking: false",
        "include_in_actionability: false",
        "activate_detector: false",
        "api_visible: false",
        "frontend_visible: false",
        "production_change_allowed: false",
    ]:
        assert snippet in text

    assert "fetch(" not in text
    assert "NEXT_PUBLIC_API_URL" not in text
    assert "/api/" not in text


def test_dataset_fixture_uses_read_only_adapter_for_dataset_shape() -> None:
    text = dataset_fixture_source()

    for snippet in [
        'from "./effort-result-replay-dataset-adapter";',
        "EFFORT_RESULT_REPLAY_DATASET_ADAPTER_BOUNDARY",
        "adaptEffortResultShadowReplayDataset",
        "isEffortResultShadowReplayDatasetReady",
        "offlineEffortResultShadowReplayDatasetFixture",
        "offlineEffortResultDatasetReplaySequences",
        "getOfflineEffortResultDatasetReplaySequences",
        "effort_result_shadow_replay_dataset",
        "shadow_replay_dataset_ready",
        "RESULT_GT_EFFORT|LT.NS|11",
        "SUPPLY_PRESSURE|LT.NS|41",
    ]:
        assert snippet in text


def test_demo_harness_renders_static_and_dataset_fixture_data_only() -> None:
    text = harness_source()

    assert '"use client";' in text
    assert 'import { EffortResultReplayBar } from "./effort-result-replay-bar";' in text
    assert 'from "./effort-result-replay-fixtures";' in text
    assert 'from "./effort-result-replay-dataset-fixture";' in text
    assert "offlineEffortResultReplayPreviewSequences: EffortResultReplaySequence[]" in text
    assert "...offlineEffortResultReplaySequences" in text
    assert "...offlineEffortResultDatasetReplaySequences" in text
    assert "getOfflineEffortResultReplayPreviewSequences" in text
    assert "offlineEffortResultReplaySequences.length" in text
    assert "offlineEffortResultDatasetReplaySequences.length" in text
    assert "Static visual validation harness only." in text
    assert "adapted dataset-shaped" in text
    assert "does not fetch live data" in text
    assert 'data-demo-only="true"' in text
    assert 'data-production-change-allowed="false"' in text
    assert 'data-dataset-backed-preview="true"' in text
    assert "<EffortResultReplayBar replaySequences={replaySequences} />" in text


def test_demo_harness_has_no_live_or_production_side_effects() -> None:
    text = harness_source()

    for forbidden in [
        "fetch(",
        "NEXT_PUBLIC_API_URL",
        "/api/",
        "place_order",
        "submit_order(",
        "broker",
        "emit_alert",
        "localStorage",
        "sessionStorage",
    ]:
        assert forbidden not in text


def test_offline_demo_harness_keeps_root_dashboard_unchanged() -> None:
    assert not REPLAY_ROUTE_PATH.exists()
    if ROOT_PAGE_PATH.exists():
        root_page = ROOT_PAGE_PATH.read_text(encoding="utf-8")
        assert "EffortResultReplayDemoHarness" not in root_page
        assert "effort-result-replay-demo-harness" not in root_page
        assert "effort-result-replay-fixtures" not in root_page
        assert "effort-result-replay-dataset-fixture" not in root_page
