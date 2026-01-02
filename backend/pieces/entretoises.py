# backend\pieces\entretoises.py

"""
Pièce: entretoises
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'entretoises'.\"\"\"

    def __init__(self):
        self.nom = "entretoises"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
