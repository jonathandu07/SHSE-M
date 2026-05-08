from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _push_unknown(report: Dict[str, Any], category: str, name: str, reason: str) -> None:
    report.setdefault("inconnues", {}).setdefault(category, []).append({"nom": name, "raison": reason})


@dataclass
class StatorMoteurElectrique:
    moteur: Optional[Any] = None
    tension_bus_v: Optional[float] = None
    courant_max_a: Optional[float] = None
    puissance_max_w: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "stator_moteur_electrique",
            "electrique": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        moteur = self.moteur
        tension = self.tension_bus_v if self.tension_bus_v is not None else getattr(moteur, "tension_bus_v", None)
        courant = self.courant_max_a if self.courant_max_a is not None else getattr(moteur, "courant_max_a", None)
        puissance = self.puissance_max_w if self.puissance_max_w is not None else getattr(moteur, "puissance_max_w", None)
        rep["electrique"]["tension_bus_v"] = tension
        rep["electrique"]["courant_max_a"] = courant
        rep["electrique"]["puissance_max_w"] = puissance
        if _is_finite(tension) and _is_finite(courant):
            rep["electrique"]["puissance_dc_max_w"] = float(tension) * float(courant)
        else:
            _push_unknown(rep, "partielles", "puissance_dc_max_w", "Calculable si tension_bus_v et courant_max_a sont fournis.")
        return rep
