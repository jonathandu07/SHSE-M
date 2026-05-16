"""Vue 3D matplotlib — fallback générique pour toutes les autres pièces"""
from __future__ import annotations
import numpy as np
from frontend.ensemble.viz_3d_template import _safe, cylinder_surface, disk_surface, apply_style


def draw_3d(ax, piece) -> None:
    """Vue 3D générique : cylindre dimensionné depuis les données disponibles."""
    # Essai de lecture d'un diamètre
    D_raw = _safe(piece, "diametre_m", "diametre_primitif_m", "diametre_arbre_m",
                   "alesage_m", "diametre_nominal_m", default=0.0)
    D_mm = D_raw * 1000 if D_raw < 5 else D_raw  # auto-détection unité
    if D_mm <= 0:
        D_mm = 50.0

    H_raw = _safe(piece, "longueur_m", "hauteur_m", "course_m",
                   "longueur_bielle_m", "longueur_totale_m", default=0.0)
    H_mm = H_raw * 1000 if H_raw < 5 else H_raw
    if H_mm <= 0:
        H_mm = D_mm * 2.0

    R = D_mm / 2
    X, Y, Z = cylinder_surface(R, H_mm)
    ax.plot_surface(X, Y, Z, color="#3E5349", alpha=0.8, linewidth=0)

    for z_fl in [0, H_mm]:
        Xf, Yf, Zf = disk_surface(0, R, z_fl)
        ax.plot_surface(Xf, Yf, Zf, color="#091226", alpha=0.85, linewidth=0)

    # Nom de la pièce
    nom = getattr(piece, "nom", None) or (piece.get("nom") if isinstance(piece, dict) else None) or "Pièce"
    apply_style(ax, title=f"{str(nom).replace('_', ' ').title()} — Ø{D_mm:.0f}×{H_mm:.0f} mm")

    lim = R * 1.5
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-H_mm * 0.05, H_mm * 1.1)
    ax.view_init(elev=20, azim=30)
