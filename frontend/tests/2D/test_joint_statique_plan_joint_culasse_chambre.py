import unittest
import matplotlib.pyplot as plt
from frontend.pieces.2D import joint_statique_plan_joint_culasse_chambre

class TestJointStatiquePlanJointCulasseChambre2D(unittest.TestCase):
    def test_draw(self):
        fig, ax = plt.subplots()
        
        class MockPiece:
            def __init__(self):
                self.nom = "Test Piece"
                self.alesage_m = 0.1
                self.diametre_interne_m = 0.1
                self.hauteur_m = 0.1
                self.hauteur_mm = 0.1
                self.diametre_nominal_m = 0.1
                self.longueur_m = 0.1
                self.diametre_externe_m = 0.1
                self.nom = "TestPiece"
                self.diametre_exterieur_m = 0.1
                self.diametre_m = 0.1
                self.entraxe_m = 0.1
                self.diametre_interieur_m = 0.1

        
        piece = MockPiece()
        
        # Should run without error
        joint_statique_plan_joint_culasse_chambre.draw(ax, piece)
        
        # Check if something was added (patches or text)
        has_content = len(ax.patches) > 0 or len(ax.texts) > 0
        self.assertTrue(has_content, "Draw function should add patches or text to the axes")
        
        plt.close(fig)

if __name__ == '__main__':
    unittest.main()
