import pytest
import matplotlib.pyplot as plt
from frontend.gui.piece_connector import get_piece_instance, hydrate_piece
from frontend.gui.viz_utils import get_viz_figure

def test_get_piece_instance_moteur_thermique():
    """Vérifie l'instanciation des pièces du moteur thermique."""
    ep = {"alesage_m": 0.130, "course_m": 0.150}
    
    # Piston
    piston = get_piece_instance("piston", ep)
    assert piston is not None
    assert hasattr(piston, "analyser")
    assert piston.alesage_nominal_m == 0.130
    
    # Bielle
    bielle = get_piece_instance("bielle", ep)
    assert bielle is not None

def test_get_piece_instance_subsystems():
    """Vérifie l'instanciation des sous-systèmes."""
    ep = {"tension_nominale_v": 400.0}
    
    # Batterie
    batt = get_piece_instance("batterie", ep)
    assert batt is not None
    assert batt.tension_nominale_v == 400.0
    
    # Alternateur
    alt = get_piece_instance("alternateur", ep)
    assert alt is not None

    me = get_piece_instance("moteur_electrique", ep)
    assert me is not None

    bc = get_piece_instance("boite_crabots", ep)
    assert bc is not None


def test_get_piece_instance_supports_backend_piece_names():
    ep = {"alesage_m": 0.130, "course_m": 0.150}

    coussinet = get_piece_instance("coussinet_arbre_piston", ep)
    couvercle = get_piece_instance("couvercle_cylindre", ep)
    arbre = get_piece_instance("arbre", ep)
    arbre_piston = get_piece_instance("arbre_piston", ep)
    deplaceur = get_piece_instance("deplaceur", ep)
    joint_deplaceur = get_piece_instance("joint_deplaceur", ep)
    joint_piston = get_piece_instance("joint_piston", ep)

    assert coussinet is not None
    assert couvercle is not None
    assert arbre is not None
    assert arbre_piston is not None
    assert deplaceur is not None
    assert joint_deplaceur is not None
    assert joint_piston is not None

def test_get_piece_instance_fallback():
    """Vérifie le comportement si la pièce est inconnue."""
    assert get_piece_instance("flux_flux", {}) is None


def test_hydrate_piece_uses_backend_serialized_object():
    """Le front doit relire les attributs et rapports calculés par le backend."""
    ep = {"alesage_m": 0.130, "course_m": 0.150}
    piston = get_piece_instance("piston", ep)
    data = {
        "objet_serialise": {
            "alesage_nominal_m": 0.222,
            "course_m": 0.333,
        },
        "rapport": {
            "resultat": 42,
        },
    }

    hydrate_piece(piston, data)

    assert piston.alesage_nominal_m == pytest.approx(0.222)
    assert piston.course_m == pytest.approx(0.333)
    assert piston.analyser()["resultat"] == 42


def test_arbre_sketch_returns_diagnostic_figure_when_geometry_is_missing():
    arbre = get_piece_instance(
        "arbre",
        {"nombre_cylindres": 5, "rpm_nominal": 3200.0},
        db_data={
            "rapport": {
                "dimensionnements": {"couple_max_Nm": 447.6, "rpm": 3200.0},
                "cao": {"diametre_nominal_arbre_m": None, "longueur_totale_m": None},
                "inconnues": {"impossibles": [{"nom": "diametre_arbre_m", "raison": "manquant"}], "partielles": []},
            }
        },
    )

    fig = get_viz_figure("arbre", arbre, "sketches_2d")

    assert fig is not None
    plt.close(fig)
