# backend/pieces/joint_piston.py
# =============================================================================
# JOINT PISTON — étanchéité piston <-> cylindre (côté froid)
# =============================================================================
# Strict "rien inventer" :
# - Ne choisit PAS un standard, un ratio recommandé, ni un type de joint.
# - Calcule tout ce qui est déductible si :
#   * on a un Piston (objet backend.pieces.piston.Piston) et son rapport calculé
#     (piston.analyser()) incluant la géométrie de gorge / CAO
#   * et/ou un Cylindre (alesage_m)
#   * et/ou un joint (ID/CS) explicitement fourni
#
# Ce module sait :
# - reprendre automatiquement la géométrie de gorge calculée dans piston.py
# - reprendre automatiquement les rainures multiples si présentes
# - calculer volume/surface du tore si ID+CS
# - calculer volume de gorge si (Df, w, profondeur)
# - calculer stretch si ID + D_montage
# - calculer squeeze radial si CS + D_cyl + D_fond_gorge
# - calculer aire de contact et frottement si (bande_contact, p_contact, mu)
# - estimer p_contact si module élastomère explicite (ou résoluble via materiaux.py) + squeeze
#
# IMPORTANT :
# - Toute "norme" (ISO 3601, recommandations squeeze/stretch) doit être entrée comme
#   contrainte explicite par l'utilisateur ; sinon ce module ne fait que calculer
#   la géométrie et les grandeurs dérivées.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
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


# =============================================================================
# Helpers
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


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


def _push_inc(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
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


def _perimetre(D_m: float) -> float:
    return math.pi * _req_pos("D_m", D_m)


def _aire_disque(D_m: float) -> float:
    D = _req_pos("D_m", D_m)
    return math.pi * (0.5 * D) ** 2


def _safe_get_dict(d: Any, key: str) -> Dict[str, Any]:
    v = d.get(key, {}) if isinstance(d, dict) else {}
    return v if isinstance(v, dict) else {}


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
        "module_elastomere_pa": None,
    }
    if not cle or get_materiau is None:
        return out

    m = get_materiau(cle)
    if m is None:
        return out

    out["densite_kg_m3"] = valeur(getattr(m, "densite_kg_m3", None), mode=mode)

    # certains jeux de données mettent "module_elastomere_pa", sinon fallback young
    out["module_elastomere_pa"] = valeur(getattr(m, "module_elastomere_pa", None), mode=mode)
    if out["module_elastomere_pa"] is None:
        out["module_elastomere_pa"] = valeur(getattr(m, "module_young_pa", None), mode=mode)

    return out


# =============================================================================
# Géométrie torique
# =============================================================================

def tore_volume_m3(ID_m: float, CS_m: float) -> float:
    IDv = _req_pos("ID_m", ID_m)
    CSv = _req_pos("CS_m", CS_m)
    r = 0.5 * CSv
    R = 0.5 * IDv + r
    return 2.0 * (math.pi ** 2) * R * (r ** 2)


def tore_surface_m2(ID_m: float, CS_m: float) -> float:
    IDv = _req_pos("ID_m", ID_m)
    CSv = _req_pos("CS_m", CS_m)
    r = 0.5 * CSv
    R = 0.5 * IDv + r
    return 4.0 * (math.pi ** 2) * R * r


def tore_diametre_moyen_m(ID_m: float, CS_m: float) -> float:
    IDv = _req_pos("ID_m", ID_m)
    CSv = _req_pos("CS_m", CS_m)
    return IDv + CSv


# =============================================================================
# Résolution depuis piston / cylindre
# =============================================================================

