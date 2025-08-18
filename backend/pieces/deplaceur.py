# -*- coding: utf-8 -*-
# backend/pieces/deplaceur.py
"""
Frontal unifié — Déplaceur Stirling (dépendant du cylindre)

Appelle:
  - backend.modules.cylindre_core / cylindre_vector   (pour obtenir B,S si non fournis)
  - backend.modules.deplaceur_core / deplaceur_vector
  - backend.modules.deplaceur_batch_io   (Pandas)

CLI:
  # a) B et S fournis directement
  python -m backend.pieces.deplaceur single --bore 0.08 --stroke 0.08 --rpm 600

  # b) B,S déduits d'un sizing cylindre
  python -m backend.pieces.deplaceur single --power 3000 --rpm 900 --eta 0.85 --pme 200000

  # c) Vectorisé : grille puissances×régimes -> cylindre (B,S) -> déplaceur
  python -m backend.pieces.deplaceur vector --powers 1500,3000 --rpms 600,900 --eta 0.85

  # d) Batch CSV : nécessite colonnes bore_m, stroke_m (dimension cylindre déjà faite)
  python -m backend.pieces.deplaceur batch --in in.csv --out out.csv
"""

from __future__ import annotations
import argparse
import sys
import numpy as np

# ------ Déplaceur (core + vector + batch) ------
from backend.modules.deplaceur_core import (
    DeplaceurInputs as DepInputs,
    DeplaceurResult as DepResult,
    size_deplaceur as dep_scalar,
)
from backend.modules.deplaceur_vector import (
    size_deplaceur_vector as dep_vector,
)
from backend.modules.deplaceur_batch_io import (
    from_csv as dep_from_csv,
    run_batch as dep_run_batch,
    to_csv as dep_to_csv,
)

# ------ Cylindre (pour obtenir B,S si non fournis) ------
from backend.modules.cylindre_core import (
    SizingInputs as CylInputs,
    size_stirling_cylinders as cyl_scalar,
)
from backend.modules.cylindre_vector import (
    size_stirling_cylinders_vector as cyl_vector,
)

# ---------------------------
# Affichages
# ---------------------------

def _print_scalar(res: DepResult, inp: DepInputs):
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
            print(f"{idx}: NOK | {msg_map.get(int(res['message_id'][idx]), 'NOK')}")

# ---------------------------
# Helpers
# ---------------------------

def _csv_floats(s: str) -> np.ndarray:
    vals = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            vals.append(float(tok))
        except ValueError:
            raise argparse.ArgumentTypeError(f"Valeur non numérique: '{tok}'")
    if not vals:
        raise argparse.ArgumentTypeError("Liste vide.")
    return np.array(vals, dtype=float)

def _scalar_bore_stroke_from_cyl(power, rpm, eta, pme, use_pmean, pmean, kme,
                                 Up_max, bmax, S_over_B, nmax, allow_reduce, min_rpm):
    """Calcule (B,S,rpm_out) via cylindre_core à partir d’exigences."""
    req = CylInputs(
        power_W=power, rpm=rpm, eta_mech=eta,
        p_me=pme, use_pmean_model=use_pmean, p_mean=pmean, k_me=kme,
        upiston_max=Up_max, bore_max=bmax, stroke_to_bore=S_over_B,
        n_cyl_max=nmax, allow_rpm_reduce=allow_reduce, min_rpm=min_rpm
    )
    cres = cyl_scalar(req)
    if not cres.ok:
        raise RuntimeError("Dimensionnement cylindre impossible : " + cres.message)
    return cres.bore_m, cres.stroke_m, cres.rpm

def _vector_bore_stroke_from_cyl(powers, rpms, eta, pme, use_pmean, pmean, kme,
                                 Up_max, bmax, S_over_B, nmax, allow_reduce, min_rpm):
    """Renvoie dict avec B,S,rpm_out en grille (Np×Nr) via cylindre_vector."""
    c = cyl_vector(
        power_W=powers, rpm=rpms, eta_mech=eta,
        p_me=pme, use_pmean_model=use_pmean, p_mean=pmean, k_me=kme,
        upiston_max=Up_max, bore_max=bmax, stroke_to_bore=S_over_B,
        n_cyl_max=nmax, allow_rpm_reduce=allow_reduce, min_rpm=min_rpm
    )
    if not np.any(c["ok"]):
        raise RuntimeError("Aucune combinaison puissance×régime ne passe (cylindre).")
    return {"B": c["bore_m"], "S": c["stroke_m"], "rpm": c["rpm"], "ok": c["ok"]}

# ---------------------------
# Calculs
# ---------------------------

