# backend/components/boite_crabots/pieces/carter_boite.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
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
class CarterBoite:
    """
    Carter de la boîte à crabots.
    Supporte les efforts des roulements et assure l'étanchéité.
    """

    # Liste des roulements supportés (instances de RoulementBoite ou dictionnaires de résultats)
    roulements: Optional[List[Any]] = None

    # Géométrie globale simplifiée
    longueur_interne_m: Optional[float] = None
    largeur_interne_m: Optional[float] = None
    hauteur_interne_m: Optional[float] = None
    epaisseur_paroi_m: Optional[float] = None

    # Matériau
    densite_kg_m3: Optional[float] = None
    sigma_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "carter_boite",
            "efforts_supports": {},
            "dimensionnements": {},
            "contraintes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. Somme des efforts aux paliers
        F_radiale_totale = 0.0
        F_axiale_totale = 0.0
        
        has_efforts = False
        if self.roulements is not None and len(self.roulements) > 0:
            for i, r in enumerate(self.roulements):
                Fr = None
                Fa = None
                
                if isinstance(r, dict):
                    Fr = r.get("entrees", {}).get("force_radiale_N")
                    Fa = r.get("entrees", {}).get("force_axiale_N")
                elif hasattr(r, "analyser"):
                    try:
                        rep = r.analyser()
                        Fr = rep.get("entrees", {}).get("force_radiale_N")
                        Fa = rep.get("entrees", {}).get("force_axiale_N")
                    except Exception:
                        pass
                else:
                    Fr = getattr(r, "force_radiale_N", None)
                    Fa = getattr(r, "force_axiale_N", None)

                if Fr is not None:
                    F_radiale_totale += abs(float(Fr))
                    has_efforts = True
                if Fa is not None:
                    F_axiale_totale += abs(float(Fa))
                    has_efforts = True

        if has_efforts:
            rapport["efforts_supports"]["force_radiale_cumulee_N"] = F_radiale_totale
            rapport["efforts_supports"]["force_axiale_cumulee_N"] = F_axiale_totale
        else:
            _push_inconnue(rapport, "partielles", "efforts_roulements", "Aucun roulement fourni ou aucun effort trouvé pour le carter.")

        # 2. Vérification de l'épaisseur de paroi / contrainte membranaire simplifiée
        # On suppose le carter comme une cuve soumise à une pression équivalente ou à des efforts ponctuels.
        # Modèle ultra-simplifié : contrainte de cisaillement locale aux paliers
        
        ep = self.epaisseur_paroi_m
        if ep is not None and ep > 0:
            # Si on connait le diamètre des portées on pourrait calculer la surface cisaillée.
            # En l'absence, on se contente de remonter l'épaisseur
            rapport["dimensionnements"]["epaisseur_paroi_m"] = ep
        else:
            _push_inconnue(rapport, "partielles", "epaisseur_paroi_m", "L'épaisseur de la paroi est requise pour calculer la masse et la résistance locale.")

        # Estimation de la masse
        L = self.longueur_interne_m
        W = self.largeur_interne_m
        H = self.hauteur_interne_m
        rho = self.densite_kg_m3
        
        if L is not None and W is not None and H is not None and ep is not None and rho is not None:
            # Volume d'une boîte vide : (L+2e)*(W+2e)*(H+2e) - L*W*H
            L_ext = L + 2*ep
            W_ext = W + 2*ep
            H_ext = H + 2*ep
            V_ext = L_ext * W_ext * H_ext
            V_int = L * W * H
            V_mat = V_ext - V_int
            masse = V_mat * rho
            rapport["dimensionnements"]["volume_matiere_m3"] = V_mat
            rapport["dimensionnements"]["masse_estimee_kg"] = masse
        else:
            _push_inconnue(rapport, "partielles", "masse_carter", "Géométrie interne complète (L, W, H), épaisseur et densité requises pour estimer la masse.")

        return rapport
