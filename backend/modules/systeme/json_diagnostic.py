from __future__ import annotations

"""Diagnostic causal de rapports JSON STHO-ME.

Ce module analyse des symptomes deja presents dans un JSON. Il ne calcule pas
de valeur metier, ne modifie pas le repository et n'applique aucun patch.
"""

from dataclasses import asdict, is_dataclass
import copy
import json
import math
from typing import Any, Dict, Iterable, List, Mapping

from backend.modules.systeme.aliases import canonical_field_name, get_alias_paths


CRITICAL_DEPENDENCIES: dict[str, list[str]] = {
    "omega_moteur_rad_s": ["rpm_moteur"],
    "couple_moteur_nm": ["puissance_traction_w", "omega_moteur_rad_s"],
    "couple_alternateur_nm": ["puissance_bus_dc_w", "rendement_alternateur", "rpm_alternateur"],
    "rapport_alternateur_moteur": ["rpm_alternateur", "rpm_moteur"],
    "architecture": ["alesage_m", "course_m", "pme_pa", "rpm_moteur", "puissance_traction_w"],
    "nombre_cylindres": ["alesage_m", "course_m", "pme_pa", "rpm_moteur", "puissance_traction_w"],
    "solidworks_ready": ["alesage_m", "course_m", "nombre_cylindres", "architecture", "interfaces_pieces"],
}

ROOT_PATTERNS = (
    {
        "id": "moteur_thermique_definir_depuis_exigences",
        "title": "Moteur thermique non ferme",
        "subsystem": "moteur_thermique",
        "needles": ("definir_depuis_exigences", "moteur_thermique_definition", "moteurthermique.definir"),
        "field": "moteur_thermique_definir_depuis_exigences",
        "action": "Renseigner les arguments obligatoires ou fournir des bornes CDC suffisantes.",
    },
    {
        "id": "boite_crabots_rapports",
        "title": "Chaine alternateur / boite / moteur non reliee",
        "subsystem": "boite_crabots",
        "needles": ("boite_crabots.rapports", "rapports_boite", "rapport_boite", "rapport_vitesse_alt"),
        "field": "rapport_alternateur_moteur",
        "action": "Fournir des rapports candidats ou des bornes de rapport explicites.",
    },
    {
        "id": "rpm_moteur_absent",
        "title": "Plage regime moteur absente",
        "subsystem": "moteur_thermique",
        "needles": ("rpm", "regime_moteur", "vitesse_moteur_thermique"),
        "field": "rpm_moteur",
        "action": "Fournir un regime nominal ou des bornes rpm CDC.",
    },
    {
        "id": "couple_alternateur_absent",
        "title": "Couple alternateur non disponible",
        "subsystem": "alternateur",
        "needles": ("couple_alternateur", "couple alternateur"),
        "field": "couple_alternateur_nm",
        "action": "Fournir puissance alternateur et regime alternateur, ou un couple direct.",
    },
    {
        "id": "couple_moteur_absent",
        "title": "Couple moteur non disponible",
        "subsystem": "moteur_thermique",
        "needles": ("couple_moteur", "couple moteur", "torsion"),
        "field": "couple_moteur_nm",
        "action": "Fournir puissance moteur et rpm moteur, ou un couple direct.",
    },
    {
        "id": "architecture_cylindres_non_resolus",
        "title": "Architecture et cylindres non resolus",
        "subsystem": "architecture",
        "needles": ("architecture", "nombre_cylindres", "cylindres"),
        "field": "architecture",
        "action": "Fermer les donnees moteur amont ou fournir un domaine architecture/cylindres.",
    },
    {
        "id": "cao_non_fermee",
        "title": "CAO non fermee",
        "subsystem": "cao",
        "needles": ("solidworks", "cao", "3d", "cotes"),
        "field": "solidworks_ready",
        "action": "Completer les cotes et interfaces requises avant 3D/SolidWorks.",
    },
)


