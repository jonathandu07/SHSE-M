import os
import sys
import importlib.util
import math

# Configuration
BACKEND_PIECES_DIR = os.path.join("backend", "pieces")
FRONTEND_CHARTS_DIR = os.path.join("frontend", "pieces", "charts")

def get_piece_class(filepath):
    """Dynamically imports the Piece class from a file."""
    try:
        spec = importlib.util.spec_from_file_location("module.name", filepath)
        module = importlib.util.module_from_spec(spec)
        sys.modules["module.name"] = module
        spec.loader.exec_module(module)
        if hasattr(module, "Piece"):
            return module.Piece
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
    return None

def estimate_resistance(piece_instance):
    """
    Estime les résistances mécaniques basées sur les attributs disponibles.
    Retourne un dict avec: usure, chaleur, torsion, flexion, compression (valeurs 0-100).
    """
    attrs = piece_instance.__dict__
    
    # Heuristiques basées sur les attributs disponibles
    resistance = {
        'usure': 50,           # Résistance à l'usure (0-100)
        'chaleur': 50,         # Résistance thermique (0-100)
        'torsion': 50,         # Résistance à la torsion (0-100)
        'flexion': 50,         # Résistance à la flexion (0-100)
        'compression': 50      # Résistance à la compression (0-100)
    }
    
    # Détection de matériaux/types pour ajuster résistances
    nom = piece_instance.nom.lower()
    
    # Pièces en rotation: plus sensibles à l'usure
    if 'roulement' in nom or 'palier' in nom or 'coussinet' in nom:
        resistance['usure'] = 40  # Usure plus élevée
        resistance['torsion'] = 70
        
    # Pièces chaudes: plus sensibles à la chaleur
    if 'chambre' in nom or 'combustion' in nom or 'chaude' in nom:
        resistance['chaleur'] = 30  # Tolère moins bien (valeur basse = stress élevé)
        resistance['compression'] = 80
        
    # Arbres et axes: bons en torsion/flexion
    if 'arbre' in nom or 'axe' in nom or 'vilebrequin' in nom:
        resistance['torsion'] = 85
        resistance['flexion'] = 80
        resistance['usure'] = 60
        
    # Joints et étanchéité: usure et chaleur critiques
    if 'joint' in nom or 'etanch' in nom or 'segment' in nom:
        resistance['usure'] = 35
        resistance['chaleur'] = 40
        resistance['compression'] = 60
        
    # Piston: compression et chaleur
    if 'piston' in nom:
        resistance['compression'] = 75
        resistance['chaleur'] = 45
        resistance['usure'] = 50
        
    # Bielle: flexion et torsion
    if 'bielle' in nom:
        resistance['flexion'] = 80
        resistance['torsion'] = 75
        resistance['compression'] = 85
        
    # Ressorts: flexion
    if 'ressort' in nom or 'rappel' in nom:
        resistance['flexion'] = 70
        resistance['usure'] = 55
        
    return resistance

def generate_chart_code(module_name, piece_instance):
    """Génère le code du graphique radar avec zones de tolérance."""
    
    resistance = estimate_resistance(piece_instance)
    
    code = f"""import matplotlib.pyplot as plt
import numpy as np

def plot_data(ax, piece):
    \"\"\"
    Graphique radar montrant les résistances mécaniques avec zones de tolérance.
    \"\"\"
    categories = ['Usure', 'Chaleur', 'Torsion', 'Flexion', 'Compression']
    
    # Valeurs de résistance (0-100, plus haut = meilleur)
    # Ces valeurs sont des estimations basées sur le type de pièce
    values = [{resistance['usure']}, {resistance['chaleur']}, {resistance['torsion']}, {resistance['flexion']}, {resistance['compression']}]
    
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
    
    ax.set_title(f"Résistances Mécaniques: {{piece.nom}}", size=14, weight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8)
    ax.grid(True)
"""
    
    return code

def main():
    print(f"Scanning {BACKEND_PIECES_DIR}...")
    if not os.path.exists(FRONTEND_CHARTS_DIR):
        os.makedirs(FRONTEND_CHARTS_DIR)

    files = [f for f in os.listdir(BACKEND_PIECES_DIR) if f.endswith(".py") and f != "__init__.py"]
    
    count = 0
    for f in files:
        filepath = os.path.join(BACKEND_PIECES_DIR, f)
        PieceClass = get_piece_class(filepath)
        
        if PieceClass:
            try:
                p = PieceClass()
                chart_code = generate_chart_code(f[:-3], p)
                
                # Write Chart Script
                chart_file = os.path.join(FRONTEND_CHARTS_DIR, f)
                
                with open(chart_file, 'w', encoding='utf-8') as script:
                    script.write(chart_code)
                    
                count += 1
            except Exception as e:
                print(f"Error processing instance of {f}: {e}")

    # Create __init__.py
    with open(os.path.join(FRONTEND_CHARTS_DIR, "__init__.py"), 'w') as f:
        pass

    print(f"Generated {count} chart scripts in {FRONTEND_CHARTS_DIR}.")

if __name__ == "__main__":
    main()