def size_one_with_cyl_link(args) -> DepResult:
    """
    Mode scalaire :
      - si --bore & --stroke présents → utilise directement
      - sinon → calcule d'abord le cylindre à partir de --power/--rpm/--eta/...
    """
    if args.bore is not None and args.stroke is not None:
        B, S, rpm_use = args.bore, args.stroke, args.rpm
    else:
        if args.power is None or args.rpm is None or args.eta is None:
            raise RuntimeError("Fournis soit --bore & --stroke, soit --power --rpm --eta (et pme/pmean/kme).")
        B, S, rpm_use = _scalar_bore_stroke_from_cyl(
            power=args.power, rpm=args.rpm, eta=args.eta,
            pme=args.pme, use_pmean=args.use_pmean, pmean=args.pmean, kme=args.kme,
            Up_max=args.upiston_max, bmax=args.bore_max, S_over_B=args.sb,
            nmax=args.nmax, allow_reduce=args.allow_reduce, min_rpm=args.min_rpm
        )

    inp = DepInputs(
        bore_m=B, stroke_m=S,
        k_phase=args.k_phase,
        dome_extra_clearance_m=args.dome_clear,
        radial_clearance_cold_m=None if np.isnan(args.clearance_cold) else args.clearance_cold,
        min_hot_clearance_m=args.clearance_hot_min,
        alpha_material_1K=args.alpha, deltaT_hotK=args.dT, manuf_tol_radial_m=args.tol,
        shell_thickness_m=args.shell_t, cap_thickness_m=args.cap_t,
        material_density=args.rho, core_density=args.rho_core, use_hollow_core=args.core,
        rod_length_m=None if np.isnan(args.rod_L) else args.rod_L,
        rod_diameter_m=args.rod_d, young_modulus_Pa=args.E,
        rpm=rpm_use, gas_dynamic_dp_Pa=args.dp,
        acceptable_leak_index=args.leak_max
    )
    res = dep_scalar(inp)
    _print_scalar(res, inp)
    return res

def size_grid_with_cyl_link(args) -> dict:
    """
    Mode vector :
      - si --bores & --strokes fournis → utilise directement (grille bores×strokes)
      - sinon → utilise --powers & --rpms (& eta, pme…) pour obtenir B,S via cylindre_vector
    """
    if args.bores and args.strokes:
        bores = _csv_floats(args.bores)[:, None]
        strokes = _csv_floats(args.strokes)[None, :]
        rpm_mat = np.full_like(bores * strokes, fill_value=args.rpm, dtype=float)
        mask_ok = np.ones_like(rpm_mat, dtype=bool)
        Bmat, Smat = bores, strokes
    else:
        if args.powers is None or args.rpms is None:
            raise RuntimeError("En vector : fournis (--bores & --strokes) OU (--powers & --rpms).")
        powers = _csv_floats(args.powers)[:, None]
        rpms   = _csv_floats(args.rpms)[None, :]
        cyl = _vector_bore_stroke_from_cyl(
            powers=powers, rpms=rpms, eta=args.eta,
            pme=args.pme, use_pmean=args.use_pmean, pmean=args.pmean, kme=args.kme,
            Up_max=args.upiston_max, bmax=args.bore_max, S_over_B=args.sb,
            nmax=args.nmax, allow_reduce=args.allow_reduce, min_rpm=args.min_rpm
        )
        Bmat, Smat, rpm_mat, mask_ok = cyl["B"], cyl["S"], cyl["rpm"], cyl["ok"]

    # Appel vectorisé déplaceur
    res = dep_vector(
        bore_m=Bmat, stroke_m=Smat,
        k_phase=args.k_phase, dome_extra_clearance_m=args.dome_clear,
        radial_clearance_cold_m=None,  # auto en fonction ΔT
        min_hot_clearance_m=args.clearance_hot_min,
        alpha_material_1K=args.alpha, deltaT_hotK=args.dT, manuf_tol_radial_m=args.tol,
        shell_thickness_m=args.shell_t, cap_thickness_m=args.cap_t,
        material_density=args.rho, core_density=args.rho_core, use_hollow_core=args.core,
        rod_length_m=None if np.isnan(args.rod_L) else args.rod_L,
        rod_diameter_m=args.rod_d, young_modulus_Pa=args.E,
        rpm=rpm_mat, gas_dynamic_dp_Pa=args.dp,
        acceptable_leak_index=args.leak_max
    )

    # Si la pré-étape cylindre marquait des NOK, on propage un message_id distinct (4)
    if "message_id" in res:
        msg = res["message_id"]
        msg = np.where(mask_ok, msg, np.full_like(msg, 4))  # 4 = échec cylindre
        res["message_id"] = msg
        res["ok"] = res["ok"] & mask_ok

    _print_vector_brief(res)
    return res

# ---------------------------
# CLI
# ---------------------------

