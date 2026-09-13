from pathlib import Path

CHECKLIST_PATH = Path("frontend/app/effort-result-replay-review-checklist.tsx")
HARNESS_PATH = Path("frontend/app/effort-result-replay-demo-harness.tsx")
ROUTE_PATH = Path("frontend/app/replay/effort-result/page.tsx")
ROOT_PAGE_PATH = Path("frontend/app/page.tsx")


def checklist_source() -> str:
    return CHECKLIST_PATH.read_text(encoding="utf-8")


def harness_source() -> str:
    return HARNESS_PATH.read_text(encoding="utf-8")


def route_source() -> str:
    return ROUTE_PATH.read_text(encoding="utf-8")


def test_review_checklist_exports_visual_review_only_contract() -> None:
    text = checklist_source()

    for snippet in [
        '"use client";',
        'import type { EffortResultReplaySequence } from "./effort-result-replay-bar";',
        'import { buildEffortResultMarkerOverlays } from "./effort-result-replay-bar";',
        "export const EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_BOUNDARY",
        "visualReviewChecklistOnly: true",
        "offlinePreviewOnly: true",
        "readsReplaySequencesOnly: true",
        "manualReviewOnly: true",
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
    ]:
        assert snippet in text


def test_review_checklist_lists_sequence_context_and_questions() -> None:
    text = checklist_source()

    for snippet in [
        "export const EFFORT_RESULT_REPLAY_REVIEW_CHECKLIST_QUESTIONS",
        "Did the marker appear on the correct bar?",
        "Did the prior context support the signal?",
        "Did follow-through confirm or reject it?",
        "Did the setup look like real VSA/SMC quality?",
        "replaySequences.map",
        "sequence.symbol",
        "sequence.event_week_beginning",
        "sequence.target",
        "expectedRelationshipFor(sequence)",
        "markerLabelsFor(sequence)",
        "priorContextFor(sequence)",
        "followThroughFor(sequence)",
        'data-review-sequence-id={sequence.sequence_id}',
        'data-target={sequence.target}',
        'data-symbol={sequence.symbol}',
        'type="checkbox"',
    ]:
        assert snippet in text


def test_review_checklist_derives_marker_labels_from_existing_overlays() -> None:
    text = checklist_source()

    for snippet in [
        "buildEffortResultMarkerOverlays(sequence.frames)",
        ".map((overlay) => overlay.label)",
        "Array.from(new Set(labels))",
        'return uniqueLabels.length > 0 ? uniqueLabels.join(", ") : "No shadow marker";',
    ]:
        assert snippet in text


def test_demo_harness_renders_checklist_beside_replay_bar() -> None:
    text = harness_source()

    for snippet in [
        'import { EffortResultReplayReviewChecklist } from "./effort-result-replay-review-checklist";',
        'data-visual-review-checklist="true"',
        'className="replay-preview-workbench"',
        'data-visual-review-workbench="true"',
        "<EffortResultReplayBar replaySequences={replaySequences} />",
        "<EffortResultReplayReviewChecklist replaySequences={replaySequences} />",
    ]:
        assert snippet in text


def test_route_remains_existing_gated_entrypoint_without_direct_checklist_import() -> None:
    text = route_source()

    assert "EffortResultReplayPreviewEntrypoint" in text
    assert "isEffortResultReplayPreviewRouteEnabled" in text
    assert "EffortResultReplayReviewChecklist" not in text
    assert "effort-result-replay-review-checklist" not in text


def test_review_checklist_has_no_live_or_production_side_effects() -> None:
    combined_text = checklist_source() + "\n" + harness_source()

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
        assert forbidden not in combined_text

    if ROOT_PAGE_PATH.exists():
        root_page = ROOT_PAGE_PATH.read_text(encoding="utf-8")
        assert "EffortResultReplayReviewChecklist" not in root_page
        assert "effort-result-replay-review-checklist" not in root_page