def diagnostiquer_json_sthome(
    *,
    data: dict,
    source_name: str | None = None,
    mode: str = "rapport_ou_config",
    strict: bool = True,
    include_patch: bool = True,
    max_items: int = 500,
) -> dict:
    payload = data if isinstance(data, dict) else {}
    type_detecte = detecter_type_json(payload)
    extracted = extraire_inconnues_et_alertes(payload)
    items = extracted["items"][: max(1, max_items)]
    dedup = dedupliquer_problemes(items)
    graph = construire_graphe_dependances(payload, items)
    causes = identifier_causes_racines(items=items, graph=graph, data=payload)
    patchs = proposer_patchs_json(causes_racines=causes, data=payload, strict=strict) if include_patch else []
    patch_by_cause = {str(p.get("cause_id")): p for p in patchs if isinstance(p, Mapping)}
    for cause in causes:
        patch = patch_by_cause.get(str(cause.get("id")))
        if patch:
            cause.setdefault("patchs_proposes", []).append(patch)
    blocking_count = sum(1 for item in items if item.get("categorie") in {"bloquant", "impossible", "cao", "optimisation"})
    score = _diagnostic_score(len(causes), len(items), blocking_count, len(dedup.get("doublons", [])))
    statut = _diagnostic_status(score, causes, blocking_count)
    cao_available = bool(_get_path(payload, "cao.available") or _get_path(payload, "frontend.cao.available"))
    solidworks_ready = bool(
        _get_path(payload, "cao.solidworks_ready")
        or _get_path(payload, "cao.solidworks_ready_detaille")
        or _get_path(payload, "frontend.cao.solidworks_ready")
    )
    return _jsonable(
        {
            "meta": {
                "source_name": source_name,
                "mode": mode,
                "type_detecte": type_detecte,
                "strict": bool(strict),
            },
            "resume": {
                "statut": statut,
                "score_diagnostic_100": score,
                "nb_causes_racines": len(causes),
                "nb_symptomes": len(items),
                "nb_doublons_probables": len(dedup.get("doublons", [])),
                "nb_champs_bloquants": blocking_count,
                "cao_disponible": cao_available,
                "solidworks_ready": solidworks_ready,
            },
            "causes_racines": causes,
            "symptomes": dedup.get("items_uniques", []),
            "doublons": dedup.get("doublons", []),
            "dependances": graph,
            "patchs_proposes": patchs,
            "actions_prioritaires": _actions_from_causes(causes),
            "sections_analysees": extracted["sections_analysees"],
            "inconnues_normalisees": extracted["inconnues"],
            "alertes_normalisees": extracted["alertes"],
            "notes": [
                "Diagnostic causal non mutateur: aucun patch n'est applique automatiquement.",
                "Les causes sont inferees depuis les champs, raisons, chemins JSON et alias connus.",
            ],
        }
    )


def detecter_type_json(data: dict) -> str:
    if not isinstance(data, Mapping):
        return "inconnu"
    if all(key in data for key in ("sous_systemes", "pieces", "synthese")) and (
        data.get("tracabilite") is not None or data.get("traçabilite") is not None or data.get("rapports") is not None
    ):
        return "rapport_sthome"
    frontend = data.get("frontend")
    if isinstance(frontend, Mapping) and (frontend.get("fields") is not None or frontend.get("cao") is not None):
        return "frontend_contract"
    if data.get("fields") is not None and data.get("cao") is not None:
        return "frontend_contract"
    if any(key in data for key in ("config_completee", "rapport_avant", "rapport_apres", "inconnues_restantes")):
        return "resolution_inconnues"
    if data.get("resolution_candidates") is not None or data.get("resolution_inconnues") is not None:
        return "resolution_inconnues"
    if data.get("synthese_optimisation") is not None or (
        data.get("actions") is not None and data.get("extractions") is not None
    ):
        return "optimisation"
    if all(key in data for key in ("composants", "pieces", "analyses", "meta")):
        return "config"
    return "inconnu"


