from backend.ensemble.resolution_inconnues import CahierDesChargesSTHOME, resoudre_inconnues_systeme


def test_systeme_minimal_devient_calculable():
    report = resoudre_inconnues_systeme(
        {
            "puissance_traction_kw": 100.0,
            "rpm_moteur_nominal": 3000.0,
            "pme_pa": 1_000_000.0,
            "pression_max_pa": 4_000_000.0,
            "distance_km": 120.0,
            "conso_kwh_km": 0.18,
            "cellule_tension_nominale_v": 3.6,
            "cellule_capacite_ah": 5.0,
            "contrainte_service_pa": 120_000_000.0,
        },
        {},
        CahierDesChargesSTHOME(
            tension_bus_dc_v=400.0,
            vitesse_piston_max_ms=16.0,
            materiaux_autorises=("acier_42crmo4_qt", "alu_7075_t6"),
            familles_materiaux_autorisees=("metal",),
        ),
    )

    payload = report.payload_resolu
    assert payload["puissance_traction_w"] == 100_000.0
    assert payload["courant_bus_dc_a"] > 0.0
    assert payload["couple_moteur_nm"] > 0.0
    assert payload["cylindree_totale_m3"] > 0.0
    assert payload["nb_cellules_serie"] > 0
    assert payload["nb_cellules_parallele"] > 0
    assert payload["materiau_cle"] in {"acier_42crmo4_qt", "alu_7075_t6"}
    assert report.coherence_systeme["score_global"] > 0.65


def test_systeme_incoherent_est_rejete():
    report = resoudre_inconnues_systeme(
        {
            "puissance_bus_dc_w": 100_000.0,
            "tension_bus_dc_v": 400.0,
            "courant_bus_dc_a": 1.0,
            "puissance_moteur_requise_W": 80_000.0,
            "rpm_moteur_nominal": 3000.0,
            "couple_moteur_nm": 1.0,
        },
        {},
        CahierDesChargesSTHOME(autoriser_choix_materiau=False),
    )

    coherence = report.coherence_systeme
    assert coherence["statut"] == "invalide"
    assert coherence["points_bloquants"]
    assert report.inconnues["conflits"]

