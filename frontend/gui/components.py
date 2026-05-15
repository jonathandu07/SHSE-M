from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import StringProperty, ListProperty, DictProperty

# Design System SHSE-M
COLORS = {
    "BL": (0.05, 0.05, 0.07, 1),      # Background profond (Dark Blue)
    "BF": (0.12, 0.14, 0.18, 1),      # Fond de carte (Bleu-Gris)
    "BA": (0.25, 0.85, 0.65, 1),      # Accent (Vert émeraude / Cyan)
    "RF": (0.95, 0.35, 0.35, 1),      # Erreur (Rouge)
    "white": (1, 1, 1, 1),
    "GAXD": (0.6, 0.65, 0.7, 1),      # Gris texte secondaire
    "GW": (0.9, 0.9, 0.9, 0.1),       # Gris transparent
    "JV": (1.0, 0.8, 0.0, 1.0),       # Jaune validation
}

class ModernButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_color = (0, 0, 0, 0)
        self.bold = True
        self.color = COLORS["white"]
        with self.canvas.before:
            Color(*(COLORS["BA"] if not self.disabled else COLORS["GAXD"]))
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[8])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

class PremiumCard(BoxLayout):
    def __init__(self, title="", **kwargs):
        super().__init__(orientation="vertical", padding=20, spacing=10, **kwargs)
        with self.canvas.before:
            Color(*COLORS["BF"])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._upd, size=self._upd)
        
        if title:
            self.add_widget(Label(text=title.upper(), bold=True, color=COLORS["BA"], 
                                  size_hint_y=None, height=30, font_size="14sp", halign="left"))

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

from kivy.lang import Builder
from kivy.uix.textinput import TextInput

# AZERTY MAPPING
AZERTY_MAP = {
    "&": "1", "é": "2", '"': "3", "'": "4", "(": "5", "-": "6", "è": "7", "_": "8", "ç": "9", "à": "0"
}

class NeumorphicInput(TextInput):
    """Champ de saisie neumorphique : chiffres + séparateur décimal ('.' ou ',')."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = (0, 0, 0, 0)
        self.foreground_color = (0.02, 0.08, 0.25, 1)
        self.disabled_foreground_color = (0.02, 0.08, 0.25, 1)
        self.hint_text_color = (0.45, 0.45, 0.45, 1)
        self.cursor_color = (0.92, 0.10, 0.12, 1)
        self.selection_color = (0.70, 0.82, 0.95, 0.85)
        self.padding = [20, 18, 20, 18]
        self.font_size = "32sp"
        self.multiline = False
        self.write_tab = False
        self.halign = "center"
        self.bind(text=self._ensure_readable_state, focus=self._ensure_readable_state)

    def _ensure_readable_state(self, *args):
        self.foreground_color = (0.02, 0.08, 0.25, 1)
        self.disabled_foreground_color = (0.02, 0.08, 0.25, 1)
        self.cursor_color = (0.92, 0.10, 0.12, 1)

    def insert_text(self, substring, from_undo=False):
        s = substring or ""
        current = self.text or ""
        sel = self.selection_text or ""
        out = []
        for ch in s:
            if ch in AZERTY_MAP: ch = AZERTY_MAP[ch]
            if ch == ",": ch = "."
            if ch.isdigit() or ch == ".":
                if ch == "." and sel == "" and "." in current: continue
                out.append(ch)
        return super().insert_text("".join(out), from_undo=from_undo)

Builder.load_string(r"""
<NeumorphicInput>:
    background_normal: ''
    background_active: ''
    background_color: 0, 0, 0, 0
    size_hint_y: None
    height: '76dp'
    font_size: '32sp'
    multiline: False
    write_tab: False
    padding: [20, 18, 20, 18]
    halign: 'center'
    foreground_color: 0.02, 0.08, 0.25, 1
    hint_text_color: 0.45, 0.45, 0.45, 1
    cursor_color: 0.92, 0.10, 0.12, 1
    cursor_width: '2dp'
    selection_color: 0.70, 0.82, 0.95, 0.85
    selection_text_color: 0.02, 0.08, 0.25, 1
    canvas.before:
        Color:
            rgba: 0.85, 0.85, 0.85, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [15]
        Color:
            rgba: 0.97, 0.97, 1, 1
        RoundedRectangle:
            pos: self.x + 2, self.y + 2
            size: self.width - 4, self.height - 4
            radius: [13]
""")

class TechRow(BoxLayout):
    def __init__(self, label, value, unit="", color=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=34, spacing=10, **kwargs)
        self.add_widget(Label(text=str(label), color=COLORS["GAXD"], font_size="13sp", halign="left"))
        val_text = f"{value}" if value is not None else "--"
        if unit and value is not None: val_text += f" {unit}"
        self.add_widget(Label(text=val_text, color=color or COLORS["white"], bold=True, halign="right"))
