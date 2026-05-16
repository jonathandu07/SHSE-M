# frontend/gui/resource_views.py
from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from frontend.gui.components import (
    COLORS,
    EmptyState,
    ModernButton,
    ResourceCard,
)


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
        # Certains rapports peuvent renvoyer {"items": [...]} ou {"ressources": [...]}
        for key in ("items", "resources", "ressources", "data", "files", "fichiers"):
            if isinstance(value.get(key), list):
                return list(value[key])
        # Sinon on transforme chaque entrée en ressource nommée.
        return [
            {"name": str(k), "value": v, "source_key": str(k)}
            for k, v in value.items()
        ]
    return [value]


def _first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def _looks_like_url(value: str) -> bool:
    v = value.lower().strip()
    return v.startswith(("http://", "https://", "file://"))


def _looks_like_path(value: str) -> bool:
    if not value:
        return False
    if _looks_like_url(value):
        return True
    return (
        "\\" in value
        or "/" in value
        or value.lower().endswith(
            (
                ".json",
                ".csv",
                ".txt",
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".svg",
                ".html",
                ".htm",
                ".stl",
                ".step",
                ".stp",
                ".obj",
                ".glb",
                ".gltf",
                ".sldprt",
                ".sldasm",
                ".xlsx",
            )
        )
    )


def _resource_status(item: Mapping[str, Any]) -> str:
    explicit = _first_present(item, "status", "statut", "state", "etat")
    if explicit is not None:
        return str(explicit)

    if bool(item.get("resolved")):
        return "disponible"

    if _first_present(item, "path", "filepath", "file_path", "url", "href", "target") is not None:
        return "disponible"

    if item.get("missing_reason") or item.get("reason"):
        return "indisponible"

    return "inconnu"


def _resource_name(item: Mapping[str, Any], fallback: str) -> str:
    name = _first_present(
        item,
        "name",
        "nom",
        "label",
        "title",
        "titre",
        "filename",
        "file_name",
        "source_key",
    )
    if name is not None:
        return _to_text(name, fallback)

    path = _first_present(item, "path", "filepath", "file_path", "url", "href")
    if path is not None:
        raw = _to_text(path)
        if raw:
            return Path(raw).name if not _looks_like_url(raw) else raw

    return fallback


def _resource_type(item: Mapping[str, Any], default: str = "Ressource") -> str:
    rtype = _first_present(
        item,
        "type",
        "rtype",
        "kind",
        "format",
        "extension",
        "resource_type",
    )
    if rtype is not None:
        return _to_text(rtype, default)

    path = _first_present(item, "path", "filepath", "file_path", "url", "href")
    if path is not None:
        raw = _to_text(path)
        suffix = Path(raw).suffix.lower().strip(".")
        if suffix:
            return suffix.upper()

    return default


def _resource_subsystem(item: Mapping[str, Any], default: str = "Général") -> str:
    subsystem = _first_present(
        item,
        "subsystem",
        "sous_systeme",
        "component",
        "composant",
        "source",
        "category",
        "categorie",
    )
    return _to_text(subsystem, default)


def _resource_target(item: Mapping[str, Any]) -> Optional[str]:
    target = _first_present(
        item,
        "path",
        "filepath",
        "file_path",
        "absolute_path",
        "url",
        "href",
        "target",
        "output",
        "sortie",
    )
    if target is None:
        return None

    text = _to_text(target).strip()
    return text or None


def _resource_description(item: Mapping[str, Any]) -> str:
    desc = _first_present(
        item,
        "description",
        "details",
        "detail",
        "summary",
        "resume",
        "missing_reason",
        "reason",
        "message",
    )
    return _to_text(desc, "")


def _normalise_resource(raw: Any, index: int, default_type: str) -> Dict[str, Any]:
    """
    Normalise une ressource frontend sans inventer de données.

    Accepte :
    - dict backend standard ;
    - str représentant chemin/URL/nom ;
    - Path ;
    - valeur brute quelconque.
    """
    if isinstance(raw, Mapping):
        item = dict(raw)
    elif isinstance(raw, (str, Path)):
        text = str(raw)
        if _looks_like_path(text):
            item = {
                "name": Path(text).name if not _looks_like_url(text) else text,
                "path": text,
                "type": Path(text).suffix.strip(".").upper() or default_type,
            }
        else:
            item = {
                "name": text,
                "type": default_type,
                "value": text,
            }
    else:
        item = {
            "name": f"Ressource {index + 1}",
            "type": default_type,
            "value": raw,
        }

    name = _resource_name(item, f"Ressource {index + 1}")
    rtype = _resource_type(item, default_type)
    subsystem = _resource_subsystem(item)
    status = _resource_status(item)
    target = _resource_target(item)
    description = _resource_description(item)

    item.update(
        {
            "name": name,
            "type": rtype,
            "subsystem": subsystem,
            "status": status,
            "target": target,
            "description": description,
            "_search_blob": " ".join(
                [
                    name,
                    rtype,
                    subsystem,
                    status,
                    target or "",
                    description,
                    _to_text(item.get("raw_path")),
                    _to_text(item.get("source")),
                ]
            ).lower(),
        }
    )
    return item


