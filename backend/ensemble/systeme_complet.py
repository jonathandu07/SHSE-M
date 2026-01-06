# backend/ensemble/systeme_complet.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Literal, Tuple, List, Sequence
import math


# ============================================================
# Imports robustes (adapte si ton projet a une arbo différente)
# ============================================================

try:
    # Composants
    from backend.components.moteur_electrique import (
        MoteurElectrique,
        calcul_demande_moteur_depuis_vehicule,
        verifie_moteur_sur_demande,
    )
    from backend.components.batterie import Batterie
    from backend.components.alternateur import Alternateur
    from backend.components.moteur_thermique import MoteurThermique
    from backend.components.boite_crabots import BoiteCrabots
    from backend.components.architecture import Architecture

    # Modules (réutilisation quand disponibles)
    from backend.modules.moteur_thermique.calcul_cylindree import calcul_cylindree_totale

except Exception:
    from components.moteur_electrique import (
        MoteurElectrique,
        calcul_demande_moteur_depuis_vehicule,
        verifie_moteur_sur_demande,
    )
    from components.batterie import Batterie
    from components.alternateur import Alternateur
    from components.moteur_thermique import MoteurThermique
    from components.boite_crabots import BoiteCrabots
    from components.architecture import Architecture

    try:
        from modules.moteur_thermique.calcul_cylindree import calcul_cylindree_totale
    except Exception:
        calcul_cylindree_totale = None  # type: ignore


# ============================================================
# Helpers généraux
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strict: bool = True) -> float:
    v = _require_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    if "inconnues" not in rapport:
        rapport["inconnues"] = {"impossibles": [], "partielles": []}
    if categorie not in rapport["inconnues"]:
        rapport["inconnues"][categorie] = []
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

    inc = rapport.get("inconnues", {})
    inc["impossibles"] = dedup(list(inc.get("impossibles", []) or []))
    inc["partielles"] = dedup(list(inc.get("partielles", []) or []))
    rapport["inconnues"] = inc


def _merge_inconnues(dst: Dict[str, Any], src: Optional[Dict[str, Any]], *, prefix: str) -> None:
    if not isinstance(src, dict):
        return
    inc = src.get("inconnues", {})
    for cat in ("impossibles", "partielles"):
        for it in (inc.get(cat, []) or []):
            dst["inconnues"][cat].append(
                {
                    "nom": f"{prefix} :: {it.get('nom', '')}",
                    "raison": str(it.get("raison", "")),
                }
            )


def _fallback_cylindree_totale(alesage_m: float, course_m: float, nombre_cylindres: int) -> float:
    return (math.pi / 4.0) * alesage_m * alesage_m * course_m * max(1, int(nombre_cylindres))


def _cylindree_totale_m3(alesage_m: float, course_m: float, nombre_cylindres: int) -> float:
    if calcul_cylindree_totale is not None:
        try:
            return float(calcul_cylindree_totale(alesage_m, course_m, int(nombre_cylindres)))
        except Exception:
            return _fallback_cylindree_totale(alesage_m, course_m, int(nombre_cylindres))
    return _fallback_cylindree_totale(alesage_m, course_m, int(nombre_cylindres))


# ============================================================
# Modèle système complet
# ============================================================

ModeElectriqueAlternateur = Literal["triphase_ac", "monophase_ac", "dc"]
ScenarioBusDC = Literal["traction", "charge", "max", "traction_plus_charge"]


