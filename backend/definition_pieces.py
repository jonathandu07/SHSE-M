import sys
import os

# Ajout du chemin racine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pieces.cylindre_chemise import Piece as Cylindre
from pieces.piston_puissance import Piece as Piston
from pieces.axe_piston import Piece as Axe

def main():
    print("=== DÉFINITION DES PIÈCES DU SYSTÈME SHSE-M ===\n")

    # 1. PARAMÈTRES GLOBAUX DU SYSTÈME (Objectifs)
    PUISSANCE_CIBLE_W = 200000.0  # 200 kW
    REGIME_CIBLE_TR_MIN = 3000.0
    PME_CIBLE_PA = 15e5           # 15 Bar de Pression Moyenne Effective
    PRESSION_MAX_PA = 80e5        # 80 Bar Pression Max Combustion
    NB_CYLINDRES = 4
    FATIO_S_B = 1.1               # Moteur longue course
    
    print(f"Objectifs:\n  Puissance: {PUISSANCE_CIBLE_W/1000:.0f} kW\n  Régime: {REGIME_CIBLE_TR_MIN} tr/min\n  PME: {PME_CIBLE_PA/1e5:.0f} bar\n")

    # 2. INSTANCIATION DES PIÈCES
    cylindre = Cylindre()
    piston = Piston()
    axe = Axe()

    # 3. CALCUL / DIMENSIONNEMENT EN CHAÎNE
    
    # A. Cylindre (Maître)
    cylindre.dimensionner(
        puissance_cible_w=PUISSANCE_CIBLE_W,
        pme_pa=PME_CIBLE_PA,
        regime_tr_min=REGIME_CIBLE_TR_MIN,
        nb_cylindres=NB_CYLINDRES,
        ratio_course_alesage=FATIO_S_B,
        pression_max_pa=PRESSION_MAX_PA
    )
    
    # B. Piston (Dépend du cylindre)
    piston.dimensionner(
        alesage_m=cylindre.alesage_m,
        course_m=cylindre.course_m,
        regime_tr_min=REGIME_CIBLE_TR_MIN,
        pression_max_pa=PRESSION_MAX_PA
    )
    
    # C. Axe Piston (Dépend du piston et de la force gaz)
    axe.dimensionner(
        force_max_n=piston.force_max_gaz_n,
        diametre_piston_m=piston.diametre_m
    )

    # 4. RAPPORT FINAL
    pieces = [cylindre, piston, axe]
    
    for p in pieces:
        print("------------------------------------------------")
        print(p.decrire())
    print("------------------------------------------------")
    print("\nCalcul terminé. Ces dimensions sont mathématiquement cohérentes avec les formules modules.")

if __name__ == "__main__":
    main()
