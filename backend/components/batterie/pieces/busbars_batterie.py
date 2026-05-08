from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

from backend.components.batterie.modules.calcul_electrique_pack import calcul_section_cuivre_estimee_mm2


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
class BusbarsBatterie:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    courant_a: Optional[float] = None
    densite_courant_a_mm2: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "busbars_batterie",
            "electrique": {},
            "dimensionnement": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        source = self.rapport_batterie or {}
        current = self.courant_a
        if current is None:
            current = _get(source, "charge", "courant_charge_A")
        if current is None:
            current = _get(source, "electrique", "courant_decharge_A_estime")

        j = self.densite_courant_a_mm2
        if current is not None and j is not None and _is_finite(current) and _is_finite(j) and float(j) > 0.0:
            rep["dimensionnement"]["section_cuivre_estimee_mm2"] = calcul_section_cuivre_estimee_mm2(float(current), float(j))
        else:
            _push_unknown(rep, "partielles", "section_cuivre_estimee_mm2", "Calculable si courant_a et densite_courant_a_mm2 sont fournis.")

        rep["electrique"]["courant_a"] = current
        rep["dimensionnement"]["densite_courant_a_mm2"] = j
        if current is None:
            _push_unknown(rep, "partielles", "courant_a", "Courant de charge/decharge requis pour predimensionner les busbars.")
        return rep
