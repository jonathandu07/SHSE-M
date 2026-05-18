"""
Chemin : frontend/ensemble/screen_models.py
But :
    Construire les modeles d'ecran consommes par frontend/gui.
Pourquoi ce fichier existe :
    Le GUI doit devenir une couche d'ecrans. Cette couche prepare les donnees
    dashboard, diagnostic, CAO et visualisation a partir de l'etat frontend.
Donnees consommees :
    Etat frontend complet, rapports backend, frontend_contract, diagnostic,
    cao_dossier, mechanical_graphs.
Livrables produits :
    Modeles JSON-serializable pour dashboard, diagnostic, CAO, visualisations
    et rendu de piece.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.components.design_blocks import (
    cao_summary_card,
    diagnostic_summary_card,
    mechanical_closure_card,
    power_chain_card,
    power_input_card,
)
from frontend.ensemble.actions import lister_actions_frontend
from frontend.ensemble.cao_adapter import build_cao_frontend_summary
from frontend.ensemble.contract_adapter import build_contract_model, get_contract_field, get_frontend_contract
from frontend.ensemble.diagnostic_adapter import build_diagnostic_summary
from frontend.ensemble.graphs_adapter import collect_backend_charts
from frontend.ensemble.piece_data_adapter import get_path, safe_dict, safe_list
from frontend.ensemble.visualisation_orchestrator import construire_tableau_pages_visualisation, construire_visualisation_piece


def _report_from_state(frontend_state: Mapping[str, Any] | None) -> Dict[str, Any]:
    state = safe_dict(frontend_state)
    return safe_dict(state.get("raw_report")) or state


def _metric(label: str, value: Any, unit: str = "", status: str | None = None) -> Dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, "status": status or ("missing" if value is None else "ok")}


def _bool_text(value: Any) -> str:
    if value is True:
        return "OUI"
    if value is False:
        return "NON"
    return "-"


def _chain_check(chain_validation: Mapping[str, Any], name: str) -> Dict[str, Any]:
    for item in safe_list(chain_validation.get("checks")):
        if isinstance(item, Mapping) and item.get("name") == name:
            return dict(item)
    return {}


def build_design_input_model(frontend_state: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Expose la puissance utilisateur sans inventer de cible."""
    state = safe_dict(frontend_state)
    report = _report_from_state(frontend_state)
    inputs = safe_dict(state.get("inputs")) or safe_dict(report.get("frontend_inputs"))
    value = inputs.get("puissance_sortie")
    unit = inputs.get("unite")
    return {
        "title": "Entrée de conception",
        "label": "Puissance demandée en sortie moteur électrique",
        "value": value,
        "unit": unit or "kW",
        "kw": inputs.get("puissance_sortie_kw"),
        "watts": inputs.get("puissance_sortie_w"),
        "status": inputs.get("status") or ("input" if value is not None else "missing_required"),
        "source": inputs.get("source") or "user_input",
        "trace": safe_dict(inputs.get("trace")),
        "reason": None if value is not None else "Saisir une puissance de sortie en kW ou ch.",
    }


def build_power_chain_model(frontend_state: Mapping[str, Any] | None) -> list[Dict[str, Any]]:
    report = _report_from_state(frontend_state)
    contract = get_frontend_contract(report)
    chain = safe_dict(report.get("validation_chaine_100kw")) or safe_dict(get_path(report, "frontend.chain_validation"))
    chain_values = safe_dict(chain.get("valeurs"))
    return [
        _metric("Sortie moteur electrique", get_contract_field(contract, "synthese.moteur_electrique.puissance_sortie_w").get("value"), "W"),
        _metric("Bus DC design", get_contract_field(contract, "synthese.systeme.P_bus_dc_design_w").get("value"), "W"),
        _metric("Alternateur electrique", chain_values.get("puissance_alternateur_electrique_w"), "W"),
        _metric("Moteur thermique arbre", chain_values.get("puissance_moteur_thermique_arbre_w"), "W"),
        _metric("Regime thermique", chain_values.get("rpm_moteur_thermique"), "rpm"),
        _metric("Couple thermique", chain_values.get("couple_moteur_thermique_nm"), "Nm"),
        _metric("Score chaine", chain.get("score_chaine_100"), "/100", "ok" if chain.get("ok") else ("alerte" if chain else "missing")),
    ]


