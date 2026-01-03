# backend/components/moteur_thermique.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple
import math


# ============================================================
# Imports des modules "moteur_thermique" (robustes)
# ============================================================

try:
    from backend.modules.moteur_thermique.calcul_cylindree import (
        calcul_cylindree_unitaire,
        calcul_cylindree_totale,
    )
    from backend.modules.moteur_thermique.calcul_travail_indique import (
        calcul_travail_indique_pme,
        calcul_puissance_indiquee,
    )
    from backend.modules.moteur_thermique.calcul_force_gaz import calcul_force_gaz
    from backend.modules.moteur_thermique.calcul_force_inertie import calcul_force_inertie_alternative
    from backend.modules.moteur_thermique.calcul_couple_vilebrequin import calcul_couple_instantane
    from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import (
        calcul_epaisseur_cylindre_mince,
        calcul_epaisseur_cylindre_lame,
    )
    from backend.modules.moteur_thermique.calcul_loi_gaz_parfait import (
        calcul_pression_gaz_parfait,
        calcul_temperature_compression_adiabatique,
    )
    from backend.modules.moteur_thermique.calcul_fuite_segment import (
        calcul_debit_fuite_annulaire,
        calcul_masse_fuite,
    )
    from backend.modules.moteur_thermique.calcul_pertes_frottement import (
        calcul_puissance_frottement_segment,
        calcul_puissance_frottement_palier,
    )
    from backend.modules.moteur_thermique.calcul_precharge_vis import (
        calcul_force_separation,
        calcul_precharge_vis_totale,
        calcul_couple_serrage,
    )
    from backend.modules.moteur_thermique.calcul_vitesse_piston import calcul_vitesse_moyenne_piston
    from backend.modules.moteur_thermique.calcul_usure_archard import (
        calcul_volume_usure_archard,
        calcul_perte_epaisseur,
    )
except Exception:
    # Si ton projet a une autre structure de packages, adapte uniquement ces imports.
    from backend.modules.moteur_thermique.calcul_cylindree import (
        calcul_cylindree_unitaire,
        calcul_cylindree_totale,
    )
    from backend.modules.moteur_thermique.calcul_travail_indique import (
        calcul_travail_indique_pme,
        calcul_puissance_indiquee,
    )
    from backend.modules.moteur_thermique.calcul_force_gaz import calcul_force_gaz
    from backend.modules.moteur_thermique.calcul_force_inertie import calcul_force_inertie_alternative
    from backend.modules.moteur_thermique.calcul_couple_vilebrequin import calcul_couple_instantane
    from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import (
        calcul_epaisseur_cylindre_mince,
        calcul_epaisseur_cylindre_lame,
    )
    from backend.modules.moteur_thermique.calcul_loi_gaz_parfait import (
        calcul_pression_gaz_parfait,
        calcul_temperature_compression_adiabatique,
    )
    from backend.modules.moteur_thermique.calcul_fuite_segment import (
        calcul_debit_fuite_annulaire,
        calcul_masse_fuite,
    )
    from backend.modules.moteur_thermique.calcul_pertes_frottement import (
        calcul_puissance_frottement_segment,
        calcul_puissance_frottement_palier,
    )
    from backend.modules.moteur_thermique.calcul_precharge_vis import (
        calcul_force_separation,
        calcul_precharge_vis_totale,
        calcul_couple_serrage,
    )
    from backend.modules.moteur_thermique.calcul_vitesse_piston import calcul_vitesse_moyenne_piston
    from backend.modules.moteur_thermique.calcul_usure_archard import (
        calcul_volume_usure_archard,
        calcul_perte_epaisseur,
    )


# ============================================================
# Helpers
# ============================================================

TempsMoteur = Literal[2, 4]


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


def _require_int_pos(name: str, x: Any) -> int:
    if not isinstance(x, int) or x <= 0:
        raise ValueError(f"{name} doit être un entier > 0 (reçu: {x!r}).")
    return int(x)


def _omega_from_rpm(rpm: float) -> float:
    return (2.0 * math.pi * rpm) / 60.0


def _cycles_par_seconde(rpm: float, temps_moteur: int) -> float:
    # 2T : 1 cycle / tour => n/60
    # 4T : 1 cycle / 2 tours => (n/60)/2
    cps = rpm / 60.0
    if temps_moteur == 4:
        cps /= 2.0
    return cps


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


