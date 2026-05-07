# backend\modules\moteur_thermique\calcul_pertes_frottement.py
from __future__ import annotations

import math
from typing import Iterable, Sequence


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
    Utile pour imposer des contraintes physiques (vitesses, charges, coefficients, etc.).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _somme_controles(nom: str, valeurs: Iterable[float]) -> float:
    total = 0.0
    for i, v in enumerate(valeurs):
        total += _exiger_positif(f"{nom}[{i}]", v, strict=False)
    return total


def _verifier_memes_longueurs(*series: Sequence[float]) -> None:
    if not series:
        return
    n = len(series[0])
    for s in series[1:]:
        if len(s) != n:
            raise ValueError("Les séquences doivent avoir la même longueur.")


def calcul_puissance_frottement_segment(
    force_normale_n: float,
    vitesse_moyenne_ms: float,
    coef_frottement: float,
) -> float:
    """
    Estime la puissance dissipée par frottement au niveau d'un segment (ou joint).

    Modèle simple de frottement sec / Coulomb :
      P_f = μ * N * v

    Où :
    - P_f : puissance dissipée (W)
    - μ   : coefficient de frottement (sans dimension)
    - N   : force normale de contact (N)
    - v   : vitesse de glissement moyenne (m/s)
    """
    mu = _exiger_positif("coef_frottement", coef_frottement, strict=False)
    N = _exiger_positif("force_normale_n", force_normale_n, strict=False)
    v = _exiger_positif("vitesse_moyenne_ms", vitesse_moyenne_ms, strict=False)
    return mu * N * v


def calcul_puissance_frottement_palier(
    charge_w: float,
    vitesse_glissement_ms: float,
    coef_frottement_f: float,
) -> float:
    """
    Estime la puissance dissipée dans un palier lisse via un modèle simplifié :
      P_f = f * W * v

    Où :
    - P_f : puissance dissipée (W)
    - f   : coefficient de frottement
    - W   : charge sur le palier (N)
    - v   : vitesse de glissement (m/s)
    """
    f = _exiger_positif("coef_frottement_f", coef_frottement_f, strict=False)
    W = _exiger_positif("charge_w", charge_w, strict=False)
    v = _exiger_positif("vitesse_glissement_ms", vitesse_glissement_ms, strict=False)
    return f * W * v


def calcul_vitesse_glissement_palier_depuis_diametre(
    diametre_arbre_m: float,
    regime_tr_min: float,
) -> float:
    """
    Vitesse périphérique de l'arbre sur le palier :
      v = pi * D * n / 60
    """
    D = _exiger_positif("diametre_arbre_m", diametre_arbre_m, strict=False)
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=False)
    return math.pi * D * n / 60.0


def calcul_couple_frottement_depuis_puissance(
    puissance_frottement_w: float,
    regime_tr_min: float,
) -> float:
    """
    Convertit une puissance dissipée en couple de frottement moyen :
      P = C * omega
      C = P / omega
    """
    P = _exiger_positif("puissance_frottement_w", puissance_frottement_w, strict=False)
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=True)
    omega = 2.0 * math.pi * n / 60.0
    return P / omega


def calcul_puissance_frottement_depuis_couple(
    couple_frottement_nm: float,
    regime_tr_min: float,
) -> float:
    """
    Convertit un couple de frottement moyen en puissance dissipée :
      P = C * omega
    """
    C = _exiger_positif("couple_frottement_nm", couple_frottement_nm, strict=False)
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=False)
    omega = 2.0 * math.pi * n / 60.0
    return C * omega


def calcul_puissance_frottement_segments_total(
    forces_normales_n: Sequence[float],
    vitesses_moyennes_ms: Sequence[float],
    coefs_frottement: Sequence[float],
) -> float:
    """
    Somme des pertes de plusieurs segments / bandes de contact.

    Chaque triplet (N_i, v_i, mu_i) est traité par :
      P_i = mu_i * N_i * v_i
    """
    _verifier_memes_longueurs(forces_normales_n, vitesses_moyennes_ms, coefs_frottement)

    total = 0.0
    for i, (N, v, mu) in enumerate(zip(forces_normales_n, vitesses_moyennes_ms, coefs_frottement)):
        total += calcul_puissance_frottement_segment(
            force_normale_n=_exiger_positif(f"forces_normales_n[{i}]", N, strict=False),
            vitesse_moyenne_ms=_exiger_positif(f"vitesses_moyennes_ms[{i}]", v, strict=False),
            coef_frottement=_exiger_positif(f"coefs_frottement[{i}]", mu, strict=False),
        )
    return total


def calcul_puissance_frottement_paliers_total(
    charges_w_n: Sequence[float],
    vitesses_glissement_ms: Sequence[float],
    coefs_frottement_f: Sequence[float],
) -> float:
    """
    Somme des pertes de plusieurs paliers lisses.

    Chaque triplet (W_i, v_i, f_i) est traité par :
      P_i = f_i * W_i * v_i
    """
    _verifier_memes_longueurs(charges_w_n, vitesses_glissement_ms, coefs_frottement_f)

    total = 0.0
    for i, (W, v, f) in enumerate(zip(charges_w_n, vitesses_glissement_ms, coefs_frottement_f)):
        total += calcul_puissance_frottement_palier(
            charge_w=_exiger_positif(f"charges_w_n[{i}]", W, strict=False),
            vitesse_glissement_ms=_exiger_positif(f"vitesses_glissement_ms[{i}]", v, strict=False),
            coef_frottement_f=_exiger_positif(f"coefs_frottement_f[{i}]", f, strict=False),
        )
    return total


