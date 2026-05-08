# frontend/pieces/sketches_2d/vilbrequin.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, Circle

from backend.components.moteur_thermique.pieces.vilbrequin import Vilbrequin


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


def _fmt_kg(v: float) -> str:
    return f"{v:.6f} kg"


def _fmt_pa(v: float) -> str:
    return f"{v:.6e} Pa"


def _fmt_nmpa(v: float) -> str:
    return f"{v:.6e} N·m/rad"


def _fmt_kgm2(v: float) -> str:
    return f"{v:.6e} kg·m²"


def _fmt_nm(v: float) -> str:
    return f"{v:.6f} N·m"


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
class DonneesCroquisVilbrequin:
    course_mm: float = 0.0
    rayon_manivelle_mm: float = 0.0
    rpm: float = 0.0
    couple_max_nm: float = 0.0
    moment_flexion_max_nm: float = 0.0

    d_journal_mm: float = 0.0
    L_journal_mm: float = 0.0
    d_maneton_mm: float = 0.0
    L_maneton_mm: float = 0.0

    nb_journaux: int = 0
    nb_manetons: int = 0

    densite_kg_m3: float = 0.0
    limite_elastique_pa: float = 0.0
    module_young_pa: float = 0.0
    poisson: float = 0.0
    resistance_traction_pa: float = 0.0
    limite_fatigue_pa: float = 0.0

    module_cisaillement_pa: float = 0.0
    module_compressibilite_pa: float = 0.0
    rigidite_specifique: float = 0.0

    V_journal_unitaire_m3: float = 0.0
    V_maneton_unitaire_m3: float = 0.0
    V_journaux_total_m3: float = 0.0
    V_manetons_total_m3: float = 0.0
    V_webs_total_m3: float = 0.0
    V_contrepoids_total_m3: float = 0.0
    V_total_modele_m3: float = 0.0

    m_journal_unitaire_kg: float = 0.0
    m_maneton_unitaire_kg: float = 0.0
    m_journaux_total_kg: float = 0.0
    m_manetons_total_kg: float = 0.0
    m_webs_total_kg: float = 0.0
    m_contrepoids_total_kg: float = 0.0
    m_totale_modele_kg: float = 0.0

    I_journal_unitaire_kgm2: float = 0.0
    I_journaux_total_kgm2: float = 0.0
    I_maneton_son_axe_kgm2: float = 0.0
    I_maneton_axe_vilebrequin_kgm2: float = 0.0
    I_manetons_total_kgm2: float = 0.0
    I_totale_minimale_kgm2: float = 0.0

    J_journal_m4: float = 0.0
    k_journal_nm_rad: float = 0.0
    L_eq_mm: float = 0.0
    k_eq_nm_rad: float = 0.0

    tau_journal_pa: float = 0.0
    sigma_journal_pa: float = 0.0
    sigma_vm_journal_pa: float = 0.0
    sigma_adm_journal_pa: float = 0.0
    marge_vm_journal: float = 0.0

    tau_maneton_pa: float = 0.0
    sigma_maneton_pa: float = 0.0
    sigma_vm_maneton_pa: float = 0.0
    sigma_adm_maneton_pa: float = 0.0
    marge_vm_maneton: float = 0.0

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(vilbrequin: Vilbrequin) -> DonneesCroquisVilbrequin:
    rap = vilbrequin.analyser(strict=False)

    cin = rap.get("cinematique", {})
    geo = rap.get("geometrie", {})
    mat = rap.get("materiau", {})
    prop = rap.get("proprietes_derivees", {})
    vols = rap.get("volumes", {})
    masses = rap.get("masses", {})
    inert = rap.get("inerties", {})
    raid = rap.get("raideur", {})
    ctr = rap.get("contraintes", {})
    ctr_j = ctr.get("journal_principal", {}) if isinstance(ctr.get("journal_principal"), dict) else {}
    ctr_m = ctr.get("maneton", {}) if isinstance(ctr.get("maneton"), dict) else {}
    raid_j = raid.get("journal_type", {}) if isinstance(raid.get("journal_type"), dict) else {}
    raid_eq = raid.get("equivalente_modele", {}) if isinstance(raid.get("equivalente_modele"), dict) else {}

    return DonneesCroquisVilbrequin(
        course_mm=_mm(_get_nested(cin, "course_m", default=0.0)),
        rayon_manivelle_mm=_mm(_get_nested(cin, "rayon_manivelle_m", default=0.0)),
        rpm=_safe_float(_get_nested(cin, "rpm", default=0.0)),
        couple_max_nm=_safe_float(_get_nested(cin, "couple_max_Nm", default=0.0)),
        moment_flexion_max_nm=_safe_float(_get_nested(cin, "moment_flexion_max_Nm", default=0.0)),

        d_journal_mm=_mm(_get_nested(geo, "diametre_journal_principal_m", default=0.0)),
        L_journal_mm=_mm(_get_nested(geo, "largeur_portee_journal_m", default=0.0)),
        d_maneton_mm=_mm(_get_nested(geo, "diametre_maneton_m", default=0.0)),
        L_maneton_mm=_mm(_get_nested(geo, "largeur_portee_maneton_m", default=0.0)),

        nb_journaux=int(_safe_float(_get_nested(geo, "nb_journaux_principaux", default=0), 0)),
        nb_manetons=int(_safe_float(_get_nested(geo, "nb_manetons", default=0), 0)),

        densite_kg_m3=_safe_float(_get_nested(mat, "densite_kg_m3", default=0.0)),
        limite_elastique_pa=_safe_float(_get_nested(mat, "limite_elastique_pa", default=0.0)),
        module_young_pa=_safe_float(_get_nested(mat, "module_young_pa", default=0.0)),
        poisson=_safe_float(_get_nested(mat, "poisson", default=0.0)),
        resistance_traction_pa=_safe_float(_get_nested(mat, "resistance_traction_pa", default=0.0)),
        limite_fatigue_pa=_safe_float(_get_nested(mat, "limite_fatigue_pa", default=0.0)),

        module_cisaillement_pa=_safe_float(_get_nested(prop, "module_cisaillement_G_pa", default=0.0)),
        module_compressibilite_pa=_safe_float(_get_nested(prop, "module_compressibilite_K_pa", default=0.0)),
        rigidite_specifique=_safe_float(_get_nested(prop, "rigidite_specifique_E_sur_rho", default=0.0)),

        V_journal_unitaire_m3=_safe_float(_get_nested(vols, "journal_principal_unitaire_m3", default=0.0)),
        V_maneton_unitaire_m3=_safe_float(_get_nested(vols, "maneton_unitaire_m3", default=0.0)),
        V_journaux_total_m3=_safe_float(_get_nested(vols, "journaux_total_m3", default=0.0)),
        V_manetons_total_m3=_safe_float(_get_nested(vols, "manetons_total_m3", default=0.0)),
        V_webs_total_m3=_safe_float(_get_nested(vols, "webs_total_m3", default=0.0)),
        V_contrepoids_total_m3=_safe_float(_get_nested(vols, "contrepoids_total_m3", default=0.0)),
        V_total_modele_m3=_safe_float(_get_nested(vols, "volume_total_modele_m3", default=0.0)),

        m_journal_unitaire_kg=_safe_float(_get_nested(masses, "journal_principal_unitaire_kg", default=0.0)),
        m_maneton_unitaire_kg=_safe_float(_get_nested(masses, "maneton_unitaire_kg", default=0.0)),
        m_journaux_total_kg=_safe_float(_get_nested(masses, "journaux_total_kg", default=0.0)),
        m_manetons_total_kg=_safe_float(_get_nested(masses, "manetons_total_kg", default=0.0)),
        m_webs_total_kg=_safe_float(_get_nested(masses, "webs_total_kg", default=0.0)),
        m_contrepoids_total_kg=_safe_float(_get_nested(masses, "contrepoids_total_kg", default=0.0)),
        m_totale_modele_kg=_safe_float(_get_nested(masses, "masse_totale_modele_kg", default=0.0)),

        I_journal_unitaire_kgm2=_safe_float(_get_nested(inert, "journal_principal_unitaire_kg_m2", default=0.0)),
        I_journaux_total_kgm2=_safe_float(_get_nested(inert, "journaux_total_kg_m2", default=0.0)),
        I_maneton_son_axe_kgm2=_safe_float(_get_nested(inert, "maneton_unitaire_autour_son_axe_kg_m2", default=0.0)),
        I_maneton_axe_vilebrequin_kgm2=_safe_float(_get_nested(inert, "maneton_unitaire_autour_axe_vilbrequin_kg_m2", default=0.0)),
        I_manetons_total_kgm2=_safe_float(_get_nested(inert, "manetons_total_autour_axe_vilbrequin_kg_m2", default=0.0)),
        I_totale_minimale_kgm2=_safe_float(_get_nested(inert, "inertie_polaire_minimale_modele_kg_m2", default=0.0)),

        J_journal_m4=_safe_float(_get_nested(raid_j, "J_m4", default=0.0)),
        k_journal_nm_rad=_safe_float(_get_nested(raid_j, "k_Nm_par_rad", default=0.0)),
        L_eq_mm=_mm(_get_nested(raid_eq, "L_eq_m", default=0.0)),
        k_eq_nm_rad=_safe_float(_get_nested(raid_eq, "k_Nm_par_rad", default=0.0)),

        tau_journal_pa=_safe_float(_get_nested(ctr_j, "tau_torsion_pa", default=0.0)),
        sigma_journal_pa=_safe_float(_get_nested(ctr_j, "sigma_flexion_pa", default=0.0)),
        sigma_vm_journal_pa=_safe_float(_get_nested(ctr_j, "sigma_von_mises_pa", default=0.0)),
        sigma_adm_journal_pa=_safe_float(_get_nested(ctr_j, "sigma_admissible_pa", default=0.0)),
        marge_vm_journal=_safe_float(_get_nested(ctr_j, "marge_von_mises", default=0.0)),

        tau_maneton_pa=_safe_float(_get_nested(ctr_m, "tau_torsion_pa", default=0.0)),
        sigma_maneton_pa=_safe_float(_get_nested(ctr_m, "sigma_flexion_pa", default=0.0)),
        sigma_vm_maneton_pa=_safe_float(_get_nested(ctr_m, "sigma_von_mises_pa", default=0.0)),
        sigma_adm_maneton_pa=_safe_float(_get_nested(ctr_m, "sigma_admissible_pa", default=0.0)),
        marge_vm_maneton=_safe_float(_get_nested(ctr_m, "marge_von_mises", default=0.0)),

        rapport_complet=rap,
    )


