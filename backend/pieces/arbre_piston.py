# backend/pieces/arbre_piston.py
# =============================================================================
# ARBRE DE PISTON — SHSE-M (version enrichie : géométrie + taraudage)
# =============================================================================
# Objectif :
# - Calculer TOUT ce qui est calculable à partir des entrées.
# - Réduire les inconnues en :
#   (1) intégrant une table ISO (filetages métriques "pas gros" courants) — donnée normative,
#       pas une invention.
#   (2) calculant les diamètres/longueurs minimaux requis, puis en listant les tailles ISO
#       compatibles (sans choisir à ta place).
#
# IMPORTANT :
# - On ne "choisit" pas un M8/M10 si tu ne le demandes pas :
#   on calcule d_noyau_min, L_engagement_min, puis on propose des candidats ISO.
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

def _von_mises_sigma_tau(sigma: float, tau: float) -> float:
    return math.sqrt(sigma**2 + 3.0 * tau**2)

def _sigma_flexion(M: float, d: float) -> float:
    W = (math.pi * d**3) / 32.0
    return M / W

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
# Filetages ISO métriques (pas gros) — table normative (données standards)
# =============================================================================

# Remarque : on stocke des grandeurs "utiles calculatoires" :
# - d_nom : diamètre nominal (m)
# - p : pas (m)
# - d2 : diamètre moyen approximatif (m) (pour cisaillement de filet)
# - d3 : diamètre au fond de filet (noyau taraudage) approximatif (m)
# - d_percage : foret de taraudage "classique" (m) (approx d_nom - p)
#
# Sans demander de sources web ici : c'est une table pratique (valeurs usuelles ISO).
# Si tu as une base normative interne, remplace cette table.
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

def _liste_filetages_compatibles_par_noyau(d_noyau_min_m: float) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for k, v in ISO_METRIQUE_PAS_GROS.items():
        if float(v["d3"]) >= float(d_noyau_min_m):
            out.append({"filetage": k, **v})
    out.sort(key=lambda x: x["d_nom"])
    return out


# =============================================================================
# Pièce : ArbrePiston
# =============================================================================

