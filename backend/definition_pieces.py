import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pieces.cylindre_chemise import Piece as Cylindre
from pieces.piston_puissance import Piece as Piston
from pieces.axe_piston import Piece as Axe
from pieces.bielle_corps import Piece as Bielle
from pieces.vilebrequin_corps import Piece as Vilebrequin
from pieces.maneton import Piece as Maneton
from pieces.vis_couvercle import Piece as Vis
from pieces.arbre_sortie_portee_sortie import Piece as ArbreSortie
from pieces.roulements_bagues_galet import Piece as Roulement

def main():
    print("=== DÉFINITION DES PIÈCES (INTERDÉPENDANCE FORTE) ===\n")

    # OBJECTIFS
    PUISSANCE_CIBLE_W = 150000.0
    REGIME_TR_MIN = 4500.0
    PRESSION_MAX_PA = 90e5
    NB_CYL = 4
    
    print(f"INPUTS: {PUISSANCE_CIBLE_W/1000}kW @ {REGIME_TR_MIN}rpm, Pmax={PRESSION_MAX_PA/1e5}bar")

    # INSTANCES
    cyl = Cylindre()
    pis = Piston()
    axe = Axe()
    bie = Bielle()
    vil = Vilebrequin()
    man = Maneton()
    vis = Vis()
    arb = ArbreSortie()
    rlt = Roulement()

    # 1. CYLINDRE (Point de départ)
    cyl.dimensionner(PUISSANCE_CIBLE_W, 12e5, REGIME_TR_MIN, NB_CYL, 1.0, PRESSION_MAX_PA)
    
    # 2. PISTON (Dépend du Cylindre)
    pis.dimensionner(cyl, REGIME_TR_MIN, PRESSION_MAX_PA)
    
    # 3. AXE (Dépend du Piston)
    axe.dimensionner(pis)
    
    # 4. BIELLE (Dépend Cylindre, Piston, Axe)
    bie.dimensionner(cyl, pis, axe, PRESSION_MAX_PA, REGIME_TR_MIN)
    
    # 5. VILEBREQUIN (Dépend Cylindre, Bielle)
    vil.dimensionner(cyl, bie)
    
    # 6. MANETON (Dépend Bielle (force), et Vilo (diamètre principal pour ratio))
    # Note: On n'a pas refactor maneton.py pour prendre l'objet Vilo, on passe les float pour l'instant
    # Amélioration possible: man.dimensionner(vil, bie, regime)
    man.dimensionner(bie.force_compression_max_n, vil.diametre_tourillon_m, REGIME_TR_MIN)
    
    # 7. VIS (Dépend Cylindre)
    vis.dimensionner(PRESSION_MAX_PA, cyl.alesage_m * 1.3)
    
    # 8. ARBRE SORTIE (Dépend Vilebrequin)
    arb.dimensionner(vil.couple_max_approx_nm, 5000.0) 
    
    # 9. ROULEMENT
    rlt.dimensionner(5000.0, 0, REGIME_TR_MIN)

    # AFFICHAGE
    liste = [cyl, pis, axe, bie, vil, man, vis, arb, rlt]
    for p in liste:
        print("-" * 40)
        print(p.decrire())
    print("-" * 40)

if __name__ == "__main__":
    main()
