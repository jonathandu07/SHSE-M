from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import textwrap

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from frontend.gui.viz_utils import get_viz_figure


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _flatten_mapping(data: Any, prefix: str = "", depth: int = 0, max_depth: int = 5) -> Iterable[Tuple[str, str]]:
    if depth > max_depth or not isinstance(data, dict):
        return
    for key, value in sorted(data.items(), key=lambda item: str(item[0])):
        label = f"{prefix}{str(key)}"
        if isinstance(value, dict):
            yield from _flatten_mapping(value, f"{label} > ", depth + 1, max_depth=max_depth)
        elif isinstance(value, (list, tuple)):
            if not value:
                yield label, "[]"
            elif all(not isinstance(item, (dict, list, tuple)) for item in value[:8]):
                yield label, ", ".join(str(item) for item in value[:8])
            else:
                yield label, f"[{len(value)} elements]"
        elif value is None:
            yield label, "-"
        else:
            yield label, str(value)


def _status_from_payload(payload: Dict[str, Any]) -> Tuple[str, str]:
    data = _safe_dict(payload)
    if not data:
        return "A calculer", "Aucune donnée backend disponible."

    construit = bool(data.get("construit"))
    rapport = _safe_dict(data.get("rapport"))
    rapport_disponible = bool(data.get("rapport_disponible")) or (rapport and "note" not in rapport and "erreur" not in rapport)
    if construit and rapport_disponible:
        return "Calculee", "Element construit avec rapport exploitable."
    if construit:
        return "Partielle", str(rapport.get("note") or "Element construit avec retour partiel.")
    return "Non construite", "Donnees insuffisantes pour finaliser cet element."


def _text_page(pdf: PdfPages, title: str, lines: List[str], *, footer: Optional[str] = None) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    fig.text(0.06, 0.965, title, fontsize=16, fontweight="bold", va="top")
    if footer:
        fig.text(0.06, 0.03, footer, fontsize=8, color="#666666", va="bottom")

    wrapped: List[str] = []
    for line in lines:
        wrapped.extend(textwrap.wrap(line, width=105) or [""])

    page_size = 46
    chunk = wrapped[:page_size]
    y = 0.93
    for line in chunk:
        fig.text(0.06, y, line, fontsize=9, family="monospace", va="top")
        y -= 0.019

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

    if len(wrapped) > page_size:
        _text_page(pdf, f"{title} (suite)", wrapped[page_size:], footer=footer)


def _figure_page(pdf: PdfPages, fig: Any, title: str) -> None:
    try:
        if hasattr(fig, "suptitle"):
            fig.suptitle(title)
        pdf.savefig(fig, bbox_inches="tight")
    finally:
        plt.close(fig)


def _build_data_lines(payload: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for key, value in _flatten_mapping(payload):
        lines.append(f"{key}: {value}")
    return lines or ["Aucune donnée calculée disponible."]


def export_element_pdf(
    *,
    element_name: str,
    display_name: str,
    payload: Optional[Dict[str, Any]],
    element_obj: Any,
    output_path: str | Path,
    is_component: bool = False,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = _safe_dict(payload)
    status, detail = _status_from_payload(data)

    with PdfPages(output) as pdf:
        summary_lines = [
            f"Element: {display_name}",
            f"Nom technique: {element_name}",
            f"Type: {'composant' if is_component else 'piece'}",
            f"Etat backend: {status}",
            f"Detail: {detail}",
            "",
        ]
        summary_lines.extend(_build_data_lines({
            "inventaire": data.get("inventaire"),
            "construction": data.get("construction"),
            "rapport": data.get("rapport"),
            "rapports": data.get("rapports"),
        }))
        _text_page(pdf, f"Fiche technique - {display_name}", summary_lines, footer=str(output))

        for viz_type, label in (
            ("sketches_2d", "Vue 2D / Croquis"),
            ("views_3d", "Vue 3D"),
            ("charts", "Graphiques"),
        ):
            fig = None
            if element_obj is not None:
                try:
                    fig = get_viz_figure(element_name, element_obj, viz_type)
                except Exception:
                    fig = None
            if fig is not None:
                _figure_page(pdf, fig, f"{display_name} - {label}")
            else:
                _text_page(
                    pdf,
                    f"{display_name} - {label}",
                    [f"Aucune vue disponible pour {label.lower()} avec les données actuelles."],
                    footer=str(output),
                )

        _text_page(pdf, f"{display_name} - Donnees detaillees", _build_data_lines(data), footer=str(output))

    return output
