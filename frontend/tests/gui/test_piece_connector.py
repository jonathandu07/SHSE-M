import pytest
from frontend.gui.piece_connector import get_piece_instance

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

def test_get_piece_instance_fallback():
    """Vérifie le comportement si la pièce est inconnue."""
    assert get_piece_instance("flux_flux", {}) is None
