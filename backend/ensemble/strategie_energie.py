# backend/ensemble/strategie_energie.py
# -*- coding: utf-8 -*-
"""
strategie_energie.py
=========================================================
Cerveau énergétique SHSE-M — Couplage Batterie/Groupe Motopropulseur
=========================================================

Hiérarchie de décision :
1. Sécurité Système (Température, Tensions, Courants)
2. Continuité Fonctionnelle (Traction minimale)
3. Préservation Batterie (SoH, C-rate, Pertes Joule)
4. Optimisation Rendement (Alternateur, Boîte, Thermique)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal, Tuple, Union
import math

# Imports physiques atomiques
try:
    from backend.ensemble import calcul_stho_me as phys
except ImportError:
    import calcul_stho_me as phys  # type: ignore

# --- TYPES ---

ModeEnergetique = Literal[
    "ev_only",           # Batterie seule
    "soutien_traction",  # Thermique aide la traction
    "recharge_batterie", # Thermique recharge batterie
    "maintien_soc",      # Thermique maintient le SoC
    "mode_degrade",      # Sécurité ou SoH critique
    "urgence_puissance"  # Priorité traction brute sur SoH
]

# --- DATACLASSES ---

@dataclass(frozen=True)
class EnveloppeBatterie:
    """
    Définit les limites de charge/décharge à un instant T.
    Toutes les valeurs sont Optionnelles : si Inconnues, elles valent None.
    """
    p_charge_max_soh_w: Optional[float] = None
    p_charge_max_temp_w: Optional[float] = None
    p_charge_max_crate_w: Optional[float] = None
    p_charge_max_bus_w: Optional[float] = None
    p_charge_recommandee_w: Optional[float] = None
    limites_actives: List[str] = field(default_factory=list)
    raison_limitante: str = ""

@dataclass(frozen=True)
class PointFonctionnement:
    """Point de fonctionnement d'une machine tournante ou d'un moteur."""
    rpm: Optional[float] = None
    couple_nm: Optional[float] = None
    puissance_w: Optional[float] = None
    rendement: Optional[float] = None
    pertes_w: Optional[float] = None

@dataclass(frozen=True)
class DecisionEnergetique:
    """Le résultat de l'arbitrage énergétique."""
    mode: ModeEnergetique
    p_charge_cible_w: float
    point_alternateur: PointFonctionnement
    rapport_boite: Optional[str]
    point_thermique: PointFonctionnement
    validation_transitoire: Dict[str, Any]

# --- LOGIQUE DE CALCUL ---

