# frontend/components/architechture/pieces/culasse_arch/mesh_3d.py
from __future__ import annotations

import pyvista as pv
from backend.components.architechture.pieces.culasse_arch import CulasseArch

def construire_mesh(piece: CulasseArch) -> pv.PolyData:
    """Construit le maillage 3D de la pièce."""
    # TODO: Remplacer par la géométrie exacte
    mesh = pv.Cube() 
    return mesh

def afficher_3d(piece: CulasseArch, afficher_axes: bool = True):
    """Affiche la pièce en 3D."""
    mesh = construire_mesh(piece)
    
    plotter = pv.Plotter()
    plotter.add_mesh(mesh, color="lightblue", show_edges=True)
    
    if afficher_axes:
        plotter.add_axes()
        
    plotter.add_text(f"Vue 3D : {piece.__class__.__name__}", font_size=12)
    plotter.view_isometric()
    plotter.show()
