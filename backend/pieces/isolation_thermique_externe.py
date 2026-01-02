# backend\pieces\isolation_thermique_externe.py

"""
Pièce: isolation_thermique_externe
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'isolation_thermique_externe'.\"\"\"

    def __init__(self):
        self.nom = "isolation_thermique_externe"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
