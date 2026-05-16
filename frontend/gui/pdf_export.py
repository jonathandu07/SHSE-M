# frontend/gui/pdf_export.py
from __future__ import annotations

import json
import math
import textwrap
import traceback
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from frontend.gui.components import PALETTE

try:
    from frontend.gui.viz_utils import get_viz_figure
except Exception:  # pragma: no cover
    get_viz_figure = None  # type: ignore


# =============================================================================
# Types
# =============================================================================

Row = Tuple[str, str]
Section = Tuple[str, List[Row]]


# =============================================================================
# Constantes PDF / thème
# =============================================================================

A4_FIGSIZE = (8.27, 11.69)

MARGIN_X = 0.065
TOP_Y = 0.955
BOTTOM_Y = 0.052

TITLE_SIZE = 16
SUBTITLE_SIZE = 10
BODY_SIZE = 8.6
SMALL_SIZE = 7.4

LINE_HEIGHT = 0.0185
SECTION_GAP = 0.012
ROW_GAP = 0.002

WRAP_WIDTH_TITLE = 78
WRAP_WIDTH_KEY = 28
WRAP_WIDTH_VALUE = 82
WRAP_WIDTH_FULL = 112

MAX_ROWS_PER_SECTION_PREVIEW = 80
MAX_UNKNOWN_PREVIEW = 20
MAX_NOTE_PREVIEW = 20
MAX_NESTED_DEPTH = 4
MAX_JSON_DEPTH = 8

COLOR_BG = PALETTE.get("BLANC_LUNAIRE", "#F4FEFE")
COLOR_MAIN = PALETTE.get("BLEU_FRANCE_WEB", "#091226")
COLOR_ACCENT = PALETTE.get("ROUGE_SPARTE", "#75161E")
COLOR_TEXT = PALETTE.get("GRIGIO_SCURO", "#0A0B0A")
COLOR_MUTED = PALETTE.get("NATURAL_GREEN", "#3E5349")


# =============================================================================
# Helpers généraux
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _deep_get(data: Any, *path: str) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _human_label(value: Any) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ").strip()
    if not text:
        return "Champ"
    return " ".join(part.capitalize() for part in text.split())


