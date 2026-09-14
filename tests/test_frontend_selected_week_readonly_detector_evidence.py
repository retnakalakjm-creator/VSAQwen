from pathlib import Path

PANEL_PATH = Path("frontend/app/bar-by-bar-panel.tsx")
CSS_PATH = Path("frontend/app/bar-by-bar-panel.module.css")
DOC_PATH = Path("docs/FRONTEND_READONLY_DETECTOR_EVIDENCE.md")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_selected_week_detector_evidence_filters_current_analysis_by_selected_week() -> None:
    panel = source(PANEL_PATH)

    assert "const selectedWeekDetectorEvidence = useMemo(() => {" in panel
    assert "if (!selectedReading) return [];" in panel
    assert "return detectorEvidence.filter((event) => event.week === selectedReading.week);" in panel
    assert "}, [detectorEvidence, selectedReading]);" in panel


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


def test_selected_week_detector_evidence_keeps_readonly_guardrails_visible() -> None:
    panel = source(PANEL_PATH)

    assert "function renderSelectedWeekDetectorEvidence()" in panel
    assert "<h4>Read-only Detector Evidence</h4>" in panel
    assert "Selected-week detector evidence is review-only" in panel
    assert "does not change scoring, ranking, actionability, trade plan, alerts, or orders" in panel
    assert "No Effort/Result or Absorption event in the current analysis response for this selected week." in panel
    assert "Detector evidence unavailable: {detectorError}" in panel
    assert "Loading detector evidence for selected week..." in panel


def test_selected_week_detector_evidence_lists_labels_observations_and_metadata() -> None:
    panel = source(PANEL_PATH)

    assert "selectedWeekDetectorEvidence.map((event) =>" in panel
    assert "Read-only / not scoring" in panel
    assert "<strong>{detectorCodeLabel(event.code)}</strong>" in panel
    assert "<p>{detectorReading(event)}</p>" in panel
    assert "<small>{event.category} · {event.direction}</small>" in panel


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
    assert "The selected weekly professional reading now includes a `Read-only Detector Evidence` block" in doc
    assert "filters the same production analysis response to the selected week" in doc
    assert "The selected-week block is also review-only" in doc
