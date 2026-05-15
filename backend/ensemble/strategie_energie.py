# backend/ensemble/strategie_energie.py
# -*- coding: utf-8 -*-
"""
strategie_energie.py
=========================================================
Cerveau énergétique SHSE-M — Couplage Batterie/GMP
=========================================================
Séparation stricte entre modèle physique et arbitrage de mission.
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
    "ev_only",           # Batterie seule
    "soutien_traction",  # Thermique aide traction bus DC
    "recharge_batterie", # Thermique recharge batterie
    "maintien_soc",      # Thermique maintient SoC cible
    "mode_degrade",      # Surcharge/Sécurité (Charge interdite)
    "urgence_puissance"  # Priorité traction sur SoH (si autorisé)
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
    raison_limitante: str = ""

@dataclass(frozen=True)
class PointGrille:
    """Point riche de la cartographie énergétique."""
    rpm: float
    couple_nm: float
    statut: Literal["ok", "partiel", "impossible"]
    p_meca_w: float
    p_elec_w: Optional[float] = None
    rendement: Optional[float] = None
    rapport_alternateur: Dict[str, Any] = field(default_factory=dict)
    inconnues: List[Dict[str, str]] = field(default_factory=list)

@dataclass(frozen=True)
class DecisionEnergetique:
    """Synthèse de l'arbitrage."""
    mode: ModeEnergetique
    p_charge_cible_w: float
    point_retenu: Optional[Dict[str, Any]] = None
    inconnues: Dict[str, List[Dict[str, str]]] = field(default_factory=lambda: {"impossibles": [], "partielles": []})

# --- FONCTIONS INTERNES ---

def determiner_enveloppe_batterie(
    batterie_obj: Any,
    etat_actuel: Dict[str, Any]
) -> Tuple[EnveloppeBatterie, List[Dict[str, str]]]:
    """Calcule les limites sans inventer de données manquantes."""
    inconnues = []
    limites = []
    
    temp_c = etat_actuel.get("batterie_temp_c")
    soc = etat_actuel.get("batterie_soc")
    soh = etat_actuel.get("batterie_soh")
    v_bus = etat_actuel.get("v_bus_dc_v")
    
    cap_ah = getattr(batterie_obj, "capacite_ah", None)
    c_rate_max = getattr(batterie_obj, "c_rate_charge_max", None)
    temp_limite = getattr(batterie_obj, "temp_cellule_critique_c", None)

    # 1. Limite C-rate
    p_crate = None
    if all(x is not None for x in (c_rate_max, cap_ah, v_bus)):
        try:
            # On vérifie indirectement via phys (qui lève des erreurs si < 0)
            phys.calculer_c_rate(c_rate_max * cap_ah, cap_ah) 
            i_max = c_rate_max * cap_ah
            p_crate = i_max * v_bus
        except Exception as e:
            inconnues.append({"nom": "p_charge_max_crate_w", "raison": f"Erreur calcul physique: {e}"})
    else:
        inconnues.append({"nom": "p_charge_max_crate_w", "raison": "Manque c_rate_max, capacite_ah ou v_bus_dc_v"})

    # 2. Limite Température (Derating)
    p_temp = None
    if all(x is not None for x in (temp_c, temp_limite, v_bus, cap_ah)):
        delta = temp_limite - temp_c
        if delta <= 0:
            p_temp = 0.0
            limites.append("temp_critique")
        elif delta < 5.0:
            facteur = delta / 5.0
            p_temp = (p_crate or 0.0) * facteur
            limites.append("derating_thermique")
        else:
            p_temp = p_crate
    else:
        inconnues.append({"nom": "p_charge_max_temp_w", "raison": "Manque temp_c ou temp_cellule_critique_c"})

    # 3. Limite SoH
    p_soh = None
    if soh is not None and p_crate is not None:
        p_soh = p_crate * max(0.1, soh) # Règle de gestion : pas plus que le SoH relatif
        if soh < 0.85: limites.append("protection_soh")
    else:
        inconnues.append({"nom": "p_charge_max_soh_w", "raison": "Manque soh ou p_crate"})

    valeurs = [v for v in [p_crate, p_temp, p_soh] if v is not None]
    p_reco = min(valeurs) if valeurs else None
    
    env = EnveloppeBatterie(
        p_charge_max_soh_w=p_soh, p_charge_max_temp_w=p_temp,
        p_charge_max_crate_w=p_crate, p_charge_recommandee_w=p_reco,
        limites_actives=limites,
        raison_limitante=min([("temp", p_temp), ("soh", p_soh), ("crate", p_crate)], key=lambda x: x[1] if x[1] is not None else float('inf'))[0] if limites else "Optimale"
    )
    return env, inconnues

