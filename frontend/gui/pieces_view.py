# frontend/gui/piece_library.py
from __future__ import annotations

import json
import math
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from frontend.gui.components import (
    COLORS,
    EmptyState,
    JsonTreeView,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SearchBar,
    SectionTitle,
    StatusBadge,
)

try:
    from frontend.gui.report_adapter import extract_piece_list
except Exception:  # pragma: no cover
    extract_piece_list = None  # type: ignore

try:
    from frontend.gui.piece_connector import (
        get_piece_instance,
        get_piece_connector_diagnostic,
    )
except Exception:  # pragma: no cover
    get_piece_instance = None  # type: ignore
    get_piece_connector_diagnostic = None  # type: ignore

try:
    from frontend.gui.pdf_export import export_element_pdf
except Exception:  # pragma: no cover
    export_element_pdf = None  # type: ignore


# =============================================================================
# Helpers stricts
# =============================================================================

def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


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


def _short_text(value: Any, max_len: int = 90) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _human_label(value: Any) -> str:
    text = str(value or "").replace("_", " ").replace("-", " ").strip()
    if not text:
        return "Champ"
    return " ".join(part.capitalize() for part in text.split())


def _slug(value: Any) -> str:
    raw = str(value or "piece").strip().lower()
    out = []
    for ch in raw:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "_".join(part for part in "".join(out).split("_") if part) or "piece"


def _fmt_value(value: Any) -> str:
    if value is None:
        return "—"

    if isinstance(value, bool):
        return "Oui" if value else "Non"

    if _is_finite(value):
        v = float(value)
        av = abs(v)
        if av >= 1_000_000:
            return f"{v / 1_000_000:.4g} M"
        if av >= 1_000:
            return f"{v / 1_000:.4g} k"
        if 0.0 < av < 0.001:
            return f"{v:.4e}"
        return f"{v:.4g}"

    if isinstance(value, Mapping):
        return f"dict:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"

    return _short_text(value, 70)


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 7) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

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
            return {
                "type": type(value).__name__,
                "attributs": _jsonable(
                    {
                        k: v
                        for k, v in vars(value).items()
                        if not k.startswith("_") and not callable(v)
                    },
                    depth=depth + 1,
                    max_depth=max_depth,
                ),
            }
        except Exception:
            pass

    return str(value)


def _label(
    text: str,
    *,
    color: Any = None,
    bold: bool = False,
    size: str = "12sp",
    height: int = 28,
) -> Label:
    lbl = Label(
        text=str(text),
        color=color or COLORS["BFW"],
        bold=bold,
        font_size=size,
        size_hint_y=None,
        height=dp(height),
        halign="left",
        valign="middle",
    )
    lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
    return lbl


def _count_unknowns(value: Any) -> int:
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

    walk(value)
    return total


def _count_alerts(value: Any) -> int:
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

    walk(value)
    return total


def _count_nodes(value: Any, *, depth: int = 0, max_depth: int = 6) -> int:
    if value is None:
        return 0

    if depth > max_depth:
        return 1

    if isinstance(value, Mapping):
        return 1 + sum(_count_nodes(v, depth=depth + 1, max_depth=max_depth) for v in value.values())

    if isinstance(value, list):
        return 1 + sum(_count_nodes(v, depth=depth + 1, max_depth=max_depth) for v in value)

    return 1


def _status_from_piece(piece: Mapping[str, Any]) -> str:
    status = str(piece.get("status") or piece.get("statut") or "").lower()
    if status:
        if status in {"ok", "calculée", "calculee", "disponible", "construit", "construite", "complet"}:
            return "ok"
        if status in {"erreur", "bloquant", "impossible", "missing", "indisponible"}:
            return "alerte"
        return status

    data = _safe_dict(piece.get("data"))
    payload = _safe_dict(piece.get("payload"))

    if piece.get("available") is False:
        return "indisponible"
    if _count_unknowns(data) or _count_unknowns(payload):
        return "alerte"
    if data or payload:
        return "ok"

    return "partiel"


# =============================================================================
# Collecte backend
# =============================================================================

REPORT_ATTRS: Tuple[str, ...] = (
    "raw_backend_report",
    "backend_report",
    "full_report",
    "last_backend_report",
    "engine_report",
    "system_report",
    "raw_report",
    "report",
    "last_report",
    "all_data",
    "toutes_les_donnees",
)


