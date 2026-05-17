from __future__ import annotations

"""Services backend appelables par Kivy sans API HTTP."""

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.ensemble.STHO_ME import STHO_ME
from backend.modules.systeme.data_repository import SystemDataRepository
from backend.modules.systeme.frontend_contract import build_diagnostic_contract, build_frontend_contract
from backend.modules.systeme.json_diagnostic import diagnostiquer_json_sthome
from backend.modules.systeme.resolution_inconnues import resoudre_inconnues_systeme


def charger_data_contract(project_id: str, repository: Any | None = None) -> dict:
    repository = repository or SystemDataRepository()
    config = repository.get_project_parameters(project_id)
    rapport = STHO_ME.depuis_config(config).analyser(repository=repository, frontend_contract=True)
    return build_frontend_contract(rapport, project_id=project_id)


def resoudre_inconnues_project(project_id: str, repository: Any | None = None) -> dict:
    repository = repository or SystemDataRepository()
    config = repository.get_project_parameters(project_id)
    rapport = STHO_ME.depuis_config(config).analyser(resolve_unknowns=False, frontend_contract=False)
    result = resoudre_inconnues_systeme(
        config=config,
        rapport=rapport,
        cahier_des_charges=dict(config.get("cahier_des_charges", {})) if isinstance(config, dict) else {},
        repository=repository,
        project_id=project_id,
        recalculer=lambda cfg: STHO_ME.depuis_config(cfg).analyser(resolve_unknowns=False, frontend_contract=False),
    )
    out = result.en_dict()
    final_report = STHO_ME.depuis_config(out.get("config_completee", config)).analyser(repository=repository, frontend_contract=True)
    out["frontend_contract"] = build_frontend_contract(final_report, project_id=project_id)
    return out


def verrouiller_parametres_project(project_id: str, paths: list[str], repository: Any | None = None) -> dict:
    repository = repository or SystemDataRepository()
    params = repository.get_project_parameters(project_id)
    locked: List[str] = []
    for path in paths:
        value = _get_path(params, path)
        if value is not None:
            repository.save_project_parameter(
                project_id=project_id,
                path=path,
                name=path.split(".")[-1],
                value=value,
                source="user_lock",
                status="input",
                locked=True,
                allow_locked_overwrite=True,
            )
            locked.append(path)
    return {"project_id": project_id, "locked": locked, "frontend_contract": charger_data_contract(project_id, repository=repository)}


def recalculer_project(project_id: str, repository: Any | None = None) -> dict:
    repository = repository or SystemDataRepository()
    config = repository.get_project_parameters(project_id)
    return STHO_ME.depuis_config(config).analyser(repository=repository, frontend_contract=True)


def optimiser_project(project_id: str, repository: Any | None = None) -> dict:
    repository = repository or SystemDataRepository()
    config = repository.get_project_parameters(project_id)
    rapport = STHO_ME.depuis_config(config).analyser(repository=repository, optimize=True, frontend_contract=True)
    if hasattr(repository, "save_optimization_run"):
        repository.save_optimization_run(project_id=project_id, run=rapport.get("optimisation", {}))
    return {"rapport": rapport, "frontend_contract": build_frontend_contract(rapport, project_id=project_id)}


def diagnostiquer_json_file(
    path_json: str,
    *,
    repository: Any | None = None,
    project_id: str | None = None,
    strict: bool = True,
) -> dict:
    _ = repository, project_id
    path = Path(path_json).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Le fichier JSON doit contenir un objet racine.")
    return diagnostiquer_json_data(data, source_name=str(path), strict=strict)


def diagnostiquer_json_data(
    data: dict,
    *,
    source_name: str | None = None,
    repository: Any | None = None,
    project_id: str | None = None,
    strict: bool = True,
) -> dict:
    _ = repository, project_id
    diagnostic = diagnostiquer_json_sthome(data=data, source_name=source_name, strict=strict)
    return {
        "diagnostic": diagnostic,
        "frontend_contract": build_diagnostic_contract(diagnostic),
    }


def _get_path(data: Dict[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur
