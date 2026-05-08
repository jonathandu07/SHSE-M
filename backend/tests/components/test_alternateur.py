import pytest
from backend.components.alternateur.alternateur import Alternateur

def test_alternateur_init():
    alt = Alternateur()
    assert alt is not None
    assert alt.nombre_poles == 12 # Valeur par défaut attendue

def test_alternateur_analysis():
    alt = Alternateur()
    res = alt.analyser_point_de_fonctionnement()
    assert isinstance(res, dict)
    assert "rendement" in res
    assert "bus_dc" in res
    
def test_alternateur_dimensionnement():
    alt = Alternateur()
    # On vérifie que les calculs de base ne crashent pas
    pieces = alt.analyser_point_de_fonctionnement().get("pieces", {})
    assert "rotor" in pieces
    assert "stator" in pieces