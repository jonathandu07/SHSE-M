# backend/components/batterie/modules/calcul_charge_optimale.py
from __future__ import annotations

import math
from typing import Optional

def _clamp(val: float, mini: float, maxi: float) -> float:
    return max(mini, min(maxi, val))

def calcul_courant_charge_optimal_a(
    soc: float,
    temperature_c: float,
    c_rate_max: float,
    capacite_ah: float,
    tension_pack_v: float,
    puissance_source_max_kw: Optional[float] = None,
    t_opt_min: float = 20.0,
    t_opt_max: float = 35.0,
    t_limit_c: float = 55.0,
    soc_seuil_cv: float = 0.8,
    pente_cv: float = 5.0
) -> float:
    """
    Calcule le courant de charge optimal (A) pour une recharge rapide et sûre.
    
    Logique de "Cell Preservation" :
    1. Base : Courant nominal = C_rate_max * Capacite_Ah
    2. Derating Thermique : Réduction si T < T_opt_min ou T > T_opt_max. Arrêt si T >= T_limit.
    3. Derating SOC : Simulation de la phase CV (Constant Voltage) après un seuil.
    4. Limitation Source : Ne pas dépasser la puissance disponible de l'Alternateur.
    """
    if soc < 0 or soc > 1:
        raise ValueError(f"SOC doit être entre 0 et 1 (reçu: {soc})")
    
    # 1. Courant de base (limite chimique)
    i_base = c_rate_max * capacite_ah
    
    # 2. Derating Thermique
    f_thermique = 1.0
    if temperature_c < t_opt_min:
        # Réduction progressive si trop froid (lithium plating risk)
        f_thermique = _clamp((temperature_c + 10) / (t_opt_min + 10), 0.0, 1.0)
    elif temperature_c > t_opt_max:
        # Réduction progressive si trop chaud (thermal runaway risk)
        f_thermique = _clamp((t_limit_c - temperature_c) / (t_limit_c - t_opt_max), 0.0, 1.0)
    
    # 3. Derating SOC (Phase CV)
    f_soc = 1.0
    if soc > soc_seuil_cv:
        # Réduction linéaire après le seuil SOC
        f_soc = _clamp(1.0 - pente_cv * (soc - soc_seuil_cv), 0.1, 1.0)
    
    i_optimal = i_base * f_thermique * f_soc
    
    # 4. Limitation par la source externe (Alternateur)
    if puissance_source_max_kw is not None and puissance_source_max_kw > 0:
        i_source_max = (puissance_source_max_kw * 1000.0) / tension_pack_v
        i_optimal = min(i_optimal, i_source_max)
    
    return float(max(0.0, i_optimal))

def estimer_puissance_refroidissement_tms_w(
    courant_a: float,
    resistance_interne_pack_ohm: float,
    delta_t_cible_k: float = 5.0,
    efficacite_tms: float = 0.8
) -> float:
    """
    Estime la puissance thermique à évacuer par le TMS pour maintenir le pack au frais.
    P_joule = R * I^2
    """
    p_joule = resistance_interne_pack_ohm * (courant_a ** 2)
    return p_joule / efficacite_tms
