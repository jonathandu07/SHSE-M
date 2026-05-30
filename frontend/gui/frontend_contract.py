from __future__ import annotations

"""Helpers frontend passifs pour le contrat backend.

Ces fonctions formatent et filtrent uniquement les donnees recues. Elles ne
calculent aucune grandeur metier.
"""

from typing import Any, Dict, List, Mapping

from frontend.ensemble.contract_adapter import (
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_CANDIDATE_FROM_POWER_PROFILE,
    STATUS_COMPUTED,
    STATUS_MISSING_OPTIONAL,
    STATUS_MISSING_REQUIRED,
    STATUS_PARTIAL,
    STATUS_REJECTED_BY_OPTIMIZATION,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    annotate_contract_field,
    effective_field_status,
    field_has_trace,
    normalize_contract_status,
)

CANONICAL_STATUS_ALIASES = {
    "candidate_generated": "candidate_from_cdc",
    "candidate_optimized": "candidate_from_cdc",
    "candidate_rejected": "rejected_by_optimization",
    "generated_from_cahier_des_charges": "candidate_from_cdc",
    "optimisee": "candidate_from_cdc",
    "optimisé": "partial",
    "optimized": "partial",
    "validated": "partial",
}

STATUS_COLORS = {
    "computed": "success",
    "input": "success",
    "database": "success",
    "derived": "success",
    "contrainte_cdc": "warning",
    "candidate_from_cdc": "warning",
    "candidate_from_power_profile": "warning",
    "validated_by_optimization": "success",
    "rejected_by_optimization": "error",
    "candidate_generated": "warning",
    "candidate_optimized": "warning",
    "candidate_rejected": "error",
    "missing_required": "error",
    "missing_optional": "warning",
    "partial": "warning",
    "impossible": "error",
    "error": "error",
}


def format_field(field: Mapping[str, Any]) -> str:
    return format_field_value(field)


def get_field(contract: Mapping[str, Any], path: str) -> Dict[str, Any] | None:
    """Retourne le champ contractuel exact, sans chercher dans le JSON brut."""
    if not isinstance(contract, Mapping):
        return None
    fields = contract.get("fields", [])
    if not isinstance(fields, list):
        return None
    for field in fields:
        if isinstance(field, Mapping) and field.get("path") == path:
            return annotate_contract_field(field)
    return None


def get_field_value(contract: Mapping[str, Any], path: str) -> Any:
    field = get_field(contract, path)
    return field.get("value") if field else None


def get_field_status(contract: Mapping[str, Any], path: str) -> str | None:
    field = get_field(contract, path)
    return effective_field_status(field) if field else None


def format_field_value(field: Mapping[str, Any]) -> str:
    value = field.get("value")
    unit = field.get("unit")
    if value is None:
        return "INCONNU"
    return f"{value} {unit}".strip() if unit else str(value)


def field_color(field: Mapping[str, Any]) -> str:
    return field_badge_color(field)


def is_field_blocking(field: Mapping[str, Any]) -> bool:
    if not isinstance(field, Mapping):
        return False
    status = effective_field_status(field)
    return bool(field.get("blocking")) or status in {"missing_required", "impossible", "error"}


def is_field_editable(field: Mapping[str, Any]) -> bool:
    if not isinstance(field, Mapping):
        return False
    status = effective_field_status(field)
    trace = field.get("trace") if isinstance(field.get("trace"), Mapping) else {}
    locked = bool(field.get("locked") or trace.get("locked") or field.get("database_locked"))
    if locked:
        return False
    return bool(field.get("editable")) or status in {"candidate_from_cdc", "candidate_from_power_profile"}


def field_badge_label(field: Mapping[str, Any]) -> str:
    status = effective_field_status(field)
    labels = {
        "computed": "calcule",
        "input": "saisi",
        "database": "bdd",
        "derived": "deduit",
        "contrainte_cdc": "contrainte cdc",
        "candidate_from_cdc": "candidat backend",
        "candidate_from_power_profile": "hypothese predim",
        "validated_by_optimization": "valide optimisation",
        "rejected_by_optimization": "rejete optimisation",
        "missing_required": "bloquant",
        "missing_optional": "optionnel",
        "partial": "partiel",
        "impossible": "impossible",
        "error": "erreur",
    }
    return labels.get(status, status or "inconnu")


def field_badge_color(field: Mapping[str, Any]) -> str:
    return STATUS_COLORS.get(effective_field_status(field), "warning")


def is_cao_available(contract: Mapping[str, Any]) -> bool:
    cao = contract.get("cao", {})
    return bool(isinstance(cao, Mapping) and cao.get("available") is True)


def is_real_solidworks_available(contract: Mapping[str, Any]) -> bool:
    """Compatibilite historique : dossier utilisable, sans generation STEP."""
    cao = contract.get("cao", {}) if isinstance(contract, Mapping) else {}
    if not isinstance(cao, Mapping):
        return False
    return bool(cao.get("available") and cao.get("solidworks_ready") and not cao.get("step_export"))


def is_step_export_available(contract: Mapping[str, Any]) -> bool:
    cao = contract.get("cao", {}) if isinstance(contract, Mapping) else {}
    return bool(isinstance(cao, Mapping) and cao.get("step_export") is True)


def is_manual_modeling_dossier_available(contract: Mapping[str, Any]) -> bool:
    """Retourne vrai seulement pour un dossier de modelisation backend explicite."""
    return is_real_solidworks_available(contract)


def get_missing_required_fields(contract: Mapping[str, Any]) -> List[str]:
    cao = contract.get("cao", {})
    missing = cao.get("missing_required_fields", []) if isinstance(cao, Mapping) else []
    if isinstance(missing, list):
        return [str(x) for x in missing]
    return []


def candidate_label(field: Mapping[str, Any]) -> str | None:
    status = effective_field_status(field)
    if status == "candidate_from_cdc":
        return "proposee par le backend"
    if status == "candidate_from_power_profile":
        return "hypothese de pre-dimensionnement"
    if status == "validated_by_optimization":
        return "validee par optimisation"
    if status == "rejected_by_optimization":
        return "rejetee"
    return None


def contract_fields_by_status(contract: Mapping[str, Any], status: str) -> List[Dict[str, Any]]:
    normalized = _normalize_status(status)
    fields = contract.get("fields", []) if isinstance(contract, Mapping) else []
    return [
        annotate_contract_field(field)
        for field in fields
        if isinstance(field, Mapping) and effective_field_status(field) == normalized
    ]


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
    return normalize_contract_status(CANONICAL_STATUS_ALIASES.get(str(value or "").strip().lower(), value))
