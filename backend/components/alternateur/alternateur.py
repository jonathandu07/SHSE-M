# backend/components/alternateur.py
from __future__ import annotations

"""
Alternateur SHSE-M / STHO-ME — version système intégrée
========================================================

Rôle du composant
-----------------
L'alternateur n'est pas un calcul isolé. Dans le système SHSE-M, il est placé entre :

    moteur thermique -> boîte à crabots -> alternateur -> bus DC -> batterie / moteur électrique

Cette version :
- calcule la cinématique rotor, la fréquence électrique et la FEM ;
- calcule la puissance AC/DC utile, les pertes connues, le rendement sur pertes connues ;
- distingue strictement les valeurs calculées, les bornes minimales et les valeurs dimensionnantes ;
- produit des clés compatibles avec la boîte à crabots :
    resultats.P_out_W
    resultats.eta_total
    resultats.P_mecanique_W
    resultats.couple_mecanique_Nm
    pertes.P_pertes_totales_W
- produit des exigences mécaniques remontables vers la boîte et le moteur thermique ;
- produit des exigences électriques remontables vers la batterie / bus DC ;
- vérifie les plages optimales de régime alternateur ;
- analyse rotor, stator, arbre, carter, ventilation, bobine d'excitation et roulement sans inventer
  de données constructeur.

Unités SI : m, kg, s, N, Pa, W, V, A, Ohm, Hz, rad/s, tr/min.

Principe "sans invention"
-------------------------
Le script ne crée pas de rendement, coefficient Steinmetz, résistance, capacité roulement,
résistance thermique ou coefficient de convection si tu ne les fournis pas.

Quand une donnée manque, il remonte une inconnue :
- "impossibles" : la conclusion demandée est impossible ;
- "partielles"  : une estimation partielle ou une borne peut être produite.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Mapping, Optional, Sequence, Tuple
import inspect
import json
import math
import os
import sys


# =============================================================================
# Chemins / imports robustes
# =============================================================================

_HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
for _p in (
    _HERE,
    _HERE / "modules",
    _HERE / "pieces",
    _HERE.parent,
    _HERE.parent / "modules" / "alternateur",
    _HERE.parent / "components" / "alternateur" / "modules",
    _HERE.parent / "components" / "alternateur" / "pieces",
    Path.cwd(),
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

_IMPORT_ERRORS: Dict[str, str] = {}


def _import_attr(module_names: Iterable[str], attr: str, *, required: bool = False) -> Any:
    last_exc: Optional[BaseException] = None
    tried: list[str] = []
    for module_name in module_names:
        tried.append(module_name)
        try:
            mod = import_module(module_name)
            return getattr(mod, attr)
        except BaseException as exc:
            last_exc = exc
            continue
    key = f"{attr} ({', '.join(tried[:4])}{'...' if len(tried) > 4 else ''})"
    _IMPORT_ERRORS[key] = f"{type(last_exc).__name__}: {last_exc}"
    if required:
        raise ImportError(f"Impossible d'importer {attr}. Dernière erreur: {last_exc}")
    return None


def _alts(module_basename: str) -> Tuple[str, ...]:
    return (
        f"backend.components.alternateur.modules.{module_basename}",
        f"backend.modules.alternateur.{module_basename}",
        f"components.alternateur.modules.{module_basename}",
        f"modules.alternateur.{module_basename}",
        f"modules.{module_basename}",
        module_basename,
    )


def _piece_alts(module_basename: str) -> Tuple[str, ...]:
    return (
        f"backend.components.alternateur.pieces.{module_basename}",
        f"backend.modules.alternateur.pieces.{module_basename}",
        f"components.alternateur.pieces.{module_basename}",
        f"pieces.{module_basename}",
        module_basename,
    )


# Modules calcul fournis.
calcul_vitesse_angulaire = _import_attr(_alts("calcul_vitesse_angulaire"), "calcul_vitesse_angulaire")
calcul_frequence_synchrone = _import_attr(_alts("calcul_frequence_synchrone"), "calcul_frequence_synchrone")
calcul_fem_induite = _import_attr(_alts("calcul_fem_induite"), "calcul_fem_induite")
calcul_flux_pole = _import_attr(_alts("calcul_fem_induite"), "calcul_flux_pole")
tension_ligne_depuis_phase = _import_attr(_alts("calcul_fem_induite"), "tension_ligne_depuis_phase")
tension_phase_depuis_ligne = _import_attr(_alts("calcul_fem_induite"), "tension_phase_depuis_ligne")
calcul_puissance_triphase = _import_attr(_alts("calcul_puissance_electrique"), "calcul_puissance_triphase")
calcul_puissance_monophase = _import_attr(_alts("calcul_puissance_electrique"), "calcul_puissance_monophase")
calcul_puissance_dc = _import_attr(_alts("calcul_puissance_electrique"), "calcul_puissance_dc")
calcul_resistance_enroulement = _import_attr(_alts("calcul_pertes_cuivre"), "calcul_resistance_enroulement")
calcul_pertes_cuivre_phase = _import_attr(_alts("calcul_pertes_cuivre"), "calcul_pertes_cuivre_phase")
calcul_pertes_cuivre_triphase = _import_attr(_alts("calcul_pertes_cuivre"), "calcul_pertes_cuivre_triphase")
calcul_pertes_fer_steinmetz = _import_attr(_alts("calcul_pertes_fer"), "calcul_pertes_fer_steinmetz")
calcul_rendement_alternateur = _import_attr(_alts("calcul_rendement_alternateur"), "calcul_rendement_alternateur")
calcul_puissance_mecanique = _import_attr(_alts("calcul_puissance_mecanique"), "calcul_puissance_mecanique")
calcul_couple_alternateur = _import_attr(_alts("calcul_couple_alternateur"), "calcul_couple_alternateur")
calcul_echauffement_thermique = _import_attr(_alts("calcul_echauffement_thermique"), "calcul_echauffement_thermique")

# Modules batterie optionnels.
calcul_temps_charge = _import_attr(
    (
        "backend.components.batterie.modules.calcul_temps_charge",
        "backend.modules.batterie.calcul_temps_charge",
        "components.batterie.modules.calcul_temps_charge",
        "modules.batterie.calcul_temps_charge",
        "calcul_temps_charge",
    ),
    "calcul_temps_charge",
)

# Pièces externes optionnelles.
RotorPiece = _import_attr(_piece_alts("rotor"), "Rotor")
StatorPiece = _import_attr(_piece_alts("stator"), "Stator")
ArbreAlternateurPiece = _import_attr(_piece_alts("arbre_alternateur"), "ArbreAlternateur")
CarterAlternateurPiece = _import_attr(_piece_alts("carter_alternateur"), "CarterAlternateur")
VentilateurPiece = _import_attr(_piece_alts("ventilateur"), "Ventilateur")
BobineExcitationPiece = _import_attr(_piece_alts("bobine_excite"), "BobineExcitation")
RoulementAlternateurPiece = _import_attr(_piece_alts("roulement_alternateur"), "RoulementAlternateur")


# =============================================================================
# Fallbacks mathématiques si le fichier est utilisé seul
# =============================================================================

def _fallback_calcul_vitesse_angulaire(vitesse_rotation_tr_min: float, *, input_unite: str = "rpm", allow_negative: bool = True, clamp_non_negative: bool = False) -> float:
    x = _req_finite("vitesse_rotation_tr_min", vitesse_rotation_tr_min)
    if not allow_negative and x < 0:
        raise ValueError("La vitesse de rotation ne peut pas être négative.")
    if input_unite == "rpm":
        omega = 2.0 * math.pi * x / 60.0
    elif input_unite == "rad_s":
        omega = x
    else:
        raise ValueError("input_unite doit être 'rpm' ou 'rad_s'.")
    return abs(omega) if clamp_non_negative else omega


def _fallback_calcul_frequence_synchrone(vitesse_rotation_tr_min: float, nombre_poles: int, *, mode_poles: str = "poles", clamp_non_negative: bool = True) -> float:
    n = _req_finite("vitesse_rotation_tr_min", vitesse_rotation_tr_min)
    if not isinstance(nombre_poles, int) or nombre_poles <= 0:
        raise ValueError("nombre_poles doit être un entier > 0.")
    if mode_poles in ("poles", "pair_poles"):
        if nombre_poles % 2 != 0:
            raise ValueError("Le nombre de pôles doit être pair.")
        f = n * nombre_poles / 120.0
    elif mode_poles == "pole_pairs":
        f = n * nombre_poles / 60.0
    else:
        raise ValueError("mode_poles invalide.")
    return abs(f) if clamp_non_negative else f


def _fallback_calcul_flux_pole(induction_gap_t: float, aire_pole_m2: float, *, flux_model: str = "B*A") -> float:
    B = _req_finite("induction_gap_t", induction_gap_t)
    A = _req_pos("aire_pole_m2", aire_pole_m2, strict=False)
    return abs(B) * A if flux_model == "abs(B)*A" else B * A


def _fallback_calcul_fem_induite(
    frequence_hz: float,
    nombre_spires_serie: int,
    flux_max_pole_wb: float,
    facteur_enroulement_kw: float,
    *,
    onde: str = "sinus",
    constante_custom: Optional[float] = None,
    clamp_non_negative: bool = True,
) -> float:
    f = _req_pos("frequence_hz", frequence_hz, strict=False)
    if not isinstance(nombre_spires_serie, int) or nombre_spires_serie < 0:
        raise ValueError("nombre_spires_serie doit être un entier >= 0.")
    phi = _req_finite("flux_max_pole_wb", flux_max_pole_wb)
    kw = _req_finite("facteur_enroulement_kw", facteur_enroulement_kw)
    if onde == "sinus":
        C = 4.44
    elif onde == "carree":
        C = 4.00
    elif onde == "custom" and constante_custom is not None:
        C = _req_pos("constante_custom", constante_custom, strict=True)
    else:
        raise ValueError("onde doit être 'sinus', 'carree' ou 'custom'.")
    E = C * f * nombre_spires_serie * phi * kw
    return abs(E) if clamp_non_negative else E


def _fallback_tension_ligne_depuis_phase(v_phase_rms: float, couplage: str) -> float:
    V = _req_pos("v_phase_rms", v_phase_rms, strict=False)
    if couplage in ("Y", "etoile"):
        return math.sqrt(3.0) * V
    if couplage in ("Delta", "triangle"):
        return V
    raise ValueError("couplage/connexion invalide.")


def _fallback_tension_phase_depuis_ligne(v_ligne_rms: float, couplage: str) -> float:
    V = _req_pos("v_ligne_rms", v_ligne_rms, strict=False)
    if couplage in ("Y", "etoile"):
        return V / math.sqrt(3.0)
    if couplage in ("Delta", "triangle"):
        return V
    raise ValueError("couplage/connexion invalide.")


def _fallback_puissance_triphase(tension_composee: float, courant_ligne: float, facteur_puissance: float = 1.0, *, entree: str = "VLL_IL", connexion: str = "Y", clamp_non_negative: bool = False, **_: Any) -> float:
    V = _req_finite("tension_composee", tension_composee)
    I = _req_finite("courant_ligne", courant_ligne)
    pf = max(-1.0, min(1.0, _req_finite("facteur_puissance", facteur_puissance)))
    if entree == "Vph_Iph":
        if connexion == "Y":
            V, I = math.sqrt(3.0) * V, I
        elif connexion == "Delta":
            V, I = V, math.sqrt(3.0) * I
        else:
            raise ValueError("connexion doit être Y ou Delta.")
    P = math.sqrt(3.0) * V * I * pf
    return max(0.0, P) if clamp_non_negative else P


def _fallback_puissance_monophase(tension: float, courant: float, facteur_puissance: float = 1.0, *, clamp_non_negative: bool = False, **_: Any) -> float:
    P = _req_finite("tension", tension) * _req_finite("courant", courant) * max(-1.0, min(1.0, _req_finite("facteur_puissance", facteur_puissance)))
    return max(0.0, P) if clamp_non_negative else P


def _fallback_puissance_dc(tension_dc: float, courant_dc: float, *, clamp_non_negative: bool = False, **_: Any) -> float:
    P = _req_finite("tension_dc", tension_dc) * _req_finite("courant_dc", courant_dc)
    return max(0.0, P) if clamp_non_negative else P


def _fallback_resistance_enroulement(resistivite: float, longueur_fil: float, section_fil: float, *, temperature_c: Optional[float] = None, temperature_ref_c: float = 20.0, coef_temperature: float = 0.00393, clamp_non_negative: bool = True) -> float:
    rho = _req_pos("resistivite", resistivite, strict=False)
    L = _req_pos("longueur_fil", longueur_fil, strict=False)
    A = _req_pos("section_fil", section_fil, strict=True)
    if temperature_c is not None:
        rho *= 1.0 + _req_finite("coef_temperature", coef_temperature) * (_req_finite("temperature_c", temperature_c) - _req_finite("temperature_ref_c", temperature_ref_c))
    R = rho * L / A
    return max(0.0, R) if clamp_non_negative else R


def _fallback_pertes_cuivre_phase(courant: float, resistance: float, *, courant_type: str = "rms", clamp_non_negative: bool = True) -> float:
    I = _req_finite("courant", courant)
    if courant_type == "peak":
        I /= math.sqrt(2.0)
    R = _req_finite("resistance", resistance)
    P = I * I * R
    return max(0.0, P) if clamp_non_negative else P


def _fallback_pertes_cuivre_triphase(courant_phase: float, resistance_phase: float, *, courant_type: str = "rms", connexion: str = "Y", courant_est_ligne: bool = False, clamp_non_negative: bool = True) -> float:
    I = _req_finite("courant_phase", courant_phase)
    if courant_type == "peak":
        I /= math.sqrt(2.0)
    if courant_est_ligne and connexion == "Delta":
        I /= math.sqrt(3.0)
    R = _req_finite("resistance_phase", resistance_phase)
    P = 3.0 * I * I * R
    return max(0.0, P) if clamp_non_negative else P


def _fallback_pertes_fer_steinmetz(k_h: float, frequence: float, induction_max: float, exposant_steinmetz: float, k_e: float, *, eddy_freq_exp: float = 2.0, eddy_induction_exp: float = 2.0, masse_kg: Optional[float] = None, volume_m3: Optional[float] = None, return_details: bool = False, clamp_non_negative: bool = True) -> float | Dict[str, float]:
    kh = _req_pos("k_h", k_h, strict=False)
    ke = _req_pos("k_e", k_e, strict=False)
    f = _req_pos("frequence", frequence, strict=False)
    B = _req_pos("induction_max", induction_max, strict=False)
    x = _req_finite("exposant_steinmetz", exposant_steinmetz)
    hyst = kh * f * (B ** x)
    eddy = ke * (f ** _req_finite("eddy_freq_exp", eddy_freq_exp)) * (B ** _req_finite("eddy_induction_exp", eddy_induction_exp))
    spec = hyst + eddy
    if clamp_non_negative:
        hyst, eddy, spec = max(0.0, hyst), max(0.0, eddy), max(0.0, spec)
    if masse_kg is not None and volume_m3 is not None:
        raise ValueError("Fournis masse_kg ou volume_m3, pas les deux.")
    factor = 1.0
    if masse_kg is not None:
        factor = _req_pos("masse_kg", masse_kg, strict=True)
    elif volume_m3 is not None:
        factor = _req_pos("volume_m3", volume_m3, strict=True)
    total = spec * factor
    return {"P_hyst": hyst * factor, "P_eddy": eddy * factor, "P_total": total, "P_spec": spec, "facteur_totalisation": factor} if return_details else total


def _fallback_rendement(puissance_utile_out: float, somme_pertes: float = 0.0, liste_pertes: Optional[Iterable[float]] = None, *, clamp_0_1: bool = True, return_details: bool = False, **_: Any) -> float | Dict[str, float]:
    Pout = _req_finite("puissance_utile_out", puissance_utile_out)
    losses = sum(float(x) for x in (liste_pertes if liste_pertes is not None else [somme_pertes]) if x is not None)
    Pin = Pout + losses
    eta = 0.0 if Pin <= 1e-12 else Pout / Pin
    if clamp_0_1:
        eta = max(0.0, min(1.0, eta))
    return {"eta": eta, "P_out": Pout, "P_losses": losses, "P_in": Pin} if return_details else eta


def _fallback_puissance_mecanique(puissance_electrique_cible: float, rendement_alternateur: float, *, pertes_fixes_w: float = 0.0, clamp_non_negative: bool = False, mode_signe: str = "conserver") -> float:
    P = (_req_finite("puissance_electrique_cible", puissance_electrique_cible) + _req_finite("pertes_fixes_w", pertes_fixes_w)) / _req_eta("rendement_alternateur", rendement_alternateur)
    if mode_signe == "abs":
        P = abs(P)
    return max(0.0, P) if clamp_non_negative else P


def _fallback_couple_alternateur(puissance_electrique_cible: float, rendement_alternateur: float, vitesse_angulaire: float, *, pertes_fixes_w: float = 0.0, clamp_non_negative: bool = False, mode_signe: str = "conserver", epsilon_omega: float = 1e-12) -> float:
    Pm = _fallback_puissance_mecanique(puissance_electrique_cible, rendement_alternateur, pertes_fixes_w=pertes_fixes_w, clamp_non_negative=False, mode_signe="conserver")
    omega = _req_finite("vitesse_angulaire", vitesse_angulaire)
    if abs(omega) <= epsilon_omega:
        raise ValueError("omega nul.")
    if mode_signe == "abs_omega":
        omega = abs(omega)
    T = Pm / omega
    return max(0.0, T) if clamp_non_negative else T


def _fallback_echauffement(puissance_pertes_totale: float, resistance_thermique: float, *, offset_temperature: float = 0.0, clamp_non_negative: bool = False) -> float:
    dT = _req_finite("puissance_pertes_totale", puissance_pertes_totale) * _req_finite("resistance_thermique", resistance_thermique) + _req_finite("offset_temperature", offset_temperature)
    return max(0.0, dT) if clamp_non_negative else dT


calcul_vitesse_angulaire = calcul_vitesse_angulaire or _fallback_calcul_vitesse_angulaire
calcul_frequence_synchrone = calcul_frequence_synchrone or _fallback_calcul_frequence_synchrone
calcul_flux_pole = calcul_flux_pole or _fallback_calcul_flux_pole
calcul_fem_induite = calcul_fem_induite or _fallback_calcul_fem_induite
tension_ligne_depuis_phase = tension_ligne_depuis_phase or _fallback_tension_ligne_depuis_phase
tension_phase_depuis_ligne = tension_phase_depuis_ligne or _fallback_tension_phase_depuis_ligne
calcul_puissance_triphase = calcul_puissance_triphase or _fallback_puissance_triphase
calcul_puissance_monophase = calcul_puissance_monophase or _fallback_puissance_monophase
calcul_puissance_dc = calcul_puissance_dc or _fallback_puissance_dc
calcul_resistance_enroulement = calcul_resistance_enroulement or _fallback_resistance_enroulement
calcul_pertes_cuivre_phase = calcul_pertes_cuivre_phase or _fallback_pertes_cuivre_phase
calcul_pertes_cuivre_triphase = calcul_pertes_cuivre_triphase or _fallback_pertes_cuivre_triphase
calcul_pertes_fer_steinmetz = calcul_pertes_fer_steinmetz or _fallback_pertes_fer_steinmetz
calcul_rendement_alternateur = calcul_rendement_alternateur or _fallback_rendement
calcul_puissance_mecanique = calcul_puissance_mecanique or _fallback_puissance_mecanique
calcul_couple_alternateur = calcul_couple_alternateur or _fallback_couple_alternateur
calcul_echauffement_thermique = calcul_echauffement_thermique or _fallback_echauffement


# =============================================================================
# Types / helpers
# =============================================================================

ModeElectrique = Literal["triphase_ac", "monophase_ac", "dc"]
Connexion = Literal["Y", "Delta"]
ModePoles = Literal["poles", "pair_poles", "pole_pairs"]
Onde = Literal["sinus", "carree", "custom"]
StrategieAlternateur = Literal[
    "max_rendement",
    "min_pertes",
    "min_couple_moteur",
    "rpm_cible",
    "pareto",
]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _req_eta(name: str, eta: Any) -> float:
    v = _req_finite(name, eta)
    if not (0.0 < v <= 1.0):
        raise ValueError(f"{name} doit être dans (0,1] (reçu: {v}).")
    return v


def _req_int(name: str, x: Any, *, min_value: int = 0) -> int:
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


def _push_inconnue(rep: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rep.setdefault("inconnues", {}).setdefault(cat, []).append({"nom": str(nom), "raison": str(raison)})


def _dedup_inconnues(rep: Dict[str, Any]) -> None:
    inc = rep.setdefault("inconnues", {})
    for cat in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out = []
        for item in inc.setdefault(cat, []):
            if not isinstance(item, Mapping):
                continue
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append({"nom": key[0], "raison": key[1]})
        inc[cat] = out


def _merge_inconnues(dst: Dict[str, Any], src: Optional[Mapping[str, Any]], *, prefix: str) -> None:
    if not isinstance(src, Mapping):
        return
    inc = src.get("inconnues", {})
    if not isinstance(inc, Mapping):
        return
    for cat in ("impossibles", "partielles"):
        for item in inc.get(cat, []) or []:
            if isinstance(item, Mapping):
                _push_inconnue(dst, cat, f"{prefix} :: {item.get('nom', '')}", str(item.get("raison", "")))


def _safe_get(obj: Any, *path_or_names: str) -> Any:
    if obj is None:
        return None
    if len(path_or_names) == 1:
        names = path_or_names[0].split(".")
    else:
        names = list(path_or_names)
    cur = obj
    for name in names:
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(name)
        else:
            try:
                cur = getattr(cur, name)
            except Exception:
                return None
    return cur


def _coalesce(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _phase_line_from_connexion(connexion: Connexion) -> Tuple[float, float]:
    """
    Retourne :
    - V_ligne / V_phase
    - I_phase / I_ligne
    """
    if connexion == "Y":
        return math.sqrt(3.0), 1.0
    if connexion == "Delta":
        return 1.0, 1.0 / math.sqrt(3.0)
    raise ValueError("connexion doit être 'Y' ou 'Delta'.")


def _call_with_supported_kwargs(fn: Any, /, **kwargs: Any) -> Any:
    if not callable(fn):
        raise TypeError("fn doit être appelable.")
    try:
        sig = inspect.signature(fn)
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            return fn(**kwargs)
        return fn(**{k: v for k, v in kwargs.items() if k in sig.parameters})
    except (ValueError, TypeError):
        return fn(**kwargs)


def _to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return "inf" if obj > 0 else "-inf"
        return obj
    if is_dataclass(obj):
        return _to_jsonable(asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "tolist"):
        try:
            return _to_jsonable(obj.tolist())
        except Exception:
            pass
    if hasattr(obj, "item"):
        try:
            return _to_jsonable(obj.item())
        except Exception:
            pass
    return str(obj)


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | os.PathLike[str]) -> str:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


# =============================================================================
# Dataclasses système
# =============================================================================

@dataclass(frozen=True)
class PlageRegimeAlternateur:
    """Plage de fonctionnement optimale de l'alternateur."""
    rpm_cible: Optional[float] = None
    rpm_min_optimal: Optional[float] = None
    rpm_max_optimal: Optional[float] = None
    rpm_min_admissible: Optional[float] = None
    rpm_max_admissible: Optional[float] = None

    def analyser(self, rpm: Optional[float]) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "rpm": rpm,
            "rpm_cible": self.rpm_cible,
            "rpm_min_optimal": self.rpm_min_optimal,
            "rpm_max_optimal": self.rpm_max_optimal,
            "rpm_min_admissible": self.rpm_min_admissible,
            "rpm_max_admissible": self.rpm_max_admissible,
            "ok_admissible": None,
            "ok_optimal": None,
            "ecart_relatif_cible": None,
            "score_rpm": None,
            "inconnues": {"impossibles": [], "partielles": []},
        }
        if rpm is None:
            _push_inconnue(rep, "impossibles", "rpm_alternateur", "Requis pour vérifier la plage de régime.")
            _dedup_inconnues(rep)
            return rep
        n = _req_finite("rpm_alternateur", rpm)

        ok_adm = True
        if self.rpm_min_admissible is not None and n < self.rpm_min_admissible:
            ok_adm = False
        if self.rpm_max_admissible is not None and n > self.rpm_max_admissible:
            ok_adm = False
        if self.rpm_min_admissible is None and self.rpm_max_admissible is None:
            _push_inconnue(rep, "partielles", "plage_admissible", "rpm_min_admissible / rpm_max_admissible non fournis.")

        ok_opt = None
        if self.rpm_min_optimal is not None and self.rpm_max_optimal is not None:
            ok_opt = self.rpm_min_optimal <= n <= self.rpm_max_optimal
        else:
            _push_inconnue(rep, "partielles", "plage_optimale", "rpm_min_optimal / rpm_max_optimal non fournis.")

        score = 0.0
        if self.rpm_cible is not None and self.rpm_cible > 0:
            ec = abs(n - self.rpm_cible) / self.rpm_cible
            rep["ecart_relatif_cible"] = ec
            score += ec
        elif self.rpm_min_optimal is not None and self.rpm_max_optimal is not None:
            if n < self.rpm_min_optimal:
                score += (self.rpm_min_optimal - n) / max(self.rpm_min_optimal, 1e-12)
            elif n > self.rpm_max_optimal:
                score += (n - self.rpm_max_optimal) / max(self.rpm_max_optimal, 1e-12)
        else:
            score = None

        rep["ok_admissible"] = ok_adm
        rep["ok_optimal"] = ok_opt
        rep["score_rpm"] = score
        _dedup_inconnues(rep)
        return rep


