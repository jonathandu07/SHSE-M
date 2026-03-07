# backend/pieces/roulement_aiguille_arbre_vilebrequin.py
# =============================================================================
# ROULEMENT À AIGUILLES — ARBRE / VILEBREQUIN (côté maneton / grande tête)
# =============================================================================
# Objectif :
# - conserver le comportement initial : calcul d'exigences sans "inventer" une référence ;
# - aller plus loin pour définir AU MAXIMUM le roulement par le calcul ;
# - exploiter les autres pièces (bielle, arbre_vilebrequin, moteur) ;
# - produire un bloc "cao" exploitable pour dessin manuel / SolidWorks ;
# - vérifier une référence catalogue si elle est fournie.
#
# IMPORTANT :
# - Sans référence commerciale, ce module ne "choisit" pas un roulement réel du commerce.
# - Il calcule :
#   * les exigences mécaniques (C, C0, vitesse, pression),
#   * les interfaces obligatoires (d, B),
#   * et, si tu fournis assez de paramètres géométriques explicites,
#     une géométrie estimée du roulement/cage/aiguilles :
#       - D_ext estimé
#       - diamètre moyen des aiguilles
#       - charge par aiguille
#       - longueur utile d’aiguille
#       - remplissage circonférentiel
#
# Principe "rien inventer" :
# - aucune série catalogue imposée ;
# - aucune proportion cachée ;
# - toute hypothèse géométrique doit venir :
#   * d'une référence catalogue fournie,
#   * ou de paramètres explicites utilisateur,
#   * ou de scénarios EXPLICITES (listes candidates) si tu veux explorer.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List, Literal, Sequence
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
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": nom, "raison": raison})


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


def _safe_get_dict(d: Any, key: str) -> Dict[str, Any]:
    if isinstance(d, dict):
        v = d.get(key, {})
        return v if isinstance(v, dict) else {}
    return {}


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for m in ("calculer", "analyser"):
        try:
            if hasattr(obj, m) and callable(getattr(obj, m)):
                try:
                    r = getattr(obj, m)(strict=False)
                except TypeError:
                    r = getattr(obj, m)()
                if isinstance(r, dict):
                    return r
        except Exception:
            continue
    return None


