# backend/pieces/couvercle_cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
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
# Convection (optionnelle) : calcul h dans un tube
# (utile si tu veux estimer h côté couvercle, sinon laisse h_* en input)
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
    Re_candidates: list[float] = []
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
    """
    Plaque mince (Kirchhoff–Love), circulaire, encastrée au bord, chargement uniforme q.
    Résultats principaux :
    - Moment au centre (par unité de longueur): M0 = q a^2 / 16
    - Contrainte de flexion max (approx surface): sigma_max ≈ 6*M0/t^2 = 3*q*a^2/(8*t^2)
    - Flèche au centre: w0 = q a^4 / (64*D), D = E t^3 / (12*(1-nu^2))
    """
    q = abs(float(q_Pa))
    a = _req_pos("rayon_m", rayon_m)
    t = _req_pos("epaisseur_m", epaisseur_m)
    E = _req_pos("E_Pa", E_Pa)
    nu2 = _req_pos("nu", nu, strictly=False)

    M0 = q * a * a / 16.0
    sigma_max = (6.0 * M0) / (t * t)  # ~ 3*q*a^2/(8*t^2)

    Dflex = (E * (t ** 3)) / (12.0 * (1.0 - nu2 ** 2))
    w0 = (q * (a ** 4)) / (64.0 * Dflex) if Dflex > 0 else float("nan")

    return {"M0_Nm_par_m": M0, "sigma_flexion_max_Pa": sigma_max, "w0_m": w0, "D_flexion_Nm": Dflex}

def _epaisseur_requise_sigma_plaque_encastree(
    *,
    q_Pa: float,
    rayon_m: float,
    sigma_admissible_eff_Pa: float,
) -> float:
    # sigma_max = 3*q*a^2/(8*t^2) <= sigma_eff => t >= sqrt(3*q*a^2/(8*sigma_eff))
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
    # w0 = q a^4 /(64 D), D = E t^3 /(12(1-nu^2))
    # => w0 = (12(1-nu^2) q a^4)/(64 E t^3)
    # => t >= [ (12(1-nu^2) q a^4)/(64 E w0) ]^(1/3)
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

TypeAppui = Literal["encastre"]  # volontairement limité : pas de "simple_appui" sans référentiel explicit

