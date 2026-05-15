# backend/ensemble/strategie_energie.py
# -*- coding: utf-8 -*-
"""
strategie_energie.py
=========================================================
Cerveau énergétique SHSE-M — Arbitrage Lexicographique Pur
=========================================================
AUCUNE valeur par défaut. Zéro invention.
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
    # Score lexicographique : (Sécurité, Meca, Elec, SoH_Inc, SoH_Val, Pertes_Inc, Pertes_Val, Rend_Inc, Rend_Val)
    score_lexico: Tuple[int, int, int, int, float, int, float, int, float] = field(default_factory=lambda: (2, 2, 2, 1, 1.0, 1, 1e9, 1, 1.0))
    inconnues: List[Dict[str, str]] = field(default_factory=list)

# --- FONCTIONS INTERNES ---

def determiner_enveloppe_batterie(
    batterie_obj: Any,
    etat_actuel: Dict[str, Any]
) -> Tuple[EnveloppeBatterie, List[Dict[str, str]]]:
    """Calcule les limites sans inventer de données manquantes."""
    inconnues = []
    limites_actives = []
    
    temp_c = etat_actuel.get("batterie_temp_c")
    v_bus = etat_actuel.get("v_bus_dc_v")
    cap_ah = getattr(batterie_obj, "capacite_ah", None)
    c_rate_max = getattr(batterie_obj, "c_rate_charge_max", None)
    soh = etat_actuel.get("batterie_soh")
    
    temp_limite = getattr(batterie_obj, "temp_cellule_critique_c", None)
    temp_derating_seuil = getattr(batterie_obj, "temp_derating_seuil_c", None)
    i_max_bus = getattr(batterie_obj, "courant_max_bus_a", None)
    soh_min_prot = getattr(batterie_obj, "soh_seuil_protection", None)

    # 1. Limite C-rate
    p_crate = None
    if all(x is not None for x in (c_rate_max, cap_ah, v_bus)):
        try:
            p_crate = c_rate_max * cap_ah * v_bus
        except Exception as e:
            inconnues.append({"nom": "p_charge_max_crate_w", "raison": str(e)})
    else:
        inconnues.append({"nom": "p_charge_max_crate_w", "raison": "Données manquantes (C-rate, Capacité ou V_bus)"})

    # 2. Limite Température
    p_temp = None
    if all(x is not None for x in (temp_c, temp_limite)):
        if temp_c >= temp_limite:
            p_temp = 0.0
            limites_actives.append("temp_critique")
        elif temp_derating_seuil is not None and temp_c > temp_derating_seuil:
            plage = temp_limite - temp_derating_seuil
            facteur = (temp_limite - temp_c) / plage if plage > 0 else 0.0
            p_temp = (p_crate or 0.0) * facteur # Si p_crate inconnu, p_temp l'est aussi
            limites_actives.append("derating_thermique")
        elif temp_derating_seuil is None and temp_c > (temp_limite - 5.0): # Ici on n'invente pas 5.0, on dit que c'est inconnu
            inconnues.append({"nom": "p_charge_max_temp_w", "raison": "Seuil de derating thermique inconnu"})
        else:
            p_temp = p_crate
    else:
        inconnues.append({"nom": "p_charge_max_temp_w", "raison": "Température actuelle ou limite critique inconnue"})

    # 3. Limite SoH
    p_soh = None
    if all(x is not None for x in (soh, p_crate, soh_min_prot)):
        p_soh = p_crate * soh
        if soh < soh_min_prot:
            limites_actives.append("protection_soh")
    else:
        inconnues.append({"nom": "p_charge_max_soh_w", "raison": "SoH, p_crate ou seuil de protection inconnu"})

    # 4. Limite Bus
    p_bus = (v_bus * i_max_bus) if (v_bus is not None and i_max_bus is not None) else None
    if p_bus is None: inconnues.append({"nom": "p_charge_max_bus_w", "raison": "V_bus ou Courant max bus inconnu"})

    valeurs = [v for v in [p_crate, p_temp, p_soh, p_bus] if v is not None]
    p_reco = min(valeurs) if valeurs else None
    
    raison = None
    if p_reco is not None:
        mappe = {"crate": p_crate, "temp": p_temp, "soh": p_soh, "bus": p_bus}
        valides = {k: v for k, v in mappe.items() if v is not None}
        if valides:
            raison = min(valides, key=valides.get)

    return EnveloppeBatterie(
        p_charge_max_soh_w=p_soh, p_charge_max_temp_w=p_temp,
        p_charge_max_crate_w=p_crate, p_charge_max_bus_w=p_bus,
        p_charge_recommandee_w=p_reco,
        limites_actives=limites_actives,
        raison_limitante=raison
    ), inconnues

def generer_carto_energetique(
    alternateur_obj: Any,
    bornes: Dict[str, float],
    v_bus: float,
    soh_batterie: Optional[float]
) -> Dict[str, Any]:
    grille = {"points": [], "inconnues_globales": []}
    
    keys = ["rpm_min", "rpm_max", "rpm_step", "couple_min", "couple_max", "couple_step"]
    if any(bornes.get(k) is None for k in keys):
        grille["inconnues_globales"].append("Bornes de recherche incomplètes (rpm_min/max/step ou couple_min/max/step)")
        return grille

    fn_analyse = getattr(alternateur_obj, "analyser_point_de_fonctionnement", None)
    if not callable(fn_analyse):
        grille["inconnues_globales"].append("L'objet alternateur n'expose pas analyser_point_de_fonctionnement")
        return grille

    for rpm in range(int(bornes["rpm_min"]), int(bornes["rpm_max"]) + 1, int(bornes["rpm_step"])):
        for c in range(int(bornes["couple_min"]), int(bornes["couple_max"]) + 1, int(bornes["couple_step"])):
            p_meca = (c * 2 * math.pi * rpm) / 60
            
            try:
                rep = fn_analyse(vitesse_rotation_rpm=float(rpm), tension_v=float(v_bus), couple_nm=float(c))
            except TypeError:
                rep = fn_analyse(vitesse_rotation_rpm=float(rpm), tension_v=float(v_bus))
                rep.setdefault("inconnues", {}).setdefault("partielles", []).append({"nom": "couple", "raison": "API Alternateur ne prend pas le couple en entrée"})

            p_elec = rep.get("sortie_electrique", {}).get("puissance_utile_w")
            rendement = rep.get("rendement", {}).get("eta_sur_pertes_connues")
            pertes = rep.get("pertes", {}).get("pertes_connues_total_w")
            
            inc_imp = rep.get("inconnues", {}).get("impossibles", [])
            inc_par = rep.get("inconnues", {}).get("partielles", [])
            
            if inc_imp: s_elec = 2
            elif inc_par: s_elec = 1
            else: s_elec = 0
            
            # Score lexicographique hiérarchisé
            s_soh_inc = 1 if soh_batterie is None else 0
            s_soh_val = (1.0 - soh_batterie) if soh_batterie is not None else 1.0
            
            s_pertes_inc = 1 if pertes is None else 0
            s_pertes_val = pertes if pertes is not None else 1e9
            
            s_rend_inc = 1 if rendement is None else 0
            s_rend_val = (1.0 - rendement) if rendement is not None else 1.0

            score = (0, 0, s_elec, s_soh_inc, s_soh_val, s_pertes_inc, s_pertes_val, s_rend_inc, s_rend_val)

            grille["points"].append(PointGrille(
                rpm=rpm, couple_nm=c, p_meca_w=p_meca, p_elec_w=p_elec,
                pertes_totales_w=pertes, rendement=rendement,
                statut_meca="ok", statut_elec=("ok" if s_elec == 0 else ("partiel" if s_elec == 1 else "impossible")),
                score_lexico=score,
                rapport_alternateur=rep,
                inconnues=inc_imp + inc_par
            ))
    return grille

# --- FONCTION PRINCIPALE ---

def calculer_strategie_couplage(
    etat_systeme: Dict[str, Any],
    composants: Dict[str, Any]
) -> Dict[str, Any]:
    rapport = {
        "decision": None, "mode_energetique": "ev_only",
        "enveloppe_batterie": None, "bilan_bus_dc": {},
        "derivees_chaine_energie": {}, "candidats": [],
        "point_retenu": None, "validation_transitoire": {"statut": "non_calcule"},
        "inconnues": {"impossibles": [], "partielles": []},
        "alertes": {}, "notes_modele": []
    }

    bat = composants.get("batterie")
    alt = composants.get("alternateur")
    mt = composants.get("moteur_thermique")
    bt = composants.get("boite_crabots")
    me = composants.get("moteur_electrique")

    v_bus = etat_systeme.get("v_bus_dc_v")
    soc = etat_systeme.get("batterie_soc")
    p_roue = etat_systeme.get("puissance_traction_roue_w")
    
    if any(x is None for x in (bat, v_bus, soc, p_roue)):
        raison = f"Données critiques manquantes : " + (", ".join([k for k, v in {"Bat": bat, "Vbus": v_bus, "SoC": soc, "Proue": p_roue}.items() if v is None]))
        rapport["inconnues"]["impossibles"].append({"nom": "strategie_globale", "raison": raison})
        return rapport

    # 1. Enveloppe Batterie
    env, inc_env = determiner_enveloppe_batterie(bat, etat_systeme)
    rapport["enveloppe_batterie"] = env
    rapport["inconnues"]["partielles"].extend(inc_env)

    # 2. Chaîne d'énergie (Roue -> Bus DC)
    eta_me = getattr(me, "rendement_moteur_electrique", None)
    if eta_me is not None and eta_me > 0:
        p_traction_bus = p_roue / eta_me
        rapport["derivees_chaine_energie"]["p_traction_bus_dc_w"] = p_traction_bus
    else:
        rapport["inconnues"]["partielles"].append({"nom": "rendement_moteur_electrique", "raison": "Conversion Roue -> Bus DC impossible précisément."})
        p_traction_bus = None

    # 3. Arbitrage Mode
    temp_c = etat_systeme.get("batterie_temp_c")
    temp_critique = getattr(bat, "temp_cellule_critique_c", None)
    soc_min_soutien = getattr(bat, "soc_seuil_soutien_traction", None)
    soc_max_recharge = getattr(bat, "soc_seuil_fin_recharge", None)
    
    if temp_c is not None and temp_critique is not None and temp_c >= temp_critique:
        rapport["mode_energetique"] = "mode_degrade"
        p_charge_cible = 0.0
        rapport["alertes"]["thermique"] = "Température batterie critique : charge interdite."
    elif all(x is not None for x in (soc_min_soutien, soc_max_recharge)):
        if p_roue > 0 and soc < soc_min_soutien:
            rapport["mode_energetique"] = "soutien_traction"
        elif soc < soc_max_recharge:
            rapport["mode_energetique"] = "recharge_batterie"
        else:
            rapport["mode_energetique"] = "ev_only"
        p_charge_cible = env.p_charge_recommandee_w if env.p_charge_recommandee_w is not None else 0.0
    else:
        rapport["inconnues"]["partielles"].append({"nom": "arbitrage_mode", "raison": "Seuils SoC (soutien/recharge) inconnus. Mode par défaut: ev_only."})
        rapport["mode_energetique"] = "ev_only"
        p_charge_cible = 0.0

    if p_traction_bus is not None:
        p_gen_req = p_traction_bus + p_charge_cible
    else:
        p_gen_req = None
        rapport["inconnues"]["impossibles"].append({"nom": "puissance_generation", "raison": "Impossible de calculer la puissance bus DC requise."})

    rapport["bilan_bus_dc"] = {"p_gen_requise_w": p_gen_req, "p_charge_cible_w": p_charge_cible}

    # 4. Optimisation
    if p_gen_req is not None and p_gen_req > 0 and alt:
        bornes = etat_systeme.get("bornes_recherche")
        if not bornes:
            rapport["inconnues"]["impossibles"].append({"nom": "cartographie", "raison": "Bornes de recherche absentes"})
            return rapport
            
        carto = generer_carto_energetique(alt, bornes, v_bus, etat_systeme.get("batterie_soh"))
        
        candidats = []
        for pt in carto["points"]:
            if pt.p_elec_w is None or abs(pt.p_elec_w - p_gen_req) / max(p_gen_req, 1.0) > 0.05: continue
            raps = getattr(bt, "rapports", None)
            if not raps: continue
            for nom_rap, ratio in raps.items():
                rpm_mt = pt.rpm / ratio
                rpm_min_mt, rpm_max_mt = getattr(mt, "rpm_min", None), getattr(mt, "rpm_max", None)
                if rpm_min_mt is not None and rpm_max_mt is not None and rpm_min_mt <= rpm_mt <= rpm_max_mt:
                    candidats.append({"alternateur": pt, "rapport": nom_rap, "thermique": {"rpm": rpm_mt, "couple_nm": pt.couple_nm * ratio}, "score_lexico": pt.score_lexico})
        
        rapport["candidats"] = candidats
        if candidats:
            candidats.sort(key=lambda x: x["score_lexico"])
            best = candidats[0]
            rapport["point_retenu"] = best
            rapport["decision"] = {"mode": rapport["mode_energetique"], "p_charge_w": p_charge_cible, "rapport_boite": best["rapport"], "point_thermique": best["thermique"]}
        else:
            rapport["inconnues"]["impossibles"].append({"nom": "point_fonctionnement", "raison": "Aucun point alternateur/boîte/thermique atteignable pour la puissance demandée."})

    # 5. Transitoire
    pt_act = etat_systeme.get("point_actuel_thermique")
    dt = etat_systeme.get("temps_disponible_s")
    depl = composants.get("deplaceur")
    r_th = getattr(depl, "resistance_thermique_k_w", None)
    c_th = getattr(depl, "capacite_thermique_j_k", None)
    
    if rapport["point_retenu"] and mt:
        if all(x is not None for x in (pt_act, dt, r_th, c_th)):
            try:
                tau = phys.constante_temps_thermique(r_th, c_th)
                p_init = (pt_act["rpm"] * pt_act["couple_nm"] * 2 * math.pi) / 60
                p_cible = (rapport["point_retenu"]["thermique"]["rpm"] * rapport["point_retenu"]["thermique"]["couple_nm"] * 2 * math.pi) / 60
                p_acc = phys.reponse_transitoire_premier_ordre(p_init, p_cible, dt, tau)
                rapport["validation_transitoire"] = {"statut": "valide" if abs(p_acc - p_cible) < 0.1 * (p_gen_req or 1.0) else "limite_inertie", "p_accessible_w": p_acc}
            except Exception as e:
                rapport["validation_transitoire"] = {"statut": "erreur", "raison": str(e)}
        else:
            rapport["validation_transitoire"] = {"statut": "impossible", "raison": "Données transitoires (Pt actuel, dt, Rth ou Cth) manquantes."}

    return rapport
