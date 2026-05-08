# frontend/pieces/sketches_2d/coussinet_arbre_piston.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle

from backend.components.moteur_thermique.pieces.coussinet_arbre_piston import CoussinetArbrePiston


# ============================================================
# OUTILS
# ============================================================

def _mm(x_m: Optional[float]) -> float:
    if x_m is None:
        return 0.0
    return float(x_m) * 1000.0


def _um(x_m: Optional[float]) -> float:
    if x_m is None:
        return 0.0
    return float(x_m) * 1_000_000.0


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


def _fmt_um(v: float) -> str:
    return f"{v:.2f} µm"


def _fmt_n(v: float) -> str:
    return f"{v:.2f} N"


def _fmt_pa(v: float) -> str:
    return f"{v:.3e} Pa"


def _fmt_m2(v: float) -> str:
    return f"{v:.6e} m²"


def _fmt_m3(v: float) -> str:
    return f"{v:.6e} m³"


def _fmt_w(v: float) -> str:
    return f"{v:.3f} W"


def _fmt_nm(v: float) -> str:
    return f"{v:.6f} N·m"


def _fmt_kg(v: float) -> str:
    return f"{v:.6f} kg"


def _fmt_kw(v: float) -> str:
    return f"{v:.6e} K/W"


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
class DonneesCroquisCoussinet:
    diametre_interieur_mm: float = 0.0
    diametre_exterieur_mm: float = 0.0
    longueur_mm: float = 0.0
    epaisseur_radiale_mm: float = 0.0
    jeu_radial_um: float = 0.0
    chanfrein_mm: float = 0.0

    rayon_interieur_mm: float = 0.0
    rayon_exterieur_mm: float = 0.0

    diametre_candidates_mm: Optional[list[float]] = None

    charge_radiale_N: float = 0.0
    charge_axiale_N: float = 0.0

    rpm: float = 0.0
    omega_rad_s: float = 0.0
    vitesse_glissement_m_s: float = 0.0

    surface_projetee_m2: float = 0.0
    pression_projetee_pa: float = 0.0
    pression_admissible_pa: float = 0.0
    pression_admissible_effective_pa: float = 0.0
    marge_pression: float = 0.0

    pv_w_m2: float = 0.0
    pv_admissible_w_m2: float = 0.0
    pv_admissible_effective_w_m2: float = 0.0
    marge_pv: float = 0.0

    mu: float = 0.0
    puissance_frottement_w: float = 0.0
    couple_frottement_nm: float = 0.0

    sommerfeld: float = 0.0
    viscosite_pa_s: float = 0.0
    L_sur_d: float = 0.0

    R_conduction_K_W: float = 0.0
    k_coussinet_w_m_k: float = 0.0

    volume_m3: float = 0.0
    masse_kg: float = 0.0
    densite_kg_m3: float = 0.0

    mode_lubrification: str = ""
    excentricite_um: float = 0.0

    tolerance_diametre_interieur_um: float = 0.0
    tolerance_diametre_exterieur_um: float = 0.0
    tolerance_longueur_um: float = 0.0
    rugosite_interieure_ra_um: float = 0.0
    rugosite_exterieure_ra_um: float = 0.0

    L_min_solutions_mm: Optional[list[dict[str, Any]]] = None

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(coussinet: CoussinetArbrePiston) -> DonneesCroquisCoussinet:
    rapport = coussinet.analyser(strict=False)

    geo = rapport.get("geometrie", {})
    cin = rapport.get("cinematique", {})
    eff = rapport.get("efforts", {})
    press = rapport.get("pressions", {})
    pv = rapport.get("pv", {})
    frott = rapport.get("frottement", {})
    hydro = rapport.get("hydrodynamique", {})
    thermique = rapport.get("thermique", {})
    masse = rapport.get("masse", {})
    cao = rapport.get("cao", {})
    tribo = rapport.get("tribologie", {})
    dim = rapport.get("dimensionnement", {})

    diam_int = _get_nested(cao, "diametre_interieur_nominal_m", default=_get_nested(geo, "diametre_portee_m", default=0.0))
    diam_ext = _get_nested(cao, "diametre_exterieur_nominal_m", default=_get_nested(geo, "diametre_exterieur_m", default=0.0))
    longueur = _get_nested(cao, "longueur_nominale_m", default=_get_nested(geo, "longueur_coussinet_m", default=0.0))
    e = _get_nested(cao, "epaisseur_radiale_m", default=_get_nested(geo, "epaisseur_coussinet_m", default=0.0))
    jeu = _get_nested(cao, "jeu_radial_m", default=_get_nested(geo, "jeu_radial_m", default=0.0))

    coupe = _get_nested(cao, "coupe_radiale", default={}) or {}

    sols = dim.get("solutions") if isinstance(dim.get("solutions"), list) else []

    sols_mm = []
    for s in sols:
        if not isinstance(s, dict):
            continue
        ss = dict(s)
        if _safe_float(ss.get("d_m"), 0.0) > 0:
            ss["d_mm"] = _mm(ss["d_m"])
        if _safe_float(ss.get("L_min_m"), 0.0) > 0:
            ss["L_min_mm"] = _mm(ss["L_min_m"])
        cts = ss.get("contraintes")
        if isinstance(cts, dict):
            if _safe_float(cts.get("L_min_pression_m"), 0.0) > 0:
                cts["L_min_pression_mm"] = _mm(cts["L_min_pression_m"])
            if _safe_float(cts.get("L_min_PV_m"), 0.0) > 0:
                cts["L_min_PV_mm"] = _mm(cts["L_min_PV_m"])
        sols_mm.append(ss)

    return DonneesCroquisCoussinet(
        diametre_interieur_mm=_mm(diam_int),
        diametre_exterieur_mm=_mm(diam_ext),
        longueur_mm=_mm(longueur),
        epaisseur_radiale_mm=_mm(e),
        jeu_radial_um=_um(jeu),
        chanfrein_mm=_mm(_get_nested(cao, "chanfrein_entrees_m", default=0.0)),

        rayon_interieur_mm=_mm(_get_nested(coupe, "rayon_interieur_m", default=(0.5 * diam_int if diam_int else 0.0))),
        rayon_exterieur_mm=_mm(_get_nested(coupe, "rayon_exterieur_m", default=(0.5 * diam_ext if diam_ext else 0.0))),

        diametre_candidates_mm=[_mm(v) for v in (_get_nested(geo, "diametre_portee_candidates_m", default=[]) or [])],

        charge_radiale_N=_safe_float(_get_nested(eff, "charge_radiale_N", default=0.0)),
        charge_axiale_N=_safe_float(_get_nested(eff, "charge_axiale_N", default=0.0)),

        rpm=_safe_float(_get_nested(cin, "rpm", default=0.0)),
        omega_rad_s=_safe_float(_get_nested(cin, "omega_rad_s", default=0.0)),
        vitesse_glissement_m_s=_safe_float(_get_nested(cin, "vitesse_glissement_m_s", default=0.0)),

        surface_projetee_m2=_safe_float(_get_nested(press, "surface_projetee_m2", default=0.0)),
        pression_projetee_pa=_safe_float(_get_nested(press, "pression_projetee_pa", default=0.0)),
        pression_admissible_pa=_safe_float(_get_nested(press, "pression_admissible_pa", default=0.0)),
        pression_admissible_effective_pa=_safe_float(_get_nested(press, "pression_admissible_effective_pa", default=0.0)),
        marge_pression=_safe_float(_get_nested(press, "marge_pression", default=0.0)),

        pv_w_m2=_safe_float(_get_nested(pv, "pv_W_m2", default=0.0)),
        pv_admissible_w_m2=_safe_float(_get_nested(pv, "pv_admissible_W_m2", default=0.0)),
        pv_admissible_effective_w_m2=_safe_float(_get_nested(pv, "pv_admissible_effective_W_m2", default=0.0)),
        marge_pv=_safe_float(_get_nested(pv, "marge_pv", default=0.0)),

        mu=_safe_float(_get_nested(frott, "mu", default=0.0)),
        puissance_frottement_w=_safe_float(_get_nested(frott, "puissance_frottement_W", default=0.0)),
        couple_frottement_nm=_safe_float(_get_nested(frott, "couple_frottement_Nm", default=0.0)),

        sommerfeld=_safe_float(_get_nested(hydro, "sommerfeld_S", default=0.0)),
        viscosite_pa_s=_safe_float(_get_nested(hydro, "eta_Pa_s", default=_get_nested(tribo, "viscosite_Pa_s", default=0.0))),
        L_sur_d=_safe_float(_get_nested(hydro, "L_sur_d", default=0.0)),

        R_conduction_K_W=_safe_float(_get_nested(thermique, "R_conduction_K_W", default=0.0)),
        k_coussinet_w_m_k=_safe_float(_get_nested(thermique, "k_coussinet_W_m_K", default=0.0)),

        volume_m3=_safe_float(_get_nested(masse, "volume_m3", default=0.0)),
        masse_kg=_safe_float(_get_nested(masse, "masse_kg", default=0.0)),
        densite_kg_m3=_safe_float(_get_nested(masse, "densite_kg_m3", default=0.0)),

        mode_lubrification=str(_get_nested(tribo, "mode_lubrification", default="") or ""),
        excentricite_um=_um(_get_nested(geo, "excentricite_m", default=0.0)),

        tolerance_diametre_interieur_um=_um(_get_nested(cao, "tolerance_diametre_interieur_m", default=0.0)),
        tolerance_diametre_exterieur_um=_um(_get_nested(cao, "tolerance_diametre_exterieur_m", default=0.0)),
        tolerance_longueur_um=_um(_get_nested(cao, "tolerance_longueur_m", default=0.0)),
        rugosite_interieure_ra_um=_safe_float(_get_nested(cao, "rugosite_interieure_ra_um", default=0.0)),
        rugosite_exterieure_ra_um=_safe_float(_get_nested(cao, "rugosite_exterieure_ra_um", default=0.0)),

        L_min_solutions_mm=sols_mm,
        rapport_complet=rapport,
    )


