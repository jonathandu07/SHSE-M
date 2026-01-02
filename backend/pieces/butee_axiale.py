# backend\pieces\butee_axiale.py

"""
Pièce: butee_axiale
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'butee_axiale'.\"\"\"

    def __init__(self):
        self.nom = "butee_axiale"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
