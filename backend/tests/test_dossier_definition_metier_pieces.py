from backend.components.moteur_thermique.pieces.arbre_piston import ArbrePiston
from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin
from backend.components.moteur_thermique.pieces.bielle import CorpsBielle
from backend.components.moteur_thermique.pieces.cylindre import Cylindre
from backend.components.moteur_thermique.pieces.piston import Piston


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
    }


def test_piston_expose_surfaces_interfaces_et_dossier():
    rapport = _reports()["piston"]

    assert {"jupe_piston", "tete_piston", "gorges_joint_piston"} <= _names(rapport["surfaces_fonctionnelles"])
    assert {"cylindre", "joint_piston", "arbre_piston"} <= _piece_b(rapport["interfaces_assemblage"])
    dossier = rapport["dossier_definition_solidworks"]
    assert {"jupe_piston", "gorges_joint_piston"} <= _names(dossier["surfaces_fonctionnelles"])
    assert dossier["solidworks_ready"] is False


def test_cylindre_expose_surfaces_limites_pression_et_rdm():
    rapport = _reports()["cylindre"]

    assert {"alesage_cylindre", "paroi_sous_pression", "portee_couvercle"} <= _names(rapport["surfaces_fonctionnelles"])
    assert "pression_max" in _names(rapport["limites_usage"])
    assert {"sigma_cerclage_mince", "sigma_von_mises_lame_au_ri"} <= _names(rapport["contraintes_rdm"])
    dossier = rapport["dossier_definition_solidworks"]
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
        dossier = rapport["dossier_definition_solidworks"]
        assert dossier["step_generation"] is False
        assert dossier["final_geometry"] is False
        assert dossier["solidworks_ready"] is False
        assert dossier["notes_modelisation"]
        assert any("aucun export STEP" in str(note.get("texte", "")) for note in dossier["notes_modelisation"])

