"""
Chemin : frontend/ensemble/STHO_ME.py
But :
    Presenter le rapport systeme STHO-ME deja orchestre par le backend.
Pourquoi ce fichier existe :
    STHO_ME est l'orchestrateur backend central ; ce module frontend sert de
    facade d'affichage et ne duplique aucune orchestration metier.
Donnees consommees :
    meta, synthese, sous_systemes, pieces et liaisons du rapport backend.
Livrables produits :
    Contrat de section JSON-serializable pour GUI ou console.
Limites :
    - ne construit aucun composant ;
    - ne calcule aucune inconnue ;
    - ne produit pas de STEP ;
    - run_demo lance uniquement une demonstration explicite.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_STHO_ME(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("STHO_ME", report, run_demo=run_demo)


def afficher_resultats_STHO_ME(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_STHO_ME(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_STHO_ME(run_demo=True)
