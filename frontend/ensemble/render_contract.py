"""
Chemin : frontend/ensemble/render_contract.py
But :
    Construire des contrats de rendu JSON-serializable pour les visualisations.
Pourquoi ce fichier existe :
    Le GUI doit afficher des croquis, vues 3D indicatives et graphiques sans
    connaitre les details de chaque piece. Ce module fournit une forme commune.
Donnees consommees :
    Rapports backend deja calcules, cao_dossier, mechanical_graphs.
Livrables produits :
    Contrats de rendu piece/composant/systeme.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import (
    STATUS_AVAILABLE,
    STATUS_MISSING_REQUIRED,
    STATUS_PARTIAL,
    collect_dimensions,
    get_backend_graphs,
    get_backend_sketches,
    get_backend_views_3d,
    get_piece_report,
    safe_dict,
)


def empty_render_contract(
    *,
    item_id: str,
    kind: str,
    title: str,
    status: str = STATUS_MISSING_REQUIRED,
    reason: str | None = None,
) -> Dict[str, Any]:
    return {
        "id": item_id,
        "kind": kind,
        "title": title,
        "status": status,
        "source": "backend",
        "backend_paths": [],
        "sketches_2d": [],
        "views_3d": [],
        "charts": [],
        "solidworks_data": {
            "dimensions_to_copy": [],
            "notes": [],
            "missing_dimensions": [],
            "step_export": False,
            "solidworks_ready": False,
        },
        "step_export": False,
        "solidworks_ready": False,
        "missing_fields": [],
        "warnings": [],
        "actions": [],
        "reason": reason,
    }


def normalize_sketch(sketch: Mapping[str, Any]) -> Dict[str, Any]:
    status = sketch.get("status") or sketch.get("statut") or STATUS_PARTIAL
    return {
        "id": sketch.get("id") or sketch.get("name") or "sketch_backend",
        "type": "sketch_2d",
        "status": status,
        "title": sketch.get("title") or sketch.get("titre") or sketch.get("id") or "Croquis backend",
        "figure_path": sketch.get("figure_path") or sketch.get("path"),
        "geometry_json": safe_dict(sketch.get("geometrie")) or safe_dict(sketch.get("geometry_json")),
        "used_fields": list(sketch.get("used_fields") or sketch.get("champs_utilises") or []),
        "missing_fields": list(sketch.get("missing_fields") or sketch.get("missing") or []),
        "solidworks_dimensions": list(sketch.get("solidworks_dimensions") or sketch.get("cotes") or []),
        "source": sketch.get("source") or "backend.cao_dossier",
    }


def normalize_view_3d(view: Mapping[str, Any]) -> Dict[str, Any]:
    status = view.get("status") or view.get("statut") or STATUS_PARTIAL
    geometry = safe_dict(view.get("json_geometry")) or safe_dict(view.get("dimensions")) or safe_dict(view.get("geometry_json"))
    return {
        "id": view.get("id") or view.get("name") or "view_3d_backend",
        "type": "view_3d_indicative",
        "status": status,
        "title": view.get("title") or view.get("titre") or view.get("id") or "Vue 3D indicative backend",
        "mesh_available": bool(view.get("mesh_available") or geometry),
        "json_geometry": geometry,
        "warning": view.get("avertissement") or view.get("warning") or "Vue indicative, pas STEP, pas modele final.",
        "used_fields": list(view.get("used_fields") or []),
        "missing_fields": list(view.get("missing_fields") or view.get("missing") or []),
        "source": view.get("source") or "backend.cao_dossier",
    }


def normalize_chart(chart: Mapping[str, Any]) -> Dict[str, Any]:
    status = chart.get("status") or STATUS_PARTIAL
    return {
        "id": chart.get("id") or chart.get("name") or "chart_backend",
        "type": "chart",
        "status": status,
        "title": chart.get("title") or chart.get("titre") or chart.get("id") or "Graphique backend",
        "x_label": chart.get("x_label") or "",
        "y_label": chart.get("y_label") or "",
        "series": list(chart.get("series") or []),
        "markers": list(chart.get("markers") or []),
        "formula": chart.get("formula") or chart.get("formule"),
        "source": chart.get("source") or "backend.mechanical_graphs",
        "interpretation": chart.get("interpretation") or "",
        "missing_fields": list(chart.get("missing_fields") or chart.get("missing") or []),
    }


def build_piece_render_contract(piece_name: str, global_report: Mapping[str, Any], *, title: str | None = None) -> Dict[str, Any]:
    piece_report = get_piece_report(global_report, piece_name)
    contract = empty_render_contract(
        item_id=piece_name,
        kind="piece",
        title=title or piece_name.replace("_", " ").title(),
        status=STATUS_MISSING_REQUIRED if not piece_report else STATUS_PARTIAL,
        reason=None if piece_report else "Rapport backend de piece absent.",
    )

    source_path = piece_report.get("_source_path") if isinstance(piece_report, Mapping) else None
    if source_path:
        contract["backend_paths"].append(source_path)

    sketches = [normalize_sketch(item) for item in get_backend_sketches(global_report, piece_name)]
    views = [normalize_view_3d(item) for item in get_backend_views_3d(global_report, piece_name)]
    charts = [normalize_chart(item) for item in get_backend_graphs(global_report, piece_name)]

    dimensions = collect_dimensions(piece_report)
    contract["sketches_2d"] = sketches
    contract["views_3d"] = views
    contract["charts"] = charts
    contract["solidworks_data"]["dimensions_to_copy"] = dimensions
    contract["solidworks_data"]["notes"].append("Donnees a reporter dans SolidWorks ; aucun STEP n'est produit.")

    unknowns = []
    for section in ("inconnues.impossibles", "inconnues.partielles", "missing_fields"):
        value = piece_report
        for part in section.split("."):
            value = value.get(part) if isinstance(value, Mapping) else None
        if isinstance(value, list):
            unknowns.extend(value)
    contract["missing_fields"] = unknowns
    contract["solidworks_data"]["missing_dimensions"] = unknowns

    if sketches or views or charts or dimensions:
        contract["status"] = STATUS_AVAILABLE if not unknowns else STATUS_PARTIAL
        contract["reason"] = None
    elif piece_report:
        contract["status"] = STATUS_PARTIAL
        contract["warnings"].append("Rapport piece present, mais aucun livrable graphique backend n'est encore disponible.")
        contract["actions"].append("Generer cao_dossier/mechanical_graphs cote backend.")
    else:
        contract["actions"].append("Produire ou charger le rapport backend de la piece.")

    contract["solidworks_data"]["step_export"] = False
    contract["solidworks_data"]["solidworks_ready"] = False
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    return contract


def summarize_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "id": contract.get("id"),
        "title": contract.get("title"),
        "kind": contract.get("kind"),
        "status": contract.get("status"),
        "sketches": len(contract.get("sketches_2d") or []),
        "views_3d": len(contract.get("views_3d") or []),
        "charts": len(contract.get("charts") or []),
        "dimensions": len(safe_dict(contract.get("solidworks_data")).get("dimensions_to_copy") or []),
        "missing_fields": len(contract.get("missing_fields") or []),
    }
