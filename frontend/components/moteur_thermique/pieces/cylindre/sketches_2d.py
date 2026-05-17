"""
Chemin : frontend/components/moteur_thermique/pieces/cylindre/sketches_2d.py
But : Définition des esquisses géométriques 2D de la pièce.
"""

# frontend/pieces/sketches_2d/cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
from matplotlib.lines import Line2D

from backend.components.moteur_thermique.pieces.cylindre import Cylindre


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
    return f"{v:.2f} Pa"


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
# HACHURES
# ============================================================

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


def _add_hatched_polygon(ax, pts: List[Tuple[float, float]], hatch: str = "////", lw: float = 0.9):
    if not pts:
        return
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
# EXTRACTION DES DONNÉES CALCULÉES
# ============================================================

@dataclass
class DonneesCroquisCylindre:
    # géométrie principale
    alesage_mm: float
    diametre_exterieur_mm: float
    epaisseur_mm: float
    longueur_utile_mm: float
    longueur_totale_mm: float

    # brides
    bride_epaisseur_mm: float = 0.0
    bride_largeur_radiale_mm: float = 0.0
    bride_diametre_exterieur_mm: float = 0.0

    # perçages
    nb_trous: int = 0
    diametre_trou_mm: float = 0.0
    diametre_cercle_percage_mm: float = 0.0
    angles_deg: Optional[List[float]] = None

    # gorge
    gorge_largeur_mm: float = 0.0
    gorge_profondeur_mm: float = 0.0
    gorge_diametre_moyen_joint_mm: float = 0.0
    gorge_diametre_tore_mm: float = 0.0
    gorge_taux_ecrasement: float = 0.0

    # détails fabrication
    chanfrein_entree_piston_mm: float = 0.0
    chanfrein_exterieur_mm: float = 0.0
    rayon_conge_mm: float = 0.0
    jeu_piston_cylindre_mm: float = 0.0

    # efforts
    force_pression_service_N: float = 0.0
    force_pression_max_N: float = 0.0
    force_separation_N: float = 0.0
    force_joint_N: float = 0.0
    force_precharge_totale_N: float = 0.0
    force_precharge_par_vis_N: float = 0.0
    couple_serrage_par_vis_Nm: float = 0.0

    # visserie
    filetage_txt: str = ""
    as_mm2: float = 0.0

    # masse / inerties
    masse_kg: float = 0.0
    volume_metal_m3: float = 0.0
    volume_brides_m3: float = 0.0
    inertie_I_m4: float = 0.0
    inertie_J_m4: float = 0.0

    # contraintes / vérifs
    sigma_cerclage_mince_pa: float = 0.0
    sigma_vm_lame_pa: float = 0.0
    note_paroi_mince: str = ""

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(cylindre: Cylindre) -> DonneesCroquisCylindre:
    rapport = cylindre.analyser(strict=False)

    geo = rapport.get("geometrie", {})
    dim = rapport.get("dimensionnement", {})
    ass = rapport.get("assemblage", {})
    contraintes = rapport.get("contraintes", {})
    masse = rapport.get("masse", {})
    inerties = rapport.get("inerties", {})
    verif = rapport.get("verifications", {})

    alesage_m = _get_nested(rapport, "entrees", "alesage_m", default=0.0)
    longueur_utile_m = _get_nested(rapport, "entrees", "longueur_utile_m", default=0.0)

    diametre_exterieur_m = _get_nested(geo, "diametre_externe_m", default=0.0)
    epaisseur_m = _get_nested(dim, "epaisseur_retenue_m", default=0.0)

    cao = _get_nested(geo, "cao", default={}) or {}
    bride = cao.get("bride", {}) if isinstance(cao, dict) else {}
    gorge = cao.get("gorge_joint", {}) if isinstance(cao, dict) else {}
    visserie = cao.get("visserie", {}) if isinstance(cao, dict) else {}

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

        nb_trous=int(_get_nested(bride, "nb_trous", default=0) or 0),
        diametre_trou_mm=_mm(_get_nested(bride, "diametre_trou_m", default=0.0)),
        diametre_cercle_percage_mm=_mm(_get_nested(bride, "diametre_cercle_percage_m", default=0.0)),
        angles_deg=_get_nested(bride, "angles_deg", default=[]),

        gorge_largeur_mm=_mm(_get_nested(gorge, "largeur_gorge_m", default=0.0)),
        gorge_profondeur_mm=_mm(_get_nested(gorge, "profondeur_gorge_m", default=0.0)),
        gorge_diametre_moyen_joint_mm=_mm(_get_nested(gorge, "diametre_moyen_joint_m", default=0.0)),
        gorge_diametre_tore_mm=_mm(_get_nested(gorge, "diametre_tore_m", default=0.0)),
        gorge_taux_ecrasement=_safe_float(_get_nested(gorge, "taux_ecrasement_cible", default=0.0)),

        chanfrein_entree_piston_mm=_mm(_get_nested(cao, "chanfrein_entree_piston_m", default=0.0)),
        chanfrein_exterieur_mm=_mm(_get_nested(cao, "chanfrein_exterieur_m", default=0.0)),
        rayon_conge_mm=_mm(_get_nested(cao, "rayon_conge_m", default=0.0)),
        jeu_piston_cylindre_mm=_mm(_get_nested(cao, "jeu_piston_cylindre_m", default=0.0)),

        force_pression_service_N=_safe_float(_get_nested(dim, "force_pression_piston_service_N", default=0.0)),
        force_pression_max_N=_safe_float(_get_nested(dim, "force_pression_piston_max_N", default=0.0)),
        force_separation_N=_safe_float(_get_nested(ass, "force_separation_N", default=0.0)),
        force_joint_N=_safe_float(_get_nested(ass, "force_joint_N", default=0.0)),
        force_precharge_totale_N=_safe_float(_get_nested(ass, "force_precharge_totale_requise_N", default=0.0)),
        force_precharge_par_vis_N=_safe_float(_get_nested(visserie, "force_precharge_par_vis_N", default=0.0)),
        couple_serrage_par_vis_Nm=_safe_float(_get_nested(visserie, "couple_serrage_par_vis_Nm", default=0.0)),

        filetage_txt=str(_get_nested(visserie, "taraudage", default="") or ""),
        as_mm2=_safe_float(_get_nested(visserie, "As_mm2", default=0.0)),

        masse_kg=_safe_float(_get_nested(masse, "masse_kg", default=0.0))
        + _safe_float(_get_nested(masse, "masse_brides_kg", default=0.0)),
        volume_metal_m3=_safe_float(_get_nested(masse, "volume_metal_m3", default=0.0)),
        volume_brides_m3=_safe_float(_get_nested(masse, "volume_brides_m3", default=0.0)),
        inertie_I_m4=_safe_float(_get_nested(inerties, "inertie_flexion_I_m4", default=0.0)),
        inertie_J_m4=_safe_float(_get_nested(inerties, "inertie_polaire_J_m4", default=0.0)),

        sigma_cerclage_mince_pa=_safe_float(_get_nested(contraintes, "sigma_cerclage_mince_pa", default=0.0)),
        sigma_vm_lame_pa=_safe_float(_get_nested(contraintes, "sigma_von_mises_lame_au_ri_pa", default=0.0)),
        note_paroi_mince=str(_get_nested(verif, "note_paroi_mince", default="") or ""),

        rapport_complet=rapport,
    )


