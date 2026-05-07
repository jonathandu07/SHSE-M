# frontend/pieces/3D/coussinet_arbre_piston.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — COUSSINET ARBRE-PISTON
# =============================================================================
# But :
# - afficher un coussinet 3D détaillé à partir de backend/pieces/coussinet_arbre_piston.py
# - n'utiliser que les données du bloc CAO sans inventer
#
# Dépendances :
#   pip install pyvista vtk numpy
#
# Modélise :
# - tube creux
# - chanfreins d'entrée/sortie si disponibles
# - guides visuels (axe, plans de début/fin)
#
# Limites volontaires :
# - pas de fente
# - pas de gorge d'huile
# - pas de perçage de lubrification
# - pas de bi-matière
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.coussinet_arbre_piston import CoussinetArbrePiston


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

def extraire_geometrie_depuis_rapport(rapport: Dict[str, Any]) -> Dict[str, float]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dictionnaire issu de CoussinetArbrePiston.analyser().")

    cao = _get_dict(rapport, "cao")
    coupe = _get_dict(cao, "coupe_radiale")

    d_int = cao.get("diametre_interieur_nominal_m")
    d_ext = cao.get("diametre_exterieur_nominal_m")
    L = cao.get("longueur_nominale_m")

    if d_int is None or L is None:
        raise ValueError(
            "Bloc CAO incomplet : diametre_interieur_nominal_m et longueur_nominale_m requis."
        )

    geom = {
        "diametre_interieur_nominal_m": _req_pos("cao.diametre_interieur_nominal_m", d_int),
        "diametre_exterieur_nominal_m": (
            _req_pos("cao.diametre_exterieur_nominal_m", d_ext)
            if d_ext is not None else None
        ),
        "longueur_nominale_m": _req_pos("cao.longueur_nominale_m", L),
        "epaisseur_radiale_m": (
            _req_pos("cao.epaisseur_radiale_m", cao.get("epaisseur_radiale_m"))
            if cao.get("epaisseur_radiale_m") is not None else None
        ),
        "jeu_radial_m": (
            _req_pos("cao.jeu_radial_m", cao.get("jeu_radial_m"), strictly=False)
            if cao.get("jeu_radial_m") is not None else None
        ),
        "chanfrein_entrees_m": (
            _req_pos("cao.chanfrein_entrees_m", cao.get("chanfrein_entrees_m"), strictly=False)
            if cao.get("chanfrein_entrees_m") is not None else 0.0
        ),
        "x_debut_m": (
            _req_finite("cao.x_debut_m", cao.get("x_debut_m"))
            if cao.get("x_debut_m") is not None else 0.0
        ),
        "x_fin_m": (
            _req_finite("cao.x_fin_m", cao.get("x_fin_m"))
            if cao.get("x_fin_m") is not None else _req_pos("cao.longueur_nominale_m", L)
        ),
        "rayon_interieur_m": (
            _req_pos("cao.coupe_radiale.rayon_interieur_m", coupe.get("rayon_interieur_m"))
            if coupe.get("rayon_interieur_m") is not None else 0.5 * _req_pos("cao.diametre_interieur_nominal_m", d_int)
        ),
        "rayon_exterieur_m": (
            _req_pos("cao.coupe_radiale.rayon_exterieur_m", coupe.get("rayon_exterieur_m"))
            if coupe.get("rayon_exterieur_m") is not None else (
                0.5 * _req_pos("cao.diametre_exterieur_nominal_m", d_ext) if d_ext is not None else None
            )
        ),
    }

    if geom["rayon_exterieur_m"] is None and geom["epaisseur_radiale_m"] is not None:
        geom["rayon_exterieur_m"] = geom["rayon_interieur_m"] + geom["epaisseur_radiale_m"]

    if geom["rayon_exterieur_m"] is None:
        raise ValueError(
            "Le rayon extérieur n'est pas calculable : fournir diamètre extérieur ou épaisseur radiale."
        )

    if geom["rayon_exterieur_m"] <= geom["rayon_interieur_m"]:
        raise ValueError("Géométrie invalide : rayon extérieur <= rayon intérieur.")

    return geom


