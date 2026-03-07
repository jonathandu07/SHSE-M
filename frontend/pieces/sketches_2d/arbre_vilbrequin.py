# frontend/pieces/sketches_2d/arbre_vilbrequin.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

from backend.pieces.arbre_vilbrequin import ArbreVilbrequin


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


def _fmt_nm(v: float) -> str:
    return f"{v:.2f} N·m"


def _fmt_pa(v: float) -> str:
    return f"{v:.3e} Pa"


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


# ============================================================
# DONNÉES EXTRAITES
# ============================================================

@dataclass
class DonneesCroquisArbreVilbrequin:
    # géométrie
    course_mm: float = 0.0
    rayon_manivelle_mm: float = 0.0
    diametre_journal_mm: float = 0.0
    largeur_journal_mm: float = 0.0
    diametre_maneton_mm: float = 0.0
    largeur_maneton_mm: float = 0.0
    entre_axe_paliers_mm: float = 0.0
    largeur_totale_mm: float = 0.0
    nb_journaux: int = 0

    # référence roulement
    d_interieur_ref_mm: float = 0.0
    D_exterieur_ref_mm: float = 0.0
    B_largeur_ref_mm: float = 0.0
    diametre_usinage_journal_mm: float = 0.0

    # dimensions mini calculées
    dmin_torsion_mm: float = 0.0
    dmin_flexion_mm: float = 0.0
    dmin_axial_mm: float = 0.0
    dmin_maneton_calc_mm: float = 0.0
    dmin_journal_calc_mm: float = 0.0

    # contraintes journal
    sigma_axiale_j_pa: float = 0.0
    sigma_flexion_j_pa: float = 0.0
    tau_torsion_j_pa: float = 0.0
    sigma_vm_j_pa: float = 0.0
    marge_vm_j: float = 0.0

    # contraintes maneton
    sigma_axiale_m_pa: float = 0.0
    sigma_flexion_m_pa: float = 0.0
    tau_torsion_m_pa: float = 0.0
    sigma_vm_m_pa: float = 0.0
    marge_vm_m: float = 0.0

    sigma_admissible_pa: float = 0.0

    # contact
    pression_contact_maneton_pa: float = 0.0

    # efforts / cinématique
    couple_max_Nm: float = 0.0
    force_bielle_N: float = 0.0
    force_axiale_N: float = 0.0
    moment_flexion_max_Nm: float = 0.0
    rpm: float = 0.0
    omega_rad_s: float = 0.0

    # masse / inerties
    masse_kg: float = 0.0
    volume_total_m3: float = 0.0
    I_journal_m4: float = 0.0
    J_journal_m4: float = 0.0
    I_maneton_m4: float = 0.0
    J_maneton_m4: float = 0.0

    # CAO
    centre_journal_g_mm: float = 0.0
    centre_journal_d_mm: float = 0.0
    centre_maneton_mm: float = 0.0
    diametre_epaulement_journal_mm: float = 0.0
    diametre_epaulement_maneton_mm: float = 0.0
    rayon_conge_journal_mm: float = 0.0
    rayon_conge_maneton_mm: float = 0.0
    chanfrein_journal_mm: float = 0.0
    chanfrein_maneton_mm: float = 0.0

    note_modele_cao: str = ""
    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(arbre: ArbreVilbrequin) -> DonneesCroquisArbreVilbrequin:
    rapport = arbre.analyser(strict=False)

    geo = rapport.get("geometrie", {})
    rou = rapport.get("roulement", {})
    bie = rapport.get("bielle_maneton", {})
    dim = rapport.get("dimensionnements", {})
    cont = rapport.get("contraintes", {})
    pc = rapport.get("pressions_contact", {})
    cin = rapport.get("cinematique", {})
    rec = rapport.get("recuperations", {})
    masse = rapport.get("masse", {})
    inert = rapport.get("inerties", {})
    cao = rapport.get("cao", {})

    c_j = cont.get("journal_principal", {}) if isinstance(cont.get("journal_principal"), dict) else {}
    c_m = cont.get("maneton", {}) if isinstance(cont.get("maneton"), dict) else {}
    pc_m = pc.get("maneton", {}) if isinstance(pc.get("maneton"), dict) else {}
    i_j = inert.get("journal_principal", {}) if isinstance(inert.get("journal_principal"), dict) else {}
    i_m = inert.get("maneton", {}) if isinstance(inert.get("maneton"), dict) else {}
    cao_j = cao.get("journal_principal", {}) if isinstance(cao.get("journal_principal"), dict) else {}
    cao_m = cao.get("maneton", {}) if isinstance(cao.get("maneton"), dict) else {}
    cao_maniv = cao.get("manivelle", {}) if isinstance(cao.get("manivelle"), dict) else {}
    cao_ref = cao.get("roulement_reference", {}) if isinstance(cao.get("roulement_reference"), dict) else {}

    return DonneesCroquisArbreVilbrequin(
        course_mm=_mm(_get_nested(geo, "course_m", default=_get_nested(cin, "course_m", default=0.0))),
        rayon_manivelle_mm=_mm(_get_nested(geo, "rayon_manivelle_m", default=_get_nested(cin, "rayon_manivelle_m", default=0.0))),
        diametre_journal_mm=_mm(_get_nested(geo, "diametre_journal_principal_m", default=0.0)),
        largeur_journal_mm=_mm(_get_nested(geo, "largeur_portee_journal_m", default=0.0)),
        diametre_maneton_mm=_mm(_get_nested(geo, "diametre_maneton_m", default=0.0)),
        largeur_maneton_mm=_mm(_get_nested(geo, "largeur_portee_maneton_m", default=0.0)),
        entre_axe_paliers_mm=_mm(_get_nested(geo, "entre_axe_paliers_m", default=0.0)),
        largeur_totale_mm=_mm(_get_nested(geo, "largeur_totale_arbre_m", default=0.0)),
        nb_journaux=int(_get_nested(geo, "nb_journaux_principaux", default=_get_nested(cao, "nb_journaux_principaux", default=0)) or 0),

        d_interieur_ref_mm=_mm(_get_nested(rou, "d_interieur_reference_m", default=_get_nested(cao_ref, "d_interieur_m", default=0.0))),
        D_exterieur_ref_mm=_mm(_get_nested(rou, "D_exterieur_reference_m", default=_get_nested(cao_ref, "D_exterieur_m", default=0.0))),
        B_largeur_ref_mm=_mm(_get_nested(rou, "B_largeur_reference_m", default=_get_nested(cao_ref, "B_largeur_m", default=0.0))),
        diametre_usinage_journal_mm=_mm(_get_nested(geo, "diametre_usinage_journal_m", default=0.0)),

        dmin_torsion_mm=_mm(_get_nested(dim, "diametre_min_torsion_m", default=0.0)),
        dmin_flexion_mm=_mm(_get_nested(dim, "diametre_min_flexion_m", default=0.0)),
        dmin_axial_mm=_mm(_get_nested(dim, "diametre_min_axial_m", default=0.0)),
        dmin_maneton_calc_mm=_mm(_get_nested(dim, "diametre_maneton_min_calcule_m", default=0.0)),
        dmin_journal_calc_mm=_mm(_get_nested(dim, "diametre_journal_min_calcule_m", default=0.0)),

        sigma_axiale_j_pa=_safe_float(_get_nested(c_j, "sigma_axiale_pa", default=0.0)),
        sigma_flexion_j_pa=_safe_float(_get_nested(c_j, "sigma_flexion_pa", default=0.0)),
        tau_torsion_j_pa=_safe_float(_get_nested(c_j, "tau_torsion_pa", default=0.0)),
        sigma_vm_j_pa=_safe_float(_get_nested(c_j, "sigma_von_mises_pa", default=0.0)),
        marge_vm_j=_safe_float(_get_nested(c_j, "marge_von_mises", default=0.0)),

        sigma_axiale_m_pa=_safe_float(_get_nested(c_m, "sigma_axiale_pa", default=0.0)),
        sigma_flexion_m_pa=_safe_float(_get_nested(c_m, "sigma_flexion_pa", default=0.0)),
        tau_torsion_m_pa=_safe_float(_get_nested(c_m, "tau_torsion_pa", default=0.0)),
        sigma_vm_m_pa=_safe_float(_get_nested(c_m, "sigma_von_mises_pa", default=0.0)),
        marge_vm_m=_safe_float(_get_nested(c_m, "marge_von_mises", default=0.0)),

        sigma_admissible_pa=_safe_float(_get_nested(c_j, "sigma_admissible_pa", default=_get_nested(c_m, "sigma_admissible_pa", default=0.0))),
        pression_contact_maneton_pa=_safe_float(_get_nested(pc_m, "pression_moyenne_pa", default=0.0)),

        couple_max_Nm=_safe_float(_get_nested(rec, "couple_max_Nm", default=0.0)),
        force_bielle_N=_safe_float(_get_nested(rec, "force_bielle_effective_N", default=0.0)),
        force_axiale_N=_safe_float(_get_nested(rec, "force_axiale_N", default=0.0)),
        moment_flexion_max_Nm=_safe_float(_get_nested(rec, "moment_flexion_max_Nm", default=0.0)),
        rpm=_safe_float(_get_nested(cin, "rpm", default=0.0)),
        omega_rad_s=_safe_float(_get_nested(cin, "omega_rad_s", default=0.0)),

        masse_kg=_safe_float(_get_nested(masse, "masse_kg", default=0.0)),
        volume_total_m3=_safe_float(_get_nested(masse, "volume_total_minimal_m3", default=0.0)),
        I_journal_m4=_safe_float(_get_nested(i_j, "I_m4", default=0.0)),
        J_journal_m4=_safe_float(_get_nested(i_j, "J_m4", default=0.0)),
        I_maneton_m4=_safe_float(_get_nested(i_m, "I_m4", default=0.0)),
        J_maneton_m4=_safe_float(_get_nested(i_m, "J_m4", default=0.0)),

        centre_journal_g_mm=_mm(_get_nested(cao_j, "centre_gauche_x_m", default=0.0)),
        centre_journal_d_mm=_mm(_get_nested(cao_j, "centre_droit_x_m", default=0.0)),
        centre_maneton_mm=_mm(_get_nested(cao_m, "centre_x_m", default=_get_nested(cao_maniv, "centre_maneton_x_m", default=0.0))),
        diametre_epaulement_journal_mm=_mm(_get_nested(cao_j, "diametre_epaulement_m", default=0.0)),
        diametre_epaulement_maneton_mm=_mm(_get_nested(cao_m, "diametre_epaulement_m", default=0.0)),
        rayon_conge_journal_mm=_mm(_get_nested(cao_j, "rayon_conge_m", default=0.0)),
        rayon_conge_maneton_mm=_mm(_get_nested(cao_m, "rayon_conge_m", default=0.0)),
        chanfrein_journal_mm=_mm(_get_nested(cao_j, "chanfrein_m", default=0.0)),
        chanfrein_maneton_mm=_mm(_get_nested(cao_m, "chanfrein_m", default=0.0)),

        note_modele_cao=str(_get_nested(cao, "hypothese_modele", default="") or ""),
        rapport_complet=rapport,
    )


