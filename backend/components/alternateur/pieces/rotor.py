# backend/components/alternateur/pieces/rotor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal
import math

from backend.components.alternateur.modules.calcul_frequence_synchrone import calcul_frequence_synchrone
from backend.components.alternateur.modules.calcul_couple_alternateur import calcul_couple_alternateur
from backend.components.alternateur.modules.calcul_puissance_mecanique import calcul_puissance_mecanique

ModePoles = Literal["poles", "pair_poles", "pole_pairs"]

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
class Rotor:
    """
    Rotor de l'alternateur.
    Gère la conversion de la vitesse d'entrée (boîte/moteur) en fréquence synchrone,
    ainsi que la détermination du couple mécanique absorbé.
    """

    boite_crabots: Optional[Any] = None
    alternateur: Optional[Any] = None

    # Entrées
    vitesse_rotation_rpm: Optional[float] = None
    puissance_electrique_cible_w: Optional[float] = None
    rendement_alternateur_global: Optional[float] = None
    pertes_fixes_w: float = 0.0

    # Topologie
    nombre_poles: Optional[int] = None
    mode_poles: ModePoles = "poles"

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "rotor",
            "entrees": {},
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Vitesse de rotation
        rpm = self.vitesse_rotation_rpm
        if rpm is None:
            # On tente de récupérer la vitesse d'entrée depuis l'alternateur (si analysé)
            rpm = _get(self.alternateur, "vitesse_rotation_rpm")
        
        if rpm is not None:
            rpm = _require_positive("vitesse_rotation_rpm", rpm, strictly=False)
            rapport["entrees"]["vitesse_rotation_rpm"] = rpm
        else:
            _push_inconnue(rapport, "impossibles", "vitesse_rotation_rpm", "Vitesse du rotor requise pour calculer la fréquence et le couple.")

        # 2. Fréquence synchrone
        if rpm is not None and self.nombre_poles is not None:
            freq = calcul_frequence_synchrone(
                vitesse_rotation_tr_min=rpm,
                nombre_poles=self.nombre_poles,
                mode_poles=self.mode_poles,
                clamp_non_negative=True
            )
            rapport["resultats"]["frequence_synchrone_hz"] = freq
        else:
            _push_inconnue(rapport, "partielles", "frequence_synchrone", "vitesse_rotation_rpm et nombre_poles requis.")

        # 3. Couple et Puissance Mécanique
        P_elec = self.puissance_electrique_cible_w
        if P_elec is None:
            P_elec = _get(self.alternateur, "puissance_electrique_cible_w")

        eta = self.rendement_alternateur_global
        
        if P_elec is not None and eta is not None and rpm is not None and rpm > 0:
            omega = rpm * math.pi / 30.0
            
            P_meca = calcul_puissance_mecanique(
                puissance_electrique_cible=P_elec,
                rendement_alternateur=eta,
                pertes_fixes_w=self.pertes_fixes_w,
                clamp_non_negative=True
            )
            rapport["resultats"]["puissance_mecanique_absorbee_w"] = P_meca
            
            couple = calcul_couple_alternateur(
                puissance_electrique_cible=P_elec,
                rendement_alternateur=eta,
                vitesse_angulaire=omega,
                pertes_fixes_w=self.pertes_fixes_w,
                clamp_non_negative=True
            )
            rapport["resultats"]["couple_resistant_nm"] = couple
        else:
            _push_inconnue(rapport, "partielles", "puissance_et_couple", "P_elec, rendement, et rpm(>0) requis.")

        return rapport
