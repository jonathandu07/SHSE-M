import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

def draw(ax, p):
    """
    Renders a 2D cross-section sketch of the Cylinder Cover (Couvercle Cylindre).
    Focus on the spherical dome (calotte sphérique).
    """
    # 1. Extraction des dimensions
    # Rayon base (a)
    a_m = getattr(p, "rayon_base_m", getattr(p, "diametre_ouverture_m", 0.08)/2 if hasattr(p, "diametre_ouverture_m") else 0.04)
    # Hauteur bombe (h)
    h_m = getattr(p, "hauteur_bombe_m", 0.01)
    # Epaisseur (t)
    t_m = getattr(p, "epaisseur_retenue_m", 0.005)
    # Rayon externe (R_ext) for the flange
    r_ext_m = getattr(p, "rayon_externe_m", a_m + 0.02)
    nb_vis = int(getattr(p, "nb_vis", 0))
    
    # Conversion mm
    a = a_m * 1000
    h = h_m * 1000
    t = t_m * 1000
    r_ext = r_ext_m * 1000
    
    # 2. Calcul du rayon de courbure (R) pour le dessin de l'arc
    # R = (a^2 + h^2) / 2h
    if h > 0:
        R_curve = (a**2 + h**2) / (2 * h)
    else:
        R_curve = 1e6 # Plat
        
    # 3. Dessin des brides (Flanges)
    # Gauche
    rect_f_l = patches.Rectangle((-r_ext, 0), r_ext - a, t, facecolor='#A9A9A9', edgecolor='black')
    # Droite
    rect_f_r = patches.Rectangle((a, 0), r_ext - a, t, facecolor='#A9A9A9', edgecolor='black')
    ax.add_patch(rect_f_l)
    ax.add_patch(rect_f_r)
    
    # 4. Dessin de la calotte (Dome)
    # On utilise PathPatch ou simplement un Arc/Wedge
    # Angle d'ouverture
    alpha_deg = math.degrees(math.asin(a / R_curve))
    # Centre du cercle de courbure est à Y = h - R_curve
    cy = h - R_curve
    
    # Arc extérieur
    wedge_ext = patches.Wedge((0, cy), R_curve + t/2, 90 - alpha_deg, 90 + alpha_deg, width=t, facecolor='#C0C0C0', edgecolor='black', linewidth=1)
    ax.add_patch(wedge_ext)
    
    # 5. Vis (Schématique)
    if nb_vis > 0:
        # On dessine 2 vis dans la coupe
        bolt_x = (a + r_ext) / 2
        rect_bolt_l = patches.Rectangle((-bolt_x - 2, -5), 4, t + 10, color='blue', alpha=0.3)
        rect_bolt_r = patches.Rectangle((bolt_x - 2, -5), 4, t + 10, color='blue', alpha=0.3)
        ax.add_patch(rect_bolt_l)
        ax.add_patch(rect_bolt_r)
    
    # Cotations
    ax.text(0, -10, f"Ø Base {2*a:.1f} mm", ha='center', fontweight='bold', color='#BF0000')
    ax.text(0, h + t + 5, f"Bombe h = {h:.1f} mm", ha='center', fontsize=9)
    ax.text(r_ext + 2, t/2, f"t={t:.1f}", va='center', fontsize=8)
    
    # Axe
    ax.axvline(0, color='gray', linestyle='-.', linewidth=0.8, alpha=0.4)
    
    # 6. Mise en page
    ax.set_aspect('equal')
    margin = r_ext * 0.2
    ax.set_xlim(-r_ext - margin, r_ext + margin)
    ax.set_ylim(-15, h + t + 15)
    ax.axis('off')
    ax.set_title("COUPE COUVERCLE (DÔME)", fontsize=12, pad=10)
