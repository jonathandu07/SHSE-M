# backend/components/boite_crabots/pieces/pignon_boite.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

from backend.components.boite_crabots.modules.calcul_force_pignon import (
    calcul_force_tangentielle,
    calcul_forces_engrenage,
)
from backend.components.boite_crabots.modules.calcul_contact_dent import calcul_contrainte_contact_hertz
from backend.components.boite_crabots.modules.calcul_flexion_dent import calcul_contrainte_flexion_lewis

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _require_positive(name: str, x: Any, *, strictly: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strictly else x >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x

def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": nom, "raison": raison})

def _get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for n in names:
            if n in obj:
                return obj.get(n)
        return None
    for n in names:
        if hasattr(obj, n):
            try:
                return getattr(obj, n)
            except Exception:
                pass
    return None

@dataclass
class PignonBoite:
    """
    Pignon (engrenage) de la boîte à crabots.
    """

    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None

    # Efforts
    couple_max_Nm: Optional[float] = None

    # Géométrie
    diametre_primitif_m: Optional[float] = None
    largeur_denture_b_m: Optional[float] = None
    module_m: Optional[float] = None
    angle_pression_deg: float = 20.0
    angle_helice_deg: float = 0.0

    # Coefficients matériau/qualité
    coefficient_zh: Optional[float] = None  # Contact (Hertz)
    facteur_forme_y: Optional[float] = None # Flexion (Lewis)

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "pignon_boite",
            "entrees": {},
            "forces": {},
            "contraintes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Récupération du couple
        T = self.couple_max_Nm
        if T is None:
            T = _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        
        if T is not None:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            rapport["entrees"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rapport, "impossibles", "couple_max_Nm", "Requis pour calculer les efforts sur la denture.")

        # 2. Forces d'engrenage
        Ft = None
        d = self.diametre_primitif_m
        
        if T is not None and d is not None and d > 0:
            Ft = calcul_force_tangentielle(
                couple_nm=T, diametre_primitif_m=d, use_abs_couple=True, clamp_non_negative=True
            )
            rapport["forces"]["F_tangentielle_N"] = Ft
            
            forces = calcul_forces_engrenage(
                force_tangentielle=Ft,
                angle_pression_deg=self.angle_pression_deg,
                angle_helice_deg=self.angle_helice_deg,
                output="FT_FR_FA",
                use_abs_force=True,
                clamp_non_negative=False
            )
            rapport["forces"]["F_radiale_N"] = float(forces["F_r"])
            rapport["forces"]["F_axiale_N"] = float(forces["F_a"])
        else:
            _push_inconnue(rapport, "partielles", "diametre_primitif_m", "Requis pour déterminer les forces d'engrènement.")

        # 3. Contrainte de contact (Hertz)
        if Ft is not None and self.largeur_denture_b_m is not None and d is not None and self.coefficient_zh is not None:
            sigma_H = calcul_contrainte_contact_hertz(
                force_tangentielle=Ft,
                largeur_denture_b=self.largeur_denture_b_m,
                diametre_primitif_moyen=d,
                coefficient_zh=self.coefficient_zh,
                use_abs_force=True,
                clamp_non_negative=True,
                return_details=False
            )
            rapport["contraintes"]["sigma_contact_hertz_pa"] = sigma_H
        else:
            _push_inconnue(rapport, "partielles", "calcul_hertz", "largeur_denture, diametre_primitif et coefficient_zh requis.")

        # 4. Contrainte de flexion (Lewis)
        if Ft is not None and self.largeur_denture_b_m is not None and self.module_m is not None and self.facteur_forme_y is not None:
            sigma_F = calcul_contrainte_flexion_lewis(
                force_tangentielle=Ft,
                largeur_denture_b=self.largeur_denture_b_m,
                module_m=self.module_m,
                facteur_forme_y=self.facteur_forme_y,
                use_abs_force=True,
                clamp_non_negative=True,
                return_details=False
            )
            rapport["contraintes"]["sigma_flexion_lewis_pa"] = sigma_F
        else:
            _push_inconnue(rapport, "partielles", "calcul_lewis", "largeur_denture, module_m et facteur_forme_y requis.")

        return rapport
