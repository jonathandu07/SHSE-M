from backend.components.moteur_thermique.pieces.arbre_piston import ArbrePiston
from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin
from backend.components.moteur_thermique.pieces.bielle import CorpsBielle
from backend.components.moteur_thermique.pieces.coussinet_arbre_piston import CoussinetArbrePiston
from backend.components.moteur_thermique.pieces.cylindre import Cylindre
from backend.components.moteur_thermique.pieces.deplaceur import Deplaceur
from backend.components.moteur_thermique.pieces.joint_deplaceur import JointDeplaceur
from backend.components.moteur_thermique.pieces.joint_piston import JointPiston
from backend.components.moteur_thermique.pieces.piston import Piston
from backend.components.moteur_thermique.pieces.vilbrequin import Vilbrequin


def _names(rows):
    return {row.get("nom") for row in rows}


def _piece_b(rows):
    return {row.get("piece_b") for row in rows}


def _reports():
    return {
        "piston": Piston(
            alesage_nominal_m=0.08,
            course_m=0.06,
            rpm=3000.0,
            fit_hole="H7",
            fit_shaft="h6",
            pression_max_pa=2e6,
            materiau_piston_cle="alu_6061_t6",
            hauteur_totale_m=0.05,
            longueur_jupe_m=0.03,
            epaisseur_tete_m=0.005,
            nb_joints=2,
            section_joint_mm=2.0,
            squeeze=0.2,
        ).analyser(),
        "cylindre": Cylindre(
            0.08,
            0.06,
            0.1,
            1e5,
            2e6,
            materiau_cle="acier_42crmo4_qt",
            contrainte_admissible_pa=250e6,
            module_young_pa=210e9,
            coefficient_poisson=0.3,
            densite_kg_m3=7800.0,
        ).analyser(),
        "bielle": CorpsBielle(
            longueur_bielle_m=0.15,
            force_axiale_max_N=1000.0,
            materiau_cle="acier_42crmo4_qt",
            section_fut_m2=1e-4,
            inertie_min_fut_m4=1e-9,
            K_flambage=1.0,
            diametre_axe_piston_m=0.018,
            diametre_maneton_m=0.03,
        ).analyser(),
        "arbre_piston": ArbrePiston(
            longueur_totale_m=0.08,
            longueur_fut_central_m=0.04,
            diametre_exterieur_fut_m=0.02,
            force_axiale_N=1000.0,
            force_cisaillement_N=200.0,
            moment_flexion_Nm=10.0,
            couple_torsion_Nm=5.0,
            materiau_cle="acier_42crmo4_qt",
            limite_elastique_pa=600e6,
            module_young_pa=210e9,
            diametre_portee_coussinet_m=0.02,
        ).analyser(),
        "arbre_vilbrequin": ArbreVilbrequin(
            course_m=0.06,
            couple_max_Nm=100.0,
            moment_flexion_max_Nm=50.0,
            force_bielle_effective_N=3000.0,
            rpm=3000.0,
            diametre_journal_principal_m=0.035,
            largeur_portee_journal_m=0.02,
            diametre_maneton_m=0.03,
            largeur_portee_maneton_m=0.02,
            materiau_cle="acier_42crmo4_qt",
            limite_elastique_pa=600e6,
            module_young_pa=210e9,
        ).analyser(),
        "vilbrequin": Vilbrequin(
            course_m=0.06,
            rpm=3000.0,
            couple_max_Nm=100.0,
            moment_flexion_max_Nm=50.0,
            nb_manetons=1,
            nb_journaux_principaux=2,
            densite_kg_m3=7800.0,
            limite_elastique_pa=600e6,
            module_young_pa=210e9,
            poisson=0.3,
        ).analyser(),
        "joint_piston": JointPiston(
            diametre_interieur_cylindre_m=0.08,
            diametre_interieur_joint_m=0.074,
            diametre_section_joint_m=0.003,
            diametre_fond_gorge_m=0.077,
            profondeur_gorge_m=0.0012,
            largeur_gorge_m=0.0045,
            pression_contact_pa=2e6,
            coeff_frottement_mu=0.15,
            largeur_bande_contact_m=0.003,
        ).analyser(),
        "deplaceur": Deplaceur(
            diametre_exterieur_m=0.079,
            longueur_totale_m=0.1,
            course_disponible_m=0.02,
            jeu_radial_m=0.0005,
            delta_p_chaud_froid_pa=10_000.0,
            temperature_chaud_C=550.0,
            temperature_froid_C=90.0,
            type_deplaceur="tubulaire",
            diametre_interieur_m=0.055,
        ).analyser(),
        "joint_deplaceur": JointDeplaceur(
            diametre_deplaceur_m=0.079,
            longueur_deplaceur_m=0.1,
            alesage_cylindre_m=0.08,
            nb_joints=2,
            section_joint_mm=3.0,
            squeeze=0.2,
            facteur_largeur=1.5,
            pression_service_pa=150_000.0,
            module_elastomere_pa=7e6,
            coeff_frottement=0.15,
            largeur_bande_contact_m=0.003,
        ).analyser(),
        "coussinet_arbre_piston": CoussinetArbrePiston(
            diametre_portee_m=0.020,
            longueur_coussinet_m=0.020,
            epaisseur_coussinet_m=0.002,
            jeu_radial_m=20e-6,
            charge_radiale_N=2000.0,
            rpm=3000.0,
            coefficient_frottement=0.05,
            pression_admissible_pa=30e6,
            pv_admissible_W_m2=1.0e9,
        ).analyser(),
    }