# =============================================================================
# Construction géométrique détaillée
# =============================================================================

def _profil_coussinet_chanfreine(
    longueur_m: float,
    ri_m: float,
    ro_m: float,
    chanfrein_m: float,
    n_x: int = 120,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Construit les profils intérieur et extérieur avec chanfreins d'entrée/sortie.
    Chanfrein modélisé linéairement.
    """
    L = _req_pos("longueur_m", longueur_m)
    ri = _req_pos("ri_m", ri_m)
    ro = _req_pos("ro_m", ro_m)
    ch = _req_pos("chanfrein_m", chanfrein_m, strictly=False)

    e = ro - ri
    ch_eff = min(ch, 0.45 * L, 0.95 * e)

    x = np.linspace(-0.5 * L, 0.5 * L, n_x)
    r_ext = np.full_like(x, ro, dtype=float)
    r_int = np.full_like(x, ri, dtype=float)

    if ch_eff > 0.0:
        xl0 = -0.5 * L
        xl1 = xl0 + ch_eff
        xr0 = 0.5 * L - ch_eff
        xr1 = 0.5 * L

        m_left = x <= xl1
        m_right = x >= xr0

        # Chanfrein intérieur : ouverture plus large aux extrémités
        r_int[m_left] = ri + (1.0 - (x[m_left] - xl0) / ch_eff) * ch_eff
        r_int[m_right] = ri + ((x[m_right] - xr0) / ch_eff) * ch_eff

        # Chanfrein extérieur : on le garde cylindrique pour éviter d'inventer un profil externe non demandé
        # donc r_ext reste constant

    return x, r_int, r_ext


def _mesh_tube_chanfreine(
    longueur_m: float,
    ri_m: float,
    ro_m: float,
    chanfrein_m: float,
    n_x: int = 120,
    n_theta: int = 180,
) -> pv.PolyData:
    x, r_int, r_ext = _profil_coussinet_chanfreine(
        longueur_m=longueur_m,
        ri_m=ri_m,
        ro_m=ro_m,
        chanfrein_m=chanfrein_m,
        n_x=n_x,
    )

    theta = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)

    # Surface extérieure
    Xo = np.repeat(x[:, None], n_theta, axis=1)
    Yo = r_ext[:, None] * np.cos(theta)[None, :]
    Zo = r_ext[:, None] * np.sin(theta)[None, :]
    grid_o = pv.StructuredGrid(Xo, Yo, Zo)
    surf_o = grid_o.extract_surface().triangulate()

    # Surface intérieure
    Xi = np.repeat(x[:, None], n_theta, axis=1)
    Yi = r_int[:, None] * np.cos(theta)[None, :]
    Zi = r_int[:, None] * np.sin(theta)[None, :]
    grid_i = pv.StructuredGrid(Xi, Yi, Zi)
    surf_i = grid_i.extract_surface().triangulate()

    # Faces d'entrée/sortie par triangles annulaire
    pts = []
    faces = []

    for x_face, r1, r2 in ((x[0], r_int[0], r_ext[0]), (x[-1], r_int[-1], r_ext[-1])):
        base_idx = len(pts)
        for th in theta:
            pts.append([x_face, r1 * np.cos(th), r1 * np.sin(th)])
        for th in theta:
            pts.append([x_face, r2 * np.cos(th), r2 * np.sin(th)])

        n = len(theta)
        for i in range(n):
            i2 = (i + 1) % n
            a = base_idx + i
            b = base_idx + i2
            c = base_idx + n + i2
            d = base_idx + n + i
            faces.extend([4, a, b, c, d])

    annulus_faces = pv.PolyData(np.array(pts), np.array(faces))
    return surf_o.merge(surf_i).merge(annulus_faces).clean()


def construire_mesh_coussinet_detaille(
    rapport: Dict[str, Any],
    *,
    n_x: int = 120,
    n_theta: int = 180,
) -> Tuple[pv.PolyData, Dict[str, float]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    mesh = _mesh_tube_chanfreine(
        longueur_m=geom["longueur_nominale_m"],
        ri_m=geom["rayon_interieur_m"],
        ro_m=geom["rayon_exterieur_m"],
        chanfrein_m=geom["chanfrein_entrees_m"],
        n_x=n_x,
        n_theta=n_theta,
    )
    return mesh.clean(), geom


# =============================================================================
# Guides visuels
# =============================================================================

def construire_guides_visuels(geom: Dict[str, float]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    x0 = -0.5 * geom["longueur_nominale_m"]
    x1 = 0.5 * geom["longueur_nominale_m"]
    ro = geom["rayon_exterieur_m"]

    guides["axe"] = pv.Line(
        pointa=(x0 - 0.2 * geom["longueur_nominale_m"], 0.0, 0.0),
        pointb=(x1 + 0.2 * geom["longueur_nominale_m"], 0.0, 0.0),
        resolution=1,
    )

    guides["plan_debut"] = pv.Line(
        pointa=(x0, -1.2 * ro, 0.0),
        pointb=(x0, 1.2 * ro, 0.0),
        resolution=1,
    )

    guides["plan_fin"] = pv.Line(
        pointa=(x1, -1.2 * ro, 0.0),
        pointb=(x1, 1.2 * ro, 0.0),
        resolution=1,
    )

    return guides


def construire_coupe_visuelle(geom: Dict[str, float]) -> pv.PolyData:
    """
    Aide visuelle : un anneau mince au centre pour lire la coupe radiale.
    """
    return pv.Cylinder(
        center=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=geom["rayon_exterieur_m"],
        height=0.02 * geom["longueur_nominale_m"],
        resolution=160,
        capping=False,
    ).extract_surface().clean()


# =============================================================================
# Affichage
# =============================================================================

def afficher_coussinet_arbre_piston_3d_detaille(
    source: CoussinetArbrePiston | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    afficher_coupe_visuelle: bool = False,
    couleur_coussinet: str = "burlywood",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    if isinstance(source, CoussinetArbrePiston):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un CoussinetArbrePiston ou un rapport dict.")

    mesh, geom = construire_mesh_coussinet_detaille(rapport)

    plotter = pv.Plotter(window_size=(1280, 820))
    plotter.set_background("#1e1e1e")

    plotter.add_mesh(
        mesh,
        color=couleur_coussinet,
        smooth_shading=True,
        show_edges=afficher_bords,
        specular=0.28,
        specular_power=24,
    )

    if afficher_guides:
        guides = construire_guides_visuels(geom)
        if "axe" in guides:
            plotter.add_mesh(guides["axe"], color="white", line_width=2)
        if "plan_debut" in guides:
            plotter.add_mesh(guides["plan_debut"], color="gold", line_width=2)
        if "plan_fin" in guides:
            plotter.add_mesh(guides["plan_fin"], color="gold", line_width=2)

    if afficher_coupe_visuelle:
        coupe = construire_coupe_visuelle(geom)
        plotter.add_mesh(coupe, color="cyan", opacity=0.20, line_width=2)

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Coussinet arbre-piston — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh, rapport


# =============================================================================
# Exemple
# =============================================================================

if __name__ == "__main__":
    c = CoussinetArbrePiston(
        diametre_portee_m=0.020,
        longueur_coussinet_m=0.020,
        epaisseur_coussinet_m=0.002,
        charge_radiale_N=2000.0,
        rpm=3000.0,
        coefficient_frottement=0.05,
        mode_lubrification="eau",
        temperature_lubrifiant_K=300.0,
        pression_lubrifiant_Pa=101325.0,
        jeu_radial_m=20e-6,
        materiau_coussinet="bronze_cusn12",
        pression_admissible_pa=30e6,
        pv_admissible_W_m2=1.0e9,
        facteur_securite=2.0,
    )

    afficher_coussinet_arbre_piston_3d_detaille(c)