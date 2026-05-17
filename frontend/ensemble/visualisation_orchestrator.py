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

from frontend.ensemble.piece_data_adapter import (
    component_piece_directories,
    get_backend_graphs,
    get_component_report,
    get_piece_report,
    safe_dict,
    safe_list,
)
from frontend.ensemble.render_contract import build_piece_render_contract, empty_render_contract, summarize_contract


_ROOT = Path(__file__).resolve().parents[2]
_COMPONENTS_ROOT = _ROOT / "frontend" / "components"


def _module_name_from_piece_dir(path: Path) -> str | None:
    try:
        rel = path.relative_to(_ROOT).with_suffix("")
    except Exception:
        return None
    main_file = path / f"{path.name}.py"
    if not main_file.exists():
        return None
    return ".".join((*rel.parts, path.name))


def _discover_piece_modules() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for path in component_piece_directories(_COMPONENTS_ROOT):
        family = path.parents[1].name if len(path.parents) > 1 else ""
        module_name = _module_name_from_piece_dir(path)
        out[path.name] = {
            "piece": path.name,
            "family": family,
            "path": str(path),
            "module": module_name,
            "has_main": bool(module_name),
            "has_sketches": (path / "sketches_2d.py").exists(),
            "has_mesh_3d": (path / "mesh_3d.py").exists(),
            "has_charts": (path / "charts.py").exists(),
        }
    return out


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
    report_names = _report_piece_names(data)
    all_names = sorted(set(discovered) | report_names)
    pieces: list[dict[str, Any]] = []
    for name in all_names:
        meta = dict(discovered.get(name) or {"piece": name, "family": "backend", "path": None, "module": None})
        piece_report = get_piece_report(data, name)
        graphs = get_backend_graphs(data, name)
        status = "available" if piece_report and (graphs or meta.get("has_sketches") or meta.get("has_mesh_3d")) else "partial" if piece_report else "missing_required"
        meta.update(
            {
                "status": status,
                "backend_report": bool(piece_report),
                "backend_graphs": len(graphs),
                "solidworks_ready": False,
                "step_export": False,
            }
        )
        pieces.append(meta)

    components = []
    for name in ("moteur_thermique", "moteur_electrique", "batterie", "alternateur", "boite_crabots", "architecture"):
        comp = get_component_report(data, name)
        components.append(
            {
                "component": name,
                "status": "available" if comp else "missing_required",
                "backend_report": bool(comp),
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
        out[name] = contract
    return {"components": out, "cards": [summarize_contract(c) for c in out.values()]}


def construire_tableau_pages_visualisation(report: dict) -> dict:
    inventory = lister_visualisations_disponibles(report)
    pieces_by_family: Dict[str, list[dict[str, Any]]] = {}
    for piece in safe_list(inventory.get("pieces")):
        if not isinstance(piece, Mapping):
            continue
        family = str(piece.get("family") or "backend")
        pieces_by_family.setdefault(family, []).append(dict(piece))

    return {
        "title": "Visualisation technique",
        "system": {
            "power_chain": safe_dict(report).get("validation_chaine_100kw"),
            "strategy": safe_dict(report).get("strategie_energie"),
            "diagnostic": safe_dict(report).get("diagnostic"),
            "cao_dossier": safe_dict(report).get("cao_dossier"),
        },
        "components": inventory.get("components", []),
        "pieces_by_family": pieces_by_family,
        "solidworks": {
            "step_export": False,
            "solidworks_ready": False,
            "cao_dossier": bool(safe_dict(report).get("cao_dossier")),
            "mechanical_graphs": bool(safe_dict(report).get("mechanical_graphs")),
        },
        "summary": inventory.get("summary", {}),
    }


__all__ = [
    "lister_visualisations_disponibles",
    "construire_visualisation_piece",
    "construire_visualisations_toutes_pieces",
    "construire_visualisations_composants",
    "construire_tableau_pages_visualisation",
]

