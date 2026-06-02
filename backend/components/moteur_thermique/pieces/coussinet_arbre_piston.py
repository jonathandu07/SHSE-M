# backend/components/moteur_thermique/pieces/coussinet_arbre_piston.py
# =============================================================================
# COUSSINET ARBRE-PISTON — SHSE-M
# =============================================================================
# Rôle :
# - Palier lisse (coussinet) entre l’arbre de piston et la bielle / tête de bielle.
#
# Objectif :
# - Calculer tout ce qui est calculable sans invention :
#   * pression projetée,
#   * vitesse de glissement,
#   * PV,
#   * puissance de frottement,
#   * nombre de Sommerfeld si les données hydrodynamiques existent,
#   * résistance thermique radiale,
#   * masse,
#   * longueur minimale L si limites tribologiques fournies,
#   * bloc "cao" exploitable pour le dessin manuel / SolidWorks.
#
# Principe :
# - aucun standard ni aucune valeur tribologique cachée ne sont choisis à ta place,
# - si une donnée manque, elle est signalée dans "inconnues",
# - si un arbre de piston est fourni, on récupère ce qu’on peut depuis ses attributs
#   ou depuis arbre_piston.analyser().
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List, Literal, Iterable

from backend.modules.systeme.dossier_definition import ajouter_dossier_definition_solidworks
import math


# =============================================================================
# Utilitaires
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _omega_rad_s(rpm: float) -> float:
    return 2.0 * math.pi * (_req_pos("rpm", rpm, strictly=False) / 60.0)


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

    rapport["inconnues"]["impossibles"] = dedup(
        list(rapport["inconnues"].get("impossibles", []) or [])
    )
    rapport["inconnues"]["partielles"] = dedup(
        list(rapport["inconnues"].get("partielles", []) or [])
    )


