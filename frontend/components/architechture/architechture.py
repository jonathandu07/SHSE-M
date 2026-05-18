"""
Chemin : frontend/components/architechture/architechture.py
But :
    Orchestrer la visualisation frontend de l'architecture moteur.
Pourquoi ce fichier existe :
    L'architecture et le nombre de cylindres sont decides ou traces cote backend.
    Le frontend affiche ces resultats sans fabriquer un schema d'architecture.
Donnees consommees :
    sous_systemes.architecture, rapports.composants.architecture,
    cao_dossier et mechanical_graphs.
Livrables produits :
    Contrat JSON de composant.
Limites :
    - ne choisit pas L/V/boxer/etoile ;
    - ne choisit pas le nombre de cylindres ;
    - ne trace pas un bloc fictif ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import collect_dimensions, get_backend_graphs, get_component_report, safe_dict
from frontend.ensemble.render_contract import empty_render_contract, normalize_chart


COMPONENT_NAME = "architecture"


def visualiser_composant(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    component = safe_dict(data) or get_component_report(report, COMPONENT_NAME)
    contract = empty_render_contract(
        item_id=COMPONENT_NAME,
        kind="component",
        title="Architecture moteur",
        status="partial" if component else "missing_required",
        reason=None if component else "Rapport backend architecture absent.",
    )
    contract["solidworks_data"]["dimensions_to_copy"] = collect_dimensions(component)
    contract["charts"] = [normalize_chart(item) for item in get_backend_graphs(report, COMPONENT_NAME)]
    if not component:
        contract["actions"].append("Charger ou calculer sous_systemes.architecture cote backend.")
    if component and not contract["charts"]:
        contract["actions"].append("Generer les graphes architecture cote backend.")
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    return contract


def tracer_croquis_architecture_2d(
    architecture: Any = None,
    *,
    data: Mapping[str, Any] | None = None,
    global_report: Mapping[str, Any] | None = None,
    titre: str = "Architecture moteur",
) -> Dict[str, Any]:
    if data is None and isinstance(architecture, Mapping):
        data = architecture
    contract = visualiser_composant(data=data, global_report=global_report)
    contract["warnings"].append("Aucun croquis architecture n'est trace sans architecture backend validee.")
    return contract


if __name__ == "__main__":
    print(json.dumps(visualiser_composant(), ensure_ascii=False, indent=2))
