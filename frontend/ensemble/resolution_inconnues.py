"""
Chemin : frontend/ensemble/resolution_inconnues.py
But :
    Presenter les inconnues et hypotheses resolues par le backend.
Pourquoi ce fichier existe :
    Le cockpit doit afficher ce qui est calcule, candidat, rejete ou restant,
    sans completer une inconnue cote frontend.
Donnees consommees :
    Sections resolution_inconnues, inconnues, hypotheses et tracabilite.
Livrables produits :
    Contrat de section JSON-serializable.
Limites :
    - ne resout aucune inconnue ;
    - n'applique aucun patch ;
    - ne valide aucun candidat ;
    - run_demo est seulement explicite.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_resolution_inconnues(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("resolution_inconnues", report, run_demo=run_demo)


def afficher_resultats_resolution_inconnues(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_resolution_inconnues(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_resolution_inconnues(run_demo=True)
