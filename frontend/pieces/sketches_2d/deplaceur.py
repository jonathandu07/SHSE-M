# frontend/pieces/sketches_2d/deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, Circle

from backend.pieces.deplaceur import Deplaceur


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


def _fmt_m4(v: float) -> str:
    return f"{v:.6e} m⁴"


def _fmt_kg(v: float) -> str:
    return f"{v:.6f} kg"


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
class DonneesCroquisDeplaceur:
    # Déplaceur
    type_deplaceur: str = ""
    diametre_exterieur_mm: float = 0.0
    diametre_interieur_mm: float = 0.0
    longueur_totale_mm: float = 0.0
    epaisseur_paroi_mm: float = 0.0
    aire_face_m2: float = 0.0
    section_matiere_m2: float = 0.0
    volume_matiere_m3: float = 0.0
    masse_kg: float = 0.0

    # Cylindre associé
    cylindre_diametre_interieur_mm: float = 0.0
    cylindre_diametre_exterieur_mm: float = 0.0
    cylindre_longueur_utile_mm: float = 0.0

    # Jeu et position
    jeu_radial_um: float = 0.0
    position_axiale_centre_mm: float = 0.0
    position_face_froid_mm: float = 0.0
    position_face_chaud_mm: float = 0.0
    position_min_centre_mm: float = 0.0
    position_max_centre_mm: float = 0.0
    position_normalisee: float = 0.0
    course_disponible_mm: float = 0.0
    course_geometrique_max_mm: float = 0.0

    # Volumes
    longueur_zone_froide_mm: float = 0.0
    longueur_zone_chaude_mm: float = 0.0
    volume_zone_froide_m3: float = 0.0
    volume_zone_chaude_m3: float = 0.0
    volume_total_interne_cylindre_m3: float = 0.0
    volume_occupe_par_deplaceur_m3: float = 0.0
    volume_libre_total_hors_deplaceur_m3: float = 0.0

    # Pressions / efforts
    pression_chaud_pa: float = 0.0
    pression_froid_pa: float = 0.0
    delta_p_pa: float = 0.0
    force_axiale_N: float = 0.0
    surface_effective_m2: float = 0.0

    # Thermique / déformations
    temperature_chaud_C: float = 0.0
    temperature_froid_C: float = 0.0
    deformation_axiale: float = 0.0
    allongement_um: float = 0.0
    augmentation_rayon_um: float = 0.0
    jeu_residuel_um: float = 0.0

    # Flambage
    flambage_euler_N: float = 0.0
    marge_flambage: float = 0.0

    # Orifice / gaz
    perte_charge_orifice_pa: float = 0.0
    rho_gaz_utilise_kg_m3: float = 0.0

    # Joints / rainures
    nb_joints: int = 0
    section_joint_mm: float = 0.0
    largeur_rainure_mm: float = 0.0
    profondeur_rainure_mm: float = 0.0
    diametre_fond_rainure_mm: float = 0.0
    rayon_fond_rainure_mm: float = 0.0
    positions_axiales_rainures_mm: Optional[List[float]] = None
    marge_extremite_rainure_mm: float = 0.0
    entraxe_min_rainure_mm: float = 0.0
    taux_compression: float = 0.0
    taux_remplissage_max: float = 0.0

    # Fabrication / CAO
    chanfrein_extremites_mm: float = 0.0
    rayon_conge_mm: float = 0.0
    rugosite_exterieure_ra_um: float = 0.0
    rugosite_faces_ra_um: float = 0.0
    tolerance_diametre_exterieur_um: float = 0.0
    tolerance_longueur_um: float = 0.0
    tolerance_position_um: float = 0.0

    # Vérifications
    compatible_alesage: Optional[bool] = None
    compatible_longueur: Optional[bool] = None
    position_dans_course: Optional[bool] = None

    rapport_complet: Optional[Dict[str, Any]] = None


