# frontend/pieces/sketches_2d/cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D

# Import du backend
from backend.pieces.cylindre import Cylindre


# ============================================================
# Outils
# ============================================================

def _mm(x_m: float) -> float:
    return float(x_m) * 1000.0


def _get_nested(d: Dict[str, Any], *keys: str, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _add_dimension_h(
    ax,
    x1: float,
    x2: float,
    y: float,
    text: str,
    offset_text: float = 4.0,
    color: str = "black",
):
    """
    Cote horizontale simple.
    Coordonnées en mm.
    """
    ax.add_line(Line2D([x1, x1], [0, y], linestyle="--", linewidth=0.8, color=color))
    ax.add_line(Line2D([x2, x2], [0, y], linestyle="--", linewidth=0.8, color=color))
    ax.annotate(
        "",
        xy=(x1, y),
        xytext=(x2, y),
        arrowprops=dict(arrowstyle="<->", linewidth=1.0, color=color),
    )
    ax.text((x1 + x2) / 2.0, y + offset_text, text, ha="center", va="bottom", color=color)


def _add_dimension_v(
    ax,
    x: float,
    y1: float,
    y2: float,
    text: str,
    offset_text: float = 4.0,
    color: str = "black",
):
    """
    Cote verticale simple.
    Coordonnées en mm.
    """
    ax.add_line(Line2D([0, x], [y1, y1], linestyle="--", linewidth=0.8, color=color))
    ax.add_line(Line2D([0, x], [y2, y2], linestyle="--", linewidth=0.8, color=color))
    ax.annotate(
        "",
        xy=(x, y1),
        xytext=(x, y2),
        arrowprops=dict(arrowstyle="<->", linewidth=1.0, color=color),
    )
    ax.text(x + offset_text, (y1 + y2) / 2.0, text, ha="left", va="center", color=color, rotation=90)


# ============================================================
# Extraction des données calculées
# ============================================================

@dataclass
class DonneesCroquisCylindre:
    alesage_mm: float
    diametre_exterieur_mm: float
    epaisseur_mm: float
    longueur_utile_mm: float
    longueur_totale_mm: float

    bride_epaisseur_mm: float = 0.0
    bride_largeur_radiale_mm: float = 0.0
    bride_diametre_exterieur_mm: float = 0.0

    nb_trous: int = 0
    diametre_trou_mm: float = 0.0
    diametre_cercle_percage_mm: float = 0.0
    angles_deg: Optional[List[float]] = None

    gorge_largeur_mm: float = 0.0
    gorge_profondeur_mm: float = 0.0

    chanfrein_entree_piston_mm: float = 0.0
    rayon_conge_mm: float = 0.0

    force_pression_max_N: float = 0.0
    force_separation_N: float = 0.0

    source_rapport: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(cylindre: Cylindre) -> DonneesCroquisCylindre:
    rapport = cylindre.analyser(strict=False)

    geo = rapport.get("geometrie", {})
    dim = rapport.get("dimensionnement", {})
    ass = rapport.get("assemblage", {})

    alesage_m = _get_nested(rapport, "entrees", "alesage_m", default=0.0)
    longueur_utile_m = _get_nested(rapport, "entrees", "longueur_utile_m", default=0.0)

    diametre_exterieur_m = _get_nested(geo, "diametre_externe_m", default=0.0)
    epaisseur_m = _get_nested(dim, "epaisseur_retenue_m", default=0.0)

    cao = _get_nested(geo, "cao", default={}) or {}
    bride = cao.get("bride", {}) if isinstance(cao, dict) else {}
    gorge = cao.get("gorge_joint", {}) if isinstance(cao, dict) else {}

    longueur_totale_m = (
        _get_nested(geo, "longueur_totale_avec_brides_m", default=None)
        or _get_nested(cao, "longueur_totale_nominale_m", default=None)
        or longueur_utile_m
    )

    return DonneesCroquisCylindre(
        alesage_mm=_mm(alesage_m),
        diametre_exterieur_mm=_mm(diametre_exterieur_m),
        epaisseur_mm=_mm(epaisseur_m),
        longueur_utile_mm=_mm(longueur_utile_m),
        longueur_totale_mm=_mm(longueur_totale_m),

        bride_epaisseur_mm=_mm(_get_nested(bride, "epaisseur_bride_m", default=0.0)),
        bride_largeur_radiale_mm=_mm(_get_nested(bride, "largeur_bride_m", default=0.0)),
        bride_diametre_exterieur_mm=_mm(_get_nested(bride, "diametre_bride_externe_m", default=0.0)),

        nb_trous=int(_get_nested(bride, "nb_trous", default=0)),
        diametre_trou_mm=_mm(_get_nested(bride, "diametre_trou_m", default=0.0)),
        diametre_cercle_percage_mm=_mm(_get_nested(bride, "diametre_cercle_percage_m", default=0.0)),
        angles_deg=_get_nested(bride, "angles_deg", default=[]),

        gorge_largeur_mm=_mm(_get_nested(gorge, "largeur_gorge_m", default=0.0)),
        gorge_profondeur_mm=_mm(_get_nested(gorge, "profondeur_gorge_m", default=0.0)),

        chanfrein_entree_piston_mm=_mm(_get_nested(cao, "chanfrein_entree_piston_m", default=0.0)),
        rayon_conge_mm=_mm(_get_nested(cao, "rayon_conge_m", default=0.0)),

        force_pression_max_N=_safe_float(_get_nested(dim, "force_pression_piston_max_N", default=0.0)),
        force_separation_N=_safe_float(_get_nested(ass, "force_separation_N", default=0.0)),

        source_rapport=rapport,
    )


# ============================================================
# Tracé 2D
# ============================================================

def tracer_croquis_cylindre_2d(
    cylindre: Cylindre,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D - Cylindre",
):
    """
    Trace un croquis 2D à partir des données calculées par Cylindre.analyser().

    Vue de gauche : coupe longitudinale simplifiée
    Vue de droite : face avant simplifiée avec perçages
    """
    d = extraire_donnees_croquis(cylindre)

    if d.alesage_mm <= 0 or d.longueur_utile_mm <= 0:
        raise ValueError("Impossible de tracer le croquis : dimensions principales invalides.")

    fig, (ax_side, ax_front) = plt.subplots(
        1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [2.2, 1.2]}
    )
    fig.suptitle(titre, fontsize=14)

    # ------------------------------------------------------------
    # VUE DE CÔTÉ
    # ------------------------------------------------------------
    L_util = d.longueur_utile_mm
    L_tot = d.longueur_totale_mm
    D_int = d.alesage_mm
    D_ext = d.diametre_exterieur_mm
    D_bride = d.bride_diametre_exterieur_mm if d.bride_diametre_exterieur_mm > 0 else D_ext
    e_bride = d.bride_epaisseur_mm

    y_int = D_int / 2.0
    y_ext = D_ext / 2.0
    y_bride = D_bride / 2.0

    # Origine vue côté
    x0 = 0.0
    x1 = e_bride
    x2 = x1 + L_util
    x3 = x2 + e_bride if e_bride > 0 else L_tot

    if e_bride > 0:
        # Brides externes
        ax_side.add_patch(Rectangle((x0, -y_bride), e_bride, D_bride, fill=False, linewidth=1.5))
        ax_side.add_patch(Rectangle((x2, -y_bride), e_bride, D_bride, fill=False, linewidth=1.5))

        # Fût externe
        ax_side.add_patch(Rectangle((x1, -y_ext), L_util, D_ext, fill=False, linewidth=1.8))

        # Alésage interne
        ax_side.add_patch(Rectangle((x1, -y_int), L_util, D_int, fill=False, linewidth=1.2))

        # Liaisons visuelles bride/fût
        ax_side.add_line(Line2D([x1, x1], [-y_bride, -y_ext], linewidth=1.2))
        ax_side.add_line(Line2D([x1, x1], [y_ext, y_bride], linewidth=1.2))
        ax_side.add_line(Line2D([x2, x2], [-y_bride, -y_ext], linewidth=1.2))
        ax_side.add_line(Line2D([x2, x2], [y_ext, y_bride], linewidth=1.2))
    else:
        # Version simple sans brides
        ax_side.add_patch(Rectangle((x0, -y_ext), L_util, D_ext, fill=False, linewidth=1.8))
        ax_side.add_patch(Rectangle((x0, -y_int), L_util, D_int, fill=False, linewidth=1.2))
        x1 = 0.0
        x2 = L_util
        x3 = L_util

    # Axe
    ax_side.axhline(0, linestyle="--", linewidth=0.8)

    # Gorge de joint simplifiée sur bride avant si disponible
    if d.gorge_largeur_mm > 0 and d.gorge_profondeur_mm > 0 and e_bride > 0:
        gorge_x = x0 + 0.55 * e_bride
        gorge_y = y_int + d.gorge_profondeur_mm
        ax_side.add_patch(
            Rectangle(
                (gorge_x, y_int),
                d.gorge_largeur_mm,
                d.gorge_profondeur_mm,
                fill=False,
                linewidth=1.0,
                linestyle="--",
            )
        )
        ax_side.add_patch(
            Rectangle(
                (gorge_x, -(y_int + d.gorge_profondeur_mm)),
                d.gorge_largeur_mm,
                d.gorge_profondeur_mm,
                fill=False,
                linewidth=1.0,
                linestyle="--",
            )
        )

    # Cotes
    cote_y_1 = y_bride + 15.0
    cote_y_2 = y_bride + 30.0
    cote_y_3 = y_bride + 45.0

    _add_dimension_h(ax_side, x1, x2, cote_y_1, f"L utile = {L_util:.2f} mm")
    _add_dimension_h(ax_side, x0, x3, cote_y_2, f"L totale = {L_tot:.2f} mm")

    if e_bride > 0:
        _add_dimension_h(ax_side, x0, x1, cote_y_3, f"e bride = {e_bride:.2f} mm")

    cote_x_1 = x3 + 20.0
    cote_x_2 = x3 + 40.0
    cote_x_3 = x3 + 60.0

    _add_dimension_v(ax_side, cote_x_1, -y_int, y_int, f"Ø alésage = {D_int:.2f} mm")
    _add_dimension_v(ax_side, cote_x_2, -y_ext, y_ext, f"Ø ext = {D_ext:.2f} mm")
    if D_bride > D_ext:
        _add_dimension_v(ax_side, cote_x_3, -y_bride, y_bride, f"Ø bride = {D_bride:.2f} mm")

    # Texte complémentaire
    infos = [
        f"Épaisseur paroi: {d.epaisseur_mm:.2f} mm",
    ]
    if d.gorge_largeur_mm > 0:
        infos.append(f"Gorge joint: {d.gorge_largeur_mm:.2f} x {d.gorge_profondeur_mm:.2f} mm")
    if d.chanfrein_entree_piston_mm > 0:
        infos.append(f"Chanfrein entrée piston: {d.chanfrein_entree_piston_mm:.2f} mm")
    if d.force_pression_max_N > 0:
        infos.append(f"Force pression max: {d.force_pression_max_N:.2f} N")
    if d.force_separation_N > 0:
        infos.append(f"Force séparation: {d.force_separation_N:.2f} N")

    ax_side.text(
        x0,
        -y_bride - 35.0,
        "\n".join(infos),
        ha="left",
        va="top",
        fontsize=9,
    )

    ax_side.set_title("Vue de côté")
    ax_side.set_aspect("equal", adjustable="box")
    ax_side.set_xlim(-10, max(x3 + 90.0, L_tot + 90.0))
    ax_side.set_ylim(-(y_bride + 60.0), y_bride + 60.0)
    ax_side.grid(True, linestyle=":", linewidth=0.5)
    ax_side.set_xlabel("x [mm]")
    ax_side.set_ylabel("y [mm]")

    # ------------------------------------------------------------
    # VUE DE FACE
    # ------------------------------------------------------------
    R_bride = D_bride / 2.0
    R_ext = D_ext / 2.0
    R_int = D_int / 2.0

    # Cercles principaux
    ax_front.add_patch(Circle((0, 0), R_bride, fill=False, linewidth=1.5))
    ax_front.add_patch(Circle((0, 0), R_ext, fill=False, linewidth=1.2))
    ax_front.add_patch(Circle((0, 0), R_int, fill=False, linewidth=1.2))

    # Cercle de perçage
    if d.diametre_cercle_percage_mm > 0:
        R_pcd = d.diametre_cercle_percage_mm / 2.0
        ax_front.add_patch(Circle((0, 0), R_pcd, fill=False, linewidth=1.0, linestyle="--"))

        if d.nb_trous > 0 and d.diametre_trou_mm > 0:
            angles = d.angles_deg or [i * (360.0 / d.nb_trous) for i in range(d.nb_trous)]
            r_trou = d.diametre_trou_mm / 2.0
            for ang_deg in angles:
                a = math.radians(float(ang_deg))
                x = R_pcd * math.cos(a)
                y = R_pcd * math.sin(a)
                ax_front.add_patch(Circle((x, y), r_trou, fill=False, linewidth=1.0))

    # Axes
    ax_front.axhline(0, linestyle="--", linewidth=0.8)
    ax_front.axvline(0, linestyle="--", linewidth=0.8)

    # Annotations
    txt = [
        f"Ø bride = {D_bride:.2f} mm",
        f"Ø ext = {D_ext:.2f} mm",
        f"Ø alésage = {D_int:.2f} mm",
    ]
    if d.nb_trous > 0:
        txt.append(f"{d.nb_trous} trous Ø {d.diametre_trou_mm:.2f} mm")
    if d.diametre_cercle_percage_mm > 0:
        txt.append(f"PCD = {d.diametre_cercle_percage_mm:.2f} mm")

    ax_front.text(
        -R_bride,
        -R_bride - 18.0,
        "\n".join(txt),
        ha="left",
        va="top",
        fontsize=9,
    )

    ax_front.set_title("Vue de face")
    ax_front.set_aspect("equal", adjustable="box")
    lim = max(R_bride, R_ext, R_int) + 30.0
    ax_front.set_xlim(-lim, lim)
    ax_front.set_ylim(-lim, lim)
    ax_front.grid(True, linestyle=":", linewidth=0.5)
    ax_front.set_xlabel("x [mm]")
    ax_front.set_ylabel("y [mm]")

    plt.tight_layout()

    if enregistrer:
        plt.savefig(enregistrer, dpi=200, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, (ax_side, ax_front), d


# ============================================================
# Exemple d'utilisation
# ============================================================

if __name__ == "__main__":
    from backend.pieces.cylindre import (
        ReglesJointTorique,
        ReglesVisserieBride,
        ReglesFabricationCylindre,
    )

    cyl = Cylindre(
        alesage_m=0.080,
        course_m=0.090,
        longueur_utile_m=0.120,
        pression_service_pa=2.5e6,
        pression_max_pa=4.0e6,
        pression_externe_pa=1.0e5,
        materiau_cle="acier_s355",
        facteur_securite=2.0,

        # Pour obtenir la fermeture complète :
        regles_joint_torique=ReglesJointTorique(
            diametre_tore_m=0.003,
            taux_ecrasement_cible=0.20,
            coefficient_largeur_gorge=1.15,
            coefficient_force_contact_lineique_n_m=12000.0,
            position_axiale="double",
        ),
        regles_visserie=ReglesVisserieBride(),
        regles_fabrication=ReglesFabricationCylindre(),
    )

    tracer_croquis_cylindre_2d(
        cyl,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D - Cylindre calculé",
    )