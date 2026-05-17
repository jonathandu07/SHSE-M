"""
Chemin : frontend/components/moteur_thermique/pieces/bielle/sketches_2d.py
But : Définition des esquisses géométriques 2D de la pièce.
"""

# frontend/pieces/sketches_2d/bielle.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle, Polygon

from backend.components.moteur_thermique.pieces.bielle import CorpsBielle


# ============================================================
# OUTILS
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


def _fmt_pa(v: float) -> str:
    return f"{v:.3e} Pa"


def _fmt_m2(v: float) -> str:
    return f"{v:.6e} m²"


def _fmt_m3(v: float) -> str:
    return f"{v:.6e} m³"


def _fmt_m4(v: float) -> str:
    return f"{v:.6e} m⁴"


def _linestyle_axe():
    return dict(linestyle=(0, (8, 4, 2, 4)), linewidth=0.9, color="black")


def _linestyle_hidden():
    return dict(linestyle=(0, (4, 4)), linewidth=0.8, color="black")


def _linestyle_dimension():
    return dict(linewidth=1.0, color="black")


def _draw_extension_line(ax, x1: float, y1: float, x2: float, y2: float):
    ax.add_line(Line2D([x1, x2], [y1, y2], linestyle="--", linewidth=0.75, color="black"))


def _add_dimension_h(
    ax,
    x1: float,
    x2: float,
    y_ref: float,
    y_dim: float,
    text: str,
    text_offset: float = 4.0,
):
    _draw_extension_line(ax, x1, y_ref, x1, y_dim)
    _draw_extension_line(ax, x2, y_ref, x2, y_dim)
    ax.annotate(
        "",
        xy=(x1, y_dim),
        xytext=(x2, y_dim),
        arrowprops=dict(arrowstyle="<->", **_linestyle_dimension()),
    )
    ax.text((x1 + x2) / 2.0, y_dim + text_offset, text, ha="center", va="bottom", fontsize=9)


def _add_dimension_v(
    ax,
    x_ref: float,
    x_dim: float,
    y1: float,
    y2: float,
    text: str,
    text_offset: float = 4.0,
):
    _draw_extension_line(ax, x_ref, y1, x_dim, y1)
    _draw_extension_line(ax, x_ref, y2, x_dim, y2)
    ax.annotate(
        "",
        xy=(x_dim, y1),
        xytext=(x_dim, y2),
        arrowprops=dict(arrowstyle="<->", **_linestyle_dimension()),
    )
    ax.text(x_dim + text_offset, (y1 + y2) / 2.0, text, ha="left", va="center", rotation=90, fontsize=9)


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


def _add_hatched_rect(ax, x: float, y: float, w: float, h: float, hatch: str = "////", lw: float = 0.9):
    rect = Rectangle(
        (x, y),
        w,
        h,
        fill=True,
        facecolor="white",
        edgecolor="black",
        linewidth=lw,
        hatch=hatch,
        zorder=0,
    )
    ax.add_patch(rect)


def _add_hatched_polygon(ax, pts, hatch="////", lw=0.9):
    poly = Polygon(
        pts,
        closed=True,
        fill=True,
        facecolor="white",
        edgecolor="black",
        linewidth=lw,
        hatch=hatch,
        zorder=0,
    )
    ax.add_patch(poly)


# ============================================================
# DONNÉES EXTRAITES
# ============================================================

