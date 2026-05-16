"""
frontend/pieces/views_3d/_3d_template.py
Utilitaires partagés pour les vues 3D matplotlib des pièces SHSE-M.
"""
from __future__ import annotations

import math
import numpy as np


def _safe(obj, *keys, default=0.0) -> float:
    """Extrait un float depuis un objet ou dict via plusieurs clés candidates."""
    for k in keys:
        try:
            v = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
            if v is not None:
                f = float(v)
                if math.isfinite(f) and f != 0.0:
                    return f
        except Exception:
            pass
    return float(default)


def cylinder_surface(r: float, h: float, n: int = 60):
    """Génère la surface latérale d'un cylindre droit."""
    theta = np.linspace(0, 2 * np.pi, n)
    z = np.linspace(0, h, 2)
    Theta, Z = np.meshgrid(theta, z)
    X = r * np.cos(Theta)
    Y = r * np.sin(Theta)
    return X, Y, Z


def disk_surface(r_in: float, r_out: float, z: float, n: int = 60):
    """Génère un disque plein ou en anneau à hauteur z."""
    theta = np.linspace(0, 2 * np.pi, n)
    r = np.linspace(r_in, r_out, 2)
    Theta, R = np.meshgrid(theta, r)
    X = R * np.cos(Theta)
    Y = R * np.sin(Theta)
    Z = np.full_like(X, z)
    return X, Y, Z


def apply_style(ax, title: str = "", unit: str = "mm"):
    """Style commun pour les vues 3D."""
    ax.set_xlabel(f"X [{unit}]", fontsize=8)
    ax.set_ylabel(f"Y [{unit}]", fontsize=8)
    ax.set_zlabel(f"Z [{unit}]", fontsize=8)
    ax.tick_params(labelsize=7)
    if title:
        ax.set_title(title, fontsize=10, fontweight="bold", color="#091226", pad=10)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.grid(True, alpha=0.25)
