# backend/components/moteur_electrique.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple


# =============================================================================
# Imports des modules "métier" (robustes)
# =============================================================================
# IMPORTANT : aucun "valeur typique" injectée ici.
# Si un module n'est pas trouvable, on échoue explicitement.

try:
    # Arborescence préférée (cohérente avec tes fichiers uploadés)
    from backend.components.moteur_electrique.modules.calcul_force_resistance_vitesse import calcul_force_resistance_totale
    from backend.components.moteur_electrique.modules.calcul_puissance_roue import (
        calcul_puissance_roue,
        calcul_couple_roue_total,
        calcul_couple_par_roue,
    )
    from backend.components.moteur_electrique.modules.calcul_puissance_moteur import (
        calcul_puissance_moteur_electrique,
        calcul_couple_moteur,
    )
    from backend.components.moteur_electrique.modules.calcul_charge_essieu import calcul_charges_essieux
    from backend.components.moteur_electrique.modules.calcul_acceleration_max import calcul_acceleration_max

    # optionnel (si présent dans ton projet)
    try:
        from backend.components.moteur_electrique.modules.calcul_multi_domaine import (
            calcul_demande_nautique as _md_nautique,
            calcul_demande_aerien_rho as _md_aerien_rho,
            calcul_demande_ferroviaire_davis as _md_ferro_davis,
            calcul_densite_air_sec as _md_rho_air_sec,
        )
    except Exception:
        _md_nautique = None  # type: ignore
        _md_aerien_rho = None  # type: ignore
        _md_ferro_davis = None  # type: ignore
        _md_rho_air_sec = None  # type: ignore

except Exception:
    try:
        # fallback legacy: backend/modules/vehicule/...
        from backend.modules.vehicule.calcul_force_resistance_vitesse import calcul_force_resistance_totale
        from backend.modules.vehicule.calcul_puissance_roue import (
            calcul_puissance_roue,
            calcul_couple_roue_total,
            calcul_couple_par_roue,
        )
        from backend.modules.vehicule.calcul_puissance_moteur import (
            calcul_puissance_moteur_electrique,
            calcul_couple_moteur,
        )
        from backend.modules.vehicule.calcul_charge_essieu import calcul_charges_essieux
        from backend.modules.vehicule.calcul_acceleration_max import calcul_acceleration_max

        _md_nautique = None  # type: ignore
        _md_aerien_rho = None  # type: ignore
        _md_ferro_davis = None  # type: ignore
        _md_rho_air_sec = None  # type: ignore

    except Exception as e:
        raise ImportError(
            "Impossible d'importer les modules de calcul. "
            "Ajuste les chemins d'import dans backend/components/moteur_electrique.py "
            f"(erreur d'import: {e})."
        )


# =============================================================================
# Helpers (validation + conversions)
# =============================================================================

DriveMode = Literal["FWD", "RWD", "AWD"]
AngleUnit = Literal["rad", "deg"]
Domaine = Literal["routier", "nautique", "aerien", "ferroviaire"]

_G0 = 9.80665  # constante physique (standard)


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _req_ratio_0_1(name: str, x: Any, *, strict_min: bool = True) -> float:
    v = _req_finite(name, x)
    if strict_min:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    if v > 1.0:
        raise ValueError(f"{name} doit être <= 1 (reçu: {v}).")
    return v


def rpm_to_rad_s(rpm: float) -> float:
    rpm = _req_finite("rpm", rpm)
    return (2.0 * math.pi) * (rpm / 60.0)


def rad_s_to_rpm(omega: float) -> float:
    omega = _req_finite("omega", omega)
    return (omega * 60.0) / (2.0 * math.pi)


def _push_inc(rapport: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rapport["inconnues"][cat].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[dict]) -> List[dict]:
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


def _wh_per_km_from_p_v(p_w: float, v_ms: float) -> float:
    # Wh/km = (P / v) * (1000 / 3600)
    P = _req_pos("p_w", p_w, strict=False)
    v = _req_pos("v_ms", v_ms, strict=True)
    if P == 0.0:
        return 0.0
    return (P / v) * (1000.0 / 3600.0)


def _bisect_monotone(
    f: Any,
    target: float,
    v_lo: float,
    v_hi: float,
    *,
    max_iter: int = 200,
    rel_tol: float = 1e-7,
    abs_tol: float = 1e-9,
) -> float:
    """
    Résout f(v)=target pour f croissante sur [v_lo, v_hi], par dichotomie.
    """
    t = _req_pos("target", target, strict=False)
    lo = _req_pos("v_lo", v_lo, strict=False)
    hi = _req_pos("v_hi", v_hi, strict=True)

    f_lo = float(f(lo))
    f_hi = float(f(hi))

    if f_lo > t:
        return lo
    if f_hi < t:
        return hi

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = float(f(mid))
        err = f_mid - t
        if abs(err) <= max(abs_tol, rel_tol * max(1.0, t)):
            return mid
        if f_mid < t:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _get_req(params: Dict[str, Any], key: str) -> Any:
    if key not in params:
        raise KeyError(f"Paramètre manquant: {key}")
    return params[key]


