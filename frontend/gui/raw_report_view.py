import json
import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock

class RawReportViewScreen(Screen):
    """Displays the raw backend report JSON for transparency and debugging."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', spacing=10, padding=20)
        
        # Header
        header = BoxLayout(size_hint_y=None, height=50, spacing=10)
        header.add_widget(Label(text="[b]RAPPORT BRUT BACKEND[/b]", markup=True, font_size='18sp'))
        
        btn_back = Button(text="Retour", size_hint_x=None, width=100)
        btn_back.bind(on_release=self.go_back)
        header.add_widget(btn_back)
        layout.add_widget(header)
        
        # JSON Area
        self.json_display = TextInput(
            text="Aucune donnée disponible.",
            readonly=True,
            font_name='Roboto', # Monospace would be better but let's stick to standard
            background_color=(0.1, 0.1, 0.1, 1),
            foreground_color=(0.9, 0.9, 0.9, 1),
            font_size='12sp'
        )
        layout.add_widget(self.json_display)
        
        # Footer Actions
        footer = BoxLayout(size_hint_y=None, height=50, spacing=10)
        
        btn_copy = Button(text="Copier dans le presse-papier")
        btn_copy.bind(on_release=self.copy_to_clipboard)
        footer.add_widget(btn_copy)
        
        btn_save = Button(text="Sauvegarder JSON")
        btn_save.bind(on_release=self.save_to_file)
        footer.add_widget(btn_save)
        
        layout.add_widget(footer)
        self.add_widget(layout)
        
        self.status_label = Label(text="", size_hint_y=None, height=30, color=(0.5, 0.8, 0.5, 1))
        layout.add_widget(self.status_label)

    def on_enter(self):
        """Load the raw report from the app instance."""
        from kivy.app import App
        app = App.get_running_app()
        
        if hasattr(app, 'raw_backend_report') and app.raw_backend_report:
            try:
                formatted_json = json.dumps(app.raw_backend_report, indent=4, ensure_ascii=False)
                self.json_display.text = formatted_json
            except Exception as e:
                self.json_display.text = f"Erreur de formatage : {str(e)}"
        else:
            self.json_display.text = "Aucune donnée disponible - Lancez un calcul d'abord."

    def go_back(self, instance):
        self.manager.current = 'dashboard'

    def copy_to_clipboard(self, instance):
        Clipboard.copy(self.json_display.text)
        self.show_status("Copié !")

    def save_to_file(self, instance):
        # In a real app, we'd show a file chooser. For now, save to outputs/last_report.json
        try:
            os.makedirs("outputs", exist_ok=True)
            path = os.path.join("outputs", "last_report.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.json_display.text)
            self.show_status(f"Sauvegardé dans {path}")
        except Exception as e:
            self.show_status(f"Erreur : {str(e)}")

    def show_status(self, msg):
        self.status_label.text = msg
        Clock.schedule_once(self.clear_status, 3)

    def clear_status(self, dt):
        self.status_label.text = ""
