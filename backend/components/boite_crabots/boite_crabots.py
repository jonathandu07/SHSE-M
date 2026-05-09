from __future__ import annotations

"""
boite_crabots.py — composant orchestrateur de boîte à crabots
================================================================

Objectif :
- utiliser les modules spécialisés de la boîte à crabots quand ils existent ;
- rester exécutable en isolé avec des formules de secours explicites ;
- analyser la boîte complète : engrenage, arbre, crabot, roulements, choc d'engagement ;
- orchestrer les pièces : arbre, pignon, crabot, roulement, baladeur, fourchette, carter ;
- ne jamais inventer de cote, coefficient matériau, datasheet ou limite admissible.

Toutes les unités sont SI : m, kg, s, N, Pa, W, tr/min, rad/s.
"""

import importlib
import inspect
import json
import math
import sys
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, Optional, Sequence, Tuple, List


# =============================================================================
# Préparation du chemin projet
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent
for _candidate in (_THIS_DIR, _THIS_DIR.parent, _THIS_DIR.parent.parent, Path.cwd()):
    if str(_candidate) not in sys.path:
        sys.path.append(str(_candidate))


# =============================================================================
# Imports robustes
# =============================================================================

_MISSING = object()


def _import_attr(module_names: Sequence[str], attr: str, default: Any = _MISSING) -> Any:
    last_error: Optional[BaseException] = None
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr)
        except Exception as exc:  # robustesse runtime
            last_error = exc
    if default is not _MISSING:
        return default
    raise ImportError(f"Impossible d'importer {attr} depuis {module_names}: {last_error}")


# -----------------------------------------------------------------------------
# Fonctions de calcul — modules spécialisés si présents, sinon secours explicite.
# -----------------------------------------------------------------------------

calcul_inertie_equivalente = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_choc_engagement",
        "components.boite_crabots.modules.calcul_choc_engagement",
        "boite_crabots.modules.calcul_choc_engagement",
        "modules.calcul_choc_engagement",
        "calcul_choc_engagement",
    ),
    "calcul_inertie_equivalente",
    default=None,
)
calcul_energie_choc = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_choc_engagement",
        "components.boite_crabots.modules.calcul_choc_engagement",
        "boite_crabots.modules.calcul_choc_engagement",
        "modules.calcul_choc_engagement",
        "calcul_choc_engagement",
    ),
    "calcul_energie_choc",
    default=None,
)
calcul_couple_synchronisation_moyen = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_choc_engagement",
        "components.boite_crabots.modules.calcul_choc_engagement",
        "boite_crabots.modules.calcul_choc_engagement",
        "modules.calcul_choc_engagement",
        "calcul_choc_engagement",
    ),
    "calcul_couple_synchronisation_moyen",
    default=None,
)
calcul_force_tangentielle = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_force_pignon",
        "components.boite_crabots.modules.calcul_force_pignon",
        "boite_crabots.modules.calcul_force_pignon",
        "modules.calcul_force_pignon",
        "calcul_force_pignon",
    ),
    "calcul_force_tangentielle",
    default=None,
)
calcul_forces_engrenage = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_force_pignon",
        "components.boite_crabots.modules.calcul_force_pignon",
        "boite_crabots.modules.calcul_force_pignon",
        "modules.calcul_force_pignon",
        "calcul_force_pignon",
    ),
    "calcul_forces_engrenage",
    default=None,
)
calcul_contrainte_contact_hertz = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_contact_dent",
        "components.boite_crabots.modules.calcul_contact_dent",
        "boite_crabots.modules.calcul_contact_dent",
        "modules.calcul_contact_dent",
        "calcul_contact_dent",
    ),
    "calcul_contrainte_contact_hertz",
    default=None,
)
calcul_contrainte_flexion_lewis = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_flexion_dent",
        "components.boite_crabots.modules.calcul_flexion_dent",
        "boite_crabots.modules.calcul_flexion_dent",
        "modules.calcul_flexion_dent",
        "calcul_flexion_dent",
    ),
    "calcul_contrainte_flexion_lewis",
    default=None,
)
calcul_contrainte_cisaillement_torsion = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_dimensionnement_arbre",
        "components.boite_crabots.modules.calcul_dimensionnement_arbre",
        "boite_crabots.modules.calcul_dimensionnement_arbre",
        "modules.calcul_dimensionnement_arbre",
        "calcul_dimensionnement_arbre",
    ),
    "calcul_contrainte_cisaillement_torsion",
    default=None,
)
calcul_contrainte_flexion_arbre = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_dimensionnement_arbre",
        "components.boite_crabots.modules.calcul_dimensionnement_arbre",
        "boite_crabots.modules.calcul_dimensionnement_arbre",
        "modules.calcul_dimensionnement_arbre",
        "calcul_dimensionnement_arbre",
    ),
    "calcul_contrainte_flexion_arbre",
    default=None,
)
calcul_von_mises_arbre = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_dimensionnement_arbre",
        "components.boite_crabots.modules.calcul_dimensionnement_arbre",
        "boite_crabots.modules.calcul_dimensionnement_arbre",
        "modules.calcul_dimensionnement_arbre",
        "calcul_dimensionnement_arbre",
    ),
    "calcul_von_mises_arbre",
    default=None,
)
calcul_couple_transmissible_crabot = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_dimensionnement_crabot",
        "components.boite_crabots.modules.calcul_dimensionnement_crabot",
        "boite_crabots.modules.calcul_dimensionnement_crabot",
        "modules.calcul_dimensionnement_crabot",
        "calcul_dimensionnement_crabot",
    ),
    "calcul_couple_transmissible_crabot",
    default=None,
)
calcul_pression_contact_crabot = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_dimensionnement_crabot",
        "components.boite_crabots.modules.calcul_dimensionnement_crabot",
        "boite_crabots.modules.calcul_dimensionnement_crabot",
        "modules.calcul_dimensionnement_crabot",
        "calcul_dimensionnement_crabot",
    ),
    "calcul_pression_contact_crabot",
    default=None,
)
calcul_charge_equivalente_roulement = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_duree_vie_roulement",
        "components.boite_crabots.modules.calcul_duree_vie_roulement",
        "boite_crabots.modules.calcul_duree_vie_roulement",
        "modules.calcul_duree_vie_roulement",
        "calcul_duree_vie_roulement",
    ),
    "calcul_charge_equivalente_roulement",
    default=None,
)
calcul_duree_vie_l10 = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_duree_vie_roulement",
        "components.boite_crabots.modules.calcul_duree_vie_roulement",
        "boite_crabots.modules.calcul_duree_vie_roulement",
        "modules.calcul_duree_vie_roulement",
        "calcul_duree_vie_roulement",
    ),
    "calcul_duree_vie_l10",
    default=None,
)
calcul_duree_vie_heures = _import_attr(
    (
        "backend.components.boite_crabots.modules.calcul_duree_vie_roulement",
        "components.boite_crabots.modules.calcul_duree_vie_roulement",
        "boite_crabots.modules.calcul_duree_vie_roulement",
        "modules.calcul_duree_vie_roulement",
        "calcul_duree_vie_roulement",
    ),
    "calcul_duree_vie_heures",
    default=None,
)


# =============================================================================
# Helpers généraux
# =============================================================================

TypeRoulement = Literal["bille", "rouleau"]
ConnexionCrabot = Literal["direct", "via_engrenage"]
StrategieOptimisation = Literal[
    "max_eta_alternateur",
    "min_pertes_alternateur",
    "min_couple_moteur",
    "pareto",
]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strictly: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strictly else x >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


def _safe_float(x: Any) -> Optional[float]:
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    if isinstance(x, int) and not isinstance(x, bool):
        return x
    f = _safe_float(x)
    if f is None:
        return None
    return int(f)


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _safe_get_float(obj: Any, name: str) -> Optional[float]:
    return _safe_float(_safe_getattr(obj, name, None))


def _get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj.get(name)
        return None
    for name in names:
        if hasattr(obj, name):
            try:
                return getattr(obj, name)
            except Exception:
                pass
    return None


def _omega_from_rpm(rpm: float) -> float:
    return (2.0 * math.pi) * (_require_positive("rpm", rpm, strictly=True) / 60.0)


def _rpm_from_omega(omega_rad_s: float) -> float:
    return (_require_finite("omega_rad_s", omega_rad_s) * 60.0) / (2.0 * math.pi)


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, str]] = []
        for item in list(inc.get(categorie, []) or []):
            if not isinstance(item, dict):
                continue
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key in seen:
                continue
            seen.add(key)
            out.append({"nom": key[0], "raison": key[1]})
        inc[categorie] = out


def _merge_inconnues(dst: Dict[str, Any], src: Optional[Dict[str, Any]], *, prefix: str) -> None:
    if not isinstance(src, dict):
        return
    inc = src.get("inconnues", {}) if isinstance(src.get("inconnues", {}), dict) else {}
    for categorie in ("impossibles", "partielles"):
        for item in list(inc.get(categorie, []) or []):
            if isinstance(item, dict):
                _push_inconnue(dst, categorie, f"{prefix} :: {item.get('nom', '')}", str(item.get("raison", "")))


