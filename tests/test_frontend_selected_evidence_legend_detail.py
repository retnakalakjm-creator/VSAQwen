from pathlib import Path

HELPER_PATH = Path("frontend/app/selected-evidence-legend-detail.ts")


def helper_source() -> str:
    return HELPER_PATH.read_text(encoding="utf-8")


def test_selected_evidence_fallback_normalizes_blank_text() -> None:
    source = helper_source()

    assert "function fallbackText" in source
    assert "const text = value?.trim();" in source
    assert "return text ? text : null;" in source


def test_selected_evidence_plain_english_fallback_order() -> None:
    source = helper_source()

    fallback_order = [
        'fallbackText(plainEnglishLegendText(lookup, { code: evidence.code, family: "evidence_code" }))',
        'fallbackText(plainEnglishLegendText(lookup, { code: evidence.code, family: "event_label" }))',
        "fallbackText(plainEnglishLegendText(lookup, { code: evidence.code }))",
        "fallbackText(evidence.description)",
        "fallbackText(evidence.observation)",
    ]

    positions = [source.index(item) for item in fallback_order]
    assert positions == sorted(positions)
