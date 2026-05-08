# backend/components/architechture/pieces/bloc_moteur_arch.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class BlocMoteurArch:
    """
    Conséquences architecturales sur le Bloc Moteur (Carter).
    """
    architecture: str = "L"
    nb_cylindres: int = 4
    alesage_m: float = 0.1
    course_m: float = 0.1
    
    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "bloc_moteur_arch",
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # Multiplicateurs de volume et de masse du carter
        # Un bloc en V est plus court mais beaucoup plus large et a deux plans de joint.
        
        masse_base = self.nb_cylindres * 10.0  # Hypothèse 10kg par cylindre pour un bloc L
        largeur_base = 0.4
        hauteur_base = 0.5
        
        f_masse = 1.0
        f_largeur = 1.0
        f_hauteur = 1.0
        
        if self.architecture == "V":
            f_masse = 1.25  # Plus de matière pour rigidifier le V
            f_largeur = 1.8
            f_hauteur = 0.8
        elif self.architecture == "W":
            f_masse = 1.5
            f_largeur = 2.2
            f_hauteur = 0.75
        elif self.architecture == "Etoile":
            f_masse = 1.1
            f_largeur = 2.5
            f_hauteur = 2.5
        elif self.architecture == "Boxer":
            f_masse = 1.3
            f_largeur = 2.0
            f_hauteur = 0.5

        rep["resultats"] = {
            "masse_bloc_estimee_kg": masse_base * f_masse,
            "largeur_hors_tout_m": largeur_base * f_largeur,
            "hauteur_hors_tout_m": hauteur_base * f_hauteur,
            "nb_plans_de_joint_culasse": 1 if self.architecture == "L" else (2 if self.architecture in ["V", "Boxer"] else 3)
        }

        return rep
