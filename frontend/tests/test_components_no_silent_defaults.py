from __future__ import annotations

from pathlib import Path


def test_ensemble_wrappers_lisent_un_rapport_sans_appeler_bridge(monkeypatch):
    def fail_bridge():
        raise AssertionError("Le bridge ne doit pas etre appele avec un rapport fourni")

    monkeypatch.setattr("frontend.main.get_backend_bridge", fail_bridge)

    from frontend.ensemble.air import afficher_resultats_air
    from frontend.ensemble.optimisation import afficher_resultats_optimisation

    assert afficher_resultats_air({"air": {"rho": 1.2}})["status"] == "available"
    assert afficher_resultats_optimisation({"optimisation": {"score": 0.8}})["status"] == "available"


def test_orchestrateurs_frontend_ne_contiennent_pas_fallbacks_metier_dangereux():
    files = [
        Path("frontend/ensemble/backend_bridge.py"),
        Path("frontend/ensemble/cao_adapter.py"),
        Path("frontend/ensemble/graphs_adapter.py"),
        Path("frontend/ensemble/diagnostic_adapter.py"),
        Path("frontend/ensemble/actions.py"),
        Path("frontend/ensemble/piece_data_adapter.py"),
        Path("frontend/ensemble/render_contract.py"),
        Path("frontend/ensemble/visualisation_orchestrator.py"),
        Path("frontend/components/moteur_thermique/pieces/arbre_piston/arbre_piston.py"),
        Path("frontend/components/moteur_thermique/pieces/arbre_piston/charts.py"),
        Path("frontend/gui/technical_visualization.py"),
    ]
    forbidden = (" or 3000", " or 400", " or 0.9", " or 0.08", "default=0.0", "safe_float(..., default=0.0)")

    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token!r} dans {path}"


def test_ensemble_ne_lance_pas_run_100kw_sauf_bridge_demo_explicite():
    files = [p for p in Path("frontend/ensemble").glob("*.py") if p.name != "backend_bridge.py"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert ".run_100kw(" not in text, f"run_100kw implicite dans {path}"
