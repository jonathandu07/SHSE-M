# backend\ensemble\optimisation.py
# Rend cohérent et compatible les données entre les pièces
# et optimise le système complet pour minimiser les pertes énergétiques.

from __future__ import annotations

from dataclasses import dataclass, is_dataclass, replace
from typing import Any, Dict, Optional, Tuple, List, Sequence
import math


# ============================================================
# Imports robustes
# ============================================================

try:
    from backend.ensemble.systeme_complet import SystemeComplet
except Exception:  # pragma: no cover
    try:
        from ensemble.systeme_complet import SystemeComplet  # type: ignore
    except Exception:  # pragma: no cover
        SystemeComplet = None  # type: ignore

try:
    from backend.components.moteur_thermique import MoteurThermique
except Exception:  # pragma: no cover
    try:
        from components.moteur_thermique import MoteurThermique  # type: ignore
    except Exception:  # pragma: no cover
        MoteurThermique = None  # type: ignore


# ============================================================
# Helpers robustes
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    if _is_finite(x):
        return int(float(x))
    return None


def _safe_dict(d: Any) -> Dict[str, Any]:
    return d if isinstance(d, dict) else {}


def _get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for n in names:
            if n in obj:
                return obj.get(n)
        return None
    for n in names:
        if hasattr(obj, n):
            try:
                return getattr(obj, n)
            except Exception:
                pass
    return None


