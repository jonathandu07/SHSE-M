# frontend/pieces/3D/joint_piston.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — JOINT PISTON
# =============================================================================
# But :
# - afficher un joint piston / ses rainures en 3D
# - utiliser les données de backend/pieces/joint_piston.py
# - ne rien inventer hors du rapport calculé
#
# Dépendances :
#   pip install pyvista vtk numpy
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Tuple, List, Optional
import math

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.joint_piston import JointPiston


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
        raise TypeError("rapport doit être un dictionnaire issu de JointPiston.analyser().")

    entrees = rapport.get("entrees", {}) if isinstance(rapport.get("entrees"), dict) else {}
    geo_joint = rapport.get("geometrie_joint", {}) if isinstance(rapport.get("geometrie_joint"), dict) else {}
    gorge = rapport.get("gorge", {}) if isinstance(rapport.get("gorge"), dict) else {}
    rainures = rapport.get("rainures", {}) if isinstance(rapport.get("rainures"), dict) else {}

    details = rainures.get("details")
    if not isinstance(details, list):
        details = []

    return {
        "diametre_interieur_cylindre_m": (
            _req_pos("entrees.diametre_interieur_cylindre_m", entrees.get("diametre_interieur_cylindre_m"))
            if entrees.get("diametre_interieur_cylindre_m") is not None else None
        ),
        "diametre_interieur_joint_m": (
            _req_pos("entrees.diametre_interieur_joint_m", entrees.get("diametre_interieur_joint_m"))
            if entrees.get("diametre_interieur_joint_m") is not None else None
        ),
        "diametre_section_joint_m": (
            _req_pos("entrees.diametre_section_joint_m", entrees.get("diametre_section_joint_m"))
            if entrees.get("diametre_section_joint_m") is not None else None
        ),
        "diametre_moyen_joint_m": (
            _req_pos("geometrie_joint.diametre_moyen_joint_m", geo_joint.get("diametre_moyen_joint_m"))
            if geo_joint.get("diametre_moyen_joint_m") is not None else None
        ),
        "diametre_fond_gorge_m": (
            _req_pos("entrees.diametre_fond_gorge_m", entrees.get("diametre_fond_gorge_m"))
            if entrees.get("diametre_fond_gorge_m") is not None else None
        ),
        "profondeur_gorge_m": (
            _req_pos("entrees.profondeur_gorge_m", entrees.get("profondeur_gorge_m"))
            if entrees.get("profondeur_gorge_m") is not None else None
        ),
        "largeur_gorge_m": (
            _req_pos("entrees.largeur_gorge_m", entrees.get("largeur_gorge_m"))
            if entrees.get("largeur_gorge_m") is not None else None
        ),
        "largeur_bande_contact_m": (
            _req_pos("entrees.largeur_bande_contact_m", entrees.get("largeur_bande_contact_m"))
            if entrees.get("largeur_bande_contact_m") is not None else None
        ),
        "taux_remplissage": gorge.get("taux_remplissage_volume_joint_sur_gorge"),
        "rainures_details": details,
        "nombre_rainures": int(rainures["nombre_rainures"]) if rainures.get("nombre_rainures") is not None else len(details),
    }


# =============================================================================
# Géométrie de base
# =============================================================================