def test_piston_expose_surfaces_interfaces_et_dossier():
    rapport = _reports()["piston"]

    assert {"jupe_piston", "tete_piston", "gorges_joint_piston"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"cylindre", "joint_piston", "arbre_piston"} <= _piece_b(rapport["interfaces_assemblage"])
    dossier = rapport["dossier_definition_piece"]
    assert {"jupe_piston", "gorges_joint_piston"} <= _names(dossier["surfaces_fonctionnelles"])
    assert dossier["solidworks_ready"] is False


def test_cylindre_expose_surfaces_limites_pression_et_rdm():
    rapport = _reports()["cylindre"]

    assert {"alesage_cylindre", "paroi_sous_pression", "portee_couvercle"} <= _names(rapport["surfaces_fonctionnelles"])
    assert "pression_max" in _names(rapport["limites_usage"])
    assert {"sigma_cerclage_mince", "sigma_von_mises_lame_au_ri"} <= _names(rapport["contraintes_rdm"])
    dossier = rapport["dossier_definition_piece"]
    assert "alesage_cylindre" in _names(dossier["surfaces_fonctionnelles"])
    assert "pression_max" in _names(dossier["limites_usage"])


def test_bielle_expose_interfaces_petite_et_grande_tete():
    rapport = _reports()["bielle"]

    assert {"alesage_petite_tete", "alesage_grande_tete", "fut_bielle"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"arbre_piston", "vilebrequin", "roulement_aiguille_arbre"} <= _piece_b(rapport["interfaces_assemblage"])
    assert "flambage_euler" in _names(rapport["contraintes_rdm"])
    assert "parallelisme_petite_grande_tete" in _names(rapport["tolerances"])


def test_arbre_piston_expose_controles_qualite_et_limites_mecaniques():
    rapport = _reports()["arbre_piston"]

    assert {"fut_central", "portee_coussinet", "tetons_extremites"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"diametre_fut", "rectitude", "coaxialite_tetons"} <= _names(rapport["controles_qualite"])
    assert {"force_axiale", "couple_torsion", "marge_von_mises"} <= _names(rapport["limites_usage"])
    assert "von_mises" in _names(rapport["contraintes_rdm"])


def test_arbre_vilbrequin_expose_interfaces_maneton_tourillon():
    rapport = _reports()["arbre_vilbrequin"]

    assert {"tourillons_principaux", "maneton", "rayons_raccordement"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"vilebrequin", "bielle", "roulement_aiguille_arbre_vilebrequin", "clavette_arbre"} <= _piece_b(rapport["interfaces_assemblage"])
    assert {"contraintes_maneton", "pression_contact_maneton"} <= _names(rapport["contraintes_rdm"])
    assert "diametre_maneton" in _names(rapport["controles_qualite"])


def test_vilbrequin_expose_surfaces_et_reste_distinct_arbre_vilbrequin():
    rapports = _reports()
    vilbrequin = rapports["vilbrequin"]
    arbre_vilbrequin = rapports["arbre_vilbrequin"]

    assert vilbrequin["piece"] == "vilbrequin"
    assert arbre_vilbrequin["piece"] in {"arbre_vilbrequin", "arbre_vilebrequin"}
    assert vilbrequin["piece"] != arbre_vilbrequin["piece"]
    assert {"maneton", "tourillons", "rayons_raccordement", "portees_roulement"} <= _names(vilbrequin["surfaces_fonctionnelles"])
    assert {"bielle", "roulement_aiguille_arbre_vilebrequin", "arbre_vilbrequin"} <= _piece_b(vilbrequin["interfaces_assemblage"])
    assert "arbre_vilbrequin" in _piece_b(vilbrequin["interfaces_assemblage"])
    assert {"vilbrequin", "vilebrequin"} & _piece_b(arbre_vilbrequin["interfaces_assemblage"])
    assert {"torsion_journal_principal", "von_mises_maneton", "fatigue"} <= _names(vilbrequin["contraintes_rdm"])
    assert "diametre_maneton" in _names(vilbrequin["controles_qualite"])
    assert "maneton" in _names(vilbrequin["dossier_definition_piece"]["surfaces_fonctionnelles"])


