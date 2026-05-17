from __future__ import annotations

"""Graphiques mecaniques de pre-verification STHO-ME.

Les graphiques sont des donnees JSON. Ce module ne produit pas d'image et ne
valide pas SolidWorks ; il expose des courbes analytiques tracees depuis les
valeurs deja calculees par le backend.
"""

import math
from typing import Any, Mapping

from backend.ensemble import calcul_stho_me as phys
from backend.ensemble import materiaux as matlib


STATUS_AVAILABLE = "available"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing_required"


def generer_graphiques_mecaniques(
    rapport: dict,
    *,
    strict: bool = True,
) -> dict:
    data = rapport if isinstance(rapport, dict) else {}
    context = _extract_context(data)
    graphs = [
        _graph_diametre_arbre_vs_contrainte(context),
        _graph_couple_vs_diametre_min(context),
        _graph_rpm_vs_vitesse_piston(context),
        _graph_alesage_course_vs_cylindree(context),
        _graph_puissance_vs_couple(context),
        _graph_courant_bus_vs_tension(context),
        _graph_pertes_joule_vs_courant(context),
    ]
    available = [g for g in graphs if g["status"] == STATUS_AVAILABLE]
    partial = [g for g in graphs if g["status"] == STATUS_PARTIAL]
    return {
        "status": STATUS_AVAILABLE if available else (STATUS_PARTIAL if partial else STATUS_MISSING),
        "graphs_available": len(available),
        "graphs_partial": len(partial),
        "graphs_missing": len([g for g in graphs if g["status"] == STATUS_MISSING]),
        "strict": bool(strict),
        "context": context,
        "graphiques": graphs,
        "notes": [
            "Graphiques analytiques de pre-verification, pas une simulation elements finis.",
            "Les materiaux issus des contraintes/profils restent des candidats tant qu'ils ne sont pas verrouilles.",
        ],
    }


def _graph_diametre_arbre_vs_contrainte(context: Mapping[str, Any]) -> dict:
    torque = _num(context.get("couple_moteur_thermique_nm"))
    materials = _material_rows(context)
    missing = _missing({"couple_moteur_thermique_nm": torque, "materiaux": materials})
    if missing:
        return _graph_missing("diametre_arbre_vs_contrainte_torsion", "Contrainte torsion selon diametre arbre", missing)

    series = []
    markers = []
    diameters = _diameter_range_mm(context, torque, materials)
    torsion_points = [{"x": d_mm, "y": phys.contrainte_torsion(torque, d_mm / 1000.0) / 1e6} for d_mm in diameters]
    series.append({"name": "torsion", "points": torsion_points, "formula": "tau = 16*T/(pi*d^3)"})
    for material in materials:
        tau_adm = _num(material.get("tau_admissible_pa"))
        if tau_adm is None:
            continue
        series.append(
            {
                "name": f"tau admissible - {material['cle']}",
                "points": [{"x": d_mm, "y": tau_adm / 1e6} for d_mm in diameters],
                "material_status": material.get("status"),
            }
        )
        d_min_m = phys.diametre_arbre_torsion(torque, tau_adm)
        markers.append(
            {
                "name": f"diametre minimum {material['cle']}",
                "x": d_min_m * 1000.0,
                "y": tau_adm / 1e6,
                "unit": "mm/MPa",
                "status": material.get("status"),
            }
        )
    return _graph(
        "diametre_arbre_vs_contrainte_torsion",
        "Contrainte de torsion selon diametre d'arbre",
        "Diametre arbre (mm)",
        "Contrainte torsion (MPa)",
        series,
        markers=markers,
        interpretation="Choisir un diametre situe a droite du marqueur minimum du materiau retenu.",
        dependencies={"couple_moteur_thermique_nm": torque, "materiaux": [m["cle"] for m in materials]},
    )


