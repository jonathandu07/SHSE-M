# backend/components/boite_crabots/pieces/arbre_boite.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import math

# Imports pour les calculs d'arbre
from backend.components.boite_crabots.modules.calcul_dimensionnement_arbre import (
    calcul_contrainte_cisaillement_torsion,
    calcul_contrainte_flexion_arbre,
    calcul_von_mises_arbre,
)

# Helpers
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

def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for m in ("analyser", "calculer"):
        fn = getattr(obj, m, None)
        if callable(fn):
            try:
                out = fn(strict=False) if m == "analyser" else fn()
                if isinstance(out, dict):
                    return out
            except Exception:
                pass
    return None

@dataclass
class ArbreBoite:
    """
    Arbre de la boîte à crabots.
    Peut-être l'arbre primaire ou secondaire.
    """

    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None

    # Efforts
    couple_max_Nm: Optional[float] = None
    moment_flechissant_max_Nm: Optional[float] = None

    # Géométrie
    diametre_arbre_m: Optional[float] = None

    # Matériau et contraintes
    tau_admissible_pa: Optional[float] = None
    sigma_admissible_pa: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    facteur_securite: float = 2.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "arbre_boite",
            "entrees": {},
            "dimensionnements": {},
            "contraintes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Récupération du couple depuis le moteur ou l'entrée directe
        T = self.couple_max_Nm
        if T is None:
            T = _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        
        if T is not None:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            rapport["dimensionnements"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rapport, "impossibles", "couple_max_Nm", "Requis pour dimensionner l'arbre en torsion.")

        M = self.moment_flechissant_max_Nm
        if M is not None:
            M = _require_positive("moment_flechissant_max_Nm", M, strictly=False)
            rapport["dimensionnements"]["moment_flechissant_max_Nm"] = M
        else:
            _push_inconnue(rapport, "partielles", "moment_flechissant_max_Nm", "Utile pour la flexion.")

        # 2. Contraintes admissibles
        tau_adm = self.tau_admissible_pa
        sigma_adm = self.sigma_admissible_pa

        if tau_adm is None and self.limite_elastique_pa is not None:
            tau_adm = float(self.limite_elastique_pa) / (self.facteur_securite * math.sqrt(3.0))
            rapport["notes_modele"].append("tau_admissible_pa déduit de la limite élastique (von Mises).")

        if sigma_adm is None and self.limite_elastique_pa is not None:
            sigma_adm = float(self.limite_elastique_pa) / self.facteur_securite
            rapport["notes_modele"].append("sigma_admissible_pa déduit de la limite élastique.")

        rapport["contraintes"]["tau_admissible_pa"] = tau_adm
        rapport["contraintes"]["sigma_admissible_pa"] = sigma_adm

        # 3. Diamètre minimum (torsion)
        d_min_torsion = None
        if T is not None and tau_adm is not None and tau_adm > 0:
            d_min_torsion = (16.0 * T / (math.pi * tau_adm)) ** (1.0 / 3.0)
            rapport["dimensionnements"]["d_min_torsion_m"] = d_min_torsion
        else:
            _push_inconnue(rapport, "partielles", "d_min_torsion_m", "Calculable si couple et tau_admissible_pa sont connus.")

        # 4. Diamètre minimum (flexion)
        d_min_flexion = None
        if M is not None and sigma_adm is not None and sigma_adm > 0:
            d_min_flexion = (32.0 * M / (math.pi * sigma_adm)) ** (1.0 / 3.0)
            rapport["dimensionnements"]["d_min_flexion_m"] = d_min_flexion

        # 5. Diamètre retenu
        ds = [d for d in (d_min_torsion, d_min_flexion) if d is not None]
        d_min_global = max(ds) if ds else None
        
        d_retenu = self.diametre_arbre_m
        if d_retenu is not None:
            rapport["dimensionnements"]["diametre_arbre_impose_m"] = d_retenu
        elif d_min_global is not None:
            d_retenu = d_min_global
            rapport["dimensionnements"]["diametre_arbre_calcule_m"] = d_retenu
        else:
            _push_inconnue(rapport, "impossibles", "diametre_arbre_m", "Impossible de dimensionner l'arbre sans données (couple, contraintes).")

        # 6. Vérifications des contraintes avec le diamètre retenu
        if d_retenu is not None and d_retenu > 0:
            if T is not None:
                tau_reel = calcul_contrainte_cisaillement_torsion(
                    couple_nm=T, diametre_arbre_m=d_retenu, use_abs_couple=True, clamp_non_negative=True
                )
                rapport["contraintes"]["tau_torsion_reel_pa"] = tau_reel
                if tau_adm is not None:
                    rapport["contraintes"]["ok_torsion"] = (tau_reel <= tau_adm)
            
            if M is not None:
                sigma_reel = calcul_contrainte_flexion_arbre(
                    moment_flechissant_nm=M, diametre_arbre_m=d_retenu, use_abs_moment=True, clamp_non_negative=True
                )
                rapport["contraintes"]["sigma_flexion_reel_pa"] = sigma_reel
                if sigma_adm is not None:
                    rapport["contraintes"]["ok_flexion"] = (sigma_reel <= sigma_adm)
                
                if T is not None and 'tau_reel' in locals():
                    sigma_vm = calcul_von_mises_arbre(
                        contrainte_flexion=sigma_reel,
                        contrainte_cisaillement=tau_reel,
                        mode="flexion+torsion"
                    )
                    rapport["contraintes"]["sigma_von_mises_reel_pa"] = sigma_vm
                    if sigma_adm is not None:
                        rapport["contraintes"]["ok_von_mises"] = (sigma_vm <= sigma_adm)

        return rapport
