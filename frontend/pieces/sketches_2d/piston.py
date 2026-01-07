import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw(ax, p):
    """
    Renders a 2D cross-section sketch of the Piston.
    """
    # 1. Extraction des dimensions
    # On utilise les diamètres calculés ou l'alésage nominal comme fallback
    diam = getattr(p, "diametre_piston_cao_centre_m", getattr(p, "alesage_nominal_m", 0.08))
    h_total = getattr(p, "hauteur_totale_m", 0.05)
    t_head = getattr(p, "epaisseur_tete_m", 0.01)
    nb_rings = int(getattr(p, "nb_joints", 0))
    
    # Conversion mm
    D = diam * 1000
    H = h_total * 1000
    th = t_head * 1000
    
    # 2. Dessin du corps du piston (Coupe)
    # Forme générale (Rectangle)
    # Couronne (Top)
    rect_crown = patches.Rectangle((-D/2, H-th), D, th, linewidth=1.5, edgecolor='black', facecolor='#A9A9A9')
    # Jupe (Côtés) - simulé par deux bandes verticales
    skirt_w = D * 0.15
    rect_skirt_l = patches.Rectangle((-D/2, 0), skirt_w, H-th, linewidth=1.2, edgecolor='black', facecolor='#C0C0C0')
    rect_skirt_r = patches.Rectangle((D/2 - skirt_w, 0), skirt_w, H-th, linewidth=1.2, edgecolor='black', facecolor='#C0C0C0')
    
    ax.add_patch(rect_crown)
    ax.add_patch(rect_skirt_l)
    ax.add_patch(rect_skirt_r)
    
    # 3. Segments (Rainures)
    # On place les segments sous la tête
    ring_h = 2  # mm
    ring_space = 3 # mm
    start_y = H - th - 5
    for i in range(nb_rings):
        y = start_y - i * (ring_h + ring_space)
        if y > 2: # Ne pas sortir du piston
            # Rainures gauche/droite
            g_l = patches.Rectangle((-D/2, y), 3, ring_h, color='white', edgecolor='black', linewidth=0.5)
            g_r = patches.Rectangle((D/2 - 3, y), 3, ring_h, color='white', edgecolor='black', linewidth=0.5)
            ax.add_patch(g_l)
            ax.add_patch(g_r)

    # Axe (Wrist Pin hole)
    circle_pin = patches.Circle((0, H/2), D*0.15, fill=False, edgecolor='blue', linestyle='--', linewidth=1)
    ax.add_patch(circle_pin)
    
    # Centre Line
    ax.axvline(0, color='gray', linestyle='-.', linewidth=0.8, alpha=0.5)
    
    # Cotations
    ax.text(0, -H*0.1, f"Ø {D:.1f} mm", ha='center', fontweight='bold', color='#BF0000')
    ax.text(D/2 + 5, H/2, f"H = {H:.1f} mm", va='center', rotation=90)
    ax.text(0, H + 3, f"Tête = {th:.1f} mm", ha='center', fontsize=9)
    
    # 4. Mise en page
    ax.set_aspect('equal')
    margin = max(D, H) * 0.2
    ax.set_xlim(-D/2 - margin, D/2 + margin)
    ax.set_ylim(-margin, H + margin)
    ax.axis('off')
    ax.set_title("COUPE PISTON", fontsize=12, pad=10)
