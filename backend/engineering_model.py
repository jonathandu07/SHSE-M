import math
import json
import os

# =============================================================================
# GLOBAL ENGINEERING CONSTANTS
# =============================================================================
MATERIALS = {
    "310S": {"sigma_yield": 210, "sigma_uts": 550, "sigma_creep_650": 40, "rho": 7900, "E": 200e3}, # MPa
    "304L": {"sigma_yield": 190, "sigma_uts": 500, "rho": 7900, "E": 193e3},
    "42CrMo4": {"sigma_yield": 900, "sigma_uts": 1100, "rho": 7850, "E": 210e3},
    "Alu_7075": {"sigma_yield": 450, "sigma_uts": 550, "rho": 2800, "E": 71e3},
    "CastIron_GL": {"sigma_yield": 250, "sigma_compression": 800, "rho": 7200, "E": 110e3}
}

class DimensioningEngine:
    def __init__(self, p_elec_kw=40, rpm=1000, p_mean_bar=20, n_cyl=4, bn=0.15):
        self.p_elec_kw = p_elec_kw
        self.rpm = rpm
        self.p_mean_bar = p_mean_bar
        self.n_cyl = n_cyl
        self.bn = bn
        
        # System Constants
        self.eff_elec = 0.90
        self.eff_mech = 0.92
        self.p_safety_bar = p_mean_bar * 1.5 # 50% surge safety
        self.t_hot = 650 # °C
        self.t_cold = 60 # °C
        
        self._calculate_global()

    def _calculate_global(self):
        # 1. Power Chain
        self.p_meca_needed_kw = self.p_elec_kw / self.eff_elec
        self.p_meca_needed_w = self.p_meca_needed_kw * 1000.0
        
        # 2. Beale Dimensioning
        self.freq_hz = self.rpm / 60.0
        self.p_mean_pa = self.p_mean_bar * 1e5
        
        # V = P / (Bn * Pm * f)
        self.vd_total_m3 = self.p_meca_needed_w / (self.bn * self.p_mean_pa * self.freq_hz)
        self.vd_total_liters = self.vd_total_m3 * 1000.0
        self.vd_cyl_l = self.vd_total_liters / self.n_cyl
        self.vd_cyl_m3 = self.vd_cyl_l / 1000.0
        
        # 3. Geometry (Square engine assumption for robustness)
        # pi/4 * B^2 * S = V
        # Let B = S => pi/4 * B^3 = V => B = (4V/pi)^(1/3)
        self.bore_m = (4 * self.vd_cyl_m3 / math.pi) ** (1.0/3.0)
        self.stroke_m = self.bore_m
        
        self.bore_mm = self.bore_m * 1000
        self.stroke_mm = self.stroke_m * 1000
        
        # 4. Velocities & Forces
        self.v_piston_mean = 2 * self.stroke_m * self.freq_hz
        self.omega = 2 * math.pi * self.freq_hz
        self.torque_mean_nm = self.p_meca_needed_w / self.omega
        
        # Max Gas Force (Approx P_max ~ 1.3 * P_mean) for rod sizing
        self.p_max_bar = self.p_mean_bar * 1.3
        self.force_gas_max_n = (self.p_max_bar * 1e5) * (math.pi * (self.bore_m/2)**2)

    def generate_report_markdown(self):
        return f"""
# GLOBAL PARAMETRIC MODEL
**Target:** {self.p_elec_kw} kWe | **RPM:** {self.rpm} | **P_mean:** {self.p_mean_bar} bar

## 1. System Inputs & Hypotheses
*   **Beale Number (Bn):** {self.bn} (Robust Air)
*   **Electrical Efficiency:** {self.eff_elec*100}%
*   **Required Mech Power:** {self.p_meca_needed_kw:.2f} kW
*   **Safety Pressure:** {self.p_safety_bar} bar

## 2. Calculated Dimensions
*   **Total Displacement:** {self.vd_total_liters:.2f} L
*   **Cylinders:** {self.n_cyl}
*   **Unit Displacement:** {self.vd_cyl_l:.2f} L
*   **Bore:** {self.bore_mm:.1f} mm  |  **Stroke:** {self.stroke_mm:.1f} mm
*   **Piston Speed:** {self.v_piston_mean:.2f} m/s
*   **Mean Torque:** {self.torque_mean_nm:.1f} Nm
*   **Max Gas Force (Rod load):** {self.force_gas_max_n:.0f} N
"""

# =============================================================================
# COMPONENT CLASSES (HEADWORKS GENERATORS)
# =============================================================================

class ComponentPiece:
    def __init__(self, engine: DimensioningEngine):
        self.e = engine
        self.name = "Generic"
        self.ref = "AAA-000"
        self.data = {}
    
    def calculate(self):
        pass
        
    def render_markdown(self):
        return ""