def _resoudre_rapport_piston(
    piston: Optional[Any],
    rapport_piston: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if isinstance(rapport_piston, dict):
        return rapport_piston

    if piston is None:
        return None

    try:
        if hasattr(piston, "analyser") and callable(getattr(piston, "analyser")):
            rep = piston.analyser(strict=False)  # type: ignore[misc]
            return rep if isinstance(rep, dict) else None
    except Exception:
        return None

    return None


def _resoudre_diametre_cylindre(
    cylindre: Optional[Any],
    rapport_piston: Optional[Dict[str, Any]],
    entree_directe: Optional[float],
) -> Tuple[Optional[float], Optional[str]]:
    D_cyl = entree_directe
    source = "entree_directe" if D_cyl is not None else None

    if D_cyl is None and cylindre is not None:
        for attr in ("alesage_m", "diametre_interieur_m", "diametre_alesage_m"):
            if hasattr(cylindre, attr):
                v = getattr(cylindre, attr)
                if v is not None and _is_finite(v):
                    D_cyl = float(v)
                    source = f"cylindre.{attr}"
                    break

    if D_cyl is None and isinstance(rapport_piston, dict):
        dims = _safe_get_dict(rapport_piston, "dimensions")
        liaisons = _safe_get_dict(rapport_piston, "liaisons")
        cyl_l = _safe_get_dict(liaisons, "cylindre")
        cao = _safe_get_dict(dims, "cao")

        for path, v in (
            ("dimensions.cao.diametre_interieur_cylindre_m", cao.get("diametre_interieur_cylindre_m")),
            ("liaisons.cylindre.alesage_nominal_m", cyl_l.get("alesage_nominal_m")),
            ("dimensions.alesage_min_m", dims.get("alesage_min_m")),
        ):
            if v is not None and _is_finite(v):
                D_cyl = float(v)
                source = f"rapport_piston.{path}"
                break

    return D_cyl, source


def _resoudre_geometrie_gorge_depuis_rapport_piston(
    rapport_piston: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "section_joint_m": None,
        "diametre_fond_gorge_m": None,
        "profondeur_gorge_m": None,
        "largeur_gorge_m": None,
        "diametre_montage_joint_m": None,
        "diametre_moyen_joint_monte_m": None,
        "hauteur_radiale_disponible_m": None,
        "pression_contact_estimee_pa": None,
        "bande_contact_m": None,
        "nb_joints": None,
        "rainures": [],
        "sources": {},
    }

    if not isinstance(rapport_piston, dict):
        return out

    joints = _safe_get_dict(rapport_piston, "joints")
    dims = _safe_get_dict(rapport_piston, "dimensions")
    cao = _safe_get_dict(dims, "cao")
    cao_joints = _safe_get_dict(cao, "joints")

    mapping = (
        ("section_joint_m", "section_joint_m"),
        ("diametre_fond_gorge_m", "diametre_fond_rainure_m"),
        ("profondeur_gorge_m", "profondeur_radiale_rainure_m"),
        ("largeur_gorge_m", "largeur_rainure_m"),
        ("diametre_montage_joint_m", "diametre_montage_joint_m"),
        ("diametre_moyen_joint_monte_m", "diametre_moyen_joint_monte_m"),
        ("hauteur_radiale_disponible_m", "hauteur_radiale_disponible_m"),
        ("pression_contact_estimee_pa", "pression_contact_estimee_pa"),
        ("nb_joints", "nb_joints"),
    )

    for out_key, src_key in mapping:
        if joints.get(src_key) is not None:
            out[out_key] = joints.get(src_key)
            out["sources"][out_key] = f"rapport_piston.joints.{src_key}"
        elif cao_joints.get(src_key) is not None:
            out[out_key] = cao_joints.get(src_key)
            out["sources"][out_key] = f"rapport_piston.dimensions.cao.joints.{src_key}"

    rainures = joints.get("rainures")
    if isinstance(rainures, list) and rainures:
        out["rainures"] = rainures
        out["sources"]["rainures"] = "rapport_piston.joints.rainures"
    else:
        rainures = cao.get("rainures")
        if isinstance(rainures, list) and rainures:
            out["rainures"] = rainures
            out["sources"]["rainures"] = "rapport_piston.dimensions.cao.rainures"

    if out["rainures"]:
        r0 = out["rainures"][0]
        if isinstance(r0, dict):
            if out["largeur_gorge_m"] is None and r0.get("largeur_m") is not None:
                out["largeur_gorge_m"] = r0.get("largeur_m")
                out["sources"]["largeur_gorge_m"] = "rapport_piston.rainures[0].largeur_m"
            if out["profondeur_gorge_m"] is None and r0.get("profondeur_radiale_m") is not None:
                out["profondeur_gorge_m"] = r0.get("profondeur_radiale_m")
                out["sources"]["profondeur_gorge_m"] = "rapport_piston.rainures[0].profondeur_radiale_m"
            if out["diametre_fond_gorge_m"] is None and r0.get("diametre_fond_rainure_m") is not None:
                out["diametre_fond_gorge_m"] = r0.get("diametre_fond_rainure_m")
                out["sources"]["diametre_fond_gorge_m"] = "rapport_piston.rainures[0].diametre_fond_rainure_m"
            if out["section_joint_m"] is None and r0.get("section_joint_m") is not None:
                out["section_joint_m"] = r0.get("section_joint_m")
                out["sources"]["section_joint_m"] = "rapport_piston.rainures[0].section_joint_m"
            if out["diametre_montage_joint_m"] is None and r0.get("diametre_montage_joint_m") is not None:
                out["diametre_montage_joint_m"] = r0.get("diametre_montage_joint_m")
                out["sources"]["diametre_montage_joint_m"] = "rapport_piston.rainures[0].diametre_montage_joint_m"
            if out["diametre_moyen_joint_monte_m"] is None and r0.get("diametre_moyen_joint_monte_m") is not None:
                out["diametre_moyen_joint_monte_m"] = r0.get("diametre_moyen_joint_monte_m")
                out["sources"]["diametre_moyen_joint_monte_m"] = "rapport_piston.rainures[0].diametre_moyen_joint_monte_m"
            if out["hauteur_radiale_disponible_m"] is None and r0.get("hauteur_radiale_disponible_m") is not None:
                out["hauteur_radiale_disponible_m"] = r0.get("hauteur_radiale_disponible_m")
                out["sources"]["hauteur_radiale_disponible_m"] = "rapport_piston.rainures[0].hauteur_radiale_disponible_m"
            if out["bande_contact_m"] is None and r0.get("largeur_bande_contact_joint_m") is not None:
                out["bande_contact_m"] = r0.get("largeur_bande_contact_joint_m")
                out["sources"]["bande_contact_m"] = "rapport_piston.rainures[0].largeur_bande_contact_joint_m"

    return out


# =============================================================================
# JointPiston
# =============================================================================

@dataclass(frozen=True)
class JointPiston:
    """
    Joint piston <-> cylindre.

    Par défaut, si ID/CS sont fournis => joint torique (modèle géométrique).
    Sinon, on ne "devine" pas ID/CS.
    """

    piston: Optional[Any] = None
    cylindre: Optional[Any] = None
    rapport_piston: Optional[Dict[str, Any]] = None

    diametre_interieur_joint_m: Optional[float] = None  # ID
    diametre_section_joint_m: Optional[float] = None    # CS

    diametre_fond_gorge_m: Optional[float] = None
    profondeur_gorge_m: Optional[float] = None
    largeur_gorge_m: Optional[float] = None

    diametre_interieur_cylindre_m: Optional[float] = None

    pression_diff_pa: Optional[float] = None
    pression_contact_pa: Optional[float] = None
    coeff_frottement_mu: Optional[float] = None
    largeur_bande_contact_m: Optional[float] = None

    materiau_joint_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    module_elastomere_pa: Optional[float] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "sources": {},
            "geometrie_joint": {},
            "gorge": {},
            "squeeze_stretch": {},
            "efforts": {},
            "frottements": {},
            "matiere": {},
            "coherences": {},
            "rainures": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ---------------------------------------------------------------------
        # 1) Résolution des sources
        # ---------------------------------------------------------------------
        rp = _resoudre_rapport_piston(self.piston, self.rapport_piston)
        gorge_piston = _resoudre_geometrie_gorge_depuis_rapport_piston(rp)
        D_cyl, D_cyl_source = _resoudre_diametre_cylindre(self.cylindre, rp, self.diametre_interieur_cylindre_m)

        if D_cyl_source:
            rapport["sources"]["diametre_interieur_cylindre_m"] = D_cyl_source

        # ---------------------------------------------------------------------
        # 2) Géométrie gorge / rainures
        # ---------------------------------------------------------------------
        D_fond = self.diametre_fond_gorge_m
        prof = self.profondeur_gorge_m
        larg = self.largeur_gorge_m
        rainures = gorge_piston["rainures"]

        if D_fond is None and gorge_piston["diametre_fond_gorge_m"] is not None:
            D_fond = float(gorge_piston["diametre_fond_gorge_m"])
            rapport["sources"]["diametre_fond_gorge_m"] = gorge_piston["sources"].get("diametre_fond_gorge_m", "rapport_piston")

        if prof is None and gorge_piston["profondeur_gorge_m"] is not None:
            prof = float(gorge_piston["profondeur_gorge_m"])
            rapport["sources"]["profondeur_gorge_m"] = gorge_piston["sources"].get("profondeur_gorge_m", "rapport_piston")

        if larg is None and gorge_piston["largeur_gorge_m"] is not None:
            larg = float(gorge_piston["largeur_gorge_m"])
            rapport["sources"]["largeur_gorge_m"] = gorge_piston["sources"].get("largeur_gorge_m", "rapport_piston")

        # ---------------------------------------------------------------------
        # 3) Entrées joint (ID/CS)
        # ---------------------------------------------------------------------
        ID = self.diametre_interieur_joint_m
        CS = self.diametre_section_joint_m

        if CS is None and gorge_piston["section_joint_m"] is not None:
            CS = float(gorge_piston["section_joint_m"])
            rapport["sources"]["diametre_section_joint_m"] = gorge_piston["sources"].get("section_joint_m", "rapport_piston")

        # ---------------------------------------------------------------------
        # 4) Récap entrées
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "diametre_interieur_cylindre_m": D_cyl,
            "diametre_interieur_joint_m": ID,
            "diametre_section_joint_m": CS,
            "diametre_fond_gorge_m": D_fond,
            "profondeur_gorge_m": prof,
            "largeur_gorge_m": larg,
            "pression_diff_pa": self.pression_diff_pa,
            "pression_contact_pa": self.pression_contact_pa,
            "coeff_frottement_mu": self.coeff_frottement_mu,
            "largeur_bande_contact_m": self.largeur_bande_contact_m,
            "materiau_joint_cle": self.materiau_joint_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "module_elastomere_pa": self.module_elastomere_pa,
            "mode_materiau": self.mode_materiau,
        }

        # ---------------------------------------------------------------------
        # 5) Géométrie du joint (tore) si ID+CS
        # ---------------------------------------------------------------------
        V_joint = None
        S_joint = None
        D_moy = None
        perim_moy = None

        if ID is not None and CS is not None:
            IDv = _req_pos("diametre_interieur_joint_m", ID)
            CSv = _req_pos("diametre_section_joint_m", CS)
            V_joint = tore_volume_m3(IDv, CSv)
            S_joint = tore_surface_m2(IDv, CSv)
            D_moy = tore_diametre_moyen_m(IDv, CSv)
            perim_moy = _perimetre(D_moy)
            rapport["geometrie_joint"].update({
                "volume_joint_m3": V_joint,
                "surface_joint_m2": S_joint,
                "diametre_moyen_joint_m": D_moy,
                "perimetre_moyen_joint_m": perim_moy,
                "rayon_section_m": 0.5 * CSv,
            })
        else:
            _push_inc(
                rapport,
                "impossibles",
                "geometrie_joint_torique",
                "Pour calculer la géométrie d’un tore, fournir diametre_interieur_joint_m ET diametre_section_joint_m (ID/CS).",
            )

        # ---------------------------------------------------------------------
        # 6) Géométrie de gorge + volume gorge
        # ---------------------------------------------------------------------
        V_gorge = None
        if D_fond is not None and prof is not None and larg is not None:
            Df = _req_pos("diametre_fond_gorge_m", D_fond)
            pr = _req_pos("profondeur_gorge_m", prof)
            w = _req_pos("largeur_gorge_m", larg)
            perim_fond = _perimetre(Df)
            A_sec = pr * w
            V_gorge = perim_fond * A_sec
            rapport["gorge"].update({
                "perimetre_fond_gorge_m": perim_fond,
                "section_gorge_rect_m2": A_sec,
                "volume_gorge_m3": V_gorge,
            })
            if V_joint is not None and V_gorge > 0:
                rapport["gorge"]["taux_remplissage_volume_joint_sur_gorge"] = V_joint / V_gorge
        else:
            _push_inc(
                rapport,
                "partielles",
                "volume_gorge",
                "Calculable si diametre_fond_gorge_m + profondeur_gorge_m + largeur_gorge_m sont connus (piston.py peut les fournir).",
            )

        # ---------------------------------------------------------------------
        # 7) Stretch (étirement)
        # ---------------------------------------------------------------------
        stretch = None
        D_montage = gorge_piston["diametre_montage_joint_m"]
        if D_montage is None:
            D_montage = D_fond

        if ID is not None:
            IDv = _req_pos("diametre_interieur_joint_m", ID)
            if D_montage is not None:
                Dm = _req_pos("diametre_montage_joint_m", D_montage)
                stretch = (Dm - IDv) / IDv
                rapport["squeeze_stretch"]["diametre_montage_stretch_m"] = Dm
                rapport["squeeze_stretch"]["stretch_fraction"] = stretch
                if gorge_piston["sources"].get("diametre_montage_joint_m"):
                    rapport["sources"]["diametre_montage_stretch_m"] = gorge_piston["sources"]["diametre_montage_joint_m"]
            else:
                _push_inc(
                    rapport,
                    "partielles",
                    "stretch_fraction",
                    "Calculable si diametre_montage_joint_m ou diametre_fond_gorge_m est connu.",
                )

        # ---------------------------------------------------------------------
        # 8) Squeeze (écrasement radial)
        # ---------------------------------------------------------------------
        squeeze = None
        h_dispo = gorge_piston["hauteur_radiale_disponible_m"]
        if h_dispo is None and CS is not None and D_cyl is not None and D_fond is not None:
            CSv = _req_pos("diametre_section_joint_m", CS)
            Dc = _req_pos("diametre_interieur_cylindre_m", D_cyl)
            Df = _req_pos("diametre_fond_gorge_m", D_fond)
            h_dispo = (Dc - Df) / 2.0
            squeeze = (CSv - h_dispo) / CSv
        elif h_dispo is not None and CS is not None:
            CSv = _req_pos("diametre_section_joint_m", CS)
            h_dispo = _req_pos("hauteur_radiale_disponible_m", h_dispo, strictly=False)
            squeeze = (CSv - h_dispo) / CSv

        if squeeze is not None:
            rapport["squeeze_stretch"].update({
                "hauteur_radiale_disponible_m": h_dispo,
                "squeeze_radial_fraction": squeeze,
            })
        else:
            _push_inc(
                rapport,
                "partielles",
                "squeeze_radial_fraction",
                "Calculable si diametre_section_joint_m + diametre_interieur_cylindre_m + diametre_fond_gorge_m sont connus.",
            )

        # ---------------------------------------------------------------------
        # 9) Estimation pression de contact (optionnelle) : p_contact ~= E * squeeze
        # ---------------------------------------------------------------------
        p_contact_est = None
        Eel = self.module_elastomere_pa
        if Eel is None and self.materiau_joint_cle:
            props = _materiau_props(self.materiau_joint_cle, mode=self.mode_materiau)
            Eel = props.get("module_elastomere_pa")

        if squeeze is not None:
            if Eel is not None:
                Eelv = _req_pos("module_elastomere_pa", Eel)
                p_contact_est = Eelv * squeeze
                rapport["matiere"]["module_elastomere_pa"] = Eelv
                rapport["efforts"]["pression_contact_estimee_pa"] = p_contact_est
                rapport["notes_modele"].append("p_contact estimée via modèle explicite p≈E*squeeze (simplifié).")
            else:
                _push_inc(
                    rapport,
                    "partielles",
                    "pression_contact_estimee_pa",
                    "Estimable si module_elastomere_pa (override) ou materiau_joint_cle résoluble (module) est disponible.",
                )

        # ---------------------------------------------------------------------
        # 10) Aire de contact + frottement
        # ---------------------------------------------------------------------
        A_contact = None
        bande_contact = self.largeur_bande_contact_m
        if bande_contact is None and gorge_piston["bande_contact_m"] is not None:
            bande_contact = float(gorge_piston["bande_contact_m"])
            rapport["sources"]["largeur_bande_contact_m"] = gorge_piston["sources"].get("bande_contact_m", "rapport_piston")

        if perim_moy is not None and bande_contact is not None:
            b = _req_pos("largeur_bande_contact_m", bande_contact)
            A_contact = perim_moy * b
            rapport["frottements"]["aire_contact_m2"] = A_contact
            rapport["frottements"]["largeur_bande_contact_m"] = b
        else:
            _push_inc(
                rapport,
                "partielles",
                "aire_contact_m2",
                "Calculable si largeur_bande_contact_m est fournie ET si le joint (ID/CS) est défini.",
            )

        p_use = None
        if self.pression_contact_pa is not None:
            p_use = _req_pos("pression_contact_pa", self.pression_contact_pa, strictly=False)
            rapport["efforts"]["pression_contact_utilisee_pa"] = p_use
            rapport["sources"]["pression_contact_utilisee_pa"] = "entree pression_contact_pa"
        elif p_contact_est is not None:
            p_use = float(p_contact_est)
            rapport["efforts"]["pression_contact_utilisee_pa"] = p_use
            rapport["sources"]["pression_contact_utilisee_pa"] = "estimation E*squeeze"
        elif gorge_piston["pression_contact_estimee_pa"] is not None:
            p_use = _req_pos("pression_contact_pa", gorge_piston["pression_contact_estimee_pa"], strictly=False)
            rapport["efforts"]["pression_contact_utilisee_pa"] = p_use
            rapport["sources"]["pression_contact_utilisee_pa"] = gorge_piston["sources"].get("pression_contact_estimee_pa", "rapport_piston")

        if self.coeff_frottement_mu is not None and p_use is not None and A_contact is not None:
            mu = _req_pos("coeff_frottement_mu", self.coeff_frottement_mu, strictly=False)
            N = p_use * A_contact
            Ff = mu * N
            rapport["frottements"].update({
                "coeff_frottement_mu": mu,
                "effort_normal_estime_N": N,
                "force_frottement_estimee_N": Ff,
                "modele": "F = mu * (p_contact * A_contact)",
            })
        else:
            _push_inc(
                rapport,
                "partielles",
                "force_frottement_estimee_N",
                "Calculable si coeff_frottement_mu + (pression_contact_pa ou E*squeeze) + aire_contact_m2 sont connus.",
            )

        # ---------------------------------------------------------------------
        # 11) Force pression équivalente globale (ordre de grandeur)
        # ---------------------------------------------------------------------
        if self.pression_diff_pa is not None and D_cyl is not None:
            dp = _req_finite("pression_diff_pa", self.pression_diff_pa)
            Dc = _req_pos("diametre_interieur_cylindre_m", D_cyl)
            Aref = _aire_disque(Dc)
            Fp = abs(dp) * Aref
            rapport["efforts"].update({
                "aire_reference_disque_cylindre_m2": Aref,
                "force_pression_equivalente_N": Fp,
                "note": "Ordre de grandeur global Δp * aire cylindre (pas force locale sur joint).",
            })
        else:
            _push_inc(
                rapport,
                "partielles",
                "force_pression_equivalente_N",
                "Calculable si pression_diff_pa et diametre_interieur_cylindre_m sont fournis.",
            )

        # ---------------------------------------------------------------------
        # 12) Matière : densité -> masse si volume joint connu
        # ---------------------------------------------------------------------
        rho = self.densite_kg_m3
        if rho is None and self.materiau_joint_cle:
            props = _materiau_props(self.materiau_joint_cle, mode=self.mode_materiau)
            rho = props.get("densite_kg_m3")

        if rho is not None:
            rhov = _req_pos("densite_kg_m3", rho)
            rapport["matiere"]["densite_kg_m3"] = rhov
            if V_joint is not None:
                rapport["matiere"]["masse_joint_kg"] = rhov * V_joint
            else:
                _push_inc(rapport, "partielles", "masse_joint_kg", "Calculable si volume_joint_m3 est calculable (ID/CS).")
        else:
            _push_inc(
                rapport,
                "impossibles",
                "densite_kg_m3",
                "Impossible sans densite_kg_m3 ou materiau_joint_cle résoluble via materiaux.py.",
            )

        # ---------------------------------------------------------------------
        # 13) Cohérences géométriques simples (sans norme)
        # ---------------------------------------------------------------------
        if squeeze is not None:
            rapport["coherences"]["squeeze_positive"] = (squeeze > 0.0)
            rapport["coherences"]["squeeze_moins_100pct"] = (squeeze < 1.0)
            if squeeze <= 0.0:
                rapport["notes_modele"].append("SQUEEZE <= 0 : pas d'écrasement (risque étanchéité nulle).")
            if squeeze >= 1.0:
                rapport["notes_modele"].append("SQUEEZE >= 1 : montage impossible (écrasement >= 100%).")

        tr = rapport.get("gorge", {}).get("taux_remplissage_volume_joint_sur_gorge")
        if tr is not None:
            rapport["coherences"]["taux_remplissage_le_1"] = (float(tr) <= 1.0)
            if float(tr) > 1.0:
                rapport["notes_modele"].append(
                    "Taux remplissage volume > 1 : joint ne rentre pas dans gorge (modèle gorge rectangulaire)."
                )

        if stretch is not None:
            rapport["coherences"]["stretch_non_negatif"] = (stretch >= 0.0)

        # ---------------------------------------------------------------------
        # 14) Détail des rainures reprises du piston
        # ---------------------------------------------------------------------
        if isinstance(rainures, list) and rainures:
            rapport["rainures"]["nombre_rainures"] = len(rainures)
            rapport["rainures"]["details"] = []

            for i, r in enumerate(rainures, start=1):
                if not isinstance(r, dict):
                    continue

                rr: Dict[str, Any] = {"index": i}
                for key in (
                    "position_centre_depuis_face_tete_m",
                    "position_debut_depuis_face_tete_m",
                    "position_fin_depuis_face_tete_m",
                    "largeur_m",
                    "profondeur_radiale_m",
                    "diametre_fond_rainure_m",
                    "rayon_fond_rainure_m",
                    "diametre_zone_hors_rainure_m",
                    "diametre_interieur_cylindre_m",
                    "hauteur_radiale_disponible_m",
                    "section_joint_m",
                    "squeeze_cible",
                    "squeeze_reconstruit",
                    "diametre_montage_joint_m",
                    "diametre_moyen_joint_monte_m",
                    "largeur_bande_contact_joint_m",
                    "volume_gorge_m3",
                ):
                    if key in r:
                        rr[key] = r[key]

                # stretch local si ID connu
                if ID is not None and r.get("diametre_montage_joint_m") is not None:
                    IDv = _req_pos("diametre_interieur_joint_m", ID)
                    Dm_loc = _req_pos("diametre_montage_joint_m", r["diametre_montage_joint_m"])
                    rr["stretch_fraction"] = (Dm_loc - IDv) / IDv

                # squeeze local si CS connu
                if CS is not None:
                    CSv = _req_pos("diametre_section_joint_m", CS)
                    if r.get("hauteur_radiale_disponible_m") is not None:
                        h_loc = _req_pos("hauteur_radiale_disponible_m", r["hauteur_radiale_disponible_m"], strictly=False)
                        rr["squeeze_radial_fraction"] = (CSv - h_loc) / CSv

                rapport["rainures"]["details"].append(rr)
        else:
            _push_inc(
                rapport,
                "partielles",
                "rainures",
                "Le détail de chaque rainure est disponible si le rapport du piston contient joints.rainures.",
            )

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "JointPiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# =============================================================================
# Exemple minimal
# =============================================================================
if __name__ == "__main__":
    jp = JointPiston(
        rapport_piston=None,  # mets ici le dict retourné par piston.analyser()
        diametre_interieur_cylindre_m=0.080,
        diametre_interieur_joint_m=0.074,
        diametre_section_joint_m=0.003,
        diametre_fond_gorge_m=0.077,
        profondeur_gorge_m=0.0012,
        largeur_gorge_m=0.0045,
        largeur_bande_contact_m=0.003,
        coeff_frottement_mu=0.15,
        pression_contact_pa=2e6,
        materiau_joint_cle="nbr_70",
    )

    from pprint import pprint
    pprint(jp.analyser(strict=False))