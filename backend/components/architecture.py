# backend/components/architecture.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple
import math


# ============================================================
# Types / profils d'usage
# ============================================================

UsageType = Literal["voiture", "moto", "bateau", "avion", "stationnaire", "autre"]
ArchitectureType = Literal["L", "V", "W", "Etoile", "Boxer"]


@dataclass(frozen=True)
class ProfilUsageMoteur:
    """
    Profil d'usage : aucune donnée cachée.

    Deux modes :
    - mode simple historique : pré-sélection rapide sur PME + vitesse piston + gabarit ;
    - mode fin multi-cas : activé si cas_de_charge et taux_compression sont fournis.
    """
    usage: UsageType
    longueur_dispo_m: float
    largeur_dispo_m: float
    hauteur_dispo_m: Optional[float] = None
    horizon_usage_h: float = 20000.0
    vitesse_piston_max_ms: Optional[float] = None
    taux_compression: Optional[float] = None

    # cas de charge explicites (mode fin)
    cas_de_charge: Optional[Tuple[Any, ...]] = None
    ordre_allumage_map: Optional[Mapping[int, Sequence[int] | str]] = None
    ponderations_cas: Optional[Mapping[str, float]] = None

    # pondérations explicites
    poids_maintenance: float = 1.0
    poids_masse: float = 1.0
    poids_cout_matiere: float = 1.0
    poids_compacite: float = 1.0
    poids_fiabilite: float = 1.0
    poids_rendement: float = 1.0

    # contraintes / préférences
    architectures_autorisees: Optional[Tuple[ArchitectureType, ...]] = None
    architecture_forcee: Optional[ArchitectureType] = None

    commentaire: str = ""


def estimer_pme_depuis_couple_et_cylindree(
    couple_nm: float,
    cylindree_totale_m3: float,
    *,
    temps_moteur: int = 4,
) -> float:
    """
    Estime la PME (BMEP) à partir du couple et de la cylindrée totale.

      - 4T : BMEP = 4π T / Vd
      - 2T : BMEP = 2π T / Vd
    """
    T = _require_finite("couple_nm", couple_nm)
    Vd = _require_positive("cylindree_totale_m3", cylindree_totale_m3, strict=True)
    if temps_moteur == 4:
        return float((4.0 * math.pi * T) / Vd)
    if temps_moteur == 2:
        return float((2.0 * math.pi * T) / Vd)
    raise ValueError("temps_moteur doit être 2 ou 4.")


def estimer_pme_depuis_puissance_et_cylindree(
    puissance_mecanique_w: float,
    cylindree_totale_m3: float,
    regime_tr_min: float,
    *,
    temps_moteur: int = 4,
    rendement_mecanique: float = 1.0,
) -> float:
    """
    Estime la PME (BMEP) à partir de P, Vd, régime et rendement.

      PME = P / (Vd * f * eta_m)
    """
    P = _require_positive("puissance_mecanique_w", puissance_mecanique_w, strict=False)
    Vd = _require_positive("cylindree_totale_m3", cylindree_totale_m3, strict=True)
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    eta = _require_positive("rendement_mecanique", rendement_mecanique, strict=True)

    if temps_moteur == 4:
        f = n / 120.0
    elif temps_moteur == 2:
        f = n / 60.0
    else:
        raise ValueError("temps_moteur doit être 2 ou 4.")

    if Vd * f * eta <= 0.0:
        return 0.0
    return float(P / (Vd * f * eta))


# ============================================================
# Imports des modules architecture (robustes)
# ============================================================

try:
    from backend.modules.architecture.calcul_cout_maintenance_archard import (
        calcul_cout_maintenance_estime,
        calcul_cout_maintenance_estime_auto_prix,
    )
except Exception:
    from backend.modules.architecture.calcul_cout_maintenance_archard import (  # type: ignore
        calcul_cout_maintenance_estime,
        calcul_cout_maintenance_estime_auto_prix,
    )

try:
    from backend.modules.architecture.calcul_cylindree_admissible import (
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )
except Exception:
    from backend.modules.architecture.calcul_cylindree_admissible import (  # type: ignore
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )

try:
    from backend.modules.architecture.calcul_cylindree_totale import (
        calcul_cylindree_totale_requise,
    )
except Exception:
    from backend.modules.architecture.calcul_cylindree_totale import (  # type: ignore
        calcul_cylindree_totale_requise,
    )

try:
    from backend.modules.architecture.calcul_nombre_cylindres_min import (
        calcul_nombre_cylindres_min,
    )
except Exception:
    from backend.modules.architecture.calcul_nombre_cylindres_min import (  # type: ignore
        calcul_nombre_cylindres_min,
    )

try:
    from backend.modules.architecture.choix_architecture_optimale import (
        choix_architecture_optimale,
        evaluer_architecture,
    )
except Exception:
    from backend.modules.architecture.choix_architecture_optimale import (  # type: ignore
        choix_architecture_optimale,
        evaluer_architecture,
    )

try:
    from backend.modules.architecture.resolution_globale_architecture import (
        resoudre_architecture_globale,
    )
except Exception:
    from backend.modules.architecture.resolution_globale_architecture import (  # type: ignore
        resoudre_architecture_globale,
    )

# Solveur fin multi-cas
try:
    from backend.modules.architecture.architecture_fine_multicas import (
        resoudre_architecture_fine_multicas,
        ParametresPackagingArchitecture,
        ParametresMasseArchitecture,
        ParametresPertesArchitecture,
        ParametresFiabiliteArchitecture,
        ParametresScoreArchitecture,
        OptionsExplorationArchitecture,
    )