def extraire_inconnues_et_alertes(data: dict) -> dict:
    items: List[dict[str, Any]] = []
    inconnues: List[dict[str, Any]] = []
    alertes: List[dict[str, Any]] = []
    sections: set[str] = set()

    def add(raw: Any, *, path: str, category: str, source: str, is_alert: bool = False) -> None:
        normalized = _normalize_item(raw, path=path, category=category, source=source, is_alert=is_alert)
        items.append(normalized)
        if is_alert:
            alertes.append(normalized)
        else:
            inconnues.append(normalized)
        sections.add(path.split(".")[0] if path else "racine")

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                key_s = str(key)
                next_path = f"{path}.{key_s}" if path else key_s
                key_l = key_s.lower()
                if key_l in {"inconnues", "unknowns"} and isinstance(value, Mapping):
                    for category, values in value.items():
                        cat_path = f"{next_path}.{category}"
                        for raw in _as_list(values):
                            add(raw, path=cat_path, category=str(category), source=cat_path)
                elif key_l in {"alertes", "alerts"} and isinstance(value, Mapping):
                    for category, values in value.items():
                        cat_path = f"{next_path}.{category}"
                        for raw in _as_list(values):
                            add(raw, path=cat_path, category=str(category), source=cat_path, is_alert=True)
                elif key_l in {"missing_requirements"}:
                    for raw in _as_list(value):
                        add(raw, path=next_path, category="bloquant", source=next_path)
                elif key_l in {"inconnues_cao"}:
                    for raw in _as_list(value):
                        add(raw, path=next_path, category="cao", source=next_path)
                elif key_l in {"erreur", "error"} and value:
                    add({"nom": key_s, "raison": value}, path=next_path, category="erreur", source=path or "racine", is_alert=True)

                if isinstance(value, (Mapping, list)):
                    walk(value, next_path)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, (Mapping, list)):
                    walk(value, f"{path}[{index}]")

    walk(data)
    return {
        "items": _dedupe_exact(items),
        "inconnues": _dedupe_exact(inconnues),
        "alertes": _dedupe_exact(alertes),
        "sections_analysees": sorted(sections),
    }


def dedupliquer_problemes(items: list[dict]) -> dict:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicates: List[dict[str, Any]] = []
    uniques: List[dict[str, Any]] = []
    for item in items:
        field = canonical_field_name(item.get("champ") or item.get("path") or item.get("id"))
        reason_key = _normalize_text(item.get("raison"))[:120]
        subsystem = _normalize_text(item.get("sous_systeme"))
        key = (field, reason_key, subsystem)
        group = groups.setdefault(
            key,
            {
                "cause_probable": field or "inconnu",
                "raison": item.get("raison"),
                "sous_systeme": item.get("sous_systeme"),
                "occurrences": [],
                "chemins_affectes": [],
                "sources_affectees": [],
            },
        )
        occurrence = {
            "id": item.get("id"),
            "path": item.get("path"),
            "source": item.get("source"),
            "severity": item.get("severity"),
        }
        if group["occurrences"]:
            duplicates.append(occurrence)
        else:
            uniques.append(item)
        group["occurrences"].append(occurrence)
        if item.get("path") not in group["chemins_affectes"]:
            group["chemins_affectes"].append(item.get("path"))
        if item.get("source") not in group["sources_affectees"]:
            group["sources_affectees"].append(item.get("source"))
    return {
        "causes_probables": list(groups.values()),
        "items_uniques": uniques,
        "doublons": duplicates,
    }


