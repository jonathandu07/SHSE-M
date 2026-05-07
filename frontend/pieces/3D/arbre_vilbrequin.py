# frontend/pieces/3D/arbre_vilbrequin.py
# =============================================================================
# VISUALISATION 3D — ARBRE DE VILEBREQUIN
# =============================================================================
# But :
# - afficher rapidement la forme 3D attendue minimale de la pièce
# - utiliser uniquement les données calculées dans backend/components/moteur_thermique/pieces/arbre_vilbrequin.py
# - ne pas inventer les bras/contrepoids si non définis
#
# Dépendances :
#   pip install pyvista vtk
#
# Usage :
#   python frontend/pieces/3D/arbre_vilbrequin.py
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pyvista as pv

from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin


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
            "Bloc CAO absent. Il faut que ArbreVilbrequin.analyser() puisse calculer rapport['cao']."
        )
    return cao


# =============================================================================
# Lecture des données CAO
# =============================================================================

def extraire_geometrie_depuis_rapport(rapport: Dict[str, Any]) -> Dict[str, Any]:
    cao = _get_cao(rapport)

    manivelle = cao.get("manivelle", {})
    journal = cao.get("journal_principal", {})
    maneton = cao.get("maneton", {})

    geom: Dict[str, Any] = {
        "rayon_manivelle_m": (
            _req_pos("cao.manivelle.rayon_manivelle_m", manivelle.get("rayon_manivelle_m"))
            if manivelle.get("rayon_manivelle_m") is not None
            else None
        ),

        "journal_diametre_m": (
            _req_pos("cao.journal_principal.diametre_m", journal.get("diametre_m"))
            if journal.get("diametre_m") is not None
            else None
        ),
        "journal_largeur_m": (
            _req_pos("cao.journal_principal.largeur_portee_m", journal.get("largeur_portee_m"))
            if journal.get("largeur_portee_m") is not None
            else None
        ),
        "journal_centre_gauche_x_m": (
            _req_finite("cao.journal_principal.centre_gauche_x_m", journal.get("centre_gauche_x_m"))
            if journal.get("centre_gauche_x_m") is not None
            else None
        ),
        "journal_centre_droit_x_m": (
            _req_finite("cao.journal_principal.centre_droit_x_m", journal.get("centre_droit_x_m"))
            if journal.get("centre_droit_x_m") is not None
            else None
        ),

        "maneton_diametre_m": (
            _req_pos("cao.maneton.diametre_m", maneton.get("diametre_m"))
            if maneton.get("diametre_m") is not None
            else None
        ),
        "maneton_largeur_m": (
            _req_pos("cao.maneton.largeur_portee_m", maneton.get("largeur_portee_m"))
            if maneton.get("largeur_portee_m") is not None
            else None
        ),
        "maneton_centre_x_m": (
            _req_finite("cao.maneton.centre_x_m", maneton.get("centre_x_m"))
            if maneton.get("centre_x_m") is not None
            else None
        ),

        "nb_journaux_principaux": int(cao.get("nb_journaux_principaux", 0) or 0),
        "hypothese_modele": cao.get("hypothese_modele"),
    }

    return geom


# =============================================================================
# Construction géométrique simple
# =============================================================================

def _cylindre_z(
    centre_x: float,
    centre_y: float,
    longueur: float,
    rayon: float,
    resolution: int = 96,
) -> pv.PolyData:
    cyl = pv.Cylinder(
        center=(centre_x, centre_y, 0.0),
        direction=(0.0, 0.0, 1.0),
        radius=rayon,
        height=longueur,
        resolution=resolution,
        capping=True,
    )
    return cyl.triangulate()


def construire_mesh_arbre_vilebrequin(
    rapport: Dict[str, Any],
    resolution: int = 96,
) -> Tuple[pv.PolyData, Dict[str, pv.PolyData]]:
    """
    Construit un mesh 3D simple de visualisation.
    Ne modélise que les portées explicitement définies dans le backend :
    - journaux principaux
    - maneton
    Les bras/contrepoids ne sont pas inventés.
    """
    g = extraire_geometrie_depuis_rapport(rapport)

    sous_meshes: Dict[str, pv.PolyData] = {}
    mesh_total: Optional[pv.PolyData] = None

    # Journaux principaux : sur l'axe principal y = 0
    if (
        g["journal_diametre_m"] is not None
        and g["journal_largeur_m"] is not None
    ):
        rj = g["journal_diametre_m"] / 2.0

        if g["journal_centre_gauche_x_m"] is not None:
            jg = _cylindre_z(
                centre_x=g["journal_centre_gauche_x_m"],
                centre_y=0.0,
                longueur=g["journal_largeur_m"],
                rayon=rj,
                resolution=resolution,
            )
            sous_meshes["journal_gauche"] = jg
            mesh_total = jg if mesh_total is None else mesh_total.merge(jg)

        if g["journal_centre_droit_x_m"] is not None:
            jd = _cylindre_z(
                centre_x=g["journal_centre_droit_x_m"],
                centre_y=0.0,
                longueur=g["journal_largeur_m"],
                rayon=rj,
                resolution=resolution,
            )
            sous_meshes["journal_droit"] = jd
            mesh_total = jd if mesh_total is None else mesh_total.merge(jd)

    # Maneton : parallèle à l'axe Z, mais décalé radialement de r_manivelle
    if (
        g["maneton_diametre_m"] is not None
        and g["maneton_largeur_m"] is not None
    ):
        rm = g["maneton_diametre_m"] / 2.0
        x_m = g["maneton_centre_x_m"] if g["maneton_centre_x_m"] is not None else 0.0
        y_m = g["rayon_manivelle_m"] if g["rayon_manivelle_m"] is not None else 0.0

        m = _cylindre_z(
            centre_x=x_m,
            centre_y=y_m,
            longueur=g["maneton_largeur_m"],
            rayon=rm,
            resolution=resolution,
        )
        sous_meshes["maneton"] = m
        mesh_total = m if mesh_total is None else mesh_total.merge(m)

    if mesh_total is None:
        raise ValueError(
            "Aucune géométrie exploitable à afficher : ni journal principal ni maneton définis."
        )

    return mesh_total.clean(), sous_meshes


