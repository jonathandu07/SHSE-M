# backend/components/moteur_thermique/pieces/bielle.py
# =============================================================================
# CORPS DE BIELLE — SHSE-M
# Version complétée : calcul + inter-pièces + bloc CAO / SolidWorks
# =============================================================================
# Principe :
# - On calcule tout ce qui est calculable.
# - On récupère explicitement les données des autres pièces (piston, arbre_piston,
#   moteur_thermique, cylindre) si elles existent et si leur format le permet.
# - On n’invente pas : si une donnée manque, elle est déclarée "inconnue".
#
# Sorties principales :
# - Efforts axiaux max/min (si déductibles)
# - Section minimale A_min et, si la famille géométrique est imposée, dimensions du fût
# - Diamètre équivalent d_eq
# - Flambage Euler (si E, I_min, L, K connus)
# - Pressions de contact petite/grande tête
# - Bloc "cao" exploitable pour dessin manuel / SolidWorks
#
# IMPORTANT :
# - La géométrie complète réelle d’une bielle est un choix de conception.
# - Ici, aucune forme n’est choisie automatiquement :
#   * soit tu fournis la géométrie,
#   * soit tu fournis une famille (ex : rectangle + ratio b/h),
#   * soit le module renvoie des équivalents calculatoires et des inconnues.
# =============================================================================

# backend/components/moteur_thermique/pieces/bielle.py
# =============================================================================
# CORPS DE BIELLE — SHSE-M
# Version complétée : calcul + inter-pièces + bloc CAO / SolidWorks
# =============================================================================
# Principe :
# - On calcule tout ce qui est calculable.
# - On récupère explicitement les données des autres pièces (piston, arbre_piston,
#   moteur_thermique, cylindre) si elles existent et si leur format le permet.
# - On n’invente pas : si une donnée manque, elle est déclarée "inconnue".
#
# Sorties principales :
# - Efforts axiaux max/min (si déductibles)
# - Section minimale A_min et, si la famille géométrique est imposée, dimensions du fût
# - Diamètre équivalent d_eq
# - Flambage Euler (si E, I_min, L, K connus)
# - Pressions de contact petite/grande tête
# - Bloc "cao" exploitable pour dessin manuel / SolidWorks
#
# IMPORTANT :
# - La géométrie complète réelle d’une bielle est un choix de conception.
# - Ici, aucune forme n’est choisie automatiquement :
#   * soit tu fournis la géométrie,
#   * soit tu fournis une famille (ex : rectangle + ratio b/h),
#   * soit le module renvoie des équivalents calculatoires et des inconnues.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List, Literal

from backend.modules.systeme.dossier_definition import ajouter_dossier_definition_solidworks
import math


# =============================================================================
# Utilitaires généraux
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly and v <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if (not strictly) and v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": nom, "raison": raison}
    )


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

    rapport["inconnues"]["impossibles"] = dedup(list(rapport["inconnues"].get("impossibles", []) or []))
    rapport["inconnues"]["partielles"] = dedup(list(rapport["inconnues"].get("partielles", []) or []))


def _deep_get(d: Any, path: Tuple[str, ...]) -> Any:
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        if k not in cur:
            return None
        cur = cur[k]
    return cur


def _first_numeric_from_dict(d: Dict[str, Any], candidates: List[Tuple[str, ...]]) -> Optional[float]:
    for path in candidates:
        v = _deep_get(d, path)
        if _is_finite(v):
            return float(v)
    return None


def _missing_tolerance_bielle(nom: str, typ: str, raison: str) -> Dict[str, Any]:
    return {"nom": nom, "type": typ, "valeur": None, "statut": "missing", "raison": raison}


def _status_bielle(*values: Any) -> str:
    return "ok" if all(v is not None for v in values) else "partial"


def _ajouter_champs_metier_definition_bielle(rapport: Dict[str, Any]) -> None:
    geo = rapport.get("geometrie", {}) if isinstance(rapport.get("geometrie"), dict) else {}
    cao = rapport.get("cao", {}) if isinstance(rapport.get("cao"), dict) else {}
    petite = geo.get("petite_tete", {}) if isinstance(geo.get("petite_tete"), dict) else {}
    grande = geo.get("grande_tete", {}) if isinstance(geo.get("grande_tete"), dict) else {}
    petite_cao = cao.get("petite_tete", {}) if isinstance(cao.get("petite_tete"), dict) else {}
    grande_cao = cao.get("grande_tete", {}) if isinstance(cao.get("grande_tete"), dict) else {}
    fut = geo.get("fut", {}) if isinstance(geo.get("fut"), dict) else {}
    efforts = rapport.get("efforts", {}) if isinstance(rapport.get("efforts"), dict) else {}
    contacts = rapport.get("contacts_tetes", {}) if isinstance(rapport.get("contacts_tetes"), dict) else {}
    flambage = rapport.get("flambage", {}) if isinstance(rapport.get("flambage"), dict) else {}
    fatigue = rapport.get("fatigue", {}) if isinstance(rapport.get("fatigue"), dict) else {}
    d_petite = petite.get("diametre_axe_piston_m") or petite_cao.get("diametre_alÃ©sage_m") or petite_cao.get("diametre_alesage_m")
    d_grande = grande.get("diametre_maneton_m") or grande_cao.get("diametre_alÃ©sage_m") or grande_cao.get("diametre_alesage_m")
    tol_petite = petite_cao.get("tolerance_diametre_alÃ©sage_m") or petite_cao.get("tolerance_diametre_alesage_m")
    tol_grande = grande_cao.get("tolerance_diametre_alÃ©sage_m") or grande_cao.get("tolerance_diametre_alesage_m")

    rapport["surfaces_fonctionnelles"] = [
        {"nom": "alesage_petite_tete", "fonction": "liaison avec arbre_piston", "geometrie_associee": "petite_tete", "cote_associee": "diametre_axe_piston_m", "valeur_associee": d_petite, "risque": "pression de contact ou matage si diametre/largeur/jeu non definis", "controle_recommande": "diametre, coaxialite et rugosite alesage petite tete"},
        {"nom": "alesage_grande_tete", "fonction": "liaison avec maneton/vilebrequin", "geometrie_associee": "grande_tete", "cote_associee": "diametre_maneton_m", "valeur_associee": d_grande, "risque": "pression contact maneton ou defaut d'alignement", "controle_recommande": "diametre, largeur portee, parallelisme avec petite tete"},
        {"nom": "fut_bielle", "fonction": "transmission effort axial traction/compression", "geometrie_associee": "fut", "cote_associee": "section_fut_m2", "valeur_associee": fut.get("section_m2"), "risque": "flambage, fatigue ou contrainte axiale excessive", "controle_recommande": "section, epaisseur, rectitude et rayons de raccordement"},
    ]
    rapport["interfaces_assemblage"] = [
        {"piece_a": "bielle", "piece_b": "arbre_piston", "fonction": "pivot petite tete", "type_liaison": "pivot", "cote_interface": d_petite, "jeu_ou_serrage": _deep_get(rapport, ("entrees", "jeu_radial_petite_tete_m")), "tolerance": tol_petite, "effort_transmis": efforts.get("force_axiale_max_N"), "risque": "matage petite tete si pression admissible non verifiee", "statut": _status_bielle(d_petite)},
        {"piece_a": "bielle", "piece_b": "vilebrequin", "fonction": "pivot grande tete sur maneton", "type_liaison": "pivot", "cote_interface": d_grande, "jeu_ou_serrage": _deep_get(rapport, ("entrees", "jeu_radial_grande_tete_m")), "tolerance": tol_grande, "effort_transmis": efforts.get("force_axiale_max_N"), "risque": "pression contact maneton ou fatigue grande tete", "statut": _status_bielle(d_grande)},
        {"piece_a": "bielle", "piece_b": "roulement_aiguille_arbre", "fonction": "support tribologique petite ou grande tete", "type_liaison": "roulement/coussinet", "cote_interface": petite.get("largeur_portee_m") or grande.get("largeur_portee_m"), "jeu_ou_serrage": None, "tolerance": None, "effort_transmis": efforts.get("force_axiale_max_N"), "risque": "reference et jeu roulement non selectionnes", "statut": "partial"},
    ]
    rapport["tolerances"] = [
        {"nom": "diametre_alesage_petite_tete", "type": "diametral", "valeur": tol_petite, "statut": "known" if tol_petite is not None else "missing", "source": "geometrie.petite_tete", "raison": None if tol_petite is not None else "tolerance a definir selon axe, coussinet/roulement et procede"},
        {"nom": "diametre_alesage_grande_tete", "type": "diametral", "valeur": tol_grande, "statut": "known" if tol_grande is not None else "missing", "source": "geometrie.grande_tete", "raison": None if tol_grande is not None else "tolerance a definir selon maneton, coussinet/roulement et procede"},
        _missing_tolerance_bielle("parallelisme_petite_grande_tete", "geometrique", "a definir selon procede et montage final"),
    ]
    rapport["contraintes_rdm"] = [
        {"nom": "contrainte_axiale", "type": "traction_compression", "valeur": _deep_get(rapport, ("contraintes", "axial")), "source": "contraintes.axial"},
        {"nom": "flambage_euler", "type": "flambage", "valeur": flambage, "source": "flambage"},
        {"nom": "fatigue", "type": "fatigue", "valeur": fatigue, "source": "fatigue"},
        {"nom": "contacts_tetes", "type": "pression_contact", "valeur": contacts, "source": "contacts_tetes"},
    ]
    rapport["limites_usage"] = [
        {"nom": "force_axiale_max", "valeur": efforts.get("force_axiale_max_N"), "unite": "N", "condition_non_conformite": "effort axial superieur au dimensionnement"},
        {"nom": "charge_critique_flambage", "valeur": flambage.get("charge_critique_N"), "unite": "N", "condition_non_conformite": "force compression proche ou superieure a la charge critique"},
        {"nom": "limite_endurance", "valeur": _deep_get(rapport, ("materiau", "limite_endurance_pa")), "unite": "Pa", "condition_non_conformite": "fatigue non validee sous cycle fourni"},
    ]
    rapport["controles_qualite"] = [
        {"nom": "entraxe_bielle", "type": "cote", "cote": _deep_get(rapport, ("cao", "entraxe_centres_m")), "controle": "mesure entraxe petite/grande tete"},
        {"nom": "alesage_petite_tete", "type": "cote", "cote": d_petite, "controle": "diametre et rugosite"},
        {"nom": "alesage_grande_tete", "type": "cote", "cote": d_grande, "controle": "diametre, circularite et largeur portee"},
        {"nom": "parallelisme_tetes", "type": "geometrique", "cote": None, "controle": "parallelisme/coaxialite a definir et verifier"},
    ]
    rapport["notes_modelisation"] = [
        {"nom": "feature_initiale", "texte": "Modele SolidWorks conseille: esquisser entraxe petite/grande tete puis construire fut et bossages."},
        {"nom": "references", "texte": "Nommer les axes petite_tete et grande_tete pour les contraintes d'assemblage."},
        {"nom": "parametrique", "texte": "Laisser entraxe, diametres d'alesage et section de fut parametriques ; aucun export STEP n'est genere."},
    ]


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    for m in ("calculer", "analyser"):
        try:
            if hasattr(obj, m) and callable(getattr(obj, m)):
                r = getattr(obj, m)(strict=False)
                if isinstance(r, dict):
                    return r
        except TypeError:
            try:
                r = getattr(obj, m)()
                if isinstance(r, dict):
                    return r
            except Exception:
                continue
        except Exception:
            continue
    return None


