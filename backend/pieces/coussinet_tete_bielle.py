# backend\pieces\coussinet_tete_bielle.py

"""
Pièce: coussinet_tete_bielle
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'coussinet_tete_bielle'.\"\"\"

    def __init__(self):
        self.nom = "coussinet_tete_bielle"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
