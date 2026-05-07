# frontend/pieces/3D/arbre.py
# =============================================================================
# VISUALISATION 3D DÉTAILLÉE — ARBRE MOTEUR
# =============================================================================
# But :
# - afficher une forme 3D détaillée et crédible de l'arbre moteur
# - utiliser les données calculées par backend/pieces/arbre.py
# - ne pas inventer des diamètres d'épaulement non fournis
#
# Dépendances :
#   pip install pyvista vtk numpy
#
# Ce module modélise :
# - le corps de l'arbre,
# - les chanfreins d'extrémité,
# - la rainure de clavette (si calculable),
# - les zones axiales utiles (entrée / bloc cylindres / sortie) comme aides visuelles.
#
# Limite volontaire :
# - pas de variation de diamètre d'épaulement si le backend n'en donne pas.
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.arbre import ArbreMoteur


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
# Extraction des données
# =============================================================================

def extraire_geometrie_depuis_rapport(rapport: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dictionnaire issu de ArbreMoteur.analyser().")

    cao = _get_dict(rapport, "cao")
    longueur = _get_dict(rapport, "longueur")
    interfaces = _get_dict(rapport, "interfaces")
    clavette = _get_dict(rapport, "clavette")

    d = cao.get("diametre_nominal_arbre_m")
    L = cao.get("longueur_totale_m")
    ch = cao.get("chanfrein_extremite_m")
    rc = cao.get("rayon_conge_epaulement_m")

    if d is None or L is None:
        raise ValueError(
            "Le bloc CAO ne contient pas assez d'informations pour afficher l'arbre "
            "(diametre_nominal_arbre_m et longueur_totale_m requis)."
        )

    geom = {
        "diametre_arbre_m": _req_pos("cao.diametre_nominal_arbre_m", d),
        "longueur_totale_m": _req_pos("cao.longueur_totale_m", L),
        "chanfrein_extremite_m": _req_pos("cao.chanfrein_extremite_m", ch, strictly=False) if ch is not None else 0.0,
        "rayon_conge_epaulement_m": _req_pos("cao.rayon_conge_epaulement_m", rc, strictly=False) if rc is not None else None,

        "bloc_cylindres_longueur_m": (
            _req_pos("longueur.bloc_cylindres_longueur_m", longueur.get("bloc_cylindres_longueur_m"))
            if longueur.get("bloc_cylindres_longueur_m") is not None else None
        ),
        "empilement_entree_m": (
            _req_pos("longueur.empilement_annexe_cote_entree_m", longueur.get("empilement_annexe_cote_entree_m"))
            if longueur.get("empilement_annexe_cote_entree_m") is not None else None
        ),
        "empilement_sortie_m": (
            _req_pos("longueur.empilement_annexe_cote_sortie_m", longueur.get("empilement_annexe_cote_sortie_m"))
            if longueur.get("empilement_annexe_cote_sortie_m") is not None else None
        ),
        "depassement_entree_m": (
            _req_pos("longueur.depassement_cote_entree_m", longueur.get("depassement_cote_entree_m"), strictly=False)
            if longueur.get("depassement_cote_entree_m") is not None else None
        ),
        "depassement_sortie_m": (
            _req_pos("longueur.depassement_cote_sortie_m", longueur.get("depassement_cote_sortie_m"), strictly=False)
            if longueur.get("depassement_cote_sortie_m") is not None else None
        ),

        "largeur_moyeu_vilbrequin_m": (
            _req_pos("interfaces.largeur_moyeu_vilbrequin_m", interfaces.get("largeur_moyeu_vilbrequin_m"))
            if interfaces.get("largeur_moyeu_vilbrequin_m") is not None else None
        ),
        "largeur_portee_roulement_m": (
            _req_pos("interfaces.largeur_portee_roulement_m", interfaces.get("largeur_portee_roulement_m"))
            if interfaces.get("largeur_portee_roulement_m") is not None else None
        ),

        "clavette_b_m": (
            _req_pos("clavette.b_m", clavette.get("b_m"))
            if clavette.get("b_m") is not None else None
        ),
        "clavette_h_m": (
            _req_pos("clavette.h_m", clavette.get("h_m"))
            if clavette.get("h_m") is not None else None
        ),
        "clavette_longueur_m": (
            _req_pos("clavette.longueur_min_requise_m", clavette.get("longueur_min_requise_m"))
            if clavette.get("longueur_min_requise_m") is not None else None
        ),
        "profondeur_rainure_arbre_m": (
            _req_pos("clavette.profondeur_rainure_arbre_m", clavette.get("profondeur_rainure_arbre_m"))
            if clavette.get("profondeur_rainure_arbre_m") is not None else None
        ),
    }

    return geom


# =============================================================================
# Géométrie de révolution
# =============================================================================

def _profil_rayon_avec_chanfreins(
    longueur_m: float,
    rayon_m: float,
    chanfrein_m: float,
    n_x: int = 120,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Profil radial le long de X.
    Le chanfrein est modélisé comme un biseau linéaire à 45° :
    - aux extrémités, le rayon de face vaut R - c
    - puis il rejoint linéairement R sur une longueur c
    """
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

        r[left_mask] = (R - c_eff) + (x[left_mask] - x_left0) / c_eff * c_eff
        r[right_mask] = R - (x[right_mask] - x_right0) / c_eff * c_eff

    r = np.clip(r, 1e-9, None)
    return x, r


def _mesh_revolution_arbre(
    longueur_m: float,
    diametre_m: float,
    chanfrein_m: float,
    n_x: int = 120,
    n_theta: int = 180,
) -> pv.PolyData:
    """
    Construit l'enveloppe extérieure de l'arbre par révolution autour de l'axe X.
    """
    R = 0.5 * _req_pos("diametre_m", diametre_m)
    x_prof, r_prof = _profil_rayon_avec_chanfreins(longueur_m, R, chanfrein_m, n_x=n_x)

    theta = np.linspace(0.0, 2.0 * np.pi, n_theta, endpoint=False)

    X = np.repeat(x_prof[:, None], n_theta, axis=1)
    Y = r_prof[:, None] * np.cos(theta)[None, :]
    Z = r_prof[:, None] * np.sin(theta)[None, :]

    grid = pv.StructuredGrid(X, Y, Z)
    surf = grid.extract_surface().triangulate().clean()

    # Bouchons d'extrémité
    r_face = max(R - min(chanfrein_m, 0.95 * R), 1e-9)

    cyl_cap_g = pv.Cylinder(
        center=(-0.5 * longueur_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_face,
        height=1e-6,
        resolution=max(48, n_theta),
        capping=True,
    ).triangulate()

    cyl_cap_d = pv.Cylinder(
        center=(0.5 * longueur_m, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=r_face,
        height=1e-6,
        resolution=max(48, n_theta),
        capping=True,
    ).triangulate()

    return surf.merge(cyl_cap_g).merge(cyl_cap_d).clean()


# =============================================================================
# Rainure de clavette
# =============================================================================

def _calculer_zone_clavette(geom: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Détermine x_debut et x_fin de la clavette.

    Convention d'affichage explicitée :
    - si on connaît le dépassement d'entrée + largeur de moyeu, on place la clavette
      dans la zone de moyeu côté entrée ;
    - sinon, on la centre dans l'empilement d'entrée ;
    - sinon, on ne la place pas.
    """
    L = geom["longueur_totale_m"]
    x0 = -0.5 * L

    L_key = geom["clavette_longueur_m"]
    if L_key is None or L_key <= 0.0:
        return None

    dep_in = geom["depassement_entree_m"]
    largeur_moyeu = geom["largeur_moyeu_vilbrequin_m"]
    emp_in = geom["empilement_entree_m"]

    if dep_in is not None and largeur_moyeu is not None:
        zone_start = x0 + dep_in
        zone_end = zone_start + largeur_moyeu
        zone_len = zone_end - zone_start
        if zone_len <= 0.0:
            return None
        x_start = zone_start + max(0.0, 0.5 * (zone_len - L_key))
        x_end = x_start + min(L_key, zone_len)
        return x_start, x_end

    if emp_in is not None:
        zone_start = x0
        zone_end = x0 + emp_in
        zone_len = zone_end - zone_start
        if zone_len <= 0.0:
            return None
        x_start = zone_start + max(0.0, 0.5 * (zone_len - L_key))
        x_end = x_start + min(L_key, zone_len)
        return x_start, x_end

    return None


def _booleen_rainure_clavette(mesh: pv.PolyData, geom: Dict[str, Any]) -> pv.PolyData:
    b = geom["clavette_b_m"]
    t2 = geom["profondeur_rainure_arbre_m"]
    d = geom["diametre_arbre_m"]

    if b is None or t2 is None or d is None:
        return mesh

    zone = _calculer_zone_clavette(geom)
    if zone is None:
        return mesh

    x_start, x_end = zone
    if x_end <= x_start:
        return mesh

    R = 0.5 * d
    longueur = x_end - x_start

    # La rainure est modélisée comme un enlèvement prismatique.
    # Elle est centrée sur le sommet de l'arbre (direction +Y).
    y_min = R - t2
    y_max = R + 2.0 * t2

    box = pv.Box(bounds=(
        x_start, x_end,
        -0.5 * b, 0.5 * b,
        y_min, y_max,
    )).triangulate()

    # Rotation pour placer la largeur de rainure selon Z et la profondeur selon Y
    box = box.rotate_x(90.0, point=(0.0, 0.0, 0.0), inplace=False)

    try:
        out = mesh.triangulate().boolean_difference(box)
        return out.clean()
    except Exception:
        # Si le booléen échoue localement, on préfère garder la géométrie externe
        return mesh


# =============================================================================
# Guides visuels
# =============================================================================

def construire_guides_visuels(geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    L = geom["longueur_totale_m"]
    d = geom["diametre_arbre_m"]
    R = 0.5 * d

    x0 = -0.5 * L
    x3 = 0.5 * L

    guides["axe"] = pv.Line((x0 - 0.05 * L, 0.0, 0.0), (x3 + 0.05 * L, 0.0, 0.0), resolution=1)

    emp_in = geom["empilement_entree_m"]
    bloc = geom["bloc_cylindres_longueur_m"]
    emp_out = geom["empilement_sortie_m"]

    if emp_in is not None:
        x1 = x0 + emp_in
        guides["plan_entree"] = pv.Line((x1, -1.4 * R, 0.0), (x1, 1.4 * R, 0.0), resolution=1)

    if emp_in is not None and bloc is not None:
        x2 = x0 + emp_in + bloc
        guides["plan_sortie_bloc"] = pv.Line((x2, -1.4 * R, 0.0), (x2, 1.4 * R, 0.0), resolution=1)

    zone = _calculer_zone_clavette(geom)
    if zone is not None:
        xs, xe = zone
        guides["clavette_debut"] = pv.Line((xs, -1.2 * R, 0.0), (xs, 1.2 * R, 0.0), resolution=1)
        guides["clavette_fin"] = pv.Line((xe, -1.2 * R, 0.0), (xe, 1.2 * R, 0.0), resolution=1)

    return guides


def construire_bandes_axiales(geom: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    """
    Cylindres légèrement surdimensionnés servant d'aide visuelle pour lire les zones.
    """
    bandes: Dict[str, pv.PolyData] = {}
    L = geom["longueur_totale_m"]
    d = geom["diametre_arbre_m"]
    R = 0.5 * d

    x0 = -0.5 * L
    emp_in = geom["empilement_entree_m"]
    bloc = geom["bloc_cylindres_longueur_m"]
    emp_out = geom["empilement_sortie_m"]

    r_visu = 1.12 * R

    if emp_in is not None and emp_in > 0.0:
        bandes["entree"] = pv.Cylinder(
            center=(x0 + 0.5 * emp_in, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),
            radius=r_visu,
            height=emp_in,
            resolution=96,
            capping=False,
        ).extract_surface().clean()

    if emp_in is not None and bloc is not None and bloc > 0.0:
        bandes["bloc"] = pv.Cylinder(
            center=(x0 + emp_in + 0.5 * bloc, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),
            radius=r_visu,
            height=bloc,
            resolution=96,
            capping=False,
        ).extract_surface().clean()

    if emp_out is not None and emp_out > 0.0:
        bandes["sortie"] = pv.Cylinder(
            center=(0.5 * L - 0.5 * emp_out, 0.0, 0.0),
            direction=(1.0, 0.0, 0.0),
            radius=r_visu,
            height=emp_out,
            resolution=96,
            capping=False,
        ).extract_surface().clean()

    return bandes


# =============================================================================
# Construction complète
# =============================================================================

def construire_mesh_arbre_detaille(
    rapport: Dict[str, Any],
    *,
    n_x: int = 140,
    n_theta: int = 200,
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    geom = extraire_geometrie_depuis_rapport(rapport)

    mesh = _mesh_revolution_arbre(
        longueur_m=geom["longueur_totale_m"],
        diametre_m=geom["diametre_arbre_m"],
        chanfrein_m=geom["chanfrein_extremite_m"],
        n_x=n_x,
        n_theta=n_theta,
    )

    mesh = _booleen_rainure_clavette(mesh, geom)
    return mesh.clean(), geom


# =============================================================================
# Visualisation
# =============================================================================

def afficher_arbre_3d_detaille(
    source: ArbreMoteur | Dict[str, Any],
    *,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    afficher_bandes: bool = True,
    couleur_arbre: str = "lightsteelblue",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    if isinstance(source, ArbreMoteur):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un ArbreMoteur ou un rapport dict.")

    mesh, geom = construire_mesh_arbre_detaille(rapport)

    plotter = pv.Plotter(window_size=(1300, 820))
    plotter.set_background("#1e1e1e")

    plotter.add_mesh(
        mesh,
        color=couleur_arbre,
        smooth_shading=True,
        show_edges=afficher_bords,
        specular=0.30,
        specular_power=25,
    )

    if afficher_bandes:
        bandes = construire_bandes_axiales(geom)
        if "entree" in bandes:
            plotter.add_mesh(bandes["entree"], color="gold", opacity=0.18, line_width=2)
        if "bloc" in bandes:
            plotter.add_mesh(bandes["bloc"], color="cyan", opacity=0.12, line_width=2)
        if "sortie" in bandes:
            plotter.add_mesh(bandes["sortie"], color="tomato", opacity=0.18, line_width=2)

    if afficher_guides:
        guides = construire_guides_visuels(geom)
        for name, guide in guides.items():
            color = "white"
            width = 2
            if "clavette" in name:
                color = "gold"
                width = 3
            plotter.add_mesh(guide, color=color, line_width=width)

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Arbre moteur — visualisation 3D détaillée", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh, rapport


# =============================================================================
# Exemple
# =============================================================================

if __name__ == "__main__":
    a = ArbreMoteur(
        couple_max_Nm=120.0,
        moment_flexion_max_Nm=40.0,
        nombre_cylindres=2,
        entraxe_cylindres_m=0.120,
        diametre_externe_cylindre_m=0.090,
        depassement_cote_entree_m=0.020,
        depassement_cote_sortie_m=0.015,
        limite_elastique_arbre_pa=700e6,
        densite_arbre_kg_m3=7800.0,
        facteur_securite=2.0,
        limite_elastique_clavette_pa=500e6,
        limite_elastique_moyeu_pa=450e6,
    )

    afficher_arbre_3d_detaille(a)