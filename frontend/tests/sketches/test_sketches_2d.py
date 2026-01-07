import unittest
import matplotlib.pyplot as plt
from frontend.tests.base import FrontendBaseTest
from frontend.pieces.sketches_2d import cylindre, piston, bielle, vilbrequin, couvercle_cylindre

class TestSketches2D(FrontendBaseTest):
    
    def test_draw_cylindre(self):
        self.logger.info("Test de dessin : Cylindre")
        p = self.get_mock_piece("moteur_thermique")
        fig, ax = plt.subplots()
        cylindre.draw(ax, p)
        self.assert_sketch_valid(ax)
        self.logger.info("Cylindre validé avec succès.")
        plt.close(fig)

    def test_draw_piston(self):
        self.logger.info("Test de dessin : Piston")
        p = self.get_mock_piece("moteur_thermique")
        fig, ax = plt.subplots()
        piston.draw(ax, p)
        self.assert_sketch_valid(ax)
        self.logger.info("Piston validé avec succès.")
        plt.close(fig)

    def test_draw_bielle(self):
        self.logger.info("Test de dessin : Bielle")
        p = self.get_mock_piece("moteur_thermique")
        fig, ax = plt.subplots()
        bielle.draw(ax, p)
        self.assert_sketch_valid(ax)
        self.logger.info("Bielle validée avec succès.")
        plt.close(fig)

    def test_draw_vilbrequin(self):
        self.logger.info("Test de dessin : Vilbrequin")
        p = self.get_mock_piece("moteur_thermique")
        fig, ax = plt.subplots()
        vilbrequin.draw(ax, p)
        self.assert_sketch_valid(ax)
        self.logger.info("Vilbrequin validé avec succès.")
        plt.close(fig)

    def test_draw_couvercle_cylindre(self):
        self.logger.info("Test de dessin : Couvercle Cylindre")
        p = self.get_mock_piece("moteur_thermique")
        fig, ax = plt.subplots()
        couvercle_cylindre.draw(ax, p)
        self.assert_sketch_valid(ax)
        self.logger.info("Couvercle Cylindre validé avec succès.")
        plt.close(fig)

if __name__ == "__main__":
    unittest.main()