def _aire_disque(d: float) -> float:
    d_v = _req_pos("d", d)
    return math.pi * (0.5 * d_v) ** 2


def _inertie_cercle(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**4) / 64.0


def _sigma_axiale(F: float, A: float) -> float:
    return float(F) / float(A)


def _euler_pcrit(E: float, I: float, L: float, K: float) -> float:
    E_v = _req_pos("E", E)
    I_v = _req_pos("I", I)
    L_v = _req_pos("L", L)
    K_v = _req_pos("K", K)
    return (math.pi**2) * E_v * I_v / ((K_v * L_v) ** 2)


def _rectangle_dims_from_area_ratio(A: float, ratio_b_sur_h: float) -> Tuple[float, float]:
    """
    A = b*h et b = r*h => h = sqrt(A/r), b = r*h
    """
    A_v = _req_pos("A", A)
    r = _req_pos("ratio_b_sur_h", ratio_b_sur_h)
    h = math.sqrt(A_v / r)
    b = r * h
    return b, h


def _rectangle_inerties(b: float, h: float) -> Dict[str, float]:
    b_v = _req_pos("b", b)
    h_v = _req_pos("h", h)
    Ix = (b_v * h_v**3) / 12.0
    Iy = (h_v * b_v**3) / 12.0
    return {
        "Ix_m4": Ix,
        "Iy_m4": Iy,
        "Imin_m4": min(Ix, Iy),
        "Imax_m4": max(Ix, Iy),
    }


def _goodman_utilisation(sigma_a: float, sigma_m: float, Se: float, Rm: float) -> Optional[float]:
    return (float(sigma_a) / float(Se)) + (max(float(sigma_m), 0.0) / float(Rm))


def _soderberg_utilisation(sigma_a: float, sigma_m: float, Se: float, Re: float) -> Optional[float]:
    return (float(sigma_a) / float(Se)) + (max(float(sigma_m), 0.0) / float(Re))


def _gerber_utilisation(sigma_a: float, sigma_m: float, Se: float, Rm: float) -> Optional[float]:
    return (float(sigma_a) / float(Se)) + (max(float(sigma_m), 0.0) / float(Rm)) ** 2


def _euler_flambage_detaille(E: float, I: float, A: float, L: float, K: float, Re: Optional[float]) -> Dict[str, float]:
    Pcr = _euler_pcrit(E, I, L, K)
    rg = math.sqrt(float(I) / float(A))
    out = {
        "charge_critique_euler_N": Pcr,
        "rayon_giration_m": rg,
        "elancement": (float(K) * float(L)) / rg,
    }
    if Re is not None:
        Py = float(A) * float(Re)
        out["charge_critique_rankine_N"] = 1.0 / ((1.0 / Pcr) + (1.0 / Py))
    return out


def _deformation_annulaire_simplifiee(F: float, E: float, largeur: float, epaisseur_radiale: float, rayon_moyen: float) -> Dict[str, float]:
    b = _req_pos("largeur", largeur)
    t = _req_pos("epaisseur_radiale", epaisseur_radiale)
    R = _req_pos("rayon_moyen", rayon_moyen)
    E_v = _req_pos("E", E)
    k = (E_v * b * t**3) / (12.0 * R**3)
    return {"raideur_N_m": k, "deformation_diametrale_m": float(F) / k if k > 0.0 else math.inf}


def _pv_palier(pression_pa: float, vitesse_m_s: float) -> float:
    return float(pression_pa) * float(vitesse_m_s)


def _sommerfeld_simplifie(mu_pa_s: float, n_tr_s: float, pression_pa: float, rayon_m: float, jeu_radial_m: float) -> float:
    return (float(mu_pa_s) * float(n_tr_s) / float(pression_pa)) * (float(rayon_m) / float(jeu_radial_m)) ** 2


