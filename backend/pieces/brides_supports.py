# backend\pieces\brides_supports.py

"""
Pièce: brides_supports
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'brides_supports'.\"\"\"

    def __init__(self):
        self.nom = "brides_supports"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
