from pathlib import Path

CLIENT_PATH = Path("frontend/app/plain-english-legend-client.ts")


def client_source() -> str:
    return CLIENT_PATH.read_text(encoding="utf-8")


def test_plain_english_legend_lookup_builds_family_code_keys() -> None:
    source = client_source()

    assert "new Map(legends.map((legend) => [`${legend.family}:${legend.code}`, legend]))" in source


def test_plain_english_legend_lookup_trims_code_and_family() -> None:
    source = client_source()

    assert "const code = key.code?.trim();" in source
    assert "if (!code) return null;" in source
    assert "const family = key.family?.trim();" in source
    assert "if (family) return lookup.get(`${family}:${code}`) ?? null;" in source


def test_plain_english_legend_generic_lookup_order_prioritizes_evidence_codes() -> None:
    source = client_source()

    fallback_order = [
        "`evidence_code:${code}`",
        "`event_label:${code}`",
        "`review_marker:${code}`",
        "`lifecycle:${code}`",
        "`outcome_label:${code}`",
        "`cluster:${code}`",
        "`transition:${code}`",
        "`case_type:${code}`",
        "`review_reason:${code}`",
    ]

    positions = [source.index(item) for item in fallback_order]
    assert positions == sorted(positions)
