# backend\pieces\volant_inertie.py

"""
Pièce: volant_inertie
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'volant_inertie'.\"\"\"

    def __init__(self):
        self.nom = "volant_inertie"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
