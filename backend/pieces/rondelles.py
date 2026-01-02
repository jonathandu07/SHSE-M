# backend\pieces\rondelles.py

"""
Pièce: rondelles
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'rondelles'.\"\"\"

    def __init__(self):
        self.nom = "rondelles"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
