"""
Chemin : frontend/ensemble/visualisation_orchestrator.py
But :
    Orchestrer toutes les visualisations techniques frontend.
Pourquoi ce fichier existe :
    Les pages GUI ne doivent pas connaitre chaque script de piece. Elles
    demandent ici la liste des visualisations et un contrat de rendu pour une
    piece ou un composant, construit depuis le rapport backend.
Donnees consommees :
    Rapport backend complet, frontend_contract, cao_dossier, mechanical_graphs.
Livrables produits :
    Tableau des pages de visualisation, contrats de rendu piece/composant/systeme.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, Mapping

from frontend.ensemble.actions import lister_actions_frontend
from frontend.ensemble.cao_adapter import build_cao_frontend_summary
from frontend.ensemble.diagnostic_adapter import build_diagnostic_summary
from frontend.ensemble.graphs_adapter import collect_backend_charts
from frontend.ensemble.piece_data_adapter import (
    component_piece_directories,
    get_backend_graphs,
    get_backend_sketches,
    get_backend_views_3d,
    get_component_report,
    get_piece_report,
    safe_dict,
    safe_list,
)
from frontend.ensemble.render_contract import build_piece_render_contract, empty_render_contract, summarize_contract


_ROOT = Path(__file__).resolve().parents[2]
_COMPONENTS_ROOT = _ROOT / "frontend" / "components"
_BACKEND_COMPONENTS_ROOT = _ROOT / "backend" / "components"


_DANGEROUS_DEFAULT_TOKENS = (
    "default=" + "0.0",
    " or " + "3000",
    " or " + "400",
    " or " + "0.9",
    " or " + "0.08",
    "safe_float(",
)


def _module_name_from_piece_dir(path: Path) -> str | None:
    try:
        rel = path.relative_to(_ROOT).with_suffix("")
    except Exception:
        return None
    main_file = path / f"{path.name}.py"
    if not main_file.exists():
        return None
    return ".".join((*rel.parts, path.name))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""


def _piece_module_flags(path: Path) -> Dict[str, Any]:
    main_file = path / f"{path.name}.py"
    main_text = _read_text(main_file) if main_file.exists() else ""
    all_text = "\n".join(_read_text(item) for item in path.glob("*.py"))
    dangerous_count = sum(all_text.count(token) for token in _DANGEROUS_DEFAULT_TOKENS)
    supports_contract = "def visualiser_piece" in main_text
    return {
        "supports_render_contract": supports_contract,
        "legacy_hidden_demo": (not supports_contract) and (("bridge." + "run_100kw()") in main_text or "get_backend_bridge()" in main_text),
        "imports_backend_class": "from backend." in main_text,
        "dangerous_defaults_count": dangerous_count,
        "docstring_present": main_text.lstrip().startswith('"""'),
    }


def _discover_piece_modules() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for path in component_piece_directories(_COMPONENTS_ROOT):
        family = path.parents[1].name if len(path.parents) > 1 else ""
        module_name = _module_name_from_piece_dir(path)
        flags = _piece_module_flags(path)
        out[path.name] = {
            "piece": path.name,
            "family": family,
            "path": str(path),
            "module": module_name,
            "has_main": bool(module_name),
            "has_sketches": (path / "sketches_2d.py").exists(),
            "has_mesh_3d": (path / "mesh_3d.py").exists(),
            "has_charts": (path / "charts.py").exists(),
            **flags,
        }
    return out


def _discover_backend_pieces() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not _BACKEND_COMPONENTS_ROOT.exists():
        return out
    for pieces_dir in _BACKEND_COMPONENTS_ROOT.glob("*/pieces"):
        if not pieces_dir.is_dir():
            continue
        family = pieces_dir.parent.name
        for file in pieces_dir.glob("*.py"):
            if file.name.startswith("__"):
                continue
            out[file.stem] = {
                "piece": file.stem,
                "family": family,
                "path": str(file),
            }
    return out


def _component_module_name(component_name: str) -> str | None:
    path = _COMPONENTS_ROOT / component_name / f"{component_name}.py"
    if path.exists():
        return f"frontend.components.{component_name}.{component_name}"
    return None


def _component_frontend_flags(component_name: str) -> Dict[str, Any]:
    module_path = _COMPONENTS_ROOT / component_name / f"{component_name}.py"
    text = _read_text(module_path) if module_path.exists() else ""
    return {
        "frontend_present": module_path.exists(),
        "supports_render_contract": "def visualiser_composant" in text,
        "legacy_hidden_demo": ("bridge." + "run_100kw()") in text or "get_backend_bridge()" in text,
        "imports_backend_class": "from backend." in text,
        "dangerous_defaults_count": sum(text.count(token) for token in _DANGEROUS_DEFAULT_TOKENS),
        "module": _component_module_name(component_name),
    }