def build_parser():
    ap = argparse.ArgumentParser(description="Déplaceur Stirling — frontal unifié (dépend cylindre)")
    sp = ap.add_subparsers(dest="cmd", required=True)

    # ---- single ----
    p1 = sp.add_parser("single", help="Un seul cas (scalaire)")

    # Option A: B,S fournis
    p1.add_argument("--bore", type=float, help="Alésage B (m)")
    p1.add_argument("--stroke", type=float, help="Course S (m)")

    # Option B: via cylindre (power/rpm/eta…)
    p1.add_argument("--power", type=float, help="Puissance visée (W) pour sizing cylindre")
    p1.add_argument("--rpm", type=float, help="Régime (tr/min)", required=False, default=None)
    p1.add_argument("--eta", type=float, help="Rdt mécanique", default=0.85)
    p1.add_argument("--pme", type=float, default=200e3)
    p1.add_argument("--use-pmean", action="store_true")
    p1.add_argument("--pmean", type=float, default=1.0e6)
    p1.add_argument("--kme", type=float, default=0.20)
    p1.add_argument("--upiston-max", type=float, default=2.0)
    p1.add_argument("--bore-max", type=float, default=0.10)
    p1.add_argument("--sb", type=float, default=1.0)
    p1.add_argument("--nmax", type=int, default=12)
    p1.add_argument("--allow-reduce", action="store_true")
    p1.add_argument("--min-rpm", type=float, default=300.0)

    # Paramètres propres déplaceur
    p1.add_argument("--k-phase", type=float, default=1.0)
    p1.add_argument("--dome-clear", type=float, default=0.02)
    p1.add_argument("--clearance-hot-min", type=float, default=0.08e-3)
    p1.add_argument("--alpha", type=float, default=12e-6)
    p1.add_argument("--dT", type=float, default=500.0)
    p1.add_argument("--tol", type=float, default=0.03e-3)
    p1.add_argument("--shell-t", type=float, default=0.5e-3)
    p1.add_argument("--cap-t", type=float, default=0.6e-3)
    p1.add_argument("--rho", type=float, default=8000.0)
    p1.add_argument("--core", action="store_true", help="Déplaceur creux (coeur léger)")
    p1.add_argument("--rho-core", type=float, default=50.0)
    p1.add_argument("--rod-L", type=float, default=float("nan"))
    p1.add_argument("--rod-d", type=float, default=4e-3)
    p1.add_argument("--E", type=float, default=200e9)
    p1.add_argument("--dp", type=float, default=2000.0, help="ΔP dynamique (Pa)")
    p1.add_argument("--leak-max", type=float, default=1.5e-4)
    p1.add_argument("--clearance-cold", type=float, default=float("nan"))

    # ---- vector ----
    p2 = sp.add_parser("vector", help="Vectorisé (bores×strokes OU powers×rpms)")

    # Option A: bores/strokes explicites
    p2.add_argument("--bores", type=str, help="CSV d'alésages (m), ex: 0.06,0.07,0.08")
    p2.add_argument("--strokes", type=str, help="CSV de courses (m), ex: 0.06,0.08")

    # Option B: via cylindre
    p2.add_argument("--powers", type=str, help="CSV puissances (W)")
    p2.add_argument("--rpms", type=str, help="CSV régimes (tr/min)")
    p2.add_argument("--eta", type=float, default=0.85)
    p2.add_argument("--pme", type=float, default=200e3)
    p2.add_argument("--use-pmean", action="store_true")
    p2.add_argument("--pmean", type=float, default=1.0e6)
    p2.add_argument("--kme", type=float, default=0.20)
    p2.add_argument("--upiston-max", type=float, default=2.0)
    p2.add_argument("--bore-max", type=float, default=0.10)
    p2.add_argument("--sb", type=float, default=1.0)
    p2.add_argument("--nmax", type=int, default=12)
    p2.add_argument("--allow-reduce", action="store_true")
    p2.add_argument("--min-rpm", type=float, default=300.0)

    # Paramètres propres déplaceur
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
    p2.add_argument("--rpm", type=float, default=600.0, help="Rpm si bores/strokes fournis")
    p2.add_argument("--dp", type=float, default=2000.0)
    p2.add_argument("--leak-max", type=float, default=1.5e-4)

    # ---- batch ----
    p3 = sp.add_parser("batch", help="Batch CSV → CSV (Pandas) (requiert bore_m & stroke_m)")
    p3.add_argument("--in", dest="in_csv", required=True)
    p3.add_argument("--out", dest="out_csv", required=True)

    return ap

def main() -> int:
    ap = build_parser()
    args = ap.parse_args()
    try:
        if args.cmd == "single":
            size_one_with_cyl_link(args)
            return 0
        elif args.cmd == "vector":
            size_grid_with_cyl_link(args)
            return 0
        elif args.cmd == "batch":
            df = dep_from_csv(args.in_csv)
            df_out = dep_run_batch(df)
            dep_to_csv(df_out, args.out_csv)
            print(f"Batch terminé. Résultats écrits dans: {args.out_csv}")
            return 0
        else:
            ap.print_help()
            return 2
    except Exception as e:
        print(f"[ERREUR] {type(e).__name__}: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