def _cylindre_plein_x(longueur_m: float, diametre_m: float, resolution: int = 180) -> pv.PolyData:
    return pv.Cylinder(
        center=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=0.5 * _req_pos("diametre_m", diametre_m),
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
    diametre_exterieur_support_m: float,
) -> pv.PolyData:
    w = _req_pos("largeur_gorge_m", largeur_gorge_m)
    df = _req_pos("diametre_fond_gorge_m", diametre_fond_gorge_m)
    de = _req_pos("diametre_exterieur_support_m", diametre_exterieur_support_m)

    r_ext = 0.5 * de
    r_fond = 0.5 * df

    if r_fond >= r_ext:
        return mesh

    ext = pv.Cylinder(
        center=(x_centre_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_ext,
        height=w,
        resolution=160,
        capping=True,
    ).triangulate()

    inte = pv.Cylinder(
        center=(x_centre_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
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

    x = np.full_like(uu, x_centre_m, dtype=float) + r * np.sin(vv)
    y = (R + r * np.cos(vv)) * np.cos(uu)
    z = (R + r * np.cos(vv)) * np.sin(uu)

    grid = pv.StructuredGrid(x, y, z)
    return grid.extract_surface().triangulate().clean()


# =============================================================================
# Construction complète
# =============================================================================

def construire_mesh_joint_piston_detaille(
    rapport: Dict[str, Any],
    *,
    longueur_support_m: Optional[float] = None,
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    D_fond = geom["diametre_fond_gorge_m"]
    prof = geom["profondeur_gorge_m"]
    w = geom["largeur_gorge_m"]
    ID = geom["diametre_interieur_joint_m"]
    CS = geom["diametre_section_joint_m"]
    D_moy = geom["diametre_moyen_joint_m"]
    rainures_details = geom["rainures_details"]

    if D_fond is None or prof is None:
        raise ValueError("diametre_fond_gorge_m et profondeur_gorge_m sont requis pour le viewer 3D.")

    D_support = D_fond + 2.0 * prof
    if D_support <= 0:
        raise ValueError("Diamètre support invalide.")

    # Longueur support
    if longueur_support_m is None:
        xs = []
        if rainures_details:
            for r in rainures_details:
                if not isinstance(r, dict):
                    continue
                for k in ("position_debut_depuis_face_tete_m", "position_fin_depuis_face_tete_m"):
                    if r.get(k) is not None and _is_finite(r.get(k)):
                        xs.append(float(r[k]))
        if xs:
            longueur_support_m = max(xs) + 0.02
        else:
            largeur_ref = w if w is not None else max(CS or 0.003, 0.003)
            longueur_support_m = 8.0 * largeur_ref

    Ls = _req_pos("longueur_support_m", longueur_support_m)

    meshes: Dict[str, pv.PolyData] = {}
    support = _cylindre_plein_x(Ls, D_support)
    meshes["support_initial"] = support

    # Cas rainures multiples détaillées
    if rainures_details:
        support_creuse = support.copy()
        x_origin = -0.5 * Ls

        for i, r in enumerate(rainures_details, start=1):
            if not isinstance(r, dict):
                continue

            lg = r.get("largeur_m")
            df = r.get("diametre_fond_rainure_m")
            x0 = r.get("position_debut_depuis_face_tete_m")
            x1 = r.get("position_fin_depuis_face_tete_m")
            xc = r.get("position_centre_depuis_face_tete_m")

            if xc is None and x0 is not None and x1 is not None and _is_finite(x0) and _is_finite(x1):
                xc = 0.5 * (float(x0) + float(x1))

            if lg is not None and df is not None and xc is not None and _is_finite(lg) and _is_finite(df) and _is_finite(xc):
                x_local = x_origin + float(xc)
                support_creuse = _creuser_gorge_annulaire(
                    support_creuse,
                    x_centre_m=x_local,
                    largeur_gorge_m=float(lg),
                    diametre_fond_gorge_m=float(df),
                    diametre_exterieur_support_m=D_support,
                )

                # tore local si possible
                sec_loc = r.get("section_joint_m")
                dmont = r.get("diametre_montage_joint_m")
                dmoy_loc = r.get("diametre_moyen_joint_monte_m")

                section_use = float(sec_loc) if _is_finite(sec_loc) else CS
                diam_moy_use = float(dmoy_loc) if _is_finite(dmoy_loc) else D_moy

                if diam_moy_use is None and section_use is not None and _is_finite(dmont):
                    diam_moy_use = float(dmont) + float(section_use)

                if diam_moy_use is not None and section_use is not None:
                    meshes[f"joint_{i}"] = _mesh_tore(
                        diametre_centreline_m=diam_moy_use,
                        section_joint_m=section_use,
                        x_centre_m=x_local,
                    )

        meshes["support"] = support_creuse

    else:
        meshes["support"] = support

        # Cas simple mono-rainure au centre
        if w is not None:
            meshes["support"] = _creuser_gorge_annulaire(
                meshes["support"],
                x_centre_m=0.0,
                largeur_gorge_m=w,
                diametre_fond_gorge_m=D_fond,
                diametre_exterieur_support_m=D_support,
            )

            if D_moy is not None and CS is not None:
                meshes["joint_1"] = _mesh_tore(
                    diametre_centreline_m=D_moy,
                    section_joint_m=CS,
                    x_centre_m=0.0,
                )
            elif ID is not None and CS is not None:
                meshes["joint_1"] = _mesh_tore(
                    diametre_centreline_m=ID + CS,
                    section_joint_m=CS,
                    x_centre_m=0.0,
                )

    return meshes, geom


# =============================================================================
# Guides visuels
# =============================================================================

def construire_guides_visuels(meshes: Dict[str, pv.PolyData], geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    support = meshes.get("support")
    if support is not None:
        bounds = support.bounds
        xmin, xmax = bounds[0], bounds[1]
        ymax = max(abs(bounds[2]), abs(bounds[3]), abs(bounds[4]), abs(bounds[5]))

        guides["axe"] = pv.Line(
            pointa=(xmin - 0.1 * (xmax - xmin), 0.0, 0.0),
            pointb=(xmax + 0.1 * (xmax - xmin), 0.0, 0.0),
            resolution=1,
        )

        details = geom["rainures_details"]
        if details:
            pts = []
            for r in details:
                if isinstance(r, dict) and r.get("position_centre_depuis_face_tete_m") is not None and _is_finite(r.get("position_centre_depuis_face_tete_m")):
                    pts.append((xmin + float(r["position_centre_depuis_face_tete_m"]), ymax, 0.0))
            if pts:
                guides["centres_rainures"] = pv.PolyData(np.array(pts))

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_joint_piston_3d_detaille(
    source: JointPiston | Dict[str, Any],
    *,
    longueur_support_m: Optional[float] = None,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    afficher_support: bool = True,
    couleur_support: str = "lightsteelblue",
    couleur_joint: str = "tomato",
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    if isinstance(source, JointPiston):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un JointPiston ou un rapport dict.")

    meshes, geom = construire_mesh_joint_piston_detaille(
        rapport,
        longueur_support_m=longueur_support_m,
    )

    plotter = pv.Plotter(window_size=(1320, 840))
    plotter.set_background("#1e1e1e")

    if afficher_support and "support" in meshes:
        plotter.add_mesh(
            meshes["support"],
            color=couleur_support,
            smooth_shading=True,
            show_edges=afficher_bords,
            opacity=0.55,
            specular=0.18,
            specular_power=16,
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
        guides = construire_guides_visuels(meshes, geom)

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

    plotter.add_text("Joint piston — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return meshes, rapport


# =============================================================================
# Exemple minimal
# =============================================================================

if __name__ == "__main__":
    jp = JointPiston(
        diametre_interieur_cylindre_m=0.080,
        diametre_interieur_joint_m=0.074,
        diametre_section_joint_m=0.003,
        diametre_fond_gorge_m=0.077,
        profondeur_gorge_m=0.0012,
        largeur_gorge_m=0.0045,
        largeur_bande_contact_m=0.003,
        coeff_frottement_mu=0.15,
        pression_contact_pa=2e6,
        materiau_joint_cle="nbr_70",
    )

    afficher_joint_piston_3d_detaille(jp)