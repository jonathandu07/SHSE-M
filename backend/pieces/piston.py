# backend/pieces/piston.py
# =============================================================================
# PISTON (côté froid) — SHSE-M
# =============================================================================
# Objectif (SolidWorks) : sortir des COTES GEOMETRIQUES exploitables
# (diamètres min/max, jeux min/max, longueurs mini si contraintes fournies),
# en utilisant les autres pièces/modules quand disponibles, SANS VALEUR CACHÉE.
#
# IMPORTANT "zéro invention" :
# - Aucune tolérance "au pif" : si on applique un ajustement ISO 286, il est
#   explicitement demandé via fit_hole / fit_shaft + grade (ex: H7 / h6).
# - Si tu ne donnes pas l’ajustement, on ne “devine” pas : on calcule uniquement
#   ce qui est déductible du cylindre et des contraintes fournies.
# - Minimisation masse : uniquement quand une contrainte donne une borne (ex:
#   longueur de jupe mini via pression de palier admissible, épaisseur mini via
#   contrainte admissible). Sinon -> inconnue.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal, Tuple
import math

# =============================================================================
# Imports projet (optionnels, robustes)
# =============================================================================

try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


try:
    from backend.pieces.cylindre import Cylindre  # type: ignore
except Exception:  # pragma: no cover
    Cylindre = None  # type: ignore


# =============================================================================
# Helpers robustes
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    if strict and v <= 0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if (not strict) and v < 0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v

