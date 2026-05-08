# backend/components/boite_crabots/pieces/baladeur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

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
class Baladeur:
    """
    Baladeur de la boîte à crabots.
    Pièce mobile axialement, liée en rotation à l'arbre par des cannelures.
    """

    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None

    # Efforts
    couple_max_Nm: Optional[float] = None

    # Géométrie des cannelures internes
    diametre_primitif_cannelure_m: Optional[float] = None
    longueur_cannelure_m: Optional[float] = None
    nombre_dents_cannelure: Optional[int] = None
    epaisseur_dent_cannelure_m: Optional[float] = None # 'e' pour le cisaillement
    hauteur_contact_cannelure_m: Optional[float] = None # 'h' pour l'écrasement (matage)

    # Matériau (limites admissibles)
    tau_admissible_cannelure_pa: Optional[float] = None
    pression_admissible_cannelure_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "baladeur",
            "entrees": {},
            "cannelures": {},
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
            _push_inconnue(rapport, "impossibles", "couple_max_Nm", "Requis pour évaluer les contraintes sur les cannelures.")

        # 2. Vérification géométrie cannelures
        d = self.diametre_primitif_cannelure_m
        L = self.longueur_cannelure_m
        Z = self.nombre_dents_cannelure
        e = self.epaisseur_dent_cannelure_m
        h = self.hauteur_contact_cannelure_m

        geo_ok = (d is not None and L is not None and Z is not None and e is not None and h is not None)
        
        if not geo_ok:
            _push_inconnue(rapport, "partielles", "geometrie_cannelures", "Tous les paramètres géométriques des cannelures sont requis (diamètre, longueur, Z, épaisseur, hauteur).")

        # 3. Calculs des contraintes (Cisaillement et Matage)
        if T is not None and geo_ok:
            d = float(d)
            L = float(L)
            e = float(e)
            h = float(h)
            Z = int(Z)
            
            # Force tangentielle totale à répartir
            Ft_totale = 2.0 * T / d
            
            # Cisaillement à la base de la dent (tau)
            # Surface de cisaillement totale = Z * L * e
            tau_cannelure = Ft_totale / (Z * L * e)
            rapport["cannelures"]["contrainte_cisaillement_pa"] = tau_cannelure
            
            if self.tau_admissible_cannelure_pa is not None:
                rapport["contraintes"]["ok_cisaillement"] = (tau_cannelure <= self.tau_admissible_cannelure_pa)
            else:
                _push_inconnue(rapport, "partielles", "tau_admissible_cannelure_pa", "Requis pour vérifier le cisaillement.")

            # Pression de contact / matage (p)
            # Surface de contact totale = Z * L * h
            p_cannelure = Ft_totale / (Z * L * h)
            rapport["cannelures"]["pression_matage_pa"] = p_cannelure

            if self.pression_admissible_cannelure_pa is not None:
                rapport["contraintes"]["ok_matage"] = (p_cannelure <= self.pression_admissible_cannelure_pa)
            else:
                _push_inconnue(rapport, "partielles", "pression_admissible_cannelure_pa", "Requis pour vérifier la pression de matage.")

            # Dimensionnement inverse : Longueur minimale requise
            if self.tau_admissible_cannelure_pa is not None and self.pression_admissible_cannelure_pa is not None:
                L_min_cis = Ft_totale / (Z * e * self.tau_admissible_cannelure_pa)
                L_min_mat = Ft_totale / (Z * h * self.pression_admissible_cannelure_pa)
                rapport["cannelures"]["longueur_min_requise_m"] = max(L_min_cis, L_min_mat)

        return rapport
