# backend/pieces/couvercle_cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
import math

# ============================================================
# Imports projet (avec fallbacks) — réduction des inconnues
# ============================================================

# --- Matériaux (réduction d'inconnues) ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None

# --- Pièces associées (optionnel) ---
try:
    from backend.pieces.cylindre import Cylindre
except Exception:  # pragma: no cover
    try:
        from pieces.cylindre import Cylindre  # type: ignore
    except Exception:  # pragma: no cover
        Cylindre = None  # type: ignore

# --- Fluides (optionnel : calcul h convection si tu veux) ---
try:
    from backend.ensemble.eau import etat_eau_pure, etat_eau_salee, etat_antigel
except Exception:  # pragma: no cover
    etat_eau_pure = etat_eau_salee = etat_antigel = None  # type: ignore

try:
    from backend.ensemble.air import air_state
except Exception:  # pragma: no cover
    air_state = None  # type: ignore


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
# Convection (optionnelle) : calcul h dans un tube
# ============================================================

FluideType = Literal["air", "eau_pure", "eau_salee", "antigel"]

@dataclass(frozen=True)
class EntreeConvectionTube:
    fluide: FluideType
    T_K: float
    p_Pa: float

    # Pour "air"
    altitude_m: float = 0.0
    RH: float = 0.0
    co2_ppm: float = 420.0

    # Pour eau salée
    salinite_g_kg: float = 35.0

    # Pour antigel
    fraction_massique_glycol: float = 0.0
    type_glycol: Literal["MEG", "MPG"] = "MEG"

    # Ecoulement
    debit_massique_kg_s: float = 0.0
    diametre_m: float = 0.0

    # Choix corrélation (minimal)
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
    return {"A_section_m2": A, "v_m_s": v, "Re": Re, "Pr": Pr, "Nu": Nu, "h_W_m2_K": h, "modele_txt": modele_txt}

def _etat_fluide_pour_convection(ent: EntreeConvectionTube) -> Dict[str, float]:
    if ent.fluide == "air":
        if air_state is None:
            raise RuntimeError("backend.ensemble.air.air_state indisponible.")
        st = air_state(
            altitude_m=float(ent.altitude_m),
            T_K=float(ent.T_K),
            p_Pa=float(ent.p_Pa),
            RH=float(ent.RH),
            co2_ppm=float(ent.co2_ppm),
        )
        return {"rho": float(st.rho_kg_m3), "cp": float(st.cp_J_kgK), "mu": float(st.mu_Pa_s), "k": float(st.k_W_mK)}

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
# Matériau : extraction (réduit fortement les inconnues)
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

    # Re conservateur (min global)
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
# ISO filetages métriques (sélection déterministe)
# ============================================================

FiletageSerie = Literal["iso_metric_coarse"]

# ISO 261 (pas grossier) — valeurs usuelles (mm)
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

def _iso898_yield_strength_pa_from_class(classe_iso: str) -> float:
    """
    Classe ISO 898-1 (ex: "8.8", "10.9").
    Définition :
      Rm (MPa) = 100 * premier_nombre
      Re (MPa) = 10 * premier_nombre * second_nombre
    """
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
    """
    Aire résistante traction As (mm²), formule usuelle ISO 898-1 :
      As = (pi/4) * (d - 0.9382*p)^2
    """
    d = _req_pos("d_mm", d_mm)
    p = _req_pos("p_mm", p_mm)
    return (math.pi / 4.0) * ((d - 0.9382 * p) ** 2)

def _internal_thread_minor_diameter_mm(d_mm: float, p_mm: float) -> float:
    """
    Diamètre au fond de filet (taraudage) D1 (mm) (valeur "basic") :
      D1 ≈ D - 1.082532 * P
    """
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
        raise ValueError("pas_mm non fourni et pas grossier introuvable pour ce diamètre dans la table.")
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

    raise ValueError("Aucun filetage trouvé dans la série pour satisfaire As_requise_m2 (ou d_max_mm trop bas).")


