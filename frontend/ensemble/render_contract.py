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
    get_path,
    get_piece_report,
    safe_dict,
)
from frontend.ensemble.contract_adapter import (
    STATUS_COMPUTED,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    STATUS_PARTIAL as CONTRACT_STATUS_PARTIAL,
    field_has_trace,
    normalize_contract_status,
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
        "dossier_definition_solidworks": {
            "statut": "blocked" if status == STATUS_MISSING_REQUIRED else "partial",
            "solidworks_ready": False,
            "step_generation": False,
            "schema_only": True,
            "final_geometry": False,
            "features_a_modeliser": [],
            "cotes_connues": {},
            "cotes_manquantes": {},
            "interfaces": [],
            "tolerances": [],
            "surfaces_fonctionnelles": [],
            "contraintes_rdm": [],
            "limites_usage": [],
            "controles_qualite": [],
            "notes_modelisation": [],
            "statut_validation": "not_validated",
        },
        "interfaces_assemblage": [],
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
        "warning": view.get("avertissement") or view.get("warning") or "Schema de principe pour preparation SolidWorks ; geometrie partielle, aucun STEP.",
        "used_fields": list(view.get("used_fields") or []),
        "missing_fields": list(view.get("missing_fields") or view.get("missing") or []),
        "source": view.get("source") or "backend.cao_dossier",
    }


def normalize_chart(chart: Mapping[str, Any]) -> Dict[str, Any]:
    series = list(chart.get("series") or [])
    has_points = any(isinstance(item, Mapping) and item.get("points") for item in series)
    raw_status = chart.get("status") or chart.get("statut")
    if raw_status is not None:
        status = normalize_contract_status(raw_status)
        if status in {STATUS_COMPUTED, STATUS_VALIDATED_BY_OPTIMIZATION} and not field_has_trace(chart):
            status = CONTRACT_STATUS_PARTIAL
    else:
        status = STATUS_PARTIAL
    if not has_points and status == STATUS_AVAILABLE:
        status = STATUS_PARTIAL
    return {
        "id": chart.get("id") or chart.get("name") or "chart_backend",
        "type": "chart",
        "status": status,
        "raw_status": raw_status,
        "title": chart.get("title") or chart.get("titre") or chart.get("id") or "Graphique backend",
        "x_label": chart.get("x_label") or "",
        "y_label": chart.get("y_label") or "",
        "series": series,
        "markers": list(chart.get("markers") or []),
        "formula": chart.get("formula") or chart.get("formule"),
        "source": chart.get("source") or "backend.mechanical_graphs",
        "interpretation": chart.get("interpretation") or "",
        "missing_fields": list(chart.get("missing_fields") or chart.get("missing") or []),
        "trace_present": field_has_trace(chart),
        "warning": chart.get("warning") or chart.get("avertissement") or (
            "Graphique partiel : donnees ou trace backend insuffisantes."
            if status == STATUS_PARTIAL
            else None
        ),
    }


