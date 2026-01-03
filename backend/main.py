# backend/main.py
import sys
import os
import math

# Ajout du chemin racine pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.engineering_model import DimensioningEngine
from backend.definition_pieces import dimensionner_pieces_completes
from backend.system_generator import DriveChainGenerator

def dimensionner_systeme_shsem(puissance_traction_kw: float, charger_batterie: bool = True):
    """
    Calcule les besoins globaux et détermine l'architecture moteur optimale.
    Utilise le nouveau moteur de dimensionnement cohérent (Stirling Air).
    """
    print(f"=== DIMENSIONNEMENT SYSTÈME SHSE-M ({puissance_traction_kw} kW) ===\n")

    # 1. BILAN DE PUISSANCE
    # On garde la logique de chaine de traction pour savoir combien de kWe il faut
    ETA_INV = 0.97
    ETA_MOT = 0.92
    
    p_aux_w = 5000.0
    p_charge_bat_w = 20000.0 if charger_batterie else 0.0
    
    # Puissance Elec Totale demandée au Bus DC
    p_dc_total_w = (puissance_traction_kw * 1000.0 / (ETA_MOT * ETA_INV)) + p_charge_bat_w + p_aux_w
    p_elec_cible_kw = p_dc_total_w / 1000.0

    print(f"Puissance Traction (Roues): {puissance_traction_kw:.1f} kW")
    print(f"Puissance Bus DC Total: {p_elec_cible_kw:.1f} kW")
    
    # 2. APPEL AU NOUVEAU MOTEUR DE CALCUL (ENGINEERING MODEL)
    # Paramètres Hardcodés du "Scénario A" validé par l'audit
    TARGET_RPM = 1000.0
    TARGET_P_MEAN = 20.0 # bars
    TARGET_N_CYL = 4
    
    # Instanciation du moteur physique
    eng = DimensioningEngine(
        p_elec_kw=p_elec_cible_kw,
        rpm=TARGET_RPM,
        p_mean_bar=TARGET_P_MEAN,
        n_cyl=TARGET_N_CYL,
        bn=0.15 # Air Robuste
    )
    
    print(f">> BESOIN MOTEUR THERMIQUE (Vilo): {eng.p_meca_needed_kw:.1f} kW")
    print("\n[RÉSULTATS DU MODÈLE PHYSIQUE STIRLING]")
    print(f"Architecture : {eng.n_cyl} Cylindres Gamma")
    print(f"Cylindrée Totale : {eng.vd_total_liters:.2f} Litres")
    print(f"Alésage : {eng.bore_mm:.1f} mm")
    print(f"Course  : {eng.stroke_mm:.1f} mm")
    print(f"Pression Moyenne : {eng.p_mean_bar} bar")
    print(f"Couple Moyen : {eng.torque_mean_nm:.1f} Nm")

    # 3. MAPPING VERS LE FORMAT ATTENDU PAR LE GUI
    # On adapte les clés pour que l'interface s'y retrouve
    config = {
        "N_cyl": eng.n_cyl,
        "Architecture": f"L{eng.n_cyl}", # Ex: L4
        "Score": 100.0, # Dummy
        "Cout_Maint_Estime": 1500.0,
        "Bore_mm": eng.bore_mm,
        "Stroke_mm": eng.stroke_mm,
        "RPM": eng.rpm,
        "PME": eng.p_mean_pa,
        "PME_bar": eng.p_mean_bar,
        "vd_tot_cc": eng.vd_total_liters * 1000.0,
        "masse_totale_kg": 250.0 + (eng.vd_total_liters * 20.0), # Estimation grossière masse
        "L_max_m": eng.bore_m * 1.5 * eng.n_cyl + 0.3,
        "W_max_m": 0.6
    }
    
    # 4. DIMENSIONNEMENT COMPLET DES PIÈCES (ENVOI DES BONS PARAMÈTRES)
    # On passe les "vraies" valeurs physiques
    dimensionner_pieces_completes(
        puissance_cible_w=eng.p_meca_needed_w,
        regime_tr_min=eng.rpm,
        n_cyl=eng.n_cyl,
        pression_max_pa=eng.p_safety_bar * 1e5 # Pression de sécurité pour le dimensionnement mecanique
    )
    
    # 5. LOGIQUE COMPLÉMENTAIRE
    gen = DriveChainGenerator()
    gen.compute(puissance_traction_kw)
    config['drivetrain'] = gen.results
    
    m_bat = float(gen.results['batterie']['masse_estimee'].split()[0])
    config['masse_totale_kg'] += m_bat
    
    return config

if __name__ == "__main__":
    p_in = 40.0 # 40kW Traction par défaut
    if len(sys.argv) > 1:
        try: p_in = float(sys.argv[1])
        except ValueError: pass
            
    dimensionner_systeme_shsem(p_in)
