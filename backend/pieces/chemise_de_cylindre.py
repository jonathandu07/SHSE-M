# -*- coding: utf-8 -*-
# backend/pieces/chemise_de_cylindre.py
"""
Chemise de cylindre (liner) — pré-dimensionnement
- Ø intérieur = B (à froid, hors jeu choisi)
- Épaisseur liée à la pression interne (contrainte cerclage)
- Prend en compte paroi mince ou épaisse (Lame), au besoin par recherche numérique.
- Vérifie les jeux à chaud/froid (dilatations) et propose un jeu à froid pour atteindre
  un jeu radial minimal à chaud.

⚠️ Pré-étude : pour un design final, valider avec un modèle détaillé (sertissage/bloc,
rainures, nervures, gradients thermiques, fatigue, flambage axial si chemise libre).

Auteur : ChatGPT (GPT-5 Thinking)
"""

from __future__ import annotations
from dataclasses import dataclass
import math

# ----------------------------
# Entrées / Sorties
# ----------------------------

@dataclass
class ChemiseInputs:
    # Géométrie fonctionnelle
    bore_m: float                    # B (m) — diamètre intérieur cible (à froid)
    longueur_m: float                # longueur utile de chemise (m)

    # Chargement pression
    p_interne_Pa: float              # pression interne max (Pa)
    fs: float = 1.5                  # facteur de sécurité sur contrainte (>=1)

    # Matériau de la chemise (ambiante)
    sigma_allow_Pa: float = 220e6    # contrainte admissible (Pa) (ex. fonte/acier)
    E_Pa: float = 200e9              # module d'Young (Pa) — info
    density_kg_m3: float = 7800.0    # masse volumique (kg/m³)
    alpha_1K: float = 11e-6          # CTE (1/K) chemise (ex. fonte ~10–11e-6)

    # Température / jeux
    T_cold_C: float = 20.0
    T_hot_C: float = 150.0           # niveau moyen côté froid (chemise)
    piston_alpha_1K: float = 20.5e-6 # CTE piston (ex. Al4032)
    piston_cold_diam_m: float | None = None  # si None: on suppose piston ≈ B - 2*jeu_froid
    radial_clearance_cold_m: float | None = 0.02e-3  # jeu radial cible à froid (m); None => calculé pour tenir min_hot
    radial_clearance_hot_min_m: float = 0.01e-3      # jeu radial minimal requis à chaud (m)
    manuf_tol_radial_m: float = 0.01e-3              # tolérance/ovalisation prise en compte (m)

    # Critères de calcul
    thin_wall_limit: float = 0.10     # seuil t/r_i pour paroi mince

@dataclass
class ChemiseResult:
    ok: bool
    message: str

    # Géométrie
    bore_cold_m: float = 0.0
    epaisseur_m: float = 0.0
    t_over_ri: float = 0.0

    # Contraintes (max)
    hoop_stress_Pa: float = 0.0       # σθ max calculée
    method: str = "thin"              # "thin" ou "thick"

    # Jeux & dilatations
    piston_cold_diam_m: float = 0.0
    clearance_cold_radial_m: float = 0.0
    chemise_hot_diam_m: float = 0.0
    piston_hot_diam_m: float = 0.0
    clearance_hot_radial_m: float = 0.0
    recommended_cold_clearance_m: float = 0.0

    # Masse
    masse_kg: float = 0.0

# ----------------------------
# Outils internes
# ----------------------------

def _thin_wall_required_t(ri: float, p: float, sigma_allow: float, fs: float) -> float:
    """
    Paroi mince: σθ ≈ p * r_i / t  => t_req = p * r_i * fs / sigma_allow
    """
    return (p * ri * fs) / max(sigma_allow, 1.0)

def _lame_sigma_theta_max(ri: float, ro: float, p_i: float) -> float:
    """
    Contrainte circonférentielle maximale pour un cylindre épais fermé, pression interne p_i,
    pression externe ~0. Max au rayon intérieur:
      σθ(r_i) = p_i * ( (ro^2 + ri^2) / (ro^2 - ri^2) )
    """
    if ro <= ri * (1.0 + 1e-6):
        return float("inf")
    return p_i * ((ro**2 + ri**2) / (ro**2 - ri**2))

def _thick_wall_required_t(ri: float, p: float, sigma_allow: float, fs: float) -> float:
    """
    Inverse du critère Lame sur σθ(ri) <= sigma_allow / fs.
    On résout pour ro par dichotomie, puis t = ro - ri.
    """
    target = max(sigma_allow, 1.0) / max(fs, 1.0)
    # bornes : t de 0 -> 0.5*ri (raisonnable)
    lo, hi = 1e-6, 0.5 * ri
    for _ in range(100):
        t = 0.5 * (lo + hi)
        ro = ri + t
        s = _lame_sigma_theta_max(ri, ro, p)
        if s > target:
            lo = t
        else:
            hi = t
    return hi

def _mass_cylindrical_shell(ro: float, ri: float, L: float, rho: float) -> float:
    vol = math.pi * (ro**2 - ri**2) * L
    return rho * vol

# ----------------------------
# Calcul principal
# ----------------------------

