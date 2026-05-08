# frontend/pieces/sketches_2d/joint_deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D

from backend.components.moteur_thermique.pieces.joint_deplaceur import JointDeplaceur


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
class DonneesCroquisJointDeplaceur:
    diametre_deplaceur_mm: float = 0.0
    longueur_deplaceur_mm: float = 0.0
    alesage_cylindre_mm: float = 0.0
    jeu_radial_mm: float = 0.0
    nb_joints: int = 0

    section_joint_mm: float = 0.0
    squeeze: float = 0.0
    facteur_largeur: float = 0.0

    largeur_gorge_mm: float = 0.0
    profondeur_gorge_mm: float = 0.0
    diametre_fond_gorge_mm: float = 0.0
    rayon_fond_gorge_mm: float = 0.0
    diametre_centreline_joint_mm: float = 0.0
    protrusion_radiale_mm: float = 0.0

    positions_axiales_rainures_mm: Optional[List[float]] = None

    pression_service_pa: float = 0.0
    module_elastomere_pa: float = 0.0
    module_min_pa: float = 0.0
    pression_contact_estimee_pa: float = 0.0
    marge_p_contact_vs_service: float = 0.0

    coeff_frottement: float = 0.0
    largeur_bande_contact_mm: float = 0.0
    perimetre_contact_mm: float = 0.0
    aire_contact_m2: float = 0.0
    force_frottement_n: float = 0.0

    volume_gorge_unitaire_m3: float = 0.0
    volume_gorges_total_m3: float = 0.0
    volume_joint_unitaire_m3: float = 0.0
    volume_joints_total_m3: float = 0.0
    taux_remplissage: float = 0.0

    compatibilite_ok: Optional[bool] = None
    protrusion_ok: Optional[bool] = None
    gap_residuel_mm: float = 0.0
    remplissage_ok: Optional[bool] = None

    orientation: str = ""
    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(joint: JointDeplaceur) -> DonneesCroquisJointDeplaceur:
    rap = joint.analyser(strict=False)

    geo = rap.get("geometrie", {})
    gorge = rap.get("gorge", {})
    serv = rap.get("service", {})
    elast = rap.get("elasticite", {})
    frot = rap.get("frottement", {})
    verif = rap.get("verifications", {})
    cao = rap.get("cao", {})
    ent = rap.get("entrees", {})

    positions = gorge.get("positions_axiales_rainures_m")
    if isinstance(positions, list):
        positions_mm = [_mm(x) for x in positions]
    else:
        positions_mm = None

    return DonneesCroquisJointDeplaceur(
        diametre_deplaceur_mm=_mm(_get_nested(ent, "diametre_deplaceur_m", default=0.0)),
        longueur_deplaceur_mm=_mm(_get_nested(ent, "longueur_deplaceur_m", default=0.0)),
        alesage_cylindre_mm=_mm(_get_nested(ent, "alesage_cylindre_m", default=0.0)),
        jeu_radial_mm=_mm(_get_nested(ent, "jeu_radial_m", default=0.0)),
        nb_joints=int(_safe_float(_get_nested(ent, "nb_joints", default=0), 0)),

        section_joint_mm=_safe_float(_get_nested(ent, "section_joint_mm", default=0.0)),
        squeeze=_safe_float(_get_nested(ent, "squeeze", default=0.0)),
        facteur_largeur=_safe_float(_get_nested(ent, "facteur_largeur", default=0.0)),

        largeur_gorge_mm=_mm(_get_nested(gorge, "largeur_gorge_axiale_m", default=0.0)),
        profondeur_gorge_mm=_mm(_get_nested(gorge, "profondeur_gorge_radiale_m", default=0.0)),
        diametre_fond_gorge_mm=_mm(_get_nested(gorge, "diametre_fond_gorge_m", default=0.0)),
        rayon_fond_gorge_mm=_mm(_get_nested(gorge, "rayon_fond_gorge_m", default=0.0)),
        diametre_centreline_joint_mm=_mm(_get_nested(gorge, "diametre_centreline_joint_m", default=0.0)),
        protrusion_radiale_mm=_mm(_get_nested(gorge, "protrusion_radiale_theorique_m", default=0.0)),

        positions_axiales_rainures_mm=positions_mm,

        pression_service_pa=_safe_float(_get_nested(serv, "pression_service_pa", default=0.0)),
        module_elastomere_pa=_safe_float(_get_nested(elast, "module_elastomere_pa", default=0.0)),
        module_min_pa=_safe_float(_get_nested(elast, "module_min_pour_p_contact_ge_p_service_pa", default=0.0)),
        pression_contact_estimee_pa=_safe_float(_get_nested(elast, "pression_contact_estimee_pa", default=0.0)),
        marge_p_contact_vs_service=_safe_float(_get_nested(elast, "marge_p_contact_vs_service", default=0.0)),

        coeff_frottement=_safe_float(_get_nested(ent, "coeff_frottement", default=0.0)),
        largeur_bande_contact_mm=_mm(_get_nested(ent, "largeur_bande_contact_m", default=0.0)),
        perimetre_contact_mm=_mm(_get_nested(frot, "perimetre_contact_m", default=0.0)),
        aire_contact_m2=_safe_float(_get_nested(frot, "aire_contact_m2", default=0.0)),
        force_frottement_n=_safe_float(_get_nested(frot, "force_frottement_N", default=0.0)),

        volume_gorge_unitaire_m3=_safe_float(_get_nested(geo, "volume_gorge_unitaire_m3", default=0.0)),
        volume_gorges_total_m3=_safe_float(_get_nested(geo, "volume_gorges_total_m3", default=0.0)),
        volume_joint_unitaire_m3=_safe_float(_get_nested(geo, "volume_joint_unitaire_approx_m3", default=0.0)),
        volume_joints_total_m3=_safe_float(_get_nested(geo, "volume_joints_total_approx_m3", default=0.0)),
        taux_remplissage=_safe_float(_get_nested(geo, "taux_remplissage_gorge_approx", default=0.0)),

        compatibilite_ok=_get_nested(verif, "compatibilite_cylindre_deplaceur", "ok_si_alesage_superieur", default=None),
        protrusion_ok=_get_nested(verif, "protrusion_compatible_avec_jeu", default=None),
        gap_residuel_mm=_mm(_get_nested(verif, "gap_radial_residuel_apres_contact_m", default=0.0)),
        remplissage_ok=_get_nested(verif, "taux_remplissage_gorge_acceptable", default=None),

        orientation=str(_get_nested(cao, "orientation", default="")),
        rapport_complet=rap,
    )


