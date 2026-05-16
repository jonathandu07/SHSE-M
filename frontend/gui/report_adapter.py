"""Adaptateur strict backend -> frontend.

Ce module ne fait aucun calcul physique. Il extrait, classe et présente les
données déjà présentes dans le rapport backend. Une absence reste une absence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_nested(data: Any, path: str, default: Any = None) -> Any:
    if not isinstance(data, dict):
        return default
    cur: Any = data
    for key in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return default
        if cur is None:
            return default
    return cur


def first_present(report: Dict[str, Any], *paths: str) -> tuple[Any, Optional[str]]:
    for path in paths:
        marker = object()
        value = get_nested(report, path, marker)
        if value is not marker:
            return value, path
    return None, None


def _status_from_value(value: Any, explicit_status: Optional[str] = None) -> str:
    if explicit_status:
        return str(explicit_status)
    if value is None:
        return "inconnu"
    return "ok"


def _detail_point(report: Dict[str, Any], detail_key: str) -> Optional[Dict[str, Any]]:
    detail = get_nested(report, f"derivees_chaine_energie.details.{detail_key}")
    return detail if isinstance(detail, dict) else None


def resolve_metric(report: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Résout une métrique technique à partir de plusieurs chemins candidats.

    Règle : prend la première valeur non-None. Ne transforme jamais None en 0.
    """
    first_candidate = candidates[0] if candidates else {}
    label = first_candidate.get("label", "Inconnu")
    unit = first_candidate.get("unit", "")

    for cand in candidates:
        path = cand.get("raw_path")
        if not path:
            continue

        # Extraction de la valeur
        val = get_nested(report, path)

        # Si c'est un dictionnaire de détail (format backend standard)
        if isinstance(val, dict) and "valeur" in val:
            source = val.get("source") or cand.get("source_type", "backend")
            status = val.get("statut") or "ok"
            val = val.get("valeur")
        else:
            source = cand.get("source_type", "backend")
            status = "ok" if val is not None else "missing"

        if val is not None:
            return {
                "label": label,
                "value": val,
                "unit": unit,
                "status": status,
                "source": source,
                "raw_path": path,
                "resolved": True,
            }

    # Si rien n'est résolu
    return {
        "label": label,
        "value": None,
        "unit": unit,
        "status": "missing",
        "source": None,
        "raw_path": candidates[0].get("raw_path") if candidates else None,
        "resolved": False,
        "missing_reason": "Donnée non trouvée dans les chemins backend testés",
        "candidates": [c.get("raw_path") for c in candidates],
    }


