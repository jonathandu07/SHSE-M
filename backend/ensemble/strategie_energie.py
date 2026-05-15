# backend/ensemble/strategie_energie.py
# -*- coding: utf-8 -*-
"""
strategie_energie.py
=========================================================
Cerveau énergétique SHSE-M — Version 6 (Zéro Invention)
=========================================================
Strict respect du principe de non-invention de données.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal, Tuple, Union
import math

try:
    from backend.ensemble import calcul_stho_me as phys
except ImportError:
    import calcul_stho_me as phys  # type: ignore

# --- TYPES ---

ModeEnergetique = Literal[
    "ev_only", "soutien_traction", "recharge_batterie", 
    "maintien_soc", "mode_degrade", "urgence_puissance"
]

# --- DATACLASSES ---

@dataclass(frozen=True)
class EnveloppeBatterie:
    """Limites de puissance calculables à l'instant T."""
    p_charge_max_soh_w: Optional[float] = None
    p_charge_max_temp_w: Optional[float] = None
    p_charge_max_crate_w: Optional[float] = None
    p_charge_max_bus_w: Optional[float] = None
    p_charge_recommandee_w: Optional[float] = None
    limites_actives: List[str] = field(default_factory=list)
    raison_limitante: Optional[str] = None

@dataclass(frozen=True)
class PointGrille:
    """Point riche de la cartographie énergétique."""
    rpm: float
    couple_nm: float
    statut_meca: Literal["ok", "partiel", "impossible"]
    statut_elec: Literal["ok", "partiel", "impossible"]
    p_meca_w: float
    p_elec_w: Optional[float] = None
    pertes_totales_w: Optional[float] = None
    rendement: Optional[float] = None
    rapport_alternateur: Dict[str, Any] = field(default_factory=dict)
    # Score: (Sec, Meca, Elec, SoH_Inc, SoH_Val, Pertes_Inc, Pertes_Val, Rend_Inc, Rend_Val)
    score_lexico: Tuple[int, int, int, int, float, int, float, int, float] = field(default_factory=lambda: (2, 2, 2, 1, 1.0, 1, 1e12, 1, 1.0))
    inconnues: List[Dict[str, str]] = field(default_factory=list)

# --- FONCTIONS INTERNES ---