# =============================================================================
# Aides visuelles
# =============================================================================

def construire_guides_visuels(rapport: Dict[str, Any]) -> Dict[str, pv.PolyData]:
    """
    Construit quelques guides non-solides pour mieux lire la géométrie :
    - axe principal
    - point centre maneton
    - ligne de manivelle
    """
    g = extraire_geometrie_depuis_rapport(rapport)
    guides: Dict[str, pv.PolyData] = {}

    xs = []

    if g["journal_centre_gauche_x_m"] is not None:
        xs.append(float(g["journal_centre_gauche_x_m"]))
    if g["journal_centre_droit_x_m"] is not None:
        xs.append(float(g["journal_centre_droit_x_m"]))
    if g["maneton_centre_x_m"] is not None:
        xs.append(float(g["maneton_centre_x_m"]))

    if not xs:
        xs = [-0.05, 0.05]

    x_min = min(xs) - 0.05
    x_max = max(xs) + 0.05

    # Axe principal de rotation : ligne dans X au niveau y=0, z=0
    guides["axe_rotation"] = pv.Line(
        pointa=(x_min, 0.0, 0.0),
        pointb=(x_max, 0.0, 0.0),
        resolution=1,
    )

    # Guide rayon de manivelle
    if g["rayon_manivelle_m"] is not None:
        x_m = g["maneton_centre_x_m"] if g["maneton_centre_x_m"] is not None else 0.0
        y_m = g["rayon_manivelle_m"]
        guides["rayon_manivelle"] = pv.Line(
            pointa=(x_m, 0.0, 0.0),
            pointb=(x_m, y_m, 0.0),
            resolution=1,
        )
        guides["centre_maneton"] = pv.PolyData([(x_m, y_m, 0.0)])

    return guides


# =============================================================================
# Visualisation
# =============================================================================

def afficher_arbre_vilebrequin_3d(
    source: ArbreVilbrequin | Dict[str, Any],
    *,
    resolution: int = 96,
    afficher_axes: bool = True,
    afficher_bords: bool = False,
    afficher_guides: bool = True,
    couleur_journaux: str = "lightsteelblue",
    couleur_maneton: str = "salmon",
) -> Tuple[pv.PolyData, Dict[str, Any]]:
    """
    Affiche la pièce dans une fenêtre interactive PyVista.
    """
    if isinstance(source, ArbreVilbrequin):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un ArbreVilbrequin ou un rapport dict.")

    mesh_total, sous_meshes = construire_mesh_arbre_vilebrequin(
        rapport,
        resolution=resolution,
    )

    plotter = pv.Plotter(window_size=(1280, 820))
    plotter.set_background("#1e1e1e")

    # Journaux
    if "journal_gauche" in sous_meshes:
        plotter.add_mesh(
            sous_meshes["journal_gauche"],
            color=couleur_journaux,
            smooth_shading=True,
            show_edges=afficher_bords,
            specular=0.25,
            specular_power=20,
        )

    if "journal_droit" in sous_meshes:
        plotter.add_mesh(
            sous_meshes["journal_droit"],
            color=couleur_journaux,
            smooth_shading=True,
            show_edges=afficher_bords,
            specular=0.25,
            specular_power=20,
        )

    # Maneton
    if "maneton" in sous_meshes:
        plotter.add_mesh(
            sous_meshes["maneton"],
            color=couleur_maneton,
            smooth_shading=True,
            show_edges=afficher_bords,
            specular=0.25,
            specular_power=20,
        )

    # Guides
    if afficher_guides:
        guides = construire_guides_visuels(rapport)

        if "axe_rotation" in guides:
            plotter.add_mesh(guides["axe_rotation"], color="white", line_width=2)

        if "rayon_manivelle" in guides:
            plotter.add_mesh(guides["rayon_manivelle"], color="gold", line_width=3)

        if "centre_maneton" in guides:
            plotter.add_mesh(
                guides["centre_maneton"],
                color="gold",
                point_size=12,
                render_points_as_spheres=True,
            )

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    plotter.add_text("Arbre de vilebrequin — visualisation 3D minimale", font_size=12)
    plotter.view_isometric()
    plotter.show()

    return mesh_total, rapport


# =============================================================================
# Exemple minimal
# =============================================================================

if __name__ == "__main__":
    class RoulementAiguilleMock:
        def calculer(self):
            return {
                "dimensions_requises": {"d_interieur_requis_m": 0.030},
                "dimensions_reference": {
                    "d_interieur_m": 0.030,
                    "D_exterieur_m": 0.037,
                    "B_largeur_m": 0.016,
                },
            }

    av = ArbreVilbrequin(
        roulement_aiguille=RoulementAiguilleMock(),
        course_m=0.085,
        couple_max_Nm=134.0,
        limite_elastique_pa=800e6,
        densite_kg_m3=7800.0,
        facteur_securite=2.0,
        nb_journaux_principaux=2,
        entre_axe_paliers_m=0.120,
    )

    afficher_arbre_vilebrequin_3d(av)
