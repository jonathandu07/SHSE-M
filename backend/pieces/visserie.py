# -*- coding: utf-8 -*-
# backend/pieces/visserie.py
"""
Sélection automatique de visserie métrique ISO pour un assemblage soumis à traction/cisaillement.

Fonctionnement (pré-dimensionnement) :
- Entrées : charges externes (traction/cisaillement), mode "friction" (anti-glissement) ou "bearing"
  (cisaillement en appui), matériaux, facteurs de sécurité, environnement (corrosion), etc.
- Recherche : (diamètre, classe, nombre de vis) minimaux respectant :
  • pas de séparation du joint sous traction,
  • contrainte traction vis <= Sp (charge d'épreuve) / FS,
  • mode "friction" : μ * Σ(F_preload) >= V_ext * FS_shear,
  • mode "bearing" : cisaillement tige et pression de palier (trou) admissibles.
- Sorties : choix vis, classe, quantité, précharge cible, couple de serrage, marges FoS.

⚠️ Pré-dimensionnement : à valider / détailler (écrous, rondelles, filets engagés, serrage réel,
tolérances, surfaces, coefficients, fatigue).
"""

from __future__ import annotations
from dataclasses import dataclass
import math
from typing import List, Tuple, Dict, Optional

# --------------------------
# Petites bases normalisées
# --------------------------

# Aire résistante filetée (ISO 898-1 / ISO 724) — valeurs typiques (m²)
# (arrondies pour pré-dimensionnement)
METRIC_TABLE: Dict[str, Dict[str, float]] = {
    "M4":  {"d": 0.004,  "pitch": 0.7e-3,  "As": 8.78e-6},
    "M5":  {"d": 0.005,  "pitch": 0.8e-3,  "As": 14.2e-6},
    "M6":  {"d": 0.006,  "pitch": 1.0e-3,  "As": 20.1e-6},
    "M8":  {"d": 0.008,  "pitch": 1.25e-3, "As": 36.6e-6},
    "M10": {"d": 0.010,  "pitch": 1.5e-3,  "As": 58.0e-6},
    "M12": {"d": 0.012,  "pitch": 1.75e-3, "As": 84.3e-6},
    "M14": {"d": 0.014,  "pitch": 2.0e-3,  "As": 115.0e-6},
    "M16": {"d": 0.016,  "pitch": 2.0e-3,  "As": 157.0e-6},
    "M20": {"d": 0.020,  "pitch": 2.5e-3,  "As": 245.0e-6},
}

# Classes de vis (valeurs de référence, Pa)
# Rp0.2 ~ limite d'élasticité ; Sp ~ charge d'épreuve (proof) ~ 0.9*Rm (selon classe)
BOLT_CLASSES: Dict[str, Dict[str, float]] = {
    "8.8":   {"Rm": 800e6,  "Rp": 0.8*800e6,  "Sp": 0.9*800e6},
    "10.9":  {"Rm": 1000e6, "Rp": 0.9*1000e6, "Sp": 0.9*1000e6},
    "12.9":  {"Rm": 1200e6, "Rp": 0.9*1200e6, "Sp": 0.9*1200e6},
    "A2-70": {"Rm": 700e6,  "Rp": 0.45*700e6, "Sp": 0.7*700e6},  # inox austénitique ~ ordre de grandeur
}

# Coefficients usuels
SHEAR_FACTOR = 0.58  # τ_all ≈ 0.58*Rp (von Mises simplifié)
TORQUE_K = 0.20      # T ≈ k * F_preload * d_nom (lubrifié léger)
MU_STEEL_DRY = 0.14  # µ de frottement acier/acier propre (ordre de grandeur)

# --------------------------
# Données d'entrée / sortie
# --------------------------

