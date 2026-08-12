import config
from models import EvidenceCode


def test_no_supply_is_not_standalone_demand_pressure() -> None:
    assert EvidenceCode.NO_SUPPLY not in config.DEMAND_EVIDENCE_WEIGHTS


def test_no_supply_remains_available_to_the_evidence_layer() -> None:
    assert EvidenceCode.NO_SUPPLY in EvidenceCode
