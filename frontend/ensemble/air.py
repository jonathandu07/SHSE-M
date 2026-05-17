"""
Chemin : frontend/ensemble/air.py
But :
    Presenter la section backend liee a l'air et aux proprietes de fluide.
Pourquoi ce fichier existe :
    Il garde un point d'entree frontend pour le module air sans refaire les
    calculs thermodynamiques et sans lancer un scenario backend cache.
Donnees consommees :
    Sections air/fluides deja produites par backend/main.py ou STHO_ME.
Livrables produits :
    Contrat de section JSON-serializable pour affichage ou console.
Limites :
    - ne calcule pas les proprietes de l'air ;
    - ne choisit aucune valeur atmospherique ;
    - ne remplace pas une donnee absente ;
    - run_demo lance explicitement le scenario 100 kW.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.backend_bridge import build_module_section_contract, print_module_section_contract


def construire_contrat_air(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    return build_module_section_contract("air", report, run_demo=run_demo)


def afficher_resultats_air(report: Mapping[str, Any] | None = None, *, run_demo: bool = False) -> Dict[str, Any]:
    contract = construire_contrat_air(report, run_demo=run_demo)
    print_module_section_contract(contract)
    return contract


if __name__ == "__main__":
    afficher_resultats_air(run_demo=True)
