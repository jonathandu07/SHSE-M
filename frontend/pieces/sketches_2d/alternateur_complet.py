# frontend/pieces/sketches_2d/alternateur_complet.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Wedge
from matplotlib.lines import Line2D

from backend.components.alternateur.alternateur import Alternateur

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

@dataclass
class DonneesCroquisAlternateur:
    rpm: float = 0.0
    puissance_w: float = 0.0
    rendement: float = 0.0
    
    # Géométrie
    diametre_rotor_mm: float = 0.0
    diametre_stator_mm: float = 0.0
    longueur_mm: float = 0.0
    
    # Pertes
    pertes_cuivre_w: float = 0.0
    pertes_fer_w: float = 0.0
    
    # Ventilation
    debit_air_m3_s: float = 0.0

def extraire_donnees_croquis(alternateur: Alternateur) -> DonneesCroquisAlternateur:
    rap = alternateur.analyser_point_de_fonctionnement()
    
    pieces = rap.get("pieces", {})
    rotor = pieces.get("rotor", {})
    stator = pieces.get("stator", {})
    ventilateur = pieces.get("ventilateur", {})
    
    return DonneesCroquisAlternateur(
        rpm=_safe_float(rap.get("entrees", {}).get("regime_tr_min"), 0.0),
        puissance_w=_safe_float(rap.get("bus_dc", {}).get("puissance_bus_dc_W"), 0.0),
        rendement=_safe_float(rap.get("rendement", {}).get("rendement_global"), 0.0),
        diametre_rotor_mm=_safe_float(rotor.get("geometrie", {}).get("diametre_m"), 0.0) * 1000,
        diametre_stator_mm=_safe_float(stator.get("geometrie", {}).get("diametre_exterieur_m"), 0.0) * 1000,
        pertes_cuivre_w=_safe_float(stator.get("pertes", {}).get("pertes_cuivre_total_W"), 0.0),
        pertes_fer_w=_safe_float(stator.get("pertes", {}).get("pertes_fer_total_W"), 0.0),
        debit_air_m3_s=_safe_float(ventilateur.get("resultats", {}).get("debit_volumique_m3_s"), 0.0)
    )

def tracer_croquis_alternateur_2d(alternateur: Alternateur, titre: str = "Vue en Coupe Alternateur - SHSE-M"):
    d = extraire_donnees_croquis(alternateur)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
    
    # --- VUE DE FACE (TRANSVERSALE) ---
    ax1.set_title("Vue Transversale")
    ax1.set_aspect('equal')
    ax1.axis('off')
    
    # Stator (Extérieur)
    r_stator = d.diametre_stator_mm / 2 if d.diametre_stator_mm > 0 else 100
    ax1.add_patch(Circle((0, 0), r_stator, fill=False, edgecolor="black", linewidth=2, linestyle='--'))
    ax1.text(0, r_stator+5, "STATOR", ha="center")
    
    # Bobinages (Petits cercles)
    for i in range(12):
        angle = i * 30
        x = (r_stator-10) * math.cos(math.radians(angle))
        y = (r_stator-10) * math.sin(math.radians(angle))
        ax1.add_patch(Circle((x, y), 5, color="copper", alpha=0.7))
    
    # Rotor (Intérieur)
    r_rotor = d.diametre_rotor_mm / 2 if d.diametre_rotor_mm > 0 else 70
    ax1.add_patch(Circle((0, 0), r_rotor, facecolor="#e0e0e0", edgecolor="blue"))
    ax1.text(0, 0, "ROTOR", ha="center", va="center", color="blue", weight="bold")
    
    # Pôles (Flèches N/S)
    for i in range(4):
        angle = i * 90
        ax1.text(r_rotor*0.7 * math.cos(math.radians(angle)), 
                 r_rotor*0.7 * math.sin(math.radians(angle)), 
                 "N" if i%2==0 else "S", ha="center", va="center", weight="bold")

    # --- VUE LONGITUDINALE (FLUX) ---
    ax2.set_title("Flux et Pertes")
    ax2.axis('off')
    
    labels = ['Pertes Cuivre', 'Pertes Fer', 'Puissance Utile']
    values = [d.pertes_cuivre_w, d.pertes_fer_w, d.puissance_w]
    colors = ['#ff9999', '#66b3ff', '#99ff99']
    
    if sum(values) > 0:
        ax2.pie(values, labels=labels, autopct='%1.1f%%', colors=colors, startangle=140)
    else:
        ax2.text(0.5, 0.5, "Données de puissance\nindisponibles", ha="center")

    # Infos Ventilation
    ax2.text(0.5, -0.1, f"Flux d'air : {d.debit_air_m3_s*3600:.1f} m³/h", 
             transform=ax2.transAxes, ha="center", bbox=dict(boxstyle="round", facecolor="cyan", alpha=0.1))

    plt.suptitle(titre, fontsize=16)
    return fig

if __name__ == "__main__":
    alt = Alternateur()
    tracer_croquis_alternateur_2d(alt)
    plt.show()
