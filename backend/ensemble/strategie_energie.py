from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from backend.ensemble import calcul_stho_me as phys
except Exception:  # pragma: no cover
    import calcul_stho_me as phys  # type: ignore


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inconnues = rapport.setdefault("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        uniques: List[Dict[str, str]] = []
        vus = set()
        for item in list(inconnues.get(categorie, []) or []):
            if not isinstance(item, dict):
                continue
            cle = (str(item.get("nom")), str(item.get("raison")))
            if cle in vus:
                continue
            vus.add(cle)
            uniques.append({"nom": cle[0], "raison": cle[1]})
        inconnues[categorie] = uniques


def _first_finite(*values: Any) -> Optional[float]:
    for value in values:
        if _is_finite(value):
            return float(value)
    return None


def _deep_get(source: Any, *keys: str) -> Any:
    current = source
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _append_note(rapport: Dict[str, Any], note: str) -> None:
    rapport.setdefault("notes_modele", []).append(str(note))


def _collect_inconnues(*sources: Optional[Mapping[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    bloc = {"impossibles": [], "partielles": []}
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        inconnues = _safe_dict(source.get("inconnues"))
        for categorie in ("impossibles", "partielles"):
            for item in list(inconnues.get(categorie, []) or []):
                if isinstance(item, dict):
                    bloc[categorie].append({"nom": str(item.get("nom", "?")), "raison": str(item.get("raison", ""))})
    return bloc


class ModeEnergetique(str, Enum):
    EV_ONLY = "ev_only"
    SOUTIEN_TRACTION = "soutien_traction"
    RECHARGE_BATTERIE = "recharge_batterie"
    MAINTIEN_SOC = "maintien_soc"
    MODE_DEGRADE = "mode_degrade"
    URGENCE_PUISSANCE = "urgence_puissance"


@dataclass(frozen=True)
class EnveloppeBatterie:
    p_charge_max_soh_w: Optional[float] = None
    p_charge_max_temp_w: Optional[float] = None
    p_charge_max_crate_w: Optional[float] = None
    p_charge_max_bus_w: Optional[float] = None
    p_charge_recommandee_w: Optional[float] = None
    limites_actives: List[str] = field(default_factory=list)
    raison_limitante: Optional[str] = None

    def vers_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_battery_capacity_ah(batterie: Any, rapport_batterie: Optional[Mapping[str, Any]]) -> Optional[float]:
    return _first_finite(
        _deep_get(rapport_batterie, "electrique", "capacite_pack_ah"),
        _deep_get(rapport_batterie, "dimensionnement_fin", "rapport", "dimensionnement", "capacite_pack_ah"),
        getattr(batterie, "capacite_ah", None),
    )


def _extract_battery_voltage_v(
    batterie: Any,
    rapport_batterie: Optional[Mapping[str, Any]],
    etat_systeme: Optional[Mapping[str, Any]],
) -> Optional[float]:
    return _first_finite(
        _deep_get(etat_systeme, "v_bus_dc_v"),
        _deep_get(rapport_batterie, "electrique", "tension_pack_nominale_v"),
        _deep_get(rapport_batterie, "dimensionnement", "tension_nominale_v"),
        getattr(batterie, "tension_charge_v", None),
        getattr(batterie, "tension_nominale_v", None),
    )


def determiner_enveloppe_batterie(
    *,
    batterie: Any,
    etat_systeme: Optional[Mapping[str, Any]] = None,
    rapport_batterie: Optional[Mapping[str, Any]] = None,
    rapport_recharge_batterie: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    rapport: Dict[str, Any] = {
        "enveloppe": EnveloppeBatterie().vers_dict(),
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }
    etat = _safe_dict(etat_systeme)
    rep_batt = _safe_dict(rapport_batterie)
    rep_recharge = _safe_dict(rapport_recharge_batterie)

    tension_bus_v = _extract_battery_voltage_v(batterie, rep_batt, etat)
    capacite_ah = _extract_battery_capacity_ah(batterie, rep_batt)
    c_rate_max = _first_finite(
        etat.get("c_rate_charge_max"),
        getattr(batterie, "c_rate_max_charge", None),
        getattr(batterie, "c_rate_charge_max", None),
    )
    temperature_pack_c = _first_finite(etat.get("batterie_temp_c"), etat.get("temperature_pack_c"))
    temperature_limite_c = _first_finite(
        etat.get("temperature_limite_pack_c"),
        _deep_get(rep_recharge, "securite_cellules", "temperature_limite_c"),
        getattr(batterie, "temperature_alerte_c", None),
        getattr(batterie, "temp_cellule_critique_c", None),
    )

    p_charge_max_crate_w = None
    if _is_finite(c_rate_max) and _is_finite(capacite_ah) and _is_finite(tension_bus_v):
        p_charge_max_crate_w = float(c_rate_max) * float(capacite_ah) * float(tension_bus_v)
    else:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_crate_w",
            "Calculable si C-rate constructeur, capacité Ah et tension bus DC sont disponibles.",
        )

    p_charge_max_bus_w = _first_finite(
        etat.get("p_charge_max_bus_w"),
        (float(_deep_get(rep_recharge, "securite_cellules", "puissance_charge_max_autorisee_kw")) * 1000.0)
        if _is_finite(_deep_get(rep_recharge, "securite_cellules", "puissance_charge_max_autorisee_kw"))
        else None,
    )
    if p_charge_max_bus_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_bus_w",
            "Calculable si une limite explicite de puissance de charge BMS ou pack est fournie.",
        )

    p_charge_max_temp_w = None
    if _is_finite(temperature_pack_c) and _is_finite(temperature_limite_c):
        if float(temperature_pack_c) >= float(temperature_limite_c):
            p_charge_max_temp_w = 0.0
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "p_charge_max_temp_w",
                "La température reste admissible, mais aucune loi explicite de derating thermique n'est fournie.",
            )
    else:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_temp_w",
            "Calculable si température pack et température limite admissible sont disponibles.",
        )

    p_charge_max_soh_w = _first_finite(
        etat.get("p_charge_max_soh_w"),
        (float(_deep_get(rep_recharge, "securite_cellules", "puissance_charge_max_soh_kw")) * 1000.0)
        if _is_finite(_deep_get(rep_recharge, "securite_cellules", "puissance_charge_max_soh_kw"))
        else None,
    )
    if p_charge_max_soh_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_soh_w",
            "Aucune relation explicite SoH -> puissance de charge maximale n'est disponible.",
        )

    limites = {
        "p_charge_max_soh_w": p_charge_max_soh_w,
        "p_charge_max_temp_w": p_charge_max_temp_w,
        "p_charge_max_crate_w": p_charge_max_crate_w,
        "p_charge_max_bus_w": p_charge_max_bus_w,
    }
    valeurs_finies = {nom: float(valeur) for nom, valeur in limites.items() if _is_finite(valeur)}
    p_charge_recommandee_w = min(valeurs_finies.values()) if valeurs_finies else None
    limites_actives = [nom for nom, valeur in valeurs_finies.items() if p_charge_recommandee_w is not None and abs(valeur - p_charge_recommandee_w) <= 1e-9]
    raison_limitante = limites_actives[0] if limites_actives else None

    rapport["enveloppe"] = EnveloppeBatterie(
        p_charge_max_soh_w=p_charge_max_soh_w,
        p_charge_max_temp_w=p_charge_max_temp_w,
        p_charge_max_crate_w=p_charge_max_crate_w,
        p_charge_max_bus_w=p_charge_max_bus_w,
        p_charge_recommandee_w=p_charge_recommandee_w,
        limites_actives=limites_actives,
        raison_limitante=raison_limitante,
    ).vers_dict()
    _dedup_inconnues(rapport)
    return rapport


