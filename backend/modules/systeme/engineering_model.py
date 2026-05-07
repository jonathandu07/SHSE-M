from __future__ import annotations

import math
from dataclasses import dataclass, field


def _require_positive(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number.")
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{name} must be > 0.")
    return value


@dataclass(frozen=True)
class DimensioningEngine:
    """Small physical sizing core used by backend.main.

    The model intentionally stays simple and explicit. It uses the Stirling
    Beale relation:

        P = Bn * p_mean * Vd_total * f

    where f is the shaft frequency in revolutions per second.
    """

    p_elec_kw: float
    rpm: float = 1000.0
    p_mean_bar: float = 20.0
    n_cyl: int = 4
    bn: float = 0.15
    eta_alternateur: float = 0.90
    bore_stroke_ratio: float = 1.0
    safety_pressure_factor: float = 2.5

    p_elec_w: float = field(init=False)
    p_meca_needed_w: float = field(init=False)
    p_meca_needed_kw: float = field(init=False)
    p_mean_pa: float = field(init=False)
    p_safety_bar: float = field(init=False)
    vd_total_m3: float = field(init=False)
    vd_total_liters: float = field(init=False)
    vd_unit_m3: float = field(init=False)
    bore_m: float = field(init=False)
    bore_mm: float = field(init=False)
    stroke_m: float = field(init=False)
    stroke_mm: float = field(init=False)
    torque_mean_nm: float = field(init=False)

    def __post_init__(self) -> None:
        p_elec_kw = _require_positive("p_elec_kw", self.p_elec_kw)
        rpm = _require_positive("rpm", self.rpm)
        p_mean_bar = _require_positive("p_mean_bar", self.p_mean_bar)
        bn = _require_positive("bn", self.bn)
        eta_alt = _require_positive("eta_alternateur", self.eta_alternateur)
        bore_stroke_ratio = _require_positive("bore_stroke_ratio", self.bore_stroke_ratio)
        safety_factor = _require_positive("safety_pressure_factor", self.safety_pressure_factor)

        if not isinstance(self.n_cyl, int) or self.n_cyl <= 0:
            raise ValueError("n_cyl must be an integer > 0.")
        if eta_alt > 1.0:
            raise ValueError("eta_alternateur must be <= 1.")

        p_elec_w = p_elec_kw * 1000.0
        p_meca_needed_w = p_elec_w / eta_alt
        p_mean_pa = p_mean_bar * 1.0e5
        rev_per_s = rpm / 60.0

        vd_total_m3 = p_meca_needed_w / (bn * p_mean_pa * rev_per_s)
        vd_unit_m3 = vd_total_m3 / float(self.n_cyl)

        # V = pi/4 * B^2 * S and B/S = ratio.
        stroke_m = ((4.0 * vd_unit_m3) / (math.pi * bore_stroke_ratio**2.0)) ** (1.0 / 3.0)
        bore_m = bore_stroke_ratio * stroke_m

        omega = 2.0 * math.pi * rpm / 60.0
        torque_mean_nm = p_meca_needed_w / omega

        object.__setattr__(self, "p_elec_w", p_elec_w)
        object.__setattr__(self, "p_meca_needed_w", p_meca_needed_w)
        object.__setattr__(self, "p_meca_needed_kw", p_meca_needed_w / 1000.0)
        object.__setattr__(self, "p_mean_pa", p_mean_pa)
        object.__setattr__(self, "p_safety_bar", p_mean_bar * safety_factor)
        object.__setattr__(self, "vd_total_m3", vd_total_m3)
        object.__setattr__(self, "vd_total_liters", vd_total_m3 * 1000.0)
        object.__setattr__(self, "vd_unit_m3", vd_unit_m3)
        object.__setattr__(self, "stroke_m", stroke_m)
        object.__setattr__(self, "stroke_mm", stroke_m * 1000.0)
        object.__setattr__(self, "bore_m", bore_m)
        object.__setattr__(self, "bore_mm", bore_m * 1000.0)
        object.__setattr__(self, "torque_mean_nm", torque_mean_nm)

    def as_dict(self) -> dict[str, float | int]:
        return {
            "p_elec_kw": self.p_elec_kw,
            "p_meca_needed_kw": self.p_meca_needed_kw,
            "rpm": self.rpm,
            "p_mean_bar": self.p_mean_bar,
            "p_safety_bar": self.p_safety_bar,
            "n_cyl": self.n_cyl,
            "bn": self.bn,
            "vd_total_liters": self.vd_total_liters,
            "bore_mm": self.bore_mm,
            "stroke_mm": self.stroke_mm,
            "torque_mean_nm": self.torque_mean_nm,
        }
