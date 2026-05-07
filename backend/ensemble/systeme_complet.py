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
    from backend.components.moteur_electrique.moteur_electrique import (
        MoteurElectrique,
        calcul_demande_moteur_depuis_vehicule,
        verifie_moteur_sur_demande,
    )
    from backend.components.batterie.batterie import Batterie
    from backend.components.alternateur.alternateur import Alternateur
    from backend.components.moteur_thermique.moteur_thermique import MoteurThermique
    from backend.components.boite_crabots.boite_crabots import BoiteCrabots
    from backend.components.architechture.architecture import Architecture

    # Modules
    from backend.components.moteur_thermique.modules.calcul_cylindree import calcul_cylindree_totale

except Exception:
    from backend.components.moteur_electrique.moteur_electrique import (
        MoteurElectrique,
        calcul_demande_moteur_depuis_vehicule,
        verifie_moteur_sur_demande,
    )
    from backend.components.batterie.batterie import Batterie
    from backend.components.alternateur.alternateur import Alternateur
    from backend.components.moteur_thermique.moteur_thermique import MoteurThermique
    from backend.components.boite_crabots.boite_crabots import BoiteCrabots
    from backend.components.architechture.architecture import Architecture

    try:
        from backend.components.moteur_thermique.modules.calcul_cylindree import calcul_cylindree_totale
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


def _require_int_positive(name: str, x: Any, *, strict: bool = True) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    ok = x > 0 if strict else x >= 0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return int(x)


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


def _safe_dict(d: Any) -> Dict[str, Any]:
    return d if isinstance(d, dict) else {}


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int):
        return int(x)
    if _is_finite(x):
        xi = int(float(x))
        return xi
    return None


def _safe_bool(x: Any) -> Optional[bool]:
    if isinstance(x, bool):
        return x
    return None


def _add_note(rapport: Dict[str, Any], message: str) -> None:
    if "notes_modele" not in rapport:
        rapport["notes_modele"] = []
    rapport["notes_modele"].append(str(message))


def _first_finite(*vals: Any) -> Optional[float]:
    for v in vals:
        if _is_finite(v):
            return float(v)
    return None


