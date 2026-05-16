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
        
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)
        
        if not ui or ui.get("is_empty"):
            root.add_widget(self._top_bar("STHOME COCKPIT"))
            root.add_widget(EmptyState(text="Aucun rapport disponible. Lance un calcul depuis l'accueil."))
            self.add_widget(root)
            return

        dash = ui.get("dashboard", {})
        root.add_widget(self._top_bar(dash.get("title", "STHOME COCKPIT")))

        scroll = ScrollView(do_scroll_x=False, bar_width=4)
        content = BoxLayout(orientation="vertical", spacing=16, size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # 1. KPIs Section
        kpis = GridLayout(cols=4, spacing=16, size_hint_y=None, height=130)
        for kpi in dash.get("kpis", []):
            kpis.add_widget(KpiCard(kpi["label"], kpi["value"], kpi.get("unit", ""), kpi.get("status", "ok")))
        
        # Add summary counts as KPIs
        summary = dash.get("summary", {})
        kpis.add_widget(KpiCard("Données à compléter", summary.get("missing_count"), "", "alerte" if summary.get("missing_count") else "ok"))
        kpis.add_widget(KpiCard("Alertes critiques", summary.get("alert_count"), "", "alerte" if summary.get("alert_count") else "ok"))
        
        content.add_widget(kpis)

        # 2. Missing Requirements Alert
        if summary.get("missing_count", 0) > 0:
            content.add_widget(self._missing_alert(summary.get("missing_count")))

        # 3. Main Bento Grid
        # Fixed height for bento cards to prevent overlap, use scroll within them if needed
        bento = BentoGrid(cols=2, spacing=16, size_hint_y=None, height=600)
        
        # Energy Chain (max 8)
        energy_list = dash.get("energy_chain", [])[:8]
        bento.add_widget(self._metric_panel("Chaîne énergétique", energy_list))
        
        # Subsystems
        bento.add_widget(self._subsystems_panel(dash.get("subsystems", [])))
        
        content.add_widget(bento)

        # 4. Quick Actions
        content.add_widget(self._actions_panel(dash.get("actions", [])))

        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)

    def _top_bar(self, title: str) -> BoxLayout:
        bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        lbl = Label(text=title.upper(), color=COLORS["BFW"], bold=True, font_size="18sp", halign="left", valign="middle")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        bar.add_widget(lbl)
        
        for text, target in (
            ("RECALCULER", "loading"),
            ("ÉDITER", "edit_parameters"),
            ("ACCUEIL", "home"),
        ):
            btn = ModernButton(text=text, size_hint_x=None, width=120, font_size="12sp")
            btn.bind(on_release=lambda _, t=target: setattr(self.manager, "current", t))
            bar.add_widget(btn)
        return bar

    def _missing_alert(self, count: int) -> PremiumCard:
        panel = PremiumCard(bg=COLORS["RS_18"], border=COLORS["RS"], height=70, size_hint_y=None)
        panel.padding = [20, 10]
        row = BoxLayout(orientation="horizontal", spacing=20)
        row.add_widget(Label(
            text=f"Cockpit incomplet : {count} données manquantes pour fermer le calcul système.",
            color=COLORS["RS"],
            bold=True,
            halign="left",
            font_size="13sp"
        ))
        btn = ModernButton(text="RÉSOUDRE LES MANQUES", size_hint_x=None, width=200, font_size="12sp")
        btn.bind(on_release=lambda _: setattr(self.manager, "current", "missing_requirements"))
        row.add_widget(btn)
        panel.add_widget(row)
        return panel

    def _metric_panel(self, title: str, items: list[dict]) -> PremiumCard:
        panel = PremiumCard(title=title)
        if not items:
            panel.add_widget(EmptyState(text="Aucune donnée résolue dans cette section."))
            return panel
        
        container = BoxLayout(orientation="vertical", spacing=2)
        for item in items:
            container.add_widget(MetricRow(
                item.get("label"), 
                item.get("value"), 
                item.get("unit", ""), 
                item.get("status", ""),
                source=item.get("source", "")
            ))
        panel.add_widget(container)
        return panel

    def _subsystems_panel(self, items: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="États sous-systèmes")
        if not items:
            panel.add_widget(EmptyState(text="Sous-systèmes indisponibles."))
            return panel
            
        scroll = ScrollView(do_scroll_x=False)
        container = BoxLayout(orientation="vertical", spacing=4, size_hint_y=None)
        container.bind(minimum_height=container.setter("height"))
        
        for item in items:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=36, spacing=10)
            name_lbl = Label(text=item.get("name"), color=COLORS["GS"], font_size="13sp", halign="left", valign="middle", size_hint_x=0.4)
            name_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
            row.add_widget(name_lbl)
            
            status = item.get("status", "inconnu")
            row.add_widget(StatusBadge(status=status))
            
            missing = item.get("missing_count", 0)
            if missing > 0:
                m_lbl = Label(text=f"{missing} à compléter", color=COLORS["RS"], font_size="10sp", halign="right", size_hint_x=0.3)
                m_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
                row.add_widget(m_lbl)
            else:
                row.add_widget(Widget(size_hint_x=0.3))
                
            container.add_widget(row)
            
        scroll.add_widget(container)
        panel.add_widget(scroll)
        return panel

    def _actions_panel(self, actions: list[dict]) -> PremiumCard:
        panel = PremiumCard(title="Accès rapides / Cockpit étendu", height=120, size_hint_y=None)
        grid = GridLayout(cols=5, spacing=10)
        for act in actions:
            btn = ModernButton(text=act["label"].upper(), font_size="11sp")
            btn.bind(on_release=lambda _, t=act["target"]: setattr(self.manager, "current", t))
            grid.add_widget(btn)
        panel.add_widget(grid)
        return panel

    def _find_value(self, ui: dict, label: str):
        for item in ui.get("energy_chain", []):
            if item.get("label") == label:
                return item.get("value")
        return None
