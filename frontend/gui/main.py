"""
SHSE-M - Interface Technique Haute Fidélité
Design : Neumorphisme Premium & Bento Design
Palette de Couleurs Utilisateur Stricte
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.core.window import Window
from kivy.clock import Clock
import os
import sys
import threading

# Palette de couleurs (RGB normalisé)
COLORS = {
    'BL': (244/255, 254/255, 254/255, 1),
    'GW': (247/255, 247/255, 255/255, 1),
    'BG': (229/255, 229/255, 229/255, 1),
    'GF': (217/255, 217/255, 217/255, 1),
    'GAXD': (112/255, 112/255, 112/255, 1),
    'VG': (107/255, 108/255, 102/255, 1),
    'JV': (255/255, 198/255, 0/255, 1),
    'BF': (5/255, 20/255, 64/255, 1),
    'BA': (129/255, 161/255, 184/255, 1),
    'BM': (3/255, 34/255, 76/255, 1),
    'BFW': (9/255, 18/255, 38/255, 1),
    'NF': (30/255, 30/255, 30/255, 1),
    'white': (1, 1, 1, 1),
    'black': (0, 0, 0, 1),
    'RF': (236/255, 25/255, 32/255, 1),
}

class PremiumCard(BoxLayout):
    """Carte Bento avec Neumorphisme doux."""
    def __init__(self, title="", **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = [20, 20]
        self.spacing = 10
        with self.canvas.before:
            # Ombre portée (Shadow)
            Color(200/255, 200/255, 200/255, 0.4)
            self.shadow = RoundedRectangle(pos=(0,0), size=(0,0), radius=[24])
            # Fond (Lumière)
            Color(*COLORS['white'])
            self.bg = RoundedRectangle(pos=(0,0), size=(0,0), radius=[24])
        self.bind(pos=self.update_graphics, size=self.update_graphics)
        
        if title:
            self.add_widget(Label(
                text=title.upper(),
                size_hint_y=None, height=30,
                color=COLORS['BF'],
                bold=True, font_size='14sp',
                halign='left'
            ))

    def update_graphics(self, *args):
        self.shadow.pos = (self.x + 6, self.y - 6)
        self.shadow.size = self.size
        self.bg.pos = self.pos
        self.bg.size = self.size

from kivy.lang import Builder

# Styles KV pour assurer une réactivité parfaite
Builder.load_string("""
<NeumorphicInput>:
    background_normal: ''
    background_active: ''
    background_color: 0, 0, 0, 0
    font_size: '32sp'
    padding: [20, 20]
    halign: 'center'
    cursor_color: 0.02, 0.08, 0.25, 1
    foreground_color: 0.02, 0.08, 0.25, 1
    canvas.before:
        Color:
            rgba: 0.85, 0.85, 0.85, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [15]
        Color:
            rgba: 0.97, 0.97, 1, 1
        RoundedRectangle:
            pos: self.x + 2, self.y + 2
            size: self.width - 4, self.height - 4
            radius: [13]
