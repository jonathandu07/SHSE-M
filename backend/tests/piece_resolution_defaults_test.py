from backend.main import dimensionner_systeme_shsem


def test_piece_resolution_defaults_close_key_arbre_chain():
    report = dimensionner_systeme_shsem(
        puissance_traction_kw=150.0,
        charger_batterie=True,
        vitesse_moteur_thermique_rpm=1500.0,
        pme_pa=15e5,
        pression_max_pa=80e5,
        rendement_mecanique_cible_min=0.85,
        carburants_autorises=["diesel", "essence", "ethanol", "methanol", "gpl", "gnv", "hydrogene"],
        mode_carburant="multi_carburant",
        architectures_autorisees=["L", "V", "W", "Etoile", "Boxer"],
        moteur_thermique_definition={
            "temps_moteur": 4,
            "rpm_nominal": 1500.0,
            "pme_pa": 15e5,
            "pression_max_pa": 80e5,
            "rendement_mecanique_cible_min": 0.85,
            "mode_carburant": "multi_carburant",
            "carburants_autorises": ["diesel", "essence", "ethanol", "methanol", "gpl", "gnv", "hydrogene"],
        },
    )

    rapports = report["rapports_pieces"]

    arbre = rapports["arbre"]
    clavette = rapports["clavette_arbre"]
    bielle = rapports["bielle"]

    assert arbre["cao"]["diametre_nominal_arbre_m"] is not None
    assert arbre["cao"]["zone_clavette"]["b_m"] is not None
    assert not clavette["inconnues"]["impossibles"]
    assert clavette["cao"]["clavette"]["longueur_m"] is not None
    assert not bielle["inconnues"]["impossibles"]
