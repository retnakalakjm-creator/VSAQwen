"""Reproducible current-constituent NSE index universe preparation for WF7C2.

This module is research-only. It converts an official NSE Indices constituent
CSV into the yfinance-style NSE symbols already consumed by ProVSA, while
recording the exact source bytes by SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Sequence


NIFTY_500_CONSTITUENT_URL = (
    "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
)
DEFAULT_OUTPUT_DIR = Path("reports/weekly-foundation/wf7c2-universe")


@dataclass(frozen=True, slots=True)
class NseIndexUniverseManifest:
    index_name: str
    source_url: str
    source_sha256: str
    retrieved_at_utc: str
    source_symbol_count: int
    provider_symbol_count: int
    source_symbols: tuple[str, ...]
    provider_symbols: tuple[str, ...]
    provider_suffix: str
    survivor_bias_warning: str
    is_actionable: bool = False


@dataclass(frozen=True, slots=True)
class NseIndexUniversePaths:
    manifest_json: Path
    wf7c2_symbols_txt: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def _decode_csv_bytes(csv_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return csv_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("constituent CSV must be UTF-8 encoded")


def parse_nse_constituent_symbols(csv_bytes: bytes) -> tuple[str, ...]:
    """Return normalized exchange symbols from an official constituent CSV."""

    text = _decode_csv_bytes(csv_bytes)
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None or "Symbol" not in reader.fieldnames:
        raise ValueError("constituent CSV must contain a 'Symbol' column")

    symbols: list[str] = []
    seen: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        symbol = str(row.get("Symbol") or "").strip().upper()
        if not symbol:
            raise ValueError(f"blank Symbol at CSV row {row_number}")
        if symbol in seen:
            raise ValueError(f"duplicate Symbol in constituent CSV: {symbol}")
        seen.add(symbol)
        symbols.append(symbol)

    if not symbols:
        raise ValueError("constituent CSV contains no symbols")
    return tuple(symbols)


def to_yfinance_nse_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized if normalized.endswith(".NS") else f"{normalized}.NS"


def build_nse_index_universe_manifest(
    csv_bytes: bytes,
    *,
    index_name: str = "NIFTY 500",
    source_url: str = NIFTY_500_CONSTITUENT_URL,
    retrieved_at_utc: str | None = None,
) -> NseIndexUniverseManifest:
    source_symbols = parse_nse_constituent_symbols(csv_bytes)
    provider_symbols = tuple(to_yfinance_nse_symbol(item) for item in source_symbols)
    if len(set(provider_symbols)) != len(provider_symbols):
        raise ValueError("provider symbol normalization produced duplicates")

    retrieved_at = (
        datetime.now(timezone.utc).isoformat()
        if retrieved_at_utc is None
        else str(retrieved_at_utc).strip()
    )
    if not retrieved_at:
        raise ValueError("retrieved_at_utc cannot be blank")

    return NseIndexUniverseManifest(
        index_name=str(index_name).strip() or "NIFTY 500",
        source_url=str(source_url).strip(),
        source_sha256=hashlib.sha256(csv_bytes).hexdigest(),
        retrieved_at_utc=retrieved_at,
        source_symbol_count=len(source_symbols),
        provider_symbol_count=len(provider_symbols),
        source_symbols=source_symbols,
        provider_symbols=provider_symbols,
        provider_suffix=".NS",
        survivor_bias_warning=(
            "This is a current-constituent universe, not a point-in-time historical "
            "membership series. Historical WF7C2 results therefore retain survivor-bias "
            "and index-reconstitution limitations."
        ),
        is_actionable=False,
    )


def write_nse_index_universe_bundle(
    manifest: NseIndexUniverseManifest,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> NseIndexUniversePaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NseIndexUniversePaths(
        manifest_json=root / "wf7c2_nse_universe_manifest.json",
        wf7c2_symbols_txt=root / "wf7c2_symbols.txt",
    )
    payload = asdict(manifest)
    payload["source_symbols"] = list(manifest.source_symbols)
    payload["provider_symbols"] = list(manifest.provider_symbols)
    paths.manifest_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    paths.wf7c2_symbols_txt.write_text(
        ",".join(manifest.provider_symbols),
        encoding="utf-8",
    )
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert an official NSE Indices constituent CSV into a reproducible "
            "WF7C2 yfinance symbol universe. Research-only; no production changes."
        )
    )
    parser.add_argument("--csv", required=True, help="Path to official constituent CSV.")
    parser.add_argument("--index-name", default="NIFTY 500")
    parser.add_argument("--source-url", default=NIFTY_500_CONSTITUENT_URL)
    parser.add_argument("--retrieved-at-utc", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    manifest = build_nse_index_universe_manifest(
        csv_path.read_bytes(),
        index_name=args.index_name,
        source_url=args.source_url,
        retrieved_at_utc=args.retrieved_at_utc,
    )
    paths = write_nse_index_universe_bundle(manifest, args.output_dir)
    print(
        json.dumps(
            {
                "index_name": manifest.index_name,
                "source_symbol_count": manifest.source_symbol_count,
                "provider_symbol_count": manifest.provider_symbol_count,
                "source_sha256": manifest.source_sha256,
                "is_actionable": False,
                "output_paths": paths.as_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "NIFTY_500_CONSTITUENT_URL",
    "NseIndexUniverseManifest",
    "NseIndexUniversePaths",
    "build_nse_index_universe_manifest",
    "parse_nse_constituent_symbols",
    "to_yfinance_nse_symbol",
    "write_nse_index_universe_bundle",
]
