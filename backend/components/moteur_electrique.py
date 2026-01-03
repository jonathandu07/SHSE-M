# backend/components/moteur_electrique.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any


# =========================
# Imports des modules "métier"
# (avec fallback de chemins possibles)
# =========================

# NOTE:
# Je ne peux pas deviner à 100% ton arborescence Python réelle.
# Donc je fais des imports robustes: tu n'auras qu'à garder le bloc
# qui correspond à ton projet si tu veux simplifier.

try:
    # Exemple: backend/modules/...
    from backend.modules.calcul_force_resistance_vitesse import calcul_force_resistance_totale
    from backend.modules.calcul_puissance_roue import (
        calcul_puissance_roue,
        calcul_couple_roue_total,
        calcul_couple_par_roue,
    )
    from backend.modules.calcul_puissance_moteur import (
        calcul_puissance_moteur_electrique,
        calcul_couple_moteur,
    )
    from backend.modules.calcul_charge_essieu import calcul_charges_essieux
    from backend.modules.calcul_acceleration_max import calcul_acceleration_max

except Exception:
    try:
        # Exemple: backend/modules/vehicule/...
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

    except Exception as e:
        raise ImportError(
            "Impossible d'importer les modules de calcul. "
            "Ajuste les chemins d'import dans backend/components/moteur_electrique.py "
            f"(erreur d'import: {e})."
        )


# =========================
# Helpers (validation + conversions)
# =========================

DriveMode = Literal["FWD", "RWD", "AWD"]
_G0 = 9.80665


def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: float) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: float, *, strictly: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strictly else x >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


def _require_eta(name: str, eta: float) -> float:
    eta = _require_finite(name, eta)
    if not (0.0 < eta <= 1.0):
        raise ValueError(f"{name} doit être dans (0, 1] (reçu: {eta}).")
    return eta


def rpm_to_rad_s(rpm: float) -> float:
    rpm = _require_finite("rpm", rpm)
    return (2.0 * math.pi) * (rpm / 60.0)


def rad_s_to_rpm(omega: float) -> float:
    omega = _require_finite("omega", omega)
    return (omega * 60.0) / (2.0 * math.pi)


# =========================
# Modèle moteur: minimal en inconnues, exploitable
# =========================

