from __future__ import annotations

"""Generation de candidats bornee par le cahier des charges."""

import math
from typing import Any, Dict, List, Mapping

from backend.modules.systeme.status import SOURCE_CDC, STATUS_CANDIDATE_FROM_CDC, STATUS_COMPUTED


def generer_candidates_pour_inconnue(
    *,
    nom: str,
    path: str | None,
    raison: str,
    config: dict[str, Any],
    rapport: dict[str, Any],
    cahier_des_charges: dict[str, Any],
) -> list[Any]:
    from backend.modules.systeme.resolution_inconnues import DonneeCandidate

    out: List[DonneeCandidate] = []
    target = (path or nom or "").lower()

    if "longueur_bielle" in target:
        course = _first_number(config, rapport, "course_m", "synthese.moteur_thermique.course_m")
        rmin = _number(cahier_des_charges.get("ratio_bielle_course_min"))
        rmax = _number(cahier_des_charges.get("ratio_bielle_course_max"))
        if course is not None and rmin is not None and rmax is not None and 0.0 < rmin <= rmax:
            for ratio in _linspace(rmin, rmax, 5):
                out.append(
                    DonneeCandidate(
                        nom=nom,
                        path=path or "pieces.bielle.longueur_bielle_m",
                        valeur=course * ratio,
                        unite="m",
                        source=SOURCE_CDC,
                        statut=STATUS_CANDIDATE_FROM_CDC,
                        raison=(
                            "Longueur de bielle generee depuis la course et l'intervalle "
                            "ratio_bielle_course_min/max du cahier des charges."
                        ),
                        dependances=["course_m", "ratio_bielle_course_min", "ratio_bielle_course_max"],
                        metadata={
                            "ratio_bielle_course": ratio,
                            "borne_min": rmin,
                            "borne_max": rmax,
                            "domaine": {"min": rmin, "max": rmax, "count": 5},
                            "formule": "longueur_bielle_m = course_m * ratio_bielle_course",
                            "score_local": _domain_score(ratio, rmin, rmax),
                            "raison_inconnue": raison,
                        },
                    )
                )

    if target in {"tension_bus_dc_v", "bus_dc.tension_bus_dc_v"} or target.endswith(".tension_bus_dc_v"):
        tension = _number(cahier_des_charges.get("tension_bus_dc_v"))
        if tension is not None:
            out.append(
                DonneeCandidate(
                    nom=nom,
                    path=path or "tension_bus_dc_v",
                    valeur=tension,
                    unite="V",
                    source=SOURCE_CDC,
                    statut=STATUS_CANDIDATE_FROM_CDC,
                    raison="Tension bus DC imposee explicitement par le cahier des charges.",
                    dependances=["cahier_des_charges.tension_bus_dc_v"],
                    metadata={
                        "domaine": {"exact": tension},
                        "formule": "tension_bus_dc_v = cahier_des_charges.tension_bus_dc_v",
                        "score_local": 1.0,
                        "raison_inconnue": raison,
                    },
                )
            )

    if "rapport_vitesse_alt_sur_moteur" in target or "rapport_boite" in target:
        rpm_moteur = _first_number(config, rapport, "vitesse_moteur_thermique_rpm", "rpm_moteur_nominal", "synthese.moteur_thermique.rpm_nominal")
        rpm_alt = _first_number(config, rapport, "vitesse_alternateur_rpm", "rpm_alternateur_cible")
        rmin = _number(cahier_des_charges.get("rapport_boite_min"))
        rmax = _number(cahier_des_charges.get("rapport_boite_max"))
        if rpm_moteur and rpm_alt and rpm_moteur > 0:
            ratio = rpm_alt / rpm_moteur
            if (rmin is None or ratio >= rmin) and (rmax is None or ratio <= rmax):
                out.append(
                    DonneeCandidate(
                        nom=nom,
                        path=path or "rapport_vitesse_alt_sur_moteur",
                        valeur=ratio,
                        unite=None,
                        source="computed",
                        statut=STATUS_COMPUTED,
                        raison="Rapport moteur/alternateur calcule exactement depuis deux regimes connus.",
                        dependances=["vitesse_alternateur_rpm", "vitesse_moteur_thermique_rpm"],
                        metadata={
                            "rapport_boite_min": rmin,
                            "rapport_boite_max": rmax,
                            "domaine": {"min": rmin, "max": rmax},
                            "formule": "rapport = rpm_alternateur / rpm_moteur",
                            "score_local": 1.0,
                        },
                    )
                )

    if target.endswith("nombre_cylindres") or target == "nombre_cylindres":
        values = cahier_des_charges.get("nombres_cylindres_autorises")
        if isinstance(values, (list, tuple)) and values:
            for value in values:
                if isinstance(value, int) and value > 0:
                    out.append(
                        DonneeCandidate(
                            nom=nom,
                            path=path or "nombre_cylindres",
                            valeur=value,
                            unite=None,
                            source=SOURCE_CDC,
                            statut=STATUS_CANDIDATE_FROM_CDC,
                            raison="Nombre de cylindres candidat issu de la liste autorisee CDC.",
                            dependances=["cahier_des_charges.nombres_cylindres_autorises"],
                            metadata={"domaine": list(values), "formule": "selection dans nombres_cylindres_autorises", "score_local": 1.0 / len(values)},
                        )
                    )

    if "rpm" in target or "regime" in target:
        rmin = _first_number({"cdc": cahier_des_charges}, {}, "cdc.rpm_moteur_min", "cdc.rpm_min", "cdc.regime_moteur_min")
        rmax = _first_number({"cdc": cahier_des_charges}, {}, "cdc.rpm_moteur_max", "cdc.rpm_max", "cdc.regime_moteur_max")
        bounds = cahier_des_charges.get("bornes")
        if isinstance(bounds, Mapping):
            for key in (path or nom or "rpm_moteur", "rpm_moteur", "rpm_moteur_nominal"):
                b = bounds.get(key)
                if isinstance(b, Mapping):
                    rmin = _number(b.get("min")) if rmin is None else rmin
                    rmax = _number(b.get("max")) if rmax is None else rmax
        if rmin is not None and rmax is not None and 0 < rmin <= rmax:
            for rpm in _linspace(rmin, rmax, 5):
                out.append(
                    DonneeCandidate(
                        nom=nom,
                        path=path or "rpm_moteur_nominal",
                        valeur=rpm,
                        unite="rpm",
                        source=SOURCE_CDC,
                        statut=STATUS_CANDIDATE_FROM_CDC,
                        raison="Regime moteur candidat genere depuis les bornes explicites du cahier des charges.",
                        dependances=["cahier_des_charges.rpm_moteur_min", "cahier_des_charges.rpm_moteur_max"],
                        metadata={
                            "domaine": {"min": rmin, "max": rmax, "count": 5},
                            "formule": "exploration lineaire dans les bornes rpm CDC",
                            "score_local": _domain_score(rpm, rmin, rmax),
                            "raison_inconnue": raison,
                        },
                    )
                )

    if any(token in target for token in ("alesage", "course", "bore", "stroke")):
        field = "alesage_m" if any(token in target for token in ("alesage", "bore")) else "course_m"
        bmin = _number(cahier_des_charges.get(f"{field}_min"))
        bmax = _number(cahier_des_charges.get(f"{field}_max"))
        bounds = cahier_des_charges.get("bornes")
        if isinstance(bounds, Mapping) and isinstance(bounds.get(field), Mapping):
            bmin = _number(bounds[field].get("min")) if bmin is None else bmin
            bmax = _number(bounds[field].get("max")) if bmax is None else bmax
        if bmin is not None and bmax is not None and 0 < bmin <= bmax:
            for value in _linspace(bmin, bmax, 5):
                out.append(
                    DonneeCandidate(
                        nom=nom,
                        path=path or field,
                        valeur=value,
                        unite="m",
                        source=SOURCE_CDC,
                        statut=STATUS_CANDIDATE_FROM_CDC,
                        raison=f"{field} candidat genere depuis les bornes explicites du cahier des charges.",
                        dependances=[f"cahier_des_charges.{field}_min", f"cahier_des_charges.{field}_max"],
                        metadata={
                            "domaine": {"min": bmin, "max": bmax, "count": 5},
                            "formule": f"exploration lineaire dans les bornes {field} CDC",
                            "score_local": _domain_score(value, bmin, bmax),
                            "raison_inconnue": raison,
                        },
                    )
                )

    if "materiau" in target or "material" in target:
        allowed = cahier_des_charges.get("materiaux_autorises")
        constraints = cahier_des_charges.get("contraintes_materiau") or cahier_des_charges.get("materiau_contraintes")
        if isinstance(allowed, (list, tuple)) and allowed and isinstance(constraints, Mapping) and constraints:
            for material in allowed:
                if material:
                    out.append(
                        DonneeCandidate(
                            nom=nom,
                            path=path or "materiau",
                            valeur=str(material),
                            unite=None,
                            source=SOURCE_CDC,
                            statut=STATUS_CANDIDATE_FROM_CDC,
                            raison="Materiau candidat issu de la liste autorisee et de contraintes materiau explicites.",
                            dependances=["cahier_des_charges.materiaux_autorises", "cahier_des_charges.contraintes_materiau"],
                            metadata={"domaine": list(allowed), "contraintes": dict(constraints), "formule": "selection materiau autorisee", "score_local": 1.0 / len(allowed)},
                        )
                    )

    if "carburant" in target or "fuel" in target:
        allowed = cahier_des_charges.get("carburants_autorises")
        rule = cahier_des_charges.get("regle_carburant_dimensionnant") or cahier_des_charges.get("strategie_carburant")
        if isinstance(allowed, (list, tuple)) and allowed and rule:
            for fuel in allowed:
                out.append(
                    DonneeCandidate(
                        nom=nom,
                        path=path or "carburant",
                        valeur=str(fuel),
                        unite=None,
                        source=SOURCE_CDC,
                        statut=STATUS_CANDIDATE_FROM_CDC,
                        raison="Carburant candidat issu d'une liste autorisee et d'une regle explicite.",
                        dependances=["cahier_des_charges.carburants_autorises", "cahier_des_charges.regle_carburant_dimensionnant"],
                        metadata={"domaine": list(allowed), "regle": str(rule), "formule": "selection carburant autorisee", "score_local": 1.0 / len(allowed)},
                    )
                )

    if target.endswith("ns") or "ns_batterie" in target or "cellules_serie" in target:
        cell = cahier_des_charges.get("cellule_batterie")
        bus_v = _first_number(config, rapport, "tension_bus_dc_v", "synthese.systeme.V_bus_dc_v")
        if isinstance(cell, Mapping) and bus_v is not None:
            cell_v = _number(cell.get("tension_nominale_v"))
            if cell_v and cell_v > 0:
                nominal = max(1, int(round(bus_v / cell_v)))
                domain = sorted({max(1, nominal - 1), nominal, nominal + 1})
                for ns in domain:
                    out.append(
                        DonneeCandidate(
                            nom=nom,
                            path=path or "batterie.Ns",
                            valeur=ns,
                            unite=None,
                            source=SOURCE_CDC,
                            statut=STATUS_CANDIDATE_FROM_CDC,
                            raison="Nombre de cellules serie candidat depuis tension bus et cellule imposee.",
                            dependances=["tension_bus_dc_v", "cahier_des_charges.cellule_batterie.tension_nominale_v"],
                            metadata={"domaine": domain, "formule": "Ns ~= tension_bus_dc_v / tension_cellule_v", "score_local": 1.0 / len(domain)},
                        )
                    )

    return out


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    return None


def _first_number(config: Mapping[str, Any], rapport: Mapping[str, Any], *paths: str) -> float | None:
    for path in paths:
        for root in (config, rapport):
            value = _get_path(root, path)
            number = _number(value)
            if number is not None:
                return number
    return None


def _linspace(start: float, stop: float, count: int) -> list[float]:
    if count <= 1:
        return [start]
    step = (stop - start) / float(count - 1)
    return [start + step * i for i in range(count)]


def _domain_score(value: float, mini: float, maxi: float) -> float:
    if maxi <= mini:
        return 1.0
    center = (mini + maxi) / 2.0
    half = (maxi - mini) / 2.0
    return max(0.0, 1.0 - abs(value - center) / half)
