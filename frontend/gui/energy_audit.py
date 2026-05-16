# frontend\gui\energy_audit.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty, ListProperty, DictProperty, ObjectProperty
from kivy.graphics import Color, RoundedRectangle
from kivy.app import App
import math

from frontend.gui.components import COLORS, ModernButton, PremiumCard, MetricRow, StatusBadge

STATUS_COLORS = {
    "ok": (30 / 255, 180 / 255, 50 / 255, 1),
    "partiel": (255 / 255, 165 / 255, 0 / 255, 1),
    "impossible": (236 / 255, 25 / 255, 32 / 255, 1),
    "alerte": (255 / 255, 198 / 255, 0 / 255, 1),
    "inconnu": (112 / 255, 112 / 255, 112 / 255, 1),
    "missing": (236 / 255, 25 / 255, 32 / 255, 1),
}

def _get_status_color(status):
    return STATUS_COLORS.get(str(status).lower(), STATUS_COLORS["inconnu"])

class AuditCard(BoxLayout):
    def __init__(self, title="", status=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = [20, 20]
        self.spacing = 10
        
        with self.canvas.before:
            Color(200 / 255, 200 / 255, 200 / 255, 0.35)
            self.shadow = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[24])
            Color(*COLORS["white"])
            self.bg = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[24])

        self.bind(pos=self.update_graphics, size=self.update_graphics)

        header = BoxLayout(size_hint_y=None, height=30, spacing=10)
        if title:
            t = Label(
                text=title.upper(),
                size_hint_x=0.7,
                color=COLORS["BF"],
                bold=True,
                font_size="14sp",
                halign="left",
                valign="middle",
            )
            t.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            header.add_widget(t)
        
        if status:
            s_label = Label(
                text=str(status).upper(),
                size_hint_x=0.3,
                color=_get_status_color(status),
                bold=True,
                font_size="12sp",
                halign="right",
                valign="middle"
            )
            s_label.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            header.add_widget(s_label)
        
        self.add_widget(header)

    def update_graphics(self, *args):
        self.shadow.pos = (self.x + 6, self.y - 6)
        self.shadow.size = self.size
        self.bg.pos = self.pos
        self.bg.size = self.size

class EnergyAuditScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLORS["BL"])
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        
        self.layout = BoxLayout(orientation="vertical", padding=30, spacing=20)
        
        # Header
        header = BoxLayout(size_hint_y=None, height=60, spacing=20)
        header.add_widget(Label(text="AUDIT DE CONFORMITÉ TECHNIQUE", font_size="22sp", bold=True, color=COLORS["BF"], halign="left"))
        
        back = ModernButton(text="RETOUR", size_hint_x=None, width=140)
        back.bind(on_press=lambda *_: setattr(self.manager, "current", "dashboard"))
        header.add_widget(back)
        self.layout.add_widget(header)
        
        self.scroll = ScrollView(do_scroll_x=False)
        self.content = GridLayout(cols=2, spacing=25, size_hint_y=None, padding=[5, 5])
        self.content.bind(minimum_height=self.content.setter("height"))
        
        self.scroll.add_widget(self.content)
        self.layout.add_widget(self.scroll)
        self.add_widget(self.layout)

    def _upd(self, *a):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.content.clear_widgets()
        app = App.get_running_app()
        ui = getattr(app, 'ui_report', {})
        
        if not ui or ui.get("is_empty", True):
            self.content.add_widget(Label(text="Données indisponibles — le backend n'a pas fourni de rapport d'audit.", color=COLORS["RS"]))
            return

        # Résumé
        res_card = AuditCard(title="Résumé Global")
        res_card.size_hint_y = None
        res_card.bind(minimum_height=res_card.setter("height"))
        for item in ui.get("dashboard_metrics", []) + ui.get("missing_requirements", []):
            res_card.add_widget(AuditRow(
                label=item["label"],
                value=item["value"],
                unit=item["unit"],
                status=item["status"],
                source=item.get("source"),
                raw_path=item.get("raw_path")
            ))
        self.content.add_widget(res_card)

        # Energie
        en_card = AuditCard(title="Chaîne Énergétique")
        en_card.size_hint_y = None
        en_card.bind(minimum_height=en_card.setter("height"))
        for item in ui.get("energy_chain", []):
            en_card.add_widget(AuditRow(
                label=item["label"],
                value=item["value"],
                unit=item["unit"],
                status=item["status"],
                source=item.get("source"),
                raw_path=item.get("raw_path")
            ))
        self.content.add_widget(en_card)

        # Inconnues & Alertes
        if ui.get("unknowns") or ui.get("alerts"):
            card_alerts = AuditCard(title="Alertes & Inconnues")
            card_alerts.size_hint_y = None
            card_alerts.bind(minimum_height=card_alerts.setter("height"))
            
            for u in ui.get("unknowns", []):
                msg = f"• {u['name']}: {u['reason']}"
                l = Label(text=msg, color=COLORS["RS"], font_size="11sp", size_hint_y=None, height=24, halign="left", valign="middle")
                l.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
                card_alerts.add_widget(l)
                
            for a in ui.get("alerts", []):
                msg = f"! {a['name']}: {a['detail']}"
                l = Label(text=msg, color=COLORS["RS"], font_size="11sp", size_hint_y=None, height=24, halign="left", valign="middle")
                l.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
                card_alerts.add_widget(l)
                
            self.content.add_widget(card_alerts)

class AuditRow(BoxLayout):
    def __init__(self, label, value, unit="", status="ok", source=None, raw_path=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=2, **kwargs)
        self.padding = [12, 8, 12, 8]
        
        main_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=32, spacing=10)
        
        # Label
        lbl = Label(text=str(label), color=COLORS["GS"], font_size="13sp", size_hint_x=0.4, halign="left", valign="middle")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        main_row.add_widget(lbl)
        
        # Value
        from frontend.gui.components import format_value
        val_text = format_value(value, unit)
        
        val_lbl = Label(text=val_text, color=_get_status_color(status), bold=True, font_size="14sp", size_hint_x=0.35, halign="right", valign="middle")
        val_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        main_row.add_widget(val_lbl)
        
        # Status Badge
        main_row.add_widget(StatusBadge(status=status, text=status.upper(), size_hint_x=None, width=100))
        
        self.add_widget(main_row)
        
        if raw_path:
            path_lbl = Label(text=f"Path: {raw_path}", color=COLORS["GS"], font_size="9sp", size_hint_y=None, height=12, halign="left")
            path_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
            self.add_widget(path_lbl)
            self.height = 32 + 12 + 16
        else:
            self.height = 32 + 16

        with self.canvas.before:
            Color(*COLORS["BL_18"])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[8])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size