def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 6) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if is_dataclass(value):
        try:
            return _to_jsonable(asdict(value), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _to_jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {
                "type": type(value).__name__,
                "attributs": _to_jsonable({k: v for k, v in vars(value).items() if not k.startswith("_")}, depth=depth + 1, max_depth=max_depth),
            }
        except Exception:
            pass
    return {"type": type(value).__name__}


def _call_with_supported_kwargs(fn: Any, kwargs: Mapping[str, Any]) -> Any:
    if not callable(fn):
        raise TypeError("fn doit être appelable")
    try:
        sig = inspect.signature(fn)
        accepts_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if accepts_varkw:
            return fn(**dict(kwargs))
        accepted = set(sig.parameters.keys())
        return fn(**{k: v for k, v in kwargs.items() if k in accepted})
    except (TypeError, ValueError):
        return fn(**dict(kwargs))


# =============================================================================
# Formules de secours si les modules spécialisés ne sont pas importables
# =============================================================================

if calcul_inertie_equivalente is None:
    def calcul_inertie_equivalente(inertie_primaire: float, inertie_secondaire: float, *, clamp_non_negative: bool = True) -> float:
        J1 = _require_positive("inertie_primaire", inertie_primaire, strictly=False)
        J2 = _require_positive("inertie_secondaire", inertie_secondaire, strictly=False)
        if J1 + J2 <= 0.0:
            return 0.0
        val = (J1 * J2) / (J1 + J2)
        return max(0.0, val) if clamp_non_negative else val

if calcul_energie_choc is None:
    def calcul_energie_choc(inertie_eq: float, delta_omega_rad_s: float, *, clamp_non_negative: bool = True) -> float:
        J = _require_positive("inertie_eq", inertie_eq, strictly=False)
        dw = _require_finite("delta_omega_rad_s", delta_omega_rad_s)
        val = 0.5 * J * dw * dw
        return max(0.0, val) if clamp_non_negative else val

if calcul_couple_synchronisation_moyen is None:
    def calcul_couple_synchronisation_moyen(
        inertie_eq: float,
        delta_omega_rad_s: float,
        temps_engagement_s: float,
        *,
        use_abs_delta_omega: bool = True,
        clamp_non_negative: bool = False,
    ) -> float:
        J = _require_positive("inertie_eq", inertie_eq, strictly=False)
        dw = _require_finite("delta_omega_rad_s", delta_omega_rad_s)
        if use_abs_delta_omega:
            dw = abs(dw)
        t = _require_positive("temps_engagement_s", temps_engagement_s, strictly=True)
        val = J * dw / t
        return max(0.0, val) if clamp_non_negative else val

if calcul_force_tangentielle is None:
    def calcul_force_tangentielle(
        couple_nm: float,
        diametre_primitif_m: float,
        *,
        use_abs_couple: bool = True,
        clamp_non_negative: bool = True,
    ) -> float:
        T = _require_finite("couple_nm", couple_nm)
        if use_abs_couple:
            T = abs(T)
        d = _require_positive("diametre_primitif_m", diametre_primitif_m, strictly=True)
        val = 2.0 * T / d
        return max(0.0, val) if clamp_non_negative else val

if calcul_forces_engrenage is None:
    def calcul_forces_engrenage(
        force_tangentielle: float,
        angle_pression_deg: float = 20.0,
        angle_helice_deg: float = 0.0,
        *,
        output: str = "FT_FR_FA",
        use_abs_force: bool = True,
        clamp_non_negative: bool = False,
    ) -> Dict[str, float]:
        Ft = _require_finite("force_tangentielle", force_tangentielle)
        if use_abs_force:
            Ft = abs(Ft)
        alpha = math.radians(_require_finite("angle_pression_deg", angle_pression_deg))
        beta = math.radians(_require_finite("angle_helice_deg", angle_helice_deg))
        cos_beta = max(abs(math.cos(beta)), 1e-12)
        Fr = Ft * math.tan(alpha) / cos_beta
        Fa = Ft * math.tan(beta)
        if clamp_non_negative:
            Ft, Fr, Fa = max(0.0, Ft), max(0.0, Fr), max(0.0, Fa)
        return {"F_t": float(Ft), "F_r": float(Fr), "F_a": float(Fa), "F_tangentielle": float(Ft), "F_radiale": float(Fr), "F_axiale": float(Fa)}

if calcul_contrainte_contact_hertz is None:
    def calcul_contrainte_contact_hertz(
        force_tangentielle: float,
        largeur_denture_b: float,
        diametre_primitif_moyen: float,
        coefficient_zh: float,
        *,
        use_abs_force: bool = True,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        Ft = _require_finite("force_tangentielle", force_tangentielle)
        if use_abs_force:
            Ft = abs(Ft)
        b = _require_positive("largeur_denture_b", largeur_denture_b, strictly=True)
        d = _require_positive("diametre_primitif_moyen", diametre_primitif_moyen, strictly=True)
        Zh = _require_positive("coefficient_zh", coefficient_zh, strictly=True)
        sigma = Zh * math.sqrt(max(0.0, Ft) / (b * d))
        if clamp_non_negative:
            sigma = max(0.0, sigma)
        return {"sigma_H_Pa": sigma} if return_details else sigma

if calcul_contrainte_flexion_lewis is None:
    def calcul_contrainte_flexion_lewis(
        force_tangentielle: float,
        largeur_denture_b: float,
        module_m: float,
        facteur_forme_y: float,
        *,
        use_abs_force: bool = True,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        Ft = _require_finite("force_tangentielle", force_tangentielle)
        if use_abs_force:
            Ft = abs(Ft)
        b = _require_positive("largeur_denture_b", largeur_denture_b, strictly=True)
        m = _require_positive("module_m", module_m, strictly=True)
        y = _require_positive("facteur_forme_y", facteur_forme_y, strictly=True)
        sigma = Ft / (b * m * y)
        if clamp_non_negative:
            sigma = max(0.0, sigma)
        return {"sigma_F_Pa": sigma} if return_details else sigma

if calcul_contrainte_cisaillement_torsion is None:
    def calcul_contrainte_cisaillement_torsion(couple_nm: float, diametre_arbre_m: float, *, use_abs_couple: bool = True, clamp_non_negative: bool = True) -> float:
        T = _require_finite("couple_nm", couple_nm)
        if use_abs_couple:
            T = abs(T)
        d = _require_positive("diametre_arbre_m", diametre_arbre_m, strictly=True)
        tau = 16.0 * T / (math.pi * d ** 3)
        return max(0.0, tau) if clamp_non_negative else tau

if calcul_contrainte_flexion_arbre is None:
    def calcul_contrainte_flexion_arbre(moment_flechissant_nm: float, diametre_arbre_m: float, *, use_abs_moment: bool = True, clamp_non_negative: bool = True) -> float:
        M = _require_finite("moment_flechissant_nm", moment_flechissant_nm)
        if use_abs_moment:
            M = abs(M)
        d = _require_positive("diametre_arbre_m", diametre_arbre_m, strictly=True)
        sigma = 32.0 * M / (math.pi * d ** 3)
        return max(0.0, sigma) if clamp_non_negative else sigma

if calcul_von_mises_arbre is None:
    def calcul_von_mises_arbre(contrainte_flexion: float, contrainte_cisaillement: float, *, mode: str = "flexion+torsion", clamp_non_negative: bool = True) -> float:
        sigma = _require_finite("contrainte_flexion", contrainte_flexion)
        tau = _require_finite("contrainte_cisaillement", contrainte_cisaillement)
        vm = math.sqrt(sigma * sigma + 3.0 * tau * tau)
        return max(0.0, vm) if clamp_non_negative else vm

if calcul_couple_transmissible_crabot is None:
    def calcul_couple_transmissible_crabot(
        nombre_dents: int,
        pression_admissible: float,
        hauteur_dent: float,
        largeur_dent: float,
        rayon_moyen: float,
        facteur_repartition: float = 1.0,
        *,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        z = int(_require_positive("nombre_dents", nombre_dents, strictly=True))
        p = _require_positive("pression_admissible", pression_admissible, strictly=False)
        h = _require_positive("hauteur_dent", hauteur_dent, strictly=True)
        b = _require_positive("largeur_dent", largeur_dent, strictly=True)
        r = _require_positive("rayon_moyen", rayon_moyen, strictly=True)
        k = _require_positive("facteur_repartition", facteur_repartition, strictly=True)
        T = z * p * h * b * r * k
        if clamp_non_negative:
            T = max(0.0, T)
        return {"T_cap_Nm": T} if return_details else T

if calcul_pression_contact_crabot is None:
    def calcul_pression_contact_crabot(
        couple_nm: float,
        nombre_dents: int,
        hauteur_dent: float,
        largeur_dent: float,
        rayon_moyen: float,
        *,
        facteur_repartition: float = 1.0,
        use_abs_couple: bool = True,
        clamp_non_negative: bool = True,
        return_details: bool = False,
    ) -> float | Dict[str, float]:
        T = _require_finite("couple_nm", couple_nm)
        if use_abs_couple:
            T = abs(T)
        z = int(_require_positive("nombre_dents", nombre_dents, strictly=True))
        h = _require_positive("hauteur_dent", hauteur_dent, strictly=True)
        b = _require_positive("largeur_dent", largeur_dent, strictly=True)
        r = _require_positive("rayon_moyen", rayon_moyen, strictly=True)
        k = _require_positive("facteur_repartition", facteur_repartition, strictly=True)
        p = T / (z * h * b * r * k)
        if clamp_non_negative:
            p = max(0.0, p)
        return {"p_contact_Pa": p} if return_details else p

if calcul_charge_equivalente_roulement is None:
    def calcul_charge_equivalente_roulement(force_radiale: float, force_axiale: float, facteur_x: float, facteur_y: float, *, use_abs_forces: bool = True, clamp_non_negative: bool = True) -> float:
        Fr = _require_finite("force_radiale", force_radiale)
        Fa = _require_finite("force_axiale", force_axiale)
        if use_abs_forces:
            Fr, Fa = abs(Fr), abs(Fa)
        X = _require_positive("facteur_x", facteur_x, strictly=False)
        Y = _require_positive("facteur_y", facteur_y, strictly=False)
        P = X * Fr + Y * Fa
        return max(0.0, P) if clamp_non_negative else P

if calcul_duree_vie_l10 is None:
    def calcul_duree_vie_l10(charge_dynamique_base_c: float, charge_equivalente_p: float, type_roulement: str = "bille", exposant_p: Optional[float] = None, *, clamp_non_negative: bool = True) -> float:
        C = _require_positive("charge_dynamique_base_c", charge_dynamique_base_c, strictly=True)
        P = _require_positive("charge_equivalente_p", charge_equivalente_p, strictly=True)
        exp = float(exposant_p) if exposant_p is not None else (3.0 if str(type_roulement).lower() == "bille" else 10.0 / 3.0)
        L10 = (C / P) ** exp
        return max(0.0, L10) if clamp_non_negative else L10

if calcul_duree_vie_heures is None:
    def calcul_duree_vie_heures(l10_millions: float, vitesse_rotation_tr_min: float, *, clamp_non_negative: bool = True) -> float:
        L10 = _require_positive("l10_millions", l10_millions, strictly=False)
        rpm = _require_positive("vitesse_rotation_tr_min", vitesse_rotation_tr_min, strictly=True)
        h = (L10 * 1_000_000.0) / (60.0 * rpm)
        return max(0.0, h) if clamp_non_negative else h


# =============================================================================
# Imports métier et pièces
# =============================================================================

Alternateur = _import_attr(
    ("backend.components.alternateur.alternateur", "backend.components.alternateur", "components.alternateur.alternateur", "alternateur"),
    "Alternateur",
    default=Any,
)
MoteurThermique = _import_attr(
    ("backend.components.moteur_thermique.moteur_thermique", "backend.components.moteur_thermique", "components.moteur_thermique.moteur_thermique", "moteur_thermique"),
    "MoteurThermique",
    default=Any,
)

ArbreBoite = _import_attr(("backend.components.boite_crabots.pieces.arbre_boite", "components.boite_crabots.pieces.arbre_boite", "pieces.arbre_boite", "arbre_boite"), "ArbreBoite", default=None)
PieceCrabot = _import_attr(("backend.components.boite_crabots.pieces.crabot", "components.boite_crabots.pieces.crabot", "pieces.crabot", "crabot"), "Crabot", default=None)
PignonBoite = _import_attr(("backend.components.boite_crabots.pieces.pignon_boite", "components.boite_crabots.pieces.pignon_boite", "pieces.pignon_boite", "pignon_boite"), "PignonBoite", default=None)
RoulementBoite = _import_attr(("backend.components.boite_crabots.pieces.roulement_boite", "components.boite_crabots.pieces.roulement_boite", "pieces.roulement_boite", "roulement_boite"), "RoulementBoite", default=None)
Baladeur = _import_attr(("backend.components.boite_crabots.pieces.baladeur", "components.boite_crabots.pieces.baladeur", "pieces.baladeur", "baladeur"), "Baladeur", default=None)
Fourchette = _import_attr(("backend.components.boite_crabots.pieces.fourchette", "components.boite_crabots.pieces.fourchette", "pieces.fourchette", "fourchette"), "Fourchette", default=None)
CarterBoite = _import_attr(("backend.components.boite_crabots.pieces.carter_boite", "components.boite_crabots.pieces.carter_boite", "pieces.carter_boite", "carter_boite"), "CarterBoite", default=None)


# =============================================================================
# Pièces de secours si les fichiers de pièces ne sont pas importables
# =============================================================================

@dataclass
class _LocalArbreBoite:
    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None
    couple_max_Nm: Optional[float] = None
    moment_flechissant_max_Nm: Optional[float] = None
    diametre_arbre_m: Optional[float] = None
    tau_admissible_pa: Optional[float] = None
    sigma_admissible_pa: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    facteur_securite: float = 2.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "arbre_boite", "dimensionnements": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm if self.couple_max_Nm is not None else _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        M = self.moment_flechissant_max_Nm
        tau_adm = self.tau_admissible_pa
        sig_adm = self.sigma_admissible_pa
        if tau_adm is None and self.limite_elastique_pa is not None:
            tau_adm = float(self.limite_elastique_pa) / (max(self.facteur_securite, 1e-12) * math.sqrt(3.0))
            rep["notes_modele"].append("tau_admissible_pa déduit de limite_elastique_pa / (S*sqrt(3)).")
        if sig_adm is None and self.limite_elastique_pa is not None:
            sig_adm = float(self.limite_elastique_pa) / max(self.facteur_securite, 1e-12)
            rep["notes_modele"].append("sigma_admissible_pa déduit de limite_elastique_pa / S.")
        d_candidates: List[float] = []
        if T is not None and tau_adm is not None and tau_adm > 0:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            d_t = (16.0 * T / (math.pi * tau_adm)) ** (1.0 / 3.0)
            rep["dimensionnements"]["d_min_torsion_m"] = d_t
            d_candidates.append(d_t)
        else:
            _push_inconnue(rep, "partielles", "d_min_torsion_m", "Calculable si couple_max_Nm et tau_admissible_pa sont connus.")
        if M is not None and sig_adm is not None and sig_adm > 0:
            M = _require_positive("moment_flechissant_max_Nm", M, strictly=False)
            d_f = (32.0 * M / (math.pi * sig_adm)) ** (1.0 / 3.0)
            rep["dimensionnements"]["d_min_flexion_m"] = d_f
            d_candidates.append(d_f)
        d = self.diametre_arbre_m if self.diametre_arbre_m is not None else (max(d_candidates) if d_candidates else None)
        if d is None:
            _push_inconnue(rep, "impossibles", "diametre_arbre_m", "Impossible de vérifier l'arbre sans diamètre ou contraintes admissibles.")
        else:
            rep["dimensionnements"]["diametre_arbre_m"] = float(d)
            if T is not None:
                tau = calcul_contrainte_cisaillement_torsion(T, d, use_abs_couple=True, clamp_non_negative=True)
                rep["contraintes"]["tau_torsion_reel_pa"] = tau
                if tau_adm is not None:
                    rep["contraintes"]["ok_torsion"] = bool(tau <= tau_adm)
            if M is not None:
                sig = calcul_contrainte_flexion_arbre(M, d, use_abs_moment=True, clamp_non_negative=True)
                rep["contraintes"]["sigma_flexion_reel_pa"] = sig
                if sig_adm is not None:
                    rep["contraintes"]["ok_flexion"] = bool(sig <= sig_adm)
        _dedup_inconnues(rep)
        return rep


@dataclass
class _LocalPignonBoite:
    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None
    couple_max_Nm: Optional[float] = None
    diametre_primitif_m: Optional[float] = None
    largeur_denture_b_m: Optional[float] = None
    module_m: Optional[float] = None
    angle_pression_deg: float = 20.0
    angle_helice_deg: float = 0.0
    coefficient_zh: Optional[float] = None
    facteur_forme_y: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "pignon_boite", "entrees": {}, "forces": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm if self.couple_max_Nm is not None else _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        Ft: Optional[float] = None
        if T is None:
            _push_inconnue(rep, "impossibles", "couple_max_Nm", "Requis pour calculer les efforts sur denture.")
        elif self.diametre_primitif_m is None:
            _push_inconnue(rep, "partielles", "diametre_primitif_m", "Requis pour calculer F_t = 2T/d.")
        else:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            Ft = calcul_force_tangentielle(T, self.diametre_primitif_m, use_abs_couple=True, clamp_non_negative=True)
            forces = calcul_forces_engrenage(Ft, self.angle_pression_deg, self.angle_helice_deg, output="FT_FR_FA", use_abs_force=True, clamp_non_negative=False)
            rep["forces"].update({"F_tangentielle_N": Ft, "F_radiale_N": float(forces["F_r"]), "F_axiale_N": float(forces["F_a"])})
        if Ft is not None and self.largeur_denture_b_m is not None and self.diametre_primitif_m is not None and self.coefficient_zh is not None:
            rep["contraintes"]["sigma_contact_hertz_pa"] = calcul_contrainte_contact_hertz(Ft, self.largeur_denture_b_m, self.diametre_primitif_m, self.coefficient_zh, use_abs_force=True, clamp_non_negative=True, return_details=False)
        else:
            _push_inconnue(rep, "partielles", "calcul_hertz", "Ft, largeur_denture_b_m, diametre_primitif_m et coefficient_zh requis.")
        if Ft is not None and self.largeur_denture_b_m is not None and self.module_m is not None and self.facteur_forme_y is not None:
            rep["contraintes"]["sigma_flexion_lewis_pa"] = calcul_contrainte_flexion_lewis(Ft, self.largeur_denture_b_m, self.module_m, self.facteur_forme_y, use_abs_force=True, clamp_non_negative=True, return_details=False)
        else:
            _push_inconnue(rep, "partielles", "calcul_lewis", "Ft, largeur_denture_b_m, module_m et facteur_forme_y requis.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class _LocalPieceCrabot:
    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None
    couple_max_Nm: Optional[float] = None
    delta_omega_rad_s: Optional[float] = None
    temps_engagement_s: Optional[float] = None
    inertie_primaire_kg_m2: Optional[float] = None
    inertie_secondaire_kg_m2: Optional[float] = None
    nombre_dents: Optional[int] = None
    hauteur_dent_m: Optional[float] = None
    largeur_dent_m: Optional[float] = None
    rayon_moyen_m: Optional[float] = None
    facteur_repartition: float = 1.0
    pression_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "crabot", "entrees": {}, "choc_engagement": {}, "dimensionnements": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm if self.couple_max_Nm is not None else _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        if T is not None:
            rep["entrees"]["couple_max_Nm"] = _require_positive("couple_max_Nm", T, strictly=False)
        else:
            _push_inconnue(rep, "impossibles", "couple_max_Nm", "Requis pour valider le couple transmissible.")
        if self.inertie_primaire_kg_m2 is not None and self.inertie_secondaire_kg_m2 is not None:
            Jeq = calcul_inertie_equivalente(self.inertie_primaire_kg_m2, self.inertie_secondaire_kg_m2, clamp_non_negative=True)
            rep["choc_engagement"]["inertie_equivalente_kg_m2"] = Jeq
            if self.delta_omega_rad_s is not None:
                rep["choc_engagement"]["energie_choc_J"] = calcul_energie_choc(Jeq, self.delta_omega_rad_s, clamp_non_negative=True)
                if self.temps_engagement_s is not None:
                    rep["choc_engagement"]["couple_synchronisation_moyen_Nm"] = calcul_couple_synchronisation_moyen(Jeq, self.delta_omega_rad_s, self.temps_engagement_s, use_abs_delta_omega=True)
                else:
                    _push_inconnue(rep, "partielles", "temps_engagement_s", "Requis pour calculer le couple de synchronisation.")
            else:
                _push_inconnue(rep, "partielles", "delta_omega_rad_s", "Requis pour calculer l'énergie de choc.")
        else:
            _push_inconnue(rep, "partielles", "inerties", "inertie_primaire_kg_m2 et inertie_secondaire_kg_m2 requises pour le choc.")
        geo_ok = self.nombre_dents is not None and self.hauteur_dent_m is not None and self.largeur_dent_m is not None and self.rayon_moyen_m is not None
        if geo_ok:
            if self.pression_admissible_pa is not None:
                Tcap = calcul_couple_transmissible_crabot(self.nombre_dents, self.pression_admissible_pa, self.hauteur_dent_m, self.largeur_dent_m, self.rayon_moyen_m, self.facteur_repartition, clamp_non_negative=True, return_details=False)
                rep["dimensionnements"]["couple_transmissible_max_Nm"] = Tcap
                if T is not None:
                    rep["contraintes"]["ok_couple"] = bool(abs(float(T)) <= Tcap)
            else:
                _push_inconnue(rep, "partielles", "pression_admissible_pa", "Requis pour calculer le couple transmissible max.")
            if T is not None:
                peff = calcul_pression_contact_crabot(T, self.nombre_dents, self.hauteur_dent_m, self.largeur_dent_m, self.rayon_moyen_m, facteur_repartition=self.facteur_repartition, use_abs_couple=True, clamp_non_negative=True, return_details=False)
                rep["contraintes"]["pression_contact_effective_pa"] = peff
        else:
            _push_inconnue(rep, "partielles", "geometrie_crabot", "nombre_dents, hauteur, largeur et rayon moyen requis.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class _LocalRoulementBoite:
    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None
    pignon: Optional[Any] = None
    force_radiale_N: Optional[float] = None
    force_axiale_N: Optional[float] = None
    rpm: Optional[float] = None
    capacite_dynamique_C_N: Optional[float] = None
    facteur_X: Optional[float] = None
    facteur_Y: Optional[float] = None
    type_roulement: TypeRoulement = "bille"
    exposant_p: Optional[float] = None
    duree_vie_cible_heures: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "roulement_boite", "entrees": {}, "duree_vie": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        Fr, Fa = self.force_radiale_N, self.force_axiale_N
        if (Fr is None or Fa is None) and self.pignon is not None and hasattr(self.pignon, "analyser"):
            try:
                p_rep = self.pignon.analyser()
                Fr = Fr if Fr is not None else p_rep.get("forces", {}).get("F_radiale_N")
                Fa = Fa if Fa is not None else p_rep.get("forces", {}).get("F_axiale_N")
            except Exception:
                pass
        rpm = self.rpm if self.rpm is not None else _get(self.moteur_thermique, "rpm", "regime_rpm")
        if rpm is not None:
            rep["entrees"]["rpm"] = _require_positive("rpm", rpm, strictly=False)
        else:
            _push_inconnue(rep, "partielles", "rpm", "Requis pour convertir L10 en heures.")
        if Fr is not None:
            rep["entrees"]["force_radiale_N"] = float(Fr)
        else:
            _push_inconnue(rep, "impossibles", "force_radiale_N", "Requise pour évaluer la charge équivalente.")
        if Fa is not None:
            rep["entrees"]["force_axiale_N"] = float(Fa)
        P_eq = None
        if Fr is not None and Fa is not None and self.facteur_X is not None and self.facteur_Y is not None:
            P_eq = calcul_charge_equivalente_roulement(Fr, Fa, self.facteur_X, self.facteur_Y, use_abs_forces=True, clamp_non_negative=True)
            rep["duree_vie"]["charge_equivalente_P_N"] = P_eq
        else:
            _push_inconnue(rep, "partielles", "charge_equivalente", "Fr, Fa, facteur_X et facteur_Y requis.")
        if P_eq is not None and self.capacite_dynamique_C_N is not None:
            L10 = calcul_duree_vie_l10(self.capacite_dynamique_C_N, P_eq, self.type_roulement, self.exposant_p, clamp_non_negative=True)
            rep["duree_vie"]["L10_millions_tours"] = L10
            if rpm is not None and float(rpm) > 0:
                h = calcul_duree_vie_heures(L10, rpm, clamp_non_negative=True)
                rep["duree_vie"]["L10_heures"] = h
                if self.duree_vie_cible_heures is not None:
                    rep["duree_vie"]["ok_duree_vie"] = bool(h >= self.duree_vie_cible_heures)
        else:
            _push_inconnue(rep, "partielles", "L10_millions_tours", "Charge équivalente et C dynamique requises.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class _LocalBaladeur:
    moteur_thermique: Optional[Any] = None
    boite_crabots: Optional[Any] = None
    couple_max_Nm: Optional[float] = None
    diametre_primitif_cannelure_m: Optional[float] = None
    longueur_cannelure_m: Optional[float] = None
    nombre_dents_cannelure: Optional[int] = None
    epaisseur_dent_cannelure_m: Optional[float] = None
    hauteur_contact_cannelure_m: Optional[float] = None
    tau_admissible_cannelure_pa: Optional[float] = None
    pression_admissible_cannelure_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "baladeur", "entrees": {}, "cannelures": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm if self.couple_max_Nm is not None else _get(self.moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")
        if T is None:
            _push_inconnue(rep, "impossibles", "couple_max_Nm", "Requis pour évaluer les cannelures.")
        else:
            rep["entrees"]["couple_max_Nm"] = _require_positive("couple_max_Nm", T, strictly=False)
        vals = (self.diametre_primitif_cannelure_m, self.longueur_cannelure_m, self.nombre_dents_cannelure, self.epaisseur_dent_cannelure_m, self.hauteur_contact_cannelure_m)
        if T is not None and all(v is not None for v in vals):
            d, L, Z, e, h = float(vals[0]), float(vals[1]), int(vals[2]), float(vals[3]), float(vals[4])
            Ft = 2.0 * float(T) / d
            tau = Ft / (Z * L * e)
            p = Ft / (Z * L * h)
            rep["cannelures"].update({"contrainte_cisaillement_pa": tau, "pression_matage_pa": p})
            if self.tau_admissible_cannelure_pa is not None:
                rep["contraintes"]["ok_cisaillement"] = bool(tau <= self.tau_admissible_cannelure_pa)
            else:
                _push_inconnue(rep, "partielles", "tau_admissible_cannelure_pa", "Requis pour vérifier le cisaillement.")
            if self.pression_admissible_cannelure_pa is not None:
                rep["contraintes"]["ok_matage"] = bool(p <= self.pression_admissible_cannelure_pa)
            else:
                _push_inconnue(rep, "partielles", "pression_admissible_cannelure_pa", "Requis pour vérifier le matage.")
        else:
            _push_inconnue(rep, "partielles", "geometrie_cannelures", "Diamètre, longueur, nombre de dents, épaisseur et hauteur requis.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class _LocalFourchette:
    force_manoeuvre_N: Optional[float] = None
    masse_baladeur_kg: Optional[float] = None
    acceleration_engagement_m_s2: Optional[float] = None
    coefficient_frottement_cannelure: float = 0.1
    force_radiale_cannelure_N: Optional[float] = None
    longueur_bras_m: Optional[float] = None
    largeur_bras_m: Optional[float] = None
    epaisseur_bras_m: Optional[float] = None
    surface_contact_patins_m2: Optional[float] = None
    sigma_flexion_admissible_pa: Optional[float] = None
    pression_contact_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "fourchette", "entrees": {}, "efforts": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        F = self.force_manoeuvre_N
        if F is None:
            Fi = self.masse_baladeur_kg * self.acceleration_engagement_m_s2 if self.masse_baladeur_kg is not None and self.acceleration_engagement_m_s2 is not None else 0.0
            Ff = self.force_radiale_cannelure_N * self.coefficient_frottement_cannelure if self.force_radiale_cannelure_N is not None else 0.0
            if Fi or Ff:
                F = Fi + Ff
                rep["notes_modele"].append("Force de manœuvre estimée via inertie et frottement.")
            else:
                _push_inconnue(rep, "partielles", "force_manoeuvre_N", "Requise pour dimensionner la fourchette.")
        if F is not None:
            F = _require_positive("force_manoeuvre_N", F, strictly=False)
            rep["efforts"]["force_manoeuvre_N"] = F
            if self.longueur_bras_m is not None and self.largeur_bras_m is not None and self.epaisseur_bras_m is not None:
                M = (F / 2.0) * self.longueur_bras_m
                W = self.largeur_bras_m * self.epaisseur_bras_m ** 2 / 6.0
                sigma = M / W
                rep["contraintes"]["sigma_flexion_bras_pa"] = sigma
                if self.sigma_flexion_admissible_pa is not None:
                    rep["contraintes"]["ok_flexion"] = bool(sigma <= self.sigma_flexion_admissible_pa)
            else:
                _push_inconnue(rep, "partielles", "geometrie_bras", "longueur, largeur et épaisseur requises.")
            if self.surface_contact_patins_m2 is not None and self.surface_contact_patins_m2 > 0:
                p = F / self.surface_contact_patins_m2
                rep["contraintes"]["pression_contact_patins_pa"] = p
                if self.pression_contact_admissible_pa is not None:
                    rep["contraintes"]["ok_pression_contact"] = bool(p <= self.pression_contact_admissible_pa)
            else:
                _push_inconnue(rep, "partielles", "surface_contact_patins_m2", "Requise pour la pression patins/gorge.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class _LocalCarterBoite:
    roulements: Optional[List[Any]] = None
    longueur_interne_m: Optional[float] = None
    largeur_interne_m: Optional[float] = None
    hauteur_interne_m: Optional[float] = None
    epaisseur_paroi_m: Optional[float] = None
    densite_kg_m3: Optional[float] = None
    sigma_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"piece": "carter_boite", "efforts_supports": {}, "dimensionnements": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        Fr_tot = Fa_tot = 0.0
        found = False
        for r in list(self.roulements or []):
            rr = r
            if hasattr(r, "analyser"):
                try:
                    rr = r.analyser()
                except Exception:
                    rr = {}
            if isinstance(rr, dict):
                ent = rr.get("entrees", {}) if isinstance(rr.get("entrees", {}), dict) else {}
                Fr = _safe_float(ent.get("force_radiale_N"))
                Fa = _safe_float(ent.get("force_axiale_N"))
                if Fr is not None:
                    Fr_tot += abs(Fr); found = True
                if Fa is not None:
                    Fa_tot += abs(Fa); found = True
        if found:
            rep["efforts_supports"].update({"force_radiale_cumulee_N": Fr_tot, "force_axiale_cumulee_N": Fa_tot})
        else:
            _push_inconnue(rep, "partielles", "efforts_roulements", "Aucun effort de roulement trouvé pour le carter.")
        if all(v is not None for v in (self.longueur_interne_m, self.largeur_interne_m, self.hauteur_interne_m, self.epaisseur_paroi_m, self.densite_kg_m3)):
            L, W, H, e, rho = float(self.longueur_interne_m), float(self.largeur_interne_m), float(self.hauteur_interne_m), float(self.epaisseur_paroi_m), float(self.densite_kg_m3)
            Vmat = (L + 2*e) * (W + 2*e) * (H + 2*e) - L * W * H
            rep["dimensionnements"].update({"volume_matiere_m3": Vmat, "masse_estimee_kg": Vmat * rho})
        else:
            _push_inconnue(rep, "partielles", "masse_carter", "L, l, h internes, épaisseur et densité requis.")
        _dedup_inconnues(rep)
        return rep


if ArbreBoite is None:
    ArbreBoite = _LocalArbreBoite
if PieceCrabot is None:
    PieceCrabot = _LocalPieceCrabot
if PignonBoite is None:
    PignonBoite = _LocalPignonBoite
if RoulementBoite is None:
    RoulementBoite = _LocalRoulementBoite
if Baladeur is None:
    Baladeur = _LocalBaladeur
if Fourchette is None:
    Fourchette = _LocalFourchette
if CarterBoite is None:
    CarterBoite = _LocalCarterBoite

@dataclass(frozen=True)
class BoiteCrabots:
    """
    Composant d'analyse "boîte à crabots" visant à produire un maximum
    d'informations par calcul, et à laisser comme inconnues uniquement :
    - des données constructeur (roulement, matériaux, coefficients)
    - des données géométriques non fournies
    - des paramètres de montage/usage (temps d'engagement, inerties, etc.)

    + Intégration moteur -> boîte -> alternateur :
      - évalue des rapports de vitesse candidats,
      - calcule le point alternateur (Pdc demandée, vitesse),
      - déduit couple et puissance côté boîte (si rendement alternateur calculable),
      - sinon expose des bornes théoriques minimales (sans les confondre avec une valeur réelle),
      - passe le couple transmis dans les modules denture/crabot/roulements,
      - permet de choisir un rapport selon une stratégie (si les métriques existent).
    """

    # -------------------------
    # Géométrie engrenage
    # -------------------------
    diametre_primitif_m: Optional[float] = None  # d (m)
    largeur_denture_b_m: Optional[float] = None  # b (m)
    module_m: Optional[float] = None             # m (m) pour Lewis
    angle_pression_deg: float = 20.0
    angle_helice_deg: float = 0.0

    # Coefficients / facteurs (souvent inconnues constructeur)
    coefficient_zh: Optional[float] = None       # Z_H (Hertz)
    facteur_forme_y: Optional[float] = None      # Y (Lewis)

    # -------------------------
    # Crabot (géométrie + admissible)
    # -------------------------
    crabot_nombre_dents: Optional[int] = None
    crabot_hauteur_dent_m: Optional[float] = None
    crabot_largeur_dent_m: Optional[float] = None
    crabot_rayon_moyen_m: Optional[float] = None
    crabot_pression_admissible_pa: Optional[float] = None
    crabot_facteur_repartition: float = 1.0

    # -------------------------
    # Arbres (si tu veux calculer contraintes)
    # -------------------------
    diametre_arbre_m: Optional[float] = None

    # -------------------------
    # Roulements (si tu veux vie)
    # -------------------------
    roulement_C_N: Optional[float] = None
    roulement_X: Optional[float] = None
    roulement_Y: Optional[float] = None
    roulement_type: TypeRoulement = "bille"
    roulement_exposant_p: Optional[float] = None

    # -------------------------
    # Options
    # -------------------------
    clamp_non_negative: bool = True

    # -------------------------
    # Pièces (optionnel)
    # -------------------------
    piece_arbre: Optional[ArbreBoite] = None
    piece_crabot: Optional[PieceCrabot] = None
    piece_pignon: Optional[PignonBoite] = None
    piece_roulement: Optional[RoulementBoite] = None
    piece_baladeur: Optional[Baladeur] = None
    piece_fourchette: Optional[Fourchette] = None
    piece_carter: Optional[CarterBoite] = None

    # ------------------------------------------------------------
    # Analyse mécanique locale (inchangé)
    # ------------------------------------------------------------
    def analyser_point(
        self,
        *,
        couple_nm: float,
        vitesse_rotation_tr_min: Optional[float] = None,
        calcul_forces_engrenage_actif: bool = True,
        moment_flechissant_nm: Optional[float] = None,
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_axiale_N: Optional[float] = None,
        force_radiale_N: Optional[float] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "resultats": {},
            "contraintes": {},
            "roulements": {},
            "crabot": {},
            "choc_engagement": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        T = _require_finite("couple_nm", couple_nm)
        rapport["entrees"]["couple_nm"] = T
        rapport["entrees"]["vitesse_rotation_tr_min"] = vitesse_rotation_tr_min

        # ============================================================
        # 1) Forces d'engrenage (si d primitif connu)
        # ============================================================
        Ft: Optional[float] = None
        Fr: Optional[float] = None
        Fa: Optional[float] = None

        if calcul_forces_engrenage_actif:
            if self.diametre_primitif_m is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "force_tangentielle F_t",
                    "Calculable si diametre_primitif_m est fourni (F_t = 2*T/d).",
                )
            else:
                d = _require_positive("diametre_primitif_m", self.diametre_primitif_m, strictly=True)
                Ft = calcul_force_tangentielle(
                    couple_nm=T,
                    diametre_primitif_m=d,
                    use_abs_couple=True,
                    clamp_non_negative=self.clamp_non_negative,
                )
                forces = calcul_forces_engrenage(
                    force_tangentielle=Ft,
                    angle_pression_deg=self.angle_pression_deg,
                    angle_helice_deg=self.angle_helice_deg,
                    output="FT_FR_FA",
                    use_abs_force=True,
                    clamp_non_negative=False,
                )
                Fr = float(forces["F_r"])
                Fa = float(forces["F_a"])

        if force_radiale_N is not None:
            Fr = _require_finite("force_radiale_N", force_radiale_N)
        if force_axiale_N is not None:
            Fa = _require_finite("force_axiale_N", force_axiale_N)

        rapport["resultats"]["F_t_N"] = Ft
        rapport["resultats"]["F_r_N"] = Fr
        rapport["resultats"]["F_a_N"] = Fa

        # ============================================================
        # 2) Contraintes sur denture (Hertz + Lewis)
        # ============================================================
        sigma_H: Optional[float] = None
        if (
            Ft is not None
            and self.largeur_denture_b_m is not None
            and self.diametre_primitif_m is not None
            and self.coefficient_zh is not None
        ):
            sigma_H = calcul_contrainte_contact_hertz(
                force_tangentielle=Ft,
                largeur_denture_b=self.largeur_denture_b_m,
                diametre_primitif_moyen=self.diametre_primitif_m,
                coefficient_zh=self.coefficient_zh,
                use_abs_force=True,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contrainte_contact_hertz sigma_H",
                "Calculable si Ft, largeur_denture_b_m, diametre_primitif_m et coefficient_zh sont fournis.",
            )

        sigma_F: Optional[float] = None
        if (
            Ft is not None
            and self.largeur_denture_b_m is not None
            and self.module_m is not None
            and self.facteur_forme_y is not None
        ):
            sigma_F = calcul_contrainte_flexion_lewis(
                force_tangentielle=Ft,
                largeur_denture_b=self.largeur_denture_b_m,
                module_m=self.module_m,
                facteur_forme_y=self.facteur_forme_y,
                use_abs_force=True,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contrainte_flexion_lewis sigma_F",
                "Calculable si Ft, largeur_denture_b_m, module_m et facteur_forme_y sont fournis.",
            )

        rapport["contraintes"]["sigma_H_Pa"] = sigma_H
        rapport["contraintes"]["sigma_F_Pa"] = sigma_F

        # ============================================================
        # 3) Contraintes arbre (torsion, flexion, Von Mises)
        # ============================================================
        tau_torsion: Optional[float] = None
        sigma_flexion_arbre: Optional[float] = None
        sigma_vm: Optional[float] = None

        if self.diametre_arbre_m is not None:
            d_arbre = _require_positive("diametre_arbre_m", self.diametre_arbre_m, strictly=True)

            tau_torsion = calcul_contrainte_cisaillement_torsion(
                couple_nm=T,
                diametre_arbre_m=d_arbre,
                use_abs_couple=True,
                clamp_non_negative=True,
            )

            if moment_flechissant_nm is not None:
                M = _require_finite("moment_flechissant_nm", moment_flechissant_nm)
                sigma_flexion_arbre = calcul_contrainte_flexion_arbre(
                    moment_flechissant_nm=M,
                    diametre_arbre_m=d_arbre,
                    use_abs_moment=True,
                    clamp_non_negative=True,
                )
                sigma_vm = calcul_von_mises_arbre(
                    contrainte_flexion=sigma_flexion_arbre,
                    contrainte_cisaillement=tau_torsion,
                    mode="flexion+torsion",
                    clamp_non_negative=True,
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "contraintes flexion/Von Mises arbre",
                    "Flexion/Von Mises calculables si moment_flechissant_nm est fourni (ou calculé via géométrie/appuis).",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contraintes arbre",
                "Calculables si diametre_arbre_m est fourni (et moment_flechissant_nm pour flexion/Von Mises).",
            )

        rapport["contraintes"]["tau_torsion_Pa"] = tau_torsion
        rapport["contraintes"]["sigma_flexion_arbre_Pa"] = sigma_flexion_arbre
        rapport["contraintes"]["sigma_von_mises_Pa"] = sigma_vm

        # ============================================================
        # 4) Crabot : couple transmissible + pression contact
        # ============================================================
        T_cap_crabot: Optional[float] = None
        p_contact_crabot: Optional[float] = None

        if (
            self.crabot_nombre_dents is not None
            and self.crabot_pression_admissible_pa is not None
            and self.crabot_hauteur_dent_m is not None
            and self.crabot_largeur_dent_m is not None
            and self.crabot_rayon_moyen_m is not None
        ):
            T_cap_crabot = calcul_couple_transmissible_crabot(
                nombre_dents=self.crabot_nombre_dents,
                pression_admissible=self.crabot_pression_admissible_pa,
                hauteur_dent=self.crabot_hauteur_dent_m,
                largeur_dent=self.crabot_largeur_dent_m,
                rayon_moyen=self.crabot_rayon_moyen_m,
                facteur_repartition=self.crabot_facteur_repartition,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "couple transmissible crabot T_cap",
                "Calculable si (crabot_nombre_dents, crabot_pression_admissible_pa, crabot_hauteur_dent_m, crabot_largeur_dent_m, crabot_rayon_moyen_m) sont fournis.",
            )

        if (
            self.crabot_nombre_dents is not None
            and self.crabot_hauteur_dent_m is not None
            and self.crabot_largeur_dent_m is not None
            and self.crabot_rayon_moyen_m is not None
        ):
            p_contact_crabot = calcul_pression_contact_crabot(
                couple_nm=T,
                nombre_dents=self.crabot_nombre_dents,
                hauteur_dent=self.crabot_hauteur_dent_m,
                largeur_dent=self.crabot_largeur_dent_m,
                rayon_moyen=self.crabot_rayon_moyen_m,
                use_abs_couple=True,
                facteur_repartition=self.crabot_facteur_repartition,
                clamp_non_negative=True,
                return_details=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "pression contact crabot p",
                "Calculable si (crabot_nombre_dents, crabot_hauteur_dent_m, crabot_largeur_dent_m, crabot_rayon_moyen_m) sont fournis.",
            )

        rapport["crabot"]["T_cap_Nm"] = T_cap_crabot
        rapport["crabot"]["p_contact_Pa"] = p_contact_crabot
        if T_cap_crabot is not None:
            rapport["crabot"]["ok_couple"] = bool(abs(T) <= T_cap_crabot)

        # ============================================================
        # 5) Roulements : charge équivalente + durée de vie
        # ============================================================
        P_eq: Optional[float] = None
        if Fr is not None and Fa is not None and self.roulement_X is not None and self.roulement_Y is not None:
            P_eq = calcul_charge_equivalente_roulement(
                force_radiale=Fr,
                force_axiale=Fa,
                facteur_x=self.roulement_X,
                facteur_y=self.roulement_Y,
                use_abs_forces=True,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "charge équivalente roulement P",
                "Calculable si Fr, Fa et facteurs roulement_X/roulement_Y sont connus.",
            )

        L10_millions: Optional[float] = None
        L10_heures: Optional[float] = None
        if P_eq is not None and self.roulement_C_N is not None:
            L10_millions = calcul_duree_vie_l10(
                charge_dynamique_base_c=self.roulement_C_N,
                charge_equivalente_p=P_eq,
                type_roulement=self.roulement_type,
                exposant_p=self.roulement_exposant_p,
                clamp_non_negative=True,
            )
            if vitesse_rotation_tr_min is not None:
                L10_heures = calcul_duree_vie_heures(
                    l10_millions=L10_millions,
                    vitesse_rotation_tr_min=_require_positive("vitesse_rotation_tr_min", vitesse_rotation_tr_min, strictly=True),
                    clamp_non_negative=True,
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "durée de vie roulement (heures)",
                    "Conversion L10h calculable si vitesse_rotation_tr_min est fournie.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "durée de vie roulement (L10)",
                "Calculable si charge équivalente P_eq et capacité dynamique roulement_C_N sont connues.",
            )

        rapport["roulements"]["P_eq_N"] = P_eq
        rapport["roulements"]["L10_millions_tours"] = L10_millions
        rapport["roulements"]["L10_heures"] = L10_heures

        # ============================================================
        # 6) Choc d'engagement (inertie eq, énergie, couple sync)
        # ============================================================
        Jeq: Optional[float] = None
        E_choc: Optional[float] = None
        T_sync: Optional[float] = None

        if inertie_primaire_kg_m2 is not None and inertie_secondaire_kg_m2 is not None:
            J1 = _require_finite("inertie_primaire_kg_m2", inertie_primaire_kg_m2)
            J2 = _require_finite("inertie_secondaire_kg_m2", inertie_secondaire_kg_m2)
            Jeq = calcul_inertie_equivalente(
                inertie_primaire=J1,
                inertie_secondaire=J2,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "inertie équivalente J_eq",
                "Calculable si inertie_primaire_kg_m2 et inertie_secondaire_kg_m2 sont fournies.",
            )

        if Jeq is not None and delta_omega_rad_s is not None:
            d_omega = _require_finite("delta_omega_rad_s", delta_omega_rad_s)
            E_choc = calcul_energie_choc(
                inertie_eq=Jeq,
                delta_omega_rad_s=d_omega,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "énergie de choc ΔE",
                "Calculable si J_eq et delta_omega_rad_s sont fournis.",
            )

        if Jeq is not None and delta_omega_rad_s is not None and temps_engagement_s is not None:
            T_sync = calcul_couple_synchronisation_moyen(
                inertie_eq=Jeq,
                delta_omega_rad_s=_require_finite("delta_omega_rad_s", delta_omega_rad_s),
                temps_engagement_s=_require_positive("temps_engagement_s", temps_engagement_s, strictly=True),
                use_abs_delta_omega=True,
                clamp_non_negative=False,
            )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "couple de synchronisation moyen T_sync",
                "Calculable si J_eq, delta_omega_rad_s et temps_engagement_s sont fournis.",
            )

        rapport["choc_engagement"]["J_eq_kg_m2"] = Jeq
        rapport["choc_engagement"]["energie_choc_J"] = E_choc
        rapport["choc_engagement"]["couple_sync_moyen_Nm"] = T_sync

        # ============================================================
        # 7) Inconnues vraiment impossibles sans datasheet
        # ============================================================
        _push_inconnue(
            rapport,
            "impossibles",
            "coefficients matériau/qualité denture",
            "Z_H (contact Hertz), Y (Lewis), limites admissibles, facteurs dynamiques/fatigue nécessitent normes/datasheet ou calibration.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "géométrie complète + montage",
            "Sans entraxes, position des appuis, raideurs, alignements, on ne peut pas déduire les moments fléchissants et les répartitions réelles.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "données roulement constructeur",
            "C, facteurs X/Y (selon type, montage, Fa/Fr) proviennent des catalogues/abaques.",
        )

        # ============================================================
        # 8) Analyse des pièces (si définies)
        # ============================================================
        pieces_rapport = {}
        for nom, piece in [
            ("arbre", self.piece_arbre),
            ("crabot", self.piece_crabot),
            ("pignon", self.piece_pignon),
            ("roulement", self.piece_roulement),
            ("baladeur", self.piece_baladeur),
            ("fourchette", self.piece_fourchette),
            ("carter", self.piece_carter),
        ]:
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces_rapport[nom] = piece.analyser()
                except Exception as e:
                    pieces_rapport[nom] = {"erreur": str(e)}
        
        if pieces_rapport:
            rapport["pieces"] = pieces_rapport

        _dedup_inconnues(rapport)
        return rapport

    # ------------------------------------------------------------
    # Intégration : moteur -> boîte -> alternateur (sans invention)
    # ------------------------------------------------------------
    def analyser_chaine_moteur_alternateur(
        self,
        *,
        alternateur: Alternateur,
        puissance_bus_dc_w: float,
        rpm_moteur: float,
        rapports: List[float],
        rendement_boite: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Optional[Any] = None,
        moteur: Optional[Any] = None,
        strategie: StrategieOptimisation = "pareto",
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_radiale_N: Optional[float] = None,
        force_axiale_N: Optional[float] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "candidats": [],
            "selection": None,
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        Pdc = _require_positive("puissance_bus_dc_w", puissance_bus_dc_w, strictly=False)
        rpm_m = _require_positive("rpm_moteur", rpm_moteur, strictly=True)

        if not isinstance(rapports, list) or len(rapports) == 0:
            raise ValueError("rapports doit être une liste non vide de rapports (float).")

        eta_boite: Optional[float] = None
        if rendement_boite is not None:
            eta_boite = _require_positive("rendement_boite", rendement_boite, strictly=True)
            if eta_boite > 1.0:
                raise ValueError("rendement_boite doit être <= 1.0")

        Vbus = tension_bus_dc_v
        if Vbus is None and batterie is not None:
            Vbus = _safe_get_float(batterie, "tension_nominale_v")
            if Vbus is None:
                Vbus = _safe_get_float(batterie, "tension_bus_v")
            if Vbus is None:
                Vbus = _safe_get_float(batterie, "tension_v")

        if Vbus is None:
            _push_inconnue(
                rapport,
                "partielles",
                "tension_bus_dc_v",
                "Donne tension_bus_dc_v (ou un objet batterie avec tension_nominale_v/tension_bus_v) pour déduire le courant DC.",
            )

        rapport["entrees"].update(
            {
                "puissance_bus_dc_w": Pdc,
                "rpm_moteur": rpm_m,
                "omega_moteur_rad_s": _omega_from_rpm(rpm_m),
                "rendement_boite": eta_boite,
                "tension_bus_dc_v": Vbus,
                "strategie": strategie,
            }
        )

        for r in rapports:
            if not _is_finite(r) or float(r) <= 0.0:
                rapport["notes_modele"].append(f"Rapport ignoré (invalide): {r!r}")
                continue

            ratio = float(r)
            rpm_alt = rpm_m * ratio
            omega_alt = _omega_from_rpm(rpm_alt)

            cand: Dict[str, Any] = {
                "rapport": ratio,
                "rpm_alternateur": rpm_alt,
                "omega_alternateur_rad_s": omega_alt,
                "alternateur": None,
                "boite": None,
                "exigences": {},
            }

            alt_report: Optional[Dict[str, Any]] = None
            if alternateur is None:
                _push_inconnue(rapport, "impossibles", "alternateur", "Objet alternateur requis.")
            else:
                if hasattr(alternateur, "analyser_pour_bus_dc"):
                    alt_report = alternateur.analyser_pour_bus_dc(  # type: ignore[call-arg]
                        puissance_bus_dc_w=Pdc,
                        vitesse_rotation_rpm=rpm_alt,
                        tension_bus_dc_v=Vbus,
                        batterie=batterie,
                        moteur=moteur,
                    )
                else:
                    if Vbus is None:
                        _push_inconnue(
                            rapport,
                            "impossibles",
                            "analyse alternateur en DC",
                            "Sans tension DC (Vbus), impossible de déterminer le courant DC et donc P_out via V*I.",
                        )
                    else:
                        Ibus = Pdc / Vbus if abs(Vbus) > 1e-12 else float("inf")
                        alt_report = alternateur.analyser_point_de_fonctionnement(  # type: ignore[call-arg]
                            vitesse_rotation_rpm=rpm_alt,
                            mode_electrique="dc",
                            tension_v=Vbus,
                            courant_a=Ibus,
                        )

            cand["alternateur"] = alt_report

            # Extractions : P_out, eta_total, P_mec, T_mec, pertes
            # analyser_point_de_fonctionnement() -> clés au niveau racine
            # analyser_pour_bus_dc() -> sous-dict rep["alternateur"]
            P_out: Optional[float] = None
            eta_alt: Optional[float] = None
            P_mec_alt: Optional[float] = None
            T_mec_alt: Optional[float] = None
            P_pertes_alt: Optional[float] = None

            alt_core: Optional[Dict[str, Any]] = None
            if isinstance(alt_report, dict):
                if isinstance(alt_report.get("alternateur", None), dict):
                    alt_core = alt_report.get("alternateur", None)
                else:
                    alt_core = alt_report

            if isinstance(alt_core, dict):
                try:
                    P_out = alt_core.get("resultats", {}).get("P_out_W", None)
                    eta_alt = alt_core.get("resultats", {}).get("eta_total", None)
                    P_mec_alt = alt_core.get("resultats", {}).get("P_mecanique_W", None)
                    T_mec_alt = alt_core.get("resultats", {}).get("couple_mecanique_Nm", None)
                    P_pertes_alt = alt_core.get("pertes", {}).get("P_pertes_totales_W", None)
                except Exception:
                    pass

            # Bornes minimales théoriques (rendement = 100%)
            P_mec_min_theorique = Pdc
            T_alt_min_theorique = (Pdc / omega_alt) if abs(omega_alt) > 1e-12 else None

            cand["exigences"].update(
                {
                    "P_out_W": P_out,
                    "eta_alternateur": eta_alt,
                    "P_pertes_alternateur_W": P_pertes_alt,
                    "P_mecanique_alternateur_W": P_mec_alt,
                    "couple_alternateur_Nm": T_mec_alt,
                    "P_mec_min_theorique_W": P_mec_min_theorique,
                    "couple_alt_min_theorique_Nm": T_alt_min_theorique,
                }
            )

            def _remonte_couple(T_out: Optional[float]) -> Optional[float]:
                if T_out is None:
                    return None
                if eta_boite is None:
                    return T_out * ratio
                return (T_out * ratio) / eta_boite

            def _remonte_puissance(P_out_meca: Optional[float]) -> Optional[float]:
                if P_out_meca is None:
                    return None
                if eta_boite is None:
                    return P_out_meca
                return P_out_meca / eta_boite

            T_moteur_requis = _remonte_couple(T_mec_alt)
            P_moteur_requise = _remonte_puissance(P_mec_alt)

            T_moteur_min_theorique = _remonte_couple(T_alt_min_theorique) if T_alt_min_theorique is not None else None
            P_moteur_min_theorique = _remonte_puissance(P_mec_min_theorique)

            cand["exigences"].update(
                {
                    "couple_moteur_requis_Nm": T_moteur_requis,
                    "puissance_moteur_requise_W": P_moteur_requise,
                    "couple_moteur_min_theorique_Nm": T_moteur_min_theorique,
                    "puissance_moteur_min_theorique_W": P_moteur_min_theorique,
                }
            )

            couple_pour_dimensionnement = T_moteur_requis
            tag_couple = "reel"
            if couple_pour_dimensionnement is None:
                couple_pour_dimensionnement = T_moteur_min_theorique
                tag_couple = "borne_min_theorique"

            if couple_pour_dimensionnement is None:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "couple transmis",
                    "Impossible : ni couple alternateur calculé, ni borne théorique (omega_alt=0 ?).",
                )
                boite_report = None
            else:
                boite_report = self.analyser_point(
                    couple_nm=float(couple_pour_dimensionnement),
                    vitesse_rotation_tr_min=rpm_m,
                    inertie_primaire_kg_m2=inertie_primaire_kg_m2,
                    inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
                    delta_omega_rad_s=delta_omega_rad_s,
                    temps_engagement_s=temps_engagement_s,
                    force_radiale_N=force_radiale_N,
                    force_axiale_N=force_axiale_N,
                )
                boite_report.setdefault("notes_modele", [])
                boite_report["notes_modele"].append(f"Couple d'entrée utilisé: {tag_couple}")

            cand["boite"] = boite_report

            # Estimation conso : uniquement si le moteur fournit BSFC (g/kWh)
            bsfc_g_kwh = None
            if moteur is not None:
                bsfc_g_kwh = _safe_get_float(moteur, "bsfc_g_kwh")
                if bsfc_g_kwh is None:
                    bsfc_g_kwh = _safe_get_float(moteur, "consommation_specifique_g_kwh")

            if bsfc_g_kwh is not None:
                P_for_fuel = P_moteur_requise if P_moteur_requise is not None else P_moteur_min_theorique
                if P_for_fuel is not None:
                    fuel_g_h = bsfc_g_kwh * (float(P_for_fuel) / 1000.0)
                    cand["exigences"]["bsfc_g_kwh_utilisee"] = bsfc_g_kwh
                    cand["exigences"]["debit_carburant_g_h_estime"] = fuel_g_h
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "débit carburant",
                        "BSFC fournie, mais puissance moteur requise indéterminable (rendements manquants).",
                    )

            rapport["candidats"].append(cand)

        if len(rapport["candidats"]) == 0:
            _push_inconnue(
                rapport,
                "impossibles",
                "rapports",
                "Aucun rapport valide (>0) dans la liste fournie.",
            )
            _dedup_inconnues(rapport)
            return rapport

        def _metric(c: Dict[str, Any], key: str) -> Optional[float]:
            try:
                v = c.get("exigences", {}).get(key, None)
                if v is None:
                    return None
                f = float(v)
                return f if math.isfinite(f) else None
            except Exception:
                return None

        selection: Optional[Dict[str, Any]] = None

        if strategie in ("max_eta_alternateur", "min_pertes_alternateur", "min_couple_moteur"):
            scored: List[Tuple[float, Dict[str, Any]]] = []
            for c in rapport["candidats"]:
                if strategie == "max_eta_alternateur":
                    m = _metric(c, "eta_alternateur")
                    if m is not None:
                        scored.append((m, c))
                elif strategie == "min_pertes_alternateur":
                    m = _metric(c, "P_pertes_alternateur_W")
                    if m is not None:
                        scored.append((-m, c))  # minimisation
                else:
                    m = _metric(c, "couple_moteur_requis_Nm")
                    if m is None:
                        m = _metric(c, "couple_moteur_min_theorique_Nm")
                    if m is not None:
                        scored.append((-m, c))  # minimisation

            if len(scored) == 0:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "selection",
                    f"Impossible d'appliquer la stratégie {strategie}: métriques indisponibles (modèles/paramètres manquants).",
                )
            else:
                scored.sort(key=lambda t: t[0], reverse=True)
                selection = scored[0][1]

        elif strategie == "pareto":
            pts: List[Tuple[float, float, Dict[str, Any]]] = []
            for c in rapport["candidats"]:
                eta = _metric(c, "eta_alternateur")
                t = _metric(c, "couple_moteur_requis_Nm")
                if t is None:
                    t = _metric(c, "couple_moteur_min_theorique_Nm")
                if eta is not None and t is not None:
                    pts.append((eta, t, c))

            if len(pts) == 0:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "pareto",
                    "Impossible de calculer un Pareto (eta_alternateur et couple_moteur manquants).",
                )
            else:
                front: List[Dict[str, Any]] = []
                for i, (eta_i, t_i, c_i) in enumerate(pts):
                    dominated = False
                    for j, (eta_j, t_j, _c_j) in enumerate(pts):
                        if j == i:
                            continue
                        if (eta_j >= eta_i and t_j <= t_i) and (eta_j > eta_i or t_j < t_i):
                            dominated = True
                            break
                    if not dominated:
                        front.append(c_i)
                rapport["selection"] = {"pareto_front": front, "count": len(front)}
        else:
            raise ValueError("strategie invalide.")

        if selection is not None:
            rapport["selection"] = {
                "strategie": strategie,
                "rapport": selection.get("rapport"),
                "resume": selection.get("exigences", {}),
            }

        _dedup_inconnues(rapport)
        return rapport


# =============================================================================
# Méthodes d'orchestration ajoutées à BoiteCrabots
# =============================================================================

def _try_analyser_piece(piece: Any) -> Dict[str, Any]:
    if piece is None:
        return {"erreur": "piece absente"}
    fn = getattr(piece, "analyser", None)
    if not callable(fn):
        return {"type": type(piece).__name__, "erreur": "méthode analyser absente"}
    try:
        return fn(strict=False)
    except TypeError:
        try:
            return fn()
        except Exception as exc:
            return {"type": type(piece).__name__, "erreur": str(exc)}
    except Exception as exc:
        return {"type": type(piece).__name__, "erreur": str(exc)}


def _boite_analyser_pieces(
    self: "BoiteCrabots",
    *,
    moteur_thermique: Optional[Any] = None,
    couple_nm: Optional[float] = None,
    vitesse_rotation_tr_min: Optional[float] = None,
    moment_flechissant_nm: Optional[float] = None,
    inertie_primaire_kg_m2: Optional[float] = None,
    inertie_secondaire_kg_m2: Optional[float] = None,
    delta_omega_rad_s: Optional[float] = None,
    temps_engagement_s: Optional[float] = None,
    force_axiale_N: Optional[float] = None,
    force_radiale_N: Optional[float] = None,
    piece_kwargs: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Analyse les pièces de la boîte.
    Les pièces fournies dans la dataclass sont prioritaires ; sinon l'orchestrateur
    construit des pièces minimales avec les champs disponibles.
    """
    piece_kwargs = dict(piece_kwargs or {})
    rapport: Dict[str, Any] = {
        "pieces": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }

    T = couple_nm if couple_nm is not None else _get(moteur_thermique, "couple_max_Nm", "couple_nm", "couple_Nm")

    pignon = self.piece_pignon
    if pignon is None:
        kwargs = {
            "moteur_thermique": moteur_thermique,
            "boite_crabots": self,
            "couple_max_Nm": T,
            "diametre_primitif_m": self.diametre_primitif_m,
            "largeur_denture_b_m": self.largeur_denture_b_m,
            "module_m": self.module_m,
            "angle_pression_deg": self.angle_pression_deg,
            "angle_helice_deg": self.angle_helice_deg,
            "coefficient_zh": self.coefficient_zh,
            "facteur_forme_y": self.facteur_forme_y,
        }
        kwargs.update(piece_kwargs.get("pignon", {}))
        try:
            pignon = PignonBoite(**kwargs)
        except Exception as exc:
            pignon = None
            _push_inconnue(rapport, "impossibles", "construction pignon", str(exc))
    rapport["pieces"]["pignon"] = _try_analyser_piece(pignon)

    Fr = force_radiale_N
    Fa = force_axiale_N
    p_rep = rapport["pieces"].get("pignon", {})
    if isinstance(p_rep, dict):
        forces = p_rep.get("forces", {}) if isinstance(p_rep.get("forces", {}), dict) else {}
        Fr = Fr if Fr is not None else forces.get("F_radiale_N")
        Fa = Fa if Fa is not None else forces.get("F_axiale_N")

    arbre = self.piece_arbre
    if arbre is None:
        kwargs = {
            "moteur_thermique": moteur_thermique,
            "boite_crabots": self,
            "couple_max_Nm": T,
            "moment_flechissant_max_Nm": moment_flechissant_nm,
            "diametre_arbre_m": self.diametre_arbre_m,
        }
        kwargs.update(piece_kwargs.get("arbre", {}))
        try:
            arbre = ArbreBoite(**kwargs)
        except Exception as exc:
            arbre = None
            _push_inconnue(rapport, "impossibles", "construction arbre", str(exc))
    rapport["pieces"]["arbre"] = _try_analyser_piece(arbre)

    crabot = self.piece_crabot
    if crabot is None:
        kwargs = {
            "moteur_thermique": moteur_thermique,
            "boite_crabots": self,
            "couple_max_Nm": T,
            "delta_omega_rad_s": delta_omega_rad_s,
            "temps_engagement_s": temps_engagement_s,
            "inertie_primaire_kg_m2": inertie_primaire_kg_m2,
            "inertie_secondaire_kg_m2": inertie_secondaire_kg_m2,
            "nombre_dents": self.crabot_nombre_dents,
            "hauteur_dent_m": self.crabot_hauteur_dent_m,
            "largeur_dent_m": self.crabot_largeur_dent_m,
            "rayon_moyen_m": self.crabot_rayon_moyen_m,
            "facteur_repartition": self.crabot_facteur_repartition,
            "pression_admissible_pa": self.crabot_pression_admissible_pa,
        }
        kwargs.update(piece_kwargs.get("crabot", {}))
        try:
            crabot = PieceCrabot(**kwargs)
        except Exception as exc:
            crabot = None
            _push_inconnue(rapport, "impossibles", "construction crabot", str(exc))
    rapport["pieces"]["crabot"] = _try_analyser_piece(crabot)

    roulement = self.piece_roulement
    if roulement is None:
        kwargs = {
            "moteur_thermique": moteur_thermique,
            "boite_crabots": self,
            "pignon": pignon,
            "force_radiale_N": Fr,
            "force_axiale_N": Fa,
            "rpm": vitesse_rotation_tr_min,
            "capacite_dynamique_C_N": self.roulement_C_N,
            "facteur_X": self.roulement_X,
            "facteur_Y": self.roulement_Y,
            "type_roulement": self.roulement_type,
            "exposant_p": self.roulement_exposant_p,
        }
        kwargs.update(piece_kwargs.get("roulement", {}))
        try:
            roulement = RoulementBoite(**kwargs)
        except Exception as exc:
            roulement = None
            _push_inconnue(rapport, "impossibles", "construction roulement", str(exc))
    rapport["pieces"]["roulement"] = _try_analyser_piece(roulement)

    baladeur = self.piece_baladeur
    if baladeur is None:
        kwargs = {"moteur_thermique": moteur_thermique, "boite_crabots": self, "couple_max_Nm": T}
        kwargs.update(piece_kwargs.get("baladeur", {}))
        try:
            baladeur = Baladeur(**kwargs)
        except Exception as exc:
            baladeur = None
            _push_inconnue(rapport, "impossibles", "construction baladeur", str(exc))
    rapport["pieces"]["baladeur"] = _try_analyser_piece(baladeur)

    fourchette = self.piece_fourchette
    if fourchette is None:
        kwargs = dict(piece_kwargs.get("fourchette", {}))
        try:
            fourchette = Fourchette(**kwargs)
        except Exception as exc:
            fourchette = None
            _push_inconnue(rapport, "impossibles", "construction fourchette", str(exc))
    rapport["pieces"]["fourchette"] = _try_analyser_piece(fourchette)

    carter = self.piece_carter
    if carter is None:
        kwargs = {"roulements": [rapport["pieces"].get("roulement", {})]}
        kwargs.update(piece_kwargs.get("carter", {}))
        try:
            carter = CarterBoite(**kwargs)
        except Exception as exc:
            carter = None
            _push_inconnue(rapport, "impossibles", "construction carter", str(exc))
    rapport["pieces"]["carter"] = _try_analyser_piece(carter)

    for nom, rep in list(rapport["pieces"].items()):
        _merge_inconnues(rapport, rep if isinstance(rep, dict) else None, prefix=nom)
    _dedup_inconnues(rapport)
    return rapport


def _boite_analyser(
    self: "BoiteCrabots",
    *,
    couple_nm: Optional[float] = None,
    vitesse_rotation_tr_min: Optional[float] = None,
    calcul_forces_engrenage_actif: bool = True,
    moment_flechissant_nm: Optional[float] = None,
    inertie_primaire_kg_m2: Optional[float] = None,
    inertie_secondaire_kg_m2: Optional[float] = None,
    delta_omega_rad_s: Optional[float] = None,
    temps_engagement_s: Optional[float] = None,
    force_axiale_N: Optional[float] = None,
    force_radiale_N: Optional[float] = None,
    analyser_pieces: bool = True,
    piece_kwargs: Optional[Mapping[str, Mapping[str, Any]]] = None,
    # intégration alternateur optionnelle
    alternateur: Optional[Any] = None,
    puissance_bus_dc_w: Optional[float] = None,
    rpm_moteur: Optional[float] = None,
    rapports: Optional[Sequence[float]] = None,
    rendement_boite: Optional[float] = None,
    tension_bus_dc_v: Optional[float] = None,
    batterie: Optional[Any] = None,
    moteur: Optional[Any] = None,
    strategie: StrategieOptimisation = "pareto",
) -> Dict[str, Any]:
    rapport: Dict[str, Any] = {
        "composant": "boite_crabots",
        "entrees": {},
        "analyses": {},
        "synthese": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }

    if couple_nm is not None:
        point = self.analyser_point(
            couple_nm=couple_nm,
            vitesse_rotation_tr_min=vitesse_rotation_tr_min,
            calcul_forces_engrenage_actif=calcul_forces_engrenage_actif,
            moment_flechissant_nm=moment_flechissant_nm,
            inertie_primaire_kg_m2=inertie_primaire_kg_m2,
            inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
            delta_omega_rad_s=delta_omega_rad_s,
            temps_engagement_s=temps_engagement_s,
            force_axiale_N=force_axiale_N,
            force_radiale_N=force_radiale_N,
        )
        rapport["analyses"]["point"] = point
        _merge_inconnues(rapport, point, prefix="point")
        rapport["synthese"].update({
            "F_t_N": _get(point, "resultats") and point.get("resultats", {}).get("F_t_N"),
            "F_r_N": _get(point, "resultats") and point.get("resultats", {}).get("F_r_N"),
            "F_a_N": _get(point, "resultats") and point.get("resultats", {}).get("F_a_N"),
            "sigma_H_Pa": point.get("contraintes", {}).get("sigma_H_Pa"),
            "sigma_F_Pa": point.get("contraintes", {}).get("sigma_F_Pa"),
            "tau_torsion_Pa": point.get("contraintes", {}).get("tau_torsion_Pa"),
            "sigma_von_mises_Pa": point.get("contraintes", {}).get("sigma_von_mises_Pa"),
            "T_cap_crabot_Nm": point.get("crabot", {}).get("T_cap_Nm"),
            "P_eq_roulement_N": point.get("roulements", {}).get("P_eq_N"),
            "L10_roulement_h": point.get("roulements", {}).get("L10_heures"),
        })
    else:
        _push_inconnue(rapport, "partielles", "analyse_point", "Fournir couple_nm pour lancer l'analyse mécanique locale.")

    if alternateur is not None or puissance_bus_dc_w is not None or rpm_moteur is not None or rapports is not None:
        if alternateur is None or puissance_bus_dc_w is None or rpm_moteur is None or rapports is None:
            _push_inconnue(rapport, "impossibles", "chaine_moteur_alternateur", "alternateur, puissance_bus_dc_w, rpm_moteur et rapports sont requis ensemble.")
        else:
            chaine = self.analyser_chaine_moteur_alternateur(
                alternateur=alternateur,
                puissance_bus_dc_w=puissance_bus_dc_w,
                rpm_moteur=rpm_moteur,
                rapports=list(rapports),
                rendement_boite=rendement_boite,
                tension_bus_dc_v=tension_bus_dc_v,
                batterie=batterie,
                moteur=moteur,
                strategie=strategie,
                inertie_primaire_kg_m2=inertie_primaire_kg_m2,
                inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
                delta_omega_rad_s=delta_omega_rad_s,
                temps_engagement_s=temps_engagement_s,
                force_radiale_N=force_radiale_N,
                force_axiale_N=force_axiale_N,
            )
            rapport["analyses"]["chaine_moteur_alternateur"] = chaine
            _merge_inconnues(rapport, chaine, prefix="chaine")

    if analyser_pieces:
        pieces = self.analyser_pieces(
            moteur_thermique=moteur,
            couple_nm=couple_nm,
            vitesse_rotation_tr_min=vitesse_rotation_tr_min,
            moment_flechissant_nm=moment_flechissant_nm,
            inertie_primaire_kg_m2=inertie_primaire_kg_m2,
            inertie_secondaire_kg_m2=inertie_secondaire_kg_m2,
            delta_omega_rad_s=delta_omega_rad_s,
            temps_engagement_s=temps_engagement_s,
            force_axiale_N=force_axiale_N,
            force_radiale_N=force_radiale_N,
            piece_kwargs=piece_kwargs,
        )
        rapport["analyses"]["pieces"] = pieces
        _merge_inconnues(rapport, pieces, prefix="pieces")

    _dedup_inconnues(rapport)
    return rapport


BoiteCrabots.analyser_pieces = _boite_analyser_pieces  # type: ignore[attr-defined]
BoiteCrabots.analyser = _boite_analyser  # type: ignore[attr-defined]


# =============================================================================
# API haut niveau
# =============================================================================

def construire_boite_crabots(config: Mapping[str, Any]) -> BoiteCrabots:
    """Construit une BoiteCrabots depuis un dictionnaire en filtrant les clés acceptées."""
    cfg = dict(config or {})
    bloc = cfg.get("boite_crabots", cfg)
    if not isinstance(bloc, Mapping):
        raise ValueError("config['boite_crabots'] doit être un dictionnaire si fourni.")
    sig = inspect.signature(BoiteCrabots)
    kwargs = {k: v for k, v in dict(bloc).items() if k in sig.parameters}
    return BoiteCrabots(**kwargs)


def concevoir_boite_crabots(config: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Orchestrateur complet : construit la boîte puis lance l'analyse locale,
    l'analyse des pièces et, si les objets sont fournis, la chaîne moteur-alternateur.
    """
    cfg = dict(config or {})
    boite = cfg.get("instance")
    if boite is None:
        boite = construire_boite_crabots(cfg)
    if not isinstance(boite, BoiteCrabots):
        raise ValueError("config['instance'] doit être une BoiteCrabots si fourni.")

    analyse_cfg = cfg.get("analyse", cfg)
    if not isinstance(analyse_cfg, Mapping):
        raise ValueError("config['analyse'] doit être un dictionnaire si fourni.")

    accepted = set(inspect.signature(boite.analyser).parameters.keys())
    kwargs = {k: v for k, v in dict(analyse_cfg).items() if k in accepted}
    rapport = boite.analyser(**kwargs)
    rapport["objet"] = _to_jsonable(boite, max_depth=3)
    return rapport


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | Path) -> Path:
    """Exporte un rapport en JSON UTF-8 lisible."""
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


__all__ = [
    "BoiteCrabots",
    "construire_boite_crabots",
    "concevoir_boite_crabots",
    "exporter_rapport_json",
    "ArbreBoite",
    "PieceCrabot",
    "PignonBoite",
    "RoulementBoite",
    "Baladeur",
    "Fourchette",
    "CarterBoite",
]


if __name__ == "__main__":
    # Test minimal volontairement incomplet : doit produire un rapport avec inconnues, sans planter.
    exemple = {
        "boite_crabots": {
            "diametre_primitif_m": 0.08,
            "largeur_denture_b_m": 0.018,
            "module_m": 0.002,
            "diametre_arbre_m": 0.025,
            "crabot_nombre_dents": 6,
            "crabot_hauteur_dent_m": 0.006,
            "crabot_largeur_dent_m": 0.008,
            "crabot_rayon_moyen_m": 0.035,
        },
        "analyse": {
            "couple_nm": 120.0,
            "vitesse_rotation_tr_min": 3000.0,
            "moment_flechissant_nm": 35.0,
            "inertie_primaire_kg_m2": 0.015,
            "inertie_secondaire_kg_m2": 0.040,
            "delta_omega_rad_s": 120.0,
            "temps_engagement_s": 0.25,
        },
    }
    print(json.dumps(_to_jsonable(concevoir_boite_crabots(exemple)), ensure_ascii=False, indent=2)[:3000])
