# backend\pieces\couvercle_avant.py

"""
Pièce: couvercle_avant
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'couvercle_avant'.\"\"\"

    def __init__(self):
        self.nom = "couvercle_avant"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
