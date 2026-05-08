# backend/components/batterie/pieces/bms_batterie.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

from backend.components.batterie.modules.calcul_charge_optimale import calcul_courant_charge_optimal_a

@dataclass
class BMSBatterie:
    """
    Battery Management System (BMS).
    Cerveau de la batterie assurant la sécurité et la longévité.
    """
    
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    
    # Monitoring
    soc: float = 0.5
    temperature_cellules_c: float = 25.0
    soh: float = 1.0  # State of Health
    
    # Paramètres de sécurité (cell preservation)
    c_rate_max_charge: float = 1.0
    tension_max_cellule_v: float = 4.2
    temperature_alerte_c: float = 50.0
    
    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "bms",
            "monitoring": {
                "soc": self.soc,
                "temperature_cellules_c": self.temperature_cellules_c,
                "soh": self.soh
            },
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }
        
        # 1. Récupération des données pack
        capacite_ah = None
        tension_v = None
        if self.batterie is not None:
            # On tente de récupérer depuis l'objet orchestrateur
            capacite_ah = getattr(self.batterie, "capacite_ah_estimee", None)
            tension_v = getattr(self.batterie, "tension_nominale_v", None)
        
        if capacite_ah is None and self.rapport_batterie:
            capacite_ah = self.rapport_batterie.get("electrique", {}).get("capacite_Ah_estimee")
            tension_v = self.rapport_batterie.get("entrees", {}).get("tension_nominale_v")

        if capacite_ah and tension_v:
            # 2. Calcul du courant de charge optimal (Cell Preservation)
            i_opt = calcul_courant_charge_optimal_a(
                soc=self.soc,
                temperature_c=self.temperature_cellules_c,
                c_rate_max=self.c_rate_max_charge,
                capacite_ah=capacite_ah,
                tension_pack_v=tension_v,
                t_limit_c=self.temperature_alerte_c
            )
            rep["resultats"]["courant_charge_max_securise_a"] = i_opt
            rep["resultats"]["puissance_charge_max_securisee_kw"] = (i_opt * tension_v) / 1000.0
            
            # Alerte thermique
            if self.temperature_cellules_c > self.temperature_alerte_c:
                rep["resultats"]["alerte_securite"] = "Surchauffe ! Charge interrompue ou réduite."
        else:
            rep["inconnues"]["impossibles"].append({
                "nom": "calcul_charge_securisee",
                "raison": "Capacité Ah et Tension nominale requises."
            })

        return rep