@dataclass
class ScrewSelectionInputs:
    # Charges globales (ultimes)
    axial_tension_N: float = 0.0     # traction externe (séparation)
    shear_N: float = 0.0             # cisaillement total sur l’assemblage
    mode: str = "friction"           # "friction" (anti-glissement) ou "bearing"

    # Configuration
    n_bolts_max: int = 12
    bolt_sizes: Optional[List[str]] = None           # ex: ["M6","M8","M10"]; None => toutes
    preferred_classes: Optional[List[str]] = None    # ex: ["10.9","8.8"]; None => 10.9 → 8.8 → 12.9 → A2-70

    # Joint & surfaces (pour friction et séparation)
    friction_mu: float = MU_STEEL_DRY
    joint_stiffness_ratio: float = 0.25  # part de la charge axiale externe qui va dans la vis (0.2–0.4)
    preload_ratio_of_Sp: float = 0.7     # F_preload ≈ 0.7 * Sp * As (serrage cible)
    use_washers: bool = True

    # Pièces en appui (pour bearing)
    plate_thickness_m: float = 0.006     # épaisseur pièce portante (m)
    bearing_allow_Pa: float = 250e6      # pression de palier trou-âme admissible (Pa)

    # Sécurité
    FS_tension: float = 1.25
    FS_shear: float = 1.25
    FS_bearing: float = 1.25
    FS_noslip: float = 1.30   # marge sur critère anti-glissement (friction)

    # Environnement
    corrosive_env: bool = False  # si True, privilégier inox (A2-70) sinon acier carbone

@dataclass
class ScrewSelectionResult:
    ok: bool
    message: str
    bolt_size: str = ""
    bolt_class: str = ""
    bolt_count: int = 0

    # Données de la vis choisie
    d_nom_m: float = 0.0
    pitch_m: float = 0.0
    As_m2: float = 0.0

    # Précharge & couple
    preload_per_bolt_N: float = 0.0
    torque_estimate_Nm: float = 0.0

    # Vérifs (marges)
    fos_tension: float = 0.0
    fos_shear: float = 0.0
    fos_bearing: float = 0.0
    noslip_ok: bool = True
    joint_separation_ok: bool = True

    # Détails
    mode_used: str = ""
    hints: List[str] = None

# --------------------------
# Utilitaires
# --------------------------

def _iter_sizes(order: Optional[List[str]]) -> List[str]:
    if order is None:
        return list(METRIC_TABLE.keys())
    return [s for s in order if s in METRIC_TABLE]

def _iter_classes(pref: Optional[List[str]], corrosive: bool) -> List[str]:
    base = ["10.9", "8.8", "12.9", "A2-70"]
    if corrosive:
        base = ["A2-70", "10.9", "8.8", "12.9"]
    if pref:
        base = [c for c in pref if c in BOLT_CLASSES] + [c for c in base if c not in pref]
    # enlever doublons en gardant l'ordre
    seen, out = set(), []
    for c in base:
        if c not in seen:
            out.append(c); seen.add(c)
    return out

def _bearing_pressure_per_bolt(shear_per_bolt: float, d_nom: float, t_plate: float) -> float:
    # pression de palier ~ F / (d * t)
    return shear_per_bolt / max(d_nom * t_plate, 1e-12)

# --------------------------
# Noyau de sélection
# --------------------------

