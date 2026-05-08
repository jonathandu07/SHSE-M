# backend/components/alternateur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple
import math

# ============================================================
# Imports des modules alternateur (robustes à l'arborescence)
# ============================================================

try:
    from backend.components.alternateur.modules.calcul_vitesse_angulaire import calcul_vitesse_angulaire
    from backend.components.alternateur.modules.calcul_frequence_synchrone import calcul_frequence_synchrone
    from backend.components.alternateur.modules.calcul_fem_induite import (
        calcul_fem_induite,
        calcul_fem_induite_avec_induction,
    )
    from backend.components.alternateur.modules.calcul_puissance_electrique import (
        calcul_puissance_triphase,
        calcul_puissance_monophase,
        calcul_puissance_dc,
    )
    from backend.components.alternateur.modules.calcul_pertes_cuivre import (
        calcul_resistance_enroulement,
        calcul_pertes_cuivre_phase,
        calcul_pertes_cuivre_triphase,
    )
    from backend.components.alternateur.modules.calcul_pertes_fer import calcul_pertes_fer_steinmetz
    from backend.components.alternateur.modules.calcul_rendement_alternateur import calcul_rendement_alternateur
    from backend.components.alternateur.modules.calcul_puissance_mecanique import calcul_puissance_mecanique
    from backend.components.alternateur.modules.calcul_couple_alternateur import calcul_couple_alternateur
    from backend.components.alternateur.modules.calcul_echauffement_thermique import calcul_echauffement_thermique
except Exception:
    from backend.components.alternateur.modules.calcul_vitesse_angulaire import calcul_vitesse_angulaire
    from backend.components.alternateur.modules.calcul_frequence_synchrone import calcul_frequence_synchrone
    from backend.components.alternateur.modules.calcul_fem_induite import (
        calcul_fem_induite,
        calcul_fem_induite_avec_induction,
    )
    from backend.components.alternateur.modules.calcul_puissance_electrique import (
        calcul_puissance_triphase,
        calcul_puissance_monophase,
        calcul_puissance_dc,
    )
    from backend.components.alternateur.modules.calcul_pertes_cuivre import (
        calcul_resistance_enroulement,
        calcul_pertes_cuivre_phase,
        calcul_pertes_cuivre_triphase,
    )
    from backend.components.alternateur.modules.calcul_pertes_fer import calcul_pertes_fer_steinmetz
    from backend.components.alternateur.modules.calcul_rendement_alternateur import calcul_rendement_alternateur
    from backend.components.alternateur.modules.calcul_puissance_mecanique import calcul_puissance_mecanique
    from backend.components.alternateur.modules.calcul_couple_alternateur import calcul_couple_alternateur
    from backend.components.alternateur.modules.calcul_echauffement_thermique import calcul_echauffement_thermique

# ============================================================
# (Optionnel) import module batterie pour temps/énergie de charge
# ============================================================

try:
    from backend.components.batterie.modules.calcul_temps_charge import calcul_temps_charge
except Exception:
    try:
        from backend.components.batterie.modules.calcul_temps_charge import calcul_temps_charge  # type: ignore
    except Exception:
        calcul_temps_charge = None  # type: ignore


# ============================================================
# Imports des pièces
# ============================================================
try:
    from backend.components.alternateur.pieces.rotor import Rotor
    from backend.components.alternateur.pieces.stator import Stator
    from backend.components.alternateur.pieces.arbre_alternateur import ArbreAlternateur
    from backend.components.alternateur.pieces.carter_alternateur import CarterAlternateur
except Exception:
    Rotor = Any
    Stator = Any
    ArbreAlternateur = Any
    CarterAlternateur = Any

# ============================================================
# Types & helpers
# ============================================================

ModeElectrique = Literal["triphase_ac", "monophase_ac", "dc"]
Connexion = Literal["Y", "Delta"]
ModePoles = Literal["poles", "pair_poles", "pole_pairs"]


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


def _req_eta(name: str, eta: Any) -> float:
    v = _req_finite(name, eta)
    if not (0.0 < v <= 1.0):
        raise ValueError(f"{name} doit être dans (0,1] (reçu: {v}).")
    return v


