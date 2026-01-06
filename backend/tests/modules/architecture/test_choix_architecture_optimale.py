# backend\modules\architecture\choix_architecture_optimale.py
from __future__ import annotations

import math
from typing import Tuple


# =============================================================================
# Utilitaires robustesse (non intrusifs)
# =============================================================================

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
    Longueurs et largeurs disponibles doivent être > 0.
    """
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


# =============================================================================
# Modèle d'encombrement/complexité : paramétrage centralisé
# =============================================================================
# But : retirer des "inconnues" en rendant les hypothèses EXPLICITES et modifiables.
# - pas_cylindre_m : pas longitudinal moyen par cylindre (axe à axe), inclut carter/entretoises.
# - largeur_base_m : largeur typique d'un bloc en ligne (ordre de grandeur).
# - multiplicateurs : pénalités/coeffs géométriques par architecture.
#
# IMPORTANT : on ne change pas l'API des fonctions, seulement l'implémentation interne.
pas_cylindre_m = 0.15
largeur_base_m = 0.40

# Multiplicateurs "package" (L_pkg, W_pkg) et facteurs d'ingénierie
_MODELES = {
    "L": {  # en ligne
        "banques": 1,
        "L_mult": 1.00,  # L = N * pas
        "W_mult": 1.00,  # W = base
        "complexite": 1.00,
        "serviceabilite": 1.00,
        "contraintes_nb": "tous",  # tous N possibles
    },
    "V": {  # en V (2 bancs)
        "banques": 2,
        "L_mult": 0.50,  # L = (N/2)*pas
        "W_mult": 1.50,
        "complexite": 1.30,
        "serviceabilite": 0.80,
        "contraintes_nb": "pair",  # N pair
    },
    "W": {  # en W (3 bancs simplifié)
        "banques": 3,
        "L_mult": 1.0 / 3.0,  # L = (N/3)*pas
        "W_mult": 2.00,
        "complexite": 1.80,
        "serviceabilite": 0.60,
        "contraintes_nb": "multiple_3_ou_4",  # logique historique conservée
    },
    "Etoile": {  # radial
        "banques": "radial",
        "L_mult": 1.50,  # court
        "W_mult": 2.50,  # large
        "complexite": 2.00,
        "serviceabilite": 0.90,
        "contraintes_nb": "tous",
    },
}


def _architecture_possible(type_arch: str, nb_cylindres: int) -> bool:
    """Contraintes simples sur le nombre de cylindres par architecture (cohérentes avec ton code)."""
    if type_arch not in _MODELES:
        return False

    if type_arch == "V":
        return (nb_cylindres % 2) == 0

    if type_arch == "W":
        # Conservation de ta logique d'origine :
        # - autoriser si divisible par 3 ou 4, et nb_cylindres >= 3
        if nb_cylindres < 3:
            return False
        return (nb_cylindres % 3 == 0) or (nb_cylindres % 4 == 0)

    return True


def evaluer_architecture(
    type_arch: str,
    nb_cylindres: int,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    cout_maintenance_estime: float = 0.0
) -> Tuple[float, bool]:
    """
    Évalue une architecture ("L", "V", "W", "Etoile") selon :
    - l'encombrement (longueur/largeur packagées),
    - la complexité (carters, alignement, distribution),
    - la maintenabilité (accessibilité, pénalisation du coût de maintenance).

    Retour :
        (score, est_valide)

    IMPORTANT compatibilité :
    - Même signature, même type de retour (tuple[float, bool]).
    - Même logique globale : pénalité forte si hors gabarit, score plus faible = meilleur.
    """
    nb = _exiger_int_positif("nb_cylindres", nb_cylindres, strict=True)
    L_max = _exiger_positif("longueur_dispo_m", longueur_dispo_m, strict=True)
    W_max = _exiger_positif("largeur_dispo_m", largeur_dispo_m, strict=True)
    cout_maint = _exiger_positif("cout_maintenance_estime", cout_maintenance_estime, strict=False)

    # Rejet propre si architecture inconnue ou impossible (au lieu de calculer n'importe quoi)
    if (type_arch not in _MODELES) or (not _architecture_possible(type_arch, nb)):
        return 9999.0, False

    modele = _MODELES[type_arch]

    # ---------------------------
    # 1) Estimation encombrement
    # ---------------------------
    # Hypothèse : longueur ~ pas_cylindre * nb_cylindres * multiplicateur
    # (pour V et W, multiplicateur reflète le nombre de bancs)
    if type_arch == "Etoile":
        # Radial : longueur faible quasi indépendante de N (carter + accessoires)
        # On conserve ton ordre de grandeur (pas*1.5), mais en l'expliquant.
        L_pkg = pas_cylindre_m * modele["L_mult"]
    else:
        L_pkg = (nb * pas_cylindre_m) * float(modele["L_mult"])

    # Largeur : base * multiplicateur
    W_pkg = largeur_base_m * float(modele["W_mult"])

    # ---------------------------
    # 2) Validité packaging
    # ---------------------------
    valide = (L_pkg <= L_max) and (W_pkg <= W_max)

    # ---------------------------
    # 3) Score maintenance normalisé
    # ---------------------------
    # Ici on retire une "inconnue" importante de ton code : la normalisation €/score.
    # On explicite un "échelle" qui convertit un coût € en points :
    #   score_maint = (cout / echelle_eur_par_point) / serviceabilite
    #
    # Si tu sais ton CAPEX / OPEX, tu peux choisir une échelle réaliste.
    # Par défaut, on garde ton 1000€ -> 1 point.
    echelle_eur_par_point = 1000.0

    serviceabilite = float(modele["serviceabilite"])
    if serviceabilite <= 0.0:
        # sécurité : éviter division par zéro si modèle mal paramétré
        serviceabilite = 0.1

    score_maintenance = (cout_maint / echelle_eur_par_point) / serviceabilite

    # ---------------------------
    # 4) Score dimensionnel + complexité
    # ---------------------------
    # On normalise proprement par les dimensions dispo (évite l'effet d'échelle).
    # Longueur relative = L_pkg/L_max, largeur relative = W_pkg/W_max
    score_encombrement = (L_pkg / L_max) + (W_pkg / W_max)

    complexite = float(modele["complexite"])
    # Pondération : proche de ton code (0.5)
    score_complexite = 0.5 * complexite

    # Score total
    score = score_encombrement + score_complexite + score_maintenance

    # Pénalité très forte si non valide (comportement conservé)
    if not valide:
        score += 1000.0

    return score, valide


def choix_architecture_optimale(
    nb_cylindres: int,
    L_max: float,
    W_max: float,
    cout_maintenance_estime: float = 0.0
) -> str:
    """
    Sélectionne la meilleure architecture pour un nombre de cylindres donné.

    Compatibilité :
    - Même signature et retour (str).
    - On conserve les options et la logique de filtrage (pair pour V, contraintes pour W).

    Stratégie :
    - Évalue chaque option possible,
    - ne retient que les architectures valides (qui rentrent dans L_max/W_max),
    - choisit le score minimal.
    """
    nb = _exiger_int_positif("nb_cylindres", nb_cylindres, strict=True)
    _exiger_positif("L_max", L_max, strict=True)
    _exiger_positif("W_max", W_max, strict=True)
    _exiger_positif("cout_maintenance_estime", cout_maintenance_estime, strict=False)

    options = ["L", "V", "W", "Etoile"]

    # Filtrage cohérent avec tes contraintes (mais centralisé)
    options = [a for a in options if _architecture_possible(a, nb)]

    best_arch = "Inconnue"
    best_score = 99999.0

    for arch in options:
        score, valide = evaluer_architecture(
            arch, nb, L_max, W_max, cout_maintenance_estime
        )
        if valide and score < best_score:
            best_score = score
            best_arch = arch

    return best_arch
