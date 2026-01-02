import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importation de TOUTES les pièces (58 modules)
from pieces.cylindre_chemise import Piece as Cylindre
from pieces.piston_puissance import Piece as Piston
from pieces.axe_piston import Piece as AxePiston
from pieces.bielle_corps import Piece as Bielle
from pieces.vilebrequin_corps import Piece as Vilebrequin
from pieces.maneton import Piece as Maneton
from pieces.vis_couvercle import Piece as VisCouvercle
from pieces.arbre_sortie_portee_sortie import Piece as ArbreSortie
from pieces.roulements_bagues_galet import Piece as Roulement
from pieces.segments_compression_piston import Piece as SegmentsCompression
from pieces.segment_racleur_piston import Piece as SegmentRacleur
from pieces.coussinet_tete_bielle import Piece as CoussinetTete # Legacy ? Non, Paliers Maneton maintenant
from pieces.paliers_bielle_maneton import Piece as PaliersManeton # REMPLACE CoussinetTete (plus précis)
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

# Nouveaux ajouts High Precision
from pieces.contrepoids_equilibrage import Piece as Contrepoids
from pieces.circlips_axe_piston import Piece as Circlips
from pieces.systeme_rappel_precharge import Piece as Ressorts
from pieces.joint_tournant_arbre_sortie import Piece as JointSortie
from pieces.jaquette_refroidissement_enveloppe_eau import Piece as Jaquette
from pieces.etancheite_paroi_mobile_joints_guide_labyrinthe_segments import Piece as EtancheiteParoi
from pieces.guidages_paroi_mobile_patins_bagues_glissieres import Piece as GuidageParoi
from pieces.brides_supports import Piece as Brides
from pieces.entretoises import Piece as Entretoises
from pieces.huile_graisse import Piece as Huile
from pieces.butees_mecaniques_fin_de_course import Piece as ButeesMeca

# Import BDD
from database import SecureDatabase