# =============================================================================
# Modèle moteur: couple/puissance sans hypothèses
# =============================================================================

@dataclass(frozen=True)
class MoteurElectrique:
    """
    Modèle simple d'un moteur électrique, sans valeurs "typées" imposées.

    Requis:
      - puissance_max_w
      - regime_max_rpm
      - ET (couple_max_nm OU regime_base_rpm)
        (pour définir la courbe couple constant -> puissance constante)

    Rendements / pertes:
      - rendement_moteur, pertes_fixes_w ne sont utilisés QUE pour estimer une
        puissance électrique (approx). Si tu ne les fournis pas: on ne les invente pas.
    """

    puissance_max_w: float
    regime_max_rpm: float

    couple_max_nm: Optional[float] = None
    regime_base_rpm: Optional[float] = None

    # Optionnels (aucune valeur par défaut “typique”)
    rendement_moteur: Optional[float] = None          # mech / elec
    rendement_transmission: Optional[float] = None    # roue / moteur (si tu veux stocker ici)

    tension_bus_v: Optional[float] = None
    courant_max_a: Optional[float] = None

    pertes_fixes_w: float = 0.0

    def __post_init__(self) -> None:
        _req_pos("puissance_max_w", self.puissance_max_w, strict=True)
        _req_pos("regime_max_rpm", self.regime_max_rpm, strict=True)
        _req_finite("pertes_fixes_w", self.pertes_fixes_w)

        if (self.couple_max_nm is None) and (self.regime_base_rpm is None):
            raise ValueError(
                "Il faut fournir 'couple_max_nm' OU 'regime_base_rpm' "
                "pour définir une courbe couple/puissance sans hypothèses."
            )

        if self.couple_max_nm is not None:
            _req_pos("couple_max_nm", self.couple_max_nm, strict=True)

        if self.regime_base_rpm is not None:
            _req_pos("regime_base_rpm", self.regime_base_rpm, strict=True)
            if self.regime_base_rpm > self.regime_max_rpm:
                raise ValueError("regime_base_rpm ne peut pas dépasser regime_max_rpm.")

        if self.rendement_moteur is not None:
            _req_ratio_0_1("rendement_moteur", self.rendement_moteur, strict_min=True)

        if self.rendement_transmission is not None:
            _req_ratio_0_1("rendement_transmission", self.rendement_transmission, strict_min=True)

        # garde-fou cohérence si les deux infos sont fournies
        if self.couple_max_nm is not None and self.regime_base_rpm is not None:
            omega_b = rpm_to_rad_s(self.regime_base_rpm)
            P_at_base = self.couple_max_nm * omega_b
            if P_at_base > 1.2 * self.puissance_max_w:
                raise ValueError(
                    "Incohérence: couple_max_nm * omega_base dépasse fortement puissance_max_w. "
                    "Vérifie (Pmax, Tmax, rpm_base)."
                )

    @property
    def omega_max_rad_s(self) -> float:
        return rpm_to_rad_s(self.regime_max_rpm)

    @property
    def omega_base_rad_s(self) -> float:
        if self.regime_base_rpm is not None:
            return rpm_to_rad_s(self.regime_base_rpm)
        assert self.couple_max_nm is not None
        omega_b = self.puissance_max_w / self.couple_max_nm
        return min(omega_b, self.omega_max_rad_s)

    @property
    def regime_base_rpm_calcule(self) -> float:
        return rad_s_to_rpm(self.omega_base_rad_s)

    @property
    def couple_max_nm_calcule(self) -> float:
        if self.couple_max_nm is not None:
            return self.couple_max_nm
        assert self.regime_base_rpm is not None
        omega_b = rpm_to_rad_s(self.regime_base_rpm)
        return self.puissance_max_w / omega_b

    def couple_disponible_nm(self, regime_rpm: float) -> float:
        rpm = _req_pos("regime_rpm", regime_rpm, strict=False)
        rpm = min(rpm, self.regime_max_rpm)

        omega = max(rpm_to_rad_s(rpm), 1e-9)
        omega_b = self.omega_base_rad_s
        Tmax = self.couple_max_nm_calcule

        if omega <= omega_b:
            return Tmax
        return min(Tmax, self.puissance_max_w / omega)

    def puissance_mecanique_disponible_w(self, regime_rpm: float) -> float:
        rpm = _req_pos("regime_rpm", regime_rpm, strict=False)
        rpm = min(rpm, self.regime_max_rpm)
        omega = rpm_to_rad_s(rpm)
        T = self.couple_disponible_nm(rpm)
        return min(self.puissance_max_w, T * omega)

    def puissance_electrique_approx_w(self, regime_rpm: float) -> float:
        """
        P_elec ≈ (P_mech + pertes_fixes) / eta_moteur
        Sans eta_moteur: impossible (pas d'invention).
        """
        if self.rendement_moteur is None:
            raise ValueError("rendement_moteur non fourni: impossible d'estimer P_elec.")
        eta = _req_ratio_0_1("rendement_moteur", self.rendement_moteur, strict_min=True)
        Pm = self.puissance_mecanique_disponible_w(regime_rpm)
        Pin = (Pm + self.pertes_fixes_w) / eta
        return max(0.0, Pin)

    def verifie_coherence_electrique(self) -> Dict[str, Any]:
        """
        Vérifie (si V et I fournis) la cohérence avec Pmax.
        Nécessite eta_moteur pour comparer méc/élec sans supposer.
        """
        out: Dict[str, Any] = {"ok": True}

        if self.tension_bus_v is None or self.courant_max_a is None:
            out["info"] = "tension_bus_v/courant_max_a non fournis -> pas de check."
            return out
        if self.rendement_moteur is None:
            out["info"] = "rendement_moteur non fourni -> pas de check méc/élec."
            return out

        V = _req_pos("tension_bus_v", self.tension_bus_v, strict=True)
        I = _req_pos("courant_max_a", self.courant_max_a, strict=True)
        eta = _req_ratio_0_1("rendement_moteur", self.rendement_moteur, strict_min=True)

        P_elec_max = V * I
        P_mech_max_est = P_elec_max * eta

        out.update(
            {
                "P_elec_max_W": float(P_elec_max),
                "P_mech_max_est_W": float(P_mech_max_est),
                "P_mech_spec_W": float(self.puissance_max_w),
            }
        )

        if self.puissance_max_w > 1.05 * P_mech_max_est:
            out["ok"] = False
            out["warning"] = "Pmax mécanique > V*I*eta (écart > 5%). Vérifier V/I/eta/Pmax."
        return out


