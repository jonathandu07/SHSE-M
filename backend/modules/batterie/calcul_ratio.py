# backend\modules\batterie\calcul_ratio.py
import numpy as np
import matplotlib.pyplot as plt

def simulateur_ratio_batterie_robuste():
    # --- CONFIGURATION DU PIRE SCÉNARIO (Worst Case) ---
    TEMP_EXTERIEURE = -15  # Celsius
    COEFF_PERTE_FROID = 0.65  # La batterie perd 35% d'efficacité par grand froid
    PENTE_MOYENNE = 0.05      # 5% de pente constante (montée Ardéchoise)
    RESERVE_SECURITE_SOC = 0.20 # 20% de batterie intouchable (phares, ECU, survie)
    
    # --- BIBLIOTHÈQUE MULTI-CARBURANT ---
    # LHV en MJ/kg | Densité en kg/L | Rendement moteur estimé
    carburants = {
        "Gazole":      {"lhv": 42.7, "rho": 0.85, "eta": 0.35},
        "Ethanol_E85": {"lhv": 26.8, "rho": 0.79, "eta": 0.28},
        "Huile_Veg":   {"lhv": 37.0, "rho": 0.91, "eta": 0.32}
    }
    
    # Sélection du pire carburant pour le dimensionnement (Ethanol = Moins d'énergie)
    c_nom = "Ethanol_E85"
    c = carburants[c_nom]

    # --- DONNÉES VÉHICULE ---
    m_vehicule_vide = 1350.0  # kg
    S_cx = 0.75               # Aérodynamisme
    rho_air_froid = 1.35      # Air plus dense en hiver (augmente la traînée)
    vitesse_ms = 70 / 3.6     # Vitesse de croisière (70 km/h)

    # Paramètres Batterie
    densite_pack = 0.16       # kWh / kg
    
    # --- SIMULATION ---
    tailles_kwh = np.linspace(2.0, 30.0, 150)
    conso_l_100 = []
    
    for kwh_nom in tailles_kwh:
        # 1. Capacité réelle disponible (Froid + Réserve)
        kwh_dispo = kwh_nom * COEFF_PERTE_FROID * (1 - RESERVE_SECURITE_SOC)
        
        # 2. Masse totale
        m_batt = kwh_nom / densite_pack
        m_totale = m_vehicule_vide + m_batt
        
        # 3. Calcul des forces de traction (Joules pour 100km)
        distance = 100000
        f_roulement = m_totale * 9.81 * 0.015
        f_pente = m_totale * 9.81 * PENTE_MOYENNE
        f_aero = 0.5 * rho_air_froid * S_cx * (vitesse_ms**2)
        
        energie_roues_j = (f_roulement + f_pente + f_aero) * distance
        
        # 4. Gain hybridation (Efficacité du Peak Shaving)
        # On muscle la saturation : en conditions dégradées, il faut plus de kWh pour saturer
        gain_max = 0.45 
        saturation_froid = 8.0 # Besoin de plus de tampon car la batterie peine
        facteur_hyb = 1 - (gain_max * (1 - np.exp(-kwh_dispo / saturation_froid)))
        
        # 5. Calcul consommation (MJ -> Litres)
        energie_carbu_mj = (energie_roues_j / 1e6) / (c["eta"] * facteur_hyb)
        conso_litres = (energie_carbu_mj / c["lhv"]) / c["rho"]
        
        conso_l_100.append(conso_litres)

    # --- RÉSULTATS ---
    idx = np.argmin(conso_l_100)
    best_kwh = tailles_kwh[idx]
    
    print(f"--- OPTIMISATION SHSE-M (PIRES CONDITIONS) ---")
    print(f"Carburant utilisé      : {c_nom}")
    print(f"Température            : {TEMP_EXTERIEURE}°C")
    print(f"Pente de référence     : {PENTE_MOYENNE*100}%")
    print(f"-----------------------------------------------")
    print(f"Capacité NOMINALE      : {best_kwh:.2f} kWh")
    print(f"Capacité RÉELLE (Hiver): {best_kwh*COEFF_PERTE_FROID*(1-RESERVE_SECURITE_SOC):.2f} kWh")
    print(f"Poids de la batterie   : {best_kwh/densite_pack:.1f} kg")
    print(f"Consommation estimée   : {conso_l_100[idx]:.2f} L/100km")

    # --- GRAPHIQUE ---
    plt.figure(figsize=(10, 6))
    plt.plot(tailles_kwh, conso_l_100, color='darkred', lw=2, label=f"Conso avec {c_nom}")
    plt.axvline(best_kwh, color='black', linestyle='--', label=f'Ratio Parfait: {best_kwh:.1f}kWh')
    plt.fill_between(tailles_kwh, conso_l_100, facecolor='red', alpha=0.1)
    
    plt.title(f"Optimisation Batterie : Cas Critique ({c_nom} + Froid + Pente)")
    plt.xlabel("Capacité Nominale Batterie (kWh)")
    plt.ylabel("Consommation (L/100km)")
    plt.grid(True, which='both', linestyle=':', alpha=0.5)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    simulateur_ratio_batterie_robuste()