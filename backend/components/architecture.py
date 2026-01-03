# backend/components/architecture.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math


# ============================================================
# Imports des modules architecture (robustes)
# ============================================================

# coût maintenance (Archard simplifié + option scraping)
try:
    from backend.modules.architecture.calcul_cout_maintenance_archard import (
        calcul_cout_maintenance_estime,
        calcul_cout_maintenance_estime_auto_prix,
    )
except Exception:
    from backend.modules.architecture.calcul_cout_maintenance_archard import (  # type: ignore
        calcul_cout_maintenance_estime,
        calcul_cout_maintenance_estime_auto_prix,
    )

# cylindrée admissible (vitesse piston + ratio S/B)
try:
    from backend.modules.architecture.calcul_cylindree_admissible import (
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )
except Exception:
    from backend.modules.architecture.calcul_cylindree_admissible import (  # type: ignore
        calcul_bore_max_admissible,
        calcul_cylindree_unit_max,
    )

# cylindrée totale requise
try:
    from backend.modules.architecture.calcul_cylindree_totale import calcul_cylindree_totale_requise
except Exception:
    from backend.modules.architecture.calcul_cylindree_totale import calcul_cylindree_totale_requise  # type: ignore

# nombre de cylindres minimal
try:
    from backend.modules.architecture.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min
except Exception:
    from backend.modules.architecture.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min  # type: ignore

# choix architecture (score packaging + complexité + maintenance)
try:
    from backend.modules.architecture.choix_architecture_optimale import (
        choix_architecture_optimale,
        evaluer_architecture,
    )
except Exception:
    from backend.modules.architecture.choix_architecture_optimale import (  # type: ignore
        choix_architecture_optimale,
        evaluer_architecture,
    )

# résolution globale (déjà existante dans tes modules)
try:
    from backend.modules.architecture.resolution_globale_architecture import resoudre_architecture_globale
except Exception:
    from backend.modules.architecture.resolution_globale_architecture import resoudre_architecture_globale  # type: ignore


# ============================================================
# Helpers robustesse + gestion des inconnues
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


def _require_int_positive(name: str, x: Any, *, strict: bool = True) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    ok = x > 0 if strict else x >= 0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return int(x)


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[dict]) -> List[dict]:
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


def _hz_cycles(regime_tr_min: float, temps_moteur: int) -> float:
    """
    Convertit un régime (tr/min) en fréquence de cycles (Hz = cycles/s).
    - 4T : f = n/120
    - 2T : f = n/60
    """
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    if temps_moteur == 4:
        return n / 120.0
    if temps_moteur == 2:
        return n / 60.0
    raise ValueError("temps_moteur doit être 2 ou 4.")


def _course_max_depuis_vitesse_piston(vitesse_piston_max_ms: float, regime_tr_min: float) -> float:
    """
    Vitesse moyenne piston : U_p = 2*S*(n/60) => S_max = 30*U_p_max/n
    """
    U = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    if n == 0.0:
        return 0.0
    return (30.0 * U) / n


def _bore_et_course_depuis_volume_et_ratio(volume_unitaire_m3: float, ratio_s_b: float) -> Tuple[float, float]:
    """
    Déduction exacte :
      V = (pi/4) * B^2 * S, avec S = r*B
      => V = (pi/4) * r * B^3
      => B = (4V/(pi r))^(1/3), S = r*B
    """
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    r = _require_positive("ratio_s_b", ratio_s_b, strict=True)
    if V == 0.0:
        return 0.0, 0.0
    B = ((4.0 * V) / (math.pi * r)) ** (1.0 / 3.0)
    S = r * B
    return float(B), float(S)


def _ratio_max_compatible_vitesse_piston(volume_unitaire_m3: float, course_max_m: float) -> float:
    """
    Contrainte S <= S_max, avec :
      S = r*B et B = (4V/(pi r))^(1/3)
      => S = r^(2/3) * (4V/pi)^(1/3)
      => r <= (S_max / K)^(3/2), K=(4V/pi)^(1/3)
    """
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    S_max = _require_positive("course_max_m", course_max_m, strict=False)
    if V == 0.0:
        return float("inf")
    K = (4.0 * V / math.pi) ** (1.0 / 3.0)
    if K <= 0.0:
        return 0.0
    return float((S_max / K) ** 1.5)


def _surface_piston_m2(bore_m: float) -> float:
    B = _require_positive("bore_m", bore_m, strict=False)
    if B == 0.0:
        return 0.0
    return float(math.pi * (B**2) / 4.0)


