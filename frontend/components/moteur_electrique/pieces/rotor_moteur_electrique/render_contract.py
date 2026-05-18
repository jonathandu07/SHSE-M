"""
Chemin : frontend/components/moteur_electrique/pieces/rotor_moteur_electrique/render_contract.py
But :
    Fournir le contrat de rendu commun de la piece rotor_moteur_electrique.
Pourquoi ce fichier existe :
    Les pages GUI et exports consomment une forme stable, independante des
    details du script de piece.
Donnees consommees :
    Rapport global et rapport de piece issus de frontend/main.py.
Livrables produits :
    Contrat JSON-serializable avec croquis, 3D, graphes et cotes SolidWorks.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_rendering import build_piece_visualization_contract

PIECE_NAME = "rotor_moteur_electrique"


def build_render_contract(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    return build_piece_visualization_contract(PIECE_NAME, data=data, global_report=global_report)
