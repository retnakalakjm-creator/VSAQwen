from config import DEMAND_EVIDENCE_WEIGHTS, SUPPLY_EVIDENCE_WEIGHTS
from models import EvidenceCode
from scanner import ScannerEngine


CONFIRMATION_ONLY_BULLISH = frozenset({
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
    EvidenceCode.DEMAND_DRYING_UP,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.SPRING,
    EvidenceCode.TEST,
    EvidenceCode.SELLING_CLIMAX,
})

CONFIRMATION_ONLY_BEARISH = frozenset({
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.SUPPLY_HIGH_VOLUME,
    EvidenceCode.SUPPLY_WIDE_SPREAD,
    EvidenceCode.SUPPLY_ABSORPTION,
})


def test_directional_vsa_codes_are_classified_as_scored_or_confirmation_only() -> None:
    scored_bullish = frozenset(DEMAND_EVIDENCE_WEIGHTS)
    scored_bearish_directional = frozenset(SUPPLY_EVIDENCE_WEIGHTS) & ScannerEngine._BEARISH_VSA_CODES

    assert scored_bullish.isdisjoint(CONFIRMATION_ONLY_BULLISH)
    assert scored_bearish_directional.isdisjoint(CONFIRMATION_ONLY_BEARISH)
    assert scored_bullish | CONFIRMATION_ONLY_BULLISH == ScannerEngine._BULLISH_VSA_CODES
    assert scored_bearish_directional | CONFIRMATION_ONLY_BEARISH == ScannerEngine._BEARISH_VSA_CODES


def test_supply_weight_map_may_contain_non_directional_scored_events() -> None:
    assert EvidenceCode.SUPPLY_DRYING_UP in SUPPLY_EVIDENCE_WEIGHTS
    assert EvidenceCode.SUPPLY_DRYING_UP not in ScannerEngine._BEARISH_VSA_CODES


def test_confirmation_only_events_have_no_professional_pressure_weight() -> None:
    for code in CONFIRMATION_ONLY_BULLISH:
        assert code not in DEMAND_EVIDENCE_WEIGHTS

    for code in CONFIRMATION_ONLY_BEARISH:
        assert code not in SUPPLY_EVIDENCE_WEIGHTS


def test_all_currently_scored_directional_events_have_positive_weights() -> None:
    assert all(weight > 0.0 for weight in DEMAND_EVIDENCE_WEIGHTS.values())
    assert all(weight > 0.0 for weight in SUPPLY_EVIDENCE_WEIGHTS.values())