def _collect_backend_report(app: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}

    for attr in REPORT_ATTRS:
        try:
            value = getattr(app, attr, None)
        except Exception:
            continue

        if isinstance(value, Mapping) and value:
            merged = _merge_non_none(merged, value)

    ui = _safe_dict(getattr(app, "ui_report", {}) or {})
    if ui:
        merged.setdefault("ui_report", ui)

    return merged


def _merge_non_none(base: Mapping[str, Any], extra: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})

    for key, value in dict(extra or {}).items():
        if value is None:
            continue

        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[str(key)] = _merge_non_none(out[key], value)
        else:
            out[str(key)] = value

    return out


def _extract_material(data: Mapping[str, Any]) -> Any:
    candidates = (
        data.get("material"),
        data.get("materiau"),
        data.get("materiau_cle"),
        data.get("materiau_piston_cle"),
        data.get("materiau_cylindre_cle"),
        data.get("materiau_bielle_cle"),
        _deep_get(data, "rapport", "materiau"),
        _deep_get(data, "rapport", "materiaux"),
        _deep_get(data, "rapport", "cao", "materiau"),
        _deep_get(data, "inventaire", "materiau"),
        _deep_get(data, "inventaire", "materiau_cle"),
    )
    return _first_non_empty(*candidates)


def _extract_type(name: str, data: Mapping[str, Any]) -> str:
    return str(
        _first_non_empty(
            data.get("type"),
            data.get("famille"),
            _deep_get(data, "inventaire", "type"),
            _deep_get(data, "rapport", "type"),
            _infer_type_from_name(name),
        )
    )


def _infer_type_from_name(name: str) -> str:
    low = str(name or "").lower()

    if any(k in low for k in ("piston", "cylindre", "bielle", "vilebrequin", "arbre", "coussinet", "couvercle", "joint", "deplaceur")):
        return "pièce moteur thermique"
    if "alternateur" in low:
        return "composant électrique"
    if "batterie" in low:
        return "stockage énergie"
    if "boite" in low or "crabot" in low:
        return "transmission"
    if "architecture" in low:
        return "architecture système"

    return "pièce"


def _flatten_simple_block(data: Any, *, max_items: int = 80) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if not isinstance(data, Mapping):
        return out

    def walk(node: Any, prefix: str = "", depth: int = 0) -> None:
        if depth > 3 or len(out) >= max_items:
            return

        if not isinstance(node, Mapping):
            return

        for key, value in node.items():
            if len(out) >= max_items:
                break

            label = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"

            if isinstance(value, Mapping):
                walk(value, label, depth + 1)
            elif isinstance(value, list):
                out[label] = f"list:{len(value)}"
            else:
                out[label] = value

    walk(data)
    return out


def _extract_dimensions(data: Mapping[str, Any]) -> Dict[str, Any]:
    candidates: Dict[str, Any] = {}

    for block in (
        data.get("dimensions"),
        data.get("dimensionnement"),
        data.get("dimensionnements"),
        _deep_get(data, "rapport", "dimensions"),
        _deep_get(data, "rapport", "dimensionnement"),
        _deep_get(data, "rapport", "dimensionnements"),
        _deep_get(data, "rapport", "geometrie"),
        _deep_get(data, "rapport", "cao"),
        _deep_get(data, "inventaire", "dimensions"),
    ):
        candidates.update(_flatten_simple_block(block, max_items=40))

    # Champs fréquents à la racine.
    for key in (
        "alesage_m",
        "course_m",
        "diametre_m",
        "diametre_mm",
        "longueur_m",
        "longueur_mm",
        "epaisseur_m",
        "rayon_m",
        "masse_kg",
        "volume_m3",
    ):
        if data.get(key) is not None:
            candidates.setdefault(key, data.get(key))

    return candidates