def _graph_couple_vs_diametre_min(context: Mapping[str, Any]) -> dict:
    torque = _num(context.get("couple_moteur_thermique_nm"))
    materials = _material_rows(context)
    missing = _missing({"couple_moteur_thermique_nm": torque, "materiaux": materials})
    if missing:
        return _graph_missing("couple_vs_diametre_min", "Diametre minimum selon couple", missing)
    max_torque = max(float(torque) * 1.5, 1.0)
    torques = _linspace(max(float(torque) * 0.25, 1.0), max_torque, 24)
    series = []
    markers = []
    for material in materials:
        tau_adm = _num(material.get("tau_admissible_pa"))
        if tau_adm is None:
            continue
        points = [{"x": t, "y": phys.diametre_arbre_torsion(t, tau_adm) * 1000.0} for t in torques]
        series.append({"name": material["cle"], "points": points, "material_status": material.get("status")})
        markers.append({"name": f"couple design - {material['cle']}", "x": torque, "y": phys.diametre_arbre_torsion(torque, tau_adm) * 1000.0})
    return _graph(
        "couple_vs_diametre_min",
        "Diametre minimum d'arbre selon couple",
        "Couple (Nm)",
        "Diametre minimum (mm)",
        series,
        markers=markers,
        interpretation="Courbe issue de la torsion pure, a completer par flexion/fatigue et details de clavette.",
        dependencies={"couple_moteur_thermique_nm": torque},
    )


def _graph_rpm_vs_vitesse_piston(context: Mapping[str, Any]) -> dict:
    stroke = _num(context.get("course_m"))
    rpm = _num(context.get("rpm_moteur"))
    missing = _missing({"course_m": stroke, "rpm_moteur": rpm})
    if missing:
        return _graph_missing("rpm_vs_vitesse_piston", "Vitesse piston selon regime", missing)
    rpm_max = max(rpm, 1.0) * 1.4
    rpms = _linspace(max(500.0, rpm_max / 8.0), rpm_max, 30)
    points = [{"x": r, "y": phys.vitesse_piston(stroke, r)} for r in rpms]
    series = [{"name": "vitesse piston", "points": points, "formula": "Up = 2*S*N/60"}]
    limit = _num(context.get("vitesse_piston_max_ms"))
    if limit is not None:
        series.append({"name": "limite CDC", "points": [{"x": r, "y": limit} for r in rpms]})
    markers = [{"name": "point design", "x": rpm, "y": phys.vitesse_piston(stroke, rpm)}] if rpm is not None else []
    return _graph(
        "rpm_vs_vitesse_piston",
        "Vitesse piston selon regime",
        "Regime (rpm)",
        "Vitesse piston (m/s)",
        series,
        markers=markers,
        interpretation="Verifier que le point de regime reste sous la limite CDC si elle existe.",
        dependencies={"course_m": stroke, "rpm_moteur": rpm},
    )


def _graph_alesage_course_vs_cylindree(context: Mapping[str, Any]) -> dict:
    bore = _num(context.get("alesage_m"))
    stroke = _num(context.get("course_m"))
    n_cyl = _num(context.get("nombre_cylindres"))
    ratio_min = _num(context.get("ratio_course_alesage_min"))
    ratio_max = _num(context.get("ratio_course_alesage_max"))
    missing = _missing({"alesage_m": bore, "course_m": stroke, "nombre_cylindres": n_cyl, "ratio_course_alesage_min": ratio_min, "ratio_course_alesage_max": ratio_max})
    if missing:
        return _graph_missing("alesage_course_vs_cylindree", "Cylindree selon alesage/course", missing)
    ratios = _linspace(ratio_min, ratio_max, 24)
    points = []
    for ratio in ratios:
        b = bore
        s = b * ratio
        vd = phys.volume_balayage(b, s) * int(n_cyl)
        points.append({"x": ratio, "y": vd * 1e6})
    marker_y = phys.volume_balayage(bore, stroke) * int(n_cyl) * 1e6
    return _graph(
        "alesage_course_vs_cylindree",
        "Cylindree selon ratio course/alesage",
        "Ratio course/alesage",
        "Cylindree totale (cc)",
        [{"name": "cylindree", "points": points, "formula": "Vd = pi/4*B^2*S*Ncyl"}],
        markers=[{"name": "point design", "x": stroke / bore, "y": marker_y}],
        interpretation="Courbe indicative autour de l'alesage design pour comparer des ratios course/alesage.",
        dependencies={"alesage_m": bore, "course_m": stroke, "nombre_cylindres": int(n_cyl), "ratio_course_alesage_min": ratio_min, "ratio_course_alesage_max": ratio_max},
    )


