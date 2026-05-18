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


def get_frontend_contract(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    data = safe_dict(report)
    return safe_dict(data.get("frontend_contract")) or safe_dict(data.get("frontend"))


def index_contract_fields(contract: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for field in safe_list(safe_dict(contract).get("fields")):
        if isinstance(field, Mapping) and field.get("path"):
            out[str(field["path"])] = dict(field)
    return out


def get_contract_field(contract: Mapping[str, Any], path: str) -> Dict[str, Any]:
    return index_contract_fields(contract).get(path, {})


def build_contract_model(report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    contract = get_frontend_contract(report)
    fields = [dict(item) for item in safe_list(contract.get("fields")) if isinstance(item, Mapping)]
    blocking = [field for field in fields if field.get("blocking") or field.get("status") in {"missing_required", "impossible", "error"}]
    candidates = [field for field in fields if str(field.get("status") or "").startswith("candidate")]
    return {
        "contract": contract,
        "fields": fields,
        "fields_by_path": index_contract_fields(contract),
        "blocking_fields": blocking,
        "candidate_fields": candidates,
        "summary": {
            "fields_count": len(fields),
            "blocking_count": len(blocking),
            "candidate_count": len(candidates),
            "raw_available": bool(contract),
        },
    }


__all__ = [
    "build_contract_model",
    "get_contract_field",
    "get_frontend_contract",
    "index_contract_fields",
]
