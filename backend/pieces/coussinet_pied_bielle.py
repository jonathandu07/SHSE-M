# backend\pieces\coussinet_pied_bielle.py

"""
Pièce: coussinet_pied_bielle
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'coussinet_pied_bielle'.\"\"\"

    def __init__(self):
        self.nom = "coussinet_pied_bielle"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
