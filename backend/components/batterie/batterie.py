# backend/components/batterie/batterie.py
from __future__ import annotations

import inspect
import json
import math
import sys
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Préparation chemins d'import
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent

for candidate in (
    _THIS_DIR,
    _THIS_DIR / "modules",
    _THIS_DIR / "pieces",
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    Path.cwd(),
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


def _import_attr(module_names: Sequence[str], attr: str, *, required: bool = True) -> Any:
    last_error: Optional[Exception] = None
    for module_name in module_names:
        try:
            module = __import__(module_name, fromlist=[attr])
            return getattr(module, attr)
        except Exception as exc:  # pragma: no cover - dépend de l'arborescence runtime
            last_error = exc
    _IMPORT_ERRORS[attr] = " ; ".join([*module_names]) + (f" :: {last_error}" if last_error else "")
    if required:
        raise ImportError(f"Impossible d'importer {attr} depuis {module_names}: {last_error}") from last_error
    return None


def _mod(*names: str) -> Tuple[str, ...]:
    return tuple(names)


# --- modules énergie / dimensionnement simple ---
calcul_capacite_totale_batterie = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_dimensionnement_batterie",
        "backend.modules.batterie.calcul_dimensionnement_batterie",
        "calcul_dimensionnement_batterie",
    ),
    "calcul_capacite_totale_batterie",
)
calcul_poids_batterie = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_dimensionnement_batterie",
        "backend.modules.batterie.calcul_dimensionnement_batterie",
        "calcul_dimensionnement_batterie",
    ),
    "calcul_poids_batterie",
)

calcul_energie_utile_cible = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_energie_utile",
        "backend.modules.batterie.calcul_energie_utile",
        "calcul_energie_utile",
    ),
    "calcul_energie_utile_cible",
)
calcul_energie_utile_trajet = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_energie_utile",
        "backend.modules.batterie.calcul_energie_utile",
        "calcul_energie_utile",
    ),
    "calcul_energie_utile_trajet",
)
calcul_energie_utile_pic = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_energie_utile",
        "backend.modules.batterie.calcul_energie_utile",
        "calcul_energie_utile",
    ),
    "calcul_energie_utile_pic",
)
choisir_energie_utile_finale = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_energie_utile",
        "backend.modules.batterie.calcul_energie_utile",
        "calcul_energie_utile",
    ),
    "choisir_energie_utile_finale",
)

calcul_temps_charge = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_temps_charge",
        "backend.modules.batterie.calcul_temps_charge",
        "calcul_temps_charge",
    ),
    "calcul_temps_charge",
)

# --- électrique pack ---
calcul_conso_kwh_km_depuis_puissance_vitesse = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_conso_kwh_km_depuis_puissance_vitesse",
)
calcul_ah_depuis_kwh_tension = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_ah_depuis_kwh_tension",
)
calcul_kwh_depuis_ah_tension = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_kwh_depuis_ah_tension",
)
calcul_courant_depuis_kw_tension = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_courant_depuis_kw_tension",
)
calcul_puissance_kw_depuis_tension_courant = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_puissance_kw_depuis_tension_courant",
)
calcul_c_rate_depuis_kw_kwh = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_c_rate_depuis_kw_kwh",
)
calcul_puissance_effective_stockee = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_puissance_effective_stockee",
)
calcul_puissance_charge_requise = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_puissance_charge_requise",
)
calcul_temps_charge_constant_power = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_temps_charge_constant_power",
)
calcul_puissance_charge_pack_kw = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_puissance_charge_pack_kw",
)
calcul_section_cuivre_estimee_mm2 = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_electrique_pack",
        "backend.modules.batterie.calcul_electrique_pack",
        "calcul_electrique_pack",
    ),
    "calcul_section_cuivre_estimee_mm2",
)

# --- charge optimale / TMS ---
calcul_courant_charge_optimal_a = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_charge_optimale",
        "backend.modules.batterie.calcul_charge_optimale",
        "calcul_charge_optimale",
    ),
    "calcul_courant_charge_optimal_a",
)
estimer_puissance_refroidissement_tms_w = _import_attr(
    _mod(
        "backend.components.batterie.modules.calcul_charge_optimale",
        "backend.modules.batterie.calcul_charge_optimale",
        "calcul_charge_optimale",
    ),
    "estimer_puissance_refroidissement_tms_w",
)

# --- électrolyte solide ---
ElectrolyteSolide = _import_attr(
    _mod(
        "backend.components.batterie.modules.electrolyte_solide",
        "backend.modules.batterie.electrolyte_solide",
        "electrolyte_solide",
    ),
    "ElectrolyteSolide",
)
CelluleSolide = _import_attr(
    _mod(
        "backend.components.batterie.modules.electrolyte_solide",
        "backend.modules.batterie.electrolyte_solide",
        "electrolyte_solide",
    ),
    "CelluleSolide",
)
PackSolide = _import_attr(
    _mod(
        "backend.components.batterie.modules.electrolyte_solide",
        "backend.modules.batterie.electrolyte_solide",
        "electrolyte_solide",
    ),
    "PackSolide",
)
ElectrolyteOptions = _import_attr(
    _mod(
        "backend.components.batterie.modules.electrolyte_solide",
        "backend.modules.batterie.electrolyte_solide",
        "electrolyte_solide",
    ),
    "Options",
)
evaluer_electrolyte_solide = _import_attr(
    _mod(
        "backend.components.batterie.modules.electrolyte_solide",
        "backend.modules.batterie.electrolyte_solide",
        "electrolyte_solide",
    ),
    "evaluer_electrolyte_solide",
)

