import pytest
from backend.components.moteur_thermique.pieces.arbre_vilbrequin import ArbreVilbrequin

def test_vilebrequin_init():
    v = ArbreVilbrequin(course_m=0.150)
    assert v.course_m == 0.150

def test_vilebrequin_analysis():
    v = ArbreVilbrequin(course_m=0.150, couple_max_Nm=1000.0, materiau_cle="alu_6061_t6")
    res = v.analyser()
    assert res["piece"] == "arbre_vilebrequin"
    assert "dimensionnements" in res
    assert "diametre_min_torsion_m" in res["dimensionnements"]

def test_vilebrequin_cao():
    v = ArbreVilbrequin(course_m=0.150, diametre_maneton_m=0.080, largeur_portee_maneton_m=0.060)
    res = v.analyser()
    assert "cao" in res
    assert res["bielle_maneton"]["diametre_maneton_m"] == 0.080