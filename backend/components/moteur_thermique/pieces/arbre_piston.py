# backend/components/moteur_thermique/pieces/arbre_piston.py
# =============================================================================
# ARBRE DE PISTON — SHSE-M
# Version complétée : CAO + arbre plein/évidé + cisaillement + torsion + flexion
# + flambage + taraudages ISO + géométrie exploitable SolidWorks
# =============================================================================
# Objectif "rien inventer" :
# - Ne PAS choisir une géométrie finale unique si une donnée manque.
# - Calculer tout ce qui est calculable à partir :
#   - des efforts fournis,
#   - des efforts déduits du piston si piston.analyser() est exploitable,
#   - du matériau via materiaux.py si dispo,
#   - des géométries déjà connues (taraudages, portées, évidement, longueurs),
#   - des scénarios de k = Di/Do si l’évidement n’est pas imposé.
#
# Le module :
# - vérifie une géométrie imposée (plein ou évidé),
# - ou dimensionne l’arbre central en scénarios si la géométrie n’est pas entièrement fixée,
# - produit un bloc "cao" pour faciliter le dessin 3D sous SolidWorks.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List, Literal
import math


# =============================================================================
# Utilitaires
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": nom, "raison": raison}
    )


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

    rapport["inconnues"]["impossibles"] = dedup(list(rapport["inconnues"].get("impossibles", []) or []))
    rapport["inconnues"]["partielles"] = dedup(list(rapport["inconnues"].get("partielles", []) or []))


def _safe_get_dict(obj: Any, key: str) -> Dict[str, Any]:
    if isinstance(obj, dict):
        v = obj.get(key, {})
        return v if isinstance(v, dict) else {}
    return {}


def _aire_disque(d: float) -> float:
    r = 0.5 * _req_pos("d", d)
    return math.pi * r * r


def _aire_annulaire(Do: float, Di: float) -> float:
    Do_v = _req_pos("Do", Do)
    Di_v = _req_pos("Di", Di, strictly=False)
    if Di_v >= Do_v:
        raise ValueError("Di doit être < Do.")
    return (math.pi / 4.0) * (Do_v * Do_v - Di_v * Di_v)


def _inertie_cercle(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**4) / 64.0


def _polaire_cercle(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**4) / 32.0


def _inertie_annulaire(Do: float, Di: float) -> float:
    Do_v = _req_pos("Do", Do)
    Di_v = _req_pos("Di", Di, strictly=False)
    if Di_v >= Do_v:
        raise ValueError("Di doit être < Do.")
    return (math.pi * (Do_v**4 - Di_v**4)) / 64.0


def _polaire_annulaire(Do: float, Di: float) -> float:
    Do_v = _req_pos("Do", Do)
    Di_v = _req_pos("Di", Di, strictly=False)
    if Di_v >= Do_v:
        raise ValueError("Di doit être < Do.")
    return (math.pi * (Do_v**4 - Di_v**4)) / 32.0


def _module_flexion_cercle(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**3) / 32.0


def _module_flexion_annulaire(Do: float, Di: float) -> float:
    I = _inertie_annulaire(Do, Di)
    return I / (_req_pos("Do", Do) / 2.0)


def _sigma_flexion_plein(M: float, d: float) -> float:
    return abs(float(M)) / _module_flexion_cercle(d)


def _sigma_flexion_annulaire(M: float, Do: float, Di: float) -> float:
    return abs(float(M)) / _module_flexion_annulaire(Do, Di)


def _von_mises_sigma_tau(sigma: float, tau: float) -> float:
    return math.sqrt(float(sigma) ** 2 + 3.0 * float(tau) ** 2)


def _omega_from_rpm(rpm: float) -> float:
    return 2.0 * math.pi * (_req_pos("rpm", rpm, strictly=False) / 60.0)


def _euler_pcrit(E: float, I: float, L: float, K: float) -> float:
    E_v = _req_pos("E", E)
    I_v = _req_pos("I", I)
    L_v = _req_pos("L", L)
    K_v = _req_pos("K", K)
    return (math.pi ** 2) * E_v * I_v / ((K_v * L_v) ** 2)


def _tau_y_vm(Re: float) -> float:
    return float(Re) / math.sqrt(3.0)


def _tau_y_tresca(Re: float) -> float:
    return float(Re) / 2.0


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
                    mat = mod.get_materiau(materiau_cle)  # type: ignore[attr-defined]
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
                Re = Re if Re is not None else g(
                    mat,
                    "limite_elastique_pa",
                    "Re_pa",
                    "rp02_pa",
                    "yield_strength_pa",
                )
                E = E if E is not None else g(
                    mat,
                    "module_young_pa",
                    "E_pa",
                    "young_pa",
                    "young_modulus_pa",
                )
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "limite_elastique_pa": Re,
        "module_young_pa": E,
    }


# =============================================================================
# Résolution depuis piston / cylindre
# =============================================================================

def _resoudre_depuis_piston(piston: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "force_axiale_nette_n": None,
        "force_gaz_n": None,
        "hauteur_totale_piston_m": None,
        "diametre_piston_nominal_m": None,
    }
    if piston is None:
        return out

    try:
        if hasattr(piston, "analyser") and callable(getattr(piston, "analyser")):
            rep = piston.analyser(strict=False)  # type: ignore[misc]
        elif isinstance(piston, dict):
            rep = piston
        else:
            rep = None
    except Exception:
        rep = None

    if not isinstance(rep, dict):
        return out

    out["rapport"] = rep
    cin = _safe_get_dict(rep, "cinematique")
    dim = _safe_get_dict(rep, "dimensions")
    cao = _safe_get_dict(dim, "cao")

    if _is_finite(cin.get("force_axiale_nette_n")):
        out["force_axiale_nette_n"] = float(cin["force_axiale_nette_n"])
    if _is_finite(cin.get("force_gaz_n")):
        out["force_gaz_n"] = float(cin["force_gaz_n"])
    if _is_finite(dim.get("hauteur_totale_m")):
        out["hauteur_totale_piston_m"] = float(dim["hauteur_totale_m"])
    if _is_finite(cao.get("diametre_exterieur_nominal_m")):
        out["diametre_piston_nominal_m"] = float(cao["diametre_exterieur_nominal_m"])

    return out


