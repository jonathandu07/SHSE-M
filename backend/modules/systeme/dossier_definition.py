from __future__ import annotations

"""Construction passive du dossier de definition SolidWorks.

Ce module ne calcule pas de piece, ne choisit pas de tolerance et ne genere
aucun fichier CAO. Il structure seulement les informations deja presentes dans
les rapports backend afin que le frontend reste consommateur passif.
"""

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence


STATUTS_DOSSIER = {
    "blocked",
    "partial",
    "ready_for_manual_modeling",
    "ready_for_assembly_check",
    "validated_by_calculation",
    "not_validated",
}


_DIMENSION_MARKERS = (
    "alesage",
    "bore",
    "course",
    "stroke",
    "diametre",
    "diameter",
    "rayon",
    "radius",
    "longueur",
    "length",
    "largeur",
    "width",
    "hauteur",
    "height",
    "epaisseur",
    "thickness",
    "entraxe",
    "portee",
    "surface",
    "volume",
    "masse",
    "gorge",
    "rainure",
    "groove",
    "filetage",
    "taraudage",
    "pas_",
    "jeu",
    "clearance",
    "tolerance",
    "x_",
    "y_",
    "z_",
)


PIECE_REQUIREMENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "piston": {
        "cotes": ("diametre_piston", "hauteur_piston", "alesage", "jeu_radial"),
        "interfaces": ("cylindre", "arbre_piston", "joint_piston"),
    },
    "cylindre": {
        "cotes": ("alesage", "course", "longueur_utile", "epaisseur_paroi"),
        "interfaces": ("piston", "couvercle_cylindre", "joint_piston"),
    },
    "corps_bielle": {
        "cotes": ("longueur_bielle", "diametre_axe_piston", "diametre_maneton", "section_fut"),
        "interfaces": ("arbre_piston", "vilebrequin", "roulement_aiguille_arbre"),
    },
    "bielle": {
        "cotes": ("longueur_bielle", "diametre_axe_piston", "diametre_maneton", "section_fut"),
        "interfaces": ("arbre_piston", "vilebrequin", "roulement_aiguille_arbre"),
    },
    "arbre_piston": {
        "cotes": ("longueur_totale", "diametre_portee", "diametre_exterieur", "longueur_coussinet"),
        "interfaces": ("piston", "bielle", "coussinet_arbre_piston"),
    },
    "arbre": {
        "cotes": ("diametre_arbre", "longueur_arbre", "portee", "clavette"),
        "interfaces": ("clavette_arbre", "roulement", "boite_crabots"),
    },
    "arbre_vilbrequin": {
        "cotes": ("diametre_tourillon", "diametre_maneton", "rayon_manivelle", "longueur"),
        "interfaces": ("vilebrequin", "roulement_aiguille_arbre_vilebrequin"),
    },
    "arbre_vilebrequin": {
        "cotes": ("diametre_tourillon", "diametre_maneton", "rayon_manivelle", "longueur"),
        "interfaces": ("vilebrequin", "roulement_aiguille_arbre_vilebrequin"),
    },
    "vilbrequin": {
        "cotes": ("diametre_tourillon", "diametre_maneton", "rayon_manivelle", "longueur"),
        "interfaces": ("bielle", "arbre_vilbrequin", "roulement_aiguille_arbre_vilebrequin"),
    },
    "vilebrequin": {
        "cotes": ("diametre_tourillon", "diametre_maneton", "rayon_manivelle", "longueur"),
        "interfaces": ("bielle", "arbre_vilebrequin", "roulement_aiguille_arbre_vilebrequin"),
    },
    "joint_piston": {
        "cotes": ("diametre_interieur", "section", "gorge", "squeeze"),
        "interfaces": ("piston", "cylindre"),
    },
    "deplaceur": {
        "cotes": ("diametre_exterieur", "diametre_interieur", "longueur", "jeu_radial"),
        "interfaces": ("joint_deplaceur", "cylindre"),
    },
    "joint_deplaceur": {
        "cotes": ("diametre_interieur", "diametre_exterieur", "section", "gorge", "squeeze"),
        "interfaces": ("deplaceur", "cylindre"),
    },
    "coussinet_arbre_piston": {
        "cotes": ("diametre_interieur", "diametre_exterieur", "longueur", "jeu_radial"),
        "interfaces": ("arbre_piston", "bielle"),
    },
    "roulement_aiguille_arbre": {
        "cotes": ("diametre_interieur", "diametre_exterieur", "largeur", "nombre_aiguilles"),
        "interfaces": ("arbre_piston", "bielle"),
    },
    "roulement_aiguille_arbre_vilebrequin": {
        "cotes": ("diametre_maneton", "diametre_exterieur", "largeur", "nombre_aiguilles"),
        "interfaces": ("vilebrequin", "bielle", "maneton"),
    },
    "couvercle_cylindre": {
        "cotes": ("diametre_bride", "epaisseur", "percage", "precharge"),
        "interfaces": ("cylindre", "vis_couvercle_cylindre", "joint"),
    },
    "vis_couvercle_cylindre": {
        "cotes": ("diametre_nominal", "longueur_vis", "filetage", "cercle_percage"),
        "interfaces": ("couvercle_cylindre", "cylindre"),
    },
    "clavette_arbre": {
        "cotes": ("largeur", "hauteur", "longueur", "rainure"),
        "interfaces": ("arbre", "moyeu"),
    },
}


