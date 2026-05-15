"""SHSE-M Report Adapter
Normalizes backend reports for the Kivy UI.
Single Source of Truth for frontend data.
"""

from typing import Any, Dict, List, Optional, Union

def get_nested(data: Any, path: str, default: Any = None) -> Any:
    """Safely retrieves a value from a nested dict using a dot-separated path."""
    if not isinstance(data, dict):
        return default
    keys = path.split(".")
    curr = data
    for k in keys:
        if isinstance(curr, dict):
            curr = curr.get(k)
        else:
            return default
    return curr

def make_data_point(report: Dict[str, Any], path: str, label: str, unit: str = "", source: str = "backend") -> Dict[str, Any]:
    """Creates a normalized UI data point from a backend report path."""
    val = get_nested(report, path)
    return {
        "label": label,
        "value": val,
        "unit": unit,
        "status": "ok" if val is not None else "inconnu",
        "source": source,
        "raw_path": path
    }

def adapt_backend_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms a raw backend report into a structured UI report.
    No physics calculations performed here.
    """
    if not report:
        return {"error": "Rapport vide ou inexistant"}

    ui = {
        "sections": {},
        "unknowns": flatten_unknowns(report),
        "alerts": flatten_alerts(report),
        "meta": report.get("meta", {}),
        "is_empty": False
    }

    # 1. Résumé Global (Bento Section A)
    ui["sections"]["resume"] = {
        "title": "Résumé Global",
        "items": [
            make_data_point(report, "resume_gui.Architecture", "Architecture"),
            make_data_point(report, "resume_gui.N_cyl", "Nombre de cylindres"),
            make_data_point(report, "resume_gui.Bore_mm", "Alésage", "mm"),
            make_data_point(report, "resume_gui.Stroke_mm", "Course", "mm"),
            make_data_point(report, "resume_gui.RPM", "Régime nominal", "rpm"),
            make_data_point(report, "resume_gui.vd_tot_cc", "Cylindrée totale", "cc"),
            make_data_point(report, "resume_gui.masse_totale_kg", "Masse estimée", "kg"),
        ]
    }

    # 2. Chaîne Énergétique (Bento Section B)
    # Check both strategie_energie and derivees_chaine_energie
    ui["sections"]["energie"] = {
        "title": "Chaîne Énergétique",
        "items": [
            make_data_point(report, "entrees.puissance_traction_kw", "Cible Traction", "kW"),
            make_data_point(report, "strategie_energie.mode_energetique", "Mode Énergétique"),
            make_data_point(report, "derivees_chaine_energie.details.p_traction_w", "Puissance Traction", "W"),
            make_data_point(report, "derivees_chaine_energie.details.p_bus_total", "Puissance Bus DC", "W"),
            make_data_point(report, "strategie_energie.bilan_bus_dc.puissance_recharge_retenue_w", "Recharge Batterie", "W"),
            make_data_point(report, "strategie_energie.enveloppe_batterie.raison_limitante", "Limitation Batterie"),
        ]
    }

    # 3. Sous-systèmes (Bento Section C)
    ui["sections"]["sous_systemes"] = {
        "title": "Sous-systèmes",
        "items": [
            make_data_point(report, "resume_gui.P_bus_dc_design_w", "Alternateur (Design)", "W"),
            make_data_point(report, "resume_gui.energie_batterie_kwh", "Batterie (Utile)", "kWh"),
            make_data_point(report, "resume_gui.couple_moyen_Nm", "Couple Moyen", "Nm"),
            make_data_point(report, "resume_gui.Force_bielle_N", "Force Bielle Max", "N"),
            make_data_point(report, "resume_gui.Pmax_Pa", "Pression Max (Pmax)", "Pa"),
        ]
    }

    # 4. État d'Export (Bento Section D)
    exports = extract_export_availability(report)
    ui["sections"]["exports"] = {
        "title": "Disponibilité des Exports",
        "items": [
            {"label": "Dossier PDF", "status": "disponible" if exports.get("pdf") else "indisponible", "reason": exports.get("pdf_reason")},
            {"label": "Modèle SolidWorks", "status": "disponible" if exports.get("cao") else "indisponible", "reason": exports.get("cao_reason")},
            {"label": "Tableur Excel", "status": "disponible" if exports.get("excel") else "indisponible", "reason": exports.get("excel_reason")},
        ]
    }

    return ui

def flatten_unknowns(report: Dict[str, Any]) -> List[Dict[str, str]]:
    """Collects all unknowns from the report."""
    raw_unknowns = report.get("inconnues", {})
    if not isinstance(raw_unknowns, dict):
        return []
    
    flat = []
    for cat, items in raw_unknowns.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    flat.append({
                        "category": cat,
                        "name": item.get("nom", item.get("champ", "?")),
                        "reason": item.get("raison", ""),
                        "piece": item.get("piece", "")
                    })
                else:
                    flat.append({"category": cat, "name": str(item), "reason": "Inconnu"})
    return flat

def flatten_alerts(report: Dict[str, Any]) -> List[Dict[str, str]]:
    """Collects all alerts/warnings from the report."""
    raw_alerts = report.get("alertes", {})
    if not isinstance(raw_alerts, dict):
        return []
    
    flat = []
    for cat, items in raw_alerts.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    flat.append({
                        "category": cat,
                        "name": item.get("nom", "?"),
                        "detail": item.get("detail", item.get("raison", ""))
                    })
                else:
                    flat.append({"category": cat, "name": str(item), "detail": "Alerte"})
    return flat

def extract_architecture_candidates(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts valid architecture candidates from the report."""
    # Look for candidates in systeme_complet.synthese or elsewhere if backend provides them
    # For now, if no candidates are provided, return an empty list (Zero Invention)
    candidates = get_nested(report, "systeme_complet.synthese.architectures_candidates")
    if not isinstance(candidates, list):
        return []
    return candidates

def extract_piece_list(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extracts the list of pieces with their status."""
    pieces_data = report.get("pieces", {})
    reports_pieces = report.get("rapports_pieces", {})
    
    piece_list = []
    if not isinstance(pieces_data, dict):
        return []

    for name, obj in pieces_data.items():
        if obj is not None:
            piece_report = reports_pieces.get(name, {})
            piece_list.append({
                "name": name,
                "type": type(obj).__name__ if hasattr(obj, "__class__") else "Pièce",
                "data": piece_report,
                "status": "ok"
            })
    return piece_list

def extract_export_availability(report: Dict[str, Any]) -> Dict[str, Any]:
    """Determines what exports are possible based on data presence."""
    cao_ready = get_nested(report, "cao.solidworks_ready_detaille", False)
    cao_reason = get_nested(report, "cao.raison_detaille", "Données géométriques incomplètes.")
    
    # PDF is usually ready if there is at least a summary
    pdf_ready = report.get("resume_gui") is not None
    pdf_reason = "Résumé indisponible." if not pdf_ready else ""

    return {
        "cao": cao_ready,
        "cao_reason": cao_reason if not cao_ready else "Prêt pour export détaillé.",
        "pdf": pdf_ready,
        "pdf_reason": pdf_reason,
        "excel": pdf_ready, # Simplified for now
        "excel_reason": pdf_reason
    }
