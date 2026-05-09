
# backend/ensemble/optimisation.py
# =============================================================================
# ORCHESTRATEUR D'OPTIMISATION INTER-PIECES — SHSE-M
# =============================================================================
# Rôle :
# - rendre cohérents les calculateurs de pièces sans inventer de cotes,
# - normaliser les sorties hétérogènes des modules,
# - vérifier les interfaces géométriques / mécaniques / d'étanchéité,
# - agréger les pertes déjà calculées par les sous-modules,
# - proposer des corrections prudentes quand elles sont faisables sans hypothèse cachée.
#
# Important :
# - ce module ne remplace pas les calculateurs spécialisés ;
# - il ne choisit pas de dimensions "catalogue" à ta place ;
# - si une donnée manque, elle est signalée dans "inconnues".
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
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
    from backend.components.moteur_thermique.moteur_thermique import MoteurThermique
except Exception:  # pragma: no cover
    try:
        from backend.components.moteur_thermique.moteur_thermique import MoteurThermique  # type: ignore
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


def _first_non_none(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _first_finite(*vals: Any) -> Optional[float]:
    for v in vals:
        if _is_finite(v):
            return float(v)
    return None


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or not _is_finite(a) or not _is_finite(b):
        return None
    if abs(float(b)) <= 1e-18:
        return None
    return float(a) / float(b)


def _ecart_relatif(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or not _is_finite(a) or not _is_finite(b):
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
    if not _is_dataclass_instance(obj):
        return obj
    try:
        allowed = {f.name for f in fields(obj)}
        filt = {k: v for k, v in updates.items() if k in allowed}
        return replace(obj, **filt) if filt else obj
    except Exception:
        return obj


def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Essaie, dans l'ordre :
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


def _resolve_report_mapping(source: Any) -> Optional[Dict[str, Any]]:
    if isinstance(source, dict):
        return source
    return _try_call_report(source)


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


def _append_note(rapport: Dict[str, Any], message: str) -> None:
    rapport.setdefault("notes_modele", []).append(str(message))


def _dedup_rapport(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for k in ("impossibles", "partielles"):
        inc[k] = _dedup_list_of_dict(list(inc.get(k, []) or []), keys=("nom", "raison"))

    alerts = rapport.setdefault("alertes", {})
    for k, lst in list(alerts.items()):
        alerts[k] = _dedup_list_of_dict(list(lst or []), keys=("nom", "detail"))

    actions = rapport.setdefault("actions", [])
    rapport["actions"] = _dedup_list_of_dict(
        list(actions or []),
        keys=("cible", "champ", "valeur", "strategie"),
    )


# ============================================================
# Extraction transversale des pertes
# ============================================================

def _extract_pertes(rapport_piece: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    r = _safe_dict(rapport_piece)

    pertes = _safe_dict(r.get("pertes"))
    resultats = _safe_dict(r.get("resultats"))
    thermique = _safe_dict(r.get("thermique"))
    etancheite = _safe_dict(r.get("etancheite"))
    frottement = _safe_dict(r.get("frottement"))
    frottements = _safe_dict(r.get("frottements"))
    tribologie = _safe_dict(r.get("tribologie"))

    return {
        "P_frottement_W": _somme_finis([
            pertes.get("P_frottement_total_W"),
            pertes.get("P_frottement_totale_W"),
            pertes.get("P_frottement_W"),
            thermique.get("P_perdue_W"),
            frottement.get("P_frottement_W"),
            frottements.get("P_frottement_W"),
            tribologie.get("P_frottement_W"),
            resultats.get("P_frottement_W"),
            r.get("P_frottement_W"),
        ]),
        "P_fuite_W": _first_finite(
            pertes.get("P_fuite_W"),
            resultats.get("P_fuite_W"),
            etancheite.get("P_fuite_W"),
            r.get("P_fuite_W"),
        ),
        "Q_fuite_m3_s": _first_finite(
            pertes.get("Q_fuite_totale_m3_s"),
            pertes.get("Q_fuite_m3_s"),
            resultats.get("Q_fuite_m3_s"),
            etancheite.get("Q_fuite_m3_s"),
            r.get("Q_fuite_m3_s"),
        ),
        "m_dot_fuite_kg_s": _first_finite(
            pertes.get("m_dot_fuite_total_kg_s"),
            pertes.get("m_dot_fuite_kg_s"),
            resultats.get("m_dot_fuite_kg_s"),
            etancheite.get("m_dot_fuite_kg_s"),
            r.get("m_dot_fuite_kg_s"),
        ),
    }


# ============================================================
# Extractions normalisées des pièces
# ============================================================

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
        "rpm_moteur": _first_finite(
            mt.get("rpm_nominal"),
            cao_mt.get("rpm_nominal"),
            liaisons.get("rpm_moteur_thermique"),
        ),
        "P_moteur_thermique_W": _safe_float(mt.get("puissance_requise_W")),
        "couple_moteur_thermique_Nm": _safe_float(mt.get("couple_requis_Nm")),
        "pme_pa": _first_finite(mt.get("pme_pa"), pme.get("pme_pa_utilisee_ou_requise")),
        "pression_max_pa": _first_finite(
            mt.get("pression_max_pa"),
            liaisons.get("pression_max_pa"),
        ),
        "architecture": _get(mt, "architecture"),
        "nb_cyl": _safe_int(mt.get("nombre_cylindres")),
        "alesage_m": _first_finite(
            mt.get("alesage_m"),
            cao_mt.get("alesage_mm") / 1000.0 if _is_finite(cao_mt.get("alesage_mm")) else None,
        ),
        "course_m": _first_finite(
            mt.get("course_m"),
            cao_mt.get("course_mm") / 1000.0 if _is_finite(cao_mt.get("course_mm")) else None,
        ),
        "epaisseur_cylindre_m": _first_finite(
            mt.get("epaisseur_cylindre_retenue_m"),
            cao_mt.get("epaisseur_cylindre_mm") / 1000.0 if _is_finite(cao_mt.get("epaisseur_cylindre_mm")) else None,
        ),
        "V_bus_dc_v": _first_finite(veh.get("tension_bus_dc_v"), bus.get("V_bus_dc_v")),
        "P_bus_dc_design_w": _first_finite(veh.get("puissance_bus_dc_design_w"), bus.get("P_bus_dc_design_w")),
        "E_batterie_kwh": _safe_float(batt.get("energie_utile_kwh")),
        "P_alt_meca_W": _safe_float(alt.get("P_mecanique_W")),
        "T_alt_meca_Nm": _safe_float(alt.get("couple_mecanique_Nm")),
        "solidworks_ready": bool(cao.get("solidworks_ready")),
    }


def _extract_cylindre_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    ent = _safe_dict(r.get("entrees"))
    geo = _safe_dict(r.get("geometrie"))
    cao = _safe_dict(geo.get("cao"))
    dim = _safe_dict(r.get("dimensionnement"))
    contraintes = _safe_dict(r.get("contraintes"))
    deform = _safe_dict(r.get("deformations"))
    assemblage = _safe_dict(r.get("assemblage"))
    fabrication = _safe_dict(r.get("fabrication"))

    return {
        "alesage_m": _first_finite(
            ent.get("alesage_m"),
            geo.get("diametre_interne_m"),
            geo.get("diametre_interieur_nominal_m"),
            cao.get("diametre_interieur_nominal_m"),
        ),
        "course_m": _first_finite(ent.get("course_m"), geo.get("course_m")),
        "longueur_utile_m": _first_finite(ent.get("longueur_utile_m"), geo.get("longueur_utile_m")),
        "pression_service_pa": _safe_float(ent.get("pression_service_pa")),
        "pression_max_pa": _safe_float(ent.get("pression_max_pa")),
        "epaisseur_m": _first_finite(
            dim.get("epaisseur_retenue_m"),
            dim.get("epaisseur_cylindre_retenue_m"),
            dim.get("epaisseur_lame_m"),
            dim.get("epaisseur_mince_m"),
            geo.get("epaisseur_paroi_m"),
        ),
        "diametre_exterieur_m": _first_finite(
            geo.get("diametre_exterieur_m"),
            geo.get("diametre_externe_m"),
            cao.get("diametre_exterieur_nominal_m"),
        ),
        "diametre_bride_externe_m": _first_finite(
            assemblage.get("diametre_bride_externe_m"),
            geo.get("diametre_bride_externe_m"),
        ),
        "diametre_cercle_percage_m": _first_finite(
            assemblage.get("diametre_cercle_percage_m"),
            geo.get("diametre_cercle_percage_m"),
        ),
        "force_separation_N": _first_finite(
            assemblage.get("force_separation_N"),
            assemblage.get("force_pression_piston_max_N"),
        ),
        "force_joint_N": _safe_float(assemblage.get("force_joint_N")),
        "precharge_totale_requise_N": _first_finite(
            assemblage.get("force_precharge_totale_requise_N"),
            assemblage.get("force_precharge_totale_N"),
        ),
        "sigma_vm_pa": _safe_float(contraintes.get("sigma_von_mises_max_pa")),
        "ovalisation_m": _first_finite(
            deform.get("ovalisation_m"),
            deform.get("ovalisation_serrage_m"),
        ),
        "augmentation_diametre_interne_pression_m": _safe_float(
            deform.get("augmentation_diametre_interne_pression_m")
        ),
        "augmentation_diametre_interne_thermique_m": _safe_float(
            deform.get("augmentation_diametre_interne_thermique_m")
        ),
        "rugosite_alesage_ra_um": _safe_float(fabrication.get("alesage_ra_um")),
        "surcote_finition_m": _safe_float(fabrication.get("surcote_finition_m")),
    }


def _extract_piston_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    ent = _safe_dict(r.get("entrees"))
    dims = _safe_dict(r.get("dimensions"))
    geo = _safe_dict(r.get("geometrie"))
    cao = _safe_dict(r.get("cao"))
    joints = _safe_dict(r.get("joints"))
    etan = _safe_dict(r.get("etancheite"))
    cine = _safe_dict(r.get("cinematique"))
    efforts = _safe_dict(r.get("efforts"))

    return {
        "diametre_exterieur_m": _first_finite(
            geo.get("diametre_exterieur_m"),
            cao.get("diametre_exterieur_nominal_m"),
            dims.get("diametre_exterieur_m"),
            ent.get("alesage_nominal_m"),
        ),
        "hauteur_totale_m": _first_finite(
            geo.get("hauteur_totale_m"),
            dims.get("hauteur_totale_m"),
            cao.get("hauteur_totale_m"),
        ),
        "jeu_radial_froid_m": _first_finite(
            geo.get("jeu_radial_froid_m"),
            dims.get("jeu_radial_froid_m"),
            etan.get("jeu_radial_froid_m"),
        ),
        "jeu_radial_chaud_m": _first_finite(
            geo.get("jeu_radial_chaud_m"),
            dims.get("jeu_radial_chaud_m"),
            etan.get("jeu_radial_chaud_m"),
        ),
        "nb_joints": _safe_int(_first_non_none(joints.get("nb_joints"), ent.get("nb_joints"))),
        "diametre_fond_rainure_m": _first_finite(
            joints.get("diametre_fond_rainure_m"),
            geo.get("diametre_fond_rainure_m"),
        ),
        "force_axiale_nette_N": _first_finite(
            cine.get("force_axiale_nette_n"),
            cine.get("force_axiale_nette_N"),
            efforts.get("force_axiale_nette_N"),
        ),
        "force_gaz_N": _first_finite(cine.get("force_gaz_n"), cine.get("force_gaz_N")),
        "Q_fuite_m3_s": _first_finite(
            etan.get("Q_fuite_m3_s"),
            r.get("Q_fuite_m3_s"),
        ),
    }


def _extract_joint_piston_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    gj = _safe_dict(r.get("geometrie_joint"))
    gorge = _safe_dict(r.get("gorge"))
    frott = _safe_dict(r.get("frottements"))
    coh = _safe_dict(r.get("coherences"))
    rain = _safe_dict(r.get("rainures"))
    efforts = _safe_dict(r.get("efforts"))

    return {
        "nb_joints": _safe_int(_first_non_none(rain.get("nb_joints"), gj.get("nb_joints"))),
        "diametre_interieur_cylindre_m": _safe_float(gj.get("diametre_interieur_cylindre_m")),
        "diametre_interieur_joint_m": _safe_float(gj.get("diametre_interieur_joint_m")),
        "section_joint_m": _first_finite(gj.get("section_joint_m"), gj.get("diametre_section_joint_m")),
        "diametre_fond_gorge_m": _safe_float(gorge.get("diametre_fond_gorge_m")),
        "largeur_gorge_m": _safe_float(gorge.get("largeur_gorge_m")),
        "profondeur_gorge_m": _safe_float(gorge.get("profondeur_gorge_m")),
        "squeeze": _safe_float(coh.get("squeeze")),
        "pression_contact_pa": _first_finite(
            efforts.get("pression_contact_pa"),
            efforts.get("pression_contact_estimee_pa"),
        ),
        "force_frottement_N": _first_finite(
            frott.get("force_frottement_N"),
            frott.get("force_frottement_estimee_N"),
        ),
        "P_frottement_W": _safe_float(frott.get("P_frottement_W")),
    }


def _extract_deplaceur_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    efforts = _safe_dict(r.get("efforts"))
    etan = _safe_dict(r.get("etancheite"))
    contraintes = _safe_dict(r.get("contraintes"))

    return {
        "diametre_exterieur_m": _safe_float(geo.get("diametre_exterieur_m")),
        "diametre_interieur_m": _safe_float(geo.get("diametre_interieur_m")),
        "longueur_totale_m": _safe_float(geo.get("longueur_totale_m")),
        "jeu_radial_m": _safe_float(geo.get("jeu_radial_m")),
        "longueur_zone_chaude_m": _safe_float(geo.get("longueur_zone_chaude_m")),
        "longueur_zone_froide_m": _safe_float(geo.get("longueur_zone_froide_m")),
        "pression_max_pa": _first_finite(
            efforts.get("pression_max_pa"),
            _safe_dict(r.get("pressions")).get("pression_max_pa"),
        ),
        "force_axiale_N": _first_finite(
            efforts.get("force_axiale_N"),
            efforts.get("force_resultante_axiale_N"),
        ),
        "Q_fuite_m3_s": _first_finite(etan.get("Q_fuite_m3_s"), r.get("Q_fuite_m3_s")),
        "sigma_vm_pa": _first_finite(
            contraintes.get("sigma_von_mises_pa"),
            contraintes.get("sigma_eq_pa"),
        ),
    }


def _extract_joint_deplaceur_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    gorge = _safe_dict(r.get("gorge"))
    service = _safe_dict(r.get("service"))
    frott = _safe_dict(r.get("frottement"))
    verif = _safe_dict(r.get("verifications"))
    cao = _safe_dict(r.get("cao"))

    return {
        "diametre_deplaceur_m": _first_finite(
            service.get("diametre_deplaceur_m"),
            geo.get("diametre_deplaceur_m"),
        ),
        "diametre_fond_gorge_m": _first_finite(
            gorge.get("diametre_fond_gorge_m"),
            geo.get("diametre_fond_gorge_m"),
            cao.get("diametre_fond_gorge_m"),
        ),
        "diametre_centreline_joint_m": _first_finite(
            geo.get("diametre_centreline_joint_m"),
            cao.get("diametre_centreline_joint_m"),
        ),
        "section_joint_m": _safe_float(service.get("section_joint_m")),
        "largeur_gorge_m": _first_finite(
            gorge.get("largeur_gorge_m"),
            cao.get("largeur_gorge_m"),
        ),
        "profondeur_gorge_m": _first_finite(
            gorge.get("profondeur_gorge_m"),
            gorge.get("profondeur_gorge_radiale_m"),
            cao.get("profondeur_gorge_m"),
        ),
        "squeeze": _first_finite(service.get("squeeze"), verif.get("squeeze")),
        "force_frottement_N": _safe_float(frott.get("force_frottement_N")),
        "P_frottement_W": _safe_float(frott.get("P_frottement_W")),
    }


def _extract_bielle_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    ent = _safe_dict(r.get("entrees"))
    geo = _safe_dict(r.get("geometrie"))
    pt = _safe_dict(_first_non_none(r.get("petite_tete"), geo.get("petite_tete"), {}))
    gt = _safe_dict(_first_non_none(r.get("grande_tete"), geo.get("grande_tete"), {}))
    fut = _safe_dict(_first_non_none(r.get("fut"), geo.get("fut"), {}))
    efforts = _safe_dict(r.get("efforts"))
    pressions = _safe_dict(r.get("pressions_contact"))
    contraintes = _safe_dict(r.get("contraintes"))

    return {
        "longueur_bielle_m": _safe_float(ent.get("longueur_bielle_m")),
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
        "section_fut_m2": _first_finite(
            fut.get("section_m2"),
            geo.get("section_fut_m2"),
            ent.get("section_fut_m2"),
        ),
        "inertie_min_fut_m4": _first_finite(
            fut.get("inertie_min_fut_m4"),
            ent.get("inertie_min_fut_m4"),
        ),
        "force_axiale_max_N": _first_finite(
            efforts.get("force_axiale_max_N"),
            efforts.get("force_axiale_max_tension_N"),
            geo.get("force_axiale_max_N"),
        ),
        "force_axiale_min_N": _first_finite(
            efforts.get("force_axiale_min_N"),
            efforts.get("force_axiale_max_compression_N"),
        ),
        "pression_petite_tete_pa": _first_finite(
            pressions.get("pression_petite_tete_pa"),
            pt.get("pression_moyenne_pa"),
        ),
        "pression_grande_tete_pa": _first_finite(
            pressions.get("pression_grande_tete_pa"),
            gt.get("pression_moyenne_pa"),
        ),
        "sigma_vm_pa": _first_finite(
            contraintes.get("sigma_von_mises_pa"),
            contraintes.get("sigma_eq_pa"),
        ),
    }


def _extract_arbre_piston_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    contraintes = _safe_dict(r.get("contraintes"))
    cao = _safe_dict(r.get("cao"))
    dim = _safe_dict(r.get("dimensionnement_evide"))
    ru = _safe_dict(dim.get("resultat_unique"))
    taraudages = _safe_dict(r.get("taraudages"))

    return {
        "diametre_fut_ext_m": _first_finite(
            geo.get("diametre_fut_central_m"),
            geo.get("diametre_exterieur_fut_m"),
            geo.get("diametre_exterieur_fut_min_vm_m"),
            ru.get("Do_m"),
        ),
        "diametre_fut_int_m": _first_finite(
            geo.get("diametre_interieur_fut_m"),
            geo.get("diametre_interieur_fut_associe_vm_m"),
            ru.get("Di_m"),
        ),
        "diametre_portee_coussinet_m": _first_finite(
            geo.get("diametre_portee_coussinet_m"),
            r.get("diametre_portee_coussinet_m"),
        ),
        "longueur_coussinet_m": _first_finite(
            geo.get("longueur_coussinet_m"),
            r.get("longueur_coussinet_m"),
        ),
        "sigma_vm_pa": _safe_float(contraintes.get("sigma_von_mises_pa")),
        "sigma_allow_pa": _safe_float(contraintes.get("sigma_allow_pa")),
        "marge_sigma_vm": _safe_float(contraintes.get("marge_sigma_vm")),
        "P_crit_flambage_N": _first_finite(
            _safe_dict(r.get("flambage")).get("P_crit_N"),
            _safe_dict(r.get("flambage")).get("P_crit_flambage_N"),
        ),
        "effort_axial_max_taraudage_N": _max_finis([
            taraudages.get("effort_axial_sur_taraudage_gauche_N"),
            taraudages.get("effort_axial_sur_taraudage_droit_N"),
        ]),
        "cao": cao,
    }


def _extract_arbre_vilebrequin_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    cine = _safe_dict(r.get("cinematique"))
    geo = _safe_dict(r.get("geometrie"))
    roult = _safe_dict(r.get("roulement"))
    bman = _safe_dict(r.get("bielle_maneton"))
    press = _safe_dict(r.get("pressions_contact"))
    contraintes = _safe_dict(r.get("contraintes"))

    return {
        "course_m": _first_finite(cine.get("course_m"), geo.get("course_m")),
        "rpm": _safe_float(cine.get("rpm")),
        "couple_max_Nm": _safe_float(cine.get("couple_max_Nm")),
        "force_bielle_effective_N": _first_finite(
            cine.get("force_bielle_effective_N"),
            bman.get("force_bielle_effective_N"),
        ),
        "diametre_journal_principal_m": _first_finite(
            geo.get("diametre_journal_principal_m"),
            roult.get("journal_principal"),
            roult.get("d_interieur_reference_m"),
        ),
        "diametre_maneton_m": _first_finite(
            geo.get("diametre_maneton_m"),
            bman.get("diametre_maneton_m"),
            roult.get("d_interieur_requis_maneton_m"),
        ),
        "largeur_portee_journal_m": _first_finite(
            geo.get("largeur_portee_journal_m"),
            roult.get("B_largeur_reference_m"),
        ),
        "largeur_portee_maneton_m": _first_finite(
            geo.get("largeur_portee_maneton_m"),
            bman.get("largeur_portee_m"),
            roult.get("B_largeur_requise_m"),
        ),
        "pression_moyenne_journal_pa": _first_finite(
            press.get("pression_moyenne_journal_pa"),
            press.get("pression_moyenne_pa"),
        ),
        "pression_moyenne_maneton_pa": _first_finite(
            press.get("pression_moyenne_maneton_pa"),
            bman.get("pression_moyenne_pa"),
        ),
        "sigma_vm_pa": _safe_float(contraintes.get("sigma_von_mises_pa")),
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
        "marge_von_mises": _safe_float(contraintes.get("marge_von_mises")),
        "masse_totale_kg": _safe_float(masses.get("masse_totale_kg")),
        "I_polaire_kg_m2": _safe_float(inerties.get("I_polaire_totale_kg_m2")),
        "k_torsion_Nm_rad": _first_finite(
            raideur.get("raideur_torsion_Nm_rad"),
            raideur.get("k_Nm_par_rad"),
        ),
    }


def _extract_roulement_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    dims = _safe_dict(r.get("dimensions_requises"))
    geo_est = _safe_dict(r.get("geometrie_estimee"))
    ref = _safe_dict(r.get("dimensions_reference"))
    roulement = _safe_dict(r.get("roulement"))
    charges = _safe_dict(r.get("charges"))
    vie = _safe_dict(r.get("vie"))
    exigences = _safe_dict(r.get("exigences"))

    return {
        "d_interieur_requis_m": _first_finite(
            dims.get("d_interieur_requis_m"),
            dims.get("diametre_interieur_requis_m"),
            exigences.get("d_interieur_requis_m"),
            ref.get("d_interieur_m"),
        ),
        "B_requise_m": _first_finite(
            dims.get("B_requise_m"),
            dims.get("largeur_requise_m"),
            exigences.get("B_requise_m"),
            ref.get("B_largeur_m"),
        ),
        "D_exterieur_m": _first_finite(
            geo_est.get("D_exterieur_estime_m"),
            ref.get("D_exterieur_m"),
            ref.get("D_exterieur_reference_m"),
        ),
        "C_requis_N": _first_finite(vie.get("C_requis_N"), exigences.get("C_requis_N")),
        "C0_requis_N": _first_finite(vie.get("C0_requis_N"), exigences.get("C0_requis_N")),
        "charge_equivalente_N": _first_finite(
            charges.get("force_radiale_equivalente_N"),
            charges.get("charge_equivalente_P_N"),
        ),
        "charge_statique_N": _first_finite(
            charges.get("force_resultante_max_N"),
            charges.get("charge_statique_P0_N"),
        ),
        "rpm": _first_finite(
            roulement.get("rpm"),
            charges.get("rpm"),
            exigences.get("rpm"),
        ),
    }


def _extract_coussinet_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    tribo = _safe_dict(r.get("tribologie"))
    press = _safe_dict(r.get("pressions"))
    pv = _safe_dict(r.get("pv"))
    frott = _safe_dict(r.get("frottement"))
    hydro = _safe_dict(r.get("hydrodynamique"))
    cao = _safe_dict(r.get("cao"))

    return {
        "diametre_interieur_m": _first_finite(
            cao.get("diametre_interieur_m"),
            geo.get("diametre_portee_m"),
            geo.get("diametre_interieur_m"),
        ),
        "diametre_exterieur_m": _first_finite(
            cao.get("diametre_exterieur_m"),
            geo.get("diametre_exterieur_m"),
        ),
        "longueur_m": _first_finite(
            cao.get("longueur_m"),
            geo.get("longueur_coussinet_m"),
            geo.get("longueur_m"),
        ),
        "jeu_radial_m": _safe_float(geo.get("jeu_radial_m")),
        "pression_proj_pa": _first_finite(
            tribo.get("pression_proj_pa"),
            press.get("pression_proj_pa"),
        ),
        "PV": _first_finite(
            tribo.get("PV"),
            pv.get("PV"),
        ),
        "P_frottement_W": _first_finite(
            tribo.get("P_frottement_W"),
            frott.get("P_frottement_W"),
        ),
        "sommerfeld": _first_finite(
            hydro.get("nombre_sommerfeld"),
            hydro.get("Sommerfeld"),
        ),
    }


def _extract_couvercle_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    geo = _safe_dict(r.get("geometrie"))
    charges = _safe_dict(r.get("charges"))
    thermique = _safe_dict(r.get("thermique"))
    assemblage = _safe_dict(r.get("assemblage"))
    deformation = _safe_dict(r.get("deformations"))
    fabrication = _safe_dict(r.get("fabrication"))
    verif = _safe_dict(r.get("verifications"))

    return {
        "epaisseur_m": _first_finite(
            geo.get("epaisseur_m"),
            geo.get("epaisseur_retenue_m"),
        ),
        "diametre_ouverture_m": _first_finite(
            geo.get("diametre_ouverture_m"),
            charges.get("diametre_ouverture_m"),
        ),
        "diametre_bride_externe_m": _first_finite(
            geo.get("diametre_bride_externe_m"),
            assemblage.get("diametre_bride_externe_m"),
        ),
        "force_separation_N": _first_finite(
            assemblage.get("force_separation_N"),
            charges.get("force_separation_N"),
        ),
        "force_joint_N": _first_finite(
            assemblage.get("force_joint_N"),
            charges.get("force_joint_N"),
        ),
        "precharge_par_vis_N": _first_finite(
            assemblage.get("force_precharge_par_vis_N"),
            verif.get("force_precharge_par_vis_N"),
        ),
        "precharge_totale_N": _first_finite(
            assemblage.get("force_precharge_totale_N"),
            verif.get("force_precharge_totale_N"),
        ),
        "R_th_K_W": _first_finite(
            thermique.get("resistance_thermique_K_W"),
            thermique.get("R_th_K_W"),
        ),
        "fleche_max_m": _first_finite(
            deformation.get("fleche_max_m"),
            deformation.get("deformation_max_m"),
        ),
        "rugosite_face_joint_ra_um": _safe_float(fabrication.get("rugosite_face_joint_ra_um")),
    }


def _extract_vis_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    ent = _safe_dict(r.get("entrees"))
    selection = _safe_dict(r.get("selection"))
    geo = _safe_dict(r.get("geometrie"))
    implant = _safe_dict(r.get("implantation"))
    verif = _safe_dict(r.get("verifications"))
    taraud = _safe_dict(r.get("taraudages"))

    return {
        "nb_vis": _safe_int(_first_non_none(selection.get("nb_vis"), implant.get("nb_vis"), ent.get("nb_vis_impose"))),
        "diametre_nominal_m": _first_finite(
            selection.get("diametre_nominal_m"),
            geo.get("diametre_nominal_m"),
            ent.get("d_vis_impose_mm") / 1000.0 if _is_finite(ent.get("d_vis_impose_mm")) else None,
        ),
        "filetage": _first_non_none(selection.get("filetage"), geo.get("filetage")),
        "F_par_vis_N": _first_finite(
            selection.get("F_par_vis_N"),
            verif.get("F_par_vis_N"),
            verif.get("force_dimensionnement_par_vis_N"),
        ),
        "Re_vis_pa": _first_finite(
            selection.get("Re_vis_pa"),
            verif.get("Re_vis_pa"),
            verif.get("limite_elastique_vis_pa"),
        ),
        "sigma_allow_vis_pa": _first_finite(
            verif.get("sigma_allow_vis_pa"),
            verif.get("sigma_allow_pa"),
            verif.get("sigma_allow_vis_pa"),
        ),
        "longueur_vis_min_m": _first_finite(
            selection.get("longueur_vis_min_m"),
            verif.get("longueur_vis_min_m"),
        ),
        "diametre_trou_passant_m": _first_finite(
            geo.get("diametre_trou_passant_m"),
            implant.get("diametre_trou_passant_m"),
        ),
        "diametre_percage_avant_taraudage_m": _first_finite(
            taraud.get("diametre_percage_avant_taraudage_m"),
            taraud.get("diametre_percage_avant_taraudage_mm") / 1000.0 if _is_finite(taraud.get("diametre_percage_avant_taraudage_mm")) else None,
        ),
        "diametre_cercle_percage_m": _first_finite(
            implant.get("diametre_cercle_percage_m"),
            ent.get("diametre_cercle_percage_m"),
        ),
    }


def _extract_arbre_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    ent = _safe_dict(r.get("entrees"))
    dim = _safe_dict(r.get("dimensionnements"))
    contr = _safe_dict(r.get("contraintes"))
    clav = _safe_dict(r.get("clavette"))
    inter = _safe_dict(r.get("interfaces"))
    cao = _safe_dict(r.get("cao"))

    return {
        "diametre_arbre_m": _first_finite(
            dim.get("diametre_arbre_m"),
            ent.get("diametre_arbre_m"),
            inter.get("diametre_nominal_arbre_m"),
        ),
        "diametre_passage_arbre_m": _first_finite(
            ent.get("diametre_passage_arbre_m"),
            inter.get("diametre_passage_arbre_m"),
        ),
        "largeur_portee_roulement_m": _first_finite(
            inter.get("largeur_portee_roulement_m"),
            cao.get("largeur_portee_roulement_m"),
        ),
        "longueur_portee_clavette_disponible_m": _first_finite(
            ent.get("longueur_portee_clavette_disponible_m"),
            inter.get("longueur_portee_clavette_disponible_m"),
        ),
        "clavette_b_m": _first_finite(
            clav.get("b_m"),
            ent.get("clavette_b_m"),
        ),
        "clavette_h_m": _first_finite(
            clav.get("h_m"),
            ent.get("clavette_h_m"),
        ),
        "tau_arbre_pa": _first_finite(
            contr.get("tau_max_pa"),
            contr.get("tau_torsion_pa"),
        ),
        "sigma_vm_pa": _safe_float(contr.get("sigma_von_mises_pa")),
    }


def _extract_clavette_metrics(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    r = _safe_dict(rep)
    if not r:
        return {}

    dims = _safe_dict(r.get("dimensions"))
    inter = _safe_dict(r.get("interfaces"))
    clav = _safe_dict(r.get("clavette"))
    verif = _safe_dict(r.get("verifications"))
    contr = _safe_dict(r.get("contraintes"))

    return {
        "b_m": _first_finite(
            dims.get("b_m"),
            clav.get("b_m"),
            inter.get("clavette_b_m"),
        ),
        "h_m": _first_finite(
            dims.get("h_m"),
            clav.get("h_m"),
            inter.get("clavette_h_m"),
        ),
        "longueur_m": _first_finite(
            dims.get("longueur_m"),
            clav.get("longueur_m"),
            inter.get("longueur_clavette_m"),
        ),
        "diametre_arbre_m": _first_finite(
            inter.get("diametre_arbre_m"),
            r.get("diametre_arbre_m"),
        ),
        "tau_max_pa": _first_finite(
            contr.get("tau_max_pa"),
            verif.get("tau_max_pa"),
        ),
        "sigma_appui_max_pa": _first_finite(
            contr.get("sigma_appui_max_pa"),
            verif.get("sigma_appui_max_pa"),
        ),
    }


# ============================================================
# Orchestrateur
# ============================================================

@dataclass
@dataclass
class OptimisationSysteme:
    """
    Orchestrateur inter-pièces.

    Il ne remplace pas les calculateurs de pièces :
    il vérifie leur cohérence mutuelle, recolle leurs interfaces
    et agrège les pertes déjà calculées.
    """

    systeme_complet: Optional[Any] = None
    moteur_thermique: Optional[Any] = None

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

    arbre: Optional[Any] = None
    clavette_arbre: Optional[Any] = None

    rapport_backend: Optional[Dict[str, Any]] = None
    rapports_pieces: Optional[Dict[str, Any]] = None
    analyses_composants: Optional[Dict[str, Any]] = None
    objets_serialises: Optional[Dict[str, Any]] = None
    inventaire: Optional[Dict[str, Any]] = None

    tolerance_relatif_forte: float = 0.02
    tolerance_relatif_standard: float = 0.05
    tolerance_relatif_lache: float = 0.10
    tolerance_interference_absolue_m: float = 1e-12

    @classmethod
    def depuis_rapport_backend(cls, rapport_backend: Optional[Dict[str, Any]]) -> "OptimisationSysteme":
        rapport = _safe_dict(rapport_backend)
        objets = _safe_dict(rapport.get("objets_serialises"))
        pieces = _safe_dict(objets.get("pieces"))
        composants = _safe_dict(objets.get("composants"))

        return cls(
            systeme_complet=rapport,
            moteur_thermique=composants.get("moteur_thermique"),
            cylindre=pieces.get("cylindre"),
            piston=pieces.get("piston"),
            joint_piston=pieces.get("joint_piston"),
            deplaceur=pieces.get("deplaceur"),
            joint_deplaceur=pieces.get("joint_deplaceur"),
            bielle=pieces.get("bielle"),
            arbre_piston=pieces.get("arbre_piston"),
            coussinet_arbre_piston=pieces.get("coussinet_arbre_piston"),
            arbre_vilebrequin=pieces.get("arbre_vilebrequin"),
            vilbrequin=pieces.get("vilbrequin"),
            roulement_aiguille_arbre=pieces.get("roulement_aiguille_arbre"),
            roulement_aiguille_arbre_vilebrequin=pieces.get("roulement_aiguille_arbre_vilebrequin"),
            couvercle_cylindre=pieces.get("couvercle_cylindre"),
            vis_couvercle_cylindre=pieces.get("vis_couvercle_cylindre"),
            arbre=pieces.get("arbre"),
            clavette_arbre=pieces.get("clavette_arbre"),
            rapport_backend=rapport,
            rapports_pieces=_safe_dict(rapport.get("rapports_pieces")),
            analyses_composants=_safe_dict(rapport.get("analyses_composants")),
            objets_serialises=objets,
            inventaire=_safe_dict(rapport.get("inventaire")),
        )

    def _piece_report(self, piece_name: str, piece_obj: Any) -> Optional[Dict[str, Any]]:
        report = _resolve_report_mapping(piece_obj)
        if report is not None:
            return report

        backend_piece_reports = _safe_dict(self.rapports_pieces)
        if isinstance(backend_piece_reports.get(piece_name), dict):
            return backend_piece_reports[piece_name]

        rapport = _safe_dict(self.rapport_backend)
        backend_piece_reports = _safe_dict(rapport.get("rapports_pieces"))
        if isinstance(backend_piece_reports.get(piece_name), dict):
            return backend_piece_reports[piece_name]

        inv_piece = _safe_dict(_safe_dict(_safe_dict(rapport.get("inventaire")).get("pieces")).get(piece_name))
        if isinstance(inv_piece.get("rapport"), dict):
            return inv_piece.get("rapport")

        return None

    def _component_report(self, component_name: str, component_obj: Any = None) -> Optional[Dict[str, Any]]:
        report = _resolve_report_mapping(component_obj)
        if report is not None:
            return report

        analyses = _safe_dict(self.analyses_composants)
        aliases = {
            "moteur_thermique": (
                "moteur_thermique",
                "moteur_thermique_geometrie",
                "moteur_thermique_cycle",
                "moteur_thermique_point",
                "moteur_thermique_bilan_carburant",
                "construction_moteur_thermique",
            ),
            "alternateur": ("alternateur", "alternateur_bus_dc"),
            "batterie": ("batterie", "batterie_dimensionnement"),
            "boite_crabots": ("boite_crabots", "boite_point", "boite_chaine"),
            "architecture": ("architecture",),
            "electronique_puissance": ("electronique_puissance",),
        }
        for alias in aliases.get(component_name, (component_name,)):
            if isinstance(analyses.get(alias), dict):
                return analyses[alias]

        rapport = _safe_dict(self.rapport_backend)
        analyses = _safe_dict(rapport.get("analyses_composants"))
        for alias in aliases.get(component_name, (component_name,)):
            if isinstance(analyses.get(alias), dict):
                return analyses[alias]

        return None

    # --------------------------------------------------------
    # Analyse globale
    # --------------------------------------------------------
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

        # ----------------------------------------------------
        # 1) Récupération des rapports
        # ----------------------------------------------------
        rep_sys = _resolve_report_mapping(self.systeme_complet)
        if rep_sys is None:
            rep_sys = _safe_dict(self.rapport_backend)

        rep_mt = self._component_report("moteur_thermique", self.moteur_thermique)
        if rep_mt is None and self.systeme_complet is not None:
            rep_mt = _resolve_report_mapping(getattr(self.systeme_complet, "moteur_thermique", None))

        rep_cyl = self._piece_report("cylindre", self.cylindre)
        rep_pis = self._piece_report("piston", self.piston)
        rep_jp = self._piece_report("joint_piston", self.joint_piston)
        rep_dep = self._piece_report("deplaceur", self.deplaceur)
        rep_jd = self._piece_report("joint_deplaceur", self.joint_deplaceur)
        rep_bie = self._piece_report("bielle", self.bielle)
        rep_ap = self._piece_report("arbre_piston", self.arbre_piston)
        rep_cous = self._piece_report("coussinet_arbre_piston", self.coussinet_arbre_piston)
        rep_av = self._piece_report("arbre_vilebrequin", self.arbre_vilebrequin)
        rep_vb = self._piece_report("vilbrequin", self.vilbrequin)
        rep_raa = self._piece_report("roulement_aiguille_arbre", self.roulement_aiguille_arbre)
        rep_raav = self._piece_report("roulement_aiguille_arbre_vilebrequin", self.roulement_aiguille_arbre_vilebrequin)
        rep_cov = self._piece_report("couvercle_cylindre", self.couvercle_cylindre)
        rep_vis = self._piece_report("vis_couvercle_cylindre", self.vis_couvercle_cylindre)
        rep_arb = self._piece_report("arbre", self.arbre)
        rep_clav = self._piece_report("clavette_arbre", self.clavette_arbre)

        rapport["rapports_sources"] = {
            "systeme_complet": rep_sys is not None,
            "moteur_thermique": rep_mt is not None,
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
            "arbre": rep_arb is not None,
            "clavette_arbre": rep_clav is not None,
        }

        # ----------------------------------------------------
        # 2) Extraction normalisée
        # ----------------------------------------------------
        ext_sys = _extract_systeme_metrics(rep_sys)
        ext_cyl = _extract_cylindre_metrics(rep_cyl)
        ext_pis = _extract_piston_metrics(rep_pis)
        ext_jp = _extract_joint_piston_metrics(rep_jp)
        ext_dep = _extract_deplaceur_metrics(rep_dep)
        ext_jd = _extract_joint_deplaceur_metrics(rep_jd)
        ext_bie = _extract_bielle_metrics(rep_bie)
        ext_ap = _extract_arbre_piston_metrics(rep_ap)
        ext_cous = _extract_coussinet_metrics(rep_cous)
        ext_av = _extract_arbre_vilebrequin_metrics(rep_av)
        ext_vb = _extract_vilebrequin_metrics(rep_vb)
        ext_raa = _extract_roulement_metrics(rep_raa)
        ext_raav = _extract_roulement_metrics(rep_raav)
        ext_cov = _extract_couvercle_metrics(rep_cov)
        ext_vis = _extract_vis_metrics(rep_vis)
        ext_arb = _extract_arbre_metrics(rep_arb)
        ext_clav = _extract_clavette_metrics(rep_clav)

        # Le moteur thermique dédié est ramené au même format que le système complet si possible.
        ext_mt = {
            "alesage_m": _first_finite(
                _dig(rep_mt, "synthese", "moteur_thermique", "alesage_m"),
                _dig(rep_mt, "entrees", "alesage_m"),
                _dig(rep_mt, "geometrie", "alesage_m"),
            ),
            "course_m": _first_finite(
                _dig(rep_mt, "synthese", "moteur_thermique", "course_m"),
                _dig(rep_mt, "entrees", "course_m"),
                _dig(rep_mt, "geometrie", "course_m"),
            ),
            "nb_cyl": _safe_int(_first_non_none(
                _dig(rep_mt, "synthese", "moteur_thermique", "nombre_cylindres"),
                _dig(rep_mt, "entrees", "nombre_cylindres"),
            )),
            "pme_pa": _first_finite(
                _dig(rep_mt, "synthese", "moteur_thermique", "pme_pa"),
                _dig(rep_mt, "entrees", "pme_pa"),
            ),
            "pression_max_pa": _first_finite(
                _dig(rep_mt, "synthese", "moteur_thermique", "pression_max_pa"),
                _dig(rep_mt, "entrees", "pression_max_pa"),
            ),
            "architecture": _first_non_none(
                _dig(rep_mt, "synthese", "moteur_thermique", "architecture"),
                _dig(rep_mt, "entrees", "architecture"),
            ),
        }

        rapport["extractions"] = {
            "systeme_complet": ext_sys,
            "moteur_thermique": ext_mt,
            "cylindre": ext_cyl,
            "piston": ext_pis,
            "joint_piston": ext_jp,
            "deplaceur": ext_dep,
            "joint_deplaceur": ext_jd,
            "bielle": ext_bie,
            "arbre_piston": ext_ap,
            "coussinet_arbre_piston": ext_cous,
            "arbre_vilebrequin": ext_av,
            "vilbrequin": ext_vb,
            "roulement_aiguille_arbre": ext_raa,
            "roulement_aiguille_arbre_vilebrequin": ext_raav,
            "couvercle_cylindre": ext_cov,
            "vis_couvercle_cylindre": ext_vis,
            "arbre": ext_arb,
            "clavette_arbre": ext_clav,
        }

        coh = rapport["coherences"]

        # ----------------------------------------------------
        # 3) Cohérences moteur / cylindre / piston
        # ----------------------------------------------------
        D_cyl = _first_finite(ext_cyl.get("alesage_m"), ext_sys.get("alesage_m"), ext_mt.get("alesage_m"))
        D_pis = _safe_float(ext_pis.get("diametre_exterieur_m"))

        if D_cyl is not None and D_pis is not None:
            jeu_rad = 0.5 * (D_cyl - D_pis)
            ok = jeu_rad >= -self.tolerance_interference_absolue_m
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
                "Nécessite l'alésage cylindre et le diamètre piston.",
            )

        # ----------------------------------------------------
        # 3.2 Course globale
        # ----------------------------------------------------
        course_ref = _first_finite(
            ext_sys.get("course_m"),
            ext_mt.get("course_m"),
            ext_cyl.get("course_m"),
            ext_av.get("course_m"),
            ext_vb.get("course_m"),
        )
        if course_ref is not None:
            comp: List[Dict[str, Any]] = []
            for nom, val in (
                ("systeme_complet", ext_sys.get("course_m")),
                ("moteur_thermique", ext_mt.get("course_m")),
                ("cylindre", ext_cyl.get("course_m")),
                ("arbre_vilebrequin", ext_av.get("course_m")),
                ("vilbrequin", ext_vb.get("course_m")),
            ):
                v = _safe_float(val)
                if v is not None:
                    comp.append({
                        "source": nom,
                        "course_m": v,
                        "ecart_relatif": _ecart_relatif(v, course_ref),
                    })

            coh["course_globale"] = {
                "course_reference_m": course_ref,
                "comparaison": comp,
                "coherent": all(
                    (it["ecart_relatif"] is None or it["ecart_relatif"] <= self.tolerance_relatif_standard)
                    for it in comp
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

        # ----------------------------------------------------
        # 3.3 Cohérence moteur : alesage / course / nombre de cylindres
        # ----------------------------------------------------
        bore_ref = _first_finite(ext_sys.get("alesage_m"), ext_mt.get("alesage_m"), ext_cyl.get("alesage_m"))
        if bore_ref is not None:
            comp_bore: List[Dict[str, Any]] = []
            for nom, val in (
                ("systeme_complet", ext_sys.get("alesage_m")),
                ("moteur_thermique", ext_mt.get("alesage_m")),
                ("cylindre", ext_cyl.get("alesage_m")),
            ):
                v = _safe_float(val)
                if v is not None:
                    comp_bore.append({
                        "source": nom,
                        "alesage_m": v,
                        "ecart_relatif": _ecart_relatif(v, bore_ref),
                    })
            coh["alesage_global"] = {
                "alesage_reference_m": bore_ref,
                "comparaison": comp_bore,
                "coherent": all(
                    (it["ecart_relatif"] is None or it["ecart_relatif"] <= self.tolerance_relatif_standard)
                    for it in comp_bore
                ),
            }
            if not coh["alesage_global"]["coherent"]:
                _push_warning(
                    rapport,
                    "coherence_alesage",
                    "alesage_global",
                    "Les alésages ne sont pas alignés entre moteur, système et cylindre.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "alesage global",
                "Aucun alésage exploitable n'a été trouvé.",
            )

        # ----------------------------------------------------
        # 3.4 Arbre piston / petite tête / coussinet
        # ----------------------------------------------------
        d_ap = _first_finite(ext_ap.get("diametre_portee_coussinet_m"), ext_ap.get("diametre_fut_ext_m"))
        d_pt = _safe_float(ext_bie.get("diametre_axe_piston_m"))
        d_cous = _safe_float(ext_cous.get("diametre_interieur_m"))

        if d_ap is not None:
            coh_ap = {
                "diametre_reference_m": d_ap,
                "diametre_arbre_piston_m": d_ap,
                "diametre_petite_tete_m": d_pt,
                "diametre_coussinet_m": d_cous,
                "ecart_rel_petite_tete": _ecart_relatif(d_ap, d_pt),
                "ecart_rel_coussinet": _ecart_relatif(d_ap, d_cous),
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

        # ----------------------------------------------------
        # 3.5 Maneton / grande tête / roulement maneton / arbres
        # ----------------------------------------------------
        d_maneton_ref = _first_finite(
            ext_bie.get("diametre_maneton_m"),
            ext_av.get("diametre_maneton_m"),
            ext_vb.get("diametre_maneton_m"),
            ext_raav.get("d_interieur_requis_m"),
        )

        if d_maneton_ref is not None:
            cmp_maneton: List[Dict[str, Any]] = []
            for nom, v in (
                ("bielle", ext_bie.get("diametre_maneton_m")),
                ("arbre_vilebrequin", ext_av.get("diametre_maneton_m")),
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

        # ----------------------------------------------------
        # 3.6 Journal principal / roulement arbre / arbre
        # ----------------------------------------------------
        d_journal_ref = _first_finite(
            ext_av.get("diametre_journal_principal_m"),
            ext_vb.get("diametre_journal_principal_m"),
            ext_raa.get("d_interieur_requis_m"),
            ext_arb.get("diametre_arbre_m"),
        )
        if d_journal_ref is not None:
            cmp_journal: List[Dict[str, Any]] = []
            for nom, v in (
                ("arbre_vilebrequin", ext_av.get("diametre_journal_principal_m")),
                ("vilbrequin", ext_vb.get("diametre_journal_principal_m")),
                ("roulement_aiguille_arbre", ext_raa.get("d_interieur_requis_m")),
                ("arbre", ext_arb.get("diametre_arbre_m")),
            ):
                vv = _safe_float(v)
                if vv is not None:
                    cmp_journal.append({
                        "source": nom,
                        "diametre_m": vv,
                        "ecart_relatif": _ecart_relatif(vv, d_journal_ref),
                    })
            coh["journal_principal_interfaces"] = {
                "diametre_reference_m": d_journal_ref,
                "comparaison": cmp_journal,
                "coherent": all(
                    (it["ecart_relatif"] is None or it["ecart_relatif"] <= self.tolerance_relatif_standard)
                    for it in cmp_journal
                ),
            }
            if not coh["journal_principal_interfaces"]["coherent"]:
                _push_warning(
                    rapport,
                    "interfaces",
                    "journal_principal",
                    "Diamètres journal principal / arbre / roulement non cohérents.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "interface journal principal",
                "Aucun diamètre de journal principal exploitable.",
            )

        # ----------------------------------------------------
        # 3.7 Déplaceur / cylindre
        # ----------------------------------------------------
        d_dep = _safe_float(ext_dep.get("diametre_exterieur_m"))
        if D_cyl is not None and d_dep is not None:
            jeu_dep = 0.5 * (D_cyl - d_dep)
            coh["deplaceur_vs_cylindre"] = {
                "alesage_cylindre_m": D_cyl,
                "diametre_deplaceur_m": d_dep,
                "jeu_radial_calcule_m": jeu_dep,
                "jeu_radial_piece_m": ext_dep.get("jeu_radial_m"),
                "coherent": jeu_dep >= -self.tolerance_interference_absolue_m,
            }
            if coh["deplaceur_vs_cylindre"]["coherent"] is False:
                _push_warning(
                    rapport,
                    "interferences",
                    "deplaceur_vs_cylindre",
                    "Le déplaceur interfère avec le cylindre.",
                )
        elif self.deplaceur is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "coherence deplaceur/cylindre",
                "Nécessite alésage cylindre et diamètre déplaceur.",
            )

        # ----------------------------------------------------
        # 3.8 Joint deplaceur / déplaceur
        # ----------------------------------------------------
        d_fond_jd = _safe_float(ext_jd.get("diametre_fond_gorge_m"))
        d_dep_ref = _first_finite(ext_jd.get("diametre_deplaceur_m"), ext_dep.get("diametre_exterieur_m"))
        if d_dep_ref is not None and d_fond_jd is not None:
            coh["joint_deplaceur_vs_deplaceur"] = {
                "diametre_deplaceur_m": d_dep_ref,
                "diametre_fond_gorge_m": d_fond_jd,
                "profondeur_gorge_m": ext_jd.get("profondeur_gorge_m"),
                "coherent": d_fond_jd < d_dep_ref,
            }
            if coh["joint_deplaceur_vs_deplaceur"]["coherent"] is False:
                _push_warning(
                    rapport,
                    "interfaces",
                    "joint_deplaceur_vs_deplaceur",
                    "Le diamètre de fond de gorge du joint déplaceur n'est pas inférieur au diamètre support.",
                )
        elif self.joint_deplaceur is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "interface joint deplaceur",
                "Diamètre support ou fond de gorge introuvable.",
            )

        # ----------------------------------------------------
        # 3.9 Joint piston / piston
        # ----------------------------------------------------
        d_fond_jp = _safe_float(ext_jp.get("diametre_fond_gorge_m"))
        if d_fond_jp is not None and D_pis is not None:
            coh["joint_piston_vs_piston"] = {
                "diametre_piston_m": D_pis,
                "diametre_fond_gorge_m": d_fond_jp,
                "profondeur_gorge_m": ext_jp.get("profondeur_gorge_m"),
                "largeur_gorge_m": ext_jp.get("largeur_gorge_m"),
                "coherent": d_fond_jp < D_pis,
            }
            if coh["joint_piston_vs_piston"]["coherent"] is False:
                _push_warning(
                    rapport,
                    "interfaces",
                    "joint_piston_vs_piston",
                    "Le diamètre de fond de gorge du joint piston n'est pas inférieur au diamètre piston.",
                )

        # ----------------------------------------------------
        # 3.10 Fermeture cylindre / couvercle / vis
        # ----------------------------------------------------
        pmax_ref = _first_finite(ext_cyl.get("pression_max_pa"), ext_sys.get("pression_max_pa"), ext_mt.get("pression_max_pa"), ext_sys.get("pme_pa"))
        if pmax_ref is not None:
            F_sep = _first_finite(
                ext_cov.get("force_separation_N"),
                ext_cyl.get("force_separation_N"),
            )
            F_pre_cov = _first_finite(
                ext_cov.get("precharge_totale_N"),
                ext_cyl.get("precharge_totale_requise_N"),
            )
            nb_vis = _safe_int(ext_vis.get("nb_vis"))
            F_par_vis = _safe_float(ext_vis.get("F_par_vis_N"))
            F_pre_vis_total = (float(nb_vis) * float(F_par_vis)) if (nb_vis is not None and F_par_vis is not None) else None

            coherent_cov = None if (F_sep is None or F_pre_cov is None) else (F_pre_cov >= F_sep)
            coherent_vis = None if (F_sep is None or F_pre_vis_total is None) else (F_pre_vis_total >= F_sep)

            coh["fermeture_cylindre"] = {
                "pression_reference_pa": pmax_ref,
                "force_separation_N": F_sep,
                "precharge_totale_couvercle_N": F_pre_cov,
                "precharge_totale_vis_N": F_pre_vis_total,
                "F_par_vis_N": F_par_vis,
                "nb_vis": nb_vis,
                "coherent_couvercle": coherent_cov,
                "coherent_vis": coherent_vis,
                "coherent_global": (coherent_cov is not False and coherent_vis is not False),
            }

            if coherent_cov is False:
                _push_warning(
                    rapport,
                    "assemblage",
                    "couvercle_precharge",
                    "La précharge totale côté couvercle est inférieure à la force de séparation.",
                )
            if coherent_vis is False:
                _push_warning(
                    rapport,
                    "assemblage",
                    "vis_precharge",
                    "La capacité globale des vis est inférieure à la force de séparation.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "fermeture cylindre",
                "Aucune pression de référence exploitable pour l'assemblage.",
            )

        # ----------------------------------------------------
        # 3.11 Roulements : vitesse et charge
        # ----------------------------------------------------
        for nom, ext_roul in (
            ("roulement_aiguille_arbre", ext_raa),
            ("roulement_aiguille_arbre_vilebrequin", ext_raav),
        ):
            info = {
                "d_interieur_requis_m": ext_roul.get("d_interieur_requis_m"),
                "B_requise_m": ext_roul.get("B_requise_m"),
                "C_requis_N": ext_roul.get("C_requis_N"),
                "C0_requis_N": ext_roul.get("C0_requis_N"),
                "charge_equivalente_N": ext_roul.get("charge_equivalente_N"),
                "rpm": ext_roul.get("rpm"),
                "dimensionnable": any(
                    ext_roul.get(k) is not None for k in ("d_interieur_requis_m", "B_requise_m", "C_requis_N", "C0_requis_N")
                ),
            }
            coh[nom] = info
            if not info["dimensionnable"] and (self.roulement_aiguille_arbre is not None or self.roulement_aiguille_arbre_vilebrequin is not None):
                _push_inconnue(
                    rapport,
                    "partielles",
                    nom,
                    "Données insuffisantes pour spécifier complètement le roulement.",
                )

        # ----------------------------------------------------
        # 3.12 Clavette / arbre
        # ----------------------------------------------------
        b_key = _first_finite(ext_clav.get("b_m"), ext_arb.get("clavette_b_m"))
        h_key = _first_finite(ext_clav.get("h_m"), ext_arb.get("clavette_h_m"))
        d_shaft_key = _first_finite(ext_clav.get("diametre_arbre_m"), ext_arb.get("diametre_arbre_m"))

        if any(v is not None for v in (b_key, h_key, d_shaft_key)):
            coh["clavette_arbre"] = {
                "diametre_arbre_m": d_shaft_key,
                "largeur_clavette_m": b_key,
                "hauteur_clavette_m": h_key,
                "tau_max_pa": ext_clav.get("tau_max_pa"),
                "sigma_appui_max_pa": ext_clav.get("sigma_appui_max_pa"),
                "coherent": True,
            }

        # ----------------------------------------------------
        # 3.13 Marges structurelles
        # ----------------------------------------------------
        marges: Dict[str, Any] = {}
        sigma_ap = _safe_float(ext_ap.get("sigma_vm_pa"))
        sigma_ap_allow = _safe_float(ext_ap.get("sigma_allow_pa"))
        if sigma_ap is not None and sigma_ap_allow is not None:
            ok = sigma_ap <= sigma_ap_allow
            marges["arbre_piston"] = {
                "sigma_vm_pa": sigma_ap,
                "sigma_allow_pa": sigma_ap_allow,
                "taux_utilisation": _ratio(sigma_ap, sigma_ap_allow),
                "coherent": ok,
            }
            if not ok:
                _push_warning(
                    rapport,
                    "rdm",
                    "arbre_piston",
                    "La contrainte équivalente de l'arbre de piston dépasse la contrainte admissible.",
                )

        sigma_av = _safe_float(ext_av.get("sigma_vm_pa"))
        sigma_vb = _safe_float(ext_vb.get("sigma_vm_pa"))
        if sigma_av is not None:
            marges["arbre_vilebrequin"] = {
                "sigma_vm_pa": sigma_av,
                "coherent": True,
            }
        if sigma_vb is not None:
            marges["vilbrequin"] = {
                "sigma_vm_pa": sigma_vb,
                "marge_von_mises": ext_vb.get("marge_von_mises"),
                "coherent": None if ext_vb.get("marge_von_mises") is None else (ext_vb.get("marge_von_mises") >= 0.0),
            }
            if marges["vilbrequin"]["coherent"] is False:
                _push_warning(
                    rapport,
                    "rdm",
                    "vilbrequin",
                    "Le vilbrequin dépasse sa marge de von Mises.",
                )
        coh["marges_structurales"] = marges

        # ----------------------------------------------------
        # 4) Pertes énergétiques agrégées
        # ----------------------------------------------------
        pertes_sys = _extract_pertes(rep_sys)
        pertes_mt = _extract_pertes(rep_mt)
        pertes_cyl = _extract_pertes(rep_cyl)
        pertes_pis = _extract_pertes(rep_pis)
        pertes_jp = _extract_pertes(rep_jp)
        pertes_dep = _extract_pertes(rep_dep)
        pertes_jd = _extract_pertes(rep_jd)
        pertes_cous = _extract_pertes(rep_cous)
        pertes_cov = _extract_pertes(rep_cov)

        P_frott_total = _somme_finis([
            pertes_sys.get("P_frottement_W"),
            pertes_mt.get("P_frottement_W"),
            pertes_cyl.get("P_frottement_W"),
            pertes_pis.get("P_frottement_W"),
            pertes_jp.get("P_frottement_W"),
            pertes_dep.get("P_frottement_W"),
            pertes_jd.get("P_frottement_W"),
            pertes_cous.get("P_frottement_W"),
            pertes_cov.get("P_frottement_W"),
            ext_jp.get("P_frottement_W"),
            ext_jd.get("P_frottement_W"),
            ext_cous.get("P_frottement_W"),
        ])

        Q_fuite_total = _somme_finis([
            pertes_sys.get("Q_fuite_m3_s"),
            pertes_mt.get("Q_fuite_m3_s"),
            pertes_cyl.get("Q_fuite_m3_s"),
            pertes_pis.get("Q_fuite_m3_s"),
            pertes_jp.get("Q_fuite_m3_s"),
            pertes_dep.get("Q_fuite_m3_s"),
            pertes_jd.get("Q_fuite_m3_s"),
            ext_pis.get("Q_fuite_m3_s"),
            ext_jp.get("Q_fuite_m3_s"),
            ext_dep.get("Q_fuite_m3_s"),
        ])

        mdot_fuite_total = _somme_finis([
            pertes_sys.get("m_dot_fuite_kg_s"),
            pertes_mt.get("m_dot_fuite_kg_s"),
            pertes_cyl.get("m_dot_fuite_kg_s"),
            pertes_pis.get("m_dot_fuite_kg_s"),
            pertes_jp.get("m_dot_fuite_kg_s"),
            pertes_dep.get("m_dot_fuite_kg_s"),
            pertes_jd.get("m_dot_fuite_kg_s"),
        ])

        rapport["pertes"] = {
            "P_frottement_totale_W": P_frott_total,
            "Q_fuite_totale_m3_s": Q_fuite_total,
            "m_dot_fuite_total_kg_s": mdot_fuite_total,
            "detail": {
                "systeme_complet": pertes_sys,
                "moteur_thermique": pertes_mt,
                "cylindre": pertes_cyl,
                "piston": pertes_pis,
                "joint_piston": pertes_jp,
                "deplaceur": pertes_dep,
                "joint_deplaceur": pertes_jd,
                "coussinet_arbre_piston": pertes_cous,
                "couvercle_cylindre": pertes_cov,
            },
        }

        # ----------------------------------------------------
        # 5) Synthèse
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # 6) Actions explicites d'optimisation
        # ----------------------------------------------------
        if ext_jp.get("P_frottement_W") is not None:
            rapport["actions"].append({
                "cible": "joint_piston",
                "champ": "geometrie_gorge",
                "valeur": "a_reexaminer",
                "strategie": "reduire_frottement_si_etancheite_suffisante",
            })

        if ext_jd.get("P_frottement_W") is not None:
            rapport["actions"].append({
                "cible": "joint_deplaceur",
                "champ": "geometrie_gorge",
                "valeur": "a_reexaminer",
                "strategie": "reduire_frottement_si_etancheite_suffisante",
            })

        if ext_cous.get("PV") is not None:
            rapport["actions"].append({
                "cible": "coussinet_arbre_piston",
                "champ": "PV",
                "valeur": ext_cous.get("PV"),
                "strategie": "augmenter_longueur_ou_reduire_charge_si_PV_trop_eleve",
            })

        if ext_cov.get("R_th_K_W") is not None:
            rapport["actions"].append({
                "cible": "couvercle_cylindre",
                "champ": "R_th_K_W",
                "valeur": ext_cov.get("R_th_K_W"),
                "strategie": "reduire_resistance_thermique_si_evacuation_chaud_insuffisante",
            })

        if ext_ap.get("marge_sigma_vm") is not None:
            rapport["actions"].append({
                "cible": "arbre_piston",
                "champ": "marge_sigma_vm",
                "valeur": ext_ap.get("marge_sigma_vm"),
                "strategie": "augmenter_section_si_marge_trop_faible",
            })

        if ext_vb.get("marge_von_mises") is not None:
            rapport["actions"].append({
                "cible": "vilbrequin",
                "champ": "marge_von_mises",
                "valeur": ext_vb.get("marge_von_mises"),
                "strategie": "augmenter_sections_ou_reduire_efforts_si_marge_negative",
            })

        if coh.get("fermeture_cylindre", {}).get("coherent_global") is False:
            rapport["actions"].append({
                "cible": "assemblage_cylindre",
                "champ": "precharge_totale",
                "valeur": coh["fermeture_cylindre"].get("force_separation_N"),
                "strategie": "augmenter_nb_vis_ou_diametre_vis_ou_precharge",
            })

        _append_note(
            rapport,
            "Ce module normalise des sorties hétérogènes et vérifie les interfaces sans inventer de dimensions manquantes."
        )
        _append_note(
            rapport,
            "Les corrections proposées sont prudentes : seulement des alignements directs sur des valeurs déjà calculées."
        )
        _append_note(
            rapport,
            "Le score global agrège cohérence géométrique et pénalité de pertes de frottement connues."
        )

        _dedup_rapport(rapport)
        return rapport

    # --------------------------------------------------------
    # Alias de compatibilité
    # --------------------------------------------------------
    def calculer(self, *, strict: bool = False) -> Dict[str, Any]:
        _ = strict
        return self.analyser()

    # --------------------------------------------------------
    # Proposition de corrections prudentes
    # --------------------------------------------------------
    def optimiser(self) -> Dict[str, Any]:
        rapport = self.analyser()

        objets_corriges: Dict[str, Any] = {
            "systeme_complet": self.systeme_complet,
            "moteur_thermique": self.moteur_thermique,
            "cylindre": self.cylindre,
            "piston": self.piston,
            "joint_piston": self.joint_piston,
            "deplaceur": self.deplaceur,
            "joint_deplaceur": self.joint_deplaceur,
            "bielle": self.bielle,
            "arbre_piston": self.arbre_piston,
            "coussinet_arbre_piston": self.coussinet_arbre_piston,
            "arbre_vilebrequin": self.arbre_vilebrequin,
            "vilbrequin": self.vilbrequin,
            "roulement_aiguille_arbre": self.roulement_aiguille_arbre,
            "roulement_aiguille_arbre_vilebrequin": self.roulement_aiguille_arbre_vilebrequin,
            "couvercle_cylindre": self.couvercle_cylindre,
            "vis_couvercle_cylindre": self.vis_couvercle_cylindre,
            "arbre": self.arbre,
            "clavette_arbre": self.clavette_arbre,
        }

        extr = _safe_dict(rapport.get("extractions"))
        coh = _safe_dict(rapport.get("coherences"))

        # ----------------------------------------------------
        # piston <- alesage cylindre si interférence
        # ----------------------------------------------------
        piston_vs_cyl = _safe_dict(coh.get("piston_vs_cylindre"))
        D_cyl = _safe_float(piston_vs_cyl.get("alesage_m"))
        D_pis = _safe_float(piston_vs_cyl.get("diametre_piston_m"))

        if piston_vs_cyl.get("coherent") is False and D_cyl is not None and self.piston is not None:
            if D_pis is not None:
                new_d = min(D_pis, D_cyl)
                objets_corriges["piston"] = _replace_if_possible(
                    self.piston,
                    diametre_exterieur_m=new_d,
                    alesage_nominal_m=D_cyl,
                )

        # ----------------------------------------------------
        # système complet / moteur thermique interne <- valeurs extraites
        # ----------------------------------------------------
        ext_sys = _safe_dict(extr.get("systeme_complet"))
        ext_mt = _safe_dict(extr.get("moteur_thermique"))

        bore = _first_finite(ext_sys.get("alesage_m"), ext_mt.get("alesage_m"))
        course = _first_finite(ext_sys.get("course_m"), ext_mt.get("course_m"))
        nb_cyl = _safe_int(_first_non_none(ext_sys.get("nb_cyl"), ext_mt.get("nb_cyl")))
        arch = _first_non_none(ext_sys.get("architecture"), ext_mt.get("architecture"))
        pmax = _first_finite(ext_sys.get("pression_max_pa"), ext_mt.get("pression_max_pa"))

        if self.moteur_thermique is not None:
            objets_corriges["moteur_thermique"] = _replace_if_possible(
                self.moteur_thermique,
                alesage_m=bore,
                course_m=course,
                nombre_cylindres=nb_cyl,
                architecture=arch,
                pression_max_pa=pmax,
            )

        if self.systeme_complet is not None and _is_dataclass_instance(self.systeme_complet):
            mt_obj = getattr(self.systeme_complet, "moteur_thermique", None)
            mt_new = _replace_if_possible(
                mt_obj,
                alesage_m=bore,
                course_m=course,
                nombre_cylindres=nb_cyl,
                architecture=arch,
                pression_max_pa=pmax,
            )
            objets_corriges["systeme_complet"] = _replace_if_possible(
                self.systeme_complet,
                moteur_thermique=mt_new,
            )

        # ----------------------------------------------------
        # arbre_piston <- portée coussinet si information disponible
        # ----------------------------------------------------
        ext_ap = _safe_dict(extr.get("arbre_piston"))
        ext_cous = _safe_dict(extr.get("coussinet_arbre_piston"))
        d_ref_ap = _first_finite(ext_ap.get("diametre_portee_coussinet_m"), ext_cous.get("diametre_interieur_m"))
        L_ref_ap = _first_finite(ext_ap.get("longueur_coussinet_m"), ext_cous.get("longueur_m"))

        if self.arbre_piston is not None:
            objets_corriges["arbre_piston"] = _replace_if_possible(
                self.arbre_piston,
                diametre_portee_coussinet_m=d_ref_ap,
                longueur_coussinet_m=L_ref_ap,
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
