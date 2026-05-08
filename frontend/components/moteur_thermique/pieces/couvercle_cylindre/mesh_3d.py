# frontend/pieces/3D/couvercle_cylindre.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — COUVERCLE CYLINDRE
# =============================================================================
# But :
# - afficher un couvercle de cylindre 3D détaillé à partir du backend
# - utiliser uniquement les données du bloc rapport["geometrie"]["cao"]
# - ne pas inventer de formes absentes du backend
#
# Dépendances :
#   pip install pyvista vtk numpy
#
# Modélise :
# - calotte sphérique
# - bride annulaire
# - perçages sur cercle de perçage si définis
# - axe, cercle de perçage, repères visuels
#
# Limites volontaires :
# - pas de taraudage réel
# - pas de têtes de vis
# - pas de joint torique 3D
# - pas de nervures/bossages si non fournis
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import math
import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.couvercle_cylindre import CouvercleCylindre


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
# Extraction
# =============================================================================

def extraire_geometrie_depuis_rapport(rapport: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dictionnaire issu de CouvercleCylindre.analyser().")

    geo = _get_dict(rapport, "geometrie")
    cao = _get_dict(geo, "cao")
    bride = _get_dict(cao, "bride")
    assemblage = _get_dict(cao, "assemblage")

    if not cao:
        raise ValueError(
            "Le bloc geometrie.cao est absent. "
            "La visualisation 3D détaillée nécessite un rapport avec le bloc CAO complet."
        )

    geom = {
        "forme": cao.get("forme"),
        "diametre_ouverture_m": _req_pos("cao.diametre_ouverture_m", cao.get("diametre_ouverture_m")),
        "rayon_base_calotte_m": _req_pos("cao.rayon_base_calotte_m", cao.get("rayon_base_calotte_m")),
        "hauteur_bombe_interieure_m": _req_pos("cao.hauteur_bombe_interieure_m", cao.get("hauteur_bombe_interieure_m")),
        "rayon_courbure_interieur_m": _req_pos("cao.rayon_courbure_interieur_m", cao.get("rayon_courbure_interieur_m")),
        "rayon_courbure_exterieur_m": _req_pos("cao.rayon_courbure_exterieur_m", cao.get("rayon_courbure_exterieur_m")),
        "epaisseur_calotte_m": _req_pos("cao.epaisseur_calotte_m", cao.get("epaisseur_calotte_m")),
        "diametre_exterieur_calotte_base_m": _req_pos(
            "cao.diametre_exterieur_calotte_base_m",
            cao.get("diametre_exterieur_calotte_base_m"),
        ),
        "chanfrein_m": (
            _req_pos("cao.chanfrein_m", cao.get("chanfrein_m"), strictly=False)
            if cao.get("chanfrein_m") is not None else 0.0
        ),
        "conge_m": (
            _req_pos("cao.conge_m", cao.get("conge_m"), strictly=False)
            if cao.get("conge_m") is not None else None
        ),

        "bride_rayon_interne_m": (
            _req_pos("cao.bride.rayon_bride_interne_m", bride.get("rayon_bride_interne_m"))
            if bride.get("rayon_bride_interne_m") is not None else None
        ),
        "bride_rayon_externe_m": (
            _req_pos("cao.bride.rayon_bride_externe_m", bride.get("rayon_bride_externe_m"))
            if bride.get("rayon_bride_externe_m") is not None else None
        ),
        "bride_epaisseur_m": (
            _req_pos("cao.bride.epaisseur_bride_m", bride.get("epaisseur_bride_m"))
            if bride.get("epaisseur_bride_m") is not None else None
        ),
        "bride_largeur_m": (
            _req_pos("cao.bride.largeur_bride_m", bride.get("largeur_bride_m"))
            if bride.get("largeur_bride_m") is not None else None
        ),

        "diametre_cercle_percage_m": (
            _req_pos("cao.assemblage.diametre_cercle_percage_m", assemblage.get("diametre_cercle_percage_m"))
            if assemblage.get("diametre_cercle_percage_m") is not None else None
        ),
        "diametre_trou_m": (
            _req_pos("cao.assemblage.diametre_trou_m", assemblage.get("diametre_trou_m"))
            if assemblage.get("diametre_trou_m") is not None else None
        ),
        "angles_trous_deg": (
            [float(a) for a in assemblage.get("angles_trous_deg")]
            if isinstance(assemblage.get("angles_trous_deg"), list) else None
        ),
        "nb_vis": (
            int(assemblage.get("nb_vis"))
            if assemblage.get("nb_vis") is not None else None
        ),
    }

    if geom["rayon_courbure_exterieur_m"] <= geom["rayon_courbure_interieur_m"]:
        raise ValueError("Géométrie invalide : rayon extérieur <= rayon intérieur.")

    return geom


# =============================================================================
# Calotte sphérique
# =============================================================================

def _calotte_surface_points(
    rayon_m: float,
    rayon_base_m: float,
    z_decalage_m: float,
    n_theta: int = 180,
    n_phi: int = 80,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Génère une calotte sphérique de révolution autour de Z.
    Convention :
    - plan de base de la calotte à z = 0
    - sommet de la calotte vers +Z
    - centre de la sphère situé sur l'axe Z à z = z_decalage_m
    """
    R = _req_pos("rayon_m", rayon_m)
    a = _req_pos("rayon_base_m", rayon_base_m)
    if a >= R:
        raise ValueError("rayon_base_m doit être < rayon_m")

    phi_max = math.asin(a / R)
    phis = np.linspace(0.0, phi_max, n_phi)
    thetas = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)

    # sphère paramétrée autour du centre (0,0,z_decalage_m)
    rr = R * np.sin(phis)
    zz = z_decalage_m + R * np.cos(phis)

    X = np.repeat(rr[:, None], n_theta, axis=1) * np.cos(thetas)[None, :]
    Y = np.repeat(rr[:, None], n_theta, axis=1) * np.sin(thetas)[None, :]
    Z = np.repeat(zz[:, None], n_theta, axis=1)

    return X, Y, Z


def _mesh_calotte_epaisse(
    rayon_interieur_m: float,
    rayon_exterieur_m: float,
    rayon_base_m: float,
    n_theta: int = 180,
    n_phi: int = 90,
) -> pv.PolyData:
    """
    Crée la coque épaisse de la calotte en fusionnant :
    - surface extérieure
    - surface intérieure
    - anneau de fermeture à la base
    """
    Ri = _req_pos("rayon_interieur_m", rayon_interieur_m)
    Re = _req_pos("rayon_exterieur_m", rayon_exterieur_m)
    a = _req_pos("rayon_base_m", rayon_base_m)

    if Re <= Ri:
        raise ValueError("rayon_exterieur_m doit être > rayon_interieur_m")

    # plan de base z=0
    zi = -math.sqrt(Ri * Ri - a * a)
    ze = -math.sqrt(Re * Re - a * a)

    Xi, Yi, Zi = _calotte_surface_points(
        rayon_m=Ri,
        rayon_base_m=a,
        z_decalage_m=-zi,
        n_theta=n_theta,
        n_phi=n_phi,
    )
    Xe, Ye, Ze = _calotte_surface_points(
        rayon_m=Re,
        rayon_base_m=a,
        z_decalage_m=-ze,
        n_theta=n_theta,
        n_phi=n_phi,
    )

    surf_i = pv.StructuredGrid(Xi, Yi, Zi).extract_surface().triangulate()
    surf_e = pv.StructuredGrid(Xe, Ye, Ze).extract_surface().triangulate()

    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    pts = []
    faces = []

    base_idx = 0
    for th in theta:
        pts.append([a * math.cos(th), a * math.sin(th), 0.0])  # cercle intérieur base
    for th in theta:
        r_ext_base = a
        pts.append([r_ext_base * math.cos(th), r_ext_base * math.sin(th), 0.0])  # cercle extérieur base
    # Ici même rayon au plan de base, la différence d'épaisseur se lit sur la courbure
    # donc on ferme plutôt avec une nappe externe/interne sur les premiers anneaux.
    # Pour garantir une peau fermée visuelle, on relie le premier anneau extérieur/intérieur.
    pts = []
    faces = []
    n = n_theta

    # anneau de fermeture au bord
    outer_ring = np.column_stack([Xe[-1, :], Ye[-1, :], Ze[-1, :]])
    inner_ring = np.column_stack([Xi[-1, :], Yi[-1, :], Zi[-1, :]])
    pts = np.vstack([inner_ring, outer_ring])

    for i in range(n):
        i2 = (i + 1) % n
        a0 = i
        a1 = i2
        b1 = n + i2
        b0 = n + i
        faces.extend([4, a0, a1, b1, b0])

    ring = pv.PolyData(pts, np.array(faces))
    return surf_e.merge(surf_i).merge(ring).clean()


# =============================================================================
# Bride
# =============================================================================

def _mesh_bride_annulaire(
    r_int: float,
    r_ext: float,
    epaisseur: float,
    z0: float = 0.0,
    resolution: int = 180,
) -> pv.PolyData:
    ext = pv.Cylinder(
        center=(0.0, 0.0, z0 - 0.5 * epaisseur),
        direction=(0.0, 0.0, 1.0),
        radius=r_ext,
        height=epaisseur,
        resolution=resolution,
        capping=True,
    ).triangulate()

    inte = pv.Cylinder(
        center=(0.0, 0.0, z0 - 0.5 * epaisseur),
        direction=(0.0, 0.0, 1.0),
        radius=r_int,
        height=epaisseur + 1e-6,
        resolution=resolution,
        capping=True,
    ).triangulate()

    try:
        return ext.boolean_difference(inte).clean()
    except Exception:
        return ext.clean()


# =============================================================================
# Perçages
# =============================================================================

def _percer_trous_bride(
    mesh: pv.PolyData,
    diametre_cercle_percage_m: Optional[float],
    diametre_trou_m: Optional[float],
    angles_trous_deg: Optional[List[float]],
    epaisseur_zone_m: float,
) -> pv.PolyData:
    if diametre_cercle_percage_m is None or diametre_trou_m is None or not angles_trous_deg:
        return mesh

    rpc = 0.5 * _req_pos("diametre_cercle_percage_m", diametre_cercle_percage_m)
    dtr = _req_pos("diametre_trou_m", diametre_trou_m)
    hz = max(epaisseur_zone_m * 3.0, 1e-4)

    out = mesh
    for ang in angles_trous_deg:
        th = math.radians(float(ang))
        x = rpc * math.cos(th)
        y = rpc * math.sin(th)

        cyl = pv.Cylinder(
            center=(x, y, -0.5 * epaisseur_zone_m),
            direction=(0.0, 0.0, 1.0),
            radius=0.5 * dtr,
            height=hz,
            resolution=80,
            capping=True,
        ).triangulate()

        try:
            out = out.boolean_difference(cyl).clean()
        except Exception:
            continue

    return out


# =============================================================================
# Construction complète
# =============================================================================

def construire_mesh_couvercle_cylindre_detaille(
    rapport: Dict[str, Any],
    *,
    n_theta: int = 180,
    n_phi: int = 90,
) -> Tuple[pv.PolyData, Dict[str, Any], Dict[str, pv.PolyData]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    sous_meshes: Dict[str, pv.PolyData] = {}

    calotte = _mesh_calotte_epaisse(
        rayon_interieur_m=geom["rayon_courbure_interieur_m"],
        rayon_exterieur_m=geom["rayon_courbure_exterieur_m"],
        rayon_base_m=geom["rayon_base_calotte_m"],
        n_theta=n_theta,
        n_phi=n_phi,
    )
    sous_meshes["calotte"] = calotte

    mesh_total = calotte

    if (
        geom["bride_rayon_interne_m"] is not None
        and geom["bride_rayon_externe_m"] is not None
        and geom["bride_epaisseur_m"] is not None
    ):
        bride = _mesh_bride_annulaire(
            r_int=geom["bride_rayon_interne_m"],
            r_ext=geom["bride_rayon_externe_m"],
            epaisseur=geom["bride_epaisseur_m"],
            z0=0.0,
            resolution=max(160, n_theta),
        )
        sous_meshes["bride"] = bride
        mesh_total = mesh_total.merge(bride).clean()

        mesh_total = _percer_trous_bride(
            mesh_total,
            diametre_cercle_percage_m=geom["diametre_cercle_percage_m"],
            diametre_trou_m=geom["diametre_trou_m"],
            angles_trous_deg=geom["angles_trous_deg"],
            epaisseur_zone_m=geom["bride_epaisseur_m"],
        )

    return mesh_total.clean(), geom, sous_meshes


# =============================================================================
# Guides visuels
# =============================================================================

def construire_guides_visuels(geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    a = geom["rayon_base_calotte_m"]
    rmax = max(
        a,
        geom["bride_rayon_externe_m"] if geom["bride_rayon_externe_m"] is not None else a,
    )

    guides["axe"] = pv.Line(
        pointa=(0.0, 0.0, -0.2 * rmax),
        pointb=(0.0, 0.0, 1.4 * geom["hauteur_bombe_interieure_m"]),
        resolution=1,
    )

    guides["cercle_base"] = pv.Circle(
        radius=a,
        resolution=240,
    )

    if geom["diametre_cercle_percage_m"] is not None:
        guides["cercle_percage"] = pv.Circle(
            radius=0.5 * geom["diametre_cercle_percage_m"],
            resolution=240,
        )

    if geom["angles_trous_deg"] and geom["diametre_cercle_percage_m"] is not None:
        pts = []
        rpc = 0.5 * geom["diametre_cercle_percage_m"]
        for ang in geom["angles_trous_deg"]:
            th = math.radians(float(ang))
            pts.append((rpc * math.cos(th), rpc * math.sin(th), 0.0))
        if pts:
            guides["centres_trous"] = pv.PolyData(np.array(pts))

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_couvercle_cylindre_3d_detaille(
    source: CouvercleCylindre | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    couleur_calotte: str = "lightsteelblue",
    couleur_bride: str = "silver",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    if isinstance(source, CouvercleCylindre):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un CouvercleCylindre ou un rapport dict.")

    mesh_total, geom, sous_meshes = construire_mesh_couvercle_cylindre_detaille(rapport)

    plotter = pv.Plotter(window_size=(1320, 860))
    plotter.set_background("#1e1e1e")

    if "calotte" in sous_meshes:
        plotter.add_mesh(
            sous_meshes["calotte"],
            color=couleur_calotte,
            smooth_shading=True,
            show_edges=afficher_bords,
            specular=0.28,
            specular_power=24,
        )

    if "bride" in sous_meshes:
        plotter.add_mesh(
            sous_meshes["bride"],
            color=couleur_bride,
            smooth_shading=True,
            show_edges=afficher_bords,
            specular=0.20,
            specular_power=18,
        )

    # Mesh global percé
    if "bride" in sous_meshes and geom["angles_trous_deg"]:
        plotter.add_mesh(
            mesh_total,
            color="gainsboro",
            opacity=0.08,
            show_edges=False,
        )

    if afficher_guides:
        guides = construire_guides_visuels(geom)

        if "axe" in guides:
            plotter.add_mesh(guides["axe"], color="white", line_width=2)

        if "cercle_base" in guides:
            plotter.add_mesh(guides["cercle_base"], color="gold", line_width=2)

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

    plotter.add_text("Couvercle cylindre — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh_total, rapport


# =============================================================================
# Exemple minimal
# =============================================================================

if __name__ == "__main__":
    c = CouvercleCylindre(
        diametre_ouverture_m=0.080,
        pression_max_pa=3.0e6,
        materiau_cle=None,
        limite_elastique_pa=250e6,
        module_young_pa=210e9,
        densite_kg_m3=7800.0,
        epaisseur_m=None,
        hauteur_bombe_m=None,
        rayon_courbure_m=None,
        nb_vis=6,
        vis_d_nominal_mm=8.0,
        diametre_cercle_percage_m=0.120,
        diametre_trou_m=0.009,
    )

    afficher_couvercle_cylindre_3d_detaille(c)