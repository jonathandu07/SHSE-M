import unittest
import sys
import os
import importlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class TestPiecesCompliance(unittest.TestCase):
    """
    Vérifie que tous les fichiers dans backend/pieces respectent le contrat d'interface.
    Contrat:
    - Une classe 'Piece'
    - Une méthode 'dimensionner'
    - Une méthode 'decrire'
    - Un attribut 'nom'
    """

    def test_all_pieces_implementation(self):
        pieces_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../pieces'))
        files = os.listdir(pieces_dir)
        
        count = 0
        for f in files:
            if f.endswith(".py") and f != "__init__.py":
                module_name = f"backend.pieces.{f[:-3]}"
                
                with self.subTest(module=module_name):
                    # 1. Import
                    try:
                        mod = importlib.import_module(module_name)
                    except Exception as e:
                        self.fail(f"Impossible d'importer {module_name}: {e}")
                    
                    # 2. Check Class
                    self.assertTrue(hasattr(mod, 'Piece'), f"{module_name} n'a pas de classe Piece")
                    
                    # 3. Instantiate
                    try:
                        obj = mod.Piece()
                    except Exception as e:
                        self.fail(f"Impossible d'instancier Piece dans {module_name}: {e}")
                    
                    # 4. Check Attributes
                    self.assertTrue(hasattr(obj, 'nom'), f"{module_name} n'a pas d'attribut 'nom'")
                    self.assertIsInstance(obj.nom, str)
                    
                    # 5. Check Methods
                    if not hasattr(obj, 'dimensionner'):
                         print(f"FAIL: {module_name} missing dimensionner")
                         self.fail(f"{module_name} n'a pas de méthode 'dimensionner'")
                    
                    if not hasattr(obj, 'decrire'):
                         print(f"FAIL: {module_name} missing decrire")
                         self.fail(f"{module_name} n'a pas de méthode 'decrire'")
                    
                    count += 1
        
        print(f"\n[TestPiecesCompliance] {count} pièces vérifiées avec succès.")

if __name__ == '__main__':
    unittest.main()
