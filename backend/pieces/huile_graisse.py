# backend\pieces\huile_graisse.py

"""
Pièce: huile_graisse
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'huile_graisse'.\"\"\"

    def __init__(self):
        self.nom = "huile_graisse"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
