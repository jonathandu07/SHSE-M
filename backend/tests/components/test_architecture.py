import pytest
from backend.components.architechture.architecture import Architecture

def test_architecture_init():
    arch = Architecture(architecture_forcee="V", nombre_cylindres=8)
    assert arch.nombre_cylindres == 8
    assert arch.architecture_forcee == "V"

def test_architecture_dimensionnement():
    arch = Architecture(architecture_forcee="L", nombre_cylindres=4)
    res = arch.analyser()
    assert res["architecture_finale"] == "L"
    assert res["nombre_cylindres_final"] == 4
    assert "dimensions_bloc" in res

def test_architecture_invalid():
    with pytest.raises(ValueError):
        ArchitectureMoteur(type_architecture="Z", nombre_cylindres=5) # Type inconnu