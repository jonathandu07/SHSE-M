# backend/pieces/arbre_piston.py
# =============================================================================
# ARBRE DE PISTON — SHSE-M
# Version enrichie : dimensionnement arbre ÉVIDÉ (hollow) + cisaillement + taraudages ISO
# =============================================================================
# Objectif "rien inventer" :
# - Ne PAS choisir une géométrie finale à ta place si une donnée manque.
# - Calculer tout ce qui est calculable à partir :
#   - efforts fournis (ou déduits de piston.analyser() quand possible),
#   - matériau (via materiaux.py si dispo),
#   - choix explicites (ex: ratio d’évidement k = Di/Do) si tu le fournis.
#
# Point clé demandé :
# - dimensionnement en cisaillement pour que l’arbre ne cède pas :
#   on calcule les contraintes de cisaillement (transverse V et/ou torsion T si fournis)
#   et on dimensionne (Do, Di) d’un arbre évidé.
#
# IMPORTANT :
# - Si tu ne fournis PAS au moins V (= force_cisaillement_N) et/ou un critère d’évidement
#   (k=Di/Do ou Di fixé), on ne peut pas donner une seule géométrie unique.
#   => Le module renvoie alors des "scénarios" (k candidats) SANS choisir.
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

def _aire_disque(d: float) -> float:
    r = 0.5 * d
    return math.pi * r * r

def _inertie_cercle(d: float) -> float:
    return (math.pi * d**4) / 64.0

def _polaire_cercle(d: float) -> float:
    return (math.pi * d**4) / 32.0

def _inertie_annulaire(Do: float, Di: float) -> float:
    return (math.pi * (Do**4 - Di**4)) / 64.0

def _polaire_annulaire(Do: float, Di: float) -> float:
    return (math.pi * (Do**4 - Di**4)) / 32.0

def _aire_annulaire(Do: float, Di: float) -> float:
    return (math.pi / 4.0) * (Do**2 - Di**2)

def _sigma_flexion(M: float, d: float) -> float:
    # section pleine : W = π d^3 / 32
    W = (math.pi * d**3) / 32.0
    return M / W

def _sigma_flexion_annulaire(M: float, Do: float, Di: float) -> float:
    # section annulaire : W = I / (Do/2)
    I = _inertie_annulaire(Do, Di)
    return M * (Do / 2.0) / I

def _von_mises_sigma_tau(sigma: float, tau: float) -> float:
    return math.sqrt(sigma**2 + 3.0 * tau**2)

def _omega_from_rpm(rpm: float) -> float:
    return 2.0 * math.pi * (rpm / 60.0)

def _euler_pcrit(E: float, I: float, L: float, K: float) -> float:
    return (math.pi**2) * E * I / ((K * L) ** 2)


