from __future__ import annotations

"""Contrat stable entre backend STHO-ME et frontend."""

from typing import Any, Dict, List, Mapping


ALLOWED_STATUSES = {
    "computed",
    "input",
    "database",
    "derived",
    "candidate_generated",
    "candidate_optimized",
    "candidate_rejected",
    "missing_required",
    "missing_optional",
    "partial",
    "impossible",
    "error",
}


def build_frontend_contract(
    rapport: dict[str, Any],
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    fields: List[Dict[str, Any]] = []
    trace_by_path = _trace_by_path(rapport)
    for path, label, unit in (
        ("synthese.moteur_thermique.alesage_m", "Alesage", "m"),
        ("synthese.moteur_thermique.course_m", "Course", "m"),
        ("synthese.moteur_thermique.nombre_cylindres", "Nombre cylindres", None),
        ("synthese.moteur_thermique.rpm_nominal", "Regime nominal", "rpm"),
        ("synthese.moteur_thermique.pme_pa", "PME", "Pa"),
        ("synthese.systeme.P_bus_dc_design_w", "Puissance bus DC", "W"),
        ("coherence_systeme.score_global", "Score coherence", None),
    ):
        value = _get_path(rapport, path)
        if value is not None:
            trace = trace_by_path.get(path, {})
            fields.append(
                {
                    "path": path,
                    "label": label,
                    "value": value,
                    "unit": unit,
                    "status": _normalize_status(trace.get("status") or trace.get("source") or "computed"),
                    "source": trace.get("from") or trace.get("source") or "STHO_ME",
                    "editable": False,
                    "blocking": False,
                    "reason": trace.get("reason"),
                    "confidence": trace.get("confidence") or "validated",
                }
            )

    unknowns = _normalize_unknowns(rapport)
    cao = _build_cao_contract(rapport, unknowns)
    actions = _build_actions(unknowns, cao)
    return {
        "project_id": project_id,
        "meta": dict(rapport.get("meta", {})) if isinstance(rapport.get("meta"), Mapping) else {},
        "summary": {
            "fields_count": len(fields),
            "unknowns_count": sum(len(v) for v in unknowns.values() if isinstance(v, list)),
            "cao_available": cao["available"],
            "score_global": _get_path(rapport, "coherence_systeme.score_global"),
        },
        "fields": fields,
        "unknowns": unknowns,
        "alerts": rapport.get("alertes", {}) if isinstance(rapport.get("alertes"), Mapping) else {},
        "cao": cao,
        "actions": actions,
        "raw_available": True,
    }


def _trace_by_path(rapport: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    trace = rapport.get("tracabilite") or rapport.get("traçabilite") or {}
    values = trace.get("valeurs", {}) if isinstance(trace, Mapping) else {}
    out = dict(values) if isinstance(values, Mapping) else {}
    for hyp in rapport.get("hypotheses_resolues", []) if isinstance(rapport.get("hypotheses_resolues"), list) else []:
        if isinstance(hyp, Mapping):
            champ = hyp.get("champ")
            if champ:
                out.setdefault(str(champ), {
                    "source": hyp.get("type_resolution", "derived"),
                    "from": hyp.get("source"),
                    "reason": hyp.get("justification"),
                    "confidence": hyp.get("niveau_confiance"),
                })
    return out


def _normalize_unknowns(rapport: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    inc = rapport.get("inconnues", {})
    out = {"impossibles": [], "partielles": [], "bloquantes": [], "non_bloquantes": []}
    if isinstance(inc, Mapping):
        for key in out:
            vals = inc.get(key) or []
            if isinstance(vals, list):
                out[key] = [dict(v) if isinstance(v, Mapping) else {"raison": str(v)} for v in vals]
    return out


def _build_cao_contract(rapport: Mapping[str, Any], unknowns: Mapping[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    cao = rapport.get("cao", {})
    if not isinstance(cao, Mapping):
        cao = {}
    blocking = list(unknowns.get("impossibles", [])) + list(unknowns.get("bloquantes", []))
    ready = bool(cao.get("solidworks_ready_detaille") or cao.get("available"))
    available = ready and not blocking
    return {
        "available": available,
        "status": "computed" if available else "missing_required",
        "reason": None if available else "CAO non fermee : champs requis ou validation SolidWorks absents.",
        "missing_required_fields": [_unknown_path(x) for x in blocking],
        "raw": dict(cao),
    }


def _build_actions(unknowns: Mapping[str, List[Dict[str, Any]]], cao: Mapping[str, Any]) -> List[Dict[str, Any]]:
    actions = [
        {"id": "load_known_data", "label": "charger donnees connues", "enabled": True},
        {"id": "resolve_unknowns", "label": "resoudre inconnues", "enabled": True},
        {"id": "lock_parameters", "label": "verrouiller parametres proposes", "enabled": True},
    ]
    if not cao.get("available"):
        actions.append({"id": "cao_blocked", "label": "CAO non fermee", "enabled": False, "reason": cao.get("reason")})
    return actions


def _normalize_status(value: Any) -> str:
    mapping = {
        "calculable": "computed",
        "computed": "computed",
        "deduite": "derived",
        "derived": "derived",
        "materiau": "database",
        "database": "database",
        "optimisee": "candidate_optimized",
        "candidate_optimized": "candidate_optimized",
    }
    status = mapping.get(str(value), str(value))
    return status if status in ALLOWED_STATUSES else "partial"


def _unknown_path(item: Mapping[str, Any]) -> str:
    return str(item.get("path") or item.get("champ") or item.get("nom") or "unknown")


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

