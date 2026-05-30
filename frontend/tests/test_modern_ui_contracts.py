from __future__ import annotations

import json

from frontend.components.design_blocks import power_input_card, status_badge, technical_card
from frontend.gui.components import COLORS


def test_design_blocks_utilisent_palette_existante():
    badge = status_badge("validated_by_optimization")

    assert badge["color"] == [float(v) for v in COLORS["NG"]]
    json.dumps(badge)


def test_power_input_card_json_serializable_et_sans_step():
    card = power_input_card({"value": 100.0, "unit": "kW", "kw": 100.0, "status": "input", "source": "user_input"})

    json.dumps(card)
    assert card["title"].lower().startswith("puissance")
    assert card["badge"]["status"] == "input"


def test_technical_card_ne_fabrique_pas_de_valeur_metier():
    card = technical_card(title="Dossier de modelisation", status="missing_required", metrics=[{"label": "Generation STEP", "value": False}])

    assert card["metrics"][0]["value"] is False
    assert card["status"] == "missing_required"