_ROLE_BY_PIECE = {
    "piston": "transformer la pression gaz en effort alternatif transmis a la bielle",
    "cylindre": "guider le piston et contenir la pression de cycle",
    "corps_bielle": "transmettre l'effort alternatif entre piston et vilebrequin",
    "bielle": "transmettre l'effort alternatif entre piston et vilebrequin",
    "arbre_piston": "assurer l'interface pivot entre piston et bielle",
    "arbre": "transmettre le couple mecanique sur l'arbre moteur",
    "arbre_vilbrequin": "assurer l'interface arbre associee au vilebrequin",
    "arbre_vilebrequin": "assurer l'interface arbre associee au vilebrequin",
    "vilbrequin": "transformer le mouvement alternatif en rotation",
    "vilebrequin": "transformer le mouvement alternatif en rotation",
    "joint_piston": "assurer l'etancheite piston/cylindre",
    "deplaceur": "deplacer le volume de gaz entre zones thermiques",
    "joint_deplaceur": "assurer l'etancheite autour du deplaceur",
    "coussinet_arbre_piston": "assurer le guidage tribologique de l'arbre piston",
    "roulement_aiguille_arbre": "supporter la liaison pivot arbre piston/bielle",
    "roulement_aiguille_arbre_vilebrequin": "supporter la liaison pivot maneton/grande tete",
    "couvercle_cylindre": "fermer le cylindre et reprendre les efforts de pression",
    "vis_couvercle_cylindre": "appliquer la precharge de fermeture du couvercle",
    "clavette_arbre": "transmettre le couple entre arbre et moyeu",
}


