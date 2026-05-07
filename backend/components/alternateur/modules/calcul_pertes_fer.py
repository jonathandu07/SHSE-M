# backend\modules\alternateur\calcul_pertes_fer.py
from __future__ import annotations

import math
from typing import Literal, Optional


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


def calcul_pertes_fer_steinmetz(
    k_h: float,
    frequence: float,
    induction_max: float,
    exposant_steinmetz: float,
    k_e: float,
    *,
    # Optionnel : loi "généralisée" pour les pertes Foucault: k_e * f^a * B^b
    eddy_freq_exp: float = 2.0,
    eddy_induction_exp: float = 2.0,
    # Optionnel : conversion en pertes totales si on fournit masse ou volume
    masse_kg: Optional[float] = None,
    volume_m3: Optional[float] = None,
    # Si True, renvoie aussi le détail des termes
    return_details: bool = False,
    clamp_non_negative: bool = True,
) -> float | dict[str, float]:
    """
    Estime les pertes fer (hystérésis + courants de Foucault) via un modèle type Steinmetz.

    Modèle de base (spécifique) :
      P_fe_spec = k_h * f * B^x  +  k_e * f^2 * B^2

    Extension optionnelle (généralisée pour Foucault) :
      P_eddy = k_e * f^(eddy_freq_exp) * B^(eddy_induction_exp)

    Unités :
    - Si k_h et k_e sont calibrés en W/kg (ou W/m³), la sortie est W/kg (ou W/m³).
    - Si masse_kg est fournie (et que les coefficients sont en W/kg), alors P_totale = P_spec * masse.
    - Si volume_m3 est fourni (et que les coefficients sont en W/m³), alors P_totale = P_spec * volume.
    (Ne fournis pas masse_kg ET volume_m3 en même temps.)

    Paramètres :
    - k_h : coefficient hystérésis (>=0)
    - frequence : f (Hz) (>=0)
    - induction_max : B (T) (>=0)
    - exposant_steinmetz : x (souvent ~1.5 à 2.5), non contraint ici
    - k_e : coefficient Foucault (>=0)
    - eddy_freq_exp / eddy_induction_exp : exposants pour le terme Foucault (défaut 2 et 2)
    - masse_kg / volume_m3 : optionnel, pour passer de pertes spécifiques à pertes totales
    - return_details : si True, renvoie un dict détaillant hyst/eddy/total
    - clamp_non_negative : borne à >= 0

    Retour :
    - float (par défaut) : pertes spécifiques ou totales selon masse/volume fournis
    - dict si return_details=True
    """
    kh = _require_positive("k_h", k_h, strictly=False)
    ke = _require_positive("k_e", k_e, strictly=False)
    f = _require_positive("frequence", frequence, strictly=False)
    B = _require_positive("induction_max", induction_max, strictly=False)
    x = _require_finite("exposant_steinmetz", exposant_steinmetz)

    a_f = _require_finite("eddy_freq_exp", eddy_freq_exp)
    b_B = _require_finite("eddy_induction_exp", eddy_induction_exp)

    if masse_kg is not None and volume_m3 is not None:
        raise ValueError("Fournis soit masse_kg, soit volume_m3, pas les deux.")

    # Termes spécifiques (W/kg ou W/m³ selon calibration des coefficients)
    pertes_hyst = kh * f * (B ** x)
    pertes_eddy = ke * (f ** a_f) * (B ** b_B)
    pertes_spec = pertes_hyst + pertes_eddy

    if clamp_non_negative:
        pertes_hyst = max(0.0, pertes_hyst)
        pertes_eddy = max(0.0, pertes_eddy)
        pertes_spec = max(0.0, pertes_spec)

    # Passage en pertes totales si masse/volume fourni
    facteur = 1.0
    if masse_kg is not None:
        m = _require_positive("masse_kg", masse_kg, strictly=True)
        facteur = m
    elif volume_m3 is not None:
        V = _require_positive("volume_m3", volume_m3, strictly=True)
        facteur = V

    pertes_tot = pertes_spec * facteur

    if return_details:
        return {
            "P_hyst": pertes_hyst * facteur,
            "P_eddy": pertes_eddy * facteur,
            "P_total": pertes_tot,
            "P_spec": pertes_spec,
            "facteur_totalisation": facteur,
        }

    return pertes_tot
