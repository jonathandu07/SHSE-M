"""Strict bridge from backend component scripts to frontend resource records.

The frontend must not invent sketches, charts, CAD files, 3D models or
technical values. This module only reports real backend capabilities, consumes
data already present in backend reports, or calls a real exporter/generator when
the caller supplies the required inputs.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SCAN_ROOTS: Tuple[Path, ...] = (
    PROJECT_ROOT / "backend" / "components",
    PROJECT_ROOT / "backend" / "ensemble",
)

RESOURCE_TYPES: Tuple[str, ...] = ("sketches", "charts", "three_d", "pdf", "cao", "json")

KEYWORDS_BY_TYPE: Dict[str, Tuple[str, ...]] = {
    "sketches": ("sketch", "croquis", "draw", "dessin", "schema", "figure"),
    "charts": ("chart", "graph", "plot", "cartographie"),
    "three_d": ("three_d", "view_3d", "views_3d", "vue_3d", "mesh_3d", "model_3d", "modele_3d"),
    "pdf": ("pdf",),
    "cao": ("cao", "solidworks"),
    "json": ("exporter_rapport_json", "exporter_json", "export_json", "sauvegarder_conception"),
}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _dedup(items: Iterable[Mapping[str, Any]], keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, ...]] = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        sig = tuple(str(item.get(key, "")) for key in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(dict(item))
    return out


def _module_name_from_path(path: Path) -> str:
    rel = path.resolve().relative_to(PROJECT_ROOT.resolve()).with_suffix("")
    return ".".join(rel.parts)


def _required_args(args: ast.arguments) -> List[str]:
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    required = [
        arg.arg
        for arg, default in zip(positional, defaults)
        if default is None and arg.arg not in {"self", "cls"}
    ]
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is None and arg.arg not in {"self", "cls"}:
            required.append(arg.arg)
    return required


def _all_args(args: ast.arguments) -> List[str]:
    return [
        arg.arg
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
        if arg.arg not in {"self", "cls"}
    ]


def _classify_function(name: str, doc: str, module_path: str) -> Optional[str]:
    text = f"{name} {doc} {module_path}".lower()

    if any(token in name.lower() for token in KEYWORDS_BY_TYPE["json"]):
        return "json"
    if "cartographie" in text:
        return "charts"
    if any(token in name.lower() for token in KEYWORDS_BY_TYPE["charts"]):
        return "charts"
    if any(token in name.lower() for token in KEYWORDS_BY_TYPE["three_d"]):
        return "three_d"
    if any(token in name.lower() for token in KEYWORDS_BY_TYPE["sketches"]):
        return "sketches"
    if "pdf" in name.lower():
        return "pdf"
    if "cao" in name.lower() or "solidworks" in text:
        return "cao"
    return None


def _looks_like_cao_piece_class(cls: ast.ClassDef, module_text: str, module_path: str) -> bool:
    if "/pieces/" not in module_path.replace("\\", "/"):
        return False
    class_text = f"{cls.name} {ast.get_docstring(cls) or ''} {module_text[:2000]}".lower()
    if "cao" not in class_text and "solidworks" not in class_text:
        return False
    return any(isinstance(node, ast.FunctionDef) and node.name == "analyser" for node in cls.body)


def _return_kind(resource_type: str, name: str) -> str:
    low = name.lower()
    if resource_type in {"json", "pdf"} or "export" in low:
        return "path"
    if resource_type in {"cao", "charts"}:
        return "dict"
    if resource_type in {"sketches", "three_d"}:
        return "path | data"
    return "data"


def _resource_record(
    *,
    name: str,
    resource_type: str,
    source: str = "",
    function: str = "",
    status: str = "unavailable",
    path: Optional[str] = None,
    data: Any = None,
    reason: Optional[str] = None,
    required_inputs: Optional[List[str]] = None,
    missing_inputs: Optional[List[str]] = None,
    notes: Optional[List[str]] = None,
    piece: Optional[str] = None,
    backend_module: Optional[str] = None,
    returns: str = "data",
    generator_available: bool = False,
) -> Dict[str, Any]:
    record = {
        "name": str(name),
        "type": resource_type,
        "status": status,
        "source": source or "",
        "function": function or "",
        "path": path if path and Path(path).is_file() else None,
        "data": data,
        "reason": reason,
        "required_inputs": list(required_inputs or []),
        "missing_inputs": list(missing_inputs or []),
        "notes": list(notes or []),
        "piece": piece,
        "backend_module": backend_module or source or "",
        "returns": returns,
        "generator_available": bool(generator_available or (source and function)),
    }

    if record["path"] is None and path:
        record["notes"].append(f"Chemin ignore car le fichier n'existe pas: {Path(path).name}")
    return record


def _mapping_entry(
    *,
    piece: str,
    resource_type: str,
    backend_module: str,
    function: str,
    available: bool,
    required_inputs: List[str],
    returns: str,
    notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "piece": piece,
        "resource_type": resource_type,
        "backend_module": backend_module,
        "function": function,
        "available": bool(available),
        "required_inputs": list(required_inputs),
        "returns": returns,
        "notes": list(notes or []),
    }


def discover_backend_resources() -> Dict[str, Any]:
    """Inspect available backend modules without fabricating capabilities."""

    mappings: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    scanned_files: List[str] = []

    for root in BACKEND_SCAN_ROOTS:
        if not root.exists():
            errors.append({"root": str(root), "reason": "root_absent"})
            continue

        for path in sorted(root.rglob("*.py")):
            scanned_files.append(str(path.relative_to(PROJECT_ROOT)))
            module_name = _module_name_from_path(path)
            module_text = path.read_text(encoding="utf-8", errors="ignore")

            try:
                tree = ast.parse(module_text)
            except SyntaxError as exc:
                errors.append({"module": module_name, "reason": f"syntax_error: {exc}"})
                continue

            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    resource_type = _classify_function(node.name, ast.get_docstring(node) or "", str(path))
                    if resource_type is None:
                        continue
                    mappings.append(
                        _mapping_entry(
                            piece=path.stem,
                            resource_type=resource_type,
                            backend_module=module_name,
                            function=node.name,
                            available=True,
                            required_inputs=_required_args(node.args),
                            returns=_return_kind(resource_type, node.name),
                            notes=["Fonction backend detectee par introspection AST."],
                        )
                    )

                elif isinstance(node, ast.ClassDef) and _looks_like_cao_piece_class(node, module_text, str(path)):
                    analyser = next(
                        child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == "analyser"
                    )
                    mappings.append(
                        _mapping_entry(
                            piece=path.stem,
                            resource_type="cao",
                            backend_module=module_name,
                            function=f"{node.name}.analyser",
                            available=True,
                            required_inputs=_all_args(analyser.args) or ["donnees_piece"],
                            returns="dict",
                            notes=["Analyseur de piece avec bloc CAO/SolidWorks detecte."],
                        )
                    )

    mappings = _dedup(mappings, ("resource_type", "backend_module", "function", "piece"))
    by_type = {rtype: [m for m in mappings if m["resource_type"] == rtype] for rtype in RESOURCE_TYPES}
    unavailable = {
        rtype: (
            None
            if by_type[rtype]
            else f"Aucun generateur backend {rtype} detecte dans backend/components ou backend/ensemble."
        )
        for rtype in RESOURCE_TYPES
    }

    return {
        "scan_roots": [str(root) for root in BACKEND_SCAN_ROOTS],
        "scanned_files": scanned_files,
        "resources": mappings,
        "by_type": by_type,
        "unavailable": unavailable,
        "errors": errors,
    }


def _walk_mappings(root: Any, path: str = "") -> Iterable[Tuple[str, Mapping[str, Any]]]:
    if isinstance(root, Mapping):
        yield path, root
        for key, value in root.items():
            child = f"{path}.{key}" if path else str(key)
            yield from _walk_mappings(value, child)
    elif isinstance(root, list):
        for idx, value in enumerate(root):
            yield from _walk_mappings(value, f"{path}[{idx}]")


def _get_nested(data: Mapping[str, Any], *path: str) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _flatten_unknowns(data: Mapping[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path, node in _walk_mappings(data):
        inconnues = node.get("inconnues")
        if not isinstance(inconnues, Mapping):
            continue
        for category, values in inconnues.items():
            for item in _safe_list(values):
                if isinstance(item, Mapping):
                    rows.append(
                        {
                            "category": str(category),
                            "name": str(item.get("nom") or item.get("champ") or item.get("piece") or ""),
                            "reason": str(item.get("raison") or item.get("detail") or ""),
                            "path": path,
                        }
                    )
                else:
                    rows.append(
                        {
                            "category": str(category),
                            "name": str(item),
                            "reason": "",
                            "path": path,
                        }
                    )
    return _dedup(rows, ("category", "name", "reason", "path"))


def _piece_reports(raw_backend_report: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    report = _safe_dict(raw_backend_report)
    pieces: Dict[str, Dict[str, Any]] = {}

    for key in ("rapports_pieces", "pieces", "piece_reports"):
        block = report.get(key)
        if isinstance(block, Mapping):
            for name, value in block.items():
                if isinstance(value, Mapping):
                    pieces[str(name)] = dict(value)

    inventory = _get_nested(report, "inventaire", "pieces")
    if isinstance(inventory, Mapping):
        for name, value in inventory.items():
            if isinstance(value, Mapping):
                pieces.setdefault(str(name), dict(value))

    construction = report.get("construction_pieces")
    if isinstance(construction, Mapping):
        for name, value in construction.items():
            if isinstance(value, Mapping):
                pieces.setdefault(str(name), dict(value))

    return pieces


def _find_first_key_data(data: Mapping[str, Any], wanted_key: str) -> Tuple[Optional[Any], Optional[str]]:
    for path, node in _walk_mappings(data):
        if wanted_key in node:
            value = node.get(wanted_key)
            if isinstance(value, Mapping) and value:
                return dict(value), f"{path}.{wanted_key}" if path else wanted_key
            if isinstance(value, list) and value:
                return list(value), f"{path}.{wanted_key}" if path else wanted_key
    return None, None


def _find_cao_data(piece_report: Mapping[str, Any]) -> Tuple[Optional[Any], Optional[str]]:
    for path in (
        ("cao",),
        ("dimensions", "cao"),
        ("geometrie", "cao"),
        ("rapport", "cao"),
        ("rapport", "dimensions", "cao"),
        ("rapport", "geometrie", "cao"),
    ):
        value = _get_nested(piece_report, *path)
        if isinstance(value, Mapping) and value:
            return dict(value), ".".join(path)
    return _find_first_key_data(piece_report, "cao")


def _piece_mappings(piece_name: str, inventory: Mapping[str, Any], resource_type: str) -> List[Dict[str, Any]]:
    by_type = _safe_dict(inventory.get("by_type"))
    mappings = [dict(m) for m in _safe_list(by_type.get(resource_type)) if isinstance(m, Mapping)]
    piece_key = piece_name.lower().replace("vilebrequin", "vilbrequin")
    exact_name = [
        m
        for m in mappings
        if str(m.get("piece", "")).lower() in {piece_name.lower(), piece_key}
    ]
    if exact_name:
        return exact_name

    module_matches = [
        m
        for m in mappings
        if str(m.get("backend_module", "")).lower().endswith(f".{piece_key}")
    ]
    return module_matches


def _available_first(items: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rank = {"available": 0, "partial": 1, "error": 2, "unavailable": 3}
    return sorted(
        [dict(item) for item in items],
        key=lambda item: (rank.get(str(item.get("status")), 9), str(item.get("name", ""))),
    )


def _catalog_summary(catalog: Mapping[str, List[Mapping[str, Any]]]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for rtype in RESOURCE_TYPES:
        items = [dict(i) for i in catalog.get(rtype, []) if isinstance(i, Mapping)]
        summary[f"{rtype}_available"] = sum(1 for item in items if item.get("status") == "available")
        summary[f"{rtype}_unavailable"] = sum(1 for item in items if item.get("status") == "unavailable")
        summary[f"{rtype}_partial"] = sum(1 for item in items if item.get("status") == "partial")
        summary[f"{rtype}_error"] = sum(1 for item in items if item.get("status") == "error")
    return summary


def _chart_data_from_report(raw_backend_report: Mapping[str, Any]) -> Tuple[Optional[Any], Optional[str]]:
    for key in ("cartographie_alternateur", "cartographies", "courbes", "series"):
        data, path = _find_first_key_data(raw_backend_report, key)
        if data is not None:
            return data, path
    return None, None


def build_resource_catalog(raw_backend_report: dict) -> dict:
    """Build the UI resource catalog from real backend modules and report data."""

    inventory = discover_backend_resources()
    raw = _safe_dict(raw_backend_report)
    pieces = _piece_reports(raw)
    catalog: Dict[str, List[Dict[str, Any]]] = {rtype: [] for rtype in RESOURCE_TYPES}

    chart_data, chart_path = _chart_data_from_report(raw)
    chart_generators = _safe_list(_safe_dict(inventory.get("by_type")).get("charts"))
    if chart_data is not None:
        catalog["charts"].append(
            _resource_record(
                name="Donnees cartographie backend",
                resource_type="charts",
                status="partial",
                source=f"rapport_backend.{chart_path}",
                data=chart_data,
                reason="Donnees numeriques presentes ; rendu graphique soumis aux statuts et traces backend.",
                notes=["Aucune courbe n'est tracee cote frontend sans contrat graphe valide."],
            )
        )
    elif not chart_generators:
        catalog["charts"].append(
            _resource_record(
                name="Graphiques backend",
                resource_type="charts",
                reason="Graphique indisponible : aucun generateur backend trouve.",
            )
        )
    else:
        for mapping in chart_generators:
            if not isinstance(mapping, Mapping):
                continue
            catalog["charts"].append(
                _resource_record(
                    name=f"Donnees graphique {mapping.get('piece')}",
                    resource_type="charts",
                    source=str(mapping.get("backend_module") or ""),
                    function=str(mapping.get("function") or ""),
                    reason="Generateur de donnees backend detecte, mais donnees requises absentes ou non fournies.",
                    required_inputs=[str(v) for v in _safe_list(mapping.get("required_inputs"))],
                    piece=str(mapping.get("piece") or ""),
                    backend_module=str(mapping.get("backend_module") or ""),
                    returns=str(mapping.get("returns") or "dict"),
                    generator_available=True,
                    notes=["Aucun graphique n'est trace cote frontend."],
                )
            )

    json_generators = [m for m in _safe_list(_safe_dict(inventory.get("by_type")).get("json")) if isinstance(m, Mapping)]
    if json_generators:
        for mapping in json_generators:
            catalog["json"].append(
                _resource_record(
                    name=f"Export JSON {mapping.get('piece')}",
                    resource_type="json",
                    status="partial" if raw else "unavailable",
                    source=str(mapping.get("backend_module") or ""),
                    function=str(mapping.get("function") or ""),
                    reason=(
                        "Generateur backend detecte, aucun fichier genere."
                        if raw
                        else "Generateur backend detecte mais rapport backend absent."
                    ),
                    required_inputs=[str(v) for v in _safe_list(mapping.get("required_inputs"))],
                    notes=[str(v) for v in _safe_list(mapping.get("notes"))],
                    piece=str(mapping.get("piece") or ""),
                    backend_module=str(mapping.get("backend_module") or ""),
                    returns=str(mapping.get("returns") or "path"),
                    generator_available=True,
                )
            )
    else:
        catalog["json"].append(
            _resource_record(
                name="Export JSON backend",
                resource_type="json",
                reason="Aucun export JSON backend detecte.",
            )
        )

    # PDF system export is a real frontend formatter over backend data, not a
    # backend calculator. It remains partial until a file is explicitly created.
    pdf_formatter = importlib.util.find_spec("frontend.gui.pdf_export") is not None
    catalog["pdf"].append(
        _resource_record(
            name="Rapport PDF systeme",
            resource_type="pdf",
            status="partial" if raw and pdf_formatter else "unavailable",
            source="frontend.gui.pdf_export" if pdf_formatter else "",
            function="export_system_report_pdf" if pdf_formatter else "",
            reason=(
                "Module frontend PDF detecte, aucun PDF genere."
                if raw and pdf_formatter
                else "Export PDF indisponible : rapport backend ou module PDF absent."
            ),
            required_inputs=["report", "output_path"],
            generator_available=pdf_formatter,
            notes=["Mise en forme uniquement ; les inconnues backend restent visibles."],
        )
    )

    if not pieces:
        for rtype in ("sketches", "three_d", "cao"):
            catalog[rtype].append(
                _resource_record(
                    name=f"{rtype} pieces",
                    resource_type=rtype,
                    reason="Aucun rapport de piece backend fourni.",
                )
            )

    for piece_name, piece_report in pieces.items():
        unknowns = _flatten_unknowns(piece_report)
        missing_inputs = [u["name"] for u in unknowns if u.get("name")]

        for rtype in ("sketches", "three_d"):
            mappings = _piece_mappings(piece_name, inventory, rtype)
            mapping = mappings[0] if mappings else {}
            catalog[rtype].append(
                _resource_record(
                    name=f"{piece_name} {rtype}",
                    resource_type=rtype,
                    source=str(mapping.get("backend_module") or ""),
                    function=str(mapping.get("function") or ""),
                    reason=(
                        "Generateur backend detecte mais aucune ressource fichier n'a ete produite."
                        if mapping
                        else (
                            "3D indisponible : donnees CAO absentes ou generateur backend absent."
                            if rtype == "three_d"
                            else "Croquis indisponible : aucun generateur backend trouve."
                        )
                    ),
                    required_inputs=[str(v) for v in _safe_list(mapping.get("required_inputs"))],
                    missing_inputs=missing_inputs,
                    piece=piece_name,
                    backend_module=str(mapping.get("backend_module") or ""),
                    returns=str(mapping.get("returns") or "path"),
                    generator_available=bool(mapping),
                )
            )

        cao_data, cao_path = _find_cao_data(piece_report)
        cao_mappings = _piece_mappings(piece_name, inventory, "cao")
        cao_mapping = cao_mappings[0] if cao_mappings else {}
        if cao_data is not None:
            catalog["cao"].append(
                _resource_record(
                    name=f"{piece_name} donnees CAO",
                    resource_type="cao",
                    status="partial",
                    source=f"rapport_backend.rapports_pieces.{piece_name}.{cao_path}",
                    function=str(cao_mapping.get("function") or ""),
                    data=cao_data,
                    piece=piece_name,
                    backend_module=str(cao_mapping.get("backend_module") or ""),
                    returns="dict",
                    generator_available=bool(cao_mapping),
                    reason="Bloc CAO present ; readiness SolidWorks non deduite par le catalogue.",
                    notes=["Bloc CAO present dans le rapport backend, a verifier par le contrat de rendu piece."],
                )
            )
        else:
            catalog["cao"].append(
                _resource_record(
                    name=f"{piece_name} donnees CAO",
                    resource_type="cao",
                    source=str(cao_mapping.get("backend_module") or ""),
                    function=str(cao_mapping.get("function") or ""),
                    reason=(
                        "Donnees CAO absentes du rapport backend ; completer les entrees requises."
                        if cao_mapping
                        else "Donnees CAO absentes ou generateur backend absent."
                    ),
                    required_inputs=[str(v) for v in _safe_list(cao_mapping.get("required_inputs"))],
                    missing_inputs=missing_inputs,
                    piece=piece_name,
                    backend_module=str(cao_mapping.get("backend_module") or ""),
                    returns=str(cao_mapping.get("returns") or "dict"),
                    generator_available=bool(cao_mapping),
                )
            )

    for rtype in RESOURCE_TYPES:
        catalog[rtype] = _available_first(catalog[rtype])

    return {
        "resources": catalog,
        "resource_summary": _catalog_summary(catalog),
        "backend_inventory": inventory,
    }


def get_piece_resources(piece_name: str, raw_backend_report: dict) -> dict:
    """Return available and unavailable resources for a single backend piece."""

    catalog = build_resource_catalog(raw_backend_report).get("resources", {})
    wanted = str(piece_name).lower()
    out: Dict[str, List[Dict[str, Any]]] = {rtype: [] for rtype in RESOURCE_TYPES}
    for rtype in RESOURCE_TYPES:
        for item in _safe_list(catalog.get(rtype)):
            if not isinstance(item, Mapping):
                continue
            if str(item.get("piece", "")).lower() == wanted:
                out[rtype].append(dict(item))
    return out


def _import_function(source: str, function_name: str) -> Any:
    module = importlib.import_module(source)
    target: Any = module
    for part in function_name.split("."):
        target = getattr(target, part)
    return target


def _call_with_known_inputs(fn: Any, inputs: Mapping[str, Any]) -> Tuple[Any, List[str]]:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return fn(**dict(inputs)), []

    kwargs: Dict[str, Any] = {}
    missing: List[str] = []
    accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

    for name, param in sig.parameters.items():
        if name in {"self", "cls"}:
            missing.append(name)
            continue
        if name in inputs and inputs[name] is not None:
            kwargs[name] = inputs[name]
        elif param.default is inspect._empty and param.kind not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            missing.append(name)

    if accepts_var_kw:
        for key, value in inputs.items():
            if key not in kwargs and value is not None:
                kwargs[str(key)] = value

    if missing:
        return None, missing
    return fn(**kwargs), []


def generate_or_load_resource(resource_request: dict, raw_backend_report: dict) -> dict:
    """Call a real generator/exporter, or return a precise unavailable record."""

    request = _safe_dict(resource_request)
    raw = _safe_dict(raw_backend_report)
    rtype = str(request.get("type") or request.get("resource_type") or "").strip()
    name = str(request.get("name") or rtype or "resource")
    piece = str(request.get("piece") or request.get("piece_name") or "").strip()

    if rtype not in RESOURCE_TYPES:
        return _resource_record(name=name, resource_type=rtype or "unknown", status="error", reason="Type de ressource inconnu.")

    if rtype == "cao" and piece:
        piece_report = _piece_reports(raw).get(piece, {})
        cao_data, cao_path = _find_cao_data(piece_report)
        if cao_data is not None:
            return _resource_record(
                name=name,
                resource_type="cao",
                status="partial",
                source=f"rapport_backend.rapports_pieces.{piece}.{cao_path}",
                data=cao_data,
                piece=piece,
                reason="Bloc CAO present ; readiness SolidWorks non deduite par le catalogue.",
                returns="dict",
            )
        return _resource_record(
            name=name,
            resource_type="cao",
            reason="Donnees CAO absentes du rapport backend.",
            piece=piece,
        )

    output_path = request.get("output_path") or request.get("path") or request.get("chemin")
    source = str(request.get("source") or request.get("backend_module") or "")
    function_name = str(request.get("function") or "")

    if rtype == "pdf" and function_name == "export_system_report_pdf":
        if not output_path:
            return _resource_record(
                name=name,
                resource_type="pdf",
                source="frontend.gui.pdf_export",
                function="export_system_report_pdf",
                reason="Chemin de sortie requis pour generer le PDF.",
                required_inputs=["output_path"],
                generator_available=True,
            )
        try:
            from frontend.gui.pdf_export import export_system_report_pdf

            result = export_system_report_pdf(report=raw, output_path=output_path)
            path = Path(result)
            return _resource_record(
                name=name,
                resource_type="pdf",
                status="available" if path.is_file() else "error",
                source="frontend.gui.pdf_export",
                function="export_system_report_pdf",
                path=str(path),
                reason=None if path.is_file() else "Le PDF n'a pas ete cree.",
                generator_available=True,
            )
        except Exception as exc:
            return _resource_record(
                name=name,
                resource_type="pdf",
                status="error",
                source="frontend.gui.pdf_export",
                function="export_system_report_pdf",
                reason=str(exc),
                generator_available=True,
            )

    if not source or not function_name:
        return _resource_record(
            name=name,
            resource_type=rtype,
            reason=f"{rtype} indisponible : aucune fonction backend reelle fournie dans la requete.",
        )

    inputs = _safe_dict(request.get("inputs"))
    if output_path:
        inputs.setdefault("chemin", output_path)
        inputs.setdefault("path", output_path)
        inputs.setdefault("path_json", output_path)
    if raw:
        inputs.setdefault("rapport", raw)
        inputs.setdefault("report", raw)

    try:
        fn = _import_function(source, function_name)
    except Exception as exc:
        return _resource_record(
            name=name,
            resource_type=rtype,
            status="unavailable",
            source=source,
            function=function_name,
            reason=f"Fonction backend introuvable : {exc}",
        )

    try:
        result, missing = _call_with_known_inputs(fn, inputs)
    except Exception as exc:
        return _resource_record(
            name=name,
            resource_type=rtype,
            status="error",
            source=source,
            function=function_name,
            reason=str(exc),
            generator_available=True,
        )

    if missing:
        return _resource_record(
            name=name,
            resource_type=rtype,
            source=source,
            function=function_name,
            reason="Entrees requises absentes.",
            missing_inputs=missing,
            generator_available=True,
        )

    path: Optional[Path] = None
    if isinstance(result, (str, Path)):
        path = Path(result)
    elif output_path:
        path = Path(output_path)

    if path is not None:
        return _resource_record(
            name=name,
            resource_type=rtype,
            status="available" if path.is_file() else "error",
            source=source,
            function=function_name,
            path=str(path),
            reason=None if path.is_file() else "Le backend n'a pas produit de fichier existant.",
            generator_available=True,
        )

    if result is not None:
        return _resource_record(
            name=name,
            resource_type=rtype,
            status="available",
            source=source,
            function=function_name,
            data=result,
            generator_available=True,
        )

    return _resource_record(
        name=name,
        resource_type=rtype,
        source=source,
        function=function_name,
        reason="La fonction backend n'a retourne ni fichier ni donnees.",
        generator_available=True,
    )


def dump_resource_catalog(raw_backend_report: dict, output_path: str | Path) -> Path:
    """Utility exporter for debugging the strict resource catalog."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_resource_catalog(raw_backend_report), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return output