def determiner_enveloppe_batterie(
    batterie_obj: Any,
    etat_actuel: Dict[str, Any]
) -> Tuple[EnveloppeBatterie, List[Dict[str, str]]]:
    """Calcule les limites sans inventer de données manquantes."""
    inconnues, limites_actives = [], []
    
    temp_c = etat_actuel.get("batterie_temp_c")
    v_bus = etat_actuel.get("v_bus_dc_v")
    cap_ah = getattr(batterie_obj, "capacite_ah", None)
    c_rate_max = getattr(batterie_obj, "c_rate_charge_max", None)
    soh = etat_actuel.get("batterie_soh")
    
    temp_limite = getattr(batterie_obj, "temp_cellule_critique_c", None)
    temp_derating_seuil = getattr(batterie_obj, "temp_derating_seuil_c", None)
    i_max_bus = getattr(batterie_obj, "courant_max_bus_a", None)
    soh_min_prot = getattr(batterie_obj, "soh_seuil_protection", None)
    loi_soh = getattr(batterie_obj, "loi_reduction_puissance_soh", None)

    # 1. Limite C-rate
    p_crate = None
    if all(x is not None for x in (c_rate_max, cap_ah, v_bus)):
        try:
            p_crate = c_rate_max * cap_ah * v_bus
        except Exception as e: inconnues.append({"nom": "p_charge_max_crate_w", "raison": str(e)})
    else: inconnues.append({"nom": "p_charge_max_crate_w", "raison": "Données manquantes (C-rate, Capacité ou V_bus)"})

    # 2. Limite Température
    p_temp = None
    if all(x is not None for x in (temp_c, temp_limite)):
        if temp_c >= temp_limite:
            p_temp = 0.0; limites_actives.append("temp_critique")
        elif temp_derating_seuil is not None and temp_c > temp_derating_seuil:
            plage = temp_limite - temp_derating_seuil
            facteur = (temp_limite - temp_c) / plage if plage > 0 else 0.0
            if p_crate is not None:
                p_temp = p_crate * facteur; limites_actives.append("derating_thermique")
            else: inconnues.append({"nom": "p_charge_max_temp_w", "raison": "P_crate inconnu pour appliquer le derating"})
        elif temp_derating_seuil is None:
            inconnues.append({"nom": "p_charge_max_temp_w", "raison": "Seuil de derating thermique inconnu"})
        else: p_temp = p_crate
    else: inconnues.append({"nom": "p_charge_max_temp_w", "raison": "Température actuelle ou limite critique inconnue"})

    # 3. Limite SoH
    p_soh = None
    if all(x is not None for x in (soh, p_crate, soh_min_prot)):
        if callable(loi_soh): p_soh = loi_soh(p_crate, soh)
        else: inconnues.append({"nom": "p_charge_max_soh_w", "raison": "Loi de réduction SoH non fournie"}); p_soh = None
        if soh < soh_min_prot: limites_actives.append("protection_soh")
    else: inconnues.append({"nom": "p_charge_max_soh_w", "raison": "SoH, p_crate ou seuil protection inconnu"})

    # 4. Limite Bus
    p_bus = (v_bus * i_max_bus) if (v_bus is not None and i_max_bus is not None) else None
    if p_bus is None: inconnues.append({"nom": "p_charge_max_bus_w", "raison": "V_bus ou Courant max bus inconnu"})

    valeurs = [v for v in [p_crate, p_temp, p_soh, p_bus] if v is not None]
    p_reco = min(valeurs) if (valeurs and len(valeurs) >= 4) else None # On ne recommande que si toutes les limites sont connues
    if p_reco is None: inconnues.append({"nom": "p_charge_recommandee_w", "raison": "Toutes les limites de l'enveloppe ne sont pas calculables"})
    
    raison = None
    if p_reco is not None:
        mappe = {"crate": p_crate, "temp": p_temp, "soh": p_soh, "bus": p_bus}
        raison = min(mappe, key=lambda k: mappe[k] if mappe[k] is not None else float('inf'))

    return EnveloppeBatterie(
        p_charge_max_soh_w=p_soh, p_charge_max_temp_w=p_temp, p_charge_max_crate_w=p_crate, p_charge_max_bus_w=p_bus,
        p_charge_recommandee_w=p_reco, limites_actives=limites_actives, raison_limitante=raison
    ), inconnues

def generer_carto_energetique(
    alternateur_obj: Any, bornes: Dict[str, float], v_bus: float, soh_batterie: Optional[float]
) -> Dict[str, Any]:
    grille = {"points": [], "inconnues_globales": []}
    keys = ["rpm_min", "rpm_max", "rpm_step", "couple_min", "couple_max", "couple_step"]
    if any(bornes.get(k) is None for k in keys):
        grille["inconnues_globales"].append("Bornes de recherche incompletes"); return grille
    if bornes["rpm_step"] <= 0 or bornes["couple_step"] <= 0 or bornes["rpm_min"] > bornes["rpm_max"] or bornes["couple_min"] > bornes["couple_max"]:
        grille["inconnues_globales"].append("Coherence des bornes de recherche invalide"); return grille

    fn = getattr(alternateur_obj, "analyser_point_de_fonctionnement", None)
    if not callable(fn): grille["inconnues_globales"].append("L'objet alternateur n'expose pas analyser_point_de_fonctionnement"); return grille

    for rpm in range(int(bornes["rpm_min"]), int(bornes["rpm_max"]) + 1, int(bornes["rpm_step"])):
        for c in range(int(bornes["couple_min"]), int(bornes["couple_max"]) + 1, int(bornes["couple_step"])):
            try:
                rep = fn(vitesse_rotation_rpm=float(rpm), tension_v=float(v_bus), couple_nm=float(c))
                s_elec = 2 if rep.get("inconnues", {}).get("impossibles") else (1 if rep.get("inconnues", {}).get("partielles") else 0)
            except TypeError:
                rep = {"inconnues": {"impossibles": [{"nom": "couple", "raison": "API Alternateur ne prend pas le couple"}]}}
                s_elec = 2
            
            p_elec, rendement, pertes = rep.get("sortie_electrique", {}).get("puissance_utile_w"), rep.get("rendement", {}).get("eta_sur_pertes_connues"), rep.get("pertes", {}).get("pertes_connues_total_w")
            score = (0, 0, s_elec, 1 if soh_batterie is None else 0, (1.0-(soh_batterie or 0.0)), 1 if pertes is None else 0, pertes or 1e12, 1 if rendement is None else 0, (1.0-(rendement or 0.0)))
            grille["points"].append(PointGrille(rpm=rpm, couple_nm=c, p_meca_w=(c*2*math.pi*rpm)/60, p_elec_w=p_elec, pertes_totales_w=pertes, rendement=rendement, statut_meca="ok", statut_elec=("ok" if s_elec==0 else ("partiel" if s_elec==1 else "impossible")), score_lexico=score, rapport_alternateur=rep, inconnues=rep.get("inconnues", {}).get("impossibles", [])+rep.get("inconnues", {}).get("partielles", [])))
    return grille

