"""
Chemin : frontend/ensemble/piece_rendering.py
But :
    Assembler le contrat complet de visualisation d'une piece.
Pourquoi ce fichier existe :
    Les nombreux dossiers frontend/components doivent partager une logique
    passive commune : lire les dimensions backend, produire croquis/3D/graphes
    quand les donnees existent, et diagnostiquer ce qui manque.
Donnees consommees :
    Rapport global frontend/main.py, rapport de piece, cao_dossier,
    mechanical_graphs.
Livrables produits :
    Contrats de rendu piece JSON-serializable.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.cao_rendering import build_generic_sketch_contract, build_generic_view_3d_contract
from frontend.ensemble.graph_rendering import build_chart_contracts_from_backend
from frontend.ensemble.piece_data_adapter import STATUS_AVAILABLE, STATUS_MISSING_REQUIRED, STATUS_PARTIAL, get_piece_report, safe_dict
from frontend.ensemble.render_contract import build_piece_render_contract


def build_piece_visualization_contract(
    piece_name: str,
    *,
    data: Mapping[str, Any] | None = None,
    global_report: Mapping[str, Any] | None = None,
    title: str | None = None,
) -> Dict[str, Any]:
    report = safe_dict(global_report)
    piece_report = safe_dict(data) or get_piece_report(report, piece_name)
    source_report = report if report else {"rapports_pieces": {piece_name: piece_report}}
    contract = build_piece_render_contract(piece_name, source_report, title=title or piece_name.replace("_", " ").title())

    if not piece_report:
        contract["status"] = STATUS_MISSING_REQUIRED
        contract["reason"] = "Rapport backend de piece absent."
        contract["actions"].append("Charger le rapport backend via frontend/main.py.")
        contract["step_export"] = False
        contract["solidworks_ready"] = False
        return contract

    sketch = build_generic_sketch_contract(piece_name, piece_report)
    view = build_generic_view_3d_contract(piece_name, piece_report)
    charts = build_chart_contracts_from_backend(piece_name, source_report)

    existing_sketch_ids = {item.get("id") for item in contract.get("sketches_2d") or [] if isinstance(item, Mapping)}
    if sketch.get("id") not in existing_sketch_ids:
        contract["sketches_2d"].insert(0, sketch)

    existing_view_ids = {item.get("id") for item in contract.get("views_3d") or [] if isinstance(item, Mapping)}
    if view.get("id") not in existing_view_ids:
        contract["views_3d"].insert(0, view)

    if charts:
        contract["charts"] = charts + [item for item in contract.get("charts") or [] if isinstance(item, Mapping)]

    for item in (sketch, view):
        for missing in item.get("missing_fields") or []:
            if missing not in contract["missing_fields"]:
                contract["missing_fields"].append(missing)
        for action in item.get("actions") or []:
            if action not in contract["actions"]:
                contract["actions"].append(action)

    if sketch.get("solidworks_dimensions"):
        contract["solidworks_data"]["dimensions_to_copy"] = list(sketch["solidworks_dimensions"])
    contract["solidworks_data"]["missing_dimensions"] = list(contract.get("missing_fields") or [])
    contract["solidworks_data"]["notes"].append("Croquis et 3D indicatifs issus des cotes backend ; aucun STEP n'est produit.")

    statuses = [sketch.get("status"), view.get("status")]
    if any(status == STATUS_AVAILABLE for status in statuses):
        contract["status"] = STATUS_PARTIAL if contract["missing_fields"] else STATUS_AVAILABLE
    elif piece_report:
        contract["status"] = STATUS_PARTIAL
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    contract["solidworks_data"]["step_export"] = False
    contract["solidworks_data"]["solidworks_ready"] = False
    return contract


__all__ = ["build_piece_visualization_contract"]
