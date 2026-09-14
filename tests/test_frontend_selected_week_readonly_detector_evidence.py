from pathlib import Path

PANEL_PATH = Path("frontend/app/bar-by-bar-panel.tsx")
CSS_PATH = Path("frontend/app/bar-by-bar-panel.module.css")
DOC_PATH = Path("docs/FRONTEND_READONLY_DETECTOR_EVIDENCE.md")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_selected_week_detector_evidence_uses_historical_audit_endpoint() -> None:
    panel = source(PANEL_PATH)

    assert "type AuditEventsResponse" in panel
    assert "function selectedWeekDetectorEventsFromAudit(" in panel
    assert "`${API}/api/vsa-audit/events?symbols=${encodedSymbol}&start_week=${encodedStartWeek}&horizon_weeks=1`" in panel
    assert "Selected-week detector evidence failed" in panel
    assert "const selectedWeekForAudit = selectedReadingWeek;" in panel
    assert "auditWeekParam(selectedWeekForAudit)" in panel
    assert "selectedWeekDetectorEventsFromAudit(payload, selectedWeekForAudit)" in panel


def test_selected_week_detector_evidence_extracts_readonly_codes_from_audit_row() -> None:
    panel = source(PANEL_PATH)

    assert "row.target_event_codes ?? []" in panel
    assert "row.vsa_event_codes ?? []" in panel
    assert "READ_ONLY_DETECTOR_CODES.has(code)" in panel
    assert "effort_gt_result" in panel
    assert "result_gt_effort" in panel
    assert "absorption" in panel
    assert "high_volume_reversal" in panel


def test_selected_week_detector_evidence_renders_below_professional_reading() -> None:
    panel = source(PANEL_PATH)
    selected_article_start = panel.index("<article className={`selected-bar-reading")
    selected_article_end = panel.index("</article>", selected_article_start)
    selected_article = panel[selected_article_start:selected_article_end]

    expected_order = [
        "<h4>Professional Reading</h4>",
        "<p>{selectedReading.professional_reading}</p>",
        "{renderSelectedWeekDetectorEvidence()}",
    ]
    positions = [selected_article.index(snippet) for snippet in expected_order]

    assert positions == sorted(positions)


def test_duplicate_bottom_readonly_detector_summary_panel_is_removed() -> None:
    panel = source(PANEL_PATH)
    css = source(CSS_PATH)

    assert "function renderReadOnlyDetectorEvidence()" not in panel
    assert "READ-ONLY DETECTOR EVIDENCE" not in panel
    assert "Effort / Result and Absorption" not in panel
    assert "readOnlyDetectorPanel" not in panel
    assert "readOnlyDetectorGrid" not in panel
    assert "readOnlyDetectorCard" not in panel
    assert ".readOnlyDetectorPanel" not in css
    assert ".readOnlyDetectorGrid" not in css
    assert ".readOnlyDetectorCard" not in css


def test_selected_week_detector_evidence_keeps_readonly_guardrails_visible() -> None:
    panel = source(PANEL_PATH)

    assert "function renderSelectedWeekDetectorEvidence()" in panel
    assert "<h4>Read-only Detector Evidence</h4>" in panel
    assert "Selected-week detector evidence comes from the historical audit endpoint" in panel
    assert "does not change scoring, ranking, actionability, trade plan, alerts, or orders" in panel
    assert "No Effort/Result, Absorption, or High Volume Reversal event in the historical audit response for this selected week." in panel
    assert "Selected-week audit evidence unavailable: {detectorError}" in panel
    assert "Loading selected-week audit evidence..." in panel


def test_selected_week_detector_evidence_lists_labels_notes_and_audit_date() -> None:
    panel = source(PANEL_PATH)

    assert "selectedWeekDetectorEvidence.map((event) =>" in panel
    assert "Read-only / not scoring" in panel
    assert "<strong>{detectorCodeLabel(event.code)}</strong>" in panel
    assert "<p>{detectorReading(event)}</p>" in panel
    assert "<small>Historical audit · {displayDate(event.week)}</small>" in panel
    assert "High Volume Reversal" in panel


def test_selected_week_detector_evidence_has_css_and_docs() -> None:
    css = source(CSS_PATH)
    doc = source(DOC_PATH)

    for class_name in (
        ".selectedWeekDetectorEvidence",
        ".selectedWeekDetectorGuardrail",
        ".selectedWeekDetectorList",
        ".selectedWeekDetectorItem",
    ):
        assert class_name in css

    assert "## Selected-week behavior" in doc
    assert "historical audit endpoint" in doc
    assert "/api/vsa-audit/events?symbols={symbol}&start_week={selected_week}&horizon_weeks=1" in doc
    assert "older separate bottom summary cards were removed" in doc
    assert "high_volume_reversal" in doc
    assert "The selected-week block is review-only" in doc