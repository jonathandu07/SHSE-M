from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import COLORS, EditableField, EmptyState, ModernButton


class EditParametersScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        self.fields: dict[str, EditableField] = {}
        app = App.get_running_app()
        params = (app.ui_report or {}).get("editable_parameters") or []
        
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        
        if not params:
            root.add_widget(EmptyState(text="Aucun paramètre configurable n'est exposé pour ce projet."))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=20, size_hint_y=None, padding=[10, 20])
        content.bind(minimum_height=content.setter("height"))

        # Group by section for better hierarchy
        for section, title in (
            ("system", "CONFIGURATION SYSTÈME"),
            ("engine", "DIMENSIONNEMENT THERMIQUE"),
            ("other", "AUTRES PARAMÈTRES"),
        ):
            # Filtering logic (simplified for now)
            section_items = [p for p in params if p.get("section") == section]
            if section == "system":
                section_items = [p for p in params if p.get("key") in {"puissance_entree", "unite_entree", "architecture"}]
            elif section == "engine":
                section_items = [p for p in params if "mm" in str(p.get("key")) or "cyl" in str(p.get("key"))]
            else:
                seen = {"puissance_entree", "unite_entree", "architecture"} | {p["key"] for p in params if "mm" in str(p.get("key")) or "cyl" in str(p.get("key"))}
                section_items = [p for p in params if p["key"] not in seen]

            if not section_items:
                continue
                
            content.add_widget(SectionTitle(text=title))
            grid = GridLayout(cols=2, spacing=20, size_hint_y=None, height=len(section_items)//2 * 110 + 110)
            for item in section_items:
                field = EditableField(
                    item.get("label", item.get("key")),
                    item.get("value"),
                    source=f"Source: {item.get('source', 'backend')}",
                    editable=bool(item.get("editable", True)),
                    key=item.get("key")
                )
                grid.add_widget(field)
                self.fields[item.get("key")] = field
            content.add_widget(grid)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        lbl = Label(text="PANNEAU DE CONFIGURATION", color=COLORS["BFW"], bold=True, font_size="18sp", halign="left")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        for text, cb in (("APPLIQUER ET RECALCULER", self.apply_and_recalculate), ("ANNULER", self.go_dashboard)):
            btn = ModernButton(text=text, size_hint_x=None, width=200, font_size="12sp")
            btn.bind(on_release=cb)
            bar.add_widget(btn)
        return bar

    def apply_and_recalculate(self, *_):
        app = App.get_running_app()
        params = dict(app.engine_params or {})
        for key, field in self.fields.items():
            if not field.editable:
                continue
            text = (field.input.text or "").strip()
            if text == "":
                continue
            try:
                params[key] = float(text.replace(",", ".")) if "." in text or text.isdigit() else text
            except ValueError:
                params[key] = text
        app.engine_params = params
        self.manager.current = "loading"

    def go_dashboard(self, *_):
        self.manager.current = "dashboard"