def determiner_enveloppe_batterie(
    batterie_obj: Any,
    etat_actuel: Dict[str, Any]
) -> Tuple[EnveloppeBatterie, List[Dict[str, str]]]:
    """
    Calcule l'enveloppe de puissance admissible en fonction de la santé de la batterie.
    """
    inconnues = []
    limites = []
    
    # Récupération des données d'état
    temp_c = etat_actuel.get("batterie_temp_c")
    soc = etat_actuel.get("batterie_soc")
    soh = etat_actuel.get("batterie_soh")
    v_bus = etat_actuel.get("v_bus_dc_v")
    
    # Récupération des paramètres batterie (on ne suppose rien)
    cap_ah = getattr(batterie_obj, "capacite_ah", None)
    c_rate_max = getattr(batterie_obj, "c_rate_charge_max", None)
    r_interne = getattr(batterie_obj, "resistance_interne_ohm", None)
    temp_limite = getattr(batterie_obj, "temp_cellule_critique_c", None)

    # 1. Limite par C-rate
    p_crate = None
    if all(x is not None for x in (c_rate_max, cap_ah, v_bus)):
        i_max = c_rate_max * cap_ah
        p_crate = i_max * v_bus
    else:
        inconnues.append({"nom": "p_charge_max_crate_w", "raison": "Manque c_rate_max, capacite_ah ou v_bus_dc_v"})

    # 2. Limite par Température (Derating simple si approché)
    p_temp = None
    if all(x is not None for x in (temp_c, temp_limite, v_bus, cap_ah)):
        # Si on est à 5°C de la limite, on commence à réduire linéairement
        delta = temp_limite - temp_c
        if delta <= 0:
            p_temp = 0.0
            limites.append("temp_critique")
        elif delta < 5.0:
            facteur = delta / 5.0
            p_temp = (p_crate or 100000.0) * facteur # On réduit par rapport au max possible
            limites.append("derating_thermique")
        else:
            p_temp = p_crate
    else:
        inconnues.append({"nom": "p_charge_max_temp_w", "raison": "Manque temp_c ou temp_cellule_critique_c"})

    # 3. Limite par SoH (Préservation)
    p_soh = None
    if soh is not None and p_crate is not None:
        # Plus le SoH est bas, plus on limite le courant de charge pour éviter de l'achever
        p_soh = p_crate * max(0.2, soh) # Jamais moins de 20% du max si on veut charger
        if soh < 0.8:
            limites.append("protection_soh")
    else:
        inconnues.append({"nom": "p_charge_max_soh_w", "raison": "Manque soh ou p_crate"})

    # Synthèse de la puissance recommandée (le min des contraintes calculables)
    valeurs = [v for v in [p_crate, p_temp, p_soh] if v is not None]
    p_reco = min(valeurs) if valeurs else None
    
    raison = "Optimale"
    if p_reco == p_temp: raison = "Limité par température"
    if p_reco == p_soh: raison = "Limité par SoH (vieillissement)"
    if p_reco == p_crate: raison = "Limité par C-rate constructeur"

    env = EnveloppeBatterie(
        p_charge_max_soh_w=p_soh,
        p_charge_max_temp_w=p_temp,
        p_charge_max_crate_w=p_crate,
        p_charge_max_bus_w=None, # À implémenter si on a les limites onduleur
        p_charge_recommandee_w=p_reco,
        limites_actives=limites,
        raison_limitante=raison
    )
    
    return env, inconnues

def generer_carto_alternateur(
    alternateur_obj: Any,
    bornes: Dict[str, float]
) -> Dict[str, Any]:
    """
    Génère une grille [RPM x Couple] de performance alternateur.
    Bornes attendues : rpm_min, rpm_max, rpm_step, couple_min, couple_max, couple_step.
    """
    grille = {
        "points": [],
        "inconnues": []
    }
    
    rmin = bornes.get("rpm_min")
    rmax = bornes.get("rpm_max")
    rstep = bornes.get("rpm_step")
    cmin = bornes.get("couple_min")
    cmax = bornes.get("couple_max")
    cstep = bornes.get("couple_step")
    
    if any(x is None for x in (rmin, rmax, rstep, cmin, cmax, cstep)):
        return grille # Grille vide si bornes manquantes
    
    # Paramètres physiques pour calcul des pertes (si disponibles)
    r_phase = getattr(alternateur_obj, "resistance_phase_ohm", None)
    k_v = getattr(alternateur_obj, "constante_tension_kv", None)
    
    for rpm in range(int(rmin), int(rmax) + 1, int(rstep)):
        for c in range(int(cmin), int(cmax) + 1, int(cstep)):
            p_meca = (c * 2 * math.pi * rpm) / 60
            
            # Tentative de calcul de rendement
            p_elec = None
            pertes = None
            
            if r_phase is not None:
                # Modèle simplifié : Pertes Joule = 3 * R * I²
                # On a besoin du courant, donc de k_v ou du couple
                # T = k_t * I => I = T / k_t. k_t = 60 / (2 * pi * kv * sqrt(3))
                if k_v is not None:
                    k_t = 60.0 / (2.0 * math.pi * k_v * math.sqrt(3.0))
                    i_phase = c / k_t
                    p_joule = 3.0 * r_phase * (i_phase**2)
                    pertes = p_joule # Pour l'instant, on n'invente pas les pertes fer
                    p_elec = p_meca - pertes
                else:
                    grille["inconnues"].append({"point": (rpm, c), "raison": "Manque constante kv pour courant"})
            else:
                grille["inconnues"].append({"point": (rpm, c), "raison": "Manque resistance_phase_ohm"})
                
            grille["points"].append({
                "rpm": rpm,
                "couple_nm": c,
                "p_meca_w": p_meca,
                "p_elec_w": p_elec,
                "pertes_w": pertes,
                "rendement": (p_elec / p_meca) if (p_elec and p_meca > 0) else None
            })
            
    return grille