def _build_grid(explicit_grid: Optional[Sequence[Any]], minimum: Any, maximum: Any, step: Any) -> Tuple[Optional[List[float]], Optional[str]]:
    if explicit_grid is not None:
        values = [_safe_float(v) for v in explicit_grid]
        values = [float(v) for v in values if v is not None]
        return (values or None), None if values else "Grille explicite vide ou non numérique."
    vmin = _safe_float(minimum)
    vmax = _safe_float(maximum)
    vstep = _safe_float(step)
    if vmin is None or vmax is None or vstep is None:
        return None, "Bornes de grille incomplètes."
    if vstep <= 0.0 or vmax < vmin:
        return None, "Bornes de grille invalides."
    values: List[float] = []
    current = vmin
    guard = 0
    while current <= vmax + 1e-12 and guard < 20000:
        values.append(float(current))
        current += vstep
        guard += 1
    return values, None if values else "Grille impossible à construire."


def generer_cartographie_alternateur(
    *,
    alternateur: Any,
    tension_bus_dc_v: Optional[float],
    grille_rpm: Optional[Sequence[Any]] = None,
    grille_couple_nm: Optional[Sequence[Any]] = None,
    rpm_min: Optional[float] = None,
    rpm_max: Optional[float] = None,
    rpm_step: Optional[float] = None,
    couple_min: Optional[float] = None,
    couple_max: Optional[float] = None,
    couple_step: Optional[float] = None,
) -> Dict[str, Any]:
    rapport: Dict[str, Any] = {
        "grille_rpm": [],
        "grille_couple_nm": [],
        "points": [],
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }
    rpms, err_rpm = _build_grid(grille_rpm, rpm_min, rpm_max, rpm_step)
    couples, err_couple = _build_grid(grille_couple_nm, couple_min, couple_max, couple_step)
    if err_rpm is not None:
        _push_inconnue(rapport, "impossibles", "grille_rpm", err_rpm)
    if err_couple is not None:
        _push_inconnue(rapport, "impossibles", "grille_couple_nm", err_couple)
    if rpms is None or couples is None:
        _dedup_inconnues(rapport)
        return rapport

    rapport["grille_rpm"] = rpms
    rapport["grille_couple_nm"] = couples

    eta_impose = _safe_float(getattr(alternateur, "rendement_alternateur_impose", None))
    if eta_impose is None:
        _append_note(rapport, "Sans rendement alternateur explicite, la cartographie reste partielle côté conversion mécanique -> électrique.")

    for rpm in rpms:
        omega = 2.0 * math.pi * float(rpm) / 60.0
        for couple in couples:
            point: Dict[str, Any] = {
                "rpm_alternateur": float(rpm),
                "couple_alternateur_nm": float(couple),
                "puissance_mecanique_w": float(couple) * omega,
                "puissance_electrique_w": None,
                "pertes_cuivre_w": None,
                "pertes_fer_w": None,
                "pertes_fixes_w": _safe_float(getattr(alternateur, "pertes_fixes_w", None)),
                "pertes_totales_w": None,
                "rendement": None,
                "statut": "partiel",
            }
            if tension_bus_dc_v is None:
                _push_inconnue(point, "impossibles", "tension_bus_dc_v", "Tension bus DC requise pour l'analyse électrique du point.")
                point["statut"] = "impossible"
                rapport["points"].append(point)
                continue
            if eta_impose is None or eta_impose <= 0.0:
                _push_inconnue(point, "partielles", "rendement_alternateur_impose", "Requis pour déduire la puissance électrique depuis la puissance mécanique.")
                rapport["points"].append(point)
                continue

            p_elec = point["puissance_mecanique_w"] * eta_impose
            rep_alt = alternateur.analyser_point_de_fonctionnement(
                vitesse_rotation_rpm=float(rpm),
                mode_electrique="dc",
                tension_v=float(tension_bus_dc_v),
                puissance_electrique_cible_w=float(p_elec),
            )
            point["puissance_electrique_w"] = p_elec
            point["pertes_cuivre_w"] = _deep_get(rep_alt, "pertes", "pertes_cuivre_w")
            point["pertes_fer_w"] = _deep_get(rep_alt, "pertes", "pertes_fer_w")
            point["pertes_fixes_w"] = _deep_get(rep_alt, "pertes", "pertes_fixes_w")
            point["pertes_totales_w"] = _first_finite(
                _deep_get(rep_alt, "pertes", "pertes_connues_total_w"),
                point["puissance_mecanique_w"] - p_elec,
            )
            point["rendement"] = _first_finite(
                _deep_get(rep_alt, "rendement", "rendement_impose"),
                _deep_get(rep_alt, "rendement", "eta_sur_pertes_connues"),
                eta_impose,
            )
            incon = _collect_inconnues(rep_alt)
            point["inconnues"] = incon
            point["statut"] = "ok"
            if incon["impossibles"]:
                point["statut"] = "impossible"
            elif incon["partielles"]:
                point["statut"] = "partiel"
            rapport["points"].append(point)

    _dedup_inconnues(rapport)
    return rapport


