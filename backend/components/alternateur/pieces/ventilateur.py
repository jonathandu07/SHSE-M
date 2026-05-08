# backend/components/alternateur/pieces/ventilateur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

# No external module needed for this simple model

@dataclass
class Ventilateur:
    """Modélise le ventilateur de refroidissement de l'alternateur.
    - Utilise la vitesse de rotation du rotor pour estimer le débit d'air.
    - Calcule le coefficient de convection et la température du rotor.
    """

    rotor: Optional[Any] = None  # reference to Rotor for rpm
    surface_echange_m2: Optional[float] = None
    coeff_convection: Optional[float] = None  # h (W/m²·K)
    temperature_ambiante_c: Optional[float] = None
    pertes_fixes_w: float = 0.0

    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "ventilateur",
            "entrees": {},
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }
        # 1️⃣ Vitesse du rotor (rpm)
        rpm = None
        if self.rotor is not None:
            rpm = getattr(self.rotor, "vitesse_rotation_rpm", None)
        if rpm is None:
            rep["inconnues"]["impossibles"].append({"nom": "vitesse_rotation_rpm", "raison": "Nécessaire pour débit d'air"})
        else:
            rep["entrees"]["vitesse_rotation_rpm"] = rpm

        # 2️⃣ Surface d'échange
        if self.surface_echange_m2 is None:
            rep["inconnues"]["impossibles"].append({"nom": "surface_echange_m2", "raison": "Surface d'échange nécessaire"})
        else:
            rep["entrees"]["surface_echange_m2"] = self.surface_echange_m2

        # 3️⃣ Coefficient de convection (si non fourni, on estime)
        if self.coeff_convection is None and rpm is not None:
            # estimation très simplifiée (h proportional to sqrt(rpm))
            h_est = 0.1 * math.sqrt(rpm)
            rep["resultats"]["coeff_convection_estimé"] = h_est
        elif self.coeff_convection is not None:
            rep["entrees"]["coeff_convection"] = self.coeff_convection

        # 4️⃣ Température finale (ΔT = Q / (h·A))
        if rpm is not None and self.surface_echange_m2 is not None:
            Q = self.pertes_fixes_w
            h = self.coeff_convection if self.coeff_convection is not None else 0.1 * math.sqrt(rpm)
            if h > 0:
                delta_t = Q / (h * self.surface_echange_m2)
                rep["resultats"]["delta_T_K"] = delta_t
            else:
                rep["inconnues"]["partielles"].append({"nom": "delta_T_K", "raison": "coeff convection nul"})
        else:
            rep["inconnues"]["partielles"].append({"nom": "delta_T_K", "raison": "rpm ou surface manquants"})

        return rep
