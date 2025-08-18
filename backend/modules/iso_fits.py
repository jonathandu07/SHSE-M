# backend\modules\iso_fits.py
# -*- coding: utf-8 -*-
"""
Calcul des écarts ISO 286 et des ajustements (jeu/serrage)
à partir de tableaux saisis (YAML) comme ceux de ton livre.

Utilisation en CLI :
    python iso_fits.py --D 35 --hole H7 --shaft g6
    python iso_fits.py --D 10 --hole H7
    python iso_fits.py --D 10 --shaft h6

Fichiers de données attendus (dans le même dossier) :
    holes.yaml  (alésages)
    shafts.yaml (arbres)

Chaque fichier définit :
- une liste de classes de diamètre (en mm) : ranges: [[0,3], [3,6], [6,10], ...]
- pour chaque qualité/position (ex. H7), une liste d’écarts [ES, EI] en µm
  ordonnée selon les ranges.

NB : Je fournis ci-dessous des données EXEMPLE minimales.
Complète-les selon tes tableaux pour couvrir toutes les positions et tous les intervalles.
"""

from __future__ import annotations
import argparse
import sys
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    import yaml  # pip install pyyaml
except ImportError:
    print("Ce script nécessite PyYAML. Installe-le :  pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------
# Données d'exemple : si holes.yaml / shafts.yaml n'existent pas,
# on les crée automatiquement avec un squelette prêt à compléter.
# Les valeurs ci-dessous SONT INDICATIVES (purement démonstratives).
# Remplace-les par celles de tes tableaux.
# ---------------------------------------------------------------------
EXAMPLE_HOLES = {
    "ranges": [[0,3], [3,6], [6,10], [10,18], [18,30], [30,50], [50,80], [80,120]],
    # ES/EI en µm par intervalle (même ordre que "ranges")
    "H7": [[+12, 0], [+12, 0], [+15, 0], [+18, 0], [+21, 0], [+25, 0], [+30, 0], [+35, 0]],
    "H8": [[+18, 0], [+18, 0], [+22, 0], [+27, 0], [+33, 0], [+39, 0], [+46, 0], [+54, 0]],
    "H6": [[+6, 0],  [+6, 0],  [+8, 0],  [+9, 0],  [+11, 0], [+13, 0], [+16, 0], [+19, 0]],
    # Ajoute H9, H10, ... etc. d’après ton livre
}

EXAMPLE_SHAFTS = {
    "ranges": [[0,3], [3,6], [6,10], [10,18], [18,30], [30,50], [50,80], [80,120]],
    # es/ei en µm par intervalle
    "h6": [[0, -6], [0, -6], [0, -8], [0, -9], [0, -11], [0, -13], [0, -16], [0, -19]],
    "g6": [[-2, -8], [-2, -8], [-3, -11], [-4, -13], [-5, -16], [-6, -19], [-7, -22], [-9, -25]],
    "f7": [[-5, -17], [-5, -17], [-6, -20], [-8, -26], [-10, -31], [-12, -37], [-14, -44], [-17, -52]],
    # Ajoute j6, k6, m6, n6, p6, ... etc.
}

def ensure_data_files() -> Tuple[Path, Path]:
    here = Path(__file__).resolve().parent
    holes_p = here / "holes.yaml"
    shafts_p = here / "shafts.yaml"

    if not holes_p.exists():
        with open(holes_p, "w", encoding="utf-8") as f:
            yaml.safe_dump(EXAMPLE_HOLES, f, sort_keys=False, allow_unicode=True)
        print(f"[Init] Fichier de données créé : {holes_p}")

    if not shafts_p.exists():
        with open(shafts_p, "w", encoding="utf-8") as f:
            yaml.safe_dump(EXAMPLE_SHAFTS, f, sort_keys=False, allow_unicode=True)
        print(f"[Init] Fichier de données créé : {shafts_p}")

    return holes_p, shafts_p

# ---------------------------------------------------------------------
# Chargement & recherche
# ---------------------------------------------------------------------
def load_table(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if "ranges" not in data or not isinstance(data["ranges"], list):
        raise ValueError(f"{path.name}: clé 'ranges' absente ou invalide")
    return data

def find_range_index(D: float, ranges: List[List[float]]) -> int:
    """Retourne l'index de l’intervalle contenant D (en mm).
    Les 'ranges' sont des listes [borne_inf_incluse, borne_sup_exclue] en mm.
    """
    for i, (a, b) in enumerate(ranges):
        if (D >= a) and (D < b):
            return i
    # Si D est sur la dernière borne haute, on autorise l’inclusion
    if abs(D - ranges[-1][1]) < 1e-9:
        return len(ranges) - 1
    raise ValueError(f"Diamètre {D} mm en dehors des intervalles définis.")

def get_deviations(table: Dict, symbol: str, D: float) -> Tuple[int, int]:
    """Retourne (supérieur, inférieur) en µm pour un symbole (ex. H7, g6)."""
    ranges = table["ranges"]
    idx = find_range_index(D, ranges)
    if symbol not in table:
        raise KeyError(f"Symbole '{symbol}' absent du tableau.")
    pair = table[symbol][idx]
    if not (isinstance(pair, list) and len(pair) == 2):
        raise ValueError(f"Entrée invalide pour {symbol} à l’index {idx}.")
    return int(pair[0]), int(pair[1])

# ---------------------------------------------------------------------
# Calcul d’ajustement
# ---------------------------------------------------------------------
def fit_results(D: float,
                hole: Optional[Tuple[int, int]] = None,
                shaft: Optional[Tuple[int, int]] = None) -> Dict[str, float]:
    """
    D en mm.
    hole = (ES, EI) en µm pour l’alésage (ES=écart sup, EI=écart inf).
    shaft = (es, ei) en µm pour l’arbre (es=écart sup, ei=écart inf).

    Retourne :
        - Dmax/Dmin trou et arbre (mm)
        - jeu_min / jeu_max (mm) si les deux sont fournis
    """
    out: Dict[str, float] = {}
    if hole:
        ES, EI = hole
        out["D_trou_max"] = D + ES * 1e-3
        out["D_trou_min"] = D + EI * 1e-3
    if shaft:
        es, ei = shaft
        out["d_arbre_max"] = D + es * 1e-3
        out["d_arbre_min"] = D + ei * 1e-3
    if hole and shaft:
        # Jeux (positif = jeu, négatif = serrage)
        out["jeu_min"] = out["D_trou_min"] - out["d_arbre_max"]
        out["jeu_max"] = out["D_trou_max"] - out["d_arbre_min"]
    return out

def human_report(D: float,
                 hole_sym: Optional[str], hole_dev: Optional[Tuple[int,int]],
                 shaft_sym: Optional[str], shaft_dev: Optional[Tuple[int,int]]) -> str:
    lines = []
    lines.append(f"Diamètre nominal D = {D:.3f} mm")
    if hole_sym and hole_dev:
        ES, EI = hole_dev
        lines.append(f"Alésage {hole_sym}: ES={ES} µm, EI={EI} µm")
    if shaft_sym and shaft_dev:
        es, ei = shaft_dev
        lines.append(f"Arbre   {shaft_sym}: es={es} µm, ei={ei} µm")

    res = fit_results(D, hole_dev, shaft_dev)
    if "D_trou_max" in res:
        lines.append(f"Trou : Dmax={res['D_trou_max']:.3f} mm   Dmin={res['D_trou_min']:.3f} mm")
    if "d_arbre_max" in res:
        lines.append(f"Arbre: dmax={res['d_arbre_max']:.3f} mm  dmin={res['d_arbre_min']:.3f} mm")

    if "jeu_min" in res:
        jmin = res["jeu_min"]; jmax = res["jeu_max"]
        nature = ("(serrage possible)" if jmin < 0 else "(jeu garanti)")
        lines.append(f"Ajustement : jeu_min={jmin*1e3:+.3f} µm, jeu_max={jmax*1e3:+.3f} µm {nature}")
    return "\n".join(lines)

# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def main():
    holes_p, shafts_p = ensure_data_files()
    holes = load_table(holes_p)
    shafts = load_table(shafts_p)

    p = argparse.ArgumentParser(description="Ajustements ISO (tables).")
    p.add_argument("--D", type=float, required=True, help="Diamètre nominal en mm")
    p.add_argument("--hole", type=str, help="Symbole alésage (ex. H7)")
    p.add_argument("--shaft", type=str, help="Symbole arbre (ex. g6)")
    args = p.parse_args()

    hole_dev = None
    shaft_dev = None

    if args.hole:
        hole_dev = get_deviations(holes, args.hole, args.D)
    if args.shaft:
        shaft_dev = get_deviations(shafts, args.shaft, args.D)

    if not args.hole and not args.shaft:
        print("Indique au moins --hole ou --shaft.", file=sys.stderr)
        sys.exit(2)

    print(human_report(args.D, args.hole, hole_dev, args.shaft, shaft_dev))

if __name__ == "__main__":
    main()