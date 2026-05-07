# frontend/pieces/sketches_2d/joint_piston.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D

from backend.components.moteur_thermique.pieces.joint_piston import JointPiston


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


def _fmt_m2(v: float) -> str:
    return f"{v:.6e} m²"


def _fmt_m3(v: float) -> str:
    return f"{v:.6e} m³"


def _fmt_pa(v: float) -> str:
    return f"{v:.6e} Pa"


def _fmt_n(v: float) -> str:
    return f"{v:.6f} N"


def _linestyle_axis():
    return dict(linestyle=(0, (8, 4, 2, 4)), linewidth=0.85, color="black")


def _linestyle_hidden():
    return dict(linestyle=(0, (4, 4)), linewidth=0.8, color="black")


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
        arrowprops=dict(arrowstyle="<->", linewidth=1.0, color="black"),
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
        arrowprops=dict(arrowstyle="<->", linewidth=1.0, color="black"),
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


# ============================================================
# DONNÉES EXTRAITES
# ============================================================

@dataclass
class DonneesCroquisJointPiston:
    diametre_interieur_cylindre_mm: float = 0.0

    diametre_interieur_joint_mm: float = 0.0
    diametre_section_joint_mm: float = 0.0
    diametre_moyen_joint_mm: float = 0.0
    perimetre_moyen_joint_mm: float = 0.0
    volume_joint_m3: float = 0.0
    surface_joint_m2: float = 0.0
    masse_joint_kg: float = 0.0

    diametre_fond_gorge_mm: float = 0.0
    profondeur_gorge_mm: float = 0.0
    largeur_gorge_mm: float = 0.0
    perimetre_fond_gorge_mm: float = 0.0
    section_gorge_m2: float = 0.0
    volume_gorge_m3: float = 0.0
    taux_remplissage: float = 0.0

    diametre_montage_stretch_mm: float = 0.0
    stretch_fraction: float = 0.0
    hauteur_radiale_disponible_mm: float = 0.0
    squeeze_radial_fraction: float = 0.0

    pression_contact_estimee_pa: float = 0.0
    pression_contact_utilisee_pa: float = 0.0
    coeff_frottement_mu: float = 0.0
    largeur_bande_contact_mm: float = 0.0
    aire_contact_m2: float = 0.0
    effort_normal_estime_n: float = 0.0
    force_frottement_estimee_n: float = 0.0

    pression_diff_pa: float = 0.0
    aire_reference_disque_cylindre_m2: float = 0.0
    force_pression_equivalente_n: float = 0.0

    nombre_rainures: int = 0
    rainures_detail: Optional[List[Dict[str, Any]]] = None

    squeeze_positive: Optional[bool] = None
    squeeze_moins_100pct: Optional[bool] = None
    taux_remplissage_le_1: Optional[bool] = None
    stretch_non_negatif: Optional[bool] = None

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(joint: JointPiston) -> DonneesCroquisJointPiston:
    rap = joint.analyser(strict=False)

    gj = rap.get("geometrie_joint", {})
    gorge = rap.get("gorge", {})
    ss = rap.get("squeeze_stretch", {})
    eff = rap.get("efforts", {})
    frot = rap.get("frottements", {})
    mat = rap.get("matiere", {})
    coh = rap.get("coherences", {})
    rain = rap.get("rainures", {})
    ent = rap.get("entrees", {})

    rainures_detail = rain.get("details")
    if not isinstance(rainures_detail, list):
        rainures_detail = None

    return DonneesCroquisJointPiston(
        diametre_interieur_cylindre_mm=_mm(_get_nested(ent, "diametre_interieur_cylindre_m", default=0.0)),

        diametre_interieur_joint_mm=_mm(_get_nested(ent, "diametre_interieur_joint_m", default=0.0)),
        diametre_section_joint_mm=_mm(_get_nested(ent, "diametre_section_joint_m", default=0.0)),
        diametre_moyen_joint_mm=_mm(_get_nested(gj, "diametre_moyen_joint_m", default=0.0)),
        perimetre_moyen_joint_mm=_mm(_get_nested(gj, "perimetre_moyen_joint_m", default=0.0)),
        volume_joint_m3=_safe_float(_get_nested(gj, "volume_joint_m3", default=0.0)),
        surface_joint_m2=_safe_float(_get_nested(gj, "surface_joint_m2", default=0.0)),
        masse_joint_kg=_safe_float(_get_nested(mat, "masse_joint_kg", default=0.0)),

        diametre_fond_gorge_mm=_mm(_get_nested(ent, "diametre_fond_gorge_m", default=0.0)),
        profondeur_gorge_mm=_mm(_get_nested(ent, "profondeur_gorge_m", default=0.0)),
        largeur_gorge_mm=_mm(_get_nested(ent, "largeur_gorge_m", default=0.0)),
        perimetre_fond_gorge_mm=_mm(_get_nested(gorge, "perimetre_fond_gorge_m", default=0.0)),
        section_gorge_m2=_safe_float(_get_nested(gorge, "section_gorge_rect_m2", default=0.0)),
        volume_gorge_m3=_safe_float(_get_nested(gorge, "volume_gorge_m3", default=0.0)),
        taux_remplissage=_safe_float(_get_nested(gorge, "taux_remplissage_volume_joint_sur_gorge", default=0.0)),

        diametre_montage_stretch_mm=_mm(_get_nested(ss, "diametre_montage_stretch_m", default=0.0)),
        stretch_fraction=_safe_float(_get_nested(ss, "stretch_fraction", default=0.0)),
        hauteur_radiale_disponible_mm=_mm(_get_nested(ss, "hauteur_radiale_disponible_m", default=0.0)),
        squeeze_radial_fraction=_safe_float(_get_nested(ss, "squeeze_radial_fraction", default=0.0)),

        pression_contact_estimee_pa=_safe_float(_get_nested(eff, "pression_contact_estimee_pa", default=0.0)),
        pression_contact_utilisee_pa=_safe_float(_get_nested(eff, "pression_contact_utilisee_pa", default=0.0)),
        coeff_frottement_mu=_safe_float(_get_nested(frot, "coeff_frottement_mu", default=0.0)),
        largeur_bande_contact_mm=_mm(_get_nested(frot, "largeur_bande_contact_m", default=0.0)),
        aire_contact_m2=_safe_float(_get_nested(frot, "aire_contact_m2", default=0.0)),
        effort_normal_estime_n=_safe_float(_get_nested(frot, "effort_normal_estime_N", default=0.0)),
        force_frottement_estimee_n=_safe_float(_get_nested(frot, "force_frottement_estimee_N", default=0.0)),

        pression_diff_pa=_safe_float(_get_nested(ent, "pression_diff_pa", default=0.0)),
        aire_reference_disque_cylindre_m2=_safe_float(_get_nested(eff, "aire_reference_disque_cylindre_m2", default=0.0)),
        force_pression_equivalente_n=_safe_float(_get_nested(eff, "force_pression_equivalente_N", default=0.0)),

        nombre_rainures=int(_safe_float(_get_nested(rain, "nombre_rainures", default=0), 0)),
        rainures_detail=rainures_detail,

        squeeze_positive=_get_nested(coh, "squeeze_positive", default=None),
        squeeze_moins_100pct=_get_nested(coh, "squeeze_moins_100pct", default=None),
        taux_remplissage_le_1=_get_nested(coh, "taux_remplissage_le_1", default=None),
        stretch_non_negatif=_get_nested(coh, "stretch_non_negatif", default=None),

        rapport_complet=rap,
    )


