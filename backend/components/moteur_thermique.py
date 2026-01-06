# backend/components/moteur_thermique.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple, List
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
# Imports des modules "architecture" (pour DÉFINIR le moteur)
# (si absents dans ton repo, le dimensionnement global restera "inconnu")
# ============================================================

_ARCHI_OK = True
try:
    from backend.modules.architecture.calcul_cylindree_totale import calcul_cylindree_totale_requise
    from backend.modules.architecture.calcul_cylindree_admissible import (
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )
    from backend.modules.architecture.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min
    from backend.modules.architecture.choix_architecture_optimale import (
        choix_architecture_optimale,
        evaluer_architecture,
    )
except Exception:
    _ARCHI_OK = False


# ============================================================
# Helpers
# ============================================================

TempsMoteur = Literal[2, 4]
TypePuissance = Literal["indiquee", "frein"]


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


def _require_between_0_1(name: str, x: Any, *, allow_1: bool = True) -> float:
    v = _require_finite(name, x)
    if allow_1:
        ok = (v > 0.0) and (v <= 1.0)
    else:
        ok = (v > 0.0) and (v < 1.0)
    if not ok:
        raise ValueError(f"{name} doit être dans ]0,1]{' ' if allow_1 else ''}(reçu: {v}).")
    return v


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


def _rpm_from_power_torque(power_w: float, torque_nm: float) -> float:
    """
    n = (P / T) * (60 / 2π)
    (pur calcul physique, aucune hypothèse moteur)
    """
    P = _require_finite("power_w", power_w)
    T = _require_finite("torque_nm", torque_nm)
    if T == 0.0:
        raise ValueError("torque_nm ne peut pas être 0 (division).")
    return (P / T) * (60.0 / (2.0 * math.pi))


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
    - dV/dt (m³/s) estimé
    - dh/dt (m/s) si aire connue

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

    V_1s = calcul_volume_usure_archard(
        coefficient_usure_k=k,
        charge_normale_w=W_n,
        distance_glissement_ls=max(0.0, float(v_ms)),
        durete_h=H_pa,
    )
    out["dV_dt_m3_s"] = float(V_1s)
    out["dV_par_heure_m3_h"] = float(V_1s) * 3600.0

    if aire_contact_m2 is not None:
        dh_1s = calcul_perte_epaisseur(volume_use_m3=V_1s, aire_contact_m2=aire_contact_m2)
        out["dh_dt_m_s"] = float(dh_1s)
        out["dh_par_heure_m_h"] = float(dh_1s) * 3600.0

    return out


def _bore_stroke_from_Vd_ratio(Vd_m3: float, ratio_course_alesage: float) -> Tuple[float, float]:
    """
    Résolution exacte :
        Vd = (π/4)*B²*S  et  r = S/B
        => Vd = (π/4)*B³*r
        => B = (4*Vd/(π*r))^(1/3),  S = r*B
    """
    Vd = _require_positive("Vd_m3", Vd_m3, strictly=True)
    r = _require_positive("ratio_course_alesage", ratio_course_alesage, strictly=True)
    B = (4.0 * Vd / (math.pi * r)) ** (1.0 / 3.0)
    S = r * B
    return float(B), float(S)


# ============================================================
# Composant moteur thermique (calcul + définition)
# ============================================================

