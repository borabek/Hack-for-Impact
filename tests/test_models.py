import json
from pathlib import Path

from models import Offer, Scenario

DATA = Path(__file__).resolve().parent.parent / "data"


def test_scenario_loads():
    scn = Scenario.model_validate(json.loads((DATA / "scenario.json").read_text(encoding="utf-8")))
    assert scn.shipment.weight_kg == 45
    assert scn.policy.per_call_limit_gbp == 100
    assert scn.policy.owner == "Sarah Clarke"
    assert scn.shipment.deadline.utcoffset().total_seconds() == 3600


def test_every_expected_offer_loads():
    raw = json.loads((DATA / "expected_offers.json").read_text(encoding="utf-8"))
    assert len(raw) == 5
    for filename, fields in raw.items():
        offer = Offer(offer_id=filename.split("_")[0], source_file=filename, **fields)
        assert offer.source_file == filename
        for dt in (offer.departure, offer.arrival, offer.confirm_by, offer.latest_booking):
            assert dt is None or dt.tzinfo is not None
