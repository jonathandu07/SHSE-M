from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _get(mapping_or_obj: Any, *path: str) -> Any:
    cur = mapping_or_obj
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
        if cur is None:
            return None
    return cur


def _push_unknown(report: Dict[str, Any], category: str, name: str, reason: str) -> None:
    report.setdefault("inconnues", {}).setdefault(category, []).append({"nom": name, "raison": reason})


@dataclass
class BoitierBatterie:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    masse_pack_kg: Optional[float] = None
    volume_pack_m3: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "boitier_batterie",
            "integration": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        source = self.rapport_batterie or {}
        masse = self.masse_pack_kg if self.masse_pack_kg is not None else _get(source, "dimensionnement", "masse_batterie_kg")
        volume = self.volume_pack_m3 if self.volume_pack_m3 is not None else _get(source, "dimensionnement_fin", "rapport", "volume_total_pack_m3")
        rep["integration"]["masse_pack_kg"] = masse
        rep["integration"]["volume_interne_m3"] = volume
        if not _is_finite(masse):
            _push_unknown(rep, "partielles", "masse_pack_kg", "Masse du pack requise pour qualifier le boitier.")
        if not _is_finite(volume):
            _push_unknown(rep, "partielles", "volume_interne_m3", "Volume disponible si le dimensionnement fin de pack est fourni.")
        return rep
