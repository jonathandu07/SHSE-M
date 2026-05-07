# backend/components/boite_crabots.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple, List
import math

# ============================================================
# Imports des modules "boite_crabots" (robustes à l'arborescence)
# ============================================================

try:
    from backend.components.boite_crabots.modules.calcul_choc_engagement import (
        calcul_inertie_equivalente,
        calcul_energie_choc,
        calcul_couple_synchronisation_moyen,
    )
    from backend.components.boite_crabots.modules.calcul_force_pignon import (
        calcul_force_tangentielle,
        calcul_forces_engrenage,
    )
    from backend.components.boite_crabots.modules.calcul_contact_dent import calcul_contrainte_contact_hertz
    from backend.components.boite_crabots.modules.calcul_flexion_dent import calcul_contrainte_flexion_lewis
    from backend.components.boite_crabots.modules.calcul_dimensionnement_arbre import (
        calcul_contrainte_cisaillement_torsion,
        calcul_contrainte_flexion_arbre,
        calcul_von_mises_arbre,
    )
    from backend.components.boite_crabots.modules.calcul_dimensionnement_crabot import (
        calcul_couple_transmissible_crabot,
        calcul_pression_contact_crabot,
    )
    from backend.components.boite_crabots.modules.calcul_duree_vie_roulement import (
        calcul_charge_equivalente_roulement,
        calcul_duree_vie_l10,
        calcul_duree_vie_heures,
    )
except Exception:
    # Variante possible (si ton projet n'a pas le package backend.modules)
    from backend.components.boite_crabots.modules.calcul_choc_engagement import (
        calcul_inertie_equivalente,
        calcul_energie_choc,
        calcul_couple_synchronisation_moyen,
    )
    from backend.components.boite_crabots.modules.calcul_force_pignon import (
        calcul_force_tangentielle,
        calcul_forces_engrenage,
    )
    from backend.components.boite_crabots.modules.calcul_contact_dent import calcul_contrainte_contact_hertz
    from backend.components.boite_crabots.modules.calcul_flexion_dent import calcul_contrainte_flexion_lewis
    from backend.components.boite_crabots.modules.calcul_dimensionnement_arbre import (
        calcul_contrainte_cisaillement_torsion,
        calcul_contrainte_flexion_arbre,
        calcul_von_mises_arbre,
    )
    from backend.components.boite_crabots.modules.calcul_dimensionnement_crabot import (
        calcul_couple_transmissible_crabot,
        calcul_pression_contact_crabot,
    )
    from backend.components.boite_crabots.modules.calcul_duree_vie_roulement import (
        calcul_charge_equivalente_roulement,
        calcul_duree_vie_l10,
        calcul_duree_vie_heures,
    )

# ============================================================
# Imports "métier" : moteur + alternateur (pour l'intégration)
# ============================================================

try:
    from backend.components.alternateur.alternateur import Alternateur  # type: ignore
except Exception:
    Alternateur = Any  # type: ignore

try:
    from backend.components.moteur_thermique.moteur_thermique import MoteurThermique  # type: ignore
except Exception:
    MoteurThermique = Any  # type: ignore


# ============================================================
# Helpers
# ============================================================

TypeRoulement = Literal["bille", "rouleau"]
ConnexionCrabot = Literal["direct", "via_engrenage"]
StrategieOptimisation = Literal[
    "max_eta_alternateur",
    "min_pertes_alternateur",
    "min_couple_moteur",
    "pareto",
]


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

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _safe_get_float(obj: Any, name: str) -> Optional[float]:
    v = _safe_getattr(obj, name, None)
    if v is None:
        return None
    try:
        f = float(v)
    except Exception:
        return None
    return f if math.isfinite(f) else None


def _omega_from_rpm(rpm: float) -> float:
    return (2.0 * math.pi) * (rpm / 60.0)


# ============================================================
# Composant Boîte à crabots
# ============================================================

