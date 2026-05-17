from __future__ import annotations

from pathlib import Path


def test_orchestrateurs_frontend_ne_contiennent_pas_fallbacks_metier_dangereux():
    files = [
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

