# backend/components/alternateur/pieces/stator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal
import math

from backend.components.alternateur.modules.calcul_fem_induite import calcul_fem_induite
from backend.components.alternateur.modules.calcul_pertes_cuivre import calcul_resistance_enroulement, calcul_pertes_cuivre_triphase
from backend.components.alternateur.modules.calcul_pertes_fer import calcul_pertes_fer_steinmetz

Connexion = Literal["Y", "Delta"]

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
class Stator:
    """
    Stator de l'alternateur.
    Calcule la FEM, les pertes fer (Steinmetz) et les pertes cuivre par effet Joule.
    """

    # --- FEM ---
    frequence_electrique_hz: Optional[float] = None
    nombre_spires_serie: Optional[int] = None
    flux_max_pole_wb: Optional[float] = None
    facteur_enroulement: Optional[float] = None
    connexion: Connexion = "Y"

    # --- Cuivre ---
    courant_phase_rms_a: Optional[float] = None
    resistance_phase_ohm: Optional[float] = None
    resistivite_ohm_m: Optional[float] = None
    longueur_fil_m: Optional[float] = None
    section_fil_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_ref_c: float = 20.0
    coef_temperature: float = 0.00393

    # --- Fer ---
    k_h: Optional[float] = None
    k_e: Optional[float] = None
    exposant_steinmetz: Optional[float] = None
    induction_max_t: Optional[float] = None
    masse_fer_kg: Optional[float] = None
    volume_fer_m3: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "stator",
            "resultats": {},
            "pertes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1. FEM induite
        if (
            self.frequence_electrique_hz is not None
            and self.nombre_spires_serie is not None
            and self.flux_max_pole_wb is not None
            and self.facteur_enroulement is not None
        ):
            fem_phase = calcul_fem_induite(
                frequence=self.frequence_electrique_hz,
                nombre_spires_serie=self.nombre_spires_serie,
                flux_max_pole=self.flux_max_pole_wb,
                facteur_enroulement=self.facteur_enroulement,
                clamp_non_negative=True
            )
            rapport["resultats"]["fem_phase_v"] = fem_phase
            k_vll = math.sqrt(3.0) if self.connexion == "Y" else 1.0
            rapport["resultats"]["fem_ligne_v"] = fem_phase * k_vll
        else:
            _push_inconnue(rapport, "partielles", "fem_induite", "frequence, nb_spires, flux_max et facteur_enroulement requis.")

        # 2. Pertes Cuivre
        R_phase = self.resistance_phase_ohm
        if R_phase is None and self.resistivite_ohm_m is not None and self.longueur_fil_m is not None and self.section_fil_m2 is not None:
            R_phase = calcul_resistance_enroulement(
                resistivite=self.resistivite_ohm_m,
                longueur_fil=self.longueur_fil_m,
                section_fil=self.section_fil_m2,
                temperature_c=self.temperature_c,
                temperature_ref_c=self.temperature_ref_c,
                coef_temperature=self.coef_temperature,
                clamp_non_negative=True
            )
            rapport["resultats"]["resistance_phase_calculee_ohm"] = R_phase
        elif R_phase is None:
            _push_inconnue(rapport, "partielles", "resistance_phase", "R_phase ou paramètres du fil requis.")

        if R_phase is not None and self.courant_phase_rms_a is not None:
            P_cu = calcul_pertes_cuivre_triphase(
                courant_phase=self.courant_phase_rms_a,
                resistance_phase=R_phase,
                courant_type="rms",
                connexion=self.connexion,
                courant_est_ligne=False,
                clamp_non_negative=True
            )
            rapport["pertes"]["P_cuivre_total_w"] = P_cu
        else:
            _push_inconnue(rapport, "partielles", "pertes_cuivre", "courant_phase_rms_a et R_phase requis.")

        # 3. Pertes Fer
        if (
            self.frequence_electrique_hz is not None
            and self.induction_max_t is not None
            and self.k_h is not None
            and self.k_e is not None
            and self.exposant_steinmetz is not None
        ):
            dfe = calcul_pertes_fer_steinmetz(
                k_h=self.k_h,
                frequence=self.frequence_electrique_hz,
                induction_max=self.induction_max_t,
                exposant_steinmetz=self.exposant_steinmetz,
                k_e=self.k_e,
                masse_kg=self.masse_fer_kg,
                volume_m3=self.volume_fer_m3,
                return_details=True,
                clamp_non_negative=True
            )
            rapport["pertes"]["P_fer_total_w"] = dfe["P_total"]
        else:
            _push_inconnue(rapport, "partielles", "pertes_fer", "frequence, induction_max et coefficients Steinmetz requis.")

        return rapport