# =============================================================================
# Demande moteur à partir d'un état véhicule (modules routiers)
# =============================================================================

def calcul_demande_moteur_depuis_vehicule(
    *,
    masse_kg: float,
    vitesse_ms: float,
    acceleration_ms2: float,
    angle_pente: float,
    angle_unite: AngleUnit,
    coef_roulement: float,
    coef_trainee_aero_cda: float,
    densite_air: float,       # PAS de défaut: pas d'invention
    gravite: float = _G0,     # constante physique standard
    rayon_roue_m: float,
    rapport_reduction_global: float,
    rendement_transmission: float,
    nb_roues_motrices: int = 2,
    pertes_fixes_w: float = 0.0,
    couple_pertes_nm: float = 0.0,
) -> Dict[str, float]:
    m = _req_pos("masse_kg", masse_kg, strict=True)
    v = _req_finite("vitesse_ms", vitesse_ms)
    a = _req_finite("acceleration_ms2", acceleration_ms2)

    rho = _req_pos("densite_air", densite_air, strict=True)
    g = _req_pos("gravite", gravite, strict=True)

    R = _req_pos("rayon_roue_m", rayon_roue_m, strict=True)
    G = _req_pos("rapport_reduction_global", rapport_reduction_global, strict=True)
    eta_trans = _req_ratio_0_1("rendement_transmission", rendement_transmission, strict_min=True)

    if not isinstance(nb_roues_motrices, int) or nb_roues_motrices < 1:
        raise ValueError("nb_roues_motrices doit être un entier >= 1.")

    fres = calcul_force_resistance_totale(
        masse_kg=m,
        vitesse_ms=v,
        angle_pente=angle_pente,
        coef_roulement=coef_roulement,
        coef_trainee_aero_cda=coef_trainee_aero_cda,
        densite_air=rho,
        gravite=g,
        angle_unite=angle_unite,
        oppose_mouvement=True,
        use_speed_sign=True,
        return_details=False,
    )
    F_res_tot = float(fres["F_totale"])
    F_inertie = float(m * a)
    F_req = float(F_inertie + F_res_tot)

    P_roue = float(
        calcul_puissance_roue(
            force_requise_n=F_req,
            vitesse_ms=v,
            use_abs_speed=False,
            clamp_non_negative=False,
        )
    )
    T_roue_total = float(calcul_couple_roue_total(force_requise_n=F_req, rayon_roue_m=R, clamp_non_negative=False))
    T_par_roue = float(
        calcul_couple_par_roue(
            couple_roue_total_nm=T_roue_total,
            nb_roues_motrices=nb_roues_motrices,
            repartition="egal",
        )
    )

    P_moteur = float(
        calcul_puissance_moteur_electrique(
            puissance_roue_w=P_roue,
            rendement_transmission=eta_trans,
            pertes_fixes_w=pertes_fixes_w,
            clamp_non_negative=False,
        )
    )
    T_moteur = float(
        calcul_couple_moteur(
            couple_roue_nm=T_roue_total,
            rapport_reduction_global=G,
            rendement_transmission=eta_trans,
            couple_pertes_nm=couple_pertes_nm,
            clamp_non_negative=False,
        )
    )

    omega_roue = 0.0 if R == 0 else (v / R)
    omega_moteur = omega_roue * G

    return {
        "F_res_totale_N": F_res_tot,
        "F_inertie_N": F_inertie,
        "F_requise_N": F_req,
        "P_roue_W": P_roue,
        "T_roue_total_Nm": T_roue_total,
        "T_par_roue_Nm": T_par_roue,
        "P_moteur_W": P_moteur,
        "T_moteur_Nm": T_moteur,
        "rpm_roue": rad_s_to_rpm(omega_roue),
        "rpm_moteur": rad_s_to_rpm(omega_moteur),
        "omega_roue_rad_s": omega_roue,
        "omega_moteur_rad_s": omega_moteur,
    }