# ============================================================
# VUE LONGITUDINALE DU DÉPLACEUR AVEC RAINURES
# ============================================================

def _tracer_vue_longitudinale(ax, d: DonneesCroquisJointDeplaceur):
    if d.diametre_deplaceur_mm <= 0 or d.longueur_deplaceur_mm <= 0:
        ax.text(0.5, 0.5, "Dimensions principales indisponibles", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue longitudinale")
        ax.set_axis_off()
        return

    D_dep = d.diametre_deplaceur_mm
    L_dep = d.longueur_deplaceur_mm
    y_dep = D_dep / 2.0

    ax.add_patch(Rectangle((0.0, -y_dep), L_dep, D_dep, fill=False, linewidth=1.5))
    ax.axhline(0.0, **_linestyle_axis())

    # Rainures
    if d.positions_axiales_rainures_mm and d.largeur_gorge_mm > 0 and d.profondeur_gorge_mm > 0:
        for i, xc in enumerate(d.positions_axiales_rainures_mm, start=1):
            x0 = xc - 0.5 * d.largeur_gorge_mm
            w = d.largeur_gorge_mm
            p = d.profondeur_gorge_mm

            # gorge haute
            ax.add_patch(
                Rectangle(
                    (x0, y_dep - p),
                    w,
                    p,
                    fill=False,
                    linewidth=1.0,
                    linestyle="--",
                )
            )
            # gorge basse
            ax.add_patch(
                Rectangle(
                    (x0, -y_dep),
                    w,
                    p,
                    fill=False,
                    linewidth=1.0,
                    linestyle="--",
                )
            )

            _annotate_leader(
                ax,
                x0 + 2.0,
                y_dep + 18.0 + (i - 1) * 10.0,
                xc,
                y_dep - 0.5 * p,
                f"Rainure {i}",
            )

    # alésage cylindre si connu
    if d.alesage_cylindre_mm > 0:
        y_cyl = d.alesage_cylindre_mm / 2.0
        ax.add_line(Line2D([0.0, L_dep], [y_cyl, y_cyl], **_linestyle_hidden()))
        ax.add_line(Line2D([0.0, L_dep], [-y_cyl, -y_cyl], **_linestyle_hidden()))

    # Cotes
    ydim1 = y_dep + 18.0
    ydim2 = ydim1 + 14.0

    _add_dimension_h(ax, 0.0, L_dep, 0.0, ydim1, f"L déplaceur = {_fmt_mm(L_dep)}")

    if d.positions_axiales_rainures_mm and len(d.positions_axiales_rainures_mm) >= 1:
        xc0 = d.positions_axiales_rainures_mm[0]
        _add_dimension_h(ax, 0.0, xc0, 0.0, ydim2, f"x rainure 1 = {_fmt_mm(xc0)}")

    xdim1 = L_dep + 18.0
    xdim2 = L_dep + 36.0
    xdim3 = L_dep + 54.0

    _add_dimension_v(ax, 0.0, xdim1, -y_dep, y_dep, f"Ø déplaceur = {_fmt_mm(D_dep)}")

    if d.alesage_cylindre_mm > 0:
        y_cyl = d.alesage_cylindre_mm / 2.0
        _add_dimension_v(ax, 0.0, xdim2, -y_cyl, y_cyl, f"Ø cylindre = {_fmt_mm(d.alesage_cylindre_mm)}")

    if d.largeur_gorge_mm > 0:
        xg = (d.positions_axiales_rainures_mm[0] - 0.5 * d.largeur_gorge_mm) if d.positions_axiales_rainures_mm else 0.0
        _add_dimension_h(ax, xg, xg + d.largeur_gorge_mm, y_dep, ydim2 + 14.0, f"L gorge = {_fmt_mm(d.largeur_gorge_mm)}")

    infos = [
        f"Nb joints        : {d.nb_joints}",
        f"Section joint    : {d.section_joint_mm:.3f} mm",
        f"Squeeze          : {d.squeeze:.6f}",
        f"Facteur largeur  : {d.facteur_largeur:.6f}",
    ]
    if d.jeu_radial_mm > 0:
        infos.append(f"Jeu radial       : {_fmt_mm(d.jeu_radial_mm)}")
    if d.protrusion_radiale_mm > 0:
        infos.append(f"Protrusion       : {_fmt_mm(d.protrusion_radiale_mm)}")

    ax.text(
        0.0,
        -(y_dep + 28.0),
        "\n".join(infos),
        ha="left",
        va="top",
        fontsize=8.4,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Vue longitudinale du déplaceur et des rainures")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-10.0, L_dep + 90.0)
    ax.set_ylim(-(max(d.alesage_cylindre_mm, D_dep) / 2.0 + 55.0), max(d.alesage_cylindre_mm, D_dep) / 2.0 + 60.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# COUPE RADIALE DÉTAILLÉE D'UNE GORGE
# ============================================================

def _tracer_coupe_radiale(ax, d: DonneesCroquisJointDeplaceur):
    if d.diametre_deplaceur_mm <= 0:
        ax.text(0.5, 0.5, "Diamètre déplaceur indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Coupe radiale")
        ax.set_axis_off()
        return

    R_dep = d.diametre_deplaceur_mm / 2.0
    R_fond = d.diametre_fond_gorge_mm / 2.0 if d.diametre_fond_gorge_mm > 0 else 0.0
    R_cyl = d.alesage_cylindre_mm / 2.0 if d.alesage_cylindre_mm > 0 else 0.0
    p = d.profondeur_gorge_mm
    sec = d.section_joint_mm

    # contour cylindre si connu
    if R_cyl > 0:
        ax.add_patch(Circle((0.0, 0.0), R_cyl, fill=False, linewidth=1.0, linestyle="--"))

    # contour déplaceur extérieur
    ax.add_patch(Circle((0.0, 0.0), R_dep, fill=False, linewidth=1.5))

    # fond de gorge
    if R_fond > 0:
        ax.add_patch(Circle((0.0, 0.0), R_fond, fill=False, linewidth=1.0, linestyle="--"))

    # joint schématique sur génératrice supérieure
    if R_fond > 0 and sec > 0:
        r_joint = 0.5 * sec
        centre_joint = (0.0, R_fond + r_joint)
        ax.add_patch(Circle(centre_joint, r_joint, fill=False, linewidth=1.2))

        _annotate_leader(ax, R_dep + 18.0, R_dep * 0.55, centre_joint[0], centre_joint[1], "Section de joint")

    ax.axhline(0.0, **_linestyle_axis())
    ax.axvline(0.0, **_linestyle_axis())

    # Cotes
    xdim1 = R_cyl + 18.0 if R_cyl > 0 else R_dep + 18.0
    xdim2 = xdim1 + 18.0
    xdim3 = xdim2 + 18.0

    _add_dimension_v(ax, 0.0, xdim1, -R_dep, R_dep, f"Ø dép = {_fmt_mm(d.diametre_deplaceur_mm)}")

    if R_fond > 0:
        _add_dimension_v(ax, 0.0, xdim2, -R_fond, R_fond, f"Ø fond = {_fmt_mm(d.diametre_fond_gorge_mm)}")

    if R_cyl > 0:
        _add_dimension_v(ax, 0.0, xdim3, -R_cyl, R_cyl, f"Ø alésage = {_fmt_mm(d.alesage_cylindre_mm)}")

    txt = [
        f"Profondeur gorge : {_fmt_mm(d.profondeur_gorge_mm) if d.profondeur_gorge_mm > 0 else 'N/A'}",
        f"Rayon fond       : {_fmt_mm(d.rayon_fond_gorge_mm) if d.rayon_fond_gorge_mm > 0 else 'N/A'}",
        f"Section joint    : {d.section_joint_mm:.3f} mm" if d.section_joint_mm > 0 else "Section joint    : N/A",
        f"Protrusion       : {_fmt_mm(d.protrusion_radiale_mm) if d.protrusion_radiale_mm > 0 else 'N/A'}",
        f"Jeu radial       : {_fmt_mm(d.jeu_radial_mm) if d.jeu_radial_mm > 0 else 'N/A'}",
    ]

    ax.text(
        -R_dep,
        -max(R_cyl, R_dep) - 16.0,
        "\n".join(txt),
        ha="left",
        va="top",
        fontsize=8.4,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Coupe radiale d'une gorge et du joint")
    lim = max(R_cyl, R_dep) + 45.0
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim + 30.0)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE DE FACE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisJointDeplaceur):
    if d.diametre_deplaceur_mm <= 0:
        ax.text(0.5, 0.5, "Diamètre déplaceur indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de face")
        ax.set_axis_off()
        return

    R_dep = d.diametre_deplaceur_mm / 2.0
    R_fond = d.diametre_fond_gorge_mm / 2.0 if d.diametre_fond_gorge_mm > 0 else 0.0
    R_cyl = d.alesage_cylindre_mm / 2.0 if d.alesage_cylindre_mm > 0 else 0.0
    R_cent = d.diametre_centreline_joint_mm / 2.0 if d.diametre_centreline_joint_mm > 0 else 0.0

    if R_cyl > 0:
        ax.add_patch(Circle((0.0, 0.0), R_cyl, fill=False, linewidth=1.0, linestyle="--"))
    ax.add_patch(Circle((0.0, 0.0), R_dep, fill=False, linewidth=1.5))
    if R_fond > 0:
        ax.add_patch(Circle((0.0, 0.0), R_fond, fill=False, linewidth=1.0, linestyle="--"))
    if R_cent > 0:
        ax.add_patch(Circle((0.0, 0.0), R_cent, fill=False, linewidth=0.9, linestyle=":"))

    ax.axhline(0.0, **_linestyle_axis())
    ax.axvline(0.0, **_linestyle_axis())

    txt = [
        f"Ø dép           = {_fmt_mm(d.diametre_deplaceur_mm)}",
        f"Ø fond gorge    = {_fmt_mm(d.diametre_fond_gorge_mm)}" if d.diametre_fond_gorge_mm > 0 else "Ø fond gorge    = N/A",
        f"Ø centreline    = {_fmt_mm(d.diametre_centreline_joint_mm)}" if d.diametre_centreline_joint_mm > 0 else "Ø centreline    = N/A",
        f"Ø alésage cyl.  = {_fmt_mm(d.alesage_cylindre_mm)}" if d.alesage_cylindre_mm > 0 else "Ø alésage cyl.  = N/A",
    ]

    lim = max(R_cyl, R_dep) + 24.0
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

def _tracer_cartouche(ax, d: DonneesCroquisJointDeplaceur):
    ax.set_title("Synthèse technique")
    ax.axis("off")

    lines = [
        f"Orientation                       : {d.orientation or 'N/A'}",
        f"Nb joints                         : {d.nb_joints if d.nb_joints >= 0 else 'N/A'}",
        f"Ø déplaceur                       : {_fmt_mm(d.diametre_deplaceur_mm) if d.diametre_deplaceur_mm > 0 else 'N/A'}",
        f"L déplaceur                       : {_fmt_mm(d.longueur_deplaceur_mm) if d.longueur_deplaceur_mm > 0 else 'N/A'}",
        f"Ø alésage cylindre                : {_fmt_mm(d.alesage_cylindre_mm) if d.alesage_cylindre_mm > 0 else 'N/A'}",
        f"Jeu radial                        : {_fmt_mm(d.jeu_radial_mm) if d.jeu_radial_mm > 0 else 'N/A'}",
        "",
        f"Section joint                     : {f'{d.section_joint_mm:.3f} mm' if d.section_joint_mm > 0 else 'N/A'}",
        f"Squeeze                           : {f'{d.squeeze:.6f}' if d.squeeze > 0 else 'N/A'}",
        f"Facteur largeur                   : {f'{d.facteur_largeur:.6f}' if d.facteur_largeur > 0 else 'N/A'}",
        f"Largeur gorge                     : {_fmt_mm(d.largeur_gorge_mm) if d.largeur_gorge_mm > 0 else 'N/A'}",
        f"Profondeur gorge                  : {_fmt_mm(d.profondeur_gorge_mm) if d.profondeur_gorge_mm > 0 else 'N/A'}",
        f"Ø fond gorge                      : {_fmt_mm(d.diametre_fond_gorge_mm) if d.diametre_fond_gorge_mm > 0 else 'N/A'}",
        f"Rayon fond gorge                  : {_fmt_mm(d.rayon_fond_gorge_mm) if d.rayon_fond_gorge_mm > 0 else 'N/A'}",
        f"Ø centreline joint                : {_fmt_mm(d.diametre_centreline_joint_mm) if d.diametre_centreline_joint_mm > 0 else 'N/A'}",
        f"Protrusion radiale                : {_fmt_mm(d.protrusion_radiale_mm) if d.protrusion_radiale_mm > 0 else 'N/A'}",
        "",
        f"Pression service                  : {_fmt_pa(d.pression_service_pa) if d.pression_service_pa > 0 else 'N/A'}",
        f"Module mini requis                : {_fmt_pa(d.module_min_pa) if d.module_min_pa > 0 else 'N/A'}",
        f"Module élastomère                 : {_fmt_pa(d.module_elastomere_pa) if d.module_elastomere_pa > 0 else 'N/A'}",
        f"Pression contact estimée          : {_fmt_pa(d.pression_contact_estimee_pa) if d.pression_contact_estimee_pa > 0 else 'N/A'}",
        f"Marge p_contact / p_service       : {f'{d.marge_p_contact_vs_service:.6f}' if d.marge_p_contact_vs_service > 0 else 'N/A'}",
        "",
        f"Coeff. frottement                 : {f'{d.coeff_frottement:.6f}' if d.coeff_frottement > 0 else 'N/A'}",
        f"Largeur bande contact             : {_fmt_mm(d.largeur_bande_contact_mm) if d.largeur_bande_contact_mm > 0 else 'N/A'}",
        f"Périmètre contact                 : {_fmt_mm(d.perimetre_contact_mm) if d.perimetre_contact_mm > 0 else 'N/A'}",
        f"Aire contact                      : {f'{d.aire_contact_m2:.6e} m²' if d.aire_contact_m2 > 0 else 'N/A'}",
        f"Force frottement                  : {_fmt_n(d.force_frottement_n) if d.force_frottement_n > 0 else 'N/A'}",
        "",
        f"Volume gorge unitaire             : {_fmt_m3(d.volume_gorge_unitaire_m3) if d.volume_gorge_unitaire_m3 > 0 else 'N/A'}",
        f"Volume gorges total               : {_fmt_m3(d.volume_gorges_total_m3) if d.volume_gorges_total_m3 > 0 else 'N/A'}",
        f"Volume joint unitaire             : {_fmt_m3(d.volume_joint_unitaire_m3) if d.volume_joint_unitaire_m3 > 0 else 'N/A'}",
        f"Volume joints total               : {_fmt_m3(d.volume_joints_total_m3) if d.volume_joints_total_m3 > 0 else 'N/A'}",
        f"Taux remplissage                  : {f'{d.taux_remplissage:.6f}' if d.taux_remplissage > 0 else 'N/A'}",
        "",
        f"Compatibilité cylindre/déplaceur  : {d.compatibilite_ok}",
        f"Protrusion compatible avec jeu    : {d.protrusion_ok}",
        f"Gap radial résiduel               : {_fmt_mm(d.gap_residuel_mm) if d.gap_residuel_mm >= 0 else 'N/A'}",
        f"Remplissage acceptable            : {d.remplissage_ok}",
    ]

    ax.text(
        0.02,
        0.98,
        "\n".join(lines),
        ha="left",
        va="top",
        fontsize=8.1,
        family="monospace",
        transform=ax.transAxes,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="black", linewidth=0.8),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_joint_deplaceur_2d(
    joint: JointDeplaceur,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Joint de déplaceur",
):
    d = extraire_donnees_croquis(joint)

    if d.diametre_deplaceur_mm <= 0:
        raise ValueError("Impossible de tracer : diamètre de déplaceur indisponible.")

    fig = plt.figure(figsize=(18, 11))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.55, 1.35], width_ratios=[1.4, 1.0])

    ax_long = fig.add_subplot(gs[0, :])
    ax_rad = fig.add_subplot(gs[1, 0])
    ax_face = fig.add_subplot(gs[1, 1])

    # cartouche en encart flottant
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
    j = JointDeplaceur(
        diametre_deplaceur_m=0.080,
        longueur_deplaceur_m=0.120,
        alesage_cylindre_m=0.0804,
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur=1.5,
        pression_service_pa=150_000.0,
        module_elastomere_pa=7e6,
        coeff_frottement=0.15,
        largeur_bande_contact_m=0.003,
    )

    tracer_croquis_joint_deplaceur_2d(
        j,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Joint de déplaceur",
    )