# ============================================================
# VUE LONGITUDINALE SIMPLIFIÉE
# ============================================================

def _tracer_vue_longitudinale(ax, d: DonneesCroquisVilbrequin):
    if d.d_journal_mm <= 0 and d.d_maneton_mm <= 0:
        ax.text(0.5, 0.5, "Géométrie des portées indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue longitudinale simplifiée")
        ax.set_axis_off()
        return

    Dj = d.d_journal_mm if d.d_journal_mm > 0 else d.d_maneton_mm
    Lj = d.L_journal_mm if d.L_journal_mm > 0 else 20.0
    Dm = d.d_maneton_mm if d.d_maneton_mm > 0 else d.d_journal_mm
    Lm = d.L_maneton_mm if d.L_maneton_mm > 0 else 20.0
    r = d.rayon_manivelle_mm if d.rayon_manivelle_mm > 0 else 0.0

    yj = Dj / 2.0
    ym = Dm / 2.0

    x0 = 0.0
    x1 = Lj
    entre = max(20.0, 1.3 * Lm)
    xm0 = x1 + entre
    xm1 = xm0 + Lm
    x2 = xm1 + entre
    x3 = x2 + Lj

    # Journaux principaux
    _add_hatched_rect(ax, x0, -yj, Lj, 2.0 * yj)
    ax.add_patch(Rectangle((x0, -yj), Lj, 2.0 * yj, fill=False, linewidth=1.5))
    _add_hatched_rect(ax, x2, -yj, Lj, 2.0 * yj)
    ax.add_patch(Rectangle((x2, -yj), Lj, 2.0 * yj, fill=False, linewidth=1.5))

    # Maneton décalé
    _add_hatched_rect(ax, xm0, r - ym, Lm, 2.0 * ym)
    ax.add_patch(Rectangle((xm0, r - ym), Lm, 2.0 * ym, fill=False, linewidth=1.5))

    # Axes
    ax.add_line(Line2D([x0 - 10.0, x3 + 10.0], [0.0, 0.0], **_linestyle_axis()))
    ax.add_line(Line2D([xm0 - 10.0, xm1 + 10.0], [r, r], **_linestyle_hidden()))

    # Liaisons schématiques
    ax.add_line(Line2D([x1, xm0], [0.0, r], linewidth=1.0, color="black"))
    ax.add_line(Line2D([xm1, x2], [r, 0.0], linewidth=1.0, color="black"))

    # Annotations
    _annotate_leader(ax, x0 + 6.0, yj + 15.0, x0 + 0.5 * Lj, yj, "Journal principal G")
    _annotate_leader(ax, xm0 + 4.0, r + ym + 15.0, xm0 + 0.5 * Lm, r + ym, "Maneton")
    _annotate_leader(ax, x2 + 4.0, yj + 15.0, x2 + 0.5 * Lj, yj, "Journal principal D")

    # Cotes horizontales
    ydim1 = max(yj, r + ym) + 18.0
    ydim2 = ydim1 + 14.0
    ydim3 = ydim2 + 14.0

    _add_dimension_h(ax, x0, x1, 0.0, ydim1, f"L journal = {_fmt_mm(Lj)}")
    _add_dimension_h(ax, xm0, xm1, r, ydim2, f"L maneton = {_fmt_mm(Lm)}")
    _add_dimension_h(ax, x0, x3, 0.0, ydim3, f"Longueur schématique = {_fmt_mm(x3)}")

    # Cotes verticales
    xdim1 = x3 + 18.0
    xdim2 = x3 + 36.0
    xdim3 = x3 + 54.0

    _add_dimension_v(ax, 0.0, xdim1, -yj, yj, f"Ø journal = {_fmt_mm(Dj)}")
    _add_dimension_v(ax, xm0, xdim2, r - ym, r + ym, f"Ø maneton = {_fmt_mm(Dm)}")
    if r > 0:
        _add_dimension_v(ax, xm0 - 5.0, xdim3, 0.0, r, f"r = {_fmt_mm(r)}")

    # Infos techniques
    infos = []
    if d.course_mm > 0:
        infos.append(f"Course              : {_fmt_mm(d.course_mm)}")
    if d.rpm > 0:
        infos.append(f"Régime              : {d.rpm:.2f} rpm")
    if d.couple_max_nm != 0:
        infos.append(f"Couple max          : {_fmt_nm(d.couple_max_nm)}")
    if d.moment_flexion_max_nm != 0:
        infos.append(f"Moment flexion max  : {_fmt_nm(d.moment_flexion_max_nm)}")
    if d.nb_journaux > 0:
        infos.append(f"Nb journaux         : {d.nb_journaux}")
    if d.nb_manetons > 0:
        infos.append(f"Nb manetons         : {d.nb_manetons}")

    if infos:
        ax.text(
            x0,
            -(max(yj, ym) + 28.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.4,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
        )

    ax.set_title("Vue longitudinale simplifiée du vilebrequin")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-18.0, x3 + 90.0)
    ax.set_ylim(-(max(yj, ym) + 60.0), max(ydim3 + 14.0, r + ym + 35.0))
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUES DE FACE
# ============================================================

