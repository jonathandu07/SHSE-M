"""
Chemin : frontend/ensemble/actions.py
But :
    Decrire les actions frontend disponibles a partir des sections backend.
Pourquoi ce fichier existe :
    Le GUI doit afficher des boutons sans simuler un service absent et sans
    encoder la logique d'analyse dans chaque ecran.
Donnees consommees :
    Rapport backend, diagnostic, dossier CAO, visualisations.
Livrables produits :
    Liste d'actions passives avec disponibilite et raison.
Limites :
    - ne declenche rien ;
    - ne modifie pas la BDD ;
    - ne valide pas de candidat ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.piece_data_adapter import safe_dict


def lister_actions_frontend(report: Mapping[str, Any]) -> Dict[str, Any]:
    data = safe_dict(report)
    actions = [
        {"id": "charger_donnees", "label": "Charger donnees connues", "available": True, "reason": None},
        {"id": "resoudre_inconnues", "label": "Resoudre inconnues", "available": True, "reason": None},
        {"id": "recalculer", "label": "Recalculer", "available": True, "reason": None},
        {"id": "optimiser", "label": "Optimiser", "available": bool(data.get("optimisation")), "reason": None if data.get("optimisation") else "Optimisation backend absente du rapport courant."},
        {"id": "analyser_json", "label": "Analyser JSON", "available": True, "reason": None},
        {"id": "export_cao_json", "label": "Exporter dossier CAO JSON", "available": bool(data.get("cao_dossier")), "reason": None if data.get("cao_dossier") else "Dossier CAO backend absent."},
    ]
    return {"actions": actions, "source": "frontend.ensemble.actions"}


__all__ = ["lister_actions_frontend"]
