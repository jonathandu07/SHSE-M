from backend.ensemble.STHO_ME import STHO_ME


def test_stho_me_inclut_resolution_inconnues_avant_construction():
    orchestrateur = STHO_ME.depuis_config(
        {
            "meta": {
                "cahier_des_charges": {
                    "autoriser_choix_materiau": False,
                    "tension_bus_dc_v": 400.0,
                }
            },
            "analyses": {
                "moteur_thermique_definition": {
                    "puissance_visee_w": 50_000.0,
                    "rpm": 3000.0,
                    "pression_moyenne_effective_pa": 900_000.0,
                }
            },
        }
    )

    rapport = orchestrateur.analyser()

    assert "resolution_inconnues" in rapport
    assert rapport["hypotheses_resolues"]
    assert rapport["donnees_auto_completees"]
    assert "coherence_systeme" in rapport
    assert any(h["champ"] == "alesage_m" for h in rapport["hypotheses_resolues"])


def test_stho_me_ancienne_api_depuis_config_reste_compatible():
    rapport = STHO_ME.depuis_config({"meta": {"nom_projet": "compat"}}).analyser()

    assert rapport["meta"]["orchestrateur"] == "STHO_ME.py"
    assert "synthese" in rapport
    assert "inconnues" in rapport