""")

class NeumorphicInput(TextInput):
    """Champ de saisie neumorphique corrigé."""
    pass

class ModernButton(Button):
    """Bouton Premium avec effet visuel au clic."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0,0,0,0)
        self.bold = True
        self.font_size = '18sp'
        self.color = COLORS['white']
        with self.canvas.before:
            self.bg_color = Color(*COLORS['BF'])
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
        self.bind(pos=self.update_graphics, size=self.update_graphics)

    def on_state(self, instance, value):
        if value == 'down':
            self.bg_color.rgba = COLORS['BM']
        else:
            self.bg_color.rgba = COLORS['BF']

    def update_graphics(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class ConfigScreen(Screen):
    """Écran initial : Entrée de puissance simplifiée et robuste."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Fond principal
        with self.canvas.before:
            Color(*COLORS['BL'])
            RoundedRectangle(pos=(0,0), size=(2000, 2000))
            
        l = BoxLayout(orientation='vertical', padding=[100, 60], spacing=40)
        
        # En-tête
        header = BoxLayout(orientation='vertical', size_hint_y=0.4)
        header.add_widget(Label(text="SHSE-M", font_size='64sp', bold=True, color=COLORS['BF']))
        header.add_widget(Label(text="ENGINE GENERATOR", font_size='24sp', color=COLORS['BA'], letter_spacing=5))
        l.add_widget(header)
        
        # Saisie
        main_card = PremiumCard(size_hint_y=0.4)
        main_card.add_widget(Label(text="PUISSANCE CIBLE (kW)", color=COLORS['BF'], bold=True, font_size='18sp'))
        
        self.power_input = NeumorphicInput(text="150")
        # Forcer le focus au clic
        self.power_input.bind(on_touch_down=lambda i, q: i.focus == True if i.collide_point(*q.pos) else False)
        main_card.add_widget(self.power_input)
        
        l.add_widget(main_card)
        
        # Bouton
        self.gen_btn = ModernButton(text="GÉNÉRER LE SYSTÈME", size_hint_y=0.2)
        self.gen_btn.bind(on_press=self.launch_generation)
        l.add_widget(self.gen_btn)
        
        self.add_widget(l)

    def launch_generation(self, instance):
        if self.power_input.text:
            app = App.get_running_app()
            app.target_power = self.power_input.text
            self.manager.current = 'loading'

class LoadingScreen(Screen):
    """Écran de calcul avec animation."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=100)
        self.label = Label(text="Séquençage des calculs physiques...", font_size='24sp', color=COLORS['BF'])
        self.layout.add_widget(self.label)
        self.add_widget(self.layout)

    def on_enter(self):
        Clock.schedule_once(self.run_sim, 0.5)

    def run_sim(self, dt):
        threading.Thread(target=self.do_math).start()

    def do_math(self):
        import time
        steps = ["Architecture...", "Cylindrée...", "Vilebrequin...", "Thermodynamique...", "Finalisation..."]
        for s in steps:
            Clock.schedule_once(lambda dt, msg=f"Calcul : {s}": setattr(self.label, 'text', msg))
            time.sleep(0.6)
        Clock.schedule_once(lambda dt: setattr(self.manager, 'current', 'dashboard'))

class DashboardScreen(Screen):
    """Le cerveau de l'application : Tableau de bord Bento."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=20)
        
        # Barre d'infos
        top = BoxLayout(size_hint_y=0.1, spacing=20)
        top.add_widget(Label(text="RÉSULTATS DE GÉNÉRATION", font_size='24sp', bold=True, color=COLORS['BF'], size_hint_x=0.7, halign='left'))
        back = Button(text="RECONFIGURER", size_hint_x=0.3, background_color=(0,0,0,0), color=COLORS['GAXD'], underline=True)
        back.bind(on_press=lambda x: setattr(self.manager, 'current', 'config'))
        top.add_widget(back)
        self.layout.add_widget(top)
        
        # Grille Bento
        grid = GridLayout(cols=3, rows=2, spacing=20, size_hint_y=0.8)
        
        # Card 1: Chiffres Clés
        c1 = PremiumCard(title="Performances")
        c1.add_widget(Label(text="98.2 kW", font_size='36sp', bold=True, color=COLORS['BF']))
        c1.add_widget(Label(text="Rendement estimé : 44%", color=COLORS['JV']))
        grid.add_widget(c1)
        
        # Card 2: Masse & Encombrement
        c2 = PremiumCard(title="Dimensions")
        c2.add_widget(Label(text="142 kg", font_size='36sp', bold=True, color=COLORS['BF']))
        c2.add_widget(Label(text="Volume : 0.45 m³", color=COLORS['BA']))
        grid.add_widget(c2)
        
        # Card 3: Pièces
        c3 = PremiumCard(title="Inventaire")
        c3.add_widget(Label(text="58", font_size='48sp', bold=True, color=COLORS['BF']))
        c3.add_widget(Label(text="Composants optimisés", color=COLORS['GAXD']))
        grid.add_widget(c3)
        
        # Card 4: Action Liste
        c4 = PremiumCard(title="Accès Rapide", size_hint_x=2)
        btn_grid = GridLayout(cols=2, spacing=10)
        btn_grid.add_widget(ModernButton(text="LISTE DES PIÈCES", font_size='14sp'))
        btn_grid.add_widget(ModernButton(text="VUE VECTORIELLE", font_size='14sp'))
        btn_grid.add_widget(ModernButton(text="DOSSIER PDF", font_size='14sp'))
        btn_grid.add_widget(ModernButton(text="SIMULATION LIVE", font_size='14sp'))
        c4.add_widget(btn_grid)
        grid.add_widget(c4)
        
        # Card 5: Santé Système
        c5 = PremiumCard(title="Alertes")
        c5.add_widget(Label(text="OK", font_size='48sp', bold=True, color=(30/255, 180/255, 50/255, 1)))
        c5.add_widget(Label(text="Aucune contrainte critique", color=COLORS['GAXD']))
        grid.add_widget(c5)
        
        self.layout.add_widget(grid)
        self.add_widget(self.layout)

class SHSEMApp(App):
    target_power = StringProperty("150")
    
    def build(self):
        Window.clearcolor = COLORS['BL']
        Window.size = (1200, 800)
        
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(ConfigScreen(name='config'))
        sm.add_widget(LoadingScreen(name='loading'))
        sm.add_widget(DashboardScreen(name='dashboard'))
        return sm

if __name__ == '__main__':
    SHSEMApp().run()
