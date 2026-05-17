"""
Chemin : frontend/ensemble/carburant.py
But :
    Presenter le bilan carburant calcule par le backend.
Pourquoi ce fichier existe :
    Le cockpit doit afficher le carburant impose ou evalue par le backend sans
    selectionner lui-meme une valeur typique.
Donnees consommees :
    Sections carburant et bilan moteur thermique du rapport backend.
Livrables produits :
    Contrat de section JSON-serializable.
Limites :
    - ne choisit aucun carburant ;
    - ne calcule pas PCI/AFR ;
    - ne remplace aucune inconnue ;
    - run_demo est seulement un mode console explicite.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_carburant(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("carburant", report, run_demo=run_demo)


def afficher_resultats_carburant(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_carburant(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_carburant(run_demo=True)
