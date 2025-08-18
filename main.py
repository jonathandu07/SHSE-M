# -*- coding: utf-8 -*-
# main.py
"""
CLI unifiée pour le projet moteur Stirling.

Sous-commandes principales :
  - optimise        : optimisation globale
  - cylindre        : dimensionnement B, S via BMEP (scalaire)
  - batch-cylindre  : vectorisation CSV pour cylindres
  - deplaceur       : pré-dimensionnement déplaceur (scalaire)
  - batch-deplaceur : vectorisation CSV pour déplaceurs
  - piston          : pré-dimensionnement piston
  - paliers         : pré-dimensionnement paliers
  - vilebrequin     : pré-dimensionnement vilebrequin
  - volant          : volant d’inertie
  - chemise         : chemise de cylindre
  - visserie        : choix visserie
  - materiaux       : sélection/fiche matériau
  - gaz             : fiche gaz
"""

from __future__ import annotations
import argparse
import sys
import json
from dataclasses import asdict, is_dataclass

# ========= Imports projet =========
def _safe_import():
    try:
        # Optimisation & catalogues
        from backend.modules.optimisation import OptiInputs, optimise
        from backend.modules.meteriaux import MATERIALS, choose_material_for_part, describe_material, yield_at_T
        from backend.modules.gaz import get_gaz

        # Cylindre (modules)
        from backend.modules.cylindre_core import SizingInputs as CylIn, size_stirling_cylinders as size_cyl
        from backend.modules.cylindre_batch_io import from_csv as cyl_from_csv, run_batch as cyl_run_batch, to_csv as cyl_to_csv

        # Déplaceur (modules)
        from backend.modules.deplaceur_core import DeplaceurInputs as DepIn, size_deplaceur as size_dep
        from backend.modules.deplaceur_batch_io import from_csv as dep_from_csv, run_batch as dep_run_batch, to_csv as dep_to_csv

        # Pièces
        from backend.pieces.piston import PistonInputs, size_piston
        from backend.pieces.paliers import BearingInputs, size_bearings
        from backend.pieces.vilebrequin import CrankInputs, size_crankshaft
        from backend.pieces.volant_inertie import FlywheelInputs, size_flywheel
        from backend.pieces.chemise_de_cylindre import ChemiseInputs, size_chemise
        from backend.pieces.visserie import ScrewSelectionInputs, select_screws

        return {
            # Optimisation & catalogues
            "OptiInputs": OptiInputs, "optimise": optimise,
            "MATERIALS": MATERIALS, "choose_material_for_part": choose_material_for_part,
            "describe_material": describe_material, "yield_at_T": yield_at_T,
            "get_gaz": get_gaz,

            # Cylindre
            "CylIn": CylIn, "size_cyl": size_cyl,
            "cyl_from_csv": cyl_from_csv, "cyl_run_batch": cyl_run_batch, "cyl_to_csv": cyl_to_csv,

            # Déplaceur
            "DepIn": DepIn, "size_dep": size_dep,
            "dep_from_csv": dep_from_csv, "dep_run_batch": dep_run_batch, "dep_to_csv": dep_to_csv,

            # Pièces
            "PistonInputs": PistonInputs, "size_piston": size_piston,
            "BearingInputs": BearingInputs, "size_bearings": size_bearings,
            "CrankInputs": CrankInputs, "size_crankshaft": size_crankshaft,
            "FlywheelInputs": FlywheelInputs, "size_flywheel": size_flywheel,
            "ChemiseInputs": ChemiseInputs, "size_chemise": size_chemise,
            "ScrewSelectionInputs": ScrewSelectionInputs, "select_screws": select_screws,
        }
    except Exception as e:
        print("[ERREUR IMPORT] Vérifie l’arborescence et les modules listés dans ton dépôt.", file=sys.stderr)
        raise

M = _safe_import()

# ========= Helpers d’affichage =========
def _to_dict(obj):
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    return obj.__dict__

def _print_json(obj):
    print(json.dumps(_to_dict(obj), indent=2, ensure_ascii=False))

