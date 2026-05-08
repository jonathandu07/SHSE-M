# frontend/pieces/3D/deplaceur.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — DEPLACEUR
# =============================================================================
# But :
# - afficher un déplaceur 3D détaillé à partir de backend/components/moteur_thermique/pieces/deplaceur.py
# - respecter uniquement les données calculées dans rapport["geometrie"]["cao"]
#
# Dépendances :
#   pip install pyvista vtk numpy
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Tuple, Optional, List
import math

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.deplaceur import Deplaceur


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
        raise TypeError("rapport doit être un dictionnaire issu de Deplaceur.analyser().")

    geo = _get_dict(rapport, "geometrie")
    cao = _get_dict(geo, "cao")

    if not cao:
        raise ValueError("Le bloc geometrie.cao est requis pour la visualisation 3D détaillée du déplaceur.")

    rainures = cao.get("rainures_joints")
    rainures = rainures if isinstance(rainures, dict) else None

    return {
        "type_deplaceur": cao.get("type_deplaceur"),
        "diametre_exterieur_m": _req_pos("cao.diametre_exterieur_m", cao.get("diametre_exterieur_m")),
        "diametre_interieur_m": _req_pos("cao.diametre_interieur_m", cao.get("diametre_interieur_m"), strictly=False),
        "longueur_totale_m": _req_pos("cao.longueur_totale_m", cao.get("longueur_totale_m")),
        "chanfrein_extremites_m": (
            _req_pos("cao.chanfrein_extremites_m", cao.get("chanfrein_extremites_m"), strictly=False)
            if cao.get("chanfrein_extremites_m") is not None else 0.0
        ),
        "rayon_conge_m": (
            _req_pos("cao.rayon_conge_m", cao.get("rayon_conge_m"), strictly=False)
            if cao.get("rayon_conge_m") is not None else None
        ),
        "position_axiale_centre_m": (
            _req_finite("cao.position_axiale_centre_m", cao.get("position_axiale_centre_m"))
            if cao.get("position_axiale_centre_m") is not None else None
        ),
        "position_face_froid_m": (
            _req_finite("cao.position_face_froid_m", cao.get("position_face_froid_m"))
            if cao.get("position_face_froid_m") is not None else None
        ),
        "position_face_chaud_m": (
            _req_finite("cao.position_face_chaud_m", cao.get("position_face_chaud_m"))
            if cao.get("position_face_chaud_m") is not None else None
        ),
        "rainures_joints": {
            "nb_joints": int(rainures["nb_joints"]) if rainures and rainures.get("nb_joints") is not None else None,
            "largeur_rainure_m": (
                _req_pos("cao.rainures_joints.largeur_rainure_m", rainures.get("largeur_rainure_m"))
                if rainures and rainures.get("largeur_rainure_m") is not None else None
            ),
            "profondeur_rainure_m": (
                _req_pos("cao.rainures_joints.profondeur_rainure_m", rainures.get("profondeur_rainure_m"))
                if rainures and rainures.get("profondeur_rainure_m") is not None else None
            ),
            "diametre_fond_rainure_m": (
                _req_pos("cao.rainures_joints.diametre_fond_rainure_m", rainures.get("diametre_fond_rainure_m"))
                if rainures and rainures.get("diametre_fond_rainure_m") is not None else None
            ),
            "rayon_fond_rainure_m": (
                _req_pos("cao.rainures_joints.rayon_fond_rainure_m", rainures.get("rayon_fond_rainure_m"), strictly=False)
                if rainures and rainures.get("rayon_fond_rainure_m") is not None else None
            ),
            "positions_axiales_rainures_m": (
                [float(x) for x in rainures.get("positions_axiales_rainures_m", [])]
                if rainures and isinstance(rainures.get("positions_axiales_rainures_m"), list) else None
            ),
            "marge_extremite_m": (
                _req_pos("cao.rainures_joints.marge_extremite_m", rainures.get("marge_extremite_m"), strictly=False)
                if rainures and rainures.get("marge_extremite_m") is not None else None
            ),
            "entraxe_min_m": (
                _req_pos("cao.rainures_joints.entraxe_min_m", rainures.get("entraxe_min_m"), strictly=False)
                if rainures and rainures.get("entraxe_min_m") is not None else None
            ),
        } if rainures else None,
    }


