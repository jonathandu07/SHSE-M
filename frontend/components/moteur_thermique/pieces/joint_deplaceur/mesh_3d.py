# frontend/pieces/3D/joint_deplaceur.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — JOINT DEPLACEUR
# =============================================================================
# But :
# - afficher les joints toriques du déplaceur à partir de backend/components/moteur_thermique/pieces/joint_deplaceur.py
# - utiliser uniquement les données du rapport/cao sans inventer
#
# Dépendances :
#   pip install pyvista vtk numpy
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Tuple, List, Optional
import math

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.joint_deplaceur import JointDeplaceur


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


# =============================================================================
# Extraction
# =============================================================================

def extraire_geometrie_depuis_rapport(rapport: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dictionnaire issu de JointDeplaceur.analyser().")

    cao = rapport.get("cao", {})
    if not isinstance(cao, dict) or not cao:
        raise ValueError("Le bloc rapport['cao'] est requis pour la visualisation 3D du joint déplaceur.")

    positions = cao.get("positions_axiales_rainures_m")
    if positions is not None and not isinstance(positions, list):
        positions = None

    return {
        "orientation": cao.get("orientation"),
        "diametre_deplaceur_m": (
            _req_pos("cao.diametre_deplaceur_m", cao.get("diametre_deplaceur_m"))
            if cao.get("diametre_deplaceur_m") is not None else None
        ),
        "longueur_deplaceur_m": (
            _req_pos("cao.longueur_deplaceur_m", cao.get("longueur_deplaceur_m"))
            if cao.get("longueur_deplaceur_m") is not None else None
        ),
        "nb_joints": int(cao["nb_joints"]) if cao.get("nb_joints") is not None else None,
        "section_joint_mm": (
            _req_pos("cao.section_joint_mm", cao.get("section_joint_mm"))
            if cao.get("section_joint_mm") is not None else None
        ),
        "section_joint_m": (
            _req_pos("cao.section_joint_m", cao.get("section_joint_m"))
            if cao.get("section_joint_m") is not None else None
        ),
        "squeeze": (
            _req_pos("cao.squeeze", cao.get("squeeze"), strictly=False)
            if cao.get("squeeze") is not None else None
        ),
        "largeur_gorge_m": (
            _req_pos("cao.largeur_gorge_m", cao.get("largeur_gorge_m"))
            if cao.get("largeur_gorge_m") is not None else None
        ),
        "profondeur_gorge_m": (
            _req_pos("cao.profondeur_gorge_m", cao.get("profondeur_gorge_m"))
            if cao.get("profondeur_gorge_m") is not None else None
        ),
        "diametre_fond_gorge_m": (
            _req_pos("cao.diametre_fond_gorge_m", cao.get("diametre_fond_gorge_m"))
            if cao.get("diametre_fond_gorge_m") is not None else None
        ),
        "rayon_fond_gorge_m": (
            _req_pos("cao.rayon_fond_gorge_m", cao.get("rayon_fond_gorge_m"), strictly=False)
            if cao.get("rayon_fond_gorge_m") is not None else None
        ),
        "diametre_centreline_joint_m": (
            _req_pos("cao.diametre_centreline_joint_m", cao.get("diametre_centreline_joint_m"))
            if cao.get("diametre_centreline_joint_m") is not None else None
        ),
        "positions_axiales_rainures_m": [float(x) for x in positions] if positions else None,
        "marge_extremite_m": (
            _req_pos("cao.marge_extremite_m", cao.get("marge_extremite_m"), strictly=False)
            if cao.get("marge_extremite_m") is not None else None
        ),
        "entraxe_min_m": (
            _req_pos("cao.entraxe_min_m", cao.get("entraxe_min_m"), strictly=False)
            if cao.get("entraxe_min_m") is not None else None
        ),
    }


# =============================================================================
# Géométrie
# =============================================================================

def _tube_support_deplaceur(
    longueur_m: float,
    diametre_ext_m: float,
    resolution: int = 180,
) -> pv.PolyData:
    return pv.Cylinder(
        center=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=0.5 * _req_pos("diametre_ext_m", diametre_ext_m),
        height=_req_pos("longueur_m", longueur_m),
        resolution=resolution,
        capping=True,
    ).triangulate().clean()


def _creuser_gorge_annulaire(
    mesh: pv.PolyData,
    *,
    x_centre_m: float,
    largeur_gorge_m: float,
    diametre_fond_gorge_m: float,
    diametre_deplaceur_m: float,
) -> pv.PolyData:
    lg = _req_pos("largeur_gorge_m", largeur_gorge_m)
    df = _req_pos("diametre_fond_gorge_m", diametre_fond_gorge_m)
    dd = _req_pos("diametre_deplaceur_m", diametre_deplaceur_m)

    r_ext = 0.5 * dd
    r_fond = 0.5 * df

    if r_fond >= r_ext:
        return mesh

    ext = pv.Cylinder(
        center=(x_centre_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_ext,
        height=lg,
        resolution=160,
        capping=True,
    ).triangulate()

    intc = pv.Cylinder(
        center=(x_centre_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_fond,
        height=lg + 1e-5,
        resolution=160,
        capping=True,
    ).triangulate()

    try:
        gorge = ext.boolean_difference(intc).clean()
        return mesh.boolean_difference(gorge).clean()
    except Exception:
        return mesh


def _mesh_tore(
    diametre_centreline_m: float,
    section_joint_m: float,
    x_centre_m: float,
    n_u: int = 180,
    n_v: int = 60,
) -> pv.PolyData:
    Dc = _req_pos("diametre_centreline_m", diametre_centreline_m)
    s = _req_pos("section_joint_m", section_joint_m)
    R = 0.5 * Dc
    r = 0.5 * s

    u = np.linspace(0.0, 2.0 * math.pi, n_u, endpoint=False)
    v = np.linspace(0.0, 2.0 * math.pi, n_v, endpoint=False)

    uu, vv = np.meshgrid(u, v, indexing="ij")

    # tore autour de l'axe X
    x = np.full_like(uu, x_centre_m, dtype=float) + r * np.sin(vv)
    y = (R + r * np.cos(vv)) * np.cos(uu)
    z = (R + r * np.cos(vv)) * np.sin(uu)

    grid = pv.StructuredGrid(x, y, z)
    return grid.extract_surface().triangulate().clean()


# =============================================================================
# Construction complète
# =============================================================================

def construire_mesh_joint_deplaceur_detaille(
    rapport: Dict[str, Any],
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    meshes: Dict[str, pv.PolyData] = {}

    D_dep = geom["diametre_deplaceur_m"]
    L_dep = geom["longueur_deplaceur_m"]
    pos = geom["positions_axiales_rainures_m"]
    lg = geom["largeur_gorge_m"]
    Df = geom["diametre_fond_gorge_m"]
    Dc = geom["diametre_centreline_joint_m"]
    sj = geom["section_joint_m"]

    if D_dep is None or L_dep is None:
        raise ValueError("diametre_deplaceur_m et longueur_deplaceur_m sont requis pour la visualisation.")

    support = _tube_support_deplaceur(L_dep, D_dep)
    meshes["support_initial"] = support

    if pos and lg and Df:
        x_origin = -0.5 * L_dep
        support_creuse = support.copy()
        for x_axial in pos:
            x_local = x_origin + float(x_axial)
            support_creuse = _creuser_gorge_annulaire(
                support_creuse,
                x_centre_m=x_local,
                largeur_gorge_m=lg,
                diametre_fond_gorge_m=Df,
                diametre_deplaceur_m=D_dep,
            )
        meshes["support"] = support_creuse
    else:
        meshes["support"] = support

    if pos and Dc and sj:
        for i, x_axial in enumerate(pos, start=1):
            x_local = -0.5 * L_dep + float(x_axial)
            meshes[f"joint_{i}"] = _mesh_tore(
                diametre_centreline_m=Dc,
                section_joint_m=sj,
                x_centre_m=x_local,
            )

    return meshes, geom


# =============================================================================
# Guides visuels
# =============================================================================

def construire_guides_visuels(geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    D_dep = geom["diametre_deplaceur_m"]
    L_dep = geom["longueur_deplaceur_m"]

    if D_dep is None or L_dep is None:
        return guides

    r = 0.5 * D_dep

    guides["axe"] = pv.Line(
        pointa=(-0.65 * L_dep, 0.0, 0.0),
        pointb=(0.65 * L_dep, 0.0, 0.0),
        resolution=1,
    )

    pos = geom["positions_axiales_rainures_m"]
    if pos:
        pts = []
        x_origin = -0.5 * L_dep
        for x_axial in pos:
            pts.append((x_origin + float(x_axial), r, 0.0))
        if pts:
            guides["centres_rainures"] = pv.PolyData(np.array(pts))

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_joint_deplaceur_3d_detaille(
    source: JointDeplaceur | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    afficher_support: bool = True,
    couleur_support: str = "lightsteelblue",
    couleur_joint: str = "tomato",
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    if isinstance(source, JointDeplaceur):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un JointDeplaceur ou un rapport dict.")

    meshes, geom = construire_mesh_joint_deplaceur_detaille(rapport)

    plotter = pv.Plotter(window_size=(1320, 840))
    plotter.set_background("#1e1e1e")

    if afficher_support and "support" in meshes:
        plotter.add_mesh(
            meshes["support"],
            color=couleur_support,
            smooth_shading=True,
            show_edges=afficher_bords,
            specular=0.20,
            specular_power=16,
            opacity=0.55,
        )

    for name, mesh in meshes.items():
        if name.startswith("joint_"):
            plotter.add_mesh(
                mesh,
                color=couleur_joint,
                smooth_shading=True,
                show_edges=afficher_bords,
                specular=0.35,
                specular_power=26,
            )

    if afficher_guides:
        guides = construire_guides_visuels(geom)

        if "axe" in guides:
            plotter.add_mesh(guides["axe"], color="white", line_width=2)

        if "centres_rainures" in guides:
            plotter.add_mesh(
                guides["centres_rainures"],
                color="cyan",
                point_size=10,
                render_points_as_spheres=True,
            )

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Joint déplaceur — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return meshes, rapport


# =============================================================================
# Exemple minimal
# =============================================================================

if __name__ == "__main__":
    j = JointDeplaceur(
        diametre_deplaceur_m=0.080,
        longueur_deplaceur_m=0.120,
        alesage_cylindre_m=0.0804,
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur=1.5,
        pression_service_pa=150_000.0,
        module_elastomere_pa=7e6,
        coeff_frottement=0.15,
        largeur_bande_contact_m=0.003,
    )

    afficher_joint_deplaceur_3d_detaille(j)
