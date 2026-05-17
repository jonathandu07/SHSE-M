from __future__ import annotations

"""Helpers frontend passifs pour le contrat backend.

Ces fonctions formatent et filtrent uniquement les donnees recues. Elles ne
calculent aucune grandeur metier.
"""

from typing import Any, Dict, List, Mapping


CANONICAL_STATUS_ALIASES = {
    "candidate_generated": "candidate_from_cdc",
    "candidate_optimized": "validated_by_optimization",
    "candidate_rejected": "rejected_by_optimization",
    "generated_from_cahier_des_charges": "candidate_from_cdc",
}

STATUS_COLORS = {
    "computed": "success",
    "input": "success",
    "database": "success",
    "derived": "success",
    "contrainte_cdc": "warning",
    "candidate_from_cdc": "warning",
    "validated_by_optimization": "success",
    "rejected_by_optimization": "error",
    "candidate_generated": "warning",
    "candidate_optimized": "success",
    "candidate_rejected": "error",
    "missing_required": "error",
    "missing_optional": "warning",
    "partial": "warning",
    "impossible": "error",
    "error": "error",
}


def format_field(field: Mapping[str, Any]) -> str:
    value = field.get("value")
    unit = field.get("unit")
    if value is None:
        return "indisponible"
    return f"{value} {unit}".strip() if unit else str(value)


def field_color(field: Mapping[str, Any]) -> str:
    return STATUS_COLORS.get(_normalize_status(field.get("status")), "warning")


def is_cao_available(contract: Mapping[str, Any]) -> bool:
    cao = contract.get("cao", {})
    return bool(isinstance(cao, Mapping) and cao.get("available") is True)


def get_missing_required_fields(contract: Mapping[str, Any]) -> List[str]:
    cao = contract.get("cao", {})
    missing = cao.get("missing_required_fields", []) if isinstance(cao, Mapping) else []
    if isinstance(missing, list):
        return [str(x) for x in missing]
    return []


def candidate_label(field: Mapping[str, Any]) -> str | None:
    status = _normalize_status(field.get("status"))
    if status == "candidate_from_cdc":
        return "proposee par le backend"
    if status == "validated_by_optimization":
        return "validee par optimisation"
    if status == "rejected_by_optimization":
        return "rejetee"
    return None


def diagnostic_root_cause_cards(contract: Mapping[str, Any]) -> List[Dict[str, Any]]:
    diagnostic = contract.get("diagnostic")
    if isinstance(diagnostic, Mapping):
        causes = diagnostic.get("causes_racines", [])
    else:
        causes = contract.get("unknowns", {}).get("root_causes", []) if isinstance(contract.get("unknowns"), Mapping) else []
    return [dict(c) for c in causes if isinstance(c, Mapping)]


def diagnostic_patch_is_automatic(patch: Mapping[str, Any]) -> bool:
    return bool(isinstance(patch, Mapping) and patch.get("apply_automatically") is True)


def _normalize_status(value: Any) -> str:
    raw = str(value or "")
    return CANONICAL_STATUS_ALIASES.get(raw, raw)
