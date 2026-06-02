from __future__ import annotations

"""Dossier de definition mecanique STHO-ME.

Ce module produit un dossier JSON exploitable pour le dessin industriel, la
modelisation, l'assemblage et la simulation. Il ne genere aucun STEP et ne
declare jamais un dossier comme complet sans donnees de definition.
"""

from typing import Any, Mapping

from backend.modules.systeme.mechanical_graphs import generer_graphiques_mecaniques


def construire_dossier_cao_sthome(
    rapport: dict,
    *,
    strict: bool = True,
) -> dict:
    data = rapport if isinstance(rapport, dict) else {}
    mechanical_graphs = data.get("mechanical_graphs")
    if not isinstance(mechanical_graphs, Mapping):
        mechanical_graphs = generer_graphiques_mecaniques(data, strict=strict)
    graphs = [dict(g) for g in mechanical_graphs.get("graphiques", []) if isinstance(g, Mapping)]
    context = _safe_dict(mechanical_graphs.get("context"))

    actions: list[dict[str, Any]] = []
    pieces: dict[str, Any] = {}
    sketches: list[dict[str, Any]] = []
    views_3d: list[dict[str, Any]] = []

    shaft = _build_shaft_piece(context, graphs, actions)
    if shaft:
        pieces["arbre_moteur"] = shaft
        sketches.extend(shaft.get("croquis_2d", []))
        views_3d.extend(shaft.get("vues_3d", []))

    cylinder = _build_cylinder_piece(context, actions)
    if cylinder:
        pieces["cylindre_simplifie"] = cylinder
        sketches.extend(cylinder.get("croquis_2d", []))
        views_3d.extend(cylinder.get("vues_3d", []))

    piston = _build_piston_piece(context, actions)
    if piston:
        pieces["piston_simplifie"] = piston
        sketches.extend(piston.get("croquis_2d", []))
        views_3d.extend(piston.get("vues_3d", []))

    battery = _build_battery_piece(context, actions)
    if battery:
        pieces["batterie_pack_enveloppe"] = battery

    graph_available = any(g.get("status") == "available" for g in graphs)
    sketches_available = any(s.get("statut") in {"exploitable_pour_redessin_solidworks", "partiel_exploitable"} for s in sketches)
    views_available = any(v.get("type") == "3d_indicative" and v.get("status") != "missing_required" for v in views_3d)
    drawing_data_available = bool(_solidworks_values(context, pieces))

    missing_for_solidworks = _missing_for_solidworks(context)
    missing_for_sketches = _unique_missing(sketches)
    missing_for_graphs = sorted({m for g in graphs for m in g.get("missing", []) if isinstance(m, str)})
    mode = _cao_mode(
        sketches_available=sketches_available,
        views_available=views_available,
        graph_available=graph_available,
        drawing_data_available=drawing_data_available,
    )
    resume = {
        "mode": mode,
        "available": False,
        "step_export": False,
        "solidworks_ready": False,
        "sketches_available": sketches_available,
        "views_3d_available": views_available,
        "stress_graphs_available": graph_available,
        "drawing_data_available": drawing_data_available,
        "missing_for_solidworks": missing_for_solidworks,
        "missing_for_sketches": missing_for_sketches,
        "missing_for_stress_graphs": missing_for_graphs,
        "avertissement": "Dossier de definition : aide au dessin et a la modelisation, pas un STEP ni une validation finale.",
    }

    return {
        "mode": mode,
        "resume": resume,
        "pieces": pieces,
        "assemblages": {
            "chaine_moteur_alternateur": {
                "status": "partial" if missing_for_solidworks else "pre_dimensionne",
                "interfaces": {
                    "couple_moteur_nm": context.get("couple_moteur_thermique_nm"),
                    "rpm_moteur": context.get("rpm_moteur"),
                    "rapport_boite_alt": _get_path(data, "validation_chaine_100kw.valeurs.rapport_boite_alt"),
                },
                "missing": missing_for_solidworks,
            }
        },
        "croquis_2d": sketches,
        "vues_3d": views_3d,
        "graphiques": [{"id": g.get("id"), "status": g.get("status"), "title": g.get("title")} for g in graphs],
        "donnees_solidworks": {
            "valeurs_a_reporter": _solidworks_values(context, pieces),
            "step_export": False,
            "solidworks_ready": False,
            "source": "backend.modules.systeme.cao_dossier",
        },
        "inconnues": {
            "missing_for_solidworks": missing_for_solidworks,
            "missing_for_sketches": missing_for_sketches,
            "missing_for_stress_graphs": missing_for_graphs,
        },
        "actions": actions + _actions_from_missing(missing_for_solidworks, missing_for_sketches, missing_for_graphs),
        "mechanical_graphs": mechanical_graphs,
    }


