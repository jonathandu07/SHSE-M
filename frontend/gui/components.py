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

class TechRow(BoxLayout):
    def __init__(self, label, value, unit="", color=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=34, spacing=10, **kwargs)
        self.add_widget(Label(text=str(label), color=COLORS["GAXD"], font_size="13sp", halign="left"))
        val_text = f"{value}" if value is not None else "--"
        if unit and value is not None: val_text += f" {unit}"
        self.add_widget(Label(text=val_text, color=color or COLORS["white"], bold=True, halign="right"))
