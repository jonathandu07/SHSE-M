from __future__ import annotations

import os
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget

from frontend.gui.components import COLORS, ModernButton, NeumorphicInput, SectionTitle, NeoCard


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = PROJECT_ROOT / "frontend" / "images" / "logo.png"


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=[64, 40], spacing=24)

        hero = BoxLayout(orientation="horizontal", size_hint_y=None, height=120, spacing=20)
        if LOGO_PATH.exists():
            hero.add_widget(Image(source=str(LOGO_PATH), size_hint=(None, None), size=(88, 88), allow_stretch=True, keep_ratio=True))
        title_box = BoxLayout(orientation="vertical", spacing=0)
        title_box.add_widget(Label(text="STHOME", color=COLORS["BFW"], bold=True, font_size="44sp", halign="left"))
        title_box.add_widget(Label(text="Cockpit de dimensionnement thermo-hybride", color=COLORS["NG"], font_size="18sp", halign="left"))
        hero.add_widget(title_box)
        hero.add_widget(Widget())
        root.add_widget(hero)

        card = NeoCard(orientation="vertical", size_hint_y=None, height=430, spacing=18, padding=26)
        card.add_widget(SectionTitle(text="PUISSANCE DE SORTIE DEMANDÉE"))
        intro = Label(
            text="Saisis uniquement la puissance de départ. Le backend calcule ce qu'il peut et remonte le reste comme inconnu.",
            color=COLORS["GS"],
            font_size="15sp",
            size_hint_y=None,
            height=54,
            halign="left",
            valign="top",
        )
        intro.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        card.add_widget(intro)

        form = BoxLayout(orientation="horizontal", spacing=18, size_hint_y=None, height=96)
        self.power_input = NeumorphicInput(text="", hint_text="ex : 100", size_hint_x=0.72)
        self.unit_spinner = Spinner(
            text="Unité",
            values=("kW", "ch"),
            size_hint_x=0.28,
            background_normal="",
            background_color=COLORS["BFW"],
            color=COLORS["BL"],
            bold=True,
        )
        form.add_widget(self.power_input)
        form.add_widget(self.unit_spinner)
        card.add_widget(form)

        self.error_label = Label(text="", color=COLORS["RS"], bold=True, size_hint_y=None, height=36)
        card.add_widget(self.error_label)

        btn = ModernButton(text="CALCULER", size_hint_y=None, height=68)
        btn.bind(on_release=self._launch)
        card.add_widget(btn)

        root.add_widget(card)
        root.add_widget(Widget())
        self.add_widget(root)

    def on_enter(self, *_):
        self.error_label.text = ""

    def _launch(self, *_):
        raw = (self.power_input.text or "").strip().replace(",", ".")
        if not raw:
            self.error_label.text = "Valeur absente : indique une puissance."
            return
        try:
            value = float(raw)
        except ValueError:
            self.error_label.text = "Valeur invalide : nombre attendu."
            return
        if value <= 0:
            self.error_label.text = "Valeur invalide : puissance strictement positive attendue."
            return
        unit = self.unit_spinner.text
        if unit not in {"kW", "ch"}:
            self.error_label.text = "Unité absente : choisis kW ou ch."
            return

        app = App.get_running_app()
        app.engine_params = {"puissance_entree": value, "unite_entree": unit}
        app.raw_backend_report = {}
        app.ui_report = {}
        self.manager.current = "loading"
