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


def _aliases(name: str) -> tuple[str, ...]:
    key = str(name or "").strip()
    low = key.lower()
    return tuple(dict.fromkeys((key, low, *(_PIECE_ALIASES.get(low) or ()))))


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
    value = get_path(report, path)
    return {
        "path": path,
        "label": label or path.split(".")[-1],
        "value": value,
        "unit": unit,
        "status": STATUS_AVAILABLE if value is not None else STATUS_MISSING_REQUIRED,
        "source": "backend",
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
        if row["status"] == STATUS_AVAILABLE:
            used.append(row)
        else:
            missing.append(row)
    return {
        "ok": not missing,
        "status": STATUS_AVAILABLE if not missing else STATUS_MISSING_REQUIRED,
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
            out.append({"path": path, "label": path.split(".")[-1], "value": value, "unit": unit, "source": "backend"})
    return out


def get_backend_graphs(global_report: Mapping[str, Any], piece_name: str | None = None) -> list[dict[str, Any]]:
    graphs: list[dict[str, Any]] = []
    for root in ("mechanical_graphs.graphiques", "mechanical_graphs.graphs", "cao_dossier.graphiques"):
        for item in safe_list(get_path(global_report, root)):
            if not isinstance(item, Mapping):
                continue
            row = dict(item)
            if piece_name:
                text = " ".join(str(row.get(k) or "") for k in ("id", "piece", "title")).lower()
                aliases = _aliases(piece_name)
                if not any(alias.lower() in text for alias in aliases):
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
            text = " ".join(str(row.get(k) or "") for k in ("id", "piece", "title")).lower()
            if not any(alias.lower() in text for alias in _aliases(piece_name)):
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
            text = " ".join(str(row.get(k) or "") for k in ("id", "piece", "title")).lower()
            if not any(alias.lower() in text for alias in _aliases(piece_name)):
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