def _validation_transitoire(
    *,
    point_actuel: Optional[Mapping[str, Any]],
    point_cible: Optional[Mapping[str, Any]],
    resistance_thermique_k_w: Optional[float],
    capacite_thermique_j_k: Optional[float],
    t_s: Optional[float],
) -> Dict[str, Any]:
    rapport: Dict[str, Any] = {
        "statut": "impossible",
        "point_actuel": _safe_dict(point_actuel),
        "point_cible": _safe_dict(point_cible),
        "tau_s": None,
        "rampe_puissance_w_s": None,
        "inconnues": [],
    }
    if point_actuel is None or point_cible is None:
        rapport["inconnues"].append("point_actuel et point_cible requis.")
        return rapport

    rpm_init = _first_finite(_deep_get(point_actuel, "rpm"), _deep_get(point_actuel, "rpm_moteur"))
    couple_init = _first_finite(_deep_get(point_actuel, "couple_nm"), _deep_get(point_actuel, "couple_moteur_requis_Nm"))
    rpm_cible = _first_finite(_deep_get(point_cible, "rpm"), _deep_get(point_cible, "rpm_moteur"))
    couple_cible = _first_finite(_deep_get(point_cible, "couple_nm"), _deep_get(point_cible, "couple_moteur_requis_Nm"))
    if not all(_is_finite(v) for v in (rpm_init, couple_init, rpm_cible, couple_cible)):
        rapport["inconnues"].append("rpm et couple requis pour le point actuel et le point cible.")
        return rapport
    if not all(_is_finite(v) for v in (resistance_thermique_k_w, capacite_thermique_j_k, t_s)):
        rapport["inconnues"].append("R_th, C_th et temps disponible requis pour la validation transitoire.")
        return rapport

    tau_s = phys.constante_temps_thermique(float(resistance_thermique_k_w), float(capacite_thermique_j_k))
    omega_init = 2.0 * math.pi * float(rpm_init) / 60.0
    omega_cible = 2.0 * math.pi * float(rpm_cible) / 60.0
    p_init = float(couple_init) * omega_init
    p_cible = float(couple_cible) * omega_cible
    p_atteinte = phys.reponse_transitoire_premier_ordre(p_init, p_cible, float(t_s), float(tau_s))

    rapport["tau_s"] = tau_s
    rapport["rampe_puissance_w_s"] = (p_atteinte - p_init) / max(float(t_s), 1e-12)
    rapport["point_actuel"] = {"rpm": float(rpm_init), "couple_nm": float(couple_init), "puissance_w": p_init}
    rapport["point_cible"] = {"rpm": float(rpm_cible), "couple_nm": float(couple_cible), "puissance_w": p_cible}
    rapport["statut"] = "ok" if abs(p_atteinte - p_cible) <= max(abs(p_cible) * 0.05, 1.0) else "partiel"
    return rapport


