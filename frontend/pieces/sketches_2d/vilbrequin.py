import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw(ax, p):
    """
    Renders a 2D front-view sketch of the Crankshaft (Vilbrequin) / Eccentric throw.
    """
    # 1. Extraction des dimensions
    stroke = getattr(p, "course_m", 0.08)
    d_main = getattr(p, "diametre_journal_principal_m", 0.05)
    d_pin = getattr(p, "diametre_maneton_m", 0.04)
    
    # Conversion mm
    r = (stroke / 2) * 1000  # rayon manivelle
    dm = d_main * 1000
    dp = d_pin * 1000
    
    # 2. Dessin
    # Journal principal au centre (0,0)
    circle_main_out = patches.Circle((0, 0), dm/2 + 10, facecolor='#D3D3D3', edgecolor='black', alpha=0.3) # Flasque de guidage simulé
    circle_main_in = patches.Circle((0, 0), dm/2, facecolor='#A9A9A9', edgecolor='black', linewidth=1.5)
    
    # Maneton (Offset de r sur l'axe Y pour la vue de face)
    circle_pin_in = patches.Circle((0, r), dp/2, facecolor='#808080', edgecolor='black', linewidth=1.5)
    
    # Bras de manivelle (Web) - Liaison entre les deux
    # On dessine une forme ovale ou rectangulaire englobant les deux
    web_w = max(dm, dp) + 15
    # Polyline pour le bras
    web_points = [
        (-web_w/2, -dm/2), (web_w/2, -dm/2),
        (web_w/2, r + dp/2), (-web_w/2, r + dp/2),
        (-web_w/2, -dm/2)
    ]
    poly_web = patches.Polygon(web_points, closed=True, facecolor='#C0C0C0', edgecolor='black', alpha=0.6, hatch='..')
    
    # Ajouts
    ax.add_patch(poly_web)
    ax.add_patch(circle_main_out)
    ax.add_patch(circle_main_in)
    ax.add_patch(circle_pin_in)
    
    # Lignes d'axes
    ax.plot([0, 0], [0, r], color='blue', linestyle='--', linewidth=1, label='Rayon R')
    ax.plot(0, 0, 'rx', markersize=8) # Centre principal
    ax.plot(0, r, 'bx', markersize=6) # Centre maneton
    
    # Cotations
    ax.text(web_w/2 + 5, r/2, f"R = {r:.1f} mm", va='center', fontweight='bold', color='#BF0000')
    ax.text(0, -dm/2 - 8, f"Ø Journal {dm:.1f}", ha='center', fontsize=9)
    ax.text(0, r + dp/2 + 5, f"Ø Maneton {dp:.1f}", ha='center', fontsize=9)
    
    # 3. Mise en page
    ax.set_aspect('equal')
    margin = r + max(dm, dp)
    ax.set_xlim(-margin, margin)
    ax.set_ylim(-dm/2 - 20, r + dp/2 + 20)
    ax.axis('off')
    ax.set_title("VILBREQUIN (VUE DE FACE)", fontsize=12, pad=10)
