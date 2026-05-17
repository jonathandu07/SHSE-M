from __future__ import annotations

"""Helpers frontend passifs pour le contrat backend.

Ces fonctions formatent et filtrent uniquement les donnees recues. Elles ne
calculent aucune grandeur metier.
"""

from typing import Any, Dict, List, Mapping


STATUS_COLORS = {
    "computed": "success",
    "input": "success",
    "database": "success",
    "derived": "success",
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
    return STATUS_COLORS.get(str(field.get("status")), "warning")


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
    status = field.get("status")
    if status == "candidate_generated":
        return "proposee par le backend"
    if status == "candidate_optimized":
        return "validee par optimisation"
    if status == "candidate_rejected":
        return "rejetee"
    return None

