from __future__ import annotations

"""Validation post-recalcul des candidats."""

from typing import Any, Dict, Mapping


def valider_candidate(
    *,
    candidate: Any,
    rapport_avant: dict[str, Any],
    rapport_apres: dict[str, Any],
    cahier_des_charges: dict[str, Any],
    optimisation: dict[str, Any] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    details: Dict[str, Any] = {}
    path = getattr(candidate, "path", None) or getattr(candidate, "nom", "")
    value = getattr(candidate, "valeur", None)
    source = getattr(candidate, "source", None)

    if not source or source == "unknown":
        return {"ok": False, "raison": "source non tracable", "score": None, "details": {"path": path}}

    bounds = _bounds_for(path, cahier_des_charges)
    if bounds is not None and isinstance(value, (int, float)):
        mini, maxi = bounds
        details["bounds"] = {"min": mini, "max": maxi, "value": value}
        if mini is not None and value < mini:
            return {"ok": False, "raison": "valeur sous borne CDC", "score": 0.0, "details": details}
        if maxi is not None and value > maxi:
            return {"ok": False, "raison": "valeur au-dessus borne CDC", "score": 0.0, "details": details}

    before = _unknown_counts(rapport_avant)
    after = _unknown_counts(rapport_apres)
    details["unknowns_before"] = before
    details["unknowns_after"] = after
    if after["impossibles"] > before["impossibles"]:
        return {"ok": False, "raison": "nouvelle inconnue impossible", "score": 0.0, "details": details}
    if after["bloquantes"] > before["bloquantes"]:
        return {"ok": False, "raison": "inconnues bloquantes aggravees", "score": 0.0, "details": details}

    cao_before = _cao_available(rapport_avant)
    cao_after = _cao_available(rapport_apres)
    details["cao_before"] = cao_before
    details["cao_after"] = cao_after
    if strict and cao_before and not cao_after:
        return {"ok": False, "raison": "coherence CAO degradee", "score": 0.0, "details": details}

    opt_score = _score_from_optimisation(optimisation or {})
    coherence_score = _score_from_report(rapport_apres)
    score = opt_score if opt_score is not None else coherence_score
    if score is None:
        score = max(0.0, 1.0 - 0.05 * after["bloquantes"] - 0.02 * after["partielles"])
    details["score_report"] = coherence_score
    details["score_optimisation"] = opt_score

    return {"ok": True, "raison": None, "score": float(score), "details": details}


def _bounds_for(path: str, cdc: Mapping[str, Any]) -> tuple[float | None, float | None] | None:
    key = path.split(".")[-1]
    bounds = cdc.get("bornes", {})
    if isinstance(bounds, Mapping) and isinstance(bounds.get(path), Mapping):
        b = bounds[path]
        return _num(b.get("min")), _num(b.get("max"))
    if isinstance(bounds, Mapping) and isinstance(bounds.get(key), Mapping):
        b = bounds[key]
        return _num(b.get("min")), _num(b.get("max"))
    mini = _num(cdc.get(f"{key}_min"))
    maxi = _num(cdc.get(f"{key}_max"))
    if mini is not None or maxi is not None:
        return mini, maxi
    return None


def _unknown_counts(report: Mapping[str, Any]) -> Dict[str, int]:
    inc = report.get("inconnues", {})
    if not isinstance(inc, Mapping):
        return {"impossibles": 0, "partielles": 0, "bloquantes": 0}
    return {
        "impossibles": len(inc.get("impossibles") or []),
        "partielles": len(inc.get("partielles") or []),
        "bloquantes": len(inc.get("bloquantes") or []),
    }


def _cao_available(report: Mapping[str, Any]) -> bool:
    cao = report.get("cao", {})
    if not isinstance(cao, Mapping):
        return False
    if "available" in cao:
        return bool(cao.get("available"))
    return bool(cao.get("solidworks_ready_detaille") or cao.get("solidworks_ready_minimal"))


def _score_from_report(report: Mapping[str, Any]) -> float | None:
    coh = report.get("coherence_systeme", {})
    if isinstance(coh, Mapping):
        value = coh.get("score_global")
        if isinstance(value, (int, float)):
            return float(value)
    opt = report.get("optimisation", {})
    return _score_from_optimisation(opt if isinstance(opt, Mapping) else {})


def _score_from_optimisation(opt: Mapping[str, Any]) -> float | None:
    synth = opt.get("synthese_optimisation", opt)
    if isinstance(synth, Mapping):
        value = synth.get("score_global")
        if isinstance(value, (int, float)):
            return float(value)
        value = synth.get("score_global_100")
        if isinstance(value, (int, float)):
            return float(value) / 100.0
    return None


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None

