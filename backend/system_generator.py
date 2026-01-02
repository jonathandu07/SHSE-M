import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Imports valides (Vérifiés)
from backend.modules.alternateur.calcul_couple_alternateur import calcul_couple_alternateur
# calcul_dimensionnement_batterie.py contient: calcul_capacite_totale_batterie, calcul_poids_batterie
from backend.modules.batterie.calcul_dimensionnement_batterie import calcul_poids_batterie
from backend.modules.boite_crabots.calcul_force_pignon import calcul_force_tangentielle

class DriveChainGenerator:
    """
    Génère une configuration optimale Alternateur / Batterie / Boîte
    à partir d'une simple puissance cible.
    """
    def __init__(self, voltage_bus=400.0, autonomy_hours=4.0):
        self.voltage = voltage_bus
        self.autonomy = autonomy_hours
        self.results = {}

    def compute(self, target_power_kw: float):
        print(f"--- GÉNÉRATION SYSTÈME POUR {target_power_kw} kW ---\n")
        
        target_power_w = target_power_kw * 1000.0
        
        # 1. ALTERNATEUR
        # Hypothèse: cos(phi)=0.9
        courant_phase_a = target_power_w / (math.sqrt(3) * self.voltage * 0.9)
        
        regime_alt_rpm = 3000.0
        omega_alt = (2 * math.pi * regime_alt_rpm) / 60
        
        # Calcul couple
        couple_alt_nm = calcul_couple_alternateur(target_power_w, 0.95, omega_alt)
        
        self.results['alternateur'] = {
            'puissance_nominale': f"{target_power_kw} kW",
            'tension_bus': f"{self.voltage} V",
            'courant_phase': f"{courant_phase_a:.1f} A",
            'couple_mecanique_requis': f"{couple_alt_nm:.1f} N.m (@{regime_alt_rpm} rpm)",
            'rendement_estime': "95%"
        }

        # 2. BATTERIE
        energie_utile_kwh = (target_power_kw * 0.3) * self.autonomy
        capacite_ah = (energie_utile_kwh * 1000) / self.voltage
        
        # Densité standard Li-Ion pack: 0.160 kWh/kg
        masse_kg = calcul_poids_batterie(energie_utile_kwh, 0.160)
        
        self.results['batterie'] = {
            'autonomie_cible': f"{self.autonomy} h (Usage mixte 30%)",
            'energie_embarquee': f"{energie_utile_kwh:.1f} kWh",
            'capacite_pack': f"{capacite_ah:.1f} Ah",
            'masse_estimee': f"{masse_kg:.0f} kg",
            'tension': f"{self.voltage} V"
        }

        # 3. BOITE DE VITESSE
        # P_max traction
        couple_traction_nom_nm = target_power_w / omega_alt
        couple_traction_max_nm = couple_traction_nom_nm * 2.5 
        
        # Diamètre Arbre (Torsion) : d = (16 T / (pi * tau))^(1/3)
        tau_adm = 300e6
        diam_arbre_m = ((16 * couple_traction_max_nm) / (math.pi * tau_adm)) ** (1/3)
        
        # Force sur dent (Pignon D=100mm)
        d_pignon = 0.1
        force_dent_n = calcul_force_tangentielle(couple_traction_max_nm, d_pignon)
        
        # Estimation module
        module_estime = math.ceil(2.0 * (force_dent_n/15000)) + 1
        
        self.results['boite_crabots'] = {
            'couple_entree_max': f"{couple_traction_max_nm:.0f} N.m",
            'diametre_arbre_min': f"{diam_arbre_m*1000:.1f} mm",
            'force_sur_dent_max': f"{force_dent_n/1000:.1f} kN (@Dp=100mm)",
            'module_denture_estime': f"Module {module_estime}"
        }

    def print_report(self):
        print("\n" + "="*50)
        print("   RAPPORT DE GÉNÉRATION AUTOMATIQUE (SYSTEME)   ")
        print("="*50)
        
        for component, specs in self.results.items():
            print(f"\n>> {component.upper()}")
            for k, v in specs.items():
                print(f"   - {k:<25} : {v}")
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            p_kw = float(sys.argv[1])
        except ValueError:
            p_kw = 150.0
    else:
        p_kw = 150.0 # Default
        
    gen = DriveChainGenerator()
    gen.compute(p_kw)
    gen.print_report()
