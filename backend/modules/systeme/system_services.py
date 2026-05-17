from __future__ import annotations

"""Services backend appelables par Kivy sans API HTTP."""

from typing import Any, Dict, List

from backend.ensemble.STHO_ME import STHO_ME
from backend.modules.systeme.data_repository import SystemDataRepository
from backend.modules.systeme.frontend_contract import build_frontend_contract
from backend.modules.systeme.resolution_inconnues import resoudre_inconnues_systeme


def charger_data_contract(project_id: str) -> dict:
    repository = SystemDataRepository()
    config = repository.get_project_parameters(project_id)
    rapport = STHO_ME.depuis_config(config).analyser(repository=repository, frontend_contract=True)
    return build_frontend_contract(rapport, project_id=project_id)


def resoudre_inconnues_project(project_id: str) -> dict:
    repository = SystemDataRepository()
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
    return result.en_dict()


def verrouiller_parametres_project(project_id: str, paths: list[str]) -> dict:
    repository = SystemDataRepository()
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
            )
            locked.append(path)
    return {"project_id": project_id, "locked": locked}


def recalculer_project(project_id: str) -> dict:
    repository = SystemDataRepository()
    config = repository.get_project_parameters(project_id)
    return STHO_ME.depuis_config(config).analyser(repository=repository, frontend_contract=True)


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

