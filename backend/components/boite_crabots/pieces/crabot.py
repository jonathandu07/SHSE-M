# backend/components/boite_crabots/pieces/crabot.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import math

from backend.components.boite_crabots.modules.calcul_dimensionnement_crabot import (
    calcul_couple_transmissible_crabot,
    calcul_pression_contact_crabot,
)
from backend.components.boite_crabots.modules.calcul_choc_engagement import (
    calcul_inertie_equivalente,
    calcul_energie_choc,
    calcul_couple_synchronisation_moyen,
)

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
class Crabot:
    """
    Système d'engagement à crabots.
    """

    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None

    # Efforts et cinématique
    couple_max_Nm: Optional[float] = None
    delta_omega_rad_s: Optional[float] = None
    temps_engagement_s: Optional[float] = None
    inertie_primaire_kg_m2: Optional[float] = None
    inertie_secondaire_kg_m2: Optional[float] = None

    # Géométrie du crabot
    nombre_dents: Optional[int] = None
    hauteur_dent_m: Optional[float] = None
    largeur_dent_m: Optional[float] = None
    rayon_moyen_m: Optional[float] = None
    facteur_repartition: float = 1.0

    # Admissible
    pression_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "crabot",
            "entrees": {},
            "choc_engagement": {},
            "dimensionnements": {},
            "contraintes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Récupérer les efforts du moteur ou des attributs
        T = self.couple_max_Nm
        if T is None:
            T = _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        
        if T is not None:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            rapport["entrees"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rapport, "impossibles", "couple_max_Nm", "Requis pour valider le couple transmissible.")

        # 2. Analyse de l'engagement (Choc)
        J1 = self.inertie_primaire_kg_m2
        if J1 is None:
            J1 = _get(self.moteur_thermique, "masse_tournante_equivalente_kg") # Simplification
        
        J2 = self.inertie_secondaire_kg_m2
        d_omega = self.delta_omega_rad_s
        t_eng = self.temps_engagement_s

        if J1 is not None and J2 is not None:
            Jeq = calcul_inertie_equivalente(inertie_primaire=J1, inertie_secondaire=J2, clamp_non_negative=True)
            rapport["choc_engagement"]["inertie_equivalente_kg_m2"] = Jeq

            if d_omega is not None:
                E_choc = calcul_energie_choc(inertie_eq=Jeq, delta_omega_rad_s=d_omega, clamp_non_negative=True)
                rapport["choc_engagement"]["energie_choc_J"] = E_choc

                if t_eng is not None and t_eng > 0:
                    T_sync = calcul_couple_synchronisation_moyen(
                        inertie_eq=Jeq, delta_omega_rad_s=d_omega, temps_engagement_s=t_eng, use_abs_delta_omega=True
                    )
                    rapport["choc_engagement"]["couple_synchronisation_moyen_Nm"] = T_sync
                else:
                    _push_inconnue(rapport, "partielles", "temps_engagement_s", "Requis pour calculer le couple de synchronisation.")
            else:
                _push_inconnue(rapport, "partielles", "delta_omega_rad_s", "Requis pour calculer l'énergie de choc.")
        else:
            _push_inconnue(rapport, "partielles", "inertie_primaire/secondaire_kg_m2", "Requis pour évaluer le choc d'engagement.")

        # 3. Capacité de transmission
        if (self.nombre_dents is not None and self.hauteur_dent_m is not None and 
            self.largeur_dent_m is not None and self.rayon_moyen_m is not None):
            
            p_adm = self.pression_admissible_pa
            
            if p_adm is not None:
                T_cap = calcul_couple_transmissible_crabot(
                    nombre_dents=self.nombre_dents,
                    pression_admissible=p_adm,
                    hauteur_dent=self.hauteur_dent_m,
                    largeur_dent=self.largeur_dent_m,
                    rayon_moyen=self.rayon_moyen_m,
                    facteur_repartition=self.facteur_repartition,
                    clamp_non_negative=True,
                    return_details=False
                )
                rapport["dimensionnements"]["couple_transmissible_max_Nm"] = T_cap
                
                if T is not None:
                    rapport["contraintes"]["ok_couple"] = (T <= T_cap)
            else:
                _push_inconnue(rapport, "partielles", "pression_admissible_pa", "Requis pour calculer le couple transmissible max.")

            # 4. Pression de contact effective
            if T is not None:
                p_eff = calcul_pression_contact_crabot(
                    couple_nm=T,
                    nombre_dents=self.nombre_dents,
                    hauteur_dent=self.hauteur_dent_m,
                    largeur_dent=self.largeur_dent_m,
                    rayon_moyen=self.rayon_moyen_m,
                    facteur_repartition=self.facteur_repartition,
                    use_abs_couple=True,
                    clamp_non_negative=True,
                    return_details=False
                )
                rapport["contraintes"]["pression_contact_effective_pa"] = p_eff
                if p_adm is not None:
                    rapport["contraintes"]["ok_pression"] = (p_eff <= p_adm)
        else:
            _push_inconnue(rapport, "partielles", "geometrie_crabot", "nombre_dents, hauteur, largeur et rayon moyen requis.")

        return rapport