except Exception:
    try:
        from backend.modules.architecture.architecture_fine_multicas import (  # type: ignore
            resoudre_architecture_fine_multicas,
            ParametresPackagingArchitecture,
            ParametresMasseArchitecture,
            ParametresPertesArchitecture,
            ParametresFiabiliteArchitecture,
            ParametresScoreArchitecture,
            OptionsExplorationArchitecture,
        )
    except Exception:
        resoudre_architecture_fine_multicas = None  # type: ignore
        ParametresPackagingArchitecture = None  # type: ignore
        ParametresMasseArchitecture = None  # type: ignore
        ParametresPertesArchitecture = None  # type: ignore
        ParametresFiabiliteArchitecture = None  # type: ignore
        ParametresScoreArchitecture = None  # type: ignore
        OptionsExplorationArchitecture = None  # type: ignore


# ============================================================
# Helpers robustesse + gestion des inconnues
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strict: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


def _require_int_positive(name: str, x: Any, *, strict: bool = True) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    ok = x > 0 if strict else x >= 0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return int(x)


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[dict]) -> List[dict]:
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


def _hz_cycles(regime_tr_min: float, temps_moteur: int) -> float:
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    if temps_moteur == 4:
        return n / 120.0
    if temps_moteur == 2:
        return n / 60.0
    raise ValueError("temps_moteur doit être 2 ou 4.")


def _course_max_depuis_vitesse_piston(vitesse_piston_max_ms: float, regime_tr_min: float) -> float:
    U = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    if n == 0.0:
        return 0.0
    return (30.0 * U) / n


def _bore_et_course_depuis_volume_et_ratio(volume_unitaire_m3: float, ratio_s_b: float) -> Tuple[float, float]:
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    r = _require_positive("ratio_s_b", ratio_s_b, strict=True)
    if V == 0.0:
        return 0.0, 0.0
    B = ((4.0 * V) / (math.pi * r)) ** (1.0 / 3.0)
    S = r * B
    return float(B), float(S)


def _ratio_max_compatible_vitesse_piston(volume_unitaire_m3: float, course_max_m: float) -> float:
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    S_max = _require_positive("course_max_m", course_max_m, strict=False)
    if V == 0.0:
        return float("inf")
    K = (4.0 * V / math.pi) ** (1.0 / 3.0)
    if K <= 0.0:
        return 0.0
    return float((S_max / K) ** 1.5)


def _surface_piston_m2(bore_m: float) -> float:
    B = _require_positive("bore_m", bore_m, strict=False)
    if B == 0.0:
        return 0.0
    return float(math.pi * (B**2) / 4.0)


def _estimer_packaging_simple(
    architecture: str,
    nb_cyl: int,
    *,
    pas_cylindre_m: float,
    largeur_base_m: float,
) -> Tuple[float, float]:
    nb = _require_int_positive("nb_cyl", nb_cyl, strict=True)
    pas = _require_positive("pas_cylindre_m", pas_cylindre_m, strict=True)
    w0 = _require_positive("largeur_base_m", largeur_base_m, strict=True)

    arch = str(architecture)
    if arch == "L":
        return nb * pas, w0
    if arch == "V":
        return (nb / 2.0) * pas, 1.5 * w0
    if arch == "W":
        return (nb / 3.0) * pas, 2.0 * w0
    if arch == "Etoile":
        return 1.5 * pas, 2.5 * w0
    if arch == "Boxer":
        return (nb / 2.0) * pas, 2.1 * w0
    return float("nan"), float("nan")


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    if not _is_finite(a) or not _is_finite(b):
        return None
    if float(b) == 0.0:
        return None
    return float(a) / float(b)


def _architecture_complexity_factor(arch: str) -> float:
    mapping = {
        "L": 1.00,
        "V": 1.10,
        "W": 1.25,
        "Etoile": 1.35,
        "Boxer": 1.08,
    }
    return float(mapping.get(str(arch), 1.50))


def _appeler_choix_architecture_optimale(
    nb_cyl: int,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    cout_maintenance_score: Optional[float],
) -> str:
    last_err: Optional[Exception] = None
    essais = [
        (nb_cyl, longueur_dispo_m, largeur_dispo_m, cout_maintenance_score),
        (nb_cyl, longueur_dispo_m, largeur_dispo_m),
    ]
    for args in essais:
        try:
            return str(choix_architecture_optimale(*args))
        except TypeError as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return "Inconnue"


def _appeler_evaluer_architecture(
    arch: str,
    nb_cyl: int,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    cout_maintenance_score: Optional[float],
) -> Tuple[float, bool]:
    last_err: Optional[Exception] = None
    essais = [
        (arch, nb_cyl, longueur_dispo_m, largeur_dispo_m, cout_maintenance_score),
        (arch, nb_cyl, longueur_dispo_m, largeur_dispo_m),
    ]
    for args in essais:
        try:
            out = evaluer_architecture(*args)
            if isinstance(out, tuple) and len(out) >= 2:
                return float(out[0]), bool(out[1])
            if isinstance(out, (int, float)):
                return float(out), True
        except TypeError as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return float("inf"), False


def _estimer_indice_maintenance(*, nb_cyl: int, architecture: str) -> float:
    return float(nb_cyl) * _architecture_complexity_factor(architecture)


def _estimer_masse_relative(*, nb_cyl: int, bore_m: float, course_m: float, architecture: str) -> float:
    volume_geom = float(nb_cyl) * max(0.0, float(bore_m)) ** 2 * max(0.0, float(course_m))
    f_arch = _architecture_complexity_factor(architecture)
    return float(volume_geom * f_arch)


def _estimer_cout_matiere_relatif(*, masse_relative: float, architecture: str) -> float:
    return float(masse_relative * _architecture_complexity_factor(architecture))


def _estimer_indice_fiabilite(
    *,
    nb_cyl: int,
    architecture: str,
    ratio_s_b: float,
    charge_moy_piston_n: float,
    charge_ref_n: float,
) -> float:
    charge_ratio = _safe_div(charge_moy_piston_n, charge_ref_n)
    charge_ratio = 1.0 if charge_ratio is None else max(0.0, charge_ratio)
    return float(
        _architecture_complexity_factor(architecture)
        * (1.0 + 0.10 * max(0.0, nb_cyl - 1))
        * (1.0 + 0.25 * max(0.0, ratio_s_b - 1.0))
        * charge_ratio
    )