def extraire_donnees_croquis(deplaceur: Deplaceur) -> DonneesCroquisDeplaceur:
    rapport = deplaceur.analyser(strict=False)

    cyl = rapport.get("cylindre_associe", {})
    geo = rapport.get("geometrie", {})
    pos = rapport.get("positions", {})
    vol = rapport.get("volumes", {})
    press = rapport.get("pressions", {})
    eff = rapport.get("efforts", {})
    therm = rapport.get("thermique", {})
    cont = rapport.get("contraintes", {})
    etan = rapport.get("etancheite", {})
    fab = rapport.get("fabrication", {})
    ver = rapport.get("verifications", {})
    cao = _get_nested(geo, "cao", default={}) or {}
    rain = _get_nested(cao, "rainures_joints", default={}) or {}

    rain_pos = rain.get("positions_axiales_rainures_m") if isinstance(rain.get("positions_axiales_rainures_m"), list) else []
    rain_pos_mm = [_mm(v) for v in rain_pos if _safe_float(v, -1) >= 0]

    return DonneesCroquisDeplaceur(
        type_deplaceur=str(_get_nested(cao, "type_deplaceur", default="") or ""),
        diametre_exterieur_mm=_mm(_get_nested(cao, "diametre_exterieur_m", default=_get_nested(geo, "diametre_exterieur_m", default=0.0))),
        diametre_interieur_mm=_mm(_get_nested(cao, "diametre_interieur_m", default=_get_nested(geo, "diametre_interieur_m", default=0.0))),
        longueur_totale_mm=_mm(_get_nested(cao, "longueur_totale_m", default=_get_nested(geo, "longueur_totale_m", default=0.0))),
        epaisseur_paroi_mm=_mm(_get_nested(geo, "epaisseur_paroi_m", default=0.0)),
        aire_face_m2=_safe_float(_get_nested(geo, "aire_face_m2", default=0.0)),
        section_matiere_m2=_safe_float(_get_nested(geo, "section_matiere_m2", default=0.0)),
        volume_matiere_m3=_safe_float(_get_nested(geo, "volume_matiere_m3", default=0.0)),
        masse_kg=_safe_float(_get_nested(geo, "masse_kg", default=0.0)),

        cylindre_diametre_interieur_mm=_mm(_get_nested(cyl, "diametre_interieur_m", default=0.0)),
        cylindre_diametre_exterieur_mm=_mm(_get_nested(cyl, "diametre_exterieur_m", default=0.0)),
        cylindre_longueur_utile_mm=_mm(_get_nested(cyl, "longueur_utile_m", default=0.0)),

        jeu_radial_um=_um(_get_nested(geo, "jeu_radial_m", default=0.0)),
        position_axiale_centre_mm=_mm(_get_nested(pos, "position_axiale_centre_m", default=0.0)),
        position_face_froid_mm=_mm(_get_nested(pos, "position_face_froid_m", default=0.0)),
        position_face_chaud_mm=_mm(_get_nested(pos, "position_face_chaud_m", default=0.0)),
        position_min_centre_mm=_mm(_get_nested(pos, "position_min_centre_m", default=0.0)),
        position_max_centre_mm=_mm(_get_nested(pos, "position_max_centre_m", default=0.0)),
        position_normalisee=_safe_float(_get_nested(pos, "position_centre_normalisee_sur_course", default=0.0)),
        course_disponible_mm=_mm(_get_nested(geo, "course_disponible_m", default=0.0)),
        course_geometrique_max_mm=_mm(_get_nested(ver, "course_geometrique_max_m", default=0.0)),

        longueur_zone_froide_mm=_mm(_get_nested(vol, "longueur_zone_froide_m", default=0.0)),
        longueur_zone_chaude_mm=_mm(_get_nested(vol, "longueur_zone_chaude_m", default=0.0)),
        volume_zone_froide_m3=_safe_float(_get_nested(vol, "volume_zone_froide_m3", default=0.0)),
        volume_zone_chaude_m3=_safe_float(_get_nested(vol, "volume_zone_chaude_m3", default=0.0)),
        volume_total_interne_cylindre_m3=_safe_float(_get_nested(vol, "volume_total_interne_cylindre_m3", default=0.0)),
        volume_occupe_par_deplaceur_m3=_safe_float(_get_nested(vol, "volume_occupe_par_deplaceur_m3", default=0.0)),
        volume_libre_total_hors_deplaceur_m3=_safe_float(_get_nested(vol, "volume_libre_total_hors_deplaceur_m3", default=0.0)),

        pression_chaud_pa=_safe_float(_get_nested(press, "pression_chaud_pa", default=0.0)),
        pression_froid_pa=_safe_float(_get_nested(press, "pression_froid_pa", default=0.0)),
        delta_p_pa=_safe_float(_get_nested(press, "delta_p_chaud_froid_pa", default=0.0)),
        force_axiale_N=_safe_float(_get_nested(eff, "force_axiale_N", default=0.0)),
        surface_effective_m2=_safe_float(_get_nested(eff, "surface_effective_m2", default=0.0)),

        temperature_chaud_C=_safe_float(_get_nested(therm, "temperature_chaud_C", default=0.0)),
        temperature_froid_C=_safe_float(_get_nested(therm, "temperature_froid_C", default=0.0)),
        deformation_axiale=_safe_float(_get_nested(cont, "deformation_axiale", default=0.0)),
        allongement_um=_um(_get_nested(cont, "allongement_m", default=0.0)),
        augmentation_rayon_um=_um(_get_nested(cont, "augmentation_rayon_m", default=0.0)),
        jeu_residuel_um=_um(_get_nested(ver, "jeu_residuel_m", default=0.0)),

        flambage_euler_N=_safe_float(_get_nested(ver, "flambage_euler_N", default=0.0)),
        marge_flambage=_safe_float(_get_nested(ver, "marge_flambage", default=0.0)),

        perte_charge_orifice_pa=_safe_float(_get_nested(therm, "perte_charge_orifice_pa", default=0.0)),
        rho_gaz_utilise_kg_m3=_safe_float(_get_nested(therm, "rho_gaz_utilise_kg_m3", default=0.0)),

        nb_joints=int(_safe_float(_get_nested(etan, "nb_joints", default=0), 0)),
        section_joint_mm=_safe_float(_get_nested(etan, "section_joint_mm", default=0.0)),
        largeur_rainure_mm=_mm(_get_nested(etan, "largeur_rainure_m", default=_get_nested(rain, "largeur_rainure_m", default=0.0))),
        profondeur_rainure_mm=_mm(_get_nested(etan, "profondeur_rainure_m", default=_get_nested(rain, "profondeur_rainure_m", default=0.0))),
        diametre_fond_rainure_mm=_mm(_get_nested(etan, "diametre_fond_rainure_m", default=_get_nested(rain, "diametre_fond_rainure_m", default=0.0))),
        rayon_fond_rainure_mm=_mm(_get_nested(etan, "rayon_fond_rainure_m", default=_get_nested(rain, "rayon_fond_rainure_m", default=0.0))),
        positions_axiales_rainures_mm=rain_pos_mm,
        marge_extremite_rainure_mm=_mm(_get_nested(rain, "marge_extremite_m", default=0.0)),
        entraxe_min_rainure_mm=_mm(_get_nested(rain, "entraxe_min_m", default=0.0)),
        taux_compression=_safe_float(_get_nested(etan, "taux_compression", default=0.0)),
        taux_remplissage_max=_safe_float(_get_nested(etan, "taux_remplissage_max", default=0.0)),

        chanfrein_extremites_mm=_mm(_get_nested(fab, "chanfrein_extremites_m", default=0.0)),
        rayon_conge_mm=_mm(_get_nested(fab, "rayon_conge_m", default=0.0)),
        rugosite_exterieure_ra_um=_safe_float(_get_nested(fab, "rugosite_exterieure_ra_um", default=0.0)),
        rugosite_faces_ra_um=_safe_float(_get_nested(fab, "rugosite_faces_ra_um", default=0.0)),
        tolerance_diametre_exterieur_um=_um(_get_nested(fab, "tolerance_diametre_exterieur_m", default=0.0)),
        tolerance_longueur_um=_um(_get_nested(fab, "tolerance_longueur_m", default=0.0)),
        tolerance_position_um=_um(_get_nested(fab, "tolerance_position_m", default=0.0)),

        compatible_alesage=_get_nested(ver, "diametre_deplaceur_compatible_alésage", default=None),
        compatible_longueur=_get_nested(ver, "longueur_deplaceur_compatible_cylindre", default=None),
        position_dans_course=_get_nested(ver, "position_axiale_dans_course", default=None),

        rapport_complet=rapport,
    )


