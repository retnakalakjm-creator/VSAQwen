from pathlib import Path

ADAPTER_PATH = Path("frontend/app/effort-result-replay-dataset-adapter.ts")
ROOT_PAGE_PATH = Path("frontend/app/page.tsx")
REPLAY_ROUTE_PATH = Path("frontend/app/replay/page.tsx")


def source() -> str:
    return ADAPTER_PATH.read_text(encoding="utf-8")


def test_replay_dataset_adapter_exports_read_only_contract() -> None:
    text = source()

    assert '"use client";' in text
    assert 'from "./effort-result-replay-bar";' in text
    assert "export const EFFORT_RESULT_REPLAY_DATASET_ADAPTER_BOUNDARY" in text
    assert "export type EffortResultShadowReplayDatasetInput" in text
    assert "export function adaptEffortResultShadowReplayDataset" in text
    assert "export function isEffortResultShadowReplayDatasetReady" in text
    assert "replay_sequences" in text
    assert "effort_result_shadow_replay_dataset" in text
    assert "shadow_replay_dataset_ready" in text


def test_replay_dataset_adapter_keeps_production_boundaries_closed() -> None:
    text = source()

    for snippet in [
        "readOnlyAdapterOnly: true",
        "consumesProvidedJsonOnly: true",
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


def test_replay_dataset_adapter_maps_dataset_shape_to_frontend_sequences() -> None:
    text = source()

    for snippet in [
        "function adaptShadowMarker",
        "function adaptReplayFrame",
        "function adaptReplaySequence",
        "EffortResultReplaySequence[]",
        "EffortResultReplayFrame",
        "EffortResultShadowMarker",
        "sequence.frames.map(adaptReplayFrame)",
        "source.replay_sequences",
    ]:
        assert snippet in text


def test_replay_dataset_adapter_is_not_routed_or_imported_yet() -> None:
    assert not REPLAY_ROUTE_PATH.exists()
    if ROOT_PAGE_PATH.exists():
        root_page = ROOT_PAGE_PATH.read_text(encoding="utf-8")
        assert "adaptEffortResultShadowReplayDataset" not in root_page
        assert "effort-result-replay-dataset-adapter" not in root_page