def _candidate_key(candidate: Dict[str, Any]) -> Tuple[Any, ...]:
    def _metric_pair(name: str, maximize: bool = False) -> Tuple[int, float]:
        value = _safe_float(candidate.get(name))
        if value is None:
            return 1, float("inf")
        return 0, (-value if maximize else value)

    return (
        1 if candidate.get("dangereux") else 0,
        1 if candidate.get("mecanique_impossible") else 0,
        1 if candidate.get("electrique_impossible") else 0,
        *_metric_pair("stress_batterie"),
        *_metric_pair("pertes_electriques_w"),
        *_metric_pair("pertes_mecaniques_w"),
        *_metric_pair("rendement_global", maximize=True),
        candidate.get("nb_inconnues", 0),
    )


def _extract_candidate_bus_current(candidate: Mapping[str, Any], tension_bus_dc_v: Optional[float]) -> Optional[float]:
    return _first_finite(
        _deep_get(candidate, "alternateur", "bus_dc", "courant_bus_dc_A"),
        _deep_get(candidate, "alternateur", "bus_dc", "courant_bus_dc_a"),
        (_safe_float(_deep_get(candidate, "exigences", "P_out_W")) / float(tension_bus_dc_v))
        if _is_finite(_deep_get(candidate, "exigences", "P_out_W")) and _is_finite(tension_bus_dc_v) and float(tension_bus_dc_v) > 0.0
        else None,
    )