def construire_graphe_dependances(data: dict, items: list[dict]) -> dict:
    nodes: dict[str, dict[str, Any]] = {}
    for field, upstream in CRITICAL_DEPENDENCIES.items():
        nodes.setdefault(field, {"upstream": [], "downstream": [], "missing": False})
        nodes[field]["upstream"] = list(upstream)
        for dep in upstream:
            dep_node = nodes.setdefault(dep, {"upstream": [], "downstream": [], "missing": False})
            if field not in dep_node["downstream"]:
                dep_node["downstream"].append(field)
    for item in items:
        field = canonical_field_name(item.get("champ") or item.get("path") or item.get("id"))
        if not field:
            continue
        node = nodes.setdefault(field, {"upstream": [], "downstream": [], "missing": False})
        node["missing"] = True
        node.setdefault("items", []).append(item.get("id"))
    for field, node in nodes.items():
        node["aliases"] = get_alias_paths(field)
        node["available_path"] = _first_existing_path(data, node["aliases"])
        node["missing_upstream"] = [dep for dep in node.get("upstream", []) if nodes.get(dep, {}).get("missing")]
    return {"nodes": nodes, "critical_dependencies": copy.deepcopy(CRITICAL_DEPENDENCIES)}


def identifier_causes_racines(
    *,
    items: list[dict],
    graph: dict,
    data: dict,
) -> list[dict]:
    causes: dict[str, dict[str, Any]] = {}
    for pattern in ROOT_PATTERNS:
        occurrences = [item for item in items if _matches_pattern(item, pattern)]
        field = str(pattern["field"])
        graph_node = graph.get("nodes", {}).get(field, {}) if isinstance(graph.get("nodes"), Mapping) else {}
        if graph_node.get("missing") and not occurrences:
            occurrences = [{"id": field, "path": field, "raison": "Champ critique manquant.", "source": "graphe_dependances", "severity": 80}]
        if not occurrences:
            continue
        downstream = _downstream_closure(field, graph)
        impact_sections = sorted({str(o.get("source", "")).split(".")[0] for o in occurrences if o.get("source")})
        impact_sections.extend([d for d in downstream if d not in impact_sections])
        priority = min(100, 60 + len(occurrences) * 4 + len(downstream) * 6)
        cause = {
            "id": pattern["id"],
            "titre": pattern["title"],
            "sous_systeme": pattern["subsystem"],
            "champ": field,
            "raison": _best_reason(occurrences),
            "impact": {
                "nb_symptomes_expliques": len(occurrences) + len(downstream),
                "sections_affectees": impact_sections[:20],
                "bloque_cao": field in {"solidworks_ready", "alesage_m", "course_m", "architecture", "nombre_cylindres"},
                "bloque_optimisation": field != "solidworks_ready",
                "bloque_frontend": False,
            },
            "priorite": priority,
            "actions": [pattern["action"]],
            "patchs_proposes": [],
            "occurrences": occurrences[:50],
        }
        causes[str(pattern["id"])] = cause
    return sorted(causes.values(), key=lambda c: (-float(c.get("priorite", 0)), str(c.get("id"))))


def proposer_patchs_json(
    *,
    causes_racines: list[dict],
    data: dict,
    strict: bool = True,
) -> list[dict]:
    patchs: List[dict[str, Any]] = []
    cdc = _extract_cdc(data)
    for cause in causes_racines:
        field = str(cause.get("champ") or "")
        patch_type = "missing_user_input"
        if not strict and _cdc_has_bounds_for(field, cdc):
            patch_type = "candidate_from_cdc"
        elif _could_be_repository(field):
            patch_type = "repository_lookup"
        patchs.append(
            {
                "cause_id": cause.get("id"),
                "type": patch_type,
                "path": _suggest_path(field),
                "label": _label_for_field(field),
                "expected_unit": _unit_for_field(field),
                "expected_type": _type_for_field(field),
                "reason": _reason_for_patch(field, cause),
                "example": None,
                "apply_automatically": False,
            }
        )
    return patchs


