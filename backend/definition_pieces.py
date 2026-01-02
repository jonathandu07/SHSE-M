import sys
import os
import math

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
from pieces.couvercle_avant import Piece as CouvercleAvant
from pieces.couvercle_arriere import Piece as CouvercleArriere
from pieces.culasse_couvercle_principal import Piece as Culasse
from pieces.joint_statique_plan_joint_couvercle_carter import Piece as JointCarter
from pieces.joint_statique_plan_joint_culasse_chambre import Piece as JointCulasse
from pieces.joints_statiques_collecteurs_eau import Piece as JointsEau
from pieces.joints_statiques_collecteurs_gaz import Piece as JointsGaz

from pieces.collecteur_eau_entree import Piece as ColEauEntree
from pieces.collecteur_eau_sortie import Piece as ColEauSortie
from pieces.collecteur_gaz_sortie import Piece as ColGazSortie
from pieces.tubes_helicoidaux_serpentins_cote_eau import Piece as TubesEau
from pieces.isolation_thermique_externe import Piece as Isolation

from pieces.axes_galet import Piece as AxeGalet
from pieces.rail_glissiere_translation_galet import Piece as Rail
from pieces.paliers_principaux_avant import Piece as PalierAv
from pieces.paliers_principaux_arriere import Piece as PalierAr
from pieces.butee_axiale import Piece as Butee
from pieces.goupilles_centrage import Piece as Goupilles
from pieces.clavettes_cannelures import Piece as Clavettes
from pieces.paroi_mobile_cloison_translateuse import Piece as Paroi

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
    
    # Batch 1: Structure & Seals
    couv_av = CouvercleAvant()
    couv_ar = CouvercleArriere()
    culasse = Culasse()
    jt_cart = JointCarter()
    jt_cul = JointCulasse()
    jts_eau = JointsEau()
    jts_gaz = JointsGaz()
    
    # Batch 2: Fluids
    col_eau_in = ColEauEntree()
    col_eau_out = ColEauSortie()
    col_gaz_out = ColGazSortie()
    tub_eau = TubesEau()
    isol = Isolation()
    
    # Batch 3: Kinematics
    ax_gal = AxeGalet()
    rail = Rail()
    pal_av = PalierAv()
    pal_ar = PalierAr()
    but = Butee()
    goup = Goupilles()
    clav = Clavettes()
    paroi = Paroi()

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
    
    # Structure Batch 1
    culasse.dimensionner(cyl, NB_CYL, PRESSION_MAX_PA)
    couv_av.dimensionner(carter)
    couv_ar.dimensionner(carter)
    
    # Seals Batch 1
    jt_cart.dimensionner(carter, couv_av, couv_ar)
    jt_cul.dimensionner(cyl)
    
    # Info pour joints fluides
    # Eau: Vitesse ~ 2 m/s. Q = v*S => S = Q/v. D = sqrt(4S/pi)
    debit_eau_m3s = circ_eau.debit_eau_m3h / 3600
    diam_eau = math.sqrt(4 * (debit_eau_m3s / 2.0) / math.pi)
    jts_eau.dimensionner(diam_eau, NB_CYL*2) # Entrée/Sortie par cyl
    
    jts_gaz.dimensionner(col_adm.diametre_conduit_mm / 1000.0, NB_CYL)
    
    # Fluids Batch 2
    col_eau_in.dimensionner(circ_eau, carter.longueur_m)
    col_eau_out.dimensionner(col_eau_in)
    col_gaz_out.dimensionner(col_adm)
    tub_eau.dimensionner(ch_froid, PRESSION_MAX_PA)
    isol.dimensionner(ch_chaud, NB_CYL)
    
    # Kinematics Batch 3
    # Force laterale approx = 10% force compression (tan beta)
    force_lat = bie.force_compression_max_n * 0.15 
    ax_gal.dimensionner(force_lat)
    rail.dimensionner(cyl, ax_gal)
    pal_av.dimensionner(vil)
    pal_ar.dimensionner(vil)
    but.dimensionner(vil)
    goup.dimensionner(vis, NB_CYL) # Nb Carters ? disons NB_CYL comme proxy ou 1 bloc
    clav.dimensionner(arb)
    paroi.dimensionner(cyl)

    # 3. SAUVEGARDE EN BDD
    print("\n[BDD] Initialisation de la base de données sécurisée...")
    db = SecureDatabase()
    
    liste = [
        cyl, pis, axe, bie, vil, man, vis, arb, rlt, seg_c, seg_r, cous_t, cous_p, vol,
        ch_chaud, ch_froid, deplac, ech, tub_g, circ_eau, circ_huil, col_adm, carter,
        gouj, ecr, rond,
        # Batch 1
        couv_av, couv_ar, culasse, jt_cart, jt_cul, jts_eau, jts_gaz,
        # Batch 2
        col_eau_in, col_eau_out, col_gaz_out, tub_eau, isol,
        # Batch 3
        ax_gal, rail, pal_av, pal_ar, but, goup, clav, paroi
    ]
    
    for p in liste:
        db.save_piece(p)
        
    print(f"\n[SUCCÈS] {len(liste)} Fiches techniques sauvegardées et chiffrées dans 'shse_technical_data.db'.")

if __name__ == "__main__":
    main()
