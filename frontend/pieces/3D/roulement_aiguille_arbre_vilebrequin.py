# frontend/pieces/3D/roulement_aiguille_arbre_vilebrequin.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — ROULEMENT À AIGUILLES
# arbre / vilebrequin (côté maneton / grande tête)
# =============================================================================
# But :
# - afficher un roulement à aiguilles 3D à partir du rapport backend
# - utiliser strictement les dimensions calculées / estimées
# - montrer :
#   * bague intérieure
#   * bague extérieure
#   * aiguilles
#   * cage simplifiée
#
# Dépendances :
#   pip install pyvista vtk numpy
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Tuple, List, Optional
import math

import numpy as np
import pyvista as pv

from backend.pieces.roulement_aiguille_arbre_vilebrequin import (
    RoulementAiguilleArbreVilebrequin,
)


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
    if (not strictly) and v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _safe_dict(d: Any, key: str) -> Dict[str, Any]:
    if isinstance(d, dict):
        v = d.get(key, {})
        return v if isinstance(v, dict) else {}
    return {}


# =============================================================================
# Extraction géométrique depuis rapport
# =============================================================================

def extraire_cao_roulement_aiguille(rapport: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dict issu de RoulementAiguilleArbreVilebrequin.calculer().")

    cao = _safe_dict(rapport, "cao")
    geom = _safe_dict(rapport, "geometrie_estimee")
    dims_req = _safe_dict(rapport, "dimensions_requises")

    d_int = cao.get("d_interieur_nominal_m")
    D_ext = cao.get("D_exterieur_nominal_m")
    B = cao.get("B_largeur_nominale_m")

    d_aig = cao.get("diametre_aiguille_m")
    nb_aig = cao.get("nb_aiguilles")
    L_aig = cao.get("longueur_utile_aiguille_m")
    d_pitch = cao.get("diametre_pitch_m")

    tbi = cao.get("epaisseur_bague_interieure_radiale_m")
    tbe = cao.get("epaisseur_bague_exterieure_radiale_m")
    jeu = cao.get("jeu_radial_fonctionnel_m")

    # repli sur geometrie_estimee si le bloc cao n'est pas complet
    if d_int is None:
        d_int = dims_req.get("d_interieur_requis_m")
    if B is None:
        B = dims_req.get("B_requis_m")
    if D_ext is None:
        D_ext = geom.get("D_exterieur_estime_m")
    if d_aig is None:
        d_aig = geom.get("diametre_aiguille_m")
    if nb_aig is None:
        nb_aig = geom.get("nb_aiguilles")
    if L_aig is None:
        L_aig = geom.get("longueur_utile_aiguille_m")
    if d_pitch is None:
        d_pitch = geom.get("diametre_pitch_m")
    if tbi is None:
        tbi = geom.get("epaisseur_bague_interieure_radiale_m")
    if tbe is None:
        tbe = geom.get("epaisseur_bague_exterieure_radiale_m")
    if jeu is None:
        jeu = geom.get("jeu_radial_fonctionnel_m")

    # type
    type_roulement = cao.get("type_roulement", "inconnu")

    out: Dict[str, Any] = {
        "type_roulement": type_roulement,
        "d_interieur_nominal_m": _req_pos("d_interieur_nominal_m", d_int),
        "B_largeur_nominale_m": _req_pos("B_largeur_nominale_m", B),
        "D_exterieur_nominal_m": _req_pos("D_exterieur_nominal_m", D_ext) if D_ext is not None else None,
        "diametre_aiguille_m": _req_pos("diametre_aiguille_m", d_aig) if d_aig is not None else None,
        "nb_aiguilles": int(nb_aig) if isinstance(nb_aig, int) and nb_aig > 0 else None,
        "longueur_utile_aiguille_m": _req_pos("longueur_utile_aiguille_m", L_aig) if L_aig is not None else None,
        "diametre_pitch_m": _req_pos("diametre_pitch_m", d_pitch) if d_pitch is not None else None,
        "epaisseur_bague_interieure_radiale_m": _req_pos("epaisseur_bague_interieure_radiale_m", tbi, strictly=False) if tbi is not None else 0.0,
        "epaisseur_bague_exterieure_radiale_m": _req_pos("epaisseur_bague_exterieure_radiale_m", tbe, strictly=False) if tbe is not None else 0.0,
        "jeu_radial_fonctionnel_m": _req_pos("jeu_radial_fonctionnel_m", jeu, strictly=False) if jeu is not None else 0.0,
        "chanfrein_recommande_m": _req_pos("chanfrein_recommande_m", cao.get("chanfrein_recommande_m"), strictly=False)
            if cao.get("chanfrein_recommande_m") is not None else 0.0,
        "rayon_recommande_m": _req_pos("rayon_recommande_m", cao.get("rayon_recommande_m"), strictly=False)
            if cao.get("rayon_recommande_m") is not None else 0.0,
    }

    return out


# =============================================================================
# Primitives géométriques
# =============================================================================

def _tube_z(
    *,
    z_min: float,
    z_max: float,
    diametre_interieur_m: float,
    diametre_exterieur_m: float,
    resolution: int = 220,
) -> pv.PolyData:
    h = _req_pos("hauteur", z_max - z_min)
    di = _req_pos("diametre_interieur_m", diametre_interieur_m, strictly=False)
    de = _req_pos("diametre_exterieur_m", diametre_exterieur_m)
    if di >= de:
        raise ValueError("diametre_interieur_m doit être < diametre_exterieur_m.")

    zc = 0.5 * (z_min + z_max)

    ext = pv.Cylinder(
        center=(0.0, 0.0, zc),
        direction=(0.0, 0.0, 1.0),
        radius=0.5 * de,
        height=h,
        resolution=resolution,
        capping=True,
    ).triangulate()

    inte = pv.Cylinder(
        center=(0.0, 0.0, zc),
        direction=(0.0, 0.0, 1.0),
        radius=0.5 * di,
        height=h + 1e-6,
        resolution=resolution,
        capping=True,
    ).triangulate()

    try:
        return ext.boolean_difference(inte).clean()
    except Exception:
        return ext.clean()


def _cylindre_z(
    *,
    z_min: float,
    z_max: float,
    diametre_m: float,
    resolution: int = 120,
) -> pv.PolyData:
    h = _req_pos("hauteur", z_max - z_min)
    d = _req_pos("diametre_m", diametre_m)
    zc = 0.5 * (z_min + z_max)

    return pv.Cylinder(
        center=(0.0, 0.0, zc),
        direction=(0.0, 0.0, 1.0),
        radius=0.5 * d,
        height=h,
        resolution=resolution,
        capping=True,
    ).triangulate().clean()


def _aiguille_z(
    *,
    z_min: float,
    z_max: float,
    diametre_m: float,
    x_m: float,
    y_m: float,
    resolution: int = 72,
) -> pv.PolyData:
    h = _req_pos("hauteur", z_max - z_min)
    d = _req_pos("diametre_m", diametre_m)
    zc = 0.5 * (z_min + z_max)

    return pv.Cylinder(
        center=(x_m, y_m, zc),
        direction=(0.0, 0.0, 1.0),
        radius=0.5 * d,
        height=h,
        resolution=resolution,
        capping=True,
    ).triangulate().clean()


def _couronne_cage(
    *,
    z_min: float,
    z_max: float,
    diametre_interieur_m: float,
    diametre_exterieur_m: float,
) -> pv.PolyData:
    return _tube_z(
        z_min=z_min,
        z_max=z_max,
        diametre_interieur_m=diametre_interieur_m,
        diametre_exterieur_m=diametre_exterieur_m,
        resolution=180,
    )


def _points_repartition_circulaire(nb: int, rayon_m: float) -> List[Tuple[float, float, float]]:
    z = []
    for i in range(nb):
        th = 2.0 * math.pi * i / nb
        x = rayon_m * math.cos(th)
        y = rayon_m * math.sin(th)
        z.append((x, y, th))
    return z


# =============================================================================
# Construction 3D détaillée
# =============================================================================

def construire_roulement_aiguille_3d_detaille(
    rapport: Dict[str, Any],
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    g = extraire_cao_roulement_aiguille(rapport)

    d_int = g["d_interieur_nominal_m"]
    B = g["B_largeur_nominale_m"]
    D_ext = g["D_exterieur_nominal_m"]
    d_aig = g["diametre_aiguille_m"]
    nb_aig = g["nb_aiguilles"]
    L_aig = g["longueur_utile_aiguille_m"]
    d_pitch = g["diametre_pitch_m"]
    tbi = g["epaisseur_bague_interieure_radiale_m"]
    tbe = g["epaisseur_bague_exterieure_radiale_m"]

    z_min = -0.5 * B
    z_max = 0.5 * B

    meshes: Dict[str, pv.PolyData] = {}

    # -------------------------------------------------------------------------
    # Bague intérieure
    # -------------------------------------------------------------------------
    # Si tbi > 0, on modélise une bague.
    # Sinon on considère "aiguilles seules sur maneton" ou "sans bague intérieure".
    if tbi > 0.0:
        d_ext_bi = d_int + 2.0 * tbi
        meshes["bague_interieure"] = _tube_z(
            z_min=z_min,
            z_max=z_max,
            diametre_interieur_m=d_int,
            diametre_exterieur_m=d_ext_bi,
        )
    else:
        # représentation du maneton nominal utile, en guide visuel
        meshes["portee_interieure_reference"] = _cylindre_z(
            z_min=z_min,
            z_max=z_max,
            diametre_m=d_int,
        )

    # -------------------------------------------------------------------------
    # Bague extérieure
    # -------------------------------------------------------------------------
    # Si D_ext est défini et qu'on a une épaisseur extérieure ou simplement un D estimé.
    if D_ext is not None and D_ext > d_int:
        if d_pitch is not None and d_aig is not None:
            # alésage interne de la bague extérieure ≈ cercle de roulement extérieur
            d_int_be = d_pitch + d_aig
            if d_int_be < D_ext:
                meshes["bague_exterieure"] = _tube_z(
                    z_min=z_min,
                    z_max=z_max,
                    diametre_interieur_m=d_int_be,
                    diametre_exterieur_m=D_ext,
                )
            else:
                # repli visuel minimal si la reconstruction géométrique n'est pas cohérente
                meshes["bague_exterieure"] = _tube_z(
                    z_min=z_min,
                    z_max=z_max,
                    diametre_interieur_m=0.95 * D_ext,
                    diametre_exterieur_m=D_ext,
                )

    # -------------------------------------------------------------------------
    # Aiguilles
    # -------------------------------------------------------------------------
    if d_aig is not None and nb_aig is not None and L_aig is not None and d_pitch is not None:
        r_pitch = 0.5 * d_pitch
        z_min_a = -0.5 * L_aig
        z_max_a = 0.5 * L_aig

        pts = _points_repartition_circulaire(nb_aig, r_pitch)
        for i, (x, y, _) in enumerate(pts, start=1):
            meshes[f"aiguille_{i}"] = _aiguille_z(
                z_min=z_min_a,
                z_max=z_max_a,
                diametre_m=d_aig,
                x_m=x,
                y_m=y,
            )

        # ---------------------------------------------------------------------
        # Cage simplifiée
        # ---------------------------------------------------------------------
        # On ne reconstitue pas une cage constructeur.
        # On propose deux couronnes minces de maintien, explicites et simples.
        cage_ep_ax = min(0.10 * L_aig, 0.10 * B, 0.0015)
        if cage_ep_ax > 0.0:
            d_int_cage = max(d_int + 2.0 * tbi + 0.15 * d_aig, 0.01 * d_aig)
            d_ext_cage = d_pitch + d_aig * 0.85

            if d_ext_cage > d_int_cage:
                meshes["cage_avant"] = _couronne_cage(
                    z_min=z_min_a,
                    z_max=z_min_a + cage_ep_ax,
                    diametre_interieur_m=d_int_cage,
                    diametre_exterieur_m=d_ext_cage,
                )
                meshes["cage_arriere"] = _couronne_cage(
                    z_min=z_max_a - cage_ep_ax,
                    z_max=z_max_a,
                    diametre_interieur_m=d_int_cage,
                    diametre_exterieur_m=d_ext_cage,
                )

    return meshes, g


# =============================================================================
# Guides
# =============================================================================

def construire_guides_roulement(
    meshes: Dict[str, pv.PolyData],
    g: Dict[str, Any],
) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    B = g["B_largeur_nominale_m"]
    d_int = g["d_interieur_nominal_m"]
    D_ext = g["D_exterieur_nominal_m"]
    d_pitch = g["diametre_pitch_m"]

    z_min = -0.5 * B
    z_max = 0.5 * B

    guides["axe"] = pv.Line(
        pointa=(0.0, 0.0, z_min - 0.15 * B),
        pointb=(0.0, 0.0, z_max + 0.15 * B),
        resolution=1,
    )

    # cercles repères
    def cercle(diam: float, z: float = 0.0, n: int = 240) -> pv.PolyData:
        r = 0.5 * diam
        pts = []
        for i in range(n + 1):
            th = 2.0 * math.pi * i / n
            pts.append([r * math.cos(th), r * math.sin(th), z])
        return pv.Spline(np.array(pts), n_points=len(pts) * 2)

    guides["cercle_d_interieur"] = cercle(d_int, 0.0)
    if D_ext is not None:
        guides["cercle_D_exterieur"] = cercle(D_ext, 0.0)
    if d_pitch is not None:
        guides["cercle_pitch"] = cercle(d_pitch, 0.0)

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_roulement_aiguille_3d_detaille(
    source: RoulementAiguilleArbreVilebrequin | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    couleur_bague_interieure: str = "silver",
    couleur_bague_exterieure: str = "gainsboro",
    couleur_aiguilles: str = "steelblue",
    couleur_cage: str = "orange",
    couleur_reference_interieure: str = "dimgray",
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    if isinstance(source, RoulementAiguilleArbreVilebrequin):
        rapport = source.calculer(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un RoulementAiguilleArbreVilebrequin ou un dict rapport.")

    meshes, geom = construire_roulement_aiguille_3d_detaille(rapport)

    plotter = pv.Plotter(window_size=(1400, 900))
    plotter.set_background("#1e1e1e")

    if "bague_interieure" in meshes:
        plotter.add_mesh(
            meshes["bague_interieure"],
            color=couleur_bague_interieure,
            smooth_shading=True,
            opacity=0.92,
            show_edges=afficher_bords,
            specular=0.35,
            specular_power=24,
        )

    if "portee_interieure_reference" in meshes:
        plotter.add_mesh(
            meshes["portee_interieure_reference"],
            color=couleur_reference_interieure,
            smooth_shading=True,
            opacity=0.18,
            show_edges=False,
        )

    if "bague_exterieure" in meshes:
        plotter.add_mesh(
            meshes["bague_exterieure"],
            color=couleur_bague_exterieure,
            smooth_shading=True,
            opacity=0.65,
            show_edges=afficher_bords,
            specular=0.25,
            specular_power=18,
        )

    for name, mesh in meshes.items():
        if name.startswith("aiguille_"):
            plotter.add_mesh(
                mesh,
                color=couleur_aiguilles,
                smooth_shading=True,
                opacity=1.0,
                show_edges=afficher_bords,
                specular=0.40,
                specular_power=28,
            )

    for name in ("cage_avant", "cage_arriere"):
        if name in meshes:
            plotter.add_mesh(
                meshes[name],
                color=couleur_cage,
                smooth_shading=True,
                opacity=0.45,
                show_edges=afficher_bords,
            )

    if afficher_guides:
        guides = construire_guides_roulement(meshes, geom)

        if "axe" in guides:
            plotter.add_mesh(guides["axe"], color="white", line_width=2)

        if "cercle_d_interieur" in guides:
            plotter.add_mesh(guides["cercle_d_interieur"], color="cyan", line_width=2)

        if "cercle_D_exterieur" in guides:
            plotter.add_mesh(guides["cercle_D_exterieur"], color="yellow", line_width=2)

        if "cercle_pitch" in guides:
            plotter.add_mesh(guides["cercle_pitch"], color="tomato", line_width=2)

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Roulement à aiguilles — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return meshes, rapport


# =============================================================================
# Exemple
# =============================================================================

if __name__ == "__main__":
    class CorpsBielleMock:
        def calculer(self, strict: bool = False):
            return {
                "efforts": {"force_axiale_max_N": 15000.0},
                "geometrie": {"grande_tete": {"diametre_maneton_m": 0.030}},
                "contacts_tetes": {"grande_tete": {"longueur_portee_m": 0.020}},
            }

    r = RoulementAiguilleArbreVilebrequin(
        corps_bielle=CorpsBielleMock(),
        rpm_vilebrequin=3000.0,
        vie_cible_heures=4000.0,
        facteur_application_Ka=1.2,
        charge_statique_P0_N=18000.0,
        facteur_securite_stat=1.5,
        type_roulement="avec_bague_exterieure",
        diametre_aiguille_m=0.0025,
        nb_aiguilles=24,
        epaisseur_bague_interieure_radiale_m=0.0000,
        epaisseur_bague_exterieure_radiale_m=0.0015,
        jeu_radial_fonctionnel_m=20e-6,
        pression_admissible_pa=120e6,
    )

    afficher_roulement_aiguille_3d_detaille(r)