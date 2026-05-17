# backend/components/batterie/batterie.py
from __future__ import annotations

"""
Orchestrateur batterie robuste pour SHSE-M / STHO-ME.

Objectif
--------
La batterie n'est pas seulement dimensionnée comme un stockage en kWh : elle est
traitée comme un pivot énergétique entre :
- la demande du moteur électrique de traction,
- la puissance récupérable depuis le moteur thermique + alternateur,
- la durée de vie cellule,
- les C-rate charge/décharge,
- les pertes Joule,
- le temps de recharge réaliste,
- la masse et l'intégration du pack,
- le BMS/TMS/busbars/boîtier.

Règle fondamentale
------------------
Aucune valeur métier cachée n'est inventée. Si une donnée de conception manque,
elle est inscrite dans `inconnues`. Les valeurs par défaut présentes dans les
classes sont des paramètres de calcul explicites et modifiables.

Placement recommandé
--------------------
backend/components/batterie/batterie.py

Modules utilisés si présents
----------------------------
- calcul_dimensionnement_batterie.py
- calcul_energie_utile.py
- calcul_electrique_pack.py
- calcul_charge_optimale.py
- calcul_temps_charge.py
- dimensionner_pack_cellules.py
- electrolyte_solide.py
- calcul_ratio.py
- pack_batterie.py / bms_batterie.py / tms_batterie.py / busbars_batterie.py / boitier_batterie.py
"""

import importlib
import inspect
import json
import math
import sys
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

# =============================================================================
# Préparation chemins d'import
# =============================================================================

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "batterie.py"
_THIS_DIR = _THIS_FILE.parent

for candidate in (
    _THIS_DIR,
    _THIS_DIR / "modules",
    _THIS_DIR / "pieces",
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    _THIS_DIR.parent.parent.parent,
    Path.cwd(),
    Path("/mnt/data"),  # utile en test ChatGPT/sandbox, ignoré en projet réel si inexistant
):
    try:
        p = str(candidate.resolve())
    except Exception:
        p = str(candidate)
    if p not in sys.path:
        sys.path.insert(0, p)


# =============================================================================
# Imports robustes
# =============================================================================

_IMPORT_ERRORS: Dict[str, str] = {}


def _import_attr(module_names: Sequence[str], attr: str, *, required: bool = True, default: Any = None) -> Any:
    last_error: Optional[Exception] = None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr)
        except Exception as exc:  # pragma: no cover - dépend de l'arborescence runtime
            last_error = exc
    _IMPORT_ERRORS[attr] = " ; ".join(module_names) + (f" :: {last_error}" if last_error else "")
    if required:
        raise ImportError(f"Impossible d'importer {attr} depuis {module_names}: {last_error}") from last_error
    return default


def _mod(*names: str) -> Tuple[str, ...]:
    return tuple(names)


# --- modules énergie / dimensionnement simple ---
calcul_capacite_totale_batterie = _import_attr(
    _mod("backend.components.batterie.modules.calcul_dimensionnement_batterie", "backend.modules.batterie.calcul_dimensionnement_batterie", "calcul_dimensionnement_batterie"),
    "calcul_capacite_totale_batterie",
)
calcul_poids_batterie = _import_attr(
    _mod("backend.components.batterie.modules.calcul_dimensionnement_batterie", "backend.modules.batterie.calcul_dimensionnement_batterie", "calcul_dimensionnement_batterie"),
    "calcul_poids_batterie",
)
calcul_energie_utile_cible = _import_attr(
    _mod("backend.components.batterie.modules.calcul_energie_utile", "backend.modules.batterie.calcul_energie_utile", "calcul_energie_utile"),
    "calcul_energie_utile_cible",
)
calcul_energie_utile_trajet = _import_attr(
    _mod("backend.components.batterie.modules.calcul_energie_utile", "backend.modules.batterie.calcul_energie_utile", "calcul_energie_utile"),
    "calcul_energie_utile_trajet",
)
calcul_energie_utile_pic = _import_attr(
    _mod("backend.components.batterie.modules.calcul_energie_utile", "backend.modules.batterie.calcul_energie_utile", "calcul_energie_utile"),
    "calcul_energie_utile_pic",
)
choisir_energie_utile_finale = _import_attr(
    _mod("backend.components.batterie.modules.calcul_energie_utile", "backend.modules.batterie.calcul_energie_utile", "calcul_energie_utile"),
    "choisir_energie_utile_finale",
)
calcul_temps_charge = _import_attr(
    _mod("backend.components.batterie.modules.calcul_temps_charge", "backend.modules.batterie.calcul_temps_charge", "calcul_temps_charge"),
    "calcul_temps_charge",
)

# --- électrique pack ---
calcul_conso_kwh_km_depuis_puissance_vitesse = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_conso_kwh_km_depuis_puissance_vitesse",
)
calcul_ah_depuis_kwh_tension = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_ah_depuis_kwh_tension",
)
calcul_kwh_depuis_ah_tension = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_kwh_depuis_ah_tension",
)
calcul_courant_depuis_kw_tension = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_courant_depuis_kw_tension",
)
calcul_puissance_kw_depuis_tension_courant = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_puissance_kw_depuis_tension_courant",
)
calcul_c_rate_depuis_kw_kwh = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_c_rate_depuis_kw_kwh",
)
calcul_puissance_effective_stockee = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_puissance_effective_stockee",
)
calcul_puissance_charge_requise = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_puissance_charge_requise",
)
calcul_temps_charge_constant_power = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_temps_charge_constant_power",
)
calcul_puissance_charge_pack_kw = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_puissance_charge_pack_kw",
)
calcul_section_cuivre_estimee_mm2 = _import_attr(
    _mod("backend.components.batterie.modules.calcul_electrique_pack", "backend.modules.batterie.calcul_electrique_pack", "calcul_electrique_pack"),
    "calcul_section_cuivre_estimee_mm2",
)

# --- charge optimale / TMS ---
calcul_courant_charge_optimal_a = _import_attr(
    _mod("backend.components.batterie.modules.calcul_charge_optimale", "backend.modules.batterie.calcul_charge_optimale", "calcul_charge_optimale"),
    "calcul_courant_charge_optimal_a",
)
estimer_puissance_refroidissement_tms_w = _import_attr(
    _mod("backend.components.batterie.modules.calcul_charge_optimale", "backend.modules.batterie.calcul_charge_optimale", "calcul_charge_optimale"),
    "estimer_puissance_refroidissement_tms_w",
)

# --- électrolyte solide ---
ElectrolyteSolide = _import_attr(_mod("backend.components.batterie.modules.electrolyte_solide", "backend.modules.batterie.electrolyte_solide", "electrolyte_solide"), "ElectrolyteSolide", required=False)
CelluleSolide = _import_attr(_mod("backend.components.batterie.modules.electrolyte_solide", "backend.modules.batterie.electrolyte_solide", "electrolyte_solide"), "CelluleSolide", required=False)
PackSolide = _import_attr(_mod("backend.components.batterie.modules.electrolyte_solide", "backend.modules.batterie.electrolyte_solide", "electrolyte_solide"), "PackSolide", required=False)
ElectrolyteOptions = _import_attr(_mod("backend.components.batterie.modules.electrolyte_solide", "backend.modules.batterie.electrolyte_solide", "electrolyte_solide"), "Options", required=False)
evaluer_electrolyte_solide = _import_attr(_mod("backend.components.batterie.modules.electrolyte_solide", "backend.modules.batterie.electrolyte_solide", "electrolyte_solide"), "evaluer_electrolyte_solide", required=False)

# --- dimensionnement cellules / Samsung 25R ---
PointCellule = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "PointCellule", required=False)
CellulePack = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "Cellule", required=False)
PertesPassivesPack = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "PertesPassivesPack", required=False)
ModeleThermiquePack = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "ModeleThermiquePack", required=False)
ContraintesPack = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "ContraintesPack", required=False)
DimensionnementPack = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "DimensionnementPack", required=False)
dimensionner_pack_cellules = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "dimensionner_pack_cellules", required=False)
evaluer_configuration_pack_cellules = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "evaluer_configuration_pack_cellules", required=False)
creer_cellule_samsung_25r = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "creer_cellule_samsung_25r", required=False)
definir_batterie_samsung_25r = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "definir_batterie_samsung_25r", required=False)
dimensionner_pack_samsung_25r_equivalent_twingo = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "dimensionner_pack_samsung_25r_equivalent_twingo", required=False)
formatter_rapport_pack = _import_attr(_mod("backend.components.batterie.modules.dimensionner_pack_cellules", "backend.modules.batterie.dimensionner_pack_cellules", "dimensionner_pack_cellules"), "formatter_rapport_pack", required=False)

# --- catalogue / scraping optionnel ---
CelluleCommerciale = _import_attr(_mod("backend.components.batterie.modules.scraping_cellules_batterie", "backend.modules.batterie.scraping_cellules_batterie", "scraping_cellules_batterie"), "CelluleCommerciale", required=False)
collecter_catalogue_cellules = _import_attr(_mod("backend.components.batterie.modules.scraping_cellules_batterie", "backend.modules.batterie.scraping_cellules_batterie", "scraping_cellules_batterie"), "collecter_catalogue_cellules", required=False)
classer_candidats_pre_dimensionnement = _import_attr(_mod("backend.components.batterie.modules.scraping_cellules_batterie", "backend.modules.batterie.scraping_cellules_batterie", "scraping_cellules_batterie"), "classer_candidats_pre_dimensionnement", required=False)
exigences_pour_cellule_complete = _import_attr(_mod("backend.components.batterie.modules.scraping_cellules_batterie", "backend.modules.batterie.scraping_cellules_batterie", "scraping_cellules_batterie"), "exigences_pour_cellule_complete", required=False)
cellule_vers_dict = _import_attr(_mod("backend.components.batterie.modules.scraping_cellules_batterie", "backend.modules.batterie.scraping_cellules_batterie", "scraping_cellules_batterie"), "cellule_vers_dict", required=False)
cellule_commerciale_samsung_25r_locale = _import_attr(_mod("backend.components.batterie.modules.scraping_cellules_batterie", "backend.modules.batterie.scraping_cellules_batterie", "scraping_cellules_batterie"), "cellule_commerciale_samsung_25r_locale", required=False)

# --- ratio autonomie / conso, optionnel ---
RatioCarburant = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "Carburant", required=False)
Vehicule = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "Vehicule", required=False)
Environnement = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "Environnement", required=False)
BatteriePackRatio = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "BatteriePack", required=False)
Thermique = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "Thermique", required=False)
ConfigElectrolyteSolideRatio = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "ConfigElectrolyteSolide", required=False)
conso_l_100km_pour_capacite = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "conso_l_100km_pour_capacite", required=False)
conso_l_100km_pour_capacite_avec_electrolyte_solide = _import_attr(_mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"), "conso_l_100km_pour_capacite_avec_electrolyte_solide", required=False)

# --- pièces batterie optionnelles ---
def _try_import_piece(attr: str, *modules: str) -> Any:
    return _import_attr(modules, attr, required=False)

PackBatterieImported = _try_import_piece("PackBatterie", "backend.components.batterie.pieces.pack_batterie", "backend.modules.batterie.pack_batterie", "pack_batterie")
BusbarsBatterieImported = _try_import_piece("BusbarsBatterie", "backend.components.batterie.pieces.busbars_batterie", "backend.modules.batterie.busbars_batterie", "busbars_batterie")
BoitierBatterieImported = _try_import_piece("BoitierBatterie", "backend.components.batterie.pieces.boitier_batterie", "backend.modules.batterie.boitier_batterie", "boitier_batterie")
BMSBatterieImported = _try_import_piece("BMSBatterie", "backend.components.batterie.pieces.bms_batterie", "backend.modules.batterie.bms_batterie", "bms_batterie")
TMSBatterieImported = _try_import_piece("TMSBatterie", "backend.components.batterie.pieces.tms_batterie", "backend.modules.batterie.tms_batterie", "tms_batterie")


# =============================================================================
# Helpers généraux
# =============================================================================

Number = Union[int, float]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strict: bool = True) -> float:
    v = _require_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _require_ratio_0_1(name: str, x: Any, *, allow_zero: bool = False) -> float:
    v = _require_finite(name, x)
    if allow_zero:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"{name} doit être dans [0,1] (reçu: {v}).")
    else:
        if not (0.0 < v <= 1.0):
            raise ValueError(f"{name} doit être dans (0,1] (reçu: {v}).")
    return v


