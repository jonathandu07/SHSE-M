import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'circuit_lubrification'.
    Débit huile pour paliers et refroidissement pistons.
    """

    def __init__(self):
        self.nom = "circuit_lubrification"
        self.debit_huile_l_min = 0.0
        self.pression_pompe_bar = 4.0

    def dimensionner(self, nb_cylindres: int, regime_tr_min: float):
        """
        Règle empirique.
        """
        # Environ 3-4 L/min par cylindre pour refroidissement piston jets d'huile
        debit_base = 3.5 * nb_cylindres
        
        # + Débit paliers (faible, fuites)
        # Factoriser par le régime ? (Pompe volumétrique : débit prop au régime)
        # A 6000 tr/min on veut le max.
        
        facteur_regime = regime_tr_min / 6000.0 if regime_tr_min < 6000 else 1.0
        self.debit_huile_l_min = (debit_base + 5.0) * facteur_regime # +5L/min pour la culasse/turbo...

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Pression: {self.pression_pompe_bar} bar\n"
                f"  - Débit Huile: {self.debit_huile_l_min:.1f} L/min")