@dataclass
class ArbrePiston:
    """
    Arbre/axe de piston reliant piston et bielle.
    """

    # ----------------------------
    # Liens vers pièces (optionnels)
    # ----------------------------
    piston: Optional[Any] = None
    bielle: Optional[Any] = None
    cylindre: Optional[Any] = None

    # ----------------------------
    # Géométrie générale (toutes calculables si tu fournis)
    # ----------------------------
    # Arbre simplifié en 3 tronçons coaxiaux :
    # [téton taraudé]—[fût central]—[téton taraudé]
    longueur_totale_m: Optional[float] = None
    longueur_fut_central_m: Optional[float] = None
    longueur_teton_gauche_m: Optional[float] = None
    longueur_teton_droit_m: Optional[float] = None

    diametre_fut_central_m: Optional[float] = None      # diamètre principal (porteur)
    diametre_teton_gauche_m: Optional[float] = None     # diamètre extérieur côté filetage (si réductions)
    diametre_teton_droit_m: Optional[float] = None

    rayon_conge_gauche_m: Optional[float] = None        # géométrie pure (pas de facteur d’entaille sans Kt)
    rayon_conge_droit_m: Optional[float] = None

    # Si tu préfères une version "1 seul diamètre"
    diametre_arbre_m: Optional[float] = None  # fallback : si fourni, peut alimenter diametre_fut_central_m

    # ----------------------------
    # Cinématique (utile si frottements/équilibrage)
    # ----------------------------
    rpm: Optional[float] = None

    # ----------------------------
    # Efforts
    # ----------------------------
    force_axiale_N: Optional[float] = None
    force_cisaillement_N: Optional[float] = None
    bras_levier_charge_m: Optional[float] = None
    moment_flexion_Nm: Optional[float] = None

    # Flambage
    longueur_libre_m: Optional[float] = None
    K_flambage: Optional[float] = None

    # ----------------------------
    # Fixation taraudée (2 taraudages, un à chaque extrémité)
    # ----------------------------
    # Tu peux soit :
    # - donner directement le filetage (ex: "M8") et la profondeur de taraudage.
    # - OU ne rien donner : on calcule d_noyau_min requis et propose les filetages ISO compatibles.
    filetage_gauche: Optional[str] = None
    filetage_droit: Optional[str] = None
    profondeur_taraudage_gauche_m: Optional[float] = None
    profondeur_taraudage_droit_m: Optional[float] = None

    # Hypothèses de calcul (NON inventées) :
    # - répartition des efforts sur n_vis, sinon on considère 1 vis par taraudage si tu le dis.
    # Ici : effort par vis pour chaque taraudage (si tu as 2 vis distinctes).
    effort_axial_sur_taraudage_gauche_N: Optional[float] = None
    effort_axial_sur_taraudage_droit_N: Optional[float] = None

    # Filet : résistance au cisaillement du matériau taraudé (piston ou arbre) (sinon inconnue)
    resistance_cisaillement_matiere_taraudee_pa: Optional[float] = None

    # ----------------------------
    # Coussinet côté bielle (optionnel)
    # ----------------------------
    diametre_portee_coussinet_m: Optional[float] = None
    longueur_coussinet_m: Optional[float] = None

    # ----------------------------
    # Matériau arbre
    # ----------------------------
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None

    facteur_securite: float = 2.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "geometrie": {},
            "cinematique": {},
            "efforts": {},
            "dimensionnement": {},
            "contraintes": {},
            "flambage": {},
            "taraudages": {},
            "masse": {},
            "inerties": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ----------------------------
        # 1) Matériau
        # ----------------------------
        props_mat = _resoudre_materiau(self.materiau_cle, self.densite_kg_m3, self.limite_elastique_pa, self.module_young_pa)
        rho = props_mat["densite_kg_m3"]
        Re = props_mat["limite_elastique_pa"]
        E = props_mat["module_young_pa"]
        rapport["materiau"] = {"materiau_cle": self.materiau_cle, "densite_kg_m3": rho, "limite_elastique_pa": Re, "module_young_pa": E}

        # ----------------------------
        # 2) Efforts : déduction depuis piston si possible (sans inventer)
        # ----------------------------
        F_ax = self.force_axiale_N
        F_sh = self.force_cisaillement_N
        M = self.moment_flexion_Nm

        if self.piston is not None:
            try:
                if hasattr(self.piston, "analyser") and callable(self.piston.analyser):
                    r_p = self.piston.analyser(strict=False)  # type: ignore
                    # On cherche des champs usuels
                    dim = r_p.get("dimensionnement", {}) if isinstance(r_p, dict) else {}
                    if F_ax is None and _is_finite(dim.get("force_pression_piston_max_N")):
                        F_ax = float(dim["force_pression_piston_max_N"])
                        rapport["notes_modele"].append("force_axiale_N déduite de piston.analyser().dimensionnement.force_pression_piston_max_N")
            except Exception:
                _push_inconnue(rapport, "partielles", "efforts depuis piston", "Impossible de déduire via piston.analyser() (format/erreur).")

        if M is None and F_sh is not None and self.bras_levier_charge_m is not None:
            a = _req_pos("bras_levier_charge_m", self.bras_levier_charge_m, strictly=False)
            M = F_sh * a
            rapport["notes_modele"].append("moment_flexion_Nm déduit : M = F_cisaillement * bras_levier")

        rapport["efforts"] = {"force_axiale_N": F_ax, "force_cisaillement_N": F_sh, "moment_flexion_Nm": M}

        # ----------------------------
        # 3) Géométrie : consolidation des entrées
        # ----------------------------
        # diamètre fût central
        d_c = self.diametre_fut_central_m
        if d_c is None and self.diametre_arbre_m is not None:
            d_c = self.diametre_arbre_m
            rapport["notes_modele"].append("diametre_fut_central_m pris depuis diametre_arbre_m (fallback).")
        if d_c is not None:
            d_c = _req_pos("diametre_fut_central_m", d_c)

        # longueurs tronçons
        L_tot = self.longueur_totale_m
        L_mid = self.longueur_fut_central_m
        L_g = self.longueur_teton_gauche_m
        L_d = self.longueur_teton_droit_m

        # cohérence longueurs : si 3 tronçons fournis -> total calculable
        if L_tot is None and all(_is_finite(x) for x in (L_mid, L_g, L_d)):
            L_tot = float(L_mid) + float(L_g) + float(L_d)
            rapport["notes_modele"].append("longueur_totale_m déduite = L_central + L_gauche + L_droit.")
        if L_mid is None and all(_is_finite(x) for x in (L_tot, L_g, L_d)):
            L_mid = float(L_tot) - float(L_g) - float(L_d)
            rapport["notes_modele"].append("longueur_fut_central_m déduite = L_total - L_gauche - L_droit.")

        # validations si présents
        if L_tot is not None:
            L_tot = _req_pos("longueur_totale_m", L_tot)
        if L_mid is not None:
            L_mid = _req_pos("longueur_fut_central_m", L_mid)
        if L_g is not None:
            L_g = _req_pos("longueur_teton_gauche_m", L_g)
        if L_d is not None:
            L_d = _req_pos("longueur_teton_droit_m", L_d)

        if L_mid is not None and L_mid <= 0:
            _push_inconnue(rapport, "impossibles", "géométrie longueurs", "longueur_fut_central_m <= 0 (incohérent).")

        # diamètres tétons (si non fournis, on ne déduit pas)
        d_g = self.diametre_teton_gauche_m
        d_d = self.diametre_teton_droit_m
        if d_g is not None:
            d_g = _req_pos("diametre_teton_gauche_m", d_g)
        if d_d is not None:
            d_d = _req_pos("diametre_teton_droit_m", d_d)

        rapport["geometrie"] = {
            "diametre_fut_central_m": d_c,
            "diametre_teton_gauche_m": d_g,
            "diametre_teton_droit_m": d_d,
            "longueur_totale_m": L_tot,
            "longueur_fut_central_m": L_mid,
            "longueur_teton_gauche_m": L_g,
            "longueur_teton_droit_m": L_d,
            "rayon_conge_gauche_m": self.rayon_conge_gauche_m,
            "rayon_conge_droit_m": self.rayon_conge_droit_m,
        }

        # ----------------------------
        # 4) Contraintes sur fût central (si d_c)
        # ----------------------------
        if d_c is None:
            _push_inconnue(rapport, "impossibles", "diametre_fut_central_m", "Indispensable pour contraintes/inerties/masse.")
        else:
            A = _aire_disque(d_c)
            sigma_ax = (F_ax / A) if F_ax is not None else None
            tau = (F_sh / A) if F_sh is not None else None
            sigma_b = (_sigma_flexion(M, d_c) if M is not None else None)

            if sigma_ax is None and tau is None and sigma_b is None:
                _push_inconnue(rapport, "partielles", "contraintes arbre", "Calculables si au moins un effort est fourni.")
            else:
                s_total = 0.0
                if sigma_ax is not None:
                    s_total += float(sigma_ax)
                if sigma_b is not None:
                    s_total += float(sigma_b)
                t_total = float(tau) if tau is not None else 0.0
                sigma_eq = _von_mises_sigma_tau(s_total, t_total)

                sigma_allow = None
                marge = None
                if Re is not None:
                    sigma_allow = float(Re) / FS
                    marge = (sigma_allow / sigma_eq) if sigma_eq > 0 else None
                else:
                    _push_inconnue(rapport, "partielles", "marge matériau", "Marge calculable si limite_elastique_pa (ou materiau_cle) est fourni.")

                rapport["contraintes"] = {
                    "sigma_axiale_pa": sigma_ax,
                    "tau_cisaillement_pa": tau,
                    "sigma_flexion_pa": sigma_b,
                    "sigma_von_mises_pa": sigma_eq,
                    "sigma_admissible_pa": sigma_allow,
                    "marge_von_mises": marge,
                }

            # inerties
            I = _inertie_cercle(d_c)
            Jp = _polaire_cercle(d_c)
            rapport["inerties"] = {
                "section_m2": A,
                "inertie_flexion_I_m4": I,
                "inertie_polaire_J_m4": Jp,
            }

        # ----------------------------
        # 5) Flambage (Euler) si données
        # ----------------------------
        if d_c is not None and E is not None and self.longueur_libre_m is not None and self.K_flambage is not None:
            L_free = _req_pos("longueur_libre_m", self.longueur_libre_m)
            K = _req_pos("K_flambage", self.K_flambage)
            I = _inertie_cercle(d_c)
            Pcr = _euler_pcrit(float(E), I, L_free, K)
            rapport["flambage"] = {
                "longueur_libre_m": L_free,
                "K_flambage": K,
                "charge_critique_euler_N": Pcr,
                "marge_flambage": (Pcr / abs(F_ax)) if (F_ax is not None and F_ax != 0) else None,
            }
        else:
            _push_inconnue(rapport, "partielles", "flambage", "Calculable si module_young_pa, longueur_libre_m, K_flambage et diametre_fut_central_m sont fournis.")

    # Patch à appliquer dans backend/pieces/arbre_piston.py
    # Objectif : faire dépendre le taraudage des contraintes mécaniques
    # - calcule d_noyau_min (traction au noyau) à partir de F et Re/FS
    # - calcule L_engagement_min (arrachement filets) à partir de F et tau_adm/FS
    # - si filetage NON fourni : propose uniquement les filetages ISO qui satisfont
    #   (1) traction noyau ET (2) arrachement filets avec la profondeur dispo
    # - si filetage fourni : vérifie traction + arrachement, et calcule les marges

    # ---------------------------------------------------------------------
    # AJOUT : résistance traction / cisaillement admissibles côté taraudage
    # ---------------------------------------------------------------------
    # Dans ta dataclass ArbrePiston, garde :
    #   resistance_cisaillement_matiere_taraudee_pa
    # et ajoute (optionnel) une limite en traction côté filets si tu veux :
    #   limite_elastique_matiere_taraudee_pa  (souvent = Re du piston si taraudé dans piston)
    #
    # Si tu ne la fournis pas, on utilisera Re de l'arbre (si c'est l'arbre qui est taraudé)
    # sinon on laissera inconnue.

    # Ajoute dans la dataclass :
    # limite_elastique_matiere_taraudee_pa: Optional[float] = None


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
                "d2": "diamètre moyen ISO (table) ou inconnu",
                "d3": "diamètre noyau taraudage ISO (table) ou inconnu",
                "admissibles": "σ_adm = Re/FS ; τ_adm_eff = τ_adm/FS",
            },
            "resultats": {},
            "candidats_iso": None,
            "inconnues": [],
        }

        # 0) effort
        if effort_N is None:
            out["inconnues"].append("effort_axial_N (charge appliquée sur ce taraudage)")
            return out
        F = float(effort_N)

        # 1) admissibles
        # Re_taraudage : si tu fournis limite_elastique_matiere_taraudee_pa -> priorité,
        # sinon on retombe sur Re de l'arbre (si taraudage dans arbre), sinon inconnue.
        Re_taraudage = getattr(self, "limite_elastique_matiere_taraudee_pa", None)
        if Re_taraudage is None:
            Re_taraudage = Re  # Re de l'arbre (déjà résolu)
        tau_adm = self.resistance_cisaillement_matiere_taraudee_pa

        sigma_allow = None
        tau_allow = None
        if Re_taraudage is not None and _is_finite(Re_taraudage):
            sigma_allow = float(Re_taraudage) / FS
        else:
            out["inconnues"].append("limite_elastique_matiere_taraudee_pa (ou Re arbre) pour dimensionner traction noyau")

        if tau_adm is not None and _is_finite(tau_adm):
            tau_allow = float(tau_adm) / FS
        else:
            out["inconnues"].append("resistance_cisaillement_matiere_taraudee_pa pour dimensionner arrachement filets")

        # 2) profondeur disponible
        L_dispo = None
        if profondeur_m is not None:
            L_dispo = _req_pos(f"profondeur_taraudage_{cote}_m", profondeur_m)
        else:
            out["inconnues"].append("profondeur_taraudage_m (engagement disponible)")

        # -----------------------------------------------------------------
        # CAS A : filetage déjà choisi -> on vérifie contraintes + marges
        # -----------------------------------------------------------------
        iso = _iso_get(filetage) if filetage else None
        if iso is not None:
            d2 = float(iso["d2"])
            d3 = float(iso["d3"])

            # traction noyau
            if sigma_allow is not None:
                Acore = _aire_disque(d3)
                sigma = abs(F) / Acore
                out["resultats"]["traction_noyau"] = {
                    "d3_m": d3,
                    "A_noyau_m2": Acore,
                    "sigma_pa": sigma,
                    "sigma_admissible_pa": sigma_allow,
                    "ok": sigma <= sigma_allow,
                    "marge": (sigma_allow / sigma) if sigma > 0 else None,
                }
            else:
                out["resultats"]["traction_noyau"] = {"d3_m": d3, "note": "σ_adm inconnue (Re manquant)."}

            # arrachement filets
            if tau_allow is not None and L_dispo is not None:
                A_shear = math.pi * d2 * L_dispo
                tau = abs(F) / A_shear
                out["resultats"]["arrachement_filets"] = {
                    "d2_m": d2,
                    "L_eng_m": L_dispo,
                    "A_cisaillement_m2_modele": A_shear,
                    "tau_pa": tau,
                    "tau_admissible_effective_pa": tau_allow,
                    "ok": tau <= tau_allow,
                    "marge": (tau_allow / tau) if tau > 0 else None,
                }
            else:
                out["resultats"]["arrachement_filets"] = {"d2_m": d2, "note": "τ_adm ou L_eng manquant."}

            # info foret taraudage
            out["resultats"]["iso"] = {
                "pas_m": float(iso["p"]),
                "d_nom_m": float(iso["d_nom"]),
                "d_percage_m": float(iso["d_percage"]),
            }
            return out

        # -----------------------------------------------------------------
        # CAS B : filetage NON choisi -> on DIMENSIONNE et PROPOSE
        # -----------------------------------------------------------------
        # 1) d_noyau_min via traction
        d3_min = None
        if sigma_allow is not None:
            A_min = abs(F) / sigma_allow if sigma_allow > 0 else None
            if A_min is not None:
                d3_min = math.sqrt((4.0 * A_min) / math.pi)
                out["resultats"]["traction_dimensionnement"] = {
                    "sigma_admissible_pa": sigma_allow,
                    "aire_min_m2": A_min,
                    "d3_min_m": d3_min,
                }

        # 2) L_min via arrachement (si d2 connu -> dépend du filetage, donc on fera ça par candidat)
        # On filtre les filetages ISO :
        candidats = []
        for name, v in ISO_METRIQUE_PAS_GROS.items():
            d2 = float(v["d2"])
            d3 = float(v["d3"])

            # critère traction noyau
            ok_traction = True
            marge_tr = None
            if d3_min is not None:
                ok_traction = d3 >= d3_min
                if ok_traction and sigma_allow is not None:
                    sigma = abs(F) / _aire_disque(d3)
                    marge_tr = (sigma_allow / sigma) if sigma > 0 else None

            # critère arrachement filets
            ok_filets = True
            L_min = None
            marge_f = None
            if tau_allow is not None:
                # τ = F / (π d2 L) <= τ_allow  -> L >= F / (π d2 τ_allow)
                L_min = abs(F) / (math.pi * d2 * tau_allow) if (d2 > 0 and tau_allow > 0) else None
                if L_min is not None:
                    if L_dispo is None:
                        ok_filets = False
                    else:
                        ok_filets = L_dispo >= L_min
                        if ok_filets:
                            # marge en utilisant L_dispo
                            tau = abs(F) / (math.pi * d2 * L_dispo)
                            marge_f = (tau_allow / tau) if tau > 0 else None

            # On retient les candidats uniquement si on peut conclure
            # (si sigma_allow ou tau_allow manquent, on ne peut pas filtrer correctement -> on liste quand même, mais flag)
            verdict = True
            infos_incompletes = False
            if sigma_allow is None:
                infos_incompletes = True
            else:
                verdict = verdict and ok_traction
            if tau_allow is None or L_dispo is None:
                infos_incompletes = True
            else:
                verdict = verdict and ok_filets

            candidats.append({
                "filetage": name,
                "d_nom_m": float(v["d_nom"]),
                "pas_m": float(v["p"]),
                "d2_m": d2,
                "d3_m": d3,
                "d_percage_m": float(v["d_percage"]),
                "critere_traction_ok": ok_traction if sigma_allow is not None else None,
                "d3_min_m": d3_min,
                "marge_traction": marge_tr,
                "L_min_arrachement_m": L_min,
                "critere_arrachement_ok": ok_filets if (tau_allow is not None and L_dispo is not None) else None,
                "marge_arrachement": marge_f,
                "infos_incompletes": infos_incompletes,
                "verdict_ok": verdict if not infos_incompletes else None,
            })

        # tri : d_nom croissant
        candidats.sort(key=lambda x: x["d_nom_m"])

        # si on a assez d'infos, on peut extraire les "OK"
        if sigma_allow is not None and tau_allow is not None and L_dispo is not None:
            out["candidats_iso"] = {
                "profondeur_disponible_m": L_dispo,
                "liste_ok": [c for c in candidats if c["verdict_ok"] is True],
                "liste_ko": [c for c in candidats if c["verdict_ok"] is False],
            }
            if not out["candidats_iso"]["liste_ok"]:
                out["inconnues"].append(
                    "Aucun filetage ISO (table) ne passe traction+arrachement avec la profondeur dispo : "
                    "augmenter profondeur_taraudage_m, changer matériau (Re/tau), réduire effort, ou élargir table ISO."
                )
        else:
            # info insuffisante pour filtrer, on fournit la liste annotée
            out["candidats_iso"] = {"liste_annotée": candidats}

        return out


        taraud_g = analyser_taraudage("gauche", self.filetage_gauche, self.profondeur_taraudage_gauche_m, self.effort_axial_sur_taraudage_gauche_N)
        taraud_d = analyser_taraudage("droit", self.filetage_droit, self.profondeur_taraudage_droit_m, self.effort_axial_sur_taraudage_droit_N)

        rapport["taraudages"] = {"gauche": taraud_g, "droit": taraud_d}

        # ----------------------------
        # 7) Masse + inerties (si géométrie complète + rho)
        # ----------------------------
        # Modèle : somme de cylindres coaxiaux
        if rho is None:
            _push_inconnue(rapport, "partielles", "masse", "Calculable si densite_kg_m3 (ou materiau_cle résoluble) est fournie.")
        else:
            if not all(_is_finite(x) for x in (L_mid, L_g, L_d)):
                _push_inconnue(rapport, "partielles", "masse", "Calculable si longueurs tronçons (L_central, L_gauche, L_droit) sont fournies ou déductibles.")
            else:
                # diamètres : si tétons non donnés, on ne les invente pas -> masse partielle
                V = 0.0
                parts = []
                if d_c is not None:
                    V_mid = _aire_disque(d_c) * float(L_mid)
                    V += V_mid
                    parts.append({"troncon": "fut_central", "diametre_m": d_c, "longueur_m": float(L_mid), "volume_m3": V_mid})
                else:
                    _push_inconnue(rapport, "impossibles", "masse", "diametre_fut_central_m manquant.")

                if d_g is not None:
                    Vg = _aire_disque(d_g) * float(L_g)
                    V += Vg
                    parts.append({"troncon": "teton_gauche", "diametre_m": d_g, "longueur_m": float(L_g), "volume_m3": Vg})
                else:
                    _push_inconnue(rapport, "partielles", "masse téton gauche", "Calculable si diametre_teton_gauche_m est fourni.")

                if d_d is not None:
                    Vd = _aire_disque(d_d) * float(L_d)
                    V += Vd
                    parts.append({"troncon": "teton_droit", "diametre_m": d_d, "longueur_m": float(L_d), "volume_m3": Vd})
                else:
                    _push_inconnue(rapport, "partielles", "masse téton droit", "Calculable si diametre_teton_droit_m est fourni.")

                m = float(rho) * V
                rapport["masse"] = {"volume_total_m3": V, "masse_kg": m, "detail": parts}

        # ----------------------------
        # 8) Cinématique (optionnel)
        # ----------------------------
        if self.rpm is not None:
            rpm = _req_pos("rpm", self.rpm, strictly=False)
            rapport["cinematique"] = {"rpm": rpm, "omega_rad_s": _omega_from_rpm(rpm)}
        else:
            rapport["cinematique"] = {"rpm": None, "omega_rad_s": None}

        # ----------------------------
        # 9) Entrées (trace)
        # ----------------------------
        rapport["entrees"] = {
            "longueur_totale_m": self.longueur_totale_m,
            "longueur_fut_central_m": self.longueur_fut_central_m,
            "longueur_teton_gauche_m": self.longueur_teton_gauche_m,
            "longueur_teton_droit_m": self.longueur_teton_droit_m,
            "diametre_fut_central_m": self.diametre_fut_central_m,
            "diametre_teton_gauche_m": self.diametre_teton_gauche_m,
            "diametre_teton_droit_m": self.diametre_teton_droit_m,
            "diametre_arbre_m": self.diametre_arbre_m,
            "rayon_conge_gauche_m": self.rayon_conge_gauche_m,
            "rayon_conge_droit_m": self.rayon_conge_droit_m,
            "rpm": self.rpm,
            "force_axiale_N": self.force_axiale_N,
            "force_cisaillement_N": self.force_cisaillement_N,
            "bras_levier_charge_m": self.bras_levier_charge_m,
            "moment_flexion_Nm": self.moment_flexion_Nm,
            "longueur_libre_m": self.longueur_libre_m,
            "K_flambage": self.K_flambage,
            "filetage_gauche": self.filetage_gauche,
            "filetage_droit": self.filetage_droit,
            "profondeur_taraudage_gauche_m": self.profondeur_taraudage_gauche_m,
            "profondeur_taraudage_droit_m": self.profondeur_taraudage_droit_m,
            "effort_axial_sur_taraudage_gauche_N": self.effort_axial_sur_taraudage_gauche_N,
            "effort_axial_sur_taraudage_droit_N": self.effort_axial_sur_taraudage_droit_N,
            "resistance_cisaillement_matiere_taraudee_pa": self.resistance_cisaillement_matiere_taraudee_pa,
            "diametre_portee_coussinet_m": self.diametre_portee_coussinet_m,
            "longueur_coussinet_m": self.longueur_coussinet_m,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "facteur_securite": self.facteur_securite,
        }

        # ----------------------------
        # 10) Mode strict
        # ----------------------------
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

    a = ArbrePiston(
        materiau_cle=None,
        densite_kg_m3=7800.0,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        facteur_securite=2.0,

        # géométrie
        diametre_fut_central_m=0.02,
        longueur_fut_central_m=0.04,
        longueur_teton_gauche_m=0.01,
        longueur_teton_droit_m=0.01,
        diametre_teton_gauche_m=0.018,
        diametre_teton_droit_m=0.018,

        # efforts
        force_axiale_N=15000.0,
        force_cisaillement_N=2000.0,
        bras_levier_charge_m=0.01,

        # flambage
        longueur_libre_m=0.06,
        K_flambage=1.0,

        # taraudages (si non fournis, on sort d_noyau_min + candidats ISO)
        filetage_gauche=None,
        filetage_droit=None,
        profondeur_taraudage_gauche_m=0.012,
        profondeur_taraudage_droit_m=0.012,
        effort_axial_sur_taraudage_gauche_N=8000.0,
        effort_axial_sur_taraudage_droit_N=8000.0,
        resistance_cisaillement_matiere_taraudee_pa=250e6,
    )

    pprint(a.analyser(strict=False))