def adapt_backend_report(report: Dict[str, Any]) -> Dict[str, Any]:
    if not report:
        return {
            "error": "Rapport vide ou inexistant",
            "is_empty": True,
            "sections": {},
            "dashboard_metrics": [],
            "missing_requirements": [],
            "unknowns": [],
            "alerts": [],
        }

    unknowns = flatten_unknowns(report)
    alerts = flatten_alerts(report)
    pieces = extract_piece_list(report)
    arch_candidates = extract_architecture_candidates(report)
    subsystems = extract_subsystems(report)
    exports = extract_exports(report)
    sketches = extract_visual_resources(report, "sketches")
    charts = extract_visual_resources(report, "charts")
    three_d = extract_visual_resources(report, "three_d")
    editable = extract_editable_parameters(report, arch_candidates)

    # Métriques de synthèse résolues
    dashboard_specs = [
        ("Puissance demandée", [
            {"raw_path": "derivees_chaine_energie.details.sortie_utilisateur_w.valeur", "unit": "W"},
            {"raw_path": "derivees_chaine_energie.sortie_utilisateur_w", "unit": "W"},
            {"raw_path": "entrees.puissance_traction_kw", "unit": "kW"},
        ]),
        ("Architecture", [
            {"raw_path": "resume_gui.Architecture"},
            {"raw_path": "systeme_complet.synthese.architecture.nom"},
        ]),
        ("Nombre de cylindres", [
            {"raw_path": "resume_gui.N_cyl"},
            {"raw_path": "systeme_complet.synthese.moteur_thermique.N_cyl"},
        ]),
        ("Alésage", [
            {"raw_path": "resume_gui.Bore_mm", "unit": "mm"},
            {"raw_path": "systeme_complet.synthese.moteur_thermique.Bore_mm", "unit": "mm"},
        ]),
        ("Course", [
            {"raw_path": "resume_gui.Stroke_mm", "unit": "mm"},
            {"raw_path": "systeme_complet.synthese.moteur_thermique.Stroke_mm", "unit": "mm"},
        ]),
        ("Régime nominal", [
            {"raw_path": "resume_gui.RPM", "unit": "rpm"},
            {"raw_path": "systeme_complet.synthese.moteur_thermique.RPM", "unit": "rpm"},
        ]),
        ("Cylindrée totale", [
            {"raw_path": "resume_gui.vd_tot_cc", "unit": "cc"},
            {"raw_path": "systeme_complet.synthese.moteur_thermique.vd_tot_cc", "unit": "cc"},
        ]),
        ("Score global", [
            {"raw_path": "resume_gui.score_global_100", "unit": "/100"},
        ]),
    ]

    all_metrics = []
    for label, paths in dashboard_specs:
        candidates = []
        for p in paths:
            cand = dict(p) if isinstance(p, dict) else {"raw_path": p}
            if "label" not in cand:
                cand["label"] = label
            candidates.append(cand)
        all_metrics.append(resolve_metric(report, candidates))

    dashboard_metrics = [m for m in all_metrics if m["resolved"]]
    missing_requirements = [m for m in all_metrics if not m["resolved"]]

    # Chaîne énergétique
    energy_specs = [
        ("Cible Traction", [{"raw_path": "entrees.puissance_traction_kw", "unit": "kW"}]),
        ("Mode Énergétique", [{"raw_path": "strategie_energie.mode_energetique"}]),
        ("Puissance Traction", [{"raw_path": "derivees_chaine_energie.details.p_traction_w"}, {"raw_path": "derivees_chaine_energie.sortie_utilisateur_w"}], "W"),
        ("Puissance Bus DC", [{"raw_path": "derivees_chaine_energie.details.p_bus_total"}, {"raw_path": "derivees_chaine_energie.puissance_bus_dc_totale_w"}], "W"),
        ("Recharge Batterie", [{"raw_path": "strategie_energie.bilan_bus_dc.puissance_recharge_retenue_w"}], "W"),
        ("Limitation Batterie", [{"raw_path": "strategie_energie.enveloppe_batterie.raison_limitante"}]),
        ("Puissance auxiliaire", [{"raw_path": "derivees_chaine_energie.puissance_auxiliaire_w"}, {"raw_path": "strategie_energie.bilan_bus_dc.puissance_auxiliaire_w"}], "W"),
        ("Moteur thermique requis", [{"raw_path": "derivees_chaine_energie.puissance_moteur_thermique_requise_w"}, {"raw_path": "strategie_energie.bilan_bus_dc.puissance_moteur_thermique_requise_w"}], "W"),
        ("Rendement global", [{"raw_path": "strategie_energie.bilan_bus_dc.rendement_global_calcule"}]),
    ]
    energy_metrics = []
    for spec in energy_specs:
        label = spec[0]
        paths = spec[1]
        unit = spec[2] if len(spec) > 2 else ""
        cands = []
        for p in paths:
            cand = dict(p) if isinstance(p, dict) else {"raw_path": p}
            if "unit" not in cand:
                cand["unit"] = unit
            cands.append(cand)
        energy_metrics.append(resolve_metric(report, cands))

    ui = {
        "is_empty": False,
        "meta": report.get("meta", {}),
        "summary": {
            "status": "partiel" if unknowns else "ok",
            "unknown_count": len(unknowns),
            "alert_count": len(alerts),
            "architecture": get_nested(report, "resume_gui.Architecture"),
            "mode_energetique": get_nested(report, "strategie_energie.mode_energetique"),
        },
        "dashboard_metrics": dashboard_metrics,
        "resolved_metrics": [m for m in energy_metrics if m["resolved"]],
        "missing_requirements": missing_requirements + [m for m in energy_metrics if not m["resolved"]],
        "sections": {
            "resume": {"title": "Résumé global", "items": dashboard_metrics},
            "energie": {"title": "Chaîne énergétique", "items": [m for m in energy_metrics if m["resolved"]]},
            "sous_systemes": {"title": "Sous-systèmes", "items": subsystem_metrics(subsystems)},
            "exports": {"title": "Exports", "items": [e for e in exports if e["available"]]},
        },
        "energy_chain": energy_metrics,
        "subsystems": subsystems,
        "unknowns": unknowns,
        "alerts": alerts,
        "pieces": pieces,
        "architecture_candidates": arch_candidates,
        "sketches": sketches,
        "charts": charts,
        "three_d": three_d,
        "exports": exports,
        "editable_parameters": editable,
        "technical_audit": build_data_tree(report),
        "raw_available": True,
        "notes": report.get("notes_modele") if isinstance(report.get("notes_modele"), list) else [],
    }
    return ui