class ConRod(ComponentPiece):
    def __init__(self, engine):
        super().__init__(engine)
        self.name = "Bielle de Puissance"
        self.ref = "MEC-001"
        
    def calculate(self):
        # Geometry Guidelines
        # L_entraxe approx 2.0 to 2.5 * Stroke
        self.l_entraxe = 2.2 * self.e.stroke_mm
        
        # Buckling Load (Flambage)
        # F_crit = (pi^2 * E * I) / L_eff^2
        # We need F_crit > F_gas_max * SafetyFactor
        sf_buckling = 4.0
        mat = MATERIALS["42CrMo4"]
        
        f_target = self.e.force_gas_max_n * sf_buckling
        # Assume H-section or rectangular. Let's simplify to solid rectangular for robust sizing.
        # I = b*h^3 / 12. Assume h = 2b. I = b*(2b)^3/12 = 8b^4/12 = 2/3 b^4
        # L_eff = L_entraxe (pinned-pinned)
        l_eff_m = self.l_entraxe / 1000.0
        
        # b^4 = (F_target * L^2 * 12) / (pi^2 * E * 8) ?? No
        # I_req = (F_target * L^2) / (pi^2 * E)
        i_req = (f_target * l_eff_m**2) / (math.pi**2 * mat["E"]*1e6)
        
        # 2/3 b^4 = I_req => b = (1.5 * I_req)^(1/4)
        b_m = (1.5 * i_req)**0.25
        h_m = 2.0 * b_m
        
        self.thickness = b_m * 1000.0
        self.width_small = h_m * 1000.0 # At smallest section
        
        # Head/Pied sizes
        self.d_pied = self.e.bore_mm * 0.25 # Axe piston approx 25% bore
        self.d_tete = self.e.stroke_mm * 0.60 # Maneton often 60% stroke for stiffness
        
        # Stress check (Compression simple) sigma = F/S
        area = self.thickness * self.width_small
        sigma_comp = self.e.force_gas_max_n / (area * 1e-6) # MPa is N/mm2 ? No N/m2 -> Pa
        # N / mm2 = MPa
        sigma_comp_mpa = self.e.force_gas_max_n / area
        
        self.data = {
            "L_entraxe_mm": self.l_entraxe,
            "Section_mm": f"{self.thickness:.1f} x {self.width_small:.1f}",
            "Force_Max_N": self.e.force_gas_max_n,
            "Buckling_SF": sf_buckling,
            "Stress_Comp_MPa": sigma_comp_mpa,
            "Yield_MPa": mat["sigma_yield"],
            "Material": "42CrMo4 (Acier Trempé Revenu)"
        }

    def render_markdown(self):
        return f"""
## FICHE PIÈCE : {self.name} ({self.ref})

### 1. Données d'Entrée
*   **Effort Max (Gaz):** {self.data['Force_Max_N']:.0f} N ({self.data['Force_Max_N']/9.81:.0f} kgf)
*   **Longueur (L):** {self.data['L_entraxe_mm']:.1f} mm (Ratio L/C = 2.2)
*   **Matériau:** {self.data['Material']}

### 2. Croquis Headworks (ASCII)
```text
      ( o )  <-- Pied de bielle (D_axe = {self.d_pied:.1f} H7)
        |
        |    Section Corps (I-Beam ou Rect)
        |    Épaisseur: {self.thickness:.1f} mm
        |    Largeur:   {self.width_small:.1f} mm
        |
      ( O )  <-- Tête de bielle (D_maneton = {self.d_tete:.1f})
```

### 3. Calculs de Validation (Détails)
**A. Flambage (Buckling - Euler)**
*   Hypothèse : Bi-articulée (k=1), Section rectangulaire pleine.
*   Charge Critique Visée (SF={self.data['Buckling_SF']}) : {self.data['Force_Max_N']*self.data['Buckling_SF']:.0f} N
*   Inertie Requise I : {((self.data['Force_Max_N']*self.data['Buckling_SF'] * (self.data['L_entraxe_mm']/1000)**2) / (math.pi**2 * 210e9)):.2e} m4
*   **Résultat :** Section {self.data['Section_mm']} valide.

**B. Contrainte en Compression**
*   $\sigma = F / S$
*   $\sigma = {self.data['Force_Max_N']:.0f} / ({self.thickness:.1f} \\times {self.width_small:.1f})$
*   **$\sigma$ = {self.data['Stress_Comp_MPa']:.1f} MPa**
*   Limite Elastique Re = {self.data['Yield_MPa']} MPa
*   **Marge Sécurité (Re/sigma) :** {self.data['Yield_MPa']/self.data['Stress_Comp_MPa']:.1f}
"""