def verifie_moteur_sur_demande(
    moteur: MoteurElectrique,
    demande: Dict[str, float],
    *,
    marge_puissance: float = 0.0,
    marge_couple: float = 0.0,
) -> Dict[str, float]:
    if not isinstance(moteur, MoteurElectrique):
        raise ValueError("moteur doit être une instance de MoteurElectrique.")

    rpm = _req_finite("demande['rpm_moteur']", demande.get("rpm_moteur", float("nan")))
    P_req = _req_finite("demande['P_moteur_W']", demande.get("P_moteur_W", float("nan")))
    T_req = _req_finite("demande['T_moteur_Nm']", demande.get("T_moteur_Nm", float("nan")))

    P_cap = moteur.puissance_mecanique_disponible_w(rpm)
    T_cap = moteur.couple_disponible_nm(rpm)

    P_need = P_req * (1.0 + _req_finite("marge_puissance", marge_puissance))
    T_need = T_req * (1.0 + _req_finite("marge_couple", marge_couple))

    return {
        "rpm": float(rpm),
        "P_req_W": float(P_req),
        "T_req_Nm": float(T_req),
        "P_cap_W": float(P_cap),
        "T_cap_Nm": float(T_cap),
        "P_ok": 1.0 if P_cap >= P_need else 0.0,
        "T_ok": 1.0 if T_cap >= T_need else 0.0,
        "P_ratio_cap_req": (P_cap / P_req) if abs(P_req) > 1e-9 else float("inf"),
        "T_ratio_cap_req": (T_cap / T_req) if abs(T_req) > 1e-9 else float("inf"),
        "P_marge_W": float(P_cap - P_need),
        "T_marge_Nm": float(T_cap - T_need),
    }


def acceleration_max_par_adherence(
    *,
    mu_adherence: float,
    masse_kg: float,
    hauteur_cg_m: float,
    empattement_m: float,
    charge_essieu_moteur_n: float,
    force_resistance_n: float,
    type_milieu: str,
    include_transfert: bool = False,
    clamp_non_negative: bool = True,
) -> float:
    return float(
        calcul_acceleration_max(
            mu_adherence=mu_adherence,
            charge_essieu_moteur_n=charge_essieu_moteur_n,
            force_resistance_n=force_resistance_n,
            masse_kg=masse_kg,
            hauteur_cg_m=hauteur_cg_m,
            empattement_m=empattement_m,
            type_milieu=type_milieu,
            include_transfert=include_transfert,
            clamp_non_negative=clamp_non_negative,
        )
    )


# =============================================================================
# Analyse "depuis puissance" (fusion du 2e script) : pas d'invention
# =============================================================================

