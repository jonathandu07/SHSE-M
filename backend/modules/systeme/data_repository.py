from __future__ import annotations

"""Repository de donnees systeme.

Ce module lit/ecrit des donnees techniques connues. Il ne calcule rien et ne
choisit aucune valeur.
"""

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class SystemDataRepository:
    def __init__(self, db_path: str | None = None, adapter: Any | None = None):
        self.adapter = adapter
        base = Path(__file__).resolve().parents[2]
        self.db_path = Path(db_path).resolve() if db_path else (base / "system_data_repository.json")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_project_parameter(self, project_id: str, path: str) -> Any | None:
        if self.adapter is not None and hasattr(self.adapter, "get_project_parameter"):
            return self.adapter.get_project_parameter(project_id, path)
        data = self.get_project_parameters(project_id)
        record = _get_path(data, path)
        if isinstance(record, Mapping) and "value" in record:
            return record.get("value")
        return record

    def get_project_parameters(self, project_id: str) -> dict:
        if self.adapter is not None and hasattr(self.adapter, "get_project_parameters"):
            value = self.adapter.get_project_parameters(project_id)
            return dict(value) if isinstance(value, Mapping) else {}
        data = self._load_json()
        project = data.get(project_id, {})
        return dict(project.get("parameters", {})) if isinstance(project, Mapping) else {}

    def save_project_parameter(
        self,
        *,
        project_id: str,
        path: str,
        name: str,
        value: Any,
        unit: str | None = None,
        source: str,
        status: str,
        locked: bool = False,
        metadata: dict | None = None,
    ) -> None:
        if self.adapter is not None and hasattr(self.adapter, "save_project_parameter"):
            self.adapter.save_project_parameter(
                project_id=project_id,
                path=path,
                name=name,
                value=value,
                unit=unit,
                source=source,
                status=status,
                locked=locked,
                metadata=metadata,
            )
            return
        if not source or not status:
            raise ValueError("source et status sont obligatoires pour tracer la donnee.")
        data = self._load_json()
        project = data.setdefault(project_id, {})
        parameters = project.setdefault("parameters", {})
        _set_path(
            parameters,
            path,
            {
                "name": name,
                "value": _jsonable(value),
                "unit": unit,
                "source": source,
                "status": status,
                "locked": bool(locked),
                "metadata": _jsonable(metadata or {}),
            },
        )
        self._save_json(data)

    def save_generated_candidate(self, *, project_id: str, candidate: Any) -> None:
        if self.adapter is not None and hasattr(self.adapter, "save_generated_candidate"):
            self.adapter.save_generated_candidate(project_id=project_id, candidate=candidate)
            return
        data = self._load_json()
        project = data.setdefault(project_id, {})
        project.setdefault("candidates", []).append(_jsonable(candidate))
        self._save_json(data)

    def save_optimization_run(self, *, project_id: str, run: Mapping[str, Any]) -> None:
        if self.adapter is not None and hasattr(self.adapter, "save_optimization_run"):
            self.adapter.save_optimization_run(project_id=project_id, run=run)
            return
        data = self._load_json()
        project = data.setdefault(project_id, {})
        project.setdefault("optimization_runs", []).append(_jsonable(run))
        self._save_json(data)

    def _load_json(self) -> Dict[str, Any]:
        if not self.db_path.exists():
            return {}
        try:
            value = json.loads(self.db_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError as exc:
            raise ValueError(f"Repository JSON invalide: {self.db_path}") from exc

    def _save_json(self, data: Mapping[str, Any]) -> None:
        self.db_path.write_text(json.dumps(_jsonable(data), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


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


def _set_path(data: Dict[str, Any], path: str, value: Any) -> None:
    parts = [p for p in path.split(".") if p]
    if not parts:
        raise ValueError("path obligatoire")
    cur = data
    for part in parts[:-1]:
        node = cur.get(part)
        if not isinstance(node, dict):
            node = {}
            cur[part] = node
        cur = node
    cur[parts[-1]] = value


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value