def ajouter_dossier_definition_solidworks(
    rapport: Dict[str, Any],
    piece: str | None = None,
    *,
    famille: str = "moteur_thermique",
    composant_parent: str = "moteur_thermique",
    role_mecanique: str | None = None,
    pieces_interface: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Ajoute le bloc canonique au rapport d'une piece.

    Le rapport est modifie en place et retourne pour permettre un usage simple
    juste avant `return rapport`.
    """
    if not isinstance(rapport, dict):
        return rapport
    nom = str(piece or rapport.get("piece") or rapport.get("nom") or "piece_inconnue")
    key = _canonical_key(nom)
    requirements = PIECE_REQUIREMENTS.get(key) or PIECE_REQUIREMENTS.get(str(rapport.get("piece") or "").lower()) or {}

    cotes_connues = _collect_known_dimensions(rapport)
    cotes_manquantes = _collect_missing_dimensions(rapport, requirements.get("cotes", ()), cotes_connues)
    inconnues_bloquantes = _collect_blocking_unknowns(rapport)
    interfaces = _collect_interfaces(rapport, nom, pieces_interface or requirements.get("interfaces", ()))
    tolerances = _collect_rows(rapport, ("tolerances", "tolerances_et_jeux", "iso286", "usinage_precision"))
    jeux_ajustements = _collect_rows(rapport, ("jeux", "ajustements", "iso286", "contacts_tetes", "contact_fermeture"))
    surfaces = _collect_rows(rapport, ("surfaces_fonctionnelles", "surfaces_critiques"))
    contraintes_rdm = _collect_rows(
        rapport,
        (
            "contraintes",
            "contraintes_tete",
            "dimensionnement",
            "dimensionnements",
            "dimensionnement_evide",
            "flambage",
            "flambage_detaille",
            "fatigue",
            "contacts_tetes",
            "verifications",
        ),
    )
    limites_usage = _collect_rows(
        rapport,
        ("limites_usage", "verifications", "fatigue", "usure", "thermique", "tribologie", "frottements", "fuites"),
    )
    materiaux = _collect_rows(rapport, ("materiau", "materiaux", "material", "materials"))
    controles_qualite = _collect_rows(rapport, ("controles_qualite", "controle_qualite", "qualite"))
    features = _features_from_dimensions(cotes_connues)
    notes = _collect_notes(rapport)

    statut_validation = _validation_status(rapport, contraintes_rdm)
    statut = _definition_status(
        cotes_connues=cotes_connues,
        cotes_manquantes=cotes_manquantes,
        interfaces=interfaces,
        materiaux=materiaux,
        contraintes_rdm=contraintes_rdm,
        limites_usage=limites_usage,
        inconnues_bloquantes=inconnues_bloquantes,
        statut_validation=statut_validation,
    )

    dossier = {
        "objectif": "preparer la modelisation manuelle SolidWorks, pas generer un STEP",
        "statut": statut,
        "solidworks_ready": False,
        "step_generation": False,
        "schema_only": True,
        "final_geometry": False,
        "identification": {
            "nom_canonique": nom,
            "famille": famille,
            "composant_parent": composant_parent,
            "role_mecanique": role_mecanique or _ROLE_BY_PIECE.get(key),
            "pieces_en_interface": list(pieces_interface or requirements.get("interfaces", ())),
            "fonction_systeme": role_mecanique or _ROLE_BY_PIECE.get(key),
        },
        "features_a_modeliser": features,
        "cotes_connues": cotes_connues,
        "cotes_manquantes": cotes_manquantes,
        "interfaces": interfaces,
        "interfaces_assemblage": interfaces,
        "tolerances": tolerances,
        "jeux_ajustements": jeux_ajustements,
        "surfaces_fonctionnelles": surfaces,
        "contraintes_rdm": contraintes_rdm,
        "limites_usage": limites_usage,
        "materiaux": materiaux,
        "controles_qualite": controles_qualite,
        "statut_validation": statut_validation,
        "notes_modelisation": notes,
        "inconnues_bloquantes": inconnues_bloquantes,
    }
    rapport["dossier_definition_solidworks"] = dossier
    rapport.setdefault("interfaces_assemblage", interfaces)
    rapport["solidworks_ready"] = False
    rapport["step_export"] = False
    rapport["final_geometry"] = False
    cao = rapport.get("cao")
    if isinstance(cao, dict):
        cao["solidworks_ready"] = False
        cao["step_export"] = False
        cao["final_geometry"] = False
    return rapport


def _canonical_key(piece: str) -> str:
    key = str(piece or "").strip().lower()
    aliases = {
        "corps_bielle": "bielle",
        "arbre_moteur": "arbre",
    }
    return aliases.get(key, key)


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        try:
            return _jsonable(asdict(value))
        except Exception:
            return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


def _iter_leaf(data: Any, *, prefix: str = "", depth: int = 0, max_depth: int = 7) -> Iterable[tuple[str, Any]]:
    if depth > max_depth:
        return
    if isinstance(data, Mapping):
        for key, value in data.items():
            if str(key) in {"dossier_definition_solidworks"}:
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, Mapping):
                yield from _iter_leaf(value, prefix=path, depth=depth + 1, max_depth=max_depth)
            elif isinstance(value, (list, tuple)):
                continue
            else:
                yield path, value


def _collect_known_dimensions(rapport: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path, value in _iter_leaf(rapport):
        if value is None:
            continue
        low = path.lower()
        if not any(marker in low for marker in _DIMENSION_MARKERS):
            continue
        out[path] = {
            "valeur": _jsonable(value),
            "unite": _unit_from_path(path),
            "source": "rapport_piece_backend",
            "statut": "partial",
        }
    return out


def _unit_from_path(path: str) -> str | None:
    low = path.lower()
    if low.endswith("_m"):
        return "m"
    if low.endswith("_mm"):
        return "mm"
    if low.endswith("_pa"):
        return "Pa"
    if low.endswith("_n"):
        return "N"
    if low.endswith("_nm"):
        return "N.m"
    if low.endswith("_kg"):
        return "kg"
    if low.endswith("_c"):
        return "degC"
    if low.endswith("_k"):
        return "K"
    return None


def _collect_missing_dimensions(
    rapport: Mapping[str, Any],
    expected: Sequence[str],
    known: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    known_text = " ".join(known.keys()).lower()
    for name in expected:
        token = str(name).lower()
        if token and token not in known_text:
            out[token] = {
                "raison": "donnee de definition non presente dans le rapport piece",
                "source": "requirements_piece",
                "statut": "missing_required",
            }
    for item in _unknown_rows(rapport):
        name = str(item.get("nom") or item.get("champ") or item.get("name") or "")
        if not name:
            continue
        low = name.lower()
        if any(marker in low for marker in _DIMENSION_MARKERS):
            out.setdefault(low, dict(item))
    return out


def _unknown_rows(rapport: Mapping[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    inc = rapport.get("inconnues")
    if isinstance(inc, Mapping):
        for category, values in inc.items():
            if not isinstance(values, (list, tuple)):
                continue
            for item in values:
                row = dict(item) if isinstance(item, Mapping) else {"nom": str(item)}
                row.setdefault("categorie", str(category))
                out.append(row)
    for key in ("inconnues_cao", "missing_fields"):
        values = rapport.get(key)
        if isinstance(values, (list, tuple)):
            for item in values:
                row = dict(item) if isinstance(item, Mapping) else {"nom": str(item)}
                row.setdefault("categorie", key)
                out.append(row)
    return out


def _collect_blocking_unknowns(rapport: Mapping[str, Any]) -> list[dict[str, Any]]:
    blocking_categories = {"impossibles", "impossible", "bloquantes", "blocking", "missing_required"}
    rows = []
    for row in _unknown_rows(rapport):
        cat = str(row.get("categorie") or row.get("category") or row.get("statut") or row.get("status") or "").lower()
        if cat in blocking_categories or row.get("blocking") is True:
            rows.append(row)
    return rows


def _collect_interfaces(rapport: Mapping[str, Any], piece: str, expected: Sequence[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("interfaces_assemblage", "interfaces", "liaisons", "assemblage"):
        value = rapport.get(key)
        if isinstance(value, Mapping):
            for name, payload in value.items():
                row = dict(payload) if isinstance(payload, Mapping) else {"valeur": payload}
                row.setdefault("piece_a", piece)
                row.setdefault("piece_b", str(name))
                row.setdefault("fonction", str(name))
                rows.append(_normalize_interface(row))
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, Mapping):
                    row = dict(item)
                    row.setdefault("piece_a", piece)
                    rows.append(_normalize_interface(row))
    seen_pairs = {(str(r.get("piece_a")), str(r.get("piece_b")), str(r.get("fonction"))) for r in rows}
    for name in expected:
        sig = (piece, str(name), str(name))
        if sig not in seen_pairs:
            rows.append(
                _normalize_interface(
                    {
                        "piece_a": piece,
                        "piece_b": str(name),
                        "fonction": str(name),
                        "risque": "interface attendue non documentee dans le rapport piece",
                        "statut": "partial",
                    }
                )
            )
    return rows


def _normalize_interface(row: Mapping[str, Any]) -> dict[str, Any]:
    status = str(row.get("statut") or row.get("status") or "partial").lower()
    if status not in {"ok", "partial", "blocked"}:
        status = "partial"
    if status == "ok" and not (row.get("jeu_ou_serrage") or row.get("tolerance")):
        status = "partial"
    return {
        "piece_a": row.get("piece_a"),
        "piece_b": row.get("piece_b"),
        "fonction": row.get("fonction") or row.get("role"),
        "type_liaison": row.get("type_liaison") or row.get("liaison") or row.get("type"),
        "cote_interface": row.get("cote_interface") or row.get("cote") or row.get("diametre") or row.get("diametre_interface_m"),
        "jeu_ou_serrage": row.get("jeu_ou_serrage") or row.get("jeu") or row.get("serrage"),
        "tolerance": row.get("tolerance"),
        "effort_transmis": row.get("effort_transmis") or row.get("effort") or row.get("charge"),
        "risque": row.get("risque") or row.get("warning"),
        "statut": status,
    }


def _collect_rows(rapport: Mapping[str, Any], keys: Sequence[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in keys:
        value = rapport.get(key)
        if isinstance(value, Mapping):
            for name, payload in value.items():
                row = dict(payload) if isinstance(payload, Mapping) else {"valeur": payload}
                row.setdefault("nom", str(name))
                row.setdefault("source", key)
                if _has_meaningful_value(row):
                    out.append(_jsonable(row))
        elif isinstance(value, (list, tuple)):
            for item in value:
                row = dict(item) if isinstance(item, Mapping) else {"valeur": item}
                row.setdefault("source", key)
                if _has_meaningful_value(row):
                    out.append(_jsonable(row))
    return out


def _has_meaningful_value(row: Mapping[str, Any]) -> bool:
    for key, value in row.items():
        if str(key) in {"nom", "source", "statut", "status"}:
            continue
        if value not in (None, "", [], {}):
            return True
    return False


def _features_from_dimensions(cotes: Mapping[str, Any]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    for path in cotes:
        low = path.lower()
        feature_type = None
        if any(token in low for token in ("diametre", "diameter", "alesage", "bore")):
            feature_type = "diameter"
        elif any(token in low for token in ("longueur", "length", "hauteur", "height", "course", "stroke")):
            feature_type = "length"
        elif any(token in low for token in ("gorge", "rainure", "groove")):
            feature_type = "groove"
        elif any(token in low for token in ("filetage", "taraudage", "pas_")):
            feature_type = "thread"
        elif any(token in low for token in ("portee", "surface")):
            feature_type = "functional_surface"
        if feature_type is None:
            continue
        features.append(
            {
                "type": feature_type,
                "label": path.split(".")[-1],
                "source": "rapport_piece_backend",
                "schematic": True,
                "final_geometry": False,
            }
        )
    return features


def _collect_notes(rapport: Mapping[str, Any]) -> list[dict[str, Any]]:
    notes = [
        {
            "nom": "orientation",
            "texte": "Dossier de definition pour modelisation manuelle SolidWorks ; aucun export CAO n'est genere.",
        }
    ]
    for item in rapport.get("notes_modele") or []:
        notes.append({"texte": str(item), "source": "notes_modele"})
    return notes


def _validation_status(rapport: Mapping[str, Any], contraintes: Sequence[Mapping[str, Any]]) -> str:
    explicit = str(rapport.get("statut_validation") or rapport.get("validation_status") or "").lower()
    if explicit in {"validated_by_calculation", "partial", "not_validated"}:
        return explicit
    validation = rapport.get("validation") or rapport.get("verifications")
    if isinstance(validation, Mapping):
        values = [v for v in validation.values() if isinstance(v, bool)]
        if values and all(values):
            return "validated_by_calculation"
    if contraintes:
        return "partial"
    return "not_validated"


def _definition_status(
    *,
    cotes_connues: Mapping[str, Any],
    cotes_manquantes: Mapping[str, Any],
    interfaces: Sequence[Mapping[str, Any]],
    materiaux: Sequence[Mapping[str, Any]],
    contraintes_rdm: Sequence[Mapping[str, Any]],
    limites_usage: Sequence[Mapping[str, Any]],
    inconnues_bloquantes: Sequence[Mapping[str, Any]],
    statut_validation: str,
) -> str:
    if not cotes_connues:
        return "blocked"
    if inconnues_bloquantes:
        return "blocked"
    if not interfaces or any(str(row.get("statut")) == "blocked" for row in interfaces):
        return "partial"
    has_open_interfaces = any(str(row.get("statut")) != "ok" for row in interfaces)
    complete_enough = bool(materiaux and contraintes_rdm and limites_usage and not cotes_manquantes and not has_open_interfaces)
    if complete_enough and statut_validation == "validated_by_calculation":
        return "validated_by_calculation"
    if complete_enough:
        return "ready_for_manual_modeling"
    if interfaces and not has_open_interfaces:
        return "ready_for_assembly_check"
    return "partial"


__all__ = [
    "PIECE_REQUIREMENTS",
    "STATUTS_DOSSIER",
    "ajouter_dossier_definition_solidworks",
]
