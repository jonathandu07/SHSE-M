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
        matches = re.findall(r'Formule\s*:\s*(.*)', content)
        formulas.extend(matches)
    return formulas

def latexify(text):
    """Convertit du texte brut type code en LaTeX basique."""
    # Dictionnaire de remplacement
    replacements = {
        'omega': r'\omega',
        'theta': r'\theta',
        'pi': r'\pi',
        'alpha': r'\alpha',
        'beta': r'\beta',
        'eta': r'\eta',
        'gamma': r'\gamma',
        'lambda': r'\lambda',
        'rho': r'\rho',
        'tau': r'\tau',
        'sigma': r'\sigma',
        'mu': r'\mu',
        'sqrt': r'\sqrt',
        '*': r'\cdot ',
        ' / ': r' \over ',
        '**2': r'^2',
        '**3': r'^3',
        '(': r'\left(',
        ')': r'\right)',
        'Delta': r'\Delta',
        'Phi': r'\Phi',
    }
    
    latex_text = text.strip()
    
    # Remplacements
    for k, v in replacements.items():
        latex_text = latex_text.replace(k, v)
    
    # Gestion des indices simples (ex: T1 -> T_1, P_max -> P_{max})
    # Regex pour trouver LettreChiffre (ex T1) -> T_1
    latex_text = re.sub(r'([A-Za-z])(\d+)', r'\1_\2', latex_text)
    
    return f"${latex_text}$"

def render_formula_image(formula_text, filename):
    """Génère une image PNG avec la formule."""
    fig = plt.figure(figsize=(10, 2))
    fig.patch.set_facecolor('white')
    
    clean_text = formula_text.strip()
    nice_formula = latexify(clean_text)
    
    # Rendu
    try:
        # On tente le rendu LaTeX
        plt.text(0.5, 0.5, nice_formula, fontsize=24, ha='center', va='center')
    except Exception as e:
        print(f"Warn: Echec rendu LaTeX pour '{clean_text}', fallback texte. ({e})")
        plt.text(0.5, 0.5, clean_text, fontsize=18, ha='center', va='center')
    
    plt.axis('off')
    
    out_path = os.path.join(OUTPUT_DIR, filename)
    plt.savefig(out_path, bbox_inches='tight', dpi=150)
    plt.close()
    print(f"Généré : {filename}")

def main():
    print(f"Scan des modules dans {MODULES_DIR}...")
    
    count = 0
    for root, dirs, files in os.walk(MODULES_DIR):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                path = os.path.join(root, file)
                module_name = file.replace('.py', '')
                
                formulas = extract_formulas(path)
                
                for i, form in enumerate(formulas):
                    safe_name = f"{module_name}_eq_{i+1}.png"
                    try:
                        render_formula_image(form, safe_name)
                        count += 1
                    except Exception as e:
                        print(f"Erreur fichier {safe_name}: {e}")
    print(f"Terminé. {count} images générées.")

if __name__ == "__main__":
    main()