def _report_piece_names(report: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    for root in ("rapports_pieces", "pieces", "cao_dossier.pieces"):
        block: Any = report
        for part in root.split("."):
            block = block.get(part) if isinstance(block, Mapping) else None
        if isinstance(block, Mapping):
            names.update(str(k).split(".")[-1] for k in block.keys())
    return names


def lister_visualisations_disponibles(report: dict) -> dict:
    """Liste les pieces/composants detectes et leurs livrables possibles."""
    data = safe_dict(report)
    discovered = _discover_piece_modules()
    backend_pieces = _discover_backend_pieces()
    report_names = _report_piece_names(data)
    all_names = sorted(set(discovered) | set(backend_pieces) | report_names)
    pieces: list[dict[str, Any]] = []
    for name in all_names:
        backend_meta = backend_pieces.get(name) or {}
        meta = dict(discovered.get(name) or {"piece": name, "family": backend_meta.get("family") or "backend", "path": None, "module": None})
        piece_report = get_piece_report(data, name)
        graphs = get_backend_graphs(data, name)
        sketches = get_backend_sketches(data, name)
        views = get_backend_views_3d(data, name)
        has_backend_payload = bool(graphs or sketches or views)
        supports_contract = bool(meta.get("supports_render_contract"))
        status = "available" if piece_report and (has_backend_payload or supports_contract) else "partial" if piece_report else "missing_required"
        meta.update(
            {
                "status": status,
                "backend_present": name in backend_pieces,
                "frontend_present": name in discovered,
                "backend_report": bool(piece_report),
                "backend_graphs": len(graphs),
                "backend_sketches": len(sketches),
                "backend_views_3d": len(views),
                "solidworks_ready": False,
                "step_export": False,
            }
        )
        pieces.append(meta)

    components = []
    for name in ("moteur_thermique", "moteur_electrique", "batterie", "alternateur", "boite_crabots", "architecture"):
        comp = get_component_report(data, name)
        flags = _component_frontend_flags("architechture" if name == "architecture" else name)
        components.append(
            {
                "component": name,
                "status": "available" if comp else "missing_required",
                "backend_report": bool(comp),
                "frontend_present": bool(flags.get("frontend_present")),
                "supports_render_contract": bool(flags.get("supports_render_contract")),
                "legacy_hidden_demo": bool(flags.get("legacy_hidden_demo")),
                "imports_backend_class": bool(flags.get("imports_backend_class")),
                "dangerous_defaults_count": int(flags.get("dangerous_defaults_count") or 0),
                "module": flags.get("module"),
                "sketches": False,
                "views_3d": False,
                "charts": bool(get_backend_graphs(data, name)),
            }
        )

    return {
        "schema_version": "1.0",
        "pieces": pieces,
        "components": components,
        "summary": {
            "pieces_total": len(pieces),
            "pieces_with_backend": sum(1 for p in pieces if p.get("backend_report")),
            "pieces_backend_declared": len(backend_pieces),
            "pieces_frontend_declared": len(discovered),
            "pieces_legacy_hidden_demo": sum(1 for p in pieces if p.get("legacy_hidden_demo")),
            "components_total": len(components),
            "components_with_backend": sum(1 for c in components if c.get("backend_report")),
            "step_export": False,
            "solidworks_ready": False,
        },
    }


def construire_visualisation_piece(piece_name: str, report: dict) -> dict:
    """Construit le contrat de rendu d'une piece depuis le rapport backend."""
    data = safe_dict(report)
    discovered = _discover_piece_modules()
    meta = discovered.get(piece_name)
    if meta and meta.get("module"):
        try:
            module = importlib.import_module(str(meta["module"]))
            visualiser = getattr(module, "visualiser_piece", None)
            if callable(visualiser):
                piece_report = get_piece_report(data, piece_name) or data
                return visualiser(data=piece_report, global_report=data)
            if meta.get("legacy_hidden_demo"):
                contract = build_piece_render_contract(piece_name, data)
                contract["status"] = "partial" if get_piece_report(data, piece_name) else "missing_required"
                contract["warnings"].append("Module legacy detecte : demo backend implicite ignoree par l'orchestrateur.")
                contract["actions"].append("Migrer ce module vers visualiser_piece(data=..., global_report=...).")
                return contract
        except Exception as exc:
            contract = build_piece_render_contract(piece_name, data)
            contract["status"] = "error"
            contract["warnings"].append(f"{type(exc).__name__}: {exc}")
            return contract
    return build_piece_render_contract(piece_name, data)


def construire_visualisations_toutes_pieces(report: dict) -> dict:
    inventory = lister_visualisations_disponibles(report)
    contracts = {}
    for row in safe_list(inventory.get("pieces")):
        if isinstance(row, Mapping):
            name = str(row.get("piece") or "")
            if name:
                contracts[name] = construire_visualisation_piece(name, report)
    return {
        "summary": inventory.get("summary", {}),
        "pieces": contracts,
        "cards": [summarize_contract(c) for c in contracts.values()],
    }


def construire_visualisations_composants(report: dict) -> dict:
    data = safe_dict(report)
    out: Dict[str, Any] = {}
    for row in safe_list(lister_visualisations_disponibles(data).get("components")):
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("component") or "")
        comp = get_component_report(data, name)
        module_name = row.get("module")
        if module_name and row.get("supports_render_contract"):
            try:
                module = importlib.import_module(str(module_name))
                visualiser = getattr(module, "visualiser_composant", None)
                if callable(visualiser):
                    out[name] = visualiser(data=comp, global_report=data)
                    continue
            except Exception as exc:
                pass
        contract = empty_render_contract(
            item_id=name,
            kind="component",
            title=name.replace("_", " ").title(),
            status="partial" if comp else "missing_required",
            reason=None if comp else "Rapport backend composant absent.",
        )
        contract["charts"] = get_backend_graphs(data, name)
        contract["solidworks_data"]["step_export"] = False
        contract["solidworks_data"]["solidworks_ready"] = False
        contract["step_export"] = False
        contract["solidworks_ready"] = False
        if row.get("legacy_hidden_demo"):
            contract["warnings"].append("Module composant legacy detecte : demo implicite ignoree.")
        out[name] = contract
    return {"components": out, "cards": [summarize_contract(c) for c in out.values()]}