def generer_carto_energetique(
    alternateur_obj: Any,
    bornes: Dict[str, float],
    v_bus: float
) -> Dict[str, Any]:
    """Construit la grille en propageant les inconnues du modèle alternateur."""
    grille = {"points": [], "inconnues_globales": []}
    
    keys = ["rpm_min", "rpm_max", "rpm_step", "couple_min", "couple_max", "couple_step"]
    if any(bornes.get(k) is None for k in keys):
        grille["inconnues_globales"].append("Bornes de recherche incomplètes")
        return grille

    # On utilise l'API réelle de l'alternateur
    fn_analyse = getattr(alternateur_obj, "analyser_point_de_fonctionnement", None)
    if not callable(fn_analyse):
        grille["inconnues_globales"].append("L'objet alternateur n'expose pas analyser_point_de_fonctionnement")
        return grille

    for rpm in range(int(bornes["rpm_min"]), int(bornes["rpm_max"]) + 1, int(bornes["rpm_step"])):
        for c in range(int(bornes["couple_min"]), int(bornes["couple_max"]) + 1, int(bornes["couple_step"])):
            p_meca = (c * 2 * math.pi * rpm) / 60
            
            # Appel du modèle métier SANS hypothèse de rendement
            rep = fn_analyse(vitesse_rotation_rpm=rpm, tension_v=v_bus)
            
            p_elec = rep.get("sortie_electrique", {}).get("puissance_utile_w") # Ici, on espère que le modèle calcule P_elec = P_meca - Pertes
            rendement = rep.get("rendement", {}).get("eta_sur_pertes_connues")
            
            statut = "ok"
            if rep.get("inconnues", {}).get("impossibles"): statut = "impossible"
            elif rep.get("inconnues", {}).get("partielles"): statut = "partiel"

            grille["points"].append(PointGrille(
                rpm=rpm, couple_nm=c, p_meca_w=p_meca, p_elec_w=p_elec,
                rendement=rendement, statut=statut,
                rapport_alternateur=rep,
                inconnues=rep.get("inconnues", {}).get("impossibles", []) + rep.get("inconnues", {}).get("partielles", [])
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
        "candidats": [], "validation_transitoire": {"statut": "non_calcule"},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": []
    }

    bat = composants.get("batterie")
    alt = composants.get("alternateur")
    mt = composants.get("moteur_thermique")
    bt = composants.get("boite_crabots")

    if not bat:
        rapport["inconnues"]["impossibles"].append({"nom": "strategie", "raison": "Batterie absente"})
        return rapport

    # 1. Enveloppe Batterie
    env, inc_env = determiner_enveloppe_batterie(bat, etat_systeme)
    rapport["enveloppe_batterie"] = env
    rapport["inconnues"]["partielles"].extend(inc_env)

    # 2. Arbitrage Mode & Sécurité
    p_charge_cible = 0.0
    temp_c = etat_systeme.get("batterie_temp_c", 0)
    temp_limite = getattr(bat, "temp_cellule_critique_c", 100)
    
    if temp_c >= temp_limite:
        rapport["mode_energetique"] = "mode_degrade"
        rapport["notes_modele"].append("Sécurité : Température critique. Charge batterie interdite.")
        p_charge_cible = 0.0
    else:
        soc = etat_systeme.get("batterie_soc", 0.5)
        p_traction = etat_systeme.get("puissance_traction_roue_w", 0.0)
        
        if p_traction > 0 and soc < 0.15:
            rapport["mode_energetique"] = "soutien_traction"
        elif soc < 0.8:
            rapport["mode_energetique"] = "recharge_batterie"
        else:
            rapport["mode_energetique"] = "ev_only"
            
        p_charge_cible = env.p_charge_recommandee_w or 0.0

    # 3. Bilan Bus DC
    p_traction = etat_systeme.get("puissance_traction_roue_w", 0.0)
    p_gen_requise = p_traction + p_charge_cible
    rapport["bilan_bus_dc"] = {"p_traction_w": p_traction, "p_charge_cible_w": p_charge_cible, "p_gen_requise_w": p_gen_requise}

    # 4. Optimisation Lexicographique
    if p_gen_requise > 0 and alt:
        bornes = etat_systeme.get("bornes_recherche", {
            "rpm_min": 1000, "rpm_max": 6000, "rpm_step": 500,
            "couple_min": 10, "couple_max": 200, "couple_step": 20
        })
        v_bus = etat_systeme.get("v_bus_dc_v", 400.0)
        carto = generer_carto_energetique(alt, bornes, v_bus)
        
        # Sélection lexicographique
        candidats = []
        for pt in carto["points"]:
            if pt.p_elec_w is None: continue
            # On cherche les points proches de la cible (marge 5%)
            if abs(pt.p_elec_w - p_gen_requise) / max(p_gen_requise, 1.0) < 0.05:
                # Filtrage boîte
                rapports = getattr(bt, "rapports", {"direct": 1.0})
                for nom_rap, ratio in rapports.items():
                    rpm_mt = pt.rpm / ratio
                    if getattr(mt, "rpm_min", 800) <= rpm_mt <= getattr(mt, "rpm_max", 6000):
                        candidats.append({
                            "alternateur": pt, "rapport": nom_rap,
                            "thermique": {"rpm": rpm_mt, "couple_nm": pt.couple_nm * ratio},
                            "score_stress": -(pt.rendement or 0.0) # Stress inversement proportionnel au rendement
                        })
        
        if candidats:
            candidats.sort(key=lambda x: (x["alternateur"].statut != "ok", x["score_stress"]))
            best = candidats[0]
            rapport["point_retenu"] = best
            rapport["decision"] = {
                "mode": rapport["mode_energetique"],
                "p_charge_w": p_charge_cible,
                "rapport_boite": best["rapport"],
                "point_thermique": best["thermique"]
            }
        else:
            rapport["inconnues"]["impossibles"].append({"nom": "point_optimal", "raison": "Aucun point de fonctionnement trouvé dans la grille."})

    # 5. Validation Transitoire
    if rapport["point_retenu"] and mt:
        point_actuel = etat_systeme.get("point_actuel_thermique", {"rpm": 800, "couple_nm": 0})
        point_cible = rapport["point_retenu"]["thermique"]
        dt = etat_systeme.get("temps_disponible_s", 1.0)
        
        depl = composants.get("deplaceur")
        r_th = getattr(depl, "resistance_thermique_k_w", None)
        c_th = getattr(depl, "capacite_thermique_j_k", None)
        
        if all(x is not None for x in (r_th, c_th)):
            try:
                tau = phys.constante_temps_thermique(r_th, c_th)
                p_init = (point_actuel["rpm"] * point_actuel["couple_nm"] * 2 * math.pi) / 60
                p_cible = (point_cible["rpm"] * point_cible["couple_nm"] * 2 * math.pi) / 60
                p_acc = phys.reponse_transitoire_premier_ordre(p_init, p_cible, dt, tau)
                
                rapport["validation_transitoire"] = {
                    "statut": "valide" if abs(p_acc - p_cible) < 0.1 * p_cible else "limite_inertie",
                    "p_accessible_w": p_acc, "tau_s": tau
                }
            except Exception as e:
                rapport["validation_transitoire"] = {"statut": "erreur", "raison": str(e)}
        else:
            rapport["validation_transitoire"] = {"statut": "impossible", "raison": "Manque Rth ou Cth déplaceur"}

    return rapport
