from __future__ import annotations

import importlib
import math
from typing import Any, Dict, Mapping, Optional, Sequence


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_positive(name: str, value: Any) -> float:
    if not _is_finite(value):
        raise ValueError(f"{name} must be a finite number.")
    value = float(value)
    if value <= 0.0:
        raise ValueError(f"{name} must be > 0.")
    return value


def _safe_float(x: Any) -> Optional[float]:
    return float(x) if _is_finite(x) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return int(x)
    if _is_finite(x):
        xf = float(x)
        if abs(xf - round(xf)) < 1e-12:
            return int(round(xf))
    return None


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _merge_non_none(base: Optional[Mapping[str, Any]], extra: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    out = dict(base or {})
    for key, value in dict(extra or {}).items():
        if value is None:
            continue
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _merge_non_none(out.get(key), value)
        else:
            out[key] = value
    return out


def _get_nested(data: Any, *path: str) -> Any:
    cur = data
    for key in path:
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
        if cur is None:
            return None
    return cur


def _push_unknown(report: Dict[str, Any], category: str, name: str, reason: str) -> None:
    report.setdefault("inconnues", {}).setdefault(category, []).append(
        {"nom": str(name), "raison": str(reason)}
    )


def _append_note(report: Dict[str, Any], note: str) -> None:
    report.setdefault("notes_modele", []).append(str(note))


def _import_main_module() -> Any:
    return importlib.import_module("backend.main")


def _extract_indicators(payload: Mapping[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}

    def visit(node: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                visit(value, path + (str(key),))
            return
        if isinstance(node, (list, tuple)):
            for index, value in enumerate(node):
                visit(value, path + (str(index),))
            return
        if not _is_finite(node):
            return

        key_path = ".".join(path).lower()
        number = float(node)
        if "masse" in key_path and "masse_kg" not in values:
            values["masse_kg"] = number
        if "facteur_securite" in key_path and "facteur_securite" not in values:
            values["facteur_securite"] = number
        if "diametre" in key_path and key_path.endswith("_m") and "diametre_mm" not in values:
            values["diametre_mm"] = number * 1000.0
        elif "diametre" in key_path and key_path.endswith("_mm") and "diametre_mm" not in values:
            values["diametre_mm"] = number
        if "longueur" in key_path and key_path.endswith("_m") and "longueur_mm" not in values:
            values["longueur_mm"] = number * 1000.0
        elif "longueur" in key_path and key_path.endswith("_mm") and "longueur_mm" not in values:
            values["longueur_mm"] = number

    visit(payload)
    return values


def _build_piece_inventory(
    *,
    main_mod: Any,
    pieces: Mapping[str, Any],
    rapports_pieces: Mapping[str, Any],
    construction: Mapping[str, Any],
) -> Dict[str, Any]:
    inventory: Dict[str, Any] = {}
    for name, piece_obj in pieces.items():
        rapport_piece = rapports_pieces.get(name) if isinstance(rapports_pieces, Mapping) else None
        objet = main_mod._collect_public_data(piece_obj) if piece_obj is not None else {"type": None}
        indicateurs = _extract_indicators(objet)
        if isinstance(rapport_piece, Mapping):
            indicateurs = _merge_non_none(indicateurs, _extract_indicators(rapport_piece))
        entry = {
            "nom": name,
            "type": type(piece_obj).__name__ if piece_obj is not None else None,
            "indicateurs": indicateurs,
            "construction": construction.get(name) if isinstance(construction, Mapping) else None,
            "objet": objet,
            "rapport": rapport_piece,
        }
        inventory[name] = entry
    return inventory


def _build_piece_inventory_entry(*, name: str, piece_obj: Any, rapport_piece: Any, construction: Any, main_mod: Any) -> Dict[str, Any]:
    objet = main_mod._collect_public_data(piece_obj) if piece_obj is not None else {"type": None}
    indicateurs = _extract_indicators(objet)
    if isinstance(rapport_piece, Mapping):
        indicateurs = _merge_non_none(indicateurs, _extract_indicators(rapport_piece))
    return {
        "nom": name,
        "type": type(piece_obj).__name__ if piece_obj is not None else None,
        "construit": piece_obj is not None,
        "rapport_disponible": isinstance(rapport_piece, Mapping),
        "indicateurs": indicateurs,
        "construction": construction if isinstance(construction, Mapping) else None,
        "objet": objet,
        "rapport": rapport_piece,
    }


def extraire_rapports_pieces_composants(rapports_composants: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    nested: Dict[str, Any] = {}
    for composant_nom, composant_rapport in dict(rapports_composants or {}).items():
        if not isinstance(composant_rapport, Mapping):
            continue
        pieces_block = composant_rapport.get("pieces")
        if not isinstance(pieces_block, Mapping):
            continue
        for piece_nom, piece_rapport in pieces_block.items():
            nested[f"{composant_nom}.{piece_nom}"] = piece_rapport
    return nested


def construire_inventaire_pieces_imbrique(
    *,
    rapports_pieces: Mapping[str, Any],
    main_mod: Any,
) -> Dict[str, Any]:
    inventory: Dict[str, Any] = {}
    for full_name, rapport_piece in dict(rapports_pieces or {}).items():
        if "." not in str(full_name):
            continue
        composant_nom, piece_nom = str(full_name).split(".", 1)
        inventory[full_name] = {
            "nom": full_name,
            "type": rapport_piece.get("piece") if isinstance(rapport_piece, Mapping) else piece_nom,
            "construit": True,
            "rapport_disponible": isinstance(rapport_piece, Mapping),
            "source_composant": composant_nom,
            "piece_nom": piece_nom,
            "indicateurs": _extract_indicators(rapport_piece) if isinstance(rapport_piece, Mapping) else {},
            "objet": {"type": None},
            "construction": None,
            "rapport": rapport_piece,
        }
    return inventory


def consolider_sortie_pieces(
    *,
    main_mod: Any,
    pieces: Mapping[str, Any],
    construction_report: Mapping[str, Any],
    rapports_composants: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    rapports_pieces = _safe_dict(construction_report.get("rapports_pieces"))
    rapports_pieces_composants = extraire_rapports_pieces_composants(rapports_composants)
    if rapports_pieces_composants:
        rapports_pieces = _merge_non_none(rapports_pieces, rapports_pieces_composants)

    construction = _safe_dict(construction_report.get("construction"))
    inventory = _build_piece_inventory(
        main_mod=main_mod,
        pieces=pieces,
        rapports_pieces=rapports_pieces,
        construction=construction,
    )
    inventory.update(
        construire_inventaire_pieces_imbrique(
            rapports_pieces=rapports_pieces_composants,
            main_mod=main_mod,
        )
    )

    masses = [
        float(entry["indicateurs"]["masse_kg"])
        for entry in inventory.values()
        if isinstance(entry, Mapping)
        and isinstance(entry.get("indicateurs"), Mapping)
        and _is_finite(entry["indicateurs"].get("masse_kg"))
    ]

    return {
        "pieces": inventory,
        "rapports_pieces": rapports_pieces,
        "construction_pieces": dict(construction_report),
        "objets_serialises": {
            "pieces": {
                name: main_mod._collect_public_data(piece_obj)
                for name, piece_obj in pieces.items()
            }
        },
        "inventaire": {
            "pieces": {
                name: {
                    "type": entry.get("type"),
                    "construit": bool(entry.get("construit")),
                    "rapport_disponible": bool(entry.get("rapport_disponible")),
                    **({"source_composant": entry["source_composant"]} if entry.get("source_composant") else {}),
                }
                for name, entry in inventory.items()
            }
        },
        "synthese": {
            "pieces_construites": sorted(inventory.keys()),
            "nombre_pieces_construites": len(inventory),
            "masse_pieces_kg": sum(masses) if masses else None,
        },
    }


def _find_selected_candidate(
    rapport_puissance: Mapping[str, Any],
    preferred_labels: Sequence[str],
) -> Optional[Mapping[str, Any]]:
    selection = _safe_dict(rapport_puissance.get("selection"))
    candidates = list(rapport_puissance.get("candidats_valides") or [])
    by_index = {
        candidate.get("index"): candidate
        for candidate in candidates
        if isinstance(candidate, Mapping)
    }
    for label in preferred_labels:
        entry = _safe_dict(selection.get(label))
        candidate_summary = _safe_dict(entry.get("candidat"))
        index = candidate_summary.get("index")
        if index in by_index:
            return by_index[index]
    return candidates[0] if candidates else None


def _piece_inputs_from_power_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    known = dict(candidate.get("entrees") or {})
    candidate_report = _safe_dict(candidate.get("rapport"))
    calc_mt = _safe_dict(_get_nested(candidate_report, "calculs", "moteur_thermique"))
    geom = _safe_dict(calc_mt.get("geometrie"))

    puissance_cible_w = _safe_float(
        known.get("puissance_moteur_requise_w")
        or known.get("puissance_moteur_requise_W")
        or _get_nested(candidate_report, "calculs", "puissance_moteur_requise_w")
        or calc_mt.get("puissance_indiquee_w")
    )
    regime_tr_min = _safe_float(known.get("rpm_moteur") or known.get("rpm_moteur_nominal"))
    n_cyl = _safe_int(known.get("nombre_cylindres") or known.get("n_cyl") or geom.get("nombre_cylindres"))
    pression_max_pa = _safe_float(known.get("pression_max_pa"))

    return {
        "puissance_cible_w": puissance_cible_w,
        "regime_tr_min": regime_tr_min,
        "n_cyl": n_cyl,
        "pression_max_pa": pression_max_pa,
        "pme_pa": _safe_float(known.get("pme_pa") or known.get("pme_nominale_pa")),
        "alesage_m": _safe_float(geom.get("alesage_m") or known.get("alesage_m")),
        "course_m": _safe_float(geom.get("course_m") or known.get("course_m")),
        "definition_moteur_thermique": {
            "temps_moteur": _safe_int(known.get("temps_moteur")),
            "nombre_cylindres": n_cyl,
            "alesage_m": _safe_float(geom.get("alesage_m") or known.get("alesage_m")),
            "course_m": _safe_float(geom.get("course_m") or known.get("course_m")),
            "rpm_nominal": regime_tr_min,
            "pression_max_pa": pression_max_pa,
            "pme_pa": _safe_float(known.get("pme_pa") or known.get("pme_nominale_pa")),
            "type_puissance_nominale": known.get("type_puissance_moteur") or known.get("type_puissance_nominale"),
        },
    }


def enrichir_rapport_puissance_avec_pieces(
    rapport_puissance: Mapping[str, Any],
    *,
    preferred_labels: Sequence[str] = ("couple_sortie_max", "courant_dc_min"),
) -> Dict[str, Any]:
    report = dict(rapport_puissance)
    selected_candidate = _find_selected_candidate(report, preferred_labels)
    if selected_candidate is None:
        report["orchestration_pieces"] = {
            "active": False,
            "raison": "Aucun candidat valide disponible pour lancer le dimensionnement des pieces.",
        }
        return report

    piece_inputs = _piece_inputs_from_power_candidate(selected_candidate)
    missing = [
        name for name in ("puissance_cible_w", "regime_tr_min", "n_cyl", "pression_max_pa")
        if piece_inputs.get(name) is None
    ]
    if missing:
        report["orchestration_pieces"] = {
            "active": False,
            "raison": f"Donnees insuffisantes pour construire les pieces depuis le rapport puissance: {missing}.",
            "candidate_index": selected_candidate.get("index"),
        }
        return report

    pieces_report = dimensionner_pieces_moteur_thermique(**piece_inputs)
    report["orchestration_pieces"] = {
        "active": True,
        "source": {
            "candidate_index": selected_candidate.get("index"),
            "entrees": dict(selected_candidate.get("entrees") or {}),
        },
        "resume": dict(pieces_report.get("synthese") or {}),
    }
    for section in ("pieces", "inventaire", "construction_pieces", "rapports_pieces", "objets_serialises"):
        if section in pieces_report:
            report[section] = pieces_report[section]
    return report


def _build_minimal_rapport_systeme(
    *,
    rapport_systeme: Optional[Mapping[str, Any]],
    puissance_cible_w: float,
    regime_tr_min: float,
    n_cyl: int,
    pression_max_pa: float,
    pme_pa: Optional[float],
    alesage_m: Optional[float],
    course_m: Optional[float],
    longueur_bielle_m: Optional[float],
) -> Dict[str, Any]:
    base = _safe_dict(rapport_systeme)
    synthese = _safe_dict(base.get("synthese"))
    moteur = _safe_dict(synthese.get("moteur_thermique"))
    moteur = _merge_non_none(
        moteur,
        {
            "puissance_requise_W": puissance_cible_w,
            "rpm_nominal": regime_tr_min,
            "nombre_cylindres": n_cyl,
            "pression_max_pa": pression_max_pa,
            "pme_pa": pme_pa,
            "alesage_m": alesage_m,
            "course_m": course_m,
            "longueur_bielle_m": longueur_bielle_m,
        },
    )
    synthese["moteur_thermique"] = moteur
    base["synthese"] = synthese

    cao = _safe_dict(base.get("cao"))
    cao_mt = _safe_dict(cao.get("moteur_thermique"))
    if _is_finite(alesage_m):
        cao_mt["alesage_mm"] = float(alesage_m) * 1000.0
    if _is_finite(course_m):
        cao_mt["course_mm"] = float(course_m) * 1000.0
    if cao_mt:
        cao["moteur_thermique"] = cao_mt
        base["cao"] = cao

    entrees = _safe_dict(base.get("entrees"))
    criteres = _safe_dict(entrees.get("moteur_thermique_criteres"))
    criteres["pression_max_pa"] = pression_max_pa
    entrees["moteur_thermique_criteres"] = criteres
    base["entrees"] = entrees
    return base


def dimensionner_pieces_moteur_thermique(
    *,
    puissance_cible_w: float,
    regime_tr_min: float,
    n_cyl: int,
    pression_max_pa: float,
    pme_pa: Optional[float] = None,
    alesage_m: Optional[float] = None,
    course_m: Optional[float] = None,
    longueur_bielle_m: Optional[float] = None,
    definition_moteur_thermique: Optional[Mapping[str, Any]] = None,
    pieces_definition: Optional[Mapping[str, Any]] = None,
    rapport_systeme: Optional[Mapping[str, Any]] = None,
    moteur_thermique_obj: Any = None,
    systeme_obj: Any = None,
) -> Dict[str, Any]:
    puissance_cible_w = _req_positive("puissance_cible_w", puissance_cible_w)
    regime_tr_min = _req_positive("regime_tr_min", regime_tr_min)
    pression_max_pa = _req_positive("pression_max_pa", pression_max_pa)
    n_cyl_int = _safe_int(n_cyl)
    if n_cyl_int is None or n_cyl_int <= 0:
        raise ValueError("n_cyl must be an integer > 0.")

    pme_pa = _safe_float(pme_pa)
    alesage_m = _safe_float(alesage_m)
    course_m = _safe_float(course_m)
    longueur_bielle_m = _safe_float(longueur_bielle_m)

    report: Dict[str, Any] = {
        "entrees": {
            "puissance_cible_w": puissance_cible_w,
            "regime_tr_min": regime_tr_min,
            "n_cyl": n_cyl_int,
            "pression_max_pa": pression_max_pa,
            "pme_pa": pme_pa,
            "alesage_m": alesage_m,
            "course_m": course_m,
            "longueur_bielle_m": longueur_bielle_m,
        },
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }

    omega = 2.0 * math.pi * regime_tr_min / 60.0
    report["couple_moyen_calcule_Nm"] = (puissance_cible_w / omega) if omega > 0.0 else None

    if alesage_m is None:
        _push_unknown(report, "partielles", "alesage_m", "Impossible de definir completement les pieces sans alesage reel.")
    if course_m is None:
        _push_unknown(report, "partielles", "course_m", "Impossible de definir completement les pieces sans course reelle.")
    if pme_pa is None:
        _append_note(report, "La PME n'est pas fournie a cette couche, seules les pieces constructibles sans cette donnee sont tentees.")

    main_mod = _import_main_module()
    rapport_systeme_effectif = _build_minimal_rapport_systeme(
        rapport_systeme=rapport_systeme,
        puissance_cible_w=puissance_cible_w,
        regime_tr_min=regime_tr_min,
        n_cyl=n_cyl_int,
        pression_max_pa=pression_max_pa,
        pme_pa=pme_pa,
        alesage_m=alesage_m,
        course_m=course_m,
        longueur_bielle_m=longueur_bielle_m,
    )
    definition_moteur = _merge_non_none(
        {
            "puissance_nominale_visee_w": puissance_cible_w,
            "puissance_requise_W": puissance_cible_w,
            "rpm_nominal": regime_tr_min,
            "nombre_cylindres": n_cyl_int,
            "pression_max_pa": pression_max_pa,
            "pme_nominale_pa": pme_pa,
            "pme_pa": pme_pa,
            "alesage_m": alesage_m,
            "course_m": course_m,
            "longueur_bielle_m": longueur_bielle_m,
            "couple_max_Nm": report["couple_moyen_calcule_Nm"],
        },
        definition_moteur_thermique,
    )

    pieces, construction_report = main_mod.construire_pieces_depuis_systeme(
        rapport_systeme=rapport_systeme_effectif,
        definition_moteur_thermique=definition_moteur,
        pieces_definition=_safe_dict(pieces_definition),
        moteur_thermique_obj=moteur_thermique_obj,
        systeme_obj=systeme_obj,
        return_report=True,
    )

    report.update(
        consolider_sortie_pieces(
            main_mod=main_mod,
            pieces=pieces,
            construction_report=construction_report,
        )
    )
    report["inconnues"]["impossibles"].extend(
        list(_get_nested(construction_report, "inconnues", "impossibles") or [])
    )
    report["inconnues"]["partielles"].extend(
        list(_get_nested(construction_report, "inconnues", "partielles") or [])
    )
    report["notes_modele"].extend(list(construction_report.get("notes_modele") or []))
    return report
