from __future__ import annotations

from types import SimpleNamespace

import scripts.audit_daily_event_inventory as runner
from audit.daily_event_inventory import DailyEventInventoryInputProvenance
from audit.daily_event_inventory_runner import FrozenSnapshotReplayResult
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    DailyAuditInputFingerprint,
)


def _bundle() -> DailyAuditInputBundle:
    fingerprint = DailyAuditInputFingerprint(
        symbol="LT.NS",
        version="daily-ohlcv-v1",
        period="max",
        cutoff="2026-09-18T00:00:00",
        row_count=2,
        first_session="2026-09-17T00:00:00",
        last_session="2026-09-18T00:00:00",
        sha256="a" * 64,
        relative_path="snapshots/LT.NS.csv",
    )
    return DailyAuditInputBundle(
        audit_id="daily-audit-input-snapshot-v1",
        basket_name="milestone6_standard_india_large_cap_30",
        provider="fixture",
        period="max",
        cutoff="2026-09-18T00:00:00",
        symbol_count=1,
        fingerprints=(fingerprint,),
    )


def test_snapshot_mode_never_calls_production_loader(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        runner,
        "load_daily_audit_input_bundle",
        lambda _: _bundle(),
    )
    monkeypatch.setattr(
        runner,
        "daily_audit_input_manifest_sha256",
        lambda _: "b" * 64,
    )

    def forbidden_download(*args, **kwargs):
        raise AssertionError("production loader must not be called")

    monkeypatch.setattr(runner, "download_data", forbidden_download)

    def fake_replay(symbols, **kwargs):
        seen["symbols"] = tuple(symbols)
        seen["workers"] = kwargs["workers"]
        seen["progress_writer"] = kwargs["progress_writer"]
        return FrozenSnapshotReplayResult(
            archives=("archive",),
            failures=(),
            worker_count=3,
        )

    monkeypatch.setattr(
        runner,
        "run_frozen_snapshot_replay",
        fake_replay,
    )

    fake_audit = SimpleNamespace(
        audit_id="daily-event-inventory-point-in-time-v1",
        requested_symbol_count=1,
        succeeded_symbol_count=1,
        failed_symbol_count=0,
        evaluated_bar_count=1,
        defined_code_count=37,
        profile_registered_code_count=21,
        legacy_registry_code_count=10,
        active_collector_code_count=20,
        behavior_mapped_code_count=29,
        emitted_code_count=0,
        evidence_emission_count=0,
        event_bar_count=0,
        duplicate_group_count=0,
        duplicate_extra_emission_count=0,
        active_not_observed_code_count=0,
        behavior_mapped_inactive_code_count=0,
        behavior_direction_mismatch_count=0,
        input_provenance=DailyEventInventoryInputProvenance(
            source="FROZEN_DAILY_INPUT_SNAPSHOT",
            snapshot_audit_id="daily-audit-input-snapshot-v1",
            snapshot_manifest_sha256="b" * 64,
            snapshot_basket_name=(
                "milestone6_standard_india_large_cap_30"
            ),
            snapshot_period="max",
            snapshot_cutoff="2026-09-18T00:00:00",
        ),
    )

    def fake_build(**kwargs):
        seen["archives"] = kwargs["archives"]
        seen["provenance"] = kwargs["input_provenance"]
        return fake_audit

    monkeypatch.setattr(
        runner,
        "build_daily_event_inventory_audit",
        fake_build,
    )
    monkeypatch.setattr(
        runner,
        "write_daily_event_inventory_audit",
        lambda audit, output_dir: SimpleNamespace(
            as_dict=lambda: {
                "summary_json": str(tmp_path / "summary.json")
            }
        ),
    )

    result = runner.main(
        [
            "--symbols",
            "LT.NS",
            "--now",
            "2026-09-18T16:00:00+05:30",
            "--input-snapshot-dir",
            str(tmp_path),
            "--workers",
            "3",
            "--output-dir",
            str(tmp_path / "output"),
        ]
    )

    assert result == 0
    assert seen["symbols"] == ("LT.NS",)
    assert seen["workers"] == 3
    assert seen["archives"] == ("archive",)
    provenance = seen["provenance"]
    assert provenance.source == "FROZEN_DAILY_INPUT_SNAPSHOT"
    assert provenance.snapshot_period == "max"

    output = capsys.readouterr().out
    assert '"source": "FROZEN_DAILY_INPUT_SNAPSHOT"' in output
    assert '"snapshot_worker_count": 3' in output


def test_snapshot_mode_rejects_refresh(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        runner,
        "load_daily_audit_input_bundle",
        lambda _: _bundle(),
    )

    try:
        runner.main(
            [
                "--symbols",
                "LT.NS",
                "--now",
                "2026-09-18T16:00:00+05:30",
                "--input-snapshot-dir",
                str(tmp_path),
                "--refresh",
            ]
        )
    except ValueError as exc:
        assert "--refresh cannot be used" in str(exc)
    else:
        raise AssertionError("snapshot mode must reject --refresh")


def test_workers_require_snapshot_mode() -> None:
    try:
        runner.main(
            [
                "--symbols",
                "LT.NS",
                "--now",
                "2026-09-18T16:00:00+05:30",
                "--workers",
                "2",
            ]
        )
    except ValueError as exc:
        assert "--workers is only supported" in str(exc)
    else:
        raise AssertionError("--workers must require snapshot mode")
