import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

def draw(ax, p):
    """
    Renders a 2D side-view sketch of the Connecting Rod (Bielle).
    """
    # 1. Extraction des dimensions
    L_m = getattr(p, "longueur_bielle_m", 0.15)
    d_small = getattr(p, "diametre_axe_piston_m", 0.02)
    d_big = getattr(p, "diametre_maneton_m", 0.04)
    
    # Conversion mm
    L = L_m * 1000
    ds = d_small * 1000
    db = d_big * 1000
    
    # Épaisseurs de têtes estimées (explicites pour le dessin)
    ts = ds * 0.4
    tb = db * 0.35
    
    # 2. Dessin
    # Petite tête (Small end) à X=0, Y=0
    circle_s_in = patches.Circle((0, 0), ds/2, fill=False, edgecolor='black', linewidth=1)
    circle_s_out = patches.Circle((0, 0), ds/2 + ts, fill=True, facecolor='#C0C0C0', edgecolor='black', alpha=0.8)
    
    # Grande tête (Big end) à X=L, Y=0
    circle_b_in = patches.Circle((L, 0), db/2, fill=False, edgecolor='black', linewidth=1)
    circle_b_out = patches.Circle((L, 0), db/2 + tb, fill=True, facecolor='#A9A9A9', edgecolor='black', alpha=0.8)
    
    # Fût (Shank)
    # On trace un trapèze ou rectangle entre les deux têtes
    ws = ds * 0.8 # largeur côté petite tête
    wb = db * 0.7 # largeur côté grande tête
    # Points du fût (on décale un peu des centres pour ne pas chevaucher les trous)
    x1 = ds/2 + ts/2
    x2 = L - (db/2 + tb/2)
    
    path_data = [
        (x1, ws/2), (x2, wb/2),
        (x2, -wb/2), (x1, -ws/2),
        (x1, ws/2)
    ]
    poly_shank = patches.Polygon(path_data, closed=True, facecolor='#D3D3D3', edgecolor='black', linewidth=1.2)
    
    # Ajouts au plot
    ax.add_patch(circle_s_out)
    ax.add_patch(circle_s_in)
    ax.add_patch(circle_b_out)
    ax.add_patch(circle_b_in)
    ax.add_patch(poly_shank)
    
    # Axe de la bielle
    ax.plot([0, L], [0, 0], color='blue', linestyle='-.', linewidth=0.8, alpha=0.4)
    
    # Cotations
    ax.text(L/2, wb/2 + 5, f"L = {L:.1f} mm", ha='center', fontweight='bold', color='#BF0000')
    ax.text(0, -(ds/2 + ts + 8), f"Ø axe {ds:.1f}", ha='center', fontsize=9)
    ax.text(L, -(db/2 + tb + 8), f"Ø maneton {db:.1f}", ha='center', fontsize=9)
    
    # 3. Mise en page
    ax.set_aspect('equal')
    margin = L * 0.2
    ax.set_xlim(-margin, L + margin)
    ax.set_ylim(-(db/2 + tb + margin), db/2 + tb + margin)
    ax.axis('off')
    ax.set_title("BIELLE (VUE DE CÔTÉ)", fontsize=12, pad=10)
