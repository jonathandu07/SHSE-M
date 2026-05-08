# frontend/pieces/3D/arbre_piston.py
# =============================================================================
# VISUALISATION 3D — ARBRE DE PISTON
# =============================================================================
# But :
# - afficher rapidement la forme 3D attendue de la pièce
# - utiliser uniquement les données calculées dans backend/components/moteur_thermique/pieces/arbre_piston.py
# - ne rien inventer si les cotes nécessaires sont absentes
#
# Dépendances :
#   pip install pyvista vtk
#
# Usage :
#   python frontend/pieces/3D/arbre_piston.py
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pyvista as pv

from backend.components.moteur_thermique.pieces.arbre_piston import ArbrePiston


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


def _get_cao(rapport: Dict[str, Any]) -> Dict[str, Any]:
    cao = rapport.get("cao")
    if not isinstance(cao, dict) or not cao:
        raise ValueError(
            "Bloc CAO absent. Il faut que ArbrePiston.analyser() puisse calculer rapport['cao']."
        )
    return cao


# =============================================================================
# Lecture des données CAO
# =============================================================================

def extraire_geometrie_depuis_rapport(rapport: Dict[str, Any]) -> Dict[str, float]:
    cao = _get_cao(rapport)

    axe_x = cao.get("axe_x", {})
    fut = cao.get("fut_central", {})
    tg = cao.get("teton_gauche", {})
    td = cao.get("teton_droit", {})

    geom = {
        "x0": _req_pos("cao.axe_x.x_debut_gauche_m", axe_x.get("x_debut_gauche_m"), strictly=False),
        "x1": _req_pos("cao.axe_x.x_fin_teton_gauche_m", axe_x.get("x_fin_teton_gauche_m")),
        "x2": _req_pos("cao.axe_x.x_fin_fut_central_m", axe_x.get("x_fin_fut_central_m")),
        "x3": _req_pos("cao.axe_x.x_fin_teton_droit_m", axe_x.get("x_fin_teton_droit_m")),

        "L_g": _req_pos("cao.teton_gauche.longueur_m", tg.get("longueur_m")),
        "D_g": _req_pos("cao.teton_gauche.diametre_m", tg.get("diametre_m")),

        "L_f": _req_pos("cao.fut_central.longueur_m", fut.get("longueur_m")),
        "D_f_ext": _req_pos("cao.fut_central.diametre_exterieur_m", fut.get("diametre_exterieur_m")),
        "D_f_int": _req_pos("cao.fut_central.diametre_interieur_m", fut.get("diametre_interieur_m"), strictly=False),

        "L_d": _req_pos("cao.teton_droit.longueur_m", td.get("longueur_m")),
        "D_d": _req_pos("cao.teton_droit.diametre_m", td.get("diametre_m")),
    }

    return geom


# =============================================================================
# Construction géométrique simple
# =============================================================================

def _cylindre_x(
    centre_x: float,
    longueur: float,
    rayon: float,
    resolution: int = 96,
) -> pv.PolyData:
    cyl = pv.Cylinder(
        center=(centre_x, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=rayon,
        height=longueur,
        resolution=resolution,
        capping=True,
    )
    return cyl.triangulate()


def construire_mesh_arbre_piston(rapport: Dict[str, Any], resolution: int = 96) -> pv.PolyData:
    """
    Construit un mesh 3D simple de visualisation.
    """
    g = extraire_geometrie_depuis_rapport(rapport)

    # Tronçons externes
    cyl_g = _cylindre_x(
        centre_x=(g["x0"] + g["x1"]) / 2.0,
        longueur=g["L_g"],
        rayon=g["D_g"] / 2.0,
        resolution=resolution,
    )

    cyl_f = _cylindre_x(
        centre_x=(g["x1"] + g["x2"]) / 2.0,
        longueur=g["L_f"],
        rayon=g["D_f_ext"] / 2.0,
        resolution=resolution,
    )

    cyl_d = _cylindre_x(
        centre_x=(g["x2"] + g["x3"]) / 2.0,
        longueur=g["L_d"],
        rayon=g["D_d"] / 2.0,
        resolution=resolution,
    )

    mesh = cyl_g.merge(cyl_f).merge(cyl_d).clean()

    # Evidement central seulement si explicitement défini
    if g["D_f_int"] > 0.0:
        tube_int = _cylindre_x(
            centre_x=(g["x1"] + g["x2"]) / 2.0,
            longueur=g["L_f"] + 1e-6,  # léger epsilon pour éviter les artefacts booléens
            rayon=g["D_f_int"] / 2.0,
            resolution=resolution,
        )
        try:
            mesh = mesh.boolean_difference(tube_int)
        except Exception:
            # Si la soustraction booléenne échoue localement,
            # on garde l'enveloppe externe plutôt que d'inventer autre chose.
            pass

    return mesh.clean()


# =============================================================================
# Visualisation
# =============================================================================

def afficher_arbre_piston_3d(
    source: ArbrePiston | Dict[str, Any],
    *,
    resolution: int = 96,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    couleur: str = "lightsteelblue",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    """
    Affiche la pièce dans une fenêtre interactive PyVista.
    """
    if isinstance(source, ArbrePiston):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un ArbrePiston ou un rapport dict.")

    mesh = construire_mesh_arbre_piston(rapport, resolution=resolution)

    plotter = pv.Plotter(window_size=(1200, 800))
    plotter.set_background("#1e1e1e")

    plotter.add_mesh(
        mesh,
        color=couleur,
        smooth_shading=True,
        show_edges=afficher_bords,
        specular=0.25,
        specular_power=20,
    )

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Arbre de piston — visualisation 3D", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh, rapport


# =============================================================================
# Exemple direct
# =============================================================================

if __name__ == "__main__":
    arbre = ArbrePiston(
        densite_kg_m3=7800.0,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        facteur_securite=2.0,

        longueur_fut_central_m=0.040,
        profondeur_taraudage_gauche_m=0.012,
        profondeur_taraudage_droit_m=0.012,

        force_axiale_N=15000.0,
        force_cisaillement_N=2000.0,
        bras_levier_charge_m=0.010,

        longueur_libre_m=0.060,
        K_flambage=1.0,

        effort_axial_sur_taraudage_gauche_N=8000.0,
        effort_axial_sur_taraudage_droit_N=8000.0,
        resistance_cisaillement_matiere_taraudee_pa=250e6,

        filetage_gauche="M8",
        filetage_droit="M8",
        ratio_evidement_k=0.5,
    )

    afficher_arbre_piston_3d(arbre)
