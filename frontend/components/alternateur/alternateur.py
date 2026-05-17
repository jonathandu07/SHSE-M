"""
Chemin : frontend/components/alternateur/alternateur.py
But :
    Orchestrer la visualisation frontend du composant alternateur.
Pourquoi ce fichier existe :
    Il transforme les donnees alternateur deja calculees par le backend en
    contrat de rendu. Il ne construit pas un alternateur et ne trace pas une
    coupe fictive si les dimensions backend sont absentes.
Donnees consommees :
    sous_systemes.alternateur, rapports.composants.alternateur,
    cao_dossier et mechanical_graphs.
Livrables produits :
    Contrat JSON de composant, dimensions a copier, graphes backend disponibles.
Limites :
    - ne calcule pas rendement, couple ou pertes ;
    - ne dessine pas de geometrie inventee ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import collect_dimensions, get_backend_graphs, get_component_report, safe_dict
from frontend.ensemble.render_contract import empty_render_contract, normalize_chart


COMPONENT_NAME = "alternateur"


def visualiser_composant(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    component = safe_dict(data) or get_component_report(report, COMPONENT_NAME)
    contract = empty_render_contract(
        item_id=COMPONENT_NAME,
        kind="component",
        title="Alternateur",
        status="partial" if component else "missing_required",
        reason=None if component else "Rapport backend alternateur absent.",
    )
    contract["solidworks_data"]["dimensions_to_copy"] = collect_dimensions(component)
    contract["charts"] = [normalize_chart(item) for item in get_backend_graphs(report, COMPONENT_NAME)]
    if not component:
        contract["actions"].append("Charger ou calculer sous_systemes.alternateur cote backend.")
    if component and not contract["charts"]:
        contract["actions"].append("Generer les graphes alternateur cote backend.")
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    return contract


def tracer_croquis_alternateur_2d(*, data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None, titre: str = "Alternateur") -> Dict[str, Any]:
    contract = visualiser_composant(data=data, global_report=global_report)
    contract["warnings"].append("Aucun croquis alternateur n'est trace sans donnees CAO backend.")
    return contract


if __name__ == "__main__":
    print(json.dumps(visualiser_composant(), ensure_ascii=False, indent=2))
