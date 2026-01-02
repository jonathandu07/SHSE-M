import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'circuit_refroidissement'.
    Pompe à eau, débit, capacité calorifique.
    """

    def __init__(self):
        self.nom = "circuit_refroidissement"
        self.debit_eau_m3h = 0.0
        self.puissance_dissipee_w = 0.0
        self.delta_t_cible_k = 10.0 # On vise 10°C d'échauffement eau

    def dimensionner(self, puissance_moteur_w: float, rendement_global: float = 0.35):
        """
        Dimensionnement thermique.
        P_froid = P_meca * (1-eta)/eta  (Si P_meca donnée, sinon P_chauffe - P_meca)
        Ici on a P_cible (meca).
        """
        # P_input = P_meca / eta
        puissance_input = puissance_moteur_w / rendement_global
        
        # P_pertes_totales = P_input - P_meca
        self.puissance_dissipee_w = puissance_input - puissance_moteur_w
        
        # Supposons 60% des pertes partent dans l'eau (reste échappement/rayonnement)
        puissance_eau = self.puissance_dissipee_w * 0.6
        
        # Q = m * Cp * dT
        # m_dot = P / (Cp * dT)
        cp_eau = 4180.0
        debit_massique = puissance_eau / (cp_eau * self.delta_t_cible_k)
        
        self.debit_eau_m3h = (debit_massique / 1000.0) * 3600.0

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Puissance Dissipée (Eau): {self.puissance_dissipee_w*0.6/1000:.1f} kW\n"
                f"  - Débit requis: {self.debit_eau_m3h:.2f} m3/h")
