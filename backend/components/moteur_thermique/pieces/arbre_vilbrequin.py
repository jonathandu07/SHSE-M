# backend/components/moteur_thermique/pieces/arbre_vilbrequin.py
# =============================================================================
# ARBRE DE VILEBREQUIN — SHSE-M
# Version complétée : inter-pièces + contraintes mécaniques + bloc CAO/SolidWorks
# =============================================================================
# Objectif "rien inventer" :
# - ne pas choisir une géométrie unique si les données manquent,
# - calculer tout ce qui est calculable depuis :
#   * cylindre / piston / bielle / moteur_thermique / roulement_aiguille,
#   * matériau,
#   * couple, flexion, charge bielle, course,
#   * largeurs / diamètres imposés,
# - produire un bloc "cao" exploitable pour le dessin manuel / SolidWorks.
#
# Hypothèses explicites :
# - arbre plein circulaire pour les dimensionnements élémentaires de journaux/maneton,
# - torsion pure : τmax = 16T/(π d^3),
# - flexion pure : σmax = 32M/(π d^3),
# - combinaison de contraintes : von Mises sqrt(σ² + 3τ²),
# - charge moyenne projetée sur portée : p = F / (d * L),
# - aucune fatigue détaillée sans spectre de charge ni facteurs de concentration.
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


def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


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

    rapport.setdefault("inconnues", {}).setdefault("impossibles", [])
    rapport.setdefault("inconnues", {}).setdefault("partielles", [])
    rapport["inconnues"]["impossibles"] = dedup(
        list(rapport["inconnues"].get("impossibles", []) or [])
    )
    rapport["inconnues"]["partielles"] = dedup(
        list(rapport["inconnues"].get("partielles", []) or [])
    )


def _safe_get_dict(obj: Any, key: str) -> Dict[str, Any]:
    if isinstance(obj, dict):
        v = obj.get(key, {})
        return v if isinstance(v, dict) else {}
    return {}


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for m in ("analyser", "calculer"):
        try:
            if hasattr(obj, m) and callable(getattr(obj, m)):
                try:
                    r = getattr(obj, m)(strict=False)
                except TypeError:
                    r = getattr(obj, m)()
                if isinstance(r, dict):
                    return r
        except Exception:
            continue
    return None


# =============================================================================
# Matériaux
# =============================================================================

