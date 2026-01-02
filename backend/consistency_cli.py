import sys
import os

# Ajout du path pour les imports locaux
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.consistency.dimensionnement import calcul_puissance_vilebrequin, calcul_cylindree_totale
from backend.consistency.optimizer import ArchitectureOptimizer

def run_coherence_analysis(p_traction=150.0, p_charge=20.0, p_aux=5.0, rpm=3000.0, pme_bar=15.0):
    print("="*60)
    print("      RAPPORT DE COHÉRENCE PHYSIQUE SHSE-M")
    print("="*60)
    
    # 1. BILAN DE PUISSANCE
    # ---------------------
    # Hypothèses de rendements
    ETA_INV = 0.97
    ETA_MOT = 0.92
    ETA_GEN = 0.95
    ETA_TRA = 0.98
    
    p_vilo_w = calcul_puissance_vilebrequin(
        p_traction * 1000, p_charge * 1000, p_aux * 1000,
        ETA_INV, ETA_MOT, ETA_GEN, ETA_TRA
    )
    
    print("\n[VÉRIFICATION CHAÎNE DE PUISSANCE]")
    print(f"1. Traction Roues : {p_traction} kW")
    print(f"2. Perte Elec (Mot+Inv): {p_traction * (1 - ETA_MOT*ETA_INV):.1f} kW")
    print(f"3. Bus DC (Traction) : {p_traction/(ETA_MOT*ETA_INV):.1f} kW")
    print(f"4. Surcharge (Batterie+Aux) : {p_charge+p_aux} kW")
    print(f"5. Total Bus DC : {(p_traction/(ETA_MOT*ETA_INV) + p_charge + p_aux):.1f} kW")
    print(f"6. Perte Gen/Meca (Alt+Trans): {p_vilo_w/1000 * (1 - ETA_GEN*ETA_TRA):.1f} kW")
    print(f"7. PUISSANCE VILEBREQUIN REQUISE : {p_vilo_w/1000:.1f} kW")
    
    # 2. CYLINDRÉE ET CYCLE
    # ---------------------
    pme_pa = pme_bar * 1e5
    vd_tot_m3 = calcul_cylindree_totale(p_vilo_w, pme_pa, rpm)
    
    print("\n[VÉRIFICATION CYCLE (4-TEMPS)]")
    print(f"Hypothèse: Régime stable {rpm} rpm | PME {pme_bar} bar")
    print(f"Formule: Vd = P_vilo / (PME * (RPM / 120))")
    print(f"Calcul: {p_vilo_w:.0f} / ({pme_pa:.0f} * {rpm/120:.1f})")
    print(f"CYLINDRÉE TOTALE : {vd_tot_m3*1e6:.1f} cc ({vd_tot_m3*1000:.2f} L)")
    
    # 3. OPTIMISATION ET CONTRAINTES
    # ------------------------------
    optimizer = ArchitectureOptimizer(bore_max_mm=133.3, up_max_ms=16.0)
    opt_results = optimizer.optimize(p_vilo_w, rpm, pme_pa)
    
    print("\n[ANALYSE COMPARATIVE N=2..16]")
    header = f"{'N':<3} | {'Arch':<4} | {'Bore':<6} | {'Stroke':<6} | {'Up':<5} | {'Score':<8} | {'Status'}"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    # On affiche tout pour la traçabilité (validés d'abord)
    for res in opt_results:
        status = "OK" if res["valide"] else "FAILED"
        print(f"{res['n_cyl']:<3} | {res['architecture']:<4} | {res['bore_mm']:<6.1f} | {res['stroke_mm']:<6.1f} | {res['piston_speed_ms']:<5.1f} | {res['score']:<8.1f} | {status}")
    
    # 4. RÉSULTAT FINAL
    # -----------------
    if opt_results:
        best = opt_results[0]
        print("\n" + "="*60)
        print("                 RÉCAPITULATIF FINAL")
        print("="*60)
        print(f"Nombre Cylindres   : {best['n_cyl']}")
        print(f"Architecture       : {best['architecture']}")
        print(f"Géométrie (B x S)  : {best['bore_mm']:.1f} x {best['stroke_mm']:.1f} mm")
        print(f"Cylindrée Totale   : {best['vd_tot_cc']:.1f} cc")
        print(f"Pression Effective : {best['pme_bar']:.1f} bar")
        print(f"Vitesse Piston     : {best['piston_speed_ms']:.1f} m/s")
        print(f"Cout Maint (Est)   : {best['cout_maint']:.0f} € / 20kh")
        print(f"Score Global       : {best['score']:.1f}")
        
    else:
        print("\n[ALERTE] Aucune configuration ne respecte les contraintes physiques !")

if __name__ == "__main__":
    run_coherence_analysis()
