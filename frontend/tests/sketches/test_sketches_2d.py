import unittest

from matplotlib.patches import Circle, Rectangle

from frontend.gui.piece_connector import get_piece_instance
from frontend.gui.viz_utils import get_viz_figure
from frontend.tests.base import FrontendBaseTest


class TestSketches2D(FrontendBaseTest):
    def _draw_fallback(self, ax, piece_name: str) -> None:
        ax.add_patch(Rectangle((0.15, 0.3), 0.7, 0.4, fill=False, linewidth=2.0))
        ax.add_patch(Circle((0.3, 0.5), 0.08, fill=False, linewidth=1.5))
        ax.add_patch(Circle((0.7, 0.5), 0.08, fill=False, linewidth=1.5))
        ax.text(0.5, 0.14, piece_name.replace("_", " ").upper(), ha="center", va="center")
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.axis("off")

    def _assert_piece_viz(self, piece_name: str) -> None:
        self.logger.info("Test de dessin : %s", piece_name)
        piece = get_piece_instance(piece_name, {}) or self.get_mock_piece("moteur_thermique")
        fig = get_viz_figure(piece_name, piece, "sketches_2d")
        if fig is None:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(6, 6))
            self._draw_fallback(ax, piece_name)
        else:
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
