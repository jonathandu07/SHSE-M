from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

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
    StatusBadge,
    UnknownsPanel,
)


class DashboardScreen(Screen):
    def on_enter(self, *_):
        self.refresh()

    def refresh(self) -> None:
        self.clear_widgets()
        app = App.get_running_app()
        ui = dict(app.ui_report or {})
        
        root = BoxLayout(orientation="vertical", padding=12, spacing=10)
        
        if not ui or ui.get("is_empty"):
            root.add_widget(self._top_bar("STHOME COCKPIT"))
            root.add_widget(EmptyState(text="AUCUN RAPPORT DISPONIBLE", action_text="LANCER UN CALCUL", callback=lambda _: setattr(self.manager, "current", "home")))
            self.add_widget(root)
            return

        dash = ui.get("dashboard", {})
        root.add_widget(self._top_bar(dash.get("title", "STHOME COCKPIT")))

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=12, size_hint_y=None, padding=[4, 4])
        content.bind(minimum_height=content.setter("height"))

        # 1. KPI Row (4 cards max)
        kpi_row = BoxLayout(size_hint_y=None, height=110, spacing=12)
        
        # Power Requested
        p_req = self._find_value(ui, "Puissance totale demandée")
        kpi_row.add_widget(KpiCard("Puissance demandée", p_req, "kW"))
        
        # Technical Score
        score = self._find_value(ui, "Score technique")
        kpi_row.add_widget(KpiCard("Score technique", score, "%"))
        
        # Missing & Alerts
        summary = dash.get("summary", {})
        kpi_row.add_widget(KpiCard("Données à compléter", summary.get("missing_count"), "", "alerte" if summary.get("missing_count") else "ok"))
        kpi_row.add_widget(KpiCard("Alertes critiques", summary.get("alert_count"), "", "alerte" if summary.get("alert_count") else "ok"))
        
        content.add_widget(kpi_row)

        # 2. Tier 1: Energy Chain vs Sub-systems
        tier1 = BoxLayout(size_hint_y=None, height=320, spacing=12)
        
        # Energy Chain (Compact)
        energy_panel = self._energy_chain_panel(dash.get("energy_chain", []))
        tier1.add_widget(energy_panel)
        
        # Subsystems
        sub_panel = self._subsystems_panel(dash.get("subsystems", []))
        tier1.add_widget(sub_panel)
        
        content.add_widget(tier1)

        # 3. Tier 2: Missing Summary vs Alerts/Actions
        tier2 = BoxLayout(size_hint_y=None, height=220, spacing=12)
        
        # Missing Summary
        tier2.add_widget(self._missing_summary_panel(summary.get("missing_count", 0)))
        
        # Alerts / Prochaines actions
        tier2.add_widget(self._next_actions_panel(dash.get("alerts", [])))
        
        content.add_widget(tier2)

        # 4. Tier 3: Quick Access
        content.add_widget(self._actions_panel(dash.get("actions", [])))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self, title: str) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=54, spacing=10, padding=[10, 5])
        lbl = Label(text=title.upper(), color=COLORS["BFW"], bold=True, font_size="16sp", halign="left", valign="middle")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        for text, target in (
            ("RECALCULER", "loading"),
            ("ÉDITER", "edit_parameters"),
            ("JSON", "raw_report"),
            ("ACCUEIL", "home"),
        ):
            btn = ModernButton(text=text, size_hint_x=None, width=100, font_size="11sp")
            btn.bind(on_release=lambda _, t=target: setattr(self.manager, "current", t))
            bar.add_widget(btn)
        return bar

    def _energy_chain_panel(self, items: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="Chaîne énergétique", size_hint_x=0.6)
        # Prioritize specific values requested by user
        priority = ["Puissance totale demandée", "Puissance traction", "Mode énergétique", "Puissance bus DC", "Puissance recharge"]
        
        container = BoxLayout(orientation="vertical", spacing=2)
        visible = 0
        for p_label in priority:
            val = next((i for i in items if i.get("label") == p_label), None)
            if val:
                container.add_widget(MetricRow(val["label"], val["value"], val.get("unit", ""), val.get("status", "")))
                visible += 1
        
        # Add others up to 8 total
        for item in items:
            if visible >= 8: break
            if item.get("label") not in priority:
                container.add_widget(MetricRow(item["label"], item["value"], item.get("unit", ""), item.get("status", "")))
                visible += 1
        
        panel.add_widget(container)
        # Adaptive height if very few items
        if visible < 4:
            panel.height = 180
        return panel

    def _subsystems_panel(self, items: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="Sous-systèmes", size_hint_x=0.4)
        scroll = ScrollView(do_scroll_x=False)
        container = BoxLayout(orientation="vertical", spacing=2, size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))
        
        for item in items:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=32, spacing=8)
            name = Label(text=item.get("name"), color=COLORS["GS"], font_size="11sp", halign="left", size_hint_x=0.6)
            name.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
            row.add_widget(name)
            row.add_widget(StatusBadge(status=item.get("status", "ok"), size=(70, 20), font_size="9sp", size_hint_x=None, width=80))
            container.add_widget(row)
            
        scroll.add_widget(container)
        panel.add_widget(scroll)
        return panel

    def _missing_summary_panel(self, count: int) -> PremiumCard:
        panel = PremiumCard(title="Données à compléter", size_hint_x=0.5, bg=COLORS["RS_18"] if count > 0 else COLORS["BL"])
        if count == 0:
            panel.add_widget(Label(text="Système complet.", color=COLORS["NG"], bold=True))
        else:
            panel.add_widget(Label(text=f"{count} manques identifiés.", color=COLORS["RS"], bold=True, font_size="14sp"))
            btn = GhostButton(text="VOIR LES DÉTAILS", size_hint_y=None, height=38)
            btn.bind(on_release=lambda _: setattr(self.manager, "current", "missing_requirements"))
            panel.add_widget(btn)
        return panel

    def _next_actions_panel(self, alerts: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="Alertes / Actions", size_hint_x=0.5)
        if not alerts:
            panel.add_widget(Label(text="Aucune alerte critique.", color=COLORS["NG"], font_size="12sp"))
        else:
            container = BoxLayout(orientation="vertical", spacing=2)
            for alt in alerts[:3]:
                container.add_widget(MetricRow(alt.get("label", "Alerte"), alt.get("value", ""), status="alerte"))
            panel.add_widget(container)
        return panel

    def _actions_panel(self, actions: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="Accès rapides", height=100, size_hint_y=None)
        grid = GridLayout(cols=6, spacing=8)
        for act in actions:
            btn = ModernButton(text=act["label"].upper(), font_size="10sp")
            btn.bind(on_release=lambda _, t=act["target"]: setattr(self.manager, "current", t))
            grid.add_widget(btn)
        panel.add_widget(grid)
        return panel

    def _find_value(self, ui: dict, label: str):
        for item in ui.get("dashboard", {}).get("energy_chain", []):
            if item.get("label") == label:
                return item.get("value")
        return None
