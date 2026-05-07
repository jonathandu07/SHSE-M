# backend/pieces/vis_couvercle_cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List, Sequence
import math

# ============================================================
# Imports projet (optionnels) : réduction des inconnues
# ============================================================

# --- Matériaux (arrachement filets si dispo) ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# --- Pièces (optionnel) ---
try:
    from backend.pieces.cylindre import Cylindre  # type: ignore
except Exception:  # pragma: no cover
    Cylindre = None  # type: ignore

try:
    from backend.pieces.couvercle_cylindre import CouvercleCylindre  # type: ignore
except Exception:  # pragma: no cover
    CouvercleCylindre = None  # type: ignore


# ============================================================
# Helpers robustes
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


def _req_int_ge(name: str, x: Any, nmin: int) -> int:
    if x is None:
        raise ValueError(f"{name} ne doit pas être None.")
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être int (reçu: {x!r}).")
    if x < nmin:
        raise ValueError(f"{name} doit être >= {nmin} (reçu: {x}).")
    return x


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

    rapport["inconnues"]["impossibles"] = dedup(list(rapport["inconnues"].get("impossibles", []) or []))
    rapport["inconnues"]["partielles"] = dedup(list(rapport["inconnues"].get("partielles", []) or []))


# ============================================================
# ISO métrique (pas grossier) — table déterministe
# (mêmes couples que ton couvercle_cylindre.py)
# ============================================================

@dataclass(frozen=True)
class FiletageMetric:
    d_mm: float
    p_mm: float

    @property
    def designation(self) -> str:
        return f"M{self.d_mm:g}x{self.p_mm:g}"

    @property
    def d_m(self) -> float:
        return self.d_mm * 1e-3

    @property
    def p_m(self) -> float:
        return self.p_mm * 1e-3


_METRIC_COARSE_SERIE_MM: List[Tuple[float, float]] = [
    (2.0, 0.4),
    (2.5, 0.45),
    (3.0, 0.5),
    (3.5, 0.6),
    (4.0, 0.7),
    (5.0, 0.8),
    (6.0, 1.0),
    (7.0, 1.0),
    (8.0, 1.25),
    (10.0, 1.5),
    (12.0, 1.75),
    (14.0, 2.0),
    (16.0, 2.0),
    (18.0, 2.5),
    (20.0, 2.5),
    (22.0, 2.5),
    (24.0, 3.0),
    (27.0, 3.0),
    (30.0, 3.5),
    (33.0, 3.5),
    (36.0, 4.0),
    (39.0, 4.0),
    (42.0, 4.5),
    (45.0, 4.5),
    (48.0, 5.0),
    (52.0, 5.0),
    (56.0, 5.5),
    (60.0, 5.5),
    (64.0, 6.0),
]


def filetage_metric_coarse(d_mm: float) -> FiletageMetric:
    d = _req_pos("d_mm", d_mm)
    for dd, pp in _METRIC_COARSE_SERIE_MM:
        if abs(dd - d) < 1e-12:
            return FiletageMetric(d_mm=float(dd), p_mm=float(pp))
    raise ValueError(f"Pas coarse introuvable pour d_mm={d_mm}. Ajoute-le dans _METRIC_COARSE_SERIE_MM si besoin.")


def aire_resistante_traction_vis_m2(d_mm: float, p_mm: float) -> float:
    """
    Aire résistante traction As (approx usuelle ISO 898-1):
      As = (pi/4) * (d - 0.9382*p)^2
    Entrées en mm, sortie en m².
    """
    d = _req_pos("d_mm", d_mm)
    p = _req_pos("p_mm", p_mm)
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
    d = _req_pos("d_mm", d_mm)
    p = _req_pos("p_mm", p_mm)
    d2 = d - 0.64952 * p
    if d2 <= 0:
        raise ValueError("d2 <= 0 : filetage invalide.")
    return d2 * 1e-3


