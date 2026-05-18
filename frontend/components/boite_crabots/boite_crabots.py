"""
Chemin : frontend/components/boite_crabots/boite_crabots.py
But :
    Orchestrer la visualisation frontend de la boite a crabots.
Pourquoi ce fichier existe :
    La liaison boite/alternateur/moteur doit venir du backend. Le frontend ne
    dessine pas de pignons ou crabots symboliques en les presentant comme cotes.
Donnees consommees :
    sous_systemes.boite_crabots, rapports.composants.boite_crabots,
    cao_dossier et mechanical_graphs.
Livrables produits :
    Contrat JSON de composant avec dimensions et graphes disponibles.
Limites :
    - ne choisit pas de rapport ;
    - ne dimensionne pas les arbres ;
    - ne dessine pas de boite fictive ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import collect_dimensions, get_backend_graphs, get_component_report, safe_dict
from frontend.ensemble.render_contract import empty_render_contract, normalize_chart


COMPONENT_NAME = "boite_crabots"


def visualiser_composant(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    component = safe_dict(data) or get_component_report(report, COMPONENT_NAME)
    contract = empty_render_contract(
        item_id=COMPONENT_NAME,
        kind="component",
        title="Boite a crabots",
        status="partial" if component else "missing_required",
        reason=None if component else "Rapport backend boite a crabots absent.",
    )
    contract["solidworks_data"]["dimensions_to_copy"] = collect_dimensions(component)
    contract["charts"] = [normalize_chart(item) for item in get_backend_graphs(report, COMPONENT_NAME)]
    if not component:
        contract["actions"].append("Charger ou calculer sous_systemes.boite_crabots cote backend.")
    if component and not contract["charts"]:
        contract["actions"].append("Generer les graphes boite a crabots cote backend.")
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    return contract


def tracer_croquis_boite_crabots_2d(
    boite: Any = None,
    *,
    data: Mapping[str, Any] | None = None,
    global_report: Mapping[str, Any] | None = None,
    titre: str = "Boite a crabots",
) -> Dict[str, Any]:
    if data is None and isinstance(boite, Mapping):
        data = boite
    contract = visualiser_composant(data=data, global_report=global_report)
    contract["warnings"].append("Aucun croquis boite n'est trace sans rapports/dimensions backend.")
    return contract


if __name__ == "__main__":
    print(json.dumps(visualiser_composant(), ensure_ascii=False, indent=2))