def _open_target(target: str) -> Tuple[bool, str]:
    """
    Ouvre une URL ou un fichier local.
    Renvoie (ok, message).
    """
    if not target:
        return False, "Aucune cible fournie."

    try:
        if _looks_like_url(target):
            webbrowser.open(target)
            return True, "URL ouverte."

        path = Path(target).expanduser()
        if not path.exists():
            return False, f"Fichier introuvable : {path}"

        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

        return True, "Fichier ouvert."
    except Exception as exc:
        return False, f"Ouverture impossible : {exc}"


def _json_pretty(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    except Exception:
        return str(value)


# =============================================================================
# Écran générique
# =============================================================================

class ResourceListScreen(Screen):
    resource_key = ""
    title = ""
    empty_text = "Ressource indisponible."
    default_resource_type = "Ressource"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._all_resources: List[Dict[str, Any]] = []
        self._query: str = ""
        self._count_label: Optional[Label] = None
        self._search_input: Optional[TextInput] = None
        self._root: Optional[BoxLayout] = None
        self._content_box: Optional[BoxLayout] = None

    def on_enter(self, *_: Any) -> None:
        self.refresh()

    # -------------------------------------------------------------------------
    # Chargement / filtrage
    # -------------------------------------------------------------------------

    def _load_resources(self) -> List[Dict[str, Any]]:
        app = App.get_running_app()
        ui = _safe_dict(getattr(app, "ui_report", {}) or {})
        raw_resources = _safe_list(ui.get(self.resource_key))

        return [
            _normalise_resource(raw, index=i, default_type=self.default_resource_type)
            for i, raw in enumerate(raw_resources)
        ]

    def _filtered_resources(self) -> List[Dict[str, Any]]:
        q = (self._query or "").strip().lower()
        if not q:
            return list(self._all_resources)
        return [item for item in self._all_resources if q in item.get("_search_blob", "")]

    def refresh(self) -> None:
        self._all_resources = self._load_resources()
        self._render()

    def _set_query(self, text: str) -> None:
        self._query = text or ""
        self._render_content()

    # -------------------------------------------------------------------------
    # Rendu
    # -------------------------------------------------------------------------

    def _render(self) -> None:
        self.clear_widgets()

        self._root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        self._root.add_widget(self._top_bar())
        self._root.add_widget(self._toolbar())

        self._content_box = BoxLayout(orientation="vertical")
        self._root.add_widget(self._content_box)

        self.add_widget(self._root)
        self._render_content()

    def _render_content(self) -> None:
        if self._content_box is None:
            return

        self._content_box.clear_widgets()
        resources = self._filtered_resources()

        if self._count_label is not None:
            self._count_label.text = f"{len(resources)} / {len(self._all_resources)}"

        if not self._all_resources:
            self._content_box.add_widget(EmptyState(text=self.empty_text))
            return

        if not resources:
            self._content_box.add_widget(EmptyState(text="AUCUNE RESSOURCE NE CORRESPOND AU FILTRE"))
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(4))
        grid = GridLayout(cols=1, spacing=dp(12), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for item in resources:
            grid.add_widget(self._resource_row(item))

        scroll.add_widget(grid)
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
            text=self.title.upper(),
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
            spacing=dp(10),
            padding=[dp(10), 0],
        )

        self._search_input = TextInput(
            hint_text="Filtrer par nom, type, sous-système, statut, chemin...",
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
            width=dp(105),
            font_size="11sp",
        )
        btn_clear.bind(on_release=lambda *_: self._clear_filter())
        bar.add_widget(btn_clear)

        return bar

    def _resource_row(self, item: Dict[str, Any]) -> BoxLayout:
        row = BoxLayout(
            orientation="vertical",
            spacing=dp(6),
            size_hint_y=None,
            padding=[0, 0, 0, dp(4)],
        )

        target = item.get("target")
        desc = item.get("description")

        card = ResourceCard(
            name=item.get("name", "Ressource"),
            rtype=item.get("type", "Document"),
            subsystem=item.get("subsystem", "Général"),
            status=item.get("status", "indisponible"),
        )
        row.add_widget(card)

        meta = self._meta_line(item)
        if meta:
            meta_lbl = Label(
                text=meta,
                color=COLORS.get("MUTED", COLORS["BFW"]),
                font_size="11sp",
                size_hint_y=None,
                height=dp(22),
                halign="left",
                valign="middle",
            )
            meta_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
            row.add_widget(meta_lbl)

        if desc:
            desc_lbl = Label(
                text=desc,
                color=COLORS.get("MUTED", COLORS["BFW"]),
                font_size="11sp",
                size_hint_y=None,
                height=dp(34),
                halign="left",
                valign="top",
            )
            desc_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
            row.add_widget(desc_lbl)

        actions = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(38),
        )

        btn_open = ModernButton(
            text="OUVRIR",
            size_hint_x=None,
            width=dp(95),
            font_size="10sp",
        )
        btn_open.disabled = not bool(target)
        btn_open.bind(on_release=lambda *_: self._open_item(item))
        actions.add_widget(btn_open)

        btn_copy = ModernButton(
            text="COPIER CIBLE",
            size_hint_x=None,
            width=dp(130),
            font_size="10sp",
        )
        btn_copy.disabled = not bool(target)
        btn_copy.bind(on_release=lambda *_: self._copy_target(item))
        actions.add_widget(btn_copy)

        btn_details = ModernButton(
            text="DÉTAILS",
            size_hint_x=None,
            width=dp(105),
            font_size="10sp",
        )
        btn_details.bind(on_release=lambda *_: self._show_details(item))
        actions.add_widget(btn_details)

        spacer = Label(text="")
        actions.add_widget(spacer)

        row.add_widget(actions)

        # Hauteur dynamique mais stable.
        row.height = dp(150) + (dp(34) if desc else 0) + (dp(22) if meta else 0)
        return row

    def _meta_line(self, item: Mapping[str, Any]) -> str:
        parts: List[str] = []

        raw_path = item.get("raw_path")
        if raw_path:
            parts.append(f"raw_path={raw_path}")

        source = item.get("source")
        if source:
            parts.append(f"source={source}")

        target = item.get("target")
        if target:
            parts.append(f"cible={target}")

        return "  |  ".join(_to_text(p) for p in parts if p)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def _clear_filter(self) -> None:
        self._query = ""
        if self._search_input is not None:
            self._search_input.text = ""
        self._render_content()

    def _open_item(self, item: Mapping[str, Any]) -> None:
        target = _to_text(item.get("target"))
        ok, message = _open_target(target)
        self._toast(message if not ok else "Ressource ouverte.")

    def _copy_target(self, item: Mapping[str, Any]) -> None:
        target = _to_text(item.get("target"))
        if target:
            Clipboard.copy(target)
            self._toast("Cible copiée dans le presse-papiers.")
        else:
            self._toast("Aucune cible à copier.")

    def _show_details(self, item: Mapping[str, Any]) -> None:
        body = TextInput(
            text=_json_pretty(dict(item)),
            readonly=True,
            multiline=True,
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["BFW"],
            background_color=COLORS.get("SURFACE", (0.08, 0.10, 0.14, 1)),
        )

        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        root.add_widget(body)

        btns = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(42),
        )

        popup = Popup(
            title=f"Détails — {item.get('name', 'Ressource')}",
            content=root,
            size_hint=(0.88, 0.82),
            auto_dismiss=True,
        )

        btn_copy_json = ModernButton(text="COPIER JSON", font_size="11sp")
        btn_copy_json.bind(
            on_release=lambda *_: (
                Clipboard.copy(_json_pretty(dict(item))),
                self._toast("JSON copié."),
            )
        )
        btns.add_widget(btn_copy_json)

        btn_close = ModernButton(text="FERMER", font_size="11sp")
        btn_close.bind(on_release=lambda *_: popup.dismiss())
        btns.add_widget(btn_close)

        root.add_widget(btns)
        popup.open()

    def _toast(self, message: str) -> None:
        """
        Notification simple et autonome.
        Si ton App possède déjà une méthode notify/toast, elle est utilisée.
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

        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
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
            size_hint=(0.55, 0.26),
            auto_dismiss=True,
        )
        popup.open()


# =============================================================================
# Écrans spécialisés
# =============================================================================

class SketchesScreen(ResourceListScreen):
    resource_key = "sketches"
    title = "CROQUIS D'INGÉNIERIE"
    empty_text = "AUCUN CROQUIS DISPONIBLE"
    default_resource_type = "Croquis"


class ChartsScreen(ResourceListScreen):
    resource_key = "charts"
    title = "GRAPHES DE PERFORMANCE"
    empty_text = "DONNÉES DE PERFORMANCE INSUFFISANTES"
    default_resource_type = "Graphique"


class ThreeDScreen(ResourceListScreen):
    resource_key = "three_d"
    title = "MODÈLES NUMÉRIQUES 3D"
    empty_text = "FICHIERS CAO NON GÉNÉRÉS"
    default_resource_type = "Modèle 3D"