@dataclass
class DonneesCroquisBielle:
    longueur_bielle_mm: float = 0.0

    # Fut
    forme_fut: str = ""
    largeur_fut_mm: float = 0.0
    epaisseur_fut_mm: float = 0.0
    section_fut_m2: float = 0.0
    inertie_min_fut_m4: float = 0.0
    diametre_equivalent_fut_mm: float = 0.0
    modele_section: str = ""

    # Petite tête
    diametre_axe_piston_mm: float = 0.0
    diametre_ext_petite_tete_mm: float = 0.0
    longueur_portee_petite_tete_mm: float = 0.0
    largeur_ext_petite_tete_mm: float = 0.0
    epaisseur_radiale_petite_tete_mm: float = 0.0

    # Grande tête
    diametre_maneton_mm: float = 0.0
    diametre_ext_grande_tete_mm: float = 0.0
    longueur_portee_grande_tete_mm: float = 0.0
    largeur_ext_grande_tete_mm: float = 0.0
    epaisseur_radiale_grande_tete_mm: float = 0.0

    # Axes CAO
    centre_petite_tete_x_mm: float = 0.0
    centre_grande_tete_x_mm: float = 0.0
    longueur_fut_droite_mm: float = 0.0

    # Efforts
    force_axiale_max_N: float = 0.0
    force_axiale_min_N: float = 0.0
    effort_lateral_max_N: float = 0.0

    # Contraintes / dimensionnement
    section_min_calculee_m2: float = 0.0
    diametre_equivalent_min_mm: float = 0.0
    sigma_axiale_pa: float = 0.0
    sigma_admissible_pa: float = 0.0
    marge_axiale: float = 0.0

    # Flambage
    K_flambage: float = 0.0
    charge_critique_N: float = 0.0
    marge_flambage: float = 0.0
    module_young_pa: float = 0.0

    # Contacts
    pression_petite_tete_pa: float = 0.0
    pression_grande_tete_pa: float = 0.0
    pression_admissible_petite_tete_pa: float = 0.0
    pression_admissible_grande_tete_pa: float = 0.0

    # Masse
    volume_fut_m3: float = 0.0
    masse_fut_kg: float = 0.0
    densite_kg_m3: float = 0.0

    # CAO / finition
    chanfrein_fut_mm: float = 0.0
    rayon_conge_mm: float = 0.0
    rugosite_fut_ra_um: float = 0.0
    rugosite_alesages_ra_um: float = 0.0

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(bielle: CorpsBielle) -> DonneesCroquisBielle:
    rapport = bielle.calculer(strict=False)

    fut = _get_nested(rapport, "geometrie", "fut", default={}) or {}
    pt = _get_nested(rapport, "geometrie", "petite_tete", default={}) or {}
    gt = _get_nested(rapport, "geometrie", "grande_tete", default={}) or {}
    dim = rapport.get("dimensionnements", {})
    cont = rapport.get("contraintes", {})
    axial = cont.get("axial", {}) if isinstance(cont.get("axial"), dict) else {}
    flamb = rapport.get("flambage", {})
    ct = rapport.get("contacts_tetes", {})
    ct_pt = ct.get("petite_tete", {}) if isinstance(ct.get("petite_tete"), dict) else {}
    ct_gt = ct.get("grande_tete", {}) if isinstance(ct.get("grande_tete"), dict) else {}
    masse = rapport.get("masse", {})
    cao = rapport.get("cao", {})
    cao_fut = cao.get("fut", {}) if isinstance(cao.get("fut"), dict) else {}
    cao_pt = cao.get("petite_tete", {}) if isinstance(cao.get("petite_tete"), dict) else {}
    cao_gt = cao.get("grande_tete", {}) if isinstance(cao.get("grande_tete"), dict) else {}
    mat = rapport.get("materiau", {})

    return DonneesCroquisBielle(
        longueur_bielle_mm=_mm(_get_nested(cao, "entraxe_centres_m", default=0.0)),

        forme_fut=str(_get_nested(cao, "forme_fut", default="") or ""),
        largeur_fut_mm=_mm(_get_nested(cao_fut, "largeur_m", default=_get_nested(fut, "largeur_fut_m", default=0.0))),
        epaisseur_fut_mm=_mm(_get_nested(cao_fut, "epaisseur_m", default=_get_nested(fut, "epaisseur_fut_m", default=0.0))),
        section_fut_m2=_safe_float(_get_nested(cao_fut, "section_m2", default=_get_nested(fut, "section_fut_m2", default=0.0))),
        inertie_min_fut_m4=_safe_float(_get_nested(fut, "inertie_min_fut_m4", default=0.0)),
        diametre_equivalent_fut_mm=_mm(_get_nested(cao_fut, "diametre_equivalent_m", default=_get_nested(fut, "diametre_equivalent_m", default=_get_nested(fut, "diametre_equivalent_fut_m", default=0.0)))),
        modele_section=str(_get_nested(cao_fut, "modele_section", default="") or ""),

        diametre_axe_piston_mm=_mm(_get_nested(cao_pt, "diametre_alésage_m", default=_get_nested(pt, "diametre_axe_piston_m", default=0.0))),
        diametre_ext_petite_tete_mm=_mm(_get_nested(cao_pt, "diametre_exterieur_m", default=0.0)),
        longueur_portee_petite_tete_mm=_mm(_get_nested(cao_pt, "largeur_portee_m", default=_get_nested(pt, "longueur_portee_m", default=0.0))),
        largeur_ext_petite_tete_mm=_mm(_get_nested(cao_pt, "largeur_exterieure_m", default=0.0)),
        epaisseur_radiale_petite_tete_mm=_mm(_get_nested(cao_pt, "epaisseur_radiale_m", default=0.0)),

        diametre_maneton_mm=_mm(_get_nested(cao_gt, "diametre_alésage_m", default=_get_nested(gt, "diametre_maneton_m", default=0.0))),
        diametre_ext_grande_tete_mm=_mm(_get_nested(cao_gt, "diametre_exterieur_m", default=0.0)),
        longueur_portee_grande_tete_mm=_mm(_get_nested(cao_gt, "largeur_portee_m", default=_get_nested(gt, "longueur_portee_m", default=0.0))),
        largeur_ext_grande_tete_mm=_mm(_get_nested(cao_gt, "largeur_exterieure_m", default=0.0)),
        epaisseur_radiale_grande_tete_mm=_mm(_get_nested(cao_gt, "epaisseur_radiale_m", default=0.0)),

        centre_petite_tete_x_mm=_mm(_get_nested(cao_pt, "centre_x_m", default=0.0)),
        centre_grande_tete_x_mm=_mm(_get_nested(cao_gt, "centre_x_m", default=0.0)),
        longueur_fut_droite_mm=_mm(_get_nested(cao, "longueur_fut_droite_approx_m", default=0.0)),

        force_axiale_max_N=_safe_float(_get_nested(rapport, "efforts", "force_axiale_max_N", default=0.0)),
        force_axiale_min_N=_safe_float(_get_nested(rapport, "efforts", "force_axiale_min_N", default=0.0)),
        effort_lateral_max_N=_safe_float(_get_nested(rapport, "efforts", "effort_lateral_max_N", default=0.0)),

        section_min_calculee_m2=_safe_float(_get_nested(dim, "section_min_calculee_m2", default=0.0)),
        diametre_equivalent_min_mm=_mm(_get_nested(dim, "diametre_equivalent_min_m", default=0.0)),
        sigma_axiale_pa=_safe_float(_get_nested(axial, "sigma_axiale_pa_sur_Fmax", default=0.0)),
        sigma_admissible_pa=_safe_float(_get_nested(axial, "sigma_admissible_pa", default=_get_nested(mat, "sigma_admissible_pa", default=0.0))),
        marge_axiale=_safe_float(_get_nested(axial, "marge_axiale", default=0.0)),

        K_flambage=_safe_float(_get_nested(flamb, "K_flambage", default=0.0)),
        charge_critique_N=_safe_float(_get_nested(flamb, "charge_critique_N", default=0.0)),
        marge_flambage=_safe_float(_get_nested(flamb, "marge_sur_Fmax", default=0.0)),
        module_young_pa=_safe_float(_get_nested(flamb, "module_young_pa", default=_get_nested(mat, "module_young_pa", default=0.0))),

        pression_petite_tete_pa=_safe_float(_get_nested(ct_pt, "pression_moyenne_pa", default=0.0)),
        pression_grande_tete_pa=_safe_float(_get_nested(ct_gt, "pression_moyenne_pa", default=0.0)),
        pression_admissible_petite_tete_pa=_safe_float(_get_nested(ct_pt, "pression_admissible_pa", default=0.0)),
        pression_admissible_grande_tete_pa=_safe_float(_get_nested(ct_gt, "pression_admissible_pa", default=0.0)),

        volume_fut_m3=_safe_float(_get_nested(masse, "volume_fut_m3", default=0.0)),
        masse_fut_kg=_safe_float(_get_nested(masse, "masse_fut_kg", default=0.0)),
        densite_kg_m3=_safe_float(_get_nested(mat, "densite_kg_m3", default=0.0)),

        chanfrein_fut_mm=_mm(_get_nested(cao_fut, "chanfrein_m", default=0.0)),
        rayon_conge_mm=_mm(_get_nested(cao_fut, "rayon_conge_tete_fut_m", default=0.0)),
        rugosite_fut_ra_um=_safe_float(_get_nested(cao_fut, "rugosite_ra_um", default=0.0)),
        rugosite_alesages_ra_um=_safe_float(_get_nested(cao_pt, "rugosite_alésage_ra_um", default=0.0)),

        rapport_complet=rapport,
    )


