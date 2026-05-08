# backend/components/alternateur/pieces/arbre_alternateur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

# On réutilise le calcul de dimensionnement de l'arbre (de boite_crabots)
# S'il n'est pas dispo, on importe localement ou on définit la formule.
try:
    from backend.components.boite_crabots.modules.calcul_dimensionnement_arbre import calcul_contrainte_cisaillement_torsion
except Exception:
    def calcul_contrainte_cisaillement_torsion(couple_nm: float, diametre_arbre_m: float, **kwargs: Any) -> float:
        if diametre_arbre_m <= 0:
            raise ValueError("Diamètre doit être > 0")
        tau = (16.0 * abs(couple_nm)) / (math.pi * diametre_arbre_m**3)
        return float(tau)

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
class ArbreAlternateur:
    """
    Arbre de l'alternateur.
    Transmet le couple de la boîte à crabots vers le rotor.
    """

    alternateur: Optional[Any] = None
    rotor: Optional[Any] = None

    # Efforts
    couple_nm: Optional[float] = None
    
    # Géométrie
    diametre_arbre_m: Optional[float] = None

    # Limites
    tau_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "arbre_alternateur",
            "entrees": {},
            "contraintes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Récupération du couple
        T = self.couple_nm
        if T is None:
            # On tente de le récupérer depuis le rapport du rotor ou de l'alternateur
            if hasattr(self.rotor, "analyser"):
                try:
                    rep_rotor = self.rotor.analyser()
                    T = rep_rotor.get("resultats", {}).get("couple_resistant_nm")
                except Exception:
                    pass
            if T is None:
                T = _get(self.alternateur, "couple_mecanique_Nm")
                
        if T is not None:
            T = _require_finite("couple_nm", T)
            rapport["entrees"]["couple_nm"] = T
        else:
            _push_inconnue(rapport, "impossibles", "couple_nm", "Requis pour calculer la torsion.")

        # 2. Vérification Torsion
        d = self.diametre_arbre_m
        if T is not None and d is not None and d > 0:
            tau = calcul_contrainte_cisaillement_torsion(couple_nm=T, diametre_arbre_m=d)
            rapport["contraintes"]["tau_torsion_pa"] = tau

            if self.tau_admissible_pa is not None:
                rapport["contraintes"]["ok_torsion"] = (tau <= self.tau_admissible_pa)
            else:
                _push_inconnue(rapport, "partielles", "tau_admissible_pa", "Requis pour vérifier la sécurité en torsion.")
                
            # Diamètre minimal
            if self.tau_admissible_pa is not None and self.tau_admissible_pa > 0:
                d_min = ((16.0 * abs(T)) / (math.pi * self.tau_admissible_pa)) ** (1.0 / 3.0)
                rapport["contraintes"]["diametre_min_torsion_m"] = d_min
        else:
            _push_inconnue(rapport, "partielles", "diametre_arbre_m", "Requis pour calculer les contraintes sur l'arbre.")

        return rapport
