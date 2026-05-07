# frontend/pieces/3D/roulement_aiguille_arbre.py
# =============================================================================
# VISUALISATION 3D — ROULEMENT À AIGUILLES (ARBRE / VILEBREQUIN)
# =============================================================================
# But :
# - visualiser en 3D un roulement à aiguilles issu de backend/components/moteur_thermique/pieces/roulement_aiguille_arbre.py
# - ne rien inventer :
#   * si D extérieur n'est pas connu, on n'invente pas une bague extérieure
#   * si la référence commerciale n'est pas fournie, on affiche les dimensions requises
#   * pas de cage / aiguilles individuelles car backend ne les définit pas ici
#
# Dépendances :
#   pip install pyvista vtk numpy
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import math

import numpy as np
import pyvista as pv

from backend.components.moteur_thermique.pieces.roulement_aiguille_arbre import RoulementAiguilleArbre


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
# Extraction depuis rapport backend
# =============================================================================

def extraire_cao_roulement_aiguille_arbre(
    rapport: Dict[str, Any],
    *,
    type_portee: Optional[str] = None,
) -> Dict[str, Any]:
    if not isinstance(rapport, dict):
        raise TypeError("rapport doit être un dict issu de RoulementAiguilleArbre.analyser().")

    dims_req = _safe_dict(rapport, "dimensions_requises")
    dims_ref = _safe_dict(rapport, "dimensions_reference")
    charges = _safe_dict(rapport, "charges")
    verifs = _safe_dict(rapport, "verifications_reference")

    type_eff = type_portee
    if type_eff is None:
        # priorité :
        # 1) entrée dimensions_requises.d_interieur_requis_m si backend l'a résolu
        # 2) journal si disponible
        # 3) maneton si disponible
        if dims_req.get("d_interieur_requis_m") is not None:
            type_eff = "unique"
        elif isinstance(dims_req.get("journal"), dict) and dims_req["journal"].get("d_interieur_requis_m") is not None:
            type_eff = "journal"
        elif isinstance(dims_req.get("maneton"), dict) and dims_req["maneton"].get("d_interieur_requis_m") is not None:
            type_eff = "maneton"
        else:
            type_eff = "unique"

    if type_eff == "journal":
        bloc_req = dims_req.get("journal", {})
    elif type_eff == "maneton":
        bloc_req = dims_req.get("maneton", {})
    else:
        bloc_req = dims_req

    d_req = bloc_req.get("d_interieur_requis_m")
    B_req = bloc_req.get("B_largeur_requise_m")

    d_ref = dims_ref.get("d_interieur_m")
    D_ref = dims_ref.get("D_exterieur_m")
    B_ref = dims_ref.get("B_largeur_m")

    d_use = d_ref if _is_finite(d_ref) else d_req
    B_use = B_ref if _is_finite(B_ref) else B_req
    D_use = D_ref if _is_finite(D_ref) else None

    if d_use is None:
        raise ValueError("Aucun diamètre intérieur exploitable trouvé dans le rapport.")
    if B_use is None:
        raise ValueError("Aucune largeur B exploitable trouvée dans le rapport.")

    out = {
        "type_portee": type_eff,
        "designation": dims_ref.get("designation"),
        "d_interieur_m": _req_pos("d_interieur_m", d_use),
        "B_largeur_m": _req_pos("B_largeur_m", B_use),
        "D_exterieur_m": _req_pos("D_exterieur_m", D_use) if D_use is not None else None,
        "force_radiale_equivalente_N": charges.get("force_radiale_equivalente_N"),
        "pression_proj_journal_pa": charges.get("pression_projetee_journal_pa"),
        "pression_proj_maneton_pa": charges.get("pression_projetee_maneton_pa"),
        "verification_reference": verifs,
    }
    return out


# =============================================================================
# Primitives
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
    resolution: int = 140,
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


# =============================================================================
# Construction 3D
# =============================================================================

