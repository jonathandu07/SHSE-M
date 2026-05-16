from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EmptyState, JsonTreeView, ModernButton, PremiumCard, SectionTitle


class SystemDataScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        candidates = ui.get("architecture_candidates") or []
        
        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        root.add_widget(self._top_bar())
        
        if not candidates:
            panel = PremiumCard(title="ARCHITECTURE INDISPONIBLE", bg=COLORS["BFW_08"])
            
            why_box = BoxLayout(orientation="vertical", spacing=10, padding=[20, 10])
            why_box.add_widget(Label(text="Pourquoi l'architecture est indisponible ?", bold=True, color=COLORS["RS"], font_size="14sp", halign="left"))
            
            # Simplified reasons for engineering view
            reasons = [
                "• Manque de paramètres PME (Moteur Thermique)",
                "• Cylindrée non fermée / Contraintes géométriques",
                "• Packaging ou Bus DC non dimensionnés"
            ]
            for r in reasons:
                why_box.add_widget(Label(text=r, color=COLORS["BFW"], font_size="12sp", halign="left", size_hint_y=None, height=24))
            
            panel.add_widget(why_box)
            
            panel.add_widget(EmptyState(
                text="DES DONNÉES CRITIQUES MANQUENT",
                action_text="COMPLÉTER LES PARAMÈTRES",
                callback=lambda _: setattr(self.manager, "current", "edit_parameters")
            ))
            root.add_widget(panel)
        else:
            scroll = ScrollView(do_scroll_x=False)
            grid = GridLayout(cols=2, spacing=16, size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            for cand in candidates:
                grid.add_widget(self._candidate_card(cand))
            scroll.add_widget(grid)
            root.add_widget(scroll)
            
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=54, spacing=10, padding=[10, 5])
        lbl = Label(text="DÉTAILS TECHNIQUES", color=COLORS["BFW"], bold=True, font_size="16sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=180, font_size="11sp")
        btn.bind(on_release=lambda *_: setattr(self.manager, "current", "dashboard"))
        bar.add_widget(btn)
        return bar
