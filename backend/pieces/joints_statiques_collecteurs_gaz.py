# backend\pieces\joints_statiques_collecteurs_gaz.py

"""
Pièce: joints_statiques_collecteurs_gaz
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'joints_statiques_collecteurs_gaz'.\"\"\"

    def __init__(self):
        self.nom = "joints_statiques_collecteurs_gaz"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