def diametre_percage_taraudage_mm(d_mm: float, p_mm: float) -> float:
    """Perçage avant taraudage (règle atelier courante) : d_perc ≈ d - p."""
    return float(_req_pos("d_mm", d_mm)) - float(_req_pos("p_mm", p_mm))


def diametre_trou_passant_mm(d_mm: float, jeu_mm: float) -> float:
    """Trou de passage: d_trou = d_nom + jeu."""
    return float(_req_pos("d_mm", d_mm)) + float(_req_pos("jeu_mm", jeu_mm, strictly=False))


# ============================================================
# ISO 898-1 (classe de vis) — calcul Re
# ============================================================

ClasseVisISO898 = Literal["4.6", "5.8", "8.8", "10.9", "12.9"]


def limite_elastique_vis_pa_depuis_classe(classe: ClasseVisISO898) -> float:
    """
    ISO 898-1:
      Rm (MPa) = 100 * premier_nombre
      Re (MPa) = 10  * premier_nombre * second_nombre
    Exemple 8.8 => Re = 10*8*8 = 640 MPa
    """
    s = str(classe).strip()
    a_s, b_s = s.split(".", 1)
    a = int(a_s)
    b = int(b_s)
    if a <= 0 or b <= 0:
        raise ValueError(f"classe ISO 898 invalide: {classe!r}")
    Re_MPa = 10.0 * float(a) * float(b)
    return Re_MPa * 1e6


# ============================================================
# Arrachement filets (modèle simple par cisaillement)
# ============================================================

def _tau_admissible_filets_pa(Re_matiere_pa: float, facteur_securite_arrachement: float) -> float:
    # Von Mises : tau_y ≈ 0.577*Re (approx). On applique un FS d'arrachement.
    Re = _req_pos("Re_matiere_pa", Re_matiere_pa)
    FS = _req_pos("facteur_securite_arrachement", facteur_securite_arrachement)
    return 0.577 * Re / FS


def _longueur_engagement_min_par_arrachement(
    *,
    F_par_vis_N: float,
    d2_pitch_m: float,
    tau_allow_pa: float,
    p_m: float,
) -> Dict[str, float]:
    F = _req_pos("F_par_vis_N", F_par_vis_N, strictly=False)
    d2 = _req_pos("d2_pitch_m", d2_pitch_m)
    tau = _req_pos("tau_allow_pa", tau_allow_pa)
    p = _req_pos("p_m", p_m)
    # Aire de cisaillement approx : A = pi * d2 * Le
    Le_req = (F / (math.pi * d2 * tau)) if (math.pi * d2 * tau) > 0 else float("nan")
    # on évite un engagement inférieur à ~2 pas (sinon incohérent d'un point de vue filetage)
    Le_min = max(float(Le_req), 2.0 * p)
    return {"Le_req_m": float(Le_req), "Le_min_m": float(Le_min)}


# ============================================================
# Composant : Vis couvercle-cylindre (pièce du commerce)
# ============================================================

