"""
Chemin : frontend/ensemble/materiaux.py
But :
    Presenter les materiaux fournis ou selectionnes par le backend.
Pourquoi ce fichier existe :
    Les vues frontend doivent indiquer les proprietes materiaux disponibles sans
    choisir un materiau ni inventer de contrainte admissible.
Donnees consommees :
    Sections materiaux, cao_dossier et synthese du rapport backend.
Livrables produits :
    Contrat de section JSON-serializable.
Limites :
    - ne choisit aucun materiau ;
    - ne calcule aucune propriete RDM ;
    - ne valide pas de candidat ;
    - run_demo est explicite.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_materiaux(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("materiaux", report, run_demo=run_demo)


def afficher_resultats_materiaux(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_materiaux(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_materiaux(run_demo=True)
