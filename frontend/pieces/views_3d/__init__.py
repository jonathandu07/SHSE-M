"""Dispatch 3D views: resolves piece_name -> draw_3d function."""
from __future__ import annotations
import importlib
import os
import sys
from typing import Any, Callable, Optional


_BASE = os.path.dirname(__file__)


def get_draw_3d(piece_name: str) -> Callable:
    """
    Retourne la fonction draw_3d(ax, piece) pour le nom de pièce donné.
    Fallback sur _generic si le module spécifique n'existe pas.
    """
    key = piece_name.lower().replace(" ", "_")
    module_path = f"frontend.pieces.views_3d.{key}"
    try:
        mod = importlib.import_module(module_path)
        if hasattr(mod, "draw_3d"):
            return mod.draw_3d
    except ImportError:
        pass

    # Fallback générique
    from frontend.pieces.views_3d._generic import draw_3d
    return draw_3d
