# frontend/pieces/sketches_2d/piston.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, Circle

from backend.pieces.piston import Piston


# ============================================================
# OUTILS GÉNÉRAUX
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


def _fmt_pa(v: float) -> str:
    return f"{v:.3e} Pa"


def _fmt_n(v: float) -> str:
    return f"{v:.2f} N"


def _fmt_w(v: float) -> str:
    return f"{v:.3f} W"


def _fmt_ms(v: float) -> str:
    return f"{v:.4f} m/s"


def _fmt_m2(v: float) -> str:
    return f"{v:.6e} m²"


def _fmt_m3(v: float) -> str:
    return f"{v:.6e} m³"


def _fmt_kg(v: float) -> str:
    return f"{v:.6f} kg"


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
class DonneesCroquisPiston:
    alesage_nominal_mm: float = 0.0
    course_mm: float = 0.0
    rpm: float = 0.0

    alesage_min_mm: float = 0.0
    alesage_max_mm: float = 0.0
    diametre_piston_min_mm: float = 0.0
    diametre_piston_max_mm: float = 0.0
    diametre_piston_cao_mm: float = 0.0

    hauteur_totale_mm: float = 0.0
    hauteur_totale_min_geo_mm: float = 0.0
    epaisseur_tete_mm: float = 0.0
    longueur_jupe_mm: float = 0.0

    jeu_diametral_min_um: float = 0.0
    jeu_diametral_max_um: float = 0.0
    jeu_radial_min_um: float = 0.0
    jeu_radial_max_um: float = 0.0
    jeu_radial_nominal_um: float = 0.0

    temperature_ref_k: float = 0.0
    temperature_fonctionnement_k: float = 0.0
    alpha_piston: float = 0.0
    alpha_cylindre: float = 0.0
    alesage_min_hot_mm: float = 0.0
    alesage_max_hot_mm: float = 0.0
    piston_min_hot_mm: float = 0.0
    piston_max_hot_mm: float = 0.0
    jeu_diam_min_hot_um: float = 0.0
    jeu_diam_max_hot_um: float = 0.0
    jeu_rad_min_hot_um: float = 0.0
    jeu_rad_max_hot_um: float = 0.0
    non_grippage_hot_ok: Optional[bool] = None

    nb_joints: int = 0
    section_joint_mm: float = 0.0
    squeeze: float = 0.0
    facteur_largeur_rainure: float = 0.0
    profondeur_rainure_mm: float = 0.0
    largeur_rainure_mm: float = 0.0
    diametre_fond_rainure_mm: float = 0.0
    rayon_fond_rainure_mm: float = 0.0
    diametre_montage_joint_mm: float = 0.0
    diametre_moyen_joint_monte_mm: float = 0.0
    hauteur_radiale_disponible_mm: float = 0.0
    entraxe_rainures_mm: float = 0.0
    positions_centres_rainures_mm: Optional[List[float]] = None
    rainures: Optional[List[Dict[str, Any]]] = None
    volume_gorge_unitaire_m3: float = 0.0
    volume_gorges_total_m3: float = 0.0
    squeeze_reconstruit: float = 0.0
    rainures_dans_hauteur: Optional[bool] = None

    module_elastomere_pa: float = 0.0
    pression_contact_estimee_pa: float = 0.0
    etancheite_contact_ok: Optional[bool] = None

    force_gaz_n: float = 0.0
    rayon_manivelle_mm: float = 0.0
    force_inertie_alternative_n: float = 0.0
    force_axiale_nette_n: float = 0.0

    mu_joint: float = 0.0
    bande_contact_mm: float = 0.0
    aire_contact_m2: float = 0.0
    force_normale_totale_n: float = 0.0
    vitesse_moyenne_ms: float = 0.0
    puissance_frottement_w: float = 0.0
    pv_pa_ms: float = 0.0
    pv_admissible_pa_ms: float = 0.0
    pv_ok: Optional[bool] = None

    distance_glissement_m: float = 0.0
    volume_use_m3: float = 0.0
    perte_epaisseur_um: float = 0.0

    debit_fuite_m3_s: float = 0.0
    debit_fuite_kg_s: float = 0.0
    mu_air_pa_s: float = 0.0
    densite_air_kg_m3: float = 0.0
    dP_fuite_pa: float = 0.0

    volume_plein_m3: float = 0.0
    volume_net_m3: float = 0.0
    masse_kg: float = 0.0
    inertie_rotation_axe_kg_m2: float = 0.0

    chanfrein_extremites_mm: float = 0.0
    rayon_conge_tete_jupe_mm: float = 0.0
    rugosite_exterieure_ra_um: float = 0.0
    rugosite_faces_ra_um: float = 0.0
    rugosite_fond_rainure_ra_um: float = 0.0
    tolerance_diametre_exterieur_um: float = 0.0
    tolerance_hauteur_um: float = 0.0
    tolerance_position_rainure_um: float = 0.0
    tolerance_largeur_rainure_um: float = 0.0
    tolerance_profondeur_rainure_um: float = 0.0

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(piston: Piston) -> DonneesCroquisPiston:
    rap = piston.analyser(strict=False)

    dim = rap.get("dimensions", {})
    jeux = rap.get("jeux", {})
    therm = rap.get("thermique", {})
    joints = rap.get("joints", {})
    cin = rap.get("cinematique", {})
    fr = rap.get("frottements", {})
    usure = rap.get("usure", {})
    fuites = rap.get("fuites", {})
    masses = rap.get("masses", {})
    matp = _get_nested(rap, "materiaux", "piston", default={}) or {}
    matc = _get_nested(rap, "materiaux", "cylindre", default={}) or {}
    cao = _get_nested(dim, "cao", default={}) or {}
    frj = _get_nested(fr, "joint", default={}) or {}
    usj = _get_nested(usure, "joint", default={}) or {}
    verj = _get_nested(joints, "verif", default={}) or {}

    positions = joints.get("positions_centres_depuis_face_tete_m") if isinstance(joints.get("positions_centres_depuis_face_tete_m"), list) else []
    positions_mm = [_mm(v) for v in positions]

    return DonneesCroquisPiston(
        alesage_nominal_mm=_mm(_get_nested(rap, "liaisons", "cylindre", "alesage_nominal_m", default=_get_nested(rap, "entrees", "alesage_nominal_m", default=0.0))),
        course_mm=_mm(_get_nested(rap, "liaisons", "cylindre", "course_m", default=_get_nested(rap, "entrees", "course_m", default=0.0))),
        rpm=_safe_float(_get_nested(rap, "entrees", "rpm", default=0.0)),

        alesage_min_mm=_mm(_get_nested(dim, "alesage_min_m", default=0.0)),
        alesage_max_mm=_mm(_get_nested(dim, "alesage_max_m", default=0.0)),
        diametre_piston_min_mm=_mm(_get_nested(dim, "diametre_piston_min_m", default=0.0)),
        diametre_piston_max_mm=_mm(_get_nested(dim, "diametre_piston_max_m", default=0.0)),
        diametre_piston_cao_mm=_mm(_get_nested(dim, "diametre_piston_cao_centre_m", default=_get_nested(cao, "diametre_exterieur_nominal_m", default=0.0))),

        hauteur_totale_mm=_mm(_get_nested(dim, "hauteur_totale_m", default=_get_nested(cao, "hauteur_totale_m", default=0.0))),
        hauteur_totale_min_geo_mm=_mm(_get_nested(dim, "hauteur_totale_min_geometrique_m", default=0.0)),
        epaisseur_tete_mm=_mm(
            _get_nested(dim, "epaisseur_tete_m", default=_get_nested(dim, "epaisseur_tete_min_m", default=_get_nested(cao, "epaisseur_tete_m", default=0.0)))
        ),
        longueur_jupe_mm=_mm(
            _get_nested(dim, "longueur_jupe_m", default=_get_nested(dim, "longueur_jupe_min_m", default=_get_nested(dim, "longueur_jupe_calculee_depuis_hauteur_m", default=_get_nested(cao, "longueur_jupe_m", default=0.0))))
        ),

        jeu_diametral_min_um=_um(_get_nested(jeux, "jeu_diametral_min_m", default=0.0)),
        jeu_diametral_max_um=_um(_get_nested(jeux, "jeu_diametral_max_m", default=0.0)),
        jeu_radial_min_um=_um(_get_nested(jeux, "jeu_radial_min_m", default=0.0)),
        jeu_radial_max_um=_um(_get_nested(jeux, "jeu_radial_max_m", default=0.0)),
        jeu_radial_nominal_um=_um(_get_nested(jeux, "jeu_radial_nominal_m", default=0.0)),

        temperature_ref_k=_safe_float(_get_nested(therm, "T_ref_k", default=0.0)),
        temperature_fonctionnement_k=_safe_float(_get_nested(therm, "T_fonctionnement_k", default=0.0)),
        alpha_piston=_safe_float(_get_nested(therm, "alpha_piston_1_k", default=_get_nested(matp, "alpha_dilatation_1_k", default=0.0))),
        alpha_cylindre=_safe_float(_get_nested(therm, "alpha_cylindre_1_k", default=_get_nested(matc, "alpha_dilatation_1_k", default=0.0))),
        alesage_min_hot_mm=_mm(_get_nested(therm, "alesage_min_hot_m", default=0.0)),
        alesage_max_hot_mm=_mm(_get_nested(therm, "alesage_max_hot_m", default=0.0)),
        piston_min_hot_mm=_mm(_get_nested(therm, "piston_min_hot_m", default=0.0)),
        piston_max_hot_mm=_mm(_get_nested(therm, "piston_max_hot_m", default=0.0)),
        jeu_diam_min_hot_um=_um(_get_nested(therm, "jeu_diam_min_hot_m", default=0.0)),
        jeu_diam_max_hot_um=_um(_get_nested(therm, "jeu_diam_max_hot_m", default=0.0)),
        jeu_rad_min_hot_um=_um(_get_nested(therm, "jeu_rad_min_hot_m", default=0.0)),
        jeu_rad_max_hot_um=_um(_get_nested(therm, "jeu_rad_max_hot_m", default=0.0)),
        non_grippage_hot_ok=_get_nested(rap, "contraintes", "non_grippage_hot_ok", default=None),

        nb_joints=int(_safe_float(_get_nested(joints, "nb_joints", default=0), 0)),
        section_joint_mm=_mm(_get_nested(joints, "section_joint_m", default=0.0)),
        squeeze=_safe_float(_get_nested(joints, "squeeze", default=0.0)),
        facteur_largeur_rainure=_safe_float(_get_nested(joints, "facteur_largeur_rainure", default=0.0)),
        profondeur_rainure_mm=_mm(_get_nested(joints, "profondeur_radiale_rainure_m", default=0.0)),
        largeur_rainure_mm=_mm(_get_nested(joints, "largeur_rainure_m", default=0.0)),
        diametre_fond_rainure_mm=_mm(_get_nested(joints, "diametre_fond_rainure_m", default=0.0)),
        rayon_fond_rainure_mm=_mm(_get_nested(joints, "rayon_fond_rainure_m", default=0.0)),
        diametre_montage_joint_mm=_mm(_get_nested(joints, "diametre_montage_joint_m", default=0.0)),
        diametre_moyen_joint_monte_mm=_mm(_get_nested(joints, "diametre_moyen_joint_monte_m", default=0.0)),
        hauteur_radiale_disponible_mm=_mm(_get_nested(joints, "hauteur_radiale_disponible_m", default=0.0)),
        entraxe_rainures_mm=_mm(_get_nested(joints, "entraxe_rainures_m", default=0.0)),
        positions_centres_rainures_mm=positions_mm,
        rainures=joints.get("rainures") if isinstance(joints.get("rainures"), list) else [],
        volume_gorge_unitaire_m3=_safe_float(_get_nested(joints, "volume_gorge_unitaire_m3", default=0.0)),
        volume_gorges_total_m3=_safe_float(_get_nested(joints, "volume_gorges_total_m3", default=0.0)),
        squeeze_reconstruit=_safe_float(_get_nested(verj, "squeeze_reconstruit", default=0.0)),
        rainures_dans_hauteur=_get_nested(verj, "rainures_dans_hauteur", default=None),

        module_elastomere_pa=_safe_float(_get_nested(joints, "module_elastomere_pa", default=0.0)),
        pression_contact_estimee_pa=_safe_float(_get_nested(joints, "pression_contact_estimee_pa", default=0.0)),
        etancheite_contact_ok=_get_nested(joints, "etancheite_contact_ok_si_p_contact_sup_pmax", default=None),

        force_gaz_n=_safe_float(_get_nested(cin, "force_gaz_n", default=0.0)),
        rayon_manivelle_mm=_mm(_get_nested(cin, "rayon_manivelle_m", default=0.0)),
        force_inertie_alternative_n=_safe_float(_get_nested(cin, "force_inertie_alternative_n", default=0.0)),
        force_axiale_nette_n=_safe_float(_get_nested(cin, "force_axiale_nette_n", default=0.0)),

        mu_joint=_safe_float(_get_nested(frj, "mu", default=0.0)),
        bande_contact_mm=_mm(_get_nested(frj, "bande_contact_m", default=0.0)),
        aire_contact_m2=_safe_float(_get_nested(frj, "aire_contact_m2", default=0.0)),
        force_normale_totale_n=_safe_float(_get_nested(frj, "force_normale_totale_estimee_n", default=0.0)),
        vitesse_moyenne_ms=_safe_float(_get_nested(frj, "vitesse_moyenne_ms", default=0.0)),
        puissance_frottement_w=_safe_float(_get_nested(frj, "puissance_frottement_w", default=0.0)),
        pv_pa_ms=_safe_float(_get_nested(frj, "PV_pa_ms", default=0.0)),
        pv_admissible_pa_ms=_safe_float(_get_nested(frj, "PV_admissible_pa_ms", default=0.0)),
        pv_ok=_get_nested(frj, "PV_ok", default=None),

        distance_glissement_m=_safe_float(_get_nested(usj, "distance_glissement_m", default=0.0)),
        volume_use_m3=_safe_float(_get_nested(usj, "volume_use_m3", default=0.0)),
        perte_epaisseur_um=_um(_get_nested(usj, "perte_epaisseur_m", default=0.0)),

        debit_fuite_m3_s=_safe_float(_get_nested(fuites, "debit_fuite_m3_s", default=0.0)),
        debit_fuite_kg_s=_safe_float(_get_nested(fuites, "debit_fuite_kg_s_est", default=0.0)),
        mu_air_pa_s=_safe_float(_get_nested(fuites, "mu_air_pa_s", default=0.0)),
        densite_air_kg_m3=_safe_float(_get_nested(fuites, "densite_air_kg_m3_est", default=0.0)),
        dP_fuite_pa=_safe_float(_get_nested(fuites, "dP_pa", default=0.0)),

        volume_plein_m3=_safe_float(_get_nested(masses, "volume_plein_m3", default=0.0)),
        volume_net_m3=_safe_float(_get_nested(masses, "volume_net_m3", default=0.0)),
        masse_kg=_safe_float(_get_nested(masses, "masse_kg", default=0.0)),
        inertie_rotation_axe_kg_m2=_safe_float(_get_nested(masses, "inertie_rotation_axe_kg_m2", default=0.0)),

        chanfrein_extremites_mm=_mm(_get_nested(cao, "chanfrein_extremites_m", default=0.0)),
        rayon_conge_tete_jupe_mm=_mm(_get_nested(cao, "rayon_conge_tete_jupe_m", default=0.0)),
        rugosite_exterieure_ra_um=_safe_float(_get_nested(cao, "rugosite_exterieure_ra_um", default=0.0)),
        rugosite_faces_ra_um=_safe_float(_get_nested(cao, "rugosite_faces_ra_um", default=0.0)),
        rugosite_fond_rainure_ra_um=_safe_float(_get_nested(cao, "rugosite_fond_rainure_ra_um", default=0.0)),
        tolerance_diametre_exterieur_um=_um(_get_nested(cao, "tolerance_diametre_exterieur_m", default=0.0)),
        tolerance_hauteur_um=_um(_get_nested(cao, "tolerance_hauteur_m", default=0.0)),
        tolerance_position_rainure_um=_um(_get_nested(cao, "tolerance_position_rainure_m", default=0.0)),
        tolerance_largeur_rainure_um=_um(_get_nested(cao, "tolerance_largeur_rainure_m", default=0.0)),
        tolerance_profondeur_rainure_um=_um(_get_nested(cao, "tolerance_profondeur_rainure_m", default=0.0)),

        rapport_complet=rap,
    )


