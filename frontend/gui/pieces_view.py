from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.app import App
from .report_adapter import extract_piece_list

class PieceLibraryScreen(Screen):
    """Displays a list of all components/pieces built by the backend."""
    
    def on_enter(self):
        self.refresh()

    def refresh(self):
        self.clear_widgets()
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        header = BoxLayout(size_hint_y=None, height=50, spacing=10)
        header.add_widget(Label(text="[b]BIBLIOTHÈQUE DES PIÈCES[/b]", markup=True, font_size='18sp'))
        
        btn_back = Button(text="Retour", size_hint_x=None, width=100)
        btn_back.bind(on_release=self.go_back)
        header.add_widget(btn_back)
        layout.add_widget(header)
        
        app = App.get_running_app()
        pieces = []
        if hasattr(app, 'raw_backend_report') and app.raw_backend_report:
            pieces = extract_piece_list(app.raw_backend_report)
            
        if not pieces:
            layout.add_widget(Label(text="Pièces indisponibles — le backend n’a pas fourni de données pièces.", color=(0.7, 0.7, 0.7, 1)))
        else:
            scroll = ScrollView()
            grid = GridLayout(cols=1, spacing=10, size_hint_y=None)
            grid.bind(minimum_height=grid.setter('height'))
            
            for p in pieces:
                btn = Button(
                    text=f"{p['name'].replace('_', ' ').title()} ({p['type']})",
                    size_hint_y=None,
                    height=60,
                    background_color=(0.2, 0.3, 0.4, 1)
                )
                btn.piece_data = p
                btn.bind(on_release=self.view_detail)
                grid.add_widget(btn)
            
            scroll.add_widget(grid)
            layout.add_widget(scroll)
            
        self.add_widget(layout)

    def view_detail(self, instance):
        app = App.get_running_app()
        app.selected_piece = instance.piece_data
        self.manager.current = 'piece_detail'

    def go_back(self, instance):
        self.manager.current = 'dashboard'

class PieceDetailScreen(Screen):
    """Displays detailed technical data for a specific piece."""
    
    def on_enter(self):
        self.refresh()

    def refresh(self):
        self.clear_widgets()
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        app = App.get_running_app()
        piece = getattr(app, 'selected_piece', None)
        
        header = BoxLayout(size_hint_y=None, height=50, spacing=10)
        title = piece['name'].replace('_', ' ').title() if piece else "Détail Pièce"
        header.add_widget(Label(text=f"[b]{title}[/b]", markup=True, font_size='18sp'))
        
        btn_back = Button(text="Retour", size_hint_x=None, width=100)
        btn_back.bind(on_release=self.go_back)
        header.add_widget(btn_back)
        layout.add_widget(header)
        
        if not piece:
            layout.add_widget(Label(text="Aucune pièce sélectionnée."))
        else:
            scroll = ScrollView()
            details = GridLayout(cols=2, spacing=10, padding=10, size_hint_y=None)
            details.bind(minimum_height=details.setter('height'))
            
            data = piece.get('data', {})
            if not data:
                layout.add_widget(Label(text="Aucun détail technique disponible pour cette pièce."))
            else:
                # Flatten nested data for display
                self._add_nested_details(details, data)
                
            scroll.add_widget(details)
            layout.add_widget(scroll)
            
        self.add_widget(layout)

    def _add_nested_details(self, grid, data, prefix=""):
        for k, v in data.items():
            if isinstance(v, dict):
                self._add_nested_details(grid, v, f"{prefix}{k} > ")
            elif k not in ("inconnues", "alertes", "notes_modele"):
                grid.add_widget(Label(text=f"{prefix}{k}", size_hint_x=0.4, halign='left', color=(0.8, 0.8, 0.8, 1)))
                grid.add_widget(Label(text=str(v), size_hint_x=0.6, halign='left'))

    def go_back(self, instance):
        self.manager.current = 'piece_library'
