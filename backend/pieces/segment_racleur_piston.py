# backend\pieces\segment_racleur_piston.py

"""
Pièce: segment_racleur_piston
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'segment_racleur_piston'.\"\"\"

    def __init__(self):
        self.nom = "segment_racleur_piston"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
