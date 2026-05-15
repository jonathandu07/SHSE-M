from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import inspect
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from backend.ensemble import calcul_stho_me as phys
except Exception:  # pragma: no cover
    import calcul_stho_me as phys  # type: ignore


def _is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _safe_float(value: Any) -> Optional[float]:
    return float(value) if _is_finite(value) else None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inconnues = rapport.setdefault("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        elements = list(inconnues.get(categorie, []) or [])
        uniques: List[Dict[str, str]] = []
        vus = set()
        for element in elements:
            if not isinstance(element, dict):
                continue
            cle = (str(element.get("nom", "?")), str(element.get("raison", "")))
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
        inc = _safe_dict(source.get("inconnues"))
        for categorie in ("impossibles", "partielles"):
            for item in list(inc.get(categorie, []) or []):
                if isinstance(item, dict):
                    bloc[categorie].append(
                        {"nom": str(item.get("nom", "?")), "raison": str(item.get("raison", ""))}
                    )
    return bloc


def _append_inconnues(rapport: Dict[str, Any], bloc: Mapping[str, Any]) -> None:
    for categorie in ("impossibles", "partielles"):
        for item in list(_safe_dict(bloc).get(categorie, []) or []):
            if isinstance(item, dict):
                _push_inconnue(rapport, categorie, item.get("nom", "?"), item.get("raison", ""))


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


@dataclass(frozen=True)
class ScoreLexico:
    statut_securite: int
    statut_meca: int
    statut_elec: int
    stress_batterie_connu: bool
    stress_batterie: Optional[float]
    pertes_electriques_connues: bool
    pertes_electriques_w: Optional[float]
    pertes_mecaniques_connues: bool
    pertes_mecaniques_w: Optional[float]
    rendement_connu: bool
    rendement: Optional[float]
    robustesse_connu: bool = False
    robustesse: Optional[float] = None


def cle_tri_score(score: ScoreLexico) -> Tuple[Any, ...]:
    # The known/unknown flag is compared before the numeric key. The zero fallback
    # below is only a placeholder for tuple construction and is never used to rank
    # a known value against an unknown one.
    stress_key = score.stress_batterie if score.stress_batterie is not None else 0.0
    pertes_elec_key = score.pertes_electriques_w if score.pertes_electriques_w is not None else 0.0
    pertes_meca_key = score.pertes_mecaniques_w if score.pertes_mecaniques_w is not None else 0.0
    rendement_key = -score.rendement if score.rendement is not None else 0.0
    robustesse_key = -score.robustesse if score.robustesse is not None else 0.0
    return (
        score.statut_securite,
        score.statut_meca,
        score.statut_elec,
        0 if score.stress_batterie_connu else 1,
        stress_key,
        0 if score.pertes_electriques_connues else 1,
        pertes_elec_key,
        0 if score.pertes_mecaniques_connues else 1,
        pertes_meca_key,
        0 if score.rendement_connu else 1,
        rendement_key,
        0 if score.robustesse_connu else 1,
        robustesse_key,
    )


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
    temp_c = _first_finite(etat.get("batterie_temp_c"), etat.get("temperature_pack_c"))
    temp_limite = _first_finite(
        etat.get("temperature_limite_pack_c"),
        _deep_get(rep_recharge, "securite_cellules", "temperature_limite_c"),
        getattr(batterie, "temp_cellule_critique_c", None),
        getattr(batterie, "temperature_critique_c", None),
        getattr(batterie, "temperature_alerte_c", None),
    )
    temp_derating = _first_finite(
        etat.get("temp_derating_seuil_c"),
        _deep_get(rep_recharge, "securite_cellules", "temp_derating_seuil_c"),
        getattr(batterie, "temp_derating_seuil_c", None),
    )
    soh = _first_finite(etat.get("batterie_soh"), getattr(batterie, "soh", None))

    p_charge_max_crate_w = None
    if c_rate_max is None or capacite_ah is None or tension_bus_v is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_crate_w",
            "Calculable si C-rate constructeur, capacite Ah et tension bus DC sont disponibles.",
        )
    else:
        p_charge_max_crate_w = float(c_rate_max) * float(capacite_ah) * float(tension_bus_v)

    p_charge_max_bus_w = _first_finite(
        etat.get("p_charge_max_bus_w"),
        (float(_deep_get(rep_recharge, "securite_cellules", "puissance_charge_max_autorisee_kw")) * 1000.0)
        if _is_finite(_deep_get(rep_recharge, "securite_cellules", "puissance_charge_max_autorisee_kw"))
        else None,
        getattr(batterie, "p_charge_max_bus_w", None),
    )
    if p_charge_max_bus_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_bus_w",
            "Aucune limite explicite de puissance de charge pack/BMS n'est disponible.",
        )

    p_charge_max_temp_w = None
    if temp_c is None or temp_limite is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_temp_w",
            "Temperature pack et temperature critique requises pour la limite thermique.",
        )
    elif float(temp_c) >= float(temp_limite):
        p_charge_max_temp_w = 0.0
    elif temp_derating is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_temp_w",
            "Seuil de derating thermique non fourni.",
        )
    elif float(temp_derating) >= float(temp_limite):
        _push_inconnue(
            rapport,
            "impossibles",
            "temp_derating_seuil_c",
            "Seuil de derating thermique incoherent avec la temperature critique.",
        )
    elif float(temp_c) > float(temp_derating):
        if p_charge_max_crate_w is None:
            _push_inconnue(
                rapport,
                "partielles",
                "p_charge_max_temp_w",
                "Le derating thermique progressif requiert aussi p_charge_max_crate_w.",
            )
        else:
            facteur = (float(temp_limite) - float(temp_c)) / (float(temp_limite) - float(temp_derating))
            p_charge_max_temp_w = float(p_charge_max_crate_w) * float(facteur)
    else:
        if p_charge_max_crate_w is None:
            _push_inconnue(
                rapport,
                "partielles",
                "p_charge_max_temp_w",
                "La temperature est admissible, mais aucune borne de puissance thermique n'est calculable sans limite de base.",
            )
        else:
            p_charge_max_temp_w = float(p_charge_max_crate_w)

    p_charge_max_soh_w = None
    loi_soh = getattr(batterie, "loi_reduction_puissance_soh", None)
    if soh is None:
        _push_inconnue(rapport, "partielles", "batterie_soh", "SoH non fourni.")
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_soh_w",
            "Impossible de conclure sans SoH explicite ou loi de reduction associee.",
        )
    elif p_charge_max_crate_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_soh_w",
            "Impossible sans p_charge_max_crate_w.",
        )
    elif callable(loi_soh):
        p_charge_max_soh_w = _safe_float(loi_soh(float(p_charge_max_crate_w), float(soh)))
        if p_charge_max_soh_w is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "p_charge_max_soh_w",
                "La loi explicite SoH -> puissance a renvoye une valeur non exploitable.",
            )
    else:
        _push_inconnue(
            rapport,
            "partielles",
            "p_charge_max_soh_w",
            "Loi de reduction de puissance liee au SoH non fournie.",
        )

    limites_numeriques: Dict[str, float] = {}
    for nom, valeur in (
        ("p_charge_max_soh_w", p_charge_max_soh_w),
        ("p_charge_max_temp_w", p_charge_max_temp_w),
        ("p_charge_max_crate_w", p_charge_max_crate_w),
        ("p_charge_max_bus_w", p_charge_max_bus_w),
    ):
        if valeur is not None:
            limites_numeriques[nom] = float(valeur)

    p_charge_recommandee_w = min(limites_numeriques.values()) if limites_numeriques else None
    limites_actives: List[str] = []
    if p_charge_recommandee_w is not None:
        for nom, valeur in limites_numeriques.items():
            if math.isclose(float(valeur), float(p_charge_recommandee_w), rel_tol=0.0, abs_tol=1e-12):
                limites_actives.append(nom)

    rapport["enveloppe"] = EnveloppeBatterie(
        p_charge_max_soh_w=p_charge_max_soh_w,
        p_charge_max_temp_w=p_charge_max_temp_w,
        p_charge_max_crate_w=p_charge_max_crate_w,
        p_charge_max_bus_w=p_charge_max_bus_w,
        p_charge_recommandee_w=p_charge_recommandee_w,
        limites_actives=limites_actives,
        raison_limitante=limites_actives[0] if limites_actives else None,
    ).vers_dict()
    _dedup_inconnues(rapport)
    return rapport