def _archard_depuis_vitesse(
    *,
    k: Optional[float],
    W_n: Optional[float],
    v_ms: Optional[float],
    H_pa: Optional[float],
    aire_contact_m2: Optional[float],
) -> Dict[str, Optional[float]]:
    """
    Donne :
    - débit volumique d'usure dV/dt (m³/s)
    - débit d'épaisseur dh/dt (m/s) si aire connue

    On force l'utilisation des fonctions du module Archard via une distance sur 1 seconde.
    """
    out: Dict[str, Optional[float]] = {
        "dV_dt_m3_s": None,
        "dh_dt_m_s": None,
        "dV_par_heure_m3_h": None,
        "dh_par_heure_m_h": None,
    }
    if k is None or W_n is None or v_ms is None or H_pa is None:
        return out

    # distance sur 1 seconde
    V_1s = calcul_volume_usure_archard(
        coefficient_usure_k=k,
        charge_normale_w=W_n,
        distance_glissement_ls=max(0.0, v_ms),
        durete_h=H_pa,
    )
    out["dV_dt_m3_s"] = float(V_1s)

    out["dV_par_heure_m3_h"] = float(V_1s) * 3600.0

    if aire_contact_m2 is not None:
        dh_1s = calcul_perte_epaisseur(volume_use_m3=V_1s, aire_contact_m2=aire_contact_m2)
        out["dh_dt_m_s"] = float(dh_1s)
        out["dh_par_heure_m_h"] = float(dh_1s) * 3600.0

    return out


# ============================================================
# Composant moteur thermique (pré-dimensionnement calculatoire)
# ============================================================

