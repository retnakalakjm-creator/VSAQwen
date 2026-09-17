from __future__ import annotations

import hashlib
import json

import pytest

from audit.nse_index_universe import (
    NIFTY_500_CONSTITUENT_URL,
    build_nse_index_universe_manifest,
    parse_nse_constituent_symbols,
    write_nse_index_universe_bundle,
)


def _csv(*rows: str) -> bytes:
    body = [
        "Company Name,Industry,Symbol,Series,ISIN Code",
        *rows,
    ]
    return ("\n".join(body) + "\n").encode("utf-8")


def test_parse_constituent_symbols_preserves_source_order_and_normalizes_case() -> None:
    raw = _csv(
        "Reliance Industries Ltd.,Oil Gas & Consumable Fuels, reliance ,EQ,INE002A01018",
        "M&M Ltd.,Automobile and Auto Components,M&M,EQ,INE101A01026",
    )

    assert parse_nse_constituent_symbols(raw) == ("RELIANCE", "M&M")


def test_manifest_maps_exchange_symbols_to_existing_yfinance_nse_convention() -> None:
    raw = _csv(
        "Reliance Industries Ltd.,Oil Gas & Consumable Fuels,RELIANCE,EQ,INE002A01018",
        "Bajaj Auto Ltd.,Automobile and Auto Components,BAJAJ-AUTO,EQ,INE917I01010",
    )

    manifest = build_nse_index_universe_manifest(
        raw,
        retrieved_at_utc="2026-09-17T00:00:00+00:00",
    )

    assert manifest.source_symbols == ("RELIANCE", "BAJAJ-AUTO")
    assert manifest.provider_symbols == ("RELIANCE.NS", "BAJAJ-AUTO.NS")
    assert manifest.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert manifest.source_url == NIFTY_500_CONSTITUENT_URL
    assert manifest.source_symbol_count == 2
    assert manifest.provider_symbol_count == 2
    assert manifest.is_actionable is False
    assert "survivor-bias" in manifest.survivor_bias_warning


def test_parse_rejects_missing_symbol_column() -> None:
    raw = b"Company Name,Industry\nExample Ltd.,Example\n"

    with pytest.raises(ValueError, match="Symbol"):
        parse_nse_constituent_symbols(raw)


def test_parse_rejects_duplicate_symbols_instead_of_silently_deduplicating() -> None:
    raw = _csv(
        "Example One Ltd.,Example,ONE,EQ,INE000000001",
        "Example Two Ltd.,Example,ONE,EQ,INE000000002",
    )

    with pytest.raises(ValueError, match="duplicate Symbol"):
        parse_nse_constituent_symbols(raw)


def test_bundle_writes_manifest_and_wf7c2_comma_separated_symbol_input(tmp_path) -> None:
    raw = _csv(
        "Reliance Industries Ltd.,Oil Gas & Consumable Fuels,RELIANCE,EQ,INE002A01018",
        "Tata Consultancy Services Ltd.,Information Technology,TCS,EQ,INE467B01029",
    )
    manifest = build_nse_index_universe_manifest(
        raw,
        retrieved_at_utc="2026-09-17T00:00:00+00:00",
    )

    paths = write_nse_index_universe_bundle(manifest, tmp_path)

    payload = json.loads(paths.manifest_json.read_text(encoding="utf-8"))
    assert payload["provider_symbols"] == ["RELIANCE.NS", "TCS.NS"]
    assert payload["is_actionable"] is False
    assert paths.wf7c2_symbols_txt.read_text(encoding="utf-8") == "RELIANCE.NS,TCS.NS"
