from types import SimpleNamespace

from evidence.effort import collect_effort
from models import ClosePosition, Direction, EvidenceCategory, EvidenceCode, SpreadClass, VolumeClass


def _context(
    *,
    direction=Direction.DOWN,
    volume=VolumeClass.VERY_HIGH,
    spread=SpreadClass.BELOW_AVERAGE,
    close=ClosePosition.LOWER,
    close_ratio=0.30,
    close_price=98.0,
    previous_close=100.0,
    low=95.0,
    previous_low=96.0,
):
    current = SimpleNamespace(
        direction=direction,
        volume=volume,
        spread=spread,
        close_position=close,
        close_ratio=close_ratio,
        close_price=close_price,
        prev_close=previous_close,
        low=low,
        bar_index=42,
        week_beginning="2026-05-25",
        spread_ratio=0.90,
        volume_ratio=1.90,
    )
    previous = SimpleNamespace(
        direction=Direction.DOWN,
        volume=VolumeClass.AVERAGE,
        spread=SpreadClass.AVERAGE,
        close_position=ClosePosition.MIDDLE,
        close_ratio=0.50,
        close_price=previous_close,
        low=previous_low,
        bar_index=41,
        week_beginning="2026-05-18",
        spread_ratio=1.00,
        volume_ratio=1.00,
    )
    return SimpleNamespace(current=current, previous=previous)


def _codes(ctx) -> tuple[EvidenceCode, ...]:
    return tuple(item.code for item in collect_effort(ctx))


def test_effort_gt_result_accepts_very_high_volume_below_average_spread() -> None:
    codes = _codes(_context())

    assert EvidenceCode.EFFORT_GT_RESULT in codes


def test_effort_gt_result_accepts_muted_downside_result() -> None:
    codes = _codes(
        _context(
            spread=SpreadClass.WIDE,
            close=ClosePosition.LOWER,
            close_ratio=0.25,
            close_price=98.2,
            previous_close=100.0,
        )
    )

    assert EvidenceCode.EFFORT_GT_RESULT in codes


def test_effort_gt_result_stays_read_only_weightless() -> None:
    evidence = collect_effort(_context())
    item = next(event for event in evidence if event.code is EvidenceCode.EFFORT_GT_RESULT)

    assert item.category is EvidenceCategory.EFFORT
    assert item.weight == 0.0


def test_effort_collector_connects_absorption_read_only_evidence() -> None:
    codes = _codes(
        _context(
            close=ClosePosition.MIDDLE,
            close_ratio=0.48,
            spread=SpreadClass.AVERAGE,
        )
    )

    assert EvidenceCode.ABSORPTION in codes


def test_effort_gt_result_rejects_ordinary_volume() -> None:
    codes = _codes(_context(volume=VolumeClass.AVERAGE))

    assert EvidenceCode.EFFORT_GT_RESULT not in codes
