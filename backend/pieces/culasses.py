# backend\pieces\culasses.py
"""
Module Culasses pour moteur Stirling

Dimensionnement simplifié :
- Ø d’appui ≈ B (alésage du cylindre)
- Épaisseur dictée par la pression interne et le diamètre
- Surface utile pour échange thermique ∝ B² (surface plane) ou périmètre × longueur d’ailettes

Hypothèses :
- Épaisseur calculée comme une plaque circulaire pressurisée
- Coefficients de sécurité intégrés
"""

import math
from dataclasses import dataclass

@dataclass
class Culasse:
    diametre: float          # Diamètre d'appui (m)
    epaisseur: float         # Épaisseur (m)
    surface_echange: float   # Surface utile pour échange thermique (m²)
    surface_avec_ailettes: float  # Surface si ailettes (m²)

def dimensionner_culasse(B: float, pression: float, sigma_max: float, longueur_ailettes: float = 0.05, n_ailettes: int = 20) -> Culasse:
    """
    Dimensionne une culasse de Stirling.
    
    Args:
        B (float): Diamètre du cylindre (m)
        pression (float): Pression interne max (Pa)
        sigma_max (float): Contrainte admissible du matériau (Pa)
        longueur_ailettes (float): Longueur typique des ailettes (m)
        n_ailettes (int): Nombre d’ailettes radiales
    
    Returns:
        Culasse: Objet contenant les dimensions calculées
    """
    rayon = B / 2

    # 1. Épaisseur plaque circulaire sous pression (approximation mécanique des milieux continus)
    # σ = (pression * rayon) / (2 * epaisseur)  => epaisseur >= (pression * rayon) / (2 * sigma_max)
    epaisseur = (pression * rayon) / (2 * sigma_max)

    # 2. Surface utile d’échange (surface plane)
    surface_plane = math.pi * rayon**2

    # 3. Surface avec ailettes (approx : périmètre * longueur * nb_ailettes)
    perimetre = math.pi * B
    surface_ailettes = perimetre * longueur_ailettes * n_ailettes

    return Culasse(
        diametre=B,
        epaisseur=epaisseur,
        surface_echange=surface_plane,
        surface_avec_ailettes=surface_plane + surface_ailettes
    )

if __name__ == "__main__":
    # Exemple
    culasse = dimensionner_culasse(
        B=0.08,               # 80 mm de diamètre
        pression=3e6,         # 3 MPa
        sigma_max=250e6,      # Acier 250 MPa admissible
        longueur_ailettes=0.03,
        n_ailettes=30
    )
    print(culasse)
