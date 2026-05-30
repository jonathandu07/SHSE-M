"""
Chemin : frontend/ensemble/piece_data_adapter.py
But :
    Extraire proprement les donnees backend des pieces et composants.
Pourquoi ce fichier existe :
    Les modules de rendu frontend doivent recevoir des donnees deja calculees par
    le backend. Cet adaptateur centralise la lecture des rapports sans calculer,
    sans instancier de piece vide et sans remplacer une cote manquante par zero.
Donnees consommees :
    Rapport backend complet, frontend_contract, cao_dossier, mechanical_graphs,
    rapports de pieces et rapports de composants.
Livrables produits :
    Champs normalises, rapports piece/composant et listes de dimensions a copier.
Limites :
    - ne calcule pas la piece ;
    - ne remplace pas SolidWorks ;
    - ne produit pas de STEP ;
    - n'invente aucune cote ;
    - la 3D reste indicative.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence


STATUS_AVAILABLE = "available"
STATUS_PARTIAL = "partial"
STATUS_MISSING_REQUIRED = "missing_required"
STATUS_COMPUTED = "computed"
STATUS_DERIVED = "derived"
STATUS_VALIDATED_BY_OPTIMIZATION = "validated_by_optimization"
STATUS_CANDIDATE_FROM_CDC = "candidate_from_cdc"
STATUS_CANDIDATE_FROM_POWER_PROFILE = "candidate_from_power_profile"
STATUS_REJECTED_BY_OPTIMIZATION = "rejected_by_optimization"

_VALUE_KEYS = ("value", "valeur", "result", "resultat")
_TRACE_REQUIRED = {STATUS_COMPUTED, STATUS_VALIDATED_BY_OPTIMIZATION}
_STATUS_ALIASES = {
    "candidate_generated": STATUS_CANDIDATE_FROM_CDC,
    "candidate_optimized": STATUS_CANDIDATE_FROM_CDC,
    "optimisee": STATUS_CANDIDATE_FROM_CDC,
    "optimized": STATUS_PARTIAL,
    "optimise": STATUS_PARTIAL,
    "optimisé": STATUS_PARTIAL,
    "validated": STATUS_PARTIAL,
    "candidate_rejected": STATUS_REJECTED_BY_OPTIMIZATION,
    "profil_puissance": STATUS_CANDIDATE_FROM_POWER_PROFILE,
    "missing": STATUS_MISSING_REQUIRED,
    "partiel": STATUS_PARTIAL,
}
_PUBLIC_FIELD_STATUSES = {
    STATUS_AVAILABLE,
    STATUS_PARTIAL,
    STATUS_MISSING_REQUIRED,
    STATUS_COMPUTED,
    STATUS_DERIVED,
    STATUS_VALIDATED_BY_OPTIMIZATION,
    STATUS_CANDIDATE_FROM_CDC,
    STATUS_CANDIDATE_FROM_POWER_PROFILE,
    STATUS_REJECTED_BY_OPTIMIZATION,
    "input",
    "database",
    "missing_optional",
    "impossible",
    "error",
}


_PIECE_ALIASES: dict[str, tuple[str, ...]] = {
    "arbre_piston": ("arbre_piston", "axe_piston", "arbre.piston"),
    "arbre_vilebrequin": ("arbre_vilebrequin", "arbre_vilbrequin", "arbre_vilbrequin"),
    "arbre_vilbrequin": ("arbre_vilbrequin", "arbre_vilebrequin"),
    "vilebrequin": ("vilebrequin", "vilbrequin"),
    "vilbrequin": ("vilbrequin", "vilebrequin"),
    "bielle": ("bielle", "corps_bielle"),
    "cylindre": ("cylindre",),
    "piston": ("piston",),
    "joint_piston": ("joint_piston",),
    "joint_deplaceur": ("joint_deplaceur",),
    "deplaceur": ("deplaceur",),
    "coussinet_arbre_piston": ("coussinet_arbre_piston",),
    "roulement_aiguille_arbre": ("roulement_aiguille_arbre",),
    "roulement_aiguille_arbre_vilebrequin": ("roulement_aiguille_arbre_vilebrequin",),
    "vis_couvercle_cylindre": ("vis_couvercle_cylindre",),
    "clavette_arbre": ("clavette_arbre", "clavette"),
    "arbre": ("arbre", "arbre_moteur"),
}


def safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def get_path(data: Any, path: str, default: Any = None) -> Any:
    if not isinstance(path, str) or not path:
        return default
    if isinstance(data, Mapping) and path in data:
        return data[path]
    cur = data
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _normalize_field_status(value: Any, *, trace: Mapping[str, Any] | None = None, confidence: Any = None) -> str:
    raw = str(value or "").strip().lower()
    status = _STATUS_ALIASES.get(raw, raw)
    if not status:
        status = STATUS_PARTIAL
    if status not in _PUBLIC_FIELD_STATUSES:
        status = STATUS_PARTIAL
    if confidence == "untraced_report_value":
        return STATUS_PARTIAL
    if status in _TRACE_REQUIRED and not trace:
        return STATUS_PARTIAL
    return status


def _read_detail_field(raw: Any, *, default_unit: str | None = None) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            "value": raw,
            "unit": default_unit,
            "status": STATUS_PARTIAL if raw is not None else STATUS_MISSING_REQUIRED,
            "source": "backend",
            "trace": {},
            "confidence": "untraced_report_value" if raw is not None else None,
        }

    value_key = next((key for key in _VALUE_KEYS if key in raw), None)
    if value_key is None:
        value = raw
    else:
        value = raw.get(value_key)

    trace = raw.get("trace") if isinstance(raw.get("trace"), Mapping) else {}
    confidence = raw.get("confidence") or raw.get("confiance")
    status = _normalize_field_status(raw.get("status") or raw.get("statut"), trace=trace, confidence=confidence)
    if value is None:
        status = STATUS_MISSING_REQUIRED

    return {
        "value": value,
        "unit": raw.get("unit") or raw.get("unite") or default_unit,
        "status": status,
        "raw_status": raw.get("status") or raw.get("statut"),
        "source": raw.get("source") or raw.get("origine") or "backend",
        "trace": dict(trace),
        "confidence": confidence or ("traced" if trace else "untraced_report_value" if value is not None else None),
        "dependencies": raw.get("dependencies") or raw.get("dependances") or [],
    }


def _aliases(name: str) -> tuple[str, ...]:
    key = str(name or "").strip()
    low = key.lower()
    return tuple(dict.fromkeys((key, low, *(_PIECE_ALIASES.get(low) or ()))))


def _all_known_aliases() -> tuple[str, ...]:
    names: list[str] = []
    for key, aliases in _PIECE_ALIASES.items():
        names.append(key)
        names.extend(aliases)
    return tuple(dict.fromkeys(str(name).lower().replace(".", "_") for name in names if name))


def _resource_matches_piece(row: Mapping[str, Any], piece_name: str) -> bool:
    aliases = tuple(alias.lower().replace(".", "_") for alias in _aliases(piece_name))
    piece_value = row.get("piece") or row.get("piece_name") or row.get("nom_piece")
    if piece_value:
        piece_key = str(piece_value).split(".")[-1].lower().replace(".", "_")
        return piece_key in aliases

    text = " ".join(str(row.get(k) or "") for k in ("id", "name", "title", "titre")).lower()
    normalized = "_" + "".join(ch if ch.isalnum() else "_" for ch in text) + "_"
    for alias in aliases:
        if f"_{alias}_" not in normalized:
            continue
        for known in _all_known_aliases():
            if known in aliases:
                continue
            if known.startswith(f"{alias}_") and f"_{known}_" in normalized:
                return False
        return True
    return False


def _candidate_sections(global_report: Mapping[str, Any], piece_name: str) -> list[tuple[str, Any]]:
    aliases = _aliases(piece_name)
    sections: list[tuple[str, Any]] = []
    for root in (
        "rapports_pieces",
        "pieces",
        "construction_pieces.construction",
        "objets_serialises.pieces",
        "rapports.pieces",
        "sous_systemes.moteur_thermique.pieces",
        "cao_dossier.pieces",
    ):
        block = get_path(global_report, root)
        if not isinstance(block, Mapping):
            continue
        for alias in aliases:
            if alias in block:
                sections.append((f"{root}.{alias}", block[alias]))
        for key, value in block.items():
            if str(key).split(".")[-1].lower() in aliases:
                sections.append((f"{root}.{key}", value))
    return sections


def get_piece_report(global_report: Mapping[str, Any], piece_name: str) -> Dict[str, Any]:
    """Retourne le rapport backend d'une piece sans fabriquer de donnees."""
    if not isinstance(global_report, Mapping):
        return {}
    if str(global_report.get("piece") or global_report.get("name") or "").lower() in _aliases(piece_name):
        return dict(global_report)
    for _path, payload in _candidate_sections(global_report, piece_name):
        if isinstance(payload, Mapping):
            out = dict(payload)
            out.setdefault("_source_path", _path)
            return out
    return {}


