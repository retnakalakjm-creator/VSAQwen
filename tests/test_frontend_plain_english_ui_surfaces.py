from pathlib import Path

DECISION_CONTEXT_PANEL_PATH = Path("frontend/app/decision-context-panel.tsx")
LEGENDS_PAGE_PATH = Path("frontend/app/legends/page.tsx")
ROOT_LAYOUT_PATH = Path("frontend/app/layout.tsx")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def positions_in_order(text: str, snippets: list[str]) -> list[int]:
    positions = [text.index(snippet) for snippet in snippets]
    assert positions == sorted(positions)
    return positions


def test_decision_context_panel_fetches_and_builds_plain_english_legend_lookup() -> None:
    panel = source(DECISION_CONTEXT_PANEL_PATH)

    assert "buildPlainEnglishLegendLookup" in panel
    assert "plainEnglishLegendText" in panel
    assert "type LegendRegistryPayload" in panel
    assert "const [legendRegistry, setLegendRegistry] = useState<LegendRegistryPayload | null>(null);" in panel
    assert "const [legendRegistryError, setLegendRegistryError] = useState(\"\");" in panel
    assert "fetchJson<LegendRegistryPayload>(" in panel
    assert "`${API}/api/vsa/legends`" in panel
    assert "Plain-English legend registry failed" in panel
    assert "() => buildPlainEnglishLegendLookup(legendRegistry?.legends ?? [])" in panel


def test_decision_context_story_events_keep_plain_english_meaning_and_registry_error_visible() -> None:
    panel = source(DECISION_CONTEXT_PANEL_PATH)
    event_helper_start = panel.index("function eventPlainEnglish(event: DecisionContextEvent)")
    component_return_start = panel.index("\n\n  return (\n    <section", event_helper_start)
    event_helper = panel[event_helper_start:component_return_start]
    event_cards = panel[component_return_start:]

    positions_in_order(
        event_helper,
        [
            'plainEnglishLegendText(legendLookup, { code: event.code, family: "event_label" })',
            "plainEnglishLegendText(legendLookup, { code: event.code })",
            "event.description",
            "event.observation",
        ],
    )
    assert "const legendText = eventPlainEnglish(event);" in event_cards
    assert "<small>Plain-English meaning: {legendText}</small>" in event_cards
    assert "Plain-English legend registry unavailable: {legendRegistryError}" in event_cards


def test_decision_context_lifecycle_evidence_lists_keep_code_explanations() -> None:
    panel = source(DECISION_CONTEXT_PANEL_PATH)
    code_helper_start = panel.index("function codePlainEnglish(code: string)")
    lifecycle_list_start = panel.index("function lifecycleEvidenceCodeList(title: string, codes: string[])")
    event_helper_start = panel.index("function eventPlainEnglish(event: DecisionContextEvent)")
    code_helper = panel[code_helper_start:lifecycle_list_start]
    lifecycle_list = panel[lifecycle_list_start:event_helper_start]

    positions_in_order(
        code_helper,
        [
            'plainEnglishLegendText(legendLookup, { code, family: "evidence_code" })',
            "plainEnglishLegendText(legendLookup, { code })",
            "No plain-English explanation has been registered for this code yet.",
        ],
    )
    positions_in_order(
        lifecycle_list,
        [
            "<strong>{pretty(code)}</strong>",
            "<small>{codePlainEnglish(code)}</small>",
        ],
    )

    assert 'lifecycleEvidenceCodeList("Opposing evidence", lifecycle.opposing_event_codes)' in panel
    assert 'lifecycleEvidenceCodeList("Supporting evidence", lifecycle.supporting_event_codes)' in panel
    assert '"Audit-only candidates ignored for this production-safe label"' in panel
    assert "lifecycle.ignored_audit_only_codes" in panel


def test_legends_page_keeps_registry_fetch_cycle_alias_and_family_rendering() -> None:
    legends_page = source(LEGENDS_PAGE_PATH)

    assert "async function fetchLegendRegistry(): Promise<LegendRegistryPayload>" in legends_page
    assert "fetch(`${API}/api/vsa/legends`)" in legends_page
    assert "groupPlainEnglishLegendsByFamily" in legends_page
    assert "buildPlainEnglishLegendLookup" in legends_page
    assert "registry.chart_reading_cycle.map" in legends_page
    assert "IMPORTANT_FIELDS.map" in legends_page
    assert "registry.field_family_aliases[field]" in legends_page
    assert "families.map((family) =>" in legends_page
    assert "legendsByFamily[family].map((legend) =>" in legends_page


def test_legends_page_keeps_absorption_background_review_lookup_visible() -> None:
    legends_page = source(LEGENDS_PAGE_PATH)

    positions_in_order(
        legends_page,
        [
            "const absorptionPlainEnglish = plainEnglishLegendText(legendLookup, {",
            'family: "review_marker"',
            'code: "absorption_background_review"',
            "Shared lookup check:",
            "<strong>absorption_background_review</strong> means {absorptionPlainEnglish}",
        ],
    )


def test_root_layout_keeps_plain_english_legends_navigation_link() -> None:
    layout = source(ROOT_LAYOUT_PATH)

    assert 'href="/legends"' in layout
    assert "Plain-English Legends" in layout
