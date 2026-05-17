# backend\components\boite_crabots\boite_crabots.py
from __future__ import annotations

"""
backend/components/boite_crabots.py
===============================================================================
Boîte à crabots — orchestration moteur thermique -> rapport -> alternateur.
===============================================================================

Rôle corrigé du composant :
- la boîte à crabots n'est pas seulement une réduction mécanique ;
- elle sélectionne un rapport pour maintenir le moteur thermique dans son cycle
  optimal ;
- elle adapte, généralement en multiplication, le régime transmis à l'alternateur ;
- elle permet à l'alternateur de fonctionner dans sa plage de meilleur rendement ;
- elle dimensionne ensuite les organes mécaniques sur le couple réellement transmis
  ou, si l'alternateur ne fournit pas encore son rendement, sur une borne minimale
  théorique explicitement marquée.

Unités : SI strictes sauf indication explicite : m, kg, s, N, Pa, W, tr/min, rad/s.
Principe : ne jamais inventer de matériau, cote catalogue, coefficient de norme ou
limite admissible. Les données absentes remontent dans `inconnues`.
"""

import inspect
import json
import math
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Mapping, Optional, Sequence, Tuple, List


# =============================================================================
# Types publics
# =============================================================================

TypeRoulement = Literal["bille", "rouleau"]
StrategieOptimisation = Literal[
    "maintien_cycle_moteur",
    "max_eta_alternateur",
    "min_pertes_alternateur",
    "min_couple_moteur",
    "pareto",
]


# =============================================================================
# Helpers robustesse
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _require_finite(name, x)
    ok = v > 0.0 if strictly else v >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _require_int_ge(name: str, x: Any, min_value: int = 1) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _safe_float(x: Any) -> Optional[float]:
    try:
        f = float(x)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _safe_get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        for n in names:
            if n in obj:
                return obj.get(n)
        return None
    for n in names:
        try:
            if hasattr(obj, n):
                return getattr(obj, n)
        except Exception:
            continue
    return None


def _safe_get_float(obj: Any, *names: str) -> Optional[float]:
    return _safe_float(_safe_get(obj, *names))


def _omega_from_rpm(rpm: float) -> float:
    return 2.0 * math.pi * _require_positive("rpm", rpm, strictly=True) / 60.0


def _rpm_from_omega(omega_rad_s: float) -> float:
    return _require_finite("omega_rad_s", omega_rad_s) * 60.0 / (2.0 * math.pi)


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": str(nom), "raison": str(raison)})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for categorie in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, str]] = []
        for item in list(inc.get(categorie, []) or []):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append({"nom": key[0], "raison": key[1]})
        inc[categorie] = out


def _merge_inconnues(dst: Dict[str, Any], src: Optional[Mapping[str, Any]], *, prefix: str) -> None:
    if not isinstance(src, Mapping):
        return
    inc = src.get("inconnues", {}) if isinstance(src.get("inconnues", {}), Mapping) else {}
    for categorie in ("impossibles", "partielles"):
        for item in list(inc.get(categorie, []) or []):
            if isinstance(item, Mapping):
                _push_inconnue(dst, categorie, f"{prefix} :: {item.get('nom', '')}", str(item.get("raison", "")))


