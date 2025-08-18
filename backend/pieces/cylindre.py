# -*- coding: utf-8 -*-
# backend\pieces\cylindre.py
"""
Dimensionnement de cylindre(s) pour moteur Stirling à partir d'une puissance cible.
Méthode: bilan par BMEP (Mean Effective Pressure) + contraintes mécaniques.
Auteur: ChatGPT (GPT-5 Thinking)

Hypothèses clés (modifiables) :
- On travaille avec une pression moyenne effective (BMEP) atteignable par un Stirling correctement conçu
  (chauffe convenable, bon régénérateur, pertes contenues). Valeur par défaut ~200 kPa.
- Le rendement mécanique (frottements, entraînement, auxiliaires) est pris en compte.
- La vitesse moyenne de piston (m/s) est limitée pour la longévité.
- Le script trouve le plus petit nombre de cylindres qui satisfait toutes les contraintes.
- Résultat = nombre de cylindres, alésage (B), course (S), volume balayé/cylindre, etc.

NOTE IMPORTANTE :
Ce dimensionnement par BMEP est une étape 0-1 (architecture cylindre). Pour un Stirling
avec déplaceur (haut chaud, bas froid), il faudra ensuite dimensionner volumes morts,
chauffeur/refroidisseur, régénérateur, angle de phase, matériaux, et faire une vérif via
modèle de Schmidt/iso-therme si tu veux affiner la puissance et les rendements.
"""

import math
from dataclasses import dataclass

@dataclass
class SizingInputs:
    # Exigence fonctionnelle
    power_W: float              # Puissance demandée (W) - côté frein/arbre
    rpm: float                  # Régime (tr/min) visé
    eta_mech: float             # Rendement mécanique (0..1), ex. 0.85

    # Performance cycle (méthode BMEP)
    # Option A: donner directement un BMEP plausible (Pa) — recommandé pour un premier sizing.
    p_me: float = 200e3         # BMEP en Pascal (ex. 200 kPa)
    # Option B (facultative): si tu préfères partir d'une pression moyenne de charge :
    use_pmean_model: bool = False
    p_mean: float = 1.0e6       # Pression moyenne de charge (Pa), ex. 10 bar = 1.0e6 Pa
    k_me: float = 0.20          # Facteur pour approx p_me ≈ k_me * p_mean (0.15–0.35 typ. selon design)

    # Contraintes mécaniques de longévité
    upiston_max: float = 2.0    # Vitesse moyenne de piston max (m/s) (1.5–3.0 selon longévité souhaitée)
    bore_max: float = 0.10      # Alésage maximum (m)
    stroke_to_bore: float = 1.0 # Rapport S/B (1.0 ≈ course égale au diamètre)
    n_cyl_max: int = 12         # Nombre de cylindres max à tester

    # Stratégie si rien ne passe : on peut réduire le régime jusqu’à min_rpm
    allow_rpm_reduce: bool = True
    min_rpm: float = 300.0      # Régime mini autorisé si on doit baisser pour tenir Upiston

@dataclass
class SizingResult:
    ok: bool
    message: str
    n_cyl: int = None
    rpm: float = None
    bore_m: float = None
    stroke_m: float = None
    Vs_cyl_m3: float = None
    Vs_total_m3: float = None
    p_me_used_Pa: float = None

def mean_piston_speed(stroke_m: float, rpm: float) -> float:
    # Upiston(m/s) = 2 * S(m) * RPM / 60
    return 2.0 * stroke_m * rpm / 60.0

def solve_bore_stroke_from_Vs(Vs: float, S_over_B: float):
    """
    Vs = (pi/4) * B^2 * S  avec  S = (S/B) * B = S_over_B * B
       => Vs = (pi/4) * B^3 * S_over_B
       => B = [ 4*Vs / (pi * S_over_B) ]^(1/3)
    """
    B = (4.0 * Vs / (math.pi * S_over_B)) ** (1.0/3.0)
    S = S_over_B * B
    return B, S

