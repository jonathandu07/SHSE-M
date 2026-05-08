from frontend.components.moteur_thermique.pieces.arbre_vilebrequin.sketches_2d import tracer_croquis_arbre_vilebrequin_2d

from frontend.pieces.sketches_2d._compat import render_tracer_to_axis


def draw(ax, piece):
    render_tracer_to_axis(ax, piece, tracer_croquis_arbre_vilebrequin_2d, "arbre_vilbrequin")
