from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import textwrap

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from frontend.gui.components import PALETTE
from frontend.gui.viz_utils import get_viz_figure


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _status_from_payload(payload: Dict[str, Any]) -> Tuple[str, str]:
    data = _safe_dict(payload)
    if not data:
        return "A calculer", "Aucune donnee backend disponible."

    construit = bool(data.get("construit"))
    rapport = _safe_dict(data.get("rapport"))
    rapport_disponible = bool(data.get("rapport_disponible")) or (
        rapport and "note" not in rapport and "erreur" not in rapport
    )
    if construit and rapport_disponible:
        return "Calculee", "Element construit avec rapport exploitable."
    if construit:
        return "Partielle", str(rapport.get("note") or "Element construit avec retour partiel.")
    return "Non construite", "Donnees insuffisantes pour finaliser cet element."


def _human_label(value: Any) -> str:
    return str(value).replace("_", " ").strip().capitalize()


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, dict):
        return all(_is_empty_value(v) for v in value.values())
    return False


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            fv = float(value)
        except Exception:
            return str(value)
        if fv == 0:
            return "0"
        if abs(fv) >= 1e6 or abs(fv) < 1e-3:
            return f"{fv:.3e}"
        return f"{fv:.6g}"
    if isinstance(value, (list, tuple)):
        if all(not isinstance(item, (dict, list, tuple)) for item in value[:8]):
            return ", ".join(_format_value(item) for item in value[:8])
        return f"[{len(value)} elements]"
    return str(value)


def _iter_curated_rows(
    data: Dict[str, Any],
    prefix: str = "",
    depth: int = 0,
    max_depth: int = 2,
) -> Iterable[Tuple[str, str]]:
    if depth > max_depth or not isinstance(data, dict):
        return
    for key, value in sorted(data.items(), key=lambda item: str(item[0])):
        if key in {"objet", "objet_serialise", "rapport", "rapports", "inventaire", "construction", "kwargs"}:
            continue
        label = f"{prefix}{_human_label(key)}"
        if isinstance(value, dict):
            if _is_empty_value(value):
                continue
            yield from _iter_curated_rows(value, f"{label} > ", depth + 1, max_depth=max_depth)
            continue
        if _is_empty_value(value):
            continue
        yield label, _format_value(value)


def _append_section(
    sections: List[Tuple[str, List[Tuple[str, str]]]],
    title: str,
    rows: Iterable[Tuple[str, str]],
) -> None:
    clean_rows = [(key, value) for key, value in rows if value not in ("", "-", "[]")]
    if clean_rows:
        sections.append((title, clean_rows))


def _format_unknown_entry(value: Any) -> str:
    if isinstance(value, dict):
        name = str(value.get("nom") or "").strip()
        reason = str(value.get("raison") or "").strip()
        if name and reason:
            return f"{name}: {reason}"
        if name:
            return name
        if reason:
            return reason
    return str(value)


def build_element_display_sections(payload: Optional[Dict[str, Any]]) -> List[Tuple[str, List[Tuple[str, str]]]]:
    data = _safe_dict(payload)
    report = _safe_dict(data.get("rapport"))
    inventory = _safe_dict(data.get("inventaire"))
    construction = _safe_dict(data.get("construction"))
    sections: List[Tuple[str, List[Tuple[str, str]]]] = []

    meta_rows: List[Tuple[str, str]] = []
    for key in ("type", "source_composant"):
        if not _is_empty_value(data.get(key)):
            meta_rows.append((_human_label(key), _format_value(data.get(key))))
        elif not _is_empty_value(inventory.get(key)):
            meta_rows.append((_human_label(key), _format_value(inventory.get(key))))
    status, detail = _status_from_payload(data)
    meta_rows.append(("Etat backend", status))
    meta_rows.append(("Detail", detail))
    if not _is_empty_value(construction.get("construit")):
        meta_rows.append(("Construit", _format_value(construction.get("construit"))))
    _append_section(sections, "Synthese", meta_rows)

    preferred_sections = [
        ("entrees", "Entrees calculees"),
        ("dimensionnements", "Dimensionnements"),
        ("performances", "Performances"),
        ("contraintes", "Contraintes"),
        ("interfaces", "Interfaces"),
        ("longueur", "Longueurs"),
        ("clavette", "Clavette"),
        ("masses", "Masses"),
        ("cao", "CAO"),
        ("materiau", "Materiaux"),
        ("recuperations", "Sources recuperees"),
    ]
    for key, title in preferred_sections:
        _append_section(sections, title, _iter_curated_rows(_safe_dict(report.get(key)), max_depth=2))

    inconnues = _safe_dict(report.get("inconnues"))
    if inconnues:
        rows: List[Tuple[str, str]] = []
        impossibles = [_format_unknown_entry(item) for item in inconnues.get("impossibles", []) if str(item).strip()]
        partielles = [_format_unknown_entry(item) for item in inconnues.get("partielles", []) if str(item).strip()]
        for idx, item in enumerate(impossibles[:6], start=1):
            rows.append((f"Bloquante {idx}", item))
        if len(impossibles) > 6:
            rows.append(("Bloquantes restantes", str(len(impossibles) - 6)))
        for idx, item in enumerate(partielles[:6], start=1):
            rows.append((f"Partielle {idx}", item))
        if len(partielles) > 6:
            rows.append(("Partielles restantes", str(len(partielles) - 6)))
        _append_section(sections, "Inconnues", rows)

    notes = [str(item) for item in report.get("notes_modele", []) if str(item).strip()]
    if notes:
        _append_section(sections, "Notes", [("Modele", note) for note in notes[:8]])

    return sections


def build_element_display_lines(payload: Optional[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for title, rows in build_element_display_sections(payload):
        lines.append(f"[{title}]")
        for key, value in rows:
            lines.append(f"{key}: {value}")
        lines.append("")
    return lines or ["Aucune donnee calculee disponible."]


def _text_page(pdf: PdfPages, title: str, lines: List[str], *, footer: Optional[str] = None) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(PALETTE["BLANC_LUNAIRE"])
    fig.text(0.06, 0.965, title, fontsize=16, fontweight="bold", color=PALETTE["BLEU_FRANCE_WEB"], va="top")
    if footer:
        fig.text(0.06, 0.03, footer, fontsize=8, color=PALETTE["NATURAL_GREEN"], va="bottom")

    wrapped: List[str] = []
    for line in lines:
        wrapped.extend(textwrap.wrap(line, width=105) or [""])

    page_size = 46
    chunk = wrapped[:page_size]
    y = 0.93
    for line in chunk:
        fig.text(0.06, y, line, fontsize=9, family="monospace", color=PALETTE["GRIGIO_SCURO"], va="top")
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
        summary_lines.extend(build_element_display_lines(data))
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
                    [f"Aucune vue disponible pour {label.lower()} avec les donnees actuelles."],
                    footer=str(output),
                )

        _text_page(pdf, f"{display_name} - Donnees detaillees", build_element_display_lines(data), footer=str(output))

    return output
