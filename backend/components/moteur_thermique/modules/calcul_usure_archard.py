# backend\modules\moteur_thermique\calcul_usure_archard.py
from __future__ import annotations

import math


def _est_fini(x: float) -> bool:
    """Vérifie qu'une valeur est un nombre réel fini (pas NaN, pas inf)."""
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: float) -> float:
    """Convertit en float et lève une erreur si NaN/inf."""
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    """
    Exige x > 0 (ou x >= 0 si strict=False).
    Utile pour imposer des contraintes physiques (dures, surfaces, distances...).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_volume_usure_archard(
    coefficient_usure_k: float,
    charge_normale_w: float,
    distance_glissement_ls: float,
    durete_h: float,
) -> float:
    """
    Calcule le volume de matière usée via la loi d'Archard (modèle classique d'usure adhésive).

    Formule (inchangée) :
      V_w = k * (W * Ls) / H

    Où :
    - V_w : volume usé (m³)
    - k : coefficient d'usure (sans dimension), typiquement ~1e-4 à 1e-8 (ordre de grandeur)
    - W : charge normale (N) (>= 0)
    - Ls : distance totale de glissement (m) (>= 0)
    - H : dureté du matériau le plus tendre (Pa) (> 0)

    Robustesse / contraintes physiques :
    - k >= 0 (si k = 0 => usure nulle)
    - W >= 0
    - Ls >= 0
    - H > 0 (sinon division par zéro / non physique)

    Remarque unités :
    - H est en Pascal. Les duretés Vickers/Brinell doivent être converties si nécessaire.
    """
    k = _exiger_positif("coefficient_usure_k", coefficient_usure_k, strict=False)
    W = _exiger_positif("charge_normale_w", charge_normale_w, strict=False)
    Ls = _exiger_positif("distance_glissement_ls", distance_glissement_ls, strict=False)
    H = _exiger_positif("durete_h", durete_h, strict=True)

    return k * (W * Ls) / H


def calcul_perte_epaisseur(volume_use_m3: float, aire_contact_m2: float) -> float:
    """
    Calcule la perte d'épaisseur moyenne équivalente à partir du volume usé.

    Formule (inchangée) :
      Δh = V_w / A

    Où :
    - Δh : perte d'épaisseur moyenne (m)
    - V_w : volume usé (m³) (>= 0 dans le cadre Archard)
    - A : aire de contact (m²) (> 0)

    Robustesse :
    - volume_use_m3 doit être fini (et en pratique >= 0)
    - aire_contact_m2 > 0
    """
    Vw = _exiger_fini("volume_use_m3", volume_use_m3)
    A = _exiger_positif("aire_contact_m2", aire_contact_m2, strict=True)

    # On n'impose pas Vw >= 0 par erreur "bloquante" : certains pipelines peuvent porter un signe.
    # Si tu veux le verrouiller, fais-le dans le code appelant.
    return Vw / A