def size_stirling_cylinders(inp: SizingInputs) -> SizingResult:
    # Si on préfère dériver p_me d'une pression moyenne de charge
    p_me = inp.p_me
    if inp.use_pmean_model:
        p_me = inp.k_me * inp.p_mean

    # Tours par seconde
    rps = inp.rpm / 60.0

    # Volume balayé total requis:
    # P_b = p_me * Vs_total * rps * eta_mech   => Vs_total = P_b / (p_me * rps * eta_mech)
    denominator = p_me * rps * inp.eta_mech
    if denominator <= 0:
        return SizingResult(False, "Paramètres invalides (p_me, rpm ou eta_mech).")

    Vs_total = inp.power_W / denominator  # m^3
    if Vs_total <= 0:
        return SizingResult(False, "Puissance ou paramètres non cohérents (Vs_total <= 0).")

    # Recherche du plus petit nombre de cylindres qui respecte toutes les contraintes
    def try_all(rpm_val: float):
        rps_val = rpm_val / 60.0
        for n_cyl in range(1, inp.n_cyl_max + 1):
            Vs_cyl = Vs_total / n_cyl
            # Calcule B et S depuis Vs_cyl et le rapport S/B
            B, S = solve_bore_stroke_from_Vs(Vs_cyl, inp.stroke_to_bore)

            # Contraintes
            if B > inp.bore_max:
                continue
            Up = mean_piston_speed(S, rpm_val)
            if Up > inp.upiston_max:
                continue

            # OK: retourne le premier (le plus petit n_cyl) valide
            return SizingResult(
                ok=True,
                message="Dimensionnement réussi.",
                n_cyl=n_cyl,
                rpm=rpm_val,
                bore_m=B,
                stroke_m=S,
                Vs_cyl_m3=Vs_cyl,
                Vs_total_m3=Vs_total,
                p_me_used_Pa=p_me
            )
        return None

    # 1) Essayer au régime nominal
    res = try_all(inp.rpm)
    if res:
        return res

    # 2) Optionnellement, baisser le régime pour respecter la vitesse de piston
    if inp.allow_rpm_reduce:
        rpm = inp.rpm
        # Descente par paliers raisonnables
        for rpm_candidate in [max(inp.min_rpm, x) for x in
                              [int(inp.rpm*0.8), int(inp.rpm*0.6), int(inp.rpm*0.5),
                               int(inp.rpm*0.4), int(inp.rpm*0.33), int(inp.rpm*0.25)]]:
            if rpm_candidate < inp.min_rpm:
                continue
            res = try_all(float(rpm_candidate))
            if res:
                return res

    # 3) Échec — proposer une piste d’ajustement
    return SizingResult(
        ok=False,
        message=("Aucune solution ne respecte les contraintes. "
                 "Essaie d'augmenter p_me, le nombre max de cylindres, l'alésage max, "
                 "ou de réduire la vitesse de piston et/ou le régime.")
    )

# =======================
# Exemple d'utilisation :
# =======================
if __name__ == "__main__":
    # RÉGLE ICI TES EXIGENCES ET CONTRAINTES
    inp = SizingInputs(
        power_W=3000.0,      # 3 kW demandés à l'arbre
        rpm=1500.0,          # régime visé
        eta_mech=0.85,       # rendement mécanique

        # Méthode BMEP directe (recommandé pour commencer)
        p_me=200e3,          # 200 kPa de BMEP

        # Si tu veux passer par p_mean : mets use_pmean_model=True (et ajuste p_mean, k_me)
        use_pmean_model=False,
        p_mean=1.0e6,
        k_me=0.20,

        # Contraintes mécaniques
        upiston_max=2.0,     # m/s
        bore_max=0.10,       # 100 mm
        stroke_to_bore=1.0,  # S/B
        n_cyl_max=12,

        # Stratégie en cas d'échec
        allow_rpm_reduce=True,
        min_rpm=300.0
    )

    res = size_stirling_cylinders(inp)

    # Affichage propre
    print("=== RÉSULTAT DIMENSIONNEMENT CYLINDRE STIRLING ===")
    print(f"Puissance demandée : {inp.power_W:.1f} W")
    if inp.use_pmean_model:
        print(f"Modèle p_mean: p_mean={inp.p_mean/1e5:.2f} bar, k_me={inp.k_me:.2f} -> p_me≈{res.p_me_used_Pa/1e5:.2f} bar" if res.ok else
              f"Modèle p_mean: p_mean={inp.p_mean/1e5:.2f} bar, k_me={inp.k_me:.2f}")
    else:
        print(f"BMEP utilisé    : {inp.p_me/1e5:.2f} bar")

    if res.ok:
        print(f"Nombre cylindres: {res.n_cyl}")
        print(f"Régime retenu   : {res.rpm:.0f} tr/min")
        print(f"Alésage (B)     : {res.bore_m*1000:.1f} mm")
        print(f"Course  (S)     : {res.stroke_m*1000:.1f} mm")
        print(f"V balayé/cyl    : {res.Vs_cyl_m3*1e6:.1f} cm³")
        print(f"V balayé total  : {res.Vs_total_m3*1e6:.1f} cm³")
        Up = mean_piston_speed(res.stroke_m, res.rpm)
        print(f"Vitesse piston  : {Up:.3f} m/s (limite {inp.upiston_max} m/s)")
        print(res.message)
    else:
        print("ÉCHEC :", res.message)
