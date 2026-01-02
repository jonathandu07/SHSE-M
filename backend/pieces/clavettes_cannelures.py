# backend\pieces\clavettes_cannelures.py

"""
Pièce: clavettes_cannelures
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'clavettes_cannelures'.\"\"\"

    def __init__(self):
        self.nom = "clavettes_cannelures"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