def select_screws(inp: ScrewSelectionInputs) -> ScrewSelectionResult:
    sizes = _iter_sizes(inp.bolt_sizes)
    classes = _iter_classes(inp.preferred_classes, inp.corrosive_env)

    # Ordonner par diamètre croissant (puis par classe)
    sizes = sorted(sizes, key=lambda k: METRIC_TABLE[k]["d"])

    best: Optional[ScrewSelectionResult] = None

    for size in sizes:
        d = METRIC_TABLE[size]["d"]
        pitch = METRIC_TABLE[size]["pitch"]
        As = METRIC_TABLE[size]["As"]

        for cl in classes:
            mat = BOLT_CLASSES[cl]
            Sp = mat["Sp"]             # charge d'épreuve
            Rp = mat["Rp"]             # limite élastique approx
            tau_allow = SHEAR_FACTOR * Rp

            # Précharge proposée
            F_pre = inp.preload_ratio_of_Sp * Sp * As

            # Tension admissible (à l'épreuve)
            Ft_allow = Sp * As / inp.FS_tension

            # Portion de charge axiale allant dans la vis (approx)
            # ΔF_bolt ≈ C * F_ext  (C ~ 0.2–0.4)
            deltaF = inp.joint_stiffness_ratio * inp.axial_tension_N

            # Nombre de vis à tester (1..n_bolts_max)
            for n in range(1, inp.n_bolts_max + 1):
                hints = []

                # ——— TENSION / SÉPARATION ———
                # Charge de traction par vis : ΔF/n
                F_ax_per = deltaF / n
                # Joint ne doit pas s’ouvrir : n*F_pre >= F_ext * FS_tension
                separation_ok = (n * F_pre) >= (inp.axial_tension_N * inp.FS_tension)

                # Contrainte de traction par vis (pire cas approx) :
                #   F_bolt_max ≈ F_pre + F_ax_per  (si externalité augmente la charge vis)
                F_bolt_max = F_pre + F_ax_per
                tension_ok = F_bolt_max <= Ft_allow

                # ——— CISAILLEMENT ———
                # Répartition uniforme :
                V_per = inp.shear_N / max(n, 1)

                if inp.mode.lower() == "friction":
                    # anti-glissement : μ * ΣF_pre >= V_ext * FS
                    noslip_ok = (inp.friction_mu * n * F_pre) >= (inp.shear_N * inp.FS_noslip)

                    # Si friction passe, pas besoin de check cisaillement tige/bearing (mais on les regarde pour info)
                    shear_ok = True
                    bearing_ok = True

                    fos_shear = 9.99
                    fos_bearing = 9.99
                else:
                    noslip_ok = True
                    # cisaillement tige (simple cisaillement par défaut)
                    V_allow = tau_allow * As / inp.FS_shear
                    shear_ok = V_per <= V_allow
                    fos_shear = V_allow / max(V_per, 1e-9)

                    # pression de palier (trou)
                    p_b = _bearing_pressure_per_bolt(V_per, d, inp.plate_thickness_m)
                    p_allow = inp.bearing_allow_Pa / inp.FS_bearing
                    bearing_ok = p_b <= p_allow
                    fos_bearing = p_allow / max(p_b, 1e-9)

                # ——— Décision pour cette config ———
                all_ok = tension_ok and separation_ok and shear_ok and bearing_ok and noslip_ok

                if all_ok:
                    T_est = TORQUE_K * F_pre * d
                    fos_t = Ft_allow / max(F_bolt_max, 1e-9)

                    res = ScrewSelectionResult(
                        ok=True,
                        message="OK",
                        bolt_size=size,
                        bolt_class=cl,
                        bolt_count=n,
                        d_nom_m=d,
                        pitch_m=pitch,
                        As_m2=As,
                        preload_per_bolt_N=F_pre,
                        torque_estimate_Nm=T_est,
                        fos_tension=fos_t,
                        fos_shear=(9.99 if inp.mode.lower()=="friction" else fos_shear),
                        fos_bearing=(9.99 if inp.mode.lower()=="friction" else fos_bearing),
                        noslip_ok=noslip_ok,
                        joint_separation_ok=separation_ok,
                        mode_used=inp.mode.lower(),
                        hints=hints,
                    )

                    # Choix : prioriser le diamètre le plus petit, puis le plus petit nombre de vis,
                    # puis la classe la plus "basse" (moins coûteuse).
                    if best is None:
                        best = res
                    else:
                        better = False
                        if res.d_nom_m < best.d_nom_m - 1e-9:
                            better = True
                        elif abs(res.d_nom_m - best.d_nom_m) < 1e-9 and res.bolt_count < best.bolt_count:
                            better = True
                        elif (abs(res.d_nom_m - best.d_nom_m) < 1e-9 and
                              res.bolt_count == best.bolt_count and
                              _class_rank(res.bolt_class) > _class_rank(best.bolt_class)):
                            # préférence pour classe plus "faible" (8.8 > 10.9 > 12.9 > A2-70), donc rang plus haut
                            better = True
                        if better:
                            best = res

    if best is None:
        # Si rien ne passe, construire un message utile
        tips = []
        if inp.mode.lower() == "friction":
            tips.append("• augmenter le nombre de vis ou la précharge (meilleure classe)")
            tips.append("• augmenter µ (surfaces propres/traitées) ou passer en mode 'bearing'")
        else:
            tips.append("• passer à un diamètre supérieur / plus de vis")
            tips.append("• augmenter épaisseur de pièce ou limite de pression de palier")
            tips.append("• utiliser une classe supérieure (10.9/12.9)")

        return ScrewSelectionResult(
            ok=False,
            message="Aucune configuration ne satisfait toutes les contraintes.\n" + "\n".join(tips),
        )

    # Hints additionnels
    if best.mode_used == "friction" and best.noslip_ok:
        # proposer rondelles HV si charge élevée
        if inp.use_washers and best.preload_per_bolt_N > 0.5 * BOLT_CLASSES[best.bolt_class]["Sp"] * best.As_m2:
            best.hints.append("Rondelles trempées conseillées (répartition pression / réduction pertes de précharge).")
    if inp.corrosive_env and best.bolt_class != "A2-70":
        best.hints.append("Environnement corrosif : envisager A2-70 ou traitement anticorrosion.")
    best.hints.append(f"Couple de serrage estimé: {best.torque_estimate_Nm:.1f} N·m (k≈{TORQUE_K}).")

    return best

