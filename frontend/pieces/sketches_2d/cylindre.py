import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw(ax, p):
    """
    Renders a 2D cross-section sketch of the Cylinder.
    
    Attributes expected from p (via SecureDatabase/backend):
    - alesage_m
    - longueur_utile_m
    - epaisseur_retenue_m (or fallback)
    """
    # 1. Extraction des dimensions
    bore = getattr(p, "alesage_m", 0.08)  # Default 80mm
    length = getattr(p, "longueur_utile_m", 0.15)  # Default 150mm
    thickness = getattr(p, "epaisseur_retenue_m", 0.005)  # Default 5mm
    
    # conversion en mm pour le dessin
    b = bore * 1000
    L = length * 1000
    t = thickness * 1000
    
    # 2. Dessin
    # On centre sur l'axe X=0
    # Paroi gauche
    rect_left = patches.Rectangle((-b/2 - t, 0), t, L, linewidth=1.5, edgecolor='black', facecolor='#D3D3D3', hatch='///')
    # Paroi droite
    rect_right = patches.Rectangle((b/2, 0), t, L, linewidth=1.5, edgecolor='black', facecolor='#D3D3D3', hatch='///')
    
    ax.add_patch(rect_left)
    ax.add_patch(rect_right)
    
    # Lignes de centre
    ax.axvline(0, color='blue', linestyle='--', linewidth=0.8, alpha=0.5)
    
    # Cotations (Schématiques)
    ax.text(0, -L*0.05, f"Ø {b:.1f} mm", ha='center', fontweight='bold', color='#BF0000')
    ax.text(b/2 + t + 2, L/2, f"L = {L:.1f} mm", va='center', rotation=90, fontweight='bold')
    ax.text(-b/2 - t/2, L + 5, f"t = {t:.1f} mm", ha='center', fontsize=9)
    
    # 3. Mise en page
    ax.set_aspect('equal')
    margin = max(b, L) * 0.15
    ax.set_xlim(-b/2 - t - margin, b/2 + t + margin)
    ax.set_ylim(-margin, L + margin)
    ax.axis('off')
    ax.set_title("COUPE CYLINDRE", fontsize=12, pad=15)
