"""
Chemin : frontend/components/moteur_thermique/pieces/arbre_vilbrequin/arbre_vilbrequin.py
But :
    Orchestrer la visualisation frontend de la piece arbre_vilbrequin.
Pourquoi ce fichier existe :
    Ce fichier est la page technique de piece. Il recoit un rapport backend deja
    calcule via frontend/main.py et assemble croquis, vue 3D indicative,
    graphiques et cotes SolidWorks sans lancer de calcul cache.
Donnees consommees :
    Rapport global, rapport de piece, cao_dossier et mechanical_graphs.
Livrables produits :
    Contrat de rendu JSON-serializable pour le GUI et les exports.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import run_demo_100kw
from frontend.ensemble.piece_data_adapter import get_piece_report, safe_dict
from frontend.ensemble.piece_rendering import build_piece_visualization_contract

PIECE_NAME = "arbre_vilbrequin"
TITLE = "Arbre Vilbrequin"


def visualiser_piece(
    *,
    data: Mapping[str, Any] | None = None,
    global_report: Mapping[str, Any] | None = None,
    run_demo: bool = False,
) -> Dict[str, Any]:
    """Construit le contrat de rendu depuis les donnees backend fournies."""
    report = safe_dict(global_report)
    piece_report = safe_dict(data)
    if not piece_report and report:
        piece_report = get_piece_report(report, PIECE_NAME)
    if not piece_report and run_demo:
        demo = run_demo_100kw()
        report = safe_dict(demo.get("raw_report"))
        piece_report = get_piece_report(report, PIECE_NAME)
    return build_piece_visualization_contract(PIECE_NAME, data=piece_report, global_report=report, title=TITLE)


def afficher_vues_arbre_vilbrequin(*, data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None, run_demo: bool = False) -> Dict[str, Any]:
    contract = visualiser_piece(data=data, global_report=global_report, run_demo=run_demo)
    print(json.dumps(contract, ensure_ascii=False, indent=2))
    return contract


if __name__ == "__main__":
    afficher_vues_arbre_vilbrequin(run_demo=True)
