# backend/components/boite_crabots/pieces/roulement_boite.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal
import math

from backend.components.boite_crabots.modules.calcul_duree_vie_roulement import (
    calcul_charge_equivalente_roulement,
    calcul_duree_vie_l10,
    calcul_duree_vie_heures,
)

TypeRoulement = Literal["bille", "rouleau"]

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
class RoulementBoite:
    """
    Roulement (à billes, à rouleaux) pour supporter l'arbre de la boîte.
    """

    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None
    pignon: Optional[Any] = None

    # Efforts radiaux et axiaux
    force_radiale_N: Optional[float] = None
    force_axiale_N: Optional[float] = None

    # Vitesse de rotation
    rpm: Optional[float] = None

    # Paramètres du roulement (données constructeur)
    capacite_dynamique_C_N: Optional[float] = None
    facteur_X: Optional[float] = None
    facteur_Y: Optional[float] = None
    type_roulement: TypeRoulement = "bille"
    exposant_p: Optional[float] = None  # Si non fourni, 3.0 (bille) ou 10/3 (rouleau)

    # Cible
    duree_vie_cible_heures: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "roulement_boite",
            "entrees": {},
            "duree_vie": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Récupération des efforts et de la vitesse
        rpm = self.rpm
        if rpm is None:
            rpm = _get(self.moteur_thermique, "rpm", "regime_rpm")
        
        if rpm is not None:
            rpm = _require_positive("rpm", rpm, strictly=False)
            rapport["entrees"]["rpm"] = rpm
        else:
            _push_inconnue(rapport, "partielles", "rpm", "Requis pour convertir la durée de vie en heures.")

        Fr = self.force_radiale_N
        Fa = self.force_axiale_N

        if Fr is None and hasattr(self.pignon, "analyser"):
            try:
                rep_pignon = self.pignon.analyser()
                Fr = rep_pignon.get("forces", {}).get("F_radiale_N")
                if Fa is None:
                    Fa = rep_pignon.get("forces", {}).get("F_axiale_N")
            except Exception:
                pass

        if Fr is not None:
            rapport["entrees"]["force_radiale_N"] = Fr
        else:
            _push_inconnue(rapport, "impossibles", "force_radiale_N", "Requise pour évaluer la charge équivalente.")
        
        if Fa is not None:
            rapport["entrees"]["force_axiale_N"] = Fa

        # 2. Calcul de la charge équivalente
        P_eq = None
        if Fr is not None and Fa is not None and self.facteur_X is not None and self.facteur_Y is not None:
            P_eq = calcul_charge_equivalente_roulement(
                force_radiale=Fr,
                force_axiale=Fa,
                facteur_x=self.facteur_X,
                facteur_y=self.facteur_Y,
                use_abs_forces=True,
                clamp_non_negative=True
            )
            rapport["duree_vie"]["charge_equivalente_P_N"] = P_eq
        else:
            _push_inconnue(rapport, "partielles", "charge_equivalente", "Fr, Fa, facteur_X et facteur_Y requis.")

        # 3. Calcul de la durée de vie L10
        L10_m = None
        if P_eq is not None and self.capacite_dynamique_C_N is not None:
            L10_m = calcul_duree_vie_l10(
                charge_dynamique_base_c=self.capacite_dynamique_C_N,
                charge_equivalente_p=P_eq,
                type_roulement=self.type_roulement,
                exposant_p=self.exposant_p,
                clamp_non_negative=True
            )
            rapport["duree_vie"]["L10_millions_tours"] = L10_m
        else:
            _push_inconnue(rapport, "partielles", "L10_millions_tours", "Charge équivalente et capacité_dynamique_C_N requises.")

        # 4. Conversion en heures
        L10_h = None
        if L10_m is not None and rpm is not None and rpm > 0:
            L10_h = calcul_duree_vie_heures(
                l10_millions=L10_m,
                vitesse_rotation_tr_min=rpm,
                clamp_non_negative=True
            )
            rapport["duree_vie"]["L10_heures"] = L10_h
            
            # Vérification par rapport à la cible
            if self.duree_vie_cible_heures is not None:
                rapport["duree_vie"]["ok_duree_vie"] = (L10_h >= self.duree_vie_cible_heures)

        return rapport
