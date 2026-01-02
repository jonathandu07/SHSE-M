# backend\pieces\joints_statiques_collecteurs_eau.py

"""
Pièce: joints_statiques_collecteurs_eau
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'joints_statiques_collecteurs_eau'.\"\"\"

    def __init__(self):
        self.nom = "joints_statiques_collecteurs_eau"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
