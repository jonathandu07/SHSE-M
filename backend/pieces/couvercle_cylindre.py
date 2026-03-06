# backend/pieces/couvercle_cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
import math

# ============================================================
# Imports projet (avec fallbacks)
# ============================================================

# --- Matériaux ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None

# --- Pièce associée ---
try:
    from backend.pieces.cylindre import Cylindre
except Exception:  # pragma: no cover
    try:
        from pieces.cylindre import Cylindre  # type: ignore
    except Exception:  # pragma: no cover
        Cylindre = None  # type: ignore

# --- Précharge / visserie ---
try:
    from backend.modules.moteur_thermique.calcul_precharge_vis import (
        calcul_force_separation,
        calcul_precharge_vis_totale,
        calcul_couple_serrage,
    )
except Exception:  # pragma: no cover
    def calcul_force_separation(pression_max_pa: float, aire_effective_m2: float) -> float:
        return max(0.0, float(pression_max_pa)) * max(0.0, float(aire_effective_m2))

    def calcul_precharge_vis_totale(
        force_separation_n: float,
        force_joint_n: float,
        facteur_securite: float = 1.5,
    ) -> float:
        return max(0.0, float(facteur_securite)) * max(0.0, float(force_separation_n)) + max(0.0, float(force_joint_n))

    def calcul_couple_serrage(
        force_precharge_vis_n: float,
        diametre_nominal_m: float,
        facteur_frottement_k: float = 0.2,
    ) -> float:
        return max(0.0, float(facteur_frottement_k)) * max(0.0, float(force_precharge_vis_n)) * max(0.0, float(diametre_nominal_m))

# --- Fluides ---
try:
    from backend.ensemble.eau import etat_eau_pure, etat_eau_salee, etat_antigel
except Exception:  # pragma: no cover
    etat_eau_pure = etat_eau_salee = etat_antigel = None  # type: ignore

try:
    # air.py réel: altitude_m + temperature_offset_K + RH + co2_ppm
    from backend.ensemble.air import air_state, isa_dry_temperature_pressure
except Exception:  # pragma: no cover
    air_state = None  # type: ignore
    isa_dry_temperature_pressure = None  # type: ignore


# ============================================================
# Helpers robustes
# ============================================================

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

def _req_int_pos(name: str, x: Any, *, allow_zero: bool = False) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if allow_zero:
        if x < 0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {x}).")
    else:
        if x <= 0:
            raise ValueError(f"{name} doit être > 0 (reçu: {x}).")
    return int(x)

def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))

def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})

def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, Any]] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(list(rapport["inconnues"].get("impossibles", []) or []))
    rapport["inconnues"]["partielles"] = dedup(list(rapport["inconnues"].get("partielles", []) or []))


# ============================================================
# Convection (optionnelle)
# ============================================================

FluideType = Literal["air", "eau_pure", "eau_salee", "antigel"]

@dataclass(frozen=True)
class EntreeConvectionTube:
    fluide: FluideType
    T_K: float
    p_Pa: float

    altitude_m: float = 0.0
    RH: float = 0.0
    co2_ppm: float = 420.0

    salinite_g_kg: float = 35.0

    fraction_massique_glycol: float = 0.0
    type_glycol: Literal["MEG", "MPG"] = "MEG"

    debit_massique_kg_s: float = 0.0
    diametre_m: float = 0.0

    modele: Literal["auto", "laminaire", "dittus_boelter", "gnielinski"] = "auto"
    condition_paroi: Literal["T_constante", "q_constante"] = "T_constante"
    chauffage_fluide: bool = True


def _nu_laminaire_tube(*, condition_paroi: Literal["T_constante", "q_constante"]) -> float:
    return 3.66 if condition_paroi == "T_constante" else 4.36

def _nu_dittus_boelter(Re: float, Pr: float, chauffage_fluide: bool) -> float:
    n = 0.4 if chauffage_fluide else 0.3
    return 0.023 * (Re ** 0.8) * (Pr ** n)

def _f_darcy_blasius(Re: float) -> float:
    return 0.3164 / (Re ** 0.25)

def _nu_gnielinski(Re: float, Pr: float, f_darcy: float) -> float:
    return ((f_darcy / 8.0) * (Re - 1000.0) * Pr) / (
        1.0 + 12.7 * math.sqrt(f_darcy / 8.0) * ((Pr ** (2.0 / 3.0)) - 1.0)
    )

def _h_tube_interne(
    *,
    rho: float,
    mu: float,
    k: float,
    cp: float,
    debit_massique_kg_s: float,
    diametre_m: float,
    modele: Literal["auto", "laminaire", "dittus_boelter", "gnielinski"],
    condition_paroi: Literal["T_constante", "q_constante"],
    chauffage_fluide: bool,
) -> Dict[str, Any]:
    if rho <= 0 or mu <= 0 or k <= 0 or cp <= 0:
        raise ValueError("rho, mu, k, cp doivent être > 0")
    mdot = _req_pos("debit_massique_kg_s", debit_massique_kg_s)
    D = _req_pos("diametre_m", diametre_m)

    A = math.pi * (D ** 2) / 4.0
    v = mdot / (rho * A)
    Re = rho * v * D / mu
    Pr = (cp * mu) / k

    if modele == "auto":
        if Re < 2300.0:
            Nu = _nu_laminaire_tube(condition_paroi=condition_paroi)
            modele_txt = f"laminaire({condition_paroi})"
        else:
            if Re >= 3000.0:
                f = _f_darcy_blasius(Re)
                Nu = _nu_gnielinski(Re, Pr, f)
                modele_txt = "gnielinski+blasius"
            else:
                Nu = _nu_dittus_boelter(Re, Pr, chauffage_fluide=chauffage_fluide)
                modele_txt = "dittus_boelter"
    elif modele == "laminaire":
        Nu = _nu_laminaire_tube(condition_paroi=condition_paroi)
        modele_txt = f"laminaire({condition_paroi})"
    elif modele == "dittus_boelter":
        Nu = _nu_dittus_boelter(Re, Pr, chauffage_fluide=chauffage_fluide)
        modele_txt = "dittus_boelter"
    elif modele == "gnielinski":
        if Re <= 1000.0:
            raise ValueError("Gnielinski nécessite Re > 1000.")
        f = _f_darcy_blasius(Re)
        Nu = _nu_gnielinski(Re, Pr, f)
        modele_txt = "gnielinski+blasius"
    else:
        raise ValueError("modele inconnu.")

    h = Nu * k / D
    return {
        "A_section_m2": A,
        "v_m_s": v,
        "Re": Re,
        "Pr": Pr,
        "Nu": Nu,
        "h_W_m2_K": h,
        "modele_txt": modele_txt,
    }