def extract_energy_chain(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs = [
        ("Puissance de sortie demandée", ("derivees_chaine_energie.sortie_utilisateur_w",), "W"),
        ("Puissance bus traction", ("derivees_chaine_energie.puissance_elec_usage_w", "strategie_energie.bilan_bus_dc.puissance_electrique_usage_w"), "W"),
        ("Puissance auxiliaire", ("derivees_chaine_energie.puissance_auxiliaire_w", "strategie_energie.bilan_bus_dc.puissance_auxiliaire_w"), "W"),
        ("Puissance recharge batterie", ("derivees_chaine_energie.puissance_recharge_batterie_w", "strategie_energie.bilan_bus_dc.puissance_recharge_retenue_w"), "W"),
        ("Puissance bus totale", ("derivees_chaine_energie.puissance_bus_dc_totale_w", "strategie_energie.bilan_bus_dc.puissance_bus_dc_totale_w"), "W"),
        ("Puissance instantanée beta", ("derivees_chaine_energie.puissance_bus_dc_instantanee_w", "strategie_energie.bilan_bus_dc.puissance_bus_dc_instantanee_w"), "W"),
        ("Alternateur électrique requis", ("strategie_energie.bilan_bus_dc.puissance_alternateur_electrique_requise_w",), "W"),
        ("Alternateur mécanique requis", ("derivees_chaine_energie.puissance_mecanique_alternateur_requise_w", "strategie_energie.bilan_bus_dc.puissance_mecanique_alternateur_requise_w"), "W"),
        ("Moteur thermique requis", ("derivees_chaine_energie.puissance_moteur_thermique_requise_w", "strategie_energie.bilan_bus_dc.puissance_moteur_thermique_requise_w"), "W"),
        ("Rendement global calculé", ("strategie_energie.bilan_bus_dc.rendement_global_calcule",), ""),
    ]
    return [metric_from_paths(report, label, paths, unit) for label, paths, unit in specs]


def extract_subsystems(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs = [
        ("Batterie", "strategie_energie.enveloppe_batterie", "analyses_composants.batterie_dimensionnement"),
        ("Moteur électrique", "analyses_composants.moteur_electrique", "stho_me_secondaire.rapports.composants.moteur_electrique_orchestrateur"),
        ("Alternateur", "analyses_composants.alternateur_bus_dc", "stho_me_secondaire.rapports.composants.alternateur_orchestrateur"),
        ("Boîte / transmission", "analyses_composants.boite_chaine", "stho_me_secondaire.rapports.composants.boite_crabots_orchestrateur"),
        ("Moteur thermique", "systeme_complet.synthese.moteur_thermique", "stho_me_secondaire.synthese.moteur_thermique"),
        ("Architecture", "systeme_complet.synthese.architecture", "stho_me_secondaire.rapports.composants.architecture_orchestrateur"),
        ("Stratégie énergétique", "strategie_energie", "stho_me_secondaire.rapports.strategie_energie"),
    ]
    out: List[Dict[str, Any]] = []
    for name, *paths in specs:
        data = None
        source = None
        for path in paths:
            value = get_nested(report, path)
            if isinstance(value, dict) and value:
                data = value
                source = path
                break
        
        # Filtre les données connues
        resolved_data = {}
        missing_count = 0
        if isinstance(data, dict):
            for k, v in data.items():
                if k in {"inconnues", "alertes", "notes"}:
                    continue
                if v is not None:
                    resolved_data[k] = v
                else:
                    missing_count += 1

        inc = flatten_unknowns(data or {})
        out.append(
            {
                "name": name,
                "status": "partiel" if inc else ("indisponible" if data is None else "ok"),
                "source": source,
                "data": data or {},
                "resolved_data": resolved_data,
                "missing_count": missing_count + len(inc),
                "unknowns": inc,
                "modifiable": name in {"Batterie", "Architecture", "Stratégie énergétique"},
            }
        )
    return out


def subsystem_metrics(subsystems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "label": item["name"],
            "value": item["status"].upper(),
            "unit": "",
            "status": item["status"],
            "source": item.get("source"),
            "raw_path": item.get("source"),
        }
        for item in subsystems
    ]


def flatten_unknowns(report: Dict[str, Any]) -> List[Dict[str, str]]:
    if not isinstance(report, dict):
        return []
    flat: List[Dict[str, str]] = []

    def visit(node: Any, prefix: str = "") -> None:
        if isinstance(node, dict):
            inc = node.get("inconnues")
            if isinstance(inc, dict):
                for category, items in inc.items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                flat.append(
                                    {
                                        "category": str(category),
                                        "name": str(item.get("nom", item.get("champ", "?"))),
                                        "reason": str(item.get("raison", item.get("detail", ""))),
                                        "piece": str(item.get("piece", "")),
                                        "path": prefix,
                                    }
                                )
                            else:
                                flat.append({"category": str(category), "name": str(item), "reason": "INCONNU", "piece": "", "path": prefix})
            for key, value in node.items():
                if key in {"objets_serialises", "toutes_les_donnees_pieces", "toutes_les_donnees_composants"}:
                    continue
                if isinstance(value, dict):
                    visit(value, f"{prefix}.{key}" if prefix else str(key))

    visit(report)
    seen = set()
    deduped = []
    for item in flat:
        sig = (item["category"], item["name"], item["reason"], item["path"])
        if sig not in seen:
            seen.add(sig)
            deduped.append(item)
    return deduped


def flatten_alerts(report: Dict[str, Any]) -> List[Dict[str, str]]:
    if not isinstance(report, dict):
        return []
    flat: List[Dict[str, str]] = []
    alerts = report.get("alertes")
    if isinstance(alerts, dict):
        for category, items in alerts.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        flat.append(
                            {
                                "category": str(category),
                                "name": str(item.get("nom", "?")),
                                "detail": str(item.get("detail", item.get("raison", ""))),
                            }
                        )
                    else:
                        flat.append({"category": str(category), "name": str(item), "detail": "ALERTE"})
    return flat


def extract_architecture_candidates(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    paths = [
        "systeme_complet.synthese.architectures_candidates",
        "systeme_complet.synthese.architecture.candidats",
        "stho_me_secondaire.rapports.composants.architecture_orchestrateur.candidats",
        "stho_me_secondaire.rapports.composants.architecture_orchestrateur.synthese.candidats",
        "optimisation.architectures_candidates",
    ]
    for path in paths:
        candidates = get_nested(report, path)
        if isinstance(candidates, list):
            return [c for c in candidates if isinstance(c, dict)]
    return []


def extract_piece_list(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    reports_pieces = report.get("rapports_pieces") if isinstance(report.get("rapports_pieces"), dict) else {}
    inventory = get_nested(report, "inventaire.pieces", {})
    if not isinstance(inventory, dict):
        inventory = {}

    names = sorted(set(reports_pieces.keys()) | set(inventory.keys()))
    out: List[Dict[str, Any]] = []
    for name in names:
        rep = reports_pieces.get(name) if isinstance(reports_pieces.get(name), dict) else {}
        inv = inventory.get(name) if isinstance(inventory.get(name), dict) else {}
        dims = extract_dimensions(rep)
        unknowns = flatten_unknowns(rep)
        out.append(
            {
                "name": name,
                "type": rep.get("piece") or inv.get("type") or name,
                "status": "partiel" if unknowns else ("ok" if rep else "indisponible"),
                "dimensions": dims,
                "material": first_material(rep),
                "constraints": extract_constraints(rep),
                "unknowns": unknowns,
                "data": rep,
                "pdf_available": bool(rep),
            }
        )
    return out


def extract_dimensions(piece_report: Dict[str, Any]) -> Dict[str, Any]:
    dims: Dict[str, Any] = {}
    for section in ("dimensions", "geometrie", "cao", "resultats", "dimensionnement"):
        block = piece_report.get(section)
        if isinstance(block, dict):
            for key, value in block.items():
                if any(token in str(key).lower() for token in ("m", "mm", "diametre", "longueur", "largeur", "epaisseur", "rayon", "course", "alesage")):
                    dims[str(key)] = value
    return dims


def first_material(piece_report: Dict[str, Any]) -> Any:
    for path in ("materiau", "materiau_cle", "construction.materiau", "entrees.materiau_cle", "donnees.materiau"):
        value = get_nested(piece_report, path)
        if value is not None:
            return value
    return None


def extract_constraints(piece_report: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for section in ("contraintes", "resistance", "efforts", "charges", "securite"):
        block = piece_report.get(section)
        if isinstance(block, dict):
            out.update(block)
    return out


def extract_export_availability(report: Dict[str, Any]) -> Dict[str, Any]:
    exports = extract_exports(report)
    return {item["key"]: item["available"] for item in exports} | {f"{item['key']}_reason": item["reason"] for item in exports}


def extract_exports(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    cao_ready = get_nested(report, "cao.solidworks_ready_detaille")
    pdf_ready = bool(report.get("resume_gui") or report.get("rapports_pieces"))
    json_ready = bool(report)
    pieces_ready = bool(report.get("rapports_pieces"))
    return [
        {"key": "pdf", "label": "PDF global", "available": pdf_ready, "status": "disponible" if pdf_ready else "indisponible", "reason": "" if pdf_ready else "Résumé ou pièces indisponibles."},
        {"key": "pieces_pdf", "label": "PDF pièces", "available": pieces_ready, "status": "disponible" if pieces_ready else "indisponible", "reason": "" if pieces_ready else "Aucun rapport de pièce fourni."},
        {"key": "json", "label": "JSON brut", "available": json_ready, "status": "disponible", "reason": ""},
        {"key": "cao", "label": "CAO / 3D", "available": bool(cao_ready), "status": "disponible" if cao_ready else "indisponible", "reason": get_nested(report, "cao.raison_detaille", "CAO détaillée non fournie.")},
        {"key": "charts", "label": "Graphiques", "available": bool(extract_visual_resources(report, "charts")), "status": "partiel", "reason": "Selon modules et données disponibles."},
    ]


def extract_visual_resources(report: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    pieces = extract_piece_list(report)
    folder = {"sketches": "sketches_2d", "charts": "charts", "three_d": "mesh_3d"}.get(kind, kind)
    resources: List[Dict[str, Any]] = []
    for piece in pieces:
        key = piece["name"].split(".")[-1]
        candidates = [
            PROJECT_ROOT / "frontend" / "components" / "moteur_thermique" / "pieces" / key / f"{folder}.py",
            PROJECT_ROOT / "frontend" / "components" / "moteur_thermique" / "pieces" / key / ("views_3d.py" if kind == "three_d" else f"{folder}.py"),
        ]
        path = next((p for p in candidates if p.exists()), None)
        has_data = bool(piece.get("data"))
        if path is not None or has_data:
            resources.append(
                {
                    "name": piece["name"],
                    "type": kind,
                    "status": "disponible" if path is not None and has_data else "indisponible",
                    "path": str(path) if path is not None else None,
                    "reason": "" if path is not None and has_data else "Module ou données backend indisponibles.",
                }
            )
    return resources


def extract_editable_parameters(report: Dict[str, Any], arch_candidates: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    params = [
        {"key": "puissance_entree", "label": "Puissance demandée", "value": get_nested(report, "entrees.puissance_traction_kw"), "unit": "kW", "source": "entrée utilisateur", "editable": True},
        {"key": "unite_entree", "label": "Unité", "value": get_nested(report, "entrees.unite_entree"), "unit": "", "source": "rapport.entrees.unite_entree", "editable": True},
        {"key": "architecture", "label": "Architecture choisie", "value": get_nested(report, "resume_gui.Architecture"), "unit": "", "source": "backend ou choix utilisateur", "editable": bool(arch_candidates)},
        {"key": "nombre_cylindres", "label": "Nombre de cylindres", "value": get_nested(report, "resume_gui.N_cyl"), "unit": "", "source": "backend", "editable": True},
        {"key": "alesage_mm", "label": "Alésage", "value": get_nested(report, "resume_gui.Bore_mm"), "unit": "mm", "source": "backend", "editable": True},
        {"key": "course_mm", "label": "Course", "value": get_nested(report, "resume_gui.Stroke_mm"), "unit": "mm", "source": "backend", "editable": True},
    ]
    return params


def build_data_tree(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    sections = []
    for key in (
        "meta",
        "entrees",
        "resume_gui",
        "derivees_chaine_energie",
        "strategie_energie",
        "systeme_complet",
        "analyses_composants",
        "construction_pieces",
        "rapports_pieces",
        "cao",
        "optimisation",
        "stho_me_secondaire",
        "inconnues",
        "alertes",
        "notes_modele",
    ):
        value = report.get(key)
        sections.append(
            {
                "name": key,
                "status": "inconnu" if value is None else "ok",
                "value": value,
                "source": f"rapport.{key}",
            }
        )
    return sections


def save_json_report(report: Dict[str, Any], path: str | os.PathLike[str]) -> str:
    import json

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)
