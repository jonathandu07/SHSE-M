import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
from .config import InputParameters, DimensionResults

def generate_sketches(inputs: InputParameters, res: DimensionResults, output_dir: str) -> list[str]:
    """
    Generates simplified engineering sketches (cross-sections) and saves them as images.
    Returns the list of generated file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []
    
    # Style settings
    plt.style.use('default')
    
    # 1. Cylinder & Piston Cross Section
    fig, ax = plt.subplots(figsize=(6, 8))
    
    # Coordinates (0,0 is Crank Center)
    
    # Cylinder Walls
    bore = res.Bore
    stroke = res.Stroke
    wall = res.wall_thickness
    cyl_height = stroke * 2.5 # Arbitrary visual height
    
    # Draw Cylinder (Left and Right walls)
    rect_left = patches.Rectangle((-bore/2 - wall, stroke/2), wall, cyl_height, linewidth=1, edgecolor='black', facecolor='gray')
    rect_right = patches.Rectangle((bore/2, stroke/2), wall, cyl_height, linewidth=1, edgecolor='black', facecolor='gray')
    ax.add_patch(rect_left)
    ax.add_patch(rect_right)
    
    # Piston at TDC (approx pos)
    # TDC pos of pin center = Stroke/2 + RodLength
    # Here we simplify view: Piston inside cylinder
    piston_h = res.piston_height
    p_y = stroke + piston_h # Position arbitrary for viewing
    
    piston = patches.Rectangle((-bore/2 + 0.001, p_y), bore - 0.002, piston_h, linewidth=1, edgecolor='blue', facecolor='none', label='Piston')
    ax.add_patch(piston)
    
    # Rings
    for i in range(res.num_rings):
        y_ring = p_y + piston_h - (i+1)*res.ring_height*2
        ring = patches.Rectangle((-bore/2, y_ring), bore, res.ring_height, color='orange')
        ax.add_patch(ring)
    
    # Connecting Rod Line
    # Pin center
    pin_y = p_y + piston_h - res.piston_compression_height
    # Crank pin center (at 0 angle for drawing) -> (0, stroke/2)
    # Rod connects (0, stroke/2) to (0, pin_y)
    ax.plot([0, 0], [res.Stroke/2, pin_y], 'k-', linewidth=5, alpha=0.5, label='Bielle')
    
    # Dimensions Annotation
    ax.annotate(f"Alésage {res.Bore*1000:.1f}", xy=(-bore/2, stroke), xytext=(-bore, stroke), arrowprops=dict(arrowstyle='->'))
    ax.annotate(f"Course {res.Stroke*1000:.1f}", xy=(0, stroke/2), xytext=(bore/1.5, stroke/2), arrowprops=dict(arrowstyle='<->'))

    ax.set_xlim(-bore*2, bore*2)
    ax.set_ylim(0, cyl_height + stroke)
    ax.set_aspect('equal')
    ax.set_title(f"Coupe Schématique Cylindre/Piston (N={inputs.N_rpm} rpm)")
    ax.legend()
    
    fname = os.path.join(output_dir, "sketch_cylinder.png")
    fig.savefig(fname)
    plt.close(fig)
    generated_files.append(fname)
    
    # 2. Crankshaft Simplified View
    fig, ax = plt.subplots(figsize=(8, 4))
    
    # Draw Main Journal
    l_main = res.main_journal_length
    d_main = res.main_journal_diameter
    ax.add_patch(patches.Rectangle((-l_main, -d_main/2), l_main*3, d_main, color='gray', alpha=0.3))
    
    # Draw Web
    w_web = res.web_thickness
    h_web = res.crank_radius + d_main 
    ax.add_patch(patches.Rectangle((0, -h_web/2), w_web, h_web, color='darkgray'))
    
    # Draw Pin
    l_pin = res.crank_pin_length
    d_pin = res.crank_pin_diameter
    r_crank = res.crank_radius
    ax.add_patch(patches.Rectangle((w_web, r_crank - d_pin/2), l_pin, d_pin, color='blue', alpha=0.5))
    
    # Annotations
    ax.text(w_web + l_pin/2, r_crank, f"Maneton\nØ{d_pin*1000:.1f}", ha='center', va='center')
    ax.text(-l_main/2, 0, f"Tourillon\nØ{d_main*1000:.1f}", ha='center', va='center')
    ax.annotate(f"Rayon {r_crank*1000:.1f}", xy=(w_web, 0), xytext=(w_web, r_crank), arrowprops=dict(arrowstyle='->'))
    
    ax.set_xlim(-l_main, 2*l_main + l_pin)
    ax.set_ylim(-h_web, h_web)
    ax.set_aspect('equal')
    ax.set_title("Schéma Vilebrequin (Moitié)")
    
    fname = os.path.join(output_dir, "sketch_crank.png")
    fig.savefig(fname)
    plt.close(fig)
    generated_files.append(fname)
    
    res.sketch_paths = generated_files
    return generated_files
