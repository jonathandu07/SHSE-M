"""
Chemin : frontend/ensemble/optimisation.py
But :
    Presenter les resultats d'optimisation produits par le backend.
Pourquoi ce fichier existe :
    L'optimisation est le juge final cote backend. Le frontend affiche ses
    scores, traces et rejets sans valider lui-meme un candidat.
Donnees consommees :
    Sections optimisation, synthese_optimisation et tracabilite.optimisations.
Livrables produits :
    Contrat de section JSON-serializable.
Limites :
    - ne lance aucune optimisation cachee ;
    - ne choisit aucune cote ;
    - ne valide aucun candidat ;
    - run_demo est explicite.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_optimisation(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("optimisation", report, run_demo=run_demo)


def afficher_resultats_optimisation(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_optimisation(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_optimisation(run_demo=True)
