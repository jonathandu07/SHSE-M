# backend\ensemble\systeme_complet.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Literal, Tuple
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

except Exception:
    # Variante possible si tu exécutes depuis backend/ directement
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


# ============================================================
# Helpers généraux
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strict: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


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


def _merge_inconnues(dst: Dict[str, Any], src: Dict[str, Any], *, prefix: str) -> None:
    """
    Remonte les inconnues d'un sous-rapport en les préfixant pour les rendre traçables.
    """
    inc = src.get("inconnues", {})
    for cat in ("impossibles", "partielles"):
        for it in inc.get(cat, []) or []:
            dst["inconnues"][cat].append(
                {
                    "nom": f"{prefix} :: {it.get('nom', '')}",
                    "raison": str(it.get("raison", "")),
                }
            )


# ============================================================
# Modèle système complet
# ============================================================

ModeElectriqueAlternateur = Literal["triphase_ac", "monophase_ac", "dc"]


@dataclass(frozen=True)
class SystemeComplet:
    """
    Agrégateur "système complet" : exploite tous les composants existants
    pour calculer un maximum de grandeurs, et ne laisser comme inconnues
    que ce qui est réellement non-déductible (datasheet / matériaux / géom détaillée).
    """

    moteur_electrique: MoteurElectrique
    batterie: Batterie
    alternateur: Alternateur
    moteur_thermique: MoteurThermique

    # Optionnels (mais utilisés si fournis)
    boite_crabots: Optional[BoiteCrabots] = None
    architecture: Optional[Architecture] = None

    def analyser(
        self,
        *,
        # -------------------------
        # A) Point véhicule (demande traction)
        # -------------------------
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
        nb_moteurs_electriques: int = 1,  # 1, 2, 4 ...
        pertes_fixes_transmission_w: float = 0.0,
        couple_pertes_transmission_nm: float = 0.0,
        marge_puissance: float = 0.0,
        marge_couple: float = 0.0,
        # Auxiliaires électriques (pompes, ECU, ventilateurs, etc.)
        puissance_auxiliaire_w: float = 0.0,
        # -------------------------
        # B) Mission batterie (énergie)
        # -------------------------
        distance_km: Optional[float] = None,
        conso_kwh_km: Optional[float] = None,
        puissance_moyenne_kw: Optional[float] = None,
        vitesse_moyenne_kmh: Optional[float] = None,
        temps_charge_cible_h: Optional[float] = None,
        puissance_pic_kw: Optional[float] = None,
        duree_pic_s: Optional[float] = None,
        energie_utile_imposee_kwh: Optional[float] = None,
        calculer_puissance_charge_requise: bool = True,
        # -------------------------
        # C) Alternateur (couplage + mode)
        # -------------------------
        mode_electrique_alternateur: ModeElectriqueAlternateur = "triphase_ac",
        # vitesse alternateur : soit directe, soit via ratio depuis rpm moteur thermique
        vitesse_alternateur_rpm: Optional[float] = None,
        rapport_vitesse_alt_sur_moteur: Optional[float] = None,  # rpm_alt = rpm_moteur * ratio
        vitesse_moteur_thermique_rpm: Optional[float] = None,
        # puissance électrique demandée à l'alternateur
        puissance_elec_alt_cible_w: Optional[float] = None,
        # Si tu veux calculer P_alt via V/I :
        tension_alt_v: Optional[float] = None,
        courant_alt_a: Optional[float] = None,
        facteur_puissance_alt: float = 1.0,
        entree_puissance_ac: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
        courant_est_ligne: bool = True,
        # rendement mécanique entre moteur thermique et alternateur (courroie/engrenage)
        rendement_liaison_meca_alt: float = 1.0,
        # -------------------------
        # D) Architecture (si fournie) : pour proposer N/bore/course
        # -------------------------
        pme_pa: Optional[float] = None,  # si absent, on peut déduire une PME "requise" si Vd connue
        vitesse_piston_max_ms: Optional[float] = None,
        longueur_dispo_m: Optional[float] = None,
        largeur_dispo_m: Optional[float] = None,
        horizon_usage_h: float = 20000.0,
        # -------------------------
        # E) Boîte à crabots (si fournie) : point de calcul au couple transmis
        # -------------------------
        analyser_boite_sur_couple_alternateur: bool = True,
        moment_flechissant_nm: Optional[float] = None,
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_axiale_roulement_N: Optional[float] = None,
        force_radiale_roulement_N: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Rapport global structuré :
        - traction (demande véhicule) + check moteur(s)
        - batterie (énergie, capacité, masse, charge)
        - alternateur (fréquence, FEM si possible, pertes, rendement, couple)
        - architecture (N/bore/course optimaux si possible)
        - moteur thermique (forces, cylindrée, épaisseurs, pertes, usure si possible)
        - boîte à crabots (contraintes, choc, roulements) si disponible

        Les inconnues restantes sont listées et préfixées par sous-système.
        """
        rapport: Dict[str, Any] = {
            "entrees": {},
            "sous_systemes": {},
            "liaisons": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # 0) Entrées globales (log)
        # ------------------------------------------------------------
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
            "mission_batterie": {
                "distance_km": distance_km,
                "conso_kwh_km": conso_kwh_km,
                "puissance_moyenne_kw": puissance_moyenne_kw,
                "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
                "temps_charge_cible_h": temps_charge_cible_h,
                "puissance_pic_kw": puissance_pic_kw,
                "duree_pic_s": duree_pic_s,
                "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
                "calculer_puissance_charge_requise": calculer_puissance_charge_requise,
            },
            "alternateur": {
                "mode": mode_electrique_alternateur,
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
            "architecture": {
                "pme_pa": pme_pa,
                "vitesse_piston_max_ms": vitesse_piston_max_ms,
                "longueur_dispo_m": longueur_dispo_m,
                "largeur_dispo_m": largeur_dispo_m,
                "horizon_usage_h": horizon_usage_h,
            },
            "boite_crabots": {
                "analyser_boite_sur_couple_alternateur": analyser_boite_sur_couple_alternateur,
                "moment_flechissant_nm": moment_flechissant_nm,
                "inertie_primaire_kg_m2": inertie_primaire_kg_m2,
                "inertie_secondaire_kg_m2": inertie_secondaire_kg_m2,
                "delta_omega_rad_s": delta_omega_rad_s,
                "temps_engagement_s": temps_engagement_s,
                "force_axiale_roulement_N": force_axiale_roulement_N,
                "force_radiale_roulement_N": force_radiale_roulement_N,
            },
        }

        # ------------------------------------------------------------
        # 1) Demande traction + check moteur(s)
        # ------------------------------------------------------------
        traction: Optional[Dict[str, Any]] = None
        check_moteurs: Optional[Dict[str, Any]] = None

        # Conditions minimales pour calculer la demande traction
        if (
            masse_kg is not None
            and vitesse_ms is not None
            and acceleration_ms2 is not None
            and coef_roulement is not None
            and coef_trainee_aero_cda is not None
            and rayon_roue_m is not None
            and rapport_reduction_global is not None
            and rendement_transmission is not None
        ):
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

            # Demande totale (équivalente)
            traction = {
                "demande_totale": demande,
                "demande_par_moteur": None,
            }

            # Si plusieurs moteurs identiques (ex: 4 roues), on ventile proprement
            nbm = int(nb_moteurs_electriques)
            if nbm >= 1:
                dm = dict(demande)
                # On divise P/T demandés au moteur par nb moteurs (hypothèse: partage égal)
                dm["P_moteur_W"] = float(demande["P_moteur_W"]) / nbm
                dm["T_moteur_Nm"] = float(demande["T_moteur_Nm"]) / nbm
                traction["demande_par_moteur"] = dm

                # Check capacité au régime demandé
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
                "Calculable si on fournit : masse_kg, vitesse_ms, acceleration_ms2, coef_roulement, coef_trainee_aero_cda, rayon_roue_m, rapport_reduction_global, rendement_transmission.",
            )

        rapport["sous_systemes"]["traction"] = traction
        rapport["sous_systemes"]["check_moteurs"] = check_moteurs

        # ------------------------------------------------------------
        # 2) Puissance électrique instantanée demandée (batterie -> moteurs)
        # ------------------------------------------------------------
        P_batt_inst_w: Optional[float] = None
        I_batt_inst_a: Optional[float] = None

        if traction and traction.get("demande_par_moteur"):
            dm = traction["demande_par_moteur"]
            nbm = int(max(1, nb_moteurs_electriques))

            # Hypothèse "minimum d'inconnues" :
            # - la demande calculée P_moteur_W est une puissance mécanique requise côté moteur.
            # - la conversion en électrique passe par rendement_moteur du composant MoteurElectrique.
            Pm_par = float(dm["P_moteur_W"])
            Pin_par = (Pm_par + float(self.moteur_electrique.pertes_fixes_w)) / float(self.moteur_electrique.rendement_moteur)
            Pin_total = Pin_par * nbm

            P_batt_inst_w = max(0.0, float(Pin_total) + float(puissance_auxiliaire_w))

            # Courant si tension bus connue
            if self.moteur_electrique.tension_bus_v is not None:
                Vbus = _require_positive("moteur_electrique.tension_bus_v", self.moteur_electrique.tension_bus_v, strict=True)
                I_batt_inst_a = P_batt_inst_w / Vbus if Vbus > 1e-9 else None
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "courant batterie instantané",
                    "Calculable si moteur_electrique.tension_bus_v est fournie.",
                )

        else:
            _push_inconnue(
                rapport,
                "partielles",
                "puissance batterie instantanée",
                "Calculable si la demande traction est calculée (point véhicule complet).",
            )

        rapport["liaisons"]["electrique_instantane"] = {
            "P_batterie_inst_w": P_batt_inst_w,
            "I_batterie_inst_a": I_batt_inst_a,
            "hypothese": "Pin ≈ (P_mech_demande + pertes_fixes_moteur) / eta_moteur ; total = nb_moteurs ; + auxiliaires.",
        }

        # ------------------------------------------------------------
        # 3) Batterie (dimensionnement énergie + charge)
        # ------------------------------------------------------------
        batterie_rapport = self.batterie.analyser_dimensionnement(
            distance_km=distance_km,
            conso_kwh_km=conso_kwh_km,
            puissance_moyenne_kw=puissance_moyenne_kw,
            vitesse_moyenne_kmh=vitesse_moyenne_kmh,
            temps_charge_cible_h=temps_charge_cible_h,
            puissance_pic_kw=puissance_pic_kw,
            duree_pic_s=duree_pic_s,
            energie_utile_imposee_kwh=energie_utile_imposee_kwh,
            calculer_puissance_charge_requise=calculer_puissance_charge_requise,
        )
        rapport["sous_systemes"]["batterie"] = batterie_rapport
        _merge_inconnues(rapport, batterie_rapport, prefix="batterie")

        # ------------------------------------------------------------
        # 4) Puissance alternateur cible (si non fournie)
        # ------------------------------------------------------------
        # Priorité :
        # - si puissance_elec_alt_cible_w est fournie -> on la garde
        # - sinon on essaie de la déduire de :
        #   (A) puissance batterie instantanée (traction) + auxiliaires
        #   (B) OU puissance de charge requise issue de la batterie si dispo
        P_alt_target: Optional[float] = None

        if puissance_elec_alt_cible_w is not None:
            P_alt_target = _require_positive("puissance_elec_alt_cible_w", puissance_elec_alt_cible_w, strict=False)
        else:
            # (B) si batterie a calculé P_charge_requise
            P_charge_req_kw = batterie_rapport.get("charge", {}).get("puissance_charge_requise_kw")
            if _is_finite(P_charge_req_kw):
                P_alt_target = float(P_charge_req_kw) * 1000.0
                rapport["notes_modele"].append("P_alt_target déduite de la puissance de charge requise (batterie).")
            elif P_batt_inst_w is not None:
                P_alt_target = float(P_batt_inst_w)
                rapport["notes_modele"].append("P_alt_target déduite de la puissance instantanée demandée (traction+biais).")
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "puissance alternateur cible",
                    "Donner puissance_elec_alt_cible_w, OU fournir un point traction complet, OU fournir un temps de charge cible pour calculer P_charge_requise.",
                )

        rapport["liaisons"]["alternateur_cible"] = {"P_alt_cible_w": P_alt_target}

        # ------------------------------------------------------------
        # 5) Vitesse alternateur (si non fournie)
        # ------------------------------------------------------------
        rpm_alt: Optional[float] = None
        if vitesse_alternateur_rpm is not None:
            rpm_alt = _require_finite("vitesse_alternateur_rpm", vitesse_alternateur_rpm)
        else:
            if vitesse_moteur_thermique_rpm is not None and rapport_vitesse_alt_sur_moteur is not None:
                rpm_mth = _require_finite("vitesse_moteur_thermique_rpm", vitesse_moteur_thermique_rpm)
                ratio = _require_positive("rapport_vitesse_alt_sur_moteur", rapport_vitesse_alt_sur_moteur, strict=True)
                rpm_alt = rpm_mth * ratio
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "vitesse alternateur",
                    "Donner vitesse_alternateur_rpm, OU donner vitesse_moteur_thermique_rpm + rapport_vitesse_alt_sur_moteur.",
                )

        # ------------------------------------------------------------
        # 6) Alternateur : calcul détaillé
        # ------------------------------------------------------------
        alternateur_rapport: Optional[Dict[str, Any]] = None
        if rpm_alt is not None:
            alternateur_rapport = self.alternateur.analyser_point_de_fonctionnement(
                mode_electrique=mode_electrique_alternateur,
                vitesse_rotation_rpm=rpm_alt,
                vitesse_angulaire_rad_s=None,
                tension_v=tension_alt_v,
                courant_a=courant_alt_a,
                facteur_puissance=facteur_puissance_alt,
                entree_puissance_ac=entree_puissance_ac,
                courant_est_ligne=courant_est_ligne,
                puissance_electrique_cible_w=P_alt_target,
            )
            rapport["sous_systemes"]["alternateur"] = alternateur_rapport
            _merge_inconnues(rapport, alternateur_rapport, prefix="alternateur")
        else:
            rapport["sous_systemes"]["alternateur"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "analyse alternateur",
                "Impossible sans rpm_alt (vitesse alternateur).",
            )

        # ------------------------------------------------------------
        # 7) Couple alternateur -> couple moteur thermique (via rendement liaison)
        # ------------------------------------------------------------
        couple_alt_nm: Optional[float] = None
        P_alt_mec_w: Optional[float] = None
        couple_moteur_thermique_nm: Optional[float] = None
        P_moteur_thermique_w: Optional[float] = None

        if alternateur_rapport:
            couple_alt_nm = alternateur_rapport.get("resultats", {}).get("couple_mecanique_Nm")
            P_alt_mec_w = alternateur_rapport.get("resultats", {}).get("P_mecanique_W")

            # Liaison mécanique entre moteur thermique et alternateur (courroie/engrenage)
            eta_liaison = _require_positive("rendement_liaison_meca_alt", rendement_liaison_meca_alt, strict=True)

            if _is_finite(P_alt_mec_w):
                P_moteur_thermique_w = float(P_alt_mec_w) / eta_liaison if eta_liaison > 1e-12 else None
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "P_moteur_thermique_w",
                    "Calculable si alternateur fournit P_mecanique_W (donc si eta alternateur est déterminable).",
                )

            if _is_finite(couple_alt_nm) and rapport_vitesse_alt_sur_moteur is not None:
                ratio = _require_positive("rapport_vitesse_alt_sur_moteur", rapport_vitesse_alt_sur_moteur, strict=True)
                # Couple au moteur thermique = couple alternateur / ratio (idéal) / eta_liaison
                couple_moteur_thermique_nm = (float(couple_alt_nm) / ratio) / eta_liaison
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "couple moteur thermique",
                    "Calculable si alternateur fournit son couple ET si rapport_vitesse_alt_sur_moteur est fourni.",
                )

        rapport["liaisons"]["meca_moteur_thermique_alt"] = {
            "rpm_alternateur": rpm_alt,
            "couple_alternateur_Nm": couple_alt_nm,
            "P_alternateur_meca_W": P_alt_mec_w,
            "rendement_liaison_meca_alt": rendement_liaison_meca_alt,
            "P_moteur_thermique_W": P_moteur_thermique_w,
            "couple_moteur_thermique_Nm": couple_moteur_thermique_nm,
        }

        # ------------------------------------------------------------
        # 8) Architecture (si fournie) : proposition N/bore/course
        # ------------------------------------------------------------
        arch_rapport: Optional[Dict[str, Any]] = None
        moteur_thermique_effectif = self.moteur_thermique

        if self.architecture is not None:
            # puissance cible architecture : si P_moteur_thermique_w absent, on tombe sur P_alt_mec_w
            P_arch = P_moteur_thermique_w if _is_finite(P_moteur_thermique_w) else P_alt_mec_w
            if P_arch is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "architecture",
                    "Calculable si la puissance mécanique cible à produire est connue (P_moteur_thermique_w ou P_alt_mec_w).",
                )
            elif vitesse_moteur_thermique_rpm is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "architecture :: vitesse_moteur_thermique_rpm",
                    "Nécessaire pour l'analyse d'architecture (fréquence cycles, vitesse piston, etc.).",
                )
            elif pme_pa is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "architecture :: pme_pa",
                    "PME est une entrée modèle. Donne pme_pa, OU laisse l'architecture incomplète.",
                )
            else:
                arch_rapport = self.architecture.analyser(
                    puissance_cible_w=float(P_arch),
                    regime_tr_min=float(vitesse_moteur_thermique_rpm),
                    pme_pa=float(pme_pa),
                    vitesse_piston_max_ms=vitesse_piston_max_ms,
                    longueur_dispo_m=longueur_dispo_m,
                    largeur_dispo_m=largeur_dispo_m,
                    horizon_usage_h=float(horizon_usage_h),
                )
                rapport["sous_systemes"]["architecture"] = arch_rapport
                _merge_inconnues(rapport, arch_rapport, prefix="architecture")

                # Si architecture propose un "meilleur" avec bore/course/N, on met à jour le moteur thermique
                best = (arch_rapport or {}).get("meilleur")
                if isinstance(best, dict):
                    try:
                        bore_m = _require_positive("bore_mm", best.get("bore_mm"), strict=True) / 1000.0
                        course_m = _require_positive("course_mm", best.get("course_mm"), strict=True) / 1000.0
                        N_cyl = int(best.get("N_cyl", 1))
                        if N_cyl < 1:
                            raise ValueError("N_cyl < 1")

                        moteur_thermique_effectif = replace(
                            moteur_thermique_effectif,
                            alesage_m=bore_m,
                            course_m=course_m,
                            nombre_cylindres=N_cyl,
                        )
                        rapport["notes_modele"].append("MoteurThermique mis à jour depuis le meilleur choix d'architecture (bore/course/N).")
                    except Exception:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "moteur thermique (géométrie)",
                            "Architecture 'meilleur' existe mais ses valeurs bore/course/N n'ont pas pu être exploitées (format/valeurs).",
                        )
        else:
            rapport["sous_systemes"]["architecture"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "architecture",
                "Non calculée (composant Architecture non fourni).",
            )

        # ------------------------------------------------------------
        # 9) PME requise (si non fournie) pour atteindre P_moteur_thermique_w
        # ------------------------------------------------------------
        pme_requise_pa: Optional[float] = None
        rpm_th = vitesse_moteur_thermique_rpm

        # On ne "prédit" pas la PME; on calcule la PME nécessaire si on connaît (P, Vd, rpm)
        if pme_pa is not None:
            pme_requise_pa = float(pme_pa)
        else:
            if _is_finite(P_moteur_thermique_w) and rpm_th is not None:
                # nécessite la cylindrée totale du moteur thermique effectif
                if moteur_thermique_effectif.alesage_m is not None and moteur_thermique_effectif.course_m is not None:
                    bore = float(moteur_thermique_effectif.alesage_m)
                    course = float(moteur_thermique_effectif.course_m)
                    N = int(moteur_thermique_effectif.nombre_cylindres)
                    temps = int(moteur_thermique_effectif.temps_moteur)

                    Vd_unit = (math.pi / 4.0) * bore * bore * course
                    Vd_tot = Vd_unit * max(1, N)

                    rpm = float(_require_positive("vitesse_moteur_thermique_rpm", rpm_th, strict=True))
                    f_cycles = (rpm / 60.0) / 2.0 if temps == 4 else (rpm / 60.0)

                    if Vd_tot > 1e-12 and f_cycles > 1e-12:
                        pme_requise_pa = float(P_moteur_thermique_w) / (Vd_tot * f_cycles)
                        rapport["notes_modele"].append("PME requise déduite de P_moteur_thermique, Vd_tot et fréquence cycles (ce n'est pas une PME prédite).")
                    else:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "PME requise",
                            "Impossible (Vd_tot ou f_cycles nul).",
                        )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "PME requise",
                        "Calculable si alesage_m et course_m (donc Vd) sont connus.",
                    )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "PME requise",
                    "Calculable si P_moteur_thermique_w et rpm moteur thermique sont connus, et si la cylindrée (alesage/course/N) est connue.",
                )

        rapport["liaisons"]["thermique_pme"] = {"pme_pa_utilisee_ou_requise": pme_requise_pa}

        # ------------------------------------------------------------
        # 10) Moteur thermique : analyse point de fonctionnement
        # ------------------------------------------------------------
        moteur_th_rapport: Optional[Dict[str, Any]] = None
        if rpm_th is not None:
            moteur_th_rapport = moteur_thermique_effectif.analyser_point_de_fonctionnement(
                rpm=float(rpm_th),
                pression_moyenne_effective_pa=pme_requise_pa,
                # Le reste (pression instantanée, gaz parfait, visco, etc.) dépend de données supplémentaires.
            )
            rapport["sous_systemes"]["moteur_thermique"] = moteur_th_rapport
            _merge_inconnues(rapport, moteur_th_rapport, prefix="moteur_thermique")
        else:
            rapport["sous_systemes"]["moteur_thermique"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "moteur thermique",
                "Analyse point de fonctionnement calculable si vitesse_moteur_thermique_rpm est fournie.",
            )

        # ------------------------------------------------------------
        # 11) Boîte à crabots : analyse au couple alternateur (si demandé)
        # ------------------------------------------------------------
        boite_rapport: Optional[Dict[str, Any]] = None
        if self.boite_crabots is not None and analyser_boite_sur_couple_alternateur:
            if _is_finite(couple_alt_nm):
                boite_rapport = self.boite_crabots.analyser_point(
                    couple_nm=float(couple_alt_nm),
                    vitesse_rotation_tr_min=rpm_alt,
                    calcul_forces_engrenage_actif=True,
                    moment_flechissant_nm=moment_flechissant_nm,
                    inertie_primaire_kg_m2=inertie_primaire_kg_m2,
                    inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
                    delta_omega_rad_s=delta_omega_rad_s,
                    temps_engagement_s=temps_engagement_s,
                    force_axiale_N=force_axiale_roulement_N,
                    force_radiale_N=force_radiale_roulement_N,
                )
                rapport["sous_systemes"]["boite_crabots"] = boite_rapport
                _merge_inconnues(rapport, boite_rapport, prefix="boite_crabots")
            else:
                rapport["sous_systemes"]["boite_crabots"] = None
                _push_inconnue(
                    rapport,
                    "partielles",
                    "boite_crabots",
                    "Analyse possible si couple alternateur est calculable (donc si alternateur donne couple_mecanique_Nm).",
                )
        else:
            rapport["sous_systemes"]["boite_crabots"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "boite_crabots",
                "Non calculée (composant non fourni ou analyse désactivée).",
            )

        # ------------------------------------------------------------
        # 12) Nettoyage
        # ------------------------------------------------------------
        _dedup_inconnues(rapport)
        return rapport


# ============================================================
# Exemple minimal (à adapter) — valeurs à fournir par toi
# ============================================================
if __name__ == "__main__":
    # IMPORTANT :
    # Cet exemple est volontairement "incomplet" : il montre comment appeler,
    # sans inventer de datasheet. Remplis avec TES valeurs.
    systeme = SystemeComplet(
        moteur_electrique=MoteurElectrique(
            puissance_max_w=10000.0,
            regime_max_rpm=6000.0,
            couple_max_nm=30.0,
            tension_bus_v=None,
            courant_max_a=None,
        ),
        batterie=Batterie(
            tension_nominale_v=400.0,
            capacite_nominale_ah=100.0,
        ),
        alternateur=Alternateur(
            connexion="etoile",
            nombre_poles=12,
        ),
        moteur_thermique=MoteurThermique(
            nombre_cylindres=1,
            temps_moteur=4,
        ),
        architecture=None,
        boite_crabots=None,
    )

    rapport = systeme.analyser(
        # exemple : donne un point véhicule complet, sinon tu auras des inconnues "partielles"
        masse_kg=1200.0,
        vitesse_ms=20.0,
        acceleration_ms2=0.5,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.65,
        rayon_roue_m=0.32,
        rapport_reduction_global=9.0,
        rendement_transmission=0.95,
        nb_moteurs_electriques=4,
        # alternateur
        vitesse_moteur_thermique_rpm=3000.0,
        rapport_vitesse_alt_sur_moteur=2.0,
        # puissance alternateur : si None, tentative de déduction via traction / charge
        puissance_elec_alt_cible_w=None,
    )

    # Affichage compact
    print("=== Rapport système (résumé) ===")
    print("Inconnues impossibles:", len(rapport["inconnues"]["impossibles"]))
    print("Inconnues partielles:", len(rapport["inconnues"]["partielles"]))
    print("Clés sous-systèmes:", list(rapport["sous_systemes"].keys()))