def valider_bornes_cartographie(bornes: Mapping[str, Any]) -> Tuple[bool, List[Dict[str, str]]]:
    erreurs: List[Dict[str, str]] = []
    rpm_min = _safe_float(bornes.get("rpm_min"))
    rpm_max = _safe_float(bornes.get("rpm_max"))
    rpm_step = _safe_float(bornes.get("rpm_step"))
    couple_min = _safe_float(bornes.get("couple_min"))
    couple_max = _safe_float(bornes.get("couple_max"))
    couple_step = _safe_float(bornes.get("couple_step"))

    for nom, valeur in (
        ("rpm_min", rpm_min),
        ("rpm_max", rpm_max),
        ("rpm_step", rpm_step),
        ("couple_min", couple_min),
        ("couple_max", couple_max),
        ("couple_step", couple_step),
    ):
        if valeur is None:
            erreurs.append({"nom": nom, "raison": "Borne absente ou non finie."})

    if rpm_step is not None and rpm_step <= 0.0:
        erreurs.append({"nom": "rpm_step", "raison": "Le pas de regime doit etre strictement positif."})
    if couple_step is not None and couple_step <= 0.0:
        erreurs.append({"nom": "couple_step", "raison": "Le pas de couple doit etre strictement positif."})
    if rpm_min is not None and rpm_max is not None and rpm_min > rpm_max:
        erreurs.append({"nom": "rpm_min/rpm_max", "raison": "rpm_min doit etre <= rpm_max."})
    if couple_min is not None and couple_max is not None and couple_min > couple_max:
        erreurs.append({"nom": "couple_min/couple_max", "raison": "couple_min doit etre <= couple_max."})
    return len(erreurs) == 0, erreurs


def _build_grid_from_bounds(minimum: float, maximum: float, step: float) -> List[float]:
    values: List[float] = []
    current = float(minimum)
    guard = 0
    while current <= float(maximum) + 1e-12:
        values.append(float(current))
        current += float(step)
        guard += 1
        if guard > 50000:  # pragma: no cover - safety bound only
            break
    return values