@dataclass(frozen=True)
class CouvercleCylindre:
    """
    Objectif :
    - Calculer un maximum de grandeurs sans “inventer”.
    - Réduire les inconnues via materiau_cle + (option) convection h.
    - Dimensionner l'épaisseur (si non fournie) sur :
      (A) contrainte de flexion max (plaque encastrée)
      (B) flèche max (si limite_fleche_centre_m fournie + E/nu dispo)

    Important :
    - Modèle "plaque mince encastrée" : valable si t << rayon et déformations petites.
    - Si tu veux un couvercle bombé/épais/avec nervures : c'est un autre modèle.
    """

    # Géométrie ouverture / appui
    diametre_ouverture_m: float                     # diamètre hydraulique (sur lequel agit la pression)
    rayon_appui_m: Optional[float] = None           # rayon de l'encastrement (si None => D_ouverture/2)
    rayon_externe_m: Optional[float] = None         # pour masse (si None => rayon_appui_m)

    # Pressions
    pression_service_pa: float = 0.0
    pression_max_pa: float = 0.0
    pression_externe_pa: float = 0.0

    # Epaisseur
    epaisseur_m: Optional[float] = None             # si fourni => vérif; sinon => dimensionnement
    epaisseur_min_fabrication_m: float = 0.0        # si tu veux imposer un mini (0 => aucun)
    limite_fleche_centre_m: Optional[float] = None  # optionnel

    # Matériau (réduction inconnues)
    materiau_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "min"

    # Overrides manuels (prioritaires)
    contrainte_admissible_pa: Optional[float] = None  # interprétée comme "limite matériau" avant FS
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

    # Assemblage par vis (optionnel)
    nb_vis: Optional[int] = None
    aire_resistante_vis_m2: Optional[float] = None  # As (zone résistante traction) si connue
    limite_elastique_vis_pa: Optional[float] = None
    facteur_securite_vis: float = 2.0
    facteur_partage_charge: float = 1.0             # >=1 si tu veux majorer (non-uniformité)
    facteur_securite_etancheite: float = 1.0        # >=1 si tu veux exiger plus que F_sep

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
        # 1) Validation entrées
        # ----------------------------
        D_ouv = _req_pos("diametre_ouverture_m", self.diametre_ouverture_m)
        p_serv = _req_pos("pression_service_pa", self.pression_service_pa, strictly=False)
        p_max = _req_pos("pression_max_pa", self.pression_max_pa, strictly=False)
        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        FS = _req_pos("facteur_securite", self.facteur_securite)
        e_min = _req_pos("epaisseur_min_fabrication_m", self.epaisseur_min_fabrication_m, strictly=False)

        if p_max < p_serv:
            rapport["notes_modele"].append("pression_max_pa < pression_service_pa : dimensionnement fait sur pression_max_pa quand même.")

        a = self.rayon_appui_m if self.rayon_appui_m is not None else 0.5 * D_ouv
        a = _req_pos("rayon_appui_m (ou D_ouv/2)", a)

        r_ext = self.rayon_externe_m if self.rayon_externe_m is not None else a
        r_ext = _req_pos("rayon_externe_m", r_ext)

        if r_ext < a:
            rapport["notes_modele"].append("rayon_externe_m < rayon_appui_m : masse calculée sur rayon_externe_m (disque plus petit que l'appui).")

        rapport["entrees"].update({
            "diametre_ouverture_m": D_ouv,
            "rayon_appui_m": a,
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
        })

        # ----------------------------
        # 2) Matériau : auto-déduction
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
        # 3) Contrainte admissible (pour dimensionner)
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
        # 4) Charges pression (sur ouverture)
        # ----------------------------
        delta_p = max(0.0, p_max - p_ext)
        A_ouverture = math.pi * (0.5 * D_ouv) ** 2
        F_sep = delta_p * A_ouverture  # effort qui tend à séparer couvercle/cylindre (ordre 1)
        rapport["charges"].update({
            "delta_p_dimensionnement_pa": delta_p,
            "aire_ouverture_m2": A_ouverture,
            "force_separation_N": F_sep,
        })

        # Charge surfacique sur plaque: q = delta_p (Pa = N/m²)
        q = delta_p

        # ----------------------------
        # 5) Dimensionnement épaisseur (plaque encastrée)
        # ----------------------------
        e_calc: Optional[float] = None
        e_req_sigma: Optional[float] = None
        e_req_fleche: Optional[float] = None

        if self.type_appui != "encastre":
            _push_inconnue(rapport, "impossibles", "type_appui", "Seul 'encastre' est implémenté ici (pas de formules supportées sans référentiel).")

        if self.epaisseur_m is not None:
            e_calc = _req_pos("epaisseur_m", self.epaisseur_m)
            if e_min > 0 and e_calc < e_min:
                rapport["notes_modele"].append("epaisseur_m < epaisseur_min_fabrication_m : vérifs faites mais attention au mini fabrication.")
        else:
            # dimensionnement seulement si sigma_adm connu
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

                # flèche : nécessite E et nu et limite_fleche
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
        # 6) Contraintes + flèche pour l'épaisseur retenue
        # ----------------------------
        if e_calc is not None and e_calc > 0:
            # contraintes flexion calculables sans E/nu
            # flèche nécessite E/nu
            sigma_max = (3.0 * q * (a ** 2)) / (8.0 * (e_calc ** 2)) if e_calc > 0 else None

            marge_sigma = None
            if sigma_adm is not None:
                sigma_eff = sigma_adm / FS
                if sigma_max and sigma_max > 0:
                    marge_sigma = sigma_eff / sigma_max

            rapport["contraintes"].update({
                "sigma_flexion_max_Pa": sigma_max,
                "marge_sigma_flexion": marge_sigma,
            })

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
                _push_inconnue(
                    rapport,
                    "partielles",
                    "flèche plaque",
                    "Calculable si module_young_pa et coefficient_poisson sont connus (ou via materiau_cle).",
                )

            # Dilatation thermique (géométrique) si alpha et dT
            if alpha is not None and self.delta_temperature_k is not None:
                a2 = _req_pos("coefficient_dilatation_1_k", alpha)
                dT = _req_finite("delta_temperature_k", self.delta_temperature_k)
                # variation diamètre ouverture (ordre 1)
                rapport["deformations"]["delta_diametre_ouverture_thermique_m"] = a2 * D_ouv * dT
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "dilatation thermique",
                    "Calculable si alpha (ou materiau_cle) et delta_temperature_k sont fournis.",
                )

        else:
            _push_inconnue(rapport, "impossibles", "contraintes/déformations", "Impossible sans epaisseur_retenue_m > 0.")

        # ----------------------------
        # 7) Thermique : conduction à travers le couvercle + convection (optionnel)
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
            # conduction à travers disque (approx) sur l'aire d'ouverture
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

            if "R_convection_interne_K_W" in rapport["thermique"] and "R_convection_externe_K_W" in rapport["thermique"]:
                if R_cond is not None:
                    rapport["thermique"]["R_totale_K_W"] = (
                        rapport["thermique"]["R_convection_interne_K_W"]
                        + float(R_cond)
                        + rapport["thermique"]["R_convection_externe_K_W"]
                    )
        else:
            if k_mat is None:
                _push_inconnue(rapport, "partielles", "thermique (conduction)", "Calculable si conductivite_w_m_k est fourni (souvent via materiau_cle).")

        # ----------------------------
        # 8) Masse (disque) si densité
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
        # 9) Assemblage vis : effort séparation -> effort par vis + check traction (si possible)
        # ----------------------------
        if self.nb_vis is not None:
            n = int(self.nb_vis)
            if n < 1:
                _push_inconnue(rapport, "impossibles", "nb_vis", "nb_vis doit être >= 1.")
            else:
                F_total_requis = F_sep * _req_pos("facteur_partage_charge", self.facteur_partage_charge) * _req_pos(
                    "facteur_securite_etancheite", self.facteur_securite_etancheite
                )
                F_par_vis = F_total_requis / n

                rapport["assemblage"].update({
                    "force_totale_requise_N": F_total_requis,
                    "force_requise_par_vis_N": F_par_vis,
                    "nb_vis": n,
                    "facteur_partage_charge": self.facteur_partage_charge,
                    "facteur_securite_etancheite": self.facteur_securite_etancheite,
                })

                if self.aire_resistante_vis_m2 is not None:
                    As = _req_pos("aire_resistante_vis_m2", self.aire_resistante_vis_m2)
                    sigma_vis = F_par_vis / As
                    rapport["assemblage"]["sigma_traction_vis_Pa"] = sigma_vis

                    # check admissible vis
                    Re_vis = self.limite_elastique_vis_pa
                    if Re_vis is None:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "limite_elastique_vis_pa",
                            "Vérif traction vis calculable si limite_elastique_vis_pa est fournie.",
                        )
                    else:
                        Re_v = _req_pos("limite_elastique_vis_pa", Re_vis)
                        FSv = _req_pos("facteur_securite_vis", self.facteur_securite_vis)
                        sigma_eff_vis = Re_v / FSv
                        rapport["assemblage"]["sigma_admissible_vis_eff_Pa"] = sigma_eff_vis
                        rapport["assemblage"]["marge_traction_vis"] = sigma_eff_vis / sigma_vis if sigma_vis > 0 else None
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "aire_resistante_vis_m2",
                        "Calcul traction vis possible si aire_resistante_vis_m2 (As) est fournie.",
                    )
        else:
            _push_inconnue(rapport, "partielles", "assemblage vis", "Non calculé (nb_vis non fourni).")

        # ----------------------------
        # 10) Mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CouvercleCylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# ============================================================
# Exemple rapide (à adapter) — aucune valeur “inventée”
# ============================================================
if __name__ == "__main__":
    couv = CouvercleCylindre(
        diametre_ouverture_m=0.085,      # exemple: 85 mm
        rayon_appui_m=None,              # => D/2
        pression_max_pa=15e5,            # 15 bar
        pression_externe_pa=1e5,         # si tu veux raisonner en absolu, sinon 0
        materiau_cle="acier_42cd4",      # à adapter à TA base matériaux
        mode_materiau="min",
        facteur_securite=2.0,
        limite_fleche_centre_m=0.0002,   # optionnel: 0.2 mm
        nb_vis=8,
        aire_resistante_vis_m2=None,     # si tu veux checker les vis
    )
    rep = couv.analyser(strict=False)
    print("Inconnues impossibles:", len(rep["inconnues"]["impossibles"]))
    print("Inconnues partielles:", len(rep["inconnues"]["partielles"]))
    print("Epaisseur retenue (m):", rep["dimensionnement"].get("epaisseur_retenue_m"))
