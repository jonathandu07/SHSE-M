import pytest

from backend.components.moteur_thermique.pieces.arbre import ArbreMoteur
from backend.components.moteur_thermique.pieces.arbre_piston import ArbrePiston
from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin
from backend.components.moteur_thermique.pieces.bielle import CorpsBielle
from backend.components.moteur_thermique.pieces.clavette_arbre import ClavetteArbre
from backend.components.moteur_thermique.pieces.coussinet_arbre_piston import CoussinetArbrePiston
from backend.components.moteur_thermique.pieces.couvercle_cylindre import CouvercleCylindre
from backend.components.moteur_thermique.pieces.cylindre import Cylindre
from backend.components.moteur_thermique.pieces.deplaceur import Deplaceur
from backend.components.moteur_thermique.pieces.joint_deplaceur import JointDeplaceur
from backend.components.moteur_thermique.pieces.joint_piston import JointPiston
from backend.components.moteur_thermique.pieces.piston import Piston
from backend.components.moteur_thermique.pieces.roulement_aiguille_arbre import RoulementAiguilleArbre
from backend.components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin import (
    RoulementAiguilleArbreVilebrequin,
)
from backend.components.moteur_thermique.pieces.vilbrequin import Vilbrequin
from backend.components.moteur_thermique.pieces.vis_couvercle_cylindre import VisCouvercleCylindre
from backend.modules.systeme.dossier_definition import ajouter_dossier_definition_solidworks


PRIORITY_FACTORIES = [
    ("piston", lambda: Piston(alesage_nominal_m=0.08, course_m=0.06).analyser()),
    ("cylindre", lambda: Cylindre(0.08, 0.06, 0.1, 1e5, 2e5).analyser()),
    ("bielle", lambda: CorpsBielle(longueur_bielle_m=0.15, force_axiale_max_N=1000.0).analyser()),
    ("arbre_piston", lambda: ArbrePiston(longueur_totale_m=0.08, diametre_exterieur_fut_m=0.02).analyser()),
    ("arbre_vilbrequin", lambda: ArbreVilbrequin(course_m=0.06, couple_max_Nm=100.0).analyser()),
    ("vilbrequin", lambda: Vilbrequin(course_m=0.06, couple_max_Nm=100.0).analyser()),
    (
        "joint_piston",
        lambda: JointPiston(
            diametre_interieur_joint_m=0.078,
            diametre_section_joint_m=0.003,
            diametre_interieur_cylindre_m=0.08,
        ).analyser(),
    ),
    ("deplaceur", lambda: Deplaceur(diametre_exterieur_m=0.07, longueur_totale_m=0.1).analyser()),
    (
        "joint_deplaceur",
        lambda: JointDeplaceur(
            diametre_deplaceur_m=0.07,
            longueur_deplaceur_m=0.1,
            alesage_cylindre_m=0.08,
            section_joint_mm=2.0,
        ).analyser(),
    ),
    (
        "coussinet_arbre_piston",
        lambda: CoussinetArbrePiston(diametre_portee_m=0.02, longueur_coussinet_m=0.02).analyser(),
    ),
    (
        "roulement_aiguille_arbre",
        lambda: RoulementAiguilleArbre(
            type_portee="journal",
            rpm=1000.0,
            force_radiale_equivalente_N=1000.0,
        ).analyser(),
    ),
    (
        "roulement_aiguille_arbre_vilebrequin",
        lambda: RoulementAiguilleArbreVilebrequin(
            diametre_maneton_m=0.03,
            largeur_portee_grande_tete_m=0.02,
            force_bielle_max_N=1000.0,
        ).analyser(),
    ),
    (
        "couvercle_cylindre",
        lambda: CouvercleCylindre(
            diametre_ouverture_m=0.08,
            rayon_externe_m=0.06,
            pression_max_pa=2e5,
        ).analyser(),
    ),
    (
        "vis_couvercle_cylindre",
        lambda: VisCouvercleCylindre(
            pression_max_pa=2e5,
            diametre_ouverture_m=0.08,
            rayon_externe_couvercle_m=0.06,
            largeur_bride_cylindre_m=0.02,
        ).analyser(),
    ),
    (
        "clavette_arbre",
        lambda: ClavetteArbre(
            couple_transmis_Nm=100.0,
            diametre_arbre_m=0.03,
            largeur_anneau_interieur_m=0.02,
        ).analyser(),
    ),
    ("arbre", lambda: ArbreMoteur(couple_max_Nm=100.0, diametre_arbre_m=0.03).analyser()),
]


