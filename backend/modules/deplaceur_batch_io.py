# -*- coding: utf-8 -*-
# backend/modules/deplaceur_batch_io.py
"""
Batch I/O (Pandas) pour le déplaceur : CSV -> calcul vectorisé -> CSV.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from .deplaceur_vector import size_deplaceur_vector

DEFAULTS = {
    "k_phase": 1.0,
    "dome_extra_clearance_m": 0.02,
    "radial_clearance_cold_m": np.nan,  # NaN => auto
    "min_hot_clearance_m": 0.08e-3,
    "alpha_material_1K": 12e-6,
    "deltaT_hotK": 500.0,
    "manuf_tol_radial_m": 0.03e-3,
    "shell_thickness_m": 0.5e-3,
    "cap_thickness_m": 0.6e-3,
    "material_density": 8000.0,
    "use_hollow_core": True,
    "core_density": 50.0,
    "rod_length_m": np.nan,  # NaN => auto
    "rod_diameter_m": 4e-3,
    "young_modulus_Pa": 200e9,
    "rpm": 600.0,
    "gas_dynamic_dp_Pa": 2000.0,
    "acceptable_leak_index": 1.5e-4,
}

REQUIRED = ["bore_m", "stroke_m"]

def from_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

def _with_defaults(df: pd.DataFrame) -> pd.DataFrame:
    for k, v in DEFAULTS.items():
        if k not in df.columns:
            df[k] = v
    return df

def _opt(x):
    # Convertit NaN -> None pour déclencher l’auto (ex. clearances, rod_length)
    return None if (isinstance(x, float) and np.isnan(x)) else x

def run_batch(df: pd.DataFrame) -> pd.DataFrame:
    df = _with_defaults(df)

    # Entrées obligatoires
    if not set(REQUIRED).issubset(df.columns):
        missing = list(set(REQUIRED) - set(df.columns))
        raise ValueError(f"Colonnes manquantes: {missing}")

    res = size_deplaceur_vector(
        bore_m=df["bore_m"].to_numpy(),
        stroke_m=df["stroke_m"].to_numpy(),
        k_phase=df["k_phase"].to_numpy(),
        dome_extra_clearance_m=df["dome_extra_clearance_m"].to_numpy(),
        radial_clearance_cold_m=None if df["radial_clearance_cold_m"].isna().all()
            else df["radial_clearance_cold_m"].to_numpy(),
        min_hot_clearance_m=df["min_hot_clearance_m"].to_numpy(),
        alpha_material_1K=df["alpha_material_1K"].to_numpy(),
        deltaT_hotK=df["deltaT_hotK"].to_numpy(),
        manuf_tol_radial_m=df["manuf_tol_radial_m"].to_numpy(),
        shell_thickness_m=df["shell_thickness_m"].to_numpy(),
        cap_thickness_m=df["cap_thickness_m"].to_numpy(),
        material_density=df["material_density"].to_numpy(),
        use_hollow_core=df["use_hollow_core"].to_numpy(),
        core_density=df["core_density"].to_numpy(),
        rod_length_m=None if df["rod_length_m"].isna().all()
            else df["rod_length_m"].to_numpy(),
        rod_diameter_m=df["rod_diameter_m"].to_numpy(),
        young_modulus_Pa=df["young_modulus_Pa"].to_numpy(),
        rpm=df["rpm"].to_numpy(),
        gas_dynamic_dp_Pa=df["gas_dynamic_dp_Pa"].to_numpy(),
        acceptable_leak_index=df["acceptable_leak_index"].to_numpy(),
    )

    out = df.copy()
    msg_map = {0:"OK", 1:"Jeu chaud insuffisant", 2:"Flambage tige", 3:"Fuite annulaire"}
    out["ok"] = res["ok"]
    out["message"] = pd.Categorical([msg_map[int(x)] for x in res["message_id"].ravel()])
    out["disp_outer_diameter_cold_mm"] = np.round(res["disp_outer_diameter_cold_m"]*1000.0, 3)
    out["disp_outer_diameter_hot_mm"]  = np.round(res["disp_outer_diameter_hot_m"]*1000.0, 3)
    out["disp_length_mm"]              = np.round(res["disp_length_m"]*1000.0, 2)
    out["disp_stroke_mm"]              = np.round(res["disp_stroke_m"]*1000.0, 2)
    out["radial_clearance_cold_mm"]    = np.round(res["radial_clearance_cold_m"]*1e3, 3)
    out["radial_clearance_hot_mm"]     = np.round(res["radial_clearance_hot_m"]*1e3, 3)
    out["mass_total_g"]                = np.round(res["mass_total_kg"]*1e3, 2)
    out["vmax_m_s"]                    = np.round(res["vmax_m_s"], 3)
    out["axial_force_N"]               = np.round(res["axial_force_PaN"], 2)
    out["rod_euler_ok"]                = res["rod_euler_ok"]
    out["leak_index"]                  = np.round(res["leak_index"], 6)
    out["leak_ok"]                     = res["leak_ok"]
    return out

def to_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)
