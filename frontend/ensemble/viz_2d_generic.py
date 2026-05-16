from __future__ import annotations

from typing import Any, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle


def _get_value(obj: Any, *keys: str) -> Any:
    for key in keys:
        try:
            value = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
        except Exception:
            value = None
        if value is not None:
            return value
    return None


def _safe_float(obj: Any, *keys: str) -> float | None:
    value = _get_value(obj, *keys)
    try:
        if value is None:
            return None
        out = float(value)
        return out
    except Exception:
        return None


def _candidate_metrics(piece: Any) -> List[Tuple[str, str]]:
    metrics: List[Tuple[str, str]] = []

    diameter = _safe_float(piece, "diametre_arbre_m", "diametre_m", "diametre_nominal_m", "alesage_m")
    if diameter and diameter > 0:
        metrics.append(("Diametre", f"{diameter * 1000:.1f} mm"))

    length = _safe_float(piece, "longueur_totale_m", "longueur_m", "hauteur_m", "course_m", "longueur_bielle_m")
    if length and length > 0:
        metrics.append(("Longueur", f"{length * 1000:.1f} mm"))

    torque = _safe_float(piece, "couple_max_Nm", "couple_transmis_Nm", "couple_nominal_Nm")
    if torque and torque > 0:
        metrics.append(("Couple", f"{torque:.1f} Nm"))

    rpm = _safe_float(piece, "rpm", "rpm_nominal", "regime_rpm", "regime_max_rpm")
    if rpm and rpm > 0:
        metrics.append(("Regime", f"{rpm:.0f} rpm"))

    power = _safe_float(piece, "puissance_bus_dc_W", "puissance_max_w", "puissance_nominale_w")
    if power and power > 0:
        metrics.append(("Puissance", f"{power / 1000:.1f} kW"))

    fs = _safe_float(piece, "facteur_securite", "facteur_securite_cylindre")
    if fs and fs > 0:
        metrics.append(("Securite", f"{fs:.2f}"))

    return metrics[:6]


def draw(ax, piece: Any) -> None:
    ax.set_aspect("equal")
    ax.axis("off")

    width = 0.62
    height = 0.24
    x0 = 0.19
    y0 = 0.38

    ax.add_patch(Rectangle((x0, y0), width, height, fill=False, linewidth=2.0, edgecolor="#091226"))
    ax.add_patch(Circle((x0 + 0.11, y0 + height / 2.0), 0.055, fill=False, linewidth=1.5, edgecolor="#3E5349"))
    ax.add_patch(Circle((x0 + width - 0.11, y0 + height / 2.0), 0.055, fill=False, linewidth=1.5, edgecolor="#3E5349"))
    ax.plot([x0, x0 + width], [y0 + height / 2.0, y0 + height / 2.0], linestyle="--", linewidth=1.0, color="#0A0B0A")

    ax.add_patch(FancyArrowPatch((x0, y0 + height + 0.08), (x0 + width, y0 + height + 0.08), arrowstyle="<->", mutation_scale=12, linewidth=1.2))
    ax.text(x0 + width / 2.0, y0 + height + 0.11, "Longueur utile", ha="center", va="bottom", fontsize=9, color="#091226")

    ax.add_patch(FancyArrowPatch((x0 + width + 0.08, y0), (x0 + width + 0.08, y0 + height), arrowstyle="<->", mutation_scale=12, linewidth=1.2))
    ax.text(x0 + width + 0.11, y0 + height / 2.0, "Section", ha="left", va="center", rotation=90, fontsize=9, color="#091226")

    name = _get_value(piece, "nom", "piece", "type") or "Element"
    ax.text(0.5, 0.78, str(name).replace("_", " ").upper(), ha="center", va="center", fontsize=14, fontweight="bold", color="#091226")
    ax.text(0.5, 0.72, "Vue technique generique", ha="center", va="center", fontsize=10, color="#3E5349")

    metrics = _candidate_metrics(piece)
    if metrics:
        lines = [f"{label}: {value}" for label, value in metrics]
        ax.text(
            0.08,
            0.22,
            "\n".join(lines),
            ha="left",
            va="top",
            fontsize=9,
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#0A0B0A"),
            color="#091226",
        )
    else:
        ax.text(
            0.5,
            0.20,
            "Geometrie detaillee indisponible.\nAffichage de secours base sur les donnees presentes.",
            ha="center",
            va="top",
            fontsize=9,
            color="#3E5349",
        )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def make_figure(piece: Any):
    fig, ax = plt.subplots(figsize=(6.4, 6.0))
    draw(ax, piece)
    return fig
