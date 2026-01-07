import unittest
import os
import matplotlib.pyplot as plt
from frontend.tests.conftest_logging import setup_test_logging
from frontend.tests.utils.data_extractor import get_latest_system_analysis, get_piece_data

class FrontendBaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Utilise le nom du module (fichier) pour le log au lieu du nom de la classe
        test_file_name = cls.__module__.split('.')[-1]
        cls.logger = setup_test_logging(test_file_name)
        cls.backend_log = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "logs", "test_systeme_complet.log"))
        cls.full_data = get_latest_system_analysis(cls.backend_log)
        if not cls.full_data:
            cls.logger.warning("Aucune donnée d'analyse système trouvée dans les logs backend.")

    def get_mock_piece(self, key):
        piece = get_piece_data(self.full_data, key)
        if not piece:
            self.logger.error(f"Données introuvables pour la pièce: {key}")
        return piece

    def assert_sketch_valid(self, ax):
        has_content = len(ax.patches) > 0 or len(ax.texts) > 0 or len(ax.lines) > 0
        self.assertTrue(has_content, "La fonction draw n'a rien dessiné sur les axes.")
