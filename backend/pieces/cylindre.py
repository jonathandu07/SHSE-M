# backend/pieces/cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
import math

# ============================================================
# Imports projet (avec fallbacks)
# ============================================================

# --- Cylindrée ---
try:
    from backend.modules.moteur_thermique.calcul_cylindree import calcul_cylindree_unitaire
except Exception:  # pragma: no cover
    def calcul_cylindree_unitaire(*, alesage_m: float, course_m: float, allow_zero: bool = False, return_details: bool = False) -> float:
        if alesage_m <= 0 or course_m <= 0:
            raise ValueError("alesage_m et course_m doivent être > 0")
        return (math.pi * (alesage_m ** 2) / 4.0) * course_m

# --- Epaisseur cylindre ---
try:
    from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import (
        calcul_epaisseur_cylindre_mince,
        calcul_epaisseur_cylindre_lame,
    )
except Exception:  # pragma: no cover
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
        # Modèle paroi mince (Barlow) : sigma_theta ~= (p * ri) / t
        if rayon_interne_m <= 0 or contrainte_admissible_pa <= 0 or facteur_securite <= 0:
            raise ValueError("rayon_interne_m, contrainte_admissible_pa, facteur_securite doivent être > 0")
        p = abs(float(pression_pa))
        sigma_eff = contrainte_admissible_pa / facteur_securite
        if sigma_eff <= 0:
            raise ValueError("Contrainte admissible effective <= 0")
        t = (p * rayon_interne_m) / sigma_eff
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
        # Cylindre épais (Lamé) avec p_ext=0 (fallback historique)
        ri = float(rayon_interne_m)
        if ri <= 0 or contrainte_admissible_pa <= 0 or facteur_securite <= 0:
            raise ValueError("rayon_interne_m, contrainte_admissible_pa, facteur_securite doivent être > 0")
        p = abs(float(pression_interne_pa))
        sigma_eff = contrainte_admissible_pa / facteur_securite
        if sigma_eff <= p:
            raise ValueError("sigma_eff doit être > pression_interne_pa pour Lamé (sinon épaisseur infinie).")
        ro2 = ((sigma_eff + p) / (sigma_eff - p)) * (ri ** 2)
        ro = math.sqrt(ro2)
        t = ro - ri
        return max(0.0, t) if clamp_non_negative else t

# --- Matériaux (réduction d'inconnues) ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None

# --- Fluides (optionnel : calcul h interne/externe) ---
try:
    from backend.ensemble.eau import etat_eau_pure, etat_eau_salee, etat_antigel
except Exception:  # pragma: no cover
    etat_eau_pure = etat_eau_salee = etat_antigel = None  # type: ignore

try:
    # IMPORTANT : dans ton air.py actuel, air_state prend altitude_m + temperature_offset_K (pas p_Pa direct)
    from backend.ensemble.air import air_state, isa_dry_temperature_pressure
except Exception:  # pragma: no cover
    air_state = None  # type: ignore
    isa_dry_temperature_pressure = None  # type: ignore


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

