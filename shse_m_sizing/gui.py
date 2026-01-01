import tkinter as tk
from tkinter import ttk, messagebox
import os
import csv
from .config import InputParameters, Efficiencies, Constraints, DimensionResults
from .thermodynamics import calculate_thermodynamics
from .mechanical import dimension_components
from .check import verify_constraints
from .report import generate_markdown_report, generate_bom_csv, generate_json_export
from .sketches import generate_sketches
from .materials import list_materials_by_category

class ModernSHSEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dimensionnement SHSE-M - Suite Complète")
        self.root.geometry("1000x800")
        
        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook.Tab", font=('Helvetica', 10, 'bold'))
        style.configure("Treeview.Heading", font=('Helvetica', 9, 'bold'))
        
        # NOTEBOOK (TABS)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)
        
        # TABS
        self.tab_config = ttk.Frame(self.notebook)
        self.tab_results = ttk.Frame(self.notebook)
        self.tab_sketches = ttk.Frame(self.notebook)
        self.tab_report = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_config, text=" 1. CONFIGURATION ")
        self.notebook.add(self.tab_results, text=" 2. DONNÉES TECHNIQUES ")
        self.notebook.add(self.tab_sketches, text=" 3. CROQUIS & SCHÉMAS ")
        self.notebook.add(self.tab_report, text=" 4. RAPPORT TEXTE ")
        
        self.vars = {}
        self.image_refs = [] # Keep references to avoid GC
        
        self._build_config_tab()
        self._build_results_tab()
        self._build_sketches_tab()
        self._build_report_tab()

    # --- TAB 1: CONFIG ---
    def _build_config_tab(self):
        container = ttk.Frame(self.tab_config)
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Columns
        left = ttk.Frame(container)
        right = ttk.Frame(container)
        left.pack(side="left", fill="both", expand=True)
        right.pack(side="right", fill="both", expand=True)
        
        # Sections
        self._create_input_group(left, "Objectifs & Cycle", [
            ("Puissance Batterie (kW):", "P_batt_target", 10.0),
            ("Régime (tr/min):", "N_rpm", 3000.0),
            ("Pression Moy. (bar):", "p_me_target_bar", 6.0),
            ("Nb Cylindres:", "N_cyl", 1.0)
        ])
        
        self._create_input_group(left, "Rendements", [
            ("Thermique:", "eta_th", 0.22),
            ("Mécanique:", "eta_m", 0.85),
            ("Générateur:", "eta_gen", 0.90),
            ("Électronique:", "eta_elec", 0.95),
            ("Charge:", "eta_charge", 0.95)
        ])
        
        self._create_input_group(right, "Contraintes Géométriques", [
            ("Ratio Stroke/Bore:", "S_over_B", 1.0),
            ("Ratio Bielle/Manivelle:", "rod_lambda", 3.5),
            ("Coeff. Fluctuation (Volant):", "flywheel_Cf", 0.05),
            ("U_p_max (m/s):", "U_p_max", 6.0),
            ("Phi (p_me/p_max):", "phi", 0.35),
            ("Facteur Sécurité (SF):", "safety_factor", 2.0)
        ])
        
        # Material Selectors
        self._create_material_group(right, "Matériaux", [
            ("Cylindre:", "mat_cylinder", "Alu_6061_T6", "Aluminum"),
            ("Piston:", "mat_piston", "Alu_2618A", "Aluminum"),
            ("Bielle:", "mat_rod", "42CrMo4_QT", "Steel"),
            ("Vilebrequin:", "mat_crank", "42CrMo4_QT", "Steel"),
            ("Visserie:", "mat_bolt", "42CrMo4_QT", "Steel")
        ])
        
        # Big Button
        btn_calc = ttk.Button(container, text="▶ LANCER LE CALCUL COMPLET", command=self.run_calculation)
        btn_calc.pack(side="bottom", fill="x", pady=20)

    def _create_input_group(self, parent, title, items):
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.pack(fill="x", padx=5, pady=5)
        for i, (label, var_name, default) in enumerate(items):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.DoubleVar(value=default)
            self.vars[var_name] = var
            ttk.Entry(frame, textvariable=var, width=15).grid(row=i, column=1, sticky="e", pady=2)

    def _create_material_group(self, parent, title, items):
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.pack(fill="x", padx=5, pady=5)
        for i, (label, var_name, default, category) in enumerate(items):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=default)
            self.vars[var_name] = var
            
            # Combo with filtered list
            values = list_materials_by_category(None) # Or filter by category if strictly enforced
            combo = ttk.Combobox(frame, textvariable=var, values=values, width=25, state="readonly")
            combo.grid(row=i, column=1, sticky="e", pady=2)

    # --- TAB 2: RESULTS (TREEVIEW) ---
    def _build_results_tab(self):
        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(self.tab_results)
        tree_scroll_y.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(self.tab_results, columns=("Detail", "Valeur", "Unite", "Info"), show="headings", yscrollcommand=tree_scroll_y.set)
        tree_scroll_y.config(command=self.tree.yview)
        
        self.tree.heading("Detail", text="Paramètre / Composant")
        self.tree.heading("Valeur", text="Valeur")
        self.tree.heading("Unite", text="Unité")
        self.tree.heading("Info", text="Note")
        
        self.tree.column("Detail", width=300)
        self.tree.column("Valeur", width=100)
        self.tree.column("Unite", width=80)
        self.tree.column("Info", width=200)
        
        self.tree.pack(fill="both", expand=True)

    # --- TAB 3: SKETCHES ---
    def _build_sketches_tab(self):
        self.canvas_sketches = tk.Canvas(self.tab_sketches, bg="white")
        scr_y = ttk.Scrollbar(self.tab_sketches, orient="vertical", command=self.canvas_sketches.yview)
        
        self.frame_images = ttk.Frame(self.canvas_sketches)
        
        self.canvas_sketches.configure(yscrollcommand=scr_y.set)
        
        # Layout
        scr_y.pack(side="right", fill="y")
        self.canvas_sketches.pack(side="left", fill="both", expand=True)
        
        self.canvas_sketches.create_window((0,0), window=self.frame_images, anchor="nw")
        self.frame_images.bind("<Configure>", lambda e: self.canvas_sketches.configure(scrollregion=self.canvas_sketches.bbox("all")))

    # --- TAB 4: REPORT ---
    def _build_report_tab(self):
        self.txt_report = tk.Text(self.tab_report, wrap="word", padx=10, pady=10)
        scr = ttk.Scrollbar(self.tab_report, command=self.txt_report.yview)
        self.txt_report.configure(yscrollcommand=scr.set)
        
        scr.pack(side="right", fill="y")
        self.txt_report.pack(fill="both", expand=True)

    # --- LOGIC ---
    def run_calculation(self):
        try:
            # 1. READ INPUTS
            inputs = self._get_inputs()
            
            # 2. RUN MODULES
            res = calculate_thermodynamics(inputs)
            res = dimension_components(inputs, res)
            res = verify_constraints(inputs, res)
            
            # 3. GENERATE FILES & IMAGES
            output_dir = os.path.abspath("output_shse_m")
            os.makedirs(output_dir, exist_ok=True)
            
            try:
                generate_sketches(inputs, res, output_dir)
            except Exception as e:
                print(f"Sketch Error: {e}")
            
            generate_markdown_report(inputs, res, os.path.join(output_dir, "rapport.md"))
            generate_bom_csv(res, os.path.join(output_dir, "bom.csv"))
            generate_json_export(inputs, res, os.path.join(output_dir, "params.json"))
            
            # 4. UPDATE UI
            self._update_results_tree(res, os.path.join(output_dir, "bom.csv"))
            self._update_sketches_display(res)
            self._update_report_text(os.path.join(output_dir, "rapport.md"))
            
            # Switch to results tab
            self.notebook.select(self.tab_results)
            messagebox.showinfo("Calcul Terminé", "Dimensionnement effectué avec succès !")
            
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _get_inputs(self):
        return InputParameters(
            P_batt_target=self.vars["P_batt_target"].get(),
            N_rpm=self.vars["N_rpm"].get(),
            p_me_target_bar=self.vars["p_me_target_bar"].get(),
            N_cyl=int(self.vars["N_cyl"].get()),
            eta=Efficiencies(
                eta_th=self.vars["eta_th"].get(),
                eta_m=self.vars["eta_m"].get(),
                eta_gen=self.vars["eta_gen"].get(),
                eta_elec=self.vars["eta_elec"].get(),
                eta_charge=self.vars["eta_charge"].get(),
            ),
            limits=Constraints(
                U_p_max=self.vars["U_p_max"].get(),
                S_over_B=self.vars["S_over_B"].get(),
                phi=self.vars["phi"].get(),
                safety_factor=self.vars["safety_factor"].get(),
                rod_lambda=self.vars["rod_lambda"].get(),
                flywheel_Cf=self.vars["flywheel_Cf"].get(),
                
                # Material Strings
                mat_cylinder=self.vars["mat_cylinder"].get(),
                mat_piston=self.vars["mat_piston"].get(),
                mat_rod=self.vars["mat_rod"].get(),
                mat_crank=self.vars["mat_crank"].get(),
                mat_bolt=self.vars["mat_bolt"].get()
            )
        )

    def _update_results_tree(self, res, bom_path):
        # Clear
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add summary rows first
        self.tree.insert("", "end", values=("Puissance BAT Cible", f"{self.vars['P_batt_target'].get()}", "kW", "Entrée"))
        self.tree.insert("", "end", values=("Vitesse Piston", f"{res.U_mean:.2f}", "m/s", "Calculé"))
        self.tree.insert("", "end", values=("Pression Max", f"{res.p_max/1e5:.1f}", "bar", "Calculé"))
        
        # Load detailed BOM
        if os.path.exists(bom_path):
            with open(bom_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader) # Skip header
                for row in reader:
                    # CSV: System, Comp, Detail, Val, Unit, Mat, Note
                    # We map to: Detail= Comp + Detail, Val, Unit, Note=Mat
                    detail_str = f"{row[1]} - {row[2]}"
                    self.tree.insert("", "end", values=(detail_str, row[3], row[4], row[5]))
        
        # Warnings Highlight
        if res.warnings:
            web_id = self.tree.insert("", "0", values=("!!! ALERTE !!!", str(len(res.warnings)), "-", "Voir Rapport"), tags=('warning',))
            self.tree.tag_configure('warning', foreground='red', background='yellow')

    def _update_sketches_display(self, res):
        # Clear old images
        for widget in self.frame_images.winfo_children():
            widget.destroy()
        self.image_refs = []
        
        if not res.sketch_paths:
            ttk.Label(self.frame_images, text="Aucun croquis généré.").pack()
            return
            
        for path in res.sketch_paths:
            if os.path.exists(path):
                # Frame for each image
                fr = ttk.Frame(self.frame_images, relief="groove", padding=5)
                fr.pack(pady=10, padx=10, fill="x")
                
                ttk.Label(fr, text=os.path.basename(path)).pack()
                
                img = tk.PhotoImage(file=path)
                # Downscale if huge? Tkinter PhotoImage has no resize, usually standard.
                # Matplotlib saves reasonably sized PNGs (600x800).
                
                lbl = ttk.Label(fr, image=img)
                lbl.pack()
                self.image_refs.append(img) # Prevent GC

    def _update_report_text(self, path):
        self.txt_report.delete(1.0, tk.END)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.txt_report.insert(tk.END, f.read())

def main():
    root = tk.Tk()
    app = ModernSHSEApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
