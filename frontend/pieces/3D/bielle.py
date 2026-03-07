# frontend/pieces/3D/bielle.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — BIELLE
# =============================================================================
# But :
# - afficher une bielle détaillée à partir du bloc CAO de backend/pieces/bielle.py
# - ne modéliser que ce qui est effectivement défini/calculé
#
# Dépendances :
#   pip install pyvista vtk numpy
#
# Modélise :
# - petite tête annulaire
# - grande tête annulaire
# - fût rectangle ou rond équivalent
# - transitions géométriques simples entre têtes et fût
#
# Limites volontaires :
# - pas de chapeau de bielle séparé
# - pas de vis/boulons
# - pas de profil I/H si non calculé
# - pas de congés booléens complexes si non nécessaires
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pyvista as pv

from backend.pieces.bielle import CorpsBielle


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
        raise TypeError("rapport doit être un dictionnaire issu de CorpsBielle.calculer().")

    cao = _get_dict(rapport, "cao")
    fut = _get_dict(cao, "fut")
    pt = _get_dict(cao, "petite_tete")
    gt = _get_dict(cao, "grande_tete")

    entraxe = cao.get("entraxe_centres_m")
    x_pt = cao.get("centre_petite_tete_x_m")
    x_gt = cao.get("centre_grande_tete_x_m")

    if entraxe is None or x_pt is None or x_gt is None:
        raise ValueError(
            "Le bloc CAO de la bielle est incomplet : entraxe_centres_m et centres des têtes requis."
        )

    geom = {
        "entraxe_centres_m": _req_pos("cao.entraxe_centres_m", entraxe),
        "centre_petite_tete_x_m": _req_finite("cao.centre_petite_tete_x_m", x_pt),
        "centre_grande_tete_x_m": _req_finite("cao.centre_grande_tete_x_m", x_gt),
        "longueur_fut_droite_approx_m": (
            _req_pos("cao.longueur_fut_droite_approx_m", cao.get("longueur_fut_droite_approx_m"))
            if cao.get("longueur_fut_droite_approx_m") is not None else None
        ),

        "forme_fut": cao.get("forme_fut"),
        "fut_modele_section": fut.get("modele_section"),
        "fut_largeur_m": (
            _req_pos("cao.fut.largeur_m", fut.get("largeur_m"))
            if fut.get("largeur_m") is not None else None
        ),
        "fut_epaisseur_m": (
            _req_pos("cao.fut.epaisseur_m", fut.get("epaisseur_m"))
            if fut.get("epaisseur_m") is not None else None
        ),
        "fut_diametre_equivalent_m": (
            _req_pos("cao.fut.diametre_equivalent_m", fut.get("diametre_equivalent_m"))
            if fut.get("diametre_equivalent_m") is not None else None
        ),

        "pt_diametre_alesage_m": (
            _req_pos("cao.petite_tete.diametre_alésage_m", pt.get("diametre_alésage_m"))
            if pt.get("diametre_alésage_m") is not None else None
        ),
        "pt_diametre_exterieur_m": (
            _req_pos("cao.petite_tete.diametre_exterieur_m", pt.get("diametre_exterieur_m"))
            if pt.get("diametre_exterieur_m") is not None else None
        ),
        "pt_largeur_exterieure_m": (
            _req_pos("cao.petite_tete.largeur_exterieure_m", pt.get("largeur_exterieure_m"))
            if pt.get("largeur_exterieure_m") is not None else None
        ),

        "gt_diametre_alesage_m": (
            _req_pos("cao.grande_tete.diametre_alésage_m", gt.get("diametre_alésage_m"))
            if gt.get("diametre_alésage_m") is not None else None
        ),
        "gt_diametre_exterieur_m": (
            _req_pos("cao.grande_tete.diametre_exterieur_m", gt.get("diametre_exterieur_m"))
            if gt.get("diametre_exterieur_m") is not None else None
        ),
        "gt_largeur_exterieure_m": (
            _req_pos("cao.grande_tete.largeur_exterieure_m", gt.get("largeur_exterieure_m"))
            if gt.get("largeur_exterieure_m") is not None else None
        ),

        "chanfrein_fut_m": (
            _req_pos("cao.fut.chanfrein_m", fut.get("chanfrein_m"), strictly=False)
            if fut.get("chanfrein_m") is not None else 0.0
        ),
        "rayon_conge_tete_fut_m": (
            _req_pos("cao.fut.rayon_conge_tete_fut_m", fut.get("rayon_conge_tete_fut_m"), strictly=False)
            if fut.get("rayon_conge_tete_fut_m") is not None else None
        ),
    }

    # Validation minimale des têtes pour une vraie visu détaillée
    if geom["pt_diametre_exterieur_m"] is None or geom["pt_largeur_exterieure_m"] is None:
        raise ValueError("Petite tête insuffisamment définie pour une visualisation 3D détaillée.")
    if geom["gt_diametre_exterieur_m"] is None or geom["gt_largeur_exterieure_m"] is None:
        raise ValueError("Grande tête insuffisamment définie pour une visualisation 3D détaillée.")

    return geom


