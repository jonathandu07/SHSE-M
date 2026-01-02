# backend\pieces\circlips_axe_piston.py

"""
Pièce: circlips_axe_piston
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'circlips_axe_piston'.\"\"\"

    def __init__(self):
        self.nom = "circlips_axe_piston"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
