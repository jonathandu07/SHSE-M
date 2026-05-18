"""
Chemin : frontend/ensemble/cao_rendering.py
But :
    Construire des croquis 2D et vues 3D indicatives depuis les cotes backend.
Pourquoi ce fichier existe :
    Les scripts de pieces doivent produire des supports utiles pour redessiner
    vite dans SolidWorks, tout en refusant les pieces non cotees.
Donnees consommees :
    Rapports backend de piece, dimensions deja calculees, cao_dossier.
Livrables produits :
    Contrats de croquis 2D, geometries JSON de vues 3D et figures Matplotlib
    optionnelles construites depuis les cotes existantes.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.missing_data import evaluate_geometry_readiness
from frontend.ensemble.piece_data_adapter import STATUS_AVAILABLE, STATUS_MISSING_REQUIRED, STATUS_PARTIAL, safe_dict


def _to_mm(value: Any, unit: str | None, path: str = "") -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if unit == "m" or path.lower().endswith("_m"):
        return float(value) * 1000.0
    return float(value)


def _field_mm(field: Mapping[str, Any]) -> float | None:
    return _to_mm(field.get("value"), field.get("unit"), str(field.get("path") or ""))


def _label(field: Mapping[str, Any]) -> str:
    return str(field.get("label") or field.get("path") or "dimension")


def _sorted_positions_mm(groups: Mapping[str, list[dict[str, Any]]]) -> list[float]:
    values = []
    for item in groups.get("positions", []):
        val = _field_mm(item)
        if val is not None:
            values.append(val)
    values = sorted(dict.fromkeys(values))
    if len(values) >= 2:
        return values
    lengths = [_field_mm(item) for item in groups.get("lengths", [])]
    lengths = [v for v in lengths if v is not None and v > 0]
    if lengths:
        return [0.0, max(lengths)]
    return []


def _diameters_mm(groups: Mapping[str, list[dict[str, Any]]]) -> list[float]:
    values = [_field_mm(item) for item in groups.get("diameters", [])]
    return [v for v in values if v is not None and v > 0]


def _make_sections(piece_name: str, groups: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    positions = _sorted_positions_mm(groups)
    diameters = _diameters_mm(groups)
    if len(positions) < 2 or not diameters:
        return []
    sections = []
    for idx, (x0, x1) in enumerate(zip(positions[:-1], positions[1:])):
        diameter = diameters[min(idx, len(diameters) - 1)]
        sections.append({"x0_mm": x0, "x1_mm": x1, "diameter_mm": diameter, "source": "backend"})
    return sections


def _primitive_for_piece(piece_name: str) -> str:
    low = piece_name.lower()
    if any(token in low for token in ("arbre", "vilebrequin", "vilbrequin")):
        return "shaft_stepped"
    if "cylindre" in low:
        return "tube"
    if "piston" in low:
        return "piston_simplifie"
    if "bielle" in low:
        return "rod_simplifiee"
    if any(token in low for token in ("batterie", "pack", "boitier")):
        return "box_envelope"
    if "alternateur" in low or "rotor" in low or "stator" in low:
        return "cylindrical_envelope"
    return "dimensioned_envelope"


def build_generic_sketch_contract(piece_name: str, piece_report: Mapping[str, Any]) -> Dict[str, Any]:
    data = safe_dict(piece_report)
    readiness = evaluate_geometry_readiness(piece_name, data)
    groups = readiness["groups"]
    sections = _make_sections(piece_name, groups)
    dimensions = []
    for field in readiness["fields"]:
        val_mm = _field_mm(field)
        dimensions.append(
            {
                "path": field.get("path"),
                "label": _label(field),
                "value": field.get("value"),
                "unit": field.get("unit"),
                "display_mm": val_mm,
                "source": "backend",
            }
        )

    geometry = {
        "piece": piece_name,
        "plan": "XZ",
        "unites": "mm",
        "axes": [{"id": "axe_principal", "from": [0.0, 0.0], "to": [sections[-1]["x1_mm"], 0.0]}] if sections else [],
        "segments": sections,
        "cotes": dimensions,
    }

    if readiness["status"] == STATUS_MISSING_REQUIRED:
        status = STATUS_MISSING_REQUIRED
    elif sections or len(dimensions) >= 2:
        status = STATUS_AVAILABLE if not readiness["missing_fields"] else STATUS_PARTIAL
    else:
        status = STATUS_PARTIAL

    return {
        "id": f"{piece_name}_sketch_2d",
        "type": "sketch_2d",
        "status": status,
        "title": f"Croquis cote - {piece_name}",
        "figure_path": None,
        "geometry_json": geometry,
        "used_fields": readiness["fields"],
        "missing_fields": readiness["missing_fields"],
        "solidworks_dimensions": dimensions,
        "actions": readiness["actions"],
        "source": "frontend/main.py -> backend",
    }


def build_generic_view_3d_contract(piece_name: str, piece_report: Mapping[str, Any]) -> Dict[str, Any]:
    data = safe_dict(piece_report)
    readiness = evaluate_geometry_readiness(piece_name, data)
    groups = readiness["groups"]
    sections = _make_sections(piece_name, groups)
    geometry = {
        "piece": piece_name,
        "primitive": _primitive_for_piece(piece_name),
        "axis": "X",
        "sections": sections,
        "dimensions": [
            {
                "path": field.get("path"),
                "value": field.get("value"),
                "unit": field.get("unit"),
                "display_mm": _field_mm(field),
                "source": "backend",
            }
            for field in readiness["fields"]
        ],
    }

    status = STATUS_AVAILABLE if readiness["status"] != STATUS_MISSING_REQUIRED and geometry["dimensions"] else STATUS_MISSING_REQUIRED
    return {
        "id": f"{piece_name}_3d_indicative",
        "type": "view_3d_indicative",
        "status": status,
        "title": f"Vue 3D indicative - {piece_name}",
        "mesh_available": False,
        "json_geometry": geometry,
        "warning": "Vue indicative, pas STEP, pas modele final.",
        "used_fields": readiness["fields"],
        "missing_fields": readiness["missing_fields"],
        "dependency": "PyVista optionnel ; JSON geometrique disponible si les cotes backend existent.",
        "source": "frontend/main.py -> backend",
    }


def build_sketch_figure(sketch_contract: Mapping[str, Any]) -> Any:
    """Construit une figure Matplotlib depuis geometry_json, sans inventer de cote."""
    import matplotlib.pyplot as plt

    geometry = safe_dict(sketch_contract.get("geometry_json"))
    sections = geometry.get("segments") or []
    if not sections:
        raise ValueError("Croquis indisponible : aucune section cotee backend.")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.set_aspect("equal", adjustable="box")
    ax.axhline(0, color="black", linestyle="--", linewidth=0.8)
    for section in sections:
        x0 = float(section["x0_mm"])
        x1 = float(section["x1_mm"])
        radius = float(section["diameter_mm"]) / 2.0
        ax.add_patch(plt.Rectangle((x0, -radius), x1 - x0, 2 * radius, fill=False, edgecolor="black", linewidth=1.2))
        ax.text((x0 + x1) / 2.0, radius + 3.0, f"D {2 * radius:.2f} mm", ha="center", fontsize=8)
        ax.text((x0 + x1) / 2.0, -radius - 6.0, f"L {x1 - x0:.2f} mm", ha="center", fontsize=8)
    ax.set_title(str(sketch_contract.get("title") or "Croquis cote"))
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Rayon (mm)")
    ax.autoscale_view()
    fig.tight_layout()
    return fig


__all__ = [
    "build_generic_sketch_contract",
    "build_generic_view_3d_contract",
    "build_sketch_figure",
]