def _graph_puissance_vs_couple(context: Mapping[str, Any]) -> dict:
    power = _num(context.get("puissance_moteur_thermique_arbre_w")) or _num(context.get("puissance_sortie_moteur_electrique_w"))
    rpm = _num(context.get("rpm_moteur"))
    missing = _missing({"puissance_moteur_thermique_arbre_w": power, "rpm_moteur": rpm})
    if missing:
        return _graph_missing("puissance_vs_couple", "Couple selon regime pour puissance cible", missing)
    rpm_center = rpm
    rpms = _linspace(max(500.0, rpm_center * 0.4), rpm_center * 1.6, 30)
    points = [{"x": r, "y": phys.couple_moteur(power, phys.pulsation(r))} for r in rpms]
    markers = [{"name": "point design", "x": rpm, "y": phys.couple_moteur(power, phys.pulsation(rpm))}] if rpm is not None else []
    return _graph(
        "puissance_vs_couple",
        "Couple requis selon regime pour puissance cible",
        "Regime (rpm)",
        "Couple (Nm)",
        [{"name": "couple", "points": points, "formula": "T = P/omega"}],
        markers=markers,
        interpretation="Plus le regime augmente, plus le couple requis baisse pour une puissance constante.",
        dependencies={"puissance_w": power, "rpm_moteur": rpm},
    )


def _graph_courant_bus_vs_tension(context: Mapping[str, Any]) -> dict:
    p_bus = _num(context.get("puissance_bus_dc_w"))
    v_bus = _num(context.get("tension_bus_dc_v"))
    missing = _missing({"puissance_bus_dc_w": p_bus, "tension_bus_dc_v": v_bus})
    if missing:
        return _graph_missing("courant_bus_vs_tension", "Courant bus selon tension", missing)
    v_center = v_bus
    voltages = _linspace(max(48.0, v_center * 0.5), max(60.0, v_center * 1.5), 30)
    points = [{"x": v, "y": phys.courant_pack(p_bus, v)} for v in voltages]
    markers = [{"name": "point design", "x": v_bus, "y": phys.courant_pack(p_bus, v_bus)}] if v_bus is not None else []
    return _graph(
        "courant_bus_vs_tension",
        "Courant bus DC selon tension",
        "Tension bus (V)",
        "Courant (A)",
        [{"name": "courant bus", "points": points, "formula": "I = P/U"}],
        markers=markers,
        interpretation="Une tension bus plus elevee reduit le courant pour une puissance donnee.",
        dependencies={"puissance_bus_dc_w": p_bus, "tension_bus_dc_v": v_bus},
    )


def _graph_pertes_joule_vs_courant(context: Mapping[str, Any]) -> dict:
    resistance = _num(context.get("resistance_electrique_ohm"))
    current = _num(context.get("courant_bus_dc_a"))
    missing = _missing({"resistance_electrique_ohm": resistance, "courant_bus_dc_a": current})
    if missing:
        return _graph_missing("pertes_joule_vs_courant", "Pertes Joule selon courant", missing)
    i_max = max(current, 1.0) * 1.5
    currents = _linspace(0.0, i_max, 30)
    points = [{"x": i, "y": phys.pertes_joule(resistance, i)} for i in currents]
    markers = [{"name": "point design", "x": current, "y": phys.pertes_joule(resistance, current)}] if current is not None else []
    return _graph(
        "pertes_joule_vs_courant",
        "Pertes Joule selon courant",
        "Courant (A)",
        "Pertes Joule (W)",
        [{"name": "pertes Joule", "points": points, "formula": "Pj = R*I^2"}],
        markers=markers,
        interpretation="Graphique disponible seulement si une resistance electrique reelle est fournie.",
        dependencies={"resistance_electrique_ohm": resistance, "courant_bus_dc_a": current},
    )


