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
    key = key.replace("vilbrequin", "vilebrequin")
    key = key.replace("architecture", "architechture")
    
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
    
    # Fallback générique
    try:
        from frontend.ensemble.viz_3d_generic import draw_3d
        return draw_3d
    except ImportError:
        # Si on a aussi déplacé _generic
        return lambda ax, p: None
