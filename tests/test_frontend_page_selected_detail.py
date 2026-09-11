from pathlib import Path

PAGE_PATH = Path("frontend/app/page.tsx")


def page_source() -> str:
    return PAGE_PATH.read_text(encoding="utf-8")


def test_selected_detail_imports_plain_english_helper() -> None:
    source = page_source()

    assert 'import { selectedEvidencePlainEnglish } from "./selected-evidence-legend-detail";' in source


def test_selected_detail_uses_helper_for_selected_and_latest_evidence() -> None:
    source = page_source()

    assert "const legendText = selectedEvidencePlainEnglish(legendLookup, selectedEvidence);" in source
    assert "const legendText = selectedEvidencePlainEnglish(legendLookup, displayedEvidence);" in source


def test_selected_detail_keeps_professional_reading_before_plain_english_meaning() -> None:
    source = page_source()

    selected_block_start = source.index("if (selectedEvidence) {")
    latest_block_start = source.index("if (displayedEvidence) {")
    selected_block = source[selected_block_start:latest_block_start]
    latest_block = source[latest_block_start:source.index("return <p>Select a chart marker")]

    selected_order = [
        "<h4>Professional Reading</h4>",
        "<p>{professionalReading(selectedEvidence)}</p>",
        "<h4>Plain-English meaning</h4>",
        "<p>{legendText}</p>",
    ]
    latest_order = [
        "<h4>Professional Reading</h4>",
        "<p>{professionalReading(displayedEvidence)}</p>",
        "<h4>Plain-English meaning</h4>",
        "<p>{legendText}</p>",
    ]

    selected_positions = [selected_block.index(item) for item in selected_order]
    latest_positions = [latest_block.index(item) for item in latest_order]

    assert selected_positions == sorted(selected_positions)
    assert latest_positions == sorted(latest_positions)


def test_selected_detail_registry_error_is_visible_but_separate() -> None:
    source = page_source()

    assert source.count("Plain-English legend registry unavailable: {legendRegistryError}") == 2
    assert "{legendRegistryError ? <small>Plain-English legend registry unavailable: {legendRegistryError}</small> : null}" in source
