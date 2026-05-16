from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Mapping, Optional

from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput


PALETTE = {
    "BLANC_LUNAIRE": "#F4FEFE",
    "BLEU_FRANCE_WEB": "#091226",
    "ROUGE_SPARTE": "#75161E",
    "GRIGIO_SCURO": "#0A0B0A",
    "NATURAL_GREEN": "#3E5349",
}


def _hex_to_rgba(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return (1.0, 1.0, 1.0, alpha)
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
        alpha,
    )


COLORS = {
    "BFW": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"]),
    "BL": _hex_to_rgba(PALETTE["BLEU_FRANCE_WEB"]),
    "RS": _hex_to_rgba(PALETTE["ROUGE_SPARTE"]),
    "GS": _hex_to_rgba(PALETTE["GRIGIO_SCURO"]),
    "NG": _hex_to_rgba(PALETTE["NATURAL_GREEN"]),
    "MUTED": _hex_to_rgba(PALETTE["NATURAL_GREEN"], 0.78),
    "BFW_08": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"], 0.08),
    "BFW_12": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"], 0.12),
    "BFW_18": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"], 0.18),
    "BFW_35": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"], 0.35),
    "RS_18": _hex_to_rgba(PALETTE["ROUGE_SPARTE"], 0.18),
    "NG_18": _hex_to_rgba(PALETTE["NATURAL_GREEN"], 0.18),
}


def format_value(value: Any, max_len: int = 90) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, Mapping):
        return f"[{len(value)} items]"
    if isinstance(value, (list, tuple, set)):
        return f"[{len(value)} items]"
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "..."


def _status_color(status: Any) -> tuple[float, float, float, float]:
    low = str(status or "").lower()
    if low in {"ok", "available", "disponible", "calculee", "calculée", "saisie", "retenue"}:
        return COLORS["NG"]
    if low in {"partial", "partiel", "alerte", "warning", "missing", "indisponible", "unavailable"}:
        return COLORS["RS"]
    if low in {"error", "erreur", "bloquant"}:
        return COLORS["RS"]
    return COLORS["BFW_35"]


class _CanvasBox(BoxLayout):
    def __init__(self, *, bg: Any = None, radius: float = 8, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bg = bg if bg is not None else COLORS["BFW_08"]
        self._radius = radius
        with self.canvas.before:
            self._color = Color(*self._bg)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[self._radius])
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_: Any) -> None:
        self._rect.pos = self.pos
        self._rect.size = self.size


class ModernButton(Button):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", COLORS["RS"])
        kwargs.setdefault("color", COLORS["BFW"])
        kwargs.setdefault("bold", True)
        kwargs.setdefault("font_size", "12sp")
        super().__init__(**kwargs)


class GhostButton(ModernButton):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("background_color", COLORS["BFW_12"])
        super().__init__(**kwargs)


class NeoCard(_CanvasBox):
    def __init__(self, **kwargs: Any) -> None:
        bg = kwargs.pop("bg", COLORS["BFW_08"])
        kwargs.setdefault("padding", dp(10))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(bg=bg, radius=8, **kwargs)


class PremiumCard(NeoCard):
    def __init__(self, title: str = "", **kwargs: Any) -> None:
        super().__init__(orientation=kwargs.pop("orientation", "vertical"), **kwargs)
        if title:
            self.add_widget(SectionTitle(text=title.upper()))


class SectionTitle(Label):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("color", COLORS["BFW"])
        kwargs.setdefault("bold", True)
        kwargs.setdefault("font_size", "13sp")
        kwargs.setdefault("halign", "left")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(28))
        super().__init__(**kwargs)
        self.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))


class StatusBadge(Label):
    def __init__(self, status: str = "", text: Optional[str] = None, **kwargs: Any) -> None:
        self.status = status
        kwargs.setdefault("text", str(text if text is not None else status or "inconnu").upper())
        kwargs.setdefault("color", COLORS["BFW"])
        kwargs.setdefault("bold", True)
        kwargs.setdefault("font_size", "10sp")
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(26))
        super().__init__(**kwargs)
        with self.canvas.before:
            self._color = Color(*_status_color(status))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])
        self.bind(pos=self._update_canvas, size=self._update_canvas)

    def _update_canvas(self, *_: Any) -> None:
        self._rect.pos = self.pos
        self._rect.size = self.size


class MetricRow(BoxLayout):
    def __init__(self, label: str, value: Any = None, unit: str = "", status: str = "ok", **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(30))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        label_widget = Label(
            text=str(label),
            color=COLORS["MUTED"],
            font_size="10sp",
            halign="left",
            valign="middle",
            size_hint_x=0.42,
        )
        label_widget.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        value_text = format_value(value)
        if unit:
            value_text = f"{value_text} {unit}"
        value_widget = Label(
            text=value_text,
            color=COLORS["BFW"] if status not in {"missing", "unavailable", "indisponible"} else COLORS["RS"],
            font_size="10sp",
            halign="right",
            valign="middle",
        )
        value_widget.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(label_widget)
        self.add_widget(value_widget)


