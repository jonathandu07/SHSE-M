# backend/pieces/coussinet_arbre_piston.py
# =============================================================================
# COUSSINET ARBRE-PISTON — SHSE-M
# =============================================================================
# Rôle :
# - Palier lisse (coussinet) entre l’arbre de piston et la bielle (ou tête de bielle),
#   pour réduire frottement et usure.
#
# Objectif :
# - Calculer TOUT ce qui est calculable (pressions, PV, échauffement par frottement,
#   régime hydrodynamique minimal via Sommerfeld si données suffisantes, durée de vie
#   “charge moyenne” si modèle fourni, etc.).
# - Ne RIEN inventer : toute donnée matériau/tribologie absente reste une inconnue.
#
# Dépendances possibles (non obligatoires) :
# - backend/pieces/arbre_piston.py (pour charges/diamètres)
# - backend/ensemble/huile.py ou backend/ensemble/eau.py (pour viscosité si lubrifiant)
# - backend/materiaux.py (pour propriétés coussinet / arbre)
#
# Notes modèle (sans heuristique cachée) :
# - La pression moyenne projetée est p = F / (d * L).
# - La vitesse de glissement est v = ω * (d/2) avec ω = 2πN (N en tr/s).
# - PV = p * v.
# - Puissance frottement (approx Coulomb) : P = μ * F * v (si μ fourni).
# - Régime hydrodynamique (journal bearing) nécessite : viscosité η, jeu radial c,
#   géométrie L/d, charge W, vitesse N -> nombre de Sommerfeld S.
#   Sans ces données, on ne conclut pas.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List, Literal
import math


# =============================================================================
# Utilitaires
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[dict]) -> List[dict]:
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


def _omega_rad_s(rpm: float) -> float:
    return 2.0 * math.pi * (rpm / 60.0)


# =============================================================================
# Résolution matériau (optionnelle via materiaux.py)
# =============================================================================

