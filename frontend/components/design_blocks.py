"""
Chemin : frontend/components/design_blocks.py
But :
    Fournir des blocs de rendu technique reutilisables sous forme de contrats.
Pourquoi ce fichier existe :
    frontend/components est la couche de rendu. Ces helpers normalisent les
    cartes techniques consommees par le GUI sans y placer de logique metier.
Donnees consommees :
    Modeles prepares par frontend/ensemble et palette existante du projet.
Livrables produits :
    Contrats JSON-serializable pour badges, cartes techniques, entree puissance,
    chaine puissance, CAO, diagnostic et panneaux de donnees manquantes.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

PALETTE = {
    "BLANC_LUNAIRE": "#F4FEFE",
    "BLEU_FRANCE_WEB": "#091226",
    "ROUGE_SPARTE": "#75161E",
    "GRIGIO_SCURO": "#0A0B0A",
    "NATURAL_GREEN": "#3E5349",
}


def _hex_to_rgba(value: str, alpha: float = 1.0) -> list[float]:
    value = value.strip().lstrip("#")
    return [
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
        alpha,
    ]


COLORS = {
    "BFW": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"]),
    "BL": _hex_to_rgba(PALETTE["BLEU_FRANCE_WEB"]),
    "RS": _hex_to_rgba(PALETTE["ROUGE_SPARTE"]),
    "GS": _hex_to_rgba(PALETTE["GRIGIO_SCURO"]),
    "NG": _hex_to_rgba(PALETTE["NATURAL_GREEN"]),
    "MUTED": _hex_to_rgba(PALETTE["NATURAL_GREEN"], 0.78),
    "BFW_08": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"], 0.08),
    "BFW_35": _hex_to_rgba(PALETTE["BLANC_LUNAIRE"], 0.35),
}


def _rgba(name: str) -> list[float]:
    return [float(v) for v in COLORS.get(name, COLORS["BFW"])]


def status_badge(status: Any) -> Dict[str, Any]:
    low = str(status or "missing_required").lower()
    if low in {"ok", "available", "computed", "database", "derived", "validated_by_optimization", "input"}:
        color = "NG"
    elif low in {"candidate_from_cdc", "candidate_from_power_profile", "candidate", "candidate_optimized", "partial"}:
        color = "BFW_35"
    elif low in {"error", "impossible", "missing_required", "missing", "alerte", "unavailable"}:
        color = "RS"
    else:
        color = "MUTED"
    return {"status": low, "label": low.upper(), "color": _rgba(color)}


def technical_card(
    *,
    title: str,
    status: str = "partial",
    metrics: Sequence[Mapping[str, Any]] | None = None,
    actions: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    return {
        "type": "technical_card",
        "title": title,
        "status": status,
        "badge": status_badge(status),
        "metrics": [dict(item) for item in (metrics or []) if isinstance(item, Mapping)],
        "actions": [dict(item) for item in (actions or []) if isinstance(item, Mapping)],
        "palette": {"background": _rgba("BFW_08"), "text": _rgba("BFW"), "muted": _rgba("MUTED")},
    }


def power_input_card(design_input: Mapping[str, Any]) -> Dict[str, Any]:
    return technical_card(
        title="Puissance demandee en sortie moteur electrique",
        status=str(design_input.get("status") or "missing_required"),
        metrics=[
            {"label": "Valeur saisie", "value": design_input.get("value"), "unit": design_input.get("unit")},
            {"label": "Puissance convertie", "value": design_input.get("kw"), "unit": "kW"},
            {"label": "Source", "value": design_input.get("source"), "unit": ""},
        ],
        actions=[{"label": "Lancer calcul", "target": "dashboard.calculate_power"}],
    )


def power_chain_card(items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return technical_card(title="Chaine puissance", status="available" if items else "missing_required", metrics=items)


def mechanical_closure_card(items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return technical_card(title="Fermeture mecanique", status="available" if items else "missing_required", metrics=items)


def cao_summary_card(items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return technical_card(title="Dossier CAO / SolidWorks", status="partial" if items else "missing_required", metrics=items)


def diagnostic_summary_card(diagnostic: Mapping[str, Any]) -> Dict[str, Any]:
    status = str(diagnostic.get("status") or "missing_required")
    return technical_card(
        title="Diagnostic causal",
        status=status,
        metrics=[
            {"label": "Statut", "value": diagnostic.get("status"), "unit": ""},
            {"label": "Causes racines", "value": diagnostic.get("root_causes_count"), "unit": ""},
            {"label": "Symptomes", "value": diagnostic.get("symptoms_count"), "unit": ""},
        ],
    )


__all__ = [
    "cao_summary_card",
    "diagnostic_summary_card",
    "mechanical_closure_card",
    "power_chain_card",
    "power_input_card",
    "status_badge",
    "technical_card",
]
