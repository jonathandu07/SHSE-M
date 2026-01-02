# backend\pieces\vilebrequin_corps.py

"""
Pièce: vilebrequin_corps
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'vilebrequin_corps'.\"\"\"

    def __init__(self):
        self.nom = "vilebrequin_corps"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
