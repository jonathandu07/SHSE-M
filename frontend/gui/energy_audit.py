from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EmptyState, JsonTreeView, ModernButton, PremiumCard


class EnergyAuditScreen(Screen):
    """
    Espace détaillé d'audit technique complet.
    Remplace l'ancienne vue system_data par une exploration hiérarchique robuste.
    """
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        
        raw_sections = ui.get("raw_sections") or []
        if not raw_sections:
            root.add_widget(EmptyState(text="Audit technique indisponible : aucune donnée backend n'est exploitable."))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=16, size_hint_y=None, padding=[0, 10])
        content.bind(minimum_height=content.setter("height"))
        
        for sec in raw_sections:
            content.add_widget(self._section_panel(sec))
            
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        lbl = Label(text="AUDIT DE CONFORMITÉ TECHNIQUE (DÉTAILLÉ)", color=COLORS["BFW"], bold=True, font_size="18sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=200, font_size="12sp")
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar

    def _section_panel(self, section: dict) -> PremiumCard:
        name = section.get("name", "section").upper()
        # On définit une hauteur fixe initiale raisonnable pour le JsonTreeView
        panel = PremiumCard(title=name, size_hint_y=None, height=450)
        
        data = section.get("value")
        if data is None:
            panel.add_widget(EmptyState(text="Aucune donnée enregistrée pour cette section."))
            panel.height = 100
        else:
            panel.add_widget(JsonTreeView(data))
            
        return panel
