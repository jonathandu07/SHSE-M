# -*- coding: utf-8 -*-
# backend/pieces/cylindre.py
"""
Dimensionnement de cylindre(s) Stirling — frontal unifié
- s'appuie sur:
    backend.modules.cylindre_core      (API scalaire)
    backend.modules.cylindre_vector    (API vectorisée NumPy)
    backend.modules.cylindre_batch_io  (I/O Pandas: CSV -> CSV)

CLI:
    python -m backend.pieces.cylindre single  --power 3000 --rpm 1500 --eta 0.85
    python -m backend.pieces.cylindre vector  --powers 1500,3000,5000 --rpms 600,900,1200 --eta 0.85
    python -m backend.pieces.cylindre batch   --in batch_cylindres.csv --out resultats.csv
"""

from __future__ import annotations
import argparse
import numpy as np

# --- Import des modules nouvellement factorisés ---
from backend.modules.cylindre_core import (
    SizingInputs as CoreInputs,
    SizingResult as CoreResult,
    size_stirling_cylinders as size_scalar,
    mean_piston_speed as mean_upiston_scalar,
)
from backend.modules.cylindre_vector import (
    size_stirling_cylinders_vector as size_vector,
)
from backend.modules.cylindre_batch_io import (
    from_csv as batch_from_csv,
    run_batch as batch_run,
    to_csv as batch_to_csv,
)

# ---------------------------
# Helpers d'affichage console
# ---------------------------

def _print_scalar_result(inp: CoreInputs, res: CoreResult):
    print("=== RÉSULTAT DIMENSIONNEMENT CYLINDRE STIRLING (scalaire) ===")
    print(f"Puissance demandée : {inp.power_W:.1f} W")
    if inp.use_pmean_model:
        pme_str = f"(≈ {res.p_me_used_Pa/1e5:.2f} bar)" if res.ok and res.p_me_used_Pa else ""
        print(f"Modèle p_mean     : p_mean={inp.p_mean/1e5:.2f} bar, k_me={inp.k_me:.2f} {pme_str}")
    else:
        print(f"BMEP utilisé      : {inp.p_me/1e5:.2f} bar")

    if res.ok:
        print(f"Nombre cylindres  : {res.n_cyl}")
        print(f"Régime retenu     : {res.rpm:.0f} tr/min")
        print(f"Alésage (B)       : {res.bore_m*1000:.2f} mm")
        print(f"Course  (S)       : {res.stroke_m*1000:.2f} mm")
        print(f"V balayé/cyl      : {res.Vs_cyl_m3*1e6:.2f} cm³")
        print(f"V balayé total    : {res.Vs_total_m3*1e6:.2f} cm³")
        Up = mean_upiston_scalar(res.stroke_m, res.rpm)
        print(f"Vitesse piston    : {Up:.3f} m/s (limite {inp.upiston_max} m/s)")
        print(res.message)
    else:
        print("ÉCHEC :", res.message)

def _print_vector_brief(res: dict):
    """
    Affichage compact pour usage rapide en mode vector.
    """
    ok = res["ok"]
    n_cyl = res["n_cyl"]
    rpm   = res["rpm"]
    B_mm  = res["bore_m"] * 1000.0
    S_mm  = res["stroke_m"] * 1000.0

    print("=== VECTOR — Résumé (par élément) ===")
    flat_idx = np.arange(ok.size).reshape(ok.shape)
    for idx in np.ndindex(ok.shape):
        i = flat_idx[idx]
        if ok[idx]:
            print(f"[{idx}] OK | n_cyl={int(n_cyl[idx])} | rpm={rpm[idx]:.0f} | B={B_mm[idx]:.2f} mm | S={S_mm[idx]:.2f} mm")
        else:
            print(f"[{idx}] NOK | message_id={int(res['message_id'][idx])}")

# ---------------------------
# Wrappers conviviaux (API)
# ---------------------------

def size_one(**kwargs) -> CoreResult:
    """
    Proxy simple vers l'API scalaire (backend.modules.cylindre_core).
    """
    inp = CoreInputs(**kwargs)
    return size_scalar(inp)

def size_grid(
    powers, rpms, eta_mech=0.85, **kwargs_vector
) -> dict:
    """
    Proxy simple vers l'API vectorisée (backend.modules.cylindre_vector).
    - powers : float ou array-like (W)
    - rpms   : float ou array-like (tr/min)
    """
    return size_vector(
        power_W=np.asarray(powers),
        rpm=np.asarray(rpms),
        eta_mech=eta_mech,
        **kwargs_vector
    )

# -----------
# CLI (argparse)
# -----------