def _add_common_bool(p):
    p.add_argument("--json", action="store_true", help="Sortie JSON (sinon affichage humain)")

def _maybe_print_json(flag_json: bool, dataclass_obj):
    if flag_json:
        _print_json(dataclass_obj)
        return True
    return False

# ========= Commandes =========
def cmd_optimise(args):
    cfg = M["OptiInputs"](
        power_W=args.power,
        eta_mech=args.eta,
        rpm_range=(args.rpm_min, args.rpm_max),
        pme_range_Pa=(args.pme_min, args.pme_max),
        S_over_B_range=(args.SB_min, args.SB_max),
        n_cyl_range=(args.ncyl_min, args.ncyl_max),
        gases=tuple(args.gaz),
        bore_max_m=args.bmax,
        upiston_max_m_s=args.Up_max,
        alpha_ripple=args.alpha_ripple,
        flywheel_radius_m=args.flywheel_r,
        rim_speed_limit_m_s=args.rim_vmax,
        samples=args.samples,
        local_refine=args.refine
    )
    res = M["optimise"](cfg, seed=args.seed)
    if args.json:
        _print_json(_to_dict(res))
    else:
        print("=== OPTIMISATION ===")
        print(res.message)
        b = res.best
        if b:
            print("\n-- BEST --")
            for k in ("score","rpm","p_me_Pa","S_over_B","n_cyl","B_m","S_m","Up_m_s","p_peak_Pa"):
                if k in b:
                    print(f"{k:>14} : {b[k]}")
            print("Volant J (kg·m²) :", b["volant"]["J"])
            print("Visserie         :", b["visserie"]["choice"])
            print("\n-- TOP5 --")
            for i, s in enumerate(res.top5, 1):
                print(f"{i:02d}. score={s['score']:.3f} | n_cyl={s['n_cyl']} | rpm={s['rpm']:.0f} | B={s['B_m']*1000:.1f} mm")

def cmd_cylindre(args):
    inp = M["CylIn"](
        power_W=args.power, rpm=args.rpm, eta_mech=args.eta,
        p_me=args.pme, use_pmean_model=args.use_pmean, p_mean=args.pmean, k_me=args.kme,
        upiston_max=args.Up_max, bore_max=args.bmax, stroke_to_bore=args.S_over_B,
        n_cyl_max=args.ncyl_max, allow_rpm_reduce=not args.no_rpm_reduce, min_rpm=args.min_rpm
    )
    res = M["size_cyl"](inp)
    if _maybe_print_json(args.json, res): return
    print("=== CYLINDRE ===")
    if res.ok:
        print(f"n_cyl         : {res.n_cyl}")
        print(f"rpm           : {res.rpm:.0f}")
        print(f"B (mm)        : {res.bore_m*1000:.2f}")
        print(f"S (mm)        : {res.stroke_m*1000:.2f}")
        print(f"Vs/cyl (cm³)  : {res.Vs_cyl_m3*1e6:.1f}")
        print(f"Vs total (cm³): {res.Vs_total_m3*1e6:.1f}")
        print(res.message)
    else:
        print("ÉCHEC :", res.message)

def cmd_batch_cylindre(args):
    df = M["cyl_from_csv"](args.input)
    out = M["cyl_run_batch"](df)
    if args.output:
        M["cyl_to_csv"](out, args.output)
        print(f"[OK] Résultats écrits : {args.output}")
    else:
        print(out.head(20).to_string(index=False))