def _grid_from_inputs(
    explicit_grid: Optional[Sequence[Any]],
    minimum: Any,
    maximum: Any,
    step: Any,
    prefix: str,
) -> Tuple[Optional[List[float]], List[Dict[str, str]]]:
    if explicit_grid is not None:
        valeurs: List[float] = []
        for index, valeur in enumerate(explicit_grid):
            convertie = _safe_float(valeur)
            if convertie is None:
                return None, [{"nom": f"{prefix}[{index}]", "raison": "Valeur de grille non finie."}]
            valeurs.append(float(convertie))
        if not valeurs:
            return None, [{"nom": prefix, "raison": "Grille explicite vide."}]
        return valeurs, []

    bornes = {
        f"{prefix}_min": minimum,
        f"{prefix}_max": maximum,
        f"{prefix}_step": step,
    }
    if prefix == "rpm":
        valides, erreurs = valider_bornes_cartographie(
            {
                "rpm_min": minimum,
                "rpm_max": maximum,
                "rpm_step": step,
                "couple_min": 0.0,
                "couple_max": 0.0,
                "couple_step": 1.0,
            }
        )
        erreurs = [err for err in erreurs if err["nom"].startswith("rpm")]
    else:
        valides, erreurs = valider_bornes_cartographie(
            {
                "rpm_min": 0.0,
                "rpm_max": 0.0,
                "rpm_step": 1.0,
                "couple_min": minimum,
                "couple_max": maximum,
                "couple_step": step,
            }
        )
        erreurs = [err for err in erreurs if err["nom"].startswith("couple")]

    if not valides:
        return None, erreurs

    return _build_grid_from_bounds(float(minimum), float(maximum), float(step)), []


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
        "inconnues_globales": [],
        "notes_modele": [],
    }

    rpm_grid, rpm_errors = _grid_from_inputs(grille_rpm, rpm_min, rpm_max, rpm_step, "rpm")
    couple_grid, couple_errors = _grid_from_inputs(grille_couple_nm, couple_min, couple_max, couple_step, "couple")
    for erreur in rpm_errors:
        _push_inconnue(rapport, "impossibles", erreur["nom"], erreur["raison"])
        rapport["inconnues_globales"].append(erreur)
    for erreur in couple_errors:
        _push_inconnue(rapport, "impossibles", erreur["nom"], erreur["raison"])
        rapport["inconnues_globales"].append(erreur)
    if rpm_grid is None or couple_grid is None:
        _dedup_inconnues(rapport)
        return rapport

    rapport["grille_rpm"] = rpm_grid
    rapport["grille_couple_nm"] = couple_grid

    fn = getattr(alternateur, "analyser_point_de_fonctionnement", None)
    if not callable(fn):
        erreur = {
            "nom": "alternateur.analyser_point_de_fonctionnement",
            "raison": "Methode d'analyse alternateur absente.",
        }
        _push_inconnue(rapport, "impossibles", erreur["nom"], erreur["raison"])
        rapport["inconnues_globales"].append(erreur)
        _dedup_inconnues(rapport)
        return rapport

    sig = inspect.signature(fn)
    params = sig.parameters
    accepts_var_kw = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values())
    has_couple_nm = "couple_nm" in params
    has_couple_meca = "couple_mecanique_nm" in params
    if not (has_couple_nm or has_couple_meca or accepts_var_kw):
        erreur = {
            "nom": "alternateur.couple_nm",
            "raison": "La methode analyser_point_de_fonctionnement ne permet pas d'evaluer un point rpm x couple.",
        }
        _push_inconnue(rapport, "impossibles", erreur["nom"], erreur["raison"])
        rapport["inconnues_globales"].append(erreur)
        _dedup_inconnues(rapport)
        return rapport

    if tension_bus_dc_v is None:
        erreur = {"nom": "v_bus_dc_v", "raison": "Tension bus DC requise pour la cartographie alternateur."}
        _push_inconnue(rapport, "impossibles", erreur["nom"], erreur["raison"])
        rapport["inconnues_globales"].append(erreur)
        _dedup_inconnues(rapport)
        return rapport

    for rpm in rpm_grid:
        omega = 2.0 * math.pi * float(rpm) / 60.0
        for couple in couple_grid:
            point: Dict[str, Any] = {
                "rpm_alternateur": float(rpm),
                "couple_alternateur_nm": float(couple),
                "puissance_mecanique_w": float(couple) * float(omega),
                "puissance_electrique_w": None,
                "pertes_cuivre_w": None,
                "pertes_fer_w": None,
                "pertes_fixes_w": None,
                "pertes_totales_w": None,
                "rendement": None,
                "statut": "partiel",
                "inconnues": {"impossibles": [], "partielles": []},
            }
            kwargs: Dict[str, Any] = {
                "vitesse_rotation_rpm": float(rpm),
                "tension_v": float(tension_bus_dc_v),
            }
            if has_couple_nm or accepts_var_kw:
                kwargs["couple_nm"] = float(couple)
            elif has_couple_meca:
                kwargs["couple_mecanique_nm"] = float(couple)

            try:
                rep = fn(**kwargs)
            except Exception as exc:
                _push_inconnue(point, "impossibles", "alternateur.point", f"Echec de l'analyse du point : {exc}")
                point["statut"] = "impossible"
                rapport["points"].append(point)
                continue

            rep_dict = _safe_dict(rep)
            point["puissance_electrique_w"] = _first_finite(
                _deep_get(rep_dict, "sortie_electrique", "puissance_utile_w"),
                _deep_get(rep_dict, "electrique", "puissance_utile_w"),
                _deep_get(rep_dict, "puissance_electrique_w"),
            )
            point["pertes_cuivre_w"] = _first_finite(
                _deep_get(rep_dict, "pertes", "pertes_cuivre_w"),
                _deep_get(rep_dict, "electrique", "pertes_cuivre_w"),
            )
            point["pertes_fer_w"] = _first_finite(
                _deep_get(rep_dict, "pertes", "pertes_fer_w"),
                _deep_get(rep_dict, "electrique", "pertes_fer_w"),
            )
            point["pertes_fixes_w"] = _first_finite(
                _deep_get(rep_dict, "pertes", "pertes_fixes_w"),
                getattr(alternateur, "pertes_fixes_w", None),
            )
            point["pertes_totales_w"] = _first_finite(
                _deep_get(rep_dict, "pertes", "pertes_connues_total_w"),
                _deep_get(rep_dict, "pertes", "pertes_totales_w"),
            )
            point["rendement"] = _first_finite(
                _deep_get(rep_dict, "rendement", "rendement_impose"),
                _deep_get(rep_dict, "rendement", "eta_sur_pertes_connues"),
                _deep_get(rep_dict, "rendement", "rendement"),
            )
            point["inconnues"] = _collect_inconnues(rep_dict)
            if point["puissance_electrique_w"] is None:
                _push_inconnue(
                    point,
                    "partielles",
                    "puissance_electrique_w",
                    "La puissance electrique de sortie n'est pas fournie par l'API alternateur.",
                )
            if point["inconnues"]["impossibles"]:
                point["statut"] = "impossible"
            elif point["inconnues"]["partielles"]:
                point["statut"] = "partiel"
            else:
                point["statut"] = "ok"
            rapport["points"].append(point)

    _dedup_inconnues(rapport)
    return rapport


