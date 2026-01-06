# backend\modules\architecture\resolution_globale_architecture.py
from __future__ import annotations

import math
import os
import sys
from typing import Any


# =============================================================================
# Imports robustes (sans casser l'opérabilité)
# - On essaye d'importer "normalement" (usage en package).
# - Si ça échoue, on ajoute le dossier racine du projet au sys.path, puis on ré-essaye.
# =============================================================================
try:
    from backend.modules.architecture.calcul_cylindree_totale import calcul_cylindree_totale_requise
    from backend.modules.architecture.calcul_cylindree_admissible import (
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )
    from backend.modules.architecture.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min
    from backend.modules.architecture.choix_architecture_optimale import (
        choix_architecture_optimale,
        evaluer_architecture,
    )
    from backend.modules.architecture.calcul_cout_maintenance_archard import calcul_cout_maintenance_estime
except ImportError:
    # Fallback : compatible exécution directe (script) depuis divers emplacements
    here = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(here, "../../.."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from backend.modules.architecture.calcul_cylindree_totale import calcul_cylindree_totale_requise
    from backend.modules.architecture.calcul_cylindree_admissible import (
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )
    from backend.modules.architecture.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min
    from backend.modules.architecture.choix_architecture_optimale import (
        choix_architecture_optimale,
        evaluer_architecture,
    )
    from backend.modules.architecture.calcul_cout_maintenance_archard import calcul_cout_maintenance_estime


# =============================================================================
# Paramètres "modèle" (hypothèses explicites = moins d'inconnues)
# =============================================================================

# Hypothèse cycle : 4-temps => fréquence cycles f = n/120 (n en tr/min)
_TEMPS_MOTEUR = 4

# Rendement mécanique (si PME n'est pas déjà "net vilebrequin")
_ETA_MECANIQUE = 0.85

# Ratio course/alésage maximal géométrique autorisé (limite architecture)
_RATIO_S_B_MAX = 1.2

# Hypothèses maintenance (cohérentes avec ton modèle Archard simplifié)
_DUREE_VIE_JOINT_BASE_H = 5000.0
_JOINTS_PAR_CYL = 3               # segments + étanchéité (hypothèse)
_COUT_INTERVENTION_BASE_EUR = 2000.0

# Exploration N
_N_MAX_ABSOLU = 24                # garde-fou (comme ton warning)
_DELTA_EXPLORATION = 6            # explore N_min .. N_min+6 (au lieu de +4)
_MIN_EXPLORATION = 16             # conserve ton intention : tester quelques architectures usuelles

# Verbosité (pour ne pas polluer les appels module)
# - Par défaut: on affiche (comme ton code).
# - Pour désactiver: définir SHSEM_VERBOSE=0 dans l'environnement.
_VERBOSE = os.environ.get("SHSEM_VERBOSE", "1").strip() not in ("0", "false", "False", "")


# =============================================================================
# Utilitaires robustesse
# =============================================================================

def _est_fini(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: float) -> float:
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def _log(msg: str) -> None:
    if _VERBOSE:
        print(msg)


def _hz_cycles(regime_tr_min: float, temps_moteur: int = _TEMPS_MOTEUR) -> float:
    """
    Convertit un régime (tr/min) en fréquence de cycles (Hz = cycles/s).

    - 4T : 1 cycle toutes les 2 révolutions => f = n/120
    - 2T : 1 cycle par révolution          => f = n/60
    """
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=True)
    if temps_moteur == 4:
        return n / 120.0
    if temps_moteur == 2:
        return n / 60.0
    raise ValueError("temps_moteur doit être 2 ou 4.")


