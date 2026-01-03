from __future__ import annotations

import math
from typing import Literal


_G0 = 9.80665  # m/s²


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


def calcul_force_resistance_totale(
    masse_kg: float,
    vitesse_ms: float,
    angle_pente: float,
    coef_roulement: float,
    coef_trainee_aero_cda: float,
    densite_air: float = 1.2,
    gravite: float = _G0,
    *,
    angle_unite: Literal["rad", "deg"] = "rad",
    # Si tu veux que les forces s'opposent toujours au mouvement, laisse True.
    # Si False, la composante pente garde son signe (montée +, descente -).
    oppose_mouvement: bool = True,
    # Utile si vitesse_ms peut être négative dans ton modèle (sens de déplacement).
    use_speed_sign: bool = True,
    # Pour debug/traçage
    return_details: bool = False,
) -> dict[str, float]:
    """
    Calcule les forces résistantes appliquées au véhicule (1D).

    Modèle :
    - Roulement : F_roll = m*g*Crr*cos(theta)
    - Aérodynamique : F_aero = 0.5*rho*CdA*v²
    - Pente : F_grade = m*g*sin(theta)

    Conventions :
    - angle_pente > 0 : montée.
    - Si oppose_mouvement=True (défaut), les forces retournées sont orientées
      pour s'opposer au mouvement (i.e. >= 0 en "valeur résistante").
      Dans ce cas, la pente en descente devient une "aide" et est retournée
      comme résistance négative (ou 0 selon ton traitement aval) — ici on la
      retourne avec le signe opposé au mouvement.
    - Si oppose_mouvement=False, F_pente conserve son signe physique (+ montée, - descente).
    - Si use_speed_sign=True, on oriente l'opposition au mouvement selon le signe de v.

    Retour :
      dict avec au minimum:
        - F_roulement (N)
        - F_aero (N)
        - F_pente (N)
        - F_totale (N)
      et optionnellement des détails si return_details=True.
    """
    m = _require_positive("masse_kg", masse_kg, strictly=True)
    v = _require_finite("vitesse_ms", vitesse_ms)
    crr = _require_positive("coef_roulement", coef_roulement, strictly=False)
    cda = _require_positive("coef_trainee_aero_cda", coef_trainee_aero_cda, strictly=False)
    rho = _require_positive("densite_air", densite_air, strictly=True)
    g = _require_positive("gravite", gravite, strictly=True)

    theta = math.radians(angle_pente) if angle_unite == "deg" else _require_finite("angle_pente", angle_pente)

    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    # Magnitudes (toujours >= 0)
    F_roulement_mag = m * g * crr * cos_t
    F_aero_mag = 0.5 * rho * cda * (abs(v) ** 2)
    # composante due à la pente (peut être + ou - selon convention)
    F_pente_phys = m * g * sin_t

    # Orientation (signe) : s'oppose au mouvement
    # si v==0, on prend +1 par défaut (les forces "résistantes" restent positives).
    v_sign = 1.0
    if use_speed_sign:
        v_sign = 1.0 if v >= 0.0 else -1.0

    if oppose_mouvement:
        # Roulement et aéro s'opposent toujours au mouvement
        F_roulement = F_roulement_mag * v_sign
        F_aero = F_aero_mag * v_sign

        # Pour la pente:
        # en montée (sin>0) la pente s'oppose au mouvement si on monte (v_sign>0).
        # en descente (sin<0) la pente aide le mouvement si on avance (v_sign>0),
        # donc elle devient une "résistance" négative.
        F_pente = F_pente_phys * v_sign
    else:
        # Forces "physiques" dans l'axe (roulement/aéro restent des pertes -> on les laisse positives en magnitude)
        # et la pente conserve son signe (+ montée, - descente).
        F_roulement = F_roulement_mag
        F_aero = F_aero_mag
        F_pente = F_pente_phys

    F_totale = F_roulement + F_aero + F_pente

    out: dict[str, float] = {
        "F_roulement": F_roulement,
        "F_aero": F_aero,
        "F_pente": F_pente,
        "F_totale": F_totale,
    }

    if return_details:
        out.update(
            {
                "details_theta_rad": theta,
                "details_cos_theta": cos_t,
                "details_sin_theta": sin_t,
                "details_v_sign": v_sign,
                "details_F_roulement_mag": F_roulement_mag,
                "details_F_aero_mag": F_aero_mag,
                "details_F_pente_phys": F_pente_phys,
            }
        )

    return out
