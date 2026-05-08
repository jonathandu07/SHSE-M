# backend/components/alternateur/pieces/roulement_alternateur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class RoulementAlternateur:
    """Modélise un roulement supportant l'arbre de l'alternateur.
    - Calcule la charge radiale et la durée de vie L10 (ISO‑281 simplifiée).
    """

    charge_radiale_n: Optional[float] = None  # N (force radiale)
    vitesse_rpm: Optional[float] = None
    facteur_charge: float = 1.0
    duree_vie_l10_h: Optional[float] = None

    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "roulement",
            "entrees": {},
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }
        if self.charge_radiale_n is None:
            rep["inconnues"]["impossibles"].append({"nom": "charge_radiale_n", "raison": "Charge radiale requise"})
        else:
            rep["entrees"]["charge_radiale_n"] = self.charge_radiale_n
        if self.vitesse_rpm is None:
            rep["inconnues"]["impossibles"].append({"nom": "vitesse_rpm", "raison": "Vitesse de rotation requise"})
        else:
            rep["entrees"]["vitesse_rpm"] = self.vitesse_rpm
        # Calcul simplifié de durée de vie L10
        if self.charge_radiale_n is not None and self.vitesse_rpm is not None:
            C = 1e6  # capacité nominale arbitraire pour l'exemple
            P = self.charge_radiale_n * self.facteur_charge
            L10 = (C / P) ** 3  # heures
            rep["resultats"]["duree_vie_l10_h"] = L10
        else:
            rep["inconnues"]["partielles"].append({"nom": "duree_vie_l10_h", "raison": "Paramètres manquants"})
        return rep
