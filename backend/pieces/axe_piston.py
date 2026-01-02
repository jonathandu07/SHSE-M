# backend\pieces\axe_piston.py

"""
Pièce: axe_piston
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'axe_piston'.\"\"\"

    def __init__(self):
        self.nom = "axe_piston"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
