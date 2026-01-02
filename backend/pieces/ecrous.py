# backend\pieces\ecrous.py

"""
Pièce: ecrous
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'ecrous'.\"\"\"

    def __init__(self):
        self.nom = "ecrous"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
