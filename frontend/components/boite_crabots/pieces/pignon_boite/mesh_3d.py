"""
Chemin : frontend/components/boite_crabots/pieces/pignon_boite/mesh_3d.py
But :
    Produire la vue 3D indicative de la piece pignon_boite.
Pourquoi ce fichier existe :
    La 3D Python sert a comprendre la forme depuis les cotes backend. Elle ne
    remplace jamais le modele SolidWorks final.
Donnees consommees :
    Rapport de piece prepare par frontend/ensemble.
Livrables produits :
    Contrat view_3d_indicative avec geometrie JSON.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.cao_rendering import build_generic_view_3d_contract
from frontend.ensemble.piece_data_adapter import get_piece_report, safe_dict

PIECE_NAME = "pignon_boite"


def build_view_3d_contract(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    piece_report = safe_dict(data) or get_piece_report(report, PIECE_NAME)
    return build_generic_view_3d_contract(PIECE_NAME, piece_report)


def afficher_3d(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    return build_view_3d_contract(data=data, global_report=global_report)
