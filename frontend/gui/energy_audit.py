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

# Réutilisation de la palette globale
COLORS = {
    "BL": (244 / 255, 254 / 255, 254 / 255, 1),
    "GW": (247 / 255, 247 / 255, 255 / 255, 1),
    "BG": (229 / 255, 229 / 255, 229 / 255, 1),
    "GF": (217 / 255, 217 / 255, 217 / 255, 1),
    "GAXD": (112 / 255, 112 / 255, 112 / 255, 1),
    "VG": (107 / 255, 108 / 255, 102 / 255, 1),
    "JV": (255 / 255, 198 / 255, 0 / 255, 1),
    "BF": (5 / 255, 20 / 255, 64 / 255, 1),
    "BA": (129 / 255, 161 / 255, 184 / 255, 1),
    "BM": (3 / 255, 34 / 255, 76 / 255, 1),
    "BFW": (9 / 255, 18 / 255, 38 / 255, 1),
    "NF": (30 / 255, 30 / 255, 30 / 255, 1),
    "white": (1, 1, 1, 1),
    "black": (0, 0, 0, 1),
    "RF": (236 / 255, 25 / 255, 32 / 255, 1),
}

STATUS_COLORS = {
    "ok": (30 / 255, 180 / 255, 50 / 255, 1),
    "partiel": (255 / 255, 165 / 255, 0 / 255, 1),
    "impossible": (236 / 255, 25 / 255, 32 / 255, 1),
    "alerte": (255 / 255, 198 / 255, 0 / 255, 1),
    "inconnu": (112 / 255, 112 / 255, 112 / 255, 1),
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

class AuditRow(BoxLayout):
    def __init__(self, label, value, unit="", status="ok", source=None, unknowns=None, notes=None, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=2, **kwargs)
        self.padding = [12, 8, 12, 8]
        
        main_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=32, spacing=10)
        
        # Label
        lbl = Label(text=label, color=COLORS["GAXD"], font_size="13sp", size_hint_x=0.4, halign="left", valign="middle")
        lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        main_row.add_widget(lbl)
        
        # Value
        val_text = "INCONNU" if value is None else f"{value}"
        if unit and value is not None:
            val_text += f" {unit}"
        
        val_lbl = Label(text=val_text, color=_get_status_color(status), bold=True, font_size="14sp", size_hint_x=0.35, halign="right", valign="middle")
        val_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
        main_row.add_widget(val_lbl)
        
        # Status Badge
        badge = Label(text=status.upper(), color=_get_status_color(status), bold=True, font_size="10sp", size_hint_x=0.25, halign="right", valign="middle")
        main_row.add_widget(badge)
        
        self.add_widget(main_row)
        
        # Extra info (collapsible or small text)
        extras = []
        if source: extras.append(f"Source: {source}")
        if unknowns: extras.append(f"Inconnues: {', '.join(unknowns)}")
        if notes: 
            if isinstance(notes, list): extras.extend([f"Note: {n}" for n in notes])
            else: extras.append(f"Note: {notes}")
            
        if extras:
            extra_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=2)
            for ex in extras:
                ex_lbl = Label(text=ex, color=COLORS["BA"], font_size="10sp", size_hint_y=None, height=16, halign="left", valign="middle")
                ex_lbl.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
                extra_box.add_widget(ex_lbl)
            extra_box.height = len(extras) * 18
            self.add_widget(extra_box)
            self.height = 32 + extra_box.height + 16
        else:
            self.height = 32 + 16

        with self.canvas.before:
            Color(COLORS["GW"][0], COLORS["GW"][1], COLORS["GW"][2], 0.5)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[8])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *a):
        self.rect.pos = self.pos
        self.rect.size = self.size

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
        header.add_widget(Label(text="AUDIT DE CONFORMITÉ ÉNERGÉTIQUE", font_size="22sp", bold=True, color=COLORS["BF"], halign="left"))
        
        from main import ModernButton # Type: ignore
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
        self.content.clear_widgets()
        app = App.get_running_app()
        results = app.simulation_results
        
        # Extraction du rapport de stratégie
        strat = results.get("strategie_energie", {})
        bilan = strat.get("bilan_bus_dc", {})
        env = strat.get("enveloppe_batterie", {})
        
        # 1. Synthèse Générale
        card_syn = AuditCard(title="Synthèse Générale", status=strat.get("statut", "inconnu"))
        card_syn.size_hint_y = None
        card_syn.height = 220
        
        card_syn.add_widget(AuditRow("Mode Énergétique", strat.get("mode_energetique"), status="ok" if strat.get("mode_energetique") else "partiel"))
        card_syn.add_widget(AuditRow("Décision", strat.get("decision", {}).get("raison"), status="ok"))
        
        card_syn.add_widget(AuditRow("Cible Utilisateur", app.target_power, unit="kW", status="ok"))
        p_sortie = bilan.get("puissance_sortie_demandee_w")
        card_syn.add_widget(AuditRow("Puissance Normalisée", p_sortie, unit="W", status="ok" if p_sortie is not None else "impossible"))
        
        self.content.add_widget(card_syn)
        
        # 2. Chaîne Énergétique
        card_chain = AuditCard(title="Chaîne de Puissance", size_hint_y=None)
        card_chain.bind(minimum_height=card_chain.setter("height"))
        
        chain_data = [
            ("Usage Électrique", "puissance_electrique_usage_w", "W"),
            ("Auxiliaires", "puissance_auxiliaire_w", "W"),
            ("Recharge Batterie", "puissance_recharge_retenue_w", "W"),
            ("Bus DC Total", "puissance_bus_dc_totale_w", "W"),
            ("Bus DC Instantané", "puissance_bus_dc_instantanee_w", "W"),
            ("Génération Intermittente (Beta)", "fraction_temps_generation_beta", ""),
            ("Alt. Électrique Requise", "puissance_alternateur_electrique_requise_w", "W"),
            ("Alt. Mécanique Requise", "puissance_mecanique_alternateur_requise_w", "W"),
            ("MT Requise", "puissance_moteur_thermique_requise_w", "W"),
        ]
        
        for label, key, unit in chain_data:
            val = bilan.get(key)
            # Simuler la récupération des détails si présents dans une structure parallèle ou si la clé contient un dict
            # Pour l'instant on utilise le statut global ou déduit
            status = "ok" if val is not None else "partiel"
            card_chain.add_widget(AuditRow(label, val, unit=unit, status=status))
            
        self.content.add_widget(card_chain)
        
        # 3. Batterie
        card_bat = AuditCard(title="Enveloppe Batterie", status=env.get("statut", "ok"))
        card_bat.size_hint_y = None
        card_bat.height = 300
        
        card_bat.add_widget(AuditRow("Recharge Recommandée", env.get("p_charge_recommandee_w"), unit="W"))
        card_bat.add_widget(AuditRow("Raison Limitante", env.get("raison_limite")))
        
        limites = env.get("limites_actives", {})
        if limites:
            l_box = BoxLayout(orientation="vertical", size_hint_y=None, height=len(limites)*20)
            for l_name, l_val in limites.items():
                l_box.add_widget(Label(text=f"• {l_name}: {l_val} W", color=COLORS["GAXD"], font_size="11sp", halign="left"))
            card_bat.add_widget(l_box)
            
        self.content.add_widget(card_bat)
        
        # 4. Alternateur / Boîte / Thermique
        card_mech = AuditCard(title="Chaîne Mécanique (Alternateur/Boîte/MT)")
        card_mech.size_hint_y = None
        card_mech.height = 300
        
        card_mech.add_widget(AuditRow("Rapport de Boîte", bilan.get("rapport_boite_optimal")))
        card_mech.add_widget(AuditRow("Régime Alternateur", bilan.get("regime_alternateur_rpm"), unit="tr/min"))
        card_mech.add_widget(AuditRow("Couple Alternateur", bilan.get("couple_alternateur_nm"), unit="Nm"))
        
        p_retenu = strat.get("point_retenu", {})
        if p_retenu:
            card_mech.add_widget(AuditRow("Régime MT", p_retenu.get("rpm_moteur"), unit="tr/min"))
            card_mech.add_widget(AuditRow("Couple MT Requis", p_retenu.get("exigences", {}).get("couple_moteur_requis_Nm"), unit="Nm"))
            
            # Rendements et Pertes
            rendements = p_retenu.get("rendements", {})
            if rendements:
                card_mech.add_widget(AuditRow("Rendement Global", rendements.get("global"), unit="%", status="ok"))
            
        self.content.add_widget(card_mech)

        # 5. Transitoire
        trans = strat.get("validation_transitoire", {})
        card_trans = AuditCard(title="Validation Transitoire", status=trans.get("statut", "inconnu"))
        card_trans.size_hint_y = None
        card_trans.height = 200
        
        card_trans.add_widget(AuditRow("Puissance Accessible", trans.get("p_accessible_w"), unit="W"))
        card_trans.add_widget(AuditRow("Constante de temps (Tau)", trans.get("tau_s"), unit="s"))
        card_trans.add_widget(AuditRow("Rampe", trans.get("rampe_puissance_w_s"), unit="W/s"))
        
        self.content.add_widget(card_trans)
        
        # 6. Alertes et Inconnues
        card_alerts = AuditCard(title="Alertes & Inconnues", size_hint_y=None)
        card_alerts.bind(minimum_height=card_alerts.setter("height"))
        
        inc = strat.get("inconnues", {})
        for bucket, color_name in [("impossibles", "impossible"), ("partielles", "partiel")]:
            items = inc.get(bucket, [])
            if items:
                card_alerts.add_widget(Label(text=bucket.upper(), color=STATUS_COLORS[color_name], bold=True, size_hint_y=None, height=24))
                for item in items:
                    msg = f"• {item.get('nom')}: {item.get('raison')}"
                    l = Label(text=msg, color=COLORS["BF"], font_size="11sp", size_hint_y=None, height=24, halign="left", valign="middle")
                    l.bind(size=lambda i, *_: setattr(i, "text_size", (i.width, None)))
                    card_alerts.add_widget(l)
                    
        self.content.add_widget(card_alerts)
