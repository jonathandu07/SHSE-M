"""
Chemin : frontend/components/moteur_thermique/pieces/couvercle_cylindre/views_3d.py
But : Définition et rendu des vues 3D de la pièce.
"""

from __future__ import annotations
import numpy as np
from frontend.ensemble.viz_3d_template import _safe, cylinder_surface, disk_surface, apply_style


def draw_3d(ax, piece) -> None:
    D_mm = _safe(piece, "diametre_caracteristique_mm", "alesage_nominal_mm",
                  "alesage_m", default=130.0)
    D_mm = D_mm if D_mm > 10 else D_mm * 1000

    H_mm = _safe(piece, "hauteur_bombe_mm", "hauteur_mm", default=D_mm * 0.25)
    ep_mm = _safe(piece, "epaisseur_culasse_mm", "epaisseur_mm", default=D_mm * 0.15)

    R_out = D_mm * 0.65  # flanges légèrement plus grandes que l'alésage
    R_in = D_mm / 2

    # Corps principal (dalle)
    Xd, Yd, Zd = disk_surface(0, R_out, 0)
    ax.plot_surface(Xd, Yd, Zd, color="#81A1B8", alpha=0.85, linewidth=0)

    Xd2, Yd2, Zd2 = disk_surface(0, R_out, ep_mm)
    ax.plot_surface(Xd2, Yd2, Zd2, color="#03224C", alpha=0.9, linewidth=0)

    # Paroi latérale
    X, Y, Z = cylinder_surface(R_out, ep_mm)
    ax.plot_surface(X, Y, Z, color="#81A1B8", alpha=0.6, linewidth=0)

    # Chambre de combustion (dôme central inversé)
    theta = np.linspace(0, 2 * np.pi, 60)
    r = np.linspace(0, R_in * 0.9, 30)
    T, R_grid = np.meshgrid(theta, r)
    X_dome = R_grid * np.cos(T)
    Y_dome = R_grid * np.sin(T)
    # Forme bombée : z = ep_mm + H_mm * (1 - (r/R_in)^2)
    Z_dome = ep_mm + H_mm * (1 - (R_grid / (R_in * 0.9)) ** 2) * 0.4
    ax.plot_surface(X_dome, Y_dome, Z_dome, color="#C8D8E8", alpha=0.7, linewidth=0)

    # Soupapes schématiques (2 admission + 2 échappement)
    r_valve = R_in * 0.22
    positions = [(R_in * 0.35, R_in * 0.25), (-R_in * 0.35, R_in * 0.25),
                 (R_in * 0.35, -R_in * 0.25), (-R_in * 0.35, -R_in * 0.25)]
    colors_valve = ["#FF8C00", "#FF8C00", "#808080", "#808080"]
    for (cx, cy), cv in zip(positions, colors_valve):
        Xv, Yv, Zv = cylinder_surface(r_valve, ep_mm * 0.3, n=30)
        Xv += cx; Yv += cy; Zv += ep_mm * 0.7
        ax.plot_surface(Xv, Yv, Zv, color=cv, alpha=0.9, linewidth=0)

    apply_style(ax, title=f"Couvercle Cylindre — Ø{D_mm:.0f} mm")
    lim = R_out * 1.3
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-ep_mm * 0.1, (ep_mm + H_mm) * 1.4)
    ax.view_init(elev=30, azim=-40)
