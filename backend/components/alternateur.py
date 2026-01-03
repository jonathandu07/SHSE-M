# backend/components/alternateur.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, Tuple
import math


# ============================================================
# Imports des modules alternateur (robustes à l'arborescence)
# ============================================================

try:
    from backend.modules.alternateur.calcul_vitesse_angulaire import calcul_vitesse_angulaire
    from backend.modules.alternateur.calcul_frequence_synchrone import calcul_frequence_synchrone
    from backend.modules.alternateur.calcul_fem_induite import (
        calcul_fem_induite,
        calcul_fem_induite_avec_induction,
    )
    from backend.modules.alternateur.calcul_puissance_electrique import (
        calcul_puissance_triphase,
        calcul_puissance_monophase,
        calcul_puissance_dc,
    )
    from backend.modules.alternateur.calcul_pertes_cuivre import (
        calcul_resistance_enroulement,
        calcul_pertes_cuivre_phase,
        calcul_pertes_cuivre_triphase,
    )
    from backend.modules.alternateur.calcul_pertes_fer import calcul_pertes_fer_steinmetz
    from backend.modules.alternateur.calcul_rendement_alternateur import calcul_rendement_alternateur
    from backend.modules.alternateur.calcul_puissance_mecanique import calcul_puissance_mecanique
    from backend.modules.alternateur.calcul_couple_alternateur import calcul_couple_alternateur
    from backend.modules.alternateur.calcul_echauffement_thermique import calcul_echauffement_thermique

except Exception:
    # Variante possible: backend\modules\alternateur\... (selon tes conventions)
    from backend.modules.alternateur.calcul_vitesse_angulaire import calcul_vitesse_angulaire
    from backend.modules.alternateur.calcul_frequence_synchrone import calcul_frequence_synchrone
    from backend.modules.alternateur.calcul_fem_induite import (
        calcul_fem_induite,
        calcul_fem_induite_avec_induction,
    )
    from backend.modules.alternateur.calcul_puissance_electrique import (
        calcul_puissance_triphase,
        calcul_puissance_monophase,
        calcul_puissance_dc,
    )
    from backend.modules.alternateur.calcul_pertes_cuivre import (
        calcul_resistance_enroulement,
        calcul_pertes_cuivre_phase,
        calcul_pertes_cuivre_triphase,
    )
    from backend.modules.alternateur.calcul_pertes_fer import calcul_pertes_fer_steinmetz
    from backend.modules.alternateur.calcul_rendement_alternateur import calcul_rendement_alternateur
    from backend.modules.alternateur.calcul_puissance_mecanique import calcul_puissance_mecanique
    from backend.modules.alternateur.calcul_couple_alternateur import calcul_couple_alternateur
    from backend.modules.alternateur.calcul_echauffement_thermique import calcul_echauffement_thermique


# ============================================================
# Helpers (validation + utilitaires)
# ============================================================

ModeElectrique = Literal["triphase_ac", "monophase_ac", "dc"]
Connexion = Literal["Y", "Delta"]
ModePoles = Literal["poles", "pair_poles", "pole_pairs"]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strictly: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strictly else x >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


def _require_eta(name: str, eta: Any) -> float:
    eta = _require_finite(name, eta)
    if not (0.0 < eta <= 1.0):
        raise ValueError(f"{name} doit être dans (0, 1] (reçu: {eta}).")
    return eta


def _safe_get(d: Dict[str, Any], k: str, default: Any = None) -> Any:
    return d.get(k, default)


# ============================================================
# Définition Alternateur (entrées minimales + options)
# ============================================================

