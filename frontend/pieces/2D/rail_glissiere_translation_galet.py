import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw(ax, piece):
    # Auto-generated visualization logic
    # Paramètres géométriques (avec valeurs par défaut si manquant)
    d = getattr(piece, 'diametre_m', getattr(piece, 'diametre_nominal_m', getattr(piece, 'alesage_m', 0.1)))
    d_ext = getattr(piece, 'diametre_externe_m', getattr(piece, 'diametre_exterieur_m', d))
    d_int = getattr(piece, 'diametre_interne_m', getattr(piece, 'diametre_interieur_m', 0.0))
    L = getattr(piece, 'longueur_m', getattr(piece, 'hauteur_m', getattr(piece, 'hauteur_mm', getattr(piece, 'entraxe_m', 0.1))))
    if hasattr(piece, 'hauteur_mm'): L = piece.hauteur_mm / 1000.0

    # Forme générique (Pas de dimensions canoniques trouvées)
    ax.text(0.5, 0.5, piece.nom, horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
    ax.add_patch(patches.Rectangle((0, 0), 1, 1, fill=False, edgecolor='gray'))

    # Titre et Echelle
    ax.set_title(piece.nom)
    ax.autoscale()

