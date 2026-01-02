# backend\pieces\carter_bati.py

"""
Pièce: carter_bati
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'carter_bati'.\"\"\"

    def __init__(self):
        self.nom = "carter_bati"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
