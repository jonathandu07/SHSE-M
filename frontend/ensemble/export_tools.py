"""
Chemin : frontend/ensemble/export_tools.py
But :
    Fournir des exports frontend de contrats deja construits.
Pourquoi ce fichier existe :
    Le cockpit doit pouvoir exporter un contrat JSON ou une figure deja produite
    sans recalculer ni modifier les donnees backend.
Donnees consommees :
    Contrats de rendu et objets figure optionnels deja fournis.
Livrables produits :
    Fichiers JSON/PNG/SVG demandes par l'utilisateur.
Limites :
    - ne calcule aucune cote ;
    - n'applique aucun patch ;
    - ne fabrique pas de graphique absent ;
    - ne produit pas de STEP.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def export_json_contract(contract: Mapping[str, Any], path: str | Path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(contract), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


def export_existing_figure(figure: Any, path: str | Path) -> str:
    if figure is None or not hasattr(figure, "savefig"):
        raise ValueError("Aucune figure Matplotlib existante a exporter.")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(str(target))
    return str(target)


__all__ = ["export_existing_figure", "export_json_contract"]
