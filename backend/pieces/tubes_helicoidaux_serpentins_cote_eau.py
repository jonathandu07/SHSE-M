# backend\pieces\tubes_helicoidaux_serpentins_cote_eau.py

"""
Pièce: tubes_helicoidaux_serpentins_cote_eau
"""

class Piece:
    \"\"\"Squelette minimal pour la pièce 'tubes_helicoidaux_serpentins_cote_eau'.\"\"\"

    def __init__(self):
        self.nom = "tubes_helicoidaux_serpentins_cote_eau"

    def decrire(self) -> str:
        return f"Pièce: {self.nom}"
