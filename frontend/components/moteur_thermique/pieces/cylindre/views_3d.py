"""
Chemin : frontend/components/moteur_thermique/pieces/cylindre/views_3d.py
But : Définition et rendu des vues 3D de la pièce.
"""

"""Vue 3D matplotlib — Cylindre"""
from __future__ import annotations
import numpy as np
from frontend.ensemble.viz_3d_template import _safe, cylinder_surface, disk_surface, apply_style


def draw_3d(ax, piece) -> None:
    D_mm = _safe(piece, "alesage_nominal_mm", "alesage_m", default=0.13) * (
        1 if _safe(piece, "alesage_nominal_mm", default=0.0) < 1 else 0.001
    )
    # Simpler: try mm first, then m
    d_raw = _safe(piece, "alesage_nominal_mm", "alesage_nominal_m",
                   "alesage_m", default=130.0)
    D_mm = d_raw if d_raw > 10 else d_raw * 1000

    H_mm = _safe(piece, "course_mm", "course_m", default=150.0)
    H_mm = H_mm if H_mm > 10 else H_mm * 1000

    ep_mm = _safe(piece, "epaisseur_retenue_mm", "epaisseur_paroi_mm", default=D_mm * 0.12)
    R_in = D_mm / 2
    R_out = R_in + ep_mm

    color_body = "#81A1B8"

    # Corps du cylindre (paroi)
    X_out, Y_out, Z_out = cylinder_surface(R_out, H_mm)
    ax.plot_surface(X_out, Y_out, Z_out, color=color_body, alpha=0.65, linewidth=0)

    X_in, Y_in, Z_in = cylinder_surface(R_in, H_mm)
    ax.plot_surface(X_in, Y_in, Z_in, color="#C8D8E8", alpha=0.45, linewidth=0)

    # Flasques haut et bas
    for z_fl in [0, H_mm]:
        Xf, Yf, Zf = disk_surface(R_in, R_out, z_fl)
        ax.plot_surface(Xf, Yf, Zf, color="#03224C", alpha=0.88, linewidth=0)

    apply_style(ax, title=f"Cylindre — Ø{D_mm:.0f}×{H_mm:.0f} mm")
    lim = R_out * 1.3
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-H_mm * 0.05, H_mm * 1.1)
    ax.view_init(elev=20, azim=35)
