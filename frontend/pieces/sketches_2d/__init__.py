from __future__ import annotations

from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

from . import bielle, couvercle_cylindre, cylindre, piston
from . import arbre_vilbrequin as vilbrequin


def _finish(ax, title: str):
    ax.set_title(title)
    ax.set_aspect("equal", adjustable="box")
    ax.autoscale_view()
    ax.grid(True, alpha=0.2)
    return ax


def _draw_cylindre(ax, piece=None):
    ax.add_patch(Rectangle((-20, -40), 40, 80, fill=False, linewidth=1.6))
    ax.add_patch(Rectangle((-28, -48), 56, 96, fill=False, linewidth=0.9, linestyle="--"))
    ax.add_line(Line2D([0, 0], [-50, 50], linewidth=0.8, linestyle="--", color="black"))
    ax.text(0, 54, "Cylindre", ha="center")
    return _finish(ax, "Croquis cylindre")


def _draw_piston(ax, piece=None):
    ax.add_patch(Rectangle((-24, -18), 48, 36, fill=False, linewidth=1.6))
    ax.add_patch(Circle((0, 0), 7, fill=False, linewidth=1.2))
    ax.add_line(Line2D([-24, 24], [10, 10], linewidth=0.9, color="black"))
    ax.text(0, 25, "Piston", ha="center")
    return _finish(ax, "Croquis piston")


def _draw_bielle(ax, piece=None):
    ax.add_patch(Circle((-34, 0), 12, fill=False, linewidth=1.5))
    ax.add_patch(Circle((34, 0), 18, fill=False, linewidth=1.5))
    ax.add_line(Line2D([-24, 20], [0, 0], linewidth=5.0, solid_capstyle="round", color="black"))
    ax.add_line(Line2D([-24, 20], [0, 0], linewidth=2.2, solid_capstyle="round", color="white"))
    ax.text(0, 28, "Bielle", ha="center")
    return _finish(ax, "Croquis bielle")


def _draw_vilbrequin(ax, piece=None):
    ax.add_line(Line2D([-55, -18], [0, 0], linewidth=4.0, color="black"))
    ax.add_line(Line2D([18, 55], [0, 0], linewidth=4.0, color="black"))
    ax.add_line(Line2D([-18, 0], [0, 20], linewidth=3.0, color="black"))
    ax.add_line(Line2D([0, 18], [20, 0], linewidth=3.0, color="black"))
    ax.add_patch(Circle((0, 20), 7, fill=False, linewidth=1.4))
    ax.text(0, 34, "Vilebrequin", ha="center")
    return _finish(ax, "Croquis vilebrequin")


def _draw_couvercle_cylindre(ax, piece=None):
    ax.add_patch(Rectangle((-30, -18), 60, 36, fill=False, linewidth=1.5))
    for x in (-20, 20):
        ax.add_patch(Circle((x, 0), 4, fill=False, linewidth=1.0))
    ax.add_patch(Circle((0, 0), 10, fill=False, linewidth=1.2))
    ax.text(0, 27, "Couvercle", ha="center")
    return _finish(ax, "Croquis couvercle")


for _module, _draw in (
    (cylindre, _draw_cylindre),
    (piston, _draw_piston),
    (bielle, _draw_bielle),
    (vilbrequin, _draw_vilbrequin),
    (couvercle_cylindre, _draw_couvercle_cylindre),
):
    if not hasattr(_module, "draw"):
        setattr(_module, "draw", _draw)


__all__ = ["cylindre", "piston", "bielle", "vilbrequin", "couvercle_cylindre"]