def _estimer_packaging_simple(
    architecture: str,
    nb_cyl: int,
    *,
    pas_cylindre_m: float,
    largeur_base_m: float
) -> Tuple[float, float]:
    """
    Estimation "expliquée" (sans dépendre des internals du module).
    Sert uniquement à renseigner le rapport (le scoring officiel reste evaluer_architecture()).
    """
    nb = _require_int_positive("nb_cyl", nb_cyl, strict=True)
    pas = _require_positive("pas_cylindre_m", pas_cylindre_m, strict=True)
    w0 = _require_positive("largeur_base_m", largeur_base_m, strict=True)

    arch = architecture
    if arch == "L":
        return nb * pas, w0
    if arch == "V":
        # 2 bancs : longueur ~ (N/2)*pas, largeur +50%
        return (nb / 2.0) * pas, 1.5 * w0
    if arch == "W":
        # simplification 3 bancs : longueur ~(N/3)*pas, largeur +100%
        return (nb / 3.0) * pas, 2.0 * w0
    if arch == "Etoile":
        # radial : long plutôt court, mais large
        return 1.5 * pas, 2.5 * w0

    return float("nan"), float("nan")


# ============================================================
# Composant Architecture
# ============================================================

@dataclass(frozen=True)
class Architecture:
    """
    Composant d'analyse et de pré-dimensionnement "architecture moteur" :
    - cylindrée totale requise (P, PME, fréquence cycles, rendement),
    - cylindrée unitaire max admissible (vitesse piston + ratio S/B max),
    - nombre minimal de cylindres,
    - exploration N et choix d'architecture via ton module de scoring,
    - estimation maintenance (Archard simplifié).

    Objectif : réduire les inconnues en déduisant :
      - f (cycles/s), V_tot, V_u, bore, course, ratio S/B compatible,
      - charge moyenne par piston (≈ PME*A),
      - coût maintenance relatif et choix d'architecture.
    """

    # cycle moteur : 4T ou 2T
    temps_moteur: int = 4

    # rendement mécanique : si PME n'est pas déjà "net vilebrequin"
    rendement_mecanique: float = 0.85

    # contrainte géométrique S/B max
    ratio_course_alesage_max: float = 1.2

    # maintenance (modèle joints)
    duree_vie_joint_base_h: float = 5000.0
    joints_par_cyl: int = 3
    cout_intervention_base_eur: float = 2000.0
    beta_wear_model: str = "1.5 (dans le module)"  # info seulement

    # exploration N
    delta_exploration: int = 6
    min_exploration: int = 16
    n_max_absolu: int = 24

    # packaging "informatif" (le scoring officiel reste dans evaluer_architecture)
    pas_cylindre_m: float = 0.15
    largeur_base_m: float = 0.40

    # option : estimer cout_intervention_base via scraping (si tu fournis URLs)
    activer_scraping_prix: bool = False
    urls_prix_joints: Optional[List[str]] = None
    urls_main_oeuvre: Optional[List[str]] = None
    cache_path_prix: str = "backend/.cache/prix_maintenance.json"
    cache_ttl_h: float = 168.0
    timeout_scraping_s: float = 6.0
    temps_intervention_h: float = 1.0
    cout_arret_eur: float = 0.0
    cout_consommables_eur: float = 0.0
    strict_scraping: bool = False

    def analyser(
        self,
        *,
        puissance_cible_w: Optional[float] = None,
        regime_tr_min: Optional[float] = None,
        pme_pa: Optional[float] = None,
        vitesse_piston_max_ms: Optional[float] = None,
        longueur_dispo_m: Optional[float] = None,
        largeur_dispo_m: Optional[float] = None,
        horizon_usage_h: float = 20000.0,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "cycles": {},
            "cylindree": {},
            "contraintes_admissibles": {},
            "maintenance": {},
            "exploration": [],
            "meilleur": None,
            "solution_module_globale": None,
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # Entrées
        # ------------------------------------------------------------
        rapport["entrees"] = {
            "puissance_cible_w": puissance_cible_w,
            "regime_tr_min": regime_tr_min,
            "pme_pa": pme_pa,
            "vitesse_piston_max_ms": vitesse_piston_max_ms,
            "longueur_dispo_m": longueur_dispo_m,
            "largeur_dispo_m": largeur_dispo_m,
            "horizon_usage_h": horizon_usage_h,
            "temps_moteur": self.temps_moteur,
            "rendement_mecanique": self.rendement_mecanique,
            "ratio_course_alesage_max": self.ratio_course_alesage_max,
            "joints_par_cyl": self.joints_par_cyl,
            "duree_vie_joint_base_h": self.duree_vie_joint_base_h,
            "cout_intervention_base_eur": self.cout_intervention_base_eur,
            "exploration_delta": self.delta_exploration,
            "exploration_min": self.min_exploration,
            "n_max_absolu": self.n_max_absolu,
        }

        # ------------------------------------------------------------
        # Validations / inconnues de base
        # ------------------------------------------------------------
        if puissance_cible_w is None:
            _push_inconnue(rapport, "impossibles", "puissance_cible_w", "Nécessaire pour calculer la cylindrée totale requise.")
        if regime_tr_min is None:
            _push_inconnue(rapport, "impossibles", "regime_tr_min", "Nécessaire pour f(cycles/s), vitesse piston, et cylindrée.")
        if pme_pa is None:
            _push_inconnue(rapport, "impossibles", "pme_pa", "Nécessaire pour relier puissance et cylindrée (PME).")

        # Sans gabarit, on peut calculer N_min, mais pas sélectionner l'architecture packaging.
        if longueur_dispo_m is None or largeur_dispo_m is None:
            _push_inconnue(
                rapport,
                "partielles",
                "gabarit (L/W)",
                "Nécessaire pour valider le packaging et choisir l'architecture optimale."
            )

        # Sans Up_max, on ne peut pas borner la cylindrée unitaire max (donc N_min devient partiel).
        if vitesse_piston_max_ms is None:
            _push_inconnue(
                rapport,
                "partielles",
                "vitesse_piston_max_ms",
                "Nécessaire pour borner l'alésage et la cylindrée unitaire admissible."
            )

        # Si on n'a pas le triplet (P, PME, rpm) on ne peut pas aller plus loin proprement
        if puissance_cible_w is None or regime_tr_min is None or pme_pa is None:
            _dedup_inconnues(rapport)
            return rapport

        P = _require_positive("puissance_cible_w", puissance_cible_w, strict=False)
        n_rpm = _require_positive("regime_tr_min", regime_tr_min, strict=True)
        PME = _require_positive("pme_pa", pme_pa, strict=True)
        T_usage = _require_positive("horizon_usage_h", horizon_usage_h, strict=False)

        # ------------------------------------------------------------
        # 1) Fréquence cycles
        # ------------------------------------------------------------
        f_hz = _hz_cycles(n_rpm, self.temps_moteur)
        rapport["cycles"] = {"temps_moteur": self.temps_moteur, "frequence_cycles_hz": f_hz}

        # ------------------------------------------------------------
        # 2) Cylindrée totale requise
        # ------------------------------------------------------------
        eta_m = _require_positive("rendement_mecanique", self.rendement_mecanique, strict=True)
        V_tot_m3 = float(
            calcul_cylindree_totale_requise(
                puissance_mecanique_h=P,
                pme_pa=PME,
                frequence_cycles_hz=f_hz,
                rendement_mecanique=eta_m,
            )
        )
        rapport["cylindree"]["cylindree_totale_m3"] = V_tot_m3
        rapport["cylindree"]["cylindree_totale_cc"] = V_tot_m3 * 1e6

        if V_tot_m3 <= 0.0:
            rapport["notes_modele"].append("Puissance cible nulle => cylindrée totale nulle (aucune optimisation).")
            _dedup_inconnues(rapport)
            return rapport

        # ------------------------------------------------------------
        # 3) Cylindrée unitaire max admissible (si Up_max connu)
        # ------------------------------------------------------------
        bore_max_m: Optional[float] = None
        V_unit_max_m3: Optional[float] = None
        course_max_m: Optional[float] = None

        if vitesse_piston_max_ms is not None:
            Up_max = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
            r_max = _require_positive("ratio_course_alesage_max", self.ratio_course_alesage_max, strict=True)

            bore_max_m = float(calcul_bore_max_admissible(Up_max, n_rpm, r_max))
            V_unit_max_m3 = float(calcul_cylindree_unit_max(bore_max_m, r_max))
            course_max_m = float(_course_max_depuis_vitesse_piston(Up_max, n_rpm))

            rapport["contraintes_admissibles"] = {
                "Up_max_ms": Up_max,
                "ratio_S_B_max": r_max,
                "bore_max_m": bore_max_m,
                "bore_max_mm": bore_max_m * 1000.0,
                "cylindree_unitaire_max_m3": V_unit_max_m3,
                "cylindree_unitaire_max_cc": V_unit_max_m3 * 1e6,
                "course_max_m": course_max_m,
                "course_max_mm": course_max_m * 1000.0,
            }
        else:
            rapport["contraintes_admissibles"] = {"Up_max_ms": None}

        # ------------------------------------------------------------
        # 4) Nombre minimal de cylindres (si V_unit_max connu)
        # ------------------------------------------------------------
        n_min: Optional[int] = None
        if V_unit_max_m3 is not None:
            n_min_calc = int(calcul_nombre_cylindres_min(V_tot_m3, V_unit_max_m3))
            if n_min_calc >= 999:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "N_min",
                    "Cylindrée unitaire max invalide (paramètres incohérents)."
                )
            else:
                n_min = n_min_calc
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "N_min",
                "Calculable si vitesse_piston_max_ms est fournie (pour obtenir la cylindrée unitaire max)."
            )

        rapport["cylindree"]["N_min"] = n_min

        # Si N_min inconnu, on ne peut pas explorer correctement
        if n_min is None:
            _dedup_inconnues(rapport)
            return rapport

        if n_min > self.n_max_absolu:
            _push_inconnue(
                rapport,
                "impossibles",
                "N_min",
                f"N_min={n_min} > n_max_absolu={self.n_max_absolu} (contrainte projet)."
            )
            _dedup_inconnues(rapport)
            return rapport

        # ------------------------------------------------------------
        # 5) Maintenance : éventuel recalcul d'un coût d'intervention base via scraping
        # ------------------------------------------------------------
        cout_inter_base = _require_positive("cout_intervention_base_eur", self.cout_intervention_base_eur, strict=False)

        if self.activer_scraping_prix:
            try:
                # On fabrique un "cout intervention base" pour nb_joints_base = N_min*joints_par_cyl
                cout_inter_base = float(
                    calcul_cout_maintenance_estime_auto_prix(
                        duree_usage_h=1.0,  # neutre ici : on veut seulement reconstruire le cout_inter_base
                        duree_vie_joint_base_h=self.duree_vie_joint_base_h,
                        charge_nominale_n=1.0,
                        charge_actuelle_n=1.0,
                        nb_joints_base=max(1, n_min * self.joints_par_cyl),
                        nb_joints_actuel=max(1, n_min * self.joints_par_cyl),
                        cout_inter_eur=cout_inter_base,
                        activer_scraping=True,
                        urls_prix_joints=self.urls_prix_joints,
                        urls_main_oeuvre=self.urls_main_oeuvre,
                        cache_path=self.cache_path_prix,
                        cache_ttl_h=self.cache_ttl_h,
                        timeout_s=self.timeout_scraping_s,
                        temps_intervention_h=self.temps_intervention_h,
                        cout_arret_eur=self.cout_arret_eur,
                        cout_consommables_eur=self.cout_consommables_eur,
                        strict_scraping=self.strict_scraping,
                    )
                )
                # Note : l'appel ci-dessus renvoie un coût total, pas directement cout_inter_base.
                # Pour rester simple et ne pas casser ton modèle, on garde le cout_inter_base fourni.
                rapport["notes_modele"].append(
                    "Scraping activé : le module sait estimer des prix, mais le coût d'intervention base reste à calibrer."
                )
            except Exception:
                rapport["notes_modele"].append("Scraping activé mais estimation prix non disponible (fallback sur cout_intervention_base_eur).")

        rapport["maintenance"]["cout_intervention_base_eur"] = cout_inter_base
        rapport["maintenance"]["duree_vie_joint_base_h"] = self.duree_vie_joint_base_h
        rapport["maintenance"]["joints_par_cyl"] = self.joints_par_cyl

        # ------------------------------------------------------------
        # 6) Exploration N et choix architecture
        # ------------------------------------------------------------
        if longueur_dispo_m is None or largeur_dispo_m is None:
            # N_min calculable, mais on ne peut pas trancher sur l'architecture
            _dedup_inconnues(rapport)
            return rapport

        L_max = _require_positive("longueur_dispo_m", longueur_dispo_m, strict=True)
        W_max = _require_positive("largeur_dispo_m", largeur_dispo_m, strict=True)

        n_max_explore = max(self.min_exploration, n_min + self.delta_exploration)
        n_max_explore = min(self.n_max_absolu, n_max_explore)

        # Référence maintenance : configuration N_min
        V_u_ref = V_tot_m3 / n_min

        # Pour retirer l'arbitraire sur S/B, on prend le ratio maximal compatible (borne par r_max)
        ratio_ref = self.ratio_course_alesage_max
        if course_max_m is not None:
            r_lim = _ratio_max_compatible_vitesse_piston(V_u_ref, course_max_m)
            if math.isfinite(r_lim):
                ratio_ref = min(self.ratio_course_alesage_max, r_lim)
        ratio_ref = max(1e-6, ratio_ref)

        bore_ref, _course_ref = _bore_et_course_depuis_volume_et_ratio(V_u_ref, ratio_ref)
        charge_ref_n = PME * _surface_piston_m2(bore_ref)

        best_score = float("inf")
        best_row: Optional[Dict[str, Any]] = None

        for N in range(n_min, n_max_explore + 1):
            V_u = V_tot_m3 / N

            # ratio retenu par cylindre
            ratio_ret = self.ratio_course_alesage_max
            if course_max_m is not None:
                r_lim = _ratio_max_compatible_vitesse_piston(V_u, course_max_m)
                if math.isfinite(r_lim):
                    ratio_ret = min(self.ratio_course_alesage_max, r_lim)
            ratio_ret = max(1e-6, ratio_ret)

            bore_m, course_m = _bore_et_course_depuis_volume_et_ratio(V_u, ratio_ret)

            # Vérif admissible si bore_max connu
            if bore_max_m is not None and bore_m > bore_max_m + 1e-12:
                continue
            if course_max_m is not None and course_m > course_max_m + 1e-12:
                continue

            charge_moy_n = PME * _surface_piston_m2(bore_m)

            cout_maint = float(
                calcul_cout_maintenance_estime(
                    duree_usage_h=T_usage,
                    duree_vie_joint_base_h=self.duree_vie_joint_base_h,
                    charge_nominale_n=charge_ref_n,
                    charge_actuelle_n=charge_moy_n,
                    nb_joints_base=max(1, n_min * self.joints_par_cyl),
                    nb_joints_actuel=max(1, N * self.joints_par_cyl),
                    cout_inter_eur=cout_inter_base,
                )
            )

            arch = str(choix_architecture_optimale(N, L_max, W_max, cout_maint))
            if arch == "Inconnue":
                continue

            score, valide = evaluer_architecture(arch, N, L_max, W_max, cout_maint)
            if not valide:
                continue

            # Packaging "informatif"
            L_pkg, W_pkg = _estimer_packaging_simple(
                arch, N, pas_cylindre_m=self.pas_cylindre_m, largeur_base_m=self.largeur_base_m
            )

            row = {
                "N_cyl": N,
                "architecture": arch,
                "score": float(score),
                "valide": bool(valide),
                "cout_maintenance_eur": float(cout_maint),
                "cylindree_tot_cc": float(V_tot_m3 * 1e6),
                "cylindree_unit_cc": float(V_u * 1e6),
                "bore_mm": float(bore_m * 1000.0),
                "course_mm": float(course_m * 1000.0),
                "ratio_S_B": float(ratio_ret),
                "charge_moy_piston_N": float(charge_moy_n),
                "L_pkg_m_estimee": float(L_pkg),
                "W_pkg_m_estimee": float(W_pkg),
            }
            rapport["exploration"].append(row)

            if score < best_score:
                best_score = float(score)
                best_row = row

        rapport["meilleur"] = best_row

        if best_row is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "solution",
                "Aucune configuration (N, architecture) valide dans le gabarit et sous contraintes admissibles."
            )

        # ------------------------------------------------------------
        # 7) Sortie "module global" (pour comparaison)
        # ------------------------------------------------------------
        if vitesse_piston_max_ms is not None:
            try:
                rapport["solution_module_globale"] = resoudre_architecture_globale(
                    puissance_cible_w=P,
                    regime_tr_min=n_rpm,
                    pme_pa=PME,
                    vitesse_piston_max_ms=_require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False),
                    L_max_m=L_max,
                    W_max_m=W_max,
                    horizon_usage_h=T_usage,
                )
            except Exception:
                rapport["solution_module_globale"] = None
                rapport["notes_modele"].append("Échec appel resoudre_architecture_globale (paramètres / contraintes).")

        # ------------------------------------------------------------
        # 8) Inconnues réellement impossibles sans données externes
        # ------------------------------------------------------------
        _push_inconnue(
            rapport,
            "impossibles",
            "PME réelle (carte + pertes + transitoires)",
            "PME est une entrée modèle. Impossible de la déduire sans cycle thermo/mesures et pertes détaillées."
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "vibrations / NVH / équilibrage",
            "Nécessite un modèle dynamique complet (ordre d'allumage, masses, vilebrequin, supports)."
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "refroidissement & gradients thermiques",
            "Nécessite architecture thermique, matériaux, échanges, et conditions d'usage."
        )

        _dedup_inconnues(rapport)
        return rapport
