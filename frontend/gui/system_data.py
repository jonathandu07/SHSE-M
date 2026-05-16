# frontend/gui/system_data.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from frontend.gui.components import (
    COLORS,
    EmptyState,
    JsonTreeView,
    ModernButton,
    PremiumCard,
    SectionTitle,
)

try:
    from frontend.gui.components import AccordionSection as NativeAccordionSection  # type: ignore
except Exception:
    NativeAccordionSection = None  # type: ignore


# =============================================================================
# Helpers stricts
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return [{"name": str(k), "value": v} for k, v in value.items()]
    return [{"name": "Donnée", "value": value}]


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value)


def _json_pretty(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    except Exception:
        return str(value)


def _normalise_section(raw: Any, index: int) -> Dict[str, Any]:
    """
    Normalise une section technique sans inventer de donnée.

    Formats acceptés :
    - {"name": "...", "value": ...}
    - {"title": "...", "data": ...}
    - dict libre
    - valeur brute
    """
    if isinstance(raw, Mapping):
        section = dict(raw)

        name = (
            section.get("name")
            or section.get("nom")
            or section.get("title")
            or section.get("titre")
            or section.get("key")
            or f"Section {index + 1}"
        )

        if "value" in section:
            value = section.get("value")
        elif "data" in section:
            value = section.get("data")
        elif "content" in section:
            value = section.get("content")
        else:
            value = {
                k: v
                for k, v in section.items()
                if k not in {"name", "nom", "title", "titre", "key"}
            }

        status = section.get("status") or section.get("statut") or _infer_status(value)

        return {
            "name": _to_text(name, f"Section {index + 1}"),
            "value": value,
            "status": _to_text(status, "inconnu"),
            "raw": section,
        }

    return {
        "name": f"Section {index + 1}",
        "value": raw,
        "status": _infer_status(raw),
        "raw": raw,
    }


def _infer_status(value: Any) -> str:
    if value is None:
        return "vide"
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return "vide"
    return "disponible"


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return True
    return False


def _contains_query(value: Any, query: str, *, depth: int = 0, max_depth: int = 8) -> bool:
    """
    Recherche récursive bornée pour éviter de bloquer l'UI sur gros rapports.
    """
    if not query:
        return True
    if depth > max_depth:
        return query in _to_text(type(value).__name__).lower()

    if value is None:
        return False

    if isinstance(value, Mapping):
        for k, v in value.items():
            if query in str(k).lower():
                return True
            if _contains_query(v, query, depth=depth + 1, max_depth=max_depth):
                return True
        return False

    if isinstance(value, (list, tuple, set)):
        return any(_contains_query(v, query, depth=depth + 1, max_depth=max_depth) for v in value)

    return query in _to_text(value).lower()


def _count_nodes(value: Any, *, depth: int = 0, max_depth: int = 12) -> Dict[str, int]:
    """
    Compte rapide pour résumé UI.
    """
    if depth > max_depth:
        return {"nodes": 1, "dicts": 0, "lists": 0, "leaves": 1, "missing": 0}

    if value is None:
        return {"nodes": 1, "dicts": 0, "lists": 0, "leaves": 1, "missing": 1}

    if isinstance(value, Mapping):
        out = {"nodes": 1, "dicts": 1, "lists": 0, "leaves": 0, "missing": 0}
        for v in value.values():
            c = _count_nodes(v, depth=depth + 1, max_depth=max_depth)
            for k in out:
                out[k] += c[k]
        return out

    if isinstance(value, (list, tuple, set)):
        out = {"nodes": 1, "dicts": 0, "lists": 1, "leaves": 0, "missing": 0}
        for v in value:
            c = _count_nodes(v, depth=depth + 1, max_depth=max_depth)
            for k in out:
                out[k] += c[k]
        return out

    return {
        "nodes": 1,
        "dicts": 0,
        "lists": 0,
        "leaves": 1,
        "missing": 0 if value != "" else 1,
    }


def _section_default_open(name: str) -> bool:
    n = name.lower()
    return any(
        marker in n
        for marker in (
            "résumé",
            "resume",
            "synthese",
            "synthèse",
            "dashboard",
            "systeme",
            "système",
            "meta",
        )
    )


def _build_raw_sections_from_ui(ui: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    Fallback strict : si raw_sections absent, on affiche seulement les blocs UI déjà présents.
    Aucune valeur n'est calculée ni inventée.
    """
    preferred = (
        "meta",
        "dashboard",
        "audit",
        "architecture_candidates",
        "pieces",
        "subsystems",
        "missing_requirements",
        "alerts",
        "exports",
        "sketches",
        "charts",
        "three_d",
        "editable_parameters",
        "notes",
    )

    sections: List[Dict[str, Any]] = []
    for key in preferred:
        if key in ui:
            sections.append({"name": key, "value": ui.get(key)})

    if sections:
        return sections

    return [{"name": str(k), "value": v} for k, v in ui.items()]


# =============================================================================
# Fallback AccordionSection local
# =============================================================================

class LocalAccordionSection(BoxLayout):
    """
    Accordéon autonome utilisé si frontend.gui.components.AccordionSection
    n'existe pas.
    """

    def __init__(
        self,
        *,
        title: str,
        content: Any,
        collapsed: bool = True,
        min_content_height: float = 220.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            **kwargs,
        )

        self.title = title
        self.content_widget = content
        self.collapsed = collapsed
        self.min_content_height = dp(min_content_height)

        self.header = ModernButton(
            text=self._header_text(),
            size_hint_y=None,
            height=dp(42),
            font_size="12sp",
        )
        self.header.bind(on_release=lambda *_: self.toggle())

        self.body = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=0,
        )

        self.add_widget(self.header)
        self.add_widget(self.body)

        self._sync()

    def _header_text(self) -> str:
        arrow = "▶" if self.collapsed else "▼"
        return f"{arrow}  {self.title}"

    def toggle(self) -> None:
        self.collapsed = not self.collapsed
        self._sync()

    def expand(self) -> None:
        self.collapsed = False
        self._sync()

    def collapse(self) -> None:
        self.collapsed = True
        self._sync()

    def _sync(self) -> None:
        self.header.text = self._header_text()
        self.body.clear_widgets()

        if self.collapsed:
            self.body.height = 0
            self.height = self.header.height + dp(6)
            return

        content = self.content_widget
        try:
            content.size_hint_y = None
        except Exception:
            pass

        if getattr(content, "parent", None):
            try:
                content.parent.remove_widget(content)
            except Exception:
                pass

        self.body.add_widget(content)

        content_height = getattr(content, "height", None)
        if not isinstance(content_height, (int, float)) or content_height <= 0:
            content_height = self.min_content_height

        self.body.height = max(float(content_height), self.min_content_height)
        self.height = self.header.height + self.body.height + dp(8)


def _make_accordion(title: str, data: Any, collapsed: bool) -> Any:
    view = JsonTreeView(data)

    if NativeAccordionSection is not None:
        try:
            return NativeAccordionSection(
                title=title,
                content=view,
                collapsed=collapsed,
            )
        except Exception:
            pass

    return LocalAccordionSection(
        title=title,
        content=view,
        collapsed=collapsed,
    )


# =============================================================================
# Écran principal
# =============================================================================

class SystemDataScreen(Screen):
    """
    Explorateur technique du rapport frontend.

    Rôle :
    - afficher les données strictement présentes dans ui_report ;
    - permettre recherche, inspection et export ;
    - ne pas calculer ni inventer de valeur technique.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._query: str = ""
        self._sections: List[Dict[str, Any]] = []
        self._visible_sections: List[Dict[str, Any]] = []
        self._root: Optional[BoxLayout] = None
        self._content_box: Optional[BoxLayout] = None
        self._count_label: Optional[Label] = None
        self._search_input: Optional[TextInput] = None
        self._accordion_widgets: List[Any] = []

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    # -------------------------------------------------------------------------
    # Données
    # -------------------------------------------------------------------------

    def _load_sections(self) -> List[Dict[str, Any]]:
        app = App.get_running_app()
        ui = _safe_dict(getattr(app, "ui_report", {}) or {})

        raw_sections = ui.get("raw_sections")
        if raw_sections:
            raw_items = _safe_list(raw_sections)
        else:
            raw_items = _build_raw_sections_from_ui(ui)

        sections = [
            _normalise_section(raw, index=i)
            for i, raw in enumerate(raw_items)
        ]

        return [
            sec for sec in sections
            if not _is_empty_value(sec.get("value"))
        ]

    def _filter_sections(self) -> List[Dict[str, Any]]:
        query = self._query.strip().lower()
        if not query:
            return list(self._sections)

        out: List[Dict[str, Any]] = []
        for sec in self._sections:
            name = sec.get("name", "")
            status = sec.get("status", "")
            value = sec.get("value")

            if query in _to_text(name).lower():
                out.append(sec)
                continue

            if query in _to_text(status).lower():
                out.append(sec)
                continue

            if _contains_query(value, query):
                out.append(sec)

        return out

    def refresh(self) -> None:
        self._sections = self._load_sections()
        self._render()

    # -------------------------------------------------------------------------
    # Rendu
    # -------------------------------------------------------------------------

    def _render(self) -> None:
        self.clear_widgets()
        self._accordion_widgets = []

        self._root = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )

        self._root.add_widget(self._top_bar())
        self._root.add_widget(self._toolbar())
        self._root.add_widget(self._summary_card())

        self._content_box = BoxLayout(orientation="vertical")
        self._root.add_widget(self._content_box)

        self.add_widget(self._root)
        self._render_content()

    def _render_content(self) -> None:
        if self._content_box is None:
            return

        self._content_box.clear_widgets()
        self._accordion_widgets = []

        self._visible_sections = self._filter_sections()

        if self._count_label is not None:
            self._count_label.text = f"{len(self._visible_sections)} / {len(self._sections)}"

        if not self._sections:
            self._content_box.add_widget(EmptyState(text="DONNÉES TECHNIQUES INDISPONIBLES"))
            return

        if not self._visible_sections:
            self._content_box.add_widget(EmptyState(text="AUCUNE SECTION NE CORRESPOND AU FILTRE"))
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            size_hint_y=None,
        )
        content.bind(minimum_height=content.setter("height"))

        for sec in self._visible_sections:
            name = _to_text(sec.get("name"), "Section").upper()
            data = sec.get("value")
            status = _to_text(sec.get("status"), "inconnu")
            counts = _count_nodes(data)

            title = (
                f"{name}  "
                f"[{status}]  "
                f"{counts['leaves']} valeurs, "
                f"{counts['missing']} manquantes"
            )

            accordion = _make_accordion(
                title=title,
                data=data,
                collapsed=not _section_default_open(name),
            )
            self._accordion_widgets.append(accordion)
            content.add_widget(accordion)

        scroll.add_widget(content)
        self._content_box.add_widget(scroll)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            spacing=dp(10),
            padding=[dp(10), dp(5)],
        )

        lbl = Label(
            text="DÉTAILS TECHNIQUES",
            color=COLORS["BFW"],
            bold=True,
            font_size="16sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)

        self._count_label = Label(
            text="0 / 0",
            color=COLORS.get("MUTED", COLORS["BFW"]),
            size_hint_x=None,
            width=dp(90),
            font_size="12sp",
            halign="center",
            valign="middle",
        )
        self._count_label.bind(size=lambda i, *_: setattr(i, "text_size", i.size))
        bar.add_widget(self._count_label)

        btn_refresh = ModernButton(
            text="RAFRAÎCHIR",
            size_hint_x=None,
            width=dp(125),
            font_size="11sp",
        )
        btn_refresh.bind(on_release=lambda *_: self.refresh())
        bar.add_widget(btn_refresh)

        btn_back = ModernButton(
            text="RETOUR DASHBOARD",
            size_hint_x=None,
            width=dp(180),
            font_size="11sp",
        )
        btn_back.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn_back)

        return bar

    def _toolbar(self) -> BoxLayout:
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(48),
            spacing=dp(8),
            padding=[dp(10), 0],
        )

        self._search_input = TextInput(
            hint_text="Filtrer dans les données techniques...",
            text=self._query,
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["BFW"],
            background_color=COLORS.get("SURFACE", (0.08, 0.10, 0.14, 1)),
            hint_text_color=COLORS.get("MUTED", (0.55, 0.58, 0.65, 1)),
            padding=[dp(10), dp(9), dp(10), dp(9)],
        )
        self._search_input.bind(text=lambda _, value: self._set_query(value))
        bar.add_widget(self._search_input)

        btn_clear = ModernButton(
            text="EFFACER",
            size_hint_x=None,
            width=dp(95),
            font_size="10sp",
        )
        btn_clear.bind(on_release=lambda *_: self._clear_filter())
        bar.add_widget(btn_clear)

        btn_expand = ModernButton(
            text="TOUT OUVRIR",
            size_hint_x=None,
            width=dp(120),
            font_size="10sp",
        )
        btn_expand.bind(on_release=lambda *_: self._expand_all())
        bar.add_widget(btn_expand)

        btn_collapse = ModernButton(
            text="TOUT REPLIER",
            size_hint_x=None,
            width=dp(125),
            font_size="10sp",
        )
        btn_collapse.bind(on_release=lambda *_: self._collapse_all())
        bar.add_widget(btn_collapse)

        btn_copy = ModernButton(
            text="COPIER JSON",
            size_hint_x=None,
            width=dp(125),
            font_size="10sp",
        )
        btn_copy.bind(on_release=lambda *_: self._copy_visible_json())
        bar.add_widget(btn_copy)

        btn_export = ModernButton(
            text="EXPORT JSON",
            size_hint_x=None,
            width=dp(125),
            font_size="10sp",
        )
        btn_export.bind(on_release=lambda *_: self._export_visible_json())
        bar.add_widget(btn_export)

        return bar

    def _summary_card(self) -> BoxLayout:
        card = PremiumCard(
            orientation="vertical",
            size_hint_y=None,
            height=dp(86),
            padding=dp(10),
            spacing=dp(6),
        )

        total_counts = {
            "nodes": 0,
            "dicts": 0,
            "lists": 0,
            "leaves": 0,
            "missing": 0,
        }

        for sec in self._sections:
            c = _count_nodes(sec.get("value"))
            for k in total_counts:
                total_counts[k] += c[k]

        title = SectionTitle(text="SYNTHÈSE DES DONNÉES CHARGÉES")
        card.add_widget(title)

        text = (
            f"Sections : {len(self._sections)}   |   "
            f"Nœuds : {total_counts['nodes']}   |   "
            f"Valeurs : {total_counts['leaves']}   |   "
            f"Listes : {total_counts['lists']}   |   "
            f"Dictionnaires : {total_counts['dicts']}   |   "
            f"Absences détectées : {total_counts['missing']}"
        )

        lbl = Label(
            text=text,
            color=COLORS.get("MUTED", COLORS["BFW"]),
            font_size="12sp",
            halign="left",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        card.add_widget(lbl)

        return card

    # -------------------------------------------------------------------------
    # Actions UI
    # -------------------------------------------------------------------------

    def _set_query(self, text: str) -> None:
        self._query = text or ""
        self._render_content()

    def _clear_filter(self) -> None:
        self._query = ""
        if self._search_input is not None:
            self._search_input.text = ""
        self._render_content()

    def _expand_all(self) -> None:
        for widget in self._accordion_widgets:
            fn = getattr(widget, "expand", None)
            if callable(fn):
                try:
                    fn()
                    continue
                except Exception:
                    pass

            if hasattr(widget, "collapsed"):
                try:
                    widget.collapsed = False
                    if hasattr(widget, "_sync"):
                        widget._sync()
                except Exception:
                    pass

    def _collapse_all(self) -> None:
        for widget in self._accordion_widgets:
            fn = getattr(widget, "collapse", None)
            if callable(fn):
                try:
                    fn()
                    continue
                except Exception:
                    pass

            if hasattr(widget, "collapsed"):
                try:
                    widget.collapsed = True
                    if hasattr(widget, "_sync"):
                        widget._sync()
                except Exception:
                    pass

    def _visible_payload(self) -> Dict[str, Any]:
        return {
            "meta": {
                "source": "frontend.gui.system_data.SystemDataScreen",
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "filter": self._query,
                "visible_sections": len(self._visible_sections),
                "total_sections": len(self._sections),
                "note": "Export strict des données déjà présentes dans ui_report. Aucun calcul ajouté.",
            },
            "sections": [
                {
                    "name": sec.get("name"),
                    "status": sec.get("status"),
                    "value": sec.get("value"),
                }
                for sec in self._visible_sections
            ],
        }

    def _copy_visible_json(self) -> None:
        Clipboard.copy(_json_pretty(self._visible_payload()))
        self._toast("JSON visible copié dans le presse-papiers.")

    def _export_visible_json(self) -> None:
        app = App.get_running_app()

        base = getattr(app, "project_root", None)
        if base is None:
            base = Path.cwd()

        export_dir = Path(base) / "frontend_exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        filename = f"system_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = export_dir / filename
        path.write_text(_json_pretty(self._visible_payload()), encoding="utf-8")

        self._toast(f"Export JSON créé : {path}")

    def _show_json_popup(self, title: str, payload: Any) -> None:
        body = TextInput(
            text=_json_pretty(payload),
            readonly=True,
            multiline=True,
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["BFW"],
            background_color=COLORS.get("SURFACE", (0.08, 0.10, 0.14, 1)),
        )

        root = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(10),
        )
        root.add_widget(body)

        btns = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(42),
        )

        popup = Popup(
            title=title,
            content=root,
            size_hint=(0.88, 0.82),
            auto_dismiss=True,
        )

        btn_copy = ModernButton(text="COPIER", font_size="11sp")
        btn_copy.bind(
            on_release=lambda *_: (
                Clipboard.copy(_json_pretty(payload)),
                self._toast("JSON copié."),
            )
        )
        btns.add_widget(btn_copy)

        btn_close = ModernButton(text="FERMER", font_size="11sp")
        btn_close.bind(on_release=lambda *_: popup.dismiss())
        btns.add_widget(btn_close)

        root.add_widget(btns)
        popup.open()

    def _toast(self, message: str) -> None:
        """
        Utilise le système de notification de l'app s'il existe,
        sinon affiche une popup simple.
        """
        app = App.get_running_app()

        for method_name in ("notify", "toast", "show_message", "set_status"):
            method = getattr(app, method_name, None)
            if callable(method):
                try:
                    method(message)
                    return
                except Exception:
                    pass

        content = BoxLayout(
            orientation="vertical",
            padding=dp(12),
            spacing=dp(10),
        )
        lbl = Label(
            text=message,
            color=COLORS["BFW"],
            halign="center",
            valign="middle",
        )
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", i.size))
        content.add_widget(lbl)

        popup = Popup(
            title="Information",
            content=content,
            size_hint=(0.62, 0.26),
            auto_dismiss=True,
        )
        popup.open()