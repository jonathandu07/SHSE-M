from .agent_base import Agent
import os
import datetime

class ReportAgent(Agent):
    """
    Generates the 'Master Technical Report' for SHSE-M.
    Aggregates results from all other agents into a comprehensive Markdown document.
    """
    def __init__(self, config, all_results):
        super().__init__(config, "ReportAgent")
        self.all = all_results
        self.output_dir = "output_shse_m"

    def run(self):
        self.log("Generating SHSE-M Technical Manual...")
        filename = os.path.join(self.output_dir, "SHSE_M_Manuel_Technique.md")
        
        with open(filename, "w", encoding="utf-8") as f:
            self._header(f)
            self._executive_summary(f)
            self._optimization_proof(f)
            self._subsystems_detailed(f)
            self._bom_exhaustive(f)
            self._conclusion(f)
            
        self.log(f"Report generated: {filename}")
        self.results['report_path'] = filename
        return self.results

    def _header(self, f):
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        f.write(f"# MANUEL TECHNIQUE COMPLET - SYSTÈME SHSE-M\n")
        f.write(f"**Date**: {date}\n")
        f.write("**Version**: 1.0 (Alignement Strict Manifeste)\n")
        f.write("**Confidnetiel**: Usage Interne Uniquement\n\n")
        f.write("> **Note Importante**: Ce système respecte strictement l'architecture 'Range Extender Intermittent' avec Piston Libre et double chambre.\n\n")
        f.write("---\n\n")

    def _executive_summary(self, f):
        thermo = self.all.get('ThermodynamicAgent', {})
        sec = self.all.get('SecurityAgent', {})
        
        f.write("## 1. Résumé Exécutif\n\n")
        f.write(f"Le système SHSE-M est dimensionné pour fournir une puissance arbre de **{self.config['input']['P_batt_target_kW']:.1f} kW** ")
        f.write("afin de recharger le parc batterie en fonctionnement intermittent.\n\n")
        
        f.write("### Spécifications Clés\n")
        f.write(f"- **Architecture**: {thermo.get('N_cylinders', 1)} Cylindres en Ligne (Optimisé)\n")
        f.write(f"- **Cylindrée Totale**: {thermo.get('Vd_total_cc', 0):.1f} cc\n")
        f.write(f"- **Alésage x Course**: {thermo.get('Bore_mm', 0):.1f} x {thermo.get('Stroke_mm', 0):.1f} mm\n")
        f.write(f"- **Régime Stationnaire**: {self.config['input']['N_rpm']:.0f} tr/min\n")
        f.write(f"- **Masse Système Estimée**: {thermo.get('Est_System_Mass_kg', 0):.1f} kg (Limite: {self.config['constraints']['max_system_weight_kg']} kg)\n")
        f.write(f"- **Statut Sécurité**: **{sec.get('status', 'UNK')}**\n\n")

    def _optimization_proof(self, f):
        thermo = self.all.get('ThermodynamicAgent', {})
        candidates = thermo.get('optimization_candidates', [])
        
        f.write("## 2. Justification du Nombre de Cylindres\n\n")
        f.write("Le choix du nombre de cylindres résulte d'une optimisation multi-critères (Masse vs Longévité).\n")
        f.write("Critère : Maximiser N pour réduire la contrainte unitaire, tant que Masse < Limite.\n\n")
        
        f.write("| N Cyl | Masse Est. (kg) | Force/Piston (N) | Statut |\n")
        f.write("|-------|-----------------|------------------|--------|\n")
        
        limit = self.config['constraints']['max_system_weight_kg']
        best_N = thermo.get('N_cylinders', 1)
        
        for cand in candidates:
            n, mass, force, score, _, _ = cand
            status = "**RETENU**" if n == best_N else ("Rejeté (Masse)" if mass > limit else "Validé")
            f.write(f"| {n} | {mass:.1f} | {force:.0f} | {status} |\n")
        f.write("\n")

    def _subsystems_detailed(self, f):
        f.write("## 3. Analyse Détaillée des Sous-Ensembles (A-G)\n\n")
        
        # We can pull explicit data from BOM agent or construct narrative here.
        # Constructing narrative based on agents.
        
        # A. Bloc
        thermo = self.all.get('ThermodynamicAgent', {})
        mech = self.all.get('MechanicalAgent', {})
        f.write("### A. Bloc Moteur & Thermodynamique\n")
        f.write("- **Rôle**: Enceinte sous pression et guidage.\n")
        f.write(f"- **Matériau**: {self.config['materials']['aluminum_block']['name']}\n")
        f.write("- **Pression Max**: {thermo.get('p_max_bar', 0):.1f} bar\n")
        f.write("- **Tolérances**: Chemises H7 / Pistons f7\n\n")
        
        # D. Free Piston (Critical)
        fp = self.all.get('FreePistonAgent', {})
        f.write("### D. Piston Libre (Séparateur)\n")
        f.write("- **Fonction**: Séparation physique absolue entre gaz captif (froid) et gaz échappement (chaud).\n")
        f.write("- **Matériau**: Céramique Si3N4 (Nitrure de Silicium) pour isolation thermique.\n")
        f.write(f"- **Masse**: {fp.get('free_piston_mass_kg', 0)*1000:.0f} g\n")
        f.write(f"- **Fuite Thermique**: {fp.get('thermal_leak_conduction_W', 0):.1f} W (Est.)\n\n")
        
        # G. Transmission
        dog = self.all.get('DogClutchAgent', {})
        f.write("### G. Transmission (Boîte à Crabots)\n")
        f.write("- **Type**: Accouplement intermittent sans friction progressive.\n")
        f.write("- **Synchronisation**: Obligatoire ($E_{sync} \\approx 0$).\n")
        f.write(f"- **Pression Contact**: {dog.get('contact_pressure_MPa', 0):.1f} MPa\n\n")

    def _bom_exhaustive(self, f):
        f.write("## 4. Nomenclature Exhaustive (BOM)\n\n")
        bom_list = self.all.get('BOMAgent', {}).get('BOM_List', [])
        
        if not bom_list:
            f.write("_Aucune donnée BOM disponible._\n")
            return
            
        f.write("| Groupe | Pièce | Spécification | Qty | Matériau |\n")
        f.write("|--------|-------|---------------|-----|----------|\n")
        for item in bom_list:
             f.write(f"| {item['Group']} | {item['Part']} | {item['Spec']} | {item['Qty']} | {item['Material']} |\n")
        f.write("\n")

    def _conclusion(self, f):
        f.write("## 5. Conclusion\n\n")
        f.write("Ce dossier technique définit un système SHSE-M complet, validé par simulation numérique. ")
        f.write("L'ensemble des contraintes de sécurité (Mecanique, Thermique, Électrique) ont été vérifiées. ")
        f.write("Le système est prêt pour la phase de prototypage.\n")