# --- FONCTION PRINCIPALE ---

def calculer_strategie_couplage(
    etat_systeme: Dict[str, Any], composants: Dict[str, Any]
) -> Dict[str, Any]:
    rapport = {"decision": None, "mode_energetique": "ev_only", "enveloppe_batterie": None, "bilan_bus_dc": {}, "derivees_chaine_energie": {}, "candidats": [], "point_retenu": None, "validation_transitoire": {"statut": "non_calcule"}, "inconnues": {"impossibles": [], "partielles": []}, "alertes": {}, "notes_modele": []}
    bat, alt, mt, bt, me = composants.get("batterie"), composants.get("alternateur"), composants.get("moteur_thermique"), composants.get("boite_crabots"), composants.get("moteur_electrique")
    v_bus, soc, p_roue = etat_systeme.get("v_bus_dc_v"), etat_systeme.get("batterie_soc"), etat_systeme.get("puissance_traction_roue_w")
    
    if any(x is None for x in (bat, v_bus, soc, p_roue)):
        rapport["inconnues"]["impossibles"].append({"nom": "strategie_globale", "raison": f"Manque {'Bat' if not bat else ''} {'Vbus' if v_bus is None else ''} {'SoC' if soc is None else ''} {'Proue' if p_roue is None else ''}"}); return rapport

    env, inc_env = determiner_enveloppe_batterie(bat, etat_systeme)
    rapport["enveloppe_batterie"], rapport["inconnues"]["partielles"] = env, inc_env
    
    eta_me = getattr(me, "rendement_moteur_electrique", None)
    if eta_me is not None and eta_me > 0: p_traction_bus = p_roue / eta_me; rapport["derivees_chaine_energie"]["p_traction_bus_dc_w"] = p_traction_bus
    else: rapport["inconnues"]["partielles"].append({"nom": "rendement_moteur_electrique", "raison": "Conversion Roue->Bus impossible"}); p_traction_bus = None

    temp_c, temp_crit = etat_systeme.get("batterie_temp_c"), getattr(bat, "temp_cellule_critique_c", None)
    soc_min, soc_max = getattr(bat, "soc_seuil_soutien_traction", None), getattr(bat, "soc_seuil_fin_recharge", None)
    if temp_c is not None and temp_crit is not None and temp_c >= temp_crit:
        rapport["mode_energetique"], p_charge_cible = "mode_degrade", 0.0; rapport["alertes"]["thermique"] = "Temp critique"
    elif all(x is not None for x in (soc_min, soc_max)):
        rapport["mode_energetique"] = "soutien_traction" if (p_roue > 0 and soc < soc_min) else ("recharge_batterie" if soc < soc_max else "ev_only")
        p_charge_cible = env.p_charge_recommandee_w if env.p_charge_recommandee_w is not None else None
    else: rapport["inconnues"]["partielles"].append({"nom": "seuils_soc", "raison": "Seuils SoC soutien/recharge inconnus"}); p_charge_cible = None

    p_gen_req = (p_traction_bus + p_charge_cible) if (p_traction_bus is not None and p_charge_cible is not None) else None
    rapport["bilan_bus_dc"] = {"p_gen_requise_w": p_gen_req, "p_charge_cible_w": p_charge_cible}
    if p_gen_req is None: rapport["inconnues"]["impossibles"].append({"nom": "puissance_generation", "raison": "Manque P_traction_bus ou P_charge_cible"})

    tol = etat_systeme.get("tol_puissance_relative")
    if p_gen_req is not None and p_gen_req > 0 and alt and tol is not None:
        bornes = etat_systeme.get("bornes_recherche")
        carto = generer_carto_energetique(alt, bornes or {}, v_bus, etat_systeme.get("batterie_soh"))
        if not bornes: rapport["inconnues"]["impossibles"].append({"nom": "cartographie", "raison": "Bornes absentes"})
        candidats = []
        for pt in carto["points"]:
            if pt.p_elec_w is not None and abs(pt.p_elec_w - p_gen_req) / p_gen_req <= tol:
                raps = getattr(bt, "rapports", None)
                if not raps: rapport["inconnues"]["partielles"].append({"nom": "boite", "raison": "Rapports boite inconnus"}); break
                for nom, ratio in raps.items():
                    r_min, r_max = getattr(mt, "rpm_min", None), getattr(mt, "rpm_max", None)
                    if r_min is not None and r_max is not None and r_min <= pt.rpm / ratio <= r_max:
                        candidats.append({"alternateur": pt, "rapport": nom, "thermique": {"rpm": pt.rpm / ratio, "couple_nm": pt.couple_nm * ratio}, "score_lexico": pt.score_lexico})
                    else: rapport["inconnues"]["partielles"].append({"nom": "mt_bornes", "raison": f"Bornes MT inconnues ou RPM {pt.rpm/ratio:.0f} hors limites"})
        rapport["candidats"] = candidats
        if candidats:
            candidats.sort(key=lambda x: x["score_lexico"]); rapport["point_retenu"] = candidats[0]
            rapport["decision"] = {"mode": rapport["mode_energetique"], "p_charge_w": p_charge_cible, "rapport_boite": candidats[0]["rapport"], "point_thermique": candidats[0]["thermique"]}
        else: rapport["inconnues"]["impossibles"].append({"nom": "point_fonctionnement", "raison": f"Aucun point atteignable pour P_gen={p_gen_req:.0f}W"})
    elif p_gen_req is not None and p_gen_req > 0 and tol is None:
        rapport["inconnues"]["impossibles"].append({"nom": "filtrage", "raison": "tol_puissance_relative inconnue"})

    pt_act, dt, depl = etat_systeme.get("point_actuel_thermique"), etat_systeme.get("temps_disponible_s"), composants.get("deplaceur")
    r_th, c_th = getattr(depl, "resistance_thermique_k_w", None), getattr(depl, "capacite_thermique_j_k", None)
    if rapport["point_retenu"] and mt:
        manquants = [k for k, v in {"Pt_act": pt_act, "dt": dt, "Rth": r_th, "Cth": c_th}.items() if v is None]
        if not manquants:
            try:
                tau = phys.constante_temps_thermique(r_th, c_th)
                p_c = (rapport["point_retenu"]["thermique"]["rpm"] * rapport["point_retenu"]["thermique"]["couple_nm"] * 2 * math.pi) / 60
                p_acc = phys.reponse_transitoire_premier_ordre((pt_act["rpm"]*pt_act["couple_nm"]*2*math.pi)/60, p_c, dt, tau)
                rapport["validation_transitoire"] = {"statut": "valide" if abs(p_acc - p_c) < 0.1 * p_gen_req else "limite_inertie", "p_accessible_w": p_acc}
            except Exception as e: rapport["validation_transitoire"] = {"statut": "erreur", "raison": str(e)}
        else: rapport["validation_transitoire"] = {"statut": "impossible", "raison": f"Manque: {', '.join(manquants)}"}
    return rapport
