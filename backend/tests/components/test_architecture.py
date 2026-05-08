import pytest
from backend.components.architechture.architecture import Architecture

def test_architecture_init():
    arch = Architecture()
    assert arch.temps_moteur == 4

def test_architecture_dimensionnement():
    arch = Architecture()
    # analyser() nécessite des cibles
    res = arch.analyser(puissance_cible_w=100000.0, regime_tr_min=1500.0, pme_pa=10e5)
    # On vérifie que le résultat n'est pas vide
    assert res is not None
    assert "inconnues" in res

def test_architecture_invalid():
    arch = Architecture()
    with pytest.raises(ValueError):
        arch.recommander_pour_profil(None) 