@dataclass(frozen=True)
class MoteurElectrique:
    """
    Modèle simple et exploitable d'un moteur électrique.

    Objectif "minimum d'inconnues" (sans inventer):
    - Il faut au minimum:
        - puissance_max_w (Pmax)
        - regime_max_rpm (rpm_max)
        - et l'une des deux infos suivantes:
            (A) couple_max_nm (Tmax)  -> permet de déduire le régime de base
            (B) regime_base_rpm       -> permet de déduire le couple max

    Courbe par défaut:
    - Zone 1: couple constant (T = Tmax) jusqu'au régime de base.
    - Zone 2: puissance constante (P = Pmax) au-delà, donc T = Pmax / omega.
    - Bornée par regime_max_rpm.

    Remarque:
    - Ce modèle ne "devine" pas le couple max si tu ne fournis rien:
      ce serait une hypothèse non sourcée.
    """

    puissance_max_w: float
    regime_max_rpm: float

    # L'un des deux doit être fourni
    couple_max_nm: Optional[float] = None
    regime_base_rpm: Optional[float] = None

    # Rendements (optionnels)
    rendement_moteur: float = 0.93          # mech / elec (si tu l'utilises)
    rendement_transmission: float = 0.97    # roue / moteur (si tu l'utilises)

    # Paramètres électriques (optionnels)
    tension_bus_v: Optional[float] = None
    courant_max_a: Optional[float] = None

    # Pertes (optionnelles)
    pertes_fixes_w: float = 0.0

    def __post_init__(self) -> None:
        Pmax = _require_positive("puissance_max_w", self.puissance_max_w, strictly=True)
        rpm_max = _require_positive("regime_max_rpm", self.regime_max_rpm, strictly=True)
        _require_eta("rendement_moteur", self.rendement_moteur)
        _require_eta("rendement_transmission", self.rendement_transmission)
        _require_finite("pertes_fixes_w", self.pertes_fixes_w)

        if (self.couple_max_nm is None) and (self.regime_base_rpm is None):
            raise ValueError(
                "Il faut fournir au moins 'couple_max_nm' OU 'regime_base_rpm' "
                "pour définir une courbe couple/puissance sans hypothèses."
            )

        if self.couple_max_nm is not None:
            _require_positive("couple_max_nm", self.couple_max_nm, strictly=True)

        if self.regime_base_rpm is not None:
            _require_positive("regime_base_rpm", self.regime_base_rpm, strictly=True)
            if self.regime_base_rpm > rpm_max:
                raise ValueError("regime_base_rpm ne peut pas dépasser regime_max_rpm.")

        # Si les deux sont fournis, on n'impose pas d'égalité stricte,
        # mais on peut vérifier une cohérence grossière.
        if self.couple_max_nm is not None and self.regime_base_rpm is not None:
            omega_b = rpm_to_rad_s(self.regime_base_rpm)
            P_at_base = self.couple_max_nm * omega_b
            # tolérance large: 20% (pas une règle physique universelle, juste garde-fou)
            if P_at_base > 1.2 * Pmax:
                raise ValueError(
                    "Incohérence: couple_max_nm * omega_base dépasse fortement puissance_max_w. "
                    "Vérifie (Pmax, Tmax, rpm_base)."
                )

    @property
    def omega_max_rad_s(self) -> float:
        return rpm_to_rad_s(self.regime_max_rpm)

    @property
    def omega_base_rad_s(self) -> float:
        """
        Déduit omega_base selon les infos disponibles:
        - si regime_base fourni: omega_base = conv(regime_base)
        - sinon: omega_base = Pmax / Tmax
        """
        if self.regime_base_rpm is not None:
            return rpm_to_rad_s(self.regime_base_rpm)

        assert self.couple_max_nm is not None
        omega_b = self.puissance_max_w / self.couple_max_nm
        # borne par omega_max
        return min(omega_b, self.omega_max_rad_s)

    @property
    def regime_base_rpm_calcule(self) -> float:
        return rad_s_to_rpm(self.omega_base_rad_s)

    @property
    def couple_max_nm_calcule(self) -> float:
        """
        Déduit Tmax si absent:
        Tmax = Pmax / omega_base
        """
        if self.couple_max_nm is not None:
            return self.couple_max_nm

        assert self.regime_base_rpm is not None
        omega_b = rpm_to_rad_s(self.regime_base_rpm)
        return self.puissance_max_w / omega_b

    def couple_disponible_nm(self, regime_rpm: float) -> float:
        """
        Couple dispo (mécanique arbre) selon la courbe:
        - si rpm <= rpm_base: Tmax
        - sinon: T = Pmax / omega
        borné à rpm_max.
        """
        rpm = _require_positive("regime_rpm", regime_rpm, strictly=False)
        rpm = min(rpm, self.regime_max_rpm)

        omega = max(rpm_to_rad_s(rpm), 1e-9)  # évite division 0 (pure garde-fou numérique)
        omega_b = self.omega_base_rad_s
        Tmax = self.couple_max_nm_calcule

        if omega <= omega_b:
            return Tmax

        # zone puissance constante
        return min(Tmax, self.puissance_max_w / omega)

    def puissance_mecanique_disponible_w(self, regime_rpm: float) -> float:
        """
        Puissance mécanique dispo à l'arbre = T(omega) * omega,
        bornée par Pmax.
        """
        rpm = _require_positive("regime_rpm", regime_rpm, strictly=False)
        rpm = min(rpm, self.regime_max_rpm)
        omega = rpm_to_rad_s(rpm)
        T = self.couple_disponible_nm(rpm)
        return min(self.puissance_max_w, T * omega)

    def puissance_electrique_approx_w(self, regime_rpm: float) -> float:
        """
        Estimation (optionnelle) de la puissance électrique consommée:
        P_elec ≈ (P_mech + pertes_fixes) / eta_moteur
        """
        Pm = self.puissance_mecanique_disponible_w(regime_rpm)
        Pin = (Pm + self.pertes_fixes_w) / self.rendement_moteur
        return max(0.0, Pin)

    def verifie_coherence_electrique(self) -> Dict[str, Any]:
        """
        Vérifie (si tension/courant fournis) que Pmax mécanique est plausible
        vis-à-vis de V*I*eta.
        """
        out: Dict[str, Any] = {"ok": True}

        if self.tension_bus_v is None or self.courant_max_a is None:
            out["info"] = "tension_bus_v/courant_max_a non fournis -> pas de check électrique."
            return out

        V = _require_positive("tension_bus_v", self.tension_bus_v, strictly=True)
        I = _require_positive("courant_max_a", self.courant_max_a, strictly=True)

        P_elec_max = V * I
        P_mech_max_est = P_elec_max * self.rendement_moteur

        out.update(
            {
                "P_elec_max_W": P_elec_max,
                "P_mech_max_est_W": P_mech_max_est,
                "P_mech_spec_W": self.puissance_max_w,
            }
        )

        if self.puissance_max_w > 1.05 * P_mech_max_est:
            out["ok"] = False
            out["warning"] = (
                "puissance_max_w > V*I*eta_moteur (écart > 5%). "
                "Soit (V,I) sont sous-estimés, soit eta, soit Pmax."
            )

        return out