def _von_mises_3d(s1: float, s2: float, s3: float) -> float:
    # VM = sqrt(0.5*((s1-s2)^2 + (s2-s3)^2 + (s3-s1)^2))
    return math.sqrt(0.5 * ((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2))


# ============================================================
# Convection interne/externe (optionnelle) : calcul h
# ============================================================

def _nu_laminaire_tube(*, condition_paroi: Literal["T_constante", "q_constante"]) -> float:
    # Écoulement laminaire pleinement développé, tube circulaire :
    # - paroi à température constante : Nu = 3.66
    # - flux thermique constant : Nu = 4.36
    return 3.66 if condition_paroi == "T_constante" else 4.36

def _nu_dittus_boelter(Re: float, Pr: float, chauffage_fluide: bool) -> float:
    # Dittus–Boelter (turbulent, Re ~> 1e4, 0.7<Pr<160)
    n = 0.4 if chauffage_fluide else 0.3
    return 0.023 * (Re ** 0.8) * (Pr ** n)

def _f_darcy_blasius(Re: float) -> float:
    # Blasius lisse : f = 0.3164/Re^0.25 (Re ~ 4e3..1e5+)
    return 0.3164 / (Re ** 0.25)

def _nu_gnielinski(Re: float, Pr: float, f_darcy: float) -> float:
    # Gnielinski (≈ 3e3 < Re < 5e6, 0.5 < Pr < 2000)
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
    """
    h [W/m²/K] dans un tube circulaire.

    - Aucune valeur inventée : tu dois fournir soit les propriétés fluide, soit une EntreeConvectionTube
      (qui les déduit via backend.ensemble.air/eau).
    - La corrélation (Nu) est un choix d’ingénierie : paramètre 'modele'.
    """
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
    """
    Spécifie un cas d'écoulement interne dans un tube, pour calculer h.
    Utilisé uniquement si h_interne_w_m2_k / h_externe_w_m2_k n'est pas fourni.

    Note air :
    - Ton backend.ensemble.air.air_state ne prend pas p_Pa directement.
      Ici, on déduit temperature_offset_K depuis T_K et l'ISA à altitude_m.
      p_Pa (entrée) est conservé à titre informatif.
    """
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

    # Choix corrélation
    modele: Literal["auto", "laminaire", "dittus_boelter", "gnielinski"] = "auto"
    condition_paroi: Literal["T_constante", "q_constante"] = "T_constante"
    chauffage_fluide: bool = True


def _etat_fluide_pour_convection(ent: EntreeConvectionTube) -> Dict[str, float]:
    if ent.fluide == "air":
        if air_state is None:
            raise RuntimeError("backend.ensemble.air.air_state indisponible.")
        if isa_dry_temperature_pressure is None:
            raise RuntimeError("backend.ensemble.air.isa_dry_temperature_pressure indisponible (nécessaire pour déduire temperature_offset_K).")

        altitude = float(ent.altitude_m)
        T_isa, p_isa = isa_dry_temperature_pressure(altitude_m=altitude)
        T_ent = float(ent.T_K)

        # air_state(altitude_m, temperature_offset_K, RH, co2_ppm)
        temperature_offset_K = T_ent - float(T_isa)

        st = air_state(
            altitude_m=altitude,
            temperature_offset_K=temperature_offset_K,
            RH=float(ent.RH),
            co2_ppm=float(ent.co2_ppm),
        )
        # ent.p_Pa n'est pas appliqué (air_state ne permet pas l'override pression).
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
        return {"rho": float(st.rho_kg_m3), "cp": float(st.cp_J_kg_K), "mu": float(st.mu_Pa_s), "k": float(st.k_W_m_K), "T_K": float(ent.T_K), "p_Pa": float(ent.p_Pa)}

    if ent.fluide == "eau_salee":
        if etat_eau_salee is None:
            raise RuntimeError("backend.ensemble.eau.etat_eau_salee indisponible.")
        st = etat_eau_salee(float(ent.T_K), float(ent.p_Pa), float(ent.salinite_g_kg))
        return {"rho": float(st.rho_kg_m3), "cp": float(st.cp_J_kg_K), "mu": float(st.mu_Pa_s), "k": float(st.k_W_m_K), "T_K": float(ent.T_K), "p_Pa": float(ent.p_Pa)}

    if ent.fluide == "antigel":
        if etat_antigel is None:
            raise RuntimeError("backend.ensemble.eau.etat_antigel indisponible.")
        st = etat_antigel(
            float(ent.T_K),
            float(ent.p_Pa),
            float(ent.fraction_massique_glycol),
            type_glycol=str(ent.type_glycol),
        )
        return {"rho": float(st.rho_kg_m3), "cp": float(st.cp_J_kg_K), "mu": float(st.mu_Pa_s), "k": float(st.k_W_m_K), "T_K": float(ent.T_K), "p_Pa": float(ent.p_Pa)}

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
    # On conserve, si disponibles, T/p effectivement utilisés (utile pour debug, sans “inventer”)
    if "T_K" in props:
        res["T_K_utilise"] = float(props["T_K"])
    if "p_Pa" in props:
        res["p_Pa_utilise"] = float(props["p_Pa"])
    if "p_Pa_entree" in props:
        res["p_Pa_entree"] = float(props["p_Pa_entree"])
    return res


# ============================================================
# Matériau : extraction (réduit fortement les inconnues)
# ============================================================

def _materiau_resoudre(
    *,
    materiau_cle: str,
    mode: Literal["min", "typique", "max"],
) -> Dict[str, Any]:
    """
    Extrait un paquet de propriétés SI depuis backend.ensemble.materiaux.
    'mode' contrôle la sélection des intervalles.

    - Re : borne conservatrice (min global), indépendante de la section,
      si la base matériau a une courbe "par section".
    """
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
# Pièce : Cylindre
# ============================================================

@dataclass(frozen=True)
class Cylindre:
    """
    Objectif : produire un maximum de grandeurs calculées, en diminuant les inconnues.

    Rien n'est “inventé” :
    - Si une donnée n'est ni fournie ni déductible via modules, elle reste une inconnue.

    Hypothèses mécaniques utilisées :
    - dimensionnement sous pression interne nette (p_i - p_o) (paroi mince + Lamé).
    - si p_o > p_i : collapse/flambage non traité ici -> inconnue “impossible”.
    """

    # --- Géométrie (obligatoire) ---
    alesage_m: float
    course_m: float
    longueur_utile_m: float

    # --- Pressions (absolues) ---
    pression_service_pa: float
    pression_max_pa: float
    pression_externe_pa: float = 0.0

    # --- Matériau (réduction inconnues) ---
    materiau_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "min"  # min = conservateur

    # Overrides manuels (si fournis, ils priment)
    contrainte_admissible_pa: Optional[float] = None  # interprétée comme "limite matériau" avant FS
    limite_elastique_pa: Optional[float] = None       # Re
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

    # Valeurs directes (si tu veux bypass)
    h_interne_w_m2_k: Optional[float] = None
    h_externe_w_m2_k: Optional[float] = None

    # Bride (optionnel)
    epaisseur_bride_m: Optional[float] = None
    largeur_bride_m: Optional[float] = None

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
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ----------------------------
        # 1) Validation entrées
        # ----------------------------
        D = _req_pos("alesage_m", self.alesage_m)
        S = _req_pos("course_m", self.course_m)
        L = _req_pos("longueur_utile_m", self.longueur_utile_m)
        p_serv = _req_pos("pression_service_pa", self.pression_service_pa, strictly=False)
        p_max = _req_pos("pression_max_pa", self.pression_max_pa, strictly=False)
        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        FS = _req_pos("facteur_securite", self.facteur_securite)

        if p_max < p_serv:
            rapport["notes_modele"].append("pression_max_pa < pression_service_pa : dimensionnement fait sur pression_max_pa quand même.")

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

        ri = 0.5 * D
        Ai = math.pi * (ri ** 2)

        # ----------------------------
        # 2) Matériau : déduction auto
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

        # Propriétés résolues (priorité aux overrides manuels)
        densite = self.densite_kg_m3 if self.densite_kg_m3 is not None else matp.get("densite_kg_m3")
        E = self.module_young_pa if self.module_young_pa is not None else matp.get("module_young_pa")
        nu = self.coefficient_poisson if self.coefficient_poisson is not None else matp.get("poisson")
        alpha = self.coefficient_dilatation_1_k if self.coefficient_dilatation_1_k is not None else matp.get("alpha_dilatation_1_k")
        k_mat = self.conductivite_w_m_k if self.conductivite_w_m_k is not None else matp.get("conductivite_w_m_k")
        Re = self.limite_elastique_pa if self.limite_elastique_pa is not None else matp.get("limite_elastique_min_pa")

        # ----------------------------
        # 3) Contrainte admissible (obligatoire pour épaisseur)
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
        # 4) Géométrie calculée
        # ----------------------------
        V_swept = float(calcul_cylindree_unitaire(alesage_m=D, course_m=S, allow_zero=False, return_details=False))
        surface_interne_laterale = math.pi * D * L
        volume_interne_total = Ai * L

        rapport["geometrie"].update({
            "rayon_interne_m": ri,
            "aire_section_interne_m2": Ai,
            "cylindree_unitaire_m3": V_swept,
            "volume_interne_total_m3": volume_interne_total,
            "surface_interne_laterale_m2": surface_interne_laterale,
        })

        # ----------------------------
        # 5) Efforts pression
        # ----------------------------
        F_piston_service = (p_serv - p_ext) * Ai
        F_piston_max = (p_max - p_ext) * Ai
        rapport["dimensionnement"].update({
            "force_pression_piston_service_N": F_piston_service,
            "force_pression_piston_max_N": F_piston_max,
        })

        # ----------------------------
        # 6) Épaisseur : mince + Lamé (conservatif)
        # ----------------------------
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
                "p_o > p_i : dimensionnement sous pression externe (flambage/collapse) non implémenté dans ce module.",
            )
        if delta_p == 0.0 and p_i == p_o:
            rapport["notes_modele"].append("delta_p=0 : aucun effort de pression interne net. Épaisseur minimale de fabrication non traitée.")

        if sigma_adm is not None:
            # 6.1 paroi mince (Barlow)
            t_mince = float(calcul_epaisseur_cylindre_mince(
                pression_pa=delta_p,
                rayon_interne_m=ri,
                contrainte_admissible_pa=sigma_adm,
                include_longitudinale=False,
                facteur_securite=FS,
                clamp_non_negative=True,
                return_details=False,
            ))

            # 6.2 Lamé généralisé (p_o potentiellement != 0)
            # σθ(ri)= (p_i*(ri^2+ro^2) - 2*p_o*ro^2)/(ro^2-ri^2)
            # => ro^2 = ri^2*(σ + p_i)/(σ - p_i + 2*p_o), σ = sigma_eff = sigma_adm/FS
            sigma_eff = sigma_adm / FS
            denom = (sigma_eff - p_i + 2.0 * p_o)
            if denom <= 0:
                _push_inconnue(rapport, "impossibles", "épaisseur Lamé", "Pas de solution (sigma_eff - p_i + 2*p_o <= 0).")
            else:
                ro2 = (ri * ri) * (sigma_eff + p_i) / denom
                t_lame = max(0.0, math.sqrt(ro2) - ri)

            # 6.3 retenue (conservatif)
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

        # ----------------------------
        # 7) Contraintes (mince + Lamé) + Von Mises
        # ----------------------------
        if t_retenue is not None and t_retenue > 0:
            ro = ri + t_retenue
            Do = 2.0 * ro
            Di = 2.0 * ri

            # 7.1 mince (référence)
            sigma_theta_mince = (delta_p * ri) / t_retenue
            sigma_long_mince = (delta_p * ri) / (2.0 * t_retenue)
            sigma_vm_mince = math.sqrt(sigma_theta_mince**2 + sigma_long_mince**2 - sigma_theta_mince * sigma_long_mince)

            # 7.2 Lamé exact au rayon interne
            ri2 = ri * ri
            ro2 = ro * ro
            denom2 = (ro2 - ri2)
            if denom2 <= 0:
                _push_inconnue(rapport, "impossibles", "contraintes Lamé", "ro^2 - ri^2 <= 0 (géométrie invalide).")
                sigma_theta_lame_i = sigma_r_lame_i = sigma_z_lame = sigma_vm_lame_i = None
            else:
                A = (p_i * ri2 - p_o * ro2) / denom2
                B = (ri2 * ro2 * (p_i - p_o)) / denom2
                sigma_r_lame_i = A - (B / ri2)       # = -p_i si p_o=0
                sigma_theta_lame_i = A + (B / ri2)   # cerclage max
                sigma_z_lame = A                     # axial (extrémités fermées)
                sigma_vm_lame_i = _von_mises_3d(sigma_theta_lame_i, sigma_r_lame_i, sigma_z_lame)

            # marges
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

            # info : Re effectif si matériau dépend de la section (diamètre extérieur)
            if self.materiau_cle and get_materiau is not None:
                try:
                    mat = get_materiau(self.materiau_cle)
                    section_mm = Do * 1000.0
                    Re_section = mat.limite_elastique_effective_pa(mode="min", section_mm=section_mm)
                    if Re_section is not None:
                        sigma_adm2 = float(Re_section)
                        t_mince2 = float(calcul_epaisseur_cylindre_mince(
                            pression_pa=delta_p, rayon_interne_m=ri, contrainte_admissible_pa=sigma_adm2,
                            include_longitudinale=False, facteur_securite=FS, clamp_non_negative=True, return_details=False
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

        # ----------------------------
        # 8) Déformations (si E, nu, alpha, ΔT disponibles)
        # ----------------------------
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
                _push_inconnue(rapport, "partielles", "déformations sous pression", "Calculables si module_young_pa et coefficient_poisson sont connus (ou via materiau_cle).")

            if alpha is not None and self.delta_temperature_k is not None:
                a = _req_pos("coefficient_dilatation_1_k", alpha)
                dT = _req_finite("delta_temperature_k", self.delta_temperature_k)
                delta_D_th = a * D * dT
                rapport["deformations"].update({
                    "augmentation_diametre_interne_thermique_m": delta_D_th,
                    "augmentation_rayon_interne_thermique_m": 0.5 * delta_D_th,
                })
            else:
                _push_inconnue(rapport, "partielles", "dilatation thermique", "Calculable si alpha (ou materiau_cle) et delta_temperature_k sont fournis.")

        # ----------------------------
        # 9) Thermique : Rcond + convection (si possible)
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
                _push_inconnue(rapport, "partielles", "R convection interne", "Calculable si h_interne_w_m2_k est fourni (ou convection_interne).")

            if h_o is not None:
                ho = _req_pos("h_externe_w_m2_k", h_o)
                A_o = 2.0 * math.pi * ro * L
                rapport["thermique"]["R_convection_externe_K_W"] = 1.0 / (ho * A_o)
            else:
                _push_inconnue(rapport, "partielles", "R convection externe", "Calculable si h_externe_w_m2_k est fourni (ou convection_externe).")

            if "R_convection_interne_K_W" in rapport["thermique"] and "R_convection_externe_K_W" in rapport["thermique"]:
                rapport["thermique"]["R_totale_K_W"] = (
                    rapport["thermique"]["R_convection_interne_K_W"]
                    + rapport["thermique"]["R_conduction_K_W"]
                    + rapport["thermique"]["R_convection_externe_K_W"]
                )
        else:
            if k_mat is None:
                _push_inconnue(rapport, "partielles", "thermique (conduction)", "Calculable si conductivite_w_m_k est fourni (souvent via materiau_cle).")

        # ----------------------------
        # 10) Masse + inerties (tube) si densité dispo
        # ----------------------------
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
                _push_inconnue(rapport, "partielles", "masse cylindre", "Calculable si densite_kg_m3 est fournie (souvent via materiau_cle).")

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

        # ----------------------------
        # 11) Bride (optionnel) + dimensions “globales”
        # ----------------------------
        # Sans hypothèse : on ne peut pas “inventer” les brides. On calcule seulement si données fournies.
        if t_retenue is not None and t_retenue > 0:
            ro = ri + t_retenue
            rapport["geometrie"]["longueur_totale_sans_brides_m"] = L
            rapport["geometrie"]["diametre_externe_sans_brides_m"] = 2.0 * ro

        if self.epaisseur_bride_m is not None and self.largeur_bride_m is not None:
            if t_retenue is None or t_retenue <= 0:
                _push_inconnue(rapport, "partielles", "bride", "Calculable si epaisseur_retenue_m est déterminée.")
            else:
                e_b = _req_pos("epaisseur_bride_m", self.epaisseur_bride_m)
                w_b = _req_pos("largeur_bride_m", self.largeur_bride_m)
                ro = ri + t_retenue
                r_b = ro + w_b

                # Géométrie bride
                A_anneau = math.pi * (r_b * r_b - ro * ro)
                V_brides = 2.0 * A_anneau * e_b

                rapport["geometrie"]["rayon_externe_avec_brides_m"] = r_b
                rapport["geometrie"]["diametre_externe_avec_brides_m"] = 2.0 * r_b
                rapport["geometrie"]["longueur_totale_avec_brides_m"] = L + 2.0 * e_b

                rapport["masse"]["volume_brides_m3"] = V_brides
                if densite is not None:
                    rho = _req_pos("densite_kg_m3", densite)
                    rapport["masse"]["masse_brides_kg"] = rho * V_brides
                else:
                    _push_inconnue(rapport, "partielles", "masse brides", "Calculable si densite_kg_m3 est fournie (souvent via materiau_cle).")

        # ----------------------------
        # 12) Mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "Cylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport
