import argparse
import json
import sys
from .config import InputParameters, Efficiencies, Constraints
from .thermodynamics import calculate_thermodynamics
from .mechanical import dimension_components
from .check import verify_constraints
from .report import generate_markdown_report, generate_bom_csv, generate_json_export

def load_from_json(path: str) -> InputParameters:
    with open(path, 'r') as f:
        data = json.load(f)
    # Reconstruct objects (simplified, real world would use pydantic/marshmallow)
    eta_data = data.get('eta', {})
    limits_data = data.get('limits', {})
    
    return InputParameters(
        P_batt_target=data['P_batt_target'],
        N_rpm=data['N_rpm'],
        p_me_target_bar=data['p_me_target_bar'],
        eta=Efficiencies(**eta_data),
        limits=Constraints(**limits_data),
        N_cyl=data.get('N_cyl', 1),
        fluid=data.get('fluid', 'AIR'),
        T_cold=data.get('T_cold', 330.0)
    )

def main():
    parser = argparse.ArgumentParser(description="SHSE-M Sizing Tool")
    parser.add_argument("--json", type=str, help="Path to input JSON parameter file")
    parser.add_argument("--P_batt", type=float, help="Battery Power Target (kW)")
    parser.add_argument("--N", type=float, help="RPM")
    parser.add_argument("--p_me", type=float, help="MEP Target (bar)")
    parser.add_argument("--output_dir", type=str, default=".", help="Directory for output files")
    
    args = parser.parse_args()
    
    inputs = None
    
    if args.json:
        print(f"Loading parameters from {args.json}...")
        inputs = load_from_json(args.json)
    elif args.P_batt and args.N and args.p_me:
        print("Using CLI parameters...")
        inputs = InputParameters(
            P_batt_target=args.P_batt,
            N_rpm=args.N,
            p_me_target_bar=args.p_me
        )
    else:
        # Default / Demo mode
        print("No input provided. Using default demo parameters.")
        inputs = InputParameters(
            P_batt_target=10.0,
            N_rpm=3000.0,
            p_me_target_bar=6.0
        )
        
    print(f"Calcul pour: P_batt={inputs.P_batt_target} kW @ {inputs.N_rpm} rpm")
    
    # 1. Thermodynamics
    results = calculate_thermodynamics(inputs)
    
    # 2. Mechanical Sizing
    results = dimension_components(inputs, results)
    
    # 3. Checks
    results = verify_constraints(inputs, results)
    
    if results.warnings:
        print("WARNINGS:")
        for w in results.warnings:
            print(f"  - {w}")
            
    # 4. Reporting
    import os
    os.makedirs(args.output_dir, exist_ok=True)
    
    generate_markdown_report(inputs, results, os.path.join(args.output_dir, "report.md"))
    generate_bom_csv(results, os.path.join(args.output_dir, "bom.csv"))
    generate_json_export(inputs, results, os.path.join(args.output_dir, "params.json"))
    
    print(f"Done. Files generated in {args.output_dir}/")

if __name__ == "__main__":
    main()
