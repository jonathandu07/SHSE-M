# backend\main.py
import sys
import os
import math

# Ajout du chemin racine pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.consistency.dimensionnement import calcul_puissance_vilebrequin
from backend.consistency.optimizer import ArchitectureOptimizer
from backend.definition_pieces import dimensionner_pieces_completes
from backend.system_generator import DriveChainGenerator

def dimensionner_systeme_shsem(puissance_traction_kw: float, charger_batterie: bool = True):
    """
    Calcule les besoins globaux et détermine l'architecture moteur optimale.
    Utilise le nouveau moteur de dimensionnement cohérent.
    """
    print(f"=== DIMENSIONNEMENT SYSTÈME SHSE-M ({puissance_traction_kw} kW) ===\n")

    # 1. BILAN DE PUISSANCE COHÉRENT
    ETA_INV = 0.97
    ETA_MOT = 0.92
    ETA_GEN = 0.95
    ETA_TRA = 0.98
    
    p_aux_w = 5000.0
    p_charge_bat_w = 20000.0 if charger_batterie else 0.0

    p_vilo_w = calcul_puissance_vilebrequin(
        puissance_traction_kw * 1000.0,
        p_charge_bat_w,
        p_aux_w,
        ETA_INV, ETA_MOT, ETA_GEN, ETA_TRA
    )
    
    p_dc_total = (puissance_traction_kw * 1000.0 / (ETA_MOT * ETA_INV)) + p_charge_bat_w + p_aux_w

    print(f"Puissance Traction (Roues): {puissance_traction_kw:.1f} kW")
    print(f"Puissance Bus DC Total: {p_dc_total/1000:.1f} kW")
    print(f">> BESOIN MOTEUR THERMIQUE (Vilo): {p_vilo_w/1000:.1f} kW\n")

    # 2. RÉSOLUTION ARCHITECTURALE STRICTE
    print("[Étape 2: Optimisation de l'Architecture]")
    optimizer = ArchitectureOptimizer(bore_max_mm=133.3, up_max_ms=16.0)
    pme_pa = 15e5 # 15 bars
    rpm = 3000.0
    
    results = optimizer.optimize(p_vilo_w, rpm, pme_pa)
    
    if not results:
        print("\nAucune configuration physique valide trouvée.")
        return None
        
    best = results[0] # Le meilleur score
    
    # Mapping vers l'ancien format pour compatibilité GUI
    config = {
        "N_cyl": best["n_cyl"],
        "Architecture": best["architecture"],
        "Score": best["score"],
        "Cout_Maint_Estime": best["cout_maint"],
        "Bore_mm": best["bore_mm"],
        "Stroke_mm": best["stroke_mm"],
        "RPM": rpm,
        "PME": pme_pa,
        "PME_bar": best["pme_bar"],
        "vd_tot_cc": best["vd_tot_cc"],
        "masse_totale_kg": best["masse_kg"], # Sera complété plus bas
        "L_max_m": best["vd_tot_cc"] / 5000.0,
        "W_max_m": 0.8
    }

    if config:
        print(f"\n[RÉSULTAT OPTIMAL]")
        print(f"Nombre de cylindres : {config['N_cyl']}")
        print(f"Architecture : {config['Architecture']}")
        print(f"Alésage : {config['Bore_mm']:.1f} mm")
        print(f"Course  : {config['Stroke_mm']:.1f} mm")
        print(f"Cylindrée Totale : {config['vd_tot_cc']:.1f} cc")
        
        # 3. DIMENSIONNEMENT COMPLET DES PIÈCES
        dimensionner_pieces_completes(
            puissance_cible_w=p_vilo_w,
            regime_tr_min=config['RPM'],
            n_cyl=config['N_cyl'],
            pression_max_pa=pme_pa * 6.0 # Pmax estimation simple
        )
        
        # 4. LOGIQUE COMPLÉMENTAIRE (Alt / Bat / Boîte)
        gen = DriveChainGenerator()
        gen.compute(puissance_traction_kw)
        
        config['drivetrain'] = gen.results
        
        # 5. MASSE TOTALE REELLE
        m_bat = float(gen.results['batterie']['masse_estimee'].split()[0])
        config['masse_totale_kg'] = m_bat + best["masse_kg"]
        
        return config
    
    return None

if __name__ == "__main__":
    p_in = 150.0
    if len(sys.argv) > 1:
        try: p_in = float(sys.argv[1])
        except ValueError: pass
            
    dimensionner_systeme_shsem(p_in)