def _etat_fluide_pour_convection(ent: EntreeConvectionTube) -> Dict[str, float]:
    if ent.fluide == "air":
        if air_state is None or isa_dry_temperature_pressure is None:
            raise RuntimeError("backend.ensemble.air indisponible.")
        altitude = float(ent.altitude_m)
        T_isa, p_isa = isa_dry_temperature_pressure(altitude_m=altitude)
        temperature_offset_K = float(ent.T_K) - float(T_isa)
        st = air_state(
            altitude_m=altitude,
            temperature_offset_K=temperature_offset_K,
            RH=float(ent.RH),
            co2_ppm=float(ent.co2_ppm),
        )
        return {
            "rho": float(st.rho_kg_m3),
            "cp": float(st.cp_J_kgK),
            "mu": float(st.mu_Pa_s),
            "k": float(st.k_W_mK),
            "T_K": float(st.T_K),
            "p_Pa": float(st.p_Pa),
            "T_K_entree": float(ent.T_K),
            "p_Pa_entree": float(ent.p_Pa),
            "p_Pa_ISA": float(p_isa),
            "temperature_offset_K": float(temperature_offset_K),
        }

    if ent.fluide == "eau_pure":
        if etat_eau_pure is None:
            raise RuntimeError("backend.ensemble.eau.etat_eau_pure indisponible.")
        st = etat_eau_pure(float(ent.T_K), float(ent.p_Pa))
        return {"rho": float(st.rho_kg_m3), "cp": float(st.cp_J_kg_K), "mu": float(st.mu_Pa_s), "k": float(st.k_W_m_K)}

    if ent.fluide == "eau_salee":
        if etat_eau_salee is None:
            raise RuntimeError("backend.ensemble.eau.etat_eau_salee indisponible.")
        st = etat_eau_salee(float(ent.T_K), float(ent.p_Pa), float(ent.salinite_g_kg))
        return {"rho": float(st.rho_kg_m3), "cp": float(st.cp_J_kg_K), "mu": float(st.mu_Pa_s), "k": float(st.k_W_m_K)}

    if ent.fluide == "antigel":
        if etat_antigel is None:
            raise RuntimeError("backend.ensemble.eau.etat_antigel indisponible.")
        st = etat_antigel(
            float(ent.T_K),
            float(ent.p_Pa),
            float(ent.fraction_massique_glycol),
            type_glycol=str(ent.type_glycol),
        )
        return {"rho": float(st.rho_kg_m3), "cp": float(st.cp_J_kg_K), "mu": float(st.mu_Pa_s), "k": float(st.k_W_m_K)}

    raise ValueError("fluide inconnu.")

def calcul_h_depuis_entree_convection(ent: EntreeConvectionTube) -> Dict[str, Any]:
    props = _etat_fluide_pour_convection(ent)
    res = _h_tube_interne(
        rho=props["rho"],
        mu=props["mu"],
        k=props["k"],
        cp=props["cp"],
        debit_massique_kg_s=ent.debit_massique_kg_s,
        diametre_m=ent.diametre_m,
        modele=ent.modele,
        condition_paroi=ent.condition_paroi,
        chauffage_fluide=ent.chauffage_fluide,
    )
    res["fluide"] = ent.fluide
    return res


# ============================================================
# Matériau
# ============================================================

def _materiau_resoudre(
    *,
    materiau_cle: str,
    mode: Literal["min", "typique", "max"],
) -> Dict[str, Any]:
    if get_materiau is None:
        raise RuntimeError("backend.ensemble.materiaux.get_materiau indisponible.")
    mat = get_materiau(materiau_cle)

    rho = float(mat.densite_kg_m3) if mat.densite_kg_m3 is not None else None
    E = valeur(mat.module_young_pa, mode=mode)
    nu = valeur(mat.poisson, mode=mode)
    k = valeur(mat.conductivite_thermique_w_mk, mode=mode)
    alpha = valeur(mat.alpha_dilatation_1_k, mode=mode)

    Re_candidates: List[float] = []
    base_Re = mat.limite_elastique_effective_pa(mode="min", section_mm=None)
    if base_Re is not None:
        Re_candidates.append(float(base_Re))
    if getattr(mat, "resistance_par_section", None):
        for seg in mat.resistance_par_section:
            if getattr(seg, "rp02_pa_min", None) is not None:
                Re_candidates.append(float(seg.rp02_pa_min))
    Re_min = min(Re_candidates) if Re_candidates else None

    return {
        "densite_kg_m3": rho,
        "module_young_pa": E,
        "poisson": nu,
        "conductivite_w_m_k": k,
        "alpha_dilatation_1_k": alpha,
        "limite_elastique_min_pa": Re_min,
        "T_service_min_C": getattr(mat, "temperature_service_min_c", None),
        "T_service_max_C": getattr(mat, "temperature_service_max_c", None),
        "materiau_nom": getattr(mat, "nom", materiau_cle),
        "famille": getattr(mat, "famille", None),
    }


# ============================================================
# ISO filetages métriques
# ============================================================

FiletageSerie = Literal["iso_metric_coarse"]

_METRIC_COARSE_SERIE_MM: List[Tuple[float, float]] = [
    (2.0, 0.4), (2.5, 0.45), (3.0, 0.5), (3.5, 0.6), (4.0, 0.7), (5.0, 0.8),
    (6.0, 1.0), (7.0, 1.0), (8.0, 1.25), (10.0, 1.5), (12.0, 1.75),
    (14.0, 2.0), (16.0, 2.0), (18.0, 2.5), (20.0, 2.5), (22.0, 2.5),
    (24.0, 3.0), (27.0, 3.0), (30.0, 3.5), (33.0, 3.5), (36.0, 4.0),
    (39.0, 4.0), (42.0, 4.5), (45.0, 4.5), (48.0, 5.0), (52.0, 5.0),
    (56.0, 5.5), (60.0, 5.5), (64.0, 6.0),
]

def _iso898_yield_strength_pa_from_class(classe_iso: str) -> float:
    s = str(classe_iso).strip()
    if not s or "." not in s:
        raise ValueError(f"classe_iso invalide (attendu 'x.y', reçu {classe_iso!r})")
    a_s, b_s = s.split(".", 1)
    a = int(a_s)
    b = int(b_s)
    if a <= 0 or b <= 0:
        raise ValueError(f"classe_iso invalide: {classe_iso!r}")
    Re_MPa = 10.0 * float(a) * float(b)
    return Re_MPa * 1e6

def _tensile_stress_area_iso898_mm2(d_mm: float, p_mm: float) -> float:
    d = _req_pos("d_mm", d_mm)
    p = _req_pos("p_mm", p_mm)
    return (math.pi / 4.0) * ((d - 0.9382 * p) ** 2)

def _internal_thread_minor_diameter_mm(d_mm: float, p_mm: float) -> float:
    d = _req_pos("d_mm", d_mm)
    p = _req_pos("p_mm", p_mm)
    return d - 1.082532 * p

def _pas_coarse_pour_diametre_mm(d_mm: float) -> Optional[float]:
    for d, p in _METRIC_COARSE_SERIE_MM:
        if abs(float(d) - float(d_mm)) < 1e-9:
            return float(p)
    return None

