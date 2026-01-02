# backend\pieces\maneton.py

"""
Pièce: maneton
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'maneton'.\"\"\"

    def __init__(self):
        self.nom = "maneton"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
