from pathlib import Path

COMPONENT_PATH = Path("frontend/app/effort-result-replay-bar.tsx")
ROOT_PAGE_PATH = Path("frontend/app/page.tsx")
REPLAY_ROUTE_PATH = Path("frontend/app/replay/page.tsx")


def source() -> str:
    return COMPONENT_PATH.read_text(encoding="utf-8")


def test_replay_bar_scaffold_exports_frontend_contract_types() -> None:
    text = source()

    assert '"use client";' in text
    assert "export type EffortResultShadowMarker" in text
    assert "export type EffortResultReplayFrame" in text
    assert "export type EffortResultReplaySequence" in text
    assert "export function EffortResultReplayBar" in text
    assert "replaySequences: EffortResultReplaySequence[]" in text


def test_replay_bar_scaffold_keeps_production_surfaces_disabled() -> None:
    text = source()

    assert "No API fetch, route activation, scoring, ranking, alerting, or detector activation" in text
    assert 'data-production-change-allowed="false"' in text
    assert "production_change_allowed?: false" in text
    assert "include_in_scoring?: false" in text
    assert "include_in_ranking?: false" in text
    assert "include_in_actionability?: false" in text
    assert "activate_detector?: false" in text
    assert "api_visible?: false" in text
    assert "frontend_visible?: false" in text
    assert "fetch(" not in text
    assert "NEXT_PUBLIC_API_URL" not in text


def test_replay_bar_scaffold_has_visual_backtest_controls() -> None:
    text = source()

    for snippet in [
        "Sequence",
        "Previous bar",
        "Play",
        "Pause",
        "Next bar",
        'aria-label="Replay scrubber"',
        'aria-label="Shadow marker rail"',
        "Replay offset:",
        "Shadow marker:",
    ]:
        assert snippet in text


def test_replay_bar_scaffold_is_not_routed_or_imported_yet() -> None:
    assert not REPLAY_ROUTE_PATH.exists()
    if ROOT_PAGE_PATH.exists():
        root_page = ROOT_PAGE_PATH.read_text(encoding="utf-8")
        assert "EffortResultReplayBar" not in root_page
        assert "effort-result-replay-bar" not in root_page