# ============================================================
# VUE DE CÔTÉ DES PORTÉES
# ============================================================

def _tracer_vue_cote_portees(ax, d: DonneesCroquisArbreVilbrequin):
    D_j = d.diametre_journal_mm
    L_j = d.largeur_journal_mm
    D_m = d.diametre_maneton_mm
    L_m = d.largeur_maneton_mm

    yj = D_j / 2.0 if D_j > 0 else 0.0
    ym = D_m / 2.0 if D_m > 0 else 0.0
    ymax = max(yj, ym, 1.0)

    # Positionnement longitudinal purement géométrique, sans inventer les joues
    if d.entre_axe_paliers_mm > 0:
        c_g = d.centre_journal_g_mm
        c_d = d.centre_journal_d_mm
        c_m = d.centre_maneton_mm
        if c_g == 0.0 and c_d == 0.0:
            c_g = -0.5 * d.entre_axe_paliers_mm
            c_d = 0.5 * d.entre_axe_paliers_mm
    else:
        # fallback minimal si entre-axe absent : on aligne sans prétendre dessiner la vraie géométrie
        c_g = -(L_j + L_m)
        c_m = 0.0
        c_d = (L_j + L_m)

    xjg0 = c_g - L_j / 2.0 if L_j > 0 else c_g
    xjg1 = c_g + L_j / 2.0 if L_j > 0 else c_g
    xm0 = c_m - L_m / 2.0 if L_m > 0 else c_m
    xm1 = c_m + L_m / 2.0 if L_m > 0 else c_m
    xjd0 = c_d - L_j / 2.0 if L_j > 0 else c_d
    xjd1 = c_d + L_j / 2.0 if L_j > 0 else c_d

    # Hachures
    if L_j > 0 and D_j > 0:
        _add_hatched_rect(ax, xjg0, -yj, L_j, D_j)
        _add_hatched_rect(ax, xjd0, -yj, L_j, D_j)
    if L_m > 0 and D_m > 0:
        _add_hatched_rect(ax, xm0, -ym, L_m, D_m)

    # Contours
    if L_j > 0 and D_j > 0:
        ax.add_patch(Rectangle((xjg0, -yj), L_j, D_j, fill=False, linewidth=1.5))
        ax.add_patch(Rectangle((xjd0, -yj), L_j, D_j, fill=False, linewidth=1.5))
    if L_m > 0 and D_m > 0:
        ax.add_patch(Rectangle((xm0, -ym), L_m, D_m, fill=False, linewidth=1.6))

    # Axes
    ax.axhline(0, **_linestyle_axe())
    ax.axvline(c_g, **_linestyle_hidden())
    ax.axvline(c_m, **_linestyle_hidden())
    ax.axvline(c_d, **_linestyle_hidden())

    # Leaders
    if L_j > 0 and D_j > 0:
        _annotate_leader(ax, xjg0 - 55.0, yj + 18.0, c_g, yj, "Journal principal G")
        _annotate_leader(ax, xjd1 + 10.0, yj + 18.0, c_d, yj, "Journal principal D")
    if L_m > 0 and D_m > 0:
        _annotate_leader(ax, xm1 + 10.0, ym + 18.0, c_m, ym, "Maneton")

    # Cotes longitudinales
    ydim1 = ymax + 16.0
    ydim2 = ymax + 32.0
    ydim3 = ymax + 48.0

    if L_j > 0:
        _add_dimension_h(ax, xjg0, xjg1, 0.0, ydim1, f"L journal = {_fmt_mm(L_j)}")
        _add_dimension_h(ax, xjd0, xjd1, 0.0, ydim2, f"L journal = {_fmt_mm(L_j)}")
    if L_m > 0:
        _add_dimension_h(ax, xm0, xm1, 0.0, ydim1, f"L maneton = {_fmt_mm(L_m)}")

    if d.entre_axe_paliers_mm > 0:
        _add_dimension_h(ax, c_g, c_d, 0.0, ydim3, f"Entraxe paliers = {_fmt_mm(d.entre_axe_paliers_mm)}")

    # Cotes diamètres
    xdim1 = xjd1 + 24.0
    xdim2 = xjd1 + 44.0
    if D_j > 0:
        _add_dimension_v(ax, 0.0, xdim1, -yj, yj, f"Ø journal = {_fmt_mm(D_j)}")
    if D_m > 0:
        _add_dimension_v(ax, 0.0, xdim2, -ym, ym, f"Ø maneton = {_fmt_mm(D_m)}")

    # Bloc infos local
    infos = []
    if d.diametre_epaulement_journal_mm > 0:
        infos.append(f"Ø épaulement journal : {_fmt_mm(d.diametre_epaulement_journal_mm)}")
    if d.diametre_epaulement_maneton_mm > 0:
        infos.append(f"Ø épaulement maneton : {_fmt_mm(d.diametre_epaulement_maneton_mm)}")
    if d.rayon_conge_journal_mm > 0:
        infos.append(f"Rayon congé journal  : {_fmt_mm(d.rayon_conge_journal_mm)}")
    if d.rayon_conge_maneton_mm > 0:
        infos.append(f"Rayon congé maneton  : {_fmt_mm(d.rayon_conge_maneton_mm)}")
    if d.chanfrein_journal_mm > 0:
        infos.append(f"Chanfrein journal    : {_fmt_mm(d.chanfrein_journal_mm)}")
    if d.chanfrein_maneton_mm > 0:
        infos.append(f"Chanfrein maneton    : {_fmt_mm(d.chanfrein_maneton_mm)}")
    if d.note_modele_cao:
        infos.append("Modèle CAO minimal   : portées seules")

    if infos:
        ax.text(
            min(xjg0, xm0, xjd0),
            -(ymax + 36.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.6,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    xmin = min(xjg0, xm0, xjd0) - 90.0
    xmax = max(xjg1, xm1, xjd1) + 95.0

    ax.set_title("Vue de côté détaillée des portées")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-(ymax + 70.0), ymax + 70.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE SCHÉMATIQUE DE LA MANIVELLE
# ============================================================

def _tracer_vue_manivelle(ax, d: DonneesCroquisArbreVilbrequin):
    r = d.rayon_manivelle_mm
    if r <= 0:
        ax.text(0.5, 0.5, "Rayon de manivelle non disponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Schéma cinématique")
        ax.set_axis_off()
        return

    Rj = max(d.diametre_journal_mm / 2.0, 4.0)
    Rm = max(d.diametre_maneton_mm / 2.0, 4.0)

    # Journal principal centre origine
    ax.add_patch(Circle((0.0, 0.0), Rj, fill=False, linewidth=1.5))
    ax.add_patch(Circle((r, 0.0), Rm, fill=False, linewidth=1.5))

    # Bras symbolique
    ax.add_line(Line2D([0.0, r], [0.0, 0.0], linewidth=1.2, color="black"))

    # Axe
    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    # Cote rayon
    _add_dimension_h(ax, 0.0, r, 0.0, Rm + 22.0, f"r manivelle = {_fmt_mm(r)}")

    # Course
    _add_dimension_h(ax, -r, r, 0.0, -(Rm + 22.0), f"Course = {_fmt_mm(2.0 * r)}")

    _annotate_leader(ax, -r * 0.7, Rm + 34.0, 0.0, Rj, "Axe journal")
    _annotate_leader(ax, r + 12.0, Rm + 24.0, r, Rm, "Axe maneton")

    ax.set_title("Schéma cinématique de manivelle")
    ax.set_aspect("equal", adjustable="box")
    lim = r + max(Rj, Rm) + 40.0
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim * 0.7, lim * 0.7)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUES DE FACE
# ============================================================

def _tracer_section(ax, d_ext_mm: float, titre: str, notes: List[str]):
    R = d_ext_mm / 2.0 if d_ext_mm > 0 else 0.0
    if R > 0:
        ax.add_patch(Circle((0, 0), R, fill=False, linewidth=1.5, edgecolor="black"))

    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    txt = [f"Ø = {_fmt_mm(d_ext_mm)}"] if d_ext_mm > 0 else []
    txt.extend(notes)

    lim = max(R, 1.0) + 22.0
    ax.text(
        -lim + 4.0,
        -lim + 4.0,
        "\n".join(txt),
        ha="left",
        va="bottom",
        fontsize=8.4,
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


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisArbreVilbrequin):
    lines = [
        f"Course                   : {_fmt_mm(d.course_mm) if d.course_mm > 0 else 'N/A'}",
        f"Rayon manivelle          : {_fmt_mm(d.rayon_manivelle_mm) if d.rayon_manivelle_mm > 0 else 'N/A'}",
        f"Ø journal principal      : {_fmt_mm(d.diametre_journal_mm) if d.diametre_journal_mm > 0 else 'N/A'}",
        f"L journal principal      : {_fmt_mm(d.largeur_journal_mm) if d.largeur_journal_mm > 0 else 'N/A'}",
        f"Ø maneton                : {_fmt_mm(d.diametre_maneton_mm) if d.diametre_maneton_mm > 0 else 'N/A'}",
        f"L maneton                : {_fmt_mm(d.largeur_maneton_mm) if d.largeur_maneton_mm > 0 else 'N/A'}",
        f"Entraxe paliers          : {_fmt_mm(d.entre_axe_paliers_mm) if d.entre_axe_paliers_mm > 0 else 'N/A'}",
        f"Largeur totale arbre     : {_fmt_mm(d.largeur_totale_mm) if d.largeur_totale_mm > 0 else 'N/A'}",
        f"Nb journaux principaux   : {d.nb_journaux if d.nb_journaux > 0 else 'N/A'}",
        f"d réf roulement          : {_fmt_mm(d.d_interieur_ref_mm) if d.d_interieur_ref_mm > 0 else 'N/A'}",
        f"D réf roulement          : {_fmt_mm(d.D_exterieur_ref_mm) if d.D_exterieur_ref_mm > 0 else 'N/A'}",
        f"B réf roulement          : {_fmt_mm(d.B_largeur_ref_mm) if d.B_largeur_ref_mm > 0 else 'N/A'}",
        f"Ø usinage journal        : {_fmt_mm(d.diametre_usinage_journal_mm) if d.diametre_usinage_journal_mm > 0 else 'N/A'}",
        f"d min torsion            : {_fmt_mm(d.dmin_torsion_mm) if d.dmin_torsion_mm > 0 else 'N/A'}",
        f"d min flexion            : {_fmt_mm(d.dmin_flexion_mm) if d.dmin_flexion_mm > 0 else 'N/A'}",
        f"d min axial              : {_fmt_mm(d.dmin_axial_mm) if d.dmin_axial_mm > 0 else 'N/A'}",
        f"d min maneton calculé    : {_fmt_mm(d.dmin_maneton_calc_mm) if d.dmin_maneton_calc_mm > 0 else 'N/A'}",
        f"d min journal calculé    : {_fmt_mm(d.dmin_journal_calc_mm) if d.dmin_journal_calc_mm > 0 else 'N/A'}",
        f"Couple max               : {_fmt_nm(d.couple_max_Nm) if d.couple_max_Nm > 0 else 'N/A'}",
        f"Force bielle             : {_fmt_n(d.force_bielle_N) if d.force_bielle_N > 0 else 'N/A'}",
        f"Force axiale             : {_fmt_n(d.force_axiale_N) if d.force_axiale_N != 0 else 'N/A'}",
        f"Moment flexion max       : {_fmt_nm(d.moment_flexion_max_Nm) if d.moment_flexion_max_Nm > 0 else 'N/A'}",
        f"σ admissible             : {_fmt_pa(d.sigma_admissible_pa) if d.sigma_admissible_pa > 0 else 'N/A'}",
        f"σ_VM journal             : {_fmt_pa(d.sigma_vm_j_pa) if d.sigma_vm_j_pa > 0 else 'N/A'}",
        f"Marge journal            : {f'{d.marge_vm_j:.3f}' if d.marge_vm_j > 0 else 'N/A'}",
        f"σ_VM maneton             : {_fmt_pa(d.sigma_vm_m_pa) if d.sigma_vm_m_pa > 0 else 'N/A'}",
        f"Marge maneton            : {f'{d.marge_vm_m:.3f}' if d.marge_vm_m > 0 else 'N/A'}",
        f"Pression contact maneton : {_fmt_pa(d.pression_contact_maneton_pa) if d.pression_contact_maneton_pa > 0 else 'N/A'}",
        f"Masse minimale           : {f'{d.masse_kg:.4f} kg' if d.masse_kg > 0 else 'N/A'}",
        f"Volume minimal           : {_fmt_m3(d.volume_total_m3) if d.volume_total_m3 > 0 else 'N/A'}",
        f"I journal                : {_fmt_m4(d.I_journal_m4) if d.I_journal_m4 > 0 else 'N/A'}",
        f"J journal                : {_fmt_m4(d.J_journal_m4) if d.J_journal_m4 > 0 else 'N/A'}",
        f"I maneton                : {_fmt_m4(d.I_maneton_m4) if d.I_maneton_m4 > 0 else 'N/A'}",
        f"J maneton                : {_fmt_m4(d.J_maneton_m4) if d.J_maneton_m4 > 0 else 'N/A'}",
        f"rpm                      : {f'{d.rpm:.2f}' if d.rpm > 0 else 'N/A'}",
        f"omega                    : {f'{d.omega_rad_s:.4f} rad/s' if d.omega_rad_s > 0 else 'N/A'}",
        f"Modèle CAO               : {'portées + manivelle minimale'}",
    ]

    fig.text(
        0.012,
        0.015,
        "DONNÉES EXTRAITES DE ArbreVilbrequin.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=8.15,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_arbre_vilebrequin_2d(
    arbre: ArbreVilbrequin,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Arbre de vilebrequin",
):
    d = extraire_donnees_croquis(arbre)

    if d.diametre_journal_mm <= 0 and d.diametre_maneton_mm <= 0:
        raise ValueError("Impossible de tracer : aucun diamètre de portée n’est disponible.")
    if d.course_mm <= 0 and d.rayon_manivelle_mm <= 0:
        raise ValueError("Impossible de tracer : course / rayon de manivelle absent.")

    fig = plt.figure(figsize=(19, 11))
    gs = fig.add_gridspec(2, 4, height_ratios=[2.15, 1.25], width_ratios=[1.15, 1.15, 1.15, 1.35])

    ax_side = fig.add_subplot(gs[0, :3])
    ax_scheme = fig.add_subplot(gs[0, 3])
    ax_face_g = fig.add_subplot(gs[1, 0])
    ax_face_m = fig.add_subplot(gs[1, 1])
    ax_face_d = fig.add_subplot(gs[1, 2])
    ax_info = fig.add_subplot(gs[1, 3])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_cote_portees(ax_side, d)
    _tracer_vue_manivelle(ax_scheme, d)

    _tracer_section(
        ax_face_g,
        d_ext_mm=d.diametre_journal_mm,
        titre="Vue de face - Journal G",
        notes=[
            f"L = {_fmt_mm(d.largeur_journal_mm)}" if d.largeur_journal_mm > 0 else "Longueur non dispo",
        ],
    )

    _tracer_section(
        ax_face_m,
        d_ext_mm=d.diametre_maneton_mm,
        titre="Vue de face - Maneton",
        notes=[
            f"L = {_fmt_mm(d.largeur_maneton_mm)}" if d.largeur_maneton_mm > 0 else "Longueur non dispo",
        ],
    )

    _tracer_section(
        ax_face_d,
        d_ext_mm=d.diametre_journal_mm,
        titre="Vue de face - Journal D",
        notes=[
            f"L = {_fmt_mm(d.largeur_journal_mm)}" if d.largeur_journal_mm > 0 else "Longueur non dispo",
        ],
    )

    # panneau d’avertissement / limites de modèle
    ax_info.axis("off")
    notes_modele = [
        "Le backend calcule ici surtout les portées cylindriques.",
        "Les joues/bras de vilebrequin ne sont pas définis géométriquement.",
        "Les contrepoids ne sont pas modélisés.",
        "La vue de côté représente donc les portées connues,",
        "et la vue de manivelle montre le rayon cinématique.",
        "",
        "Aucune géométrie non fournie n’est inventée.",
    ]
    ax_info.text(
        0.02,
        0.98,
        "\n".join(notes_modele),
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
        "vue_cote_portees": ax_side,
        "vue_schema_manivelle": ax_scheme,
        "vue_face_journal_g": ax_face_g,
        "vue_face_maneton": ax_face_m,
        "vue_face_journal_d": ax_face_d,
        "panneau_info": ax_info,
    }, d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

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
    )

    tracer_croquis_arbre_vilebrequin_2d(
        av,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Arbre de vilebrequin calculé",
    )