# frontend/pieces/sketches_2d/arbre_piston.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

from backend.pieces.arbre_piston import ArbrePiston


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
class DonneesCroquisArbrePiston:
    longueur_totale_mm: float = 0.0
    longueur_fut_mm: float = 0.0
    longueur_teton_g_mm: float = 0.0
    longueur_teton_d_mm: float = 0.0

    diametre_fut_ext_mm: float = 0.0
    diametre_fut_int_mm: float = 0.0
    diametre_teton_g_mm: float = 0.0
    diametre_teton_d_mm: float = 0.0
    diametre_portee_mm: float = 0.0

    rayon_conge_g_mm: float = 0.0
    rayon_conge_d_mm: float = 0.0
    chanfrein_g_mm: float = 0.0
    chanfrein_d_mm: float = 0.0

    filetage_g: str = ""
    filetage_d: str = ""
    profondeur_taraudage_g_mm: float = 0.0
    profondeur_taraudage_d_mm: float = 0.0

    x_fin_teton_g_mm: float = 0.0
    x_fin_fut_mm: float = 0.0
    x_fin_teton_d_mm: float = 0.0

    force_axiale_N: float = 0.0
    force_cisaillement_N: float = 0.0
    moment_flexion_Nm: float = 0.0
    couple_torsion_Nm: float = 0.0

    sigma_axiale_pa: float = 0.0
    sigma_flexion_pa: float = 0.0
    tau_transverse_pa: float = 0.0
    tau_torsion_pa: float = 0.0
    sigma_von_mises_pa: float = 0.0
    sigma_allow_pa: float = 0.0
    marge_sigma_vm: float = 0.0

    charge_critique_euler_N: float = 0.0
    marge_flambage: float = 0.0
    longueur_libre_mm: float = 0.0
    K_flambage: float = 0.0

    masse_kg: float = 0.0
    volume_total_m3: float = 0.0
    inertie_I_m4: float = 0.0
    inertie_J_m4: float = 0.0

    rpm: float = 0.0
    omega_rad_s: float = 0.0

    note_dimensionnement: str = ""
    evidement: bool = False

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(arbre: ArbrePiston) -> DonneesCroquisArbrePiston:
    rapport = arbre.analyser(strict=False)

    geo = rapport.get("geometrie", {})
    efforts = rapport.get("efforts", {})
    contraintes = rapport.get("contraintes", {})
    flambage = rapport.get("flambage", {})
    masse = rapport.get("masse", {})
    inerties = rapport.get("inerties", {})
    cin = rapport.get("cinematique", {})
    cao = rapport.get("cao", {})
    fut_cao = cao.get("fut_central", {}) if isinstance(cao, dict) else {}
    tg_cao = cao.get("teton_gauche", {}) if isinstance(cao, dict) else {}
    td_cao = cao.get("teton_droit", {}) if isinstance(cao, dict) else {}
    epg = cao.get("epaulement_gauche", {}) if isinstance(cao, dict) else {}
    epd = cao.get("epaulement_droit", {}) if isinstance(cao, dict) else {}
    axe_x = cao.get("axe_x", {}) if isinstance(cao, dict) else {}
    dim_evide = rapport.get("dimensionnement_evide", {})

    d_fut_ext = _get_nested(fut_cao, "diametre_exterieur_m", default=None)
    d_fut_int = _get_nested(fut_cao, "diametre_interieur_m", default=0.0)

    return DonneesCroquisArbrePiston(
        longueur_totale_mm=_mm(_get_nested(cao, "longueur_totale_m", default=_get_nested(geo, "longueur_totale_m", default=0.0))),
        longueur_fut_mm=_mm(_get_nested(geo, "longueur_fut_central_m", default=_get_nested(fut_cao, "longueur_m", default=0.0))),
        longueur_teton_g_mm=_mm(_get_nested(geo, "longueur_teton_gauche_m", default=_get_nested(tg_cao, "longueur_m", default=0.0))),
        longueur_teton_d_mm=_mm(_get_nested(geo, "longueur_teton_droit_m", default=_get_nested(td_cao, "longueur_m", default=0.0))),

        diametre_fut_ext_mm=_mm(d_fut_ext),
        diametre_fut_int_mm=_mm(d_fut_int),
        diametre_teton_g_mm=_mm(_get_nested(geo, "diametre_teton_gauche_m", default=_get_nested(tg_cao, "diametre_m", default=0.0))),
        diametre_teton_d_mm=_mm(_get_nested(geo, "diametre_teton_droit_m", default=_get_nested(td_cao, "diametre_m", default=0.0))),
        diametre_portee_mm=_mm(_get_nested(geo, "diametre_portee_coussinet_m", default=0.0)),

        rayon_conge_g_mm=_mm(_get_nested(epg, "rayon_conge_m", default=0.0)),
        rayon_conge_d_mm=_mm(_get_nested(epd, "rayon_conge_m", default=0.0)),
        chanfrein_g_mm=_mm(_get_nested(tg_cao, "chanfrein_extremite_m", default=0.0)),
        chanfrein_d_mm=_mm(_get_nested(td_cao, "chanfrein_extremite_m", default=0.0)),

        filetage_g=str(_get_nested(tg_cao, "filetage", default="") or ""),
        filetage_d=str(_get_nested(td_cao, "filetage", default="") or ""),
        profondeur_taraudage_g_mm=_mm(_get_nested(tg_cao, "profondeur_taraudage_m", default=0.0)),
        profondeur_taraudage_d_mm=_mm(_get_nested(td_cao, "profondeur_taraudage_m", default=0.0)),

        x_fin_teton_g_mm=_mm(_get_nested(axe_x, "x_fin_teton_gauche_m", default=0.0)),
        x_fin_fut_mm=_mm(_get_nested(axe_x, "x_fin_fut_central_m", default=0.0)),
        x_fin_teton_d_mm=_mm(_get_nested(axe_x, "x_fin_teton_droit_m", default=0.0)),

        force_axiale_N=_safe_float(_get_nested(efforts, "force_axiale_N", default=0.0)),
        force_cisaillement_N=_safe_float(_get_nested(efforts, "force_cisaillement_N", default=0.0)),
        moment_flexion_Nm=_safe_float(_get_nested(efforts, "moment_flexion_Nm", default=0.0)),
        couple_torsion_Nm=_safe_float(_get_nested(efforts, "couple_torsion_Nm", default=0.0)),

        sigma_axiale_pa=_safe_float(_get_nested(contraintes, "sigma_axiale_pa", default=0.0)),
        sigma_flexion_pa=_safe_float(_get_nested(contraintes, "sigma_flexion_pa", default=0.0)),
        tau_transverse_pa=_safe_float(_get_nested(contraintes, "tau_transverse_pa", default=0.0)),
        tau_torsion_pa=_safe_float(_get_nested(contraintes, "tau_torsion_pa", default=0.0)),
        sigma_von_mises_pa=_safe_float(_get_nested(contraintes, "sigma_von_mises_pa", default=0.0)),
        sigma_allow_pa=_safe_float(_get_nested(contraintes, "sigma_allow_pa", default=0.0)),
        marge_sigma_vm=_safe_float(_get_nested(contraintes, "marge_sigma_vm", default=0.0)),

        charge_critique_euler_N=_safe_float(_get_nested(flambage, "charge_critique_euler_N", default=0.0)),
        marge_flambage=_safe_float(_get_nested(flambage, "marge_flambage", default=0.0)),
        longueur_libre_mm=_mm(_get_nested(flambage, "longueur_libre_m", default=0.0)),
        K_flambage=_safe_float(_get_nested(flambage, "K_flambage", default=0.0)),

        masse_kg=_safe_float(_get_nested(masse, "masse_kg", default=0.0)),
        volume_total_m3=_safe_float(_get_nested(masse, "volume_total_m3", default=0.0)),
        inertie_I_m4=_safe_float(_get_nested(_get_nested(inerties, "fut_central", default={}), "I_m4", default=0.0)),
        inertie_J_m4=_safe_float(_get_nested(_get_nested(inerties, "fut_central", default={}), "J_m4", default=0.0)),

        rpm=_safe_float(_get_nested(cin, "rpm", default=0.0)),
        omega_rad_s=_safe_float(_get_nested(cin, "omega_rad_s", default=0.0)),

        note_dimensionnement=str(_get_nested(dim_evide, "mode", default="") or ""),
        evidement=bool(_get_nested(fut_cao, "evidement", default=False)),

        rapport_complet=rapport,
    )