def _resoudre_materiau(
    cle: Optional[str],
    densite_kg_m3: Optional[float],
    k_therm_w_m_k: Optional[float],
    limite_pression_pa: Optional[float],
) -> Dict[str, Optional[float]]:
    """
    Essaie de compléter densité, conductivité, pression admissible via une DB matériaux.
    Rien n’est inventé : si introuvable, on garde les entrées.
    """
    rho = densite_kg_m3
    k = k_therm_w_m_k
    p_adm = limite_pression_pa

    if cle:
        for modname in (
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                mat = None
                if hasattr(mod, "get_materiau"):
                    mat = mod.get_materiau(cle)  # type: ignore
                elif hasattr(mod, "MATERIAUX"):
                    mats = getattr(mod, "MATERIAUX")
                    if isinstance(mats, dict):
                        mat = mats.get(cle)
                if mat is None:
                    continue

                def g(obj: Any, *names: str) -> Optional[float]:
                    for n in names:
                        if isinstance(obj, dict) and n in obj:
                            v = obj.get(n)
                        else:
                            v = getattr(obj, n, None)
                        if v is not None and _is_finite(v):
                            return float(v)
                    return None

                rho = rho if rho is not None else g(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                k = k if k is not None else g(mat, "conductivite_w_m_k", "k_w_m_k", "lambda_w_m_k")
                # “limite_pression” peut être stockée sous différents noms si tu l’as prévu
                p_adm = p_adm if p_adm is not None else g(mat, "pression_admissible_pa", "p_admissible_pa", "bearing_pressure_pa")
                break
            except Exception:
                continue

    return {"densite_kg_m3": rho, "conductivite_w_m_k": k, "pression_admissible_pa": p_adm}


# =============================================================================
# Coussinet
# =============================================================================

LubrificationMode = Literal["inconnue", "sec", "huile", "eau", "autre"]


@dataclass
class CoussinetArbrePiston:
    """
    Coussinet lisse (journal bearing) pour arbre de piston.
    """

    # Liens vers pièces (optionnels)
    arbre_piston: Optional[Any] = None   # idéalement backend.pieces.arbre_piston.ArbrePiston

    # Géométrie (si non déductible de l’arbre)
    diametre_portee_m: Optional[float] = None    # d
    longueur_coussinet_m: Optional[float] = None # L
    epaisseur_coussinet_m: Optional[float] = None  # e (utile masse + conduction radiale)

    # Jeu radial (hydrodynamique)
    jeu_radial_m: Optional[float] = None  # c (clearance radial)
    excentricite_m: Optional[float] = None  # e (eccentricity) si tu veux aller plus loin (sinon inconnue)

    # Efforts
    charge_radiale_N: Optional[float] = None      # W (portée radiale)
    # Option : charge axiale si coussinet flasque (rare ici)
    charge_axiale_N: Optional[float] = None

    # Cinématique
    rpm: Optional[float] = None  # vitesse relative (rotation de l’arbre)

    # Tribologie
    coefficient_frottement: Optional[float] = None  # μ (si lubrifié, μ “effectif”)
    mode_lubrification: LubrificationMode = "inconnue"

    # Lubrifiant : viscosité dynamique η en Pa.s (sinon tentative via module fluide)
    viscosite_Pa_s: Optional[float] = None
    temperature_lubrifiant_K: Optional[float] = None
    pression_lubrifiant_Pa: Optional[float] = None

    # Matériau coussinet
    materiau_coussinet: Optional[str] = None
    densite_coussinet_kg_m3: Optional[float] = None
    conductivite_coussinet_w_m_k: Optional[float] = None
    pression_admissible_pa: Optional[float] = None  # p_adm

    # Limites PV (si tu as une spec fabricant/standard)
    pv_admissible_W_m2: Optional[float] = None  # (Pa*m/s) = W/m²

    # Facteur sécurité
    facteur_securite: float = 2.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "geometrie": {},
            "cinematique": {},
            "efforts": {},
            "tribologie": {},
            "pressions": {},
            "pv": {},
            "frottement": {},
            "hydrodynamique": {},
            "thermique": {},
            "masse": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ----------------------------
        # 1) Matériau coussinet (compléments)
        # ----------------------------
        props_mat = _resoudre_materiau(
            self.materiau_coussinet,
            self.densite_coussinet_kg_m3,
            self.conductivite_coussinet_w_m_k,
            self.pression_admissible_pa,
        )
        rho_c = props_mat["densite_kg_m3"]
        k_c = props_mat["conductivite_w_m_k"]
        p_adm = props_mat["pression_admissible_pa"]

        # ----------------------------
        # 2) Déduction depuis arbre_piston si possible
        # ----------------------------
        d = self.diametre_portee_m
        L = self.longueur_coussinet_m
        W = self.charge_radiale_N
        rpm = self.rpm

        if self.arbre_piston is not None:
            # On tente d’extraire des données de l’analyse de l’arbre
            try:
                if hasattr(self.arbre_piston, "analyser") and callable(self.arbre_piston.analyser):
                    r_a = self.arbre_piston.analyser(strict=False)  # type: ignore
                    # Si l’arbre a un coussinet déjà défini
                    ent = r_a.get("entrees", {}) if isinstance(r_a, dict) else {}
                    if d is None and _is_finite(ent.get("diametre_portee_coussinet_m")):
                        d = float(ent["diametre_portee_coussinet_m"])
                        rapport["notes_modele"].append("diametre_portee_m déduit de arbre_piston.entrees.diametre_portee_coussinet_m")
                    if L is None and _is_finite(ent.get("longueur_coussinet_m")):
                        L = float(ent["longueur_coussinet_m"])
                        rapport["notes_modele"].append("longueur_coussinet_m déduite de arbre_piston.entrees.longueur_coussinet_m")

                    # Effort radial : on privilégie force_cisaillement (approx charge radiale)
                    eff = r_a.get("efforts", {})
                    if W is None and isinstance(eff, dict) and _is_finite(eff.get("force_cisaillement_N")):
                        W = float(eff["force_cisaillement_N"])
                        rapport["notes_modele"].append("charge_radiale_N approximée par arbre_piston.efforts.force_cisaillement_N")
            except Exception:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "liaison arbre_piston",
                    "Impossible de déduire via arbre_piston.analyser() (erreur d’appel ou format inattendu).",
                )

        # rpm : tentative depuis piston ou système (si tu le stockes ailleurs)
        if rpm is None and self.arbre_piston is not None:
            # si l’arbre contient un piston lié, parfois rpm est là-bas
            try:
                p = getattr(self.arbre_piston, "piston", None)
                if p is not None and hasattr(p, "rpm") and _is_finite(getattr(p, "rpm")):
                    rpm = float(getattr(p, "rpm"))
                    rapport["notes_modele"].append("rpm déduit de arbre_piston.piston.rpm")
            except Exception:
                pass

        # ----------------------------
        # 3) Validation des géométries minimales
        # ----------------------------
        if d is None:
            _push_inconnue(rapport, "impossibles", "diametre_portee_m", "Indispensable pour pression, PV, vitesse.")
        else:
            d = _req_pos("diametre_portee_m", d)

        if L is None:
            _push_inconnue(rapport, "impossibles", "longueur_coussinet_m", "Indispensable pour pression projetée.")
        else:
            L = _req_pos("longueur_coussinet_m", L)

        if W is None:
            _push_inconnue(rapport, "impossibles", "charge_radiale_N", "Indispensable pour pression, PV, frottement.")
        else:
            W = _req_pos("charge_radiale_N", W, strictly=False)

        # ----------------------------
        # 4) Cinématique : vitesse de glissement
        # ----------------------------
        v = None
        omega = None
        if rpm is not None:
            rpm = _req_pos("rpm", rpm, strictly=False)
            omega = _omega_rad_s(rpm)
            if d is not None:
                v = omega * (0.5 * d)

        else:
            _push_inconnue(rapport, "partielles", "vitesse glissement", "Calculable si rpm est fourni.")

        # ----------------------------
        # 5) Pression projetée + contraintes
        # ----------------------------
        p_proj = None
        if d is not None and L is not None and W is not None:
            # p = W / (d * L)
            denom = d * L
            if denom > 0:
                p_proj = W / denom
                rapport["pressions"]["pression_projetee_pa"] = p_proj
                rapport["pressions"]["surface_projetee_m2"] = denom
                rapport["pressions"]["charge_radiale_N"] = W

                if p_adm is not None:
                    p_allow = p_adm / FS
                    rapport["pressions"]["pression_admissible_pa"] = p_adm
                    rapport["pressions"]["pression_admissible_effective_pa"] = p_allow
                    rapport["pressions"]["ok_pression"] = p_proj <= p_allow
                    rapport["pressions"]["marge_pression"] = (p_allow / p_proj) if p_proj > 0 else None
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "pression admissible",
                        "OK pression calculable si pression_admissible_pa (ou materiau_coussinet résoluble) est fourni.",
                    )

        # ----------------------------
        # 6) PV (pression * vitesse)
        # ----------------------------
        if p_proj is not None and v is not None:
            PV = p_proj * abs(v)  # W/m²
            rapport["pv"]["pv_W_m2"] = PV
            if self.pv_admissible_W_m2 is not None:
                pv_adm = _req_pos("pv_admissible_W_m2", self.pv_admissible_W_m2)
                pv_allow = pv_adm / FS
                rapport["pv"]["pv_admissible_W_m2"] = pv_adm
                rapport["pv"]["pv_admissible_effective_W_m2"] = pv_allow
                rapport["pv"]["ok_pv"] = PV <= pv_allow
                rapport["pv"]["marge_pv"] = (pv_allow / PV) if PV > 0 else None
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "PV admissible",
                    "Vérification PV possible si pv_admissible_W_m2 est fourni (spec coussinet).",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "PV",
                "Calculable si pression projetée (d,L,W) et rpm sont fournis.",
            )

        # ----------------------------
        # 7) Frottement / puissance dissipée
        # ----------------------------
        if self.coefficient_frottement is not None and v is not None and W is not None:
            mu = _req_pos("coefficient_frottement", self.coefficient_frottement, strictly=False)
            P_f = mu * abs(W) * abs(v)  # W
            T_f = mu * abs(W) * (0.5 * d) if d is not None else None  # couple de frottement
            rapport["frottement"]["mu"] = mu
            rapport["frottement"]["puissance_frottement_W"] = P_f
            rapport["frottement"]["couple_frottement_Nm"] = T_f
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "puissance frottement",
                "Calculable si coefficient_frottement, rpm, charge_radiale_N et diametre_portee_m sont fournis.",
            )

        # ----------------------------
        # 8) Hydrodynamique (Sommerfeld) — uniquement si données suffisantes
        # ----------------------------
        # Nombre de Sommerfeld (journal bearing, forme classique) :
        # S = (η * N * (r/c)^2) / p  * (L/d)
        # où N = tr/s, r = d/2, c = jeu radial, p = pression projetée
        # (selon conventions, certains mettent (r/c)^2 ou (r/c) ; ici on choisit la forme
        # courante associée aux tableaux Raimondi-Boyd, mais sans conclure sans sources/tables).
        #
        # On calcule S si η, rpm, c, p, L/d connus. On ne “mappe” pas S->(ε, f, Q)
        # sans tables/corrélations fournies.
        eta = self.viscosite_Pa_s
        if eta is None and self.mode_lubrification in ("huile", "eau"):

            # Tentative : si eau -> backend/ensemble/eau.py
            # (huile : non fourni ici -> inconnue)
            if self.mode_lubrification == "eau":
                if self.temperature_lubrifiant_K is not None and self.pression_lubrifiant_Pa is not None:
                    try:
                        from backend.ensemble.eau import etat_eau_pure  # type: ignore
                        et = etat_eau_pure(
                            T_K=float(self.temperature_lubrifiant_K),
                            p_Pa=float(self.pression_lubrifiant_Pa),
                            backend="auto",
                        )
                        eta = float(et.mu_Pa_s)
                        rapport["notes_modele"].append("viscosite_Pa_s déduite via backend.ensemble.eau.etat_eau_pure().mu_Pa_s")
                    except Exception:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "viscosité lubrifiant",
                            "mode=eau mais impossible de déduire (backend eau indisponible ou erreur).",
                        )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "viscosité lubrifiant",
                        "mode=eau : calculable si temperature_lubrifiant_K et pression_lubrifiant_Pa sont fournis.",
                    )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "viscosité lubrifiant",
                    "mode=huile : nécessite un module huile (non présent) ou viscosite_Pa_s fournie.",
                )

        # Calcul Sommerfeld
        if eta is not None and p_proj is not None and rpm is not None and d is not None and L is not None and self.jeu_radial_m is not None:
            eta = _req_pos("viscosite_Pa_s", eta)
            c = _req_pos("jeu_radial_m", self.jeu_radial_m)
            N_tr_s = rpm / 60.0
            r = 0.5 * d

            if c <= 0:
                raise ValueError("jeu_radial_m doit être > 0")

            # Formule calculatoire (sans interprétation)
            S = (eta * N_tr_s * (r / c) ** 2 / p_proj) * (L / d)
            rapport["hydrodynamique"]["sommerfeld_S"] = S
            rapport["hydrodynamique"]["eta_Pa_s"] = eta
            rapport["hydrodynamique"]["jeu_radial_m"] = c
            rapport["hydrodynamique"]["L_sur_d"] = L / d
            rapport["hydrodynamique"]["notes"] = (
                "S calculé, mais aucune interprétation (ε, Q, f) sans tables/corrélations explicitement fournies."
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "hydrodynamique (Sommerfeld)",
                "Calculable si viscosite_Pa_s (ou déductible), rpm, pression_projetee, diametre_portee, longueur et jeu_radial sont fournis.",
            )

        # ----------------------------
        # 9) Thermique : conduction radiale à travers coussinet (si épaisseur + k)
        # ----------------------------
        # Modèle simple : R_cond = ln(ro/ri)/(2πkL)
        # Ici : ri = d/2 (portée), ro = ri + epaisseur.
        if self.epaisseur_coussinet_m is not None and k_c is not None and d is not None and L is not None:
            e = _req_pos("epaisseur_coussinet_m", self.epaisseur_coussinet_m)
            k = _req_pos("conductivite_coussinet_w_m_k", k_c)
            ri = 0.5 * d
            ro = ri + e
            if ro <= ri:
                raise ValueError("epaisseur_coussinet_m invalide (ro<=ri).")
            R = math.log(ro / ri) / (2.0 * math.pi * k * L)
            rapport["thermique"]["R_conduction_K_W"] = R
            rapport["thermique"]["k_coussinet_W_m_K"] = k
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "thermique conduction",
                "Calculable si epaisseur_coussinet_m et conductivite_coussinet_w_m_k (ou materiau) sont fournis.",
            )

        # ----------------------------
        # 10) Masse (si e + rho)
        # ----------------------------
        # Volume anneau : V = π (ro² - ri²) L
        if self.epaisseur_coussinet_m is not None and rho_c is not None and d is not None and L is not None:
            e = _req_pos("epaisseur_coussinet_m", self.epaisseur_coussinet_m)
            rho = _req_pos("densite_coussinet_kg_m3", rho_c)
            ri = 0.5 * d
            ro = ri + e
            V = math.pi * (ro * ro - ri * ri) * L
            m = rho * V
            rapport["masse"] = {
                "volume_m3": V,
                "masse_kg": m,
                "densite_kg_m3": rho,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse coussinet",
                "Calculable si epaisseur_coussinet_m, densite_coussinet_kg_m3 (ou materiau) sont fournis.",
            )

        # ----------------------------
        # 11) Entrées (trace)
        # ----------------------------
        rapport["entrees"] = {
            "diametre_portee_m": self.diametre_portee_m,
            "longueur_coussinet_m": self.longueur_coussinet_m,
            "epaisseur_coussinet_m": self.epaisseur_coussinet_m,
            "jeu_radial_m": self.jeu_radial_m,
            "charge_radiale_N": self.charge_radiale_N,
            "rpm": self.rpm,
            "coefficient_frottement": self.coefficient_frottement,
            "mode_lubrification": self.mode_lubrification,
            "viscosite_Pa_s": self.viscosite_Pa_s,
            "temperature_lubrifiant_K": self.temperature_lubrifiant_K,
            "pression_lubrifiant_Pa": self.pression_lubrifiant_Pa,
            "materiau_coussinet": self.materiau_coussinet,
            "densite_coussinet_kg_m3": self.densite_coussinet_kg_m3,
            "conductivite_coussinet_w_m_k": self.conductivite_coussinet_w_m_k,
            "pression_admissible_pa": self.pression_admissible_pa,
            "pv_admissible_W_m2": self.pv_admissible_W_m2,
            "facteur_securite": self.facteur_securite,
        }

        rapport["geometrie"] = {
            "diametre_portee_m": d,
            "longueur_coussinet_m": L,
            "epaisseur_coussinet_m": self.epaisseur_coussinet_m,
            "jeu_radial_m": self.jeu_radial_m,
        }
        rapport["cinematique"] = {
            "rpm": rpm,
            "omega_rad_s": omega,
            "vitesse_glissement_m_s": v,
        }
        rapport["tribologie"] = {
            "mode_lubrification": self.mode_lubrification,
            "viscosite_Pa_s": eta,
            "coefficient_frottement": self.coefficient_frottement,
        }

        # ----------------------------
        # 12) Mode strict
        # ----------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "CoussinetArbrePiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Exemple d'usage (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    from pprint import pprint

    c = CoussinetArbrePiston(
        diametre_portee_m=0.02,
        longueur_coussinet_m=0.02,
        epaisseur_coussinet_m=0.002,
        charge_radiale_N=2000.0,
        rpm=3000.0,
        coefficient_frottement=0.05,
        mode_lubrification="eau",
        temperature_lubrifiant_K=300.0,
        pression_lubrifiant_Pa=101325.0,
        jeu_radial_m=20e-6,
        materiau_coussinet=None,
        pression_admissible_pa=30e6,
        pv_admissible_W_m2=1.0e9,
        facteur_securite=2.0,
    )

    pprint(c.analyser(strict=False))
