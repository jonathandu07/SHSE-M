"""
Chemin : frontend/ensemble/eau.py
But :
    Presenter la section backend liee a l'eau et au refroidissement.
Pourquoi ce fichier existe :
    Le frontend peut afficher les proprietes de refroidissement deja calculees,
    mais il ne doit pas calculer les proprietes d'eau ni choisir de conditions.
Donnees consommees :
    Sections eau/refroidissement deja presentes dans le rapport backend.
Livrables produits :
    Contrat de section JSON-serializable pour GUI ou console.
Limites :
    - ne calcule pas les proprietes de l'eau ;
    - ne choisit pas temperature/pression ;
    - ne remplace aucune inconnue ;
    - run_demo est uniquement explicite.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_eau(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("eau", report, run_demo=run_demo)


def afficher_resultats_eau(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_eau(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_eau(run_demo=True)
