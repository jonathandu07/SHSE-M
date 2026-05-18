"""
Chemin : frontend/components/moteur_thermique/pieces/arbre_vilbrequin/charts.py
But :
    Exposer les graphiques backend de comportement pour la piece arbre_vilbrequin.
Pourquoi ce fichier existe :
    Le frontend affiche les courbes mecaniques/physiques seulement si le backend
    a fourni les points. Aucune courbe n'est inventee ici.
Donnees consommees :
    mechanical_graphs et cao_dossier.graphiques.
Livrables produits :
    Contrats chart et figures Matplotlib optionnelles.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.graph_rendering import build_chart_contracts_from_backend, build_chart_figure

PIECE_NAME = "arbre_vilbrequin"


def build_chart_contracts(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> list[Dict[str, Any]]:
    return build_chart_contracts_from_backend(PIECE_NAME, global_report)


def tracer_graphique(chart: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    charts = [dict(chart)] if isinstance(chart, Mapping) else build_chart_contracts(global_report=global_report)
    if not charts:
        raise ValueError("Aucun graphique backend disponible.")
    return build_chart_figure(charts[0])



def plot(chart: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    return tracer_graphique(chart=chart, global_report=global_report)


def make_figure(chart: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    return tracer_graphique(chart=chart, global_report=global_report)
