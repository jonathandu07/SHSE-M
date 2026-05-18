"""
Chemin : frontend/ensemble/render_status.py
But :
    Centraliser les statuts de rendu frontend.
Pourquoi ce fichier existe :
    Les ecrans GUI et les composants techniques doivent utiliser les memes
    statuts sans redefinir partout leur logique d'affichage.
Donnees consommees :
    Statuts exposes par les contrats backend et contrats de rendu frontend.
Livrables produits :
    Normalisation de statut, labels, severites et helpers passifs.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any


STATUS_AVAILABLE = "available"
STATUS_PARTIAL = "partial"
STATUS_MISSING_REQUIRED = "missing_required"
STATUS_ERROR = "error"


def normalize_render_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"available", "ok", "computed", "validated_by_optimization", "exploitable_pour_redessin_solidworks"}:
        return STATUS_AVAILABLE
    if text in {"partial", "partiel", "candidate_from_cdc", "pre_dimensionne_partiel", "conceptuel_non_cote"}:
        return STATUS_PARTIAL
    if text in {"error", "impossible"}:
        return STATUS_ERROR
    return STATUS_MISSING_REQUIRED


def render_status_label(value: Any) -> str:
    status = normalize_render_status(value)
    return {
        STATUS_AVAILABLE: "DISPONIBLE",
        STATUS_PARTIAL: "PARTIEL",
        STATUS_MISSING_REQUIRED: "MANQUANT",
        STATUS_ERROR: "ERREUR",
    }[status]


def render_status_blocking(value: Any) -> bool:
    return normalize_render_status(value) in {STATUS_MISSING_REQUIRED, STATUS_ERROR}


__all__ = [
    "STATUS_AVAILABLE",
    "STATUS_ERROR",
    "STATUS_MISSING_REQUIRED",
    "STATUS_PARTIAL",
    "normalize_render_status",
    "render_status_blocking",
    "render_status_label",
]
