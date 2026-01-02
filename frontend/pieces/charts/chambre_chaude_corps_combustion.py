import matplotlib.pyplot as plt
import numpy as np

def plot_data(ax, piece):
    """
    Graphique radar montrant les résistances mécaniques avec zones de tolérance.
    """
    categories = ['Usure', 'Chaleur', 'Torsion', 'Flexion', 'Compression']
    
    # Valeurs de résistance (0-100, plus haut = meilleur)
    # Ces valeurs sont des estimations basées sur le type de pièce
    values = [50, 30, 50, 50, 80]
    
    # Zones de tolérance
    zone_safe = 70      # Au-dessus = zone sûre (vert)
    zone_warning = 50   # Entre 50-70 = zone d'avertissement (jaune)
    # En-dessous de 50 = zone critique (rouge)
    
    # Nombre de variables
    N = len(categories)
    
    # Angles pour le radar
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values += values[:1]  # Fermer le polygone
    angles += angles[:1]
    
    # Plot
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    # Dessiner les zones de tolérance
    ax.fill(angles, [100]*len(angles), color='green', alpha=0.1, label='Zone Sûre (>70)')
    ax.fill(angles, [zone_safe]*len(angles), color='yellow', alpha=0.15, label='Avertissement (50-70)')
    ax.fill(angles, [zone_warning]*len(angles), color='red', alpha=0.15, label='Critique (<50)')
    
    # Dessiner les valeurs de résistance
    ax.plot(angles, values, 'o-', linewidth=2, color='blue', label='Résistance Actuelle')
    ax.fill(angles, values, alpha=0.25, color='blue')
    
    # Labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(['25%', '50%', '75%', '100%'])
    
    ax.set_title(f"Résistances Mécaniques: {piece.nom}", size=14, weight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)
    ax.grid(True)
