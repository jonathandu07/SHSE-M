# backend\pieces\couvercle_arriere.py

"""
Pièce: couvercle_arriere
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'couvercle_arriere'.\"\"\"

    def __init__(self):
        self.nom = "couvercle_arriere"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