@dataclass(frozen=True)
class AnalyseDepuisPuissance:
    """
    L'utilisateur fournit UNIQUEMENT:
      - puissance_elec_dispo_w

    Le reste est calculé SI et seulement SI les paramètres nécessaires sont fournis
    dans 'config'. Sinon -> 'inconnues'.

    config["domaine"] : "routier" | "nautique" | "aerien" | "ferroviaire"
    """

    tension_systeme_v: Optional[float] = None

    def analyser(self, *, puissance_elec_dispo_w: float, config: Dict[str, Any]) -> Dict[str, Any]:
        Pdispo = _req_pos("puissance_elec_dispo_w", puissance_elec_dispo_w, strict=False)

        rapport: Dict[str, Any] = {
            "entree": {
                "puissance_elec_dispo_w": float(Pdispo),
                "tension_systeme_v": self.tension_systeme_v,
                "domaine": str(config.get("domaine", "")),
            },
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes": [],
        }

        # courant si tension connue
        if self.tension_systeme_v is not None:
            V = _req_pos("tension_systeme_v", self.tension_systeme_v, strict=True)
            rapport["resultats"]["courant_estime_A"] = 0.0 if Pdispo == 0.0 else float(Pdispo / V)
        else:
            _push_inc(rapport, "partielles", "courant_estime_A", "Calculable si tension_systeme_v est fournie.")

        domaine = str(config.get("domaine", "")).strip().lower()
        if domaine not in ("routier", "nautique", "aerien", "ferroviaire"):
            raise ValueError("config['domaine'] doit être: routier | nautique | aerien | ferroviaire")

        # ---------------------------------------------------------------------
        # ROUTIER : on inverse P_elec(v) via tes modules
        # ---------------------------------------------------------------------
        if domaine == "routier":
            req = [
                "masse_kg",
                "angle_pente",
                "angle_unite",
                "coef_roulement",
                "cda",
                "densite_air",
                "eta_transmission",
                "eta_moteur",
                "v_max_recherche_ms",
            ]
            missing = [k for k in req if k not in config]
            if missing:
                _push_inc(rapport, "impossibles", "vitesse_max_routier", f"Paramètres manquants: {missing}")
            else:
                m = _req_pos("masse_kg", config["masse_kg"], strict=True)
                angle_pente = _req_finite("angle_pente", config["angle_pente"])
                angle_unite: AngleUnit = str(config["angle_unite"])
                cr = _req_pos("coef_roulement", config["coef_roulement"], strict=False)
                cda = _req_pos("cda", config["cda"], strict=False)
                rho_air = _req_pos("densite_air", config["densite_air"], strict=True)
                eta_trans = _req_ratio_0_1("eta_transmission", config["eta_transmission"], strict_min=True)
                eta_mot = _req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True)

                pertes_meca = _req_pos("pertes_meca_fixes_w", config.get("pertes_meca_fixes_w", 0.0), strict=False)
                pertes_elec = _req_pos("pertes_elec_fixes_w", config.get("pertes_elec_fixes_w", 0.0), strict=False)

                vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                def p_elec_requise(v: float) -> float:
                    forces = calcul_force_resistance_totale(
                        masse_kg=m,
                        vitesse_ms=v,
                        angle_pente=angle_pente,
                        coef_roulement=cr,
                        coef_trainee_aero_cda=cda,
                        densite_air=rho_air,
                        gravite=_G0,
                        angle_unite=angle_unite,
                        oppose_mouvement=True,
                        use_speed_sign=False,
                        return_details=False,
                    )
                    F_tot = float(forces["F_totale"])
                    P_roue = float(calcul_puissance_roue(F_tot, v, use_abs_speed=True, clamp_non_negative=True))
                    P_meca_moteur = float(
                        calcul_puissance_moteur_electrique(
                            puissance_roue_w=P_roue,
                            rendement_transmission=eta_trans,
                            pertes_fixes_w=pertes_meca,
                            clamp_non_negative=True,
                        )
                    )
                    P_elec = 0.0 if P_meca_moteur == 0.0 else (P_meca_moteur / eta_mot)
                    P_elec += pertes_elec
                    return float(P_elec)

                v_sol = _bisect_monotone(p_elec_requise, Pdispo, 0.0, vmax)
                forces_sol = calcul_force_resistance_totale(
                    masse_kg=m,
                    vitesse_ms=v_sol,
                    angle_pente=angle_pente,
                    coef_roulement=cr,
                    coef_trainee_aero_cda=cda,
                    densite_air=rho_air,
                    gravite=_G0,
                    angle_unite=angle_unite,
                    oppose_mouvement=True,
                    use_speed_sign=False,
                    return_details=False,
                )
                F_tot = float(forces_sol["F_totale"])
                P_roue = float(calcul_puissance_roue(F_tot, v_sol, use_abs_speed=True, clamp_non_negative=True))
                P_meca_moteur = float(
                    calcul_puissance_moteur_electrique(
                        puissance_roue_w=P_roue,
                        rendement_transmission=eta_trans,
                        pertes_fixes_w=pertes_meca,
                        clamp_non_negative=True,
                    )
                )

                out: Dict[str, Any] = {
                    "vitesse_ms": float(v_sol),
                    "vitesse_kmh": float(v_sol * 3.6),
                    "F_totale_N": float(F_tot),
                    "F_roulement_N": float(forces_sol["F_roulement"]),
                    "F_aero_N": float(forces_sol["F_aero"]),
                    "F_pente_N": float(forces_sol["F_pente"]),
                    "P_roue_W": float(P_roue),
                    "P_moteur_meca_W": float(P_meca_moteur),
                    "P_elec_W": float(p_elec_requise(v_sol)),
                    "conso_Wh_km": float(_wh_per_km_from_p_v(p_elec_requise(v_sol), v_sol)) if v_sol > 0 else 0.0,
                }

                # Couples si rayon roue fourni
                if "rayon_roue_m" in config:
                    R = _req_pos("rayon_roue_m", config["rayon_roue_m"], strict=True)
                    T_roue_total = float(calcul_couple_roue_total(F_tot, R, clamp_non_negative=True))
                    out["couple_roue_total_Nm"] = T_roue_total

                    if "nb_roues_motrices" in config:
                        n = int(config["nb_roues_motrices"])
                        out["couple_par_roue_Nm"] = float(calcul_couple_par_roue(T_roue_total, n))
                    else:
                        _push_inc(rapport, "partielles", "couple_par_roue_Nm", "Calculable si nb_roues_motrices est fourni.")

                    if "rapport_reduction_global" in config:
                        G = _req_pos("rapport_reduction_global", config["rapport_reduction_global"], strict=True)
                        out["rpm_roue"] = float(rad_s_to_rpm(v_sol / R))
                        out["rpm_moteur"] = float(rad_s_to_rpm((v_sol / R) * G))
                        out["couple_moteur_Nm_estime"] = float(
                            calcul_couple_moteur(
                                couple_roue_nm=T_roue_total,
                                rapport_reduction_global=G,
                                rendement_transmission=eta_trans,
                                couple_pertes_nm=_req_pos("couple_pertes_nm", config.get("couple_pertes_nm", 0.0), strict=False),
                                clamp_non_negative=True,
                            )
                        )
                    else:
                        _push_inc(rapport, "partielles", "rpm/couple_moteur", "Calculables si rapport_reduction_global est fourni.")
                else:
                    _push_inc(rapport, "partielles", "couples", "Calculables si rayon_roue_m est fourni.")

                rapport["resultats"]["routier"] = out

            # Accélération max par adhérence (si params complets)
            req_acc = ["mu_adherence", "hauteur_cg_m", "empattement_m", "lr_m", "lf_m", "type_milieu"]
            miss_acc = [k for k in req_acc if k not in config]
            if miss_acc:
                _push_inc(rapport, "partielles", "acceleration_max_adhérence", f"Calculable si config contient: {miss_acc}")
            else:
                m = _req_pos("masse_kg", config["masse_kg"], strict=True)

                # Fres(v=0) : utile pour a_max au démarrage
                forces0 = calcul_force_resistance_totale(
                    masse_kg=m,
                    vitesse_ms=0.0,
                    angle_pente=_req_finite("angle_pente", config["angle_pente"]),
                    coef_roulement=_req_pos("coef_roulement", config["coef_roulement"], strict=False),
                    coef_trainee_aero_cda=_req_pos("cda", config["cda"], strict=False),
                    densite_air=_req_pos("densite_air", config["densite_air"], strict=True),
                    gravite=_G0,
                    angle_unite=str(config["angle_unite"]),
                    oppose_mouvement=True,
                    use_speed_sign=False,
                    return_details=False,
                )
                Fres0 = float(forces0["F_totale"])

                h = _req_pos("hauteur_cg_m", config["hauteur_cg_m"], strict=False)
                L = _req_pos("empattement_m", config["empattement_m"], strict=True)
                lr = _req_pos("lr_m", config["lr_m"], strict=False)
                lf = _req_pos("lf_m", config["lf_m"], strict=False)

                charges = calcul_charges_essieux(
                    masse_kg=m,
                    acceleration_ms2=0.0,
                    angle_pente=_req_finite("angle_pente", config["angle_pente"]),
                    empattement_l_m=L,
                    dist_cg_arriere_lr_m=lr,
                    dist_cg_avant_lf_m=lf,
                    hauteur_cg_h_m=h,
                    angle_unite=str(config["angle_unite"]),
                    clamp_non_negative=True,
                    check_consistance=True,
                    return_details=False,
                )
                N_av = float(charges["N_avant"])
                N_ar = float(charges["N_arriere"])

                mode = str(config["type_milieu"]).strip().lower()
                if mode in ("fwd", "avant", "front"):
                    N_drive = N_av
                    mode_norm = "FWD"
                elif mode in ("rwd", "arriere", "arrière", "rear"):
                    N_drive = N_ar
                    mode_norm = "RWD"
                elif mode in ("awd", "4wd", "4x4", "integral", "intégral"):
                    N_drive = N_av + N_ar
                    mode_norm = "AWD"
                else:
                    raise ValueError("type_milieu invalide (fwd/rwd/awd).")

                a_max = float(
                    calcul_acceleration_max(
                        mu_adherence=_req_pos("mu_adherence", config["mu_adherence"], strict=False),
                        charge_essieu_moteur_n=N_drive,
                        force_resistance_n=Fres0,
                        masse_kg=m,
                        hauteur_cg_m=h,
                        empattement_m=L,
                        type_milieu=mode_norm,
                        include_transfert=True,
                        clamp_non_negative=True,
                    )
                )
                rapport["resultats"]["routier_accel_adh"] = {
                    "F_resistance_v0_N": Fres0,
                    "N_avant_N": N_av,
                    "N_arriere_N": N_ar,
                    "N_drive_N": N_drive,
                    "a_max_ms2": a_max,
                    "F_traction_max_N": (m * a_max + Fres0),
                }

        # ---------------------------------------------------------------------
        # MULTI-DOMAINES : inversion vitesse depuis puissance (si modules présents)
        # Aucun coefficient "typique" : tout vient du config.
        # ---------------------------------------------------------------------
        if domaine in ("nautique", "aerien", "ferroviaire"):
            if domaine == "nautique":
                if _md_nautique is None:
                    _push_inc(rapport, "impossibles", "nautique", "Module calcul_multi_domaine (nautique) absent.")
                else:
                    req = ["surface_mouillee_m2", "cw_coque", "rho_eau_kg_m3", "eta_helice", "eta_moteur", "v_max_recherche_ms"]
                    miss = [k for k in req if k not in config]
                    if miss:
                        _push_inc(rapport, "impossibles", "nautique", f"Paramètres manquants: {miss}")
                    else:
                        vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                        def p_elec(v: float) -> float:
                            r = _md_nautique(
                                vitesse_ms=v,
                                surface_mouillee_m2=_req_pos("surface_mouillee_m2", config["surface_mouillee_m2"], strict=False),
                                cw_coque=_req_pos("cw_coque", config["cw_coque"], strict=False),
                                rho_eau_kg_m3=_req_pos("rho_eau_kg_m3", config["rho_eau_kg_m3"], strict=True),
                                eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                                eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                            )
                            return float(r["puissance_elec_W"])

                        v_sol = _bisect_monotone(p_elec, Pdispo, 0.0, vmax)
                        rsol = _md_nautique(
                            vitesse_ms=v_sol,
                            surface_mouillee_m2=_req_pos("surface_mouillee_m2", config["surface_mouillee_m2"], strict=False),
                            cw_coque=_req_pos("cw_coque", config["cw_coque"], strict=False),
                            rho_eau_kg_m3=_req_pos("rho_eau_kg_m3", config["rho_eau_kg_m3"], strict=True),
                            eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                            eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                            eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                        )
                        rapport["resultats"]["nautique"] = {
                            "vitesse_ms": float(v_sol),
                            "vitesse_kmh": float(v_sol * 3.6),
                            "force_N": float(rsol["force_N"]),
                            "puissance_meca_W": float(rsol["puissance_meca_W"]),
                            "puissance_elec_W": float(rsol["puissance_elec_W"]),
                            "conso_Wh_km": float(_wh_per_km_from_p_v(float(rsol["puissance_elec_W"]), v_sol)) if v_sol > 0 else 0.0,
                        }

            if domaine == "aerien":
                if _md_aerien_rho is None:
                    _push_inc(rapport, "impossibles", "aerien", "Module calcul_multi_domaine (aérien) absent.")
                else:
                    # rho_air peut venir directement, ou via pression+température si module dispo
                    req_base = ["s_cx_cellule_m2", "eta_helice", "eta_moteur", "v_max_recherche_ms"]
                    miss_base = [k for k in req_base if k not in config]
                    if miss_base:
                        _push_inc(rapport, "impossibles", "aerien", f"Paramètres manquants: {miss_base}")
                    else:
                        vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                        if "rho_air_kg_m3" in config:
                            rho_air = _req_pos("rho_air_kg_m3", config["rho_air_kg_m3"], strict=True)
                        else:
                            if _md_rho_air_sec is None:
                                _push_inc(
                                    rapport,
                                    "impossibles",
                                    "rho_air_kg_m3",
                                    "Fournir rho_air_kg_m3, ou fournir (pression_pa, temperature_c) + module calcul_densite_air_sec.",
                                )
                                rho_air = None
                            else:
                                if "pression_pa" not in config or "temperature_c" not in config:
                                    _push_inc(
                                        rapport,
                                        "impossibles",
                                        "rho_air_kg_m3",
                                        "Fournir rho_air_kg_m3, ou fournir pression_pa ET temperature_c.",
                                    )
                                    rho_air = None
                                else:
                                    rho_air = float(
                                        _md_rho_air_sec(
                                            pression_pa=_req_pos("pression_pa", config["pression_pa"], strict=True),
                                            temperature_c=_req_finite("temperature_c", config["temperature_c"]),
                                        )
                                    )

                        if rho_air is not None:
                            def p_elec(v: float) -> float:
                                r = _md_aerien_rho(
                                    vitesse_ms=v,
                                    rho_air_kg_m3=rho_air,
                                    s_cx_cellule_m2=_req_pos("s_cx_cellule_m2", config["s_cx_cellule_m2"], strict=False),
                                    eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                                    eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                    eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                                )
                                return float(r["puissance_elec_W"])

                            v_sol = _bisect_monotone(p_elec, Pdispo, 0.0, vmax)
                            rsol = _md_aerien_rho(
                                vitesse_ms=v_sol,
                                rho_air_kg_m3=rho_air,
                                s_cx_cellule_m2=_req_pos("s_cx_cellule_m2", config["s_cx_cellule_m2"], strict=False),
                                eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                                eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                            )
                            rapport["resultats"]["aerien"] = {
                                "densite_air": float(rsol["densite_air"]),
                                "vitesse_ms": float(v_sol),
                                "vitesse_kmh": float(v_sol * 3.6),
                                "force_N": float(rsol["force_N"]),
                                "puissance_meca_W": float(rsol["puissance_meca_W"]),
                                "puissance_elec_W": float(rsol["puissance_elec_W"]),
                                "conso_Wh_km": float(_wh_per_km_from_p_v(float(rsol["puissance_elec_W"]), v_sol)) if v_sol > 0 else 0.0,
                            }

            if domaine == "ferroviaire":
                if _md_ferro_davis is None:
                    _push_inc(rapport, "impossibles", "ferroviaire", "Module calcul_multi_domaine (ferroviaire) absent.")
                else:
                    req = ["masse_kg", "davis_A_N", "davis_B_N_s_m", "davis_C_N_s2_m2", "eta_moteur", "eta_transmission", "v_max_recherche_ms"]
                    miss = [k for k in req if k not in config]
                    if miss:
                        _push_inc(rapport, "impossibles", "ferroviaire", f"Paramètres manquants: {miss}")
                    else:
                        vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                        def p_elec(v: float) -> float:
                            r = _md_ferro_davis(
                                vitesse_ms=v,
                                masse_kg=_req_pos("masse_kg", config["masse_kg"], strict=True),
                                acceleration_ms2=0.0,
                                davis_A_N=_req_pos("davis_A_N", config["davis_A_N"], strict=False),
                                davis_B_N_s_m=_req_pos("davis_B_N_s_m", config["davis_B_N_s_m"], strict=False),
                                davis_C_N_s2_m2=_req_pos("davis_C_N_s2_m2", config["davis_C_N_s2_m2"], strict=False),
                                eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                eta_transmission=_req_ratio_0_1("eta_transmission", config["eta_transmission"], strict_min=True),
                            )
                            return float(r["puissance_elec_W"])

                        v_sol = _bisect_monotone(p_elec, Pdispo, 0.0, vmax)
                        rsol = _md_ferro_davis(
                            vitesse_ms=v_sol,
                            masse_kg=_req_pos("masse_kg", config["masse_kg"], strict=True),
                            acceleration_ms2=0.0,
                            davis_A_N=_req_pos("davis_A_N", config["davis_A_N"], strict=False),
                            davis_B_N_s_m=_req_pos("davis_B_N_s_m", config["davis_B_N_s_m"], strict=False),
                            davis_C_N_s2_m2=_req_pos("davis_C_N_s2_m2", config["davis_C_N_s2_m2"], strict=False),
                            eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                            eta_transmission=_req_ratio_0_1("eta_transmission", config["eta_transmission"], strict_min=True),
                        )
                        rapport["resultats"]["ferroviaire"] = {
                            "vitesse_ms": float(v_sol),
                            "vitesse_kmh": float(v_sol * 3.6),
                            "force_N": float(rsol["force_N"]),
                            "puissance_meca_W": float(rsol["puissance_meca_W"]),
                            "puissance_elec_W": float(rsol["puissance_elec_W"]),
                            "conso_Wh_km": float(_wh_per_km_from_p_v(float(rsol["puissance_elec_W"]), v_sol)) if v_sol > 0 else 0.0,
                        }

        _dedup_inconnues(rapport)
        return rapport


# =============================================================================
# Convenience: une fonction simple
# =============================================================================

def analyser_depuis_puissance(
    *,
    puissance_elec_dispo_w: float,
    config: Dict[str, Any],
    tension_systeme_v: Optional[float] = None,
) -> Dict[str, Any]:
    return AnalyseDepuisPuissance(tension_systeme_v=tension_systeme_v).analyser(
        puissance_elec_dispo_w=puissance_elec_dispo_w,
        config=config,
    )
