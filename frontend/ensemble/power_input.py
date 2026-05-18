"""
Chemin : frontend/ensemble/power_input.py
But :
    Valider et normaliser la puissance demandee en sortie moteur electrique.
Pourquoi ce fichier existe :
    La saisie kW/ch est une responsabilite frontend, mais elle ne doit pas se
    melanger aux calculs de dimensionnement. Ce module prepare seulement le
    payload strict transmis a frontend.main puis au backend.
Donnees consommees :
    Valeur numerique saisie par l'utilisateur et unite explicite kW/ch/CV.
Livrables produits :
    Payload JSON-serializable contenant l'unite source, la trace de conversion
    d'unite et la configuration backend minimale.
Limites :
    - ne calcule pas la piece ;
    - ne dimensionne aucun sous-systeme ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

import math
from typing import Any, Dict


CH_TO_W = 735.49875
KW_TO_W = 1000.0
SUPPORTED_UNITS = {"kw", "ch", "cv"}


def normaliser_unite_puissance(unit: str | None) -> str:
    """Retourne l'unite publique normalisee, ou leve une erreur explicite."""
    normalized = str(unit or "").strip().lower()
    if normalized == "cv":
        normalized = "ch"
    if normalized not in SUPPORTED_UNITS:
        raise ValueError("Unite puissance invalide : utiliser kW ou ch.")
    return "kW" if normalized == "kw" else "ch"


def valider_puissance_sortie(value: Any, unit: str | None = "kW") -> Dict[str, Any]:
    """Valide la saisie utilisateur sans produire de valeur de dimensionnement."""
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Puissance de sortie invalide : valeur numerique requise.") from exc

    if not math.isfinite(numeric) or numeric <= 0.0:
        raise ValueError("Puissance de sortie invalide : la valeur doit etre strictement positive.")

    public_unit = normaliser_unite_puissance(unit)
    return {
        "value": numeric,
        "unit": public_unit,
        "label": f"{numeric:g} {public_unit}",
        "status": "input",
        "source": "user_input",
    }


def build_design_input_payload(value: Any, unit: str = "kW") -> Dict[str, Any]:
    """
    Prepare le payload backend pour la puissance de sortie moteur electrique.

    La seule conversion effectuee ici est une conversion d'unite traçable :
    ch -> W -> kW. Le dimensionnement physique reste cote backend.
    """
    validated = valider_puissance_sortie(value, unit)
    numeric = float(validated["value"])
    public_unit = str(validated["unit"])

    if public_unit == "kW":
        kw = numeric
        watts = numeric * KW_TO_W
        conversion = "W = kW * 1000"
    else:
        watts = numeric * CH_TO_W
        kw = watts / KW_TO_W
        conversion = "W = ch * 735.49875 ; kW = W / 1000"

    frontend_input = {
        "puissance_sortie": numeric,
        "unite": public_unit,
        "puissance_sortie_kw": kw,
        "puissance_sortie_w": watts,
        "interpretation": "puissance demandee en sortie moteur electrique",
        "status": "input",
        "source": "frontend_power_input",
        "trace": {
            "conversion_unite": conversion,
            "note": "Conversion d'unite uniquement, aucun dimensionnement frontend.",
        },
    }

    backend_config = {
        "puissance_sortie_kw": kw,
        "puissance_sortie_moteur_electrique_kw": kw,
        "puissance_sortie_w": watts,
        "puissance_sortie_moteur_electrique_w": watts,
        "frontend_inputs": frontend_input,
        "meta_frontend": {
            "source": "frontend.ensemble.power_input",
            "unite_saisie": public_unit,
            "valeur_saisie": numeric,
        },
    }

    return {
        "inputs": frontend_input,
        "backend_config": backend_config,
        "warnings": [],
        "errors": [],
    }


__all__ = [
    "CH_TO_W",
    "KW_TO_W",
    "SUPPORTED_UNITS",
    "build_design_input_payload",
    "normaliser_unite_puissance",
    "valider_puissance_sortie",
]
