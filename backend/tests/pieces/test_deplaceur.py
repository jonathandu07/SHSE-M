import pytest
from backend.pieces.cylindre import Cylindre
from backend.pieces.deplaceur import Deplaceur

def test_deplaceur_analyser_without_longueur_totale():
    # Create a simple cylinder with required parameters
    cyl = Cylindre(
        alesage_m=0.1,
        course_m=0.2,
        longueur_utile_m=0.3,
        pression_service_pa=1e5,
        pression_max_pa=2e5,
        temperature_service_C=20,
        facteur_securite=1.5,
        contrainte_admissible_pa=250e6,
        module_young_pa=210e9,
        coefficient_poisson=0.3,
        coefficient_dilatation_1_k=12e-6,
        conductivite_w_m_k=45,
        densite_kg_m3=7800,
        h_interne_w_m2_k=500,
        h_externe_w_m2_k=50,
        delta_temperature_k=10,
    )
    # Instantiate Deplaceur without explicit longueur_totale_m
    dep = Deplaceur(cylindre=cyl, materiau_cle=None)
    # Should not raise an exception
    rapport = dep.analyser(strict=False)
    # Verify that some expected keys are present
    assert isinstance(rapport, dict)
    assert "geometrie" in rapport
    # longueur_totale_m should be derived from cylinder
    assert rapport["geometrie"]["longueur_totale_m"] == pytest.approx(0.3)