# backend\pieces\circuit_lubrification.py

"""
Pièce: circuit_lubrification
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'circuit_lubrification'.\"\"\"

    def __init__(self):
        self.nom = "circuit_lubrification"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
