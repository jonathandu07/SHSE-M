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

# Alias historiques, tous mappés sur la palette officielle.
COLORS.update(
    {
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
    }
)


AZERTY_MAP = {
    "&": "1",
    "é": "2",
    '"': "3",
    "'": "4",
    "(": "5",
    "-": "6",
    "è": "7",
    "_": "8",
    "ç": "9",
    "à": "0",
}


def format_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "INCONNU"
    if isinstance(value, float):
        text = f"{value:.3g}"
    else:
        text = str(value)
    return f"{text} {unit}".strip() if unit else text


class CanvasPanel(BoxLayout):
    def __init__(
        self,
        *,
        bg: tuple[float, float, float, float] = COLORS["BL_35"],
        border: tuple[float, float, float, float] = COLORS["BFW_18"],
        radius: int = 8,
        **kwargs: Any,
    ) -> None:
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
        kwargs.setdefault("padding", 16)
        kwargs.setdefault("spacing", 10)
        super().__init__(bg=COLORS["BL"], border=COLORS["BFW_18"], **kwargs)


class PremiumCard(NeoCard):
    def __init__(self, title: str = "", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        if title:
            self.add_widget(SectionTitle(text=title.upper()))


class BentoGrid(GridLayout):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("cols", 2)
        kwargs.setdefault("spacing", 12)
        super().__init__(**kwargs)


class SectionTitle(Label):
    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(
            text=text,
            bold=True,
            color=COLORS["BFW"],
            font_size=kwargs.pop("font_size", "15sp"),
            size_hint_y=kwargs.pop("size_hint_y", None),
            height=kwargs.pop("height", 30),
            halign="left",
            valign="middle",
            **kwargs,
        )
        self.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))


class StatusBadge(Label):
    status = StringProperty("inconnu")

    def __init__(self, status: str = "inconnu", **kwargs: Any) -> None:
        self.status = status or "inconnu"
        text = kwargs.pop("text", self.status.upper())
        super().__init__(
            text=text,
            bold=True,
            color=COLORS["BL"],
            font_size=kwargs.pop("font_size", "12sp"),
            size_hint_y=kwargs.pop("size_hint_y", None),
            height=kwargs.pop("height", 28),
            **kwargs,
        )
        with self.canvas.before:
            Color(*self._status_color())
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[6])
        self.bind(pos=self._update_canvas, size=self._update_canvas, status=lambda *_: self._redraw())

    def _status_color(self) -> tuple[float, float, float, float]:
        s = (self.status or "").lower()
        if s in {"ok", "calculée", "calculee", "disponible", "valide", "fourni", "fournie"}:
            return COLORS["NG"]
        if s in {"impossible", "erreur", "bloquant", "indisponible"}:
            return COLORS["RS"]
        return COLORS["BFW"]

    def _redraw(self) -> None:
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._status_color())
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[6])

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
        self.disabled_foreground_color = COLORS["BFW"]
        self.hint_text_color = COLORS["BFW_35"]
        self.cursor_color = COLORS["RS"]
        self.selection_color = COLORS["NG_18"]
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
            if ch == ",":
                ch = "."
            if ch.isdigit() or ch == ".":
                if ch == "." and not selection and "." in current:
                    continue
                out.append(ch)
        return super().insert_text("".join(out), from_undo=from_undo)


class MetricRow(BoxLayout):
    def __init__(self, label: str, value: Any, unit: str = "", status: str = "", source: str = "", **kwargs: Any) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=34, spacing=8, **kwargs)
        self.add_widget(Label(text=str(label), color=COLORS["GS"], font_size="13sp", halign="left", valign="middle"))
        val = Label(
            text=format_value(value, unit),
            color=COLORS["RS"] if value is None else COLORS["BFW"],
            bold=value is not None,
            font_size="13sp",
            halign="right",
            valign="middle",
        )
        val.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(val)
        if status:
            self.add_widget(StatusBadge(status=status, text=status.upper(), size_hint_x=None, width=110))
        if source:
            self.tooltip = source


TechRow = MetricRow


class KpiCard(NeoCard):
    def __init__(self, title: str, value: Any, unit: str = "", status: str = "", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        self.add_widget(Label(text=title.upper(), color=COLORS["GS"], font_size="12sp", size_hint_y=None, height=24))
        self.add_widget(Label(text=format_value(value, unit), color=COLORS["BFW"], bold=True, font_size="24sp"))
        self.add_widget(StatusBadge(status=status or ("inconnu" if value is None else "ok"), size_hint_y=None, height=26))


class EmptyState(Label):
    def __init__(self, text: str = "INDISPONIBLE", **kwargs: Any) -> None:
        super().__init__(text=text, color=COLORS["RS"], bold=True, font_size="15sp", halign="center", valign="middle", **kwargs)
        self.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))


class UnknownsPanel(PremiumCard):
    def __init__(self, items: Iterable[dict[str, Any]], title: str = "INCONNUES", **kwargs: Any) -> None:
        super().__init__(title=title, **kwargs)
        self._populate(items)

    def _populate(self, items: Iterable[dict[str, Any]]) -> None:
        data = list(items or [])
        if not data:
            self.add_widget(EmptyState(text="Aucune inconnue remontée."))
            return
        for item in data[:80]:
            self.add_widget(
                MetricRow(
                    item.get("name") or item.get("nom") or "inconnue",
                    item.get("reason") or item.get("raison") or "raison indisponible",
                    status=item.get("category") or "partiel",
                )
            )


class AlertPanel(UnknownsPanel):
    def __init__(self, items: Iterable[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(items, title="ALERTES", **kwargs)


class ActionCard(NeoCard):
    def __init__(self, title: str, detail: str, action_text: str, callback: Optional[Callable[..., Any]] = None, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        self.add_widget(SectionTitle(text=title))
        label = Label(text=detail, color=COLORS["GS"], font_size="13sp", halign="left", valign="top")
        label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(label)
        btn = ModernButton(text=action_text, size_hint_y=None, height=42)
        if callback:
            btn.bind(on_release=callback)
        self.add_widget(btn)


class EditableField(BoxLayout):
    def __init__(self, label: str, value: Any, source: str = "", editable: bool = True, **kwargs: Any) -> None:
        self.key = kwargs.pop("key", label)
        super().__init__(orientation="vertical", size_hint_y=None, height=92, spacing=6, **kwargs)
        self.editable = editable
        self.add_widget(Label(text=label, color=COLORS["BFW"], bold=True, size_hint_y=None, height=22, halign="left"))
        self.input = NeumorphicInput(text="" if value is None else str(value), size_hint_y=None, height=44, font_size="16sp", halign="left")
        self.input.disabled = not editable
        self.add_widget(self.input)
        self.add_widget(Label(text=source or ("modifiable" if editable else "non modifiable"), color=COLORS["GS"], size_hint_y=None, height=20, font_size="11sp"))


class JsonViewer(BoxLayout):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        self.text_input = TextInput(
            readonly=True,
            background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"],
            font_size="12sp",
        )
        self.add_widget(self.text_input)

    @property
    def text(self) -> str:
        return self.text_input.text

    @text.setter
    def text(self, value: str) -> None:
        self.text_input.text = value


def scrollable(content: Widget) -> ScrollView:
    scroll = ScrollView(do_scroll_x=False)
    scroll.add_widget(content)
    return scroll
