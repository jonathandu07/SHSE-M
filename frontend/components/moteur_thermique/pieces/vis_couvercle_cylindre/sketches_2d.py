"""
Chemin : frontend/components/moteur_thermique/pieces/vis_couvercle_cylindre/sketches_2d.py
But :
    Produire le contrat de croquis 2D cote de la piece vis_couvercle_cylindre.
Pourquoi ce fichier existe :
    Le croquis aide au redessin SolidWorks, mais uniquement si les cotes backend
    minimales existent.
Donnees consommees :
    Rapport de piece prepare par frontend/ensemble.
Livrables produits :
    Contrat sketch_2d et figure Matplotlib optionnelle.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.cao_rendering import build_generic_sketch_contract, build_sketch_figure
from frontend.ensemble.piece_data_adapter import get_piece_report, safe_dict

PIECE_NAME = "vis_couvercle_cylindre"


def build_sketch_contract(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    piece_report = safe_dict(data) or get_piece_report(report, PIECE_NAME)
    return build_generic_sketch_contract(PIECE_NAME, piece_report)


def tracer_croquis(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    return build_sketch_figure(build_sketch_contract(data=data, global_report=global_report))


def afficher_2d(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    return tracer_croquis(data=data, global_report=global_report)



def draw(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    return tracer_croquis(data=data, global_report=global_report)


def make_figure(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    return tracer_croquis(data=data, global_report=global_report)


def tracer_croquis_vis_couvercle_cylindre_2d(data: Mapping[str, Any] | None = None, global_report: Mapping[str, Any] | None = None) -> Any:
    return tracer_croquis(data=data, global_report=global_report)
