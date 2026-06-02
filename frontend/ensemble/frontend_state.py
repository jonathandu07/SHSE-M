"""
Chemin : frontend/ensemble/frontend_state.py
But :
    Representer l'etat frontend courant sans logique metier.
Pourquoi ce fichier existe :
    Les pages GUI ont besoin d'un conteneur stable pour les rapports backend, le
    contrat frontend, le diagnostic et le dossier de definition mecanique.
Donnees consommees :
    Etat retourne par frontend.main.FrontendBackendBridge.
Livrables produits :
    Etat JSON-serializable pour les pages de visualisation.
Limites :
    - ne lance aucun calcul ;
    - ne complete aucune inconnue ;
    - ne remplace aucune valeur manquante ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping


@dataclass
class FrontendVisualizationState:
    raw_report: Dict[str, Any] = field(default_factory=dict)
    ui_report: Dict[str, Any] = field(default_factory=dict)
    frontend_contract: Dict[str, Any] = field(default_factory=dict)
    diagnostic: Dict[str, Any] = field(default_factory=dict)
    cao_dossier: Dict[str, Any] = field(default_factory=dict)
    mechanical_graphs: Dict[str, Any] = field(default_factory=dict)
    status: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_frontend_visualization_state(raw_report: Mapping[str, Any], ui_report: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    data = dict(raw_report) if isinstance(raw_report, Mapping) else {}
    state = FrontendVisualizationState(
        raw_report=data,
        ui_report=dict(ui_report) if isinstance(ui_report, Mapping) else {},
        frontend_contract=dict(data.get("frontend_contract") or data.get("frontend") or {}),
        diagnostic=dict(data.get("diagnostic") or {}),
        cao_dossier=dict(data.get("cao_dossier") or {}),
        mechanical_graphs=dict(data.get("mechanical_graphs") or {}),
        status=str(data.get("status") or data.get("statut") or "unknown"),
    )
    return state.to_dict()


__all__ = ["FrontendVisualizationState", "build_frontend_visualization_state"]
