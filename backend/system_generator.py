import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Imports valides
from backend.modules.alternateur.calcul_couple_alternateur import calcul_couple_alternateur
from backend.modules.batterie.calcul_dimensionnement_batterie import calcul_masse_batterie
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
        # I = P / (sqrt(3) * U * cosphi) -> Inversion locale de P = sqrt(3)UlIcosphi
        facteur_puissance = 0.9
        courant_phase_a = target_power_w / (math.sqrt(3) * self.voltage * facteur_puissance)
        
        regime_alt_rpm = 3000.0
        omega_alt = (2 * math.pi * regime_alt_rpm) / 60
        
        # Calcul module
        couple_alt_nm = calcul_couple_alternateur(target_power_w, 0.95, omega_alt)
        
        self.results['alternateur'] = {
            'puissance_nominale': f"{target_power_kw} kW",
            'tension_bus': f"{self.voltage} V",
            'courant_phase': f"{courant_phase_a:.1f} A",
            'couple_mecanique_requis': f"{couple_alt_nm:.1f} N.m (@{regime_alt_rpm} rpm)",
            'rendement_estime': "95%"
        }

        # 2. BATTERIE
        # E = P_moy * t
        energie_utile_kwh = (target_power_kw * 0.3) * self.autonomy
        
        capacite_ah = (energie_utile_kwh * 1000) / self.voltage
        
        # Module batterie existant
        masse_kg = calcul_masse_batterie(energie_utile_kwh * 1000, 160.0)
        
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
        
        # RDM Inversée : d = (16 T / (pi * tau))^(1/3)
        tau_adm = 300e6
        diam_arbre_m = ((16 * couple_traction_max_nm) / (math.pi * tau_adm)) ** (1/3)
        
        # Module Boite existant
        d_pignon = 0.1
        force_dent_n = calcul_force_tangentielle(couple_traction_max_nm, d_pignon)
        
        # Estimation module engrenage (Empirique m = 2.4 * sqrt(F/k) ?)
        # Règle simple Lewis inversée m >= ... 
        # On garde l'estimateur simple
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