def calcul_couple_frottement_visqueux_palier_concentrique(
    viscosite_dynamique_pa_s: float,
    rayon_arbre_m: float,
    longueur_palier_m: float,
    jeu_radial_m: float,
    regime_tr_min: float,
) -> float:
    """
    Couple visqueux d'un palier journal concentrique très simplifié (film mince, Couette pur) :

      tau = mu * (omega * R / c)
      T = tau * (2*pi*R*L) * R
        = 2*pi * mu * omega * L * R^3 / c

    Hypothèses :
    - arbre centré,
    - film uniforme,
    - pas d'effet d'excentricité,
    - ordre de grandeur pour pré-dimensionnement.
    """
    mu = _exiger_positif("viscosite_dynamique_pa_s", viscosite_dynamique_pa_s, strict=False)
    R = _exiger_positif("rayon_arbre_m", rayon_arbre_m, strict=False)
    L = _exiger_positif("longueur_palier_m", longueur_palier_m, strict=False)
    c = _exiger_positif("jeu_radial_m", jeu_radial_m, strict=True)
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=False)

    omega = 2.0 * math.pi * n / 60.0
    return 2.0 * math.pi * mu * omega * L * (R ** 3) / c


def calcul_puissance_frottement_visqueux_palier_concentrique(
    viscosite_dynamique_pa_s: float,
    rayon_arbre_m: float,
    longueur_palier_m: float,
    jeu_radial_m: float,
    regime_tr_min: float,
) -> float:
    """
    Puissance dissipée par cisaillement visqueux dans un palier concentrique :
      P = T * omega
    """
    T = calcul_couple_frottement_visqueux_palier_concentrique(
        viscosite_dynamique_pa_s=viscosite_dynamique_pa_s,
        rayon_arbre_m=rayon_arbre_m,
        longueur_palier_m=longueur_palier_m,
        jeu_radial_m=jeu_radial_m,
        regime_tr_min=regime_tr_min,
    )
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=False)
    omega = 2.0 * math.pi * n / 60.0
    return T * omega


def calcul_puissance_frottement_moteur_totale(
    puissances_segments_w: Sequence[float] | None = None,
    puissances_paliers_w: Sequence[float] | None = None,
    autres_puissances_w: Sequence[float] | None = None,
) -> float:
    """
    Somme globale des pertes de frottement déjà calculées composant par composant.
    Aucun modèle caché : on additionne simplement les puissances.
    """
    total = 0.0
    if puissances_segments_w is not None:
        total += _somme_controles("puissances_segments_w", puissances_segments_w)
    if puissances_paliers_w is not None:
        total += _somme_controles("puissances_paliers_w", puissances_paliers_w)
    if autres_puissances_w is not None:
        total += _somme_controles("autres_puissances_w", autres_puissances_w)
    return total


def calcul_fmep_depuis_puissance_frottement(
    puissance_frottement_w: float,
    cylindree_totale_m3: float,
    regime_tr_min: float,
    *,
    temps_moteur: int = 4,
) -> float:
    """
    Convertit une puissance moyenne de frottement en FMEP (Pa).

    Pour un moteur 4T :
      P = FMEP * Vd * n / 120

    Pour un moteur 2T :
      P = FMEP * Vd * n / 60
    """
    P = _exiger_positif("puissance_frottement_w", puissance_frottement_w, strict=False)
    Vd = _exiger_positif("cylindree_totale_m3", cylindree_totale_m3, strict=True)
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=True)

    if temps_moteur == 4:
        freq = n / 120.0
    elif temps_moteur == 2:
        freq = n / 60.0
    else:
        raise ValueError("temps_moteur doit être 2 ou 4.")

    return P / (Vd * freq)


def calcul_rendement_mecanique_depuis_puissances(
    puissance_indiquee_w: float,
    puissance_frottement_w: float,
) -> float:
    """
    Rendement mécanique :
      eta_m = P_b / P_i = (P_i - P_f) / P_i
    """
    Pi = _exiger_positif("puissance_indiquee_w", puissance_indiquee_w, strict=True)
    Pf = _exiger_positif("puissance_frottement_w", puissance_frottement_w, strict=False)

    if Pf > Pi:
        raise ValueError("puissance_frottement_w ne peut pas dépasser puissance_indiquee_w.")

    return (Pi - Pf) / Pi


__all__ = [
    "_est_fini",
    "_exiger_fini",
    "_exiger_positif",
    "calcul_puissance_frottement_segment",
    "calcul_puissance_frottement_palier",
    "calcul_vitesse_glissement_palier_depuis_diametre",
    "calcul_couple_frottement_depuis_puissance",
    "calcul_puissance_frottement_depuis_couple",
    "calcul_puissance_frottement_segments_total",
    "calcul_puissance_frottement_paliers_total",
    "calcul_couple_frottement_visqueux_palier_concentrique",
    "calcul_puissance_frottement_visqueux_palier_concentrique",
    "calcul_puissance_frottement_moteur_totale",
    "calcul_fmep_depuis_puissance_frottement",
    "calcul_rendement_mecanique_depuis_puissances",
]