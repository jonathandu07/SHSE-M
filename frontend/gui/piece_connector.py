# frontend/gui/piece_connector.py
"""
Connecteur universel pièces / composants STHOME - SHSE-M.

Objectif :
- mapper un nom de pièce vers l'instance Python réelle du backend ;
- injecter les paramètres moteur courants ;
- récupérer les données calculées depuis les rapports backend ;
- hydrater les objets avec les attributs calculés ;
- éviter toute cote inventée côté frontend.

Règle fondamentale :
- une valeur vient soit de engine_params,
- soit de db_data / rapport backend,
- soit elle reste None et sera signalée comme inconnue.
"""

from __future__ import annotations

import copy
import importlib
import inspect
import math
import traceback
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple


# =============================================================================
# Types
# =============================================================================

Factory = Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Any]


@dataclass
class ConnectorIssue:
    piece: str
    niveau: str
    message: str
    source: str = ""
    exception: str = ""


@dataclass
class ConnectorBuildMeta:
    piece_name: str
    canonical_key: str
    factory_found: bool
    generic_used: bool = False
    hydrated: bool = False
    report_attached: bool = False
    params_count: int = 0
    db_data_present: bool = False
    issues: list[ConnectorIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# =============================================================================
# Helpers stricts
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_mapping(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _is_finite(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _f(data: Mapping[str, Any], *keys: str) -> Optional[float]:
    """
    Récupère strictement un float depuis plusieurs clés possibles.
    Ne fournit jamais de défaut.
    """
    for key in keys:
        if key not in data:
            continue

        value = data.get(key)

        if value is None or value == "":
            continue

        if _is_finite(value):
            return float(value)

        if isinstance(value, str):
            raw = value.strip().replace(",", ".")
            if not raw:
                continue
            try:
                out = float(raw)
            except (TypeError, ValueError):
                continue
            if math.isfinite(out):
                return out

    return None


def _i(data: Mapping[str, Any], *keys: str) -> Optional[int]:
    for key in keys:
        value = _f(data, key)
        if value is None:
            continue

        rounded = round(value)
        if abs(value - rounded) <= 1e-9:
            return int(rounded)

    return None


def _s(data: Mapping[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue

        text = str(value).strip()
        if text:
            return text

    return None


def _clean_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")

    return "_".join(part for part in "".join(out).split("_") if part)


def _merge_non_none(base: Optional[Mapping[str, Any]], extra: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Fusion prudente.
    Les valeurs non None de extra écrasent base.
    """
    out = dict(base or {})

    if not isinstance(extra, Mapping):
        return out

    for key, value in extra.items():
        if value is None:
            continue

        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[str(key)] = _merge_non_none(out.get(key), value)
        else:
            out[str(key)] = value

    return out


def _jsonable(value: Any, *, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Mapping):
        return {str(k): _jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]

    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return {
                "type": type(value).__name__,
                "attributs": _jsonable(
                    {
                        k: v
                        for k, v in vars(value).items()
                        if not k.startswith("_") and not callable(v)
                    },
                    depth=depth + 1,
                    max_depth=max_depth,
                ),
            }
        except Exception:
            pass

    return str(value)


# =============================================================================
# Normalisation des paramètres
# =============================================================================

PARAM_ALIASES: Dict[str, str] = {
    # Architecture / moteur
    "architecture": "architecture_moteur",
    "architecture_forcee": "architecture_forcee",
    "architecture_moteur": "architecture_moteur",

    "n_cyl": "nombre_cylindres",
    "nb_cyl": "nombre_cylindres",
    "nb_cylindres": "nombre_cylindres",
    "nombre_cylindre": "nombre_cylindres",
    "nombre_cylindres": "nombre_cylindres",
    "N_cyl": "nombre_cylindres",

    "rpm": "rpm_nominal",
    "rpm_moteur": "rpm_nominal",
    "rpm_moteur_nominal": "rpm_nominal",
    "vitesse_moteur_thermique_rpm": "rpm_nominal",
    "regime_moteur": "rpm_nominal",
    "regime_tr_min": "rpm_nominal",
    "RPM": "rpm_nominal",

    "pme": "pme_pa",
    "PME": "pme_pa",
    "PME_Pa": "pme_pa",
    "pme_nominale_pa": "pme_pa",
    "pression_moyenne_effective_pa": "pme_pa",

    "Pmax_Pa": "pression_max_pa",
    "pmax_pa": "pression_max_pa",
    "pression_max": "pression_max_pa",
    "pression_max_pa": "pression_max_pa",
    "pression_service": "pression_service_pa",
    "pression_service_pa": "pression_service_pa",

    # Géométrie
    "Bore_mm": "alesage_mm",
    "bore_mm": "alesage_mm",
    "alesage_mm": "alesage_mm",
    "diametre_piston_mm": "alesage_mm",

    "Stroke_mm": "course_mm",
    "stroke_mm": "course_mm",
    "course_mm": "course_mm",
    "course_piston_mm": "course_mm",

    "bore_m": "alesage_m",
    "alesage": "alesage_m",
    "alesage_m": "alesage_m",
    "diametre_piston": "alesage_m",
    "diametre_piston_m": "alesage_m",

    "stroke_m": "course_m",
    "course": "course_m",
    "course_m": "course_m",
    "course_piston": "course_m",
    "course_piston_m": "course_m",

    # Puissances / couples
    "couple_max_Nm": "couple_max_Nm",
    "couple_max_nm": "couple_max_Nm",
    "couple_moteur_max_Nm": "couple_max_Nm",
    "Couple_max_Nm": "couple_max_Nm",
    "couple_moyen_Nm": "couple_moyen_Nm",

    "force_bielle_N": "force_bielle_N",
    "Force_bielle_N": "force_bielle_N",

    "P_bus_dc_design_w": "puissance_bus_dc_w",
    "puissance_bus_dc_w": "puissance_bus_dc_w",
    "production_electrique_sortie_w": "production_electrique_sortie_w",
    "puissance_moteur_requise_W": "puissance_moteur_requise_W",

    # Batterie / électrique
    "tension_nominale_v": "tension_nominale_v",
    "tension_bus_dc_v": "tension_nominale_v",
    "tension_bus_v": "tension_nominale_v",
    "energie_batterie_kwh": "energie_batterie_kwh",
    "energie_utile_imposee_kwh": "energie_batterie_kwh",

    # Matériaux
    "materiau_cylindre": "materiau_cylindre_cle",
    "materiau_piston": "materiau_piston_cle",
    "materiau_bielle": "materiau_bielle_cle",
    "materiau_vilebrequin": "materiau_vilebrequin_cle",
    "materiau_axe_piston": "materiau_axe_piston_cle",
    "materiau_coussinet": "materiau_coussinet_cle",
    "materiau_culasse": "materiau_culasse_cle",
    "materiau_joint_piston": "materiau_joint_piston_cle",
    "materiau_deplaceur": "materiau_deplaceur_cle",
    "materiau_joint_deplaceur": "materiau_joint_deplaceur_cle",
}


def normalize_engine_params(engine_params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}

    for raw_key, value in dict(engine_params or {}).items():
        key = PARAM_ALIASES.get(str(raw_key), PARAM_ALIASES.get(_clean_name(raw_key), str(raw_key)))
        params[key] = value

        # Conserver aussi la clé brute si elle peut servir au backend.
        params.setdefault(str(raw_key), value)

    # Conversion mm -> m, uniquement si la valeur mm existe explicitement.
    alesage_mm = _f(params, "alesage_mm")
    if alesage_mm is not None and params.get("alesage_m") is None:
        params["alesage_m"] = alesage_mm / 1000.0

    course_mm = _f(params, "course_mm")
    if course_mm is not None and params.get("course_m") is None:
        params["course_m"] = course_mm / 1000.0

    # Entiers
    n_cyl = _i(params, "nombre_cylindres")
    if n_cyl is not None:
        params["nombre_cylindres"] = n_cyl

    return params


def extract_params_from_backend_payload(db_data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Récupère les paramètres disponibles dans un payload backend.
    Ne calcule pas de cotes.
    """
    data = _safe_mapping(db_data)
    if not data:
        return {}

    out: Dict[str, Any] = {}

    def put(key: str, value: Any) -> None:
        if value is not None and value != "":
            out[key] = value

    # Payloads fréquents
    rapport = _safe_dict(data.get("rapport"))
    inventaire = _safe_dict(data.get("inventaire"))
    construction = _safe_dict(data.get("construction"))
    attrs = _first_mapping(
        data.get("objet_serialise"),
        data.get("objet"),
        data.get("attributs"),
        inventaire.get("objet"),
        inventaire.get("attributs"),
    )

    # Résumé GUI ou synthèse système si le payload est global.
    resume = _safe_dict(data.get("resume_gui"))
    put("architecture_moteur", resume.get("Architecture"))
    put("nombre_cylindres", resume.get("N_cyl"))
    put("alesage_mm", resume.get("Bore_mm"))
    put("course_mm", resume.get("Stroke_mm"))
    put("rpm_nominal", resume.get("RPM"))
    put("pme_pa", _first_non_empty(resume.get("PME_Pa"), resume.get("PME")))
    put("pression_max_pa", resume.get("Pmax_Pa"))
    put("couple_max_Nm", resume.get("Couple_max_Nm"))
    put("force_bielle_N", resume.get("Force_bielle_N"))
    put("puissance_bus_dc_w", resume.get("P_bus_dc_design_w"))
    put("energie_batterie_kwh", resume.get("energie_batterie_kwh"))

    # Rapport pièce : on récupère les sous-blocs habituels.
    for block_name in (
        "entrees",
        "entrees_normalisees",
        "geometrie",
        "dimensions",
        "dimensionnement",
        "dimensionnements",
        "contraintes",
        "efforts",
        "cinematique",
        "thermique",
        "interfaces",
        "assemblage",
        "cao",
        "resultats",
        "performances",
    ):
        block = _safe_dict(rapport.get(block_name))
        for key, value in block.items():
            if isinstance(value, (dict, list, tuple)):
                continue
            put(str(key), value)

    # Inventaire / construction / attributs sérialisés
    for source in (inventaire, construction, attrs):
        for key, value in _safe_dict(source).items():
            if isinstance(value, (dict, list, tuple)):
                continue
            put(str(key), value)

    return normalize_engine_params(out)


# =============================================================================
# Construction dynamique
# =============================================================================

def _import_class(module_path: str, class_name: str) -> Any:
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _call_constructor(cls: Any, kwargs: Mapping[str, Any]) -> Any:
    """
    Appelle le constructeur en filtrant les kwargs selon sa signature.

    Si la signature est inaccessible, on tente avec tous les kwargs non None.
    """
    clean = {str(k): v for k, v in dict(kwargs or {}).items() if v is not None}

    try:
        sig = inspect.signature(cls)
    except Exception:
        return cls(**clean)

    accepted: Dict[str, Any] = {}

    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

    if has_var_kw:
        accepted = clean
    else:
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            if name in clean:
                accepted[name] = clean[name]

    return cls(**accepted)


def _construct(module_path: str, class_name: str, kwargs: Mapping[str, Any]) -> Any:
    cls = _import_class(module_path, class_name)
    return _call_constructor(cls, kwargs)


# =============================================================================
# Factories pièces
# =============================================================================

def _make_cylindre(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.cylindre",
        "Cylindre",
        {
            "alesage_m": _f(ep, "alesage_m"),
            "course_m": _f(ep, "course_m"),
            "longueur_utile_m": _f(ep, "longueur_utile_m"),
            "pression_service_pa": _f(ep, "pression_service_pa"),
            "pression_max_pa": _f(ep, "pression_max_pa"),
            "materiau_cle": _s(ep, "materiau_cylindre_cle"),
        },
    )


def _make_piston(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    cylindre = _safe_child("cylindre", ep, db_data)
    return _construct(
        "backend.components.moteur_thermique.pieces.piston",
        "Piston",
        {
            "cylindre": cylindre,
            "alesage_nominal_m": _f(ep, "alesage_m"),
            "course_m": _f(ep, "course_m"),
            "materiau_piston_cle": _s(ep, "materiau_piston_cle"),
        },
    )


def _make_bielle(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    piston = _safe_child("piston", ep, db_data)
    return _construct(
        "backend.components.moteur_thermique.pieces.bielle",
        "CorpsBielle",
        {
            "piston": piston,
            "longueur_bielle_m": _f(ep, "longueur_bielle_m", "entraxe_bielle_m"),
            "materiau_cle": _s(ep, "materiau_bielle_cle"),
        },
    )


def _make_arbre_vilebrequin(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.arbre_vilbrequin",
        "ArbreVilbrequin",
        {
            "course_m": _f(ep, "course_m"),
            "materiau_cle": _s(ep, "materiau_vilebrequin_cle"),
        },
    )


def _make_arbre_piston(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.arbre_piston",
        "ArbrePiston",
        {
            "diametre_fut_central_m": _f(ep, "diametre_axe_piston_m", "diametre_fut_central_m"),
            "longueur_totale_m": _f(ep, "longueur_axe_piston_m", "longueur_totale_m"),
            "materiau_cle": _s(ep, "materiau_axe_piston_cle"),
        },
    )


def _make_coussinet(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.coussinet_arbre_piston",
        "CoussinetArbrePiston",
        {
            "diametre_portee_m": _f(ep, "diametre_coussinet_m", "diametre_portee_m"),
            "longueur_coussinet_m": _f(ep, "longueur_coussinet_m"),
            "materiau_coussinet": _s(ep, "materiau_coussinet_cle"),
        },
    )


def _make_couvercle(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.couvercle_cylindre",
        "CouvercleCylindre",
        {
            "diametre_ouverture_m": _f(ep, "diametre_ouverture_culasse_m", "diametre_ouverture_m"),
            "rayon_externe_m": _f(ep, "rayon_externe_culasse_m", "rayon_externe_m"),
            "epaisseur_m": _f(ep, "epaisseur_culasse_m", "epaisseur_m"),
            "materiau_cle": _s(ep, "materiau_culasse_cle"),
        },
    )


def _make_joint_piston(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.joint_piston",
        "JointPiston",
        {
            "diametre_interieur_cylindre_m": _f(ep, "alesage_m", "diametre_interieur_cylindre_m"),
            "materiau_joint_cle": _s(ep, "materiau_joint_piston_cle"),
        },
    )


def _make_alternateur(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.alternateur.alternateur",
        "Alternateur",
        {
            "puissance_nominale_w": _f(ep, "puissance_alternateur_w", "production_electrique_sortie_w"),
            "tension_nominale_v": _f(ep, "tension_nominale_v"),
            "courant_nominal_a": _f(ep, "courant_alt_a"),
            "rendement": _f(ep, "rendement_alternateur", "rendement_liaison_meca_alt"),
            "vitesse_rotation_rpm": _f(ep, "vitesse_alternateur_rpm"),
        },
    )


def _make_batterie(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.batterie.batterie",
        "Batterie",
        {
            "tension_nominale_v": _f(ep, "tension_nominale_v"),
            "energie_utile_kwh": _f(ep, "energie_batterie_kwh"),
            "capacite_ah": _f(ep, "capacite_ah"),
            "puissance_pic_kw": _f(ep, "puissance_pic_kw"),
        },
    )


def _make_architecture(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.architechture.architecture",
        "Architecture",
        {
            "architecture_forcee": _s(ep, "architecture_forcee", "architecture_moteur"),
            "nombre_cylindres": _i(ep, "nombre_cylindres"),
            "alesage_m": _f(ep, "alesage_m"),
            "course_m": _f(ep, "course_m"),
            "pme_pa": _f(ep, "pme_pa"),
            "rpm_nominal": _f(ep, "rpm_nominal"),
        },
    )


def _make_arbre(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.arbre",
        "ArbreMoteur",
        {
            "couple_max_Nm": _f(ep, "couple_max_Nm"),
            "rpm": _f(ep, "rpm_nominal"),
            "nombre_cylindres": _i(ep, "nombre_cylindres"),
            "entraxe_cylindres_m": _f(ep, "entraxe_cylindres_m"),
            "diametre_externe_cylindre_m": _f(ep, "diametre_externe_cylindre_m"),
            "diametre_arbre_m": _f(ep, "diametre_arbre_m"),
        },
    )


def _make_moteur_electrique(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    puissance = _f(ep, "puissance_max_w", "puissance_moteur_w", "puissance_bus_dc_w")
    regime = _f(ep, "regime_max_rpm")
    couple = _f(ep, "couple_max_nm", "couple_max_Nm")
    if puissance is None or regime is None or couple is None:
        return None
    return _construct(
        "backend.components.moteur_electrique.moteur_electrique",
        "MoteurElectrique",
        {
            "puissance_max_w": puissance,
            "regime_max_rpm": regime,
            "couple_max_nm": couple,
            "rendement_moteur": _f(ep, "rendement_moteur"),
            "tension_bus_v": _f(ep, "tension_nominale_v"),
        },
    )


def _make_boite_crabots(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.boite_crabots.boite_crabots",
        "BoiteCrabots",
        {
            "rapports": ep.get("rapports_boite_candidates"),
            "rendement": _f(ep, "rendement_boite"),
            "facteur_service": _f(ep, "facteur_service_boite"),
            "couple_max_nm": _f(ep, "couple_max_Nm", "couple_max_nm"),
            "rpm_entree": _f(ep, "rpm_nominal"),
        },
    )


def _make_moteur_thermique(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.moteur_thermique",
        "MoteurThermique",
        {
            "nombre_cylindres": _i(ep, "nombre_cylindres"),
            "alesage_m": _f(ep, "alesage_m"),
            "course_m": _f(ep, "course_m"),
            "rpm_nominal": _f(ep, "rpm_nominal"),
            "pme_nominale_pa": _f(ep, "pme_pa"),
            "architecture": _s(ep, "architecture_moteur", "architecture_forcee"),
        },
    )


def _make_deplaceur(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    cylindre = _safe_child("cylindre", ep, db_data)
    return _construct(
        "backend.components.moteur_thermique.pieces.deplaceur",
        "Deplaceur",
        {
            "cylindre": cylindre,
            "diametre_exterieur_m": _f(ep, "diametre_deplaceur_exterieur_m", "diametre_exterieur_deplaceur_m"),
            "diametre_interieur_m": _f(ep, "diametre_deplaceur_interieur_m", "diametre_interieur_deplaceur_m"),
            "longueur_totale_m": _f(ep, "longueur_deplaceur_m", "longueur_totale_deplaceur_m"),
            "materiau_cle": _s(ep, "materiau_deplaceur_cle"),
        },
    )


def _make_joint_deplaceur(ep: Dict[str, Any], db_data: Optional[Dict[str, Any]] = None) -> Any:
    return _construct(
        "backend.components.moteur_thermique.pieces.joint_deplaceur",
        "JointDeplaceur",
        {
            "alesage_cylindre_m": _f(ep, "alesage_m"),
            "materiau_joint_cle": _s(ep, "materiau_joint_deplaceur_cle"),
        },
    )


# =============================================================================
# Registre
# =============================================================================

_CONNECTORS: Dict[str, Factory] = {
    "piston": _make_piston,
    "cylindre": _make_cylindre,
    "bielle": _make_bielle,
    "corps_bielle": _make_bielle,

    "arbre_vilebrequin": _make_arbre_vilebrequin,
    "arbre_vilbrequin": _make_arbre_vilebrequin,
    "vilebrequin": _make_arbre_vilebrequin,
    "vilbrequin": _make_arbre_vilebrequin,

    "arbre": _make_arbre,
    "arbre_moteur": _make_arbre,
    "arbremoteur": _make_arbre,

    "arbre_piston": _make_arbre_piston,
    "axe_piston": _make_arbre_piston,

    "coussinet": _make_coussinet,
    "coussinet_arbre_piston": _make_coussinet,

    "couvercle": _make_couvercle,
    "couvercle_cylindre": _make_couvercle,
    "culasse": _make_couvercle,

    "joint_piston": _make_joint_piston,
    "segment": _make_joint_piston,
    "segments": _make_joint_piston,

    "alternateur": _make_alternateur,
    "batterie": _make_batterie,
    "architecture": _make_architecture,
    "moteur_electrique": _make_moteur_electrique,
    "boite_crabots": _make_boite_crabots,
    "boite": _make_boite_crabots,
    "moteur_thermique": _make_moteur_thermique,

    "deplaceur": _make_deplaceur,
    "déplaceur": _make_deplaceur,
    "joint_deplaceur": _make_joint_deplaceur,
    "joint_déplaceur": _make_joint_deplaceur,
}


def register_piece_connector(name: str, factory: Factory) -> None:
    """
    Permet d'ajouter une pièce sans modifier le registre principal.
    """
    key = canonical_piece_key(name)
    _CONNECTORS[key] = factory


def available_piece_connectors() -> Tuple[str, ...]:
    return tuple(sorted(_CONNECTORS.keys()))


def canonical_piece_key(piece_name: str) -> str:
    key = _clean_name(piece_name)

    alias = {
        "arbre_vilbrequin": "arbre_vilebrequin",
        "vilbrequin": "arbre_vilebrequin",
        "vilebrequin": "arbre_vilebrequin",
        "culasse": "couvercle_cylindre",
        "segment": "joint_piston",
        "segments": "joint_piston",
        "boite": "boite_crabots",
        "déplaceur": "deplaceur",
        "deplaceur": "deplaceur",
    }

    return alias.get(key, key)


# =============================================================================
# Hydratation backend
# =============================================================================

def _extract_attrs(db_data: Mapping[str, Any]) -> Dict[str, Any]:
    inventaire = _first_mapping(db_data.get("inventaire"))

    attrs = _first_mapping(
        db_data.get("objet_serialise"),
        db_data.get("objet"),
        inventaire.get("objet"),
        inventaire.get("objet_serialise"),
        db_data.get("attributs"),
        inventaire.get("attributs"),
    )

    if attrs:
        return attrs

    # Si aucun objet sérialisé, on prend quelques blocs utiles du rapport.
    rapport = _first_mapping(db_data.get("rapport"), inventaire.get("rapport"))
    extracted: Dict[str, Any] = {}

    for block_name in (
        "entrees",
        "entrees_normalisees",
        "geometrie",
        "dimensions",
        "dimensionnement",
        "contraintes",
        "efforts",
        "cinematique",
        "thermique",
        "interfaces",
        "assemblage",
        "cao",
        "resultats",
    ):
        block = _safe_dict(rapport.get(block_name))
        for key, value in block.items():
            if isinstance(value, (dict, list, tuple)):
                continue
            extracted.setdefault(str(key), value)

    return extracted


def _extract_report(db_data: Mapping[str, Any]) -> Dict[str, Any]:
    inventaire = _first_mapping(db_data.get("inventaire"))

    return _first_mapping(
        db_data.get("rapport"),
        inventaire.get("rapport"),
        db_data.get("analyse"),
        db_data.get("resultats"),
        db_data.get("data"),
    )


def _apply_attrs(target: Any, attrs: Mapping[str, Any], *, depth: int = 0, max_depth: int = 5) -> None:
    if target is None or not isinstance(attrs, Mapping):
        return

    if depth > max_depth:
        return

    for key, value in attrs.items():
        key = str(key)

        if not key or key.startswith("_"):
            continue

        current = getattr(target, key, None)

        if callable(current):
            continue

        if isinstance(value, Mapping) and current is not None and hasattr(current, "__dict__"):
            _apply_attrs(current, value, depth=depth + 1, max_depth=max_depth)
            continue

        try:
            setattr(target, key, copy.deepcopy(value))
        except Exception:
            try:
                setattr(target, key, value)
            except Exception:
                pass


def _attach_report_methods(piece_obj: Any, rapport: Mapping[str, Any]) -> bool:
    if piece_obj is None or not isinstance(rapport, Mapping) or not rapport:
        return False

    frozen_report = copy.deepcopy(dict(rapport))

    def mocked_analyser(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return copy.deepcopy(frozen_report)

    def mocked_calculer(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return copy.deepcopy(frozen_report)

    attached = False

    try:
        setattr(piece_obj, "analyser", mocked_analyser)
        attached = True
    except Exception:
        pass

    try:
        setattr(piece_obj, "calculer", mocked_calculer)
        attached = True
    except Exception:
        pass

    return attached


def hydrate_piece(piece_obj: Any, db_data: Optional[Dict[str, Any]]) -> Any:
    """
    Force l'injection des données calculées backend dans une instance de pièce.

    Priorité :
    1. objet_serialise / objet / attributs ;
    2. blocs utiles du rapport ;
    3. remplacement analyser()/calculer() par le rapport déjà calculé.
    """
    if piece_obj is None or not isinstance(db_data, dict):
        return piece_obj

    attrs = _extract_attrs(db_data)
    if attrs:
        _apply_attrs(piece_obj, attrs)

    rapport = _extract_report(db_data)
    report_attached = _attach_report_methods(piece_obj, rapport)

    try:
        setattr(piece_obj, "_backend_payload", copy.deepcopy(_jsonable(db_data)))
        setattr(piece_obj, "_backend_report_attached", report_attached)
    except Exception:
        pass

    return piece_obj


# =============================================================================
# Generic fallback
# =============================================================================

def _build_generic_piece(
    piece_name: str,
    engine_params: Mapping[str, Any],
    db_data: Optional[Dict[str, Any]] = None,
    *,
    meta: Optional[ConnectorBuildMeta] = None,
) -> Any:
    class GenericPiece:
        def __init__(self) -> None:
            self.nom = piece_name
            self.nom_technique = canonical_piece_key(piece_name)
            self.generic_piece = True

        def analyser(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            payload = getattr(self, "_backend_payload_source", None)
            rapport = _extract_report(payload) if isinstance(payload, dict) else {}
            if rapport:
                return copy.deepcopy(rapport)

            return {
                "note": "Pièce générique frontend : classe backend réelle indisponible.",
                "piece": self.nom,
                "inconnues": {
                    "partielles": [
                        {
                            "nom": self.nom,
                            "raison": "Factory backend absente ou instanciation impossible.",
                        }
                    ]
                },
            }

        def calculer(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            return self.analyser(*args, **kwargs)

    piece = GenericPiece()

    for key, value in dict(engine_params or {}).items():
        if key.startswith("_"):
            continue
        try:
            setattr(piece, key, copy.deepcopy(value))
        except Exception:
            pass

    if db_data:
        try:
            setattr(piece, "_backend_payload_source", copy.deepcopy(db_data))
        except Exception:
            pass
        piece = hydrate_piece(piece, db_data)

    if meta:
        meta.generic_used = True
        try:
            setattr(piece, "_connector_meta", copy.deepcopy(_jsonable(meta.__dict__)))
        except Exception:
            pass

    return piece


# =============================================================================
# Construction sécurisée d'enfants
# =============================================================================

def _safe_child(piece_name: str, ep: Dict[str, Any], db_data: Optional[Dict[str, Any]]) -> Any:
    """
    Construit une dépendance enfant sans lever d'exception.
    En cas d'échec, renvoie une pièce générique hydratable.
    """
    try:
        return get_piece_instance(
            piece_name,
            ep,
            db_data=db_data,
            allow_generic_on_failure=True,
            silent=True,
        )
    except Exception:
        return _build_generic_piece(piece_name, ep, db_data)


# =============================================================================
# API publique
# =============================================================================

def get_piece_instance(
    piece_name: str,
    engine_params: Optional[Mapping[str, Any]],
    db_data: Optional[Dict[str, Any]] = None,
    *,
    allow_generic_on_failure: bool = False,
    silent: bool = False,
) -> Optional[Any]:
    """
    Instancie la classe Python réelle d'une pièce avec les paramètres moteur,
    puis l'hydrate avec les données backend si elles existent.

    Compatibilité :
    - conserve la signature historique : get_piece_instance(piece_name, engine_params, db_data=None)
    - ajoute seulement des options keyword-only.

    Retour :
    - instance backend réelle si possible ;
    - GenericPiece si factory absente/échec et données disponibles ou allow_generic_on_failure=True ;
    - None si échec strict sans fallback.
    """
    canonical = canonical_piece_key(piece_name)

    db_params = extract_params_from_backend_payload(db_data)
    user_params = normalize_engine_params(engine_params)

    # Priorité à la saisie / engine_params. Le backend remplit les trous.
    merged_params = _merge_non_none(db_params, user_params)
    merged_params = normalize_engine_params(merged_params)

    meta = ConnectorBuildMeta(
        piece_name=str(piece_name),
        canonical_key=canonical,
        factory_found=canonical in _CONNECTORS,
        params_count=len(merged_params),
        db_data_present=isinstance(db_data, dict),
    )

    factory = _CONNECTORS.get(canonical)

    if factory is None:
        meta.issues.append(
            ConnectorIssue(
                piece=str(piece_name),
                niveau="warning",
                message=f"Aucune factory enregistrée pour la pièce {piece_name!r}.",
                source="piece_connector.get_piece_instance",
            )
        )
        if allow_generic_on_failure or db_data:
            return _build_generic_piece(piece_name, merged_params, db_data, meta=meta)
        return None

    try:
        piece = factory(merged_params, db_data)

        if db_data:
            piece = hydrate_piece(piece, db_data)
            meta.hydrated = True
            meta.report_attached = bool(getattr(piece, "_backend_report_attached", False))

        try:
            setattr(piece, "_connector_meta", copy.deepcopy(_jsonable(meta.__dict__)))
            setattr(piece, "_connector_params", copy.deepcopy(_jsonable(merged_params)))
        except Exception:
            pass

        return piece

    except Exception as exc:
        trace = traceback.format_exc()

        meta.issues.append(
            ConnectorIssue(
                piece=str(piece_name),
                niveau="erreur",
                message=f"Échec instanciation backend réelle : {exc}",
                source=f"factory:{canonical}",
                exception=trace,
            )
        )

        if not silent:
            print(f"[piece_connector] Échec instanciation '{piece_name}' via '{canonical}':\n{trace}")

        if allow_generic_on_failure or db_data:
            return _build_generic_piece(piece_name, merged_params, db_data, meta=meta)

        return None


def get_piece_connector_diagnostic(
    piece_name: str,
    engine_params: Optional[Mapping[str, Any]],
    db_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retourne un diagnostic sans imposer au reste de l'UI d'inspecter l'objet.
    """
    canonical = canonical_piece_key(piece_name)
    db_params = extract_params_from_backend_payload(db_data)
    user_params = normalize_engine_params(engine_params)
    merged = normalize_engine_params(_merge_non_none(db_params, user_params))

    return {
        "piece_name": piece_name,
        "canonical_key": canonical,
        "factory_available": canonical in _CONNECTORS,
        "available_connectors": available_piece_connectors(),
        "engine_params_count": len(user_params),
        "backend_params_count": len(db_params),
        "merged_params_count": len(merged),
        "db_data_present": isinstance(db_data, dict),
        "has_report": bool(_extract_report(db_data or {})),
        "known_core_values": {
            "architecture_moteur": merged.get("architecture_moteur"),
            "nombre_cylindres": merged.get("nombre_cylindres"),
            "alesage_m": merged.get("alesage_m"),
            "course_m": merged.get("course_m"),
            "rpm_nominal": merged.get("rpm_nominal"),
            "pme_pa": merged.get("pme_pa"),
            "pression_max_pa": merged.get("pression_max_pa"),
            "couple_max_Nm": merged.get("couple_max_Nm"),
        },
    }
