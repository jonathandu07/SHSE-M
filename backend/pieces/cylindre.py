# backend/pieces/cylindre.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import math

# ============================================================
# Imports (si tes modules existent déjà dans ton projet)
# ============================================================

try:
    from backend.modules.moteur_thermique.calcul_cylindree import calcul_cylindree_unitaire
except Exception:
    def calcul_cylindree_unitaire(*, alesage_m: float, course_m: float, allow_zero: bool = False, return_details: bool = False) -> float:
        if alesage_m <= 0 or course_m <= 0:
            raise ValueError("alesage_m et course_m doivent être > 0")
        return (math.pi * (alesage_m ** 2) / 4.0) * course_m

try:
    from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import (
        calcul_epaisseur_cylindre_mince,
        calcul_epaisseur_cylindre_lame,
    )
except Exception:
    def calcul_epaisseur_cylindre_mince(
        *,
        pression_pa: float,
        rayon_interne_m: float,
        contrainte_admissible_pa: float,
        include_longitudinale: bool = False,
        facteur_securite: float = 1.0,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float:
        # Modèle mince (Barlow) : sigma_theta ~= p*ri/t
        if rayon_interne_m <= 0 or contrainte_admissible_pa <= 0 or facteur_securite <= 0:
            raise ValueError("rayon_interne_m, contrainte_admissible_pa, facteur_securite doivent être > 0")
        p = abs(float(pression_pa))
        sigma_eff = contrainte_admissible_pa / facteur_securite
        if sigma_eff <= 0:
            raise ValueError("Contrainte admissible effective <= 0")
        t = (p * rayon_interne_m) / sigma_eff
        return max(0.0, t) if clamp_non_negative else t

    def calcul_epaisseur_cylindre_lame(
        *,
        pression_interne_pa: float,
        rayon_interne_m: float,
        contrainte_admissible_pa: float,
        facteur_securite: float = 1.0,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float:
        # Cylindre épais (Lamé, p_ext=0), contrainte cerclage max à l'alésage:
        # sigma_theta_i = p * (ri^2 + ro^2) / (ro^2 - ri^2)
        # -> ro^2 = ((sigma + p)/(sigma - p)) * ri^2, avec sigma = sigma_eff
        ri = float(rayon_interne_m)
        if ri <= 0 or contrainte_admissible_pa <= 0 or facteur_securite <= 0:
            raise ValueError("rayon_interne_m, contrainte_admissible_pa, facteur_securite doivent être > 0")
        p = abs(float(pression_interne_pa))
        sigma_eff = contrainte_admissible_pa / facteur_securite
        if sigma_eff <= p:
            # impossible d'avoir une solution si sigma_eff <= p
            raise ValueError("sigma_eff doit être > pression_interne_pa pour Lamé (sinon épaisseur infinie).")
        ro2 = ((sigma_eff + p) / (sigma_eff - p)) * (ri ** 2)
        ro = math.sqrt(ro2)
        t = ro - ri
        return max(0.0, t) if clamp_non_negative else t


# ============================================================
# Helpers
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strictly else v >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v

def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})

