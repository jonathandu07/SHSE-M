"""
Chemin : frontend/components/moteur_thermique/moteur_thermique.py
But :
    Orchestrer la visualisation frontend du moteur thermique.
Pourquoi ce fichier existe :
    Il presente le rapport moteur thermique backend et redirige vers les pieces
    detaillees sans dessiner une architecture generique fausse.
Donnees consommees :
    sous_systemes.moteur_thermique, rapports.composants.moteur_thermique,
    rapports_pieces, cao_dossier et mechanical_graphs.
Livrables produits :
    Contrat JSON de composant avec dimensions et graphes disponibles.
Limites :
    - ne choisit pas architecture/cylindres ;
    - ne calcule ni course ni alesage ;
    - ne trace pas de moteur fictif ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import collect_dimensions, get_backend_graphs, get_component_report, safe_dict
from frontend.ensemble.render_contract import empty_render_contract, normalize_chart


COMPONENT_NAME = "moteur_thermique"


def visualiser_composant(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    component = safe_dict(data) or get_component_report(report, COMPONENT_NAME)
    contract = empty_render_contract(
        item_id=COMPONENT_NAME,
        kind="component",
        title="Moteur thermique",
        status="partial" if component else "missing_required",
        reason=None if component else "Rapport backend moteur thermique absent.",
    )
    contract["solidworks_data"]["dimensions_to_copy"] = collect_dimensions(component)
    contract["charts"] = [normalize_chart(item) for item in get_backend_graphs(report, COMPONENT_NAME)]
    if not component:
        contract["actions"].append("Charger ou calculer sous_systemes.moteur_thermique cote backend.")
    if component and not contract["charts"]:
        contract["actions"].append("Generer les graphes moteur thermique cote backend.")
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    return contract


def tracer_croquis_moteur_thermique_2d(*, data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None, titre: str = "Moteur thermique") -> Dict[str, Any]:
    contract = visualiser_composant(data=data, global_report=global_report)
    contract["warnings"].append("Aucun croquis moteur thermique n'est trace sans donnees pieces backend.")
    return contract


if __name__ == "__main__":
    print(json.dumps(visualiser_composant(), ensure_ascii=False, indent=2))
