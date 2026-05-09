from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_compute_and_save_from_main_respects_architecture_layers(tmp_path, monkeypatch):
    from backend.modules.systeme.database import SecureDatabase

    db = SecureDatabase(
        db_path=tmp_path / "technical.db",
        key_path=tmp_path / "secret.key",
    )

    captured = {}

    def fake_dimensionner_systeme_shsem(**kwargs):
        captured.update(kwargs)
        return {
            "resume_gui": {"Architecture": "L4", "N_cyl": 4},
            "inventaire": {"pieces": {"piston": {"construit": True}}},
            "rapports_pieces": {"piston": {"piece": "piston"}},
            "construction_pieces": {"construction": {"piston": {"construit": True}}},
            "objets_serialises": {"pieces": {"piston": {"type": "Piston"}}},
            "synthese": {"ok": True},
        }

    fake_main = SimpleNamespace(dimensionner_systeme_shsem=fake_dimensionner_systeme_shsem)
    monkeypatch.setattr(db, "_import_main_module", lambda: fake_main)

    result = db.compute_and_save_from_main(
        report_name="archi_test",
        function_name="dimensionner_systeme_shsem",
        puissance_traction_kw=55.0,
        charger_batterie=False,
    )

    assert captured == {"puissance_traction_kw": 55.0, "charger_batterie": False}
    assert result["report_name"] == "archi_test"
    assert result["records_saved"] >= 1
    assert result["resume_gui"]["Architecture"] == "L4"
    assert db.load_main_report("archi_test")["synthese"]["ok"] is True


def test_save_main_report_roundtrip_exposes_piece_views(tmp_path):
    from backend.modules.systeme.database import SecureDatabase

    db = SecureDatabase(
        db_path=tmp_path / "technical.db",
        key_path=tmp_path / "secret.key",
    )

    report = {
        "resume_gui": {"Architecture": "L4"},
        "inventaire": {
            "pieces": {
                "piston": {
                    "nom": "piston",
                    "type": "Piston",
                    "construit": True,
                    "rapport": {"piece": "piston"},
                    "objet": {"type": "Piston", "alesage_nominal_m": 0.09},
                },
                "alternateur.rotor": {
                    "nom": "alternateur.rotor",
                    "type": "rotor",
                    "construit": True,
                    "source_composant": "alternateur",
                    "rapport": {"piece": "rotor"},
                    "objet": {"type": None},
                },
            },
            "composants": {"alternateur": {"type": "Alternateur", "construit": True}},
        },
        "rapports_pieces": {"piston": {"piece": "piston", "dimensions": {"diametre_exterieur_m": 0.089}}},
        "construction_pieces": {"construction": {"piston": {"construit": True}}},
        "objets_serialises": {"pieces": {"piston": {"type": "Piston", "alesage_nominal_m": 0.09}}},
        "synthese": {"ok": True},
    }

    saved = db.save_main_report(report, report_name="roundtrip")
    piston = db.get_piece_data("piston")
    nested = db.get_piece_data("alternateur.rotor")
    all_pieces = db.get_all_pieces()

    assert saved["report_complet"] >= 1
    assert piston["inventaire"]["type"] == "Piston"
    assert piston["rapport"]["dimensions"]["diametre_exterieur_m"] == pytest.approx(0.089)
    assert piston["objet_serialise"]["alesage_nominal_m"] == pytest.approx(0.09)
    assert nested["inventaire"]["source_composant"] == "alternateur"
    assert "piston" in all_pieces
    assert "alternateur.rotor" in all_pieces