def cmd_deplaceur(args):
    inp = M["DepIn"](
        bore_m=args.B, stroke_m=args.S, rpm=args.rpm,
        k_phase=args.k_phase, dome_extra_clearance_m=args.marge,
        radial_clearance_cold_m=None if args.cr_cold_auto else args.cr_cold,
        min_hot_clearance_m=args.cr_hot_min,
        alpha_material_1K=args.alpha, deltaT_hotK=args.dT,
        manuf_tol_radial_m=args.tol,
        shell_thickness_m=args.t_shell, cap_thickness_m=args.t_caps,
        material_density=args.rho_shell, core_density=args.rho_core,
        use_hollow_core=not args.solid,
        rod_length_m=None if args.rod_L_auto else args.rod_L,
        rod_diameter_m=args.rod_d, young_modulus_Pa=args.E,
        gas_dynamic_dp_Pa=args.dp_dyn
    )
    res = M["size_dep"](inp)
    if _maybe_print_json(args.json, res): return
    print("=== DÉPLACEUR ===")
    if res.ok:
        print(f"Ø froid (mm)      : {res.disp_outer_diameter_cold_m*1000:.2f}")
        print(f"Ø chaud (mm)      : {res.disp_outer_diameter_hot_m*1000:.2f}")
        print(f"L utile (mm)      : {res.disp_length_m*1000:.1f}")
        print(f"Jeu à chaud (µm)  : {res.radial_clearance_hot_m*1e6:.2f}")
        print(f"Masse (g)         : {res.mass_total_kg*1e3:.1f}")
        print(res.message)
    else:
        print("ÉCHEC :", res.message)

def cmd_batch_deplaceur(args):
    df = M["dep_from_csv"](args.input)
    out = M["dep_run_batch"](df)
    if args.output:
        M["dep_to_csv"](out, args.output)
        print(f"[OK] Résultats écrits : {args.output}")
    else:
        print(out.head(20).to_string(index=False))

def cmd_piston(args):
    inp = M["PistonInputs"](
        bore_m=args.B, stroke_m=args.S, rpm=args.rpm,
        p_mean_cycle_Pa=args.pmean, p_peak_gas_Pa=args.ppeak,
        n_rings=args.nrings, axial_load_factor=args.axial_k,
        estimate_mass=args.est_mass
    )
    res = M["size_piston"](inp)
    if _maybe_print_json(args.json, res): return
    print("=== PISTON ===")
    print(f"F_peak (N)          : {res.F_peak_N:.1f}")
    print(f"Friction segments N : {res.ring_total_friction_N:.2f}")
    print(f"Ø axe estimé (mm)   : {res.pin_diameter_m*1000:.2f}")

def cmd_paliers(args):
    inp = M["BearingInputs"](
        bore_m=args.B, stroke_m=args.S, rpm=args.rpm, n_cyl=args.ncyl,
        p_mean_cycle_Pa=args.pmean, p_peak_gas_Pa=args.ppeak,
        oil_viscosity_Pa_s=args.nu, clearance_ratio=args.clear,
        p_allow_Pa=args.p_allow, PV_allow_W_m2=args.PV_allow,
        sommerfeld_min=args.Smin
    )
    res = M["size_bearings"](inp)
    if _maybe_print_json(args.json, res): return
    print("=== PALIERS ===")
    print(f"D_main (mm)  : {res.main_D_m*1000:.2f}  | L_main (mm): {res.main_L_m*1000:.2f}")
    print(f"p_main (MPa) : {res.main_unit_pressure_Pa/1e6:.2f} | PV_main (MW/m²): {res.main_PV_W_m2/1e6:.2f}")
    print(res.message)

def cmd_vilebrequin(args):
    inp = M["CrankInputs"](
        bore_m=args.B, stroke_m=args.S, rpm=args.rpm, n_cyl=args.ncyl,
        p_mean_cycle_Pa=args.pmean, p_peak_gas_Pa=args.ppeak,
        mass_recip_kg=args.mrec, balance_factor=args.fb
    )
    res = M["size_crankshaft"](inp)
    if _maybe_print_json(args.json, res): return
    print("=== VILEBREQUIN ===")
    print(f"r=S/2 (mm)       : {res.r_m*1000:.2f}")
    print(f"d_pin (mm)       : {res.pin_diameter_m*1000:.2f} | L_pin (mm): {res.pin_length_m*1000:.2f}")
    print(f"t_web (mm)       : {res.web_thickness_m*1000:.2f}")
    print(f"m_cw (kg)        : {res.cw_mass_kg:.3f}")
    print(res.message)

