import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importation de TOUTES les pièces
from pieces.cylindre_chemise import Piece as Cylindre
from pieces.piston_puissance import Piece as Piston
from pieces.axe_piston import Piece as Axe
from pieces.bielle_corps import Piece as Bielle
from pieces.vilebrequin_corps import Piece as Vilebrequin
from pieces.maneton import Piece as Maneton
from pieces.vis_couvercle import Piece as Vis
from pieces.arbre_sortie_portee_sortie import Piece as ArbreSortie
from pieces.roulements_bagues_galet import Piece as Roulement
from pieces.segments_compression_piston import Piece as SegmentsComp
from pieces.segment_racleur_piston import Piece as SegmentRacleur
from pieces.coussinet_tete_bielle import Piece as CoussinetTete
from pieces.coussinet_pied_bielle import Piece as CoussinetPied
from pieces.volant_inertie import Piece as Volant
from pieces.chambre_chaude_corps_combustion import Piece as ChambreChaud
from pieces.chambre_froide_corps_refroidissement import Piece as ChambreFroid
from pieces.deplaceur_galet_rouleau_translateur import Piece as Deplaceur
from pieces.echangeur_thermique_corps import Piece as Echangeur
from pieces.tubes_helicoidaux_serpentins_cote_gaz import Piece as TubesGaz
from pieces.circuit_refroidissement import Piece as CircuitEau
from pieces.circuit_lubrification import Piece as CircuitHuile
from pieces.collecteur_gaz_entree import Piece as CollecteurAdm
from pieces.carter_bati import Piece as Carter
from pieces.goujons import Piece as Goujons
from pieces.ecrous import Piece as Ecrous
from pieces.rondelles import Piece as Rondelles

# Import BDD
from database import SecureDatabase

def main():
    print("=== DÉFINITION INTEGRALE DES PIÈCES DU SYSTÈME SHSE-M ===\n")

    # OBJECTIFS
    PUISSANCE_CIBLE_W = 150000.0   
    REGIME_TR_MIN = 4500.0
    PRESSION_MAX_PA = 90e5         
    NB_CYL = 4
    
    print(f"INPUTS: {PUISSANCE_CIBLE_W/1000}kW @ {REGIME_TR_MIN}rpm")

    # 1. INSTANCIATION
    cyl = Cylindre()
    pis = Piston()
    axe = Axe()
    bie = Bielle()
    vil = Vilebrequin()
    man = Maneton()
    vis = Vis()
    arb = ArbreSortie()
    rlt = Roulement()
    seg_c = SegmentsComp()
    seg_r = SegmentRacleur()
    cous_t = CoussinetTete()
    cous_p = CoussinetPied()
    vol = Volant()
    ch_chaud = ChambreChaud()
    ch_froid = ChambreFroid()
    deplac = Deplaceur()
    ech = Echangeur()
    tub_g = TubesGaz()
    circ_eau = CircuitEau()
    circ_huil = CircuitHuile()
    col_adm = CollecteurAdm()
    carter = Carter()
    gouj = Goujons()
    ecr = Ecrous()
    rond = Rondelles()

    # 2. CALCULS DE DIMENSIONNEMENT (Séquence optimisée)
    
    # Core Engine
    cyl.dimensionner(PUISSANCE_CIBLE_W, 12e5, REGIME_TR_MIN, NB_CYL, 1.0, PRESSION_MAX_PA)
    pis.dimensionner(cyl, REGIME_TR_MIN, PRESSION_MAX_PA)
    axe.dimensionner(pis)
    bie.dimensionner(cyl, pis, axe, PRESSION_MAX_PA, REGIME_TR_MIN)
    vil.dimensionner(cyl, bie)
    man.dimensionner(bie.force_compression_max_n, vil.diametre_tourillon_m, REGIME_TR_MIN)
    vis.dimensionner(PRESSION_MAX_PA, cyl.alesage_m * 1.3)
    
    # Transmission
    arb.dimensionner(vil.couple_max_approx_nm, 5000.0) 
    rlt.dimensionner(5000.0, 0, REGIME_TR_MIN)
    vol.dimensionner(vil, PUISSANCE_CIBLE_W, REGIME_TR_MIN, NB_CYL)
    
    # Tribology / Detail
    seg_c.dimensionner(pis, PRESSION_MAX_PA, REGIME_TR_MIN)
    seg_r.dimensionner(pis)
    cous_t.dimensionner(man, REGIME_TR_MIN)
    cous_p.dimensionner(axe, bie)
    
    # Cycle / Thermal
    ch_chaud.dimensionner(cyl, PRESSION_MAX_PA)
    ch_froid.dimensionner(cyl, PRESSION_MAX_PA)
    deplac.dimensionner(ch_chaud, cyl)
    ech.dimensionner(cyl)
    tub_g.dimensionner(ch_chaud, PRESSION_MAX_PA)
    circ_eau.dimensionner(PUISSANCE_CIBLE_W)
    circ_huil.dimensionner(NB_CYL, REGIME_TR_MIN)
    col_adm.dimensionner(cyl, REGIME_TR_MIN)
    
    # Structure
    carter.dimensionner(cyl, NB_CYL)
    gouj.dimensionner(vis, NB_CYL, carter)
    ecr.dimensionner(gouj)
    rond.dimensionner(ecr)

    # 3. SAUVEGARDE EN BDD
    print("\n[BDD] Initialisation de la base de données sécurisée...")
    db = SecureDatabase()
    
    liste = [
        cyl, pis, axe, bie, vil, man, vis, arb, rlt, seg_c, seg_r, cous_t, cous_p, vol,
        ch_chaud, ch_froid, deplac, ech, tub_g, circ_eau, circ_huil, col_adm, carter,
        gouj, ecr, rond
    ]
    
    for p in liste:
        db.save_piece(p)
        
    print(f"\n[SUCCÈS] {len(liste)} Fiches techniques sauvegardées et chiffrées dans 'shse_technical_data.db'.")

if __name__ == "__main__":
    main()