def _add_common_scalar_args(p: argparse.ArgumentParser):
    p.add_argument("--power", type=float, required=True, help="Puissance demandée (W)")
    p.add_argument("--rpm", type=float, required=True, help="Régime (tr/min)")
    p.add_argument("--eta", type=float, default=0.85, help="Rendement mécanique (0..1)")
    p.add_argument("--pme", type=float, default=200e3, help="BMEP (Pa)")
    p.add_argument("--use-pmean", action="store_true", help="Basculer en modèle p_mean")
    p.add_argument("--pmean", type=float, default=1.0e6, help="Pression moyenne (Pa)")
    p.add_argument("--kme", type=float, default=0.20, help="Facteur p_me≈k_me*p_mean")
    p.add_argument("--upiston-max", type=float, default=2.0, help="Vitesse piston max (m/s)")
    p.add_argument("--bore-max", type=float, default=0.10, help="Alésage maximum (m)")
    p.add_argument("--sb", type=float, default=1.0, help="Rapport S/B")
    p.add_argument("--nmax", type=int, default=12, help="Nombre de cylindres max")
    p.add_argument("--allow-reduce", action="store_true", help="Autoriser réduction régime")
    p.add_argument("--min-rpm", type=float, default=300.0, help="Régime mini si réduction")

def _parse_list_floats(csv_str: str) -> np.ndarray:
    return np.array([float(x.strip()) for x in csv_str.split(",") if x.strip()])

def main():
    ap = argparse.ArgumentParser(description="Dimensionnement cylindre(s) Stirling — frontal unifié")
    sp = ap.add_subparsers(dest="cmd", required=True)

    # --- sub: single ---
    p_single = sp.add_parser("single", help="Calcul scalaire (un cas)")
    _add_common_scalar_args(p_single)

    # --- sub: vector ---
    p_vec = sp.add_parser("vector", help="Vectorisé (plusieurs puissances/régimes)")
    p_vec.add_argument("--powers", type=str, required=True, help="CSV de puissances (W), ex: 1500,3000,5000")
    p_vec.add_argument("--rpms", type=str, required=True, help="CSV de régimes (tr/min), ex: 600,900,1200")
    p_vec.add_argument("--eta", type=float, default=0.85)
    # paramètres communs
    p_vec.add_argument("--pme", type=float, default=200e3)
    p_vec.add_argument("--use-pmean", action="store_true")
    p_vec.add_argument("--pmean", type=float, default=1.0e6)
    p_vec.add_argument("--kme", type=float, default=0.20)
    p_vec.add_argument("--upiston-max", type=float, default=2.0)
    p_vec.add_argument("--bore-max", type=float, default=0.10)
    p_vec.add_argument("--sb", type=float, default=1.0)
    p_vec.add_argument("--nmax", type=int, default=12)
    p_vec.add_argument("--allow-reduce", action="store_true")
    p_vec.add_argument("--min-rpm", type=float, default=300.0)

    # --- sub: batch ---
    p_batch = sp.add_parser("batch", help="Batch CSV -> CSV (Pandas)")
    p_batch.add_argument("--in", dest="in_csv", required=True, help="Chemin CSV d'entrée")
    p_batch.add_argument("--out", dest="out_csv", required=True, help="Chemin CSV de sortie")

    args = ap.parse_args()

    if args.cmd == "single":
        res = size_one(
            power_W=args.power,
            rpm=args.rpm,
            eta_mech=args.eta,
            p_me=args.pme,
            use_pmean_model=args.use_pmean,
            p_mean=args.pmean,
            k_me=args.kme,
            upiston_max=args.upiston_max,
            bore_max=args.bore_max,
            stroke_to_bore=args.sb,
            n_cyl_max=args.nmax,
            allow_rpm_reduce=args.allow_reduce,
            min_rpm=args.min_rpm,
        )
        _print_scalar_result(CoreInputs(
            power_W=args.power, rpm=args.rpm, eta_mech=args.eta,
            p_me=args.pme, use_pmean_model=args.use_pmean, p_mean=args.pmean, k_me=args.kme,
            upiston_max=args.upiston_max, bore_max=args.bore_max, stroke_to_bore=args.sb,
            n_cyl_max=args.nmax, allow_rpm_reduce=args.allow_reduce, min_rpm=args.min_rpm
        ), res)

    elif args.cmd == "vector":
        powers = _parse_list_floats(args.powers)
        rpms   = _parse_list_floats(args.rpms)

        res = size_grid(
            powers=powers[:, None],   # grid powers x rpms (broadcast)
            rpms=rpms[None, :],
            eta_mech=args.eta,
            p_me=args.pme,
            use_pmean_model=args.use_pmean,
            p_mean=args.pmean,
            k_me=args.kme,
            upiston_max=args.upiston_max,
            bore_max=args.bore_max,
            stroke_to_bore=args.sb,
            n_cyl_max=args.nmax,
            allow_rpm_reduce=args.allow_reduce,
            min_rpm=args.min_rpm,
        )
        _print_vector_brief(res)

    elif args.cmd == "batch":
        df = batch_from_csv(args.in_csv)
        df_out = batch_run(df)
        batch_to_csv(df_out, args.out_csv)
        print(f"Batch terminé. Résultats écrits dans: {args.out_csv}")

if __name__ == "__main__":
    main()
