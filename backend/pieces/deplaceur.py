# -*- coding: utf-8 -*-
# backend/pieces/deplaceur.py
"""
Frontal unifié — Déplaceur Stirling
Appelle:
  - backend.modules.deplaceur_core       (scalaire)
  - backend.modules.deplaceur_vector     (NumPy)
  - backend.modules.deplaceur_batch_io   (Pandas)

CLI:
  python -m backend.pieces.deplaceur single --bore 0.08 --stroke 0.08 --rpm 600
  python -m backend.pieces.deplaceur vector --bores 0.06,0.08 --strokes 0.06,0.08 --rpm 600
  python -m backend.pieces.deplaceur batch --in in.csv --out out.csv
"""

from __future__ import annotations
import argparse
import numpy as np

from backend.modules.deplaceur_core import (
    DeplaceurInputs as CoreInputs,
    DeplaceurResult as CoreResult,
    size_deplaceur as size_scalar,
)
from backend.modules.deplaceur_vector import (
    size_deplaceur_vector as size_vector,
)
from backend.modules.deplaceur_batch_io import (
    from_csv as batch_from_csv,
    run_batch as batch_run,
    to_csv as batch_to_csv,
)

def _print_scalar(res: CoreResult, inp: CoreInputs):
    print("=== DÉPLACEUR — Résultat (scalaire) ===")
    if res.ok:
        print(f"Ø froid ext.    : {res.disp_outer_diameter_cold_m*1000:.2f} mm")
        print(f"Ø chaud ext.    : {res.disp_outer_diameter_hot_m*1000:.2f} mm")
        print(f"Jeu froid       : {res.radial_clearance_cold_m*1e3:.3f} mm")
        print(f"Jeu chaud       : {res.radial_clearance_hot_m*1e3:.3f} mm (min {inp.min_hot_clearance_m*1e3:.3f})")
        print(f"Longueur utile  : {res.disp_length_m*1000:.2f} mm")
        print(f"Course déplac.  : {res.disp_stroke_m*1000:.2f} mm")
        print(f"Masse totale    : {res.mass_total_kg*1e3:.1f} g")
        print(f"Vitesse max     : {res.vmax_m_s:.3f} m/s   (rpm={inp.rpm:.0f})")
        print(f"Effort axial    : {res.axial_force_PaN:.1f} N")
        print(f"Tige Euler OK ? : {'Oui' if res.rod_euler_ok else 'Non'}")
        print(f"Indice fuite    : {res.leak_index:.3e}  (OK? {'Oui' if res.leak_ok else 'Non'})")
        print(res.message)
    else:
        print("ÉCHEC :", res.message)

def _print_vector_brief(res: dict):
    msg_map = {0:"OK", 1:"Jeu chaud insuffisant", 2:"Flambage tige", 3:"Fuite annulaire"}
    print("=== DÉPLACEUR — Vector résumé ===")
    ok = res["ok"]
    for idx in np.ndindex(ok.shape):
        if ok[idx]:
            print(f"{idx}: OK | Øf={res['disp_outer_diameter_cold_m'][idx]*1000:.2f} mm | "
                  f"L={res['disp_length_m'][idx]*1000:.1f} mm | m={res['mass_total_kg'][idx]*1e3:.1f} g")
        else:
            print(f"{idx}: NOK | {msg_map[int(res['message_id'][idx])]}")

def size_one(**kwargs) -> CoreResult:
    inp = CoreInputs(**kwargs)
    return size_scalar(inp)

def size_grid(bores, strokes, **kwargs_vector) -> dict:
    return size_vector(
        bore_m=np.asarray(bores),
        stroke_m=np.asarray(strokes),
        **kwargs_vector
    )

def _csv_floats(s: str) -> np.ndarray:
    return np.array([float(x.strip()) for x in s.split(",") if x.strip()])

