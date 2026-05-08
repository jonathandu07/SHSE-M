# backend/components/boite_crabots/pieces/fourchette.py
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

@dataclass
class Fourchette:
    """
    Fourchette de sélection de la boîte à crabots.
    Transmet l'effort pour déplacer le baladeur.
    """

    # Efforts
    force_manoeuvre_N: Optional[float] = None
    
    # Paramètres de calcul de force si force_manoeuvre_N non fournie
    masse_baladeur_kg: Optional[float] = None
    acceleration_engagement_m_s2: Optional[float] = None
    coefficient_frottement_cannelure: float = 0.1
    force_radiale_cannelure_N: Optional[float] = None # Liée au couple résiduel

    # Géométrie de la fourchette (modélisée comme une poutre encastrée à la base)
    longueur_bras_m: Optional[float] = None
    largeur_bras_m: Optional[float] = None  # 'b'
    epaisseur_bras_m: Optional[float] = None # 'h' (dans le sens de la flexion)
    
    # Géométrie des patins (contact avec la gorge du baladeur)
    surface_contact_patins_m2: Optional[float] = None

    # Limites Matériau
    sigma_flexion_admissible_pa: Optional[float] = None
    pression_contact_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "fourchette",
            "entrees": {},
            "efforts": {},
            "contraintes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Calcul de l'effort de manœuvre
        F_manoeuvre = self.force_manoeuvre_N
        
        if F_manoeuvre is None:
            # Estimation de la force si non fournie
            F_inertie = 0.0
            if self.masse_baladeur_kg is not None and self.acceleration_engagement_m_s2 is not None:
                F_inertie = self.masse_baladeur_kg * self.acceleration_engagement_m_s2
            
            F_frottement = 0.0
            if self.force_radiale_cannelure_N is not None:
                F_frottement = self.force_radiale_cannelure_N * self.coefficient_frottement_cannelure
                
            if F_inertie > 0 or F_frottement > 0:
                F_manoeuvre = F_inertie + F_frottement
                rapport["notes_modele"].append("Force de manœuvre estimée via inertie et frottement.")
            else:
                _push_inconnue(rapport, "partielles", "force_manoeuvre_N", "Requise pour dimensionner la fourchette (ou fournir masse, accel, frottement).")

        if F_manoeuvre is not None:
            F_manoeuvre = _require_positive("force_manoeuvre_N", F_manoeuvre, strictly=False)
            rapport["efforts"]["force_manoeuvre_N"] = F_manoeuvre

        # 2. Vérification de la flexion des bras
        L = self.longueur_bras_m
        b = self.largeur_bras_m
        h = self.epaisseur_bras_m

        if F_manoeuvre is not None and L is not None and b is not None and h is not None:
            L = float(L)
            b = float(b)
            h = float(h)
            
            # Moment fléchissant max à la base du bras (on suppose la force répartie sur 2 bras, donc F/2 par bras)
            M_f = (F_manoeuvre / 2.0) * L
            
            # Module de flexion (I/v) pour section rectangulaire = (b * h^2) / 6
            I_sur_v = (b * h**2) / 6.0
            
            sigma_flexion = M_f / I_sur_v
            rapport["contraintes"]["sigma_flexion_bras_pa"] = sigma_flexion

            if self.sigma_flexion_admissible_pa is not None:
                rapport["contraintes"]["ok_flexion"] = (sigma_flexion <= self.sigma_flexion_admissible_pa)
            else:
                _push_inconnue(rapport, "partielles", "sigma_flexion_admissible_pa", "Requis pour vérifier la flexion des bras.")
        else:
            _push_inconnue(rapport, "partielles", "geometrie_bras", "longueur, largeur et épaisseur du bras requises pour la flexion.")

        # 3. Vérification de la pression de contact des patins
        A_patins = self.surface_contact_patins_m2
        if F_manoeuvre is not None and A_patins is not None and A_patins > 0:
            p_contact = F_manoeuvre / float(A_patins)
            rapport["contraintes"]["pression_contact_patins_pa"] = p_contact

            if self.pression_contact_admissible_pa is not None:
                rapport["contraintes"]["ok_pression_contact"] = (p_contact <= self.pression_contact_admissible_pa)
            else:
                _push_inconnue(rapport, "partielles", "pression_contact_admissible_pa", "Requis pour vérifier le contact patin/gorge.")
        else:
            _push_inconnue(rapport, "partielles", "surface_contact_patins_m2", "Requise pour vérifier la pression sur la gorge du baladeur.")

        return rapport