# ============================================================
# VUE DE CÔTÉ DÉTAILLÉE
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisBielle):
    L = d.longueur_bielle_mm
    if L <= 0:
        ax.text(0.5, 0.5, "Longueur de bielle non disponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de côté")
        ax.set_axis_off()
        return

    xp = d.centre_petite_tete_x_mm
    xg = d.centre_grande_tete_x_mm if d.centre_grande_tete_x_mm > 0 else L

    Dp_ext = d.diametre_ext_petite_tete_mm
    Dp_int = d.diametre_axe_piston_mm
    Dg_ext = d.diametre_ext_grande_tete_mm
    Dg_int = d.diametre_maneton_mm

    # fallback de représentation si les diamètres extérieurs ne sont pas connus
    if Dp_ext <= 0 and Dp_int > 0:
        Dp_ext = Dp_int * 1.35
    if Dg_ext <= 0 and Dg_int > 0:
        Dg_ext = Dg_int * 1.35

    Rp_ext = Dp_ext / 2.0 if Dp_ext > 0 else 0.0
    Rp_int = Dp_int / 2.0 if Dp_int > 0 else 0.0
    Rg_ext = Dg_ext / 2.0 if Dg_ext > 0 else 0.0
    Rg_int = Dg_int / 2.0 if Dg_int > 0 else 0.0

    # Fut
    h_fut = d.epaisseur_fut_mm
    if h_fut <= 0 and d.diametre_equivalent_fut_mm > 0:
        h_fut = d.diametre_equivalent_fut_mm
    y_fut = 0.5 * h_fut if h_fut > 0 else 0.0

    ymax = max(Rp_ext, Rg_ext, y_fut, 1.0)

    # Têtes
    if Dp_ext > 0:
        ax.add_patch(Circle((xp, 0.0), Rp_ext, fill=False, linewidth=1.5))
        _add_hatched_rect(ax, xp - Rp_ext, -Rp_ext, 2.0 * Rp_ext, 2.0 * Rp_ext, hatch="////", lw=0.0)
        ax.add_patch(Circle((xp, 0.0), Rp_ext, fill=False, linewidth=1.5))
    if Dp_int > 0:
        ax.add_patch(Circle((xp, 0.0), Rp_int, fill=False, linewidth=1.1))

    if Dg_ext > 0:
        ax.add_patch(Circle((xg, 0.0), Rg_ext, fill=False, linewidth=1.5))
        _add_hatched_rect(ax, xg - Rg_ext, -Rg_ext, 2.0 * Rg_ext, 2.0 * Rg_ext, hatch="////", lw=0.0)
        ax.add_patch(Circle((xg, 0.0), Rg_ext, fill=False, linewidth=1.5))
    if Dg_int > 0:
        ax.add_patch(Circle((xg, 0.0), Rg_int, fill=False, linewidth=1.1))

    # Fut reliant les tangentes approchées
    if y_fut > 0:
        x1 = xp + max(Rp_ext, 0.0)
        x2 = xg - max(Rg_ext, 0.0)
        if x2 > x1:
            _add_hatched_rect(ax, x1, -y_fut, x2 - x1, 2.0 * y_fut)
            ax.add_patch(Rectangle((x1, -y_fut), x2 - x1, 2.0 * y_fut, fill=False, linewidth=1.4))

            # raccords schématiques
            ax.add_line(Line2D([xp + Rp_ext, x1], [y_fut, y_fut], linewidth=1.0, color="black"))
            ax.add_line(Line2D([xp + Rp_ext, x1], [-y_fut, -y_fut], linewidth=1.0, color="black"))
            ax.add_line(Line2D([x2, xg - Rg_ext], [y_fut, y_fut], linewidth=1.0, color="black"))
            ax.add_line(Line2D([x2, xg - Rg_ext], [-y_fut, -y_fut], linewidth=1.0, color="black"))

    # Axes
    ax.axhline(0, **_linestyle_axe())
    ax.axvline(xp, **_linestyle_hidden())
    ax.axvline(xg, **_linestyle_hidden())

    # Leaders
    if Dp_ext > 0:
        _annotate_leader(ax, xp - Rp_ext - 55.0, Rp_ext + 18.0, xp, Rp_ext, "Petite tête")
    if Dg_ext > 0:
        _annotate_leader(ax, xg + Rg_ext + 10.0, Rg_ext + 18.0, xg, Rg_ext, "Grande tête")
    if y_fut > 0:
        _annotate_leader(ax, xp + 0.25 * (xg - xp), y_fut + 18.0, xp + 0.35 * (xg - xp), y_fut, "Fût")

    # Cotes
    ydim1 = ymax + 16.0
    ydim2 = ymax + 32.0
    ydim3 = ymax + 48.0

    _add_dimension_h(ax, xp, xg, 0.0, ydim1, f"Entraxe = {_fmt_mm(xg - xp)}")
    if d.longueur_fut_droite_mm > 0:
        x1 = xp + max(Rp_ext, 0.0)
        x2 = xg - max(Rg_ext, 0.0)
        if x2 > x1:
            _add_dimension_h(ax, x1, x2, 0.0, ydim2, f"L fut droite ≈ {_fmt_mm(d.longueur_fut_droite_mm)}")

    xdim1 = xg + max(Rg_ext, 10.0) + 20.0
    xdim2 = xg + max(Rg_ext, 10.0) + 40.0
    xdim3 = xg + max(Rg_ext, 10.0) + 60.0

    if Dp_int > 0:
        _add_dimension_v(ax, 0.0, xdim1, -Rp_int, Rp_int, f"Ø axe = {_fmt_mm(Dp_int)}")
    if Dg_int > 0:
        _add_dimension_v(ax, 0.0, xdim2, -Rg_int, Rg_int, f"Ø maneton = {_fmt_mm(Dg_int)}")
    if h_fut > 0:
        _add_dimension_v(ax, 0.0, xdim3, -y_fut, y_fut, f"e fut = {_fmt_mm(2.0 * y_fut)}")

    # Bloc infos
    infos = []
    if d.forme_fut:
        infos.append(f"Forme fut            : {d.forme_fut}")
    if d.modele_section:
        infos.append(f"Modèle section       : {d.modele_section}")
    if d.largeur_fut_mm > 0:
        infos.append(f"Largeur fut          : {_fmt_mm(d.largeur_fut_mm)}")
    if d.epaisseur_fut_mm > 0:
        infos.append(f"Épaisseur fut        : {_fmt_mm(d.epaisseur_fut_mm)}")
    if d.diametre_equivalent_fut_mm > 0:
        infos.append(f"Ø équivalent fut     : {_fmt_mm(d.diametre_equivalent_fut_mm)}")
    if d.rayon_conge_mm > 0:
        infos.append(f"Rayon congé          : {_fmt_mm(d.rayon_conge_mm)}")
    if d.chanfrein_fut_mm > 0:
        infos.append(f"Chanfrein fut        : {_fmt_mm(d.chanfrein_fut_mm)}")

    if infos:
        ax.text(
            xp - max(Rp_ext, 10.0),
            -(ymax + 36.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.6,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    xmin = xp - max(Rp_ext, 20.0) - 90.0
    xmax = xg + max(Rg_ext, 20.0) + 95.0

    ax.set_title("Vue de côté détaillée")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-(ymax + 75.0), ymax + 75.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUES DE FACE
# ============================================================

def _tracer_section_tete(ax, d_ext_mm: float, d_int_mm: float, largeur_mm: float, titre: str, notes: List[str]):
    Rext = d_ext_mm / 2.0 if d_ext_mm > 0 else 0.0
    Rint = d_int_mm / 2.0 if d_int_mm > 0 else 0.0

    if Rext > 0:
        ax.add_patch(Circle((0, 0), Rext, fill=False, linewidth=1.5, edgecolor="black"))
    if Rint > 0:
        ax.add_patch(Circle((0, 0), Rint, fill=False, linewidth=1.1, edgecolor="black"))

    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    txt = []
    if d_ext_mm > 0:
        txt.append(f"Ø ext = {_fmt_mm(d_ext_mm)}")
    if d_int_mm > 0:
        txt.append(f"Ø alésage = {_fmt_mm(d_int_mm)}")
    if largeur_mm > 0:
        txt.append(f"Largeur = {_fmt_mm(largeur_mm)}")
    txt.extend(notes)

    lim = max(Rext, Rint, 1.0) + 24.0
    ax.text(
        -lim + 4.0,
        -lim + 4.0,
        "\n".join(txt),
        ha="left",
        va="bottom",
        fontsize=8.3,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title(titre)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


def _tracer_section_fut(ax, d: DonneesCroquisBielle):
    if d.largeur_fut_mm > 0 and d.epaisseur_fut_mm > 0:
        b = d.largeur_fut_mm
        h = d.epaisseur_fut_mm
        _add_hatched_rect(ax, -b / 2.0, -h / 2.0, b, h)
        ax.add_patch(Rectangle((-b / 2.0, -h / 2.0), b, h, fill=False, linewidth=1.4))
        txt = [
            "Section fut rectangulaire",
            f"b = {_fmt_mm(b)}",
            f"h = {_fmt_mm(h)}",
        ]
        lim = max(b, h) * 0.8 + 20.0
    elif d.diametre_equivalent_fut_mm > 0:
        R = d.diametre_equivalent_fut_mm / 2.0
        ax.add_patch(Circle((0, 0), R, fill=False, linewidth=1.5, edgecolor="black"))
        txt = [
            "Section équivalente",
            f"Ø eq = {_fmt_mm(d.diametre_equivalent_fut_mm)}",
        ]
        lim = R + 20.0
    else:
        ax.text(0.5, 0.5, "Section fut non disponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de face - Fût")
        ax.set_axis_off()
        return

    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    if d.section_fut_m2 > 0:
        txt.append(f"A = {_fmt_m2(d.section_fut_m2)}")
    if d.inertie_min_fut_m4 > 0:
        txt.append(f"Imin = {_fmt_m4(d.inertie_min_fut_m4)}")

    ax.text(
        -lim + 4.0,
        -lim + 4.0,
        "\n".join(txt),
        ha="left",
        va="bottom",
        fontsize=8.3,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Vue de face - Fût")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisBielle):
    lines = [
        f"Entraxe bielle             : {_fmt_mm(d.longueur_bielle_mm) if d.longueur_bielle_mm > 0 else 'N/A'}",
        f"Forme fut                  : {d.forme_fut or 'N/A'}",
        f"Modèle section             : {d.modele_section or 'N/A'}",
        f"Largeur fut                : {_fmt_mm(d.largeur_fut_mm) if d.largeur_fut_mm > 0 else 'N/A'}",
        f"Épaisseur fut              : {_fmt_mm(d.epaisseur_fut_mm) if d.epaisseur_fut_mm > 0 else 'N/A'}",
        f"Section fut                : {_fmt_m2(d.section_fut_m2) if d.section_fut_m2 > 0 else 'N/A'}",
        f"Inertie min fut            : {_fmt_m4(d.inertie_min_fut_m4) if d.inertie_min_fut_m4 > 0 else 'N/A'}",
        f"Ø équivalent fut           : {_fmt_mm(d.diametre_equivalent_fut_mm) if d.diametre_equivalent_fut_mm > 0 else 'N/A'}",
        f"A min calculée             : {_fmt_m2(d.section_min_calculee_m2) if d.section_min_calculee_m2 > 0 else 'N/A'}",
        f"Ø équivalent min           : {_fmt_mm(d.diametre_equivalent_min_mm) if d.diametre_equivalent_min_mm > 0 else 'N/A'}",
        f"Force axiale max           : {_fmt_n(d.force_axiale_max_N) if d.force_axiale_max_N > 0 else 'N/A'}",
        f"Force axiale min           : {_fmt_n(d.force_axiale_min_N) if d.force_axiale_min_N != 0 else 'N/A'}",
        f"Effort latéral max         : {_fmt_n(d.effort_lateral_max_N) if d.effort_lateral_max_N > 0 else 'N/A'}",
        f"σ axiale                   : {_fmt_pa(d.sigma_axiale_pa) if d.sigma_axiale_pa != 0 else 'N/A'}",
        f"σ admissible               : {_fmt_pa(d.sigma_admissible_pa) if d.sigma_admissible_pa > 0 else 'N/A'}",
        f"Marge axiale               : {f'{d.marge_axiale:.3f}' if d.marge_axiale > 0 else 'N/A'}",
        f"E                          : {_fmt_pa(d.module_young_pa) if d.module_young_pa > 0 else 'N/A'}",
        f"K flambage                 : {f'{d.K_flambage:.3f}' if d.K_flambage > 0 else 'N/A'}",
        f"Pcrit Euler                : {_fmt_n(d.charge_critique_N) if d.charge_critique_N > 0 else 'N/A'}",
        f"Marge flambage             : {f'{d.marge_flambage:.3f}' if d.marge_flambage > 0 else 'N/A'}",
        f"Ø axe piston               : {_fmt_mm(d.diametre_axe_piston_mm) if d.diametre_axe_piston_mm > 0 else 'N/A'}",
        f"L portée petite tête       : {_fmt_mm(d.longueur_portee_petite_tete_mm) if d.longueur_portee_petite_tete_mm > 0 else 'N/A'}",
        f"p petite tête              : {_fmt_pa(d.pression_petite_tete_pa) if d.pression_petite_tete_pa > 0 else 'N/A'}",
        f"p adm petite tête          : {_fmt_pa(d.pression_admissible_petite_tete_pa) if d.pression_admissible_petite_tete_pa > 0 else 'N/A'}",
        f"Ø maneton                  : {_fmt_mm(d.diametre_maneton_mm) if d.diametre_maneton_mm > 0 else 'N/A'}",
        f"L portée grande tête       : {_fmt_mm(d.longueur_portee_grande_tete_mm) if d.longueur_portee_grande_tete_mm > 0 else 'N/A'}",
        f"p grande tête              : {_fmt_pa(d.pression_grande_tete_pa) if d.pression_grande_tete_pa > 0 else 'N/A'}",
        f"p adm grande tête          : {_fmt_pa(d.pression_admissible_grande_tete_pa) if d.pression_admissible_grande_tete_pa > 0 else 'N/A'}",
        f"Volume fut                 : {_fmt_m3(d.volume_fut_m3) if d.volume_fut_m3 > 0 else 'N/A'}",
        f"Masse fut                  : {f'{d.masse_fut_kg:.4f} kg' if d.masse_fut_kg > 0 else 'N/A'}",
        f"Densité                    : {f'{d.densite_kg_m3:.2f} kg/m³' if d.densite_kg_m3 > 0 else 'N/A'}",
        f"Chanfrein fut              : {_fmt_mm(d.chanfrein_fut_mm) if d.chanfrein_fut_mm > 0 else 'N/A'}",
        f"Rayon congé                : {_fmt_mm(d.rayon_conge_mm) if d.rayon_conge_mm > 0 else 'N/A'}",
        f"Ra fut                     : {f'{d.rugosite_fut_ra_um:.2f} µm' if d.rugosite_fut_ra_um > 0 else 'N/A'}",
        f"Ra alésages                : {f'{d.rugosite_alesages_ra_um:.2f} µm' if d.rugosite_alesages_ra_um > 0 else 'N/A'}",
    ]

    fig.text(
        0.012,
        0.015,
        "DONNÉES EXTRAITES DE CorpsBielle.calculer()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=8.05,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_bielle_2d(
    bielle: CorpsBielle,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Corps de bielle",
):
    d = extraire_donnees_croquis(bielle)

    if d.longueur_bielle_mm <= 0:
        raise ValueError("Impossible de tracer : longueur de bielle absente.")

    fig = plt.figure(figsize=(19, 11))
    gs = fig.add_gridspec(2, 4, height_ratios=[2.2, 1.3], width_ratios=[1.55, 1.0, 1.0, 1.0])

    ax_side = fig.add_subplot(gs[0, :])
    ax_face_pt = fig.add_subplot(gs[1, 0])
    ax_face_fut = fig.add_subplot(gs[1, 1])
    ax_face_gt = fig.add_subplot(gs[1, 2])
    ax_info = fig.add_subplot(gs[1, 3])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_cote(ax_side, d)

    _tracer_section_tete(
        ax_face_pt,
        d_ext_mm=d.diametre_ext_petite_tete_mm,
        d_int_mm=d.diametre_axe_piston_mm,
        largeur_mm=d.largeur_ext_petite_tete_mm if d.largeur_ext_petite_tete_mm > 0 else d.longueur_portee_petite_tete_mm,
        titre="Vue de face - Petite tête",
        notes=[],
    )

    _tracer_section_fut(ax_face_fut, d)

    _tracer_section_tete(
        ax_face_gt,
        d_ext_mm=d.diametre_ext_grande_tete_mm,
        d_int_mm=d.diametre_maneton_mm,
        largeur_mm=d.largeur_ext_grande_tete_mm if d.largeur_ext_grande_tete_mm > 0 else d.longueur_portee_grande_tete_mm,
        titre="Vue de face - Grande tête",
        notes=[],
    )

    ax_info.axis("off")
    notes = [
        "Le dessin représente uniquement",
        "la géométrie réellement calculée",
        "ou explicitement fournie.",
        "",
        "Si la forme réelle du fût n’est pas",
        "imposée, le tracé reste équivalent",
        "au modèle de section calculé.",
        "",
        "Aucune géométrie arbitraire",
        "n’est inventée.",
    ]
    ax_info.text(
        0.02,
        0.98,
        "\n".join(notes),
        transform=ax_info.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="black", linewidth=0.8),
    )

    _ajouter_cartouche_technique(fig, d)

    plt.tight_layout(rect=[0.0, 0.11, 1.0, 0.965])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, {
        "vue_cote": ax_side,
        "vue_face_petite_tete": ax_face_pt,
        "vue_face_fut": ax_face_fut,
        "vue_face_grande_tete": ax_face_gt,
        "panneau_info": ax_info,
    }, d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

if __name__ == "__main__":
    try:
        from backend.components.moteur_thermique.pieces.arbre_piston import ArbrePiston
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

    tracer_croquis_bielle_2d(
        b,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Bielle calculée",
    )