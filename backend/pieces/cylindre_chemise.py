# backend\pieces\cylindre_chemise.py

"""
Pièce: cylindre_chemise
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'cylindre_chemise'.\"\"\"

    def __init__(self):
        self.nom = "cylindre_chemise"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
