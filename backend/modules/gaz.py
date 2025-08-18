# # backend\modules\gaz.py
"""
Module gaz pour moteur Stirling

Contient les gaz pertinents pour le calcul thermodynamique :
- Hélium (He)
- Hydrogène (H2)
- Azote (N2)
- Dioxyde de carbone (CO2)
- Air (mélange O2, N2, Ar, CO2)

Chaque gaz est décrit par :
- Nom
- Symbole
- Masse molaire (g/mol)
- Cp (chaleur massique à pression constante, J/kg/K)
- Cv (chaleur massique à volume constant, J/kg/K)
- Gamma = Cp/Cv
- Conductivité thermique (W/m/K) → important pour la vitesse des échanges thermiques
"""

from dataclasses import dataclass

@dataclass
class Gaz:
    nom: str
    symbole: str
    M: float           # Masse molaire (g/mol)
    Cp: float          # J/kg/K
    Cv: float          # J/kg/K
    gamma: float       # Cp/Cv
    k: float           # conductivité thermique (W/m/K)

# Base de données gaz pertinents
GAZES = {
    "helium": Gaz(
        nom="Hélium",
        symbole="He",
        M=4.0026,
        Cp=5193,  # J/kg/K
        Cv=3116,
        gamma=1.66,
        k=0.151
    ),
    "hydrogene": Gaz(
        nom="Hydrogène",
        symbole="H2",
        M=2.016,
        Cp=14300,
        Cv=10100,
        gamma=1.41,
        k=0.168
    ),
    "azote": Gaz(
        nom="Azote",
        symbole="N2",
        M=28.014,
        Cp=1040,
        Cv=743,
        gamma=1.40,
        k=0.026
    ),
    "co2": Gaz(
        nom="Dioxyde de carbone",
        symbole="CO2",
        M=44.01,
        Cp=844,
        Cv=655,
        gamma=1.29,
        k=0.016
    ),
    "air": Gaz(
        nom="Air (≈ 78% N2, 21% O2, traces Ar, CO2)",
        symbole="Air",
        M=28.97,   # masse molaire moyenne
        Cp=1005,
        Cv=718,
        gamma=1.40,
        k=0.026
    ),
}

def get_gaz(nom: str) -> Gaz:
    """
    Retourne un objet Gaz à partir de son nom (insensible à la casse).
    """
    key = nom.lower()
    if key not in GAZES:
        raise ValueError(f"Gaz '{nom}' non disponible. Options : {list(GAZES.keys())}")
    return GAZES[key]

if __name__ == "__main__":
    # Exemple d'utilisation
    gaz = get_gaz("air")
    print(f"Gaz choisi : {gaz.nom}")
    print(f"γ = {gaz.gamma}, Cp = {gaz.Cp} J/kg/K, k = {gaz.k} W/m/K")