def size_chemise(inp: ChemiseInputs) -> ChemiseResult:
    B = inp.bore_m
    ri = 0.5 * B
    p = inp.p_interne_Pa

    # 1) Épaisseur requise (essai paroi mince d'abord)
    t_thin = _thin_wall_required_t(ri, p, inp.sigma_allow_Pa, inp.fs)
    t_over_ri = t_thin / ri

    if t_over_ri <= inp.thin_wall_limit:
        method = "thin"
        t = t_thin
        hoop = p * ri / max(t, 1e-12)  # cohérent avec la formule
    else:
        method = "thick"
        t = _thick_wall_required_t(ri, p, inp.sigma_allow_Pa, inp.fs)
        ro = ri + t
        hoop = _lame_sigma_theta_max(ri, ro, p)

    ro = ri + t

    # 2) Jeux & dilatations (de T_cold -> T_hot)
    dT = inp.T_hot_C - inp.T_cold_C
    # Diamètres à chaud
    D_chem_hot = B * (1.0 + inp.alpha_1K * dT)
    if inp.piston_cold_diam_m is not None:
        D_pis_cold = inp.piston_cold_diam_m
    else:
        # Si jeu à froid fourni, on l'utilise pour déduire D piston
        jc = inp.radial_clearance_cold_m if inp.radial_clearance_cold_m is not None else 0.02e-3
        D_pis_cold = max(B - 2.0 * jc, 1e-6)
    D_pis_hot = D_pis_cold * (1.0 + inp.piston_alpha_1K * dT)

    # Jeux
    if inp.radial_clearance_cold_m is None:
        # Déterminer un jeu à froid qui garantit ≥ min_hot à chaud (avec tolérance)
        # clearance_hot = clearance_cold + 0.5*(D_chem_hot - B) - 0.5*(D_pis_hot - D_pis_cold) - manuf_tol
        # => clearance_cold = clearance_hot + 0.5*(ΔD_pis - ΔD_chem) + manuf_tol
        deltaD_chem = D_chem_hot - B
        deltaD_pis  = D_pis_hot - D_pis_cold
        clearance_cold = (inp.radial_clearance_hot_min_m
                          + 0.5 * (deltaD_pis - deltaD_chem)
                          + inp.manuf_tol_radial_m)
    else:
        clearance_cold = inp.radial_clearance_cold_m

    clearance_hot = max(
        0.5 * (D_chem_hot - D_pis_hot) - inp.manuf_tol_radial_m,
        0.0
    )

    # 3) Masse
    masse = _mass_cylindrical_shell(ro, ri, inp.longueur_m, inp.density_kg_m3)

    # 4) Verdict
    issues = []
    if clearance_hot < inp.radial_clearance_hot_min_m - 1e-12:
        issues.append("jeu_chaud_insuffisant")
    ok = len(issues) == 0
    msg = "OK" if ok else " / ".join(issues)

    return ChemiseResult(
        ok=ok, message=msg,
        bore_cold_m=B,
        epaisseur_m=t,
        t_over_ri=t/ri,
        hoop_stress_Pa=hoop,
        method=method,
        piston_cold_diam_m=D_pis_cold,
        clearance_cold_radial_m=clearance_cold,
        chemise_hot_diam_m=D_chem_hot,
        piston_hot_diam_m=D_pis_hot,
        clearance_hot_radial_m=clearance_hot,
        recommended_cold_clearance_m=clearance_cold,
        masse_kg=masse
    )

# ----------------------------
# Démo / exécution directe
# ----------------------------

if __name__ == "__main__":
    # Exemple : B=80 mm, L=90 mm, p=1.2 MPa pic (Stirling modéré), fonte/acier
    inp = ChemiseInputs(
        bore_m=0.080,
        longueur_m=0.090,
        p_interne_Pa=1.2e6,
        fs=1.6,
        sigma_allow_Pa=220e6,    # fonte ~200–250 MPa
        E_Pa=190e9,
        density_kg_m3=7200.0,    # fonte
        alpha_1K=10.5e-6,
        T_cold_C=20.0,
        T_hot_C=150.0,
        piston_alpha_1K=20.5e-6, # Al4032
        radial_clearance_cold_m=None,      # laisse calculer pour respecter min_hot
        radial_clearance_hot_min_m=0.01e-3,
        manuf_tol_radial_m=0.02e-3
    )
    res = size_chemise(inp)

    print("=== CHEMISE DE CYLINDRE ===")
    print(f"Méthode                    : {res.method} (t/ri = {res.t_over_ri:.3f})")
    print(f"Épaisseur t                : {res.epaisseur_m*1000:.2f} mm")
    print(f"σθ max                     : {res.hoop_stress_Pa/1e6:.1f} MPa")
    print(f"Jeu radial froid (reco)    : {res.recommended_cold_clearance_m*1e6:.2f} µm")
    print(f"Jeu radial à chaud         : {res.clearance_hot_radial_m*1e6:.2f} µm  (min {inp.radial_clearance_hot_min_m*1e6:.0f})")
    print(f"Masse chemise              : {res.masse_kg*1e3:.1f} g")
    print(res.message)