# ============================================================
# VUE DE CÔTÉ DÉTAILLÉE
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisCylindre):
    L_util = d.longueur_utile_mm
    L_tot = d.longueur_totale_mm
    D_int = d.alesage_mm
    D_ext = d.diametre_exterieur_mm
    D_bride = d.bride_diametre_exterieur_mm if d.bride_diametre_exterieur_mm > 0 else D_ext
    e_bride = d.bride_epaisseur_mm

    y_int = D_int / 2.0
    y_ext = D_ext / 2.0
    y_bride = D_bride / 2.0

    x0 = 0.0
    x1 = e_bride
    x2 = x1 + L_util
    x3 = x2 + e_bride if e_bride > 0 else L_tot

    # -------------------------
    # Matière hachurée
    # -------------------------
    if e_bride > 0:
        # bride avant - partie haute
        _add_hatched_rect(ax, x0, y_ext, e_bride, y_bride - y_ext)
        _add_hatched_rect(ax, x0, -y_bride, e_bride, y_bride - y_ext)

        # bride arrière - partie haute
        _add_hatched_rect(ax, x2, y_ext, e_bride, y_bride - y_ext)
        _add_hatched_rect(ax, x2, -y_bride, e_bride, y_bride - y_ext)

        # virole principale - haut / bas
        _add_hatched_rect(ax, x1, y_int, L_util, y_ext - y_int)
        _add_hatched_rect(ax, x1, -y_ext, L_util, y_ext - y_int)
    else:
        _add_hatched_rect(ax, x0, y_int, L_util, y_ext - y_int)
        _add_hatched_rect(ax, x0, -y_ext, L_util, y_ext - y_int)
        x1 = 0.0
        x2 = L_util
        x3 = L_util

    # -------------------------
    # Contours principaux
    # -------------------------
    if e_bride > 0:
        # brides
        ax.add_patch(Rectangle((x0, -y_bride), e_bride, D_bride, fill=False, linewidth=1.4))
        ax.add_patch(Rectangle((x2, -y_bride), e_bride, D_bride, fill=False, linewidth=1.4))

        # fût externe
        ax.add_patch(Rectangle((x1, -y_ext), L_util, D_ext, fill=False, linewidth=1.6))

        # alésage interne
        ax.add_patch(Rectangle((x1, -y_int), L_util, D_int, fill=False, linewidth=1.2))

        # raccords bride/fût
        ax.add_line(Line2D([x1, x1], [-y_bride, -y_ext], linewidth=1.2, color="black"))
        ax.add_line(Line2D([x1, x1], [y_ext, y_bride], linewidth=1.2, color="black"))
        ax.add_line(Line2D([x2, x2], [-y_bride, -y_ext], linewidth=1.2, color="black"))
        ax.add_line(Line2D([x2, x2], [y_ext, y_bride], linewidth=1.2, color="black"))
    else:
        ax.add_patch(Rectangle((x0, -y_ext), L_util, D_ext, fill=False, linewidth=1.6))
        ax.add_patch(Rectangle((x0, -y_int), L_util, D_int, fill=False, linewidth=1.2))

    # -------------------------
    # Axe et lignes cachées
    # -------------------------
    ax.axhline(0, **_linestyle_axe())

    # plans de face
    ax.add_line(Line2D([x0, x0], [-y_bride, y_bride], **_linestyle_hidden()))
    ax.add_line(Line2D([x3, x3], [-y_bride, y_bride], **_linestyle_hidden()))

    # -------------------------
    # Gorge de joint
    # -------------------------
    if d.gorge_largeur_mm > 0 and d.gorge_profondeur_mm > 0 and e_bride > 0:
        gorge_x = x0 + 0.55 * e_bride
        # gorge haute
        ax.add_patch(
            Rectangle(
                (gorge_x, y_int),
                d.gorge_largeur_mm,
                d.gorge_profondeur_mm,
                fill=False,
                linewidth=1.0,
                linestyle=(0, (4, 4)),
            )
        )
        # gorge basse
        ax.add_patch(
            Rectangle(
                (gorge_x, -(y_int + d.gorge_profondeur_mm)),
                d.gorge_largeur_mm,
                d.gorge_profondeur_mm,
                fill=False,
                linewidth=1.0,
                linestyle=(0, (4, 4)),
            )
        )

        _annotate_leader(
            ax,
            x0 - 65.0,
            y_bride + 18.0,
            gorge_x + d.gorge_largeur_mm / 2.0,
            y_int + d.gorge_profondeur_mm / 2.0,
            "Gorge joint",
        )

    # -------------------------
    # Annotations mécaniques
    # -------------------------
    _annotate_leader(ax, x1 + 10.0, y_ext + 18.0, x1 + 20.0, y_ext, "Fût externe")
    _annotate_leader(ax, x1 + 10.0, -y_int - 18.0, x1 + 20.0, -y_int, "Alésage")
    if e_bride > 0:
        _annotate_leader(ax, x0 - 55.0, y_bride - 8.0, x0 + e_bride / 2.0, y_bride - 2.0, "Bride avant")
        _annotate_leader(ax, x3 + 10.0, y_bride - 8.0, x2 + e_bride / 2.0, y_bride - 2.0, "Bride arrière")

    # -------------------------
    # Cotes
    # -------------------------
    cote_y_1 = y_bride + 15.0
    cote_y_2 = y_bride + 30.0
    cote_y_3 = y_bride + 45.0
    cote_y_4 = y_bride + 60.0

    _add_dimension_h(ax, x1, x2, 0.0, cote_y_1, f"L utile = {_fmt_mm(L_util)}")
    _add_dimension_h(ax, x0, x3, 0.0, cote_y_2, f"L totale = {_fmt_mm(L_tot)}")

    if e_bride > 0:
        _add_dimension_h(ax, x0, x1, 0.0, cote_y_3, f"e bride = {_fmt_mm(e_bride)}")
        _add_dimension_h(ax, x2, x3, 0.0, cote_y_4, f"e bride = {_fmt_mm(e_bride)}")

    cote_x_1 = x3 + 20.0
    cote_x_2 = x3 + 40.0
    cote_x_3 = x3 + 60.0

    _add_dimension_v(ax, 0.0, cote_x_1, -y_int, y_int, f"Ø alésage = {_fmt_mm(D_int)}")
    _add_dimension_v(ax, 0.0, cote_x_2, -y_ext, y_ext, f"Ø ext = {_fmt_mm(D_ext)}")
    if D_bride > D_ext:
        _add_dimension_v(ax, 0.0, cote_x_3, -y_bride, y_bride, f"Ø bride = {_fmt_mm(D_bride)}")

    # cote épaisseur locale
    if d.epaisseur_mm > 0:
        x_ep = x1 + 0.22 * L_util
        ax.annotate(
            "",
            xy=(x_ep, y_int),
            xytext=(x_ep, y_ext),
            arrowprops=dict(arrowstyle="<->", linewidth=1.0, color="black"),
        )
        ax.text(x_ep + 4.0, (y_int + y_ext) / 2.0, f"e = {_fmt_mm(d.epaisseur_mm)}", fontsize=9, va="center")

    # -------------------------
    # Bloc infos local
    # -------------------------
    infos = [
        f"Épaisseur paroi       : {_fmt_mm(d.epaisseur_mm)}",
    ]
    if d.gorge_largeur_mm > 0:
        infos.append(f"Gorge joint           : {_fmt_mm(d.gorge_largeur_mm)} x {_fmt_mm(d.gorge_profondeur_mm)}")
    if d.gorge_diametre_moyen_joint_mm > 0:
        infos.append(f"Ø moyen joint         : {_fmt_mm(d.gorge_diametre_moyen_joint_mm)}")
    if d.gorge_diametre_tore_mm > 0:
        infos.append(f"Ø tore                : {_fmt_mm(d.gorge_diametre_tore_mm)}")
    if d.gorge_taux_ecrasement > 0:
        infos.append(f"Taux écrasement       : {d.gorge_taux_ecrasement:.3f}")
    if d.chanfrein_entree_piston_mm > 0:
        infos.append(f"Chanfrein entrée      : {_fmt_mm(d.chanfrein_entree_piston_mm)}")
    if d.chanfrein_exterieur_mm > 0:
        infos.append(f"Chanfrein extérieur   : {_fmt_mm(d.chanfrein_exterieur_mm)}")
    if d.rayon_conge_mm > 0:
        infos.append(f"Rayon congé           : {_fmt_mm(d.rayon_conge_mm)}")
    if d.jeu_piston_cylindre_mm > 0:
        infos.append(f"Jeu piston/cylindre   : {_fmt_mm(d.jeu_piston_cylindre_mm)}")
    if d.note_paroi_mince:
        infos.append(f"Vérification paroi    : {d.note_paroi_mince}")

    ax.text(
        x0,
        -y_bride - 38.0,
        "\n".join(infos),
        ha="left",
        va="top",
        fontsize=8.8,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
    )

    ax.set_title("Vue de côté en coupe")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-90.0, max(x3 + 95.0, L_tot + 95.0))
    ax.set_ylim(-(y_bride + 75.0), y_bride + 75.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE DE FACE DÉTAILLÉE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisCylindre):
    D_bride = d.bride_diametre_exterieur_mm if d.bride_diametre_exterieur_mm > 0 else d.diametre_exterieur_mm
    R_bride = D_bride / 2.0
    R_ext = d.diametre_exterieur_mm / 2.0
    R_int = d.alesage_mm / 2.0

    # cercles principaux
    ax.add_patch(Circle((0, 0), R_bride, fill=False, linewidth=1.5, edgecolor="black"))
    ax.add_patch(Circle((0, 0), R_ext, fill=False, linewidth=1.2, edgecolor="black"))
    ax.add_patch(Circle((0, 0), R_int, fill=False, linewidth=1.2, edgecolor="black"))

    # axes
    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    # cercle de perçage
    if d.diametre_cercle_percage_mm > 0:
        R_pcd = d.diametre_cercle_percage_mm / 2.0
        ax.add_patch(Circle((0, 0), R_pcd, fill=False, linewidth=1.0, linestyle=(0, (5, 5)), edgecolor="black"))

        if d.nb_trous > 0 and d.diametre_trou_mm > 0:
            angles = d.angles_deg or [i * (360.0 / d.nb_trous) for i in range(d.nb_trous)]
            r_trou = d.diametre_trou_mm / 2.0

            for i, ang_deg in enumerate(angles):
                a = math.radians(float(ang_deg))
                x = R_pcd * math.cos(a)
                y = R_pcd * math.sin(a)
                ax.add_patch(Circle((x, y), r_trou, fill=False, linewidth=1.0, edgecolor="black"))
                ax.text(x + r_trou + 2.0, y + r_trou + 2.0, str(i + 1), fontsize=7)

    # annotations
    txt = [
        f"Ø bride        = {_fmt_mm(D_bride)}",
        f"Ø ext          = {_fmt_mm(d.diametre_exterieur_mm)}",
        f"Ø alésage      = {_fmt_mm(d.alesage_mm)}",
    ]
    if d.nb_trous > 0:
        txt.append(f"{d.nb_trous} trous      = Ø {_fmt_mm(d.diametre_trou_mm)}")
    if d.diametre_cercle_percage_mm > 0:
        txt.append(f"PCD            = {_fmt_mm(d.diametre_cercle_percage_mm)}")
    if d.filetage_txt:
        txt.append(f"Filetage        = {d.filetage_txt}")
    if d.as_mm2 > 0:
        txt.append(f"As              = {d.as_mm2:.2f} mm²")

    ax.text(
        -R_bride,
        -R_bride - 20.0,
        "\n".join(txt),
        ha="left",
        va="top",
        fontsize=8.8,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
    )

    ax.set_title("Vue de face")
    ax.set_aspect("equal", adjustable="box")
    lim = max(R_bride, R_ext, R_int) + 38.0
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisCylindre):
    lines = [
        f"Ø alésage              : {_fmt_mm(d.alesage_mm)}",
        f"Ø extérieur            : {_fmt_mm(d.diametre_exterieur_mm)}",
        f"Ø bride                : {_fmt_mm(d.bride_diametre_exterieur_mm) if d.bride_diametre_exterieur_mm > 0 else 'N/A'}",
        f"Longueur utile         : {_fmt_mm(d.longueur_utile_mm)}",
        f"Longueur totale        : {_fmt_mm(d.longueur_totale_mm)}",
        f"Épaisseur paroi        : {_fmt_mm(d.epaisseur_mm)}",
        f"Épaisseur bride        : {_fmt_mm(d.bride_epaisseur_mm) if d.bride_epaisseur_mm > 0 else 'N/A'}",
        f"Largeur bride          : {_fmt_mm(d.bride_largeur_radiale_mm) if d.bride_largeur_radiale_mm > 0 else 'N/A'}",
        f"Ø trou                 : {_fmt_mm(d.diametre_trou_mm) if d.diametre_trou_mm > 0 else 'N/A'}",
        f"Ø cercle perçage       : {_fmt_mm(d.diametre_cercle_percage_mm) if d.diametre_cercle_percage_mm > 0 else 'N/A'}",
        f"Nb trous               : {d.nb_trous if d.nb_trous > 0 else 'N/A'}",
        f"Filetage               : {d.filetage_txt or 'N/A'}",
        f"As                     : {f'{d.as_mm2:.2f} mm²' if d.as_mm2 > 0 else 'N/A'}",
        f"F pression service     : {_fmt_n(d.force_pression_service_N) if d.force_pression_service_N > 0 else 'N/A'}",
        f"F pression max         : {_fmt_n(d.force_pression_max_N) if d.force_pression_max_N > 0 else 'N/A'}",
        f"F séparation           : {_fmt_n(d.force_separation_N) if d.force_separation_N > 0 else 'N/A'}",
        f"F joint                : {_fmt_n(d.force_joint_N) if d.force_joint_N > 0 else 'N/A'}",
        f"Précharge totale       : {_fmt_n(d.force_precharge_totale_N) if d.force_precharge_totale_N > 0 else 'N/A'}",
        f"Précharge / vis        : {_fmt_n(d.force_precharge_par_vis_N) if d.force_precharge_par_vis_N > 0 else 'N/A'}",
        f"Couple / vis           : {f'{d.couple_serrage_par_vis_Nm:.2f} N·m' if d.couple_serrage_par_vis_Nm > 0 else 'N/A'}",
        f"σ cerclage mince       : {_fmt_pa(d.sigma_cerclage_mince_pa) if d.sigma_cerclage_mince_pa > 0 else 'N/A'}",
        f"σ Von Mises Lamé       : {_fmt_pa(d.sigma_vm_lame_pa) if d.sigma_vm_lame_pa > 0 else 'N/A'}",
        f"Masse totale           : {f'{d.masse_kg:.4f} kg' if d.masse_kg > 0 else 'N/A'}",
        f"Volume métal           : {_fmt_m3(d.volume_metal_m3) if d.volume_metal_m3 > 0 else 'N/A'}",
        f"Volume brides          : {_fmt_m3(d.volume_brides_m3) if d.volume_brides_m3 > 0 else 'N/A'}",
        f"Inertie flexion I      : {_fmt_m4(d.inertie_I_m4) if d.inertie_I_m4 > 0 else 'N/A'}",
        f"Inertie polaire J      : {_fmt_m4(d.inertie_J_m4) if d.inertie_J_m4 > 0 else 'N/A'}",
        f"Note paroi             : {d.note_paroi_mince or 'N/A'}",
    ]

    fig.text(
        0.015,
        0.02,
        "DONNÉES EXTRAITES DE Cylindre.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=8.3,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_cylindre_2d(
    cylindre: Cylindre,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Cylindre",
):
    """
    Trace un croquis 2D détaillé basé sur Cylindre.analyser().

    - Vue de gauche : coupe longitudinale détaillée
    - Vue de droite : face avant détaillée
    """
    d = extraire_donnees_croquis(cylindre)

    if d.alesage_mm <= 0 or d.longueur_utile_mm <= 0:
        raise ValueError("Impossible de tracer le croquis : dimensions principales invalides.")

    fig, (ax_side, ax_front) = plt.subplots(
        1, 2, figsize=(17, 9), gridspec_kw={"width_ratios": [2.25, 1.35]}
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
    from backend.components.moteur_thermique.pieces.cylindre import (
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
        titre="Croquis 2D détaillé - Cylindre calculé",
    )