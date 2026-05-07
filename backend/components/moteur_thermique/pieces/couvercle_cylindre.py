
# backend/pieces/couvercle_cylindre.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Literal, List
import math

# ============================================================
# Imports projet (avec fallbacks)
# ============================================================

# --- Cylindrée / chambre ---
try:
    from backend.components.moteur_thermique.modules.calcul_cylindree import calcul_cylindree_unitaire
except Exception:  # pragma: no cover
    def calcul_cylindree_unitaire(
        *,
        alesage_m: float,
        course_m: float,
        allow_zero: bool = False,
        return_details: bool = False,
    ) -> float:
        if alesage_m <= 0 or course_m <= 0:
            raise ValueError("alesage_m et course_m doivent être > 0")
        return (math.pi * (alesage_m ** 2) / 4.0) * course_m

# --- Matériaux ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None

# --- Pièce associée ---
try:
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre
except Exception:  # pragma: no cover
    try:
        from pieces.cylindre import Cylindre  # type: ignore
    except Exception:  # pragma: no cover
        Cylindre = None  # type: ignore

# --- Précharge / visserie ---
try:
    from backend.components.moteur_thermique.modules.calcul_precharge_vis import (
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

def _float_if_finite(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


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
    a = _req_pos("rayon_base_m", rayon_base_m)
    p = _req_pos("pression_dimensionnement_pa", pression_dimensionnement_pa, strictly=False)
    s = _req_pos("sigma_admissible_eff_pa", sigma_admissible_eff_pa)

    phi = p / s if s > 0 else 0.0
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
# Culasse / chambre / fermeture haute / fluides associés
# ============================================================

TypeJointCulasse = Literal["plat", "torique", "mls", "metal"]
TypeOrganePassage = Literal["admission", "echappement"]
TypeOrganeHaut = Literal["bougie", "injecteur", "injecteur_bougie", "aucun"]

@dataclass(frozen=True)
class DonneesChambreHaute:
    taux_compression: Optional[float] = None
    volume_mort_m3: Optional[float] = None
    volume_chambre_m3: Optional[float] = None
    jeu_haut_m: Optional[float] = None
    surface_squish_m2: Optional[float] = None
    hauteur_locale_min_m: Optional[float] = None
    angle_toit_deg: Optional[float] = None

@dataclass(frozen=True)
class CulasseSpec:
    epaisseur_culasse_m: Optional[float] = None
    volume_matiere_m3: Optional[float] = None
    surface_appui_joint_m2: Optional[float] = None
    gradient_thermique_travers_epaisseur_k: Optional[float] = None
    temperature_metal_max_C: Optional[float] = None

@dataclass(frozen=True)
class OrganePassageHaut:
    nom: str
    type_organe: TypeOrganePassage
    nb: int = 1
    diametre_siege_m: Optional[float] = None
    levee_max_m: Optional[float] = None
    coefficient_decharge: float = 1.0
    perte_charge_zeta: Optional[float] = None
    debit_massique_kg_s: Optional[float] = None
    masse_volumique_gaz_kg_m3: Optional[float] = None
    viscosite_gaz_pa_s: Optional[float] = None
    temperature_gaz_k: Optional[float] = None

@dataclass(frozen=True)
class OrganeAllumageInjection:
    type_organe: TypeOrganeHaut = "aucun"
    nombre: int = 1
    diametre_orifice_m: Optional[float] = None
    temperature_piece_max_C: Optional[float] = None
    saillie_m: Optional[float] = None

@dataclass(frozen=True)
class JointCulasseSpec:
    type_joint: TypeJointCulasse = "plat"
    largeur_appui_m: Optional[float] = None
    rayon_moyen_m: Optional[float] = None
    aire_appui_m2: Optional[float] = None
    pression_contact_min_pa: Optional[float] = None
    force_joint_additionnelle_n: float = 0.0
    epaisseur_m: Optional[float] = None
    conductivite_w_m_k: Optional[float] = None

@dataclass(frozen=True)
class SerrageCulasseSpec:
    nb_vis: Optional[int] = None
    vis_d_nominal_mm: Optional[float] = None
    vis_pas_mm: Optional[float] = None
    classe_vis_iso898: Optional[str] = None
    limite_elastique_vis_pa: Optional[float] = None
    facteur_securite_vis: float = 1.5
    facteur_frottement_k: float = 0.20

    rigidite_vis_n_m: Optional[float] = None
    rigidite_empilage_n_m: Optional[float] = None
    longueur_serree_vis_m: Optional[float] = None
    longueur_empilage_m: Optional[float] = None
    alpha_vis_1_k: Optional[float] = None
    alpha_empilage_1_k: Optional[float] = None
    delta_temperature_serrage_k: Optional[float] = None

    securite_desserrage_min: float = 1.10

@dataclass(frozen=True)
class LubrificationHautSpec:
    debit_massique_huile_kg_s: Optional[float] = None
    masse_volumique_huile_kg_m3: Optional[float] = None
    viscosite_dynamique_pa_s: Optional[float] = None
    temperature_huile_C: Optional[float] = None

    diametre_galerie_m: Optional[float] = None
    longueur_galerie_m: Optional[float] = None
    nb_points_lubrifies: int = 0

    pression_amont_pa: Optional[float] = None
    pression_aval_pa: Optional[float] = None

    epaisseur_film_estimee_m: Optional[float] = None
    epaisseur_film_min_requise_m: Optional[float] = None
    charge_normale_n: Optional[float] = None
    aire_portante_m2: Optional[float] = None
    vitesse_glissement_m_s: Optional[float] = None

@dataclass(frozen=True)
class RefroidissementHautSpec:
    puissance_thermique_w: Optional[float] = None
    temperature_fluide_entree_C: Optional[float] = None
    temperature_ambiante_C: Optional[float] = None

    h_interne_w_m2_k: Optional[float] = None
    h_externe_w_m2_k: Optional[float] = None
    surface_interne_m2: Optional[float] = None
    surface_externe_m2: Optional[float] = None

    conductivite_piece_w_m_k: Optional[float] = None
    epaisseur_eq_m: Optional[float] = None
    delta_temperature_extreme_k: Optional[float] = None


def _section_circulaire(d_m: float) -> float:
    d = _req_pos("d_m", d_m)
    return math.pi * d * d / 4.0

def _surface_rideau_organe(diametre_siege_m: float, levee_m: float, nb: int = 1, coefficient_decharge: float = 1.0) -> float:
    d = _req_pos("diametre_siege_m", diametre_siege_m)
    l = _req_pos("levee_m", levee_m, strictly=False)
    n = _req_int_pos("nb", nb)
    cd = _req_pos("coefficient_decharge", coefficient_decharge, strictly=False)
    return math.pi * d * l * n * cd

def _perte_charge_singuliere(rho: float, v: float, zeta: float) -> float:
    return 0.5 * _req_pos("rho", rho) * (_req_pos("v", v, strictly=False) ** 2) * _req_pos("zeta", zeta, strictly=False)

def _reynolds(rho: float, v: float, D: float, mu: float) -> float:
    return _req_pos("rho", rho) * _req_pos("v", v, strictly=False) * _req_pos("D", D) / _req_pos("mu", mu)

def _debit_volumique_depuis_massique(mdot: float, rho: float) -> float:
    return _req_pos("mdot", mdot, strictly=False) / _req_pos("rho", rho)

def _volume_chambre_depuis_donnees(
    *,
    volume_deplace_unitaire_m3: Optional[float],
    taux_compression: Optional[float],
    volume_mort_m3: Optional[float],
    volume_chambre_m3: Optional[float],
) -> Dict[str, Optional[float]]:
    out = {
        "volume_deplace_unitaire_m3": volume_deplace_unitaire_m3,
        "volume_chambre_m3": None,
        "volume_mort_m3": None,
        "taux_compression": None,
    }

    Vd = volume_deplace_unitaire_m3

    if volume_chambre_m3 is not None:
        Vc = _req_pos("volume_chambre_m3", volume_chambre_m3)
        out["volume_chambre_m3"] = Vc
        out["volume_mort_m3"] = Vc
        if Vd is not None:
            out["taux_compression"] = (Vd + Vc) / Vc
        return out

    if volume_mort_m3 is not None:
        Vc = _req_pos("volume_mort_m3", volume_mort_m3)
        out["volume_chambre_m3"] = Vc
        out["volume_mort_m3"] = Vc
        if Vd is not None:
            out["taux_compression"] = (Vd + Vc) / Vc
        return out

    if taux_compression is not None and Vd is not None:
        rc = _req_pos("taux_compression", taux_compression)
        if rc <= 1.0:
            raise ValueError("taux_compression doit être > 1.")
        Vc = Vd / (rc - 1.0)
        out["volume_chambre_m3"] = Vc
        out["volume_mort_m3"] = Vc
        out["taux_compression"] = rc
        return out

    return out

def _eta_remplissage_depuis_debit(
    *,
    debit_massique_air_kg_s: float,
    masse_volumique_air_kg_m3: float,
    cylindree_totale_m3: float,
    rpm: float,
    temps_moteur: int,
) -> float:
    mdot = _req_pos("debit_massique_air_kg_s", debit_massique_air_kg_s, strictly=False)
    rho = _req_pos("masse_volumique_air_kg_m3", masse_volumique_air_kg_m3)
    Vd = _req_pos("cylindree_totale_m3", cylindree_totale_m3)
    n = _req_pos("rpm", rpm)
    cps = n / 60.0
    if int(temps_moteur) == 4:
        cps /= 2.0
    q_reel = mdot / rho
    q_theorique = Vd * cps
    return q_reel / q_theorique if q_theorique > 0 else float("nan")

def _rigidite_equivalente_serie(k1: float, k2: float) -> float:
    a = _req_pos("k1", k1)
    b = _req_pos("k2", k2)
    return (a * b) / (a + b)

def _variation_precharge_thermique(
    *,
    rigidite_vis_n_m: float,
    rigidite_empilage_n_m: float,
    alpha_vis_1_k: float,
    alpha_empilage_1_k: float,
    longueur_serree_vis_m: float,
    longueur_empilage_m: float,
    delta_temperature_k: float,
) -> Dict[str, float]:
    k_eq = _rigidite_equivalente_serie(rigidite_vis_n_m, rigidite_empilage_n_m)
    dL_vis = _req_pos("alpha_vis_1_k", alpha_vis_1_k, strictly=False) * _req_pos("longueur_serree_vis_m", longueur_serree_vis_m) * _req_finite("delta_temperature_k", delta_temperature_k)
    dL_emp = _req_pos("alpha_empilage_1_k", alpha_empilage_1_k, strictly=False) * _req_pos("longueur_empilage_m", longueur_empilage_m) * _req_finite("delta_temperature_k", delta_temperature_k)
    dF = k_eq * (dL_emp - dL_vis)
    return {
        "rigidite_equivalente_n_m": k_eq,
        "delta_L_vis_m": dL_vis,
        "delta_L_empilage_m": dL_emp,
        "delta_precharge_thermique_N": dF,
    }

def _pression_contact_reelle(force_n: float, aire_m2: float) -> float:
    return _req_pos("force_n", force_n, strictly=False) / _req_pos("aire_m2", aire_m2)

def _resistance_convection(h: float, A: float) -> float:
    return 1.0 / (_req_pos("h", h) * _req_pos("A", A))

def _resistance_conduction_plane(epaisseur_m: float, k: float, A: float) -> float:
    return _req_pos("epaisseur_m", epaisseur_m, strictly=False) / (_req_pos("k", k) * _req_pos("A", A))

def _poiseuille_tube_circulaire(mu: float, L: float, Q: float, D: float) -> float:
    return (128.0 * _req_pos("mu", mu) * _req_pos("L", L, strictly=False) * _req_pos("Q", Q, strictly=False)) / (math.pi * (_req_pos("D", D) ** 4))


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

    circularite_m: float = 0.00003
    cylindricite_m: float = 0.00005
    coaxialite_m: float = 0.00005
    perpendicularite_faces_m: float = 0.00003

    tolerance_epaisseur_m: float = 0.00010
    tolerance_bride_m: float = 0.00010
    tolerance_position_trous_m: float = 0.00010

    surepaisseur_usinage_m: float = 0.00050
    surepaisseur_finition_m: float = 0.00010


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
        "course_m": None,
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
    out["course_m"] = ent.get("course_m")
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
    cylindre: Optional[Any] = None

    # Géométrie ouverture / appui
    diametre_ouverture_m: Optional[float] = None
    rayon_appui_m: Optional[float] = None
    source_appui: SourceAppui = "ouverture"
    rayon_externe_m: Optional[float] = None

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

    # Liaison moteur / cycle
    course_m: Optional[float] = None
    rpm: Optional[float] = None
    nombre_cylindres: int = 1
    temps_moteur: Literal[2, 4] = 4
    pression_admission_pa: Optional[float] = None
    pression_echappement_pa: Optional[float] = None

    # Culasse / chambre
    chambre_haute: Optional[DonneesChambreHaute] = None
    culasse_spec: Optional[CulasseSpec] = None

    organes_admission: Optional[List[OrganePassageHaut]] = None
    organes_echappement: Optional[List[OrganePassageHaut]] = None
    organes_allumage_injection: Optional[List[OrganeAllumageInjection]] = None

    joint_culasse_spec: Optional[JointCulasseSpec] = None
    serrage_culasse_spec: Optional[SerrageCulasseSpec] = None

    lubrification_haute: Optional[LubrificationHautSpec] = None
    refroidissement_haut: Optional[RefroidissementHautSpec] = None

    # Règles explicites de forme/fabrication
    regles_forme: ReglesFormeCouvercle = field(default_factory=ReglesFormeCouvercle)

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
            "culasse": {},
            "combustion_haute": {},
            "distribution": {"admission": [], "echappement": [], "organes_hauts": []},
            "lubrification": {},
            "refroidissement_haut": {},
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
        D_ouv = _float_if_finite(self.diametre_ouverture_m)
        if D_ouv is None and cyl_auto["diametre_interieur_nominal_m"] is not None:
            D_ouv = _float_if_finite(cyl_auto["diametre_interieur_nominal_m"])
        elif D_ouv is None and cyl is not None:
            try:
                if hasattr(cyl, "alesage_m"):
                    D_ouv = _float_if_finite(getattr(cyl, "alesage_m"))
            except Exception:
                D_ouv = None

        p_serv = _float_if_finite(self.pression_service_pa)
        p_max = _float_if_finite(self.pression_max_pa)
        if p_serv is None and cyl_auto["pression_service_pa"] is not None:
            p_serv = _float_if_finite(cyl_auto["pression_service_pa"])
        if p_max is None and cyl_auto["pression_max_pa"] is not None:
            p_max = _float_if_finite(cyl_auto["pression_max_pa"])

        if D_ouv is None or D_ouv <= 0.0:
            _push_inconnue(rapport, "impossibles", "diametre_ouverture_m", "Donner diametre_ouverture_m ou fournir un cylindre analysable.")
            D_ouv_val: Optional[float] = None
        else:
            D_ouv_val = _req_pos("diametre_ouverture_m", D_ouv)

        if p_max is None:
            _push_inconnue(rapport, "impossibles", "pression_max_pa", "Nécessaire pour dimensionner le couvercle.")
            p_max_v: Optional[float] = None
        else:
            p_max_v = _req_pos("pression_max_pa", p_max, strictly=False)

        p_serv_v = 0.0 if p_serv is None else _req_pos("pression_service_pa", p_serv, strictly=False)
        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        FS = _req_pos("facteur_securite", self.facteur_securite)
        e_min = _req_pos("epaisseur_min_fabrication_m", self.epaisseur_min_fabrication_m, strictly=False)

        # appui
        a = _float_if_finite(self.rayon_appui_m)
        if a is None:
            if self.source_appui == "ouverture" and D_ouv_val is not None:
                a = 0.5 * D_ouv_val
            elif self.source_appui == "cylindre_sans_brides":
                if cyl_auto["diametre_exterieur_nominal_m"] is not None:
                    a = 0.5 * float(cyl_auto["diametre_exterieur_nominal_m"])
            elif self.source_appui in ("cylindre_avec_brides", "cylindre_cao_bride"):
                if cyl_auto["diametre_bride_externe_m"] is not None:
                    a = 0.5 * float(cyl_auto["diametre_bride_externe_m"])
                elif isinstance(cyl_rep, dict):
                    geo_tmp = cyl_rep.get("geometrie", {}) if isinstance(cyl_rep.get("geometrie", {}), dict) else {}
                    if geo_tmp.get("rayon_externe_avec_brides_m") is not None:
                        a = float(geo_tmp["rayon_externe_avec_brides_m"])

        if a is None or a <= 0.0:
            if D_ouv_val is not None:
                _push_inconnue(rapport, "partielles", "rayon_appui_m", "Non déduit ; repli sur rayon ouverture.")
                a = 0.5 * D_ouv_val
            else:
                _push_inconnue(rapport, "impossibles", "rayon_appui_m", "Impossible de déterminer le rayon d'appui.")
                a = None

        r_ext = _float_if_finite(self.rayon_externe_m)
        if r_ext is None:
            if cyl_auto["diametre_bride_externe_m"] is not None:
                r_ext = 0.5 * float(cyl_auto["diametre_bride_externe_m"])
            elif a is not None:
                r_ext = a

        if r_ext is None or r_ext <= 0.0:
            _push_inconnue(rapport, "partielles", "rayon_externe_m", "Non déterminé.")
            r_ext = a

        course_eff = _float_if_finite(self.course_m)
        if course_eff is None and cyl_auto["course_m"] is not None:
            course_eff = _float_if_finite(cyl_auto["course_m"])
        if course_eff is None and cyl is not None and hasattr(cyl, "course_m"):
            try:
                course_eff = _float_if_finite(getattr(cyl, "course_m"))
            except Exception:
                course_eff = None

        rapport["entrees"].update({
            "diametre_ouverture_m": D_ouv_val,
            "rayon_appui_m": a,
            "source_appui": self.source_appui,
            "rayon_externe_m": r_ext,
            "pression_service_pa": p_serv_v,
            "pression_max_pa": p_max_v,
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
            "course_m": course_eff,
            "rpm": self.rpm,
            "nombre_cylindres": self.nombre_cylindres,
            "temps_moteur": self.temps_moteur,
            "pression_admission_pa": self.pression_admission_pa,
            "pression_echappement_pa": self.pression_echappement_pa,
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
        delta_p = None
        A_ouverture = None
        F_sep = None
        if p_max_v is not None:
            delta_p = max(0.0, p_max_v - p_ext)
        if D_ouv_val is not None:
            A_ouverture = math.pi * (0.5 * D_ouv_val) ** 2
        if delta_p is not None and A_ouverture is not None:
            F_sep = calcul_force_separation(delta_p, A_ouverture)
        else:
            _push_inconnue(rapport, "impossibles", "charges pression", "Impossible de calculer les charges sans pression et aire d'ouverture.")

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
            if a is None:
                raise ValueError("rayon d'appui indisponible.")
            if self.hauteur_bombe_m is not None or self.rayon_courbure_m is not None:
                geo_cap = _calotte_spherique_resoudre_geometrie(
                    rayon_base_m=a,
                    hauteur_bombe_m=self.hauteur_bombe_m,
                    rayon_courbure_m=self.rayon_courbure_m,
                )
                rapport["dimensionnement"]["source_forme_calotte"] = "input"
            else:
                if sigma_eff is None or delta_p is None:
                    raise ValueError("Impossible de proposer automatiquement la forme sans sigma_eff et delta_p.")
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
            elif "R_m" in geo_cap and delta_p is not None:
                e_req_membrane = _epaisseur_requise_calotte_spherique_membrane(
                    p_Pa=delta_p,
                    R_m=float(geo_cap["R_m"]),
                    sigma_admissible_eff_Pa=float(sigma_eff),
                )
                e_calc = max(float(e_req_membrane), float(e_min))
                rapport["dimensionnement"]["epaisseur_source"] = "dimensionnement_membrane"
            else:
                _push_inconnue(rapport, "impossibles", "epaisseur_m", "Géométrie calotte ou charge non disponible.")

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
        if e_bride is not None and l_bride is not None and a is not None and r_ext is not None:
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
        if e_calc is not None and e_calc > 0 and "R_m" in geo_cap and delta_p is not None:
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
            _push_inconnue(rapport, "impossibles", "contraintes", "Impossible sans epaisseur_retenue_m, charge et géométrie calotte (R).")

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
        F_pre_tot = None
        if F_sep is not None:
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

        if nb_vis_eff is None and F_pre_tot is not None:
            if As_m2 is not None and sigma_eff_vis is not None and As_m2 > 0 and sigma_eff_vis > 0:
                F_cap = As_m2 * sigma_eff_vis
                nb_vis_eff = int(math.ceil(F_pre_tot / F_cap))
                if nb_vis_eff % 2 != 0:
                    nb_vis_eff += 1
            elif visserie_cyl is not None and visserie_cyl.get("nb_vis") is not None:
                nb_vis_eff = int(visserie_cyl["nb_vis"])

        F_par_vis = None
        if nb_vis_eff is not None and F_pre_tot is not None:
            nb_vis_eff = _req_int_pos("nb_vis", int(nb_vis_eff))
            F_par_vis = F_pre_tot / nb_vis_eff if nb_vis_eff > 0 else None
        else:
            _push_inconnue(rapport, "partielles", "nb_vis", "Impossible de fixer le nombre de vis sans données visserie suffisantes ou cylindre CAO.")

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

        couple_serrage = None
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
        # 8bis) Culasse / chambre / fermeture haute
        # ------------------------------------------------------------
        Vd_unit = None
        if course_eff is not None and D_ouv_val is not None:
            try:
                Vd_unit = calcul_cylindree_unitaire(alesage_m=D_ouv_val, course_m=_req_pos("course_m", course_eff))
            except Exception as e:
                _push_inconnue(rapport, "partielles", "volume déplacé unitaire", f"Impossible de calculer Vd: {e!r}")
        else:
            _push_inconnue(rapport, "partielles", "course_m", "Nécessaire pour calculer le volume déplacé et la chambre.")

        chambre = self.chambre_haute or DonneesChambreHaute()
        try:
            res_chambre = _volume_chambre_depuis_donnees(
                volume_deplace_unitaire_m3=Vd_unit,
                taux_compression=chambre.taux_compression,
                volume_mort_m3=chambre.volume_mort_m3,
                volume_chambre_m3=chambre.volume_chambre_m3,
            )
            rapport["combustion_haute"].update(res_chambre)
            rapport["combustion_haute"].update({
                "jeu_haut_m": chambre.jeu_haut_m,
                "surface_squish_m2": chambre.surface_squish_m2,
                "hauteur_locale_min_m": chambre.hauteur_locale_min_m,
                "angle_toit_deg": chambre.angle_toit_deg,
            })
        except Exception as e:
            _push_inconnue(rapport, "partielles", "chambre de combustion", f"Impossible de résoudre la chambre: {e!r}")

        culasse = self.culasse_spec or CulasseSpec()
        rapport["culasse"].update({
            "epaisseur_culasse_m": culasse.epaisseur_culasse_m,
            "surface_appui_joint_m2": culasse.surface_appui_joint_m2,
            "gradient_thermique_travers_epaisseur_k": culasse.gradient_thermique_travers_epaisseur_k,
            "temperature_metal_max_C": culasse.temperature_metal_max_C,
            "volume_matiere_m3": culasse.volume_matiere_m3,
        })

        if culasse.volume_matiere_m3 is not None and densite is not None:
            try:
                rapport["culasse"]["masse_culasse_kg"] = _req_pos("densite_kg_m3", densite) * _req_pos("volume_matiere_m3", culasse.volume_matiere_m3, strictly=False)
            except Exception as e:
                _push_inconnue(rapport, "partielles", "masse culasse", f"Impossible de calculer la masse culasse: {e!r}")
        elif culasse.volume_matiere_m3 is not None and densite is None:
            _push_inconnue(rapport, "partielles", "masse culasse", "Calculable si densite_kg_m3 est fournie.")

        # ------------------------------------------------------------
        # 8ter) Joint de culasse / pression de contact / serrage à chaud
        # ------------------------------------------------------------
        joint_spec = self.joint_culasse_spec
        serrage_spec = self.serrage_culasse_spec

        aire_appui_joint = None
        force_joint_min_contact = None
        pression_contact_reelle = None

        if joint_spec is not None:
            if joint_spec.aire_appui_m2 is not None:
                aire_appui_joint = _req_pos("aire_appui_m2", joint_spec.aire_appui_m2)
            elif joint_spec.largeur_appui_m is not None and D_ouv_val is not None:
                largeur = _req_pos("largeur_appui_m", joint_spec.largeur_appui_m)
                r_moy = joint_spec.rayon_moyen_m
                if r_moy is None:
                    r_moy = 0.5 * D_ouv_val + 0.5 * largeur
                aire_appui_joint = 2.0 * math.pi * _req_pos("rayon_moyen_m", r_moy) * largeur

            if joint_spec.pression_contact_min_pa is not None and aire_appui_joint is not None:
                force_joint_min_contact = _req_pos("pression_contact_min_pa", joint_spec.pression_contact_min_pa, strictly=False) * aire_appui_joint

            rapport["culasse"]["joint_culasse"] = {
                "type_joint": joint_spec.type_joint,
                "aire_appui_m2": aire_appui_joint,
                "pression_contact_min_pa": joint_spec.pression_contact_min_pa,
                "force_joint_min_contact_N": force_joint_min_contact,
                "force_joint_additionnelle_n": joint_spec.force_joint_additionnelle_n,
                "epaisseur_m": joint_spec.epaisseur_m,
                "conductivite_w_m_k": joint_spec.conductivite_w_m_k,
            }

        if serrage_spec is not None:
            if serrage_spec.nb_vis is not None:
                nb_vis_eff = _req_int_pos("nb_vis", serrage_spec.nb_vis)
                rapport["assemblage"]["nb_vis"] = nb_vis_eff

            if serrage_spec.limite_elastique_vis_pa is not None:
                Re_vis = _req_pos("limite_elastique_vis_pa", serrage_spec.limite_elastique_vis_pa)
            elif serrage_spec.classe_vis_iso898 is not None:
                Re_vis = _iso898_yield_strength_pa_from_class(serrage_spec.classe_vis_iso898)

            if serrage_spec.vis_d_nominal_mm is not None:
                filetage_impose = _filetage_depuis_nominal(
                    d_nominal_mm=_req_pos("vis_d_nominal_mm", serrage_spec.vis_d_nominal_mm),
                    pas_mm=serrage_spec.vis_pas_mm,
                )
                As_m2 = float(filetage_impose["As_m2"])
                rapport["assemblage"]["filetage"] = filetage_impose

            if Re_vis is not None:
                sigma_eff_vis = _req_pos("limite_elastique_vis_pa", Re_vis) / _req_pos("facteur_securite_vis", serrage_spec.facteur_securite_vis)
                rapport["assemblage"]["sigma_admissible_vis_eff_Pa"] = sigma_eff_vis

        F_joint_joint_culasse = None
        if joint_spec is not None:
            F_joint_joint_culasse = max(
                float(force_joint_min_contact or 0.0),
                float(joint_spec.force_joint_additionnelle_n or 0.0),
            )

            if F_joint_joint_culasse > float(F_joint or 0.0) and F_sep is not None:
                F_joint = F_joint_joint_culasse
                F_pre_tot = calcul_precharge_vis_totale(
                    force_separation_n=F_sep,
                    force_joint_n=F_joint,
                    facteur_securite=float((serrage_spec.facteur_securite_vis if serrage_spec is not None else 1.5)),
                )
                rapport["assemblage"]["force_joint_N"] = F_joint
                rapport["assemblage"]["force_precharge_totale_N"] = F_pre_tot

                if nb_vis_eff is not None:
                    F_par_vis = F_pre_tot / nb_vis_eff
                    rapport["assemblage"]["force_precharge_par_vis_N"] = F_par_vis

                    d_nom_vis_m = None
                    if filetage_impose is not None:
                        d_nom_vis_m = float(filetage_impose["d_nominal_mm"]) / 1000.0
                    if d_nom_vis_m is not None:
                        k_serrage = serrage_spec.facteur_frottement_k if serrage_spec is not None else 0.2
                        rapport["assemblage"]["couple_serrage_par_vis_Nm"] = calcul_couple_serrage(F_par_vis, d_nom_vis_m, k_serrage)

        if F_pre_tot is not None and aire_appui_joint is not None:
            pression_contact_reelle = _pression_contact_reelle(F_pre_tot, aire_appui_joint)
            rapport["culasse"]["pression_contact_reelle_pa"] = pression_contact_reelle

        if serrage_spec is not None:
            if (
                F_pre_tot is not None
                and serrage_spec.rigidite_vis_n_m is not None
                and serrage_spec.rigidite_empilage_n_m is not None
                and serrage_spec.alpha_vis_1_k is not None
                and serrage_spec.alpha_empilage_1_k is not None
                and serrage_spec.longueur_serree_vis_m is not None
                and serrage_spec.longueur_empilage_m is not None
                and serrage_spec.delta_temperature_serrage_k is not None
            ):
                try:
                    delta_precharge_thermique = _variation_precharge_thermique(
                        rigidite_vis_n_m=serrage_spec.rigidite_vis_n_m,
                        rigidite_empilage_n_m=serrage_spec.rigidite_empilage_n_m,
                        alpha_vis_1_k=serrage_spec.alpha_vis_1_k,
                        alpha_empilage_1_k=serrage_spec.alpha_empilage_1_k,
                        longueur_serree_vis_m=serrage_spec.longueur_serree_vis_m,
                        longueur_empilage_m=serrage_spec.longueur_empilage_m,
                        delta_temperature_k=serrage_spec.delta_temperature_serrage_k,
                    )
                    precharge_residuelle_chaud = F_pre_tot + delta_precharge_thermique["delta_precharge_thermique_N"]
                    rapport["culasse"]["variation_precharge_thermique"] = delta_precharge_thermique
                    rapport["culasse"]["precharge_residuelle_chaud_N"] = precharge_residuelle_chaud

                    F_ref_desserrage = float(F_sep or 0.0) + max(0.0, float(F_joint or 0.0))
                    if F_ref_desserrage > 0.0:
                        securite_desserrage = precharge_residuelle_chaud / F_ref_desserrage
                        rapport["culasse"]["securite_desserrage"] = securite_desserrage
                        rapport["verifications"]["desserrage_acceptable_a_chaud"] = (
                            securite_desserrage >= float(serrage_spec.securite_desserrage_min)
                        )
                except Exception as e:
                    _push_inconnue(rapport, "partielles", "perte de précharge à chaud", f"Impossible de calculer la variation thermique de précharge: {e!r}")
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "perte de précharge à chaud",
                    "Calculable si rigidités, longueurs, coefficients de dilatation et delta_temperature_serrage_k sont fournis."
                )

        # ------------------------------------------------------------
        # 8quater) Distribution / admission / échappement
        # ------------------------------------------------------------
        def _analyser_organe_passage(org: OrganePassageHaut) -> Dict[str, Any]:
            out: Dict[str, Any] = {
                "nom": org.nom,
                "type_organe": org.type_organe,
                "nb": org.nb,
                "diametre_siege_m": org.diametre_siege_m,
                "levee_max_m": org.levee_max_m,
                "coefficient_decharge": org.coefficient_decharge,
                "debit_massique_kg_s": org.debit_massique_kg_s,
                "temperature_gaz_k": org.temperature_gaz_k,
                "aire_geometrique_m2": None,
                "aire_rideau_effective_m2": None,
                "vitesse_gaz_m_s": None,
                "Re": None,
                "perte_charge_pa": None,
            }

            if org.diametre_siege_m is not None:
                out["aire_geometrique_m2"] = _section_circulaire(org.diametre_siege_m) * _req_int_pos("nb", org.nb)

            if org.diametre_siege_m is not None and org.levee_max_m is not None:
                out["aire_rideau_effective_m2"] = _surface_rideau_organe(
                    diametre_siege_m=org.diametre_siege_m,
                    levee_m=org.levee_max_m,
                    nb=org.nb,
                    coefficient_decharge=org.coefficient_decharge,
                )

            if (
                org.debit_massique_kg_s is not None
                and org.masse_volumique_gaz_kg_m3 is not None
                and out["aire_rideau_effective_m2"] is not None
            ):
                qv = _debit_volumique_depuis_massique(org.debit_massique_kg_s, org.masse_volumique_gaz_kg_m3)
                Aeff = float(out["aire_rideau_effective_m2"])
                if Aeff > 0.0:
                    out["vitesse_gaz_m_s"] = qv / Aeff

                if org.viscosite_gaz_pa_s is not None and out["vitesse_gaz_m_s"] is not None and org.diametre_siege_m is not None:
                    out["Re"] = _reynolds(
                        rho=org.masse_volumique_gaz_kg_m3,
                        v=out["vitesse_gaz_m_s"],
                        D=org.diametre_siege_m,
                        mu=org.viscosite_gaz_pa_s,
                    )

                if org.perte_charge_zeta is not None and out["vitesse_gaz_m_s"] is not None:
                    out["perte_charge_pa"] = _perte_charge_singuliere(
                        rho=org.masse_volumique_gaz_kg_m3,
                        v=out["vitesse_gaz_m_s"],
                        zeta=org.perte_charge_zeta,
                    )
            return out

        for org in list(self.organes_admission or []):
            try:
                rapport["distribution"]["admission"].append(_analyser_organe_passage(org))
            except Exception as e:
                _push_inconnue(rapport, "partielles", f"distribution admission:{org.nom}", f"{e!r}")

        for org in list(self.organes_echappement or []):
            try:
                rapport["distribution"]["echappement"].append(_analyser_organe_passage(org))
            except Exception as e:
                _push_inconnue(rapport, "partielles", f"distribution échappement:{org.nom}", f"{e!r}")

        for org in list(self.organes_allumage_injection or []):
            try:
                out_org = {
                    "type_organe": org.type_organe,
                    "nombre": org.nombre,
                    "diametre_orifice_m": org.diametre_orifice_m,
                    "temperature_piece_max_C": org.temperature_piece_max_C,
                    "saillie_m": org.saillie_m,
                    "section_totale_m2": None,
                }
                if org.diametre_orifice_m is not None:
                    out_org["section_totale_m2"] = _section_circulaire(org.diametre_orifice_m) * _req_int_pos("nombre", org.nombre)
                rapport["distribution"]["organes_hauts"].append(out_org)
            except Exception as e:
                _push_inconnue(rapport, "partielles", "organe allumage/injection", f"{e!r}")

        if (
            self.rpm is not None
            and Vd_unit is not None
            and self.nombre_cylindres is not None
            and len(rapport["distribution"]["admission"]) > 0
        ):
            try:
                debit_air_total = 0.0
                rho_air_ref = None
                for it in rapport["distribution"]["admission"]:
                    if it.get("debit_massique_kg_s") is not None:
                        debit_air_total += float(it["debit_massique_kg_s"])
                    if rho_air_ref is None:
                        src = next((x for x in (self.organes_admission or []) if x.nom == it["nom"]), None)
                        if src is not None and src.masse_volumique_gaz_kg_m3 is not None:
                            rho_air_ref = float(src.masse_volumique_gaz_kg_m3)

                if debit_air_total > 0.0 and rho_air_ref is not None:
                    eta_v = _eta_remplissage_depuis_debit(
                        debit_massique_air_kg_s=debit_air_total,
                        masse_volumique_air_kg_m3=rho_air_ref,
                        cylindree_totale_m3=float(Vd_unit) * float(self.nombre_cylindres),
                        rpm=_req_pos("rpm", self.rpm),
                        temps_moteur=int(self.temps_moteur),
                    )
                    rapport["distribution"]["rendement_remplissage"] = eta_v
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "rendement de remplissage",
                        "Calculable si un débit massique d'admission et une masse volumique de gaz sont fournis."
                    )
            except Exception as e:
                _push_inconnue(rapport, "partielles", "rendement de remplissage", f"{e!r}")

        # ------------------------------------------------------------
        # 8quinquies) Lubrification
        # ------------------------------------------------------------
        lub = self.lubrification_haute
        if lub is not None:
            lub_rep: Dict[str, Any] = {
                "debit_massique_huile_kg_s": lub.debit_massique_huile_kg_s,
                "masse_volumique_huile_kg_m3": lub.masse_volumique_huile_kg_m3,
                "viscosite_dynamique_pa_s": lub.viscosite_dynamique_pa_s,
                "temperature_huile_C": lub.temperature_huile_C,
                "nb_points_lubrifies": lub.nb_points_lubrifies,
                "debit_volumique_huile_m3_s": None,
                "section_galerie_m2": None,
                "vitesse_huile_m_s": None,
                "Re_galerie": None,
                "delta_p_poiseuille_pa": None,
                "pression_moyenne_contact_pa": None,
                "marge_film": None,
                "marge_pression_disponible": None,
            }

            try:
                if lub.debit_massique_huile_kg_s is not None and lub.masse_volumique_huile_kg_m3 is not None:
                    Q_h = _debit_volumique_depuis_massique(lub.debit_massique_huile_kg_s, lub.masse_volumique_huile_kg_m3)
                    lub_rep["debit_volumique_huile_m3_s"] = Q_h

                    if lub.diametre_galerie_m is not None:
                        A_gal = _section_circulaire(lub.diametre_galerie_m)
                        lub_rep["section_galerie_m2"] = A_gal
                        lub_rep["vitesse_huile_m_s"] = Q_h / A_gal if A_gal > 0 else None

                    if (
                        lub.viscosite_dynamique_pa_s is not None
                        and lub.diametre_galerie_m is not None
                        and lub.longueur_galerie_m is not None
                    ):
                        lub_rep["delta_p_poiseuille_pa"] = _poiseuille_tube_circulaire(
                            mu=lub.viscosite_dynamique_pa_s,
                            L=lub.longueur_galerie_m,
                            Q=Q_h,
                            D=lub.diametre_galerie_m,
                        )

                    if (
                        lub.masse_volumique_huile_kg_m3 is not None
                        and lub.viscosite_dynamique_pa_s is not None
                        and lub.diametre_galerie_m is not None
                        and lub_rep["vitesse_huile_m_s"] is not None
                    ):
                        lub_rep["Re_galerie"] = _reynolds(
                            rho=lub.masse_volumique_huile_kg_m3,
                            v=lub_rep["vitesse_huile_m_s"],
                            D=lub.diametre_galerie_m,
                            mu=lub.viscosite_dynamique_pa_s,
                        )

                if lub.charge_normale_n is not None and lub.aire_portante_m2 is not None:
                    lub_rep["pression_moyenne_contact_pa"] = _pression_contact_reelle(
                        force_n=lub.charge_normale_n,
                        aire_m2=lub.aire_portante_m2,
                    )

                if lub.epaisseur_film_estimee_m is not None and lub.epaisseur_film_min_requise_m is not None:
                    lub_rep["marge_film"] = _req_pos("epaisseur_film_estimee_m", lub.epaisseur_film_estimee_m, strictly=False) / _req_pos("epaisseur_film_min_requise_m", lub.epaisseur_film_min_requise_m)

                if (
                    lub.pression_amont_pa is not None
                    and lub.pression_aval_pa is not None
                    and lub_rep["delta_p_poiseuille_pa"] is not None
                ):
                    delta_p_dispo = _req_pos("pression_amont_pa", lub.pression_amont_pa, strictly=False) - _req_pos("pression_aval_pa", lub.pression_aval_pa, strictly=False)
                    delta_p_calc = _req_pos("delta_p_poiseuille_pa", lub_rep["delta_p_poiseuille_pa"], strictly=False)
                    if delta_p_calc > 0:
                        lub_rep["marge_pression_disponible"] = delta_p_dispo / delta_p_calc
            except Exception as e:
                _push_inconnue(rapport, "partielles", "lubrification", f"Impossible de résoudre une partie de la lubrification: {e!r}")

            rapport["lubrification"].update(lub_rep)
        else:
            _push_inconnue(rapport, "partielles", "lubrification", "Aucune donnée de lubrification fournie.")

        # ------------------------------------------------------------
        # 8sexies) Refroidissement haut
        # ------------------------------------------------------------
        refh = self.refroidissement_haut
        if refh is not None:
            ref_rep: Dict[str, Any] = {
                "puissance_thermique_w": refh.puissance_thermique_w,
                "temperature_fluide_entree_C": refh.temperature_fluide_entree_C,
                "temperature_ambiante_C": refh.temperature_ambiante_C,
                "R_conv_interne_K_W": None,
                "R_cond_piece_K_W": None,
                "R_joint_culasse_K_W": None,
                "R_conv_externe_K_W": None,
                "R_totale_K_W": None,
                "delta_T_piece_fluide_K": None,
                "temperature_piece_estimee_C": None,
                "temperature_piece_extreme_C": None,
            }

            try:
                R_i = None
                R_c = None
                R_j = None
                R_o = None

                if refh.h_interne_w_m2_k is not None and refh.surface_interne_m2 is not None:
                    R_i = _resistance_convection(refh.h_interne_w_m2_k, refh.surface_interne_m2)
                    ref_rep["R_conv_interne_K_W"] = R_i

                k_piece = refh.conductivite_piece_w_m_k if refh.conductivite_piece_w_m_k is not None else k_mat
                if refh.epaisseur_eq_m is not None and k_piece is not None and refh.surface_interne_m2 is not None:
                    R_c = _resistance_conduction_plane(refh.epaisseur_eq_m, k_piece, refh.surface_interne_m2)
                    ref_rep["R_cond_piece_K_W"] = R_c

                if joint_spec is not None and joint_spec.epaisseur_m is not None and joint_spec.conductivite_w_m_k is not None and aire_appui_joint is not None:
                    R_j = _resistance_conduction_plane(joint_spec.epaisseur_m, joint_spec.conductivite_w_m_k, aire_appui_joint)
                    ref_rep["R_joint_culasse_K_W"] = R_j

                if refh.h_externe_w_m2_k is not None and refh.surface_externe_m2 is not None:
                    R_o = _resistance_convection(refh.h_externe_w_m2_k, refh.surface_externe_m2)
                    ref_rep["R_conv_externe_K_W"] = R_o

                Rs = [x for x in (R_i, R_c, R_j, R_o) if x is not None]
                if len(Rs) > 0:
                    ref_rep["R_totale_K_W"] = sum(Rs)

                if refh.puissance_thermique_w is not None and ref_rep["R_totale_K_W"] is not None:
                    dT = _req_pos("puissance_thermique_w", refh.puissance_thermique_w, strictly=False) * ref_rep["R_totale_K_W"]
                    ref_rep["delta_T_piece_fluide_K"] = dT
                    if refh.temperature_fluide_entree_C is not None:
                        ref_rep["temperature_piece_estimee_C"] = refh.temperature_fluide_entree_C + dT
                    if refh.delta_temperature_extreme_k is not None and ref_rep["temperature_piece_estimee_C"] is not None:
                        ref_rep["temperature_piece_extreme_C"] = ref_rep["temperature_piece_estimee_C"] + refh.delta_temperature_extreme_k
            except Exception as e:
                _push_inconnue(rapport, "partielles", "refroidissement haut", f"Impossible de résoudre une partie du refroidissement: {e!r}")

            rapport["refroidissement_haut"].update(ref_rep)
        else:
            _push_inconnue(rapport, "partielles", "refroidissement haut", "Aucune donnée de refroidissement haut fournie.")

        # ------------------------------------------------------------
        # 8septies) Déformation thermique culasse
        # ------------------------------------------------------------
        if alpha is not None and culasse.epaisseur_culasse_m is not None and D_ouv_val is not None:
            try:
                if self.delta_temperature_k is not None:
                    rapport["deformations"]["delta_diametre_culasse_thermique_m"] = (
                        _req_pos("coefficient_dilatation_1_k", alpha, strictly=False) * D_ouv_val * _req_finite("delta_temperature_k", self.delta_temperature_k)
                    )

                if E is not None and nu is not None and culasse.gradient_thermique_travers_epaisseur_k is not None:
                    sigma_th = (
                        _req_pos("module_young_pa", E)
                        * _req_pos("coefficient_dilatation_1_k", alpha, strictly=False)
                        * _req_finite("gradient_thermique_travers_epaisseur_k", culasse.gradient_thermique_travers_epaisseur_k)
                        / (1.0 - _req_pos("coefficient_poisson", nu, strictly=False))
                    )
                    rapport["contraintes"]["sigma_thermique_culasse_bloquee_pa"] = sigma_th
            except Exception as e:
                _push_inconnue(rapport, "partielles", "déformation thermique culasse", f"{e!r}")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "déformation thermique culasse",
                "Calculable si alpha, epaisseur_culasse_m et/ou gradient thermique sont fournis."
            )

        # ------------------------------------------------------------
        # 9) Déformations thermiques globales
        # ------------------------------------------------------------
        if alpha is not None and self.delta_temperature_k is not None and D_ouv_val is not None:
            a2 = _req_pos("coefficient_dilatation_1_k", alpha)
            dT = _req_finite("delta_temperature_k", self.delta_temperature_k)
            rapport["deformations"]["delta_diametre_ouverture_thermique_m"] = a2 * D_ouv_val * dT
            if course_eff is not None:
                rapport["deformations"]["delta_longueur_thermique_m"] = a2 * course_eff * dT
        else:
            _push_inconnue(rapport, "partielles", "dilatation thermique", "Calculable si alpha, delta_temperature_k et la géométrie sont fournis.")

        # ------------------------------------------------------------
        # 10) Thermique global du couvercle
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
                "diametre_ouverture_m": D_ouv_val,
                "rayon_base_calotte_m": float(geo_cap["a_m"]),
                "hauteur_bombe_interieure_m": float(geo_cap["h_m"]),
                "rayon_courbure_interieur_m": R_int,
                "rayon_courbure_exterieur_m": R_ext,
                "epaisseur_calotte_m": e_calc,
                "diametre_exterieur_calotte_base_m": 2.0 * float(geo_cap["a_m"]),
                "bride": bride_geo,
                "assemblage": rapport["assemblage"],
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
                    "circularite_m": self.regles_forme.circularite_m,
                    "cylindricite_m": self.regles_forme.cylindricite_m,
                    "coaxialite_m": self.regles_forme.coaxialite_m,
                    "perpendicularite_faces_m": self.regles_forme.perpendicularite_faces_m,
                },
                "usinage": {
                    "surepaisseur_usinage_m": self.regles_forme.surepaisseur_usinage_m,
                    "surepaisseur_finition_m": self.regles_forme.surepaisseur_finition_m,
                },
            }
            rapport["geometrie"]["cao"] = cao
            rapport["fabrication"].update(cao["etat_surface"])
            rapport["fabrication"]["tolerances"] = cao["tolerances"]
            rapport["fabrication"]["usinage"] = cao["usinage"]

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

        if aire_appui_joint is not None and pression_contact_reelle is not None and joint_spec is not None and joint_spec.pression_contact_min_pa is not None:
            rapport["verifications"]["pression_contact_joint_suffisante"] = (
                pression_contact_reelle >= float(joint_spec.pression_contact_min_pa)
            )

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
