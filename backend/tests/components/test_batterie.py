import pytest
from backend.components.batterie.batterie import Batterie

def test_batterie_init():
    batt = Batterie(tension_nominale_v=400.0)
    assert batt.tension_nominale_v == 400.0

def test_batterie_simulation():
    batt = Batterie(tension_nominale_v=400.0, rendement_charge=0.95)
    # Simulation d'un cycle
    res = batt.analyser_dimensionnement(puissance_pic_kw=50.0, duree_pic_s=10.0, energie_utile_imposee_kwh=10.0) 
    assert "dimensionnement" in res
    assert res["dimensionnement"]["E_utile_finale_kwh"] == 10.0
    
def test_batterie_thermal():
    batt = Batterie()
    # Le modèle thermique est dans analyser_dimensionnement si activé ou via les pièces
    res = batt.analyser_dimensionnement()
    assert "inconnues" in res