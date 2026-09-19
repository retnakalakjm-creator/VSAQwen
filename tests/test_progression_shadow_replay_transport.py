from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = ROOT / "frontend/app/progression-shadow-replay-transport.tsx"
ENTRYPOINT = (
    ROOT / "frontend/app/progression-shadow-replay-preview-entrypoint.tsx"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_transport_has_play_pause_step_speed_and_scrubber() -> None:
    text = _text(TRANSPORT)
    for snippet in (
        "Play replay",
        "Pause replay",
        "Previous replay bar",
        "Next replay bar",
        'type="range"',
        'aria-label="Replay position"',
        'aria-label="Replay speed"',
        "0.5×",
        "1×",
        "2×",
    ):
        assert snippet in text


def test_transport_advances_only_one_causal_cursor_step_per_tick() -> None:
    text = _text(TRANSPORT)
    assert "cursor + 1" in text
    assert "Math.min(lastCursor, cursor + 1)" in text
    assert "window.setTimeout" in text
    assert 'data-causal-cursor-only="true"' in text
    assert 'data-future-bars-allowed="false"' in text


def test_sequence_and_dataset_changes_stop_playback_and_reset_cursor() -> None:
    text = _text(ENTRYPOINT)
    assert "setIsPlaying(false)" in text
    assert "setCursor(0)" in text
    assert "<ProgressionShadowReplayTransport" in text
    assert "frames={visibleFrames}" in text


def test_transport_has_no_network_storage_or_production_path() -> None:
    text = _text(TRANSPORT)
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
