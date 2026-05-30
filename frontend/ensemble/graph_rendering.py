"""
Chemin : frontend/ensemble/graph_rendering.py
But :
    Construire des contrats de graphiques depuis les series backend.
Pourquoi ce fichier existe :
    Les graphiques frontend doivent montrer le comportement mecanique/physique
    uniquement quand le backend a deja fourni des points ou series calcules.
Donnees consommees :
    mechanical_graphs, cao_dossier.graphiques et series presentes dans rapports.
Livrables produits :
    Contrats de graphiques JSON-serializable et figures Matplotlib optionnelles.
Limites :
    - ne calcule pas de courbe ;
    - ne genere aucun point ;
    - ne choisit aucun materiau ;
    - ne produit pas de STEP ;
    - la 3D est indicative.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from frontend.ensemble.missing_data import evaluate_chart_readiness
from frontend.ensemble.piece_data_adapter import STATUS_AVAILABLE, STATUS_MISSING_REQUIRED, get_backend_graphs, safe_dict
from frontend.ensemble.render_contract import normalize_chart


_EXPECTED_QUANTITIES: dict[str, tuple[str, ...]] = {
    "piston": ("jeu_radial", "effort_gaz", "force_inertielle", "frottement", "fuite", "contrainte"),
    "cylindre": ("pression", "contrainte_circonferentielle", "von_mises", "ovalisation", "temperature_convection"),
    "bielle": ("effort_axial", "flambage", "contrainte", "pression_petite_grande_tete", "facteur_securite"),
    "arbre_piston": ("flexion", "torsion", "cisaillement", "flambage", "von_mises"),
    "vilebrequin": ("torsion", "flexion", "von_mises", "maneton", "tourillon"),
    "joint_piston": ("squeeze", "pression_contact", "frottement", "fuite"),
    "deplaceur": ("flambage", "perte_charge", "effort_pression", "contrainte"),
    "couvercle_cylindre": ("force_separation", "precharge", "contrainte", "couple_serrage", "convection"),
}


def _profile_for_piece(piece_name: str) -> str:
    low = str(piece_name or "").lower()
    if "joint" in low and "piston" in low:
        return "joint_piston"
    if any(token in low for token in ("vilebrequin", "vilbrequin")):
        return "vilebrequin"
    if "arbre_piston" in low:
        return "arbre_piston"
    if "deplaceur" in low:
        return "deplaceur"
    if "couvercle_cylindre" in low:
        return "couvercle_cylindre"
    if "cylindre" in low:
        return "cylindre"
    if "piston" in low:
        return "piston"
    if "bielle" in low:
        return "bielle"
    return ""


def expected_quantities_for_piece(piece_name: str) -> list[str]:
    return list(_EXPECTED_QUANTITIES.get(_profile_for_piece(piece_name), ()))


def _infer_quantity_family(chart: Mapping[str, Any], expected: list[str]) -> str | None:
    text = " ".join(str(chart.get(key) or "") for key in ("id", "title", "y_label", "x_label")).lower()
    for quantity in expected:
        tokens = [part for part in quantity.split("_") if part]
        if quantity in text or all(token in text for token in tokens[:2]):
            return quantity
    return None


def build_chart_contracts_from_backend(piece_name: str, global_report: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    report = safe_dict(global_report)
    expected = expected_quantities_for_piece(piece_name)
    charts = []
    for item in get_backend_graphs(report, piece_name):
        normalized = normalize_chart(item)
        normalized["render_profile"] = _profile_for_piece(piece_name) or "generic"
        normalized["expected_quantities"] = expected
        family = _infer_quantity_family(normalized, expected)
        if family:
            normalized["quantity_family"] = family
        charts.append(normalized)
    if charts:
        return charts
    return [
        {
            "id": f"{piece_name}_backend_graphs_missing",
            "type": "chart",
            "status": STATUS_MISSING_REQUIRED,
            "title": f"Graphiques backend indisponibles - {piece_name}",
            "render_profile": _profile_for_piece(piece_name) or "generic",
            "expected_quantities": expected,
            "x_label": "",
            "y_label": "",
            "series": [],
            "markers": [],
            "formula": None,
            "source": "backend.mechanical_graphs",
            "interpretation": "Aucune serie de points backend n'est disponible pour cette piece.",
            "missing_fields": [
                {
                    "path": f"mechanical_graphs.graphiques.{quantity}" if quantity else "mechanical_graphs.graphiques",
                    "reason": "Serie de points backend absente pour cette grandeur.",
                }
                for quantity in (expected or [""])
            ],
            "actions": ["Generer les series backend pertinentes pour cette piece."],
        }
    ]


def validate_chart_contracts(charts: list[Mapping[str, Any]]) -> dict[str, Any]:
    return evaluate_chart_readiness(charts)


def build_chart_figure(chart: Mapping[str, Any]) -> Any:
    """Trace uniquement les points deja presents dans le contrat de graphique."""
    import matplotlib.pyplot as plt

    chart_data = safe_dict(chart)
    status = str(chart_data.get("status") or "").lower()
    if status not in {"available", "computed", "derived", "validated_by_optimization"}:
        raise ValueError(f"Graphique indisponible : statut backend {status}.")
    series = chart_data.get("series") or []
    if not series:
        raise ValueError("Graphique indisponible : aucune serie backend.")

    fig, ax = plt.subplots(figsize=(8, 4))
    plotted = False
    for serie in series:
        if not isinstance(serie, Mapping):
            continue
        points = [p for p in (serie.get("points") or []) if isinstance(p, Mapping) and "x" in p and "y" in p]
        if not points:
            continue
        ax.plot([p["x"] for p in points], [p["y"] for p in points], marker="o", label=str(serie.get("name") or "serie"))
        plotted = True
    for marker in chart_data.get("markers") or []:
        if isinstance(marker, Mapping) and "x" in marker and "y" in marker:
            ax.scatter([marker["x"]], [marker["y"]], s=50, label=str(marker.get("name") or "marker"))
    if not plotted:
        raise ValueError("Graphique indisponible : les series backend ne contiennent pas de points x/y.")
    ax.set_title(str(chart_data.get("title") or chart_data.get("id") or "Graphique backend"))
    ax.set_xlabel(str(chart_data.get("x_label") or "x"))
    ax.set_ylabel(str(chart_data.get("y_label") or "y"))
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return fig


__all__ = [
    "build_chart_contracts_from_backend",
    "build_chart_figure",
    "expected_quantities_for_piece",
    "validate_chart_contracts",
]
