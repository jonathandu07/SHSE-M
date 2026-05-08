import pytest
from backend.components.architechture.architecture import ArchitectureMoteur

def test_architecture_init():
    arch = ArchitectureMoteur(type_architecture="V", nombre_cylindres=8)
    assert arch.nombre_cylindres == 8
    assert arch.type_architecture == "V"

def test_architecture_dimensionnement():
    arch = ArchitectureMoteur(type_architecture="L", nombre_cylindres=4)
    res = arch.analyser()
    assert res["type_architecture"] == "L"
    assert res["nombre_cylindres"] == 4
    assert "dimensions_bloc" in res

def test_architecture_invalid():
    with pytest.raises(ValueError):
        ArchitectureMoteur(type_architecture="Z", nombre_cylindres=5) # Type inconnu