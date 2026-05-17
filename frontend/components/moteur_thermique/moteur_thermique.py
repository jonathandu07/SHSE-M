"""
Chemin : frontend/components/moteur_thermique/moteur_thermique.py
But : Orchestrateur front-end servant de page d'affichage et permettant de consulter les données sur les pièces.
"""

from __future__ import annotations
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

def tracer_croquis_moteur_thermique_2d(titre: str = "Moteur Thermique - Vue d'Ensemble"):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    
    # Représentation schématique
    ax.add_patch(Rectangle((20, 20), 60, 60, fill=False, edgecolor="black", linewidth=2))
    ax.text(50, 90, "MOTEUR THERMIQUE", ha="center", va="center", weight="bold", fontsize=14)
    
    # Éléments internes : Cylindre, Piston, Vilebrequin
    ax.add_patch(Rectangle((40, 45), 20, 30, facecolor="#f0f0f0", edgecolor="gray"))
    ax.text(50, 60, "Cylindre", ha="center", va="center", color="gray")
    
    ax.add_patch(Rectangle((42, 50), 16, 10, facecolor="#cccccc", edgecolor="black"))
    ax.text(50, 55, "Piston", ha="center", va="center", fontsize=8)
    
    ax.add_patch(Circle((50, 30), 8, facecolor="#e0e0e0", edgecolor="brown"))
    ax.text(50, 30, "Vilebrequin", ha="center", va="center", color="brown", fontsize=8)
    
    # Bielle (Ligne reliant le piston au vilebrequin)
    ax.plot([50, 50], [38, 50], color="black", linewidth=3)
    
    plt.suptitle(titre)
    plt.tight_layout()
    return fig

if __name__ == "__main__":
    tracer_croquis_moteur_thermique_2d()
    plt.show()