@dataclass(frozen=True)
class MoteurThermique:
    """
    Objectif : calculer un maximum de grandeurs (cinématique, forces, dimensionnements,
    pertes, usure Archard), et ne laisser comme inconnues que ce qui dépend :
    - courbes réelles (p(θ)), combustion/échanges thermiques détaillés
    - données matériaux/tribologie exactes (k, H, μ, lubrification)
    - géométrie détaillée (segments, paliers, état de surface, alignements, etc.)
    """

    # --- Géométrie de base ---
    alesage_m: Optional[float] = None
    course_m: Optional[float] = None
    nombre_cylindres: int = 1
    temps_moteur: TempsMoteur = 4  # 2 ou 4

    # --- Cinématique bielle-manivelle (pour inertie) ---
    longueur_bielle_m: Optional[float] = None
    rayon_manivelle_m: Optional[float] = None  # si None, approx = course/2 (partiel)
    masse_alternative_kg: Optional[float] = None  # piston + axe + part de bielle

    # --- Dimensionnement cylindre (pression/contrainte admissible) ---
    contrainte_admissible_pa: Optional[float] = None
    facteur_securite_cylindre: float = 1.5

    # --- Fuite (si tu veux estimer leakage) ---
    viscosite_pa_s: Optional[float] = None
    densite_kg_m3: Optional[float] = None

    # --- Frottements (modèle Coulomb simplifié) ---
    coef_frottement_segment: Optional[float] = None
    coef_frottement_palier: Optional[float] = None

    # --- Usure Archard (coeffs typiquement "datasheet/tribologie") ---
    # Segments / chemise
    coefficient_usure_segment_k: Optional[float] = None
    durete_contact_segment_pa: Optional[float] = None
    aire_contact_segment_m2: Optional[float] = None  # aire effective de contact (m²)

    # Palier lisse
    coefficient_usure_palier_k: Optional[float] = None
    durete_contact_palier_pa: Optional[float] = None
    aire_contact_palier_m2: Optional[float] = None

    # --- Précharge vis (couvercle) ---
    facteur_securite_vis: float = 1.5
    facteur_frottement_vis_k: float = 0.2  # approximation "écrou K"

    clamp_non_negative: bool = True

    def analyser_point_de_fonctionnement(
        self,
        *,
        rpm: Optional[float] = None,

        # Travail indiqué (si tu connais la PME)
        pression_moyenne_effective_pa: Optional[float] = None,

        # Instantané (si tu connais la pression cylindre à un angle)
        pression_cylindre_pa: Optional[float] = None,
        angle_vilebrequin_deg: Optional[float] = None,

        # Thermo gaz parfait (si tu as m, V, T)
        masse_gaz_kg: Optional[float] = None,
        volume_gaz_m3: Optional[float] = None,
        temperature_gaz_k: Optional[float] = None,
        constante_gaz_r: float = 287.05,

        # Adiabatique (si tu as T1, P1, P2)
        t1_k: Optional[float] = None,
        p1_pa: Optional[float] = None,
        p2_pa: Optional[float] = None,
        gamma: float = 1.4,

        # Fuite annulaire (segments / joints)
        delta_p_fuite_pa: Optional[float] = None,
        jeu_radial_h_m: Optional[float] = None,
        rayon_fuite_m: Optional[float] = None,
        longueur_fuite_m: Optional[float] = None,

        # Frottements (si tu as N, W, v)
        force_normale_segment_n: Optional[float] = None,
        vitesse_glissement_palier_ms: Optional[float] = None,
        charge_palier_n: Optional[float] = None,

        # Usure : si tu veux une valeur cumulée sur une durée (sinon on sort les taux)
        duree_fonctionnement_s: Optional[float] = None,

        # Couvercle / vis
        pression_max_pa: Optional[float] = None,
        aire_effective_couvercle_m2: Optional[float] = None,
        force_joint_n: Optional[float] = None,
        nombre_vis: Optional[int] = None,
        diametre_nominal_vis_m: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Rapport détaillé, en calculant tout ce qui est calculable et en listant explicitement
        les inconnues restantes (impossibles vs partielles).
        """
        rapport: Dict[str, Any] = {
            "entrees": {},
            "cylindree": {},
            "cinematique": {},
            "resultats": {},
            "thermo": {},
            "forces": {},
            "couple": {},
            "pertes": {},
            "usure": {},
            "dimensionnement": {},
            "assemblage": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ============================================================
        # 1) Entrées de base
        # ============================================================
        rapport["entrees"].update(
            {
                "rpm": rpm,
                "pression_moyenne_effective_pa": pression_moyenne_effective_pa,
                "pression_cylindre_pa": pression_cylindre_pa,
                "angle_vilebrequin_deg": angle_vilebrequin_deg,
                "duree_fonctionnement_s": duree_fonctionnement_s,
                "temps_moteur": self.temps_moteur,
                "nombre_cylindres": self.nombre_cylindres,
                "alesage_m": self.alesage_m,
                "course_m": self.course_m,
            }
        )

        # ============================================================
        # 2) Cylindrée (unitaire + totale)
        # ============================================================
        Vd_unit: Optional[float] = None
        Vd_tot: Optional[float] = None

        if self.alesage_m is not None and self.course_m is not None:
            Vd_unit = float(
                calcul_cylindree_unitaire(
                    alesage_m=self.alesage_m,
                    course_m=self.course_m,
                    allow_zero=False,
                    return_details=False,
                )
            )
            Vd_tot = float(
                calcul_cylindree_totale(
                    cylindree_unitaire_m3=Vd_unit,
                    nombre_cylindres=int(self.nombre_cylindres),
                    allow_zero_cylindres=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(rapport, "impossibles", "cylindrée", "Impossible sans alesage_m et course_m.")

        rapport["cylindree"]["Vd_unitaire_m3"] = Vd_unit
        rapport["cylindree"]["Vd_totale_m3"] = Vd_tot

        # ============================================================
        # 3) Cinématique : ω, cycles/s, vitesse moyenne piston (module dédié)
        # ============================================================
        omega: Optional[float] = None
        cps: Optional[float] = None
        v_piston_moy: Optional[float] = None

        if rpm is not None:
            rpm_val = _require_positive("rpm", rpm, strictly=False)
            omega = _omega_from_rpm(rpm_val)
            cps = _cycles_par_seconde(rpm_val, int(self.temps_moteur))

            if self.course_m is not None:
                # le module impose rpm>=0 : on utilise la magnitude
                v_piston_moy = float(calcul_vitesse_moyenne_piston(course_m=self.course_m, vitesse_rotation_tr_min=rpm_val))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "vitesse moyenne piston",
                    "Calculable si course_m est fournie.",
                )
        else:
            _push_inconnue(rapport, "partielles", "cinématique", "ω/cycles/s/vitesse piston calculables si rpm est fourni.")

        rapport["cinematique"]["omega_rad_s"] = omega
        rapport["cinematique"]["cycles_par_seconde"] = cps
        rapport["cinematique"]["vitesse_moyenne_piston_ms"] = v_piston_moy
        if v_piston_moy is not None:
            rapport["cinematique"]["distance_glissement_piston_par_heure_m"] = v_piston_moy * 3600.0

        # ============================================================
        # 4) Travail indiqué / Puissance indiquée (si PME + rpm)
        # ============================================================
        W_i: Optional[float] = None
        P_i: Optional[float] = None

        if pression_moyenne_effective_pa is not None and Vd_tot is not None:
            W_i = float(calcul_travail_indique_pme(pression_moyenne_effective_pa, Vd_tot))

            if rpm is not None:
                P_i = float(calcul_puissance_indiquee(W_i, _require_positive("rpm", rpm, strictly=False), temps_moteur=int(self.temps_moteur)))
            else:
                _push_inconnue(rapport, "partielles", "puissance indiquée", "Calculable si rpm est fourni.")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "travail/power indiqué",
                "Calculables si pression_moyenne_effective_pa et alesage/course sont fournis.",
            )

        rapport["resultats"]["travail_indique_par_cycle_J"] = W_i
        rapport["resultats"]["puissance_indiquee_W"] = P_i

        # ============================================================
        # 5) Force gaz / force inertie / couple instantané
        # ============================================================
        F_gaz: Optional[float] = None
        F_inertie: Optional[float] = None
        F_bielle: Optional[float] = None
        T_inst: Optional[float] = None

        # 5.1 Force gaz instantanée
        if pression_cylindre_pa is not None and self.alesage_m is not None:
            F_gaz = float(
                calcul_force_gaz(
                    pression_pa=_require_finite("pression_cylindre_pa", pression_cylindre_pa),
                    alesage_m=self.alesage_m,
                    allow_negative_pression=True,
                    allow_zero_alesage=False,
                    clamp_non_negative=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(rapport, "partielles", "force gaz instantanée", "Calculable si pression_cylindre_pa et alesage_m sont fournis.")

        # 5.2 Force inertie alternative
        r_manivelle: Optional[float] = None
        if self.rayon_manivelle_m is not None:
            r_manivelle = float(self.rayon_manivelle_m)
        elif self.course_m is not None:
            r_manivelle = 0.5 * float(self.course_m)
            rapport["notes_modele"].append("rayon_manivelle_m approx = course/2 (si non fourni).")

        if (
            self.masse_alternative_kg is not None
            and r_manivelle is not None
            and rpm is not None
            and self.longueur_bielle_m is not None
            and angle_vilebrequin_deg is not None
        ):
            F_inertie = float(
                calcul_force_inertie_alternative(
                    masse_alternative_kg=self.masse_alternative_kg,
                    rayon_manivelle_m=r_manivelle,
                    vitesse_rotation_tr_min=_require_positive("rpm", rpm, strictly=False),
                    longueur_bielle_m=self.longueur_bielle_m,
                    angle_vilebrequin_deg=_require_finite("angle_vilebrequin_deg", angle_vilebrequin_deg),
                    angle_unite="deg",
                    input_vitesse="rpm",
                    clamp_ratio_r_sur_l=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force inertie alternative",
                "Calculable si (masse_alternative_kg, course/rayon_manivelle_m, rpm, longueur_bielle_m, angle_vilebrequin_deg) sont fournis.",
            )

        # 5.3 Force bielle effective (simplifiée)
        if F_gaz is not None and F_inertie is not None:
            F_bielle = F_gaz - F_inertie
        else:
            _push_inconnue(rapport, "partielles", "force bielle effective", "Déductible si force gaz ET force inertie sont calculées.")

        # 5.4 Couple instantané (simplifié)
        if F_bielle is not None and r_manivelle is not None and angle_vilebrequin_deg is not None:
            T_inst = float(
                calcul_couple_instantane(
                    force_bielle_n=F_bielle,
                    rayon_manivelle_m=r_manivelle,
                    angle_vilebrequin_deg=_require_finite("angle_vilebrequin_deg", angle_vilebrequin_deg),
                    angle_unite="deg",
                    use_abs_rayon=True,
                    clamp_non_negative=False,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "couple instantané",
                "Calculable si (force bielle, rayon_manivelle_m/course, angle_vilebrequin_deg) sont fournis.",
            )

        rapport["forces"]["F_gaz_N"] = F_gaz
        rapport["forces"]["F_inertie_N"] = F_inertie
        rapport["forces"]["F_bielle_effective_N"] = F_bielle
        rapport["couple"]["T_instantane_Nm"] = T_inst
        rapport["cinematique"]["rayon_manivelle_m_effectif"] = r_manivelle

        # ============================================================
        # 6) Thermo : gaz parfait + compression adiabatique
        # ============================================================
        P_gaz: Optional[float] = None
        if masse_gaz_kg is not None and volume_gaz_m3 is not None and temperature_gaz_k is not None:
            P_gaz = float(
                calcul_pression_gaz_parfait(
                    masse_kg=_require_positive("masse_gaz_kg", masse_gaz_kg, strictly=False),
                    volume_m3=_require_positive("volume_gaz_m3", volume_gaz_m3, strictly=True),
                    temperature_k=_require_positive("temperature_gaz_k", temperature_gaz_k, strictly=True),
                    constante_gaz_r=_require_positive("constante_gaz_r", constante_gaz_r, strictly=True),
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pression gaz parfait (P=mRT/V)",
                "Calculable si masse_gaz_kg, volume_gaz_m3, temperature_gaz_k sont fournis.",
            )

        T2: Optional[float] = None
        if t1_k is not None and p1_pa is not None and p2_pa is not None:
            T2 = float(
                calcul_temperature_compression_adiabatique(
                    t1_k=_require_positive("t1_k", t1_k, strictly=True),
                    p1_pa=_require_positive("p1_pa", p1_pa, strictly=True),
                    p2_pa=_require_positive("p2_pa", p2_pa, strictly=True),
                    gamma=_require_positive("gamma", gamma, strictly=True),
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "température adiabatique T2",
                "Calculable si t1_k, p1_pa, p2_pa sont fournis (et gamma).",
            )

        rapport["thermo"]["pression_gaz_parfait_pa"] = P_gaz
        rapport["thermo"]["temperature_adiabatique_T2_k"] = T2

        # ============================================================
        # 7) Fuite annulaire : débit volumique + débit massique
        # ============================================================
        Q_fuite: Optional[float] = None
        m_dot_fuite: Optional[float] = None

        if (
            delta_p_fuite_pa is not None
            and jeu_radial_h_m is not None
            and rayon_fuite_m is not None
            and longueur_fuite_m is not None
            and self.viscosite_pa_s is not None
        ):
            Q_fuite = float(
                calcul_debit_fuite_annulaire(
                    delta_p_pa=_require_finite("delta_p_fuite_pa", delta_p_fuite_pa),
                    jeu_radial_h_m=_require_positive("jeu_radial_h_m", jeu_radial_h_m, strict=False),
                    rayon_m=_require_positive("rayon_fuite_m", rayon_fuite_m, strict=False),
                    longueur_fuite_l_m=_require_positive("longueur_fuite_m", longueur_fuite_m, strict=True),
                    viscosite_dynamique_pa_s=_require_positive("viscosite_pa_s", self.viscosite_pa_s, strict=True),
                    use_abs_delta_p=True,
                    clamp_non_negative=True,
                    return_details=False,
                )
            )

            if self.densite_kg_m3 is not None:
                m_dot_fuite = float(
                    calcul_masse_fuite(
                        debit_volumique_m3s=Q_fuite,
                        densite_kg_m3=_require_positive("densite_kg_m3", self.densite_kg_m3, strict=False),
                        use_abs_debit=True,
                        clamp_non_negative=True,
                        return_details=False,
                    )
                )
            else:
                _push_inconnue(rapport, "partielles", "débit massique de fuite", "Calculable si densite_kg_m3 est fournie (en plus de Q_fuite).")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "débit de fuite annulaire",
                "Calculable si delta_p_fuite_pa, jeu_radial_h_m, rayon_fuite_m, longueur_fuite_m, viscosite_pa_s sont fournis.",
            )

        rapport["resultats"]["Q_fuite_m3_s"] = Q_fuite
        rapport["resultats"]["m_dot_fuite_kg_s"] = m_dot_fuite

        # ============================================================
        # 8) Pertes par frottement : segments + paliers
        # ============================================================
        P_frott_seg: Optional[float] = None
        P_frott_palier: Optional[float] = None

        if force_normale_segment_n is not None and self.coef_frottement_segment is not None and v_piston_moy is not None:
            P_frott_seg = float(
                calcul_puissance_frottement_segment(
                    force_normale_n=_require_positive("force_normale_segment_n", force_normale_segment_n, strictly=False),
                    vitesse_moyenne_ms=_require_positive("v_piston_moy", v_piston_moy, strictly=False),
                    coef_frottement=_require_positive("coef_frottement_segment", self.coef_frottement_segment, strictly=False),
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pertes frottement segment",
                "Calculables si force_normale_segment_n, coef_frottement_segment, rpm et course_m sont fournis.",
            )

        if charge_palier_n is not None and vitesse_glissement_palier_ms is not None and self.coef_frottement_palier is not None:
            P_frott_palier = float(
                calcul_puissance_frottement_palier(
                    charge_w=_require_positive("charge_palier_n", charge_palier_n, strictly=False),
                    vitesse_glissement_ms=_require_positive("vitesse_glissement_palier_ms", vitesse_glissement_palier_ms, strictly=False),
                    coef_frottement_f=_require_positive("coef_frottement_palier", self.coef_frottement_palier, strictly=False),
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pertes frottement palier",
                "Calculables si charge_palier_n, vitesse_glissement_palier_ms et coef_frottement_palier sont fournis.",
            )

        P_frott_total: Optional[float] = None
        if P_frott_seg is not None or P_frott_palier is not None:
            P_frott_total = float((P_frott_seg or 0.0) + (P_frott_palier or 0.0))

        rapport["pertes"]["P_frottement_segment_W"] = P_frott_seg
        rapport["pertes"]["P_frottement_palier_W"] = P_frott_palier
        rapport["pertes"]["P_frottement_total_W"] = P_frott_total

        # ============================================================
        # 9) Puissance "frein" estimée + couple moyen + BMEP/FMEP estimés
        # ============================================================
        P_brake_est: Optional[float] = None
        T_moy_est: Optional[float] = None
        BMEP_est: Optional[float] = None
        FMEP_est: Optional[float] = None
        eta_meca_est: Optional[float] = None

        if P_i is not None and P_frott_total is not None:
            P_brake_est = float(P_i - P_frott_total)
            if self.clamp_non_negative:
                P_brake_est = max(0.0, P_brake_est)

            if omega and omega > 0.0:
                T_moy_est = P_brake_est / omega

            # BMEP approx depuis couple moyen (si Vd_tot) :
            # 4T : W_cycle = 4πT ; PME = W/Vd => 4πT/Vd
            # 2T : W_cycle = 2πT ; PME = 2πT/Vd
            if T_moy_est is not None and Vd_tot and Vd_tot > 0.0:
                coeff = 4.0 * math.pi if int(self.temps_moteur) == 4 else 2.0 * math.pi
                BMEP_est = (coeff * T_moy_est) / Vd_tot

            # FMEP approx depuis pertes frottement : FMEP = P_frott / (Vd * cycles/s)
            if P_frott_total is not None and Vd_tot and cps and Vd_tot > 0.0 and cps > 0.0:
                FMEP_est = P_frott_total / (Vd_tot * cps)

            if P_i and P_i != 0.0 and P_brake_est is not None:
                eta_meca_est = P_brake_est / P_i

            rapport["notes_modele"].append(
                "P_brake_est/BMEP/FMEP/η_meca sont des estimations simplifiées (sans pompage, pertes thermo, accessoires, combustion, etc.)."
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "puissance frein / couple moyen / BMEP / FMEP / η_meca",
                "Calculables si puissance indiquée (via PME) ET modèle de pertes (au moins frottements) sont disponibles, avec rpm pour couple/BMEP.",
            )

        rapport["resultats"]["puissance_frein_estimee_W"] = P_brake_est
        rapport["resultats"]["couple_moyen_estime_Nm"] = T_moy_est
        rapport["resultats"]["BMEP_estime_Pa"] = BMEP_est
        rapport["resultats"]["FMEP_estime_Pa"] = FMEP_est
        rapport["resultats"]["rendement_mecanique_estime"] = eta_meca_est

        # ============================================================
        # 10) Usure (Archard) : taux + cumulé si durée fournie
        # ============================================================
        # Segments (vitesse = vitesse moyenne piston)
        usure_seg = _archard_depuis_vitesse(
            k=self.coefficient_usure_segment_k,
            W_n=force_normale_segment_n,
            v_ms=v_piston_moy,
            H_pa=self.durete_contact_segment_pa,
            aire_contact_m2=self.aire_contact_segment_m2,
        )
        # Palier (vitesse = vitesse_glissement_palier_ms)
        usure_pal = _archard_depuis_vitesse(
            k=self.coefficient_usure_palier_k,
            W_n=charge_palier_n,
            v_ms=vitesse_glissement_palier_ms,
            H_pa=self.durete_contact_palier_pa,
            aire_contact_m2=self.aire_contact_palier_m2,
        )

        rapport["usure"]["segments"] = usure_seg
        rapport["usure"]["palier"] = usure_pal

        # Usure cumulée si durée fournie (on repasse par calcul_volume_usure_archard pour distance totale)
        if duree_fonctionnement_s is not None:
            t_s = _require_positive("duree_fonctionnement_s", duree_fonctionnement_s, strictly=False)

            # Segments
            if (
                self.coefficient_usure_segment_k is not None
                and force_normale_segment_n is not None
                and v_piston_moy is not None
                and self.durete_contact_segment_pa is not None
            ):
                V_seg = calcul_volume_usure_archard(
                    coefficient_usure_k=self.coefficient_usure_segment_k,
                    charge_normale_w=force_normale_segment_n,
                    distance_glissement_ls=max(0.0, v_piston_moy) * t_s,
                    durete_h=self.durete_contact_segment_pa,
                )
                rapport["usure"]["segments"]["volume_use_total_m3"] = float(V_seg)
                if self.aire_contact_segment_m2 is not None:
                    dh_seg = calcul_perte_epaisseur(volume_use_m3=V_seg, aire_contact_m2=self.aire_contact_segment_m2)
                    rapport["usure"]["segments"]["perte_epaisseur_totale_m"] = float(dh_seg)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "usure cumulée segments",
                    "Calculable si (k, W, H) segments + vitesse piston sont fournis (et aire_contact_segment_m2 pour perte d'épaisseur).",
                )

            # Palier
            if (
                self.coefficient_usure_palier_k is not None
                and charge_palier_n is not None
                and vitesse_glissement_palier_ms is not None
                and self.durete_contact_palier_pa is not None
            ):
                V_pal = calcul_volume_usure_archard(
                    coefficient_usure_k=self.coefficient_usure_palier_k,
                    charge_normale_w=charge_palier_n,
                    distance_glissement_ls=max(0.0, vitesse_glissement_palier_ms) * t_s,
                    durete_h=self.durete_contact_palier_pa,
                )
                rapport["usure"]["palier"]["volume_use_total_m3"] = float(V_pal)
                if self.aire_contact_palier_m2 is not None:
                    dh_pal = calcul_perte_epaisseur(volume_use_m3=V_pal, aire_contact_m2=self.aire_contact_palier_m2)
                    rapport["usure"]["palier"]["perte_epaisseur_totale_m"] = float(dh_pal)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "usure cumulée palier",
                    "Calculable si (k, W, H) palier + vitesse glissement palier sont fournis (et aire_contact_palier_m2 pour perte d'épaisseur).",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "usure cumulée",
                "Une durée (duree_fonctionnement_s) est nécessaire pour passer des taux (dV/dt) à un volume total.",
            )

        # Inconnues usure si paramètres tribo absents
        if self.coefficient_usure_segment_k is None or self.durete_contact_segment_pa is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "usure segments (valeur absolue)",
                "Impossible sans coefficient d'usure k et dureté H (tribologie/datasheet).",
            )
        if self.coefficient_usure_palier_k is None or self.durete_contact_palier_pa is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "usure palier (valeur absolue)",
                "Impossible sans coefficient d'usure k et dureté H (tribologie/datasheet).",
            )

        # ============================================================
        # 11) Dimensionnement paroi cylindre (mince + Lamé)
        # ============================================================
        t_mince: Optional[float] = None
        t_lame: Optional[float] = None

        p_dim: Optional[float] = None
        if pression_max_pa is not None:
            p_dim = _require_positive("pression_max_pa", pression_max_pa, strictly=False)
        elif pression_cylindre_pa is not None:
            p_dim = _require_finite("pression_cylindre_pa", pression_cylindre_pa)

        if p_dim is not None and self.alesage_m is not None and self.contrainte_admissible_pa is not None:
            ri = 0.5 * _require_positive("alesage_m", self.alesage_m, strictly=True)

            t_mince = float(
                calcul_epaisseur_cylindre_mince(
                    pression_pa=p_dim,
                    rayon_interne_m=ri,
                    contrainte_admissible_pa=_require_positive("contrainte_admissible_pa", self.contrainte_admissible_pa, strictly=True),
                    include_longitudinale=False,
                    facteur_securite=_require_positive("facteur_securite_cylindre", self.facteur_securite_cylindre, strictly=True),
                    clamp_non_negative=True,
                    return_details=False,
                )
            )
            t_lame = float(
                calcul_epaisseur_cylindre_lame(
                    pression_interne_pa=p_dim,
                    rayon_interne_m=ri,
                    contrainte_admissible_pa=_require_positive("contrainte_admissible_pa", self.contrainte_admissible_pa, strictly=True),
                    facteur_securite=_require_positive("facteur_securite_cylindre", self.facteur_securite_cylindre, strictly=True),
                    clamp_non_negative=True,
                    return_details=False,
                )
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "épaisseur paroi cylindre",
                "Calculable si (pression_max_pa ou pression_cylindre_pa), alesage_m et contrainte_admissible_pa sont fournis.",
            )

        rapport["dimensionnement"]["pression_dimensionnement_pa"] = p_dim
        rapport["dimensionnement"]["epaisseur_cylindre_mince_m"] = t_mince
        rapport["dimensionnement"]["epaisseur_cylindre_lame_m"] = t_lame

        # ============================================================
        # 12) Précharge vis couvercle
        # ============================================================
        F_sep: Optional[float] = None
        F_pre_tot: Optional[float] = None
        F_par_vis: Optional[float] = None
        M_serrage: Optional[float] = None

        if pression_max_pa is not None and aire_effective_couvercle_m2 is not None:
            F_sep = float(
                calcul_force_separation(
                    pression_max_pa=_require_positive("pression_max_pa", pression_max_pa, strictly=False),
                    aire_effective_m2=_require_positive("aire_effective_couvercle_m2", aire_effective_couvercle_m2, strictly=False),
                )
            )

            if force_joint_n is not None:
                F_pre_tot = float(
                    calcul_precharge_vis_totale(
                        force_separation_n=F_sep,
                        force_joint_n=_require_positive("force_joint_n", force_joint_n, strictly=False),
                        facteur_securite=_require_positive("facteur_securite_vis", self.facteur_securite_vis, strictly=True),
                    )
                )
            else:
                _push_inconnue(rapport, "partielles", "précharge totale vis", "Calculable si force_joint_n est fournie (en plus de F_sep).")

            if F_pre_tot is not None and nombre_vis is not None:
                n_vis = _require_int_pos("nombre_vis", nombre_vis)
                F_par_vis = F_pre_tot / float(n_vis)
            else:
                _push_inconnue(rapport, "partielles", "précharge par vis", "Calculable si F_pre_tot et nombre_vis sont fournis.")

            if F_par_vis is not None and diametre_nominal_vis_m is not None:
                M_serrage = float(
                    calcul_couple_serrage(
                        force_precharge_vis_n=F_par_vis,
                        diametre_nominal_m=_require_positive("diametre_nominal_vis_m", diametre_nominal_vis_m, strictly=True),
                        facteur_frottement_k=_require_positive("facteur_frottement_vis_k", self.facteur_frottement_vis_k, strictly=False),
                    )
                )
            else:
                _push_inconnue(rapport, "partielles", "couple de serrage vis", "Calculable si F_par_vis et diametre_nominal_vis_m sont fournis.")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "dimensionnement vis couvercle",
                "Calculable si pression_max_pa et aire_effective_couvercle_m2 sont fournis (et force_joint_n, nombre_vis, diametre_nominal_vis_m pour aller plus loin).",
            )

        rapport["assemblage"]["force_separation_N"] = F_sep
        rapport["assemblage"]["precharge_totale_N"] = F_pre_tot
        rapport["assemblage"]["precharge_par_vis_N"] = F_par_vis
        rapport["assemblage"]["couple_serrage_par_vis_Nm"] = M_serrage

        # ============================================================
        # 13) Inconnues vraiment impossibles sans modèle/courbes
        # ============================================================
        _push_inconnue(
            rapport,
            "impossibles",
            "rendement global réel",
            "Sans p(θ) (diagramme indicateur), pertes de pompage, combustion, transferts thermiques, et accessoires, on ne peut pas calculer un rendement global fiable.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "fatigue/longévité complète",
            "Sans matériaux précis, états de surface, concentrations de contraintes, et cycles de charge, on ne peut pas conclure sur la fatigue/longévité.",
        )

        _dedup_inconnues(rapport)
        return rapport