def get_component_report(global_report: Mapping[str, Any], component_name: str) -> Dict[str, Any]:
    """Retourne le rapport backend d'un composant sans logique metier."""
    if not isinstance(global_report, Mapping):
        return {}
    names = _aliases(component_name)
    for root in ("sous_systemes", "rapports.composants", "composants", "analyses_composants"):
        block = get_path(global_report, root)
        if not isinstance(block, Mapping):
            continue
        for name in names:
            if name in block and isinstance(block[name], Mapping):
                out = dict(block[name])
                out.setdefault("_source_path", f"{root}.{name}")
                return out
    return {}


def extract_field(
    report: Mapping[str, Any],
    path: str,
    *,
    unit: str | None = None,
    label: str | None = None,
    required: bool = False,
) -> Dict[str, Any]:
    raw = get_path(report, path)
    detail = _read_detail_field(raw, default_unit=unit)
    value = detail["value"]
    return {
        "path": path,
        "label": label or path.split(".")[-1],
        "value": value,
        "unit": detail.get("unit"),
        "status": detail.get("status"),
        "raw_status": detail.get("raw_status"),
        "source": detail.get("source"),
        "trace": detail.get("trace") or {},
        "confidence": detail.get("confidence"),
        "dependencies": detail.get("dependencies") or [],
        "required": bool(required),
    }


