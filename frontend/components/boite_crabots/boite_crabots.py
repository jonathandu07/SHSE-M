"""
Chemin : frontend/components/boite_crabots/boite_crabots.py
But : Orchestrateur front-end servant de page d'affichage et permettant de consulter les données sur les pièces.
"""

from __future__ import annotations
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

def tracer_croquis_boite_crabots_2d(titre: str = "Boîte à Crabots - Vue d'Ensemble"):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    
    # Représentation schématique
    ax.add_patch(Rectangle((20, 30), 60, 40, fill=False, edgecolor="black", linewidth=2))
    ax.text(50, 50, "BOÎTE À CRABOTS", ha="center", va="center", weight="bold", fontsize=14)
    
    # Éléments internes représentatifs
    ax.add_patch(Circle((35, 50), 10, facecolor="#e0e0e0", edgecolor="blue"))
    ax.text(35, 50, "Pignon", ha="center", va="center", color="blue")
    
    ax.add_patch(Circle((65, 50), 10, facecolor="#e0e0e0", edgecolor="blue"))
    ax.text(65, 50, "Crabot", ha="center", va="center", color="blue")
    
    plt.suptitle(titre)
    plt.tight_layout()
    return fig

if __name__ == "__main__":
    tracer_croquis_boite_crabots_2d()
    plt.show()
