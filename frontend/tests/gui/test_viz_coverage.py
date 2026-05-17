import pytest
import matplotlib.pyplot as plt

from frontend.gui.piece_connector import get_piece_instance
from frontend.gui.viz_utils import available_visualizations, get_viz_figure


@pytest.mark.parametrize(
    ("name", "engine_params", "db_data"),
    [
        (
            "arbre",
            {"nombre_cylindres": 5, "rpm_nominal": 3200.0},
            {
                "rapport": {
                    "dimensionnements": {"couple_max_Nm": 447.6, "rpm": 3200.0},
                    "cao": {"diametre_nominal_arbre_m": None, "longueur_totale_m": None},
                    "inconnues": {"impossibles": [{"nom": "diametre_arbre_m", "raison": "manquant"}], "partielles": []},
                }
            },
        ),
        (
            "roulement_aiguille_arbre",
            {"rpm_nominal": 3200.0},
            {
                "rapport": {
                    "charges": {"force_tangente_equivalente_N": 6800.0},
                    "dimensions_requises": {"d_interieur_requis_m": None},
                }
            },
        ),
        ("deplaceur", {"alesage_m": 0.118, "course_m": 0.130}, {"rapport": {"note": "partiel"}}),
        ("alternateur", {"tension_nominale_v": 400.0}, {"rapport": {"bus_dc": {"puissance_bus_dc_W": 150000.0}}}),
        ("batterie", {"tension_nominale_v": 400.0}, {"rapport": {"dimensionnement": {"energie_kwh": 42.0}}}),
        ("architecture", {}, {"rapport": {"meilleur": {"architecture": "L", "N_cyl": 5}}}),
    ],
)
@pytest.mark.parametrize("viz_type", ["sketches_2d", "charts", "views_3d"])
def test_visualizations_do_not_fabricate_missing_resources(name, engine_params, db_data, viz_type):
    obj = get_piece_instance(name, engine_params, db_data=db_data)

    fig = get_viz_figure(name, obj or db_data, viz_type)

    if fig is not None:
        plt.close(fig)
    else:
        availability = available_visualizations(name, obj or db_data)
        assert availability[viz_type]["available"] is False
