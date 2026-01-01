import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import threading
from .config import InputParameters, Efficiencies, Constraints
from .thermodynamics import calculate_thermodynamics
from .mechanical import dimension_components
from .check import verify_constraints
from .report import generate_markdown_report, generate_bom_csv, generate_json_export

class SHSEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dimensionnement SHSE-M")
        self.root.geometry("900x700")
        
        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # Main Frame with Scrollbar
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=1)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Input Variables
        self.vars = {}
        
        self._build_ui()
        
    def _create_section(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.pack(fill="x", padx=10, pady=5)
        return frame
        
    def _add_input(self, parent, label_text, var_name, default_value, row, col=0):
        ttk.Label(parent, text=label_text).grid(row=row, column=col*2, sticky="w", padx=5, pady=2)
        var = tk.DoubleVar(value=default_value)
        self.vars[var_name] = var
        entry = ttk.Entry(parent, textvariable=var, width=15)
        entry.grid(row=row, column=col*2+1, sticky="w", padx=5, pady=2)
        return var

    def _build_ui(self):
        # Header
        header = ttk.Label(self.scrollable_frame, text="Paramètres de Dimensionnement", font=("Helvetica", 14, "bold"))
        header.pack(pady=10)
        
        # Section 1: Cibles et Basiques
        s1 = self._create_section(self.scrollable_frame, "1. Cibles de Performance")
        self._add_input(s1, "Puissance Batterie (kW):", "P_batt_target", 10.0, 0, 0)
        self._add_input(s1, "Régime (tr/min):", "N_rpm", 3000.0, 0, 1)
        self._add_input(s1, "Pression Moyenne (bar):", "p_me_target_bar", 6.0, 1, 0)
        self._add_input(s1, "Nb Cylindres:", "N_cyl", 1.0, 1, 1) # cast to int later

        # Section 2: Rendements
        s2 = self._create_section(self.scrollable_frame, "2. Chaîne de Rendement")
        self._add_input(s2, "Thermique:", "eta_th", 0.22, 0, 0)
        self._add_input(s2, "Mécanique:", "eta_m", 0.85, 0, 1)
        self._add_input(s2, "Générateur:", "eta_gen", 0.90, 1, 0)
        self._add_input(s2, "Élec. Puissance:", "eta_elec", 0.95, 1, 1)
        self._add_input(s2, "Charge Batterie:", "eta_charge", 0.95, 2, 0)

        # Section 3: Contraintes & Durabilité
        s3 = self._create_section(self.scrollable_frame, "3. Contraintes & Matériaux")
        self._add_input(s3, "Vit. Piston Max (m/s):", "U_p_max", 6.0, 0, 0)
        self._add_input(s3, "Ratio Course/Alésage:", "S_over_B", 1.0, 0, 1)
        self._add_input(s3, "Facteur Phi (p_me/p_max):", "phi", 0.35, 1, 0)
        self._add_input(s3, "Facteur Sécurité (SF):", "safety_factor", 2.0, 1, 1)
        self._add_input(s3, "Limite Acier (Pa):", "sigma_adm_steel", 400e6, 2, 0)
        self._add_input(s3, "Limite Alu (Pa):", "sigma_adm_alum", 150e6, 2, 1)
        
        # Section 4: Output
        s4 = self._create_section(self.scrollable_frame, "Actions")
        btn = ttk.Button(s4, text="LANCER LE CALCUL", command=self.run_calculation)
        btn.pack(pady=10, fill="x")
        
        self.output_text = tk.Text(self.scrollable_frame, height=20, width=100)
        self.output_text.pack(padx=10, pady=10)
        
        btn_open = ttk.Button(self.scrollable_frame, text="Ouvrir le dossier de sortie", command=self.open_output_dir)
        btn_open.pack(pady=5)

from .sketches import generate_sketches

    def run_calculation(self):
        try:
            # Build Input Object (Safe Float Conversion)
            inputs = InputParameters(
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
                    sigma_adm_steel=self.vars["sigma_adm_steel"].get(),
                    sigma_adm_alum=self.vars["sigma_adm_alum"].get(),
                )
            )
            
            # Logic
            res = calculate_thermodynamics(inputs)
            res = dimension_components(inputs, res)
            res = verify_constraints(inputs, res)
            
            # Generate Output Dir
            output_dir = os.path.abspath("output_shse_m")
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate Sketches
            try:
                generate_sketches(inputs, res, output_dir)
            except Exception as e:
                print(f"Erreur Sketches: {e}")
                # Don't fail the whole run if plotting fails
            
            # Generate Files
            generate_markdown_report(inputs, res, os.path.join(output_dir, "rapport_dimensionnement.md"))
            generate_bom_csv(res, os.path.join(output_dir, "nomenclature.csv"))
            generate_json_export(inputs, res, os.path.join(output_dir, "parametres.json"))
            
            # Display Report
            with open(os.path.join(output_dir, "rapport_dimensionnement.md"), "r", encoding="utf-8") as f:
                report_content = f.read()
            
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, report_content)
            
            messagebox.showinfo("Succès", f"Calcul terminé.\nFichiers et Croquis générés dans:\n{output_dir}")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Une erreur est survenue:\n{str(e)}")

    def open_output_dir(self):
        output_dir = os.path.abspath("output_shse_m")
        if os.path.exists(output_dir):
            os.startfile(output_dir)
        else:
            messagebox.showwarning("Info", "Dossier de sortie inexistant (lancez un calcul d'abord).")

def main():
    root = tk.Tk()
    app = SHSEApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