def _cap_section(rapport: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = rapport.get(key, {})
    return value if isinstance(value, dict) else {}


def _status_coussinet(*values: Any) -> str:
    return "ok" if all(v is not None for v in values) else "partial"


def _missing_tolerance_coussinet(nom: str, type_: str, raison: str) -> Dict[str, Any]:
    return {"nom": nom, "type": type_, "valeur": None, "statut": "missing", "raison": raison}


def _ajouter_champs_metier_definition_coussinet(rapport: Dict[str, Any]) -> None:
    geo = _cap_section(rapport, "geometrie")
    cin = _cap_section(rapport, "cinematique")
    pressions = _cap_section(rapport, "pressions")
    pv = _cap_section(rapport, "pv")
    frottement = _cap_section(rapport, "frottement")
    thermique = _cap_section(rapport, "thermique")
    hydro = _cap_section(rapport, "hydrodynamique")
    dimensionnement = _cap_section(rapport, "dimensionnement")
    tribologie = _cap_section(rapport, "tribologie")
    efforts = _cap_section(rapport, "efforts")
    cao = _cap_section(rapport, "cao")

    d_int = geo.get("diametre_portee_m") or cao.get("diametre_interieur_nominal_m")
    d_ext = geo.get("diametre_exterieur_m") or cao.get("diametre_exterieur_nominal_m")
    longueur = geo.get("longueur_coussinet_m") or cao.get("longueur_nominale_m")
    jeu = geo.get("jeu_radial_m") or cao.get("jeu_radial_m")

    rapport.setdefault("piece", "coussinet_arbre_piston")
    rapport["surfaces_fonctionnelles"] = [
        {"nom": "diametre_interieur", "fonction": "surface de glissement sur arbre_piston", "cote_associee": "diametre_portee_m", "valeur_associee": d_int, "risque": "pression/vitesse non verifiables sans diametre interieur", "controle_recommande": "diametre interieur, circularite et rugosite"},
        {"nom": "diametre_exterieur", "fonction": "interface logement bielle", "cote_associee": "diametre_exterieur_m", "valeur_associee": d_ext, "risque": "ajustement logement non defini", "controle_recommande": "diametre exterieur et circularite"},
        {"nom": "longueur", "fonction": "largeur portante projetee", "cote_associee": "longueur_coussinet_m", "valeur_associee": longueur, "risque": "pression projetee non calculable sans longueur", "controle_recommande": "longueur et faces d'appui"},
        {"nom": "surface_glissement", "fonction": "contact tribologique arbre/coussinet", "cote_associee": "pression_projetee_pa / vitesse_glissement_m_s", "valeur_associee": {"pression_projetee_pa": pressions.get("pression_projetee_pa"), "vitesse_glissement_m_s": cin.get("vitesse_glissement_m_s")}, "risque": "PV/frottement non valides", "controle_recommande": "rugosite, jeu, lubrification"},
        {"nom": "faces_appui", "fonction": "reprise axiale et positionnement", "cote_associee": "longueur_coussinet_m", "valeur_associee": longueur, "risque": "positionnement axial incomplet", "controle_recommande": "parallelisme et perpendicularite faces"},
    ]
    rapport["interfaces_assemblage"] = [
        {"piece_a": "coussinet_arbre_piston", "piece_b": "arbre_piston", "fonction": "guidage tribologique de l'arbre", "type_liaison": "palier lisse", "cote_interface": d_int, "jeu_ou_serrage": jeu, "tolerance": cao.get("tolerance_diametre_interieur_m"), "effort_transmis": efforts.get("charge_radiale_N"), "risque": "jeu, rugosite ou lubrification non valides", "statut": _status_coussinet(d_int, longueur)},
        {"piece_a": "coussinet_arbre_piston", "piece_b": "bielle", "fonction": "logement du coussinet", "type_liaison": "emmanchement/logement", "cote_interface": d_ext, "jeu_ou_serrage": None, "tolerance": cao.get("tolerance_diametre_exterieur_m"), "effort_transmis": efforts.get("charge_radiale_N"), "risque": "ajustement logement non fourni", "statut": _status_coussinet(d_ext)},
        {"piece_a": "coussinet_arbre_piston", "piece_b": "logement", "fonction": "portee externe dans la tete de bielle", "type_liaison": "portee cylindrique", "cote_interface": d_ext, "jeu_ou_serrage": None, "tolerance": cao.get("tolerance_diametre_exterieur_m"), "effort_transmis": efforts.get("charge_radiale_N"), "risque": "serrage/jeu logement a definir", "statut": "partial"},
    ]
    rapport["tolerances"] = [
        {"nom": "jeu_radial", "type": "fonctionnel", "valeur": jeu, "statut": "known" if jeu is not None else "missing", "source": "geometrie/cao"},
        {"nom": "diametre_interieur", "type": "diametral", "valeur": cao.get("tolerance_diametre_interieur_m"), "statut": "known" if cao.get("tolerance_diametre_interieur_m") is not None else "missing", "source": "cao.tolerance_diametre_interieur_m"},
        {"nom": "diametre_exterieur", "type": "diametral", "valeur": cao.get("tolerance_diametre_exterieur_m"), "statut": "known" if cao.get("tolerance_diametre_exterieur_m") is not None else "missing", "source": "cao.tolerance_diametre_exterieur_m"},
        {"nom": "etat_surface_interieur", "type": "etat_surface", "valeur": cao.get("rugosite_interieure_ra_um"), "statut": "known" if cao.get("rugosite_interieure_ra_um") is not None else "missing", "source": "cao.rugosite_interieure_ra_um"},
        _missing_tolerance_coussinet("ajustement_logement", "ajustement", "a definir selon bielle/logement"),
        _missing_tolerance_coussinet("ajustement_arbre", "ajustement", "a definir selon arbre_piston et lubrification"),
    ]
    rapport["contraintes_rdm"] = [
        {"nom": "pression_projetee", "type": "pression_contact", "valeur": pressions.get("pression_projetee_pa"), "source": "pressions.pression_projetee_pa"},
        {"nom": "vitesse_glissement", "type": "cinematique", "valeur": cin.get("vitesse_glissement_m_s"), "source": "cinematique.vitesse_glissement_m_s"},
        {"nom": "PV", "type": "tribologie", "valeur": pv.get("pv_W_m2"), "source": "pv.pv_W_m2"},
        {"nom": "frottement", "type": "frottement", "valeur": frottement.get("puissance_frottement_W"), "source": "frottement.puissance_frottement_W"},
        {"nom": "echauffement", "type": "thermique", "valeur": thermique, "source": "thermique"},
        {"nom": "sommerfeld", "type": "hydrodynamique", "valeur": hydro.get("sommerfeld_S"), "source": "hydrodynamique.sommerfeld_S"},
    ]
    rapport["limites_usage"] = [
        {"nom": "pression_admissible", "valeur": pressions.get("pression_admissible_effective_pa") or pressions.get("pression_admissible_pa"), "unite": "Pa", "condition_non_conformite": "pression projetee superieure a pression admissible"},
        {"nom": "PV_limite", "valeur": pv.get("pv_admissible_effective_W_m2") or pv.get("pv_admissible_W_m2"), "unite": "W/m2", "condition_non_conformite": "PV superieur a la limite fournie"},
        {"nom": "vitesse_glissement", "valeur": cin.get("vitesse_glissement_m_s"), "unite": "m/s", "condition_non_conformite": "vitesse superieure a limite utilisateur"},
        {"nom": "temperature", "valeur": thermique.get("R_conduction_K_W"), "condition_non_conformite": "echauffement non valide sans bilan thermique"},
        {"nom": "limite_tribologique", "valeur": {"pression": pressions.get("marge_pression"), "pv": pv.get("marge_pv")}, "condition_non_conformite": "marge pression ou PV <= 1"},
    ]
    rapport["controles_qualite"] = [
        {"nom": "diametre_interieur", "type": "cote", "cote": d_int, "controle": "diametre interieur et circularite"},
        {"nom": "diametre_exterieur", "type": "cote", "cote": d_ext, "controle": "diametre exterieur et circularite"},
        {"nom": "longueur", "type": "cote", "cote": longueur, "controle": "longueur et perpendicularite faces"},
        {"nom": "rugosite", "type": "etat_surface", "cote": cao.get("rugosite_interieure_ra_um"), "controle": "rugosite surface de glissement"},
        {"nom": "jeu", "type": "fonctionnel", "cote": jeu, "controle": "mesure jeu radial assemble"},
    ]
    rapport["notes_modelisation"] = [
        {"nom": "bague_cylindrique", "texte": "Modeliser comme bague cylindrique uniquement si diametres et longueur sont disponibles."},
        {"nom": "surface_glissement", "texte": "Nommer la surface de glissement interieure et les faces d'appui."},
        {"nom": "jeu_parametrique", "texte": "Garder le jeu radial parametrique ; ne pas choisir d'ajustement sans donnee backend."},
        {"nom": "diametres_distincts", "texte": "Distinguer diametre interieur arbre_piston et diametre exterieur logement."},
        {"nom": "pas_de_reference", "texte": "Aucune reference catalogue ni materiau de coussinet n'est choisi automatiquement."},
        {"nom": "pas_export_step", "texte": "Dossier de modelisation manuelle uniquement ; aucun export STEP n'est genere."},
    ]


def _aire_disque(d: float) -> float:
    d_v = _req_pos("d", d)
    return math.pi * (0.5 * d_v) ** 2


def _perimetre(d: float) -> float:
    return math.pi * _req_pos("d", d)


def _iter_floats(xs: Iterable[Any]) -> List[float]:
    out: List[float] = []
    for x in xs:
        if _is_finite(x):
            out.append(float(x))
    return out


def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


# =============================================================================
# Résolution matériau (optionnelle via backend/ensemble/materiaux.py)
# =============================================================================

def _resoudre_materiau(
    cle: Optional[str],
    densite_kg_m3: Optional[float],
    k_therm_w_m_k: Optional[float],
    limite_pression_pa: Optional[float],
    *,
    mode_valeur: str = "typique",
) -> Dict[str, Optional[float]]:
    """
    Essaie de compléter densité, conductivité thermique, pression admissible via
    une DB matériaux. Rien n'est inventé si les champs n'existent pas.
    """
    rho = densite_kg_m3
    k = k_therm_w_m_k
    p_adm = limite_pression_pa

    if cle:
        for modname in (
            "backend.ensemble.materiaux",
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                get_materiau = getattr(mod, "get_materiau", None)
                valeur = getattr(mod, "valeur", None)

                mat = None
                if callable(get_materiau):
                    mat = get_materiau(cle)
                else:
                    mats = getattr(mod, "MATERIAUX", None)
                    if isinstance(mats, dict):
                        mat = mats.get(cle)

                if mat is None:
                    continue

                def vprop(obj: Any, *names: str) -> Optional[float]:
                    for n in names:
                        raw = None
                        if isinstance(obj, dict) and n in obj:
                            raw = obj.get(n)
                        else:
                            raw = getattr(obj, n, None)
                        if raw is None:
                            continue

                        if callable(valeur):
                            try:
                                vv = valeur(raw, mode=mode_valeur)  # type: ignore[misc]
                                if vv is not None and _is_finite(vv):
                                    return float(vv)
                            except Exception:
                                pass

                        if _is_finite(raw):
                            return float(raw)
                    return None

                rho = rho if rho is not None else vprop(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                k = k if k is not None else vprop(
                    mat,
                    "conductivite_thermique_w_mk",
                    "conductivite_w_m_k",
                    "k_w_m_k",
                    "lambda_w_m_k",
                )
                p_adm = p_adm if p_adm is not None else vprop(
                    mat,
                    "pression_admissible_pa",
                    "p_admissible_pa",
                    "bearing_pressure_pa",
                )
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "conductivite_w_m_k": k,
        "pression_admissible_pa": p_adm,
    }


# =============================================================================
# Déductions depuis arbre_piston
# =============================================================================

def _extraire_depuis_rapport_arbre_piston(r: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait des candidats pour :
    - d (diamètre de portée coussinet),
    - L (longueur coussinet),
    - W (charge radiale approx.),
    - rpm
    depuis un rapport arbre_piston.analyser().
    """
    out: Dict[str, Any] = {
        "d_unique_m": None,
        "d_candidates_m": [],
        "L_m": None,
        "W_N": None,
        "rpm": None,
        "notes": [],
    }

    if not isinstance(r, dict):
        return out

    ent = r.get("entrees", {}) if isinstance(r.get("entrees", {}), dict) else {}
    eff = r.get("efforts", {}) if isinstance(r.get("efforts", {}), dict) else {}
    geo = r.get("geometrie", {}) if isinstance(r.get("geometrie", {}), dict) else {}
    cin = r.get("cinematique", {}) if isinstance(r.get("cinematique", {}), dict) else {}
    cao = r.get("cao", {}) if isinstance(r.get("cao", {}), dict) else {}

    # Diamètre portée coussinet explicite
    for src_name, src in (
        ("entrees.diametre_portee_coussinet_m", ent.get("diametre_portee_coussinet_m")),
        ("geometrie.diametre_portee_coussinet_m", geo.get("diametre_portee_coussinet_m")),
    ):
        if out["d_unique_m"] is None and _is_finite(src):
            out["d_unique_m"] = float(src)
            out["notes"].append(f"d déduit de arbre_piston.{src_name}")

    # Longueur coussinet explicite
    for src_name, src in (
        ("entrees.longueur_coussinet_m", ent.get("longueur_coussinet_m")),
        ("geometrie.longueur_coussinet_m", geo.get("longueur_coussinet_m")),
    ):
        if out["L_m"] is None and _is_finite(src):
            out["L_m"] = float(src)
            out["notes"].append(f"L déduite de arbre_piston.{src_name}")

    # Charge radiale approx
    for src_name, src in (
        ("efforts.force_cisaillement_N", eff.get("force_cisaillement_N")),
        ("efforts.force_radiale_N", eff.get("force_radiale_N")),
    ):
        if out["W_N"] is None and _is_finite(src):
            out["W_N"] = float(src)
            out["notes"].append(f"W approx. déduite de arbre_piston.{src_name}")

    # rpm
    for src_name, src in (
        ("cinematique.rpm", cin.get("rpm")),
        ("entrees.rpm", ent.get("rpm")),
    ):
        if out["rpm"] is None and _is_finite(src):
            out["rpm"] = float(src)
            out["notes"].append(f"rpm déduit de arbre_piston.{src_name}")

    # Si d non explicite : tenter bloc cao
    if out["d_unique_m"] is None and isinstance(cao, dict):
        tg = cao.get("teton_gauche", {})
        td = cao.get("teton_droit", {})
        for src_name, src in (
            ("cao.teton_gauche.diametre_m", tg.get("diametre_m") if isinstance(tg, dict) else None),
            ("cao.teton_droit.diametre_m", td.get("diametre_m") if isinstance(td, dict) else None),
        ):
            if _is_finite(src):
                out["d_candidates_m"].append(float(src))
                out["notes"].append(f"d candidat extrait de arbre_piston.{src_name}")

    # Si toujours rien : tenter dimensionnement_evide
    if out["d_unique_m"] is None:
        dim = r.get("dimensionnement_evide", {}) if isinstance(r.get("dimensionnement_evide", {}), dict) else {}
        res = dim.get("resultat_unique") if isinstance(dim.get("resultat_unique"), dict) else None
        if isinstance(res, dict):
            # cas Do_m direct
            if _is_finite(res.get("Do_m")):
                out["d_unique_m"] = float(res["Do_m"])
                out["notes"].append("d déduit de arbre_piston.dimensionnement_evide.resultat_unique.Do_m")
            else:
                # cas critere_vm / critere_tresca
                for nom in ("critere_vm", "critere_tresca"):
                    rr = res.get(nom)
                    if isinstance(rr, dict) and _is_finite(rr.get("Do_min_m")):
                        out["d_candidates_m"].append(float(rr["Do_min_m"]))
                        out["notes"].append(f"d candidat extrait de arbre_piston.dimensionnement_evide.resultat_unique.{nom}.Do_min_m")

        sc = dim.get("scenarios") if isinstance(dim.get("scenarios"), dict) else None
        if isinstance(sc, dict):
            for nom in ("critere_vm", "critere_tresca"):
                lst = sc.get(nom)
                if isinstance(lst, list):
                    for it in lst:
                        if isinstance(it, dict) and _is_finite(it.get("Do_min_m")):
                            out["d_candidates_m"].append(float(it["Do_min_m"]))

    out["d_candidates_m"] = sorted(set(_iter_floats(out["d_candidates_m"])))
    out["notes"] = list(dict.fromkeys(out["notes"]))
    return out


def _extraire_depuis_objet_arbre_piston(obj: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "d_unique_m": None,
        "d_candidates_m": [],
        "L_m": None,
        "W_N": None,
        "rpm": None,
        "notes": [],
    }

    try:
        if _is_finite(getattr(obj, "diametre_portee_coussinet_m", None)):
            out["d_unique_m"] = float(getattr(obj, "diametre_portee_coussinet_m"))
            out["notes"].append("d déduit de arbre_piston.diametre_portee_coussinet_m")

        if _is_finite(getattr(obj, "longueur_coussinet_m", None)):
            out["L_m"] = float(getattr(obj, "longueur_coussinet_m"))
            out["notes"].append("L déduite de arbre_piston.longueur_coussinet_m")

        if _is_finite(getattr(obj, "force_cisaillement_N", None)):
            out["W_N"] = float(getattr(obj, "force_cisaillement_N"))
            out["notes"].append("W approx. déduite de arbre_piston.force_cisaillement_N")

        if _is_finite(getattr(obj, "rpm", None)):
            out["rpm"] = float(getattr(obj, "rpm"))
            out["notes"].append("rpm déduit de arbre_piston.rpm")
    except Exception:
        pass

    if hasattr(obj, "analyser") and callable(getattr(obj, "analyser")):
        try:
            r = obj.analyser(strict=False)  # type: ignore[misc]
            ext = _extraire_depuis_rapport_arbre_piston(r if isinstance(r, dict) else {})
            for k in ("d_unique_m", "L_m", "W_N", "rpm"):
                out[k] = out[k] if out[k] is not None else ext.get(k)
            out["d_candidates_m"] = out["d_candidates_m"] or ext.get("d_candidates_m", [])
            out["notes"].extend(ext.get("notes", []))
        except Exception:
            out["notes"].append("Impossible d'extraire via arbre_piston.analyser()")

    out["d_candidates_m"] = sorted(set(_iter_floats(out["d_candidates_m"])))
    out["notes"] = list(dict.fromkeys(out["notes"]))
    return out


# =============================================================================
# Règles explicites CAO / fabrication
# =============================================================================

@dataclass(frozen=True)
class ReglesFabricationCoussinetArbrePiston:
    # Si L absente mais dimensionnable, on ne l’impose pas silencieusement.
    # En revanche, pour bloc CAO, on peut proposer une valeur déduite de L_min.
    surcote_longueur_fabrication_m: float = 0.0

    # Chanfreins / rayons
    chanfrein_min_m: float = 0.0003
    chanfrein_max_m: float = 0.0015
    ratio_chanfrein_sur_epaisseur: float = 0.25

    # Tolérances / rugosité
    rugosite_interieure_ra_um: float = 0.8
    rugosite_exterieure_ra_um: float = 1.6
    tolerance_diametre_interieur_m: float = 0.00002
    tolerance_diametre_exterieur_m: float = 0.00003
    tolerance_longueur_m: float = 0.00005


# =============================================================================
# Coussinet
# =============================================================================

LubrificationMode = Literal["inconnue", "sec", "huile", "eau", "autre"]


@dataclass
class CoussinetArbrePiston:
    """
    Coussinet lisse (journal bearing) pour arbre de piston.

    Dimensionnement minimal possible si on connaît :
    - W et rpm,
    - d ou des candidats d,
    - et au moins une limite parmi p_adm et PV_adm.

    Les dimensions nécessaires au dessin manuel / SolidWorks sont renvoyées
    dans rapport["cao"] quand elles sont calculables.
    """

    # Liens vers pièces
    arbre_piston: Optional[Any] = None

    # Géométrie
    diametre_portee_m: Optional[float] = None
    longueur_coussinet_m: Optional[float] = None
    epaisseur_coussinet_m: Optional[float] = None
    jeu_radial_m: Optional[float] = None
    excentricite_m: Optional[float] = None

    # Efforts
    charge_radiale_N: Optional[float] = None
    charge_axiale_N: Optional[float] = None

    # Cinématique
    rpm: Optional[float] = None

    # Tribologie
    coefficient_frottement: Optional[float] = None
    mode_lubrification: LubrificationMode = "inconnue"

    # Lubrifiant
    viscosite_Pa_s: Optional[float] = None
    temperature_lubrifiant_K: Optional[float] = None
    pression_lubrifiant_Pa: Optional[float] = None

    # Matériau coussinet
    materiau_coussinet: Optional[str] = None
    densite_coussinet_kg_m3: Optional[float] = None
    conductivite_coussinet_w_m_k: Optional[float] = None
    pression_admissible_pa: Optional[float] = None
    pv_admissible_W_m2: Optional[float] = None

    # Sécurité
    facteur_securite: float = 2.0

    # Règles CAO
    regles_fabrication: ReglesFabricationCoussinetArbrePiston = field(
        default_factory=ReglesFabricationCoussinetArbrePiston
    )

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "sources": {},
            "geometrie": {},
            "cinematique": {},
            "efforts": {},
            "tribologie": {},
            "dimensionnement": {},
            "pressions": {},
            "pv": {},
            "frottement": {},
            "hydrodynamique": {},
            "thermique": {},
            "masse": {},
            "cao": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ---------------------------------------------------------------------
        # 1) Matériau
        # ---------------------------------------------------------------------
        props_mat = _resoudre_materiau(
            self.materiau_coussinet,
            self.densite_coussinet_kg_m3,
            self.conductivite_coussinet_w_m_k,
            self.pression_admissible_pa,
            mode_valeur="typique",
        )
        rho_c = props_mat["densite_kg_m3"]
        k_c = props_mat["conductivite_w_m_k"]
        p_adm = props_mat["pression_admissible_pa"]

        # ---------------------------------------------------------------------
        # 2) Déductions depuis arbre_piston
        # ---------------------------------------------------------------------
        d = self.diametre_portee_m
        L = self.longueur_coussinet_m
        W = self.charge_radiale_N
        rpm = self.rpm
        d_candidates: List[float] = []

        if self.arbre_piston is not None:
            ext = _extraire_depuis_objet_arbre_piston(self.arbre_piston)

            if d is None and _is_finite(ext.get("d_unique_m")):
                d = float(ext["d_unique_m"])
                rapport["sources"]["diametre_portee_m"] = "arbre_piston"
            if not d_candidates:
                d_candidates = _iter_floats(ext.get("d_candidates_m", []))
                if d_candidates:
                    rapport["sources"]["diametre_portee_candidates_m"] = "arbre_piston"
            if L is None and _is_finite(ext.get("L_m")):
                L = float(ext["L_m"])
                rapport["sources"]["longueur_coussinet_m"] = "arbre_piston"
            if W is None and _is_finite(ext.get("W_N")):
                W = float(ext["W_N"])
                rapport["sources"]["charge_radiale_N"] = "arbre_piston"
            if rpm is None and _is_finite(ext.get("rpm")):
                rpm = float(ext["rpm"])
                rapport["sources"]["rpm"] = "arbre_piston"

            for n in ext.get("notes", []):
                rapport["notes_modele"].append(n)

        # ---------------------------------------------------------------------
        # 3) Validation de base
        # ---------------------------------------------------------------------
        if d is not None:
            d = _req_pos("diametre_portee_m", d)
            d_candidates = [d] + [x for x in d_candidates if x > 0.0 and abs(x - d) > 1e-12]
        d_candidates = sorted(set(_iter_floats(d_candidates)))

        if L is not None:
            L = _req_pos("longueur_coussinet_m", L)

        if self.epaisseur_coussinet_m is not None:
            e = _req_pos("epaisseur_coussinet_m", self.epaisseur_coussinet_m)
        else:
            e = None

        if self.jeu_radial_m is not None:
            c = _req_pos("jeu_radial_m", self.jeu_radial_m)
        else:
            c = None

        if W is not None:
            W = _req_pos("charge_radiale_N", W, strictly=False)
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "charge_radiale_N",
                "Indispensable pour pression, PV, frottement et dimensionnement.",
            )

        if rpm is not None:
            rpm = _req_pos("rpm", rpm, strictly=False)
            omega = _omega_rad_s(rpm)
        else:
            omega = None
            _push_inconnue(
                rapport,
                "partielles",
                "rpm",
                "Indispensable pour vitesse, PV, frottement et Sommerfeld.",
            )

        # ---------------------------------------------------------------------
        # 4) Dimensionnement minimal de L
        # ---------------------------------------------------------------------
        dim: Dict[str, Any] = {
            "p_allow_pa": None,
            "pv_allow_W_m2": None,
            "solutions": [],
            "notes": [],
        }

        p_allow = None
        if p_adm is not None and _is_finite(p_adm):
            p_allow = float(p_adm) / FS
            dim["p_allow_pa"] = p_allow
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pression_admissible_pa",
                "Dimensionnement pression possible si pression_admissible_pa est fournie.",
            )

        pv_allow = None
        if self.pv_admissible_W_m2 is not None:
            pv_allow = _req_pos("pv_admissible_W_m2", self.pv_admissible_W_m2) / FS
            dim["pv_allow_W_m2"] = pv_allow
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pv_admissible_W_m2",
                "Dimensionnement PV possible si pv_admissible_W_m2 est fournie.",
            )

        def calc_L_min_for_d(d_use: float) -> Dict[str, Any]:
            out: Dict[str, Any] = {
                "d_m": d_use,
                "L_min_m": None,
                "contraintes": {},
                "ok_avec_L": None,
                "L_actuel_m": L,
            }
            if W is None:
                return out

            Lmin_p = None
            if p_allow is not None and p_allow > 0.0:
                Lmin_p = W / (d_use * p_allow)
                out["contraintes"]["L_min_pression_m"] = Lmin_p

            Lmin_pv = None
            if pv_allow is not None and pv_allow > 0.0 and omega is not None:
                Lmin_pv = (W * abs(omega)) / (2.0 * pv_allow)
                out["contraintes"]["L_min_PV_m"] = Lmin_pv

            cands = [x for x in (Lmin_p, Lmin_pv) if x is not None and x >= 0.0]
            if cands:
                out["L_min_m"] = max(cands)

            if L is not None and out["L_min_m"] is not None:
                out["ok_avec_L"] = float(L) >= float(out["L_min_m"])

            if L is not None:
                out["L_sur_d_actuel"] = float(L) / d_use
            if out["L_min_m"] is not None:
                out["L_sur_d_min"] = float(out["L_min_m"]) / d_use

            return out

        if W is not None and (p_allow is not None or (pv_allow is not None and omega is not None)):
            if d_candidates:
                dim["solutions"] = [calc_L_min_for_d(dd) for dd in d_candidates]
                if d is None and len(d_candidates) > 1:
                    dim["notes"].append("Plusieurs diamètres candidats : aucun choix automatique.")
            else:
                if pv_allow is not None and omega is not None:
                    Lmin_pv = (W * abs(omega)) / (2.0 * pv_allow)
                    dim["solutions"] = [{
                        "d_m": None,
                        "L_min_m": Lmin_pv,
                        "contraintes": {"L_min_PV_m": Lmin_pv},
                        "ok_avec_L": None,
                        "L_actuel_m": L,
                    }]
                    dim["notes"].append("d inconnu : seul L_min issu du critère PV est calculable.")
                else:
                    dim["notes"].append("Dimensionnement impossible sans d et sans contrainte suffisante.")
        else:
            dim["notes"].append("Dimensionnement impossible : fournir W et au moins p_adm ou (PV_adm + rpm).")

        rapport["dimensionnement"] = dim

        # ---------------------------------------------------------------------
        # 5) Pression projetée
        # ---------------------------------------------------------------------
        p_proj = None
        if d is None and not d_candidates:
            _push_inconnue(
                rapport,
                "impossibles",
                "diametre_portee_m",
                "Indispensable pour pression, vitesse, géométrie et dessin.",
            )
        elif d is None and d_candidates:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_portee_m",
                "Plusieurs diamètres candidats issus de arbre_piston ; aucun n'est choisi automatiquement.",
            )

        if L is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "longueur_coussinet_m",
                "Indispensable pour pression projetée et bloc CAO final.",
            )

        if d is not None and L is not None and W is not None:
            A_proj = d * L
            if A_proj > 0.0:
                p_proj = W / A_proj
                rapport["pressions"] = {
                    "surface_projetee_m2": A_proj,
                    "pression_projetee_pa": p_proj,
                    "charge_radiale_N": W,
                }

                if p_adm is not None:
                    p_allow2 = float(p_adm) / FS
                    rapport["pressions"]["pression_admissible_pa"] = float(p_adm)
                    rapport["pressions"]["pression_admissible_effective_pa"] = p_allow2
                    rapport["pressions"]["ok_pression"] = p_proj <= p_allow2
                    rapport["pressions"]["marge_pression"] = (p_allow2 / p_proj) if p_proj > 0.0 else None

        # ---------------------------------------------------------------------
        # 6) Cinématique / vitesse
        # ---------------------------------------------------------------------
        v = None
        if d is not None and omega is not None:
            v = omega * (0.5 * d)

        # ---------------------------------------------------------------------
        # 7) PV
        # ---------------------------------------------------------------------
        if p_proj is not None and v is not None:
            PV = p_proj * abs(v)
            rapport["pv"]["pv_W_m2"] = PV
            if self.pv_admissible_W_m2 is not None:
                pv_adm = _req_pos("pv_admissible_W_m2", self.pv_admissible_W_m2)
                pv_allow2 = pv_adm / FS
                rapport["pv"]["pv_admissible_W_m2"] = pv_adm
                rapport["pv"]["pv_admissible_effective_W_m2"] = pv_allow2
                rapport["pv"]["ok_pv"] = PV <= pv_allow2
                rapport["pv"]["marge_pv"] = (pv_allow2 / PV) if PV > 0.0 else None
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "PV",
                "Calculable si pression projetée et vitesse de glissement sont connues.",
            )

        # ---------------------------------------------------------------------
        # 8) Frottement / puissance dissipée
        # ---------------------------------------------------------------------
        if self.coefficient_frottement is not None and v is not None and W is not None and d is not None:
            mu = _req_pos("coefficient_frottement", self.coefficient_frottement, strictly=False)
            P_f = mu * abs(W) * abs(v)
            T_f = mu * abs(W) * (0.5 * d)
            rapport["frottement"] = {
                "mu": mu,
                "puissance_frottement_W": P_f,
                "couple_frottement_Nm": T_f,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "puissance_frottement_W",
                "Calculable si coefficient_frottement, W, d et rpm sont connus.",
            )

        # ---------------------------------------------------------------------
        # 9) Hydrodynamique / Sommerfeld
        # ---------------------------------------------------------------------
        eta = self.viscosite_Pa_s

        if eta is None and self.mode_lubrification in ("huile", "eau"):
            if self.mode_lubrification == "eau":
                if self.temperature_lubrifiant_K is not None and self.pression_lubrifiant_Pa is not None:
                    try:
                        from backend.ensemble.eau import etat_eau_pure  # type: ignore
                        et = etat_eau_pure(
                            T_K=float(self.temperature_lubrifiant_K),
                            p_Pa=float(self.pression_lubrifiant_Pa),
                            backend="auto",
                        )
                        eta = float(et.mu_Pa_s)
                        rapport["notes_modele"].append(
                            "viscosite_Pa_s déduite via backend.ensemble.eau.etat_eau_pure().mu_Pa_s"
                        )
                    except Exception:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "viscosite_Pa_s",
                            "Mode eau : déduction impossible (module eau indisponible ou erreur).",
                        )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "viscosite_Pa_s",
                        "Mode eau : calculable si temperature_lubrifiant_K et pression_lubrifiant_Pa sont fournis.",
                    )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "viscosite_Pa_s",
                    "Mode huile : fournir viscosite_Pa_s explicitement.",
                )

        if (
            eta is not None
            and p_proj is not None
            and rpm is not None
            and d is not None
            and L is not None
            and c is not None
        ):
            eta = _req_pos("viscosite_Pa_s", eta)
            N_tr_s = rpm / 60.0
            r = 0.5 * d
            S = (eta * N_tr_s * (r / c) ** 2 / p_proj) * (L / d)
            rapport["hydrodynamique"] = {
                "sommerfeld_S": S,
                "eta_Pa_s": eta,
                "jeu_radial_m": c,
                "L_sur_d": (L / d),
                "notes": "S calculé sans interprétation supplémentaire.",
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "sommerfeld_S",
                "Calculable si viscosite_Pa_s, p_proj, rpm, d, L et jeu_radial_m sont connus.",
            )

        # ---------------------------------------------------------------------
        # 10) Thermique : conduction radiale
        # ---------------------------------------------------------------------
        if e is not None and k_c is not None and d is not None and L is not None:
            k = _req_pos("conductivite_coussinet_w_m_k", k_c)
            ri = 0.5 * d
            ro = ri + e
            if ro <= ri:
                raise ValueError("epaisseur_coussinet_m invalide.")
            R = math.log(ro / ri) / (2.0 * math.pi * k * L)
            rapport["thermique"] = {
                "R_conduction_K_W": R,
                "k_coussinet_W_m_K": k,
                "ri_m": ri,
                "ro_m": ro,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "R_conduction_K_W",
                "Calculable si epaisseur_coussinet_m, conductivite et géométrie sont connus.",
            )

        # ---------------------------------------------------------------------
        # 11) Masse
        # ---------------------------------------------------------------------
        if e is not None and rho_c is not None and d is not None and L is not None:
            rho = _req_pos("densite_coussinet_kg_m3", rho_c)
            ri = 0.5 * d
            ro = ri + e
            V = math.pi * (ro * ro - ri * ri) * L
            m = rho * V
            rapport["masse"] = {
                "volume_m3": V,
                "masse_kg": m,
                "densite_kg_m3": rho,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse_coussinet",
                "Calculable si epaisseur, densité et géométrie sont connues.",
            )

        # ---------------------------------------------------------------------
        # 12) Géométrie / bloc CAO pour dessin manuel / SolidWorks
        # ---------------------------------------------------------------------
        D_ext = (d + 2.0 * e) if (d is not None and e is not None) else None
        D_int = d
        L_cao = L

        # si longueur absente mais une seule solution dimensionnante existe, on peut la proposer
        if L_cao is None and isinstance(dim.get("solutions"), list) and len(dim["solutions"]) == 1:
            sol0 = dim["solutions"][0]
            if isinstance(sol0, dict) and _is_finite(sol0.get("L_min_m")):
                L_cao = float(sol0["L_min_m"]) + self.regles_fabrication.surcote_longueur_fabrication_m
                rapport["notes_modele"].append(
                    "longueur_coussinet CAO proposée depuis L_min dimensionnant (sans l’imposer comme entrée)."
                )

        chanfrein = None
        if e is not None:
            chanfrein = _borne(
                self.regles_fabrication.ratio_chanfrein_sur_epaisseur * e,
                self.regles_fabrication.chanfrein_min_m,
                self.regles_fabrication.chanfrein_max_m,
            )

        if D_int is not None and L_cao is not None:
            rapport["cao"] = {
                "type_piece": "coussinet_arbre_piston",
                "diametre_interieur_nominal_m": D_int,
                "diametre_exterieur_nominal_m": D_ext,
                "longueur_nominale_m": L_cao,
                "epaisseur_radiale_m": e,
                "jeu_radial_m": c,
                "chanfrein_entrees_m": chanfrein,
                "rugosite_interieure_ra_um": self.regles_fabrication.rugosite_interieure_ra_um,
                "rugosite_exterieure_ra_um": self.regles_fabrication.rugosite_exterieure_ra_um,
                "tolerance_diametre_interieur_m": self.regles_fabrication.tolerance_diametre_interieur_m,
                "tolerance_diametre_exterieur_m": self.regles_fabrication.tolerance_diametre_exterieur_m,
                "tolerance_longueur_m": self.regles_fabrication.tolerance_longueur_m,
                "x_debut_m": 0.0,
                "x_fin_m": L_cao,
                "coupe_radiale": {
                    "rayon_interieur_m": (0.5 * D_int) if D_int is not None else None,
                    "rayon_exterieur_m": (0.5 * D_ext) if D_ext is not None else None,
                },
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "bloc_cao",
                "Bloc CAO complet calculable si au moins diamètre intérieur et longueur sont connus.",
            )

        # ---------------------------------------------------------------------
        # 13) Remplissage sections synthèse
        # ---------------------------------------------------------------------
        rapport["geometrie"] = {
            "diametre_portee_m": d,
            "diametre_portee_candidates_m": d_candidates if d is None else [],
            "longueur_coussinet_m": L,
            "epaisseur_coussinet_m": e,
            "jeu_radial_m": c,
            "diametre_exterieur_m": D_ext,
            "excentricite_m": self.excentricite_m,
        }

        rapport["cinematique"] = {
            "rpm": rpm,
            "omega_rad_s": omega,
            "vitesse_glissement_m_s": v,
        }

        rapport["efforts"] = {
            "charge_radiale_N": W,
            "charge_axiale_N": self.charge_axiale_N,
        }

        rapport["tribologie"] = {
            "mode_lubrification": self.mode_lubrification,
            "viscosite_Pa_s": eta,
            "coefficient_frottement": self.coefficient_frottement,
        }

        rapport["entrees"] = {
            "diametre_portee_m": self.diametre_portee_m,
            "longueur_coussinet_m": self.longueur_coussinet_m,
            "epaisseur_coussinet_m": self.epaisseur_coussinet_m,
            "jeu_radial_m": self.jeu_radial_m,
            "excentricite_m": self.excentricite_m,
            "charge_radiale_N": self.charge_radiale_N,
            "charge_axiale_N": self.charge_axiale_N,
            "rpm": self.rpm,
            "coefficient_frottement": self.coefficient_frottement,
            "mode_lubrification": self.mode_lubrification,
            "viscosite_Pa_s": self.viscosite_Pa_s,
            "temperature_lubrifiant_K": self.temperature_lubrifiant_K,
            "pression_lubrifiant_Pa": self.pression_lubrifiant_Pa,
            "materiau_coussinet": self.materiau_coussinet,
            "densite_coussinet_kg_m3": self.densite_coussinet_kg_m3,
            "conductivite_coussinet_w_m_k": self.conductivite_coussinet_w_m_k,
            "pression_admissible_pa": self.pression_admissible_pa,
            "pv_admissible_W_m2": self.pv_admissible_W_m2,
            "facteur_securite": self.facteur_securite,
        }

        # ---------------------------------------------------------------------
        # 14) Mode strict
        # ---------------------------------------------------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CoussinetArbrePiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        _ajouter_champs_metier_definition_coussinet(rapport)
        ajouter_dossier_definition_solidworks(rapport, "coussinet_arbre_piston")
        return rapport


# =============================================================================
# Exemple d'usage
# =============================================================================
if __name__ == "__main__":
    from pprint import pprint

    c = CoussinetArbrePiston(
        diametre_portee_m=0.020,
        longueur_coussinet_m=0.020,
        epaisseur_coussinet_m=0.002,
        charge_radiale_N=2000.0,
        rpm=3000.0,
        coefficient_frottement=0.05,
        mode_lubrification="eau",
        temperature_lubrifiant_K=300.0,
        pression_lubrifiant_Pa=101325.0,
        jeu_radial_m=20e-6,
        materiau_coussinet="bronze_cusn12",
        pression_admissible_pa=30e6,
        pv_admissible_W_m2=1.0e9,
        facteur_securite=2.0,
    )

    pprint(c.analyser(strict=False))
