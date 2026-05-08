from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _push_unknown(report: Dict[str, Any], category: str, name: str, reason: str) -> None:
    report.setdefault("inconnues", {}).setdefault(category, []).append({"nom": name, "raison": reason})


@dataclass
class RotorMoteurElectrique:
    moteur: Optional[Any] = None
    couple_max_nm: Optional[float] = None
    regime_base_rpm: Optional[float] = None
    regime_max_rpm: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "rotor_moteur_electrique",
            "cinematique": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        moteur = self.moteur
        couple = self.couple_max_nm if self.couple_max_nm is not None else getattr(moteur, "couple_max_nm_calcule", None)
        regime_base = self.regime_base_rpm if self.regime_base_rpm is not None else getattr(moteur, "regime_base_rpm_calcule", None)
        regime_max = self.regime_max_rpm if self.regime_max_rpm is not None else getattr(moteur, "regime_max_rpm", None)
        rep["cinematique"]["couple_max_nm"] = couple
        rep["cinematique"]["regime_base_rpm"] = regime_base
        rep["cinematique"]["regime_max_rpm"] = regime_max
        if not _is_finite(couple):
            _push_unknown(rep, "partielles", "couple_max_nm", "Issu du moteur si la definition de courbe couple/puissance est complete.")
        if not _is_finite(regime_base):
            _push_unknown(rep, "partielles", "regime_base_rpm", "Calculable si le moteur est correctement defini.")
        return rep
