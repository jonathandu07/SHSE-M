# backend\pieces\bielle_corps.py

"""
Pièce: bielle_corps
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'bielle_corps'.\"\"\"

    def __init__(self):
        self.nom = "bielle_corps"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