def _build_candidates(
    *,
    rapport_boite: Optional[Mapping[str, Any]],
    tension_bus_dc_v: Optional[float],
    capacite_ah: Optional[float],
    resistance_interne_ohm: Optional[float],
) -> List[Dict[str, Any]]:
    candidats: List[Dict[str, Any]] = []
    if not isinstance(rapport_boite, Mapping):
        return candidats

    for brut in list(rapport_boite.get("candidats", []) or []):
        if not isinstance(brut, Mapping):
            continue
        cand = dict(brut)
        exigences = _safe_dict(cand.get("exigences"))
        alt_rep = _safe_dict(cand.get("alternateur"))
        boite_rep = _safe_dict(cand.get("boite"))
        inconnues = _collect_inconnues(alt_rep, boite_rep)

        courant_bus_a = _extract_candidate_bus_current(cand, tension_bus_dc_v)
        stress_batterie = None
        if _is_finite(courant_bus_a) and _is_finite(capacite_ah) and float(capacite_ah) > 0.0:
            stress_batterie = phys.calculer_c_rate(float(courant_bus_a), float(capacite_ah))

        pertes_joule_w = None
        if _is_finite(courant_bus_a) and _is_finite(resistance_interne_ohm):
            pertes_joule_w = phys.pertes_joule_interne(float(courant_bus_a), float(resistance_interne_ohm))
        elif courant_bus_a is not None:
            inconnues["partielles"].append(
                {
                    "nom": "pertes_joule_batterie_w",
                    "raison": "Résistance interne batterie requise pour conclure les pertes Joule.",
                }
            )

        pertes_electriques_w = None
        p_pertes_alt = _first_finite(
            exigences.get("P_pertes_alternateur_W"),
            _deep_get(alt_rep, "alternateur", "pertes", "pertes_connues_total_w"),
            _deep_get(alt_rep, "pertes", "pertes_connues_total_w"),
        )
        if p_pertes_alt is not None or pertes_joule_w is not None:
            pertes_electriques_w = float(p_pertes_alt or 0.0) + float(pertes_joule_w or 0.0)

        p_meca_alt = _first_finite(
            exigences.get("P_mecanique_alternateur_W"),
            _deep_get(alt_rep, "alternateur", "mecanique", "puissance_mecanique_dimensionnante_w"),
            _deep_get(alt_rep, "mecanique", "puissance_mecanique_dimensionnante_w"),
        )
        p_moteur_req = _first_finite(exigences.get("puissance_moteur_requise_W"))
        p_moteur_min = _first_finite(exigences.get("puissance_moteur_min_theorique_W"))
        pertes_mecaniques_w = None
        if p_moteur_req is not None and p_meca_alt is not None:
            pertes_mecaniques_w = max(0.0, float(p_moteur_req) - float(p_meca_alt))
        elif p_moteur_req is None and p_moteur_min is None:
            inconnues["partielles"].append(
                {
                    "nom": "puissance_moteur_thermique_requise_w",
                    "raison": "Rendement boîte/liaison manquant : seule une borne partielle ou aucune remontée n'est disponible.",
                }
            )

        p_out = _first_finite(exigences.get("P_out_W"))
        rendement_global = None
        p_thermique_ref = _first_finite(p_moteur_req, p_moteur_min)
        if p_out is not None and p_thermique_ref is not None and p_thermique_ref > 0.0:
            rendement_global = float(p_out) / float(p_thermique_ref)

        dangereux = bool(
            _deep_get(alt_rep, "alternateur", "thermique", "ok_temperature_sur_pertes_connues") is False
            or _deep_get(alt_rep, "thermique", "ok_temperature_sur_pertes_connues") is False
        )
        mecanique_impossible = bool(inconnues["impossibles"]) or (
            _first_finite(exigences.get("couple_moteur_requis_Nm"), exigences.get("couple_moteur_min_theorique_Nm")) is None
        )
        electrique_impossible = p_out is None

        candidats.append(
            {
                "rapport": cand.get("rapport"),
                "rpm_alternateur": cand.get("rpm_alternateur"),
                "alternateur": alt_rep,
                "boite": boite_rep,
                "exigences": exigences,
                "stress_batterie": stress_batterie,
                "courant_bus_dc_a": courant_bus_a,
                "pertes_joule_batterie_w": pertes_joule_w,
                "pertes_electriques_w": pertes_electriques_w,
                "pertes_mecaniques_w": pertes_mecaniques_w,
                "rendement_global": rendement_global,
                "dangereux": dangereux,
                "mecanique_impossible": mecanique_impossible,
                "electrique_impossible": electrique_impossible,
                "nb_inconnues": len(inconnues["impossibles"]) + len(inconnues["partielles"]),
                "inconnues": inconnues,
            }
        )
    return candidats


