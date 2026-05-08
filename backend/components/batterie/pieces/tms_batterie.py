# backend/components/batterie/pieces/tms_batterie.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

from backend.components.batterie.modules.calcul_charge_optimale import estimer_puissance_refroidissement_tms_w

@dataclass
class TMSBatterie:
    """
    Thermal Management System (TMS).
    Système de refroidissement/chauffage du pack batterie.
    """
    
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    
    # Technologie
    type_refroidissement: str = "Air"  # "Air", "Liquide", "Immersif"
    efficacite_echangeur: float = 0.7
    
    # Etat
    temperature_liquide_entree_c: float = 20.0
    
    def analyser(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "tms",
            "technologie": {
                "type": self.type_refroidissement,
                "efficacite": self.efficacite_echangeur
            },
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }
        
        # 1. Estimation des besoins en refroidissement pendant la charge
        i_charge = None
        r_interne = None
        
        if self.rapport_batterie:
            i_charge = self.rapport_batterie.get("charge", {}).get("courant_charge_A")
            # On cherche une résistance interne dans le dimensionnement fin
            r_interne = self.rapport_batterie.get("dimensionnement_fin", {}).get("rapport", {}).get("resistance_interne_pack_ohm")
            
        if i_charge and r_interne:
            p_cooling = estimer_puissance_refroidissement_tms_w(
                courant_a=i_charge,
                resistance_interne_pack_ohm=r_interne,
                efficacite_tms=self.efficacite_echangeur
            )
            rep["resultats"]["besoin_refroidissement_charge_w"] = p_cooling
        else:
            rep["inconnues"]["partielles"].append({
                "nom": "besoin_refroidissement",
                "raison": "Courant de charge et Résistance interne du pack requis."
            })

        return rep
