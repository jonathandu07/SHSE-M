from __future__ import annotations

"""Contrat stable entre backend STHO-ME et frontend."""

from typing import Any, Dict, List, Mapping

from backend.modules.systeme.status import (
    ALLOWED_STATUSES,
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_COMPUTED,
    STATUS_DATABASE,
    STATUS_MISSING_REQUIRED,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    normalize_status,
)


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
            status = _normalize_status(trace.get("status") or trace.get("source") or "computed")
            metadata = trace.get("metadata") if isinstance(trace.get("metadata"), Mapping) else {}
            locked = bool(trace.get("locked") or metadata.get("locked"))
            fields.append(
                {
                    "path": path,
                    "label": label,
                    "value": value,
                    "unit": unit,
                    "status": status,
                    "source": trace.get("from") or trace.get("source") or "STHO_ME",
                    "editable": status == STATUS_CANDIDATE_FROM_CDC and not locked,
                    "blocking": False,
                    "reason": trace.get("reason"),
                    "confidence": trace.get("confidence") or ("candidate" if status == STATUS_CANDIDATE_FROM_CDC else "validated"),
                    "trace": dict(trace),
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


def build_diagnostic_contract(diagnostic: dict[str, Any]) -> dict[str, Any]:
    """Construit un contrat frontend passif depuis un diagnostic JSON."""
    causes = [dict(c) for c in diagnostic.get("causes_racines", []) if isinstance(c, Mapping)]
    fields: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    for cause in causes:
        path = str(cause.get("champ") or cause.get("path") or cause.get("id") or "")
        priority = _num(cause.get("priorite"), 50.0)
        impact = cause.get("impact") if isinstance(cause.get("impact"), Mapping) else {}
        patch = cause.get("patchs_proposes", [])
        fields.append(
            {
                "path": path,
                "label": str(cause.get("titre") or cause.get("id") or "Cause racine"),
                "value": cause.get("raison"),
                "unit": None,
                "status": STATUS_MISSING_REQUIRED if priority >= 70 else "partial",
                "source": "json_diagnostic",
                "editable": False,
                "blocking": bool(impact.get("bloque_cao") or impact.get("bloque_optimisation") or priority >= 70),
                "reason": cause.get("raison"),
                "confidence": "diagnostic",
                "trace": cause,
                "patch": patch[0] if isinstance(patch, list) and patch else None,
            }
        )
        actions.append(
            {
                "id": f"diagnostic_{cause.get('id', len(actions))}",
                "label": str(cause.get("actions", ["Voir cause"])[0] if cause.get("actions") else "Voir cause"),
                "enabled": True,
                "target": "edit_parameters",
                "path": path,
                "patch": patch[0] if isinstance(patch, list) and patch else None,
            }
        )
    resume = diagnostic.get("resume") if isinstance(diagnostic.get("resume"), Mapping) else {}
    return {
        "project_id": None,
        "meta": dict(diagnostic.get("meta", {})) if isinstance(diagnostic.get("meta"), Mapping) else {},
        "summary": {
            "status": resume.get("statut"),
            "score_diagnostic_100": resume.get("score_diagnostic_100"),
            "root_causes_count": len(causes),
            "symptoms_count": resume.get("nb_symptomes", 0),
        },
        "fields": fields,
        "unknowns": {
            "root_causes": causes,
            "symptoms": diagnostic.get("symptomes", []),
            "duplicates": diagnostic.get("doublons", []),
        },
        "alerts": diagnostic.get("alertes_normalisees", []),
        "cao": {
            "available": bool(resume.get("cao_disponible")),
            "solidworks_ready": bool(resume.get("solidworks_ready")),
            "status": STATUS_COMPUTED if resume.get("cao_disponible") else STATUS_MISSING_REQUIRED,
            "reason": None if resume.get("cao_disponible") else "CAO non fermee selon diagnostic JSON.",
        },
        "actions": actions,
        "raw_available": True,
        "diagnostic": diagnostic,
    }


def _normalize_status(value: Any) -> str:
    return normalize_status(value)


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


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
