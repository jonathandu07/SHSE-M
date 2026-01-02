# backend\main.py
import sys
import os
import math

# Ajout du chemin racine pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.modules.architecture.resolution_globale_architecture import resoudre_architecture_globale
from backend.definition_pieces import dimensionner_pieces_completes

def dimensionner_systeme_shsem(puissance_traction_kw: float, charger_batterie: bool = True):
    """
    Calcule les besoins globaux et détermine l'architecture moteur optimale.
    """
    print(f"=== DIMENSIONNEMENT SYSTÈME SHSE-M ({puissance_traction_kw} kW) ===\n")

    # 1. PARAMÈTRES DE RENDEMENT (Standards industriels SHSE-M)
    ETA_INVERTER = 0.97
    ETA_GEN = 0.95
    ETA_TRANS_MECA = 0.98
    
    # 2. PUISSANCES ANNEXES
    # Auxiliaires (Climatisation, Pompes, Electronique)
    p_aux_w = 5000.0  # 5 kW par défaut
    
    # Charge Batterie (Tampon pour hybride série)
    # On prévoit de quoi charger environ 20% de la puissance de traction en continu 
    # ou une valeur fixe si batterie vide.
    p_charge_bat_w = 0.0
    if charger_batterie:
        p_charge_bat_w = max(20000.0, puissance_traction_kw * 1000.0 * 0.1) # Min 20kW ou 10%

    # 3. CALCUL DU BUS DC
    # Puissance électrique demandée par l'onduleur pour la traction
    p_traction_dc = (puissance_traction_kw * 1000.0) / ETA_INVERTER
    
    p_dc_total = p_traction_dc + p_charge_bat_w + p_aux_w
    print(f"Puissance Traction (Meca Roues): {puissance_traction_kw:.1f} kW")
    print(f"Puissance Charge Batterie: {p_charge_bat_w/1000:.1f} kW")
    print(f"Puissance Auxiliaires: {p_aux_w/1000:.1f} kW")
    print(f"---")
    print(f"PUISSANCE TOTALE REQUISE (Bus DC): {p_dc_total/1000:.1f} kW\n")

    # 4. BESOIN THERMIQUE (Le moteur doit fournir ça via la génératrice)
    p_meca_thermique_w = p_dc_total / (ETA_GEN * ETA_TRANS_MECA)
    
    print(f">> BESOIN MOTEUR THERMIQUE (Sortie Vilebrequin): {p_meca_thermique_w/1000:.1f} kW ({p_meca_thermique_w/735.5:.0f} ch)")

    # 5. RÉSOLUTION ARCHITECTURALE
    # On définit des contraintes physiques raisonnables pour un groupe électrogène
    print("\n[Étape 2: Optimisation de l'Architecture]")
    
    config = resoudre_architecture_globale(
        puissance_cible_w=p_meca_thermique_w,
        regime_tr_min=3000.0,        # Régime stable pour génératrice
        pme_pa=15e5,                # 15 bars (Turbo Standard)
        vitesse_piston_max_ms=16.0, # Pour la longévité (GenSet)
        L_max_m=1.8,                # Contraintes packaging
        W_max_m=1.2
    )

    if config:
        print(f"\n[RÉSULTAT FINAL]")
        print(f"Nombre de cylindres : {config['N_cyl']}")
        print(f"Architecture : {config['Architecture']}")
        print(f"Alésage : {config['Bore_mm']:.1f} mm")
        print(f"Coût maintenance estimé : {config['Cout_Maint_Estime']:.0f} € / 20kh")
        
        # 6. DIMENSIONNEMENT COMPLET DES PIÈCES
        # On injecte les résultats de l'optimisation dans le moteur de calcul des pièces
        dimensionner_pieces_completes(
            puissance_cible_w=p_meca_thermique_w,
            regime_tr_min=config['RPM'],
            n_cyl=config['N_cyl'],
            pression_max_pa=config.get('P_max', 90e5) # Pmax du cycle
        )
        
        return config
    else:
        print("\nAucune configuration n'a pu être validée pour cette puissance.")
        return None

if __name__ == "__main__":
    # Puissance par défaut (150kW) ou via argument
    p_in = 150.0
    if len(sys.argv) > 1:
        try:
            p_in = float(sys.argv[1])
        except ValueError:
            pass
            
    dimensionner_systeme_shsem(p_in)