def build_mechanical_model(frontend_state: Mapping[str, Any] | None) -> list[Dict[str, Any]]:
    report = _report_from_state(frontend_state)
    chain = safe_dict(report.get("validation_chaine_100kw")) or safe_dict(get_path(report, "frontend.chain_validation"))
    chain_values = safe_dict(chain.get("valeurs"))
    chain_livrables = safe_dict(chain.get("livrables"))
    cao_summary = build_cao_frontend_summary(report)
    graphs = safe_dict(report.get("mechanical_graphs")) or safe_dict(get_frontend_contract(report).get("mechanical_graphs"))
    materials = safe_list(get_path(graphs, "context.materiaux_autorises"))
    boite_check = _chain_check(chain, "boite_reliable")
    couple_check = _chain_check(chain, "couple_moteur_thermique_calculable")
    mechanical_presizing = bool(chain_livrables.get("mechanical_presizing_ok") or cao_summary.get("drawing_data_available"))
    return [
        _metric("Couple connu", _bool_text(couple_check.get("ok") if couple_check else chain_values.get("couple_moteur_thermique_nm") is not None), "", "ok" if (couple_check.get("ok") if couple_check else chain_values.get("couple_moteur_thermique_nm") is not None) else "alerte"),
        _metric("Arbre dimensionnable", _bool_text(mechanical_presizing), "", "ok" if mechanical_presizing else "alerte"),
        _metric("Boite/crabots", _bool_text(boite_check.get("ok")) if boite_check else "-", "", "ok" if boite_check.get("ok") else "alerte"),
        _metric("Alternateur relie", _bool_text(boite_check.get("ok")) if boite_check else "-", "", "ok" if boite_check.get("ok") else "alerte"),
        _metric("Materiaux candidats", ", ".join(str(x) for x in materials[:3]) or None, "", "ok" if materials else "missing"),
        _metric("Graphes mecaniques", graphs.get("graphs_available") or len(safe_list(graphs.get("graphiques"))), "", "ok" if graphs else "alerte"),
    ]


def build_dashboard_model(frontend_state: Mapping[str, Any] | None) -> Dict[str, Any]:
    report = _report_from_state(frontend_state)
    if not report:
        return {"is_empty": True}

    contract = get_frontend_contract(report)
    chain = safe_dict(report.get("validation_chaine_100kw")) or safe_dict(get_path(report, "frontend.chain_validation"))
    diagnostic = safe_dict(report.get("diagnostic")) or safe_dict(contract.get("diagnostic"))
    diagnostic_resume = safe_dict(diagnostic.get("resume"))
    root_causes = [dict(c) for c in safe_list(diagnostic.get("causes_racines")) if isinstance(c, Mapping)]
    cao_source = dict(report)
    if safe_dict(contract.get("cao")):
        cao_source["cao"] = safe_dict(contract.get("cao"))
    if safe_dict(contract.get("cao_dossier")):
        cao_source["cao_dossier"] = safe_dict(contract.get("cao_dossier"))
    cao_summary = build_cao_frontend_summary(cao_source)
    graphs = safe_dict(report.get("mechanical_graphs")) or safe_dict(contract.get("mechanical_graphs"))
    design_input = build_design_input_model(frontend_state)
    power_chain = build_power_chain_model(frontend_state)
    mechanical_closure = build_mechanical_model(frontend_state)

    cao_preconception = [
        _metric("Mode", cao_summary.get("mode"), "", "ok" if cao_summary.get("mode") != "indisponible" else "missing"),
        _metric("Croquis cotes", _bool_text(cao_summary.get("sketches_available")), "", "ok" if cao_summary.get("sketches_available") else "alerte"),
        _metric("3D indicative", _bool_text(cao_summary.get("views_3d_available")), "", "ok" if cao_summary.get("views_3d_available") else "alerte"),
        _metric("Graphiques contraintes", _bool_text(cao_summary.get("stress_graphs_available")), "", "ok" if cao_summary.get("stress_graphs_available") else "alerte"),
        _metric("Donnees SolidWorks", _bool_text(cao_summary.get("drawing_data_available")), "", "ok" if cao_summary.get("drawing_data_available") else "alerte"),
        _metric("SolidWorks ready", _bool_text(cao_summary.get("solidworks_ready")), "", "ok" if cao_summary.get("solidworks_ready") else "alerte"),
        _metric("STEP export", _bool_text(cao_summary.get("step_export")), "", "ok" if cao_summary.get("step_export") else "alerte"),
    ]

    diagnostic_causal = {
        "status": diagnostic_resume.get("statut") or ("bloque" if root_causes else "indisponible"),
        "score": diagnostic_resume.get("score_diagnostic_100"),
        "root_causes_count": diagnostic_resume.get("nb_causes_racines", len(root_causes)),
        "symptoms_count": diagnostic_resume.get("nb_symptomes"),
        "duplicates_count": diagnostic_resume.get("nb_doublons_probables"),
        "root_causes": root_causes[:4],
    }

    dashboard = {
        "title": "STHOME COCKPIT - BACKEND MAIN",
        "summary": {
            "design_input": design_input,
            "chain_validation": {
                "available": bool(chain),
                "ok": bool(chain.get("ok")),
                "score_chaine_100": chain.get("score_chaine_100"),
                "main_blocking_point": safe_list(chain.get("points_bloquants"))[0] if safe_list(chain.get("points_bloquants")) else None,
            },
            "cao_preconception": cao_summary,
        },
        "design_input": design_input,
        "power_chain": power_chain,
        "mechanical_closure": mechanical_closure,
        "cao_preconception": cao_preconception,
        "diagnostic_causal": diagnostic_causal,
        "cards": {
            "design_input": power_input_card(design_input),
            "power_chain": power_chain_card(power_chain),
            "mechanical_closure": mechanical_closure_card(mechanical_closure),
            "cao": cao_summary_card(cao_preconception),
            "diagnostic": diagnostic_summary_card(diagnostic_causal),
        },
        "energy_chain": power_chain,
        "subsystems": [],
        "alerts": [],
        "unknowns": [],
        "actions": lister_actions_frontend(report).get("actions", []),
    }
    return {
        "is_empty": False,
        "dashboard": dashboard,
        "frontend_contract": contract,
        "cao_dossier": safe_dict(report.get("cao_dossier")),
        "mechanical_graphs": graphs,
    }


