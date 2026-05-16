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
        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        top.add_widget(Label(text="PARAMÈTRES MODIFIABLES", color=COLORS["BFW"], bold=True, font_size="19sp"))
        for text, cb in (("RECALCULER", self.apply_and_recalculate), ("DASHBOARD", self.go_dashboard)):
            btn = ModernButton(text=text, size_hint_x=None, width=150)
            btn.bind(on_release=cb)
            top.add_widget(btn)
        root.add_widget(top)
        if not params:
            root.add_widget(EmptyState(text="Aucun paramètre éditable exposé par le backend."))
            self.add_widget(root)
            return
        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=12, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        for item in params:
            field = EditableField(
                item.get("label", item.get("key", "paramètre")),
                item.get("value"),
                source=f"{item.get('source', '')} {item.get('unit', '')}".strip(),
                editable=bool(item.get("editable", False)),
            )
            content.add_widget(field)
            self.fields[item.get("key")] = field
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def apply_and_recalculate(self, *_):
        app = App.get_running_app()
        params = dict(app.engine_params or {})
        for key, field in self.fields.items():
            if not key or not field.editable:
                continue
            text = (field.input.text or "").strip()
            if text == "":
                continue
            if key == "unite_entree":
                params[key] = text
            elif key == "architecture":
                params[key] = text
            else:
                try:
                    params[key] = float(text.replace(",", "."))
                except ValueError:
                    continue
        app.engine_params = params
        self.manager.current = "loading"

    def go_dashboard(self, *_):
        self.manager.current = "dashboard"
