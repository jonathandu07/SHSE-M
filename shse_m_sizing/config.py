from dataclasses import dataclass, field
from typing import Literal, Optional, List

@dataclass
class Efficiencies:
    eta_th: float = 0.22      # Thermal efficiency
    eta_m: float = 0.85       # Mechanical efficiency
    eta_gen: float = 0.90     # Generator efficiency
    eta_elec: float = 0.95    # Power electronics efficiency
    eta_charge: float = 0.95  # Charging efficiency

    @property
    def eta_global(self) -> float:
        return self.eta_th * self.eta_m * self.eta_gen * self.eta_elec * self.eta_charge

@dataclass
class Constraints:
    U_p_max: float = 6.0         # Max mean piston speed [m/s]
    S_over_B: float = 1.0        # Stroke to Bore ratio
    phi: float = 0.35            # p_me / p_max ratio
    sigma_adm_steel: float = 400e6     # Allowable stress Steel [Pa] (e.g., 42CrMo4)
    sigma_adm_alum: float = 150e6      # Allowable stress Aluminum [Pa]
    safety_factor: float = 2.0         # Global Safety Factor
    rod_lambda: float = 3.5            # Rod length / Crank radius
    flywheel_Cf: float = 0.05          # Coefficient of fluctuation
    bearing_L10h: float = 5000         # Target bearing life [hours]
    max_diameter_limit: Optional[float] = None # Constraint on max outer dim

@dataclass
class InputParameters:
    P_batt_target: float       # kW
    N_rpm: float               # rpm
    p_me_target_bar: float     # bar
    eta: Efficiencies = field(default_factory=Efficiencies)
    limits: Constraints = field(default_factory=Constraints)
    N_cyl: int = 1             # 0 = auto-detect (not implemented in v1, defaulting to 1 or explicit)
    fluid: str = "AIR"
    T_cold: float = 330.0      # K
    p_me_target_pa: float = field(init=False)

    def __post_init__(self):
        self.p_me_target_pa = self.p_me_target_bar * 1e5

@dataclass
class DimensionResults:
    # Power
    P_shaft_req: float = 0.0
    P_indicated_req: float = 0.0
    
    # Cylinder Geometry
    Vd_total: float = 0.0
    Vd_cyl: float = 0.0
    Bore: float = 0.0
    Stroke: float = 0.0
    U_mean: float = 0.0
    
    # Forces & Pressures
    p_max: float = 0.0
    F_max: float = 0.0
    Torque_mean: float = 0.0
    
    # Components
    wall_thickness: float = 0.0
    cyl_outer_diameter: float = 0.0
    rod_length: float = 0.0
    rod_diameter: float = 0.0 # simplified circular section
    crank_radius: float = 0.0
    pin_diameter: float = 0.0
    web_width: float = 0.0
    flywheel_inertia: float = 0.0
    flywheel_mass: float = 0.0
    flywheel_diameter: float = 0.0
    water_jacket_area: float = 0.0
    
    # Warnings
    warnings: List[str] = field(default_factory=list)