def _complete_piston_report():
    return {
        "piece": "piston",
        "geometrie": {
            "diametre_piston_m": 0.08,
            "hauteur_piston_m": 0.05,
            "alesage_m": 0.08,
            "jeu_radial_m": 0.0001,
        },
        "interfaces": [
            {
                "piece_a": "piston",
                "piece_b": "cylindre",
                "fonction": "cylindre",
                "jeu_ou_serrage": "jeu radial",
                "tolerance": "backend_fourni",
                "statut": "ok",
            },
            {
                "piece_a": "piston",
                "piece_b": "arbre_piston",
                "fonction": "arbre_piston",
                "jeu_ou_serrage": "pivot",
                "tolerance": "backend_fourni",
                "statut": "ok",
            },
            {
                "piece_a": "piston",
                "piece_b": "joint_piston",
                "fonction": "joint_piston",
                "jeu_ou_serrage": "gorge",
                "tolerance": "backend_fourni",
                "statut": "ok",
            },
        ],
        "materiau": {"materiau_cle": "alu_6061_t6", "limite_elastique_pa": 250e6},
        "contraintes": {"von_mises": {"valeur_pa": 80e6, "limite_pa": 120e6}},
        "limites_usage": {"pression_max_pa": 10e6},
        "cao": {"solidworks_ready": True, "step_export": True, "final_geometry": True},
    }


@pytest.mark.parametrize("piece_name, factory", PRIORITY_FACTORIES)
def test_pieces_prioritaires_exposent_dossier_definition_solidworks(piece_name, factory):
    rapport = factory()

    dossier = rapport["dossier_definition_solidworks"]

    assert dossier["solidworks_ready"] is False
    assert dossier["step_generation"] is False
    assert dossier["schema_only"] is True
    assert dossier["final_geometry"] is False
    assert dossier["statut"] in {
        "blocked",
        "partial",
        "ready_for_manual_modeling",
        "ready_for_assembly_check",
        "validated_by_calculation",
        "not_validated",
    }
    assert dossier["identification"]["famille"] == "moteur_thermique"
    assert dossier["identification"]["nom_canonique"]
    assert rapport["solidworks_ready"] is False
    assert rapport["step_export"] is False


def test_dossier_ne_promet_jamais_step_ou_geometrie_finale():
    rapport = ajouter_dossier_definition_solidworks(_complete_piston_report(), "piston")

    dossier = rapport["dossier_definition_solidworks"]

    assert dossier["statut"] == "ready_for_manual_modeling"
    assert dossier["solidworks_ready"] is False
    assert dossier["step_generation"] is False
    assert dossier["final_geometry"] is False
    assert rapport["solidworks_ready"] is False
    assert rapport["step_export"] is False
    assert rapport["cao"]["solidworks_ready"] is False
    assert rapport["cao"]["step_export"] is False
    assert rapport["cao"]["final_geometry"] is False


def test_piece_sans_materiau_ne_devient_pas_prete_modelisation():
    rapport = _complete_piston_report()
    rapport.pop("materiau")

    dossier = ajouter_dossier_definition_solidworks(rapport, "piston")["dossier_definition_solidworks"]

    assert dossier["statut"] != "ready_for_manual_modeling"
    assert dossier["statut"] != "validated_by_calculation"
    assert dossier["materiaux"] == []


def test_piece_sans_rdm_reste_non_validee():
    rapport = _complete_piston_report()
    rapport.pop("contraintes")

    dossier = ajouter_dossier_definition_solidworks(rapport, "piston")["dossier_definition_solidworks"]

    assert dossier["statut_validation"] == "not_validated"
    assert dossier["statut"] != "validated_by_calculation"
    assert dossier["contraintes_rdm"] == []


def test_interface_sans_jeu_ou_tolerance_reste_partielle():
    rapport = _complete_piston_report()
    rapport["interfaces"][0].pop("jeu_ou_serrage")
    rapport["interfaces"][0].pop("tolerance")

    dossier = ajouter_dossier_definition_solidworks(rapport, "piston")["dossier_definition_solidworks"]

    assert any(interface["statut"] == "partial" for interface in dossier["interfaces_assemblage"])
    assert dossier["statut"] != "ready_for_manual_modeling"


def test_inconnues_backend_remontent_dans_dossier():
    rapport = _complete_piston_report()
    rapport["inconnues"] = {
        "impossibles": [
            {
                "nom": "matiere_traitement_surface",
                "raison": "choix matiere non fourni",
                "statut": "missing_required",
            }
        ],
        "partielles": [],
    }

    dossier = ajouter_dossier_definition_solidworks(rapport, "piston")["dossier_definition_solidworks"]

    assert dossier["statut"] == "blocked"
    assert dossier["inconnues_bloquantes"][0]["nom"] == "matiere_traitement_surface"

