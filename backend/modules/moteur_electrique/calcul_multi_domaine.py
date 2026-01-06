# backend\modules\moteur_electrique\calcul_multi_domaine.py
from __future__ import annotations
import math
from typing import Literal, Dict, Any

# =============================================================================
# CONSTANTES PHYSIQUES
# =============================================================================
G = 9.80665
RHO_AIR_NIVEAU_MER = 1.225
RHO_EAU_MER = 1025.0

# =============================================================================
# FORMULES DE TRACTION MULTI-DOMAINE
# =============================================================================

def calcul_demande_nautique(
    vitesse_ms: float, 
    surface_mouillee_m2: float, 
    cw_coque: float, 
    eta_helice: float = 0.6
) -> Dict[str, float]:
    """
    Calcule la force et la puissance pour la propulsion navale.
    Formule : F = 0.5 * rho * S * Cw * v^2
    """
    # Résistance hydrodynamique
    force_eau = 0.5 * RHO_EAU_MER * surface_mouillee_m2 * cw_coque * (vitesse_ms**2)
    
    # Puissance nécessaire à l'hélice (incluant rendement hélice)
    puissance_helice = (force_eau * vitesse_ms) / eta_helice
    
    return {
        "force_N": force_eau,
        "puissance_W": puissance_helice,
        "type": "Nautique"
    }



def calcul_demande_aerien(
    vitesse_ms: float, 
    altitude_m: float, 
    diametre_helice_m: float,
    ct_coefficient: float = 0.1,  # Coefficient de poussée
    cp_coefficient: float = 0.05  # Coefficient de puissance
) -> Dict[str, float]:
    """
    Calcule la poussée et la puissance pour un avion ou drone.
    Intègre la variation de densité de l'air avec l'altitude.
    """
    # 1. Calcul de la densité de l'air selon l'altitude (Modèle troposphère)
    # rho = rho0 * (1 - L*h/T0)^(gM/RL - 1)
    rho_alt = RHO_AIR_NIVEAU_MER * math.pow((1 - 0.0065 * altitude_m / 288.15), 4.256)
    
    # 2. Puissance absorbée par l'hélice (approximative pour dimensionnement)
    # Note : Le régime n (tours/s) est nécessaire pour une précision absolue
    # Ici, nous calculons la puissance de traînée aérodynamique de la cellule
    # pour maintenir la vitesse ms.
    force_trainee = 0.5 * rho_alt * 0.75 * 0.3 * (vitesse_ms**2) # Exemple Cx/S
    puissance_W = force_trainee * vitesse_ms
    
    return {
        "densite_air": rho_alt,
        "force_N": force_trainee,
        "puissance_W": puissance_W,
        "type": "Aérien"
    }



def calcul_demande_ferroviaire(
    vitesse_ms: float, 
    masse_kg: float, 
    acceleration_ms2: float = 0.0
) -> Dict[str, float]:
    """
    Calcule la demande pour la traction ferroviaire (Équation de Davis).
    F = A + Bv + Cv^2
    """
    # Coefficients de Davis (exemple pour un convoi moyen)
    A = masse_kg * 0.0015 * G  # Résistance au roulement acier/acier
    B = 0.5 * vitesse_ms       # Résistance mécanique
    C = 0.25 * (vitesse_ms**2) # Aéro convoi
    
    force_res = A + B + C
    force_inertie = masse_kg * acceleration_ms2 * 1.1 # k=0.1 pour masses tournantes
    
    force_totale = force_res + force_inertie
    puissance_W = force_totale * vitesse_ms
    
    return {
        "force_N": force_totale,
        "puissance_W": puissance_W,
        "type": "Ferroviaire"
    }



# =============================================================================
# WRAPPER D'INTÉGRATION POUR TON COMPOSANT MOTEUR
# =============================================================================

def generer_rapport_mission(
    domaine: Literal["nautique", "aerien", "ferroviaire"],
    params: Dict[str, Any]
) -> Dict[str, float]:
    """
    Point d'entrée pour tes scripts backend.
    """
    if domaine == "nautique":
        res = calcul_demande_nautique(
            params["vitesse_ms"], 
            params["surface_mouillee_m2"], 
            params["cw_coque"]
        )
    elif domaine == "aerien":
        res = calcul_demande_aerien(
            params["vitesse_ms"], 
            params["altitude_m"], 
            params["diametre_helice_m"]
        )
    else:
        res = calcul_demande_ferroviaire(
            params["vitesse_ms"], 
            params["masse_kg"], 
            params.get("acceleration_ms2", 0.0)
        )
        
    return res

if __name__ == "__main__":
    # Test pour un bateau à 15 nœuds (~7.7 m/s)
    print(generer_rapport_mission("nautique", {"vitesse_ms": 7.7, "surface_mouillee_m2": 25, "cw_coque": 0.4}))