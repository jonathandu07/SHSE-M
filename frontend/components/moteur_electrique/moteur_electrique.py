"""
Chemin : frontend/components/moteur_electrique/moteur_electrique.py
But :
    Orchestrer la visualisation frontend du moteur electrique.
Pourquoi ce fichier existe :
    Le frontend affiche le rapport moteur electrique backend et ses livrables de
    preconception sans dessiner un rotor/stator fictif.
Donnees consommees :
    sous_systemes.moteur_electrique, rapports.composants.moteur_electrique,
    cao_dossier et mechanical_graphs.
Livrables produits :
    Contrat JSON de composant.
Limites :
    - ne calcule pas puissance, couple ou rendement ;
    - ne cree pas de geometrie moteur ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import collect_dimensions, get_backend_graphs, get_component_report, safe_dict
from frontend.ensemble.render_contract import empty_render_contract, normalize_chart


COMPONENT_NAME = "moteur_electrique"


def visualiser_composant(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    component = safe_dict(data) or get_component_report(report, COMPONENT_NAME)
    contract = empty_render_contract(
        item_id=COMPONENT_NAME,
        kind="component",
        title="Moteur electrique",
        status="partial" if component else "missing_required",
        reason=None if component else "Rapport backend moteur electrique absent.",
    )
    contract["solidworks_data"]["dimensions_to_copy"] = collect_dimensions(component)
    contract["charts"] = [normalize_chart(item) for item in get_backend_graphs(report, COMPONENT_NAME)]
    if not component:
        contract["actions"].append("Charger ou calculer sous_systemes.moteur_electrique cote backend.")
    if component and not contract["charts"]:
        contract["actions"].append("Generer les graphes moteur electrique cote backend.")
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    return contract


def tracer_croquis_moteur_electrique_2d(
    moteur: Any = None,
    *,
    data: Mapping[str, Any] | None = None,
    global_report: Mapping[str, Any] | None = None,
    titre: str = "Moteur electrique",
) -> Dict[str, Any]:
    if data is None and isinstance(moteur, Mapping):
        data = moteur
    contract = visualiser_composant(data=data, global_report=global_report)
    contract["warnings"].append("Aucun croquis moteur electrique n'est trace sans donnees backend.")
    return contract


if __name__ == "__main__":
    print(json.dumps(visualiser_composant(), ensure_ascii=False, indent=2))