def _extract_context(data: Mapping[str, Any]) -> dict[str, Any]:
    resolved = _safe_dict(_get_path(data, "resolution_inconnues.payload_resolu"))
    chain_values = _safe_dict(_get_path(data, "validation_chaine_100kw.valeurs"))
    ctx = {
        "puissance_sortie_moteur_electrique_w": _first_num(chain_values, resolved, data, "puissance_sortie_moteur_electrique_w", "synthese.moteur_electrique.puissance_sortie_w"),
        "puissance_bus_dc_w": _first_num(chain_values, resolved, data, "puissance_bus_dc_design_w", "puissance_bus_dc_w", "P_bus_dc_design_w", "synthese.systeme.P_bus_dc_design_w"),
        "tension_bus_dc_v": _first_num(resolved, data, "tension_bus_dc_v", "V_bus_dc_v", "synthese.systeme.V_bus_dc_v"),
        "courant_bus_dc_a": _first_num(chain_values, resolved, data, "courant_bus_dc_a", "synthese.systeme.courant_bus_dc_a"),
        "puissance_alternateur_electrique_w": _first_num(chain_values, resolved, data, "puissance_alternateur_electrique_w", "synthese.alternateur.puissance_electrique_design_w"),
        "puissance_moteur_thermique_arbre_w": _first_num(chain_values, resolved, data, "puissance_moteur_thermique_arbre_w", "puissance_moteur_requise_W", "synthese.moteur_thermique.puissance_requise_W"),
        "rpm_moteur": _first_num(chain_values, resolved, data, "rpm_moteur_thermique", "rpm_moteur", "rpm_moteur_nominal", "synthese.moteur_thermique.rpm_nominal"),
        "couple_moteur_thermique_nm": _first_num(chain_values, resolved, data, "couple_moteur_thermique_nm", "couple_moteur_nm", "synthese.moteur_thermique.couple_requis_Nm"),
        "couple_alternateur_nm": _first_num(resolved, data, "couple_alternateur_nm", "synthese.alternateur.couple_mecanique_Nm"),
        "alesage_m": _first_num(resolved, data, "alesage_m", "synthese.moteur_thermique.alesage_m"),
        "course_m": _first_num(resolved, data, "course_m", "synthese.moteur_thermique.course_m"),
        "nombre_cylindres": _first_num(resolved, data, "nombre_cylindres", "synthese.moteur_thermique.nombre_cylindres"),
        "ratio_course_alesage_min": _first_num(resolved, data, "contraintes_resolution.ratio_course_alesage_min", "criteres_conception.ratio_course_alesage_min"),
        "ratio_course_alesage_max": _first_num(resolved, data, "contraintes_resolution.ratio_course_alesage_max", "criteres_conception.ratio_course_alesage_max"),
        "vitesse_piston_max_ms": _first_num(resolved, data, "vitesse_piston_max_ms", "criteres_conception.vitesse_piston_max_ms"),
        "resistance_electrique_ohm": _first_num(resolved, data, "resistance_electrique_ohm", "resistance_interne_ohm", "cable.resistance_ohm"),
        "nb_cellules_serie": _first_num(resolved, data, "nb_cellules_serie", "Ns", "synthese.batterie.nb_cellules_serie"),
        "nb_cellules_parallele": _first_num(resolved, data, "nb_cellules_parallele", "Np", "synthese.batterie.nb_cellules_parallele"),
        "materiaux_autorises": _first_list(resolved, data, "contraintes_resolution.materiaux_autorises", "criteres_conception.materiaux_autorises"),
        "materiau_cle": _first_str(resolved, data, "materiau_cle", "materiau", "synthese.materiau.cle"),
    }
    return {k: v for k, v in ctx.items() if v is not None}