def _class_rank(cl: str) -> int:
    # rang plus élevé = priorité plus forte à rester “classe plus faible” (coût/ductilité)
    order = ["8.8", "10.9", "12.9", "A2-70"]
    # On inverse la logique : 8.8 -> 4, 10.9 -> 3, 12.9 -> 2, A2-70 -> 1
    if cl not in order:
        return 0
    return len(order) - order.index(cl)

# --------------------------
# Démo / exécution directe
# --------------------------

if __name__ == "__main__":
    # Exemple 1 — Mode friction (anti-glissement), traction + cisaillement
    inp = ScrewSelectionInputs(
        axial_tension_N=6000.0,     # traction externe
        shear_N=4000.0,             # cisaillement
        mode="friction",
        n_bolts_max=8,
        bolt_sizes=["M6","M8","M10"],
        preferred_classes=["8.8","10.9"],
        friction_mu=0.16,
        joint_stiffness_ratio=0.3,
        preload_ratio_of_Sp=0.7,
        plate_thickness_m=0.006,
        bearing_allow_Pa=260e6,
        FS_tension=1.25, FS_shear=1.25, FS_bearing=1.25, FS_noslip=1.3,
        corrosive_env=False
    )
    res = select_screws(inp)
    print("=== VIS SERIE — Exemple 1 ===")
    print(f"OK ? {res.ok} | {res.message}")
    if res.ok:
        print(f"Choix : {res.bolt_count}× {res.bolt_size} classe {res.bolt_class}")
        print(f"Précharge/vis : {res.preload_per_bolt_N:.0f} N  | Couple ~ {res.torque_estimate_Nm:.1f} N·m")
        print(f"FoS traction : {res.fos_tension:.2f} | No-slip : {res.noslip_ok}")

    # Exemple 2 — Mode bearing (appui), cisaillement pur
    inp2 = ScrewSelectionInputs(
        axial_tension_N=0.0,
        shear_N=12000.0,
        mode="bearing",
        n_bolts_max=6,
        bolt_sizes=["M6","M8","M10"],
        preferred_classes=["8.8","10.9"],
        plate_thickness_m=0.008,
        bearing_allow_Pa=280e6,
        FS_shear=1.3, FS_bearing=1.3,
        corrosive_env=True
    )
    res2 = select_screws(inp2)
    print("\n=== VIS SERIE — Exemple 2 ===")
    print(f"OK ? {res2.ok} | {res2.message}")
    if res2.ok:
        print(f"Choix : {res2.bolt_count}× {res2.bolt_size} classe {res2.bolt_class}")
        print(f"Précharge/vis : {res2.preload_per_bolt_N:.0f} N | Couple ~ {res2.torque_estimate_Nm:.1f} N·m")
        print(f"FoS cisaillement : {res2.fos_shear:.2f} | FoS palier : {res2.fos_bearing:.2f}")
        print("Notes :", *res2.hints, sep="\n - ")
