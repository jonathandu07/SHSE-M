# frontend/pieces/3D/piston.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — PISTON
# =============================================================================
# But :
# - afficher un piston 3D à partir du rapport backend/pieces/piston.py
# - utiliser strictement les dimensions calculées
# - montrer tête, jupe, rainures et joints
#
# Dépendances :
#   pip install pyvista vtk numpy
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Tuple, List, Optional
import math

import numpy as np
import pyvista as pv

from backend.pieces.piston import Piston


# =============================================================================
# Helpers
# =============================================================================

def _is_finite(x: Any) -> bool:
    try:
        v = float(x)
        return math.isfinite(v)
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


def _safe_dict(d: Any, key: str) -> Dict[str, Any]:
    if isinstance(d, dict):
        v = d.get(key, {})
        return v if isinstance(v, dict) else {}
    return {}


# =============================================================================
# Extraction depuis rapport piston
# =============================================================================

def extraire_cao_piston(rapport: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dictionnaire issu de Piston.analyser().")

    dims = _safe_dict(rapport, "dimensions")
    cao = _safe_dict(dims, "cao")
    joints = _safe_dict(cao, "joints")
    joints_bloc = _safe_dict(rapport, "joints")

    diam_ext = cao.get("diametre_exterieur_nominal_m")
    h_tot = cao.get("hauteur_totale_m")
    ep_tete = cao.get("epaisseur_tete_m")
    l_jupe = cao.get("longueur_jupe_m")
    chanfrein = cao.get("chanfrein_extremites_m")
    rayon_conge = cao.get("rayon_conge_tete_jupe_m")

    rainures = cao.get("rainures")
    if not isinstance(rainures, list):
        rainures = joints.get("rainures")
    if not isinstance(rainures, list):
        rainures = joints_bloc.get("rainures")
    if not isinstance(rainures, list):
        rainures = []

    return {
        "diametre_exterieur_nominal_m": _req_pos("diametre_exterieur_nominal_m", diam_ext),
        "hauteur_totale_m": _req_pos("hauteur_totale_m", h_tot),
        "epaisseur_tete_m": _req_pos("epaisseur_tete_m", ep_tete, strictly=False) if ep_tete is not None else None,
        "longueur_jupe_m": _req_pos("longueur_jupe_m", l_jupe, strictly=False) if l_jupe is not None else None,
        "chanfrein_extremites_m": _req_pos("chanfrein_extremites_m", chanfrein, strictly=False) if chanfrein is not None else 0.0,
        "rayon_conge_tete_jupe_m": _req_pos("rayon_conge_tete_jupe_m", rayon_conge, strictly=False) if rayon_conge is not None else 0.0,
        "nb_joints": joints.get("nb_joints", joints_bloc.get("nb_joints")),
        "section_joint_m": joints.get("section_joint_m", joints_bloc.get("section_joint_m")),
        "diametre_fond_rainure_m": joints.get("diametre_fond_rainure_m", joints_bloc.get("diametre_fond_rainure_m")),
        "largeur_rainure_m": joints.get("largeur_rainure_m", joints_bloc.get("largeur_rainure_m")),
        "profondeur_radiale_rainure_m": joints.get("profondeur_radiale_rainure_m", joints_bloc.get("profondeur_radiale_rainure_m")),
        "positions_centres_depuis_face_tete_m": joints.get("positions_centres_depuis_face_tete_m", joints_bloc.get("positions_centres_depuis_face_tete_m")),
        "diametre_moyen_joint_monte_m": joints.get("diametre_moyen_joint_monte_m", joints_bloc.get("diametre_moyen_joint_monte_m")),
        "rainures": rainures,
    }


# =============================================================================
# Géométrie primitive
# =============================================================================

def _cylindre_z(
    *,
    z_min: float,
    z_max: float,
    diametre_m: float,
    resolution: int = 180,
) -> pv.PolyData:
    h = _req_pos("hauteur_cylindre", z_max - z_min)
    zc = 0.5 * (z_min + z_max)
    return pv.Cylinder(
        center=(0.0, 0.0, zc),
        direction=(0.0, 0.0, 1.0),
        radius=0.5 * _req_pos("diametre_m", diametre_m),
        height=h,
        resolution=resolution,
        capping=True,
    ).triangulate().clean()


def _tore_xy(
    *,
    z_centre_m: float,
    diametre_centreline_m: float,
    section_joint_m: float,
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

    x = (R + r * np.cos(vv)) * np.cos(uu)
    y = (R + r * np.cos(vv)) * np.sin(uu)
    z = np.full_like(uu, z_centre_m, dtype=float) + r * np.sin(vv)

    grid = pv.StructuredGrid(x, y, z)
    return grid.extract_surface().triangulate().clean()


def _creuser_rainure_externe(
    mesh: pv.PolyData,
    *,
    z_centre_m: float,
    largeur_m: float,
    diametre_fond_rainure_m: float,
    diametre_zone_hors_rainure_m: float,
) -> pv.PolyData:
    w = _req_pos("largeur_m", largeur_m)
    df = _req_pos("diametre_fond_rainure_m", diametre_fond_rainure_m)
    de = _req_pos("diametre_zone_hors_rainure_m", diametre_zone_hors_rainure_m)

    r_ext = 0.5 * de
    r_fond = 0.5 * df

    if r_fond >= r_ext:
        return mesh

    ext = pv.Cylinder(
        center=(0.0, 0.0, z_centre_m),
        direction=(0.0, 0.0, 1.0),
        radius=r_ext,
        height=w,
        resolution=160,
        capping=True,
    ).triangulate()

    inte = pv.Cylinder(
        center=(0.0, 0.0, z_centre_m),
        direction=(0.0, 0.0, 1.0),
        radius=r_fond,
        height=w + 1e-5,
        resolution=160,
        capping=True,
    ).triangulate()

    try:
        gorge = ext.boolean_difference(inte).clean()
        return mesh.boolean_difference(gorge).clean()
    except Exception:
        return mesh


def _ajouter_chanfrein_visuel(
    mesh: pv.PolyData,
    *,
    diametre_m: float,
    hauteur_totale_m: float,
    chanfrein_m: float,
) -> pv.PolyData:
    if chanfrein_m <= 0.0:
        return mesh

    r_ext = 0.5 * diametre_m
    h = hauteur_totale_m
    c = min(chanfrein_m, 0.2 * h, 0.2 * r_ext)

    try:
        cone_bas = pv.Cone(
            center=(0.0, 0.0, -0.5 * h + 0.5 * c),
            direction=(0.0, 0.0, 1.0),
            height=c,
            radius=r_ext + c,
            resolution=120,
        ).triangulate()

        cone_haut = pv.Cone(
            center=(0.0, 0.0, +0.5 * h - 0.5 * c),
            direction=(0.0, 0.0, -1.0),
            height=c,
            radius=r_ext + c,
            resolution=120,
        ).triangulate()

        mesh2 = mesh.boolean_difference(cone_bas).clean()
        mesh3 = mesh2.boolean_difference(cone_haut).clean()
        return mesh3
    except Exception:
        return mesh


# =============================================================================
# Construction 3D détaillée
# =============================================================================

def construire_piston_3d_detaille(
    rapport: Dict[str, Any],
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    g = extraire_cao_piston(rapport)

    D = g["diametre_exterieur_nominal_m"]
    H = g["hauteur_totale_m"]
    ep_tete = g["epaisseur_tete_m"] if g["epaisseur_tete_m"] is not None else 0.0
    L_jupe = g["longueur_jupe_m"] if g["longueur_jupe_m"] is not None else max(0.0, H - ep_tete)
    chanfrein = g["chanfrein_extremites_m"]
    rainures = g["rainures"]

    z_min = -0.5 * H
    z_max = 0.5 * H

    meshes: Dict[str, pv.PolyData] = {}

    corps = _cylindre_z(z_min=z_min, z_max=z_max, diametre_m=D)
    corps = _ajouter_chanfrein_visuel(
        corps,
        diametre_m=D,
        hauteur_totale_m=H,
        chanfrein_m=chanfrein,
    )

    # Gorges détaillées
    support = corps.copy()
    joints_meshes: List[pv.PolyData] = []

    if isinstance(rainures, list) and rainures:
        for i, r in enumerate(rainures, start=1):
            if not isinstance(r, dict):
                continue

            zc = r.get("position_centre_depuis_face_tete_m")
            w = r.get("largeur_m")
            df = r.get("diametre_fond_rainure_m")
            d_joint = r.get("section_joint_m")
            d_moy_joint = r.get("diametre_moyen_joint_monte_m")

            if zc is not None and _is_finite(zc):
                zc_global = z_min + float(zc)
            else:
                continue

            if w is not None and df is not None and _is_finite(w) and _is_finite(df):
                support = _creuser_rainure_externe(
                    support,
                    z_centre_m=zc_global,
                    largeur_m=float(w),
                    diametre_fond_rainure_m=float(df),
                    diametre_zone_hors_rainure_m=D,
                )

            if d_joint is not None and d_moy_joint is not None and _is_finite(d_joint) and _is_finite(d_moy_joint):
                joints_meshes.append(
                    _tore_xy(
                        z_centre_m=zc_global,
                        diametre_centreline_m=float(d_moy_joint),
                        section_joint_m=float(d_joint),
                    )
                )

    else:
        nbj = g["nb_joints"]
        w = g["largeur_rainure_m"]
        df = g["diametre_fond_rainure_m"]
        section_joint = g["section_joint_m"]
        positions = g["positions_centres_depuis_face_tete_m"]
        d_moy_joint = g["diametre_moyen_joint_monte_m"]

        if nbj and positions and w and df:
            for zc in positions:
                if _is_finite(zc):
                    zc_global = z_min + float(zc)

                    support = _creuser_rainure_externe(
                        support,
                        z_centre_m=zc_global,
                        largeur_m=float(w),
                        diametre_fond_rainure_m=float(df),
                        diametre_zone_hors_rainure_m=D,
                    )

                    if section_joint is not None and d_moy_joint is not None:
                        joints_meshes.append(
                            _tore_xy(
                                z_centre_m=zc_global,
                                diametre_centreline_m=float(d_moy_joint),
                                section_joint_m=float(section_joint),
                            )
                        )

    meshes["piston"] = support

    # Tête et jupe en guides visuels
    if ep_tete > 0.0:
        meshes["zone_tete"] = _cylindre_z(
            z_min=z_max - ep_tete,
            z_max=z_max,
            diametre_m=D * 1.001,
        )

    if L_jupe > 0.0:
        meshes["zone_jupe"] = _cylindre_z(
            z_min=z_min,
            z_max=z_min + L_jupe,
            diametre_m=D * 1.001,
        )

    for i, jm in enumerate(joints_meshes, start=1):
        meshes[f"joint_{i}"] = jm

    return meshes, g


# =============================================================================
# Guides
# =============================================================================

def construire_guides_piston(meshes: Dict[str, pv.PolyData], g: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    piston = meshes.get("piston")
    if piston is None:
        return guides

    bounds = piston.bounds
    xmin, xmax, ymin, ymax, zmin, zmax = bounds

    guides["axe"] = pv.Line(
        pointa=(0.0, 0.0, zmin - 0.1 * (zmax - zmin)),
        pointb=(0.0, 0.0, zmax + 0.1 * (zmax - zmin)),
        resolution=1,
    )

    rainures = g["rainures"]
    pts = []

    if isinstance(rainures, list) and rainures:
        for r in rainures:
            if isinstance(r, dict) and r.get("position_centre_depuis_face_tete_m") is not None and _is_finite(r["position_centre_depuis_face_tete_m"]):
                z_local = float(r["position_centre_depuis_face_tete_m"])
                z_global = zmin + z_local
                pts.append((0.6 * ymax, 0.0, z_global))

    if pts:
        guides["centres_rainures"] = pv.PolyData(np.array(pts))

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_piston_3d_detaille(
    source: Piston | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    couleur_piston: str = "lightsteelblue",
    couleur_tete: str = "orange",
    couleur_jupe: str = "khaki",
    couleur_joint: str = "tomato",
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    if isinstance(source, Piston):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un Piston ou un rapport dict.")

    meshes, geom = construire_piston_3d_detaille(rapport)

    plotter = pv.Plotter(window_size=(1360, 860))
    plotter.set_background("#1e1e1e")

    if "piston" in meshes:
        plotter.add_mesh(
            meshes["piston"],
            color=couleur_piston,
            smooth_shading=True,
            opacity=0.72,
            show_edges=afficher_bords,
            specular=0.22,
            specular_power=18,
        )

    if "zone_tete" in meshes:
        plotter.add_mesh(
            meshes["zone_tete"],
            color=couleur_tete,
            opacity=0.18,
            smooth_shading=True,
            show_edges=False,
        )

    if "zone_jupe" in meshes:
        plotter.add_mesh(
            meshes["zone_jupe"],
            color=couleur_jupe,
            opacity=0.14,
            smooth_shading=True,
            show_edges=False,
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
        guides = construire_guides_piston(meshes, geom)

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

    plotter.add_text("Piston — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return meshes, rapport


# =============================================================================
# Exemple
# =============================================================================

if __name__ == "__main__":
    p = Piston(
        alesage_nominal_m=0.080,
        fit_hole="H7",
        fit_shaft="h6",
        pression_max_pa=15e5,
        temperature_fonctionnement_k=350.0,
        course_m=0.060,
        rpm=1200.0,
        materiau_piston_cle="alu_7075_t6",
        materiau_cylindre_cle="acier_42crmo4_qt",
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur_rainure=1.5,
        materiau_joint_cle="nbr_70",
        coeff_frottement_joint=0.15,
        PV_admissible_pa_ms=2.0e6,
        longueur_portee_etanche_m=0.010,
        pression_aval_pa=1e5,
    )

    afficher_piston_3d_detaille(p)