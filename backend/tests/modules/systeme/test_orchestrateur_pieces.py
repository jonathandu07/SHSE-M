import importlib

import pytest


def test_extraire_rapports_pieces_composants_flattens_nested_component_reports():
    orchestrateur = importlib.import_module("backend.modules.systeme.orchestrateur_pieces")

    nested = orchestrateur.extraire_rapports_pieces_composants(
        {
            "alternateur": {"pieces": {"rotor": {"piece": "rotor"}, "stator": {"piece": "stator"}}},
            "batterie_dimensionnement": {"pieces": {"pack": {"piece": "pack_batterie"}}},
            "moteur_thermique_point": {"resultats": {}},
        }
    )

    assert nested == {
        "alternateur.rotor": {"piece": "rotor"},
        "alternateur.stator": {"piece": "stator"},
        "batterie_dimensionnement.pack": {"piece": "pack_batterie"},
    }


def test_enrichir_rapport_puissance_avec_pieces_uses_selected_candidate(monkeypatch):
    orchestrateur = importlib.import_module("backend.modules.systeme.orchestrateur_pieces")

    captured = {}

    def fake_dimensionner(**kwargs):
        captured.update(kwargs)
        return {
            "pieces": {"cylindre": {"nom": "cylindre"}},
            "inventaire": {"pieces": {"cylindre": {"construit": True}}},
            "construction_pieces": {"construction": {"cylindre": {"construit": True}}},
            "rapports_pieces": {"cylindre": {"piece": "cylindre"}},
            "objets_serialises": {"pieces": {"cylindre": {"type": "Cylindre"}}},
            "synthese": {"nombre_pieces_construites": 1},
        }

    monkeypatch.setattr(orchestrateur, "dimensionner_pieces_moteur_thermique", fake_dimensionner)

    report = orchestrateur.enrichir_rapport_puissance_avec_pieces(
        {
            "candidats_valides": [
                {
                    "index": 7,
                    "entrees": {
                        "puissance_moteur_requise_w": 100000.0,
                        "rpm_moteur": 3000.0,
                        "nombre_cylindres": 4,
                        "pression_max_pa": 6.0e6,
                        "pme_pa": 9.0e5,
                    },
                    "rapport": {
                        "calculs": {
                            "moteur_thermique": {
                                "geometrie": {
                                    "alesage_m": 0.09,
                                    "course_m": 0.08,
                                    "nombre_cylindres": 4,
                                }
                            }
                        }
                    },
                }
            ],
            "selection": {
                "couple_sortie_max": {
                    "candidat": {"index": 7},
                }
            },
        }
    )

    assert captured["puissance_cible_w"] == pytest.approx(100000.0)
    assert captured["regime_tr_min"] == pytest.approx(3000.0)
    assert captured["n_cyl"] == 4
    assert captured["pression_max_pa"] == pytest.approx(6.0e6)
    assert captured["alesage_m"] == pytest.approx(0.09)
    assert captured["course_m"] == pytest.approx(0.08)
    assert report["orchestration_pieces"]["active"] is True
    assert report["orchestration_pieces"]["source"]["candidate_index"] == 7
    assert report["pieces"]["cylindre"]["nom"] == "cylindre"


def test_dimensionner_pieces_moteur_thermique_calls_backend_main_with_architecture_payload(monkeypatch):
    orchestrateur = importlib.import_module("backend.modules.systeme.orchestrateur_pieces")

    seen = {}

    class FakeMain:
        @staticmethod
        def _collect_public_data(obj):
            return {"type": type(obj).__name__, "masse_kg": getattr(obj, "masse_kg", None)}

        @staticmethod
        def construire_pieces_depuis_systeme(**kwargs):
            seen.update(kwargs)

            class Piece:
                masse_kg = 1.5

            pieces = {"piston": Piece()}
            report = {
                "construction": {"piston": {"construit": True}},
                "rapports_pieces": {"piston": {"dimensions": {"diametre_exterieur_m": 0.089}}},
                "inconnues": {"impossibles": [], "partielles": []},
                "notes_modele": [],
            }
            return pieces, report

    monkeypatch.setattr(orchestrateur.importlib, "import_module", lambda name: FakeMain())

    result = orchestrateur.dimensionner_pieces_moteur_thermique(
        puissance_cible_w=80000.0,
        regime_tr_min=3200.0,
        n_cyl=4,
        pression_max_pa=7.0e6,
        pme_pa=8.5e5,
        alesage_m=0.09,
        course_m=0.08,
        longueur_bielle_m=0.16,
    )

    definition = seen["definition_moteur_thermique"]
    rapport_systeme = seen["rapport_systeme"]

    assert definition["nombre_cylindres"] == 4
    assert definition["alesage_m"] == pytest.approx(0.09)
    assert definition["course_m"] == pytest.approx(0.08)
    assert rapport_systeme["synthese"]["moteur_thermique"]["pression_max_pa"] == pytest.approx(7.0e6)
    assert result["synthese"]["nombre_pieces_construites"] == 1
    assert result["pieces"]["piston"]["indicateurs"]["masse_kg"] == pytest.approx(1.5)
