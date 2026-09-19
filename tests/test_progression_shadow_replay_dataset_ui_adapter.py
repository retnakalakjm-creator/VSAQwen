from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "frontend/app/progression-shadow-replay-dataset-adapter.ts"
ENTRYPOINT = (
    ROOT / "frontend/app/progression-shadow-replay-preview-entrypoint.tsx"
)
GATE = ROOT / "frontend/app/progression-shadow-replay-preview-gate.ts"
BOUNDARY = (
    ROOT
    / "frontend/app/replay/progression-semantic/preview-route-boundary.ts"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_adapter_requires_exact_k26_contract_and_ready_status() -> None:
    text = _text(ADAPTER)
    for snippet in (
        "progression-shadow-semantic-replay-dataset-v1",
        "shadow_replay_dataset_ready",
        "source_event_count",
        "sequence_count",
        "total_frame_count",
        "replay_sequences",
        "must contain exactly one event frame",
        "event week does not match event frame",
        "resolved event index does not match event frame",
        "non-event frame contains semantic marker data",
    ):
        assert snippet in text


def test_adapter_fails_closed_on_every_production_safety_flag() -> None:
    text = _text(ADAPTER)
    for snippet in (
        'booleanFalse(raw.reversal_confirmed, "reversal_confirmed")',
        "raw.persistent_direction_claim",
        'booleanFalse(raw.affects_qualification, "affects_qualification")',
        'booleanFalse(raw.affects_scoring, "affects_scoring")',
        'booleanFalse(raw.is_actionable, "is_actionable")',
    ):
        assert snippet in text


def test_ui_reads_explicit_local_json_without_network_or_storage() -> None:
    text = _text(ENTRYPOINT)
    assert 'type="file"' in text
    assert 'accept=".json,application/json"' in text
    assert "await file.text()" in text
    assert "JSON.parse" in text
    assert "adaptProgressionShadowReplayDataset" in text

    combined = "\n".join(
        _text(path)
        for path in (ADAPTER, ENTRYPOINT, GATE, BOUNDARY)
    )
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "/api/",
    ):
        assert forbidden not in combined


def test_imported_replay_shows_source_and_resolved_event_identity() -> None:
    text = _text(ENTRYPOINT)
    assert "Source event index" in text
    assert "Resolved local weekly index" in text
    assert "Event week identity" in text
    assert 'sequence.source === "k26-offline-dataset"' in text


def test_route_remains_dev_only_and_local_artifact_only() -> None:
    gate = _text(GATE)
    boundary = _text(BOUNDARY)
    assert "offlineLocalArtifactOnly: true" in gate
    assert "networkUploadAllowed: false" in gate
    assert "usesOfflineLocalArtifactOnly: true" in boundary
    assert "networkUploadAllowed: false" in boundary
    assert 'environment !== "production"' in boundary
