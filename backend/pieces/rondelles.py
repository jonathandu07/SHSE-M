class Piece:
    def __init__(self):
        self.nom = "rondelles"
        self.diametre_interne_m = 0.0
        self.diametre_externe_m = 0.0
    def dimensionner(self, ecrous):
        self.diametre_interne_m = ecrous.diametre_nominal_m * 1.05
        self.diametre_externe_m = ecrous.diametre_nominal_m * 2.0
    def decrire(self):
        return f"Pièce: {self.nom} ({self.diametre_interne_m*1000:.1f}x{self.diametre_externe_m*1000:.1f})"
