# backend\pieces\axes_galet.py

"""
Pièce: axes_galet
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'axes_galet'.\"\"\"

    def __init__(self):
        self.nom = "axes_galet"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
