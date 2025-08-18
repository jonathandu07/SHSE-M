# backend\modules\cylindre_core.py
"""
Cœur scalaire du dimensionnement cylindre (BMEP + contraintes).
Réutilisé par la couche vectorisée.
"""

import math
from dataclasses import dataclass

@dataclass
class SizingInputs:
    power_W: float
    rpm: float
    eta_mech: float
    p_me: float = 200e3
    use_pmean_model: bool = False
    p_mean: float = 1.0e6
    k_me: float = 0.20
    upiston_max: float = 2.0
    bore_max: float = 0.10
    stroke_to_bore: float = 1.0
    n_cyl_max: int = 12
    allow_rpm_reduce: bool = True
    min_rpm: float = 300.0

@dataclass
class SizingResult:
    ok: bool
    message: str
    n_cyl: int | None = None
    rpm: float | None = None
    bore_m: float | None = None
    stroke_m: float | None = None
    Vs_cyl_m3: float | None = None
    Vs_total_m3: float | None = None
    p_me_used_Pa: float | None = None

def mean_piston_speed(stroke_m: float, rpm: float) -> float:
    return 2.0 * stroke_m * rpm / 60.0

def solve_bore_stroke_from_Vs(Vs: float, S_over_B: float):
    # Vs = (pi/4) * B^2 * S = (pi/4) * B^3 * (S/B) = (pi/4) * B^3 * S_over_B
    B = (4.0 * Vs / (math.pi * S_over_B)) ** (1.0/3.0)
    S = S_over_B * B
    return B, S

def size_stirling_cylinders(inp: SizingInputs) -> SizingResult:
    p_me = inp.k_me * inp.p_mean if inp.use_pmean_model else inp.p_me
    rps = inp.rpm / 60.0
    denom = p_me * rps * inp.eta_mech
    if denom <= 0:
        return SizingResult(False, "Paramètres invalides (p_me, rpm ou eta_mech).")

    Vs_total = inp.power_W / denom
    if Vs_total <= 0:
        return SizingResult(False, "Puissance/paramètres non cohérents (Vs_total <= 0).")

    def try_all(rpm_val: float):
        for n_cyl in range(1, inp.n_cyl_max + 1):
            Vs_cyl = Vs_total / n_cyl
            B, S = solve_bore_stroke_from_Vs(Vs_cyl, inp.stroke_to_bore)
            if B > inp.bore_max:
                continue
            if mean_piston_speed(S, rpm_val) > inp.upiston_max:
                continue
            return SizingResult(
                True, "Dimensionnement réussi.",
                n_cyl=n_cyl, rpm=rpm_val, bore_m=B, stroke_m=S,
                Vs_cyl_m3=Vs_cyl, Vs_total_m3=Vs_total, p_me_used_Pa=p_me
            )
        return None

    # 1) Régime nominal
    res = try_all(inp.rpm)
    if res:
        return res

    # 2) Réduction de régime (si autorisée)
    if inp.allow_rpm_reduce:
        for rpm_candidate in [max(inp.min_rpm, x) for x in
                              [int(inp.rpm*0.8), int(inp.rpm*0.6), int(inp.rpm*0.5),
                               int(inp.rpm*0.4), int(inp.rpm*0.33), int(inp.rpm*0.25)]]:
            if rpm_candidate < inp.min_rpm:
                continue
            res = try_all(float(rpm_candidate))
            if res:
                return res

    return SizingResult(
        False,
        "Aucune solution. Augmenter p_me/n_cyl/bore_max ou baisser Upiston/rpm."
    )