class PressureCrankcase(ComponentPiece):
    def __init__(self, engine):
        super().__init__(engine)
        self.name = "Carter Sous Pression"
        self.ref = "CAR-001"
        
    def calculate(self):
        # Hoop Stress cylinder
        # t = P*D / (2*Sigma)
        # D approx bore + water jacket + clearance = Bore + 50mm
        d_internal = self.e.bore_mm * 1.5 # Crankcase is bigger than bore to fit crank
        p_design_mpa = self.e.p_safety_bar / 10.0
        
        mat = MATERIALS["CastIron_GL"] # Fonte grise ou Nodulaire
        sf = 3.0 # High safety for cast parts
        sigma_allow = mat["sigma_yield"] / sf
        
        t_min = (p_design_mpa * d_internal) / (2 * sigma_allow)
        # Casting limit often 5-6mm anyway
        self.wall_thick = max(t_min, 6.0)
        
        # Base dimensions
        self.length = self.e.n_cyl * (self.e.bore_mm * 1.5) # Espace entre cylindres
        self.width = d_internal + 40
        self.height = self.e.stroke_mm * 2.5
        
        self.data = {
            "Internal_Pressure_Bar": self.e.p_safety_bar,
            "Internal_Dia_mm": d_internal,
            "Wall_Thickness_mm": self.wall_thick,
            "Material": "Fonte GL (Grey Cast Iron)",
            "Hoop_Stress_MPa": (p_design_mpa * d_internal) / (2 * self.wall_thick)
        }
        
    def render_markdown(self):
        return f"""
## FICHE PIÈCE : {self.name} ({self.ref})

### 1. Données d'Entrée
*   **Pression Design:** {self.data['Internal_Pressure_Bar']} bar (Sécurité incluse)
*   **Dimensions Globales:** {self.length:.0f} x {self.width:.0f} x {self.height:.0f} mm
*   **Matériau:** {self.data['Material']}

### 2. Croquis Headworks (ASCII)
```text
   _______________________
  /                       \\  <-- Parois Épaisseur Min: {self.data['Wall_Thickness_mm']:.1f} mm
 |   ( Cy1 )   ( Cy2 )    |
 |                        |
 |      CRANK SPACE       |  <-- Volume interne P = {self.e.p_mean_bar} bar
 |________________________|
```

### 3. Calculs (RDM)
**A. Résistance Pression (Hoop Stress)**
*   Formule Cylindre Mince : $\sigma = \frac{{P \cdot D}}{{2 \cdot t}}$
*   $P = {self.data['Internal_Pressure_Bar']/10:.1f} MPa$, $D = {self.data['Internal_Dia_mm']:.1f} mm$, $t = {self.data['Wall_Thickness_mm']:.1f} mm$
*   **Contrainte $\sigma$ :** {self.data['Hoop_Stress_MPa']:.1f} MPa
*   **Limite Élastique (Fonte) :** ~250 MPa
*   **Facteur Sécurité :** {250 / self.data['Hoop_Stress_MPa']:.1f} (> 3.0 OK)
"""

class Crankshaft(ComponentPiece):
    def __init__(self, engine):
        super().__init__(engine)
        self.name = "Vilebrequin"
        self.ref = "MEC-002"

    def calculate(self):
        # Torsion & Flexion combinée
        # D_journal approx 0.6 * Stroke (Robust standard)
        self.d_journal = self.e.stroke_mm * 0.65
        self.d_maneton = self.e.stroke_mm * 0.60
        
        # Torsion Max T = P / w
        torque_max = self.e.torque_mean_nm * 2.5 # Peak cyclic torque
        
        # Contrainte Torsion: tau = 16 * T / (pi * d^3)
        tau_torsion = (16 * torque_max) / (math.pi * (self.d_journal/1000)**3)
        
        # Matériau
        mat = MATERIALS["42CrMo4"]
        
        self.data = {
            "D_Journal_mm": self.d_journal,
            "D_Maneton_mm": self.d_maneton,
            "Torque_Peak_Nm": torque_max,
            "Stress_Torsion_MPa": tau_torsion / 1e6,
            "Material": "42CrMo4 (Forgé)"
        }

    def render_markdown(self):
        return f"""
## FICHE PIÈCE : {self.name} ({self.ref})

### 1. Données d'Entrée
*   **Diamètre Portée (Tourillon):** {self.data['D_Journal_mm']:.1f} mm
*   **Diamètre Maneton:** {self.data['D_Maneton_mm']:.1f} mm
*   **Couple Crête:** {self.data['Torque_Peak_Nm']:.0f} Nm

### 2. Croquis Headworks (ASCII)
```text
      |       |
  (===|   M   |===)  <-- Maneton Ø{self.data['D_Maneton_mm']:.1f}
      |   |   |
      |===J===|      <-- Tourillon Ø{self.data['D_Journal_mm']:.1f}
```

### 3. Calculs (RDM)
**A. Torsion**
*   $\tau = \\frac{{16 \cdot T}}{{\pi \cdot d^3}}$
*   $\tau = {self.data['Stress_Torsion_MPa']:.1f}$ MPa
*   Limite Elastique (Cisaillement $\approx 0.58 \cdot Re$) : {900*0.58:.0f} MPa
*   **Facteur Sécurité:** {(900*0.58)/self.data['Stress_Torsion_MPa']:.1f}
"""

