# frontend/pieces/sketches_2d/batterie_pack.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Arrow
from matplotlib.lines import Line2D

from backend.components.batterie.batterie import Batterie

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

@dataclass
class DonneesCroquisBatterie:
    soc: float = 0.5
    temperature_c: float = 25.0
    soh: float = 1.0
    
    puissance_charge_kw: float = 0.0
    puissance_decharge_kw: float = 0.0
    puissance_dispo_alternateur_kw: float = 0.0
    
    courant_charge_a: float = 0.0
    courant_charge_max_securise_a: float = 0.0
    
    besoin_refroidissement_w: float = 0.0
    
    capacite_kwh: float = 0.0
    tension_v: float = 0.0

def extraire_donnees_croquis(batterie: Batterie) -> DonneesCroquisBatterie:
    # On simule une analyse pour obtenir le rapport
    # Note: Dans un vrai usage, on passerait le rapport déjà calculé
    rap = batterie.analyser_dimensionnement()
    
    # Extraction des données dynamiques (simulées ou réelles si disponibles)
    bms = rap.get("pieces", {}).get("bms", {})
    tms = rap.get("pieces", {}).get("tms", {})
    
    return DonneesCroquisBatterie(
        soc=_safe_float(bms.get("monitoring", {}).get("soc"), 0.5),
        temperature_c=_safe_float(bms.get("monitoring", {}).get("temperature_cellules_c"), 25.0),
        soh=_safe_float(bms.get("monitoring", {}).get("soh"), 1.0),
        puissance_charge_kw=_safe_float(rap.get("charge", {}).get("puissance_effective_stockee_kw"), 0.0),
        courant_charge_a=_safe_float(rap.get("charge", {}).get("courant_charge_A"), 0.0),
        courant_charge_max_securise_a=_safe_float(bms.get("resultats", {}).get("courant_charge_max_securise_a"), 0.0),
        besoin_refroidissement_w=_safe_float(tms.get("resultats", {}).get("besoin_refroidissement_charge_w"), 0.0),
        capacite_kwh=_safe_float(rap.get("dimensionnement", {}).get("capacite_totale_kwh"), 0.0),
        tension_v=_safe_float(rap.get("entrees", {}).get("tension_nominale_v"), 0.0)
    )

def tracer_croquis_batterie_2d(batterie: Batterie, titre: str = "Surveillance Pack Batterie - SHSE-M"):
    d = extraire_donnees_croquis(batterie)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    
    # 1. Dessin du Pack Batterie (Rectangle principal)
    ax.add_patch(Rectangle((30, 20), 40, 60, fill=False, edgecolor="black", linewidth=2))
    ax.text(50, 85, "PACK BATTERIE", ha="center", weight="bold")
    
    # Jauge de SOC
    soc_height = d.soc * 50
    color = "green" if d.soc > 0.2 else "red"
    ax.add_patch(Rectangle((40, 25), 20, 50, fill=False, edgecolor="gray"))
    ax.add_patch(Rectangle((40, 25), 20, soc_height, color=color, alpha=0.6))
    ax.text(50, 50, f"{d.soc*100:.1f}%", ha="center", va="center", fontsize=14, weight="bold")
    
    # 2. BMS (Unité de contrôle)
    ax.add_patch(Rectangle((75, 50), 20, 20, facecolor="#f0f0f0", edgecolor="blue"))
    ax.text(85, 75, "BMS", ha="center", weight="bold", color="blue")
    bms_txt = [
        f"SOH: {d.soh*100:.1f}%",
        f"T: {d.temperature_c:.1f}°C",
        f"I_max: {d.courant_charge_max_securise_a:.1f}A"
    ]
    ax.text(85, 60, "\n".join(bms_txt), ha="center", va="center", fontsize=9)
    
    # 3. TMS (Refroidissement)
    ax.add_patch(Rectangle((5, 50), 20, 20, facecolor="#e0f0ff", edgecolor="cyan"))
    ax.text(15, 75, "TMS", ha="center", weight="bold", color="cyan")
    ax.text(15, 60, f"Cooling:\n{d.besoin_refroidissement_w:.1f} W", ha="center", va="center", fontsize=9)
    
    # 4. Flux d'énergie (Flèches)
    # Alternateur -> Batterie
    ax.annotate("Alternateur", xy=(40, 60), xytext=(10, 85),
                arrowprops=dict(facecolor='orange', shrink=0.05))
    ax.text(25, 75, f"{d.puissance_charge_kw:.1f} kW", color="orange", weight="bold")
    
    # 5. Cartouche technique bas
    info_txt = [
        f"Capacité Totale : {d.capacite_kwh:.2f} kWh",
        f"Tension Nominale : {d.tension_v:.1f} V",
        f"Courant Actuel : {d.courant_charge_a:.1f} A"
    ]
    ax.text(50, 5, " | ".join(info_txt), ha="center", bbox=dict(boxstyle="round", facecolor="white"))

    plt.suptitle(titre)
    plt.tight_layout()
    return fig

if __name__ == "__main__":
    batt = Batterie(puissance_charge_kw=50, tension_nominale_v=400)
    tracer_croquis_batterie_2d(batt)
    plt.show()
