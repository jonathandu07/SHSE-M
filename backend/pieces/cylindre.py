# backend/pieces/cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
import math

# ============================================================
# Imports projet (avec fallbacks)
# ============================================================

# --- Cylindrée / épaisseurs ---
try:
    from backend.modules.moteur_thermique.calcul_cylindree import (
        calcul_cylindree_unitaire,
        calcul_epaisseur_cylindre_mince,
        calcul_epaisseur_cylindre_lame,
    )
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

    def calcul_epaisseur_cylindre_mince(
        *,
        pression_pa: float,
        rayon_interne_m: float,
        contrainte_admissible_pa: float,
        include_longitudinale: bool = False,
        facteur_securite: float = 1.0,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float:
        if rayon_interne_m <= 0 or contrainte_admissible_pa <= 0 or facteur_securite <= 0:
            raise ValueError("rayon_interne_m, contrainte_admissible_pa, facteur_securite doivent être > 0")
        p = abs(float(pression_pa))
        sigma_eff = contrainte_admissible_pa / facteur_securite
        if sigma_eff <= 0:
            raise ValueError("Contrainte admissible effective <= 0")
        t_hoop = (p * rayon_interne_m) / sigma_eff
        t_long = (p * rayon_interne_m) / (2.0 * sigma_eff)
        t = max(t_hoop, t_long) if include_longitudinale else t_hoop
        return max(0.0, t) if clamp_non_negative else t

    def calcul_epaisseur_cylindre_lame(
        *,
        pression_interne_pa: float,
        rayon_interne_m: float,
        contrainte_admissible_pa: float,
        facteur_securite: float = 1.0,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float:
        ri = float(rayon_interne_m)
        if ri <= 0 or contrainte_admissible_pa <= 0 or facteur_securite <= 0:
            raise ValueError("rayon_interne_m, contrainte_admissible_pa, facteur_securite doivent être > 0")
        p = abs(float(pression_interne_pa))
        sigma_eff = contrainte_admissible_pa / facteur_securite
        if sigma_eff <= p:
            raise ValueError("sigma_eff doit être > pression_interne_pa pour Lamé.")
        ro2 = ((sigma_eff + p) / (sigma_eff - p)) * (ri ** 2)
        ro = math.sqrt(ro2)
        t = ro - ri
        return max(0.0, t) if clamp_non_negative else t


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


# --- Matériaux ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


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


def _von_mises_3d(s1: float, s2: float, s3: float) -> float:
    return math.sqrt(0.5 * ((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2))


def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


def _arrondi_multiple_sup(x: float, pas: float) -> float:
    p = _req_pos("pas", pas)
    return math.ceil(float(x) / p) * p


# ============================================================
# Convection interne/externe (optionnelle) : calcul h
# ============================================================

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

    modele_utilise: str

    if modele == "auto":
        if Re < 2300.0:
            Nu = _nu_laminaire_tube(condition_paroi=condition_paroi)
            modele_utilise = f"laminaire({condition_paroi})"
        else:
            if Re >= 3000.0:
                f = _f_darcy_blasius(Re)
                Nu = _nu_gnielinski(Re, Pr, f)
                modele_utilise = "gnielinski+blasius"
            else:
                Nu = _nu_dittus_boelter(Re, Pr, chauffage_fluide=chauffage_fluide)
                modele_utilise = "dittus_boelter"
    elif modele == "laminaire":
        Nu = _nu_laminaire_tube(condition_paroi=condition_paroi)
        modele_utilise = f"laminaire({condition_paroi})"
    elif modele == "dittus_boelter":
        Nu = _nu_dittus_boelter(Re, Pr, chauffage_fluide=chauffage_fluide)
        modele_utilise = "dittus_boelter"
    elif modele == "gnielinski":
        if Re <= 1000.0:
            raise ValueError("Gnielinski nécessite Re > 1000.")
        f = _f_darcy_blasius(Re)
        Nu = _nu_gnielinski(Re, Pr, f)
        modele_utilise = "gnielinski+blasius"
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
        "modele_txt": modele_utilise,
    }


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


def _etat_fluide_pour_convection(ent: EntreeConvectionTube) -> Dict[str, float]:
    if ent.fluide == "air":
        if air_state is None:
            raise RuntimeError("backend.ensemble.air.air_state indisponible.")
        if isa_dry_temperature_pressure is None:
            raise RuntimeError("backend.ensemble.air.isa_dry_temperature_pressure indisponible.")

        altitude = float(ent.altitude_m)
        T_isa, p_isa = isa_dry_temperature_pressure(altitude_m=altitude)
        T_ent = float(ent.T_K)
        temperature_offset_K = T_ent - float(T_isa)

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
            "T_K_entree": T_ent,
            "p_Pa_entree": float(ent.p_Pa),
            "p_Pa_ISA": float(p_isa),
            "temperature_offset_K": float(temperature_offset_K),
        }

    if ent.fluide == "eau_pure":
        if etat_eau_pure is None:
            raise RuntimeError("backend.ensemble.eau.etat_eau_pure indisponible.")
        st = etat_eau_pure(float(ent.T_K), float(ent.p_Pa))
        return {
            "rho": float(st.rho_kg_m3),
            "cp": float(st.cp_J_kg_K),
            "mu": float(st.mu_Pa_s),
            "k": float(st.k_W_m_K),
            "T_K": float(ent.T_K),
            "p_Pa": float(ent.p_Pa),
        }

    if ent.fluide == "eau_salee":
        if etat_eau_salee is None:
            raise RuntimeError("backend.ensemble.eau.etat_eau_salee indisponible.")
        st = etat_eau_salee(float(ent.T_K), float(ent.p_Pa), float(ent.salinite_g_kg))
        return {
            "rho": float(st.rho_kg_m3),
            "cp": float(st.cp_J_kg_K),
            "mu": float(st.mu_Pa_s),
            "k": float(st.k_W_m_K),
            "T_K": float(ent.T_K),
            "p_Pa": float(ent.p_Pa),
        }

    if ent.fluide == "antigel":
        if etat_antigel is None:
            raise RuntimeError("backend.ensemble.eau.etat_antigel indisponible.")
        st = etat_antigel(
            float(ent.T_K),
            float(ent.p_Pa),
            float(ent.fraction_massique_glycol),
            type_glycol=str(ent.type_glycol),
        )
        return {
            "rho": float(st.rho_kg_m3),
            "cp": float(st.cp_J_kg_K),
            "mu": float(st.mu_Pa_s),
            "k": float(st.k_W_m_K),
            "T_K": float(ent.T_K),
            "p_Pa": float(ent.p_Pa),
        }

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
    if "T_K" in props:
        res["T_K_utilise"] = float(props["T_K"])
    if "p_Pa" in props:
        res["p_Pa_utilise"] = float(props["p_Pa"])
    if "p_Pa_entree" in props:
        res["p_Pa_entree"] = float(props["p_Pa_entree"])
    return res


# ============================================================
# Matériau : extraction (réduit les inconnues)
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

    Re_candidates: list[float] = []
    base_Re = mat.limite_elastique_effective_pa(mode="min", section_mm=None)
    if base_Re is not None:
        Re_candidates.append(float(base_Re))
    if getattr(mat, "resistance_par_section", None):
        for seg in mat.resistance_par_section:
            if getattr(seg, "rp02_pa_min", None) is not None:
                Re_candidates.append(float(seg.rp02_pa_min))
    Re_min = min(Re_candidates) if Re_candidates else None

    sigma_f = valeur(getattr(mat, "limite_fatigue_pa", None), mode="min")

    return {
        "densite_kg_m3": rho,
        "module_young_pa": E,
        "poisson": nu,
        "conductivite_w_m_k": k,
        "alpha_dilatation_1_k": alpha,
        "limite_elastique_min_pa": Re_min,
        "limite_fatigue_min_pa": sigma_f,
        "T_service_min_C": getattr(mat, "temperature_service_min_c", None),
        "T_service_max_C": getattr(mat, "temperature_service_max_c", None),
        "materiau_nom": getattr(mat, "nom", materiau_cle),
        "famille": getattr(mat, "famille", None),
    }


# ============================================================
# Filetages ISO métriques
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
        raise ValueError(f"classe_iso invalide (valeurs <=0): {classe_iso!r}")
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
        if abs(float(d) - float(d_mm)) < 1e-12:
            return float(p)
    return None


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
    raise ValueError("Aucun filetage trouvé pour As_requise_m2.")


# ============================================================
# Règles de conception CAO / fabrication / fermeture
# ============================================================

TypeFermetureCylindre = Literal["brides_2_couvercles"]


@dataclass(frozen=True)
class ReglesJointTorique:
    """
    Joint torique statique axial.
    - profondeur gorge = d_tore * (1 - taux_ecrasement_cible)
    - largeur gorge = coefficient_largeur_gorge * d_tore
    """
    diametre_tore_m: float
    taux_ecrasement_cible: float = 0.20
    coefficient_largeur_gorge: float = 1.15
    coefficient_force_contact_lineique_n_m: float = 12000.0
    position_axiale: Literal["avant", "arriere", "double"] = "double"


@dataclass(frozen=True)
class ReglesVisserieBride:
    """
    Données permettant de dimensionner les vis depuis la force de séparation.
    - soit classe_vis_iso898 + facteur_utilisation_precharge
    - soit contrainte_admissible_vis_pa
    """
    facteur_securite_etancheite: float = 1.5
    facteur_utilisation_precharge: float = 0.70
    classe_vis_iso898: str = "8.8"
    contrainte_admissible_vis_pa: Optional[float] = None
    d_max_vis_mm: Optional[float] = None
    diametre_nominal_vis_m: Optional[float] = None
    facteur_frottement_k: float = 0.20
    coefficient_marge_cercle_percage: float = 0.70
    largeur_matiere_radiale_min_m: float = 0.005
    jeu_diametral_trou_sur_vis_m: float = 0.001
    serie_filetage: FiletageSerie = "iso_metric_coarse"
    nombre_vis_pair_obligatoire: bool = True


@dataclass(frozen=True)
class ReglesFabricationCylindre:
    type_fermeture: TypeFermetureCylindre = "brides_2_couvercles"

    epaisseur_min_fabrication_m: float = 0.003
    surcote_usinage_interieur_m: float = 0.0002
    surcote_usinage_exterieur_m: float = 0.0003

    ratio_epaisseur_bride_sur_paroi: float = 1.50
    ratio_largeur_bride_sur_paroi: float = 3.00
    epaisseur_bride_min_m: float = 0.006
    largeur_bride_min_m: float = 0.010

    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.003
    ratio_chanfrein_sur_epaisseur: float = 0.35
    chanfrein_entree_piston_mult_sur_jeu: float = 6.0

    conge_min_m: float = 0.0005
    conge_max_m: float = 0.004
    ratio_conge_sur_epaisseur: float = 0.25

    jeu_piston_cylindre_min_m: float = 0.00004
    ratio_jeu_sur_diametre: float = 0.0005

    rugosite_alesage_ra_um: float = 0.8
    rugosite_face_joint_ra_um: float = 1.6
    rugosite_exterieure_ra_um: float = 3.2
    rugosite_gorge_ra_um: float = 1.6

    tolerance_alesage_m: float = 0.00003
    tolerance_exterieure_m: float = 0.00010
    tolerance_longueur_m: float = 0.00010
    tolerance_gorge_m: float = 0.00005
    tolerance_position_trous_m: float = 0.00010

    longueur_utile_suppl_montage_avant_m: float = 0.0
    longueur_utile_suppl_montage_arriere_m: float = 0.0


# ============================================================
# Calculs fermeture / joint / CAO
# ============================================================

def _resoudre_contrainte_vis_admissible_pa(regles_vis: ReglesVisserieBride) -> float:
    if regles_vis.contrainte_admissible_vis_pa is not None:
        return _req_pos("contrainte_admissible_vis_pa", regles_vis.contrainte_admissible_vis_pa)
    Re_vis = _iso898_yield_strength_pa_from_class(regles_vis.classe_vis_iso898)
    fu = _req_pos("facteur_utilisation_precharge", regles_vis.facteur_utilisation_precharge)
    return Re_vis * fu


def _force_joint_torique(
    *,
    diametre_joint_m: float,
    regles_joint: ReglesJointTorique,
) -> float:
    Dj = _req_pos("diametre_joint_m", diametre_joint_m)
    dt = _req_pos("diametre_tore_m", regles_joint.diametre_tore_m)
    if not (0.0 < regles_joint.taux_ecrasement_cible < 0.5):
        raise ValueError("taux_ecrasement_cible doit être dans ]0, 0.5[.")
    perimetre = math.pi * Dj
    force_lineique = _req_pos(
        "coefficient_force_contact_lineique_n_m",
        regles_joint.coefficient_force_contact_lineique_n_m,
        strictly=False,
    )
    # facteur simple lié au tore et à l'écrasement, sans norme cachée
    return perimetre * force_lineique * (dt / 0.003) * (regles_joint.taux_ecrasement_cible / 0.20)


def _calcul_gorge_joint_torique(
    *,
    diametre_interieur_cylindre_m: float,
    epaisseur_paroi_m: float,
    largeur_bride_m: float,
    regles_joint: ReglesJointTorique,
    jeu_piston_cylindre_m: float,
) -> Dict[str, Any]:
    Di = _req_pos("diametre_interieur_cylindre_m", diametre_interieur_cylindre_m)
    e = _req_pos("epaisseur_paroi_m", epaisseur_paroi_m)
    wb = _req_pos("largeur_bride_m", largeur_bride_m)
    dt = _req_pos("diametre_tore_m", regles_joint.diametre_tore_m)
    eps = _req_pos("taux_ecrasement_cible", regles_joint.taux_ecrasement_cible)

    profondeur = dt * (1.0 - eps)
    largeur = _req_pos("coefficient_largeur_gorge", regles_joint.coefficient_largeur_gorge) * dt

    if profondeur >= e:
        raise ValueError("La profondeur de gorge dépasse l'épaisseur disponible.")
    if largeur > wb:
        raise ValueError("La largeur de gorge dépasse la largeur de bride disponible.")

    # Position radiale choisie pour laisser de la matière côté intérieur et extérieur.
    marge_interne = max(1.5 * jeu_piston_cylindre_m, 0.25 * dt)
    rayon_fond_int = 0.5 * Di + marge_interne
    rayon_fond_ext = rayon_fond_int + largeur
    diametre_moyen_joint = rayon_fond_int * 2.0 + largeur

    return {
        "type_joint": "torique_statique_axial",
        "diametre_tore_m": dt,
        "taux_ecrasement_cible": eps,
        "profondeur_gorge_m": profondeur,
        "largeur_gorge_m": largeur,
        "rayon_fond_gorge_interne_m": rayon_fond_int,
        "rayon_fond_gorge_externe_m": rayon_fond_ext,
        "diametre_moyen_joint_m": diametre_moyen_joint,
        "marge_interne_gorge_m": marge_interne,
        "position_axiale": regles_joint.position_axiale,
    }


def _normaliser_nombre_vis(nb: int, obliger_pair: bool) -> int:
    n = max(3, int(nb))
    if obliger_pair and (n % 2 != 0):
        n += 1
    return n


def _choisir_visserie_depuis_precharge(
    *,
    F_pre_totale_N: float,
    regles_vis: ReglesVisserieBride,
) -> Dict[str, Any]:
    Ftot = _req_pos("F_pre_totale_N", F_pre_totale_N, strictly=False)
    sigma_vis_adm = _resoudre_contrainte_vis_admissible_pa(regles_vis)

    if regles_vis.diametre_nominal_vis_m is not None:
        d_nom_m = _req_pos("diametre_nominal_vis_m", regles_vis.diametre_nominal_vis_m)
        d_nom_mm = d_nom_m * 1000.0
        pas = _pas_coarse_pour_diametre_mm(d_nom_mm)
        if pas is None:
            raise ValueError("Pas ISO coarse introuvable pour le diamètre vis imposé.")
        As_mm2 = _tensile_stress_area_iso898_mm2(d_nom_mm, pas)
        As_m2 = As_mm2 * 1e-6
        F_pre_max_par_vis = sigma_vis_adm * As_m2
        if F_pre_max_par_vis <= 0:
            raise ValueError("Précharge max par vis <= 0.")
        nb = _normaliser_nombre_vis(
            int(math.ceil(Ftot / F_pre_max_par_vis)) if Ftot > 0 else 4,
            regles_vis.nombre_vis_pair_obligatoire,
        )
        choix = {
            "serie": regles_vis.serie_filetage,
            "d_nominal_mm": float(d_nom_mm),
            "pas_mm": float(pas),
            "taraudage": f"M{d_nom_mm:g}x{pas:g}",
            "As_mm2": float(As_mm2),
            "As_m2": float(As_m2),
            "D1_taraudage_mm": float(_internal_thread_minor_diameter_mm(d_nom_mm, pas)),
        }
    else:
        # Choix combiné vis + nb mini à partir d'une précharge par vis raisonnable
        meilleur: Optional[Dict[str, Any]] = None
        for d_mm, p_mm in _METRIC_COARSE_SERIE_MM:
            if regles_vis.d_max_vis_mm is not None and d_mm > float(regles_vis.d_max_vis_mm):
                continue
            As_mm2 = _tensile_stress_area_iso898_mm2(d_mm, p_mm)
            As_m2 = As_mm2 * 1e-6
            F_pre_max_par_vis = sigma_vis_adm * As_m2
            if F_pre_max_par_vis <= 0:
                continue
            nb_try = _normaliser_nombre_vis(
                int(math.ceil(Ftot / F_pre_max_par_vis)) if Ftot > 0 else 4,
                regles_vis.nombre_vis_pair_obligatoire,
            )
            score = nb_try * 1000.0 + d_mm  # privilégie peu de vis, puis petit diamètre
            cand = {
                "serie": regles_vis.serie_filetage,
                "d_nominal_mm": float(d_mm),
                "pas_mm": float(p_mm),
                "taraudage": f"M{d_mm:g}x{p_mm:g}",
                "As_mm2": float(As_mm2),
                "As_m2": float(As_m2),
                "D1_taraudage_mm": float(_internal_thread_minor_diameter_mm(d_mm, p_mm)),
                "nb_vis": int(nb_try),
                "F_pre_max_par_vis_N": float(F_pre_max_par_vis),
                "score": float(score),
            }
            if meilleur is None or cand["score"] < meilleur["score"]:
                meilleur = cand

        if meilleur is None:
            raise ValueError("Impossible de choisir une visserie.")
        choix = meilleur
        nb = int(choix["nb_vis"])

    F_pre_par_vis = (Ftot / nb) if nb > 0 else 0.0
    couple_serrage = calcul_couple_serrage(
        force_precharge_vis_n=F_pre_par_vis,
        diametre_nominal_m=(float(choix["d_nominal_mm"]) / 1000.0),
        facteur_frottement_k=float(regles_vis.facteur_frottement_k),
    )

    choix["nb_vis"] = int(nb)
    choix["force_precharge_par_vis_N"] = float(F_pre_par_vis)
    choix["force_precharge_totale_N"] = float(Ftot)
    choix["contrainte_admissible_vis_pa"] = float(sigma_vis_adm)
    choix["couple_serrage_par_vis_Nm"] = float(couple_serrage)
    return choix


def _calcul_bride_percages(
    *,
    diametre_exterieur_cylindre_m: float,
    epaisseur_paroi_m: float,
    largeur_bride_m: float,
    epaisseur_bride_m: float,
    visserie: Dict[str, Any],
    regles_vis: ReglesVisserieBride,
) -> Dict[str, Any]:
    De = _req_pos("diametre_exterieur_cylindre_m", diametre_exterieur_cylindre_m)
    e = _req_pos("epaisseur_paroi_m", epaisseur_paroi_m)
    wb = _req_pos("largeur_bride_m", largeur_bride_m)
    eb = _req_pos("epaisseur_bride_m", epaisseur_bride_m)

    d_vis_m = float(visserie["d_nominal_mm"]) / 1000.0
    nb = _req_int_pos("nb_vis", visserie["nb_vis"])
    jeu = _req_pos("jeu_diametral_trou_sur_vis_m", regles_vis.jeu_diametral_trou_sur_vis_m, strictly=False)
    d_trou = d_vis_m + jeu

    rayon_cylindre_ext = 0.5 * De
    rayon_bride_ext = rayon_cylindre_ext + wb

    marge_radiale = max(
        _req_pos("largeur_matiere_radiale_min_m", regles_vis.largeur_matiere_radiale_min_m, strictly=False),
        0.6 * d_trou,
    )

    r_min_centres = rayon_cylindre_ext + marge_radiale + 0.5 * d_trou
    r_max_centres = rayon_bride_ext - marge_radiale - 0.5 * d_trou

    if r_max_centres <= r_min_centres:
        raise ValueError("Bride trop étroite pour loger les perçages avec la marge matière imposée.")

    r_centres = 0.5 * (r_min_centres + r_max_centres)
    DPC = 2.0 * r_centres

    # Vérification d'espacement tangentiel
    pas_circulaire = math.pi * DPC / nb
    if pas_circulaire < (d_trou + 2.0 * marge_radiale):
        raise ValueError("Périmètre insuffisant pour répartir équidistamment les perçages retenus.")

    angles_deg = [i * (360.0 / nb) for i in range(nb)]

    return {
        "diametre_trou_m": d_trou,
        "rayon_cercle_percage_m": r_centres,
        "diametre_cercle_percage_m": DPC,
        "nb_trous": nb,
        "angles_deg": angles_deg,
        "pas_circulaire_m": pas_circulaire,
        "rayon_bride_externe_m": rayon_bride_ext,
        "diametre_bride_externe_m": 2.0 * rayon_bride_ext,
        "epaisseur_bride_m": eb,
        "largeur_bride_m": wb,
    }


def _calcul_etat_surface_et_tolerances(
    *,
    regles_fab: ReglesFabricationCylindre,
) -> Dict[str, Any]:
    return {
        "etat_surface": {
            "alesage_ra_um": float(regles_fab.rugosite_alesage_ra_um),
            "face_joint_ra_um": float(regles_fab.rugosite_face_joint_ra_um),
            "gorge_joint_ra_um": float(regles_fab.rugosite_gorge_ra_um),
            "exterieur_ra_um": float(regles_fab.rugosite_exterieure_ra_um),
        },
        "tolerances": {
            "alesage_m": float(regles_fab.tolerance_alesage_m),
            "diametre_exterieur_m": float(regles_fab.tolerance_exterieure_m),
            "longueur_m": float(regles_fab.tolerance_longueur_m),
            "gorge_m": float(regles_fab.tolerance_gorge_m),
            "position_trous_m": float(regles_fab.tolerance_position_trous_m),
        },
    }


def _calcul_cao_cylindre_ferme(
    *,
    alesage_m: float,
    longueur_utile_m: float,
    epaisseur_retenue_m: float,
    pression_max_pa: float,
    pression_externe_pa: float,
    regles_fab: ReglesFabricationCylindre,
    regles_joint: ReglesJointTorique,
    regles_vis: ReglesVisserieBride,
) -> Dict[str, Any]:
    Di = _req_pos("alesage_m", alesage_m)
    L = _req_pos("longueur_utile_m", longueur_utile_m)
    t_calc = _req_pos("epaisseur_retenue_m", epaisseur_retenue_m)
    pmax = _req_pos("pression_max_pa", pression_max_pa, strictly=False)
    pext = _req_pos("pression_externe_pa", pression_externe_pa, strictly=False)

    t_nom = max(t_calc, _req_pos("epaisseur_min_fabrication_m", regles_fab.epaisseur_min_fabrication_m, strictly=False))
    ri = 0.5 * Di
    ro = ri + t_nom
    De = 2.0 * ro

    jeu = max(
        _req_pos("jeu_piston_cylindre_min_m", regles_fab.jeu_piston_cylindre_min_m, strictly=False),
        _req_pos("ratio_jeu_sur_diametre", regles_fab.ratio_jeu_sur_diametre) * Di,
    )

    chanfrein_econo = _borne(
        regles_fab.ratio_chanfrein_sur_epaisseur * t_nom,
        regles_fab.chanfrein_min_m,
        regles_fab.chanfrein_max_m,
    )
    chanfrein_entree_piston = _borne(
        regles_fab.chanfrein_entree_piston_mult_sur_jeu * jeu,
        chanfrein_econo,
        regles_fab.chanfrein_max_m,
    )

    conge = _borne(
        regles_fab.ratio_conge_sur_epaisseur * t_nom,
        regles_fab.conge_min_m,
        regles_fab.conge_max_m,
    )

    eb = max(
        regles_fab.epaisseur_bride_min_m,
        regles_fab.ratio_epaisseur_bride_sur_paroi * t_nom,
    )
    wb = max(
        regles_fab.largeur_bride_min_m,
        regles_fab.ratio_largeur_bride_sur_paroi * t_nom,
    )

    gorge = _calcul_gorge_joint_torique(
        diametre_interieur_cylindre_m=Di,
        epaisseur_paroi_m=t_nom,
        largeur_bride_m=wb,
        regles_joint=regles_joint,
        jeu_piston_cylindre_m=jeu,
    )

    A_eff = math.pi * (0.5 * gorge["diametre_moyen_joint_m"]) ** 2
    F_sep = calcul_force_separation(max(0.0, pmax - pext), A_eff)
    F_joint = _force_joint_torique(
        diametre_joint_m=gorge["diametre_moyen_joint_m"],
        regles_joint=regles_joint,
    )
    F_pre_tot = calcul_precharge_vis_totale(
        force_separation_n=F_sep,
        force_joint_n=F_joint,
        facteur_securite=float(regles_vis.facteur_securite_etancheite),
    )

    visserie = _choisir_visserie_depuis_precharge(
        F_pre_totale_N=F_pre_tot,
        regles_vis=regles_vis,
    )

    bride = _calcul_bride_percages(
        diametre_exterieur_cylindre_m=De,
        epaisseur_paroi_m=t_nom,
        largeur_bride_m=wb,
        epaisseur_bride_m=eb,
        visserie=visserie,
        regles_vis=regles_vis,
    )

    L_tot = (
        L
        + 2.0 * eb
        + float(regles_fab.longueur_utile_suppl_montage_avant_m)
        + float(regles_fab.longueur_utile_suppl_montage_arriere_m)
    )

    fabrication = _calcul_etat_surface_et_tolerances(regles_fab=regles_fab)

    return {
        "type_fermeture": regles_fab.type_fermeture,
        "diametre_interieur_nominal_m": Di,
        "diametre_exterieur_nominal_m": De,
        "epaisseur_nominale_m": t_nom,
        "longueur_utile_nominale_m": L,
        "longueur_totale_nominale_m": L_tot,
        "rayon_interieur_nominal_m": ri,
        "rayon_exterieur_nominal_m": ro,
        "jeu_piston_cylindre_m": jeu,
        "chanfrein_entree_piston_m": chanfrein_entree_piston,
        "chanfrein_exterieur_m": chanfrein_econo,
        "rayon_conge_m": conge,
        "surcote_usinage_interieur_m": float(regles_fab.surcote_usinage_interieur_m),
        "surcote_usinage_exterieur_m": float(regles_fab.surcote_usinage_exterieur_m),
        "gorge_joint": gorge,
        "aire_effective_fermeture_m2": A_eff,
        "force_separation_N": F_sep,
        "force_joint_N": F_joint,
        "force_precharge_totale_requise_N": F_pre_tot,
        "visserie": visserie,
        "bride": bride,
        **fabrication,
    }


# ============================================================
# Pièce : Cylindre
# ============================================================

@dataclass(frozen=True)
class Cylindre:
    """
    Objectif :
    - dimensionnement mécanique sous pression,
    - estimation thermique / masse / inerties,
    - génération d'une géométrie CAO nominale exploitable,
    - fermeture par brides + joint torique + vis dimensionnées depuis la pression.

    Rien n'est “inventé” :
    - la physique vient des entrées et modules,
    - la géométrie manquante est déduite de règles explicites de conception.
    """

    # --- Géométrie (obligatoire) ---
    alesage_m: float
    course_m: float
    longueur_utile_m: float

    # --- Pressions ---
    pression_service_pa: float
    pression_max_pa: float
    pression_externe_pa: float = 0.0

    # --- Matériau ---
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

    # Convection (optionnel)
    convection_interne: Optional[EntreeConvectionTube] = None
    convection_externe: Optional[EntreeConvectionTube] = None
    h_interne_w_m2_k: Optional[float] = None
    h_externe_w_m2_k: Optional[float] = None

    # Overrides bride manuels (si fournis)
    epaisseur_bride_m: Optional[float] = None
    largeur_bride_m: Optional[float] = None

    # Règles explicites de conception
    regles_joint_torique: Optional[ReglesJointTorique] = None
    regles_visserie: Optional[ReglesVisserieBride] = None
    regles_fabrication: Optional[ReglesFabricationCylindre] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "geometrie": {},
            "dimensionnement": {},
            "contraintes": {},
            "deformations": {},
            "thermique": {},
            "masse": {},
            "inerties": {},
            "assemblage": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # 1) Validation
        # ------------------------------------------------------------
        D = _req_pos("alesage_m", self.alesage_m)
        S = _req_pos("course_m", self.course_m)
        L = _req_pos("longueur_utile_m", self.longueur_utile_m)
        p_serv = _req_pos("pression_service_pa", self.pression_service_pa, strictly=False)
        p_max = _req_pos("pression_max_pa", self.pression_max_pa, strictly=False)
        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        FS = _req_pos("facteur_securite", self.facteur_securite)

        rapport["entrees"].update({
            "alesage_m": D,
            "course_m": S,
            "longueur_utile_m": L,
            "pression_service_pa": p_serv,
            "pression_max_pa": p_max,
            "pression_externe_pa": p_ext,
            "facteur_securite": FS,
            "materiau_cle": self.materiau_cle,
            "mode_materiau": self.mode_materiau,
            "temperature_service_C": self.temperature_service_C,
        })

        if p_max < p_serv:
            rapport["notes_modele"].append("pression_max_pa < pression_service_pa : le dimensionnement reste fait sur pression_max_pa.")

        ri = 0.5 * D
        Ai = math.pi * (ri ** 2)

        # ------------------------------------------------------------
        # 2) Matériau
        # ------------------------------------------------------------
        matp: Dict[str, Any] = {}
        if self.materiau_cle:
            try:
                matp = _materiau_resoudre(materiau_cle=self.materiau_cle, mode=self.mode_materiau)
                rapport["materiau"].update(matp)

                if self.temperature_service_C is not None:
                    tmin = matp.get("T_service_min_C")
                    tmax = matp.get("T_service_max_C")
                    if tmin is not None and self.temperature_service_C < float(tmin):
                        rapport["notes_modele"].append(
                            f"Température service {self.temperature_service_C}°C < Tmin matériau ({tmin}°C)."
                        )
                    if tmax is not None and self.temperature_service_C > float(tmax):
                        rapport["notes_modele"].append(
                            f"Température service {self.temperature_service_C}°C > Tmax matériau ({tmax}°C)."
                        )
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
                "Impossible de dimensionner l’épaisseur sans contrainte_admissible_pa, limite_elastique_pa ou materiau_cle exploitable.",
            )

        # ------------------------------------------------------------
        # 3) Géométrie dérivée
        # ------------------------------------------------------------
        V_swept = float(calcul_cylindree_unitaire(
            alesage_m=D,
            course_m=S,
            allow_zero=False,
            return_details=False,
        ))
        surface_interne_laterale = math.pi * D * L
        volume_interne_total = Ai * L

        rapport["geometrie"].update({
            "rayon_interne_m": ri,
            "aire_section_interne_m2": Ai,
            "cylindree_unitaire_m3": V_swept,
            "volume_interne_total_m3": volume_interne_total,
            "surface_interne_laterale_m2": surface_interne_laterale,
        })

        # ------------------------------------------------------------
        # 4) Efforts pression
        # ------------------------------------------------------------
        F_piston_service = (p_serv - p_ext) * Ai
        F_piston_max = (p_max - p_ext) * Ai

        rapport["dimensionnement"].update({
            "force_pression_piston_service_N": F_piston_service,
            "force_pression_piston_max_N": F_piston_max,
        })

        # ------------------------------------------------------------
        # 5) Épaisseur virole
        # ------------------------------------------------------------
        t_mince: Optional[float] = None
        t_lame: Optional[float] = None
        t_retenue: Optional[float] = None

        p_i = p_max
        p_o = p_ext
        delta_p = max(0.0, p_i - p_o)

        if p_o > p_i:
            _push_inconnue(
                rapport,
                "impossibles",
                "pression externe",
                "p_o > p_i : collapse/flambage sous pression externe non traité.",
            )

        if delta_p == 0.0 and p_i == p_o:
            rapport["notes_modele"].append("delta_p=0 : aucun effort net de pression interne.")

        if sigma_adm is not None:
            t_mince = float(calcul_epaisseur_cylindre_mince(
                pression_pa=delta_p,
                rayon_interne_m=ri,
                contrainte_admissible_pa=sigma_adm,
                include_longitudinale=False,
                facteur_securite=FS,
                clamp_non_negative=True,
                return_details=False,
            ))

            sigma_eff = sigma_adm / FS
            denom = (sigma_eff - p_i + 2.0 * p_o)
            if denom <= 0:
                _push_inconnue(rapport, "impossibles", "épaisseur Lamé", "Pas de solution (sigma_eff - p_i + 2*p_o <= 0).")
            else:
                ro2 = (ri * ri) * (sigma_eff + p_i) / denom
                t_lame = max(0.0, math.sqrt(ro2) - ri)

            candidates = [x for x in (t_mince, t_lame) if isinstance(x, (int, float)) and math.isfinite(float(x))]
            if candidates:
                t_retenue = float(max(candidates))
            else:
                _push_inconnue(rapport, "impossibles", "épaisseur cylindre", "Aucun modèle calculable.")
        else:
            _push_inconnue(rapport, "impossibles", "épaisseur cylindre", "Pas de sigma_adm -> pas de dimensionnement pression.")

        rapport["dimensionnement"].update({
            "p_i_dimensionnement_pa": p_i,
            "p_o_dimensionnement_pa": p_o,
            "delta_p_dimensionnement_pa": delta_p,
            "epaisseur_mince_m": t_mince,
            "epaisseur_lame_m": t_lame,
            "epaisseur_retenue_m": t_retenue,
        })

        # ------------------------------------------------------------
        # 6) Contraintes
        # ------------------------------------------------------------
        if t_retenue is not None and t_retenue > 0:
            ro = ri + t_retenue
            Do = 2.0 * ro
            Di = 2.0 * ri

            sigma_theta_mince = (delta_p * ri) / t_retenue
            sigma_long_mince = (delta_p * ri) / (2.0 * t_retenue)
            sigma_vm_mince = math.sqrt(
                sigma_theta_mince ** 2
                + sigma_long_mince ** 2
                - sigma_theta_mince * sigma_long_mince
            )

            ri2 = ri * ri
            ro2 = ro * ro
            denom2 = (ro2 - ri2)
            if denom2 <= 0:
                _push_inconnue(rapport, "impossibles", "contraintes Lamé", "ro^2 - ri^2 <= 0.")
                sigma_theta_lame_i = sigma_r_lame_i = sigma_z_lame = sigma_vm_lame_i = None
            else:
                A = (p_i * ri2 - p_o * ro2) / denom2
                B = (ri2 * ro2 * (p_i - p_o)) / denom2
                sigma_r_lame_i = A - (B / ri2)
                sigma_theta_lame_i = A + (B / ri2)
                sigma_z_lame = A
                sigma_vm_lame_i = _von_mises_3d(sigma_theta_lame_i, sigma_r_lame_i, sigma_z_lame)

            marge_theta_mince = marge_theta_lame = None
            marge_vm_mince = marge_vm_lame = None

            if sigma_adm is not None:
                sigma_eff = sigma_adm / FS
                if sigma_eff > 0:
                    marge_theta_mince = sigma_eff / sigma_theta_mince if sigma_theta_mince != 0 else None
                    if sigma_theta_lame_i is not None and sigma_theta_lame_i != 0:
                        marge_theta_lame = sigma_eff / sigma_theta_lame_i
                    marge_vm_mince = sigma_eff / sigma_vm_mince if sigma_vm_mince != 0 else None
                    if sigma_vm_lame_i is not None and sigma_vm_lame_i != 0:
                        marge_vm_lame = sigma_eff / sigma_vm_lame_i

            ratio_t_sur_ri = t_retenue / ri
            paroi_mince_ok = ratio_t_sur_ri <= 0.10

            rapport["geometrie"].update({
                "rayon_externe_m": ro,
                "diametre_externe_m": Do,
                "diametre_interne_m": Di,
                "ratio_t_sur_ri": ratio_t_sur_ri,
            })

            rapport["contraintes"].update({
                "sigma_cerclage_mince_pa": sigma_theta_mince,
                "sigma_longitudinale_mince_pa": sigma_long_mince,
                "sigma_von_mises_mince_pa": sigma_vm_mince,
                "sigma_cerclage_lame_au_ri_pa": sigma_theta_lame_i,
                "sigma_radiale_lame_au_ri_pa": sigma_r_lame_i,
                "sigma_axiale_lame_pa": sigma_z_lame,
                "sigma_von_mises_lame_au_ri_pa": sigma_vm_lame_i,
                "marge_cerclage_mince": marge_theta_mince,
                "marge_cerclage_lame": marge_theta_lame,
                "marge_von_mises_mince": marge_vm_mince,
                "marge_von_mises_lame": marge_vm_lame,
            })

            rapport["verifications"].update({
                "hypothese_paroi_mince_ok": paroi_mince_ok,
                "note_paroi_mince": "OK (t/ri<=0.10)" if paroi_mince_ok else "NON (cylindre épais : utiliser Lamé)",
            })

            if self.materiau_cle and get_materiau is not None:
                try:
                    mat = get_materiau(self.materiau_cle)
                    section_mm = Do * 1000.0
                    Re_section = mat.limite_elastique_effective_pa(mode="min", section_mm=section_mm)
                    if Re_section is not None:
                        sigma_adm2 = float(Re_section)
                        t_mince2 = float(calcul_epaisseur_cylindre_mince(
                            pression_pa=delta_p,
                            rayon_interne_m=ri,
                            contrainte_admissible_pa=sigma_adm2,
                            include_longitudinale=False,
                            facteur_securite=FS,
                            clamp_non_negative=True,
                            return_details=False,
                        ))
                        sigma_eff2 = sigma_adm2 / FS
                        denom3 = (sigma_eff2 - p_i + 2.0 * p_o)
                        t_lame2 = None
                        if denom3 > 0:
                            ro2b = (ri * ri) * (sigma_eff2 + p_i) / denom3
                            t_lame2 = max(0.0, math.sqrt(ro2b) - ri)
                        t_ret2 = max([x for x in (t_mince2, t_lame2) if x is not None])
                        rapport["materiau"]["Re_section_mm"] = section_mm
                        rapport["materiau"]["limite_elastique_section_pa"] = float(Re_section)
                        rapport["dimensionnement"]["epaisseur_retenue_si_Re_section_m"] = float(t_ret2)
                except Exception:
                    pass
        else:
            _push_inconnue(rapport, "impossibles", "contraintes", "Impossible sans epaisseur_retenue_m > 0.")

        # ------------------------------------------------------------
        # 7) Déformations
        # ------------------------------------------------------------
        if t_retenue is not None and t_retenue > 0:
            if E is not None and nu is not None:
                E2 = _req_pos("module_young_pa", E)
                nu2 = _req_pos("coefficient_poisson", nu, strictly=False)

                sigma_theta = (delta_p * ri) / t_retenue
                sigma_long = (delta_p * ri) / (2.0 * t_retenue)
                eps_theta = (sigma_theta - nu2 * sigma_long) / E2
                delta_ri_p = eps_theta * ri

                rapport["deformations"].update({
                    "epsilon_cerclage_sous_pression": eps_theta,
                    "augmentation_rayon_interne_pression_m": delta_ri_p,
                    "augmentation_diametre_interne_pression_m": 2.0 * delta_ri_p,
                })
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "déformations sous pression",
                    "Calculables si module_young_pa et coefficient_poisson sont connus.",
                )

            if alpha is not None and self.delta_temperature_k is not None:
                a = _req_pos("coefficient_dilatation_1_k", alpha)
                dT = _req_finite("delta_temperature_k", self.delta_temperature_k)
                delta_D_th = a * D * dT
                rapport["deformations"].update({
                    "augmentation_diametre_interne_thermique_m": delta_D_th,
                    "augmentation_rayon_interne_thermique_m": 0.5 * delta_D_th,
                })
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "dilatation thermique",
                    "Calculable si alpha et delta_temperature_k sont fournis.",
                )

        # ------------------------------------------------------------
        # 8) Thermique
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

        if t_retenue is not None and t_retenue > 0 and k_mat is not None:
            k2 = _req_pos("conductivite_w_m_k", k_mat)
            ro = ri + t_retenue

            R_cond = math.log(ro / ri) / (2.0 * math.pi * k2 * L)
            rapport["thermique"]["R_conduction_K_W"] = R_cond

            if h_i is not None:
                hi = _req_pos("h_interne_w_m2_k", h_i)
                A_i = 2.0 * math.pi * ri * L
                rapport["thermique"]["R_convection_interne_K_W"] = 1.0 / (hi * A_i)
            else:
                _push_inconnue(rapport, "partielles", "R convection interne", "Calculable si h_interne_w_m2_k est fourni.")

            if h_o is not None:
                ho = _req_pos("h_externe_w_m2_k", h_o)
                A_o = 2.0 * math.pi * ro * L
                rapport["thermique"]["R_convection_externe_K_W"] = 1.0 / (ho * A_o)
            else:
                _push_inconnue(rapport, "partielles", "R convection externe", "Calculable si h_externe_w_m2_k est fourni.")

            if "R_convection_interne_K_W" in rapport["thermique"] and "R_convection_externe_K_W" in rapport["thermique"]:
                rapport["thermique"]["R_totale_K_W"] = (
                    rapport["thermique"]["R_convection_interne_K_W"]
                    + rapport["thermique"]["R_conduction_K_W"]
                    + rapport["thermique"]["R_convection_externe_K_W"]
                )
        else:
            if k_mat is None:
                _push_inconnue(rapport, "partielles", "thermique (conduction)", "Calculable si conductivite_w_m_k est fournie.")

        # ------------------------------------------------------------
        # 9) Masse + inerties
        # ------------------------------------------------------------
        if t_retenue is not None and t_retenue > 0:
            ro = ri + t_retenue
            section_metal = math.pi * (ro * ro - ri * ri)
            volume_metal = section_metal * L

            rapport["masse"].update({
                "section_metal_m2": section_metal,
                "volume_metal_m3": volume_metal,
            })

            if densite is not None:
                rho = _req_pos("densite_kg_m3", densite)
                m = rho * volume_metal
                rapport["masse"]["masse_kg"] = m
                rapport["masse"]["masse_lineique_kg_m"] = m / L if L > 0 else None
            else:
                _push_inconnue(rapport, "partielles", "masse cylindre", "Calculable si densite_kg_m3 est fournie.")

            Do = 2.0 * ro
            Di = 2.0 * ri
            I = (math.pi / 64.0) * (Do ** 4 - Di ** 4)
            Jp = 2.0 * I
            rapport["inerties"].update({
                "inertie_flexion_I_m4": I,
                "inertie_polaire_J_m4": Jp,
            })
        else:
            _push_inconnue(rapport, "impossibles", "masse/inerties", "Impossible sans epaisseur_retenue_m > 0.")

        # ------------------------------------------------------------
        # 10) Géométrie CAO fermée / assemblage
        # ------------------------------------------------------------
        if t_retenue is not None and t_retenue > 0:
            regles_fab = self.regles_fabrication or ReglesFabricationCylindre()
            regles_joint = self.regles_joint_torique
            regles_vis = self.regles_visserie or ReglesVisserieBride()

            if regles_joint is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "joint torique / fermeture complète",
                    "Fournir regles_joint_torique pour calculer gorge, fermeture et visserie.",
                )
                # Géométrie simple sans fermeture détaillée
                ro = ri + t_retenue
                rapport["geometrie"]["longueur_totale_sans_brides_m"] = L
                rapport["geometrie"]["diametre_externe_sans_brides_m"] = 2.0 * ro
                
                if self.epaisseur_bride_m is not None and self.largeur_bride_m is not None:
                    e_b = _req_pos("epaisseur_bride_m", self.epaisseur_bride_m)
                    w_b = _req_pos("largeur_bride_m", self.largeur_bride_m)
                    D_bride = 2.0 * (ro + w_b)
                    rapport["geometrie"]["diametre_externe_avec_brides_m"] = D_bride
                    rapport["geometrie"]["longueur_totale_avec_brides_m"] = L + 2.0 * e_b
                    
                    if densite is not None:
                        rho_mat = _req_pos("densite_kg_m3", densite)
                        r_b = 0.5 * D_bride
                        A_anneau = math.pi * (r_b * r_b - ro * ro)
                        V_brides = 2.0 * A_anneau * e_b
                        rapport["masse"]["volume_brides_m3"] = V_brides
                        rapport["masse"]["masse_brides_kg"] = rho_mat * V_brides
            else:
                try:
                    geo_cao = _calcul_cao_cylindre_ferme(
                        alesage_m=D,
                        longueur_utile_m=L,
                        epaisseur_retenue_m=t_retenue,
                        pression_max_pa=p_max,
                        pression_externe_pa=p_ext,
                        regles_fab=regles_fab,
                        regles_joint=regles_joint,
                        regles_vis=regles_vis,
                    )

                    # Overrides manuels de bride si fournis
                    if self.epaisseur_bride_m is not None:
                        geo_cao["bride"]["epaisseur_bride_m"] = _req_pos("epaisseur_bride_m", self.epaisseur_bride_m)
                    if self.largeur_bride_m is not None:
                        geo_cao["bride"]["largeur_bride_m"] = _req_pos("largeur_bride_m", self.largeur_bride_m)

                    rapport["geometrie"]["cao"] = geo_cao
                    rapport["geometrie"]["longueur_totale_avec_brides_m"] = geo_cao["longueur_totale_nominale_m"]
                    rapport["geometrie"]["diametre_externe_avec_brides_m"] = geo_cao["bride"]["diametre_bride_externe_m"]

                    rapport["assemblage"].update({
                        "type_fermeture": geo_cao["type_fermeture"],
                        "aire_effective_fermeture_m2": geo_cao["aire_effective_fermeture_m2"],
                        "force_separation_N": geo_cao["force_separation_N"],
                        "force_joint_N": geo_cao["force_joint_N"],
                        "force_precharge_totale_requise_N": geo_cao["force_precharge_totale_requise_N"],
                        "visserie": geo_cao["visserie"],
                        "bride": geo_cao["bride"],
                        "gorge_joint": geo_cao["gorge_joint"],
                    })

                    # Ajout masse brides si densité connue
                    if densite is not None:
                        rho = _req_pos("densite_kg_m3", densite)
                        D_bride = geo_cao["bride"]["diametre_bride_externe_m"]
                        e_b = geo_cao["bride"]["epaisseur_bride_m"]
                        ro_cyl = 0.5 * geo_cao["diametre_exterieur_nominal_m"]
                        r_b = 0.5 * D_bride
                        A_anneau = math.pi * (r_b * r_b - ro_cyl * ro_cyl)
                        V_brides = 2.0 * A_anneau * e_b
                        rapport["masse"]["volume_brides_m3"] = V_brides
                        rapport["masse"]["masse_brides_kg"] = rho * V_brides
                    else:
                        _push_inconnue(rapport, "partielles", "masse brides", "Calculable si densite_kg_m3 est fournie.")

                except Exception as e:
                    _push_inconnue(rapport, "partielles", "géométrie CAO", f"Impossible de générer la géométrie CAO complète: {e!r}")

        # ------------------------------------------------------------
        # 11) Mode strict
        # ------------------------------------------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "Cylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport