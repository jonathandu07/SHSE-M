# backend/pieces/piston.py
# =============================================================================
# PISTON (côté froid) — SHSE-M
# =============================================================================
# Objectif (SolidWorks) : sortir des COTES GEOMETRIQUES exploitables :
# - diamètres piston min/max (si ajustement ISO explicite fourni)
# - jeux min/max (à froid) + jeux min/max (à chaud si alphas + T connus)
# - dimensionnement "mini" (jupe / tête) uniquement si contraintes fournies
# - AJOUT : rainure(s) de joint(s) torique(s) sur Ø extérieur piston
#   -> calculable si (section_joint + squeeze + facteur_largeur) + jeu radial connus
#
# ZÉRO INVENTION :
# - aucun ajustement n’est choisi à ta place : il faut fit_hole/fit_shaft (ex: H7/h6)
# - aucune section ISO 3601 n’est choisie à ta place : il faut section_joint_mm
# - aucune pression admissible / PV admissible n’est inventée : il faut les fournir
# - si une donnée manque -> inconnue listée, pas de valeur “au pif”
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


# Air (viscosité via Sutherland, densité via gaz parfait si pression fournie)
try:
    from backend.ensemble.air import dynamic_viscosity_air_Pa_s  # type: ignore
except Exception:  # pragma: no cover
    dynamic_viscosity_air_Pa_s = None  # type: ignore

# Constante des gaz pour l'air sec (si dispo). Sinon on met une constante explicite.
# (Ce n’est pas une “tolérance”, c’est une constante physique standard.)
R_AIR_J_KG_K = 287.058


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
# ISO 286 (IT grades) — calcul explicite (formule i)
# =============================================================================
_IT_MULT: Dict[int, int] = {
    5: 7, 6: 10, 7: 16, 8: 25, 9: 40, 10: 64, 11: 100, 12: 160, 13: 250, 14: 400, 15: 640, 16: 1000,
}

def iso286_i_um(D_mm: float) -> float:
    D = _req_pos("D_mm", D_mm)
    return 0.45 * (D ** (1.0 / 3.0)) + 0.001 * D

def iso286_IT_um(D_mm: float, grade: int) -> float:
    if grade not in _IT_MULT:
        raise ValueError(f"Grade IT non supporté: {grade}. Supportés: {sorted(_IT_MULT)}")
    return float(_IT_MULT[grade]) * iso286_i_um(D_mm)

def iso286_hole_H(D_mm: float, grade: int) -> Tuple[float, float]:
    # Trou H : EI = 0, ES = IT
    IT = iso286_IT_um(D_mm, grade)
    return (0.0, IT)

def iso286_shaft_h(D_mm: float, grade: int) -> Tuple[float, float]:
    # Arbre h : es = 0, ei = -IT
    IT = iso286_IT_um(D_mm, grade)
    return (-IT, 0.0)


# =============================================================================
# Matériaux : récupération cohérente depuis backend.ensemble.materiaux
# =============================================================================