# ============================================================
# VUE DE CÔTÉ
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisPiston):
    D = d.diametre_piston_cao_mm
    H = d.hauteur_totale_mm
    if D <= 0 or H <= 0:
        ax.text(0.5, 0.5, "Géométrie principale indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de côté")
        ax.set_axis_off()
        return

    y = D / 2.0
    x0 = 0.0
    x1 = H

    et = d.epaisseur_tete_mm if d.epaisseur_tete_mm > 0 else 0.0
    Lj = d.longueur_jupe_mm if d.longueur_jupe_mm > 0 else 0.0

    # Contour extérieur
    _add_hatched_rect(ax, x0, -y, H, 2.0 * y)
    ax.add_patch(Rectangle((x0, -y), H, 2.0 * y, fill=False, linewidth=1.6))

    # Axe piston
    ax.add_line(Line2D([x0 - 8.0, x1 + 8.0], [0.0, 0.0], **_linestyle_axis()))

    # Tête
    if et > 0:
        ax.add_line(Line2D([et, et], [-y, y], linewidth=1.0, color="black"))
        _annotate_leader(ax, x0 + 10.0, y + 12.0, 0.5 * et, y, "Tête")

    # Jupe
    if Lj > 0:
        xj0 = H - Lj
        ax.add_line(Line2D([xj0, xj0], [-y, y], linewidth=1.0, color="black"))
        _annotate_leader(ax, xj0 + 6.0, -(y + 12.0), xj0 + 0.5 * Lj, -y, "Jupe")

    # Rainures
    if d.rainures and d.largeur_rainure_mm > 0 and d.profondeur_rainure_mm > 0:
        for rg in d.rainures:
            xc = _mm(rg.get("position_centre_depuis_face_tete_m"))
            w = _mm(rg.get("largeur_m"))
            pr = _mm(rg.get("profondeur_radiale_m"))

            ax.add_patch(Rectangle((xc - 0.5 * w, y - pr), w, pr, fill=False, linewidth=1.0, linestyle="--"))
            ax.add_patch(Rectangle((xc - 0.5 * w, -y), w, pr, fill=False, linewidth=1.0, linestyle="--"))
            ax.add_line(Line2D([xc, xc], [-y - 6.0, y + 6.0], **_linestyle_hidden()))

        if d.positions_centres_rainures_mm:
            _annotate_leader(
                ax,
                min(H + 25.0, H * 0.95),
                y + 20.0,
                d.positions_centres_rainures_mm[0],
                y - 0.5 * d.profondeur_rainure_mm,
                "Rainure joint"
            )

    # Chanfreins schématiques
    if d.chanfrein_extremites_mm > 0:
        ch = min(d.chanfrein_extremites_mm, max(0.4, 0.3 * y))
        ax.add_line(Line2D([x0, x0 + ch], [y, y - ch], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x0, x0 + ch], [-y, -(y - ch)], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x1 - ch, x1], [y - ch, y], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x1 - ch, x1], [-(y - ch), -y], linewidth=1.0, color="black"))

    # Cotes horizontales
    ydim1 = y + 14.0
    ydim2 = y + 28.0
    ydim3 = y + 42.0
    _add_dimension_h(ax, x0, x1, 0.0, ydim1, f"H totale = {_fmt_mm(H)}")
    if et > 0:
        _add_dimension_h(ax, x0, et, 0.0, ydim2, f"e tête = {_fmt_mm(et)}")
    if Lj > 0:
        _add_dimension_h(ax, x1 - Lj, x1, 0.0, ydim3, f"L jupe = {_fmt_mm(Lj)}")

    # Cotes verticales
    xdim1 = H + 15.0
    xdim2 = H + 32.0
    _add_dimension_v(ax, 0.0, xdim1, -y, y, f"Ø piston = {_fmt_mm(D)}")
    if d.diametre_fond_rainure_mm > 0:
        yfg = d.diametre_fond_rainure_mm / 2.0
        _add_dimension_v(ax, 0.0, xdim2, -yfg, yfg, f"Ø fond gorge = {_fmt_mm(d.diametre_fond_rainure_mm)}")

    infos = []
    if d.nb_joints > 0:
        infos.append(f"Nb joints            : {d.nb_joints}")
    if d.section_joint_mm > 0:
        infos.append(f"Section joint        : {d.section_joint_mm:.2f} mm")
    if d.squeeze > 0:
        infos.append(f"Squeeze cible        : {d.squeeze:.4f}")
    if d.squeeze_reconstruit > 0:
        infos.append(f"Squeeze reconstruit  : {d.squeeze_reconstruit:.4f}")
    if d.jeu_radial_nominal_um > 0:
        infos.append(f"Jeu radial nominal   : {_fmt_um(d.jeu_radial_nominal_um)}")
    elif d.jeu_radial_min_um > 0:
        infos.append(f"Jeu radial min       : {_fmt_um(d.jeu_radial_min_um)}")

    if infos:
        ax.text(
            x0,
            -(y + 28.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.3,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
        )

    ax.set_title("Vue de côté détaillée")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-18.0, H + 80.0)
    ax.set_ylim(-(y + 60.0), y + 60.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE DE FACE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisPiston):
    R = d.diametre_piston_cao_mm / 2.0
    Rf = d.diametre_fond_rainure_mm / 2.0 if d.diametre_fond_rainure_mm > 0 else 0.0
    Rcyl_min = d.alesage_min_mm / 2.0 if d.alesage_min_mm > 0 else 0.0
    Rcyl_max = d.alesage_max_mm / 2.0 if d.alesage_max_mm > 0 else 0.0

    if R <= 0:
        ax.text(0.5, 0.5, "Diamètre piston indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de face")
        ax.set_axis_off()
        return

    if Rcyl_max > 0:
        ax.add_patch(Circle((0, 0), Rcyl_max, fill=False, linewidth=1.0, linestyle="--"))
    if Rcyl_min > 0:
        ax.add_patch(Circle((0, 0), Rcyl_min, fill=False, linewidth=1.0, linestyle=":"))

    ax.add_patch(Circle((0, 0), R, fill=False, linewidth=1.5))
    if Rf > 0:
        ax.add_patch(Circle((0, 0), Rf, fill=False, linewidth=1.0, linestyle="--"))

    ax.axhline(0, **_linestyle_axis())
    ax.axvline(0, **_linestyle_axis())

    txt = [
        f"Ø piston CAO = {_fmt_mm(2.0 * R)}",
    ]
    if Rcyl_min > 0:
        txt.append(f"Ø alésage min = {_fmt_mm(2.0 * Rcyl_min)}")
    if Rcyl_max > 0:
        txt.append(f"Ø alésage max = {_fmt_mm(2.0 * Rcyl_max)}")
    if d.diametre_fond_rainure_mm > 0:
        txt.append(f"Ø fond rainure = {_fmt_mm(2.0 * Rf)}")

    lim = max(R, Rcyl_max, Rcyl_min, 1.0) + 22.0
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

    ax.set_title("Vue de face")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# DÉTAIL DES RAINURES