class KpiCard(NeoCard):
    def __init__(self, label: str, value: Any, unit: str = "", status: str = "ok", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", **kwargs)
        self.add_widget(Label(text=str(label).upper(), color=COLORS["MUTED"], font_size="10sp", size_hint_y=None, height=dp(24)))
        val = format_value(value, 48)
        if unit:
            val = f"{val} {unit}"
        self.add_widget(Label(text=val, color=COLORS["BFW"], bold=True, font_size="18sp"))
        self.add_widget(StatusBadge(status=status, size_hint_y=None, height=dp(24)))


class EmptyState(BoxLayout):
    def __init__(self, text: str = "Aucune donnee.", action_text: str = "", callback: Optional[Callable[..., Any]] = None, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(16))
        kwargs.setdefault("spacing", dp(10))
        super().__init__(**kwargs)
        self.add_widget(Label(text=str(text), color=COLORS["MUTED"], bold=True, halign="center", valign="middle"))
        if action_text and callback is not None:
            btn = ModernButton(text=action_text, size_hint_y=None, height=dp(42))
            btn.bind(on_release=callback)
            self.add_widget(btn)


class NeumorphicInput(TextInput):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("background_color", COLORS["BL"])
        kwargs.setdefault("foreground_color", COLORS["BFW"])
        kwargs.setdefault("cursor_color", COLORS["RS"])
        kwargs.setdefault("multiline", False)
        kwargs.setdefault("padding", [dp(10), dp(10), dp(10), dp(10)])
        super().__init__(**kwargs)


class AccordionSection(BoxLayout):
    def __init__(self, title: str, content: Any, collapsed: bool = False, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("spacing", dp(6))
        super().__init__(**kwargs)
        self._content = content
        self._collapsed = bool(collapsed)
        self._button = ModernButton(text=title, size_hint_y=None, height=dp(38), font_size="11sp")
        self._button.bind(on_release=self.toggle)
        self.add_widget(self._button)
        if not self._collapsed:
            self.add_widget(self._content)
        self.bind(minimum_height=self.setter("height"))

    def toggle(self, *_: Any) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            if self._content.parent is self:
                self.remove_widget(self._content)
        elif self._content.parent is None:
            self.add_widget(self._content)


class EditableField(NeoCard):
    def __init__(self, label: str, value: Any = None, source: str = "", editable: bool = True, key: str = "", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(118), **kwargs)
        self.key = key
        self.add_widget(Label(text=str(label), color=COLORS["BFW"], bold=True, font_size="12sp", size_hint_y=None, height=dp(24)))
        self.input = TextInput(
            text="" if value is None else str(value),
            multiline=False,
            readonly=not editable,
            background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"],
            size_hint_y=None,
            height=dp(38),
        )
        self.add_widget(self.input)
        self.add_widget(Label(text=str(source), color=COLORS["MUTED"], font_size="9sp", size_hint_y=None, height=dp(32), halign="left"))


class SearchBar(TextInput):
    def __init__(self, callback: Optional[Callable[[str], Any]] = None, **kwargs: Any) -> None:
        kwargs.setdefault("hint_text", "Rechercher")
        kwargs.setdefault("multiline", False)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(38))
        kwargs.setdefault("background_color", COLORS["BL"])
        kwargs.setdefault("foreground_color", COLORS["BFW"])
        kwargs.setdefault("cursor_color", COLORS["RS"])
        super().__init__(**kwargs)
        self._callback = callback
        self.bind(text=self._on_text)

    def _on_text(self, _instance: Any, value: str) -> None:
        if self._callback is not None:
            self._callback(value)


class FilterChips(BoxLayout):
    def __init__(self, filters: Iterable[str], callback: Optional[Callable[[str], Any]] = None, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("spacing", dp(8))
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(40))
        super().__init__(**kwargs)
        for name in filters:
            text = str(name)
            btn = ModernButton(text=text.upper(), size_hint_x=None, width=dp(max(76, len(text) * 8 + 24)), font_size="9sp")
            if callback is not None:
                btn.bind(on_release=lambda _btn, value=text: callback(value))
            self.add_widget(btn)


class JsonTreeView(ScrollView):
    def __init__(self, data: Any, **kwargs: Any) -> None:
        super().__init__(do_scroll_x=False, **kwargs)
        box = BoxLayout(orientation="vertical", spacing=dp(2), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        for line in self._lines(data):
            lbl = Label(text=line, color=COLORS["BFW"], font_size="10sp", size_hint_y=None, height=dp(22), halign="left")
            lbl.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            box.add_widget(lbl)
        self.add_widget(box)

    def _lines(self, data: Any, indent: int = 0) -> list[str]:
        prefix = "  " * indent
        if isinstance(data, Mapping):
            lines: list[str] = []
            for key, value in data.items():
                if isinstance(value, (Mapping, list, tuple)):
                    lines.append(f"{prefix}{key}:")
                    lines.extend(self._lines(value, indent + 1))
                else:
                    lines.append(f"{prefix}{key}: {format_value(value)}")
            return lines or [f"{prefix}{{}}"]
        if isinstance(data, (list, tuple)):
            lines = []
            for idx, value in enumerate(data):
                if isinstance(value, (Mapping, list, tuple)):
                    lines.append(f"{prefix}[{idx}]")
                    lines.extend(self._lines(value, indent + 1))
                else:
                    lines.append(f"{prefix}[{idx}] {format_value(value)}")
            return lines or [f"{prefix}[]"]
        return [f"{prefix}{format_value(data)}"]


class JsonViewer(BoxLayout):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("orientation", "vertical")
        super().__init__(**kwargs)
        self.text_input = TextInput(
            text="",
            readonly=True,
            background_color=COLORS["BL"],
            foreground_color=COLORS["BFW"],
            cursor_color=COLORS["RS"],
        )
        self.add_widget(self.text_input)

    def set_data(self, data: Any) -> None:
        self.text_input.text = json.dumps(data, ensure_ascii=False, indent=2, default=str)


class ResourceCard(NeoCard):
    def __init__(self, name: str, rtype: str = "", subsystem: str = "", status: str = "unavailable", **kwargs: Any) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(150), **kwargs)
        self.add_widget(SectionTitle(text=str(name).upper()))
        self.add_widget(StatusBadge(status=status))
        self.add_widget(MetricRow("Type", rtype, "", status))
        self.add_widget(MetricRow("Sous-systeme", subsystem, "", status))
