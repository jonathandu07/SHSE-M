"""
Chemin : frontend/ensemble/dashboard_model.py
But :
    Exposer les modeles dashboard sous un nom explicite.
Pourquoi ce fichier existe :
    Le dashboard GUI doit consommer des modeles prepares, pas fouiller le JSON
    backend. Ce module est la facade dashboard de frontend/ensemble.
Donnees consommées :
    Etat frontend complet issu de frontend/main.py.
Livrables produits :
    Modeles entree de conception, chaine puissance, fermeture mecanique,
    CAO et diagnostic.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from frontend.ensemble.screen_models import (
    build_cao_model,
    build_dashboard_model,
    build_design_input_model,
    build_diagnostic_model,
    build_mechanical_model,
    build_power_chain_model,
)

__all__ = [
    "build_cao_model",
    "build_dashboard_model",
    "build_design_input_model",
    "build_diagnostic_model",
    "build_mechanical_model",
    "build_power_chain_model",
]
