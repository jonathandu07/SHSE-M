"""
Chemin : frontend/ensemble/calcul_stho_me.py
But :
    Presenter les sections de calcul global STHO-ME deja produites par backend.
Pourquoi ce fichier existe :
    Il expose les calculs au frontend sans dupliquer les formules physiques qui
    appartiennent au backend.
Donnees consommees :
    Sections calculs, synthese et liaisons du rapport backend.
Livrables produits :
    Contrat de section JSON-serializable.
Limites :
    - ne calcule aucune puissance, contrainte ou geometrie ;
    - ne choisit aucun point de fonctionnement ;
    - ne remplace aucune inconnue ;
    - run_demo est uniquement explicite.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_calcul_stho_me(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("calcul_stho_me", report, run_demo=run_demo)


def afficher_resultats_calcul_stho_me(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_calcul_stho_me(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_calcul_stho_me(run_demo=True)
