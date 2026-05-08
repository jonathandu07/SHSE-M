"""Vue 3D matplotlib — Piston"""
from __future__ import annotations
import numpy as np
from frontend.pieces.views_3d._3d_template import _safe, cylinder_surface, disk_surface, apply_style


def draw_3d(ax, piece) -> None:
    """
    Trace une vue 3D réaliste du piston à partir des dimensions calculées.
    `piece` peut être un objet Piston ou un dict de données BDD.
    """
    # --- Extraction des dimensions ---
    D_mm = _safe(piece, "diametre_piston_cao_mm", "alesage_nominal_mm",
                  default=_safe(piece, "alesage_m", "alesage_nominal_m", default=0.13) * 1000)
    H_mm = _safe(piece, "hauteur_totale_mm", "hauteur_totale_m",
                  default=D_mm * 1.1 if D_mm else 143)
    et_mm = _safe(piece, "epaisseur_tete_mm", "epaisseur_tete_m", default=H_mm * 0.18)
    Lj_mm = _safe(piece, "longueur_jupe_mm", "longueur_jupe_m", default=H_mm * 0.45)
    pr_mm = _safe(piece, "profondeur_rainure_mm", default=D_mm * 0.05)
    lr_mm = _safe(piece, "largeur_rainure_mm", default=D_mm * 0.035)
    nb_j = max(1, int(_safe(piece, "nb_joints", default=2)))

    # Convertir tout en mm pour le plot
    R = D_mm / 2
    H = H_mm
    et = et_mm
    Lj = Lj_mm

    color_body = "#81A1B8"
    color_groove = "#E0E0E0"
    alpha_main = 0.85

    # --- Corps principal (jupe) ---
    X, Y, Z = cylinder_surface(R, H)
    ax.plot_surface(X, Y, Z, color=color_body, alpha=alpha_main, linewidth=0)

    # --- Tête (disque supérieur) ---
    Xd, Yd, Zd = disk_surface(0, R, H)
    ax.plot_surface(Xd, Yd, Zd, color="#03224C", alpha=0.9, linewidth=0)

    # --- Fond (disque inférieur) ---
    Xf, Yf, Zf = disk_surface(0, R * 0.6, 0)  # fond ouvert (jupe)
    ax.plot_surface(Xf, Yf, Zf, color=color_body, alpha=0.6, linewidth=0)

    # --- Rainures de joints ---
    for i in range(nb_j):
        z_groove = H - et - (i + 0.5) * (H * 0.12)
        if z_groove < Lj_mm * 0.3:
            break
        R_groove = R - pr_mm
        X_g, Y_g, Z_g = cylinder_surface(R_groove, lr_mm, n=60)
        Z_g += z_groove - lr_mm / 2
        ax.plot_surface(X_g, Y_g, Z_g, color=color_groove, alpha=0.95, linewidth=0)

    # --- Axe de piston (cylindre central) ---
    R_axe = R * 0.12
    h_axe = D_mm * 0.55
    X_a, Y_a, Z_a = cylinder_surface(R_axe, h_axe, n=40)
    # Axe horizontal → rotation 90° → approximation: plot comme bâton vertical centré
    z_axe_center = H * 0.4
    Z_a += z_axe_center - h_axe / 2
    ax.plot_surface(X_a, Y_a, Z_a, color="#05143F", alpha=0.9, linewidth=0)

    apply_style(ax, title=f"Piston — Ø{D_mm:.0f}×{H_mm:.0f} mm")

    # Axes équilibrés
    lim = R * 1.35
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(0, H * 1.15)
    ax.view_init(elev=22, azim=-50)