@dataclass(frozen=True)
class SystemeComplet:
    """
    Chaîne visée :
    moteur électrique -> bus DC -> batterie -> alternateur -> boîte à crabots -> moteur thermique -> architecture.
    Ne calcule que ce qui est calculable avec les entrées fournies et les composants existants.
    """

    moteur_electrique: MoteurElectrique
    batterie: Batterie
    alternateur: Alternateur
    moteur_thermique: MoteurThermique

    boite_crabots: Optional[BoiteCrabots] = None
    architecture: Optional[Architecture] = None

    def analyser(
        self,
        *,
        # A) Point véhicule
        masse_kg: Optional[float] = None,
        vitesse_ms: Optional[float] = None,
        acceleration_ms2: Optional[float] = None,
        angle_pente: float = 0.0,
        angle_unite: Literal["rad", "deg"] = "rad",
        coef_roulement: Optional[float] = None,
        coef_trainee_aero_cda: Optional[float] = None,
        densite_air: float = 1.2,
        gravite: float = 9.80665,
        rayon_roue_m: Optional[float] = None,
        rapport_reduction_global: Optional[float] = None,
        rendement_transmission: Optional[float] = None,
        nb_roues_motrices: int = 2,
        nb_moteurs_electriques: int = 1,
        pertes_fixes_transmission_w: float = 0.0,
        couple_pertes_transmission_nm: float = 0.0,
        marge_puissance: float = 0.0,
        marge_couple: float = 0.0,
        puissance_auxiliaire_w: float = 0.0,

        # B) Mission batterie
        distance_km: Optional[float] = None,
        conso_kwh_km: Optional[float] = None,
        puissance_moyenne_kw: Optional[float] = None,
        vitesse_moyenne_kmh: Optional[float] = None,
        temps_charge_cible_h: Optional[float] = None,
        puissance_pic_kw: Optional[float] = None,
        duree_pic_s: Optional[float] = None,
        energie_utile_imposee_kwh: Optional[float] = None,
        calculer_puissance_charge_requise: bool = True,
        utiliser_puissance_traction_comme_pic_si_absente: bool = True,

        # C) Bus DC
        scenario_bus_dc: ScenarioBusDC = "max",
        tension_bus_dc_v: Optional[float] = None,

        # D) Alternateur
        mode_electrique_alternateur: ModeElectriqueAlternateur = "dc",
        vitesse_alternateur_rpm: Optional[float] = None,
        rapport_vitesse_alt_sur_moteur: Optional[float] = None,
        vitesse_moteur_thermique_rpm: Optional[float] = None,
        puissance_elec_alt_cible_w: Optional[float] = None,

        tension_alt_v: Optional[float] = None,
        courant_alt_a: Optional[float] = None,
        facteur_puissance_alt: float = 1.0,
        entree_puissance_ac: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
        courant_est_ligne: bool = True,
        rendement_liaison_meca_alt: float = 1.0,

        # E) Boîte à crabots (choix rapport)
        rapports_boite_candidates: Optional[Sequence[float]] = None,
        rendement_boite: Optional[float] = None,
        facteur_service_boite: float = 1.2,

        moment_flechissant_nm: Optional[float] = None,
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_axiale_roulement_N: Optional[float] = None,
        force_radiale_roulement_N: Optional[float] = None,

        # F) Architecture / moteur thermique
        pme_pa: Optional[float] = None,
        vitesse_piston_max_ms: Optional[float] = None,
        longueur_dispo_m: Optional[float] = None,
        largeur_dispo_m: Optional[float] = None,
        horizon_usage_h: float = 20000.0,

        # G) Pass-through moteur thermique
        moteur_thermique_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        rapport: Dict[str, Any] = {
            "entrees": {},
            "sous_systemes": {},
            "liaisons": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # 1) Traction (demande véhicule) + check moteurs
        # ------------------------------------------------------------
        traction: Optional[Dict[str, Any]] = None
        check_moteurs: Optional[Dict[str, Any]] = None

        conditions_traction = (
            masse_kg is not None
            and vitesse_ms is not None
            and acceleration_ms2 is not None
            and coef_roulement is not None
            and coef_trainee_aero_cda is not None
            and rayon_roue_m is not None
            and rapport_reduction_global is not None
            and rendement_transmission is not None
        )

        if conditions_traction:
            demande = calcul_demande_moteur_depuis_vehicule(
                masse_kg=_require_positive("masse_kg", masse_kg, strict=True),
                vitesse_ms=_require_finite("vitesse_ms", vitesse_ms),
                acceleration_ms2=_require_finite("acceleration_ms2", acceleration_ms2),
                angle_pente=_require_finite("angle_pente", angle_pente),
                angle_unite=angle_unite,
                coef_roulement=_require_positive("coef_roulement", coef_roulement, strict=False),
                coef_trainee_aero_cda=_require_positive("coef_trainee_aero_cda", coef_trainee_aero_cda, strict=False),
                densite_air=_require_positive("densite_air", densite_air, strict=True),
                gravite=_require_positive("gravite", gravite, strict=True),
                rayon_roue_m=_require_positive("rayon_roue_m", rayon_roue_m, strict=True),
                rapport_reduction_global=_require_positive("rapport_reduction_global", rapport_reduction_global, strict=True),
                rendement_transmission=_require_positive("rendement_transmission", rendement_transmission, strict=True),
                nb_roues_motrices=int(nb_roues_motrices),
                pertes_fixes_w=_require_finite("pertes_fixes_transmission_w", pertes_fixes_transmission_w),
                couple_pertes_nm=_require_finite("couple_pertes_transmission_nm", couple_pertes_transmission_nm),
            )

            traction = {"demande_totale": demande, "demande_par_moteur": None}

            nbm = int(nb_moteurs_electriques)
            if nbm >= 1:
                dm = dict(demande)
                dm["P_moteur_W"] = float(demande["P_moteur_W"]) / nbm
                dm["T_moteur_Nm"] = float(demande["T_moteur_Nm"]) / nbm
                traction["demande_par_moteur"] = dm

                check_moteurs = {
                    "nb_moteurs": nbm,
                    "check_par_moteur": verifie_moteur_sur_demande(
                        self.moteur_electrique,
                        dm,
                        marge_puissance=_require_finite("marge_puissance", marge_puissance),
                        marge_couple=_require_finite("marge_couple", marge_couple),
                    ),
                    "check_total_equivalent": verifie_moteur_sur_demande(
                        self.moteur_electrique,
                        demande,
                        marge_puissance=_require_finite("marge_puissance", marge_puissance),
                        marge_couple=_require_finite("marge_couple", marge_couple),
                    ),
                }
            else:
                _push_inconnue(rapport, "impossibles", "nb_moteurs_electriques", "nb_moteurs_electriques doit être >= 1.")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "demande traction",
                "Calculable si masse_kg, vitesse_ms, acceleration_ms2, coef_roulement, coef_trainee_aero_cda, rayon_roue_m, rapport_reduction_global, rendement_transmission.",
            )

        rapport["sous_systemes"]["traction"] = traction
        rapport["sous_systemes"]["check_moteurs"] = check_moteurs

        # ------------------------------------------------------------
        # 2) Puissance bus DC traction (depuis moteur électrique)
        # ------------------------------------------------------------
        P_bus_dc_traction_w: Optional[float] = None

        if traction and traction.get("demande_par_moteur"):
            dm = traction["demande_par_moteur"]
            nbm = int(max(1, nb_moteurs_electriques))

            eta = self.moteur_electrique.rendement_moteur
            pertes_fixes = self.moteur_electrique.pertes_fixes_w or 0.0

            if eta is None or not _is_finite(eta) or float(eta) <= 0.0 or float(eta) > 1.0:
                _push_inconnue(rapport, "partielles", "P_bus_dc_traction_w", "Calculable si moteur_electrique.rendement_moteur (0..1) est fourni.")
            else:
                Pm_par = float(dm["P_moteur_W"])
                Pin_par = (Pm_par + float(pertes_fixes)) / float(eta)
                P_bus_dc_traction_w = max(0.0, Pin_par * nbm + float(puissance_auxiliaire_w))
        else:
            _push_inconnue(rapport, "partielles", "P_bus_dc_traction_w", "Calculable si traction est calculée et rendement moteur est connu.")

        # ------------------------------------------------------------
        # 3) Batterie : dimensionnement (énergie + charge)
        # ------------------------------------------------------------
        puissance_pic_kw_eff = puissance_pic_kw
        if puissance_pic_kw_eff is None and utiliser_puissance_traction_comme_pic_si_absente and P_bus_dc_traction_w is not None:
            puissance_pic_kw_eff = float(P_bus_dc_traction_w) / 1000.0
            rapport["notes_modele"].append("puissance_pic_kw déduite du point traction (P_bus_dc_traction_w) car absente en entrée.")

        batterie_rapport = self.batterie.analyser_dimensionnement(
            distance_km=distance_km,
            conso_kwh_km=conso_kwh_km,
            puissance_moyenne_kw=puissance_moyenne_kw,
            vitesse_moyenne_kmh=vitesse_moyenne_kmh,
            temps_charge_cible_h=temps_charge_cible_h,
            puissance_pic_kw=puissance_pic_kw_eff,
            duree_pic_s=duree_pic_s,
            energie_utile_imposee_kwh=energie_utile_imposee_kwh,
            calculer_puissance_charge_requise=calculer_puissance_charge_requise,
        )
        rapport["sous_systemes"]["batterie"] = batterie_rapport
        _merge_inconnues(rapport, batterie_rapport, prefix="batterie")

        # ------------------------------------------------------------
        # 4) Besoins bus DC (traction / charge) => puissance DC à fournir par alternateur
        # ------------------------------------------------------------
        P_bus_dc_charge_w: Optional[float] = None
        P_bus_dc_design_w: Optional[float] = None

        P_charge_req_kw = (batterie_rapport.get("charge") or {}).get("puissance_charge_requise_kw")
        if _is_finite(P_charge_req_kw):
            P_bus_dc_charge_w = float(P_charge_req_kw) * 1000.0

        if puissance_elec_alt_cible_w is not None and _is_finite(puissance_elec_alt_cible_w):
            P_bus_dc_design_w = float(puissance_elec_alt_cible_w)
        else:
            if scenario_bus_dc == "traction":
                P_bus_dc_design_w = P_bus_dc_traction_w
            elif scenario_bus_dc == "charge":
                P_bus_dc_design_w = P_bus_dc_charge_w
            elif scenario_bus_dc == "traction_plus_charge":
                if P_bus_dc_traction_w is not None and P_bus_dc_charge_w is not None:
                    P_bus_dc_design_w = float(P_bus_dc_traction_w) + float(P_bus_dc_charge_w)
                else:
                    _push_inconnue(rapport, "partielles", "P_bus_dc_design_w", "traction_plus_charge nécessite traction ET charge calculées.")
            else:  # max
                if P_bus_dc_traction_w is not None and P_bus_dc_charge_w is not None:
                    P_bus_dc_design_w = max(float(P_bus_dc_traction_w), float(P_bus_dc_charge_w))
                else:
                    P_bus_dc_design_w = P_bus_dc_traction_w if P_bus_dc_traction_w is not None else P_bus_dc_charge_w

            if P_bus_dc_design_w is None:
                _push_inconnue(rapport, "partielles", "P_bus_dc_design_w", "Donner puissance_elec_alt_cible_w ou fournir traction/charge exploitables.")

        # Tension bus DC : entrée > moteur > batterie charge > batterie nominale
        Vbus_dc: Optional[float] = None
        if tension_bus_dc_v is not None:
            Vbus_dc = _require_positive("tension_bus_dc_v", tension_bus_dc_v, strict=True)
        else:
            if self.moteur_electrique.tension_bus_v is not None:
                Vbus_dc = float(self.moteur_electrique.tension_bus_v)
            elif self.batterie.tension_charge_v is not None:
                Vbus_dc = float(self.batterie.tension_charge_v)
            elif self.batterie.tension_nominale_v is not None:
                Vbus_dc = float(self.batterie.tension_nominale_v)

        if Vbus_dc is None:
            _push_inconnue(rapport, "partielles", "tension bus DC", "Donner tension_bus_dc_v ou fournir tension bus moteur/batterie.")

        # Energie à recharger (utile) : si disponible via batterie
        energie_a_recharger_kwh: Optional[float] = None
        dim = batterie_rapport.get("dimensionnement") or {}
        if _is_finite(dim.get("E_utile_finale_kwh")):
            energie_a_recharger_kwh = float(dim["E_utile_finale_kwh"])
        elif energie_utile_imposee_kwh is not None and _is_finite(energie_utile_imposee_kwh):
            energie_a_recharger_kwh = float(energie_utile_imposee_kwh)

        rapport["liaisons"]["bus_dc"] = {
            "P_bus_dc_traction_w": P_bus_dc_traction_w,
            "P_bus_dc_charge_w": P_bus_dc_charge_w,
            "scenario_bus_dc": scenario_bus_dc,
            "P_bus_dc_design_w": P_bus_dc_design_w,
            "V_bus_dc_v": Vbus_dc,
            "energie_a_recharger_kwh": energie_a_recharger_kwh,
        }

        # ------------------------------------------------------------
        # 5) Alternateur + boîte à crabots (si fournie) : choix rapport puis exigences moteur thermique
        # ------------------------------------------------------------
        alternateur_rapport: Optional[Dict[str, Any]] = None
        boite_rapport: Optional[Dict[str, Any]] = None
        chaine_rapport: Optional[Dict[str, Any]] = None

        rpm_alt: Optional[float] = None
        ratio_alt_sur_moteur: Optional[float] = rapport_vitesse_alt_sur_moteur
        couple_moteur_thermique_nm: Optional[float] = None
        P_moteur_thermique_w: Optional[float] = None

        # --- Chaîne complète via boîte (prioritaire) ---
        if (
            self.boite_crabots is not None
            and rapports_boite_candidates is not None
            and vitesse_moteur_thermique_rpm is not None
            and P_bus_dc_design_w is not None
            and Vbus_dc is not None
        ):
            chaine_rapport = self.boite_crabots.analyser_chaine_moteur_alternateur(
                alternateur=self.alternateur,
                batterie=self.batterie,
                puissance_bus_dc_w=float(P_bus_dc_design_w),
                tension_bus_dc_v=float(Vbus_dc),
                rpm_moteur=float(_require_positive("vitesse_moteur_thermique_rpm", vitesse_moteur_thermique_rpm, strict=True)),
                rapports=list(rapports_boite_candidates),
                energie_a_recharger_kwh=energie_a_recharger_kwh,
                rendement_boite=rendement_boite,
                facteur_service=float(_require_positive("facteur_service_boite", facteur_service_boite, strict=True)),
                moment_flechissant_nm=moment_flechissant_nm,
                inertie_primaire_kg_m2=inertie_primaire_kg_m2,
                inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
                delta_omega_rad_s=delta_omega_rad_s,
                temps_engagement_s=temps_engagement_s,
                force_axiale_roulement_N=force_axiale_roulement_N,
                force_radiale_roulement_N=force_radiale_roulement_N,
            )
            rapport["sous_systemes"]["chaine_moteur_alternateur"] = chaine_rapport
            _merge_inconnues(rapport, chaine_rapport, prefix="chaine_moteur_alternateur")

            best = (chaine_rapport or {}).get("meilleur")
            if isinstance(best, dict):
                alternateur_rapport = best.get("alternateur")
                boite_rapport = best.get("boite_crabots")
                resume = best.get("resume", {}) if isinstance(best.get("resume"), dict) else {}

                rpm_alt = resume.get("rpm_alternateur")
                ratio_alt_sur_moteur = resume.get("rapport")
                couple_moteur_thermique_nm = resume.get("couple_moteur_requis_Nm")
                P_moteur_thermique_w = resume.get("P_moteur_requis_W")
            else:
                _push_inconnue(rapport, "partielles", "chaine_moteur_alternateur", "Chaîne calculée mais aucun 'meilleur' exploitable.")

        else:
            rapport["sous_systemes"]["chaine_moteur_alternateur"] = None

        # --- Sinon alternateur simple ---
        if alternateur_rapport is None:
            if vitesse_alternateur_rpm is not None:
                rpm_alt = _require_positive("vitesse_alternateur_rpm", vitesse_alternateur_rpm, strict=True)
            else:
                if vitesse_moteur_thermique_rpm is not None and rapport_vitesse_alt_sur_moteur is not None:
                    rpm_mth = _require_positive("vitesse_moteur_thermique_rpm", vitesse_moteur_thermique_rpm, strict=True)
                    ratio_alt_sur_moteur = _require_positive("rapport_vitesse_alt_sur_moteur", rapport_vitesse_alt_sur_moteur, strict=True)
                    rpm_alt = rpm_mth * ratio_alt_sur_moteur
                else:
                    _push_inconnue(rapport, "partielles", "vitesse alternateur", "Donner vitesse_alternateur_rpm OU (rpm moteur + ratio).")

            if rpm_alt is not None:
                if mode_electrique_alternateur == "dc":
                    if Vbus_dc is None or P_bus_dc_design_w is None:
                        _push_inconnue(rapport, "partielles", "alternateur bus DC", "Nécessite Vbus_dc et P_bus_dc_design_w.")
                    else:
                        alternateur_rapport = self.alternateur.analyser_pour_bus_dc(
                            batterie=self.batterie,
                            puissance_bus_dc_w=float(P_bus_dc_design_w),
                            tension_bus_dc_v=float(Vbus_dc),
                            vitesse_rotation_rpm=float(rpm_alt),
                            energie_a_recharger_kwh=energie_a_recharger_kwh,
                        )
                else:
                    alternateur_rapport = self.alternateur.analyser_point_de_fonctionnement(
                        mode_electrique=mode_electrique_alternateur,
                        vitesse_rotation_rpm=float(rpm_alt),
                        vitesse_angulaire_rad_s=None,
                        tension_v=tension_alt_v,
                        courant_a=courant_alt_a,
                        facteur_puissance=facteur_puissance_alt,
                        entree_puissance_ac=entree_puissance_ac,
                        courant_est_ligne=courant_est_ligne,
                        puissance_electrique_cible_w=float(P_bus_dc_design_w) if P_bus_dc_design_w is not None else None,
                    )

        rapport["sous_systemes"]["alternateur"] = alternateur_rapport
        _merge_inconnues(rapport, alternateur_rapport, prefix="alternateur")

        # ------------------------------------------------------------
        # 6) Exigences moteur thermique (si pas de chaîne)
        # ------------------------------------------------------------
        if couple_moteur_thermique_nm is None or P_moteur_thermique_w is None:
            couple_alt_nm: Optional[float] = None
            P_alt_mec_w: Optional[float] = None

            if isinstance(alternateur_rapport, dict):
                res = alternateur_rapport.get("resultats", {}) if isinstance(alternateur_rapport.get("resultats"), dict) else {}
                couple_alt_nm = res.get("couple_mecanique_Nm")
                P_alt_mec_w = res.get("P_mecanique_W")

            eta_liaison = _require_positive("rendement_liaison_meca_alt", rendement_liaison_meca_alt, strict=True)

            if _is_finite(P_alt_mec_w):
                P_moteur_thermique_w = float(P_alt_mec_w) / float(eta_liaison)
            else:
                _push_inconnue(rapport, "partielles", "P_moteur_thermique_w", "Calculable si alternateur fournit P_mecanique_W.")

            if _is_finite(couple_alt_nm) and ratio_alt_sur_moteur is not None:
                ratio = _require_positive("rapport_vitesse_alt_sur_moteur", ratio_alt_sur_moteur, strict=True)
                couple_moteur_thermique_nm = (float(couple_alt_nm) * ratio) / float(eta_liaison)
            else:
                _push_inconnue(rapport, "partielles", "couple moteur thermique", "Calculable si couple alternateur + ratio connus.")

        rapport["liaisons"]["moteur_thermique_exigences"] = {
            "rpm_moteur_thermique": vitesse_moteur_thermique_rpm,
            "P_moteur_thermique_W": P_moteur_thermique_w,
            "couple_moteur_thermique_Nm": couple_moteur_thermique_nm,
            "rpm_alternateur": rpm_alt,
            "ratio_alt_sur_moteur": ratio_alt_sur_moteur,
        }

        # ------------------------------------------------------------
        # 7) Boîte : si pas de chaîne et boîte fournie, analyse au couple alternateur
        # ------------------------------------------------------------
        if boite_rapport is None and self.boite_crabots is not None:
            couple_alt_nm = None
            if isinstance(alternateur_rapport, dict):
                res = alternateur_rapport.get("resultats", {}) if isinstance(alternateur_rapport.get("resultats"), dict) else {}
                couple_alt_nm = res.get("couple_mecanique_Nm")

            if _is_finite(couple_alt_nm):
                boite_rapport = self.boite_crabots.analyser_point(
                    couple_nm=float(couple_alt_nm),
                    vitesse_rotation_tr_min=float(rpm_alt) if rpm_alt is not None else None,
                    calcul_forces_engrenage_actif=True,
                    moment_flechissant_nm=moment_flechissant_nm,
                    inertie_primaire_kg_m2=inertie_primaire_kg_m2,
                    inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
                    delta_omega_rad_s=delta_omega_rad_s,
                    temps_engagement_s=temps_engagement_s,
                    force_axiale_N=force_axiale_roulement_N,
                    force_radiale_N=force_radiale_roulement_N,
                )
            else:
                _push_inconnue(rapport, "partielles", "boite_crabots", "Analyse possible si couple alternateur calculable.")

        rapport["sous_systemes"]["boite_crabots"] = boite_rapport
        _merge_inconnues(rapport, boite_rapport, prefix="boite_crabots")

        # ------------------------------------------------------------
        # 8) Architecture : proposition bore/course/N (si fournie)
        # ------------------------------------------------------------
        arch_rapport: Optional[Dict[str, Any]] = None
        moteur_thermique_effectif = self.moteur_thermique

        if self.architecture is not None:
            if P_moteur_thermique_w is None or not _is_finite(P_moteur_thermique_w):
                _push_inconnue(rapport, "partielles", "architecture", "Nécessite P_moteur_thermique_w.")
            elif vitesse_moteur_thermique_rpm is None:
                _push_inconnue(rapport, "impossibles", "architecture::rpm", "Nécessite vitesse_moteur_thermique_rpm.")
            elif pme_pa is None:
                _push_inconnue(rapport, "partielles", "architecture::pme", "Nécessite pme_pa (entrée modèle).")
            else:
                arch_rapport = self.architecture.analyser(
                    puissance_cible_w=float(P_moteur_thermique_w),
                    regime_tr_min=float(_require_positive("vitesse_moteur_thermique_rpm", vitesse_moteur_thermique_rpm, strict=True)),
                    pme_pa=float(pme_pa),
                    vitesse_piston_max_ms=vitesse_piston_max_ms,
                    longueur_dispo_m=longueur_dispo_m,
                    largeur_dispo_m=largeur_dispo_m,
                    horizon_usage_h=float(horizon_usage_h),
                )
                best = (arch_rapport or {}).get("meilleur")
                if isinstance(best, dict):
                    try:
                        bore_m = _require_positive("bore_mm", best.get("bore_mm"), strict=True) / 1000.0
                        course_m = _require_positive("course_mm", best.get("course_mm"), strict=True) / 1000.0
                        N_cyl = int(best.get("N_cyl", 1))
                        if N_cyl < 1:
                            raise ValueError("N_cyl < 1")
                        moteur_thermique_effectif = replace(moteur_thermique_effectif, alesage_m=bore_m, course_m=course_m, nombre_cylindres=N_cyl)
                    except Exception:
                        _push_inconnue(rapport, "partielles", "moteur_thermique(géométrie)", "Architecture 'meilleur' inexploitable (format/valeurs).")
        else:
            _push_inconnue(rapport, "partielles", "architecture", "Composant Architecture non fourni.")

        rapport["sous_systemes"]["architecture"] = arch_rapport
        _merge_inconnues(rapport, arch_rapport, prefix="architecture")

        # ------------------------------------------------------------
        # 9) PME requise (si non fournie) : calcul inverse (P, Vd, cycles/s)
        # ------------------------------------------------------------
        pme_utilisee_ou_requise_pa: Optional[float] = None
        rpm_th = vitesse_moteur_thermique_rpm

        if pme_pa is not None and _is_finite(pme_pa):
            pme_utilisee_ou_requise_pa = float(pme_pa)
        else:
            if _is_finite(P_moteur_thermique_w) and rpm_th is not None:
                if moteur_thermique_effectif.alesage_m is not None and moteur_thermique_effectif.course_m is not None:
                    bore = float(moteur_thermique_effectif.alesage_m)
                    course = float(moteur_thermique_effectif.course_m)
                    N = int(moteur_thermique_effectif.nombre_cylindres)
                    temps = int(moteur_thermique_effectif.temps_moteur)

                    Vd_tot = _cylindree_totale_m3(bore, course, N)
                    rpm = float(_require_positive("vitesse_moteur_thermique_rpm", rpm_th, strict=True))
                    f_cycles = (rpm / 60.0) / 2.0 if temps == 4 else (rpm / 60.0)

                    if Vd_tot > 1e-12 and f_cycles > 1e-12:
                        pme_utilisee_ou_requise_pa = float(P_moteur_thermique_w) / (Vd_tot * f_cycles)
                    else:
                        _push_inconnue(rapport, "partielles", "PME requise", "Vd_tot ou f_cycles nul.")
                else:
                    _push_inconnue(rapport, "partielles", "PME requise", "Nécessite alesage_m/course_m.")
            else:
                _push_inconnue(rapport, "partielles", "PME requise", "Nécessite P_moteur_thermique_w et rpm moteur thermique.")

        rapport["liaisons"]["pme"] = {"pme_pa_utilisee_ou_requise": pme_utilisee_ou_requise_pa}

        # ------------------------------------------------------------
        # 10) Moteur thermique : analyse point (pass-through)
        # ------------------------------------------------------------
        moteur_th_rapport: Optional[Dict[str, Any]] = None
        if rpm_th is not None:
            params = dict(moteur_thermique_params or {})
            moteur_th_rapport = moteur_thermique_effectif.analyser_point_de_fonctionnement(
                rpm=float(_require_positive("vitesse_moteur_thermique_rpm", rpm_th, strict=True)),
                pression_moyenne_effective_pa=pme_utilisee_ou_requise_pa,
                **params,
            )
            rapport["sous_systemes"]["moteur_thermique"] = moteur_th_rapport
            _merge_inconnues(rapport, moteur_th_rapport, prefix="moteur_thermique")
        else:
            rapport["sous_systemes"]["moteur_thermique"] = None
            _push_inconnue(rapport, "partielles", "moteur thermique", "Nécessite vitesse_moteur_thermique_rpm.")

        _dedup_inconnues(rapport)
        return rapport


if __name__ == "__main__":
    # Exemple minimal (valeurs d'appel seulement, pas une datasheet)
    systeme = SystemeComplet(
        moteur_electrique=MoteurElectrique(
            puissance_max_w=10000.0,
            regime_max_rpm=6000.0,
            couple_max_nm=30.0,
            tension_bus_v=400.0,
            rendement_moteur=0.92,
            pertes_fixes_w=100.0,
        ),
        batterie=Batterie(
            tension_nominale_v=400.0,
            capacite_nominale_ah=100.0,
            rendement_charge=0.9,
            tension_charge_v=420.0,
        ),
        alternateur=Alternateur(
            connexion="etoile",
            nombre_poles=12,
        ),
        moteur_thermique=MoteurThermique(
            nombre_cylindres=1,
            temps_moteur=4,
            alesage_m=0.08,
            course_m=0.08,
        ),
        architecture=None,
        boite_crabots=None,
    )

    rep = systeme.analyser(
        masse_kg=1200.0,
        vitesse_ms=20.0,
        acceleration_ms2=0.5,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.65,
        rayon_roue_m=0.32,
        rapport_reduction_global=9.0,
        rendement_transmission=0.95,
        nb_moteurs_electriques=4,
        vitesse_moteur_thermique_rpm=3000.0,
        rapport_vitesse_alt_sur_moteur=2.0,
        temps_charge_cible_h=1.0,
    )

    print("Inconnues impossibles:", len(rep["inconnues"]["impossibles"]))
    print("Inconnues partielles:", len(rep["inconnues"]["partielles"]))
    print("Sous-systèmes:", list(rep["sous_systemes"].keys()))