def _estimer_indice_rendement_relatif(*, nb_cyl: int, architecture: str, ratio_s_b: float) -> float:
    return float(
        1.0
        + 0.06 * max(0.0, nb_cyl - 1)
        + 0.15 * max(0.0, ratio_s_b - 1.0)
        + 0.10 * (_architecture_complexity_factor(architecture) - 1.0)
    )


def _normaliser_sur_candidats(lignes: List[Dict[str, Any]], champ: str, *, sens: str = "min") -> None:
    valeurs: List[float] = []
    for row in lignes:
        v = row.get(champ)
        if _is_finite(v):
            valeurs.append(float(v))
    if not valeurs:
        for row in lignes:
            row[f"{champ}_norm"] = None
        return

    vmin = min(valeurs)
    vmax = max(valeurs)
    if abs(vmax - vmin) <= 1e-15:
        for row in lignes:
            row[f"{champ}_norm"] = 0.0
        return

    for row in lignes:
        v = row.get(champ)
        if not _is_finite(v):
            row[f"{champ}_norm"] = None
            continue
        x = (float(v) - vmin) / (vmax - vmin)
        if sens == "max":
            x = 1.0 - x
        row[f"{champ}_norm"] = float(max(0.0, min(1.0, x)))


def _score_multi_criteres(
    row: Dict[str, Any],
    *,
    poids_maintenance: float,
    poids_masse: float,
    poids_cout_matiere: float,
    poids_compacite: float,
    poids_fiabilite: float,
    poids_rendement: float,
) -> float:
    def g(name: str) -> float:
        v = row.get(name)
        if v is None or not _is_finite(v):
            return 1.0
        return float(v)

    score = 0.0
    score += float(poids_maintenance) * g("cout_maintenance_score_eur_norm")
    score += float(poids_masse) * g("masse_relative_norm")
    score += float(poids_cout_matiere) * g("cout_matiere_relatif_norm")
    score += float(poids_compacite) * g("compacite_score_norm")
    score += float(poids_fiabilite) * g("fiabilite_indice_norm")
    score += float(poids_rendement) * g("rendement_indice_norm")
    return float(score)


def _make_fine_options(
    base: Optional[Any],
    *,
    architectures_autorisees: Optional[List[ArchitectureType]],
    architecture_forcee: Optional[ArchitectureType],
    delta_exploration: int,
    n_max_absolu: int,
) -> Optional[Any]:
    if OptionsExplorationArchitecture is None:
        return None

    archs: Tuple[str, ...]
    if architecture_forcee is not None:
        archs = (str(architecture_forcee),)
    elif architectures_autorisees:
        archs = tuple(str(a) for a in architectures_autorisees)
    else:
        archs = getattr(base, "architectures", ("L", "V", "W", "Etoile", "Boxer")) if base is not None else (
            "L", "V", "W", "Etoile", "Boxer"
        )

    if base is not None:
        return replace(
            base,
            architectures=archs,
            delta_cylindres=int(delta_exploration),
            n_max_absolu=int(n_max_absolu),
        )

    return OptionsExplorationArchitecture(
        architectures=archs,
        delta_cylindres=int(delta_exploration),
        n_max_absolu=int(n_max_absolu),
    )


