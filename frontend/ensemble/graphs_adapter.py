"""
Chemin : frontend/ensemble/graphs_adapter.py
But :
    Adapter les graphiques techniques backend pour le frontend.
Pourquoi ce fichier existe :
    Les graphes sont calcules cote backend. Le frontend doit seulement verifier
    qu'une serie de points existe, puis l'exposer au GUI ou a Matplotlib.
Donnees consommees :
    rapport.mechanical_graphs et rapport.cao_dossier.graphiques.
Livrables produits :
    Liste normalisee de graphes passifs.
Limites :
    - ne genere aucun point ;
    - ne choisit aucun materiau ;
    - ne recalcule aucune contrainte ;
    - retourne missing_required si le backend n'a pas fourni les points.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import get_path, safe_dict, safe_list
from frontend.ensemble.render_contract import normalize_chart


def collect_backend_charts(report: Mapping[str, Any]) -> Dict[str, Any]:
    data = safe_dict(report)
    raw = []
    raw.extend(safe_list(get_path(data, "mechanical_graphs.graphiques")))
    raw.extend(safe_list(get_path(data, "mechanical_graphs.graphs")))
    raw.extend(safe_list(get_path(data, "cao_dossier.graphiques")))
    charts = [normalize_chart(item) for item in raw if isinstance(item, Mapping)]
    missing = not charts
    return {
        "status": "missing_required" if missing else "available",
        "charts": charts,
        "missing_fields": ["mechanical_graphs.graphiques"] if missing else [],
        "actions": ["Generer mechanical_graphs cote backend."] if missing else [],
        "source": "backend",
    }


__all__ = ["collect_backend_charts"]
