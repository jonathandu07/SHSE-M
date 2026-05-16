from __future__ import annotations

from typing import Any

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import (
    COLORS,
    AccordionSection,
    EditableField,
    EmptyState,
    ModernButton,
    SectionTitle,
)


class EditParametersScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        self.fields: dict[str, EditableField] = {}
        app = App.get_running_app()
        params = (app.ui_report or {}).get("editable_parameters") or []
        
        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        root.add_widget(self._top_bar())
        
        if not params:
            root.add_widget(EmptyState(text="AUCUN PARAMÈTRE CONFIGURABLE"))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # Define sections
        sections_map = {
            "système": ["puissance_entree", "unite_entree", "architecture", "carburant"],
            "moteur": ["pme", "regime_pmax", "rapport_al_course", "nb_cylindres"],
            "géométrie": ["diametre_piston", "course_piston", "entraxe_bielle"]
        }
        
        for title, keys in sections_map.items():
            section_items = [p for p in params if p.get("key") in keys or any(k in p.get("key", "").lower() for k in keys)]
            if not section_items: continue
            
            grid = GridLayout(cols=2, spacing=12, size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            for item in section_items:
                val = item.get("value")
                is_missing = val is None or str(val).strip().upper() in {"INCONNU", "NONE", "..."}
                
                # Precise terminology per doctrine
                source_text = "DONNÉE ATTENDUE" if is_missing else item.get("source", "Standard projet explicite")
                if source_text.lower() == "backend":
                    source_text = "CALCUL_BACKEND"
                
                field = EditableField(
                    label=item.get("label", item.get("key")),
                    value=val,
                    source=f"Source: {source_text}",
                    editable=bool(item.get("editable", True)),
                    key=item.get("key")
                )
                grid.add_widget(field)
                self.fields[item.get("key")] = field
            
            content.add_widget(AccordionSection(title=title, content=grid, collapsed=(title != "système")))

        # Other parameters
        seen = {k for sl in sections_map.values() for k in sl}
        others = [p for p in params if p["key"] not in seen and not any(k in p["key"].lower() for k in seen)]
        if others:
            grid = GridLayout(cols=2, spacing=12, size_hint_y=None)
            grid.bind(minimum_height=grid.setter("height"))
            for item in others:
                val = item.get("value")
                is_missing = val is None or str(val).strip().upper() in {"INCONNU", "NONE", "..."}
                source_text = "DONNÉE ATTENDUE" if is_missing else item.get("source", "Standard projet explicite")
                
                field = EditableField(
                    item.get("label", item["key"]), 
                    val, 
                    source=f"Source: {source_text}",
                    editable=item.get("editable", True), 
                    key=item["key"]
                )
                grid.add_widget(field)
                self.fields[item["key"]] = field
            content.add_widget(AccordionSection(title="AUTRES", content=grid))

        scroll.add_widget(content)
        root.add_widget(scroll)
        
        # Bottom Action
        apply_btn = ModernButton(text="APPLIQUER ET RECALCULER", size_hint_y=None, height=50, background_color=COLORS["NG"])
        apply_btn.bind(on_release=self.apply_and_recalculate)
        root.add_widget(apply_btn)
        
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=54, spacing=10, padding=[10, 5])
        lbl = Label(text="PANNEAU D'INGÉNIERIE", color=COLORS["BFW"], bold=True, font_size="16sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        btn_back = ModernButton(text="RETOUR DASHBOARD", size_hint_x=None, width=180, font_size="11sp")
        btn_back.bind(on_release=self.go_dashboard)
        bar.add_widget(btn_back)
        return bar

    def apply_and_recalculate(self, *_):
        app = App.get_running_app()
        params = dict(app.engine_params or {})
        for key, field in self.fields.items():
            if not field.editable: continue
            text = (field.input.text or "").strip()
            if text == "": continue
            try:
                params[key] = float(text.replace(",", ".")) if "." in text or text.isdigit() else text
            except ValueError:
                params[key] = text
        app.engine_params = params
        self.manager.current = "loading"

    def go_dashboard(self, *_):
        self.manager.current = "dashboard"