def require_fields(report: Mapping[str, Any], fields: Sequence[Mapping[str, Any] | str]) -> Dict[str, Any]:
    extracted: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    used: list[dict[str, Any]] = []
    for spec in fields:
        if isinstance(spec, str):
            row = extract_field(report, spec)
        else:
            row = extract_field(
                report,
                str(spec.get("path") or ""),
                unit=spec.get("unit"),
                label=spec.get("label"),
                required=bool(spec.get("required")),
            )
        extracted.append(row)
        if row["value"] is not None:
            used.append(row)
        else:
            missing.append(row)
    return {
        "ok": not missing,
        "status": STATUS_PARTIAL if not missing else STATUS_MISSING_REQUIRED,
        "fields": extracted,
        "used_fields": used,
        "missing_fields": missing,
    }


def iter_leaf_fields(data: Any, *, prefix: str = "", max_depth: int = 7, depth: int = 0) -> Iterable[tuple[str, Any]]:
    if depth > max_depth:
        return
    if isinstance(data, Mapping):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, Mapping):
                yield from iter_leaf_fields(value, prefix=path, max_depth=max_depth, depth=depth + 1)
            elif isinstance(value, list):
                yield path, value
            else:
                yield path, value


def collect_dimensions(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Collecte les cotes deja presentes dans le backend, sans conversion calculee."""
    markers = (
        "diametre",
        "diameter",
        "longueur",
        "length",
        "largeur",
        "width",
        "hauteur",
        "height",
        "epaisseur",
        "thickness",
        "alesage",
        "bore",
        "course",
        "stroke",
        "rayon",
        "radius",
        "entraxe",
        "x_",
        "y_",
        "z_",
    )
    out: list[dict[str, Any]] = []
    for path, value in iter_leaf_fields(report):
        low = path.lower()
        if value is None:
            continue
        if any(marker in low for marker in markers):
            unit = "m" if low.endswith("_m") else "mm" if low.endswith("_mm") else None
            out.append(
                {
                    "path": path,
                    "label": path.split(".")[-1],
                    "value": value,
                    "unit": unit,
                    "source": "backend",
                    "status": STATUS_PARTIAL,
                    "confidence": "untraced_report_value",
                }
            )
    return out


def get_backend_graphs(global_report: Mapping[str, Any], piece_name: str | None = None) -> list[dict[str, Any]]:
    graphs: list[dict[str, Any]] = []
    for root in ("mechanical_graphs.graphiques", "mechanical_graphs.graphs", "cao_dossier.graphiques"):
        for item in safe_list(get_path(global_report, root)):
            if not isinstance(item, Mapping):
                continue
            row = dict(item)
            if piece_name and not _resource_matches_piece(row, piece_name):
                continue
            graphs.append(row)
    return graphs


def get_backend_sketches(global_report: Mapping[str, Any], piece_name: str | None = None) -> list[dict[str, Any]]:
    sketches: list[dict[str, Any]] = []
    for item in safe_list(get_path(global_report, "cao_dossier.croquis_2d")):
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        if piece_name:
            if not _resource_matches_piece(row, piece_name):
                continue
        sketches.append(row)
    return sketches


def get_backend_views_3d(global_report: Mapping[str, Any], piece_name: str | None = None) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for item in safe_list(get_path(global_report, "cao_dossier.vues_3d")):
        if not isinstance(item, Mapping):
            continue
        row = dict(item)
        if piece_name:
            if not _resource_matches_piece(row, piece_name):
                continue
        views.append(row)
    return views


def component_piece_directories(root: str | Path = "frontend/components") -> list[Path]:
    base = Path(root)
    if not base.exists():
        return []
    dirs: list[Path] = []
    for path in base.glob("*/pieces/*"):
        if path.is_dir() and path.name != "__pycache__":
            dirs.append(path)
    return sorted(dirs)