# ============================================================
# Modèle plaque circulaire (encastrée) — calculs
# ============================================================

def _plaque_circulaire_encastree_uniforme(
    *,
    q_Pa: float,
    rayon_m: float,
    epaisseur_m: float,
    E_Pa: float,
    nu: float,
) -> Dict[str, float]:
    q = abs(float(q_Pa))
    a = _req_pos("rayon_m", rayon_m)
    t = _req_pos("epaisseur_m", epaisseur_m)
    E = _req_pos("E_Pa", E_Pa)
    nu2 = _req_pos("nu", nu, strictly=False)

    M0 = q * a * a / 16.0
    sigma_max = (6.0 * M0) / (t * t)

    Dflex = (E * (t ** 3)) / (12.0 * (1.0 - nu2 ** 2))
    w0 = (q * (a ** 4)) / (64.0 * Dflex) if Dflex > 0 else float("nan")

    return {"M0_Nm_par_m": M0, "sigma_flexion_max_Pa": sigma_max, "w0_m": w0, "D_flexion_Nm": Dflex}

def _epaisseur_requise_sigma_plaque_encastree(
    *,
    q_Pa: float,
    rayon_m: float,
    sigma_admissible_eff_Pa: float,
) -> float:
    q = abs(float(q_Pa))
    a = _req_pos("rayon_m", rayon_m)
    s = _req_pos("sigma_admissible_eff_Pa", sigma_admissible_eff_Pa)
    return math.sqrt((3.0 * q * a * a) / (8.0 * s))

def _epaisseur_requise_fleche_plaque_encastree(
    *,
    q_Pa: float,
    rayon_m: float,
    E_Pa: float,
    nu: float,
    fleche_max_m: float,
) -> float:
    q = abs(float(q_Pa))
    a = _req_pos("rayon_m", rayon_m)
    E = _req_pos("E_Pa", E_Pa)
    nu2 = _req_pos("nu", nu, strictly=False)
    w = _req_pos("fleche_max_m", fleche_max_m)
    num = 12.0 * (1.0 - nu2 ** 2) * q * (a ** 4)
    den = 64.0 * E * w
    return (num / den) ** (1.0 / 3.0)


# ============================================================
# Pièce : Couvercle de cylindre
# ============================================================

TypeAppui = Literal["encastre"]
SourceAppui = Literal["ouverture", "cylindre_sans_brides", "cylindre_avec_brides"]

