# backend/components/architechture/pieces/culasse_arch.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class CulasseArch:
    """
    Conséquences architecturales sur les Culasses et la Distribution.
    """
    architecture: str = "L"
    nb_cylindres: int = 4
    nb_soupapes_par_cyl: int = 4
    
    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "culasse_arch",
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }

        nb_bancs = 1
        if self.architecture in ["V", "Boxer"]:
            nb_bancs = 2
        elif self.architecture == "W":
            nb_bancs = 3
        elif self.architecture == "Etoile":
            nb_bancs = self.nb_cylindres # Une culasse par cylindre souvent

        # Complexité de la distribution
        # En V, on double le nombre d'arbres à cames (si DOHC)
        nb_arbres_cames = 2 if self.architecture == "L" else (4 if self.architecture in ["V", "Boxer"] else 6)
        
        rep["resultats"] = {
            "nb_culasses": nb_bancs,
            "nb_arbres_a_cames_totaux": nb_arbres_cames,
            "complexite_distribution": "Elevée" if nb_bancs > 1 else "Standard",
            "nb_soupapes_totales": self.nb_cylindres * self.nb_soupapes_par_cyl
        }

        return rep