# ============================================================
# VUE DE CÔTÉ DÉTAILLÉE
# ============================================================

def _tracer_vue_cote(ax, d: DonneesCroquisDeplaceur):
    Ldep = d.longueur_totale_mm
    Ddep = d.diametre_exterieur_mm
    Ddep_i = d.diametre_interieur_mm
    Dcyl = d.cylindre_diametre_interieur_mm
    Lcyl = d.cylindre_longueur_utile_mm

    if Ldep <= 0 or Ddep <= 0:
        ax.text(0.5, 0.5, "Géométrie du déplaceur indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de côté")
        ax.set_axis_off()
        return

    y_dep = Ddep / 2.0
    y_dep_i = Ddep_i / 2.0 if Ddep_i > 0 else 0.0
    y_cyl = Dcyl / 2.0 if Dcyl > 0 else y_dep + max(8.0, d.jeu_radial_um / 1000.0)

    xc = d.position_axiale_centre_mm if d.position_axiale_centre_mm > 0 else 0.5 * Ldep
    x0 = d.position_face_froid_mm if d.position_face_froid_mm > 0 else xc - 0.5 * Ldep
    x1 = d.position_face_chaud_mm if d.position_face_chaud_mm > 0 else xc + 0.5 * Ldep

    # Cylindre si connu
    if Lcyl > 0 and Dcyl > 0:
        ax.add_patch(Rectangle((0.0, -y_cyl), Lcyl, 2.0 * y_cyl, fill=False, linewidth=1.5))
        ax.add_line(Line2D([0.0, Lcyl], [0.0, 0.0], **_linestyle_axe()))

    # Déplaceur
    _add_hatched_rect(ax, x0, -y_dep, Ldep, 2.0 * y_dep)
    ax.add_patch(Rectangle((x0, -y_dep), Ldep, 2.0 * y_dep, fill=False, linewidth=1.6))

    # Tubulaire
    if d.type_deplaceur == "tubulaire" and Ddep_i > 0:
        ax.add_patch(Rectangle((x0, -y_dep_i), Ldep, 2.0 * y_dep_i, fill=True, facecolor="white", edgecolor="black", linewidth=1.1))

    # Chanfreins schématiques
    if d.chanfrein_extremites_mm > 0:
        ch = min(d.chanfrein_extremites_mm, max(0.4, 0.3 * y_dep))
        ax.add_line(Line2D([x0, x0 + ch], [y_dep, y_dep - ch], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x0, x0 + ch], [-y_dep, -(y_dep - ch)], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x1 - ch, x1], [y_dep - ch, y_dep], linewidth=1.0, color="black"))
        ax.add_line(Line2D([x1 - ch, x1], [-(y_dep - ch), -y_dep], linewidth=1.0, color="black"))

    # Rainures
    if d.positions_axiales_rainures_mm and d.largeur_rainure_mm > 0 and d.profondeur_rainure_mm > 0:
        rg_w = d.largeur_rainure_mm
        rg_h = d.profondeur_rainure_mm
        y_top = y_dep
        for xr in d.positions_axiales_rainures_mm:
            ax.add_patch(Rectangle((xr - 0.5 * rg_w, y_top - rg_h), rg_w, rg_h, fill=False, linewidth=1.0, linestyle="--"))
            ax.add_patch(Rectangle((xr - 0.5 * rg_w, -y_top), rg_w, rg_h, fill=False, linewidth=1.0, linestyle="--"))

    # Position / volumes
    if Lcyl > 0:
        if d.position_face_froid_mm > 0:
            ax.add_patch(Rectangle((0.0, y_cyl + 4.0), d.position_face_froid_mm, 4.0, fill=False, linewidth=0.8, linestyle=":"))
            ax.text(0.5 * d.position_face_froid_mm, y_cyl + 10.0, "Zone froide", ha="center", va="bottom", fontsize=8.5)
        if d.position_face_chaud_mm > 0 and d.position_face_chaud_mm < Lcyl:
            ax.add_patch(Rectangle((d.position_face_chaud_mm, y_cyl + 4.0), Lcyl - d.position_face_chaud_mm, 4.0, fill=False, linewidth=0.8, linestyle=":"))
            ax.text(d.position_face_chaud_mm + 0.5 * (Lcyl - d.position_face_chaud_mm), y_cyl + 10.0, "Zone chaude", ha="center", va="bottom", fontsize=8.5)

    # Leaders
    _annotate_leader(ax, x0 - 70.0, y_dep + 18.0, x0 + 0.15 * Ldep, y_dep, "Déplaceur")
    if d.type_deplaceur == "tubulaire" and Ddep_i > 0:
        _annotate_leader(ax, x1 + 16.0, y_dep_i + 10.0, x0 + 0.75 * Ldep, y_dep_i, "Cavité interne")
    if d.positions_axiales_rainures_mm:
        _annotate_leader(ax, x1 + 16.0, y_dep + 25.0, d.positions_axiales_rainures_mm[0], y_dep - 0.5 * d.profondeur_rainure_mm, "Rainure joint")

    # Cotes principales
    ydim1 = max(y_cyl, y_dep) + 16.0
    ydim2 = max(y_cyl, y_dep) + 32.0
    ydim3 = max(y_cyl, y_dep) + 48.0

    _add_dimension_h(ax, x0, x1, 0.0, ydim1, f"L déplaceur = {_fmt_mm(Ldep)}")
    if Lcyl > 0:
        _add_dimension_h(ax, 0.0, Lcyl, 0.0, ydim2, f"L cylindre utile = {_fmt_mm(Lcyl)}")
    if d.position_axiale_centre_mm > 0 and d.position_min_centre_mm > 0 and d.position_max_centre_mm > 0:
        _add_dimension_h(ax, d.position_min_centre_mm, d.position_max_centre_mm, 0.0, ydim3, f"Course géométrique = {_fmt_mm(d.position_max_centre_mm - d.position_min_centre_mm)}")

    xdim1 = max(x1, Lcyl) + 18.0
    xdim2 = max(x1, Lcyl) + 36.0
    xdim3 = max(x1, Lcyl) + 54.0

    _add_dimension_v(ax, 0.0, xdim1, -y_dep, y_dep, f"Ø dep = {_fmt_mm(Ddep)}")
    if Ddep_i > 0:
        _add_dimension_v(ax, 0.0, xdim2, -y_dep_i, y_dep_i, f"Ø int = {_fmt_mm(Ddep_i)}")
    if Dcyl > 0:
        _add_dimension_v(ax, 0.0, xdim3, -y_cyl, y_cyl, f"Ø cyl = {_fmt_mm(Dcyl)}")

    infos = []
    if d.epaisseur_paroi_mm > 0:
        infos.append(f"Épaisseur paroi      : {_fmt_mm(d.epaisseur_paroi_mm)}")
    if d.jeu_radial_um > 0:
        infos.append(f"Jeu radial           : {_fmt_um(d.jeu_radial_um)}")
    if d.force_axiale_N != 0:
        infos.append(f"Force axiale         : {_fmt_n(d.force_axiale_N)}")
    if d.delta_p_pa != 0:
        infos.append(f"Δp chaud-froid       : {_fmt_pa(d.delta_p_pa)}")
    if d.masse_kg > 0:
        infos.append(f"Masse                : {_fmt_kg(d.masse_kg)}")

    if infos:
        ax.text(
            x0,
            -(max(y_cyl, y_dep) + 34.0),
            "\n".join(infos),
            ha="left",
            va="top",
            fontsize=8.5,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="black", linewidth=0.6),
        )

    xmax = max(x1, Lcyl, xdim3) + 55.0
    xmin = min(0.0, x0) - 80.0

    ax.set_title("Vue de côté détaillée dans le cylindre")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(-(max(y_cyl, y_dep) + 75.0), max(y_cyl, y_dep) + 75.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# VUE DE FACE
# ============================================================

def _tracer_vue_face(ax, d: DonneesCroquisDeplaceur):
    Rext = d.diametre_exterieur_mm / 2.0
    Rint = d.diametre_interieur_mm / 2.0 if d.diametre_interieur_mm > 0 else 0.0
    Rcyl = d.cylindre_diametre_interieur_mm / 2.0 if d.cylindre_diametre_interieur_mm > 0 else 0.0

    if Rext <= 0:
        ax.text(0.5, 0.5, "Diamètre extérieur indisponible", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Vue de face")
        ax.set_axis_off()
        return

    if Rcyl > 0:
        ax.add_patch(Circle((0, 0), Rcyl, fill=False, linewidth=1.0, linestyle="--"))
    ax.add_patch(Circle((0, 0), Rext, fill=False, linewidth=1.5))
    if Rint > 0:
        ax.add_patch(Circle((0, 0), Rint, fill=False, linewidth=1.1))

    ax.axhline(0, **_linestyle_axe())
    ax.axvline(0, **_linestyle_axe())

    txt = [
        f"Type = {d.type_deplaceur or 'N/A'}",
        f"Ø ext = {_fmt_mm(2.0 * Rext)}",
    ]
    if Rint > 0:
        txt.append(f"Ø int = {_fmt_mm(2.0 * Rint)}")
    if Rcyl > 0:
        txt.append(f"Ø cyl = {_fmt_mm(2.0 * Rcyl)}")
    if d.jeu_radial_um > 0:
        txt.append(f"Jeu radial = {_fmt_um(d.jeu_radial_um)}")

    lim = max(Rext, Rcyl, 1.0) + 24.0
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
# DÉTAIL RAINURES DE JOINTS
# ============================================================

def _tracer_detail_rainures(ax, d: DonneesCroquisDeplaceur):
    if not d.positions_axiales_rainures_mm or d.largeur_rainure_mm <= 0 or d.profondeur_rainure_mm <= 0:
        ax.text(0.5, 0.5, "Rainures de joints non disponibles", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Détail rainures")
        ax.set_axis_off()
        return

    L = d.longueur_totale_mm
    D = d.diametre_exterieur_mm
    y = D / 2.0 if D > 0 else 10.0
    rg_w = d.largeur_rainure_mm
    rg_h = d.profondeur_rainure_mm

    _add_hatched_rect(ax, 0.0, -y, L, 2.0 * y)
    ax.add_patch(Rectangle((0.0, -y), L, 2.0 * y, fill=False, linewidth=1.4))

    for xr in d.positions_axiales_rainures_mm:
        ax.add_patch(Rectangle((xr - 0.5 * rg_w, y - rg_h), rg_w, rg_h, fill=False, linewidth=1.1, linestyle="--"))
        ax.add_patch(Rectangle((xr - 0.5 * rg_w, -y), rg_w, rg_h, fill=False, linewidth=1.1, linestyle="--"))
        ax.axvline(xr, **_linestyle_hidden())

    # Cotes
    ydim1 = y + 12.0
    ydim2 = y + 24.0
    _add_dimension_h(ax, 0.0, L, 0.0, ydim1, f"L = {_fmt_mm(L)}")
    _add_dimension_h(ax, d.positions_axiales_rainures_mm[0] - 0.5 * rg_w, d.positions_axiales_rainures_mm[0] + 0.5 * rg_w, 0.0, ydim2, f"Largeur rainure = {_fmt_mm(rg_w)}")

    xdim = L + 18.0
    _add_dimension_v(ax, 0.0, xdim, y - rg_h, y, f"Prof. = {_fmt_mm(rg_h)}")

    txt = [
        f"Nb joints = {d.nb_joints}",
        f"Section joint = {d.section_joint_mm:.2f} mm" if d.section_joint_mm > 0 else "Section joint = N/A",
        f"Ø fond rainure = {_fmt_mm(d.diametre_fond_rainure_mm)}" if d.diametre_fond_rainure_mm > 0 else "Ø fond rainure = N/A",
        f"Rayon fond = {_fmt_mm(d.rayon_fond_rainure_mm)}" if d.rayon_fond_rainure_mm > 0 else "Rayon fond = N/A",
        f"Taux compression = {d.taux_compression:.3f}" if d.taux_compression > 0 else "Taux compression = N/A",
        f"Taux rempl. max = {d.taux_remplissage_max:.3f}" if d.taux_remplissage_max > 0 else "Taux rempl. max = N/A",
        f"Marge extrémité = {_fmt_mm(d.marge_extremite_rainure_mm)}" if d.marge_extremite_rainure_mm > 0 else "Marge extrémité = N/A",
        f"Entraxe min = {_fmt_mm(d.entraxe_min_rainure_mm)}" if d.entraxe_min_rainure_mm > 0 else "Entraxe min = N/A",
    ]

    ax.text(
        0.0,
        -(y + 26.0),
        "\n".join(txt),
        ha="left",
        va="top",
        fontsize=8.2,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Détail longitudinal des rainures de joints")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-15.0, L + 90.0)
    ax.set_ylim(-(y + 50.0), y + 38.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# SCHÉMA CHAUD / FROID
# ============================================================

def _tracer_schema_zones(ax, d: DonneesCroquisDeplaceur):
    Lcyl = d.cylindre_longueur_utile_mm
    if Lcyl <= 0 or d.position_face_froid_mm <= 0 or d.position_face_chaud_mm <= 0:
        ax.text(0.5, 0.5, "Volumes chaud/froid non disponibles", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Schéma zones")
        ax.set_axis_off()
        return

    H = 18.0
    ax.add_patch(Rectangle((0.0, 0.0), Lcyl, H, fill=False, linewidth=1.3))
    ax.add_patch(Rectangle((0.0, 0.0), d.position_face_froid_mm, H, fill=False, linewidth=1.0, linestyle=":"))
    ax.add_patch(Rectangle((d.position_face_froid_mm, 0.0), d.position_face_chaud_mm - d.position_face_froid_mm, H, fill=True, facecolor="white", edgecolor="black", linewidth=1.2, hatch="////"))
    ax.add_patch(Rectangle((d.position_face_chaud_mm, 0.0), Lcyl - d.position_face_chaud_mm, H, fill=False, linewidth=1.0, linestyle=":"))

    ax.text(0.5 * d.position_face_froid_mm, H / 2.0, "Froid", ha="center", va="center", fontsize=9)
    ax.text(0.5 * (d.position_face_froid_mm + d.position_face_chaud_mm), H / 2.0, "Déplaceur", ha="center", va="center", fontsize=9)
    ax.text(d.position_face_chaud_mm + 0.5 * (Lcyl - d.position_face_chaud_mm), H / 2.0, "Chaud", ha="center", va="center", fontsize=9)

    ydim = H + 10.0
    _add_dimension_h(ax, 0.0, d.position_face_froid_mm, 0.0, ydim, f"L froid = {_fmt_mm(d.longueur_zone_froide_mm)}")
    _add_dimension_h(ax, d.position_face_chaud_mm, Lcyl, 0.0, ydim + 14.0, f"L chaud = {_fmt_mm(d.longueur_zone_chaude_mm)}")

    txt = [
        f"V zone froide = {_fmt_m3(d.volume_zone_froide_m3) if d.volume_zone_froide_m3 > 0 else 'N/A'}",
        f"V zone chaude = {_fmt_m3(d.volume_zone_chaude_m3) if d.volume_zone_chaude_m3 > 0 else 'N/A'}",
        f"V total interne cyl = {_fmt_m3(d.volume_total_interne_cylindre_m3) if d.volume_total_interne_cylindre_m3 > 0 else 'N/A'}",
        f"V occupé déplaceur = {_fmt_m3(d.volume_occupe_par_deplaceur_m3) if d.volume_occupe_par_deplaceur_m3 > 0 else 'N/A'}",
        f"V libre total = {_fmt_m3(d.volume_libre_total_hors_deplaceur_m3) if d.volume_libre_total_hors_deplaceur_m3 > 0 else 'N/A'}",
    ]
    ax.text(
        0.0,
        -15.0,
        "\n".join(txt),
        ha="left",
        va="top",
        fontsize=8.1,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5),
    )

    ax.set_title("Répartition longitudinale chaud / froid")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-10.0, Lcyl + 10.0)
    ax.set_ylim(-48.0, H + 32.0)
    ax.grid(True, linestyle=":", linewidth=0.45)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")


# ============================================================
# CARTOUCHE TECHNIQUE
# ============================================================

def _ajouter_cartouche_technique(fig, d: DonneesCroquisDeplaceur):
    lines = [
        f"Type déplaceur              : {d.type_deplaceur or 'N/A'}",
        f"Ø ext déplaceur             : {_fmt_mm(d.diametre_exterieur_mm) if d.diametre_exterieur_mm > 0 else 'N/A'}",
        f"Ø int déplaceur             : {_fmt_mm(d.diametre_interieur_mm) if d.diametre_interieur_mm > 0 else 'N/A'}",
        f"L totale déplaceur          : {_fmt_mm(d.longueur_totale_mm) if d.longueur_totale_mm > 0 else 'N/A'}",
        f"Épaisseur paroi             : {_fmt_mm(d.epaisseur_paroi_mm) if d.epaisseur_paroi_mm > 0 else 'N/A'}",
        f"Aire face                   : {_fmt_m2(d.aire_face_m2) if d.aire_face_m2 > 0 else 'N/A'}",
        f"Section matière             : {_fmt_m2(d.section_matiere_m2) if d.section_matiere_m2 > 0 else 'N/A'}",
        f"Volume matière              : {_fmt_m3(d.volume_matiere_m3) if d.volume_matiere_m3 > 0 else 'N/A'}",
        f"Masse                       : {_fmt_kg(d.masse_kg) if d.masse_kg > 0 else 'N/A'}",
        f"Ø int cylindre              : {_fmt_mm(d.cylindre_diametre_interieur_mm) if d.cylindre_diametre_interieur_mm > 0 else 'N/A'}",
        f"Ø ext cylindre              : {_fmt_mm(d.cylindre_diametre_exterieur_mm) if d.cylindre_diametre_exterieur_mm > 0 else 'N/A'}",
        f"L utile cylindre            : {_fmt_mm(d.cylindre_longueur_utile_mm) if d.cylindre_longueur_utile_mm > 0 else 'N/A'}",
        f"Jeu radial                  : {_fmt_um(d.jeu_radial_um) if d.jeu_radial_um > 0 else 'N/A'}",
        f"Centre axial                : {_fmt_mm(d.position_axiale_centre_mm) if d.position_axiale_centre_mm > 0 else 'N/A'}",
        f"Face froide                 : {_fmt_mm(d.position_face_froid_mm) if d.position_face_froid_mm > 0 else 'N/A'}",
        f"Face chaude                 : {_fmt_mm(d.position_face_chaud_mm) if d.position_face_chaud_mm > 0 else 'N/A'}",
        f"Centre min                  : {_fmt_mm(d.position_min_centre_mm) if d.position_min_centre_mm > 0 else 'N/A'}",
        f"Centre max                  : {_fmt_mm(d.position_max_centre_mm) if d.position_max_centre_mm > 0 else 'N/A'}",
        f"Position normalisée         : {f'{d.position_normalisee:.6f}' if d.position_normalisee > 0 else 'N/A'}",
        f"Course dispo                : {_fmt_mm(d.course_disponible_mm) if d.course_disponible_mm > 0 else 'N/A'}",
        f"Course géométrique max      : {_fmt_mm(d.course_geometrique_max_mm) if d.course_geometrique_max_mm > 0 else 'N/A'}",
        f"L zone froide               : {_fmt_mm(d.longueur_zone_froide_mm) if d.longueur_zone_froide_mm > 0 else 'N/A'}",
        f"L zone chaude               : {_fmt_mm(d.longueur_zone_chaude_mm) if d.longueur_zone_chaude_mm > 0 else 'N/A'}",
        f"V zone froide               : {_fmt_m3(d.volume_zone_froide_m3) if d.volume_zone_froide_m3 > 0 else 'N/A'}",
        f"V zone chaude               : {_fmt_m3(d.volume_zone_chaude_m3) if d.volume_zone_chaude_m3 > 0 else 'N/A'}",
        f"V total cylindre            : {_fmt_m3(d.volume_total_interne_cylindre_m3) if d.volume_total_interne_cylindre_m3 > 0 else 'N/A'}",
        f"V occupé par déplaceur      : {_fmt_m3(d.volume_occupe_par_deplaceur_m3) if d.volume_occupe_par_deplaceur_m3 > 0 else 'N/A'}",
        f"V libre total               : {_fmt_m3(d.volume_libre_total_hors_deplaceur_m3) if d.volume_libre_total_hors_deplaceur_m3 > 0 else 'N/A'}",
        f"P chaud                     : {_fmt_pa(d.pression_chaud_pa) if d.pression_chaud_pa != 0 else 'N/A'}",
        f"P froid                     : {_fmt_pa(d.pression_froid_pa) if d.pression_froid_pa != 0 else 'N/A'}",
        f"Δp                          : {_fmt_pa(d.delta_p_pa) if d.delta_p_pa != 0 else 'N/A'}",
        f"Force axiale                : {_fmt_n(d.force_axiale_N) if d.force_axiale_N != 0 else 'N/A'}",
        f"Surface effective           : {_fmt_m2(d.surface_effective_m2) if d.surface_effective_m2 > 0 else 'N/A'}",
        f"T chaud                     : {f'{d.temperature_chaud_C:.2f} °C' if d.temperature_chaud_C != 0 else 'N/A'}",
        f"T froid                     : {f'{d.temperature_froid_C:.2f} °C' if d.temperature_froid_C != 0 else 'N/A'}",
        f"Déformation axiale          : {f'{d.deformation_axiale:.6e}' if d.deformation_axiale != 0 else 'N/A'}",
        f"Allongement                 : {_fmt_um(d.allongement_um) if d.allongement_um != 0 else 'N/A'}",
        f"Augmentation rayon          : {_fmt_um(d.augmentation_rayon_um) if d.augmentation_rayon_um != 0 else 'N/A'}",
        f"Jeu résiduel                : {_fmt_um(d.jeu_residuel_um) if d.jeu_residuel_um != 0 else 'N/A'}",
        f"Flambage Euler              : {_fmt_n(d.flambage_euler_N) if d.flambage_euler_N > 0 else 'N/A'}",
        f"Marge flambage              : {f'{d.marge_flambage:.6f}' if d.marge_flambage > 0 else 'N/A'}",
        f"Perte charge orifice        : {_fmt_pa(d.perte_charge_orifice_pa) if d.perte_charge_orifice_pa > 0 else 'N/A'}",
        f"rho gaz utilisé             : {f'{d.rho_gaz_utilise_kg_m3:.6f} kg/m³' if d.rho_gaz_utilise_kg_m3 > 0 else 'N/A'}",
        f"Nb joints                   : {d.nb_joints if d.nb_joints > 0 else 'N/A'}",
        f"Section joint               : {f'{d.section_joint_mm:.2f} mm' if d.section_joint_mm > 0 else 'N/A'}",
        f"Largeur rainure             : {_fmt_mm(d.largeur_rainure_mm) if d.largeur_rainure_mm > 0 else 'N/A'}",
        f"Profondeur rainure          : {_fmt_mm(d.profondeur_rainure_mm) if d.profondeur_rainure_mm > 0 else 'N/A'}",
        f"Ø fond rainure              : {_fmt_mm(d.diametre_fond_rainure_mm) if d.diametre_fond_rainure_mm > 0 else 'N/A'}",
        f"Rayon fond rainure          : {_fmt_mm(d.rayon_fond_rainure_mm) if d.rayon_fond_rainure_mm > 0 else 'N/A'}",
        f"Taux compression            : {f'{d.taux_compression:.6f}' if d.taux_compression > 0 else 'N/A'}",
        f"Taux remplissage max        : {f'{d.taux_remplissage_max:.6f}' if d.taux_remplissage_max > 0 else 'N/A'}",
        f"Marge extrémité rainure     : {_fmt_mm(d.marge_extremite_rainure_mm) if d.marge_extremite_rainure_mm > 0 else 'N/A'}",
        f"Entraxe min rainure         : {_fmt_mm(d.entraxe_min_rainure_mm) if d.entraxe_min_rainure_mm > 0 else 'N/A'}",
        f"Chanfrein extrémités        : {_fmt_mm(d.chanfrein_extremites_mm) if d.chanfrein_extremites_mm > 0 else 'N/A'}",
        f"Rayon congé                 : {_fmt_mm(d.rayon_conge_mm) if d.rayon_conge_mm > 0 else 'N/A'}",
        f"Ra extérieure               : {f'{d.rugosite_exterieure_ra_um:.2f} µm' if d.rugosite_exterieure_ra_um > 0 else 'N/A'}",
        f"Ra faces                    : {f'{d.rugosite_faces_ra_um:.2f} µm' if d.rugosite_faces_ra_um > 0 else 'N/A'}",
        f"Tol. Ø extérieur            : {_fmt_um(d.tolerance_diametre_exterieur_um) if d.tolerance_diametre_exterieur_um > 0 else 'N/A'}",
        f"Tol. longueur               : {_fmt_um(d.tolerance_longueur_um) if d.tolerance_longueur_um > 0 else 'N/A'}",
        f"Tol. position               : {_fmt_um(d.tolerance_position_um) if d.tolerance_position_um > 0 else 'N/A'}",
        f"Compatibilité alésage       : {d.compatible_alesage if d.compatible_alesage is not None else 'N/A'}",
        f"Compatibilité longueur      : {d.compatible_longueur if d.compatible_longueur is not None else 'N/A'}",
        f"Position dans course        : {d.position_dans_course if d.position_dans_course is not None else 'N/A'}",
    ]

    if d.positions_axiales_rainures_mm:
        lines.append("Positions rainures           : " + ", ".join(f"{v:.2f} mm" for v in d.positions_axiales_rainures_mm))

    fig.text(
        0.012,
        0.015,
        "DONNÉES EXTRAITES DE Deplaceur.analyser()\n" + "\n".join(lines),
        ha="left",
        va="bottom",
        fontsize=7.75,
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="black", linewidth=0.9),
    )


# ============================================================
# FONCTION PRINCIPALE
# ============================================================

def tracer_croquis_deplaceur_2d(
    deplaceur: Deplaceur,
    *,
    afficher: bool = True,
    enregistrer: Optional[str] = None,
    titre: str = "Croquis 2D détaillé - Déplaceur",
):
    d = extraire_donnees_croquis(deplaceur)

    if d.diametre_exterieur_mm <= 0 or d.longueur_totale_mm <= 0:
        raise ValueError("Impossible de tracer : dimensions principales du déplaceur absentes.")

    fig = plt.figure(figsize=(19, 11))
    gs = fig.add_gridspec(2, 3, height_ratios=[2.15, 1.35], width_ratios=[1.55, 1.0, 1.1])

    ax_side = fig.add_subplot(gs[0, :])
    ax_front = fig.add_subplot(gs[1, 0])
    ax_rain = fig.add_subplot(gs[1, 1])
    ax_zone = fig.add_subplot(gs[1, 2])

    fig.suptitle(titre, fontsize=15, y=0.985)

    _tracer_vue_cote(ax_side, d)
    _tracer_vue_face(ax_front, d)
    _tracer_detail_rainures(ax_rain, d)
    _tracer_schema_zones(ax_zone, d)

    _ajouter_cartouche_technique(fig, d)

    plt.tight_layout(rect=[0.0, 0.12, 1.0, 0.965])

    if enregistrer:
        plt.savefig(enregistrer, dpi=220, bbox_inches="tight")

    if afficher:
        plt.show()

    return fig, {
        "vue_cote": ax_side,
        "vue_face": ax_front,
        "detail_rainures": ax_rain,
        "schema_zones": ax_zone,
    }, d


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

if __name__ == "__main__":
    dep = Deplaceur(
        diametre_exterieur_m=0.070,
        longueur_totale_m=0.090,
        course_disponible_m=0.040,
        jeu_radial_m=0.0002,
        mode_position="centre",
        volume_mort_chaud_m3=2.0e-5,
        volume_mort_froid_m3=2.0e-5,
        pression_chaud_pa=4.0e5,
        pression_froid_pa=2.0e5,
        temperature_chaud_C=350.0,
        temperature_froid_C=40.0,
        materiau_cle=None,
        densite_kg_m3=7800.0,
        module_young_pa=210e9,
        limite_elastique_pa=350e6,
        type_deplaceur="tubulaire",
        standard_joint="ISO_3601",
        section_joint_mm=3.0,
        taux_compression_joint=0.20,
        nb_joints=2,
        orifice_aire_m2=1.5e-4,
        orifice_coeff_decharge=0.65,
        debit_gaz_m3_s=0.003,
        rho_gaz_kg_m3=1.2,
        longueur_libre_flambe_m=0.090,
        coeff_k_flambe=1.0,
    )

    tracer_croquis_deplaceur_2d(
        dep,
        afficher=True,
        enregistrer=None,
        titre="Croquis 2D détaillé - Déplaceur calculé",
    )