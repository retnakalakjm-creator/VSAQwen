from pathlib import Path

EVIDENCE_PANEL_PATH = Path("frontend/app/effort-result-replay-evidence-draft-panel.tsx")
HARNESS_PATH = Path("frontend/app/effort-result-replay-demo-harness.tsx")
ROOT_PAGE_PATH = Path("frontend/app/page.tsx")
REPLAY_ROUTE_PATH = Path("frontend/app/replay/effort-result/page.tsx")


def evidence_panel_source() -> str:
    return EVIDENCE_PANEL_PATH.read_text(encoding="utf-8")


def harness_source() -> str:
    return HARNESS_PATH.read_text(encoding="utf-8")


def test_evidence_draft_panel_exports_manual_offline_boundary() -> None:
    text = evidence_panel_source()

    for snippet in [
        '"use client";',
        'import { useMemo, useState } from "react";',
        'import type { EffortResultReplaySequence } from "./effort-result-replay-bar";',
        "buildEffortResultMarkerOverlays",
        "EFFORT_RESULT_REPLAY_EVIDENCE_DRAFT_BOUNDARY",
        "visualReplayEvidenceDraftOnly: true",
        "offlinePreviewOnly: true",
        "manualReviewOnly: true",
        "readsReplaySequencesOnly: true",
        "browserMemoryOnly: true",
        "exportOnly: true",
        "persistenceAllowed: false",
        "uploadAllowed: false",
        "liveApiFetchAllowed: false",
        "productionSignalAllowed: false",
        "scoringAllowed: false",
        "rankingAllowed: false",
        "actionabilityAllowed: false",
        "detectorActivationAllowed: false",
        "scannerStateAllowed: false",
        "alertingAllowed: false",
        "orderExecutionAllowed: false",
    ]:
        assert snippet in text


def test_evidence_draft_panel_contains_expected_fields_and_statuses() -> None:
    text = evidence_panel_source()

    for snippet in [
        "marker_alignment_status",
        "pre_event_context_status",
        "post_event_follow_through_status",
        "counterfactual_scan_status",
        "vsa_smc_quality_status",
        "reviewer_notes",
        "screenshot_filename",
        '"unreviewed"',
        '"confirmed"',
        '"needs_attention"',
        '"rejected"',
        "Reviewer notes",
        "Screenshot filename",
        "Marker labels",
    ]:
        assert snippet in text


def test_evidence_draft_panel_builds_copy_ready_json_and_markdown() -> None:
    text = evidence_panel_source()

    for snippet in [
        "buildEffortResultReplayEvidenceExport",
        "renderEffortResultReplayEvidenceMarkdownDraft",
        "effort_result_visual_replay_evidence_draft",
        "manual_visual_replay",
        "JSON.stringify(evidenceDraft, null, 2)",
        "Copy-ready JSON draft",
        "Copy-ready Markdown draft",
        "readOnly",
        "textarea",
    ]:
        assert snippet in text


def test_evidence_draft_panel_has_no_storage_upload_or_live_side_effects() -> None:
    text = evidence_panel_source()

    for forbidden in [
        "fetch(",
        "NEXT_PUBLIC_API_URL",
        "/api/",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "navigator.clipboard",
        "document.cookie",
        "sendBeacon",
        "WebSocket",
        "EventSource",
        "place_order",
        "submit_order(",
        "broker",
        "emit_alert",
    ]:
        assert forbidden not in text


def test_demo_harness_wires_evidence_panel_inside_offline_workbench() -> None:
    text = harness_source()

    for snippet in [
        'import { EffortResultReplayEvidenceDraftPanel } from "./effort-result-replay-evidence-draft-panel";',
        'data-visual-evidence-draft-panel="true"',
        '<EffortResultReplayBar replaySequences={replaySequences} />',
        '<EffortResultReplayReviewChecklist replaySequences={replaySequences} />',
        '<EffortResultReplayEvidenceDraftPanel replaySequences={replaySequences} />',
    ]:
        assert snippet in text

    assert "fetch(" not in text
    assert "NEXT_PUBLIC_API_URL" not in text
    assert "/api/" not in text
    assert "localStorage" not in text
    assert "sessionStorage" not in text


def test_route_and_root_do_not_import_evidence_panel_directly() -> None:
    for path in [ROOT_PAGE_PATH, REPLAY_ROUTE_PATH]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "EffortResultReplayEvidenceDraftPanel" not in text
        assert "effort-result-replay-evidence-draft-panel" not in text