def cmd_volant(args):
    inp = M["FlywheelInputs"](
        T_mean_Nm=args.Tm if args.Tm is not None else None,
        T1_Nm=args.T1 if args.T1 is not None else None,
        p_me_Pa=args.pme if args.Tm is None else None,
        Vs_total_per_rev_m3=args.Vs if args.Tm is None else None,
        eta_mech=args.eta,
        alpha_ripple=args.alpha if args.T1 is None else None,
        k_harmonic=1, coeff_irregularity=args.c,
        rpm=args.rpm, shape=args.shape, radius_m=args.r, rim_speed_limit_m_s=args.vmax
    )
    res = M["size_flywheel"](inp)
    if _maybe_print_json(args.json, res): return
    print("=== VOLANT D’INERTIE ===")
    print(f"J requis (kg·m²): {res.J_required_kg_m2:.5f} | m (kg): {res.mass_required_kg:.2f}")
    print(f"v_jante (m/s)   : {res.rim_speed_m_s:.1f} | OK? {'Oui' if res.speed_ok else 'Non'}")
    print(res.message)

def cmd_chemise(args):
    inp = M["ChemiseInputs"](
        bore_m=args.B, longueur_m=args.L,
        p_interne_Pa=args.p, fs=args.fs,
        sigma_allow_Pa=args.sigma, density_kg_m3=args.rho, alpha_1K=args.alpha,
        T_cold_C=args.Tc, T_hot_C=args.Th,
        piston_alpha_1K=args.alpha_pis,
        radial_clearance_cold_m=None if args.cr_cold_auto else args.cr_cold,
        radial_clearance_hot_min_m=args.cr_hot_min,
        manuf_tol_radial_m=args.tol
    )
    res = M["size_chemise"](inp)
    if _maybe_print_json(args.json, res): return
    print("=== CHEMISE ===")
    print(f"t (mm)          : {res.epaisseur_m*1000:.2f} | méthode: {res.method} (t/ri={res.t_over_ri:.3f})")
    print(f"σθ max (MPa)    : {res.hoop_stress_Pa/1e6:.1f}")
    print(f"Jeu chaud (µm)  : {res.clearance_hot_radial_m*1e6:.2f}")
    print(f"Masse (g)       : {res.masse_kg*1e3:.1f}")
    print(res.message)

def cmd_visserie(args):
    inp = M["ScrewSelectionInputs"](
        axial_tension_N=args.Fax, shear_N=args.V, mode=args.mode,
        n_bolts_max=args.nmax, bolt_sizes=args.sizes, preferred_classes=args.classes,
        friction_mu=args.mu, joint_stiffness_ratio=args.Cj, preload_ratio_of_Sp=args.preload,
        plate_thickness_m=args.tplate, bearing_allow_Pa=args.p_allow,
        FS_tension=args.FS_t, FS_shear=args.FS_v, FS_bearing=args.FS_b, FS_noslip=args.FS_ns,
        corrosive_env=args.corrosif
    )
    res = M["select_screws"](inp)
    if args.json:
        _print_json(_to_dict(res))
    else:
        print("=== VISSERIE ===")
        print("OK ?", res.ok, "|", res.message)
        if res.ok:
            print(f"Choix : {res.bolt_count}× {res.bolt_size} {res.bolt_class}")
            print(f"Précharge/vis (N): {res.preload_per_bolt_N:.0f} | Couple (N·m): {res.torque_estimate_Nm:.1f}")
            if res.hints:
                print("Notes :")
                for h in res.hints:
                    print(" -", h)

def cmd_materiaux(args):
    if args.list:
        print("=== MATÉRIAUX DISPONIBLES ===")
        for k, m in M["MATERIALS"].items():
            print(f"{k:>10} : {m.name} [{m.category}] Tmax={m.Tmax_service_C}°C")
        return
    if args.key:
        print(M["describe_material"](args.key))
        return
    mat = M["choose_material_for_part"](args.part, args.Tmax, prefer_light=args.light, require_bearing=args.bearing)
    print(M["describe_material"](mat.key))

