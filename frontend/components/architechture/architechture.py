"""
Chemin : frontend/components/architechture/sketches_2d.py
But : Orchestrateur front-end servant de page d'affichage et permettant de consulter les données sur les pièces.
"""

# frontend/pieces/sketches_2d/architecture_layout.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
from matplotlib.lines import Line2D

from backend.components.architechture.architecture import Architecture

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

@dataclass
class DonneesCroquisArchitecture:
    architecture: str = "L"
    nb_cylindres: int = 4
    
    # Conséquences physiques
    longueur_vilebrequin_mm: float = 0.0
    masse_bloc_kg: float = 0.0
    nb_culasses: int = 1
    
    # Scores
    score_global: float = 0.0

def extraire_donnees_croquis(arch: Architecture) -> DonneesCroquisArchitecture:
    rap = arch.analyser()
    meilleur = rap.get("meilleur") or {}
    pieces = rap.get("pieces", {})
    
    vilebrequin = pieces.get("vilebrequin", {}).get("resultats", {})
    bloc = pieces.get("bloc", {}).get("resultats", {})
    culasse = pieces.get("culasse", {}).get("resultats", {})
    
    return DonneesCroquisArchitecture(
        architecture=str(meilleur.get("architecture", "L")),
        nb_cylindres=int(meilleur.get("N_cyl", 4)),
        longueur_vilebrequin_mm=_safe_float(vilebrequin.get("longueur_vilebrequin_m"), 0.0) * 1000,
        masse_bloc_kg=_safe_float(bloc.get("masse_bloc_estimee_kg"), 0.0),
        nb_culasses=int(culasse.get("nb_culasses", 1)),
        score_global=_safe_float(meilleur.get("score_global"), 0.0)
    )

def tracer_croquis_architecture_2d(arch: Architecture, titre: str = "Schéma de l'Architecture Sélectionnée"):
    d = extraire_donnees_croquis(arch)
    
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(-100, 100)
    ax.set_ylim(-50, 150)
    ax.axis("off")
    
    # 1. Vilebrequin (Axe central)
    ax.add_line(Line2D([-40, 40], [0, 0], color="gray", linewidth=4, label="Vilebrequin"))
    
    # 2. Cylindres selon l'architecture
    if d.architecture == "L":
        for i in range(d.nb_cylindres):
            x = -30 + i * (60/(d.nb_cylindres-1)) if d.nb_cylindres > 1 else 0
            ax.add_patch(Rectangle((x-5, 0), 10, 30, facecolor="#f0f0f0", edgecolor="black"))
    
    elif d.architecture == "V":
        angle = 30 # 60 deg total
        for i in range(math.ceil(d.nb_cylindres/2)):
            x = -20 + i * 40
            # Banc 1
            ax.add_patch(Rectangle((x-12, 0), 10, 30, angle=angle, facecolor="#f0f0f0", edgecolor="black"))
            # Banc 2
            ax.add_patch(Rectangle((x+2, 0), 10, 30, angle=-angle, facecolor="#f0f0f0", edgecolor="black"))

    elif d.architecture == "Boxer":
        for i in range(math.ceil(d.nb_cylindres/2)):
            y = 10 + i * 20
            # Gauche
            ax.add_patch(Rectangle((-35, y-5), 30, 10, facecolor="#f0f0f0", edgecolor="black"))
            # Droite
            ax.add_patch(Rectangle((5, y-5), 30, 10, facecolor="#f0f0f0", edgecolor="black"))

    elif d.architecture == "Etoile":
        for i in range(d.nb_cylindres):
            ang = i * (360/d.nb_cylindres)
            x_tip = 40 * math.cos(math.radians(ang))
            y_tip = 40 * math.sin(math.radians(ang))
            ax.add_line(Line2D([0, x_tip], [0, y_tip], color="black", linewidth=2))
            ax.add_patch(Circle((x_tip, y_tip), 8, facecolor="#f0f0f0", edgecolor="black"))

    # 3. Annotations
    ax.text(0, -20, f"Architecture : {d.architecture} {d.nb_cylindres}", ha="center", weight="bold", fontsize=14)
    
    info_txt = [
        f"Longueur Vilebrequin : {d.longueur_vilebrequin_mm:.1f} mm",
        f"Masse Bloc Estimée : {d.masse_bloc_kg:.1f} kg",
        f"Nombre de Culasses : {d.nb_culasses}",
        f"Score Global (min=mieux) : {d.score_global:.3f}"
    ]
    ax.text(-95, 120, "\n".join(info_txt), ha="left", va="top", 
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    plt.suptitle(titre)
    return fig

if __name__ == "__main__":
    from backend.components.architechture.architecture import ProfilUsageMoteur, ArchitectureType
    profil = ProfilUsageMoteur(architecture_forcee="V")
    arch = Architecture(profil_usage=profil)
    tracer_croquis_architecture_2d(arch)
    plt.show()
