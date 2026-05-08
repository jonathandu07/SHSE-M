# backend/components/alternateur/pieces/carter_alternateur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

from backend.components.alternateur.modules.calcul_echauffement_thermique import calcul_echauffement_thermique

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
class CarterAlternateur:
    """
    Carter de l'alternateur.
    Enveloppe externe, assure le refroidissement en dissipant les pertes internes.
    """

    stator: Optional[Any] = None
    alternateur: Optional[Any] = None

    # Thermique
    puissance_pertes_totale_w: Optional[float] = None
    resistance_thermique_k_w: Optional[float] = None
    offset_temperature_c: float = 0.0
    
    # Limites
    temperature_max_admissible_c: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "carter_alternateur",
            "entrees": {},
            "thermique": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Somme des pertes
        P_pertes = self.puissance_pertes_totale_w
        if P_pertes is None:
            # On tente de récupérer depuis le stator
            if hasattr(self.stator, "analyser"):
                try:
                    rep_stator = self.stator.analyser()
                    p_cu = rep_stator.get("pertes", {}).get("P_cuivre_total_w", 0.0)
                    p_fe = rep_stator.get("pertes", {}).get("P_fer_total_w", 0.0)
                    P_pertes = p_cu + p_fe
                except Exception:
                    pass
            # Sinon, depuis l'alternateur
            if P_pertes is None or P_pertes == 0.0:
                p_pertes_alt = _get(self.alternateur, "pertes_fixes_w")
                if p_pertes_alt is not None:
                    P_pertes = p_pertes_alt

        if P_pertes is not None:
            P_pertes = _require_positive("puissance_pertes_totale_w", P_pertes, strictly=False)
            rapport["entrees"]["puissance_pertes_totale_w"] = P_pertes
        else:
            _push_inconnue(rapport, "impossibles", "puissance_pertes_totale_w", "Requise pour évaluer l'échauffement du carter.")

        # 2. Calcul d'échauffement
        if P_pertes is not None and self.resistance_thermique_k_w is not None:
            delta_t = calcul_echauffement_thermique(
                puissance_pertes_totale=P_pertes,
                resistance_thermique=self.resistance_thermique_k_w,
                offset_temperature=self.offset_temperature_c,
                clamp_non_negative=True
            )
            rapport["thermique"]["echauffement_k"] = delta_t
            temperature_absolue = self.offset_temperature_c + delta_t
            rapport["thermique"]["temperature_estimee_c"] = temperature_absolue

            if self.temperature_max_admissible_c is not None:
                rapport["thermique"]["ok_temperature"] = (temperature_absolue <= self.temperature_max_admissible_c)
            else:
                _push_inconnue(rapport, "partielles", "temperature_max_admissible_c", "Requis pour vérifier si l'alternateur surchauffe.")
        else:
            _push_inconnue(rapport, "partielles", "resistance_thermique_k_w", "Requise pour déterminer l'échauffement thermique.")

        return rapport
