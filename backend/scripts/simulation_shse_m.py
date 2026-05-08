# backend/scripts/simulation_shse_m.py
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ajout du chemin projet
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

import matplotlib.pyplot as plt
from backend.ensemble.systeme_complet import SystemeComplet
from backend.components.moteur_electrique.moteur_electrique import MoteurElectrique
from backend.components.batterie.batterie import Batterie
from backend.components.alternateur.alternateur import Alternateur
from backend.components.moteur_thermique.moteur_thermique import MoteurThermique
from backend.components.boite_crabots.boite_crabots import BoiteCrabots
from backend.components.architechture.architecture import Architecture, ProfilUsageMoteur

# Visualisations
from frontend.pieces.sketches_2d.batterie_pack import tracer_croquis_batterie_2d
from frontend.pieces.sketches_2d.alternateur_complet import tracer_croquis_alternateur_2d
from frontend.pieces.sketches_2d.architecture_layout import tracer_croquis_architecture_2d

def executer_simulation():
    print("--- Démarrage de la simulation globale SHSE-M ---")
    
    # 1. Configuration des composants
    moteur_elec = MoteurElectrique(
        puissance_max_w=120000, 
        regime_max_rpm=6000, 
        couple_max_nm=300,
        rendement_moteur=0.94
    )
    
    # Batterie avec SOC initial faible pour forcer la recharge
    batterie = Batterie(
        tension_nominale_v=400,
        puissance_charge_kw=50.0 # Capacité de charge rapide
    )
    # Simulation d'un état : SOC=15%, Temp=45°C (Chaud, donc BMS va limiter)
    # Note: On injecte ces valeurs dans le BMS via les rapports de simulation
    
    alternateur = Alternateur(nombre_poles=12)
    
    moteur_thermique = MoteurThermique(
        nombre_cylindres=6, 
        alesage_m=0.086, 
        course_m=0.086, 
        rpm_nominal=3500,
        pme_nominale_pa=8e5
    )
    
    boite = BoiteCrabots()
    
    # Architecture forcée en V pour le test
    profil_arch = ProfilUsageMoteur(
        usage="voiture",
        longueur_dispo_m=0.8,
        largeur_dispo_m=0.8,
        architecture_forcee="V"
    )
    arch = Architecture(profil_usage=profil_arch)
    
    # 2. Assemblage du système
    systeme = SystemeComplet(
        moteur_electrique=moteur_elec,
        batterie=batterie,
        alternateur=alternateur,
        moteur_thermique=moteur_thermique,
        boite_crabots=boite,
        architecture=arch
    )
    
    # 3. Analyse du scénario : Croisière + Recharge rapide
    print("Analyse du point de fonctionnement (Recharge 40kW)...")
    rapport = systeme.analyser(
        masse_kg=1500,
        vitesse_ms=25.0, # 90 km/h
        acceleration_ms2=0.0,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.32,
        rayon_roue_m=0.3,
        rapport_reduction_global=8.0,
        rendement_transmission=0.96,
        scenario_bus_dc="charge",
        puissance_elec_alt_cible_w=45000.0, # 45kW demandés à l'alternateur
        vitesse_moteur_thermique_rpm=3000.0,
        rapport_vitesse_alt_sur_moteur=2.0, # L'alternateur tourne à 6000 RPM
        energie_utile_imposee_kwh=60.0
    )
    
    # 4. Génération des rapports visuels
    print("Génération des visualisations...")
    
    # On s'assure que le répertoire de sortie existe
    output_dir = _PROJECT_ROOT / "backend" / "outputs" / "simulations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Visualisation Batterie
    fig_batt = tracer_croquis_batterie_2d(batterie, titre="Simulation Batterie : Recharge Rapide")
    fig_batt.savefig(output_dir / "viz_batterie.png")
    print(f"Graphique batterie sauvegardé : {output_dir / 'viz_batterie.png'}")
    
    # Visualisation Alternateur
    fig_alt = tracer_croquis_alternateur_2d(alternateur, titre="Simulation Alternateur : 45kW @ 6000RPM")
    fig_alt.savefig(output_dir / "viz_alternateur.png")
    print(f"Graphique alternateur sauvegardé : {output_dir / 'viz_alternateur.png'}")
    
    # Visualisation Architecture
    fig_arch = tracer_croquis_architecture_2d(arch, titre="Configuration Architecture Moteur")
    fig_arch.savefig(output_dir / "viz_architecture.png")
    print(f"Graphique architecture sauvegardé : {output_dir / 'viz_architecture.png'}")
    
    print("\n--- Simulation terminée avec succès ---")
    print(f"Résultats disponibles dans : {output_dir}")

if __name__ == "__main__":
    executer_simulation()
