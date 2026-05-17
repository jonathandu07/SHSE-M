from frontend.gui.frontend_contract import (
    candidate_label,
    contract_fields_by_status,
    field_color,
    field_badge_label,
    format_field,
    get_field,
    get_field_status,
    get_field_value,
    get_missing_required_fields,
    is_field_blocking,
    is_field_editable,
    is_cao_available,
    is_real_solidworks_available,
    is_step_export_available,
)


def test_frontend_contract_helpers_are_passive():
    field = {"value": 0.08, "unit": "m", "status": "candidate_generated"}
    contract = {"cao": {"available": False, "missing_required_fields": ["alesage_m"]}}

    assert format_field(field) == "0.08 m"
    assert field_color(field) == "warning"
    assert candidate_label(field) == "proposee par le backend"
    assert is_cao_available(contract) is False
    assert get_missing_required_fields(contract) == ["alesage_m"]


def test_frontend_contract_helpers_lisent_champs_sans_fabriquer():
    contract = {
        "fields": [
            {"path": "synthese.systeme.P_bus_dc_design_w", "value": 120000.0, "unit": "W", "status": "computed", "editable": False},
            {"path": "synthese.moteur_thermique.rpm_nominal", "value": None, "unit": "rpm", "status": "missing_required", "blocking": True},
            {"path": "candidat.ratio", "value": 2.0, "status": "candidate_from_cdc", "editable": True},
        ]
    }

    assert get_field_value(contract, "synthese.systeme.P_bus_dc_design_w") == 120000.0
    assert get_field_value(contract, "absent") is None
    assert get_field_status(contract, "synthese.moteur_thermique.rpm_nominal") == "missing_required"
    assert is_field_blocking(get_field(contract, "synthese.moteur_thermique.rpm_nominal")) is True
    assert is_field_editable(get_field(contract, "synthese.systeme.P_bus_dc_design_w")) is False
    assert is_field_editable(get_field(contract, "candidat.ratio")) is True
    assert field_badge_label(get_field(contract, "candidat.ratio")) == "candidat backend"
    assert len(contract_fields_by_status(contract, "candidate_from_cdc")) == 1


def test_cao_non_ready_bloque_step_et_solidworks():
    contract = {
        "cao": {
            "available": False,
            "solidworks_ready": False,
            "step_export": False,
            "sketches_available": True,
        }
    }

    assert is_cao_available(contract) is False
    assert is_real_solidworks_available(contract) is False
    assert is_step_export_available(contract) is False