@dataclass(frozen=True)
class MoteurThermique:
    """
    - analyser_point_de_fonctionnement(): calcule un point (forces, couple, pertes, usure, etc.)
    - definir_depuis_exigences(): définit un moteur (B, S, N, archi) UNIQUEMENT si calculable.
      Si une info manque, elle est listée comme inconnue et AUCUNE valeur n'est inventée.
    """

    # --- Géométrie de base ---
    alesage_m: Optional[float] = None
    course_m: Optional[float] = None
    nombre_cylindres: int = 1
    temps_moteur: TempsMoteur = 4  # 2 ou 4 (si tu veux éviter tout défaut, passe-le explicitement)

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

    # --- Usure Archard (coeffs tribologie) ---
    coefficient_usure_segment_k: Optional[float] = None
    durete_contact_segment_pa: Optional[float] = None
    aire_contact_segment_m2: Optional[float] = None

    coefficient_usure_palier_k: Optional[float] = None
    durete_contact_palier_pa: Optional[float] = None
    aire_contact_palier_m2: Optional[float] = None

    # --- Précharge vis (couvercle) ---
    facteur_securite_vis: float = 1.5
    facteur_frottement_vis_k: float = 0.2  # modèle K (si tu ne veux rien "par défaut", passe-le explicitement)

    clamp_non_negative: bool = True

    # ============================================================
    # DÉFINITION DU MOTEUR PAR LE CALCUL (aucune invention)
    # ============================================================

    @classmethod
    def definir_depuis_exigences(
        cls,
        *,
        # Besoin de performance
        puissance_visee_w: Optional[float],
        type_puissance: TypePuissance,
        rpm: Optional[float],
        pression_moyenne_effective_pa: Optional[float],
        temps_moteur: TempsMoteur,

        # Pour convertir "frein" -> "indiquée" si nécessaire
        rendement_mecanique: Optional[float] = None,

        # Contraintes de dimensionnement dynamique/géométrique
        vitesse_piston_max_ms: Optional[float] = None,
        ratio_course_alesage_max: Optional[float] = None,

        # Si tu veux une géométrie unique (sinon on ne peut pas choisir B,S)
        ratio_course_alesage_cible: Optional[float] = None,

        # Packaging (si tu veux choisir L/V/W/Étoile par calcul)
        L_max_m: Optional[float] = None,
        W_max_m: Optional[float] = None,
        architectures_autorisees: Optional[Tuple[str, ...]] = None,
        architecture_forcee: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retourne un rapport complet :
        - moteur_defini: instance cls(...) si et seulement si B,S,N sont calculables
        - sinon: moteur_defini = None + liste d'inconnues (impossibles/partielles)

        Aucune valeur n'est supposée si non fournie.
        """
        rapport: Dict[str, Any] = {
            "entrees": {},
            "dimensionnement": {},
            "architecture": {},
            "moteur_defini": None,
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        rapport["entrees"].update(
            {
                "puissance_visee_w": puissance_visee_w,
                "type_puissance": type_puissance,
                "rpm": rpm,
                "pression_moyenne_effective_pa": pression_moyenne_effective_pa,
                "temps_moteur": int(temps_moteur),
                "rendement_mecanique": rendement_mecanique,
                "vitesse_piston_max_ms": vitesse_piston_max_ms,
                "ratio_course_alesage_max": ratio_course_alesage_max,
                "ratio_course_alesage_cible": ratio_course_alesage_cible,
                "L_max_m": L_max_m,
                "W_max_m": W_max_m,
                "architectures_autorisees": architectures_autorisees,
                "architecture_forcee": architecture_forcee,
                "modules_architecture_disponibles": _ARCHI_OK,
            }
        )

        if not _ARCHI_OK:
            _push_inconnue(
                rapport,
                "impossibles",
                "dimensionnement global (architecture)",
                "Modules backend.modules.architecture.* indisponibles : impossible de définir B/S/N par ces calculs.",
            )
            _dedup_inconnues(rapport)
            return rapport

        # --- validations minimales (sans inventer) ---
        if puissance_visee_w is None:
            _push_inconnue(rapport, "impossibles", "puissance_visee_w", "Obligatoire pour dimensionner la cylindrée requise.")
        if rpm is None:
            _push_inconnue(rapport, "impossibles", "rpm", "Obligatoire pour la fréquence de cycle et les contraintes piston.")
        if pression_moyenne_effective_pa is None:
            _push_inconnue(rapport, "impossibles", "pression_moyenne_effective_pa", "Obligatoire pour relier puissance <-> cylindrée.")
        if vitesse_piston_max_ms is None:
            _push_inconnue(rapport, "impossibles", "vitesse_piston_max_ms", "Obligatoire pour borner le dimensionnement (cinématique).")
        if ratio_course_alesage_max is None:
            _push_inconnue(rapport, "impossibles", "ratio_course_alesage_max", "Obligatoire pour borner la géométrie (S/B).")

        if rapport["inconnues"]["impossibles"]:
            _dedup_inconnues(rapport)
            return rapport

        # --- conversion puissance frein -> indiquée (si demandé) ---
        P_visee = _require_positive("puissance_visee_w", puissance_visee_w, strictly=True)
        if type_puissance == "frein":
            if rendement_mecanique is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "rendement_mecanique",
                    "Nécessaire pour convertir une puissance frein en puissance indiquée (P_i = P_frein / η_meca).",
                )
                _dedup_inconnues(rapport)
                return rapport
            eta = _require_between_0_1("rendement_mecanique", rendement_mecanique, allow_1=True)
            P_indiquee = P_visee / eta
        else:
            P_indiquee = P_visee

        # --- fréquence de cycles ---
        rpm_val = _require_positive("rpm", rpm, strictly=True)
        freq_cycle_hz = _cycles_par_seconde(rpm_val, int(temps_moteur))

        # --- cylindrée totale requise (module) ---
        pme = _require_positive("pression_moyenne_effective_pa", pression_moyenne_effective_pa, strictly=True)
        Vd_tot_req = float(
            calcul_cylindree_totale_requise(
                puissance_w=P_indiquee,
                pression_moyenne_effective_pa=pme,
                frequence_cycle_hz=freq_cycle_hz,
                rendement_mecanique=1.0,  # ici P_indiquee est déjà "avant pertes mécaniques"
            )
        )

        # --- cylindrée unitaire max admissible (modules) ---
        Umax = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strictly=False)
        r_max = _require_positive("ratio_course_alesage_max", ratio_course_alesage_max, strictly=True)

        bore_max_m = float(calcul_bore_max_admissible(Umax, rpm_val, r_max))
        Vd_unit_max = float(calcul_cylindree_unit_max(bore_max_m, r_max))

        if Vd_unit_max <= 0.0:
            _push_inconnue(
                rapport,
                "impossibles",
                "cylindree_unitaire_max",
                "Le calcul donne une cylindrée unitaire max <= 0 (vérifie Umax, rpm, r_max).",
            )
            _dedup_inconnues(rapport)
            return rapport

        # --- nombre de cylindres minimal ---
        n_min = int(calcul_nombre_cylindres_min(Vd_tot_req, Vd_unit_max))

        # --- choix d'une cylindrée unitaire "par cylindre" : ici on propose 2 modes ---
        # 1) mode "limites" (compact en N) : Vd_unit = Vd_unit_max -> N = n_min
        Vd_unit_limite = Vd_tot_req / float(n_min)

        # bore/stroke (mode limites) :
        # - si ratio_course_alesage_cible fourni : géométrie exacte et vérifications
        # - sinon : on NE CHOISIT PAS un ratio "au hasard" -> on ne peut pas donner (B,S) uniques
        #   sauf si tu acceptes explicitement le mode "limites" à r_max (ce qui est un calcul déterministe).
        bore_m: Optional[float] = None
        stroke_m: Optional[float] = None
        ratio_utilise: Optional[float] = None

        if ratio_course_alesage_cible is not None:
            r_cible = _require_positive("ratio_course_alesage_cible", ratio_course_alesage_cible, strictly=True)
            if r_cible > r_max:
                raise ValueError(f"ratio_course_alesage_cible ({r_cible}) > ratio_course_alesage_max ({r_max}) : incohérent.")
            bore_m, stroke_m = _bore_stroke_from_Vd_ratio(Vd_unit_limite, r_cible)
            ratio_utilise = r_cible
        else:
            # On ne peut pas "inventer" un ratio, MAIS on peut produire une solution déterministe
            # si on accepte explicitement le dimensionnement "aux limites géométriques" :
            # on prend r = r_max (comme les modules admissibles le font pour Vd_unit_max).
            bore_m, stroke_m = _bore_stroke_from_Vd_ratio(Vd_unit_limite, r_max)
            ratio_utilise = r_max
            rapport["notes_modele"].append(
                "Géométrie définie avec ratio_course_alesage = ratio_course_alesage_max (dimensionnement aux limites, déterministe). "
                "Si tu veux une autre géométrie, fournis ratio_course_alesage_cible."
            )

        # --- vérification piston speed (pure vérification, pas invention) ---
        # vitesse moyenne piston = 2*S*n/60
        v_piston_moy = 2.0 * float(stroke_m) * (rpm_val / 60.0)
        if v_piston_moy > Umax + 1e-12:
            raise ValueError(
                f"Incohérence: vitesse moyenne piston {v_piston_moy:.6g} m/s > Umax {Umax:.6g} m/s "
                f"(stroke={stroke_m}, rpm={rpm_val})."
            )

        # --- architecture (si contraintes L/W connues) ---
        archi_choisie: Optional[str] = None
        details_archis: Dict[str, Any] = {}

        if architecture_forcee is not None:
            archi_choisie = str(architecture_forcee)
        else:
            if L_max_m is None or W_max_m is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "choix architecture",
                    "Calculable si L_max_m et W_max_m sont fournis (sinon pas de sélection L/V/W/Étoile).",
                )
            else:
                Lm = _require_positive("L_max_m", L_max_m, strictly=True)
                Wm = _require_positive("W_max_m", W_max_m, strictly=True)

                archis = architectures_autorisees or ("L", "V", "W", "Etoile")
                for a in archis:
                    try:
                        details_archis[str(a)] = evaluer_architecture(str(a), n_min, Lm, Wm)
                    except Exception as e:
                        details_archis[str(a)] = {"erreur": str(e)}

                try:
                    archi_choisie = str(choix_architecture_optimale(n_min, Lm, Wm))
                except Exception as e:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "choix architecture",
                        f"Échec du module de choix d'architecture: {e}",
                    )

        rapport["dimensionnement"].update(
            {
                "P_indiquee_calculee_W": float(P_indiquee),
                "frequence_cycle_hz": float(freq_cycle_hz),
                "Vd_totale_requise_m3": float(Vd_tot_req),
                "bore_max_admissible_m": float(bore_max_m),
                "Vd_unitaire_max_m3": float(Vd_unit_max),
                "nombre_cylindres_min": int(n_min),
                "Vd_unitaire_choisie_m3": float(Vd_unit_limite),
                "ratio_course_alesage_utilise": float(ratio_utilise) if ratio_utilise is not None else None,
                "alesage_defini_m": float(bore_m) if bore_m is not None else None,
                "course_definie_m": float(stroke_m) if stroke_m is not None else None,
                "vitesse_moyenne_piston_ms": float(v_piston_moy),
            }
        )

        rapport["architecture"].update(
            {
                "details_par_architecture": details_archis,
                "architecture_choisie": archi_choisie,
            }
        )

        # --- moteur défini ---
        moteur = cls(
            alesage_m=float(bore_m),
            course_m=float(stroke_m),
            nombre_cylindres=int(n_min),
            temps_moteur=temps_moteur,
        )
        rapport["moteur_defini"] = moteur

        _dedup_inconnues(rapport)
        return rapport

    # ============================================================
    # ANALYSE POINT DE FONCTIONNEMENT (déjà calculatoire)
    # ============================================================

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
                "temps_moteur": int(self.temps_moteur),
                "nombre_cylindres": int(self.nombre_cylindres),
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
                v_piston_moy = float(calcul_vitesse_moyenne_piston(course_m=self.course_m, vitesse_rotation_tr_min=rpm_val))
            else:
                _push_inconnue(rapport, "partielles", "vitesse moyenne piston", "Calculable si course_m est fournie.")
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
            _push_inconnue(rapport, "partielles", "travail/power indiqué", "Calculables si PME et alesage/course sont fournis.")

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
            _push_inconnue(rapport, "partielles", "pression gaz parfait", "Calculable si masse_gaz_kg, volume_gaz_m3, temperature_gaz_k sont fournis.")

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
            _push_inconnue(rapport, "partielles", "température adiabatique T2", "Calculable si t1_k, p1_pa, p2_pa sont fournis (et gamma).")

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
                    jeu_radial_h_m=_require_positive("jeu_radial_h_m", jeu_radial_h_m, strictly=False),
                    rayon_m=_require_positive("rayon_fuite_m", rayon_fuite_m, strictly=False),
                    longueur_fuite_l_m=_require_positive("longueur_fuite_m", longueur_fuite_m, strictly=True),
                    viscosite_dynamique_pa_s=_require_positive("viscosite_pa_s", self.viscosite_pa_s, strictly=True),
                    use_abs_delta_p=True,
                    clamp_non_negative=True,
                    return_details=False,
                )
            )

            if self.densite_kg_m3 is not None:
                m_dot_fuite = float(
                    calcul_masse_fuite(
                        debit_volumique_m3s=Q_fuite,
                        densite_kg_m3=_require_positive("densite_kg_m3", self.densite_kg_m3, strictly=False),
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
            _push_inconnue(rapport, "partielles", "pertes frottement segment", "Calculables si force_normale_segment_n, coef_frottement_segment, rpm et course_m sont fournis.")

        if charge_palier_n is not None and vitesse_glissement_palier_ms is not None and self.coef_frottement_palier is not None:
            P_frott_palier = float(
                calcul_puissance_frottement_palier(
                    charge_w=_require_positive("charge_palier_n", charge_palier_n, strictly=False),
                    vitesse_glissement_ms=_require_positive("vitesse_glissement_palier_ms", vitesse_glissement_palier_ms, strictly=False),
                    coef_frottement_f=_require_positive("coef_frottement_palier", self.coef_frottement_palier, strictly=False),
                )
            )
        else:
            _push_inconnue(rapport, "partielles", "pertes frottement palier", "Calculables si charge_palier_n, vitesse_glissement_palier_ms et coef_frottement_palier sont fournis.")

        P_frott_total: Optional[float] = None
        if P_frott_seg is not None or P_frott_palier is not None:
            P_frott_total = float((P_frott_seg or 0.0) + (P_frott_palier or 0.0))

        rapport["pertes"]["P_frottement_segment_W"] = P_frott_seg
        rapport["pertes"]["P_frottement_palier_W"] = P_frott_palier
        rapport["pertes"]["P_frottement_total_W"] = P_frott_total

        # ============================================================
        # 9) Usure (Archard) : taux + cumulé si durée fournie
        # ============================================================
        usure_seg = _archard_depuis_vitesse(
            k=self.coefficient_usure_segment_k,
            W_n=force_normale_segment_n,
            v_ms=v_piston_moy,
            H_pa=self.durete_contact_segment_pa,
            aire_contact_m2=self.aire_contact_segment_m2,
        )
        usure_pal = _archard_depuis_vitesse(
            k=self.coefficient_usure_palier_k,
            W_n=charge_palier_n,
            v_ms=vitesse_glissement_palier_ms,
            H_pa=self.durete_contact_palier_pa,
            aire_contact_m2=self.aire_contact_palier_m2,
        )

        rapport["usure"]["segments"] = usure_seg
        rapport["usure"]["palier"] = usure_pal

        if duree_fonctionnement_s is not None:
            t_s = _require_positive("duree_fonctionnement_s", duree_fonctionnement_s, strictly=False)

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
                _push_inconnue(rapport, "partielles", "usure cumulée segments", "Calculable si (k, W, H) segments + vitesse piston sont fournis (et aire pour épaisseur).")

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
                _push_inconnue(rapport, "partielles", "usure cumulée palier", "Calculable si (k, W, H) palier + vitesse palier sont fournis (et aire pour épaisseur).")
        else:
            _push_inconnue(rapport, "partielles", "usure cumulée", "Une durée (duree_fonctionnement_s) est nécessaire pour passer des taux (dV/dt) à un total.")

        if self.coefficient_usure_segment_k is None or self.durete_contact_segment_pa is None:
            _push_inconnue(rapport, "impossibles", "usure segments (valeur absolue)", "Impossible sans coefficient d'usure k et dureté H (tribologie/datasheet).")
        if self.coefficient_usure_palier_k is None or self.durete_contact_palier_pa is None:
            _push_inconnue(rapport, "impossibles", "usure palier (valeur absolue)", "Impossible sans coefficient d'usure k et dureté H (tribologie/datasheet).")

        # ============================================================
        # 10) Dimensionnement paroi cylindre (mince + Lamé)
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
        # 11) Précharge vis couvercle
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
        # 12) Inconnues réellement impossibles sans données externes
        # ============================================================
        _push_inconnue(
            rapport,
            "impossibles",
            "rendement global réel",
            "Sans p(θ) (diagramme indicateur), pertes de pompage, transferts thermiques, accessoires, on ne peut pas calculer un rendement global fiable.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "fatigue/longévité complète",
            "Sans matériaux précis, états de surface, concentrations de contraintes, et cycles de charge, on ne peut pas conclure sur la fatigue/longévité.",
        )

        _dedup_inconnues(rapport)
        return rapport