def _current_from_power(power_w: Optional[float], tension_v: Optional[float]) -> Optional[float]:
    if power_w is None or tension_v is None or float(tension_v) <= 0.0:
        return None
    return float(power_w) / float(tension_v)


def _make_score(candidate: Dict[str, Any]) -> ScoreLexico:
    return ScoreLexico(
        statut_securite=1 if candidate.get("dangereux") else 0,
        statut_meca=1 if candidate.get("mecanique_impossible") else 0,
        statut_elec=1 if candidate.get("electrique_impossible") else 0,
        stress_batterie_connu=_is_finite(candidate.get("stress_batterie")),
        stress_batterie=_safe_float(candidate.get("stress_batterie")),
        pertes_electriques_connues=_is_finite(candidate.get("pertes_electriques_w")),
        pertes_electriques_w=_safe_float(candidate.get("pertes_electriques_w")),
        pertes_mecaniques_connues=_is_finite(candidate.get("pertes_mecaniques_w")),
        pertes_mecaniques_w=_safe_float(candidate.get("pertes_mecaniques_w")),
        rendement_connu=_is_finite(candidate.get("rendement_global")),
        rendement=_safe_float(candidate.get("rendement_global")),
        robustesse_connu=_is_finite(candidate.get("robustesse")),
        robustesse=_safe_float(candidate.get("robustesse")),
    )


def _build_candidates(
    *,
    rapport_boite: Optional[Mapping[str, Any]],
    p_gen_req_w: Optional[float],
    tolerance_puissance_relative: Optional[float],
    tension_bus_dc_v: Optional[float],
    capacite_ah: Optional[float],
    resistance_interne_ohm: Optional[float],
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, str]]]]:
    candidats: List[Dict[str, Any]] = []
    inconnues = {"impossibles": [], "partielles": []}
    if not isinstance(rapport_boite, Mapping):
        return candidats, inconnues

    for brut in list(rapport_boite.get("candidats", []) or []):
        if not isinstance(brut, Mapping):
            continue
        cand = dict(brut)
        alt_rep = _safe_dict(cand.get("alternateur"))
        boite_rep = _safe_dict(cand.get("boite"))
        exigences = _safe_dict(cand.get("exigences"))
        inc_local = _collect_inconnues(alt_rep, boite_rep)

        p_elec = _first_finite(exigences.get("P_out_W"), cand.get("puissance_electrique_w"))
        if tolerance_puissance_relative is not None and p_gen_req_w is not None and p_elec is not None:
            if float(p_gen_req_w) <= 0.0:
                inc_local["impossibles"].append(
                    {
                        "nom": "puissance_generateur_requise_w",
                        "raison": "La puissance generateur requise doit etre > 0 pour filtrer les candidats.",
                    }
                )
            else:
                ecart = abs(float(p_elec) - float(p_gen_req_w)) / float(p_gen_req_w)
                if ecart > float(tolerance_puissance_relative):
                    continue

        courant_bus_a = _first_finite(
            _deep_get(alt_rep, "bus_dc", "courant_bus_dc_A"),
            _deep_get(alt_rep, "bus_dc", "courant_bus_dc_a"),
            _current_from_power(p_elec, tension_bus_dc_v),
        )

        stress_batterie = None
        if courant_bus_a is None:
            inc_local["partielles"].append(
                {"nom": "stress_batterie", "raison": "Courant bus DC requis pour calculer le stress batterie."}
            )
        elif capacite_ah is None:
            inc_local["partielles"].append(
                {"nom": "stress_batterie", "raison": "Capacite batterie requise pour calculer le C-rate."}
            )
        else:
            stress_batterie = phys.calculer_c_rate(float(courant_bus_a), float(capacite_ah))

        pertes_joule_w = None
        if courant_bus_a is not None and resistance_interne_ohm is not None:
            pertes_joule_w = phys.pertes_joule_interne(float(courant_bus_a), float(resistance_interne_ohm))
        elif courant_bus_a is not None and resistance_interne_ohm is None:
            inc_local["partielles"].append(
                {
                    "nom": "pertes_joule_batterie_w",
                    "raison": "Resistance interne batterie requise pour conclure les pertes Joule.",
                }
            )

        pertes_alt = _first_finite(
            exigences.get("P_pertes_alternateur_W"),
            _deep_get(alt_rep, "alternateur", "pertes", "pertes_connues_total_w"),
            _deep_get(alt_rep, "pertes", "pertes_connues_total_w"),
        )
        pertes_electriques_w = None
        if pertes_alt is not None and pertes_joule_w is not None:
            pertes_electriques_w = float(pertes_alt) + float(pertes_joule_w)
        elif pertes_alt is None or pertes_joule_w is None:
            inc_local["partielles"].append(
                {
                    "nom": "pertes_electriques_w",
                    "raison": "Les pertes alternateur et les pertes Joule doivent etre connues pour fermer les pertes electriques.",
                }
            )

        p_meca_alt = _first_finite(
            exigences.get("P_mecanique_alternateur_W"),
            _deep_get(alt_rep, "alternateur", "mecanique", "puissance_mecanique_dimensionnante_w"),
            _deep_get(alt_rep, "mecanique", "puissance_mecanique_dimensionnante_w"),
        )
        p_mt_req = _first_finite(exigences.get("puissance_moteur_requise_W"))
        pertes_mecaniques_w = None
        if p_mt_req is not None and p_meca_alt is not None:
            pertes_mecaniques_w = float(p_mt_req) - float(p_meca_alt)
        else:
            inc_local["partielles"].append(
                {
                    "nom": "pertes_mecaniques_w",
                    "raison": "Puissance mecanique alternateur et puissance thermique requise sont necessaires.",
                }
            )

        rendement_global = None
        if p_elec is not None and p_mt_req is not None and float(p_mt_req) > 0.0:
            rendement_global = float(p_elec) / float(p_mt_req)

        robuste = 1.0 / float(cand.get("rapport")) if _is_finite(cand.get("rapport")) and float(cand.get("rapport")) > 0.0 else None

        candidat = {
            "rapport": cand.get("rapport"),
            "rpm_alternateur": cand.get("rpm_alternateur"),
            "alternateur": alt_rep,
            "boite": boite_rep,
            "exigences": exigences,
            "courant_bus_dc_a": courant_bus_a,
            "stress_batterie": stress_batterie,
            "pertes_joule_batterie_w": pertes_joule_w,
            "pertes_electriques_w": pertes_electriques_w,
            "pertes_mecaniques_w": pertes_mecaniques_w,
            "rendement_global": rendement_global,
            "robustesse": robuste,
            "dangereux": bool(
                _deep_get(alt_rep, "alternateur", "thermique", "ok_temperature_sur_pertes_connues") is False
                or _deep_get(alt_rep, "thermique", "ok_temperature_sur_pertes_connues") is False
            ),
            "mecanique_impossible": _first_finite(
                exigences.get("couple_moteur_requis_Nm"),
                exigences.get("couple_moteur_min_theorique_Nm"),
            )
            is None,
            "electrique_impossible": p_elec is None,
            "inconnues": inc_local,
        }
        candidat["score_lexico"] = _make_score(candidat)
        candidats.append(candidat)

    return candidats, inconnues