def _resoudre_depuis_cylindre(cylindre: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "alesage_m": None,
        "course_m": None,
        "pression_max_pa": None,
    }
    if cylindre is None:
        return out

    try:
        if hasattr(cylindre, "analyser") and callable(getattr(cylindre, "analyser")):
            rep = cylindre.analyser(strict=False)  # type: ignore[misc]
        elif isinstance(cylindre, dict):
            rep = cylindre
        else:
            rep = None
    except Exception:
        rep = None

    if not isinstance(rep, dict):
        return out

    out["rapport"] = rep
    ent = _safe_get_dict(rep, "entrees")
    if _is_finite(ent.get("alesage_m")):
        out["alesage_m"] = float(ent["alesage_m"])
    if _is_finite(ent.get("course_m")):
        out["course_m"] = float(ent["course_m"])
    if _is_finite(ent.get("pression_max_pa")):
        out["pression_max_pa"] = float(ent["pression_max_pa"])

    return out


# =============================================================================
# Filetages ISO métriques (pas gros) — table standard
# =============================================================================

ISO_METRIQUE_PAS_GROS: Dict[str, Dict[str, float]] = {
    "M3":  {"d_nom": 3e-3,  "p": 0.5e-3,  "d2": 2.675e-3,  "d3": 2.387e-3,  "d_percage": 2.5e-3},
    "M4":  {"d_nom": 4e-3,  "p": 0.7e-3,  "d2": 3.545e-3,  "d3": 3.141e-3,  "d_percage": 3.3e-3},
    "M5":  {"d_nom": 5e-3,  "p": 0.8e-3,  "d2": 4.480e-3,  "d3": 4.019e-3,  "d_percage": 4.2e-3},
    "M6":  {"d_nom": 6e-3,  "p": 1.0e-3,  "d2": 5.350e-3,  "d3": 4.773e-3,  "d_percage": 5.0e-3},
    "M8":  {"d_nom": 8e-3,  "p": 1.25e-3, "d2": 7.188e-3,  "d3": 6.466e-3,  "d_percage": 6.8e-3},
    "M10": {"d_nom": 10e-3, "p": 1.5e-3,  "d2": 9.026e-3,  "d3": 8.160e-3,  "d_percage": 8.5e-3},
    "M12": {"d_nom": 12e-3, "p": 1.75e-3, "d2": 10.863e-3, "d3": 9.853e-3,  "d_percage": 10.2e-3},
    "M14": {"d_nom": 14e-3, "p": 2.0e-3,  "d2": 12.701e-3, "d3": 11.546e-3, "d_percage": 12.0e-3},
    "M16": {"d_nom": 16e-3, "p": 2.0e-3,  "d2": 14.701e-3, "d3": 13.546e-3, "d_percage": 14.0e-3},
}


def _iso_get(filetage: str) -> Optional[Dict[str, float]]:
    return ISO_METRIQUE_PAS_GROS.get(filetage.upper().strip())


def _d_nom_depuis_filetage(filetage: Optional[str]) -> Optional[float]:
    if not filetage:
        return None
    iso = _iso_get(filetage)
    if iso is None:
        return None
    return float(iso["d_nom"])


# =============================================================================
# Règles explicites de fabrication / CAO
# =============================================================================

@dataclass(frozen=True)
class ReglesFabricationArbrePiston:
    # Géométrie des portées / épaulements
    marge_longueur_teton_sur_taraudage_m: float = 0.003
    marge_epaulement_sur_fut_m: float = 0.001
    longueur_min_fut_sur_diametre: float = 0.50

    # Détails CAO
    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.0020
    conge_min_m: float = 0.0005
    conge_max_m: float = 0.0030
    ratio_conge_sur_diametre: float = 0.08

    # Tolérances / finition
    rugosite_fut_ra_um: float = 0.8
    rugosite_tetons_ra_um: float = 1.6
    tolerance_diametre_fut_m: float = 0.00003
    tolerance_diametre_tetons_m: float = 0.00003
    tolerance_longueur_m: float = 0.00005


# =============================================================================
# Dimensionnement arbre plein / évidé
# =============================================================================

def _solve_Do_min_for_tauV(V: float, tau_allow: float, k: float) -> float:
    if not (0.0 <= k < 1.0):
        raise ValueError("k (Di/Do) doit être dans [0,1).")
    denom = math.pi * float(tau_allow) * (1.0 - k * k)
    if denom <= 0.0:
        raise ValueError("tau_allow et (1-k²) doivent donner un dénominateur > 0.")
    return math.sqrt((4.0 * abs(float(V))) / denom)


def _solve_Do_min_for_tauT(T: float, tau_allow: float, k: float) -> float:
    if not (0.0 <= k < 1.0):
        raise ValueError("k (Di/Do) doit être dans [0,1).")
    denom = math.pi * float(tau_allow) * (1.0 - k**4)
    if denom <= 0.0:
        raise ValueError("tau_allow et (1-k⁴) doivent donner un dénominateur > 0.")
    return (16.0 * abs(float(T)) / denom) ** (1.0 / 3.0)


