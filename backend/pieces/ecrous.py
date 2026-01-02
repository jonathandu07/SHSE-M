class Piece:
    def __init__(self):
        self.nom = "ecrous"
        self.diametre_m = 0.0
        self.hauteur_m = 0.0
    def dimensionner(self, goujons):
        self.diametre_m = goujons.diametre_m
        self.hauteur_m = 0.8 * self.diametre_m # Standard
    def decrire(self):
        return f"Pièce: {self.nom} (M{self.diametre_m*1000:.0f})"
