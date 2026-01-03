
import math

def calculate_stirling_params(p_elec_target_kw, rpm, p_mean_bar, bn=0.15, n_cyl=4):
    # Constants & Assumptions
    EFF_ELEC = 0.90  # Efficiency of alternator + transmission
    p_mech_target_kw = p_elec_target_kw / EFF_ELEC
    p_mech_target_w = p_mech_target_kw * 1000.0
    
    freq_hz = rpm / 60.0
    p_mean_pa = p_mean_bar * 1e5
    
    # Beale Formula: P_mech = Bn * P_mean * V_swept * f
    # V_swept = P_mech / (Bn * P_mean * f)
    v_swept_total_m3 = p_mech_target_w / (bn * p_mean_pa * freq_hz)
    v_swept_total_liters = v_swept_total_m3 * 1000.0
    
    # Per Cylinder
    v_cyl_l = v_swept_total_liters / n_cyl
    v_cyl_m3 = v_swept_total_m3 / n_cyl
    
    # Dimensions (Assuming near square B/S ratio ~1.0 to 1.1)
    # V = pi * (B/2)^2 * S
    # Let S = 1.0 * B
    # V = pi/4 * B^3
    # B = (4*V / pi)^(1/3)
    bore_m = (4 * v_cyl_m3 / math.pi) ** (1.0/3.0)
    stroke_m = bore_m # Square engine
    
    bore_mm = bore_m * 1000.0
    stroke_mm = stroke_m * 1000.0
    
    # Piston Speed
    v_mps = 2 * stroke_m * freq_hz
    
    # Torque
    # P = C * w
    omega = 2 * math.pi * freq_hz
    torque_total_nm = p_mech_target_w / omega
    
    return {
        "P_elec_kW": p_elec_target_kw,
        "P_mech_kW": round(p_mech_target_kw, 2),
        "RPM": rpm,
        "P_mean_bar": p_mean_bar,
        "V_total_L": round(v_swept_total_liters, 2),
        "N_cyl": n_cyl,
        "V_cyl_L": round(v_cyl_l, 2),
        "Bore_mm": round(bore_mm, 1),
        "Stroke_mm": round(stroke_mm, 1),
        "V_mps": round(v_mps, 2),
        "Torque_Nm": round(torque_total_nm, 1)
    }

# Scenarios to Calculate
power_targets = [10, 20, 40, 60, 100] # kWe
rpms = [1000, 1500]
pressures = [20, 30] # bar

print("| P_elec (kWe) | RPM | P_mean (bar) | V_tot (L) | N_cyl | V/cyl (L) | Bore (mm) | Stroke (mm) | V_pist (m/s) | Torque (Nm) |")
print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

architectures = {
    10: 2, # 2 cyl for small pow
    20: 4, 
    40: 4,
    60: 4, # Maybe 6? keep 4 for comparison
    100: 6 # 6 cyl for high pow
}

for p_kw in power_targets:
    for r in rpms:
        for p_bar in pressures:
            n = architectures.get(p_kw, 4)
            # Adjust N_cyl for very large displacements to keep bore reasonable? 
            # For this table, let's stick to simple logic or overrides.
            if p_kw >= 60 and p_bar == 20: n = 6 # High volume needed
            if p_kw >= 100: n = 8
            
            res = calculate_stirling_params(p_kw, r, p_bar, bn=0.15, n_cyl=n)
            
            print(f"| {res['P_elec_kW']} | {res['RPM']} | {res['P_mean_bar']} | **{res['V_total_L']}** | {res['N_cyl']} | {res['V_cyl_L']} | {res['Bore_mm']} | {res['Stroke_mm']} | {res['V_mps']} | {res['Torque_Nm']} |")

print("\n\n")

# hoop stress calc function
def hoop_stress_thick(p_bar, safety_factor, diameter_mm, material_sigma_mpa):
    p_mpa = p_bar / 10.0
    radius_mm = diameter_mm / 2.0
    # t = P*R / (Sigma - 0.6*P)
    thickness_mm = (p_mpa * radius_mm) / (material_sigma_mpa/safety_factor - 0.6 * p_mpa)
    return thickness_mm

print("### Epaisseurs Paroi (Hoop Stress estimate)")
print("Hypothèse: P_design = 30 bar (3 MPa), Safety=2.0 (donc Pressure effective calcul = 60 bar equiv rupture)")
# Utilisation de formule simple P*D / 2*Sigma_admissible
# Sigma 310S à 650°C approx 100 MPa ? (très dépendant, souvent bcp moins en creep)
# Prenons 50 MPa admissible à chaud pour être safe (Creep limit)
p_des = 30.0
sig_hot = 40.0 # MPa conservative for high temp creep
sig_cold = 150.0 # MPa standard steel

print(f"| Composant | Temp | Sigma Allow (MPa) | P_design (bar) | Diamètre (mm) | Epaisseur Min (mm) |")
print("| :--- | :--- | :--- | :--- | :--- | :--- |")
for d in [100, 130, 150, 200]:
    t_hot = hoop_stress_thick(p_des, 1.0, d, sig_hot) # Safety included in Sigma low value
    t_cold = hoop_stress_thick(p_des, 1.0, d, sig_cold)
    print(f"| Tube/Cyl (Hot) | 650°C | {sig_hot} | {p_des} | {d} | **{t_hot:.2f}** |")
    print(f"| Carter (Cold) | 60°C | {sig_cold} | {p_des} | {d} | {t_cold:.2f} |")

