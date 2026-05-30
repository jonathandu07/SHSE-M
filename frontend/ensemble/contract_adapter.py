"""
Chemin : frontend/ensemble/contract_adapter.py
But :
    Adapter le frontend_contract backend en champs et resumes consommables.
Pourquoi ce fichier existe :
    Les ecrans GUI ne doivent pas fouiller directement dans le JSON brut pour
    retrouver les champs, statuts et blocages.
Donnees consommees :
    rapport.frontend, rapport.frontend_contract et champs backend normalises.
Livrables produits :
    Index de champs, listes de champs bloquants et resume de contrat.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import safe_dict, safe_list

STATUS_INPUT = "input"
STATUS_DATABASE = "database"
STATUS_COMPUTED = "computed"
STATUS_DERIVED = "derived"
STATUS_CONTRAINTE_CDC = "contrainte_cdc"
STATUS_CANDIDATE_FROM_CDC = "candidate_from_cdc"
STATUS_CANDIDATE_FROM_POWER_PROFILE = "candidate_from_power_profile"
STATUS_VALIDATED_BY_OPTIMIZATION = "validated_by_optimization"
STATUS_REJECTED_BY_OPTIMIZATION = "rejected_by_optimization"
STATUS_MISSING_REQUIRED = "missing_required"
STATUS_MISSING_OPTIONAL = "missing_optional"
STATUS_PARTIAL = "partial"
STATUS_IMPOSSIBLE = "impossible"
STATUS_ERROR = "error"

CANONICAL_STATUS_ALIASES = {
    "candidate_generated": STATUS_CANDIDATE_FROM_CDC,
    "generated_from_cahier_des_charges": STATUS_CANDIDATE_FROM_CDC,
    "optimisee": STATUS_CANDIDATE_FROM_CDC,
    "candidate_optimized": STATUS_CANDIDATE_FROM_CDC,
    "candidate_rejected": STATUS_REJECTED_BY_OPTIMIZATION,
    "profil_puissance": STATUS_CANDIDATE_FROM_POWER_PROFILE,
    "optimized": STATUS_PARTIAL,
    "optimise": STATUS_PARTIAL,
    "optimisé": STATUS_PARTIAL,
    "validated": STATUS_PARTIAL,
    "missing": STATUS_MISSING_REQUIRED,
    "partiel": STATUS_PARTIAL,
}

PUBLIC_STATUSES = {
    STATUS_INPUT,
    STATUS_DATABASE,
    STATUS_COMPUTED,
    STATUS_DERIVED,
    STATUS_CONTRAINTE_CDC,
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_CANDIDATE_FROM_POWER_PROFILE,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    STATUS_REJECTED_BY_OPTIMIZATION,
    STATUS_MISSING_REQUIRED,
    STATUS_MISSING_OPTIONAL,
    STATUS_PARTIAL,
    STATUS_IMPOSSIBLE,
    STATUS_ERROR,
}

TRACE_REQUIRED_STATUSES = {STATUS_COMPUTED, STATUS_VALIDATED_BY_OPTIMIZATION}
BLOCKING_STATUSES = {STATUS_MISSING_REQUIRED, STATUS_IMPOSSIBLE, STATUS_ERROR}
CANDIDATE_STATUSES = {STATUS_CANDIDATE_FROM_CDC, STATUS_CANDIDATE_FROM_POWER_PROFILE}


def get_frontend_contract(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    data = safe_dict(report)
    return safe_dict(data.get("frontend_contract")) or safe_dict(data.get("frontend"))


def normalize_contract_status(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return STATUS_PARTIAL
    status = CANONICAL_STATUS_ALIASES.get(raw, raw)
    return status if status in PUBLIC_STATUSES else STATUS_PARTIAL


def field_has_trace(field: Mapping[str, Any]) -> bool:
    trace = field.get("trace") if isinstance(field.get("trace"), Mapping) else {}
    if trace:
        return True
    if field.get("confidence") == "untraced_report_value":
        return False
    for key in ("validation", "validation_trace", "optimization_trace", "dependances", "dependencies"):
        value = field.get(key)
        if isinstance(value, Mapping) and value:
            return True
        if isinstance(value, list) and value:
            return True
    return False


def effective_field_status(field: Mapping[str, Any]) -> str:
    status = normalize_contract_status(field.get("status") or field.get("statut"))
    if field.get("confidence") == "untraced_report_value":
        return STATUS_PARTIAL
    if status in TRACE_REQUIRED_STATUSES and not field_has_trace(field):
        return STATUS_PARTIAL
    return status


def annotate_contract_field(field: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(field)
    raw_status = normalize_contract_status(field.get("status") or field.get("statut"))
    effective_status = effective_field_status(field)
    out["raw_status"] = raw_status
    out["status"] = effective_status
    out["trace_present"] = field_has_trace(field)
    if effective_status != raw_status:
        out.setdefault(
            "display_warning",
            "Statut degrade cote frontend : trace de calcul/validation absente.",
        )
    return out


def index_contract_fields(contract: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for field in safe_list(safe_dict(contract).get("fields")):
        if isinstance(field, Mapping) and field.get("path"):
            out[str(field["path"])] = annotate_contract_field(field)
    return out


def get_contract_field(contract: Mapping[str, Any], path: str) -> Dict[str, Any]:
    return index_contract_fields(contract).get(path, {})


def build_contract_model(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    contract = get_frontend_contract(report)
    fields = [annotate_contract_field(item) for item in safe_list(contract.get("fields")) if isinstance(item, Mapping)]
    blocking = [field for field in fields if field.get("blocking") or field.get("status") in BLOCKING_STATUSES]
    candidates = [field for field in fields if field.get("status") in CANDIDATE_STATUSES]
    untraced = [field for field in fields if field.get("confidence") == "untraced_report_value" or field.get("display_warning")]
    return {
        "contract": contract,
        "fields": fields,
        "fields_by_path": index_contract_fields(contract),
        "blocking_fields": blocking,
        "candidate_fields": candidates,
        "untraced_fields": untraced,
        "summary": {
            "fields_count": len(fields),
            "blocking_count": len(blocking),
            "candidate_count": len(candidates),
            "untraced_count": len(untraced),
            "raw_available": bool(contract),
        },
    }


__all__ = [
    "build_contract_model",
    "annotate_contract_field",
    "effective_field_status",
    "field_has_trace",
    "get_contract_field",
    "get_frontend_contract",
    "index_contract_fields",
    "normalize_contract_status",
]
