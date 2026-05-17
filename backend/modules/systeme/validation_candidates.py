from __future__ import annotations

"""Validation post-recalcul des candidats."""

from typing import Any, Dict, Mapping

from backend.modules.systeme.status import (
    SOURCE_CDC,
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    normalize_status,
)


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
    status = normalize_status(getattr(candidate, "statut", None) or source)
    reason = str(getattr(candidate, "raison", "") or "").strip()
    deps = list(getattr(candidate, "dependances", []) or [])
    metadata = getattr(candidate, "metadata", {}) or {}
    generated_from_cdc = source == SOURCE_CDC or status == STATUS_CANDIDATE_FROM_CDC

    if not source or source == "unknown":
        return {"ok": False, "raison": "source non tracable", "score": None, "details": {"path": path}}

    if generated_from_cdc:
        if not reason:
            return {"ok": False, "raison": "justification manquante", "score": None, "details": {"path": path}}
        if not deps:
            return {"ok": False, "raison": "dependances manquantes", "score": None, "details": {"path": path}}
        if "domaine" not in metadata:
            return {"ok": False, "raison": "domaine de validite manquant", "score": None, "details": {"path": path}}

    locked_conflict = _locked_conflict(path, value, cahier_des_charges)
    if locked_conflict is not None:
        return {"ok": False, "raison": "valeur verrouillee contradictoire", "score": 0.0, "details": locked_conflict}

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

    interface_issue = _interface_issue(rapport_apres)
    if interface_issue is not None:
        details["interface_issue"] = interface_issue
        return {"ok": False, "raison": "interface piece incompatible", "score": 0.0, "details": details}

    if generated_from_cdc and optimisation is None:
        return {
            "ok": False,
            "raison": "optimisation requise pour valider un candidat CDC",
            "score": None,
            "details": details,
        }
    if generated_from_cdc and optimisation is not None and _optimisation_failed(optimisation):
        details["optimisation"] = optimisation
        return {"ok": False, "raison": "optimisation en echec", "score": 0.0, "details": details}

    opt_score = _score_from_optimisation(optimisation or {})
    coherence_score = _score_from_report(rapport_apres)
    before_score = _score_from_report(rapport_avant)
    score = opt_score if opt_score is not None else coherence_score
    if generated_from_cdc and opt_score is None:
        return {"ok": False, "raison": "score optimisation absent pour candidat CDC", "score": None, "details": details}
    if before_score is not None and score is not None and score < before_score - 0.10:
        return {"ok": False, "raison": "score optimisation degrade", "score": float(score), "details": details}
    if score is None:
        score = max(0.0, 1.0 - 0.05 * after["bloquantes"] - 0.02 * after["partielles"])
    details["score_report"] = coherence_score
    details["score_optimisation"] = opt_score

    details["status_if_accepted"] = STATUS_VALIDATED_BY_OPTIMIZATION if generated_from_cdc else status
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


def _locked_conflict(path: str, value: Any, cdc: Mapping[str, Any]) -> dict[str, Any] | None:
    locked = cdc.get("locked_values") or cdc.get("valeurs_verrouillees") or {}
    if not isinstance(locked, Mapping):
        return None
    expected = None
    found = False
    if path in locked:
        expected = locked[path]
        found = True
    else:
        key = path.split(".")[-1]
        if key in locked:
            expected = locked[key]
            found = True
    if not found:
        return None
    if expected == value:
        return None
    return {"path": path, "locked_value": expected, "candidate_value": value}


def _interface_issue(report: Mapping[str, Any]) -> dict[str, Any] | None:
    for root_key in ("interfaces", "liaisons", "coherence_interfaces"):
        block = report.get(root_key)
        issue = _find_false_coherence(block, path=root_key)
        if issue is not None:
            return issue
    return None


def _find_false_coherence(node: Any, *, path: str) -> dict[str, Any] | None:
    if isinstance(node, Mapping):
        for key, value in node.items():
            key_l = str(key).lower()
            next_path = f"{path}.{key}"
            if key_l in {"compatible", "coherent", "coherent_global", "interface_ok"} and value is False:
                return {"path": next_path, "value": value}
            if key_l in {"incompatible", "interface_incompatible"} and value is True:
                return {"path": next_path, "value": value}
            child = _find_false_coherence(value, path=next_path)
            if child is not None:
                return child
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            child = _find_false_coherence(value, path=f"{path}[{idx}]")
            if child is not None:
                return child
    return None


def _optimisation_failed(optimisation: Mapping[str, Any]) -> bool:
    if not optimisation:
        return True
    for key in ("erreur", "error", "echec"):
        if optimisation.get(key):
            return True
    status = str(optimisation.get("status") or optimisation.get("statut") or "").lower()
    if status in {"error", "erreur", "echec", "failed", "invalide"}:
        return True
    synth = optimisation.get("synthese") or optimisation.get("synthese_optimisation") or {}
    if isinstance(synth, Mapping):
        status = str(synth.get("status") or synth.get("statut") or "").lower()
        if status in {"error", "erreur", "echec", "failed", "invalide"}:
            return True
    return False


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