def analyser_strategie_energie(
    etat_systeme: Optional[Mapping[str, Any]] = None,
    composants: Optional[Mapping[str, Any]] = None,
    *,
    derivees_chaine_energie: Optional[Mapping[str, Any]] = None,
    rapport_batterie: Optional[Mapping[str, Any]] = None,
    rapport_alternateur: Optional[Mapping[str, Any]] = None,
    rapport_boite: Optional[Mapping[str, Any]] = None,
    rapport_recharge_batterie: Optional[Mapping[str, Any]] = None,
    point_actuel: Optional[Mapping[str, Any]] = None,
    mode_force: Optional[str] = None,
    autoriser_soutien_traction_si_recharge_interdite: bool = False,
    poids_cout: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    etat = _safe_dict(etat_systeme)
    composants_loc = _safe_dict(composants)
    derivees = _safe_dict(derivees_chaine_energie)
    rapport: Dict[str, Any] = {
        "decision": {},
        "mode_energetique": ModeEnergetique.EV_ONLY.value,
        "enveloppe_batterie": None,
        "bilan_bus_dc": {},
        "candidats": [],
        "point_retenu": None,
        "validation_transitoire": {
            "statut": "impossible",
            "point_actuel": _safe_dict(point_actuel),
            "point_cible": {},
            "tau_s": None,
            "rampe_puissance_w_s": None,
            "inconnues": [],
        },
        "derivees_chaine_energie": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "alertes": {},
        "notes_modele": [],
    }

    batterie = composants_loc.get("batterie")
    deplaceur = composants_loc.get("deplaceur")
    if batterie is None:
        _push_inconnue(rapport, "impossibles", "batterie", "Composant batterie requis pour piloter la stratégie énergétique.")
        return rapport

    if poids_cout:
        _append_note(rapport, "Des poids explicites ont été fournis ; la sélection par coût peut être activée sans remplacer la hiérarchie lexicographique par défaut.")

    env_report = determiner_enveloppe_batterie(
        batterie=batterie,
        etat_systeme=etat,
        rapport_batterie=rapport_batterie,
        rapport_recharge_batterie=rapport_recharge_batterie,
    )
    rapport["enveloppe_batterie"] = env_report["enveloppe"]
    for categorie, items in env_report["inconnues"].items():
        for item in items:
            _push_inconnue(rapport, categorie, item.get("nom", "?"), item.get("raison", ""))

    p_sortie_w = _first_finite(etat.get("puissance_sortie_demandee_w"), derivees.get("sortie_utilisateur_w"), etat.get("puissance_traction_roue_w"))
    p_usage_w = _first_finite(etat.get("puissance_elec_usage_w"), derivees.get("puissance_elec_usage_w"))
    p_aux_w = _first_finite(etat.get("puissance_auxiliaire_w"), derivees.get("puissance_auxiliaire_w"))
    p_recharge_demandee_w = _first_finite(etat.get("p_recharge_demandee_w"), derivees.get("puissance_recharge_batterie_w"))
    beta = _first_finite(etat.get("fraction_temps_generation_beta"), derivees.get("fraction_temps_generation_beta"))
    tension_bus_dc_v = _extract_battery_voltage_v(batterie, rapport_batterie, etat)

    enveloppe = _safe_dict(rapport["enveloppe_batterie"])
    p_recharge_limite_w = _first_finite(enveloppe.get("p_charge_recommandee_w"))
    p_recharge_retenue_w = p_recharge_demandee_w
    recharge_interdite = False
    if p_recharge_demandee_w is not None and p_recharge_demandee_w > 0.0 and p_recharge_limite_w is not None:
        p_recharge_retenue_w = min(p_recharge_demandee_w, p_recharge_limite_w)
        recharge_interdite = p_recharge_retenue_w <= 0.0
    elif p_recharge_demandee_w is not None and p_recharge_demandee_w > 0.0 and p_recharge_limite_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_recommandee_w",
            "Recharge demandée mais enveloppe batterie incomplète : la puissance de recharge retenue ne peut pas être validée.",
        )

    p_bus_total_w = _first_finite(etat.get("puissance_bus_dc_totale_w"))
    if p_bus_total_w is None:
        if p_usage_w is None:
            _push_inconnue(rapport, "partielles", "puissance_bus_dc_totale_w", "Calculable si la puissance d'usage électrique est disponible.")
        elif p_aux_w is None:
            _push_inconnue(rapport, "partielles", "puissance_bus_dc_totale_w", "Puissance auxiliaire absente : la puissance bus DC totale ne peut pas être fermée.")
        elif p_recharge_demandee_w is not None and p_recharge_retenue_w is None:
            _push_inconnue(rapport, "partielles", "puissance_bus_dc_totale_w", "Recharge demandée mais puissance retenue non calculable.")
        else:
            p_bus_total_w = float(p_usage_w) + float(p_aux_w) + float(p_recharge_retenue_w or 0.0)

    p_bus_inst_w = None
    if p_bus_total_w is not None:
        if beta is None:
            p_bus_inst_w = float(p_bus_total_w)
        elif 0.0 < beta <= 1.0:
            p_bus_inst_w = float(p_bus_total_w) / float(beta)
        else:
            _push_inconnue(rapport, "impossibles", "fraction_temps_generation_beta", "beta doit être dans ]0, 1].")

    mode = ModeEnergetique.EV_ONLY
    if mode_force in {m.value for m in ModeEnergetique}:
        mode = ModeEnergetique(mode_force)
    elif recharge_interdite and p_usage_w is not None and p_usage_w > 0.0 and autoriser_soutien_traction_si_recharge_interdite:
        mode = ModeEnergetique.SOUTIEN_TRACTION
        p_recharge_retenue_w = 0.0
    elif recharge_interdite and p_recharge_demandee_w is not None and p_recharge_demandee_w > 0.0:
        mode = ModeEnergetique.MODE_DEGRADE
        p_recharge_retenue_w = 0.0
    elif p_recharge_retenue_w is not None and p_recharge_retenue_w > 0.0:
        mode = ModeEnergetique.RECHARGE_BATTERIE
    elif p_usage_w is not None and p_usage_w > 0.0:
        mode = ModeEnergetique.SOUTIEN_TRACTION

    bilan_bus_dc = {
        "puissance_sortie_demandee_w": p_sortie_w,
        "puissance_electrique_usage_w": p_usage_w,
        "puissance_auxiliaire_w": p_aux_w,
        "puissance_recharge_demandee_w": p_recharge_demandee_w,
        "puissance_recharge_retenue_w": p_recharge_retenue_w,
        "puissance_bus_dc_totale_w": p_bus_total_w,
        "puissance_bus_dc_instantanee_w": p_bus_inst_w,
        "tension_bus_dc_v": tension_bus_dc_v,
        "courant_bus_dc_a": (float(p_bus_total_w) / float(tension_bus_dc_v)) if _is_finite(p_bus_total_w) and _is_finite(tension_bus_dc_v) and float(tension_bus_dc_v) > 0.0 else None,
        "fraction_temps_generation_beta": beta,
        "puissance_alternateur_electrique_requise_w": p_bus_inst_w,
        "puissance_alternateur_mecanique_requise_w": _first_finite(derivees.get("puissance_mecanique_alternateur_requise_w")),
        "puissance_alternateur_mecanique_borne_basse_w": _first_finite(derivees.get("puissance_mecanique_alternateur_borne_basse_w")),
        "puissance_moteur_thermique_requise_w": _first_finite(derivees.get("puissance_moteur_thermique_requise_w")),
        "puissance_moteur_thermique_borne_basse_w": _first_finite(derivees.get("puissance_moteur_thermique_borne_basse_w")),
    }
    if p_sortie_w is not None and _is_finite(bilan_bus_dc["puissance_moteur_thermique_requise_w"]) and float(bilan_bus_dc["puissance_moteur_thermique_requise_w"]) > 0.0:
        bilan_bus_dc["rendement_global_calcule"] = float(p_sortie_w) / float(bilan_bus_dc["puissance_moteur_thermique_requise_w"])
    else:
        bilan_bus_dc["rendement_global_calcule"] = None

    rapport["mode_energetique"] = mode.value
    rapport["bilan_bus_dc"] = bilan_bus_dc
    rapport["derivees_chaine_energie"] = {
        **dict(derivees),
        "puissance_recharge_batterie_retenue_w": p_recharge_retenue_w,
        "puissance_bus_dc_totale_retenue_w": p_bus_total_w,
        "puissance_bus_dc_instantanee_retenue_w": p_bus_inst_w,
        "mode_energetique_retenu": mode.value,
        "raison_limitante_batterie": enveloppe.get("raison_limitante"),
    }

    candidats = _build_candidates(
        rapport_boite=rapport_boite,
        tension_bus_dc_v=tension_bus_dc_v,
        capacite_ah=_extract_battery_capacity_ah(batterie, rapport_batterie),
        resistance_interne_ohm=_first_finite(etat.get("resistance_interne_batterie_ohm"), _deep_get(rapport_batterie, "electrique", "resistance_interne_pack_ohm")),
    )
    rapport["candidats"] = candidats

    if candidats:
        point_retenu = min(candidats, key=_candidate_key)
        rapport["point_retenu"] = point_retenu
        rapport["decision"] = {
            "mode_energetique": mode.value,
            "raison_choix": "Sélection lexicographique : sécurité, faisabilité mécanique/électrique, stress batterie, pertes, rendement puis robustesse.",
            "rapport_boite": point_retenu.get("rapport"),
            "limitation_batterie": enveloppe.get("raison_limitante"),
            "puissance_recharge_retenue_w": p_recharge_retenue_w,
        }
        for categorie, items in _safe_dict(point_retenu.get("inconnues")).items():
            for item in items:
                _push_inconnue(rapport, categorie, item.get("nom", "?"), item.get("raison", ""))
    else:
        _push_inconnue(
            rapport,
            "impossibles",
            "point_retenu",
            "Aucun candidat d'optimisation n'est disponible ; fournir une analyse boîte/alternateur exploitable ou les données pour la reconstruire.",
        )

    resistance_thermique_k_w = _first_finite(etat.get("resistance_thermique_k_w"), getattr(deplaceur, "resistance_thermique_k_w", None))
    capacite_thermique_j_k = _first_finite(etat.get("capacite_thermique_j_k"), getattr(deplaceur, "capacite_thermique_j_k", None))
    point_cible = None
    if rapport["point_retenu"] is not None:
        point_cible = {
            "rpm": _first_finite(
                (float(_deep_get(rapport["point_retenu"], "rpm_alternateur")) / float(rapport["point_retenu"]["rapport"]))
                if _is_finite(_deep_get(rapport["point_retenu"], "rpm_alternateur")) and _is_finite(rapport["point_retenu"].get("rapport")) and float(rapport["point_retenu"]["rapport"]) != 0.0
                else None,
                etat.get("rpm_moteur"),
            ),
            "couple_nm": _first_finite(
                _deep_get(rapport["point_retenu"], "exigences", "couple_moteur_requis_Nm"),
                _deep_get(rapport["point_retenu"], "exigences", "couple_moteur_min_theorique_Nm"),
            ),
        }
    rapport["validation_transitoire"] = _validation_transitoire(
        point_actuel=point_actuel or etat.get("point_actuel_thermique"),
        point_cible=point_cible,
        resistance_thermique_k_w=resistance_thermique_k_w,
        capacite_thermique_j_k=capacite_thermique_j_k,
        t_s=_first_finite(etat.get("temps_disponible_s")),
    )

    if rapport_alternateur and _first_finite(bilan_bus_dc.get("puissance_alternateur_mecanique_requise_w")) is None:
        _push_inconnue(
            rapport,
            "partielles",
            "puissance_alternateur_mecanique_requise_w",
            "Le rendement alternateur ou les pertes dimensionnantes manquent pour conclure la puissance mécanique requise.",
        )
    if _first_finite(bilan_bus_dc.get("puissance_moteur_thermique_requise_w")) is None:
        _push_inconnue(
            rapport,
            "partielles",
            "puissance_moteur_thermique_requise_w",
            "Le rendement de la liaison mécanique et/ou de la boîte manque pour conclure la puissance thermique requise.",
        )

    _dedup_inconnues(rapport)
    return rapport


def calculer_strategie_couplage(
    etat_systeme: Optional[Mapping[str, Any]] = None,
    composants: Optional[Mapping[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    return analyser_strategie_energie(etat_systeme=etat_systeme, composants=composants, **kwargs)


__all__ = [
    "ModeEnergetique",
    "EnveloppeBatterie",
    "determiner_enveloppe_batterie",
    "generer_cartographie_alternateur",
    "analyser_strategie_energie",
    "calculer_strategie_couplage",
]