def _material_rows(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    keys: list[str] = []
    if isinstance(context.get("materiau_cle"), str):
        keys.append(str(context["materiau_cle"]))
    for key in context.get("materiaux_autorises", []) if isinstance(context.get("materiaux_autorises"), list) else []:
        if isinstance(key, str) and key not in keys:
            keys.append(key)
    rows: list[dict[str, Any]] = []
    for key in keys[:5]:
        if not matlib.existe_materiau(key):
            continue
        try:
            summary = matlib.resume_materiau(key, mode="typique", coef_securite=1.5)
        except Exception:
            continue
        tau = _num(summary.get("tau_admissible_von_mises_pa"))
        if tau is None:
            continue
        rows.append(
            {
                "cle": key,
                "nom": summary.get("nom"),
                "tau_admissible_pa": tau,
                "sigma_admissible_pa": summary.get("sigma_admissible_elastique_pa"),
                "status": "input" if key == context.get("materiau_cle") else "candidate_from_cdc",
                "source": "backend.ensemble.materiaux",
            }
        )
    return rows


def _diameter_range_mm(context: Mapping[str, Any], torque: float, materials: list[Mapping[str, Any]]) -> list[float]:
    mins = []
    for material in materials:
        tau = _num(material.get("tau_admissible_pa"))
        if tau is not None:
            mins.append(phys.diametre_arbre_torsion(torque, tau) * 1000.0)
    center = max(mins) if mins else 40.0
    return _linspace(max(5.0, center * 0.55), center * 1.8, 32)


def _graph(
    graph_id: str,
    title: str,
    x_label: str,
    y_label: str,
    series: list[dict[str, Any]],
    *,
    markers: list[dict[str, Any]] | None = None,
    interpretation: str,
    dependencies: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "id": graph_id,
        "title": title,
        "x_label": x_label,
        "y_label": y_label,
        "series": series,
        "markers": markers or [],
        "status": STATUS_AVAILABLE,
        "missing": [],
        "formula": [s.get("formula") for s in series if s.get("formula")],
        "source": "backend.ensemble.calcul_stho_me",
        "dependencies": dict(dependencies),
        "interpretation": interpretation,
    }


def _graph_missing(graph_id: str, title: str, missing: list[str]) -> dict[str, Any]:
    return {
        "id": graph_id,
        "title": title,
        "x_label": "",
        "y_label": "",
        "series": [],
        "markers": [],
        "status": STATUS_MISSING,
        "missing": missing,
        "formula": [],
        "source": "backend.ensemble.calcul_stho_me",
        "dependencies": {},
        "interpretation": "Graphique indisponible : donnees backend requises absentes.",
    }


def _missing(values: Mapping[str, Any]) -> list[str]:
    return [key for key, value in values.items() if value in (None, [], {})]


def _first_num(*roots_and_paths: Any) -> float | None:
    roots, paths = _split_roots_paths(roots_and_paths)
    for root in roots:
        for path in paths:
            value = _get_path(root, path) if isinstance(root, Mapping) else None
            if _is_num(value):
                return float(value)
    return None


def _first_list(*roots_and_paths: Any) -> list[Any] | None:
    roots, paths = _split_roots_paths(roots_and_paths)
    for root in roots:
        for path in paths:
            value = _get_path(root, path) if isinstance(root, Mapping) else None
            if isinstance(value, list) and value:
                return list(value)
            if isinstance(value, tuple) and value:
                return list(value)
    return None


def _first_str(*roots_and_paths: Any) -> str | None:
    roots, paths = _split_roots_paths(roots_and_paths)
    for root in roots:
        for path in paths:
            value = _get_path(root, path) if isinstance(root, Mapping) else None
            if isinstance(value, str) and value.strip():
                return value
    return None


def _split_roots_paths(args: tuple[Any, ...]) -> tuple[list[Mapping[str, Any]], list[str]]:
    roots: list[Mapping[str, Any]] = []
    paths: list[str] = []
    for item in args:
        if isinstance(item, Mapping) and not paths:
            roots.append(item)
        elif isinstance(item, str):
            paths.append(item)
        elif isinstance(item, (list, tuple)):
            paths.extend(str(x) for x in item)
    return roots, paths


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


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _num(value: Any) -> float | None:
    return float(value) if _is_num(value) else None


def _linspace(start: float, stop: float, count: int) -> list[float]:
    if count <= 1:
        return [float(start)]
    step = (stop - start) / float(count - 1)
    return [float(start + i * step) for i in range(count)]


__all__ = ["generer_graphiques_mecaniques"]
