from __future__ import annotations

"""Statuts publics normalises pour les donnees STHO-ME.

Le backend peut conserver des libelles internes historiques, mais tout ce qui
sort vers le contrat frontend doit passer par ces statuts.
"""

from typing import Any


STATUS_INPUT = "input"
STATUS_DATABASE = "database"
STATUS_COMPUTED = "computed"
STATUS_DERIVED = "derived"
STATUS_CONTRAINTE_CDC = "contrainte_cdc"
STATUS_CANDIDATE_FROM_CDC = "candidate_from_cdc"
STATUS_VALIDATED_BY_OPTIMIZATION = "validated_by_optimization"
STATUS_REJECTED_BY_OPTIMIZATION = "rejected_by_optimization"
STATUS_MISSING_REQUIRED = "missing_required"
STATUS_MISSING_OPTIONAL = "missing_optional"
STATUS_PARTIAL = "partial"
STATUS_IMPOSSIBLE = "impossible"
STATUS_ERROR = "error"

SOURCE_CDC = "generated_from_cahier_des_charges"

ALLOWED_STATUSES = {
    STATUS_INPUT,
    STATUS_DATABASE,
    STATUS_COMPUTED,
    STATUS_DERIVED,
    STATUS_CONTRAINTE_CDC,
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    STATUS_REJECTED_BY_OPTIMIZATION,
    STATUS_MISSING_REQUIRED,
    STATUS_MISSING_OPTIONAL,
    STATUS_PARTIAL,
    STATUS_IMPOSSIBLE,
    STATUS_ERROR,
}

LEGACY_STATUS_MAP = {
    "calculable": STATUS_COMPUTED,
    "calculee": STATUS_COMPUTED,
    "calcule": STATUS_COMPUTED,
    "deduite": STATUS_DERIVED,
    "deduit": STATUS_DERIVED,
    # Libelles historiques ambigus : une optimisation proposee n'est pas une
    # validation tant que le recalcul ne l'a pas marquee explicitement.
    "optimisee": STATUS_CANDIDATE_FROM_CDC,
    "candidate_generated": STATUS_CANDIDATE_FROM_CDC,
    "candidate_optimized": STATUS_CANDIDATE_FROM_CDC,
    "candidate_rejected": STATUS_REJECTED_BY_OPTIMIZATION,
    "generated_from_cahier_des_charges": STATUS_CANDIDATE_FROM_CDC,
    "materiau": STATUS_DATABASE,
    "bdd": STATUS_DATABASE,
    "db": STATUS_DATABASE,
    "missing": STATUS_MISSING_REQUIRED,
    "alerte": STATUS_PARTIAL,
    "erreur": STATUS_ERROR,
}


def normalize_status(value: Any, *, default: str = STATUS_PARTIAL) -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    status = LEGACY_STATUS_MAP.get(raw, raw)
    return status if status in ALLOWED_STATUSES else default


def is_candidate_status(value: Any) -> bool:
    return normalize_status(value) in {
        STATUS_CANDIDATE_FROM_CDC,
        STATUS_VALIDATED_BY_OPTIMIZATION,
        STATUS_REJECTED_BY_OPTIMIZATION,
    }


def is_validated_status(value: Any) -> bool:
    return normalize_status(value) in {
        STATUS_INPUT,
        STATUS_DATABASE,
        STATUS_COMPUTED,
        STATUS_DERIVED,
        STATUS_CONTRAINTE_CDC,
        STATUS_VALIDATED_BY_OPTIMIZATION,
    }