def main():
    ap = argparse.ArgumentParser(description="Déplaceur Stirling — frontal unifié")
    sp = ap.add_subparsers(dest="cmd", required=True)

    # --- single ---
    p1 = sp.add_parser("single", help="Un seul cas (scalaire)")
    p1.add_argument("--bore", type=float, required=True, help="Alésage B (m)")
    p1.add_argument("--stroke", type=float, required=True, help="Course S (m)")
    p1.add_argument("--k-phase", type=float, default=1.0)
    p1.add_argument("--clearance-hot-min", type=float, default=0.08e-3)
    p1.add_argument("--alpha", type=float, default=12e-6)
    p1.add_argument("--dT", type=float, default=500.0)
    p1.add_argument("--tol", type=float, default=0.03e-3)
    p1.add_argument("--shell-t", type=float, default=0.5e-3)
    p1.add_argument("--cap-t", type=float, default=0.6e-3)
    p1.add_argument("--rho", type=float, default=8000.0)
    p1.add_argument("--core", action="store_true", help="Activer cœur léger")
    p1.add_argument("--rho-core", type=float, default=50.0)
    p1.add_argument("--rod-L", type=float, default=float("nan"))
    p1.add_argument("--rod-d", type=float, default=4e-3)
    p1.add_argument("--E", type=float, default=200e9)
    p1.add_argument("--rpm", type=float, default=600.0)
    p1.add_argument("--dp", type=float, default=2000.0, help="ΔP dynamique (Pa)")
    p1.add_argument("--leak-max", type=float, default=1.5e-4)
    p1.add_argument("--dome-clear", type=float, default=0.02)
    p1.add_argument("--clearance-cold", type=float, default=float("nan"))

    # --- vector ---
    p2 = sp.add_parser("vector", help="Vectorisé (plusieurs alésages/courses)")
    p2.add_argument("--bores", type=str, required=True, help="CSV d'alésages en m, ex: 0.06,0.07,0.08")
    p2.add_argument("--strokes", type=str, required=True, help="CSV de courses en m, ex: 0.06,0.08")
    p2.add_argument("--k-phase", type=float, default=1.0)
    p2.add_argument("--dome-clear", type=float, default=0.02)
    p2.add_argument("--clearance-hot-min", type=float, default=0.08e-3)
    p2.add_argument("--alpha", type=float, default=12e-6)
    p2.add_argument("--dT", type=float, default=500.0)
    p2.add_argument("--tol", type=float, default=0.03e-3)
    p2.add_argument("--shell-t", type=float, default=0.5e-3)
    p2.add_argument("--cap-t", type=float, default=0.6e-3)
    p2.add_argument("--rho", type=float, default=8000.0)
    p2.add_argument("--core", action="store_true")
    p2.add_argument("--rho-core", type=float, default=50.0)
    p2.add_argument("--rod-L", type=float, default=float("nan"))
    p2.add_argument("--rod-d", type=float, default=4e-3)
    p2.add_argument("--E", type=float, default=200e9)
    p2.add_argument("--rpm", type=float, default=600.0)
    p2.add_argument("--dp", type=float, default=2000.0)
    p2.add_argument("--leak-max", type=float, default=1.5e-4)

    # --- batch ---
    p3 = sp.add_parser("batch", help="Batch CSV → CSV (Pandas)")
    p3.add_argument("--in", dest="in_csv", required=True)
    p3.add_argument("--out", dest="out_csv", required=True)

    args = ap.parse_args()

    if args.cmd == "single":
        res = size_one(
            bore_m=args.bore,
            stroke_m=args.stroke,
            k_phase=args.k_phase,
            dome_extra_clearance_m=args.dome_clear,
            radial_clearance_cold_m=None if np.isnan(args.clearance_cold) else args.clearance_cold,
            min_hot_clearance_m=args.clearance_hot_min,
            alpha_material_1K=args.alpha,
            deltaT_hotK=args.dT,
            manuf_tol_radial_m=args.tol,
            shell_thickness_m=args.shell_t,
            cap_thickness_m=args.cap_t,
            material_density=args.rho,
            use_hollow_core=args.core,
            core_density=args.rho_core,
            rod_length_m=None if np.isnan(args.rod_L) else args.rod_L,
            rod_diameter_m=args.rod_d,
            young_modulus_Pa=args.E,
            rpm=args.rpm,
            gas_dynamic_dp_Pa=args.dp,
            acceptable_leak_index=args.leak_max,
        )
        _print_scalar(res, CoreInputs(
            bore_m=args.bore, stroke_m=args.stroke, k_phase=args.k_phase,
            dome_extra_clearance_m=args.dome_clear,
            radial_clearance_cold_m=None if np.isnan(args.clearance_cold) else args.clearance_cold,
            min_hot_clearance_m=args.clearance_hot_min,
            alpha_material_1K=args.alpha, deltaT_hotK=args.dT, manuf_tol_radial_m=args.tol,
            shell_thickness_m=args.shell_t, cap_thickness_m=args.cap_t,
            material_density=args.rho, use_hollow_core=args.core, core_density=args.rho_core,
            rod_length_m=None if np.isnan(args.rod_L) else args.rod_L,
            rod_diameter_m=args.rod_d, young_modulus_Pa=args.E,
            rpm=args.rpm, gas_dynamic_dp_Pa=args.dp, acceptable_leak_index=args.leak_max
        ))

    elif args.cmd == "vector":
        bores = _csv_floats(args.bores)
        strokes = _csv_floats(args.strokes)
        res = size_grid(
            bores=bores[:, None],    # grid bores x strokes
            strokes=strokes[None, :],
            k_phase=args.k_phase,
            dome_extra_clearance_m=args.dome_clear,
            radial_clearance_cold_m=None,  # auto
            min_hot_clearance_m=args.clearance_hot_min,
            alpha_material_1K=args.alpha,
            deltaT_hotK=args.dT,
            manuf_tol_radial_m=args.tol,
            shell_thickness_m=args.shell_t,
            cap_thickness_m=args.cap_t,
            material_density=args.rho,
            use_hollow_core=args.core,
            core_density=args.rho_core,
            rod_length_m=None if np.isnan(args.rod_L) else args.rod_L,
            rod_diameter_m=args.rod_d,
            young_modulus_Pa=args.E,
            rpm=args.rpm,
            gas_dynamic_dp_Pa=args.dp,
            acceptable_leak_index=args.leak_max,
        )
        _print_vector_brief(res)

    elif args.cmd == "batch":
        df = batch_from_csv(args.in_csv)
        df_out = batch_run(df)
        batch_to_csv(df_out, args.out_csv)
        print(f"Batch terminé. Résultats écrits dans: {args.out_csv}")

if __name__ == "__main__":
    main()