# ============================================================
# VUE DE CÔTÉ EN COUPE LONGITUDINALE
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisCoussinet):
    L = d.longueur_mm
    Di = d.diametre_interieur_mm
    De = d.diametre_exterieur_mm

    if L <= 0 or Di <= 0:
        ax.text(0.5, 0.5, "Longueur ou diamètre intérieur indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de côté")
        ax.set_axis_off()
        return

    if De <= 0 and d.epaisseur_radiale_mm > 0:
        De = Di + 2.0 * d.epaisseur_radiale_mm

    yi = Di / 2.0
    ye = De / 2.0 if De > 0 else yi

    x0 = 0.0
    x1 = L

    # Matière coussinet en coupe
    if De > 0:
        _add_hatched_rect(ax, x0, -ye, L, 2.0 * ye)
        ax.add_patch(Rectangle((x0, -ye), L, 2.0 * ye, fill=False, linewidth=1.5))
        ax.add_patch(Rectangle((x0, -yi), L, 2.0 * yi, fill=True, facecolor="white", edgecolor="black", linewidth=1.1))
    else:
        ax.add_patch(Rectangle((x0, -yi), L, 2.0 * yi, fill=False, linewidth=1.4))

    # Chanfreins schématiques si disponibles
    if d.chanfrein_mm > 0 and De > 0:
        ch = min(d.chanfrein_mm, 0.35 * (ye - yi) if ye > yi else d.chanfrein_mm)
        # entrée gauche haut / bas
        ax.add_line(Line2D([x0, x0 + ch], [yi + ch, yi], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x0, x0 + ch], [-(yi + ch), -yi], linewidth=1.0, color="black"))
        # entrée droite haut / bas
        ax.add_line(Line2D([x1 - ch, x1], [yi, yi + ch], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x1 - ch, x1], [-yi, -(yi + ch)], linewidth=1.0, color="black"))

    # Axe
    ax.axhline(0, **_linestyle_axe())

    # Cotes
    ydim1 = ye + 14.0
    ydim2 = ye + 30.0

    _add_dimension_h(ax, x0, x1, 0.0, ydim1, f"L = {_fmt_mm(L)}")

    xdim1 = x1 + 18.0
    xdim2 = x1 + 36.0
    _add_dimension_v(ax, 0.0, xdim1, -yi, yi, f"Ø int = {_fmt_mm(Di)}")
    if De > 0:
        _add_dimension_v(ax, 0.0, xdim2, -ye, ye, f"Ø ext = {_fmt_mm(De)}")

    # Épaisseur
    if d.epaisseur_radiale_mm > 0 and De > 0:
        _annotate_leader(ax, x1 + 55.0, yi + 10.0, 0.65 * L, 0.5 * (yi + ye), f"e = {_fmt_mm(d.epaisseur_radiale_mm)}")

    # Infos locales
    infos = []
    if d.jeu_radial_um > 0:
        infos.append(f"Jeu radial           : {_fmt_um(d.jeu_radial_um)}")
    if d.chanfrein_mm > 0:
        infos.append(f"Chanfrein entrée     : {_fmt_mm(d.chanfrein_mm)}")
    if d.mode_lubrification:
        infos.append(f"Lubrification        : {d.mode_lubrification}")
    if d.rugosite_interieure_ra_um > 0:
        infos.append(f"Ra intérieur         : {d.rugosite_interieure_ra_um:.2f} µm")
    if d.rugosite_exterieure_ra_um > 0:
        infos.append(f"Ra extérieur         : {d.rugosite_exterieure_ra_um:.2f} µm")

    if infos:
        ax.text(
            x0,
            -(ye + 34.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.5,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    ax.set_title("Vue de côté - Coupe longitudinale")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-35.0, x1 + 90.0)
    ax.set_ylim(-(ye + 70.0), ye + 70.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE DE FACE EN COUPE RADIALE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisCoussinet):
    Ri = d.rayon_interieur_mm if d.rayon_interieur_mm > 0 else d.diametre_interieur_mm / 2.0
    Ro = d.rayon_exterieur_mm if d.rayon_exterieur_mm > 0 else d.diametre_exterieur_mm / 2.0

    if Ri <= 0:
        ax.text(0.5, 0.5, "Diamètre intérieur indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de face")
        ax.set_axis_off()
        return

    if Ro <= 0 and d.epaisseur_radiale_mm > 0:
        Ro = Ri + d.epaisseur_radiale_mm

    if Ro > 0:
        ax.add_patch(Circle((0, 0), Ro, fill=False, linewidth=1.5))
        ax.add_patch(Circle((0, 0), Ri, fill=False, linewidth=1.1))
    else:
        ax.add_patch(Circle((0, 0), Ri, fill=False, linewidth=1.4))

    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    txt = [f"Ø int = {_fmt_mm(2.0 * Ri)}"]
    if Ro > 0:
        txt.append(f"Ø ext = {_fmt_mm(2.0 * Ro)}")
    if d.epaisseur_radiale_mm > 0:
        txt.append(f"e = {_fmt_mm(d.epaisseur_radiale_mm)}")
    if d.jeu_radial_um > 0:
        txt.append(f"c = {_fmt_um(d.jeu_radial_um)}")

    lim = max(Ro, Ri, 1.0) + 22.0
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

    ax.set_title("Vue de face - Coupe radiale")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# DÉTAIL DE JEU RADIAL
# ============================================================

def _tracer_detail_jeu(ax, d: DonneesCroquisCoussinet):
    if d.diametre_interieur_mm <= 0 or d.epaisseur_radiale_mm <= 0:
        ax.text(0.5, 0.5, "Détail de jeu non disponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Détail jeu radial")
        ax.set_axis_off()
        return

    Di = d.diametre_interieur_mm
    e = d.epaisseur_radiale_mm
    c_um = d.jeu_radial_um

    # Représentation agrandie locale
    x0 = 0.0
    y0 = 0.0

    H = max(14.0, e * 7.0)
    W = 80.0

    # Arbre fictif en bas / coussinet au-dessus
    # On reste schématique : on montre la lumière intérieure et l'épaisseur
    ax.add_patch(Rectangle((x0, y0), W, 10.0, fill=False, linewidth=1.2, linestyle=(0, (4, 4))))
    ax.text(x0 + 0.5 * W, y0 - 4.0, "Arbre / portée (schéma)", ha="center", va="top", fontsize=8)

    gap = max(2.0, c_um / 10.0 if c_um > 0 else 2.0)

    # Coussinet
    _add_hatched_rect(ax, x0, y0 + 10.0 + gap, W, H)
    ax.add_patch(Rectangle((x0, y0 + 10.0 + gap), W, H, fill=False, linewidth=1.3))

    # Surface intérieure
    ax.add_line(Line2D([x0, x0 + W], [y0 + 10.0 + gap, y0 + 10.0 + gap], linewidth=1.2, color="black"))
    # Surface extérieure
    ax.add_line(Line2D([x0, x0 + W], [y0 + 10.0 + gap + H, y0 + 10.0 + gap + H], linewidth=1.2, color="black"))

    # Cotes
    _add_dimension_v(ax, x0 + W + 4.0, x0 + W + 18.0, y0 + 10.0 + gap, y0 + 10.0 + gap + H, f"e ≈ {_fmt_mm(e)}")
    if c_um > 0:
        _add_dimension_v(ax, x0 - 4.0, x0 - 18.0, y0 + 10.0, y0 + 10.0 + gap, f"c = {_fmt_um(c_um)}")

    _annotate_leader(ax, x0 + W + 26.0, y0 + 10.0 + 0.25 * H, x0 + 0.75 * W, y0 + 10.0 + gap, "Surface intérieure")
    _annotate_leader(ax, x0 + W + 26.0, y0 + 10.0 + 0.8 * H, x0 + 0.75 * W, y0 + 10.0 + gap + H, "Surface extérieure")

    txt = [
        f"Ø portée = {_fmt_mm(Di)}",
    ]
    if d.excentricite_um > 0:
        txt.append(f"Excentricité = {_fmt_um(d.excentricite_um)}")

    ax.text(
        x0,
        y0 + 10.0 + gap + H + 12.0,
        "\n".join(txt),
        ha="left",
        va="bottom",
        fontsize=8.4,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Détail schématique du jeu radial")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-30.0, W + 70.0)
    ax.set_ylim(-18.0, y0 + 10.0 + gap + H + 30.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisCoussinet):
    lines = [
        f"Ø intérieur nominal          : {_fmt_mm(d.diametre_interieur_mm) if d.diametre_interieur_mm > 0 else 'N/A'}",
        f"Ø extérieur nominal          : {_fmt_mm(d.diametre_exterieur_mm) if d.diametre_exterieur_mm > 0 else 'N/A'}",
        f"Longueur nominale            : {_fmt_mm(d.longueur_mm) if d.longueur_mm > 0 else 'N/A'}",
        f"Épaisseur radiale            : {_fmt_mm(d.epaisseur_radiale_mm) if d.epaisseur_radiale_mm > 0 else 'N/A'}",
        f"Jeu radial                   : {_fmt_um(d.jeu_radial_um) if d.jeu_radial_um > 0 else 'N/A'}",
        f"Chanfrein                    : {_fmt_mm(d.chanfrein_mm) if d.chanfrein_mm > 0 else 'N/A'}",
        f"Charge radiale               : {_fmt_n(d.charge_radiale_N) if d.charge_radiale_N >= 0 else 'N/A'}",
        f"Charge axiale                : {_fmt_n(d.charge_axiale_N) if d.charge_axiale_N != 0 else 'N/A'}",
        f"rpm                          : {f'{d.rpm:.2f}' if d.rpm > 0 else 'N/A'}",
        f"omega                        : {f'{d.omega_rad_s:.6f} rad/s' if d.omega_rad_s > 0 else 'N/A'}",
        f"Vitesse glissement           : {f'{d.vitesse_glissement_m_s:.6f} m/s' if d.vitesse_glissement_m_s > 0 else 'N/A'}",
        f"Surface projetée             : {_fmt_m2(d.surface_projetee_m2) if d.surface_projetee_m2 > 0 else 'N/A'}",
        f"Pression projetée            : {_fmt_pa(d.pression_projetee_pa) if d.pression_projetee_pa > 0 else 'N/A'}",
        f"Pression admissible          : {_fmt_pa(d.pression_admissible_pa) if d.pression_admissible_pa > 0 else 'N/A'}",
        f"Pression adm effective       : {_fmt_pa(d.pression_admissible_effective_pa) if d.pression_admissible_effective_pa > 0 else 'N/A'}",
        f"Marge pression               : {f'{d.marge_pression:.3f}' if d.marge_pression > 0 else 'N/A'}",
        f"PV                           : {_fmt_pa(d.pv_w_m2) if d.pv_w_m2 > 0 else 'N/A'}",
        f"PV admissible                : {_fmt_pa(d.pv_admissible_w_m2) if d.pv_admissible_w_m2 > 0 else 'N/A'}",
        f"PV adm effectif              : {_fmt_pa(d.pv_admissible_effective_w_m2) if d.pv_admissible_effective_w_m2 > 0 else 'N/A'}",
        f"Marge PV                     : {f'{d.marge_pv:.3f}' if d.marge_pv > 0 else 'N/A'}",
        f"Coefficient de frottement    : {f'{d.mu:.6f}' if d.mu >= 0 else 'N/A'}",
        f"Puissance de frottement      : {_fmt_w(d.puissance_frottement_w) if d.puissance_frottement_w > 0 else 'N/A'}",
        f"Couple de frottement         : {_fmt_nm(d.couple_frottement_nm) if d.couple_frottement_nm > 0 else 'N/A'}",
        f"Sommerfeld S                 : {f'{d.sommerfeld:.6e}' if d.sommerfeld > 0 else 'N/A'}",
        f"Viscosité                    : {f'{d.viscosite_pa_s:.6e} Pa·s' if d.viscosite_pa_s > 0 else 'N/A'}",
        f"L/d                          : {f'{d.L_sur_d:.6f}' if d.L_sur_d > 0 else 'N/A'}",
        f"R conduction                 : {_fmt_kw(d.R_conduction_K_W) if d.R_conduction_K_W > 0 else 'N/A'}",
        f"k coussinet                  : {f'{d.k_coussinet_w_m_k:.6f} W/m/K' if d.k_coussinet_w_m_k > 0 else 'N/A'}",
        f"Volume                       : {_fmt_m3(d.volume_m3) if d.volume_m3 > 0 else 'N/A'}",
        f"Masse                        : {_fmt_kg(d.masse_kg) if d.masse_kg > 0 else 'N/A'}",
        f"Densité                      : {f'{d.densite_kg_m3:.2f} kg/m³' if d.densite_kg_m3 > 0 else 'N/A'}",
        f"Lubrification                : {d.mode_lubrification or 'N/A'}",
        f"Excentricité                 : {_fmt_um(d.excentricite_um) if d.excentricite_um > 0 else 'N/A'}",
        f"Tol. Ø intérieur             : {_fmt_um(d.tolerance_diametre_interieur_um) if d.tolerance_diametre_interieur_um > 0 else 'N/A'}",
        f"Tol. Ø extérieur             : {_fmt_um(d.tolerance_diametre_exterieur_um) if d.tolerance_diametre_exterieur_um > 0 else 'N/A'}",
        f"Tol. longueur                : {_fmt_um(d.tolerance_longueur_um) if d.tolerance_longueur_um > 0 else 'N/A'}",
        f"Ra intérieur                 : {f'{d.rugosite_interieure_ra_um:.2f} µm' if d.rugosite_interieure_ra_um > 0 else 'N/A'}",
        f"Ra extérieur                 : {f'{d.rugosite_exterieure_ra_um:.2f} µm' if d.rugosite_exterieure_ra_um > 0 else 'N/A'}",
    ]

    if d.diametre_candidates_mm:
        lines.append("Diamètres candidats           : " + ", ".join(f"{v:.2f} mm" for v in d.diametre_candidates_mm))

    if d.L_min_solutions_mm:
        lines.append("Solutions L_min :")
        for i, s in enumerate(d.L_min_solutions_mm, start=1):
            dmm = _safe_float(s.get("d_mm"), 0.0)
            Lmm = _safe_float(s.get("L_min_mm"), 0.0)
            txt = f"  #{i} : d={dmm:.2f} mm, Lmin={Lmm:.2f} mm"
            cts = s.get("contraintes", {})
            if isinstance(cts, dict):
                lp = _safe_float(cts.get("L_min_pression_mm"), 0.0)
                lv = _safe_float(cts.get("L_min_PV_mm"), 0.0)
                if lp > 0:
                    txt += f", Lp={lp:.2f} mm"
                if lv > 0:
                    txt += f", LPV={lv:.2f} mm"
            lines.append(txt)

    fig.text(
        0.012,
        0.015,
        "DONNÉES EXTRAITES DE CoussinetArbrePiston.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=7.95,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_coussinet_arbre_piston_2d(
    coussinet: CoussinetArbrePiston,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Coussinet arbre-piston",
):
    d = extraire_donnees_croquis(coussinet)

    if d.diametre_interieur_mm <= 0 and not d.diametre_candidates_mm:
        raise ValueError("Impossible de tracer : diamètre intérieur absent.")

    fig = plt.figure(figsize=(19, 11))
    gs = fig.add_gridspec(2, 3, height_ratios=[2.15, 1.35], width_ratios=[1.6, 1.0, 1.05])

    ax_side = fig.add_subplot(gs[0, :])
    ax_front = fig.add_subplot(gs[1, 0])
    ax_gap = fig.add_subplot(gs[1, 1])
    ax_info = fig.add_subplot(gs[1, 2])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_cote(ax_side, d)
    _tracer_vue_face(ax_front, d)
    _tracer_detail_jeu(ax_gap, d)

    ax_info.axis("off")
    notes = [
        "Le croquis représente uniquement",
        "la géométrie réellement calculée",
        "ou explicitement fournie.",
        "",
        "Si plusieurs diamètres candidats existent,",
        "le fichier les liste sans en choisir un.",
        "",
        "Aucune norme tribologique cachée",
        "ni hypothèse géométrique arbitraire",
        "n’est ajoutée.",
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
        "vue_face": ax_front,
        "detail_jeu": ax_gap,
        "panneau_info": ax_info,
    }, d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

if __name__ == "__main__":
    c = CoussinetArbrePiston(
        diametre_portee_m=0.020,
        longueur_coussinet_m=0.020,
        epaisseur_coussinet_m=0.002,
        charge_radiale_N=2000.0,
        rpm=3000.0,
        coefficient_frottement=0.05,
        mode_lubrification="eau",
        temperature_lubrifiant_K=300.0,
        pression_lubrifiant_Pa=101325.0,
        jeu_radial_m=20e-6,
        materiau_coussinet="bronze_cusn12",
        pression_admissible_pa=30e6,
        pv_admissible_W_m2=1.0e9,
        facteur_securite=2.0,
    )

    tracer_croquis_coussinet_arbre_piston_2d(
        c,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Coussinet arbre-piston calculé",
    )