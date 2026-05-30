"""
Chemin : frontend/ensemble/missing_data.py
But :
    Diagnostiquer les champs manquants pour les rendus frontend.
Pourquoi ce fichier existe :
    Les croquis, graphes et vues 3D doivent refuser proprement une piece non
    cotee au lieu de remplacer une longueur, un diametre ou un effort par zero.
Donnees consommees :
    Rapports backend deja calcules et champs extraits par piece_data_adapter.
Livrables produits :
    Listes de champs disponibles, champs manquants, statut de rendu et actions.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence

from frontend.ensemble.piece_data_adapter import STATUS_AVAILABLE, STATUS_MISSING_REQUIRED, STATUS_PARTIAL, iter_leaf_fields


DIMENSION_MARKERS = (
    "diametre",
    "diameter",
    "longueur",
    "length",
    "largeur",
    "width",
    "hauteur",
    "height",
    "epaisseur",
    "thickness",
    "alesage",
    "bore",
    "course",
    "stroke",
    "rayon",
    "radius",
    "entraxe",
    "section",
    "axe_x",
    "x_",
    "y_",
    "z_",
)

EFFORT_MARKERS = (
    "couple",
    "torsion",
    "force",
    "effort",
    "pression",
    "contrainte",
    "sigma",
    "tau",
    "von_mises",
    "marge",
    "temperature",
    "pertes",
    "courant",
    "tension",
    "puissance",
    "rpm",
)


def is_numeric_backend_value(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def infer_unit(path: str) -> str | None:
    low = path.lower()
    suffixes = {
        "_mm": "mm",
        "_m": "m",
        "_nm": "Nm",
        "_pa": "Pa",
        "_mpa": "MPa",
        "_w": "W",
        "_kw": "kW",
        "_v": "V",
        "_a": "A",
        "_kg": "kg",
        "_c": "degC",
        "_k": "K",
    }
    for suffix, unit in suffixes.items():
        if low.endswith(suffix):
            return unit
    return None


def collect_numeric_fields(report: Mapping[str, Any], *, markers: Sequence[str] = DIMENSION_MARKERS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, value in iter_leaf_fields(report):
        low = path.lower()
        if not is_numeric_backend_value(value):
            continue
        if not any(marker in low for marker in markers):
            continue
        rows.append(
            {
                "path": path,
                "label": path.split(".")[-1],
                "value": value,
                "unit": infer_unit(path),
                "status": STATUS_PARTIAL,
                "source": "backend",
                "confidence": "untraced_report_value",
                "required": False,
            }
        )
    return rows


def classify_dimension_fields(fields: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {"lengths": [], "diameters": [], "thicknesses": [], "positions": [], "other": []}
    for item in fields:
        row = dict(item)
        low = str(row.get("path") or row.get("label") or "").lower()
        if "diametre" in low or "diameter" in low or "alesage" in low or "bore" in low:
            groups["diameters"].append(row)
        elif "epaisseur" in low or "thickness" in low:
            groups["thicknesses"].append(row)
        elif low.split(".")[-1].startswith(("x_", "y_", "z_")) or "axe_x" in low:
            groups["positions"].append(row)
        elif (
            "longueur" in low
            or "length" in low
            or "largeur" in low
            or "width" in low
            or "course" in low
            or "height" in low
            or "hauteur" in low
            or "entraxe" in low
        ):
            groups["lengths"].append(row)
        else:
            groups["other"].append(row)
    return groups


def _piece_requirements(piece_name: str) -> tuple[str, ...]:
    low = piece_name.lower()
    if "vis" in low:
        return ("length", "diameter")
    if "roulement" in low:
        return ("length", "diameter")
    if "coussinet" in low:
        return ("length", "diameter")
    if "joint" in low:
        return ("diameter", "thickness_or_section")
    if "couvercle" in low:
        return ("diameter", "thickness_or_section")
    if "deplaceur" in low:
        return ("length", "diameter")
    if any(token in low for token in ("arbre", "vilebrequin", "vilbrequin", "shaft")):
        return ("length_or_positions", "diameter")
    if "cylindre" in low:
        return ("length", "diameter")
    if "piston" in low:
        return ("length", "diameter")
    if "bielle" in low:
        return ("length", "diameter")
    if any(token in low for token in ("batterie", "pack", "boitier")):
        return ("any_dimension",)
    return ("any_dimension",)


def evaluate_geometry_readiness(piece_name: str, report: Mapping[str, Any]) -> dict[str, Any]:
    fields = collect_numeric_fields(report, markers=DIMENSION_MARKERS)
    groups = classify_dimension_fields(fields)
    missing: list[dict[str, Any]] = []

    for req in _piece_requirements(piece_name):
        ok = False
        if req == "any_dimension":
            ok = bool(fields)
        elif req == "length_or_positions":
            ok = bool(groups["lengths"] or groups["positions"])
        elif req == "length":
            ok = bool(groups["lengths"] or groups["positions"])
        elif req == "diameter":
            ok = bool(groups["diameters"])
        elif req == "thickness_or_section":
            ok = bool(groups["thicknesses"] or groups["other"])
        if not ok:
            missing.append(
                {
                    "path": req,
                    "label": req,
                    "value": None,
                    "unit": None,
                    "status": STATUS_MISSING_REQUIRED,
                    "source": "backend",
                    "required": True,
                    "reason": "Donnee geometrique backend absente.",
                }
            )

    status = STATUS_AVAILABLE if fields and not missing else STATUS_PARTIAL if fields else STATUS_MISSING_REQUIRED
    return {
        "status": status,
        "fields": fields,
        "groups": groups,
        "missing_fields": missing,
        "actions": ["Completer les cotes backend requises pour cette piece."] if missing else [],
    }


def evaluate_chart_readiness(charts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    usable_statuses = {"available", "computed", "derived", "validated_by_optimization"}
    available = [
        dict(chart)
        for chart in charts
        if isinstance(chart, Mapping)
        and str(chart.get("status") or "").lower() in usable_statuses
        and any(isinstance(series, Mapping) and series.get("points") for series in chart.get("series", []) or [])
    ]
    if available:
        return {"status": STATUS_AVAILABLE, "missing_fields": [], "actions": []}
    if charts:
        return {
            "status": STATUS_PARTIAL,
            "missing_fields": [{"path": "mechanical_graphs.graphiques", "reason": "Series presentes mais statut non exploitable comme graphe valide."}],
            "actions": ["Verifier les statuts et traces des graphes backend."],
        }
    return {
        "status": STATUS_MISSING_REQUIRED,
        "missing_fields": [{"path": "mechanical_graphs.graphiques", "reason": "Aucune serie de points backend disponible."}],
        "actions": ["Generer mechanical_graphs cote backend."],
    }


__all__ = [
    "DIMENSION_MARKERS",
    "EFFORT_MARKERS",
    "classify_dimension_fields",
    "collect_numeric_fields",
    "evaluate_chart_readiness",
    "evaluate_geometry_readiness",
    "infer_unit",
    "is_numeric_backend_value",
]
