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

from typing import Any, Dict, Mapping, Sequence

from frontend.ensemble.missing_data import collect_numeric_fields, evaluate_geometry_readiness
from frontend.ensemble.piece_data_adapter import STATUS_AVAILABLE, STATUS_MISSING_REQUIRED, STATUS_PARTIAL, safe_dict


_FEATURE_MARKERS = (
    "diametre",
    "diameter",
    "longueur",
    "length",
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
    "rainure",
    "gorge",
    "groove",
    "segment",
    "jupe",
    "skirt",
    "tete",
    "head",
    "calotte",
    "crown",
    "petite_tete",
    "grande_tete",
    "small_end",
    "big_end",
    "fut",
    "beam",
    "portee",
    "palier",
    "journal",
    "taraud",
    "thread",
    "filet",
    "maneton",
    "crankpin",
    "tourillon",
    "contrepoids",
    "counterweight",
    "excentration",
    "offset",
    "squeeze",
    "stretch",
    "ecrasement",
    "allongement",
    "jeu",
    "clearance",
    "zone_chaude",
    "zone_froide",
    "hot",
    "cold",
    "bride",
    "flange",
    "percage",
    "trou",
    "hole",
    "vis",
    "bolt",
    "precharge",
    "preload",
)


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


def _field_signature(field: Mapping[str, Any]) -> tuple[str, Any]:
    return (str(field.get("path") or field.get("label") or ""), field.get("value"))


def _merge_fields(*field_lists: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()
    for fields in field_lists:
        for field in fields:
            row = dict(field)
            sig = _field_signature(row)
            if sig in seen:
                continue
            seen.add(sig)
            out.append(row)
    return out


def _field_text(field: Mapping[str, Any]) -> str:
    return str(field.get("path") or field.get("label") or "").lower()


def _matches(field: Mapping[str, Any], tokens: Sequence[str]) -> bool:
    text = _field_text(field)
    return any(str(token).lower() in text for token in tokens)


def _has_positive_value(field: Mapping[str, Any]) -> bool:
    value = field.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return float(value) > 0.0


def _feature_fields(fields: Sequence[Mapping[str, Any]], tokens: Sequence[str], *, positive: bool = True) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for field in fields:
        if not _matches(field, tokens):
            continue
        if positive and not _has_positive_value(field):
            continue
        matches.append(
            {
                "path": field.get("path"),
                "label": _label(field),
                "value": field.get("value"),
                "unit": field.get("unit"),
                "display_mm": _field_mm(field),
                "status": field.get("status"),
                "source": "backend",
            }
        )
    return matches


def _make_feature(
    feature_type: str,
    label: str,
    fields: Sequence[Mapping[str, Any]],
    tokens: Sequence[str],
    *,
    positive: bool = True,
) -> dict[str, Any] | None:
    used = _feature_fields(fields, tokens, positive=positive)
    if not used:
        return None
    return {
        "type": feature_type,
        "label": label,
        "source": "backend",
        "schematic": True,
        "final_geometry": False,
        "fields": used,
    }


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


def _thicknesses_mm(groups: Mapping[str, list[dict[str, Any]]]) -> list[float]:
    values = [_field_mm(item) for item in groups.get("thicknesses", [])]
    return [v for v in values if v is not None and v > 0]


def _make_sections(piece_name: str, groups: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    positions = _sorted_positions_mm(groups)
    if len(positions) < 2:
        thicknesses = _thicknesses_mm(groups)
        if thicknesses:
            positions = [0.0, max(thicknesses)]
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
    if "joint" in low and "piston" in low:
        return "seal_ring_envelope"
    if any(token in low for token in ("vilebrequin", "vilbrequin")):
        return "crankshaft_schematic"
    if "arbre_piston" in low:
        return "shaft_stepped"
    if "deplaceur" in low:
        return "annular_displacer_envelope"
    if any(token in low for token in ("pignon", "crabot", "baladeur")):
        return "disk_or_gear_envelope"
    if "roulement" in low:
        return "bearing_ring_envelope"
    if any(token in low for token in ("stator", "rotor", "alternateur", "moteur_electrique", "bobine")):
        return "electromagnetic_cylindrical_envelope"
    if any(token in low for token in ("carter", "bloc", "culasse", "couvercle")):
        return "housing_envelope"
    if any(token in low for token in ("busbar", "busbars")):
        return "flat_conductor_envelope"
    if any(token in low for token in ("bms", "tms")):
        return "electronics_box_envelope"
    if "ventilateur" in low:
        return "fan_disk_envelope"
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
    return "dimensioned_envelope"


def _sketch_style_for_piece(piece_name: str) -> str:
    low = piece_name.lower()
    if "joint" in low and "piston" in low:
        return "seal_groove_cross_section"
    if any(token in low for token in ("vilebrequin", "vilbrequin")):
        return "crankshaft_crankpin_journals_schematic"
    if "arbre_piston" in low:
        return "piston_pin_longitudinal_section"
    if "deplaceur" in low:
        return "displacer_tube_longitudinal_section"
    if "couvercle_cylindre" in low:
        return "cylinder_cover_flange_section"
    if "cylindre" in low:
        return "cylinder_longitudinal_section"
    if "piston" in low:
        return "piston_longitudinal_section"
    if "bielle" in low:
        return "connecting_rod_centerline_schematic"
    return "dimensioned_schematic"


def _render_profile_for_piece(piece_name: str) -> str:
    low = piece_name.lower()
    if "joint" in low and "piston" in low:
        return "joint_piston"
    if any(token in low for token in ("vilebrequin", "vilbrequin")):
        return "vilebrequin"
    if "arbre_piston" in low:
        return "arbre_piston"
    if "deplaceur" in low:
        return "deplaceur"
    if "couvercle_cylindre" in low:
        return "couvercle_cylindre"
    if "cylindre" in low:
        return "cylindre"
    if "piston" in low:
        return "piston"
    if "bielle" in low:
        return "bielle"
    return "generic"


def _specialized_features(piece_name: str, fields: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    profile = _render_profile_for_piece(piece_name)
    specs: dict[str, list[tuple[str, str, tuple[str, ...]]]] = {
        "piston": [
            ("piston_outer_diameter", "Diametre exterieur piston", ("diametre_exterieur", "diametre_nominal", "diametre_piston", "outer_diameter", "alesage", "bore")),
            ("piston_height", "Hauteur piston", ("hauteur_piston", "hauteur", "height")),
            ("piston_head", "Tete / calotte", ("tete", "head", "calotte", "crown")),
            ("piston_skirt", "Jupe piston", ("jupe", "skirt")),
            ("ring_groove", "Rainure de joint/segment", ("rainure", "gorge", "groove", "segment")),
            ("pin_interface", "Interface axe piston", ("axe_piston", "diametre_axe")),
        ],
        "cylindre": [
            ("cylinder_bore", "Diametre interieur / alesage", ("diametre_interieur", "inner_diameter", "alesage", "bore")),
            ("cylinder_outer_diameter", "Diametre exterieur cylindre", ("diametre_exterieur", "outer_diameter")),
            ("cylinder_wall_thickness", "Epaisseur paroi", ("epaisseur", "wall", "thickness")),
            ("useful_length", "Longueur utile", ("longueur_utile", "longueur_cylindre", "height", "hauteur")),
            ("flange", "Bride", ("bride", "flange")),
            ("bolt_holes", "Percages / vis", ("percage", "trou", "hole", "vis", "bolt")),
        ],
        "bielle": [
            ("small_end", "Petite tete", ("petite_tete", "small_end", "diametre_axe_piston")),
            ("big_end", "Grande tete", ("grande_tete", "big_end", "diametre_maneton", "maneton")),
            ("center_distance", "Entraxe", ("entraxe", "longueur_bielle")),
            ("beam_section", "Fut / section", ("fut", "corps", "beam", "section")),
        ],
        "arbre_piston": [
            ("shaft_diameter", "Diametre arbre piston", ("diametre_exterieur", "diametre_nominal", "diametre_axe_piston", "diametre_m")),
            ("hollow_bore", "Alesage interne", ("diametre_interieur", "fut_int", "hollow", "evid")),
            ("bearing_journal", "Portee / palier", ("portee", "palier", "coussinet", "teton", "journal")),
            ("thread", "Taraudage / filetage", ("taraud", "thread", "filet")),
        ],
        "vilebrequin": [
            ("crankpin", "Maneton", ("maneton", "crankpin")),
            ("main_journal", "Tourillon principal", ("tourillon", "journal_principal", "main_journal")),
            ("counterweight", "Contrepoids", ("contrepoids", "counterweight")),
            ("crank_offset", "Excentration / rayon manivelle", ("excentration", "offset", "rayon_manivelle", "crank_radius", "course")),
        ],
        "joint_piston": [
            ("seal_inner_diameter", "Diametre interieur joint", ("diametre_interieur_joint", "diametre_interieur", "inner_diameter")),
            ("seal_section", "Section joint", ("section", "epaisseur", "thickness", "corde", "cord")),
            ("squeeze", "Squeeze", ("squeeze", "ecrasement")),
            ("stretch", "Stretch", ("stretch", "allongement")),
            ("groove", "Gorge / rainure", ("gorge", "rainure", "groove")),
        ],
        "deplaceur": [
            ("annular_body", "Corps annulaire", ("diametre_exterieur", "diametre_interieur", "tube", "annulaire")),
            ("total_length", "Longueur totale", ("longueur_totale", "longueur_deplaceur", "height", "hauteur")),
            ("hot_zone", "Zone chaude", ("zone_chaude", "chaude", "hot")),
            ("cold_zone", "Zone froide", ("zone_froide", "froide", "cold")),
            ("radial_clearance", "Jeu radial", ("jeu_radial", "clearance", "jeu")),
        ],
        "couvercle_cylindre": [
            ("cover_flange", "Couvercle / bride", ("couvercle", "bride", "flange", "diametre_bride", "diametre_ouverture")),
            ("bolt_holes", "Vis / percages", ("vis", "screw", "bolt", "percage", "trou", "hole")),
            ("preload", "Precharge", ("precharge", "preload")),
            ("convection_area", "Convection", ("convection", "surface_echange", "surface_convective")),
        ],
    }
    features = []
    for feature_type, label, tokens in specs.get(profile, []):
        feature = _make_feature(feature_type, label, fields, tokens)
        if feature is not None:
            features.append(feature)
    return features


def _first_named_mm(fields: list[dict[str, Any]], tokens: tuple[str, ...]) -> float | None:
    for item in fields:
        label = str(item.get("path") or item.get("label") or "").lower()
        if any(token in label for token in tokens):
            value = _field_mm(item)
            if value is not None and value > 0:
                return value
    return None


def _make_outline_2d(piece_name: str, groups: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    low = piece_name.lower()
    fields = []
    for values in groups.values():
        fields.extend(values)
    width = _first_named_mm(fields, ("largeur", "width", "y_", "diametre", "diameter", "alesage", "bore"))
    height = _first_named_mm(fields, ("hauteur", "height", "z_", "epaisseur", "thickness", "longueur", "length", "x_"))
    length = _first_named_mm(fields, ("longueur", "length", "x_", "entraxe"))
    if any(token in low for token in ("batterie", "pack", "boitier", "bms", "tms", "busbar", "busbars", "carter", "bloc", "culasse")):
        w = length or width
        h = width if length is not None else height
        if w is not None and h is not None:
            return {"type": "rectangle_from_backend_dimensions", "width_mm": w, "height_mm": h, "source": "backend"}
    return {}


def build_generic_sketch_contract(piece_name: str, piece_report: Mapping[str, Any]) -> Dict[str, Any]:
    data = safe_dict(piece_report)
    readiness = evaluate_geometry_readiness(piece_name, data)
    groups = readiness["groups"]
    sections = _make_sections(piece_name, groups)
    outline = _make_outline_2d(piece_name, groups)
    render_fields = _merge_fields(readiness["fields"], collect_numeric_fields(data, markers=_FEATURE_MARKERS))
    features = _specialized_features(piece_name, render_fields)
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
        "render_profile": _render_profile_for_piece(piece_name),
        "sketch_style": _sketch_style_for_piece(piece_name),
        "unites": "mm",
        "axes": [{"id": "axe_principal", "from": [0.0, 0.0], "to": [sections[-1]["x1_mm"], 0.0]}] if sections else [],
        "segments": sections,
        "outline_2d": outline,
        "features": features,
        "cotes": dimensions,
        "schematic": True,
        "final_geometry": False,
    }

    if readiness["status"] == STATUS_MISSING_REQUIRED:
        status = STATUS_MISSING_REQUIRED
    elif sections or outline:
        status = STATUS_AVAILABLE if not readiness["missing_fields"] else STATUS_PARTIAL
    elif len(dimensions) >= 2:
        status = STATUS_PARTIAL
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
        "feature_fields": render_fields,
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
    outline = _make_outline_2d(piece_name, groups)
    render_fields = _merge_fields(readiness["fields"], collect_numeric_fields(data, markers=_FEATURE_MARKERS))
    features = _specialized_features(piece_name, render_fields)
    geometry = {
        "piece": piece_name,
        "primitive": _primitive_for_piece(piece_name),
        "render_profile": _render_profile_for_piece(piece_name),
        "view_style": _sketch_style_for_piece(piece_name),
        "axis": "X",
        "sections": sections,
        "outline_2d": outline,
        "features": features,
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

    if readiness["status"] == STATUS_MISSING_REQUIRED:
        status = STATUS_MISSING_REQUIRED
    elif readiness["status"] == STATUS_AVAILABLE and geometry["dimensions"]:
        status = STATUS_AVAILABLE
    elif geometry["dimensions"]:
        status = STATUS_PARTIAL
    else:
        status = STATUS_MISSING_REQUIRED
    return {
        "id": f"{piece_name}_3d_indicative",
        "type": "view_3d_indicative",
        "status": status,
        "title": f"Vue 3D indicative - {piece_name}",
        "mesh_available": False,
        "json_geometry": geometry,
        "schematic": True,
        "final_geometry": False,
        "solidworks_ready": False,
        "quality": "dimensioned_schematic" if status == STATUS_AVAILABLE else "partial_schematic" if status == STATUS_PARTIAL else "missing_geometry",
        "warning": "Vue indicative, pas STEP, pas modele final.",
        "used_fields": readiness["fields"],
        "feature_fields": render_fields,
        "missing_fields": readiness["missing_fields"],
        "dependency": "PyVista optionnel ; JSON geometrique disponible si les cotes backend existent.",
        "source": "frontend/main.py -> backend",
    }


def build_sketch_figure(sketch_contract: Mapping[str, Any]) -> Any:
    """Construit une figure Matplotlib depuis geometry_json, sans inventer de cote."""
    import matplotlib.pyplot as plt

    geometry = safe_dict(sketch_contract.get("geometry_json"))
    sections = geometry.get("segments") or []
    outline = safe_dict(geometry.get("outline_2d"))
    features = [item for item in (geometry.get("features") or []) if isinstance(item, Mapping)]
    if not sections and not outline:
        raise ValueError("Croquis indisponible : aucune section ou enveloppe cotee backend.")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.set_aspect("equal", adjustable="box")
    ax.axhline(0, color="black", linestyle="--", linewidth=0.8)
    if sections:
        for section in sections:
            x0 = float(section["x0_mm"])
            x1 = float(section["x1_mm"])
            radius = float(section["diameter_mm"]) / 2.0
            ax.add_patch(plt.Rectangle((x0, -radius), x1 - x0, 2 * radius, fill=False, edgecolor="black", linewidth=1.2))
            ax.text((x0 + x1) / 2.0, radius + 3.0, f"D {2 * radius:.2f} mm", ha="center", fontsize=8)
            ax.text((x0 + x1) / 2.0, -radius - 6.0, f"L {x1 - x0:.2f} mm", ha="center", fontsize=8)
    else:
        width = float(outline["width_mm"])
        height = float(outline["height_mm"])
        ax.add_patch(plt.Rectangle((0.0, 0.0), width, height, fill=False, edgecolor="black", linewidth=1.2))
        ax.text(width / 2.0, height + max(height * 0.08, 2.0), f"L {width:.2f} mm", ha="center", fontsize=8)
        ax.text(width + max(width * 0.03, 2.0), height / 2.0, f"H {height:.2f} mm", va="center", fontsize=8)
    for idx, feature in enumerate(features[:8]):
        label = str(feature.get("label") or feature.get("type") or "feature")
        ax.text(0.01, 0.95 - idx * 0.055, label, transform=ax.transAxes, fontsize=7, va="top", color="#444444")
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
