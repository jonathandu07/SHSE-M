# backend/modules/moteur_thermique/calcul_cylindree.py
from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

Number = Union[int, float]

# =============================================================================
# Validation (unique, robuste) + utilitaires géométriques
# =============================================================================

def _is_finite_number(x: Any) -> bool:
    # bool est un int en Python -> on l'exclut explicitement
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite_number(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 1) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return x


def aire_disque_depuis_diametre(diametre_m: Number, *, allow_zero: bool = False) -> float:
    """
    Aire d'un disque : A = π * D² / 4
    """
    D = _req_pos("diametre_m", diametre_m, strictly=not allow_zero)
    return (math.pi * (D ** 2)) / 4.0


def rayon_depuis_diametre(diametre_m: Number, *, allow_zero: bool = False) -> float:
    D = _req_pos("diametre_m", diametre_m, strictly=not allow_zero)
    return 0.5 * D


def verifier_hypothese_paroi_mince(
    epaisseur_m: Number,
    rayon_interne_m: Number,
    *,
    ratio_max: float = 0.1,
) -> Dict[str, float]:
    """
    Vérifie l'hypothèse "paroi mince" via le ratio t / r_i.
    Heuristique usuelle : t/r_i <= 0.1 (modifiable via ratio_max).
    """
    t = _req_pos("epaisseur_m", epaisseur_m, strictly=False)
    ri = _req_pos("rayon_interne_m", rayon_interne_m, strictly=True)
    rmax = _req_pos("ratio_max", ratio_max, strictly=True)
    ratio = t / ri
    return {
        "t_over_ri": ratio,
        "ratio_max": rmax,
        "is_thin_wall": 1.0 if ratio <= rmax else 0.0,
    }


# =============================================================================
# Cylindrée + volumes + ratios
# =============================================================================