# =============================================================================
# Matériau (optionnel via materiaux.py)
# =============================================================================

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
) -> Dict[str, Optional[float]]:
    rho = densite_kg_m3
    Re = limite_elastique_pa
    E = module_young_pa

    if materiau_cle:
        for modname in (
            "backend.ensemble.materiaux",
            "backend.materiaux",
            "materiaux",
            "backend.components.materiaux",
            "backend.modules.materiaux",
        ):
            try:
                mod = __import__(modname, fromlist=["*"])
                mat = None
                if hasattr(mod, "get_materiau"):
                    mat = mod.get_materiau(materiau_cle)  # type: ignore
                elif hasattr(mod, "MATERIAUX"):
                    mats = getattr(mod, "MATERIAUX")
                    if isinstance(mats, dict):
                        mat = mats.get(materiau_cle)
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
                Re = Re if Re is not None else g(mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa")
                E = E if E is not None else g(mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa")
                break
            except Exception:
                continue

    return {"densite_kg_m3": rho, "limite_elastique_pa": Re, "module_young_pa": E}


# =============================================================================
# Filetages ISO métriques (pas gros) — table standard
# =============================================================================

ISO_METRIQUE_PAS_GROS = {
    "M3":  {"d_nom": 3e-3,  "p": 0.5e-3,  "d2": 2.675e-3, "d3": 2.387e-3, "d_percage": 2.5e-3},
    "M4":  {"d_nom": 4e-3,  "p": 0.7e-3,  "d2": 3.545e-3, "d3": 3.141e-3, "d_percage": 3.3e-3},
    "M5":  {"d_nom": 5e-3,  "p": 0.8e-3,  "d2": 4.480e-3, "d3": 4.019e-3, "d_percage": 4.2e-3},
    "M6":  {"d_nom": 6e-3,  "p": 1.0e-3,  "d2": 5.350e-3, "d3": 4.773e-3, "d_percage": 5.0e-3},
    "M8":  {"d_nom": 8e-3,  "p": 1.25e-3, "d2": 7.188e-3, "d3": 6.466e-3, "d_percage": 6.8e-3},
    "M10": {"d_nom": 10e-3, "p": 1.5e-3,  "d2": 9.026e-3, "d3": 8.160e-3, "d_percage": 8.5e-3},
    "M12": {"d_nom": 12e-3, "p": 1.75e-3, "d2": 10.863e-3, "d3": 9.853e-3, "d_percage": 10.2e-3},
    "M14": {"d_nom": 14e-3, "p": 2.0e-3,  "d2": 12.701e-3, "d3": 11.546e-3,"d_percage": 12.0e-3},
    "M16": {"d_nom": 16e-3, "p": 2.0e-3,  "d2": 14.701e-3, "d3": 13.546e-3,"d_percage": 14.0e-3},
}

def _iso_get(filetage: str) -> Optional[Dict[str, float]]:
    return ISO_METRIQUE_PAS_GROS.get(filetage.upper().strip())


# =============================================================================
# Dimensionnement arbre évidé (cisaillement + torsion + flexion)
# =============================================================================
#
# Contraintes calculées (si données disponibles) :
# - cisaillement transverse (approx conservative) : tau_V = V / A
#   (On utilise l’average shear V/A car sans modèle de répartition exacte -> non-invention, conservatif.)
# - torsion : tau_T = T * r / J
# - flexion : sigma_b = M * r / I
# - axial : sigma_ax = F / A
# - von Mises : sigma_eq = sqrt( (sigma_ax + sigma_b)^2 + 3*(tau_V + tau_T)^2 )
#
# Dimensionnement :
# - si Re connu : sigma_allow = Re / FS
# - si résistance cisaillement connue : tau_allow = tau / FS
#   sinon on peut donner des seuils théoriques (sans choisir) :
#     * tau_y_vm = Re / sqrt(3)
#     * tau_y_tresca = Re / 2
#   => on sort les 2, et tu choisis le critère.
# =============================================================================

def _tau_y_vm(Re: float) -> float:
    return float(Re) / math.sqrt(3.0)

def _tau_y_tresca(Re: float) -> float:
    return float(Re) / 2.0

def _solve_Do_min_for_tauV(V: float, tau_allow: float, k: float) -> float:
    """
    Dimensionne Do minimal pour respecter tau_V = V/A <= tau_allow, arbre annulaire
    A = π/4 * Do^2 * (1 - k^2) avec k=Di/Do
    => Do >= sqrt( 4V / (π tau_allow (1-k^2)) )
    """
    if not (0.0 <= k < 1.0):
        raise ValueError("k (Di/Do) doit être dans [0,1).")
    denom = math.pi * float(tau_allow) * (1.0 - k*k)
    if denom <= 0:
        raise ValueError("tau_allow et (1-k^2) doivent donner un dénominateur > 0.")
    return math.sqrt((4.0 * abs(float(V))) / denom)

def _solve_Do_min_for_tauT(T: float, tau_allow: float, k: float) -> float:
    """
    Dimensionne Do minimal pour respecter tau_T = T*r/J <= tau_allow, arbre annulaire
    J = π/32 * (Do^4 - Di^4) = π/32 * Do^4*(1-k^4), r=Do/2
    tau = T*(Do/2) / (π/32 * Do^4*(1-k^4)) = 16 T / (π Do^3 (1-k^4))
    => Do >= ( 16 T / (π tau_allow (1-k^4)) )^(1/3)
    """
    if not (0.0 <= k < 1.0):
        raise ValueError("k (Di/Do) doit être dans [0,1).")
    denom = math.pi * float(tau_allow) * (1.0 - k**4)
    if denom <= 0:
        raise ValueError("tau_allow et (1-k^4) doivent donner un dénominateur > 0.")
    return (16.0 * abs(float(T)) / denom) ** (1.0 / 3.0)

def _solve_Do_min_for_sig_ax(F: float, sigma_allow: float, k: float) -> float:
    """
    Dimensionne Do minimal pour sigma_ax = F/A <= sigma_allow, arbre annulaire
    A = π/4 * Do^2*(1-k^2)
    => Do >= sqrt( 4F / (π sigma_allow (1-k^2)) )
    """
    return _solve_Do_min_for_tauV(F, sigma_allow, k)  # même forme (force/contrainte)

def _solve_Do_min_for_sig_b(M: float, sigma_allow: float, k: float) -> float:
    """
    Dimensionne Do minimal pour flexion : sigma_b = M*r/I <= sigma_allow
    I = π/64 * Do^4*(1-k^4), r=Do/2
    sigma_b = M*(Do/2) / (π/64 * Do^4*(1-k^4)) = 32 M / (π Do^3 (1-k^4))
    => Do >= ( 32 M / (π sigma_allow (1-k^4)) )^(1/3)
    """
    if not (0.0 <= k < 1.0):
        raise ValueError("k (Di/Do) doit être dans [0,1).")
    denom = math.pi * float(sigma_allow) * (1.0 - k**4)
    if denom <= 0:
        raise ValueError("sigma_allow et (1-k^4) doivent donner un dénominateur > 0.")
    return (32.0 * abs(float(M)) / denom) ** (1.0 / 3.0)


# =============================================================================
# Pièce : ArbrePiston
# =============================================================================

@dataclass
class ArbrePiston:
    """
    Arbre/axe de piston reliant piston et bielle.
    """

    # Liens vers pièces (optionnels)
    piston: Optional[Any] = None
    bielle: Optional[Any] = None
    cylindre: Optional[Any] = None

    # Géométrie générale (optionnelle)
    longueur_totale_m: Optional[float] = None
    longueur_fut_central_m: Optional[float] = None
    longueur_teton_gauche_m: Optional[float] = None
    longueur_teton_droit_m: Optional[float] = None

    # Version pleine (si tu fournis)
    diametre_fut_central_m: Optional[float] = None

    # ---- NOUVEAU : arbre évidé (si tu veux explicitement dimensionner l’évidement)
    # Si fourni : l’arbre est dimensionné en ANNEAU (Do, Di).
    diametre_exterieur_fut_m: Optional[float] = None  # Do
    diametre_interieur_fut_m: Optional[float] = None  # Di
    ratio_evidement_k: Optional[float] = None         # k = Di/Do (si tu préfères)

    # Congés (géométrie pure)
    rayon_conge_gauche_m: Optional[float] = None
    rayon_conge_droit_m: Optional[float] = None

    # Cinématique
    rpm: Optional[float] = None

    # Efforts
    force_axiale_N: Optional[float] = None
    force_cisaillement_N: Optional[float] = None     # V (transverse)
    bras_levier_charge_m: Optional[float] = None
    moment_flexion_Nm: Optional[float] = None        # M
    couple_torsion_Nm: Optional[float] = None        # T (si tu as un couple sur l’arbre)

    # Flambage
    longueur_libre_m: Optional[float] = None
    K_flambage: Optional[float] = None

    # Taraudages
    filetage_gauche: Optional[str] = None
    filetage_droit: Optional[str] = None
    profondeur_taraudage_gauche_m: Optional[float] = None
    profondeur_taraudage_droit_m: Optional[float] = None
    effort_axial_sur_taraudage_gauche_N: Optional[float] = None
    effort_axial_sur_taraudage_droit_N: Optional[float] = None

    # Résistance cisaillement matière taraudée (sinon inconnue)
    resistance_cisaillement_matiere_taraudee_pa: Optional[float] = None
    # Optionnel : limite élastique matière taraudée si différente de l’arbre
    limite_elastique_matiere_taraudee_pa: Optional[float] = None

    # Coussinet (optionnel)
    diametre_portee_coussinet_m: Optional[float] = None
    longueur_coussinet_m: Optional[float] = None

    # Matériau arbre
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None

    # Dimensionnement
    facteur_securite: float = 2.0

    # Scénarios de k si tu n’en fournis pas (ce ne sont PAS des choix imposés)
    # (liste courte, uniquement pour produire des résultats exploitables sans te forcer la main)
    k_scenarios: Tuple[float, ...] = (0.0, 0.3, 0.5, 0.6, 0.7)

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "efforts": {},
            "geometrie": {},
            "cinematique": {},
            "dimensionnement_evide": {},
            "contraintes": {},
            "flambage": {},
            "taraudages": {},
            "masse": {},
            "inerties": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ---------------------------------------------------------------------
        # 1) Matériau
        # ---------------------------------------------------------------------
        props_mat = _resoudre_materiau(
            self.materiau_cle,
            self.densite_kg_m3,
            self.limite_elastique_pa,
            self.module_young_pa,
        )
        rho = props_mat["densite_kg_m3"]
        Re = props_mat["limite_elastique_pa"]
        E = props_mat["module_young_pa"]

        sigma_allow = (float(Re) / FS) if (Re is not None) else None
        tau_allow_vm = (_tau_y_vm(float(Re)) / FS) if (Re is not None) else None
        tau_allow_tresca = (_tau_y_tresca(float(Re)) / FS) if (Re is not None) else None

        rapport["materiau"] = {
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": rho,
            "limite_elastique_pa": Re,
            "module_young_pa": E,
            "admissibles": {
                "sigma_allow_pa": sigma_allow,
                "tau_allow_vm_pa": tau_allow_vm,         # Re/sqrt(3)/FS
                "tau_allow_tresca_pa": tau_allow_tresca, # Re/2/FS
                "note": "Deux critères théoriques (VM/Tresca) donnés sans choisir.",
            },
        }
        if Re is None:
            _push_inconnue(rapport, "partielles", "limite_elastique_pa", "Re requis pour calculer des contraintes admissibles.")
        if rho is None:
            _push_inconnue(rapport, "partielles", "densite_kg_m3", "rho requis pour masse.")

        # ---------------------------------------------------------------------
        # 2) Efforts : déduction depuis piston si possible (sans inventer)
        # ---------------------------------------------------------------------
        F_ax = self.force_axiale_N
        V = self.force_cisaillement_N
        M = self.moment_flexion_Nm
        T = self.couple_torsion_Nm

        if self.piston is not None:
            try:
                if hasattr(self.piston, "analyser") and callable(self.piston.analyser):
                    r_p = self.piston.analyser(strict=False)  # type: ignore
                    dim = r_p.get("dimensionnement", {}) if isinstance(r_p, dict) else {}
                    if F_ax is None and _is_finite(dim.get("force_pression_piston_max_N")):
                        F_ax = float(dim["force_pression_piston_max_N"])
                        rapport["notes_modele"].append(
                            "force_axiale_N déduite de piston.analyser().dimensionnement.force_pression_piston_max_N"
                        )
            except Exception:
                _push_inconnue(rapport, "partielles", "efforts depuis piston", "Impossible de déduire via piston.analyser() (format/erreur).")

        # Déduction moment de flexion si V et bras de levier fournis
        if M is None and V is not None and self.bras_levier_charge_m is not None:
            a = _req_pos("bras_levier_charge_m", self.bras_levier_charge_m, strictly=False)
            M = float(V) * a
            rapport["notes_modele"].append("moment_flexion_Nm déduit : M = V * bras_levier")

        rapport["efforts"] = {
            "force_axiale_N": F_ax,
            "force_cisaillement_N": V,
            "moment_flexion_Nm": M,
            "couple_torsion_Nm": T,
            "bras_levier_charge_m": self.bras_levier_charge_m,
        }

        # ---------------------------------------------------------------------
        # 3) Géométrie longueurs : déductions simples
        # ---------------------------------------------------------------------
        L_tot = self.longueur_totale_m
        L_mid = self.longueur_fut_central_m
        L_g = self.longueur_teton_gauche_m
        L_d = self.longueur_teton_droit_m

        if L_tot is None and all(_is_finite(x) for x in (L_mid, L_g, L_d)):
            L_tot = float(L_mid) + float(L_g) + float(L_d)
            rapport["notes_modele"].append("longueur_totale_m déduite = L_central + L_gauche + L_droit.")
        if L_mid is None and all(_is_finite(x) for x in (L_tot, L_g, L_d)):
            L_mid = float(L_tot) - float(L_g) - float(L_d)
            rapport["notes_modele"].append("longueur_fut_central_m déduite = L_total - L_gauche - L_droit.")

        if L_tot is not None:
            L_tot = _req_pos("longueur_totale_m", L_tot)
        if L_mid is not None:
            L_mid = _req_pos("longueur_fut_central_m", L_mid)
        if L_g is not None:
            L_g = _req_pos("longueur_teton_gauche_m", L_g)
        if L_d is not None:
            L_d = _req_pos("longueur_teton_droit_m", L_d)

        rapport["geometrie"] = {
            "longueur_totale_m": L_tot,
            "longueur_fut_central_m": L_mid,
            "longueur_teton_gauche_m": L_g,
            "longueur_teton_droit_m": L_d,
            "rayon_conge_gauche_m": self.rayon_conge_gauche_m,
            "rayon_conge_droit_m": self.rayon_conge_droit_m,
            "section": "pleine si diametre_fut_central_m ; évidée si Do/Di ou k fourni",
        }

        # ---------------------------------------------------------------------
        # 4) Dimensionnement arbre ÉVIDÉ (si effort(s) + matériau)
        # ---------------------------------------------------------------------
        # On dimensionne Do/Di à partir des contraintes (cisaillement V et/ou torsion T et/ou flexion M et/ou axial F)
        # sans choisir un k si tu ne le donnes pas : on renvoie des scénarios.
        dim_evide: Dict[str, Any] = {"mode": None, "scenarios": None, "resultat_unique": None}

        # Résolution k / (Do, Di)
        Do_in = self.diametre_exterieur_fut_m
        Di_in = self.diametre_interieur_fut_m
        k_in = self.ratio_evidement_k

        if Do_in is not None:
            Do_in = _req_pos("diametre_exterieur_fut_m", Do_in)
        if Di_in is not None:
            Di_in = _req_pos("diametre_interieur_fut_m", Di_in, strictly=False)
            if Do_in is not None and Di_in >= Do_in:
                _push_inconnue(rapport, "impossibles", "géométrie évidement", "Di >= Do (annulaire impossible).")
        if k_in is not None:
            k_in = _req_finite("ratio_evidement_k", k_in)
            if not (0.0 <= k_in < 1.0):
                _push_inconnue(rapport, "impossibles", "ratio_evidement_k", "k doit être dans [0,1).")

        # Choix de tau_allow :
        # - si Re dispo : on donne 2 seuils (VM et Tresca), sans choisir.
        # - si Re manquant : impossible de dimensionner en contrainte admissible.
        if Re is None:
            _push_inconnue(rapport, "partielles", "dimensionnement évidé", "Re requis pour dimensionner (contraintes admissibles).")

        # On ne peut dimensionner en cisaillement transverse sans V
        if V is None and T is None and M is None and F_ax is None:
            _push_inconnue(rapport, "partielles", "dimensionnement évidé", "Au moins un effort parmi F_ax, V, M, T doit être fourni/déduit.")
        else:
            # On calcule Do_min par critères séparés, puis on prend le max (conservatif).
            def compute_Do_min(k: float, sigma_allow_pa: Optional[float], tau_allow_pa: Optional[float]) -> Dict[str, Any]:
                outk: Dict[str, Any] = {"k": k, "criteres": {}, "Do_min_m": None, "Di_min_m": None, "notes": []}
                Do_candidates: List[float] = []

                if tau_allow_pa is not None:
                    if V is not None:
                        DoV = _solve_Do_min_for_tauV(float(V), float(tau_allow_pa), float(k))
                        outk["criteres"]["cisaillement_transverse"] = {"V_N": float(V), "tau_allow_pa": float(tau_allow_pa), "Do_min_m": DoV}
                        Do_candidates.append(DoV)
                    else:
                        outk["criteres"]["cisaillement_transverse"] = {"note": "V (force_cisaillement_N) manquant -> pas de dimensionnement cisaillement transverse."}

                    if T is not None:
                        DoT = _solve_Do_min_for_tauT(float(T), float(tau_allow_pa), float(k))
                        outk["criteres"]["torsion"] = {"T_Nm": float(T), "tau_allow_pa": float(tau_allow_pa), "Do_min_m": DoT}
                        Do_candidates.append(DoT)
                    else:
                        outk["criteres"]["torsion"] = {"note": "T (couple_torsion_Nm) manquant -> pas de dimensionnement torsion."}
                else:
                    outk["criteres"]["cisaillement_transverse"] = {"note": "tau_allow inconnu (Re manquant) -> impossible."}
                    outk["criteres"]["torsion"] = {"note": "tau_allow inconnu (Re manquant) -> impossible."}

                if sigma_allow_pa is not None:
                    if F_ax is not None:
                        DoF = _solve_Do_min_for_sig_ax(float(F_ax), float(sigma_allow_pa), float(k))
                        outk["criteres"]["axial"] = {"F_N": float(F_ax), "sigma_allow_pa": float(sigma_allow_pa), "Do_min_m": DoF}
                        Do_candidates.append(DoF)
                    else:
                        outk["criteres"]["axial"] = {"note": "F_ax manquant -> pas de dimensionnement axial."}

                    if M is not None:
                        DoM = _solve_Do_min_for_sig_b(float(M), float(sigma_allow_pa), float(k))
                        outk["criteres"]["flexion"] = {"M_Nm": float(M), "sigma_allow_pa": float(sigma_allow_pa), "Do_min_m": DoM}
                        Do_candidates.append(DoM)
                    else:
                        outk["criteres"]["flexion"] = {"note": "M manquant -> pas de dimensionnement flexion."}
                else:
                    outk["criteres"]["axial"] = {"note": "sigma_allow inconnu (Re manquant) -> impossible."}
                    outk["criteres"]["flexion"] = {"note": "sigma_allow inconnu (Re manquant) -> impossible."}

                if Do_candidates:
                    Do_min = max(Do_candidates)
                    outk["Do_min_m"] = Do_min
                    outk["Di_min_m"] = Do_min * float(k)
                else:
                    outk["notes"].append("Aucun critère dimensionnant calculable (efforts ou admissibles manquants).")
                return outk

            # Cas : Do/Di fournis -> on calcule contraintes, pas dimensionnement
            if Do_in is not None and Di_in is not None:
                dim_evide["mode"] = "verification_geometrie_evidee"
                Do = float(Do_in)
                Di = float(Di_in)
                A = _aire_annulaire(Do, Di)
                I = _inertie_annulaire(Do, Di)
                J = _polaire_annulaire(Do, Di)
                r = Do / 2.0

                sigma_ax = (float(F_ax) / A) if (F_ax is not None) else None
                sigma_b = (_sigma_flexion_annulaire(float(M), Do, Di) if (M is not None) else None
                           )
                tau_V = (float(V) / A) if (V is not None) else None
                tau_T = (float(T) * r / J) if (T is not None) else None

                # combinaison (conservatif : somme)
                s_tot = 0.0
                if sigma_ax is not None:
                    s_tot += float(sigma_ax)
                if sigma_b is not None:
                    s_tot += float(sigma_b)
                t_tot = 0.0
                if tau_V is not None:
                    t_tot += float(tau_V)
                if tau_T is not None:
                    t_tot += float(tau_T)

                sigma_eq = _von_mises_sigma_tau(s_tot, t_tot)

                rapport["contraintes"] = {
                    "section_annulaire_m2": A,
                    "I_m4": I,
                    "J_m4": J,
                    "sigma_axiale_pa": sigma_ax,
                    "sigma_flexion_pa": sigma_b,
                    "tau_transverse_pa": tau_V,
                    "tau_torsion_pa": tau_T,
                    "sigma_von_mises_pa": sigma_eq,
                    "sigma_allow_pa": sigma_allow,
                    "marge_sigma_vm": (sigma_allow / sigma_eq) if (sigma_allow is not None and sigma_eq > 0) else None,
                    "note": "cisaillement transverse approximé par V/A (conservatif).",
                }
                dim_evide["resultat_unique"] = {"Do_m": Do, "Di_m": Di, "k": (Di / Do if Do > 0 else None)}

            else:
                # Cas : dimensionnement -> nécessite au moins Re (pour admissibles) et un effort
                dim_evide["mode"] = "dimensionnement"
                if Re is None:
                    dim_evide["scenarios"] = {"note": "Re manquant -> pas de dimensionnement quantitatif."}
                else:
                    # Cas : k fourni -> résultat unique
                    if k_in is not None:
                        k = float(k_in)
                        sc_vm = compute_Do_min(k, sigma_allow, tau_allow_vm)
                        sc_tr = compute_Do_min(k, sigma_allow, tau_allow_tresca)
                        dim_evide["resultat_unique"] = {
                            "k": k,
                            "critere_vm": sc_vm,
                            "critere_tresca": sc_tr,
                            "note": "Deux résultats (VM/Tresca). Aucune sélection automatique.",
                        }
                    # Cas : Do fourni et k fourni -> Di calculable (mais sans vérifier contraintes)
                    elif Do_in is not None and k_in is not None:
                        dim_evide["resultat_unique"] = {"Do_m": float(Do_in), "Di_m": float(Do_in) * float(k_in)}
                    # Cas : rien fourni -> scénarios k
                    else:
                        scenarios_vm = []
                        scenarios_tr = []
                        for k in self.k_scenarios:
                            # k doit rester dans [0,1)
                            if not (0.0 <= float(k) < 1.0):
                                continue
                            scenarios_vm.append(compute_Do_min(float(k), sigma_allow, tau_allow_vm))
                            scenarios_tr.append(compute_Do_min(float(k), sigma_allow, tau_allow_tresca))
                        dim_evide["scenarios"] = {
                            "liste_k": list(self.k_scenarios),
                            "critere_vm": scenarios_vm,
                            "critere_tresca": scenarios_tr,
                            "note": "Scénarios proposés car k/Do/Di non fournis. Aucune sélection.",
                        }

        rapport["dimensionnement_evide"] = dim_evide

        # ---------------------------------------------------------------------
        # 5) Flambage (Euler) — si données
        # ---------------------------------------------------------------------
        # On peut faire flambage pour section pleine (d) OU évidée (Do/Di) si géométrie connue.
        if self.longueur_libre_m is not None and self.K_flambage is not None and E is not None:
            L_free = _req_pos("longueur_libre_m", self.longueur_libre_m)
            K = _req_pos("K_flambage", self.K_flambage)

            I_use = None
            if self.diametre_fut_central_m is not None:
                d = _req_pos("diametre_fut_central_m", self.diametre_fut_central_m)
                I_use = _inertie_cercle(d)
            elif self.diametre_exterieur_fut_m is not None and self.diametre_interieur_fut_m is not None:
                Do = _req_pos("diametre_exterieur_fut_m", self.diametre_exterieur_fut_m)
                Di = _req_pos("diametre_interieur_fut_m", self.diametre_interieur_fut_m, strictly=False)
                if Di >= Do:
                    _push_inconnue(rapport, "impossibles", "flambage", "Di >= Do.")
                else:
                    I_use = _inertie_annulaire(Do, Di)
            else:
                _push_inconnue(rapport, "partielles", "flambage", "I calculable si d (plein) ou Do/Di (évidé) sont fournis.")

            if I_use is not None:
                Pcr = _euler_pcrit(float(E), float(I_use), L_free, K)
                rapport["flambage"] = {
                    "longueur_libre_m": L_free,
                    "K_flambage": K,
                    "charge_critique_euler_N": Pcr,
                    "marge_flambage": (Pcr / abs(float(F_ax))) if (F_ax is not None and float(F_ax) != 0.0) else None,
                }
        else:
            _push_inconnue(rapport, "partielles", "flambage", "Calculable si module_young_pa + longueur_libre_m + K_flambage + section (d ou Do/Di).")

        # ---------------------------------------------------------------------
        # 6) Taraudages (vérif/dimensionnement) — basé sur ton code initial, corrigé d’indentation
        # ---------------------------------------------------------------------
        def analyser_taraudage(
            cote: Literal["gauche", "droit"],
            filetage: Optional[str],
            profondeur_m: Optional[float],
            effort_N: Optional[float],
        ) -> Dict[str, Any]:
            out: Dict[str, Any] = {
                "filetage": filetage,
                "profondeur_taraudage_m": profondeur_m,
                "effort_axial_N": effort_N,
                "modele": {
                    "traction_noyau": "σ = F / A(d3)",
                    "arrachement_filets": "τ = F / (π * d2 * L_eng)",
                    "admissibles": "σ_adm = Re/FS ; τ_adm_eff = τ_adm/FS",
                },
                "resultats": {},
                "candidats_iso": None,
                "inconnues": [],
            }

            if effort_N is None:
                out["inconnues"].append("effort_axial_N (charge appliquée sur ce taraudage)")
                return out
            F = float(effort_N)

            # admissibles traction (matière taraudée)
            Re_taraudage = self.limite_elastique_matiere_taraudee_pa
            if Re_taraudage is None:
                Re_taraudage = Re  # fallback Re arbre si taraudage dans arbre
            sigma_allow_loc = (float(Re_taraudage) / FS) if (Re_taraudage is not None and _is_finite(Re_taraudage)) else None

            tau_adm = self.resistance_cisaillement_matiere_taraudee_pa
            tau_allow_loc = (float(tau_adm) / FS) if (tau_adm is not None and _is_finite(tau_adm)) else None

            if sigma_allow_loc is None:
                out["inconnues"].append("limite_elastique_matiere_taraudee_pa (ou Re arbre) pour traction noyau")
            if tau_allow_loc is None:
                out["inconnues"].append("resistance_cisaillement_matiere_taraudee_pa pour arrachement filets")

            L_dispo = None
            if profondeur_m is not None:
                L_dispo = _req_pos(f"profondeur_taraudage_{cote}_m", profondeur_m)
            else:
                out["inconnues"].append("profondeur_taraudage_m (engagement disponible)")

            iso = _iso_get(filetage) if filetage else None

            # CAS A : filetage choisi -> vérification
            if iso is not None:
                d2 = float(iso["d2"])
                d3 = float(iso["d3"])

                if sigma_allow_loc is not None:
                    Acore = _aire_disque(d3)
                    sigma = abs(F) / Acore
                    out["resultats"]["traction_noyau"] = {
                        "d3_m": d3,
                        "A_noyau_m2": Acore,
                        "sigma_pa": sigma,
                        "sigma_admissible_pa": sigma_allow_loc,
                        "ok": sigma <= sigma_allow_loc,
                        "marge": (sigma_allow_loc / sigma) if sigma > 0 else None,
                    }
                else:
                    out["resultats"]["traction_noyau"] = {"d3_m": d3, "note": "σ_adm inconnue."}

                if tau_allow_loc is not None and L_dispo is not None:
                    A_shear = math.pi * d2 * L_dispo
                    tau = abs(F) / A_shear
                    out["resultats"]["arrachement_filets"] = {
                        "d2_m": d2,
                        "L_eng_m": L_dispo,
                        "A_cisaillement_m2_modele": A_shear,
                        "tau_pa": tau,
                        "tau_admissible_effective_pa": tau_allow_loc,
                        "ok": tau <= tau_allow_loc,
                        "marge": (tau_allow_loc / tau) if tau > 0 else None,
                    }
                else:
                    out["resultats"]["arrachement_filets"] = {"d2_m": d2, "note": "τ_adm ou L_eng manquant."}

                out["resultats"]["iso"] = {
                    "pas_m": float(iso["p"]),
                    "d_nom_m": float(iso["d_nom"]),
                    "d_percage_m": float(iso["d_percage"]),
                }
                return out

            # CAS B : filetage non choisi -> candidats ISO annotés
            candidats = []
            for name, v in ISO_METRIQUE_PAS_GROS.items():
                d2 = float(v["d2"])
                d3 = float(v["d3"])
                # traction
                ok_tr = None
                marge_tr = None
                if sigma_allow_loc is not None:
                    sigma = abs(F) / _aire_disque(d3)
                    ok_tr = sigma <= sigma_allow_loc
                    marge_tr = (sigma_allow_loc / sigma) if sigma > 0 else None
                # arrachement
                ok_ar = None
                L_min = None
                marge_ar = None
                if tau_allow_loc is not None:
                    L_min = abs(F) / (math.pi * d2 * tau_allow_loc) if (d2 > 0 and tau_allow_loc > 0) else None
                    if L_min is not None and L_dispo is not None:
                        ok_ar = L_dispo >= L_min
                        if ok_ar:
                            tau = abs(F) / (math.pi * d2 * L_dispo)
                            marge_ar = (tau_allow_loc / tau) if tau > 0 else None

                candidats.append({
                    "filetage": name,
                    "d_nom_m": float(v["d_nom"]),
                    "pas_m": float(v["p"]),
                    "d2_m": d2,
                    "d3_m": d3,
                    "d_percage_m": float(v["d_percage"]),
                    "traction_ok": ok_tr,
                    "marge_traction": marge_tr,
                    "L_min_arrachement_m": L_min,
                    "arrachement_ok": ok_ar,
                    "marge_arrachement": marge_ar,
                    "profondeur_disponible_m": L_dispo,
                })

            candidats.sort(key=lambda x: x["d_nom_m"])
            out["candidats_iso"] = {"liste_annotée": candidats}
            return out

        rapport["taraudages"] = {
            "gauche": analyser_taraudage("gauche", self.filetage_gauche, self.profondeur_taraudage_gauche_m, self.effort_axial_sur_taraudage_gauche_N),
            "droit": analyser_taraudage("droit", self.filetage_droit, self.profondeur_taraudage_droit_m, self.effort_axial_sur_taraudage_droit_N),
        }

        # ---------------------------------------------------------------------
        # 7) Masse + inerties (si section connue + longueurs + rho)
        # ---------------------------------------------------------------------
        if rho is not None and L_mid is not None:
            Vtot = 0.0
            details = []
            # fût central : plein ou évidé
            if self.diametre_fut_central_m is not None:
                d = _req_pos("diametre_fut_central_m", self.diametre_fut_central_m)
                Vmid = _aire_disque(d) * float(L_mid)
                Vtot += Vmid
                details.append({"troncon": "fut_central_plein", "diametre_m": d, "longueur_m": float(L_mid), "volume_m3": Vmid})
                rapport["inerties"]["fut_central"] = {
                    "section_m2": _aire_disque(d),
                    "I_m4": _inertie_cercle(d),
                    "J_m4": _polaire_cercle(d),
                }
            elif self.diametre_exterieur_fut_m is not None and self.diametre_interieur_fut_m is not None:
                Do = _req_pos("diametre_exterieur_fut_m", self.diametre_exterieur_fut_m)
                Di = _req_pos("diametre_interieur_fut_m", self.diametre_interieur_fut_m, strictly=False)
                if Di < Do:
                    Amid = _aire_annulaire(Do, Di)
                    Vmid = Amid * float(L_mid)
                    Vtot += Vmid
                    details.append({"troncon": "fut_central_evide", "Do_m": Do, "Di_m": Di, "longueur_m": float(L_mid), "volume_m3": Vmid})
                    rapport["inerties"]["fut_central"] = {
                        "section_m2": Amid,
                        "I_m4": _inertie_annulaire(Do, Di),
                        "J_m4": _polaire_annulaire(Do, Di),
                    }
            else:
                _push_inconnue(rapport, "partielles", "masse fut central", "Section fût central inconnue (d plein ou Do/Di).")

            rapport["masse"] = {"volume_total_m3": Vtot, "masse_kg": float(rho) * Vtot, "detail": details}
        else:
            _push_inconnue(rapport, "partielles", "masse", "Calculable si densite_kg_m3 + longueur_fut_central_m + section fût central.")

        # ---------------------------------------------------------------------
        # 8) Cinématique
        # ---------------------------------------------------------------------
        if self.rpm is not None:
            rpm = _req_pos("rpm", self.rpm, strictly=False)
            rapport["cinematique"] = {"rpm": rpm, "omega_rad_s": _omega_from_rpm(rpm)}
        else:
            rapport["cinematique"] = {"rpm": None, "omega_rad_s": None}

        # ---------------------------------------------------------------------
        # 9) Entrées (trace)
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "longueur_totale_m": self.longueur_totale_m,
            "longueur_fut_central_m": self.longueur_fut_central_m,
            "longueur_teton_gauche_m": self.longueur_teton_gauche_m,
            "longueur_teton_droit_m": self.longueur_teton_droit_m,
            "diametre_fut_central_m": self.diametre_fut_central_m,
            "diametre_exterieur_fut_m": self.diametre_exterieur_fut_m,
            "diametre_interieur_fut_m": self.diametre_interieur_fut_m,
            "ratio_evidement_k": self.ratio_evidement_k,
            "rpm": self.rpm,
            "force_axiale_N": self.force_axiale_N,
            "force_cisaillement_N": self.force_cisaillement_N,
            "moment_flexion_Nm": self.moment_flexion_Nm,
            "couple_torsion_Nm": self.couple_torsion_Nm,
            "bras_levier_charge_m": self.bras_levier_charge_m,
            "longueur_libre_m": self.longueur_libre_m,
            "K_flambage": self.K_flambage,
            "filetage_gauche": self.filetage_gauche,
            "filetage_droit": self.filetage_droit,
            "profondeur_taraudage_gauche_m": self.profondeur_taraudage_gauche_m,
            "profondeur_taraudage_droit_m": self.profondeur_taraudage_droit_m,
            "effort_axial_sur_taraudage_gauche_N": self.effort_axial_sur_taraudage_gauche_N,
            "effort_axial_sur_taraudage_droit_N": self.effort_axial_sur_taraudage_droit_N,
            "resistance_cisaillement_matiere_taraudee_pa": self.resistance_cisaillement_matiere_taraudee_pa,
            "limite_elastique_matiere_taraudee_pa": self.limite_elastique_matiere_taraudee_pa,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "facteur_securite": self.facteur_securite,
            "k_scenarios": self.k_scenarios,
        }

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "ArbrePiston(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Exemple (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    from pprint import pprint

    # Exemple : dimensionnement évidé par scénarios k (sans choisir)
    a = ArbrePiston(
        materiau_cle=None,
        densite_kg_m3=7800.0,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        facteur_securite=2.0,

        longueur_fut_central_m=0.04,

        # efforts
        force_axiale_N=15000.0,
        force_cisaillement_N=2000.0,
        bras_levier_charge_m=0.01,  # => M=20 Nm si M non donné
        couple_torsion_Nm=None,

        # flambage
        longueur_libre_m=0.06,
        K_flambage=1.0,

        # taraudages (si non fournis => liste ISO annotée)
        profondeur_taraudage_gauche_m=0.012,
        profondeur_taraudage_droit_m=0.012,
        effort_axial_sur_taraudage_gauche_N=8000.0,
        effort_axial_sur_taraudage_droit_N=8000.0,
        resistance_cisaillement_matiere_taraudee_pa=250e6,
    )

    pprint(a.analyser(strict=False))
