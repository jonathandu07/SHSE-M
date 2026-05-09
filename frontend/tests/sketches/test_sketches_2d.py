import unittest

from frontend.gui.piece_connector import get_piece_instance
from frontend.gui.viz_utils import get_viz_figure
from frontend.tests.base import FrontendBaseTest


class TestSketches2D(FrontendBaseTest):
    def _assert_piece_viz(self, piece_name: str) -> None:
        self.logger.info("Test de dessin : %s", piece_name)
        piece = get_piece_instance(piece_name, {}) or self.get_mock_piece("moteur_thermique")
        fig = get_viz_figure(piece_name, piece, "sketches_2d")
        self.assertIsNotNone(fig, f"Aucune figure generée pour {piece_name}.")
        ax = fig.axes[0]
        self.assert_sketch_valid(ax)
        fig.clf()

    def test_draw_cylindre(self):
        self._assert_piece_viz("cylindre")
        self.logger.info("Cylindre validé avec succès.")

    def test_draw_piston(self):
        self._assert_piece_viz("piston")
        self.logger.info("Piston validé avec succès.")

    def test_draw_bielle(self):
        self._assert_piece_viz("bielle")
        self.logger.info("Bielle validée avec succès.")

    def test_draw_vilbrequin(self):
        self._assert_piece_viz("vilbrequin")
        self.logger.info("Vilbrequin validé avec succès.")

    def test_draw_couvercle_cylindre(self):
        self._assert_piece_viz("couvercle_cylindre")
        self.logger.info("Couvercle Cylindre validé avec succès.")


if __name__ == "__main__":
    unittest.main()
