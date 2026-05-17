"""
Chemin : frontend/ensemble/strategie_energie.py
But :
    Presenter la strategie energie calculee par le backend.
Pourquoi ce fichier existe :
    Le frontend doit afficher la strategie et ses inconnues sans arbitrer les
    flux batterie/alternateur/moteur thermique.
Donnees consommees :
    Sections strategie_energie, synthese et optimisation du rapport backend.
Livrables produits :
    Contrat de section JSON-serializable.
Limites :
    - ne dimensionne pas la batterie ;
    - ne choisit pas un duty cycle ;
    - ne valide pas de candidat ;
    - run_demo est explicitement demande.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_strategie_energie(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("strategie_energie", report, run_demo=run_demo)


def afficher_resultats_strategie_energie(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_strategie_energie(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_strategie_energie(run_demo=True)
