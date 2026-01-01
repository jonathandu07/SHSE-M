from dataclasses import dataclass
from typing import Dict

@dataclass
class Material:
    name: str
    category: str # Steel, Aluminum, Titanium, Iron, Other
    density: float # kg/m3
    yield_strength: float # Pa (Re)
    young_modulus: float # Pa (E)
    fatigue_limit: float # Pa (Endurance limit approx)

MATERIALS_DB: Dict[str, Material] = {
    # Steels
    "S235JR": Material("Acier de Construction S235", "Steel", 7850, 235e6, 210e9, 110e6),
    "C45": Material("Acier C45 (Non Traité)", "Steel", 7850, 370e6, 210e9, 200e6),
    "42CrMo4_QT": Material("Acier 42CrMo4 (Trempé Revenu)", "Steel", 7850, 900e6, 210e9, 450e6),
    "16MnCr5": Material("Acier 16MnCr5 (Cémenté)", "Steel", 7800, 600e6, 210e9, 300e6),
    "316L": Material("Inox 316L", "Steel", 8000, 200e6, 193e9, 150e6),
    
    # Aluminums
    "Alu_6061_T6": Material("Alu 6061 T6", "Aluminum", 2700, 276e6, 69e9, 96e6),
    "Alu_7075_T6": Material("Alu 7075 T6 (Aéro)", "Aluminum", 2810, 503e6, 71e9, 159e6),
    "Alu_AS7G": Material("Alu Fonderie AS7G", "Aluminum", 2650, 200e6, 75e9, 80e6),
    "Alu_2618A": Material("Alu 2618A (Piston Haute Temp)", "Aluminum", 2770, 370e6, 74e9, 125e6),
    
    # Cast Iron
    "FGL_250": Material("Fonte Grise FGL 250", "Iron", 7200, 250e6, 100e9, 130e6), # Re approx Rupture for brittle
    "FGS_500": Material("Fonte Graphite Sphéroïdal 500", "Iron", 7100, 320e6, 170e9, 220e6),
    
    # High Performance
    "Titanium_TA6V": Material("Titane Ti-6Al-4V", "Titanium", 4430, 880e6, 113e9, 500e6),
}

def get_material(name: str) -> Material:
    return MATERIALS_DB.get(name, MATERIALS_DB["S235JR"]) # Default to basic steel

def list_materials_by_category(category: str = None) -> list[str]:
    if category:
        return [k for k, v in MATERIALS_DB.items() if v.category == category]
    return list(MATERIALS_DB.keys())
