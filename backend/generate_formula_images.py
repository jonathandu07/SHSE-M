import os
import re
import matplotlib.pyplot as plt

# Chemins
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULES_DIR = os.path.join(BASE_DIR, 'modules')
OUTPUT_DIR = os.path.join(BASE_DIR, '../frontend/images')

# Création dossier cible
os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_formulas(file_path):
    """Extrait les lignes commençant par 'Formule :' dans un fichier."""
    formulas = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # Chercher "Formule : <texte>"
        # On suppose que ça tient sur une ligne ou c'est dans une docstring
        matches = re.findall(r'Formule\s*:\s*(.*)', content)
        formulas.extend(matches)
    return formulas

def render_formula_image(formula_text, filename):
    """Génère une image PNG avec la formule."""
    fig = plt.figure(figsize=(10, 2))
    # Fond blanc, texte noir (ou style "tableau noir" si voulu)
    fig.patch.set_facecolor('white')
    
    # On essaye d'utiliser le rendu MathText de matplotlib si possible ($...$)
    # Mais les formules extraites sont souvent du texte brut "P = U * I"
    # On va les afficher en tant que texte centré.
    
    # Nettoyage léger
    clean_text = formula_text.strip()
    
    # Rendu
    plt.text(0.5, 0.5, f"${clean_text}$" if "=" in clean_text or "+" in clean_text else clean_text, 
             fontsize=20, ha='center', va='center', wrap=True)
    
    plt.axis('off')
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(out_path, bbox_inches='tight', dpi=150)
    plt.close()
    print(f"Généré : {out_path}")

def main():
    print(f"Scan des modules dans {MODULES_DIR}...")
    
    for root, dirs, files in os.walk(MODULES_DIR):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                path = os.path.join(root, file)
                module_name = file.replace('.py', '')
                
                formulas = extract_formulas(path)
                
                for i, form in enumerate(formulas):
                    # Nom fichier : module_formula_i.png
                    safe_name = f"{module_name}_eq_{i+1}.png"
                    try:
                        render_formula_image(form, safe_name)
                    except Exception as e:
                        print(f"Erreur rendu {safe_name}: {e}")

if __name__ == "__main__":
    main()
