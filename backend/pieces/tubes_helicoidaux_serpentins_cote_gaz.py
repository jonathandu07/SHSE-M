# backend\pieces\tubes_helicoidaux_serpentins_cote_gaz.py

"""
Pièce: tubes_helicoidaux_serpentins_cote_gaz
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'tubes_helicoidaux_serpentins_cote_gaz'.\"\"\"

    def __init__(self):
        self.nom = "tubes_helicoidaux_serpentins_cote_gaz"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
