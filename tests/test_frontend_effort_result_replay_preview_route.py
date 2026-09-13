from pathlib import Path

ROUTE_PATH = Path("frontend/app/replay/effort-result/page.tsx")
ROUTE_BOUNDARY_PATH = Path("frontend/app/replay/effort-result/preview-route-boundary.ts")
ROOT_PAGE_PATH = Path("frontend/app/page.tsx")
ROOT_REPLAY_ROUTE_PATH = Path("frontend/app/replay/page.tsx")
ENTRYPOINT_PATH = Path("frontend/app/effort-result-replay-preview-entrypoint.tsx")


def route_source() -> str:
    return ROUTE_PATH.read_text(encoding="utf-8")


def route_boundary_source() -> str:
    return ROUTE_BOUNDARY_PATH.read_text(encoding="utf-8")


def test_replay_preview_route_boundary_is_dev_only_offline_contract() -> None:
    text = route_boundary_source()

    for snippet in [
        "export const EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY",
        'route: "/replay/effort-result"',
        'routePurpose: "dev_only_offline_visual_review"',
        "devOnlyOfflinePreview: true",
        "enabledInProductionByDefault: false",
        "usesOfflineFixtureOnly: true",
        "usesExistingPreviewGate: true",
        "liveApiFetchAllowed: false",
        "productionSignalAllowed: false",
        "scoringAllowed: false",
        "rankingAllowed: false",
        "actionabilityAllowed: false",
        "detectorActivationAllowed: false",
        "scannerStateAllowed: false",
        "persistenceAllowed: false",
        "orderExecutionAllowed: false",
        "export function isEffortResultReplayPreviewRouteEnabled",
        'environment !== "production"',
    ]:
        assert snippet in text


def test_next_page_exports_only_supported_page_fields() -> None:
    text = route_source()

    assert "export const metadata" in text
    assert "export const dynamic" in text
    assert "export const revalidate" in text
    assert "export default function EffortResultReplayPreviewRoute" in text
    assert "export const EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY" not in text
    assert "export function" not in text


def test_replay_preview_route_uses_existing_gate_and_entrypoint() -> None:
    text = route_source()

    for snippet in [
        'import { EffortResultReplayPreviewEntrypoint } from "../../effort-result-replay-preview-entrypoint";',
        'import { EFFORT_RESULT_REPLAY_PREVIEW_GATE } from "../../effort-result-replay-preview-gate";',
        "EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY",
        "isEffortResultReplayPreviewRouteEnabled",
        'from "./preview-route-boundary";',
        "const enableOfflinePreview = isEffortResultReplayPreviewRouteEnabled();",
        'data-route={EFFORT_RESULT_REPLAY_PREVIEW_ROUTE_BOUNDARY.route}',
        'data-dev-only-offline-preview="true"',
        'data-offline-preview-enabled={enableOfflinePreview ? "true" : "false"}',
        'data-live-api-fetch-allowed="false"',
        'data-production-change-allowed="false"',
        "<EffortResultReplayPreviewEntrypoint enableOfflinePreview={enableOfflinePreview} />",
    ]:
        assert snippet in text


def test_replay_preview_route_has_no_live_or_production_side_effects() -> None:
    combined_text = route_source() + "\n" + route_boundary_source()

    for forbidden in [
        "fetch(",
        "NEXT_PUBLIC_API_URL",
        "/api/",
        "place_order",
        "submit_order(",
        "emit_alert",
        "localStorage",
        "sessionStorage",
    ]:
        assert forbidden not in combined_text


def test_route_does_not_import_into_root_dashboard_or_create_root_replay_page() -> None:
    assert not ROOT_REPLAY_ROUTE_PATH.exists()

    if ROOT_PAGE_PATH.exists():
        root_page = ROOT_PAGE_PATH.read_text(encoding="utf-8")
        assert "EffortResultReplayPreviewRoute" not in root_page
        assert "effort-result-replay-preview-route" not in root_page
        assert "effort-result-replay-preview-entrypoint" not in root_page


def test_existing_preview_entrypoint_remains_prop_gated() -> None:
    text = ENTRYPOINT_PATH.read_text(encoding="utf-8")

    assert "enableOfflinePreview = false" in text
    assert "evaluateEffortResultReplayPreviewGate({ enableOfflinePreview })" in text
    assert 'data-preview-gate="disabled"' in text
    assert 'data-preview-gate="enabled"' in text
