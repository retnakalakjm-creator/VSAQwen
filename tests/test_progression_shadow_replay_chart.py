from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "frontend/app/progression-shadow-replay-chart.tsx"
ENTRYPOINT = (
    ROOT / "frontend/app/progression-shadow-replay-preview-entrypoint.tsx"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_chart_uses_lightweight_candles_volume_and_event_markers() -> None:
    text = _text(CHART)
    for snippet in (
        "createChart",
        "CandlestickSeries",
        "HistogramSeries",
        "createSeriesMarkers",
        "candles.setData",
        "volume.setData",
        "markerForFrame",
        "chart.timeScale().fitContent()",
    ):
        assert snippet in text


def test_chart_receives_only_causal_visible_frames() -> None:
    entrypoint = _text(ENTRYPOINT)
    chart = _text(CHART)
    assert "sequence.frames.slice(0, cursor + 1)" in entrypoint
    assert "<ProgressionShadowReplayChart frames={visibleFrames}" in entrypoint
    assert "sequence.frames" not in chart
    assert 'data-future-bars-allowed="false"' in chart


def test_chart_has_no_network_persistence_or_production_path() -> None:
    text = _text(CHART)
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "/api/",
        "place_order",
        "submit_order(",
        "emit_alert",
    ):
        assert forbidden not in text
    assert 'data-live-api-fetch-allowed="false"' in text
    assert 'data-production-effect="none"' in text