def _convertir_solution_fine_vers_rapport(
    solution: Dict[str, Any],
    rapport: Dict[str, Any],
    *,
    poids_maintenance: float,
    poids_masse: float,
    poids_cout_matiere: float,
    poids_compacite: float,
    poids_fiabilite: float,
    poids_rendement: float,
) -> Dict[str, Any]:
    hypo = solution.get("hypotheses", {})
    rapport["mode_analyse"] = "fine_multicas"
    rapport["solution_fine_multicas"] = solution
    rapport["cylindree"]["cylindree_totale_m3"] = hypo.get("cylindree_totale_requise_m3")
    rapport["cylindree"]["cylindree_totale_cc"] = hypo.get("cylindree_totale_requise_cm3")
    rapport["cylindree"]["N_min"] = hypo.get("n_min")
    rapport["contraintes_admissibles"]["course_max_m"] = hypo.get("course_max_m")
    rapport["contraintes_admissibles"]["rpm_max_considere"] = hypo.get("rpm_max_considere")

    candidats = solution.get("candidats_tries", []) or []
    converted: List[Dict[str, Any]] = []
    best_by_arch: Dict[str, Dict[str, Any]] = {}

    for cand in candidats:
        gabarit = cand.get("gabarit", {}) or {}
        masse = cand.get("masse", {}) or {}
        perf = cand.get("performance_moyenne", {}) or {}
        fiab = cand.get("fiabilite_globale", {}) or {}
        maint = cand.get("maintenance", {}) or {}
        row = {
            "N_cyl": int(cand.get("nb_cylindres", 0)),
            "architecture": str(cand.get("architecture", "Inconnue")),
            "score_global": float(cand.get("score", float("inf"))),
            "score_multi_criteres": float(cand.get("score", float("inf"))),
            "score_module_externe": None,
            "valide": bool(cand.get("valide_packaging", False)),
            "cout_maintenance_eur": float(maint.get("cout_max_estime_eur", 0.0)),
            "cout_maintenance_score_eur": float(maint.get("cout_max_estime_eur", 0.0)),
            "maintenance_indice": float(maint.get("cout_max_estime_eur", 0.0)),
            "masse_relative": float(masse.get("masse_totale_estimee_kg", float("nan"))),
            "cout_matiere_relatif": float(masse.get("masse_totale_estimee_kg", float("nan"))),
            "fiabilite_indice": float(fiab.get("severite_dimensionnante", float("nan"))),
            "rendement_indice": 1.0 - float(perf.get("eta_globale_proxy_moyenne", 0.0)),
            "compacite_score": max(
                float(gabarit.get("longueur_m", 0.0)),
                float(gabarit.get("largeur_m", 0.0)),
                float(gabarit.get("hauteur_m", 0.0)),
            ),
            "cylindree_tot_cc": float(cand.get("cylindree_totale_cm3", 0.0)),
            "cylindree_unit_cc": float(cand.get("cylindree_unitaire_cm3", 0.0)),
            "bore_mm": float(cand.get("alesage_m", 0.0)) * 1000.0,
            "course_mm": float(cand.get("course_m", 0.0)) * 1000.0,
            "ratio_S_B": float(cand.get("ratio_course_alesage", float("nan"))),
            "charge_moy_piston_N": float(cand.get("pression_dimensionnante_pa", 0.0)) * _surface_piston_m2(float(cand.get("alesage_m", 0.0))),
            "L_pkg_m_estimee": float(gabarit.get("longueur_m", float("nan"))),
            "W_pkg_m_estimee": float(gabarit.get("largeur_m", float("nan"))),
            "H_pkg_m_estimee": float(gabarit.get("hauteur_m", float("nan"))),
            "masse_estimee_kg": float(masse.get("masse_totale_estimee_kg", float("nan"))),
            "eta_globale_proxy": float(perf.get("eta_globale_proxy_moyenne", float("nan"))),
            "cas_dimensionnant": fiab.get("cas_dimensionnant"),
            "organe_dimensionnant": fiab.get("organe_dimensionnant"),
            "pression_dimensionnante_pa": float(cand.get("pression_dimensionnante_pa", float("nan"))),
            "torque_max_global_nm": float(cand.get("torque_max_global_nm", float("nan"))),
            "details_fins": cand,
        }
        converted.append(row)
        arch = row["architecture"]
        if arch not in best_by_arch or float(row["score_global"]) < float(best_by_arch[arch]["score_global"]):
            best_by_arch[arch] = row

    rapport["exploration"] = converted
    rapport["meilleurs_par_architecture"] = best_by_arch

    best = solution.get("meilleur_candidat")
    if isinstance(best, dict):
        best_arch = str(best.get("architecture", ""))
        rapport["meilleur"] = best_by_arch.get(best_arch)

    rapport["criteres_conception"] = {
        "poids_maintenance": poids_maintenance,
        "poids_masse": poids_masse,
        "poids_cout_matiere": poids_cout_matiere,
        "poids_compacite": poids_compacite,
        "poids_fiabilite": poids_fiabilite,
        "poids_rendement": poids_rendement,
    }

    rapport["notes_modele"].append(
        "Mode fin multi-cas actif : la solution tient compte de cas de charge explicites, d'un cycle mécanique et d'indices de masse/rendement/fiabilité plus riches."
    )
    rapport["notes_modele"].append(
        "En mode fin, le poids 'coût matière' est replié sur la masse estimée faute de modèle industriel séparé dans le solveur multi-cas."
    )
    attention = hypo.get("attention")
    if attention:
        rapport["notes_modele"].append(str(attention))
    return rapport


# ============================================================
# Composant Architecture
# ============================================================

