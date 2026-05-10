import pytest
from unittest.mock import MagicMock

from app.dialing_worker.dynamic_variables import DynamicVariables


def _make_lead(
    phone_number="+919876543210",
    first_name="Ravi",
    last_name="Sharma",
    company="ABC Corp",
    custom_vars=None,
):
    lead = MagicMock()
    lead.phone_number = phone_number
    lead.first_name = first_name
    lead.last_name = last_name
    lead.company = company
    lead.custom_vars = custom_vars
    return lead


def _make_campaign(name="Test Campaign"):
    campaign = MagicMock()
    campaign.name = name
    return campaign


def test_from_lead_maps_standard_fields():
    lead = _make_lead()
    campaign = _make_campaign("My Campaign")
    dv = DynamicVariables.from_lead(lead, campaign)
    assert dv.first_name == "Ravi"
    assert dv.last_name == "Sharma"
    assert dv.company == "ABC Corp"
    assert dv.phone_number == "+919876543210"
    assert dv.campaign_name == "My Campaign"


def test_from_lead_none_fields_default_to_empty_string():
    lead = _make_lead(first_name=None, last_name=None, company=None)
    campaign = _make_campaign()
    dv = DynamicVariables.from_lead(lead, campaign)
    assert dv.first_name == ""
    assert dv.last_name == ""
    assert dv.company == ""


def test_from_lead_custom_vars_pass_through():
    lead = _make_lead(custom_vars={"product": "Pro Plan", "tier": "gold"})
    campaign = _make_campaign()
    dv = DynamicVariables.from_lead(lead, campaign)
    assert dv.model_dump()["product"] == "Pro Plan"
    assert dv.model_dump()["tier"] == "gold"


def test_from_lead_no_custom_vars():
    lead = _make_lead(custom_vars=None)
    campaign = _make_campaign()
    dv = DynamicVariables.from_lead(lead, campaign)
    d = dv.model_dump()
    assert "first_name" in d
    assert "phone_number" in d


def test_to_retell_dict_all_strings():
    lead = _make_lead(custom_vars={"score": 42, "active": True})
    campaign = _make_campaign()
    result = DynamicVariables.from_lead(lead, campaign).to_retell_dict()
    for v in result.values():
        assert isinstance(v, str), f"Expected str, got {type(v)} for value {v!r}"


def test_to_retell_dict_coerces_int_custom_var():
    lead = _make_lead(custom_vars={"score": 99})
    campaign = _make_campaign()
    result = DynamicVariables.from_lead(lead, campaign).to_retell_dict()
    assert result["score"] == "99"


def test_to_retell_dict_coerces_bool_custom_var():
    lead = _make_lead(custom_vars={"verified": True})
    campaign = _make_campaign()
    result = DynamicVariables.from_lead(lead, campaign).to_retell_dict()
    assert result["verified"] == "True"
