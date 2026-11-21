import pytest

import llm
import offers
from offers import compare, load_expected, load_messages, merge_update, parse_message, verify, verify_merged

MESSAGES = load_messages()
EXPECTED = load_expected()


@pytest.fixture
def no_llm(monkeypatch):
    for k in ["LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        monkeypatch.delenv(k, raising=False)


def test_all_messages_have_expected_answers():
    assert set(MESSAGES) == set(EXPECTED)
    assert len(MESSAGES) == 5


@pytest.mark.parametrize("filename", sorted(EXPECTED))
def test_every_expected_quote_verifies(filename):
    checks = verify(EXPECTED[filename], MESSAGES[filename])
    assert checks, "every message has evidence"
    bad = [c for c in checks if not c.verified]
    assert not bad, bad


def test_changed_number_in_quote_fails():
    offer = EXPECTED["nordlink_groupage_email.txt"].model_copy(deep=True)
    offer.evidence["price_gbp"] = "transport is GBP 940 all-in"
    check = {c.field: c for c in verify(offer, MESSAGES[offer.source_file])}["price_gbp"]
    assert not check.verified


def test_changed_time_in_quote_fails():
    offer = EXPECTED["nordlink_groupage_email.txt"].model_copy(deep=True)
    offer.evidence["departure"] = "Trunk departs Tue 22:00"
    check = {c.field: c for c in verify(offer, MESSAGES[offer.source_file])}["departure"]
    assert not check.verified


def test_value_must_appear_in_its_quote():
    offer = EXPECTED["nordlink_groupage_email.txt"].model_copy(deep=True)
    offer.hold_fee_gbp = 6  # quote is real, but it says GBP 60
    check = {c.field: c for c in verify(offer, MESSAGES[offer.source_file])}["hold_fee_gbp"]
    assert not check.verified


def test_wrong_datetime_value_fails_even_with_real_quote():
    offer = EXPECTED["nordlink_groupage_email.txt"].model_copy(deep=True)
    offer.arrival = offer.arrival.replace(day=27)  # Fri, but the quote says Thu
    check = {c.field: c for c in verify(offer, MESSAGES[offer.source_file])}["arrival"]
    assert not check.verified


def test_eur_parts_are_summed():
    check = {c.field: c for c in verify(EXPECTED["milano_rental_email.txt"],
                                        MESSAGES["milano_rental_email.txt"])}["price_eur"]
    assert check.verified  # "Hire EUR 460 + EUR 60 delivery" -> 520


def test_quote_normalisation_handles_case_and_dashes():
    offer = EXPECTED["nordlink_groupage_email.txt"].model_copy(deep=True)
    offer.evidence["cancellation_terms"] = "NON-REFUNDABLE. We hold it until Tue 18:00 – confirm by then"
    check = {c.field: c for c in verify(offer, MESSAGES[offer.source_file])}["cancellation_terms"]
    assert check.verified


def test_invented_quote_fails():
    offer = EXPECTED["swiftvan_whatsapp.txt"].model_copy(deep=True)
    offer.evidence["cancellation_terms"] = "full refund at any time"
    check = {c.field: c for c in verify(offer, MESSAGES[offer.source_file])}["cancellation_terms"]
    assert not check.verified


def test_merge_update_sets_fee_and_keeps_everything_else():
    base = EXPECTED["nordlink_groupage_email.txt"]
    merged = merge_update(base, EXPECTED["nordlink_update.txt"])
    assert merged.hold_fee_gbp == 120
    assert merged.evidence["hold_fee_gbp"] == "holding fee is now £120"
    assert merged.carrier == "Nordlink Groupage Ltd"  # identity stays: still the approved merchant
    for f in ["price_gbp", "arrival", "departure", "confirm_by", "collection_cutoff", "crew", "service"]:
        assert getattr(merged, f) == getattr(base, f)
        if f in base.evidence:
            assert merged.evidence[f] == base.evidence[f]
    assert "The new £120 holding fee is only held for 2 hours" in merged.limitations
    assert all(x in merged.limitations for x in base.limitations)
    assert base.hold_fee_gbp == 60  # base untouched


def test_merged_quotes_check_against_the_right_message():
    base, upd = EXPECTED["nordlink_groupage_email.txt"], EXPECTED["nordlink_update.txt"]
    checks = verify_merged(base, upd, MESSAGES[base.source_file], MESSAGES[upd.source_file])
    by = {c.field: c for c in checks}
    assert by["hold_fee_gbp"].verified and by["hold_fee_gbp"].quote == "holding fee is now £120"
    assert all(c.verified for c in checks)


def test_parse_message_falls_back_to_replayed_without_key(no_llm):
    assert not llm.available()
    for fn, text in MESSAGES.items():
        offer, src = parse_message(fn, text, use_llm=True)
        assert src == "replayed"
        assert offer == EXPECTED[fn]


def test_parse_message_falls_back_when_llm_fails(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: None)
    offer, src = parse_message("aerodash_quote.txt", MESSAGES["aerodash_quote.txt"], use_llm=True)
    assert src == "replayed" and offer.max_weight_kg_per_piece == 32


def test_parse_message_falls_back_on_invalid_llm_output(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: {"mode": "teleport", "arrival": "soon"})
    _, src = parse_message("aerodash_quote.txt", MESSAGES["aerodash_quote.txt"], use_llm=True)
    assert src == "replayed"


def test_parse_message_uses_valid_llm_output(monkeypatch, tmp_path):
    monkeypatch.setattr(offers, "LLM_OUT", tmp_path / "llm_offers.json")
    monkeypatch.setattr(llm, "available", lambda: True)
    fake = {"carrier": "AeroDash Couriers", "mode": "air_courier", "price_gbp": 2900,
            "max_weight_kg_per_piece": "32", "flags": None, "evidence": {"max_weight_kg_per_piece": "32kg per piece"}}
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: fake)
    offer, src = parse_message("aerodash_quote.txt", MESSAGES["aerodash_quote.txt"], use_llm=True)
    assert src == "llm" and offer.max_weight_kg_per_piece == 32 and offer.flags == []
    assert (tmp_path / "llm_offers.json").exists()


def test_compare_counts_fields():
    e = EXPECTED["swiftvan_whatsapp.txt"]
    m, t, misses = compare(e, e)
    assert m == t and not misses
    wrong = e.model_copy(update={"price_gbp": 1500, "flags": [], "hold_fee_gbp": 50})
    m2, t2, misses2 = compare(wrong, e)
    assert t2 == t + 1  # a guessed hold fee counts as a field
    assert m2 == m - 2  # price wrong, injection not flagged
    assert any(x.startswith("price_gbp") for x in misses2)


def test_llm_json_parsing():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('Here you go: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    assert llm.parse_json("nope") is None
    assert llm.parse_json(None) is None


def test_llm_complete_returns_none_without_provider(no_llm):
    assert llm.complete("s", "u") is None
    assert llm.complete_json("s", "u") is None
