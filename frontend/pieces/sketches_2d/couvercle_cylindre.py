# frontend/pieces/sketches_2d/couvercle_cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle, Polygon


from backend.pieces.couvercle_cylindre import CouvercleCylindre


# ============================================================
# OUTILS GÉNÉRAUX
# ============================================================

def _mm(x_m: Optional[float]) -> float:
    if x_m is None:
        return 0.0
    return float(x_m) * 1000.0


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def _get_nested(d: Dict[str, Any], *keys: str, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _fmt_mm(v: float) -> str:
    return f"{v:.2f} mm"


def _fmt_n(v: float) -> str:
    return f"{v:.2f} N"


def _fmt_nm(v: float) -> str:
    return f"{v:.2f} N·m"


def _linestyle_axe():
    return dict(linestyle=(0, (8, 4, 2, 4)), linewidth=0.9, color="black")


def _linestyle_hidden():
    return dict(linestyle=(0, (4, 4)), linewidth=0.8, color="black")


def _linestyle_dimension():
    return dict(linewidth=1.0, color="black")


# ============================================================
# COTATION / ANNOTATION
# ============================================================

def _draw_extension_line(ax, x1: float, y1: float, x2: float, y2: float):
    ax.add_line(Line2D([x1, x2], [y1, y2], linestyle="--", linewidth=0.75, color="black"))


def _add_dimension_h(
    ax,
    x1: float,
    x2: float,
    y_ref_low: float,
    y_dim: float,
    text: str,
    text_offset: float = 4.0,
):
    _draw_extension_line(ax, x1, y_ref_low, x1, y_dim)
    _draw_extension_line(ax, x2, y_ref_low, x2, y_dim)
    ax.annotate(
        "",
        xy=(x1, y_dim),
        xytext=(x2, y_dim),
        arrowprops=dict(arrowstyle="<->", **_linestyle_dimension()),
    )
    ax.text((x1 + x2) / 2.0, y_dim + text_offset, text, ha="center", va="bottom", fontsize=9)


def _add_dimension_v(
    ax,
    x_ref_left: float,
    x_dim: float,
    y1: float,
    y2: float,
    text: str,
    text_offset: float = 4.0,
):
    _draw_extension_line(ax, x_ref_left, y1, x_dim, y1)
    _draw_extension_line(ax, x_ref_left, y2, x_dim, y2)
    ax.annotate(
        "",
        xy=(x_dim, y1),
        xytext=(x_dim, y2),
        arrowprops=dict(arrowstyle="<->", **_linestyle_dimension()),
    )
    ax.text(x_dim + text_offset, (y1 + y2) / 2.0, text, ha="left", va="center", rotation=90, fontsize=9)


def _add_note(ax, x: float, y: float, title: str, lines: List[str], fontsize: int = 9):
    text = title
    if lines:
        text += "\n" + "\n".join(lines)
    ax.text(
        x,
        y,
        text,
        ha="left",
        va="top",
        fontsize=fontsize,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="black", linewidth=0.8),
    )


def _annotate_leader(ax, x_text: float, y_text: float, x_target: float, y_target: float, text: str):
    ax.annotate(
        text,
        xy=(x_target, y_target),
        xytext=(x_text, y_text),
        textcoords="data",
        ha="left",
        va="center",
        fontsize=9,
        arrowprops=dict(arrowstyle="->", linewidth=0.9, color="black"),
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.6),
    )


# ============================================================
# HACHURES DE COUPE
# ============================================================

def _make_closed_section_polygon(
    xs_outer: List[float],
    ys_outer: List[float],
    xs_inner: List[float],
    ys_inner: List[float],
) -> List[Tuple[float, float]]:
    """
    Construit un polygone fermé représentant la matière de la calotte en coupe.
    """
    if not xs_outer or not ys_outer or not xs_inner or not ys_inner:
        return []

    outer = list(zip(xs_outer, ys_outer))
    inner = list(zip(reversed(xs_inner), reversed(ys_inner)))
    return outer + inner


