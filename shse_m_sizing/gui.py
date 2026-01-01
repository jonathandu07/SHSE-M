import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import threading
from PIL import Image, ImageTk

# Import logic
from .main import run_full_sizing

class RedirectText:
    def __init__(self, text_widget):
        self.output = text_widget

    def write(self, string):
        self.output.insert("end", string)
        self.output.see("end")

    def flush(self):
        pass

class MinimalistGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SHSE-M | Interface Ingénierie Interactive")
        self.root.geometry("1600x1000")
        
        # GLOBAL STYLE
        self.colors = {
            "bg": "#f5f5f7", 
            "panel": "#ffffff",
            "primary": "#007aff", 
            "text": "#1d1d1f",
            "success": "#34c759",
            "border": "#d2d2d7",
            "highlight": "#e5f1ff"
        }
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.style.configure("TFrame", background=self.colors["bg"])
        self.style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        self.style.configure("TNotebook", background=self.colors["bg"])
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 11), padding=[20, 8])
        self.style.map("TNotebook.Tab", background=[("selected", self.colors["primary"])], foreground=[("selected", "white")])
        self.style.configure("Treeview", font=("Segoe UI", 10), rowheight=30, borderwidth=0)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background=self.colors["panel"], padding=5)
        self.style.map("Treeview", background=[("selected", self.colors["highlight"])], foreground=[("selected", "black")])
        
        # VARIABLES
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config = self.load_config()
        self.input_vars = {}
        self.current_results = {}
        self.image_refs = []
        
        # LAYOUT
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill="both", expand=True)
        
        self.build_header()
        
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tab_config = ttk.Frame(self.notebook, padding=20)
        self.tab_interactive = ttk.Frame(self.notebook, padding=0) # New Interactive Tab
        self.tab_logs = ttk.Frame(self.notebook, padding=20)
        
        self.notebook.add(self.tab_config, text="CONFIGURATION")
        self.notebook.add(self.tab_interactive, text="EXPLORATION SYSTÈME (BOM & DÉTAILS)")
        self.notebook.add(self.tab_logs, text="LOGS")
        
        self.build_config_tab()
        self.build_interactive_tab()
        self.build_logs_tab()

    def build_header(self):
        header = tk.Frame(self.main_container, bg=self.colors["panel"], height=60, padx=20)
        header.pack(fill="x", side="top")
        
        tk.Label(header, text="SHSE-M · Platforme Avancée", 
                 bg=self.colors["panel"], fg=self.colors["text"], 
                 font=("Segoe UI", 16, "bold")).pack(side="left", pady=15)
        
        tk.Button(header, text="▶ LANCER SIMULATION", 
                  bg=self.colors["primary"], fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", padx=20, pady=8, command=self.run_sim_thread).pack(side="right", pady=10)

    def load_config(self):
        try:
            with open(self.config_path, "r") as f: return json.load(f)
        except: return {}

    def build_config_tab(self):
        # Quick config editor
        canvas = tk.Canvas(self.tab_config, bg=self.colors["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(self.tab_config, command=canvas.yview)
        frame = ttk.Frame(canvas)
        canvas.create_window((0,0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        r, c = 0, 0
        for category, items in self.config.items():
            if not isinstance(items, dict): continue
            lf = tk.LabelFrame(frame, text=f" {category.upper()} ", font=("Segoe UI", 9, "bold"), bg="white", padx=10, pady=10)
            lf.grid(row=r, column=c, sticky="nsew", padx=10, pady=10)
            
            sub_r = 0
            for k, v in items.items():
                if isinstance(v, dict): continue
                tk.Label(lf, text=k, bg="white").grid(row=sub_r, column=0, sticky="w")
                var = tk.StringVar(value=str(v))
                self.input_vars[f"{category}.{k}"] = var
                ttk.Entry(lf, textvariable=var, width=12).grid(row=sub_r, column=1, padx=5)
                sub_r+=1
            c+=1
            if c > 3: 
                c=0 
                r+=1
        
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    # --- INTERACTIVE EXPLORER ---
    def build_interactive_tab(self):
        # Paned Window: Left (BOM List), Right (Detail View)
        paned = ttk.PanedWindow(self.tab_interactive, orient='horizontal')
        paned.pack(fill="both", expand=True)
        
        # LEFT: BOM TREE
        frame_left = ttk.Frame(paned, padding=0)
        paned.add(frame_left, weight=1)
        
        cols = ("Part", "Spec")
        self.tree = ttk.Treeview(frame_left, columns=cols, show="tree headings")
        self.tree.heading("#0", text="Système / Composant")
        self.tree.heading("Part", text="Élément")
        self.tree.heading("Spec", text="Spécification")
        self.tree.column("#0", width=250)
        self.tree.column("Part", width=200)
        self.tree.column("Spec", width=150)
        
        sb = ttk.Scrollbar(frame_left, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # RIGHT: DETAIL PANEL
        self.detail_frame = tk.Frame(paned, bg="white", bd=1, relief="solid")
        paned.add(self.detail_frame, weight=2)
        
        # Initial State
        self.lbl_empty = tk.Label(self.detail_frame, text="Sélectionnez un composant pour voir les détails", 
                                  bg="white", fg="#999", font=("Segoe UI", 12))
        self.lbl_empty.pack(expand=True)
        
        # Content Container (Hidden initially)
        self.content_container = tk.Frame(self.detail_frame, bg="white")

    def on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        item_id = sel[0]
        item = self.tree.item(item_id)
        
        # Clean Right Panel
        self.lbl_empty.pack_forget()
        for w in self.content_container.winfo_children(): w.destroy()
        self.content_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Check if it's a "Component" with rich data (Piston, Bielle...)
        comp_name = item['text']
        # Map Tree Label to Results Key if needed
        # In populate, I will use IDs that match keys if possible
        
        # Look for data in 'shsem_components'
        comp_data = None
        comps = self.current_results.get('MechanicalAgent', {}).get('shsem_components', {})
        
        if comp_name in comps: # Check mechanical
            comp_data = comps[comp_name]
        else:
            # Check other agents
            for agent_name in ['FreePistonAgent', 'DogClutchAgent']:
                c = self.current_results.get(agent_name, {}).get('shsem_components', {})
                if comp_name in c:
                    comp_data = c[comp_name]
                    break
        
        if comp_data:
            self.show_component_details(comp_name, comp_data)
        elif item_id.startswith("BOM_"):
            # Show Standard BOM Info
            vals = item['values']
            self.show_simple_bom_details(item['text'], vals)
        else:
             tk.Label(self.content_container, text=f"Info: {item['text']}", bg="white", font=("Segoe UI", 14, "bold")).pack()

    def show_component_details(self, name, data):
        # Title
        tk.Label(self.content_container, text=name.upper(), bg="white", fg=self.colors["primary"], font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0,10))
        
        # Notebook for details
        nb = ttk.Notebook(self.content_container)
        nb.pack(fill="both", expand=True)
        
        # Data Tab
        tab_data = tk.Frame(nb, bg="white", padx=20, pady=20)
        nb.add(tab_data, text="Données Techniques")
        
        # Material
        tk.Label(tab_data, text="Matériau:", bg="white", fg="#777").grid(row=0, column=0, sticky="w")
        tk.Label(tab_data, text=data.get('material', '-'), bg="white", font=("Segoe UI", 11, "bold")).grid(row=0, column=1, sticky="w", padx=10)
        
        # Specs List
        r = 2
        tk.Label(tab_data, text="Géométrie & Masse", bg="white", font=("Segoe UI", 10, "bold", "underline")).grid(row=1, column=0, sticky="w", pady=(10,5))
        for k, v in data.get('specs', []):
            tk.Label(tab_data, text=k, bg="white").grid(row=r, column=0, sticky="w")
            tk.Label(tab_data, text=v, bg="white", fg="#333").grid(row=r, column=1, sticky="w", padx=10)
            r += 1

        # Stress & Wear Limit Bars
        r += 1
        tk.Label(tab_data, text="Résistance & Usure (RDM)", bg="white", font=("Segoe UI", 10, "bold", "underline")).grid(row=r, column=0, sticky="w", pady=(15,5))
        r += 1
        
        for k, val_str, limit in data.get('stress_data', []):
            # Parse value
            try:
                val = float(val_str.split()[0])
                if isinstance(limit, (int, float)):
                    pct = min((val / limit) * 100, 100)
                    color = self.colors["success"] if pct < 80 else "#ffcc00" if pct < 100 else "#ff3b30"
                else: 
                    pct = 0
                    color = "#999"
            except:
                pct = 0
                color = "#999"
                
            tk.Label(tab_data, text=k, bg="white").grid(row=r, column=0, sticky="w")
            tk.Label(tab_data, text=val_str, bg="white").grid(row=r, column=1, sticky="w", padx=10)
            
            # Bar
            cv = tk.Canvas(tab_data, width=150, height=10, bg="#eee", highlightthickness=0)
            cv.grid(row=r, column=2, padx=10)
            cv.create_rectangle(0, 0, 1.5*pct, 10, fill=color, outline="")
            
            if isinstance(limit, (int, float)):
                tk.Label(tab_data, text=f"(Lim: {limit})", bg="white", fg="#777", font=("Segoe UI", 8)).grid(row=r, column=3)
            r += 1

        # Manufacturing
        r += 1
        tk.Label(tab_data, text="Fabrication", bg="white", font=("Segoe UI", 10, "bold", "underline")).grid(row=r, column=0, sticky="w", pady=(15,5))
        r += 1
        manuf = data.get('manufacturing', {})
        for k, v in manuf.items():
             tk.Label(tab_data, text=k, bg="white").grid(row=r, column=0, sticky="w")
             tk.Label(tab_data, text=v, bg="white").grid(row=r, column=1, sticky="w", padx=10)
             r+=1

        # Sketch Tab
        tab_draw = tk.Frame(nb, bg="white", padx=20, pady=20)
        nb.add(tab_draw, text="Plans & Croquis")
        
        # Load specific sketch
        # Sketches dict is in all_results['Sketches'] but it's a dict now?
        # Main.py returns a list path or dict? Need to check main.py.
        # sketches_tech.py returns a Dict. main.py puts it in 'Sketches'.
        
        sketches = self.current_results.get('Sketches', {})
        sketch_path = sketches.get(name) # Key matches "Piston", "Bielle"
        
        if sketch_path and os.path.exists(sketch_path):
             pil_img = Image.open(sketch_path)
             # Resize to fit
             pil_img.thumbnail((500, 500))
             tk_img = ImageTk.PhotoImage(pil_img)
             self.image_refs.append(tk_img) # keep ref
             tk.Label(tab_draw, image=tk_img, bg="white").pack()
             tk.Label(tab_draw, text=f"Fichier: {os.path.basename(sketch_path)}", bg="white", fg="#999").pack(pady=5)
        else:
            tk.Label(tab_draw, text="Aucun croquis spécifique disponible.", bg="white").pack()
            
    def show_simple_bom_details(self, text, values):
        tk.Label(self.content_container, text=text, bg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(self.content_container, text=f"Spécification: {values[0]}", bg="white").pack(anchor="w", pady=5)
        # Add a generic placeholder image or icon
        
    def populate_tree(self, res):
        self.tree.delete(*self.tree.get_children())
        
        # 1. System Summary (N_cyl)
        thermo = res.get('ThermodynamicAgent', {})
        N_cyl = thermo.get('N_cylinders', 1)
        mass_sys = thermo.get('Est_System_Mass_kg', 0)
        
        root_sys = self.tree.insert("", "end", text=f"Architecture Globale ({N_cyl} Cyl.)", open=True)
        self.tree.insert(root_sys, "end", text="Masse Système (Est.)", values=(f"{mass_sys:.1f} kg", f"Obj < 50kg"))
        self.tree.insert(root_sys, "end", text="Alésage x Course", values=(f"{thermo.get('Bore_mm',0):.1f} x {thermo.get('Stroke_mm',0):.1f} mm", "Carré"))
        
        # 2. Main Components (Interactive - Aggregated from all agents)
        root_mech = self.tree.insert("", "end", text="Organes Mécaniques (Détaillés)", open=True)
        
        # Helper to add comps from an agent
        def add_agent_comps(agent_name):
            agent_res = res.get(agent_name, {})
            comps = agent_res.get('shsem_components', {})
            for name, data in comps.items():
                # Avoid duplicates if any
                if not self.tree.exists(name):
                    self.tree.insert(root_mech, "end", text=name, values=("Voir détail >>", data.get('material')))
        
        add_agent_comps('MechanicalAgent')
        add_agent_comps('FreePistonAgent')
        add_agent_comps('DogClutchAgent')
            
        # 2. General BOM
        root_bom = self.tree.insert("", "end", text="BOM Globale", open=True)
        bom_list = res.get('BOMAgent', {}).get('BOM_List', [])
        
        # Group by 'Group'
        groups = {}
        for item in bom_list:
            g = item.get('Group', 'Divers')
            if g not in groups: groups[g] = []
            groups[g].append(item)
            
        for g_name, items in groups.items():
            g_node = self.tree.insert(root_bom, "end", text=g_name, open=False)
            for it in items:
                self.tree.insert(g_node, "end", text=it.get('Part'), values=(it.get('Spec'), it.get('Material')), iid=f"BOM_{it['Part']}")

    def build_logs_tab(self):
        self.txt_log = tk.Text(self.tab_logs, bg="#222", fg="#0f0", font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True)

    def run_sim_thread(self):
        # Save config
        for k, v in self.input_vars.items():
             cat, key = k.split(".", 1)
             try: self.config[cat][key] = float(v.get())
             except: self.config[cat][key] = v.get()
        with open(self.config_path, "w") as f: json.dump(self.config, f)
        
        self.txt_log.delete(1.0, tk.END)
        self.notebook.select(self.tab_logs)
        
        def task():
            old_out = sys.stdout
            sys.stdout = RedirectText(self.txt_log)
            try:
                print(">>> CALCUL EN COURS...")
                self.current_results = run_full_sizing(self.config)
                
                print(">>> CHARGEMENT DE L'INTERFACE INTERACTIVE...")
                self.populate_tree(self.current_results)
                
                print(">>> DONE.")
                messagebox.showinfo("Succès", "Simulation Terminée")
                self.notebook.select(self.tab_interactive)
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()
            finally:
                sys.stdout = old_out
                
        threading.Thread(target=task).start()

def main():
    root = tk.Tk()
    app = MinimalistGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
