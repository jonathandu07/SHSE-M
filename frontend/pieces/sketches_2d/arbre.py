# frontend/pieces/sketches_2d/arbre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

from backend.pieces.arbre import ArbreMoteur


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


def _fmt_kgm2(v: float) -> str:
    return f"{v:.6e} kg·m²"


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
class DonneesCroquisArbreMoteur:
    diametre_nominal_mm: float = 0.0
    longueur_totale_mm: float = 0.0

    # clavette
    clavette_b_mm: float = 0.0
    clavette_h_mm: float = 0.0
    clavette_L_mm: float = 0.0
    rainure_arbre_mm: float = 0.0
    rainure_moyeu_mm: float = 0.0
    clavette_L_cisaillement_mm: float = 0.0
    clavette_L_ecrasement_mm: float = 0.0
    clavette_L_disponible_mm: float = 0.0
    clavette_longueur_ok: Optional[bool] = None
    norme_din: str = ""

    # interfaces
    largeur_moyeu_mm: float = 0.0
    largeur_roulement_mm: float = 0.0

    # architecture longitudinale
    bloc_cylindres_L_mm: float = 0.0
    empilement_entree_mm: float = 0.0
    empilement_sortie_mm: float = 0.0
    depassement_entree_mm: float = 0.0
    depassement_sortie_mm: float = 0.0
    nombre_cylindres: int = 0
    entraxe_cylindres_mm: float = 0.0
    diametre_externe_cylindre_mm: float = 0.0

    # mécanique
    couple_max_Nm: float = 0.0
    rpm: float = 0.0
    moment_flexion_max_Nm: float = 0.0
    force_radiale_N: float = 0.0
    force_axiale_N: float = 0.0

    d_min_torsion_mm: float = 0.0
    d_min_flexion_mm: float = 0.0
    d_min_traction_mm: float = 0.0
    d_min_vm_mm: float = 0.0
    d_min_global_mm: float = 0.0
    d_max_passage_mm: float = 0.0

    tau_adm_arbre_pa: float = 0.0
    sigma_adm_arbre_pa: float = 0.0
    tau_adm_clavette_pa: float = 0.0
    sigma_adm_appui_pa: float = 0.0

    check_d_vs_dmin_ok: Optional[bool] = None
    check_d_vs_passage_ok: Optional[bool] = None

    # masse
    volume_modele_m3: float = 0.0
    masse_modele_kg: float = 0.0
    inertie_polaire_modele_kg_m2: float = 0.0
    densite_kg_m3: float = 0.0

    # CAO
    rayon_conge_mm: float = 0.0
    chanfrein_mm: float = 0.0
    note_cao: str = ""

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(arbre: ArbreMoteur) -> DonneesCroquisArbreMoteur:
    rapport = arbre.analyser(strict=False)

    dim = rapport.get("dimensionnements", {})
    clav = rapport.get("clavette", {})
    longu = rapport.get("longueur", {})
    inter = rapport.get("interfaces", {})
    cont = rapport.get("contraintes", {})
    masses = rapport.get("masses", {})
    cao = rapport.get("cao", {})
    mat = rapport.get("materiau", {})
    arbre_mat = mat.get("arbre", {}) if isinstance(mat.get("arbre"), dict) else {}

    reco = clav.get("recommandation_din", {}) if isinstance(clav.get("recommandation_din"), dict) else {}
    note_norme = ""
    if reco:
        norme_val = reco.get("norme")
        if norme_val is not None:
            note_norme = f"DIN 6885-{int(float(norme_val))}"

    return DonneesCroquisArbreMoteur(
        diametre_nominal_mm=_mm(_get_nested(cao, "diametre_nominal_arbre_m", default=0.0)),
        longueur_totale_mm=_mm(_get_nested(cao, "longueur_totale_m", default=_get_nested(longu, "longueur_totale_arbre_m", default=0.0))),

        clavette_b_mm=_mm(_get_nested(clav, "b_m", default=_get_nested(cao, "zone_clavette", "b_m", default=0.0))),
        clavette_h_mm=_mm(_get_nested(clav, "h_m", default=_get_nested(cao, "zone_clavette", "h_m", default=0.0))),
        clavette_L_mm=_mm(_get_nested(cao, "zone_clavette", "longueur_m", default=_get_nested(clav, "longueur_min_requise_m", default=0.0))),
        rainure_arbre_mm=_mm(_get_nested(clav, "profondeur_rainure_arbre_m", default=_get_nested(cao, "zone_clavette", "profondeur_rainure_arbre_m", default=0.0))),
        rainure_moyeu_mm=_mm(_get_nested(clav, "profondeur_rainure_moyeu_m", default=_get_nested(cao, "zone_clavette", "profondeur_rainure_moyeu_m", default=0.0))),
        clavette_L_cisaillement_mm=_mm(_get_nested(clav, "longueur_min_cisaillement_m", default=0.0)),
        clavette_L_ecrasement_mm=_mm(_get_nested(clav, "longueur_min_ecrasement_m", default=0.0)),
        clavette_L_disponible_mm=_mm(_get_nested(clav, "longueur_disponible_m", default=0.0)),
        clavette_longueur_ok=_get_nested(clav, "check_longueur_ok", default=None),
        norme_din=note_norme,

        largeur_moyeu_mm=_mm(_get_nested(inter, "largeur_moyeu_vilbrequin_m", default=_get_nested(cao, "epaulements", "largeur_moyeu_vilbrequin_m", default=0.0))),
        largeur_roulement_mm=_mm(_get_nested(inter, "largeur_portee_roulement_m", default=_get_nested(cao, "epaulements", "largeur_portee_roulement_m", default=0.0))),

        bloc_cylindres_L_mm=_mm(_get_nested(longu, "bloc_cylindres_longueur_m", default=0.0)),
        empilement_entree_mm=_mm(_get_nested(longu, "empilement_annexe_cote_entree_m", default=0.0)),
        empilement_sortie_mm=_mm(_get_nested(longu, "empilement_annexe_cote_sortie_m", default=0.0)),
        depassement_entree_mm=_mm(_get_nested(longu, "depassement_cote_entree_m", default=0.0)),
        depassement_sortie_mm=_mm(_get_nested(longu, "depassement_cote_sortie_m", default=0.0)),
        nombre_cylindres=int(_get_nested(longu, "nombre_cylindres", default=0) or 0),
        entraxe_cylindres_mm=_mm(_get_nested(longu, "entraxe_cylindres_m", default=0.0)),
        diametre_externe_cylindre_mm=_mm(_get_nested(longu, "diametre_externe_cylindre_m", default=0.0)),

        couple_max_Nm=_safe_float(_get_nested(dim, "couple_max_Nm", default=0.0)),
        rpm=_safe_float(_get_nested(dim, "rpm", default=0.0)),
        moment_flexion_max_Nm=_safe_float(_get_nested(dim, "moment_flexion_max_Nm", default=0.0)),
        force_radiale_N=_safe_float(_get_nested(dim, "force_radiale_N", default=0.0)),
        force_axiale_N=_safe_float(_get_nested(dim, "force_axiale_N", default=0.0)),

        d_min_torsion_mm=_mm(_get_nested(dim, "d_min_torsion_m", default=0.0)),
        d_min_flexion_mm=_mm(_get_nested(dim, "d_min_flexion_m", default=0.0)),
        d_min_traction_mm=_mm(_get_nested(dim, "d_min_traction_m", default=0.0)),
        d_min_vm_mm=_mm(_get_nested(dim, "d_min_von_mises_combine_m", default=0.0)),
        d_min_global_mm=_mm(_get_nested(dim, "d_min_global_m", default=0.0)),
        d_max_passage_mm=_mm(_get_nested(dim, "d_max_passage_m", default=0.0)),

        tau_adm_arbre_pa=_safe_float(_get_nested(cont, "tau_admissible_arbre_pa", default=0.0)),
        sigma_adm_arbre_pa=_safe_float(_get_nested(cont, "sigma_admissible_arbre_pa", default=0.0)),
        tau_adm_clavette_pa=_safe_float(_get_nested(cont, "tau_admissible_clavette_pa", default=0.0)),
        sigma_adm_appui_pa=_safe_float(_get_nested(cont, "sigma_admissible_appui_pa", default=0.0)),

        check_d_vs_dmin_ok=_get_nested(dim, "check_d_vs_dmin_ok", default=None),
        check_d_vs_passage_ok=_get_nested(dim, "check_d_vs_passage_ok", default=None),

        volume_modele_m3=_safe_float(_get_nested(masses, "volume_modele_m3", default=0.0)),
        masse_modele_kg=_safe_float(_get_nested(masses, "masse_modele_kg", default=0.0)),
        inertie_polaire_modele_kg_m2=_safe_float(_get_nested(masses, "inertie_polaire_modele_kg_m2", default=0.0)),
        densite_kg_m3=_safe_float(_get_nested(masses, "densite_kg_m3", default=_get_nested(arbre_mat, "densite_kg_m3", default=0.0))),

        rayon_conge_mm=_mm(_get_nested(cao, "rayon_conge_epaulement_m", default=0.0)),
        chanfrein_mm=_mm(_get_nested(cao, "chanfrein_extremite_m", default=0.0)),
        note_cao=str(_get_nested(cao, "note", default="") or ""),

        rapport_complet=rapport,
    )