def test_joint_piston_expose_gorge_squeeze_et_dossier():
    rapport = _reports()["joint_piston"]

    assert {"tore", "surface_contact_cylindre", "surface_contact_gorge", "section_joint"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"piston", "cylindre", "gorge_piston"} <= _piece_b(rapport["interfaces_assemblage"])
    assert {"squeeze", "stretch", "pression_contact", "frottement"} <= _names(rapport["contraintes_rdm"])
    assert {"section_joint", "largeur_gorge", "profondeur_gorge", "jeu_radial"} <= _names(rapport["tolerances"])
    assert "tore" in _names(rapport["dossier_definition_piece"]["surfaces_fonctionnelles"])


def test_deplaceur_expose_zones_thermiques_et_limites_usage():
    rapport = _reports()["deplaceur"]

    assert {"corps_deplaceur", "surface_chaude", "surface_froide", "zone_etancheite", "portee_joint"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"cylindre", "joint_deplaceur", "chambre_chaude", "chambre_froide"} <= _piece_b(rapport["interfaces_assemblage"])
    assert {"flambage", "effort_pression", "perte_charge", "dilatation_thermique"} <= _names(rapport["contraintes_rdm"])
    assert {"pression_maximale", "temperature_maximale", "jeu_radial_minimal"} <= _names(rapport["limites_usage"])
    assert "surface_chaude" in _names(rapport["dossier_definition_piece"]["surfaces_fonctionnelles"])


def test_joint_deplaceur_expose_gorge_compression_et_missing_sans_invention():
    rapport = _reports()["joint_deplaceur"]

    assert {"section_joint", "surface_contact_cylindre", "surface_contact_deplaceur", "gorge"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"deplaceur", "cylindre", "gorge"} <= _piece_b(rapport["interfaces_assemblage"])
    assert {"squeeze", "pression_contact", "frottement", "fuite", "usure"} <= _names(rapport["contraintes_rdm"])
    assert {"section", "diametre", "profondeur_gorge", "largeur_gorge", "jeu_radial"} <= _names(rapport["tolerances"])
    missing = [row for row in rapport["tolerances"] if row.get("statut") == "missing"]
    assert missing
    assert all(row.get("valeur") is None for row in missing)


def test_coussinet_arbre_piston_expose_pv_pression_vitesse_et_dossier():
    rapport = _reports()["coussinet_arbre_piston"]

    assert {"diametre_interieur", "diametre_exterieur", "longueur", "surface_glissement", "faces_appui"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"arbre_piston", "bielle", "logement"} <= _piece_b(rapport["interfaces_assemblage"])
    assert {"pression_projetee", "vitesse_glissement", "PV", "frottement", "echauffement"} <= _names(rapport["contraintes_rdm"])
    assert {"pression_admissible", "PV_limite", "limite_tribologique"} <= _names(rapport["limites_usage"])
    assert "surface_glissement" in _names(rapport["dossier_definition_piece"]["surfaces_fonctionnelles"])


def test_tolerances_inconnues_restent_missing_sans_valeur_inventee():
    rapports = _reports()
    missing_rows = []
    for rapport in rapports.values():
        missing_rows.extend([row for row in rapport["tolerances"] if row.get("statut") == "missing"])

    assert missing_rows
    assert all(row.get("valeur") is None for row in missing_rows)
    assert all(row.get("raison") for row in missing_rows)


def test_controles_et_notes_modelisation_restent_des_aides_sans_cao_finale():
    for rapport in _reports().values():
        assert rapport["controles_qualite"]
        assert rapport["notes_modelisation"]
        dossier = rapport["dossier_definition_piece"]
        assert dossier["step_generation"] is False
        assert dossier["final_geometry"] is False
        assert dossier["solidworks_ready"] is False
        assert dossier["notes_modelisation"]
        assert any("aucun STEP" in str(note.get("texte", "")) or "aucun export STEP" in str(note.get("texte", "")) for note in dossier["notes_modelisation"])