# =============================================================================
# Géométrie extérieure
# =============================================================================

def _profil_rayon_chanfreine(
    longueur_m: float,
    rayon_m: float,
    chanfrein_m: float,
    n_x: int = 120,
) -> Tuple[np.ndarray, np.ndarray]:
    L = _req_pos("longueur_m", longueur_m)
    R = _req_pos("rayon_m", rayon_m)
    c = _req_pos("chanfrein_m", chanfrein_m, strictly=False)

    c_eff = min(c, 0.45 * L, 0.95 * R)

    x = np.linspace(-0.5 * L, 0.5 * L, n_x)
    r = np.full_like(x, R, dtype=float)

    if c_eff > 0.0:
        x_left0 = -0.5 * L
        x_left1 = x_left0 + c_eff
        x_right0 = 0.5 * L - c_eff
        x_right1 = 0.5 * L

        left_mask = x <= x_left1
        right_mask = x >= x_right0

        r[left_mask] = (R - c_eff) + ((x[left_mask] - x_left0) / c_eff) * c_eff
        r[right_mask] = R - ((x[right_mask] - x_right0) / c_eff) * c_eff

    r = np.clip(r, 1e-9, None)
    return x, r


def _mesh_revolution_axe_x(
    longueur_m: float,
    rayon_exterieur_m: float,
    chanfrein_m: float,
    n_x: int = 120,
    n_theta: int = 180,
) -> pv.PolyData:
    x_prof, r_prof = _profil_rayon_chanfreine(
        longueur_m=longueur_m,
        rayon_m=rayon_exterieur_m,
        chanfrein_m=chanfrein_m,
        n_x=n_x,
    )

    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)

    X = np.repeat(x_prof[:, None], n_theta, axis=1)
    Y = r_prof[:, None] * np.cos(theta)[None, :]
    Z = r_prof[:, None] * np.sin(theta)[None, :]

    grid = pv.StructuredGrid(X, Y, Z)
    surf = grid.extract_surface().triangulate().clean()

    r_face = max(rayon_exterieur_m - min(chanfrein_m, 0.95 * rayon_exterieur_m), 1e-9)

    cap_g = pv.Cylinder(
        center=(-0.5 * longueur_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_face,
        height=1e-6,
        resolution=max(48, n_theta),
        capping=True,
    ).triangulate()

    cap_d = pv.Cylinder(
        center=(0.5 * longueur_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_face,
        height=1e-6,
        resolution=max(48, n_theta),
        capping=True,
    ).triangulate()

    return surf.merge(cap_g).merge(cap_d).clean()


def _creuser_alésage_central(
    mesh: pv.PolyData,
    longueur_m: float,
    rayon_interieur_m: float,
) -> pv.PolyData:
    if rayon_interieur_m <= 0.0:
        return mesh

    cyl = pv.Cylinder(
        center=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=rayon_interieur_m,
        height=longueur_m + 1e-4,
        resolution=180,
        capping=True,
    ).triangulate()

    try:
        return mesh.boolean_difference(cyl).clean()
    except Exception:
        return mesh


# =============================================================================
# Rainures de joints
# =============================================================================

def _creuser_rainures_joints(
    mesh: pv.PolyData,
    geom: Dict[str, Any],
) -> pv.PolyData:
    rj = geom["rainures_joints"]
    if not rj:
        return mesh

    largeur = rj["largeur_rainure_m"]
    profondeur = rj["profondeur_rainure_m"]
    diam_fond = rj["diametre_fond_rainure_m"]
    positions = rj["positions_axiales_rainures_m"]

    if not largeur or not profondeur or not diam_fond or not positions:
        return mesh

    L = geom["longueur_totale_m"]
    x_origin = -0.5 * L
    r_ext = 0.5 * geom["diametre_exterieur_m"]
    r_fond = 0.5 * diam_fond

    out = mesh
    for xpos in positions:
        x_local = x_origin + float(xpos)

        # gorge annulaire
        gorge = pv.Cylinder(
            center=(x_local, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),
            radius=r_ext,
            height=largeur,
            resolution=180,
            capping=True,
        ).triangulate()

        noyau = pv.Cylinder(
            center=(x_local, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),
            radius=r_fond,
            height=largeur + 1e-5,
            resolution=180,
            capping=True,
        ).triangulate()

        try:
            anneau = gorge.boolean_difference(noyau).clean()
            out = out.boolean_difference(anneau).clean()
        except Exception:
            continue

    return out


# =============================================================================
# Construction complète
# =============================================================================

def construire_mesh_deplaceur_detaille(
    rapport: Dict[str, Any],
    *,
    n_x: int = 120,
    n_theta: int = 180,
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    de = geom["diametre_exterieur_m"]
    di = geom["diametre_interieur_m"]
    L = geom["longueur_totale_m"]
    ch = geom["chanfrein_extremites_m"]

    mesh = _mesh_revolution_axe_x(
        longueur_m=L,
        rayon_exterieur_m=0.5 * de,
        chanfrein_m=ch,
        n_x=n_x,
        n_theta=n_theta,
    )

    if di > 0.0:
        mesh = _creuser_alésage_central(mesh, L, 0.5 * di)

    mesh = _creuser_rainures_joints(mesh, geom)

    return mesh.clean(), geom


# =============================================================================
# Guides visuels
# =============================================================================

def construire_guides_visuels(geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    L = geom["longueur_totale_m"]
    de = geom["diametre_exterieur_m"]
    r = 0.5 * de

    guides["axe"] = pv.Line(
        pointa=(-0.65 * L, 0.0, 0.0),
        pointb=(0.65 * L, 0.0, 0.0),
        resolution=1,
    )

    if geom["position_face_froid_m"] is not None:
        x = float(geom["position_face_froid_m"])
        guides["plan_face_froid"] = pv.Line(
            pointa=(x, -1.2 * r, 0.0),
            pointb=(x, 1.2 * r, 0.0),
            resolution=1,
        )

    if geom["position_face_chaud_m"] is not None:
        x = float(geom["position_face_chaud_m"])
        guides["plan_face_chaud"] = pv.Line(
            pointa=(x, -1.2 * r, 0.0),
            pointb=(x, 1.2 * r, 0.0),
            resolution=1,
        )

    rj = geom["rainures_joints"]
    if rj and rj["positions_axiales_rainures_m"]:
        x_origin = -0.5 * L
        pts = []
        for xpos in rj["positions_axiales_rainures_m"]:
            pts.append((x_origin + float(xpos), r, 0.0))
        if pts:
            guides["centres_rainures"] = pv.PolyData(np.array(pts))

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_deplaceur_3d_detaille(
    source: Deplaceur | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    couleur_deplaceur: str = "lightsteelblue",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    if isinstance(source, Deplaceur):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un Deplaceur ou un rapport dict.")

    mesh, geom = construire_mesh_deplaceur_detaille(rapport)

    plotter = pv.Plotter(window_size=(1320, 840))
    plotter.set_background("#1e1e1e")

    plotter.add_mesh(
        mesh,
        color=couleur_deplaceur,
        smooth_shading=True,
        show_edges=afficher_bords,
        specular=0.30,
        specular_power=24,
    )

    if afficher_guides:
        guides = construire_guides_visuels(geom)

        if "axe" in guides:
            plotter.add_mesh(guides["axe"], color="white", line_width=2)

        if "plan_face_froid" in guides:
            plotter.add_mesh(guides["plan_face_froid"], color="gold", line_width=2)

        if "plan_face_chaud" in guides:
            plotter.add_mesh(guides["plan_face_chaud"], color="tomato", line_width=2)

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

    plotter.add_text("Déplaceur — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh, rapport


# =============================================================================
# Exemple minimal
# =============================================================================

if __name__ == "__main__":
    d = Deplaceur(
        diametre_exterieur_m=0.070,
        longueur_totale_m=0.090,
        course_disponible_m=0.040,
        jeu_radial_m=0.0005,
        type_deplaceur="tubulaire",
        standard_joint="ISO_3601",
        section_joint_mm=2.5,
        taux_compression_joint=0.20,
        nb_joints=2,
        delta_p_chaud_froid_pa=50000.0,
        module_young_pa=210e9,
        densite_kg_m3=7800.0,
    )

    afficher_deplaceur_3d_detaille(d)
