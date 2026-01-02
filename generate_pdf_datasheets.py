import os
import sys
import importlib.util
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.platypus import Table, TableStyle
import matplotlib.pyplot as plt
import numpy as np

# Configuration
BACKEND_PIECES_DIR = os.path.join("backend", "pieces")
OUTPUT_DIR = os.path.join("output", "datasheets", "pieces")

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

def create_resistance_chart_image(piece_name, output_path):
    """Génère l'image du graphique de résistance."""
    # Valeurs types (simplifiées pour la génération)
    categories = ['Usure', 'Chaleur', 'Torsion', 'Flexion', 'Compression']
    values = [50, 50, 50, 50, 50]  # Valeurs par défaut
    
    # Ajuster selon le type de pièce
    if 'palier' in piece_name or 'coussinet' in piece_name:
        values = [40, 50, 70, 50, 50]
    elif 'piston' in piece_name:
        values = [50, 45, 50, 50, 75]
    elif 'arbre' in piece_name or 'vilebrequin' in piece_name:
        values = [60, 50, 85, 80, 50]
    
    # Créer le graphique radar
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    values_plot = values + values[:1]
    angles_plot = angles + angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection='polar'))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    # Zones de tolérance
    ax.fill(angles_plot, [100]*len(angles_plot), color='green', alpha=0.1)
    ax.fill(angles_plot, [70]*len(angles_plot), color='yellow', alpha=0.15)
    ax.fill(angles_plot, [50]*len(angles_plot), color='red', alpha=0.15)
    
    # Valeurs
    ax.plot(angles_plot, values_plot, 'o-', linewidth=2, color='blue')
    ax.fill(angles_plot, values_plot, alpha=0.25, color='blue')
    
    ax.set_xticks(angles)
    ax.set_xticklabels(categories, size=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(['25%', '50%', '75%', '100%'], size=8)
    ax.grid(True)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

def generate_piece_pdf(piece_instance, output_path):
    """Génère un PDF pour une pièce."""
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # Header
    c.setFillColor(HexColor('#1f4788'))
    c.rect(0, height - 40*mm, width, 40*mm, fill=True, stroke=False)
    
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(20*mm, height - 25*mm, "FICHE TECHNIQUE")
    
    c.setFont("Helvetica", 16)
    c.drawString(20*mm, height - 35*mm, piece_instance.nom.upper())
    
    # Section Spécifications
    y_position = height - 55*mm
    c.setFillColor(HexColor('#000000'))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20*mm, y_position, "1. SPÉCIFICATIONS TECHNIQUES")
    
    y_position -= 10*mm
    c.setFont("Helvetica", 10)
    
    # Extraire les attributs
    specs = []
    for attr, value in piece_instance.__dict__.items():
        if attr == 'nom':
            continue
        
        # Formater la valeur
        if isinstance(value, float):
            if 'm' in attr:
                display_value = f"{value*1000:.2f} mm"
            elif 'kg' in attr:
                display_value = f"{value:.3f} kg"
            elif 'n' in attr.lower() or 'force' in attr.lower():
                display_value = f"{value/1000:.1f} kN"
            elif 'pa' in attr.lower() or 'pression' in attr.lower():
                display_value = f"{value/1e6:.1f} MPa"
            else:
                display_value = f"{value:.3f}"
        else:
            display_value = str(value)
        
        # Formater le nom
        display_name = attr.replace('_', ' ').title()
        specs.append([display_name, display_value])
    
    # Limiter à 15 entrées max pour tenir sur la page
    specs = specs[:15]
    
    # Table
    table_data = [["Paramètre", "Valeur"]] + specs
    table = Table(table_data, colWidths=[80*mm, 80*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f0f0f0')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc'))
    ]))
    
    table.wrapOn(c, width, height)
    table.drawOn(c, 20*mm, y_position - len(specs)*6*mm - 15*mm)
    
    # Section Résistances Mécaniques
    y_position = y_position - len(specs)*6*mm - 35*mm
    
    if y_position > 80*mm:  # Assez d'espace
        c.setFont("Helvetica-Bold", 14)
        c.drawString(20*mm, y_position, "2. RÉSISTANCES MÉCANIQUES")
        
        # Générer l'image du graphique
        chart_path = os.path.join("output", "temp_chart.png")
        os.makedirs("output", exist_ok=True)
        create_resistance_chart_image(piece_instance.nom, chart_path)
        
        # Insérer l'image
        if os.path.exists(chart_path):
            c.drawImage(chart_path, 20*mm, y_position - 85*mm, width=90*mm, height=75*mm, preserveAspectRatio=True)
            os.remove(chart_path)
    
    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(HexColor('#666666'))
    c.drawString(20*mm, 15*mm, f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}")
    c.drawRightString(width - 20*mm, 15*mm, "SHSE-M Technical Documentation")
    
    c.save()
    print(f"  ✓ Generated: {output_path}")

def main():
    print("Generating PDF Technical Datasheets...")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Ajouter le chemin backend au sys.path
    sys.path.insert(0, os.path.abspath("."))
    
    files = [f for f in os.listdir(BACKEND_PIECES_DIR) if f.endswith(".py") and f != "__init__.py"]
    
    count = 0
    for f in files:
        filepath = os.path.join(BACKEND_PIECES_DIR, f)
        PieceClass = get_piece_class(filepath)
        
        if PieceClass:
            try:
                # Instancier la pièce (sans arguments pour l'instant, valeurs par défaut)
                piece = PieceClass()
                
                # Nom du PDF
                pdf_name = f[:-3] + ".pdf"
                pdf_path = os.path.join(OUTPUT_DIR, pdf_name)
                
                # Générer le PDF
                generate_piece_pdf(piece, pdf_path)
                count += 1
                
            except Exception as e:
                print(f"  ✗ Error generating PDF for {f}: {e}")
    
    print(f"\n[SUCCESS] Generated {count} PDF datasheets in '{OUTPUT_DIR}'")

if __name__ == "__main__":
    main()