def _resoudre_materiau(
    materiau_cle: Optional[str],
    densite_kg_m3: Optional[float],
    limite_elastique_pa: Optional[float],
    module_young_pa: Optional[float],
    poisson: Optional[float] = None,
    resistance_traction_pa: Optional[float] = None,
    limite_fatigue_pa: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    rho = float(densite_kg_m3) if _is_finite(densite_kg_m3) else None
    Re = float(limite_elastique_pa) if _is_finite(limite_elastique_pa) else None
    E = float(module_young_pa) if _is_finite(module_young_pa) else None
    nu = float(poisson) if _is_finite(poisson) else None
    Rm = float(resistance_traction_pa) if _is_finite(resistance_traction_pa) else None
    Sf = float(limite_fatigue_pa) if _is_finite(limite_fatigue_pa) else None

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
                valeur = getattr(mod, "valeur", None)

                def g(obj: Any, *names: str, mode: str = "typique") -> Optional[float]:
                    for n in names:
                        if isinstance(obj, dict) and n in obj:
                            v = obj.get(n)
                        else:
                            v = getattr(obj, n, None)
                        if v is not None and _is_finite(v):
                            return float(v)
                        if callable(valeur):
                            try:
                                out = valeur(v, mode=mode)
                                if _is_finite(out):
                                    return float(out)
                            except Exception:
                                pass
                    return None

                rho = rho if rho is not None else g(mat, "densite_kg_m3", "rho_kg_m3", "densite")
                Re = Re if Re is not None else g(
                    mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa", mode="min"
                )
                if Re is None and hasattr(mat, "limite_elastique_effective_pa"):
                    try:
                        v = mat.limite_elastique_effective_pa(mode="min")
                        if _is_finite(v):
                            Re = float(v)
                    except Exception:
                        pass
                if Re is None:
                    try:
                        segs = list(getattr(mat, "resistance_par_section", ()) or ())
                        vals = [
                            float(seg.rp02_pa_min)
                            for seg in segs
                            if _is_finite(getattr(seg, "rp02_pa_min", None))
                        ]
                        if vals:
                            Re = min(vals)
                    except Exception:
                        pass
                E = E if E is not None else g(
                    mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa"
                )
                nu = nu if nu is not None else g(mat, "poisson", "nu")
                Rm = Rm if Rm is not None else g(
                    mat, "resistance_traction_pa", "Rm_pa", "uts_pa", "ultimate_strength_pa", mode="min"
                )
                if Rm is None and hasattr(mat, "resistance_traction_effective_pa"):
                    try:
                        v = mat.resistance_traction_effective_pa(mode="min")
                        if _is_finite(v):
                            Rm = float(v)
                    except Exception:
                        pass
                if Rm is None:
                    try:
                        segs = list(getattr(mat, "resistance_par_section", ()) or ())
                        vals = []
                        for seg in segs:
                            rm = getattr(seg, "rm_pa", None)
                            out = valeur(rm, mode="min") if callable(valeur) else rm
                            if _is_finite(out):
                                vals.append(float(out))
                        if vals:
                            Rm = min(vals)
                    except Exception:
                        pass
                Sf = Sf if Sf is not None else g(
                    mat, "limite_fatigue_pa", "Sf_pa", "endurance_limit_pa", mode="min"
                )
                if Sf is None and hasattr(mat, "limite_fatigue_effective_pa"):
                    try:
                        v = mat.limite_fatigue_effective_pa(mode="min")
                        if _is_finite(v):
                            Sf = float(v)
                    except Exception:
                        pass
                break
            except Exception:
                continue

    return {
        "densite_kg_m3": rho,
        "limite_elastique_pa": Re,
        "module_young_pa": E,
        "poisson": nu,
        "resistance_traction_pa": Rm,
        "limite_fatigue_pa": Sf,
    }


# =============================================================================
# RDM arbres
# =============================================================================

def _section_disque(d: float) -> float:
    d_v = _req_pos("d", d)
    return math.pi * (0.5 * d_v) ** 2


def _inertie_cercle(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**4) / 64.0


def _polar_J(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**4) / 32.0


def _module_flexion(d: float) -> float:
    d_v = _req_pos("d", d)
    return (math.pi * d_v**3) / 32.0


def _tau_torsion_max(T: float, d: float) -> float:
    return (16.0 * abs(float(T))) / (math.pi * _req_pos("d", d) ** 3)


def _sigma_flexion_max(M: float, d: float) -> float:
    return (32.0 * abs(float(M))) / (math.pi * _req_pos("d", d) ** 3)


def _sigma_axiale(F: float, d: float) -> float:
    return abs(float(F)) / _section_disque(d)


def _von_mises_sigma_tau(sigma: float, tau: float) -> float:
    return math.sqrt(float(sigma) ** 2 + 3.0 * float(tau) ** 2)


def _dmin_torsion_vonmises(T: float, Re: float, FS: float) -> float:
    tau_adm = float(Re) / (float(FS) * math.sqrt(3.0))
    if tau_adm <= 0.0:
        raise ValueError("tau_adm <= 0")
    return (16.0 * abs(float(T)) / (math.pi * tau_adm)) ** (1.0 / 3.0)


def _dmin_bending_vonmises(M: float, Re: float, FS: float) -> float:
    sigma_adm = float(Re) / float(FS)
    if sigma_adm <= 0.0:
        raise ValueError("sigma_adm <= 0")
    return (32.0 * abs(float(M)) / (math.pi * sigma_adm)) ** (1.0 / 3.0)


def _dmin_axial(F: float, Re: float, FS: float) -> float:
    sigma_adm = float(Re) / float(FS)
    if sigma_adm <= 0.0:
        raise ValueError("sigma_adm <= 0")
    return math.sqrt((4.0 * abs(float(F))) / (math.pi * sigma_adm))


def _reactions_simple(F: float, L: float, a: float) -> Dict[str, float]:
    Rg = float(F) * (float(L) - float(a)) / float(L)
    Rd = float(F) * float(a) / float(L)
    return {
        "reaction_gauche_N": Rg,
        "reaction_droite_N": Rd,
        "moment_max_Nm": Rg * float(a),
    }


def _goodman(sigma_a: float, sigma_m: float, Se: float, Rm: float) -> float:
    return float(sigma_a) / float(Se) + max(float(sigma_m), 0.0) / float(Rm)


def _soderberg(sigma_a: float, sigma_m: float, Se: float, Re: float) -> float:
    return float(sigma_a) / float(Se) + max(float(sigma_m), 0.0) / float(Re)


def _frequence_propre_torsion_2_masses(k: float, J1: float, J2: float) -> Dict[str, float]:
    omega = math.sqrt(float(k) * (1.0 / float(J1) + 1.0 / float(J2)))
    return {"omega_rad_s": omega, "frequence_hz": omega / (2.0 * math.pi)}


# =============================================================================
# Résolution depuis autres pièces
# =============================================================================

def _resoudre_depuis_cylindre(cylindre: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "alesage_m": None,
        "course_m": None,
        "pression_max_pa": None,
    }
    if cylindre is None:
        return out

    rep = _try_call_report(cylindre)
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


def _resoudre_depuis_piston(piston: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "force_axiale_nette_n": None,
        "force_gaz_n": None,
        "course_m": None,
    }
    if piston is None:
        return out

    rep = _try_call_report(piston)
    if not isinstance(rep, dict):
        return out

    out["rapport"] = rep
    cin = _safe_get_dict(rep, "cinematique")
    ent = _safe_get_dict(rep, "entrees")

    if _is_finite(cin.get("force_axiale_nette_n")):
        out["force_axiale_nette_n"] = float(cin["force_axiale_nette_n"])
    if _is_finite(cin.get("force_gaz_n")):
        out["force_gaz_n"] = float(cin["force_gaz_n"])
    if _is_finite(ent.get("course_m")):
        out["course_m"] = float(ent["course_m"])

    return out


def _resoudre_depuis_bielle(bielle: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "diametre_maneton_m": None,
        "longueur_portee_grande_tete_m": None,
        "force_axiale_max_N": None,
        "longueur_bielle_m": None,
    }
    if bielle is None:
        return out

    rep = _try_call_report(bielle)
    if not isinstance(rep, dict):
        for attr in ("diametre_maneton_m", "longueur_portee_grande_tete_m", "force_axiale_max_N", "longueur_bielle_m"):
            v = getattr(bielle, attr, None)
            if _is_finite(v):
                out[attr] = float(v)
        return out

    out["rapport"] = rep
    geo = _safe_get_dict(rep, "geometrie")
    gt = _safe_get_dict(geo, "grande_tete")
    eff = _safe_get_dict(rep, "efforts")
    ent = _safe_get_dict(rep, "entrees")

    if _is_finite(gt.get("diametre_maneton_m")):
        out["diametre_maneton_m"] = float(gt["diametre_maneton_m"])
    if _is_finite(gt.get("longueur_portee_m")):
        out["longueur_portee_grande_tete_m"] = float(gt["longueur_portee_m"])
    if _is_finite(eff.get("force_axiale_max_N")):
        out["force_axiale_max_N"] = float(eff["force_axiale_max_N"])
    if _is_finite(ent.get("longueur_bielle_m")):
        out["longueur_bielle_m"] = float(ent["longueur_bielle_m"])

    return out


def _resoudre_depuis_moteur(moteur: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "couple_max_Nm": None,
        "force_bielle_N": None,
        "rpm": None,
        "diametre_maneton_m": None,
        "course_m": None,
    }
    if moteur is None:
        return out

    rep = _try_call_report(moteur)
    if not isinstance(rep, dict):
        return out

    out["rapport"] = rep

    couple_blocs = [
        _safe_get_dict(rep, "couple"),
        _safe_get_dict(rep, "resultats"),
        _safe_get_dict(rep, "dimensionnement"),
        rep if isinstance(rep, dict) else {},
    ]
    for bloc in couple_blocs:
        for k in ("couple_max_Nm", "couple_Nm", "T_instantane_Nm", "T_Nm"):
            if out["couple_max_Nm"] is None and _is_finite(bloc.get(k)):
                out["couple_max_Nm"] = float(bloc[k])

        for k in ("force_bielle_effective_N", "force_bielle_N", "F_bielle_N", "force_bielle_n"):
            if out["force_bielle_N"] is None and _is_finite(bloc.get(k)):
                out["force_bielle_N"] = float(bloc[k])

        for k in ("rpm",):
            if out["rpm"] is None and _is_finite(bloc.get(k)):
                out["rpm"] = float(bloc[k])

        for k in ("diametre_maneton_m",):
            if out["diametre_maneton_m"] is None and _is_finite(bloc.get(k)):
                out["diametre_maneton_m"] = float(bloc[k])

        for k in ("course_m",):
            if out["course_m"] is None and _is_finite(bloc.get(k)):
                out["course_m"] = float(bloc[k])

    return out


def _resoudre_depuis_roulement(roulement: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "d_interieur_reference_m": None,
        "D_exterieur_reference_m": None,
        "B_largeur_reference_m": None,
        "d_interieur_requis_maneton_m": None,
    }
    if roulement is None:
        return out

    rep = _try_call_report(roulement)
    if isinstance(rep, dict):
        out["rapport"] = rep
        dim_req = _safe_get_dict(rep, "dimensions_requises")
        dim_ref = _safe_get_dict(rep, "dimensions_reference")
        bloc_r = _safe_get_dict(rep, "roulement")

        if _is_finite(dim_req.get("d_interieur_requis_m")):
            out["d_interieur_requis_maneton_m"] = float(dim_req["d_interieur_requis_m"])

        for k in ("d_interieur_m", "d_alesage_m"):
            if out["d_interieur_reference_m"] is None and _is_finite(dim_ref.get(k)):
                out["d_interieur_reference_m"] = float(dim_ref[k])

        if _is_finite(dim_ref.get("D_exterieur_m")):
            out["D_exterieur_reference_m"] = float(dim_ref["D_exterieur_m"])
        if _is_finite(dim_ref.get("B_largeur_m")):
            out["B_largeur_reference_m"] = float(dim_ref["B_largeur_m"])

        if out["d_interieur_reference_m"] is None and _is_finite(bloc_r.get("d_alesage_m")):
            out["d_interieur_reference_m"] = float(bloc_r["d_alesage_m"])
        if out["D_exterieur_reference_m"] is None and _is_finite(bloc_r.get("D_exterieur_m")):
            out["D_exterieur_reference_m"] = float(bloc_r["D_exterieur_m"])
        if out["B_largeur_reference_m"] is None and _is_finite(bloc_r.get("largeur_m")):
            out["B_largeur_reference_m"] = float(bloc_r["largeur_m"])

    if out["d_interieur_reference_m"] is None:
        for attr in ("d_interieur_m", "d_alesage_m", "diametre_interieur_m", "d_m"):
            v = getattr(roulement, attr, None)
            if _is_finite(v):
                out["d_interieur_reference_m"] = float(v)
                break

    if out["D_exterieur_reference_m"] is None:
        for attr in ("D_exterieur_m", "diametre_exterieur_m", "D_m"):
            v = getattr(roulement, attr, None)
            if _is_finite(v):
                out["D_exterieur_reference_m"] = float(v)
                break

    if out["B_largeur_reference_m"] is None:
        for attr in ("B_largeur_m", "largeur_m", "B_m", "epaisseur_m"):
            v = getattr(roulement, attr, None)
            if _is_finite(v):
                out["B_largeur_reference_m"] = float(v)
                break

    return out


# =============================================================================
# Règles explicites CAO / fabrication
# =============================================================================

@dataclass(frozen=True)
class ReglesFabricationArbreVilebrequin:
    marge_largeur_portee_sur_roulement_m: float = 0.001
    marge_diametre_epaulement_sur_portee_m: float = 0.001

    conge_min_m: float = 0.0008
    conge_max_m: float = 0.0040
    ratio_conge_sur_diametre: float = 0.06

    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.0020
    ratio_chanfrein_sur_diametre: float = 0.03

    rugosite_portees_ra_um: float = 0.4
    rugosite_hors_portees_ra_um: float = 1.6
    tolerance_diametre_portee_m: float = 0.00003
    tolerance_largeur_portee_m: float = 0.00005


# =============================================================================
# Pièce : ArbreVilbrequin
# =============================================================================

@dataclass
class ArbreVilbrequin:
    """
    Arbre de vilebrequin (journaux principaux + maneton).
    """

    cylindre: Optional[Any] = None
    piston: Optional[Any] = None
    bielle: Optional[Any] = None
    moteur_thermique: Optional[Any] = None
    roulement_aiguille: Optional[Any] = None

    course_m: Optional[float] = None
    couple_max_Nm: Optional[float] = None
    moment_flexion_max_Nm: Optional[float] = None
    force_axiale_N: Optional[float] = None
    force_bielle_effective_N: Optional[float] = None
    rpm: Optional[float] = None

    diametre_journal_principal_m: Optional[float] = None
    diametre_maneton_m: Optional[float] = None
    largeur_portee_journal_m: Optional[float] = None
    largeur_portee_maneton_m: Optional[float] = None

    entre_axe_paliers_m: Optional[float] = None
    largeur_totale_arbre_m: Optional[float] = None

    nb_journaux_principaux: Literal[1, 2] = 2

    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None
    poisson: Optional[float] = None
    resistance_traction_pa: Optional[float] = None
    limite_fatigue_pa: Optional[float] = None
    facteur_securite: float = 2.0

    serrage_roulement_m: Optional[float] = None
    jeu_roulement_m: Optional[float] = None

    regles_fabrication: ReglesFabricationArbreVilebrequin = field(
        default_factory=ReglesFabricationArbreVilebrequin
    )

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "arbre_vilebrequin",
            "entrees": {},
            "sources": {},
            "materiau": {},
            "recuperations": {},
            "cinematique": {},
            "roulement": {},
            "bielle_maneton": {},
            "dimensionnements": {},
            "contraintes": {},
            "pressions_contact": {},
            "geometrie": {},
            "masse": {},
            "inerties": {},
            "cao": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        FS = _req_pos("facteur_securite", self.facteur_securite)

        props = _resoudre_materiau(
            self.materiau_cle,
            self.densite_kg_m3,
            self.limite_elastique_pa,
            self.module_young_pa,
            self.poisson,
            self.resistance_traction_pa,
            self.limite_fatigue_pa,
        )
        rho = props["densite_kg_m3"]
        Re = props["limite_elastique_pa"]
        E = props["module_young_pa"]
        nu = props["poisson"]
        Rm = props["resistance_traction_pa"]
        Sf = props["limite_fatigue_pa"]
        sigma_adm = (float(Re) / FS) if Re is not None else None

        rapport["materiau"] = {
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": rho,
            "limite_elastique_pa": Re,
            "module_young_pa": E,
            "poisson": nu,
            "resistance_traction_pa": Rm,
            "limite_fatigue_pa": Sf,
            "facteur_securite": FS,
            "sigma_admissible_pa": sigma_adm,
        }

        if Re is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "limite_elastique_pa",
                "Nécessaire pour dimensionner quantitativement les diamètres mini.",
            )

        cyl = _resoudre_depuis_cylindre(self.cylindre)
        pist = _resoudre_depuis_piston(self.piston)
        bie = _resoudre_depuis_bielle(self.bielle)
        mot = _resoudre_depuis_moteur(self.moteur_thermique)
        rou = _resoudre_depuis_roulement(self.roulement_aiguille)

        course = self.course_m
        if course is None and cyl["course_m"] is not None:
            course = float(cyl["course_m"])
            rapport["sources"]["course_m"] = "cylindre"
        elif course is None and pist["course_m"] is not None:
            course = float(pist["course_m"])
            rapport["sources"]["course_m"] = "piston"
        elif course is None and mot["course_m"] is not None:
            course = float(mot["course_m"])
            rapport["sources"]["course_m"] = "moteur_thermique"

        if course is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "course_m",
                "Nécessaire pour déterminer le rayon de manivelle r = course/2.",
            )
            r_manivelle = None
        else:
            course = _req_pos("course_m", course)
            r_manivelle = 0.5 * course

        rpm = self.rpm
        if rpm is None and mot["rpm"] is not None:
            rpm = float(mot["rpm"])
            rapport["sources"]["rpm"] = "moteur_thermique"

        T = self.couple_max_Nm
        if T is None and mot["couple_max_Nm"] is not None:
            T = float(mot["couple_max_Nm"])
            rapport["sources"]["couple_max_Nm"] = "moteur_thermique"

        F_bielle = self.force_bielle_effective_N
        if F_bielle is None and mot["force_bielle_N"] is not None:
            F_bielle = float(mot["force_bielle_N"])
            rapport["sources"]["force_bielle_effective_N"] = "moteur_thermique"
        elif F_bielle is None and bie["force_axiale_max_N"] is not None:
            F_bielle = float(bie["force_axiale_max_N"])
            rapport["sources"]["force_bielle_effective_N"] = "bielle"
        elif F_bielle is None and pist["force_axiale_nette_n"] is not None:
            F_bielle = float(pist["force_axiale_nette_n"])
            rapport["sources"]["force_bielle_effective_N"] = "piston.force_axiale_nette_n"
        elif F_bielle is None and pist["force_gaz_n"] is not None:
            F_bielle = float(pist["force_gaz_n"])
            rapport["sources"]["force_bielle_effective_N"] = "piston.force_gaz_n"

        if T is None and F_bielle is not None and r_manivelle is not None:
            T = abs(float(F_bielle)) * float(r_manivelle)
            rapport["notes_modele"].append(
                "couple_max_Nm déduit approximativement par T = |F_bielle| * r_manivelle."
            )

        Mmax = self.moment_flexion_max_Nm
        F_ax = self.force_axiale_N

        rapport["recuperations"] = {
            "couple_max_Nm": T,
            "force_bielle_effective_N": F_bielle,
            "force_axiale_N": F_ax,
            "moment_flexion_max_Nm": Mmax,
            "rpm": rpm,
        }

        if T is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "couple_max_Nm",
                "Nécessaire pour dimensionner en torsion.",
            )

        if Mmax is None:
            _push_inconnue(
                rapport,
                "partielles",
                "moment_flexion_max_Nm",
                "Non calculable ici sans modèle d'appuis/positions des charges.",
            )
        else:
            Mmax = _req_pos("moment_flexion_max_Nm", Mmax, strictly=False)

        if F_ax is not None:
            F_ax = _req_pos("force_axiale_N", F_ax, strictly=False)

        d_ref = rou["d_interieur_reference_m"]
        D_ref = rou["D_exterieur_reference_m"]
        B_ref = rou["B_largeur_reference_m"]
        d_requis_maneton = rou["d_interieur_requis_maneton_m"]

        d_journal = self.diametre_journal_principal_m
        if d_journal is not None:
            d_journal = _req_pos("diametre_journal_principal_m", d_journal)

        largeur_journal = self.largeur_portee_journal_m
        if largeur_journal is not None:
            largeur_journal = _req_pos("largeur_portee_journal_m", largeur_journal)

        if d_journal is None and d_ref is not None:
            d_journal = float(d_ref)
            rapport["notes_modele"].append(
                "diametre_journal_principal_m repris depuis le diamètre intérieur de référence du roulement."
            )

        if largeur_journal is None and B_ref is not None:
            largeur_journal = float(B_ref) + self.regles_fabrication.marge_largeur_portee_sur_roulement_m
            rapport["notes_modele"].append(
                "largeur_portee_journal_m déduite depuis la largeur de référence du roulement + marge explicite."
            )

        d_maneton = self.diametre_maneton_m
        if d_maneton is None and bie["diametre_maneton_m"] is not None:
            d_maneton = float(bie["diametre_maneton_m"])
            rapport["sources"]["diametre_maneton_m"] = "bielle"
        elif d_maneton is None and mot["diametre_maneton_m"] is not None:
            d_maneton = float(mot["diametre_maneton_m"])
            rapport["sources"]["diametre_maneton_m"] = "moteur_thermique"
        elif d_maneton is None and d_requis_maneton is not None:
            d_maneton = float(d_requis_maneton)
            rapport["sources"]["diametre_maneton_m"] = "roulement_aiguille.dimensions_requises"

        if d_maneton is not None:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "diametre_maneton_m",
                "Requis pour la géométrie et les contraintes du maneton.",
            )

        largeur_maneton = self.largeur_portee_maneton_m
        if largeur_maneton is None and bie["longueur_portee_grande_tete_m"] is not None:
            largeur_maneton = float(bie["longueur_portee_grande_tete_m"])
            rapport["sources"]["largeur_portee_maneton_m"] = "bielle"
        elif largeur_maneton is None and B_ref is not None:
            largeur_maneton = float(B_ref) + self.regles_fabrication.marge_largeur_portee_sur_roulement_m
            rapport["notes_modele"].append(
                "largeur_portee_maneton_m déduite depuis largeur de référence du roulement + marge explicite."
            )

        if largeur_maneton is not None:
            largeur_maneton = _req_pos("largeur_portee_maneton_m", largeur_maneton)

        rapport["roulement"] = {
            "d_interieur_reference_m": d_ref,
            "D_exterieur_reference_m": D_ref,
            "B_largeur_reference_m": B_ref,
            "d_interieur_requis_maneton_m": d_requis_maneton,
            "diametre_journal_principal_m": d_journal,
            "largeur_portee_journal_m": largeur_journal,
        }

        rapport["bielle_maneton"] = {
            "diametre_maneton_m": d_maneton,
            "largeur_portee_maneton_m": largeur_maneton,
            "force_axiale_max_bielle_N": bie["force_axiale_max_N"],
        }

        dmin_tors = None
        dmin_bend = None
        dmin_ax = None

        if T is not None and Re is not None:
            dmin_tors = _dmin_torsion_vonmises(float(T), float(Re), FS)
            rapport["dimensionnements"]["diametre_min_torsion_m"] = dmin_tors
            rapport["dimensionnements"]["critere_torsion"] = "von Mises torsion pure"

        if Mmax is not None and Re is not None:
            dmin_bend = _dmin_bending_vonmises(float(Mmax), float(Re), FS)
            rapport["dimensionnements"]["diametre_min_flexion_m"] = dmin_bend
            rapport["dimensionnements"]["critere_flexion"] = "flexion pure sigma <= Re/FS"

        if F_ax is not None and Re is not None:
            dmin_ax = _dmin_axial(float(F_ax), float(Re), FS)
            rapport["dimensionnements"]["diametre_min_axial_m"] = dmin_ax
            rapport["dimensionnements"]["critere_axial"] = "traction/compression sigma <= Re/FS"

        dmin_geo_maneton = None
        if d_requis_maneton is not None:
            dmin_geo_maneton = float(d_requis_maneton)

        if d_maneton is None and any(v is not None for v in (dmin_tors, dmin_bend, dmin_ax, dmin_geo_maneton)):
            candidats = [v for v in (dmin_tors, dmin_bend, dmin_ax, dmin_geo_maneton) if v is not None]
            if candidats:
                rapport["dimensionnements"]["diametre_maneton_min_calcule_m"] = max(candidats)

        if d_journal is None and any(v is not None for v in (dmin_tors, dmin_bend, dmin_ax, d_ref)):
            candidats = [v for v in (dmin_tors, dmin_bend, dmin_ax, d_ref) if v is not None]
            if candidats:
                rapport["dimensionnements"]["diametre_journal_min_calcule_m"] = max(candidats)

        def calc_contraintes_section(d_use: Optional[float], nom: str) -> Optional[Dict[str, Any]]:
            if d_use is None:
                return None

            sigma_t = _sigma_axiale(float(F_ax), float(d_use)) if F_ax is not None else 0.0
            sigma_b = _sigma_flexion_max(float(Mmax), float(d_use)) if Mmax is not None else 0.0
            tau_t = _tau_torsion_max(float(T), float(d_use)) if T is not None else 0.0
            sigma_comb = sigma_t + sigma_b
            sigma_eq = _von_mises_sigma_tau(sigma_comb, tau_t)

            return {
                "diametre_m": d_use,
                "section_m2": _section_disque(d_use),
                "I_m4": _inertie_cercle(d_use),
                "J_m4": _polar_J(d_use),
                "sigma_axiale_pa": sigma_t if F_ax is not None else None,
                "sigma_flexion_pa": sigma_b if Mmax is not None else None,
                "tau_torsion_pa": tau_t if T is not None else None,
                "sigma_von_mises_pa": sigma_eq,
                "sigma_admissible_pa": sigma_adm,
                "ok_von_mises": (sigma_eq <= sigma_adm) if sigma_adm is not None else None,
                "marge_von_mises": (sigma_adm / sigma_eq) if (sigma_adm is not None and sigma_eq > 0.0) else None,
                "note": f"Contraintes calculées sur {nom} supposé circulaire plein.",
            }

        c_j = calc_contraintes_section(d_journal, "journal principal")
        if c_j is not None:
            rapport["contraintes"]["journal_principal"] = c_j

        c_m = calc_contraintes_section(d_maneton, "maneton")
        if c_m is not None:
            rapport["contraintes"]["maneton"] = c_m

        if F_bielle is not None and d_maneton is not None and largeur_maneton is not None:
            p = abs(float(F_bielle)) / (float(d_maneton) * float(largeur_maneton))
            rapport["pressions_contact"]["maneton"] = {
                "force_N": abs(float(F_bielle)),
                "diametre_m": d_maneton,
                "largeur_portee_m": largeur_maneton,
                "pression_moyenne_pa": p,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pression_contact_maneton",
                "Calculable si force_bielle_effective_N, diametre_maneton_m et largeur_portee_maneton_m sont connus.",
            )

        if d_journal is not None and largeur_journal is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "pression_contact_journal",
                "Nécessite la réaction au palier principal, non calculée ici sans statique détaillée.",
            )

        if d_ref is not None and d_journal is not None:
            if self.serrage_roulement_m is not None and self.jeu_roulement_m is not None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "ajustement_roulement",
                    "Donner soit un serrage, soit un jeu, pas les deux.",
                )
            elif self.serrage_roulement_m is not None:
                s = _req_finite("serrage_roulement_m", self.serrage_roulement_m)
                rapport["geometrie"]["diametre_usinage_journal_m"] = float(d_ref) + abs(s)
                rapport["notes_modele"].append(
                    "Diamètre usiné journal calculé depuis un serrage cible simplifié."
                )
            elif self.jeu_roulement_m is not None:
                j = _req_finite("jeu_roulement_m", self.jeu_roulement_m)
                rapport["geometrie"]["diametre_usinage_journal_m"] = float(d_ref) - abs(j)
                rapport["notes_modele"].append(
                    "Diamètre usiné journal calculé depuis un jeu cible simplifié."
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "ajustement_roulement",
                    "Impossible de proposer un diamètre usiné sans jeu/serrage cible ni ajustement normalisé.",
                )

        if self.entre_axe_paliers_m is not None:
            entre_paliers = _req_pos("entre_axe_paliers_m", self.entre_axe_paliers_m)
        else:
            entre_paliers = None
            _push_inconnue(
                rapport,
                "partielles",
                "entre_axe_paliers_m",
                "Nécessaire pour la statique détaillée, les réactions et les épaulements complets.",
            )

        nb_j = int(self.nb_journaux_principaux)
        if nb_j < 1:
            raise ValueError("nb_journaux_principaux doit être >= 1.")

        largeur_totale = self.largeur_totale_arbre_m
        if largeur_totale is not None:
            largeur_totale = _req_pos("largeur_totale_arbre_m", largeur_totale)
        elif largeur_journal is not None and largeur_maneton is not None:
            largeur_totale = nb_j * float(largeur_journal) + float(largeur_maneton)
            rapport["notes_modele"].append(
                "largeur_totale_arbre_m déduite minimalement des largeurs de portées connues."
            )

        d_epaulement_journal = None
        if d_journal is not None:
            d_epaulement_journal = d_journal + self.regles_fabrication.marge_diametre_epaulement_sur_portee_m

        d_epaulement_maneton = None
        if d_maneton is not None:
            d_epaulement_maneton = d_maneton + self.regles_fabrication.marge_diametre_epaulement_sur_portee_m

        rayon_conge_journal = None
        if d_journal is not None:
            rayon_conge_journal = _borne(
                self.regles_fabrication.ratio_conge_sur_diametre * d_journal,
                self.regles_fabrication.conge_min_m,
                self.regles_fabrication.conge_max_m,
            )

        rayon_conge_maneton = None
        if d_maneton is not None:
            rayon_conge_maneton = _borne(
                self.regles_fabrication.ratio_conge_sur_diametre * d_maneton,
                self.regles_fabrication.conge_min_m,
                self.regles_fabrication.conge_max_m,
            )

        chanfrein_journal = None
        if d_journal is not None:
            chanfrein_journal = _borne(
                self.regles_fabrication.ratio_chanfrein_sur_diametre * d_journal,
                self.regles_fabrication.chanfrein_min_m,
                self.regles_fabrication.chanfrein_max_m,
            )

        chanfrein_maneton = None
        if d_maneton is not None:
            chanfrein_maneton = _borne(
                self.regles_fabrication.ratio_chanfrein_sur_diametre * d_maneton,
                self.regles_fabrication.chanfrein_min_m,
                self.regles_fabrication.chanfrein_max_m,
            )

        rapport["geometrie"].update({
            "diametre_journal_principal_m": d_journal,
            "largeur_portee_journal_m": largeur_journal,
            "diametre_maneton_m": d_maneton,
            "largeur_portee_maneton_m": largeur_maneton,
            "rayon_manivelle_m": r_manivelle,
            "course_m": course,
            "entre_axe_paliers_m": entre_paliers,
            "D_exterieur_reference_roulement_m": D_ref,
            "B_largeur_reference_roulement_m": B_ref,
            "largeur_totale_arbre_m": largeur_totale,
        })

        if rho is not None:
            Vtot = 0.0
            detail = []

            if d_journal is not None and largeur_journal is not None:
                Vj = nb_j * _section_disque(float(d_journal)) * float(largeur_journal)
                Vtot += Vj
                detail.append({
                    "troncon": "journaux_principaux",
                    "nombre": nb_j,
                    "diametre_m": float(d_journal),
                    "largeur_unitaire_m": float(largeur_journal),
                    "volume_total_m3": Vj,
                })

            if d_maneton is not None and largeur_maneton is not None:
                Vm = _section_disque(float(d_maneton)) * float(largeur_maneton)
                Vtot += Vm
                detail.append({
                    "troncon": "maneton",
                    "diametre_m": float(d_maneton),
                    "largeur_m": float(largeur_maneton),
                    "volume_m3": Vm,
                })

            if Vtot > 0.0:
                rapport["masse"] = {
                    "volume_total_minimal_m3": Vtot,
                    "masse_kg": float(rho) * Vtot,
                    "note": "Masse minimale basée sur les seules portées cylindriques modélisées.",
                    "detail": detail,
                }
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "masse",
                    "Calculable si au moins une portée géométrique est connue.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "masse",
                "Nécessite la densité matière.",
            )

        if d_journal is not None:
            rapport["inerties"]["journal_principal"] = {
                "section_m2": _section_disque(float(d_journal)),
                "I_m4": _inertie_cercle(float(d_journal)),
                "J_m4": _polar_J(float(d_journal)),
                "module_flexion_m3": _module_flexion(float(d_journal)),
            }

        if d_maneton is not None:
            rapport["inerties"]["maneton"] = {
                "section_m2": _section_disque(float(d_maneton)),
                "I_m4": _inertie_cercle(float(d_maneton)),
                "J_m4": _polar_J(float(d_maneton)),
                "module_flexion_m3": _module_flexion(float(d_maneton)),
            }

        if d_maneton is not None or d_journal is not None:
            x_j_g = None
            x_j_d = None
            x_m = 0.0 if d_maneton is not None else None

            if entre_paliers is not None:
                x_j_g = -0.5 * float(entre_paliers)
                x_j_d = +0.5 * float(entre_paliers)

            rapport["cao"] = {
                "type_piece": "arbre_vilebrequin",
                "hypothese_modele": "CAO minimale des portées cylindriques sans contrepoids ni bras définis.",
                "repere": {
                    "axe_rotation": "Z",
                    "origine_x_m": 0.0,
                    "origine_au_centre_maneton": x_m is not None,
                },
                "manivelle": {
                    "course_m": course,
                    "rayon_manivelle_m": r_manivelle,
                    "centre_maneton_x_m": x_m,
                },
                "journal_principal": {
                    "diametre_m": d_journal,
                    "largeur_portee_m": largeur_journal,
                    "diametre_epaulement_m": d_epaulement_journal,
                    "rayon_conge_m": rayon_conge_journal,
                    "chanfrein_m": chanfrein_journal,
                    "rugosite_ra_um": self.regles_fabrication.rugosite_portees_ra_um,
                    "tolerance_diametre_m": self.regles_fabrication.tolerance_diametre_portee_m,
                    "tolerance_largeur_m": self.regles_fabrication.tolerance_largeur_portee_m,
                    "centre_gauche_x_m": x_j_g,
                    "centre_droit_x_m": x_j_d,
                },
                "maneton": {
                    "diametre_m": d_maneton,
                    "largeur_portee_m": largeur_maneton,
                    "diametre_epaulement_m": d_epaulement_maneton,
                    "rayon_conge_m": rayon_conge_maneton,
                    "chanfrein_m": chanfrein_maneton,
                    "rugosite_ra_um": self.regles_fabrication.rugosite_portees_ra_um,
                    "tolerance_diametre_m": self.regles_fabrication.tolerance_diametre_portee_m,
                    "tolerance_largeur_m": self.regles_fabrication.tolerance_largeur_portee_m,
                    "centre_x_m": x_m,
                },
                "roulement_reference": {
                    "d_interieur_m": d_ref,
                    "D_exterieur_m": D_ref,
                    "B_largeur_m": B_ref,
                },
                "largeur_totale_estimee_m": largeur_totale,
                "nb_journaux_principaux": nb_j,
            }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "bloc_cao",
                "Bloc CAO complet calculable si au moins un diamètre de portée est connu.",
            )

        rapport["cinematique"] = {
            "course_m": course,
            "rayon_manivelle_m": r_manivelle,
            "rpm": rpm,
            "omega_rad_s": (2.0 * math.pi * float(rpm) / 60.0) if rpm is not None else None,
        }

        _push_inconnue(
            rapport,
            "partielles",
            "reactions_paliers",
            "Nécessaires pour la statique détaillée des journaux et les pressions réelles de palier.",
        )
        _push_inconnue(
            rapport,
            "partielles",
            "bras_de_vilebrequin",
            "Nécessaires pour dessiner complètement les joues/bras entre journaux et maneton.",
        )
        _push_inconnue(
            rapport,
            "partielles",
            "contrepoids",
            "Nécessaires pour la géométrie complète, la masse réelle et l'équilibrage.",
        )
        _push_inconnue(
            rapport,
            "partielles",
            "fatigue",
            "Nécessite spectre de charge, concentrations de contraintes, état de surface et traitements.",
        )

        rapport["entrees"] = {
            "course_m": self.course_m,
            "couple_max_Nm": self.couple_max_Nm,
            "moment_flexion_max_Nm": self.moment_flexion_max_Nm,
            "force_axiale_N": self.force_axiale_N,
            "force_bielle_effective_N": self.force_bielle_effective_N,
            "rpm": self.rpm,
            "diametre_journal_principal_m": self.diametre_journal_principal_m,
            "diametre_maneton_m": self.diametre_maneton_m,
            "largeur_portee_journal_m": self.largeur_portee_journal_m,
            "largeur_portee_maneton_m": self.largeur_portee_maneton_m,
            "entre_axe_paliers_m": self.entre_axe_paliers_m,
            "largeur_totale_arbre_m": self.largeur_totale_arbre_m,
            "nb_journaux_principaux": self.nb_journaux_principaux,
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": self.densite_kg_m3,
            "limite_elastique_pa": self.limite_elastique_pa,
            "module_young_pa": self.module_young_pa,
            "poisson": self.poisson,
            "resistance_traction_pa": self.resistance_traction_pa,
            "limite_fatigue_pa": self.limite_fatigue_pa,
            "facteur_securite": self.facteur_securite,
            "serrage_roulement_m": self.serrage_roulement_m,
            "jeu_roulement_m": self.jeu_roulement_m,
        }

        _dedup_inconnues(rapport)
        if strict and rapport["inconnues"]["impossibles"]:
            raise ValueError(
                "ArbreVilbrequin(strict=True) : des inconnues impossibles restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Extension fine : réactions, joues, équilibrage, fatigue, torsion vibratoire
# =============================================================================

@dataclass
class ArbreVilbrequinFine(ArbreVilbrequin):
    position_charge_depuis_palier_gauche_m: Optional[float] = None
    force_radiale_bielle_N: Optional[float] = None

    entraxe_journal_maneton_m: Optional[float] = None
    epaisseur_joue_m: Optional[float] = None
    largeur_joue_m: Optional[float] = None
    nb_joues: Optional[int] = None
    debord_joue_m: Optional[float] = None
    rayon_conge_joue_m: Optional[float] = None
    chanfrein_joue_m: Optional[float] = None

    masse_tournante_equilibree_kg: Optional[float] = None
    masse_alternative_kg: Optional[float] = None
    fraction_masse_alternative_equilibree: Optional[float] = None
    coefficient_equilibrage: Optional[float] = None
    rayon_cg_contrepoids_m: Optional[float] = None
    masse_contrepoids_existante_kg: Optional[float] = None

    moment_flexion_min_Nm: Optional[float] = None
    moment_flexion_moyen_Nm: Optional[float] = None
    moment_flexion_alterne_Nm: Optional[float] = None
    couple_min_Nm: Optional[float] = None
    couple_moyen_Nm: Optional[float] = None
    couple_alterne_Nm: Optional[float] = None
    Kt_flexion: float = 1.0
    Kt_torsion: float = 1.0
    facteur_surface_fatigue: float = 1.0
    facteur_taille_fatigue: float = 1.0
    facteur_fiabilite_fatigue: float = 1.0
    facteur_temperature_fatigue: float = 1.0
    traitement_thermique: Optional[str] = None

    inertie_amont_kg_m2: Optional[float] = None
    inertie_aval_kg_m2: Optional[float] = None
    raideur_torsion_equivalente_Nm_rad: Optional[float] = None
    ordre_excitation: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport = super().analyser(strict=False)
        rapport.setdefault("reactions_paliers", {})
        rapport.setdefault("joues", {})
        rapport.setdefault("equilibrage", {})
        rapport.setdefault("fatigue", {})
        rapport.setdefault("torsion_vibratoire", {})

        geom = rapport.get("geometrie", {})
        mat = rapport.get("materiau", {})
        rec = rapport.get("recuperations", {})

        d_j = geom.get("diametre_journal_principal_m")
        d_m = geom.get("diametre_maneton_m")
        L_j = geom.get("largeur_portee_journal_m")
        r = geom.get("rayon_manivelle_m")
        rpm = rec.get("rpm")
        Re = mat.get("limite_elastique_pa")
        Rm = mat.get("resistance_traction_pa")
        Sf = mat.get("limite_fatigue_pa")
        rho = mat.get("densite_kg_m3")

        F_rad = self.force_radiale_bielle_N
        if F_rad is None and _is_finite(rec.get("force_bielle_effective_N")):
            F_rad = abs(float(rec["force_bielle_effective_N"]))
        if _is_finite(self.entre_axe_paliers_m) and F_rad is not None:
            L = _req_pos("entre_axe_paliers_m", self.entre_axe_paliers_m)
            a = self.position_charge_depuis_palier_gauche_m
            if a is None and int(getattr(self, "nb_journaux_principaux", 2)) == 2:
                a = 0.5 * L
                rapport["notes_modele"].append(
                    "position_charge_depuis_palier_gauche_m non fournie : charge supposée au milieu entre deux paliers."
                )
            if a is not None:
                a = _req_pos("position_charge_depuis_palier_gauche_m", a, strictly=False)
                stat = _reactions_simple(float(F_rad), L, a)
                rapport["reactions_paliers"] = {
                    "force_radiale_bielle_N": float(F_rad),
                    "entre_axe_paliers_m": L,
                    "position_charge_depuis_palier_gauche_m": a,
                    **stat,
                }
                if not _is_finite(rec.get("moment_flexion_max_Nm")):
                    rec["moment_flexion_max_Nm"] = stat["moment_max_Nm"]
                    rapport["recuperations"]["moment_flexion_max_Nm"] = stat["moment_max_Nm"]
            else:
                _push_inconnue(rapport, "partielles", "position_charge_depuis_palier_gauche_m", "Requise pour les réactions exactes de paliers.")
        else:
            _push_inconnue(rapport, "partielles", "reactions_paliers", "Nécessite entre_axe_paliers_m et force radiale bielle.")

        if rapport["reactions_paliers"] and _is_finite(d_j) and _is_finite(L_j):
            Rg = abs(float(rapport["reactions_paliers"]["reaction_gauche_N"]))
            Rd = abs(float(rapport["reactions_paliers"]["reaction_droite_N"]))
            rapport.setdefault("pressions_contact", {})
            rapport["pressions_contact"]["journal_gauche"] = {
                "force_N": Rg,
                "diametre_m": float(d_j),
                "largeur_portee_m": float(L_j),
                "pression_moyenne_pa": Rg / (float(d_j) * float(L_j)),
            }
            rapport["pressions_contact"]["journal_droit"] = {
                "force_N": Rd,
                "diametre_m": float(d_j),
                "largeur_portee_m": float(L_j),
                "pression_moyenne_pa": Rd / (float(d_j) * float(L_j)),
            }

        if all(_is_finite(v) for v in (self.epaisseur_joue_m, self.largeur_joue_m, self.entraxe_journal_maneton_m, d_j, d_m)):
            h = float(self.entraxe_journal_maneton_m) - 0.5 * (float(d_j) + float(d_m))
            if h > 0.0:
                nb = int(self.nb_joues) if isinstance(self.nb_joues, int) and self.nb_joues > 0 else 2
                V_une = float(self.epaisseur_joue_m) * float(self.largeur_joue_m) * h
                rapport["joues"] = {
                    "epaisseur_joue_m": float(self.epaisseur_joue_m),
                    "largeur_joue_m": float(self.largeur_joue_m),
                    "hauteur_web_m": h,
                    "nb_joues": nb,
                    "volume_total_modele_m3": nb * V_une,
                    "debord_joue_m": self.debord_joue_m,
                    "rayon_conge_joue_m": self.rayon_conge_joue_m,
                    "chanfrein_joue_m": self.chanfrein_joue_m,
                    "note": "Modèle volumique prismatique pour les joues.",
                }
                if _is_finite(rho):
                    rapport["joues"]["masse_totale_modele_kg"] = float(rho) * nb * V_une
            else:
                _push_inconnue(rapport, "partielles", "joues", "L'entraxe journal-maneton fourni est incompatible avec les diamètres.")
        else:
            _push_inconnue(rapport, "partielles", "joues", "Nécessite épaisseur, largeur et entraxe réel des joues.")

        if _is_finite(r) and _is_finite(self.rayon_cg_contrepoids_m) and _is_finite(self.coefficient_equilibrage):
            if _is_finite(self.masse_tournante_equilibree_kg) or _is_finite(self.masse_alternative_kg):
                m_eq = float(self.masse_tournante_equilibree_kg or 0.0) + float(self.fraction_masse_alternative_equilibree or 0.0) * float(self.masse_alternative_kg or 0.0)
                moment_cible = float(self.coefficient_equilibrage) * m_eq * float(r)
                m_cw = moment_cible / float(self.rayon_cg_contrepoids_m)
                rapport["equilibrage"] = {
                    "masse_equivalente_a_equilibrer_kg": m_eq,
                    "coefficient_equilibrage": float(self.coefficient_equilibrage),
                    "moment_equilibrage_cible_kg_m": moment_cible,
                    "rayon_cg_contrepoids_m": float(self.rayon_cg_contrepoids_m),
                    "masse_contrepoids_requise_kg": m_cw,
                }
                if _is_finite(self.masse_contrepoids_existante_kg):
                    resid = float(self.masse_contrepoids_existante_kg) * float(self.rayon_cg_contrepoids_m) - moment_cible
                    rapport["equilibrage"]["masse_contrepoids_existante_kg"] = float(self.masse_contrepoids_existante_kg)
                    rapport["equilibrage"]["balourd_residuel_kg_m"] = resid
            else:
                _push_inconnue(rapport, "partielles", "equilibrage", "Nécessite les masses tournante et/ou alternative.")
        else:
            _push_inconnue(rapport, "partielles", "contrepoids", "Nécessite rayon manivelle, rayon CG contrepoids et coefficient d'équilibrage.")

        if _is_finite(d_j):
            Mmax = self.moment_flexion_max_Nm if _is_finite(self.moment_flexion_max_Nm) else rec.get("moment_flexion_max_Nm")
            Mmin = self.moment_flexion_min_Nm
            if not _is_finite(self.moment_flexion_moyen_Nm) and not _is_finite(self.moment_flexion_alterne_Nm) and _is_finite(Mmax) and _is_finite(Mmin):
                M_m = 0.5 * (float(Mmax) + float(Mmin))
                M_a = 0.5 * (float(Mmax) - float(Mmin))
            else:
                M_m = self.moment_flexion_moyen_Nm
                M_a = self.moment_flexion_alterne_Nm

            Tmax = self.couple_max_Nm if _is_finite(self.couple_max_Nm) else rec.get("couple_max_Nm")
            Tmin = self.couple_min_Nm
            if not _is_finite(self.couple_moyen_Nm) and not _is_finite(self.couple_alterne_Nm) and _is_finite(Tmax) and _is_finite(Tmin):
                T_m = 0.5 * (float(Tmax) + float(Tmin))
                T_a = 0.5 * (float(Tmax) - float(Tmin))
            else:
                T_m = self.couple_moyen_Nm
                T_a = self.couple_alterne_Nm

            if all(_is_finite(v) for v in (M_m, M_a, T_m, T_a, Sf)) and (_is_finite(Rm) or _is_finite(Re)):
                sigma_m = float(self.Kt_flexion) * _sigma_flexion_max(float(M_m), float(d_j))
                sigma_a = float(self.Kt_flexion) * _sigma_flexion_max(float(M_a), float(d_j))
                tau_m = float(self.Kt_torsion) * _tau_torsion_max(float(T_m), float(d_j))
                tau_a = float(self.Kt_torsion) * _tau_torsion_max(float(T_a), float(d_j))
                sigma_vm_m = _von_mises_sigma_tau(sigma_m, tau_m)
                sigma_vm_a = _von_mises_sigma_tau(sigma_a, tau_a)
                Se_corr = float(Sf) * float(self.facteur_surface_fatigue) * float(self.facteur_taille_fatigue) * float(self.facteur_fiabilite_fatigue) * float(self.facteur_temperature_fatigue)
                rapport["fatigue"] = {
                    "section_reference": "journal_principal",
                    "diametre_reference_m": float(d_j),
                    "sigma_von_mises_moyenne_pa": sigma_vm_m,
                    "sigma_von_mises_alternee_pa": sigma_vm_a,
                    "limite_endurance_corrigee_pa": Se_corr,
                    "Kt_flexion": float(self.Kt_flexion),
                    "Kt_torsion": float(self.Kt_torsion),
                    "goodman_utilisation": (_goodman(sigma_vm_a, sigma_vm_m, Se_corr, float(Rm)) if _is_finite(Rm) else None),
                    "soderberg_utilisation": (_soderberg(sigma_vm_a, sigma_vm_m, Se_corr, float(Re)) if _is_finite(Re) else None),
                    "traitement_thermique": self.traitement_thermique,
                }
            else:
                _push_inconnue(rapport, "partielles", "fatigue_vilebrequin", "Nécessite moments/couples moyens et alternés, endurance corrigée et matériau.")
        else:
            _push_inconnue(rapport, "partielles", "fatigue_vilebrequin", "Nécessite un diamètre de section de référence.")

        if all(_is_finite(v) for v in (self.raideur_torsion_equivalente_Nm_rad, self.inertie_amont_kg_m2, self.inertie_aval_kg_m2)):
            tv = _frequence_propre_torsion_2_masses(float(self.raideur_torsion_equivalente_Nm_rad), float(self.inertie_amont_kg_m2), float(self.inertie_aval_kg_m2))
            if _is_finite(rpm) and _is_finite(self.ordre_excitation):
                fexc = float(self.ordre_excitation) * float(rpm) / 60.0
                tv["frequence_excitation_hz"] = fexc
                tv["ratio_excitation_sur_mode"] = fexc / tv["frequence_hz"] if tv["frequence_hz"] > 0.0 else None
            rapport["torsion_vibratoire"] = tv
        else:
            _push_inconnue(rapport, "partielles", "torsion_vibratoire", "Nécessite deux inerties et une raideur torsionnelle équivalente.")

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "ArbreVilbrequinFine(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport


# =============================================================================
# Exemple minimal
# =============================================================================
if __name__ == "__main__":
    class RoulementAiguilleMock:
        def analyser(self):
            return {
                "dimensions_requises": {"d_interieur_requis_m": 0.030},
                "dimensions_reference": {
                    "d_interieur_m": 0.030,
                    "D_exterieur_m": 0.037,
                    "B_largeur_m": 0.016,
                },
            }

    av = ArbreVilbrequinFine(
        roulement_aiguille=RoulementAiguilleMock(),
        course_m=0.085,
        couple_max_Nm=134.0,
        limite_elastique_pa=800e6,
        resistance_traction_pa=950e6,
        limite_fatigue_pa=420e6,
        densite_kg_m3=7800.0,
        facteur_securite=2.0,
        nb_journaux_principaux=2,
        entre_axe_paliers_m=0.090,
        position_charge_depuis_palier_gauche_m=0.045,
        force_radiale_bielle_N=12000.0,
        diametre_journal_principal_m=0.030,
        diametre_maneton_m=0.030,
        largeur_portee_journal_m=0.017,
        largeur_portee_maneton_m=0.016,
    )

    from pprint import pprint
    pprint(av.analyser(strict=False))
