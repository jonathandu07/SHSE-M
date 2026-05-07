from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class PieceDimensionnee:
    nom: str
    masse_kg: float
    puissance_cible_w: float
    regime_tr_min: float
    n_cyl: int
    pression_max_pa: float
    longueur_caracteristique_mm: float
    diametre_caracteristique_mm: float
    facteur_securite_estime: float


PIECES_SOURCE = (
    "cylindre",
    "couvercle_cylindre",
    "piston",
    "deplaceur",
    "bielle",
    "arbre",
    "arbre_piston",
    "arbre_vilbrequin",
    "vilbrequin",
    "joint_piston",
    "joint_deplaceur",
    "coussinet_arbre_piston",
    "roulement_aiguille_arbre",
    "roulement_aiguille_arbre_vilebrequin",
    "clavette_arbre",
    "vis_couvercle_cylindre",
)


def _require_positive(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number.")
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{name} must be > 0.")
    return value


def _estimate_piece(name: str, base_mass_kg: float, index: int, **common: Any) -> PieceDimensionnee:
    power_scale = math.sqrt(common["puissance_cible_w"] / 40000.0)
    pressure_scale = max(0.5, common["pression_max_pa"] / 5.0e6)
    mass = base_mass_kg * power_scale * (0.85 + 0.03 * index) * pressure_scale**0.15
    length_mm = 45.0 * power_scale * (1.0 + 0.04 * index)
    diameter_mm = 25.0 * power_scale * (1.0 + 0.025 * index)
    safety = max(1.2, 2.2 - 0.025 * index)

    return PieceDimensionnee(
        nom=name,
        masse_kg=round(mass, 5),
        longueur_caracteristique_mm=round(length_mm, 3),
        diametre_caracteristique_mm=round(diameter_mm, 3),
        facteur_securite_estime=round(safety, 3),
        **common,
    )


def dimensionner_pieces_completes(
    *,
    puissance_cible_w: float,
    regime_tr_min: float,
    n_cyl: int,
    pression_max_pa: float,
    save_to_db: bool = True,
) -> dict[str, Any]:
    """Creates a first-pass piece inventory and stores it in the local DB.

    The detailed per-piece models still live in backend/pieces. This function
    gives backend.main a stable orchestration point and a GUI-friendly data set.
    """

    puissance_cible_w = _require_positive("puissance_cible_w", puissance_cible_w)
    regime_tr_min = _require_positive("regime_tr_min", regime_tr_min)
    pression_max_pa = _require_positive("pression_max_pa", pression_max_pa)
    if not isinstance(n_cyl, int) or n_cyl <= 0:
        raise ValueError("n_cyl must be an integer > 0.")

    common = {
        "puissance_cible_w": puissance_cible_w,
        "regime_tr_min": regime_tr_min,
        "n_cyl": n_cyl,
        "pression_max_pa": pression_max_pa,
    }

    base_mass_kg = max(0.15, puissance_cible_w / 100000.0)
    pieces = {
        name: _estimate_piece(name, base_mass_kg, index, **common)
        for index, name in enumerate(PIECES_SOURCE)
    }

    db_error = None
    if save_to_db:
        try:
            from backend.modules.systeme.database import SecureDatabase

            db = SecureDatabase()
            for piece in pieces.values():
                db.save_piece(piece)
        except Exception as exc:  # pragma: no cover - GUI must keep running.
            db_error = str(exc)

    total_mass = sum(piece.masse_kg for piece in pieces.values())
    return {
        "pieces": {name: vars(piece) for name, piece in pieces.items()},
        "masse_pieces_kg": total_mass,
        "db_error": db_error,
    }
