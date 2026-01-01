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
    piston_h = res.piston_height
    p_y = stroke + piston_h 
    
    piston = patches.Rectangle((-bore/2 + 0.001, p_y), bore - 0.002, piston_h, linewidth=1, edgecolor='blue', facecolor='none', label='Piston')
    ax.add_patch(piston)
    
    # Rings
    for i in range(res.num_rings):
        y_ring = p_y + piston_h - (i+1)*res.ring_height*2
        ring = patches.Rectangle((-bore/2, y_ring), bore, res.ring_height, color='orange')
        ax.add_patch(ring)
    
    # Connecting Rod Line
    pin_y = p_y + piston_h - res.piston_compression_height
    ax.plot([0, 0], [res.Stroke/2, pin_y], 'k-', linewidth=5, alpha=0.5, label='Bielle')
    
    # Annotations - Tolerances & Finish
    ax.annotate(f"Ø {bore*1000:.2f} H7\nRa 0.4", xy=(-bore/2, cyl_height/2 + stroke), xytext=(-bore*1.2, cyl_height/2 + stroke), arrowprops=dict(arrowstyle='->'))
    ax.annotate(f"Jeu Piston/Cyl ~0.04 mm", xy=(bore/2, p_y + piston_h/2), xytext=(bore*0.8, p_y + piston_h/2), arrowprops=dict(arrowstyle='->'))

    ax.set_xlim(-bore*2, bore*2)
    ax.set_ylim(0, cyl_height + stroke)
    ax.set_aspect('equal')
    ax.set_title(f"Cylindre & Piston (H7/g6, N={inputs.N_rpm} rpm)")
    
    fname = os.path.join(output_dir, "sketch_cylinder.png")
    fig.savefig(fname)
    plt.close(fig)
    generated_files.append(fname)
    
    # 2. Crankshaft Simplified View
    fig, ax = plt.subplots(figsize=(8, 5))
    
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
    
    # Annotations - Finishes
    ax.annotate(f"Tourillon Ø{d_main*1000:.1f} g6\nRa 0.4 (Rectifié)", xy=(-l_main/2, d_main/2), xytext=(-l_main/2, d_main*2), arrowprops=dict(arrowstyle='->'))
    ax.annotate(f"Maneton Ø{d_pin*1000:.1f} g6\nRa 0.4 (Rectifié)", xy=(w_web + l_pin/2, r_crank + d_pin/2), xytext=(w_web + l_pin/2, r_crank + d_pin*1.5), arrowprops=dict(arrowstyle='->'))
    
    ax.set_xlim(-l_main, 2*l_main + l_pin)
    ax.set_ylim(-h_web*1.5, h_web*2.5)
    ax.set_aspect('equal')
    ax.set_title("Vilebrequin (Tolérances & État de Surface)")
    ax.axis('off')
    
    fname = os.path.join(output_dir, "sketch_crank.png")
    fig.savefig(fname)
    plt.close(fig)
    generated_files.append(fname)

    # 3. Connecting Rod Detail
    fig, ax = plt.subplots(figsize=(4, 8))
    
    # Dimensions
    l_rod = res.rod_length
    d_small = res.rod_small_end_diameter
    d_big = res.rod_big_end_diameter
    w_beam = res.rod_column_section_width
    
    # Small End
    c_small = patches.Circle((0, l_rod), d_small/2, edgecolor='black', facecolor='lightblue')
    # Hole Small End
    c_pin = patches.Circle((0, l_rod), res.pin_diameter/2, edgecolor='black', facecolor='white')
    
    # Big End
    c_big = patches.Circle((0, 0), d_big/2, edgecolor='black', facecolor='lightblue')
    # Hole Big End
    c_crankpin = patches.Circle((0, 0), res.crank_pin_diameter/2, edgecolor='black', facecolor='white')
    
    # Beam (tapered)
    beam_pts = [
        (-w_beam/2, l_rod - d_small/2),
        (w_beam/2, l_rod - d_small/2),
        (w_beam*0.8, d_big/2),
        (-w_beam*0.8, d_big/2)
    ]
    beam = patches.Polygon(beam_pts, closed=True, edgecolor='black', facecolor='lightblue')
    
    ax.add_patch(beam)
    ax.add_patch(c_small)
    ax.add_patch(c_pin)
    ax.add_patch(c_big)
    ax.add_patch(c_crankpin)
    
    # Bolts lines
    ax.plot([-d_big*0.6, -d_big*0.6], [-d_big/2, d_big/2], 'k--', linewidth=1)
    ax.plot([d_big*0.6, d_big*0.6], [-d_big/2, d_big/2], 'k--', linewidth=1)
    
    # Annotations - Hardware
    # Bolt M-size approx
    m_size_raw = res.rod_bolt_diameter * 1000
    # Snap to standard M6, M8, M10, etc? Simple Rounding for sketch
    m_size = round(m_size_raw)
    if m_size < 4: m_size = 4
    
    ax.annotate(f"2x Vis M{m_size}\n(Std 8.8 ou 12.9)", xy=(d_big*0.6, 0), xytext=(d_big*1.2, 0), arrowprops=dict(arrowstyle='->'))
    ax.annotate(f"Pied: Bague Bronze\nRa 0.8 / H7", xy=(0, l_rod + d_small/2), xytext=(0, l_rod + d_small), arrowprops=dict(arrowstyle='->'))
    ax.annotate(f"Tête: Coussinets\nRa 0.8 / H7", xy=(0, -d_big/2), xytext=(0, -d_big), arrowprops=dict(arrowstyle='->'))

    ax.set_xlim(-d_big*1.5, d_big*1.5)
    ax.set_ylim(-d_big*1.5, l_rod + d_small*1.5)
    ax.set_aspect('equal')
    ax.set_title("Bielle (Visserie & Ajustements)")
    ax.axis('off')
    
    fname = os.path.join(output_dir, "sketch_rod.png")
    fig.savefig(fname)
    plt.close(fig)
    generated_files.append(fname)
    
    res.sketch_paths = generated_files
    return generated_files
