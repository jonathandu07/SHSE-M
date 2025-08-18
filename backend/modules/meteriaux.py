# -*- coding: utf-8 -*-
# backend/modules/meteriaux.py
"""
Catalogue & helpers matériaux — moteur Stirling

Contenu :
- Matériaux pertinents (inox haut T°, alliages Ni, fontes/acier, Al piston,
  bronzes/aluminiums paliers, polymères tribo, céramiques réfractaires, visserie).
- Propriétés utiles pour pré-dimensionnement :
  densité, E, α, k, Rp0.2/UTS (ambiante), dé-ratings à chaud, T_service_max,
  p/PV (paliers), remarques soudabilité/corrosion.
- Profils d'exigence par sous-ensemble (heater head, régénérateur, déplaceur,
  piston, bielle/vilebrequin, paliers, visserie).
- Helpers : résistance vs température, sélection candidats, compatibilité CTE, etc.

⚠️ Données "engineering handbook" de premier niveau pour *pré-étude*.
Affiner avec fiches fournisseurs & normes pour le choix final.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import bisect
import math

# =========================
# Modèles de données
# =========================

@dataclass(frozen=True)
class Material:
    key: str
    name: str
    category: str  # "inox", "ni_alloy", "acier", "aluminium", "fonte", "bronze", "polymere", "ceramique", "visserie"
    density_kg_m3: float
    E_Pa: float  # Young
    alpha_1K: float  # dilatation linéaire (1/K)
    k_W_mK: float  # conductivité thermique
    Rp0_2_Pa: float  # limite d'élasticité (amb.)
    UTS_Pa: float    # résistance traction (amb.)
    Tmax_service_C: float
    # facteurs de réduction de résistance (amb->temp) : [(°C, facteur_sur_Rp0.2)]
    yield_reduction: List[Tuple[float, float]] = field(default_factory=list)
    # propriétés paliers (facultatives)
    p_bearing_allow_Pa: Optional[float] = None
    PV_allow_W_m2: Optional[float] = None
    # notes d'usage
    notes: str = ""
    weldable: bool = True
    corrosion: str = ""  # hints

# =========================
# Catalogue (pertinent Stirling)
# =========================

MATERIALS: Dict[str, Material] = {
    # --- Chaud / tête de chauffe / échangeurs chauds ---
    "SS310S": Material(
        key="SS310S", name="Inox 310S", category="inox",
        density_kg_m3=7900, E_Pa=190e9, alpha_1K=16e-6, k_W_mK=14.0,
        Rp0_2_Pa=205e6, UTS_Pa=515e6, Tmax_service_C=1000,
        yield_reduction=[(200,0.85),(400,0.65),(600,0.45),(800,0.30),(950,0.22)],
        notes="Très bonne tenue oxydation > 900°C; idéal coque chaude/déplaceur fin.",
        corrosion="Bonne oxydation; Cl- à éviter >300°C."
    ),
    "SS253MA": Material(
        key="SS253MA", name="Inox 253MA (EN 1.4835)", category="inox",
        density_kg_m3=7800, E_Pa=190e9, alpha_1K=16.5e-6, k_W_mK=15.0,
        Rp0_2_Pa=310e6, UTS_Pa=650e6, Tmax_service_C=1100,
        yield_reduction=[(200,0.9),(400,0.7),(600,0.5),(800,0.35),(1000,0.25)],
        notes="Aciers FeCrNi silicés; bon fluage chaud; échangeurs/cheminées."
    ),
    "IN625": Material(
        key="IN625", name="Alliage nickel Inconel 625", category="ni_alloy",
        density_kg_m3=8440, E_Pa=205e9, alpha_1K=13e-6, k_W_mK=9.8,
        Rp0_2_Pa=460e6, UTS_Pa=930e6, Tmax_service_C=1000,
        yield_reduction=[(200,0.95),(400,0.8),(600,0.65),(800,0.5),(1000,0.35)],
        notes="Excellente tenue chaud/corrosion; brasage/ soudage OK; coût élevé."
    ),
    "IN718": Material(
        key="IN718", name="Inconel 718 précipité", category="ni_alloy",
        density_kg_m3=8190, E_Pa=200e9, alpha_1K=13e-6, k_W_mK=11.4,
        Rp0_2_Pa=1000e6, UTS_Pa=1250e6, Tmax_service_C=700,
        yield_reduction=[(200,0.95),(400,0.85),(600,0.65),(700,0.5)],
        notes="Très haute résistance jusqu’à ~650–700°C; parfait tiges/axes chauds."
    ),

    # --- Froid / piston / chemise / structure ---
    "Al4032": Material(
        key="Al4032", name="Al Si 12 (4032) piston", category="aluminium",
        density_kg_m3=2680, E_Pa=73e9, alpha_1K=20.5e-6, k_W_mK=147,
        Rp0_2_Pa=240e6, UTS_Pa=380e6, Tmax_service_C=250,
        yield_reduction=[(100,0.85),(150,0.7),(200,0.55),(250,0.45)],
        notes="Faible dilatation vs 2618; stabilité dimensionnelle; idéal pistons Stirling côté froid."
    ),
    "Al2618": Material(
        key="Al2618", name="Al 2618A forgé", category="aluminium",
        density_kg_m3=2780, E_Pa=73e9, alpha_1K=22e-6, k_W_mK=160,
        Rp0_2_Pa=330e6, UTS_Pa=440e6, Tmax_service_C=250,
        yield_reduction=[(100,0.85),(150,0.7),(200,0.55),(250,0.45)],
        notes="Très tenace, pistons performants; dilate un peu plus que 4032."
    ),
    "FG250": Material(
        key="FG250", name="Fonte grise (chemise)", category="fonte",
        density_kg_m3=7100, E_Pa=110e9, alpha_1K=10.5e-6, k_W_mK=54,
        Rp0_2_Pa=200e6, UTS_Pa=250e6, Tmax_service_C=400,
        yield_reduction=[(200,0.85),(300,0.7),(400,0.55)],
        notes="Chemises autolubrifiantes (graphite); très bon rodage/segments."
    ),
    "42CrMo4": Material(
        key="42CrMo4", name="Acier allié 42CrMo4 (4140)", category="acier",
        density_kg_m3=7850, E_Pa=210e9, alpha_1K=12e-6, k_W_mK=42,
        Rp0_2_Pa=650e6, UTS_Pa=900e6, Tmax_service_C=350,
        yield_reduction=[(200,0.9),(300,0.8),(350,0.7)],
        notes="Vilebrequin, bielle; bonne ténacité; traitable (QT)."
    ),
    "17-4PH": Material(
        key="17-4PH", name="Inox précipité 17-4PH", category="inox",
        density_kg_m3=7800, E_Pa=200e9, alpha_1K=10.8e-6, k_W_mK=17,
        Rp0_2_Pa=900e6, UTS_Pa=1100e6, Tmax_service_C=315,
        yield_reduction=[(200,0.85),(300,0.7)],
        notes="Tiges/axes froids rigides avec résistance élevée; corrosion bonne."
    ),

    # --- Paliers / tribo ---
    "CuSn12": Material(
        key="CuSn12", name="Bronze étain CuSn12 (palier)", category="bronze",
        density_kg_m3=8800, E_Pa=100e9, alpha_1K=17e-6, k_W_mK=60,
        Rp0_2_Pa=220e6, UTS_Pa=300e6, Tmax_service_C=250,
        yield_reduction=[(150,0.85),(200,0.7),(250,0.55)],
        p_bearing_allow_Pa=12e6, PV_allow_W_m2=2.0e6,
        notes="Palier lisse universel; bonne résistance au grippage."
    ),
    "AlSn20Cu": Material(
        key="AlSn20Cu", name="Alliage palier AlSn20Cu", category="bronze",
        density_kg_m3=7200, E_Pa=80e9, alpha_1K=21e-6, k_W_mK=130,
        Rp0_2_Pa=120e6, UTS_Pa=220e6, Tmax_service_C=200,
        yield_reduction=[(120,0.85),(160,0.7),(200,0.55)],
        p_bearing_allow_Pa=8e6, PV_allow_W_m2=1.6e6,
        notes="Très bon en lubrification limite; dépôts tendres anti-grip."
    ),
    "PTFE_Bronze": Material(
        key="PTFE_Bronze", name="Composite PTFE/bronze (bagues)", category="polymere",
        density_kg_m3=2300, E_Pa=2.0e9, alpha_1K=120e-6, k_W_mK=0.25,
        Rp0_2_Pa=30e6, UTS_Pa=45e6, Tmax_service_C=200,
        yield_reduction=[(100,0.7),(150,0.5),(200,0.35)],
        p_bearing_allow_Pa=5e6, PV_allow_W_m2=1.0e6,
        notes="Faibles frottements, usage léger/à sec, faibles rigidité & T°."
    ),

    # --- Joints / faibles frottements haut T° ---
    "Graphite_Ep": Material(
        key="Graphite_Ep", name="Graphite expansé (joints haute T°)", category="ceramique",
        density_kg_m3=1100, E_Pa=5e9, alpha_1K=3e-6, k_W_mK=100,
        Rp0_2_Pa=20e6, UTS_Pa=40e6, Tmax_service_C=450,
        yield_reduction=[(300,0.7),(450,0.5)],
        notes="Joints statiques haute T°, inertie chimique; pas pour pièces structurelles."
    ),

    # --- Visserie (rappel) ---
    "Bolt_8_8": Material(
        key="Bolt_8_8", name="Vis acier classe 8.8", category="visserie",
        density_kg_m3=7850, E_Pa=210e9, alpha_1K=12e-6, k_W_mK=45,
        Rp0_2_Pa=640e6, UTS_Pa=800e6, Tmax_service_C=150,
        notes="Assemblages généraux; éviter >150°C sans requalification."
    ),
    "Bolt_10_9": Material(
        key="Bolt_10_9", name="Vis acier classe 10.9", category="visserie",
        density_kg_m3=7850, E_Pa=210e9, alpha_1K=12e-6, k_W_mK=45,
        Rp0_2_Pa=900e6, UTS_Pa=1000e6, Tmax_service_C=150,
        notes="Haute résistance; serrage contrôlé."
    ),
    "Bolt_A2_70": Material(
        key="Bolt_A2_70", name="Vis inox A2-70", category="visserie",
        density_kg_m3=8000, E_Pa=190e9, alpha_1K=16e-6, k_W_mK=15,
        Rp0_2_Pa=210e6, UTS_Pa=700e6, Tmax_service_C=300,
        notes="Bonne corrosion; résistance plus faible; ok jusqu’à ~300°C."
    ),
}

# =========================
# Profils d’exigence par pièce
# =========================

PART_PROFILES = {
    # zone chaude
    "heater_head": {
        "Tmax_C": 850,
        "categories": ["ni_alloy", "inox"],
        "min_yield_amb_Pa": 200e6,
        "note": "Coque chaude / échangeur côté brûleur.",
    },
    "regenerator_screen": {
        "Tmax_C": 750,
        "categories": ["inox", "ni_alloy"],
        "min_yield_amb_Pa": 200e6,
        "note": "Tamis/feutre métallique régénérateur; privilégier inox 310S/253MA.",
    },
    "displacer_shell": {
        "Tmax_C": 700,
        "categories": ["inox", "ni_alloy"],
        "min_yield_amb_Pa": 200e6,
        "note": "Coque mince, faible densité privilégiée; 310S/253MA; IN625 si sévère.",
    },
    # zone froide / mobile
    "piston": {
        "Tmax_C": 200,
        "categories": ["aluminium"],
        "min_yield_amb_Pa": 200e6,
        "note": "Piston côté froid; 4032 privilégié pour stabilité thermique.",
    },
    "cylinder_liner": {
        "Tmax_C": 200,
        "categories": ["fonte", "inox"],
        "min_yield_amb_Pa": 180e6,
        "note": "Chemise fonte graphitée (rodage/segments).",
    },
    "crankshaft": {
        "Tmax_C": 120,
        "categories": ["acier"],
        "min_yield_amb_Pa": 550e6,
        "note": "Vilebrequin/bielle : 42CrMo4; 17-4PH si corrosion.",
    },
    "bearing_journal": {
        "Tmax_C": 120,
        "categories": ["bronze", "polymere"],
        "min_yield_amb_Pa": 80e6,
        "note": "Paliers lisses : CuSn12 ou AlSn; PTFE/bronze si charge modérée.",
    },
    "fasteners": {
        "Tmax_C": 120,
        "categories": ["visserie"],
        "min_yield_amb_Pa": 200e6,
        "note": "8.8 / 10.9; A2-70 si corrosion.",
    },
    "hot_rod": {
        "Tmax_C": 650,
        "categories": ["ni_alloy", "inox"],
        "min_yield_amb_Pa": 400e6,
        "note": "Tige déplaceur côté chaud : IN718/IN625/310S selon T°.",
    },
}

# =========================
# Helpers — sélection & calculs
# =========================

def strength_factor_at_T(mat: Material, T_C: float) -> float:
    """Renvoie le facteur multiplicatif sur Rp0.2 à la température T (interpolation piècewise, clamp)."""
    if not mat.yield_reduction:
        return 1.0
    pts = sorted(mat.yield_reduction, key=lambda x: x[0])
    temps = [t for t,_ in pts]
    facs = [f for _,f in pts]
    if T_C <= temps[0]:
        return facs[0]
    if T_C >= temps[-1]:
        return facs[-1]
    i = bisect.bisect_left(temps, T_C)
    # interpolation linéaire
    t0,t1 = temps[i-1], temps[i]
    f0,f1 = facs[i-1], facs[i]
    return f0 + (f1 - f0) * ( (T_C - t0) / (t1 - t0) )

def yield_at_T(mat: Material, T_C: float) -> float:
    """Retourne Rp0.2(T) ≈ Rp0.2(amb) * facteur(T)."""
    return mat.Rp0_2_Pa * strength_factor_at_T(mat, T_C)

def select_candidates(part: str, Tmax_C: float, require_bearing: bool=False) -> List[Material]:
    """
    Retourne la liste triée des matériaux compatibles avec le profil 'part' et la T° max.
    Tri par adéquation température puis densité (léger d'abord pour pièces mobiles).
    """
    profile = PART_PROFILES.get(part)
    if not profile:
        raise KeyError(f"Profil inconnu: {part}")
    cats = set(profile["categories"])
    out: List[Material] = []
    for m in MATERIALS.values():
        if m.category not in cats:
            continue
        if Tmax_C > m.Tmax_service_C + 1e-9:
            continue
        if m.Rp0_2_Pa < profile["min_yield_amb_Pa"]:
            continue
        if require_bearing and (m.p_bearing_allow_Pa is None):
            continue
        out.append(m)
    # tri : marge de T° décroissante, puis densité croissante
    def score(m: Material):
        dT = (m.Tmax_service_C - Tmax_C)
        return (-dT, m.density_kg_m3)
    return sorted(out, key=score)

def cte_mismatch(a: Material, b: Material, d_ref_m: float, dT_C: float) -> Tuple[float, float]:
    """
    Calcule l'écart radial dû aux CTE (Δr ≈ 0.5 * Δα * d_ref * ΔT) et l'écart diamétral ΔD.
    Utile pour jeux piston/chemise, déplaceur/cylindre, bagues.
    """
    delta_alpha = (a.alpha_1K - b.alpha_1K)
    delta_D = delta_alpha * d_ref_m * dT_C
    delta_r = 0.5 * delta_D
    return delta_r, delta_D

def bearing_limits(material_key: str) -> Tuple[Optional[float], Optional[float]]:
    """Retourne (p_allow, PV_allow) pour un matériau de palier si défini."""
    m = MATERIALS[material_key]
    return (m.p_bearing_allow_Pa, m.PV_allow_W_m2)

def suggest_fastener_class(corrosive: bool, Tmax_C: float) -> str:
    """Heuristique simple de classe de vis."""
    if corrosive and Tmax_C <= MATERIALS["Bolt_A2_70"].Tmax_service_C:
        return "A2-70"
    if Tmax_C <= 120:
        return "8.8"
    return "10.9"

def joinability_hint(m: Material) -> str:
    if m.category in ("inox","acier"):
        return "Soudable (TIG/MIG). Traitements thermiques selon nuance."
    if m.category == "ni_alloy":
        return "Soudage/brazage possibles, contrôle fissuration/MCIC recommandé."
    if m.category == "aluminium":
        return "Soudable; prudence sur T_HAZ & déformations; usinage aisé."
    if m.category == "bronze":
        return "Brasage / emmanchement; usinage facile."
    if m.category == "polymere":
        return "Collage/emmanchement; éviter T° locales élevées."
    if m.category == "ceramique":
        return "Jointage par compression/graphite; collage selon grade."
    return "Voir fournisseur."

# =========================
# API conviviale
# =========================

def choose_material_for_part(part: str, Tmax_C: float, prefer_light: bool=False,
                             require_bearing: bool=False) -> Material:
    """
    Sélectionne un "meilleur" matériau pour une pièce.
    - prefer_light: favorise la densité (pour masses alternatives)
    - require_bearing: impose p/PV définis (paliers)
    """
    cands = select_candidates(part, Tmax_C, require_bearing=require_bearing)
    if not cands:
        raise RuntimeError(f"Aucun matériau ne satisfait {part} à {Tmax_C}°C.")
    if prefer_light:
        cands = sorted(cands, key=lambda m: (m.density_kg_m3, -m.Tmax_service_C))
    return cands[0]

def describe_material(key: str) -> str:
    """Résumé humain court pour logs/CLI."""
    m = MATERIALS[key]
    s = (f"{m.name} [{m.category}] ρ={m.density_kg_m3:.0f} kg/m³, E={m.E_Pa/1e9:.0f} GPa, "
         f"α={m.alpha_1K*1e6:.1f} µm/m·K, k={m.k_W_mK:.1f} W/mK, Rp0.2={m.Rp0_2_Pa/1e6:.0f} MPa, "
         f"UTS={m.UTS_Pa/1e6:.0f} MPa, Tmax={m.Tmax_service_C:.0f}°C. {m.notes}")
    return s

# =========================
# Démo rapide
# =========================

if __name__ == "__main__":
    # Exemples d’usage
    hot = choose_material_for_part("heater_head", Tmax_C=800)
    print("[heater_head]", describe_material(hot.key))
    disp = choose_material_for_part("displacer_shell", Tmax_C=650, prefer_light=True)
    print("[displacer_shell]", describe_material(disp.key))
    piston = choose_material_for_part("piston", Tmax_C=180, prefer_light=True)
    print("[piston]", describe_material(piston.key))
    # Compatibilité CTE piston/chemise (180°C -> 20°C : ΔT ≈ 160 K)
    dr, dD = cte_mismatch(MATERIALS["Al4032"], MATERIALS["FG250"], d_ref_m=0.08, dT_C=160)
    print(f"Δr CTE piston/chemise (160K, Ø80) ≈ {dr*1e6:.1f} µm (ΔD={dD*1e6:.1f} µm)")
    # Palier
    be = choose_material_for_part("bearing_journal", Tmax_C=90, require_bearing=True)
    print("[palier]", describe_material(be.key), "p_allow=", be.p_bearing_allow_Pa, "PV_allow=", be.PV_allow_W_m2)
    # Visserie
    cls = suggest_fastener_class(corrosive=False, Tmax_C=80)
    print("Classe vis suggérée:", cls)
