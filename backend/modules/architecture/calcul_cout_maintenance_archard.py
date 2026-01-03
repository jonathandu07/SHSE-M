# backend\modules\architecture\calcul_cout_maintenance_archard.py
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
    """Exige x > 0 (ou x >= 0 si strict=False)."""
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _exiger_int_positif(nom: str, x: int, *, strict: bool = True) -> int:
    """Exige un entier > 0 (ou >= 0 si strict=False)."""
    if not isinstance(x, int):
        raise ValueError(f"{nom} doit être un entier (reçu: {x!r}).")
    ok = x > 0 if strict else x >= 0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_cout_maintenance_estime(
    duree_usage_h: float,
    duree_vie_joint_base_h: float,
    charge_nominale_n: float,
    charge_actuelle_n: float,
    nb_joints_base: int,
    nb_joints_actuel: int,
    cout_inter_eur: float,
) -> float:
    """
    Estime le coût de maintenance lié à l'usure des joints (modèle empirique type Archard).

    Objectif :
    - Donner un ordre de grandeur de coût sur un horizon d'utilisation,
      en tenant compte du fait que :
        - plus la charge sur un joint est élevée, plus la durée de vie baisse,
        - plus il y a de joints, plus une intervention coûte (pièces, MO, etc.).

    Modèle utilisé (inchangé dans l'esprit, fiabilisé) :
      Cost_total = N_interventions * Cout_par_intervention

      N_interventions ≈ T / L_seal
      L_seal = L0 * (W0 / W)^β

    Où :
    - T : durée d'usage (h)
    - L0 : durée de vie de référence d'un joint (h) à la charge W0
    - W0 : charge nominale de référence (N)
    - W : charge actuelle (N)
    - β : exposant empirique d'usure (sans dimension)
    - Cout_par_intervention = Cout_intervention * (N_joints_actuel / N_joints_base)

    Paramètres :
    - duree_usage_h : T (h) (>= 0)
    - duree_vie_joint_base_h : L0 (h) (> 0)
    - charge_nominale_n : W0 (N) (> 0)
    - charge_actuelle_n : W (N) (>= 0) ; si W <= 0 => coût retourné = 0.0 (comme ton code)
    - nb_joints_base : nombre de joints de référence (> 0)
    - nb_joints_actuel : nombre de joints pour la configuration actuelle (>= 0)
    - cout_inter_eur : coût forfaitaire d'une intervention (EUR) (>= 0)

    Retour :
    - Coût total estimé (EUR) en float.
    """
    # Exposant empirique d'usure : valeur typique à calibrer sur données réelles
    beta_wear = 1.5

    # Validation robuste (sans changer les retours : toujours float)
    T = _exiger_positif("duree_usage_h", duree_usage_h, strict=False)
    L0 = _exiger_positif("duree_vie_joint_base_h", duree_vie_joint_base_h, strict=True)
    W0 = _exiger_positif("charge_nominale_n", charge_nominale_n, strict=True)
    W = _exiger_fini("charge_actuelle_n", charge_actuelle_n)
    nb_base = _exiger_int_positif("nb_joints_base", nb_joints_base, strict=True)
    nb_actuel = _exiger_int_positif("nb_joints_actuel", nb_joints_actuel, strict=False)
    cout_inter = _exiger_positif("cout_inter_eur", cout_inter_eur, strict=False)

    # Comportement historique : si charge actuelle <= 0 => coût nul
    if W <= 0.0:
        return 0.0

    # Durée de vie estimée : L = L0 * (W0/W)^β
    # - Si W > W0, le ratio < 1 => durée de vie diminue
    # - Si W < W0, le ratio > 1 => durée de vie augmente
    ratio_charge = W0 / W
    duree_vie_estimee = L0 * (ratio_charge ** beta_wear)

    # Protection : si duree_vie_estimee ~ 0 (cas extrême), coût tend vers +inf.
    # Ici on explicite l'erreur plutôt que de produire des nombres instables.
    if duree_vie_estimee <= 0.0 or not math.isfinite(duree_vie_estimee):
        raise ValueError("Durée de vie estimée non valide (vérifier charges et paramètres).")

    # Nombre d'interventions sur la période
    nb_interventions = T / duree_vie_estimee

    # Coût par intervention : proportionnel au nombre de joints
    # (si nb_actuel = 0, coût pièces/joints peut être nul => coût par inter = 0)
    facteur_joints = nb_actuel / nb_base
    cout_par_inter = cout_inter * facteur_joints

    # Coût total
    return nb_interventions * cout_par_inter