def _collect_piece_unknowns(piece_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    inconnues = piece_report.get("inconnues")
    if isinstance(inconnues, Mapping):
        for category, values in inconnues.items():
            for item in values if isinstance(values, list) else []:
                if isinstance(item, Mapping):
                    row = dict(item)
                    row.setdefault("category", category)
                    row.setdefault("status", row.get("statut") or "missing_required")
                    out.append(row)
                else:
                    out.append({"category": category, "name": str(item), "status": "missing_required"})
    for key, category in (("inconnues_cao", "cao"), ("missing_fields", "geometry")):
        values = piece_report.get(key)
        for item in values if isinstance(values, list) else []:
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("category", category)
                row.setdefault("status", row.get("statut") or "missing_required")
                out.append(row)
            else:
                out.append({"category": category, "name": str(item), "status": "missing_required"})

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in out:
        sig = (
            str(item.get("path") or item.get("champ") or item.get("name") or item.get("nom") or ""),
            str(item.get("category") or ""),
            str(item.get("reason") or item.get("raison") or item.get("detail") or ""),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(item)
    return deduped


def _safe_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        rows: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("nom", str(key))
            else:
                row = {"nom": str(key), "valeur": item}
            rows.append(row)
        return rows
    if isinstance(value, (list, tuple)):
        return [dict(item) if isinstance(item, Mapping) else {"nom": str(item)} for item in value]
    if value is not None:
        return [{"valeur": value}]
    return []


def _safe_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {
            str(k): dict(v) if isinstance(v, Mapping) else v
            for k, v in value.items()
        }
    return {}


def _first_rows_from_values(*values: Any) -> list[dict[str, Any]]:
    for value in values:
        rows = _safe_rows(value)
        if rows:
            return rows
    return []


def _first_rows(piece_report: Mapping[str, Any], *paths: str) -> list[dict[str, Any]]:
    for path in paths:
        rows = _safe_rows(get_path(piece_report, path))
        if rows:
            return rows
    return []


def _dimension_key(item: Mapping[str, Any]) -> str:
    return str(item.get("path") or item.get("label") or item.get("nom") or item.get("name") or len(item))


def _unknown_key(item: Mapping[str, Any]) -> str:
    return str(
        item.get("path")
        or item.get("champ")
        or item.get("nom")
        or item.get("name")
        or item.get("label")
        or len(item)
    )


def _known_dimensions_from_contract(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    solidworks = safe_dict(contract.get("solidworks_data"))
    for item in solidworks.get("dimensions_to_copy") or []:
        if isinstance(item, Mapping):
            out.setdefault(_dimension_key(item), dict(item))
    for sketch in contract.get("sketches_2d") or []:
        if not isinstance(sketch, Mapping):
            continue
        for item in sketch.get("solidworks_dimensions") or []:
            if isinstance(item, Mapping):
                out.setdefault(_dimension_key(item), dict(item))
    return out


def _features_from_contract(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for block_name in ("sketches_2d", "views_3d"):
        for item in contract.get(block_name) or []:
            if not isinstance(item, Mapping):
                continue
            geometry = safe_dict(item.get("geometry_json")) or safe_dict(item.get("json_geometry"))
            for feature in geometry.get("features") or []:
                if not isinstance(feature, Mapping):
                    continue
                row = {
                    "type": feature.get("type"),
                    "label": feature.get("label") or feature.get("type"),
                    "source": feature.get("source") or "backend",
                    "schematic": bool(feature.get("schematic", True)),
                    "final_geometry": False,
                }
                sig = (str(row["type"]), str(row["label"]))
                if sig in seen:
                    continue
                seen.add(sig)
                features.append(row)
    return features


def _missing_dimensions_from_unknowns(unknowns: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in unknowns:
        row = dict(item) if isinstance(item, Mapping) else {"nom": str(item)}
        out.setdefault(_unknown_key(row), row)
    return out


def _definition_status(
    *,
    piece_report: Mapping[str, Any],
    cotes_connues: Mapping[str, Any],
    cotes_manquantes: Mapping[str, Any],
    tolerances: list[dict[str, Any]],
    materiaux: list[dict[str, Any]],
) -> str:
    if not piece_report or not cotes_connues:
        return "blocked"
    existing = safe_dict(piece_report.get("dossier_definition_solidworks")) or safe_dict(piece_report.get("dossier_cao_preparation"))
    requested = str(existing.get("statut") or existing.get("status") or "").strip()
    if requested == "ready_for_manual_modeling":
        if cotes_manquantes or not tolerances or not materiaux:
            return "partial"
        return "ready_for_manual_modeling"
    if requested in {"blocked", "partial"}:
        return requested
    return "partial"


def refresh_solidworks_definition_dossier(contract: Dict[str, Any], piece_name: str, piece_report: Mapping[str, Any]) -> Dict[str, Any]:
    """Expose un dossier d'aide a la modelisation, sans exporter de CAO."""
    existing = safe_dict(piece_report.get("dossier_definition_solidworks")) or safe_dict(piece_report.get("dossier_cao_preparation"))
    cotes_connues = _safe_mapping(existing.get("cotes_connues")) or _known_dimensions_from_contract(contract)
    cotes_manquantes = _safe_mapping(existing.get("cotes_manquantes")) or _missing_dimensions_from_unknowns(list(contract.get("missing_fields") or []))
    features = _safe_rows(existing.get("features_a_modeliser")) or _features_from_contract(contract)
    interfaces = _first_rows_from_values(
        existing.get("interfaces_assemblage"),
        existing.get("interfaces"),
        get_path(piece_report, "interfaces_assemblage"),
        get_path(piece_report, "interfaces"),
        get_path(piece_report, "liaisons"),
    )
    tolerances = _first_rows_from_values(
        existing.get("tolerances"),
        get_path(piece_report, "tolerances"),
        get_path(piece_report, "tolerances_et_jeux"),
        get_path(piece_report, "jeux"),
        get_path(piece_report, "ajustements"),
    )
    jeux_ajustements = _first_rows_from_values(
        existing.get("jeux_ajustements"),
        get_path(piece_report, "jeux_ajustements"),
        get_path(piece_report, "jeux"),
        get_path(piece_report, "ajustements"),
    )
    surfaces = _first_rows_from_values(existing.get("surfaces_fonctionnelles"), get_path(piece_report, "surfaces_fonctionnelles"), get_path(piece_report, "surfaces"))
    contraintes_rdm = _first_rows_from_values(existing.get("contraintes_rdm"), get_path(piece_report, "contraintes_rdm"), get_path(piece_report, "rdm"), get_path(piece_report, "contraintes"))
    limites_usage = _first_rows_from_values(existing.get("limites_usage"), get_path(piece_report, "limites_usage"), get_path(piece_report, "limites"), get_path(piece_report, "performances"))
    controles_qualite = _first_rows_from_values(existing.get("controles_qualite"), get_path(piece_report, "controles_qualite"), get_path(piece_report, "controle_qualite"), get_path(piece_report, "qualite"))
    materiaux = _first_rows_from_values(existing.get("materiaux"), get_path(piece_report, "materiaux"), get_path(piece_report, "materiau"), get_path(piece_report, "material"), get_path(piece_report, "materials"))
    inconnues_bloquantes = _first_rows_from_values(
        existing.get("inconnues_bloquantes"),
        get_path(piece_report, "inconnues_bloquantes"),
        get_path(piece_report, "inconnues.bloquantes"),
        get_path(piece_report, "inconnues.impossibles"),
    )
    notes = _first_rows_from_values(existing.get("notes_modelisation"), get_path(piece_report, "notes_modelisation"))
    if not notes:
        notes = [
            {
                "nom": "orientation",
                "texte": "Dossier d'aide a la modelisation manuelle dans SolidWorks ; aucun export CAO n'est genere.",
            }
        ]

    statut = _definition_status(
        piece_report=piece_report,
        cotes_connues=cotes_connues,
        cotes_manquantes=cotes_manquantes,
        tolerances=tolerances,
        materiaux=materiaux,
    )
    validation = existing.get("statut_validation")
    if validation not in {"validated_by_calculation", "not_validated"}:
        validation = "not_validated"

    dossier = {
        "piece": piece_name,
        "statut": statut,
        "solidworks_ready": False,
        "step_generation": False,
        "step_export": False,
        "schema_only": True,
        "final_geometry": False,
        "features_a_modeliser": features,
        "cotes_connues": cotes_connues,
        "cotes_manquantes": cotes_manquantes,
        "interfaces": interfaces,
        "interfaces_assemblage": interfaces,
        "tolerances": tolerances,
        "jeux_ajustements": jeux_ajustements,
        "surfaces_fonctionnelles": surfaces,
        "contraintes_rdm": contraintes_rdm,
        "limites_usage": limites_usage,
        "controles_qualite": controles_qualite,
        "notes_modelisation": notes,
        "statut_validation": validation,
        "materiaux": materiaux,
        "inconnues_bloquantes": inconnues_bloquantes,
    }
    contract["dossier_definition_solidworks"] = dossier
    contract["dossier_cao_preparation"] = dossier
    contract["interfaces_assemblage"] = interfaces
    solidworks = safe_dict(contract.get("solidworks_data"))
    solidworks["dossier_definition_solidworks"] = dossier
    solidworks["step_export"] = False
    solidworks["solidworks_ready"] = False
    contract["solidworks_data"] = solidworks
    contract["step_export"] = False
    contract["solidworks_ready"] = False
    return contract


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
    contract["solidworks_data"]["notes"].append("Donnees a reporter dans SolidWorks pour modelisation manuelle ; aucun export CAO n'est produit.")

    unknowns = _collect_piece_unknowns(piece_report)
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
    refresh_solidworks_definition_dossier(contract, piece_name, piece_report)
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
