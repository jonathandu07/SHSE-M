# backend\pieces\goujons.py

"""
Pièce: goujons
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'goujons'.\"\"\"

    def __init__(self):
        self.nom = "goujons"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