def _filetage_depuis_nominal(
    *,
    d_nominal_mm: float,
    pas_mm: Optional[float],
) -> Dict[str, Any]:
    d = _req_pos("d_nominal_mm", d_nominal_mm)
    p = pas_mm if pas_mm is not None else _pas_coarse_pour_diametre_mm(d)
    if p is None:
        raise ValueError("pas_mm non fourni et pas grossier introuvable pour ce diamètre.")
    p = _req_pos("pas_mm", p)
    As_mm2 = _tensile_stress_area_iso898_mm2(d, p)
    return {
        "serie": "iso_metric_coarse",
        "d_nominal_mm": float(d),
        "pas_mm": float(p),
        "taraudage": f"M{d:g}x{p:g}",
        "As_mm2": float(As_mm2),
        "As_m2": float(As_mm2) * 1e-6,
        "D1_taraudage_mm": float(_internal_thread_minor_diameter_mm(d, p)),
    }

def _choisir_filetage(
    *,
    serie: FiletageSerie,
    As_requise_m2: float,
    d_max_mm: Optional[float] = None,
) -> Dict[str, Any]:
    As_req = _req_pos("As_requise_m2", As_requise_m2)
    As_req_mm2 = As_req * 1e6
    if serie != "iso_metric_coarse":
        raise ValueError("Seule la série 'iso_metric_coarse' est implémentée.")
    for d_mm, p_mm in _METRIC_COARSE_SERIE_MM:
        if d_max_mm is not None and float(d_mm) > float(d_max_mm):
            continue
        As_mm2 = _tensile_stress_area_iso898_mm2(d_mm, p_mm)
        if As_mm2 >= As_req_mm2:
            return {
                "serie": serie,
                "d_nominal_mm": float(d_mm),
                "pas_mm": float(p_mm),
                "taraudage": f"M{d_mm:g}x{p_mm:g}",
                "As_mm2": float(As_mm2),
                "As_m2": float(As_mm2) * 1e-6,
                "D1_taraudage_mm": float(_internal_thread_minor_diameter_mm(d_mm, p_mm)),
            }
    raise ValueError("Aucun filetage trouvé (As_requise_m2 trop élevée ou d_max_mm trop bas).")


# ============================================================
# Géométrie couvercle : calotte sphérique + bride
# ============================================================

TypeAppui = Literal["encastre"]
SourceAppui = Literal["ouverture", "cylindre_sans_brides", "cylindre_avec_brides", "cylindre_cao_bride"]
FormeCouvercle = Literal["calotte_spherique"]

def _calotte_spherique_resoudre_geometrie(
    *,
    rayon_base_m: float,
    hauteur_bombe_m: Optional[float],
    rayon_courbure_m: Optional[float],
) -> Dict[str, float]:
    a = _req_pos("rayon_base_m", rayon_base_m)

    if hauteur_bombe_m is None and rayon_courbure_m is None:
        raise ValueError("Il faut fournir hauteur_bombe_m ou rayon_courbure_m pour un couvercle convexe.")

    if hauteur_bombe_m is not None:
        h = _req_pos("hauteur_bombe_m", hauteur_bombe_m)
        R = (a * a + h * h) / (2.0 * h)
        if R <= a:
            raise ValueError("Géométrie calotte invalide : R <= a.")
    else:
        R = _req_pos("rayon_courbure_m", rayon_courbure_m)
        if R <= a:
            raise ValueError("rayon_courbure_m doit être > rayon_base_m.")
        h = R - math.sqrt(R * R - a * a)
        if h <= 0:
            raise ValueError("Hauteur de bombe calculée <= 0.")

    A = 2.0 * math.pi * R * h
    Vcap = (math.pi * h / 6.0) * (3.0 * a * a + h * h)
    angle_ouverture_rad = math.asin(a / R)
    return {
        "a_m": a,
        "h_m": h,
        "R_m": R,
        "A_surface_m2": A,
        "V_cap_m3": Vcap,
        "angle_ouverture_rad": angle_ouverture_rad,
        "angle_ouverture_deg": math.degrees(angle_ouverture_rad),
    }

def _epaisseur_requise_calotte_spherique_membrane(
    *,
    p_Pa: float,
    R_m: float,
    sigma_admissible_eff_Pa: float,
) -> float:
    p = abs(float(p_Pa))
    R = _req_pos("R_m", R_m)
    s = _req_pos("sigma_admissible_eff_Pa", sigma_admissible_eff_Pa)
    return (p * R) / (2.0 * s)

def _proposer_forme_calotte_depuis_pression_matiere(
    *,
    rayon_base_m: float,
    pression_dimensionnement_pa: float,
    sigma_admissible_eff_pa: float,
    rapport_min: float = 0.12,
    rapport_max: float = 0.35,
) -> Dict[str, float]:
    """
    Règle explicite de conception :
    - plus p/sigma_eff est élevé, plus on bombe le couvercle
    - on borne h/a pour garder une pièce réaliste et dessinable
    """
    a = _req_pos("rayon_base_m", rayon_base_m)
    p = _req_pos("pression_dimensionnement_pa", pression_dimensionnement_pa, strictly=False)
    s = _req_pos("sigma_admissible_eff_pa", sigma_admissible_eff_pa)

    phi = p / s if s > 0 else 0.0
    # règle déterministe, sans prétendre être une loi physique pure
    ratio_h_sur_a = _borne(0.12 + 4.0 * phi, rapport_min, rapport_max)
    h = ratio_h_sur_a * a
    geo = _calotte_spherique_resoudre_geometrie(
        rayon_base_m=a,
        hauteur_bombe_m=h,
        rayon_courbure_m=None,
    )
    geo["ratio_h_sur_a"] = ratio_h_sur_a
    return geo

def _volume_calotte_mince(geo_cap: Dict[str, float], epaisseur_m: float) -> float:
    A = _req_pos("A_surface_m2", geo_cap["A_surface_m2"])
    e = _req_pos("epaisseur_m", epaisseur_m)
    return A * e

def _surface_annulaire(r_int: float, r_ext: float) -> float:
    ri = _req_pos("r_int", r_int, strictly=False)
    re = _req_pos("r_ext", r_ext)
    if re <= ri:
        raise ValueError("r_ext doit être > r_int.")
    return math.pi * (re * re - ri * ri)


# ============================================================
# Règles fabrication / forme
# ============================================================

