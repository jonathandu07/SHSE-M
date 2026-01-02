import unittest
import sys
import os
import importlib

# CONFIGURATION DU PATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

class TestAssetsCompliance(unittest.TestCase):
    """
    Vérifie que tous les scripts de rendu (sketches et charts) respectent l'interface attendue.
    """

    def test_sketches_2d_compliance(self):
        """Vérifie que tous les croquis 2D ont une fonction draw(ax, piece)."""
        sketches_dir = os.path.join(BASE_DIR, "frontend", "pieces", "sketches_2d")
        if not os.path.exists(sketches_dir):
            self.skipTest("Dossier sketches_2d introuvable")
            
        files = [f for f in os.listdir(sketches_dir) if f.endswith(".py") and f != "__init__.py"]
        
        count = 0
        for f in files:
            module_path = f"frontend.pieces.sketches_2d.{f[:-3]}"
            with self.subTest(module=module_path):
                try:
                    mod = importlib.import_module(module_path)
                    self.assertTrue(hasattr(mod, 'draw'), f"{f} manque de la fonction 'draw'")
                    count += 1
                except Exception as e:
                    self.fail(f"Erreur d'import sur {f}: {e}")
        print(f"\n[TestAssetsCompliance] {count} sketches 2D vérifiés.")

    def test_charts_compliance(self):
        """Vérifie que tous les graphiques (charts) ont une fonction plot_data(ax, piece)."""
        charts_dir = os.path.join(BASE_DIR, "frontend", "pieces", "charts")
        if not os.path.exists(charts_dir):
            self.skipTest("Dossier charts introuvable")
            
        files = [f for f in os.listdir(charts_dir) if f.endswith(".py") and f != "__init__.py"]
        
        count = 0
        for f in files:
            module_path = f"frontend.pieces.charts.{f[:-3]}"
            with self.subTest(module=module_path):
                try:
                    mod = importlib.import_module(module_path)
                    self.assertTrue(hasattr(mod, 'plot_data'), f"{f} manque de la fonction 'plot_data'")
                    count += 1
                except Exception as e:
                    self.fail(f"Erreur d'import sur {f}: {e}")
        print(f"\n[TestAssetsCompliance] {count} charts radar vérifiés.")

if __name__ == '__main__':
    unittest.main()
