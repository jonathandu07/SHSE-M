import unittest
from unittest.mock import MagicMock
import sys
import os

# CONFIGURATION DU PATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Mock Kivy before import to avoid requiring a display for basic logic tests
from kivy.config import Config
Config.set('graphics', 'multisamples', '0')
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONSOLELOG'] = '1'

# We import the classes to test
from frontend.gui.main import NeumorphicInput, AZERTY_MAP

class TestGUILogic(unittest.TestCase):

    def setUp(self):
        # sauvegarde de la méthode originale
        import kivy.uix.textinput
        self.orig_insert = kivy.uix.textinput.TextInput.insert_text

    def tearDown(self):
        import kivy.uix.textinput
        kivy.uix.textinput.TextInput.insert_text = self.orig_insert

    def test_azerty_mapping(self):
        """Vérifie que les touches AZERTY sont correctement converties."""
        text_input = NeumorphicInput()
        
        def mock_super_insert(instance, substring, from_undo=False):
            instance.text += substring

        import kivy.uix.textinput
        kivy.uix.textinput.TextInput.insert_text = mock_super_insert

        # Simulation
        text_input.insert_text("&")
        text_input.insert_text("é")
        text_input.insert_text("\"")
        
        self.assertEqual(text_input.text, "123")

    def test_comma_replacement(self):
        """Vérifie que la virgule est remplacée par un point."""
        text_input = NeumorphicInput()
        text_input.text = "" 
        
        import kivy.uix.textinput
        kivy.uix.textinput.TextInput.insert_text = lambda inst, s, *args, **kwargs: setattr(inst, 'text', inst.text + s)

        text_input.insert_text("12,5")
        self.assertEqual(text_input.text, "12.5")

    def test_invalid_chars(self):
        """Vérifie que les caractères non numériques sont ignorés."""
        text_input = NeumorphicInput()
        text_input.text = ""
        
        import kivy.uix.textinput
        kivy.uix.textinput.TextInput.insert_text = lambda inst, s, *args, **kwargs: setattr(inst, 'text', inst.text + s)

        text_input.insert_text("12abc34!#")
        self.assertEqual(text_input.text, "1234")

    def test_config_screen_validation(self):
        """Vérifie la validation de la puissance dans ConfigScreen."""
        from frontend.gui.main import ConfigScreen
        
        # Mock de l'App
        app = MagicMock()
        import frontend.gui.main
        frontend.gui.main.App.get_running_app = lambda: app
        
        screen = ConfigScreen(name='config')
        screen.manager = MagicMock() # Mock pour éviter le crash au changement d'écran
        screen.power_input.text = " 250,5 "
        screen.launch_generation()
        
        # Vérifie que la puissance a été castée en float string "250.5"
        self.assertEqual(app.target_power, "250.5")
        self.assertEqual(screen.err.text, "")

    def test_config_screen_invalid(self):
        """Vérifie la gestion d'erreur pour une puissance invalide."""
        from frontend.gui.main import ConfigScreen
        screen = ConfigScreen(name='config')
        
        screen.power_input.text = "abc"
        screen.launch_generation()
        self.assertIn("Entrée invalide", screen.err.text)

if __name__ == '__main__':
    unittest.main()