# ============================================================
# VUE DE CÔTÉ
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisArbrePiston):
    Lg = d.longueur_teton_g_mm
    Lm = d.longueur_fut_mm
    Ld = d.longueur_teton_d_mm

    if d.longueur_totale_mm > 0:
        Ltot = d.longueur_totale_mm
    else:
        Ltot = Lg + Lm + Ld

    x0 = 0.0
    x1 = Lg
    x2 = Lg + Lm
    x3 = Ltot

    Dg = d.diametre_teton_g_mm
    Dm = d.diametre_fut_ext_mm
    Di = d.diametre_fut_int_mm
    Dd = d.diametre_teton_d_mm

    yg = Dg / 2.0 if Dg > 0 else 0.0
    ym = Dm / 2.0 if Dm > 0 else 0.0
    ymi = Di / 2.0 if Di > 0 else 0.0
    yd = Dd / 2.0 if Dd > 0 else 0.0

    ymax = max(yg, ym, yd, 1.0)

    # Hachures matière
    if Lg > 0 and Dg > 0:
        _add_hatched_rect(ax, x0, -yg, Lg, Dg)
    if Lm > 0 and Dm > 0:
        if d.evidement and Di > 0:
            _add_hatched_rect(ax, x1, ymi, Lm, ym - ymi)
            _add_hatched_rect(ax, x1, -ym, Lm, ym - ymi)
        else:
            _add_hatched_rect(ax, x1, -ym, Lm, Dm)
    if Ld > 0 and Dd > 0:
        _add_hatched_rect(ax, x2, -yd, Ld, Dd)

    # Contours
    if Lg > 0 and Dg > 0:
        ax.add_patch(Rectangle((x0, -yg), Lg, Dg, fill=False, linewidth=1.4))
    if Lm > 0 and Dm > 0:
        ax.add_patch(Rectangle((x1, -ym), Lm, Dm, fill=False, linewidth=1.6))
        if d.evidement and Di > 0:
            ax.add_patch(Rectangle((x1, -ymi), Lm, Di, fill=False, linewidth=1.1))
    if Ld > 0 and Dd > 0:
        ax.add_patch(Rectangle((x2, -yd), Ld, Dd, fill=False, linewidth=1.4))

    # Épaulements
    if Lg > 0 and Lm > 0:
        ax.add_line(Line2D([x1, x1], [-ym, -yg], color="black", linewidth=1.2))
        ax.add_line(Line2D([x1, x1], [yg, ym], color="black", linewidth=1.2))
    if Lm > 0 and Ld > 0:
        ax.add_line(Line2D([x2, x2], [-ym, -yd], color="black", linewidth=1.2))
        ax.add_line(Line2D([x2, x2], [yd, ym], color="black", linewidth=1.2))

    # Axe
    ax.axhline(0, **_linestyle_axe())

    # Taraudages schématiques
    if d.profondeur_taraudage_g_mm > 0 and Dg > 0 and Lg > 0:
        ltg = min(d.profondeur_taraudage_g_mm, Lg)
        ax.add_patch(Rectangle((x0, -0.28 * Dg), ltg, 0.56 * Dg, fill=False, linewidth=1.0, linestyle=(0, (4, 4))))
        _annotate_leader(ax, x0 - 65.0, yg + 18.0, x0 + ltg * 0.5, 0.0, "Taraudage gauche")
    if d.profondeur_taraudage_d_mm > 0 and Dd > 0 and Ld > 0:
        ltd = min(d.profondeur_taraudage_d_mm, Ld)
        ax.add_patch(Rectangle((x3 - ltd, -0.28 * Dd), ltd, 0.56 * Dd, fill=False, linewidth=1.0, linestyle=(0, (4, 4))))
        _annotate_leader(ax, x3 + 10.0, yd + 18.0, x3 - ltd * 0.5, 0.0, "Taraudage droit")

    # Chanfreins schématiques
    if d.chanfrein_g_mm > 0 and Dg > 0:
        ax.add_line(Line2D([x0, x0 + d.chanfrein_g_mm], [yg, yg - d.chanfrein_g_mm], color="black", linewidth=1.0))
        ax.add_line(Line2D([x0, x0 + d.chanfrein_g_mm], [-yg, -yg + d.chanfrein_g_mm], color="black", linewidth=1.0))
    if d.chanfrein_d_mm > 0 and Dd > 0:
        ax.add_line(Line2D([x3, x3 - d.chanfrein_d_mm], [yd, yd - d.chanfrein_d_mm], color="black", linewidth=1.0))
        ax.add_line(Line2D([x3, x3 - d.chanfrein_d_mm], [-yd, -yd + d.chanfrein_d_mm], color="black", linewidth=1.0))

    # Annotations
    if Lg > 0:
        _annotate_leader(ax, x0 + 5.0, yg + 18.0, x0 + 0.45 * Lg, yg, "Téton gauche")
    if Lm > 0:
        _annotate_leader(ax, x1 + 5.0, ym + 18.0, x1 + 0.45 * Lm, ym, "Fût central")
    if Ld > 0:
        _annotate_leader(ax, x2 + 5.0, yd + 18.0, x2 + 0.45 * Ld, yd, "Téton droit")
    if d.evidement and Lm > 0 and Di > 0:
        _annotate_leader(ax, x1 + 0.15 * Lm, -ymi - 18.0, x1 + 0.35 * Lm, 0.0, "Évidement axial")

    # Cotes horizontales
    ydim1 = ymax + 14.0
    ydim2 = ymax + 28.0
    ydim3 = ymax + 42.0
    ydim4 = ymax + 56.0

    if Lg > 0:
        _add_dimension_h(ax, x0, x1, 0.0, ydim1, f"L téton G = {_fmt_mm(Lg)}")
    if Lm > 0:
        _add_dimension_h(ax, x1, x2, 0.0, ydim2, f"L fût = {_fmt_mm(Lm)}")
    if Ld > 0:
        _add_dimension_h(ax, x2, x3, 0.0, ydim3, f"L téton D = {_fmt_mm(Ld)}")
    _add_dimension_h(ax, x0, x3, 0.0, ydim4, f"L totale = {_fmt_mm(Ltot)}")

    # Cotes verticales
    xdim1 = x3 + 18.0
    xdim2 = x3 + 36.0
    xdim3 = x3 + 54.0
    xdim4 = x3 + 72.0

    if Dg > 0:
        _add_dimension_v(ax, 0.0, xdim1, -yg, yg, f"Ø G = {_fmt_mm(Dg)}")
    if Dm > 0:
        _add_dimension_v(ax, 0.0, xdim2, -ym, ym, f"Ø fût = {_fmt_mm(Dm)}")
    if d.evidement and Di > 0:
        _add_dimension_v(ax, 0.0, xdim3, -ymi, ymi, f"Ø int = {_fmt_mm(Di)}")
    if Dd > 0:
        _add_dimension_v(ax, 0.0, xdim4, -yd, yd, f"Ø D = {_fmt_mm(Dd)}")

    # Bloc infos local
    infos = []
    if d.filetage_g:
        infos.append(f"Filetage gauche     : {d.filetage_g}")
    if d.filetage_d:
        infos.append(f"Filetage droit      : {d.filetage_d}")
    if d.profondeur_taraudage_g_mm > 0:
        infos.append(f"Prof. taraudage G   : {_fmt_mm(d.profondeur_taraudage_g_mm)}")
    if d.profondeur_taraudage_d_mm > 0:
        infos.append(f"Prof. taraudage D   : {_fmt_mm(d.profondeur_taraudage_d_mm)}")
    if d.rayon_conge_g_mm > 0:
        infos.append(f"Rayon congé G       : {_fmt_mm(d.rayon_conge_g_mm)}")
    if d.rayon_conge_d_mm > 0:
        infos.append(f"Rayon congé D       : {_fmt_mm(d.rayon_conge_d_mm)}")
    if d.chanfrein_g_mm > 0:
        infos.append(f"Chanfrein G         : {_fmt_mm(d.chanfrein_g_mm)}")
    if d.chanfrein_d_mm > 0:
        infos.append(f"Chanfrein D         : {_fmt_mm(d.chanfrein_d_mm)}")
    if d.note_dimensionnement:
        infos.append(f"Mode dim.           : {d.note_dimensionnement}")

    if infos:
        ax.text(
            x0,
            -(ymax + 36.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.6,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    ax.set_title("Vue de côté détaillée")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-90.0, x3 + 95.0)
    ax.set_ylim(-(ymax + 70.0), ymax + 70.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUES DE FACE
# ============================================================

def _tracer_section(ax, d_ext_mm: float, d_int_mm: float, titre: str, notes: List[str]):
    R_ext = d_ext_mm / 2.0 if d_ext_mm > 0 else 0.0
    R_int = d_int_mm / 2.0 if d_int_mm > 0 else 0.0

    if R_ext > 0:
        ax.add_patch(Circle((0, 0), R_ext, fill=False, linewidth=1.5, edgecolor="black"))
    if R_int > 0:
        ax.add_patch(Circle((0, 0), R_int, fill=False, linewidth=1.1, edgecolor="black"))

    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    txt = [f"Ø ext = {_fmt_mm(d_ext_mm)}"] if d_ext_mm > 0 else []
    if d_int_mm > 0:
        txt.append(f"Ø int = {_fmt_mm(d_int_mm)}")
    txt.extend(notes)

    lim = max(R_ext, R_int, 1.0) + 24.0
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
# CARTOUCHE
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisArbrePiston):
    lines = [
        f"Longueur totale         : {_fmt_mm(d.longueur_totale_mm) if d.longueur_totale_mm > 0 else 'N/A'}",
        f"Longueur fut            : {_fmt_mm(d.longueur_fut_mm) if d.longueur_fut_mm > 0 else 'N/A'}",
        f"Longueur téton G        : {_fmt_mm(d.longueur_teton_g_mm) if d.longueur_teton_g_mm > 0 else 'N/A'}",
        f"Longueur téton D        : {_fmt_mm(d.longueur_teton_d_mm) if d.longueur_teton_d_mm > 0 else 'N/A'}",
        f"Ø fut ext               : {_fmt_mm(d.diametre_fut_ext_mm) if d.diametre_fut_ext_mm > 0 else 'N/A'}",
        f"Ø fut int               : {_fmt_mm(d.diametre_fut_int_mm) if d.diametre_fut_int_mm > 0 else 'N/A'}",
        f"Ø téton G               : {_fmt_mm(d.diametre_teton_g_mm) if d.diametre_teton_g_mm > 0 else 'N/A'}",
        f"Ø téton D               : {_fmt_mm(d.diametre_teton_d_mm) if d.diametre_teton_d_mm > 0 else 'N/A'}",
        f"Filetage G              : {d.filetage_g or 'N/A'}",
        f"Filetage D              : {d.filetage_d or 'N/A'}",
        f"Prof taraudage G        : {_fmt_mm(d.profondeur_taraudage_g_mm) if d.profondeur_taraudage_g_mm > 0 else 'N/A'}",
        f"Prof taraudage D        : {_fmt_mm(d.profondeur_taraudage_d_mm) if d.profondeur_taraudage_d_mm > 0 else 'N/A'}",
        f"Force axiale            : {_fmt_n(d.force_axiale_N) if d.force_axiale_N != 0 else 'N/A'}",
        f"Force cisaillement      : {_fmt_n(d.force_cisaillement_N) if d.force_cisaillement_N != 0 else 'N/A'}",
        f"Moment flexion          : {_fmt_nm(d.moment_flexion_Nm) if d.moment_flexion_Nm != 0 else 'N/A'}",
        f"Couple torsion          : {_fmt_nm(d.couple_torsion_Nm) if d.couple_torsion_Nm != 0 else 'N/A'}",
        f"σ axiale                : {_fmt_pa(d.sigma_axiale_pa) if d.sigma_axiale_pa > 0 else 'N/A'}",
        f"σ flexion               : {_fmt_pa(d.sigma_flexion_pa) if d.sigma_flexion_pa > 0 else 'N/A'}",
        f"τ transverse            : {_fmt_pa(d.tau_transverse_pa) if d.tau_transverse_pa > 0 else 'N/A'}",
        f"τ torsion               : {_fmt_pa(d.tau_torsion_pa) if d.tau_torsion_pa > 0 else 'N/A'}",
        f"σ Von Mises             : {_fmt_pa(d.sigma_von_mises_pa) if d.sigma_von_mises_pa > 0 else 'N/A'}",
        f"σ admissible            : {_fmt_pa(d.sigma_allow_pa) if d.sigma_allow_pa > 0 else 'N/A'}",
        f"Marge σ_VM              : {f'{d.marge_sigma_vm:.3f}' if d.marge_sigma_vm > 0 else 'N/A'}",
        f"Pcrit Euler             : {_fmt_n(d.charge_critique_euler_N) if d.charge_critique_euler_N > 0 else 'N/A'}",
        f"Marge flambage          : {f'{d.marge_flambage:.3f}' if d.marge_flambage > 0 else 'N/A'}",
        f"Longueur libre          : {_fmt_mm(d.longueur_libre_mm) if d.longueur_libre_mm > 0 else 'N/A'}",
        f"K flambage              : {f'{d.K_flambage:.3f}' if d.K_flambage > 0 else 'N/A'}",
        f"Masse                   : {f'{d.masse_kg:.4f} kg' if d.masse_kg > 0 else 'N/A'}",
        f"Volume total            : {_fmt_m3(d.volume_total_m3) if d.volume_total_m3 > 0 else 'N/A'}",
        f"Inertie I               : {_fmt_m4(d.inertie_I_m4) if d.inertie_I_m4 > 0 else 'N/A'}",
        f"Inertie J               : {_fmt_m4(d.inertie_J_m4) if d.inertie_J_m4 > 0 else 'N/A'}",
        f"rpm                     : {f'{d.rpm:.2f}' if d.rpm > 0 else 'N/A'}",
        f"omega                   : {f'{d.omega_rad_s:.4f} rad/s' if d.omega_rad_s > 0 else 'N/A'}",
        f"Evidement               : {'oui' if d.evidement else 'non'}",
        f"Mode dimensionnement    : {d.note_dimensionnement or 'N/A'}",
    ]

    fig.text(
        0.012,
        0.015,
        "DONNÉES EXTRAITES DE ArbrePiston.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=8.2,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_arbre_piston_2d(
    arbre: ArbrePiston,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Arbre de piston",
):
    d = extraire_donnees_croquis(arbre)

    if d.longueur_totale_mm <= 0 and (d.longueur_teton_g_mm + d.longueur_fut_mm + d.longueur_teton_d_mm) <= 0:
        raise ValueError("Impossible de tracer : les longueurs principales sont absentes.")
    if d.diametre_fut_ext_mm <= 0 and d.diametre_teton_g_mm <= 0 and d.diametre_teton_d_mm <= 0:
        raise ValueError("Impossible de tracer : les diamètres principaux sont absents.")

    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(2, 3, height_ratios=[2.2, 1.25], width_ratios=[2.0, 1.0, 1.0])

    ax_side = fig.add_subplot(gs[0, :])
    ax_face_g = fig.add_subplot(gs[1, 0])
    ax_face_mid = fig.add_subplot(gs[1, 1])
    ax_face_d = fig.add_subplot(gs[1, 2])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_cote(ax_side, d)

    _tracer_section(
        ax_face_g,
        d_ext_mm=d.diametre_teton_g_mm,
        d_int_mm=0.0,
        titre="Vue de face - Téton gauche",
        notes=[f"Filetage : {d.filetage_g}" if d.filetage_g else "Sans filetage explicite"],
    )

    _tracer_section(
        ax_face_mid,
        d_ext_mm=d.diametre_fut_ext_mm,
        d_int_mm=d.diametre_fut_int_mm if d.evidement else 0.0,
        titre="Vue de face - Fût central",
        notes=["Section évidée" if d.evidement and d.diametre_fut_int_mm > 0 else "Section pleine"],
    )

    _tracer_section(
        ax_face_d,
        d_ext_mm=d.diametre_teton_d_mm,
        d_int_mm=0.0,
        titre="Vue de face - Téton droit",
        notes=[f"Filetage : {d.filetage_d}" if d.filetage_d else "Sans filetage explicite"],
    )

    _ajouter_cartouche_technique(fig, d)

    plt.tight_layout(rect=[0.0, 0.11, 1.0, 0.965])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, {
        "vue_cote": ax_side,
        "vue_face_gauche": ax_face_g,
        "vue_face_fut": ax_face_mid,
        "vue_face_droite": ax_face_d,
    }, d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

if __name__ == "__main__":
    arbre = ArbrePiston(
        densite_kg_m3=7800.0,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        facteur_securite=2.0,

        longueur_fut_central_m=0.040,
        profondeur_taraudage_gauche_m=0.012,
        profondeur_taraudage_droit_m=0.012,

        force_axiale_N=15000.0,
        force_cisaillement_N=2000.0,
        bras_levier_charge_m=0.010,

        longueur_libre_m=0.060,
        K_flambage=1.0,

        effort_axial_sur_taraudage_gauche_N=8000.0,
        effort_axial_sur_taraudage_droit_N=8000.0,
        resistance_cisaillement_matiere_taraudee_pa=250e6,

        filetage_gauche="M8",
        filetage_droit="M8",
        ratio_evidement_k=0.5,
    )

    tracer_croquis_arbre_piston_2d(
        arbre,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Arbre de piston calculé",
    )