def _require_int_pos(name: str, x: Any) -> int:
    if not isinstance(x, int) or isinstance(x, bool) or x <= 0:
        raise ValueError(f"{name} doit être un entier > 0 (reçu: {x!r}).")
    return int(x)


def _safe_float(x: Any) -> Optional[float]:
    try:
        f = float(x)
    except Exception:
        return None
    return f if math.isfinite(f) else None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return x
    f = _safe_float(x)
    if f is not None and abs(f - round(f)) < 1e-9:
        return int(round(f))
    return None


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _deep_get(x: Any, *path: str) -> Any:
    cur = x
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, Mapping):
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


def _sum_finite(vals: Iterable[Any]) -> Optional[float]:
    xs = [float(v) for v in vals if _is_finite(v)]
    return sum(xs) if xs else None


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _push_alerte(rapport: Dict[str, Any], categorie: str, nom: str, detail: str, gravite: str = "avertissement") -> None:
    rapport.setdefault("alertes", {}).setdefault(categorie, []).append({"nom": str(nom), "detail": str(detail), "gravite": str(gravite)})


def _append_note(rapport: Dict[str, Any], note: str) -> None:
    rapport.setdefault("notes_modele", []).append(str(note))


def _dedup_list_of_dict(items: Iterable[Mapping[str, Any]], keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    seen: set[Tuple[str, ...]] = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        sig = tuple(str(it.get(k, "")) for k in keys)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(dict(it))
    return out


def _dedup_rapport(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for cat in ("impossibles", "partielles"):
        inc[cat] = _dedup_list_of_dict(list(inc.get(cat, []) or []), ("nom", "raison"))
    alerts = rapport.setdefault("alertes", {})
    for cat, items in list(alerts.items()):
        alerts[cat] = _dedup_list_of_dict(list(items or []), ("nom", "detail", "gravite"))
    notes = []
    seen_notes = set()
    for n in list(rapport.get("notes_modele", []) or []):
        if n not in seen_notes:
            seen_notes.add(n)
            notes.append(n)
    rapport["notes_modele"] = notes


def _to_jsonable(x: Any, *, depth: int = 0, max_depth: int = 12) -> Any:
    if depth > max_depth:
        return {"type": type(x).__name__, "truncated": True}
    if x is None or isinstance(x, (str, int, bool)):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else str(x)
    if isinstance(x, Path):
        return str(x)
    if isinstance(x, Mapping):
        return {str(k): _to_jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in x]
    if hasattr(x, "en_dict") and callable(getattr(x, "en_dict")):
        try:
            return _to_jsonable(x.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(x, "as_dict") and callable(getattr(x, "as_dict")):
        try:
            return _to_jsonable(x.as_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if is_dataclass(x):
        try:
            return _to_jsonable(asdict(x), depth=depth + 1, max_depth=max_depth)
        except Exception:
            return {"type": type(x).__name__}
    if hasattr(x, "__dict__"):
        try:
            attrs = {k: v for k, v in vars(x).items() if not k.startswith("_") and not callable(v)}
            return {"type": type(x).__name__, "attributs": _to_jsonable(attrs, depth=depth + 1, max_depth=max_depth)}
        except Exception:
            pass
    return {"type": type(x).__name__, "repr": repr(x)}


def _call_with_supported_kwargs(fn: Any, **kwargs: Any) -> Any:
    try:
        sig = inspect.signature(fn)
    except Exception:
        return fn(**{k: v for k, v in kwargs.items() if v is not None})
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return fn(**{k: v for k, v in kwargs.items() if v is not None})
    filt = {k: v for k, v in kwargs.items() if k in sig.parameters and v is not None}
    return fn(**filt)


def _extract_pack_report(rapport_dim: Any) -> Dict[str, Any]:
    data = _to_jsonable(rapport_dim)
    if isinstance(data, dict):
        return data
    return {"valeur": data}


def _try(label: str, rapport: Dict[str, Any], fn: Callable[[], Any], *, target_path: Optional[Tuple[str, ...]] = None) -> Any:
    try:
        out = fn()
        if target_path:
            cur = rapport
            for key in target_path[:-1]:
                cur = cur.setdefault(key, {})
            cur[target_path[-1]] = _to_jsonable(out)
        return out
    except Exception as exc:
        _push_inconnue(rapport, "impossibles", label, str(exc))
        return None


# =============================================================================
# Fallbacks pièces batterie
# =============================================================================

@dataclass
class _PackBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    energie_nominale_kwh: Optional[float] = None
    tension_nominale_v: Optional[float] = None
    capacite_ah: Optional[float] = None
    masse_kg: Optional[float] = None
    volume_m3: Optional[float] = None
    nb_series: Optional[int] = None
    nb_parallele: Optional[int] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        source = self.rapport_batterie or {}
        rep: Dict[str, Any] = {"piece": "pack_batterie", "electrique": {}, "integration": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        dim = _safe_dict(_deep_get(source, "dimensionnement_fin", "rapport"))
        energie = _first_non_none(self.energie_nominale_kwh, _deep_get(source, "dimensionnement", "capacite_totale_kwh"), dim.get("energie_nominale_pack_kwh"))
        tension = _first_non_none(self.tension_nominale_v, _deep_get(source, "entrees", "tension_nominale_v"), dim.get("tension_nominale_pack_v"))
        capacite = _first_non_none(self.capacite_ah, _deep_get(source, "electrique", "capacite_Ah_estimee"), dim.get("capacite_pack_ah"))
        masse = _first_non_none(self.masse_kg, _deep_get(source, "dimensionnement", "masse_batterie_kg"), dim.get("masse_totale_pack_kg"))
        volume = _first_non_none(self.volume_m3, dim.get("volume_total_pack_m3"))
        ns = _first_non_none(self.nb_series, _deep_get(source, "entrees", "nb_series"), dim.get("nb_series"))
        np_ = _first_non_none(self.nb_parallele, _deep_get(source, "entrees", "nb_parallele"), dim.get("nb_parallele"))
        rep["electrique"].update({"energie_nominale_kwh": energie, "tension_nominale_v": tension, "capacite_ah": capacite})
        rep["integration"].update({"masse_kg": masse, "volume_m3": volume, "nb_series": ns, "nb_parallele": np_})
        if not _is_finite(energie):
            _push_inconnue(rep, "partielles", "energie_nominale_kwh", "Calculable si la batterie a pu être dimensionnée.")
        if not _is_finite(tension):
            _push_inconnue(rep, "partielles", "tension_nominale_v", "Requise pour caractériser le pack.")
        if not _is_finite(capacite):
            _push_inconnue(rep, "partielles", "capacite_ah", "Calculable si énergie et tension nominale sont connues.")
        if not _is_finite(masse):
            _push_inconnue(rep, "partielles", "masse_kg", "Calculable si masse cellules ou densité énergétique pack est fournie.")
        _dedup_rapport(rep)
        return rep


@dataclass
class _BusbarsBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    courant_a: Optional[float] = None
    densite_courant_a_mm2: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        source = self.rapport_batterie or {}
        rep: Dict[str, Any] = {"piece": "busbars_batterie", "electrique": {}, "dimensionnement": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        courant = _first_non_none(
            self.courant_a,
            _deep_get(source, "charge", "courant_charge_A"),
            _deep_get(source, "electrique", "courant_decharge_A_estime"),
            _deep_get(source, "dimensionnement_fin", "rapport", "rapports_charge", "courant_charge_pack_a"),
            _deep_get(source, "equilibre_systeme", "courant_charge_optimal_A"),
        )
        j = self.densite_courant_a_mm2
        rep["electrique"]["courant_a"] = courant
        rep["dimensionnement"]["densite_courant_a_mm2"] = j
        if _is_finite(courant) and _is_finite(j) and float(j) > 0.0:
            rep["dimensionnement"]["section_cuivre_estimee_mm2"] = float(calcul_section_cuivre_estimee_mm2(float(courant), float(j)))
        else:
            _push_inconnue(rep, "partielles", "section_cuivre_estimee_mm2", "Calculable si courant_a et densite_courant_a_mm2 sont fournis.")
        _dedup_rapport(rep)
        return rep


@dataclass
class _BoitierBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    masse_pack_kg: Optional[float] = None
    volume_pack_m3: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        source = self.rapport_batterie or {}
        rep: Dict[str, Any] = {"piece": "boitier_batterie", "integration": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        masse = _first_non_none(self.masse_pack_kg, _deep_get(source, "dimensionnement", "masse_batterie_kg"), _deep_get(source, "dimensionnement_fin", "rapport", "masse_totale_pack_kg"))
        volume = _first_non_none(self.volume_pack_m3, _deep_get(source, "dimensionnement_fin", "rapport", "volume_total_pack_m3"))
        rep["integration"].update({"masse_pack_kg": masse, "volume_interne_m3": volume})
        if not _is_finite(masse):
            _push_inconnue(rep, "partielles", "masse_pack_kg", "Masse du pack requise pour qualifier le boîtier.")
        if not _is_finite(volume):
            _push_inconnue(rep, "partielles", "volume_interne_m3", "Volume disponible si le dimensionnement fin de pack est fourni.")
        _dedup_rapport(rep)
        return rep


@dataclass
class _BMSBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    soc: float = 0.5
    temperature_cellules_c: float = 25.0
    soh: float = 1.0
    c_rate_max_charge: float = 1.0
    tension_max_cellule_v: float = 4.2
    temperature_alerte_c: float = 50.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "bms", "monitoring": {"soc": self.soc, "temperature_cellules_c": self.temperature_cellules_c, "soh": self.soh}, "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        source = self.rapport_batterie or {}
        capacite_ah = _first_non_none(
            getattr(self.batterie, "capacite_ah_estimee", None) if self.batterie is not None else None,
            _deep_get(source, "electrique", "capacite_Ah_estimee"),
            _deep_get(source, "dimensionnement_fin", "rapport", "capacite_pack_ah"),
        )
        tension_v = _first_non_none(
            getattr(self.batterie, "tension_nominale_v", None) if self.batterie is not None else None,
            _deep_get(source, "entrees", "tension_nominale_v"),
            _deep_get(source, "dimensionnement_fin", "rapport", "tension_nominale_pack_v"),
        )
        source_kw = _first_finite(_deep_get(source, "equilibre_systeme", "puissance_recharge_effective_kw"), _deep_get(source, "charge", "puissance_effective_stockee_kw"))
        if _is_finite(capacite_ah) and _is_finite(tension_v):
            i_opt = calcul_courant_charge_optimal_a(
                soc=float(self.soc),
                temperature_c=float(self.temperature_cellules_c),
                c_rate_max=float(self.c_rate_max_charge),
                capacite_ah=float(capacite_ah),
                tension_pack_v=float(tension_v),
                puissance_source_max_kw=source_kw,
                t_limit_c=float(self.temperature_alerte_c),
            )
            rep["resultats"]["courant_charge_max_securise_a"] = float(i_opt)
            rep["resultats"]["puissance_charge_max_securisee_kw"] = float(i_opt) * float(tension_v) / 1000.0
            if float(self.temperature_cellules_c) >= float(self.temperature_alerte_c):
                rep["resultats"]["alerte_securite"] = "Surchauffe : charge à réduire ou interrompre."
        else:
            _push_inconnue(rep, "impossibles", "calcul_charge_securisee", "Capacité Ah et tension nominale requises.")
        _dedup_rapport(rep)
        return rep


@dataclass
class _TMSBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    type_refroidissement: str = "Air"
    efficacite_echangeur: float = 0.7
    temperature_liquide_entree_c: float = 20.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "tms", "technologie": {"type": self.type_refroidissement, "efficacite": self.efficacite_echangeur}, "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        source = self.rapport_batterie or {}
        i_charge = _first_non_none(
            _deep_get(source, "charge", "courant_charge_A"),
            _deep_get(source, "dimensionnement_fin", "rapport", "rapports_charge", "courant_charge_pack_a"),
            _deep_get(source, "equilibre_systeme", "courant_charge_optimal_A"),
        )
        r_pack = _first_non_none(
            _deep_get(source, "dimensionnement_fin", "rapport", "resistance_pack_nominale_ohm"),
            _deep_get(source, "dimensionnement_fin", "rapport", "resistance_pack_min_ohm"),
            _deep_get(source, "electrique", "resistance_interne_pack_ohm"),
        )
        if _is_finite(i_charge) and _is_finite(r_pack):
            rep["resultats"]["besoin_refroidissement_charge_w"] = float(
                estimer_puissance_refroidissement_tms_w(
                    courant_a=float(i_charge),
                    resistance_interne_pack_ohm=float(r_pack),
                    efficacite_tms=float(self.efficacite_echangeur),
                )
            )
        else:
            _push_inconnue(rep, "partielles", "besoin_refroidissement", "Courant de charge et résistance interne pack requis.")
        _dedup_rapport(rep)
        return rep


PackBatterie = PackBatterieImported or _PackBatterieFallback
BusbarsBatterie = BusbarsBatterieImported or _BusbarsBatterieFallback
BoitierBatterie = BoitierBatterieImported or _BoitierBatterieFallback
BMSBatterie = BMSBatterieImported or _BMSBatterieFallback
TMSBatterie = TMSBatterieImported or _TMSBatterieFallback


# =============================================================================
# Modèles de données spécifiques à l'équilibre système
# =============================================================================

@dataclass(frozen=True)
class ContraintesEquilibreBatterie:
    """
    Contraintes système pour éviter une batterie trop petite ou trop grande.

    Toutes les puissances sont en kW, les énergies en kWh.
    """

    # Demande électrique / traction
    puissance_sortie_continue_kw: Optional[float] = None
    puissance_sortie_moyenne_kw: Optional[float] = None
    puissance_sortie_pic_kw: Optional[float] = None
    rendement_batterie_vers_moteur: float = 1.0

    # Source de recharge : moteur thermique + alternateur + conversion vers pack
    puissance_recharge_source_kw: Optional[float] = None
    rendement_recharge_source: float = 0.90
    duty_moteur_thermique_max: Optional[float] = 0.50
    marge_usage_wltp: float = 0.20

    # Fenêtre temporelle de contrôle
    periode_equilibre_h: Optional[float] = None
    autonomie_elec_min_h: Optional[float] = None
    temps_recharge_max_h: Optional[float] = None
    energie_tampon_min_kwh: Optional[float] = None

    # Contraintes pack / durée de vie
    c_rate_decharge_continue_max: Optional[float] = None
    c_rate_decharge_pic_max: Optional[float] = None
    c_rate_charge_max: Optional[float] = None
    masse_pack_max_kg: Optional[float] = None
    capacite_nominale_min_kwh: Optional[float] = None
    capacite_nominale_max_kwh: Optional[float] = None
    capacite_nominale_preferee_kwh: Optional[float] = None

    # État charge/thermique pour calcul charge optimale
    soc_reference_charge: float = 0.50
    temperature_cellules_c: float = 25.0

    def __post_init__(self) -> None:
        for name in (
            "puissance_sortie_continue_kw", "puissance_sortie_moyenne_kw", "puissance_sortie_pic_kw",
            "puissance_recharge_source_kw", "periode_equilibre_h", "autonomie_elec_min_h",
            "temps_recharge_max_h", "energie_tampon_min_kwh", "c_rate_decharge_continue_max",
            "c_rate_decharge_pic_max", "c_rate_charge_max", "masse_pack_max_kg",
            "capacite_nominale_min_kwh", "capacite_nominale_max_kwh", "capacite_nominale_preferee_kwh",
        ):
            v = getattr(self, name)
            if v is not None:
                _require_positive(name, v, strict=False if name.startswith("puissance") or name.startswith("energie") else True)
        _require_ratio_0_1("rendement_batterie_vers_moteur", self.rendement_batterie_vers_moteur, allow_zero=False)
        _require_ratio_0_1("rendement_recharge_source", self.rendement_recharge_source, allow_zero=False)
        _require_ratio_0_1("marge_usage_wltp", self.marge_usage_wltp, allow_zero=True)
        _require_ratio_0_1("soc_reference_charge", self.soc_reference_charge, allow_zero=True)
        _require_finite("temperature_cellules_c", self.temperature_cellules_c)
        if self.duty_moteur_thermique_max is not None:
            _require_ratio_0_1("duty_moteur_thermique_max", self.duty_moteur_thermique_max, allow_zero=False)
        if self.capacite_nominale_min_kwh is not None and self.capacite_nominale_max_kwh is not None:
            if self.capacite_nominale_max_kwh < self.capacite_nominale_min_kwh:
                raise ValueError("capacite_nominale_max_kwh doit être >= capacite_nominale_min_kwh.")


@dataclass(frozen=True)
class ScoreEquilibre:
    capacite_nominale_kwh: float
    energie_utile_kwh: float
    masse_pack_kg: Optional[float]
    c_rate_decharge_continue: Optional[float]
    c_rate_decharge_pic: Optional[float]
    c_rate_charge_source: Optional[float]
    temps_recharge_fenetre_h: Optional[float]
    duty_moteur_usage: Optional[float]
    score: float
    raisons: Tuple[str, ...] = tuple()

    def en_dict(self) -> Dict[str, Any]:
        return _to_jsonable(asdict(self))


# =============================================================================
# Composant Batterie
# =============================================================================

@dataclass(frozen=True)
class Batterie:
    """
    Orchestrateur batterie.

    En plus du dimensionnement énergétique classique, cette version ajoute une
    analyse `equilibre_systeme` : elle vérifie que la batterie n'est ni trop
    petite (C-rate, tampon, duty moteur thermique trop élevé) ni trop grande
    (masse, recharge impossible dans la fenêtre imposée, courant de charge trop
    faible/fort, source insuffisante).
    """

    fenetre_soc: float = 0.8
    densite_energetique_kwh_kg: Optional[float] = None
    rendement_charge: float = 0.90
    puissance_charge_kw: Optional[float] = None
    tension_nominale_v: Optional[float] = None
    tension_charge_v: Optional[float] = None

    # Paramètres de préservation par défaut explicites ; modifiables à l'appel.
    c_rate_charge_preservation: float = 0.8
    c_rate_decharge_continue_preservation: Optional[float] = None
    c_rate_decharge_pic_preservation: Optional[float] = None

    piece_pack: Optional[Any] = None
    piece_busbars: Optional[Any] = None
    piece_boitier: Optional[Any] = None
    piece_bms: Optional[Any] = None
    piece_tms: Optional[Any] = None

    def __post_init__(self) -> None:
        _require_ratio_0_1("fenetre_soc", self.fenetre_soc, allow_zero=False)
        _require_ratio_0_1("rendement_charge", self.rendement_charge, allow_zero=False)
        _require_positive("c_rate_charge_preservation", self.c_rate_charge_preservation, strict=True)
        if self.densite_energetique_kwh_kg is not None:
            _require_positive("densite_energetique_kwh_kg", self.densite_energetique_kwh_kg, strict=True)
        if self.puissance_charge_kw is not None:
            _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False)
        if self.tension_nominale_v is not None:
            _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)
        if self.tension_charge_v is not None:
            _require_positive("tension_charge_v", self.tension_charge_v, strict=True)
        if self.c_rate_decharge_continue_preservation is not None:
            _require_positive("c_rate_decharge_continue_preservation", self.c_rate_decharge_continue_preservation, strict=True)
        if self.c_rate_decharge_pic_preservation is not None:
            _require_positive("c_rate_decharge_pic_preservation", self.c_rate_decharge_pic_preservation, strict=True)

    @property
    def capacite_ah_estimee(self) -> Optional[float]:
        return None

    def analyser(self, *, strict: bool = False, **kwargs: Any) -> Dict[str, Any]:
        return self.analyser_dimensionnement(strict=strict, **kwargs)

    # ------------------------------------------------------------------
    # API principale
    # ------------------------------------------------------------------
    def analyser_dimensionnement(
        self,
        *,
        strict: bool = False,
        distance_km: Optional[float] = None,
        conso_kwh_km: Optional[float] = None,
        puissance_moyenne_kw: Optional[float] = None,
        vitesse_moyenne_kmh: Optional[float] = None,
        temps_charge_cible_h: Optional[float] = None,
        puissance_pic_kw: Optional[float] = None,
        duree_pic_s: Optional[float] = None,
        energie_utile_imposee_kwh: Optional[float] = None,
        mode_aggregation_energie: str = "max",
        calculer_puissance_charge_requise_flag: bool = True,
        calculer_puissance_charge_requise: Optional[bool] = None,
        # Nouveau cœur robuste : équilibre SHSE-M
        contraintes_equilibre: Optional[ContraintesEquilibreBatterie] = None,
        activer_equilibre_systeme: bool = True,
        puissance_sortie_continue_kw: Optional[float] = None,
        puissance_sortie_moyenne_kw: Optional[float] = None,
        puissance_sortie_pic_kw: Optional[float] = None,
        puissance_recharge_source_kw: Optional[float] = None,
        rendement_recharge_source: Optional[float] = None,
        rendement_batterie_vers_moteur: Optional[float] = None,
        duty_moteur_thermique_max: Optional[float] = None,
        marge_usage_wltp: Optional[float] = None,
        periode_equilibre_h: Optional[float] = None,
        autonomie_elec_min_h: Optional[float] = None,
        temps_recharge_max_h: Optional[float] = None,
        energie_tampon_min_kwh: Optional[float] = None,
        capacite_nominale_min_kwh: Optional[float] = None,
        capacite_nominale_max_kwh: Optional[float] = None,
        capacite_nominale_preferee_kwh: Optional[float] = None,
        masse_pack_max_kg: Optional[float] = None,
        c_rate_charge_max: Optional[float] = None,
        c_rate_decharge_continue_max: Optional[float] = None,
        c_rate_decharge_pic_max: Optional[float] = None,
        soc_reference_charge: float = 0.50,
        temperature_cellules_c: float = 25.0,
        # électrolyte solide
        activer_electrolyte_solide: bool = False,
        nb_series: Optional[int] = None,
        nb_parallele: Optional[int] = None,
        tension_cellule_v: Optional[float] = None,
        capacite_cellule_ah: Optional[float] = None,
        courant_cellule_max_a: Optional[float] = None,
        conductivite_ionique_s_m: Optional[float] = None,
        epaisseur_electrolyte_m: Optional[float] = None,
        surface_active_m2: Optional[float] = None,
        resistance_interface_ohm: Optional[float] = None,
        puissance_pack_continue_kw: Optional[float] = None,
        puissance_pack_pic_kw: Optional[float] = None,
        rendement_chaine: Optional[float] = None,
        electrolyte_strict: bool = False,
        # catalogue
        activer_catalogue_cellules: bool = False,
        catalogue_cellules: Optional[Sequence[Any]] = None,
        utiliser_samsung_25r_locale_catalogue: bool = False,
        catalogue_top_n: int = 5,
        catalogue_sleep_s: float = 0.0,
        # dimensionnement fin générique
        activer_dimensionnement_fin: bool = False,
        cellule_pack: Optional[Any] = None,
        energie_nominale_cible_pack_kwh: Optional[float] = None,
        tension_bus_min_v: Optional[float] = None,
        tension_bus_max_v: Optional[float] = None,
        tension_nominale_cible_pack_v: Optional[float] = None,
        pertes_passives_pack: Optional[Any] = None,
        modele_thermique_pack: Optional[Any] = None,
        nb_series_min_dim: Optional[int] = None,
        nb_series_max_dim: Optional[int] = None,
        courant_charge_cellule_a_dim: Optional[float] = None,
        rendement_charge_dim: Optional[float] = None,
        # Samsung 25R direct
        activer_samsung_25r: bool = False,
        samsung_nb_cellules_total: Optional[int] = None,
        samsung_nb_series: Optional[int] = None,
        samsung_nb_parallele: Optional[int] = None,
        samsung_tension_nominale_cible_v: Optional[float] = None,
        samsung_energie_nominale_cible_kwh: Optional[float] = None,
        samsung_courant_decharge_cellule_conception_a: float = 10.0,
        samsung_courant_charge_cellule_a: float = 2.0,
        samsung_reserve_soc: float = 0.10,
        samsung_utiliser_resistance_max: bool = False,
        samsung_masse_hors_cellules_kg: Optional[float] = None,
        samsung_volume_hors_cellules_m3: float = 0.0,
        samsung_resistance_hors_cellules_ohm: float = 0.0,
        activer_samsung_25r_twingo: bool = False,
        # ratio carburant/batterie, optionnel
        activer_ratio_conso: bool = False,
        ratio_params: Optional[Dict[str, Any]] = None,
        # pièces
        analyser_pieces: bool = True,
        busbars_densite_courant_a_mm2: Optional[float] = None,
        busbars_courant_a: Optional[float] = None,
        bms_soc: Optional[float] = None,
        bms_temperature_cellules_c: Optional[float] = None,
        bms_soh: float = 1.0,
        tms_efficacite_echangeur: Optional[float] = None,
    ) -> Dict[str, Any]:
        if calculer_puissance_charge_requise is not None:
            calculer_puissance_charge_requise_flag = bool(calculer_puissance_charge_requise)

        rapport: Dict[str, Any] = self._nouveau_rapport()

        w = _require_ratio_0_1("fenetre_soc", self.fenetre_soc, allow_zero=False)
        eta_charge = _require_ratio_0_1("rendement_charge", self.rendement_charge, allow_zero=False)
        if mode_aggregation_energie not in ("max", "somme"):
            raise ValueError("mode_aggregation_energie doit être 'max' ou 'somme'.")
        if catalogue_top_n <= 0:
            raise ValueError("catalogue_top_n doit être > 0.")

        # Centralise la contrainte équilibre pour que les appels anciens restent compatibles.
        eq = self._build_contraintes_equilibre(
            contraintes_equilibre=contraintes_equilibre,
            puissance_sortie_continue_kw=puissance_sortie_continue_kw,
            puissance_sortie_moyenne_kw=_first_non_none(puissance_sortie_moyenne_kw, puissance_moyenne_kw),
            puissance_sortie_pic_kw=_first_non_none(puissance_sortie_pic_kw, puissance_pic_kw),
            puissance_recharge_source_kw=_first_non_none(puissance_recharge_source_kw, self.puissance_charge_kw),
            rendement_recharge_source=_first_non_none(rendement_recharge_source, self.rendement_charge),
            rendement_batterie_vers_moteur=_first_non_none(rendement_batterie_vers_moteur, 1.0),
            duty_moteur_thermique_max=duty_moteur_thermique_max,
            marge_usage_wltp=marge_usage_wltp,
            periode_equilibre_h=periode_equilibre_h,
            autonomie_elec_min_h=autonomie_elec_min_h,
            temps_recharge_max_h=temps_recharge_max_h,
            energie_tampon_min_kwh=energie_tampon_min_kwh,
            capacite_nominale_min_kwh=capacite_nominale_min_kwh,
            capacite_nominale_max_kwh=capacite_nominale_max_kwh,
            capacite_nominale_preferee_kwh=capacite_nominale_preferee_kwh,
            masse_pack_max_kg=masse_pack_max_kg,
            c_rate_charge_max=_first_non_none(c_rate_charge_max, self.c_rate_charge_preservation),
            c_rate_decharge_continue_max=_first_non_none(c_rate_decharge_continue_max, self.c_rate_decharge_continue_preservation),
            c_rate_decharge_pic_max=_first_non_none(c_rate_decharge_pic_max, self.c_rate_decharge_pic_preservation),
            soc_reference_charge=soc_reference_charge,
            temperature_cellules_c=temperature_cellules_c,
        )

        rapport["entrees"] = {
            "fenetre_soc": w,
            "densite_energetique_kwh_kg": self.densite_energetique_kwh_kg,
            "rendement_charge": eta_charge,
            "puissance_charge_kw": self.puissance_charge_kw,
            "tension_nominale_v": self.tension_nominale_v,
            "tension_charge_v": self.tension_charge_v,
            "distance_km": distance_km,
            "conso_kwh_km": conso_kwh_km,
            "puissance_moyenne_kw": puissance_moyenne_kw,
            "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
            "temps_charge_cible_h": temps_charge_cible_h,
            "puissance_pic_kw": puissance_pic_kw,
            "duree_pic_s": duree_pic_s,
            "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
            "mode_aggregation_energie": mode_aggregation_energie,
            "activer_equilibre_systeme": activer_equilibre_systeme,
            "contraintes_equilibre": _to_jsonable(eq),
            "activer_electrolyte_solide": activer_electrolyte_solide,
            "nb_series": nb_series,
            "nb_parallele": nb_parallele,
            "activer_catalogue_cellules": activer_catalogue_cellules,
            "activer_dimensionnement_fin": activer_dimensionnement_fin,
            "activer_samsung_25r": activer_samsung_25r,
            "activer_samsung_25r_twingo": activer_samsung_25r_twingo,
            "activer_ratio_conso": activer_ratio_conso,
        }

        # ------------------------------------------------------------------
        # 1) Énergies utiles
        # ------------------------------------------------------------------
        E_u_final = self._analyser_energies_utiles(
            rapport,
            distance_km=distance_km,
            conso_kwh_km=conso_kwh_km,
            puissance_moyenne_kw=puissance_moyenne_kw,
            vitesse_moyenne_kmh=vitesse_moyenne_kmh,
            temps_charge_cible_h=temps_charge_cible_h,
            puissance_pic_kw=puissance_pic_kw,
            duree_pic_s=duree_pic_s,
            energie_utile_imposee_kwh=energie_utile_imposee_kwh,
            mode_aggregation_energie=mode_aggregation_energie,
            eta_charge=eta_charge,
            eq=eq,
        )

        # ------------------------------------------------------------------
        # 2) Dimensionnement simple : capacité / masse
        # ------------------------------------------------------------------
        E_batt_tot = None
        m_batt = None
        if E_u_final is not None:
            E_batt_tot = float(calcul_capacite_totale_batterie(E_u_final, w))
            if self.densite_energetique_kwh_kg is not None:
                m_batt = float(calcul_poids_batterie(E_batt_tot, _require_positive("densite_energetique_kwh_kg", self.densite_energetique_kwh_kg, strict=True)))
            else:
                _push_inconnue(rapport, "partielles", "masse_batterie_kg", "Calculable si densite_energetique_kwh_kg est fournie.")
        else:
            _push_inconnue(rapport, "partielles", "capacite_totale_kwh", "Calculable si E_utile_finale_kwh est déterminée.")

        rapport["dimensionnement"].update({
            "E_utile_finale_kwh": E_u_final,
            "capacite_totale_kwh": E_batt_tot,
            "masse_batterie_kg": m_batt,
            "fenetre_soc": w,
        })

        # ------------------------------------------------------------------
        # 3) Charge / courant / C-rate
        # ------------------------------------------------------------------
        self._analyser_charge_et_electrique(
            rapport,
            E_u_final=E_u_final,
            E_batt_tot=E_batt_tot,
            eta_charge=eta_charge,
            temps_charge_cible_h=temps_charge_cible_h,
            calculer_puissance_charge_requise_flag=calculer_puissance_charge_requise_flag,
            puissance_moyenne_kw=puissance_moyenne_kw,
        )

        # ------------------------------------------------------------------
        # 4) Équilibre système SHSE-M : cœur nouveau
        # ------------------------------------------------------------------
        if activer_equilibre_systeme:
            self._analyser_equilibre_systeme(rapport, eq=eq, E_batt_simple_kwh=E_batt_tot, E_u_simple_kwh=E_u_final)
        else:
            rapport["equilibre_systeme"]["actif"] = False

        # Si l'équilibre propose une capacité plus contraignante, on aligne la cible fine.
        cap_equilibre = _safe_float(_deep_get(rapport, "equilibre_systeme", "capacite_nominale_recommandee_kwh"))
        if cap_equilibre is not None:
            if E_batt_tot is None or cap_equilibre > E_batt_tot:
                rapport["dimensionnement"]["capacite_totale_kwh_avant_equilibre"] = E_batt_tot
                rapport["dimensionnement"]["capacite_totale_kwh"] = cap_equilibre
                E_batt_tot = cap_equilibre
                rapport["dimensionnement"]["E_utile_finale_kwh"] = cap_equilibre * w
                if self.densite_energetique_kwh_kg is not None:
                    rapport["dimensionnement"]["masse_batterie_kg"] = float(calcul_poids_batterie(cap_equilibre, self.densite_energetique_kwh_kg))

        # ------------------------------------------------------------------
        # 5) Électrolyte solide
        # ------------------------------------------------------------------
        if activer_electrolyte_solide:
            self._analyser_electrolyte_solide(
                rapport,
                nb_series=nb_series,
                nb_parallele=nb_parallele,
                tension_cellule_v=tension_cellule_v,
                capacite_cellule_ah=capacite_cellule_ah,
                courant_cellule_max_a=courant_cellule_max_a,
                conductivite_ionique_s_m=conductivite_ionique_s_m,
                epaisseur_electrolyte_m=epaisseur_electrolyte_m,
                surface_active_m2=surface_active_m2,
                resistance_interface_ohm=resistance_interface_ohm,
                puissance_pack_continue_kw=_first_non_none(puissance_pack_continue_kw, puissance_sortie_continue_kw, puissance_moyenne_kw),
                puissance_pack_pic_kw=_first_non_none(puissance_pack_pic_kw, puissance_sortie_pic_kw, puissance_pic_kw),
                rendement_chaine=rendement_chaine,
                electrolyte_strict=electrolyte_strict,
            )

        # ------------------------------------------------------------------
        # 6) Dimensionnement fin / Samsung / catalogue
        # ------------------------------------------------------------------
        effective_energy_target = _first_finite(energie_nominale_cible_pack_kwh, samsung_energie_nominale_cible_kwh, E_batt_tot)
        effective_power_cont = _first_finite(_deep_get(rapport, "equilibre_systeme", "puissance_sortie_continue_kw"), puissance_sortie_continue_kw, puissance_moyenne_kw, 0.0)
        effective_power_pic = _first_finite(_deep_get(rapport, "equilibre_systeme", "puissance_sortie_pic_kw"), puissance_sortie_pic_kw, puissance_pic_kw, effective_power_cont, 0.0)

        if activer_samsung_25r or activer_samsung_25r_twingo:
            self._analyser_samsung_25r(
                rapport,
                activer_samsung_25r_twingo=activer_samsung_25r_twingo,
                nb_cellules_total=samsung_nb_cellules_total,
                nb_series=samsung_nb_series,
                nb_parallele=samsung_nb_parallele,
                tension_nominale_cible_v=_first_non_none(samsung_tension_nominale_cible_v, tension_nominale_cible_pack_v, self.tension_nominale_v),
                energie_nominale_cible_kwh=effective_energy_target,
                puissance_continue_kw=effective_power_cont or 0.0,
                puissance_pic_kw=effective_power_pic or 0.0,
                courant_decharge_cellule_conception_a=samsung_courant_decharge_cellule_conception_a,
                courant_charge_cellule_a=samsung_courant_charge_cellule_a,
                rendement_charge=eta_charge if rendement_charge_dim is None else rendement_charge_dim,
                reserve_soc=samsung_reserve_soc,
                masse_hors_cellules_kg=samsung_masse_hors_cellules_kg,
                volume_hors_cellules_m3=samsung_volume_hors_cellules_m3,
                resistance_hors_cellules_ohm=samsung_resistance_hors_cellules_ohm,
                utiliser_resistance_max=samsung_utiliser_resistance_max,
            )

        if activer_dimensionnement_fin:
            self._analyser_dimensionnement_fin(
                rapport,
                cellule_pack=cellule_pack,
                energie_nominale_cible_pack_kwh=effective_energy_target,
                tension_bus_min_v=tension_bus_min_v,
                tension_bus_max_v=tension_bus_max_v,
                tension_nominale_cible_pack_v=_first_non_none(tension_nominale_cible_pack_v, self.tension_nominale_v),
                puissance_continue_kw=effective_power_cont or 0.0,
                puissance_pic_kw=effective_power_pic or 0.0,
                pertes_passives_pack=pertes_passives_pack,
                modele_thermique_pack=modele_thermique_pack,
                nb_series_min_dim=nb_series_min_dim,
                nb_series_max_dim=nb_series_max_dim,
                courant_charge_cellule_a_dim=courant_charge_cellule_a_dim,
                rendement_charge_dim=eta_charge if rendement_charge_dim is None else rendement_charge_dim,
            )

        if activer_catalogue_cellules:
            self._analyser_catalogue(
                rapport,
                catalogue_cellules=catalogue_cellules,
                utiliser_samsung_25r_locale_catalogue=utiliser_samsung_25r_locale_catalogue,
                catalogue_top_n=catalogue_top_n,
                catalogue_sleep_s=catalogue_sleep_s,
                energie_cible_kwh=effective_energy_target,
                tension_nominale_cible_v=_first_non_none(tension_nominale_cible_pack_v, self.tension_nominale_v),
                puissance_continue_kw=effective_power_cont,
                puissance_pic_kw=effective_power_pic,
            )

        if activer_ratio_conso:
            self._analyser_ratio_conso(rapport, ratio_params=ratio_params, capacite_nominale_kwh=E_batt_tot)

        # ------------------------------------------------------------------
        # 7) Pièces pack/BMS/TMS/busbars/boîtier
        # ------------------------------------------------------------------
        if analyser_pieces:
            self._analyser_pieces(
                rapport,
                busbars_densite_courant_a_mm2=busbars_densite_courant_a_mm2,
                busbars_courant_a=busbars_courant_a,
                bms_soc=bms_soc if bms_soc is not None else eq.soc_reference_charge,
                bms_temperature_cellules_c=bms_temperature_cellules_c if bms_temperature_cellules_c is not None else eq.temperature_cellules_c,
                bms_soh=bms_soh,
                tms_efficacite_echangeur=tms_efficacite_echangeur,
            )

        self._synthese_finale(rapport)
        _dedup_rapport(rapport)
        if strict and rapport.get("inconnues", {}).get("impossibles"):
            raise ValueError(json.dumps(rapport["inconnues"]["impossibles"], ensure_ascii=False, indent=2))
        return _to_jsonable(rapport)

    def export_json(self, chemin: Union[str, Path], *, indent: int = 2, **kwargs: Any) -> Path:
        path = Path(chemin)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.analyser_dimensionnement(**kwargs)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Construction du rapport
    # ------------------------------------------------------------------
    def _nouveau_rapport(self) -> Dict[str, Any]:
        return {
            "composant": "batterie",
            "meta": {
                "orchestrateur": "Batterie",
                "mode": "dimensionnement_equilibre_systeme_sans_invention",
                "modules_disponibles": self._module_status(),
            },
            "entrees": {},
            "energies_utiles": {},
            "dimensionnement": {},
            "charge": {},
            "electrique": {},
            "equilibre_systeme": {},
            "electrolyte_solide": {},
            "catalogue_cellules": {},
            "dimensionnement_fin": {},
            "samsung_25r": {},
            "ratio_conso": {},
            "pieces": {},
            "synthese": {},
            "hypotheses": [],
            "notes_modele": [],
            "alertes": {"coherence": [], "dimensionnement": [], "securite": [], "thermique": []},
            "unites": {
                "energie": "kWh",
                "puissance": "kW",
                "courant": "A",
                "tension": "V",
                "masse": "kg",
                "temps": "h",
                "resistance": "ohm",
                "pertes": "W",
            },
            "imports_manquants": dict(_IMPORT_ERRORS),
            "inconnues": {"impossibles": [], "partielles": []},
        }

    def _module_status(self) -> Dict[str, bool]:
        return {
            "calcul_dimensionnement_batterie": callable(calcul_capacite_totale_batterie) and callable(calcul_poids_batterie),
            "calcul_energie_utile": callable(calcul_energie_utile_trajet) and callable(calcul_energie_utile_pic),
            "calcul_electrique_pack": callable(calcul_courant_depuis_kw_tension) and callable(calcul_c_rate_depuis_kw_kwh),
            "calcul_charge_optimale": callable(calcul_courant_charge_optimal_a),
            "calcul_temps_charge": callable(calcul_temps_charge),
            "dimensionner_pack_cellules": callable(dimensionner_pack_cellules) or callable(definir_batterie_samsung_25r),
            "electrolyte_solide": callable(evaluer_electrolyte_solide),
            "calcul_ratio": callable(conso_l_100km_pour_capacite),
            "pieces_batterie": any(cls is not None for cls in (PackBatterie, BusbarsBatterie, BoitierBatterie, BMSBatterie, TMSBatterie)),
        }

    # ------------------------------------------------------------------
    # Sous-calculs
    # ------------------------------------------------------------------
    def _build_contraintes_equilibre(self, *, contraintes_equilibre: Optional[ContraintesEquilibreBatterie], **kwargs: Any) -> ContraintesEquilibreBatterie:
        allowed = {f.name for f in fields(ContraintesEquilibreBatterie)}
        if contraintes_equilibre is not None:
            updates = {k: v for k, v in kwargs.items() if v is not None and k in allowed}
            return replace(contraintes_equilibre, **updates) if updates else contraintes_equilibre
        return ContraintesEquilibreBatterie(**{k: v for k, v in kwargs.items() if v is not None and k in allowed})

    def _analyser_energies_utiles(self, rapport: Dict[str, Any], *, distance_km: Optional[float], conso_kwh_km: Optional[float], puissance_moyenne_kw: Optional[float], vitesse_moyenne_kmh: Optional[float], temps_charge_cible_h: Optional[float], puissance_pic_kw: Optional[float], duree_pic_s: Optional[float], energie_utile_imposee_kwh: Optional[float], mode_aggregation_energie: str, eta_charge: float, eq: ContraintesEquilibreBatterie) -> Optional[float]:
        E_trajet: Optional[float] = None
        conso_derivee: Optional[float] = None
        if distance_km is not None:
            d = _require_positive("distance_km", distance_km, strict=False)
            if conso_kwh_km is not None:
                c = _require_positive("conso_kwh_km", conso_kwh_km, strict=False)
                E_trajet = float(calcul_energie_utile_trajet(d, c))
            elif puissance_moyenne_kw is not None and vitesse_moyenne_kmh is not None:
                Pm = _require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
                vm = _require_positive("vitesse_moyenne_kmh", vitesse_moyenne_kmh, strict=True)
                conso_derivee = float(calcul_conso_kwh_km_depuis_puissance_vitesse(Pm, vm))
                E_trajet = float(calcul_energie_utile_trajet(d, conso_derivee))
                rapport["hypotheses"].append("conso_kwh_km dérivée par P_moyenne/vitesse_moyenne.")
            else:
                _push_inconnue(rapport, "partielles", "E_trajet_kwh", "Calculable si conso_kwh_km ou (puissance_moyenne_kw + vitesse_moyenne_kmh) est fourni.")

        E_charge_cible: Optional[float] = None
        if temps_charge_cible_h is not None:
            t = _require_positive("temps_charge_cible_h", temps_charge_cible_h, strict=False)
            if self.puissance_charge_kw is not None:
                Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False)
                E_charge_cible = float(calcul_energie_utile_cible(t, Pchg, eta_charge))
            else:
                _push_inconnue(rapport, "partielles", "E_charge_cible_kwh", "Calculable si puissance_charge_kw est fournie.")

        E_pic: Optional[float] = None
        if puissance_pic_kw is not None and duree_pic_s is not None:
            E_pic = float(calcul_energie_utile_pic(_require_positive("puissance_pic_kw", puissance_pic_kw, strict=False), _require_positive("duree_pic_s", duree_pic_s, strict=False)))
        elif puissance_pic_kw is not None or duree_pic_s is not None:
            _push_inconnue(rapport, "partielles", "E_pic_kwh", "Calculable si puissance_pic_kw ET duree_pic_s sont fournis.")

        E_autonomie: Optional[float] = None
        if eq.autonomie_elec_min_h is not None:
            P_ref = _first_finite(eq.puissance_sortie_moyenne_kw, puissance_moyenne_kw, eq.puissance_sortie_continue_kw)
            if P_ref is not None:
                E_autonomie = P_ref * eq.autonomie_elec_min_h / eq.rendement_batterie_vers_moteur
            else:
                _push_inconnue(rapport, "partielles", "E_autonomie_elec_min_kwh", "Calculable si autonomie_elec_min_h et puissance moyenne/continue sont fournies.")

        E_periode: Optional[float] = None
        if eq.periode_equilibre_h is not None and eq.duty_moteur_thermique_max is not None:
            P_avg = _first_finite(eq.puissance_sortie_moyenne_kw, puissance_moyenne_kw)
            if P_avg is not None:
                P_avg_corr = P_avg * (1.0 + eq.marge_usage_wltp) / eq.rendement_batterie_vers_moteur
                E_periode = P_avg_corr * (1.0 - eq.duty_moteur_thermique_max) * eq.periode_equilibre_h
            else:
                _push_inconnue(rapport, "partielles", "E_tampon_periode_kwh", "Calculable si periode_equilibre_h, duty_moteur_thermique_max et puissance_sortie_moyenne_kw sont fournis.")

        E_tampon_min = None
        if eq.energie_tampon_min_kwh is not None:
            E_tampon_min = _require_positive("energie_tampon_min_kwh", eq.energie_tampon_min_kwh, strict=False)

        E_imposee: Optional[float] = None
        if energie_utile_imposee_kwh is not None:
            E_imposee = _require_positive("energie_utile_imposee_kwh", energie_utile_imposee_kwh, strict=False)

        candidates = [v for v in (E_trajet, E_charge_cible, E_pic, E_autonomie, E_periode, E_tampon_min, E_imposee) if v is not None]
        E_u_final: Optional[float] = None
        if candidates:
            E_u_final = float(choisir_energie_utile_finale(*candidates)) if mode_aggregation_energie == "max" else float(sum(candidates))
            if mode_aggregation_energie == "somme":
                rapport["hypotheses"].append("E_utile_finale obtenue par somme des contraintes disponibles.")
        else:
            _push_inconnue(rapport, "impossibles", "E_utile_finale_kwh", "Impossible sans au moins un critère : trajet, charge cible, pic, autonomie, tampon ou énergie imposée.")

        rapport["energies_utiles"] = {
            "conso_kwh_km_derivee": conso_derivee,
            "E_trajet_kwh": E_trajet,
            "E_charge_cible_kwh": E_charge_cible,
            "E_pic_kwh": E_pic,
            "E_autonomie_elec_min_kwh": E_autonomie,
            "E_tampon_periode_kwh": E_periode,
            "E_tampon_min_imposee_kwh": E_tampon_min,
            "E_imposee_kwh": E_imposee,
            "E_utile_finale_kwh": E_u_final,
        }
        return E_u_final

    def _analyser_charge_et_electrique(self, rapport: Dict[str, Any], *, E_u_final: Optional[float], E_batt_tot: Optional[float], eta_charge: float, temps_charge_cible_h: Optional[float], calculer_puissance_charge_requise_flag: bool, puissance_moyenne_kw: Optional[float]) -> None:
        t_charge: Optional[float] = None
        P_eff_kw: Optional[float] = None
        P_charge_req_kw: Optional[float] = None
        I_charge_a: Optional[float] = None

        if E_u_final is not None:
            if self.puissance_charge_kw is not None:
                Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=True)
                t_charge = float(calcul_temps_charge(E_u_final, Pchg, eta_charge))
                P_eff_kw = float(calcul_puissance_effective_stockee(Pchg, eta_charge))
            else:
                _push_inconnue(rapport, "partielles", "temps_charge_h", "Calculable si puissance_charge_kw est fournie.")
            if temps_charge_cible_h is not None and calculer_puissance_charge_requise_flag:
                P_charge_req_kw = float(calcul_puissance_charge_requise(E_u_final, _require_positive("temps_charge_cible_h", temps_charge_cible_h, strict=True), eta_charge))
        else:
            _push_inconnue(rapport, "partielles", "charge", "Calculable si E_utile_finale_kwh est déterminée.")

        if P_eff_kw is not None:
            Vchg = _first_non_none(self.tension_charge_v, self.tension_nominale_v)
            if Vchg is not None:
                I_charge_a = float(calcul_courant_depuis_kw_tension(P_eff_kw, _require_positive("tension_charge_v|tension_nominale_v", Vchg, strict=True)))
            else:
                _push_inconnue(rapport, "partielles", "courant_charge_A", "Calculable si tension_charge_v ou tension_nominale_v est fournie.")

        rapport["charge"].update({
            "temps_charge_h": t_charge,
            "puissance_effective_stockee_kw": P_eff_kw,
            "puissance_charge_requise_kw": P_charge_req_kw,
            "courant_charge_A": I_charge_a,
        })

        capacite_ah: Optional[float] = None
        I_decharge_a: Optional[float] = None
        C_decharge: Optional[float] = None
        C_charge: Optional[float] = None
        if E_batt_tot is not None and self.tension_nominale_v is not None:
            Vn = _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)
            capacite_ah = float(calcul_ah_depuis_kwh_tension(E_batt_tot, Vn))
        elif E_batt_tot is not None:
            _push_inconnue(rapport, "partielles", "capacite_Ah_estimee", "Calculable si tension_nominale_v est fournie.")

        if puissance_moyenne_kw is not None and E_batt_tot is not None:
            Pm = _require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
            C_decharge = float(calcul_c_rate_depuis_kw_kwh(Pm, E_batt_tot))
            if self.tension_nominale_v is not None:
                I_decharge_a = float(calcul_courant_depuis_kw_tension(Pm, _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)))
            else:
                _push_inconnue(rapport, "partielles", "courant_decharge_A_estime", "Calculable si tension_nominale_v est fournie.")
        elif E_batt_tot is not None:
            _push_inconnue(rapport, "partielles", "C_rate_decharge", "Calculable si puissance_moyenne_kw est fournie.")

        if self.puissance_charge_kw is not None and E_batt_tot is not None:
            C_charge = float(calcul_c_rate_depuis_kw_kwh(self.puissance_charge_kw, E_batt_tot))

        rapport["electrique"].update({
            "capacite_Ah_estimee": capacite_ah,
            "courant_decharge_A_estime": I_decharge_a,
            "C_rate_decharge_estime": C_decharge,
            "C_rate_charge_estime": C_charge,
        })

    def _analyser_equilibre_systeme(self, rapport: Dict[str, Any], *, eq: ContraintesEquilibreBatterie, E_batt_simple_kwh: Optional[float], E_u_simple_kwh: Optional[float]) -> None:
        out: Dict[str, Any] = {"actif": True, "mode": "equilibre_fiabilite_durabilite_efficience"}
        rapport["equilibre_systeme"] = out

        w = self.fenetre_soc
        P_avg = _first_finite(eq.puissance_sortie_moyenne_kw)
        P_cont = _first_finite(eq.puissance_sortie_continue_kw, P_avg)
        P_pic = _first_finite(eq.puissance_sortie_pic_kw, P_cont)
        P_source_brut = _first_finite(eq.puissance_recharge_source_kw)
        P_source_eff = None if P_source_brut is None else P_source_brut * eq.rendement_recharge_source
        P_avg_corr = None if P_avg is None else P_avg * (1.0 + eq.marge_usage_wltp) / eq.rendement_batterie_vers_moteur
        P_cont_pack = None if P_cont is None else P_cont / eq.rendement_batterie_vers_moteur
        P_pic_pack = None if P_pic is None else P_pic / eq.rendement_batterie_vers_moteur

        out.update({
            "puissance_sortie_moyenne_kw": P_avg,
            "puissance_sortie_continue_kw": P_cont,
            "puissance_sortie_pic_kw": P_pic,
            "puissance_recharge_source_kw": P_source_brut,
            "puissance_recharge_effective_kw": P_source_eff,
            "puissance_moyenne_corrigee_wltp_kw": P_avg_corr,
        })

        # 1) Cohérence source / duty-cycle : si impossible énergétiquement, ne pas masquer par une batterie énorme.
        duty_usage = None
        if P_avg_corr is not None and P_source_eff is not None:
            if P_source_eff <= 0.0:
                _push_alerte(rapport, "coherence", "source_recharge_nulle", "La source de recharge effective est nulle : l'équilibre énergétique long terme est impossible.", "erreur")
            else:
                duty_usage = P_avg_corr / P_source_eff
                out["duty_moteur_usage_estime"] = duty_usage
                if eq.duty_moteur_thermique_max is not None and duty_usage > eq.duty_moteur_thermique_max + 1e-12:
                    _push_alerte(
                        rapport,
                        "coherence",
                        "duty_moteur_thermique_depasse",
                        f"La demande moyenne corrigée ({P_avg_corr:.3f} kW) impose duty≈{duty_usage:.3f}, au-dessus de la limite {eq.duty_moteur_thermique_max:.3f}. Grossir la batterie ne résout pas ce bilan long terme ; il faut plus de puissance source, moins de demande moyenne ou une stratégie différente.",
                        "erreur",
                    )
        elif P_avg_corr is not None:
            _push_inconnue(rapport, "partielles", "duty_moteur_usage_estime", "Calculable si puissance_recharge_source_kw est fournie.")

        # 2) Puissance nette en pire cas : si source < demande continue, la batterie doit décharger même moteur allumé.
        if P_cont_pack is not None and P_source_eff is not None:
            out["puissance_nette_charge_worst_case_kw"] = P_source_eff - P_cont_pack
            if P_source_eff < P_cont_pack:
                _push_alerte(
                    rapport,
                    "coherence",
                    "source_inferieure_traction_continue",
                    f"En pleine demande continue, la source effective ({P_source_eff:.3f} kW) est inférieure à la demande pack ({P_cont_pack:.3f} kW). La batterie se vide même moteur thermique actif.",
                    "avertissement",
                )

        # 3) Contraintes minimales de capacité nominale.
        minima: Dict[str, float] = {}
        if E_batt_simple_kwh is not None:
            minima["dimensionnement_energie_simple"] = E_batt_simple_kwh
        if eq.capacite_nominale_min_kwh is not None:
            minima["capacite_nominale_min_imposee"] = eq.capacite_nominale_min_kwh
        if eq.energie_tampon_min_kwh is not None:
            minima["energie_tampon_min_sur_fenetre_soc"] = eq.energie_tampon_min_kwh / w
        if eq.autonomie_elec_min_h is not None and P_avg_corr is not None:
            minima["autonomie_elec_min_sur_fenetre_soc"] = (P_avg_corr * eq.autonomie_elec_min_h) / w
        if eq.periode_equilibre_h is not None and eq.duty_moteur_thermique_max is not None and P_avg_corr is not None:
            minima["tampon_off_cycle_sur_fenetre_soc"] = (P_avg_corr * (1.0 - eq.duty_moteur_thermique_max) * eq.periode_equilibre_h) / w
        if P_cont_pack is not None and eq.c_rate_decharge_continue_max is not None:
            minima["limite_c_rate_decharge_continue"] = P_cont_pack / eq.c_rate_decharge_continue_max
        if P_pic_pack is not None and eq.c_rate_decharge_pic_max is not None:
            minima["limite_c_rate_decharge_pic"] = P_pic_pack / eq.c_rate_decharge_pic_max
        if P_source_eff is not None and eq.c_rate_charge_max is not None:
            minima["limite_c_rate_charge_source"] = P_source_eff / eq.c_rate_charge_max

        if not minima:
            _push_inconnue(rapport, "partielles", "capacite_nominale_recommandee_kwh", "Aucune contrainte de capacité exploitable : fournir énergie utile, puissance, C-rate ou contrainte temporelle.")
            return

        cap_min = max(minima.values())
        cap_min = max(cap_min, 0.0)
        cap_max = eq.capacite_nominale_max_kwh
        if cap_max is None and eq.masse_pack_max_kg is not None and self.densite_energetique_kwh_kg is not None:
            cap_max = eq.masse_pack_max_kg * self.densite_energetique_kwh_kg
            out["capacite_max_depuis_masse_kwh"] = cap_max
        if cap_max is not None and cap_min > cap_max + 1e-12:
            _push_alerte(
                rapport,
                "dimensionnement",
                "capacite_min_superieure_capacite_max",
                f"Capacité minimale calculée {cap_min:.3f} kWh > capacité maximale autorisée {cap_max:.3f} kWh.",
                "erreur",
            )

        # 4) Recherche d'un optimum simple et transparent.
        cap_candidates = self._generer_capacites_candidates(cap_min, cap_max, eq.capacite_nominale_preferee_kwh)
        evaluations: List[ScoreEquilibre] = []
        for cap in cap_candidates:
            evaluations.append(self._evaluer_capacite_equilibre(cap, eq=eq, P_cont_pack=P_cont_pack, P_pic_pack=P_pic_pack, P_source_eff=P_source_eff, duty_usage=duty_usage))

        feasible = [ev for ev in evaluations if ev.score < 1e8]
        selected = min(feasible or evaluations, key=lambda ev: ev.score)

        out.update({
            "contraintes_min_kwh": minima,
            "capacite_nominale_min_calculee_kwh": cap_min,
            "capacite_nominale_max_autorisee_kwh": cap_max,
            "capacite_nominale_recommandee_kwh": selected.capacite_nominale_kwh,
            "energie_utile_recommandee_kwh": selected.energie_utile_kwh,
            "masse_pack_estimee_kg": selected.masse_pack_kg,
            "c_rate_decharge_continue": selected.c_rate_decharge_continue,
            "c_rate_decharge_pic": selected.c_rate_decharge_pic,
            "c_rate_charge_source": selected.c_rate_charge_source,
            "temps_recharge_fenetre_h": selected.temps_recharge_fenetre_h,
            "duty_moteur_usage_estime": selected.duty_moteur_usage,
            "score_selection": selected.score,
            "raisons_selection": list(selected.raisons),
            "candidats_evalues": [ev.en_dict() for ev in sorted(evaluations, key=lambda x: x.score)[:12]],
        })

        # 5) Courant de charge optimal BMS/TMS si tension/capacité connues.
        Vpack = _first_finite(self.tension_charge_v, self.tension_nominale_v)
        if Vpack is not None:
            Ah_pack = calcul_ah_depuis_kwh_tension(selected.capacite_nominale_kwh, Vpack)
            I_opt = calcul_courant_charge_optimal_a(
                soc=eq.soc_reference_charge,
                temperature_c=eq.temperature_cellules_c,
                c_rate_max=eq.c_rate_charge_max or self.c_rate_charge_preservation,
                capacite_ah=Ah_pack,
                tension_pack_v=Vpack,
                puissance_source_max_kw=P_source_eff,
            )
            out["capacite_Ah_recommandee"] = Ah_pack
            out["courant_charge_optimal_A"] = I_opt
            out["puissance_charge_optimale_kw"] = I_opt * Vpack / 1000.0
        else:
            _push_inconnue(rapport, "partielles", "courant_charge_optimal_A", "Calculable si tension_nominale_v ou tension_charge_v est fournie.")

        # 6) Alertes recharge trop longue / masse.
        if selected.temps_recharge_fenetre_h is not None and eq.temps_recharge_max_h is not None:
            if selected.temps_recharge_fenetre_h > eq.temps_recharge_max_h + 1e-12:
                _push_alerte(
                    rapport,
                    "dimensionnement",
                    "batterie_trop_grande_pour_recharge",
                    f"La recharge de la fenêtre SOC utile demande {selected.temps_recharge_fenetre_h:.3f} h, au-dessus du temps max {eq.temps_recharge_max_h:.3f} h.",
                    "erreur",
                )
        if selected.masse_pack_kg is not None and eq.masse_pack_max_kg is not None and selected.masse_pack_kg > eq.masse_pack_max_kg + 1e-12:
            _push_alerte(
                rapport,
                "dimensionnement",
                "masse_pack_depassee",
                f"Masse pack estimée {selected.masse_pack_kg:.3f} kg > masse max {eq.masse_pack_max_kg:.3f} kg.",
                "erreur",
            )

    def _generer_capacites_candidates(self, cap_min: float, cap_max: Optional[float], cap_pref: Optional[float]) -> List[float]:
        lo = max(0.0, float(cap_min))
        if cap_max is None:
            hi = max(lo * 2.5, lo + 1.0)
        else:
            hi = max(lo, float(cap_max))
        values: set[float] = set()
        values.add(round(lo, 6))
        values.add(round(hi, 6))
        if cap_pref is not None:
            values.add(round(max(lo, min(hi, cap_pref)), 6))
        # Densité plus forte près du minimum pour éviter une batterie trop grosse.
        for f in (1.02, 1.05, 1.10, 1.15, 1.20, 1.30, 1.50, 1.75, 2.00):
            values.add(round(max(lo, min(hi, lo * f)), 6))
        if hi > lo:
            for i in range(25):
                t = i / 24
                values.add(round(lo + (hi - lo) * t, 6))
        return sorted(v for v in values if math.isfinite(v) and v >= lo - 1e-12 and v <= hi + 1e-12)

    def _evaluer_capacite_equilibre(self, cap: float, *, eq: ContraintesEquilibreBatterie, P_cont_pack: Optional[float], P_pic_pack: Optional[float], P_source_eff: Optional[float], duty_usage: Optional[float]) -> ScoreEquilibre:
        reasons: List[str] = []
        score = 0.0
        E_use = cap * self.fenetre_soc
        mass = None
        if self.densite_energetique_kwh_kg is not None:
            mass = cap / self.densite_energetique_kwh_kg
            score += mass * 0.01
            if eq.masse_pack_max_kg is not None and mass > eq.masse_pack_max_kg:
                score += 1e8
                reasons.append("masse_pack_max_depassee")

        C_cont = None if P_cont_pack is None or cap <= 0.0 else P_cont_pack / cap
        C_pic = None if P_pic_pack is None or cap <= 0.0 else P_pic_pack / cap
        C_chg = None if P_source_eff is None or cap <= 0.0 else P_source_eff / cap

        if C_cont is not None and eq.c_rate_decharge_continue_max is not None:
            ratio = C_cont / eq.c_rate_decharge_continue_max
            score += max(0.0, ratio) ** 2 * 10.0
            if ratio > 1.0:
                score += 1e8
                reasons.append("c_rate_decharge_continue_depasse")
        if C_pic is not None and eq.c_rate_decharge_pic_max is not None:
            ratio = C_pic / eq.c_rate_decharge_pic_max
            score += max(0.0, ratio) ** 2 * 3.0
            if ratio > 1.0:
                score += 1e8
                reasons.append("c_rate_decharge_pic_depasse")
        if C_chg is not None and eq.c_rate_charge_max is not None:
            ratio = C_chg / eq.c_rate_charge_max
            score += max(0.0, ratio) ** 2 * 8.0
            if ratio > 1.0:
                score += 1e8
                reasons.append("c_rate_charge_depasse")

        t_recharge = None
        if P_source_eff is not None and P_source_eff > 0.0:
            t_recharge = E_use / P_source_eff
            if eq.temps_recharge_max_h is not None:
                ratio = t_recharge / eq.temps_recharge_max_h
                score += max(0.0, ratio) ** 2 * 4.0
                if ratio > 1.0:
                    score += 1e8
                    reasons.append("temps_recharge_max_depasse")
        elif E_use > 0.0:
            reasons.append("source_recharge_absente")

        if duty_usage is not None and eq.duty_moteur_thermique_max is not None:
            ratio = duty_usage / eq.duty_moteur_thermique_max
            score += max(0.0, ratio) ** 2 * 50.0
            if ratio > 1.0:
                # Pas une propriété de la batterie : on marque, mais la sélection reste utile pour diagnostic.
                reasons.append("duty_moteur_depasse_independant_capacite")

        if eq.capacite_nominale_preferee_kwh is not None:
            score += abs(cap - eq.capacite_nominale_preferee_kwh) / max(eq.capacite_nominale_preferee_kwh, 1e-9)
        else:
            # Préférence contrôlée pour la plus petite batterie qui respecte tout : évite le surdimensionnement.
            score += cap * 0.001

        return ScoreEquilibre(
            capacite_nominale_kwh=float(cap),
            energie_utile_kwh=float(E_use),
            masse_pack_kg=None if mass is None else float(mass),
            c_rate_decharge_continue=None if C_cont is None else float(C_cont),
            c_rate_decharge_pic=None if C_pic is None else float(C_pic),
            c_rate_charge_source=None if C_chg is None else float(C_chg),
            temps_recharge_fenetre_h=None if t_recharge is None else float(t_recharge),
            duty_moteur_usage=None if duty_usage is None else float(duty_usage),
            score=float(score),
            raisons=tuple(reasons),
        )

    def _analyser_electrolyte_solide(self, rapport: Dict[str, Any], **kwargs: Any) -> None:
        if not callable(evaluer_electrolyte_solide) or ElectrolyteSolide is None or CelluleSolide is None or PackSolide is None:
            _push_inconnue(rapport, "partielles", "electrolyte_solide", "Module electrolyte_solide indisponible.")
            return
        elec = ElectrolyteSolide(
            conductivite_ionique_s_m=kwargs.get("conductivite_ionique_s_m"),
            epaisseur_m=kwargs.get("epaisseur_electrolyte_m"),
            resistance_interface_ohm=kwargs.get("resistance_interface_ohm"),
        )
        cell = CelluleSolide(
            surface_active_m2=kwargs.get("surface_active_m2"),
            tension_nominale_v=kwargs.get("tension_cellule_v"),
            capacite_ah=kwargs.get("capacite_cellule_ah"),
            courant_max_a=kwargs.get("courant_cellule_max_a"),
        )
        pack = PackSolide(
            nb_series=kwargs.get("nb_series"),
            nb_parallele=kwargs.get("nb_parallele"),
            puissance_continue_kw=kwargs.get("puissance_pack_continue_kw"),
            puissance_pic_kw=kwargs.get("puissance_pack_pic_kw"),
            rendement_chaine=kwargs.get("rendement_chaine"),
        )
        opts = ElectrolyteOptions(strict=bool(kwargs.get("electrolyte_strict", False))) if ElectrolyteOptions is not None else None
        res = _try("electrolyte_solide", rapport, lambda: evaluer_electrolyte_solide(elec, cell, pack, opts) if opts is not None else evaluer_electrolyte_solide(elec, cell, pack))
        rapport["electrolyte_solide"]["rapport"] = _to_jsonable(res)
        inc = _deep_get(rapport, "electrolyte_solide", "rapport", "inconnues")
        if isinstance(inc, list):
            for item in inc:
                _push_inconnue(rapport, "partielles", f"electrolyte_solide.{item}", "Donnée requise par le modèle électrolyte solide.")

    def _analyser_samsung_25r(self, rapport: Dict[str, Any], **kwargs: Any) -> None:
        if kwargs.get("activer_samsung_25r_twingo"):
            if not callable(dimensionner_pack_samsung_25r_equivalent_twingo):
                _push_inconnue(rapport, "partielles", "dimensionner_pack_samsung_25r_equivalent_twingo", "Fonction indisponible.")
                return
            res = _try(
                "samsung_25r_twingo",
                rapport,
                lambda: dimensionner_pack_samsung_25r_equivalent_twingo(
                    puissance_continue_kw=kwargs.get("puissance_continue_kw") or 0.0,
                    puissance_pic_kw=kwargs.get("puissance_pic_kw") or 0.0,
                    courant_decharge_cellule_conception_a=kwargs.get("courant_decharge_cellule_conception_a") or 10.0,
                    courant_charge_cellule_a=kwargs.get("courant_charge_cellule_a") or 2.0,
                ),
            )
        else:
            if not callable(definir_batterie_samsung_25r):
                _push_inconnue(rapport, "partielles", "definir_batterie_samsung_25r", "Fonction indisponible.")
                return
            res = _try(
                "samsung_25r",
                rapport,
                lambda: definir_batterie_samsung_25r(
                    nb_cellules_total=kwargs.get("nb_cellules_total"),
                    nb_series=kwargs.get("nb_series"),
                    nb_parallele=kwargs.get("nb_parallele"),
                    tension_nominale_cible_v=kwargs.get("tension_nominale_cible_v"),
                    energie_nominale_cible_kwh=kwargs.get("energie_nominale_cible_kwh"),
                    puissance_continue_kw=kwargs.get("puissance_continue_kw") or 0.0,
                    puissance_pic_kw=kwargs.get("puissance_pic_kw") or 0.0,
                    courant_decharge_cellule_conception_a=kwargs.get("courant_decharge_cellule_conception_a") or 10.0,
                    courant_charge_cellule_a=kwargs.get("courant_charge_cellule_a") or 2.0,
                    rendement_charge=kwargs.get("rendement_charge") or self.rendement_charge,
                    reserve_soc=kwargs.get("reserve_soc") if kwargs.get("reserve_soc") is not None else 0.10,
                    masse_hors_cellules_kg=kwargs.get("masse_hors_cellules_kg"),
                    volume_hors_cellules_m3=kwargs.get("volume_hors_cellules_m3") or 0.0,
                    resistance_hors_cellules_ohm=kwargs.get("resistance_hors_cellules_ohm") or 0.0,
                    utiliser_resistance_max=bool(kwargs.get("utiliser_resistance_max")),
                ),
            )
        rapport["samsung_25r"]["rapport"] = _to_jsonable(res)
        if res is not None:
            rapport["dimensionnement_fin"].setdefault("source", "samsung_25r")
            rapport["dimensionnement_fin"]["rapport"] = _to_jsonable(res)

    def _analyser_dimensionnement_fin(self, rapport: Dict[str, Any], **kwargs: Any) -> None:
        if not callable(dimensionner_pack_cellules) or ContraintesPack is None:
            _push_inconnue(rapport, "partielles", "dimensionner_pack_cellules", "Module de dimensionnement fin indisponible.")
            return
        cellule = kwargs.get("cellule_pack")
        if cellule is None:
            if callable(creer_cellule_samsung_25r):
                cellule = creer_cellule_samsung_25r()
                rapport["hypotheses"].append("Dimensionnement fin exécuté avec Samsung 25R locale faute de cellule_pack fournie explicitement.")
            else:
                _push_inconnue(rapport, "impossibles", "cellule_pack", "Requise pour dimensionner un pack cellules si Samsung 25R locale indisponible.")
                return
        E = kwargs.get("energie_nominale_cible_pack_kwh")
        if E is None:
            _push_inconnue(rapport, "impossibles", "energie_nominale_cible_pack_kwh", "Requise pour dimensionnement fin cellules.")
            return
        vmin = kwargs.get("tension_bus_min_v")
        vmax = kwargs.get("tension_bus_max_v")
        target_v = kwargs.get("tension_nominale_cible_pack_v")
        # Si non fourni, on prend une fenêtre bus déduite du target_v et de la cellule seulement si les données existent explicitement.
        if vmin is None or vmax is None:
            if target_v is not None:
                # Dérivation depuis tension cible : on n'invente pas une topologie, on donne une fenêtre large centrée sur le target.
                vmin = vmin if vmin is not None else 0.70 * float(target_v)
                vmax = vmax if vmax is not None else 1.25 * float(target_v)
                rapport["hypotheses"].append("tension_bus_min_v/max_v déduites de tension_nominale_cible_pack_v par bornes larges 0.70/1.25 pour permettre l'exploration ; à remplacer par le bus réel.")
            else:
                _push_inconnue(rapport, "impossibles", "tension_bus_min_v / tension_bus_max_v", "Requises pour dimensionnement fin cellules si tension_nominale_cible_pack_v absente.")
                return
        contraintes = ContraintesPack(
            energie_nominale_cible_kwh=float(E),
            tension_bus_min_v=float(vmin),
            tension_bus_max_v=float(vmax),
            puissance_continue_kw=float(kwargs.get("puissance_continue_kw") or 0.0),
            puissance_pic_kw=float(kwargs.get("puissance_pic_kw") or 0.0),
            tension_nominale_cible_v=target_v,
        )
        res = _try(
            "dimensionnement_fin_pack_cellules",
            rapport,
            lambda: dimensionner_pack_cellules(
                cellule=cellule,
                contraintes=contraintes,
                pertes_passives=kwargs.get("pertes_passives_pack"),
                modele_thermique=kwargs.get("modele_thermique_pack"),
                nb_series_min=kwargs.get("nb_series_min_dim"),
                nb_series_max=kwargs.get("nb_series_max_dim"),
                courant_charge_cellule_a=kwargs.get("courant_charge_cellule_a_dim"),
                rendement_charge=kwargs.get("rendement_charge_dim") or self.rendement_charge,
            ),
        )
        rapport["dimensionnement_fin"].update({"source": "dimensionner_pack_cellules", "rapport": _to_jsonable(res)})

    def _analyser_catalogue(self, rapport: Dict[str, Any], *, catalogue_cellules: Optional[Sequence[Any]], utiliser_samsung_25r_locale_catalogue: bool, catalogue_top_n: int, catalogue_sleep_s: float, energie_cible_kwh: Optional[float], tension_nominale_cible_v: Optional[float], puissance_continue_kw: Optional[float], puissance_pic_kw: Optional[float]) -> None:
        if not callable(classer_candidats_pre_dimensionnement):
            _push_inconnue(rapport, "partielles", "catalogue_cellules", "classer_candidats_pre_dimensionnement indisponible.")
            return
        cellules = list(catalogue_cellules or [])
        if utiliser_samsung_25r_locale_catalogue and callable(cellule_commerciale_samsung_25r_locale):
            try:
                cellules.append(cellule_commerciale_samsung_25r_locale())
            except Exception as exc:
                _push_alerte(rapport, "dimensionnement", "samsung_25r_catalogue_local", str(exc), "avertissement")
        if not cellules and callable(collecter_catalogue_cellules):
            try:
                cellules = list(collecter_catalogue_cellules(sleep_s=catalogue_sleep_s))
            except Exception as exc:
                _push_inconnue(rapport, "partielles", "collecter_catalogue_cellules", f"Échec collecte catalogue: {exc}")
        if not cellules:
            _push_inconnue(rapport, "partielles", "catalogue_cellules", "Aucune cellule catalogue disponible.")
            return
        if energie_cible_kwh is None or tension_nominale_cible_v is None:
            _push_inconnue(rapport, "partielles", "classement_catalogue", "Requiert energie_cible_kwh et tension_nominale_cible_v.")
            return
        res = _try(
            "classer_candidats_pre_dimensionnement",
            rapport,
            lambda: classer_candidats_pre_dimensionnement(
                cellules,
                energie_cible_kwh=float(energie_cible_kwh),
                tension_pack_nominale_v=float(tension_nominale_cible_v),
                puissance_continue_kw=puissance_continue_kw,
                puissance_pic_kw=puissance_pic_kw,
                top_n=int(catalogue_top_n),
            ),
        )
        rapport["catalogue_cellules"]["candidats"] = _to_jsonable(res)

    def _analyser_ratio_conso(self, rapport: Dict[str, Any], *, ratio_params: Optional[Dict[str, Any]], capacite_nominale_kwh: Optional[float]) -> None:
        params = dict(ratio_params or {})
        if not callable(conso_l_100km_pour_capacite):
            _push_inconnue(rapport, "partielles", "ratio_conso", "Module calcul_ratio indisponible.")
            return
        if capacite_nominale_kwh is None:
            _push_inconnue(rapport, "partielles", "ratio_conso", "Calculable si capacite_nominale_kwh est déterminée.")
            return
        required = ("vehicule", "env", "batterie", "thermique", "carburant", "vitesse_kmh", "pente")
        missing = [k for k in required if k not in params]
        if missing:
            _push_inconnue(rapport, "partielles", "ratio_conso", "Données manquantes: " + ", ".join(missing))
            return
        fn = conso_l_100km_pour_capacite_avec_electrolyte_solide if params.get("ssb") is not None and callable(conso_l_100km_pour_capacite_avec_electrolyte_solide) else conso_l_100km_pour_capacite
        res = _try("ratio_conso", rapport, lambda: fn(capacite_nominale_kwh=capacite_nominale_kwh, **params))
        rapport["ratio_conso"]["rapport"] = _to_jsonable(res)

    def _analyser_pieces(self, rapport: Dict[str, Any], *, busbars_densite_courant_a_mm2: Optional[float], busbars_courant_a: Optional[float], bms_soc: float, bms_temperature_cellules_c: float, bms_soh: float, tms_efficacite_echangeur: Optional[float]) -> None:
        pieces: Dict[str, Any] = {}
        common = {"batterie": self, "rapport_batterie": rapport}
        piece_specs = {
            "pack_batterie": (self.piece_pack or PackBatterie(**common), {}),
            "busbars_batterie": (self.piece_busbars or BusbarsBatterie(**common, courant_a=busbars_courant_a, densite_courant_a_mm2=busbars_densite_courant_a_mm2), {}),
            "boitier_batterie": (self.piece_boitier or BoitierBatterie(**common), {}),
            "bms_batterie": (self.piece_bms or BMSBatterie(**common, soc=bms_soc, temperature_cellules_c=bms_temperature_cellules_c, soh=bms_soh), {}),
            "tms_batterie": (self.piece_tms or TMSBatterie(**common, efficacite_echangeur=tms_efficacite_echangeur if tms_efficacite_echangeur is not None else 0.7), {}),
        }
        for name, (obj, kwargs) in piece_specs.items():
            fn = getattr(obj, "analyser", None)
            if callable(fn):
                pieces[name] = _try(f"piece.{name}", rapport, lambda fn=fn, kwargs=kwargs: _call_with_supported_kwargs(fn, strict=False, **kwargs))
            else:
                _push_inconnue(rapport, "partielles", f"piece.{name}", "Objet pièce sans méthode analyser().")
        rapport["pieces"] = _to_jsonable(pieces)
        legacy_aliases = {
            "pack": "pack_batterie",
            "busbars": "busbars_batterie",
            "boitier": "boitier_batterie",
            "bms": "bms_batterie",
            "tms": "tms_batterie",
        }
        for alias, source_name in legacy_aliases.items():
            if source_name in rapport["pieces"] and alias not in rapport["pieces"]:
                rapport["pieces"][alias] = rapport["pieces"][source_name]

    def _synthese_finale(self, rapport: Dict[str, Any]) -> None:
        eq = _safe_dict(rapport.get("equilibre_systeme"))
        dim = _safe_dict(rapport.get("dimensionnement"))
        fin = _safe_dict(_deep_get(rapport, "dimensionnement_fin", "rapport"))
        samsung = _safe_dict(_deep_get(rapport, "samsung_25r", "rapport"))
        inc_imp = len(_deep_get(rapport, "inconnues", "impossibles") or [])
        alert_err = sum(1 for items in _safe_dict(rapport.get("alertes")).values() for it in (items or []) if isinstance(it, Mapping) and it.get("gravite") == "erreur")
        cap = _first_finite(eq.get("capacite_nominale_recommandee_kwh"), dim.get("capacite_totale_kwh"), fin.get("energie_nominale_pack_kwh"), samsung.get("energie_nominale_pack_kwh"))
        mass = _first_finite(eq.get("masse_pack_estimee_kg"), dim.get("masse_batterie_kg"), fin.get("masse_totale_pack_kg"), samsung.get("masse_totale_pack_kg"))
        rapport["synthese"] = {
            "ok_calcul": inc_imp == 0,
            "ok_conception": inc_imp == 0 and alert_err == 0,
            "nb_inconnues_impossibles": inc_imp,
            "nb_alertes_erreur": alert_err,
            "capacite_nominale_recommandee_kwh": cap,
            "energie_utile_recommandee_kwh": _first_finite(eq.get("energie_utile_recommandee_kwh"), dim.get("E_utile_finale_kwh")),
            "masse_pack_estimee_kg": mass,
            "duty_moteur_usage_estime": eq.get("duty_moteur_usage_estime"),
            "temps_recharge_fenetre_h": eq.get("temps_recharge_fenetre_h"),
            "c_rate_charge_source": eq.get("c_rate_charge_source"),
            "c_rate_decharge_continue": eq.get("c_rate_decharge_continue"),
            "diagnostic": self._diagnostic_text(inc_imp, alert_err, eq),
        }

    def _diagnostic_text(self, inc_imp: int, alert_err: int, eq: Mapping[str, Any]) -> str:
        if inc_imp > 0:
            return "Calcul incomplet : des données obligatoires manquent."
        if alert_err > 0:
            return "Conception non validée : au moins une contrainte système est violée."
        if eq.get("capacite_nominale_recommandee_kwh") is not None:
            return "Batterie dimensionnée avec équilibre énergie / recharge / C-rate / masse."
        return "Batterie dimensionnée partiellement ; fournir les contraintes système pour valider l'équilibre."


# =============================================================================
# Exemple de fumée
# =============================================================================


def _demo() -> Dict[str, Any]:
    """Exemple minimal : vérifie le câblage sans valider un véhicule réel."""
    batterie = Batterie(
        fenetre_soc=0.70,
        densite_energetique_kwh_kg=0.16,
        rendement_charge=0.90,
        puissance_charge_kw=35.0,
        tension_nominale_v=360.0,
        c_rate_charge_preservation=0.8,
        c_rate_decharge_continue_preservation=1.5,
        c_rate_decharge_pic_preservation=3.0,
    )
    return batterie.analyser_dimensionnement(
        energie_utile_imposee_kwh=12.0,
        puissance_moyenne_kw=18.0,
        puissance_pic_kw=100.0,
        duree_pic_s=30.0,
        puissance_sortie_continue_kw=60.0,
        puissance_sortie_moyenne_kw=18.0,
        puissance_sortie_pic_kw=100.0,
        puissance_recharge_source_kw=35.0,
        duty_moteur_thermique_max=0.50,
        marge_usage_wltp=0.20,
        autonomie_elec_min_h=0.25,
        temps_recharge_max_h=1.5,
        temperature_cellules_c=30.0,
        soc_reference_charge=0.50,
        activer_samsung_25r=True,
        samsung_tension_nominale_cible_v=360.0,
        samsung_courant_decharge_cellule_conception_a=10.0,
        samsung_courant_charge_cellule_a=2.0,
        busbars_densite_courant_a_mm2=3.0,
    )


if __name__ == "__main__":
    print(json.dumps(_demo()["synthese"], ensure_ascii=False, indent=2))