# =============================================================================
# Matériau (optionnel via materiaux.py)
# =============================================================================

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
    resistance_traction_pa: Optional[float] = None,
    limite_endurance_pa: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    rho = densite_kg_m3
    Re = limite_elastique_pa
    E = module_young_pa
    Rm = resistance_traction_pa
    Se = limite_endurance_pa

    if materiau_cle:
        for modname in (
            "backend.ensemble.materiaux",
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                mat = None
                if hasattr(mod, "get_materiau"):
                    mat = mod.get_materiau(materiau_cle)  # type: ignore[attr-defined]
                elif hasattr(mod, "MATERIAUX"):
                    mats = getattr(mod, "MATERIAUX")
                    if isinstance(mats, dict):
                        mat = mats.get(materiau_cle)

                if mat is None:
                    continue
                valeur = getattr(mod, "valeur", None)

                def g(obj: Any, *names: str, mode: str = "typique") -> Optional[float]:
                    for n in names:
                        if isinstance(obj, dict) and n in obj:
                            v = obj.get(n)
                        else:
                            v = getattr(obj, n, None)
                        if v is not None and _is_finite(v):
                            return float(v)
                        if callable(valeur):
                            try:
                                out = valeur(v, mode=mode)
                                if _is_finite(out):
                                    return float(out)
                            except Exception:
                                pass
                    return None

                rho = rho if rho is not None else g(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                Re = Re if Re is not None else g(mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa", mode="min")
                if Re is None and hasattr(mat, "limite_elastique_effective_pa"):
                    try:
                        v = mat.limite_elastique_effective_pa(mode="min")
                        if _is_finite(v):
                            Re = float(v)
                    except Exception:
                        pass
                if Re is None:
                    try:
                        segs = list(getattr(mat, "resistance_par_section", ()) or ())
                        vals = [
                            float(seg.rp02_pa_min)
                            for seg in segs
                            if _is_finite(getattr(seg, "rp02_pa_min", None))
                        ]
                        if vals:
                            Re = min(vals)
                    except Exception:
                        pass
                E = E if E is not None else g(mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa")
                Rm = Rm if Rm is not None else g(mat, "resistance_traction_pa", "Rm_pa", "uts_pa", "ultimate_strength_pa", mode="min")
                if Rm is None and hasattr(mat, "resistance_traction_effective_pa"):
                    try:
                        v = mat.resistance_traction_effective_pa(mode="min")
                        if _is_finite(v):
                            Rm = float(v)
                    except Exception:
                        pass
                if Rm is None:
                    try:
                        segs = list(getattr(mat, "resistance_par_section", ()) or ())
                        vals = []
                        for seg in segs:
                            rm = getattr(seg, "rm_pa", None)
                            out = valeur(rm, mode="min") if callable(valeur) else rm
                            if _is_finite(out):
                                vals.append(float(out))
                        if vals:
                            Rm = min(vals)
                    except Exception:
                        pass
                Se = Se if Se is not None else g(mat, "limite_fatigue_pa", "limite_endurance_pa", "Sf_pa", "endurance_limit_pa", mode="min")
                if Se is None and hasattr(mat, "limite_fatigue_effective_pa"):
                    try:
                        v = mat.limite_fatigue_effective_pa(mode="min")
                        if _is_finite(v):
                            Se = float(v)
                    except Exception:
                        pass
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "limite_elastique_pa": Re,
        "module_young_pa": E,
        "resistance_traction_pa": Rm,
        "limite_endurance_pa": Se,
    }


# =============================================================================
# Règles explicites CAO / fabrication
# =============================================================================

FormeFutBielle = Literal["rectangle", "rond_equivalent", "equivalent_sans_forme"]
FormeTeteBielle = Literal["circulaire", "non_definie"]


@dataclass(frozen=True)
class ReglesFabricationBielle:
    # Marges explicites
    surlongueur_fut_par_tete_m: float = 0.002
    epaisseur_radiale_tete_min_m: float = 0.002
    largeur_tete_marge_sur_portee_m: float = 0.001

    # Détails CAO
    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.0020
    ratio_chanfrein_sur_epaisseur: float = 0.15

    rayon_conge_min_m: float = 0.0008
    rayon_conge_max_m: float = 0.0040
    ratio_conge_sur_epaisseur_fut: float = 0.25

    # Finition
    rugosite_fut_ra_um: float = 1.6
    rugosite_alésages_tetes_ra_um: float = 0.8
    tolerance_longueur_m: float = 0.00010
    tolerance_diametre_alésage_m: float = 0.00003
    tolerance_largeur_tete_m: float = 0.00005
    tolerance_fut_m: float = 0.00005


# =============================================================================
# Pièce : CorpsBielle
# =============================================================================

@dataclass
class CorpsBielle:
    """
    Corps de bielle + cohérence géométrique petite/grande tête + bloc CAO.
    """

    # Liens vers autres pièces
    piston: Optional[Any] = None
    arbre_piston: Optional[Any] = None
    cylindre: Optional[Any] = None
    moteur_thermique: Optional[Any] = None

    # Longueur de bielle (entraxe)
    longueur_bielle_m: Optional[float] = None

    # Matériau
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None
    resistance_traction_pa: Optional[float] = None
    limite_endurance_pa: Optional[float] = None

    # Fatigue (facteurs explicites)
    coefficient_entaille_Kt: float = 1.0
    facteur_surface: float = 1.0
    facteur_taille: float = 1.0
    facteur_fiabilite: float = 1.0
    facteur_charge_fatigue: float = 1.0
    facteur_temperature_fatigue: float = 1.0

    # Sécurité
    facteur_securite: float = 2.0

    # Flambage
    K_flambage: Optional[float] = None
    K_flambage_plan_fort: Optional[float] = None
    K_flambage_plan_faible: Optional[float] = None
    inertie_plan_fort_fut_m4: Optional[float] = None
    inertie_plan_faible_fut_m4: Optional[float] = None

    # Efforts
    force_axiale_max_N: Optional[float] = None
    force_axiale_min_N: Optional[float] = None
    force_axiale_max_tension_N: Optional[float] = None
    force_axiale_max_compression_N: Optional[float] = None
    effort_lateral_max_N: Optional[float] = None
    rpm: Optional[float] = None

    # Géométrie fût : options
    diametre_equivalent_fut_m: Optional[float] = None
    largeur_fut_m: Optional[float] = None
    epaisseur_fut_m: Optional[float] = None
    section_fut_m2: Optional[float] = None
    inertie_min_fut_m4: Optional[float] = None
    ratio_largeur_sur_epaisseur: Optional[float] = None
    forme_fut: FormeFutBielle = "equivalent_sans_forme"

    # Petites / grandes têtes
    diametre_axe_piston_m: Optional[float] = None
    longueur_portee_petite_tete_m: Optional[float] = None
    pression_admissible_petite_tete_pa: Optional[float] = None

    diametre_maneton_m: Optional[float] = None
    longueur_portee_grande_tete_m: Optional[float] = None
    pression_admissible_grande_tete_pa: Optional[float] = None

    # Epaisseurs / largeurs radiales des têtes si tu veux imposer une géométrie
    epaisseur_radiale_petite_tete_m: Optional[float] = None
    epaisseur_radiale_grande_tete_m: Optional[float] = None
    largeur_exterieure_petite_tete_m: Optional[float] = None
    largeur_exterieure_grande_tete_m: Optional[float] = None
    pression_matage_admissible_petite_tete_pa: Optional[float] = None
    pression_matage_admissible_grande_tete_pa: Optional[float] = None
    pv_admissible_petite_tete_pa_m_s: Optional[float] = None
    pv_admissible_grande_tete_pa_m_s: Optional[float] = None
    vitesse_glissement_petite_tete_m_s: Optional[float] = None
    vitesse_glissement_grande_tete_m_s: Optional[float] = None
    viscosite_huile_pa_s: Optional[float] = None
    jeu_radial_petite_tete_m: Optional[float] = None
    jeu_radial_grande_tete_m: Optional[float] = None

    # Règles CAO
    regles_fabrication: ReglesFabricationBielle = field(default_factory=ReglesFabricationBielle)

    # -------------------------------------------------------------------------
    # Extraction inter-pièces
    # -------------------------------------------------------------------------

    def _extraire_efforts_depuis_piston(self, rapport: Dict[str, Any]) -> Optional[float]:
        rp = _try_call_report(self.piston)
        if not isinstance(rp, dict):
            _push_inconnue(rapport, "partielles", "efforts piston", "Impossible de lire piston.")
            return None

        candidates = [
            ("cinematique", "force_axiale_nette_n"),
            ("cinematique", "force_gaz_n"),
            ("resultats", "force_pression_piston_max_N"),
            ("dimensionnement", "force_pression_piston_max_N"),
            ("dimensionnement", "force_pression_piston_service_N"),
            ("force_gaz_N",),
            ("force_pression_N",),
        ]
        F = _first_numeric_from_dict(rp, candidates)
        if F is not None:
            rapport["notes_modele"].append("force_axiale_max_N déduite depuis piston.")
        else:
            _push_inconnue(rapport, "partielles", "force piston", "Aucune clé d'effort reconnue dans le rapport piston.")
        return F

    def _extraire_efforts_depuis_moteur_thermique(self, rapport: Dict[str, Any]) -> Optional[float]:
        rm = _try_call_report(self.moteur_thermique)
        if not isinstance(rm, dict):
            _push_inconnue(rapport, "partielles", "efforts moteur_thermique", "Impossible de lire moteur_thermique.")
            return None

        candidates = [
            ("forces", "force_bielle_N"),
            ("forces", "force_bielle_max_N"),
            ("resultats", "force_bielle_N"),
            ("resultats", "F_bielle_N"),
            ("resultats", "force_bielle_max_N"),
            ("dimensionnement", "force_bielle_N"),
            ("force_bielle_N",),
            ("F_bielle_N",),
        ]
        F = _first_numeric_from_dict(rm, candidates)
        if F is not None:
            rapport["notes_modele"].append("force_axiale_max_N déduite depuis moteur_thermique.")
        else:
            _push_inconnue(rapport, "partielles", "force bielle", "Aucune clé force_bielle reconnue dans moteur_thermique.")
        return F

    def _extraire_diametre_axe_depuis_arbre_piston(self, rapport: Dict[str, Any]) -> Optional[float]:
        if self.arbre_piston is None:
            return None

        for attr in (
            "diametre_portee_coussinet_m",
            "diametre_teton_gauche_m",
            "diametre_teton_droit_m",
            "diametre_fut_central_m",
            "diametre_arbre_m",
        ):
            try:
                v = getattr(self.arbre_piston, attr, None)
                if _is_finite(v):
                    rapport["notes_modele"].append(f"diametre_axe_piston_m déduit depuis arbre_piston.{attr}.")
                    return float(v)
            except Exception:
                pass

        ra = _try_call_report(self.arbre_piston)
        if isinstance(ra, dict):
            candidates = [
                ("geometrie", "diametre_portee_coussinet_m"),
                ("geometrie", "diametre_teton_gauche_m"),
                ("geometrie", "diametre_teton_droit_m"),
                ("entrees", "diametre_portee_coussinet_m"),
                ("entrees", "diametre_teton_gauche_m"),
                ("entrees", "diametre_teton_droit_m"),
                ("cao", "teton_gauche", "diametre_m"),
                ("cao", "teton_droit", "diametre_m"),
            ]
            d = _first_numeric_from_dict(ra, candidates)
            if d is not None:
                rapport["notes_modele"].append("diametre_axe_piston_m déduit depuis le rapport arbre_piston.")
                return d

        _push_inconnue(
            rapport,
            "partielles",
            "diametre_axe_piston_m",
            "Impossible de déduire depuis arbre_piston.",
        )
        return None

    def _extraire_longueur_bielle(self, rapport: Dict[str, Any]) -> Optional[float]:
        for src in (self.moteur_thermique, self.cylindre, self.piston):
            if src is None:
                continue

            for attr in ("longueur_bielle_m", "entraxe_bielle_m"):
                try:
                    v = getattr(src, attr, None)
                    if _is_finite(v):
                        rapport["notes_modele"].append(f"longueur_bielle_m déduite depuis {src.__class__.__name__}.{attr}.")
                        return float(v)
                except Exception:
                    pass

            r = _try_call_report(src)
            if isinstance(r, dict):
                candidates = [
                    ("entrees", "longueur_bielle_m"),
                    ("geometrie", "longueur_bielle_m"),
                    ("resultats", "longueur_bielle_m"),
                    ("entrees", "entraxe_bielle_m"),
                ]
                v = _first_numeric_from_dict(r, candidates)
                if v is not None:
                    rapport["notes_modele"].append("longueur_bielle_m déduite depuis un rapport d'autre pièce.")
                    return v

        _push_inconnue(
            rapport,
            "impossibles",
            "longueur_bielle_m",
            "Nécessaire pour flambage/masse/CAO. Non fournie et non déductible.",
        )
        return None

    def _extraire_diametre_maneton_depuis_moteur(self, rapport: Dict[str, Any]) -> Optional[float]:
        if self.moteur_thermique is None:
            return None

        for attr in ("diametre_maneton_m", "diametre_palier_bielle_m", "diametre_portee_maneton_m"):
            try:
                v = getattr(self.moteur_thermique, attr, None)
                if _is_finite(v):
                    rapport["notes_modele"].append(f"diametre_maneton_m déduit depuis moteur_thermique.{attr}.")
                    return float(v)
            except Exception:
                pass

        rm = _try_call_report(self.moteur_thermique)
        if isinstance(rm, dict):
            candidates = [
                ("geometrie", "diametre_maneton_m"),
                ("dimensionnement", "diametre_maneton_m"),
                ("resultats", "diametre_maneton_m"),
            ]
            d = _first_numeric_from_dict(rm, candidates)
            if d is not None:
                rapport["notes_modele"].append("diametre_maneton_m déduit depuis le rapport moteur_thermique.")
                return d

        return None

    # -------------------------------------------------------------------------
    # Calcul principal
    # -------------------------------------------------------------------------

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "corps_bielle",
            "entrees": {},
            "sources": {},
            "materiau": {},
            "efforts": {},
            "geometrie": {
                "fut": {},
                "petite_tete": {},
                "grande_tete": {},
            },
            "dimensionnements": {},
            "cycle_charge": {},
            "contraintes": {},
            "fatigue": {},
            "flambage": {},
            "flambage_detaille": {},
            "contacts_tetes": {},
            "contacts_tetes_affines": {},
            "masse": {},
            "cao": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ---------------------------------------------------------------------
        # 1) Matériau
        # ---------------------------------------------------------------------
        props = _resoudre_materiau(
            self.materiau_cle,
            self.densite_kg_m3,
            self.limite_elastique_pa,
            self.module_young_pa,
            self.resistance_traction_pa,
            self.limite_endurance_pa,
        )
        rho = props["densite_kg_m3"]
        Re = props["limite_elastique_pa"]
        E = props["module_young_pa"]
        Rm = props["resistance_traction_pa"]
        Se = props["limite_endurance_pa"]

        sigma_adm = (float(Re) / FS) if Re is not None else None

        rapport["materiau"] = {
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": rho,
            "limite_elastique_pa": Re,
            "module_young_pa": E,
            "resistance_traction_pa": Rm,
            "limite_endurance_pa": Se,
            "sigma_admissible_pa": sigma_adm,
        }

        # ---------------------------------------------------------------------
        # 2) Efforts
        # ---------------------------------------------------------------------
        Fmax = self.force_axiale_max_N
        Fmin = self.force_axiale_min_N

        if Fmax is None and self.moteur_thermique is not None:
            Fmax = self._extraire_efforts_depuis_moteur_thermique(rapport)
            if Fmax is not None:
                rapport["sources"]["force_axiale_max_N"] = "moteur_thermique"

        if Fmax is None and self.piston is not None:
            Fmax = self._extraire_efforts_depuis_piston(rapport)
            if Fmax is not None:
                rapport["sources"]["force_axiale_max_N"] = "piston"

        if Fmax is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "force_axiale_max_N",
                "Indispensable pour dimensionner la bielle.",
            )
        else:
            Fmax = _req_finite("force_axiale_max_N", Fmax)

        if Fmin is not None:
            Fmin = _req_finite("force_axiale_min_N", Fmin)

        rapport["efforts"] = {
            "force_axiale_max_N": Fmax,
            "force_axiale_min_N": Fmin,
            "force_axiale_max_tension_N": self.force_axiale_max_tension_N,
            "force_axiale_max_compression_N": self.force_axiale_max_compression_N,
            "effort_lateral_max_N": self.effort_lateral_max_N,
            "rpm": self.rpm,
        }

        F_tension = abs(_req_pos("force_axiale_max_tension_N", self.force_axiale_max_tension_N, strictly=False)) if self.force_axiale_max_tension_N is not None else None
        F_compression = abs(_req_pos("force_axiale_max_compression_N", self.force_axiale_max_compression_N, strictly=False)) if self.force_axiale_max_compression_N is not None else None

        if F_tension is None or F_compression is None:
            vals = [float(v) for v in (Fmax, Fmin) if v is not None]
            if vals:
                if F_tension is None and max(vals) > 0.0:
                    F_tension = max(vals)
                if F_compression is None and min(vals) < 0.0:
                    F_compression = abs(min(vals))

        if F_tension is not None or F_compression is not None:
            Fsig_max = float(F_tension) if F_tension is not None else 0.0
            Fsig_min = -float(F_compression) if F_compression is not None else 0.0
            rapport["cycle_charge"] = {
                "Fmax_tension_N": F_tension,
                "Fmax_compression_N": F_compression,
                "effort_moyen_N": 0.5 * (Fsig_max + Fsig_min),
                "effort_alterne_N": 0.5 * (Fsig_max - Fsig_min),
                "rapport_R": (Fsig_min / Fsig_max) if Fsig_max != 0.0 else None,
                "force_max_signee_N": Fsig_max,
                "force_min_signee_N": Fsig_min,
            }
        else:
            _push_inconnue(rapport, "partielles", "cycle_traction_compression", "Nécessite Fmax/Fmin ou Fmax_tension/Fmax_compression.")

        # ---------------------------------------------------------------------
        # 3) Longueur entraxe
        # ---------------------------------------------------------------------
        L = self.longueur_bielle_m
        if L is None:
            L = self._extraire_longueur_bielle(rapport)
            if L is not None:
                rapport["sources"]["longueur_bielle_m"] = "autre_piece"
        else:
            L = _req_pos("longueur_bielle_m", L)

        # ---------------------------------------------------------------------
        # 4) Diamètres / portées têtes
        # ---------------------------------------------------------------------
        d_axe = self.diametre_axe_piston_m
        if d_axe is None and self.arbre_piston is not None:
            d_axe = self._extraire_diametre_axe_depuis_arbre_piston(rapport)
            if d_axe is not None:
                rapport["sources"]["diametre_axe_piston_m"] = "arbre_piston"
        elif d_axe is not None:
            d_axe = _req_pos("diametre_axe_piston_m", d_axe)

        if d_axe is None:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_axe_piston_m",
                "Requis pour pression de contact petite tête et CAO complète.",
            )

        d_maneton = self.diametre_maneton_m
        if d_maneton is None and self.moteur_thermique is not None:
            d_maneton = self._extraire_diametre_maneton_depuis_moteur(rapport)
            if d_maneton is not None:
                rapport["sources"]["diametre_maneton_m"] = "moteur_thermique"
        elif d_maneton is not None:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)

        if d_maneton is None:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_maneton_m",
                "Requis pour pression de contact grande tête et CAO complète.",
            )

        Lp = _req_pos("longueur_portee_petite_tete_m", self.longueur_portee_petite_tete_m) if self.longueur_portee_petite_tete_m is not None else None
        Lg = _req_pos("longueur_portee_grande_tete_m", self.longueur_portee_grande_tete_m) if self.longueur_portee_grande_tete_m is not None else None

        rapport["geometrie"]["petite_tete"].update({
            "diametre_axe_piston_m": d_axe,
            "longueur_portee_m": Lp,
        })
        rapport["geometrie"]["grande_tete"].update({
            "diametre_maneton_m": d_maneton,
            "longueur_portee_m": Lg,
        })

        # ---------------------------------------------------------------------
        # 5) Géométrie fût : A et Imin
        # ---------------------------------------------------------------------
        A: Optional[float] = None
        Imin: Optional[float] = None
        modele_section: Optional[str] = None
        b_fut: Optional[float] = None
        h_fut: Optional[float] = None
        d_eq: Optional[float] = None

        # Cas 1 : section + inertie directes
        if self.section_fut_m2 is not None:
            A = _req_pos("section_fut_m2", self.section_fut_m2)
            modele_section = "section_directe"
            rapport["geometrie"]["fut"]["section_fut_m2"] = A

            if self.inertie_min_fut_m4 is not None:
                Imin = _req_pos("inertie_min_fut_m4", self.inertie_min_fut_m4)
                rapport["geometrie"]["fut"]["inertie_min_fut_m4"] = Imin
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "inertie_min_fut_m4",
                    "Indispensable pour flambage si seule la section est fournie.",
                )

            d_eq = math.sqrt(4.0 * A / math.pi)
            rapport["geometrie"]["fut"]["diametre_equivalent_depuis_section_m"] = d_eq

        # Cas 2 : rectangle imposé
        elif self.largeur_fut_m is not None and self.epaisseur_fut_m is not None:
            b_fut = _req_pos("largeur_fut_m", self.largeur_fut_m)
            h_fut = _req_pos("epaisseur_fut_m", self.epaisseur_fut_m)
            A = b_fut * h_fut
            iner = _rectangle_inerties(b_fut, h_fut)
            Imin = iner["Imin_m4"]
            d_eq = math.sqrt(4.0 * A / math.pi)
            modele_section = "rectangle"

            rapport["geometrie"]["fut"].update({
                "largeur_fut_m": b_fut,
                "epaisseur_fut_m": h_fut,
                "section_fut_m2": A,
                "Ix_m4": iner["Ix_m4"],
                "Iy_m4": iner["Iy_m4"],
                "inertie_min_fut_m4": Imin,
                "diametre_equivalent_m": d_eq,
            })

        # Cas 3 : rond équivalent imposé
        elif self.diametre_equivalent_fut_m is not None:
            d_eq = _req_pos("diametre_equivalent_fut_m", self.diametre_equivalent_fut_m)
            A = _aire_disque(d_eq)
            Imin = _inertie_cercle(d_eq)
            modele_section = "rond_equivalent"

            rapport["geometrie"]["fut"].update({
                "diametre_equivalent_fut_m": d_eq,
                "section_fut_m2": A,
                "inertie_min_fut_m4": Imin,
            })

        # Cas 4 : dimensionnement minimal depuis Fmax et Re
        else:
            if Fmax is not None and sigma_adm is not None:
                A_min = abs(float(Fmax)) / sigma_adm
                d_eq_min = math.sqrt(4.0 * A_min / math.pi)

                rapport["dimensionnements"]["section_min_calculee_m2"] = A_min
                rapport["dimensionnements"]["diametre_equivalent_min_m"] = d_eq_min
                rapport["dimensionnements"]["critere_section"] = "sigma_axiale <= Re/FS"
                rapport["notes_modele"].append(
                    "Le diamètre équivalent du fût est une représentation de section, pas un choix de forme réel."
                )

                if self.forme_fut == "rectangle":
                    if self.ratio_largeur_sur_epaisseur is None:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "ratio_largeur_sur_epaisseur",
                            "Requis pour convertir A_min en rectangle (b,h) sans inventer.",
                        )
                    else:
                        r = _req_pos("ratio_largeur_sur_epaisseur", self.ratio_largeur_sur_epaisseur)
                        b_fut, h_fut = _rectangle_dims_from_area_ratio(A_min, r)
                        iner = _rectangle_inerties(b_fut, h_fut)
                        A = A_min
                        Imin = iner["Imin_m4"]
                        d_eq = d_eq_min
                        modele_section = "rectangle_equivalent"

                        rapport["dimensionnements"]["rectangle_equivalent"] = {
                            "ratio_b_sur_h": r,
                            "largeur_b_m": b_fut,
                            "epaisseur_h_m": h_fut,
                            "section_m2": A,
                            "Ix_m4": iner["Ix_m4"],
                            "Iy_m4": iner["Iy_m4"],
                            "inertie_min_m4": Imin,
                            "note": "Calculé uniquement car le ratio a été fourni explicitement.",
                        }

                        rapport["geometrie"]["fut"].update({
                            "largeur_fut_m": b_fut,
                            "epaisseur_fut_m": h_fut,
                            "section_fut_m2": A,
                            "Ix_m4": iner["Ix_m4"],
                            "Iy_m4": iner["Iy_m4"],
                            "inertie_min_fut_m4": Imin,
                            "diametre_equivalent_m": d_eq,
                        })

                elif self.forme_fut == "rond_equivalent":
                    A = A_min
                    Imin = _inertie_cercle(d_eq_min)
                    d_eq = d_eq_min
                    modele_section = "rond_equivalent_minimal"
                    rapport["geometrie"]["fut"].update({
                        "diametre_equivalent_fut_m": d_eq,
                        "section_fut_m2": A,
                        "inertie_min_fut_m4": Imin,
                    })

                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "géométrie_fut",
                        "A_min et d_eq sont calculés, mais la forme réelle du fût n'est pas imposée.",
                    )
            else:
                if Fmax is None:
                    _push_inconnue(rapport, "impossibles", "dimensionnement section fût", "Nécessite force_axiale_max_N.")
                if sigma_adm is None:
                    _push_inconnue(rapport, "impossibles", "dimensionnement section fût", "Nécessite limite_elastique_pa ou materiau_cle résoluble.")

        # ---------------------------------------------------------------------
        # 6) Contraintes axiales
        # ---------------------------------------------------------------------
        if A is not None and Fmax is not None:
            sigma = _sigma_axiale(float(Fmax), float(A))
            marge = (sigma_adm / abs(sigma)) if (sigma_adm is not None and sigma != 0.0) else None
            rapport["contraintes"]["axial"] = {
                "modele_section": modele_section,
                "sigma_axiale_pa_sur_Fmax": sigma,
                "sigma_tension_max_pa": (_sigma_axiale(float(rapport["cycle_charge"]["Fmax_tension_N"]), float(A)) if rapport["cycle_charge"].get("Fmax_tension_N") is not None else None),
                "sigma_compression_max_pa": (-_sigma_axiale(float(rapport["cycle_charge"]["Fmax_compression_N"]), float(A)) if rapport["cycle_charge"].get("Fmax_compression_N") is not None else None),
                "sigma_admissible_pa": sigma_adm,
                "marge_axiale": marge,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contrainte_axiale",
                "Calculable si section de fût et force axiale max sont connues.",
            )

        if A is not None and rapport["cycle_charge"]:
            smax = _sigma_axiale(float(rapport["cycle_charge"]["force_max_signee_N"]), float(A))
            smin = _sigma_axiale(float(rapport["cycle_charge"]["force_min_signee_N"]), float(A))
            sigma_m = 0.5 * (smax + smin)
            sigma_a = 0.5 * (smax - smin)
            Kt = _req_pos("coefficient_entaille_Kt", self.coefficient_entaille_Kt)
            sigma_m_loc = Kt * sigma_m
            sigma_a_loc = Kt * sigma_a
            Se_corr = None
            if Se is not None:
                Se_corr = float(Se) * float(self.facteur_surface) * float(self.facteur_taille) * float(self.facteur_fiabilite) * float(self.facteur_charge_fatigue) * float(self.facteur_temperature_fatigue)
            rapport["fatigue"] = {
                "sigma_max_nominale_pa": smax,
                "sigma_min_nominale_pa": smin,
                "sigma_moyenne_locale_pa": sigma_m_loc,
                "sigma_alternee_locale_pa": sigma_a_loc,
                "rapport_R": rapport["cycle_charge"].get("rapport_R"),
                "Kt": Kt,
                "limite_endurance_corrigee_pa": Se_corr,
                "resistance_traction_pa": Rm,
                "limite_elastique_pa": Re,
            }
            if Se_corr is not None and Rm is not None:
                ug = _goodman_utilisation(sigma_a_loc, sigma_m_loc, Se_corr, Rm)
                rapport["fatigue"]["goodman"] = {"utilisation": ug, "ok": ug <= 1.0}
                rapport["fatigue"]["gerber"] = {"utilisation": _gerber_utilisation(sigma_a_loc, sigma_m_loc, Se_corr, Rm)}
            else:
                _push_inconnue(rapport, "partielles", "fatigue_goodman_gerber", "Nécessite limite_endurance et résistance à la traction.")
            if Se_corr is not None and Re is not None:
                us = _soderberg_utilisation(sigma_a_loc, sigma_m_loc, Se_corr, Re)
                rapport["fatigue"]["soderberg"] = {"utilisation": us, "ok": us <= 1.0}
            else:
                _push_inconnue(rapport, "partielles", "fatigue_soderberg", "Nécessite limite_endurance et limite élastique.")
        else:
            _push_inconnue(rapport, "partielles", "fatigue_bielle", "Calculable si section du fût, cycle de charge et matériau réel avec endurance sont connus.")

        # ---------------------------------------------------------------------
        # 7) Flambage Euler
        # ---------------------------------------------------------------------
        if Imin is not None and E is not None and L is not None and self.K_flambage is not None:
            K = _req_pos("K_flambage", self.K_flambage)
            Pcr = _euler_pcrit(float(E), float(Imin), float(L), float(K))
            marge_flamb = (Pcr / abs(float(Fmax))) if (Fmax is not None and float(Fmax) != 0.0) else None
            rapport["flambage"] = {
                "modele": "Euler (colonne équivalente)",
                "inertie_min_fut_m4": Imin,
                "module_young_pa": E,
                "longueur_bielle_m": L,
                "K_flambage": K,
                "charge_critique_N": Pcr,
                "marge_sur_Fmax": marge_flamb,
            }
            if A is not None:
                Ix = self.inertie_plan_fort_fut_m4 if self.inertie_plan_fort_fut_m4 is not None else rapport["geometrie"]["fut"].get("Ix_m4", Imin)
                Iy = self.inertie_plan_faible_fut_m4 if self.inertie_plan_faible_fut_m4 is not None else rapport["geometrie"]["fut"].get("Iy_m4", Imin)
                Kfort = self.K_flambage_plan_fort if self.K_flambage_plan_fort is not None else self.K_flambage
                Kfaible = self.K_flambage_plan_faible if self.K_flambage_plan_faible is not None else self.K_flambage
                if Ix is not None and Kfort is not None:
                    rapport["flambage_detaille"]["plan_fort"] = _euler_flambage_detaille(float(E), float(Ix), float(A), float(L), float(Kfort), Re)
                if Iy is not None and Kfaible is not None:
                    rapport["flambage_detaille"]["plan_faible"] = _euler_flambage_detaille(float(E), float(Iy), float(A), float(L), float(Kfaible), Re)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "flambage",
                "Calculable si inertie_min_fut_m4, module_young_pa, longueur_bielle_m et K_flambage sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 8) Contacts têtes
        # ---------------------------------------------------------------------
        rpm_eff = _req_pos("rpm", self.rpm, strictly=False) if self.rpm is not None else None

        if Fmax is not None and d_axe is not None and Lp is not None:
            p = abs(float(Fmax)) / (float(d_axe) * float(Lp))
            ok = None
            marge = None
            if self.pression_admissible_petite_tete_pa is not None:
                padm = _req_pos("pression_admissible_petite_tete_pa", self.pression_admissible_petite_tete_pa)
                ok = p <= (padm / FS)
                marge = (padm / FS) / p if p > 0.0 else None
            rapport["contacts_tetes"]["petite_tete"] = {
                "diametre_axe_m": d_axe,
                "longueur_portee_m": Lp,
                "pression_moyenne_pa": p,
                "pression_admissible_pa": self.pression_admissible_petite_tete_pa,
                "ok": ok,
                "marge": marge,
            }
            aff = {"ecrasement_local_pa": p, "pression_fond_oeil_pa": p}
            if self.pression_matage_admissible_petite_tete_pa is not None:
                pm = _req_pos("pression_matage_admissible_petite_tete_pa", self.pression_matage_admissible_petite_tete_pa)
                aff["matage"] = {"ok": p <= pm / FS, "marge": (pm / FS) / p if p > 0.0 else None}
            if self.vitesse_glissement_petite_tete_m_s is not None:
                v = _req_pos("vitesse_glissement_petite_tete_m_s", self.vitesse_glissement_petite_tete_m_s, strictly=False)
                aff["vitesse_glissement_m_s"] = v
                aff["PV_pa_m_s"] = _pv_palier(p, v)
                if self.pv_admissible_petite_tete_pa_m_s is not None:
                    pv_adm = _req_pos("pv_admissible_petite_tete_pa_m_s", self.pv_admissible_petite_tete_pa_m_s)
                    aff["PV_ok"] = aff["PV_pa_m_s"] <= pv_adm / FS
            if E is not None and ep_rad_pt is not None and larg_ext_pt is not None:
                aff.update(_deformation_annulaire_simplifiee(abs(float(Fmax)), float(E), float(larg_ext_pt), float(ep_rad_pt), 0.5 * (float(d_axe) + float(ep_rad_pt))))
            if self.viscosite_huile_pa_s is not None and self.jeu_radial_petite_tete_m is not None and self.vitesse_glissement_petite_tete_m_s is not None:
                n = float(self.vitesse_glissement_petite_tete_m_s) / (math.pi * float(d_axe))
                aff["sommerfeld_simplifie"] = _sommerfeld_simplifie(float(self.viscosite_huile_pa_s), n, p, 0.5 * float(d_axe), float(self.jeu_radial_petite_tete_m))
            rapport["contacts_tetes_affines"]["petite_tete"] = aff
        else:
            _push_inconnue(rapport, "partielles", "contact_petite_tete", "Calculable si Fmax, d_axe et longueur_portee_petite_tete_m sont connus.")

        if Fmax is not None and d_maneton is not None and Lg is not None:
            p = abs(float(Fmax)) / (float(d_maneton) * float(Lg))
            ok = None
            marge = None
            if self.pression_admissible_grande_tete_pa is not None:
                padm = _req_pos("pression_admissible_grande_tete_pa", self.pression_admissible_grande_tete_pa)
                ok = p <= (padm / FS)
                marge = (padm / FS) / p if p > 0.0 else None
            rapport["contacts_tetes"]["grande_tete"] = {
                "diametre_maneton_m": d_maneton,
                "longueur_portee_m": Lg,
                "pression_moyenne_pa": p,
                "pression_admissible_pa": self.pression_admissible_grande_tete_pa,
                "ok": ok,
                "marge": marge,
            }
            aff = {"ecrasement_local_pa": p, "pression_fond_oeil_pa": p}
            if self.pression_matage_admissible_grande_tete_pa is not None:
                pm = _req_pos("pression_matage_admissible_grande_tete_pa", self.pression_matage_admissible_grande_tete_pa)
                aff["matage"] = {"ok": p <= pm / FS, "marge": (pm / FS) / p if p > 0.0 else None}
            v = self.vitesse_glissement_grande_tete_m_s
            if v is None and rpm_eff is not None:
                v = math.pi * float(d_maneton) * float(rpm_eff) / 60.0
                rapport["notes_modele"].append("vitesse_glissement_grande_tete_m_s déduite via π*d_maneton*rpm/60.")
            if v is not None:
                aff["vitesse_glissement_m_s"] = v
                aff["PV_pa_m_s"] = _pv_palier(p, v)
                if self.pv_admissible_grande_tete_pa_m_s is not None:
                    pv_adm = _req_pos("pv_admissible_grande_tete_pa_m_s", self.pv_admissible_grande_tete_pa_m_s)
                    aff["PV_ok"] = aff["PV_pa_m_s"] <= pv_adm / FS
            if E is not None and ep_rad_gt is not None and larg_ext_gt is not None:
                aff.update(_deformation_annulaire_simplifiee(abs(float(Fmax)), float(E), float(larg_ext_gt), float(ep_rad_gt), 0.5 * (float(d_maneton) + float(ep_rad_gt))))
            if self.viscosite_huile_pa_s is not None and self.jeu_radial_grande_tete_m is not None and v is not None:
                n = (float(rpm_eff) / 60.0) if rpm_eff is not None else (float(v) / (math.pi * float(d_maneton)))
                aff["sommerfeld_simplifie"] = _sommerfeld_simplifie(float(self.viscosite_huile_pa_s), n, p, 0.5 * float(d_maneton), float(self.jeu_radial_grande_tete_m))
            rapport["contacts_tetes_affines"]["grande_tete"] = aff
        else:
            _push_inconnue(rapport, "partielles", "contact_grande_tete", "Calculable si Fmax, d_maneton et longueur_portee_grande_tete_m sont connus.")

        # ---------------------------------------------------------------------
        # 9) Masse du fût
        # ---------------------------------------------------------------------
        if rho is not None and A is not None and L is not None:
            V_fut = float(A) * float(L)
            m_fut = float(rho) * V_fut
            rapport["masse"] = {
                "modele": "m = rho * section_fut * longueur_bielle (fût seul, têtes non modélisées)",
                "volume_fut_m3": V_fut,
                "masse_fut_kg": m_fut,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse_fut",
                "Calculable si densité, section et longueur_bielle_m sont connues.",
            )

        # ---------------------------------------------------------------------
        # 10) Définition CAO des têtes (si possible)
        # ---------------------------------------------------------------------
        ep_rad_pt = self.epaisseur_radiale_petite_tete_m
        ep_rad_gt = self.epaisseur_radiale_grande_tete_m

        if ep_rad_pt is not None:
            ep_rad_pt = _req_pos("epaisseur_radiale_petite_tete_m", ep_rad_pt)
        elif d_axe is not None:
            ep_rad_pt = self.regles_fabrication.epaisseur_radiale_tete_min_m

        if ep_rad_gt is not None:
            ep_rad_gt = _req_pos("epaisseur_radiale_grande_tete_m", ep_rad_gt)
        elif d_maneton is not None:
            ep_rad_gt = self.regles_fabrication.epaisseur_radiale_tete_min_m

        Dext_pt = (d_axe + 2.0 * ep_rad_pt) if (d_axe is not None and ep_rad_pt is not None) else None
        Dext_gt = (d_maneton + 2.0 * ep_rad_gt) if (d_maneton is not None and ep_rad_gt is not None) else None

        larg_ext_pt = self.largeur_exterieure_petite_tete_m
        if larg_ext_pt is None and Lp is not None:
            larg_ext_pt = Lp + self.regles_fabrication.largeur_tete_marge_sur_portee_m
        elif larg_ext_pt is not None:
            larg_ext_pt = _req_pos("largeur_exterieure_petite_tete_m", larg_ext_pt)

        larg_ext_gt = self.largeur_exterieure_grande_tete_m
        if larg_ext_gt is None and Lg is not None:
            larg_ext_gt = Lg + self.regles_fabrication.largeur_tete_marge_sur_portee_m
        elif larg_ext_gt is not None:
            larg_ext_gt = _req_pos("largeur_exterieure_grande_tete_m", larg_ext_gt)

        # ---------------------------------------------------------------------
        # 11) Bloc CAO
        # ---------------------------------------------------------------------
        chanfrein_fut = None
        rayon_conge = None
        if h_fut is not None:
            chanfrein_fut = _borne(
                self.regles_fabrication.ratio_chanfrein_sur_epaisseur * h_fut,
                self.regles_fabrication.chanfrein_min_m,
                self.regles_fabrication.chanfrein_max_m,
            )
            rayon_conge = _borne(
                self.regles_fabrication.ratio_conge_sur_epaisseur_fut * h_fut,
                self.regles_fabrication.rayon_conge_min_m,
                self.regles_fabrication.rayon_conge_max_m,
            )
        elif d_eq is not None:
            chanfrein_fut = _borne(
                self.regles_fabrication.ratio_chanfrein_sur_epaisseur * d_eq,
                self.regles_fabrication.chanfrein_min_m,
                self.regles_fabrication.chanfrein_max_m,
            )
            rayon_conge = _borne(
                self.regles_fabrication.ratio_conge_sur_epaisseur_fut * d_eq,
                self.regles_fabrication.rayon_conge_min_m,
                self.regles_fabrication.rayon_conge_max_m,
            )

        if L is not None:
            # Convention de dessin : origine au centre petite tête, axe longitudinal = X
            x_centre_petite = 0.0
            x_centre_grande = float(L)
        else:
            x_centre_petite = None
            x_centre_grande = None

        # Longueur droite approximative du fût entre tangences des têtes
        longueur_fut_droite = None
        if L is not None and Dext_pt is not None and Dext_gt is not None:
            longueur_fut_droite = float(L) - 0.5 * Dext_pt - 0.5 * Dext_gt
            if longueur_fut_droite < 0.0:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "CAO_bielle",
                    "Les diamètres extérieurs de têtes sont incompatibles avec la longueur de bielle.",
                )

        rapport["cao"] = {
            "type_piece": "bielle",
            "forme_fut": self.forme_fut,
            "entraxe_centres_m": L,
            "centre_petite_tete_x_m": x_centre_petite,
            "centre_grande_tete_x_m": x_centre_grande,
            "longueur_fut_droite_approx_m": longueur_fut_droite,
            "fut": {
                "modele_section": modele_section,
                "largeur_m": b_fut,
                "epaisseur_m": h_fut,
                "section_m2": A,
                "diametre_equivalent_m": d_eq,
                "chanfrein_m": chanfrein_fut,
                "rayon_conge_tete_fut_m": rayon_conge,
                "rugosite_ra_um": self.regles_fabrication.rugosite_fut_ra_um,
                "tolerance_m": self.regles_fabrication.tolerance_fut_m,
            },
            "petite_tete": {
                "forme": "circulaire" if d_axe is not None else "non_definie",
                "diametre_alésage_m": d_axe,
                "diametre_exterieur_m": Dext_pt,
                "largeur_portee_m": Lp,
                "largeur_exterieure_m": larg_ext_pt,
                "epaisseur_radiale_m": ep_rad_pt,
                "centre_x_m": x_centre_petite,
                "rugosite_alésage_ra_um": self.regles_fabrication.rugosite_alésages_tetes_ra_um,
                "tolerance_diametre_alésage_m": self.regles_fabrication.tolerance_diametre_alésage_m,
                "tolerance_largeur_m": self.regles_fabrication.tolerance_largeur_tete_m,
            },
            "grande_tete": {
                "forme": "circulaire" if d_maneton is not None else "non_definie",
                "diametre_alésage_m": d_maneton,
                "diametre_exterieur_m": Dext_gt,
                "largeur_portee_m": Lg,
                "largeur_exterieure_m": larg_ext_gt,
                "epaisseur_radiale_m": ep_rad_gt,
                "centre_x_m": x_centre_grande,
                "rugosite_alésage_ra_um": self.regles_fabrication.rugosite_alésages_tetes_ra_um,
                "tolerance_diametre_alésage_m": self.regles_fabrication.tolerance_diametre_alésage_m,
                "tolerance_largeur_m": self.regles_fabrication.tolerance_largeur_tete_m,
            },
            "tolerances_globales": {
                "tolerance_longueur_m": self.regles_fabrication.tolerance_longueur_m,
            },
        }

        # ---------------------------------------------------------------------
        # 12) Trace entrées
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "longueur_bielle_m": self.longueur_bielle_m,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "resistance_traction_pa": self.resistance_traction_pa,
            "limite_endurance_pa": self.limite_endurance_pa,
            "coefficient_entaille_Kt": self.coefficient_entaille_Kt,
            "facteur_surface": self.facteur_surface,
            "facteur_taille": self.facteur_taille,
            "facteur_fiabilite": self.facteur_fiabilite,
            "facteur_charge_fatigue": self.facteur_charge_fatigue,
            "facteur_temperature_fatigue": self.facteur_temperature_fatigue,
            "facteur_securite": self.facteur_securite,
            "K_flambage": self.K_flambage,
            "K_flambage_plan_fort": self.K_flambage_plan_fort,
            "K_flambage_plan_faible": self.K_flambage_plan_faible,
            "inertie_plan_fort_fut_m4": self.inertie_plan_fort_fut_m4,
            "inertie_plan_faible_fut_m4": self.inertie_plan_faible_fut_m4,
            "force_axiale_max_N": self.force_axiale_max_N,
            "force_axiale_min_N": self.force_axiale_min_N,
            "force_axiale_max_tension_N": self.force_axiale_max_tension_N,
            "force_axiale_max_compression_N": self.force_axiale_max_compression_N,
            "effort_lateral_max_N": self.effort_lateral_max_N,
            "rpm": self.rpm,
            "diametre_equivalent_fut_m": self.diametre_equivalent_fut_m,
            "largeur_fut_m": self.largeur_fut_m,
            "epaisseur_fut_m": self.epaisseur_fut_m,
            "section_fut_m2": self.section_fut_m2,
            "inertie_min_fut_m4": self.inertie_min_fut_m4,
            "ratio_largeur_sur_epaisseur": self.ratio_largeur_sur_epaisseur,
            "forme_fut": self.forme_fut,
            "diametre_axe_piston_m": self.diametre_axe_piston_m,
            "longueur_portee_petite_tete_m": self.longueur_portee_petite_tete_m,
            "pression_admissible_petite_tete_pa": self.pression_admissible_petite_tete_pa,
            "diametre_maneton_m": self.diametre_maneton_m,
            "longueur_portee_grande_tete_m": self.longueur_portee_grande_tete_m,
            "pression_admissible_grande_tete_pa": self.pression_admissible_grande_tete_pa,
            "epaisseur_radiale_petite_tete_m": self.epaisseur_radiale_petite_tete_m,
            "epaisseur_radiale_grande_tete_m": self.epaisseur_radiale_grande_tete_m,
            "largeur_exterieure_petite_tete_m": self.largeur_exterieure_petite_tete_m,
            "largeur_exterieure_grande_tete_m": self.largeur_exterieure_grande_tete_m,
            "pression_matage_admissible_petite_tete_pa": self.pression_matage_admissible_petite_tete_pa,
            "pression_matage_admissible_grande_tete_pa": self.pression_matage_admissible_grande_tete_pa,
            "pv_admissible_petite_tete_pa_m_s": self.pv_admissible_petite_tete_pa_m_s,
            "pv_admissible_grande_tete_pa_m_s": self.pv_admissible_grande_tete_pa_m_s,
            "vitesse_glissement_petite_tete_m_s": self.vitesse_glissement_petite_tete_m_s,
            "vitesse_glissement_grande_tete_m_s": self.vitesse_glissement_grande_tete_m_s,
            "viscosite_huile_pa_s": self.viscosite_huile_pa_s,
            "jeu_radial_petite_tete_m": self.jeu_radial_petite_tete_m,
            "jeu_radial_grande_tete_m": self.jeu_radial_grande_tete_m,
        }

        _ajouter_champs_metier_definition_bielle(rapport)
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CorpsBielle(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        ajouter_dossier_definition_solidworks(rapport, "bielle")
        return rapport


# =============================================================================
# Exemple minimal
# =============================================================================
if __name__ == "__main__":
    try:
        from backend.components.moteur_thermique.pieces.arbre_piston import ArbrePiston  # type: ignore
        arbre = ArbrePiston(
            diametre_portee_coussinet_m=0.020,
        )
    except Exception:
        arbre = None

    b = CorpsBielle(
        arbre_piston=arbre,
        longueur_bielle_m=0.140,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        densite_kg_m3=7800.0,
        facteur_securite=2.0,
        K_flambage=1.0,
        force_axiale_max_N=15000.0,
        forme_fut="rectangle",
        ratio_largeur_sur_epaisseur=2.0,
        longueur_portee_petite_tete_m=0.018,
        diametre_maneton_m=0.030,
        longueur_portee_grande_tete_m=0.020,
    )

    from pprint import pprint
    pprint(b.calculer(strict=False))
