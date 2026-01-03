# backend\modules\moteur_thermique\calcul_epaisseur_paroi_cylindre.py
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


def calcul_epaisseur_cylindre_mince(
    pression_pa: float,
    rayon_interne_m: float,
    contrainte_admissible_pa: float,
    *,
    # Options non intrusives (défaut = comportement historique)
    include_longitudinale: bool = False,
    facteur_securite: float = 1.0,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule l'épaisseur minimale d'un cylindre mince sous pression interne.

    Modèle de base (contraintes de membrane, paroi mince) :
      - Contrainte circonférentielle (hoop) : σ_θ = p * r_i / t
        => t >= p * r_i / σ_adm

    Option :
      - Contrainte longitudinale : σ_L = p * r_i / (2t)
        (si include_longitudinale=True, on dimensionne sur la contrainte la plus pénalisante)

    Paramètres :
    - pression_pa : p (Pa) (>=0)
    - rayon_interne_m : r_i (m) (>0)
    - contrainte_admissible_pa : σ_adm (Pa) (>0)
    - include_longitudinale : False (défaut) -> dimensionne sur σ_θ uniquement
    - facteur_securite : FS (>=1 typiquement), appliqué sur la contrainte admissible effective :
        σ_eff = σ_adm / FS
      Défaut 1.0 (aucun changement).
    - clamp_non_negative : True -> borne t à >= 0
    - return_details : True -> renvoie aussi les contraintes ciblées et σ_eff

    Retour :
    - épaisseur minimale t (m) ou dict si return_details=True
    """
    p = _require_positive("pression_pa", pression_pa, strictly=False)
    ri = _require_positive("rayon_interne_m", rayon_interne_m, strictly=True)
    sigma_adm = _require_positive("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _require_positive("facteur_securite", facteur_securite, strictly=True)

    # Contrainte admissible "effective" après facteur de sécurité
    sigma_eff = sigma_adm / fs

    # Dimensionnement par contrainte circonférentielle
    t_hoop = (p * ri) / sigma_eff if sigma_eff > 0 else float("inf")

    # Dimensionnement par contrainte longitudinale (si demandé)
    # => t >= p*ri/(2*sigma_eff) (moins pénalisant que hoop en général)
    t_long = (p * ri) / (2.0 * sigma_eff) if sigma_eff > 0 else float("inf")

    # On prend la plus grande des exigences (la plus pénalisante)
    t_req = max(t_hoop, t_long) if include_longitudinale else t_hoop

    if clamp_non_negative:
        t_req = max(0.0, t_req)

    if return_details:
        return {
            "t": t_req,
            "t_hoop": t_hoop,
            "t_long": t_long,
            "p": p,
            "ri": ri,
            "sigma_adm": sigma_adm,
            "facteur_securite": fs,
            "sigma_eff": sigma_eff,
            "include_longitudinale": 1.0 if include_longitudinale else 0.0,
        }
    return t_req


def calcul_epaisseur_cylindre_lame(
    pression_interne_pa: float,
    rayon_interne_m: float,
    contrainte_admissible_pa: float,
    *,
    # Options non intrusives (défaut = comportement historique)
    hypothese: Literal["tangentiel_ri"] = "tangentiel_ri",
    facteur_securite: float = 1.0,
    epsilon: float = 1e-12,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule l'épaisseur d'un cylindre épais (Lamé) sous pression interne, en limitant σ_θ au rayon interne.

    Hypothèse (comme ton code) :
      σ_θ(r_i) = p * (r_o² + r_i²) / (r_o² - r_i²)  <= σ_adm

    Inversion :
      r_o = r_i * sqrt( (σ_adm + p) / (σ_adm - p) )
      t = r_o - r_i

    Paramètres :
    - pression_interne_pa : p (Pa) (>=0)
    - rayon_interne_m : r_i (m) (>0)
    - contrainte_admissible_pa : σ_adm (Pa) (>0)
    - facteur_securite : FS (>=1 typiquement), σ_eff = σ_adm / FS
      Défaut 1.0 (aucun changement).
    - epsilon : seuil anti-instabilité lorsque σ_eff ≈ p
    - clamp_non_negative : True -> borne t à >= 0
    - return_details : True -> renvoie r_o, ratio, etc.

    Retour :
    - épaisseur t (m) ou dict si return_details=True
    """
    p = _require_positive("pression_interne_pa", pression_interne_pa, strictly=False)
    ri = _require_positive("rayon_interne_m", rayon_interne_m, strictly=True)
    sigma_adm = _require_positive("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _require_positive("facteur_securite", facteur_securite, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)

    sigma_eff = sigma_adm / fs

    # Condition de faisabilité (sinon dénominateur <= 0)
    if sigma_eff <= p + eps:
        raise ValueError(
            "Dimensionnement impossible/instable: il faut sigma_adm/FS > p (avec marge). "
            f"(sigma_eff={sigma_eff}, p={p})"
        )

    ratio = (sigma_eff + p) / (sigma_eff - p)
    if ratio < 1.0:
        # Théoriquement ratio >= 1 si sigma_eff > p, mais on protège le cas numérique/pathologique.
        raise ValueError("Ratio Lamé inattendu (<1). Vérifie les paramètres.")

    ro = ri * math.sqrt(ratio)
    t = ro - ri

    if clamp_non_negative:
        t = max(0.0, t)

    if return_details:
        return {
            "t": t,
            "ri": ri,
            "ro": ro,
            "p": p,
            "sigma_adm": sigma_adm,
            "facteur_securite": fs,
            "sigma_eff": sigma_eff,
            "ratio": ratio,
            "hypothese": 1.0,  # placeholder simple (évite d'exporter du texte si tu logs en CSV)
        }
    return t