def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: list[dict]) -> list[dict]:
        seen: set[Tuple[str, str]] = set()
        out: list[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out
    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


# ============================================================
# Pièce : Cylindre (calculatoire, sans heuristiques “inventées”)
# ============================================================

@dataclass(frozen=True)
class Cylindre:
    """
    Objectif :
    - Produire un maximum de grandeurs 100% calculées
    - Zéro “valeur devinée” : tout ce qui dépend d’une donnée externe doit être fourni
      (matériau, thermo, etc.), sinon reporté comme inconnue.
    - Option strict=True : si une inconnue reste, on lève une erreur.

    Modèle :
    - Dimensionnement pression interne via cylindre mince (Barlow) + cylindre épais (Lamé),
      et choix conservatif t = max(t_mince, t_lame).
    - Contraintes vérifiées (cerclage/longitudinale) et marges.
    - Déformations (pression/thermique) uniquement si E, nu, alpha, ΔT sont fournis.
    - Masse/inerties uniquement si densité + longueurs sont fournies.
    """

    # Géométrie
    alesage_m: float
    course_m: float
    longueur_utile_m: float  # longueur utile du fût (pour masse/surface), sans couvercles
    # Pressions
    pression_service_pa: float
    pression_max_pa: float
    pression_externe_pa: float = 0.0  # si besoin (sinon 0)
    # Matériau / admissible
    contrainte_admissible_pa: Optional[float] = None  # si connue directement
    limite_elastique_pa: Optional[float] = None       # sinon fournir Re et on calcule admissible = Re / FS
    facteur_securite: float = 2.0

    # Propriétés mécaniques (pour déformation)
    module_young_pa: Optional[float] = None
    coefficient_poisson: Optional[float] = None

    # Thermique (dilatation / conduction)
    coefficient_dilatation_1_k: Optional[float] = None  # alpha
    delta_temperature_k: Optional[float] = None         # ΔT
    conductivite_w_m_k: Optional[float] = None          # k
    h_interne_w_m2_k: Optional[float] = None            # convection interne
    h_externe_w_m2_k: Optional[float] = None            # convection externe

    # Masse
    densite_kg_m3: Optional[float] = None

    # Paramètres d’assemblage (facultatif, mais calculable si fourni)
    epaisseur_bride_m: Optional[float] = None
    largeur_bride_m: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "geometrie": {},
            "dimensionnement": {},
            "contraintes": {},
            "deformations": {},
            "thermique": {},
            "masse": {},
            "inerties": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ----------------------------
        # 1) Validation & entrées
        # ----------------------------
        D = _req_pos("alesage_m", self.alesage_m)
        S = _req_pos("course_m", self.course_m)
        L = _req_pos("longueur_utile_m", self.longueur_utile_m)
        p_serv = _req_pos("pression_service_pa", self.pression_service_pa, strictly=False)
        p_max = _req_pos("pression_max_pa", self.pression_max_pa, strictly=False)
        p_ext = _req_pos("pression_externe_pa", self.pression_externe_pa, strictly=False)
        FS = _req_pos("facteur_securite", self.facteur_securite)

        if p_max < p_serv:
            rapport["notes_modele"].append("pression_max_pa < pression_service_pa : dimensionnement fait sur pression_max_pa quand même.")

        rapport["entrees"].update({
            "alesage_m": D,
            "course_m": S,
            "longueur_utile_m": L,
            "pression_service_pa": p_serv,
            "pression_max_pa": p_max,
            "pression_externe_pa": p_ext,
            "facteur_securite": FS,
            "contrainte_admissible_pa": self.contrainte_admissible_pa,
            "limite_elastique_pa": self.limite_elastique_pa,
        })

        ri = 0.5 * D
        Ai = math.pi * (ri ** 2)  # aire piston / section interne

        # Admissible effective (obligatoire pour dimensionner)
        sigma_adm: Optional[float] = None
        if self.contrainte_admissible_pa is not None:
            sigma_adm = _req_pos("contrainte_admissible_pa", self.contrainte_admissible_pa)
        elif self.limite_elastique_pa is not None:
            Re = _req_pos("limite_elastique_pa", self.limite_elastique_pa)
            sigma_adm = Re  # admissible brute; FS appliqué dans les formules
            rapport["notes_modele"].append("contrainte_admissible_pa déduite de limite_elastique_pa (FS appliqué ensuite).")
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "contrainte admissible",
                "Impossible de dimensionner l’épaisseur sans contrainte_admissible_pa ou limite_elastique_pa.",
            )

        # ----------------------------
        # 2) Géométrie calculée
        # ----------------------------
        V_swept = float(calcul_cylindree_unitaire(alesage_m=D, course_m=S, allow_zero=False, return_details=False))
        surface_interne_laterale = math.pi * D * L  # fût interne
        volume_interne_total = Ai * L

        rapport["geometrie"].update({
            "rayon_interne_m": ri,
            "aire_section_interne_m2": Ai,
            "cylindree_unitaire_m3": V_swept,
            "volume_interne_total_m3": volume_interne_total,
            "surface_interne_laterale_m2": surface_interne_laterale,
        })

        # ----------------------------
        # 3) Efforts pression
        # ----------------------------
        F_piston_service = p_serv * Ai
        F_piston_max = p_max * Ai
        rapport["dimensionnement"].update({
            "force_pression_piston_service_N": F_piston_service,
            "force_pression_piston_max_N": F_piston_max,
        })

        # ----------------------------
        # 4) Épaisseur : mince + Lamé (conservatif)
        # ----------------------------
        t_mince: Optional[float] = None
        t_lame: Optional[float] = None
        t_retenue: Optional[float] = None

        # On dimensionne sur Δp interne-externe (conservatif)
        delta_p = max(0.0, (p_max - p_ext))

        if sigma_adm is not None:
            # Modèle mince
            t_mince = float(calcul_epaisseur_cylindre_mince(
                pression_pa=delta_p,
                rayon_interne_m=ri,
                contrainte_admissible_pa=sigma_adm,
                include_longitudinale=False,
                facteur_securite=FS,
                clamp_non_negative=True,
                return_details=False,
            ))

            # Modèle Lamé (épais)
            try:
                t_lame = float(calcul_epaisseur_cylindre_lame(
                    pression_interne_pa=delta_p,
                    rayon_interne_m=ri,
                    contrainte_admissible_pa=sigma_adm,
                    facteur_securite=FS,
                    clamp_non_negative=True,
                    return_details=False,
                ))
            except ValueError as e:
                # typiquement si sigma_eff <= p
                _push_inconnue(rapport, "impossibles", "épaisseur Lamé", str(e))
                t_lame = None

            # Choix conservatif
            candidates = [x for x in [t_mince, t_lame] if isinstance(x, (int, float)) and math.isfinite(float(x))]
            if candidates:
                t_retenue = max(candidates)
            else:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "épaisseur cylindre",
                    "Impossible de déterminer une épaisseur retenue (aucun modèle calculable).",
                )
        else:
            _push_inconnue(rapport, "impossibles", "épaisseur cylindre", "Pas de sigma_adm -> pas de dimensionnement pression.")

        rapport["dimensionnement"].update({
            "delta_p_dimensionnement_pa": delta_p,
            "epaisseur_mince_m": t_mince,
            "epaisseur_lame_m": t_lame,
            "epaisseur_retenue_m": t_retenue,
        })

        # ----------------------------
        # 5) Contraintes & marges (avec t_retenue)
        # ----------------------------
        if t_retenue is not None and t_retenue > 0:
            ro = ri + t_retenue
            Do = 2.0 * ro

            # Contraintes mince (référence)
            sigma_theta_mince = (delta_p * ri) / t_retenue if t_retenue > 0 else None
            sigma_long_mince = (delta_p * ri) / (2.0 * t_retenue) if t_retenue > 0 else None

            # Contraintes Lamé (au rayon interne), si ro défini
            # A = (p_i*ri^2 - p_o*ro^2)/(ro^2 - ri^2)
            # B = (ri^2*ro^2*(p_i - p_o))/(ro^2 - ri^2)
            # sigma_theta(ri) = A + B/ri^2
            ri2 = ri * ri
            ro2 = ro * ro
            denom = (ro2 - ri2)
            if denom <= 0:
                _push_inconnue(rapport, "impossibles", "contraintes Lamé", "ro^2 - ri^2 <= 0 (géométrie invalide).")
                sigma_theta_lame_i = None
                sigma_r_lame_i = None
            else:
                A = (delta_p * ri2 - 0.0 * ro2) / denom  # p_ext=0 dans Lamé fallback (delta_p déjà)
                B = (ri2 * ro2 * (delta_p - 0.0)) / denom
                sigma_theta_lame_i = A + (B / ri2)
                sigma_r_lame_i = A - (B / ri2)  # doit ~ -p_i

            # Marges
            marge_theta_mince = None
            marge_theta_lame = None
            if sigma_adm is not None:
                sigma_eff = sigma_adm / FS
                if sigma_theta_mince is not None and sigma_eff > 0:
                    marge_theta_mince = sigma_eff / sigma_theta_mince if sigma_theta_mince != 0 else None
                if sigma_theta_lame_i is not None and sigma_eff > 0:
                    marge_theta_lame = sigma_eff / sigma_theta_lame_i if sigma_theta_lame_i != 0 else None

            # Critère paroi mince
            ratio_t_sur_r = t_retenue / ri
            paroi_mince_ok = ratio_t_sur_r <= 0.10

            rapport["geometrie"].update({
                "rayon_externe_m": ro,
                "diametre_externe_m": Do,
                "ratio_t_sur_ri": ratio_t_sur_r,
            })

            rapport["contraintes"].update({
                "sigma_cerclage_mince_pa": sigma_theta_mince,
                "sigma_longitudinale_mince_pa": sigma_long_mince,
                "sigma_cerclage_lame_au_ri_pa": sigma_theta_lame_i,
                "sigma_radiale_lame_au_ri_pa": sigma_r_lame_i,
                "marge_cerclage_mince": marge_theta_mince,
                "marge_cerclage_lame": marge_theta_lame,
            })

            rapport["verifications"].update({
                "hypothese_paroi_mince_ok": paroi_mince_ok,
                "note_paroi_mince": "OK (t/ri<=0.10)" if paroi_mince_ok else "NON (utiliser Lamé/épais)",
            })
        else:
            _push_inconnue(rapport, "impossibles", "contraintes", "Impossible sans epaisseur_retenue_m > 0.")

        # ----------------------------
        # 6) Déformations (pression + thermique) : 100% calcul si E, nu, alpha, ΔT fournis
        # ----------------------------
        if t_retenue is not None and t_retenue > 0:
            # 6.1 Dilatation sous pression (approx mince, extrémités fermées)
            if self.module_young_pa is not None and self.coefficient_poisson is not None:
                E = _req_pos("module_young_pa", self.module_young_pa)
                nu = _req_pos("coefficient_poisson", self.coefficient_poisson, strictly=False)

                # εθ = (σθ - ν σL)/E
                sigma_theta = (delta_p * ri) / t_retenue
                sigma_long = (delta_p * ri) / (2.0 * t_retenue)
                eps_theta = (sigma_theta - nu * sigma_long) / E
                delta_ri_p = eps_theta * ri
                delta_D_p = 2.0 * delta_ri_p

                rapport["deformations"].update({
                    "epsilon_cerclage_sous_pression": eps_theta,
                    "augmentation_rayon_interne_pression_m": delta_ri_p,
                    "augmentation_diametre_interne_pression_m": delta_D_p,
                })
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "déformations sous pression",
                    "Calculables si module_young_pa et coefficient_poisson sont fournis.",
                )

            # 6.2 Dilatation thermique
            if self.coefficient_dilatation_1_k is not None and self.delta_temperature_k is not None:
                alpha = _req_pos("coefficient_dilatation_1_k", self.coefficient_dilatation_1_k)
                dT = _req_finite("delta_temperature_k", self.delta_temperature_k)
                delta_D_th = alpha * D * dT
                delta_ri_th = 0.5 * delta_D_th
                rapport["deformations"].update({
                    "augmentation_diametre_interne_thermique_m": delta_D_th,
                    "augmentation_rayon_interne_thermique_m": delta_ri_th,
                })
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "dilatation thermique",
                    "Calculable si coefficient_dilatation_1_k et delta_temperature_k sont fournis.",
                )
        # sinon déjà marqué impossible via épaisseur

        # ----------------------------
        # 7) Thermique : résistances (conduction + convection) si données fournies
        # ----------------------------
        if t_retenue is not None and t_retenue > 0 and self.conductivite_w_m_k is not None:
            k = _req_pos("conductivite_w_m_k", self.conductivite_w_m_k)
            ro = ri + t_retenue

            # Résistance conduction cylindre : Rcond = ln(ro/ri)/(2πkL)
            R_cond = math.log(ro / ri) / (2.0 * math.pi * k * L)
            rapport["thermique"]["R_conduction_K_W"] = R_cond

            # Convection interne/externe (si fournis)
            if self.h_interne_w_m2_k is not None:
                h_i = _req_pos("h_interne_w_m2_k", self.h_interne_w_m2_k)
                A_i = 2.0 * math.pi * ri * L
                R_hi = 1.0 / (h_i * A_i)
                rapport["thermique"]["R_convection_interne_K_W"] = R_hi
            else:
                _push_inconnue(rapport, "partielles", "R convection interne", "Calculable si h_interne_w_m2_k est fourni.")

            if self.h_externe_w_m2_k is not None:
                h_o = _req_pos("h_externe_w_m2_k", self.h_externe_w_m2_k)
                A_o = 2.0 * math.pi * ro * L
                R_ho = 1.0 / (h_o * A_o)
                rapport["thermique"]["R_convection_externe_K_W"] = R_ho
            else:
                _push_inconnue(rapport, "partielles", "R convection externe", "Calculable si h_externe_w_m2_k est fourni.")

            # Résistance totale si toutes présentes
            R_tot = None
            if "R_convection_interne_K_W" in rapport["thermique"] and "R_convection_externe_K_W" in rapport["thermique"]:
                R_tot = (
                    rapport["thermique"]["R_convection_interne_K_W"]
                    + rapport["thermique"]["R_conduction_K_W"]
                    + rapport["thermique"]["R_convection_externe_K_W"]
                )
                rapport["thermique"]["R_totale_K_W"] = R_tot
        else:
            if self.conductivite_w_m_k is None:
                _push_inconnue(rapport, "partielles", "thermique (conduction/convection)", "Calculable si conductivite_w_m_k est fournie (et h_i/h_o pour convection).")

        # ----------------------------
        # 8) Masse + inerties (tube) si densité fournie
        # ----------------------------
        if t_retenue is not None and t_retenue > 0:
            ro = ri + t_retenue
            section_metal = math.pi * (ro * ro - ri * ri)
            volume_metal = section_metal * L

            rapport["masse"].update({
                "section_metal_m2": section_metal,
                "volume_metal_m3": volume_metal,
            })

            if self.densite_kg_m3 is not None:
                rho = _req_pos("densite_kg_m3", self.densite_kg_m3)
                m = rho * volume_metal
                rapport["masse"]["masse_kg"] = m
                rapport["masse"]["masse_lineique_kg_m"] = m / L if L > 0 else None
            else:
                _push_inconnue(rapport, "partielles", "masse cylindre", "Calculable si densite_kg_m3 est fournie.")

            # Inerties section (tube) : I = π/64 * (Do^4 - Di^4)
            Do = 2.0 * ro
            Di = 2.0 * ri
            I = (math.pi / 64.0) * (Do ** 4 - Di ** 4)
            Jp = (math.pi / 32.0) * (Do ** 4 - Di ** 4)  # polaire
            rapport["inerties"].update({
                "inertie_flexion_I_m4": I,
                "inertie_polaire_J_m4": Jp,
            })
        else:
            _push_inconnue(rapport, "impossibles", "masse/inerties", "Impossible sans epaisseur_retenue_m > 0.")

        # ----------------------------
        # 9) Bride (si fournie) : volume + masse additionnelle
        # ----------------------------
        if self.epaisseur_bride_m is not None and self.largeur_bride_m is not None:
            if t_retenue is None or t_retenue <= 0:
                _push_inconnue(rapport, "partielles", "bride", "Calculable si epaisseur_retenue_m est déterminée.")
            else:
                e_b = _req_pos("epaisseur_bride_m", self.epaisseur_bride_m)
                w_b = _req_pos("largeur_bride_m", self.largeur_bride_m)
                ro = ri + t_retenue
                r_b = ro + w_b
                # Volume approximatif 2 brides (haut/bas) : anneau * e_b * 2
                A_anneau = math.pi * (r_b * r_b - ro * ro)
                V_brides = 2.0 * A_anneau * e_b
                rapport["masse"]["volume_bridges_m3"] = V_brides
                if self.densite_kg_m3 is not None:
                    rho = _req_pos("densite_kg_m3", self.densite_kg_m3)
                    rapport["masse"]["masse_bridges_kg"] = rho * V_brides
                else:
                    _push_inconnue(rapport, "partielles", "masse brides", "Calculable si densite_kg_m3 est fournie.")

        # ----------------------------
        # 10) “Zéro inconnue” : mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "Cylindre(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport
