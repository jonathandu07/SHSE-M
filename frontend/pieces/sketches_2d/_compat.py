from __future__ import annotations

from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np

from frontend.gui.piece_connector import get_piece_instance


def render_tracer_to_axis(ax: Any, piece: Any, tracer: Callable[..., Any], piece_name: str) -> None:
    target_piece = piece
    if target_piece is None or isinstance(target_piece, dict):
        target_piece = get_piece_instance(piece_name, {}) or piece

    fig = tracer(target_piece, afficher=False)
    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    image = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).reshape((height, width, 4))
    ax.imshow(image)
    ax.axis("off")
    plt.close(fig)
