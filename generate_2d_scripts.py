import os
import sys
import importlib.util
import inspect

# Configuration
BACKEND_PIECES_DIR = os.path.join("backend", "pieces")
FRONTEND_2D_DIR = os.path.join("frontend", "pieces", "2D")

def get_piece_class(filepath):
    """Dynamically imports the Piece class from a file."""
    try:
        spec = importlib.util.spec_from_file_location("module.name", filepath)
        module = importlib.util.module_from_spec(spec)
        sys.modules["module.name"] = module # Hack to handle some imports if needed
        spec.loader.exec_module(module)
        if hasattr(module, "Piece"):
            return module.Piece
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
    return None

def generate_draw_logic(piece_instance):
    """Generates the body of the draw(ax, piece) function based on attributes."""
    attrs = piece_instance.__dict__.keys()
    
    # Heuristics
    has_d_ext = "diametre_externe_m" in attrs or "diametre_exterieur_m" in attrs
    has_d_int = "diametre_interne_m" in attrs or "diametre_interieur_m" in attrs
    has_d = "diametre_m" in attrs or "diametre_nominal_m" in attrs or "alesage_m" in attrs
    has_l = "longueur_m" in attrs or "hauteur_m" in attrs or "hauteur_mm" in attrs or "course_m" in attrs or "entraxe_m" in attrs
    
    # Normalisation des noms pour le script généré
    # On va générer du code qui tente de récupérer ces valeurs
    
    code = "    # Auto-generated visualization logic\n"
    code += "    # Paramètres géométriques (avec valeurs par défaut si manquant)\n"
    
    # Extraction générique
    code += "    d = getattr(piece, 'diametre_m', getattr(piece, 'diametre_nominal_m', getattr(piece, 'alesage_m', 0.1)))\n"
    code += "    d_ext = getattr(piece, 'diametre_externe_m', getattr(piece, 'diametre_exterieur_m', d))\n"
    code += "    d_int = getattr(piece, 'diametre_interne_m', getattr(piece, 'diametre_interieur_m', 0.0))\n"
    code += "    L = getattr(piece, 'longueur_m', getattr(piece, 'hauteur_m', getattr(piece, 'hauteur_mm', getattr(piece, 'entraxe_m', 0.1))))\n"
    code += "    if hasattr(piece, 'hauteur_mm'): L = piece.hauteur_mm / 1000.0\n\n"

    # Logique de dessin
    if has_d_int and has_d_ext:
        # Tube / Bague
        code += "    # Tube / Bague (Vue en coupe ou de face)\n"
        code += "    # Cercle Ext\n"
        code += "    ax.add_patch(patches.Circle((0, 0), d_ext/2, edgecolor='black', facecolor='#e0e0e0', label='Ext'))\n"
        code += "    # Cercle Int\n"
        code += "    ax.add_patch(patches.Circle((0, 0), d_int/2, edgecolor='black', facecolor='white', label='Int'))\n"
        code += "    ax.set_aspect('equal')\n"
        
    elif has_d and has_l:
        # Cylindre plein ou Axe (Vue de coté)
        code += "    # Cylindre (Vue de coté)\n"
        code += "    # Rectangle centré sur Y\n"
        code += "    rect = patches.Rectangle((0, -d/2), L, d, linewidth=1, edgecolor='black', facecolor='#f0f0f0')\n"
        code += "    ax.add_patch(rect)\n"
        code += "    # Axe médian\n"
        code += "    ax.axhline(0, color='red', linestyle='--', linewidth=0.5)\n"
        code += "    ax.set_aspect('equal')\n"
        
    elif has_d:
        # Disque simple
        code += "    # Disque / Cercle\n"
        code += "    ax.add_patch(patches.Circle((0, 0), d/2, edgecolor='black', facecolor='#d0d0d0'))\n"
        code += "    ax.set_aspect('equal')\n"
        
    else:
        # Fallback : Boite générique
        code += "    # Forme générique (Pas de dimensions canoniques trouvées)\n"
        code += "    ax.text(0.5, 0.5, piece.nom, horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)\n"
        code += "    ax.add_patch(patches.Rectangle((0, 0), 1, 1, fill=False, edgecolor='gray'))\n"

    # Add Info Text
    code += "\n    # Titre et Echelle\n"
    code += "    ax.set_title(piece.nom)\n"
    code += "    ax.autoscale()\n"

    return code

def main():
    print(f"Scanning {BACKEND_PIECES_DIR}...")
    if not os.path.exists(FRONTEND_2D_DIR):
        os.makedirs(FRONTEND_2D_DIR)

    files = [f for f in os.listdir(BACKEND_PIECES_DIR) if f.endswith(".py") and f != "__init__.py"]
    
    count = 0
    for f in files:
        filepath = os.path.join(BACKEND_PIECES_DIR, f)
        PieceClass = get_piece_class(filepath)
        
        if PieceClass:
            try:
                p = PieceClass()
                drawing_code = generate_draw_logic(p)
                
                # Write Frontend Script
                frontend_file = os.path.join(FRONTEND_2D_DIR, f) # Same filename
                
                content = "import matplotlib.pyplot as plt\n"
                content += "import matplotlib.patches as patches\n\n"
                content += "def draw(ax, piece):\n"
                content += drawing_code
                content += "\n"
                
                with open(frontend_file, 'w', encoding='utf-8') as script:
                    script.write(content)
                    
                count += 1
            except Exception as e:
                print(f"Error processing instance of {f}: {e}")

    print(f"Generated {count} drawing scripts in {FRONTEND_2D_DIR}.")

if __name__ == "__main__":
    main()