def _course_max_depuis_vitesse_piston(vitesse_piston_max_ms: float, regime_tr_min: float) -> float:
    """
    Vitesse moyenne piston : U_p = 2*S*(n/60) => S_max = 30*U_p_max/n
    """
    U = _exiger_positif("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=True)
    return (30.0 * U) / n


def _bore_et_course_depuis_volume_et_ratio(
    volume_unitaire_m3: float,
    ratio_s_b: float
) -> tuple[float, float]:
    """
    Déduction exacte (retire une inconnue) :
      V = (pi/4) * B^2 * S
      avec S = ratio * B
      => V = (pi/4) * ratio * B^3
      => B = (4V/(pi*ratio))^(1/3)
      => S = ratio * B
    """
    V = _exiger_positif("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    r = _exiger_positif("ratio_s_b", ratio_s_b, strict=True)

    if V == 0.0:
        return 0.0, 0.0

    B = ((4.0 * V) / (math.pi * r)) ** (1.0 / 3.0)
    S = r * B
    return B, S


def _ratio_max_compatible_vitesse_piston(volume_unitaire_m3: float, course_max_m: float) -> float:
    """
    On veut choisir le ratio S/B le PLUS GRAND possible (=> bore plus petit, moins de surface,
    donc souvent moins de charge), MAIS sans dépasser la course max imposée par U_p_max.

    Avec V = (pi/4)*r*B^3, on obtient :
      B = (4V/(pi r))^(1/3)
      S = r*B = r*(4V/(pi r))^(1/3) = r^(2/3) * (4V/pi)^(1/3)

    Contrainte S <= S_max :
      r^(2/3) <= S_max / K   avec K = (4V/pi)^(1/3)
      r <= (S_max / K)^(3/2)

    Retour : r_lim (peut être très grand si V très petit).
    """
    V = _exiger_positif("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    S_max = _exiger_positif("course_max_m", course_max_m, strict=False)

    if V == 0.0:
        return float("inf")  # aucun volume => aucune contrainte

    K = (4.0 * V / math.pi) ** (1.0 / 3.0)
    if K <= 0.0:
        return 0.0

    ratio_lim = (S_max / K) ** (1.5)
    return ratio_lim


# =============================================================================
# Résolution globale (API conservée : même signature, retour dict)
# =============================================================================

def resoudre_architecture_globale(
    puissance_cible_w: float,
    regime_tr_min: float,
    pme_pa: float,
    vitesse_piston_max_ms: float,
    L_max_m: float,
    W_max_m: float,
    horizon_usage_h: float = 20000.0
) -> dict:
    """
    Résout une optimisation globale :
    - calcule la cylindrée totale requise (via PME, fréquence cycles, rendement),
    - calcule la cylindrée unitaire max admissible (via vitesse piston + ratio S/B max),
    - en déduit un N_min,
    - explore N autour de N_min et choisit l'architecture minimisant :
        score packaging + complexité + maintenance (déjà encapsulé dans evaluer_architecture).

    IMPORTANT compatibilité :
    - Ne change pas le type de retour : dict.
    - Ne change pas les clés existantes dans best_config (on conserve celles que tu posais).
    - Réduit les "inconnues" : alésage/courses sont déduits mathématiquement avec un ratio
      choisi automatiquement sous contraintes (au lieu du ratio arbitraire 1.0).
    """
    P = _exiger_positif("puissance_cible_w", puissance_cible_w, strict=False)
    n_rpm = _exiger_positif("regime_tr_min", regime_tr_min, strict=True)
    PME = _exiger_positif("pme_pa", pme_pa, strict=True)
    Up_max = _exiger_positif("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    _exiger_positif("L_max_m", L_max_m, strict=True)
    _exiger_positif("W_max_m", W_max_m, strict=True)
    T_usage = _exiger_positif("horizon_usage_h", horizon_usage_h, strict=False)

    _log("=== RÉSOLUTION GLOBALE ARCHITECTURE SHSE-M ===")

    # 1) Fréquence cycles (4T par défaut)
    freq_hz = _hz_cycles(n_rpm, _TEMPS_MOTEUR)

    # 2) Cylindrée totale requise
    #    V_tot = P_b / (eta_m * PME * f)
    cyl_tot_m3 = calcul_cylindree_totale_requise(
        puissance_mecanique_h=P,
        pme_pa=PME,
        frequence_cycles_hz=freq_hz,
        rendement_mecanique=_ETA_MECANIQUE,
    )
    _log(f"Cylindrée Totale Requise: {cyl_tot_m3 * 1e6:.1f} cc")

    # Si P=0 => V_tot=0. On retourne vide (comportement simple, évite des divisions).
    if cyl_tot_m3 <= 0.0:
        _log("Puissance cible nulle ou cylindrée totale nulle -> aucune solution à optimiser.")
        return {}

    # 3) Bornes unitaires admissibles (vitesse piston + ratio S/B max)
    bore_max_m = calcul_bore_max_admissible(Up_max, n_rpm, _RATIO_S_B_MAX)
    cyl_unit_max_m3 = calcul_cylindree_unit_max(bore_max_m, _RATIO_S_B_MAX)
    _log(
        f"Cylindrée Unitaire Max: {cyl_unit_max_m3 * 1e6:.1f} cc "
        f"(Alésage max {bore_max_m * 1000:.1f} mm, S/B max {_RATIO_S_B_MAX:.2f})"
    )

    # 4) N minimal
    n_min = calcul_nombre_cylindres_min(cyl_tot_m3, cyl_unit_max_m3)

    # Si le module renvoie sa sentinelle (999), on sort proprement
    if n_min >= 999:
        _log("ATTENTION: cylindrée unitaire max invalide -> N_min sentinelle. Paramètres incohérents.")
        return {}

    if n_min > _N_MAX_ABSOLU:
        _log(f"ATTENTION: N_min > {_N_MAX_ABSOLU}. Paramètres probablement irréalistes.")
        return {}

    _log(f"Nombre Cylindres Min (Physique): {n_min}")

    # 5) Pré-calculs : course max imposée par Up_max (utile pour retirer l'inconnue sur S/B réel)
    course_max_m = _course_max_depuis_vitesse_piston(Up_max, n_rpm)

    # 6) Exploration globale
    n_max_explore = max(_MIN_EXPLORATION, n_min + _DELTA_EXPLORATION)
    n_max_explore = min(_N_MAX_ABSOLU, n_max_explore)

    best_global_score = float("inf")
    best_config: dict[str, Any] = {}

    # Référence maintenance : on garde ta logique "référence = N_min"
    v_u_ref = cyl_tot_m3 / n_min

    # Choix du ratio de référence :
    # - On prend le plus grand ratio possible sous contraintes (=> bore plus petit),
    #   limité par la géométrie _RATIO_S_B_MAX.
    ratio_lim_ref = _ratio_max_compatible_vitesse_piston(v_u_ref, course_max_m)
    ratio_ref = min(_RATIO_S_B_MAX, ratio_lim_ref) if math.isfinite(ratio_lim_ref) else _RATIO_S_B_MAX
    # garde-fou
    ratio_ref = max(1e-6, ratio_ref)

    bore_ref, course_ref = _bore_et_course_depuis_volume_et_ratio(v_u_ref, ratio_ref)
    surface_ref = math.pi * (bore_ref ** 2) / 4.0
    charge_ref_n = PME * surface_ref

    for n_cyl in range(n_min, n_max_explore + 1):
        v_u = cyl_tot_m3 / n_cyl

        # Ratio "réel" déduit (plus d'arbitraire ratio=1.0) :
        # - ratio <= _RATIO_S_B_MAX (contrainte géométrique)
        # - ratio <= ratio_lim (contrainte vitesse piston => course <= course_max)
        ratio_lim = _ratio_max_compatible_vitesse_piston(v_u, course_max_m)
        ratio_retenu = min(_RATIO_S_B_MAX, ratio_lim) if math.isfinite(ratio_lim) else _RATIO_S_B_MAX
        ratio_retenu = max(1e-6, ratio_retenu)

        bore_actuel, course_actuelle = _bore_et_course_depuis_volume_et_ratio(v_u, ratio_retenu)

        # Contraintes physiques vérifiées explicitement (fiabilité)
        # - bore ne doit pas dépasser bore_max issu de Up_max + ratio max
        # - course ne doit pas dépasser course_max (sinon Up dépasserait)
        if bore_actuel > bore_max_m + 1e-12 or course_actuelle > course_max_m + 1e-12:
            # Cette config n respecte pas les limites, on ignore.
            continue

        surface_piston = math.pi * (bore_actuel ** 2) / 4.0

        # Charge moyenne (approx) : F_moy ~ PME * A
        charge_moy_n = PME * surface_piston

        # Coût maintenance (modèle existant)
        cout_maint = calcul_cout_maintenance_estime(
            duree_usage_h=T_usage,
            duree_vie_joint_base_h=_DUREE_VIE_JOINT_BASE_H,
            charge_nominale_n=charge_ref_n,
            charge_actuelle_n=charge_moy_n,
            nb_joints_base=n_min * _JOINTS_PAR_CYL,
            nb_joints_actuel=n_cyl * _JOINTS_PAR_CYL,
            cout_inter_eur=_COUT_INTERVENTION_BASE_EUR,
        )

        # Choix architecture (module existant)
        best_arch_for_n = choix_architecture_optimale(n_cyl, L_max_m, W_max_m, cout_maint)

        if best_arch_for_n == "Inconnue":
            continue

        score, valide = evaluer_architecture(best_arch_for_n, n_cyl, L_max_m, W_max_m, cout_maint)
        if not valide:
            continue

        _log(
            f"N={n_cyl:>2} -> Arch={best_arch_for_n:<6} | "
            f"Maint={cout_maint:>8.0f} € | Score={score:>7.2f} | "
            f"Bore={bore_actuel*1000:>6.1f} mm | Course={course_actuelle*1000:>6.1f} mm | S/B={ratio_retenu:>4.2f}"
        )

        if score < best_global_score:
            best_global_score = score
            best_config = {
                # Clés conservées (comme ton code)
                "N_cyl": n_cyl,
                "Architecture": best_arch_for_n,
                "Score": float(score),
                "Cout_Maint_Estime": float(cout_maint),
                "Bore_mm": float(bore_actuel * 1000.0),
                "RPM": float(n_rpm),
                "PME": float(PME),

                # Infos supplémentaires utiles (ajout non cassant)
                "Course_mm": float(course_actuelle * 1000.0),
                "Ratio_Sur_B": float(ratio_retenu),
                "Cylindree_tot_cc": float(cyl_tot_m3 * 1e6),
                "Cylindree_unit_cc": float(v_u * 1e6),
                "Up_max_ms": float(Up_max),
            }

    _log("\n=== RÉSULTAT OPTIMAL ===")
    _log(str(best_config))

    return best_config


if __name__ == "__main__":
    # Test nominal SHSE-M 150kW
    resoudre_architecture_globale(
        puissance_cible_w=150000.0,
        regime_tr_min=4500.0,
        pme_pa=12e5,  # 12 bar PME
        vitesse_piston_max_ms=25.0,
        L_max_m=1.2,
        W_max_m=0.8,
    )