# =============================================================================
# Matériaux (optionnel)
# =============================================================================

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    module_young_pa: Optional[float],
    limite_elastique_pa: Optional[float],
) -> Dict[str, Optional[float]]:
    rho = densite_kg_m3
    E = module_young_pa
    Re = limite_elastique_pa

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

                def g(obj: Any, *names: str) -> Optional[float]:
                    for n in names:
                        if isinstance(obj, dict) and n in obj:
                            v = obj.get(n)
                        else:
                            v = getattr(obj, n, None)
                        if v is not None and _is_finite(v):
                            return float(v)
                    return None

                rho = rho if rho is not None else g(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                E = E if E is not None else g(mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa")
                Re = Re if Re is not None else g(mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa")
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "module_young_pa": E,
        "limite_elastique_pa": Re,
    }


# =============================================================================
# Modèles roulement (exigences)
# =============================================================================

def _L10_million_rev(vie_heures: float, rpm: float) -> float:
    return float(rpm) * 60.0 * float(vie_heures) / 1e6


def _C_requis_iso281(P_N: float, L10_million: float, p_exposant: float) -> float:
    return float(P_N) * (float(L10_million) ** (1.0 / float(p_exposant)))


def _pression_moyenne_proj(F_N: float, d_m: float, B_m: float) -> float:
    d = _req_pos("d_m", d_m)
    B = _req_pos("B_m", B_m)
    return abs(float(F_N)) / (d * B)


def _vitesse_peripherique(d_m: float, rpm: float) -> float:
    d = _req_pos("d_m", d_m)
    n = _req_pos("rpm", rpm, strictly=False)
    return math.pi * d * n / 60.0


# =============================================================================
# Géométrie d'un roulement à aiguilles (sans norme cachée)
# =============================================================================

def _diametre_moyen_chemin_aiguilles(
    d_interieur_m: float,
    diametre_aiguille_m: float,
    jeu_radial_fonctionnel_m: float = 0.0,
    epaisseur_bague_interieure_radiale_m: float = 0.0,
) -> float:
    """
    Diamètre moyen du cercle des centres d'aiguilles.
    Hypothèse géométrique explicite :
    D_pitch = d + 2*(t_bague_int + jeu_radial + d_aiguille/2)
    """
    d = _req_pos("d_interieur_m", d_interieur_m)
    da = _req_pos("diametre_aiguille_m", diametre_aiguille_m)
    j = _req_pos("jeu_radial_fonctionnel_m", jeu_radial_fonctionnel_m, strictly=False)
    tbi = _req_pos("epaisseur_bague_interieure_radiale_m", epaisseur_bague_interieure_radiale_m, strictly=False)
    return d + 2.0 * (tbi + j + 0.5 * da)


def _diametre_exterieur_estime(
    d_interieur_m: float,
    diametre_aiguille_m: float,
    epaisseur_bague_interieure_radiale_m: float = 0.0,
    epaisseur_bague_exterieure_radiale_m: float = 0.0,
    jeu_radial_fonctionnel_m: float = 0.0,
) -> float:
    """
    D = d + 2*(t_bague_int + jeu + d_aiguille + t_bague_ext)
    """
    d = _req_pos("d_interieur_m", d_interieur_m)
    da = _req_pos("diametre_aiguille_m", diametre_aiguille_m)
    tbi = _req_pos("epaisseur_bague_interieure_radiale_m", epaisseur_bague_interieure_radiale_m, strictly=False)
    tbe = _req_pos("epaisseur_bague_exterieure_radiale_m", epaisseur_bague_exterieure_radiale_m, strictly=False)
    j = _req_pos("jeu_radial_fonctionnel_m", jeu_radial_fonctionnel_m, strictly=False)
    return d + 2.0 * (tbi + j + da + tbe)


def _circonference(D_m: float) -> float:
    return math.pi * _req_pos("D_m", D_m)


def _remplissage_circonference(
    diametre_pitch_m: float,
    diametre_aiguille_m: float,
    nb_aiguilles: int,
    jeu_circonference_par_aiguille_m: float = 0.0,
) -> Dict[str, float]:
    Dp = _req_pos("diametre_pitch_m", diametre_pitch_m)
    da = _req_pos("diametre_aiguille_m", diametre_aiguille_m)
    z = _req_int_ge("nb_aiguilles", nb_aiguilles, min_value=1)
    jc = _req_pos("jeu_circonference_par_aiguille_m", jeu_circonference_par_aiguille_m, strictly=False)

    C = _circonference(Dp)
    pas_requis = z * (da + jc)
    taux = pas_requis / C

    return {
        "circonference_pitch_m": C,
        "developpe_requis_m": pas_requis,
        "taux_remplissage_circonference": taux,
        "ok_geometrique": 1.0 if pas_requis <= C else 0.0,
    }


def _charge_par_aiguille(F_N: float, nb_aiguilles: int, facteur_repartition: float = 1.0) -> float:
    """
    Répartition simplifiée, explicite :
    F_aig = F * facteur_repartition / z
    Si tu veux tenir compte d'une répartition non uniforme, fournis facteur_repartition > 1.
    """
    F = abs(float(F_N))
    z = _req_int_ge("nb_aiguilles", nb_aiguilles, min_value=1)
    fr = _req_pos("facteur_repartition", facteur_repartition)
    return F * fr / z


def _pression_proj_par_aiguille(F_aiguille_N: float, diametre_aiguille_m: float, longueur_utile_m: float) -> float:
    da = _req_pos("diametre_aiguille_m", diametre_aiguille_m)
    L = _req_pos("longueur_utile_m", longueur_utile_m)
    return abs(float(F_aiguille_N)) / (da * L)


# =============================================================================
# Règles explicites CAO / exploration
# =============================================================================

TypeRoulementAiguille = Literal[
    "inconnu",
    "aiguilles_seules",
    "avec_cage_sans_bagues",
    "avec_bague_exterieure",
    "avec_bagues_interieure_exterieure",
]


@dataclass(frozen=True)
class ReglesGeometrieRoulementAiguille:
    """
    Règles EXPLICITES.
    Rien n'est imposé si tu ne fournis pas les paramètres géométriques associés.
    """
    marge_axiale_aiguille_par_face_m: float = 0.0005
    jeu_circonference_par_aiguille_m: float = 0.0
    facteur_repartition_charge_par_aiguille: float = 1.0

    chanfrein_min_m: float = 0.0002
    chanfrein_max_m: float = 0.0010
    rayon_min_m: float = 0.0002
    rayon_max_m: float = 0.0010

    rugosite_portees_ra_um: float = 0.4
    rugosite_logement_ra_um: float = 0.8
    tolerance_diametre_m: float = 0.00001
    tolerance_largeur_m: float = 0.00002


# =============================================================================
# Pièce
# =============================================================================

@dataclass
class RoulementAiguilleArbreVilebrequin:
    """
    Roulement à aiguilles au niveau du maneton (grande tête).

    Sorties clés :
    - exigences mécaniques : C_min, C0_min, vitesse, pression
    - interfaces : d_interieur_requis_m, B_requis_m
    - géométrie estimée (si paramètres suffisants)
    - bloc CAO
    """

    # Liens
    corps_bielle: Optional[Any] = None
    arbre_vilebrequin: Optional[Any] = None
    moteur_thermique: Optional[Any] = None

    # Cinématique / durée de vie
    rpm_vilebrequin: Optional[float] = None
    vie_cible_heures: Optional[float] = None
    exposant_p_iso281: float = 10.0 / 3.0

    # Facteurs
    facteur_application_Ka: Optional[float] = None
    facteur_fiablete_a1: Optional[float] = None
    facteur_contamination_a23: Optional[float] = None

    # Charges
    charge_equivalente_P_N: Optional[float] = None
    charge_statique_P0_N: Optional[float] = None
    facteur_securite_stat: Optional[float] = None

    # Interface (déductible depuis bielle / arbre)
    diametre_maneton_m: Optional[float] = None
    largeur_portee_grande_tete_m: Optional[float] = None
    force_bielle_max_N: Optional[float] = None

    # Type de roulement / géométrie explicite
    type_roulement: TypeRoulementAiguille = "inconnu"
    diametre_aiguille_m: Optional[float] = None
    nb_aiguilles: Optional[int] = None
    longueur_aiguille_m: Optional[float] = None

    epaisseur_bague_interieure_radiale_m: Optional[float] = None
    epaisseur_bague_exterieure_radiale_m: Optional[float] = None
    jeu_radial_fonctionnel_m: Optional[float] = None

    # Si tu ne veux pas une géométrie unique, tu peux fournir des scénarios
    diametre_aiguille_candidates_m: Tuple[float, ...] = tuple()
    nb_aiguilles_candidates: Tuple[int, ...] = tuple()
    epaisseur_bague_interieure_candidates_m: Tuple[float, ...] = tuple()
    epaisseur_bague_exterieure_candidates_m: Tuple[float, ...] = tuple()
    jeu_radial_candidates_m: Tuple[float, ...] = tuple()

    # Matériau roulement (optionnel)
    materiau_roulement_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    module_young_pa: Optional[float] = None
    limite_elastique_pa: Optional[float] = None

    # Référence commerciale (si choisie)
    d_interieur_m: Optional[float] = None
    D_exterieur_m: Optional[float] = None
    B_largeur_m: Optional[float] = None
    C_dynamique_N: Optional[float] = None
    C0_statique_N: Optional[float] = None
    vitesse_limite_rpm: Optional[float] = None
    pression_admissible_pa: Optional[float] = None

    # Règles explicites
    regles_geometrie: ReglesGeometrieRoulementAiguille = field(default_factory=ReglesGeometrieRoulementAiguille)

    # -------------------------------------------------------------------------
    # Extraction autres pièces
    # -------------------------------------------------------------------------

    def _extraire_depuis_bielle(self, rapport: Dict[str, Any]) -> Dict[str, Optional[float]]:
        out = {
            "Fmax_N": None,
            "d_maneton_m": None,
            "L_portee_m": None,
        }
        rb = _try_call_report(self.corps_bielle)
        if not isinstance(rb, dict):
            if self.corps_bielle is not None:
                _push_inconnue(rapport, "partielles", "bielle", "Impossible de lire corps_bielle (pas de dict retourné).")
            return out

        out["Fmax_N"] = _first_numeric_from_dict(
            rb,
            [
                ("efforts", "force_axiale_max_N"),
                ("resultats", "force_axiale_max_N"),
                ("force_axiale_max_N",),
            ],
        )
        out["d_maneton_m"] = _first_numeric_from_dict(
            rb,
            [
                ("geometrie", "grande_tete", "diametre_maneton_m"),
                ("contacts_tetes", "grande_tete", "diametre_maneton_m"),
                ("entrees", "diametre_maneton_m"),
                ("diametre_maneton_m",),
            ],
        )
        out["L_portee_m"] = _first_numeric_from_dict(
            rb,
            [
                ("contacts_tetes", "grande_tete", "longueur_portee_m"),
                ("geometrie", "grande_tete", "longueur_portee_m"),
                ("entrees", "longueur_portee_grande_tete_m"),
            ],
        )
        return out

    def _extraire_depuis_arbre_vilebrequin(self, rapport: Dict[str, Any]) -> Dict[str, Optional[float]]:
        out = {
            "rpm": None,
            "force_bielle_effective_N": None,
            "diametre_maneton_m": None,
            "largeur_portee_maneton_m": None,
        }
        rv = _try_call_report(self.arbre_vilebrequin)
        if not isinstance(rv, dict):
            if self.arbre_vilebrequin is not None:
                _push_inconnue(rapport, "partielles", "arbre_vilebrequin", "Impossible de lire arbre_vilebrequin.")
            return out

        rec = _safe_get_dict(rv, "recuperations")
        bie = _safe_get_dict(rv, "bielle_maneton")
        ent = _safe_get_dict(rv, "entrees")

        if _is_finite(rec.get("rpm")):
            out["rpm"] = float(rec["rpm"])
        elif _is_finite(ent.get("rpm")):
            out["rpm"] = float(ent["rpm"])

        if _is_finite(rec.get("force_bielle_effective_N")):
            out["force_bielle_effective_N"] = float(rec["force_bielle_effective_N"])

        if _is_finite(bie.get("diametre_maneton_m")):
            out["diametre_maneton_m"] = float(bie["diametre_maneton_m"])
        elif _is_finite(_deep_get(rv, ("geometrie", "diametre_maneton_m"))):
            out["diametre_maneton_m"] = float(_deep_get(rv, ("geometrie", "diametre_maneton_m")))

        if _is_finite(bie.get("largeur_portee_maneton_m")):
            out["largeur_portee_maneton_m"] = float(bie["largeur_portee_maneton_m"])
        elif _is_finite(_deep_get(rv, ("geometrie", "largeur_portee_maneton_m"))):
            out["largeur_portee_maneton_m"] = float(_deep_get(rv, ("geometrie", "largeur_portee_maneton_m")))

        return out

    def _extraire_depuis_moteur(self, rapport: Dict[str, Any]) -> Dict[str, Optional[float]]:
        out = {"rpm": None, "force_bielle_N": None}
        rm = _try_call_report(self.moteur_thermique)
        if not isinstance(rm, dict):
            if self.moteur_thermique is not None:
                _push_inconnue(rapport, "partielles", "moteur_thermique", "Impossible de lire moteur_thermique.")
            return out

        for bloc in (
            _safe_get_dict(rm, "forces"),
            _safe_get_dict(rm, "resultats"),
            _safe_get_dict(rm, "dimensionnement"),
            rm,
        ):
            for k in ("force_bielle_effective_N", "force_bielle_N", "F_bielle_N"):
                if out["force_bielle_N"] is None and _is_finite(bloc.get(k)):
                    out["force_bielle_N"] = float(bloc[k])

            for k in ("rpm",):
                if out["rpm"] is None and _is_finite(bloc.get(k)):
                    out["rpm"] = float(bloc[k])

        return out

    # -------------------------------------------------------------------------
    # Calcul principal
    # -------------------------------------------------------------------------

    def calculer(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "roulement_aiguille_arbre_vilebrequin",
            "entrees": {},
            "donnees_bielle": {},
            "donnees_arbre_vilebrequin": {},
            "donnees_moteur": {},
            "matiere": {},
            "charges": {},
            "exigences": {},
            "dimensions_requises": {},
            "geometrie_estimee": {},
            "scenarios_geometrie": {},
            "dimensions_reference": {},
            "verification_reference": {},
            "cao": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # ---------------------------------------------------------------------
        # 1) Matière
        # ---------------------------------------------------------------------
        mat = _resoudre_materiau(
            self.materiau_roulement_cle,
            self.densite_kg_m3,
            self.module_young_pa,
            self.limite_elastique_pa,
        )
        rapport["matiere"] = {
            "materiau_roulement_cle": self.materiau_roulement_cle,
            "densite_kg_m3": mat["densite_kg_m3"],
            "module_young_pa": mat["module_young_pa"],
            "limite_elastique_pa": mat["limite_elastique_pa"],
        }

        # ---------------------------------------------------------------------
        # 2) Déductions autres pièces
        # ---------------------------------------------------------------------
        b = self._extraire_depuis_bielle(rapport) if self.corps_bielle is not None else {"Fmax_N": None, "d_maneton_m": None, "L_portee_m": None}
        a = self._extraire_depuis_arbre_vilebrequin(rapport) if self.arbre_vilebrequin is not None else {"rpm": None, "force_bielle_effective_N": None, "diametre_maneton_m": None, "largeur_portee_maneton_m": None}
        m = self._extraire_depuis_moteur(rapport) if self.moteur_thermique is not None else {"rpm": None, "force_bielle_N": None}

        rapport["donnees_bielle"] = b
        rapport["donnees_arbre_vilebrequin"] = a
        rapport["donnees_moteur"] = m

        # ---------------------------------------------------------------------
        # 3) Interface : d et B
        # ---------------------------------------------------------------------
        d_maneton = self.diametre_maneton_m
        if d_maneton is None and b["d_maneton_m"] is not None:
            d_maneton = float(b["d_maneton_m"])
            rapport["notes_modele"].append("diametre_maneton_m déduit depuis CorpsBielle.")
        elif d_maneton is None and a["diametre_maneton_m"] is not None:
            d_maneton = float(a["diametre_maneton_m"])
            rapport["notes_modele"].append("diametre_maneton_m déduit depuis ArbreVilbrequin.")

        if d_maneton is not None:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)
            rapport["dimensions_requises"]["d_interieur_requis_m"] = d_maneton
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "diametre_maneton_m",
                "Indispensable pour définir l'alésage du roulement et le maneton.",
            )

        L_portee = self.largeur_portee_grande_tete_m
        if L_portee is None and b["L_portee_m"] is not None:
            L_portee = float(b["L_portee_m"])
            rapport["notes_modele"].append("largeur_portee_grande_tete_m déduite depuis CorpsBielle.")
        elif L_portee is None and a["largeur_portee_maneton_m"] is not None:
            L_portee = float(a["largeur_portee_maneton_m"])
            rapport["notes_modele"].append("largeur_portee_grande_tete_m déduite depuis ArbreVilbrequin.")

        if L_portee is not None:
            L_portee = _req_pos("largeur_portee_grande_tete_m", L_portee)
            rapport["dimensions_requises"]["B_max_logement_m"] = L_portee
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_portee_grande_tete_m",
                "Utile pour fixer ou vérifier la largeur B du roulement.",
            )

        # ---------------------------------------------------------------------
        # 4) Charges
        # ---------------------------------------------------------------------
        P = self.charge_equivalente_P_N
        if P is None and self.force_bielle_max_N is not None:
            P = abs(float(self.force_bielle_max_N))
            rapport["notes_modele"].append("charge_equivalente_P_N reprise depuis force_bielle_max_N fournie.")
        elif P is None and a["force_bielle_effective_N"] is not None:
            P = abs(float(a["force_bielle_effective_N"]))
            rapport["notes_modele"].append("charge_equivalente_P_N déduite depuis ArbreVilbrequin.")
        elif P is None and b["Fmax_N"] is not None:
            P = abs(float(b["Fmax_N"]))
            rapport["notes_modele"].append("Hypothèse conservatrice : P ≈ |force_axiale_max_bielle|.")
        elif P is None and m["force_bielle_N"] is not None:
            P = abs(float(m["force_bielle_N"]))
            rapport["notes_modele"].append("charge_equivalente_P_N déduite depuis moteur_thermique.")

        if P is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "charge_equivalente_P_N",
                "Indispensable pour C_min et pression projetée.",
            )

        P0 = self.charge_statique_P0_N
        if P0 is None and P is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "charge_statique_P0_N",
                "Requise pour C0 statique ; non déduite automatiquement.",
            )

        rapport["charges"] = {
            "charge_equivalente_P_N": P,
            "charge_statique_P0_N": P0,
        }

        # ---------------------------------------------------------------------
        # 5) Vitesse / vie
        # ---------------------------------------------------------------------
        rpm = self.rpm_vilebrequin
        if rpm is None and a["rpm"] is not None:
            rpm = float(a["rpm"])
            rapport["notes_modele"].append("rpm_vilebrequin déduit depuis ArbreVilbrequin.")
        elif rpm is None and m["rpm"] is not None:
            rpm = float(m["rpm"])
            rapport["notes_modele"].append("rpm_vilebrequin déduit depuis moteur_thermique.")

        vie_h = self.vie_cible_heures

        if rpm is None:
            _push_inconnue(rapport, "impossibles", "rpm_vilebrequin", "Nécessaire pour L10 et vitesse périphérique.")
        else:
            rpm = _req_pos("rpm_vilebrequin", rpm)

        if vie_h is None:
            _push_inconnue(rapport, "impossibles", "vie_cible_heures", "Nécessaire pour calculer L10.")
        else:
            vie_h = _req_pos("vie_cible_heures", vie_h)

        # ---------------------------------------------------------------------
        # 6) Exigences ISO 281
        # ---------------------------------------------------------------------
        if P is not None and rpm is not None and vie_h is not None:
            P_eff = float(P)

            if self.facteur_application_Ka is not None:
                Ka = _req_pos("facteur_application_Ka", self.facteur_application_Ka)
                P_eff *= Ka
                rapport["notes_modele"].append("P_eff = P * Ka.")

            if self.facteur_fiablete_a1 is not None or self.facteur_contamination_a23 is not None:
                rapport["notes_modele"].append(
                    "a1/a23 sont enregistrés mais non appliqués automatiquement sans convention ISO explicite supplémentaire."
                )

            L10_m = _L10_million_rev(float(vie_h), float(rpm))
            pexp = _req_pos("exposant_p_iso281", self.exposant_p_iso281)
            C_min = _C_requis_iso281(P_eff, L10_m, pexp)

            rapport["exigences"].update({
                "L10_millions_tours": L10_m,
                "P_eff_N": P_eff,
                "C_dynamique_min_N": C_min,
                "exposant_p": pexp,
            })

        if P0 is not None and self.facteur_securite_stat is not None:
            fs0 = _req_pos("facteur_securite_stat", self.facteur_securite_stat)
            rapport["exigences"]["C0_statique_min_N"] = abs(float(P0)) * fs0
            rapport["exigences"]["facteur_securite_stat"] = fs0
        elif P0 is not None and self.facteur_securite_stat is None:
            _push_inconnue(rapport, "partielles", "facteur_securite_stat", "Requis pour C0_statique_min_N.")

        # ---------------------------------------------------------------------
        # 7) Largeur requise par calcul
        # ---------------------------------------------------------------------
        B_min_pression = None
        if P is not None and d_maneton is not None and self.pression_admissible_pa is not None:
            padm = _req_pos("pression_admissible_pa", self.pression_admissible_pa)
            B_min_pression = abs(float(P)) / (float(d_maneton) * padm)
            rapport["dimensions_requises"]["B_min_pression_m"] = B_min_pression

        B_requis = None
        Bs: List[float] = []
        if L_portee is not None:
            Bs.append(float(L_portee))
        if B_min_pression is not None:
            Bs.append(float(B_min_pression))
        if Bs:
            B_requis = max(Bs)
            rapport["dimensions_requises"]["B_requis_m"] = B_requis
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "B_requis_m",
                "Calculable si largeur_portee_grande_tete_m et/ou pression_admissible_pa sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 8) Géométrie estimée UNIQUE si assez de paramètres
        # ---------------------------------------------------------------------
        def _calc_geom_unique(
            *,
            d_int: float,
            B_use: float,
            diam_aig: float,
            z: int,
            tbi: float,
            tbe: float,
            jeu: float,
            L_aig_imposee: Optional[float],
        ) -> Dict[str, Any]:
            res: Dict[str, Any] = {}

            d_pitch = _diametre_moyen_chemin_aiguilles(
                d_interieur_m=d_int,
                diametre_aiguille_m=diam_aig,
                jeu_radial_fonctionnel_m=jeu,
                epaisseur_bague_interieure_radiale_m=tbi,
            )
            D_ext = _diametre_exterieur_estime(
                d_interieur_m=d_int,
                diametre_aiguille_m=diam_aig,
                epaisseur_bague_interieure_radiale_m=tbi,
                epaisseur_bague_exterieure_radiale_m=tbe,
                jeu_radial_fonctionnel_m=jeu,
            )

            if L_aig_imposee is not None:
                L_aig = _req_pos("longueur_aiguille_m", L_aig_imposee)
            else:
                L_aig = B_use - 2.0 * self.regles_geometrie.marge_axiale_aiguille_par_face_m
                if L_aig <= 0.0:
                    raise ValueError("Largeur B insuffisante pour loger la longueur utile d’aiguille avec les marges axiales.")

            circ = _remplissage_circonference(
                diametre_pitch_m=d_pitch,
                diametre_aiguille_m=diam_aig,
                nb_aiguilles=z,
                jeu_circonference_par_aiguille_m=self.regles_geometrie.jeu_circonference_par_aiguille_m,
            )

            F_par_aig = None
            p_proj_par_aig = None
            if P is not None:
                F_par_aig = _charge_par_aiguille(
                    F_N=float(P),
                    nb_aiguilles=z,
                    facteur_repartition=self.regles_geometrie.facteur_repartition_charge_par_aiguille,
                )
                p_proj_par_aig = _pression_proj_par_aiguille(
                    F_aiguille_N=F_par_aig,
                    diametre_aiguille_m=diam_aig,
                    longueur_utile_m=L_aig,
                )

            res.update({
                "d_interieur_m": d_int,
                "B_largeur_m": B_use,
                "diametre_aiguille_m": diam_aig,
                "nb_aiguilles": z,
                "longueur_utile_aiguille_m": L_aig,
                "epaisseur_bague_interieure_radiale_m": tbi,
                "epaisseur_bague_exterieure_radiale_m": tbe,
                "jeu_radial_fonctionnel_m": jeu,
                "diametre_pitch_m": d_pitch,
                "D_exterieur_estime_m": D_ext,
                "charge_par_aiguille_N": F_par_aig,
                "pression_projetee_par_aiguille_pa": p_proj_par_aig,
                "circonference": circ,
            })
            return res

        can_calc_unique_geom = (
            d_maneton is not None
            and B_requis is not None
            and self.diametre_aiguille_m is not None
            and self.nb_aiguilles is not None
        )

        if can_calc_unique_geom:
            tbi = _req_pos("epaisseur_bague_interieure_radiale_m", self.epaisseur_bague_interieure_radiale_m or 0.0, strictly=False)
            tbe = _req_pos("epaisseur_bague_exterieure_radiale_m", self.epaisseur_bague_exterieure_radiale_m or 0.0, strictly=False)
            jeu = _req_pos("jeu_radial_fonctionnel_m", self.jeu_radial_fonctionnel_m or 0.0, strictly=False)

            try:
                geom_unique = _calc_geom_unique(
                    d_int=float(d_maneton),
                    B_use=float(B_requis),
                    diam_aig=_req_pos("diametre_aiguille_m", self.diametre_aiguille_m),
                    z=_req_int_ge("nb_aiguilles", self.nb_aiguilles, min_value=1),
                    tbi=tbi,
                    tbe=tbe,
                    jeu=jeu,
                    L_aig_imposee=self.longueur_aiguille_m,
                )
                rapport["geometrie_estimee"] = geom_unique
            except Exception as e:
                _push_inconnue(rapport, "partielles", "geometrie_estimee", f"Calcul géométrique impossible: {e}")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "geometrie_estimee",
                "Pour une géométrie unique estimée, fournir au moins diametre_aiguille_m et nb_aiguilles, plus d_interieur_requis_m et B_requis calculables.",
            )

        # ---------------------------------------------------------------------
        # 9) Scénarios géométriques si listes candidates
        # ---------------------------------------------------------------------
        scen_list: List[Dict[str, Any]] = []
        if (
            d_maneton is not None
            and B_requis is not None
            and self.diametre_aiguille_candidates_m
            and self.nb_aiguilles_candidates
        ):
            tbi_cands = self.epaisseur_bague_interieure_candidates_m or (self.epaisseur_bague_interieure_radiale_m,) if self.epaisseur_bague_interieure_radiale_m is not None else (0.0,)
            tbe_cands = self.epaisseur_bague_exterieure_candidates_m or (self.epaisseur_bague_exterieure_radiale_m,) if self.epaisseur_bague_exterieure_radiale_m is not None else (0.0,)
            jeu_cands = self.jeu_radial_candidates_m or (self.jeu_radial_fonctionnel_m,) if self.jeu_radial_fonctionnel_m is not None else (0.0,)

            for da in self.diametre_aiguille_candidates_m:
                for z in self.nb_aiguilles_candidates:
                    for tbi in tbi_cands:
                        for tbe in tbe_cands:
                            for jeu in jeu_cands:
                                try:
                                    sc = _calc_geom_unique(
                                        d_int=float(d_maneton),
                                        B_use=float(B_requis),
                                        diam_aig=_req_pos("diametre_aiguille_m", da),
                                        z=_req_int_ge("nb_aiguilles", z, min_value=1),
                                        tbi=_req_pos("epaisseur_bague_interieure_radiale_m", tbi, strictly=False),
                                        tbe=_req_pos("epaisseur_bague_exterieure_radiale_m", tbe, strictly=False),
                                        jeu=_req_pos("jeu_radial_fonctionnel_m", jeu, strictly=False),
                                        L_aig_imposee=self.longueur_aiguille_m,
                                    )
                                    scen_list.append(sc)
                                except Exception:
                                    continue

            if scen_list:
                rapport["scenarios_geometrie"] = {
                    "nb_scenarios": len(scen_list),
                    "liste": scen_list,
                    "note": "Scénarios produits sans sélection automatique.",
                }

        # ---------------------------------------------------------------------
        # 10) Référence commerciale si fournie
        # ---------------------------------------------------------------------
        d_ref = D_ref = B_ref = None

        if self.d_interieur_m is not None:
            d_ref = _req_pos("d_interieur_m", self.d_interieur_m)
            rapport["dimensions_reference"]["d_interieur_m"] = d_ref

        if self.D_exterieur_m is not None:
            D_ref = _req_pos("D_exterieur_m", self.D_exterieur_m)
            rapport["dimensions_reference"]["D_exterieur_m"] = D_ref
            rapport["dimensions_requises"]["D_exterieur_requis_m"] = D_ref

        if self.B_largeur_m is not None:
            B_ref = _req_pos("B_largeur_m", self.B_largeur_m)
            rapport["dimensions_reference"]["B_largeur_m"] = B_ref

        # Interface référence
        if d_ref is not None and d_maneton is not None:
            rapport["verification_reference"].setdefault("interface", {})
            rapport["verification_reference"]["interface"]["d_vs_maneton_nominal"] = {
                "d_interieur_m": d_ref,
                "diametre_maneton_m": d_maneton,
                "ecart_m": d_ref - d_maneton,
                "ok": abs(d_ref - d_maneton) <= 1e-12,
            }

        if B_ref is not None and L_portee is not None:
            rapport["verification_reference"].setdefault("interface", {})
            rapport["verification_reference"]["interface"]["B_vs_portee"] = {
                "B_largeur_m": B_ref,
                "largeur_portee_m": L_portee,
                "marge_m": L_portee - B_ref,
                "ok": (L_portee >= B_ref),
            }

        if P is not None and d_ref is not None and B_ref is not None:
            p_proj = _pression_moyenne_proj(float(P), d_ref, B_ref)
            rapport["verification_reference"]["pression_proj"] = {
                "pression_moyenne_pa": p_proj,
                "pression_admissible_pa": self.pression_admissible_pa,
            }
            if self.pression_admissible_pa is not None:
                padm = _req_pos("pression_admissible_pa", self.pression_admissible_pa)
                rapport["verification_reference"]["pression_proj"]["ok"] = (p_proj <= padm)
                rapport["verification_reference"]["pression_proj"]["marge"] = (padm / p_proj) if p_proj > 0 else None

        if self.C_dynamique_N is not None and "C_dynamique_min_N" in rapport["exigences"]:
            C = _req_pos("C_dynamique_N", self.C_dynamique_N)
            Cmin = float(rapport["exigences"]["C_dynamique_min_N"])
            rapport["verification_reference"]["C"] = {
                "C_N": C,
                "C_min_N": Cmin,
                "ok": C >= Cmin,
                "marge": (C / Cmin) if Cmin > 0 else None,
            }
        elif "C_dynamique_min_N" in rapport["exigences"]:
            _push_inconnue(rapport, "partielles", "C_dynamique_N", "Fournir C catalogue pour valider la référence.")

        if self.C0_statique_N is not None and "C0_statique_min_N" in rapport["exigences"]:
            C0 = _req_pos("C0_statique_N", self.C0_statique_N)
            C0min = float(rapport["exigences"]["C0_statique_min_N"])
            rapport["verification_reference"]["C0"] = {
                "C0_N": C0,
                "C0_min_N": C0min,
                "ok": C0 >= C0min,
                "marge": (C0 / C0min) if C0min > 0 else None,
            }
        elif "C0_statique_min_N" in rapport["exigences"]:
            _push_inconnue(rapport, "partielles", "C0_statique_N", "Fournir C0 catalogue pour valider la référence.")

        if self.vitesse_limite_rpm is not None and rpm is not None:
            vmax = _req_pos("vitesse_limite_rpm", self.vitesse_limite_rpm)
            rapport["verification_reference"]["vitesse"] = {
                "rpm_service": rpm,
                "rpm_limite": vmax,
                "ok": rpm <= vmax,
                "marge": (vmax / rpm) if rpm > 0 else None,
            }
        elif rpm is not None:
            _push_inconnue(rapport, "partielles", "vitesse_limite_rpm", "Fournir vitesse limite fabricant pour valider la référence.")

        # ---------------------------------------------------------------------
        # 11) Bloc CAO / SolidWorks
        # ---------------------------------------------------------------------
        d_cao = d_ref if d_ref is not None else rapport["dimensions_requises"].get("d_interieur_requis_m")
        B_cao = B_ref if B_ref is not None else rapport["dimensions_requises"].get("B_requis_m")
        D_cao = D_ref if D_ref is not None else rapport.get("geometrie_estimee", {}).get("D_exterieur_estime_m")

        v_periph = _vitesse_peripherique(float(d_cao), float(rpm)) if (d_cao is not None and rpm is not None) else None

        chanfrein = None
        rayon = None
        if d_cao is not None:
            chanfrein = _borne(
                0.03 * float(d_cao),
                self.regles_geometrie.chanfrein_min_m,
                self.regles_geometrie.chanfrein_max_m,
            )
            rayon = _borne(
                0.02 * float(d_cao),
                self.regles_geometrie.rayon_min_m,
                self.regles_geometrie.rayon_max_m,
            )

        rapport["cao"] = {
            "type_roulement": self.type_roulement,
            "d_interieur_nominal_m": d_cao,
            "D_exterieur_nominal_m": D_cao,
            "B_largeur_nominale_m": B_cao,
            "diametre_aiguille_m": self.diametre_aiguille_m if self.diametre_aiguille_m is not None else rapport.get("geometrie_estimee", {}).get("diametre_aiguille_m"),
            "nb_aiguilles": self.nb_aiguilles if self.nb_aiguilles is not None else rapport.get("geometrie_estimee", {}).get("nb_aiguilles"),
            "longueur_utile_aiguille_m": rapport.get("geometrie_estimee", {}).get("longueur_utile_aiguille_m"),
            "diametre_pitch_m": rapport.get("geometrie_estimee", {}).get("diametre_pitch_m"),
            "epaisseur_bague_interieure_radiale_m": self.epaisseur_bague_interieure_radiale_m,
            "epaisseur_bague_exterieure_radiale_m": self.epaisseur_bague_exterieure_radiale_m,
            "jeu_radial_fonctionnel_m": self.jeu_radial_fonctionnel_m,
            "chanfrein_recommande_m": chanfrein,
            "rayon_recommande_m": rayon,
            "rugosite_portees_ra_um": self.regles_geometrie.rugosite_portees_ra_um,
            "rugosite_logement_ra_um": self.regles_geometrie.rugosite_logement_ra_um,
            "tolerance_diametre_m": self.regles_geometrie.tolerance_diametre_m,
            "tolerance_largeur_m": self.regles_geometrie.tolerance_largeur_m,
            "vitesse_peripherique_m_s": v_periph,
            "note": "Bloc CAO : si D/B exacts ne sont pas fournis par catalogue, les valeurs sont des exigences ou estimations géométriques explicites.",
        }

        # ---------------------------------------------------------------------
        # 12) Entrées
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "rpm_vilebrequin": self.rpm_vilebrequin,
            "vie_cible_heures": self.vie_cible_heures,
            "exposant_p_iso281": self.exposant_p_iso281,
            "facteur_application_Ka": self.facteur_application_Ka,
            "facteur_fiablete_a1": self.facteur_fiablete_a1,
            "facteur_contamination_a23": self.facteur_contamination_a23,
            "charge_equivalente_P_N": self.charge_equivalente_P_N,
            "charge_statique_P0_N": self.charge_statique_P0_N,
            "facteur_securite_stat": self.facteur_securite_stat,
            "diametre_maneton_m": self.diametre_maneton_m,
            "largeur_portee_grande_tete_m": self.largeur_portee_grande_tete_m,
            "force_bielle_max_N": self.force_bielle_max_N,
            "type_roulement": self.type_roulement,
            "diametre_aiguille_m": self.diametre_aiguille_m,
            "nb_aiguilles": self.nb_aiguilles,
            "longueur_aiguille_m": self.longueur_aiguille_m,
            "epaisseur_bague_interieure_radiale_m": self.epaisseur_bague_interieure_radiale_m,
            "epaisseur_bague_exterieure_radiale_m": self.epaisseur_bague_exterieure_radiale_m,
            "jeu_radial_fonctionnel_m": self.jeu_radial_fonctionnel_m,
            "diametre_aiguille_candidates_m": self.diametre_aiguille_candidates_m,
            "nb_aiguilles_candidates": self.nb_aiguilles_candidates,
            "epaisseur_bague_interieure_candidates_m": self.epaisseur_bague_interieure_candidates_m,
            "epaisseur_bague_exterieure_candidates_m": self.epaisseur_bague_exterieure_candidates_m,
            "jeu_radial_candidates_m": self.jeu_radial_candidates_m,
            "materiau_roulement_cle": self.materiau_roulement_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "module_young_pa": self.module_young_pa,
            "limite_elastique_pa": self.limite_elastique_pa,
            "d_interieur_m": self.d_interieur_m,
            "D_exterieur_m": self.D_exterieur_m,
            "B_largeur_m": self.B_largeur_m,
            "C_dynamique_N": self.C_dynamique_N,
            "C0_statique_N": self.C0_statique_N,
            "vitesse_limite_rpm": self.vitesse_limite_rpm,
            "pression_admissible_pa": self.pression_admissible_pa,
        }

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "RoulementAiguilleArbreVilebrequin(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# =============================================================================
# Exemple minimal
# =============================================================================
if __name__ == "__main__":
    from pprint import pprint

    class CorpsBielleMock:
        def calculer(self, strict: bool = False):
            return {
                "efforts": {"force_axiale_max_N": 15000.0},
                "geometrie": {"grande_tete": {"diametre_maneton_m": 0.030}},
                "contacts_tetes": {"grande_tete": {"longueur_portee_m": 0.020}},
            }

    r = RoulementAiguilleArbreVilebrequin(
        corps_bielle=CorpsBielleMock(),
        rpm_vilebrequin=3000.0,
        vie_cible_heures=4000.0,
        facteur_application_Ka=1.2,
        charge_statique_P0_N=18000.0,
        facteur_securite_stat=1.5,

        # géométrie explicite pour aller au-delà des seules exigences
        type_roulement="avec_bague_exterieure",
        diametre_aiguille_m=0.0025,
        nb_aiguilles=24,
        epaisseur_bague_interieure_radiale_m=0.0000,
        epaisseur_bague_exterieure_radiale_m=0.0015,
        jeu_radial_fonctionnel_m=20e-6,

        # pression admissible si tu veux calculer B_min_pression
        pression_admissible_pa=120e6,
    )

    pprint(r.calculer(strict=False))