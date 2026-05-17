"""
Chemin : frontend/components/moteur_thermique/pieces/arbre_piston/charts.py
But :
    Adapter les graphiques techniques backend pour l'arbre de piston.
Pourquoi ce fichier existe :
    Le frontend doit afficher des points deja fournis par mechanical_graphs ou
    par le rapport de piece. Il ne genere pas de courbe physique locale.
Donnees consommees :
    mechanical_graphs.graphiques et rapports_pieces.arbre_piston.
Livrables produits :
    Contrats de graphiques JSON-serializable.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import get_backend_graphs, safe_dict


def build_chart_contracts(*, data: Mapping[str, Any], global_report: Mapping[str, Any] | None = None) -> list[Dict[str, Any]]:
    report = safe_dict(global_report)
    graphs = get_backend_graphs(report, "arbre_piston") if report else []
    if graphs:
        return [dict(g) for g in graphs]

    return [
        {
            "id": "arbre_piston_graphes_backend_absents",
            "type": "chart",
            "status": "missing_required",
            "title": "Graphiques arbre de piston indisponibles",
            "x_label": "",
            "y_label": "",
            "series": [],
            "markers": [],
            "formula": None,
            "source": "backend.mechanical_graphs",
            "interpretation": "Aucun point backend disponible ; le frontend ne trace pas de courbe inventee.",
            "missing_fields": ["mechanical_graphs.graphiques"],
        }
    ]


__all__ = ["build_chart_contracts"]

