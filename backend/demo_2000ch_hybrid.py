import sys
import os
import math

# Ajout du chemin racine (parent de backend)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.modules.architecture.resolution_globale_architecture import resoudre_architecture_globale

def demonstration_sizing_2000ch():
    print("=== DÉMONSTRATION DIMENSIONNEMENT HYBRIDE SÉRIE 2000 CH ===\n")

    # 1. Inputs Utilisateur
    puissance_moteur_elec_ch = 2000.0
    puissance_moteur_elec_w = puissance_moteur_elec_ch * 735.499
    
    rendement_inverter = 0.95
    rendement_generatrice = 0.94
    rendement_transmission = 0.98
    
    puissance_auxiliaires_w = 5000.0 # Clime, Pompe, Avionique...
    
    # 2. Scénario "Batterie Vide" -> Le thermique doit tout fournir
    # Il doit alimenter le moteur via la chaine électrique ET recharger la batterie
    print(f"Puissance Traction: {puissance_moteur_elec_w/1000:.1f} kW ({puissance_moteur_elec_ch} ch)")
    
    # Puissance électrique requise au niveau du bus DC pour la traction
    p_dc_traction = puissance_moteur_elec_w / rendement_inverter
    
    # Puissance de charge batterie (Ex: Recharger 50kWh en 30min -> 100kW)
    # Hypothèse: Recharge rapide demandée
    battery_capacity_kwh = 100.0 # Ex: 100kWh pour tampon
    time_to_charge_h = 1.0 
    p_dc_charge = (battery_capacity_kwh * 1000) / time_to_charge_h
    
    print(f"Puissance Charge Batterie: {p_dc_charge/1000:.1f} kW (pour recharger {battery_capacity_kwh}kWh en {time_to_charge_h}h)")
    print(f"Puissance Auxiliaires: {puissance_auxiliaires_w/1000:.1f} kW")
    
    p_dc_total = p_dc_traction + p_dc_charge + puissance_auxiliaires_w
    print(f"Puissance Totale Bus DC: {p_dc_total/1000:.1f} kW")
    
    # 3. Dimensionnement du Moteur Thermique
    # Le thermique entraine la génératrice.
    # P_meca_thermique = P_elec_gen_out / eta_gen
    p_meca_thermique_requise = p_dc_total / rendement_generatrice
    
    print(f"\n>> PUISSANCE THERMIQUE REQUISE: {p_meca_thermique_requise/1000:.1f} kW ({p_meca_thermique_requise/735.5:.0f} ch)")
    
    # 4. Résolution Architecturale pour ce moteur de ~1.7MW
    # On utilise le solveur créé précédemment
    
    # Paramètres de contrainte pour un tel monstre
    # Probablement un gros engin, donc de la place ?
    L_max = 2.5 
    W_max = 1.5 
    
    print("\n--- Recherche de l'architecture optimale pour cette puissance ---")
    best_config = resoudre_architecture_globale(
        puissance_cible_w=p_meca_thermique_requise,
        regime_tr_min=2500.0, # Moteur lent car très gros
        pme_pa=18e5, # Turbo Diesel Fortement Suralimenté (18 bars)
        vitesse_piston_max_ms=18.0, # Conservateur pour fiabilité
        L_max_m=L_max,
        W_max_m=W_max
    )
    
    if best_config:
        print(f"\n[SOLUTION RETENUE]")
        print(f"Architecture: {best_config['Architecture']}")
        print(f"Nombre de cylindres: {best_config['N_cyl']}")
        print(f"Alésage: {best_config['Bore_mm']:.1f} mm")
        print(f"Cylindrée Totale: {(best_config['N_cyl'] * (math.pi*(best_config['Bore_mm']/1000)**2/4 * (best_config['Bore_mm']/1000 * 1.2)) * 1000):.1f} Litres (Est.)")
    else:
        print("Pas de solution trouvée dans les contraintes.")

if __name__ == "__main__":
    demonstration_sizing_2000ch()
