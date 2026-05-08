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
class PackBatterie:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    energie_nominale_kwh: Optional[float] = None
    tension_nominale_v: Optional[float] = None
    capacite_ah: Optional[float] = None
    masse_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    nb_series: Optional[int] = None
    nb_parallele: Optional[int] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "pack_batterie",
            "electrique": {},
            "integration": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        source = self.rapport_batterie or {}
        energie = self.energie_nominale_kwh
        if energie is None:
            energie = _get(source, "dimensionnement", "capacite_totale_kwh")
        tension = self.tension_nominale_v if self.tension_nominale_v is not None else _get(source, "entrees", "tension_nominale_v")
        capacite = self.capacite_ah if self.capacite_ah is not None else _get(source, "electrique", "capacite_Ah_estimee")
        masse = self.masse_kg if self.masse_kg is not None else _get(source, "dimensionnement", "masse_batterie_kg")
        volume = self.volume_m3 if self.volume_m3 is not None else _get(source, "dimensionnement_fin", "rapport", "volume_total_pack_m3")
        ns = self.nb_series if self.nb_series is not None else _get(source, "entrees", "nb_series")
        np = self.nb_parallele if self.nb_parallele is not None else _get(source, "entrees", "nb_parallele")

        rep["electrique"]["energie_nominale_kwh"] = energie
        rep["electrique"]["tension_nominale_v"] = tension
        rep["electrique"]["capacite_ah"] = capacite
        rep["integration"]["masse_kg"] = masse
        rep["integration"]["volume_m3"] = volume
        rep["integration"]["nb_series"] = ns
        rep["integration"]["nb_parallele"] = np

        if not _is_finite(energie):
            _push_unknown(rep, "partielles", "energie_nominale_kwh", "Calculable si la batterie a pu etre dimensionnee.")
        if not _is_finite(tension):
            _push_unknown(rep, "partielles", "tension_nominale_v", "Requise pour caracteriser completement le pack.")
        if not _is_finite(capacite):
            _push_unknown(rep, "partielles", "capacite_ah", "Calculable si energie et tension nominale sont connues.")
        if not _is_finite(masse):
            _push_unknown(rep, "partielles", "masse_kg", "Calculable si la densite energetique pack est fournie.")
        if volume is None:
            _push_unknown(rep, "partielles", "volume_m3", "Disponible si le dimensionnement fin de pack a ete execute.")

        return rep
