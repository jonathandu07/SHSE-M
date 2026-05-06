from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


def _fmt(value: float, unit: str, digits: int = 1) -> str:
    return f"{value:.{digits}f} {unit}"


@dataclass
class DriveChainGenerator:
    """Builds a compact drivetrain summary for the GUI.

    This is not a detailed design authority. It provides deterministic,
    documented estimates so the app can run and display coherent first-pass
    sizing data.
    """

    eta_inverter: float = 0.97
    eta_motor: float = 0.92
    eta_alternator: float = 0.90
    eta_gearbox: float = 0.96
    bus_voltage_v: float = 400.0
    battery_density_kwh_kg: float = 0.18
    usable_soc_window: float = 0.80
    autonomy_h_at_target: float = 0.50
    aux_power_kw: float = 5.0
    charge_power_kw: float = 20.0
    results: dict[str, dict[str, Any]] = field(default_factory=dict)

    def compute(self, puissance_traction_kw: float, *, charger_batterie: bool = True) -> dict[str, dict[str, Any]]:
        if not isinstance(puissance_traction_kw, (int, float)) or not math.isfinite(float(puissance_traction_kw)):
            raise ValueError("puissance_traction_kw must be a finite number.")
        p_wheel_kw = float(puissance_traction_kw)
        if p_wheel_kw <= 0.0:
            raise ValueError("puissance_traction_kw must be > 0.")

        charge_kw = self.charge_power_kw if charger_batterie else 0.0
        p_motor_elec_kw = p_wheel_kw / self.eta_motor
        p_bus_kw = p_motor_elec_kw / self.eta_inverter + self.aux_power_kw + charge_kw
        p_alt_meca_kw = p_bus_kw / self.eta_alternator

        energy_useful_kwh = max(p_wheel_kw * self.autonomy_h_at_target, 1.0)
        energy_nominal_kwh = energy_useful_kwh / self.usable_soc_window
        battery_mass_kg = energy_nominal_kwh / self.battery_density_kwh_kg
        bus_current_a = (p_bus_kw * 1000.0) / self.bus_voltage_v

        rpm_ref = 1000.0
        omega_ref = 2.0 * math.pi * rpm_ref / 60.0
        torque_alt_nm = (p_alt_meca_kw * 1000.0) / omega_ref

        self.results = {
            "moteur_electrique": {
                "puissance_roues": _fmt(p_wheel_kw, "kW"),
                "puissance_elec_moteur": _fmt(p_motor_elec_kw, "kW"),
                "rendement_moteur": f"{self.eta_motor:.2f}",
            },
            "batterie": {
                "energie_utile": _fmt(energy_useful_kwh, "kWh"),
                "energie_nominale": _fmt(energy_nominal_kwh, "kWh"),
                "masse_estimee": _fmt(battery_mass_kg, "kg"),
                "tension_bus": _fmt(self.bus_voltage_v, "V", 0),
                "courant_bus_design": _fmt(bus_current_a, "A", 0),
            },
            "alternateur": {
                "puissance_electrique": _fmt(p_bus_kw, "kW"),
                "puissance_mecanique": _fmt(p_alt_meca_kw, "kW"),
                "rendement": f"{self.eta_alternator:.2f}",
                "couple_a_1000rpm": _fmt(torque_alt_nm, "Nm"),
            },
            "boite_crabots": {
                "rendement": f"{self.eta_gearbox:.2f}",
                "couple_design": _fmt(torque_alt_nm / self.eta_gearbox, "Nm"),
                "regime_reference": _fmt(rpm_ref, "tr/min", 0),
            },
        }
        return self.results