@dataclass(frozen=True)
class Architecture:
    """
    Analyse et pré-dimensionnement architecture moteur.

    Deux niveaux d'analyse :
    - simple historique : rapide, conservatif, compatible avec les appels existants ;
    - fin multi-cas : activé si cas_de_charge + taux_compression sont fournis.
    """

    # cycle moteur : 4T ou 2T
    temps_moteur: int = 4

    # rendement mécanique
    rendement_mecanique: float = 0.85

    # contrainte géométrique S/B max
    ratio_course_alesage_max: float = 1.2

    # maintenance (modèle joints)
    duree_vie_joint_base_h: float = 5000.0
    joints_par_cyl: int = 3
    cout_intervention_base_eur: float = 2000.0
    beta_wear_model: str = "1.5 (dans le module)"

    # exploration N
    delta_exploration: int = 6
    min_exploration: int = 16
    n_max_absolu: int = 24

    # packaging "informatif"
    pas_cylindre_m: float = 0.15
    largeur_base_m: float = 0.40

    # scraping optionnel
    activer_scraping_prix: bool = False
    urls_prix_joints: Optional[List[str]] = None
    urls_main_oeuvre: Optional[List[str]] = None
    cache_path_prix: str = "backend/.cache/prix_maintenance.json"
    cache_ttl_h: float = 168.0
    timeout_scraping_s: float = 6.0
    temps_intervention_h: float = 1.0
    cout_arret_eur: float = 0.0
    cout_consommables_eur: float = 0.0
    strict_scraping: bool = False

    # solveur fin (paramètres avancés optionnels)
    params_packaging_fins: Optional[Any] = None
    params_masse_fins: Optional[Any] = None
    params_pertes_fins: Optional[Any] = None
    params_fiabilite_fins: Optional[Any] = None
    options_fines: Optional[Any] = None

    # ------------------------------------------------------------
    # Wrapper : usage/profil -> appel analyser()
    # ------------------------------------------------------------
    def recommander_pour_profil(
        self,
        profil: ProfilUsageMoteur,
        *,
        puissance_cible_w: Optional[float] = None,
        regime_tr_min: Optional[float] = None,
        pme_pa: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not isinstance(profil, ProfilUsageMoteur):
            raise ValueError("profil doit être une instance de ProfilUsageMoteur.")
        return self.analyser(
            puissance_cible_w=puissance_cible_w,
            regime_tr_min=regime_tr_min,
            pme_pa=pme_pa,
            vitesse_piston_max_ms=profil.vitesse_piston_max_ms,
            longueur_dispo_m=profil.longueur_dispo_m,
            largeur_dispo_m=profil.largeur_dispo_m,
            hauteur_dispo_m=profil.hauteur_dispo_m,
            horizon_usage_h=profil.horizon_usage_h,
            taux_compression=profil.taux_compression,
            cas_de_charge=list(profil.cas_de_charge) if profil.cas_de_charge else None,
            ordre_allumage_map=dict(profil.ordre_allumage_map) if profil.ordre_allumage_map else None,
            ponderations_cas=dict(profil.ponderations_cas) if profil.ponderations_cas else None,
            architectures_autorisees=list(profil.architectures_autorisees) if profil.architectures_autorisees else None,
            architecture_forcee=profil.architecture_forcee,
            poids_maintenance=profil.poids_maintenance,
            poids_masse=profil.poids_masse,
            poids_cout_matiere=profil.poids_cout_matiere,
            poids_compacite=profil.poids_compacite,
            poids_fiabilite=profil.poids_fiabilite,
            poids_rendement=profil.poids_rendement,
            usage=profil.usage,
            commentaire_usage=profil.commentaire,
        )

    def analyser(
        self,
        *,
        puissance_cible_w: Optional[float] = None,
        regime_tr_min: Optional[float] = None,
        pme_pa: Optional[float] = None,
        vitesse_piston_max_ms: Optional[float] = None,
        longueur_dispo_m: Optional[float] = None,
        largeur_dispo_m: Optional[float] = None,
        hauteur_dispo_m: Optional[float] = None,
        horizon_usage_h: float = 20000.0,
        taux_compression: Optional[float] = None,
        cas_de_charge: Optional[List[Any]] = None,
        ordre_allumage_map: Optional[Mapping[int, Sequence[int] | str]] = None,
        ponderations_cas: Optional[Mapping[str, float]] = None,
        activer_mode_fine: bool = True,

        # contraintes / préférences architecture
        architectures_autorisees: Optional[List[ArchitectureType]] = None,
        architecture_forcee: Optional[ArchitectureType] = None,

        # pondérations explicites
        poids_maintenance: float = 1.0,
        poids_masse: float = 1.0,
        poids_cout_matiere: float = 1.0,
        poids_compacite: float = 1.0,
        poids_fiabilite: float = 1.0,
        poids_rendement: float = 1.0,

        # métadonnées
        usage: Optional[UsageType] = None,
        commentaire_usage: str = "",
    ) -> Dict[str, Any]:

        for nom, val in {
            "poids_maintenance": poids_maintenance,
            "poids_masse": poids_masse,
            "poids_cout_matiere": poids_cout_matiere,
            "poids_compacite": poids_compacite,
            "poids_fiabilite": poids_fiabilite,
            "poids_rendement": poids_rendement,
        }.items():
            if not _is_finite(val) or float(val) < 0.0:
                raise ValueError(f"{nom} doit être un nombre fini >= 0.")

        rapport: Dict[str, Any] = {
            "mode_analyse": "simple",
            "entrees": {},
            "cycles": {},
            "cylindree": {},
            "contraintes_admissibles": {},
            "maintenance": {},
            "criteres_conception": {},
            "exploration": [],
            "meilleur": None,
            "meilleurs_par_architecture": {},
            "solution_module_globale": None,
            "solution_fine_multicas": None,
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        rapport["entrees"] = {
            "usage": usage,
            "commentaire_usage": commentaire_usage,
            "puissance_cible_w": puissance_cible_w,
            "regime_tr_min": regime_tr_min,
            "pme_pa": pme_pa,
            "vitesse_piston_max_ms": vitesse_piston_max_ms,
            "longueur_dispo_m": longueur_dispo_m,
            "largeur_dispo_m": largeur_dispo_m,
            "hauteur_dispo_m": hauteur_dispo_m,
            "horizon_usage_h": horizon_usage_h,
            "temps_moteur": self.temps_moteur,
            "rendement_mecanique": self.rendement_mecanique,
            "ratio_course_alesage_max": self.ratio_course_alesage_max,
            "joints_par_cyl": self.joints_par_cyl,
            "duree_vie_joint_base_h": self.duree_vie_joint_base_h,
            "cout_intervention_base_eur": self.cout_intervention_base_eur,
            "architectures_autorisees": architectures_autorisees,
            "architecture_forcee": architecture_forcee,
            "taux_compression": taux_compression,
            "nb_cas_de_charge": len(cas_de_charge) if cas_de_charge else 0,
            "activer_mode_fine": bool(activer_mode_fine),
        }

        rapport["criteres_conception"] = {
            "poids_maintenance": poids_maintenance,
            "poids_masse": poids_masse,
            "poids_cout_matiere": poids_cout_matiere,
            "poids_compacite": poids_compacite,
            "poids_fiabilite": poids_fiabilite,
            "poids_rendement": poids_rendement,
        }

        if puissance_cible_w is None:
            _push_inconnue(rapport, "impossibles", "puissance_cible_w", "Nécessaire pour calculer la cylindrée totale requise.")
        if regime_tr_min is None:
            _push_inconnue(rapport, "impossibles", "regime_tr_min", "Nécessaire pour f(cycles/s), vitesse piston, et cylindrée.")
        if pme_pa is None:
            _push_inconnue(rapport, "impossibles", "pme_pa", "Nécessaire pour relier puissance et cylindrée (PME).")

        if longueur_dispo_m is None or largeur_dispo_m is None:
            _push_inconnue(rapport, "partielles", "gabarit (L/W)", "Nécessaire pour valider le packaging et choisir l'architecture optimale.")

        if vitesse_piston_max_ms is None:
            _push_inconnue(rapport, "partielles", "vitesse_piston_max_ms", "Nécessaire pour borner l'alésage et la cylindrée unitaire admissible.")

        if puissance_cible_w is None or regime_tr_min is None or pme_pa is None:
            _dedup_inconnues(rapport)
            return rapport

        # ------------------------------------------------------------
        # Mode fin multi-cas : privilégié si les entrées sont présentes
        # ------------------------------------------------------------
        if (
            bool(activer_mode_fine)
            and resoudre_architecture_fine_multicas is not None
            and cas_de_charge
            and taux_compression is not None
            and longueur_dispo_m is not None
            and largeur_dispo_m is not None
            and vitesse_piston_max_ms is not None
        ):
            try:
                options_fines = _make_fine_options(
                    self.options_fines,
                    architectures_autorisees=architectures_autorisees,
                    architecture_forcee=architecture_forcee,
                    delta_exploration=self.delta_exploration,
                    n_max_absolu=self.n_max_absolu,
                )

                poids_masse_fins = float(poids_masse) + 0.60 * float(poids_cout_matiere)
                params_score = self.params_packaging_fins  # dummy to keep linter silent pattern-free
                _ = params_score
                if ParametresScoreArchitecture is not None:
                    params_score = ParametresScoreArchitecture(
                        poids_masse=poids_masse_fins,
                        poids_rendement=float(poids_rendement),
                        poids_fiabilite=float(poids_fiabilite),
                        poids_packaging=float(poids_compacite),
                        poids_maintenance=float(poids_maintenance),
                    )
                else:
                    params_score = None

                solution_fine = resoudre_architecture_fine_multicas(
                    puissance_cible_w=_require_positive("puissance_cible_w", puissance_cible_w, strict=False),
                    regime_nominal_tr_min=_require_positive("regime_tr_min", regime_tr_min, strict=True),
                    pme_nominale_pa=_require_positive("pme_pa", pme_pa, strict=True),
                    vitesse_piston_max_ms=_require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False),
                    L_max_m=_require_positive("longueur_dispo_m", longueur_dispo_m, strict=True),
                    W_max_m=_require_positive("largeur_dispo_m", largeur_dispo_m, strict=True),
                    H_max_m=_require_positive("hauteur_dispo_m", hauteur_dispo_m, strict=True) if hauteur_dispo_m is not None else None,
                    taux_compression=_require_positive("taux_compression", taux_compression, strict=True),
                    cas_de_charge=cas_de_charge,
                    horizon_usage_h=_require_positive("horizon_usage_h", horizon_usage_h, strict=False),
                    ordre_allumage_map=ordre_allumage_map,
                    params_packaging=self.params_packaging_fins if self.params_packaging_fins is not None else ParametresPackagingArchitecture(),
                    params_masse=self.params_masse_fins if self.params_masse_fins is not None else ParametresMasseArchitecture(),
                    params_pertes=self.params_pertes_fins if self.params_pertes_fins is not None else ParametresPertesArchitecture(),
                    params_fiabilite=self.params_fiabilite_fins if self.params_fiabilite_fins is not None else ParametresFiabiliteArchitecture(),
                    params_score=params_score if params_score is not None else ParametresScoreArchitecture(),
                    options=options_fines if options_fines is not None else OptionsExplorationArchitecture(),
                    ponderations_cas=ponderations_cas,
                )

                rapport = _convertir_solution_fine_vers_rapport(
                    solution_fine,
                    rapport,
                    poids_maintenance=poids_maintenance,
                    poids_masse=poids_masse,
                    poids_cout_matiere=poids_cout_matiere,
                    poids_compacite=poids_compacite,
                    poids_fiabilite=poids_fiabilite,
                    poids_rendement=poids_rendement,
                )

                rapport["notes_modele"].append(
                    "Le solveur fin est utilisé car cas_de_charge et taux_compression ont été fournis."
                )
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "coût industriel réel",
                    "Le solveur fin estime masse, rendement et fiabilité, mais pas le coût industriel exact sans procédés, volumes et temps d'usinage.",
                )
                _dedup_inconnues(rapport)
                return rapport
            except Exception as exc:
                rapport["notes_modele"].append(
                    f"Mode fin indisponible ou échec solveur multi-cas ({exc}). Repli sur le mode simple historique."
                )

        else:
            if activer_mode_fine and cas_de_charge and taux_compression is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "taux_compression",
                    "Requis pour activer le solveur fin multi-cas avec les cas de charge fournis.",
                )
            elif activer_mode_fine and cas_de_charge and resoudre_architecture_fine_multicas is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "solveur fin multi-cas",
                    "Module architecture_fine_multicas introuvable ; analyse simple utilisée.",
                )

        # ------------------------------------------------------------
        # Mode simple historique
        # ------------------------------------------------------------
        P = _require_positive("puissance_cible_w", puissance_cible_w, strict=False)
        n_rpm = _require_positive("regime_tr_min", regime_tr_min, strict=True)
        PME = _require_positive("pme_pa", pme_pa, strict=True)
        T_usage = _require_positive("horizon_usage_h", horizon_usage_h, strict=False)

        f_hz = _hz_cycles(n_rpm, self.temps_moteur)
        rapport["cycles"] = {"temps_moteur": self.temps_moteur, "frequence_cycles_hz": f_hz}

        eta_m = _require_positive("rendement_mecanique", self.rendement_mecanique, strict=True)
        V_tot_m3 = float(calcul_cylindree_totale_requise(P, PME, f_hz, eta_m))
        rapport["cylindree"]["cylindree_totale_m3"] = V_tot_m3
        rapport["cylindree"]["cylindree_totale_cc"] = V_tot_m3 * 1e6

        if V_tot_m3 <= 0.0:
            rapport["notes_modele"].append("Puissance cible nulle => cylindrée totale nulle.")
            _dedup_inconnues(rapport)
            return rapport

        bore_max_m: Optional[float] = None
        V_unit_max_m3: Optional[float] = None
        course_max_m: Optional[float] = None

        if vitesse_piston_max_ms is not None:
            Up_max = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
            r_max = _require_positive("ratio_course_alesage_max", self.ratio_course_alesage_max, strict=True)

            bore_max_m = float(calcul_bore_max_admissible(Up_max, n_rpm, r_max))
            V_unit_max_m3 = float(calcul_cylindree_unit_max(bore_max_m, r_max))
            course_max_m = float(_course_max_depuis_vitesse_piston(Up_max, n_rpm))

            rapport["contraintes_admissibles"] = {
                "Up_max_ms": Up_max,
                "ratio_S_B_max": r_max,
                "bore_max_m": bore_max_m,
                "bore_max_mm": bore_max_m * 1000.0,
                "cylindree_unitaire_max_m3": V_unit_max_m3,
                "cylindree_unitaire_max_cc": V_unit_max_m3 * 1e6,
                "course_max_m": course_max_m,
                "course_max_mm": course_max_m * 1000.0,
            }
        else:
            rapport["contraintes_admissibles"] = {"Up_max_ms": None}

        n_min: Optional[int] = None
        if V_unit_max_m3 is not None:
            n_min_calc = int(calcul_nombre_cylindres_min(V_tot_m3, V_unit_max_m3))
            if n_min_calc >= 999:
                _push_inconnue(rapport, "impossibles", "N_min", "Cylindrée unitaire max invalide (paramètres incohérents).")
            else:
                n_min = n_min_calc
        else:
            _push_inconnue(rapport, "partielles", "N_min", "Calculable si vitesse_piston_max_ms est fournie.")
        rapport["cylindree"]["N_min"] = n_min

        if n_min is None:
            _dedup_inconnues(rapport)
            return rapport

        if n_min > self.n_max_absolu:
            _push_inconnue(rapport, "impossibles", "N_min", f"N_min={n_min} > n_max_absolu={self.n_max_absolu}.")
            _dedup_inconnues(rapport)
            return rapport

        cout_inter_base = _require_positive("cout_intervention_base_eur", self.cout_intervention_base_eur, strict=False)
        if self.activer_scraping_prix:
            try:
                _ = calcul_cout_maintenance_estime_auto_prix(
                    duree_usage_h=1.0,
                    duree_vie_joint_base_h=self.duree_vie_joint_base_h,
                    charge_nominale_n=1.0,
                    charge_actuelle_n=1.0,
                    nb_joints_base=max(1, n_min * self.joints_par_cyl),
                    nb_joints_actuel=max(1, n_min * self.joints_par_cyl),
                    cout_inter_eur=cout_inter_base,
                    activer_scraping=True,
                    urls_prix_joints=self.urls_prix_joints,
                    urls_main_oeuvre=self.urls_main_oeuvre,
                    cache_path=self.cache_path_prix,
                    cache_ttl_h=self.cache_ttl_h,
                    timeout_s=self.timeout_scraping_s,
                    temps_intervention_h=self.temps_intervention_h,
                    cout_arret_eur=self.cout_arret_eur,
                    cout_consommables_eur=self.cout_consommables_eur,
                    strict_scraping=self.strict_scraping,
                )
                rapport["notes_modele"].append("Scraping activé : le module sait estimer des prix ; calibrer cout_intervention_base_eur si besoin.")
            except Exception:
                rapport["notes_modele"].append("Scraping activé mais estimation prix indisponible (fallback sur cout_intervention_base_eur).")

        rapport["maintenance"]["cout_intervention_base_eur"] = cout_inter_base
        rapport["maintenance"]["duree_vie_joint_base_h"] = self.duree_vie_joint_base_h
        rapport["maintenance"]["joints_par_cyl"] = self.joints_par_cyl

        if longueur_dispo_m is None or largeur_dispo_m is None:
            _dedup_inconnues(rapport)
            return rapport

        L_max = _require_positive("longueur_dispo_m", longueur_dispo_m, strict=True)
        W_max = _require_positive("largeur_dispo_m", largeur_dispo_m, strict=True)

        n_max_explore = max(self.min_exploration, n_min + self.delta_exploration)
        n_max_explore = min(self.n_max_absolu, n_max_explore)

        V_u_ref = V_tot_m3 / n_min
        ratio_ref = self.ratio_course_alesage_max
        if course_max_m is not None:
            r_lim = _ratio_max_compatible_vitesse_piston(V_u_ref, course_max_m)
            if math.isfinite(r_lim):
                ratio_ref = min(self.ratio_course_alesage_max, r_lim)
        ratio_ref = max(1e-6, ratio_ref)
        bore_ref, _ = _bore_et_course_depuis_volume_et_ratio(V_u_ref, ratio_ref)
        charge_ref_n = PME * _surface_piston_m2(bore_ref)

        allowed_set: Optional[set[str]] = None
        if architectures_autorisees:
            allowed_set = set(map(str, architectures_autorisees))

        for N in range(n_min, n_max_explore + 1):
            V_u = V_tot_m3 / N

            ratio_ret = self.ratio_course_alesage_max
            if course_max_m is not None:
                r_lim = _ratio_max_compatible_vitesse_piston(V_u, course_max_m)
                if math.isfinite(r_lim):
                    ratio_ret = min(self.ratio_course_alesage_max, r_lim)
            ratio_ret = max(1e-6, ratio_ret)

            bore_m, course_m = _bore_et_course_depuis_volume_et_ratio(V_u, ratio_ret)

            if bore_max_m is not None and bore_m > bore_max_m + 1e-12:
                continue
            if course_max_m is not None and course_m > course_max_m + 1e-12:
                continue

            charge_moy_n = PME * _surface_piston_m2(bore_m)

            cout_maint_raw = float(
                calcul_cout_maintenance_estime(
                    duree_usage_h=T_usage,
                    duree_vie_joint_base_h=self.duree_vie_joint_base_h,
                    charge_nominale_n=charge_ref_n,
                    charge_actuelle_n=charge_moy_n,
                    nb_joints_base=max(1, n_min * self.joints_par_cyl),
                    nb_joints_actuel=max(1, N * self.joints_par_cyl),
                    cout_inter_eur=cout_inter_base,
                )
            )
            cout_maint_score = float(cout_maint_raw * float(poids_maintenance))

            if architecture_forcee is not None:
                arch = str(architecture_forcee)
            else:
                arch = _appeler_choix_architecture_optimale(N, L_max, W_max, cout_maint_score)

            if arch == "Inconnue":
                continue
            if allowed_set is not None and arch not in allowed_set:
                continue

            score_module, valide = _appeler_evaluer_architecture(arch, N, L_max, W_max, cout_maint_score)
            if not bool(valide):
                continue

            L_pkg, W_pkg = _estimer_packaging_simple(arch, N, pas_cylindre_m=self.pas_cylindre_m, largeur_base_m=self.largeur_base_m)

            compacite_score = None
            if _is_finite(L_pkg) and _is_finite(W_pkg):
                compacite_score = _safe_div((L_pkg / L_max) + (W_pkg / W_max), 2.0)

            maintenance_indice = _estimer_indice_maintenance(nb_cyl=N, architecture=arch)
            masse_relative = _estimer_masse_relative(nb_cyl=N, bore_m=bore_m, course_m=course_m, architecture=arch)
            cout_matiere_relatif = _estimer_cout_matiere_relatif(masse_relative=masse_relative, architecture=arch)
            fiabilite_indice = _estimer_indice_fiabilite(
                nb_cyl=N,
                architecture=arch,
                ratio_s_b=ratio_ret,
                charge_moy_piston_n=charge_moy_n,
                charge_ref_n=charge_ref_n,
            )
            rendement_indice = _estimer_indice_rendement_relatif(nb_cyl=N, architecture=arch, ratio_s_b=ratio_ret)

            row = {
                "N_cyl": N,
                "architecture": arch,
                "score_module_externe": float(score_module),
                "valide": bool(valide),
                "cout_maintenance_eur": float(cout_maint_raw),
                "cout_maintenance_score_eur": float(cout_maint_score),
                "maintenance_indice": float(maintenance_indice),
                "masse_relative": float(masse_relative),
                "cout_matiere_relatif": float(cout_matiere_relatif),
                "fiabilite_indice": float(fiabilite_indice),
                "rendement_indice": float(rendement_indice),
                "compacite_score": float(compacite_score) if compacite_score is not None else None,
                "cylindree_tot_cc": float(V_tot_m3 * 1e6),
                "cylindree_unit_cc": float(V_u * 1e6),
                "bore_mm": float(bore_m * 1000.0),
                "course_mm": float(course_m * 1000.0),
                "ratio_S_B": float(ratio_ret),
                "charge_moy_piston_N": float(charge_moy_n),
                "L_pkg_m_estimee": float(L_pkg),
                "W_pkg_m_estimee": float(W_pkg),
            }
            rapport["exploration"].append(row)

        if not rapport["exploration"]:
            _push_inconnue(
                rapport,
                "impossibles",
                "solution",
                "Aucune configuration (N, architecture) valide dans le gabarit et sous contraintes admissibles.",
            )
            _dedup_inconnues(rapport)
            return rapport

        _normaliser_sur_candidats(rapport["exploration"], "cout_maintenance_score_eur", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "masse_relative", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "cout_matiere_relatif", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "compacite_score", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "fiabilite_indice", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "rendement_indice", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "score_module_externe", sens="min")

        best_score = float("inf")
        best_row: Optional[Dict[str, Any]] = None

        for row in rapport["exploration"]:
            score_multi = _score_multi_criteres(
                row,
                poids_maintenance=poids_maintenance,
                poids_masse=poids_masse,
                poids_cout_matiere=poids_cout_matiere,
                poids_compacite=poids_compacite,
                poids_fiabilite=poids_fiabilite,
                poids_rendement=poids_rendement,
            )
            score_global = float(score_multi + 0.20 * float(row.get("score_module_externe_norm") or 0.0))
            row["score_multi_criteres"] = float(score_multi)
            row["score_global"] = float(score_global)
            if score_global < best_score:
                best_score = score_global
                best_row = row

        rapport["meilleur"] = best_row

        best_by_arch: Dict[str, Dict[str, Any]] = {}
        for row in rapport["exploration"]:
            a = str(row["architecture"])
            if a not in best_by_arch or float(row["score_global"]) < float(best_by_arch[a]["score_global"]):
                best_by_arch[a] = row
        rapport["meilleurs_par_architecture"] = best_by_arch

        if vitesse_piston_max_ms is not None:
            try:
                rapport["solution_module_globale"] = resoudre_architecture_globale(
                    puissance_cible_w=P,
                    regime_tr_min=n_rpm,
                    pme_pa=PME,
                    vitesse_piston_max_ms=_require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False),
                    L_max_m=L_max,
                    W_max_m=W_max,
                    horizon_usage_h=T_usage,
                )
            except Exception:
                rapport["solution_module_globale"] = None
                rapport["notes_modele"].append("Échec appel resoudre_architecture_globale (paramètres / contraintes).")

        rapport["notes_modele"].append(
            "Les critères masse/coût matière/fiabilité/rendement sont ici des indices RELATIFS d'arbitrage, pas des valeurs industrielles absolues."
        )
        rapport["notes_modele"].append(
            "Le score global combine explicitement maintenance, masse, coût matière, compacité, fiabilité relative et rendement relatif."
        )

        _push_inconnue(rapport, "impossibles", "PME réelle (carte + pertes + transitoires)", "PME est une entrée modèle. Impossible de la déduire sans cycle thermo/mesures.")
        _push_inconnue(rapport, "impossibles", "vibrations / NVH / équilibrage", "Nécessite un modèle dynamique complet.")
        _push_inconnue(rapport, "impossibles", "refroidissement & gradients thermiques", "Nécessite architecture thermique, matériaux, échanges, conditions d'usage.")
        _push_inconnue(rapport, "impossibles", "coût industriel réel", "Le coût matière/usinage réel nécessite procédés, temps de fabrication, tolérances, outillages et volumes de série.")
        _push_inconnue(rapport, "impossibles", "masse réelle moteur complet", "Une masse réelle exige ensuite le détail des pièces, matériaux, épaisseurs et accessoires.")

        _dedup_inconnues(rapport)
        return rapport


__all__ = [
    "UsageType",
    "ArchitectureType",
    "ProfilUsageMoteur",
    "estimer_pme_depuis_couple_et_cylindree",
    "estimer_pme_depuis_puissance_et_cylindree",
    "Architecture",
]
