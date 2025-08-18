# -*- coding: utf-8 -*-
# backend/modules/optimisation.py
"""
Optimisation globale d'un moteur Stirling (pré-étude)
- Orchestre les modules 'pieces' et 'modules' existants pour évaluer une configuration.
- Variables: n_cyl, rpm, p_me, S/B, gaz (air/He/H2/N2/CO2)
- Contraintes: Upiston, B_max, et OK flags de chaque sous-système
- Objectif: masse + friction + compacité + pénalités (configurable)

NOTE: pré-dimensionnement (0-1). Pour un design final, compléter par un modèle
thermo (Schmidt/isotherme non id.), CFD échangeurs, et fatigue.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Tuple, List, Dict, Optional
import random, math

# ==== Imports des sous-modules (assumés présents dans ton repo) ====
# En cas d'absence, une ImportError te dira quoi ajouter.
from backend.modules.deplaceur_core import DeplaceurInputs, size_deplaceur
from backend.pieces.piston import PistonInputs, size_piston
from backend.pieces.paliers import BearingInputs, size_bearings
from backend.pieces.vilebrequin import CrankInputs, size_crankshaft
from backend.pieces.volant_inertie import FlywheelInputs, size_flywheel
from backend.pieces.chemise_de_cylindre import ChemiseInputs, size_chemise
from backend.pieces.visserie import ScrewSelectionInputs, select_screws
from backend.modules.meteriaux import MATERIALS, choose_material_for_part, yield_at_T
from backend.modules.gaz import get_gaz

# ======= Données d'entrée & sortie de l'optimisation =======

@dataclass
class OptiInputs:
    # Cible fonctionnelle
    power_W: float
    eta_mech: float = 0.85

    # Variables et bornes (exploration)
    rpm_range: Tuple[float, float] = (400.0, 1500.0)        # tr/min
    pme_range_Pa: Tuple[float, float] = (120e3, 400e3)      # Pa
    S_over_B_range: Tuple[float, float] = (0.8, 1.3)        # ratio S/B
    n_cyl_range: Tuple[int, int] = (1, 8)
    gases: Tuple[str, ...] = ("air", "helium", "hydrogene", "azote")  # clés get_gaz

    # Contraintes mécaniques
    bore_max_m: float = 0.10
    upiston_max_m_s: float = 2.2
    p_peak_factor: float = 6.0   # p_peak ≈ factor * p_me (ordre de grandeur)

    # Hypothèses volant/finition
    alpha_ripple: float = 0.25   # T1/Tm
    flywheel_radius_m: float = 0.18
    rim_speed_limit_m_s: float = 80.0

    # Matériaux
    liner_material_key: str = "FG250"   # chemise par défaut
    hot_head_Tmax_C: float = 800.0      # pour choix matériau culasse chaude si besoin

    # Visserie (culasse / flasque représentative)
    n_bolts_max: int = 12
    bolt_sizes: Tuple[str, ...] = ("M6", "M8", "M10")
    plate_thickness_m: float = 0.008
    friction_mode: str = "bearing"      # "bearing" ou "friction"

    # Budget d'exploration
    samples: int = 600                   # nombre d'échantillons aléatoires
    local_refine: int = 60               # itérations de raffinement local

    # Pondérations de l'objectif (scalaires)
    w_mass: float = 1.0                  # masse (kg) totalisée (volant + chemise + déplaceur)
    w_friction: float = 0.03             # friction segments (N)
    w_cyl: float = 0.4                   # pénalité par cylindre
    w_bore: float = 1.0                  # alésage (m) pour compacité
    penalty_big: float = 1e6             # pénalité dure si contrainte viole

@dataclass
class OptiCandidate:
    rpm: float
    p_me_Pa: float
    S_over_B: float
    n_cyl: int
    gas_key: str

@dataclass
class OptiResult:
    ok: bool
    message: str
    best: Dict
    top5: List[Dict]

# ======= Utilitaires dimensionnement de base =======

def _solve_bore_stroke_from_Vs(Vs: float, S_over_B: float) -> Tuple[float,float]:
    # Vs = (π/4) * B^2 * S = (π/4) * B^3 * (S/B)
    B = (4.0 * Vs / (math.pi * S_over_B)) ** (1.0/3.0)
    S = S_over_B * B
    return B, S

def _mean_piston_speed(S: float, rpm: float) -> float:
    return 2.0 * S * rpm / 60.0

def _vs_total(power_W: float, p_me: float, rpm: float, eta: float) -> float:
    # Vs_total = P / (p_me * rps * eta)
    rps = rpm / 60.0
    return power_W / max(p_me * rps * eta, 1e-9)

def _estimate_recip_mass_kg(bore_m: float, scale_ref_B: float=0.08, m_ref: float=0.35) -> float:
    # masse alternative ~ proportionnelle à l'aire piston ~ B^2 (approx)
    return m_ref * (bore_m / scale_ref_B) ** 2

# ====== Évaluation d’un candidat ======

def evaluate_candidate(cfg: OptiInputs, cand: OptiCandidate, rng: random.Random) -> Dict:
    # 0) Grandeurs cylindre
    Vs_tot = _vs_total(cfg.power_W, cand.p_me_Pa, cand.rpm, cfg.eta_mech)
    Vs_cyl = Vs_tot / cand.n_cyl
    B, S = _solve_bore_stroke_from_Vs(Vs_cyl, cand.S_over_B)
    Up = _mean_piston_speed(S, cand.rpm)

    feasible = True
    penalties = 0.0
    reasons = []

    # Contraintes géométriques de base
    if B > cfg.bore_max_m + 1e-12:
        feasible = False
        penalties += cfg.penalty_big * (B - cfg.bore_max_m) / cfg.bore_max_m
        reasons.append("bore>max")
    if Up > cfg.upiston_max_m_s + 1e-12:
        feasible = False
        penalties += cfg.penalty_big * (Up - cfg.upiston_max_m_s) / cfg.upiston_max_m_s
        reasons.append("Upiston>max")

    # 1) PISTON
    p_peak = cfg.p_peak_factor * cand.p_me_Pa
    piston_in = PistonInputs(
        bore_m=B, stroke_m=S, rpm=cand.rpm,
        p_mean_cycle_Pa=cand.p_me_Pa, p_peak_gas_Pa=p_peak,
        n_rings=2, estimate_mass=False  # on garde friction segments
    )
    piston = size_piston(piston_in)

    # 2) DÉPLACEUR
    disp_in = DeplaceurInputs(
        bore_m=B, stroke_m=S, rpm=cand.rpm,
        k_phase=1.0, dome_extra_clearance_m=0.008,
        radial_clearance_cold_m=None, min_hot_clearance_m=0.08e-3,
        alpha_material_1K=12e-6, deltaT_hotK=500.0,
        shell_thickness_m=0.4e-3, cap_thickness_m=0.5e-3,
        material_density=7900.0, core_density=60.0, use_hollow_core=True
    )
    disp = size_deplaceur(disp_in)
    if not disp.ok:
        feasible = False
        penalties += cfg.penalty_big
        reasons.append("deplaceur")

    # 3) PALIERS
    be_in = BearingInputs(
        bore_m=B, stroke_m=S, rpm=cand.rpm, n_cyl=cand.n_cyl,
        p_mean_cycle_Pa=cand.p_me_Pa, p_peak_gas_Pa=p_peak
    )
    be = size_bearings(be_in)
    if not be.ok:
        feasible = False
        penalties += cfg.penalty_big
        reasons.append("paliers")

    # 4) VILEBREQUIN
    m_rec = _estimate_recip_mass_kg(B)
    cr_in = CrankInputs(
        bore_m=B, stroke_m=S, rpm=cand.rpm, n_cyl=cand.n_cyl,
        p_mean_cycle_Pa=cand.p_me_Pa, p_peak_gas_Pa=p_peak,
        mass_recip_kg=m_rec, balance_factor=0.5
    )
    cr = size_crankshaft(cr_in)
    if not cr.ok:
        feasible = False
        penalties += cfg.penalty_big
        reasons.append("vilebrequin")

    # 5) CHEMISE (matériau & contrainte à chaud)
    mat_liner = MATERIALS[cfg.liner_material_key]
    # dé-rating de Rp0.2 à la T_hot assumée (150°C typique côté froid)
    sigma_allow_T = yield_at_T(mat_liner, 150.0)
    chem_in = ChemiseInputs(
        bore_m=B, longueur_m=max(1.1*S, 0.06),  # heuristique longueur
        p_interne_Pa=p_peak, fs=1.6,
        sigma_allow_Pa=sigma_allow_T,
        density_kg_m3=mat_liner.density_kg_m3, alpha_1K=mat_liner.alpha_1K,
        piston_alpha_1K=20.5e-6,
        radial_clearance_cold_m=None, radial_clearance_hot_min_m=0.01e-3,
        manuf_tol_radial_m=0.02e-3
    )
    chem = size_chemise(chem_in)
    if not chem.ok:
        feasible = False
        penalties += cfg.penalty_big
        reasons.append("chemise")

    # 6) VOLANT D’INERTIE
    # Vs_total par tour ~ Vs_tot (1 cycle/tr pour alpha-type) → T_mean via p_me
    fw_in = FlywheelInputs(
        p_me_Pa=cand.p_me_Pa,
        Vs_total_per_rev_m3=Vs_tot,
        eta_mech=cfg.eta_mech,
        alpha_ripple=cfg.alpha_ripple,
        k_harmonic=1,
        coeff_irregularity=0.02,
        rpm=cand.rpm,
        shape="rim",
        radius_m=cfg.flywheel_radius_m,
        rim_speed_limit_m_s=cfg.rim_speed_limit_m_s
    )
    fw = size_flywheel(fw_in)
    if not fw.speed_ok or not fw.hoop_ok:
        feasible = False
        penalties += cfg.penalty_big
        reasons.append("volant")

    # 7) VISSERIE (joint représentatif soumis à p_peak * A piston)
    A_pis = math.pi * (B**2) / 4.0
    axial = p_peak * A_pis
    screw_in = ScrewSelectionInputs(
        axial_tension_N=axial, shear_N=0.0,
        mode=cfg.friction_mode,
        n_bolts_max=cfg.n_bolts_max,
        bolt_sizes=list(cfg.bolt_sizes),
        plate_thickness_m=cfg.plate_thickness_m
    )
    screws = select_screws(screw_in)
    if not screws.ok:
        feasible = False
        penalties += cfg.penalty_big
        reasons.append("visserie")

    # === Objectif (plus petit est meilleur) ===
    mass_total = (chem.masse_kg
                  + disp.mass_total_kg
                  + fw.mass_required_kg)

    score = (
        cfg.w_mass * mass_total
        + cfg.w_friction * piston.ring_total_friction_N
        + cfg.w_cyl * cand.n_cyl
        + cfg.w_bore * B
        + penalties
    )

    return {
        "score": score,
        "feasible": feasible,
        "reasons": reasons,
        # design vars
        "rpm": cand.rpm, "p_me_Pa": cand.p_me_Pa, "S_over_B": cand.S_over_B,
        "n_cyl": cand.n_cyl, "gas": cand.gas_key,
        # key geometry
        "B_m": B, "S_m": S, "Up_m_s": Up, "Vs_cyl_m3": Vs_cyl, "Vs_tot_m3": Vs_tot,
        # modules raw (quelques extraits utiles)
        "p_peak_Pa": p_peak,
        "piston": {
            "F_peak_N": piston.F_peak_N,
            "ring_friction_N": piston.ring_total_friction_N,
            "pin_diameter_m": piston.pin_diameter_m
        },
        "deplaceur": {
            "ok": disp.ok, "mass_kg": disp.mass_total_kg,
            "clear_hot_m": disp.radial_clearance_hot_m
        },
        "paliers": {"ok": be.ok, "D_main_m": be.main_D_m, "L_main_m": be.main_L_m},
        "vilebrequin": {"ok": cr.ok, "d_pin_m": cr.pin_diameter_m, "t_web_m": cr.web_thickness_m},
        "chemise": {"ok": chem.ok, "t_m": chem.epaisseur_m, "mass_kg": chem.masse_kg},
        "volant": {"ok": (fw.speed_ok and fw.hoop_ok), "J": fw.J_required_kg_m2, "mass_kg": fw.mass_required_kg},
        "visserie": {"ok": screws.ok, "choice": f"{screws.bolt_count}x {screws.bolt_size} {screws.bolt_class}"},
    }

# ====== Optimisation globale ======

def _random_candidate(cfg: OptiInputs, rng: random.Random) -> OptiCandidate:
    n_cyl = rng.randint(cfg.n_cyl_range[0], cfg.n_cyl_range[1])
    rpm = rng.uniform(cfg.rpm_range[0], cfg.rpm_range[1])
    # échantillonnage log pour p_me
    log_pmin, log_pmax = math.log(cfg.pme_range_Pa[0]), math.log(cfg.pme_range_Pa[1])
    p_me = math.exp(rng.uniform(log_pmin, log_pmax))
    S_over_B = rng.uniform(cfg.S_over_B_range[0], cfg.S_over_B_range[1])
    gas = rng.choice(cfg.gases)
    return OptiCandidate(rpm=rpm, p_me_Pa=p_me, S_over_B=S_over_B, n_cyl=n_cyl, gas_key=gas)

def _neighbor(cand: OptiCandidate, cfg: OptiInputs, rng: random.Random) -> OptiCandidate:
    # petite perturbation locale
    def clamp(v, lo, hi): return max(lo, min(hi, v))
    rpm = clamp(cand.rpm * (1.0 + rng.uniform(-0.08, 0.08)), *cfg.rpm_range)
    p_me = clamp(cand.p_me_Pa * (1.0 + rng.uniform(-0.12, 0.12)), *cfg.pme_range_Pa)
    S_over_B = clamp(cand.S_over_B + rng.uniform(-0.05, 0.05), *cfg.S_over_B_range)
    n_cyl = int(clamp(cand.n_cyl + rng.choice([-1, 0, 1]), cfg.n_cyl_range[0], cfg.n_cyl_range[1]))
    gas = rng.choice(cfg.gases)
    return OptiCandidate(rpm=rpm, p_me_Pa=p_me, S_over_B=S_over_B, n_cyl=n_cyl, gas_key=gas)

def optimise(cfg: OptiInputs, seed: int = 42) -> OptiResult:
    rng = random.Random(seed)
    population: List[Dict] = []

    # 1) Échantillonnage global
    for _ in range(cfg.samples):
        cand = _random_candidate(cfg, rng)
        res = evaluate_candidate(cfg, cand, rng)
        population.append(res)

    # 2) Recherche locale à partir des meilleurs
    population.sort(key=lambda x: x["score"])
    bests = population[:max(10, cfg.local_refine//3)]
    for base in bests:
        cand0 = OptiCandidate(
            rpm=base["rpm"], p_me_Pa=base["p_me_Pa"],
            S_over_B=base["S_over_B"], n_cyl=base["n_cyl"], gas_key=base["gas"]
        )
        cur = base
        for _ in range(cfg.local_refine):
            neigh = _neighbor(cand0, cfg, rng)
            nres = evaluate_candidate(cfg, neigh, rng)
            if nres["score"] < cur["score"]:
                cur = nres
                cand0 = OptiCandidate(
                    rpm=cur["rpm"], p_me_Pa=cur["p_me_Pa"],
                    S_over_B=cur["S_over_B"], n_cyl=cur["n_cyl"], gas_key=cur["gas"]
                )
                population.append(cur)

    population.sort(key=lambda x: x["score"])
    top5 = population[:5]
    best = top5[0] if top5 else None
    if best is None:
        return OptiResult(ok=False, message="Aucune solution évaluée.", best={}, top5=[])

    msg = "OK" if best["feasible"] else f"Meilleure solution avec pénalités: {best['reasons']}"
    return OptiResult(ok=True, message=msg, best=best, top5=top5)

# ====== Démo ======

if __name__ == "__main__":
    cfg = OptiInputs(
        power_W=3000.0,
        eta_mech=0.85,
        rpm_range=(500, 1200),
        pme_range_Pa=(150e3, 300e3),
        S_over_B_range=(0.9, 1.2),
        n_cyl_range=(1, 6),
        gases=("air","helium"),
        bore_max_m=0.10,
        upiston_max_m_s=2.0,
        samples=400,
        local_refine=60
    )
    res = optimise(cfg, seed=123)
    print("=== OPTIMISATION ===")
    print(res.message)
    print("\n-- BEST --")
    b = res.best
    for k in ("score","rpm","p_me_Pa","S_over_B","n_cyl","B_m","S_m","Up_m_s","p_peak_Pa"):
        print(f"{k:>14} : {b[k] if k in b else '—'}")
    print("Mass(volant+chemise+déplaceur) ≈",
          b["volant"]["mass_kg"] + b["chemise"]["mass_kg"] + b["deplaceur"]["mass_kg"], "kg")
    print("Friction segments (N)     :", b["piston"]["ring_friction_N"])
    print("Visserie                  :", b["visserie"]["choice"])
    print("\n-- TOP5 scores --")
    for i, s in enumerate(res.top5, 1):
        print(f"{i:02d}. score={s['score']:.3f} | n_cyl={s['n_cyl']} | rpm={s['rpm']:.0f} | B={s['B_m']*1000:.1f} mm")