def selectionner_point_optimal(
    p_elec_cible: float,
    carto: Dict[str, Any],
    boite_obj: Any,
    thermique_obj: Any,
    poids: Optional[Dict[str, float]] = None
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Recherche lexicographique du meilleur point.
    Priorité : 1. Accessibilité (Boîte), 2. Stress (Courant), 3. Pertes Totales.
    """
    candidats = []
    
    # 1. Filtrer les points qui peuvent produire la puissance cible
    for pt in carto.get("points", []):
        if pt["p_elec_w"] is None: continue
        
        # On accepte une marge de 5% sur la puissance produite
        if abs(pt["p_elec_w"] - p_elec_cible) / max(p_elec_cible, 1.0) < 0.05:
            # Vérifier si un rapport de boîte permet d'atteindre ce RPM thermique
            # (Simplification : on suppose que la boîte est entre le thermique et l'alternateur)
            rapports = getattr(boite_obj, "rapports", {"direct": 1.0})
            for nom_rap, ratio in rapports.items():
                rpm_thermique = pt["rpm"] / ratio
                # Vérifier si le thermique peut tourner à ce régime
                t_max = getattr(thermique_obj, "rpm_max", 6000)
                t_min = getattr(thermique_obj, "rpm_min", 800)
                if t_min <= rpm_thermique <= t_max:
                    candidats.append({
                        "alternateur": pt,
                        "rapport": nom_rap,
                        "thermique": {"rpm": rpm_thermique, "couple_nm": pt["couple_nm"] * ratio},
                        "pertes_totales_w": (pt["pertes_w"] or 0) # + pertes boite si connues
                    })

    if not candidats:
        return None, []

    # 2. Tri Lexicographique
    # On trie par :
    # a) Rendement alternateur (déjà calculé)
    # b) Pertes totales
    candidats.sort(key=lambda x: (-(x["alternateur"]["rendement"] or 0), x["pertes_totales_w"]))
    
    return candidats[0], candidats

def calculer_strategie_couplage(
    etat_systeme: Dict[str, Any],
    composants: Dict[str, Any],
    poids_optimisation: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Arbitre la mission énergétique globale.
    """
    rapport = {
        "decision": None,
        "mode_energetique": "ev_only",
        "enveloppe_batterie": None,
        "bilan_bus_dc": {},
        "candidats": [],
        "point_retenu": None,
        "validation_transitoire": {"statut": "non_calcule"},
        "inconnues": {"impossibles": [], "partielles": []},
        "alertes": {},
        "notes_modele": []
    }

    # 1. Extraction des composants
    batterie = composants.get("batterie")
    alternateur = composants.get("alternateur")
    boite = composants.get("boite_crabots")
    thermique = composants.get("moteur_thermique")

    if not batterie:
        rapport["inconnues"]["impossibles"].append({"nom": "strategie", "raison": "Batterie absente des composants"})
        return rapport

    # 2. Détermination de l'enveloppe batterie
    env, inc_env = determiner_enveloppe_batterie(batterie, etat_systeme)
    rapport["enveloppe_batterie"] = env
    rapport["inconnues"]["partielles"].extend(inc_env)

    # 3. Validation Sécurité immédiate
    temp_c = etat_systeme.get("batterie_temp_c", 0)
    temp_limite = getattr(batterie, "temp_cellule_critique_c", 100)
    if temp_c >= temp_limite:
        rapport["mode_energetique"] = "mode_degrade"
        rapport["notes_modele"].append("ALERTE : Température batterie critique. Arrêt de la charge.")
        p_charge_cible = 0.0
    else:
        # Logique de mode selon SoC et Besoin
        soc = etat_systeme.get("batterie_soc", 1.0)
        p_traction = etat_systeme.get("puissance_traction_roue_w", 0.0)
        
        if p_traction > 0 and soc < 0.2:
            rapport["mode_energetique"] = "soutien_traction"
        elif soc < 0.8:
            rapport["mode_energetique"] = "recharge_batterie"
        else:
            rapport["mode_energetique"] = "ev_only"
            
        p_charge_cible = env.p_charge_recommandee_w if env.p_charge_recommandee_w is not None else 0.0

    # 4. Bilan Bus DC
    p_gen_requise = (etat_systeme.get("puissance_traction_roue_w", 0) + p_charge_cible)
    rapport["bilan_bus_dc"] = {
        "p_traction_w": etat_systeme.get("puissance_traction_roue_w"),
        "p_charge_cible_w": p_charge_cible,
        "p_gen_requise_w": p_gen_requise
    }

    # 5. Recherche du point optimal
    if p_gen_requise > 0 and alternateur:
        # On définit des bornes par défaut pour la recherche si non fournies
        bornes = etat_systeme.get("bornes_recherche", {
            "rpm_min": 1000, "rpm_max": 8000, "rpm_step": 500,
            "couple_min": 5, "couple_max": 200, "couple_step": 10
        })
        
        carto = generer_carto_alternateur(alternateur, bornes)
        best, candidats = selectionner_point_optimal(p_gen_requise, carto, boite, thermique)
        
        rapport["candidats"] = candidats
        rapport["point_retenu"] = best
        
        if best:
            rapport["decision"] = {
                "p_charge_w": p_charge_cible,
                "rapport_boite": best["rapport"],
                "rpm_thermique": best["thermique"]["rpm"],
                "couple_thermique": best["thermique"]["couple_nm"],
                "rpm_alternateur": best["alternateur"]["rpm"],
                "couple_alternateur": best["alternateur"]["couple_nm"]
            }
        else:
            rapport["inconnues"]["impossibles"].append({
                "nom": "point_optimal", 
                "raison": "Aucun point de fonctionnement trouvé pour la puissance cible avec les rapports de boîte actuels."
            })

    # 6. Validation transitoire
    if rapport["point_retenu"] and thermique:
        point_actuel = etat_systeme.get("point_actuel_thermique", {"rpm": 800, "couple_nm": 0})
        point_cible = rapport["point_retenu"]["thermique"]
        dt = etat_systeme.get("temps_disponible_s", 1.0)
        
        # Récupération des paramètres thermiques du déplaceur
        deplaceur = composants.get("deplaceur")
        r_th = getattr(deplaceur, "resistance_thermique_k_w", None)
        c_th = getattr(deplaceur, "capacite_thermique_j_k", None)
        
        validation = {
            "statut": "inconnu",
            "tau_s": None,
            "p_accessible_w": None,
            "inconnues": []
        }
        
        if r_th is not None and c_th is not None:
            tau = phys.constante_temps_thermique(r_th, c_th)
            validation["tau_s"] = tau
            
            p_init = (point_actuel["rpm"] * point_actuel["couple_nm"] * 2 * math.pi) / 60
            p_cible = (point_cible["rpm"] * point_cible["couple_nm"] * 2 * math.pi) / 60
            
            p_reelle = phys.reponse_transitoire_premier_ordre(p_init, p_cible, dt, tau)
            validation["p_accessible_w"] = p_reelle
            
            if abs(p_reelle - p_cible) / max(p_cible, 1.0) < 0.1:
                validation["statut"] = "valide"
            else:
                validation["statut"] = "limite_par_inertie"
                rapport["notes_modele"].append(f"Inertie thermique : seulement {p_reelle/1000:.1f}kW accessibles sur {p_cible/1000:.1f}kW en {dt}s.")
        else:
            if r_th is None: validation["inconnues"].append("resistance_thermique_k_w")
            if c_th is None: validation["inconnues"].append("capacite_thermique_j_k")
            validation["statut"] = "impossible_calculer_transitoire"
            rapport["inconnues"]["partielles"].append({
                "nom": "validation_transitoire", 
                "raison": f"Manque paramètres thermiques déplaceur : {validation['inconnues']}"
            })
            
        rapport["validation_transitoire"] = validation

    return rapport
