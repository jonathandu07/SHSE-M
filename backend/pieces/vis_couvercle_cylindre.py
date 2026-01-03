# backend/pieces/vis_couvercle_cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
import math

# ============================================================
# Imports projet (optionnels) : réduction des inconnues
# ============================================================

# --- Matériaux (pour déduire Re du taraudage / limite admissible) ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# --- Pièces (optionnel : permet de passer des objets Cylindre/Couvercle) ---
try:
    from backend.pieces.cylindre import Cylindre  # type: ignore
except Exception:  # pragma: no cover
    Cylindre = None  # type: ignore

try:
    from backend.pieces.couvercle_cylindre import CouvercleCylindre  # type: ignore
except Exception:  # pragma: no cover
    CouvercleCylindre = None  # type: ignore


# ============================================================
# Helpers
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strictly else v >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: list[dict]) -> list[dict]:
        seen: set[Tuple[str, str]] = set()
        out: list[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


# ============================================================
# Standards simples (ISO métrique, pas "coarse" usuels)
# ============================================================

@dataclass(frozen=True)
class FiletageMetric:
    d_mm: float
    p_mm: float

    @property
    def d_m(self) -> float:
        return self.d_mm * 1e-3

    @property
    def p_m(self) -> float:
        return self.p_mm * 1e-3

    @property
    def designation(self) -> str:
        return f"M{self.d_mm:g}x{self.p_mm:g}"


_METRIC_COARSE_PITCH_MM: Dict[int, float] = {
    2: 0.4,
    2.5: 0.45,
    3: 0.5,
    4: 0.7,
    5: 0.8,
    6: 1.0,
    8: 1.25,
    10: 1.5,
    12: 1.75,
    14: 2.0,
    16: 2.0,
    18: 2.5,
    20: 2.5,
    22: 2.5,
    24: 3.0,
    27: 3.0,
    30: 3.5,
}


def filetage_metric_coarse(d_mm: float) -> FiletageMetric:
    if d_mm not in _METRIC_COARSE_PITCH_MM:
        raise ValueError(f"Pas coarse inconnu pour d_mm={d_mm}. Ajoute-le si besoin.")
    return FiletageMetric(d_mm=float(d_mm), p_mm=float(_METRIC_COARSE_PITCH_MM[d_mm]))


def aire_resistante_traction_vis_m2(d_mm: float, p_mm: float) -> float:
    """
    Aire résistante traction (approx standard ISO métrique):
      As = π/4 * (d - 0.9382 p)^2
    Entrées en mm, sortie en m².
    """
    d = float(d_mm)
    p = float(p_mm)
    deq = d - 0.9382 * p
    if deq <= 0:
        raise ValueError("d - 0.9382*p <= 0 : filetage invalide.")
    As_mm2 = (math.pi / 4.0) * (deq ** 2)
    return As_mm2 * 1e-6


def diametre_pour_cercle_pointe_m(d_mm: float, p_mm: float) -> float:
    """
    Diamètre au pas (pitch diameter) approx (ISO 60°):
      d2 ≈ d - 0.64952 p
    Entrées en mm, sortie en m.
    """
    d = float(d_mm)
    p = float(p_mm)
    d2 = d - 0.64952 * p
    if d2 <= 0:
        raise ValueError("d2 <= 0 : filetage invalide.")
    return d2 * 1e-3


def diametre_percage_taraudage_mm(d_mm: float, p_mm: float) -> float:
    """
    Perçage avant taraudage (règle d'atelier courante):
      d_perc ≈ d - p
    """
    return float(d_mm) - float(p_mm)


def diametre_trou_passant_mm(d_mm: float, jeu_mm: float) -> float:
    """Trou de passage: d_trou = d_nom + jeu."""
    return float(d_mm) + float(jeu_mm)


# ============================================================
# Classes de vis (propriétés mécaniques usuelles)
# ============================================================

ClasseVis = Literal["4.6", "5.8", "8.8", "10.9", "12.9"]


def limite_elastique_vis_pa(classe: ClasseVis) -> float:
    """
    Valeurs usuelles Re (Pa) par classe ISO 898-1.
    """
    mapping_mpa = {
        "4.6": 240.0,
        "5.8": 400.0,
        "8.8": 640.0,
        "10.9": 900.0,
        "12.9": 1080.0,
    }
    return mapping_mpa[classe] * 1e6


# ============================================================
# Modèle : assemblage vis couvercle/cylindre
# ============================================================

@dataclass(frozen=True)
class VisCouvercleCylindre:
    """
    Dimensionnement d'un assemblage couvercle ↔ cylindre par vis.

    - Déduit automatiquement:
      nb_vis, filetage, trous couvercle (passants), taraudages cylindre,
      cercle de perçage et coordonnées.
    - Dimensionnement traction des vis: F_sep = Δp * Aire_ouverture,
      puis F_req = F_sep * facteur_securite_etancheite.
    - Arrachement filets (si matériau taraudage connu): estimation par cisaillement.
    """

    # Références (optionnelles) : objets de ton projet
    cylindre: Optional[Any] = None
    couvercle: Optional[Any] = None

    # Charges
    pression_max_pa: Optional[float] = None
    pression_externe_pa: float = 0.0
    diametre_ouverture_m: Optional[float] = None

    facteur_securite_etancheite: float = 1.0
    facteur_partage_charge: float = 1.0

    # Géométrie dispo
    rayon_externe_couvercle_m: Optional[float] = None
    rayon_externe_cylindre_m: Optional[float] = None
    largeur_bride_cylindre_m: float = 0.0

    # Règles géométriques (paramétrables)
    jeu_trou_passant_mm: float = 1.0
    facteur_distance_bord: float = 1.5
    facteur_espacement: float = 3.0

    # Choix / contraintes
    nb_vis_impose: Optional[int] = None
    d_vis_impose_mm: Optional[float] = None
    classe_vis: ClasseVis = "8.8"
    facteur_securite_vis: float = 2.0
    liste_nb_vis: Tuple[int, ...] = (4, 6, 8, 10, 12, 16, 20, 24)
    liste_d_vis_mm: Tuple[float, ...] = (6, 8, 10, 12, 14, 16, 18, 20)

    # Filets / taraudage
    materiau_taraudage_cle: Optional[str] = None
    facteur_securite_arrachement: float = 2.0
    longueur_engagement_max_m: Optional[float] = None

    # Épaisseurs (pour longueur de vis)
    epaisseur_couvercle_m: Optional[float] = None
    surcote_longueur_vis_m: float = 0.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "charges": {},
            "selection": {},
            "geometrie": {},
            "perçages": {},
            "taraudages": {},
            "implantation": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        cov = self.couvercle
        cyl = self.cylindre

        # --- D_ouverture ---
        D_ouv = self.diametre_ouverture_m
        if D_ouv is None and cov is not None and hasattr(cov, "diametre_ouverture_m"):
            D_ouv = getattr(cov, "diametre_ouverture_m")
        if D_ouv is None:
            _push_inconnue(rapport, "impossibles", "diametre_ouverture_m", "Nécessaire pour calculer l'effort de séparation.")
        else:
            D_ouv = _req_pos("diametre_ouverture_m", D_ouv)

        # --- Pression max ---
        p_max = self.pression_max_pa
        if p_max is None:
            if cov is not None and hasattr(cov, "pression_max_pa"):
                p_max = getattr(cov, "pression_max_pa")
            elif cyl is not None and hasattr(cyl, "pression_max_pa"):
                p_max = getattr(cyl, "pression_max_pa")
        if p_max is None:
            _push_inconnue(rapport, "impossibles", "pression_max_pa", "Nécessaire pour dimensionner les vis.")
        else:
            p_max = _req_pos("pression_max_pa", p_max, strictly=False)

        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        k_seal = _req_pos("facteur_securite_etancheite", self.facteur_securite_etancheite)
        k_part = _req_pos("facteur_partage_charge", self.facteur_partage_charge)

        # --- Rayons externes dispo (pour cercle de perçage) ---
        r_cov_ext = self.rayon_externe_couvercle_m
        if r_cov_ext is None and cov is not None:
            if hasattr(cov, "rayon_externe_m") and getattr(cov, "rayon_externe_m") is not None:
                r_cov_ext = getattr(cov, "rayon_externe_m")
            elif hasattr(cov, "rayon_appui_m") and getattr(cov, "rayon_appui_m") is not None:
                r_cov_ext = getattr(cov, "rayon_appui_m")
        if r_cov_ext is not None:
            r_cov_ext = _req_pos("rayon_externe_couvercle_m", r_cov_ext)
        else:
            _push_inconnue(rapport, "partielles", "rayon_externe_couvercle_m", "Nécessaire pour vérifier l'implantation des vis.")

        r_cyl_ext = self.rayon_externe_cylindre_m
        if r_cyl_ext is not None:
            r_cyl_ext = _req_pos("rayon_externe_cylindre_m", r_cyl_ext)
        else:
            # tentative via cylindre.analyser()
            if cyl is not None and hasattr(cyl, "analyser"):
                try:
                    rep_cyl = cyl.analyser(strict=False)
                    r_cyl_ext = rep_cyl.get("geometrie", {}).get("rayon_externe_m")
                    if r_cyl_ext is not None:
                        r_cyl_ext = _req_pos("rayon_externe_cylindre_m", r_cyl_ext)
                except Exception:
                    r_cyl_ext = None
            if r_cyl_ext is None:
                _push_inconnue(rapport, "partielles", "rayon_externe_cylindre_m", "Nécessaire pour vérifier l'implantation côté cylindre.")

        w_bride = _req_pos("largeur_bride_cylindre_m", self.largeur_bride_cylindre_m, strictly=False)

        # --- épaisseur couvercle (longueur vis) ---
        e_cov = self.epaisseur_couvercle_m
        if e_cov is None and cov is not None and hasattr(cov, "epaisseur_m") and getattr(cov, "epaisseur_m") is not None:
            e_cov = getattr(cov, "epaisseur_m")
        if e_cov is None and cov is not None and hasattr(cov, "analyser"):
            try:
                rep_cov = cov.analyser(strict=False)
                e_cov = rep_cov.get("dimensionnement", {}).get("epaisseur_retenue_m")
            except Exception:
                e_cov = None
        if e_cov is not None:
            e_cov = _req_pos("epaisseur_couvercle_m", e_cov)
        else:
            _push_inconnue(rapport, "partielles", "epaisseur_couvercle_m", "Utile pour calculer la longueur de vis.")

        # --- matériau taraudage (arrachement) ---
        mat_taraudage_cle = self.materiau_taraudage_cle
        if mat_taraudage_cle is None and cyl is not None and hasattr(cyl, "materiau_cle"):
            mat_taraudage_cle = getattr(cyl, "materiau_cle")

        Re_taraudage = None
        if mat_taraudage_cle is not None and get_materiau is not None:
            try:
                m = get_materiau(str(mat_taraudage_cle))
                Re_taraudage = valeur(getattr(m, "limite_elastique_pa", None), "min")
            except Exception as e:
                _push_inconnue(rapport, "partielles", "Re taraudage", f"Impossible de résoudre le matériau '{mat_taraudage_cle}': {e}")
        else:
            _push_inconnue(rapport, "partielles", "Re taraudage", "Arrachement filets calculable si materiau_taraudage_cle est fourni et materiaux.py disponible.")

        # ------------------------------------------------------------
        # 2) Charges (effort séparation)
        # ------------------------------------------------------------
        F_sep = None
        if D_ouv is not None and p_max is not None:
            delta_p = max(0.0, p_max - p_ext)
            A_ouv = math.pi * (0.5 * D_ouv) ** 2
            F_sep = delta_p * A_ouv
            F_req = F_sep * k_seal
            rapport["charges"].update({
                "delta_p_dimensionnement_pa": delta_p,
                "aire_ouverture_m2": A_ouv,
                "force_separation_N": F_sep,
                "force_totale_requise_N": F_req,
                "facteur_securite_etancheite": k_seal,
                "facteur_partage_charge": k_part,
            })
        else:
            _push_inconnue(rapport, "impossibles", "force_separation", "Impossible sans diametre_ouverture_m et pression_max_pa.")

        # ------------------------------------------------------------
        # 3) Sélection nb_vis + filetage (traction)
        # ------------------------------------------------------------
        Re_vis = limite_elastique_vis_pa(self.classe_vis)
        FS_vis = _req_pos("facteur_securite_vis", self.facteur_securite_vis)

        nb_list = (self.nb_vis_impose,) if self.nb_vis_impose is not None else self.liste_nb_vis
        d_list = (self.d_vis_impose_mm,) if self.d_vis_impose_mm is not None else self.liste_d_vis_mm

        best = None  # (n, filetage, As, F_par_vis, sigma_allow)
        if F_sep is not None:
            F_tot = float(rapport["charges"]["force_totale_requise_N"])
            for n in nb_list:
                if n is None:
                    continue
                n = int(n)
                if n <= 0:
                    continue

                F_par_vis = (F_tot * k_part) / n
                sigma_allow = Re_vis / FS_vis
                As_req = F_par_vis / sigma_allow

                for dmm in d_list:
                    if dmm is None:
                        continue
                    try:
                        ft = filetage_metric_coarse(float(dmm))
                    except Exception:
                        continue
                    As = aire_resistante_traction_vis_m2(ft.d_mm, ft.p_mm)
                    if As >= As_req:
                        best = (n, ft, As, F_par_vis, sigma_allow)
                        break
                if best is not None:
                    break

            if best is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "dimensionnement vis",
                    "Aucune combinaison (nb_vis, diamètre) ne satisfait F_par_vis <= As*sigma_allow avec les listes fournies.",
                )
        else:
            _push_inconnue(rapport, "impossibles", "dimensionnement vis", "Pas de charge -> pas de sélection.")

        if best is not None:
            n, ft, As, F_par_vis, sigma_allow = best
            rapport["selection"].update({
                "nb_vis": n,
                "filetage": ft.designation,
                "d_nominal_mm": ft.d_mm,
                "pas_mm": ft.p_mm,
                "aire_resistante_As_m2": As,
                "limite_elastique_vis_pa": Re_vis,
                "sigma_allow_vis_pa": sigma_allow,
                "force_dimensionnement_par_vis_N": F_par_vis,
            })

        # ------------------------------------------------------------
        # 4) Cercle de perçage + trous + taraudage
        # ------------------------------------------------------------
        if best is not None and D_ouv is not None:
            n, ft, _, _, _ = best
            r_ouv = 0.5 * D_ouv

            d_trou_mm = diametre_trou_passant_mm(ft.d_mm, self.jeu_trou_passant_mm)
            d_trou_m = d_trou_mm * 1e-3

            d_bord = self.facteur_distance_bord * d_trou_m
            s_min = self.facteur_espacement * d_trou_m

            r_ext_dispo_candidates = []
            if r_cov_ext is not None:
                r_ext_dispo_candidates.append(r_cov_ext)
            if r_cyl_ext is not None:
                r_ext_dispo_candidates.append(r_cyl_ext + w_bride)
            r_ext_dispo = min(r_ext_dispo_candidates) if r_ext_dispo_candidates else None

            if r_ext_dispo is None:
                _push_inconnue(rapport, "partielles", "implantation", "Impossible de borner le cercle de perçage sans rayons externes.")
            else:
                R_min = r_ouv + d_bord + 0.5 * d_trou_m
                R_max = r_ext_dispo - d_bord - 0.5 * d_trou_m
                R_spacing = (n * s_min) / (2.0 * math.pi)

                R_pc = max(R_min, R_spacing)
                if R_pc > R_max:
                    _push_inconnue(
                        rapport,
                        "impossibles",
                        "cercle de perçage",
                        f"Pas de place: R_min={R_min:.6g} m, R_spacing={R_spacing:.6g} m, R_max={R_max:.6g} m.",
                    )
                else:
                    rapport["geometrie"].update({
                        "rayon_ouverture_m": r_ouv,
                        "rayon_exterieur_disponible_m": r_ext_dispo,
                        "rayon_cercle_percage_m": R_pc,
                        "diametre_cercle_percage_m": 2.0 * R_pc,
                        "distance_bord_m": d_bord,
                        "espacement_arc_min_m": s_min,
                        "rayon_min_m": R_min,
                        "rayon_max_m": R_max,
                        "rayon_min_espacement_m": R_spacing,
                    })

                    pts: List[Dict[str, float]] = []
                    for i in range(n):
                        theta = 2.0 * math.pi * i / n
                        pts.append({
                            "i": i,
                            "theta_rad": theta,
                            "x_m": R_pc * math.cos(theta),
                            "y_m": R_pc * math.sin(theta),
                        })
                    rapport["implantation"]["points_trous"] = pts
                    rapport["implantation"]["angle_pas_deg"] = 360.0 / n

            rapport["perçages"].update({
                "diametre_trou_passant_mm": d_trou_mm,
                "diametre_trou_passant_m": d_trou_m,
                "jeu_trou_passant_mm": float(self.jeu_trou_passant_mm),
            })

            d_perc_mm = diametre_percage_taraudage_mm(ft.d_mm, ft.p_mm)
            rapport["taraudages"].update({
                "filetage": ft.designation,
                "diametre_percage_avant_taraudage_mm": d_perc_mm,
                "diametre_percage_avant_taraudage_m": d_perc_mm * 1e-3,
            })

            # ------------------------------------------------------------
            # 5) Longueur engagement (arrachement filets)
            # ------------------------------------------------------------
            if Re_taraudage is not None:
                tau_allow = 0.577 * float(Re_taraudage) / _req_pos(
                    "facteur_securite_arrachement", self.facteur_securite_arrachement
                )
                d2_m = diametre_pour_cercle_pointe_m(ft.d_mm, ft.p_mm)
                F_par_vis = float(rapport["selection"]["force_dimensionnement_par_vis_N"])
                Le_req = F_par_vis / (math.pi * d2_m * tau_allow)
                Le = max(Le_req, 2.0 * ft.p_m)

                if self.longueur_engagement_max_m is not None:
                    Le_max = _req_pos("longueur_engagement_max_m", self.longueur_engagement_max_m)
                    if Le > Le_max:
                        _push_inconnue(rapport, "impossibles", "longueur engagement", f"{Le:.6g} m > {Le_max:.6g} m dispo.")
                    else:
                        rapport["taraudages"]["longueur_engagement_m"] = Le
                else:
                    rapport["taraudages"]["longueur_engagement_m"] = Le

                rapport["taraudages"]["longueur_engagement_requise_m"] = Le_req
                rapport["taraudages"]["tau_allow_filets_pa"] = tau_allow
                rapport["taraudages"]["d2_pitch_diameter_m"] = d2_m
            else:
                _push_inconnue(rapport, "partielles", "arrachement filets", "Calculable si Re matériau taraudage est connu.")

            # ------------------------------------------------------------
            # 6) Longueur de vis minimale
            # ------------------------------------------------------------
            if e_cov is not None and "longueur_engagement_m" in rapport["taraudages"]:
                rapport["selection"]["longueur_vis_min_m"] = (
                    e_cov + float(rapport["taraudages"]["longueur_engagement_m"]) + float(self.surcote_longueur_vis_m)
                )
            elif e_cov is not None:
                _push_inconnue(rapport, "partielles", "longueur vis", "Longueur vis calculable si longueur_engagement_m est déterminée.")

        # ------------------------------------------------------------
        # 7) Vérif traction (taux d'utilisation)
        # ------------------------------------------------------------
        if best is not None:
            util = float(rapport["selection"]["force_dimensionnement_par_vis_N"]) / (
                float(rapport["selection"]["aire_resistante_As_m2"]) * float(rapport["selection"]["sigma_allow_vis_pa"])
            )
            rapport["verifications"]["utilisation_traction_vis"] = util

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "VisCouvercleCylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# Exemple d'usage (à adapter):
# vis = VisCouvercleCylindre(cylindre=my_cyl, couvercle=my_cov, largeur_bride_cylindre_m=0.02)
# rep = vis.analyser(strict=False)
# print(rep["selection"], rep["taraudages"], rep["perçages"])
