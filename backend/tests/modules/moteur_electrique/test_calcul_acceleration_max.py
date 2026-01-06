from __future__ import annotations

import math
from typing import Literal, Optional


DriveMode = Literal["FWD", "RWD", "AWD"]
_G0 = 9.80665  # m/s² (gravité standard)


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


def _parse_mode(mode: str) -> DriveMode:
    if not isinstance(mode, str):
        raise ValueError("mode/type_milieu doit être une chaîne ('FWD', 'RWD', 'AWD').")
    m = mode.strip().upper()
    if m in ("FWD", "FRONT", "AVANT"):
        return "FWD"
    if m in ("RWD", "REAR", "ARRIERE", "ARRIÈRE"):
        return "RWD"
    if m in ("AWD", "4WD", "4X4", "QUATTRO", "INTEGRAL", "INTÉGRAL"):
        return "AWD"
    raise ValueError("Mode doit être 'FWD', 'RWD' ou 'AWD'.")


def calcul_acceleration_max(
    mu_adherence: float,
    charge_essieu_moteur_n: float,
    force_resistance_n: float,
    masse_kg: float,
    hauteur_cg_m: float,
    empattement_m: float,
    type_milieu: str = "fwd",
    *,
    include_transfert: bool = False,
    clamp_non_negative: bool = False,
) -> float:
    """
    Calcule l'accélération max limitée par l'adhérence.

    Paramètres (unités SI) :
    - mu_adherence: coefficient d'adhérence (>= 0)
    - charge_essieu_moteur_n: charge normale (N) sur les roues motrices.
      *En mode AWD, passe idéalement la somme des charges normales sur toutes les roues motrices
      (souvent ~ m*g si route plane), sinon le résultat sera conservateur.*
    - force_resistance_n: force résistante totale (N) dans l'axe du mouvement (roulement, aéro,
      pente si tu l’inclus, etc.).
    - masse_kg: masse totale (kg)
    - hauteur_cg_m: hauteur du centre de gravité (m)
    - empattement_m: empattement (m)
    - type_milieu: 'fwd'/'rwd'/'awd' (insensible à la casse)

    Options :
    - include_transfert:
        False (défaut) -> formule simple: Fmax = mu * N_drive (N fourni), puis a = (Fmax - Fres)/m
        True -> inclut un transfert de charge longitudinal simplifié via une résolution analytique
                (couplage a <-> transfert). Requiert h et L cohérents.
        Remarque: cette option suppose que charge_essieu_moteur_n est la charge *statique* (ou quasi)
        de l’essieu moteur sur terrain plat, et applique un modèle de transfert en accélération.
    - clamp_non_negative:
        True -> borne a >= 0 (utile si Fres > mu*N)
        False -> peut retourner une accélération négative (physiquement: décélération nette).

    Retour :
    - accélération max (m/s²)
    """
    mu = _require_positive("mu_adherence", mu_adherence, strictly=False)
    N_drive = _require_positive("charge_essieu_moteur_n", charge_essieu_moteur_n, strictly=False)
    Fres = _require_finite("force_resistance_n", force_resistance_n)
    m = _require_positive("masse_kg", masse_kg, strictly=True)
    h = _require_positive("hauteur_cg_m", hauteur_cg_m, strictly=False)
    L = _require_positive("empattement_m", empattement_m, strictly=True)

    mode = _parse_mode(type_milieu)

    # Cas simple (compatible avec ton code actuel)
    if not include_transfert or mode == "AWD" or h == 0.0:
        a = (mu * N_drive - Fres) / m
        return max(0.0, a) if clamp_non_negative else a

    # Transfert de charge longitudinal simplifié (résolution analytique)
    # Hypothèse: N_drive = N_static +/- (m*a*h/L) selon l'essieu moteur.
    # F_traction_max = mu * N_drive
    # m*a = F_traction_max - Fres
    # => a = (mu*N_static - Fres) / (m*(1 +/- mu*h/L)) avec + pour FWD, - pour RWD
    if mode == "FWD":
        denom = m * (1.0 + (mu * h / L))
    else:  # "RWD"
        denom = m * (1.0 - (mu * h / L))

    if denom <= 0.0 or not math.isfinite(denom):
        raise ValueError(
            "Dénominateur non-physique (<=0). Vérifie mu, h, L (risque de wheelie/paramètres incohérents)."
        )

    a = (mu * N_drive - Fres) / denom
    return max(0.0, a) if clamp_non_negative else a


def calcul_acceleration_max_analytique(
    mu: float,
    masse: float,
    g: float,
    lr: float,
    lf: float,
    h: float,
    L: float,
    theta: float,
    Fres: float,
    mode: str = "FWD",
    *,
    theta_unite: Literal["rad", "deg"] = "rad",
    clamp_non_negative: bool = False,
) -> float:
    """
    Formule analytique (1D) pour l'accélération maximale limitée par l'adhérence, avec transfert.

    IMPORTANT (cohérence des forces) :
    - Fres doit représenter la force résistante *totale* dans l’axe du déplacement.
      Si tu veux inclure la pente, inclue typiquement m*g*sin(theta) dans Fres (en plus du roulement/aéro).
      Cette fonction n’ajoute PAS automatiquement m*g*sin(theta).

    Paramètres :
    - mu: coefficient d'adhérence (>=0)
    - masse: masse (kg)
    - g: gravité (m/s²), typiquement 9.80665
    - lr, lf: distances CG->essieu AR et CG->essieu AV (m)
    - h: hauteur CG (m)
    - L: empattement (m) (idéalement ~ lr+lf)
    - theta: angle de pente (rad par défaut, ou degrés si theta_unite='deg')
    - Fres: résistances (N)
    - mode: 'FWD' ou 'RWD' (insensible à la casse)

    Retour :
    - a_max en m/s²
    """
    mu = _require_positive("mu", mu, strictly=False)
    m = _require_positive("masse", masse, strictly=True)
    g = _require_positive("g", g, strictly=True)
    lr = _require_positive("lr", lr, strictly=False)
    lf = _require_positive("lf", lf, strictly=False)
    h = _require_positive("h", h, strictly=False)
    L = _require_positive("L", L, strictly=True)
    Fres = _require_finite("Fres", Fres)

    dm = _parse_mode(mode)
    if dm == "AWD":
        raise ValueError("Cette formule analytique est définie ici pour 'FWD' ou 'RWD' uniquement.")

    # Cohérence géométrique (tolérance souple)
    if lr > 0.0 and lf > 0.0:
        s = lr + lf
        if abs(s - L) / max(L, 1e-9) > 0.02:  # 2%
            raise ValueError(f"Incohérence: lr+lf={s} m ne correspond pas à L={L} m (tolérance 2%).")

    th = math.radians(theta) if theta_unite == "deg" else theta
    cos_th = math.cos(th)
    sin_th = math.sin(th)

    # Dénominateurs de transfert
    if dm == "FWD":
        denom = 1.0 + (mu * h / L)
        numer = mu * ((g * cos_th * lr / L) - (g * sin_th * h / L)) - (Fres / m)
    else:  # RWD
        denom = 1.0 - (mu * h / L)
        numer = mu * ((g * cos_th * lf / L) + (g * sin_th * h / L)) - (Fres / m)

    if denom <= 0.0 or not math.isfinite(denom):
        raise ValueError(
            "Dénominateur non-physique (<=0). Vérifie mu, h, L (risque de wheelie/paramètres incohérents)."
        )

    a = numer / denom
    return max(0.0, a) if clamp_non_negative else a