@dataclass(frozen=True)
class VisCouvercleCylindre:
    """
    Dimensionnement d'un assemblage couvercle ↔ cylindre par vis du commerce,
    sans "inventer" de valeurs géométriques de tête (qui dépendent de la norme de vis choisie).

    Ce module calcule, quand c'est possible :
      - Effort de séparation (Δp * aire ouverture)
      - Force totale requise (étanchéité) + partage
      - Choix (nb_vis, filetage M d x p) parmi les listes candidates (ou imposé)
      - Diamètre trous passants, perçage taraudage
      - Cercle de perçage + coordonnées (si rayons externes dispo)
      - Longueur d'engagement minimale contre arrachement (si matériau taraudage connu)
      - Longueur minimale de vis (si épaisseur couvercle connue + engagement)
    """

    # Références projet (optionnelles)
    cylindre: Optional[Any] = None
    couvercle: Optional[Any] = None

    # Entrées minimales (si pas d'objets)
    pression_max_pa: Optional[float] = None
    pression_externe_pa: float = 0.0
    diametre_ouverture_m: Optional[float] = None

    # Facteurs (dimensionnement)
    facteur_securite_etancheite: float = 1.0          # multiplie F_sep
    facteur_partage_charge: float = 1.0               # multiplie F_tot avant répartition
    facteur_securite_vis: float = 2.0                 # Re/FS (admissible traction)

    # Géométrie dispo (pour cercle de perçage)
    rayon_externe_couvercle_m: Optional[float] = None
    rayon_externe_cylindre_m: Optional[float] = None
    largeur_bride_cylindre_m: float = 0.0             # si cylindre+bride

    # Règles géométriques (implantation)
    jeu_trou_passant_mm: float = 1.0                  # si tu ne veux pas de défaut, mets None et fournis explicitement
    facteur_distance_bord: float = 1.5
    facteur_espacement: float = 3.0

    # Choix de vis (pas de valeurs "inventées" : soit imposées, soit explorées via listes)
    nb_vis_impose: Optional[int] = None
    d_vis_impose_mm: Optional[float] = None
    classe_vis_iso898: ClasseVisISO898 = "8.8"

    # Espace de recherche (utilisé seulement si non imposé)
    liste_nb_vis: Tuple[int, ...] = (4, 6, 8, 10, 12, 16, 20, 24)
    liste_d_vis_mm: Tuple[float, ...] = (6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0)

    # Taraudage : matériau (arrachement)
    materiau_taraudage_cle: Optional[str] = None
    facteur_securite_arrachement: float = 2.0
    longueur_engagement_max_m: Optional[float] = None

    # Longueur de vis : empilement
    epaisseur_couvercle_m: Optional[float] = None
    epaisseur_joint_m: Optional[float] = None          # si joint connu
    surcote_longueur_vis_m: float = 0.0                # marge (rondelle, tolérances, dépassement)

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

        # ------------------------------------------------------------
        # 0) D_ouverture et pression (input > objets)
        # ------------------------------------------------------------
        D_ouv = self.diametre_ouverture_m
        if D_ouv is None and cov is not None and hasattr(cov, "diametre_ouverture_m"):
            D_ouv = getattr(cov, "diametre_ouverture_m")

        p_max = self.pression_max_pa
        if p_max is None:
            if cov is not None and hasattr(cov, "pression_max_pa"):
                p_max = getattr(cov, "pression_max_pa")
            elif cyl is not None and hasattr(cyl, "pression_max_pa"):
                p_max = getattr(cyl, "pression_max_pa")

        if D_ouv is None:
            _push_inconnue(rapport, "impossibles", "diametre_ouverture_m", "Nécessaire pour calculer l'effort de séparation.")
        else:
            D_ouv = _req_pos("diametre_ouverture_m", D_ouv)

        if p_max is None:
            _push_inconnue(rapport, "impossibles", "pression_max_pa", "Nécessaire pour dimensionner les vis.")
        else:
            p_max = _req_pos("pression_max_pa", p_max, strictly=False)

        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        k_seal = _req_pos("facteur_securite_etancheite", self.facteur_securite_etancheite)
        k_part = _req_pos("facteur_partage_charge", self.facteur_partage_charge)
        FS_vis = _req_pos("facteur_securite_vis", self.facteur_securite_vis)

        rapport["entrees"].update({
            "diametre_ouverture_m": D_ouv,
            "pression_max_pa": p_max,
            "pression_externe_pa": p_ext,
            "facteur_securite_etancheite": k_seal,
            "facteur_partage_charge": k_part,
            "classe_vis_iso898": self.classe_vis_iso898,
            "facteur_securite_vis": FS_vis,
            "rayon_externe_couvercle_m": self.rayon_externe_couvercle_m,
            "rayon_externe_cylindre_m": self.rayon_externe_cylindre_m,
            "largeur_bride_cylindre_m": self.largeur_bride_cylindre_m,
            "epaisseur_couvercle_m": self.epaisseur_couvercle_m,
            "epaisseur_joint_m": self.epaisseur_joint_m,
            "surcote_longueur_vis_m": self.surcote_longueur_vis_m,
        })

        # ------------------------------------------------------------
        # 1) Charges
        # ------------------------------------------------------------
        F_sep: Optional[float] = None
        F_req: Optional[float] = None
        if D_ouv is not None and p_max is not None:
            delta_p = max(0.0, float(p_max) - float(p_ext))
            A_ouv = math.pi * (0.5 * float(D_ouv)) ** 2
            F_sep = delta_p * A_ouv
            F_req = F_sep * k_seal
            rapport["charges"].update({
                "delta_p_dimensionnement_pa": delta_p,
                "aire_ouverture_m2": A_ouv,
                "force_separation_N": F_sep,
                "force_totale_requise_N": F_req,
            })
        else:
            _push_inconnue(rapport, "impossibles", "force_separation", "Impossible sans diametre_ouverture_m et pression_max_pa.")

        # ------------------------------------------------------------
        # 2) Rayons externes (implantation) : input > objets/analyse
        # ------------------------------------------------------------
        r_cov_ext = self.rayon_externe_couvercle_m
        if r_cov_ext is None and cov is not None:
            if hasattr(cov, "rayon_externe_m") and getattr(cov, "rayon_externe_m") is not None:
                r_cov_ext = getattr(cov, "rayon_externe_m")
            elif hasattr(cov, "rayon_appui_m") and getattr(cov, "rayon_appui_m") is not None:
                r_cov_ext = getattr(cov, "rayon_appui_m")

        if r_cov_ext is not None:
            r_cov_ext = _req_pos("rayon_externe_couvercle_m", r_cov_ext)
        else:
            _push_inconnue(rapport, "partielles", "rayon_externe_couvercle_m", "Nécessaire pour borner le cercle de perçage côté couvercle.")

        r_cyl_ext = self.rayon_externe_cylindre_m
        if r_cyl_ext is None and cyl is not None and hasattr(cyl, "analyser"):
            try:
                rep_cyl = cyl.analyser(strict=False)
                r_cyl_ext = rep_cyl.get("geometrie", {}).get("rayon_externe_m")
            except Exception:
                r_cyl_ext = None

        if r_cyl_ext is not None:
            r_cyl_ext = _req_pos("rayon_externe_cylindre_m", r_cyl_ext)
        else:
            _push_inconnue(rapport, "partielles", "rayon_externe_cylindre_m", "Nécessaire pour borner le cercle de perçage côté cylindre.")

        w_bride = _req_pos("largeur_bride_cylindre_m", self.largeur_bride_cylindre_m, strictly=False)

        # ------------------------------------------------------------
        # 3) Épaisseur couvercle (longueur vis) : input > objets/analyse
        # ------------------------------------------------------------
        e_cov = self.epaisseur_couvercle_m
        if e_cov is None and cov is not None:
            if hasattr(cov, "epaisseur_m") and getattr(cov, "epaisseur_m") is not None:
                e_cov = getattr(cov, "epaisseur_m")
            elif hasattr(cov, "analyser"):
                try:
                    rep_cov = cov.analyser(strict=False)
                    e_cov = rep_cov.get("dimensionnement", {}).get("epaisseur_retenue_m")
                except Exception:
                    e_cov = None

        if e_cov is not None:
            e_cov = _req_pos("epaisseur_couvercle_m", e_cov)
        else:
            _push_inconnue(rapport, "partielles", "epaisseur_couvercle_m", "Nécessaire pour calculer la longueur minimale de vis.")

        e_joint = self.epaisseur_joint_m
        if e_joint is not None:
            e_joint = _req_pos("epaisseur_joint_m", e_joint, strictly=False)

        # ------------------------------------------------------------
        # 4) Matériau taraudage (arrachement) : input > cylindre
        # ------------------------------------------------------------
        mat_taraudage_cle = self.materiau_taraudage_cle
        if mat_taraudage_cle is None and cyl is not None and hasattr(cyl, "materiau_cle"):
            mat_taraudage_cle = getattr(cyl, "materiau_cle")

        Re_taraudage: Optional[float] = None
        if mat_taraudage_cle is not None and get_materiau is not None:
            try:
                m = get_materiau(str(mat_taraudage_cle))
                # on essaye plusieurs champs possibles (selon ton implémentation)
                # - si ton Materiau a une méthode limite_elastique_effective_pa(mode=...), elle est la plus fiable
                Re_candidates: List[float] = []

                if hasattr(m, "limite_elastique_effective_pa") and callable(getattr(m, "limite_elastique_effective_pa")):
                    v = m.limite_elastique_effective_pa(mode="min", section_mm=None)
                    if v is not None:
                        Re_candidates.append(float(v))

                for attr in ("limite_elastique_pa", "rp02_pa", "rp02_pa_min"):
                    v2 = getattr(m, attr, None)
                    v2f = valeur(v2, "min") if v2 is not None else None
                    if v2f is not None:
                        Re_candidates.append(float(v2f))

                Re_taraudage = min(Re_candidates) if Re_candidates else None
            except Exception as e:
                _push_inconnue(rapport, "partielles", "Re taraudage", f"Impossible de résoudre le matériau '{mat_taraudage_cle}': {e!r}")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "Re taraudage",
                "Arrachement filets calculable si materiau_taraudage_cle est fourni et materiaux.py disponible.",
            )

        # ------------------------------------------------------------
        # 5) Sélection nb_vis + filetage (traction)
        # ------------------------------------------------------------
        best: Optional[Dict[str, Any]] = None
        if F_req is not None:
            Re_vis = limite_elastique_vis_pa_depuis_classe(self.classe_vis_iso898)
            sigma_allow = Re_vis / FS_vis

            # si imposés -> on ne “devine” rien
            nb_list: Sequence[int] = (self.nb_vis_impose,) if self.nb_vis_impose is not None else self.liste_nb_vis
            d_list: Sequence[float] = (self.d_vis_impose_mm,) if self.d_vis_impose_mm is not None else self.liste_d_vis_mm

            for n in nb_list:
                if n is None:
                    continue
                n_i = int(n)
                if n_i <= 0:
                    continue

                F_par_vis = (float(F_req) * k_part) / float(n_i)
                As_req = F_par_vis / float(sigma_allow) if sigma_allow > 0 else float("inf")

                for dmm in d_list:
                    if dmm is None:
                        continue
                    try:
                        ft = filetage_metric_coarse(float(dmm))
                        As = aire_resistante_traction_vis_m2(ft.d_mm, ft.p_mm)
                    except Exception:
                        continue

                    if As >= As_req:
                        best = {
                            "nb_vis": n_i,
                            "filetage": ft,
                            "As_m2": float(As),
                            "As_req_m2": float(As_req),
                            "F_par_vis_N": float(F_par_vis),
                            "Re_vis_pa": float(Re_vis),
                            "sigma_allow_pa": float(sigma_allow),
                        }
                        break

                if best is not None:
                    break

            if best is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "dimensionnement vis",
                    "Aucune combinaison (nb_vis, diamètre) ne satisfait la traction avec les listes fournies / imposées.",
                )
        else:
            _push_inconnue(rapport, "impossibles", "dimensionnement vis", "Pas de charge -> pas de sélection.")

        if best is not None:
            ft: FiletageMetric = best["filetage"]
            rapport["selection"].update({
                "nb_vis": best["nb_vis"],
                "classe_vis_iso898": self.classe_vis_iso898,
                "limite_elastique_vis_pa": best["Re_vis_pa"],
                "sigma_allow_vis_pa": best["sigma_allow_pa"],
                "filetage": ft.designation,
                "d_nominal_mm": ft.d_mm,
                "pas_mm": ft.p_mm,
                "aire_resistante_As_m2": best["As_m2"],
                "aire_resistante_As_req_m2": best["As_req_m2"],
                "force_dimensionnement_par_vis_N": best["F_par_vis_N"],
            })

        # ------------------------------------------------------------
        # 6) Perçages / taraudages / cercle de perçage
        # ------------------------------------------------------------
        if best is not None and D_ouv is not None:
            ft = best["filetage"]
            n = int(best["nb_vis"])
            r_ouv = 0.5 * float(D_ouv)

            # trous passants couvercle
            # (si tu refuses tout défaut, impose jeu_trou_passant_mm explicitement)
            d_trou_mm = diametre_trou_passant_mm(ft.d_mm, float(self.jeu_trou_passant_mm))
            d_trou_m = d_trou_mm * 1e-3
            rapport["perçages"].update({
                "diametre_trou_passant_mm": float(d_trou_mm),
                "diametre_trou_passant_m": float(d_trou_m),
                "jeu_trou_passant_mm": float(self.jeu_trou_passant_mm),
            })

            # taraudage cylindre : perçage
            d_perc_mm = diametre_percage_taraudage_mm(ft.d_mm, ft.p_mm)
            rapport["taraudages"].update({
                "filetage": ft.designation,
                "diametre_percage_avant_taraudage_mm": float(d_perc_mm),
                "diametre_percage_avant_taraudage_m": float(d_perc_mm) * 1e-3,
            })

            # cercle de perçage : nécessite un rayon externe dispo
            r_ext_dispo_candidates: List[float] = []
            if r_cov_ext is not None:
                r_ext_dispo_candidates.append(float(r_cov_ext))
            if r_cyl_ext is not None:
                r_ext_dispo_candidates.append(float(r_cyl_ext) + float(w_bride))
            r_ext_dispo = min(r_ext_dispo_candidates) if r_ext_dispo_candidates else None

            d_bord = float(self.facteur_distance_bord) * float(d_trou_m)
            s_min = float(self.facteur_espacement) * float(d_trou_m)

            if r_ext_dispo is None:
                _push_inconnue(rapport, "partielles", "cercle_percage", "Bornage impossible sans rayon externe (couvercle ou cylindre).")
            else:
                R_min = r_ouv + d_bord + 0.5 * d_trou_m
                R_max = r_ext_dispo - d_bord - 0.5 * d_trou_m
                R_spacing = (n * s_min) / (2.0 * math.pi)
                R_pc = max(R_min, R_spacing)

                if R_pc > R_max:
                    _push_inconnue(
                        rapport,
                        "impossibles",
                        "cercle_percage",
                        f"Pas de place: R_min={R_min:.6g} m, R_spacing={R_spacing:.6g} m, R_max={R_max:.6g} m.",
                    )
                else:
                    rapport["geometrie"].update({
                        "rayon_ouverture_m": float(r_ouv),
                        "rayon_exterieur_disponible_m": float(r_ext_dispo),
                        "rayon_cercle_percage_m": float(R_pc),
                        "diametre_cercle_percage_m": float(2.0 * R_pc),
                        "distance_bord_m": float(d_bord),
                        "espacement_arc_min_m": float(s_min),
                        "rayon_min_m": float(R_min),
                        "rayon_max_m": float(R_max),
                        "rayon_min_espacement_m": float(R_spacing),
                    })

                    pts: List[Dict[str, float]] = []
                    for i in range(n):
                        theta = 2.0 * math.pi * i / n
                        pts.append({
                            "i": float(i),
                            "theta_rad": float(theta),
                            "x_m": float(R_pc * math.cos(theta)),
                            "y_m": float(R_pc * math.sin(theta)),
                        })
                    rapport["implantation"]["points_trous"] = pts
                    rapport["implantation"]["angle_pas_deg"] = float(360.0 / n)

            # ------------------------------------------------------------
            # 7) Engagement (arrachement filets) si matériau taraudage connu
            # ------------------------------------------------------------
            if Re_taraudage is not None:
                tau_allow = _tau_admissible_filets_pa(float(Re_taraudage), float(self.facteur_securite_arrachement))
                d2_m = diametre_pour_cercle_pointe_m(ft.d_mm, ft.p_mm)
                F_par_vis = float(best["F_par_vis_N"])

                eng = _longueur_engagement_min_par_arrachement(
                    F_par_vis_N=F_par_vis,
                    d2_pitch_m=d2_m,
                    tau_allow_pa=tau_allow,
                    p_m=ft.p_m,
                )
                Le = float(eng["Le_min_m"])

                if self.longueur_engagement_max_m is not None:
                    Le_max = _req_pos("longueur_engagement_max_m", self.longueur_engagement_max_m)
                    if Le > Le_max:
                        _push_inconnue(
                            rapport,
                            "impossibles",
                            "longueur_engagement_m",
                            f"Engagement requis {Le:.6g} m > longueur_engagement_max_m {Le_max:.6g} m.",
                        )
                    else:
                        rapport["taraudages"]["longueur_engagement_m"] = Le
                else:
                    rapport["taraudages"]["longueur_engagement_m"] = Le

                rapport["taraudages"].update({
                    "longueur_engagement_requise_m": float(eng["Le_req_m"]),
                    "tau_allow_filets_pa": float(tau_allow),
                    "d2_pitch_diameter_m": float(d2_m),
                    "Re_taraudage_pa_utilisee": float(Re_taraudage),
                })
            else:
                _push_inconnue(rapport, "partielles", "arrachement_filets", "Calculable si le matériau taraudage (Re) est connu.")

            # ------------------------------------------------------------
            # 8) Longueur minimale de vis (désignation commerciale MxP x Lmin)
            #     (sans inventer une norme de tête => on ne donne pas dk/k, etc.)
            # ------------------------------------------------------------
            if e_cov is not None and "longueur_engagement_m" in rapport["taraudages"]:
                stack = float(e_cov) + (float(e_joint) if e_joint is not None else 0.0)
                L_min = stack + float(rapport["taraudages"]["longueur_engagement_m"]) + float(self.surcote_longueur_vis_m)
                rapport["selection"].update({
                    "empilement_prise_en_compte_m": float(stack),
                    "longueur_vis_min_m": float(L_min),
                    "longueur_vis_min_mm": float(L_min * 1e3),
                    "designation_commerciale_min": f"{ft.designation} x {L_min*1e3:.3f} mm (prendre longueur normalisée >=)",
                })
            elif e_cov is None:
                _push_inconnue(rapport, "partielles", "longueur_vis", "Calculable si epaisseur_couvercle_m est connue (ou déductible du couvercle).")
            else:
                _push_inconnue(rapport, "partielles", "longueur_vis", "Calculable si longueur_engagement_m est déterminée (arrachement filets).")

        # ------------------------------------------------------------
        # 9) Vérifications
        # ------------------------------------------------------------
        if best is not None:
            util = float(best["F_par_vis_N"]) / (float(best["As_m2"]) * float(best["sigma_allow_pa"]))
            rapport["verifications"]["utilisation_traction_vis"] = float(util)

        # Couple de serrage: impossible sans coefficient de frottement + diamètre sous tête + stratégie de précharge
        _push_inconnue(
            rapport,
            "impossibles",
            "couple_de_serrage",
            "Impossible sans modèle de frottement (µ filets/portée), type de vis/tête/rondelle et précharge cible.",
        )
        # Géométrie de tête: impossible sans choisir une norme (ISO 4762/4014/...) et une exécution
        _push_inconnue(
            rapport,
            "impossibles",
            "dimensions_tete_vis",
            "Impossible sans spécifier le type/norme de vis (ex: ISO 4762, ISO 4014...) et sa série dimensionnelle.",
        )

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "VisCouvercleCylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# Exemple (à adapter) :
# vis = VisCouvercleCylindre(cylindre=my_cyl, couvercle=my_cov, largeur_bride_cylindre_m=0.02,
#                           materiau_taraudage_cle="acier_x", epaisseur_joint_m=0.001)
# rep = vis.analyser(strict=False)
# print(rep["selection"])
