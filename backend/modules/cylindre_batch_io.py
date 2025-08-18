# backend\modules\cylindre_batch_io.py
"""
Utilitaires batch (Pandas) pour vectoriser l'entrée/sortie.
- from_csv(...): charge et applique des valeurs par défaut si colonnes manquantes
- run_batch(df, **kwargs): passe df aux calculs vectorisés et retourne un df résultats aligné
- to_csv(...): exporte
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from .cylindre_vector import size_stirling_cylinders_vector

DEFAULTS = {
    "eta_mech": 0.85,
    "p_me": 200e3,
    "use_pmean_model": False,
    "p_mean": 1.0e6,
    "k_me": 0.20,
    "upiston_max": 2.0,
    "bore_max": 0.10,
    "stroke_to_bore": 1.0,
    "n_cyl_max": 12,
    "allow_rpm_reduce": True,
    "min_rpm": 300.0,
}

REQUIRED = ["power_W", "rpm", "eta_mech"]

def from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df

def _with_defaults(df: pd.DataFrame) -> pd.DataFrame:
    for k, v in DEFAULTS.items():
        if k not in df.columns:
            df[k] = v
    return df

def run_batch(df: pd.DataFrame) -> pd.DataFrame:
    df = _with_defaults(df)
    # Entrées
    power = df["power_W"].to_numpy()
    rpm   = df["rpm"].to_numpy()
    eta   = df["eta_mech"].to_numpy()

    res = size_stirling_cylinders_vector(
        power_W=power, rpm=rpm, eta_mech=eta,
        p_me=df["p_me"].iat[0] if df["p_me"].nunique()==1 else df["p_me"].to_numpy(),
        use_pmean_model=df["use_pmean_model"].iat[0] if df["use_pmean_model"].nunique()==1 else df["use_pmean_model"].to_numpy(),
        p_mean=df["p_mean"].iat[0] if df["p_mean"].nunique()==1 else df["p_mean"].to_numpy(),
        k_me=df["k_me"].iat[0] if df["k_me"].nunique()==1 else df["k_me"].to_numpy(),
        upiston_max=df["upiston_max"].iat[0] if df["upiston_max"].nunique()==1 else df["upiston_max"].to_numpy(),
        bore_max=df["bore_max"].iat[0] if df["bore_max"].nunique()==1 else df["bore_max"].to_numpy(),
        stroke_to_bore=df["stroke_to_bore"].iat[0] if df["stroke_to_bore"].nunique()==1 else df["stroke_to_bore"].to_numpy(),
        n_cyl_max=int(df["n_cyl_max"].iat[0]) if df["n_cyl_max"].nunique()==1 else df["n_cyl_max"].to_numpy(),
        allow_rpm_reduce=df["allow_rpm_reduce"].iat[0] if df["allow_rpm_reduce"].nunique()==1 else df["allow_rpm_reduce"].to_numpy(),
        min_rpm=df["min_rpm"].iat[0] if df["min_rpm"].nunique()==1 else df["min_rpm"].to_numpy(),
    )

    out = df.copy()
    # Map message_id -> texte court
    msg_map = {0:"OK", 1:"Param invalides", 2:"Vs<=0", 3:"Aucune solution"}
    out["ok"] = res["ok"]
    out["message"] = pd.Categorical([msg_map[int(x)] for x in res["message_id"].ravel()])
    out["n_cyl"] = res["n_cyl"]
    out["rpm_out"] = np.round(res["rpm"], 2)
    out["bore_mm"] = np.round(res["bore_m"]*1000.0, 3)
    out["stroke_mm"] = np.round(res["stroke_m"]*1000.0, 3)
    out["Vs_cyl_cm3"] = np.round(res["Vs_cyl_m3"]*1e6, 3)
    out["Vs_total_cm3"] = np.round(res["Vs_total_m3"]*1e6, 3)
    out["p_me_bar"] = np.round(res["p_me_used_Pa"]/1e5, 3)
    return out

def to_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)