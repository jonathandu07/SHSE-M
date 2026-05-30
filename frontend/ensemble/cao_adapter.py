"""
Chemin : frontend/ensemble/cao_adapter.py
But :
    Adapter le dossier de preparation SolidWorks backend en structure frontend passive.
Pourquoi ce fichier existe :
    La preparation SolidWorks frontend sert au redessin et aux vues indicatives.
    Elle ne doit jamais transformer une absence de cote en geometrie exploitable sans avertissement.
Donnees consommees :
    rapport.cao_dossier, rapport.cao, rapport.mechanical_graphs.
Livrables produits :
    Resume CAO progressif : croquis, 3D indicative, graphes, donnees SolidWorks.
Limites :
    - ne calcule aucune cote ;
    - ne produit pas de STEP ;
    - solidworks_ready reste uniquement lu depuis le backend, jamais invente ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import get_path, safe_dict, safe_list


def build_cao_frontend_summary(report: Mapping[str, Any]) -> Dict[str, Any]:
    data = safe_dict(report)
    dossier = safe_dict(data.get("cao_dossier"))
    cao = safe_dict(data.get("cao"))
    croquis = safe_list(dossier.get("croquis_2d"))
    vues = safe_list(dossier.get("vues_3d"))
    graphs = safe_list(get_path(data, "mechanical_graphs.graphiques"))
    missing_for_solidworks = safe_list(cao.get("missing_for_solidworks") or dossier.get("missing_for_solidworks"))
    raw_solidworks_ready = bool(cao.get("solidworks_ready") or dossier.get("solidworks_ready"))
    solidworks_ready = raw_solidworks_ready and not missing_for_solidworks and str(cao.get("status") or "").lower() not in {"partial", "missing_required", "impossible", "error"}

    return {
        "mode": dossier.get("mode") or cao.get("mode") or ("croquis_cotes_et_3d_indicative" if dossier else "indisponible"),
        "step_export": False,
        "solidworks_ready": solidworks_ready,
        "sketches_available": bool(cao.get("sketches_available")) or bool(croquis),
        "views_3d_available": bool(cao.get("views_3d_available")) or bool(vues),
        "stress_graphs_available": bool(cao.get("stress_graphs_available")) or bool(graphs),
        "drawing_data_available": bool(cao.get("drawing_data_available")) or bool(dossier.get("donnees_solidworks") or dossier.get("pieces")),
        "missing_for_solidworks": missing_for_solidworks,
        "missing_for_sketches": safe_list(cao.get("missing_for_sketches") or dossier.get("missing_for_sketches")),
        "missing_for_stress_graphs": safe_list(cao.get("missing_for_stress_graphs") or dossier.get("missing_for_stress_graphs")),
        "source": "backend.cao_dossier" if dossier else "backend.cao",
        "warning": None if solidworks_ready else "Dossier de modelisation incomplet : cotes, interfaces ou validations manquantes.",
    }


__all__ = ["build_cao_frontend_summary"]
