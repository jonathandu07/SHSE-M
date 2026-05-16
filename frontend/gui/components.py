"""Composants UI STHOME / SHSE-M.

Le module centralise la palette officielle. Les alias historiques restent
présents pour compatibilité, mais pointent uniquement vers les cinq couleurs
autorisées par le projet.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget


def _rgba(hex_value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    hex_value = hex_value.strip().lstrip("#")
    return (
        int(hex_value[0:2], 16) / 255.0,
        int(hex_value[2:4], 16) / 255.0,
        int(hex_value[4:6], 16) / 255.0,
        alpha,
    )


PALETTE = {
    "BLANC_LUNAIRE": "#F4FEFE",
    "BLEU_FRANCE_WEB": "#091226",
    "ROUGE_SPARTE": "#75161E",
    "GRIGIO_SCURO": "#0A0B0A",
    "NATURAL_GREEN": "#3E5349",
}

COLORS = {
    "BL": _rgba(PALETTE["BLANC_LUNAIRE"]),
    "BFW": _rgba(PALETTE["BLEU_FRANCE_WEB"]),
    "RS": _rgba(PALETTE["ROUGE_SPARTE"]),
    "GS": _rgba(PALETTE["GRIGIO_SCURO"]),
    "NG": _rgba(PALETTE["NATURAL_GREEN"]),
    "BL_08": _rgba(PALETTE["BLANC_LUNAIRE"], 0.08),
    "BL_18": _rgba(PALETTE["BLANC_LUNAIRE"], 0.18),
    "BL_35": _rgba(PALETTE["BLANC_LUNAIRE"], 0.35),
    "BFW_08": _rgba(PALETTE["BLEU_FRANCE_WEB"], 0.08),
    "BFW_18": _rgba(PALETTE["BLEU_FRANCE_WEB"], 0.18),
    "BFW_35": _rgba(PALETTE["BLEU_FRANCE_WEB"], 0.35),
    "NG_18": _rgba(PALETTE["NATURAL_GREEN"], 0.18),
    "RS_18": _rgba(PALETTE["ROUGE_SPARTE"], 0.18),
}

# Alias historiques
COLORS.update({
    "BF": COLORS["BFW"],
    "BM": COLORS["BFW"],
    "BA": COLORS["NG"],
    "GAXD": COLORS["GS"],
    "NF": COLORS["GS"],
    "RF": COLORS["RS"],
    "RV": COLORS["RS"],
    "GW": COLORS["BL"],
    "white": COLORS["BL"],
    "BC": COLORS["NG"],
    "JV": COLORS["RS"],
})

AZERTY_MAP = {
    "&": "1", "é": "2", '"': "3", "'": "4", "(": "5",
    "-": "6", "è": "7", "_": "8", "ç": "9", "à": "0",
}


def format_value(value: Any, unit: str = "") -> str:
    if value is None: return "..."
    if isinstance(value, (dict, list)): return f"[{len(value)} items]"
    if isinstance(value, float): text = f"{value:.4g}"
    else: text = str(value)
    if len(text) > 30: text = text[:27] + "..."
    return f"{text} {unit}".strip() if unit else text


class CanvasPanel(BoxLayout):
    def __init__(self, *, bg: tuple[float, float, float, float] = COLORS["BL_35"], border: tuple[float, float, float, float] = COLORS["BFW_18"], radius: int = 8, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bg_color = bg
        self._border_color = border
        self._radius = radius
        with self.canvas.before:
            Color(*self._bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(*self._border_color)
            self._line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius), width=1)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_: Any) -> None:
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._line.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class GlassPanel(CanvasPanel):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("padding", 16)
        kwargs.setdefault("spacing", 10)
        super().__init__(bg=COLORS["BL_35"], border=COLORS["BFW_18"], **kwargs)


class NeoCard(CanvasPanel):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("padding", 12)
        kwargs.setdefault("spacing", 8)
        kwargs.setdefault("bg", COLORS["BL"])
        kwargs.setdefault("border", COLORS["BFW_18"])
        super().__init__(**kwargs)


class PremiumCard(NeoCard):
    def __init__(self, title: str = "", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        if title:
            header = BoxLayout(size_hint_y=None, height=34, spacing=10)
            header.add_widget(SectionTitle(text=title.upper()))
            self.add_widget(header)


class BentoGrid(GridLayout):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("cols", 2)
        kwargs.setdefault("spacing", 12)
        super().__init__(**kwargs)


class SectionTitle(Label):
    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(
            text=str(text).upper(),
            bold=True, color=COLORS["BFW"], font_size=kwargs.pop("font_size", "14sp"),
            size_hint_y=None, height=30, halign="left", valign="middle", **kwargs
        )
        self.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))


class StatusBadge(Label):
    status = StringProperty("inconnu")
    def __init__(self, status: str = "inconnu", **kwargs: Any) -> None:
        self.status = str(status or "inconnu")
        text = kwargs.pop("text", self.status.upper())
        super().__init__(
            text=text, bold=True, color=COLORS["BL"], font_size="10sp",
            size_hint=(None, None), size=(110, 24), **kwargs
        )
        with self.canvas.before:
            Color(*self._status_color())
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[4])
        self.bind(pos=self._update_canvas, size=self._update_canvas, status=lambda *_: self._redraw())

    def _status_color(self) -> tuple[float, float, float, float]:
        s = (self.status or "").lower()
        if s in {"ok", "calculée", "calculee", "disponible", "valide", "fourni", "fournie", "complet"}: return COLORS["NG"]
        if s in {"impossible", "erreur", "bloquant", "indisponible", "missing", "alerte"}: return COLORS["RS"]
        return COLORS["BFW"]

    def _redraw(self) -> None:
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._status_color())
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[4])

    def _update_canvas(self, *_: Any) -> None:
        self._rect.pos = self.pos
        self._rect.size = self.size


class ModernButton(Button):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = kwargs.get("color", COLORS["BL"])
        self.bold = True
        with self.canvas.before:
            Color(*COLORS["BFW"])
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[8])
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_: Any) -> None:
        self._rect.pos = self.pos
        self._rect.size = self.size


class GhostButton(ModernButton):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*COLORS["NG"])
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[8])


class NeumorphicInput(TextInput):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0, 0, 0, 0)
        self.foreground_color = COLORS["BFW"]
        self.padding = [18, 16, 18, 16]
        self.font_size = kwargs.get("font_size", "28sp")
        self.multiline = False
        self.write_tab = False
        self.halign = kwargs.get("halign", "center")
        with self.canvas.before:
            Color(*COLORS["BFW_08"])
            self._outer = RoundedRectangle(pos=self.pos, size=self.size, radius=[10])
            Color(*COLORS["BL"])
            self._inner = RoundedRectangle(pos=(self.x + 2, self.y + 2), size=(self.width - 4, self.height - 4), radius=[8])
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_: Any) -> None:
        self._outer.pos = self.pos
        self._outer.size = self.size
        self._inner.pos = (self.x + 2, self.y + 2)
        self._inner.size = (max(0, self.width - 4), max(0, self.height - 4))

    def insert_text(self, substring: str, from_undo: bool = False) -> None:
        s = substring or ""
        current = self.text or ""
        selection = self.selection_text or ""
        out: list[str] = []
        for ch in s:
            ch = AZERTY_MAP.get(ch, ch)
            if ch == ",": ch = "."
            if ch.isdigit() or ch == ".":
                if ch == "." and not selection and "." in current: continue
                out.append(ch)
        return super().insert_text("".join(out), from_undo=from_undo)


class MetricRow(BoxLayout):
    def __init__(self, label: str, value: Any, unit: str = "", status: str = "", source: str = "", **kwargs: Any) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=32, spacing=8, **kwargs)
        self.padding = [4, 0]
        lbl = Label(text=str(label), color=COLORS["GS"], font_size="11sp", size_hint_x=0.5, halign="left", valign="middle", shorten=True, shorten_from="right")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        self.add_widget(lbl)
        val_text = format_value(value, unit)
        val = Label(text=val_text, color=COLORS["RS"] if value is None or val_text == "..." else COLORS["BFW"], bold=value is not None, font_size="12sp", size_hint_x=0.3, halign="right", valign="middle", shorten=True)
        val.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        self.add_widget(val)
        if status:
            self.add_widget(StatusBadge(status=status, size_hint_x=None, width=90, font_size="9sp", size=(90, 22)))
        else:
            self.add_widget(Widget(size_hint_x=None, width=90))


class KpiCard(NeoCard):
    def __init__(self, title: str, value: Any, unit: str = "", status: str = "", **kwargs: Any) -> None:
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", 110)
        super().__init__(orientation="vertical", spacing=2, **kwargs)
        self.padding = [10, 8]
        self.add_widget(Label(text=str(title).upper(), color=COLORS["GS"], font_size="10sp", size_hint_y=None, height=18, halign="center"))
        val_lbl = Label(text=format_value(value, unit), color=COLORS["BFW"], bold=True, font_size="20sp", halign="center", valign="middle")
        val_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        self.add_widget(val_lbl)
        badge_box = BoxLayout(size_hint_y=None, height=24)
        badge_box.add_widget(Widget()) 
        badge_box.add_widget(StatusBadge(status=status or ("missing" if value is None else "ok"), size=(80, 20), font_size="9sp"))
        badge_box.add_widget(Widget())
        self.add_widget(badge_box)


class AccordionSection(BoxLayout):
    def __init__(self, title: str, content: Widget, collapsed: bool = True, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, **kwargs)
        self.spacing = 2
        self.header = Button(
            text=f"{'▶' if collapsed else '▼'} {title.upper()}",
            size_hint_y=None, height=34, background_normal="", background_color=COLORS["BFW"],
            color=COLORS["BL"], bold=True, font_size="13sp", halign="left", padding=[10, 0]
        )
        self.header.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        self.add_widget(self.header)
        self.content_container = BoxLayout(orientation="vertical", size_hint_y=None, spacing=2)
        self.content_container.bind(minimum_height=self.content_container.setter("height"))
        self.content_container.add_widget(content)
        if collapsed:
            self.content_container.opacity = 0
            self.content_container.height = 0
            self.content_container.disabled = True
        self.add_widget(self.content_container)
        self.header.bind(on_release=self.toggle)
        self.bind(minimum_height=self.setter("height"))

    def toggle(self, *_: Any) -> None:
        if self.content_container.height == 0:
            self.content_container.height = self.content_container.minimum_height
            self.content_container.opacity = 1
            self.content_container.disabled = False
            self.header.text = self.header.text.replace("▶", "▼")
        else:
            self.content_container.height = 0
            self.content_container.opacity = 0
            self.content_container.disabled = True
            self.header.text = self.header.text.replace("▼", "▶")
        if self.parent: self.parent.height = self.parent.minimum_height


class SearchBar(BoxLayout):
    def __init__(self, callback: Callable[[str], None], **kwargs: Any) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=46, spacing=10, **kwargs)
        self.padding = [10, 5]
        self.input = TextInput(
            hint_text="Rechercher...", multiline=False, background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"], font_size="14sp", padding=[10, 8]
        )
        self.input.bind(text=lambda _, val: callback(val))
        self.add_widget(self.input)
        btn = ModernButton(text="CLEAR", size_hint_x=None, width=80)
        btn.bind(on_release=lambda *_: setattr(self.input, "text", ""))
        self.add_widget(btn)


class FilterChips(BoxLayout):
    def __init__(self, filters: list[str], callback: Callable[[str], None], **kwargs: Any) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=40, spacing=8, **kwargs)
        self.padding = [10, 5]
        self.active_filter = "Tous"
        self.buttons: dict[str, Button] = {}
        for f in ["Tous"] + filters:
            btn = Button(
                text=f, size_hint_x=None, width=max(80, len(f) * 10 + 20),
                background_normal="", background_color=COLORS["NG"] if f == "Tous" else COLORS["BFW_08"],
                color=COLORS["BL"] if f == "Tous" else COLORS["BFW"], font_size="12sp"
            )
            btn.bind(on_release=lambda b, val=f: self._select(val))
            self.buttons[f] = btn
            self.add_widget(btn)
        self.callback = callback

    def _select(self, filter_name: str) -> None:
        for name, btn in self.buttons.items():
            if name == filter_name:
                btn.background_color = COLORS["NG"]; btn.color = COLORS["BL"]
            else:
                btn.background_color = COLORS["BFW_08"]; btn.color = COLORS["BFW"]
        self.active_filter = filter_name
        self.callback(filter_name)


class RequirementCard(NeoCard):
    def __init__(self, name: str, subsystem: str, priority: str, reason: str, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=140, spacing=4, **kwargs)
        self.padding = [14, 12]
        header = BoxLayout(size_hint_y=None, height=24, spacing=10)
        header.add_widget(Label(text=name.upper(), bold=True, color=COLORS["BFW"], font_size="13sp", halign="left"))
        header.add_widget(StatusBadge(status=priority, size=(90, 22), font_size="9sp"))
        self.add_widget(header)
        self.add_widget(Label(text=f"ORIENTATION : {subsystem.upper()}", color=COLORS["GS"], font_size="11sp", size_hint_y=None, height=18, halign="left"))
        reason_lbl = Label(text=reason, color=COLORS["BFW"], font_size="12sp", halign="left", valign="top")
        reason_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        self.add_widget(reason_lbl)
        btn_box = BoxLayout(size_hint_y=None, height=32, spacing=10)
        btn_box.add_widget(Widget())
        edit_btn = GhostButton(text="RÉSOUDRE", size_hint_x=None, width=100, font_size="10sp")
        btn_box.add_widget(edit_btn)
        self.add_widget(btn_box)


class ResourceCard(NeoCard):
    def __init__(self, name: str, rtype: str, subsystem: str, status: str, **kwargs: Any) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=64, spacing=15, **kwargs)
        self.padding = [12, 8]
        icon_box = BoxLayout(size_hint_x=None, width=40)
        icon_box.add_widget(Label(text="📄", font_size="24sp"))
        self.add_widget(icon_box)
        info_box = BoxLayout(orientation="vertical", spacing=2)
        info_box.add_widget(Label(text=name, bold=True, color=COLORS["BFW"], font_size="13sp", halign="left"))
        info_box.add_widget(Label(text=f"{rtype} | {subsystem}", color=COLORS["GS"], font_size="10sp", halign="left"))
        self.add_widget(info_box)
        self.add_widget(StatusBadge(status=status, size=(90, 22), font_size="9sp", size_hint_x=None, width=100))
        open_btn = ModernButton(text="OUVRIR", size_hint_x=None, width=80, font_size="10sp")
        self.add_widget(open_btn)


class EmptyState(BoxLayout):
    def __init__(self, text: str = "INDISPONIBLE", action_text: str = "", callback: Optional[Callable] = None, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", spacing=10, padding=20, **kwargs)
        self.add_widget(Label(text=text, color=COLORS["RS"], bold=True, font_size="14sp", halign="center"))
        if action_text and callback:
            btn = ModernButton(text=action_text, size_hint=(None, None), size=(220, 42), pos_hint={"center_x": 0.5})
            btn.bind(on_release=callback)
            self.add_widget(btn)


class EditableField(NeoCard):
    def __init__(self, label: str, value: Any, source: str = "", editable: bool = True, key: str = "", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=110, **kwargs)
        self.padding = [10, 8]
        self.key = key
        self.editable = editable
        header = BoxLayout(size_hint_y=None, height=24)
        header.add_widget(Label(text=label.upper(), color=COLORS["GS"], font_size="10sp", halign="left"))
        if not editable: header.add_widget(Label(text="LECTURE SEULE", color=COLORS["NG"], font_size="9sp", halign="right"))
        self.add_widget(header)
        self.input = TextInput(
            text=str(value) if value is not None else "", multiline=False, readonly=not editable,
            background_color=COLORS["BL"] if editable else COLORS["BFW_08"], foreground_color=COLORS["BFW"],
            font_size="16sp", padding=[8, 8]
        )
        self.add_widget(self.input)
        if source: self.add_widget(Label(text=source, color=COLORS["GS"], font_size="9sp", halign="left", size_hint_y=None, height=16))


class JsonTreeView(ScrollView):
    def __init__(self, data: Any, **kwargs: Any) -> None:
        super().__init__(do_scroll_x=True, **kwargs)
        self.content = BoxLayout(orientation="vertical", size_hint_y=None, padding=10, spacing=4)
        self.content.bind(minimum_height=self.content.setter("height"))
        self._render(data, self.content)
        self.add_widget(self.content)

    def _render(self, data: Any, container: BoxLayout, level: int = 0) -> None:
        indent = "  " * level
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    btn = Button(
                        text=f"{indent}▶ {k}", size_hint_y=None, height=30, background_normal="",
                        background_color=COLORS["BFW_08"], color=COLORS["BFW"], halign="left", font_size="13sp"
                    )
                    btn.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
                    container.add_widget(btn)
                    sc = BoxLayout(orientation="vertical", size_hint_y=None, spacing=2)
                    sc.bind(minimum_height=sc.setter("height"))
                    sc.height = 0
                    def toggle(b: Button, target=sc) -> None:
                        if target.height == 0: target.height = target.minimum_height; b.text = b.text.replace("▶", "▼")
                        else: target.height = 0; b.text = b.text.replace("▼", "▶")
                    btn.bind(on_release=toggle)
                    self._render(v, sc, level + 1); container.add_widget(sc)
                else: container.add_widget(MetricRow(f"{indent}{k}", v))
        elif isinstance(data, list):
            for i, v in enumerate(data):
                if isinstance(v, (dict, list)): self._render({f"Item {i}": v}, container, level)
                else: container.add_widget(MetricRow(f"{indent}[{i}]", v))


class JsonViewer(BoxLayout):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        self.text_input = TextInput(
            readonly=True, background_color=COLORS["BL"], foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"], font_size="12sp", multiline=True
        )
        self.add_widget(self.text_input)


class ActionCard(NeoCard):
    def __init__(self, title: str, detail: str, action_text: str, callback: Optional[Callable[..., Any]] = None, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        self.add_widget(SectionTitle(text=title))
        label = Label(text=detail, color=COLORS["GS"], font_size="12sp", halign="left", valign="top")
        label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(label)
        btn = ModernButton(text=action_text, size_hint_y=None, height=40)
        if callback: btn.bind(on_release=callback)
        self.add_widget(btn)


def scrollable(content: Widget) -> ScrollView:
    scroll = ScrollView(do_scroll_x=False)
    scroll.add_widget(content)
    return scroll
