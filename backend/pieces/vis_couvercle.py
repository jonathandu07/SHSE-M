# backend\pieces\vis_couvercle.py

"""
Pièce: vis_couvercle
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'vis_couvercle'.\"\"\"

    def __init__(self):
        self.nom = "vis_couvercle"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
