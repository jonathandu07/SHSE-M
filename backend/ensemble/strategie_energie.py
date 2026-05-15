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
    rapport["bilan_bus_dc"] = {
        "p_traction_w": etat_systeme.get("puissance_traction_roue_w"),
        "p_charge_cible_w": p_charge_cible,
        "p_gen_requise_w": etat_systeme.get("puissance_traction_roue_w", 0) + p_charge_cible
    }

    # TODO: Phase 3 - Recherche du point optimal (Lexicographique)
    # TODO: Phase 4 - Validation transitoire

    return rapport
