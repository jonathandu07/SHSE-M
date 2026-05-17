from backend.modules.systeme.frontend_contract import build_diagnostic_contract
from frontend.gui.frontend_contract import diagnostic_patch_is_automatic, diagnostic_root_cause_cards


def _diagnostic():
    return {
        "meta": {"type_detecte": "rapport_sthome"},
        "resume": {
            "statut": "bloque",
            "score_diagnostic_100": 42,
            "nb_symptomes": 3267,
            "cao_disponible": False,
            "solidworks_ready": False,
        },
        "causes_racines": [
            {
                "id": "boite_crabots_rapports",
                "titre": "Boite absente",
                "sous_systeme": "boite_crabots",
                "champ": "rapport_alternateur_moteur",
                "raison": "Rapports absents",
                "priorite": 92,
                "impact": {"nb_symptomes_expliques": 320, "bloque_cao": False, "bloque_optimisation": True},
                "actions": ["Fournir rapports candidats."],
                "patchs_proposes": [
                    {
                        "type": "missing_user_input",
                        "path": "composants.boite_crabots.rapports",
                        "apply_automatically": False,
                    }
                ],
            }
        ],
        "symptomes": [{"champ": "couple_alternateur_nm", "raison": "absent"}],
        "doublons": [],
    }


def test_contrat_diagnostic_contient_cartes_causes_racines():
    contract = build_diagnostic_contract(_diagnostic())
    cards = diagnostic_root_cause_cards(contract)
    assert len(cards) == 1
    assert contract["fields"][0]["blocking"] is True
    assert contract["cao"]["available"] is False


def test_patch_diagnostic_non_automatique():
    contract = build_diagnostic_contract(_diagnostic())
    patch = contract["fields"][0]["patch"]
    assert diagnostic_patch_is_automatic(patch) is False


def test_symptomes_sont_dans_unknowns_separes():
    contract = build_diagnostic_contract(_diagnostic())
    assert contract["unknowns"]["root_causes"][0]["id"] == "boite_crabots_rapports"
    assert contract["unknowns"]["symptoms"][0]["champ"] == "couple_alternateur_nm"