def _slug(value: Any) -> str:
    raw = str(value or "export").strip().lower()
    out = []
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "_".join(part for part in "".join(out).split("_") if part) or "export"


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, Mapping):
        return all(_is_empty_value(v) for v in value.values())
    return False


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = MAX_JSON_DEPTH) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

    if is_dataclass(value):
        try:
            return _jsonable(asdict(value), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass

    if isinstance(value, Mapping):
        return {
            str(k): _jsonable(v, depth=depth + 1, max_depth=max_depth)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [
            _jsonable(v, depth=depth + 1, max_depth=max_depth)
            for v in value
        ]

    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            public_attrs = {
                key: val
                for key, val in vars(value).items()
                if not key.startswith("_") and not callable(val)
            }
            if public_attrs:
                return {
                    "type": type(value).__name__,
                    "attributs": _jsonable(public_attrs, depth=depth + 1, max_depth=max_depth),
                }
        except Exception:
            pass

    return str(value)


def _format_value(value: Any) -> str:
    if value is None:
        return "—"

    if isinstance(value, bool):
        return "Oui" if value else "Non"

    if _is_finite(value):
        fv = float(value)
        if fv == 0.0:
            return "0"
        if abs(fv) >= 1e6 or abs(fv) < 1e-3:
            return f"{fv:.4e}"
        return f"{fv:.6g}"

    if isinstance(value, Mapping):
        if not value:
            return "{}"
        return f"{{{len(value)} champs}}"

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if not items:
            return "[]"
        if all(not isinstance(item, (dict, list, tuple, set)) for item in items[:8]):
            suffix = "" if len(items) <= 8 else f", ... (+{len(items) - 8})"
            return ", ".join(_format_value(item) for item in items[:8]) + suffix
        return f"[{len(items)} éléments]"

    return str(value)


def _count_unknowns(data: Any) -> int:
    total = 0

    def walk(node: Any) -> None:
        nonlocal total

        if isinstance(node, Mapping):
            inc = node.get("inconnues")
            if isinstance(inc, Mapping):
                for values in inc.values():
                    if isinstance(values, list):
                        total += len(values)

            inconnues_cao = node.get("inconnues_cao")
            if isinstance(inconnues_cao, list):
                total += len(inconnues_cao)

            for child in node.values():
                if isinstance(child, (Mapping, list)):
                    walk(child)

        elif isinstance(node, list):
            for child in node:
                if isinstance(child, (Mapping, list)):
                    walk(child)

    walk(data)
    return total


def _count_alerts(data: Any) -> int:
    total = 0

    def walk(node: Any) -> None:
        nonlocal total

        if isinstance(node, Mapping):
            alerts = node.get("alertes")
            if isinstance(alerts, Mapping):
                for values in alerts.values():
                    if isinstance(values, list):
                        total += len(values)

            for child in node.values():
                if isinstance(child, (Mapping, list)):
                    walk(child)

        elif isinstance(node, list):
            for child in node:
                if isinstance(child, (Mapping, list)):
                    walk(child)

    walk(data)
    return total


# =============================================================================
# Statut backend
# =============================================================================

def _status_from_payload(payload: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    data = _safe_dict(payload)

    if not data:
        return "À calculer", "Aucune donnée backend disponible."

    if data.get("erreur"):
        return "Erreur", str(data.get("erreur"))

    construit = bool(data.get("construit"))
    rapport = _safe_dict(data.get("rapport"))

    rapport_disponible = bool(data.get("rapport_disponible")) or (
        bool(rapport)
        and "note" not in rapport
        and "erreur" not in rapport
    )

    if construit and rapport_disponible:
        return "Calculée", "Élément construit avec rapport exploitable."

    if rapport_disponible:
        return "Rapport disponible", "Rapport exploitable, construction non explicitement confirmée."

    if construit:
        return "Partielle", str(rapport.get("note") or "Élément construit avec retour partiel.")

    if rapport.get("erreur"):
        return "Erreur", str(rapport.get("erreur"))

    if rapport.get("note"):
        return "Partielle", str(rapport.get("note"))

    return "Non construite", "Données insuffisantes pour finaliser cet élément."


def _status_color(status: str) -> str:
    low = status.lower()
    if "erreur" in low or "non" in low or "à calculer" in low:
        return COLOR_ACCENT
    if "part" in low:
        return COLOR_MUTED
    return COLOR_MAIN


# =============================================================================
# Extraction sections
# =============================================================================

SKIP_KEYS = {
    "objet",
    "objet_serialise",
    "rapport",
    "rapports",
    "inventaire",
    "construction",
    "kwargs",
    "raw",
    "trace",
    "traceback",
}


def _iter_curated_rows(
    data: Mapping[str, Any],
    prefix: str = "",
    depth: int = 0,
    max_depth: int = MAX_NESTED_DEPTH,
) -> Iterator[Row]:
    if depth > max_depth:
        return

    for key, value in sorted(data.items(), key=lambda item: str(item[0])):
        key_str = str(key)

        if key_str in SKIP_KEYS:
            continue

        if _is_empty_value(value):
            continue

        label = f"{prefix}{_human_label(key_str)}"

        if isinstance(value, Mapping):
            yield from _iter_curated_rows(value, f"{label} > ", depth + 1, max_depth=max_depth)
            continue

        yield label, _format_value(value)


def _append_section(sections: List[Section], title: str, rows: Iterable[Row]) -> None:
    clean: List[Row] = []

    for key, value in rows:
        if value in ("", "-", "[]", "{}", "None"):
            continue
        clean.append((str(key), str(value)))

    if clean:
        sections.append((title, clean))


def _format_unknown_entry(value: Any) -> str:
    if isinstance(value, Mapping):
        name = str(
            _first_non_empty(
                value.get("nom"),
                value.get("name"),
                value.get("champ"),
                value.get("key"),
                value.get("piece"),
                "",
            )
        ).strip()

        reason = str(
            _first_non_empty(
                value.get("raison"),
                value.get("reason"),
                value.get("detail"),
                value.get("message"),
                value.get("erreur"),
                "",
            )
        ).strip()

        if name and reason:
            return f"{name}: {reason}"
        if name:
            return name
        if reason:
            return reason

    return str(value)


def _flatten_inconnues(data: Mapping[str, Any]) -> List[Row]:
    rows: List[Row] = []

    inc = _safe_dict(data.get("inconnues"))
    for category in ("impossibles", "partielles", "cao"):
        values = _safe_list(inc.get(category))
        for idx, item in enumerate(values[:MAX_UNKNOWN_PREVIEW], start=1):
            rows.append((f"{_human_label(category)} {idx}", _format_unknown_entry(item)))
        if len(values) > MAX_UNKNOWN_PREVIEW:
            rows.append((f"{_human_label(category)} restantes", str(len(values) - MAX_UNKNOWN_PREVIEW)))

    inconnues_cao = _safe_list(data.get("inconnues_cao"))
    for idx, item in enumerate(inconnues_cao[:MAX_UNKNOWN_PREVIEW], start=1):
        rows.append((f"CAO {idx}", _format_unknown_entry(item)))
    if len(inconnues_cao) > MAX_UNKNOWN_PREVIEW:
        rows.append(("CAO restantes", str(len(inconnues_cao) - MAX_UNKNOWN_PREVIEW)))

    return rows


def _flatten_alertes(data: Mapping[str, Any]) -> List[Row]:
    rows: List[Row] = []
    alerts = _safe_dict(data.get("alertes"))

    for category, values in alerts.items():
        for idx, item in enumerate(_safe_list(values)[:MAX_UNKNOWN_PREVIEW], start=1):
            rows.append((f"{_human_label(category)} {idx}", _format_unknown_entry(item)))

    return rows


def build_element_display_sections(payload: Optional[Dict[str, Any]]) -> List[Section]:
    data = _safe_dict(payload)
    report = _safe_dict(data.get("rapport"))
    inventory = _safe_dict(data.get("inventaire"))
    construction = _safe_dict(data.get("construction"))
    sections: List[Section] = []

    status, detail = _status_from_payload(data)

    meta_rows: List[Row] = [
        ("État backend", status),
        ("Détail", detail),
    ]

    for key in ("type", "source_composant", "nom", "name", "famille"):
        value = _first_non_empty(data.get(key), inventory.get(key), report.get(key))
        if not _is_empty_value(value):
            meta_rows.append((_human_label(key), _format_value(value)))

    if not _is_empty_value(construction.get("construit")):
        meta_rows.append(("Construit", _format_value(construction.get("construit"))))

    meta_rows.append(("Inconnues détectées", str(_count_unknowns(data))))
    meta_rows.append(("Alertes détectées", str(_count_alerts(data))))

    _append_section(sections, "Synthèse", meta_rows)

    preferred_sections = [
        ("entrees", "Entrées calculées"),
        ("entrees_normalisees", "Entrées normalisées"),
        ("dimensionnement", "Dimensionnement"),
        ("dimensionnements", "Dimensionnements"),
        ("geometrie", "Géométrie"),
        ("dimensions", "Dimensions"),
        ("performances", "Performances"),
        ("contraintes", "Contraintes"),
        ("efforts", "Efforts"),
        ("cinematique", "Cinématique"),
        ("thermique", "Thermique"),
        ("interfaces", "Interfaces"),
        ("assemblage", "Assemblage"),
        ("etancheite", "Étanchéité"),
        ("frottement", "Frottement"),
        ("frottements", "Frottements"),
        ("masses", "Masses"),
        ("materiau", "Matériaux"),
        ("cao", "CAO"),
        ("fabrication", "Fabrication"),
        ("recuperations", "Sources récupérées"),
        ("resultats", "Résultats"),
    ]

    for key, title in preferred_sections:
        _append_section(sections, title, _iter_curated_rows(_safe_dict(report.get(key)), max_depth=MAX_NESTED_DEPTH))

    _append_section(sections, "Inconnues", _flatten_inconnues(report))
    _append_section(sections, "Alertes", _flatten_alertes(report))

    notes = [str(item) for item in _safe_list(report.get("notes_modele")) if str(item).strip()]
    if notes:
        _append_section(sections, "Notes modèle", [("Note", note) for note in notes[:MAX_NOTE_PREVIEW]])

    if report.get("erreur"):
        _append_section(sections, "Erreur", [("Erreur", str(report.get("erreur")))])

    if not sections and data:
        _append_section(sections, "Données brutes", _iter_curated_rows(data, max_depth=2))

    return sections


def build_element_display_lines(payload: Optional[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []

    for title, rows in build_element_display_sections(payload):
        lines.append(f"[{title}]")
        for key, value in rows:
            lines.append(f"{key}: {value}")
        lines.append("")

    return lines or ["Aucune donnée calculée disponible."]


# =============================================================================
# Rendu PDF bas niveau
# =============================================================================

def _new_page(title: str, *, subtitle: str = "", footer: str = ""):
    fig = plt.figure(figsize=A4_FIGSIZE)
    fig.patch.set_facecolor(COLOR_BG)

    fig.text(
        MARGIN_X,
        TOP_Y,
        title,
        fontsize=TITLE_SIZE,
        fontweight="bold",
        color=COLOR_MAIN,
        va="top",
        ha="left",
    )

    if subtitle:
        fig.text(
            MARGIN_X,
            TOP_Y - 0.030,
            subtitle,
            fontsize=SUBTITLE_SIZE,
            color=COLOR_MUTED,
            va="top",
            ha="left",
        )

    if footer:
        fig.text(
            MARGIN_X,
            BOTTOM_Y - 0.020,
            footer,
            fontsize=SMALL_SIZE,
            color=COLOR_MUTED,
            va="bottom",
            ha="left",
        )

    return fig


def _save_text_pages(
    pdf: PdfPages,
    *,
    title: str,
    lines: Sequence[str],
    subtitle: str = "",
    footer: str = "",
) -> None:
    wrapped: List[str] = []

    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(str(line), width=WRAP_WIDTH_FULL) or [""])

    if not wrapped:
        wrapped = ["Aucune donnée."]

    page_index = 1
    idx = 0

    while idx < len(wrapped):
        page_title = title if page_index == 1 else f"{title} - suite {page_index}"
        fig = _new_page(page_title, subtitle=subtitle if page_index == 1 else "", footer=footer)

        y = TOP_Y - (0.060 if subtitle and page_index == 1 else 0.040)

        while idx < len(wrapped) and y > BOTTOM_Y:
            line = wrapped[idx]
            fig.text(
                MARGIN_X,
                y,
                line,
                fontsize=BODY_SIZE,
                family="DejaVu Sans Mono",
                color=COLOR_TEXT,
                va="top",
                ha="left",
            )
            y -= LINE_HEIGHT
            idx += 1

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_index += 1


def _save_sections_pages(
    pdf: PdfPages,
    *,
    title: str,
    sections: Sequence[Section],
    subtitle: str = "",
    footer: str = "",
) -> None:
    if not sections:
        _save_text_pages(pdf, title=title, lines=["Aucune section disponible."], subtitle=subtitle, footer=footer)
        return

    fig = _new_page(title, subtitle=subtitle, footer=footer)
    y = TOP_Y - (0.060 if subtitle else 0.040)
    page_index = 1

    def new_continuation_page() -> None:
        nonlocal fig, y, page_index
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        page_index += 1
        fig = _new_page(f"{title} - suite {page_index}", footer=footer)
        y = TOP_Y - 0.040

    def ensure_space(required: float = 0.040) -> None:
        if y - required < BOTTOM_Y:
            new_continuation_page()

    for section_title, rows in sections:
        ensure_space(0.055)

        fig.text(
            MARGIN_X,
            y,
            section_title.upper(),
            fontsize=10.5,
            fontweight="bold",
            color=COLOR_ACCENT,
            va="top",
            ha="left",
        )
        y -= 0.024

        for key, value in rows[:MAX_ROWS_PER_SECTION_PREVIEW]:
            key_lines = textwrap.wrap(str(key), width=WRAP_WIDTH_KEY) or [""]
            value_lines = textwrap.wrap(str(value), width=WRAP_WIDTH_VALUE) or [""]

            line_count = max(len(key_lines), len(value_lines))
            required = line_count * LINE_HEIGHT + ROW_GAP

            ensure_space(required)

            for i in range(line_count):
                ky = key_lines[i] if i < len(key_lines) else ""
                val = value_lines[i] if i < len(value_lines) else ""

                fig.text(
                    MARGIN_X,
                    y,
                    ky,
                    fontsize=BODY_SIZE,
                    fontweight="bold" if i == 0 else "normal",
                    color=COLOR_MAIN,
                    va="top",
                    ha="left",
                )
                fig.text(
                    MARGIN_X + 0.285,
                    y,
                    val,
                    fontsize=BODY_SIZE,
                    color=COLOR_TEXT,
                    va="top",
                    ha="left",
                )
                y -= LINE_HEIGHT

            y -= ROW_GAP

        if len(rows) > MAX_ROWS_PER_SECTION_PREVIEW:
            ensure_space(0.024)
            fig.text(
                MARGIN_X,
                y,
                f"... {len(rows) - MAX_ROWS_PER_SECTION_PREVIEW} lignes supplémentaires non affichées dans cette section.",
                fontsize=SMALL_SIZE,
                color=COLOR_MUTED,
                va="top",
                ha="left",
            )
            y -= 0.022

        y -= SECTION_GAP

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _save_cover_page(
    pdf: PdfPages,
    *,
    title: str,
    subtitle: str,
    rows: Sequence[Row],
    footer: str,
) -> None:
    fig = _new_page(title, subtitle=subtitle, footer=footer)

    fig.text(
        MARGIN_X,
        0.835,
        "Rapport technique généré par STHOME / SHSE-M",
        fontsize=13,
        fontweight="bold",
        color=COLOR_MAIN,
        va="top",
        ha="left",
    )

    y = 0.785
    for key, value in rows:
        fig.text(
            MARGIN_X,
            y,
            str(key),
            fontsize=9,
            fontweight="bold",
            color=COLOR_MAIN,
            va="top",
            ha="left",
        )
        fig.text(
            MARGIN_X + 0.29,
            y,
            str(value),
            fontsize=9,
            color=COLOR_TEXT,
            va="top",
            ha="left",
        )
        y -= 0.028

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _save_toc_page(pdf: PdfPages, sections: Sequence[Section], *, footer: str) -> None:
    lines = ["Sections incluses dans le PDF :", ""]

    for idx, (title, rows) in enumerate(sections, start=1):
        lines.append(f"{idx}. {title} ({len(rows)} ligne(s))")

    _save_text_pages(
        pdf,
        title="Table des matières",
        lines=lines,
        footer=footer,
    )


def _save_figure_page(pdf: PdfPages, fig: Any, title: str, *, footer: str = "") -> None:
    try:
        if hasattr(fig, "suptitle"):
            fig.suptitle(title, color=COLOR_MAIN, fontweight="bold")
        pdf.savefig(fig, bbox_inches="tight")
    finally:
        plt.close(fig)


def _save_error_page(pdf: PdfPages, title: str, error: Any, *, footer: str = "") -> None:
    lines = [
        "Une erreur est survenue pendant la génération de cette page.",
        "",
        str(error),
        "",
        traceback.format_exc(),
    ]
    _save_text_pages(pdf, title=title, lines=lines, footer=footer)


# =============================================================================
# Visualisations
# =============================================================================

def _get_visualisation_figure(element_name: str, element_obj: Any, viz_type: str) -> Any:
    if get_viz_figure is None:
        return None

    if element_obj is None:
        return None

    try:
        return get_viz_figure(element_name, element_obj, viz_type)
    except Exception:
        return None


def _append_visualisation_pages(
    pdf: PdfPages,
    *,
    element_name: str,
    display_name: str,
    element_obj: Any,
    footer: str,
) -> None:
    viz_plan = (
        ("sketches_2d", "Vue 2D / Croquis"),
        ("views_3d", "Vue 3D"),
        ("charts", "Graphiques"),
    )

    for viz_type, label in viz_plan:
        fig = _get_visualisation_figure(element_name, element_obj, viz_type)

        if fig is not None:
            _save_figure_page(pdf, fig, f"{display_name} - {label}", footer=footer)
        else:
            _save_text_pages(
                pdf,
                title=f"{display_name} - {label}",
                lines=[
                    f"Aucune vue disponible pour : {label}.",
                    "",
                    "Causes possibles :",
                    "- données géométriques absentes ou partielles ;",
                    "- objet pièce/composant non construit ;",
                    "- visualiseur non disponible pour ce type d'élément ;",
                    "- backend incomplet sur les paramètres nécessaires.",
                ],
                footer=footer,
            )


# =============================================================================
# API existante : export élément
# =============================================================================

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
    sections = build_element_display_sections(data)

    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    footer = f"{output} - généré le {export_time}"

    cover_rows: List[Row] = [
        ("Élément", display_name),
        ("Nom technique", element_name),
        ("Type", "Composant" if is_component else "Pièce"),
        ("État backend", status),
        ("Détail", detail),
        ("Inconnues détectées", str(_count_unknowns(data))),
        ("Alertes détectées", str(_count_alerts(data))),
        ("Fichier", str(output)),
    ]

    with PdfPages(output) as pdf:
        _save_cover_page(
            pdf,
            title=f"Fiche technique - {display_name}",
            subtitle=f"{'Composant' if is_component else 'Pièce'} - {element_name}",
            rows=cover_rows,
            footer=footer,
        )

        _save_toc_page(pdf, sections, footer=footer)

        _save_sections_pages(
            pdf,
            title=f"{display_name} - Données calculées",
            sections=sections,
            subtitle=f"État backend : {status}",
            footer=footer,
        )

        _append_visualisation_pages(
            pdf,
            element_name=element_name,
            display_name=display_name,
            element_obj=element_obj,
            footer=footer,
        )

        raw_lines = json.dumps(_jsonable(data), ensure_ascii=False, indent=2).splitlines()
        _save_text_pages(
            pdf,
            title=f"{display_name} - Données brutes JSON",
            lines=raw_lines,
            footer=footer,
        )

    return output


# =============================================================================
# Export rapport système complet
# =============================================================================

def _section_from_report(report: Mapping[str, Any], key: str, title: str) -> Optional[Section]:
    value = report.get(key)

    if _is_empty_value(value):
        return None

    if isinstance(value, Mapping):
        rows = list(_iter_curated_rows(value, max_depth=MAX_NESTED_DEPTH))
        if not rows:
            rows = [("Données", _format_value(value))]
        return title, rows

    if isinstance(value, list):
        rows: List[Row] = []
        for idx, item in enumerate(value[:120], start=1):
            rows.append((f"Item {idx}", _format_value(item)))
        if len(value) > 120:
            rows.append(("Items restants", str(len(value) - 120)))
        return title, rows

    return title, [("Valeur", _format_value(value))]


def build_system_report_sections(report: Optional[Dict[str, Any]]) -> List[Section]:
    data = _safe_dict(report)
    sections: List[Section] = []

    if not data:
        return [("Rapport", [("État", "Aucune donnée backend disponible.")])]

    summary_rows: List[Row] = [
        ("Inconnues détectées", str(_count_unknowns(data))),
        ("Alertes détectées", str(_count_alerts(data))),
    ]

    resume_gui = _safe_dict(data.get("resume_gui"))
    for key in (
        "Architecture",
        "N_cyl",
        "Bore_mm",
        "Stroke_mm",
        "RPM",
        "PME",
        "PME_Pa",
        "Pmax_Pa",
        "Couple_max_Nm",
        "P_bus_dc_design_w",
        "energie_batterie_kwh",
    ):
        if not _is_empty_value(resume_gui.get(key)):
            summary_rows.append((_human_label(key), _format_value(resume_gui.get(key))))

    sections.append(("Synthèse système", summary_rows))

    for key, title in (
        ("resume_gui", "Résumé GUI"),
        ("synthese", "Synthèse backend"),
        ("systeme_complet", "Système complet"),
        ("cao", "CAO / SolidWorks"),
        ("analyses_composants", "Analyses composants"),
        ("construction_pieces", "Construction pièces"),
        ("rapports_pieces", "Rapports pièces"),
        ("optimisation", "Optimisation"),
        ("legacy", "Legacy"),
        ("inconnues", "Inconnues consolidées"),
        ("alertes", "Alertes consolidées"),
    ):
        section = _section_from_report(data, key, title)
        if section:
            sections.append(section)

    return sections


def export_system_report_pdf(
    *,
    report: Optional[Dict[str, Any]],
    output_path: str | Path,
    title: str = "Rapport technique système STHOME",
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    data = _safe_dict(report)
    sections = build_system_report_sections(data)

    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    footer = f"{output} - généré le {export_time}"

    cover_rows: List[Row] = [
        ("Titre", title),
        ("État", "Rapport disponible" if data else "Aucune donnée"),
        ("Inconnues détectées", str(_count_unknowns(data))),
        ("Alertes détectées", str(_count_alerts(data))),
        ("Fichier", str(output)),
    ]

    with PdfPages(output) as pdf:
        _save_cover_page(
            pdf,
            title=title,
            subtitle="Export système complet",
            rows=cover_rows,
            footer=footer,
        )

        _save_toc_page(pdf, sections, footer=footer)

        _save_sections_pages(
            pdf,
            title="Données système consolidées",
            sections=sections,
            footer=footer,
        )

        raw_lines = json.dumps(_jsonable(data), ensure_ascii=False, indent=2).splitlines()
        _save_text_pages(
            pdf,
            title="Rapport brut JSON",
            lines=raw_lines,
            footer=footer,
        )

    return output


# =============================================================================
# Export lot pièces / composants
# =============================================================================

def export_elements_bundle_pdf(
    *,
    elements: Mapping[str, Dict[str, Any]],
    output_path: str | Path,
    title: str = "Dossier technique éléments STHOME",
    is_component: bool = False,
) -> Path:
    """
    Exporte plusieurs pièces/composants dans un seul PDF.

    elements attendu :
    {
        "piston": {
            "display_name": "Piston",
            "payload": {...},
            "object": piston_obj,
        },
        ...
    }
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    export_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    footer = f"{output} - généré le {export_time}"

    with PdfPages(output) as pdf:
        _save_cover_page(
            pdf,
            title=title,
            subtitle="Export groupé",
            rows=[
                ("Nombre d'éléments", str(len(elements))),
                ("Type", "Composants" if is_component else "Pièces"),
                ("Fichier", str(output)),
            ],
            footer=footer,
        )

        toc_sections: List[Section] = []
        for technical_name, item in elements.items():
            display_name = str(item.get("display_name") or _human_label(technical_name))
            payload = _safe_dict(item.get("payload"))
            status, _ = _status_from_payload(payload)
            toc_sections.append(
                (
                    display_name,
                    [
                        ("Nom technique", technical_name),
                        ("État backend", status),
                        ("Inconnues", str(_count_unknowns(payload))),
                        ("Alertes", str(_count_alerts(payload))),
                    ],
                )
            )

        _save_toc_page(pdf, toc_sections, footer=footer)

        for technical_name, item in elements.items():
            display_name = str(item.get("display_name") or _human_label(technical_name))
            payload = _safe_dict(item.get("payload"))
            element_obj = item.get("object")

            try:
                sections = build_element_display_sections(payload)
                _save_sections_pages(
                    pdf,
                    title=f"Fiche - {display_name}",
                    sections=sections,
                    subtitle=f"Nom technique : {technical_name}",
                    footer=footer,
                )

                _append_visualisation_pages(
                    pdf,
                    element_name=str(technical_name),
                    display_name=display_name,
                    element_obj=element_obj,
                    footer=footer,
                )

            except Exception as exc:
                _save_error_page(
                    pdf,
                    title=f"Erreur export - {display_name}",
                    error=exc,
                    footer=footer,
                )

    return output