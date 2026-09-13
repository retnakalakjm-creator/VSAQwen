from pathlib import Path

GATE_PATH = Path("frontend/app/effort-result-replay-preview-gate.ts")
ENTRYPOINT_PATH = Path("frontend/app/effort-result-replay-preview-entrypoint.tsx")
ROOT_PAGE_PATH = Path("frontend/app/page.tsx")
REPLAY_ROUTE_PATH = Path("frontend/app/replay/page.tsx")


def gate_source() -> str:
    return GATE_PATH.read_text(encoding="utf-8")


def entrypoint_source() -> str:
    return ENTRYPOINT_PATH.read_text(encoding="utf-8")


def test_preview_gate_exports_disabled_default_contract() -> None:
    text = gate_source()

    for snippet in [
        "export const EFFORT_RESULT_REPLAY_PREVIEW_GATE",
        "previewEntrypointOnly: true",
        "enabledByDefault: false",
        "requiresExplicitPreviewEnablement: true",
        "offlineDemoHarnessOnly: true",
        "export function evaluateEffortResultReplayPreviewGate",
        'reason: "disabled_by_default"',
        'reason: "enabled_for_offline_demo_only"',
    ]:
        assert snippet in text


def test_preview_gate_blocks_live_or_production_surfaces() -> None:
    text = gate_source()

    for snippet in [
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
        "production_change_allowed: false",
        "route_activation_allowed: false",
        "live_api_fetch_allowed: false",
        "input.allowRouteActivation === true",
        "input.allowLiveApiFetch === true",
        "input.allowProductionSignals === true",
        'reason: "blocked_for_production_boundary"',
    ]:
        assert snippet in text

    assert "fetch(" not in text
    assert "NEXT_PUBLIC_API_URL" not in text
    assert "/api/" not in text


def test_preview_entrypoint_is_explicit_prop_gated() -> None:
    text = entrypoint_source()

    for snippet in [
        '"use client";',
        'import { EffortResultReplayDemoHarness } from "./effort-result-replay-demo-harness";',
        "evaluateEffortResultReplayPreviewGate({ enableOfflinePreview })",
        "enableOfflinePreview = false",
        'data-preview-gate="disabled"',
        'data-preview-gate="enabled"',
        'data-demo-only="true"',
        'data-production-change-allowed="false"',
        'data-live-api-fetch-allowed="false"',
        "<EffortResultReplayDemoHarness />",
        "DisabledEffortResultReplayPreviewEntrypoint",
    ]:
        assert snippet in text


def test_preview_entrypoint_has_no_live_or_production_side_effects() -> None:
    text = entrypoint_source()

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


def test_preview_entrypoint_is_not_routed_or_imported_yet() -> None:
    assert not REPLAY_ROUTE_PATH.exists()

    if ROOT_PAGE_PATH.exists():
        root_page = ROOT_PAGE_PATH.read_text(encoding="utf-8")
        assert "EffortResultReplayPreviewEntrypoint" not in root_page
        assert "effort-result-replay-preview-entrypoint" not in root_page
        assert "EffortResultReplayDemoHarness" not in root_page