def _materiau_props(
    cle: Optional[str],
    *,
    mode: Literal["min", "typique", "max"] = "typique",
) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {
        "densite_kg_m3": None,
        "limite_elastique_pa": None,
        "module_young_pa": None,
        "poisson": None,
        "alpha_dilatation_1_k": None,
        "conductivite_w_mk": None,
        # (élastomères) si tu les as dans ta base
        "module_elastomere_pa": None,
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

    # pour les joints : certains projets mettent un champ dédié
    out["module_elastomere_pa"] = valeur(getattr(m, "module_elastomere_pa", None), mode=mode)
    if out["module_elastomere_pa"] is None:
        # fallback possible (si ta base ne distingue pas)
        out["module_elastomere_pa"] = out["module_young_pa"]

    return out


# =============================================================================
# Cinématique : vitesse moyenne piston (fallback explicite)
# =============================================================================

def vitesse_moyenne_piston(course_m: float, rpm: float) -> float:
    # v_moy = 2*course*rpm/60
    return 2.0 * _req_pos("course_m", course_m) * (_req_pos("rpm", rpm, strict=False) / 60.0)


# =============================================================================
# Rainure joint torique (sur piston Ø extérieur) — modèle explicite
# =============================================================================
# Convention géométrique (explicite) :
# - Le piston a un Ø extérieur D_piston (zone hors rainure).
# - La rainure est une gorge annulaire sur Ø extérieur :
#       D_fond_gorge = D_piston - 2 * profondeur_radiale
# - Le cylindre a un Ø d’alésage D_alesage.
# - Le jeu radial c = (D_alesage - D_piston)/2 (si jeu>0).
# - Joint torique : section d (diamètre de tore).
# - Squeeze radial s (0..1) défini par :
#       s = (d - profondeur_radiale - c) / d
#   donc profondeur_radiale = d*(1 - s) - c
# - Largeur gorge axiale = facteur_largeur * d (facteur fourni)
#
# => calculable SI (D_alesage, D_piston, d, s, facteur_largeur) sont connus.

def rainure_profondeur_radiale_m(section_joint_m: float, squeeze: float, jeu_radial_m: float) -> float:
    d = _req_pos("section_joint_m", section_joint_m)
    s = _req_pos("squeeze", squeeze, strict=False)
    if not (0.0 < s < 1.0):
        raise ValueError("squeeze doit être dans (0,1).")
    c = _req_pos("jeu_radial_m", jeu_radial_m, strict=False)
    pr = d * (1.0 - s) - c
    # si pr <= 0 => gorge incohérente (joint “rentre” déjà sans gorge)
    return pr

def rainure_largeur_m(section_joint_m: float, facteur_largeur: float) -> float:
    return _req_pos("facteur_largeur", facteur_largeur) * _req_pos("section_joint_m", section_joint_m)

def volume_gorge_annulaire_m3(D_fond_gorge_m: float, largeur_m: float, profondeur_radiale_m: float) -> float:
    # Modèle “rectangle” : V = périmètre(fond) * largeur * profondeur_radiale
    return _perimetre(_req_pos("D_fond_gorge_m", D_fond_gorge_m)) * _req_pos("largeur_m", largeur_m) * _req_pos("profondeur_radiale_m", profondeur_radiale_m)


# =============================================================================
# Piston
# =============================================================================

@dataclass
class Piston:
    # Liaisons (pour récupérer les données sans les recopier)
    cylindre: Optional[Any] = None  # idéalement backend.pieces.cylindre.Cylindre

    # Matériaux (clés) : piston et cylindre (dilatation)
    materiau_piston_cle: Optional[str] = None
    materiau_cylindre_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"

    # Température de référence (fabrication / métrologie)
    temperature_ref_k: float = 293.15

    # Conditions (si absentes, tentative de lecture sur cylindre)
    pression_max_pa: Optional[float] = None
    temperature_fonctionnement_k: Optional[float] = None

    # Géométrie de base (si absente, lecture sur cylindre)
    alesage_nominal_m: Optional[float] = None
    course_m: Optional[float] = None
    rpm: Optional[float] = None  # utile pour PV & puissance frottement

    # Ajustement ISO 286 (pour D piston min/max). Ex: H7/h6
    fit_hole: Optional[str] = None
    fit_shaft: Optional[str] = None

    # Couronne (tête) : modèle explicite requis
    k_sigma_plaque: Optional[float] = None
    contrainte_admissible_pa: Optional[float] = None
    facteur_securite: float = 2.0
    epaisseur_tete_m: Optional[float] = None

    # Jupe : dimensionnement si effort latéral + p_adm fournis
    effort_lateral_N: Optional[float] = None
    pression_palier_admissible_pa: Optional[float] = None
    longueur_jupe_m: Optional[float] = None

    # Hauteur totale (architecture piston) : non déductible sans modèle
    hauteur_totale_m: Optional[float] = None

    # Masse : simplifiée si densité + volume simplifié
    # (densité depuis matériau piston)

    # ===============================
    # AJOUT : JOINT TORIQUE (rainure sur piston Ø extérieur)
    # ===============================
    nb_joints: Optional[int] = None

    # Joint (aucune valeur par défaut)
    section_joint_mm: Optional[float] = None          # d (mm)
    squeeze: Optional[float] = None                   # s (0..1)
    facteur_largeur_rainure: Optional[float] = None   # largeur = facteur * d

    # Matériau joint (pour estimer pression de contact si tu le veux)
    materiau_joint_cle: Optional[str] = None
    module_elastomere_pa: Optional[float] = None      # override direct
    # Frottement joint
    coeff_frottement_joint: Optional[float] = None
    largeur_bande_contact_joint_m: Optional[float] = None  # bande axiale de contact (si tu veux aire)

    # Usure PV admissible (explicite si tu veux “valider”)
    PV_admissible_pa_ms: Optional[float] = None

    # Fuites (jeu annulaire) : modèle laminaire explicite si ΔP + L_portée donnés
    longueur_portee_etanche_m: Optional[float] = None
    pression_aval_pa: Optional[float] = None  # pression vers laquelle ça fuit

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
            "joints": {},
            "frottements": {},
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
        course = self.course_m

        if self.cylindre is not None:
            # alesage
            for attr in ("alesage_m", "diametre_interieur_m", "diametre_alesage_m"):
                if Dcyl is None and hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        Dcyl = float(v)
                        break
            # pression max
            for attr in ("pression_max_pa", "pression_service_pa", "pression_interne_pa", "pression_cote_froid_pa"):
                if Pmax is None and hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        Pmax = float(v)
                        break
            # température
            for attr in ("temperature_froide_k", "temperature_cote_froid_k", "temperature_fonctionnement_k"):
                if Tfn is None and hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        Tfn = float(v)
                        break
            # course
            for attr in ("course_m", "course_piston_m"):
                if course is None and hasattr(self.cylindre, attr):
                    v = getattr(self.cylindre, attr)
                    if v is not None:
                        course = float(v)
                        break
            # matériau cylindre
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
                "course_m": course,
                "materiau_cle": self.materiau_cylindre_cle,
            }

        # validations
        if Dcyl is None:
            _push_inc(rap, "impossibles", "alesage_nominal_m", "Requis (ou fournir un Cylindre avec alesage_m).")
        else:
            Dcyl = _req_pos("alesage_nominal_m", Dcyl)

        if Pmax is None:
            _push_inc(rap, "partielles", "pression_max_pa", "Utile pour dimensionner la tête / efforts gaz.")
        else:
            Pmax = _req_pos("pression_max_pa", Pmax, strict=False)

        if Tfn is None:
            _push_inc(rap, "partielles", "temperature_fonctionnement_k", "Utile pour dilatations/jeu à chaud.")
        else:
            Tfn = _req_pos("temperature_fonctionnement_k", Tfn)

        if course is None:
            _push_inc(rap, "partielles", "course_m", "Utile pour vitesse moyenne (PV, puissance frottement).")

        # ---------------------------------------------------------------------
        # 2) ISO 286 : bornes alésage + piston si fit_* fournis
        # ---------------------------------------------------------------------
        D_hole_min = D_hole_max = None
        D_piston_min = D_piston_max = None
        D_piston_cao = None

        if Dcyl is not None and self.fit_hole and self.fit_shaft:
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
                _push_inc(rap, "impossibles", "fit_hole", "Seul 'H' supporté ici (EI=0).")
            if shaft_L != "h":
                _push_inc(rap, "impossibles", "fit_shaft", "Seul 'h' supporté ici (es=0).")

            if hole_L == "H" and shaft_L == "h":
                D_mm = Dcyl * 1e3
                EI_h_um, ES_h_um = iso286_hole_H(D_mm, hole_g)
                ei_s_um, es_s_um = iso286_shaft_h(D_mm, shaft_g)

                D_hole_min = Dcyl + (EI_h_um * 1e-6)
                D_hole_max = Dcyl + (ES_h_um * 1e-6)
                D_piston_min = Dcyl + (ei_s_um * 1e-6)
                D_piston_max = Dcyl + (es_s_um * 1e-6)

                jeu_diam_min = D_hole_min - D_piston_max
                jeu_diam_max = D_hole_max - D_piston_min

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
                rap["jeux"]["jeu_radial_min_m"] = 0.5 * jeu_diam_min
                rap["jeux"]["jeu_radial_max_m"] = 0.5 * jeu_diam_max

                D_piston_cao = 0.5 * (D_piston_min + D_piston_max)
                rap["dimensions"]["diametre_piston_cao_centre_m"] = D_piston_cao

                rap["notes_modele"].append(
                    "ISO 286 appliqué avec H/h uniquement (EI=0, es=0). "
                    "Pour d’autres lettres (g6, f7, …), implémenter les déviations fondamentales."
                )
        else:
            _push_inc(
                rap, "impossibles",
                "diametre_piston_min_max",
                "Impossible sans ajustement explicite : fournir fit_hole (ex H7) + fit_shaft (ex h6)."
            )

        # ---------------------------------------------------------------------
        # 3) Thermique : jeu à chaud (dilatation différentielle) si alphas dispo
        # ---------------------------------------------------------------------
        if Dcyl is not None and Tfn is not None:
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

            if (alpha_p is not None and alpha_c is not None and
                D_hole_min is not None and D_hole_max is not None and
                D_piston_min is not None and D_piston_max is not None):
                dT = Tfn - float(self.temperature_ref_k)

                def dil(D_ref: float, a: float) -> float:
                    return D_ref * (1.0 + a * dT)

                D_hole_min_hot = dil(float(D_hole_min), float(alpha_c))
                D_hole_max_hot = dil(float(D_hole_max), float(alpha_c))
                D_pis_min_hot = dil(float(D_piston_min), float(alpha_p))
                D_pis_max_hot = dil(float(D_piston_max), float(alpha_p))

                jeu_diam_min_hot = D_hole_min_hot - D_pis_max_hot
                jeu_diam_max_hot = D_hole_max_hot - D_pis_min_hot

                rap["thermique"]["alesage_min_hot_m"] = D_hole_min_hot
                rap["thermique"]["alesage_max_hot_m"] = D_hole_max_hot
                rap["thermique"]["piston_min_hot_m"] = D_pis_min_hot
                rap["thermique"]["piston_max_hot_m"] = D_pis_max_hot
                rap["thermique"]["jeu_diam_min_hot_m"] = jeu_diam_min_hot
                rap["thermique"]["jeu_diam_max_hot_m"] = jeu_diam_max_hot
                rap["thermique"]["jeu_rad_min_hot_m"] = 0.5 * jeu_diam_min_hot
                rap["thermique"]["jeu_rad_max_hot_m"] = 0.5 * jeu_diam_max_hot

                rap["contraintes"]["non_grippage_hot_ok"] = (jeu_diam_min_hot > 0.0)
            else:
                _push_inc(
                    rap, "partielles",
                    "jeu_chaud",
                    "Calculable si bornes ISO + alpha piston/cylindre + T_fonctionnement_k sont connus."
                )

        # ---------------------------------------------------------------------
        # 4) Couronne (épaisseur tête) : modèle explicite requis
        # ---------------------------------------------------------------------
        if self.epaisseur_tete_m is not None:
            rap["dimensions"]["epaisseur_tete_m"] = _req_pos("epaisseur_tete_m", self.epaisseur_tete_m)
        else:
            if Dcyl is None or Pmax is None or self.k_sigma_plaque is None:
                _push_inc(
                    rap, "partielles",
                    "epaisseur_tete_min_m",
                    "Calculable si (alesage, pression_max, k_sigma_plaque) sont fournis."
                )
            else:
                sigma_adm = self.contrainte_admissible_pa
                if sigma_adm is None:
                    props_p = _materiau_props(self.materiau_piston_cle, mode=self.mode_materiau)
                    Re = props_p["limite_elastique_pa"]
                    if Re is not None:
                        sigma_adm = float(Re) / float(self.facteur_securite)
                        rap["notes_modele"].append("contrainte_admissible déduite de Re/facteur_securite.")
                    else:
                        _push_inc(
                            rap, "partielles",
                            "contrainte_admissible_pa",
                            "Fournir contrainte_admissible_pa ou un matériau piston avec limite_elastique_pa."
                        )
                if sigma_adm is not None:
                    a = 0.5 * Dcyl
                    ksig = _req_pos("k_sigma_plaque", self.k_sigma_plaque, strict=True)
                    tmin = a * math.sqrt(ksig * float(Pmax) / float(sigma_adm))
                    rap["dimensions"]["epaisseur_tete_min_m"] = tmin
                    rap["notes_modele"].append(
                        "Épaisseur tête minimisée via sigma=k*p*(a^2/t^2) (k_sigma_plaque explicite)."
                    )

        # ---------------------------------------------------------------------
        # 5) Jupe : longueur mini si effort latéral + p_adm fournis
        # ---------------------------------------------------------------------
        if self.longueur_jupe_m is not None:
            rap["dimensions"]["longueur_jupe_m"] = _req_pos("longueur_jupe_m", self.longueur_jupe_m)
        else:
            if Dcyl is None or self.effort_lateral_N is None or self.pression_palier_admissible_pa is None:
                _push_inc(
                    rap, "partielles",
                    "longueur_jupe_min_m",
                    "Calculable si (alesage, effort_lateral_N, pression_palier_admissible_pa) sont fournis."
                )
            else:
                F = _req_pos("effort_lateral_N", self.effort_lateral_N, strict=False)
                p_adm = _req_pos("pression_palier_admissible_pa", self.pression_palier_admissible_pa)
                Lmin = F / (_perimetre(Dcyl) * p_adm)
                rap["dimensions"]["longueur_jupe_min_m"] = Lmin
                rap["notes_modele"].append("Longueur jupe minimisée via p_contact = F/(pi*D*L).")

        # ---------------------------------------------------------------------
        # 6) Hauteur totale : non déductible sans architecture (segments/axe/etc.)
        # ---------------------------------------------------------------------
        if self.hauteur_totale_m is not None:
            rap["dimensions"]["hauteur_totale_m"] = _req_pos("hauteur_totale_m", self.hauteur_totale_m)
        else:
            _push_inc(
                rap, "partielles",
                "hauteur_totale_m",
                "Non déductible ici sans modèle d’architecture piston. Fournir hauteur_totale_m."
            )

        # ---------------------------------------------------------------------
        # 7) Masse simplifiée : piston plein (à remplacer par volume CAO réel)
        # ---------------------------------------------------------------------
        props_p = _materiau_props(self.materiau_piston_cle, mode=self.mode_materiau)
        rho = props_p["densite_kg_m3"]
        if rho is None:
            _push_inc(rap, "partielles", "masse_simplifiee_kg", "Calculable si densité matériau piston connue.")
        else:
            if D_piston_cao is not None and rap["dimensions"].get("hauteur_totale_m") is not None:
                h = float(rap["dimensions"]["hauteur_totale_m"])
                V = _vol_cylindre(float(D_piston_cao), h)
                rap["masses"]["volume_simplifie_m3"] = V
                rap["masses"]["masse_simplifiee_kg"] = V * float(rho)
                rap["notes_modele"].append("Masse simplifiée (piston plein) : à remplacer par volume CAO réel.")
            else:
                _push_inc(rap, "partielles", "masse_simplifiee_kg", "Nécessite (diametre_piston_cao_centre_m, hauteur_totale_m).")

        # ---------------------------------------------------------------------
        # 8) AJOUT : Rainure(s) de joint torique sur piston Ø extérieur
        # ---------------------------------------------------------------------
        # On exige au minimum : nb_joints, section_joint_mm, squeeze, facteur_largeur_rainure
        # et un jeu radial (à partir ISO). Sans ça -> pas de rainure calculable.
        if self.nb_joints is None:
            _push_inc(rap, "impossibles", "nb_joints", "Requis pour définir le nombre de rainures.")
            nbj = None
        else:
            nbj = int(self.nb_joints)
            if nbj < 0:
                raise ValueError("nb_joints doit être >= 0.")

        # jeu radial (à froid) pour le modèle de squeeze (il faut un c)
        jeu_radial_ref = rap["jeux"].get("jeu_radial_min_m")
        if jeu_radial_ref is None:
            # on peut aussi utiliser jeu_radial_max_m selon ton choix de pire cas,
            # mais on ne choisit pas à ta place : on signale qu’il faut des bornes.
            _push_inc(
                rap, "impossibles",
                "jeu_radial_ref",
                "Impossible sans bornes ISO (fit_hole/fit_shaft) pour obtenir un jeu radial."
            )

        # calcul rainure si on peut
        if nbj is not None and nbj > 0:
            if (self.section_joint_mm is None or self.squeeze is None or self.facteur_largeur_rainure is None):
                _push_inc(
                    rap, "impossibles",
                    "rainure_joint",
                    "Impossible sans (section_joint_mm, squeeze, facteur_largeur_rainure)."
                )
            elif D_piston_cao is None or Dcyl is None or jeu_radial_ref is None:
                _push_inc(
                    rap, "impossibles",
                    "rainure_joint",
                    "Impossible sans D_piston_cao (via ISO), Dcyl, et jeu_radial_ref."
                )
            else:
                d = _req_pos("section_joint_mm", self.section_joint_mm) * 1e-3
                s = _req_pos("squeeze", self.squeeze, strict=False)
                fw = _req_pos("facteur_largeur_rainure", self.facteur_largeur_rainure)
                c = _req_pos("jeu_radial_ref", float(jeu_radial_ref), strict=False)

                # profondeur radiale selon convention explicitée
                pr = rainure_profondeur_radiale_m(section_joint_m=d, squeeze=s, jeu_radial_m=c)
                w = rainure_largeur_m(section_joint_m=d, facteur_largeur=fw)

                # diamètres rainure
                D_pis = _req_pos("D_piston_cao", float(D_piston_cao))
                D_fond = D_pis - 2.0 * pr

                rap["joints"]["nb_joints"] = nbj
                rap["joints"]["section_joint_m"] = d
                rap["joints"]["squeeze"] = s
                rap["joints"]["jeu_radial_ref_m"] = c
                rap["joints"]["profondeur_radiale_rainure_m"] = pr
                rap["joints"]["largeur_rainure_m"] = w
                rap["joints"]["diametre_piston_zone_hors_rainure_m"] = D_pis
                rap["joints"]["diametre_fond_rainure_m"] = D_fond
                rap["joints"]["volume_gorge_unitaire_m3"] = volume_gorge_annulaire_m3(D_fond, w, pr)
                rap["joints"]["volume_gorges_total_m3"] = rap["joints"]["volume_gorge_unitaire_m3"] * nbj

                # Vérifs géométriques minimales (sans norme cachée)
                rap["joints"]["verif"] = {
                    "profondeur_radiale_positive": (pr > 0.0),
                    "diametre_fond_rainure_positif": (D_fond > 0.0),
                    # squeeze réellement réalisé par la formule (doit retomber sur s)
                    "squeeze_reconstruit": (d - pr - c) / d if d > 0 else None,
                }

                # Estimation pression de contact (optionnelle) : p_contact ~ E * squeeze
                Eel = self.module_elastomere_pa
                if Eel is None and self.materiau_joint_cle:
                    props_j = _materiau_props(self.materiau_joint_cle, mode=self.mode_materiau)
                    Eel = props_j.get("module_elastomere_pa")

                if Eel is not None:
                    Eel = _req_pos("module_elastomere_pa", Eel)
                    p_contact = Eel * s
                    rap["joints"]["module_elastomere_pa"] = Eel
                    rap["joints"]["pression_contact_estimee_pa"] = p_contact
                    rap["notes_modele"].append("Joint : estimation p_contact ~= E * squeeze (modèle simplifié explicite).")

                    # Vérif étanchéité très simple (explicite) : p_contact > pression_max
                    if Pmax is not None:
                        rap["joints"]["etancheite_contact_ok_si_p_contact_sup_pmax"] = (p_contact > float(Pmax))
                else:
                    _push_inc(
                        rap, "partielles",
                        "pression_contact_joint",
                        "Estimable si module_elastomere_pa (ou materiau_joint_cle avec module) est disponible."
                    )

                # Frottement joint (optionnel) : F = mu * p_contact * A_contact
                if (self.coeff_frottement_joint is not None and
                    self.largeur_bande_contact_joint_m is not None):
                    mu = _req_pos("coeff_frottement_joint", self.coeff_frottement_joint, strict=False)
                    b = _req_pos("largeur_bande_contact_joint_m", self.largeur_bande_contact_joint_m)
                    p_contact = rap["joints"].get("pression_contact_estimee_pa")
                    if p_contact is None:
                        _push_inc(
                            rap, "partielles",
                            "frottement_joint",
                            "Calculable si pression_contact_estimee_pa est disponible (module_elastomere + squeeze)."
                        )
                    else:
                        A_contact = _perimetre(D_pis) * b * nbj
                        Ff = mu * float(p_contact) * A_contact
                        rap["frottements"]["joint"] = {
                            "mu": mu,
                            "bande_contact_m": b,
                            "aire_contact_m2": A_contact,
                            "force_frottement_N": Ff,
                            "modele": "F = mu * p_contact * (perimetre * bande * nb_joints)",
                        }

                        # PV (usure) si rpm+course
                        if course is not None and self.rpm is not None:
                            v = vitesse_moyenne_piston(course, self.rpm)
                            PV = float(p_contact) * v
                            rap["frottements"]["joint"]["vitesse_moyenne_ms"] = v
                            rap["frottements"]["joint"]["PV_pa_ms"] = PV
                            if self.PV_admissible_pa_ms is not None:
                                PVadm = _req_pos("PV_admissible_pa_ms", self.PV_admissible_pa_ms)
                                rap["frottements"]["joint"]["PV_admissible_pa_ms"] = PVadm
                                rap["frottements"]["joint"]["PV_ok"] = (PV <= PVadm)
                        else:
                            _push_inc(
                                rap, "partielles",
                                "PV_joint",
                                "Calculable si course_m (ou cylindre.course_m) + rpm sont fournis."
                            )
                else:
                    _push_inc(
                        rap, "partielles",
                        "frottement_joint",
                        "Calculable si (coeff_frottement_joint, largeur_bande_contact_joint_m) + (pression_contact estimée)."
                    )

        elif nbj == 0:
            rap["notes_modele"].append("nb_joints=0 : aucune rainure de joint torique à générer.")

        # ---------------------------------------------------------------------
        # 9) Fuites par jeu annulaire (laminaire) — modèle explicite si ΔP + L
        # ---------------------------------------------------------------------
        # Q ≈ (pi * D * c^3 / (12 * mu * L)) * ΔP
        # -> ici D ~ D_piston_cao, c ~ jeu_radial_min (pire pour grippage/fuite ?)
        if (D_piston_cao is not None and
            rap["jeux"].get("jeu_radial_max_m") is not None and
            self.longueur_portee_etanche_m is not None and
            Pmax is not None and
            self.pression_aval_pa is not None and
            Tfn is not None):
            D = float(D_piston_cao)
            c = float(rap["jeux"]["jeu_radial_max_m"])  # fuite pire au jeu max
            L = _req_pos("longueur_portee_etanche_m", self.longueur_portee_etanche_m)
            P1 = float(Pmax)
            P2 = _req_pos("pression_aval_pa", self.pression_aval_pa, strict=False)
            dP = max(P1 - P2, 0.0)

            if dynamic_viscosity_air_Pa_s is None:
                _push_inc(
                    rap, "partielles",
                    "debit_fuite_m3_s",
                    "Impossible sans viscosité air : fournir un module air.dynamic_viscosity_air_Pa_s(T) ou μ."
                )
            else:
                mu = float(dynamic_viscosity_air_Pa_s(float(Tfn)))
                if mu <= 0:
                    _push_inc(rap, "impossibles", "mu_air", "Viscosité air non positive.")
                else:
                    Q = (math.pi * D * (c ** 3) / (12.0 * mu * L)) * dP
                    rap["fuites"]["modele"] = "Q = (π*D*c^3/(12*μ*L))*ΔP (laminaire, explicite)"
                    rap["fuites"]["D_m"] = D
                    rap["fuites"]["jeu_radial_m"] = c
                    rap["fuites"]["L_portee_m"] = L
                    rap["fuites"]["mu_pa_s"] = mu
                    rap["fuites"]["dP_pa"] = dP
                    rap["fuites"]["debit_fuite_m3_s"] = Q

                    # densité via gaz parfait (explicite) si tu veux mdot
                    rho = P1 / (R_AIR_J_KG_K * float(Tfn)) if float(Tfn) > 0 else None
                    if rho is not None and rho > 0:
                        rap["fuites"]["densite_air_kg_m3_est"] = rho
                        rap["fuites"]["debit_fuite_kg_s_est"] = Q * rho
        else:
            _push_inc(
                rap, "partielles",
                "debit_fuite_m3_s",
                "Calculable si (D_piston via ISO, jeu_radial_max, longueur_portee_etanche_m, pression_max, pression_aval_pa, T) + μ(T) sont connus."
            )

        # ---------------------------------------------------------------------
        # Entrées récap
        # ---------------------------------------------------------------------
        rap["entrees"] = {
            "alesage_nominal_m": self.alesage_nominal_m,
            "course_m": self.course_m,
            "rpm": self.rpm,
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
            "epaisseur_tete_m": self.epaisseur_tete_m,
            "longueur_jupe_m": self.longueur_jupe_m,
            # joints
            "nb_joints": self.nb_joints,
            "section_joint_mm": self.section_joint_mm,
            "squeeze": self.squeeze,
            "facteur_largeur_rainure": self.facteur_largeur_rainure,
            "materiau_joint_cle": self.materiau_joint_cle,
            "module_elastomere_pa": self.module_elastomere_pa,
            "coeff_frottement_joint": self.coeff_frottement_joint,
            "largeur_bande_contact_joint_m": self.largeur_bande_contact_joint_m,
            "PV_admissible_pa_ms": self.PV_admissible_pa_ms,
            # fuites
            "longueur_portee_etanche_m": self.longueur_portee_etanche_m,
            "pression_aval_pa": self.pression_aval_pa,
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
    # Exemple : calcul ISO + rainure joint (si paramètres fournis)
    p = Piston(
        alesage_nominal_m=0.080,
        fit_hole="H7",
        fit_shaft="h6",
        pression_max_pa=15e5,
        temperature_fonctionnement_k=350.0,
        course_m=0.060,
        rpm=1200.0,

        materiau_piston_cle="alu_7075_t6",
        materiau_cylindre_cle="acier_42cd4",

        # Rainure joint torique (EXPLICITE)
        nb_joints=1,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur_rainure=1.5,
        materiau_joint_cle="nbr_70",          # dépend de ta base
        coeff_frottement_joint=0.15,
        largeur_bande_contact_joint_m=0.003,
        PV_admissible_pa_ms=2.0e6,            # EXPLICITE si tu veux vérifier

        # Fuite (EXPLICITE)
        longueur_portee_etanche_m=0.010,
        pression_aval_pa=1e5,
    )

    from pprint import pprint
    pprint(p.analyser(strict=False))
