"""
frontend/gui/viz_utils.py
Utilitaire pour résoudre les chemins des modules de visualisation (2D, 3D, Charts)
en respectant l'architecture miroir du backend.
"""
from __future__ import annotations
import importlib
import traceback
from typing import Any, Optional, Callable

def resolve_viz_module(piece_name: str, viz_type: str) -> Optional[Any]:
    """
    Tente de charger le module de visualisation pour une pièce.
    viz_type: 'sketches_2d', 'views_3d' ou 'charts'
    """
    # Harmonisation des noms et correction des fautes de frappe (miroir du backend)
    key = piece_name.lower().replace(" ", "_")
    # Mapping vers les dossiers réels du frontend
    mapping = {
        "vilebrequin": "arbre_vilebrequin",
        "vilbrequin": "vilbrequin",
        "arbre_vilebrequin": "arbre_vilebrequin",
        "architecture": "architechture",
        "architechture": "architechture",
        "couvercle": "couvercle_cylindre",
        "coussinet": "coussinet_arbre_piston",
    }
    key = mapping.get(key, key)
    
    # Liste des composants racines (top-level components)
    subsystems = [
        "alternateur", "batterie", "architechture", 
        "boite_crabots", "moteur_electrique", "moteur_thermique"
    ]
    
    if key in subsystems:
        path = f"frontend.components.{key}.{viz_type}"
    else:
        # Par défaut, on cherche dans les pièces du moteur thermique
        path = f"frontend.components.moteur_thermique.pieces.{key}.{viz_type}"
        
    try:
        return importlib.import_module(path)
    except ImportError:
        # Fallback pour vilbrequin/vilebrequin si l'utilisateur a utilisé l'ancienne orthographe
        if "vilebrequin" in key:
            try:
                alt_path = path.replace("vilebrequin", "vilbrequin")
                return importlib.import_module(alt_path)
            except ImportError:
                pass
        return None
    except Exception as e:
        print(f"[viz_utils] Erreur lors du chargement de {path}: {e}")
        return None

def get_draw_3d_func(piece_name: str) -> Callable:
    """Version mise à jour de get_draw_3d."""
    mod = resolve_viz_module(piece_name, "views_3d")
    if mod and hasattr(mod, "draw_3d"):
        return mod.draw_3d
    if mod and hasattr(mod, "draw"):
        return mod.draw
    
    # Fallback générique
    try:
        from frontend.ensemble.viz_3d_generic import draw_3d
        return draw_3d
    except ImportError:
        return lambda ax, p: None

def get_viz_figure(piece_name: str, piece_obj: Any, viz_type: str) -> Optional[Any]:
    """
    Récupère une Figure Matplotlib pour une pièce donnée.
    viz_type: 'sketches_2d', 'views_3d' ou 'charts'
    """
    import matplotlib.pyplot as plt
    mod = resolve_viz_module(piece_name, viz_type)
    if not mod:
        return None

    try:
        if viz_type == "views_3d":
            draw_fn = get_draw_3d_func(piece_name)
            from mpl_toolkits.mplot3d import Axes3D # noqa: F401
            fig = plt.figure(figsize=(5, 5))
            ax = fig.add_subplot(111, projection='3d')
            draw_fn(ax, piece_obj)
            return fig

        elif viz_type == "charts":
            if hasattr(mod, "plot_data"):
                fig = plt.figure(figsize=(5, 5))
                ax = fig.add_subplot(111, polar=True)
                mod.plot_data(ax, piece_obj)
                return fig

        elif viz_type == "sketches_2d":
            # Cas 1: draw(ax, piece)
            if hasattr(mod, "draw"):
                fig, ax = plt.subplots(figsize=(6, 6))
                mod.draw(ax, piece_obj)
                return fig
            
            # Cas 2: tracer_croquis_[piece]_2d(piece, ...)
            for attr in dir(mod):
                if attr.startswith("tracer_croquis_") and attr.endswith("_2d"):
                    fn = getattr(mod, attr)
                    if callable(fn):
                        # On appelle avec afficher=False pour récupérer l'objet figure
                        res = fn(piece_obj, afficher=False)
                        return res[0] if isinstance(res, (tuple, list)) else res
    except Exception as e:
        print(f"[viz_utils] Erreur get_viz_figure({piece_name}, {viz_type}): {e}")
    
    return None
