import csv
import json
from .agent_base import Agent

class BOMAgent(Agent):
    """
    Generates Bill of Materials.
    """
    def __init__(self, config, all_results):
        super().__init__(config, "BOMAgent")
        self.all_results = all_results

    def _add(self, bom_list, group, part, spec, qty, mat):
        bom_list.append({
            "Group": group,
            "Part": part,
            "Spec": spec,
            "Qty": qty,
            "Material": mat
        })

    def run(self):
        thermo = self.all_results.get('ThermodynamicAgent', {})
        mech = self.all_results.get('MechanicalAgent', {})
        
        # Get Cylinder Count
        try:
            N_cyl = int(thermo.get('N_cylinders', 1))
        except:
            N_cyl = 1
            
        self.log(f"Generating Exhaustive BOM for {N_cyl} Cylinders...")
        bom = []

        # Helper for standard parts
        def add_std(group, part, spec, qty, mat):
            self._add(bom, group, part, spec, qty, mat)

        # 1. Cylinder Block Group (A)
        g = "A. Bloc Thermo-Pneumatique"
        
        # Major
        add_std(g, "Carter Monobloc", "Usiné CNC / Moulé", 1, "Alu 6061-T6")
        add_std(g, "Chemise Cylindre", f"Ø{thermo.get('Bore_mm',0):.1f} H7 (Traîtée)", N_cyl, "Fonte GS 600-3")
        add_std(g, "Culasse (Chambre Chaude)", "Design Hémisphérique", N_cyl, "Inconel 718")
        add_std(g, "Couvre-Culasse", "Étanchéité", 1, "Alu / Composite")
        
        # Seals & Fasteners
        add_std(g, "Joint de Culasse", "Multi-feuilles MLS", N_cyl, "Inox/Viton")
        add_std(g, "Joint Torique Chemise (Haut)", "Viton Ø98x2", N_cyl, "FKM")
        add_std(g, "Joint Torique Chemise (Bas)", "Viton Ø98x2", N_cyl, "FKM")
        add_std(g, "Goujons de Culasse", "M12 x 1.5 - Classe 12.9", 6*N_cyl, "Acier Haute Résistance")
        add_std(g, "Écrous de Culasse", "M12 Embase", 6*N_cyl, "Acier 12.9")
        add_std(g, "Rondelles Culasse", "M12 Durcies", 6*N_cyl, "Acier Trempé")
        add_std(g, "Vis Carter", "M8 x 30 CHC", 14, "Acier 8.8 Zingué")
        add_std(g, "Bouchon Vidange/Purge", "M14 x 1.25 + Joint Cuivre", 2, "Acier/Cuivre")
        add_std(g, "Pions de Centrage", "Ø8 x 16", 4, "Acier Rectifié")

        # 2. Piston Group (C + F)
        g = "C. Attelage Mobile (Piston)"
        add_std(g, "Piston Moteur", f"Ø{mech.get('piston_diameter',0):.1f} f7 (Forgé)", N_cyl, "Alu 2618A")
        add_std(g, "Axe de Piston", f"Ø{mech.get('pin_diameter_mm',0):.1f} g6 (DLC)", N_cyl, "Acier 16MnCr5")
        add_std(g, "Clips Axe Piston", "Circlips Intérieur Ø30", 2*N_cyl, "Acier Ressort")
        add_std(g, "Segment Feu", "Cromé / Barrel", N_cyl, "Acier Inox")
        add_std(g, "Segment Étanchéité", "Bec d'aigle", N_cyl, "Fonte Nodulaire")
        add_std(g, "Segment Racleur", "3 pièces (Ressort)", N_cyl, "Acier/Expander Inox")
        
        # Piston Libre
        g = "D. Piston Libre / Séparateur"
        fp_res = self.all_results.get('FreePistonAgent', {})
        add_std(g, "Piston Libre", f"Si3N4 Ø{thermo.get('Bore_mm',0):.1f} (Masse {fp_res.get('free_piston_mass_kg',0)*1000:.0f}g)", N_cyl, "Céramique Si3N4")
        add_std(g, "Segments Piston Libre", "Polymère Haute Temp (PEEK)", 2*N_cyl, "PEEK / Bronze")
        add_std(g, "Ressort de Rappel (Opt)", "Pneumatique ou Méca", N_cyl, "Acier Ressort")

        # 3. Rod & Crank (F)
        g = "F. Conversion Mécanique (Bas Moteur)"
        add_std(g, "Bielle", f"Entraxe {mech.get('rod_length_mm',0):.1f} (I-Beam)", N_cyl, "Acier Forgé 42CrMo4")
        add_std(g, "Vis de Bielle", "ARP 2000 M9x1.0", 2*N_cyl, "Acier Haute Résistance")
        add_std(g, "Coussinets Bielle (Paire)", "Trimétal (Al-Sn-Cu)", N_cyl, "Standard SAE")
        add_std(g, "Vilebrequin", f"{N_cyl} Cylindres / Course 95mm", 1, "Acier 42CrMo4 Nitruré")
        add_std(g, "Clavette Vilebrequin", "Disque / Woodruff", 1, "Acier C45")
        add_std(g, "Paliers Vilebrequin (Main)", "Roulements à Rouleaux ou Lisses", N_cyl+1, "100Cr6 / Bronze")
        add_std(g, "Joint Spy Vilebrequin AV", "Double Lèvre", 1, "FKM")
        add_std(g, "Joint Spy Vilebrequin AR", "Double Lèvre", 1, "FKM")
        add_std(g, "Volant Moteur", "Monomasse Équilibré", 1, "Acier C45")
        add_std(g, "Vis Volant Moteur", "M10 x 1.0 (Frein filet)", 6, "Acier 10.9")

        # 4. Combustion (B)
        g = "B. Système Combustion"
        add_std(g, "Injecteur Carburant", "Haute Pression (GDI)", N_cyl, "Inox / Solénoïde")
        add_std(g, "Joint Injecteur", "Torique Viton", N_cyl, "FKM")
        add_std(g, "Bride Fixation Injecteur", "Plaque Inox", N_cyl, "Inox 304")
        add_std(g, "Bougie Allumage", "Iridium / Platine", N_cyl, "Céramique / Inox")
        add_std(g, "Bobine Crayon", "COP (Coil on Plug)", N_cyl, "Cuivre / Epoxy")
        add_std(g, "Pompe Carburant HP", "Piston Radial", 1, "Inox")
        add_std(g, "Raccords Hoses Carburant", "AN-6", 4, "Alu Anodisé")
        add_std(g, "Durite Carburant", "Téflon tressé Inox", 1.5, "PTFE/SS")

        # 5. Cold Chamber & Gas (D)
        g = "D. Gaz Captif (Azote/Hélium)"
        gas_res = self.all_results.get('CaptiveGasAgent', {})
        add_std(g, "Réservoir Buffer", f"{gas_res.get('V_buffer_L',1):.1f}L (Accumulateur)", 1, "Acier Hydropneumatique")
        add_std(g, "Valve Schrader Remplissage", "Haute Pression", 1, "Laiton Nickelé")
        add_std(g, "Capteur Pression Absolu", "0-100 bar", N_cyl, "Piezo-résistif")
        add_std(g, "Joint Torique Buffer", "Étanchéité Statique", 1, "NBR 90 Shore")
        add_std(g, "Raccord Banjo Gaz", "1/4 BSP", 2*N_cyl, "Acier Bichromaté")
        add_std(g, "Tuyauterie Gaz Rigide", "Ø6mm", 0.5*N_cyl, "Acier Inox recuit")

        # 6. Dog Clutch (G)
        g = "G. Transmission / Accouplement"
        add_std(g, "Crabot Mobile (Moteur)", "Acier Cémenté 6 Dents", 1, "16MnCr5")
        add_std(g, "Crabot Fixe (Génératrice)", "Acier Cémenté 6 Dents", 1, "16MnCr5")
        add_std(g, "Fourchette de commande", "Bronze / Alu", 1, "CuAl10Ni")
        add_std(g, "Axe de Fourchette", "Rectifié", 1, "Acier Trempé")
        add_std(g, "Solénoïde d'Engagement", "Push/Pull 12V", 1, "Cuivre/Fer")
        add_std(g, "Ressort de Rappel Crabot", "Compression", 1, "Acier Ressort")
        add_std(g, "Circlips Axe", "Exterieur Ø12", 2, "Acier")

        # 7. Electrical (H)
        g = "H. Génératrice & Puissance"
        elec = self.all_results.get('ElectricalAgent', {})
        add_std(g, "Stator Bobiné", f"{elec.get('alternator_power_kW',0):.1f} kW / Refroidi Eau", 1, "Cuivre Class H / FerSi")
        add_std(g, "Rotor à Aimants", "IPM (Interior PM)", 1, "NdFeB N42UH")
        add_std(g, "Roulements Génératrice", "Ceramic Hybrid (Haut RPM)", 2, "Si3N4 / Acier")
        add_std(g, "Boîtier Génératrice", "Alu Extrudé Aileté", 1, "Alu 6063")
        add_std(g, "Presse-étoupe Câbles", "IP68 M25", 3, "Polyamide")
        add_std(g, "Câble Phase (Orange)", f"Blindé {elec.get('cable_section_mm2',10):.0f}mm²", 3, "Cuivre/Silicone")
        add_std(g, "Connecteur Puissance", "3 Pôles HV", 1, "Plastique UL94")

        # 8. Cooling (E)
        g = "E. Circuit Refroidissement"
        cool = self.all_results.get('CoolingAgent', {})
        add_std(g, "Pompe à Eau Électrique", f"PWM {cool.get('coolant_flow_L_min',0):.0f} L/min", 1, "PPS / Brushless")
        add_std(g, "Radiateur Échangeur", "Alu Brazé 300x300", 1, "Alu 3003")
        add_std(g, "Ventilateur", "Axial 12V", 1, "PA6-GF30")
        add_std(g, "Thermostat", "Ouverture 85°C", 1, "Laiton/Cire")
        add_std(g, "Durites Silicone", "Ø25mm", 4, "Silicone Renforcé")
        add_std(g, "Colliers de Serrage", "Worm Drive Inox", 8, "Inox A2")
        add_std(g, "Liquide de Refroidissement", "OAT -35°C", 3, "Glycol/Eau")

        # 9. Control & Safety (J, M) & Mounting
        g = "J/M. Contrôle & Structure"
        add_std(g, "ECU Principal", "PCB en Boîtier Alu IP67", 1, "FR4 / Alu")
        add_std(g, "Capteur PMH (Crank)", "Hall Effect", 1, "Plastique/Cuivre")
        add_std(g, "Capteur Température Eau", "NTC", 1, "Laiton")
        add_std(g, "Faisceau Basse Tension", "Gaine Tressée", 1, "Cuivre/PVC")
        add_std(g, "Silentblocs Moteur", "Caoutchouc Shore 60A", 4, "NR/SBR + Acier")
        add_std(g, "Vis Support Moteur", "M10 x 50", 4, "Acier 10.9")
        add_std(g, "Châssis Berceau", "Tube Carré 25x25 Soudé", 1, "Acier E24")

        self.results['BOM_List'] = bom
        return self.results
