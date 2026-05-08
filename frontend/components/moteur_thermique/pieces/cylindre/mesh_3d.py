# frontend/pieces/3D/cylindre.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — CYLINDRE
# =============================================================================
# But :
# - afficher un cylindre détaillé à partir de backend/components/moteur_thermique/pieces/cylindre.py
# - utiliser prioritairement rapport["geometrie"]["cao"]
# - ne rien inventer hors des données calculées
#
# Dépendances :
#   pip install pyvista vtk numpy
#
# Modélise :
# - virole cylindrique
# - deux brides
# - perçages de brides
# - gorges de joint si disponibles
# - guides visuels
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import math

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.cylindre import Cylindre


# =============================================================================
# Utilitaires
# =============================================================================

def _is_finite(x: Any) -> bool:
    try:
        v = float(x)
        return v == v and abs(v) != float("inf")
    except Exception:
        return False


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly and v <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if not strictly and v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _get_dict(dct: Dict[str, Any], key: str) -> Dict[str, Any]:
    v = dct.get(key, {})
    return v if isinstance(v, dict) else {}


# =============================================================================
# Extraction géométrie
# =============================================================================

def extraire_geometrie_depuis_rapport(rapport: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dictionnaire issu de Cylindre.analyser().")

    geo = _get_dict(rapport, "geometrie")
    cao = _get_dict(geo, "cao")
    bride = _get_dict(cao, "bride")
    gorge = _get_dict(cao, "gorge_joint")
    visserie = _get_dict(cao, "visserie")

    # Fallback minimal si bloc CAO absent
    if not cao:
        di = geo.get("diametre_interne_m")
        de = geo.get("diametre_externe_m")
        if di is None or de is None:
            raise ValueError(
                "Le rapport ne contient pas assez d'informations pour une visualisation 3D détaillée."
            )
        return {
            "mode_cao": False,
            "diametre_interieur_nominal_m": _req_pos("geometrie.diametre_interne_m", di),
            "diametre_exterieur_nominal_m": _req_pos("geometrie.diametre_externe_m", de),
            "longueur_utile_nominale_m": _req_pos("entrees.longueur_utile_m", rapport["entrees"]["longueur_utile_m"]),
            "longueur_totale_nominale_m": _req_pos("entrees.longueur_utile_m", rapport["entrees"]["longueur_utile_m"]),
            "epaisseur_nominale_m": 0.5 * (_req_pos("geometrie.diametre_externe_m", de) - _req_pos("geometrie.diametre_interne_m", di)),
            "jeu_piston_cylindre_m": None,
            "chanfrein_entree_piston_m": None,
            "chanfrein_exterieur_m": None,
            "rayon_conge_m": None,
            "bride": None,
            "gorge_joint": None,
            "visserie": None,
        }

    return {
        "mode_cao": True,
        "diametre_interieur_nominal_m": _req_pos("cao.diametre_interieur_nominal_m", cao.get("diametre_interieur_nominal_m")),
        "diametre_exterieur_nominal_m": _req_pos("cao.diametre_exterieur_nominal_m", cao.get("diametre_exterieur_nominal_m")),
        "epaisseur_nominale_m": _req_pos("cao.epaisseur_nominale_m", cao.get("epaisseur_nominale_m")),
        "longueur_utile_nominale_m": _req_pos("cao.longueur_utile_nominale_m", cao.get("longueur_utile_nominale_m")),
        "longueur_totale_nominale_m": _req_pos("cao.longueur_totale_nominale_m", cao.get("longueur_totale_nominale_m")),
        "rayon_interieur_nominal_m": _req_pos("cao.rayon_interieur_nominal_m", cao.get("rayon_interieur_nominal_m")),
        "rayon_exterieur_nominal_m": _req_pos("cao.rayon_exterieur_nominal_m", cao.get("rayon_exterieur_nominal_m")),
        "jeu_piston_cylindre_m": (
            _req_pos("cao.jeu_piston_cylindre_m", cao.get("jeu_piston_cylindre_m"), strictly=False)
            if cao.get("jeu_piston_cylindre_m") is not None else None
        ),
        "chanfrein_entree_piston_m": (
            _req_pos("cao.chanfrein_entree_piston_m", cao.get("chanfrein_entree_piston_m"), strictly=False)
            if cao.get("chanfrein_entree_piston_m") is not None else None
        ),
        "chanfrein_exterieur_m": (
            _req_pos("cao.chanfrein_exterieur_m", cao.get("chanfrein_exterieur_m"), strictly=False)
            if cao.get("chanfrein_exterieur_m") is not None else None
        ),
        "rayon_conge_m": (
            _req_pos("cao.rayon_conge_m", cao.get("rayon_conge_m"), strictly=False)
            if cao.get("rayon_conge_m") is not None else None
        ),
        "bride": {
            "diametre_bride_externe_m": _req_pos("cao.bride.diametre_bride_externe_m", bride.get("diametre_bride_externe_m")),
            "rayon_bride_externe_m": _req_pos("cao.bride.rayon_bride_externe_m", bride.get("rayon_bride_externe_m")),
            "epaisseur_bride_m": _req_pos("cao.bride.epaisseur_bride_m", bride.get("epaisseur_bride_m")),
            "largeur_bride_m": _req_pos("cao.bride.largeur_bride_m", bride.get("largeur_bride_m")),
            "diametre_cercle_percage_m": (
                _req_pos("cao.bride.diametre_cercle_percage_m", bride.get("diametre_cercle_percage_m"))
                if bride.get("diametre_cercle_percage_m") is not None else None
            ),
            "diametre_trou_m": (
                _req_pos("cao.bride.diametre_trou_m", bride.get("diametre_trou_m"))
                if bride.get("diametre_trou_m") is not None else None
            ),
            "nb_trous": int(bride["nb_trous"]) if bride.get("nb_trous") is not None else None,
            "angles_deg": [float(a) for a in bride.get("angles_deg", [])] if isinstance(bride.get("angles_deg"), list) else None,
        } if bride else None,
        "gorge_joint": {
            "diametre_tore_m": _req_pos("cao.gorge_joint.diametre_tore_m", gorge.get("diametre_tore_m")),
            "profondeur_gorge_m": _req_pos("cao.gorge_joint.profondeur_gorge_m", gorge.get("profondeur_gorge_m")),
            "largeur_gorge_m": _req_pos("cao.gorge_joint.largeur_gorge_m", gorge.get("largeur_gorge_m")),
            "rayon_fond_gorge_interne_m": _req_pos("cao.gorge_joint.rayon_fond_gorge_interne_m", gorge.get("rayon_fond_gorge_interne_m")),
            "rayon_fond_gorge_externe_m": _req_pos("cao.gorge_joint.rayon_fond_gorge_externe_m", gorge.get("rayon_fond_gorge_externe_m")),
            "diametre_moyen_joint_m": _req_pos("cao.gorge_joint.diametre_moyen_joint_m", gorge.get("diametre_moyen_joint_m")),
            "position_axiale": gorge.get("position_axiale"),
        } if gorge else None,
        "visserie": visserie if visserie else None,
    }


# =============================================================================
# Primitives géométriques
# =============================================================================

def _tube_x(
    x0: float,
    x1: float,
    r_int: float,
    r_ext: float,
    resolution: int = 180,
) -> pv.PolyData:
    length = x1 - x0
    if length <= 0:
        raise ValueError("Longueur de tube <= 0.")
    ext = pv.Cylinder(
        center=(0.5 * (x0 + x1), 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_ext,
        height=length,
        resolution=resolution,
        capping=True,
    ).triangulate()
    inte = pv.Cylinder(
        center=(0.5 * (x0 + x1), 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_int,
        height=length + 1e-6,
        resolution=resolution,
        capping=True,
    ).triangulate()
    try:
        return ext.boolean_difference(inte).clean()
    except Exception:
        return ext.clean()


def _anneau_bride_x(
    x0: float,
    x1: float,
    r_int: float,
    r_ext: float,
    resolution: int = 180,
) -> pv.PolyData:
    return _tube_x(x0=x0, x1=x1, r_int=r_int, r_ext=r_ext, resolution=resolution)


def _percer_trous_sur_bride(
    mesh: pv.PolyData,
    x0: float,
    x1: float,
    diametre_cercle_percage_m: Optional[float],
    diametre_trou_m: Optional[float],
    angles_deg: Optional[List[float]],
) -> pv.PolyData:
    if diametre_cercle_percage_m is None or diametre_trou_m is None or not angles_deg:
        return mesh

    rpc = 0.5 * _req_pos("diametre_cercle_percage_m", diametre_cercle_percage_m)
    rtr = 0.5 * _req_pos("diametre_trou_m", diametre_trou_m)
    h = (x1 - x0) + 1e-4

    out = mesh
    for a in angles_deg:
        th = math.radians(float(a))
        y = rpc * math.cos(th)
        z = rpc * math.sin(th)
        cyl = pv.Cylinder(
            center=(0.5 * (x0 + x1), y, z),
            direction=(1.0, 0.0, 0.0),
            radius=rtr,
            height=h,
            resolution=80,
            capping=True,
        ).triangulate()
        try:
            out = out.boolean_difference(cyl).clean()
        except Exception:
            continue
    return out


def _creuser_gorge_joint_sur_face(
    mesh: pv.PolyData,
    x_face: float,
    largeur_gorge_m: float,
    rayon_fond_gorge_interne_m: float,
    rayon_fond_gorge_externe_m: float,
) -> pv.PolyData:
    lg = _req_pos("largeur_gorge_m", largeur_gorge_m)
    ri = _req_pos("rayon_fond_gorge_interne_m", rayon_fond_gorge_interne_m)
    re = _req_pos("rayon_fond_gorge_externe_m", rayon_fond_gorge_externe_m)
    if re <= ri:
        return mesh

    # Petite saignée annulaire centrée sur la face
    x0 = x_face - 0.5 * lg
    x1 = x_face + 0.5 * lg
    gorge = _tube_x(x0=x0, x1=x1, r_int=ri, r_ext=re, resolution=180)
    try:
        return mesh.boolean_difference(gorge).clean()
    except Exception:
        return mesh


# =============================================================================
# Construction complète
# =============================================================================

def construire_mesh_cylindre_detaille(
    rapport: Dict[str, Any],
    resolution: int = 180,
) -> Tuple[pv.PolyData, Dict[str, Any], Dict[str, pv.PolyData]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    di = geom["diametre_interieur_nominal_m"]
    de = geom["diametre_exterieur_nominal_m"]
    ri = 0.5 * di
    re = 0.5 * de

    L_tot = geom["longueur_totale_nominale_m"]
    L_utile = geom["longueur_utile_nominale_m"]

    sous_meshes: Dict[str, pv.PolyData] = {}

    if geom["bride"] is not None:
        eb = geom["bride"]["epaisseur_bride_m"]
        x_left_bride_0 = -0.5 * L_tot
        x_left_bride_1 = x_left_bride_0 + eb

        x_right_bride_1 = 0.5 * L_tot
        x_right_bride_0 = x_right_bride_1 - eb

        x_body_0 = x_left_bride_1
        x_body_1 = x_right_bride_0

        cyl_body = _tube_x(x_body_0, x_body_1, ri, re, resolution=resolution)
        sous_meshes["corps"] = cyl_body

        rb = geom["bride"]["rayon_bride_externe_m"]
        bride_g = _anneau_bride_x(x_left_bride_0, x_left_bride_1, re, rb, resolution=resolution)
        bride_d = _anneau_bride_x(x_right_bride_0, x_right_bride_1, re, rb, resolution=resolution)

        bride_g = _percer_trous_sur_bride(
            bride_g,
            x_left_bride_0,
            x_left_bride_1,
            geom["bride"]["diametre_cercle_percage_m"],
            geom["bride"]["diametre_trou_m"],
            geom["bride"]["angles_deg"],
        )
        bride_d = _percer_trous_sur_bride(
            bride_d,
            x_right_bride_0,
            x_right_bride_1,
            geom["bride"]["diametre_cercle_percage_m"],
            geom["bride"]["diametre_trou_m"],
            geom["bride"]["angles_deg"],
        )

        sous_meshes["bride_gauche"] = bride_g
        sous_meshes["bride_droite"] = bride_d

        mesh_total = cyl_body.merge(bride_g).merge(bride_d).clean()

        # Gorges de joint, si disponibles
        if geom["gorge_joint"] is not None:
            pos = geom["gorge_joint"]["position_axiale"]
            lg = geom["gorge_joint"]["largeur_gorge_m"]
            rg_i = geom["gorge_joint"]["rayon_fond_gorge_interne_m"]
            rg_e = geom["gorge_joint"]["rayon_fond_gorge_externe_m"]

            if pos in ("avant", "double"):
                mesh_total = _creuser_gorge_joint_sur_face(
                    mesh_total, x_left_bride_1, lg, rg_i, rg_e
                )
            if pos in ("arriere", "double"):
                mesh_total = _creuser_gorge_joint_sur_face(
                    mesh_total, x_right_bride_0, lg, rg_i, rg_e
                )

    else:
        mesh_total = _tube_x(-0.5 * L_tot, 0.5 * L_tot, ri, re, resolution=resolution)
        sous_meshes["corps"] = mesh_total

    return mesh_total.clean(), geom, sous_meshes


# =============================================================================
# Guides visuels
# =============================================================================

def construire_guides_visuels(geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    L_tot = geom["longueur_totale_nominale_m"]
    de = geom["diametre_exterieur_nominal_m"]
    re = 0.5 * de

    guides["axe"] = pv.Line(
        pointa=(-0.65 * L_tot, 0.0, 0.0),
        pointb=(0.65 * L_tot, 0.0, 0.0),
        resolution=1,
    )

    guides["plan_gauche"] = pv.Line(
        pointa=(-0.5 * L_tot, -1.2 * re, 0.0),
        pointb=(-0.5 * L_tot, 1.2 * re, 0.0),
        resolution=1,
    )
    guides["plan_droit"] = pv.Line(
        pointa=(0.5 * L_tot, -1.2 * re, 0.0),
        pointb=(0.5 * L_tot, 1.2 * re, 0.0),
        resolution=1,
    )

    if geom["bride"] is not None and geom["bride"]["diametre_cercle_percage_m"] is not None:
        circle = pv.Circle(radius=0.5 * geom["bride"]["diametre_cercle_percage_m"], resolution=240)
        guides["cercle_percage"] = circle

        if geom["bride"]["angles_deg"]:
            pts = []
            rpc = 0.5 * geom["bride"]["diametre_cercle_percage_m"]
            for a in geom["bride"]["angles_deg"]:
                th = math.radians(float(a))
                pts.append((0.0, rpc * math.cos(th), rpc * math.sin(th)))
            if pts:
                guides["centres_trous"] = pv.PolyData(np.array(pts))

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_cylindre_3d_detaille(
    source: Cylindre | Dict[str, Any],
    *,
    resolution: int = 180,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    couleur_corps: str = "lightsteelblue",
    couleur_brides: str = "silver",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    if isinstance(source, Cylindre):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un Cylindre ou un rapport dict.")

    mesh_total, geom, sous_meshes = construire_mesh_cylindre_detaille(
        rapport,
        resolution=resolution,
    )

    plotter = pv.Plotter(window_size=(1360, 860))
    plotter.set_background("#1e1e1e")

    if "corps" in sous_meshes:
        plotter.add_mesh(
            sous_meshes["corps"],
            color=couleur_corps,
            smooth_shading=True,
            show_edges=afficher_bords,
            specular=0.28,
            specular_power=24,
        )

    for name in ("bride_gauche", "bride_droite"):
        if name in sous_meshes:
            plotter.add_mesh(
                sous_meshes[name],
                color=couleur_brides,
                smooth_shading=True,
                show_edges=afficher_bords,
                specular=0.18,
                specular_power=18,
            )

    if ("bride_gauche" in sous_meshes or "bride_droite" in sous_meshes):
        plotter.add_mesh(mesh_total, color="gainsboro", opacity=0.08, show_edges=False)

    if afficher_guides:
        guides = construire_guides_visuels(geom)

        if "axe" in guides:
            plotter.add_mesh(guides["axe"], color="white", line_width=2)
        if "plan_gauche" in guides:
            plotter.add_mesh(guides["plan_gauche"], color="gold", line_width=2)
        if "plan_droit" in guides:
            plotter.add_mesh(guides["plan_droit"], color="gold", line_width=2)
        if "cercle_percage" in guides:
            plotter.add_mesh(guides["cercle_percage"], color="cyan", line_width=2)
        if "centres_trous" in guides:
            plotter.add_mesh(
                guides["centres_trous"],
                color="cyan",
                point_size=10,
                render_points_as_spheres=True,
            )

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Cylindre — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh_total, rapport


# =============================================================================
# Exemple minimal
# =============================================================================

if __name__ == "__main__":
    cyl = Cylindre(
        alesage_m=0.080,
        course_m=0.090,
        longueur_utile_m=0.120,
        pression_service_pa=1.5e6,
        pression_max_pa=3.0e6,
        limite_elastique_pa=250e6,
        module_young_pa=210e9,
        coefficient_poisson=0.30,
        densite_kg_m3=7800.0,
        regles_joint_torique=None,  # mettre des règles pour avoir la fermeture complète
    )

    afficher_cylindre_3d_detaille(cyl)
