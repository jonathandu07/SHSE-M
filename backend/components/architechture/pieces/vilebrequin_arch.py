# backend/components/architechture/pieces/vilebrequin_arch.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class VilebrequinArch:
    """
    Conséquences architecturales sur le Vilebrequin.
    Rôle : Déterminer la longueur et la complexité de l'arbre moteur selon la disposition.
    """
    architecture: str = "L"
    nb_cylindres: int = 4
    pas_cylindre_m: float = 0.15
    diametre_journal_m: float = 0.05

    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "vilebrequin_arch",
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # Facteurs de compacité longitudinale
        # L : 1 maneton par cylindre
        # V : 2 cylindres partagent souvent un maneton (V-twin, V4, V6...)
        # Boxer : 1 maneton par cylindre (souvent décalés)
        
        f_longueur = 1.0
        nb_manetons = self.nb_cylindres
        nb_paliers = self.nb_cylindres + 1

        if self.architecture == "V":
            f_longueur = 0.55  # Environ moitié de longueur pour le même nb de cylindres
            nb_manetons = math.ceil(self.nb_cylindres / 2)
            nb_paliers = nb_manetons + 1
        elif self.architecture == "W":
            f_longueur = 0.35
            nb_manetons = math.ceil(self.nb_cylindres / 3)
            nb_paliers = nb_manetons + 1
        elif self.architecture == "Etoile":
            f_longueur = 0.2
            nb_manetons = 1  # Tous les pistons sur le même maneton (bielle maîtresse)
            nb_paliers = 2
        elif self.architecture == "Boxer":
            f_longueur = 0.6
            nb_manetons = self.nb_cylindres
            nb_paliers = self.nb_cylindres + 1

        longueur_estimee = self.nb_cylindres * self.pas_cylindre_m * f_longueur
        
        rep["resultats"] = {
            "longueur_vilebrequin_m": longueur_estimee,
            "nb_manetons_estimes": nb_manetons,
            "nb_paliers_estimes": nb_paliers,
            "complexite_usinage": "Haute" if self.architecture in ["V", "W", "Etoile"] else "Standard"
        }

        return rep

import math
