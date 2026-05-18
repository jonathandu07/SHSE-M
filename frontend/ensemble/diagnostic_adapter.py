"""
Chemin : frontend/ensemble/diagnostic_adapter.py
But :
    Adapter le diagnostic causal backend pour les pages frontend.
Pourquoi ce fichier existe :
    Le GUI doit afficher les causes racines avant les symptomes sans analyser le
    JSON brut lui-meme.
Donnees consommees :
    rapport.diagnostic ou frontend.diagnostic.
Livrables produits :
    Cartes de causes racines, symptomes, patchs non appliques.
Limites :
    - ne resout aucune inconnue ;
    - n'applique aucun patch ;
    - ne modifie pas la BDD ;
    - ne masque pas les causes restantes.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import get_path, safe_dict, safe_list


def build_diagnostic_summary(report: Mapping[str, Any]) -> Dict[str, Any]:
    data = safe_dict(report)
    diagnostic = safe_dict(data.get("diagnostic") or get_path(data, "frontend.diagnostic"))
    causes = [dict(item) for item in safe_list(diagnostic.get("causes_racines")) if isinstance(item, Mapping)]
    symptoms = [dict(item) for item in safe_list(diagnostic.get("symptomes")) if isinstance(item, Mapping)]
    patches = [dict(item) for item in safe_list(diagnostic.get("patchs_proposes")) if isinstance(item, Mapping)]
    return {
        "status": diagnostic.get("resume", {}).get("statut") if isinstance(diagnostic.get("resume"), Mapping) else diagnostic.get("status"),
        "causes_racines": causes,
        "symptomes": symptoms,
        "patchs_proposes": patches,
        "root_cause_count": len(causes),
        "symptom_count": len(symptoms),
        "patches_are_automatic": False,
        "source": "backend.diagnostic" if diagnostic else "missing",
    }


def diagnostiquer_frontend_data(data: Mapping[str, Any], *, source_name: str = "frontend.app", strict: bool = True) -> Dict[str, Any]:
    """Appelle le service backend de diagnostic depuis la couche ensemble."""
    if not isinstance(data, Mapping) or not data:
        return {
            "diagnostic": {
                "meta": {"type_detecte": "inconnu"},
                "resume": {"statut": "bloque", "score_diagnostic_100": 0, "nb_causes_racines": 0, "nb_symptomes": 0},
                "causes_racines": [],
                "symptomes": [],
                "patchs_proposes": [],
                "notes": ["Aucun JSON backend disponible en memoire."],
            }
        }
    try:
        from backend.modules.systeme.system_services import diagnostiquer_json_data

        return diagnostiquer_json_data(dict(data), source_name=source_name, strict=strict)
    except Exception as exc:
        return {
            "diagnostic": {
                "meta": {"type_detecte": "inconnu"},
                "resume": {"statut": "bloque", "score_diagnostic_100": 0, "nb_causes_racines": 0, "nb_symptomes": 0},
                "causes_racines": [],
                "symptomes": [],
                "patchs_proposes": [],
                "notes": [f"Diagnostic indisponible: {exc}"],
            }
        }


__all__ = ["build_diagnostic_summary", "diagnostiquer_frontend_data"]