def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 10) -> Any:
    if depth > max_depth:
        return {"type": type(value).__name__, "truncated": True}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v, depth=depth + 1, max_depth=max_depth) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v, depth=depth + 1, max_depth=max_depth) for v in value]
    if is_dataclass(value):
        try:
            return _to_jsonable(asdict(value), depth=depth + 1, max_depth=max_depth)
        except Exception:
            return {"type": type(value).__name__}
    if hasattr(value, "tolist"):
        try:
            return _to_jsonable(value.tolist(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _to_jsonable(value.item(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {"type": type(value).__name__, "attributs": _to_jsonable(vars(value), depth=depth + 1, max_depth=max_depth)}
        except Exception:
            pass
    return str(value)


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
# Modules de calcul intégrés — issus de tes modules spécialisés, sans dépendance externe
# =============================================================================

def calcul_force_tangentielle(
    couple_nm: float,
    diametre_primitif_m: float,
    *,
    use_abs_couple: bool = True,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
) -> float:
    T = _require_finite("couple_nm", couple_nm)
    d = _require_positive("diametre_primitif_m", diametre_primitif_m, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)
    if d <= eps:
        raise ValueError("diametre_primitif_m trop petit.")
    T_eff = abs(T) if use_abs_couple else T
    Ft = 2.0 * T_eff / d
    return max(0.0, Ft) if clamp_non_negative else Ft


def calcul_forces_engrenage(
    force_tangentielle: float,
    angle_pression_deg: float = 20.0,
    angle_helice_deg: float = 0.0,
    *,
    output: Literal["FR_FA", "FT_FR_FA"] = "FT_FR_FA",
    use_abs_force: bool = True,
    epsilon_cos: float = 1e-12,
    clamp_non_negative: bool = False,
) -> Dict[str, float]:
    Ft = _require_finite("force_tangentielle", force_tangentielle)
    if use_abs_force:
        Ft = abs(Ft)
    phi = math.radians(_require_finite("angle_pression_deg", angle_pression_deg))
    beta = math.radians(_require_finite("angle_helice_deg", angle_helice_deg))
    epsc = _require_positive("epsilon_cos", epsilon_cos, strictly=True)
    cos_beta = math.cos(beta)
    if abs(cos_beta) <= epsc:
        raise ValueError("angle_helice_deg trop proche de 90°.")
    Fr = Ft * math.tan(phi) / cos_beta
    Fa = Ft * math.tan(beta)
    if clamp_non_negative:
        Ft, Fr, Fa = max(0.0, Ft), max(0.0, Fr), max(0.0, Fa)
    if output == "FR_FA":
        return {"F_r": Fr, "F_a": Fa}
    return {"F_t": Ft, "F_r": Fr, "F_a": Fa}


def calcul_contrainte_contact_hertz(
    force_tangentielle: float,
    largeur_denture_b: float,
    diametre_primitif_moyen: float,
    coefficient_zh: float,
    *,
    use_abs_force: bool = True,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    Ft = _require_finite("force_tangentielle", force_tangentielle)
    b = _require_positive("largeur_denture_b", largeur_denture_b, strictly=True)
    dm = _require_positive("diametre_primitif_moyen", diametre_primitif_moyen, strictly=True)
    Zh = _require_positive("coefficient_zh", coefficient_zh, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)
    Ft_eff = abs(Ft) if use_abs_force else Ft
    denom = b * dm
    if denom <= eps:
        raise ValueError("b * d_m trop petit.")
    term = Ft_eff / denom
    if term < 0.0:
        raise ValueError("Terme sous racine négatif.")
    sigma = Zh * math.sqrt(term)
    if clamp_non_negative:
        sigma = max(0.0, sigma)
    if return_details:
        return {"sigma_H": sigma, "F_t_eff": Ft_eff, "b": b, "d_m": dm, "Z_H": Zh, "terme_sous_racine": term}
    return sigma


def calcul_contrainte_flexion_lewis(
    force_tangentielle: float,
    largeur_denture_b: float,
    module_m: float,
    facteur_forme_y: float,
    *,
    use_abs_force: bool = True,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    Ft = _require_finite("force_tangentielle", force_tangentielle)
    b = _require_positive("largeur_denture_b", largeur_denture_b, strictly=True)
    m = _require_positive("module_m", module_m, strictly=True)
    Y = _require_positive("facteur_forme_y", facteur_forme_y, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)
    Ft_eff = abs(Ft) if use_abs_force else Ft
    denom = b * m * Y
    if denom <= eps:
        raise ValueError("b * m * Y trop petit.")
    sigma = Ft_eff / denom
    if clamp_non_negative:
        sigma = max(0.0, sigma)
    if return_details:
        return {"sigma_F": sigma, "F_t_eff": Ft_eff, "b": b, "module_m": m, "Y": Y}
    return sigma


def calcul_contrainte_cisaillement_torsion(
    couple_nm: float,
    diametre_arbre_m: float,
    *,
    use_abs_couple: bool = True,
    clamp_non_negative: bool = True,
) -> float:
    T = _require_finite("couple_nm", couple_nm)
    d = _require_positive("diametre_arbre_m", diametre_arbre_m, strictly=True)
    T_eff = abs(T) if use_abs_couple else T
    tau = 16.0 * T_eff / (math.pi * d**3)
    return max(0.0, tau) if clamp_non_negative else tau


def calcul_contrainte_flexion_arbre(
    moment_flechissant_nm: float,
    diametre_arbre_m: float,
    *,
    use_abs_moment: bool = True,
    clamp_non_negative: bool = True,
) -> float:
    M = _require_finite("moment_flechissant_nm", moment_flechissant_nm)
    d = _require_positive("diametre_arbre_m", diametre_arbre_m, strictly=True)
    M_eff = abs(M) if use_abs_moment else M
    sigma = 32.0 * M_eff / (math.pi * d**3)
    return max(0.0, sigma) if clamp_non_negative else sigma


def calcul_von_mises_arbre(
    contrainte_flexion: float,
    contrainte_cisaillement: float,
    *,
    mode: Literal["flexion+torsion", "general"] = "flexion+torsion",
    clamp_non_negative: bool = True,
) -> float:
    sigma = _require_finite("contrainte_flexion", contrainte_flexion)
    tau = _require_finite("contrainte_cisaillement", contrainte_cisaillement)
    if mode not in ("flexion+torsion", "general"):
        raise ValueError("mode invalide.")
    vm = math.sqrt(sigma**2 + 3.0 * tau**2)
    return max(0.0, vm) if clamp_non_negative else vm


def calcul_coefficient_securite(contrainte_von_mises_pa: float, limite_elastique_pa: float) -> float:
    sigma = _require_positive("contrainte_von_mises_pa", contrainte_von_mises_pa, strictly=False)
    Re = _require_positive("limite_elastique_pa", limite_elastique_pa, strictly=True)
    return float("inf") if sigma == 0.0 else Re / sigma


def estimer_diametre_minimal_von_mises(
    couple_nm: float,
    moment_flechissant_nm: float,
    limite_elastique_pa: float,
    coefficient_securite_cible: float = 1.5,
) -> float:
    T = abs(_require_finite("couple_nm", couple_nm))
    M = abs(_require_finite("moment_flechissant_nm", moment_flechissant_nm))
    Re = _require_positive("limite_elastique_pa", limite_elastique_pa, strictly=True)
    S = _require_positive("coefficient_securite_cible", coefficient_securite_cible, strictly=True)
    charge = math.sqrt(4.0 * M**2 + 3.0 * T**2)
    d3 = 16.0 * S * charge / (math.pi * Re)
    return d3 ** (1.0 / 3.0)


def calcul_couple_transmissible_crabot(
    nombre_dents: int,
    pression_admissible: float,
    hauteur_dent: float,
    largeur_dent: float,
    rayon_moyen: float,
    *,
    facteur_repartition: float = 1.0,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    Nd = _require_int_ge("nombre_dents", nombre_dents, 1)
    p = _require_positive("pression_admissible", pression_admissible, strictly=False)
    h = _require_positive("hauteur_dent", hauteur_dent, strictly=False)
    b = _require_positive("largeur_dent", largeur_dent, strictly=False)
    r = _require_positive("rayon_moyen", rayon_moyen, strictly=True)
    k = _require_positive("facteur_repartition", facteur_repartition, strictly=False)
    Tcap = Nd * p * h * b * r * k
    if clamp_non_negative:
        Tcap = max(0.0, Tcap)
    if return_details:
        return {"T_cap": Tcap, "N_d": float(Nd), "p_adm": p, "aire_contact": h * b, "r_m": r, "facteur_repartition": k}
    return Tcap


def calcul_pression_contact_crabot(
    couple_nm: float,
    nombre_dents: int,
    hauteur_dent: float,
    largeur_dent: float,
    rayon_moyen: float,
    *,
    use_abs_couple: bool = True,
    facteur_repartition: float = 1.0,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    T = _require_finite("couple_nm", couple_nm)
    Nd = _require_int_ge("nombre_dents", nombre_dents, 1)
    h = _require_positive("hauteur_dent", hauteur_dent, strictly=False)
    b = _require_positive("largeur_dent", largeur_dent, strictly=False)
    r = _require_positive("rayon_moyen", rayon_moyen, strictly=True)
    k = _require_positive("facteur_repartition", facteur_repartition, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)
    T_eff = abs(T) if use_abs_couple else T
    area = h * b
    if area <= eps:
        raise ValueError("Aire de contact crabot trop faible.")
    Nd_eff = Nd * k
    force_dent = T_eff / (Nd_eff * r)
    pression = force_dent / area
    if clamp_non_negative:
        pression = max(0.0, pression)
    if return_details:
        return {"p_contact": pression, "T_eff": T_eff, "N_eff": Nd_eff, "force_par_dent": force_dent, "aire_contact": area, "r_m": r}
    return pression


def calcul_inertie_equivalente(
    inertie_primaire: float,
    inertie_secondaire: float,
    *,
    clamp_non_negative: bool = True,
    epsilon: float = 1e-12,
) -> float:
    J1 = _require_finite("inertie_primaire", inertie_primaire)
    J2 = _require_finite("inertie_secondaire", inertie_secondaire)
    den = J1 + J2
    if abs(den) <= epsilon:
        return 0.0
    Jeq = J1 * J2 / den
    return max(0.0, Jeq) if clamp_non_negative else Jeq


def calcul_energie_choc(inertie_eq: float, delta_omega_rad_s: float, *, clamp_non_negative: bool = True) -> float:
    J = _require_finite("inertie_eq", inertie_eq)
    dw = _require_finite("delta_omega_rad_s", delta_omega_rad_s)
    E = 0.5 * J * dw**2
    return max(0.0, E) if clamp_non_negative else E


def calcul_couple_synchronisation_moyen(
    inertie_eq: float,
    delta_omega_rad_s: float,
    temps_engagement_s: float,
    *,
    use_abs_delta_omega: bool = True,
    epsilon_t: float = 1e-12,
    clamp_non_negative: bool = False,
) -> float:
    J = _require_finite("inertie_eq", inertie_eq)
    dw = _require_finite("delta_omega_rad_s", delta_omega_rad_s)
    t = _require_finite("temps_engagement_s", temps_engagement_s)
    if t <= epsilon_t:
        raise ValueError("temps_engagement_s doit être > 0.")
    if use_abs_delta_omega:
        dw = abs(dw)
    T = J * dw / t
    return max(0.0, T) if clamp_non_negative else T


def calcul_charge_equivalente_roulement(
    force_radiale: float,
    force_axiale: float,
    facteur_x: float,
    facteur_y: float,
    *,
    use_abs_forces: bool = True,
    clamp_non_negative: bool = True,
) -> float:
    Fr = _require_finite("force_radiale", force_radiale)
    Fa = _require_finite("force_axiale", force_axiale)
    X = _require_finite("facteur_x", facteur_x)
    Y = _require_finite("facteur_y", facteur_y)
    if use_abs_forces:
        Fr, Fa = abs(Fr), abs(Fa)
    P = X * Fr + Y * Fa
    return max(0.0, P) if clamp_non_negative else P


def calcul_duree_vie_l10(
    charge_dynamique_base_c: float,
    charge_equivalente_p: float,
    type_roulement: str = "bille",
    *,
    exposant_p: Optional[float] = None,
    epsilon: float = 1e-12,
    clamp_non_negative: bool = True,
) -> float:
    C = _require_positive("charge_dynamique_base_c", charge_dynamique_base_c, strictly=True)
    P = _require_finite("charge_equivalente_p", charge_equivalente_p)
    eps = _require_positive("epsilon", epsilon, strictly=True)
    if exposant_p is not None:
        p = _require_positive("exposant_p", exposant_p, strictly=True)
    else:
        t = str(type_roulement or "").strip().lower()
        if t == "bille":
            p = 3.0
        elif t == "rouleau":
            p = 10.0 / 3.0
        else:
            raise ValueError("type_roulement inconnu.")
    if abs(P) <= eps:
        return float("inf")
    L10 = (C / abs(P)) ** p
    return max(0.0, L10) if clamp_non_negative else L10


def calcul_duree_vie_heures(
    l10_millions: float,
    vitesse_rotation_tr_min: float,
    *,
    clamp_non_negative: bool = True,
    epsilon_n: float = 1e-12,
) -> float:
    L10 = _require_finite("l10_millions", l10_millions)
    n = _require_finite("vitesse_rotation_tr_min", vitesse_rotation_tr_min)
    epsn = _require_positive("epsilon_n", epsilon_n, strictly=True)
    if math.isinf(L10):
        return float("inf")
    if n <= epsn:
        raise ValueError("vitesse_rotation_tr_min doit être > 0.")
    h = 1_000_000.0 * L10 / (60.0 * n)
    return max(0.0, h) if clamp_non_negative else h


# =============================================================================
# Pièces
# =============================================================================

@dataclass
class PignonBoite:
    couple_max_Nm: Optional[float] = None
    diametre_primitif_m: Optional[float] = None
    largeur_denture_b_m: Optional[float] = None
    module_m: Optional[float] = None
    angle_pression_deg: float = 20.0
    angle_helice_deg: float = 0.0
    coefficient_zh: Optional[float] = None
    facteur_forme_y: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep = {"piece": "pignon_boite", "entrees": {}, "forces": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm
        if T is not None:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            rep["entrees"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rep, "impossibles", "couple_max_Nm", "Requis pour calculer les efforts sur denture.")

        Ft = None
        if T is not None and self.diametre_primitif_m is not None:
            Ft = calcul_force_tangentielle(T, self.diametre_primitif_m)
            forces = calcul_forces_engrenage(Ft, self.angle_pression_deg, self.angle_helice_deg)
            rep["forces"].update({"F_tangentielle_N": Ft, "F_radiale_N": forces["F_r"], "F_axiale_N": forces["F_a"]})
        else:
            _push_inconnue(rep, "partielles", "diametre_primitif_m", "Requis pour F_t = 2T/d.")

        if Ft is not None and self.largeur_denture_b_m is not None and self.diametre_primitif_m is not None and self.coefficient_zh is not None:
            rep["contraintes"]["sigma_contact_hertz_pa"] = calcul_contrainte_contact_hertz(Ft, self.largeur_denture_b_m, self.diametre_primitif_m, self.coefficient_zh)
        else:
            _push_inconnue(rep, "partielles", "calcul_hertz", "Ft, largeur_denture_b_m, diametre_primitif_m et coefficient_zh requis.")

        if Ft is not None and self.largeur_denture_b_m is not None and self.module_m is not None and self.facteur_forme_y is not None:
            rep["contraintes"]["sigma_flexion_lewis_pa"] = calcul_contrainte_flexion_lewis(Ft, self.largeur_denture_b_m, self.module_m, self.facteur_forme_y)
        else:
            _push_inconnue(rep, "partielles", "calcul_lewis", "Ft, largeur_denture_b_m, module_m et facteur_forme_y requis.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class ArbreBoite:
    couple_max_Nm: Optional[float] = None
    moment_flechissant_max_Nm: Optional[float] = None
    diametre_arbre_m: Optional[float] = None
    tau_admissible_pa: Optional[float] = None
    sigma_admissible_pa: Optional[float] = None
    limite_elastique_pa: Optional[float] = None
    facteur_securite: float = 2.0

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep = {"piece": "arbre_boite", "entrees": {}, "dimensionnements": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm
        M = self.moment_flechissant_max_Nm
        tau_adm = self.tau_admissible_pa
        sig_adm = self.sigma_admissible_pa
        if tau_adm is None and self.limite_elastique_pa is not None:
            tau_adm = self.limite_elastique_pa / (max(self.facteur_securite, 1e-12) * math.sqrt(3.0))
            rep["notes_modele"].append("tau_admissible_pa déduit de limite_elastique_pa/(S*sqrt(3)).")
        if sig_adm is None and self.limite_elastique_pa is not None:
            sig_adm = self.limite_elastique_pa / max(self.facteur_securite, 1e-12)
            rep["notes_modele"].append("sigma_admissible_pa déduit de limite_elastique_pa/S.")
        rep["contraintes"].update({"tau_admissible_pa": tau_adm, "sigma_admissible_pa": sig_adm})
        d_candidates: List[float] = []
        if T is not None:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            rep["entrees"]["couple_max_Nm"] = T
            if tau_adm is not None and tau_adm > 0:
                d_t = (16.0 * T / (math.pi * tau_adm)) ** (1.0 / 3.0)
                rep["dimensionnements"]["d_min_torsion_m"] = d_t
                d_candidates.append(d_t)
            else:
                _push_inconnue(rep, "partielles", "tau_admissible_pa", "Requis pour calculer d_min_torsion_m.")
        else:
            _push_inconnue(rep, "impossibles", "couple_max_Nm", "Requis pour dimensionner l'arbre en torsion.")
        if M is not None:
            M = _require_positive("moment_flechissant_max_Nm", M, strictly=False)
            rep["entrees"]["moment_flechissant_max_Nm"] = M
            if sig_adm is not None and sig_adm > 0:
                d_f = (32.0 * M / (math.pi * sig_adm)) ** (1.0 / 3.0)
                rep["dimensionnements"]["d_min_flexion_m"] = d_f
                d_candidates.append(d_f)
            else:
                _push_inconnue(rep, "partielles", "sigma_admissible_pa", "Requis pour calculer d_min_flexion_m.")
        else:
            _push_inconnue(rep, "partielles", "moment_flechissant_max_Nm", "Utile pour la flexion et Von Mises.")

        d = self.diametre_arbre_m or (max(d_candidates) if d_candidates else None)
        if d is None:
            _push_inconnue(rep, "impossibles", "diametre_arbre_m", "Impossible de vérifier l'arbre sans diamètre ou contrainte admissible.")
        else:
            d = _require_positive("diametre_arbre_m", d, strictly=True)
            rep["dimensionnements"]["diametre_arbre_m"] = d
            tau = sigma = sigma_vm = None
            if T is not None:
                tau = calcul_contrainte_cisaillement_torsion(T, d)
                rep["contraintes"]["tau_torsion_reel_pa"] = tau
                if tau_adm is not None:
                    rep["contraintes"]["ok_torsion"] = bool(tau <= tau_adm)
            if M is not None:
                sigma = calcul_contrainte_flexion_arbre(M, d)
                rep["contraintes"]["sigma_flexion_reel_pa"] = sigma
                if sig_adm is not None:
                    rep["contraintes"]["ok_flexion"] = bool(sigma <= sig_adm)
            if sigma is not None and tau is not None:
                sigma_vm = calcul_von_mises_arbre(sigma, tau)
                rep["contraintes"]["sigma_von_mises_reel_pa"] = sigma_vm
                if self.limite_elastique_pa is not None:
                    rep["contraintes"]["coefficient_securite_von_mises"] = calcul_coefficient_securite(sigma_vm, self.limite_elastique_pa)
        _dedup_inconnues(rep)
        return rep


@dataclass
class Crabot:
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
        rep = {"piece": "crabot", "entrees": {}, "choc_engagement": {}, "dimensionnements": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm
        if T is not None:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            rep["entrees"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rep, "impossibles", "couple_max_Nm", "Requis pour valider le couple transmissible.")

        if self.inertie_primaire_kg_m2 is not None and self.inertie_secondaire_kg_m2 is not None:
            Jeq = calcul_inertie_equivalente(self.inertie_primaire_kg_m2, self.inertie_secondaire_kg_m2)
            rep["choc_engagement"]["inertie_equivalente_kg_m2"] = Jeq
            if self.delta_omega_rad_s is not None:
                rep["choc_engagement"]["energie_choc_J"] = calcul_energie_choc(Jeq, self.delta_omega_rad_s)
                if self.temps_engagement_s is not None:
                    rep["choc_engagement"]["couple_synchronisation_moyen_Nm"] = calcul_couple_synchronisation_moyen(Jeq, self.delta_omega_rad_s, self.temps_engagement_s, use_abs_delta_omega=True)
                else:
                    _push_inconnue(rep, "partielles", "temps_engagement_s", "Requis pour le couple de synchronisation.")
            else:
                _push_inconnue(rep, "partielles", "delta_omega_rad_s", "Requis pour l'énergie de choc.")
        else:
            _push_inconnue(rep, "partielles", "inerties", "inertie_primaire_kg_m2 et inertie_secondaire_kg_m2 requises pour le choc.")

        geo = self.nombre_dents is not None and self.hauteur_dent_m is not None and self.largeur_dent_m is not None and self.rayon_moyen_m is not None
        if geo:
            if self.pression_admissible_pa is not None:
                Tcap = calcul_couple_transmissible_crabot(
                    self.nombre_dents,
                    self.pression_admissible_pa,
                    self.hauteur_dent_m,
                    self.largeur_dent_m,
                    self.rayon_moyen_m,
                    facteur_repartition=self.facteur_repartition,
                )
                rep["dimensionnements"]["couple_transmissible_max_Nm"] = Tcap
                if T is not None:
                    rep["contraintes"]["ok_couple"] = bool(T <= Tcap)
            else:
                _push_inconnue(rep, "partielles", "pression_admissible_pa", "Requis pour calculer le couple transmissible max.")
            if T is not None:
                p_eff = calcul_pression_contact_crabot(
                    T,
                    self.nombre_dents,
                    self.hauteur_dent_m,
                    self.largeur_dent_m,
                    self.rayon_moyen_m,
                    facteur_repartition=self.facteur_repartition,
                )
                rep["contraintes"]["pression_contact_effective_pa"] = p_eff
                if self.pression_admissible_pa is not None:
                    rep["contraintes"]["ok_pression"] = bool(p_eff <= self.pression_admissible_pa)
        else:
            _push_inconnue(rep, "partielles", "geometrie_crabot", "nombre_dents, hauteur, largeur et rayon moyen requis.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class RoulementBoite:
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
        rep = {"piece": "roulement_boite", "entrees": {}, "duree_vie": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        Fr, Fa = self.force_radiale_N, self.force_axiale_N
        if Fr is not None:
            rep["entrees"]["force_radiale_N"] = _require_finite("force_radiale_N", Fr)
        else:
            _push_inconnue(rep, "impossibles", "force_radiale_N", "Requise pour la charge équivalente.")
        if Fa is not None:
            rep["entrees"]["force_axiale_N"] = _require_finite("force_axiale_N", Fa)
        else:
            _push_inconnue(rep, "partielles", "force_axiale_N", "Requise avec facteur_Y pour la charge équivalente.")
        if self.rpm is not None:
            rep["entrees"]["rpm"] = _require_positive("rpm", self.rpm, strictly=False)
        else:
            _push_inconnue(rep, "partielles", "rpm", "Requis pour convertir L10 en heures.")
        P_eq = None
        if Fr is not None and Fa is not None and self.facteur_X is not None and self.facteur_Y is not None:
            P_eq = calcul_charge_equivalente_roulement(Fr, Fa, self.facteur_X, self.facteur_Y)
            rep["duree_vie"]["charge_equivalente_P_N"] = P_eq
        else:
            _push_inconnue(rep, "partielles", "charge_equivalente", "Fr, Fa, facteur_X et facteur_Y requis.")
        if P_eq is not None and self.capacite_dynamique_C_N is not None:
            L10 = calcul_duree_vie_l10(self.capacite_dynamique_C_N, P_eq, self.type_roulement, exposant_p=self.exposant_p)
            rep["duree_vie"]["L10_millions_tours"] = L10
            if self.rpm is not None:
                h = calcul_duree_vie_heures(L10, self.rpm)
                rep["duree_vie"]["L10_heures"] = h
                if self.duree_vie_cible_heures is not None:
                    rep["duree_vie"]["ok_duree_vie"] = bool(h >= self.duree_vie_cible_heures)
        else:
            _push_inconnue(rep, "partielles", "L10_millions_tours", "Charge équivalente et capacité dynamique C requises.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class Baladeur:
    couple_max_Nm: Optional[float] = None
    diametre_primitif_cannelure_m: Optional[float] = None
    longueur_cannelure_m: Optional[float] = None
    nombre_dents_cannelure: Optional[int] = None
    epaisseur_dent_cannelure_m: Optional[float] = None
    hauteur_contact_cannelure_m: Optional[float] = None
    tau_admissible_cannelure_pa: Optional[float] = None
    pression_admissible_cannelure_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep = {"piece": "baladeur", "entrees": {}, "cannelures": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = self.couple_max_Nm
        if T is not None:
            T = _require_positive("couple_max_Nm", T, strictly=False)
            rep["entrees"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rep, "impossibles", "couple_max_Nm", "Requis pour évaluer les cannelures.")
        vals = (self.diametre_primitif_cannelure_m, self.longueur_cannelure_m, self.nombre_dents_cannelure, self.epaisseur_dent_cannelure_m, self.hauteur_contact_cannelure_m)
        if T is not None and all(v is not None for v in vals):
            d, L, Z, e, h = float(vals[0]), float(vals[1]), int(vals[2]), float(vals[3]), float(vals[4])
            Ft = 2.0 * T / d
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
            _push_inconnue(rep, "partielles", "geometrie_cannelures", "Diamètre, longueur, Z, épaisseur et hauteur requis.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class Fourchette:
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
        rep = {"piece": "fourchette", "entrees": {}, "efforts": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
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
                M = 0.5 * F * self.longueur_bras_m
                W = self.largeur_bras_m * self.epaisseur_bras_m**2 / 6.0
                sigma = M / W
                rep["contraintes"]["sigma_flexion_bras_pa"] = sigma
                if self.sigma_flexion_admissible_pa is not None:
                    rep["contraintes"]["ok_flexion"] = bool(sigma <= self.sigma_flexion_admissible_pa)
            else:
                _push_inconnue(rep, "partielles", "geometrie_bras", "Longueur, largeur et épaisseur requises.")
            if self.surface_contact_patins_m2 is not None and self.surface_contact_patins_m2 > 0:
                p = F / self.surface_contact_patins_m2
                rep["contraintes"]["pression_contact_patins_pa"] = p
                if self.pression_contact_admissible_pa is not None:
                    rep["contraintes"]["ok_pression_contact"] = bool(p <= self.pression_contact_admissible_pa)
            else:
                _push_inconnue(rep, "partielles", "surface_contact_patins_m2", "Requise pour vérifier le contact patin/gorge.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class CarterBoite:
    roulements: Optional[List[Any]] = None
    longueur_interne_m: Optional[float] = None
    largeur_interne_m: Optional[float] = None
    hauteur_interne_m: Optional[float] = None
    epaisseur_paroi_m: Optional[float] = None
    densite_kg_m3: Optional[float] = None
    sigma_admissible_pa: Optional[float] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rep = {"piece": "carter_boite", "efforts_supports": {}, "dimensionnements": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        Fr_tot = Fa_tot = 0.0
        found = False
        for r in list(self.roulements or []):
            rr = r.analyser(strict=False) if hasattr(r, "analyser") else r
            if isinstance(rr, Mapping):
                ent = rr.get("entrees", {}) if isinstance(rr.get("entrees"), Mapping) else {}
                Fr = _safe_float(ent.get("force_radiale_N"))
                Fa = _safe_float(ent.get("force_axiale_N"))
                if Fr is not None:
                    Fr_tot += abs(Fr); found = True
                if Fa is not None:
                    Fa_tot += abs(Fa); found = True
        if found:
            rep["efforts_supports"].update({"force_radiale_cumulee_N": Fr_tot, "force_axiale_cumulee_N": Fa_tot})
        else:
            _push_inconnue(rep, "partielles", "efforts_roulements", "Aucun effort de roulement exploitable trouvé.")
        if all(v is not None for v in (self.longueur_interne_m, self.largeur_interne_m, self.hauteur_interne_m, self.epaisseur_paroi_m, self.densite_kg_m3)):
            L, W, H, e, rho = float(self.longueur_interne_m), float(self.largeur_interne_m), float(self.hauteur_interne_m), float(self.epaisseur_paroi_m), float(self.densite_kg_m3)
            Vmat = (L + 2*e) * (W + 2*e) * (H + 2*e) - L * W * H
            rep["dimensionnements"].update({"volume_matiere_m3": Vmat, "masse_estimee_kg": Vmat * rho})
        else:
            _push_inconnue(rep, "partielles", "masse_carter", "L, l, h internes, épaisseur et densité requis.")
        _dedup_inconnues(rep)
        return rep


# =============================================================================
# Orchestrateur boîte à crabots
# =============================================================================

@dataclass(frozen=True)
class BoiteCrabots:
    # Géométrie engrenage
    diametre_primitif_m: Optional[float] = None
    largeur_denture_b_m: Optional[float] = None
    module_m: Optional[float] = None
    angle_pression_deg: float = 20.0
    angle_helice_deg: float = 0.0
    coefficient_zh: Optional[float] = None
    facteur_forme_y: Optional[float] = None

    # Crabot
    crabot_nombre_dents: Optional[int] = None
    crabot_hauteur_dent_m: Optional[float] = None
    crabot_largeur_dent_m: Optional[float] = None
    crabot_rayon_moyen_m: Optional[float] = None
    crabot_pression_admissible_pa: Optional[float] = None
    crabot_facteur_repartition: float = 1.0

    # Arbre
    diametre_arbre_m: Optional[float] = None
    limite_elastique_arbre_pa: Optional[float] = None
    facteur_securite_arbre: float = 2.0

    # Roulement
    roulement_C_N: Optional[float] = None
    roulement_X: Optional[float] = None
    roulement_Y: Optional[float] = None
    roulement_type: TypeRoulement = "bille"
    roulement_exposant_p: Optional[float] = None
    roulement_duree_vie_cible_h: Optional[float] = None

    # Fonctionnement système : moteur optimal -> alternateur
    rpm_moteur_optimal: Optional[float] = None
    rpm_moteur_min_optimal: Optional[float] = None
    rpm_moteur_max_optimal: Optional[float] = None
    couple_moteur_max_admissible_Nm: Optional[float] = None
    puissance_moteur_max_admissible_W: Optional[float] = None
    rpm_alternateur_cible: Optional[float] = None
    rpm_alternateur_min_optimal: Optional[float] = None
    rpm_alternateur_max_optimal: Optional[float] = None
    rapport_min: Optional[float] = None
    rapport_max: Optional[float] = None
    nb_rapports_auto: int = 9
    forcer_multiplication: bool = True
    rendement_boite_defaut: Optional[float] = None

    # Options
    clamp_non_negative: bool = True

    # Pièces optionnelles déjà construites
    piece_arbre: Optional[ArbreBoite] = None
    piece_crabot: Optional[Crabot] = None
    piece_pignon: Optional[PignonBoite] = None
    piece_roulement: Optional[RoulementBoite] = None
    piece_baladeur: Optional[Baladeur] = None
    piece_fourchette: Optional[Fourchette] = None
    piece_carter: Optional[CarterBoite] = None

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
        rep: Dict[str, Any] = {
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
        rep["entrees"].update({"couple_nm": T, "vitesse_rotation_tr_min": vitesse_rotation_tr_min})

        Ft = Fr = Fa = None
        if calcul_forces_engrenage_actif:
            if self.diametre_primitif_m is None:
                _push_inconnue(rep, "partielles", "force_tangentielle F_t", "Calculable si diametre_primitif_m est fourni.")
            else:
                Ft = calcul_force_tangentielle(T, self.diametre_primitif_m, clamp_non_negative=self.clamp_non_negative)
                forces = calcul_forces_engrenage(Ft, self.angle_pression_deg, self.angle_helice_deg, output="FT_FR_FA")
                Fr, Fa = float(forces["F_r"]), float(forces["F_a"])
        if force_radiale_N is not None:
            Fr = _require_finite("force_radiale_N", force_radiale_N)
        if force_axiale_N is not None:
            Fa = _require_finite("force_axiale_N", force_axiale_N)
        rep["resultats"].update({"F_t_N": Ft, "F_r_N": Fr, "F_a_N": Fa})

        if Ft is not None and self.largeur_denture_b_m is not None and self.diametre_primitif_m is not None and self.coefficient_zh is not None:
            rep["contraintes"]["sigma_H_Pa"] = calcul_contrainte_contact_hertz(Ft, self.largeur_denture_b_m, self.diametre_primitif_m, self.coefficient_zh)
        else:
            _push_inconnue(rep, "partielles", "contrainte_contact_hertz sigma_H", "Ft, largeur, diamètre primitif et Z_H requis.")
        if Ft is not None and self.largeur_denture_b_m is not None and self.module_m is not None and self.facteur_forme_y is not None:
            rep["contraintes"]["sigma_F_Pa"] = calcul_contrainte_flexion_lewis(Ft, self.largeur_denture_b_m, self.module_m, self.facteur_forme_y)
        else:
            _push_inconnue(rep, "partielles", "contrainte_flexion_lewis sigma_F", "Ft, largeur, module et facteur Y requis.")

        tau = sigma_b = sigma_vm = None
        if self.diametre_arbre_m is not None:
            tau = calcul_contrainte_cisaillement_torsion(T, self.diametre_arbre_m)
            rep["contraintes"]["tau_torsion_Pa"] = tau
            if moment_flechissant_nm is not None:
                sigma_b = calcul_contrainte_flexion_arbre(moment_flechissant_nm, self.diametre_arbre_m)
                sigma_vm = calcul_von_mises_arbre(sigma_b, tau)
                rep["contraintes"].update({"sigma_flexion_arbre_Pa": sigma_b, "sigma_von_mises_Pa": sigma_vm})
                if self.limite_elastique_arbre_pa is not None:
                    rep["contraintes"]["coefficient_securite_arbre"] = calcul_coefficient_securite(sigma_vm, self.limite_elastique_arbre_pa)
            else:
                _push_inconnue(rep, "partielles", "moment_flechissant_nm", "Requis pour la flexion/Von Mises arbre.")
        else:
            _push_inconnue(rep, "partielles", "diametre_arbre_m", "Requis pour contraintes d'arbre.")

        if self.crabot_nombre_dents is not None and self.crabot_hauteur_dent_m is not None and self.crabot_largeur_dent_m is not None and self.crabot_rayon_moyen_m is not None:
            p_contact = calcul_pression_contact_crabot(T, self.crabot_nombre_dents, self.crabot_hauteur_dent_m, self.crabot_largeur_dent_m, self.crabot_rayon_moyen_m, facteur_repartition=self.crabot_facteur_repartition)
            rep["crabot"]["p_contact_Pa"] = p_contact
            if self.crabot_pression_admissible_pa is not None:
                Tcap = calcul_couple_transmissible_crabot(self.crabot_nombre_dents, self.crabot_pression_admissible_pa, self.crabot_hauteur_dent_m, self.crabot_largeur_dent_m, self.crabot_rayon_moyen_m, facteur_repartition=self.crabot_facteur_repartition)
                rep["crabot"].update({"T_cap_Nm": Tcap, "ok_couple": bool(abs(T) <= Tcap), "ok_pression": bool(p_contact <= self.crabot_pression_admissible_pa)})
            else:
                _push_inconnue(rep, "partielles", "crabot_pression_admissible_pa", "Requis pour capacité de couple crabot.")
        else:
            _push_inconnue(rep, "partielles", "géométrie crabot", "nombre dents, hauteur, largeur et rayon moyen requis.")

        if Fr is not None and Fa is not None and self.roulement_X is not None and self.roulement_Y is not None:
            P_eq = calcul_charge_equivalente_roulement(Fr, Fa, self.roulement_X, self.roulement_Y)
            rep["roulements"]["P_eq_N"] = P_eq
            if self.roulement_C_N is not None:
                L10 = calcul_duree_vie_l10(self.roulement_C_N, P_eq, self.roulement_type, exposant_p=self.roulement_exposant_p)
                rep["roulements"]["L10_millions_tours"] = L10
                if vitesse_rotation_tr_min is not None:
                    L10h = calcul_duree_vie_heures(L10, vitesse_rotation_tr_min)
                    rep["roulements"]["L10_heures"] = L10h
                    if self.roulement_duree_vie_cible_h is not None:
                        rep["roulements"]["ok_duree_vie"] = bool(L10h >= self.roulement_duree_vie_cible_h)
                else:
                    _push_inconnue(rep, "partielles", "vitesse_rotation_tr_min", "Requise pour L10 en heures.")
            else:
                _push_inconnue(rep, "partielles", "roulement_C_N", "Requis pour L10.")
        else:
            _push_inconnue(rep, "partielles", "charge roulement", "Fr, Fa, roulement_X et roulement_Y requis.")

        if inertie_primaire_kg_m2 is not None and inertie_secondaire_kg_m2 is not None:
            Jeq = calcul_inertie_equivalente(inertie_primaire_kg_m2, inertie_secondaire_kg_m2)
            rep["choc_engagement"]["J_eq_kg_m2"] = Jeq
            if delta_omega_rad_s is not None:
                rep["choc_engagement"]["energie_choc_J"] = calcul_energie_choc(Jeq, delta_omega_rad_s)
                if temps_engagement_s is not None:
                    rep["choc_engagement"]["couple_sync_moyen_Nm"] = calcul_couple_synchronisation_moyen(Jeq, delta_omega_rad_s, temps_engagement_s)
                else:
                    _push_inconnue(rep, "partielles", "temps_engagement_s", "Requis pour couple de synchronisation.")
            else:
                _push_inconnue(rep, "partielles", "delta_omega_rad_s", "Requis pour énergie de choc.")
        else:
            _push_inconnue(rep, "partielles", "inerties engagement", "Inerties primaire/secondaire requises pour choc.")

        _push_inconnue(rep, "impossibles", "coefficients matériau/qualité denture", "Z_H, Y, limites admissibles et facteurs fatigue proviennent des normes/datasheets.")
        _push_inconnue(rep, "impossibles", "géométrie complète + montage", "Entraxes, appuis, raideurs, alignements et moments réels exigent la CAO/montage détaillé.")
        _dedup_inconnues(rep)
        return rep

    @staticmethod
    def _score_cible_ou_plage(
        valeur: Optional[float],
        *,
        cible: Optional[float] = None,
        mini: Optional[float] = None,
        maxi: Optional[float] = None,
        nom: str = "valeur",
    ) -> Tuple[Optional[float], List[str]]:
        if valeur is None:
            return None, [f"{nom}: valeur absente"]
        x = _require_finite(nom, valeur)
        scores: List[float] = []
        notes: List[str] = []
        if cible is not None:
            c = _require_positive(f"{nom}_cible", cible, strictly=True)
            scores.append(abs(x - c) / c)
        if mini is not None or maxi is not None:
            lo = _require_positive(f"{nom}_min", mini, strictly=False) if mini is not None else -float("inf")
            hi = _require_positive(f"{nom}_max", maxi, strictly=True) if maxi is not None else float("inf")
            if lo > hi:
                raise ValueError(f"Plage invalide pour {nom}.")
            if x < lo:
                scores.append((lo - x) / max(abs(lo), 1e-12)); notes.append(f"{nom}: sous plage optimale")
            elif x > hi:
                scores.append((x - hi) / max(abs(hi), 1e-12)); notes.append(f"{nom}: au-dessus plage optimale")
            else:
                scores.append(0.0)
        if not scores:
            return None, []
        return float(max(scores)), notes

    @staticmethod
    def _extraire_metrics_alternateur(alt_report: Optional[Mapping[str, Any]]) -> Dict[str, Optional[float]]:
        metrics = {"P_out_W": None, "eta_total": None, "P_mecanique_W": None, "couple_mecanique_Nm": None, "P_pertes_totales_W": None}
        if not isinstance(alt_report, Mapping):
            return metrics
        core = alt_report.get("alternateur") if isinstance(alt_report.get("alternateur"), Mapping) else alt_report
        pools: List[Mapping[str, Any]] = [core]
        for k in ("resultats", "pertes", "sorties"):
            if isinstance(core.get(k), Mapping):
                pools.append(core[k])
        aliases = {
            "P_out_W": ("P_out_W", "puissance_sortie_w", "puissance_bus_dc_w"),
            "eta_total": ("eta_total", "rendement", "rendement_total", "eta"),
            "P_mecanique_W": ("P_mecanique_W", "puissance_mecanique_w", "P_in_meca_W"),
            "couple_mecanique_Nm": ("couple_mecanique_Nm", "couple_nm", "couple_Nm"),
            "P_pertes_totales_W": ("P_pertes_totales_W", "pertes_totales_w", "P_pertes_W"),
        }
        for key, names in aliases.items():
            for pool in pools:
                for n in names:
                    v = _safe_float(pool.get(n))
                    if v is not None:
                        metrics[key] = v
                        break
                if metrics[key] is not None:
                    break
        return metrics

    def generer_rapports_cycle_optimal(
        self,
        *,
        rpm_moteur: float,
        rapports: Optional[Sequence[float]] = None,
        rpm_alternateur_cible: Optional[float] = None,
        rpm_alternateur_min_optimal: Optional[float] = None,
        rpm_alternateur_max_optimal: Optional[float] = None,
        rapport_min: Optional[float] = None,
        rapport_max: Optional[float] = None,
        nb_rapports_auto: Optional[int] = None,
        forcer_multiplication: Optional[bool] = None,
    ) -> List[float]:
        rpm_m = _require_positive("rpm_moteur", rpm_moteur, strictly=True)
        rmin = self.rapport_min if rapport_min is None else rapport_min
        rmax = self.rapport_max if rapport_max is None else rapport_max
        n_auto = self.nb_rapports_auto if nb_rapports_auto is None else int(nb_rapports_auto)
        mult = self.forcer_multiplication if forcer_multiplication is None else bool(forcer_multiplication)
        vals: List[float] = []
        if rapports:
            for r in rapports:
                rf = _safe_float(r)
                if rf is not None and rf > 0:
                    vals.append(rf)
        else:
            target = rpm_alternateur_cible if rpm_alternateur_cible is not None else self.rpm_alternateur_cible
            lo_alt = rpm_alternateur_min_optimal if rpm_alternateur_min_optimal is not None else self.rpm_alternateur_min_optimal
            hi_alt = rpm_alternateur_max_optimal if rpm_alternateur_max_optimal is not None else self.rpm_alternateur_max_optimal
            if target is not None:
                vals.append(_require_positive("rpm_alternateur_cible", target, strictly=True) / rpm_m)
            if lo_alt is not None and hi_alt is not None:
                lo = _require_positive("rpm_alternateur_min_optimal", lo_alt, strictly=True) / rpm_m
                hi = _require_positive("rpm_alternateur_max_optimal", hi_alt, strictly=True) / rpm_m
                if lo > hi:
                    lo, hi = hi, lo
                n = max(2, n_auto)
                for i in range(n):
                    t = i / max(1, n - 1)
                    vals.append(lo + t * (hi - lo))
            elif lo_alt is not None:
                vals.append(_require_positive("rpm_alternateur_min_optimal", lo_alt, strictly=True) / rpm_m)
            elif hi_alt is not None:
                vals.append(_require_positive("rpm_alternateur_max_optimal", hi_alt, strictly=True) / rpm_m)
            if not vals:
                vals = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
        lo_r = _require_positive("rapport_min", rmin, strictly=True) if rmin is not None else (1.0 if mult else 1e-9)
        hi_r = _require_positive("rapport_max", rmax, strictly=True) if rmax is not None else float("inf")
        out: List[float] = []
        for r in vals:
            if not math.isfinite(r) or r <= 0:
                continue
            if r < lo_r or r > hi_r:
                continue
            if mult and r < 1.0:
                continue
            if not any(abs(r - x) <= 1e-9 for x in out):
                out.append(float(r))
        return sorted(out)

    def analyser_chaine_moteur_alternateur(
        self,
        *,
        alternateur: Optional[Any] = None,
        puissance_bus_dc_w: float,
        rpm_moteur: Optional[float] = None,
        rapports: Optional[Sequence[float]] = None,
        rendement_boite: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Optional[Any] = None,
        moteur: Optional[Any] = None,
        strategie: StrategieOptimisation = "maintien_cycle_moteur",
        rpm_moteur_optimal: Optional[float] = None,
        rpm_moteur_min_optimal: Optional[float] = None,
        rpm_moteur_max_optimal: Optional[float] = None,
        couple_moteur_max_admissible_Nm: Optional[float] = None,
        puissance_moteur_max_admissible_W: Optional[float] = None,
        rpm_alternateur_cible: Optional[float] = None,
        rpm_alternateur_min_optimal: Optional[float] = None,
        rpm_alternateur_max_optimal: Optional[float] = None,
        rapport_min: Optional[float] = None,
        rapport_max: Optional[float] = None,
        nb_rapports_auto: Optional[int] = None,
        forcer_multiplication: Optional[bool] = None,
        inertie_primaire_kg_m2: Optional[float] = None,
        inertie_secondaire_kg_m2: Optional[float] = None,
        delta_omega_rad_s: Optional[float] = None,
        temps_engagement_s: Optional[float] = None,
        force_radiale_N: Optional[float] = None,
        force_axiale_N: Optional[float] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "role_fonctionnel": {
                "boite_crabots": "sélecteur de rapport pour maintenir le moteur thermique dans son cycle optimal et placer l'alternateur dans sa plage utile",
                "effet_recherche": "multiplication contrôlée du régime alternateur lorsque rapport > 1",
            },
            "entrees": {}, "rapports_generes": [], "candidats": [], "selection": None,
            "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": [],
        }
        Pdc = _require_positive("puissance_bus_dc_w", puissance_bus_dc_w, strictly=False)
        rpm_obj = None
        if moteur is not None:
            rpm_obj = _safe_get_float(moteur, "rpm_moteur_optimal", "regime_optimal_rpm", "rpm_optimal", "regime_rpm", "rpm")
        rpm_opt = rpm_moteur_optimal if rpm_moteur_optimal is not None else self.rpm_moteur_optimal
        rpm_m = rpm_opt if rpm_opt is not None else (rpm_moteur if rpm_moteur is not None else rpm_obj)
        if rpm_m is None:
            _push_inconnue(rapport, "impossibles", "rpm_moteur/rpm_moteur_optimal", "Requis pour calculer le rapport vers l'alternateur.")
            _dedup_inconnues(rapport); return rapport
        rpm_m = _require_positive("rpm_moteur", rpm_m, strictly=True)

        rpm_m_min = rpm_moteur_min_optimal if rpm_moteur_min_optimal is not None else self.rpm_moteur_min_optimal
        rpm_m_max = rpm_moteur_max_optimal if rpm_moteur_max_optimal is not None else self.rpm_moteur_max_optimal
        rpm_alt_c = rpm_alternateur_cible if rpm_alternateur_cible is not None else self.rpm_alternateur_cible
        rpm_alt_min = rpm_alternateur_min_optimal if rpm_alternateur_min_optimal is not None else self.rpm_alternateur_min_optimal
        rpm_alt_max = rpm_alternateur_max_optimal if rpm_alternateur_max_optimal is not None else self.rpm_alternateur_max_optimal
        eta_b = rendement_boite if rendement_boite is not None else self.rendement_boite_defaut
        if eta_b is not None:
            eta_b = _require_positive("rendement_boite", eta_b, strictly=True)
            if eta_b > 1.0:
                raise ValueError("rendement_boite doit être <= 1.")
        else:
            _push_inconnue(rapport, "partielles", "rendement_boite", "Sans rendement, le couple moteur requis est sans pertes de boîte.")
        Vbus = tension_bus_dc_v
        if Vbus is None and batterie is not None:
            Vbus = _safe_get_float(batterie, "tension_nominale_v", "tension_bus_v", "tension_v")
        if Vbus is None:
            _push_inconnue(rapport, "partielles", "tension_bus_dc_v", "Utile pour appeler l'alternateur en mode DC.")

        ratios = self.generer_rapports_cycle_optimal(
            rpm_moteur=rpm_m,
            rapports=rapports,
            rpm_alternateur_cible=rpm_alt_c,
            rpm_alternateur_min_optimal=rpm_alt_min,
            rpm_alternateur_max_optimal=rpm_alt_max,
            rapport_min=rapport_min,
            rapport_max=rapport_max,
            nb_rapports_auto=nb_rapports_auto,
            forcer_multiplication=forcer_multiplication,
        )
        rapport["rapports_generes"] = ratios
        rapport["entrees"].update({
            "puissance_bus_dc_w": Pdc, "rpm_moteur_utilise": rpm_m,
            "rpm_moteur_optimal": rpm_opt, "rpm_moteur_min_optimal": rpm_m_min, "rpm_moteur_max_optimal": rpm_m_max,
            "rpm_alternateur_cible": rpm_alt_c, "rpm_alternateur_min_optimal": rpm_alt_min, "rpm_alternateur_max_optimal": rpm_alt_max,
            "rendement_boite": eta_b, "tension_bus_dc_v": Vbus, "strategie": strategie,
        })
        if not ratios:
            _push_inconnue(rapport, "impossibles", "rapports", "Aucun rapport valide généré.")
            _dedup_inconnues(rapport); return rapport

        omega_m = _omega_from_rpm(rpm_m)
        for ratio in ratios:
            rpm_alt = rpm_m * ratio
            omega_alt = _omega_from_rpm(rpm_alt)
            cand: Dict[str, Any] = {"rapport": ratio, "type_rapport": "multiplicateur" if ratio > 1 else ("direct" if abs(ratio-1) < 1e-12 else "reducteur"), "rpm_moteur": rpm_m, "rpm_alternateur": rpm_alt, "alternateur": None, "boite": None, "exigences": {}, "scores": {}, "notes": []}

            alt_report = None
            if alternateur is not None:
                try:
                    if hasattr(alternateur, "analyser_pour_bus_dc"):
                        alt_report = _call_with_supported_kwargs(alternateur.analyser_pour_bus_dc, {"puissance_bus_dc_w": Pdc, "vitesse_rotation_rpm": rpm_alt, "tension_bus_dc_v": Vbus, "batterie": batterie, "moteur": moteur})
                    elif hasattr(alternateur, "analyser_point_de_fonctionnement"):
                        if Vbus is None or abs(float(Vbus)) <= 1e-12:
                            _push_inconnue(rapport, "impossibles", "analyse alternateur DC", "Fournir tension_bus_dc_v.")
                        else:
                            alt_report = _call_with_supported_kwargs(alternateur.analyser_point_de_fonctionnement, {"vitesse_rotation_rpm": rpm_alt, "mode_electrique": "dc", "tension_v": Vbus, "courant_a": Pdc / float(Vbus)})
                    else:
                        _push_inconnue(rapport, "partielles", "API alternateur", "analyser_pour_bus_dc ou analyser_point_de_fonctionnement absent.")
                except Exception as exc:
                    cand["notes"].append(f"Analyse alternateur échouée: {exc}")
            else:
                _push_inconnue(rapport, "partielles", "alternateur", "Alternateur absent : calcul des bornes minimales seulement.")
            cand["alternateur"] = alt_report
            metrics = self._extraire_metrics_alternateur(alt_report)

            P_out = metrics["P_out_W"]
            eta_alt = metrics["eta_total"]
            P_mec_alt = metrics["P_mecanique_W"]
            T_alt = metrics["couple_mecanique_Nm"]
            P_pertes = metrics["P_pertes_totales_W"]
            P_mec_min = Pdc
            T_alt_min = P_mec_min / omega_alt if abs(omega_alt) > 1e-12 else None
            if P_mec_alt is None and eta_alt is not None and eta_alt > 0:
                P_mec_alt = Pdc / eta_alt
            if T_alt is None and P_mec_alt is not None:
                T_alt = P_mec_alt / omega_alt

            def remonte_p(P: Optional[float]) -> Optional[float]:
                if P is None: return None
                return P / eta_b if eta_b is not None else P
            def remonte_t(Ta: Optional[float]) -> Optional[float]:
                if Ta is None: return None
                return Ta * ratio / eta_b if eta_b is not None else Ta * ratio

            P_mot = remonte_p(P_mec_alt)
            T_mot = remonte_t(T_alt)
            P_mot_min = remonte_p(P_mec_min)
            T_mot_min = remonte_t(T_alt_min)
            couple_dim = T_mot if T_mot is not None else T_mot_min

            cand["exigences"].update({
                "P_out_W": P_out, "eta_alternateur": eta_alt, "P_pertes_alternateur_W": P_pertes,
                "P_mecanique_alternateur_W": P_mec_alt, "couple_alternateur_Nm": T_alt,
                "P_mec_min_theorique_W": P_mec_min, "couple_alt_min_theorique_Nm": T_alt_min,
                "puissance_moteur_requise_W": P_mot, "couple_moteur_requis_Nm": T_mot,
                "puissance_moteur_min_theorique_W": P_mot_min, "couple_moteur_min_theorique_Nm": T_mot_min,
                "couple_utilise_dimensionnement_Nm": couple_dim,
                "couple_dimensionnement_type": "reel_ou_eta" if T_mot is not None else "borne_min_theorique",
            })
            cmax = couple_moteur_max_admissible_Nm if couple_moteur_max_admissible_Nm is not None else self.couple_moteur_max_admissible_Nm
            pmax = puissance_moteur_max_admissible_W if puissance_moteur_max_admissible_W is not None else self.puissance_moteur_max_admissible_W
            if cmax is not None and couple_dim is not None:
                cand["exigences"]["ok_couple_moteur"] = bool(abs(couple_dim) <= cmax)
            pcheck = P_mot if P_mot is not None else P_mot_min
            if pmax is not None and pcheck is not None:
                cand["exigences"]["ok_puissance_moteur"] = bool(pcheck <= pmax)

            if couple_dim is not None:
                boite = self.analyser_point(couple_nm=float(couple_dim), vitesse_rotation_tr_min=rpm_m, inertie_primaire_kg_m2=inertie_primaire_kg_m2, inertie_secondaire_kg_m2=inertie_secondaire_kg_m2, delta_omega_rad_s=delta_omega_rad_s, temps_engagement_s=temps_engagement_s, force_radiale_N=force_radiale_N, force_axiale_N=force_axiale_N)
                boite.setdefault("notes_modele", []).append(cand["exigences"]["couple_dimensionnement_type"])
                cand["boite"] = boite
                _merge_inconnues(rapport, boite, prefix=f"rapport {ratio:g}")
            else:
                _push_inconnue(rapport, "impossibles", "couple dimensionnement", "Impossible de dimensionner la boîte pour ce rapport.")

            s_m, nm = self._score_cible_ou_plage(rpm_m, cible=rpm_opt, mini=rpm_m_min, maxi=rpm_m_max, nom="rpm_moteur")
            s_a, na = self._score_cible_ou_plage(rpm_alt, cible=rpm_alt_c, mini=rpm_alt_min, maxi=rpm_alt_max, nom="rpm_alternateur")
            cand["notes"].extend(nm + na)
            s_eta = (1.0 - max(0.0, min(1.0, eta_alt))) if eta_alt is not None else None
            s_pertes = (P_pertes / max(Pdc, 1e-12)) if P_pertes is not None else None
            s_couple = (float(couple_dim) / max(float(T_mot_min), 1e-12) - 1.0) if (couple_dim is not None and T_mot_min not in (None, 0)) else None
            scores = {"score_cycle_moteur": s_m, "score_vitesse_alternateur": s_a, "score_eta_alternateur": s_eta, "score_pertes_alternateur": s_pertes, "score_couple_moteur": s_couple}
            weights = {"score_cycle_moteur": 3.0, "score_vitesse_alternateur": 2.5, "score_eta_alternateur": 1.5, "score_pertes_alternateur": 1.0, "score_couple_moteur": 0.8}
            total = denom = 0.0; missing = 0
            for k, w in weights.items():
                v = scores[k]
                if v is None:
                    missing += 1; continue
                total += w * max(0.0, float(v)); denom += w
            scores["score_global"] = (total / denom if denom > 0 else float("inf")) + 0.03 * missing
            cand["scores"] = scores
            rapport["candidats"].append(cand)

        if not rapport["candidats"]:
            _push_inconnue(rapport, "impossibles", "candidats", "Aucun candidat exploitable.")
            _dedup_inconnues(rapport); return rapport

        def metric(c: Mapping[str, Any], key: str) -> Optional[float]:
            return _safe_float((c.get("exigences", {}) or {}).get(key))

        selection = None
        if strategie == "maintien_cycle_moteur":
            selection = min(rapport["candidats"], key=lambda c: float(c.get("scores", {}).get("score_global", float("inf"))))
        elif strategie == "max_eta_alternateur":
            vals = [c for c in rapport["candidats"] if metric(c, "eta_alternateur") is not None]
            selection = max(vals, key=lambda c: metric(c, "eta_alternateur")) if vals else None
        elif strategie == "min_pertes_alternateur":
            vals = [c for c in rapport["candidats"] if metric(c, "P_pertes_alternateur_W") is not None]
            selection = min(vals, key=lambda c: metric(c, "P_pertes_alternateur_W")) if vals else None
        elif strategie == "min_couple_moteur":
            vals = [c for c in rapport["candidats"] if metric(c, "couple_moteur_requis_Nm") is not None or metric(c, "couple_moteur_min_theorique_Nm") is not None]
            selection = min(vals, key=lambda c: metric(c, "couple_moteur_requis_Nm") if metric(c, "couple_moteur_requis_Nm") is not None else metric(c, "couple_moteur_min_theorique_Nm")) if vals else None
        elif strategie == "pareto":
            pts: List[Tuple[float, float, Dict[str, Any]]] = []
            for c in rapport["candidats"]:
                eta = metric(c, "eta_alternateur")
                t = metric(c, "couple_moteur_requis_Nm") or metric(c, "couple_moteur_min_theorique_Nm")
                if eta is not None and t is not None:
                    pts.append((eta, t, c))
            front: List[Dict[str, Any]] = []
            for i, (eta_i, t_i, c_i) in enumerate(pts):
                dominated = False
                for j, (eta_j, t_j, _) in enumerate(pts):
                    if i != j and (eta_j >= eta_i and t_j <= t_i) and (eta_j > eta_i or t_j < t_i):
                        dominated = True; break
                if not dominated:
                    front.append(c_i)
            rapport["selection"] = {"strategie": strategie, "pareto_front": front, "count": len(front)}
        else:
            raise ValueError("strategie invalide.")
        if selection is not None:
            rapport["selection"] = {"strategie": strategie, "rapport": selection.get("rapport"), "type_rapport": selection.get("type_rapport"), "rpm_moteur": selection.get("rpm_moteur"), "rpm_alternateur": selection.get("rpm_alternateur"), "resume": selection.get("exigences", {}), "scores": selection.get("scores", {})}
        elif rapport["selection"] is None:
            _push_inconnue(rapport, "partielles", "selection", "Métriques insuffisantes pour cette stratégie.")
        _dedup_inconnues(rapport)
        return rapport

    def analyser_pieces(
        self,
        *,
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
        piece_kwargs = dict(piece_kwargs or {})
        rep: Dict[str, Any] = {"pieces": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        T = couple_nm
        def build_or_use(name: str, supplied: Any, cls: Any, kwargs: Dict[str, Any]) -> Any:
            if supplied is not None:
                return supplied
            merged = dict(kwargs); merged.update(piece_kwargs.get(name, {}))
            accepted = set(getattr(cls, "__dataclass_fields__", {}).keys())
            return cls(**{k: v for k, v in merged.items() if k in accepted})
        pignon = build_or_use("pignon", self.piece_pignon, PignonBoite, {"couple_max_Nm": T, "diametre_primitif_m": self.diametre_primitif_m, "largeur_denture_b_m": self.largeur_denture_b_m, "module_m": self.module_m, "angle_pression_deg": self.angle_pression_deg, "angle_helice_deg": self.angle_helice_deg, "coefficient_zh": self.coefficient_zh, "facteur_forme_y": self.facteur_forme_y})
        p_rep = pignon.analyser(strict=False)
        rep["pieces"]["pignon"] = p_rep; _merge_inconnues(rep, p_rep, prefix="pignon")
        forces = p_rep.get("forces", {}) if isinstance(p_rep.get("forces"), Mapping) else {}
        Fr = force_radiale_N if force_radiale_N is not None else forces.get("F_radiale_N")
        Fa = force_axiale_N if force_axiale_N is not None else forces.get("F_axiale_N")
        arbre = build_or_use("arbre", self.piece_arbre, ArbreBoite, {"couple_max_Nm": T, "moment_flechissant_max_Nm": moment_flechissant_nm, "diametre_arbre_m": self.diametre_arbre_m, "limite_elastique_pa": self.limite_elastique_arbre_pa, "facteur_securite": self.facteur_securite_arbre})
        a_rep = arbre.analyser(strict=False)
        rep["pieces"]["arbre"] = a_rep; _merge_inconnues(rep, a_rep, prefix="arbre")
        crabot = build_or_use("crabot", self.piece_crabot, Crabot, {"couple_max_Nm": T, "delta_omega_rad_s": delta_omega_rad_s, "temps_engagement_s": temps_engagement_s, "inertie_primaire_kg_m2": inertie_primaire_kg_m2, "inertie_secondaire_kg_m2": inertie_secondaire_kg_m2, "nombre_dents": self.crabot_nombre_dents, "hauteur_dent_m": self.crabot_hauteur_dent_m, "largeur_dent_m": self.crabot_largeur_dent_m, "rayon_moyen_m": self.crabot_rayon_moyen_m, "facteur_repartition": self.crabot_facteur_repartition, "pression_admissible_pa": self.crabot_pression_admissible_pa})
        c_rep = crabot.analyser(strict=False)
        rep["pieces"]["crabot"] = c_rep; _merge_inconnues(rep, c_rep, prefix="crabot")
        roulement = build_or_use("roulement", self.piece_roulement, RoulementBoite, {"force_radiale_N": Fr, "force_axiale_N": Fa, "rpm": vitesse_rotation_tr_min, "capacite_dynamique_C_N": self.roulement_C_N, "facteur_X": self.roulement_X, "facteur_Y": self.roulement_Y, "type_roulement": self.roulement_type, "exposant_p": self.roulement_exposant_p, "duree_vie_cible_heures": self.roulement_duree_vie_cible_h})
        r_rep = roulement.analyser(strict=False)
        rep["pieces"]["roulement"] = r_rep; _merge_inconnues(rep, r_rep, prefix="roulement")
        baladeur = build_or_use("baladeur", self.piece_baladeur, Baladeur, {"couple_max_Nm": T})
        b_rep = baladeur.analyser(strict=False)
        rep["pieces"]["baladeur"] = b_rep; _merge_inconnues(rep, b_rep, prefix="baladeur")
        fourchette = build_or_use("fourchette", self.piece_fourchette, Fourchette, {})
        f_rep = fourchette.analyser(strict=False)
        rep["pieces"]["fourchette"] = f_rep; _merge_inconnues(rep, f_rep, prefix="fourchette")
        carter = build_or_use("carter", self.piece_carter, CarterBoite, {"roulements": [r_rep]})
        ca_rep = carter.analyser(strict=False)
        rep["pieces"]["carter"] = ca_rep; _merge_inconnues(rep, ca_rep, prefix="carter")
        _dedup_inconnues(rep)
        return rep

    def analyser(
        self,
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
        alternateur: Optional[Any] = None,
        puissance_bus_dc_w: Optional[float] = None,
        rpm_moteur: Optional[float] = None,
        rapports: Optional[Sequence[float]] = None,
        rendement_boite: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Optional[Any] = None,
        moteur: Optional[Any] = None,
        strategie: StrategieOptimisation = "maintien_cycle_moteur",
        rpm_moteur_optimal: Optional[float] = None,
        rpm_moteur_min_optimal: Optional[float] = None,
        rpm_moteur_max_optimal: Optional[float] = None,
        couple_moteur_max_admissible_Nm: Optional[float] = None,
        puissance_moteur_max_admissible_W: Optional[float] = None,
        rpm_alternateur_cible: Optional[float] = None,
        rpm_alternateur_min_optimal: Optional[float] = None,
        rpm_alternateur_max_optimal: Optional[float] = None,
        rapport_min: Optional[float] = None,
        rapport_max: Optional[float] = None,
        nb_rapports_auto: Optional[int] = None,
        forcer_multiplication: Optional[bool] = None,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {"composant": "boite_crabots", "role_fonctionnel": "maintenir le moteur thermique dans son cycle optimal et adapter/multiplier le régime vers l'alternateur", "entrees": {}, "analyses": {}, "synthese": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        if couple_nm is not None:
            point = self.analyser_point(couple_nm=couple_nm, vitesse_rotation_tr_min=vitesse_rotation_tr_min, calcul_forces_engrenage_actif=calcul_forces_engrenage_actif, moment_flechissant_nm=moment_flechissant_nm, inertie_primaire_kg_m2=inertie_primaire_kg_m2, inertie_secondaire_kg_m2=inertie_secondaire_kg_m2, delta_omega_rad_s=delta_omega_rad_s, temps_engagement_s=temps_engagement_s, force_axiale_N=force_axiale_N, force_radiale_N=force_radiale_N)
            rep["analyses"]["point"] = point; _merge_inconnues(rep, point, prefix="point")
            rep["synthese"].update({"F_t_N": point.get("resultats", {}).get("F_t_N"), "F_r_N": point.get("resultats", {}).get("F_r_N"), "F_a_N": point.get("resultats", {}).get("F_a_N"), "sigma_H_Pa": point.get("contraintes", {}).get("sigma_H_Pa"), "sigma_F_Pa": point.get("contraintes", {}).get("sigma_F_Pa"), "tau_torsion_Pa": point.get("contraintes", {}).get("tau_torsion_Pa"), "sigma_von_mises_Pa": point.get("contraintes", {}).get("sigma_von_mises_Pa"), "T_cap_crabot_Nm": point.get("crabot", {}).get("T_cap_Nm"), "P_eq_roulement_N": point.get("roulements", {}).get("P_eq_N"), "L10_roulement_h": point.get("roulements", {}).get("L10_heures")})
        else:
            _push_inconnue(rep, "partielles", "analyse_point", "Fournir couple_nm pour lancer l'analyse mécanique locale directe.")
        wants_chain = any(v is not None for v in (alternateur, puissance_bus_dc_w, rpm_moteur, rpm_moteur_optimal, rapports, rpm_alternateur_cible, rpm_alternateur_min_optimal, rpm_alternateur_max_optimal, self.rpm_moteur_optimal, self.rpm_alternateur_cible, self.rpm_alternateur_min_optimal, self.rpm_alternateur_max_optimal))
        if wants_chain:
            if puissance_bus_dc_w is None:
                _push_inconnue(rep, "impossibles", "puissance_bus_dc_w", "Requise pour la chaîne moteur optimal -> boîte -> alternateur.")
            else:
                chaine = self.analyser_chaine_moteur_alternateur(alternateur=alternateur, puissance_bus_dc_w=puissance_bus_dc_w, rpm_moteur=rpm_moteur, rapports=rapports, rendement_boite=rendement_boite, tension_bus_dc_v=tension_bus_dc_v, batterie=batterie, moteur=moteur, strategie=strategie, rpm_moteur_optimal=rpm_moteur_optimal, rpm_moteur_min_optimal=rpm_moteur_min_optimal, rpm_moteur_max_optimal=rpm_moteur_max_optimal, couple_moteur_max_admissible_Nm=couple_moteur_max_admissible_Nm, puissance_moteur_max_admissible_W=puissance_moteur_max_admissible_W, rpm_alternateur_cible=rpm_alternateur_cible, rpm_alternateur_min_optimal=rpm_alternateur_min_optimal, rpm_alternateur_max_optimal=rpm_alternateur_max_optimal, rapport_min=rapport_min, rapport_max=rapport_max, nb_rapports_auto=nb_rapports_auto, forcer_multiplication=forcer_multiplication, inertie_primaire_kg_m2=inertie_primaire_kg_m2, inertie_secondaire_kg_m2=inertie_secondaire_kg_m2, delta_omega_rad_s=delta_omega_rad_s, temps_engagement_s=temps_engagement_s, force_radiale_N=force_radiale_N, force_axiale_N=force_axiale_N)
                rep["analyses"]["chaine_moteur_optimal_alternateur"] = chaine; _merge_inconnues(rep, chaine, prefix="chaine")
                sel = chaine.get("selection") if isinstance(chaine.get("selection"), Mapping) else None
                if sel:
                    res = sel.get("resume", {}) if isinstance(sel.get("resume"), Mapping) else {}
                    rep["synthese"].update({"rapport_selectionne": sel.get("rapport"), "rpm_alternateur_selectionne": sel.get("rpm_alternateur"), "couple_moteur_requis_Nm": res.get("couple_moteur_requis_Nm"), "couple_moteur_min_theorique_Nm": res.get("couple_moteur_min_theorique_Nm"), "puissance_moteur_requise_W": res.get("puissance_moteur_requise_W"), "puissance_moteur_min_theorique_W": res.get("puissance_moteur_min_theorique_W")})
        if analyser_pieces:
            T_piece = couple_nm
            if T_piece is None:
                sel = rep.get("analyses", {}).get("chaine_moteur_optimal_alternateur", {}).get("selection")
                if isinstance(sel, Mapping):
                    res = sel.get("resume", {}) if isinstance(sel.get("resume"), Mapping) else {}
                    T_piece = res.get("couple_moteur_requis_Nm") or res.get("couple_moteur_min_theorique_Nm")
            pieces = self.analyser_pieces(couple_nm=T_piece, vitesse_rotation_tr_min=vitesse_rotation_tr_min or rpm_moteur_optimal or self.rpm_moteur_optimal or rpm_moteur, moment_flechissant_nm=moment_flechissant_nm, inertie_primaire_kg_m2=inertie_primaire_kg_m2, inertie_secondaire_kg_m2=inertie_secondaire_kg_m2, delta_omega_rad_s=delta_omega_rad_s, temps_engagement_s=temps_engagement_s, force_axiale_N=force_axiale_N, force_radiale_N=force_radiale_N, piece_kwargs=piece_kwargs)
            rep["analyses"]["pieces"] = pieces; _merge_inconnues(rep, pieces, prefix="pieces")
        _dedup_inconnues(rep)
        return rep


# =============================================================================
# API haut niveau
# =============================================================================

def _filtrer_kwargs(cls: Any, valeurs: Mapping[str, Any]) -> Dict[str, Any]:
    fields = set(getattr(cls, "__dataclass_fields__", {}).keys())
    if not fields:
        try:
            fields = set(inspect.signature(cls).parameters.keys())
        except Exception:
            return dict(valeurs)
    return {k: v for k, v in dict(valeurs).items() if k in fields}


def construire_boite_crabots(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> BoiteCrabots:
    cfg: Dict[str, Any] = dict(config or {})
    cfg.update(overrides)
    bloc = cfg.get("boite_crabots", cfg)
    if not isinstance(bloc, Mapping):
        raise ValueError("config['boite_crabots'] doit être un dictionnaire si fourni.")
    return BoiteCrabots(**_filtrer_kwargs(BoiteCrabots, bloc))


def concevoir_boite_crabots(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = dict(config or {})
    cfg.update(overrides)
    boite = cfg.get("instance")
    if boite is None:
        boite = construire_boite_crabots(cfg)
    if not isinstance(boite, BoiteCrabots):
        raise ValueError("config['instance'] doit être une BoiteCrabots si fourni.")
    analyse_cfg = cfg.get("analyse", cfg)
    if not isinstance(analyse_cfg, Mapping):
        raise ValueError("config['analyse'] doit être un dictionnaire si fourni.")
    accepted = set(inspect.signature(boite.analyser).parameters.keys())
    rapport = boite.analyser(**{k: v for k, v in dict(analyse_cfg).items() if k in accepted})
    rapport["objet"] = _to_jsonable(boite, max_depth=4)
    return rapport


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | Path, *, indent: int = 2) -> Path:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=indent), encoding="utf-8")
    return path


__all__ = [
    "BoiteCrabots", "construire_boite_crabots", "concevoir_boite_crabots", "exporter_rapport_json",
    "PignonBoite", "ArbreBoite", "Crabot", "RoulementBoite", "Baladeur", "Fourchette", "CarterBoite",
    "calcul_force_tangentielle", "calcul_forces_engrenage", "calcul_contrainte_contact_hertz", "calcul_contrainte_flexion_lewis",
    "calcul_contrainte_cisaillement_torsion", "calcul_contrainte_flexion_arbre", "calcul_von_mises_arbre",
    "calcul_couple_transmissible_crabot", "calcul_pression_contact_crabot", "calcul_inertie_equivalente",
    "calcul_energie_choc", "calcul_couple_synchronisation_moyen", "calcul_charge_equivalente_roulement", "calcul_duree_vie_l10", "calcul_duree_vie_heures",
]


if __name__ == "__main__":
    exemple = {
        "boite_crabots": {
            "diametre_primitif_m": 0.08,
            "largeur_denture_b_m": 0.018,
            "module_m": 0.002,
            "diametre_arbre_m": 0.025,
            "limite_elastique_arbre_pa": 650e6,
            "crabot_nombre_dents": 6,
            "crabot_hauteur_dent_m": 0.006,
            "crabot_largeur_dent_m": 0.008,
            "crabot_rayon_moyen_m": 0.035,
            "crabot_pression_admissible_pa": 250e6,
            "roulement_C_N": 8000.0,
            "roulement_X": 1.0,
            "roulement_Y": 0.0,
            "rpm_moteur_optimal": 2800.0,
            "rpm_moteur_min_optimal": 2600.0,
            "rpm_moteur_max_optimal": 3000.0,
            "rpm_alternateur_cible": 9000.0,
            "rpm_alternateur_min_optimal": 7500.0,
            "rpm_alternateur_max_optimal": 10500.0,
            "rendement_boite_defaut": 0.94,
        },
        "analyse": {
            "couple_nm": 120.0,
            "vitesse_rotation_tr_min": 2800.0,
            "moment_flechissant_nm": 35.0,
            "inertie_primaire_kg_m2": 0.015,
            "inertie_secondaire_kg_m2": 0.040,
            "delta_omega_rad_s": 120.0,
            "temps_engagement_s": 0.25,
            "puissance_bus_dc_w": 25_000.0,
            "rapports": [2.5, 3.0, 3.2, 3.5, 4.0],
        },
    }
    rapport = concevoir_boite_crabots(exemple)
    print(json.dumps(_to_jsonable({
        "role_fonctionnel": rapport.get("role_fonctionnel"),
        "synthese": rapport.get("synthese"),
        "selection": rapport.get("analyses", {}).get("chaine_moteur_optimal_alternateur", {}).get("selection"),
        "inconnues": rapport.get("inconnues"),
    }), ensure_ascii=False, indent=2))