def _normalize_item(raw: Any, *, path: str, category: str, source: str, is_alert: bool) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        item = dict(raw)
    else:
        item = {"nom": str(raw), "raison": str(raw)}
    field = item.get("path") or item.get("champ") or item.get("field") or item.get("nom") or item.get("name") or path
    reason = item.get("raison") or item.get("reason") or item.get("detail") or item.get("message") or item.get("erreur") or ""
    subsystem = item.get("sous_systeme") or item.get("subsystem") or _infer_subsystem(field, reason, source)
    normalized_category = _category(category, is_alert)
    canonical = canonical_field_name(field)
    return {
        "id": _stable_id(source, field, reason),
        "path": str(item.get("path") or path),
        "champ": canonical or str(field),
        "raison": str(reason),
        "categorie": normalized_category,
        "sous_systeme": str(subsystem),
        "source": str(item.get("source") or source),
        "severity": _severity(normalized_category, reason),
        "raw": _jsonable(item),
    }


def _matches_pattern(item: Mapping[str, Any], pattern: Mapping[str, Any]) -> bool:
    blob = _normalize_text(" ".join(str(item.get(k, "")) for k in ("id", "path", "champ", "raison", "source", "sous_systeme")))
    field = canonical_field_name(item.get("champ") or item.get("path"))
    if field == pattern.get("field"):
        return True
    return any(_normalize_text(needle) in blob for needle in pattern.get("needles", ()))


def _downstream_closure(field: str, graph: Mapping[str, Any]) -> list[str]:
    nodes = graph.get("nodes", {}) if isinstance(graph.get("nodes"), Mapping) else {}
    seen: set[str] = set()
    queue = list(nodes.get(field, {}).get("downstream", []) if isinstance(nodes.get(field), Mapping) else [])
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        node = nodes.get(cur, {})
        if isinstance(node, Mapping):
            queue.extend([x for x in node.get("downstream", []) if x not in seen])
    return sorted(seen)


def _best_reason(items: Iterable[Mapping[str, Any]]) -> str:
    reasons = [str(item.get("raison") or "").strip() for item in items if str(item.get("raison") or "").strip()]
    return max(reasons, key=len) if reasons else "Cause racine probable detectee depuis les chemins JSON."


def _actions_from_causes(causes: list[dict]) -> list[dict]:
    out = []
    for cause in causes[:10]:
        out.append(
            {
                "id": f"action_{cause.get('id')}",
                "label": str(cause.get("actions", ["Corriger"])[0]),
                "priority": cause.get("priorite"),
                "field": cause.get("champ"),
                "apply_automatically": False,
            }
        )
    return out


def _diagnostic_score(nb_causes: int, nb_items: int, nb_blocking: int, nb_duplicates: int) -> float:
    score = 100.0
    score -= min(45.0, nb_causes * 10.0)
    score -= min(30.0, nb_blocking * 3.0)
    score -= min(15.0, nb_items * 0.05)
    score += min(10.0, nb_duplicates * 0.01)
    return round(max(0.0, min(100.0, score)), 1)


def _diagnostic_status(score: float, causes: list[dict], blocking_count: int) -> str:
    if blocking_count or any(float(c.get("priorite", 0)) >= 80 for c in causes):
        return "bloque"
    if score >= 90:
        return "valide"
    if score >= 65:
        return "exploitable"
    return "partiel"


def _extract_cdc(data: Mapping[str, Any]) -> Mapping[str, Any]:
    for path in ("cahier_des_charges", "meta.cahier_des_charges", "analyses.cahier_des_charges", "criteres_conception"):
        value = _get_path(data, path)
        if isinstance(value, Mapping):
            return value
    return {}


def _cdc_has_bounds_for(field: str, cdc: Mapping[str, Any]) -> bool:
    if not cdc:
        return False
    key = field.split(".")[-1]
    if cdc.get(f"{key}_min") is not None and cdc.get(f"{key}_max") is not None:
        return True
    bounds = cdc.get("bornes")
    return isinstance(bounds, Mapping) and (key in bounds or field in bounds)


def _could_be_repository(field: str) -> bool:
    return field in {"materiau", "carburant", "architecture", "tension_bus_dc_v"} or "rapport" in field


def _suggest_path(field: str) -> str:
    paths = get_alias_paths(field)
    return paths[0] if paths else field


