"""
Chemin : frontend/components/moteur_electrique/moteur_electrique.py
But : Orchestrateur front-end servant de page d'affichage et permettant de consulter les données sur les pièces.
"""

from __future__ import annotations
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

def tracer_croquis_moteur_electrique_2d(titre: str = "Moteur Électrique - Vue d'Ensemble"):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    
    # Représentation schématique
    ax.add_patch(Rectangle((25, 25), 50, 50, fill=False, edgecolor="black", linewidth=2))
    ax.text(50, 85, "MOTEUR ÉLECTRIQUE", ha="center", va="center", weight="bold", fontsize=14)
    
    # Éléments internes : Stator et Rotor
    ax.add_patch(Circle((50, 50), 20, fill=False, edgecolor="orange", linewidth=4))
    ax.text(50, 65, "Stator", ha="center", color="orange")
    
    ax.add_patch(Circle((50, 50), 12, facecolor="#e0e0e0", edgecolor="red"))
    ax.text(50, 50, "Rotor", ha="center", va="center", color="red", weight="bold")
    
    plt.suptitle(titre)
    plt.tight_layout()
    return fig

if __name__ == "__main__":
    tracer_croquis_moteur_electrique_2d()
    plt.show()
