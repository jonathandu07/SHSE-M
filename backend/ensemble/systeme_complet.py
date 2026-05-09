from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import math


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    if _is_finite(x):
        xf = float(x)
        if abs(xf - round(xf)) < 1e-12:
            return int(round(xf))
    return None


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _push_inconnue(report: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    report.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _vehicle_power_w(
    *,
    masse_kg: Optional[float],
    vitesse_ms: Optional[float],
    acceleration_ms2: Optional[float],
    angle_pente: Optional[float],
    angle_unite: str,
    coef_roulement: Optional[float],
    coef_trainee_aero_cda: Optional[float],
) -> Optional[float]:
    if not _is_finite(vitesse_ms) or not _is_finite(masse_kg):
        return None
    v = float(vitesse_ms)
    m = float(masse_kg)
    acc = float(acceleration_ms2 or 0.0)
    crr = float(coef_roulement or 0.0)
    cda = float(coef_trainee_aero_cda or 0.0)
    g = 9.81
    rho = 1.225
    grade = 0.0
    if _is_finite(angle_pente):
        angle = float(angle_pente)
        if str(angle_unite).lower() in {"deg", "degre", "degres"}:
            angle = math.radians(angle)
        grade = math.sin(angle)
    f_roll = m * g * crr
    f_aero = 0.5 * rho * cda * v * v
    f_acc = m * acc
    f_grade = m * g * grade
    force = max(0.0, f_roll + f_aero + f_acc + f_grade)
    return force * v


@dataclass
class SystemeComplet:
    moteur_electrique: Any = None
    batterie: Any = None
    alternateur: Any = None
    moteur_thermique: Any = None
    boite_crabots: Any = None
    architecture: Any = None

    def analyser(
        self,
        *,
        masse_kg: Optional[float] = None,
        vitesse_ms: Optional[float] = None,
        acceleration_ms2: Optional[float] = None,
        angle_pente: Optional[float] = None,
        angle_unite: str = "rad",
        coef_roulement: Optional[float] = None,
        coef_trainee_aero_cda: Optional[float] = None,
        rayon_roue_m: Optional[float] = None,
        rapport_reduction_global: Optional[float] = None,
        rendement_transmission: Optional[float] = None,
        puissance_auxiliaire_w: Optional[float] = None,
        distance_km: Optional[float] = None,
        conso_kwh_km: Optional[float] = None,
        puissance_moyenne_kw: Optional[float] = None,
        vitesse_moyenne_kmh: Optional[float] = None,
        temps_charge_cible_h: Optional[float] = None,
        puissance_pic_kw: Optional[float] = None,
        duree_pic_s: Optional[float] = None,
        energie_utile_imposee_kwh: Optional[float] = None,
        calculer_puissance_charge_requise: bool = False,
        scenario_bus_dc: Optional[str] = None,
        tension_bus_dc_v: Optional[float] = None,
        vitesse_alternateur_rpm: Optional[float] = None,
        vitesse_moteur_thermique_rpm: Optional[float] = None,
        rapport_vitesse_alt_sur_moteur: Optional[float] = None,
        puissance_elec_alt_cible_w: Optional[float] = None,
        tension_alt_v: Optional[float] = None,
        courant_alt_a: Optional[float] = None,
        facteur_puissance_alt: Optional[float] = None,
        courant_est_ligne: Optional[bool] = None,
        rendement_liaison_meca_alt: Optional[float] = None,
        rapports_boite_candidates: Optional[Sequence[float]] = None,
        rendement_boite: Optional[float] = None,
        facteur_service_boite: Optional[float] = None,
        moment_flechissant_nm: Optional[float] = None,
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_axiale_roulement_N: Optional[float] = None,
        force_radiale_roulement_N: Optional[float] = None,
        pme_pa: Optional[float] = None,
        vitesse_piston_max_ms: Optional[float] = None,
        longueur_dispo_m: Optional[float] = None,
        largeur_dispo_m: Optional[float] = None,
        hauteur_dispo_m: Optional[float] = None,
        horizon_usage_h: Optional[float] = None,
        architectures_autorisees: Optional[List[str]] = None,
        architecture_forcee: Optional[str] = None,
        poids_maintenance: Optional[float] = None,
        poids_masse: Optional[float] = None,
        poids_cout_matiere: Optional[float] = None,
        poids_compacite: Optional[float] = None,
        poids_fiabilite: Optional[float] = None,
        poids_rendement: Optional[float] = None,
        pression_max_pa: Optional[float] = None,
        contrainte_admissible_pa: Optional[float] = None,
        densite_materiau_kg_m3: Optional[float] = None,
        cout_matiere_eur_kg: Optional[float] = None,
        rendement_indique_cible_min: Optional[float] = None,
        rendement_mecanique_cible_min: Optional[float] = None,
        masse_estimee_max_kg: Optional[float] = None,
        cout_matiere_max_eur: Optional[float] = None,
        indice_maintenance_max: Optional[float] = None,
        duree_vie_cible_h: Optional[float] = None,
        moteur_thermique_params: Optional[Dict[str, Any]] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "meta": {"orchestrateur": "SystemeComplet", "mode": "compatibilite_calculable"},
            "entrees": {
                "mission_batterie": {
                    "distance_km": distance_km,
                    "conso_kwh_km": conso_kwh_km,
                    "puissance_moyenne_kw": puissance_moyenne_kw,
                    "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
                    "temps_charge_cible_h": temps_charge_cible_h,
                    "puissance_pic_kw": puissance_pic_kw,
                    "duree_pic_s": duree_pic_s,
                    "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
                },
                "architecture": {
                    "longueur_dispo_m": longueur_dispo_m,
                    "largeur_dispo_m": largeur_dispo_m,
                    "hauteur_dispo_m": hauteur_dispo_m,
                },
                "boite": {
                    "rapports_boite_candidates": list(rapports_boite_candidates) if rapports_boite_candidates is not None else None,
                    "moment_flechissant_nm": moment_flechissant_nm,
                },
                "puissance_bus_dc_w": puissance_elec_alt_cible_w,
                "production_electrique_sortie_w": puissance_elec_alt_cible_w,
                "moteur_thermique_criteres": {
                    "pression_max_pa": pression_max_pa,
                },
            },
            "sous_systemes": {},
            "liaisons": {},
            "synthese": {},
            "cao": {"solidworks_ready_detaille": False, "moteur_thermique": {}},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        p_trac = _vehicle_power_w(
            masse_kg=masse_kg,
            vitesse_ms=vitesse_ms,
            acceleration_ms2=acceleration_ms2,
            angle_pente=angle_pente,
            angle_unite=angle_unite,
            coef_roulement=coef_roulement,
            coef_trainee_aero_cda=coef_trainee_aero_cda,
        )
        if p_trac is None and _is_finite(puissance_moyenne_kw):
            p_trac = float(puissance_moyenne_kw) * 1000.0

        p_aux = float(puissance_auxiliaire_w or 0.0)
        p_bus = _safe_float(puissance_elec_alt_cible_w)
        if p_bus is None:
            p_bus = p_trac + p_aux if p_trac is not None else None

        if p_trac is None:
            _push_inconnue(report, "partielles", "traction", "Masse et vitesse requises pour fermer la puissance de traction.")
        report["sous_systemes"]["traction"] = {
            "puissance_traction_w": p_trac,
            "puissance_auxiliaire_w": p_aux,
        }

        arch_report = None
        if self.architecture is not None and hasattr(self.architecture, "analyser"):
            try:
                arch_report = self.architecture.analyser(
                    puissance_cible_w=p_trac,
                    regime_tr_min=vitesse_moteur_thermique_rpm,
                    pme_pa=pme_pa,
                    vitesse_piston_max_ms=vitesse_piston_max_ms,
                    longueur_dispo_m=longueur_dispo_m,
                    largeur_dispo_m=largeur_dispo_m,
                    architectures_autorisees=architectures_autorisees,
                    architecture_forcee=architecture_forcee,
                    horizon_usage_h=horizon_usage_h,
                    pression_max_pa=pression_max_pa,
                    contrainte_admissible_pa=contrainte_admissible_pa,
                    densite_materiau_kg_m3=densite_materiau_kg_m3,
                    cout_matiere_eur_kg=cout_matiere_eur_kg,
                    rendement_indique_cible_min=rendement_indique_cible_min,
                    rendement_mecanique_cible_min=rendement_mecanique_cible_min,
                    masse_estimee_max_kg=masse_estimee_max_kg,
                    cout_matiere_max_eur=cout_matiere_max_eur,
                    indice_maintenance_max=indice_maintenance_max,
                    duree_vie_cible_h=duree_vie_cible_h,
                )
                report["sous_systemes"]["architecture"] = arch_report
            except Exception as exc:
                _push_inconnue(report, "partielles", "architecture", str(exc))

        mt_def = None
        if self.moteur_thermique is not None and hasattr(self.moteur_thermique, "definir_depuis_exigences") and p_trac is not None and _is_finite(vitesse_moteur_thermique_rpm) and _is_finite(pme_pa):
            try:
                mt_def = self.moteur_thermique.definir_depuis_exigences(
                    puissance_visee_w=p_trac,
                    type_puissance="frein",
                    rpm=float(vitesse_moteur_thermique_rpm),
                    pression_moyenne_effective_pa=float(pme_pa),
                    temps_moteur=int(getattr(self.moteur_thermique, "temps_moteur", 4) or 4),
                    rendement_mecanique=getattr(self.moteur_thermique, "rendement_mecanique_nominal", None) or rendement_mecanique_cible_min or 0.85,
                    vitesse_piston_max_ms=vitesse_piston_max_ms,
                    ratio_course_alesage_max=getattr(self.moteur_thermique, "ratio_course_alesage_max", None),
                    ratio_course_alesage_cible=getattr(self.moteur_thermique, "ratio_course_alesage_cible", None),
                    L_max_m=longueur_dispo_m,
                    W_max_m=largeur_dispo_m,
                    architectures_autorisees=tuple(architectures_autorisees) if architectures_autorisees is not None else None,
                    architecture_forcee=architecture_forcee,
                    pression_max_pa=pression_max_pa,
                    contrainte_admissible_pa=contrainte_admissible_pa,
                    facteur_securite_cylindre=getattr(self.moteur_thermique, "facteur_securite_cylindre", 1.5),
                    densite_materiau_kg_m3=densite_materiau_kg_m3,
                    cout_matiere_eur_kg=cout_matiere_eur_kg,
                    rendement_indique_cible_min=rendement_indique_cible_min,
                    rendement_mecanique_cible_min=rendement_mecanique_cible_min,
                    masse_estimee_max_kg=masse_estimee_max_kg,
                    cout_matiere_max_eur=cout_matiere_max_eur,
                    indice_maintenance_max=indice_maintenance_max,
                    duree_vie_cible_h=duree_vie_cible_h,
                )
            except Exception as exc:
                _push_inconnue(report, "partielles", "moteur_thermique_definition", str(exc))
        else:
            _push_inconnue(report, "partielles", "moteur_thermique_definition", "Puissance, regime et PME requis pour definir le moteur thermique.")

        moteur_effectif = _safe_dict(mt_def).get("moteur_defini") if isinstance(mt_def, dict) else None
        if moteur_effectif is None:
            moteur_effectif = self.moteur_thermique

        mt_point = None
        if moteur_effectif is not None and hasattr(moteur_effectif, "analyser_point_de_fonctionnement"):
            try:
                mt_point = moteur_effectif.analyser_point_de_fonctionnement(
                    rpm=vitesse_moteur_thermique_rpm,
                    pression_moyenne_effective_pa=pme_pa,
                    pression_max_pa=pression_max_pa,
                )
                report["sous_systemes"]["moteur_thermique"] = mt_point
            except Exception as exc:
                _push_inconnue(report, "partielles", "moteur_thermique_point", str(exc))

        alt_report = None
        if self.alternateur is not None and hasattr(self.alternateur, "analyser_pour_bus_dc") and p_bus is not None:
            try:
                alt_report = self.alternateur.analyser_pour_bus_dc(
                    puissance_bus_dc_w=p_bus,
                    vitesse_rotation_rpm=vitesse_alternateur_rpm or ((vitesse_moteur_thermique_rpm or 0.0) * (rapport_vitesse_alt_sur_moteur or 1.0)),
                    tension_bus_dc_v=tension_bus_dc_v,
                    batterie=self.batterie,
                    moteur=self.moteur_electrique,
                    energie_a_recharger_kwh=energie_utile_imposee_kwh,
                )
                report["sous_systemes"]["alternateur"] = alt_report
            except Exception as exc:
                _push_inconnue(report, "partielles", "alternateur", str(exc))

        batt_report = None
        if self.batterie is not None and hasattr(self.batterie, "analyser_dimensionnement"):
            try:
                batt_report = self.batterie.analyser_dimensionnement(
                    distance_km=distance_km,
                    conso_kwh_km=conso_kwh_km,
                    puissance_moyenne_kw=puissance_moyenne_kw,
                    vitesse_moyenne_kmh=vitesse_moyenne_kmh,
                    temps_charge_cible_h=temps_charge_cible_h,
                    puissance_pic_kw=puissance_pic_kw,
                    duree_pic_s=duree_pic_s,
                    energie_utile_imposee_kwh=energie_utile_imposee_kwh,
                )
                report["sous_systemes"]["batterie"] = batt_report
            except Exception as exc:
                _push_inconnue(report, "partielles", "batterie", str(exc))

        mt_dim = _safe_dict(_safe_dict(mt_point).get("dimensionnement"))
        mt_conc = _safe_dict(_safe_dict(mt_point).get("conception"))
        mt_res = _safe_dict(_safe_dict(mt_point).get("resultats"))
        best_arch = _safe_dict(_safe_dict(arch_report).get("meilleur"))
        batt_dim = _safe_dict(_safe_dict(batt_report).get("dimensionnement"))
        alt_bus = _safe_dict(_safe_dict(alt_report).get("bus_dc"))
        alt_out = _safe_dict(_safe_dict(alt_report).get("sortie_dc"))

        architecture_nom = mt_conc.get("architecture") or best_arch.get("architecture") or getattr(moteur_effectif, "architecture", None)
        n_cyl = _safe_int(mt_conc.get("nombre_cylindres")) or _safe_int(best_arch.get("N_cyl")) or _safe_int(getattr(moteur_effectif, "nombre_cylindres", None))
        bore_m = _safe_float(mt_conc.get("alesage_m")) or _safe_float(getattr(moteur_effectif, "alesage_m", None))
        course_m = _safe_float(mt_conc.get("course_m")) or _safe_float(getattr(moteur_effectif, "course_m", None))
        cyl_tot_m3 = _safe_float(mt_dim.get("cylindree_totale_m3"))
        if cyl_tot_m3 is None and bore_m is not None and course_m is not None and n_cyl is not None:
            cyl_tot_m3 = math.pi * bore_m * bore_m * course_m * float(n_cyl) / 4.0
        p_mot_req = _safe_float(mt_res.get("puissance_frein_estimee_W")) or p_trac
        rpm_nom = _safe_float(vitesse_moteur_thermique_rpm) or _safe_float(getattr(moteur_effectif, "rpm_nominal", None))
        couple_req = None
        if p_mot_req is not None and rpm_nom is not None and rpm_nom > 0.0:
            omega = 2.0 * math.pi * rpm_nom / 60.0
            couple_req = p_mot_req / omega

        report["liaisons"] = {
            "bus_dc": {
                "P_bus_dc_design_w": alt_bus.get("puissance_bus_dc_W") or p_bus,
                "V_bus_dc_v": alt_bus.get("tension_bus_dc_V") or tension_bus_dc_v or _safe_float(_safe_dict(batt_dim).get("tension_nominale_v")),
                "scenario_bus_dc": scenario_bus_dc,
                "energie_a_recharger_kwh": energie_utile_imposee_kwh,
            },
            "alternateur": {
                "vitesse_rotation_rpm": vitesse_alternateur_rpm or ((vitesse_moteur_thermique_rpm or 0.0) * (rapport_vitesse_alt_sur_moteur or 1.0)),
            },
            "moteur_thermique_exigences": {
                "rpm_moteur_thermique": rpm_nom,
            },
        }

        report["synthese"] = {
            "vehicule": {
                "puissance_bus_dc_design_w": alt_bus.get("puissance_bus_dc_W") or p_bus,
                "tension_bus_dc_v": alt_bus.get("tension_bus_dc_V") or tension_bus_dc_v or _safe_float(_safe_dict(batt_dim).get("tension_nominale_v")),
            },
            "batterie": {
                "energie_utile_kwh": _safe_float(batt_dim.get("energie_utile_kwh")) or energie_utile_imposee_kwh,
                "tension_nominale_v": _safe_float(batt_dim.get("tension_nominale_v")) or tension_bus_dc_v,
            },
            "alternateur": {
                "P_electrique_sortie_W": _safe_float(alt_out.get("puissance_sortie_dc_W")) or p_bus,
                "vitesse_rotation_rpm": report["liaisons"]["alternateur"]["vitesse_rotation_rpm"],
            },
            "moteur_thermique": {
                "architecture": architecture_nom,
                "nombre_cylindres": n_cyl,
                "alesage_m": bore_m,
                "course_m": course_m,
                "rpm_nominal": rpm_nom,
                "pme_pa": _safe_float(pme_pa),
                "cylindree_totale_cc": cyl_tot_m3 * 1e6 if cyl_tot_m3 is not None else None,
                "puissance_requise_W": p_mot_req,
                "couple_requis_Nm": couple_req,
                "couple_max_Nm": _safe_float(mt_dim.get("couple_max_Nm")) or couple_req,
                "epaisseur_cylindre_retenue_m": _safe_float(mt_dim.get("epaisseur_cylindre_retenue_m")),
                "pression_max_pa": _safe_float(pression_max_pa),
            },
        }

        report["cao"]["moteur_thermique"] = {
            "alesage_mm": bore_m * 1000.0 if bore_m is not None else None,
            "course_mm": course_m * 1000.0 if course_m is not None else None,
        }
        return report