@dataclass(frozen=True)
class BoiteCrabots:
    """
    Composant d'analyse "boîte à crabots" visant à produire un maximum
    d'informations par calcul, et à laisser comme inconnues uniquement :
    - des données constructeur (roulement, matériaux, coefficients)
    - des données géométriques non fournies
    - des paramètres de montage/usage (temps d'engagement, inerties, etc.)

    + Intégration moteur -> boîte -> alternateur :
      - évalue des rapports de vitesse candidats,
      - calcule le point alternateur (Pdc demandée, vitesse),
      - déduit couple et puissance côté boîte (si rendement alternateur calculable),
      - sinon expose des bornes théoriques minimales (sans les confondre avec une valeur réelle),
      - passe le couple transmis dans les modules denture/crabot/roulements,
      - permet de choisir un rapport selon une stratégie (si les métriques existent).
    """

    # -------------------------
    # Géométrie engrenage
    # -------------------------
    diametre_primitif_m: Optional[float] = None  # d (m)
    largeur_denture_b_m: Optional[float] = None  # b (m)
    module_m: Optional[float] = None             # m (m) pour Lewis
    angle_pression_deg: float = 20.0
    angle_helice_deg: float = 0.0

    # Coefficients / facteurs (souvent inconnues constructeur)
    coefficient_zh: Optional[float] = None       # Z_H (Hertz)
    facteur_forme_y: Optional[float] = None      # Y (Lewis)

    # -------------------------
    # Crabot (géométrie + admissible)
    # -------------------------
    crabot_nombre_dents: Optional[int] = None
    crabot_hauteur_dent_m: Optional[float] = None
    crabot_largeur_dent_m: Optional[float] = None
    crabot_rayon_moyen_m: Optional[float] = None
    crabot_pression_admissible_pa: Optional[float] = None
    crabot_facteur_repartition: float = 1.0

    # -------------------------
    # Arbres (si tu veux calculer contraintes)
    # -------------------------
    diametre_arbre_m: Optional[float] = None

    # -------------------------
    # Roulements (si tu veux vie)
    # -------------------------
    roulement_C_N: Optional[float] = None
    roulement_X: Optional[float] = None
    roulement_Y: Optional[float] = None
    roulement_type: TypeRoulement = "bille"
    roulement_exposant_p: Optional[float] = None

    # -------------------------
    # Options
    # -------------------------
    clamp_non_negative: bool = True

    # ------------------------------------------------------------
    # Analyse mécanique locale (inchangé)
    # ------------------------------------------------------------
    def analyser_point(
        self,
        *,
        couple_nm: float,
        vitesse_rotation_tr_min: Optional[float] = None,
        calcul_forces_engrenage_actif: bool = True,
        moment_flechissant_nm: Optional[float] = None,
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_axiale_N: Optional[float] = None,
        force_radiale_N: Optional[float] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "resultats": {},
            "contraintes": {},
            "roulements": {},
            "crabot": {},
            "choc_engagement": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        T = _require_finite("couple_nm", couple_nm)
        rapport["entrees"]["couple_nm"] = T
        rapport["entrees"]["vitesse_rotation_tr_min"] = vitesse_rotation_tr_min

        # ============================================================
        # 1) Forces d'engrenage (si d primitif connu)
        # ============================================================
        Ft: Optional[float] = None
        Fr: Optional[float] = None
        Fa: Optional[float] = None

        if calcul_forces_engrenage_actif:
            if self.diametre_primitif_m is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "force_tangentielle F_t",
                    "Calculable si diametre_primitif_m est fourni (F_t = 2*T/d).",
                )
            else:
                d = _require_positive("diametre_primitif_m", self.diametre_primitif_m, strictly=True)
                Ft = calcul_force_tangentielle(
                    couple_nm=T,
                    diametre_primitif_m=d,
                    use_abs_couple=True,
                    clamp_non_negative=self.clamp_non_negative,
                )
                forces = calcul_forces_engrenage(
                    force_tangentielle=Ft,
                    angle_pression_deg=self.angle_pression_deg,
                    angle_helice_deg=self.angle_helice_deg,
                    output="FT_FR_FA",
                    use_abs_force=True,
                    clamp_non_negative=False,
                )
                Fr = float(forces["F_r"])
                Fa = float(forces["F_a"])

        if force_radiale_N is not None:
            Fr = _require_finite("force_radiale_N", force_radiale_N)
        if force_axiale_N is not None:
            Fa = _require_finite("force_axiale_N", force_axiale_N)

        rapport["resultats"]["F_t_N"] = Ft
        rapport["resultats"]["F_r_N"] = Fr
        rapport["resultats"]["F_a_N"] = Fa

        # ============================================================
        # 2) Contraintes sur denture (Hertz + Lewis)
        # ============================================================
        sigma_H: Optional[float] = None
        if (
            Ft is not None
            and self.largeur_denture_b_m is not None
            and self.diametre_primitif_m is not None
            and self.coefficient_zh is not None
        ):
            sigma_H = calcul_contrainte_contact_hertz(
                force_tangentielle=Ft,
                largeur_denture_b=self.largeur_denture_b_m,
                diametre_primitif_moyen=self.diametre_primitif_m,
                coefficient_zh=self.coefficient_zh,
                use_abs_force=True,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contrainte_contact_hertz sigma_H",
                "Calculable si Ft, largeur_denture_b_m, diametre_primitif_m et coefficient_zh sont fournis.",
            )

        sigma_F: Optional[float] = None
        if (
            Ft is not None
            and self.largeur_denture_b_m is not None
            and self.module_m is not None
            and self.facteur_forme_y is not None
        ):
            sigma_F = calcul_contrainte_flexion_lewis(
                force_tangentielle=Ft,
                largeur_denture_b=self.largeur_denture_b_m,
                module_m=self.module_m,
                facteur_forme_y=self.facteur_forme_y,
                use_abs_force=True,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contrainte_flexion_lewis sigma_F",
                "Calculable si Ft, largeur_denture_b_m, module_m et facteur_forme_y sont fournis.",
            )

        rapport["contraintes"]["sigma_H_Pa"] = sigma_H
        rapport["contraintes"]["sigma_F_Pa"] = sigma_F

        # ============================================================
        # 3) Contraintes arbre (torsion, flexion, Von Mises)
        # ============================================================
        tau_torsion: Optional[float] = None
        sigma_flexion_arbre: Optional[float] = None
        sigma_vm: Optional[float] = None

        if self.diametre_arbre_m is not None:
            d_arbre = _require_positive("diametre_arbre_m", self.diametre_arbre_m, strictly=True)

            tau_torsion = calcul_contrainte_cisaillement_torsion(
                couple_nm=T,
                diametre_arbre_m=d_arbre,
                use_abs_couple=True,
                clamp_non_negative=True,
            )

            if moment_flechissant_nm is not None:
                M = _require_finite("moment_flechissant_nm", moment_flechissant_nm)
                sigma_flexion_arbre = calcul_contrainte_flexion_arbre(
                    moment_flechissant_nm=M,
                    diametre_arbre_m=d_arbre,
                    use_abs_moment=True,
                    clamp_non_negative=True,
                )
                sigma_vm = calcul_von_mises_arbre(
                    contrainte_flexion=sigma_flexion_arbre,
                    contrainte_cisaillement=tau_torsion,
                    mode="flexion+torsion",
                    clamp_non_negative=True,
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "contraintes flexion/Von Mises arbre",
                    "Flexion/Von Mises calculables si moment_flechissant_nm est fourni (ou calculé via géométrie/appuis).",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contraintes arbre",
                "Calculables si diametre_arbre_m est fourni (et moment_flechissant_nm pour flexion/Von Mises).",
            )

        rapport["contraintes"]["tau_torsion_Pa"] = tau_torsion
        rapport["contraintes"]["sigma_flexion_arbre_Pa"] = sigma_flexion_arbre
        rapport["contraintes"]["sigma_von_mises_Pa"] = sigma_vm

        # ============================================================
        # 4) Crabot : couple transmissible + pression contact
        # ============================================================
        T_cap_crabot: Optional[float] = None
        p_contact_crabot: Optional[float] = None

        if (
            self.crabot_nombre_dents is not None
            and self.crabot_pression_admissible_pa is not None
            and self.crabot_hauteur_dent_m is not None
            and self.crabot_largeur_dent_m is not None
            and self.crabot_rayon_moyen_m is not None
        ):
            T_cap_crabot = calcul_couple_transmissible_crabot(
                nombre_dents=self.crabot_nombre_dents,
                pression_admissible=self.crabot_pression_admissible_pa,
                hauteur_dent=self.crabot_hauteur_dent_m,
                largeur_dent=self.crabot_largeur_dent_m,
                rayon_moyen=self.crabot_rayon_moyen_m,
                facteur_repartition=self.crabot_facteur_repartition,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "couple transmissible crabot T_cap",
                "Calculable si (crabot_nombre_dents, crabot_pression_admissible_pa, crabot_hauteur_dent_m, crabot_largeur_dent_m, crabot_rayon_moyen_m) sont fournis.",
            )

        if (
            self.crabot_nombre_dents is not None
            and self.crabot_hauteur_dent_m is not None
            and self.crabot_largeur_dent_m is not None
            and self.crabot_rayon_moyen_m is not None
        ):
            p_contact_crabot = calcul_pression_contact_crabot(
                couple_nm=T,
                nombre_dents=self.crabot_nombre_dents,
                hauteur_dent=self.crabot_hauteur_dent_m,
                largeur_dent=self.crabot_largeur_dent_m,
                rayon_moyen=self.crabot_rayon_moyen_m,
                use_abs_couple=True,
                facteur_repartition=self.crabot_facteur_repartition,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pression contact crabot p",
                "Calculable si (crabot_nombre_dents, crabot_hauteur_dent_m, crabot_largeur_dent_m, crabot_rayon_moyen_m) sont fournis.",
            )

        rapport["crabot"]["T_cap_Nm"] = T_cap_crabot
        rapport["crabot"]["p_contact_Pa"] = p_contact_crabot
        if T_cap_crabot is not None:
            rapport["crabot"]["ok_couple"] = bool(abs(T) <= T_cap_crabot)

        # ============================================================
        # 5) Roulements : charge équivalente + durée de vie
        # ============================================================
        P_eq: Optional[float] = None
        if Fr is not None and Fa is not None and self.roulement_X is not None and self.roulement_Y is not None:
            P_eq = calcul_charge_equivalente_roulement(
                force_radiale=Fr,
                force_axiale=Fa,
                facteur_x=self.roulement_X,
                facteur_y=self.roulement_Y,
                use_abs_forces=True,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "charge équivalente roulement P",
                "Calculable si Fr, Fa et facteurs roulement_X/roulement_Y sont connus.",
            )

        L10_millions: Optional[float] = None
        L10_heures: Optional[float] = None
        if P_eq is not None and self.roulement_C_N is not None:
            L10_millions = calcul_duree_vie_l10(
                charge_dynamique_base_c=self.roulement_C_N,
                charge_equivalente_p=P_eq,
                type_roulement=self.roulement_type,
                exposant_p=self.roulement_exposant_p,
                clamp_non_negative=True,
            )
            if vitesse_rotation_tr_min is not None:
                L10_heures = calcul_duree_vie_heures(
                    l10_millions=L10_millions,
                    vitesse_rotation_tr_min=_require_positive("vitesse_rotation_tr_min", vitesse_rotation_tr_min, strictly=True),
                    clamp_non_negative=True,
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "durée de vie roulement (heures)",
                    "Conversion L10h calculable si vitesse_rotation_tr_min est fournie.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "durée de vie roulement (L10)",
                "Calculable si charge équivalente P_eq et capacité dynamique roulement_C_N sont connues.",
            )

        rapport["roulements"]["P_eq_N"] = P_eq
        rapport["roulements"]["L10_millions_tours"] = L10_millions
        rapport["roulements"]["L10_heures"] = L10_heures

        # ============================================================
        # 6) Choc d'engagement (inertie eq, énergie, couple sync)
        # ============================================================
        Jeq: Optional[float] = None
        E_choc: Optional[float] = None
        T_sync: Optional[float] = None

        if inertie_primaire_kg_m2 is not None and inertie_secondaire_kg_m2 is not None:
            J1 = _require_finite("inertie_primaire_kg_m2", inertie_primaire_kg_m2)
            J2 = _require_finite("inertie_secondaire_kg_m2", inertie_secondaire_kg_m2)
            Jeq = calcul_inertie_equivalente(
                inertie_primaire=J1,
                inertie_secondaire=J2,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "inertie équivalente J_eq",
                "Calculable si inertie_primaire_kg_m2 et inertie_secondaire_kg_m2 sont fournies.",
            )

        if Jeq is not None and delta_omega_rad_s is not None:
            d_omega = _require_finite("delta_omega_rad_s", delta_omega_rad_s)
            E_choc = calcul_energie_choc(
                inertie_eq=Jeq,
                delta_omega_rad_s=d_omega,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "énergie de choc ΔE",
                "Calculable si J_eq et delta_omega_rad_s sont fournis.",
            )

        if Jeq is not None and delta_omega_rad_s is not None and temps_engagement_s is not None:
            T_sync = calcul_couple_synchronisation_moyen(
                inertie_eq=Jeq,
                delta_omega_rad_s=_require_finite("delta_omega_rad_s", delta_omega_rad_s),
                temps_engagement_s=_require_positive("temps_engagement_s", temps_engagement_s, strictly=True),
                use_abs_delta_omega=True,
                clamp_non_negative=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "couple de synchronisation moyen T_sync",
                "Calculable si J_eq, delta_omega_rad_s et temps_engagement_s sont fournis.",
            )

        rapport["choc_engagement"]["J_eq_kg_m2"] = Jeq
        rapport["choc_engagement"]["energie_choc_J"] = E_choc
        rapport["choc_engagement"]["couple_sync_moyen_Nm"] = T_sync

        # ============================================================
        # 7) Inconnues vraiment impossibles sans datasheet
        # ============================================================
        _push_inconnue(
            rapport,
            "impossibles",
            "coefficients matériau/qualité denture",
            "Z_H (contact Hertz), Y (Lewis), limites admissibles, facteurs dynamiques/fatigue nécessitent normes/datasheet ou calibration.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "géométrie complète + montage",
            "Sans entraxes, position des appuis, raideurs, alignements, on ne peut pas déduire les moments fléchissants et les répartitions réelles.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "données roulement constructeur",
            "C, facteurs X/Y (selon type, montage, Fa/Fr) proviennent des catalogues/abaques.",
        )

        _dedup_inconnues(rapport)
        return rapport

    # ------------------------------------------------------------
    # Intégration : moteur -> boîte -> alternateur (sans invention)
    # ------------------------------------------------------------
    def analyser_chaine_moteur_alternateur(
        self,
        *,
        alternateur: Alternateur,
        puissance_bus_dc_w: float,
        rpm_moteur: float,
        rapports: List[float],
        rendement_boite: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Optional[Any] = None,
        moteur: Optional[Any] = None,
        strategie: StrategieOptimisation = "pareto",
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_radiale_N: Optional[float] = None,
        force_axiale_N: Optional[float] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "candidats": [],
            "selection": None,
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        Pdc = _require_positive("puissance_bus_dc_w", puissance_bus_dc_w, strictly=False)
        rpm_m = _require_positive("rpm_moteur", rpm_moteur, strictly=True)

        if not isinstance(rapports, list) or len(rapports) == 0:
            raise ValueError("rapports doit être une liste non vide de rapports (float).")

        eta_boite: Optional[float] = None
        if rendement_boite is not None:
            eta_boite = _require_positive("rendement_boite", rendement_boite, strictly=True)
            if eta_boite > 1.0:
                raise ValueError("rendement_boite doit être <= 1.0")

        Vbus = tension_bus_dc_v
        if Vbus is None and batterie is not None:
            Vbus = _safe_get_float(batterie, "tension_nominale_v")
            if Vbus is None:
                Vbus = _safe_get_float(batterie, "tension_bus_v")
            if Vbus is None:
                Vbus = _safe_get_float(batterie, "tension_v")

        if Vbus is None:
            _push_inconnue(
                rapport,
                "partielles",
                "tension_bus_dc_v",
                "Donne tension_bus_dc_v (ou un objet batterie avec tension_nominale_v/tension_bus_v) pour déduire le courant DC.",
            )

        rapport["entrees"].update(
            {
                "puissance_bus_dc_w": Pdc,
                "rpm_moteur": rpm_m,
                "omega_moteur_rad_s": _omega_from_rpm(rpm_m),
                "rendement_boite": eta_boite,
                "tension_bus_dc_v": Vbus,
                "strategie": strategie,
            }
        )

        for r in rapports:
            if not _is_finite(r) or float(r) <= 0.0:
                rapport["notes_modele"].append(f"Rapport ignoré (invalide): {r!r}")
                continue

            ratio = float(r)
            rpm_alt = rpm_m * ratio
            omega_alt = _omega_from_rpm(rpm_alt)

            cand: Dict[str, Any] = {
                "rapport": ratio,
                "rpm_alternateur": rpm_alt,
                "omega_alternateur_rad_s": omega_alt,
                "alternateur": None,
                "boite": None,
                "exigences": {},
            }

            alt_report: Optional[Dict[str, Any]] = None
            if alternateur is None:
                _push_inconnue(rapport, "impossibles", "alternateur", "Objet alternateur requis.")
            else:
                if hasattr(alternateur, "analyser_pour_bus_dc"):
                    alt_report = alternateur.analyser_pour_bus_dc(  # type: ignore[call-arg]
                        puissance_bus_dc_w=Pdc,
                        vitesse_rotation_rpm=rpm_alt,
                        tension_bus_dc_v=Vbus,
                        batterie=batterie,
                        moteur=moteur,
                    )
                else:
                    if Vbus is None:
                        _push_inconnue(
                            rapport,
                            "impossibles",
                            "analyse alternateur en DC",
                            "Sans tension DC (Vbus), impossible de déterminer le courant DC et donc P_out via V*I.",
                        )
                    else:
                        Ibus = Pdc / Vbus if abs(Vbus) > 1e-12 else float("inf")
                        alt_report = alternateur.analyser_point_de_fonctionnement(  # type: ignore[call-arg]
                            vitesse_rotation_rpm=rpm_alt,
                            mode_electrique="dc",
                            tension_v=Vbus,
                            courant_a=Ibus,
                        )

            cand["alternateur"] = alt_report

            # Extractions : P_out, eta_total, P_mec, T_mec, pertes
            # analyser_point_de_fonctionnement() -> clés au niveau racine
            # analyser_pour_bus_dc() -> sous-dict rep["alternateur"]
            P_out: Optional[float] = None
            eta_alt: Optional[float] = None
            P_mec_alt: Optional[float] = None
            T_mec_alt: Optional[float] = None
            P_pertes_alt: Optional[float] = None

            alt_core: Optional[Dict[str, Any]] = None
            if isinstance(alt_report, dict):
                if isinstance(alt_report.get("alternateur", None), dict):
                    alt_core = alt_report.get("alternateur", None)
                else:
                    alt_core = alt_report

            if isinstance(alt_core, dict):
                try:
                    P_out = alt_core.get("resultats", {}).get("P_out_W", None)
                    eta_alt = alt_core.get("resultats", {}).get("eta_total", None)
                    P_mec_alt = alt_core.get("resultats", {}).get("P_mecanique_W", None)
                    T_mec_alt = alt_core.get("resultats", {}).get("couple_mecanique_Nm", None)
                    P_pertes_alt = alt_core.get("pertes", {}).get("P_pertes_totales_W", None)
                except Exception:
                    pass

            # Bornes minimales théoriques (rendement = 100%)
            P_mec_min_theorique = Pdc
            T_alt_min_theorique = (Pdc / omega_alt) if abs(omega_alt) > 1e-12 else None

            cand["exigences"].update(
                {
                    "P_out_W": P_out,
                    "eta_alternateur": eta_alt,
                    "P_pertes_alternateur_W": P_pertes_alt,
                    "P_mecanique_alternateur_W": P_mec_alt,
                    "couple_alternateur_Nm": T_mec_alt,
                    "P_mec_min_theorique_W": P_mec_min_theorique,
                    "couple_alt_min_theorique_Nm": T_alt_min_theorique,
                }
            )

            def _remonte_couple(T_out: Optional[float]) -> Optional[float]:
                if T_out is None:
                    return None
                if eta_boite is None:
                    return T_out * ratio
                return (T_out * ratio) / eta_boite

            def _remonte_puissance(P_out_meca: Optional[float]) -> Optional[float]:
                if P_out_meca is None:
                    return None
                if eta_boite is None:
                    return P_out_meca
                return P_out_meca / eta_boite

            T_moteur_requis = _remonte_couple(T_mec_alt)
            P_moteur_requise = _remonte_puissance(P_mec_alt)

            T_moteur_min_theorique = _remonte_couple(T_alt_min_theorique) if T_alt_min_theorique is not None else None
            P_moteur_min_theorique = _remonte_puissance(P_mec_min_theorique)

            cand["exigences"].update(
                {
                    "couple_moteur_requis_Nm": T_moteur_requis,
                    "puissance_moteur_requise_W": P_moteur_requise,
                    "couple_moteur_min_theorique_Nm": T_moteur_min_theorique,
                    "puissance_moteur_min_theorique_W": P_moteur_min_theorique,
                }
            )

            couple_pour_dimensionnement = T_moteur_requis
            tag_couple = "reel"
            if couple_pour_dimensionnement is None:
                couple_pour_dimensionnement = T_moteur_min_theorique
                tag_couple = "borne_min_theorique"

            if couple_pour_dimensionnement is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "couple transmis",
                    "Impossible : ni couple alternateur calculé, ni borne théorique (omega_alt=0 ?).",
                )
                boite_report = None
            else:
                boite_report = self.analyser_point(
                    couple_nm=float(couple_pour_dimensionnement),
                    vitesse_rotation_tr_min=rpm_m,
                    inertie_primaire_kg_m2=inertie_primaire_kg_m2,
                    inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
                    delta_omega_rad_s=delta_omega_rad_s,
                    temps_engagement_s=temps_engagement_s,
                    force_radiale_N=force_radiale_N,
                    force_axiale_N=force_axiale_N,
                )
                boite_report.setdefault("notes_modele", [])
                boite_report["notes_modele"].append(f"Couple d'entrée utilisé: {tag_couple}")

            cand["boite"] = boite_report

            # Estimation conso : uniquement si le moteur fournit BSFC (g/kWh)
            bsfc_g_kwh = None
            if moteur is not None:
                bsfc_g_kwh = _safe_get_float(moteur, "bsfc_g_kwh")
                if bsfc_g_kwh is None:
                    bsfc_g_kwh = _safe_get_float(moteur, "consommation_specifique_g_kwh")

            if bsfc_g_kwh is not None:
                P_for_fuel = P_moteur_requise if P_moteur_requise is not None else P_moteur_min_theorique
                if P_for_fuel is not None:
                    fuel_g_h = bsfc_g_kwh * (float(P_for_fuel) / 1000.0)
                    cand["exigences"]["bsfc_g_kwh_utilisee"] = bsfc_g_kwh
                    cand["exigences"]["debit_carburant_g_h_estime"] = fuel_g_h
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "débit carburant",
                        "BSFC fournie, mais puissance moteur requise indéterminable (rendements manquants).",
                    )

            rapport["candidats"].append(cand)

        if len(rapport["candidats"]) == 0:
            _push_inconnue(
                rapport,
                "impossibles",
                "rapports",
                "Aucun rapport valide (>0) dans la liste fournie.",
            )
            _dedup_inconnues(rapport)
            return rapport

        def _metric(c: Dict[str, Any], key: str) -> Optional[float]:
            try:
                v = c.get("exigences", {}).get(key, None)
                if v is None:
                    return None
                f = float(v)
                return f if math.isfinite(f) else None
            except Exception:
                return None

        selection: Optional[Dict[str, Any]] = None

        if strategie in ("max_eta_alternateur", "min_pertes_alternateur", "min_couple_moteur"):
            scored: List[Tuple[float, Dict[str, Any]]] = []
            for c in rapport["candidats"]:
                if strategie == "max_eta_alternateur":
                    m = _metric(c, "eta_alternateur")
                    if m is not None:
                        scored.append((m, c))
                elif strategie == "min_pertes_alternateur":
                    m = _metric(c, "P_pertes_alternateur_W")
                    if m is not None:
                        scored.append((-m, c))  # minimisation
                else:
                    m = _metric(c, "couple_moteur_requis_Nm")
                    if m is None:
                        m = _metric(c, "couple_moteur_min_theorique_Nm")
                    if m is not None:
                        scored.append((-m, c))  # minimisation

            if len(scored) == 0:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "selection",
                    f"Impossible d'appliquer la stratégie {strategie}: métriques indisponibles (modèles/paramètres manquants).",
                )
            else:
                scored.sort(key=lambda t: t[0], reverse=True)
                selection = scored[0][1]

        elif strategie == "pareto":
            pts: List[Tuple[float, float, Dict[str, Any]]] = []
            for c in rapport["candidats"]:
                eta = _metric(c, "eta_alternateur")
                t = _metric(c, "couple_moteur_requis_Nm")
                if t is None:
                    t = _metric(c, "couple_moteur_min_theorique_Nm")
                if eta is not None and t is not None:
                    pts.append((eta, t, c))

            if len(pts) == 0:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "pareto",
                    "Impossible de calculer un Pareto (eta_alternateur et couple_moteur manquants).",
                )
            else:
                front: List[Dict[str, Any]] = []
                for i, (eta_i, t_i, c_i) in enumerate(pts):
                    dominated = False
                    for j, (eta_j, t_j, _c_j) in enumerate(pts):
                        if j == i:
                            continue
                        if (eta_j >= eta_i and t_j <= t_i) and (eta_j > eta_i or t_j < t_i):
                            dominated = True
                            break
                    if not dominated:
                        front.append(c_i)
                rapport["selection"] = {"pareto_front": front, "count": len(front)}
        else:
            raise ValueError("strategie invalide.")

        if selection is not None:
            rapport["selection"] = {
                "strategie": strategie,
                "rapport": selection.get("rapport"),
                "resume": selection.get("exigences", {}),
            }

        _dedup_inconnues(rapport)
        return rapport