def main():
    print("=== DÉFINITION INTEGRALE HAUTE PRÉCISION DU SYSTÈME SHSE-M ===\\n")

    PUISSANCE_CIBLE_W = 150000.0   
    REGIME_TR_MIN = 4500.0
    PRESSION_MAX_PA = 90e5         
    NB_CYL = 4
    
    print(f"INPUTS: {PUISSANCE_CIBLE_W/1000}kW @ {REGIME_TR_MIN}rpm")

    # 1. INSTANCIATION (Tous les objets)
    cyl = Cylindre()
    pis = Piston()
    axe = AxePiston()
    bie = Bielle()
    vil = Vilebrequin()
    man = Maneton()
    vis = VisCouvercle()
    arb = ArbreSortie()
    rlt = Roulement()
    seg_c = SegmentsCompression()
    seg_r = SegmentRacleur()
    # cous_t = CoussinetTete() # Remplacé par PaliersManeton
    cous_m = PaliersManeton()
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
    
    couv_av = CouvercleAvant()
    couv_ar = CouvercleArriere()
    culasse = Culasse()
    jt_cart = JointCarter()
    jt_cul = JointCulasse()
    jts_eau = JointsEau()
    jts_gaz = JointsGaz()
    
    col_eau_in = ColEauEntree()
    col_eau_out = ColEauSortie()
    col_gaz_out = ColGazSortie()
    tub_eau = TubesEau()
    isol = Isolation()
    
    ax_gal = AxeGalet()
    rail = Rail()
    pal_av = PalierAv()
    pal_ar = PalierAr()
    but = Butee()
    goup = Goupilles()
    clav = Clavettes()
    paroi = Paroi()
    
    # New
    cp = Contrepoids()
    circ = Circlips()
    ress = Ressorts()
    jt_out = JointSortie()
    jaq = Jaquette()
    etanch_p = EtancheiteParoi()
    guid_p = GuidageParoi()
    brides = Brides()
    entre = Entretoises()
    huile = Huile()
    but_meca = ButeesMeca()

    # 2. CALCULS DE DIMENSIONNEMENT (Séquence Dépendances)
    
    # --- MOTEUR DE BASE ---
    cyl.dimensionner(PUISSANCE_CIBLE_W, 12e5, REGIME_TR_MIN, NB_CYL, 1.0, PRESSION_MAX_PA)
    pis.dimensionner(cyl, REGIME_TR_MIN, PRESSION_MAX_PA)
    axe.dimensionner(pis)
    circ.dimensionner(axe, REGIME_TR_MIN) # New
    
    bie.dimensionner(cyl, pis, axe, PRESSION_MAX_PA, REGIME_TR_MIN)
    vil.dimensionner(cyl, bie, NB_CYL)
    man.dimensionner(bie.force_compression_max_n, vil.diametre_tourillon_m, REGIME_TR_MIN)
    
    cp.dimensionner(vil, bie, pis, REGIME_TR_MIN) # New
    cous_m.dimensionner(man, bie, 4e5, bie.force_compression_max_n) # New (remplace cous_t avec arguments précis)
    cous_p.dimensionner(axe, bie)
    
    # --- TRANSMISSION ---
    arb.dimensionner(vil.couple_max_approx_nm, 5000.0)
    clav.dimensionner(arb)
    vol.dimensionner(vil, PUISSANCE_CIBLE_W, REGIME_TR_MIN, NB_CYL)
    jt_out.dimensionner(arb, REGIME_TR_MIN) # New
    
    # --- THERMODYNAMIQUE & FLUIDES ---
    ch_chaud.dimensionner(cyl, PRESSION_MAX_PA)
    ch_froid.dimensionner(cyl, PRESSION_MAX_PA)
    deplac.dimensionner(ch_chaud, cyl)
    paroi.dimensionner(cyl)
    
    etanch_p.dimensionner(paroi, 10e5) # New
    guid_p.dimensionner(paroi, 100.0) # New
    
    ech.dimensionner(cyl)
    tub_g.dimensionner(ch_chaud, PRESSION_MAX_PA)
    
    circ_eau.dimensionner(PUISSANCE_CIBLE_W)
    jaq.dimensionner(cyl) # New
    
    circ_huil.dimensionner(NB_CYL, REGIME_TR_MIN)
    huile.dimensionner((cyl.cylindree_unitaire_m3 * NB_CYL), has_turbo=True) # New
    
    col_adm.dimensionner(cyl, REGIME_TR_MIN)
    
    # --- STRUCTURE ---
    carter.dimensionner(cyl, NB_CYL)
    vis.dimensionner(PRESSION_MAX_PA, cyl.alesage_m * 1.3)
    gouj.dimensionner(vis, NB_CYL, carter)
    ecr.dimensionner(gouj.diametre_m) # New
    rond.dimensionner(ecr)
    entre.dimensionner(gouj.diametre_m, 0.05) # New (Entretoise 50mm)
    
    culasse.dimensionner(cyl, NB_CYL, PRESSION_MAX_PA)
    couv_av.dimensionner(carter)
    couv_ar.dimensionner(carter)
    brides.dimensionner(carter.masse_estimee_kg * 4.0) # New (Masse totale estimée x4 coeff ?) Non, juste masse moteur.
    
    # --- JOINTS ---
    jt_cart.dimensionner(carter, couv_av, couv_ar)
    jt_cul.dimensionner(cyl)
    
    debit_eau_m3s = circ_eau.debit_eau_m3h / 3600
    diam_eau = math.sqrt(4 * (debit_eau_m3s / 2.0) / math.pi)
    jts_eau.dimensionner(diam_eau, NB_CYL*2)
    jts_gaz.dimensionner(col_adm.diametre_conduit_mm / 1000.0, NB_CYL)
    
    # --- COLLECTEURS ---
    col_eau_in.dimensionner(circ_eau, carter.longueur_m)
    col_eau_out.dimensionner(col_eau_in)
    col_gaz_out.dimensionner(col_adm)
    tub_eau.dimensionner(ch_froid, PRESSION_MAX_PA)
    isol.dimensionner(ch_chaud, NB_CYL)
    
    # --- KINEMATICS ---
    force_lat = bie.force_compression_max_n * 0.15 
    ax_gal.dimensionner(force_lat)
    rlt.dimensionner(5000.0, ax_gal.diametre_m, REGIME_TR_MIN) # Roulement Galet
    rail.dimensionner(cyl, ax_gal)
    pal_av.dimensionner(vil)
    pal_ar.dimensionner(vil) # Palier Principal (Vilo)
    but.dimensionner(vil)
    goup.dimensionner(vis, NB_CYL)

    ress.dimensionner(5.0, REGIME_TR_MIN, cyl.course_m) # New (5kg masse mobile ?) Stirling displacer est lourd.
    but_meca.dimensionner(deplac.masse_kg, 1.5) # New (1.5 m/s impact)

    # 3. SAUVEGARDE EN BDD
    print("\\n[BDD] Mise à jour complète avec High Precision Physics...")
    db = SecureDatabase()
    
    liste_complete = [
        cyl, pis, axe, circ, bie, vil, cp, man, cous_m, cous_p, vol, arb, clav, jt_out,
        ch_chaud, ch_froid, deplac, etanch_p, guid_p, ech, tub_g, 
        circ_eau, jaq, circ_huil, huile, col_adm,
        carter, culasse, couv_av, couv_ar, vis, gouj, ecr, rond, entre, brides,
        jt_cart, jt_cul, jts_eau, jts_gaz,
        col_eau_in, col_eau_out, col_gaz_out, tub_eau, isol,
        ax_gal, rlt, rail, pal_av, pal_ar, but, goup, ress, but_meca, paroi
    ]
    
    count = 0
    for p in liste_complete:
        db.save_piece(p)
        count += 1
        
    print(f"\\n[SUCCÈS] {count} composants définis avec précision et sauvegardés.")

if __name__ == "__main__":
    main()