# --- dimensionnement cellules / Samsung 25R ---
PointCellule = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "PointCellule",
)
CellulePack = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "Cellule",
)
PertesPassivesPack = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "PertesPassivesPack",
)
ModeleThermiquePack = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "ModeleThermiquePack",
)
ContraintesPack = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "ContraintesPack",
)
DimensionnementPack = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "DimensionnementPack",
)
dimensionner_pack_cellules = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "dimensionner_pack_cellules",
)
evaluer_configuration_pack_cellules = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "evaluer_configuration_pack_cellules",
)
creer_cellule_samsung_25r = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "creer_cellule_samsung_25r",
)
definir_batterie_samsung_25r = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "definir_batterie_samsung_25r",
)
dimensionner_pack_samsung_25r_equivalent_twingo = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "dimensionner_pack_samsung_25r_equivalent_twingo",
)
formatter_rapport_pack = _import_attr(
    _mod(
        "backend.components.batterie.modules.dimensionner_pack_cellules",
        "backend.modules.batterie.dimensionner_pack_cellules",
        "dimensionner_pack_cellules",
    ),
    "formatter_rapport_pack",
)

# --- catalogue / scraping optionnel ---
CelluleCommerciale = _import_attr(
    _mod(
        "backend.components.batterie.modules.scraping_cellules_batterie",
        "backend.modules.batterie.scraping_cellules_batterie",
        "scraping_cellules_batterie",
    ),
    "CelluleCommerciale",
    required=False,
)
collecter_catalogue_cellules = _import_attr(
    _mod(
        "backend.components.batterie.modules.scraping_cellules_batterie",
        "backend.modules.batterie.scraping_cellules_batterie",
        "scraping_cellules_batterie",
    ),
    "collecter_catalogue_cellules",
    required=False,
)
classer_candidats_pre_dimensionnement = _import_attr(
    _mod(
        "backend.components.batterie.modules.scraping_cellules_batterie",
        "backend.modules.batterie.scraping_cellules_batterie",
        "scraping_cellules_batterie",
    ),
    "classer_candidats_pre_dimensionnement",
    required=False,
)
exigences_pour_cellule_complete = _import_attr(
    _mod(
        "backend.components.batterie.modules.scraping_cellules_batterie",
        "backend.modules.batterie.scraping_cellules_batterie",
        "scraping_cellules_batterie",
    ),
    "exigences_pour_cellule_complete",
    required=False,
)
cellule_vers_dict = _import_attr(
    _mod(
        "backend.components.batterie.modules.scraping_cellules_batterie",
        "backend.modules.batterie.scraping_cellules_batterie",
        "scraping_cellules_batterie",
    ),
    "cellule_vers_dict",
    required=False,
)
cellule_commerciale_samsung_25r_locale = _import_attr(
    _mod(
        "backend.components.batterie.modules.scraping_cellules_batterie",
        "backend.modules.batterie.scraping_cellules_batterie",
        "scraping_cellules_batterie",
    ),
    "cellule_commerciale_samsung_25r_locale",
    required=False,
)

# --- ratio autonomie / conso, optionnel ---
Carburant = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "Carburant",
    required=False,
)
Vehicule = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "Vehicule",
    required=False,
)
Environnement = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "Environnement",
    required=False,
)
BatteriePackRatio = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "BatteriePack",
    required=False,
)
Thermique = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "Thermique",
    required=False,
)
ConfigElectrolyteSolideRatio = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "ConfigElectrolyteSolide",
    required=False,
)
conso_l_100km_pour_capacite = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "conso_l_100km_pour_capacite",
    required=False,
)
conso_l_100km_pour_capacite_avec_electrolyte_solide = _import_attr(
    _mod("backend.components.batterie.modules.calcul_ratio", "backend.modules.batterie.calcul_ratio", "calcul_ratio"),
    "conso_l_100km_pour_capacite_avec_electrolyte_solide",
    required=False,
)


# =============================================================================
# Helpers généraux
# =============================================================================


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


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _safe_float(x: Any) -> Optional[float]:
    try:
        f = float(x)
    except Exception:
        return None
    return f if math.isfinite(f) else None


def _deep_get(x: Any, *path: str) -> Any:
    cur = x
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


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append(
        {"nom": str(nom), "raison": str(raison)}
    )


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


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for cat in ("impossibles", "partielles"):
        inc[cat] = _dedup_list_of_dict(list(inc.get(cat, []) or []), ("nom", "raison"))


