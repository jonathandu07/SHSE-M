import argparse
import json
import logging
import os
import sys

from .agent_rendements import EfficiencyAgent
from .agent_thermodynamique import ThermodynamicAgent
from .agent_combustion import CombustionAgent
from .agent_gaz_captif import CaptiveGasAgent
from .agent_mecanique import MechanicalAgent
from .agent_crabots import DogClutchAgent
from .agent_refroidissement import CoolingAgent
from .agent_electrique import ElectricalAgent
from .agent_batterie_bms import BatteryAgent
from .agent_securite import SecurityAgent
from .agent_controle import ControlAgent
from .agent_bom import BOMAgent

def main():
    parser = argparse.ArgumentParser(description="SHSE-M Sizing (Multi-Agent)")
    parser.add_argument("--config", type=str, default="shse_m_sizing/config.json", help="Path to config file")
    parser.add_argument("--output", type=str, default="output_shse_m", help="Output directory")
    args = parser.parse_args()

    # Setup Output
    os.makedirs(args.output, exist_ok=True)
    
    # Load Config
    with open(args.config, 'r') as f:
        config = json.load(f)

    # Global Results Store
    all_results = {}
    
    print("=== SHSE-M Sizing Start ===")
    
    # 1. Efficiency Agent
    eff_agent = EfficiencyAgent(config)
    res_eff = eff_agent.run()
    all_results['EfficiencyAgent'] = res_eff
    
    # 2. Thermodynamic Agent
    P_indicated = res_eff['P_indicated_kW']
    thermo_agent = ThermodynamicAgent(config, P_indicated)
    res_thermo = thermo_agent.run()
    all_results['ThermodynamicAgent'] = res_thermo
    
    # 3. Combustion Agent
    eta_th = res_thermo['eta_th']
    comb_agent = CombustionAgent(config, P_indicated, eta_th)
    res_comb = comb_agent.run()
    all_results['CombustionAgent'] = res_comb
    
    # 4. Captive Gas Agent
    V_total_cc = res_thermo['Vd_total_cc']
    gas_agent = CaptiveGasAgent(config, V_total_cc)
    res_gas = gas_agent.run()
    all_results['CaptiveGasAgent'] = res_gas
    
    # 5. Mechanical Agent
    Bore = res_thermo['Bore_mm']
    Stroke = res_thermo['Stroke_mm']
    p_max = res_thermo['p_max_bar']
    mech_agent = MechanicalAgent(config, Bore, Stroke, p_max)
    res_mech = mech_agent.run()
    all_results['MechanicalAgent'] = res_mech
    
    # 6. Dog Clutch Agent
    # Torque Mean ~ P_shaft / w. 
    # Use Peak Torque for sizing? 
    # T_mean = P_shaft / (2*pi*N/60)
    P_shaft = res_eff['P_shaft_kW'] * 1000
    w = 2 * 3.14159 * config['input']['N_rpm'] / 60
    T_mean = P_shaft / w
    # T_max estimate (pulse) ~ 2 * T_mean? or more depending on cylinder count
    T_max = T_mean * 2.0 
    
    clutch_agent = DogClutchAgent(config, T_max)
    res_clutch = clutch_agent.run()
    all_results['DogClutchAgent'] = res_clutch
    
    # 7. Cooling Agent
    Q_in = res_comb['P_thermal_input_kW']
    cool_agent = CoolingAgent(config, Q_in, P_indicated)
    res_cool = cool_agent.run()
    all_results['CoolingAgent'] = res_cool
    
    # 8. Electrical Agent
    elec_agent = ElectricalAgent(config, res_eff['P_shaft_kW'])
    res_elec = elec_agent.run()
    all_results['ElectricalAgent'] = res_elec
    
    # 9. Battery Agent
    batt_agent = BatteryAgent(config, res_elec['current_max_A'])
    res_batt = batt_agent.run()
    all_results['BatteryAgent'] = res_batt
    
    # 10. Security & Control
    sec_agent = SecurityAgent(config, all_results)
    res_sec = sec_agent.run()
    
    ctrl_agent = ControlAgent(config)
    res_ctrl = ctrl_agent.run()
    
    # 11. BOM
    bom_agent = BOMAgent(config, all_results)
    res_bom = bom_agent.run()
    bom_agent.export_csv(os.path.join(args.output, "BOM.csv"))
    
    # Reporting
    report_path = os.path.join(args.output, "final_report.json")
    with open(report_path, 'w') as f:
        json.dump(all_results, f, indent=4)
        
    print(f"Sizing Complete. Report: {report_path}")
    print(f"Bore: {Bore:.1f} mm, Stroke: {Stroke:.1f} mm")
    print(f"Safety Check: {res_sec['status']}")

if __name__ == "__main__":
    main()
