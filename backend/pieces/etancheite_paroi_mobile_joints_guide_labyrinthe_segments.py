import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'etancheite_paroi_mobile_joints_guide_labyrinthe_segments'.
    Segments ou labyrinthe pour l'étanchéité du piston translateur (Stirling).
    """

    def __init__(self):
        self.nom = "etancheite_paroi_mobile_joints_guide_labyrinthe_segments"
        self.diametre_m = 0.0
        self.type_etancheite = "Segments PTFE"
        self.nb_segments = 3
        self.fuite_estimee_l_min = 0.0

    def dimensionner(self, paroi_mobile, delta_pression_pa):
        """
        Dimensionne l'étanchéité dynamique.
        """
        self.diametre_m = paroi_mobile.diametre_externe_m
        
        # Choix techno: PTFE pour faible frottement et fonctionnement sec (Stirling)
        # Nombre de gorges dépend du delta P
        # Règle pouce: 1 segment par 50 bar ? Pour Stirling (P_mean ~100b, delta P ~10b)
        # 3 Segments est standard pour bonne étanchéité.
        self.nb_segments = 3
        if delta_pression_pa > 50e5: # > 50 bar delta
            self.nb_segments = 4
            
        # Estimation Fuite (Formule Poiseuille laminaire dans fente)
        # Q = (...) très complexe.
        # Approx empirique: 0.1% du débit balayé.
        # Ici on met juste une valeur indicative dépendante de la taille/pression
        self.fuite_estimee_l_min = (1.0 + (delta_pression_pa/10e5)) * self.diametre_m * 10.0

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Type: {self.type_etancheite} (x{self.nb_segments})\n"
                f"  - Pour Alésage: Ø{self.diametre_m*1000:.1f} mm\n"
                f"  - Fuite Moyenne Est.: {self.fuite_estimee_l_min:.2f} L/min")