@dataclass(frozen=True)
class ReglesFormeCouvercle:
    rapport_h_sur_a_min: float = 0.12
    rapport_h_sur_a_max: float = 0.35
    ratio_epaisseur_bride_sur_epaisseur_calotte: float = 1.30
    epaisseur_bride_min_m: float = 0.006
    largeur_bride_min_m: float = 0.010
    largeur_bride_sur_epaisseur_m: float = 3.0
    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.003
    ratio_chanfrein_sur_epaisseur: float = 0.30
    conge_min_m: float = 0.0005
    conge_max_m: float = 0.004
    ratio_conge_sur_epaisseur: float = 0.25

    rugosite_face_joint_ra_um: float = 1.6
    rugosite_exterieure_ra_um: float = 3.2
    rugosite_interieure_ra_um: float = 1.6

    tolerance_epaisseur_m: float = 0.00010
    tolerance_bride_m: float = 0.00010
    tolerance_position_trous_m: float = 0.00010

def _resoudre_depuis_cylindre_cao(cyl_rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "cao_cylindre": None,
        "bride": None,
        "visserie": None,
        "gorge_joint": None,
        "diametre_interieur_nominal_m": None,
        "diametre_exterieur_nominal_m": None,
        "diametre_bride_externe_m": None,
        "diametre_cercle_percage_m": None,
        "nb_trous": None,
        "diametre_trou_m": None,
        "angles_deg": None,
        "epaisseur_bride_m": None,
        "largeur_bride_m": None,
        "pression_max_pa": None,
        "pression_service_pa": None,
    }
    if not isinstance(cyl_rep, dict):
        return out

    ent = cyl_rep.get("entrees", {}) if isinstance(cyl_rep.get("entrees", {}), dict) else {}
    geo = cyl_rep.get("geometrie", {}) if isinstance(cyl_rep.get("geometrie", {}), dict) else {}
    cao = geo.get("cao", {}) if isinstance(geo.get("cao", {}), dict) else {}
    ass = cyl_rep.get("assemblage", {}) if isinstance(cyl_rep.get("assemblage", {}), dict) else {}

    bride = None
    visserie = None
    gorge_joint = None

    if isinstance(cao, dict) and cao:
        bride = cao.get("bride") if isinstance(cao.get("bride"), dict) else None
        visserie = cao.get("visserie") if isinstance(cao.get("visserie"), dict) else None
        gorge_joint = cao.get("gorge_joint") if isinstance(cao.get("gorge_joint"), dict) else None

    if bride is None and isinstance(ass.get("bride"), dict):
        bride = ass["bride"]
    if visserie is None and isinstance(ass.get("visserie"), dict):
        visserie = ass["visserie"]
    if gorge_joint is None and isinstance(ass.get("gorge_joint"), dict):
        gorge_joint = ass["gorge_joint"]

    out["cao_cylindre"] = cao if cao else None
    out["bride"] = bride
    out["visserie"] = visserie
    out["gorge_joint"] = gorge_joint

    if isinstance(cao, dict) and cao:
        out["diametre_interieur_nominal_m"] = cao.get("diametre_interieur_nominal_m")
        out["diametre_exterieur_nominal_m"] = cao.get("diametre_exterieur_nominal_m")

    if out["diametre_interieur_nominal_m"] is None:
        out["diametre_interieur_nominal_m"] = geo.get("diametre_interne_m")
    if out["diametre_exterieur_nominal_m"] is None:
        out["diametre_exterieur_nominal_m"] = geo.get("diametre_externe_m")

    if isinstance(bride, dict):
        out["diametre_bride_externe_m"] = bride.get("diametre_bride_externe_m")
        out["diametre_cercle_percage_m"] = bride.get("diametre_cercle_percage_m")
        out["nb_trous"] = bride.get("nb_trous")
        out["diametre_trou_m"] = bride.get("diametre_trou_m")
        out["angles_deg"] = bride.get("angles_deg")
        out["epaisseur_bride_m"] = bride.get("epaisseur_bride_m")
        out["largeur_bride_m"] = bride.get("largeur_bride_m")

    out["pression_max_pa"] = ent.get("pression_max_pa")
    out["pression_service_pa"] = ent.get("pression_service_pa")
    return out

def _calcul_force_joint_torique_simplifiee(gorge_joint: Dict[str, Any]) -> Optional[float]:
    try:
        Dj = _req_pos("diametre_moyen_joint_m", gorge_joint["diametre_moyen_joint_m"])
        dt = _req_pos("diametre_tore_m", gorge_joint["diametre_tore_m"])
        eps = _req_pos("taux_ecrasement_cible", gorge_joint["taux_ecrasement_cible"])
        coeff = 12000.0
        return math.pi * Dj * coeff * (dt / 0.003) * (eps / 0.20)
    except Exception:
        return None


# ============================================================
# Pièce : CouvercleCylindre
# ============================================================

