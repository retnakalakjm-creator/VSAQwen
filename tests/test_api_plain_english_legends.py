from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_plain_english_legend_registry_endpoint() -> None:
    response = client.get("/api/vsa/legends")

    assert response.status_code == 200
    payload = response.json()

    assert payload["production_safe"] is True
    assert payload["chart_reading_cycle"]
    assert payload["chart_reading_cycle"][0]["stage"] == "background_mood"
    assert payload["field_family_aliases"]["_outcome_label"] == "outcome_label"
    assert payload["field_family_aliases"]["_review_reason"] == "review_reason"
    assert payload["field_family_aliases"]["_classify_cluster"] == "cluster"
    assert payload["field_family_aliases"]["_classify_transition"] == "transition"
    assert payload["field_family_aliases"]["_case_type_for_transition"] == "case_type"

    legends_by_code_family = {
        (legend["code"], legend["family"]): legend
        for legend in payload["legends"]
    }

    active = legends_by_code_family[("active", "lifecycle")]
    assert active["frontend_label"] == "Active"
    assert "fresh same-side evidence" in active["plain_english"]
    assert active["chart_reading_order"] == 1

    absorption = legends_by_code_family[(
        "absorption_background_review",
        "review_marker",
    )]
    assert absorption["frontend_label"] == "Absorption Background Review"
    assert "Selling pressure may be getting absorbed" in absorption["plain_english"]
    assert absorption["audit_only"] is True

    transition = legends_by_code_family[(
        "chart_confirm_supersession_rule_candidate",
        "case_type",
    )]
    assert "casebook task" in transition["plain_english"]
    assert "supersede" in transition["plain_english"]