@dataclass(frozen=True)
class InterfaceBusDC:
    """Contraintes côté bus DC / batterie."""
    tension_bus_dc_v: Optional[float] = None
    courant_bus_max_a: Optional[float] = None
    puissance_charge_max_w: Optional[float] = None
    rendement_redressement: Optional[float] = None
    rendement_charge: Optional[float] = None

    def extraire_tension(self, batterie: Any = None, moteur: Any = None) -> Optional[float]:
        return _coalesce(
            self.tension_bus_dc_v,
            _safe_get(batterie, "tension_charge_v"),
            _safe_get(batterie, "tension_nominale_v"),
            _safe_get(batterie, "tension_bus_v"),
            _safe_get(batterie, "bus_dc", "tension_v"),
            _safe_get(batterie, "entrees", "tension_nominale_v"),
            _safe_get(moteur, "tension_bus_v"),
            _safe_get(moteur, "entrees", "tension_bus_v"),
        )

    def verifier(self, *, puissance_bus_dc_w: Optional[float], tension_bus_dc_v: Optional[float], courant_bus_dc_a: Optional[float]) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "puissance_bus_dc_w": puissance_bus_dc_w,
            "tension_bus_dc_v": tension_bus_dc_v,
            "courant_bus_dc_a": courant_bus_dc_a,
            "courant_bus_max_a": self.courant_bus_max_a,
            "puissance_charge_max_w": self.puissance_charge_max_w,
            "ok_courant_bus": None,
            "ok_puissance_charge": None,
            "inconnues": {"impossibles": [], "partielles": []},
        }
        if courant_bus_dc_a is not None and self.courant_bus_max_a is not None:
            rep["ok_courant_bus"] = abs(float(courant_bus_dc_a)) <= self.courant_bus_max_a
        elif courant_bus_dc_a is None:
            _push_inconnue(rep, "partielles", "courant_bus_dc_a", "Calculable si puissance bus et tension bus sont connues.")
        else:
            _push_inconnue(rep, "partielles", "courant_bus_max_a", "Requis pour vérifier la limite de courant du bus/BMS.")

        if puissance_bus_dc_w is not None and self.puissance_charge_max_w is not None:
            rep["ok_puissance_charge"] = abs(float(puissance_bus_dc_w)) <= self.puissance_charge_max_w
        elif self.puissance_charge_max_w is None:
            _push_inconnue(rep, "partielles", "puissance_charge_max_w", "Requis pour vérifier la limite de charge batterie/BMS.")
        _dedup_inconnues(rep)
        return rep


