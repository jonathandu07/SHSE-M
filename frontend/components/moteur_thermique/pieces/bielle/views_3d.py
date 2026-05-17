"""
Chemin : frontend/components/moteur_thermique/pieces/bielle/views_3d.py
But : Définition et rendu des vues 3D de la pièce.
"""

from __future__ import annotations
import numpy as np
from frontend.ensemble.viz_3d_template import _safe, cylinder_surface, disk_surface, apply_style


def draw_3d(ax, piece) -> None:
    # Dimensions
    L_mm = _safe(piece, "longueur_bielle_mm", "longueur_bielle_m", default=255.0)
    L_mm = L_mm if L_mm > 10 else L_mm * 1000

    D_pe_mm = _safe(piece, "diametre_petite_tete_mm", "diametre_axe_mm", default=L_mm * 0.12)
    D_gt_mm = _safe(piece, "diametre_grande_tete_mm", "diametre_maneton_mm", default=L_mm * 0.22)
    w_fut_mm = _safe(piece, "largeur_fut_mm", default=L_mm * 0.08)

    R_pe = D_pe_mm / 2
    R_gt = D_gt_mm / 2
    h_fut = w_fut_mm

    # Petite tête (haute)
    X, Y, Z = cylinder_surface(R_pe, h_fut, n=50)
    Z += L_mm - h_fut / 2
    ax.plot_surface(X, Y, Z, color="#81A1B8", alpha=0.85, linewidth=0)
    Xd, Yd, Zd = disk_surface(0, R_pe, L_mm)
    ax.plot_surface(Xd, Yd, Zd, color="#03224C", alpha=0.88, linewidth=0)

    # Grande tête (basse)
    X2, Y2, Z2 = cylinder_surface(R_gt, h_fut, n=50)
    ax.plot_surface(X2, Y2, Z2, color="#81A1B8", alpha=0.85, linewidth=0)
    Xd2, Yd2, Zd2 = disk_surface(0, R_gt, 0)
    ax.plot_surface(Xd2, Yd2, Zd2, color="#03224C", alpha=0.88, linewidth=0)

    # Fût (corps — approximation par un prisme elliptique)
    t = np.linspace(0, 1, 30)
    z_vals = t * L_mm
    w_half = np.linspace(R_pe, R_gt, 30)
    t_half = w_fut_mm / 2

    for i, (z_v, w_h) in enumerate(zip(z_vals, w_half)):
        if i % 3 == 0:
            ax.plot([-t_half, t_half], [0, 0], [z_v, z_v],
                    color="#81A1B8", alpha=0.3, linewidth=2)
    # Contour fuselé (lignes de bord)
    ax.plot([-t_half]*30, [0]*30, list(z_vals), color="#03224C", alpha=0.7, linewidth=1.5)
    ax.plot([t_half]*30, [0]*30, list(z_vals), color="#03224C", alpha=0.7, linewidth=1.5)

    apply_style(ax, title=f"Bielle — L={L_mm:.0f} mm")
    lim = max(R_gt, t_half) * 2.2
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-L_mm * 0.05, L_mm * 1.1)
    ax.view_init(elev=15, azim=25)
