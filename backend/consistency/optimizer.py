import math
from .dimensionnement import calcul_cylindree_totale

class ArchitectureOptimizer:
    def __init__(self, bore_max_mm=133.3, up_max_ms=16.0, ratio_sb_min=0.8, ratio_sb_max=1.2):
        self.bore_max_m = bore_max_mm / 1000.0
        self.up_max_ms = up_max_ms
        self.ratio_sb_min = ratio_sb_min
        self.ratio_sb_max = ratio_sb_max

    def optimize(self, p_vilo_w: float, rpm: float, pme_pa: float, l_max_m=1.8, w_max_m=1.2):
        """
        Recherche le meilleur N entre 2 et 16.
        """
        vd_tot_m3 = calcul_cylindree_totale(p_vilo_w, pme_pa, rpm)
        results = []

        for n in range(2, 17):
            config = self._evaluate_n(n, vd_tot_m3, rpm, pme_pa, l_max_m, w_max_m)
            if config["valide"]:
                results.append(config)
        
        # Tri par score (le plus bas est le mieux)
        results.sort(key=lambda x: x["score"])
        return results

    def _evaluate_n(self, n, vd_tot, rpm, pme, l_limit, w_limit):
        vd_u = vd_tot / n
        
        # 1. Détermination de la géométrie (Hypothèse Carrée B=S par défaut pour init)
        # V_u = pi * B^2 * S / 4. Si S=B: B = (4 * V_u / pi)^(1/3)
        bore = ( (4 * vd_u) / math.pi ) ** (1/3)
        stroke = bore
        
        # Ajustement si B dépasse B_max
        if bore > self.bore_max_m:
            bore = self.bore_max_m
            stroke = vd_u / (math.pi * (bore**2) / 4)
        
        # 2. Vérification des contraintes
        up = (2.0 * stroke * rpm) / 60.0 # Vitesse moyenne piston
        ratio_sb = stroke / bore
        
        valide = True
        alertes = []
        
        if bore > self.bore_max_m + 1e-6:
            valide = False
            alertes.append(f"Alésage {bore*1000:.1f}mm > {self.bore_max_m*1000:.1f}mm")
        
        if up > self.up_max_ms + 1e-2:
            valide = False
            alertes.append(f"Vitesse Piston {up:.1f}m/s > {self.up_max_ms:.1f}m/s")
            
        if not (self.ratio_sb_min <= ratio_sb <= self.ratio_sb_max):
            valide = False
            alertes.append(f"Ratio S/B {ratio_sb:.2f} hors plage [{self.ratio_sb_min}, {self.ratio_sb_max}]")

        # 3. Calcul du Score
        # Masse estimée (Scale avec Vd et N)
        # Formule empirique : M = K1 * Vd + K2 * N
        masse_kg = (vd_tot * 1e6 * 0.15) + (n * 12.0)
        
        # Coût Maintenance (Modèle réaliste)
        # C = Fixe + N * (Pièces) + Pénalité Charge (PME)
        cout_maint = 500.0 + (n * 150.0) + (pme / 1e5 * 20.0)
        
        # Pénalité Equilibrage / Vibrations (L2, L3, V6 etc)
        # On simplifie : malus sur petits N
        vibration_penalty = 1000.0 / n
        
        score = masse_kg * 2.0 + (cout_maint / 10.0) + vibration_penalty
        
        # Choix Architecture simplifiée pour le Score (Packaging)
        # N=2..6 -> L (En ligne), N>6 -> V (En V)
        arch = "L" if n <= 6 else "V"
        
        return {
            "n_cyl": n,
            "architecture": arch,
            "bore_mm": bore * 1000.0,
            "stroke_mm": stroke * 1000.0,
            "vd_tot_cc": vd_tot * 1e6,
            "vd_u_cc": vd_u * 1e6,
            "pme_bar": pme / 1e5,
            "piston_speed_ms": up,
            "ratio_sb": ratio_sb,
            "masse_kg": masse_kg,
            "cout_maint": cout_maint,
            "score": score,
            "valide": valide,
            "alertes": alertes
        }
