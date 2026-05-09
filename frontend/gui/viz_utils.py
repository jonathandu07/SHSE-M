"""
frontend/gui/viz_utils.py
Utilitaire pour resoudre les chemins des modules de visualisation (2D, 3D, Charts)
en respectant l'architecture miroir du backend.
"""
from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable, Optional


def resolve_viz_module(piece_name: str, viz_type: str) -> Optional[Any]:
    """
    Tente de charger le module de visualisation pour une piece.
    viz_type: 'sketches_2d', 'views_3d' ou 'charts'
    """
    key = piece_name.lower().replace(" ", "_")
    mapping = {
        "vilebrequin": "arbre_vilebrequin",
        "vilbrequin": "vilbrequin",
        "arbre_vilbrequin": "arbre_vilebrequin",
        "arbre_vilebrequin": "arbre_vilebrequin",
        "arbremoteur": "arbre",
        "architecture": "architechture",
        "architechture": "architechture",
        "couvercle": "couvercle_cylindre",
        "coussinet": "coussinet_arbre_piston",
    }
    key = mapping.get(key, key)

    subsystems = [
        "alternateur",
        "batterie",
        "architechture",
        "boite_crabots",
        "moteur_electrique",
        "moteur_thermique",
    ]

    if key in subsystems:
        paths = [f"frontend.components.{key}.{viz_type}"]
    else:
        paths = [f"frontend.components.moteur_thermique.pieces.{key}.{viz_type}"]

    if viz_type == "views_3d":
        paths.extend(path.replace(".views_3d", ".mesh_3d") for path in list(paths))

    if "vilebrequin" in key:
        paths.extend(path.replace("vilebrequin", "vilbrequin") for path in list(paths))

    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            return importlib.import_module(path)
        except ImportError:
            continue
        except Exception as exc:
            print(f"[viz_utils] Erreur lors du chargement de {path}: {exc}")
            return None
    return None


def get_draw_3d_func(piece_name: str) -> Callable:
    mod = resolve_viz_module(piece_name, "views_3d")
    if mod and hasattr(mod, "draw_3d"):
        return mod.draw_3d
    if mod and hasattr(mod, "draw"):
        return mod.draw

    try:
        from frontend.ensemble.viz_3d_generic import draw_3d

        return draw_3d
    except ImportError:
        return lambda ax, p: None


def get_viz_figure(piece_name: str, piece_obj: Any, viz_type: str) -> Optional[Any]:
    """
    Recupere une Figure Matplotlib pour une piece donnee.
    viz_type: 'sketches_2d', 'views_3d' ou 'charts'
    """
    import matplotlib.pyplot as plt

    mod = resolve_viz_module(piece_name, viz_type)

    try:
        if viz_type == "views_3d":
            draw_fn = get_draw_3d_func(piece_name)
            from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

            fig = plt.figure(figsize=(5, 5))
            ax = fig.add_subplot(111, projection="3d")
            draw_fn(ax, piece_obj)
            return fig

        if viz_type == "charts":
            if mod and hasattr(mod, "plot_data"):
                plot_fn = mod.plot_data
            else:
                from frontend.ensemble.viz_radar_template import plot_data as plot_fn

            fig = plt.figure(figsize=(5, 5))
            ax = fig.add_subplot(111, polar=True)
            plot_fn(ax, piece_obj)
            return fig

        if viz_type == "sketches_2d":
            if mod and hasattr(mod, "draw"):
                fig, ax = plt.subplots(figsize=(6, 6))
                mod.draw(ax, piece_obj)
                return fig

            if mod:
                for attr in dir(mod):
                    if attr.startswith("tracer_croquis_") and attr.endswith("_2d"):
                        fn = getattr(mod, attr)
                        if callable(fn):
                            params = inspect.signature(fn).parameters
                            if "afficher" in params:
                                res = fn(piece_obj, afficher=False)
                            else:
                                res = fn(piece_obj)
                            return res[0] if isinstance(res, (tuple, list)) else res
    except Exception as exc:
        print(f"[viz_utils] Erreur get_viz_figure({piece_name}, {viz_type}): {exc}")

    if viz_type == "sketches_2d":
        try:
            from frontend.ensemble.viz_2d_generic import make_figure

            return make_figure(piece_obj)
        except Exception as exc:
            print(f"[viz_utils] Echec fallback 2D pour {piece_name}: {exc}")
            return None

    if viz_type == "charts":
        try:
            from frontend.ensemble.viz_radar_template import plot_data as plot_fn

            fig = plt.figure(figsize=(5, 5))
            ax = fig.add_subplot(111, polar=True)
            plot_fn(ax, piece_obj)
            return fig
        except Exception as exc:
            print(f"[viz_utils] Echec fallback chart pour {piece_name}: {exc}")
            return None

    return None