# ============================================================
# VUE LONGITUDINALE DU PISTON ET DES RAINURES
# ============================================================

def _tracer_vue_longitudinale(ax, d: DonneesCroquisJointPiston):
    # dimensions issues des rainures si possible
    if d.rainures_detail and len(d.rainures_detail) > 0:
        rainures = d.rainures_detail
        xs_min = []
        xs_max = []
        diam_hors = []
        diam_fond = []
        for r in rainures:
            if isinstance(r, dict):
                if r.get("position_debut_depuis_face_tete_m") is not None:
                    xs_min.append(_mm(r["position_debut_depuis_face_tete_m"]))
                if r.get("position_fin_depuis_face_tete_m") is not None:
                    xs_max.append(_mm(r["position_fin_depuis_face_tete_m"]))
                if r.get("diametre_zone_hors_rainure_m") is not None:
                    diam_hors.append(_mm(r["diametre_zone_hors_rainure_m"]))
                if r.get("diametre_fond_rainure_m") is not None:
                    diam_fond.append(_mm(r["diametre_fond_rainure_m"]))

        if xs_max:
            L_piston = max(xs_max) + 10.0
        else:
            L_piston = 80.0

        D_hors = max(diam_hors) if diam_hors else (d.diametre_interieur_cylindre_mm - 2.0 if d.diametre_interieur_cylindre_mm > 0 else 60.0)
        D_fond = max(diam_fond) if diam_fond else d.diametre_fond_gorge_mm
    else:
        L_piston = 80.0
        D_hors = d.diametre_interieur_cylindre_mm - 2.0 if d.diametre_interieur_cylindre_mm > 0 else 60.0
        D_fond = d.diametre_fond_gorge_mm

    if D_hors <= 0:
        D_hors = 60.0

    y_hors = D_hors / 2.0
    y_fond = D_fond / 2.0 if D_fond > 0 else y_hors - 1.0

    # piston extérieur
    ax.add_patch(Rectangle((0.0, -y_hors), L_piston, 2.0 * y_hors, fill=False, linewidth=1.5))
    ax.axhline(0.0, **_linestyle_axis())

    # cylindre en lignes cachées
    if d.diametre_interieur_cylindre_mm > 0:
        y_cyl = d.diametre_interieur_cylindre_mm / 2.0
        ax.add_line(Line2D([0.0, L_piston], [y_cyl, y_cyl], **_linestyle_hidden()))
        ax.add_line(Line2D([0.0, L_piston], [-y_cyl, -y_cyl], **_linestyle_hidden()))

    # rainures détaillées
    if d.rainures_detail:
        for i, r in enumerate(d.rainures_detail, start=1):
            if not isinstance(r, dict):
                continue

            x0 = _mm(r.get("position_debut_depuis_face_tete_m", 0.0))
            x1 = _mm(r.get("position_fin_depuis_face_tete_m", 0.0))
            width = x1 - x0 if x1 > x0 else d.largeur_gorge_mm
            prof = _mm(r.get("profondeur_radiale_m", 0.0))
            d_fond_loc = _mm(r.get("diametre_fond_rainure_m", 0.0))
            y_fond_loc = d_fond_loc / 2.0 if d_fond_loc > 0 else y_fond

            if width > 0 and prof > 0:
                # rainure haute
                ax.add_patch(
                    Rectangle(
                        (x0, y_fond_loc),
                        width,
                        y_hors - y_fond_loc,
                        fill=False,
                        linewidth=1.0,
                        linestyle="--",
                    )
                )
                # rainure basse
                ax.add_patch(
                    Rectangle(
                        (x0, -y_hors),
                        width,
                        y_hors - y_fond_loc,
                        fill=False,
                        linewidth=1.0,
                        linestyle="--",
                    )
                )

                xc = 0.5 * (x0 + x1)
                _annotate_leader(
                    ax,
                    x1 + 4.0,
                    y_hors + 16.0 + 9.0 * (i - 1),
                    xc,
                    y_fond_loc + 0.5 * (y_hors - y_fond_loc),
                    f"Rainure {i}",
                )

    # Cotes principales
    ydim1 = y_hors + 18.0
    ydim2 = ydim1 + 14.0

    _add_dimension_h(ax, 0.0, L_piston, 0.0, ydim1, f"L modèle = {_fmt_mm(L_piston)}")

    xdim1 = L_piston + 18.0
    xdim2 = L_piston + 36.0
    xdim3 = L_piston + 54.0

    _add_dimension_v(ax, 0.0, xdim1, -y_hors, y_hors, f"Ø hors gorge = {_fmt_mm(D_hors)}")

    if D_fond > 0:
        _add_dimension_v(ax, 0.0, xdim2, -y_fond, y_fond, f"Ø fond = {_fmt_mm(D_fond)}")

    if d.diametre_interieur_cylindre_mm > 0:
        y_cyl = d.diametre_interieur_cylindre_mm / 2.0
        _add_dimension_v(ax, 0.0, xdim3, -y_cyl, y_cyl, f"Ø cylindre = {_fmt_mm(d.diametre_interieur_cylindre_mm)}")

    if d.rainures_detail and len(d.rainures_detail) > 0:
        r0 = d.rainures_detail[0]
        if isinstance(r0, dict):
            x0 = _mm(r0.get("position_debut_depuis_face_tete_m", 0.0))
            x1 = _mm(r0.get("position_fin_depuis_face_tete_m", 0.0))
            if x1 > x0:
                _add_dimension_h(ax, x0, x1, y_hors, ydim2, f"L gorge = {_fmt_mm(x1 - x0)}")

    infos = [
        f"Nb rainures     : {d.nombre_rainures}",
        f"ID joint        : {_fmt_mm(d.diametre_interieur_joint_mm) if d.diametre_interieur_joint_mm > 0 else 'N/A'}",
        f"CS joint        : {_fmt_mm(d.diametre_section_joint_mm) if d.diametre_section_joint_mm > 0 else 'N/A'}",
        f"Squeeze         : {f'{d.squeeze_radial_fraction:.6f}' if d.squeeze_radial_fraction else 'N/A'}",
        f"Stretch         : {f'{d.stretch_fraction:.6f}' if d.stretch_fraction else 'N/A'}",
    ]

    ax.text(
        0.0,
        -(max(d.diametre_interieur_cylindre_mm, D_hors) / 2.0 + 24.0),
        "\n".join(infos),
        ha="left",
        va="top",
        fontsize=8.4,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Vue longitudinale du piston et des rainures")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-10.0, L_piston + 90.0)
    ax.set_ylim(-(max(d.diametre_interieur_cylindre_mm, D_hors) / 2.0 + 55.0), max(d.diametre_interieur_cylindre_mm, D_hors) / 2.0 + 60.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# COUPE RADIALE DÉTAILLÉE D'UNE GORGE
# ============================================================

def _tracer_coupe_radiale(ax, d: DonneesCroquisJointPiston):
    # déduction de diamètre hors gorge
    D_hors = 0.0
    if d.rainures_detail and len(d.rainures_detail) > 0:
        r0 = d.rainures_detail[0]
        if isinstance(r0, dict) and r0.get("diametre_zone_hors_rainure_m") is not None:
            D_hors = _mm(r0["diametre_zone_hors_rainure_m"])

    if D_hors <= 0:
        if d.diametre_interieur_cylindre_mm > 0:
            D_hors = d.diametre_interieur_cylindre_mm - 2.0
        elif d.diametre_fond_gorge_mm > 0 and d.profondeur_gorge_mm > 0:
            D_hors = d.diametre_fond_gorge_mm + 2.0 * d.profondeur_gorge_mm
        else:
            D_hors = 60.0

    R_hors = D_hors / 2.0
    R_fond = d.diametre_fond_gorge_mm / 2.0 if d.diametre_fond_gorge_mm > 0 else 0.0
    R_cyl = d.diametre_interieur_cylindre_mm / 2.0 if d.diametre_interieur_cylindre_mm > 0 else 0.0

    # cylindre
    if R_cyl > 0:
        ax.add_patch(Circle((0.0, 0.0), R_cyl, fill=False, linewidth=1.0, linestyle="--"))

    # piston hors gorge
    ax.add_patch(Circle((0.0, 0.0), R_hors, fill=False, linewidth=1.5))

    # fond de gorge
    if R_fond > 0:
        ax.add_patch(Circle((0.0, 0.0), R_fond, fill=False, linewidth=1.0, linestyle="--"))

    # tore schématique
    if d.diametre_section_joint_mm > 0 and R_fond > 0:
        r_joint = 0.5 * d.diametre_section_joint_mm
        centre_joint = (0.0, R_fond + r_joint)
        ax.add_patch(Circle(centre_joint, r_joint, fill=False, linewidth=1.2))
        _annotate_leader(ax, R_hors + 18.0, R_hors * 0.55, centre_joint[0], centre_joint[1], "Section joint")

    ax.axhline(0.0, **_linestyle_axis())
    ax.axvline(0.0, **_linestyle_axis())

    xdim1 = max(R_cyl, R_hors) + 18.0
    xdim2 = xdim1 + 18.0
    xdim3 = xdim2 + 18.0

    _add_dimension_v(ax, 0.0, xdim1, -R_hors, R_hors, f"Ø hors gorge = {_fmt_mm(D_hors)}")

    if R_fond > 0:
        _add_dimension_v(ax, 0.0, xdim2, -R_fond, R_fond, f"Ø fond = {_fmt_mm(d.diametre_fond_gorge_mm)}")

    if R_cyl > 0:
        _add_dimension_v(ax, 0.0, xdim3, -R_cyl, R_cyl, f"Ø cylindre = {_fmt_mm(d.diametre_interieur_cylindre_mm)}")

    txt = [
        f"Profondeur gorge : {_fmt_mm(d.profondeur_gorge_mm) if d.profondeur_gorge_mm > 0 else 'N/A'}",
        f"Largeur gorge    : {_fmt_mm(d.largeur_gorge_mm) if d.largeur_gorge_mm > 0 else 'N/A'}",
        f"Hauteur disp.    : {_fmt_mm(d.hauteur_radiale_disponible_mm) if d.hauteur_radiale_disponible_mm > 0 else 'N/A'}",
        f"Squeeze radial   : {f'{d.squeeze_radial_fraction:.6f}' if d.squeeze_radial_fraction else 'N/A'}",
        f"Stretch          : {f'{d.stretch_fraction:.6f}' if d.stretch_fraction else 'N/A'}",
    ]

    ax.text(
        -max(R_cyl, R_hors),
        -max(R_cyl, R_hors) - 16.0,
        "\n".join(txt),
        ha="left",
        va="top",
        fontsize=8.4,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Coupe radiale d'une gorge de joint piston")
    lim = max(R_cyl, R_hors) + 45.0
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim + 30.0)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE DE FACE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisJointPiston):
    D_hors = 0.0
    if d.rainures_detail and len(d.rainures_detail) > 0:
        r0 = d.rainures_detail[0]
        if isinstance(r0, dict) and r0.get("diametre_zone_hors_rainure_m") is not None:
            D_hors = _mm(r0["diametre_zone_hors_rainure_m"])

    if D_hors <= 0:
        if d.diametre_interieur_cylindre_mm > 0:
            D_hors = d.diametre_interieur_cylindre_mm - 2.0
        elif d.diametre_fond_gorge_mm > 0 and d.profondeur_gorge_mm > 0:
            D_hors = d.diametre_fond_gorge_mm + 2.0 * d.profondeur_gorge_mm
        else:
            D_hors = 60.0

    R_hors = D_hors / 2.0
    R_fond = d.diametre_fond_gorge_mm / 2.0 if d.diametre_fond_gorge_mm > 0 else 0.0
    R_cyl = d.diametre_interieur_cylindre_mm / 2.0 if d.diametre_interieur_cylindre_mm > 0 else 0.0
    R_joint_mean = d.diametre_moyen_joint_mm / 2.0 if d.diametre_moyen_joint_mm > 0 else 0.0

    if R_cyl > 0:
        ax.add_patch(Circle((0.0, 0.0), R_cyl, fill=False, linewidth=1.0, linestyle="--"))
    ax.add_patch(Circle((0.0, 0.0), R_hors, fill=False, linewidth=1.5))
    if R_fond > 0:
        ax.add_patch(Circle((0.0, 0.0), R_fond, fill=False, linewidth=1.0, linestyle="--"))
    if R_joint_mean > 0:
        ax.add_patch(Circle((0.0, 0.0), R_joint_mean, fill=False, linewidth=0.9, linestyle=":"))

    ax.axhline(0.0, **_linestyle_axis())
    ax.axvline(0.0, **_linestyle_axis())

    txt = [
        f"Ø hors gorge   = {_fmt_mm(D_hors)}",
        f"Ø fond gorge   = {_fmt_mm(d.diametre_fond_gorge_mm) if d.diametre_fond_gorge_mm > 0 else 'N/A'}",
        f"Ø moyen joint  = {_fmt_mm(d.diametre_moyen_joint_mm) if d.diametre_moyen_joint_mm > 0 else 'N/A'}",
        f"Ø cylindre     = {_fmt_mm(d.diametre_interieur_cylindre_mm) if d.diametre_interieur_cylindre_mm > 0 else 'N/A'}",
    ]

    lim = max(R_cyl, R_hors) + 24.0
    ax.text(
        -lim + 4.0,
        -lim + 4.0,
        "\n".join(txt),
        ha="left",
        va="bottom",
        fontsize=8.2,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Vue de face - diamètres caractéristiques")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _tracer_cartouche(ax, d: DonneesCroquisJointPiston):
    ax.set_title("Synthèse technique")
    ax.axis("off")

    lines = [
        f"Ø cylindre                        : {_fmt_mm(d.diametre_interieur_cylindre_mm) if d.diametre_interieur_cylindre_mm > 0 else 'N/A'}",
        f"ID joint                          : {_fmt_mm(d.diametre_interieur_joint_mm) if d.diametre_interieur_joint_mm > 0 else 'N/A'}",
        f"CS joint                          : {_fmt_mm(d.diametre_section_joint_mm) if d.diametre_section_joint_mm > 0 else 'N/A'}",
        f"Ø moyen joint                     : {_fmt_mm(d.diametre_moyen_joint_mm) if d.diametre_moyen_joint_mm > 0 else 'N/A'}",
        f"Périmètre moyen                   : {_fmt_mm(d.perimetre_moyen_joint_mm) if d.perimetre_moyen_joint_mm > 0 else 'N/A'}",
        f"Surface joint                     : {f'{d.surface_joint_m2:.6e} m²' if d.surface_joint_m2 > 0 else 'N/A'}",
        f"Volume joint                      : {_fmt_m3(d.volume_joint_m3) if d.volume_joint_m3 > 0 else 'N/A'}",
        f"Masse joint                       : {f'{d.masse_joint_kg:.6e} kg' if d.masse_joint_kg > 0 else 'N/A'}",
        "",
        f"Ø fond gorge                      : {_fmt_mm(d.diametre_fond_gorge_mm) if d.diametre_fond_gorge_mm > 0 else 'N/A'}",
        f"Profondeur gorge                  : {_fmt_mm(d.profondeur_gorge_mm) if d.profondeur_gorge_mm > 0 else 'N/A'}",
        f"Largeur gorge                     : {_fmt_mm(d.largeur_gorge_mm) if d.largeur_gorge_mm > 0 else 'N/A'}",
        f"Périmètre fond gorge              : {_fmt_mm(d.perimetre_fond_gorge_mm) if d.perimetre_fond_gorge_mm > 0 else 'N/A'}",
        f"Section gorge                     : {f'{d.section_gorge_m2:.6e} m²' if d.section_gorge_m2 > 0 else 'N/A'}",
        f"Volume gorge                      : {_fmt_m3(d.volume_gorge_m3) if d.volume_gorge_m3 > 0 else 'N/A'}",
        f"Taux remplissage                  : {f'{d.taux_remplissage:.6f}' if d.taux_remplissage > 0 else 'N/A'}",
        "",
        f"Ø montage stretch                 : {_fmt_mm(d.diametre_montage_stretch_mm) if d.diametre_montage_stretch_mm > 0 else 'N/A'}",
        f"Stretch                           : {f'{d.stretch_fraction:.6f}' if d.stretch_fraction else 'N/A'}",
        f"Hauteur radiale disponible        : {_fmt_mm(d.hauteur_radiale_disponible_mm) if d.hauteur_radiale_disponible_mm > 0 else 'N/A'}",
        f"Squeeze radial                    : {f'{d.squeeze_radial_fraction:.6f}' if d.squeeze_radial_fraction else 'N/A'}",
        "",
        f"Pression contact estimée          : {_fmt_pa(d.pression_contact_estimee_pa) if d.pression_contact_estimee_pa > 0 else 'N/A'}",
        f"Pression contact utilisée         : {_fmt_pa(d.pression_contact_utilisee_pa) if d.pression_contact_utilisee_pa > 0 else 'N/A'}",
        f"Coeff. frottement                 : {f'{d.coeff_frottement_mu:.6f}' if d.coeff_frottement_mu > 0 else 'N/A'}",
        f"Largeur bande contact             : {_fmt_mm(d.largeur_bande_contact_mm) if d.largeur_bande_contact_mm > 0 else 'N/A'}",
        f"Aire contact                      : {f'{d.aire_contact_m2:.6e} m²' if d.aire_contact_m2 > 0 else 'N/A'}",
        f"Effort normal estimé              : {_fmt_n(d.effort_normal_estime_n) if d.effort_normal_estime_n > 0 else 'N/A'}",
        f"Force frottement estimée          : {_fmt_n(d.force_frottement_estimee_n) if d.force_frottement_estimee_n > 0 else 'N/A'}",
        "",
        f"Pression diff.                    : {_fmt_pa(d.pression_diff_pa) if d.pression_diff_pa != 0 else 'N/A'}",
        f"Aire disque cylindre              : {f'{d.aire_reference_disque_cylindre_m2:.6e} m²' if d.aire_reference_disque_cylindre_m2 > 0 else 'N/A'}",
        f"Force pression équivalente        : {_fmt_n(d.force_pression_equivalente_n) if d.force_pression_equivalente_n > 0 else 'N/A'}",
        "",
        f"Nombre de rainures                : {d.nombre_rainures}",
        f"Squeeze > 0                       : {d.squeeze_positive}",
        f"Squeeze < 100%                    : {d.squeeze_moins_100pct}",
        f"Remplissage <= 1                  : {d.taux_remplissage_le_1}",
        f"Stretch >= 0                      : {d.stretch_non_negatif}",
    ]

    ax.text(
        0.02,
        0.98,
        "\n".join(lines),
        ha="left",
        va="top",
        fontsize=8.0,
        family="monospace",
        transform=ax.transAxes,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="black", linewidth=0.8),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_joint_piston_2d(
    joint: JointPiston,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Joint piston",
):
    d = extraire_donnees_croquis(joint)

    if (
        d.diametre_interieur_cylindre_mm <= 0
        and d.diametre_interieur_joint_mm <= 0
        and d.diametre_fond_gorge_mm <= 0
    ):
        raise ValueError("Impossible de tracer : aucune géométrie exploitable n'a été trouvée.")

    fig = plt.figure(figsize=(18, 11))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.55, 1.35], width_ratios=[1.4, 1.0])

    ax_long = fig.add_subplot(gs[0, :])
    ax_rad = fig.add_subplot(gs[1, 0])
    ax_face = fig.add_subplot(gs[1, 1])

    ax_cart = fig.add_axes([0.60, 0.09, 0.36, 0.34])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_longitudinale(ax_long, d)
    _tracer_coupe_radiale(ax_rad, d)
    _tracer_vue_face(ax_face, d)
    _tracer_cartouche(ax_cart, d)

    plt.tight_layout(rect=[0.0, 0.0, 1.0, 0.965])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, {
        "vue_longitudinale": ax_long,
        "coupe_radiale": ax_rad,
        "vue_face": ax_face,
        "cartouche": ax_cart,
    }, d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

if __name__ == "__main__":
    jp = JointPiston(
        rapport_piston=None,
        diametre_interieur_cylindre_m=0.080,
        diametre_interieur_joint_m=0.074,
        diametre_section_joint_m=0.003,
        diametre_fond_gorge_m=0.077,
        profondeur_gorge_m=0.0012,
        largeur_gorge_m=0.0045,
        largeur_bande_contact_m=0.003,
        coeff_frottement_mu=0.15,
        pression_contact_pa=2e6,
        materiau_joint_cle="nbr_70",
    )

    tracer_croquis_joint_piston_2d(
        jp,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Joint piston",
    )