from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from frontend.gui.components import (
    COLORS,
    ActionCard,
    BentoGrid,
    EmptyState,
    KpiCard,
    MetricRow,
    ModernButton,
    NeoCard,
    PremiumCard,
    SectionTitle,
    UnknownsPanel,
)


class DashboardScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        root.add_widget(self._top_bar())
        if not ui or ui.get("is_empty"):
            root.add_widget(EmptyState(text="Aucun rapport disponible. Lance un calcul depuis l'accueil."))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=12, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        dashboard_metrics = ui.get("dashboard_metrics", [])
        kpis = GridLayout(cols=4, spacing=12, size_hint_y=None, height=150)
        
        # Power is usually the first one or we find it by label
        power = next((m for m in dashboard_metrics if "Puissance" in m["label"]), None)
        kpis.add_widget(KpiCard("Puissance", power["value"] if power else None, power["unit"] if power else "W", power["status"] if power else "missing"))
        
        arch = next((m for m in dashboard_metrics if m["label"] == "Architecture"), None)
        kpis.add_widget(KpiCard("Architecture", arch["value"] if arch else None, "", arch["status"] if arch else "missing"))
        
        kpis.add_widget(KpiCard("Inconnues", summary.get("unknown_count"), "", "partiel" if summary.get("unknown_count") else "ok"))
        kpis.add_widget(KpiCard("Alertes", summary.get("alert_count"), "", "partiel" if summary.get("alert_count") else "ok"))
        content.add_widget(kpis)

        missing = ui.get("missing_requirements", [])
        if missing:
            content.add_widget(self._missing_panel(missing))

        bento = BentoGrid(size_hint_y=None, height=710)
        bento.add_widget(self._metric_panel("Chaîne énergétique", ui.get("resolved_metrics", [])))
        bento.add_widget(self._subsystems_panel(ui.get("subsystems", [])))
        bento.add_widget(UnknownsPanel(ui.get("unknowns", []), size_hint_y=None))
        bento.add_widget(self._actions_panel())
        content.add_widget(bento)

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=58, spacing=10)
        bar.add_widget(Label(text="STHOME — COCKPIT D'INGÉNIERIE", color=COLORS["BFW"], bold=True, font_size="20sp", halign="left"))
        for text, target in (
            ("RECALCULER", "loading"),
            ("ÉDITER", "edit_parameters"),
            ("JSON", "raw_json"),
            ("ACCUEIL", "home"),
        ):
            btn = ModernButton(text=text, size_hint_x=None, width=140)
            btn.bind(on_release=lambda _, t=target: setattr(self.manager, "current", t))
            bar.add_widget(btn)
        return bar

    def _metric_panel(self, title: str, items: list[dict]) -> PremiumCard:
        panel = PremiumCard(title=title)
        if not items:
            panel.add_widget(EmptyState(text="Toutes les données sont à compléter."))
            return panel
        for item in items:
            if item.get("value") is not None:
                panel.add_widget(MetricRow(item.get("label"), item.get("value"), item.get("unit", ""), item.get("status", ""), item.get("source") or ""))
        return panel

    def _subsystems_panel(self, items: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="Sous-systèmes")
        if not items:
            panel.add_widget(EmptyState(text="Sous-systèmes indisponibles."))
            return panel
        for item in items:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=40, spacing=8)
            row.add_widget(Label(text=item.get("name"), color=COLORS["GS"], font_size="14sp", halign="left", valign="middle"))
            
            status = item.get("status", "inconnu")
            row.add_widget(StatusBadge(status=status, text=status.upper(), size_hint_x=None, width=110))
            
            missing = item.get("missing_count", 0)
            if missing > 0:
                missing_label = Label(text=f"[{missing} à compléter]", color=COLORS["RS"], font_size="12sp", size_hint_x=None, width=120)
                row.add_widget(missing_label)
            
            panel.add_widget(row)
            
            # Sub-items only if resolved
            resolved = item.get("resolved_data", {})
            for k, v in resolved.items():
                if v is not None:
                    panel.add_widget(MetricRow(f"  - {k}", v, status="ok"))
                    
        return panel

    def _missing_panel(self, items: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="DONNÉES NÉCESSAIRES POUR COMPLÉTER LE CALCUL")
        panel.height = 120
        row = BoxLayout(orientation="horizontal", spacing=20)
        label = Label(
            text=f"Il manque {len(items)} données techniques pour fermer le calcul système.",
            color=COLORS["RS"],
            bold=True,
            halign="left"
        )
        row.add_widget(label)
        btn = ModernButton(text="VOIR LES MANQUES", size_hint_x=None, width=200)
        btn.bind(on_release=lambda _: setattr(self.manager, "current", "missing_requirements"))
        row.add_widget(btn)
        panel.add_widget(row)
        return panel

    def _actions_panel(self) -> PremiumCard:
        panel = PremiumCard(title="Accès rapides")
        grid = GridLayout(cols=2, spacing=10)
        actions = [
            ("Données globales", "system_data"),
            ("Pièces", "piece_library"),
            ("Croquis", "sketches"),
            ("Graphiques", "charts"),
            ("3D", "three_d"),
            ("Exports", "exports"),
            ("Architecture", "architecture_choice"),
            ("Édition", "edit_parameters"),
        ]
        for text, target in actions:
            btn = ModernButton(text=text)
            btn.bind(on_release=lambda _, t=target: setattr(self.manager, "current", t))
            grid.add_widget(btn)
        panel.add_widget(grid)
        return panel

    def _find_value(self, ui: dict, label: str):
        for item in ui.get("energy_chain", []):
            if item.get("label") == label:
                return item.get("value")
        return None
