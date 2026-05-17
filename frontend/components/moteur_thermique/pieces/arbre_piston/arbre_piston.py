"""
Chemin : frontend/components/moteur_thermique/pieces/arbre_piston/arbre_piston.py
But :
    Orchestrer les visualisations frontend de l'arbre de piston.
Pourquoi ce fichier existe :
    Il sert de page technique de piece : il lit un rapport backend deja calcule,
    appelle les adaptateurs de croquis/3D/graphes et retourne un contrat de rendu
    exploitable par le GUI ou par un export JSON.
Donnees consommees :
    rapports_pieces.arbre_piston, cao_dossier, mechanical_graphs.
Livrables produits :
    Contrat JSON avec croquis 2D cote, vue 3D indicative, graphiques techniques
    et cotes a reporter dans SolidWorks quand elles existent cote backend.
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

from frontend.ensemble.piece_data_adapter import get_piece_report, safe_dict
from frontend.ensemble.render_contract import build_piece_render_contract, normalize_chart


PIECE_NAME = "arbre_piston"


def _call_optional(module_name: str, function_name: str, data: Mapping[str, Any], global_report: Mapping[str, Any]) -> Any:
    try:
        module = __import__(f"{__package__}.{module_name}", fromlist=[function_name])
        func = getattr(module, function_name, None)
        if callable(func):
            return func(data=data, global_report=global_report)
    except Exception as exc:
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}", "source_module": module_name}
    return None


def visualiser_piece(
    *,
    data: Mapping[str, Any] | None = None,
    global_report: Mapping[str, Any] | None = None,
    run_demo: bool = False,
) -> Dict[str, Any]:
    """Construit le contrat de rendu sans lancer de calcul backend implicite."""
    report = safe_dict(global_report)
    piece_report = safe_dict(data)

    if not piece_report and report:
        piece_report = get_piece_report(report, PIECE_NAME)

    if not piece_report and run_demo:
        from frontend.main import get_backend_bridge

        state = get_backend_bridge().run_100kw()
        report = safe_dict(state.get("raw_report"))
        piece_report = get_piece_report(report, PIECE_NAME)

    source_report = report if report else {"rapports_pieces": {PIECE_NAME: piece_report}}
    contract = build_piece_render_contract(PIECE_NAME, source_report, title="Arbre de piston")

    if piece_report:
        contract.setdefault("backend_paths", []).append(piece_report.get("_source_path") or f"rapports_pieces.{PIECE_NAME}")

    sketch = _call_optional("sketches_2d", "build_sketch_contract", piece_report, source_report)
    if isinstance(sketch, Mapping):
        if sketch.get("type") == "sketch_2d":
            contract["sketches_2d"].insert(0, dict(sketch))
        elif sketch.get("status") == "error":
            contract["warnings"].append(str(sketch.get("reason") or "Erreur croquis."))

    view = _call_optional("mesh_3d", "build_view_3d_contract", piece_report, source_report)
    if isinstance(view, Mapping):
        if view.get("type") == "view_3d_indicative":
            contract["views_3d"].insert(0, dict(view))
        elif view.get("status") == "error":
            contract["warnings"].append(str(view.get("reason") or "Erreur 3D."))

    chart_payload = _call_optional("charts", "build_chart_contracts", piece_report, source_report)
    if isinstance(chart_payload, list):
        contract["charts"] = [normalize_chart(c) for c in chart_payload if isinstance(c, Mapping)] + list(contract.get("charts") or [])
    elif isinstance(chart_payload, Mapping) and chart_payload.get("type") == "chart":
        contract["charts"].insert(0, normalize_chart(chart_payload))

    has_payload = any(contract.get(k) for k in ("sketches_2d", "views_3d", "charts")) or bool(
        safe_dict(contract.get("solidworks_data")).get("dimensions_to_copy")
    )
    if has_payload and contract.get("status") == "missing_required":
        contract["status"] = "partial"
    contract["solidworks_data"]["step_export"] = False
    contract["solidworks_data"]["solidworks_ready"] = False
    return contract


def afficher_vues_arbre_piston(*, data: Mapping[str, Any] | None = None, run_demo: bool = False) -> Dict[str, Any]:
    """Affiche un resume console et retourne le contrat de rendu."""
    contract = visualiser_piece(data=data, run_demo=run_demo)
    print("=======================================================")
    print("  Visualisation technique : arbre_piston")
    print("=======================================================")
    print(f"Statut      : {contract.get('status')}")
    print(f"Croquis     : {len(contract.get('sketches_2d') or [])}")
    print(f"3D indic.   : {len(contract.get('views_3d') or [])}")
    print(f"Graphiques  : {len(contract.get('charts') or [])}")
    print("STEP export : False")
    return contract


if __name__ == "__main__":
    print(json.dumps(afficher_vues_arbre_piston(run_demo=True), ensure_ascii=False, indent=2))