def _solve_Do_min_for_sig_ax(F: float, sigma_allow: float, k: float) -> float:
    return _solve_Do_min_for_tauV(F, sigma_allow, k)


def _solve_Do_min_for_sig_b(M: float, sigma_allow: float, k: float) -> float:
    if not (0.0 <= k < 1.0):
        raise ValueError("k (Di/Do) doit être dans [0,1).")
    denom = math.pi * float(sigma_allow) * (1.0 - k**4)
    if denom <= 0.0:
        raise ValueError("sigma_allow et (1-k⁴) doivent donner un dénominateur > 0.")
    return (32.0 * abs(float(M)) / denom) ** (1.0 / 3.0)


def _compute_section_props(Do: float, Di: float) -> Dict[str, float]:
    if Di <= 0.0:
        A = _aire_disque(Do)
        I = _inertie_cercle(Do)
        J = _polaire_cercle(Do)
        W = _module_flexion_cercle(Do)
    else:
        A = _aire_annulaire(Do, Di)
        I = _inertie_annulaire(Do, Di)
        J = _polaire_annulaire(Do, Di)
        W = _module_flexion_annulaire(Do, Di)

    return {
        "section_m2": A,
        "I_m4": I,
        "J_m4": J,
        "W_m3": W,
        "rayon_ext_m": Do / 2.0,
    }


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

    # Géométrie générale
    longueur_totale_m: Optional[float] = None
    longueur_fut_central_m: Optional[float] = None
    longueur_teton_gauche_m: Optional[float] = None
    longueur_teton_droit_m: Optional[float] = None

    # Section centrale pleine
    diametre_fut_central_m: Optional[float] = None

    # Section centrale évidée
    diametre_exterieur_fut_m: Optional[float] = None
    diametre_interieur_fut_m: Optional[float] = None
    ratio_evidement_k: Optional[float] = None

    # Tétons / extrémités
    diametre_teton_gauche_m: Optional[float] = None
    diametre_teton_droit_m: Optional[float] = None

    # Congés / chanfreins
    rayon_conge_gauche_m: Optional[float] = None
    rayon_conge_droit_m: Optional[float] = None
    chanfrein_gauche_m: Optional[float] = None
    chanfrein_droit_m: Optional[float] = None

    # Cinématique
    rpm: Optional[float] = None

    # Efforts
    force_axiale_N: Optional[float] = None
    force_cisaillement_N: Optional[float] = None
    bras_levier_charge_m: Optional[float] = None
    moment_flexion_Nm: Optional[float] = None
    couple_torsion_Nm: Optional[float] = None

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

    # Résistance matière taraudée
    resistance_cisaillement_matiere_taraudee_pa: Optional[float] = None
    limite_elastique_matiere_taraudee_pa: Optional[float] = None

    # Portée coussinet / liaison
    diametre_portee_coussinet_m: Optional[float] = None
    longueur_coussinet_m: Optional[float] = None

    # Matériau arbre
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None

    # Dimensionnement
    facteur_securite: float = 2.0

    # Scénarios de k si non imposé
    k_scenarios: Tuple[float, ...] = (0.0, 0.3, 0.5, 0.6, 0.7)

    # Règles explicites CAO
    regles_fabrication: ReglesFabricationArbrePiston = field(default_factory=ReglesFabricationArbrePiston)

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "sources": {},
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
            "cao": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        # ---------------------------------------------------------------------
        # 1) Résolution depuis piston / cylindre
        # ---------------------------------------------------------------------
        pist = _resoudre_depuis_piston(self.piston)
        cyl = _resoudre_depuis_cylindre(self.cylindre)

        # ---------------------------------------------------------------------
        # 2) Matériau
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
                "tau_allow_vm_pa": tau_allow_vm,
                "tau_allow_tresca_pa": tau_allow_tresca,
                "note": "Deux critères théoriques (VM/Tresca) donnés sans sélection automatique.",
            },
        }
        if Re is None:
            _push_inconnue(rapport, "partielles", "limite_elastique_pa", "Re requis pour contraintes admissibles.")
        if rho is None:
            _push_inconnue(rapport, "partielles", "densite_kg_m3", "rho requis pour masse.")

        # ---------------------------------------------------------------------
        # 3) Efforts
        # ---------------------------------------------------------------------
        F_ax = self.force_axiale_N
        V = self.force_cisaillement_N
        M = self.moment_flexion_Nm
        T = self.couple_torsion_Nm

        if F_ax is None and pist["force_axiale_nette_n"] is not None:
            F_ax = float(pist["force_axiale_nette_n"])
            rapport["sources"]["force_axiale_N"] = "piston.analyser().cinematique.force_axiale_nette_n"
        elif F_ax is None and pist["force_gaz_n"] is not None:
            F_ax = float(pist["force_gaz_n"])
            rapport["sources"]["force_axiale_N"] = "piston.analyser().cinematique.force_gaz_n"

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
        # 4) Géométrie longueurs
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

        # Si filetage et profondeurs connus, on peut déduire longueur mini des tétons
        if L_g is None and self.profondeur_taraudage_gauche_m is not None:
            L_g = _req_pos("profondeur_taraudage_gauche_m", self.profondeur_taraudage_gauche_m) + self.regles_fabrication.marge_longueur_teton_sur_taraudage_m
            rapport["notes_modele"].append("longueur_teton_gauche_m déduite depuis profondeur de taraudage + marge explicite.")
        if L_d is None and self.profondeur_taraudage_droit_m is not None:
            L_d = _req_pos("profondeur_taraudage_droit_m", self.profondeur_taraudage_droit_m) + self.regles_fabrication.marge_longueur_teton_sur_taraudage_m
            rapport["notes_modele"].append("longueur_teton_droit_m déduite depuis profondeur de taraudage + marge explicite.")

        # Si toujours absent, tentative de déduction simple depuis le piston
        if L_mid is None and pist["hauteur_totale_piston_m"] is not None:
            L_mid = max(
                self.regles_fabrication.longueur_min_fut_sur_diametre * (pist["diametre_piston_nominal_m"] or 0.0),
                0.5 * float(pist["hauteur_totale_piston_m"]),
            )
            if L_mid > 0.0:
                rapport["notes_modele"].append("longueur_fut_central_m estimée via hauteur piston et règle explicite.")

        if L_tot is not None:
            L_tot = _req_pos("longueur_totale_m", L_tot)
        if L_mid is not None:
            L_mid = _req_pos("longueur_fut_central_m", L_mid)
        if L_g is not None:
            L_g = _req_pos("longueur_teton_gauche_m", L_g)
        if L_d is not None:
            L_d = _req_pos("longueur_teton_droit_m", L_d)

        # Si L_tot absent mais L_mid/L_g/L_d connus après déductions
        if L_tot is None and all(_is_finite(x) for x in (L_mid, L_g, L_d)):
            L_tot = float(L_mid) + float(L_g) + float(L_d)

        rapport["geometrie"].update({
            "longueur_totale_m": L_tot,
            "longueur_fut_central_m": L_mid,
            "longueur_teton_gauche_m": L_g,
            "longueur_teton_droit_m": L_d,
        })

        # ---------------------------------------------------------------------
        # 5) Diamètres des tétons
        # ---------------------------------------------------------------------
        D_tg = self.diametre_teton_gauche_m
        D_td = self.diametre_teton_droit_m

        if D_tg is None:
            D_tg = _d_nom_depuis_filetage(self.filetage_gauche)
            if D_tg is not None:
                rapport["notes_modele"].append("diametre_teton_gauche_m déduit du diamètre nominal du filetage gauche.")
        if D_td is None:
            D_td = _d_nom_depuis_filetage(self.filetage_droit)
            if D_td is not None:
                rapport["notes_modele"].append("diametre_teton_droit_m déduit du diamètre nominal du filetage droit.")

        if self.diametre_portee_coussinet_m is not None:
            D_portee = _req_pos("diametre_portee_coussinet_m", self.diametre_portee_coussinet_m)
        else:
            D_portee = None

        if D_tg is None and D_portee is not None:
            D_tg = D_portee
        if D_td is None and D_portee is not None:
            D_td = D_portee

        if D_tg is not None:
            D_tg = _req_pos("diametre_teton_gauche_m", D_tg)
        if D_td is not None:
            D_td = _req_pos("diametre_teton_droit_m", D_td)

        rapport["geometrie"].update({
            "diametre_teton_gauche_m": D_tg,
            "diametre_teton_droit_m": D_td,
            "diametre_portee_coussinet_m": D_portee,
            "longueur_coussinet_m": self.longueur_coussinet_m,
        })

        # ---------------------------------------------------------------------
        # 6) Section centrale : imposée ou dimensionnée
        # ---------------------------------------------------------------------
        Do_in = self.diametre_exterieur_fut_m
        Di_in = self.diametre_interieur_fut_m
        d_plein = self.diametre_fut_central_m
        k_in = self.ratio_evidement_k

        if Do_in is not None:
            Do_in = _req_pos("diametre_exterieur_fut_m", Do_in)
        if Di_in is not None:
            Di_in = _req_pos("diametre_interieur_fut_m", Di_in, strictly=False)
        if d_plein is not None:
            d_plein = _req_pos("diametre_fut_central_m", d_plein)
        if k_in is not None:
            k_in = _req_finite("ratio_evidement_k", k_in)
            if not (0.0 <= k_in < 1.0):
                _push_inconnue(rapport, "impossibles", "ratio_evidement_k", "k doit être dans [0,1).")

        if Do_in is None and d_plein is not None:
            Do_in = d_plein
            if Di_in is None:
                Di_in = 0.0
        elif Do_in is not None and Di_in is None and k_in is not None:
            Di_in = Do_in * k_in
        elif Do_in is None and Di_in is not None and k_in is not None:
            Do_in = Di_in / k_in if k_in > 0.0 else None

        # Compatibilité épaulements
        if Do_in is not None:
            if D_tg is not None and Do_in < D_tg:
                _push_inconnue(rapport, "impossibles", "diametre_fut", "Le diamètre du fût central est < au diamètre du téton gauche.")
            if D_td is not None and Do_in < D_td:
                _push_inconnue(rapport, "impossibles", "diametre_fut", "Le diamètre du fût central est < au diamètre du téton droit.")

        def compute_Do_min(k: float, sigma_allow_pa: Optional[float], tau_allow_pa: Optional[float]) -> Dict[str, Any]:
            outk: Dict[str, Any] = {"k": k, "criteres": {}, "Do_min_m": None, "Di_min_m": None, "notes": []}
            Do_candidates: List[float] = []

            if tau_allow_pa is not None:
                if V is not None:
                    DoV = _solve_Do_min_for_tauV(float(V), float(tau_allow_pa), float(k))
                    outk["criteres"]["cisaillement_transverse"] = {
                        "V_N": float(V),
                        "tau_allow_pa": float(tau_allow_pa),
                        "Do_min_m": DoV,
                    }
                    Do_candidates.append(DoV)
                else:
                    outk["criteres"]["cisaillement_transverse"] = {"note": "V manquant."}

                if T is not None:
                    DoT = _solve_Do_min_for_tauT(float(T), float(tau_allow_pa), float(k))
                    outk["criteres"]["torsion"] = {
                        "T_Nm": float(T),
                        "tau_allow_pa": float(tau_allow_pa),
                        "Do_min_m": DoT,
                    }
                    Do_candidates.append(DoT)
                else:
                    outk["criteres"]["torsion"] = {"note": "T manquant."}
            else:
                outk["criteres"]["cisaillement_transverse"] = {"note": "tau_allow inconnue."}
                outk["criteres"]["torsion"] = {"note": "tau_allow inconnue."}

            if sigma_allow_pa is not None:
                if F_ax is not None:
                    DoF = _solve_Do_min_for_sig_ax(float(F_ax), float(sigma_allow_pa), float(k))
                    outk["criteres"]["axial"] = {
                        "F_N": float(F_ax),
                        "sigma_allow_pa": float(sigma_allow_pa),
                        "Do_min_m": DoF,
                    }
                    Do_candidates.append(DoF)
                else:
                    outk["criteres"]["axial"] = {"note": "F_ax manquant."}

                if M is not None:
                    DoM = _solve_Do_min_for_sig_b(float(M), float(sigma_allow_pa), float(k))
                    outk["criteres"]["flexion"] = {
                        "M_Nm": float(M),
                        "sigma_allow_pa": float(sigma_allow_pa),
                        "Do_min_m": DoM,
                    }
                    Do_candidates.append(DoM)
                else:
                    outk["criteres"]["flexion"] = {"note": "M manquant."}
            else:
                outk["criteres"]["axial"] = {"note": "sigma_allow inconnue."}
                outk["criteres"]["flexion"] = {"note": "sigma_allow inconnue."}

            # compatibilité avec tétons / portée
            d_min_geo = 0.0
            for d_test in (D_tg, D_td, D_portee):
                if d_test is not None:
                    d_min_geo = max(d_min_geo, float(d_test))
            if d_min_geo > 0.0:
                outk["criteres"]["geometrie_minimale"] = {"Do_min_m": d_min_geo}
                Do_candidates.append(d_min_geo)

            if Do_candidates:
                Do_min = max(Do_candidates)
                outk["Do_min_m"] = Do_min
                outk["Di_min_m"] = Do_min * float(k)
            else:
                outk["notes"].append("Aucun critère dimensionnant calculable.")
            return outk

        dim_evide: Dict[str, Any] = {"mode": None, "resultat_unique": None, "scenarios": None}

        if Re is None:
            _push_inconnue(rapport, "partielles", "dimensionnement_fut", "Re requis pour dimensionner quantitativement.")
        if V is None and T is None and M is None and F_ax is None:
            _push_inconnue(rapport, "partielles", "efforts_dimensionnants", "Au moins un effort parmi F_ax, V, M, T est requis.")

        if Do_in is not None and Di_in is not None:
            # Vérification d'une géométrie imposée
            if Di_in >= Do_in:
                _push_inconnue(rapport, "impossibles", "geometrie_fut", "Di >= Do.")
            else:
                props = _compute_section_props(float(Do_in), float(Di_in))
                A = props["section_m2"]
                I = props["I_m4"]
                J = props["J_m4"]
                r_ext = props["rayon_ext_m"]

                sigma_ax = abs(float(F_ax)) / A if F_ax is not None else None
                sigma_b = abs(float(M)) * r_ext / I if M is not None else None
                tau_V = abs(float(V)) / A if V is not None else None
                tau_T = abs(float(T)) * r_ext / J if T is not None else None

                sigma_tot = 0.0
                if sigma_ax is not None:
                    sigma_tot += float(sigma_ax)
                if sigma_b is not None:
                    sigma_tot += float(sigma_b)

                tau_tot = 0.0
                if tau_V is not None:
                    tau_tot += float(tau_V)
                if tau_T is not None:
                    tau_tot += float(tau_T)

                sigma_eq = _von_mises_sigma_tau(sigma_tot, tau_tot)

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
                    "marge_sigma_vm": (sigma_allow / sigma_eq) if (sigma_allow is not None and sigma_eq > 0.0) else None,
                    "note": "cisaillement transverse modélisé par V/A (conservatif).",
                }

                dim_evide["mode"] = "verification_geometrie_imposee"
                dim_evide["resultat_unique"] = {
                    "Do_m": float(Do_in),
                    "Di_m": float(Di_in),
                    "k": (float(Di_in) / float(Do_in)) if float(Do_in) > 0.0 else None,
                }

                rapport["geometrie"]["diametre_exterieur_fut_m"] = float(Do_in)
                rapport["geometrie"]["diametre_interieur_fut_m"] = float(Di_in)
        else:
            # Dimensionnement en scénarios
            dim_evide["mode"] = "dimensionnement"

            if Re is not None:
                if k_in is not None:
                    sc_vm = compute_Do_min(float(k_in), sigma_allow, tau_allow_vm)
                    sc_tr = compute_Do_min(float(k_in), sigma_allow, tau_allow_tresca)
                    dim_evide["resultat_unique"] = {
                        "k": float(k_in),
                        "critere_vm": sc_vm,
                        "critere_tresca": sc_tr,
                        "note": "Deux résultats (VM/Tresca), sans sélection automatique.",
                    }

                    # on prend seulement pour bloc CAO un candidat non imposé comme résultat "technique"
                    if sc_vm.get("Do_min_m") is not None:
                        rapport["geometrie"]["diametre_exterieur_fut_min_vm_m"] = sc_vm["Do_min_m"]
                        rapport["geometrie"]["diametre_interieur_fut_associe_vm_m"] = sc_vm["Di_min_m"]
                    if sc_tr.get("Do_min_m") is not None:
                        rapport["geometrie"]["diametre_exterieur_fut_min_tresca_m"] = sc_tr["Do_min_m"]
                        rapport["geometrie"]["diametre_interieur_fut_associe_tresca_m"] = sc_tr["Di_min_m"]
                else:
                    scenarios_vm = []
                    scenarios_tr = []
                    for k in self.k_scenarios:
                        if 0.0 <= float(k) < 1.0:
                            scenarios_vm.append(compute_Do_min(float(k), sigma_allow, tau_allow_vm))
                            scenarios_tr.append(compute_Do_min(float(k), sigma_allow, tau_allow_tresca))
                    dim_evide["scenarios"] = {
                        "liste_k": list(self.k_scenarios),
                        "critere_vm": scenarios_vm,
                        "critere_tresca": scenarios_tr,
                        "note": "Scénarios proposés car k/Do/Di ne sont pas imposés.",
                    }

        rapport["dimensionnement_evide"] = dim_evide

        # ---------------------------------------------------------------------
        # 7) Flambage
        # ---------------------------------------------------------------------
        if self.longueur_libre_m is not None and self.K_flambage is not None and E is not None:
            L_free = _req_pos("longueur_libre_m", self.longueur_libre_m)
            K = _req_pos("K_flambage", self.K_flambage)

            I_use = None
            if Do_in is not None and Di_in is not None and Di_in < Do_in:
                I_use = _inertie_annulaire(float(Do_in), float(Di_in))
            elif d_plein is not None:
                I_use = _inertie_cercle(float(d_plein))
            elif dim_evide.get("resultat_unique"):
                res_u = dim_evide["resultat_unique"]
                if isinstance(res_u, dict):
                    sc_vm = res_u.get("critere_vm")
                    if isinstance(sc_vm, dict) and sc_vm.get("Do_min_m") is not None and sc_vm.get("Di_min_m") is not None:
                        I_use = _inertie_annulaire(float(sc_vm["Do_min_m"]), float(sc_vm["Di_min_m"]))

            if I_use is not None:
                Pcr = _euler_pcrit(float(E), float(I_use), L_free, K)
                rapport["flambage"] = {
                    "longueur_libre_m": L_free,
                    "K_flambage": K,
                    "charge_critique_euler_N": Pcr,
                    "marge_flambage": (Pcr / abs(float(F_ax))) if (F_ax is not None and float(F_ax) != 0.0) else None,
                }
            else:
                _push_inconnue(rapport, "partielles", "flambage", "I calculable si d plein ou Do/Di sont disponibles.")
        else:
            _push_inconnue(rapport, "partielles", "flambage", "Calculable si E + longueur_libre_m + K_flambage + section.")

        # ---------------------------------------------------------------------
        # 8) Taraudages
        # ---------------------------------------------------------------------
        def analyser_taraudage(
            cote: Literal["gauche", "droit"],
            filetage: Optional[str],
            profondeur_m: Optional[float],
            effort_N: Optional[float],
            diametre_teton_m: Optional[float],
        ) -> Dict[str, Any]:
            out: Dict[str, Any] = {
                "filetage": filetage,
                "profondeur_taraudage_m": profondeur_m,
                "effort_axial_N": effort_N,
                "resultats": {},
                "candidats_iso": None,
                "inconnues": [],
            }

            if effort_N is None:
                out["inconnues"].append("effort_axial_N")
                return out
            F = abs(float(effort_N))

            Re_taraudage = self.limite_elastique_matiere_taraudee_pa
            if Re_taraudage is None:
                Re_taraudage = Re

            sigma_allow_loc = (float(Re_taraudage) / FS) if (Re_taraudage is not None and _is_finite(Re_taraudage)) else None

            tau_adm = self.resistance_cisaillement_matiere_taraudee_pa
            tau_allow_loc = (float(tau_adm) / FS) if (tau_adm is not None and _is_finite(tau_adm)) else None

            L_dispo = None
            if profondeur_m is not None:
                L_dispo = _req_pos(f"profondeur_taraudage_{cote}_m", profondeur_m)

            iso = _iso_get(filetage) if filetage else None

            if iso is not None:
                d_nom = float(iso["d_nom"])
                d2 = float(iso["d2"])
                d3 = float(iso["d3"])

                if diametre_teton_m is not None and d_nom > float(diametre_teton_m) + 1e-15:
                    out["resultats"]["compatibilite_teton"] = {
                        "diametre_teton_m": float(diametre_teton_m),
                        "d_nom_m": d_nom,
                        "ok": False,
                    }
                else:
                    out["resultats"]["compatibilite_teton"] = {
                        "diametre_teton_m": diametre_teton_m,
                        "d_nom_m": d_nom,
                        "ok": True if diametre_teton_m is not None else None,
                    }

                if sigma_allow_loc is not None:
                    Acore = _aire_disque(d3)
                    sigma = F / Acore
                    out["resultats"]["traction_noyau"] = {
                        "d3_m": d3,
                        "A_noyau_m2": Acore,
                        "sigma_pa": sigma,
                        "sigma_admissible_pa": sigma_allow_loc,
                        "ok": sigma <= sigma_allow_loc,
                        "marge": (sigma_allow_loc / sigma) if sigma > 0.0 else None,
                    }

                if tau_allow_loc is not None and L_dispo is not None:
                    A_shear = math.pi * d2 * L_dispo
                    tau = F / A_shear
                    out["resultats"]["arrachement_filets"] = {
                        "d2_m": d2,
                        "L_eng_m": L_dispo,
                        "A_cisaillement_m2_modele": A_shear,
                        "tau_pa": tau,
                        "tau_admissible_effective_pa": tau_allow_loc,
                        "ok": tau <= tau_allow_loc,
                        "marge": (tau_allow_loc / tau) if tau > 0.0 else None,
                    }

                out["resultats"]["iso"] = {
                    "pas_m": float(iso["p"]),
                    "d_nom_m": d_nom,
                    "d_percage_m": float(iso["d_percage"]),
                }
                return out

            # candidats ISO si filetage non choisi
            candidats = []
            for name, v in ISO_METRIQUE_PAS_GROS.items():
                d_nom = float(v["d_nom"])
                d2 = float(v["d2"])
                d3 = float(v["d3"])

                if diametre_teton_m is not None and d_nom > float(diametre_teton_m) + 1e-15:
                    continue

                ok_tr = None
                marge_tr = None
                if sigma_allow_loc is not None:
                    sigma = F / _aire_disque(d3)
                    ok_tr = sigma <= sigma_allow_loc
                    marge_tr = (sigma_allow_loc / sigma) if sigma > 0.0 else None

                ok_ar = None
                L_min = None
                marge_ar = None
                if tau_allow_loc is not None:
                    L_min = F / (math.pi * d2 * tau_allow_loc) if (d2 > 0.0 and tau_allow_loc > 0.0) else None
                    if L_min is not None and L_dispo is not None:
                        ok_ar = L_dispo >= L_min
                        if ok_ar:
                            tau = F / (math.pi * d2 * L_dispo)
                            marge_ar = (tau_allow_loc / tau) if tau > 0.0 else None

                candidats.append({
                    "filetage": name,
                    "d_nom_m": d_nom,
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
            out["candidats_iso"] = {"liste_annotee": candidats}
            return out

        rapport["taraudages"] = {
            "gauche": analyser_taraudage(
                "gauche",
                self.filetage_gauche,
                self.profondeur_taraudage_gauche_m,
                self.effort_axial_sur_taraudage_gauche_N,
                D_tg,
            ),
            "droit": analyser_taraudage(
                "droit",
                self.filetage_droit,
                self.profondeur_taraudage_droit_m,
                self.effort_axial_sur_taraudage_droit_N,
                D_td,
            ),
        }

        # ---------------------------------------------------------------------
        # 9) Masse + inerties
        # ---------------------------------------------------------------------
        if rho is not None:
            Vtot = 0.0
            details = []

            if L_mid is not None:
                if Do_in is not None and Di_in is not None and Di_in < Do_in:
                    Amid = _aire_annulaire(float(Do_in), float(Di_in))
                    Vmid = Amid * float(L_mid)
                    Vtot += Vmid
                    details.append({
                        "troncon": "fut_central_evide",
                        "Do_m": float(Do_in),
                        "Di_m": float(Di_in),
                        "longueur_m": float(L_mid),
                        "volume_m3": Vmid,
                    })
                    rapport["inerties"]["fut_central"] = {
                        "section_m2": Amid,
                        "I_m4": _inertie_annulaire(float(Do_in), float(Di_in)),
                        "J_m4": _polaire_annulaire(float(Do_in), float(Di_in)),
                    }
                elif d_plein is not None:
                    Vmid = _aire_disque(float(d_plein)) * float(L_mid)
                    Vtot += Vmid
                    details.append({
                        "troncon": "fut_central_plein",
                        "diametre_m": float(d_plein),
                        "longueur_m": float(L_mid),
                        "volume_m3": Vmid,
                    })
                    rapport["inerties"]["fut_central"] = {
                        "section_m2": _aire_disque(float(d_plein)),
                        "I_m4": _inertie_cercle(float(d_plein)),
                        "J_m4": _polaire_cercle(float(d_plein)),
                    }

            if L_g is not None and D_tg is not None:
                Vg = _aire_disque(float(D_tg)) * float(L_g)
                Vtot += Vg
                details.append({
                    "troncon": "teton_gauche",
                    "diametre_m": float(D_tg),
                    "longueur_m": float(L_g),
                    "volume_m3": Vg,
                })

            if L_d is not None and D_td is not None:
                Vd = _aire_disque(float(D_td)) * float(L_d)
                Vtot += Vd
                details.append({
                    "troncon": "teton_droit",
                    "diametre_m": float(D_td),
                    "longueur_m": float(L_d),
                    "volume_m3": Vd,
                })

            m_tot = float(rho) * Vtot
            rapport["masse"] = {
                "volume_total_m3": Vtot,
                "masse_kg": m_tot,
                "detail": details,
            }
        else:
            _push_inconnue(rapport, "partielles", "masse", "Calculable si densité et géométrie sont connues.")

        # ---------------------------------------------------------------------
        # 10) Cinématique
        # ---------------------------------------------------------------------
        if self.rpm is not None:
            rpm = _req_pos("rpm", self.rpm, strictly=False)
            rapport["cinematique"] = {
                "rpm": rpm,
                "omega_rad_s": _omega_from_rpm(rpm),
            }
        else:
            rapport["cinematique"] = {"rpm": None, "omega_rad_s": None}

        # ---------------------------------------------------------------------
        # 11) CAO exploitable pour SolidWorks
        # ---------------------------------------------------------------------
        Do_cao = None
        Di_cao = None

        if Do_in is not None and Di_in is not None and Di_in < Do_in:
            Do_cao = float(Do_in)
            Di_cao = float(Di_in)
        elif d_plein is not None:
            Do_cao = float(d_plein)
            Di_cao = 0.0
        else:
            res_u = rapport["dimensionnement_evide"].get("resultat_unique")
            if isinstance(res_u, dict):
                crit_vm = res_u.get("critere_vm")
                if isinstance(crit_vm, dict) and crit_vm.get("Do_min_m") is not None and crit_vm.get("Di_min_m") is not None:
                    Do_cao = float(crit_vm["Do_min_m"])
                    Di_cao = float(crit_vm["Di_min_m"])

        # Détails CAO seulement si suffisamment défini
        if L_mid is not None and L_g is not None and L_d is not None:
            x0 = 0.0
            x1 = float(L_g)
            x2 = float(L_g) + float(L_mid)
            x3 = float(L_g) + float(L_mid) + float(L_d)

            rayon_conge_g = self.rayon_conge_gauche_m
            if rayon_conge_g is None and (Do_cao is not None):
                rayon_conge_g = _borne(
                    self.regles_fabrication.ratio_conge_sur_diametre * float(Do_cao),
                    self.regles_fabrication.conge_min_m,
                    self.regles_fabrication.conge_max_m,
                )

            rayon_conge_d = self.rayon_conge_droit_m
            if rayon_conge_d is None and (Do_cao is not None):
                rayon_conge_d = _borne(
                    self.regles_fabrication.ratio_conge_sur_diametre * float(Do_cao),
                    self.regles_fabrication.conge_min_m,
                    self.regles_fabrication.conge_max_m,
                )

            ch_g = self.chanfrein_gauche_m
            if ch_g is None:
                ch_g = self.regles_fabrication.chanfrein_min_m

            ch_d = self.chanfrein_droit_m
            if ch_d is None:
                ch_d = self.regles_fabrication.chanfrein_min_m

            rapport["cao"] = {
                "type_piece": "arbre_piston",
                "longueur_totale_m": x3,
                "axe_x": {
                    "x_debut_gauche_m": x0,
                    "x_fin_teton_gauche_m": x1,
                    "x_fin_fut_central_m": x2,
                    "x_fin_teton_droit_m": x3,
                },
                "fut_central": {
                    "longueur_m": L_mid,
                    "diametre_exterieur_m": Do_cao,
                    "diametre_interieur_m": Di_cao,
                    "evidement": (Di_cao is not None and Di_cao > 0.0),
                    "rugosite_ra_um": self.regles_fabrication.rugosite_fut_ra_um,
                    "tolerance_diametre_m": self.regles_fabrication.tolerance_diametre_fut_m,
                },
                "teton_gauche": {
                    "longueur_m": L_g,
                    "diametre_m": D_tg,
                    "filetage": self.filetage_gauche,
                    "profondeur_taraudage_m": self.profondeur_taraudage_gauche_m,
                    "chanfrein_extremite_m": ch_g,
                    "rugosite_ra_um": self.regles_fabrication.rugosite_tetons_ra_um,
                    "tolerance_diametre_m": self.regles_fabrication.tolerance_diametre_tetons_m,
                },
                "teton_droit": {
                    "longueur_m": L_d,
                    "diametre_m": D_td,
                    "filetage": self.filetage_droit,
                    "profondeur_taraudage_m": self.profondeur_taraudage_droit_m,
                    "chanfrein_extremite_m": ch_d,
                    "rugosite_ra_um": self.regles_fabrication.rugosite_tetons_ra_um,
                    "tolerance_diametre_m": self.regles_fabrication.tolerance_diametre_tetons_m,
                },
                "epaulement_gauche": {
                    "x_m": x1,
                    "rayon_conge_m": rayon_conge_g,
                },
                "epaulement_droit": {
                    "x_m": x2,
                    "rayon_conge_m": rayon_conge_d,
                },
                "tolerance_longueur_m": self.regles_fabrication.tolerance_longueur_m,
            }
        else:
            _push_inconnue(rapport, "partielles", "bloc_cao", "Bloc CAO complet calculable si les longueurs sont définies.")

        # ---------------------------------------------------------------------
        # 12) Entrées tracées
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
            "diametre_teton_gauche_m": self.diametre_teton_gauche_m,
            "diametre_teton_droit_m": self.diametre_teton_droit_m,
            "rayon_conge_gauche_m": self.rayon_conge_gauche_m,
            "rayon_conge_droit_m": self.rayon_conge_droit_m,
            "chanfrein_gauche_m": self.chanfrein_gauche_m,
            "chanfrein_droit_m": self.chanfrein_droit_m,
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
            "diametre_portee_coussinet_m": self.diametre_portee_coussinet_m,
            "longueur_coussinet_m": self.longueur_coussinet_m,
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
# Exemple
# =============================================================================
if __name__ == "__main__":
    from pprint import pprint

    a = ArbrePiston(
        densite_kg_m3=7800.0,
        limite_elastique_pa=600e6,
        module_young_pa=210e9,
        facteur_securite=2.0,

        longueur_fut_central_m=0.040,
        profondeur_taraudage_gauche_m=0.012,
        profondeur_taraudage_droit_m=0.012,

        force_axiale_N=15000.0,
        force_cisaillement_N=2000.0,
        bras_levier_charge_m=0.010,

        longueur_libre_m=0.060,
        K_flambage=1.0,

        effort_axial_sur_taraudage_gauche_N=8000.0,
        effort_axial_sur_taraudage_droit_N=8000.0,
        resistance_cisaillement_matiere_taraudee_pa=250e6,

        filetage_gauche="M8",
        filetage_droit="M8",
        ratio_evidement_k=0.5,
    )

    pprint(a.analyser(strict=False))