def analyser_couverture_backend_frontend(report: dict | None = None) -> dict:
    """Compare pieces backend, couches frontend et risques legacy detectes."""
    data = safe_dict(report)
    frontend_pieces = _discover_piece_modules()
    backend_pieces = _discover_backend_pieces()
    names = sorted(set(frontend_pieces) | set(backend_pieces) | _report_piece_names(data))
    rows: list[dict[str, Any]] = []
    for name in names:
        front = frontend_pieces.get(name) or {}
        back = backend_pieces.get(name) or {}
        row = {
            "piece": name,
            "family": front.get("family") or back.get("family") or "backend",
            "backend_present": bool(back),
            "frontend_present": bool(front),
            "backend_report": bool(get_piece_report(data, name)),
            "supports_render_contract": bool(front.get("supports_render_contract")),
            "legacy_hidden_demo": bool(front.get("legacy_hidden_demo")),
            "imports_backend_class": bool(front.get("imports_backend_class")),
            "dangerous_defaults_count": int(front.get("dangerous_defaults_count") or 0),
            "status": "couvert" if front.get("supports_render_contract") else "legacy_a_migrer" if front else "frontend_absent",
        }
        rows.append(row)
    return {
        "pieces": rows,
        "summary": {
            "backend_pieces": sum(1 for row in rows if row["backend_present"]),
            "frontend_pieces": sum(1 for row in rows if row["frontend_present"]),
            "render_contract_supported": sum(1 for row in rows if row["supports_render_contract"]),
            "legacy_hidden_demo": sum(1 for row in rows if row["legacy_hidden_demo"]),
            "dangerous_defaults_files": sum(1 for row in rows if row["dangerous_defaults_count"] > 0),
        },
    }


def construire_tableau_pages_visualisation(report: dict) -> dict:
    inventory = lister_visualisations_disponibles(report)
    data = safe_dict(report)
    pieces_by_family: Dict[str, list[dict[str, Any]]] = {}
    for piece in safe_list(inventory.get("pieces")):
        if not isinstance(piece, Mapping):
            continue
        family = str(piece.get("family") or "backend")
        pieces_by_family.setdefault(family, []).append(dict(piece))

    return {
        "title": "Visualisation technique",
        "system": {
            "power_chain": data.get("validation_chaine_100kw"),
            "strategy": data.get("strategie_energie"),
            "diagnostic": data.get("diagnostic"),
            "diagnostic_summary": build_diagnostic_summary(data),
            "cao_dossier": data.get("cao_dossier"),
            "mechanical_graphs": data.get("mechanical_graphs"),
        },
        "components": inventory.get("components", []),
        "pieces_by_family": pieces_by_family,
        "solidworks": {
            "step_export": False,
            "solidworks_ready": False,
            "cao_dossier": bool(data.get("cao_dossier")),
            "mechanical_graphs": bool(data.get("mechanical_graphs")),
        },
        "cao_summary": build_cao_frontend_summary(data),
        "graphs_summary": collect_backend_charts(data),
        "coverage": analyser_couverture_backend_frontend(data),
        "actions": lister_actions_frontend(data).get("actions", []),
        "summary": inventory.get("summary", {}),
    }


__all__ = [
    "lister_visualisations_disponibles",
    "construire_visualisation_piece",
    "construire_visualisations_toutes_pieces",
    "construire_visualisations_composants",
    "construire_tableau_pages_visualisation",
    "analyser_couverture_backend_frontend",
]