def _add_hatched_polygon(ax, pts: List[Tuple[float, float]], hatch: str = "////"):
    if not pts:
        return
    poly = Polygon(
        pts,
        closed=True,
        fill=True,
        facecolor="white",
        edgecolor="black",
        linewidth=0.9,
        hatch=hatch,
        zorder=0,
    )
    ax.add_patch(poly)


# ============================================================
# PROFIL CALOTTE SPHÉRIQUE
# ============================================================

def _build_cap_profile(
    a_mm: float,
    h_mm: float,
    R_int_mm: float,
    e_mm: float,
    n: int = 400,
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """
    Profil de la calotte en coupe méridienne.
    Convention :
    - le plan de base de la calotte est x = 0
    - la calotte bombe vers +x
    - l'axe de révolution est y = 0

    Renvoie :
    - intérieur : (xs_int, ys_int)
    - extérieur : (xs_ext, ys_ext)
    sur l'intervalle y ∈ [-a, +a]
    """
    if a_mm <= 0 or h_mm <= 0 or R_int_mm <= 0 or e_mm <= 0:
        raise ValueError("Paramètres géométriques invalides pour la calotte.")

    # Pour une calotte sphérique :
    # h = R - sqrt(R^2 - a^2)
    # donc le centre est à x_c = h - R
    x_center = h_mm - R_int_mm

    xs_int: List[float] = []
    ys_int: List[float] = []
    for i in range(n + 1):
        y = -a_mm + (2.0 * a_mm * i / n)
        val = R_int_mm ** 2 - y ** 2
        if val < 0:
            continue
        x = x_center + math.sqrt(val)
        xs_int.append(x)
        ys_int.append(y)

    R_ext_mm = R_int_mm + e_mm
    xs_ext: List[float] = []
    ys_ext: List[float] = []
    for i in range(n + 1):
        y = -a_mm + (2.0 * a_mm * i / n)
        val = R_ext_mm ** 2 - y ** 2
        if val < 0:
            continue
        x = x_center + math.sqrt(val)
        xs_ext.append(x)
        ys_ext.append(y)

    return xs_int, ys_int, xs_ext, ys_ext


# ============================================================
# DONNÉES EXTRAITES DU RAPPORT
# ============================================================

@dataclass
class DonneesCroquisCouvercle:
    # géométrie principale
    diametre_ouverture_mm: float
    rayon_base_calotte_mm: float
    hauteur_bombe_mm: float
    rayon_courbure_interieur_mm: float
    rayon_courbure_exterieur_mm: float
    epaisseur_calotte_mm: float

    # bride
    rayon_bride_interne_mm: float = 0.0
    rayon_bride_externe_mm: float = 0.0
    diametre_bride_externe_mm: float = 0.0
    epaisseur_bride_mm: float = 0.0
    largeur_bride_mm: float = 0.0

    # assemblage
    nb_trous: int = 0
    diametre_trou_mm: float = 0.0
    diametre_cercle_percage_mm: float = 0.0
    angles_trous_deg: Optional[List[float]] = None

    force_separation_N: float = 0.0
    force_joint_N: float = 0.0
    force_precharge_totale_N: float = 0.0
    force_precharge_par_vis_N: float = 0.0
    couple_serrage_par_vis_Nm: float = 0.0

    # fabrication / finition
    chanfrein_mm: float = 0.0
    conge_mm: float = 0.0

    # divers
    filetage_txt: str = ""
    source_forme: str = ""
    masse_kg: float = 0.0
    volume_total_m3: float = 0.0

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(couvercle: CouvercleCylindre) -> DonneesCroquisCouvercle:
    rapport = couvercle.analyser(strict=False)

    geo = rapport.get("geometrie", {})
    cao = geo.get("cao", {}) if isinstance(geo.get("cao"), dict) else {}
    calotte = geo.get("calotte", {}) if isinstance(geo.get("calotte"), dict) else {}
    bride = geo.get("bride", {}) if isinstance(geo.get("bride"), dict) else {}
    assemblage = rapport.get("assemblage", {}) if isinstance(rapport.get("assemblage"), dict) else {}
    dim = rapport.get("dimensionnement", {}) if isinstance(rapport.get("dimensionnement"), dict) else {}
    masse = rapport.get("masse", {}) if isinstance(rapport.get("masse"), dict) else {}

    bride_cao = cao.get("bride", {}) if isinstance(cao.get("bride"), dict) else {}
    assemblage_cao = cao.get("assemblage", {}) if isinstance(cao.get("assemblage"), dict) else {}
    filetage = assemblage.get("filetage", {}) if isinstance(assemblage.get("filetage"), dict) else {}

    rayon_bride_interne_m = (
        _get_nested(bride_cao, "rayon_bride_interne_m", default=None)
        or _get_nested(bride, "rayon_bride_interne_m", default=0.0)
    )
    rayon_bride_externe_m = (
        _get_nested(bride_cao, "rayon_bride_externe_m", default=None)
        or _get_nested(bride, "rayon_bride_externe_m", default=0.0)
    )
    diametre_bride_externe_m = (
        _get_nested(bride_cao, "diametre_bride_externe_m", default=None)
        or _get_nested(bride, "diametre_bride_externe_m", default=0.0)
    )
    epaisseur_bride_m = (
        _get_nested(bride_cao, "epaisseur_bride_m", default=None)
        or _get_nested(bride, "epaisseur_bride_m", default=0.0)
    )
    largeur_bride_m = (
        _get_nested(bride_cao, "largeur_bride_m", default=None)
        or _get_nested(bride, "largeur_bride_m", default=0.0)
    )

    return DonneesCroquisCouvercle(
        diametre_ouverture_mm=_mm(_get_nested(cao, "diametre_ouverture_m", default=0.0)),
        rayon_base_calotte_mm=_mm(
            _get_nested(cao, "rayon_base_calotte_m", default=None)
            or _get_nested(calotte, "a_m", default=0.0)
        ),
        hauteur_bombe_mm=_mm(
            _get_nested(cao, "hauteur_bombe_interieure_m", default=None)
            or _get_nested(calotte, "h_m", default=0.0)
        ),
        rayon_courbure_interieur_mm=_mm(
            _get_nested(cao, "rayon_courbure_interieur_m", default=None)
            or _get_nested(calotte, "R_m", default=0.0)
        ),
        rayon_courbure_exterieur_mm=_mm(_get_nested(cao, "rayon_courbure_exterieur_m", default=0.0)),
        epaisseur_calotte_mm=_mm(_get_nested(cao, "epaisseur_calotte_m", default=0.0)),

        rayon_bride_interne_mm=_mm(rayon_bride_interne_m),
        rayon_bride_externe_mm=_mm(rayon_bride_externe_m),
        diametre_bride_externe_mm=_mm(diametre_bride_externe_m),
        epaisseur_bride_mm=_mm(epaisseur_bride_m),
        largeur_bride_mm=_mm(largeur_bride_m),

        nb_trous=int(_get_nested(assemblage, "nb_vis", default=0) or 0),
        diametre_trou_mm=_mm(_get_nested(assemblage, "diametre_trou_m", default=0.0)),
        diametre_cercle_percage_mm=_mm(_get_nested(assemblage, "diametre_cercle_percage_m", default=0.0)),
        angles_trous_deg=_get_nested(assemblage, "angles_trous_deg", default=[]),

        force_separation_N=_safe_float(_get_nested(assemblage, "force_separation_N", default=0.0)),
        force_joint_N=_safe_float(_get_nested(assemblage, "force_joint_N", default=0.0)),
        force_precharge_totale_N=_safe_float(_get_nested(assemblage, "force_precharge_totale_N", default=0.0)),
        force_precharge_par_vis_N=_safe_float(_get_nested(assemblage, "force_precharge_par_vis_N", default=0.0)),
        couple_serrage_par_vis_Nm=_safe_float(_get_nested(assemblage, "couple_serrage_par_vis_Nm", default=0.0)),

        chanfrein_mm=_mm(_get_nested(cao, "chanfrein_m", default=0.0)),
        conge_mm=_mm(_get_nested(cao, "conge_m", default=0.0)),

        filetage_txt=str(_get_nested(filetage, "taraudage", default="") or ""),
        source_forme=str(_get_nested(dim, "source_forme_calotte", default="") or ""),
        masse_kg=_safe_float(_get_nested(masse, "masse_kg", default=0.0)),
        volume_total_m3=_safe_float(_get_nested(masse, "volume_total_m3", default=0.0)),
        rapport_complet=rapport,
    )


# ============================================================
# TRACÉ VUE DE CÔTÉ
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisCouvercle):
    a = d.rayon_base_calotte_mm
    h = d.hauteur_bombe_mm
    R_int = d.rayon_courbure_interieur_mm
    e = d.epaisseur_calotte_mm

    R_ouv = d.diametre_ouverture_mm / 2.0

    e_bride = d.epaisseur_bride_mm
    R_bi = d.rayon_bride_interne_mm if d.rayon_bride_interne_mm > 0 else a
    R_be = d.rayon_bride_externe_mm if d.rayon_bride_externe_mm > 0 else max(a, d.diametre_bride_externe_mm / 2.0)
    D_bride = d.diametre_bride_externe_mm if d.diametre_bride_externe_mm > 0 else 2.0 * R_be

    xs_int, ys_int, xs_ext, ys_ext = _build_cap_profile(
        a_mm=a,
        h_mm=h,
        R_int_mm=R_int,
        e_mm=e,
        n=400,
    )

    # Hachure matière calotte
    pts_hatch = _make_closed_section_polygon(xs_ext, ys_ext, xs_int, ys_int)
    _add_hatched_polygon(ax, pts_hatch, hatch="////")

    # Bride hachurée
    if e_bride > 0 and R_be > R_bi > 0:
        rect_top = Rectangle(
            (-e_bride, R_bi),
            e_bride,
            R_be - R_bi,
            fill=True,
            facecolor="white",
            edgecolor="black",
            linewidth=0.9,
            hatch="////",
            zorder=0,
        )
        rect_bot = Rectangle(
            (-e_bride, -R_be),
            e_bride,
            R_be - R_bi,
            fill=True,
            facecolor="white",
            edgecolor="black",
            linewidth=0.9,
            hatch="////",
            zorder=0,
        )
        ax.add_patch(rect_top)
        ax.add_patch(rect_bot)

    # Contours
    ax.plot(xs_ext, ys_ext, color="black", linewidth=1.6)
    ax.plot(xs_int, ys_int, color="black", linewidth=1.2)

    # Plan de base et axe
    ax.add_line(Line2D([0, 0], [-R_be, R_be], **_linestyle_hidden()))
    ax.axhline(0, **_linestyle_axe())

    # Bride complète
    if e_bride > 0:
        ax.add_line(Line2D([-e_bride, -e_bride], [-R_be, -R_bi], color="black", linewidth=1.3))
        ax.add_line(Line2D([-e_bride, -e_bride], [R_bi, R_be], color="black", linewidth=1.3))
        ax.add_line(Line2D([-e_bride, 0], [-R_be, -R_be], color="black", linewidth=1.3))
        ax.add_line(Line2D([-e_bride, 0], [R_be, R_be], color="black", linewidth=1.3))
        ax.add_line(Line2D([-e_bride, 0], [-R_bi, -R_bi], color="black", linewidth=1.1))
        ax.add_line(Line2D([-e_bride, 0], [R_bi, R_bi], color="black", linewidth=1.1))

    # Ligne de diamètre d'ouverture
    ax.add_line(Line2D([0, 0], [-R_ouv, R_ouv], **_linestyle_hidden()))

    # Annotations locales
    _annotate_leader(ax, h * 0.55, a + 20.0, xs_ext[-1], 0.0, "Sommet calotte")
    _annotate_leader(ax, max(h * 0.25, 15.0), -a - 25.0, xs_int[len(xs_int)//2], ys_int[len(ys_int)//2], "Paroi intérieure")
    _annotate_leader(ax, max(h * 0.35, 25.0), a + 38.0, xs_ext[len(xs_ext)//2], ys_ext[len(ys_ext)//2], "Paroi extérieure")

    if e_bride > 0:
        _annotate_leader(ax, -e_bride - 55.0, R_be + 18.0, -e_bride / 2.0, R_be - 0.15 * (R_be - R_bi), "Bride")
        _annotate_leader(ax, -e_bride - 55.0, -R_be - 18.0, -e_bride / 2.0, -R_be + 0.15 * (R_be - R_bi), "Bride")

    # Cotes horizontales
    y_dim_base = R_be + 18.0
    _add_dimension_h(ax, 0.0, h, 0.0, y_dim_base, f"h bombe = {_fmt_mm(h)}")

    if e_bride > 0:
        _add_dimension_h(ax, -e_bride, 0.0, 0.0, y_dim_base + 16.0, f"e bride = {_fmt_mm(e_bride)}")

    # Cotes verticales
    x_dim_base = h + 28.0
    _add_dimension_v(ax, 0.0, x_dim_base, -R_ouv, R_ouv, f"Ø ouverture = {_fmt_mm(2.0 * R_ouv)}")
    _add_dimension_v(ax, 0.0, x_dim_base + 18.0, -a, a, f"Ø base calotte = {_fmt_mm(2.0 * a)}")

    if D_bride > 0:
        _add_dimension_v(ax, 0.0, x_dim_base + 36.0, -R_be, R_be, f"Ø bride = {_fmt_mm(D_bride)}")

    # Épaisseur via flèche locale
    if len(xs_int) > 200 and len(xs_ext) > 200:
        idx = len(xs_int) // 2
        xi, yi = xs_int[idx], ys_int[idx]
        xo, yo = xs_ext[idx], ys_ext[idx]
        ax.annotate(
            "",
            xy=(xi, yi),
            xytext=(xo, yo),
            arrowprops=dict(arrowstyle="<->", linewidth=1.0, color="black"),
        )
        ax.text((xi + xo) / 2.0 + 3.0, (yi + yo) / 2.0 + 3.0, f"e = {_fmt_mm(e)}", fontsize=9)

    # Rayons de courbure
    ax.text(h * 0.35, 8.0, f"Rint = {_fmt_mm(R_int)}", fontsize=9)
    if d.rayon_courbure_exterieur_mm > 0:
        ax.text(h * 0.35, -18.0, f"Rext = {_fmt_mm(d.rayon_courbure_exterieur_mm)}", fontsize=9)

    ax.set_title("Vue de côté en coupe")
    ax.set_aspect("equal", adjustable="box")

    x_min = -max(e_bride + 75.0, 90.0)
    x_max = max(h + 110.0, 140.0)
    y_lim = max(R_be, a) + 70.0

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-y_lim, y_lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# TRACÉ VUE DE FACE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisCouvercle):
    R_ouv = d.diametre_ouverture_mm / 2.0
    a = d.rayon_base_calotte_mm
    R_be = d.rayon_bride_externe_mm if d.rayon_bride_externe_mm > 0 else max(a, d.diametre_bride_externe_mm / 2.0)

    # Cercles principaux
    ax.add_patch(Circle((0, 0), R_be, fill=False, linewidth=1.5, edgecolor="black"))
    ax.add_patch(Circle((0, 0), a, fill=False, linewidth=1.2, edgecolor="black"))
    ax.add_patch(Circle((0, 0), R_ouv, fill=False, linewidth=1.2, edgecolor="black"))

    # Cercle de perçage
    if d.diametre_cercle_percage_mm > 0:
        R_pcd = d.diametre_cercle_percage_mm / 2.0
        ax.add_patch(Circle((0, 0), R_pcd, fill=False, linewidth=0.9, edgecolor="black", linestyle=(0, (5, 5))))

        # Trous
        if d.nb_trous > 0 and d.diametre_trou_mm > 0:
            r_trou = d.diametre_trou_mm / 2.0
            angles = d.angles_trous_deg or [i * (360.0 / d.nb_trous) for i in range(d.nb_trous)]

            for i, ang_deg in enumerate(angles):
                a_rad = math.radians(float(ang_deg))
                x = R_pcd * math.cos(a_rad)
                y = R_pcd * math.sin(a_rad)

                ax.add_patch(Circle((x, y), r_trou, fill=False, linewidth=1.0, edgecolor="black"))

                # petit repère de numérotation
                ax.text(
                    x + r_trou + 2.0,
                    y + r_trou + 2.0,
                    str(i + 1),
                    fontsize=7,
                    ha="left",
                    va="bottom",
                )

    # Axes de symétrie
    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    # Annotations radiales principales
    ax.text(6.0, 6.0, "Axe", fontsize=9)
    ax.text(R_ouv * 0.25, -10.0, f"Ø ouv. = {_fmt_mm(2.0 * R_ouv)}", fontsize=9)
    ax.text(a * 0.32, -22.0, f"Ø base = {_fmt_mm(2.0 * a)}", fontsize=9)
    if R_be > 0:
        ax.text(R_be * 0.28, -34.0, f"Ø bride = {_fmt_mm(2.0 * R_be)}", fontsize=9)

    if d.diametre_cercle_percage_mm > 0:
        ax.text(
            -R_be,
            -R_be - 15.0,
            f"PCD = {_fmt_mm(d.diametre_cercle_percage_mm)}",
            fontsize=9,
            ha="left",
            va="top",
        )

    if d.nb_trous > 0 and d.diametre_trou_mm > 0:
        ax.text(
            -R_be,
            -R_be - 30.0,
            f"{d.nb_trous} x Ø {_fmt_mm(d.diametre_trou_mm)}",
            fontsize=9,
            ha="left",
            va="top",
        )

    ax.set_title("Vue de face")
    ax.set_aspect("equal", adjustable="box")
    lim = max(R_be, a, R_ouv) + 38.0
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE D'INFORMATIONS
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisCouvercle):
    lines = [
        f"Ø ouverture           : {_fmt_mm(d.diametre_ouverture_mm)}",
        f"Ø bride ext.          : {_fmt_mm(d.diametre_bride_externe_mm) if d.diametre_bride_externe_mm > 0 else 'N/A'}",
        f"Rayon base calotte    : {_fmt_mm(d.rayon_base_calotte_mm)}",
        f"Hauteur bombe         : {_fmt_mm(d.hauteur_bombe_mm)}",
        f"R courbure int.       : {_fmt_mm(d.rayon_courbure_interieur_mm)}",
        f"R courbure ext.       : {_fmt_mm(d.rayon_courbure_exterieur_mm) if d.rayon_courbure_exterieur_mm > 0 else 'N/A'}",
        f"Épaisseur calotte     : {_fmt_mm(d.epaisseur_calotte_mm)}",
        f"Épaisseur bride       : {_fmt_mm(d.epaisseur_bride_mm) if d.epaisseur_bride_mm > 0 else 'N/A'}",
        f"Largeur bride         : {_fmt_mm(d.largeur_bride_mm) if d.largeur_bride_mm > 0 else 'N/A'}",
        f"Nb trous / vis        : {d.nb_trous if d.nb_trous > 0 else 'N/A'}",
        f"Ø trou                : {_fmt_mm(d.diametre_trou_mm) if d.diametre_trou_mm > 0 else 'N/A'}",
        f"Ø cercle perçage      : {_fmt_mm(d.diametre_cercle_percage_mm) if d.diametre_cercle_percage_mm > 0 else 'N/A'}",
        f"Filetage              : {d.filetage_txt or 'N/A'}",
        f"F séparation          : {_fmt_n(d.force_separation_N) if d.force_separation_N > 0 else 'N/A'}",
        f"F joint               : {_fmt_n(d.force_joint_N) if d.force_joint_N > 0 else 'N/A'}",
        f"Précharge totale      : {_fmt_n(d.force_precharge_totale_N) if d.force_precharge_totale_N > 0 else 'N/A'}",
        f"Précharge / vis       : {_fmt_n(d.force_precharge_par_vis_N) if d.force_precharge_par_vis_N > 0 else 'N/A'}",
        f"Couple / vis          : {_fmt_nm(d.couple_serrage_par_vis_Nm) if d.couple_serrage_par_vis_Nm > 0 else 'N/A'}",
        f"Chanfrein             : {_fmt_mm(d.chanfrein_mm) if d.chanfrein_mm > 0 else 'N/A'}",
        f"Congé                 : {_fmt_mm(d.conge_mm) if d.conge_mm > 0 else 'N/A'}",
        f"Masse                 : {f'{d.masse_kg:.4f} kg' if d.masse_kg > 0 else 'N/A'}",
        f"Volume total          : {f'{d.volume_total_m3:.6e} m³' if d.volume_total_m3 > 0 else 'N/A'}",
        f"Source forme          : {d.source_forme or 'N/A'}",
    ]

    fig.text(
        0.015,
        0.02,
        "DONNÉES EXTRAITES DE CouvercleCylindre.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=8.5,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_couvercle_2d(
    couvercle: CouvercleCylindre,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Couvercle de cylindre",
):
    d = extraire_donnees_croquis(couvercle)

    if (
        d.diametre_ouverture_mm <= 0
        or d.rayon_base_calotte_mm <= 0
        or d.hauteur_bombe_mm <= 0
        or d.rayon_courbure_interieur_mm <= 0
        or d.epaisseur_calotte_mm <= 0
    ):
        raise ValueError(
            "Impossible de tracer le croquis : "
            "la géométrie calculée de la calotte est incomplète ou invalide."
        )

    fig, (ax_side, ax_front) = plt.subplots(
        1,
        2,
        figsize=(17, 9),
        gridspec_kw={"width_ratios": [2.25, 1.35]},
    )
    fig.suptitle(titre, fontsize=15, y=0.98)

    _tracer_vue_cote(ax_side, d)
    _tracer_vue_face(ax_front, d)
    _ajouter_cartouche_technique(fig, d)

    plt.tight_layout(rect=[0.0, 0.10, 1.0, 0.96])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, (ax_side, ax_front), d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

if __name__ == "__main__":
    from backend.pieces.cylindre import (
        Cylindre,
        ReglesJointTorique,
        ReglesVisserieBride,
        ReglesFabricationCylindre,
    )
    from backend.pieces.couvercle_cylindre import ReglesFormeCouvercle

    cyl = Cylindre(
        alesage_m=0.080,
        course_m=0.090,
        longueur_utile_m=0.120,
        pression_service_pa=2.5e6,
        pression_max_pa=4.0e6,
        pression_externe_pa=1.0e5,
        materiau_cle="acier_s355",
        facteur_securite=2.0,
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

    couv = CouvercleCylindre(
        cylindre=cyl,
        pression_max_pa=4.0e6,
        pression_externe_pa=1.0e5,
        materiau_cle="acier_s355",
        facteur_securite=2.0,
        regles_forme=ReglesFormeCouvercle(),
    )

    tracer_croquis_couvercle_2d(
        couv,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Couvercle cylindre calculé",
    )