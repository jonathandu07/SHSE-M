import pytest
from backend.components.batterie.batterie import Batterie

def test_batterie_init():
    batt = Batterie(tension_nominale_v=400.0)
    assert batt.tension_nominale_v == 400.0

def test_batterie_simulation():
    batt = Batterie(tension_nominale_v=400.0)
    # Simulation d'un cycle de décharge/charge
    res = batt.analyser_point_de_fonctionnement(puissance_w=-10000.0) # Décharge 10kW
    assert res["bilan"]["puissance_nette_W"] < 0
    
    res_charge = batt.analyser_point_de_fonctionnement(puissance_w=10000.0) # Charge 10kW
    assert res_charge["bilan"]["puissance_nette_W"] > 0

def test_batterie_thermal():
    batt = Batterie()
    res = batt.analyser_point_de_fonctionnement(puissance_w=50000.0)
    assert "thermique" in res
    assert res["thermique"]["pertes_joule_W"] > 0