# frontend/pieces/3D/vilbrequin.py
# =============================================================================
# VISUALISATION 3D — VILBREQUIN
# =============================================================================
# But :
# - visualiser un vilbrequin à partir du rapport backend/pieces/vilbrequin.py
# - ne rien inventer :
#   * journaux et manetons seulement si leurs dimensions existent
#   * webs / contrepoids non modélisés sans géométrie explicite
#   * placement axial par convention explicite de visualisation
#
# Dépendances :
#   pip install pyvista vtk numpy
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
import math

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.vilbrequin import Vilbrequin


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


def _safe_float(d: Dict[str, Any], key: str) -> Optional[float]:
    v = d.get(key)
    if _is_finite(v):
        return float(v)
    return None


# =============================================================================
# Extraction depuis rapport backend
# =============================================================================

def extraire_cao_vilbrequin(rapport: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dict issu de Vilbrequin.analyser().")

    geo = _safe_dict(rapport, "geometrie")
    cine = _safe_dict(rapport, "cinematique")
    masses = _safe_dict(rapport, "masses")
    inerties = _safe_dict(rapport, "inerties")
    volumes = _safe_dict(rapport, "volumes")

    d_j = _safe_float(geo, "diametre_journal_principal_m")
    B_j = _safe_float(geo, "largeur_portee_journal_m")
    d_m = _safe_float(geo, "diametre_maneton_m")
    B_m = _safe_float(geo, "largeur_portee_maneton_m")
    n_j = geo.get("nb_journaux_principaux")
    n_m = geo.get("nb_manetons")
    r = _safe_float(cine, "rayon_manivelle_m")
    course = _safe_float(cine, "course_m")
    rpm = _safe_float(cine, "rpm")

    out = {
        "diametre_journal_principal_m": d_j,
        "largeur_portee_journal_m": B_j,
        "diametre_maneton_m": d_m,
        "largeur_portee_maneton_m": B_m,
        "nb_journaux_principaux": int(n_j) if isinstance(n_j, int) and n_j > 0 else None,
        "nb_manetons": int(n_m) if isinstance(n_m, int) and n_m > 0 else None,
        "rayon_manivelle_m": r,
        "course_m": course,
        "rpm": rpm,
        "masse_totale_modele_kg": _safe_float(masses, "masse_totale_modele_kg"),
        "inertie_polaire_minimale_modele_kg_m2": _safe_float(inerties, "inertie_polaire_minimale_modele_kg_m2"),
        "volume_total_modele_m3": _safe_float(volumes, "volume_total_modele_m3"),
    }

    return out


# =============================================================================
# Primitives
# =============================================================================

def _cylindre_z(
    *,
    centre_x: float,
    centre_y: float,
    z_min: float,
    z_max: float,
    diametre_m: float,
    resolution: int = 140,
) -> pv.PolyData:
    h = _req_pos("hauteur", z_max - z_min)
    d = _req_pos("diametre_m", diametre_m)
    zc = 0.5 * (z_min + z_max)

    return pv.Cylinder(
        center=(centre_x, centre_y, zc),
        direction=(0.0, 0.0, 1.0),
        radius=0.5 * d,
        height=h,
        resolution=resolution,
        capping=True,
    ).triangulate().clean()


def _boite(
    *,
    centre: Tuple[float, float, float],
    size: Tuple[float, float, float],
) -> pv.PolyData:
    return pv.Box(bounds=(
        centre[0] - 0.5 * size[0], centre[0] + 0.5 * size[0],
        centre[1] - 0.5 * size[1], centre[1] + 0.5 * size[1],
        centre[2] - 0.5 * size[2], centre[2] + 0.5 * size[2],
    )).triangulate().clean()


# =============================================================================
# Convention de placement axial
# =============================================================================

def _positions_axiales(
    *,
    nb: int,
    largeur_m: float,
    entraxe_m: float,
) -> List[Tuple[float, float]]:
    """
    Retourne une liste de segments [z_min, z_max] centrés sur 0.

    Convention explicite de visualisation :
    - les centres sont espacés de entraxe_m
    - chaque élément a une largeur constante largeur_m
    """
    n = int(nb)
    if n <= 0:
        return []

    L = _req_pos("largeur_m", largeur_m)
    e = _req_pos("entraxe_m", entraxe_m)

    z0 = -0.5 * (n - 1) * e
    out: List[Tuple[float, float]] = []
    for i in range(n):
        zc = z0 + i * e
        out.append((zc - 0.5 * L, zc + 0.5 * L))
    return out


# =============================================================================
# Construction 3D
# =============================================================================

def construire_vilbrequin_3d(
    rapport: Dict[str, Any],
    *,
    facteur_entraxe: float = 1.8,
    afficher_webs_conventionnels: bool = True,
    epaisseur_web_conventionnelle_sur_largeur: float = 0.35,
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    g = extraire_cao_vilbrequin(rapport)

    d_j = g["diametre_journal_principal_m"]
    B_j = g["largeur_portee_journal_m"]
    d_m = g["diametre_maneton_m"]
    B_m = g["largeur_portee_maneton_m"]
    n_j = g["nb_journaux_principaux"]
    n_m = g["nb_manetons"]
    r = g["rayon_manivelle_m"]

    meshes: Dict[str, pv.PolyData] = {}

    # validation minimale
    if d_j is None and d_m is None:
        raise ValueError("Aucune géométrie exploitable : ni journal ni maneton.")
    if n_j is None and d_j is not None:
        raise ValueError("nb_journaux_principaux requis pour placer les journaux.")
    if n_m is None and d_m is not None:
        raise ValueError("nb_manetons requis pour placer les manetons.")

    # largeur de référence pour le pas axial
    largeurs = [x for x in (B_j, B_m) if x is not None]
    if not largeurs:
        raise ValueError("Aucune largeur de portée exploitable.")
    largeur_ref = max(largeurs)
    entraxe = facteur_entraxe * largeur_ref

    # -------------------------------------------------------------------------
    # Journaux
    # -------------------------------------------------------------------------
    pos_j = []
    if d_j is not None and B_j is not None and n_j is not None:
        pos_j = _positions_axiales(
            nb=n_j,
            largeur_m=B_j,
            entraxe_m=entraxe,
        )
        for i, (zmin, zmax) in enumerate(pos_j, start=1):
            meshes[f"journal_{i}"] = _cylindre_z(
                centre_x=0.0,
                centre_y=0.0,
                z_min=zmin,
                z_max=zmax,
                diametre_m=d_j,
            )

    # -------------------------------------------------------------------------
    # Manetons
    # -------------------------------------------------------------------------
    pos_m = []
    if d_m is not None and B_m is not None and n_m is not None:
        pos_m = _positions_axiales(
            nb=n_m,
            largeur_m=B_m,
            entraxe_m=entraxe,
        )

        # convention explicite :
        # alternance haut/bas autour de l’axe de rotation
        r_use = 0.0 if r is None else r
        for i, (zmin, zmax) in enumerate(pos_m, start=1):
            signe = 1.0 if (i % 2 == 1) else -1.0
            y_off = signe * r_use
            meshes[f"maneton_{i}"] = _cylindre_z(
                centre_x=0.0,
                centre_y=y_off,
                z_min=zmin,
                z_max=zmax,
                diametre_m=d_m,
            )

    # -------------------------------------------------------------------------
    # Webs conventionnels (facultatifs)
    # -------------------------------------------------------------------------
    # Ce ne sont PAS des webs calculés par le backend.
    # Ils sont affichés uniquement comme liaisons visuelles explicites.
    if afficher_webs_conventionnels and pos_j and pos_m and d_j is not None and d_m is not None:
        n_pair = min(len(pos_j), len(pos_m))
        e_web = epaisseur_web_conventionnelle_sur_largeur * largeur_ref
        e_web = max(e_web, 1e-4)

        for i in range(n_pair):
            zj = 0.5 * (pos_j[i][0] + pos_j[i][1])
            zm = 0.5 * (pos_m[i][0] + pos_m[i][1])

            # si journaux et manetons ne sont pas exactement au même z,
            # on crée un web centré entre les deux
            zc = 0.5 * (zj + zm)
            dz = abs(zm - zj)
            long_z = max(e_web, dz + 0.5 * min(B_j or largeur_ref, B_m or largeur_ref))
            y_off = (r if r is not None else 0.0) * (1.0 if ((i + 1) % 2 == 1) else -1.0)

            hauteur_y = abs(y_off) + 0.25 * max(d_j, d_m)
            largeur_x = 0.20 * max(d_j, d_m)

            meshes[f"web_conventionnel_{i+1}"] = _boite(
                centre=(0.0, 0.5 * y_off, zc),
                size=(largeur_x, max(hauteur_y, 1e-4), long_z),
            )

    return meshes, g


# =============================================================================
# Guides
# =============================================================================

def construire_guides_vilbrequin(g: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    d_j = g["diametre_journal_principal_m"]
    d_m = g["diametre_maneton_m"]
    B_j = g["largeur_portee_journal_m"]
    B_m = g["largeur_portee_maneton_m"]
    n_j = g["nb_journaux_principaux"]
    n_m = g["nb_manetons"]

    largeurs = [x for x in (B_j, B_m) if x is not None]
    if not largeurs:
        return guides

    largeur_ref = max(largeurs)
    entraxe = 1.8 * largeur_ref
    n_all = max(n_j or 0, n_m or 0, 1)
    demi_long = 0.5 * (n_all - 1) * entraxe + largeur_ref

    guides["axe_vilbrequin"] = pv.Line(
        pointa=(0.0, 0.0, -demi_long),
        pointb=(0.0, 0.0, demi_long),
        resolution=1,
    )

    if d_j is not None:
        guides["axe_journal_central"] = pv.Line(
            pointa=(0.0, 0.0, -0.5 * (B_j or largeur_ref)),
            pointb=(0.0, 0.0, 0.5 * (B_j or largeur_ref)),
            resolution=1,
        )

    if d_m is not None and g["rayon_manivelle_m"] is not None:
        y_off = g["rayon_manivelle_m"]
        guides["axe_maneton_reference"] = pv.Line(
            pointa=(0.0, y_off, -0.5 * (B_m or largeur_ref)),
            pointb=(0.0, y_off, 0.5 * (B_m or largeur_ref)),
            resolution=1,
        )

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_vilbrequin_3d(
    source: Vilbrequin | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_guides: bool = True,
    afficher_bords: bool = False,
    afficher_webs_conventionnels: bool = True,
    couleur_journaux: str = "lightgray",
    couleur_manetons: str = "silver",
    couleur_webs: str = "slategray",
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    if isinstance(source, Vilbrequin):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un Vilbrequin ou un dict rapport.")

    meshes, geom = construire_vilbrequin_3d(
        rapport,
        afficher_webs_conventionnels=afficher_webs_conventionnels,
    )

    plotter = pv.Plotter(window_size=(1450, 920))
    plotter.set_background("#1e1e1e")

    for nom, mesh in meshes.items():
        if nom.startswith("journal_"):
            plotter.add_mesh(
                mesh,
                color=couleur_journaux,
                smooth_shading=True,
                show_edges=afficher_bords,
                specular=0.25,
                specular_power=20,
            )
        elif nom.startswith("maneton_"):
            plotter.add_mesh(
                mesh,
                color=couleur_manetons,
                smooth_shading=True,
                show_edges=afficher_bords,
                specular=0.25,
                specular_power=20,
            )
        elif nom.startswith("web_conventionnel_"):
            plotter.add_mesh(
                mesh,
                color=couleur_webs,
                smooth_shading=True,
                opacity=0.65,
                show_edges=afficher_bords,
            )

    if afficher_guides:
        guides = construire_guides_vilbrequin(geom)
        for nom, mesh in guides.items():
            if "vilbrequin" in nom:
                plotter.add_mesh(mesh, color="white", line_width=2)
            elif "journal" in nom:
                plotter.add_mesh(mesh, color="cyan", line_width=3)
            else:
                plotter.add_mesh(mesh, color="yellow", line_width=3)

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    titre = "Vilbrequin — visualisation 3D"
    plotter.add_text(titre, font_size=12)

    sous_titre = []
    if geom.get("course_m") is not None:
        sous_titre.append(f"course={geom['course_m']:.6g} m")
    if geom.get("rayon_manivelle_m") is not None:
        sous_titre.append(f"r={geom['rayon_manivelle_m']:.6g} m")
    if geom.get("rpm") is not None:
        sous_titre.append(f"rpm={geom['rpm']:.6g}")
    if sous_titre:
        plotter.add_text(" | ".join(sous_titre), position="lower_left", font_size=10)

    plotter.view_isometric()
    plotter.show()

    return meshes, rapport


# =============================================================================
# Exemple
# =============================================================================

if __name__ == "__main__":
    vb = Vilbrequin(
        nb_manetons=2,
        nb_journaux_principaux=3,
        course_m=0.060,
        rpm=3000.0,
        couple_max_Nm=45.0,
        densite_kg_m3=7800.0,
        limite_elastique_pa=700e6,
        module_young_pa=210e9,
        poisson=0.30,
    )

    # Pour une vraie visualisation, il faut idéalement un arbre_vilbrequin
    # qui fournisse :
    # - diametre_journal_principal_m
    # - largeur_portee_journal_m
    # - diametre_maneton_m
    # - largeur_portee_maneton_m
    #
    # Ici, le backend Vilbrequin seul ne les invente pas.
    # Donc cet exemple minimal servira surtout à vérifier les inconnues.

    try:
        afficher_vilbrequin_3d(vb)
    except Exception as e:
        print("Visualisation impossible sans géométrie de portées suffisante :", e)