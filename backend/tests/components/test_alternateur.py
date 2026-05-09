import pytest
from backend.components.alternateur.alternateur import Alternateur

def test_alternateur_init():
    alt = Alternateur()
    assert alt is not None
    assert alt.nombre_poles is None 

def test_alternateur_analysis():
    alt = Alternateur(nombre_poles=12)
    res = alt.analyser_point_de_fonctionnement(vitesse_rotation_rpm=1500.0)
    assert isinstance(res, dict)
    assert "cinematique" in res
    assert res["cinematique"]["frequence_synchrone_hz"] == pytest.approx(150.0)

def test_alternateur_dimensionnement():
    alt = Alternateur()
    res = alt.analyser_point_de_fonctionnement(vitesse_rotation_rpm=1500.0)
    assert "cinematique" in res
    assert "electrique" in res
