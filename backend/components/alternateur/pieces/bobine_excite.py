# backend/components/alternateur/pieces/bobine_excite.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class BobineExcitation:
    """Modélise la bobine d'excitation de l'alternateur.
    - Calcule les pertes cuivre liées à l'excitation et le champ magnétique.
    - Nécessite le nombre de spires, le courant d'excitation et les paramètres du fil.
    """

    nombre_spires: Optional[int] = None
    courant_excite_a: Optional[float] = None
    resistivity_ohm_m: Optional[float] = None
    longueur_fil_m: Optional[float] = None
    section_fil_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_ref_c: float = 20.0
    coef_temperature: float = 0.00393

    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "bobine_excite",
            "entrees": {},
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }
        if self.nombre_spires is None:
            rep["inconnues"]["impossibles"].append({"nom": "nombre_spires", "raison": "Nombre de spires nécessaire"})
        else:
            rep["entrees"]["nombre_spires"] = self.nombre_spires
        if self.courant_excite_a is None:
            rep["inconnues"]["impossibles"].append({"nom": "courant_excite_a", "raison": "Courant d'excitation requis"})
        else:
            rep["entrees"]["courant_excite_a"] = self.courant_excite_a

        # Calcul des pertes cuivre si on possède les paramètres de résistance du fil
        if all(v is not None for v in (self.resistivity_ohm_m, self.longueur_fil_m, self.section_fil_m2, self.courant_excite_a)):
            R = self.resistivity_ohm_m * self.longueur_fil_m / self.section_fil_m2
            P_loss = (self.courant_excite_a ** 2) * R
            # Correction thermique du fil
            if self.temperature_c is not None:
                facteur = 1 + self.coef_temperature * (self.temperature_c - self.temperature_ref_c)
                P_loss *= facteur
            rep["resultats"]["pertes_cuivre_excitation_w"] = P_loss
        else:
            rep["inconnues"]["partielles"].append({"nom": "pertes_cuivre_excitation_w", "raison": "Paramètres de résistance du fil manquants"})

        return rep