@dataclass(frozen=True)
class CouvercleCylindre:
    """
    Objectif : dimensionner le couvercle (plaque encastrée) et réduire au maximum
    les inconnues en s'appuyant sur (1) un matériau, (2) un cylindre si fourni,
    (3) un dimensionnement vis/taraudage ISO métrique (optionnel).

    Le code n'invente pas :
    - si une donnée n'est pas calculable, elle est signalée via 'inconnues'.
    """

    # Référence pièce associée (réduit les inconnues géométriques/pression)
    cylindre: Optional[Any] = None  # attendu: Cylindre, si importable, ou dict rapport

    # Géométrie ouverture / appui
    diametre_ouverture_m: Optional[float] = None
    rayon_appui_m: Optional[float] = None
    source_appui: SourceAppui = "ouverture"  # défaut: D/2 (pas de supposition)

    rayon_externe_m: Optional[float] = None  # masse : si None => rayon_appui_m

    # Pressions
    pression_service_pa: Optional[float] = None
    pression_max_pa: Optional[float] = None
    pression_externe_pa: float = 0.0

    # Epaisseur
    epaisseur_m: Optional[float] = None
    epaisseur_min_fabrication_m: float = 0.0
    limite_fleche_centre_m: Optional[float] = None

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

    # Thermique (optionnel)
    convection_interne: Optional[EntreeConvectionTube] = None
    convection_externe: Optional[EntreeConvectionTube] = None
    h_interne_w_m2_k: Optional[float] = None
    h_externe_w_m2_k: Optional[float] = None

    # Assemblage / taraudage (optionnel)
    nb_vis: Optional[int] = None
    facteur_partage_charge: float = 1.0
    facteur_securite_etancheite: float = 1.0

    # Vis (capacité traction)
    aire_resistante_vis_m2: Optional[float] = None     # As si connue
    limite_elastique_vis_pa: Optional[float] = None    # Re vis
    classe_vis_iso898: Optional[str] = None            # sinon Re vis calculée
    facteur_securite_vis: float = 2.0

    # Filetage ISO (si As non fourni)
    serie_filetage: FiletageSerie = "iso_metric_coarse"
    d_max_vis_mm: Optional[float] = None
    vis_d_nominal_mm: Optional[float] = None          # si tu veux imposer un diamètre (ex: 10)
    vis_pas_mm: Optional[float] = None                # optionnel si pas grossier connu

    type_appui: TypeAppui = "encastre"

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
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ----------------------------
        # 0) Auto-déduction depuis cylindre (si fourni)
        # ----------------------------
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

        # Diamètre ouverture : input > cylindre.alesage_m
        D_ouv: Optional[float] = self.diametre_ouverture_m
        if D_ouv is None and cyl is not None:
            try:
                if hasattr(cyl, "alesage_m"):
                    D_ouv = float(getattr(cyl, "alesage_m"))
            except Exception:
                D_ouv = None

        # Pressions : input > cylindre.*
        p_serv = self.pression_service_pa
        p_max = self.pression_max_pa
        if cyl is not None:
            try:
                if p_serv is None and hasattr(cyl, "pression_service_pa"):
                    p_serv = float(getattr(cyl, "pression_service_pa"))
                if p_max is None and hasattr(cyl, "pression_max_pa"):
                    p_max = float(getattr(cyl, "pression_max_pa"))
            except Exception:
                pass

        # Validation entrées minimales
        if D_ouv is None:
            _push_inconnue(rapport, "impossibles", "diametre_ouverture_m", "Donner diametre_ouverture_m OU fournir un cylindre avec alesage_m.")
            D_ouv = float("nan")
        else:
            D_ouv = _req_pos("diametre_ouverture_m", D_ouv)

        if p_max is None:
            _push_inconnue(rapport, "impossibles", "pression_max_pa", "Nécessaire pour calculer la force de séparation et dimensionner (ou fournir cylindre/pression).")
        p_serv_v = 0.0 if p_serv is None else _req_pos("pression_service_pa", p_serv, strictly=False)
        p_max_v = 0.0 if p_max is None else _req_pos("pression_max_pa", p_max, strictly=False)

        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        FS = _req_pos("facteur_securite", self.facteur_securite)
        e_min = _req_pos("epaisseur_min_fabrication_m", self.epaisseur_min_fabrication_m, strictly=False)

        if _is_finite(p_serv_v) and _is_finite(p_max_v) and p_max_v < p_serv_v:
            rapport["notes_modele"].append("pression_max_pa < pression_service_pa : dimensionnement fait sur pression_max_pa quand même.")

        # Appui (rayon) : input > source_appui
        a: Optional[float] = self.rayon_appui_m
        if a is None:
            if self.source_appui == "ouverture":
                a = 0.5 * D_ouv
            elif cyl_rep is not None:
                geo = cyl_rep.get("geometrie", {}) if isinstance(cyl_rep.get("geometrie", {}), dict) else {}
                if self.source_appui == "cylindre_sans_brides":
                    a = geo.get("rayon_externe_m")
                elif self.source_appui == "cylindre_avec_brides":
                    a = geo.get("rayon_externe_avec_brides_m")
        if a is None:
            _push_inconnue(rapport, "partielles", "rayon_appui_m", "Non déduit (source_appui nécessite un cylindre analysable).")
            a = 0.5 * D_ouv
        a = _req_pos("rayon_appui_m", a)

        r_ext = self.rayon_externe_m if self.rayon_externe_m is not None else a
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
            "limite_fleche_centre_m": self.limite_fleche_centre_m,
            "materiau_cle": self.materiau_cle,
            "mode_materiau": self.mode_materiau,
            "type_appui": self.type_appui,
            "temperature_service_C": self.temperature_service_C,
            "cylindre_fournit": cyl is not None,
        })

        # ----------------------------
        # 1) Matériau : auto-déduction
        # ----------------------------
        matp: Dict[str, Any] = {}
        if self.materiau_cle:
            try:
                matp = _materiau_resoudre(materiau_cle=self.materiau_cle, mode=self.mode_materiau)
                rapport["materiau"].update(matp)

                if self.temperature_service_C is not None:
                    tmin = matp.get("T_service_min_C")
                    tmax = matp.get("T_service_max_C")
                    if tmin is not None and self.temperature_service_C < float(tmin):
                        rapport["notes_modele"].append(f"Température service {self.temperature_service_C}°C < Tmin matériau ({tmin}°C).")
                    if tmax is not None and self.temperature_service_C > float(tmax):
                        rapport["notes_modele"].append(f"Température service {self.temperature_service_C}°C > Tmax matériau ({tmax}°C).")
            except Exception as e:
                _push_inconnue(rapport, "partielles", "matériau auto", f"Impossible de charger materiau_cle={self.materiau_cle!r}: {e!r}")

        densite = self.densite_kg_m3 if self.densite_kg_m3 is not None else matp.get("densite_kg_m3")
        E = self.module_young_pa if self.module_young_pa is not None else matp.get("module_young_pa")
        nu = self.coefficient_poisson if self.coefficient_poisson is not None else matp.get("poisson")
        alpha = self.coefficient_dilatation_1_k if self.coefficient_dilatation_1_k is not None else matp.get("alpha_dilatation_1_k")
        k_mat = self.conductivite_w_m_k if self.conductivite_w_m_k is not None else matp.get("conductivite_w_m_k")
        Re = self.limite_elastique_pa if self.limite_elastique_pa is not None else matp.get("limite_elastique_min_pa")

        # ----------------------------
        # 2) Contrainte admissible (pour dimensionner)
        # ----------------------------
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

        # ----------------------------
        # 3) Charges pression (sur ouverture)
        # ----------------------------
        delta_p = max(0.0, p_max_v - p_ext)
        A_ouverture = math.pi * (0.5 * D_ouv) ** 2
        F_sep = delta_p * A_ouverture
        rapport["charges"].update({
            "delta_p_dimensionnement_pa": delta_p,
            "aire_ouverture_m2": A_ouverture,
            "force_separation_N": F_sep,
        })
        q = delta_p

        # ----------------------------
        # 4) Dimensionnement épaisseur (plaque encastrée)
        # ----------------------------
        if self.type_appui != "encastre":
            _push_inconnue(rapport, "impossibles", "type_appui", "Seul 'encastre' est implémenté ici.")

        e_calc: Optional[float] = None
        e_req_sigma: Optional[float] = None
        e_req_fleche: Optional[float] = None

        if self.epaisseur_m is not None:
            e_calc = _req_pos("epaisseur_m", self.epaisseur_m)
        else:
            if sigma_adm is None:
                _push_inconnue(rapport, "impossibles", "epaisseur_m", "Impossible de dimensionner sans sigma_adm.")
            else:
                sigma_eff = sigma_adm / FS
                if sigma_eff <= 0:
                    _push_inconnue(rapport, "impossibles", "sigma_eff", "sigma_adm/FS <= 0.")
                else:
                    e_req_sigma = _epaisseur_requise_sigma_plaque_encastree(
                        q_Pa=q,
                        rayon_m=a,
                        sigma_admissible_eff_Pa=sigma_eff,
                    )

                if self.limite_fleche_centre_m is not None:
                    if E is None or nu is None:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "epaisseur (flèche)",
                            "Dimensionnement flèche possible si module_young_pa et coefficient_poisson sont connus (ou via materiau_cle).",
                        )
                    else:
                        try:
                            e_req_fleche = _epaisseur_requise_fleche_plaque_encastree(
                                q_Pa=q,
                                rayon_m=a,
                                E_Pa=_req_pos("module_young_pa", E),
                                nu=_req_pos("coefficient_poisson", nu, strictly=False),
                                fleche_max_m=_req_pos("limite_fleche_centre_m", self.limite_fleche_centre_m),
                            )
                        except Exception as e:
                            _push_inconnue(rapport, "partielles", "epaisseur (flèche)", f"Erreur calcul flèche: {e!r}")

                cands = [x for x in (e_req_sigma, e_req_fleche, e_min) if _is_finite(x) and float(x) > 0]
                if cands:
                    e_calc = float(max(cands))
                else:
                    _push_inconnue(rapport, "impossibles", "epaisseur_m", "Aucun critère exploitable pour dimensionner l'épaisseur.")

        rapport["dimensionnement"].update({
            "q_uniforme_Pa": q,
            "rayon_plaque_m": a,
            "epaisseur_requise_sigma_m": e_req_sigma,
            "epaisseur_requise_fleche_m": e_req_fleche,
            "epaisseur_retenue_m": e_calc,
            "epaisseur_source": "input" if self.epaisseur_m is not None else "dimensionnement",
        })

        # ----------------------------
        # 5) Contraintes + flèche pour l'épaisseur retenue
        # ----------------------------
        if e_calc is not None and e_calc > 0:
            sigma_max = (3.0 * q * (a ** 2)) / (8.0 * (e_calc ** 2))
            marge_sigma = None
            if sigma_adm is not None and sigma_max > 0:
                marge_sigma = (sigma_adm / FS) / sigma_max
            rapport["contraintes"].update({"sigma_flexion_max_Pa": sigma_max, "marge_sigma_flexion": marge_sigma})

            if E is not None and nu is not None:
                try:
                    res_pl = _plaque_circulaire_encastree_uniforme(
                        q_Pa=q,
                        rayon_m=a,
                        epaisseur_m=e_calc,
                        E_Pa=_req_pos("module_young_pa", E),
                        nu=_req_pos("coefficient_poisson", nu, strictly=False),
                    )
                    rapport["deformations"].update({
                        "fleche_centre_m": float(res_pl["w0_m"]),
                        "rigidite_flexion_D_Nm": float(res_pl["D_flexion_Nm"]),
                        "moment_centre_Nm_par_m": float(res_pl["M0_Nm_par_m"]),
                    })
                    if self.limite_fleche_centre_m is not None:
                        rapport["verifications"]["fleche_ok"] = float(res_pl["w0_m"]) <= float(self.limite_fleche_centre_m)
                except Exception as e:
                    _push_inconnue(rapport, "partielles", "flèche plaque", f"Impossible de calculer la flèche: {e!r}")
            else:
                _push_inconnue(rapport, "partielles", "flèche plaque", "Calculable si module_young_pa et coefficient_poisson sont connus (ou via materiau_cle).")

            if alpha is not None and self.delta_temperature_k is not None:
                a2 = _req_pos("coefficient_dilatation_1_k", alpha)
                dT = _req_finite("delta_temperature_k", self.delta_temperature_k)
                rapport["deformations"]["delta_diametre_ouverture_thermique_m"] = a2 * D_ouv * dT
            else:
                _push_inconnue(rapport, "partielles", "dilatation thermique", "Calculable si alpha (ou materiau_cle) et delta_temperature_k sont fournis.")
        else:
            _push_inconnue(rapport, "impossibles", "contraintes/déformations", "Impossible sans epaisseur_retenue_m > 0.")

        # ----------------------------
        # 6) Thermique : conduction + convection (optionnel)
        # ----------------------------
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

        if e_calc is not None and e_calc > 0 and k_mat is not None:
            k2 = _req_pos("conductivite_w_m_k", k_mat)
            R_cond = e_calc / (k2 * A_ouverture) if A_ouverture > 0 else None
            rapport["thermique"]["R_conduction_K_W"] = R_cond

            if h_i is not None:
                hi = _req_pos("h_interne_w_m2_k", h_i)
                rapport["thermique"]["R_convection_interne_K_W"] = 1.0 / (hi * A_ouverture)
            else:
                _push_inconnue(rapport, "partielles", "R convection interne", "Calculable si h_interne_w_m2_k est fourni (ou convection_interne).")

            if h_o is not None:
                ho = _req_pos("h_externe_w_m2_k", h_o)
                rapport["thermique"]["R_convection_externe_K_W"] = 1.0 / (ho * A_ouverture)
            else:
                _push_inconnue(rapport, "partielles", "R convection externe", "Calculable si h_externe_w_m2_k est fourni (ou convection_externe).")

            if ("R_convection_interne_K_W" in rapport["thermique"]) and ("R_convection_externe_K_W" in rapport["thermique"]) and (R_cond is not None):
                rapport["thermique"]["R_totale_K_W"] = (
                    float(rapport["thermique"]["R_convection_interne_K_W"])
                    + float(R_cond)
                    + float(rapport["thermique"]["R_convection_externe_K_W"])
                )
        else:
            if k_mat is None:
                _push_inconnue(rapport, "partielles", "thermique (conduction)", "Calculable si conductivite_w_m_k est fourni (souvent via materiau_cle).")

        # ----------------------------
        # 7) Masse (disque) si densité
        # ----------------------------
        if e_calc is not None and e_calc > 0:
            A_ext = math.pi * (r_ext ** 2)
            V = A_ext * e_calc
            rapport["masse"].update({"aire_externe_m2": A_ext, "volume_m3": V})
            if densite is not None:
                rho = _req_pos("densite_kg_m3", densite)
                rapport["masse"]["masse_kg"] = rho * V
            else:
                _push_inconnue(rapport, "partielles", "masse", "Calculable si densite_kg_m3 est fournie (souvent via materiau_cle).")

        # ----------------------------
        # 8) Vis/taraudage : deux modes
        #    - nb_vis connu -> choix/verification filetage
        #    - nb_vis inconnu mais filetage imposé -> nb_vis requis
        # ----------------------------
        # Re vis : input > classe ISO 898
        Re_vis: Optional[float] = self.limite_elastique_vis_pa
        if Re_vis is None and self.classe_vis_iso898 is not None:
            try:
                Re_vis = float(_iso898_yield_strength_pa_from_class(self.classe_vis_iso898))
                rapport["assemblage"]["limite_elastique_vis_source"] = f"classe_vis_iso898={self.classe_vis_iso898}"
            except Exception as e:
                _push_inconnue(rapport, "partielles", "limite_elastique_vis_pa", f"Classe vis ISO 898 invalide: {e!r}")
                Re_vis = None

        sigma_eff_vis: Optional[float] = None
        if Re_vis is not None:
            Re_v = _req_pos("limite_elastique_vis_pa", Re_vis)
            FSv = _req_pos("facteur_securite_vis", self.facteur_securite_vis)
            sigma_eff_vis = Re_v / FSv
            rapport["assemblage"]["sigma_admissible_vis_eff_Pa"] = sigma_eff_vis
        else:
            _push_inconnue(rapport, "partielles", "sigma_admissible_vis_eff_Pa", "Calculable si limite_elastique_vis_pa (ou classe_vis_iso898) est fournie.")

        F_total_requis = F_sep * _req_pos("facteur_partage_charge", self.facteur_partage_charge) * _req_pos(
            "facteur_securite_etancheite", self.facteur_securite_etancheite
        )
        rapport["assemblage"]["force_totale_requise_N"] = F_total_requis

        # Filetage imposé ?
        filetage_impose: Optional[Dict[str, Any]] = None
        if self.vis_d_nominal_mm is not None:
            try:
                filetage_impose = _filetage_depuis_nominal(d_nominal_mm=self.vis_d_nominal_mm, pas_mm=self.vis_pas_mm)
                rapport["assemblage"]["filetage_impose"] = filetage_impose
            except Exception as e:
                _push_inconnue(rapport, "partielles", "filetage_impose", f"Impossible de construire le filetage imposé: {e!r}")
                filetage_impose = None

        # As : input > filetage imposé > filetage auto
        As_m2: Optional[float] = None
        if self.aire_resistante_vis_m2 is not None:
            As_m2 = _req_pos("aire_resistante_vis_m2", self.aire_resistante_vis_m2)
            rapport["assemblage"]["As_source"] = "aire_resistante_vis_m2 (input)"
        elif filetage_impose is not None:
            As_m2 = float(filetage_impose["As_m2"])
            rapport["assemblage"]["As_source"] = "filetage_impose"
        # filetage_auto uniquement si nb_vis connu

        if self.nb_vis is not None:
            n = int(self.nb_vis)
            if n < 1:
                _push_inconnue(rapport, "impossibles", "nb_vis", "nb_vis doit être >= 1.")
            else:
                F_par_vis = F_total_requis / n
                rapport["assemblage"]["nb_vis"] = n
                rapport["assemblage"]["force_requise_par_vis_N"] = F_par_vis

                filetage_auto: Optional[Dict[str, Any]] = None
                if As_m2 is None:
                    if sigma_eff_vis is not None and sigma_eff_vis > 0:
                        As_req_m2 = float(F_par_vis) / float(sigma_eff_vis)
                        rapport["assemblage"]["As_requise_m2"] = As_req_m2
                        try:
                            filetage_auto = _choisir_filetage(
                                serie=self.serie_filetage,
                                As_requise_m2=As_req_m2,
                                d_max_mm=self.d_max_vis_mm,
                            )
                            rapport["assemblage"]["filetage_recommande"] = filetage_auto
                            As_m2 = float(filetage_auto["As_m2"])
                            rapport["assemblage"]["As_source"] = "filetage_recommande (ISO série)"
                        except Exception as e:
                            _push_inconnue(rapport, "partielles", "filetage_recommande", f"Impossible de choisir un filetage: {e!r}")
                    else:
                        _push_inconnue(rapport, "partielles", "As", "Aire résistante déductible si limite_elastique_vis et FS sont connus.")

                if As_m2 is not None and As_m2 > 0:
                    sigma_vis = float(F_par_vis) / float(As_m2)
                    rapport["assemblage"]["sigma_traction_vis_Pa"] = sigma_vis
                    if sigma_eff_vis is not None and sigma_vis > 0:
                        rapport["assemblage"]["marge_traction_vis"] = float(sigma_eff_vis) / float(sigma_vis)
        else:
            # nb_vis inconnu : on peut le déduire si filetage (=> As) ET sigma_eff_vis connus.
            if As_m2 is not None and sigma_eff_vis is not None and As_m2 > 0 and sigma_eff_vis > 0:
                F_cap_par_vis = float(As_m2) * float(sigma_eff_vis)
                n_req = int(math.ceil(float(F_total_requis) / float(F_cap_par_vis))) if F_cap_par_vis > 0 else None
                rapport["assemblage"]["nb_vis_requis"] = n_req
                rapport["assemblage"]["capacite_traction_par_vis_N"] = F_cap_par_vis
            else:
                _push_inconnue(rapport, "partielles", "nb_vis", "nb_vis requis calculable si filetage (As) et limite_elastique_vis (ou classe) sont connus.")

        # ----------------------------
        # 9) Mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CouvercleCylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport
