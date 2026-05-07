from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional


UNIT_TO_W = {
    "w": 1.0,
    "kw": 1000.0,
    "hp": 745.6998715822702,
    "bhp": 745.6998715822702,
    "cv": 735.49875,
    "ch": 735.49875,
    "cheval": 735.49875,
    "chevaux": 735.49875,
}


def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _require_positive(name: str, value: Any) -> float:
    if not _is_finite(value):
        raise ValueError(f"{name} doit etre un nombre fini.")
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{name} doit etre > 0.")
    return value


def _optional_positive(name: str, value: Any) -> Optional[float]:
    if value is None:
        return None
    return _require_positive(name, value)


def _ratio(name: str, value: Any) -> Optional[float]:
    if value is None:
        return None
    value = _require_positive(name, value)
    if value > 1.0:
        raise ValueError(f"{name} doit etre <= 1.")
    return value


def _get(known: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in known and known[name] is not None:
            return known[name]
    return None


def _push_unknown(report: Dict[str, Any], kind: str, name: str, reason: str, unlocks: str) -> None:
    report["inconnues"][kind].append({"nom": name, "raison": reason, "debloque": unlocks})


def _dedup_unknowns(report: Dict[str, Any]) -> None:
    for kind in ("impossibles", "partielles"):
        seen: set[tuple[str, str]] = set()
        out = []
        for item in report["inconnues"][kind]:
            key = (str(item.get("nom")), str(item.get("raison")))
            if key not in seen:
                seen.add(key)
                out.append(item)
        report["inconnues"][kind] = out


def normaliser_puissance(puissance: float, unite: str = "kw") -> Dict[str, float | str]:
    unit = str(unite or "kw").strip().lower()
    if unit not in UNIT_TO_W:
        allowed = ", ".join(sorted(UNIT_TO_W))
        raise ValueError(f"unite inconnue {unite!r}. Unites acceptees: {allowed}.")

    p_w = _require_positive("puissance", puissance) * UNIT_TO_W[unit]
    return {
        "valeur_entree": float(puissance),
        "unite_entree": unit,
        "w": p_w,
        "kw": p_w / 1000.0,
        "hp": p_w / UNIT_TO_W["hp"],
        "cv": p_w / UNIT_TO_W["cv"],
    }


def _torque_from_power(p_w: float, rpm: float) -> float:
    omega = 2.0 * math.pi * rpm / 60.0
    return p_w / omega


def _cycles_per_second(rpm: float, temps_moteur: int) -> float:
    if temps_moteur == 2:
        return rpm / 60.0
    if temps_moteur == 4:
        return rpm / 120.0
    raise ValueError("temps_moteur doit valoir 2 ou 4.")


def _bore_stroke_from_vd_ratio(vd_unit_m3: float, ratio_course_alesage: float) -> Dict[str, float]:
    ratio = _require_positive("ratio_course_alesage", ratio_course_alesage)
    bore_m = ((4.0 * vd_unit_m3) / (math.pi * ratio)) ** (1.0 / 3.0)
    stroke_m = ratio * bore_m
    return {
        "alesage_m": bore_m,
        "course_m": stroke_m,
        "alesage_mm": bore_m * 1000.0,
        "course_mm": stroke_m * 1000.0,
        "ratio_course_alesage": ratio,
    }


def analyser_puissance_sortie(
    puissance: float,
    unite: str = "kw",
    *,
    type_sortie: str = "sortie_utilisateur",
    donnees_connues: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Analyse stricte depuis une puissance de sortie.

    Cette fonction ne cree pas de composant par defaut. Elle calcule seulement
    les grandeurs fermees par les entrees et liste les donnees manquantes pour
    aller plus loin.
    """

    known: Dict[str, Any] = dict(donnees_connues or {})
    power = normaliser_puissance(puissance, unite)
    p_out_w = float(power["w"])

    report: Dict[str, Any] = {
        "meta": {
            "mode": "puissance_sortie_strict_sans_invention",
            "type_sortie": type_sortie,
        },
        "entrees": {
            "puissance": power,
            "donnees_connues": known,
        },
        "calculs": {
            "puissance_sortie": power,
            "energie_si_maintenue_1h_kwh": p_out_w / 1000.0,
        },
        "composants": {},
        "pieces": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [
            "Une puissance seule fixe une intensite de puissance, pas une geometrie ni une autonomie.",
            "Les calculs ci-dessous restent vides tant qu'une grandeur necessaire manque.",
        ],
    }

    rpm_sortie = _optional_positive("rpm_sortie", _get(known, "rpm_sortie", "regime_sortie_rpm"))
    if rpm_sortie is not None:
        report["calculs"]["couple_sortie_nm"] = _torque_from_power(p_out_w, rpm_sortie)
    else:
        _push_unknown(
            report,
            "partielles",
            "rpm_sortie",
            "Necessaire pour convertir la puissance de sortie en couple.",
            "couple_sortie_nm",
        )

    rendement_total = _ratio("rendement_total", _get(known, "rendement_total", "rendement_chaine"))
    if rendement_total is not None:
        report["calculs"]["puissance_amont_requise_w"] = p_out_w / rendement_total
    else:
        _push_unknown(
            report,
            "partielles",
            "rendement_total",
            "Necessaire pour remonter de la puissance sortie vers la puissance amont.",
            "puissance_amont_requise_w",
        )

    tension_dc_v = _optional_positive(
        "tension_dc_v",
        _get(known, "tension_dc_v", "tension_bus_dc_v", "tension_sortie_v"),
    )
    if tension_dc_v is not None:
        report["calculs"]["courant_dc_a"] = p_out_w / tension_dc_v
    else:
        _push_unknown(
            report,
            "partielles",
            "tension_dc_v",
            "Necessaire pour deduire le courant DC depuis P = U * I.",
            "courant_dc_a",
        )

    tension_ac_ligne_v = _optional_positive("tension_ac_ligne_v", _get(known, "tension_ac_ligne_v"))
    facteur_puissance = _ratio("facteur_puissance", _get(known, "facteur_puissance"))
    if tension_ac_ligne_v is not None and facteur_puissance is not None:
        report["calculs"]["courant_triphase_ligne_a"] = p_out_w / (math.sqrt(3.0) * tension_ac_ligne_v * facteur_puissance)
    elif tension_ac_ligne_v is not None or facteur_puissance is not None:
        _push_unknown(
            report,
            "partielles",
            "tension_ac_ligne_v + facteur_puissance",
            "Les deux sont requis pour deduire le courant triphase.",
            "courant_triphase_ligne_a",
        )

    duree_h = _optional_positive("duree_h", _get(known, "duree_h", "autonomie_h", "temps_fonctionnement_h"))
    if duree_h is not None:
        report["calculs"]["energie_sortie_sur_duree_kwh"] = (p_out_w / 1000.0) * duree_h
    else:
        _push_unknown(
            report,
            "partielles",
            "duree_h",
            "Necessaire pour transformer une puissance en energie.",
            "energie_sortie_sur_duree_kwh",
        )

    distance_km = _optional_positive("distance_km", _get(known, "distance_km"))
    conso_kwh_km = _optional_positive("conso_kwh_km", _get(known, "conso_kwh_km"))
    if distance_km is not None and conso_kwh_km is not None:
        report["calculs"]["energie_trajet_kwh"] = distance_km * conso_kwh_km
    elif distance_km is not None or conso_kwh_km is not None:
        _push_unknown(
            report,
            "partielles",
            "distance_km + conso_kwh_km",
            "Les deux sont requis pour dimensionner l'energie utile batterie sur trajet.",
            "energie_trajet_kwh",
        )

    puissance_moteur_w = _optional_positive(
        "puissance_moteur_requise_w",
        _get(known, "puissance_moteur_requise_w", "puissance_moteur_requise_W", "puissance_frein_moteur_w"),
    )
    rendement_sortie_moteur = _ratio(
        "rendement_sortie_depuis_moteur",
        _get(known, "rendement_sortie_depuis_moteur", "rendement_transmission_moteur_sortie"),
    )
    if puissance_moteur_w is None and rendement_sortie_moteur is not None:
        puissance_moteur_w = p_out_w / rendement_sortie_moteur
        report["notes_modele"].append("puissance_moteur_requise_w calculee depuis la puissance de sortie et le rendement fourni.")
    if puissance_moteur_w is not None:
        report["calculs"]["puissance_moteur_requise_w"] = puissance_moteur_w
    else:
        _push_unknown(
            report,
            "partielles",
            "puissance_moteur_requise_w ou rendement_sortie_depuis_moteur",
            "Necessaire pour relier la sortie utilisateur au moteur thermique.",
            "couple_moteur_nm, cylindree_totale_requise_m3",
        )

    rpm_moteur = _optional_positive(
        "rpm_moteur",
        _get(known, "rpm_moteur", "rpm_moteur_nominal", "vitesse_moteur_thermique_rpm"),
    )
    if puissance_moteur_w is not None and rpm_moteur is not None:
        report["calculs"]["couple_moteur_nm"] = _torque_from_power(puissance_moteur_w, rpm_moteur)
    elif puissance_moteur_w is not None or rpm_moteur is not None:
        _push_unknown(
            report,
            "partielles",
            "puissance_moteur_requise_w + rpm_moteur",
            "Les deux sont requis pour calculer le couple moteur.",
            "couple_moteur_nm",
        )

    pme_pa = _optional_positive(
        "pme_pa",
        _get(known, "pme_pa", "pression_moyenne_effective_pa", "pme_nominale_pa"),
    )
    temps_moteur_raw = _get(known, "temps_moteur")
    temps_moteur = int(temps_moteur_raw) if temps_moteur_raw is not None else None
    type_puissance_moteur = _get(known, "type_puissance_moteur", "type_puissance_nominale")
    rendement_mecanique = _ratio("rendement_mecanique", _get(known, "rendement_mecanique", "rendement_mecanique_nominal"))

    puissance_indiquee_w: Optional[float] = None
    if type_puissance_moteur not in ("frein", "indiquee"):
        _push_unknown(
            report,
            "impossibles",
            "type_puissance_moteur",
            "Preciser 'frein' ou 'indiquee' pour relier puissance et PME.",
            "cylindree_totale_requise_m3",
        )
    if puissance_moteur_w is not None:
        if type_puissance_moteur == "indiquee":
            puissance_indiquee_w = puissance_moteur_w
        elif type_puissance_moteur == "frein":
            if rendement_mecanique is not None:
                puissance_indiquee_w = puissance_moteur_w / rendement_mecanique
            else:
                _push_unknown(
                    report,
                    "impossibles",
                    "rendement_mecanique",
                    "Requis pour convertir une puissance frein en puissance indiquee.",
                    "cylindree_totale_requise_m3",
                )
        else:
            _push_unknown(
                report,
                "impossibles",
                "type_puissance_moteur",
                "Preciser 'frein' ou 'indiquee' pour relier puissance et PME.",
                "cylindree_totale_requise_m3",
            )

    if puissance_indiquee_w is not None and rpm_moteur is not None and pme_pa is not None and temps_moteur is not None:
        cycles_hz = _cycles_per_second(rpm_moteur, temps_moteur)
        vd_total_m3 = puissance_indiquee_w / (pme_pa * cycles_hz)
        report["calculs"]["moteur_thermique"] = {
            "puissance_indiquee_w": puissance_indiquee_w,
            "cycles_par_seconde": cycles_hz,
            "cylindree_totale_requise_m3": vd_total_m3,
            "cylindree_totale_requise_l": vd_total_m3 * 1000.0,
        }
    else:
        missing = []
        if puissance_indiquee_w is None:
            missing.append("puissance indiquee")
        if rpm_moteur is None:
            missing.append("rpm_moteur")
        if pme_pa is None:
            missing.append("pme_pa")
        if temps_moteur is None:
            missing.append("temps_moteur")
        _push_unknown(
            report,
            "impossibles",
            "cylindree moteur thermique",
            "Manque: " + ", ".join(missing) + ".",
            "cylindree_totale_requise_m3",
        )

    motor_calc = report["calculs"].get("moteur_thermique", {})
    vd_total = motor_calc.get("cylindree_totale_requise_m3") if isinstance(motor_calc, dict) else None
    nombre_cylindres_raw = _get(known, "nombre_cylindres", "n_cyl")
    nombre_cylindres = int(nombre_cylindres_raw) if nombre_cylindres_raw is not None else None
    ratio_cible = _optional_positive("ratio_course_alesage_cible", _get(known, "ratio_course_alesage_cible"))
    ratio_max = _optional_positive("ratio_course_alesage_max", _get(known, "ratio_course_alesage_max"))
    vitesse_piston_max_ms = _optional_positive("vitesse_piston_max_ms", _get(known, "vitesse_piston_max_ms"))

    if _is_finite(vd_total):
        n_for_geom = nombre_cylindres
        ratio_for_geom = ratio_cible
        source_geom = "nombre_cylindres + ratio_course_alesage_cible fournis"

        if n_for_geom is None and rpm_moteur is not None and vitesse_piston_max_ms is not None and ratio_max is not None:
            course_max_m = vitesse_piston_max_ms / (2.0 * rpm_moteur / 60.0)
            bore_max_m = course_max_m / ratio_max
            vd_unit_max_m3 = (math.pi / 4.0) * bore_max_m**2 * course_max_m
            n_for_geom = max(1, math.ceil(float(vd_total) / vd_unit_max_m3))
            ratio_for_geom = ratio_max
            source_geom = "nombre_cylindres_min calcule aux limites rpm/Umax/ratio_max"
            report["calculs"]["moteur_thermique"]["nombre_cylindres_min"] = n_for_geom
            report["calculs"]["moteur_thermique"]["cylindree_unitaire_max_m3"] = vd_unit_max_m3

        if n_for_geom is not None and ratio_for_geom is None and ratio_max is not None:
            ratio_for_geom = ratio_max
            source_geom = "ratio_course_alesage_max utilise comme limite fournie"

        if n_for_geom is not None and ratio_for_geom is not None:
            vd_unit = float(vd_total) / float(n_for_geom)
            geom = _bore_stroke_from_vd_ratio(vd_unit, ratio_for_geom)
            geom.update({"nombre_cylindres": n_for_geom, "source": source_geom})
            report["calculs"]["moteur_thermique"]["geometrie"] = geom
        else:
            _push_unknown(
                report,
                "partielles",
                "nombre_cylindres/ratio_course_alesage",
                "Necessaire pour passer d'une cylindree totale a alesage/course.",
                "alesage_m, course_m, nombre_cylindres",
            )

    geom = {}
    if isinstance(report["calculs"].get("moteur_thermique"), dict):
        geom = report["calculs"]["moteur_thermique"].get("geometrie", {}) or {}
    pression_max_pa = _optional_positive("pression_max_pa", _get(known, "pression_max_pa"))
    contrainte_admissible_pa = _optional_positive("contrainte_admissible_pa", _get(known, "contrainte_admissible_pa"))
    facteur_securite = _optional_positive("facteur_securite_cylindre", _get(known, "facteur_securite_cylindre"))
    if geom and pression_max_pa is not None and contrainte_admissible_pa is not None and facteur_securite is not None:
        rayon_m = float(geom["alesage_m"]) / 2.0
        report["calculs"]["moteur_thermique"]["epaisseur_cylindre_mince_m"] = pression_max_pa * rayon_m * facteur_securite / contrainte_admissible_pa
    elif geom:
        _push_unknown(
            report,
            "partielles",
            "pression_max_pa + contrainte_admissible_pa + facteur_securite_cylindre",
            "Necessaires pour predimensionner l'epaisseur du cylindre.",
            "epaisseur_cylindre_mince_m",
        )

    report["composants"] = {
        "moteur_thermique": {
            "statut": "partiel" if "moteur_thermique" in report["calculs"] else "bloque",
            "calculable_depuis_puissance": ["puissance", "couple si rpm", "cylindree si rpm+pme+temps+type puissance"],
        },
        "moteur_electrique": {
            "statut": "partiel",
            "calculable_depuis_puissance": ["puissance nominale"],
            "manque_pour_definition": ["rpm/couple", "tension", "rendement", "limites thermiques", "courbe couple-vitesse"],
        },
        "alternateur": {
            "statut": "partiel",
            "calculable_depuis_puissance": ["courant si tension connue", "couple si rpm connu"],
            "manque_pour_definition": ["rpm", "tension", "nombre poles", "bobinage", "flux/induction", "rendement/pertes"],
        },
        "batterie": {
            "statut": "partiel" if ("energie_sortie_sur_duree_kwh" in report["calculs"] or "energie_trajet_kwh" in report["calculs"]) else "bloque",
            "calculable_depuis_puissance": ["energie seulement si duree/autonomie ou trajet fournis"],
            "manque_pour_definition": ["energie utile", "fenetre SOC", "tension pack", "cellule commerciale", "C-rate", "thermique", "BMS"],
        },
        "boite_crabots": {
            "statut": "partiel" if ("couple_sortie_nm" in report["calculs"] or "couple_moteur_nm" in report["calculs"]) else "bloque",
            "calculable_depuis_puissance": ["couple si rpm connu"],
            "manque_pour_definition": ["rapports", "module denture", "materiau", "efforts roulements", "inerties d'engagement"],
        },
    }

    report["pieces"] = {
        "cylindre": ["alesage", "course", "pression_max", "contrainte admissible", "materiau/densite"],
        "piston": ["cylindre defini", "pression_max", "rpm", "materiau", "segments/joints"],
        "bielle": ["piston", "course", "rpm", "force gaz/inertie", "longueur bielle", "materiau"],
        "arbre_piston": ["piston", "efforts", "rpm", "materiau"],
        "vilbrequin": ["couple moteur", "course", "nombre manetons/journaux", "materiau", "charges bielle"],
        "roulements": ["charges radiales/axiales", "rpm", "duree de vie cible", "catalogue ou dimensions"],
        "alternateur": ["puissance electrique", "rpm", "tension", "poles", "bobinage", "flux", "pertes"],
        "batterie": ["energie utile", "puissance charge/decharge", "tension", "cellule", "architecture pack"],
    }

    calcul_count = len(report["calculs"])
    unknown_count = len(report["inconnues"]["impossibles"]) + len(report["inconnues"]["partielles"])
    report["niveau_definition"] = {
        "calculs_directs": calcul_count,
        "inconnues_total": unknown_count,
        "pret_pour_dimensionnement_pieces": bool(geom and pression_max_pa is not None and contrainte_admissible_pa is not None),
    }

    _dedup_unknowns(report)
    report["niveau_definition"]["inconnues_total"] = len(report["inconnues"]["impossibles"]) + len(report["inconnues"]["partielles"])
    return report