@dataclass(frozen=True)
class Alternateur:
    """
    Objectif : produire un maximum d'infos par calcul, et ne laisser comme
    'inconnues' que ce qui est réellement impossible à déduire sans :
    - datasheet constructeur
    - mesures
    - calibration matériau / thermique

    Le script :
    - calcule fréquence, f.e.m. induite (si données magnétisme/enroulement),
    - calcule puissance électrique (AC/DC),
    - estime pertes cuivre/fer (si paramètres connus),
    - en déduit rendement, puissance méca, couple,
    - estime échauffement (si résistance thermique connue),
    - liste explicitement les inconnues restantes (impossibles / partielles).
    """

    # --- Cinématique / topologie machine ---
    nombre_poles: Optional[int] = None
    mode_poles: ModePoles = "poles"  # "poles" (P) ou "pole_pairs" (p)
    connexion: Connexion = "Y"       # utile pour quelques conversions

    # --- Enroulement / magnétisme (nécessaire pour FEM induite) ---
    nombre_spires_serie: Optional[int] = None
    facteur_enroulement: Optional[float] = None  # k_w
    flux_max_pole_wb: Optional[float] = None     # Phi_max (Wb)

    # Option alternative: flux approx par B_g * A_p
    induction_gap_t: Optional[float] = None      # B_g (T)
    aire_pole_m2: Optional[float] = None         # A_p (m²)

    # --- Pertes cuivre (résistance enroulement) ---
    resistance_phase_ohm: Optional[float] = None
    # ou bien calculable via rho, L, A
    resistivite_ohm_m: Optional[float] = None
    longueur_fil_m: Optional[float] = None
    section_fil_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_ref_c: float = 20.0
    coef_temperature: float = 0.00393

    # --- Pertes fer (modèle Steinmetz) ---
    k_h: Optional[float] = None
    k_e: Optional[float] = None
    exposant_steinmetz: Optional[float] = None
    induction_max_t: Optional[float] = None
    eddy_freq_exp: float = 2.0
    eddy_induction_exp: float = 2.0
    masse_fer_kg: Optional[float] = None
    volume_fer_m3: Optional[float] = None

    # --- Pertes fixes (frottements, excitation, ventilation, etc.) ---
    pertes_fixes_w: float = 0.0

    # --- Thermique (pour échauffement) ---
    resistance_thermique_k_w: Optional[float] = None  # K/W ou °C/W
    offset_temperature: float = 0.0

    # --- Options de comportement ---
    clamp_non_negative: bool = True

    def __post_init__(self) -> None:
        # Validations légères, sans bloquer les usages "partiels"
        _require_finite("pertes_fixes_w", self.pertes_fixes_w)
        _require_finite("offset_temperature", self.offset_temperature)

        if self.nombre_poles is not None:
            if not isinstance(self.nombre_poles, int) or self.nombre_poles <= 0:
                raise ValueError("nombre_poles doit être un entier > 0 si fourni.")

        if self.nombre_spires_serie is not None:
            if not isinstance(self.nombre_spires_serie, int) or self.nombre_spires_serie < 0:
                raise ValueError("nombre_spires_serie doit être un entier >= 0 si fourni.")

        if self.resistance_phase_ohm is not None:
            _require_positive("resistance_phase_ohm", self.resistance_phase_ohm, strictly=False)

        if self.resistance_thermique_k_w is not None:
            _require_finite("resistance_thermique_k_w", self.resistance_thermique_k_w)

        # Évite double totalisation fer masse+volume (le module refusera aussi)
        if self.masse_fer_kg is not None and self.volume_fer_m3 is not None:
            raise ValueError("Fournis soit masse_fer_kg, soit volume_fer_m3, pas les deux.")

    # ------------------------------------------------------------
    # Analyse principale : un point de fonctionnement
    # ------------------------------------------------------------
    def analyser_point_de_fonctionnement(
        self,
        *,
        # Vitesse
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        # Mode électrique + mesures
        mode_electrique: ModeElectrique = "triphase_ac",
        # Triphasé AC : VLL + IL + pf
        tension_v: Optional[float] = None,
        courant_a: Optional[float] = None,
        facteur_puissance: float = 1.0,
        # Monophasé AC : V + I + pf (on réutilise tension_v/courant_a)
        # DC : Vdc + Idc (on réutilise tension_v/courant_a)
        # Choix d'entrée pour calcul puissance tri (VLL_IL ou Vph_Iph)
        entree_puissance_ac: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
        # Courant interprété comme courant de ligne ?
        courant_est_ligne: bool = True,
        # P électrique cible (si tu ne donnes pas V/I)
        puissance_electrique_cible_w: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Retourne un rapport très détaillé.
        - Si puissance_electrique_cible_w est fourni : P_out = cette valeur (prioritaire)
        - Sinon : P_out calculée depuis (tension, courant, pf) selon le mode

        Nota :
        - sans données cuivre/fer, le rendement ne peut pas être calculé : il restera une inconnue
        - sans Rth, l'échauffement reste une inconnue
        """
        rapport: Dict[str, Any] = {
            "entrees": {},
            "resultats": {},
            "pertes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # -----------------------------
        # 1) Vitesse (omega) + fréquence synchrone
        # -----------------------------
        omega: Optional[float] = None
        rpm: Optional[float] = None

        if vitesse_angulaire_rad_s is not None:
            omega = calcul_vitesse_angulaire(
                vitesse_angulaire_rad_s,
                input_unite="rad_s",
                allow_negative=True,
                clamp_non_negative=False,
            )
            rpm = (omega * 60.0) / (2.0 * math.pi)

        elif vitesse_rotation_rpm is not None:
            rpm = _require_finite("vitesse_rotation_rpm", vitesse_rotation_rpm)
            omega = calcul_vitesse_angulaire(
                rpm,
                input_unite="rpm",
                allow_negative=True,
                clamp_non_negative=False,
            )
        else:
            rapport["inconnues"]["impossibles"].append(
                {"nom": "vitesse (rpm ou omega)", "raison": "Impossible de calculer fréquence, couple, puissance méca sans vitesse."}
            )

        rapport["entrees"]["rpm"] = rpm
        rapport["entrees"]["omega_rad_s"] = omega

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
                rapport["inconnues"]["impossibles"].append(
                    {"nom": "nombre_poles", "raison": "Nécessaire pour calculer la fréquence synchrone à partir de rpm."}
                )
            if rpm is None:
                rapport["inconnues"]["impossibles"].append(
                    {"nom": "rpm", "raison": "Nécessaire pour calculer la fréquence synchrone."}
                )

        rapport["resultats"]["frequence_hz"] = frequence_hz

        # -----------------------------
        # 2) FEM induite (si infos enroulement + flux)
        # -----------------------------
        fem_phase_v: Optional[float] = None
        fem_phase_v_via_BA: Optional[float] = None

        # Cas A : flux directement fourni
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
        else:
            # Inconnues : partiellement calculables si on remplace flux par B*A
            missing = []
            if frequence_hz is None:
                missing.append("frequence_hz")
            if self.nombre_spires_serie is None:
                missing.append("nombre_spires_serie")
            if self.facteur_enroulement is None:
                missing.append("facteur_enroulement")
            if self.flux_max_pole_wb is None:
                missing.append("flux_max_pole_wb")
            rapport["inconnues"]["partielles"].append(
                {
                    "nom": "FEM induite (flux direct)",
                    "raison": "Calculable si on fournit : " + ", ".join(missing),
                }
            )

        # Cas B : flux approximé via B_g * A_p
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
        else:
            missing = []
            if frequence_hz is None:
                missing.append("frequence_hz")
            if self.nombre_spires_serie is None:
                missing.append("nombre_spires_serie")
            if self.facteur_enroulement is None:
                missing.append("facteur_enroulement")
            if self.induction_gap_t is None:
                missing.append("induction_gap_t")
            if self.aire_pole_m2 is None:
                missing.append("aire_pole_m2")
            rapport["inconnues"]["partielles"].append(
                {
                    "nom": "FEM induite (via B*A)",
                    "raison": "Calculable si on fournit : " + ", ".join(missing),
                }
            )

        rapport["resultats"]["fem_phase_v"] = fem_phase_v
        rapport["resultats"]["fem_phase_v_via_BA"] = fem_phase_v_via_BA

        # -----------------------------
        # 3) Puissance électrique utile P_out
        # -----------------------------
        P_out: Optional[float] = None
        details_puissance: Optional[Dict[str, float]] = None

        if puissance_electrique_cible_w is not None:
            P_out = _require_finite("puissance_electrique_cible_w", puissance_electrique_cible_w)
            rapport["notes_modele"].append(
                "Puissance électrique utile fixée par cible (prioritaire sur V/I/pf)."
            )
        else:
            if tension_v is None or courant_a is None:
                rapport["inconnues"]["impossibles"].append(
                    {"nom": "P_out", "raison": "Donner puissance_electrique_cible_w OU (tension_v et courant_a) pour calculer la puissance."}
                )
            else:
                V = _require_finite("tension_v", tension_v)
                I = _require_finite("courant_a", courant_a)

                if mode_electrique == "triphase_ac":
                    details = calcul_puissance_triphase(
                        tension_composee=V,
                        courant_ligne=I,
                        facteur_puissance=facteur_puissance,
                        entree=entree_puissance_ac,
                        connexion=self.connexion,
                        return_details=True,
                        clamp_non_negative=self.clamp_non_negative,
                    )
                    details_puissance = details  # type: ignore[assignment]
                    P_out = float(details["P"])

                elif mode_electrique == "monophase_ac":
                    details = calcul_puissance_monophase(
                        tension=V,
                        courant=I,
                        facteur_puissance=facteur_puissance,
                        return_details=True,
                        clamp_non_negative=self.clamp_non_negative,
                    )
                    details_puissance = details  # type: ignore[assignment]
                    P_out = float(details["P"])

                elif mode_electrique == "dc":
                    details = calcul_puissance_dc(
                        tension_dc=V,
                        courant_dc=I,
                        return_details=True,
                        clamp_non_negative=self.clamp_non_negative,
                    )
                    details_puissance = details  # type: ignore[assignment]
                    P_out = float(details["P"])

                else:
                    raise ValueError("mode_electrique invalide.")

        rapport["entrees"]["mode_electrique"] = mode_electrique
        rapport["entrees"]["tension_v"] = tension_v
        rapport["entrees"]["courant_a"] = courant_a
        rapport["entrees"]["facteur_puissance"] = facteur_puissance
        rapport["resultats"]["P_out_W"] = P_out
        rapport["resultats"]["details_puissance"] = details_puissance

        # -----------------------------
        # 4) Résistance phase (si besoin) + pertes cuivre
        # -----------------------------
        R_phase: Optional[float] = None
        if self.resistance_phase_ohm is not None:
            R_phase = float(self.resistance_phase_ohm)
        else:
            # Tentative de déduction via rho, L, A
            if (
                self.resistivite_ohm_m is not None
                and self.longueur_fil_m is not None
                and self.section_fil_m2 is not None
            ):
                R_phase = calcul_resistance_enroulement(
                    resistivite=self.resistivite_ohm_m,
                    longueur_fil=self.longueur_fil_m,
                    section_fil=self.section_fil_m2,
                    temperature_c=self.temperature_c,
                    temperature_ref_c=self.temperature_ref_c,
                    coef_temperature=self.coef_temperature,
                    clamp_non_negative=True,
                )
                rapport["notes_modele"].append(
                    "Résistance phase déduite par R=rho*L/A (avec correction température si fournie)."
                )
            else:
                rapport["inconnues"]["partielles"].append(
                    {
                        "nom": "resistance_phase_ohm",
                        "raison": "Fournir resistance_phase_ohm OU (resistivite_ohm_m, longueur_fil_m, section_fil_m2).",
                    }
                )

        rapport["resultats"]["R_phase_ohm"] = R_phase

        P_cu_total: Optional[float] = None
        P_cu_detail: Dict[str, Any] = {}

        # Courant utile pour pertes cuivre (en AC : courant de ligne ou de phase selon convention)
        if R_phase is not None and courant_a is not None:
            I_in = float(courant_a)

            # 4.1 pertes cuivre triphasées
            P_cu_total = calcul_pertes_cuivre_triphase(
                courant_phase=I_in,
                resistance_phase=R_phase,
                courant_type="rms",
                connexion=self.connexion,
                courant_est_ligne=courant_est_ligne,
                clamp_non_negative=True,
            )
            P_cu_detail["P_cu_triphase_W"] = P_cu_total

            # 4.2 pertes cuivre par phase (pour visibilité)
            # On reconstruit I_phase à partir de I_ligne si nécessaire (mêmes conventions que le module)
            if courant_est_ligne:
                if self.connexion == "Y":
                    I_phase = I_in
                else:  # Delta
                    I_phase = I_in / math.sqrt(3.0)
            else:
                I_phase = I_in

            P_cu_phase = calcul_pertes_cuivre_phase(
                courant=I_phase,
                resistance=R_phase,
                courant_type="rms",
                clamp_non_negative=True,
            )
            P_cu_detail["I_phase_rms_A"] = I_phase
            P_cu_detail["P_cu_phase_W"] = P_cu_phase
            P_cu_detail["P_cu_recompose_W"] = 3.0 * P_cu_phase

        else:
            rapport["inconnues"]["partielles"].append(
                {
                    "nom": "Pertes cuivre",
                    "raison": "Calculables si on connaît courant_a (au point) et R_phase_ohm (directe ou déduite).",
                }
            )

        rapport["pertes"]["P_cuivre_W"] = P_cu_total
        rapport["pertes"]["details_cuivre"] = P_cu_detail

        # -----------------------------
        # 5) Pertes fer (Steinmetz) : nécessite coefficients + B + f
        # -----------------------------
        P_fe_total: Optional[float] = None
        P_fe_detail: Optional[Dict[str, float]] = None

        if (
            frequence_hz is not None
            and self.k_h is not None
            and self.k_e is not None
            and self.exposant_steinmetz is not None
            and self.induction_max_t is not None
        ):
            # totalisation via masse ou volume si fourni (sinon -> "spécifique")
            details = calcul_pertes_fer_steinmetz(
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
            # type: ignore[assignment]
            P_fe_total = float(details["P_total"])
            P_fe_detail = {k: float(v) for k, v in details.items()}  # copie propre
        else:
            rapport["inconnues"]["impossibles"].append(
                {
                    "nom": "Pertes fer (Steinmetz)",
                    "raison": (
                        "Impossible sans calibration matériau (k_h, k_e, exposant_steinmetz) "
                        "et sans Bmax + fréquence."
                    ),
                }
            )

        rapport["pertes"]["P_fer_W"] = P_fe_total
        rapport["pertes"]["details_fer"] = P_fe_detail

        # -----------------------------
        # 6) Rendement, P méca, couple
        # -----------------------------
        P_losses_list: list[float] = []
        if P_cu_total is not None:
            P_losses_list.append(float(P_cu_total))
        if P_fe_total is not None:
            P_losses_list.append(float(P_fe_total))
        # pertes fixes : on les traite comme pertes supplémentaires (modèle simple)
        if _is_finite(self.pertes_fixes_w) and float(self.pertes_fixes_w) != 0.0:
            P_losses_list.append(float(self.pertes_fixes_w))

        eta_total: Optional[float] = None
        eta_detail: Optional[Dict[str, float]] = None

        if P_out is not None and len(P_losses_list) > 0:
            details_eta = calcul_rendement_alternateur(
                puissance_utile_out=float(P_out),
                liste_pertes=P_losses_list,
                clamp_0_1=True,
                return_details=True,
            )
            eta_detail = {k: float(v) for k, v in details_eta.items()}  # type: ignore[arg-type]
            eta_total = float(details_eta["eta"])
        else:
            # Sans P_out ou sans pertes, pas de rendement calculable (sinon tu inventes)
            if P_out is None:
                rapport["inconnues"]["impossibles"].append(
                    {"nom": "rendement", "raison": "Impossible sans puissance utile P_out."}
                )
            else:
                rapport["inconnues"]["partielles"].append(
                    {"nom": "rendement", "raison": "Fournir au moins un modèle de pertes (cuivre/fer/fixes) pour calculer eta."}
                )

        rapport["resultats"]["eta_total"] = eta_total
        rapport["resultats"]["details_rendement"] = eta_detail

        P_mec: Optional[float] = None
        couple_nm: Optional[float] = None

        if P_out is not None and eta_total is not None and omega is not None and abs(omega) > 1e-12:
            # Puissance mécanique requise (on considère ici eta_total inclut toutes les pertes listées)
            P_mec = calcul_puissance_mecanique(
                puissance_electrique_cible=float(P_out),
                rendement_alternateur=float(eta_total),
                pertes_fixes_w=0.0,  # déjà inclus dans eta_total si tu l'as mis dans la liste de pertes
                clamp_non_negative=self.clamp_non_negative,
                mode_signe="abs" if self.clamp_non_negative else "conserver",
            )

            # Couple mécanique requis
            couple_nm = calcul_couple_alternateur(
                puissance_electrique_cible=float(P_out),
                rendement_alternateur=float(eta_total),
                vitesse_angulaire=float(omega),
                pertes_fixes_w=0.0,  # même logique : déjà inclus dans eta_total
                clamp_non_negative=self.clamp_non_negative,
                mode_signe="abs_omega" if self.clamp_non_negative else "conserver",
            )
        else:
            # Diagnostics fins
            if P_out is None:
                rapport["inconnues"]["impossibles"].append(
                    {"nom": "P_mec / couple", "raison": "Impossible sans puissance électrique utile P_out."}
                )
            if eta_total is None:
                rapport["inconnues"]["impossibles"].append(
                    {"nom": "P_mec / couple", "raison": "Impossible sans rendement (donc sans modèle de pertes ou datasheet)."}
                )
            if omega is None:
                rapport["inconnues"]["impossibles"].append(
                    {"nom": "couple", "raison": "Impossible sans vitesse angulaire omega."}
                )

        rapport["resultats"]["P_mecanique_W"] = P_mec
        rapport["resultats"]["couple_mecanique_Nm"] = couple_nm

        # -----------------------------
        # 7) Échauffement (DeltaT) si Rth connue
        # -----------------------------
        P_pertes_totales: Optional[float] = None
        if len(P_losses_list) > 0:
            P_pertes_totales = float(sum(P_losses_list))

        rapport["pertes"]["P_pertes_totales_W"] = P_pertes_totales

        delta_t: Optional[float] = None
        if P_pertes_totales is not None and self.resistance_thermique_k_w is not None:
            delta_t = calcul_echauffement_thermique(
                puissance_pertes_totale=P_pertes_totales,
                resistance_thermique=float(self.resistance_thermique_k_w),
                offset_temperature=float(self.offset_temperature),
                clamp_non_negative=True,
            )
        else:
            rapport["inconnues"]["partielles"].append(
                {
                    "nom": "échauffement (DeltaT)",
                    "raison": "Calculable si on connaît resistance_thermique_k_w et si un modèle de pertes est disponible.",
                }
            )

        rapport["resultats"]["deltaT_K_ou_C"] = delta_t

        # -----------------------------
        # 8) Résumé des inconnues restantes (nettoyage simple)
        # -----------------------------
        # (Évite doublons exacts)
        def _dedup(lst: list[dict]) -> list[dict]:
            seen: set[Tuple[str, str]] = set()
            out: list[dict] = []
            for item in lst:
                key = (str(item.get("nom", "")), str(item.get("raison", "")))
                if key not in seen:
                    seen.add(key)
                    out.append(item)
            return out

        rapport["inconnues"]["impossibles"] = _dedup(rapport["inconnues"]["impossibles"])
        rapport["inconnues"]["partielles"] = _dedup(rapport["inconnues"]["partielles"])

        # Mémorise les entrées structurées
        rapport["entrees"].update(
            {
                "vitesse_rotation_rpm": vitesse_rotation_rpm,
                "vitesse_angulaire_rad_s": vitesse_angulaire_rad_s,
                "entree_puissance_ac": entree_puissance_ac,
                "courant_est_ligne": courant_est_ligne,
                "puissance_electrique_cible_w": puissance_electrique_cible_w,
                "connexion": self.connexion,
                "nombre_poles": self.nombre_poles,
                "mode_poles": self.mode_poles,
            }
        )

        return rapport