def _push_inc(rap: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rap["inconnues"][cat].append({"nom": nom, "raison": raison})

def _dedup_inconnues(rap: Dict[str, Any]) -> None:
    def dedup(lst: list[dict]) -> list[dict]:
        seen: set[tuple[str, str]] = set()
        out: list[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out
    rap["inconnues"]["impossibles"] = dedup(rap["inconnues"]["impossibles"])
    rap["inconnues"]["partielles"] = dedup(rap["inconnues"]["partielles"])


def _aire_disque(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    r = 0.5 * D
    return math.pi * r * r

def _perimetre(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return math.pi * D

def _vol_cylindre(diametre_m: float, hauteur_m: float) -> float:
    return _aire_disque(diametre_m) * _req_pos("hauteur_m", hauteur_m)


# =============================================================================
# ISO 286 (IT grades) — calcul explicite, pas de table cachée
# =============================================================================
# On calcule la tolérance IT via l’unité "i" (µm) :
#   i = 0.45 * D^(1/3) + 0.001 * D   (D en mm)
# puis IT = k * i (k dépend du grade : IT5..IT16)
# (Si tu veux une table ISO officielle complète par paliers de dimensions, il
# faut l’implémenter explicitement : ici, on reste sur la formule standard i.)
#
# LIMITATION assumée :
# - Cette approche utilise D nominal en mm (pas la moyenne géométrique d’un palier).
# - Pour un dimensionnement ultra strict ISO par intervalle, ajoute une fonction
#   "D_moy_paliers" dans ton projet. Ici : zéro invention => pas de paliers cachés.

_IT_MULT: Dict[int, int] = {
    5: 7,
    6: 10,
    7: 16,
    8: 25,
    9: 40,
    10: 64,
    11: 100,
    12: 160,
    13: 250,
    14: 400,
    15: 640,
    16: 1000,
}

def iso286_i_um(D_mm: float) -> float:
    D = _req_pos("D_mm", D_mm)
    return 0.45 * (D ** (1.0 / 3.0)) + 0.001 * D

def iso286_IT_um(D_mm: float, grade: int) -> float:
    if grade not in _IT_MULT:
        raise ValueError(f"Grade IT non supporté: {grade}. Supportés: {sorted(_IT_MULT)}")
    i = iso286_i_um(D_mm)
    return float(_IT_MULT[grade]) * i

def iso286_hole_H(D_mm: float, grade: int) -> Tuple[float, float]:
    """
    Trou H : EI = 0 µm, ES = IT
    Retourne (EI_um, ES_um)
    """
    IT = iso286_IT_um(D_mm, grade)
    return (0.0, IT)

def iso286_shaft_h(D_mm: float, grade: int) -> Tuple[float, float]:
    """
    Arbre h : es = 0 µm, ei = -IT
    Retourne (ei_um, es_um)
    """
    IT = iso286_IT_um(D_mm, grade)
    return (-IT, 0.0)


# =============================================================================
# Matériaux : récupération cohérente depuis materiaux.py
# =============================================================================

def _materiau_props(
    cle: Optional[str],
    *,
    mode: Literal["min", "typique", "max"] = "typique",
) -> Dict[str, Optional[float]]:
    """
    Attend que backend.ensemble.materiaux.get_materiau(cle) renvoie un objet
    (dataclass) avec attributs potentiels.
    On lit via valeur() pour min/typique/max si dispo.
    """
    out: Dict[str, Optional[float]] = {
        "densite_kg_m3": None,
        "limite_elastique_pa": None,
        "module_young_pa": None,
        "poisson": None,
        "alpha_dilatation_1_k": None,
        "conductivite_w_mk": None,
    }
    if not cle or get_materiau is None:
        return out
    m = get_materiau(cle)
    if m is None:
        return out

    out["densite_kg_m3"] = valeur(getattr(m, "densite_kg_m3", None), mode=mode)
    out["limite_elastique_pa"] = valeur(getattr(m, "limite_elastique_pa", None), mode=mode)
    out["module_young_pa"] = valeur(getattr(m, "module_young_pa", None), mode=mode)
    out["poisson"] = valeur(getattr(m, "poisson", None), mode=mode)
    out["alpha_dilatation_1_k"] = valeur(getattr(m, "alpha_dilatation_1_k", None), mode=mode)
    out["conductivite_w_mk"] = valeur(getattr(m, "conductivite_w_mk", None), mode=mode)
    return out


# =============================================================================
# Piston
# =============================================================================

@dataclass
class Piston:
    # Liaisons
    cylindre: Optional[Any] = None  # idéalement backend.pieces.cylindre.Cylindre

    # Matériaux (clés) : piston et cylindre (pour dilatation différentielle)
    materiau_piston_cle: Optional[str] = None
    materiau_cylindre_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"

    # Référence température (fabrication / métrologie)
    temperature_ref_k: float = 293.15  # 20°C (convention explicite)

    # Conditions (si absentes, on tente de les lire sur cylindre)
    pression_max_pa: Optional[float] = None
    temperature_fonctionnement_k: Optional[float] = None

    # Géométrie de base : si non fournie, on tente de lire sur cylindre
    alesage_nominal_m: Optional[float] = None

    # Ajustement ISO 286 (si tu veux calculer D piston min/max automatiquement)
    # Exemple trou/arbre : H7/h6 (trou sur base + arbre)
    fit_hole: Optional[str] = None   # ex: "H7"
    fit_shaft: Optional[str] = None  # ex: "h6"

    # Longueurs et épaisseurs : calculables seulement si contraintes fournies
    hauteur_totale_m: Optional[float] = None  # si tu l’imposes (sinon inconnue)
    # longueur jupe : peut être dimensionnée si effort latéral + p_adm fournis
    effort_lateral_N: Optional[float] = None
    pression_palier_admissible_pa: Optional[float] = None  # contrainte de contact admissible (explicite)
    longueur_jupe_m: Optional[float] = None  # override direct

    # Couronne (tête) : dimensionnable si modèle + contrainte admissible fournis
    # Ici on ne choisit PAS un modèle de plaque à ta place.
    # On te laisse fournir un coefficient explicite k_sigma tel que :
    #   sigma = k_sigma * p * (a^2 / t^2)  =>  t_min = a * sqrt(k_sigma * p / sigma_adm)
    # où a = rayon, p = pression, t = épaisseur.
    k_sigma_plaque: Optional[float] = None
    contrainte_admissible_pa: Optional[float] = None  # ex: Re / FS (à fournir ou déduire)
    facteur_securite: float = 2.0
    epaisseur_tete_m: Optional[float] = None  # override direct

    # Étanchéité / fuite : si tu veux calculer débit par jeu, il faut L_portée et ΔP (explicites)
    longueur_portee_etanche_m: Optional[float] = None
    pression_aval_pa: Optional[float] = None  # pression vers laquelle ça fuit (explicite)

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rap: Dict[str, Any] = {
            "piece": "piston",
            "entrees": {},
            "liaisons": {},
            "iso286": {},
            "dimensions": {},
            "jeux": {},
            "thermique": {},
            "contraintes": {},
            "masses": {},
            "fuites": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # ---------------------------------------------------------------------
        # 1) Récup depuis cylindre si fourni
        # ---------------------------------------------------------------------
        Dcyl = self.alesage_nominal_m
        Pmax = self.pression_max_pa
        Tfn = self.temperature_fonctionnement_k

        if self.cylindre is not None:
            # alesage
            for attr in ("alesage_m", "diametre_interieur_m", "diametre_alesage_m"):
                if Dcyl is None and hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        Dcyl = float(v)
                        break

            # pression max
            for attr in ("pression_max_pa", "pression_interne_pa", "pression_cote_froid_pa"):
                if Pmax is None and hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        Pmax = float(v)
                        break

            # température de fonctionnement côté froid
            for attr in ("temperature_froide_k", "temperature_cote_froid_k", "temperature_fonctionnement_k"):
                if Tfn is None and hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        Tfn = float(v)
                        break

            # matériau cylindre si présent
            if self.materiau_cylindre_cle is None:
                for attr in ("materiau_cle", "materiau", "materiau_cylindre_cle"):
                    if hasattr(self.cylindre, attr):
                        v = getattr(self.cylindre, attr)
                        if v:
                            self.materiau_cylindre_cle = str(v)
                            break

            rap["liaisons"]["cylindre"] = {
                "source": "objet",
                "alesage_nominal_m": Dcyl,
                "pression_max_pa": Pmax,
                "temperature_fonctionnement_k": Tfn,
                "materiau_cle": self.materiau_cylindre_cle,
            }

        # validations
        if Dcyl is None:
            _push_inc(rap, "impossibles", "alesage_nominal_m", "Requis (ou fournir un Cylindre avec alesage_m).")
        else:
            Dcyl = _req_pos("alesage_nominal_m", Dcyl)

        if Pmax is None:
            _push_inc(rap, "partielles", "pression_max_pa", "Utile pour dimensionner la tête (sinon inconnue).")
        else:
            Pmax = _req_pos("pression_max_pa", Pmax)

        if Tfn is None:
            _push_inc(rap, "partielles", "temperature_fonctionnement_k", "Utile pour dilatations/jeu à chaud.")
        else:
            Tfn = _req_pos("temperature_fonctionnement_k", Tfn)

        # ---------------------------------------------------------------------
        # 2) ISO 286 : tolérances trou + piston si fit_* fournis
        # ---------------------------------------------------------------------
        # Pour rester "zéro invention", on ne choisit pas l’ajustement à ta place.
        # Si tu veux une auto-sélection, elle doit être codée avec une règle explicite.
        if Dcyl is not None and self.fit_hole and self.fit_shaft:
            # parse ex: H7 / h6 (on ne supporte que H et h ici, car déviation fondamentale explicite)
            def parse_fit(s: str) -> Tuple[str, int]:
                s = s.strip()
                if len(s) < 2:
                    raise ValueError(f"Fit invalide: {s!r}")
                letter = s[0]
                grade = int(s[1:])
                return letter, grade

            hole_L, hole_g = parse_fit(self.fit_hole)
            shaft_L, shaft_g = parse_fit(self.fit_shaft)

            if hole_L != "H":
                _push_inc(rap, "impossibles", "fit_hole", "Seul 'H' est supporté ici (EI=0).")
            if shaft_L != "h":
                _push_inc(rap, "impossibles", "fit_shaft", "Seul 'h' est supporté ici (es=0).")

            if hole_L == "H" and shaft_L == "h":
                D_mm = Dcyl * 1e3
                EI_h_um, ES_h_um = iso286_hole_H(D_mm, hole_g)
                ei_s_um, es_s_um = iso286_shaft_h(D_mm, shaft_g)

                # limites absolues
                D_hole_min = Dcyl + (EI_h_um * 1e-6)
                D_hole_max = Dcyl + (ES_h_um * 1e-6)
                D_piston_min = Dcyl + (ei_s_um * 1e-6)
                D_piston_max = Dcyl + (es_s_um * 1e-6)

                # jeux diamétraux
                jeu_diam_min = D_hole_min - D_piston_max
                jeu_diam_max = D_hole_max - D_piston_min
                jeu_rad_min = 0.5 * jeu_diam_min
                jeu_rad_max = 0.5 * jeu_diam_max

                rap["iso286"] = {
                    "D_mm": D_mm,
                    "hole": {"fit": self.fit_hole, "EI_um": EI_h_um, "ES_um": ES_h_um},
                    "shaft": {"fit": self.fit_shaft, "ei_um": ei_s_um, "es_um": es_s_um},
                }
                rap["dimensions"]["alesage_min_m"] = D_hole_min
                rap["dimensions"]["alesage_max_m"] = D_hole_max
                rap["dimensions"]["diametre_piston_min_m"] = D_piston_min
                rap["dimensions"]["diametre_piston_max_m"] = D_piston_max
                rap["jeux"]["jeu_diametral_min_m"] = jeu_diam_min
                rap["jeux"]["jeu_diametral_max_m"] = jeu_diam_max
                rap["jeux"]["jeu_radial_min_m"] = jeu_rad_min
                rap["jeux"]["jeu_radial_max_m"] = jeu_rad_max

                # Pour CAO : diamètre “nominal” conseillé = milieu de zone piston
                rap["dimensions"]["diametre_piston_cao_centre_m"] = 0.5 * (D_piston_min + D_piston_max)
                rap["notes_modele"].append(
                    "ISO 286 appliqué avec H/h uniquement : trou EI=0, arbre es=0. "
                    "Pour d’autres lettres (g6, f7, …), il faut implémenter les déviations fondamentales."
                )
        else:
            _push_inc(
                rap,
                "partielles",
                "diametre_piston_min_max_iso",
                "Calculable si alesage_nominal_m + fit_hole (ex H7) + fit_shaft (ex h6) sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 3) Thermique : jeu à chaud (dilatation différentielle)
        # ---------------------------------------------------------------------
        # Si on a diamètres min/max + alpha piston/cyl + ΔT, on calcule le pire cas :
        # - Jeu minimal à chaud = (D_cyl_min_hot - D_piston_max_hot)
        # On utilise un modèle linéaire : D(T)=D_ref*(1+alpha*(T-Tref))
        if Dcyl is not None and Tfn is not None:
            alpha_p = None
            alpha_c = None

            props_p = _materiau_props(self.materiau_piston_cle, mode=self.mode_materiau)
            props_c = _materiau_props(self.materiau_cylindre_cle, mode=self.mode_materiau)
            alpha_p = props_p["alpha_dilatation_1_k"]
            alpha_c = props_c["alpha_dilatation_1_k"]

            rap["thermique"]["alpha_piston_1_k"] = alpha_p
            rap["thermique"]["alpha_cylindre_1_k"] = alpha_c
            rap["thermique"]["T_ref_k"] = self.temperature_ref_k
            rap["thermique"]["T_fonctionnement_k"] = Tfn

            if alpha_p is None:
                _push_inc(rap, "partielles", "alpha_piston_1_k", "Requis pour calculer le jeu à chaud.")
            if alpha_c is None:
                _push_inc(rap, "partielles", "alpha_cylindre_1_k", "Requis pour calculer le jeu à chaud.")

            # si on a déjà des bornes iso
            D_cyl_min = rap["dimensions"].get("alesage_min_m")
            D_cyl_max = rap["dimensions"].get("alesage_max_m")
            D_pis_min = rap["dimensions"].get("diametre_piston_min_m")
            D_pis_max = rap["dimensions"].get("diametre_piston_max_m")

            if (alpha_p is not None and alpha_c is not None and
                D_cyl_min is not None and D_cyl_max is not None and
                D_pis_min is not None and D_pis_max is not None):
                dT = Tfn - float(self.temperature_ref_k)

                def dil(D_ref: float, a: float) -> float:
                    return D_ref * (1.0 + a * dT)

                D_cyl_min_hot = dil(float(D_cyl_min), float(alpha_c))
                D_cyl_max_hot = dil(float(D_cyl_max), float(alpha_c))
                D_pis_min_hot = dil(float(D_pis_min), float(alpha_p))
                D_pis_max_hot = dil(float(D_pis_max), float(alpha_p))

                jeu_diam_min_hot = D_cyl_min_hot - D_pis_max_hot
                jeu_diam_max_hot = D_cyl_max_hot - D_pis_min_hot

                rap["thermique"]["alesage_min_hot_m"] = D_cyl_min_hot
                rap["thermique"]["alesage_max_hot_m"] = D_cyl_max_hot
                rap["thermique"]["piston_min_hot_m"] = D_pis_min_hot
                rap["thermique"]["piston_max_hot_m"] = D_pis_max_hot
                rap["thermique"]["jeu_diam_min_hot_m"] = jeu_diam_min_hot
                rap["thermique"]["jeu_diam_max_hot_m"] = jeu_diam_max_hot
                rap["thermique"]["jeu_rad_min_hot_m"] = 0.5 * jeu_diam_min_hot
                rap["thermique"]["jeu_rad_max_hot_m"] = 0.5 * jeu_diam_max_hot

                rap["contraintes"]["non_grippage_hot_ok"] = (jeu_diam_min_hot > 0.0)
            else:
                _push_inc(
                    rap,
                    "partielles",
                    "jeu_chaud",
                    "Calculable si (tolérances ISO -> bornes) + alpha piston/cylindre + T_fonctionnement_k sont connus.",
                )

        # ---------------------------------------------------------------------
        # 4) Couronne (épaisseur tête) : seulement si modèle explicite donné
        # ---------------------------------------------------------------------
        # sigma = k_sigma * p * (a^2 / t^2) => t_min = a * sqrt(k_sigma * p / sigma_adm)
        # a = rayon ~ D/2
        if self.epaisseur_tete_m is not None:
            rap["dimensions"]["epaisseur_tete_m"] = _req_pos("epaisseur_tete_m", self.epaisseur_tete_m)
        else:
            if Dcyl is None:
                _push_inc(rap, "partielles", "epaisseur_tete_m", "Nécessite au moins alesage_nominal_m.")
            elif Pmax is None:
                _push_inc(rap, "partielles", "epaisseur_tete_m", "Nécessite pression_max_pa (ou source cylindre).")
            elif self.k_sigma_plaque is None:
                _push_inc(
                    rap,
                    "partielles",
                    "epaisseur_tete_m",
                    "Impossible sans modèle explicite : fournir k_sigma_plaque (relation sigma=k*p*(a^2/t^2)).",
                )
            else:
                # sigma_adm
                sigma_adm = self.contrainte_admissible_pa
                if sigma_adm is None:
                    props_p = _materiau_props(self.materiau_piston_cle, mode=self.mode_materiau)
                    Re = props_p["limite_elastique_pa"]
                    if Re is not None:
                        sigma_adm = float(Re) / float(self.facteur_securite)
                        rap["notes_modele"].append("contrainte_admissible déduite de Re/facteur_securite.")
                    else:
                        _push_inc(
                            rap,
                            "partielles",
                            "contrainte_admissible_pa",
                            "Fournir contrainte_admissible_pa ou un matériau piston avec limite_elastique_pa.",
                        )

                if sigma_adm is not None:
                    a = 0.5 * Dcyl
                    ksig = _req_pos("k_sigma_plaque", self.k_sigma_plaque, strict=True)
                    tmin = a * math.sqrt(ksig * Pmax / float(sigma_adm))
                    rap["dimensions"]["epaisseur_tete_min_m"] = tmin
                    rap["notes_modele"].append(
                        "Épaisseur tête minimisée via modèle sigma=k*p*(a^2/t^2) (k_sigma_plaque fourni explicitement)."
                    )

        # ---------------------------------------------------------------------
        # 5) Jupe : longueur mini si effort latéral + pression palier adm fournis
        # ---------------------------------------------------------------------
        # p_contact = F_side / (pi * D * L) => L_min = F_side / (pi * D * p_adm)
        if self.longueur_jupe_m is not None:
            rap["dimensions"]["longueur_jupe_m"] = _req_pos("longueur_jupe_m", self.longueur_jupe_m)
        else:
            if Dcyl is None:
                _push_inc(rap, "partielles", "longueur_jupe_m", "Nécessite alesage_nominal_m.")
            elif self.effort_lateral_N is None:
                _push_inc(rap, "partielles", "longueur_jupe_m", "Nécessite effort_lateral_N (ou une loi bielle-manivelle ailleurs).")
            elif self.pression_palier_admissible_pa is None:
                _push_inc(rap, "partielles", "longueur_jupe_m", "Nécessite pression_palier_admissible_pa (contrainte explicite).")
            else:
                F = _req_pos("effort_lateral_N", self.effort_lateral_N, strict=False)
                p_adm = _req_pos("pression_palier_admissible_pa", self.pression_palier_admissible_pa)
                Lmin = F / (_perimetre(Dcyl) * p_adm)
                rap["dimensions"]["longueur_jupe_min_m"] = Lmin
                rap["notes_modele"].append("Longueur jupe minimisée via p_contact = F/(pi*D*L).")

        # ---------------------------------------------------------------------
        # 6) Hauteur totale : pas déductible sans architecture (segments, axe, etc.)
        # ---------------------------------------------------------------------
        if self.hauteur_totale_m is not None:
            rap["dimensions"]["hauteur_totale_m"] = _req_pos("hauteur_totale_m", self.hauteur_totale_m)
        else:
            _push_inc(
                rap,
                "partielles",
                "hauteur_totale_m",
                "Non déductible ici sans architecture piston (segments, axe, épaulements). Fournir ou créer un module d’architecture.",
            )

        # ---------------------------------------------------------------------
        # 7) Masse : si on a une géométrie minimale et densité
        # ---------------------------------------------------------------------
        props_p = _materiau_props(self.materiau_piston_cle, mode=self.mode_materiau)
        rho = props_p["densite_kg_m3"]
        if rho is None:
            _push_inc(rap, "partielles", "masse_kg", "Calculable si matériau piston (densite_kg_m3) est connu.")
        else:
            # Volume très simplifié : cylindre plein de D_piston_cao et h_totale.
            D_cao = rap["dimensions"].get("diametre_piston_cao_centre_m")
            h = rap["dimensions"].get("hauteur_totale_m")
            if D_cao is not None and h is not None:
                V = _vol_cylindre(float(D_cao), float(h))
                rap["masses"]["volume_simplifie_m3"] = V
                rap["masses"]["masse_simplifiee_kg"] = V * float(rho)
                rap["notes_modele"].append("Masse simplifiée (piston plein) : à remplacer par CAO/volume réel.")
            else:
                _push_inc(rap, "partielles", "masse_kg", "Nécessite (diametre_piston_cao_centre_m, hauteur_totale_m).")

        # ---------------------------------------------------------------------
        # 8) Fuites par jeu annulaire : seulement si ΔP et L_portée explicites
        # ---------------------------------------------------------------------
        # (Le modèle compressible complet dépend de choix explicites -> pas ici.)
        if (self.longueur_portee_etanche_m is not None and
            self.pression_aval_pa is not None and
            rap["jeux"].get("jeu_radial_max_m") is not None and
            Pmax is not None):
            # on ne calcule pas mu ici : ce module doit appeler ton air.py si tu veux.
            _push_inc(
                rap,
                "partielles",
                "debit_fuite",
                "Modèle de fuite non calculé ici sans viscosité μ (à récupérer via air.py) et choix de modèle (laminaire, compressible, etc.).",
            )
        else:
            _push_inc(
                rap,
                "partielles",
                "debit_fuite",
                "Calculable seulement si tu fournis (longueur_portee_etanche_m, pression_aval_pa) + μ (via air.py) + un modèle explicite.",
            )

        # ---------------------------------------------------------------------
        # Entrées récap
        # ---------------------------------------------------------------------
        rap["entrees"] = {
            "alesage_nominal_m": self.alesage_nominal_m,
            "fit_hole": self.fit_hole,
            "fit_shaft": self.fit_shaft,
            "pression_max_pa": self.pression_max_pa,
            "temperature_fonctionnement_k": self.temperature_fonctionnement_k,
            "materiau_piston_cle": self.materiau_piston_cle,
            "materiau_cylindre_cle": self.materiau_cylindre_cle,
            "mode_materiau": self.mode_materiau,
            "temperature_ref_k": self.temperature_ref_k,
            "effort_lateral_N": self.effort_lateral_N,
            "pression_palier_admissible_pa": self.pression_palier_admissible_pa,
            "k_sigma_plaque": self.k_sigma_plaque,
            "contrainte_admissible_pa": self.contrainte_admissible_pa,
            "facteur_securite": self.facteur_securite,
            "hauteur_totale_m": self.hauteur_totale_m,
        }

        _dedup_inconnues(rap)
        if strict and (rap["inconnues"]["impossibles"] or rap["inconnues"]["partielles"]):
            raise ValueError(
                "Piston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rap['inconnues']['impossibles']}\n"
                f"Partielles: {rap['inconnues']['partielles']}"
            )
        return rap


# =============================================================================
# Exemple minimal (aucune valeur cachée)
# =============================================================================
if __name__ == "__main__":
    # Cas typique : on a un cylindre qui fournit alesage/pression/temp.
    # Et on fixe explicitement un ajustement ISO de type H7/h6.
    p = Piston(
        cylindre=None,              # mets un Cylindre(...) réel ici
        alesage_nominal_m=0.080,    # si pas de cylindre objet
        fit_hole="H7",
        fit_shaft="h6",
        materiau_piston_cle="alu_7075_t6",   # dépend de ta base materiaux.py
        materiau_cylindre_cle="acier_42cd4", # idem
        pression_max_pa=15e5,
        temperature_fonctionnement_k=350.0,
        # Pour dimensionner la jupe, il faut une contrainte explicite :
        effort_lateral_N=800.0,
        pression_palier_admissible_pa=5e6,
        # Pour dimensionner la tête, il faut un modèle explicite :
        k_sigma_plaque=0.5,  # exemple : à JUSTIFIER par ton modèle choisi
    )
    from pprint import pprint
    pprint(p.analyser(strict=False))