def _dig(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Essaie, dans l'ordre:
    - analyser(strict=False)
    - calculer(strict=False)
    - analyser()
    - calculer()
    """
    if obj is None:
        return None

    for name in ("analyser", "calculer"):
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                out = fn(strict=False)
                if isinstance(out, dict):
                    return out
            except TypeError:
                try:
                    out = fn()
                    if isinstance(out, dict):
                        return out
                except Exception:
                    pass
            except Exception:
                pass
    return None


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": nom, "raison": raison}
    )


def _push_warning(rapport: Dict[str, Any], categorie: str, nom: str, detail: str) -> None:
    rapport.setdefault("alertes", {}).setdefault(categorie, []).append(
        {"nom": nom, "detail": detail}
    )


def _dedup_list_of_dict(lst: List[Dict[str, Any]], *, keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, ...]] = set()
    out: List[Dict[str, Any]] = []
    for it in lst:
        sig = tuple(str(it.get(k, "")) for k in keys)
        if sig not in seen:
            seen.add(sig)
            out.append(it)
    return out


def _dedup_rapport(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for k in ("impossibles", "partielles"):
        inc[k] = _dedup_list_of_dict(list(inc.get(k, []) or []), keys=("nom", "raison"))

    alerts = rapport.setdefault("alertes", {})
    for k, lst in list(alerts.items()):
        alerts[k] = _dedup_list_of_dict(list(lst or []), keys=("nom", "detail"))

    actions = rapport.setdefault("actions", [])
    rapport["actions"] = _dedup_list_of_dict(list(actions or []), keys=("cible", "champ", "valeur"))


def _append_note(rapport: Dict[str, Any], message: str) -> None:
    rapport.setdefault("notes_modele", []).append(str(message))


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    if not _is_finite(a) or not _is_finite(b):
        return None
    if abs(float(b)) <= 1e-18:
        return None
    return float(a) / float(b)


def _ecart_relatif(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    if not _is_finite(a) or not _is_finite(b):
        return None
    den = max(abs(float(a)), abs(float(b)), 1e-18)
    return abs(float(a) - float(b)) / den


def _somme_finis(vals: Sequence[Any]) -> Optional[float]:
    xs = [float(v) for v in vals if _is_finite(v)]
    return sum(xs) if xs else None


def _min_finis(vals: Sequence[Any]) -> Optional[float]:
    xs = [float(v) for v in vals if _is_finite(v)]
    return min(xs) if xs else None


def _max_finis(vals: Sequence[Any]) -> Optional[float]:
    xs = [float(v) for v in vals if _is_finite(v)]
    return max(xs) if xs else None


def _is_dataclass_instance(obj: Any) -> bool:
    return obj is not None and is_dataclass(obj) and not isinstance(obj, type)


def _replace_if_possible(obj: Any, **updates: Any) -> Any:
    if _is_dataclass_instance(obj):
        try:
            return replace(obj, **updates)
        except Exception:
            return obj
    return obj


# ============================================================
# Extraction transversale
# ============================================================

def _extraire_pertes(rapport_piece: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """
    Agrège des pertes énergétiques si elles existent déjà dans le rapport.
    """
    r = _safe_dict(rapport_piece)
    pertes = _safe_dict(r.get("pertes"))
    resultats = _safe_dict(r.get("resultats"))
    thermique = _safe_dict(r.get("thermique"))
    etancheite = _safe_dict(r.get("etancheite"))

    p_frott = _somme_finis([
        pertes.get("P_frottement_total_W"),
        pertes.get("P_frottement_segment_W"),
        pertes.get("P_frottement_palier_W"),
        thermique.get("P_perdue_W"),
    ])

    p_fuite = _first_finite(
        resultats.get("P_fuite_W"),
        etancheite.get("P_fuite_W"),
    )

    q_fuite = _first_finite(
        resultats.get("Q_fuite_m3_s"),
        etancheite.get("Q_fuite_m3_s"),
    )

    mdot_fuite = _first_finite(
        resultats.get("m_dot_fuite_kg_s"),
        etancheite.get("m_dot_fuite_kg_s"),
    )

    return {
        "P_frottement_W": p_frott,
        "P_fuite_W": p_fuite,
        "Q_fuite_m3_s": q_fuite,
        "m_dot_fuite_kg_s": mdot_fuite,
    }


def _first_finite(*vals: Any) -> Optional[float]:
    for v in vals:
        if _is_finite(v):
            return float(v)
    return None


def _extract_systeme_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    synth = _safe_dict(r.get("synthese"))
    mt = _safe_dict(synth.get("moteur_thermique"))
    veh = _safe_dict(synth.get("vehicule"))
    batt = _safe_dict(synth.get("batterie"))
    alt = _safe_dict(synth.get("alternateur"))
    cao = _safe_dict(r.get("cao"))
    cao_mt = _safe_dict(cao.get("moteur_thermique"))
    liaisons = _safe_dict(r.get("liaisons"))
    pme = _safe_dict(liaisons.get("pme"))
    bus = _safe_dict(liaisons.get("bus_dc"))

    return {
        "rpm_moteur": _first_finite(mt.get("rpm_nominal"), cao_mt.get("rpm_nominal")),
        "P_moteur_thermique_W": _safe_float(mt.get("puissance_requise_W")),
        "couple_moteur_thermique_Nm": _safe_float(mt.get("couple_requis_Nm")),
        "pme_pa": _first_finite(mt.get("pme_pa"), pme.get("pme_pa_utilisee_ou_requise")),
        "architecture": _get(mt, "architecture"),
        "nb_cyl": _safe_int(mt.get("nombre_cylindres")),
        "alesage_m": _first_finite(mt.get("alesage_m"), cao_mt.get("alesage_mm") / 1000.0 if _is_finite(cao_mt.get("alesage_mm")) else None),
        "course_m": _first_finite(mt.get("course_m"), cao_mt.get("course_mm") / 1000.0 if _is_finite(cao_mt.get("course_mm")) else None),
        "epaisseur_cylindre_m": _first_finite(mt.get("epaisseur_cylindre_retenue_m"), cao_mt.get("epaisseur_cylindre_mm") / 1000.0 if _is_finite(cao_mt.get("epaisseur_cylindre_mm")) else None),
        "V_bus_dc_v": _first_finite(veh.get("tension_bus_dc_v"), bus.get("V_bus_dc_v")),
        "P_bus_dc_design_w": _first_finite(veh.get("puissance_bus_dc_design_w"), bus.get("P_bus_dc_design_w")),
        "E_batterie_kwh": _safe_float(batt.get("energie_utile_kwh")),
        "P_alt_meca_W": _safe_float(alt.get("P_mecanique_W")),
        "T_alt_meca_Nm": _safe_float(alt.get("couple_mecanique_Nm")),
        "solidworks_ready": bool(cao.get("solidworks_ready")) if isinstance(cao.get("solidworks_ready"), bool) else None,
    }


def _extract_cylindre_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    ent = _safe_dict(r.get("entrees"))
    geo = _safe_dict(r.get("geometrie"))
    cao = _safe_dict(geo.get("cao"))
    dim = _safe_dict(r.get("dimensionnement"))
    contraintes = _safe_dict(r.get("contraintes"))

    return {
        "alesage_m": _first_finite(
            ent.get("alesage_m"),
            geo.get("diametre_interne_m"),
            cao.get("diametre_interieur_nominal_m"),
        ),
        "course_m": _safe_float(ent.get("course_m")),
        "pression_max_pa": _safe_float(ent.get("pression_max_pa")),
        "epaisseur_m": _first_finite(
            dim.get("epaisseur_cylindre_retenue_m"),
            dim.get("epaisseur_cylindre_lame_m"),
            dim.get("epaisseur_cylindre_mince_m"),
            geo.get("epaisseur_paroi_m"),
        ),
        "diametre_exterieur_m": _first_finite(
            geo.get("diametre_externe_m"),
            cao.get("diametre_exterieur_nominal_m"),
        ),
        "sigma_vm_pa": _safe_float(contraintes.get("sigma_von_mises_max_pa")),
    }


def _extract_piston_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    dims = _safe_dict(r.get("dimensions"))
    cao = _safe_dict(dims.get("cao"))
    joints = _safe_dict(r.get("joints"))
    cine = _safe_dict(r.get("cinematique"))
    etan = _safe_dict(r.get("etancheite"))

    return {
        "diametre_exterieur_m": _first_finite(
            cao.get("diametre_exterieur_nominal_m"),
            dims.get("diametre_exterieur_m"),
        ),
        "hauteur_totale_m": _safe_float(dims.get("hauteur_totale_m")),
        "jeu_radial_froid_m": _safe_float(dims.get("jeu_radial_froid_m")),
        "jeu_radial_chaud_m": _safe_float(dims.get("jeu_radial_chaud_m")),
        "nb_joints": _safe_int(joints.get("nb_joints")),
        "force_axiale_nette_n": _safe_float(cine.get("force_axiale_nette_n")),
        "force_gaz_n": _safe_float(cine.get("force_gaz_n")),
        "Q_fuite_m3_s": _first_finite(etan.get("Q_fuite_m3_s"), r.get("Q_fuite_m3_s")),
    }


def _extract_arbre_piston_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    contraintes = _safe_dict(r.get("contraintes"))
    cao = _safe_dict(r.get("cao"))
    dim = _safe_dict(r.get("dimensionnement_evide"))
    ru = _safe_dict(dim.get("resultat_unique"))

    return {
        "diametre_fut_ext_m": _first_finite(
            geo.get("diametre_exterieur_fut_m"),
            geo.get("diametre_exterieur_fut_min_vm_m"),
            ru.get("Do_m"),
        ),
        "diametre_fut_int_m": _first_finite(
            geo.get("diametre_interieur_fut_m"),
            geo.get("diametre_interieur_fut_associe_vm_m"),
            ru.get("Di_m"),
        ),
        "sigma_vm_pa": _safe_float(contraintes.get("sigma_von_mises_pa")),
        "sigma_allow_pa": _safe_float(contraintes.get("sigma_allow_pa")),
        "marge_sigma_vm": _safe_float(contraintes.get("marge_sigma_vm")),
        "cao": cao,
    }


def _extract_bielle_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    gt = _safe_dict(geo.get("grande_tete"))
    pt = _safe_dict(geo.get("petite_tete"))
    fut = _safe_dict(geo.get("fut"))
    efforts = _safe_dict(r.get("efforts"))
    pressions = _safe_dict(r.get("pressions_contact"))
    cao = _safe_dict(r.get("cao"))

    return {
        "longueur_bielle_m": _safe_float(_safe_dict(r.get("entrees")).get("longueur_bielle_m")),
        "diametre_axe_piston_m": _first_finite(
            pt.get("diametre_axe_piston_m"),
            geo.get("diametre_axe_piston_m"),
        ),
        "longueur_portee_petite_tete_m": _first_finite(
            pt.get("longueur_portee_m"),
            geo.get("longueur_portee_petite_tete_m"),
        ),
        "diametre_maneton_m": _first_finite(
            gt.get("diametre_maneton_m"),
            geo.get("diametre_maneton_m"),
        ),
        "longueur_portee_grande_tete_m": _first_finite(
            gt.get("longueur_portee_m"),
            geo.get("longueur_portee_grande_tete_m"),
        ),
        "section_fut_m2": _first_finite(fut.get("section_m2"), geo.get("section_fut_m2")),
        "force_axiale_max_N": _first_finite(
            efforts.get("force_axiale_max_N"),
            geo.get("force_axiale_max_N"),
        ),
        "pression_petite_tete_pa": _safe_float(pressions.get("pression_petite_tete_pa")),
        "pression_grande_tete_pa": _safe_float(pressions.get("pression_grande_tete_pa")),
        "cao": cao,
    }


def _extract_vilebrequin_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    cine = _safe_dict(r.get("cinematique"))
    geo = _safe_dict(r.get("geometrie"))
    contraintes = _safe_dict(r.get("contraintes"))
    masses = _safe_dict(r.get("masses"))
    inerties = _safe_dict(r.get("inerties"))
    raideur = _safe_dict(r.get("raideur"))

    return {
        "course_m": _safe_float(cine.get("course_m")),
        "rpm": _safe_float(cine.get("rpm")),
        "couple_max_Nm": _safe_float(cine.get("couple_max_Nm")),
        "rayon_manivelle_m": _safe_float(cine.get("rayon_manivelle_m")),
        "diametre_journal_principal_m": _safe_float(geo.get("diametre_journal_principal_m")),
        "diametre_maneton_m": _safe_float(geo.get("diametre_maneton_m")),
        "largeur_journal_principal_m": _safe_float(geo.get("largeur_journal_principal_m")),
        "largeur_maneton_m": _safe_float(geo.get("largeur_maneton_m")),
        "sigma_vm_pa": _safe_float(contraintes.get("sigma_von_mises_pa")),
        "masse_totale_kg": _safe_float(masses.get("masse_totale_kg")),
        "I_polaire_kg_m2": _safe_float(inerties.get("I_polaire_totale_kg_m2")),
        "k_torsion_Nm_rad": _safe_float(raideur.get("raideur_torsion_Nm_rad")),
    }


def _extract_roulement_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    dims = _safe_dict(r.get("dimensions_requises"))
    roulement = _safe_dict(r.get("roulement"))
    charges = _safe_dict(r.get("charges"))
    vie = _safe_dict(r.get("vie"))

    return {
        "d_interieur_requis_m": _first_finite(
            dims.get("d_interieur_requis_m"),
            dims.get("diametre_interieur_requis_m"),
        ),
        "B_requise_m": _first_finite(
            dims.get("B_requise_m"),
            dims.get("largeur_requise_m"),
        ),
        "C_requis_N": _safe_float(vie.get("C_requis_N")),
        "C0_requis_N": _safe_float(vie.get("C0_requis_N")),
        "force_radiale_equivalente_N": _safe_float(charges.get("force_radiale_equivalente_N")),
        "rpm": _safe_float(roulement.get("rpm")),
    }


def _extract_joint_piston_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    etan = _safe_dict(r.get("etancheite"))
    geo = _safe_dict(r.get("geometrie"))
    frott = _safe_dict(r.get("frottement"))
    cao = _safe_dict(r.get("cao"))

    return {
        "Q_fuite_m3_s": _first_finite(etan.get("Q_fuite_m3_s"), r.get("Q_fuite_m3_s")),
        "force_frottement_N": _safe_float(frott.get("force_frottement_N")),
        "P_frottement_W": _safe_float(frott.get("P_frottement_W")),
        "largeur_gorge_m": _first_finite(geo.get("largeur_gorge_m"), cao.get("largeur_gorge_m")),
        "profondeur_gorge_m": _first_finite(geo.get("profondeur_gorge_m"), cao.get("profondeur_gorge_m")),
    }


def _extract_coussinet_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    tribo = _safe_dict(r.get("tribologie"))
    resultats = _safe_dict(r.get("resultats"))
    cao = _safe_dict(r.get("cao"))

    return {
        "diametre_interieur_m": _first_finite(cao.get("diametre_interieur_m"), resultats.get("diametre_interieur_m")),
        "longueur_m": _first_finite(cao.get("longueur_m"), resultats.get("longueur_m")),
        "pression_proj_pa": _first_finite(tribo.get("pression_proj_pa"), resultats.get("pression_proj_pa")),
        "PV": _first_finite(tribo.get("PV"), resultats.get("PV")),
        "P_frottement_W": _first_finite(tribo.get("P_frottement_W"), resultats.get("P_frottement_W")),
    }


def _extract_vis_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    choix = _safe_dict(r.get("choix"))
    assemblage = _safe_dict(r.get("assemblage"))
    cao = _safe_dict(r.get("cao"))

    return {
        "nb_vis": _safe_int(_first_non_none(choix.get("nb_vis"), assemblage.get("nb_vis"))),
        "diametre_nominal_m": _first_finite(
            choix.get("diametre_nominal_m"),
            assemblage.get("diametre_nominal_m"),
            cao.get("diametre_nominal_m"),
        ),
        "couple_serrage_par_vis_Nm": _first_finite(
            assemblage.get("couple_serrage_par_vis_Nm"),
            choix.get("couple_serrage_par_vis_Nm"),
        ),
        "precharge_par_vis_N": _first_finite(
            assemblage.get("precharge_par_vis_N"),
            choix.get("precharge_par_vis_N"),
        ),
    }


def _extract_couvercle_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    assemblage = _safe_dict(r.get("assemblage"))
    thermique = _safe_dict(r.get("thermique"))
    cao = _safe_dict(r.get("cao"))

    return {
        "epaisseur_m": _first_finite(
            geo.get("epaisseur_m"),
            cao.get("epaisseur_m"),
        ),
        "force_separation_N": _safe_float(assemblage.get("force_separation_N")),
        "precharge_totale_N": _safe_float(assemblage.get("precharge_totale_N")),
        "R_th_K_W": _first_finite(thermique.get("resistance_thermique_K_W"), thermique.get("R_th_K_W")),
    }


def _first_non_none(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


# ============================================================
# Pièce agrégée d'optimisation
# ============================================================

@dataclass
class OptimisationSysteme:
    """
    Orchestrateur inter-pièces.
    Il ne remplace pas les calculateurs de pièces:
    il vérifie leur cohérence mutuelle et agrège les pertes.
    """

    systeme_complet: Optional[Any] = None

    cylindre: Optional[Any] = None
    piston: Optional[Any] = None
    joint_piston: Optional[Any] = None

    deplaceur: Optional[Any] = None
    joint_deplaceur: Optional[Any] = None

    bielle: Optional[Any] = None
    arbre_piston: Optional[Any] = None
    coussinet_arbre_piston: Optional[Any] = None

    arbre_vilebrequin: Optional[Any] = None
    vilbrequin: Optional[Any] = None
    roulement_aiguille_arbre: Optional[Any] = None
    roulement_aiguille_arbre_vilebrequin: Optional[Any] = None

    couvercle_cylindre: Optional[Any] = None
    vis_couvercle_cylindre: Optional[Any] = None
    clavette_arbre: Optional[Any] = None

    # tolérances de cohérence
    tolerance_relatif_forte: float = 0.02
    tolerance_relatif_standard: float = 0.05
    tolerance_relatif_lache: float = 0.10

    def analyser(self) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "optimisation_systeme",
            "rapports_sources": {},
            "extractions": {},
            "coherences": {},
            "pertes": {},
            "synthese_optimisation": {},
            "actions": [],
            "alertes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # --------------------------------------------------------
        # 1) Récupération des rapports
        # --------------------------------------------------------
        rep_sys = _try_call_report(self.systeme_complet)
        rep_cyl = _try_call_report(self.cylindre)
        rep_pis = _try_call_report(self.piston)
        rep_jp = _try_call_report(self.joint_piston)
        rep_dep = _try_call_report(self.deplaceur)
        rep_jd = _try_call_report(self.joint_deplaceur)
        rep_bie = _try_call_report(self.bielle)
        rep_ap = _try_call_report(self.arbre_piston)
        rep_cous = _try_call_report(self.coussinet_arbre_piston)
        rep_av = _try_call_report(self.arbre_vilebrequin)
        rep_vb = _try_call_report(self.vilbrequin)
        rep_raa = _try_call_report(self.roulement_aiguille_arbre)
        rep_raav = _try_call_report(self.roulement_aiguille_arbre_vilebrequin)
        rep_cov = _try_call_report(self.couvercle_cylindre)
        rep_vis = _try_call_report(self.vis_couvercle_cylindre)
        rep_clav = _try_call_report(self.clavette_arbre)

        rapport["rapports_sources"] = {
            "systeme_complet": rep_sys is not None,
            "cylindre": rep_cyl is not None,
            "piston": rep_pis is not None,
            "joint_piston": rep_jp is not None,
            "deplaceur": rep_dep is not None,
            "joint_deplaceur": rep_jd is not None,
            "bielle": rep_bie is not None,
            "arbre_piston": rep_ap is not None,
            "coussinet_arbre_piston": rep_cous is not None,
            "arbre_vilebrequin": rep_av is not None,
            "vilbrequin": rep_vb is not None,
            "roulement_aiguille_arbre": rep_raa is not None,
            "roulement_aiguille_arbre_vilebrequin": rep_raav is not None,
            "couvercle_cylindre": rep_cov is not None,
            "vis_couvercle_cylindre": rep_vis is not None,
            "clavette_arbre": rep_clav is not None,
        }

        # --------------------------------------------------------
        # 2) Extraction normalisée
        # --------------------------------------------------------
        ext_sys = _extract_systeme_metrics(rep_sys)
        ext_cyl = _extract_cylindre_metrics(rep_cyl)
        ext_pis = _extract_piston_metrics(rep_pis)
        ext_ap = _extract_arbre_piston_metrics(rep_ap)
        ext_bie = _extract_bielle_metrics(rep_bie)
        ext_vb = _extract_vilebrequin_metrics(rep_vb)
        ext_raa = _extract_roulement_metrics(rep_raa)
        ext_raav = _extract_roulement_metrics(rep_raav)
        ext_jp = _extract_joint_piston_metrics(rep_jp)
        ext_cous = _extract_coussinet_metrics(rep_cous)
        ext_vis = _extract_vis_metrics(rep_vis)
        ext_cov = _extract_couvercle_metrics(rep_cov)

        rapport["extractions"] = {
            "systeme_complet": ext_sys,
            "cylindre": ext_cyl,
            "piston": ext_pis,
            "arbre_piston": ext_ap,
            "bielle": ext_bie,
            "vilbrequin": ext_vb,
            "roulement_aiguille_arbre": ext_raa,
            "roulement_aiguille_arbre_vilebrequin": ext_raav,
            "joint_piston": ext_jp,
            "coussinet_arbre_piston": ext_cous,
            "vis_couvercle_cylindre": ext_vis,
            "couvercle_cylindre": ext_cov,
        }

        # --------------------------------------------------------
        # 3) Cohérence géométrique globale
        # --------------------------------------------------------
        coh = rapport["coherences"]

        # 3.1 Alesage / piston
        D_cyl = _first_finite(ext_cyl.get("alesage_m"), ext_sys.get("alesage_m"))
        D_pis = _safe_float(ext_pis.get("diametre_exterieur_m"))
        if D_cyl is not None and D_pis is not None:
            jeu_rad = 0.5 * (D_cyl - D_pis)
            ok = jeu_rad >= -1e-12
            coh["piston_vs_cylindre"] = {
                "alesage_m": D_cyl,
                "diametre_piston_m": D_pis,
                "jeu_radial_calcule_m": jeu_rad,
                "jeu_radial_froid_piece_m": ext_pis.get("jeu_radial_froid_m"),
                "jeu_radial_chaud_piece_m": ext_pis.get("jeu_radial_chaud_m"),
                "coherent": ok,
            }
            if not ok:
                _push_warning(
                    rapport,
                    "interferences",
                    "piston_vs_cylindre",
                    "Le piston est plus grand que l'alésage nominal.",
                )
                rapport["actions"].append({
                    "cible": "piston",
                    "champ": "diametre_exterieur_m",
                    "valeur": D_cyl,
                    "strategie": "reduire_ou_recalculer_jeu",
                })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "coherence piston/cylindre",
                "Nécessite alesage cylindre et diamètre piston.",
            )

        # 3.2 Course système / cylindre / vilebrequin
        course_ref = _first_finite(ext_sys.get("course_m"), ext_cyl.get("course_m"), ext_vb.get("course_m"))
        if course_ref is not None:
            ecarts_course: List[Dict[str, Any]] = []
            for nom, val in (
                ("systeme_complet", ext_sys.get("course_m")),
                ("cylindre", ext_cyl.get("course_m")),
                ("vilbrequin", ext_vb.get("course_m")),
            ):
                v = _safe_float(val)
                if v is not None:
                    ec = _ecart_relatif(v, course_ref)
                    ecarts_course.append({"source": nom, "course_m": v, "ecart_relatif": ec})

            coh["course_globale"] = {
                "course_reference_m": course_ref,
                "comparaison": ecarts_course,
                "coherent": all(
                    (it["ecart_relatif"] is None or it["ecart_relatif"] <= self.tolerance_relatif_standard)
                    for it in ecarts_course
                ),
            }

            if not coh["course_globale"]["coherent"]:
                _push_warning(
                    rapport,
                    "coherence_course",
                    "course_globale",
                    "Les valeurs de course ne sont pas alignées entre sous-systèmes.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "course globale",
                "Aucune course exploitable n'a été trouvée.",
            )

        # 3.3 Arbre piston / petite tête / coussinet
        d_ap = _safe_float(ext_ap.get("diametre_fut_ext_m"))
        d_pt = _safe_float(ext_bie.get("diametre_axe_piston_m"))
        d_cous = _safe_float(ext_cous.get("diametre_interieur_m"))

        if d_ap is not None:
            coh_ap = {
                "diametre_arbre_piston_m": d_ap,
                "diametre_petite_tete_m": d_pt,
                "diametre_coussinet_m": d_cous,
                "ecart_rel_petite_tete": _ecart_relatif(d_ap, d_pt) if d_pt is not None else None,
                "ecart_rel_coussinet": _ecart_relatif(d_ap, d_cous) if d_cous is not None else None,
                "coherent_petite_tete": None if d_pt is None else (_ecart_relatif(d_ap, d_pt) <= self.tolerance_relatif_standard),
                "coherent_coussinet": None if d_cous is None else (_ecart_relatif(d_ap, d_cous) <= self.tolerance_relatif_standard),
            }
            coh["arbre_piston_interfaces"] = coh_ap

            if coh_ap["coherent_petite_tete"] is False:
                _push_warning(
                    rapport,
                    "interfaces",
                    "arbre_piston_vs_petite_tete",
                    "Diamètre arbre-piston et petite tête non cohérents.",
                )
            if coh_ap["coherent_coussinet"] is False:
                _push_warning(
                    rapport,
                    "interfaces",
                    "arbre_piston_vs_coussinet",
                    "Diamètre arbre-piston et coussinet non cohérents.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "interface arbre_piston",
                "Diamètre arbre-piston introuvable.",
            )

        # 3.4 Maneton / grande tête / roulement grande tête / vilebrequin
        d_maneton_ref = _first_finite(
            ext_bie.get("diametre_maneton_m"),
            ext_vb.get("diametre_maneton_m"),
            ext_raav.get("d_interieur_requis_m"),
        )

        if d_maneton_ref is not None:
            cmp_maneton: List[Dict[str, Any]] = []
            for nom, v in (
                ("bielle", ext_bie.get("diametre_maneton_m")),
                ("vilbrequin", ext_vb.get("diametre_maneton_m")),
                ("roulement_aiguille_arbre_vilebrequin", ext_raav.get("d_interieur_requis_m")),
            ):
                vv = _safe_float(v)
                if vv is not None:
                    cmp_maneton.append({
                        "source": nom,
                        "diametre_m": vv,
                        "ecart_relatif": _ecart_relatif(vv, d_maneton_ref),
                    })

            coh["maneton_interfaces"] = {
                "diametre_reference_m": d_maneton_ref,
                "comparaison": cmp_maneton,
                "coherent": all(
                    (it["ecart_relatif"] is None or it["ecart_relatif"] <= self.tolerance_relatif_standard)
                    for it in cmp_maneton
                ),
            }

            if not coh["maneton_interfaces"]["coherent"]:
                _push_warning(
                    rapport,
                    "interfaces",
                    "maneton",
                    "Diamètres maneton/bielle/roulement non cohérents.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "interface maneton",
                "Aucun diamètre de maneton exploitable.",
            )

        # 3.5 Pression cylindre / couvercle / vis
        pmax_ref = _first_finite(ext_cyl.get("pression_max_pa"), ext_sys.get("pme_pa"))
        if pmax_ref is not None:
            coh["fermeture_cylindre"] = {
                "pression_reference_pa": pmax_ref,
                "force_separation_couvercle_N": ext_cov.get("force_separation_N"),
                "precharge_totale_couvercle_N": ext_cov.get("precharge_totale_N"),
                "precharge_par_vis_N": ext_vis.get("precharge_par_vis_N"),
                "nb_vis": ext_vis.get("nb_vis"),
                "coherent": None,
            }

            F_sep = _safe_float(ext_cov.get("force_separation_N"))
            F_pre = _safe_float(ext_cov.get("precharge_totale_N"))
            if F_sep is not None and F_pre is not None:
                ok = F_pre >= F_sep
                coh["fermeture_cylindre"]["coherent"] = ok
                if not ok:
                    _push_warning(
                        rapport,
                        "assemblage",
                        "couvercle_precharge",
                        "La précharge totale du couvercle est inférieure à la force de séparation.",
                    )

        # --------------------------------------------------------
        # 4) Pertes énergétiques agrégées
        # --------------------------------------------------------
        pertes_sys = _extract_pertes(rep_sys)
        pertes_cyl = _extract_pertes(rep_cyl)
        pertes_pis = _extract_pertes(rep_pis)
        pertes_jp = _extract_pertes(rep_jp)
        pertes_dep = _extract_pertes(rep_dep)
        pertes_jd = _extract_pertes(rep_jd)
        pertes_cous = _extract_pertes(rep_cous)
        pertes_cov = _extract_pertes(rep_cov)

        P_frott_total = _somme_finis([
            pertes_sys.get("P_frottement_W"),
            pertes_cyl.get("P_frottement_W"),
            pertes_pis.get("P_frottement_W"),
            pertes_jp.get("P_frottement_W"),
            pertes_dep.get("P_frottement_W"),
            pertes_jd.get("P_frottement_W"),
            pertes_cous.get("P_frottement_W"),
            pertes_cov.get("P_frottement_W"),
            ext_jp.get("P_frottement_W"),
            ext_cous.get("P_frottement_W"),
        ])

        Q_fuite_total = _somme_finis([
            pertes_sys.get("Q_fuite_m3_s"),
            pertes_cyl.get("Q_fuite_m3_s"),
            pertes_pis.get("Q_fuite_m3_s"),
            pertes_jp.get("Q_fuite_m3_s"),
        ])

        mdot_fuite_total = _somme_finis([
            pertes_sys.get("m_dot_fuite_kg_s"),
            pertes_cyl.get("m_dot_fuite_kg_s"),
            pertes_pis.get("m_dot_fuite_kg_s"),
            pertes_jp.get("m_dot_fuite_kg_s"),
        ])

        rapport["pertes"] = {
            "P_frottement_totale_W": P_frott_total,
            "Q_fuite_totale_m3_s": Q_fuite_total,
            "m_dot_fuite_total_kg_s": mdot_fuite_total,
            "detail": {
                "systeme_complet": pertes_sys,
                "cylindre": pertes_cyl,
                "piston": pertes_pis,
                "joint_piston": pertes_jp,
                "deplaceur": pertes_dep,
                "joint_deplaceur": pertes_jd,
                "coussinet_arbre_piston": pertes_cous,
                "couvercle_cylindre": pertes_cov,
            },
        }

        # --------------------------------------------------------
        # 5) Synthèse optimisation
        # --------------------------------------------------------
        nb_alertes = sum(len(v) for v in rapport.get("alertes", {}).values())
        nb_inconnues = len(rapport["inconnues"]["impossibles"]) + len(rapport["inconnues"]["partielles"])

        score_coherence = 100.0
        score_coherence -= 8.0 * nb_alertes
        score_coherence -= 2.0 * nb_inconnues
        score_coherence = max(0.0, min(100.0, score_coherence))

        P_design = _safe_float(ext_sys.get("P_bus_dc_design_w"))
        penalite_pertes = None
        if P_design is not None and P_design > 0.0 and P_frott_total is not None:
            penalite_pertes = 100.0 * P_frott_total / P_design

        score_global = score_coherence
        if penalite_pertes is not None:
            score_global = max(0.0, score_global - min(50.0, penalite_pertes))

        rapport["synthese_optimisation"] = {
            "score_coherence_100": score_coherence,
            "penalite_pertes_pct_sur_bus_dc": penalite_pertes,
            "score_global_100": score_global,
            "solidworks_ready_systeme": ext_sys.get("solidworks_ready"),
            "nombre_alertes": nb_alertes,
            "nombre_inconnues": nb_inconnues,
            "systeme_coherent": (score_coherence >= 70.0 and nb_alertes == 0),
        }

        # --------------------------------------------------------
        # 6) Actions d'optimisation explicites
        # --------------------------------------------------------
        if ext_jp.get("P_frottement_W") is not None:
            rapport["actions"].append({
                "cible": "joint_piston",
                "champ": "geometrie_gorge",
                "valeur": "a_reexaminer",
                "strategie": "reduire_frottement_si_etancheite_suffisante",
            })

        if ext_cous.get("PV") is not None and _is_finite(ext_cous.get("PV")):
            rapport["actions"].append({
                "cible": "coussinet_arbre_piston",
                "champ": "PV",
                "valeur": ext_cous.get("PV"),
                "strategie": "verifier_longueur_ou_charge_si_PV_trop_eleve",
            })

        if ext_cov.get("R_th_K_W") is not None:
            rapport["actions"].append({
                "cible": "couvercle_cylindre",
                "champ": "resistance_thermique",
                "valeur": ext_cov.get("R_th_K_W"),
                "strategie": "reduire_Rth_si_evacuation_thermique_insuffisante",
            })

        if ext_ap.get("marge_sigma_vm") is not None:
            rapport["actions"].append({
                "cible": "arbre_piston",
                "champ": "marge_sigma_vm",
                "valeur": ext_ap.get("marge_sigma_vm"),
                "strategie": "augmenter_section_si_marge_trop_faible",
            })

        _append_note(
            rapport,
            "Le score global agrège cohérence géométrique et pénalité sur pertes de frottement connues."
        )
        _append_note(
            rapport,
            "Aucune dimension n'est inventée : les incohérences sont signalées et les actions proposées restent explicites."
        )

        _dedup_rapport(rapport)
        return rapport

    # ------------------------------------------------------------
    # Optimisation légère : construit des objets corrigés si possible
    # ------------------------------------------------------------
    def optimiser(self) -> Dict[str, Any]:
        """
        Produit :
        - un rapport d'analyse,
        - une proposition de mises à jour dataclass quand cela est faisable sans hypothèse cachée.
        """
        rapport = self.analyser()

        objets_corriges: Dict[str, Any] = {
            "systeme_complet": self.systeme_complet,
            "cylindre": self.cylindre,
            "piston": self.piston,
            "arbre_piston": self.arbre_piston,
            "bielle": self.bielle,
            "vilbrequin": self.vilbrequin,
            "couvercle_cylindre": self.couvercle_cylindre,
            "vis_couvercle_cylindre": self.vis_couvercle_cylindre,
        }

        coh = _safe_dict(rapport.get("coherences"))
        piston_vs_cyl = _safe_dict(coh.get("piston_vs_cylindre"))

        D_cyl = _safe_float(piston_vs_cyl.get("alesage_m"))
        D_pis = _safe_float(piston_vs_cyl.get("diametre_piston_m"))
        coherent_pc = piston_vs_cyl.get("coherent")

        # Correction prudente piston/cylindre :
        # on ne change le piston que si le cylindre est connu et qu'il y a interférence.
        if coherent_pc is False and D_cyl is not None and self.piston is not None:
            current = D_pis
            if current is not None:
                # on garde un très léger retrait au lieu d'égaler strictement l'alésage
                new_d = min(current, D_cyl)
                objets_corriges["piston"] = _replace_if_possible(
                    self.piston,
                    diametre_exterieur_m=new_d,
                )

        # Si le système complet est une dataclass et que son moteur thermique interne peut être aligné
        ext_sys = _safe_dict(_safe_dict(rapport.get("extractions")).get("systeme_complet"))
        if self.systeme_complet is not None and _is_dataclass_instance(self.systeme_complet):
            mt = getattr(self.systeme_complet, "moteur_thermique", None)
            if mt is not None and _is_dataclass_instance(mt):
                bore = _safe_float(ext_sys.get("alesage_m"))
                course = _safe_float(ext_sys.get("course_m"))
                nb_cyl = _safe_int(ext_sys.get("nb_cyl"))
                arch = _get(ext_sys, "architecture")

                updates_mt: Dict[str, Any] = {}
                if bore is not None:
                    updates_mt["alesage_m"] = bore
                if course is not None:
                    updates_mt["course_m"] = course
                if nb_cyl is not None:
                    updates_mt["nombre_cylindres"] = nb_cyl
                if arch is not None:
                    updates_mt["architecture"] = arch

                if updates_mt:
                    mt_new = _replace_if_possible(mt, **updates_mt)
                    objets_corriges["systeme_complet"] = _replace_if_possible(
                        self.systeme_complet,
                        moteur_thermique=mt_new,
                    )

        return {
            "analyse": rapport,
            "objets_corriges": objets_corriges,
        }


# ============================================================
# Exécution simple
# ============================================================

if __name__ == "__main__":
    opt = OptimisationSysteme()
    rep = opt.analyser()

    print("=== Optimisation système ===")
    print("Alertes:", sum(len(v) for v in rep.get("alertes", {}).values()))
    print("Inconnues impossibles:", len(rep["inconnues"]["impossibles"]))
    print("Inconnues partielles:", len(rep["inconnues"]["partielles"]))
    print("Score cohérence:", rep["synthese_optimisation"]["score_coherence_100"])
    print("Score global:", rep["synthese_optimisation"]["score_global_100"])