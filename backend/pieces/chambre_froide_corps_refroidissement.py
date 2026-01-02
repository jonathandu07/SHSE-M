# backend\pieces\chambre_froide_corps_refroidissement.py

"""
Pièce: chambre_froide_corps_refroidissement
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'chambre_froide_corps_refroidissement'.\"\"\"

    def __init__(self):
        self.nom = "chambre_froide_corps_refroidissement"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
