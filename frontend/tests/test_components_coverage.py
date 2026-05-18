from __future__ import annotations

import json

from frontend.ensemble.visualisation_orchestrator import analyser_couverture_backend_frontend, lister_visualisations_disponibles
from frontend.ensemble.visualisation_orchestrator import construire_visualisations_composants


def test_couverture_compare_backend_frontend_et_signale_legacy():
    coverage = analyser_couverture_backend_frontend({"rapports_pieces": {"arbre_piston": {"piece": "arbre_piston"}}})

    json.dumps(coverage, ensure_ascii=False)
    rows = {row["piece"]: row for row in coverage["pieces"]}
    assert "arbre_piston" in rows
    assert rows["arbre_piston"]["frontend_present"] is True
    assert rows["arbre_piston"]["supports_render_contract"] is True
    assert coverage["summary"]["backend_pieces"] >= 1
    assert "legacy_hidden_demo" in coverage["summary"]


def test_inventory_ne_declare_pas_step_et_expose_statuts_backend_frontend():
    inventory = lister_visualisations_disponibles({"rapports_pieces": {"piston": {"piece": "piston"}}})

    row = next(item for item in inventory["pieces"] if item["piece"] == "piston")
    assert row["backend_report"] is True
    assert row["step_export"] is False
    assert row["solidworks_ready"] is False
    assert "legacy_hidden_demo" in row


def test_orchestrateur_composants_utilise_contrats_passifs():
    payload = construire_visualisations_composants(
        {
            "sous_systemes": {
                "alternateur": {"dimensionnement": {"diametre_m": 0.2}},
                "batterie": {"pack": {"longueur_m": 0.8}},
            }
        }
    )

    alternateur = payload["components"]["alternateur"]
    batterie = payload["components"]["batterie"]
    assert alternateur["kind"] == "component"
    assert batterie["kind"] == "component"
    assert alternateur["step_export"] is False
    assert batterie["solidworks_ready"] is False
    assert alternateur["solidworks_data"]["dimensions_to_copy"][0]["source"] == "backend"
