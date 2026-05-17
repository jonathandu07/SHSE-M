from __future__ import annotations

"""Generation de candidats bornee par le cahier des charges."""

import math
from typing import Any, Dict, List, Mapping


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
                        source="generated_from_cahier_des_charges",
                        statut="candidate_generated",
                        raison=(
                            "Longueur de bielle generee depuis la course et l'intervalle "
                            "ratio_bielle_course_min/max du cahier des charges."
                        ),
                        dependances=["course_m", "ratio_bielle_course_min", "ratio_bielle_course_max"],
                        metadata={"ratio_bielle_course": ratio, "borne_min": rmin, "borne_max": rmax, "raison_inconnue": raison},
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
                    source="generated_from_cahier_des_charges",
                    statut="candidate_generated",
                    raison="Tension bus DC imposee explicitement par le cahier des charges.",
                    dependances=["cahier_des_charges.tension_bus_dc_v"],
                    metadata={"raison_inconnue": raison},
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
                        statut="candidate_generated",
                        raison="Rapport moteur/alternateur calcule exactement depuis deux regimes connus.",
                        dependances=["vitesse_alternateur_rpm", "vitesse_moteur_thermique_rpm"],
                        metadata={"rapport_boite_min": rmin, "rapport_boite_max": rmax},
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
                            source="generated_from_cahier_des_charges",
                            statut="candidate_generated",
                            raison="Nombre de cylindres candidat issu de la liste autorisee CDC.",
                            dependances=["cahier_des_charges.nombres_cylindres_autorises"],
                            metadata={"domaine": list(values)},
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

