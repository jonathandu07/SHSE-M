from frontend.gui.frontend_contract import (
    candidate_label,
    field_color,
    format_field,
    get_missing_required_fields,
    is_cao_available,
)


def test_frontend_contract_helpers_are_passive():
    field = {"value": 0.08, "unit": "m", "status": "candidate_generated"}
    contract = {"cao": {"available": False, "missing_required_fields": ["alesage_m"]}}

    assert format_field(field) == "0.08 m"
    assert field_color(field) == "warning"
    assert candidate_label(field) == "proposee par le backend"
    assert is_cao_available(contract) is False
    assert get_missing_required_fields(contract) == ["alesage_m"]

