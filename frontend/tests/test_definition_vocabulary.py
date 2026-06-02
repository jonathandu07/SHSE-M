from __future__ import annotations

from pathlib import Path


def test_libelles_ui_principaux_ne_centrent_pas_le_programme_sur_solidworks():
    files = [
        Path("frontend/main.py"),
        Path("frontend/gui/cao_dossier_view.py"),
        Path("frontend/gui/dashboard.py"),
        Path("frontend/gui/technical_visualization.py"),
        Path("frontend/components/design_blocks.py"),
        Path("frontend/ensemble/actions.py"),
        Path("backend/modules/systeme/frontend_contract.py"),
        Path("backend/modules/systeme/cao_dossier.py"),
    ]
    forbidden = [
        "Preparation SolidWorks",
        "Préparation SolidWorks",
        "Dossier SolidWorks",
        "SolidWorks ready",
        "SolidWorks pret",
        "SolidWorks prêt",
        "Dossier de modelisation SolidWorks",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contient encore {token!r}"


def test_champs_legacy_restant_sont_des_drapeaux_de_non_generation():
    text = Path("frontend/gui/cao_dossier_view.py").read_text(encoding="utf-8")

    assert "Generation STEP" in text
    assert 'MetricRow("Generation STEP"' in text
    assert '"missing"' in text
    assert "DOSSIER DE DEFINITION" in text