def _push_inconnue(rep: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rep["inconnues"][cat].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rep: Dict[str, Any]) -> None:
    def dedup(lst: list[dict]) -> list[dict]:
        seen: set[Tuple[str, str]] = set()
        out: list[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rep["inconnues"]["impossibles"] = dedup(rep["inconnues"]["impossibles"])
    rep["inconnues"]["partielles"] = dedup(rep["inconnues"]["partielles"])


def _phase_line_from_connexion(connexion: Connexion) -> Tuple[float, float]:
    """
    Renvoie (k_Vll_from_Vph, k_Iph_from_Il) pour une machine triphasée:
      - Y     : V_LL = sqrt(3)*V_ph ; I_ph = I_L
      - Delta : V_LL = V_ph         ; I_ph = I_L/sqrt(3)
    """
    if connexion == "Y":
        return (math.sqrt(3.0), 1.0)
    return (1.0, 1.0 / math.sqrt(3.0))


def _safe_get_attr(obj: Any, attr: str) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return None


# ============================================================
# Alternateur
# ============================================================

@dataclass(frozen=True)
class Alternateur:
    """
    Alternateur "calcul-only" :
    - calcule tout ce qui est déterminable à partir des entrées fournies,
    - n'invente jamais (toute donnée techno manquante => inconnue),
    - peut s'intégrer à des objets 'moteur' et 'batterie' via lecture d'attributs.
    """

    # --- Cinématique / topologie ---
    nombre_poles: Optional[int] = None
    mode_poles: ModePoles = "poles"
    connexion: Connexion = "Y"

    # --- Enroulement / magnétisme (FEM) ---
    nombre_spires_serie: Optional[int] = None
    facteur_enroulement: Optional[float] = None  # k_w
    flux_max_pole_wb: Optional[float] = None     # Phi_max

    # Alternative flux ~ B_g * A_p
    induction_gap_t: Optional[float] = None
    aire_pole_m2: Optional[float] = None

    # --- Cuivre (R_phase) ---
    resistance_phase_ohm: Optional[float] = None
    resistivite_ohm_m: Optional[float] = None
    longueur_fil_m: Optional[float] = None
    section_fil_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_ref_c: float = 20.0
    coef_temperature: float = 0.00393

    # --- Fer (Steinmetz) ---
    k_h: Optional[float] = None
    k_e: Optional[float] = None
    exposant_steinmetz: Optional[float] = None
    induction_max_t: Optional[float] = None
    eddy_freq_exp: float = 2.0
    eddy_induction_exp: float = 2.0
    masse_fer_kg: Optional[float] = None
    volume_fer_m3: Optional[float] = None

    # --- Pertes fixes ---
    pertes_fixes_w: float = 0.0

    # --- Thermique ---
    resistance_thermique_k_w: Optional[float] = None
    offset_temperature: float = 0.0

    # --- Pièces (optionnel) ---
    piece_rotor: Optional[Rotor] = None
    piece_stator: Optional[Stator] = None
    piece_arbre: Optional[ArbreAlternateur] = None
    piece_carter: Optional[CarterAlternateur] = None

    clamp_non_negative: bool = True

    def __post_init__(self) -> None:
        _req_finite("pertes_fixes_w", self.pertes_fixes_w)
        _req_finite("offset_temperature", self.offset_temperature)

        if self.nombre_poles is not None:
            if not isinstance(self.nombre_poles, int) or self.nombre_poles <= 0:
                raise ValueError("nombre_poles doit être un entier > 0 si fourni.")

        if self.nombre_spires_serie is not None:
            if not isinstance(self.nombre_spires_serie, int) or self.nombre_spires_serie < 0:
                raise ValueError("nombre_spires_serie doit être un entier >= 0 si fourni.")

        if self.resistance_phase_ohm is not None:
            _req_pos("resistance_phase_ohm", self.resistance_phase_ohm, strictly=False)

        if self.resistance_thermique_k_w is not None:
            _req_finite("resistance_thermique_k_w", self.resistance_thermique_k_w)

        if self.masse_fer_kg is not None and self.volume_fer_m3 is not None:
            raise ValueError("Fournis soit masse_fer_kg, soit volume_fer_m3, pas les deux.")

    # ------------------------------------------------------------
    # Analyse d'un point (machine seule)
    # ------------------------------------------------------------
    def analyser_point_de_fonctionnement(
        self,
        *,
        # Vitesse (au choix)
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        # Mode & grandeurs électriques si mesurées
        mode_electrique: ModeElectrique = "triphase_ac",
        tension_v: Optional[float] = None,
        courant_a: Optional[float] = None,
        facteur_puissance: float = 1.0,
        entree_puissance_ac: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
        courant_est_ligne: bool = True,
        # Cible de puissance (prioritaire)
        puissance_electrique_cible_w: Optional[float] = None,
        # IMPORTANT (anti-invention) :
        # - pertes cuivre nécessitent I_phase_rms stator.
        #   En AC tri: on peut le déduire selon connexion/courant_est_ligne.
        #   En DC: impossible sans modèle de redressement => fournir explicitement si tu veux calculer P_cuivre.
        courant_phase_rms_stator_a: Optional[float] = None,
        # Mono/charges partielles: si tu utilises une seule phase (ou 2), ne pas inventer -> fournir nb_phases_chargees
        nb_phases_chargees: Optional[int] = None,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "entrees": {},
            "resultats": {},
            "pertes": {},
            "thermique": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1) Vitesse
        omega: Optional[float] = None
        rpm: Optional[float] = None

        if vitesse_angulaire_rad_s is not None:
            omega = calcul_vitesse_angulaire(
                float(vitesse_angulaire_rad_s),
                input_unite="rad_s",
                allow_negative=True,
                clamp_non_negative=False,
            )
            rpm = (omega * 60.0) / (2.0 * math.pi)
        elif vitesse_rotation_rpm is not None:
            rpm = _req_finite("vitesse_rotation_rpm", vitesse_rotation_rpm)
            omega = calcul_vitesse_angulaire(
                rpm,
                input_unite="rpm",
                allow_negative=True,
                clamp_non_negative=False,
            )
        else:
            _push_inconnue(rep, "impossibles", "vitesse (rpm/omega)", "Requise pour fréquence, couple, P_mécanique.")
        rep["entrees"]["rpm"] = rpm
        rep["entrees"]["omega_rad_s"] = omega

        # 2) Fréquence synchrone
        frequence_hz: Optional[float] = None
        if rpm is not None and self.nombre_poles is not None:
            frequence_hz = calcul_frequence_synchrone(
                vitesse_rotation_tr_min=rpm,
                nombre_poles=self.nombre_poles,
                mode_poles=self.mode_poles,
                clamp_non_negative=True,
            )
        else:
            if self.nombre_poles is None:
                _push_inconnue(rep, "impossibles", "nombre_poles", "Requis pour calculer f_synchrone depuis rpm.")
            if rpm is None:
                _push_inconnue(rep, "impossibles", "rpm", "Requis pour calculer f_synchrone.")
        rep["resultats"]["frequence_hz"] = frequence_hz

        # 3) FEM induite (phase) + conversions (ligne)
        fem_phase_v: Optional[float] = None
        fem_phase_v_via_BA: Optional[float] = None
        fem_ll_v: Optional[float] = None
        fem_ll_v_via_BA: Optional[float] = None

        k_vll, _ = _phase_line_from_connexion(self.connexion)

        if (
            frequence_hz is not None
            and self.nombre_spires_serie is not None
            and self.facteur_enroulement is not None
            and self.flux_max_pole_wb is not None
        ):
            fem_phase_v = calcul_fem_induite(
                frequence=frequence_hz,
                nombre_spires_serie=self.nombre_spires_serie,
                flux_max_pole=self.flux_max_pole_wb,
                facteur_enroulement=self.facteur_enroulement,
                clamp_non_negative=True,
            )
            fem_ll_v = k_vll * float(fem_phase_v)
        else:
            _push_inconnue(
                rep,
                "partielles",
                "FEM induite (flux direct)",
                "Calculable si f, N, k_w, Phi_max sont fournis.",
            )

        if (
            frequence_hz is not None
            and self.nombre_spires_serie is not None
            and self.facteur_enroulement is not None
            and self.induction_gap_t is not None
            and self.aire_pole_m2 is not None
        ):
            fem_phase_v_via_BA = calcul_fem_induite_avec_induction(
                frequence=frequence_hz,
                nombre_spires_serie=self.nombre_spires_serie,
                induction_gap=self.induction_gap_t,
                aire_pole=self.aire_pole_m2,
                facteur_enroulement=self.facteur_enroulement,
                clamp_non_negative=True,
                flux_model="abs(B)*A",
            )
            fem_ll_v_via_BA = k_vll * float(fem_phase_v_via_BA)
        else:
            _push_inconnue(
                rep,
                "partielles",
                "FEM induite (via B*A)",
                "Calculable si f, N, k_w, B_g, A_p sont fournis.",
            )

        rep["resultats"]["fem_phase_v"] = fem_phase_v
        rep["resultats"]["fem_ligne_ligne_v"] = fem_ll_v
        rep["resultats"]["fem_phase_v_via_BA"] = fem_phase_v_via_BA
        rep["resultats"]["fem_ligne_ligne_v_via_BA"] = fem_ll_v_via_BA

        # 4) Puissance électrique utile P_out
        P_out: Optional[float] = None
        details_puissance: Optional[Dict[str, float]] = None

        if puissance_electrique_cible_w is not None:
            P_out = _req_finite("puissance_electrique_cible_w", puissance_electrique_cible_w)
            rep["notes_modele"].append("P_out imposée par cible (prioritaire).")
        else:
            if tension_v is None or courant_a is None:
                _push_inconnue(rep, "impossibles", "P_out", "Fournir puissance_electrique_cible_w OU (tension_v et courant_a).")
            else:
                V = _req_finite("tension_v", tension_v)
                I = _req_finite("courant_a", courant_a)

                if mode_electrique == "triphase_ac":
                    d = calcul_puissance_triphase(
                        tension_composee=V,
                        courant_ligne=I,
                        facteur_puissance=facteur_puissance,
                        entree=entree_puissance_ac,
                        connexion=self.connexion,
                        return_details=True,
                        clamp_non_negative=self.clamp_non_negative,
                    )
                    details_puissance = {k: float(v) for k, v in d.items()}  # type: ignore[union-attr]
                    P_out = float(details_puissance["P"])
                elif mode_electrique == "monophase_ac":
                    d = calcul_puissance_monophase(
                        tension=V,
                        courant=I,
                        facteur_puissance=facteur_puissance,
                        return_details=True,
                        clamp_non_negative=self.clamp_non_negative,
                    )
                    details_puissance = {k: float(v) for k, v in d.items()}  # type: ignore[union-attr]
                    P_out = float(details_puissance["P"])
                elif mode_electrique == "dc":
                    d = calcul_puissance_dc(
                        tension_dc=V,
                        courant_dc=I,
                        return_details=True,
                        clamp_non_negative=self.clamp_non_negative,
                    )
                    details_puissance = {k: float(v) for k, v in d.items()}  # type: ignore[union-attr]
                    P_out = float(details_puissance["P"])
                else:
                    raise ValueError("mode_electrique invalide.")

        rep["entrees"]["mode_electrique"] = mode_electrique
        rep["entrees"]["tension_v"] = tension_v
        rep["entrees"]["courant_a"] = courant_a
        rep["entrees"]["facteur_puissance"] = facteur_puissance
        rep["entrees"]["entree_puissance_ac"] = entree_puissance_ac
        rep["entrees"]["courant_est_ligne"] = courant_est_ligne

        rep["resultats"]["P_out_W"] = P_out
        rep["resultats"]["details_puissance"] = details_puissance

        # 5) Résistance phase (R_phase)
        R_phase: Optional[float] = None
        if self.resistance_phase_ohm is not None:
            R_phase = float(self.resistance_phase_ohm)
        else:
            if self.resistivite_ohm_m is not None and self.longueur_fil_m is not None and self.section_fil_m2 is not None:
                R_phase = calcul_resistance_enroulement(
                    resistivite=self.resistivite_ohm_m,
                    longueur_fil=self.longueur_fil_m,
                    section_fil=self.section_fil_m2,
                    temperature_c=self.temperature_c,
                    temperature_ref_c=self.temperature_ref_c,
                    coef_temperature=self.coef_temperature,
                    clamp_non_negative=True,
                )
                rep["notes_modele"].append("R_phase déduite par R=rho*L/A (avec correction température si fournie).")
            else:
                _push_inconnue(
                    rep,
                    "partielles",
                    "R_phase",
                    "Fournir resistance_phase_ohm OU (resistivite_ohm_m, longueur_fil_m, section_fil_m2).",
                )
        rep["resultats"]["R_phase_ohm"] = R_phase

        # 6) Pertes cuivre (sans inventer le courant stator)
        P_cu_total: Optional[float] = None
        cuivre_details: Dict[str, Any] = {}

        I_phase_rms: Optional[float] = None

        if courant_phase_rms_stator_a is not None:
            I_phase_rms = _req_pos("courant_phase_rms_stator_a", courant_phase_rms_stator_a, strictly=False)
            rep["notes_modele"].append("I_phase_rms stator fourni explicitement (prioritaire).")
        else:
            if mode_electrique == "triphase_ac" and courant_a is not None:
                I_in = _req_pos("courant_a", courant_a, strictly=False)
                if courant_est_ligne:
                    _, k_iph_from_il = _phase_line_from_connexion(self.connexion)
                    I_phase_rms = I_in * k_iph_from_il
                    cuivre_details["I_ligne_rms_A"] = I_in
                    cuivre_details["I_phase_rms_A"] = I_phase_rms
                else:
                    I_phase_rms = I_in
                    cuivre_details["I_phase_rms_A"] = I_phase_rms
            elif mode_electrique == "monophase_ac":
                # Impossible de déduire combien de phases du stator sont chargées sans info.
                if courant_a is not None and nb_phases_chargees is not None:
                    nph = int(nb_phases_chargees)
                    if nph <= 0 or nph > 3:
                        raise ValueError("nb_phases_chargees doit être dans {1,2,3}.")
                    I_phase_rms = _req_pos("courant_a", courant_a, strictly=False)
                    cuivre_details["nb_phases_chargees"] = nph
                    cuivre_details["I_phase_rms_A"] = I_phase_rms
                else:
                    _push_inconnue(
                        rep,
                        "partielles",
                        "Pertes cuivre (monophasé)",
                        "Fournir nb_phases_chargees et un courant de phase RMS (courant_a interprété phase).",
                    )
            elif mode_electrique == "dc":
                _push_inconnue(
                    rep,
                    "partielles",
                    "Pertes cuivre (DC)",
                    "Impossible de déduire I_phase RMS stator depuis I_DC sans modèle de redressement. Fournir courant_phase_rms_stator_a.",
                )

        if R_phase is not None and I_phase_rms is not None:
            if mode_electrique == "triphase_ac":
                # Triphasé: on utilise directement le module triphasé
                P_cu_total = calcul_pertes_cuivre_triphase(
                    courant_phase=I_phase_rms,
                    resistance_phase=R_phase,
                    courant_type="rms",
                    connexion=self.connexion,
                    courant_est_ligne=False,  # on passe déjà I_phase
                    clamp_non_negative=True,
                )
                cuivre_details["P_cu_triphase_W"] = float(P_cu_total)
            elif mode_electrique == "monophase_ac":
                nph = int(nb_phases_chargees) if nb_phases_chargees is not None else 1
                P_cu_phase = calcul_pertes_cuivre_phase(
                    courant=I_phase_rms,
                    resistance=R_phase,
                    courant_type="rms",
                    clamp_non_negative=True,
                )
                P_cu_total = float(nph) * float(P_cu_phase)
                cuivre_details["P_cu_phase_W"] = float(P_cu_phase)
                cuivre_details["P_cu_total_W"] = float(P_cu_total)
            else:
                # DC: si I_phase fourni, on peut calculer pareil que triphasé (stator triphasé)
                P_cu_total = calcul_pertes_cuivre_triphase(
                    courant_phase=I_phase_rms,
                    resistance_phase=R_phase,
                    courant_type="rms",
                    connexion=self.connexion,
                    courant_est_ligne=False,
                    clamp_non_negative=True,
                )
                cuivre_details["P_cu_triphase_equiv_W"] = float(P_cu_total)

        rep["pertes"]["P_cuivre_W"] = P_cu_total
        rep["pertes"]["details_cuivre"] = cuivre_details

        # 7) Pertes fer (Steinmetz)
        P_fe_total: Optional[float] = None
        P_fe_detail: Optional[Dict[str, float]] = None

        if (
            frequence_hz is not None
            and self.k_h is not None
            and self.k_e is not None
            and self.exposant_steinmetz is not None
            and self.induction_max_t is not None
        ):
            dfe = calcul_pertes_fer_steinmetz(
                k_h=self.k_h,
                frequence=frequence_hz,
                induction_max=self.induction_max_t,
                exposant_steinmetz=self.exposant_steinmetz,
                k_e=self.k_e,
                eddy_freq_exp=self.eddy_freq_exp,
                eddy_induction_exp=self.eddy_induction_exp,
                masse_kg=self.masse_fer_kg,
                volume_m3=self.volume_fer_m3,
                return_details=True,
                clamp_non_negative=True,
            )
            P_fe_total = float(dfe["P_total"])  # type: ignore[index]
            P_fe_detail = {k: float(v) for k, v in dfe.items()}  # type: ignore[union-attr]
        else:
            _push_inconnue(
                rep,
                "impossibles",
                "Pertes fer (Steinmetz)",
                "Impossible sans calibration matériau (k_h,k_e,alpha) et sans Bmax + fréquence.",
            )

        rep["pertes"]["P_fer_W"] = P_fe_total
        rep["pertes"]["details_fer"] = P_fe_detail

        # 8) Rendement (à partir des pertes réellement calculées, pas d'invention)
        pertes_list: list[float] = []
        if P_cu_total is not None:
            pertes_list.append(float(P_cu_total))
        if P_fe_total is not None:
            pertes_list.append(float(P_fe_total))
        if float(self.pertes_fixes_w) != 0.0:
            pertes_list.append(float(self.pertes_fixes_w))

        eta_total: Optional[float] = None
        eta_detail: Optional[Dict[str, float]] = None

        if P_out is not None and len(pertes_list) > 0:
            deta = calcul_rendement_alternateur(
                puissance_utile_out=float(P_out),
                liste_pertes=pertes_list,
                clamp_0_1=True,
                return_details=True,
            )
            eta_total = float(deta["eta"])  # type: ignore[index]
            eta_detail = {k: float(v) for k, v in deta.items()}  # type: ignore[union-attr]
        else:
            if P_out is None:
                _push_inconnue(rep, "impossibles", "rendement", "Impossible sans P_out.")
            else:
                _push_inconnue(rep, "partielles", "rendement", "Calculable si au moins une perte est déterminée (cuivre/fer/fixes).")

        rep["resultats"]["eta_total"] = eta_total
        rep["resultats"]["details_rendement"] = eta_detail

        # 9) Puissance méca & couple
        P_mec: Optional[float] = None
        couple_nm: Optional[float] = None

        if P_out is not None and eta_total is not None:
            P_mec = calcul_puissance_mecanique(
                puissance_electrique_cible=float(P_out),
                rendement_alternateur=float(eta_total),
                pertes_fixes_w=0.0,  # déjà inclus via liste_pertes si ajouté
                clamp_non_negative=self.clamp_non_negative,
                mode_signe="abs" if self.clamp_non_negative else "conserver",
            )

            if omega is not None and abs(omega) > 1e-12:
                couple_nm = calcul_couple_alternateur(
                    puissance_electrique_cible=float(P_out),
                    rendement_alternateur=float(eta_total),
                    vitesse_angulaire=float(omega),
                    pertes_fixes_w=0.0,
                    clamp_non_negative=self.clamp_non_negative,
                    mode_signe="abs_omega" if self.clamp_non_negative else "conserver",
                )
            else:
                _push_inconnue(rep, "impossibles", "couple", "Impossible sans omega (rad/s).")
        else:
            if P_out is None:
                _push_inconnue(rep, "impossibles", "P_mec/couple", "Impossible sans P_out.")
            if eta_total is None:
                _push_inconnue(rep, "impossibles", "P_mec/couple", "Impossible sans rendement (donc sans pertes calculées).")

        rep["resultats"]["P_mecanique_W"] = P_mec
        rep["resultats"]["couple_mecanique_Nm"] = couple_nm

        # 10) Thermique (DeltaT)
        P_pertes_tot: Optional[float] = float(sum(pertes_list)) if len(pertes_list) > 0 else None
        rep["pertes"]["P_pertes_totales_W"] = P_pertes_tot

        delta_t: Optional[float] = None
        if P_pertes_tot is not None and self.resistance_thermique_k_w is not None:
            delta_t = calcul_echauffement_thermique(
                puissance_pertes_totale=float(P_pertes_tot),
                resistance_thermique=float(self.resistance_thermique_k_w),
                offset_temperature=float(self.offset_temperature),
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(rep, "partielles", "échauffement (DeltaT)", "Calculable si Rth et pertes totales sont déterminées.")

        rep["thermique"]["deltaT_K_ou_C"] = delta_t

        rep["entrees"]["nb_phases_chargees"] = nb_phases_chargees
        rep["entrees"]["courant_phase_rms_stator_a"] = courant_phase_rms_stator_a

        # ============================================================
        # 11) Analyse des pièces (si définies)
        # ============================================================
        pieces_rapport = {}
        for nom, piece in [
            ("rotor", self.piece_rotor),
            ("stator", self.piece_stator),
            ("arbre", self.piece_arbre),
            ("carter", self.piece_carter),
        ]:
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces_rapport[nom] = piece.analyser()
                except Exception as e:
                    pieces_rapport[nom] = {"erreur": str(e)}
        
        if pieces_rapport:
            rep["pieces"] = pieces_rapport

        _dedup_inconnues(rep)
        return rep

    # ------------------------------------------------------------
    # Intégration: utilisateur donne P (W) -> on calcule le bus DC
    # + on exploite les données moteur/batterie si présentes.
    # ------------------------------------------------------------
    def analyser_pour_bus_dc(
        self,
        *,
        puissance_bus_dc_w: float,
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        # Si non fourni, on tente batterie.tension_charge_v -> batterie.tension_nominale_v -> moteur.tension_bus_v
        tension_bus_dc_v: Optional[float] = None,
        # Objets externes (optionnels) : on lit des attributs sans supposer leurs classes
        batterie: Any = None,
        moteur: Any = None,
        # Si tu veux un temps de charge: énergie utile à restaurer (kWh) (à fournir explicitement)
        energie_a_recharger_kwh: Optional[float] = None,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "entrees": {},
            "bus_dc": {},
            "alternateur": {},
            "integration": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        Pdc = _req_finite("puissance_bus_dc_w", puissance_bus_dc_w)
        rep["entrees"]["puissance_bus_dc_w"] = Pdc

        # 1) Détermination tension bus DC depuis batterie/moteur si possible
        Vdc: Optional[float] = None
        if tension_bus_dc_v is not None:
            Vdc = _req_pos("tension_bus_dc_v", tension_bus_dc_v, strictly=True)
            rep["notes_modele"].append("tension_bus_dc_v fournie explicitement (prioritaire).")
        else:
            # Batterie: tension_charge_v puis tension_nominale_v
            V_batt_chg = _safe_get_attr(batterie, "tension_charge_v")
            V_batt_nom = _safe_get_attr(batterie, "tension_nominale_v")
            V_mot = _safe_get_attr(moteur, "tension_bus_v")

            if V_batt_chg is not None and _is_finite(V_batt_chg) and float(V_batt_chg) > 0:
                Vdc = float(V_batt_chg)
                rep["notes_modele"].append("tension bus DC déduite de batterie.tension_charge_v.")
            elif V_batt_nom is not None and _is_finite(V_batt_nom) and float(V_batt_nom) > 0:
                Vdc = float(V_batt_nom)
                rep["notes_modele"].append("tension bus DC déduite de batterie.tension_nominale_v.")
            elif V_mot is not None and _is_finite(V_mot) and float(V_mot) > 0:
                Vdc = float(V_mot)
                rep["notes_modele"].append("tension bus DC déduite de moteur.tension_bus_v.")
            else:
                _push_inconnue(
                    rep,
                    "impossibles",
                    "tension bus DC",
                    "Fournir tension_bus_dc_v ou renseigner batterie.(tension_charge_v/tension_nominale_v) ou moteur.tension_bus_v.",
                )

        rep["bus_dc"]["tension_v"] = Vdc

        # 2) Courant DC requis
        Idc: Optional[float] = None
        if Vdc is not None:
            # P = V*I => I = P/V
            Idc = Pdc / Vdc if abs(Vdc) > 1e-15 else None
        else:
            _push_inconnue(rep, "impossibles", "courant bus DC", "Impossible sans tension bus DC.")
        rep["bus_dc"]["courant_a"] = Idc
        rep["bus_dc"]["puissance_w"] = Pdc

        # 3) Vérifs contraintes moteur/batterie (sans hypothèses)
        # Moteur: courant_max_a, puissance_max_w (si existent)
        Imax = _safe_get_attr(moteur, "courant_max_a")
        Pmax_m = _safe_get_attr(moteur, "puissance_max_w")
        if Idc is not None and Imax is not None and _is_finite(Imax) and float(Imax) > 0:
            rep["integration"]["moteur_courant_max_a"] = float(Imax)
            rep["integration"]["moteur_courant_ok"] = bool(abs(Idc) <= float(Imax) + 1e-12)
        if Pmax_m is not None and _is_finite(Pmax_m) and float(Pmax_m) > 0:
            rep["integration"]["moteur_puissance_max_w"] = float(Pmax_m)
            rep["integration"]["moteur_puissance_ok"] = bool(abs(Pdc) <= float(Pmax_m) + 1e-12)

        # Batterie: puissance_charge_kw (si existe) limite côté chargeur (si ton objet Batterie l'a)
        Pchg_kw = _safe_get_attr(batterie, "puissance_charge_kw")
        if Pchg_kw is not None and _is_finite(Pchg_kw) and float(Pchg_kw) > 0:
            Pchg_w = float(Pchg_kw) * 1000.0
            rep["integration"]["batterie_puissance_charge_max_w"] = Pchg_w
            # On ne présume pas du signe: si Pdc>0 = charge
            rep["integration"]["batterie_puissance_charge_ok"] = bool(Pdc <= Pchg_w + 1e-12) if Pdc >= 0 else True

        # 4) Analyse alternateur (mode DC). IMPORTANT: pertes cuivre/fer ne sont calculées
        #    que si leurs entrées sont disponibles => pas d'invention.
        #    Ici, on passe Vdc/Idc pour "P_out", mais P_cuivre dépend du courant stator:
        #    on ne l'invente pas (courant_phase_rms_stator_a absent => P_cuivre restera inconnue).
        alt = self.analyser_point_de_fonctionnement(
            vitesse_rotation_rpm=vitesse_rotation_rpm,
            vitesse_angulaire_rad_s=vitesse_angulaire_rad_s,
            mode_electrique="dc",
            tension_v=Vdc,
            courant_a=Idc,
            puissance_electrique_cible_w=None,  # on laisse le module calculer P=V*I (si V/I connus)
            courant_phase_rms_stator_a=None,    # sinon, il faudra fournir explicitement
        )
        rep["alternateur"] = alt

        # 5) Temps de charge (si énergie à recharger connue + module dispo)
        t_h: Optional[float] = None
        if energie_a_recharger_kwh is not None:
            E = _req_pos("energie_a_recharger_kwh", energie_a_recharger_kwh, strictly=False)
            if calcul_temps_charge is None:
                _push_inconnue(rep, "partielles", "temps de charge", "Module calcul_temps_charge indisponible/import impossible.")
            else:
                if Pdc <= 0:
                    _push_inconnue(rep, "impossibles", "temps de charge", "Puissance DC <= 0 : pas une charge.")
                else:
                    # rendement_charge si présent sur l'objet batterie, sinon inconnue
                    eta_chg = _safe_get_attr(batterie, "rendement_charge")
                    if eta_chg is None:
                        _push_inconnue(rep, "partielles", "temps de charge", "Fournir batterie.rendement_charge (0..1).")
                    else:
                        eta = _req_eta("batterie.rendement_charge", eta_chg)
                        t_h = float(calcul_temps_charge(E, Pdc / 1000.0, eta))
        rep["integration"]["temps_charge_h"] = t_h

        rep["entrees"].update(
            {
                "vitesse_rotation_rpm": vitesse_rotation_rpm,
                "vitesse_angulaire_rad_s": vitesse_angulaire_rad_s,
                "tension_bus_dc_v": tension_bus_dc_v,
                "energie_a_recharger_kwh": energie_a_recharger_kwh,
            }
        )

        _dedup_inconnues(rep)
        return rep