def _build_shaft_piece(context: Mapping[str, Any], graphs: list[Mapping[str, Any]], actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    torque = _num(context.get("couple_moteur_thermique_nm"))
    diameter = _shaft_candidate_diameter_mm(graphs)
    material = _shaft_candidate_material(graphs)
    if torque is None and diameter is None:
        actions.append({"piece": "arbre_moteur", "action": "fournir couple moteur ou diametre d'arbre calcule", "blocking": True})
        return None
    missing = []
    if diameter is None:
        missing.append("diametre_arbre_m")
    for field in ("longueur_arbre_m", "portees_roulements", "clavette"):
        missing.append(field)
    sketch = {
        "id": "arbre_moteur_vue_longitudinale",
        "piece": "arbre_moteur",
        "type": "croquis_2d_cote",
        "plan": "XZ",
        "unites": "mm",
        "geometrie": {
            "segments": [
                {"x0_mm": None, "x1_mm": None, "diameter_mm": diameter, "role": "fut_principal"}
            ],
            "cercles": [
                {"centre": [0, 0], "diameter_mm": diameter, "role": "section_torsion"} if diameter is not None else None
            ],
            "axes": [{"id": "axe_rotation", "orientation": "X"}],
            "cotes": [
                {"nom": "diametre_min_torsion", "valeur": diameter, "unite": "mm", "source": "calcul_stho_me.diametre_arbre_torsion"},
                {"nom": "longueur_totale", "valeur": None, "unite": "mm", "source": None, "missing": True},
            ],
        },
        "annotations": [
            f"Couple transmis: {torque:.3g} Nm" if torque is not None else "Couple transmis manquant",
            f"Materiau candidat: {material}" if material else "Materiau candidat non verrouille",
            "Vue schematique pour preparation a la modelisation ; geometrie partielle.",
        ],
        "source": "calcul analytique torsion",
        "statut": "exploitable_pour_redessin_solidworks" if diameter is not None else "missing_required",
        "missing": missing,
    }
    sketch["geometrie"]["cercles"] = [c for c in sketch["geometrie"]["cercles"] if c is not None]
    view = {
        "id": "arbre_moteur_3d_simplifie",
        "piece": "arbre_moteur",
        "type": "3d_indicative",
        "primitive": "shaft_stepped",
        "axis": "X",
        "dimensions": {"diameter_mm": diameter, "length_mm": None},
        "features": [],
        "annotations": sketch["annotations"],
        "status": "partial" if diameter is not None else "missing_required",
        "missing": ["longueur_arbre_m", "portees_roulements", "clavette"],
        "avertissement": "Vue schematique de preparation a la modelisation ; aucun STEP.",
    }
    return {
        "status": "pre_dimensionne_partiel" if diameter is not None else "missing_required",
        "dimensions": {
            "couple_transmis_nm": torque,
            "diametre_min_torsion_mm": diameter,
            "materiau_candidat": material,
            "longueur_totale_mm": None,
        },
        "croquis_2d": [sketch],
        "vues_3d": [view],
        "missing": missing,
    }


def _build_cylinder_piece(context: Mapping[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    bore = _num(context.get("alesage_m"))
    stroke = _num(context.get("course_m"))
    if bore is None and stroke is None:
        actions.append({"piece": "cylindre_simplifie", "action": "fournir alesage/course pour croquis cylindre", "blocking": False})
        return None
    missing = [name for name, value in {"alesage_m": bore, "course_m": stroke, "epaisseur_paroi_m": None}.items() if value is None]
    sketch = {
        "id": "cylindre_vue_coupe_simplifiee",
        "piece": "cylindre_simplifie",
        "type": "croquis_2d_cote",
        "plan": "XZ",
        "unites": "mm",
        "geometrie": {"segments": [], "cercles": [], "axes": [{"id": "axe_cylindre", "orientation": "Z"}], "cotes": [
            {"nom": "alesage", "valeur": bore * 1000.0 if bore is not None else None, "unite": "mm", "source": "resolution_inconnues"},
            {"nom": "course", "valeur": stroke * 1000.0 if stroke is not None else None, "unite": "mm", "source": "resolution_inconnues"},
            {"nom": "epaisseur_paroi", "valeur": None, "unite": "mm", "missing": True},
        ]},
        "annotations": ["Cylindre simplifie pour dossier de definition.", "Epaisseur paroi a fermer avant modelisation."],
        "source": "resolution_inconnues",
        "statut": "exploitable_pour_redessin_solidworks" if bore is not None and stroke is not None else "partiel_exploitable",
        "missing": missing,
    }
    view = {
        "id": "cylindre_3d_simplifie",
        "piece": "cylindre_simplifie",
        "type": "3d_indicative",
        "primitive": "hollow_cylinder",
        "dimensions": {"bore_mm": bore * 1000.0 if bore is not None else None, "stroke_mm": stroke * 1000.0 if stroke is not None else None, "wall_thickness_mm": None},
        "features": [],
        "annotations": ["Vue schematique de preparation a la modelisation ; aucun STEP."],
        "status": "partial" if bore is None or stroke is None else "available",
        "missing": missing,
        "avertissement": "Vue schematique de preparation a la modelisation ; aucun STEP.",
    }
    return {"status": sketch["statut"], "dimensions": {"alesage_m": bore, "course_m": stroke, "epaisseur_paroi_m": None}, "croquis_2d": [sketch], "vues_3d": [view], "missing": missing}


def _build_piston_piece(context: Mapping[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    bore = _num(context.get("alesage_m"))
    if bore is None:
        return None
    missing = ["hauteur_piston_m", "diametre_axe_piston_m", "segments"]
    sketch = {
        "id": "piston_vue_coupe_simplifiee",
        "piece": "piston_simplifie",
        "type": "croquis_2d_cote",
        "plan": "XZ",
        "unites": "mm",
        "geometrie": {"segments": [], "cercles": [], "axes": [{"id": "axe_piston", "orientation": "Z"}], "cotes": [
            {"nom": "diametre_nominal", "valeur": bore * 1000.0, "unite": "mm", "source": "alesage_m"},
            {"nom": "hauteur_piston", "valeur": None, "unite": "mm", "missing": True},
        ]},
        "annotations": ["Diametre nominal derive de l'alesage backend.", "Hauteur et gorge segments a definir avant modelisation."],
        "source": "resolution_inconnues",
        "statut": "partiel_exploitable",
        "missing": missing,
    }
    return {"status": "partiel_exploitable", "dimensions": {"diametre_nominal_m": bore, "hauteur_piston_m": None}, "croquis_2d": [sketch], "vues_3d": [], "missing": missing}


def _build_battery_piece(context: Mapping[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    ns = _num(context.get("nb_cellules_serie"))
    np = _num(context.get("nb_cellules_parallele"))
    if ns is None and np is None:
        return None
    return {
        "status": "donnees_topologie_disponibles",
        "dimensions": {"nb_cellules_serie": ns, "nb_cellules_parallele": np, "enveloppe_mm": None},
        "missing": ["implantation_cellules", "enveloppe_pack_mm"],
        "notes": ["Topologie electrique exploitable ; enveloppe mecanique a definir."],
    }


def _shaft_candidate_diameter_mm(graphs: list[Mapping[str, Any]]) -> float | None:
    for graph in graphs:
        if graph.get("id") != "diametre_arbre_vs_contrainte_torsion":
            continue
        markers = graph.get("markers")
        if isinstance(markers, list):
            values = [_num(m.get("x")) for m in markers if isinstance(m, Mapping)]
            values = [v for v in values if v is not None]
            if values:
                return max(values)
    return None


def _shaft_candidate_material(graphs: list[Mapping[str, Any]]) -> str | None:
    selected: tuple[float, str] | None = None
    for graph in graphs:
        if graph.get("id") != "diametre_arbre_vs_contrainte_torsion":
            continue
        markers = graph.get("markers")
        if not isinstance(markers, list):
            continue
        for marker in markers:
            if not isinstance(marker, Mapping):
                continue
            diameter = _num(marker.get("x"))
            name = str(marker.get("name", "")).replace("diametre minimum", "").strip()
            if diameter is None or not name:
                continue
            if selected is None or diameter > selected[0]:
                selected = (diameter, name)
    return selected[1] if selected else None


def _solidworks_values(context: Mapping[str, Any], pieces: Mapping[str, Any]) -> dict[str, Any]:
    values = {
        "puissance_sortie_moteur_electrique_w": context.get("puissance_sortie_moteur_electrique_w"),
        "puissance_bus_dc_w": context.get("puissance_bus_dc_w"),
        "couple_moteur_thermique_nm": context.get("couple_moteur_thermique_nm"),
        "rpm_moteur": context.get("rpm_moteur"),
        "alesage_m": context.get("alesage_m"),
        "course_m": context.get("course_m"),
        "nombre_cylindres": context.get("nombre_cylindres"),
    }
    shaft = _safe_dict(pieces.get("arbre_moteur"))
    values["arbre_moteur"] = _safe_dict(shaft.get("dimensions"))
    return {k: v for k, v in values.items() if v not in (None, {}, [])}


def _missing_for_solidworks(context: Mapping[str, Any]) -> list[str]:
    required = {
        "materiau_verrouille": context.get("materiau_cle"),
        "longueurs_arbre": None,
        "portees_roulements": None,
        "clavettes": None,
        "epaisseurs_cylindre": None,
        "details_piston": None,
        "interfaces_boite": None,
    }
    return [key for key, value in required.items() if value is None]


def _unique_missing(sketches: list[Mapping[str, Any]]) -> list[str]:
    out: list[str] = []
    for sketch in sketches:
        for item in sketch.get("missing", []):
            if isinstance(item, str) and item not in out:
                out.append(item)
    return out


def _actions_from_missing(*groups: list[str]) -> list[dict[str, Any]]:
    out = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item in seen:
                continue
            seen.add(item)
            out.append({"champ": item, "action": f"Completer {item} pour avancer vers le dossier de definition.", "apply_automatically": False})
    return out


def _cao_mode(*, sketches_available: bool, views_available: bool, graph_available: bool, drawing_data_available: bool) -> str:
    if sketches_available and views_available:
        return "3d_indicative"
    if sketches_available:
        return "croquis_cotes"
    if drawing_data_available or graph_available:
        return "conceptuel_non_cote"
    return "indisponible"


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    current: Any = data
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


__all__ = ["construire_dossier_cao_sthome"]