def _tracer_vue_face(ax, diam_mm: float, titre: str, txt_extra: Optional[list[str]] = None):
    if diam_mm <= 0:
        ax.text(0.5, 0.5, "Diamètre indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(titre)
        ax.set_axis_off()
        return

    R = diam_mm / 2.0
    ax.add_patch(Circle((0.0, 0.0), R, fill=False, linewidth=1.5))
    ax.axhline(0.0, **_linestyle_axis())
    ax.axvline(0.0, **_linestyle_axis())

    lines = [f"Ø = {_fmt_mm(diam_mm)}"]
    if txt_extra:
        lines.extend(txt_extra)

    lim = R + 22.0
    ax.text(
        -lim + 4.0,
        -lim + 4.0,
        "\n".join(lines),
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
# SCHÉMA SYNTHÉTIQUE MÉCANIQUE
# ============================================================

def _tracer_schema_mecanique(ax, d: DonneesCroquisVilbrequin):
    ax.set_title("Synthèse mécanique")
    ax.axis("off")

    lines = [
        f"Volume journal unitaire           : {_fmt_m3(d.V_journal_unitaire_m3) if d.V_journal_unitaire_m3 > 0 else 'N/A'}",
        f"Volume maneton unitaire           : {_fmt_m3(d.V_maneton_unitaire_m3) if d.V_maneton_unitaire_m3 > 0 else 'N/A'}",
        f"Volume journaux total             : {_fmt_m3(d.V_journaux_total_m3) if d.V_journaux_total_m3 > 0 else 'N/A'}",
        f"Volume manetons total             : {_fmt_m3(d.V_manetons_total_m3) if d.V_manetons_total_m3 > 0 else 'N/A'}",
        f"Volume webs total                 : {_fmt_m3(d.V_webs_total_m3) if d.V_webs_total_m3 > 0 else 'N/A'}",
        f"Volume contrepoids total          : {_fmt_m3(d.V_contrepoids_total_m3) if d.V_contrepoids_total_m3 > 0 else 'N/A'}",
        f"Volume total modèle               : {_fmt_m3(d.V_total_modele_m3) if d.V_total_modele_m3 > 0 else 'N/A'}",
        "",
        f"Masse journal unitaire            : {_fmt_kg(d.m_journal_unitaire_kg) if d.m_journal_unitaire_kg > 0 else 'N/A'}",
        f"Masse maneton unitaire            : {_fmt_kg(d.m_maneton_unitaire_kg) if d.m_maneton_unitaire_kg > 0 else 'N/A'}",
        f"Masse journaux total              : {_fmt_kg(d.m_journaux_total_kg) if d.m_journaux_total_kg > 0 else 'N/A'}",
        f"Masse manetons total              : {_fmt_kg(d.m_manetons_total_kg) if d.m_manetons_total_kg > 0 else 'N/A'}",
        f"Masse webs total                  : {_fmt_kg(d.m_webs_total_kg) if d.m_webs_total_kg > 0 else 'N/A'}",
        f"Masse contrepoids total           : {_fmt_kg(d.m_contrepoids_total_kg) if d.m_contrepoids_total_kg > 0 else 'N/A'}",
        f"Masse totale modèle               : {_fmt_kg(d.m_totale_modele_kg) if d.m_totale_modele_kg > 0 else 'N/A'}",
        "",
        f"Inertie journal unitaire          : {_fmt_kgm2(d.I_journal_unitaire_kgm2) if d.I_journal_unitaire_kgm2 > 0 else 'N/A'}",
        f"Inertie journaux total            : {_fmt_kgm2(d.I_journaux_total_kgm2) if d.I_journaux_total_kgm2 > 0 else 'N/A'}",
        f"Inertie maneton / son axe         : {_fmt_kgm2(d.I_maneton_son_axe_kgm2) if d.I_maneton_son_axe_kgm2 > 0 else 'N/A'}",
        f"Inertie maneton / axe vilebrequin : {_fmt_kgm2(d.I_maneton_axe_vilebrequin_kgm2) if d.I_maneton_axe_vilebrequin_kgm2 > 0 else 'N/A'}",
        f"Inertie manetons total            : {_fmt_kgm2(d.I_manetons_total_kgm2) if d.I_manetons_total_kgm2 > 0 else 'N/A'}",
        f"Inertie totale minimale modèle    : {_fmt_kgm2(d.I_totale_minimale_kgm2) if d.I_totale_minimale_kgm2 > 0 else 'N/A'}",
        "",
        f"J journal                         : {f'{d.J_journal_m4:.6e} m⁴' if d.J_journal_m4 > 0 else 'N/A'}",
        f"k journal type                    : {_fmt_nmpa(d.k_journal_nm_rad) if d.k_journal_nm_rad > 0 else 'N/A'}",
        f"L_eq torsion                      : {_fmt_mm(d.L_eq_mm) if d.L_eq_mm > 0 else 'N/A'}",
        f"k équivalente modèle              : {_fmt_nmpa(d.k_eq_nm_rad) if d.k_eq_nm_rad > 0 else 'N/A'}",
        "",
        f"tau journal                       : {_fmt_pa(d.tau_journal_pa) if d.tau_journal_pa > 0 else 'N/A'}",
        f"sigma journal                     : {_fmt_pa(d.sigma_journal_pa) if d.sigma_journal_pa > 0 else 'N/A'}",
        f"sigma VM journal                  : {_fmt_pa(d.sigma_vm_journal_pa) if d.sigma_vm_journal_pa > 0 else 'N/A'}",
        f"sigma adm journal                 : {_fmt_pa(d.sigma_adm_journal_pa) if d.sigma_adm_journal_pa > 0 else 'N/A'}",
        f"marge VM journal                  : {f'{d.marge_vm_journal:.6f}' if d.marge_vm_journal > 0 else 'N/A'}",
        "",
        f"tau maneton                       : {_fmt_pa(d.tau_maneton_pa) if d.tau_maneton_pa > 0 else 'N/A'}",
        f"sigma maneton                     : {_fmt_pa(d.sigma_maneton_pa) if d.sigma_maneton_pa > 0 else 'N/A'}",
        f"sigma VM maneton                  : {_fmt_pa(d.sigma_vm_maneton_pa) if d.sigma_vm_maneton_pa > 0 else 'N/A'}",
        f"sigma adm maneton                 : {_fmt_pa(d.sigma_adm_maneton_pa) if d.sigma_adm_maneton_pa > 0 else 'N/A'}",
        f"marge VM maneton                  : {f'{d.marge_vm_maneton:.6f}' if d.marge_vm_maneton > 0 else 'N/A'}",
    ]

    ax.text(
        0.02,
        0.98,
        "\n".join(lines),
        ha="left",
        va="top",
        fontsize=8.2,
        family="monospace",
        transform=ax.transAxes,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="black", linewidth=0.8),
    )


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche(fig, d: DonneesCroquisVilbrequin):
    lines = [
        f"Course                           : {_fmt_mm(d.course_mm) if d.course_mm > 0 else 'N/A'}",
        f"Rayon manivelle                  : {_fmt_mm(d.rayon_manivelle_mm) if d.rayon_manivelle_mm > 0 else 'N/A'}",
        f"Régime                           : {f'{d.rpm:.2f} rpm' if d.rpm > 0 else 'N/A'}",
        f"Couple max                       : {_fmt_nm(d.couple_max_nm) if d.couple_max_nm != 0 else 'N/A'}",
        f"Moment flexion max               : {_fmt_nm(d.moment_flexion_max_nm) if d.moment_flexion_max_nm != 0 else 'N/A'}",
        f"Ø journal principal              : {_fmt_mm(d.d_journal_mm) if d.d_journal_mm > 0 else 'N/A'}",
        f"L portée journal                 : {_fmt_mm(d.L_journal_mm) if d.L_journal_mm > 0 else 'N/A'}",
        f"Ø maneton                        : {_fmt_mm(d.d_maneton_mm) if d.d_maneton_mm > 0 else 'N/A'}",
        f"L portée maneton                 : {_fmt_mm(d.L_maneton_mm) if d.L_maneton_mm > 0 else 'N/A'}",
        f"Nb journaux principaux           : {d.nb_journaux if d.nb_journaux > 0 else 'N/A'}",
        f"Nb manetons                      : {d.nb_manetons if d.nb_manetons > 0 else 'N/A'}",
        f"Densité matériau                 : {f'{d.densite_kg_m3:.3f} kg/m³' if d.densite_kg_m3 > 0 else 'N/A'}",
        f"Limite élastique                 : {_fmt_pa(d.limite_elastique_pa) if d.limite_elastique_pa > 0 else 'N/A'}",
        f"Module Young                     : {_fmt_pa(d.module_young_pa) if d.module_young_pa > 0 else 'N/A'}",
        f"Poisson                          : {f'{d.poisson:.6f}' if d.poisson > 0 else 'N/A'}",
        f"Résistance traction              : {_fmt_pa(d.resistance_traction_pa) if d.resistance_traction_pa > 0 else 'N/A'}",
        f"Limite fatigue                   : {_fmt_pa(d.limite_fatigue_pa) if d.limite_fatigue_pa > 0 else 'N/A'}",
        f"Module cisaillement G            : {_fmt_pa(d.module_cisaillement_pa) if d.module_cisaillement_pa > 0 else 'N/A'}",
        f"Module compressibilité K         : {_fmt_pa(d.module_compressibilite_pa) if d.module_compressibilite_pa > 0 else 'N/A'}",
        f"Rigidité spécifique E/rho        : {f'{d.rigidite_specifique:.6e}' if d.rigidite_specifique > 0 else 'N/A'}",
    ]

    fig.text(
        0.012,
        0.014,
        "DONNÉES EXTRAITES DE Vilbrequin.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=7.8,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_vilbrequin_2d(
    vilbrequin: Vilbrequin,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Vilbrequin",
):
    d = extraire_donnees_croquis(vilbrequin)

    if d.d_journal_mm <= 0 and d.d_maneton_mm <= 0:
        raise ValueError("Impossible de tracer : aucun diamètre exploitable (journal/maneton).")

    fig = plt.figure(figsize=(19, 11))
    gs = fig.add_gridspec(2, 3, height_ratios=[2.0, 1.45], width_ratios=[1.35, 1.0, 1.25])

    ax_long = fig.add_subplot(gs[0, :])
    ax_j = fig.add_subplot(gs[1, 0])
    ax_m = fig.add_subplot(gs[1, 1])
    ax_syn = fig.add_subplot(gs[1, 2])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_longitudinale(ax_long, d)

    txt_j = []
    if d.L_journal_mm > 0:
        txt_j.append(f"L = {_fmt_mm(d.L_journal_mm)}")
    if d.m_journal_unitaire_kg > 0:
        txt_j.append(f"m = {_fmt_kg(d.m_journal_unitaire_kg)}")
    if d.I_journal_unitaire_kgm2 > 0:
        txt_j.append(f"I = {_fmt_kgm2(d.I_journal_unitaire_kgm2)}")
    _tracer_vue_face(ax_j, d.d_journal_mm, "Vue de face - Journal principal", txt_j)

    txt_m = []
    if d.L_maneton_mm > 0:
        txt_m.append(f"L = {_fmt_mm(d.L_maneton_mm)}")
    if d.m_maneton_unitaire_kg > 0:
        txt_m.append(f"m = {_fmt_kg(d.m_maneton_unitaire_kg)}")
    if d.I_maneton_axe_vilebrequin_kgm2 > 0:
        txt_m.append(f"I axe VB = {_fmt_kgm2(d.I_maneton_axe_vilebrequin_kgm2)}")
    _tracer_vue_face(ax_m, d.d_maneton_mm, "Vue de face - Maneton", txt_m)

    _tracer_schema_mecanique(ax_syn, d)
    _ajouter_cartouche(fig, d)

    plt.tight_layout(rect=[0.0, 0.11, 1.0, 0.965])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, {
        "vue_longitudinale": ax_long,
        "vue_face_journal": ax_j,
        "vue_face_maneton": ax_m,
        "synthese_mecanique": ax_syn,
    }, d


# ============================================================
# EXEMPLE D’UTILISATION
# ============================================================

if __name__ == "__main__":
    vb = Vilbrequin(
        nb_manetons=1,
        nb_journaux_principaux=2,
        course_m=0.085,
        couple_max_Nm=120.0,
        moment_flexion_max_Nm=40.0,
        materiau_cle=None,
        densite_kg_m3=7800.0,
        limite_elastique_pa=800e6,
        module_young_pa=210e9,
        poisson=0.3,
        facteur_securite=2.0,
        volume_webs_total_m3=1.2e-4,
        volume_contrepoids_total_m3=1.8e-4,
        longueur_torsion_equivalente_m=0.12,
    )

    tracer_croquis_vilbrequin_2d(
        vb,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Vilbrequin calculé",
    )