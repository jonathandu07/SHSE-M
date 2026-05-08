from frontend.components.moteur_thermique.pieces.couvercle_cylindre.sketches_2d import tracer_croquis_couvercle_2d

from frontend.pieces.sketches_2d._compat import render_tracer_to_axis


def draw(ax, piece):
    render_tracer_to_axis(ax, piece, tracer_croquis_couvercle_2d, "couvercle_cylindre")