# ============================================================
# VUE DE CÔTÉ DÉTAILLÉE
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisArbreMoteur):
    L = d.longueur_totale_mm
    D = d.diametre_nominal_mm

    if L <= 0 or D <= 0:
        ax.text(0.5, 0.5, "Données géométriques insuffisantes", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de côté")
        ax.set_axis_off()
        return

    y = D / 2.0

    x0 = 0.0
    x1 = L

    # Matière
    _add_hatched_rect(ax, x0, -y, L, D)

    # Contour arbre
    ax.add_patch(Rectangle((x0, -y), L, D, fill=False, linewidth=1.6))

    # Axe
    ax.axhline(0, **_linestyle_axe())

    # Répartition indicative des zones si on a les longueurs
    x_emp_in = d.empilement_entree_mm
    x_bloc = x_emp_in + d.bloc_cylindres_L_mm
    x_emp_out = x_bloc + d.empilement_sortie_mm

    if d.empilement_entree_mm > 0:
        ax.add_line(Line2D([x_emp_in, x_emp_in], [-y, y], **_linestyle_hidden()))
    if d.bloc_cylindres_L_mm > 0:
        ax.add_line(Line2D([x_bloc, x_bloc], [-y, y], **_linestyle_hidden()))

    # Zone clavette schématique
    if d.clavette_b_mm > 0 and d.clavette_h_mm > 0 and d.clavette_L_mm > 0:
        # Position conventionnelle : côté entrée, centrée dans empilement entrée si dispo
        if d.empilement_entree_mm > 0:
            xk0 = max(0.0, 0.5 * (d.empilement_entree_mm - d.clavette_L_mm))
        else:
            xk0 = 0.08 * L
        xk1 = min(L, xk0 + d.clavette_L_mm)

        rainure_h = d.rainure_arbre_mm if d.rainure_arbre_mm > 0 else min(d.clavette_h_mm * 0.5, y * 0.6)
        ax.add_patch(
            Rectangle(
                (xk0, y - rainure_h),
                xk1 - xk0,
                rainure_h,
                fill=False,
                linewidth=1.0,
                linestyle=(0, (4, 4)),
            )
        )
        _annotate_leader(ax, xk0, y + 18.0, xk0 + 0.5 * (xk1 - xk0), y - 0.5 * rainure_h, "Rainure de clavette")

        # Cote longueur clavette
        _add_dimension_h(ax, xk0, xk1, 0.0, y + 34.0, f"L clavette = {_fmt_mm(d.clavette_L_mm)}")

    # Interfaces
    if d.largeur_moyeu_mm > 0:
        xm0 = 0.0
        xm1 = min(L, d.largeur_moyeu_mm)
        ax.add_patch(Rectangle((xm0, -y * 0.82), xm1 - xm0, 1.64 * y, fill=False, linewidth=1.0, linestyle=(0, (3, 3))))
        _annotate_leader(ax, xm1 + 10.0, y + 18.0, 0.5 * (xm0 + xm1), y * 0.82, "Zone moyeu")

    if d.largeur_roulement_mm > 0:
        xr1 = L
        xr0 = max(0.0, xr1 - d.largeur_roulement_mm)
        ax.add_patch(Rectangle((xr0, -y * 0.78), xr1 - xr0, 1.56 * y, fill=False, linewidth=1.0, linestyle=(0, (3, 3))))
        _annotate_leader(ax, xr0 - 65.0, y + 18.0, 0.5 * (xr0 + xr1), y * 0.78, "Portée roulement")

    # Leaders généraux
    _annotate_leader(ax, 0.18 * L, y + 52.0, 0.18 * L, y, "Arbre nominal")
    if d.empilement_entree_mm > 0:
        _annotate_leader(ax, 0.02 * L, -(y + 24.0), 0.5 * d.empilement_entree_mm, -y, "Côté entrée")
    if d.empilement_sortie_mm > 0:
        _annotate_leader(ax, max(0.65 * L, x_bloc + 10.0), -(y + 24.0), L - 0.5 * d.empilement_sortie_mm, -y, "Côté sortie")

    # Cotes
    ydim1 = y + 14.0
    ydim2 = y + 28.0
    ydim3 = y + 42.0
    ydim4 = y + 56.0

    _add_dimension_h(ax, x0, x1, 0.0, ydim1, f"L totale = {_fmt_mm(L)}")

    if d.empilement_entree_mm > 0:
        _add_dimension_h(ax, x0, x_emp_in, 0.0, ydim2, f"Emp. entrée = {_fmt_mm(d.empilement_entree_mm)}")
    if d.bloc_cylindres_L_mm > 0:
        _add_dimension_h(ax, x_emp_in, x_bloc, 0.0, ydim3, f"Bloc cylindres = {_fmt_mm(d.bloc_cylindres_L_mm)}")
    if d.empilement_sortie_mm > 0:
        _add_dimension_h(ax, x_bloc, min(L, x_bloc + d.empilement_sortie_mm), 0.0, ydim4, f"Emp. sortie = {_fmt_mm(d.empilement_sortie_mm)}")

    xdim = L + 22.0
    _add_dimension_v(ax, 0.0, xdim, -y, y, f"Ø arbre = {_fmt_mm(D)}")

    # Bloc infos local
    infos = []
    if d.rayon_conge_mm > 0:
        infos.append(f"Rayon congé          : {_fmt_mm(d.rayon_conge_mm)}")
    if d.chanfrein_mm > 0:
        infos.append(f"Chanfrein extrémité  : {_fmt_mm(d.chanfrein_mm)}")
    if d.norme_din:
        infos.append(f"Norme clavette       : {d.norme_din}")
    if d.clavette_b_mm > 0 and d.clavette_h_mm > 0:
        infos.append(f"Clavette b x h       : {_fmt_mm(d.clavette_b_mm)} x {_fmt_mm(d.clavette_h_mm)}")
    if d.rainure_arbre_mm > 0:
        infos.append(f"Rainure arbre        : {_fmt_mm(d.rainure_arbre_mm)}")
    if d.rainure_moyeu_mm > 0:
        infos.append(f"Rainure moyeu        : {_fmt_mm(d.rainure_moyeu_mm)}")
    if d.note_cao:
        infos.append("Note CAO             : modèle axial simplifié")

    if infos:
        ax.text(
            x0,
            -(y + 36.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.6,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    ax.set_title("Vue de côté détaillée")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-80.0, L + 90.0)
    ax.set_ylim(-(y + 70.0), y + 70.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE DE FACE SECTION NOMINALE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisArbreMoteur):
    R = d.diametre_nominal_mm / 2.0 if d.diametre_nominal_mm > 0 else 0.0
    if R <= 0:
        ax.text(0.5, 0.5, "Diamètre absent", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de face")
        ax.set_axis_off()
        return

    ax.add_patch(Circle((0, 0), R, fill=False, linewidth=1.5, edgecolor="black"))
    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    txt = [f"Ø = {_fmt_mm(d.diametre_nominal_mm)}"]
    if d.d_max_passage_mm > 0:
        txt.append(f"Ø max passage = {_fmt_mm(d.d_max_passage_mm)}")

    lim = R + 24.0
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

    ax.set_title("Vue de face - Section nominale")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# DÉTAIL DE CLAVETTE
# ============================================================

def _tracer_detail_clavette(ax, d: DonneesCroquisArbreMoteur):
    if d.diametre_nominal_mm <= 0 or d.clavette_b_mm <= 0 or d.clavette_h_mm <= 0:
        ax.text(0.5, 0.5, "Détail clavette non disponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Détail clavette")
        ax.set_axis_off()
        return

    D = d.diametre_nominal_mm
    R = D / 2.0

    # Représentation simplifiée coupe radiale :
    # arbre en bas, clavette au dessus, moyeu schématique
    x0 = 0.0
    y0 = 0.0

    # arbre
    ax.add_patch(Rectangle((x0, y0), D, R, fill=False, linewidth=1.4))
    _add_hatched_rect(ax, x0, y0, D, R)

    # rainure arbre
    if d.rainure_arbre_mm > 0 and d.clavette_b_mm > 0:
        xr = x0 + 0.5 * (D - d.clavette_b_mm)
        ax.add_patch(Rectangle((xr, R - d.rainure_arbre_mm), d.clavette_b_mm, d.rainure_arbre_mm, fill=False, linewidth=1.0))

    # clavette
    xk = x0 + 0.5 * (D - d.clavette_b_mm)
    yk = R - d.rainure_arbre_mm
    ax.add_patch(Rectangle((xk, yk), d.clavette_b_mm, d.clavette_h_mm, fill=False, linewidth=1.3))

    # moyeu schématique
    Hm = max(d.clavette_h_mm * 2.4, R * 0.9)
    ax.add_patch(Rectangle((x0 - 0.18 * D, R), 1.36 * D, Hm, fill=False, linewidth=1.0, linestyle=(0, (4, 4))))

    # rainure moyeu
    if d.rainure_moyeu_mm > 0:
        ax.add_patch(Rectangle((xk, R), d.clavette_b_mm, d.rainure_moyeu_mm, fill=False, linewidth=1.0))

    # annotations
    _annotate_leader(ax, x0 + 1.05 * D, y0 + 0.2 * R, x0 + 0.5 * D, 0.35 * R, "Arbre")
    _annotate_leader(ax, x0 + 1.05 * D, yk + 0.5 * d.clavette_h_mm, xk + 0.5 * d.clavette_b_mm, yk + 0.5 * d.clavette_h_mm, "Clavette")
    _annotate_leader(ax, x0 + 1.05 * D, R + 0.7 * Hm, x0 + 0.55 * D, R + 0.7 * Hm, "Moyeu")

    # cotes
    _add_dimension_h(ax, xk, xk + d.clavette_b_mm, y0, R + Hm + 12.0, f"b = {_fmt_mm(d.clavette_b_mm)}")
    _add_dimension_v(ax, x0 - 12.0, x0 - 26.0, yk, yk + d.clavette_h_mm, f"h = {_fmt_mm(d.clavette_h_mm)}")

    if d.rainure_arbre_mm > 0:
        _add_dimension_v(ax, x0 + D + 10.0, x0 + D + 24.0, R - d.rainure_arbre_mm, R, f"t2 = {_fmt_mm(d.rainure_arbre_mm)}")
    if d.rainure_moyeu_mm > 0:
        _add_dimension_v(ax, x0 + D + 34.0, x0 + D + 48.0, R, R + d.rainure_moyeu_mm, f"t4 = {_fmt_mm(d.rainure_moyeu_mm)}")

    txt = []
    if d.clavette_L_cisaillement_mm > 0:
        txt.append(f"L min cisaillement = {_fmt_mm(d.clavette_L_cisaillement_mm)}")
    if d.clavette_L_ecrasement_mm > 0:
        txt.append(f"L min écrasement   = {_fmt_mm(d.clavette_L_ecrasement_mm)}")
    if d.clavette_L_disponible_mm > 0:
        txt.append(f"L disponible       = {_fmt_mm(d.clavette_L_disponible_mm)}")
    if d.clavette_longueur_ok is not None:
        txt.append(f"Vérif L            = {'OK' if d.clavette_longueur_ok else 'NON OK'}")

    if txt:
        ax.text(
            x0,
            -(0.32 * D),
            "\n".join(txt),
            ha="left",
            va="top",
            fontsize=8.5,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    ax.set_title("Détail rainure / clavette / moyeu")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.35 * D, 1.75 * D)
    ax.set_ylim(-0.5 * D, R + Hm + 28.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# IMPLANTATION LONGITUDINALE
# ============================================================

def _tracer_implantation(ax, d: DonneesCroquisArbreMoteur):
    ax.set_title("Implantation longitudinale calculée")
    ax.axhline(0, **_linestyle_axe())

    L = d.longueur_totale_mm
    if L <= 0:
        ax.text(0.5, 0.5, "Longueur totale non disponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return

    x0 = 0.0
    xe = d.empilement_entree_mm
    xb = xe + d.bloc_cylindres_L_mm
    xs = xb + d.empilement_sortie_mm

    ax.add_line(Line2D([x0, L], [0, 0], linewidth=1.5, color="black"))
    ax.plot([x0, xe, xb, xs], [0, 0, 0, 0], marker="|", linestyle="None", color="black", markersize=18)

    if d.empilement_entree_mm > 0:
        _annotate_leader(ax, x0, 18.0, 0.5 * xe, 0.0, "Empilement entrée")
        _add_dimension_h(ax, x0, xe, 0.0, 28.0, _fmt_mm(d.empilement_entree_mm))
    if d.bloc_cylindres_L_mm > 0:
        _annotate_leader(ax, xe + 10.0, 18.0, xe + 0.5 * d.bloc_cylindres_L_mm, 0.0, "Bloc cylindres")
        _add_dimension_h(ax, xe, xb, 0.0, 44.0, _fmt_mm(d.bloc_cylindres_L_mm))
    if d.empilement_sortie_mm > 0:
        _annotate_leader(ax, xb + 10.0, 18.0, xb + 0.5 * d.empilement_sortie_mm, 0.0, "Empilement sortie")
        _add_dimension_h(ax, xb, xs, 0.0, 60.0, _fmt_mm(d.empilement_sortie_mm))

    _add_dimension_h(ax, x0, L, 0.0, 78.0, f"L totale = {_fmt_mm(L)}")

    txt = []
    if d.nombre_cylindres > 0:
        txt.append(f"Nombre cylindres  : {d.nombre_cylindres}")
    if d.entraxe_cylindres_mm > 0:
        txt.append(f"Entraxe cyl.      : {_fmt_mm(d.entraxe_cylindres_mm)}")
    if d.diametre_externe_cylindre_mm > 0:
        txt.append(f"Ø ext cylindre    : {_fmt_mm(d.diametre_externe_cylindre_mm)}")
    if d.depassement_entree_mm > 0:
        txt.append(f"Dépassement entrée: {_fmt_mm(d.depassement_entree_mm)}")
    if d.depassement_sortie_mm > 0:
        txt.append(f"Dépassement sortie: {_fmt_mm(d.depassement_sortie_mm)}")

    if txt:
        ax.text(
            x0,
            -22.0,
            "\n".join(txt),
            ha="left",
            va="top",
            fontsize=8.5,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    ax.set_xlim(-40.0, L + 40.0)
    ax.set_ylim(-55.0, 100.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisArbreMoteur):
    lines = [
        f"Ø nominal arbre          : {_fmt_mm(d.diametre_nominal_mm) if d.diametre_nominal_mm > 0 else 'N/A'}",
        f"Longueur totale          : {_fmt_mm(d.longueur_totale_mm) if d.longueur_totale_mm > 0 else 'N/A'}",
        f"Couple max               : {_fmt_nm(d.couple_max_Nm) if d.couple_max_Nm >= 0 else 'N/A'}",
        f"rpm                      : {f'{d.rpm:.2f}' if d.rpm > 0 else 'N/A'}",
        f"Moment flexion max       : {_fmt_nm(d.moment_flexion_max_Nm) if d.moment_flexion_max_Nm > 0 else 'N/A'}",
        f"Force radiale            : {_fmt_n(d.force_radiale_N) if d.force_radiale_N > 0 else 'N/A'}",
        f"Force axiale             : {_fmt_n(d.force_axiale_N) if d.force_axiale_N > 0 else 'N/A'}",
        f"d min torsion            : {_fmt_mm(d.d_min_torsion_mm) if d.d_min_torsion_mm > 0 else 'N/A'}",
        f"d min flexion            : {_fmt_mm(d.d_min_flexion_mm) if d.d_min_flexion_mm > 0 else 'N/A'}",
        f"d min traction           : {_fmt_mm(d.d_min_traction_mm) if d.d_min_traction_mm > 0 else 'N/A'}",
        f"d min VM combiné         : {_fmt_mm(d.d_min_vm_mm) if d.d_min_vm_mm > 0 else 'N/A'}",
        f"d min global             : {_fmt_mm(d.d_min_global_mm) if d.d_min_global_mm > 0 else 'N/A'}",
        f"d max passage            : {_fmt_mm(d.d_max_passage_mm) if d.d_max_passage_mm > 0 else 'N/A'}",
        f"τ adm arbre              : {_fmt_pa(d.tau_adm_arbre_pa) if d.tau_adm_arbre_pa > 0 else 'N/A'}",
        f"σ adm arbre              : {_fmt_pa(d.sigma_adm_arbre_pa) if d.sigma_adm_arbre_pa > 0 else 'N/A'}",
        f"τ adm clavette           : {_fmt_pa(d.tau_adm_clavette_pa) if d.tau_adm_clavette_pa > 0 else 'N/A'}",
        f"σ adm appui              : {_fmt_pa(d.sigma_adm_appui_pa) if d.sigma_adm_appui_pa > 0 else 'N/A'}",
        f"Check d >= dmin          : {d.check_d_vs_dmin_ok if d.check_d_vs_dmin_ok is not None else 'N/A'}",
        f"Check d <= passage       : {d.check_d_vs_passage_ok if d.check_d_vs_passage_ok is not None else 'N/A'}",
        f"Clavette norme           : {d.norme_din or 'N/A'}",
        f"Clavette b               : {_fmt_mm(d.clavette_b_mm) if d.clavette_b_mm > 0 else 'N/A'}",
        f"Clavette h               : {_fmt_mm(d.clavette_h_mm) if d.clavette_h_mm > 0 else 'N/A'}",
        f"Clavette L requise       : {_fmt_mm(d.clavette_L_mm) if d.clavette_L_mm > 0 else 'N/A'}",
        f"Clavette L cisaillement  : {_fmt_mm(d.clavette_L_cisaillement_mm) if d.clavette_L_cisaillement_mm > 0 else 'N/A'}",
        f"Clavette L écrasement    : {_fmt_mm(d.clavette_L_ecrasement_mm) if d.clavette_L_ecrasement_mm > 0 else 'N/A'}",
        f"Clavette L disponible    : {_fmt_mm(d.clavette_L_disponible_mm) if d.clavette_L_disponible_mm > 0 else 'N/A'}",
        f"Vérif clavette           : {d.clavette_longueur_ok if d.clavette_longueur_ok is not None else 'N/A'}",
        f"Largeur moyeu            : {_fmt_mm(d.largeur_moyeu_mm) if d.largeur_moyeu_mm > 0 else 'N/A'}",
        f"Largeur roulement        : {_fmt_mm(d.largeur_roulement_mm) if d.largeur_roulement_mm > 0 else 'N/A'}",
        f"Bloc cylindres           : {_fmt_mm(d.bloc_cylindres_L_mm) if d.bloc_cylindres_L_mm > 0 else 'N/A'}",
        f"Empilement entrée        : {_fmt_mm(d.empilement_entree_mm) if d.empilement_entree_mm > 0 else 'N/A'}",
        f"Empilement sortie        : {_fmt_mm(d.empilement_sortie_mm) if d.empilement_sortie_mm > 0 else 'N/A'}",
        f"Masse modèle             : {f'{d.masse_modele_kg:.4f} kg' if d.masse_modele_kg > 0 else 'N/A'}",
        f"Volume modèle            : {_fmt_m3(d.volume_modele_m3) if d.volume_modele_m3 > 0 else 'N/A'}",
        f"Inertie polaire modèle   : {_fmt_kgm2(d.inertie_polaire_modele_kg_m2) if d.inertie_polaire_modele_kg_m2 > 0 else 'N/A'}",
        f"Densité                  : {f'{d.densite_kg_m3:.2f} kg/m³' if d.densite_kg_m3 > 0 else 'N/A'}",
        f"Rayon congé              : {_fmt_mm(d.rayon_conge_mm) if d.rayon_conge_mm > 0 else 'N/A'}",
        f"Chanfrein                : {_fmt_mm(d.chanfrein_mm) if d.chanfrein_mm > 0 else 'N/A'}",
    ]

    fig.text(
        0.012,
        0.015,
        "DONNÉES EXTRAITES DE ArbreMoteur.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=8.1,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_arbre_moteur_2d(
    arbre: ArbreMoteur,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Arbre moteur",
):
    d = extraire_donnees_croquis(arbre)

    if d.diametre_nominal_mm <= 0 and d.longueur_totale_mm <= 0:
        raise ValueError("Impossible de tracer : diamètre nominal et longueur totale absents.")

    fig = plt.figure(figsize=(19, 11))
    gs = fig.add_gridspec(2, 3, height_ratios=[2.15, 1.3], width_ratios=[1.6, 1.15, 1.25])

    ax_side = fig.add_subplot(gs[0, :])
    ax_face = fig.add_subplot(gs[1, 0])
    ax_key = fig.add_subplot(gs[1, 1])
    ax_layout = fig.add_subplot(gs[1, 2])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_cote(ax_side, d)
    _tracer_vue_face(ax_face, d)
    _tracer_detail_clavette(ax_key, d)
    _tracer_implantation(ax_layout, d)

    _ajouter_cartouche_technique(fig, d)

    plt.tight_layout(rect=[0.0, 0.11, 1.0, 0.965])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, {
        "vue_cote": ax_side,
        "vue_face": ax_face,
        "detail_clavette": ax_key,
        "implantation": ax_layout,
    }, d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

if __name__ == "__main__":
    a = ArbreMoteur(
        couple_max_Nm=120.0,
        moment_flexion_max_Nm=40.0,
        nombre_cylindres=2,
        entraxe_cylindres_m=0.120,
        diametre_externe_cylindre_m=0.090,
        depassement_cote_entree_m=0.020,
        depassement_cote_sortie_m=0.015,
        limite_elastique_arbre_pa=700e6,
        densite_arbre_kg_m3=7800.0,
        facteur_securite=2.0,
        limite_elastique_clavette_pa=500e6,
        limite_elastique_moyeu_pa=450e6,
    )

    tracer_croquis_arbre_moteur_2d(
        a,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Arbre moteur calculé",
    )