def build_diagnostic_model(frontend_state: Mapping[str, Any] | None) -> Dict[str, Any]:
    report = _report_from_state(frontend_state)
    diagnostic = safe_dict(report.get("diagnostic"))
    if diagnostic:
        return {"diagnostic": diagnostic, "summary": build_diagnostic_summary(report)}
    summary = build_diagnostic_summary(report)
    return {
        "diagnostic": {
            "meta": {"type_detecte": "inconnu"},
            "resume": {"statut": summary.get("status") or "inconnu", "nb_causes_racines": summary.get("root_cause_count"), "nb_symptomes": summary.get("symptom_count")},
            "causes_racines": summary.get("causes_racines", []),
            "symptomes": summary.get("symptomes", []),
            "patchs_proposes": summary.get("patchs_proposes", []),
            "notes": [],
        },
        "summary": summary,
    }


def build_cao_model(frontend_state: Mapping[str, Any] | None) -> Dict[str, Any]:
    report = _report_from_state(frontend_state)
    contract = get_frontend_contract(report)
    cao_source = dict(report)
    if safe_dict(contract.get("cao")):
        cao_source["cao"] = safe_dict(contract.get("cao"))
    if safe_dict(contract.get("cao_dossier")):
        cao_source["cao_dossier"] = safe_dict(contract.get("cao_dossier"))
    return {
        "cao": safe_dict(contract.get("cao")) or safe_dict(report.get("cao")),
        "cao_dossier": safe_dict(contract.get("cao_dossier")) or safe_dict(report.get("cao_dossier")),
        "mechanical_graphs": safe_dict(contract.get("mechanical_graphs")) or safe_dict(report.get("mechanical_graphs")),
        "summary": build_cao_frontend_summary(cao_source),
        "graphs_summary": collect_backend_charts(report),
    }


def build_visualisation_model(frontend_state: Mapping[str, Any] | None) -> Dict[str, Any]:
    report = _report_from_state(frontend_state)
    table = construire_tableau_pages_visualisation(report)
    return {
        "title": "VISUALISATION TECHNIQUE",
        "table": table,
        "summary": table.get("summary", {}),
        "system": table.get("system", {}),
        "components": table.get("components", []),
        "pieces_by_family": table.get("pieces_by_family", {}),
        "solidworks": table.get("solidworks", {}),
        "coverage": table.get("coverage", {}),
        "actions": table.get("actions", []),
    }


def build_piece_render_model(piece_name: str, frontend_state: Mapping[str, Any] | None) -> Dict[str, Any]:
    report = _report_from_state(frontend_state)
    return construire_visualisation_piece(piece_name, report)


__all__ = [
    "build_cao_model",
    "build_dashboard_model",
    "build_design_input_model",
    "build_diagnostic_model",
    "build_mechanical_model",
    "build_piece_render_model",
    "build_power_chain_model",
    "build_visualisation_model",
]