def cmd_gaz(args):
    g = M["get_gaz"](args.key)
    if args.json:
        _print_json(asdict(g))
    else:
        print(f"{g.nom} ({g.symbole}) — M={g.M} g/mol, γ={g.gamma}, Cp={g.Cp} J/kg/K, k={g.k} W/m/K")

# ========= Parser =========
def build_parser():
    p = argparse.ArgumentParser(description="CLI Stirling — dimensionnements, batch & optimisation")
    sp = p.add_subparsers(dest="cmd", required=True)

    # optimise
    po = sp.add_parser("optimise", help="Optimisation globale")
    po.add_argument("--power", type=float, required=True, help="Puissance cible (W)")
    po.add_argument("--eta", type=float, default=0.85)
    po.add_argument("--rpm-min", type=float, default=400)
    po.add_argument("--rpm-max", type=float, default=1500)
    po.add_argument("--pme-min", type=float, default=120e3)
    po.add_argument("--pme-max", type=float, default=400e3)
    po.add_argument("--SB-min", type=float, default=0.8)
    po.add_argument("--SB-max", type=float, default=1.3)
    po.add_argument("--ncyl-min", type=int, default=1)
    po.add_argument("--ncyl-max", type=int, default=8)
    po.add_argument("--gaz", nargs="+", default=["air","helium","hydrogene","azote"])
    po.add_argument("--bmax", type=float, default=0.10)
    po.add_argument("--Up-max", type=float, default=2.2)
    po.add_argument("--alpha-ripple", type=float, default=0.25)
    po.add_argument("--flywheel-r", type=float, default=0.18)
    po.add_argument("--rim-vmax", type=float, default=80.0)
    po.add_argument("--samples", type=int, default=600)
    po.add_argument("--refine", type=int, default=60)
    po.add_argument("--seed", type=int, default=123)
    _add_common_bool(po)

    # cylindre scalaire
    pcyl = sp.add_parser("cylindre", help="Dimensionnement cylindre (B,S)")
    pcyl.add_argument("--power", type=float, required=True)
    pcyl.add_argument("--rpm", type=float, required=True)
    pcyl.add_argument("--eta", type=float, default=0.85)
    pcyl.add_argument("--pme", type=float, default=200e3)
    pcyl.add_argument("--use-pmean", action="store_true")
    pcyl.add_argument("--pmean", type=float, default=1.0e6)
    pcyl.add_argument("--kme", type=float, default=0.20)
    pcyl.add_argument("--Up-max", type=float, default=2.0)
    pcyl.add_argument("--bmax", type=float, default=0.10)
    pcyl.add_argument("--S-over-B", type=float, default=1.0)
    pcyl.add_argument("--ncyl-max", type=int, default=12)
    pcyl.add_argument("--no-rpm-reduce", action="store_true")
    pcyl.add_argument("--min-rpm", type=float, default=300.0)
    _add_common_bool(pcyl)

    # cylindre batch
    pbc = sp.add_parser("batch-cylindre", help="Vectorisation CSV pour cylindres")
    pbc.add_argument("--input", "-i", required=True, help="CSV d’entrée")
    pbc.add_argument("--output", "-o", required=False, help="CSV de sortie")

    # déplaceur scalaire
    pd = sp.add_parser("deplaceur", help="Pré-dimensionnement déplaceur")
    pd.add_argument("--B", type=float, required=True)
    pd.add_argument("--S", type=float, required=True)
    pd.add_argument("--rpm", type=float, default=600.0)
    pd.add_argument("--k-phase", type=float, default=1.0)
    pd.add_argument("--marge", type=float, default=0.008)
    pd.add_argument("--cr-cold", type=float, default=0.12e-3)
    pd.add_argument("--cr-cold-auto", action="store_true")
    pd.add_argument("--cr-hot-min", type=float, default=0.08e-3)
    pd.add_argument("--alpha", type=float, default=12e-6)
    pd.add_argument("--dT", type=float, default=500.0)
    pd.add_argument("--tol", type=float, default=0.03e-3)
    pd.add_argument("--t-shell", type=float, default=0.4e-3)
    pd.add_argument("--t-caps", type=float, default=0.5e-3)
    pd.add_argument("--rho-shell", type=float, default=7900.0)
    pd.add_argument("--rho-core", type=float, default=60.0)
    pd.add_argument("--solid", action="store_true")
    pd.add_argument("--rod-L", type=float, default=0.0)
    pd.add_argument("--rod-L-auto", action="store_true")
    pd.add_argument("--rod-d", type=float, default=4e-3)
    pd.add_argument("--E", type=float, default=190e9)
    pd.add_argument("--dp-dyn", type=float, default=2000.0)
    _add_common_bool(pd)

    # déplaceur batch
    pbd = sp.add_parser("batch-deplaceur", help="Vectorisation CSV pour déplaceurs")
    pbd.add_argument("--input", "-i", required=True, help="CSV d’entrée")
    pbd.add_argument("--output", "-o", required=False, help="CSV de sortie")

    # piston
    pp = sp.add_parser("piston", help="Pré-dimensionnement piston")
    pp.add_argument("--B", type=float, required=True)
    pp.add_argument("--S", type=float, required=True)
    pp.add_argument("--rpm", type=float, default=600.0)
    pp.add_argument("--pmean", type=float, default=200e3)
    pp.add_argument("--ppeak", type=float, default=1.2e6)
    pp.add_argument("--nrings", type=int, default=2)
    pp.add_argument("--axial-k", type=float, default=1.0)
    pp.add_argument("--est-mass", action="store_true")
    _add_common_bool(pp)

    # paliers
    pal = sp.add_parser("paliers", help="Pré-dimensionnement paliers lisses")
    pal.add_argument("--B", type=float, required=True)
    pal.add_argument("--S", type=float, required=True)
    pal.add_argument("--rpm", type=float, default=600.0)
    pal.add_argument("--ncyl", type=int, default=1)
    pal.add_argument("--pmean", type=float, default=200e3)
    pal.add_argument("--ppeak", type=float, default=1.2e6)
    pal.add_argument("--nu", type=float, default=0.02)
    pal.add_argument("--clear", type=float, default=0.0015)
    pal.add_argument("--p-allow", type=float, default=10e6)
    pal.add_argument("--PV-allow", type=float, default=2.0e6)
    pal.add_argument("--Smin", type=float, default=0.05)
    _add_common_bool(pal)

    # vilebrequin
    pv = sp.add_parser("vilebrequin", help="Pré-dimensionnement vilebrequin")
    pv.add_argument("--B", type=float, required=True)
    pv.add_argument("--S", type=float, required=True)
    pv.add_argument("--rpm", type=float, default=600.0)
    pv.add_argument("--ncyl", type=int, default=1)
    pv.add_argument("--pmean", type=float, default=200e3)
    pv.add_argument("--ppeak", type=float, default=1.2e6)
    pv.add_argument("--mrec", type=float, default=0.35)
    pv.add_argument("--fb", type=float, default=0.5)
    _add_common_bool(pv)

    # volant
    fv = sp.add_parser("volant", help="Volant d’inertie")
    fv.add_argument("--rpm", type=float, default=600.0)
    fv.add_argument("--Tm", type=float, default=None, help="Couple moyen (Nm) (sinon pme+Vs)")
    fv.add_argument("--T1", type=float, default=None, help="Amplitude fondamentale (Nm) (sinon alpha)")
    fv.add_argument("--pme", type=float, default=None)
    fv.add_argument("--Vs", type=float, default=None, help="Vs_total par tour (m³)")
    fv.add_argument("--eta", type=float, default=0.9)
    fv.add_argument("--alpha", type=float, default=0.25)
    fv.add_argument("--c", type=float, default=0.02, help="coefficient d’irrégularité")
    fv.add_argument("--shape", choices=["rim","solid"], default="rim")
    fv.add_argument("--r", type=float, default=0.18)
    fv.add_argument("--vmax", type=float, default=80.0)
    _add_common_bool(fv)

    # chemise
    ch = sp.add_parser("chemise", help="Chemise de cylindre")
    ch.add_argument("--B", type=float, required=True)
    ch.add_argument("--L", type=float, required=True)
    ch.add_argument("--p", type=float, required=True, help="Pression interne max (Pa)")
    ch.add_argument("--fs", type=float, default=1.6)
    ch.add_argument("--sigma", type=float, default=220e6)
    ch.add_argument("--rho", type=float, default=7200.0)
    ch.add_argument("--alpha", type=float, default=10.5e-6)
    ch.add_argument("--Tc", type=float, default=20.0)
    ch.add_argument("--Th", type=float, default=150.0)
    ch.add_argument("--alpha-pis", type=float, default=20.5e-6)
    ch.add_argument("--cr-cold", type=float, default=0.02e-3)
    ch.add_argument("--cr-cold-auto", action="store_true")
    ch.add_argument("--cr-hot-min", type=float, default=0.01e-3)
    ch.add_argument("--tol", type=float, default=0.02e-3)
    _add_common_bool(ch)

    # visserie
    vs = sp.add_parser("visserie", help="Sélection visserie")
    vs.add_argument("--Fax", type=float, default=0.0)
    vs.add_argument("--V", type=float, default=0.0)
    vs.add_argument("--mode", choices=["friction","bearing"], default="bearing")
    vs.add_argument("--nmax", type=int, default=12)
    vs.add_argument("--sizes", nargs="+", default=["M6","M8","M10"])
    vs.add_argument("--classes", nargs="+", default=None)
    vs.add_argument("--mu", type=float, default=0.14)
    vs.add_argument("--Cj", type=float, default=0.3)
    vs.add_argument("--preload", type=float, default=0.7)
    vs.add_argument("--tplate", type=float, default=0.006)
    vs.add_argument("--p-allow", type=float, default=250e6)
    vs.add_argument("--FS-t", type=float, default=1.25)
    vs.add_argument("--FS-v", type=float, default=1.25)
    vs.add_argument("--FS-b", type=float, default=1.25)
    vs.add_argument("--FS-ns", type=float, default=1.30)
    vs.add_argument("--corrosif", action="store_true")
    _add_common_bool(vs)

    # materiaux
    mt = sp.add_parser("materiaux", help="Matériaux (liste, fiche, ou sélection par pièce)")
    mt.add_argument("--list", action="store_true", help="Lister tous les matériaux")
    mt.add_argument("--key", type=str, help="Afficher la fiche d’un matériau par clé")
    mt.add_argument("--part", type=str, default="piston", help="Profil (piston, heater_head, bearing_journal...)")
    mt.add_argument("--Tmax", type=float, default=180.0)
    mt.add_argument("--light", action="store_true", help="Préférer léger")
    mt.add_argument("--bearing", action="store_true", help="Exiger p/PV (paliers)")

    # gaz
    gz = sp.add_parser("gaz", help="Gaz (fiche)")
    gz.add_argument("--key", type=str, default="air", help="air, helium, hydrogene, azote, co2")
    _add_common_bool(gz)

    return p

# ========= Entrée =========
def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "optimise": cmd_optimise,
        "cylindre": cmd_cylindre,
        "batch-cylindre": cmd_batch_cylindre,
        "deplaceur": cmd_deplaceur,
        "batch-deplaceur": cmd_batch_deplaceur,
        "piston": cmd_piston,
        "paliers": cmd_paliers,
        "vilebrequin": cmd_vilebrequin,
        "volant": cmd_volant,
        "chemise": cmd_chemise,
        "visserie": cmd_visserie,
        "materiaux": cmd_materiaux,
        "gaz": cmd_gaz,
    }
    dispatch[args.cmd](args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