def calcul_cylindree_unitaire(
    alesage_m: Number,
    course_m: Number,
    *,
    allow_zero: bool = False,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    """
    Cylindrée unitaire (volume balayé) :
      V_d = (π * B² / 4) * S
    """
    B = _req_pos("alesage_m", alesage_m, strictly=not allow_zero)
    S = _req_pos("course_m", course_m, strictly=not allow_zero)

    aire_section = (math.pi * (B ** 2)) / 4.0
    Vd = aire_section * S

    if return_details:
        return {
            "V_d": Vd,
            "alesage_m": B,
            "course_m": S,
            "aire_section_m2": aire_section,
        }
    return Vd


def calcul_cylindree_totale(
    cylindree_unitaire_m3: Number,
    nombre_cylindres: int,
    *,
    allow_zero_cylindres: bool = False,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    """
    Cylindrée totale :
      V_tot = V_unit * N
    """
    V_unit = _req_finite("cylindree_unitaire_m3", cylindree_unitaire_m3)
    N = _req_int_ge("nombre_cylindres", nombre_cylindres, 0 if allow_zero_cylindres else 1)

    V_tot = V_unit * float(N)

    if return_details:
        return {
            "V_tot": V_tot,
            "cylindree_unitaire_m3": V_unit,
            "nombre_cylindres": float(N),
        }
    return V_tot


def calcul_volume_mort(cylindree_unitaire_m3: Number, taux_compression: Number) -> float:
    """
    Volume mort V_c (chambre au PMH) depuis le taux de compression CR :
      CR = (V_d + V_c)/V_c  =>  V_c = V_d / (CR - 1)
    """
    Vd = _req_pos("cylindree_unitaire_m3", cylindree_unitaire_m3, strictly=True)
    CR = _req_finite("taux_compression", taux_compression)
    if CR <= 1.0:
        raise ValueError(f"taux_compression doit être > 1.0 (reçu: {CR}).")
    return Vd / (CR - 1.0)


def calcul_taux_compression(cylindree_unitaire_m3: Number, volume_mort_m3: Number) -> float:
    """
    Taux de compression géométrique :
      CR = (V_d + V_c) / V_c
    """
    Vd = _req_pos("cylindree_unitaire_m3", cylindree_unitaire_m3, strictly=False)
    Vc = _req_pos("volume_mort_m3", volume_mort_m3, strictly=True)
    return (Vd + Vc) / Vc


def calcul_ratio_alesage_course(
    alesage_m: Number,
    course_m: Number,
    return_details: bool = False,
    *,
    tol_carre: float = 0.01,
) -> Union[float, Dict[str, float]]:
    """
    Ratio R = B / S
    Retourne aussi un code d'architecture si return_details=True :
      0.0  = carré (~1)
      -1.0 = longue course (<1)
      1.0  = super-carré (>1)
    """
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    tol = _req_pos("tol_carre", tol_carre, strictly=True)

    ratio = B / S

    if return_details:
        if abs(ratio - 1.0) < tol:
            arch = 0.0
        elif ratio < 1.0:
            arch = -1.0
        else:
            arch = 1.0

        return {
            "ratio": ratio,
            "architecture_code": arch,
            "alesage_m": B,
            "course_m": S,
            "tol_carre": tol,
        }

    return ratio


# =============================================================================
# Force gaz sur piston
# =============================================================================

def calcul_force_gaz(
    pression_pa: Number,
    alesage_m: Number,
    *,
    allow_negative_pression: bool = True,
    allow_zero_alesage: bool = False,
    clamp_non_negative: bool = False,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    """
    Force gaz :
      A_p = π * B² / 4
      F_g = p * A_p
    """
    p = _req_finite("pression_pa", pression_pa)
    if (not allow_negative_pression) and p < 0.0:
        raise ValueError("pression_pa ne peut pas être négative (allow_negative_pression=False).")

    B = _req_pos("alesage_m", alesage_m, strictly=not allow_zero_alesage)

    aire_piston = (math.pi * (B ** 2)) / 4.0
    F = p * aire_piston

    if clamp_non_negative:
        F = max(0.0, F)

    if return_details:
        return {
            "F_g": F,
            "pression_pa": p,
            "alesage_m": B,
            "aire_piston_m2": aire_piston,
        }
    return F


# =============================================================================
# Épaisseur paroi cylindre (mince / Lamé)
# =============================================================================

def calcul_epaisseur_cylindre_mince(
    pression_pa: Number,
    rayon_interne_m: Number,
    contrainte_admissible_pa: Number,
    *,
    include_longitudinale: bool = False,
    facteur_securite: Number = 1.0,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    """
    Paroi mince (contraintes de membrane) :
      σ_θ = p * r_i / t  => t >= p * r_i / σ_eff
      σ_L = p * r_i / (2t) (optionnel)
    avec σ_eff = σ_adm / FS
    """
    p = _req_pos("pression_pa", pression_pa, strictly=False)
    ri = _req_pos("rayon_interne_m", rayon_interne_m, strictly=True)
    sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _req_pos("facteur_securite", facteur_securite, strictly=True)

    sigma_eff = sigma_adm / fs

    t_hoop = (p * ri) / sigma_eff if sigma_eff > 0 else float("inf")
    t_long = (p * ri) / (2.0 * sigma_eff) if sigma_eff > 0 else float("inf")

    t_req = max(t_hoop, t_long) if include_longitudinale else t_hoop
    if clamp_non_negative:
        t_req = max(0.0, t_req)

    if return_details:
        return {
            "t": t_req,
            "t_hoop": t_hoop,
            "t_long": t_long,
            "p": p,
            "ri": ri,
            "sigma_adm": sigma_adm,
            "facteur_securite": fs,
            "sigma_eff": sigma_eff,
            "include_longitudinale": 1.0 if include_longitudinale else 0.0,
        }
    return t_req


def calcul_epaisseur_cylindre_lame(
    pression_interne_pa: Number,
    rayon_interne_m: Number,
    contrainte_admissible_pa: Number,
    *,
    facteur_securite: Number = 1.0,
    epsilon: Number = 1e-12,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    """
    Cylindre épais (Lamé), en limitant σ_θ au rayon interne :
      r_o = r_i * sqrt((σ_eff + p)/(σ_eff - p))
      t = r_o - r_i
    Condition : σ_eff > p (avec marge epsilon).
    """
    p = _req_pos("pression_interne_pa", pression_interne_pa, strictly=False)
    ri = _req_pos("rayon_interne_m", rayon_interne_m, strictly=True)
    sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _req_pos("facteur_securite", facteur_securite, strictly=True)
    eps = _req_pos("epsilon", epsilon, strictly=True)

    sigma_eff = sigma_adm / fs

    if sigma_eff <= p + eps:
        raise ValueError(
            "Dimensionnement impossible/instable: il faut sigma_adm/FS > p (avec marge). "
            f"(sigma_eff={sigma_eff}, p={p})"
        )

    ratio = (sigma_eff + p) / (sigma_eff - p)
    if ratio < 1.0:
        raise ValueError("Ratio Lamé inattendu (<1). Vérifie les paramètres.")

    ro = ri * math.sqrt(ratio)
    t = ro - ri

    if clamp_non_negative:
        t = max(0.0, t)

    if return_details:
        return {
            "t": t,
            "ri": ri,
            "ro": ro,
            "p": p,
            "sigma_adm": sigma_adm,
            "facteur_securite": fs,
            "sigma_eff": sigma_eff,
            "ratio": ratio,
        }
    return t


# =============================================================================
# Helpers "depuis alésage" + auto (sans inventer : on garde les deux modèles)
# =============================================================================

ModeleParoi = Literal["mince", "lame", "auto", "both"]


def calcul_epaisseur_paroi_depuis_alesage(
    pression_pa: Number,
    alesage_m: Number,
    contrainte_admissible_pa: Number,
    *,
    modele: ModeleParoi = "auto",
    facteur_securite: Number = 1.0,
    include_longitudinale: bool = False,
    epsilon: Number = 1e-12,
    ratio_mince_max: float = 0.1,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    """
    Dimensionnement paroi depuis l'alésage (r_i = B/2).

    - modele="mince" : retourne t_mince
    - modele="lame"  : retourne t_lame (sinon erreur si impossible)
    - modele="both"  : retourne un dict avec les deux (t_lame_m = NaN si impossible)
    - modele="auto"  : retourne t_mince si (t_mince/r_i <= ratio_mince_max), sinon t_lame
                       (ratio_mince_max = heuristique paramétrable)
    """
    p = _req_pos("pression_pa", pression_pa, strictly=False)
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _req_pos("facteur_securite", facteur_securite, strictly=True)
    rmax = _req_pos("ratio_mince_max", ratio_mince_max, strictly=True)

    ri = 0.5 * B

    d_mince = calcul_epaisseur_cylindre_mince(
        p,
        ri,
        sigma_adm,
        include_longitudinale=include_longitudinale,
        facteur_securite=fs,
        return_details=True,
    )
    assert isinstance(d_mince, dict)
    t_mince = float(d_mince["t"])
    t_over_ri = (t_mince / ri) if ri > 0 else float("inf")

    out: Dict[str, float] = {
        "alesage_m": B,
        "rayon_interne_m": ri,
        "pression_pa": p,
        "contrainte_admissible_pa": sigma_adm,
        "facteur_securite": float(fs),
        "t_mince_m": t_mince,
        "t_over_ri_mince": t_over_ri,
        "ratio_mince_max": float(rmax),
    }

    t_lame: Optional[float] = None
    d_lame: Optional[Dict[str, float]] = None
    try:
        tmp = calcul_epaisseur_cylindre_lame(
            p,
            ri,
            sigma_adm,
            facteur_securite=fs,
            epsilon=epsilon,
            return_details=True,
        )
        assert isinstance(tmp, dict)
        d_lame = tmp
        t_lame = float(d_lame["t"])
        out.update(
            {
                "t_lame_m": t_lame,
                "ro_lame_m": float(d_lame["ro"]),
                "ratio_lame": float(d_lame["ratio"]),
            }
        )
    except ValueError:
        # Lamé impossible => on n'invente rien : on laisse t_lame absent (ou NaN en mode "both")
        pass

    if modele == "mince":
        return out if return_details else t_mince

    if modele == "lame":
        if t_lame is None:
            raise ValueError("Calcul Lamé impossible avec ces paramètres (sigma_eff <= p).")
        return out if return_details else t_lame

    if modele == "both":
        if t_lame is None:
            out["t_lame_m"] = float("nan")
        return out

    # auto
    if t_over_ri <= rmax:
        out["modele_auto"] = 0.0  # mince
        return out if return_details else t_mince

    if t_lame is None:
        raise ValueError("Auto: paroi mince non valide (t/ri trop grand) et Lamé impossible (sigma_eff <= p).")
    out["modele_auto"] = 1.0  # lame
    return out if return_details else t_lame


# =============================================================================
# Agrégateur : calcule tout ce qui est calculable avec les entrées disponibles
# =============================================================================

class ResultatCylindre(TypedDict, total=False):
    # Géométrie
    alesage_m: float
    course_m: float
    nombre_cylindres: float
    aire_section_m2: float
    rayon_interne_m: float

    # Volumes
    cylindree_unitaire_m3: float
    cylindree_totale_m3: float
    cylindree_unitaire_l: float
    cylindree_totale_l: float
    cylindree_unitaire_cm3: float
    cylindree_totale_cm3: float

    # Compression
    taux_compression: float
    volume_mort_m3: float
    volume_mort_cm3: float

    # Ratio B/S
    ratio_alesage_course: float
    architecture_code: float

    # Gaz
    pression_pa: float
    force_gaz_n: float
    aire_piston_m2: float

    # Paroi
    contrainte_admissible_pa: float
    facteur_securite: float
    epaisseur_mince_m: float
    epaisseur_lame_m: float
    epaisseur_auto_m: float
    t_over_ri_mince: float
    ratio_mince_max: float

    # Diagnostic
    inconnues: str


def calculer_cylindre_complet(
    *,
    alesage_m: Optional[Number] = None,
    course_m: Optional[Number] = None,
    nombre_cylindres: Optional[int] = None,
    taux_compression: Optional[Number] = None,
    volume_mort_m3: Optional[Number] = None,
    pression_pa: Optional[Number] = None,
    contrainte_admissible_pa: Optional[Number] = None,
    modele_paroi: ModeleParoi = "auto",
    facteur_securite: Number = 1.0,
    include_longitudinale: bool = False,
    ratio_mince_max: float = 0.1,
    epsilon: Number = 1e-12,
) -> ResultatCylindre:
    """
    Agrégateur déterministe :
    - calcule tout ce qui est déductible des entrées
    - n'invente rien : si une donnée manque, elle est listée dans 'inconnues'
    - si CR et Vc sont fournis, vérifie la cohérence (tolérance relative stricte)
    """
    res: ResultatCylindre = {}
    inconnues: List[str] = []

    B: Optional[float] = None
    S: Optional[float] = None
    N: Optional[int] = None

    if alesage_m is not None:
        B = _req_pos("alesage_m", alesage_m, strictly=True)
        res["alesage_m"] = B
        res["rayon_interne_m"] = 0.5 * B
    else:
        inconnues.append("alesage_m")

    if course_m is not None:
        S = _req_pos("course_m", course_m, strictly=True)
        res["course_m"] = S
    else:
        inconnues.append("course_m")

    if nombre_cylindres is not None:
        N = _req_int_ge("nombre_cylindres", nombre_cylindres, 1)
        res["nombre_cylindres"] = float(N)
    else:
        inconnues.append("nombre_cylindres")

    # aire / cylindrée
    Vd_unit: Optional[float] = None
    if B is not None:
        aire = (math.pi * (B ** 2)) / 4.0
        res["aire_section_m2"] = aire
        res["aire_piston_m2"] = aire
        if S is not None:
            Vd_unit = aire * S
            res["cylindree_unitaire_m3"] = Vd_unit
            res["cylindree_unitaire_l"] = Vd_unit * 1000.0
            res["cylindree_unitaire_cm3"] = Vd_unit * 1_000_000.0
        else:
            inconnues.append("cylindree_unitaire_m3 (course manquante)")
    else:
        inconnues.append("aire_section_m2 / aire_piston_m2")

    if Vd_unit is not None and N is not None:
        Vtot = Vd_unit * float(N)
        res["cylindree_totale_m3"] = Vtot
        res["cylindree_totale_l"] = Vtot * 1000.0
        res["cylindree_totale_cm3"] = Vtot * 1_000_000.0
    elif Vd_unit is None:
        inconnues.append("cylindree_totale_m3 (cylindree_unitaire manquante)")
    elif N is None:
        inconnues.append("cylindree_totale_m3 (nombre_cylindres manquant)")

    # ratio alésage/course
    if B is not None and S is not None:
        details = calcul_ratio_alesage_course(B, S, return_details=True)
        assert isinstance(details, dict)
        res["ratio_alesage_course"] = float(details["ratio"])
        res["architecture_code"] = float(details["architecture_code"])
    else:
        inconnues.append("ratio_alesage_course / architecture_code")

    # compression : CR <-> Vc
    CR: Optional[float] = None
    Vc: Optional[float] = None

    if taux_compression is not None:
        CR = _req_finite("taux_compression", taux_compression)
        if CR <= 1.0:
            raise ValueError(f"taux_compression doit être > 1.0 (reçu: {CR}).")
        res["taux_compression"] = CR

    if volume_mort_m3 is not None:
        Vc = _req_pos("volume_mort_m3", volume_mort_m3, strictly=True)
        res["volume_mort_m3"] = Vc
        res["volume_mort_cm3"] = Vc * 1_000_000.0

    if Vd_unit is not None and CR is not None and Vc is None:
        Vc = Vd_unit / (CR - 1.0)
        res["volume_mort_m3"] = Vc
        res["volume_mort_cm3"] = Vc * 1_000_000.0
    elif Vd_unit is not None and Vc is not None and CR is None:
        CR = (Vd_unit + Vc) / Vc
        res["taux_compression"] = CR
    elif Vd_unit is None and (CR is not None or Vc is not None):
        inconnues.append("compression (cylindree_unitaire requise)")

    # cohérence stricte si CR et Vc fournis
    if Vd_unit is not None and CR is not None and Vc is not None:
        CR2 = (Vd_unit + Vc) / Vc
        rel = abs(CR2 - CR) / max(abs(CR), 1e-12)
        if rel > 1e-9:
            raise ValueError(f"Incohérence CR/Vc : CR fourni={CR}, CR recalculé={CR2} (rel={rel}).")

    # force gaz
    if pression_pa is not None:
        p = _req_finite("pression_pa", pression_pa)
        res["pression_pa"] = p
        if B is not None:
            res["force_gaz_n"] = p * float(res["aire_piston_m2"])
        else:
            inconnues.append("force_gaz_n (alesage manquant)")
    else:
        inconnues.append("pression_pa / force_gaz_n")

    # paroi : nécessite p, B, sigma_adm
    if contrainte_admissible_pa is not None:
        sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
        fs = _req_pos("facteur_securite", facteur_securite, strictly=True)
        res["contrainte_admissible_pa"] = sigma_adm
        res["facteur_securite"] = float(fs)

        if pression_pa is not None and B is not None:
            d = calcul_epaisseur_paroi_depuis_alesage(
                pression_pa=res["pression_pa"],
                alesage_m=B,
                contrainte_admissible_pa=sigma_adm,
                modele="both",
                facteur_securite=fs,
                include_longitudinale=include_longitudinale,
                ratio_mince_max=ratio_mince_max,
                epsilon=epsilon,
                return_details=True,
            )
            assert isinstance(d, dict)
            res["epaisseur_mince_m"] = float(d["t_mince_m"])
            res["t_over_ri_mince"] = float(d["t_over_ri_mince"])
            res["ratio_mince_max"] = float(d["ratio_mince_max"])

            if "t_lame_m" in d:
                # peut être NaN si Lamé impossible
                res["epaisseur_lame_m"] = float(d["t_lame_m"])

            t_auto = calcul_epaisseur_paroi_depuis_alesage(
                pression_pa=res["pression_pa"],
                alesage_m=B,
                contrainte_admissible_pa=sigma_adm,
                modele=modele_paroi,
                facteur_securite=fs,
                include_longitudinale=include_longitudinale,
                ratio_mince_max=ratio_mince_max,
                epsilon=epsilon,
                return_details=False,
            )
            res["epaisseur_auto_m"] = float(t_auto)
        else:
            inconnues.append("epaisseur_paroi (pression/alesage requis)")
    else:
        inconnues.append("contrainte_admissible_pa / epaisseur_paroi")

    res["inconnues"] = "; ".join(inconnues) if inconnues else ""
    return res


__all__ = [
    # utils
    "aire_disque_depuis_diametre",
    "rayon_depuis_diametre",
    "verifier_hypothese_paroi_mince",
    # cylindrée / compression / ratio
    "calcul_cylindree_unitaire",
    "calcul_cylindree_totale",
    "calcul_volume_mort",
    "calcul_taux_compression",
    "calcul_ratio_alesage_course",
    # gaz
    "calcul_force_gaz",
    # paroi
    "calcul_epaisseur_cylindre_mince",
    "calcul_epaisseur_cylindre_lame",
    "calcul_epaisseur_paroi_depuis_alesage",
    # agrégateur
    "ResultatCylindre",
    "calculer_cylindre_complet",
]
