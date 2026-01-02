import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from backend.modules.architecture.calcul_cylindree_totale import calcul_cylindree_totale_requise
from backend.modules.architecture.calcul_cylindree_admissible import calcul_bore_max_admissible, calcul_cylindree_unit_max
from backend.modules.architecture.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min
from backend.modules.architecture.choix_architecture_optimale import choix_architecture_optimale, evaluer_architecture
from backend.modules.architecture.calcul_cout_maintenance_archard import calcul_cout_maintenance_estime

def resoudre_architecture_globale(
    puissance_cible_w: float,
    regime_tr_min: float,
    pme_pa: float,
    vitesse_piston_max_ms: float,
    L_max_m: float,
    W_max_m: float,
    horizon_usage_h: float = 20000.0
) -> dict:
    """
    Résout le problème d'optimisation global décrit dans 'formules_architecture.md'.
    Détermine N_cylindres et Architecture optimaux minimisant le coût Packaging + Maintenance.
    """
    print("=== RÉSOLUTION GLOBALE ARCHITECTURE SHSE-M ===")
    
    # 1. Cylindrée Totale
    # 4 temps (f = N/120)
    freq_hz = regime_tr_min / 120.0
    cyl_tot_m3 = calcul_cylindree_totale_requise(puissance_cible_w, pme_pa, freq_hz, rendement_mecanique=0.85)
    print(f"Cylindrée Totale Requise: {cyl_tot_m3*1e6:.1f} cc")
    
    # 2. Bornes Unitaires
    ratio_sb_max = 1.2
    bore_max_m = calcul_bore_max_admissible(vitesse_piston_max_ms, regime_tr_min, ratio_sb_max)
    cyl_unit_max_m3 = calcul_cylindree_unit_max(bore_max_m, ratio_sb_max)
    print(f"Cylindrée Unitaire Max: {cyl_unit_max_m3*1e6:.1f} cc (Alésage max {bore_max_m*1000:.1f}mm)")
    
    # 3. N_cyl Min
    n_min = calcul_nombre_cylindres_min(cyl_tot_m3, cyl_unit_max_m3)
    if n_min > 24:
        print("ATTENTION: N_min > 24. Paramètres irréalistes.")
        return {}
    print(f"Nombre Cylindres Min (Physique): {n_min}")
    
    # 4. Optimisation Globale
    # On itère N de n_min à N_max
    n_max_explore = max(16, n_min + 4)
    best_global_score = 999999.0
    best_config = {}
    
    for n in range(n_min, n_max_explore + 1):
        # Pour ce N, quelle est la charge unitaire ?
        # Pression reste PME, mais force sur le piston change si on réduit l'alésage ?
        # Non, V_cyl = V_tot / N. Donc B diminue.
        # V_u = V_tot / N
        v_u = cyl_tot_m3 / n
        # B = (4 * V_u / (pi * ratio))^(1/3)
        bore_actuel = ((4 * v_u) / (math.pi * 1.0)) ** (1/3) # Ratio ~ 1.0 moyen
        surface_piston = math.pi * (bore_actuel**2) / 4
        
        # Charge Moyenne ~ PME * Surface
        # Charge Max ~ Pmax * Surface (Pmax ~ 10 * PME)
        charge_moy_n = pme_pa * surface_piston
        
        # Référence (Base 1 cyl ou Base n_min)
        # Pour coût maintenance, il faut une Ref. Disons Ref = N_min
        v_u_ref = cyl_tot_m3 / n_min
        bore_ref = ((4 * v_u_ref) / (math.pi * 1.0)) ** (1/3)
        charge_ref_n = pme_pa * (math.pi * bore_ref**2 / 4)
        
        # Coût Maintenance
        cout_maint = calcul_cout_maintenance_estime(
            duree_usage_h=horizon_usage_h,
            duree_vie_joint_base_h=5000.0, # Ref 5000h
            charge_nominale_n=charge_ref_n,
            charge_actuelle_n=charge_moy_n,
            nb_joints_base=n_min * 3, # Segments + Etanchéité
            nb_joints_actuel=n * 3,
            cout_inter_eur=2000.0
        )
        
        # Choix Architecture
        best_arch_for_n = choix_architecture_optimale(n, L_max_m, W_max_m, cout_maint)
        
        if best_arch_for_n != "Inconnue":
             # Recalcul score exact
             score, valide = evaluer_architecture(best_arch_for_n, n, L_max_m, W_max_m, cout_maint)
             
             print(f"N={n} -> Arch={best_arch_for_n} | Maint={cout_maint:.0f}€ | Score={score:.2f}")
             
             if score < best_global_score:
                 best_global_score = score
                 best_config = {
                     "N_cyl": n,
                     "Architecture": best_arch_for_n,
                     "Score": score,
                     "Cout_Maint_Estime": cout_maint,
                     "Bore_mm": bore_actuel*1000,
                     "RPM": regime_tr_min,
                     "PME": pme_pa
                 }
                 
    print("\n=== RÉSULTAT OPTIMAL ===")
    print(best_config)
    return best_config

if __name__ == "__main__":
    # Test nominal SHSE-M 150kW
    resoudre_architecture_globale(
        puissance_cible_w=150000.0,
        regime_tr_min=4500.0,
        pme_pa=12e5, # 12 bars PME
        vitesse_piston_max_ms=25.0,
        L_max_m=1.2,
        W_max_m=0.8
    )
