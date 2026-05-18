from __future__ import annotations

import pytest

from frontend.ensemble.power_input import build_design_input_payload, valider_puissance_sortie


def test_saisie_puissance_kw_acceptee():
    payload = build_design_input_payload(100, "kW")

    assert payload["inputs"]["puissance_sortie"] == 100.0
    assert payload["inputs"]["unite"] == "kW"
    assert payload["backend_config"]["puissance_sortie_moteur_electrique_kw"] == 100.0
    assert payload["backend_config"]["frontend_inputs"]["status"] == "input"


def test_saisie_puissance_ch_acceptee_et_tracee():
    payload = build_design_input_payload(100, "ch")

    assert payload["inputs"]["unite"] == "ch"
    assert payload["backend_config"]["puissance_sortie_moteur_electrique_kw"] > 0
    assert "Conversion d'unite" in payload["inputs"]["trace"]["note"]


def test_saisie_puissance_negative_refusee():
    with pytest.raises(ValueError):
        valider_puissance_sortie(-1, "kW")


def test_unite_inconnue_refusee():
    with pytest.raises(ValueError):
        build_design_input_payload(100, "BTU")
