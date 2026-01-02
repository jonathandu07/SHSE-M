# backend\pieces\piston_puissance.py

"""
Pièce: piston_puissance
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'piston_puissance'.\"\"\"

    def __init__(self):
        self.nom = "piston_puissance"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