@dataclass(frozen=True)
class CouvercleCylindre:
    # Référence au cylindre
    cylindre: Optional[Any] = None  # Cylindre ou dict rapport

    # Géométrie ouverture / appui
    diametre_ouverture_m: Optional[float] = None
    rayon_appui_m: Optional[float] = None
    source_appui: SourceAppui = "ouverture"
    rayon_externe_m: Optional[float] = None  # si None -> rayon base bride/cylindre

    # Pressions
    pression_service_pa: Optional[float] = None
    pression_max_pa: Optional[float] = None
    pression_externe_pa: float = 0.0

    # Forme
    forme: FormeCouvercle = "calotte_spherique"
    hauteur_bombe_m: Optional[float] = None
    rayon_courbure_m: Optional[float] = None

    # Épaisseur
    epaisseur_m: Optional[float] = None
    epaisseur_min_fabrication_m: float = 0.0

    # Matériau
    materiau_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "min"

    contrainte_admissible_pa: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    facteur_securite: float = 2.0

    module_young_pa: Optional[float] = None
    coefficient_poisson: Optional[float] = None
    coefficient_dilatation_1_k: Optional[float] = None
    conductivite_w_m_k: Optional[float] = None
    densite_kg_m3: Optional[float] = None

    temperature_service_C: Optional[float] = None
    delta_temperature_k: Optional[float] = None

    # Thermique optionnelle
    convection_interne: Optional[EntreeConvectionTube] = None
    convection_externe: Optional[EntreeConvectionTube] = None
    h_interne_w_m2_k: Optional[float] = None
    h_externe_w_m2_k: Optional[float] = None

    # Assemblage / overrides éventuels
    nb_vis: Optional[int] = None
    vis_d_nominal_mm: Optional[float] = None
    vis_pas_mm: Optional[float] = None
    aire_resistante_vis_m2: Optional[float] = None
    limite_elastique_vis_pa: Optional[float] = None
    classe_vis_iso898: Optional[str] = None
    facteur_securite_vis: Optional[float] = None
    serie_filetage: FiletageSerie = "iso_metric_coarse"
    d_max_vis_mm: Optional[float] = None

    diametre_cercle_percage_m: Optional[float] = None
    diametre_trou_m: Optional[float] = None
    angles_trous_deg: Optional[List[float]] = None
    epaisseur_bride_m: Optional[float] = None
    largeur_bride_m: Optional[float] = None

    type_appui: TypeAppui = "encastre"

    # Règles explicites de forme/fabrication
    regles_forme: ReglesFormeCouvercle = ReglesFormeCouvercle()

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "geometrie": {},
            "charges": {},
            "dimensionnement": {},
            "contraintes": {},
            "deformations": {},
            "thermique": {},
            "masse": {},
            "assemblage": {},
            "fabrication": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # 0) Récupération cylindre
        # ------------------------------------------------------------
        cyl_rep: Optional[Dict[str, Any]] = None
        cyl = self.cylindre
        if cyl is not None:
            try:
                if hasattr(cyl, "analyser") and callable(getattr(cyl, "analyser")):
                    cyl_rep = cyl.analyser(strict=False)  # type: ignore[call-arg]
                elif isinstance(cyl, dict):
                    cyl_rep = cyl
                else:
                    _push_inconnue(rapport, "partielles", "cylindre", "Format non supporté (attendu Cylindre ou dict rapport).")
            except Exception as e:
                _push_inconnue(rapport, "partielles", "cylindre.analyser", f"Impossible d'exploiter cylindre: {e!r}")

        cyl_auto = _resoudre_depuis_cylindre_cao(cyl_rep)

        # ------------------------------------------------------------
        # 1) Entrées géométriques et pressions
        # ------------------------------------------------------------
        D_ouv: Optional[float] = self.diametre_ouverture_m
        if D_ouv is None and cyl_auto["diametre_interieur_nominal_m"] is not None:
            D_ouv = float(cyl_auto["diametre_interieur_nominal_m"])
        elif D_ouv is None and cyl is not None:
            try:
                if hasattr(cyl, "alesage_m"):
                    D_ouv = float(getattr(cyl, "alesage_m"))
            except Exception:
                D_ouv = None

        p_serv = self.pression_service_pa
        p_max = self.pression_max_pa
        if p_serv is None and cyl_auto["pression_service_pa"] is not None:
            p_serv = float(cyl_auto["pression_service_pa"])
        if p_max is None and cyl_auto["pression_max_pa"] is not None:
            p_max = float(cyl_auto["pression_max_pa"])

        if D_ouv is None:
            _push_inconnue(rapport, "impossibles", "diametre_ouverture_m", "Donner diametre_ouverture_m ou fournir un cylindre analysable.")
            D_ouv = float("nan")
        else:
            D_ouv = _req_pos("diametre_ouverture_m", D_ouv)

        if p_max is None:
            _push_inconnue(rapport, "impossibles", "pression_max_pa", "Nécessaire pour dimensionner le couvercle.")
            p_max_v = 0.0
        else:
            p_max_v = _req_pos("pression_max_pa", p_max, strictly=False)

        p_serv_v = 0.0 if p_serv is None else _req_pos("pression_service_pa", p_serv, strictly=False)
        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        FS = _req_pos("facteur_securite", self.facteur_securite)
        e_min = _req_pos("epaisseur_min_fabrication_m", self.epaisseur_min_fabrication_m, strictly=False)

        # appui
        a: Optional[float] = self.rayon_appui_m
        if a is None:
            if self.source_appui == "ouverture":
                a = 0.5 * D_ouv
            elif self.source_appui == "cylindre_sans_brides":
                if cyl_auto["diametre_exterieur_nominal_m"] is not None:
                    a = 0.5 * float(cyl_auto["diametre_exterieur_nominal_m"])
            elif self.source_appui in ("cylindre_avec_brides", "cylindre_cao_bride"):
                if cyl_auto["diametre_bride_externe_m"] is not None:
                    a = 0.5 * float(cyl_auto["diametre_bride_externe_m"])
                elif isinstance(cyl_rep, dict):
                    geo = cyl_rep.get("geometrie", {}) if isinstance(cyl_rep.get("geometrie", {}), dict) else {}
                    if geo.get("rayon_externe_avec_brides_m") is not None:
                        a = float(geo["rayon_externe_avec_brides_m"])
        if a is None:
            _push_inconnue(rapport, "partielles", "rayon_appui_m", "Non déduit ; repli sur rayon ouverture.")
            a = 0.5 * D_ouv
        a = _req_pos("rayon_appui_m", a)

        r_ext = self.rayon_externe_m
        if r_ext is None:
            if cyl_auto["diametre_bride_externe_m"] is not None:
                r_ext = 0.5 * float(cyl_auto["diametre_bride_externe_m"])
            else:
                r_ext = a
        r_ext = _req_pos("rayon_externe_m", r_ext)

        rapport["entrees"].update({
            "diametre_ouverture_m": D_ouv,
            "rayon_appui_m": a,
            "source_appui": self.source_appui,
            "rayon_externe_m": r_ext,
            "pression_service_pa": p_serv,
            "pression_max_pa": p_max,
            "pression_externe_pa": p_ext,
            "facteur_securite": FS,
            "epaisseur_m": self.epaisseur_m,
            "epaisseur_min_fabrication_m": e_min,
            "forme": self.forme,
            "hauteur_bombe_m": self.hauteur_bombe_m,
            "rayon_courbure_m": self.rayon_courbure_m,
            "materiau_cle": self.materiau_cle,
            "mode_materiau": self.mode_materiau,
            "type_appui": self.type_appui,
            "temperature_service_C": self.temperature_service_C,
            "cylindre_fournit": cyl is not None,
        })

        # ------------------------------------------------------------
        # 2) Matériau
        # ------------------------------------------------------------
        matp: Dict[str, Any] = {}
        if self.materiau_cle:
            try:
                matp = _materiau_resoudre(materiau_cle=self.materiau_cle, mode=self.mode_materiau)
                rapport["materiau"].update(matp)
            except Exception as e:
                _push_inconnue(rapport, "partielles", "matériau auto", f"Impossible de charger materiau_cle={self.materiau_cle!r}: {e!r}")

        densite = self.densite_kg_m3 if self.densite_kg_m3 is not None else matp.get("densite_kg_m3")
        E = self.module_young_pa if self.module_young_pa is not None else matp.get("module_young_pa")
        nu = self.coefficient_poisson if self.coefficient_poisson is not None else matp.get("poisson")
        alpha = self.coefficient_dilatation_1_k if self.coefficient_dilatation_1_k is not None else matp.get("alpha_dilatation_1_k")
        k_mat = self.conductivite_w_m_k if self.conductivite_w_m_k is not None else matp.get("conductivite_w_m_k")
        Re = self.limite_elastique_pa if self.limite_elastique_pa is not None else matp.get("limite_elastique_min_pa")

        sigma_adm: Optional[float] = None
        if self.contrainte_admissible_pa is not None:
            sigma_adm = _req_pos("contrainte_admissible_pa", self.contrainte_admissible_pa)
            rapport["materiau"]["contrainte_admissible_source"] = "contrainte_admissible_pa (input)"
        elif Re is not None:
            sigma_adm = _req_pos("limite_elastique_pa", Re)
            rapport["materiau"]["contrainte_admissible_source"] = "limite_elastique_pa (Re) + FS"
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "contrainte admissible",
                "Impossible de dimensionner sans contrainte_admissible_pa, limite_elastique_pa ou materiau_cle exploitable.",
            )

        # ------------------------------------------------------------
        # 3) Charges de pression
        # ------------------------------------------------------------
        delta_p = max(0.0, p_max_v - p_ext)
        A_ouverture = math.pi * (0.5 * D_ouv) ** 2
        F_sep = calcul_force_separation(delta_p, A_ouverture)
        rapport["charges"].update({
            "delta_p_dimensionnement_pa": delta_p,
            "aire_ouverture_m2": A_ouverture,
            "force_separation_N": F_sep,
        })

        # ------------------------------------------------------------
        # 4) Géométrie calotte
        # ------------------------------------------------------------
        geo_cap: Dict[str, float] = {}
        sigma_eff = None
        if sigma_adm is not None:
            sigma_eff = float(sigma_adm) / FS

        try:
            if self.hauteur_bombe_m is not None or self.rayon_courbure_m is not None:
                geo_cap = _calotte_spherique_resoudre_geometrie(
                    rayon_base_m=a,
                    hauteur_bombe_m=self.hauteur_bombe_m,
                    rayon_courbure_m=self.rayon_courbure_m,
                )
                rapport["dimensionnement"]["source_forme_calotte"] = "input"
            else:
                if sigma_eff is None:
                    raise ValueError("Impossible de proposer automatiquement la forme sans sigma_eff.")
                geo_cap = _proposer_forme_calotte_depuis_pression_matiere(
                    rayon_base_m=a,
                    pression_dimensionnement_pa=delta_p,
                    sigma_admissible_eff_pa=sigma_eff,
                    rapport_min=self.regles_forme.rapport_h_sur_a_min,
                    rapport_max=self.regles_forme.rapport_h_sur_a_max,
                )
                rapport["dimensionnement"]["source_forme_calotte"] = "regle_pression_matiere"
                rapport["notes_modele"].append(
                    "Forme convexe auto-déduite par règle explicite h/a = f(p/sigma_eff), bornée par les règles de conception."
                )

            rapport["geometrie"]["calotte"] = geo_cap
        except Exception as e:
            _push_inconnue(rapport, "impossibles", "géométrie calotte", f"{e}")
            geo_cap = {}

        # ------------------------------------------------------------
        # 5) Épaisseur couvercle
        # ------------------------------------------------------------
        e_calc: Optional[float] = None
        e_req_membrane: Optional[float] = None

        if self.epaisseur_m is not None:
            e_calc = _req_pos("epaisseur_m", self.epaisseur_m)
            rapport["dimensionnement"]["epaisseur_source"] = "input"
        else:
            if sigma_eff is None:
                _push_inconnue(rapport, "impossibles", "epaisseur_m", "Impossible de dimensionner sans sigma_eff.")
            elif "R_m" in geo_cap:
                e_req_membrane = _epaisseur_requise_calotte_spherique_membrane(
                    p_Pa=delta_p,
                    R_m=float(geo_cap["R_m"]),
                    sigma_admissible_eff_Pa=float(sigma_eff),
                )
                e_calc = max(float(e_req_membrane), float(e_min))
                rapport["dimensionnement"]["epaisseur_source"] = "dimensionnement_membrane"
            else:
                _push_inconnue(rapport, "impossibles", "epaisseur_m", "Géométrie calotte non disponible.")

        rapport["dimensionnement"].update({
            "modele": "calotte_spherique_membrane",
            "epaisseur_requise_membrane_m": e_req_membrane,
            "epaisseur_min_fabrication_m": e_min,
            "epaisseur_retenue_m": e_calc,
        })

        rapport["notes_modele"].append(
            "Couvercle modélisé comme calotte sphérique mince en membrane ; les effets locaux de bord ne sont pas inclus."
        )

        # ------------------------------------------------------------
        # 6) Bride et raccord au cylindre
        # ------------------------------------------------------------
        e_bride = self.epaisseur_bride_m
        l_bride = self.largeur_bride_m

        if e_calc is not None and e_calc > 0:
            if e_bride is None:
                if cyl_auto["epaisseur_bride_m"] is not None:
                    e_bride = float(cyl_auto["epaisseur_bride_m"])
                else:
                    e_bride = max(
                        self.regles_forme.epaisseur_bride_min_m,
                        self.regles_forme.ratio_epaisseur_bride_sur_epaisseur_calotte * e_calc,
                    )
            if l_bride is None:
                if cyl_auto["largeur_bride_m"] is not None:
                    l_bride = float(cyl_auto["largeur_bride_m"])
                else:
                    l_bride = max(
                        self.regles_forme.largeur_bride_min_m,
                        self.regles_forme.largeur_bride_sur_epaisseur_m * e_calc,
                    )
        else:
            if e_bride is not None:
                e_bride = _req_pos("epaisseur_bride_m", e_bride)
            if l_bride is not None:
                l_bride = _req_pos("largeur_bride_m", l_bride)

        bride_geo: Dict[str, Any] = {}
        if e_bride is not None and l_bride is not None:
            e_bride = _req_pos("epaisseur_bride_m", e_bride)
            l_bride = _req_pos("largeur_bride_m", l_bride)
            r_bride_int = a
            r_bride_ext = max(r_ext, a + l_bride)
            bride_geo = {
                "rayon_bride_interne_m": r_bride_int,
                "rayon_bride_externe_m": r_bride_ext,
                "diametre_bride_externe_m": 2.0 * r_bride_ext,
                "epaisseur_bride_m": e_bride,
                "largeur_bride_m": l_bride,
                "surface_annulaire_bride_m2": _surface_annulaire(r_bride_int, r_bride_ext),
            }
            rapport["geometrie"]["bride"] = bride_geo
        else:
            _push_inconnue(rapport, "partielles", "bride", "Bride non entièrement déterminée.")

        # ------------------------------------------------------------
        # 7) Contraintes membrane
        # ------------------------------------------------------------
        if e_calc is not None and e_calc > 0 and "R_m" in geo_cap:
            Rm = float(geo_cap["R_m"])
            sigma_mem = (delta_p * Rm) / (2.0 * e_calc)
            marge_sigma = None
            if sigma_eff is not None and sigma_mem > 0:
                marge_sigma = sigma_eff / sigma_mem

            rapport["contraintes"].update({
                "sigma_membrane_Pa": sigma_mem,
                "marge_sigma_membrane": marge_sigma,
            })
        else:
            _push_inconnue(rapport, "impossibles", "contraintes", "Impossible sans epaisseur_retenue_m et géométrie calotte (R).")

        # ------------------------------------------------------------
        # 8) Assemblage vis/perçages
        # ------------------------------------------------------------
        visserie_cyl = cyl_auto["visserie"] if isinstance(cyl_auto["visserie"], dict) else None
        gorge_joint = cyl_auto["gorge_joint"] if isinstance(cyl_auto["gorge_joint"], dict) else None

        nb_vis_eff = self.nb_vis if self.nb_vis is not None else cyl_auto["nb_trous"]
        dpc_eff = self.diametre_cercle_percage_m if self.diametre_cercle_percage_m is not None else cyl_auto["diametre_cercle_percage_m"]
        dtrou_eff = self.diametre_trou_m if self.diametre_trou_m is not None else cyl_auto["diametre_trou_m"]
        angles_eff = self.angles_trous_deg if self.angles_trous_deg is not None else cyl_auto["angles_deg"]

        # force joint
        F_joint = _calcul_force_joint_torique_simplifiee(gorge_joint) if gorge_joint is not None else 0.0
        F_pre_tot = calcul_precharge_vis_totale(
            force_separation_n=F_sep,
            force_joint_n=F_joint,
            facteur_securite=1.5,
        )

        Re_vis: Optional[float] = self.limite_elastique_vis_pa
        if Re_vis is None and self.classe_vis_iso898 is not None:
            try:
                Re_vis = float(_iso898_yield_strength_pa_from_class(self.classe_vis_iso898))
            except Exception as e:
                _push_inconnue(rapport, "partielles", "limite_elastique_vis_pa", f"Classe vis ISO invalide: {e!r}")
        elif Re_vis is None and visserie_cyl is not None:
            if visserie_cyl.get("contrainte_admissible_vis_pa") is not None:
                # remonter à une contrainte d'usage si besoin, sans prétendre retrouver Re
                pass

        filetage_impose: Optional[Dict[str, Any]] = None
        if self.vis_d_nominal_mm is not None:
            try:
                filetage_impose = _filetage_depuis_nominal(
                    d_nominal_mm=self.vis_d_nominal_mm,
                    pas_mm=self.vis_pas_mm,
                )
            except Exception as e:
                _push_inconnue(rapport, "partielles", "filetage_impose", f"Impossible de construire le filetage imposé: {e!r}")
        elif visserie_cyl is not None and visserie_cyl.get("d_nominal_mm") is not None:
            try:
                filetage_impose = _filetage_depuis_nominal(
                    d_nominal_mm=float(visserie_cyl["d_nominal_mm"]),
                    pas_mm=float(visserie_cyl["pas_mm"]) if visserie_cyl.get("pas_mm") is not None else None,
                )
            except Exception:
                filetage_impose = None

        As_m2 = None
        if self.aire_resistante_vis_m2 is not None:
            As_m2 = _req_pos("aire_resistante_vis_m2", self.aire_resistante_vis_m2)
        elif filetage_impose is not None:
            As_m2 = float(filetage_impose["As_m2"])
        elif visserie_cyl is not None and visserie_cyl.get("As_m2") is not None:
            As_m2 = float(visserie_cyl["As_m2"])

        sigma_eff_vis = None
        if self.facteur_securite_vis is not None and Re_vis is not None:
            sigma_eff_vis = _req_pos("limite_elastique_vis_pa", Re_vis) / _req_pos("facteur_securite_vis", self.facteur_securite_vis)
        elif visserie_cyl is not None and visserie_cyl.get("contrainte_admissible_vis_pa") is not None:
            sigma_eff_vis = float(visserie_cyl["contrainte_admissible_vis_pa"])

        if nb_vis_eff is None:
            if As_m2 is not None and sigma_eff_vis is not None and As_m2 > 0 and sigma_eff_vis > 0:
                F_cap = As_m2 * sigma_eff_vis
                nb_vis_eff = int(math.ceil(F_pre_tot / F_cap))
                if nb_vis_eff % 2 != 0:
                    nb_vis_eff += 1
            elif visserie_cyl is not None and visserie_cyl.get("nb_vis") is not None:
                nb_vis_eff = int(visserie_cyl["nb_vis"])

        if nb_vis_eff is not None:
            nb_vis_eff = _req_int_pos("nb_vis", int(nb_vis_eff))
            F_par_vis = F_pre_tot / nb_vis_eff if nb_vis_eff > 0 else None
        else:
            F_par_vis = None
            _push_inconnue(rapport, "partielles", "nb_vis", "Impossible de fixer le nombre de vis sans données visserie suffisantes ou cylindre CAO.")

        # si le cylindre a déjà défini DPC/trous/angles, on les reprend
        if nb_vis_eff is not None and dpc_eff is None and bride_geo:
            r_bi = bride_geo["rayon_bride_interne_m"]
            r_be = bride_geo["rayon_bride_externe_m"]
            r_centres = 0.5 * (r_bi + r_be)
            dpc_eff = 2.0 * r_centres

        if dtrou_eff is None:
            if filetage_impose is not None:
                dtrou_eff = float(filetage_impose["d_nominal_mm"]) / 1000.0 + 0.001
            elif visserie_cyl is not None and visserie_cyl.get("d_nominal_mm") is not None:
                dtrou_eff = float(visserie_cyl["d_nominal_mm"]) / 1000.0 + 0.001

        if nb_vis_eff is not None and angles_eff is None:
            angles_eff = [i * (360.0 / nb_vis_eff) for i in range(nb_vis_eff)]

        if F_par_vis is not None:
            d_nom_vis_m = None
            if filetage_impose is not None:
                d_nom_vis_m = float(filetage_impose["d_nominal_mm"]) / 1000.0
            elif visserie_cyl is not None and visserie_cyl.get("d_nominal_mm") is not None:
                d_nom_vis_m = float(visserie_cyl["d_nominal_mm"]) / 1000.0
            couple_serrage = (
                calcul_couple_serrage(F_par_vis, d_nom_vis_m, 0.2)
                if d_nom_vis_m is not None else None
            )
        else:
            couple_serrage = None

        assemblage = {
            "force_separation_N": F_sep,
            "force_joint_N": F_joint,
            "force_precharge_totale_N": F_pre_tot,
            "nb_vis": nb_vis_eff,
            "force_precharge_par_vis_N": F_par_vis,
            "diametre_cercle_percage_m": dpc_eff,
            "diametre_trou_m": dtrou_eff,
            "angles_trous_deg": angles_eff,
            "filetage": filetage_impose,
            "As_m2": As_m2,
            "sigma_admissible_vis_eff_Pa": sigma_eff_vis,
            "couple_serrage_par_vis_Nm": couple_serrage,
            "gorge_joint_reprise_cylindre": gorge_joint,
        }
        rapport["assemblage"].update(assemblage)

        # ------------------------------------------------------------
        # 9) Déformations thermiques
        # ------------------------------------------------------------
        if alpha is not None and self.delta_temperature_k is not None:
            a2 = _req_pos("coefficient_dilatation_1_k", alpha)
            dT = _req_finite("delta_temperature_k", self.delta_temperature_k)
            rapport["deformations"]["delta_diametre_ouverture_thermique_m"] = a2 * D_ouv * dT
        else:
            _push_inconnue(rapport, "partielles", "dilatation thermique", "Calculable si alpha et delta_temperature_k sont fournis.")

        # ------------------------------------------------------------
        # 10) Thermique
        # ------------------------------------------------------------
        h_i = self.h_interne_w_m2_k
        h_o = self.h_externe_w_m2_k

        if h_i is None and self.convection_interne is not None:
            try:
                res = calcul_h_depuis_entree_convection(self.convection_interne)
                h_i = float(res["h_W_m2_K"])
                rapport["thermique"]["h_interne_calcule"] = res
            except Exception as e:
                _push_inconnue(rapport, "partielles", "h_interne", f"Impossible de calculer h_interne: {e!r}")

        if h_o is None and self.convection_externe is not None:
            try:
                res = calcul_h_depuis_entree_convection(self.convection_externe)
                h_o = float(res["h_W_m2_K"])
                rapport["thermique"]["h_externe_calcule"] = res
            except Exception as e:
                _push_inconnue(rapport, "partielles", "h_externe", f"Impossible de calculer h_externe: {e!r}")

        if e_calc is not None and e_calc > 0 and k_mat is not None and "A_surface_m2" in geo_cap:
            k2 = _req_pos("conductivite_w_m_k", k_mat)
            A_ref = float(geo_cap["A_surface_m2"])
            R_cond = e_calc / (k2 * A_ref) if A_ref > 0 else None
            rapport["thermique"]["R_conduction_K_W"] = R_cond

            if h_i is not None:
                rapport["thermique"]["R_convection_interne_K_W"] = 1.0 / (_req_pos("h_interne_w_m2_k", h_i) * A_ref)
            else:
                _push_inconnue(rapport, "partielles", "R convection interne", "Calculable si h_interne_w_m2_k est fourni.")

            if h_o is not None:
                rapport["thermique"]["R_convection_externe_K_W"] = 1.0 / (_req_pos("h_externe_w_m2_k", h_o) * A_ref)
            else:
                _push_inconnue(rapport, "partielles", "R convection externe", "Calculable si h_externe_w_m2_k est fourni.")

            if ("R_convection_interne_K_W" in rapport["thermique"]) and ("R_convection_externe_K_W" in rapport["thermique"]) and (R_cond is not None):
                rapport["thermique"]["R_totale_K_W"] = (
                    float(rapport["thermique"]["R_convection_interne_K_W"])
                    + float(R_cond)
                    + float(rapport["thermique"]["R_convection_externe_K_W"])
                )
        else:
            if k_mat is None:
                _push_inconnue(rapport, "partielles", "thermique (conduction)", "Calculable si conductivite_w_m_k est fournie.")

        # ------------------------------------------------------------
        # 11) Masse
        # ------------------------------------------------------------
        if e_calc is not None and e_calc > 0 and geo_cap and "A_surface_m2" in geo_cap:
            A_surf = float(geo_cap["A_surface_m2"])
            V_calotte = _volume_calotte_mince(geo_cap, e_calc)
            V_bride = 0.0
            if bride_geo:
                V_bride = bride_geo["surface_annulaire_bride_m2"] * bride_geo["epaisseur_bride_m"]

            rapport["masse"].update({
                "surface_calotte_m2": A_surf,
                "volume_calotte_m3": V_calotte,
                "volume_bride_m3": V_bride,
                "volume_total_m3": V_calotte + V_bride,
            })

            if densite is not None:
                rho = _req_pos("densite_kg_m3", densite)
                rapport["masse"]["masse_kg"] = rho * (V_calotte + V_bride)
            else:
                _push_inconnue(rapport, "partielles", "masse", "Calculable si densite_kg_m3 est fournie.")

        # ------------------------------------------------------------
        # 12) Fabrication / CAO export
        # ------------------------------------------------------------
        if e_calc is not None and e_calc > 0 and geo_cap:
            chanfrein = _borne(
                self.regles_forme.ratio_chanfrein_sur_epaisseur * e_calc,
                self.regles_forme.chanfrein_min_m,
                self.regles_forme.chanfrein_max_m,
            )
            conge = _borne(
                self.regles_forme.ratio_conge_sur_epaisseur * e_calc,
                self.regles_forme.conge_min_m,
                self.regles_forme.conge_max_m,
            )

            R_int = float(geo_cap["R_m"])
            R_ext = R_int + e_calc

            cao = {
                "forme": "calotte_spherique_avec_bride",
                "diametre_ouverture_m": D_ouv,
                "rayon_base_calotte_m": float(geo_cap["a_m"]),
                "hauteur_bombe_interieure_m": float(geo_cap["h_m"]),
                "rayon_courbure_interieur_m": R_int,
                "rayon_courbure_exterieur_m": R_ext,
                "epaisseur_calotte_m": e_calc,
                "diametre_exterieur_calotte_base_m": 2.0 * float(geo_cap["a_m"]),
                "bride": bride_geo,
                "assemblage": assemblage,
                "chanfrein_m": chanfrein,
                "conge_m": conge,
                "etat_surface": {
                    "face_joint_ra_um": self.regles_forme.rugosite_face_joint_ra_um,
                    "interieur_ra_um": self.regles_forme.rugosite_interieure_ra_um,
                    "exterieur_ra_um": self.regles_forme.rugosite_exterieure_ra_um,
                },
                "tolerances": {
                    "epaisseur_m": self.regles_forme.tolerance_epaisseur_m,
                    "bride_m": self.regles_forme.tolerance_bride_m,
                    "position_trous_m": self.regles_forme.tolerance_position_trous_m,
                },
            }
            rapport["geometrie"]["cao"] = cao
            rapport["fabrication"].update(cao["etat_surface"])
            rapport["fabrication"]["tolerances"] = cao["tolerances"]

        # ------------------------------------------------------------
        # 13) Vérifications de cohérence cylindre/couvercle
        # ------------------------------------------------------------
        if cyl_auto["diametre_bride_externe_m"] is not None and bride_geo:
            rapport["verifications"]["diametre_bride_coherent_avec_cylindre"] = (
                abs(float(cyl_auto["diametre_bride_externe_m"]) - float(bride_geo["diametre_bride_externe_m"])) <= 1e-9
            )

        if cyl_auto["diametre_cercle_percage_m"] is not None and dpc_eff is not None:
            rapport["verifications"]["DPC_coherent_avec_cylindre"] = (
                abs(float(cyl_auto["diametre_cercle_percage_m"]) - float(dpc_eff)) <= 1e-9
            )

        if cyl_auto["nb_trous"] is not None and nb_vis_eff is not None:
            rapport["verifications"]["nb_trous_coherent_avec_cylindre"] = (int(cyl_auto["nb_trous"]) == int(nb_vis_eff))

        # ------------------------------------------------------------
        # 14) Mode strict
        # ------------------------------------------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CouvercleCylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport