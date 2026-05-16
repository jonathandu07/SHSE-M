from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput

from frontend.gui.components import COLORS, ModernButton


class ErrorScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=24, spacing=12)
        root.add_widget(Label(text="ERREUR BACKEND", color=COLORS["RS"], bold=True, font_size="24sp", size_hint_y=None, height=54))
        self.message = Label(text="", color=COLORS["BFW"], font_size="16sp", size_hint_y=None, height=70)
        root.add_widget(self.message)
        self.trace = TextInput(readonly=True, background_color=COLORS["BL"], foreground_color=COLORS["RS"])
        root.add_widget(self.trace)
        btn = ModernButton(text="RETOUR ACCUEIL", size_hint_y=None, height=52)
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        root.add_widget(btn)
        self.add_widget(root)

    def set_error(self, message: str, trace: str = "") -> None:
        self.message.text = message
        self.trace.text = trace or "Trace indisponible."