class Piston(ComponentPiece):
    def __init__(self, engine):
        super().__init__(engine)
        self.name = "Piston De Puissance"
        self.ref = "MEC-010"

    def calculate(self):
        # Pression contact Axe
        # F_gas_max sur surface projetée axe (D_axe * L_portée)
        d_axe = self.e.bore_mm * 0.25
        l_portee = d_axe * 1.5
        
        area_proj = (d_axe/1000) * (l_portee/1000)
        p_specifique_mpa = (self.e.force_gas_max_n / area_proj) / 1e6
        
        # Étanchéité
        # Segments PTFE chargés
        
        self.data = {
            "Diameter_mm": self.e.bore_mm,
            "Height_mm": self.e.bore_mm * 0.8,
            "Pin_Diameter_mm": d_axe,
            "Bearing_Pressure_MPa": p_specifique_mpa,
            "Material": "Alu 7075-T6"
        }

    def render_markdown(self):
        return f"""
## FICHE PIÈCE : {self.name} ({self.ref})

### 1. Données d'Entrée
*   **Diamètre:** {self.data['Diameter_mm']:.1f} mm (-0.05 / -0.10 pour dilatation)
*   **Axe Piston:** Ø{self.data['Pin_Diameter_mm']:.1f} mm
*   **Pression Spécifique Axe:** {self.data['Bearing_Pressure_MPa']:.1f} MPa (Max admissible bague bronze ~30-50 MPa)

### 2. Croquis
```text
      ___________  <-- Tête Plate
     |   =====   | <-- Gorges Segments (3x)
     |           |
     |  ( O )    | <-- Alésage Axe Ø{self.data['Pin_Diameter_mm']:.1f}
     |___________|
```
"""

class HeaterHead(ComponentPiece):
    def __init__(self, engine):
        super().__init__(engine)
        self.name = "Échangeur Chaud (Heater Head)"
        self.ref = "THE-001"

    def calculate(self):
        # Hoop stress tubes
        # P = 30 bar, T = 650°C
        # Material 310S
        
        # Tube Dimensions
        # Faisceau tubulaire pour surface exchange
        # N tubes of diam 10mm ?
        d_tube_ext = 12.0
        p_des = self.e.p_safety_bar
        sig_hot = MATERIALS["310S"]["sigma_creep_650"] # 40 MPa
        
        # t = P*D / (2*Sig + P) approx
        t_req = (p_des/10.0 * d_tube_ext) / (2 * sig_hot)
        t_final = max(t_req, 1.5) # Min manufacturing
        
        self.data = {
            "Tube_OD_mm": d_tube_ext,
            "Wall_Thick_mm": t_final,
            "Nb_Tubes": 40, # Estimation pour surface
            "Material": "Inox 310S (Réfractaire)"
        }

    def render_markdown(self):
        return f"""
## FICHE PIÈCE : {self.name} ({self.ref})

### 1. Données
*   **Température:** 650°C
*   **Pression:** {self.e.p_safety_bar} bar
*   **Matériau:** {self.data['Material']}

### 2. Dimensionnement Tubes
*   Tube Ø{self.data['Tube_OD_mm']} mm x {self.data['Wall_Thick_mm']:.2f} mm
*   Critère Rupture (Creep): {MATERIALS['310S']['sigma_creep_650']} MPa
"""

# =============================================================================
# MAIN SCRIPT
# =============================================================================

def generate_full_engineering_package(power_kw=40, rpm=1000, p_bar=20):
    eng = DimensioningEngine(p_elec_kw=power_kw, rpm=rpm, p_mean_bar=p_bar)
    
    # Generate Global Report
    report = eng.generate_report_markdown()
    
    # Generate Pieces
    pieces = [
        ConRod(eng), 
        PressureCrankcase(eng),
        Crankshaft(eng),
        Piston(eng),
        HeaterHead(eng)
    ]
    
    for p in pieces:
        p.calculate()
        report += "\n---\n" + p.render_markdown()
        
    return report

if __name__ == "__main__":
    # Generate Baseline 40kW Report
    final_rpt = generate_full_engineering_package(40, 1000, 20)
    
    # Output to stdout/file
    print(final_rpt)
    with open("shse_engineering_pack_40kwe.md", "w", encoding="utf-8") as f:
        f.write(final_rpt)
