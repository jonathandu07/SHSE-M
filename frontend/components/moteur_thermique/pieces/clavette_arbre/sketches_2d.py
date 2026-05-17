"""
Chemin : frontend/components/moteur_thermique/pieces/clavette_arbre/sketches_2d.py
But : Définition des esquisses géométriques 2D de la pièce.
"""

# frontend/components/moteur_thermique/pieces/clavette_arbre/sketches_2d.py
from __future__ import annotations

import matplotlib.pyplot as plt
from backend.components.moteur_thermique.pieces.clavette_arbre import ClavetteArbre

def tracer_vue_cote(ax, piece: ClavetteArbre):
    """Trace la vue de côté de la pièce."""
    ax.text(0.5, 0.5, f"Vue de côté : {piece.__class__.__name__}", ha="center", va="center")
    ax.set_title("Vue de côté")
    ax.set_axis_off()

def tracer_vue_face(ax, piece: ClavetteArbre):
    """Trace la vue de face de la pièce."""
    ax.text(0.5, 0.5, f"Vue de face : {piece.__class__.__name__}", ha="center", va="center")
    ax.set_title("Vue de face")
    ax.set_axis_off()

def afficher_2d(piece: ClavetteArbre):
    """Affiche la figure 2D complète."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    tracer_vue_cote(axes[0], piece)
    tracer_vue_face(axes[1], piece)
    plt.tight_layout()
    plt.show()
