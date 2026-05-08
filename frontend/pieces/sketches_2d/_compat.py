from __future__ import annotations

from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle

from frontend.gui.piece_connector import get_piece_instance


def _draw_fallback(ax: Any, piece_name: str) -> None:
    ax.add_patch(Rectangle((0.15, 0.3), 0.7, 0.4, fill=False, linewidth=2.0, edgecolor="#03224C"))
    ax.add_patch(Circle((0.3, 0.5), 0.08, fill=False, linewidth=1.5, edgecolor="#81A1B8"))
    ax.add_patch(Circle((0.7, 0.5), 0.08, fill=False, linewidth=1.5, edgecolor="#81A1B8"))
    ax.text(0.5, 0.14, piece_name.replace("_", " ").upper(), ha="center", va="center")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")


def render_tracer_to_axis(ax: Any, piece: Any, tracer: Callable[..., Any], piece_name: str) -> None:
    target_piece = piece
    if target_piece is None or isinstance(target_piece, dict):
        target_piece = get_piece_instance(piece_name, {}) or piece

    try:
        rendered = tracer(target_piece, afficher=False)
        fig = rendered[0] if isinstance(rendered, tuple) else rendered
        fig.canvas.draw()
        width, height = fig.canvas.get_width_height()
        image = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).reshape((height, width, 4))
        ax.imshow(image)
        ax.text(0.02, 0.02, piece_name, transform=ax.transAxes, fontsize=1, alpha=0.0)
        ax.axis("off")
        plt.close(fig)
    except Exception:
        _draw_fallback(ax, piece_name)