# =========================
# Demande moteur à partir du véhicule (en utilisant tes modules)
# =========================

def calcul_demande_moteur_depuis_vehicule(
    *,
    # Cinématique
    masse_kg: float,
    vitesse_ms: float,
    acceleration_ms2: float,
    angle_pente: float = 0.0,
    angle_unite: Literal["rad", "deg"] = "rad",
    # Résistances
    coef_roulement: float,
    coef_trainee_aero_cda: float,
    densite_air: float = 1.2,
    gravite: float = _G0,
    # Roues / transmission
    rayon_roue_m: float,
    rapport_reduction_global: float,
    rendement_transmission: float,
    nb_roues_motrices: int = 2,
    # Pertes
    pertes_fixes_w: float = 0.0,
    couple_pertes_nm: float = 0.0,
) -> Dict[str, float]:
    """
    Calcule la demande (couple, puissance, régime) côté moteur à partir
    d'un état véhicule (v, a, pente) + résistances.

    Chaîne:
      résistances -> F_res
      inertie     -> m*a
      F_req = m*a + F_res_totale
      -> P_roue, T_roue_total
      -> P_moteur, T_moteur (avec tes modules)

    Retour: dict (unités SI, rpm pour régimes)
    """
    m = _require_positive("masse_kg", masse_kg, strictly=True)
    v = _require_finite("vitesse_ms", vitesse_ms)
    a = _require_finite("acceleration_ms2", acceleration_ms2)

    R = _require_positive("rayon_roue_m", rayon_roue_m, strictly=True)
    G = _require_positive("rapport_reduction_global", rapport_reduction_global, strictly=True)
    eta_trans = _require_eta("rendement_transmission", rendement_transmission)

    if not isinstance(nb_roues_motrices, int) or nb_roues_motrices < 1:
        raise ValueError("nb_roues_motrices doit être un entier >= 1.")

    # 1) Forces résistantes (roulement + aero + pente)
    fres = calcul_force_resistance_totale(
        masse_kg=m,
        vitesse_ms=v,
        angle_pente=angle_pente,
        coef_roulement=coef_roulement,
        coef_trainee_aero_cda=coef_trainee_aero_cda,
        densite_air=densite_air,
        gravite=gravite,
        angle_unite=angle_unite,
        oppose_mouvement=True,
        use_speed_sign=True,
        return_details=False,
    )
    F_res_tot = fres["F_totale"]

    # 2) Force inertielle (1D)
    F_inertie = m * a

    # 3) Force requise à la roue
    # Convention: v>=0 = avance; F_res_tot est orientée pour s'opposer au mouvement (selon ton module).
    # Donc en traction: F_req = F_inertie + F_res_tot.
    F_req = F_inertie + F_res_tot

    # 4) Puissance + couple aux roues
    P_roue = calcul_puissance_roue(
        force_requise_n=F_req,
        vitesse_ms=v,
        use_abs_speed=False,
        clamp_non_negative=False,
    )
    T_roue_total = calcul_couple_roue_total(
        force_requise_n=F_req,
        rayon_roue_m=R,
        clamp_non_negative=False,
    )
    T_par_roue = calcul_couple_par_roue(
        couple_roue_total_nm=T_roue_total,
        nb_roues_motrices=nb_roues_motrices,
        repartition="egal",
    )

    # 5) Côté moteur (via tes modules)
    P_moteur = calcul_puissance_moteur_electrique(
        puissance_roue_w=P_roue,
        rendement_transmission=eta_trans,
        pertes_fixes_w=pertes_fixes_w,
        clamp_non_negative=False,
    )
    T_moteur = calcul_couple_moteur(
        couple_roue_nm=T_roue_total,
        rapport_reduction_global=G,
        rendement_transmission=eta_trans,
        couple_pertes_nm=couple_pertes_nm,
        clamp_non_negative=False,
    )

    # 6) Régimes roue / moteur
    omega_roue = v / R if abs(R) > 0 else 0.0
    omega_moteur = omega_roue * G
    rpm_roue = rad_s_to_rpm(omega_roue)
    rpm_moteur = rad_s_to_rpm(omega_moteur)

    return {
        "F_res_totale_N": F_res_tot,
        "F_inertie_N": F_inertie,
        "F_requise_N": F_req,
        "P_roue_W": P_roue,
        "T_roue_total_Nm": T_roue_total,
        "T_par_roue_Nm": T_par_roue,
        "P_moteur_W": P_moteur,
        "T_moteur_Nm": T_moteur,
        "rpm_roue": rpm_roue,
        "rpm_moteur": rpm_moteur,
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
    """
    Compare la demande calculée à la capacité du moteur à ce régime.
    marge_* : marge relative (0.1 = +10% de marge exigée côté moteur).
    """
    if not isinstance(moteur, MoteurElectrique):
        raise ValueError("moteur doit être une instance de MoteurElectrique.")

    rpm = _require_finite("demande['rpm_moteur']", demande.get("rpm_moteur", float("nan")))
    P_req = _require_finite("demande['P_moteur_W']", demande.get("P_moteur_W", float("nan")))
    T_req = _require_finite("demande['T_moteur_Nm']", demande.get("T_moteur_Nm", float("nan")))

    P_cap = moteur.puissance_mecanique_disponible_w(rpm)
    T_cap = moteur.couple_disponible_nm(rpm)

    # marges demandées
    P_need = P_req * (1.0 + _require_finite("marge_puissance", marge_puissance))
    T_need = T_req * (1.0 + _require_finite("marge_couple", marge_couple))

    return {
        "rpm": rpm,
        "P_req_W": P_req,
        "T_req_Nm": T_req,
        "P_cap_W": P_cap,
        "T_cap_Nm": T_cap,
        "P_ok": 1.0 if P_cap >= P_need else 0.0,
        "T_ok": 1.0 if T_cap >= T_need else 0.0,
        "P_ratio_cap_req": (P_cap / P_req) if abs(P_req) > 1e-9 else float("inf"),
        "T_ratio_cap_req": (T_cap / T_req) if abs(T_req) > 1e-9 else float("inf"),
        "P_marge_W": P_cap - P_need,
        "T_marge_Nm": T_cap - T_need,
    }


# =========================
# (Optionnel) Limitation par l'adhérence / charges essieux
# =========================

def acceleration_max_par_adherence(
    *,
    mu_adherence: float,
    masse_kg: float,
    hauteur_cg_m: float,
    empattement_m: float,
    # charges statiques: si tu connais N_avant/N_arriere au repos, tu peux les passer directement
    # sinon tu peux calculer N_avant/N_arriere statiques via lr/lf (voir ton module calcul_charges_essieux)
    charge_essieu_moteur_n: float,
    force_resistance_n: float,
    type_milieu: str = "FWD",
    include_transfert: bool = False,
    clamp_non_negative: bool = True,
) -> float:
    """
    Wrapper direct sur ton module d'accélération max.
    Utile si tu veux "clamp" une accélération demandée par le moteur
    aux limites d'adhérence.
    """
    return calcul_acceleration_max(
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