def _label_for_field(field: str) -> str:
    labels = {
        "rpm_moteur": "Regime moteur nominal",
        "rapport_alternateur_moteur": "Rapports de boite candidats",
        "couple_alternateur_nm": "Couple alternateur",
        "couple_moteur_nm": "Couple moteur",
        "architecture": "Architecture moteur",
        "solidworks_ready": "Fermeture CAO",
    }
    return labels.get(field, field.replace("_", " ").title())


def _unit_for_field(field: str) -> str | None:
    if "rpm" in field:
        return "rpm"
    if field.endswith("_w"):
        return "W"
    if field.endswith("_v"):
        return "V"
    if field.endswith("_nm"):
        return "N.m"
    if field.endswith("_m"):
        return "m"
    return None


def _type_for_field(field: str) -> str:
    if "rapport" in field:
        return "list[float]"
    if field in {"architecture", "materiau", "carburant", "solidworks_ready"}:
        return "str"
    return "float"


def _reason_for_patch(field: str, cause: Mapping[str, Any]) -> str:
    if field == "rapport_alternateur_moteur":
        return "Necessaire pour relier rpm moteur et rpm alternateur."
    if field == "rpm_moteur":
        return "Necessaire pour calculer omega, couple, geometrie moteur et liaison alternateur."
    return str(cause.get("raison") or "Champ necessaire pour lever une cause racine.")


def _category(category: Any, is_alert: bool) -> str:
    raw = _normalize_text(category)
    if is_alert:
        return "alerte"
    if raw in {"impossibles", "impossible", "bloquantes", "bloquant", "required_fields", "missing_required", "erreur", "error"}:
        return "bloquant"
    if raw in {"cao", "inconnues_cao"}:
        return "cao"
    if raw in {"optimisation"}:
        return "optimisation"
    if raw in {"partielles", "partielle", "partial", "missing_optional"}:
        return "partiel"
    return raw or "inconnu"


def _severity(category: str, reason: Any) -> int:
    base = {
        "bloquant": 90,
        "cao": 82,
        "optimisation": 78,
        "alerte": 65,
        "partiel": 45,
    }.get(category, 35)
    text = _normalize_text(reason)
    if "missing required" in text or "argument" in text or "impossible" in text:
        base = max(base, 88)
    return min(100, base)


def _infer_subsystem(*texts: Any) -> str:
    blob = _normalize_text(" ".join(str(t or "") for t in texts))
    for needle, subsystem in (
        ("moteur_thermique", "moteur_thermique"),
        ("thermal", "moteur_thermique"),
        ("alternateur", "alternateur"),
        ("boite", "boite_crabots"),
        ("crabot", "boite_crabots"),
        ("batterie", "batterie"),
        ("bus_dc", "batterie"),
        ("moteur_electrique", "moteur_electrique"),
        ("architecture", "architecture"),
        ("solidworks", "cao"),
        ("cao", "cao"),
        ("optimisation", "optimisation"),
    ):
        if needle in blob:
            return subsystem
    return "general"


def _first_existing_path(data: Mapping[str, Any], paths: Iterable[str]) -> str | None:
    for path in paths:
        if _get_path(data, path) is not None:
            return path
    return None


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    if path in data:
        return data[path]
    cur: Any = data
    for part in str(path).split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Mapping):
        return [value]
    if value in (None, ""):
        return []
    return [value]


def _dedupe_exact(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        sig = (str(item.get("path")), str(item.get("champ")), str(item.get("raison")))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def _stable_id(*parts: Any) -> str:
    text = _normalize_text(" ".join(str(p or "") for p in parts))
    return text[:140] or "diagnostic_item"


def _normalize_text(value: Any) -> str:
    raw = str(value or "").lower()
    out = []
    for char in raw:
        if char.isalnum():
            out.append(char)
        else:
            out.append("_")
    return "_".join(part for part in "".join(out).split("_") if part)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)
