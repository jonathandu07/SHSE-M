from __future__ import annotations

from importlib import import_module
from typing import Callable, Dict


_MODULES: Dict[str, str] = {
    "arbre": "frontend.components.moteur_thermique.pieces.arbre.mesh_3d",
    "arbre_piston": "frontend.components.moteur_thermique.pieces.arbre_piston.mesh_3d",
    "arbre_vilbrequin": "frontend.components.moteur_thermique.pieces.arbre_vilebrequin.mesh_3d",
    "bielle": "frontend.components.moteur_thermique.pieces.bielle.mesh_3d",
    "couvercle_cylindre": "frontend.components.moteur_thermique.pieces.couvercle_cylindre.mesh_3d",
    "cylindre": "frontend.components.moteur_thermique.pieces.cylindre.views_3d",
    "deplaceur": "frontend.components.moteur_thermique.pieces.deplaceur.mesh_3d",
    "joint_deplaceur": "frontend.components.moteur_thermique.pieces.joint_deplaceur.mesh_3d",
    "joint_piston": "frontend.components.moteur_thermique.pieces.joint_piston.mesh_3d",
    "piston": "frontend.components.moteur_thermique.pieces.piston.views_3d",
    "vilbrequin": "frontend.components.moteur_thermique.pieces.vilbrequin.mesh_3d",
}


def get_draw_3d(piece_name: str) -> Callable:
    key = str(piece_name).strip().lower()
    module_name = _MODULES.get(key)
    if module_name is None:
        raise ImportError(f"Aucune vue 3D declaree pour {piece_name}.")
    module = import_module(module_name)
    draw = getattr(module, "draw_3d", None) or getattr(module, "draw", None)
    if draw is None:
        raise AttributeError(f"Le module {module_name} n'expose ni draw_3d ni draw.")
    return draw
