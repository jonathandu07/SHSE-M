# backend/pieces/arbre_vilbrequin.py
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
                    mat, "limite_elastique_pa", "Re_pa", "rp02_pa", "yield_strength_pa"
                )
                E = E if E is not None else g(
                    mat, "module_young_pa", "E_pa", "young_pa", "young_modulus_pa"
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
        # fallback attributs directs
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

    # blocs fréquents
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

    # fallback attributs directs
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
    # Epaulements / marges
    marge_largeur_portee_sur_roulement_m: float = 0.001
    marge_diametre_epaulement_sur_portee_m: float = 0.001

    # Congés / rayons
    conge_min_m: float = 0.0008
    conge_max_m: float = 0.0040
    ratio_conge_sur_diametre: float = 0.06

    # Chanfreins
    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.0020
    ratio_chanfrein_sur_diametre: float = 0.03

    # Rugosité / tolérances
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

    # Liens
    cylindre: Optional[Any] = None
    piston: Optional[Any] = None
    bielle: Optional[Any] = None
    moteur_thermique: Optional[Any] = None
    roulement_aiguille: Optional[Any] = None

    # Cinématique / externes
    course_m: Optional[float] = None
    couple_max_Nm: Optional[float] = None
    moment_flexion_max_Nm: Optional[float] = None
    force_axiale_N: Optional[float] = None
    force_bielle_effective_N: Optional[float] = None
    rpm: Optional[float] = None

    # Géométrie imposée
    diametre_journal_principal_m: Optional[float] = None
    diametre_maneton_m: Optional[float] = None
    largeur_portee_journal_m: Optional[float] = None
    largeur_portee_maneton_m: Optional[float] = None

    # Géométrie globale utile CAO
    entre_axe_paliers_m: Optional[float] = None
    largeur_totale_arbre_m: Optional[float] = None
    nb_journaux_principaux: int = 2

    # Matériau
    materiau_cle: Optional[str] = None
    densite_kg_m3: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    module_young_pa: Optional[float] = None
    facteur_securite: float = 2.0

    # Ajustements
    serrage_roulement_m: Optional[float] = None
    jeu_roulement_m: Optional[float] = None

    # Règles CAO
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

        # ---------------------------------------------------------------------
        # 1) Matériau
        # ---------------------------------------------------------------------
        props = _resoudre_materiau(
            self.materiau_cle,
            self.densite_kg_m3,
            self.limite_elastique_pa,
            self.module_young_pa,
        )
        rho = props["densite_kg_m3"]
        Re = props["limite_elastique_pa"]
        E = props["module_young_pa"]
        sigma_adm = (float(Re) / FS) if Re is not None else None

        rapport["materiau"] = {
            "materiau_cle": self.materiau_cle,
            "densite_kg_m3": rho,
            "limite_elastique_pa": Re,
            "module_young_pa": E,
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

        # ---------------------------------------------------------------------
        # 2) Résolution depuis autres pièces
        # ---------------------------------------------------------------------
        cyl = _resoudre_depuis_cylindre(self.cylindre)
        pist = _resoudre_depuis_piston(self.piston)
        bie = _resoudre_depuis_bielle(self.bielle)
        mot = _resoudre_depuis_moteur(self.moteur_thermique)
        rou = _resoudre_depuis_roulement(self.roulement_aiguille)

        # ---------------------------------------------------------------------
        # 3) Course -> rayon manivelle
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 4) Efforts / couple / rpm
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 5) Roulement + maneton
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 6) Dimensionnements diamètres minimaux
        # ---------------------------------------------------------------------
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

        # Géométrie imposée minimale
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

        # ---------------------------------------------------------------------
        # 7) Contraintes réelles si géométrie connue
        # ---------------------------------------------------------------------
        def calc_contraintes_section(
            d_use: Optional[float],
            nom: str,
        ) -> Optional[Dict[str, Any]]:
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

        # ---------------------------------------------------------------------
        # 8) Pressions de contact sur portées
        # ---------------------------------------------------------------------
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

        # pression sur journal : on ne connaît pas la réaction palier sans statique détaillée
        if d_journal is not None and largeur_journal is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "pression_contact_journal",
                "Nécessite la réaction au palier principal, non calculée ici sans statique détaillée.",
            )

        # ---------------------------------------------------------------------
        # 9) Ajustement roulement
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 10) Géométrie exploitable
        # ---------------------------------------------------------------------
        # Entre-axe paliers : si non fourni, impossible de statuer sur les réactions.
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

        # Largeur totale approximative si on a les largeurs
        largeur_totale = self.largeur_totale_arbre_m
        if largeur_totale is not None:
            largeur_totale = _req_pos("largeur_totale_arbre_m", largeur_totale)
        elif largeur_journal is not None and largeur_maneton is not None:
            # modèle minimal : 2 journaux + 1 maneton
            largeur_totale = nb_j * float(largeur_journal) + float(largeur_maneton)
            rapport["notes_modele"].append(
                "largeur_totale_arbre_m déduite minimalement des largeurs de portées connues."
            )

        # Détails CAO
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

        # ---------------------------------------------------------------------
        # 11) Masse / inerties minimales
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 12) Bloc CAO / SolidWorks
        # ---------------------------------------------------------------------
        # Convention minimaliste :
        # - origine en X au centre du maneton,
        # - axe de rotation principal = Z,
        # - les portées sont des cylindres coaxiaux distincts à modéliser,
        # - les masses de bras/contrepoids restent hors modèle tant qu'elles ne sont pas définies.
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

        # ---------------------------------------------------------------------
        # 13) Synthèse cinématique
        # ---------------------------------------------------------------------
        rapport["cinematique"] = {
            "course_m": course,
            "rayon_manivelle_m": r_manivelle,
            "rpm": rpm,
            "omega_rad_s": (2.0 * math.pi * float(rpm) / 60.0) if rpm is not None else None,
        }

        # ---------------------------------------------------------------------
        # 14) Inconnues complémentaires mécaniques
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # 15) Entrées tracées
        # ---------------------------------------------------------------------
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
            "facteur_securite": self.facteur_securite,
            "serrage_roulement_m": self.serrage_roulement_m,
            "jeu_roulement_m": self.jeu_roulement_m,
        }

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "ArbreVilbrequin(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# =============================================================================
# Exemple minimal
# =============================================================================
if __name__ == "__main__":
    class RoulementAiguilleMock:
        def calculer(self):
            return {
                "dimensions_requises": {"d_interieur_requis_m": 0.030},
                "dimensions_reference": {
                    "d_interieur_m": 0.030,
                    "D_exterieur_m": 0.037,
                    "B_largeur_m": 0.016,
                },
            }

    av = ArbreVilbrequin(
        roulement_aiguille=RoulementAiguilleMock(),
        course_m=0.085,
        couple_max_Nm=134.0,
        limite_elastique_pa=800e6,
        densite_kg_m3=7800.0,
        facteur_securite=2.0,
        nb_journaux_principaux=2,
    )

    from pprint import pprint
    pprint(av.analyser(strict=False))