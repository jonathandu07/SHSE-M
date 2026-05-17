"""
Chemin : frontend/ensemble/backend_bridge.py
But :
    Centraliser l'acces frontend aux rapports deja produits par frontend.main.
Pourquoi ce fichier existe :
    Les modules frontend/ensemble doivent orchestrer l'affichage et l'extraction
    sans lancer un calcul backend cache. Ce bridge fournit un point unique pour
    lire l'etat courant, ou lancer explicitement une demonstration 100 kW.
Donnees consommees :
    frontend.main.get_backend_bridge(), rapports backend bruts, ui_report et
    sections normalisees.
Livrables produits :
    Contrats passifs par module, etats frontend normalises et resumes console.
Limites :
    - ne calcule pas de physique ;
    - ne choisit aucune valeur ;
    - ne remplace aucune inconnue par un defaut ;
    - ne produit pas de STEP ;
    - run_100kw n'est appele qu'en mode demonstration explicite.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Sequence

from frontend.ensemble.piece_data_adapter import get_path, safe_dict, safe_list


MODULE_SECTION_PATHS: dict[str, tuple[str, ...]] = {
    "air": ("air", "fluides.air", "proprietes.air", "sous_systemes.air", "analyses.air"),
    "eau": ("eau", "fluides.eau", "refroidissement.eau", "sous_systemes.eau", "analyses.eau"),
    "carburant": ("carburant", "synthese.carburant", "analyses_composants.moteur_thermique_bilan_carburant"),
    "materiaux": ("materiaux", "materiaux_selectionnes", "synthese.materiaux", "cao_dossier.materiaux"),
    "calcul_stho_me": ("calcul_stho_me", "calculs", "synthese", "liaisons"),
    "strategie_energie": ("strategie_energie", "synthese.strategie_energie", "optimisation.strategie_energie"),
    "resolution_inconnues": ("resolution_inconnues", "inconnues", "hypotheses", "tracabilite.candidats"),
    "optimisation": ("optimisation", "synthese_optimisation", "tracabilite.optimisations"),
    "STHO_ME": ("meta", "synthese", "sous_systemes", "pieces", "liaisons"),
}


def get_reports_from_frontend_main(
    *,
    report: Mapping[str, Any] | None = None,
    run_demo: bool = False,
) -> Dict[str, Any]:
    """Retourne les rapports disponibles sans lancer de calcul, sauf demo explicite."""
    if isinstance(report, Mapping):
        return {"raw_report": dict(report), "ui_report": {}, "state": {}}

    from frontend.main import get_backend_bridge

    bridge = get_backend_bridge()
    if run_demo:
        state = bridge.run_100kw()
    else:
        state = getattr(bridge, "state", {}) or {}

    return {
        "raw_report": safe_dict(getattr(bridge, "raw_report", {})),
        "ui_report": safe_dict(getattr(bridge, "ui_report", {})),
        "state": safe_dict(state),
    }


def run_demo_100kw() -> Dict[str, Any]:
    """Lance explicitement le scenario de demonstration 100 kW."""
    return get_reports_from_frontend_main(run_demo=True)


def _find_raw_section(ui_report: Mapping[str, Any], module_name: str) -> tuple[str | None, Any]:
    needle = str(module_name or "").lower()
    for section in safe_list(ui_report.get("raw_sections")):
        if not isinstance(section, Mapping):
            continue
        key = str(section.get("key") or section.get("title") or "").lower()
        if needle and needle in key:
            return str(section.get("key") or module_name), section.get("data")
    return None, None


def build_module_section_contract(
    module_name: str,
    report: Mapping[str, Any] | None = None,
    *,
    run_demo: bool = False,
    candidate_paths: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Construit un contrat de lecture de section sans creer de donnees."""
    reports = get_reports_from_frontend_main(report=report, run_demo=run_demo)
    raw_report = safe_dict(reports.get("raw_report"))
    ui_report = safe_dict(reports.get("ui_report"))
    paths = tuple(candidate_paths or MODULE_SECTION_PATHS.get(module_name, (module_name,)))

    for path in paths:
        value = get_path(raw_report, path)
        if value is not None:
            return {
                "id": module_name,
                "kind": "ensemble_module",
                "status": "available",
                "source": "backend",
                "backend_paths": [path],
                "data": value,
                "missing_fields": [],
                "warnings": [],
                "actions": [],
                "step_export": False,
                "solidworks_ready": False,
            }

    section_key, section_data = _find_raw_section(ui_report, module_name)
    if section_key is not None:
        return {
            "id": module_name,
            "kind": "ensemble_module",
            "status": "available",
            "source": "backend.ui_report",
            "backend_paths": [f"raw_sections.{section_key}"],
            "data": section_data,
            "missing_fields": [],
            "warnings": [],
            "actions": [],
            "step_export": False,
            "solidworks_ready": False,
        }

    return {
        "id": module_name,
        "kind": "ensemble_module",
        "status": "missing_required",
        "source": "backend",
        "backend_paths": list(paths),
        "data": None,
        "missing_fields": [{"path": path, "reason": "Section backend absente."} for path in paths],
        "warnings": [],
        "actions": ["Charger un rapport backend contenant cette section."],
        "step_export": False,
        "solidworks_ready": False,
    }


def print_module_section_contract(contract: Mapping[str, Any]) -> None:
    """Affiche un contrat de module pour les scripts lances en console."""
    print(f"=== MODULE FRONTEND : {contract.get('id')} ===")
    print(f"Statut : {contract.get('status')}")
    print(f"Source : {contract.get('source')}")
    if contract.get("data") is None:
        print("Aucune donnee backend disponible.")
        for item in safe_list(contract.get("missing_fields"))[:8]:
            if isinstance(item, Mapping):
                print(f"- manquant : {item.get('path')} | {item.get('reason')}")
        return
    print(json.dumps(contract.get("data"), ensure_ascii=False, indent=2)[:4000])


__all__ = [
    "MODULE_SECTION_PATHS",
    "build_module_section_contract",
    "get_reports_from_frontend_main",
    "print_module_section_contract",
    "run_demo_100kw",
]