def construire_roulement_aiguille_arbre_3d(
    rapport: Dict[str, Any],
    *,
    type_portee: Optional[str] = None,
    ratio_epaisseur_bague_ref: float = 0.08,
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    g = extraire_cao_roulement_aiguille_arbre(rapport, type_portee=type_portee)

    d_int = g["d_interieur_m"]
    B = g["B_largeur_m"]
    D_ext = g["D_exterieur_m"]

    z_min = -0.5 * B
    z_max = 0.5 * B

    meshes: Dict[str, pv.PolyData] = {}

    # -------------------------------------------------------------------------
    # Portée intérieure / bague intérieure de référence
    # -------------------------------------------------------------------------
    # Le backend ne donne pas ici une vraie épaisseur de bague intérieure.
    # On crée donc un cylindre de référence représentant la portée arbre/maneton.
    meshes["portee_interieure_reference"] = _cylindre_z(
        z_min=z_min,
        z_max=z_max,
        diametre_m=d_int,
    )

    # -------------------------------------------------------------------------
    # Bague extérieure si référence connue
    # -------------------------------------------------------------------------
    if D_ext is not None:
        # on évite d'inventer un profil interne réel du roulement :
        # on prend une couronne minimale autour de d_int.
        di_be = max(d_int * (1.0 + 2.0 * ratio_epaisseur_bague_ref), d_int + 1e-5)
        if di_be >= D_ext:
            di_be = 0.98 * D_ext

        if di_be > d_int and D_ext > di_be:
            meshes["bague_exterieure"] = _tube_z(
                z_min=z_min,
                z_max=z_max,
                diametre_interieur_m=di_be,
                diametre_exterieur_m=D_ext,
            )

    # -------------------------------------------------------------------------
    # Volume enveloppe du roulement
    # -------------------------------------------------------------------------
    # utile visuellement si D extérieur absent
    if D_ext is None:
        d_env = d_int * 1.15
        meshes["enveloppe_inconnue"] = _tube_z(
            z_min=z_min,
            z_max=z_max,
            diametre_interieur_m=d_int,
            diametre_exterieur_m=d_env,
        )

    return meshes, g


# =============================================================================
# Guides
# =============================================================================

def construire_guides_roulement_aiguille_arbre(
    g: Dict[str, Any],
) -> Dict[str, pv.PolyData]:
    guides: Dict[str, pv.PolyData] = {}

    B = g["B_largeur_m"]
    d_int = g["d_interieur_m"]
    D_ext = g["D_exterieur_m"]

    z_min = -0.5 * B
    z_max = 0.5 * B

    guides["axe"] = pv.Line(
        pointa=(0.0, 0.0, z_min - 0.20 * B),
        pointb=(0.0, 0.0, z_max + 0.20 * B),
        resolution=1,
    )

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

    return guides


# =============================================================================
# Affichage
# =============================================================================

def afficher_roulement_aiguille_arbre_3d(
    source: RoulementAiguilleArbre | Dict[str, Any],
    *,
    type_portee: Optional[str] = None,
    afficher_axes: bool = True,
    afficher_guides: bool = True,
    afficher_bords: bool = False,
    couleur_portee: str = "dimgray",
    couleur_bague_exterieure: str = "gainsboro",
    couleur_enveloppe_inconnue: str = "lightsteelblue",
) -> Tuple[Dict[str, pv.PolyData], Dict[str, Any]]:
    if isinstance(source, RoulementAiguilleArbre):
        rapport = source.analyser(strict=False)
    elif isinstance(source, dict):
        rapport = source
    else:
        raise TypeError("source doit être un RoulementAiguilleArbre ou un dict rapport.")

    meshes, geom = construire_roulement_aiguille_arbre_3d(
        rapport,
        type_portee=type_portee,
    )

    plotter = pv.Plotter(window_size=(1400, 900))
    plotter.set_background("#1e1e1e")

    if "portee_interieure_reference" in meshes:
        plotter.add_mesh(
            meshes["portee_interieure_reference"],
            color=couleur_portee,
            smooth_shading=True,
            opacity=0.35,
            show_edges=False,
        )

    if "bague_exterieure" in meshes:
        plotter.add_mesh(
            meshes["bague_exterieure"],
            color=couleur_bague_exterieure,
            smooth_shading=True,
            opacity=0.82,
            show_edges=afficher_bords,
            specular=0.25,
            specular_power=18,
        )

    if "enveloppe_inconnue" in meshes:
        plotter.add_mesh(
            meshes["enveloppe_inconnue"],
            color=couleur_enveloppe_inconnue,
            smooth_shading=True,
            opacity=0.22,
            show_edges=afficher_bords,
        )

    if afficher_guides:
        guides = construire_guides_roulement_aiguille_arbre(geom)

        if "axe" in guides:
            plotter.add_mesh(guides["axe"], color="white", line_width=2)
        if "cercle_d_interieur" in guides:
            plotter.add_mesh(guides["cercle_d_interieur"], color="cyan", line_width=2)
        if "cercle_D_exterieur" in guides:
            plotter.add_mesh(guides["cercle_D_exterieur"], color="yellow", line_width=2)

    if afficher_axes:
        plotter.add_axes()
        plotter.show_grid(color="gray")

    titre = "Roulement à aiguilles — arbre/vilebrequin"
    if geom.get("type_portee") is not None:
        titre += f" ({geom['type_portee']})"
    plotter.add_text(titre, font_size=12)

    plotter.view_isometric()
    plotter.show()

    return meshes, rapport


# =============================================================================
# Exemple
# =============================================================================

if __name__ == "__main__":
    r = RoulementAiguilleArbre(
        type_portee="maneton",
        rpm=3000.0,
        couple_max_Nm=45.0,
        rayon_manivelle_m=0.03,
        force_radiale_equivalente_N=6000.0,
        duree_vie_cible_h=4000.0,
        exposant_vie_p=10.0 / 3.0,
    )

    afficher_roulement_aiguille_arbre_3d(r, type_portee="maneton")