# =============================================================================
# Primitives
# =============================================================================

def _cylindre_z(
    centre_x: float,
    centre_y: float,
    longueur_z: float,
    rayon: float,
    resolution: int = 120,
) -> pv.PolyData:
    return pv.Cylinder(
        center=(centre_x, centre_y, 0.0),
        direction=(0.0, 0.0, 1.0),
        radius=rayon,
        height=longueur_z,
        resolution=resolution,
        capping=True,
    ).triangulate()


def _boite(
    centre_x: float,
    centre_y: float,
    centre_z: float,
    size_x: float,
    size_y: float,
    size_z: float,
) -> pv.PolyData:
    return pv.Box(bounds=(
        centre_x - 0.5 * size_x, centre_x + 0.5 * size_x,
        centre_y - 0.5 * size_y, centre_y + 0.5 * size_y,
        centre_z - 0.5 * size_z, centre_z + 0.5 * size_z,
    )).triangulate()


def _tronc_transition(
    x0: float,
    x1: float,
    r0: float,
    r1: float,
    epaisseur_z: float,
    n_x: int = 40,
    n_theta: int = 100,
) -> pv.PolyData:
    """
    Transition lissée par variation linéaire du rayon entre deux sections circulaires.
    Axe longitudinal = X, extrusion selon Z finie.
    """
    if x1 <= x0:
        raise ValueError("x1 doit être > x0 pour la transition.")

    xs = np.linspace(x0, x1, n_x)
    rs = np.linspace(r0, r1, n_x)
    z = np.linspace(-0.5 * epaisseur_z, 0.5 * epaisseur_z, 2)
    theta = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)

    X = np.repeat(xs[:, None], n_theta, axis=1)
    Y = rs[:, None] * np.cos(theta)[None, :]
    Zring = rs[:, None] * np.sin(theta)[None, :]

    # On aplatie en Z pour faire une sorte de peau "épaisse" ensuite on utilise Delaunay
    pts = np.column_stack([X.ravel(), Y.ravel(), Zring.ravel()])
    shell = pv.PolyData(pts).delaunay_3d(alpha=epaisseur_z * 2.0).extract_geometry().triangulate()
    return shell.clean()


# =============================================================================
# Construction détaillée
# =============================================================================

def _construire_tete_annulaire(
    centre_x: float,
    diam_ext: float,
    diam_int: Optional[float],
    largeur_z: float,
    resolution: int = 160,
) -> pv.PolyData:
    ext = _cylindre_z(
        centre_x=centre_x,
        centre_y=0.0,
        longueur_z=largeur_z,
        rayon=0.5 * diam_ext,
        resolution=resolution,
    )

    if diam_int is not None and diam_int > 0.0:
        inte = _cylindre_z(
            centre_x=centre_x,
            centre_y=0.0,
            longueur_z=largeur_z + 1e-6,
            rayon=0.5 * diam_int,
            resolution=resolution,
        )
        try:
            return ext.boolean_difference(inte).clean()
        except Exception:
            return ext.clean()

    return ext.clean()


def _construire_fut_rectangle(
    x0: float,
    x1: float,
    largeur_y: float,
    epaisseur_z: float,
) -> pv.PolyData:
    return _boite(
        centre_x=0.5 * (x0 + x1),
        centre_y=0.0,
        centre_z=0.0,
        size_x=(x1 - x0),
        size_y=largeur_y,
        size_z=epaisseur_z,
    ).clean()