@dataclass
class Alternateur:
    """
    Alternateur calculatoire intégré.

    Il accepte les appels :
    - analyser_point_de_fonctionnement(...)
    - analyser_pour_bus_dc(...)
    - analyser_depuis_boite_crabots(...)
    - comparer_rapports_boite(...)
    """

    # Cinématique / topologie
    nombre_poles: Optional[int] = None
    mode_poles: ModePoles = "poles"
    connexion: Connexion = "Y"
    plage_regime: PlageRegimeAlternateur = field(default_factory=PlageRegimeAlternateur)

    # Enroulement / magnétisme
    nombre_spires_serie: Optional[int] = None
    facteur_enroulement: Optional[float] = None
    flux_max_pole_wb: Optional[float] = None
    induction_gap_t: Optional[float] = None
    aire_pole_m2: Optional[float] = None
    onde: Onde = "sinus"
    constante_custom: Optional[float] = None

    # Sortie électrique
    facteur_puissance_defaut: float = 1.0
    courant_max_ligne_a: Optional[float] = None
    courant_max_phase_a: Optional[float] = None
    tension_max_ligne_v: Optional[float] = None

    # Cuivre
    resistance_phase_ohm: Optional[float] = None
    resistivite_ohm_m: Optional[float] = None
    longueur_fil_m: Optional[float] = None
    section_fil_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_ref_c: float = 20.0
    coef_temperature: float = 0.00393

    # Fer / Steinmetz
    k_h: Optional[float] = None
    k_e: Optional[float] = None
    exposant_steinmetz: Optional[float] = None
    induction_max_t: Optional[float] = None
    eddy_freq_exp: float = 2.0
    eddy_induction_exp: float = 2.0
    masse_fer_kg: Optional[float] = None
    volume_fer_m3: Optional[float] = None

    # Pertes / rendement
    pertes_fixes_w: float = 0.0
    pertes_mecaniques_w: Optional[float] = None
    rendement_alternateur_impose: Optional[float] = None

    # Redressement / bus DC
    interface_bus_dc: InterfaceBusDC = field(default_factory=InterfaceBusDC)

    # Thermique
    resistance_thermique_k_w: Optional[float] = None
    temperature_ambiante_c: float = 20.0
    offset_temperature_c: float = 0.0
    temperature_max_admissible_c: Optional[float] = None

    # Dimensionnement mécanique
    diametre_arbre_m: Optional[float] = None
    tau_admissible_pa: Optional[float] = None
    charge_radiale_roulement_n: Optional[float] = None
    facteur_charge_roulement: float = 1.0
    capacite_dynamique_roulement_n: Optional[float] = None

    # Refroidissement / excitation
    surface_echange_m2: Optional[float] = None
    coeff_convection_w_m2k: Optional[float] = None
    autoriser_estimation_convection_proxy: bool = False
    nombre_spires_excitation: Optional[int] = None
    courant_excitation_a: Optional[float] = None
    resistance_excitation_ohm: Optional[float] = None
    longueur_fil_excitation_m: Optional[float] = None
    section_fil_excitation_m2: Optional[float] = None
    resistivite_excitation_ohm_m: Optional[float] = None

    # Pièces externes optionnelles
    piece_rotor: Optional[Any] = None
    piece_stator: Optional[Any] = None
    piece_arbre: Optional[Any] = None
    piece_carter: Optional[Any] = None
    piece_ventilateur: Optional[Any] = None
    piece_bobine_excite: Optional[Any] = None
    piece_roulement: Optional[Any] = None

    clamp_non_negative: bool = True

    def __post_init__(self) -> None:
        _req_finite("pertes_fixes_w", self.pertes_fixes_w)
        _req_finite("temperature_ambiante_c", self.temperature_ambiante_c)
        _req_finite("offset_temperature_c", self.offset_temperature_c)
        _req_finite("facteur_puissance_defaut", self.facteur_puissance_defaut)
        if self.nombre_poles is not None:
            _req_int("nombre_poles", self.nombre_poles, min_value=1)
        if self.nombre_spires_serie is not None:
            _req_int("nombre_spires_serie", self.nombre_spires_serie, min_value=0)
        if self.rendement_alternateur_impose is not None:
            _req_eta("rendement_alternateur_impose", self.rendement_alternateur_impose)
        if self.masse_fer_kg is not None and self.volume_fer_m3 is not None:
            raise ValueError("Fournis soit masse_fer_kg, soit volume_fer_m3, pas les deux.")
        if self.connexion not in ("Y", "Delta"):
            raise ValueError("connexion doit être 'Y' ou 'Delta'.")

    # ------------------------------------------------------------------
    # Analyse principale
    # ------------------------------------------------------------------
    def analyser_point_de_fonctionnement(
        self,
        *,
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        mode_electrique: ModeElectrique = "triphase_ac",
        tension_v: Optional[float] = None,
        courant_a: Optional[float] = None,
        facteur_puissance: Optional[float] = None,
        entree_puissance_ac: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
        courant_est_ligne: bool = True,
        puissance_electrique_cible_w: Optional[float] = None,
        courant_phase_rms_stator_a: Optional[float] = None,
        energie_a_recharger_kwh: Optional[float] = None,
        rendement_charge: Optional[float] = None,
        rendement_redressement: Optional[float] = None,
        source_appel: str = "point",
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "composant": "alternateur",
            "source_appel": source_appel,
            "entrees": {},
            "cinematique": {},
            "plage_regime": {},
            "electromagnetique": {},
            "sortie_electrique": {},
            "pertes": {},
            "rendement": {},
            "mecanique": {},
            "thermique": {},
            "charge_batterie": {},
            "validations": {},
            "resultats": {},
            "pieces": {},
            "imports": {"erreurs_optionnelles": dict(_IMPORT_ERRORS)},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        pf = self.facteur_puissance_defaut if facteur_puissance is None else facteur_puissance
        rep["entrees"].update({
            "vitesse_rotation_rpm": vitesse_rotation_rpm,
            "vitesse_angulaire_rad_s": vitesse_angulaire_rad_s,
            "mode_electrique": mode_electrique,
            "tension_v": tension_v,
            "courant_a": courant_a,
            "facteur_puissance": pf,
            "entree_puissance_ac": entree_puissance_ac,
            "courant_est_ligne": courant_est_ligne,
            "puissance_electrique_cible_w": puissance_electrique_cible_w,
            "connexion": self.connexion,
            "nombre_poles": self.nombre_poles,
            "rendement_redressement": rendement_redressement,
        })

        # 1) Vitesse mécanique
        omega: Optional[float] = None
        rpm: Optional[float] = None
        if vitesse_angulaire_rad_s is not None:
            omega = calcul_vitesse_angulaire(vitesse_angulaire_rad_s, input_unite="rad_s")
            rpm = (omega * 60.0) / (2.0 * math.pi)
        elif vitesse_rotation_rpm is not None:
            rpm = _req_finite("vitesse_rotation_rpm", vitesse_rotation_rpm)
            omega = calcul_vitesse_angulaire(rpm, input_unite="rpm")
        else:
            _push_inconnue(rep, "impossibles", "vitesse_rotation_rpm ou vitesse_angulaire_rad_s", "Vitesse requise pour fréquence, puissance mécanique et couple.")

        rep["cinematique"]["vitesse_rotation_rpm"] = rpm
        rep["cinematique"]["vitesse_angulaire_rad_s"] = omega
        rep["plage_regime"] = self.plage_regime.analyser(rpm)
        _merge_inconnues(rep, rep["plage_regime"], prefix="plage_regime")

        # 2) Fréquence synchrone
        frequence_hz: Optional[float] = None
        if rpm is not None and self.nombre_poles is not None:
            frequence_hz = calcul_frequence_synchrone(
                vitesse_rotation_tr_min=rpm,
                nombre_poles=self.nombre_poles,
                mode_poles=self.mode_poles,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(rep, "partielles", "frequence_synchrone_hz", "Calculable si vitesse et nombre_poles sont fournis.")
        rep["cinematique"]["frequence_synchrone_hz"] = frequence_hz

        # 3) Flux / FEM
        flux_wb = self.flux_max_pole_wb
        if flux_wb is None and self.induction_gap_t is not None and self.aire_pole_m2 is not None:
            flux_wb = calcul_flux_pole(
                induction_gap_t=self.induction_gap_t,
                aire_pole_m2=self.aire_pole_m2,
                flux_model="B*A",
            )
        elif flux_wb is None:
            _push_inconnue(rep, "partielles", "flux_max_pole_wb", "Fournir flux_max_pole_wb ou induction_gap_t + aire_pole_m2.")

        fem_phase_v: Optional[float] = None
        fem_ligne_v: Optional[float] = None
        if frequence_hz is not None and self.nombre_spires_serie is not None and flux_wb is not None and self.facteur_enroulement is not None:
            fem_phase_v = calcul_fem_induite(
                frequence_hz=frequence_hz,
                nombre_spires_serie=self.nombre_spires_serie,
                flux_max_pole_wb=flux_wb,
                facteur_enroulement_kw=self.facteur_enroulement,
                onde=self.onde,
                constante_custom=self.constante_custom,
                clamp_non_negative=True,
            )
            k_vll, _ = _phase_line_from_connexion(self.connexion)
            fem_ligne_v = fem_phase_v * k_vll
        else:
            _push_inconnue(rep, "partielles", "fem_induite", "Calculable si fréquence, spires, flux et facteur d'enroulement sont fournis.")

        rep["electromagnetique"].update({
            "flux_max_pole_wb": flux_wb,
            "fem_phase_rms_v": fem_phase_v,
            "fem_ligne_ligne_rms_v": fem_ligne_v,
            "nombre_spires_serie": self.nombre_spires_serie,
            "facteur_enroulement": self.facteur_enroulement,
            "onde": self.onde,
        })

        # 4) Puissance électrique utile
        P_out: Optional[float] = puissance_electrique_cible_w
        V_sortie: Optional[float] = None if tension_v is None else _req_finite("tension_v", tension_v)
        I_ligne_ou_dc: Optional[float] = None if courant_a is None else _req_finite("courant_a", courant_a)

        if P_out is None and V_sortie is not None and I_ligne_ou_dc is not None:
            if mode_electrique == "triphase_ac":
                P_out = calcul_puissance_triphase(
                    tension_composee=V_sortie,
                    courant_ligne=I_ligne_ou_dc,
                    facteur_puissance=pf,
                    entree=entree_puissance_ac,
                    connexion=self.connexion,
                    clamp_non_negative=self.clamp_non_negative,
                )
            elif mode_electrique == "monophase_ac":
                P_out = calcul_puissance_monophase(
                    tension=V_sortie,
                    courant=I_ligne_ou_dc,
                    facteur_puissance=pf,
                    clamp_non_negative=self.clamp_non_negative,
                )
            elif mode_electrique == "dc":
                P_out = calcul_puissance_dc(
                    tension_dc=V_sortie,
                    courant_dc=I_ligne_ou_dc,
                    clamp_non_negative=self.clamp_non_negative,
                )
            else:
                raise ValueError("mode_electrique doit être 'triphase_ac', 'monophase_ac' ou 'dc'.")
        elif P_out is None:
            _push_inconnue(rep, "impossibles", "puissance_electrique_sortie_w", "Fournir puissance_electrique_cible_w ou tension_v + courant_a.")

        if P_out is not None:
            P_out = _req_finite("puissance_electrique_sortie_w", P_out)

        rep["sortie_electrique"].update({
            "mode": mode_electrique,
            "tension_v": V_sortie,
            "courant_a": I_ligne_ou_dc,
            "facteur_puissance": pf,
            "puissance_utile_w": P_out,
        })

        # 5) Courant de phase stator
        courant_phase: Optional[float] = courant_phase_rms_stator_a
        if courant_phase is None and I_ligne_ou_dc is not None and mode_electrique == "triphase_ac":
            _, k_iph_from_il = _phase_line_from_connexion(self.connexion)
            courant_phase = I_ligne_ou_dc * k_iph_from_il if courant_est_ligne else I_ligne_ou_dc
        elif courant_phase is None and I_ligne_ou_dc is not None and mode_electrique == "monophase_ac":
            courant_phase = I_ligne_ou_dc
        elif courant_phase is None and P_out is not None and V_sortie is not None and V_sortie != 0.0:
            if mode_electrique == "dc":
                courant_phase = None
            elif mode_electrique == "triphase_ac":
                I_est_ligne = abs(P_out) / max(math.sqrt(3.0) * abs(V_sortie) * max(abs(_req_finite("facteur_puissance", pf)), 1e-12), 1e-12)
                _, k_iph_from_il = _phase_line_from_connexion(self.connexion)
                courant_phase = I_est_ligne * k_iph_from_il
            elif mode_electrique == "monophase_ac":
                courant_phase = abs(P_out) / max(abs(V_sortie) * max(abs(_req_finite("facteur_puissance", pf)), 1e-12), 1e-12)

        rep["sortie_electrique"]["courant_phase_rms_stator_a"] = courant_phase

        # 6) Limites tension / courant
        if fem_ligne_v is not None and V_sortie is not None:
            rep["validations"]["ok_fem_vs_tension_sortie"] = fem_ligne_v >= abs(V_sortie)
            rep["validations"]["marge_fem_v"] = fem_ligne_v - abs(V_sortie)
        elif V_sortie is not None:
            _push_inconnue(rep, "partielles", "validation_fem_vs_tension", "Calculable si FEM ligne est calculée.")

        if self.courant_max_ligne_a is not None and I_ligne_ou_dc is not None:
            rep["validations"]["ok_courant_ligne"] = abs(I_ligne_ou_dc) <= self.courant_max_ligne_a
        elif self.courant_max_ligne_a is None:
            _push_inconnue(rep, "partielles", "courant_max_ligne_a", "Requis pour vérifier le courant admissible ligne/DC.")

        if self.courant_max_phase_a is not None and courant_phase is not None:
            rep["validations"]["ok_courant_phase"] = abs(courant_phase) <= self.courant_max_phase_a
        elif self.courant_max_phase_a is None and mode_electrique != "dc":
            _push_inconnue(rep, "partielles", "courant_max_phase_a", "Requis pour vérifier le courant admissible des enroulements.")

        if self.tension_max_ligne_v is not None and fem_ligne_v is not None:
            rep["validations"]["ok_tension_max_ligne"] = abs(fem_ligne_v) <= self.tension_max_ligne_v

        # 7) Résistance phase + pertes cuivre
        R_phase = self.resistance_phase_ohm
        if R_phase is None and self.resistivite_ohm_m is not None and self.longueur_fil_m is not None and self.section_fil_m2 is not None:
            R_phase = calcul_resistance_enroulement(
                resistivite=self.resistivite_ohm_m,
                longueur_fil=self.longueur_fil_m,
                section_fil=self.section_fil_m2,
                temperature_c=self.temperature_c,
                temperature_ref_c=self.temperature_ref_c,
                coef_temperature=self.coef_temperature,
                clamp_non_negative=True,
            )
        elif R_phase is None:
            _push_inconnue(rep, "partielles", "resistance_phase_ohm", "Fournir R_phase ou résistivité + longueur_fil + section_fil.")
        if R_phase is not None:
            R_phase = _req_pos("resistance_phase_ohm", R_phase, strict=False)

        P_cu: Optional[float] = None
        if R_phase is not None and courant_phase is not None:
            if mode_electrique == "triphase_ac":
                P_cu = calcul_pertes_cuivre_triphase(
                    courant_phase=courant_phase,
                    resistance_phase=R_phase,
                    courant_type="rms",
                    connexion=self.connexion,
                    courant_est_ligne=False,
                    clamp_non_negative=True,
                )
            else:
                P_cu = calcul_pertes_cuivre_phase(
                    courant=courant_phase,
                    resistance=R_phase,
                    courant_type="rms",
                    clamp_non_negative=True,
                )
        elif mode_electrique != "dc":
            _push_inconnue(rep, "partielles", "pertes_cuivre_w", "Calculables si courant phase et résistance phase sont connus.")
        elif mode_electrique == "dc":
            _push_inconnue(rep, "partielles", "pertes_cuivre_stator_w", "En sortie DC, fournir courant_phase_rms_stator_a ou modèle redresseur pour remonter le courant stator.")

        rep["pertes"].update({
            "resistance_phase_ohm": R_phase,
            "pertes_cuivre_w": P_cu,
        })

        # 8) Pertes fer
        P_fe: Optional[float] = None
        if frequence_hz is not None and self.induction_max_t is not None and self.k_h is not None and self.k_e is not None and self.exposant_steinmetz is not None:
            d_fe = calcul_pertes_fer_steinmetz(
                k_h=self.k_h,
                frequence=frequence_hz,
                induction_max=self.induction_max_t,
                exposant_steinmetz=self.exposant_steinmetz,
                k_e=self.k_e,
                eddy_freq_exp=self.eddy_freq_exp,
                eddy_induction_exp=self.eddy_induction_exp,
                masse_kg=self.masse_fer_kg,
                volume_m3=self.volume_fer_m3,
                return_details=True,
                clamp_non_negative=True,
            )
            P_fe = float(d_fe["P_total"])
            rep["pertes"]["detail_pertes_fer"] = d_fe
        else:
            _push_inconnue(rep, "partielles", "pertes_fer_w", "Calculables si fréquence, induction_max, k_h, k_e et exposant Steinmetz sont fournis.")
        rep["pertes"]["pertes_fer_w"] = P_fe

        # 9) Pertes excitation
        P_exc: Optional[float] = None
        R_exc = self.resistance_excitation_ohm
        if R_exc is None and self.resistivite_excitation_ohm_m is not None and self.longueur_fil_excitation_m is not None and self.section_fil_excitation_m2 is not None:
            R_exc = calcul_resistance_enroulement(
                resistivite=self.resistivite_excitation_ohm_m,
                longueur_fil=self.longueur_fil_excitation_m,
                section_fil=self.section_fil_excitation_m2,
                temperature_c=self.temperature_c,
                temperature_ref_c=self.temperature_ref_c,
                coef_temperature=self.coef_temperature,
                clamp_non_negative=True,
            )
        if R_exc is not None and self.courant_excitation_a is not None:
            P_exc = float(self.courant_excitation_a) ** 2 * float(R_exc)
        elif self.courant_excitation_a is not None:
            _push_inconnue(rep, "partielles", "pertes_excitation_w", "Calculables si résistance ou géométrie de la bobine d'excitation est fournie.")

        P_mec_loss = self.pertes_mecaniques_w
        if P_mec_loss is None:
            _push_inconnue(rep, "partielles", "pertes_mecaniques_w", "Frottements/ventilation non fournis : non inclus dans les pertes connues.")

        rep["pertes"]["pertes_excitation_w"] = P_exc
        rep["pertes"]["pertes_mecaniques_w"] = P_mec_loss
        rep["pertes"]["pertes_fixes_w"] = float(self.pertes_fixes_w)

        pertes_connues = [float(self.pertes_fixes_w)]
        for p in (P_cu, P_fe, P_exc, P_mec_loss):
            if p is not None:
                pertes_connues.append(float(p))

        P_pertes_connues = sum(pertes_connues)
        pertes_incompletes = any(p is None for p in (P_cu, P_fe, P_mec_loss))
        rep["pertes"]["pertes_connues_total_w"] = P_pertes_connues
        rep["pertes"]["pertes_totales_W"] = P_pertes_connues  # alias compatibilité
        rep["pertes"]["P_pertes_totales_W"] = P_pertes_connues  # alias boîte à crabots
        rep["pertes"]["pertes_connues_incompletes"] = bool(pertes_incompletes)
        if pertes_incompletes:
            rep["notes_modele"].append("Les pertes totales réelles ne sont pas conclues : pertes cuivre, fer ou mécaniques manquantes.")

        # 10) Rendement / puissance mécanique / couple
        eta_impose = self.rendement_alternateur_impose
        eta_sur_pertes_connues: Optional[float] = None
        if P_out is not None:
            eta_sur_pertes_connues = calcul_rendement_alternateur(
                puissance_utile_out=P_out,
                liste_pertes=pertes_connues,
                clamp_0_1=True,
                return_details=False,
            )

        eta_dimensionnant = eta_impose
        if eta_dimensionnant is None and not pertes_incompletes and eta_sur_pertes_connues is not None:
            eta_dimensionnant = eta_sur_pertes_connues
            rep["notes_modele"].append("Rendement dimensionnant pris sur pertes calculées car toutes les pertes principales disponibles.")
        elif eta_dimensionnant is None:
            _push_inconnue(rep, "partielles", "rendement_alternateur_impose", "Requis pour conclure la puissance mécanique et le couple dimensionnants si les pertes sont incomplètes.")

        rep["rendement"].update({
            "rendement_impose": eta_impose,
            "eta_sur_pertes_connues": eta_sur_pertes_connues,
            "eta_sur_pertes_connues_est_partiel": bool(pertes_incompletes),
            "eta_dimensionnant_utilise": eta_dimensionnant,
        })

        P_meca_sur_pertes_connues: Optional[float] = None
        couple_sur_pertes_connues: Optional[float] = None
        if P_out is not None:
            P_meca_sur_pertes_connues = P_out + P_pertes_connues
            rep["mecanique"]["puissance_mecanique_sur_pertes_connues_w"] = P_meca_sur_pertes_connues
            if omega is not None and abs(omega) > 1e-12:
                couple_sur_pertes_connues = P_meca_sur_pertes_connues / abs(omega)
                rep["mecanique"]["couple_sur_pertes_connues_nm"] = couple_sur_pertes_connues

        P_meca_dim: Optional[float] = None
        couple_dim: Optional[float] = None
        if P_out is not None and eta_dimensionnant is not None:
            P_meca_dim = calcul_puissance_mecanique(
                puissance_electrique_cible=P_out,
                rendement_alternateur=eta_dimensionnant,
                pertes_fixes_w=0.0,
                clamp_non_negative=self.clamp_non_negative,
                mode_signe="abs" if self.clamp_non_negative else "conserver",
            )
            # Si le rendement imposé englobe tout, on n'ajoute pas les pertes connues une seconde fois.
            rep["mecanique"]["puissance_mecanique_dimensionnante_w"] = P_meca_dim
            if omega is not None and abs(omega) > 1e-12:
                couple_dim = calcul_couple_alternateur(
                    puissance_electrique_cible=P_out,
                    rendement_alternateur=eta_dimensionnant,
                    vitesse_angulaire=omega,
                    pertes_fixes_w=0.0,
                    clamp_non_negative=self.clamp_non_negative,
                    mode_signe="abs_omega" if self.clamp_non_negative else "conserver",
                )
                rep["mecanique"]["couple_mecanique_dimensionnant_nm"] = couple_dim
            elif omega is None:
                _push_inconnue(rep, "partielles", "couple_mecanique_dimensionnant_nm", "Calculable si vitesse angulaire disponible.")

        # 11) Thermique
        if self.resistance_thermique_k_w is not None:
            delta_t_connues = calcul_echauffement_thermique(
                puissance_pertes_totale=P_pertes_connues,
                resistance_thermique=self.resistance_thermique_k_w,
                offset_temperature=self.offset_temperature_c,
                clamp_non_negative=True,
            )
            temperature_estimee = self.temperature_ambiante_c + delta_t_connues
            rep["thermique"].update({
                "resistance_thermique_k_w": self.resistance_thermique_k_w,
                "echauffement_sur_pertes_connues_k": delta_t_connues,
                "temperature_estimee_sur_pertes_connues_c": temperature_estimee,
                "temperature_max_admissible_c": self.temperature_max_admissible_c,
            })
            if self.temperature_max_admissible_c is not None:
                rep["thermique"]["ok_temperature_sur_pertes_connues"] = temperature_estimee <= self.temperature_max_admissible_c
        else:
            _push_inconnue(rep, "partielles", "resistance_thermique_k_w", "Requise pour évaluer l'échauffement.")

        # 12) Charge batterie optionnelle
        rendement_charge_eff = _coalesce(rendement_charge, self.interface_bus_dc.rendement_charge)
        if calcul_temps_charge is not None and energie_a_recharger_kwh is not None and P_out is not None and P_out > 0.0 and rendement_charge_eff is not None:
            try:
                P_kw = P_out / 1000.0
                rep["charge_batterie"]["temps_charge_h"] = calcul_temps_charge(
                    energie_utile_kwh=energie_a_recharger_kwh,
                    puissance_charge_kw=P_kw,
                    rendement_charge=rendement_charge_eff,
                )
                rep["charge_batterie"]["energie_a_recharger_kwh"] = energie_a_recharger_kwh
                rep["charge_batterie"]["puissance_charge_kw"] = P_kw
                rep["charge_batterie"]["rendement_charge"] = rendement_charge_eff
            except Exception as exc:
                rep["charge_batterie"]["erreur_calcul_temps_charge"] = str(exc)
        elif energie_a_recharger_kwh is not None:
            _push_inconnue(rep, "partielles", "temps_charge_h", "Calculable si puissance électrique > 0, rendement_charge et module calcul_temps_charge disponibles.")

        # 13) Exigences système
        rep["mecanique"]["exigences_pour_boite_crabots"] = {
            "rpm_alternateur": rpm,
            "couple_alternateur_dimensionnant_nm": couple_dim,
            "couple_alternateur_sur_pertes_connues_nm": couple_sur_pertes_connues,
            "puissance_mecanique_dimensionnante_w": P_meca_dim,
            "puissance_mecanique_sur_pertes_connues_w": P_meca_sur_pertes_connues,
        }
        rep["sortie_electrique"]["exigences_pour_bus_dc_batterie"] = {
            "puissance_utile_w": P_out,
            "tension_v": V_sortie,
            "courant_a": I_ligne_ou_dc,
            "rendement_redressement": rendement_redressement,
        }

        # 14) Compatibilité attendue par la boîte à crabots
        eta_total = eta_dimensionnant if eta_dimensionnant is not None else eta_sur_pertes_connues
        P_meca_compat = P_meca_dim if P_meca_dim is not None else P_meca_sur_pertes_connues
        couple_compat = couple_dim if couple_dim is not None else couple_sur_pertes_connues

        rep["resultats"].update({
            "P_out_W": P_out,
            "eta_total": eta_total,
            "P_mecanique_W": P_meca_compat,
            "couple_mecanique_Nm": couple_compat,
            "vitesse_rotation_rpm": rpm,
            "omega_rad_s": omega,
            "frequence_hz": frequence_hz,
            "fem_phase_rms_v": fem_phase_v,
            "fem_ligne_ligne_rms_v": fem_ligne_v,
            "pertes_totales_connues_W": P_pertes_connues,
            "pertes_incompletes": pertes_incompletes,
            "ok_rpm_optimal": rep["plage_regime"].get("ok_optimal"),
            "score_rpm": rep["plage_regime"].get("score_rpm"),
        })

        # 15) Pièces
        contexte = {
            "rpm": rpm,
            "omega": omega,
            "frequence_hz": frequence_hz,
            "P_out": P_out,
            "eta": eta_dimensionnant,
            "eta_sur_pertes_connues": eta_sur_pertes_connues,
            "P_pertes_connues": P_pertes_connues,
            "P_cu": P_cu,
            "P_fe": P_fe,
            "P_exc": P_exc,
            "P_mec_loss": P_mec_loss,
            "R_phase": R_phase,
            "courant_phase": courant_phase,
            "flux_wb": flux_wb,
            "fem_phase_v": fem_phase_v,
            "fem_ligne_v": fem_ligne_v,
            "couple_dimensionnant": couple_compat,
        }
        rep["pieces"] = self._analyser_pieces(contexte)
        for nom, piece_rep in rep["pieces"].items():
            _merge_inconnues(rep, piece_rep if isinstance(piece_rep, Mapping) else None, prefix=f"pieces.{nom}")

        # 16) OK global : seulement sur validations explicitement calculées
        rep["validations"]["ok_global_sur_donnees_connues"] = self._ok_global(rep)
        _dedup_inconnues(rep)
        return _to_jsonable(rep)

    # ------------------------------------------------------------------
    # Intégration bus DC
    # ------------------------------------------------------------------
    def analyser_pour_bus_dc(
        self,
        *,
        puissance_bus_dc_w: float,
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Any = None,
        moteur: Any = None,
        energie_a_recharger_kwh: Optional[float] = None,
        rendement_charge: Optional[float] = None,
        rendement_redressement: Optional[float] = None,
    ) -> Dict[str, Any]:
        Pdc = _req_finite("puissance_bus_dc_w", puissance_bus_dc_w)
        Vdc = _coalesce(tension_bus_dc_v, self.interface_bus_dc.extraire_tension(batterie=batterie, moteur=moteur))
        Idc: Optional[float] = None
        if Vdc is not None:
            Vdc = _req_pos("tension_bus_dc_v", Vdc, strict=True)
            Idc = Pdc / Vdc

        eta_rect = _coalesce(rendement_redressement, self.interface_bus_dc.rendement_redressement)
        P_alt_sortie = Pdc
        redressement_est_borne = True
        if eta_rect is not None:
            eta_rect = _req_eta("rendement_redressement", eta_rect)
            P_alt_sortie = Pdc / eta_rect
            redressement_est_borne = False

        rep: Dict[str, Any] = {
            "composant": "alternateur_bus_dc",
            "entrees": {
                "puissance_bus_dc_w": Pdc,
                "tension_bus_dc_v": Vdc,
                "courant_bus_dc_a": Idc,
                "energie_a_recharger_kwh": energie_a_recharger_kwh,
                "rendement_redressement": eta_rect,
                "puissance_sortie_alternateur_avant_redressement_w": P_alt_sortie,
            },
            "interface_bus_dc": {},
            "alternateur": {},
            "resultats": {},
            "pertes": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        if Vdc is None:
            _push_inconnue(rep, "partielles", "tension_bus_dc_v", "Fournir tension_bus_dc_v ou un objet batterie/moteur contenant la tension nominale.")
        if redressement_est_borne:
            _push_inconnue(rep, "partielles", "rendement_redressement", "Non fourni : P_alt_sortie = P_bus_dc est une borne minimale électrique, pas la puissance AC réelle avant redressement.")
            rep["notes_modele"].append("Sans rendement de redressement, le calcul utilise une borne minimale électrique côté alternateur.")

        rep["interface_bus_dc"] = self.interface_bus_dc.verifier(
            puissance_bus_dc_w=Pdc,
            tension_bus_dc_v=Vdc,
            courant_bus_dc_a=Idc,
        )
        _merge_inconnues(rep, rep["interface_bus_dc"], prefix="interface_bus_dc")

        alt = self.analyser_point_de_fonctionnement(
            vitesse_rotation_rpm=vitesse_rotation_rpm,
            vitesse_angulaire_rad_s=vitesse_angulaire_rad_s,
            mode_electrique="dc",
            tension_v=Vdc,
            courant_a=Idc,
            puissance_electrique_cible_w=P_alt_sortie,
            energie_a_recharger_kwh=energie_a_recharger_kwh,
            rendement_charge=_coalesce(rendement_charge, self.interface_bus_dc.rendement_charge),
            rendement_redressement=eta_rect,
            source_appel="bus_dc",
        )
        rep["alternateur"] = alt
        _merge_inconnues(rep, alt, prefix="alternateur")

        # Aliases haut niveau pour extraction simple par la boîte.
        alt_res = alt.get("resultats", {}) if isinstance(alt, Mapping) else {}
        alt_pertes = alt.get("pertes", {}) if isinstance(alt, Mapping) else {}
        rep["resultats"] = {
            "P_out_W": alt_res.get("P_out_W"),
            "P_bus_dc_W": Pdc,
            "eta_total": alt_res.get("eta_total"),
            "P_mecanique_W": alt_res.get("P_mecanique_W"),
            "couple_mecanique_Nm": alt_res.get("couple_mecanique_Nm"),
            "vitesse_rotation_rpm": alt_res.get("vitesse_rotation_rpm"),
            "frequence_hz": alt_res.get("frequence_hz"),
            "courant_bus_dc_a": Idc,
            "tension_bus_dc_v": Vdc,
        }
        rep["pertes"] = {
            "P_pertes_totales_W": alt_pertes.get("P_pertes_totales_W"),
            "pertes_incompletes": alt_res.get("pertes_incompletes"),
        }
        _dedup_inconnues(rep)
        return _to_jsonable(rep)

    # ------------------------------------------------------------------
    # Intégration boîte à crabots
    # ------------------------------------------------------------------
    def analyser_depuis_boite_crabots(
        self,
        *,
        rpm_moteur: float,
        rapport_boite: float,
        puissance_bus_dc_w: float,
        rendement_boite: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Any = None,
        moteur: Any = None,
        energie_a_recharger_kwh: Optional[float] = None,
        rendement_charge: Optional[float] = None,
        rendement_redressement: Optional[float] = None,
    ) -> Dict[str, Any]:
        n_moteur = _req_pos("rpm_moteur", rpm_moteur, strict=True)
        ratio = _req_pos("rapport_boite", rapport_boite, strict=True)
        n_alt = n_moteur * ratio

        rep = self.analyser_pour_bus_dc(
            puissance_bus_dc_w=puissance_bus_dc_w,
            vitesse_rotation_rpm=n_alt,
            tension_bus_dc_v=tension_bus_dc_v,
            batterie=batterie,
            moteur=moteur,
            energie_a_recharger_kwh=energie_a_recharger_kwh,
            rendement_charge=rendement_charge,
            rendement_redressement=rendement_redressement,
        )
        rep.setdefault("chaine_moteur_boite_alternateur", {})
        res = rep.get("resultats", {}) if isinstance(rep, Mapping) else {}
        T_alt = _safe_float(res.get("couple_mecanique_Nm"))
        P_meca_alt = _safe_float(res.get("P_mecanique_W"))

        eta_b = None
        if rendement_boite is not None:
            eta_b = _req_eta("rendement_boite", rendement_boite)

        T_moteur_req = None
        if T_alt is not None:
            T_moteur_req = (T_alt * ratio) / eta_b if eta_b is not None else (T_alt * ratio)

        P_moteur_req = None
        if P_meca_alt is not None:
            P_moteur_req = P_meca_alt / eta_b if eta_b is not None else P_meca_alt

        rep["chaine_moteur_boite_alternateur"] = {
            "rpm_moteur": n_moteur,
            "rapport_boite": ratio,
            "rpm_alternateur": n_alt,
            "rendement_boite": eta_b,
            "couple_alternateur_nm": T_alt,
            "puissance_mecanique_alternateur_w": P_meca_alt,
            "couple_moteur_requis_nm": T_moteur_req,
            "puissance_moteur_requise_w": P_moteur_req,
        }
        if eta_b is None:
            _push_inconnue(rep, "partielles", "rendement_boite", "Non fourni : couple/puissance moteur remontés hors pertes boîte.")
        _dedup_inconnues(rep)
        return _to_jsonable(rep)

    def comparer_rapports_boite(
        self,
        *,
        rpm_moteur: float,
        rapports: Sequence[float],
        puissance_bus_dc_w: float,
        rendement_boite: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Any = None,
        moteur: Any = None,
        strategie: StrategieAlternateur = "pareto",
        rendement_redressement: Optional[float] = None,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "composant": "alternateur_comparaison_rapports",
            "entrees": {
                "rpm_moteur": rpm_moteur,
                "rapports": list(rapports),
                "puissance_bus_dc_w": puissance_bus_dc_w,
                "rendement_boite": rendement_boite,
                "strategie": strategie,
            },
            "candidats": [],
            "selection": None,
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        if not rapports:
            _push_inconnue(rep, "impossibles", "rapports", "Liste de rapports vide.")
            return rep

        for r in rapports:
            if not _is_finite(r) or float(r) <= 0:
                rep["notes_modele"].append(f"Rapport ignoré : {r!r}")
                continue
            cand = self.analyser_depuis_boite_crabots(
                rpm_moteur=rpm_moteur,
                rapport_boite=float(r),
                puissance_bus_dc_w=puissance_bus_dc_w,
                rendement_boite=rendement_boite,
                tension_bus_dc_v=tension_bus_dc_v,
                batterie=batterie,
                moteur=moteur,
                rendement_redressement=rendement_redressement,
            )
            resume = self._extraire_resume_candidat(cand)
            cand_light = {
                "rapport": float(r),
                "resume": resume,
                "rapport_complet": cand,
            }
            rep["candidats"].append(cand_light)
            _merge_inconnues(rep, cand if isinstance(cand, Mapping) else None, prefix=f"rapport_{r}")

        if not rep["candidats"]:
            _push_inconnue(rep, "impossibles", "candidats", "Aucun rapport valide.")
            _dedup_inconnues(rep)
            return rep

        rep["selection"] = self._selectionner_candidat(rep["candidats"], strategie=strategie)
        _dedup_inconnues(rep)
        return _to_jsonable(rep)

    # ------------------------------------------------------------------
    # Pièces : analyse interne robuste
    # ------------------------------------------------------------------
    def _analyser_pieces(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        pieces: Dict[str, Any] = {
            "rotor": self._piece_rotor(ctx),
            "stator": self._piece_stator(ctx),
            "arbre": self._piece_arbre(ctx),
            "carter": self._piece_carter(ctx),
            "ventilateur": self._piece_ventilateur(ctx),
            "bobine_excitation": self._piece_bobine(ctx),
            "roulement": self._piece_roulement(ctx),
        }

        externes = {
            "rotor_externe": self.piece_rotor,
            "stator_externe": self.piece_stator,
            "arbre_externe": self.piece_arbre,
            "carter_externe": self.piece_carter,
            "ventilateur_externe": self.piece_ventilateur,
            "bobine_excite_externe": self.piece_bobine_excite,
            "roulement_externe": self.piece_roulement,
        }
        for nom, piece in externes.items():
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces[nom] = piece.analyser(strict=False)
                except TypeError:
                    try:
                        pieces[nom] = piece.analyser()
                    except Exception as exc:
                        pieces[nom] = {"erreur": str(exc)}
                except Exception as exc:
                    pieces[nom] = {"erreur": str(exc)}
        return pieces

    def _piece_rotor(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "rotor", "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}}
        rpm = ctx.get("rpm")
        P_out = ctx.get("P_out")
        eta = ctx.get("eta")
        if rpm is not None and self.nombre_poles is not None:
            rep["resultats"]["frequence_synchrone_hz"] = calcul_frequence_synchrone(
                vitesse_rotation_tr_min=float(rpm),
                nombre_poles=int(self.nombre_poles),
                mode_poles=self.mode_poles,
                clamp_non_negative=True,
            )
        else:
            _push_inconnue(rep, "partielles", "frequence_synchrone_hz", "vitesse_rotation_rpm et nombre_poles requis.")
        if P_out is not None and eta is not None and rpm is not None and float(rpm) != 0.0:
            omega = calcul_vitesse_angulaire(float(rpm), input_unite="rpm", clamp_non_negative=True)
            rep["resultats"]["puissance_mecanique_absorbee_w"] = calcul_puissance_mecanique(
                puissance_electrique_cible=float(P_out),
                rendement_alternateur=float(eta),
                pertes_fixes_w=0.0,
                clamp_non_negative=True,
                mode_signe="abs",
            )
            rep["resultats"]["couple_resistant_nm"] = calcul_couple_alternateur(
                puissance_electrique_cible=float(P_out),
                rendement_alternateur=float(eta),
                vitesse_angulaire=omega,
                pertes_fixes_w=0.0,
                clamp_non_negative=True,
                mode_signe="abs_omega",
            )
        else:
            _push_inconnue(rep, "partielles", "couple_resistant_nm", "P_out, rendement dimensionnant et vitesse non nulle requis.")
        _dedup_inconnues(rep)
        return rep

    def _piece_stator(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "stator", "resultats": {}, "pertes": {}, "inconnues": {"impossibles": [], "partielles": []}}
        rep["resultats"]["fem_phase_rms_v"] = ctx.get("fem_phase_v")
        rep["resultats"]["fem_ligne_ligne_rms_v"] = ctx.get("fem_ligne_v")
        rep["resultats"]["resistance_phase_ohm"] = ctx.get("R_phase")
        rep["pertes"]["P_cuivre_total_w"] = ctx.get("P_cu")
        rep["pertes"]["P_fer_total_w"] = ctx.get("P_fe")
        if ctx.get("fem_phase_v") is None:
            _push_inconnue(rep, "partielles", "fem_phase_rms_v", "Fréquence, spires, flux et facteur d'enroulement requis.")
        if ctx.get("P_cu") is None:
            _push_inconnue(rep, "partielles", "P_cuivre_total_w", "Courant phase et résistance phase requis.")
        if ctx.get("P_fe") is None:
            _push_inconnue(rep, "partielles", "P_fer_total_w", "Paramètres Steinmetz requis.")
        _dedup_inconnues(rep)
        return rep

    def _piece_arbre(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "arbre_alternateur", "entrees": {}, "contraintes": {}, "inconnues": {"impossibles": [], "partielles": []}}
        T = ctx.get("couple_dimensionnant")
        if T is None:
            _push_inconnue(rep, "impossibles", "couple_nm", "Requis pour vérifier la torsion de l'arbre.")
        else:
            rep["entrees"]["couple_nm"] = float(T)
        if T is not None and self.diametre_arbre_m is not None:
            d = _req_pos("diametre_arbre_m", self.diametre_arbre_m, strict=True)
            tau = 16.0 * abs(float(T)) / (math.pi * d**3)
            rep["contraintes"]["tau_torsion_pa"] = tau
            rep["entrees"]["diametre_arbre_m"] = d
            if self.tau_admissible_pa is not None:
                tau_adm = _req_pos("tau_admissible_pa", self.tau_admissible_pa, strict=True)
                rep["contraintes"]["ok_torsion"] = tau <= tau_adm
                rep["contraintes"]["diametre_min_torsion_m"] = (16.0 * abs(float(T)) / (math.pi * tau_adm)) ** (1.0 / 3.0)
            else:
                _push_inconnue(rep, "partielles", "tau_admissible_pa", "Requis pour vérifier le coefficient de sécurité.")
        elif self.diametre_arbre_m is None:
            _push_inconnue(rep, "partielles", "diametre_arbre_m", "Requis pour calculer la contrainte de torsion.")
        _dedup_inconnues(rep)
        return rep

    def _piece_carter(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "carter_alternateur", "thermique": {}, "inconnues": {"impossibles": [], "partielles": []}}
        P_loss = ctx.get("P_pertes_connues")
        rep["thermique"]["puissance_pertes_connues_w"] = P_loss
        if P_loss is not None and self.resistance_thermique_k_w is not None:
            delta = calcul_echauffement_thermique(
                puissance_pertes_totale=float(P_loss),
                resistance_thermique=float(self.resistance_thermique_k_w),
                offset_temperature=self.offset_temperature_c,
                clamp_non_negative=True,
            )
            rep["thermique"]["echauffement_sur_pertes_connues_k"] = delta
            rep["thermique"]["temperature_sur_pertes_connues_c"] = self.temperature_ambiante_c + delta
            if self.temperature_max_admissible_c is not None:
                rep["thermique"]["ok_temperature"] = self.temperature_ambiante_c + delta <= self.temperature_max_admissible_c
        else:
            _push_inconnue(rep, "partielles", "echauffement", "Pertes connues et résistance thermique requises.")
        _dedup_inconnues(rep)
        return rep

    def _piece_ventilateur(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "ventilateur", "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}, "notes_modele": []}
        rpm = ctx.get("rpm")
        h = self.coeff_convection_w_m2k
        if h is None and self.autoriser_estimation_convection_proxy and rpm is not None and float(rpm) >= 0.0:
            h = 0.1 * math.sqrt(float(rpm))
            rep["resultats"]["coeff_convection_estime_w_m2k"] = h
            rep["notes_modele"].append("Coefficient de convection proxy h=0.1*sqrt(rpm), à remplacer par corrélation réelle.")
        elif h is None:
            _push_inconnue(rep, "partielles", "coeff_convection_w_m2k", "Fournir coeff_convection ou activer explicitement autoriser_estimation_convection_proxy.")

        if h is not None and self.surface_echange_m2 is not None and ctx.get("P_pertes_connues") is not None:
            A = _req_pos("surface_echange_m2", self.surface_echange_m2, strict=True)
            rep["resultats"]["delta_t_refroidissement_k"] = float(ctx["P_pertes_connues"]) / max(float(h) * A, 1e-12)
        else:
            _push_inconnue(rep, "partielles", "delta_t_refroidissement_k", "h, surface d'échange et pertes connues requis.")
        _dedup_inconnues(rep)
        return rep

    def _piece_bobine(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "bobine_excitation", "entrees": {}, "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}}
        if self.nombre_spires_excitation is not None:
            rep["entrees"]["nombre_spires_excitation"] = self.nombre_spires_excitation
        else:
            _push_inconnue(rep, "partielles", "nombre_spires_excitation", "Requis pour caractériser la bobine d'excitation.")
        if self.courant_excitation_a is not None:
            rep["entrees"]["courant_excitation_a"] = self.courant_excitation_a
        else:
            _push_inconnue(rep, "partielles", "courant_excitation_a", "Requis pour calculer les pertes d'excitation.")

        R_exc = self.resistance_excitation_ohm
        if R_exc is None and self.resistivite_excitation_ohm_m is not None and self.longueur_fil_excitation_m is not None and self.section_fil_excitation_m2 is not None:
            R_exc = calcul_resistance_enroulement(
                resistivite=self.resistivite_excitation_ohm_m,
                longueur_fil=self.longueur_fil_excitation_m,
                section_fil=self.section_fil_excitation_m2,
                temperature_c=self.temperature_c,
                temperature_ref_c=self.temperature_ref_c,
                coef_temperature=self.coef_temperature,
                clamp_non_negative=True,
            )
        if R_exc is not None:
            rep["resultats"]["resistance_excitation_ohm"] = R_exc
        else:
            _push_inconnue(rep, "partielles", "resistance_excitation_ohm", "Fournir R excitation ou géométrie du fil.")
        if R_exc is not None and self.courant_excitation_a is not None:
            rep["resultats"]["pertes_cuivre_excitation_w"] = float(self.courant_excitation_a) ** 2 * float(R_exc)
        _dedup_inconnues(rep)
        return rep

    def _piece_roulement(self, ctx: Mapping[str, Any]) -> Dict[str, Any]:
        rep = {"piece": "roulement_alternateur", "entrees": {}, "resultats": {}, "inconnues": {"impossibles": [], "partielles": []}}
        rpm = ctx.get("rpm")
        if self.charge_radiale_roulement_n is None:
            _push_inconnue(rep, "partielles", "charge_radiale_roulement_n", "Requise pour la durée de vie L10.")
            _dedup_inconnues(rep)
            return rep
        if rpm is None:
            _push_inconnue(rep, "partielles", "vitesse_rotation_rpm", "Requise pour exprimer la durée de vie en heures.")
            _dedup_inconnues(rep)
            return rep
        P = _req_pos("charge_radiale_roulement_n", self.charge_radiale_roulement_n, strict=True) * _req_pos("facteur_charge_roulement", self.facteur_charge_roulement, strict=True)
        C = self.capacite_dynamique_roulement_n
        rep["entrees"].update({"charge_equivalente_n": P, "vitesse_rpm": rpm, "capacite_dynamique_n": C})
        if C is None:
            _push_inconnue(rep, "partielles", "capacite_dynamique_roulement_n", "Requise pour calculer L10 ISO-281 simplifiée.")
            _dedup_inconnues(rep)
            return rep
        C = _req_pos("capacite_dynamique_roulement_n", C, strict=True)
        millions_rev = (C / P) ** 3
        heures = (millions_rev * 1_000_000.0) / (60.0 * max(abs(float(rpm)), 1e-12))
        rep["resultats"]["duree_vie_l10_h"] = heures
        _dedup_inconnues(rep)
        return rep

    # ------------------------------------------------------------------
    # Sélection / validations
    # ------------------------------------------------------------------
    @staticmethod
    def _ok_global(rep: Mapping[str, Any]) -> Optional[bool]:
        vals: list[bool] = []
        for block_name in ("validations", "thermique"):
            block = rep.get(block_name, {})
            if not isinstance(block, Mapping):
                continue
            for key, value in block.items():
                if key.startswith("ok_") and isinstance(value, bool):
                    vals.append(value)
        plage = rep.get("plage_regime", {})
        if isinstance(plage, Mapping) and isinstance(plage.get("ok_admissible"), bool):
            vals.append(bool(plage["ok_admissible"]))
        if not vals:
            return None
        return all(vals)

    @staticmethod
    def _extraire_resume_candidat(cand: Mapping[str, Any]) -> Dict[str, Any]:
        res = cand.get("resultats", {}) if isinstance(cand.get("resultats", {}), Mapping) else {}
        chaine = cand.get("chaine_moteur_boite_alternateur", {}) if isinstance(cand.get("chaine_moteur_boite_alternateur", {}), Mapping) else {}
        alt = cand.get("alternateur", {}) if isinstance(cand.get("alternateur", {}), Mapping) else {}
        alt_res = alt.get("resultats", {}) if isinstance(alt.get("resultats", {}), Mapping) else {}
        return {
            "rapport": chaine.get("rapport_boite"),
            "rpm_alternateur": chaine.get("rpm_alternateur") or res.get("vitesse_rotation_rpm"),
            "P_out_W": res.get("P_out_W") or alt_res.get("P_out_W"),
            "eta_total": res.get("eta_total") or alt_res.get("eta_total"),
            "P_mecanique_W": res.get("P_mecanique_W") or alt_res.get("P_mecanique_W"),
            "couple_alternateur_Nm": chaine.get("couple_alternateur_nm") or res.get("couple_mecanique_Nm"),
            "couple_moteur_requis_Nm": chaine.get("couple_moteur_requis_nm"),
            "puissance_moteur_requise_W": chaine.get("puissance_moteur_requise_w"),
            "score_rpm": alt_res.get("score_rpm"),
            "ok_rpm_optimal": alt_res.get("ok_rpm_optimal"),
        }

    @staticmethod
    def _selectionner_candidat(candidats: Sequence[Mapping[str, Any]], *, strategie: StrategieAlternateur) -> Dict[str, Any]:
        resumes = [(c, c.get("resume", {}) if isinstance(c.get("resume", {}), Mapping) else {}) for c in candidats]

        def finite(v: Any) -> Optional[float]:
            return _safe_float(v)

        if strategie == "max_rendement":
            scored = [(finite(r.get("eta_total")), c) for c, r in resumes]
            scored = [(s, c) for s, c in scored if s is not None]
            if scored:
                s, c = max(scored, key=lambda x: x[0])
                return {"strategie": strategie, "rapport": c.get("rapport"), "score": s, "resume": c.get("resume")}
        elif strategie == "min_pertes":
            scored = [(finite(r.get("P_mecanique_W")) - finite(r.get("P_out_W")), c) for c, r in resumes if finite(r.get("P_mecanique_W")) is not None and finite(r.get("P_out_W")) is not None]
            if scored:
                s, c = min(scored, key=lambda x: x[0])
                return {"strategie": strategie, "rapport": c.get("rapport"), "score": s, "resume": c.get("resume")}
        elif strategie == "min_couple_moteur":
            scored = [(finite(r.get("couple_moteur_requis_Nm")), c) for c, r in resumes]
            scored = [(s, c) for s, c in scored if s is not None]
            if scored:
                s, c = min(scored, key=lambda x: x[0])
                return {"strategie": strategie, "rapport": c.get("rapport"), "score": s, "resume": c.get("resume")}
        elif strategie == "rpm_cible":
            scored = [(finite(r.get("score_rpm")), c) for c, r in resumes]
            scored = [(s, c) for s, c in scored if s is not None]
            if scored:
                s, c = min(scored, key=lambda x: x[0])
                return {"strategie": strategie, "rapport": c.get("rapport"), "score": s, "resume": c.get("resume")}
        elif strategie == "pareto":
            front = []
            pts = []
            for c, r in resumes:
                eta = finite(r.get("eta_total"))
                couple = finite(r.get("couple_moteur_requis_Nm"))
                rpm_score = finite(r.get("score_rpm"))
                if eta is not None and couple is not None:
                    pts.append((eta, couple, rpm_score if rpm_score is not None else 0.0, c))
            for i, (eta_i, couple_i, rpm_i, c_i) in enumerate(pts):
                dominated = False
                for j, (eta_j, couple_j, rpm_j, _c_j) in enumerate(pts):
                    if i == j:
                        continue
                    if (eta_j >= eta_i and couple_j <= couple_i and rpm_j <= rpm_i) and (eta_j > eta_i or couple_j < couple_i or rpm_j < rpm_i):
                        dominated = True
                        break
                if not dominated:
                    front.append({"rapport": c_i.get("rapport"), "resume": c_i.get("resume")})
            return {"strategie": strategie, "pareto_front": front, "count": len(front)}
        else:
            raise ValueError("strategie invalide.")

        return {"strategie": strategie, "erreur": "métriques insuffisantes pour sélectionner un rapport."}


# =============================================================================
# Constructeurs / orchestration haut niveau
# =============================================================================

def _build_plage(obj: Any) -> PlageRegimeAlternateur:
    if isinstance(obj, PlageRegimeAlternateur):
        return obj
    if isinstance(obj, Mapping):
        allowed = set(inspect.signature(PlageRegimeAlternateur).parameters.keys())
        return PlageRegimeAlternateur(**{k: v for k, v in obj.items() if k in allowed})
    return PlageRegimeAlternateur()


def _build_interface_bus(obj: Any) -> InterfaceBusDC:
    if isinstance(obj, InterfaceBusDC):
        return obj
    if isinstance(obj, Mapping):
        allowed = set(inspect.signature(InterfaceBusDC).parameters.keys())
        return InterfaceBusDC(**{k: v for k, v in obj.items() if k in allowed})
    return InterfaceBusDC()


def construire_alternateur(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Alternateur:
    cfg: Dict[str, Any] = dict(config or {})
    if "alternateur" in cfg and isinstance(cfg["alternateur"], Mapping):
        merged = dict(cfg["alternateur"])
        merged.update({k: v for k, v in cfg.items() if k != "alternateur"})
        cfg = merged
    cfg.update({k: v for k, v in overrides.items() if v is not None})

    if "plage_regime" in cfg:
        cfg["plage_regime"] = _build_plage(cfg["plage_regime"])
    else:
        # Compatibilité top-level
        plage_keys = set(inspect.signature(PlageRegimeAlternateur).parameters.keys())
        if any(k in cfg for k in plage_keys):
            cfg["plage_regime"] = _build_plage({k: cfg[k] for k in plage_keys if k in cfg})

    if "interface_bus_dc" in cfg:
        cfg["interface_bus_dc"] = _build_interface_bus(cfg["interface_bus_dc"])
    else:
        bus_keys = set(inspect.signature(InterfaceBusDC).parameters.keys())
        if any(k in cfg for k in bus_keys):
            cfg["interface_bus_dc"] = _build_interface_bus({k: cfg[k] for k in bus_keys if k in cfg})

    allowed = set(inspect.signature(Alternateur).parameters.keys())
    kwargs = {k: v for k, v in cfg.items() if k in allowed}
    return Alternateur(**kwargs)


def concevoir_alternateur(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = dict(config or {})
    cfg.update(overrides)
    alt = cfg.get("instance")
    if alt is None:
        alt = construire_alternateur(cfg)
    if not isinstance(alt, Alternateur):
        raise ValueError("config['instance'] doit être une instance de Alternateur si fourni.")

    # 1) Comparaison de rapports boîte
    for key in ("comparaison_rapports", "rapports_boite", "selection_rapports"):
        if isinstance(cfg.get(key), Mapping):
            analyse = dict(cfg[key])
            allowed = set(inspect.signature(Alternateur.comparer_rapports_boite).parameters.keys()) - {"self"}
            return alt.comparer_rapports_boite(**{k: v for k, v in analyse.items() if k in allowed})

    # 2) Chaîne moteur -> boîte -> alternateur
    for key in ("depuis_boite_crabots", "chaine_boite", "boite"):
        if isinstance(cfg.get(key), Mapping) and ("rpm_moteur" in cfg[key] or "rapport_boite" in cfg[key]):
            analyse = dict(cfg[key])
            allowed = set(inspect.signature(Alternateur.analyser_depuis_boite_crabots).parameters.keys()) - {"self"}
            return alt.analyser_depuis_boite_crabots(**{k: v for k, v in analyse.items() if k in allowed})

    # 3) Bus DC
    bus_dc = {}
    for key in ("bus_dc", "analyse_bus_dc"):
        if isinstance(cfg.get(key), Mapping):
            bus_dc.update(dict(cfg[key]))
    if bus_dc or "puissance_bus_dc_w" in cfg:
        allowed_bus = set(inspect.signature(Alternateur.analyser_pour_bus_dc).parameters.keys()) - {"self"}
        bus_dc.update({k: v for k, v in cfg.items() if k in allowed_bus})
        return alt.analyser_pour_bus_dc(**bus_dc)

    # 4) Point de fonctionnement direct
    point = {}
    for key in ("point", "point_de_fonctionnement", "fonctionnement"):
        if isinstance(cfg.get(key), Mapping):
            point.update(dict(cfg[key]))
    allowed_point = set(inspect.signature(Alternateur.analyser_point_de_fonctionnement).parameters.keys()) - {"self"}
    point.update({k: v for k, v in cfg.items() if k in allowed_point})
    return alt.analyser_point_de_fonctionnement(**point)


__all__ = [
    "ModeElectrique",
    "Connexion",
    "ModePoles",
    "Onde",
    "StrategieAlternateur",
    "PlageRegimeAlternateur",
    "InterfaceBusDC",
    "Alternateur",
    "construire_alternateur",
    "concevoir_alternateur",
    "exporter_rapport_json",
]


if __name__ == "__main__":
    exemple = concevoir_alternateur({
        "alternateur": {
            "nombre_poles": 8,
            "mode_poles": "poles",
            "connexion": "Y",

            # Plage système : la boîte doit amener l'alternateur ici
            "plage_regime": {
                "rpm_cible": 9000.0,
                "rpm_min_optimal": 7500.0,
                "rpm_max_optimal": 10500.0,
                "rpm_min_admissible": 3000.0,
                "rpm_max_admissible": 12000.0,
            },

            # Électromagnétique
            "nombre_spires_serie": 40,
            "facteur_enroulement": 0.95,
            "induction_gap_t": 0.9,
            "aire_pole_m2": 1.2e-3,

            # Pertes calculables
            "resistance_phase_ohm": 0.08,
            "k_h": 0.02,
            "k_e": 1e-5,
            "exposant_steinmetz": 1.7,
            "induction_max_t": 0.9,
            "masse_fer_kg": 12.0,
            "pertes_fixes_w": 250.0,
            "pertes_mecaniques_w": 180.0,

            # Dimensionnant si pertes incomplètes / pour compatibilité chaîne
            "rendement_alternateur_impose": 0.92,

            # Thermique / mécanique
            "resistance_thermique_k_w": 0.08,
            "temperature_max_admissible_c": 120.0,
            "surface_echange_m2": 0.5,
            "diametre_arbre_m": 0.035,
            "tau_admissible_pa": 90e6,

            # Interface bus DC
            "interface_bus_dc": {
                "tension_bus_dc_v": 400.0,
                "courant_bus_max_a": 120.0,
                "puissance_charge_max_w": 35_000.0,
                "rendement_redressement": 0.96,
                "rendement_charge": 0.95,
            },
        },
        "comparaison_rapports": {
            "rpm_moteur": 2800.0,
            "rapports": [2.5, 3.0, 3.2, 3.5, 4.0],
            "puissance_bus_dc_w": 25_000.0,
            "rendement_boite": 0.94,
            "strategie": "pareto",
        },
    })
    print(json.dumps(_to_jsonable({
        "selection": exemple.get("selection"),
        "premier_candidat": exemple.get("candidats", [{}])[0].get("resume"),
        "inconnues": exemple.get("inconnues"),
    }), ensure_ascii=False, indent=2))
