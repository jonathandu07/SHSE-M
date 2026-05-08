import pytest
from backend.components.moteur_thermique.pieces.piston import Piston

def test_piston_init():
    p = Piston(alesage_nominal_m=0.130, course_m=0.150, materiau_piston_cle="alu_6061_t6")
    assert p.alesage_nominal_m == 0.130

def test_piston_analysis():
    p = Piston(alesage_nominal_m=0.130, course_m=0.150, pression_max_pa=10e6, materiau_piston_cle="alu_6061_t6")
    res = p.analyser()
    assert res["piece"] == "piston"
    assert "dimensions" in res
    assert "masses" in res
    
def test_piston_with_cylindre():
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre
    c = Cylindre(alesage_m=0.130, course_m=0.150, longueur_utile_m=0.200, 
                 pression_service_pa=10e6, pression_max_pa=15e6, materiau_cle="acier_42crmo4_qt")
    p = Piston(cylindre=c, materiau_piston_cle="alu_6061_t6")
    res = p.analyser()
    assert res["liaisons"]["cylindre"]["cylindre_fournit"] is True
    assert res["liaisons"]["cylindre"]["alesage_nominal_m"] == 0.130