def _first_non_none(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _bool_max_all(values: Sequence[Optional[bool]]) -> Optional[bool]:
    """
    Agrégation conservatrice :
    - si au moins un False => False
    - sinon si au moins un True => True
    - sinon None
    """
    seen_true = False
    for v in values:
        if v is False:
            return False
        if v is True:
            seen_true = True
    return True if seen_true else None


# ============================================================
# Modèle système complet
# ============================================================

ModeElectriqueAlternateur = Literal["triphase_ac", "monophase_ac", "dc"]
ScenarioBusDC = Literal["traction", "charge", "max", "traction_plus_charge"]


@dataclass(frozen=True)
class SystemeComplet:
    """
    Chaîne visée :
    moteur électrique -> bus DC -> batterie -> alternateur -> boîte à crabots
    -> moteur thermique -> architecture.

    Le système :
    - calcule ce qui est calculable ;
    - n'invente pas les données manquantes ;
    - consolide les résultats techniques et les critères globaux :
      puissance / énergie / nombre de cylindres / géométrie / cohérence système.
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

        # E) Boîte à crabots
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

        architectures_autorisees: Optional[List[Literal["L", "V", "W", "Etoile"]]] = None,
        architecture_forcee: Optional[Literal["L", "V", "W", "Etoile"]] = None,
        poids_maintenance: float = 1.0,
        poids_masse: float = 1.0,
        poids_cout_matiere: float = 1.0,
        poids_compacite: float = 1.0,
        poids_fiabilite: float = 1.0,
        poids_rendement: float = 1.0,

        # Critères moteur thermique globaux
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

        # G) Pass-through moteur thermique
        moteur_thermique_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        rapport: Dict[str, Any] = {
            "entrees": {},
            "sous_systemes": {},
            "liaisons": {},
            "synthese": {},
            "criteres_conception": {},
            "cao": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        rapport["entrees"] = {
            "vehicule": {
                "masse_kg": masse_kg,
                "vitesse_ms": vitesse_ms,
                "acceleration_ms2": acceleration_ms2,
                "angle_pente": angle_pente,
                "angle_unite": angle_unite,
                "coef_roulement": coef_roulement,
                "coef_trainee_aero_cda": coef_trainee_aero_cda,
                "densite_air": densite_air,
                "gravite": gravite,
                "rayon_roue_m": rayon_roue_m,
                "rapport_reduction_global": rapport_reduction_global,
                "rendement_transmission": rendement_transmission,
                "nb_roues_motrices": nb_roues_motrices,
                "nb_moteurs_electriques": nb_moteurs_electriques,
                "pertes_fixes_transmission_w": pertes_fixes_transmission_w,
                "couple_pertes_transmission_nm": couple_pertes_transmission_nm,
                "marge_puissance": marge_puissance,
                "marge_couple": marge_couple,
                "puissance_auxiliaire_w": puissance_auxiliaire_w,
            },
            "batterie": {
                "distance_km": distance_km,
                "conso_kwh_km": conso_kwh_km,
                "puissance_moyenne_kw": puissance_moyenne_kw,
                "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
                "temps_charge_cible_h": temps_charge_cible_h,
                "puissance_pic_kw": puissance_pic_kw,
                "duree_pic_s": duree_pic_s,
                "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
                "calculer_puissance_charge_requise": calculer_puissance_charge_requise,
                "utiliser_puissance_traction_comme_pic_si_absente": utiliser_puissance_traction_comme_pic_si_absente,
            },
            "bus_dc": {
                "scenario_bus_dc": scenario_bus_dc,
                "tension_bus_dc_v": tension_bus_dc_v,
            },
            "alternateur": {
                "mode_electrique_alternateur": mode_electrique_alternateur,
                "vitesse_alternateur_rpm": vitesse_alternateur_rpm,
                "rapport_vitesse_alt_sur_moteur": rapport_vitesse_alt_sur_moteur,
                "vitesse_moteur_thermique_rpm": vitesse_moteur_thermique_rpm,
                "puissance_elec_alt_cible_w": puissance_elec_alt_cible_w,
                "tension_alt_v": tension_alt_v,
                "courant_alt_a": courant_alt_a,
                "facteur_puissance_alt": facteur_puissance_alt,
                "entree_puissance_ac": entree_puissance_ac,
                "courant_est_ligne": courant_est_ligne,
                "rendement_liaison_meca_alt": rendement_liaison_meca_alt,
            },
            "boite_crabots": {
                "rapports_boite_candidates": list(rapports_boite_candidates) if rapports_boite_candidates is not None else None,
                "rendement_boite": rendement_boite,
                "facteur_service_boite": facteur_service_boite,
                "moment_flechissant_nm": moment_flechissant_nm,
                "inertie_primaire_kg_m2": inertie_primaire_kg_m2,
                "inertie_secondaire_kg_m2": inertie_secondaire_kg_m2,
                "delta_omega_rad_s": delta_omega_rad_s,
                "temps_engagement_s": temps_engagement_s,
                "force_axiale_roulement_N": force_axiale_roulement_N,
                "force_radiale_roulement_N": force_radiale_roulement_N,
            },
            "architecture": {
                "pme_pa": pme_pa,
                "vitesse_piston_max_ms": vitesse_piston_max_ms,
                "longueur_dispo_m": longueur_dispo_m,
                "largeur_dispo_m": largeur_dispo_m,
                "horizon_usage_h": horizon_usage_h,
                "architectures_autorisees": architectures_autorisees,
                "architecture_forcee": architecture_forcee,
                "poids_maintenance": poids_maintenance,
                "poids_masse": poids_masse,
                "poids_cout_matiere": poids_cout_matiere,
                "poids_compacite": poids_compacite,
                "poids_fiabilite": poids_fiabilite,
                "poids_rendement": poids_rendement,
            },
            "moteur_thermique_criteres": {
                "pression_max_pa": pression_max_pa,
                "contrainte_admissible_pa": contrainte_admissible_pa,
                "densite_materiau_kg_m3": densite_materiau_kg_m3,
                "cout_matiere_eur_kg": cout_matiere_eur_kg,
                "rendement_indique_cible_min": rendement_indique_cible_min,
                "rendement_mecanique_cible_min": rendement_mecanique_cible_min,
                "masse_estimee_max_kg": masse_estimee_max_kg,
                "cout_matiere_max_eur": cout_matiere_max_eur,
                "indice_maintenance_max": indice_maintenance_max,
                "duree_vie_cible_h": duree_vie_cible_h,
            },
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
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "nb_moteurs_electriques",
                    "nb_moteurs_electriques doit être >= 1.",
                )
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

            eta = getattr(self.moteur_electrique, "rendement_moteur", None)
            pertes_fixes = getattr(self.moteur_electrique, "pertes_fixes_w", None) or 0.0

            if eta is None or not _is_finite(eta) or float(eta) <= 0.0 or float(eta) > 1.0:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "P_bus_dc_traction_w",
                    "Calculable si moteur_electrique.rendement_moteur (0..1) est fourni.",
                )
            else:
                Pm_par = float(dm["P_moteur_W"])
                Pin_par = (Pm_par + float(pertes_fixes)) / float(eta)
                P_bus_dc_traction_w = max(0.0, Pin_par * nbm + float(puissance_auxiliaire_w))
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "P_bus_dc_traction_w",
                "Calculable si traction est calculée et rendement moteur est connu.",
            )

        # ------------------------------------------------------------
        # 3) Batterie : dimensionnement (énergie + charge)
        # ------------------------------------------------------------
        puissance_pic_kw_eff = puissance_pic_kw
        if puissance_pic_kw_eff is None and utiliser_puissance_traction_comme_pic_si_absente and P_bus_dc_traction_w is not None:
            puissance_pic_kw_eff = float(P_bus_dc_traction_w) / 1000.0
            _add_note(
                rapport,
                "puissance_pic_kw déduite du point traction (P_bus_dc_traction_w) car absente en entrée."
            )

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
        # 4) Besoins bus DC
        # ------------------------------------------------------------
        P_bus_dc_charge_w: Optional[float] = None
        P_bus_dc_design_w: Optional[float] = None

        P_charge_req_kw = (_safe_dict(batterie_rapport.get("charge"))).get("puissance_charge_requise_kw")
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
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "P_bus_dc_design_w",
                        "traction_plus_charge nécessite traction ET charge calculées.",
                    )
            else:  # max
                if P_bus_dc_traction_w is not None and P_bus_dc_charge_w is not None:
                    P_bus_dc_design_w = max(float(P_bus_dc_traction_w), float(P_bus_dc_charge_w))
                else:
                    P_bus_dc_design_w = P_bus_dc_traction_w if P_bus_dc_traction_w is not None else P_bus_dc_charge_w

            if P_bus_dc_design_w is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "P_bus_dc_design_w",
                    "Donner puissance_elec_alt_cible_w ou fournir traction/charge exploitables.",
                )

        # Tension bus DC : entrée > moteur > batterie charge > batterie nominale
        Vbus_dc: Optional[float] = None
        if tension_bus_dc_v is not None:
            Vbus_dc = _require_positive("tension_bus_dc_v", tension_bus_dc_v, strict=True)
        else:
            Vbus_dc = _first_finite(
                getattr(self.moteur_electrique, "tension_bus_v", None),
                getattr(self.batterie, "tension_charge_v", None),
                getattr(self.batterie, "tension_nominale_v", None),
            )

        if Vbus_dc is None:
            _push_inconnue(
                rapport,
                "partielles",
                "tension bus DC",
                "Donner tension_bus_dc_v ou fournir tension bus moteur/batterie.",
            )

        # Energie à recharger
        energie_a_recharger_kwh: Optional[float] = None
        dim_batt = _safe_dict(batterie_rapport.get("dimensionnement"))
        if _is_finite(dim_batt.get("E_utile_finale_kwh")):
            energie_a_recharger_kwh = float(dim_batt["E_utile_finale_kwh"])
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
        # 5) Alternateur + boîte à crabots
        # ------------------------------------------------------------
        alternateur_rapport: Optional[Dict[str, Any]] = None
        boite_rapport: Optional[Dict[str, Any]] = None
        chaine_rapport: Optional[Dict[str, Any]] = None

        rpm_alt: Optional[float] = None
        ratio_alt_sur_moteur: Optional[float] = rapport_vitesse_alt_sur_moteur
        couple_moteur_thermique_nm: Optional[float] = None
        P_moteur_thermique_w: Optional[float] = None

        # --- Chaîne complète via boîte (prioritaire)
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
                rendement_boite=rendement_boite,
                inertie_primaire_kg_m2=inertie_primaire_kg_m2,
                inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
                delta_omega_rad_s=delta_omega_rad_s,
                temps_engagement_s=temps_engagement_s,
                force_axiale_N=force_axiale_roulement_N,
                force_radiale_N=force_radiale_roulement_N,
            )
            rapport["sous_systemes"]["chaine_moteur_alternateur"] = chaine_rapport
            _merge_inconnues(rapport, chaine_rapport, prefix="chaine_moteur_alternateur")

            best = _safe_dict(chaine_rapport.get("meilleur"))
            if best:
                alternateur_rapport = _safe_dict(best.get("alternateur"))
                boite_rapport = _safe_dict(best.get("boite_crabots"))
                resume = _safe_dict(best.get("resume"))

                rpm_alt = _safe_float(resume.get("rpm_alternateur"))
                ratio_alt_sur_moteur = _safe_float(resume.get("rapport"))
                couple_moteur_thermique_nm = _safe_float(resume.get("couple_moteur_requis_Nm"))
                P_moteur_thermique_w = _safe_float(resume.get("P_moteur_requis_W"))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "chaine_moteur_alternateur",
                    "Chaîne calculée mais aucun 'meilleur' exploitable.",
                )
        else:
            rapport["sous_systemes"]["chaine_moteur_alternateur"] = None

        # --- Sinon alternateur simple
        if alternateur_rapport is None:
            if vitesse_alternateur_rpm is not None:
                rpm_alt = _require_positive("vitesse_alternateur_rpm", vitesse_alternateur_rpm, strict=True)
            else:
                if vitesse_moteur_thermique_rpm is not None and rapport_vitesse_alt_sur_moteur is not None:
                    rpm_mth = _require_positive("vitesse_moteur_thermique_rpm", vitesse_moteur_thermique_rpm, strict=True)
                    ratio_alt_sur_moteur = _require_positive("rapport_vitesse_alt_sur_moteur", rapport_vitesse_alt_sur_moteur, strict=True)
                    rpm_alt = rpm_mth * ratio_alt_sur_moteur
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "vitesse alternateur",
                        "Donner vitesse_alternateur_rpm OU (rpm moteur + ratio).",
                    )

            if rpm_alt is not None:
                if mode_electrique_alternateur == "dc":
                    if Vbus_dc is None or P_bus_dc_design_w is None:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "alternateur bus DC",
                            "Nécessite Vbus_dc et P_bus_dc_design_w.",
                        )
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
                # Le rapport peut venir de analyser_pour_bus_dc (imbriqué) ou analyser_point_de_fonctionnement (direct)
                alt_base = alternateur_rapport.get("alternateur") if isinstance(alternateur_rapport.get("alternateur"), dict) else alternateur_rapport
                res = _safe_dict(alt_base.get("resultats"))
                couple_alt_nm = _safe_float(res.get("couple_mecanique_Nm"))
                P_alt_mec_w = _safe_float(res.get("P_mecanique_W"))

            eta_liaison = _require_positive("rendement_liaison_meca_alt", rendement_liaison_meca_alt, strict=True)

            if _is_finite(P_alt_mec_w):
                P_moteur_thermique_w = float(P_alt_mec_w) / float(eta_liaison)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "P_moteur_thermique_w",
                    "Calculable si alternateur fournit P_mecanique_W.",
                )

            if _is_finite(couple_alt_nm) and ratio_alt_sur_moteur is not None:
                ratio = _require_positive("rapport_vitesse_alt_sur_moteur", ratio_alt_sur_moteur, strict=True)
                couple_moteur_thermique_nm = (float(couple_alt_nm) * ratio) / float(eta_liaison)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "couple moteur thermique",
                    "Calculable si couple alternateur + ratio connus.",
                )

        rapport["liaisons"]["moteur_thermique_exigences"] = {
            "rpm_moteur_thermique": vitesse_moteur_thermique_rpm,
            "P_moteur_thermique_W": P_moteur_thermique_w,
            "couple_moteur_thermique_Nm": couple_moteur_thermique_nm,
            "rpm_alternateur": rpm_alt,
            "ratio_alt_sur_moteur": ratio_alt_sur_moteur,
        }

        # ------------------------------------------------------------
        # 7) Boîte : si pas de chaîne et boîte fournie
        # ------------------------------------------------------------
        if boite_rapport is None and self.boite_crabots is not None:
            couple_alt_nm = None
            if isinstance(alternateur_rapport, dict):
                res = _safe_dict(alternateur_rapport.get("resultats"))
                couple_alt_nm = _safe_float(res.get("couple_mecanique_Nm"))

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
                _push_inconnue(
                    rapport,
                    "partielles",
                    "boite_crabots",
                    "Analyse possible si couple alternateur calculable.",
                )

        rapport["sous_systemes"]["boite_crabots"] = boite_rapport
        _merge_inconnues(rapport, boite_rapport, prefix="boite_crabots")

        # ------------------------------------------------------------
        # 8) Architecture / définition moteur thermique
        # ------------------------------------------------------------
        arch_rapport: Optional[Dict[str, Any]] = None
        moteur_thermique_definition: Optional[Dict[str, Any]] = None
        moteur_thermique_effectif = self.moteur_thermique

        # 8A) Si composant Architecture fourni : arbitrage N / archi / bore / course
        if self.architecture is not None:
            if P_moteur_thermique_w is None or not _is_finite(P_moteur_thermique_w):
                _push_inconnue(
                    rapport,
                    "partielles",
                    "architecture",
                    "Nécessite P_moteur_thermique_w.",
                )
            elif vitesse_moteur_thermique_rpm is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "architecture::rpm",
                    "Nécessite vitesse_moteur_thermique_rpm.",
                )
            elif pme_pa is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "architecture::pme",
                    "Nécessite pme_pa (entrée modèle).",
                )
            else:
                arch_rapport = self.architecture.analyser(
                    puissance_cible_w=float(P_moteur_thermique_w),
                    regime_tr_min=float(_require_positive("vitesse_moteur_thermique_rpm", vitesse_moteur_thermique_rpm, strict=True)),
                    pme_pa=float(pme_pa),
                    vitesse_piston_max_ms=vitesse_piston_max_ms,
                    longueur_dispo_m=longueur_dispo_m,
                    largeur_dispo_m=largeur_dispo_m,
                    horizon_usage_h=float(horizon_usage_h),
                    architectures_autorisees=architectures_autorisees,
                    architecture_forcee=architecture_forcee,
                    poids_maintenance=poids_maintenance,
                    poids_masse=poids_masse,
                    poids_cout_matiere=poids_cout_matiere,
                    poids_compacite=poids_compacite,
                    poids_fiabilite=poids_fiabilite,
                    poids_rendement=poids_rendement,
                )
                best = _safe_dict(arch_rapport.get("meilleur"))
                if best:
                    try:
                        bore_m = _require_positive("bore_mm", best.get("bore_mm"), strict=True) / 1000.0
                        course_m = _require_positive("course_mm", best.get("course_mm"), strict=True) / 1000.0
                        N_cyl = _require_int_positive("N_cyl", int(best.get("N_cyl", 1)), strict=True)
                        moteur_thermique_effectif = replace(
                            moteur_thermique_effectif,
                            alesage_m=bore_m,
                            course_m=course_m,
                            nombre_cylindres=N_cyl,
                            architecture=str(best.get("architecture")) if best.get("architecture") is not None else getattr(moteur_thermique_effectif, "architecture", None),
                            rpm_nominal=float(vitesse_moteur_thermique_rpm),
                            pme_nominale_pa=float(pme_pa),
                            puissance_nominale_visee_w=float(P_moteur_thermique_w),
                            type_puissance_nominale="frein",
                        )
                    except Exception:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "moteur_thermique(géométrie depuis architecture)",
                            "Architecture 'meilleur' inexploitable (format/valeurs).",
                        )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "architecture",
                "Composant Architecture non fourni.",
            )

        rapport["sous_systemes"]["architecture"] = arch_rapport
        _merge_inconnues(rapport, arch_rapport, prefix="architecture")

        # 8B) Définition directe du moteur thermique si assez d'entrées
        # Utilise la méthode enrichie du composant moteur thermique.
        if (
            P_moteur_thermique_w is not None
            and _is_finite(P_moteur_thermique_w)
            and vitesse_moteur_thermique_rpm is not None
            and _is_finite(vitesse_moteur_thermique_rpm)
            and pme_pa is not None
            and _is_finite(pme_pa)
            and vitesse_piston_max_ms is not None
            and _is_finite(vitesse_piston_max_ms)
        ):
            try:
                moteur_thermique_definition = MoteurThermique.definir_depuis_exigences(
                    puissance_visee_w=float(P_moteur_thermique_w),
                    type_puissance="frein",
                    rpm=float(vitesse_moteur_thermique_rpm),
                    pression_moyenne_effective_pa=float(pme_pa),
                    temps_moteur=int(moteur_thermique_effectif.temps_moteur),
                    rendement_mecanique=getattr(moteur_thermique_effectif, "rendement_mecanique_nominal", None) or getattr(moteur_thermique_effectif, "rendement_mecanique_cible_min", None) or 0.85,
                    vitesse_piston_max_ms=float(vitesse_piston_max_ms),
                    ratio_course_alesage_max=getattr(self.architecture, "ratio_course_alesage_max", None) if self.architecture is not None else 1.2,
                    ratio_course_alesage_cible=None,
                    L_max_m=longueur_dispo_m,
                    W_max_m=largeur_dispo_m,
                    architectures_autorisees=tuple(architectures_autorisees) if architectures_autorisees is not None else None,
                    architecture_forcee=architecture_forcee,
                    pression_max_pa=pression_max_pa,
                    contrainte_admissible_pa=contrainte_admissible_pa,
                    facteur_securite_cylindre=getattr(moteur_thermique_effectif, "facteur_securite_cylindre", 1.5),
                    densite_materiau_kg_m3=densite_materiau_kg_m3,
                    cout_matiere_eur_kg=cout_matiere_eur_kg,
                    rendement_indique_cible_min=rendement_indique_cible_min,
                    rendement_mecanique_cible_min=rendement_mecanique_cible_min,
                    masse_estimee_max_kg=masse_estimee_max_kg,
                    cout_matiere_max_eur=cout_matiere_max_eur,
                    indice_maintenance_max=indice_maintenance_max,
                    duree_vie_cible_h=duree_vie_cible_h,
                )
                rapport["sous_systemes"]["moteur_thermique_definition"] = moteur_thermique_definition
                _merge_inconnues(rapport, moteur_thermique_definition, prefix="moteur_thermique_definition")

                mt_def = moteur_thermique_definition.get("moteur_defini")
                if mt_def is not None:
                    # garde les champs calculés sans perdre les champs déjà portés par l'instance système
                    moteur_thermique_effectif = replace(
                        moteur_thermique_effectif,
                        alesage_m=getattr(mt_def, "alesage_m", moteur_thermique_effectif.alesage_m),
                        course_m=getattr(mt_def, "course_m", moteur_thermique_effectif.course_m),
                        nombre_cylindres=getattr(mt_def, "nombre_cylindres", moteur_thermique_effectif.nombre_cylindres),
                        architecture=getattr(mt_def, "architecture", getattr(moteur_thermique_effectif, "architecture", None)),
                        rpm_nominal=getattr(mt_def, "rpm_nominal", getattr(moteur_thermique_effectif, "rpm_nominal", None)),
                        pme_nominale_pa=getattr(mt_def, "pme_nominale_pa", getattr(moteur_thermique_effectif, "pme_nominale_pa", None)),
                        puissance_nominale_visee_w=getattr(mt_def, "puissance_nominale_visee_w", getattr(moteur_thermique_effectif, "puissance_nominale_visee_w", None)),
                        type_puissance_nominale=getattr(mt_def, "type_puissance_nominale", getattr(moteur_thermique_effectif, "type_puissance_nominale", None)),
                        rendement_mecanique_nominal=getattr(mt_def, "rendement_mecanique_nominal", getattr(moteur_thermique_effectif, "rendement_mecanique_nominal", None)),
                        pression_max_pa=getattr(mt_def, "pression_max_pa", getattr(moteur_thermique_effectif, "pression_max_pa", None)),
                        contrainte_admissible_pa=getattr(mt_def, "contrainte_admissible_pa", getattr(moteur_thermique_effectif, "contrainte_admissible_pa", None)),
                        densite_materiau_kg_m3=getattr(mt_def, "densite_materiau_kg_m3", getattr(moteur_thermique_effectif, "densite_materiau_kg_m3", None)),
                        cout_matiere_eur_kg=getattr(mt_def, "cout_matiere_eur_kg", getattr(moteur_thermique_effectif, "cout_matiere_eur_kg", None)),
                        rendement_indique_cible_min=getattr(mt_def, "rendement_indique_cible_min", getattr(moteur_thermique_effectif, "rendement_indique_cible_min", None)),
                        rendement_mecanique_cible_min=getattr(mt_def, "rendement_mecanique_cible_min", getattr(moteur_thermique_effectif, "rendement_mecanique_cible_min", None)),
                        masse_estimee_max_kg=getattr(mt_def, "masse_estimee_max_kg", getattr(moteur_thermique_effectif, "masse_estimee_max_kg", None)),
                        cout_matiere_max_eur=getattr(mt_def, "cout_matiere_max_eur", getattr(moteur_thermique_effectif, "cout_matiere_max_eur", None)),
                        indice_maintenance_max=getattr(mt_def, "indice_maintenance_max", getattr(moteur_thermique_effectif, "indice_maintenance_max", None)),
                        duree_vie_cible_h=getattr(mt_def, "duree_vie_cible_h", getattr(moteur_thermique_effectif, "duree_vie_cible_h", None)),
                    )
            except Exception as e:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "moteur_thermique_definition",
                    f"Echec de definir_depuis_exigences(): {e}",
                )
        else:
            rapport["sous_systemes"]["moteur_thermique_definition"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "moteur_thermique_definition",
                "Nécessite au minimum P_moteur_thermique_w, vitesse_moteur_thermique_rpm, pme_pa et vitesse_piston_max_ms.",
            )

        # ------------------------------------------------------------
        # 9) PME requise (si non fournie)
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
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "PME requise",
                            "Vd_tot ou f_cycles nul.",
                        )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "PME requise",
                        "Nécessite alesage_m/course_m.",
                    )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "PME requise",
                    "Nécessite P_moteur_thermique_w et rpm moteur thermique.",
                )

        rapport["liaisons"]["pme"] = {
            "pme_pa_utilisee_ou_requise": pme_utilisee_ou_requise_pa,
        }

        # ------------------------------------------------------------
        # 10) Moteur thermique : analyse point
        # ------------------------------------------------------------
        moteur_th_rapport: Optional[Dict[str, Any]] = None
        if rpm_th is not None:
            params = dict(moteur_thermique_params or {})
            params.pop("rpm", None)
            params.pop("pression_moyenne_effective_pa", None)
            params.pop("pression_max_pa", None)
            import inspect
            sig = inspect.signature(moteur_thermique_effectif.analyser_point_de_fonctionnement)
            valid_keys = set(sig.parameters.keys())
            filtered_params = {k: v for k, v in params.items() if k in valid_keys}
            
            moteur_th_rapport = moteur_thermique_effectif.analyser_point_de_fonctionnement(
                rpm=float(_require_positive("vitesse_moteur_thermique_rpm", rpm_th, strict=True)),
                pression_moyenne_effective_pa=pme_utilisee_ou_requise_pa,
                pression_max_pa=pression_max_pa,
                **filtered_params,
            )
            rapport["sous_systemes"]["moteur_thermique"] = moteur_th_rapport
            _merge_inconnues(rapport, moteur_th_rapport, prefix="moteur_thermique")
        else:
            rapport["sous_systemes"]["moteur_thermique"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "moteur thermique",
                "Nécessite vitesse_moteur_thermique_rpm.",
            )

        # ------------------------------------------------------------
        # 11) Synthèse système
        # ------------------------------------------------------------
        mt_dim = _safe_dict((_safe_dict(moteur_th_rapport)).get("dimensionnement"))
        mt_conception = _safe_dict((_safe_dict(moteur_th_rapport)).get("conception"))
        mt_resultats = _safe_dict((_safe_dict(moteur_th_rapport)).get("resultats"))
        mt_pertes = _safe_dict((_safe_dict(moteur_th_rapport)).get("pertes"))

        arch_best = _safe_dict((_safe_dict(arch_rapport)).get("meilleur"))
        mt_def_dim = _safe_dict((_safe_dict(moteur_thermique_definition)).get("dimensionnement"))
        mt_def_eval = _safe_dict((_safe_dict(moteur_thermique_definition)).get("evaluation_conception"))
        mt_def_estim = _safe_dict((_safe_dict(moteur_thermique_definition)).get("estimations"))

        batterie_dim = _safe_dict((_safe_dict(batterie_rapport)).get("dimensionnement"))
        batterie_charge = _safe_dict((_safe_dict(batterie_rapport)).get("charge"))
        alt_resultats = _safe_dict((_safe_dict(alternateur_rapport)).get("resultats"))

        mt_bore_m = _first_finite(
            getattr(moteur_thermique_effectif, "alesage_m", None),
            _safe_float(mt_def_dim.get("alesage_defini_m")),
            (_safe_float(arch_best.get("bore_mm")) / 1000.0) if _is_finite(arch_best.get("bore_mm")) else None,
        )
        mt_course_m = _first_finite(
            getattr(moteur_thermique_effectif, "course_m", None),
            _safe_float(mt_def_dim.get("course_definie_m")),
            (_safe_float(arch_best.get("course_mm")) / 1000.0) if _is_finite(arch_best.get("course_mm")) else None,
        )
        mt_n_cyl = _first_non_none(
            getattr(moteur_thermique_effectif, "nombre_cylindres", None),
            _safe_int(arch_best.get("N_cyl")),
            _safe_int(mt_def_dim.get("nombre_cylindres_min")),
        )
        mt_arch = _first_non_none(
            getattr(moteur_thermique_effectif, "architecture", None),
            arch_best.get("architecture"),
            _safe_dict((_safe_dict(arch_rapport)).get("architecture")).get("architecture_choisie") if isinstance(_safe_dict(arch_rapport).get("architecture"), dict) else None,
        )

        Vd_tot_m3 = None
        if mt_bore_m is not None and mt_course_m is not None and mt_n_cyl is not None:
            Vd_tot_m3 = _cylindree_totale_m3(mt_bore_m, mt_course_m, int(mt_n_cyl))

        respecte_masse = _bool_max_all(
            [
                _safe_bool(mt_conception.get("respecte_masse_estimee_max")),
                _safe_bool(mt_def_eval.get("respecte_masse_max")),
            ]
        )
        respecte_cout = _bool_max_all(
            [
                _safe_bool(mt_conception.get("respecte_cout_matiere_max")),
                _safe_bool(mt_def_eval.get("respecte_cout_matiere_max")),
            ]
        )
        respecte_maintenance = _bool_max_all(
            [
                _safe_bool(mt_conception.get("respecte_indice_maintenance_max")),
                _safe_bool(mt_def_eval.get("respecte_indice_maintenance_max")),
            ]
        )
        respecte_rendement_meca = _bool_max_all(
            [
                _safe_bool(mt_conception.get("respecte_rendement_mecanique_min")),
                _safe_bool(mt_def_eval.get("respecte_rendement_mecanique_min")),
            ]
        )

        rapport["criteres_conception"] = {
            "maintenance": {
                "poids": poids_maintenance,
                "indice_maintenance_max": indice_maintenance_max,
                "respecte": respecte_maintenance,
            },
            "masse": {
                "poids": poids_masse,
                "masse_estimee_max_kg": masse_estimee_max_kg,
                "respecte": respecte_masse,
            },
            "cout": {
                "poids": poids_cout_matiere,
                "cout_matiere_max_eur": cout_matiere_max_eur,
                "respecte": respecte_cout,
            },
            "compacite": {
                "poids": poids_compacite,
                "longueur_dispo_m": longueur_dispo_m,
                "largeur_dispo_m": largeur_dispo_m,
            },
            "fiabilite": {
                "poids": poids_fiabilite,
                "pression_max_pa": pression_max_pa,
                "contrainte_admissible_pa": contrainte_admissible_pa,
                "duree_vie_cible_h": duree_vie_cible_h,
            },
            "rendement": {
                "poids": poids_rendement,
                "rendement_indique_cible_min": rendement_indique_cible_min,
                "rendement_mecanique_cible_min": rendement_mecanique_cible_min,
                "respecte_rendement_mecanique_min": respecte_rendement_meca,
            },
        }

        rapport["synthese"] = {
            "vehicule": {
                "puissance_traction_bus_dc_w": P_bus_dc_traction_w,
                "puissance_bus_dc_design_w": P_bus_dc_design_w,
                "tension_bus_dc_v": Vbus_dc,
            },
            "batterie": {
                "energie_utile_kwh": _first_finite(
                    batterie_dim.get("E_utile_finale_kwh"),
                    energie_a_recharger_kwh,
                ),
                "puissance_charge_requise_kw": _safe_float(batterie_charge.get("puissance_charge_requise_kw")),
                "puissance_pic_kw": _first_finite(
                    batterie_dim.get("P_pic_finale_kw"),
                    puissance_pic_kw_eff,
                ),
            },
            "alternateur": {
                "rpm_alternateur": rpm_alt,
                "P_mecanique_W": _safe_float(alt_resultats.get("P_mecanique_W")),
                "couple_mecanique_Nm": _safe_float(alt_resultats.get("couple_mecanique_Nm")),
            },
            "moteur_thermique": {
                "rpm_nominal": _first_finite(
                    getattr(moteur_thermique_effectif, "rpm_nominal", None),
                    vitesse_moteur_thermique_rpm,
                ),
                "puissance_requise_W": P_moteur_thermique_w,
                "couple_requis_Nm": couple_moteur_thermique_nm,
                "pme_pa": pme_utilisee_ou_requise_pa,
                "pression_max_pa": pression_max_pa,
                "architecture": mt_arch,
                "nombre_cylindres": mt_n_cyl,
                "alesage_m": mt_bore_m,
                "course_m": mt_course_m,
                "cylindree_totale_m3": Vd_tot_m3,
                "cylindree_totale_cc": Vd_tot_m3 * 1e6 if Vd_tot_m3 is not None else None,
                "epaisseur_cylindre_retenue_m": _first_finite(
                    mt_dim.get("epaisseur_cylindre_retenue_m"),
                    mt_def_dim.get("epaisseur_cylindre_retenue_m"),
                ),
                "puissance_indiquee_W": _safe_float(mt_resultats.get("puissance_indiquee_W")),
                "puissance_frein_estimee_W": _safe_float(mt_resultats.get("puissance_frein_estimee_W")),
                "rendement_mecanique_estime": _safe_float(mt_pertes.get("rendement_mecanique_estime")),
                "masse_estimee_kg": _first_finite(
                    _safe_dict(mt_conception.get("masse")).get("masse_estimee_kg"),
                    _safe_dict(mt_def_estim.get("masse")).get("masse_estimee_kg"),
                ),
                "cout_matiere_estime_eur": _first_finite(
                    mt_conception.get("cout_matiere_estime_eur"),
                    mt_def_estim.get("cout_matiere_estime_eur"),
                ),
                "indice_maintenance": _first_finite(
                    mt_conception.get("indice_maintenance"),
                    mt_def_estim.get("indice_maintenance"),
                ),
                "respecte_masse_max": respecte_masse,
                "respecte_cout_max": respecte_cout,
                "respecte_indice_maintenance_max": respecte_maintenance,
                "respecte_rendement_mecanique_min": respecte_rendement_meca,
            },
        }

        # ------------------------------------------------------------
        # 12) CAO : paquet de cotes de haut niveau
        # ------------------------------------------------------------
        rapport["cao"] = {
            "solidworks_ready": (
                mt_bore_m is not None
                and mt_course_m is not None
                and mt_n_cyl is not None
            ),
            "moteur_thermique": {
                "architecture": mt_arch,
                "nombre_cylindres": mt_n_cyl,
                "alesage_mm": mt_bore_m * 1000.0 if mt_bore_m is not None else None,
                "course_mm": mt_course_m * 1000.0 if mt_course_m is not None else None,
                "epaisseur_cylindre_mm": (
                    _first_finite(
                        mt_dim.get("epaisseur_cylindre_retenue_m"),
                        mt_def_dim.get("epaisseur_cylindre_retenue_m"),
                    ) * 1000.0
                    if _first_finite(
                        mt_dim.get("epaisseur_cylindre_retenue_m"),
                        mt_def_dim.get("epaisseur_cylindre_retenue_m"),
                    ) is not None
                    else None
                ),
                "cylindree_totale_cc": Vd_tot_m3 * 1e6 if Vd_tot_m3 is not None else None,
                "rpm_nominal": _first_finite(
                    getattr(moteur_thermique_effectif, "rpm_nominal", None),
                    vitesse_moteur_thermique_rpm,
                ),
                "pme_pa": pme_utilisee_ou_requise_pa,
            },
            "systeme": {
                "P_bus_dc_design_w": P_bus_dc_design_w,
                "V_bus_dc_v": Vbus_dc,
                "P_moteur_thermique_requise_w": P_moteur_thermique_w,
                "couple_moteur_thermique_requis_nm": couple_moteur_thermique_nm,
            },
        }

        # ------------------------------------------------------------
        # 13) Inconnues système de haut niveau
        # ------------------------------------------------------------
        if rapport["cao"]["solidworks_ready"] is False:
            _push_inconnue(
                rapport,
                "partielles",
                "cao moteur thermique",
                "La géométrie moteur n'est pas encore complètement fermée pour une saisie SolidWorks directe.",
            )

        if self.architecture is None and moteur_thermique_definition is None:
            _push_inconnue(
                rapport,
                "partielles",
                "synthèse architecture moteur",
                "Le système n'a ni arbitrage Architecture exploitable ni définition directe complète du moteur thermique.",
            )

        _add_note(
            rapport,
            "Le système complet consolide ce qui est calculable mais ne remplace pas encore le dimensionnement détaillé de toutes les pièces mécaniques aval."
        )
        _add_note(
            rapport,
            "Le bloc 'cao' fourni ici est un paquet de cotes de haut niveau pour fermer l'architecture moteur ; les autres pièces devront ensuite consommer ces données."
        )

        _dedup_inconnues(rapport)
        return rapport


if __name__ == "__main__":
    # Exemple minimal d'appel
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
        architecture=Architecture(),
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
        pme_pa=8.0e5,
        vitesse_piston_max_ms=10.0,
        longueur_dispo_m=1.2,
        largeur_dispo_m=0.8,
        pression_max_pa=3.0e6,
        contrainte_admissible_pa=1.2e8,
        densite_materiau_kg_m3=7800.0,
        cout_matiere_eur_kg=2.0,
        rendement_mecanique_cible_min=0.80,
        masse_estimee_max_kg=150.0,
        cout_matiere_max_eur=1000.0,
        indice_maintenance_max=10.0,
    )

    print("Inconnues impossibles:", len(rep["inconnues"]["impossibles"]))
    print("Inconnues partielles:", len(rep["inconnues"]["partielles"]))
    print("Sous-systèmes:", list(rep["sous_systemes"].keys()))
    print("Synthèse moteur thermique:", rep["synthese"]["moteur_thermique"])