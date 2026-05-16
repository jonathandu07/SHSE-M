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
        
        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        root.add_widget(self._top_bar())
        
        raw_sections = ui.get("raw_sections") or []
        if not raw_sections:
            root.add_widget(EmptyState(text="DONNÉES TECHNIQUES INDISPONIBLES"))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        
        for sec in raw_sections:
            name = sec.get("name", "Section").upper()
            data = sec.get("value")
            if data:
                accordion = AccordionSection(title=name, content=JsonTreeView(data), collapsed=(name != "RÉSUMÉ SYSTÈME"))
                content.add_widget(accordion)
            
        scroll.add_widget(content)
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