def _construire_fut_rond(
    x0: float,
    x1: float,
    diametre: float,
    resolution: int = 120,
) -> pv.PolyData:
    return pv.Cylinder(
        center=(0.5 * (x0 + x1), 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=0.5 * diametre,
        height=(x1 - x0),
        resolution=resolution,
        capping=True,
    ).triangulate().clean()


def construire_mesh_bielle_detaillee(
    rapport: Dict[str, Any],
    resolution: int = 140,
) -> Tuple[pv.PolyData, Dict[str, Any], Dict[str, pv.PolyData]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    x_pt = geom["centre_petite_tete_x_m"]
    x_gt = geom["centre_grande_tete_x_m"]

    pt_rext = 0.5 * geom["pt_diametre_exterieur_m"]
    gt_rext = 0.5 * geom["gt_diametre_exterieur_m"]

    pt_rint = 0.5 * geom["pt_diametre_alesage_m"] if geom["pt_diametre_alesage_m"] is not None else None
    gt_rint = 0.5 * geom["gt_diametre_alesage_m"] if geom["gt_diametre_alesage_m"] is not None else None

    z_pt = geom["pt_largeur_exterieure_m"]
    z_gt = geom["gt_largeur_exterieure_m"]

    sous_meshes: Dict[str, pv.PolyData] = {}

    # Têtes
    petite_tete = _construire_tete_annulaire(
        centre_x=x_pt,
        diam_ext=geom["pt_diametre_exterieur_m"],
        diam_int=geom["pt_diametre_alesage_m"],
        largeur_z=z_pt,
        resolution=resolution,
    )
    grande_tete = _construire_tete_annulaire(
        centre_x=x_gt,
        diam_ext=geom["gt_diametre_exterieur_m"],
        diam_int=geom["gt_diametre_alesage_m"],
        largeur_z=z_gt,
        resolution=resolution,
    )

    sous_meshes["petite_tete"] = petite_tete
    sous_meshes["grande_tete"] = grande_tete

    # Fût
    # On prend des tangences géométriques simples sur les rayons extérieurs
    x_fut0 = x_pt + pt_rext
    x_fut1 = x_gt - gt_rext

    if x_fut1 <= x_fut0:
        raise ValueError("La géométrie de bielle est incohérente : le fût n'a pas de longueur positive.")

    fut = None
    if geom["fut_largeur_m"] is not None and geom["fut_epaisseur_m"] is not None:
        fut = _construire_fut_rectangle(
            x0=x_fut0,
            x1=x_fut1,
            largeur_y=geom["fut_largeur_m"],
            epaisseur_z=geom["fut_epaisseur_m"],
        )
        sous_meshes["fut"] = fut

        # Transitions simples boîte -> tête
        trans_g = _boite(
            centre_x=0.5 * (x_fut0 + (x_pt + 0.65 * pt_rext)),
            centre_y=0.0,
            centre_z=0.0,
            size_x=max((x_fut0 - (x_pt + 0.65 * pt_rext)), 1e-6),
            size_y=max(geom["fut_largeur_m"], 1e-6),
            size_z=max(min(z_pt, geom["fut_epaisseur_m"]), 1e-6),
        )
        trans_d = _boite(
            centre_x=0.5 * ((x_gt - 0.65 * gt_rext) + x_fut1),
            centre_y=0.0,
            centre_z=0.0,
            size_x=max(((x_gt - 0.65 * gt_rext) - x_fut1), 1e-6),
            size_y=max(geom["fut_largeur_m"], 1e-6),
            size_z=max(min(z_gt, geom["fut_epaisseur_m"]), 1e-6),
        )
        sous_meshes["transition_gauche"] = trans_g
        sous_meshes["transition_droite"] = trans_d

    elif geom["fut_diametre_equivalent_m"] is not None:
        fut = _construire_fut_rond(
            x0=x_fut0,
            x1=x_fut1,
            diametre=geom["fut_diametre_equivalent_m"],
            resolution=resolution,
        )
        sous_meshes["fut"] = fut

        rf = 0.5 * geom["fut_diametre_equivalent_m"]
        trans_g = _tronc_transition(
            x0=x_pt + 0.65 * pt_rext,
            x1=x_fut0,
            r0=pt_rext,
            r1=rf,
            epaisseur_z=min(z_pt, geom["fut_diametre_equivalent_m"]),
        )
        trans_d = _tronc_transition(
            x0=x_fut1,
            x1=x_gt - 0.65 * gt_rext,
            r0=rf,
            r1=gt_rext,
            epaisseur_z=min(z_gt, geom["fut_diametre_equivalent_m"]),
        )
        sous_meshes["transition_gauche"] = trans_g
        sous_meshes["transition_droite"] = trans_d

    else:
        raise ValueError(
            "Le fût de bielle n'est pas assez défini : "
            "ni rectangle exploitable, ni rond équivalent exploitable."
        )

    # Union visuelle
    mesh_total: Optional[pv.PolyData] = None
    for name in ("petite_tete", "transition_gauche", "fut", "transition_droite", "grande_tete"):
        if name in sous_meshes:
            mesh_total = sous_meshes[name] if mesh_total is None else mesh_total.merge(sous_meshes[name])

    if mesh_total is None:
        raise ValueError("Impossible de construire la géométrie de la bielle.")

    return mesh_total.clean(), geom, sous_meshes


# =============================================================================
# Guides
# =============================================================================

def construire_guides_visuels(geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    x_pt = geom["centre_petite_tete_x_m"]
    x_gt = geom["centre_grande_tete_x_m"]
    pt_rext = 0.5 * geom["pt_diametre_exterieur_m"]
    gt_rext = 0.5 * geom["gt_diametre_exterieur_m"]

    guides["axe_centres"] = pv.Line(
        pointa=(x_pt - pt_rext - 0.02, 0.0, 0.0),
        pointb=(x_gt + gt_rext + 0.02, 0.0, 0.0),
        resolution=1,
    )

    guides["centre_petite_tete"] = pv.PolyData([(x_pt, 0.0, 0.0)])
    guides["centre_grande_tete"] = pv.PolyData([(x_gt, 0.0, 0.0)])

    guides["entraxe"] = pv.Line(
        pointa=(x_pt, 0.0, 0.0),
        pointb=(x_gt, 0.0, 0.0),
        resolution=1,
    )

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_bielle_3d_detaillee(
    source: CorpsBielle | Dict[str, Any],
    *,
    resolution: int = 140,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    couleur_tetes: str = "lightsteelblue",
    couleur_fut: str = "silver",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    if isinstance(source, CorpsBielle):
        rapport = source.calculer(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un CorpsBielle ou un rapport dict.")

    mesh_total, geom, sous_meshes = construire_mesh_bielle_detaillee(
        rapport,
        resolution=resolution,
    )

    plotter = pv.Plotter(window_size=(1320, 840))
    plotter.set_background("#1e1e1e")

    for name in ("petite_tete", "grande_tete"):
        if name in sous_meshes:
            plotter.add_mesh(
                sous_meshes[name],
                color=couleur_tetes,
                smooth_shading=True,
                show_edges=afficher_bords,
                specular=0.30,
                specular_power=25,
            )

    for name in ("transition_gauche", "fut", "transition_droite"):
        if name in sous_meshes:
            plotter.add_mesh(
                sous_meshes[name],
                color=couleur_fut,
                smooth_shading=True,
                show_edges=afficher_bords,
                specular=0.18,
                specular_power=18,
            )

    if afficher_guides:
        guides = construire_guides_visuels(geom)

        if "axe_centres" in guides:
            plotter.add_mesh(guides["axe_centres"], color="white", line_width=2)

        if "entraxe" in guides:
            plotter.add_mesh(guides["entraxe"], color="gold", line_width=3)

        for key in ("centre_petite_tete", "centre_grande_tete"):
            if key in guides:
                plotter.add_mesh(
                    guides[key],
                    color="gold",
                    point_size=12,
                    render_points_as_spheres=True,
                )

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Bielle — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh_total, rapport


# =============================================================================
# Exemple minimal
# =============================================================================

if __name__ == "__main__":
    try:
        from backend.pieces.arbre_piston import ArbrePiston  # type: ignore
        arbre = ArbrePiston(
            diametre_portee_coussinet_m=0.020,
        )
    except Exception:
        arbre = None

    b = CorpsBielle(
        arbre_piston=arbre,
        longueur_bielle_m=0.140,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        densite_kg_m3=7800.0,
        facteur_securite=2.0,
        K_flambage=1.0,
        force_axiale_max_N=15000.0,
        forme_fut="rectangle",
        ratio_largeur_sur_epaisseur=2.0,
        longueur_portee_petite_tete_m=0.018,
        diametre_maneton_m=0.030,
        longueur_portee_grande_tete_m=0.020,
    )

    afficher_bielle_3d_detaillee(b)