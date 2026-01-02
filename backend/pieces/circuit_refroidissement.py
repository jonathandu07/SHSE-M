# backend\pieces\circuit_refroidissement.py

"""
Pièce: circuit_refroidissement
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'circuit_refroidissement'.\"\"\"

    def __init__(self):
        self.nom = "circuit_refroidissement"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
