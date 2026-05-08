import pytest
from backend.components.moteur_thermique.pieces.bielle import CorpsBielle

def test_bielle_init():
    b = CorpsBielle(longueur_bielle_m=0.300, materiau_cle="acier_42crmo4_qt")
    assert b.longueur_bielle_m == 0.300

def test_bielle_analysis():
    b = CorpsBielle(longueur_bielle_m=0.300, force_axiale_max_N=50000.0, materiau_cle="acier_42crmo4_qt")
    res = b.analyser()
    assert res["piece"] == "corps_bielle"
    assert "efforts" in res
    assert res["efforts"]["force_axiale_max_N"] == 50000.0

def test_bielle_flambage():
    b = CorpsBielle(longueur_bielle_m=0.300, force_axiale_max_N=50000.0, 
                    materiau_cle="alu_6061_t6", section_fut_m2=0.001, inertie_min_fut_m4=1e-8,
                    K_flambage=1.0)
    res = b.analyser()
    assert "flambage" in res
    if res["flambage"]:
        # La clé exacte est charge_critique_N dans analyser()
        assert "charge_critique_N" in res["flambage"]
        assert res["flambage"]["charge_critique_N"] > 0