def _serialize_obj(x: Any) -> Any:
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, dict):
        return {str(k): _serialize_obj(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_serialize_obj(v) for v in x]
    if hasattr(x, "en_dict") and callable(getattr(x, "en_dict")):
        try:
            return _serialize_obj(x.en_dict())
        except Exception:
            pass
    if is_dataclass(x):
        try:
            return _serialize_obj(asdict(x))
        except Exception:
            return {"type": type(x).__name__}
    return {"type": type(x).__name__, "repr": repr(x)}


def _call_with_supported_kwargs(fn: Any, **kwargs: Any) -> Any:
    sig = inspect.signature(fn)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return fn(**kwargs)
    filt = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(**filt)


# =============================================================================
# Pièces batterie : imports robustes + fallbacks autonomes
# =============================================================================


def _try_import_piece(attr: str, *modules: str) -> Any:
    return _import_attr(modules, attr, required=False)


PackBatterieImported = _try_import_piece(
    "PackBatterie",
    "backend.components.batterie.pieces.pack_batterie",
    "backend.modules.batterie.pack_batterie",
    "pack_batterie",
)
BusbarsBatterieImported = _try_import_piece(
    "BusbarsBatterie",
    "backend.components.batterie.pieces.busbars_batterie",
    "backend.modules.batterie.busbars_batterie",
    "busbars_batterie",
)
BoitierBatterieImported = _try_import_piece(
    "BoitierBatterie",
    "backend.components.batterie.pieces.boitier_batterie",
    "backend.modules.batterie.boitier_batterie",
    "boitier_batterie",
)
BMSBatterieImported = _try_import_piece(
    "BMSBatterie",
    "backend.components.batterie.pieces.bms_batterie",
    "backend.modules.batterie.bms_batterie",
    "bms_batterie",
)
TMSBatterieImported = _try_import_piece(
    "TMSBatterie",
    "backend.components.batterie.pieces.tms_batterie",
    "backend.modules.batterie.tms_batterie",
    "tms_batterie",
)


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
        rep: Dict[str, Any] = {
            "piece": "pack_batterie",
            "electrique": {},
            "integration": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        energie = _first_non_none(self.energie_nominale_kwh, _deep_get(source, "dimensionnement", "capacite_totale_kwh"), _deep_get(source, "dimensionnement_fin", "rapport", "energie_nominale_pack_kwh"))
        tension = _first_non_none(self.tension_nominale_v, _deep_get(source, "entrees", "tension_nominale_v"), _deep_get(source, "dimensionnement_fin", "rapport", "tension_nominale_pack_v"))
        capacite = _first_non_none(self.capacite_ah, _deep_get(source, "electrique", "capacite_Ah_estimee"), _deep_get(source, "dimensionnement_fin", "rapport", "capacite_pack_ah"))
        masse = _first_non_none(self.masse_kg, _deep_get(source, "dimensionnement", "masse_batterie_kg"), _deep_get(source, "dimensionnement_fin", "rapport", "masse_totale_pack_kg"))
        volume = _first_non_none(self.volume_m3, _deep_get(source, "dimensionnement_fin", "rapport", "volume_total_pack_m3"))
        ns = _first_non_none(self.nb_series, _deep_get(source, "entrees", "nb_series"), _deep_get(source, "dimensionnement_fin", "rapport", "nb_series"))
        np_ = _first_non_none(self.nb_parallele, _deep_get(source, "entrees", "nb_parallele"), _deep_get(source, "dimensionnement_fin", "rapport", "nb_parallele"))
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
        _dedup_inconnues(rep)
        return rep


@dataclass
class _BusbarsBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    courant_a: Optional[float] = None
    densite_courant_a_mm2: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        source = self.rapport_batterie or {}
        rep: Dict[str, Any] = {
            "piece": "busbars_batterie",
            "electrique": {},
            "dimensionnement": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        courant = _first_non_none(
            self.courant_a,
            _deep_get(source, "charge", "courant_charge_A"),
            _deep_get(source, "electrique", "courant_decharge_A_estime"),
            _deep_get(source, "dimensionnement_fin", "rapport", "rapports_charge", "courant_charge_pack_a"),
        )
        j = self.densite_courant_a_mm2
        rep["electrique"]["courant_a"] = courant
        rep["dimensionnement"]["densite_courant_a_mm2"] = j
        if _is_finite(courant) and _is_finite(j) and float(j) > 0:
            rep["dimensionnement"]["section_cuivre_estimee_mm2"] = float(calcul_section_cuivre_estimee_mm2(float(courant), float(j)))
        else:
            _push_inconnue(rep, "partielles", "section_cuivre_estimee_mm2", "Calculable si courant_a et densite_courant_a_mm2 sont fournis.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class _BoitierBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    masse_pack_kg: Optional[float] = None
    volume_pack_m3: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        source = self.rapport_batterie or {}
        rep: Dict[str, Any] = {
            "piece": "boitier_batterie",
            "integration": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        masse = _first_non_none(self.masse_pack_kg, _deep_get(source, "dimensionnement", "masse_batterie_kg"), _deep_get(source, "dimensionnement_fin", "rapport", "masse_totale_pack_kg"))
        volume = _first_non_none(self.volume_pack_m3, _deep_get(source, "dimensionnement_fin", "rapport", "volume_total_pack_m3"))
        rep["integration"].update({"masse_pack_kg": masse, "volume_interne_m3": volume})
        if not _is_finite(masse):
            _push_inconnue(rep, "partielles", "masse_pack_kg", "Masse du pack requise pour qualifier le boîtier.")
        if not _is_finite(volume):
            _push_inconnue(rep, "partielles", "volume_interne_m3", "Volume disponible si le dimensionnement fin de pack est fourni.")
        _dedup_inconnues(rep)
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
        rep: Dict[str, Any] = {
            "piece": "bms",
            "monitoring": {"soc": self.soc, "temperature_cellules_c": self.temperature_cellules_c, "soh": self.soh},
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
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
        if _is_finite(capacite_ah) and _is_finite(tension_v):
            i_opt = calcul_courant_charge_optimal_a(
                soc=float(self.soc),
                temperature_c=float(self.temperature_cellules_c),
                c_rate_max=float(self.c_rate_max_charge),
                capacite_ah=float(capacite_ah),
                tension_pack_v=float(tension_v),
                t_limit_c=float(self.temperature_alerte_c),
            )
            rep["resultats"]["courant_charge_max_securise_a"] = float(i_opt)
            rep["resultats"]["puissance_charge_max_securisee_kw"] = float(i_opt) * float(tension_v) / 1000.0
            if float(self.temperature_cellules_c) >= float(self.temperature_alerte_c):
                rep["resultats"]["alerte_securite"] = "Surchauffe : charge à réduire ou interrompre."
        else:
            _push_inconnue(rep, "impossibles", "calcul_charge_securisee", "Capacité Ah et tension nominale requises.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class _TMSBatterieFallback:
    batterie: Optional[Any] = None
    rapport_batterie: Optional[Dict[str, Any]] = None
    type_refroidissement: str = "Air"
    efficacite_echangeur: float = 0.7
    temperature_liquide_entree_c: float = 20.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "piece": "tms",
            "technologie": {"type": self.type_refroidissement, "efficacite": self.efficacite_echangeur},
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        source = self.rapport_batterie or {}
        i_charge = _first_non_none(
            _deep_get(source, "charge", "courant_charge_A"),
            _deep_get(source, "dimensionnement_fin", "rapport", "rapports_charge", "courant_charge_pack_a"),
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
        _dedup_inconnues(rep)
        return rep


PackBatterie = PackBatterieImported or _PackBatterieFallback
BusbarsBatterie = BusbarsBatterieImported or _BusbarsBatterieFallback
BoitierBatterie = BoitierBatterieImported or _BoitierBatterieFallback
BMSBatterie = BMSBatterieImported or _BMSBatterieFallback
TMSBatterie = TMSBatterieImported or _TMSBatterieFallback


# =============================================================================
# Composant Batterie
# =============================================================================


@dataclass(frozen=True)
class Batterie:
    """
    Orchestrateur batterie.

    Le composant agrège les modules fournis : énergie utile, capacité totale,
    masse, temps de charge, électricité pack, charge optimale, électrolyte solide,
    dimensionnement cellules, Samsung 25R, catalogue et pièces pack/BMS/TMS.

    Règle de conception : aucune hypothèse métier implicite. Une valeur absente
    devient une inconnue explicite, sauf constantes physiques ou choix déjà
    explicités dans les modules appelés.
    """

    fenetre_soc: float = 0.8
    densite_energetique_kwh_kg: Optional[float] = None
    rendement_charge: float = 0.90
    puissance_charge_kw: Optional[float] = None
    tension_nominale_v: Optional[float] = None
    tension_charge_v: Optional[float] = None

    piece_pack: Optional[Any] = None
    piece_busbars: Optional[Any] = None
    piece_boitier: Optional[Any] = None
    piece_bms: Optional[Any] = None
    piece_tms: Optional[Any] = None

    def __post_init__(self) -> None:
        _require_ratio_0_1("fenetre_soc", self.fenetre_soc, allow_zero=False)
        _require_ratio_0_1("rendement_charge", self.rendement_charge, allow_zero=False)
        if self.densite_energetique_kwh_kg is not None:
            _require_positive("densite_energetique_kwh_kg", self.densite_energetique_kwh_kg, strict=True)
        if self.puissance_charge_kw is not None:
            _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False)
        if self.tension_nominale_v is not None:
            _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)
        if self.tension_charge_v is not None:
            _require_positive("tension_charge_v", self.tension_charge_v, strict=True)

    @property
    def capacite_ah_estimee(self) -> Optional[float]:
        return None

    def analyser(
        self,
        *,
        strict: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self.analyser_dimensionnement(**kwargs)

    def analyser_dimensionnement(
        self,
        *,
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
        tms_efficacite_echangeur: Optional[float] = None,
    ) -> Dict[str, Any]:
        if calculer_puissance_charge_requise is not None:
            calculer_puissance_charge_requise_flag = bool(calculer_puissance_charge_requise)

        rapport: Dict[str, Any] = {
            "composant": "batterie",
            "entrees": {},
            "energies_utiles": {},
            "dimensionnement": {},
            "charge": {},
            "electrique": {},
            "electrolyte_solide": {},
            "catalogue_cellules": {},
            "dimensionnement_fin": {},
            "samsung_25r": {},
            "ratio_conso": {},
            "pieces": {},
            "hypotheses": [],
            "notes_modele": [],
            "unites": {},
            "imports_manquants": dict(_IMPORT_ERRORS),
            "inconnues": {"impossibles": [], "partielles": []},
        }

        w = _require_ratio_0_1("fenetre_soc", self.fenetre_soc, allow_zero=False)
        eta_charge = _require_ratio_0_1("rendement_charge", self.rendement_charge, allow_zero=False)
        if mode_aggregation_energie not in ("max", "somme"):
            raise ValueError("mode_aggregation_energie doit être 'max' ou 'somme'.")
        if catalogue_top_n <= 0:
            raise ValueError("catalogue_top_n doit être > 0.")

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
            "activer_electrolyte_solide": activer_electrolyte_solide,
            "nb_series": nb_series,
            "nb_parallele": nb_parallele,
            "activer_catalogue_cellules": activer_catalogue_cellules,
            "activer_dimensionnement_fin": activer_dimensionnement_fin,
            "activer_samsung_25r": activer_samsung_25r,
            "activer_samsung_25r_twingo": activer_samsung_25r_twingo,
            "activer_ratio_conso": activer_ratio_conso,
        }
        rapport["unites"] = {
            "energie": "kWh",
            "puissance": "kW",
            "courant": "A",
            "tension": "V",
            "masse": "kg",
            "temps": "h",
            "résistance": "ohm",
            "pertes": "W",
        }

        # ------------------------------------------------------------------
        # 1) Énergies utiles
        # ------------------------------------------------------------------
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

        E_imposee: Optional[float] = None
        if energie_utile_imposee_kwh is not None:
            E_imposee = _require_positive("energie_utile_imposee_kwh", energie_utile_imposee_kwh, strict=False)

        candidates = [v for v in (E_trajet, E_charge_cible, E_pic, E_imposee) if v is not None]
        E_u_final: Optional[float] = None
        if candidates:
            E_u_final = float(choisir_energie_utile_finale(*candidates)) if mode_aggregation_energie == "max" else float(sum(candidates))
            if mode_aggregation_energie == "somme":
                rapport["hypotheses"].append("E_utile_finale obtenue par somme des contraintes disponibles.")
        else:
            _push_inconnue(rapport, "impossibles", "E_utile_finale_kwh", "Impossible sans au moins un critère : trajet, charge cible, pic ou énergie imposée.")

        rapport["energies_utiles"] = {
            "conso_kwh_km_derivee": conso_derivee,
            "E_trajet_kwh": E_trajet,
            "E_charge_cible_kwh": E_charge_cible,
            "E_pic_kwh": E_pic,
            "E_imposee_kwh": E_imposee,
            "E_utile_finale_kwh": E_u_final,
        }

        # ------------------------------------------------------------------
        # 2) Capacité totale + masse
        # ------------------------------------------------------------------
        E_batt_tot: Optional[float] = None
        m_batt: Optional[float] = None
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
        })

        # ------------------------------------------------------------------
        # 3) Charge / courant / C-rate
        # ------------------------------------------------------------------
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
        elif puissance_moyenne_kw is not None:
            _push_inconnue(rapport, "partielles", "C_rate_decharge_estime", "Calculable si capacite_totale_kwh est déterminée.")

        if self.puissance_charge_kw is not None and E_batt_tot is not None:
            C_charge = float(calcul_c_rate_depuis_kw_kwh(_require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False), E_batt_tot))

        rapport["electrique"].update({
            "capacite_Ah_estimee": capacite_ah,
            "courant_decharge_A_estime": I_decharge_a,
            "C_rate_decharge_estime": C_decharge,
            "C_rate_charge_estime": C_charge,
        })

        # ------------------------------------------------------------------
        # 4) Électrolyte solide
        # ------------------------------------------------------------------
        if activer_electrolyte_solide:
            try:
                rep_elec = evaluer_electrolyte_solide(
                    ElectrolyteSolide(
                        conductivite_ionique_s_m=conductivite_ionique_s_m,
                        epaisseur_m=epaisseur_electrolyte_m,
                        resistance_interface_ohm=resistance_interface_ohm,
                    ),
                    CelluleSolide(
                        surface_active_m2=surface_active_m2,
                        tension_nominale_v=tension_cellule_v,
                        capacite_ah=capacite_cellule_ah,
                        courant_max_a=courant_cellule_max_a,
                    ),
                    PackSolide(
                        nb_series=nb_series,
                        nb_parallele=nb_parallele,
                        puissance_continue_kw=_first_non_none(puissance_pack_continue_kw, puissance_moyenne_kw),
                        puissance_pic_kw=_first_non_none(puissance_pack_pic_kw, puissance_pic_kw),
                        rendement_chaine=rendement_chaine,
                    ),
                    opts=ElectrolyteOptions(strict=bool(electrolyte_strict)),
                )
                rapport["electrolyte_solide"] = {"active": True, "rapport": _serialize_obj(rep_elec)}
            except Exception as exc:
                rapport["electrolyte_solide"] = {"active": True, "erreur": str(exc)}
                _push_inconnue(rapport, "partielles", "electrolyte_solide", f"Échec du calcul : {exc}")
        else:
            rapport["electrolyte_solide"] = {"active": False}

        # ------------------------------------------------------------------
        # 5) Catalogue commercial
        # ------------------------------------------------------------------
        if activer_catalogue_cellules:
            if collecter_catalogue_cellules is None or classer_candidats_pre_dimensionnement is None:
                rapport["catalogue_cellules"] = {"active": True, "erreur": "module scraping_cellules_batterie indisponible"}
                _push_inconnue(rapport, "partielles", "catalogue_cellules", "Module de catalogue/scraping indisponible.")
            else:
                e_nom_cat = _first_non_none(energie_nominale_cible_pack_kwh, E_batt_tot)
                v_nom_cat = _first_non_none(tension_nominale_cible_pack_v, self.tension_nominale_v)
                if e_nom_cat is None or v_nom_cat is None:
                    rapport["catalogue_cellules"] = {"active": True, "candidats": []}
                    _push_inconnue(rapport, "partielles", "catalogue_cellules", "Calculable si énergie nominale cible et tension nominale cible sont connues.")
                else:
                    try:
                        if catalogue_cellules is not None:
                            cells = list(catalogue_cellules)
                            rapport["hypotheses"].append("Catalogue cellules fourni explicitement : aucun scraping lancé.")
                        elif utiliser_samsung_25r_locale_catalogue and cellule_commerciale_samsung_25r_locale is not None:
                            cells = [cellule_commerciale_samsung_25r_locale()]
                            rapport["hypotheses"].append("Catalogue local Samsung 25R utilisé : aucune requête réseau.")
                        else:
                            cells = list(collecter_catalogue_cellules(sleep_s=float(catalogue_sleep_s)))
                            rapport["hypotheses"].append("Catalogue collecté via URLs explicites du module de scraping.")
                        candidats = classer_candidats_pre_dimensionnement(
                            cellules=cells,
                            energie_nominale_cible_kwh=float(e_nom_cat),
                            tension_pack_nominale_cible_v=float(v_nom_cat),
                            puissance_continue_kw=_first_non_none(puissance_pack_continue_kw, puissance_moyenne_kw),
                            puissance_pic_kw=_first_non_none(puissance_pack_pic_kw, puissance_pic_kw),
                        )
                        top_items: List[Dict[str, Any]] = []
                        for predim in candidats[:catalogue_top_n]:
                            src = next((c for c in cells if getattr(c.specs, "reference", None) == predim.reference), None)
                            besoins = [] if src is None or exigences_pour_cellule_complete is None else exigences_pour_cellule_complete(src.specs)
                            top_items.append({
                                "pre_dimensionnement": _serialize_obj(predim),
                                "cellule_catalogue": None if src is None or cellule_vers_dict is None else cellule_vers_dict(src),
                                "besoins_dimensionnement_fin": besoins,
                            })
                        rapport["catalogue_cellules"] = {
                            "active": True,
                            "energie_nominale_cible_pack_kwh": float(e_nom_cat),
                            "tension_nominale_cible_pack_v": float(v_nom_cat),
                            "nb_candidats": len(candidats),
                            "candidats": top_items,
                        }
                    except Exception as exc:
                        rapport["catalogue_cellules"] = {"active": True, "erreur": str(exc), "candidats": []}
                        _push_inconnue(rapport, "partielles", "catalogue_cellules", f"Échec du catalogue : {exc}")
        else:
            rapport["catalogue_cellules"] = {"active": False}

        # ------------------------------------------------------------------
        # 6) Dimensionnement fin générique
        # ------------------------------------------------------------------
        if activer_dimensionnement_fin:
            e_nom_fin = _first_non_none(energie_nominale_cible_pack_kwh, E_batt_tot)
            p_cont_fin = _first_non_none(puissance_pack_continue_kw, puissance_moyenne_kw)
            p_pic_fin = _first_non_none(puissance_pack_pic_kw, puissance_pic_kw)
            if cellule_pack is None:
                rapport["dimensionnement_fin"] = {"active": True, "erreur": "cellule_pack manquante"}
                _push_inconnue(rapport, "partielles", "dimensionnement_fin", "Le dimensionnement fin exige une Cellule complète avec OCV, résistances et limites courant.")
            elif e_nom_fin is None or tension_bus_min_v is None or tension_bus_max_v is None or p_cont_fin is None or p_pic_fin is None:
                rapport["dimensionnement_fin"] = {"active": True, "erreur": "contraintes incomplètes"}
                _push_inconnue(rapport, "partielles", "dimensionnement_fin", "Requiert énergie cible, tensions bus min/max, puissance continue et puissance pic.")
            else:
                try:
                    contraintes = ContraintesPack(
                        energie_nominale_cible_kwh=float(e_nom_fin),
                        tension_bus_min_v=_require_positive("tension_bus_min_v", tension_bus_min_v, strict=True),
                        tension_bus_max_v=_require_positive("tension_bus_max_v", tension_bus_max_v, strict=True),
                        puissance_continue_kw=_require_positive("puissance_continue_pack_kw", p_cont_fin, strict=False),
                        puissance_pic_kw=_require_positive("puissance_pic_pack_kw", p_pic_fin, strict=False),
                        tension_nominale_cible_v=_first_non_none(tension_nominale_cible_pack_v, self.tension_nominale_v),
                        duree_pic_s=None if duree_pic_s is None else _require_positive("duree_pic_s", duree_pic_s, strict=True),
                    )
                    dim = dimensionner_pack_cellules(
                        cellule=cellule_pack,
                        contraintes=contraintes,
                        pertes_passives=pertes_passives_pack,
                        modele_thermique=modele_thermique_pack,
                        nb_series_min=nb_series_min_dim,
                        nb_series_max=nb_series_max_dim,
                        courant_charge_cellule_a=courant_charge_cellule_a_dim,
                        rendement_charge=eta_charge if rendement_charge_dim is None else rendement_charge_dim,
                    )
                    dim_dict = _serialize_obj(dim)
                    rapport["dimensionnement_fin"] = {"active": True, "rapport": dim_dict}
                    rapport["dimensionnement"]["capacite_totale_kwh_dimensionnement_fin"] = dim_dict.get("energie_nominale_pack_kwh")
                    rapport["dimensionnement"]["masse_batterie_kg_dimensionnement_fin"] = dim_dict.get("masse_totale_pack_kg")
                    rapport["electrique"]["resistance_interne_pack_ohm"] = _first_non_none(dim_dict.get("resistance_pack_nominale_ohm"), dim_dict.get("resistance_pack_min_ohm"))
                except Exception as exc:
                    rapport["dimensionnement_fin"] = {"active": True, "erreur": str(exc)}
                    _push_inconnue(rapport, "partielles", "dimensionnement_fin", f"Échec : {exc}")
        else:
            rapport["dimensionnement_fin"] = {"active": False}

        # ------------------------------------------------------------------
        # 7) Samsung 25R direct
        # ------------------------------------------------------------------
        if activer_samsung_25r or activer_samsung_25r_twingo:
            try:
                if activer_samsung_25r_twingo:
                    dim_s = dimensionner_pack_samsung_25r_equivalent_twingo(
                        puissance_continue_kw=0.0 if puissance_pack_continue_kw is None else float(puissance_pack_continue_kw),
                        puissance_pic_kw=0.0 if puissance_pack_pic_kw is None else float(puissance_pack_pic_kw),
                        courant_decharge_cellule_conception_a=float(samsung_courant_decharge_cellule_conception_a),
                        courant_charge_cellule_a=float(samsung_courant_charge_cellule_a),
                    )
                else:
                    dim_s = definir_batterie_samsung_25r(
                        nb_cellules_total=samsung_nb_cellules_total,
                        nb_series=samsung_nb_series,
                        nb_parallele=samsung_nb_parallele,
                        tension_nominale_cible_v=_first_non_none(samsung_tension_nominale_cible_v, tension_nominale_cible_pack_v, self.tension_nominale_v),
                        energie_nominale_cible_kwh=_first_non_none(samsung_energie_nominale_cible_kwh, energie_nominale_cible_pack_kwh, E_batt_tot),
                        puissance_continue_kw=0.0 if puissance_pack_continue_kw is None else float(puissance_pack_continue_kw),
                        puissance_pic_kw=0.0 if puissance_pack_pic_kw is None else float(puissance_pack_pic_kw),
                        courant_decharge_cellule_conception_a=float(samsung_courant_decharge_cellule_conception_a),
                        courant_charge_cellule_a=float(samsung_courant_charge_cellule_a),
                        rendement_charge=eta_charge,
                        reserve_soc=float(samsung_reserve_soc),
                        masse_hors_cellules_kg=samsung_masse_hors_cellules_kg,
                        volume_hors_cellules_m3=float(samsung_volume_hors_cellules_m3),
                        resistance_hors_cellules_ohm=float(samsung_resistance_hors_cellules_ohm),
                        utiliser_resistance_max=bool(samsung_utiliser_resistance_max),
                    )
                rapport["samsung_25r"] = {
                    "active": True,
                    "rapport": _serialize_obj(dim_s),
                    "texte": formatter_rapport_pack(dim_s) if formatter_rapport_pack is not None else None,
                }
            except Exception as exc:
                rapport["samsung_25r"] = {"active": True, "erreur": str(exc)}
                _push_inconnue(rapport, "partielles", "samsung_25r", f"Échec du dimensionnement Samsung 25R : {exc}")
        else:
            rapport["samsung_25r"] = {"active": False}

        # ------------------------------------------------------------------
        # 8) Ratio conso carburant/batterie
        # ------------------------------------------------------------------
        if activer_ratio_conso:
            if conso_l_100km_pour_capacite is None:
                rapport["ratio_conso"] = {"active": True, "erreur": "module calcul_ratio indisponible"}
                _push_inconnue(rapport, "partielles", "ratio_conso", "Module calcul_ratio indisponible.")
            elif ratio_params is None:
                rapport["ratio_conso"] = {"active": True, "erreur": "ratio_params manquant"}
                _push_inconnue(rapport, "partielles", "ratio_conso", "Fournir ratio_params avec vehicule/env/batterie/thermique/carburant/vitesse/pente.")
            else:
                try:
                    rapport["ratio_conso"] = {"active": True, "rapport": _serialize_obj(conso_l_100km_pour_capacite(**ratio_params))}
                except Exception as exc:
                    rapport["ratio_conso"] = {"active": True, "erreur": str(exc)}
                    _push_inconnue(rapport, "partielles", "ratio_conso", f"Échec : {exc}")
        else:
            rapport["ratio_conso"] = {"active": False}

        # ------------------------------------------------------------------
        # 9) Pièces pack / BMS / TMS
        # ------------------------------------------------------------------
        if analyser_pieces:
            pieces_rapport: Dict[str, Any] = {}
            pack_piece = self.piece_pack or PackBatterie(batterie=self, rapport_batterie=rapport)
            busbars_piece = self.piece_busbars or BusbarsBatterie(
                batterie=self,
                rapport_batterie=rapport,
                courant_a=busbars_courant_a,
                densite_courant_a_mm2=busbars_densite_courant_a_mm2,
            )
            boitier_piece = self.piece_boitier or BoitierBatterie(batterie=self, rapport_batterie=rapport)
            if self.piece_bms is not None:
                bms_piece = self.piece_bms
            else:
                bms_kwargs = {"batterie": self, "rapport_batterie": rapport}
                bms_piece = BMSBatterie(**bms_kwargs)
            if bms_soc is not None and hasattr(bms_piece, "soc"):
                try:
                    setattr(bms_piece, "soc", float(bms_soc))
                except Exception:
                    pass
            if bms_temperature_cellules_c is not None and hasattr(bms_piece, "temperature_cellules_c"):
                try:
                    setattr(bms_piece, "temperature_cellules_c", float(bms_temperature_cellules_c))
                except Exception:
                    pass
            if self.piece_tms is not None:
                tms_piece = self.piece_tms
            else:
                tms_piece = TMSBatterie(batterie=self, rapport_batterie=rapport)
            if tms_efficacite_echangeur is not None and hasattr(tms_piece, "efficacite_echangeur"):
                try:
                    setattr(tms_piece, "efficacite_echangeur", float(tms_efficacite_echangeur))
                except Exception:
                    pass
            for nom, piece in (
                ("pack", pack_piece),
                ("busbars", busbars_piece),
                ("boitier", boitier_piece),
                ("bms", bms_piece),
                ("tms", tms_piece),
            ):
                if piece is not None and hasattr(piece, "analyser"):
                    try:
                        pieces_rapport[nom] = _call_with_supported_kwargs(piece.analyser, strict=False)
                    except Exception as exc:
                        pieces_rapport[nom] = {"erreur": str(exc)}
            rapport["pieces"] = pieces_rapport
        else:
            rapport["pieces"] = {"active": False}

        # ------------------------------------------------------------------
        # 10) Inconnues structurelles
        # ------------------------------------------------------------------
        _push_inconnue(rapport, "impossibles", "vieillissement / durée de vie", "Impossible sans modèle de vieillissement : cycles, DoD, C-rate, température, chimie, données fabricant.")
        _push_inconnue(rapport, "impossibles", "courbe CC/CV complète", "Le temps de charge simple reste un modèle à puissance constante ; la phase CV réelle doit venir d'une fiche cellule ou d'essais.")
        if modele_thermique_pack is None and not activer_samsung_25r:
            _push_inconnue(rapport, "impossibles", "thermique pack détaillée", "Impossible sans architecture pack, résistances internes, modèle thermique, ambiance et profils de charge/décharge.")

        rapport["energie_utile"] = {
            "kwh_finale": E_u_final,
            "kwh_trajet": E_trajet,
            "kwh_pic": E_pic,
        }
        _dedup_inconnues(rapport)
        return rapport

    def analyser_recharge_systeme(
        self,
        *,
        rapport_alternateur: Optional[Dict[str, Any]] = None,
        rapport_moteur_elec: Optional[Dict[str, Any]] = None,
        rapport_batterie: Optional[Dict[str, Any]] = None,
        soc_actuel: float = 0.5,
        temperature_pack_c: float = 25.0,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "flux_energie_kw": {},
            "securite_cellules": {},
            "optimisation": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }
        P_alt_w = _first_finite(
            _deep_get(rapport_alternateur, "bus_dc", "puissance_bus_dc_W"),
            _deep_get(rapport_alternateur, "resultats", "P_out_W"),
            _deep_get(rapport_alternateur, "alternateur", "resultats", "P_out_W"),
            _deep_get(rapport_alternateur, "synthese", "alternateur", "P_electrique_W"),
        )
        P_mot_kw = _first_finite(
            _deep_get(rapport_moteur_elec, "electrique", "puissance_absorbee_kw"),
            _deep_get(rapport_moteur_elec, "resultats", "P_elec_W"),
            _deep_get(rapport_moteur_elec, "demande", "P_moteur_W") / 1000.0 if _is_finite(_deep_get(rapport_moteur_elec, "demande", "P_moteur_W")) else None,
        )
        P_alt_kw = None if P_alt_w is None else P_alt_w / 1000.0
        if P_alt_kw is None:
            _push_inconnue(rep, "partielles", "puissance alternateur", "Fournir un rapport alternateur avec puissance bus DC / P_out_W.")
            P_alt_kw = 0.0
        if P_mot_kw is None:
            P_mot_kw = 0.0
        P_dispo = P_alt_kw - P_mot_kw
        rep["flux_energie_kw"] = {"alternateur_prod": P_alt_kw, "moteur_conso": P_mot_kw, "bilan_disponible": P_dispo}

        bms_piece = self.piece_bms or BMSBatterie(batterie=self, rapport_batterie=rapport_batterie)
        if hasattr(bms_piece, "soc"):
            try:
                setattr(bms_piece, "soc", float(soc_actuel))
            except Exception:
                pass
        if hasattr(bms_piece, "temperature_cellules_c"):
            try:
                setattr(bms_piece, "temperature_cellules_c", float(temperature_pack_c))
            except Exception:
                pass
        try:
            bms_rep = _call_with_supported_kwargs(bms_piece.analyser, strict=False)
            P_safe = _deep_get(bms_rep, "resultats", "puissance_charge_max_securisee_kw")
            rep["securite_cellules"]["bms"] = bms_rep
            rep["securite_cellules"]["puissance_charge_max_autorisee_kw"] = P_safe
            if _is_finite(P_safe):
                P_reel = max(0.0, min(P_dispo, float(P_safe)))
                rep["optimisation"]["puissance_charge_reelle_kw"] = P_reel
                rep["optimisation"]["limitee_par"] = "BMS" if float(P_safe) < P_dispo else "source"
                rep["optimisation"]["etat"] = "décharge nette" if P_dispo < 0 else "recharge possible"
            else:
                _push_inconnue(rep, "partielles", "puissance_charge_max_autorisee_kw", "BMS incapable de calculer la puissance charge sûre sans capacité Ah et tension pack.")
        except Exception as exc:
            _push_inconnue(rep, "impossibles", "optimisation_recharge", f"BMS non exploitable : {exc}")
        _dedup_inconnues(rep)
        return rep


# =============================================================================
# API haut niveau
# =============================================================================


def construire_batterie(config: Optional[Mapping[str, Any]] = None) -> Batterie:
    cfg = dict(config or {})
    kwargs = {
        "fenetre_soc": cfg.get("fenetre_soc", 0.8),
        "densite_energetique_kwh_kg": cfg.get("densite_energetique_kwh_kg"),
        "rendement_charge": cfg.get("rendement_charge", 0.90),
        "puissance_charge_kw": cfg.get("puissance_charge_kw"),
        "tension_nominale_v": cfg.get("tension_nominale_v"),
        "tension_charge_v": cfg.get("tension_charge_v"),
        "piece_pack": cfg.get("piece_pack"),
        "piece_busbars": cfg.get("piece_busbars"),
        "piece_boitier": cfg.get("piece_boitier"),
        "piece_bms": cfg.get("piece_bms"),
        "piece_tms": cfg.get("piece_tms"),
    }
    return Batterie(**kwargs)


def concevoir_batterie(config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(config or {})
    batterie = cfg.get("batterie")
    if batterie is None:
        batterie = construire_batterie(cfg)
    elif isinstance(batterie, dict):
        batterie = construire_batterie(batterie)
    if not isinstance(batterie, Batterie):
        if hasattr(batterie, "analyser"):
            return _serialize_obj(_call_with_supported_kwargs(batterie.analyser, **dict(cfg.get("analyse", cfg))))
        raise TypeError("config['batterie'] doit être une Batterie, un dict ou un objet avec analyser().")
    analyse_cfg = dict(cfg.get("analyse", {}))
    init_keys = {
        "batterie",
        "analyse",
        "fenetre_soc",
        "densite_energetique_kwh_kg",
        "rendement_charge",
        "puissance_charge_kw",
        "tension_nominale_v",
        "tension_charge_v",
        "piece_pack",
        "piece_busbars",
        "piece_boitier",
        "piece_bms",
        "piece_tms",
    }
    allowed = set(inspect.signature(batterie.analyser_dimensionnement).parameters)
    for k, v in cfg.items():
        if k not in init_keys and k in allowed and k not in analyse_cfg:
            analyse_cfg[k] = v
    return batterie.analyser_dimensionnement(**analyse_cfg)


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | Path, *, indent: int = 2) -> Path:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_serialize_obj(dict(rapport)), ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


__all__ = [
    "Batterie",
    "construire_batterie",
    "concevoir_batterie",
    "exporter_rapport_json",
    "PackBatterie",
    "BusbarsBatterie",
    "BoitierBatterie",
    "BMSBatterie",
    "TMSBatterie",
    "PointCellule",
    "CellulePack",
    "PertesPassivesPack",
    "ModeleThermiquePack",
    "ContraintesPack",
    "DimensionnementPack",
    "creer_cellule_samsung_25r",
    "definir_batterie_samsung_25r",
    "dimensionner_pack_samsung_25r_equivalent_twingo",
    "formatter_rapport_pack",
]


if __name__ == "__main__":
    demo = concevoir_batterie(
        {
            "fenetre_soc": 0.80,
            "densite_energetique_kwh_kg": 0.16,
            "rendement_charge": 0.92,
            "puissance_charge_kw": 18.0,
            "tension_nominale_v": 345.6,
            "distance_km": 100.0,
            "conso_kwh_km": 0.16,
            "temps_charge_cible_h": 0.5,
            "puissance_pic_kw": 90.0,
            "duree_pic_s": 10.0,
            "activer_samsung_25r_twingo": True,
            "puissance_pack_continue_kw": 60.0,
            "puissance_pack_pic_kw": 90.0,
            "utiliser_samsung_25r_locale_catalogue": True,
            "analyser_pieces": True,
        }
    )
    print(json.dumps(_serialize_obj(demo), ensure_ascii=False, indent=2)[:4000])
