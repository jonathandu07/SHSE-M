# backend/components/boite_crabots.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple
import math


# ============================================================
# Imports des modules "boite_crabots" (robustes à l'arborescence)
# ============================================================

try:
    from backend.modules.boite_crabots.calcul_choc_engagement import (
        calcul_inertie_equivalente,
        calcul_energie_choc,
        calcul_couple_synchronisation_moyen,
    )
    from backend.modules.boite_crabots.calcul_force_pignon import (
        calcul_force_tangentielle,
        calcul_forces_engrenage,
    )
    from backend.modules.boite_crabots.calcul_contact_dent import calcul_contrainte_contact_hertz
    from backend.modules.boite_crabots.calcul_flexion_dent import calcul_contrainte_flexion_lewis
    from backend.modules.boite_crabots.calcul_dimensionnement_arbre import (
        calcul_contrainte_cisaillement_torsion,
        calcul_contrainte_flexion_arbre,
        calcul_von_mises_arbre,
    )
    from backend.modules.boite_crabots.calcul_dimensionnement_crabot import (
        calcul_couple_transmissible_crabot,
        calcul_pression_contact_crabot,
    )
    from backend.modules.boite_crabots.calcul_duree_vie_roulement import (
        calcul_charge_equivalente_roulement,
        calcul_duree_vie_l10,
        calcul_duree_vie_heures,
    )
except Exception:
    # Variante possible (si ton projet n'a pas le package backend.modules)
    from backend.modules.boite_crabots.calcul_choc_engagement import (
        calcul_inertie_equivalente,
        calcul_energie_choc,
        calcul_couple_synchronisation_moyen,
    )
    from backend.modules.boite_crabots.calcul_force_pignon import (
        calcul_force_tangentielle,
        calcul_forces_engrenage,
    )
    from backend.modules.boite_crabots.calcul_contact_dent import calcul_contrainte_contact_hertz
    from backend.modules.boite_crabots.calcul_flexion_dent import calcul_contrainte_flexion_lewis
    from backend.modules.boite_crabots.calcul_dimensionnement_arbre import (
        calcul_contrainte_cisaillement_torsion,
        calcul_contrainte_flexion_arbre,
        calcul_von_mises_arbre,
    )
    from backend.modules.boite_crabots.calcul_dimensionnement_crabot import (
        calcul_couple_transmissible_crabot,
        calcul_pression_contact_crabot,
    )
    from backend.modules.boite_crabots.calcul_duree_vie_roulement import (
        calcul_charge_equivalente_roulement,
        calcul_duree_vie_l10,
        calcul_duree_vie_heures,
    )


# ============================================================
# Helpers
# ============================================================

TypeRoulement = Literal["bille", "rouleau"]
ConnexionCrabot = Literal["direct", "via_engrenage"]


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

    Les modules utilisés couvrent :
    - choc d'engagement (inertie eq, énergie, couple sync)
    - forces sur pignon (Ft, Fr, Fa)
    - contrainte contact (Hertz simplifié)
    - contrainte flexion dent (Lewis simplifié)
    - contraintes arbre (torsion, flexion, Von Mises)
    - crabot (pression contact, couple transmissible)
    - roulements (charge équivalente, L10, L10h)
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

    def analyser_point(
        self,
        *,
        # Entrées fonctionnelles
        couple_nm: float,
        vitesse_rotation_tr_min: Optional[float] = None,
        # Si engrenage
        calcul_forces_engrenage_actif: bool = True,
        # Si tu as un moment de flexion arbre (sinon partiel)
        moment_flechissant_nm: Optional[float] = None,
        # Choc d'engagement
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        # Forces roulement (si tu veux vie)
        force_axiale_N: Optional[float] = None,
        # (Fr peut venir de l'engrenage; sinon tu peux le donner)
        force_radiale_N: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Produit un rapport complet à partir d'un couple transmis et (optionnellement)
        d'une vitesse et de paramètres de choc.

        Retour:
        {
          "entrees": {...},
          "resultats": {...},
          "contraintes": {...},
          "roulements": {...},
          "crabot": {...},
          "choc_engagement": {...},
          "inconnues": {"impossibles": [...], "partielles": [...]}
        }
        """
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

        # override forces si l'utilisateur les passe explicitement
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
        # 2.1 Contact Hertz
        sigma_H: Optional[float] = None
        if Ft is not None and self.largeur_denture_b_m is not None and self.diametre_primitif_m is not None and self.coefficient_zh is not None:
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

        # 2.2 Flexion Lewis
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

        # Capacité
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

        # Pression contact au couple demandé
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
            rapport["crabot"]["ok_couple"] = bool(abs(T) <= T_cap_crabot)  # magnitude simple

        # ============================================================
        # 5) Roulements : charge équivalente + durée de vie
        # ============================================================
        # Charge équivalente
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

        # L10 + L10h
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
        # (On les déclare explicitement pour ton objectif "minimum d'inconnu")
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