def _validation_transitoire(
    *,
    point_actuel: Optional[Mapping[str, Any]],
    point_cible: Optional[Mapping[str, Any]],
    resistance_thermique_k_w: Optional[float],
    capacite_thermique_j_k: Optional[float],
    t_s: Optional[float],
    tolerance_transitoire_relative: Optional[float],
) -> Dict[str, Any]:
    rapport: Dict[str, Any] = {
        "statut": "impossible",
        "point_actuel": _safe_dict(point_actuel),
        "point_cible": _safe_dict(point_cible),
        "tau_s": None,
        "rampe_puissance_w_s": None,
        "p_accessible_w": None,
        "inconnues": [],
    }

    manquants: List[str] = []
    if point_actuel is None:
        manquants.append("point_actuel_thermique")
    if point_cible is None:
        manquants.append("point_cible_thermique")
    if t_s is None:
        manquants.append("temps_disponible_s")
    if resistance_thermique_k_w is None:
        manquants.append("deplaceur.resistance_thermique_k_w")
    if capacite_thermique_j_k is None:
        manquants.append("deplaceur.capacite_thermique_j_k")
    if manquants:
        rapport["inconnues"] = manquants
        return rapport

    rpm_init = _first_finite(_deep_get(point_actuel, "rpm"), _deep_get(point_actuel, "rpm_moteur"))
    couple_init = _first_finite(_deep_get(point_actuel, "couple_nm"), _deep_get(point_actuel, "couple_moteur_requis_Nm"))
    rpm_cible = _first_finite(_deep_get(point_cible, "rpm"), _deep_get(point_cible, "rpm_moteur"))
    couple_cible = _first_finite(_deep_get(point_cible, "couple_nm"), _deep_get(point_cible, "couple_moteur_requis_Nm"))
    if rpm_init is None or couple_init is None or rpm_cible is None or couple_cible is None:
        rapport["inconnues"].append("rpm/couple_points")
        return rapport

    tau_s = phys.constante_temps_thermique(float(resistance_thermique_k_w), float(capacite_thermique_j_k))
    omega_init = 2.0 * math.pi * float(rpm_init) / 60.0
    omega_cible = 2.0 * math.pi * float(rpm_cible) / 60.0
    p_init = float(couple_init) * float(omega_init)
    p_cible = float(couple_cible) * float(omega_cible)
    p_accessible = phys.reponse_transitoire_premier_ordre(float(p_init), float(p_cible), float(t_s), float(tau_s))

    rapport["tau_s"] = float(tau_s)
    rapport["rampe_puissance_w_s"] = (float(p_accessible) - float(p_init)) / float(t_s)
    rapport["p_accessible_w"] = float(p_accessible)
    rapport["point_actuel"] = {"rpm": float(rpm_init), "couple_nm": float(couple_init), "puissance_w": float(p_init)}
    rapport["point_cible"] = {"rpm": float(rpm_cible), "couple_nm": float(couple_cible), "puissance_w": float(p_cible)}

    if tolerance_transitoire_relative is None:
        rapport["statut"] = "partiel"
        rapport["raison"] = "Puissance accessible calculee, mais tolerance transitoire non fournie."
        return rapport
    if not _is_finite(tolerance_transitoire_relative) or float(tolerance_transitoire_relative) < 0.0:
        rapport["statut"] = "impossible"
        rapport["raison"] = "Tolerance transitoire invalide."
        rapport["inconnues"].append("tolerance_transitoire_relative")
        return rapport
    if float(p_cible) <= 0.0:
        rapport["statut"] = "impossible"
        rapport["raison"] = "Puissance cible invalide pour la validation transitoire."
        rapport["inconnues"].append("point_cible_thermique.puissance_w")
        return rapport

    ecart = abs(float(p_accessible) - float(p_cible)) / float(p_cible)
    rapport["statut"] = "ok" if ecart <= float(tolerance_transitoire_relative) else "partiel"
    rapport["ecart_relatif"] = float(ecart)
    return rapport


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
            "p_accessible_w": None,
            "inconnues": [],
        },
        "derivees_chaine_energie": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "alertes": {},
        "notes_modele": [],
    }

    batterie = composants_loc.get("batterie")
    alternateur = composants_loc.get("alternateur")
    boite = composants_loc.get("boite_crabots")
    moteur_thermique = composants_loc.get("moteur_thermique")
    deplaceur = composants_loc.get("deplaceur")

    if batterie is None:
        _push_inconnue(rapport, "impossibles", "batterie", "Composant batterie requis pour la strategie energetique.")
        return rapport
    if poids_cout:
        _append_note(
            rapport,
            "Des poids explicites ont ete fournis. La selection lexicographique reste prioritaire tant qu'un autre mode de cout n'est pas demande.",
        )

    env_report = determiner_enveloppe_batterie(
        batterie=batterie,
        etat_systeme=etat,
        rapport_batterie=rapport_batterie,
        rapport_recharge_batterie=rapport_recharge_batterie,
    )
    rapport["enveloppe_batterie"] = env_report["enveloppe"]
    _append_inconnues(rapport, env_report["inconnues"])

    tension_bus_dc_v = _first_finite(etat.get("v_bus_dc_v"), derivees.get("tension_bus_dc_v"))
    if tension_bus_dc_v is None:
        _push_inconnue(rapport, "impossibles", "v_bus_dc_v", "Tension bus DC requise.")

    p_sortie_w = _first_finite(
        etat.get("puissance_sortie_demandee_w"),
        derivees.get("sortie_utilisateur_w"),
        etat.get("puissance_traction_roue_w"),
    )
    p_usage_w = _first_finite(
        etat.get("puissance_elec_usage_w"),
        etat.get("p_traction_bus_dc_w"),
        derivees.get("puissance_elec_usage_w"),
    )
    if p_usage_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "p_traction_bus_dc_w",
            "Puissance electrique moteur requise absente ; aucun fallback P_bus = P_sortie n'est autorise.",
        )

    p_aux_w = _first_finite(etat.get("puissance_auxiliaire_w"), derivees.get("puissance_auxiliaire_w"))
    if p_aux_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "puissance_auxiliaire_w",
            "Puissance auxiliaire absente ; la puissance bus DC totale restera partielle.",
        )

    p_recharge_demandee_w = _first_finite(
        etat.get("p_recharge_demandee_w"),
        derivees.get("puissance_recharge_batterie_w"),
    )
    beta = _first_finite(
        etat.get("fraction_temps_generation_beta"),
        derivees.get("fraction_temps_generation_beta"),
    )

    mode: ModeEnergetique
    if mode_force in {item.value for item in ModeEnergetique}:
        mode = ModeEnergetique(mode_force)
    elif p_recharge_demandee_w is not None and p_recharge_demandee_w > 0.0:
        mode = ModeEnergetique.RECHARGE_BATTERIE
    elif p_usage_w is not None and p_usage_w > 0.0:
        mode = ModeEnergetique.SOUTIEN_TRACTION
    else:
        mode = ModeEnergetique.EV_ONLY

    enveloppe = _safe_dict(rapport["enveloppe_batterie"])
    p_recharge_cible_w: Optional[float]
    raison_charge = None
    if mode in (ModeEnergetique.EV_ONLY, ModeEnergetique.SOUTIEN_TRACTION, ModeEnergetique.MODE_DEGRADE):
        p_recharge_cible_w = 0.0
        raison_charge = "Recharge non demandee par le mode energetique."
    elif mode in (ModeEnergetique.RECHARGE_BATTERIE, ModeEnergetique.MAINTIEN_SOC, ModeEnergetique.URGENCE_PUISSANCE):
        p_recharge_limite_w = _first_finite(enveloppe.get("p_charge_recommandee_w"))
        if p_recharge_demandee_w is None:
            p_recharge_cible_w = None
            _push_inconnue(
                rapport,
                "partielles",
                "p_recharge_demandee_w",
                "Le mode energetique demande une recharge mais la puissance de recharge demandee est absente.",
            )
        elif p_recharge_limite_w is None:
            p_recharge_cible_w = None
            _push_inconnue(
                rapport,
                "partielles",
                "p_charge_recommandee_w",
                "Le mode energetique demande une recharge mais l'enveloppe batterie est incomplete.",
            )
        else:
            p_recharge_cible_w = min(float(p_recharge_demandee_w), float(p_recharge_limite_w))
            raison_charge = "Recharge limitee par l'enveloppe batterie." if p_recharge_cible_w < float(p_recharge_demandee_w) else "Recharge autorisee."
            if p_recharge_cible_w <= 0.0:
                if autoriser_soutien_traction_si_recharge_interdite and p_usage_w is not None and p_usage_w > 0.0:
                    mode = ModeEnergetique.SOUTIEN_TRACTION
                    p_recharge_cible_w = 0.0
                    raison_charge = "Recharge interdite ; soutien traction maintenu."
                else:
                    mode = ModeEnergetique.MODE_DEGRADE
                    p_recharge_cible_w = 0.0
                    raison_charge = "Recharge interdite par la batterie."
    else:  # pragma: no cover - exhaustive safety
        p_recharge_cible_w = None

    p_bus_total_w = _first_finite(etat.get("puissance_bus_dc_totale_w"), derivees.get("puissance_bus_dc_totale_w"))
    if p_bus_total_w is None:
        if p_usage_w is None:
            _push_inconnue(rapport, "impossibles", "puissance_bus_dc_totale_w", "Impossible sans puissance electrique d'usage.")
        elif p_aux_w is None:
            _push_inconnue(rapport, "partielles", "puissance_bus_dc_totale_w", "Puissance auxiliaire absente.")
        elif p_recharge_cible_w is None:
            _push_inconnue(rapport, "partielles", "puissance_bus_dc_totale_w", "Puissance de recharge cible absente.")
        else:
            p_bus_total_w = float(p_usage_w) + float(p_aux_w) + float(p_recharge_cible_w)

    p_bus_inst_w = _first_finite(etat.get("puissance_bus_dc_instantanee_w"), derivees.get("puissance_bus_dc_instantanee_w"))
    if p_bus_inst_w is None:
        if p_bus_total_w is None:
            _push_inconnue(rapport, "partielles", "puissance_bus_dc_instantanee_w", "Puissance bus totale absente.")
        elif beta is None:
            _push_inconnue(
                rapport,
                "partielles",
                "fraction_temps_generation_beta",
                "beta absent : pas de generation intermittente calculee.",
            )
        elif not _is_finite(beta) or float(beta) <= 0.0 or float(beta) > 1.0:
            _push_inconnue(rapport, "impossibles", "fraction_temps_generation_beta", "beta doit etre dans ]0, 1].")
        else:
            p_bus_inst_w = float(p_bus_total_w) / float(beta)

    tolerance_puissance_relative = _safe_float(etat.get("tolerance_puissance_relative"))
    if etat.get("tolerance_puissance_relative") is None:
        _push_inconnue(
            rapport,
            "partielles",
            "tolerance_puissance_relative",
            "Tolerance absente : filtrage par proximite de puissance non realise.",
        )
    elif tolerance_puissance_relative is None or float(tolerance_puissance_relative) < 0.0:
        _push_inconnue(
            rapport,
            "impossibles",
            "tolerance_puissance_relative",
            "Tolerance invalide.",
        )
        tolerance_puissance_relative = None

    carto_bornes = _safe_dict(etat.get("bornes_cartographie_alternateur"))
    if alternateur is not None and carto_bornes:
        carto = generer_cartographie_alternateur(
            alternateur=alternateur,
            tension_bus_dc_v=tension_bus_dc_v,
            rpm_min=_safe_float(carto_bornes.get("rpm_min")),
            rpm_max=_safe_float(carto_bornes.get("rpm_max")),
            rpm_step=_safe_float(carto_bornes.get("rpm_step")),
            couple_min=_safe_float(carto_bornes.get("couple_min")),
            couple_max=_safe_float(carto_bornes.get("couple_max")),
            couple_step=_safe_float(carto_bornes.get("couple_step")),
        )
        for inc in list(carto.get("inconnues_globales", []) or []):
            if isinstance(inc, dict):
                _push_inconnue(rapport, "impossibles", inc.get("nom", "?"), inc.get("raison", ""))
        rapport["cartographie_alternateur"] = carto

    if boite is None or getattr(boite, "rapports", None) is None:
        _push_inconnue(
            rapport,
            "impossibles",
            "boite_crabots.rapports",
            "Rapports de boite absents : impossible de relier alternateur et moteur thermique.",
        )
    if moteur_thermique is not None:
        rpm_min_mt = getattr(moteur_thermique, "rpm_min", None)
        rpm_max_mt = getattr(moteur_thermique, "rpm_max", None)
        if rpm_min_mt is None or rpm_max_mt is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "moteur_thermique.rpm_min/rpm_max",
                "Plage de regime moteur thermique absente.",
            )

    candidats, inconnues_candidats = _build_candidates(
        rapport_boite=rapport_boite,
        p_gen_req_w=p_bus_inst_w if p_bus_inst_w is not None else p_bus_total_w,
        tolerance_puissance_relative=tolerance_puissance_relative,
        tension_bus_dc_v=tension_bus_dc_v,
        capacite_ah=_extract_battery_capacity_ah(batterie, rapport_batterie),
        resistance_interne_ohm=_first_finite(
            etat.get("resistance_interne_batterie_ohm"),
            _deep_get(rapport_batterie, "electrique", "resistance_interne_pack_ohm"),
        ),
    )
    rapport["candidats"] = candidats
    _append_inconnues(rapport, inconnues_candidats)

    if not candidats:
        _push_inconnue(
            rapport,
            "impossibles",
            "point_retenu",
            "Aucun candidat exploitable n'est disponible pour la chaine alternateur/boite/moteur thermique.",
        )
    else:
        point_retenu = min(candidats, key=lambda item: cle_tri_score(item["score_lexico"]))
        rapport["point_retenu"] = point_retenu
        _append_inconnues(rapport, point_retenu.get("inconnues", {}))

    p_alt_meca_req_w = _first_finite(
        derivees.get("puissance_mecanique_alternateur_requise_w"),
        _deep_get(rapport["point_retenu"], "exigences", "P_mecanique_alternateur_W"),
        _deep_get(rapport["point_retenu"], "alternateur", "mecanique", "puissance_mecanique_dimensionnante_w"),
    )
    if p_alt_meca_req_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "puissance_mecanique_alternateur_requise_w",
            "Rendement alternateur absent ou analyse alternateur incomplète.",
        )

    p_mt_req_w = _first_finite(
        derivees.get("puissance_moteur_thermique_requise_w"),
        _deep_get(rapport["point_retenu"], "exigences", "puissance_moteur_requise_W"),
    )
    if p_mt_req_w is None:
        _push_inconnue(
            rapport,
            "partielles",
            "puissance_moteur_thermique_requise_w",
            "Rendement boite/liaison absent ou analyse mecanique incomplete.",
        )

    couple_alt_nm = _first_finite(
        _deep_get(rapport["point_retenu"], "alternateur", "mecanique", "couple_mecanique_dimensionnant_nm"),
        _deep_get(rapport["point_retenu"], "couple_alternateur_nm"),
    )
    if couple_alt_nm is None:
        _push_inconnue(
            rapport,
            "partielles",
            "couple_alternateur_nm",
            "Couple alternateur non fourni par les analyses disponibles.",
        )

    bilan_bus_dc = {
        "puissance_sortie_demandee_w": p_sortie_w,
        "puissance_electrique_usage_w": p_usage_w,
        "puissance_auxiliaire_w": p_aux_w,
        "puissance_recharge_demandee_w": p_recharge_demandee_w,
        "p_charge_cible_w": p_recharge_cible_w,
        "puissance_recharge_retenue_w": p_recharge_cible_w,
        "puissance_bus_dc_totale_w": p_bus_total_w,
        "puissance_bus_dc_instantanee_w": p_bus_inst_w,
        "tension_bus_dc_v": tension_bus_dc_v,
        "courant_bus_dc_a": _current_from_power(p_bus_total_w, tension_bus_dc_v),
        "fraction_temps_generation_beta": beta,
        "puissance_alternateur_electrique_requise_w": p_bus_inst_w if p_bus_inst_w is not None else p_bus_total_w,
        "puissance_mecanique_alternateur_requise_w": p_alt_meca_req_w,
        "couple_alternateur_nm": couple_alt_nm,
        "regime_alternateur_rpm": _first_finite(_deep_get(rapport["point_retenu"], "rpm_alternateur")),
        "rapport_boite_optimal": _first_finite(_deep_get(rapport["point_retenu"], "rapport")),
        "regime_moteur_thermique_rpm": None,
        "couple_moteur_thermique_nm": _first_finite(
            _deep_get(rapport["point_retenu"], "exigences", "couple_moteur_requis_Nm"),
            _deep_get(rapport["point_retenu"], "exigences", "couple_moteur_min_theorique_Nm"),
        ),
        "puissance_moteur_thermique_requise_w": p_mt_req_w,
        "raison_charge": raison_charge,
    }
    if _is_finite(bilan_bus_dc["regime_alternateur_rpm"]) and _is_finite(bilan_bus_dc["rapport_boite_optimal"]) and float(bilan_bus_dc["rapport_boite_optimal"]) != 0.0:
        bilan_bus_dc["regime_moteur_thermique_rpm"] = float(bilan_bus_dc["regime_alternateur_rpm"]) / float(bilan_bus_dc["rapport_boite_optimal"])
    if p_sortie_w is not None and p_mt_req_w is not None and float(p_mt_req_w) > 0.0:
        bilan_bus_dc["rendement_global_calcule"] = float(p_sortie_w) / float(p_mt_req_w)
    else:
        bilan_bus_dc["rendement_global_calcule"] = None
    rapport["bilan_bus_dc"] = bilan_bus_dc

    rapport["derivees_chaine_energie"] = {
        **dict(derivees),
        "puissance_recharge_batterie_retenue_w": p_recharge_cible_w,
        "puissance_bus_dc_totale_retenue_w": p_bus_total_w,
        "puissance_bus_dc_instantanee_retenue_w": p_bus_inst_w,
        "mode_energetique_retenu": mode.value,
        "raison_limitante_batterie": enveloppe.get("raison_limitante"),
    }

    if rapport["point_retenu"] is not None:
        rapport["decision"] = {
            "mode_energetique": mode.value,
            "raison_choix": "Selection lexicographique : securite, faisabilite, preservation batterie, pertes, rendement, robustesse.",
            "rapport_boite": _deep_get(rapport["point_retenu"], "rapport"),
            "limitation_batterie": enveloppe.get("raison_limitante"),
            "puissance_recharge_retenue_w": p_recharge_cible_w,
        }

    point_cible = None
    if rapport["point_retenu"] is not None:
        point_cible = {
            "rpm": bilan_bus_dc.get("regime_moteur_thermique_rpm"),
            "couple_nm": bilan_bus_dc.get("couple_moteur_thermique_nm"),
        }
    rapport["validation_transitoire"] = _validation_transitoire(
        point_actuel=point_actuel or _safe_dict(etat.get("point_actuel_thermique")),
        point_cible=point_cible,
        resistance_thermique_k_w=_first_finite(
            etat.get("resistance_thermique_k_w"),
            getattr(deplaceur, "resistance_thermique_k_w", None),
        ),
        capacite_thermique_j_k=_first_finite(
            etat.get("capacite_thermique_j_k"),
            getattr(deplaceur, "capacite_thermique_j_k", None),
        ),
        t_s=_first_finite(etat.get("temps_disponible_s")),
        tolerance_transitoire_relative=_safe_float(etat.get("tolerance_transitoire_relative")),
    )

    rapport["mode_energetique"] = mode.value
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
    "ScoreLexico",
    "cle_tri_score",
    "valider_bornes_cartographie",
    "determiner_enveloppe_batterie",
    "generer_cartographie_alternateur",
    "analyser_strategie_energie",
    "calculer_strategie_couplage",
]