def _extract_constraints(data: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    for block in (
        data.get("constraints"),
        data.get("contraintes"),
        _deep_get(data, "rapport", "contraintes"),
        _deep_get(data, "rapport", "efforts"),
        _deep_get(data, "rapport", "thermique"),
        _deep_get(data, "rapport", "performances"),
        _deep_get(data, "rapport", "interfaces"),
    ):
        out.update(_flatten_simple_block(block, max_items=60))

    return out


def _extract_unknowns(data: Mapping[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def add(category: str, item: Any, source: str) -> None:
        if isinstance(item, Mapping):
            out.append(
                {
                    "name": str(_first_non_empty(item.get("name"), item.get("nom"), item.get("champ"), item.get("piece"), category)),
                    "reason": str(_first_non_empty(item.get("reason"), item.get("raison"), item.get("detail"), item.get("message"), "")),
                    "category": category,
                    "source": source,
                }
            )
        else:
            out.append(
                {
                    "name": category,
                    "reason": str(item),
                    "category": category,
                    "source": source,
                }
            )

    def walk(node: Any, source: str) -> None:
        if isinstance(node, Mapping):
            inc = node.get("inconnues")
            if isinstance(inc, Mapping):
                for category, values in inc.items():
                    for item in _safe_list(values):
                        add(str(category), item, f"{source}.inconnues.{category}")

            inconnues_cao = node.get("inconnues_cao")
            if isinstance(inconnues_cao, list):
                for item in inconnues_cao:
                    add("cao", item, f"{source}.inconnues_cao")

            for key, value in node.items():
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{source}.{key}")

        elif isinstance(node, list):
            for idx, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{source}[{idx}]")

    walk(data, "piece")

    seen: set[Tuple[str, str, str]] = set()
    deduped: List[Dict[str, Any]] = []

    for item in out:
        sig = (item.get("name", ""), item.get("reason", ""), item.get("source", ""))
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(item)

    return deduped


def _normalize_piece(name: str, raw: Mapping[str, Any], *, source: str) -> Dict[str, Any]:
    data = dict(raw)

    payload = _safe_dict(
        _first_non_empty(
            data.get("payload"),
            data.get("data"),
            data,
        )
    )

    dimensions = _extract_dimensions(payload)
    constraints = _extract_constraints(payload)
    unknowns = _extract_unknowns(payload)

    piece = {
        "name": str(_first_non_empty(data.get("name"), data.get("nom"), data.get("label"), name)),
        "technical_name": str(_first_non_empty(data.get("technical_name"), data.get("key"), data.get("nom_technique"), name)),
        "type": _extract_type(name, payload),
        "material": _extract_material(payload),
        "status": str(_first_non_empty(data.get("status"), data.get("statut"), "")),
        "dimensions": dimensions,
        "constraints": constraints,
        "unknowns": unknowns,
        "alerts_count": _count_alerts(payload),
        "nodes_count": _count_nodes(payload),
        "source": source,
        "data": payload,
        "raw": dict(raw),
    }

    piece["status"] = _status_from_piece(piece)

    return piece


def _extract_pieces_from_mapping(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    pieces: List[Dict[str, Any]] = []

    # 1) Adapter existant.
    if extract_piece_list is not None:
        try:
            adapted = extract_piece_list(dict(report))
            if isinstance(adapted, list):
                for idx, item in enumerate(adapted):
                    if isinstance(item, Mapping):
                        name = str(_first_non_empty(item.get("name"), item.get("nom"), item.get("key"), f"piece_{idx}"))
                        pieces.append(_normalize_piece(name, item, source="report_adapter.extract_piece_list"))
        except Exception:
            pass

    # 2) Blocs backend fréquents.
    block_paths = (
        ("rapports_pieces", report.get("rapports_pieces")),
        ("construction_pieces", report.get("construction_pieces")),
        ("pieces", report.get("pieces")),
        ("bibliotheque_pieces", report.get("bibliotheque_pieces")),
        ("moteur_thermique.pieces", _deep_get(report, "moteur_thermique", "pieces")),
        ("systeme_complet.rapports_pieces", _deep_get(report, "systeme_complet", "rapports_pieces")),
        ("toutes_les_donnees_composants", report.get("toutes_les_donnees_composants")),
    )

    for source, block in block_paths:
        if isinstance(block, Mapping):
            for name, payload in block.items():
                if isinstance(payload, Mapping):
                    pieces.append(_normalize_piece(str(name), payload, source=source))

        elif isinstance(block, list):
            for idx, payload in enumerate(block):
                if isinstance(payload, Mapping):
                    name = str(_first_non_empty(payload.get("name"), payload.get("nom"), payload.get("key"), f"piece_{idx}"))
                    pieces.append(_normalize_piece(name, payload, source=f"{source}[{idx}]"))

    # 3) Recherche récursive limitée : dict dont les clés ressemblent à des pièces.
    known_names = {
        "piston",
        "cylindre",
        "bielle",
        "corps_bielle",
        "arbre",
        "arbre_moteur",
        "arbre_vilebrequin",
        "arbre_vilbrequin",
        "vilebrequin",
        "arbre_piston",
        "axe_piston",
        "coussinet",
        "coussinet_arbre_piston",
        "couvercle",
        "couvercle_cylindre",
        "culasse",
        "joint_piston",
        "joint_deplaceur",
        "deplaceur",
        "alternateur",
        "batterie",
        "moteur_electrique",
        "boite_crabots",
        "moteur_thermique",
        "architecture",
    }

    def walk(node: Any, path: str = "", depth: int = 0) -> None:
        if depth > 4:
            return

        if isinstance(node, Mapping):
            for key, value in node.items():
                key_str = str(key)
                key_low = key_str.lower()

                if key_low in known_names and isinstance(value, Mapping):
                    pieces.append(_normalize_piece(key_str, value, source=f"recursive:{path}.{key_str}" if path else f"recursive:{key_str}"))

                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}.{key_str}" if path else key_str, depth + 1)

        elif isinstance(node, list):
            for idx, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}[{idx}]", depth + 1)

    walk(report)

    return _dedup_pieces(pieces)


def _dedup_pieces(pieces: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}

    for piece in pieces:
        name = str(_first_non_empty(piece.get("technical_name"), piece.get("name"), "piece"))
        key = _slug(name)

        old = by_key.get(key)
        if old is None:
            by_key[key] = dict(piece)
            continue

        old_score = _piece_richness(old)
        new_score = _piece_richness(piece)
        if new_score >= old_score:
            merged = _merge_non_none(old, piece)
            by_key[key] = merged

    out = list(by_key.values())
    out.sort(key=lambda p: (str(p.get("type", "")), str(p.get("name", ""))))
    return out


def _piece_richness(piece: Mapping[str, Any]) -> int:
    score = 0
    score += len(_safe_dict(piece.get("dimensions"))) * 3
    score += len(_safe_dict(piece.get("constraints"))) * 2
    score += len(_safe_list(piece.get("unknowns")))
    score += _count_nodes(piece.get("data"))
    if piece.get("material"):
        score += 5
    if piece.get("status") in {"ok", "disponible"}:
        score += 5
    return score


def collect_piece_library(app: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    report = _collect_backend_report(app)
    pieces = _extract_pieces_from_mapping(report)

    diagnostics = {
        "report_present": bool(report),
        "pieces_count": len(pieces),
        "unknowns_count": sum(len(_safe_list(p.get("unknowns"))) for p in pieces),
        "alerts_count": sum(int(p.get("alerts_count") or 0) for p in pieces),
        "sources": sorted({str(p.get("source", "")) for p in pieces if p.get("source")}),
    }

    return pieces, diagnostics


# =============================================================================
# Bibliothèque des pièces
# =============================================================================

class PieceLibraryScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.search_query = ""
        self.active_filter = "Tous"
        self.pieces: List[Dict[str, Any]] = []
        self.diagnostics: Dict[str, Any] = {}
        self.content: Optional[GridLayout] = None

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()

        app = App.get_running_app()
        self.pieces, self.diagnostics = collect_piece_library(app)

        try:
            app.piece_library = list(self.pieces)
            app.piece_library_diagnostics = dict(self.diagnostics)
        except Exception:
            pass

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        root.add_widget(self._top_bar())
        root.add_widget(self._summary_panel())

        if not self.pieces:
            root.add_widget(
                EmptyState(
                    text="Pièces indisponibles : le backend n'a pas fourni de bibliothèque exploitable.",
                    action_text="RETOUR DASHBOARD",
                    callback=lambda *_: self._go("dashboard"),
                )
            )
            self.add_widget(root)
            return

        controls = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(92), spacing=dp(5))
        controls.add_widget(SearchBar(callback=self._on_search))
        controls.add_widget(self._filter_bar())
        root.add_widget(controls)

        scroll = ScrollView(do_scroll_x=False)
        self.content = GridLayout(cols=3, spacing=dp(12), size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter("height"))

        self._populate()

        scroll.add_widget(self.content)
        root.add_widget(scroll)
        self.add_widget(root)

    # -------------------------------------------------------------------------
    # UI bibliothèque
    # -------------------------------------------------------------------------

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            spacing=dp(10),
        )

        lbl = Label(
            text="BIBLIOTHÈQUE DES PIÈCES",
            color=COLORS["BFW"],
            bold=True,
            font_size="19sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        buttons = (
            ("RAFRAÎCHIR", self.refresh, 120),
            ("AUDIT", lambda *_: self._go("energy_audit"), 90),
            ("EXPORTS", lambda *_: self._go("exports"), 110),
            ("DASHBOARD", lambda *_: self._go("dashboard"), 140),
        )

        for text, callback, width in buttons:
            btn = ModernButton(text=text, size_hint_x=None, width=dp(width), font_size="11sp")
            btn.bind(on_release=callback)
            bar.add_widget(btn)

        return bar

    def _summary_panel(self) -> PremiumCard:
        total = len(self.pieces)
        ok = sum(1 for p in self.pieces if str(p.get("status")) in {"ok", "disponible", "calculée", "calculee"})
        alert = sum(1 for p in self.pieces if str(p.get("status")) in {"alerte", "erreur", "bloquant"})
        partial = total - ok - alert

        panel = PremiumCard(title="Résumé bibliothèque", size_hint_y=None, height=dp(118))

        grid = GridLayout(cols=6, spacing=dp(8), size_hint_y=None, height=dp(48))
        grid.add_widget(MetricRow("Pièces", total, "", "ok" if total else "missing"))
        grid.add_widget(MetricRow("OK", ok, "", "ok" if ok else "missing"))
        grid.add_widget(MetricRow("À vérifier", alert, "", "alerte" if alert else "ok"))
        grid.add_widget(MetricRow("Partielles", partial, "", "partiel" if partial else "ok"))
        grid.add_widget(MetricRow("Inconnues", self.diagnostics.get("unknowns_count"), "", "alerte" if self.diagnostics.get("unknowns_count") else "ok"))
        grid.add_widget(MetricRow("Sources", len(_safe_list(self.diagnostics.get("sources"))), "", "ok" if self.diagnostics.get("sources") else "missing"))
        panel.add_widget(grid)

        sources = ", ".join(_safe_list(self.diagnostics.get("sources"))[:5])
        panel.add_widget(
            _label(
                f"Sources : {sources or 'aucune source backend détectée'}",
                color=COLORS["GS"],
                size="11sp",
                height=28,
            )
        )

        return panel

    def _filter_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))
        bar.add_widget(_label("Filtres :", color=COLORS["GS"], size="11sp", height=36))

        filters = ["Tous", "OK", "Alertes", "Partielles"]
        filters.extend(sorted({str(p.get("type", "pièce")) for p in self.pieces})[:12])

        for name in filters:
            btn = ModernButton(text=name.upper(), font_size="9sp", size_hint_x=None, width=dp(max(82, len(name) * 8 + 24)))
            btn.bind(on_release=lambda *_args, f=name: self._on_filter(f))
            bar.add_widget(btn)

        return bar

    def _populate(self) -> None:
        if self.content is None:
            return

        self.content.clear_widgets()
        filtered = self._filtered_pieces()

        if not filtered:
            self.content.add_widget(
                Label(
                    text="Aucune pièce ne correspond aux filtres.",
                    color=COLORS["GS"],
                    size_hint_y=None,
                    height=dp(40),
                )
            )
            return

        for piece in filtered:
            self.content.add_widget(self._piece_card(piece))

    def _filtered_pieces(self) -> List[Dict[str, Any]]:
        query = self.search_query.strip().lower()
        active = self.active_filter

        out: List[Dict[str, Any]] = []

        for piece in self.pieces:
            status = str(piece.get("status", "")).lower()
            ptype = str(piece.get("type", "pièce"))

            if active == "OK" and status not in {"ok", "disponible", "calculée", "calculee"}:
                continue
            if active == "Alertes" and status not in {"alerte", "erreur", "bloquant"}:
                continue
            if active == "Partielles" and status not in {"partiel", "indisponible", "missing"}:
                continue
            if active not in {"Tous", "OK", "Alertes", "Partielles"} and ptype != active:
                continue

            if query:
                blob = " ".join(
                    str(piece.get(k, ""))
                    for k in ("name", "technical_name", "type", "material", "status", "source")
                ).lower()
                if query not in blob:
                    continue

            out.append(piece)

        return out

    def _piece_card(self, piece: Mapping[str, Any]) -> NeoCard:
        status = _status_from_piece(piece)
        unknowns = _safe_list(piece.get("unknowns"))
        dimensions = _safe_dict(piece.get("dimensions"))
        constraints = _safe_dict(piece.get("constraints"))

        card = NeoCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(286),
            spacing=dp(6),
            padding=dp(10),
        )

        card.add_widget(SectionTitle(text=str(piece.get("name", "PIÈCE")).upper()))
        card.add_widget(StatusBadge(status=status, size_hint_y=None, height=dp(26)))

        card.add_widget(MetricRow("Type", piece.get("type"), "", status))
        card.add_widget(MetricRow("Matériau", piece.get("material") or "—", "", "ok" if piece.get("material") else "missing"))
        card.add_widget(MetricRow("Dimensions", len(dimensions), "", "ok" if dimensions else "missing"))
        card.add_widget(MetricRow("Contraintes", len(constraints), "", "ok" if constraints else "missing"))
        card.add_widget(MetricRow("Inconnues", len(unknowns), "", "alerte" if unknowns else "ok"))
        card.add_widget(MetricRow("Source", _short_text(piece.get("source"), 38), "", status))

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(8))

        detail_btn = ModernButton(text="DÉTAIL", font_size="10sp")
        detail_btn.bind(on_release=lambda *_: self._open_detail(dict(piece)))
        btn_row.add_widget(detail_btn)

        copy_btn = ModernButton(text="COPIER", font_size="10sp")
        copy_btn.bind(on_release=lambda *_: self._copy_piece(dict(piece)))
        btn_row.add_widget(copy_btn)

        card.add_widget(btn_row)
        return card

    # -------------------------------------------------------------------------
    # Actions bibliothèque
    # -------------------------------------------------------------------------

    def _on_search(self, query: str) -> None:
        self.search_query = query or ""
        self._populate()

    def _on_filter(self, filter_name: str) -> None:
        self.active_filter = filter_name or "Tous"
        self._populate()

    def _open_detail(self, piece: Dict[str, Any]) -> None:
        app = App.get_running_app()
        app.selected_piece = dict(piece)
        self._go("piece_detail")

    def _copy_piece(self, piece: Dict[str, Any]) -> None:
        Clipboard.copy(json.dumps(_jsonable(piece), ensure_ascii=False, indent=2))

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name


