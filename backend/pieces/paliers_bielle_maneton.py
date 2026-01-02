# backend\pieces\paliers_bielle_maneton.py

"""
Pièce: paliers_bielle_maneton
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'paliers_bielle_maneton'.\"\"\"

    def __init__(self):
        self.nom = "paliers_bielle_maneton"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
