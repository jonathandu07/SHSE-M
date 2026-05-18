"""
Chemin : frontend/components/moteur_thermique/pieces/cylindre/data_adapter.py
But :
    Adapter les donnees backend de la piece cylindre.
Pourquoi ce fichier existe :
    Les modules de rendu lisent des champs normalises sans connaitre les chemins
    heterogenes des rapports backend.
Donnees consommees :
    Rapport global et rapport de piece issus de frontend/main.py.
Livrables produits :
    Rapport de piece et champs requis normalises.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from frontend.ensemble.piece_data_adapter import extract_field, get_piece_report, require_fields, safe_dict

PIECE_NAME = "cylindre"


def adapter_donnees_piece(global_report: Mapping[str, Any] | None = None, data: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    report = safe_dict(global_report)
    return safe_dict(data) or get_piece_report(report, PIECE_NAME)


def extraire_champ(report: Mapping[str, Any], path: str, *, unit: str | None = None, required: bool = False) -> Dict[str, Any]:
    field = extract_field(report, path, unit=unit)
    field["required"] = bool(required)
    return field


def verifier_champs(report: Mapping[str, Any], fields: Sequence[Mapping[str, Any] | str]) -> Dict[str, Any]:
    return require_fields(report, fields)