# =============================================================================
# Détail pièce
# =============================================================================

class PieceDetailScreen(Screen):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.last_message = ""
        self.last_error = ""

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()

        app = App.get_running_app()
        piece = dict(getattr(app, "selected_piece", {}) or {})

        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        root.add_widget(self._top_bar(piece))

        if not piece:
            root.add_widget(
                EmptyState(
                    text="Aucune pièce sélectionnée.",
                    action_text="RETOUR BIBLIOTHÈQUE",
                    callback=lambda *_: self._go("piece_library"),
                )
            )
            self.add_widget(root)
            return

        root.add_widget(self._summary_panel(piece))

        if self.last_message or self.last_error:
            root.add_widget(self._message_panel())

        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        content.add_widget(
            self._section(
                "Synthèse",
                {
                    "nom": piece.get("name"),
                    "nom_technique": piece.get("technical_name"),
                    "type": piece.get("type"),
                    "statut": piece.get("status"),
                    "materiau": piece.get("material"),
                    "source": piece.get("source"),
                    "noeuds_backend": piece.get("nodes_count"),
                    "alertes": piece.get("alerts_count"),
                },
            )
        )

        content.add_widget(self._section("Dimensions", _safe_dict(piece.get("dimensions"))))
        content.add_widget(self._section("Contraintes / performances", _safe_dict(piece.get("constraints"))))
        content.add_widget(self._unknowns_section(_safe_list(piece.get("unknowns"))))
        content.add_widget(self._connector_section(piece))
        content.add_widget(self._section("Données complètes", _safe_dict(piece.get("data"))))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    # -------------------------------------------------------------------------
    # UI détail
    # -------------------------------------------------------------------------

    def _top_bar(self, piece: Mapping[str, Any]) -> BoxLayout:
        top = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(58),
            spacing=dp(10),
        )

        title = str(piece.get("name", "PIÈCE")).upper() if piece else "PIÈCE"
        lbl = Label(
            text=title,
            color=COLORS["BFW"],
            bold=True,
            font_size="19sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        top.add_widget(lbl)

        buttons = (
            ("PDF", self.export_pdf, 90),
            ("COPIER JSON", self.copy_json, 130),
            ("EXPORTS", lambda *_: self._go("exports"), 110),
            ("RETOUR", lambda *_: self._go("piece_library"), 110),
        )

        for text, callback, width in buttons:
            btn = ModernButton(text=text, size_hint_x=None, width=dp(width), font_size="11sp")
            btn.bind(on_release=callback)
            top.add_widget(btn)

        return top

    def _summary_panel(self, piece: Mapping[str, Any]) -> PremiumCard:
        status = _status_from_piece(piece)
        dimensions = _safe_dict(piece.get("dimensions"))
        constraints = _safe_dict(piece.get("constraints"))
        unknowns = _safe_list(piece.get("unknowns"))
        data = _safe_dict(piece.get("data"))

        panel = PremiumCard(title="Résumé pièce", size_hint_y=None, height=dp(118))

        grid = GridLayout(cols=6, spacing=dp(8), size_hint_y=None, height=dp(48))
        grid.add_widget(MetricRow("Statut", status, "", status))
        grid.add_widget(MetricRow("Dimensions", len(dimensions), "", "ok" if dimensions else "missing"))
        grid.add_widget(MetricRow("Contraintes", len(constraints), "", "ok" if constraints else "missing"))
        grid.add_widget(MetricRow("Inconnues", len(unknowns), "", "alerte" if unknowns else "ok"))
        grid.add_widget(MetricRow("Nœuds", _count_nodes(data), "", "ok" if data else "missing"))
        grid.add_widget(MetricRow("PDF", "possible" if export_element_pdf else "module absent", "", "ok" if export_element_pdf else "missing"))
        panel.add_widget(grid)

        panel.add_widget(
            _label(
                f"Source : {_short_text(piece.get('source'), 160)}",
                color=COLORS["GS"],
                size="11sp",
                height=28,
            )
        )

        return panel

    def _message_panel(self) -> NeoCard:
        status = "alerte" if self.last_error else "ok"
        text = self.last_error or self.last_message

        panel = NeoCard(orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(8))
        panel.add_widget(StatusBadge(status=status, size_hint_x=None, width=dp(110)))
        panel.add_widget(_label(_short_text(text, 180), color=COLORS["RS"] if self.last_error else COLORS["NG"], height=38))
        return panel

    def _section(self, title: str, data: Mapping[str, Any]) -> NeoCard:
        card = NeoCard(orientation="vertical", size_hint_y=None, spacing=dp(4), padding=dp(10))
        card.add_widget(SectionTitle(text=title.upper()))

        if not data:
            card.add_widget(EmptyState(text="INDISPONIBLE"))
            card.height = dp(128)
            return card

        count = 0
        for key, value in data.items():
            if count >= 60:
                card.add_widget(MetricRow("Suite", "voir JSON brut", "", "partiel"))
                break

            card.add_widget(MetricRow(str(key), _fmt_value(value)))
            count += 1

        card.height = max(dp(128), dp(46 + min(60, max(1, count)) * 34))
        return card

    def _unknowns_section(self, unknowns: Sequence[Mapping[str, Any]]) -> NeoCard:
        card = NeoCard(orientation="vertical", size_hint_y=None, spacing=dp(4), padding=dp(10))
        card.add_widget(SectionTitle(text="INCONNUES"))

        if not unknowns:
            card.add_widget(MetricRow("État", "Aucune inconnue détectée", "", "ok"))
            card.height = dp(124)
            return card

        for idx, item in enumerate(unknowns[:40], start=1):
            label = str(_first_non_empty(item.get("name"), item.get("category"), f"Inconnue {idx}"))
            reason = str(_first_non_empty(item.get("reason"), item.get("source"), "—"))
            card.add_widget(MetricRow(label, _short_text(reason, 75), "", "alerte"))

        if len(unknowns) > 40:
            card.add_widget(MetricRow("Suite", f"{len(unknowns) - 40} inconnue(s) non affichée(s)", "", "alerte"))

        card.height = max(dp(128), dp(46 + min(42, len(unknowns)) * 34))
        return card

    def _connector_section(self, piece: Mapping[str, Any]) -> NeoCard:
        app = App.get_running_app()
        params = _safe_dict(getattr(app, "engine_params", {}) or {})
        data = _safe_dict(piece.get("data"))
        name = str(_first_non_empty(piece.get("technical_name"), piece.get("name"), ""))

        diagnostic: Dict[str, Any] = {}

        if get_piece_connector_diagnostic is not None:
            try:
                diagnostic = get_piece_connector_diagnostic(name, params, data)
            except Exception as exc:
                diagnostic = {
                    "erreur": str(exc),
                    "trace": traceback.format_exc(),
                }
        else:
            diagnostic = {
                "module": "frontend.gui.piece_connector indisponible",
            }

        return self._section("Connecteur Python backend", diagnostic)

    # -------------------------------------------------------------------------
    # Actions détail
    # -------------------------------------------------------------------------

    def copy_json(self, *_: Any) -> None:
        app = App.get_running_app()
        piece = dict(getattr(app, "selected_piece", {}) or {})
        Clipboard.copy(json.dumps(_jsonable(piece), ensure_ascii=False, indent=2))
        self.last_message = "JSON pièce copié dans le presse-papiers."
        self.last_error = ""
        self.refresh()

    def export_pdf(self, *_: Any) -> None:
        if export_element_pdf is None:
            self.last_error = "Module pdf_export indisponible : export PDF impossible."
            self.last_message = ""
            self.refresh()
            return

        app = App.get_running_app()
        piece = dict(getattr(app, "selected_piece", {}) or {})

        if not piece:
            self.last_error = "Aucune pièce sélectionnée."
            self.last_message = ""
            self.refresh()
            return

        name = str(_first_non_empty(piece.get("technical_name"), piece.get("name"), "piece"))
        display = str(_first_non_empty(piece.get("name"), name))
        payload = {
            "type": piece.get("type"),
            "source_composant": piece.get("source"),
            "construit": piece.get("status") in {"ok", "disponible", "calculée", "calculee"},
            "rapport_disponible": bool(piece.get("data")),
            "rapport": _safe_dict(piece.get("data")),
            "inventaire": {
                "type": piece.get("type"),
                "materiau": piece.get("material"),
                "dimensions": piece.get("dimensions"),
                "contraintes": piece.get("constraints"),
                "unknowns": piece.get("unknowns"),
            },
        }

        element_obj = None
        if get_piece_instance is not None:
            try:
                element_obj = get_piece_instance(
                    name,
                    _safe_dict(getattr(app, "engine_params", {}) or {}),
                    db_data=_safe_dict(piece.get("data")),
                )
            except Exception:
                element_obj = None

        try:
            export_dir = Path(
                _first_non_empty(
                    getattr(app, "export_dir", None),
                    getattr(app, "exports_dir", None),
                    Path.cwd() / "exports",
                )
            )
            export_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = export_dir / f"piece_{_slug(name)}_{timestamp}.pdf"

            path = export_element_pdf(
                element_name=name,
                display_name=display,
                payload=payload,
                element_obj=element_obj,
                output_path=output,
                is_component=False,
            )

            Clipboard.copy(str(path))
            self.last_message = f"PDF généré : {path}"
            self.last_error = ""

        except Exception as exc:
            self.last_error = f"Échec export PDF : {exc}"
            self.last_message = ""

        self.refresh()

    def _go(self, screen_name: str) -> None:
        if self.manager is not None:
            self.manager.current = screen_name