# ============================================================

def _tracer_detail_rainures(ax, d: DonneesCroquisPiston):
    if not d.rainures or d.largeur_rainure_mm <= 0 or d.profondeur_rainure_mm <= 0 or d.hauteur_totale_mm <= 0:
        ax.text(0.5, 0.5, "Rainures non disponibles", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Détail rainures")
        ax.set_axis_off()
        return

    H = d.hauteur_totale_mm
    D = d.diametre_piston_cao_mm
    y = D / 2.0

    _add_hatched_rect(ax, 0.0, -y, H, 2.0 * y)
    ax.add_patch(Rectangle((0.0, -y), H, 2.0 * y, fill=False, linewidth=1.4))

    for rg in d.rainures:
        xc = _mm(rg.get("position_centre_depuis_face_tete_m"))
        w = _mm(rg.get("largeur_m"))
        pr = _mm(rg.get("profondeur_radiale_m"))

        ax.add_patch(Rectangle((xc - 0.5 * w, y - pr), w, pr, fill=False, linewidth=1.05, linestyle="--"))
        ax.add_patch(Rectangle((xc - 0.5 * w, -y), w, pr, fill=False, linewidth=1.05, linestyle="--"))
        ax.axvline(xc, **_linestyle_hidden())

    ydim1 = y + 12.0
    ydim2 = y + 24.0
    _add_dimension_h(ax, 0.0, H, 0.0, ydim1, f"H = {_fmt_mm(H)}")

    rg0 = d.rainures[0]
    xc0 = _mm(rg0.get("position_centre_depuis_face_tete_m"))
    w0 = _mm(rg0.get("largeur_m"))
    pr0 = _mm(rg0.get("profondeur_radiale_m"))
    _add_dimension_h(ax, xc0 - 0.5 * w0, xc0 + 0.5 * w0, 0.0, ydim2, f"Larg. gorge = {_fmt_mm(w0)}")

    xdim = H + 18.0
    _add_dimension_v(ax, 0.0, xdim, y - pr0, y, f"Prof. = {_fmt_mm(pr0)}")

    txt = [
        f"Nb rainures = {d.nb_joints}",
        f"Section joint = {d.section_joint_mm:.2f} mm" if d.section_joint_mm > 0 else "Section joint = N/A",
        f"Ø fond = {_fmt_mm(d.diametre_fond_rainure_mm)}" if d.diametre_fond_rainure_mm > 0 else "Ø fond = N/A",
        f"Rayon fond = {_fmt_mm(d.rayon_fond_rainure_mm)}" if d.rayon_fond_rainure_mm > 0 else "Rayon fond = N/A",
        f"Entraxe = {_fmt_mm(d.entraxe_rainures_mm)}" if d.entraxe_rainures_mm > 0 else "Entraxe = N/A",
        f"Hauteur radiale dispo = {_fmt_mm(d.hauteur_radiale_disponible_mm)}" if d.hauteur_radiale_disponible_mm > 0 else "Hauteur radiale dispo = N/A",
        f"Rainures dans hauteur = {d.rainures_dans_hauteur if d.rainures_dans_hauteur is not None else 'N/A'}",
    ]

    if d.positions_centres_rainures_mm:
        txt.append("Centres = " + ", ".join(f"{x:.2f} mm" for x in d.positions_centres_rainures_mm))

    ax.text(
        0.0,
        -(y + 26.0),
        "\n".join(txt),
        ha="left",
        va="top",
        fontsize=8.0,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Détail axial des rainures de joints")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-12.0, H + 90.0)
    ax.set_ylim(-(y + 50.0), y + 40.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# SCHÉMA TÊTE / JOINTS / JUPE
# ============================================================

def _tracer_schema_axial(ax, d: DonneesCroquisPiston):
    H = d.hauteur_totale_mm
    if H <= 0:
        ax.text(0.5, 0.5, "Schéma axial indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Schéma axial")
        ax.set_axis_off()
        return

    Hbox = 18.0
    ax.add_patch(Rectangle((0.0, 0.0), H, Hbox, fill=False, linewidth=1.25))

    et = d.epaisseur_tete_mm if d.epaisseur_tete_mm > 0 else 0.0
    Lj = d.longueur_jupe_mm if d.longueur_jupe_mm > 0 else 0.0
    x_jupe = H - Lj if Lj > 0 else None

    # Tête
    if et > 0:
        ax.add_patch(Rectangle((0.0, 0.0), et, Hbox, fill=False, linewidth=1.0, linestyle=":"))
        ax.text(0.5 * et, Hbox / 2.0, "Tête", ha="center", va="center", fontsize=9)

    # Jupe
    if x_jupe is not None:
        ax.add_patch(Rectangle((x_jupe, 0.0), Lj, Hbox, fill=False, linewidth=1.0, linestyle=":"))
        ax.text(x_jupe + 0.5 * Lj, Hbox / 2.0, "Jupe", ha="center", va="center", fontsize=9)

    # Rainures
    if d.rainures:
        for rg in d.rainures:
            xc = _mm(rg.get("position_centre_depuis_face_tete_m"))
            w = _mm(rg.get("largeur_m"))
            ax.add_patch(Rectangle((xc - 0.5 * w, 0.0), w, Hbox, fill=True, facecolor="white", edgecolor="black", linewidth=1.0, hatch="////"))
            ax.text(xc, Hbox + 4.0, f"J{int(rg.get('index', 0))}", ha="center", va="bottom", fontsize=8)

    ydim = Hbox + 10.0
    _add_dimension_h(ax, 0.0, H, 0.0, ydim, f"H totale = {_fmt_mm(H)}")
    if et > 0:
        _add_dimension_h(ax, 0.0, et, 0.0, ydim + 14.0, f"Tête = {_fmt_mm(et)}")
    if x_jupe is not None:
        _add_dimension_h(ax, x_jupe, H, 0.0, ydim + 28.0, f"Jupe = {_fmt_mm(Lj)}")

    txt = []
    if d.hauteur_totale_min_geo_mm > 0:
        txt.append(f"H min géométrique = {_fmt_mm(d.hauteur_totale_min_geo_mm)}")
    if d.chanfrein_extremites_mm > 0:
        txt.append(f"Chanfrein = {_fmt_mm(d.chanfrein_extremites_mm)}")
    if d.rayon_conge_tete_jupe_mm > 0:
        txt.append(f"Congé tête/jupe = {_fmt_mm(d.rayon_conge_tete_jupe_mm)}")

    if txt:
        ax.text(
            0.0,
            -15.0,
            "\n".join(txt),
            ha="left",
            va="top",
            fontsize=8.0,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
        )

    ax.set_title("Répartition axiale tête / joints / jupe")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-10.0, H + 10.0)
    ax.set_ylim(-42.0, Hbox + 35.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche(fig, d: DonneesCroquisPiston):
    lines = [
        f"Alésage nominal              : {_fmt_mm(d.alesage_nominal_mm) if d.alesage_nominal_mm > 0 else 'N/A'}",
        f"Course                       : {_fmt_mm(d.course_mm) if d.course_mm > 0 else 'N/A'}",
        f"Régime                       : {f'{d.rpm:.2f} rpm' if d.rpm > 0 else 'N/A'}",
        f"Alésage min                  : {_fmt_mm(d.alesage_min_mm) if d.alesage_min_mm > 0 else 'N/A'}",
        f"Alésage max                  : {_fmt_mm(d.alesage_max_mm) if d.alesage_max_mm > 0 else 'N/A'}",
        f"Ø piston min                 : {_fmt_mm(d.diametre_piston_min_mm) if d.diametre_piston_min_mm > 0 else 'N/A'}",
        f"Ø piston max                 : {_fmt_mm(d.diametre_piston_max_mm) if d.diametre_piston_max_mm > 0 else 'N/A'}",
        f"Ø piston CAO                 : {_fmt_mm(d.diametre_piston_cao_mm) if d.diametre_piston_cao_mm > 0 else 'N/A'}",
        f"H totale                     : {_fmt_mm(d.hauteur_totale_mm) if d.hauteur_totale_mm > 0 else 'N/A'}",
        f"H min géométrique            : {_fmt_mm(d.hauteur_totale_min_geo_mm) if d.hauteur_totale_min_geo_mm > 0 else 'N/A'}",
        f"Épaisseur tête               : {_fmt_mm(d.epaisseur_tete_mm) if d.epaisseur_tete_mm > 0 else 'N/A'}",
        f"Longueur jupe                : {_fmt_mm(d.longueur_jupe_mm) if d.longueur_jupe_mm > 0 else 'N/A'}",
        f"Jeu diam. min                : {_fmt_um(d.jeu_diametral_min_um) if d.jeu_diametral_min_um != 0 else 'N/A'}",
        f"Jeu diam. max                : {_fmt_um(d.jeu_diametral_max_um) if d.jeu_diametral_max_um != 0 else 'N/A'}",
        f"Jeu radial min               : {_fmt_um(d.jeu_radial_min_um) if d.jeu_radial_min_um != 0 else 'N/A'}",
        f"Jeu radial max               : {_fmt_um(d.jeu_radial_max_um) if d.jeu_radial_max_um != 0 else 'N/A'}",
        f"Jeu radial nominal           : {_fmt_um(d.jeu_radial_nominal_um) if d.jeu_radial_nominal_um != 0 else 'N/A'}",
        f"T réf                        : {f'{d.temperature_ref_k:.2f} K' if d.temperature_ref_k > 0 else 'N/A'}",
        f"T fonctionnement             : {f'{d.temperature_fonctionnement_k:.2f} K' if d.temperature_fonctionnement_k > 0 else 'N/A'}",
        f"alpha piston                 : {f'{d.alpha_piston:.6e} 1/K' if d.alpha_piston > 0 else 'N/A'}",
        f"alpha cylindre               : {f'{d.alpha_cylindre:.6e} 1/K' if d.alpha_cylindre > 0 else 'N/A'}",
        f"Alésage min chaud            : {_fmt_mm(d.alesage_min_hot_mm) if d.alesage_min_hot_mm > 0 else 'N/A'}",
        f"Alésage max chaud            : {_fmt_mm(d.alesage_max_hot_mm) if d.alesage_max_hot_mm > 0 else 'N/A'}",
        f"Piston min chaud             : {_fmt_mm(d.piston_min_hot_mm) if d.piston_min_hot_mm > 0 else 'N/A'}",
        f"Piston max chaud             : {_fmt_mm(d.piston_max_hot_mm) if d.piston_max_hot_mm > 0 else 'N/A'}",
        f"Jeu diam. min chaud          : {_fmt_um(d.jeu_diam_min_hot_um) if d.jeu_diam_min_hot_um != 0 else 'N/A'}",
        f"Jeu diam. max chaud          : {_fmt_um(d.jeu_diam_max_hot_um) if d.jeu_diam_max_hot_um != 0 else 'N/A'}",
        f"Jeu rad. min chaud           : {_fmt_um(d.jeu_rad_min_hot_um) if d.jeu_rad_min_hot_um != 0 else 'N/A'}",
        f"Jeu rad. max chaud           : {_fmt_um(d.jeu_rad_max_hot_um) if d.jeu_rad_max_hot_um != 0 else 'N/A'}",
        f"Non-grippage à chaud         : {d.non_grippage_hot_ok if d.non_grippage_hot_ok is not None else 'N/A'}",
        f"Nb joints                    : {d.nb_joints if d.nb_joints > 0 else 'N/A'}",
        f"Section joint                : {f'{d.section_joint_mm:.2f} mm' if d.section_joint_mm > 0 else 'N/A'}",
        f"Squeeze cible                : {f'{d.squeeze:.6f}' if d.squeeze > 0 else 'N/A'}",
        f"Squeeze reconstruit          : {f'{d.squeeze_reconstruit:.6f}' if d.squeeze_reconstruit > 0 else 'N/A'}",
        f"Facteur largeur gorge        : {f'{d.facteur_largeur_rainure:.6f}' if d.facteur_largeur_rainure > 0 else 'N/A'}",
        f"Profondeur gorge             : {_fmt_mm(d.profondeur_rainure_mm) if d.profondeur_rainure_mm > 0 else 'N/A'}",
        f"Largeur gorge                : {_fmt_mm(d.largeur_rainure_mm) if d.largeur_rainure_mm > 0 else 'N/A'}",
        f"Ø fond gorge                 : {_fmt_mm(d.diametre_fond_rainure_mm) if d.diametre_fond_rainure_mm > 0 else 'N/A'}",
        f"Rayon fond gorge             : {_fmt_mm(d.rayon_fond_rainure_mm) if d.rayon_fond_rainure_mm > 0 else 'N/A'}",
        f"Ø montage joint              : {_fmt_mm(d.diametre_montage_joint_mm) if d.diametre_montage_joint_mm > 0 else 'N/A'}",
        f"Ø moyen joint monté          : {_fmt_mm(d.diametre_moyen_joint_monte_mm) if d.diametre_moyen_joint_monte_mm > 0 else 'N/A'}",
        f"Hauteur radiale dispo        : {_fmt_mm(d.hauteur_radiale_disponible_mm) if d.hauteur_radiale_disponible_mm > 0 else 'N/A'}",
        f"Entraxe rainures             : {_fmt_mm(d.entraxe_rainures_mm) if d.entraxe_rainures_mm > 0 else 'N/A'}",
        f"Volume gorge unitaire        : {_fmt_m3(d.volume_gorge_unitaire_m3) if d.volume_gorge_unitaire_m3 > 0 else 'N/A'}",
        f"Volume gorges total          : {_fmt_m3(d.volume_gorges_total_m3) if d.volume_gorges_total_m3 > 0 else 'N/A'}",
        f"Rainures dans hauteur        : {d.rainures_dans_hauteur if d.rainures_dans_hauteur is not None else 'N/A'}",
        f"Module élastomère            : {_fmt_pa(d.module_elastomere_pa) if d.module_elastomere_pa > 0 else 'N/A'}",
        f"Pression contact estimée     : {_fmt_pa(d.pression_contact_estimee_pa) if d.pression_contact_estimee_pa > 0 else 'N/A'}",
        f"Étanchéité contact > Pmax    : {d.etancheite_contact_ok if d.etancheite_contact_ok is not None else 'N/A'}",
        f"Force gaz                    : {_fmt_n(d.force_gaz_n) if d.force_gaz_n != 0 else 'N/A'}",
        f"Rayon manivelle              : {_fmt_mm(d.rayon_manivelle_mm) if d.rayon_manivelle_mm > 0 else 'N/A'}",
        f"Force inertie alternative    : {_fmt_n(d.force_inertie_alternative_n) if d.force_inertie_alternative_n != 0 else 'N/A'}",
        f"Force axiale nette           : {_fmt_n(d.force_axiale_nette_n) if d.force_axiale_nette_n != 0 else 'N/A'}",
        f"Mu joint                     : {f'{d.mu_joint:.6f}' if d.mu_joint != 0 else 'N/A'}",
        f"Bande contact                : {_fmt_mm(d.bande_contact_mm) if d.bande_contact_mm > 0 else 'N/A'}",
        f"Aire contact                 : {_fmt_m2(d.aire_contact_m2) if d.aire_contact_m2 > 0 else 'N/A'}",
        f"Force normale totale         : {_fmt_n(d.force_normale_totale_n) if d.force_normale_totale_n > 0 else 'N/A'}",
        f"Vitesse moyenne              : {_fmt_ms(d.vitesse_moyenne_ms) if d.vitesse_moyenne_ms > 0 else 'N/A'}",
        f"Puissance frottement         : {_fmt_w(d.puissance_frottement_w) if d.puissance_frottement_w > 0 else 'N/A'}",
        f"PV                           : {f'{d.pv_pa_ms:.6e} Pa·m/s' if d.pv_pa_ms > 0 else 'N/A'}",
        f"PV admissible                : {f'{d.pv_admissible_pa_ms:.6e} Pa·m/s' if d.pv_admissible_pa_ms > 0 else 'N/A'}",
        f"PV OK                        : {d.pv_ok if d.pv_ok is not None else 'N/A'}",
        f"Distance glissement          : {f'{d.distance_glissement_m:.6f} m' if d.distance_glissement_m > 0 else 'N/A'}",
        f"Volume usure                 : {_fmt_m3(d.volume_use_m3) if d.volume_use_m3 > 0 else 'N/A'}",
        f"Perte épaisseur              : {_fmt_um(d.perte_epaisseur_um) if d.perte_epaisseur_um > 0 else 'N/A'}",
        f"Débit fuite volumique        : {f'{d.debit_fuite_m3_s:.6e} m³/s' if d.debit_fuite_m3_s > 0 else 'N/A'}",
        f"Débit fuite massique         : {f'{d.debit_fuite_kg_s:.6e} kg/s' if d.debit_fuite_kg_s > 0 else 'N/A'}",
        f"mu air                       : {f'{d.mu_air_pa_s:.6e} Pa·s' if d.mu_air_pa_s > 0 else 'N/A'}",
        f"rho air                      : {f'{d.densite_air_kg_m3:.6f} kg/m³' if d.densite_air_kg_m3 > 0 else 'N/A'}",
        f"dP fuite                     : {_fmt_pa(d.dP_fuite_pa) if d.dP_fuite_pa > 0 else 'N/A'}",
        f"Volume plein                 : {_fmt_m3(d.volume_plein_m3) if d.volume_plein_m3 > 0 else 'N/A'}",
        f"Volume net                   : {_fmt_m3(d.volume_net_m3) if d.volume_net_m3 > 0 else 'N/A'}",
        f"Masse                        : {_fmt_kg(d.masse_kg) if d.masse_kg > 0 else 'N/A'}",
        f"Inertie rotation axe         : {f'{d.inertie_rotation_axe_kg_m2:.6e} kg·m²' if d.inertie_rotation_axe_kg_m2 > 0 else 'N/A'}",
        f"Chanfrein extrémités         : {_fmt_mm(d.chanfrein_extremites_mm) if d.chanfrein_extremites_mm > 0 else 'N/A'}",
        f"Rayon congé tête/jupe        : {_fmt_mm(d.rayon_conge_tete_jupe_mm) if d.rayon_conge_tete_jupe_mm > 0 else 'N/A'}",
        f"Ra extérieure                : {f'{d.rugosite_exterieure_ra_um:.2f} µm' if d.rugosite_exterieure_ra_um > 0 else 'N/A'}",
        f"Ra faces                     : {f'{d.rugosite_faces_ra_um:.2f} µm' if d.rugosite_faces_ra_um > 0 else 'N/A'}",
        f"Ra fond rainure              : {f'{d.rugosite_fond_rainure_ra_um:.2f} µm' if d.rugosite_fond_rainure_ra_um > 0 else 'N/A'}",
        f"Tol. Ø ext                   : {_fmt_um(d.tolerance_diametre_exterieur_um) if d.tolerance_diametre_exterieur_um > 0 else 'N/A'}",
        f"Tol. hauteur                 : {_fmt_um(d.tolerance_hauteur_um) if d.tolerance_hauteur_um > 0 else 'N/A'}",
        f"Tol. position rainure        : {_fmt_um(d.tolerance_position_rainure_um) if d.tolerance_position_rainure_um > 0 else 'N/A'}",
        f"Tol. largeur rainure         : {_fmt_um(d.tolerance_largeur_rainure_um) if d.tolerance_largeur_rainure_um > 0 else 'N/A'}",
        f"Tol. profondeur rainure      : {_fmt_um(d.tolerance_profondeur_rainure_um) if d.tolerance_profondeur_rainure_um > 0 else 'N/A'}",
    ]

    if d.positions_centres_rainures_mm:
        lines.append("Centres rainures             : " + ", ".join(f"{v:.2f} mm" for v in d.positions_centres_rainures_mm))

    fig.text(
        0.012,
        0.014,
        "DONNÉES EXTRAITES DE Piston.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=7.55,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_piston_2d(
    piston: Piston,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Piston",
):
    d = extraire_donnees_croquis(piston)

    if d.diametre_piston_cao_mm <= 0:
        raise ValueError("Impossible de tracer : diamètre piston CAO absent.")
    if d.hauteur_totale_mm <= 0:
        raise ValueError("Impossible de tracer : hauteur totale du piston absente.")

    fig = plt.figure(figsize=(19, 11))
    gs = fig.add_gridspec(2, 3, height_ratios=[2.2, 1.35], width_ratios=[1.55, 1.0, 1.1])

    ax_side = fig.add_subplot(gs[0, :])
    ax_front = fig.add_subplot(gs[1, 0])
    ax_grooves = fig.add_subplot(gs[1, 1])
    ax_axial = fig.add_subplot(gs[1, 2])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_cote(ax_side, d)
    _tracer_vue_face(ax_front, d)
    _tracer_detail_rainures(ax_grooves, d)
    _tracer_schema_axial(ax_axial, d)

    _ajouter_cartouche(fig, d)

    plt.tight_layout(rect=[0.0, 0.12, 1.0, 0.965])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, {
        "vue_cote": ax_side,
        "vue_face": ax_front,
        "detail_rainures": ax_grooves,
        "schema_axial": ax_axial,
    }, d


# ============================================================
# EXEMPLE D’UTILISATION
# ============================================================

if __name__ == "__main__":
    p = Piston(
        alesage_nominal_m=0.080,
        fit_hole="H7",
        fit_shaft="h6",
        pression_max_pa=15e5,
        temperature_fonctionnement_k=350.0,
        course_m=0.060,
        rpm=1200.0,
        materiau_piston_cle="alu_7075_t6",
        materiau_cylindre_cle="acier_42crmo4_qt",
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur_rainure=1.5,
        materiau_joint_cle="nbr_70",
        coeff_frottement_joint=0.15,
        PV_admissible_pa_ms=2.0e6,
        longueur_portee_etanche_m=0.010,
        pression_aval_pa=1e5,
    )

    tracer_croquis_piston_2d(
        p,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Piston calculé",
    )