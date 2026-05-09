# backend\components\moteur_electrique\moteur_electrique.py
from __future__ import annotations

import importlib
import json
import math
import sys
from dataclasses import asdict, dataclass, is_dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple


# =============================================================================
# Préparation du chemin projet
# =============================================================================

_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent

for candidate in (
    _THIS_DIR,
    _THIS_DIR / "modules",
    _THIS_DIR / "pieces",
    _THIS_DIR.parent,
    _THIS_DIR.parent.parent,
    _THIS_DIR.parent.parent.parent,
    Path.cwd(),
):
    try:
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.append(candidate_str)
    except Exception:
        pass


# =============================================================================
# Imports robustes des modules métier
# =============================================================================

IMPORT_STATUS: Dict[str, Any] = {
    "modules": {},
    "pieces": {},
    "erreurs": {},
}


def _import_attr(
    module_names: Sequence[str],
    attr: str,
    *,
    required: bool = True,
    default: Any = None,
) -> Any:
    """
    Importe un attribut depuis plusieurs chemins possibles.

    Objectif : le même fichier doit fonctionner :
    - dans l'arborescence backend.components.moteur_electrique ;
    - dans une arborescence components.moteur_electrique ;
    - en exécution isolée avec les modules .py dans le même dossier.
    """
    errors: List[str] = []
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            value = getattr(module, attr)
            return value
        except Exception as exc:
            errors.append(f"{module_name}.{attr}: {exc}")
    IMPORT_STATUS["erreurs"][attr] = errors
    if required:
        raise ImportError(
            f"Impossible d'importer {attr}. Chemins testés: {list(module_names)}. "
            f"Dernières erreurs: {errors[-3:]}"
        )
    return default


def _register_import(name: str, value: Any, *, section: str = "modules") -> Any:
    IMPORT_STATUS.setdefault(section, {})[name] = value is not None
    return value


# Modules routiers / puissance / adhérence
calcul_force_resistance_totale = _register_import(
    "calcul_force_resistance_totale",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_force_resistance_vitesse",
            "components.moteur_electrique.modules.calcul_force_resistance_vitesse",
            "moteur_electrique.modules.calcul_force_resistance_vitesse",
            "modules.calcul_force_resistance_vitesse",
            "calcul_force_resistance_vitesse",
        ),
        "calcul_force_resistance_totale",
    ),
)

calcul_puissance_roue = _register_import(
    "calcul_puissance_roue",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_puissance_roue",
            "components.moteur_electrique.modules.calcul_puissance_roue",
            "moteur_electrique.modules.calcul_puissance_roue",
            "modules.calcul_puissance_roue",
            "calcul_puissance_roue",
        ),
        "calcul_puissance_roue",
    ),
)
calcul_couple_roue_total = _register_import(
    "calcul_couple_roue_total",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_puissance_roue",
            "components.moteur_electrique.modules.calcul_puissance_roue",
            "moteur_electrique.modules.calcul_puissance_roue",
            "modules.calcul_puissance_roue",
            "calcul_puissance_roue",
        ),
        "calcul_couple_roue_total",
    ),
)
calcul_couple_par_roue = _register_import(
    "calcul_couple_par_roue",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_puissance_roue",
            "components.moteur_electrique.modules.calcul_puissance_roue",
            "moteur_electrique.modules.calcul_puissance_roue",
            "modules.calcul_puissance_roue",
            "calcul_puissance_roue",
        ),
        "calcul_couple_par_roue",
    ),
)

calcul_puissance_moteur_electrique = _register_import(
    "calcul_puissance_moteur_electrique",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_puissance_moteur",
            "components.moteur_electrique.modules.calcul_puissance_moteur",
            "moteur_electrique.modules.calcul_puissance_moteur",
            "modules.calcul_puissance_moteur",
            "calcul_puissance_moteur",
        ),
        "calcul_puissance_moteur_electrique",
    ),
)
calcul_couple_moteur = _register_import(
    "calcul_couple_moteur",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_puissance_moteur",
            "components.moteur_electrique.modules.calcul_puissance_moteur",
            "moteur_electrique.modules.calcul_puissance_moteur",
            "modules.calcul_puissance_moteur",
            "calcul_puissance_moteur",
        ),
        "calcul_couple_moteur",
    ),
)

calcul_charges_essieux = _register_import(
    "calcul_charges_essieux",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_charge_essieu",
            "components.moteur_electrique.modules.calcul_charge_essieu",
            "moteur_electrique.modules.calcul_charge_essieu",
            "modules.calcul_charge_essieu",
            "calcul_charge_essieu",
        ),
        "calcul_charges_essieux",
    ),
)

calcul_acceleration_max = _register_import(
    "calcul_acceleration_max",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_acceleration_max",
            "components.moteur_electrique.modules.calcul_acceleration_max",
            "moteur_electrique.modules.calcul_acceleration_max",
            "modules.calcul_acceleration_max",
            "calcul_acceleration_max",
        ),
        "calcul_acceleration_max",
    ),
)

# Modules multi-domaines optionnels
_md_nautique = _register_import(
    "calcul_demande_nautique",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_multi_domaine",
            "backend.modules.moteur_electrique.calcul_multi_domaine",
            "components.moteur_electrique.modules.calcul_multi_domaine",
            "moteur_electrique.modules.calcul_multi_domaine",
            "modules.calcul_multi_domaine",
            "calcul_multi_domaine",
        ),
        "calcul_demande_nautique",
        required=False,
    ),
)
_md_aerien_rho = _register_import(
    "calcul_demande_aerien_rho",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_multi_domaine",
            "backend.modules.moteur_electrique.calcul_multi_domaine",
            "components.moteur_electrique.modules.calcul_multi_domaine",
            "moteur_electrique.modules.calcul_multi_domaine",
            "modules.calcul_multi_domaine",
            "calcul_multi_domaine",
        ),
        "calcul_demande_aerien_rho",
        required=False,
    ),
)
_md_ferro_davis = _register_import(
    "calcul_demande_ferroviaire_davis",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_multi_domaine",
            "backend.modules.moteur_electrique.calcul_multi_domaine",
            "components.moteur_electrique.modules.calcul_multi_domaine",
            "moteur_electrique.modules.calcul_multi_domaine",
            "modules.calcul_multi_domaine",
            "calcul_multi_domaine",
        ),
        "calcul_demande_ferroviaire_davis",
        required=False,
    ),
)
_md_rho_air_sec = _register_import(
    "calcul_densite_air_sec",
    _import_attr(
        (
            "backend.components.moteur_electrique.modules.calcul_multi_domaine",
            "backend.modules.moteur_electrique.calcul_multi_domaine",
            "components.moteur_electrique.modules.calcul_multi_domaine",
            "moteur_electrique.modules.calcul_multi_domaine",
            "modules.calcul_multi_domaine",
            "calcul_multi_domaine",
        ),
        "calcul_densite_air_sec",
        required=False,
    ),
)


# =============================================================================
# Imports robustes des pièces
# =============================================================================

RotorMoteurElectrique = _register_import(
    "RotorMoteurElectrique",
    _import_attr(
        (
            "backend.components.moteur_electrique.pieces.rotor_moteur_electrique",
            "components.moteur_electrique.pieces.rotor_moteur_electrique",
            "moteur_electrique.pieces.rotor_moteur_electrique",
            "pieces.rotor_moteur_electrique",
            "rotor_moteur_electrique",
        ),
        "RotorMoteurElectrique",
        required=False,
    ),
    section="pieces",
)

StatorMoteurElectrique = _register_import(
    "StatorMoteurElectrique",
    _import_attr(
        (
            "backend.components.moteur_electrique.pieces.stator_moteur_electrique",
            "components.moteur_electrique.pieces.stator_moteur_electrique",
            "moteur_electrique.pieces.stator_moteur_electrique",
            "pieces.stator_moteur_electrique",
            "stator_moteur_electrique",
        ),
        "StatorMoteurElectrique",
        required=False,
    ),
    section="pieces",
)


if RotorMoteurElectrique is None:
    @dataclass
    class RotorMoteurElectrique:  # type: ignore[no-redef]
        moteur: Optional[Any] = None
        couple_max_nm: Optional[float] = None
        regime_base_rpm: Optional[float] = None
        regime_max_rpm: Optional[float] = None

        def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
            moteur = self.moteur
            couple = self.couple_max_nm if self.couple_max_nm is not None else getattr(moteur, "couple_max_nm_calcule", None)
            regime_base = self.regime_base_rpm if self.regime_base_rpm is not None else getattr(moteur, "regime_base_rpm_calcule", None)
            regime_max = self.regime_max_rpm if self.regime_max_rpm is not None else getattr(moteur, "regime_max_rpm", None)
            rep: Dict[str, Any] = {
                "piece": "rotor_moteur_electrique",
                "cinematique": {
                    "couple_max_nm": couple,
                    "regime_base_rpm": regime_base,
                    "regime_max_rpm": regime_max,
                },
                "inconnues": {"impossibles": [], "partielles": []},
                "notes_modele": ["Fallback rotor interne utilisé : fichier pièce non importé."],
            }
            if not isinstance(couple, (int, float)) or not math.isfinite(float(couple)):
                rep["inconnues"]["partielles"].append({"nom": "couple_max_nm", "raison": "Définition moteur incomplète."})
            if not isinstance(regime_base, (int, float)) or not math.isfinite(float(regime_base)):
                rep["inconnues"]["partielles"].append({"nom": "regime_base_rpm", "raison": "Définition moteur incomplète."})
            return rep

if StatorMoteurElectrique is None:
    @dataclass
    class StatorMoteurElectrique:  # type: ignore[no-redef]
        moteur: Optional[Any] = None
        tension_bus_v: Optional[float] = None
        courant_max_a: Optional[float] = None
        puissance_max_w: Optional[float] = None

        def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
            moteur = self.moteur
            tension = self.tension_bus_v if self.tension_bus_v is not None else getattr(moteur, "tension_bus_v", None)
            courant = self.courant_max_a if self.courant_max_a is not None else getattr(moteur, "courant_max_a", None)
            puissance = self.puissance_max_w if self.puissance_max_w is not None else getattr(moteur, "puissance_max_w", None)
            rep: Dict[str, Any] = {
                "piece": "stator_moteur_electrique",
                "electrique": {
                    "tension_bus_v": tension,
                    "courant_max_a": courant,
                    "puissance_max_w": puissance,
                },
                "inconnues": {"impossibles": [], "partielles": []},
                "notes_modele": ["Fallback stator interne utilisé : fichier pièce non importé."],
            }
            if isinstance(tension, (int, float)) and isinstance(courant, (int, float)) and math.isfinite(float(tension)) and math.isfinite(float(courant)):
                rep["electrique"]["puissance_dc_max_w"] = float(tension) * float(courant)
            else:
                rep["inconnues"]["partielles"].append({"nom": "puissance_dc_max_w", "raison": "Calculable si tension_bus_v et courant_max_a sont fournis."})
            return rep

# =============================================================================
# Helpers (validation + conversions)
# =============================================================================

DriveMode = Literal["FWD", "RWD", "AWD"]
AngleUnit = Literal["rad", "deg"]
Domaine = Literal["routier", "nautique", "aerien", "ferroviaire"]

_G0 = 9.80665  # constante physique (standard)


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


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


def _req_ratio_0_1(name: str, x: Any, *, strict_min: bool = True) -> float:
    v = _req_finite(name, x)
    if strict_min:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    if v > 1.0:
        raise ValueError(f"{name} doit être <= 1 (reçu: {v}).")
    return v


def rpm_to_rad_s(rpm: float) -> float:
    rpm = _req_finite("rpm", rpm)
    return (2.0 * math.pi) * (rpm / 60.0)


def rad_s_to_rpm(omega: float) -> float:
    omega = _req_finite("omega", omega)
    return (omega * 60.0) / (2.0 * math.pi)


def _push_inc(rapport: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rapport["inconnues"][cat].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: List[dict]) -> List[dict]:
        seen: set[Tuple[str, str]] = set()
        out: List[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


def _wh_per_km_from_p_v(p_w: float, v_ms: float) -> float:
    # Wh/km = (P / v) * (1000 / 3600)
    P = _req_pos("p_w", p_w, strict=False)
    v = _req_pos("v_ms", v_ms, strict=True)
    if P == 0.0:
        return 0.0
    return (P / v) * (1000.0 / 3600.0)


def _bisect_monotone(
    f: Any,
    target: float,
    v_lo: float,
    v_hi: float,
    *,
    max_iter: int = 200,
    rel_tol: float = 1e-7,
    abs_tol: float = 1e-9,
) -> float:
    """
    Résout f(v)=target pour f croissante sur [v_lo, v_hi], par dichotomie.
    """
    t = _req_pos("target", target, strict=False)
    lo = _req_pos("v_lo", v_lo, strict=False)
    hi = _req_pos("v_hi", v_hi, strict=True)

    f_lo = float(f(lo))
    f_hi = float(f(hi))

    if f_lo > t:
        return lo
    if f_hi < t:
        return hi

    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = float(f(mid))
        err = f_mid - t
        if abs(err) <= max(abs_tol, rel_tol * max(1.0, t)):
            return mid
        if f_mid < t:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _get_req(params: Dict[str, Any], key: str) -> Any:
    if key not in params:
        raise KeyError(f"Paramètre manquant: {key}")
    return params[key]


# =============================================================================
# Modèle moteur: couple/puissance sans hypothèses
# =============================================================================

@dataclass(frozen=True)
class MoteurElectrique:
    """
    Modèle simple d'un moteur électrique, sans valeurs "typées" imposées.

    Requis:
      - puissance_max_w
      - regime_max_rpm
      - ET (couple_max_nm OU regime_base_rpm)
        (pour définir la courbe couple constant -> puissance constante)

    Rendements / pertes:
      - rendement_moteur, pertes_fixes_w ne sont utilisés QUE pour estimer une
        puissance électrique (approx). Si tu ne les fournis pas: on ne les invente pas.
    """

    puissance_max_w: float
    regime_max_rpm: float

    couple_max_nm: Optional[float] = None
    regime_base_rpm: Optional[float] = None

    # Optionnels (aucune valeur par défaut “typique”)
    rendement_moteur: Optional[float] = None          # mech / elec
    rendement_transmission: Optional[float] = None    # roue / moteur (si tu veux stocker ici)

    tension_bus_v: Optional[float] = None
    courant_max_a: Optional[float] = None

    pertes_fixes_w: float = 0.0

    piece_rotor: Optional[RotorMoteurElectrique] = None
    piece_stator: Optional[StatorMoteurElectrique] = None

    def __post_init__(self) -> None:
        _req_pos("puissance_max_w", self.puissance_max_w, strict=True)
        _req_pos("regime_max_rpm", self.regime_max_rpm, strict=True)
        _req_finite("pertes_fixes_w", self.pertes_fixes_w)

        if (self.couple_max_nm is None) and (self.regime_base_rpm is None):
            raise ValueError(
                "Il faut fournir 'couple_max_nm' OU 'regime_base_rpm' "
                "pour définir une courbe couple/puissance sans hypothèses."
            )

        if self.couple_max_nm is not None:
            _req_pos("couple_max_nm", self.couple_max_nm, strict=True)

        if self.regime_base_rpm is not None:
            _req_pos("regime_base_rpm", self.regime_base_rpm, strict=True)
            if self.regime_base_rpm > self.regime_max_rpm:
                raise ValueError("regime_base_rpm ne peut pas dépasser regime_max_rpm.")

        if self.rendement_moteur is not None:
            _req_ratio_0_1("rendement_moteur", self.rendement_moteur, strict_min=True)

        if self.rendement_transmission is not None:
            _req_ratio_0_1("rendement_transmission", self.rendement_transmission, strict_min=True)

        # garde-fou cohérence si les deux infos sont fournies
        if self.couple_max_nm is not None and self.regime_base_rpm is not None:
            omega_b = rpm_to_rad_s(self.regime_base_rpm)
            P_at_base = self.couple_max_nm * omega_b
            if P_at_base > 1.2 * self.puissance_max_w:
                raise ValueError(
                    "Incohérence: couple_max_nm * omega_base dépasse fortement puissance_max_w. "
                    "Vérifie (Pmax, Tmax, rpm_base)."
                )

    @property
    def omega_max_rad_s(self) -> float:
        return rpm_to_rad_s(self.regime_max_rpm)

    @property
    def omega_base_rad_s(self) -> float:
        if self.regime_base_rpm is not None:
            return rpm_to_rad_s(self.regime_base_rpm)
        assert self.couple_max_nm is not None
        omega_b = self.puissance_max_w / self.couple_max_nm
        return min(omega_b, self.omega_max_rad_s)

    @property
    def regime_base_rpm_calcule(self) -> float:
        return rad_s_to_rpm(self.omega_base_rad_s)

    @property
    def couple_max_nm_calcule(self) -> float:
        if self.couple_max_nm is not None:
            return self.couple_max_nm
        assert self.regime_base_rpm is not None
        omega_b = rpm_to_rad_s(self.regime_base_rpm)
        return self.puissance_max_w / omega_b

    def couple_disponible_nm(self, regime_rpm: float) -> float:
        rpm = _req_pos("regime_rpm", regime_rpm, strict=False)
        rpm = min(rpm, self.regime_max_rpm)

        omega = max(rpm_to_rad_s(rpm), 1e-9)
        omega_b = self.omega_base_rad_s
        Tmax = self.couple_max_nm_calcule

        if omega <= omega_b:
            return Tmax
        return min(Tmax, self.puissance_max_w / omega)

    def puissance_mecanique_disponible_w(self, regime_rpm: float) -> float:
        rpm = _req_pos("regime_rpm", regime_rpm, strict=False)
        rpm = min(rpm, self.regime_max_rpm)
        omega = rpm_to_rad_s(rpm)
        T = self.couple_disponible_nm(rpm)
        return min(self.puissance_max_w, T * omega)

    def puissance_electrique_approx_w(self, regime_rpm: float) -> float:
        """
        P_elec ≈ (P_mech + pertes_fixes) / eta_moteur
        Sans eta_moteur: impossible (pas d'invention).
        """
        if self.rendement_moteur is None:
            raise ValueError("rendement_moteur non fourni: impossible d'estimer P_elec.")
        eta = _req_ratio_0_1("rendement_moteur", self.rendement_moteur, strict_min=True)
        Pm = self.puissance_mecanique_disponible_w(regime_rpm)
        Pin = (Pm + self.pertes_fixes_w) / eta
        return max(0.0, Pin)

    def verifie_coherence_electrique(self) -> Dict[str, Any]:
        """
        Vérifie (si V et I fournis) la cohérence avec Pmax.
        Nécessite eta_moteur pour comparer méc/élec sans supposer.
        """
        out: Dict[str, Any] = {"ok": True}

        if self.tension_bus_v is None or self.courant_max_a is None:
            out["info"] = "tension_bus_v/courant_max_a non fournis -> pas de check."
            return out
        if self.rendement_moteur is None:
            out["info"] = "rendement_moteur non fourni -> pas de check méc/élec."
            return out

        V = _req_pos("tension_bus_v", self.tension_bus_v, strict=True)
        I = _req_pos("courant_max_a", self.courant_max_a, strict=True)
        eta = _req_ratio_0_1("rendement_moteur", self.rendement_moteur, strict_min=True)

        P_elec_max = V * I
        P_mech_max_est = P_elec_max * eta

        out.update(
            {
                "P_elec_max_W": float(P_elec_max),
                "P_mech_max_est_W": float(P_mech_max_est),
                "P_mech_spec_W": float(self.puissance_max_w),
            }
        )

        if self.puissance_max_w > 1.05 * P_mech_max_est:
            out["ok"] = False
            out["warning"] = "Pmax mécanique > V*I*eta (écart > 5%). Vérifier V/I/eta/Pmax."
        return out

    def analyser_definition(self) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "moteur_electrique",
            "definition": {
                "puissance_max_w": float(self.puissance_max_w),
                "regime_max_rpm": float(self.regime_max_rpm),
                "regime_base_rpm": float(self.regime_base_rpm_calcule),
                "couple_max_nm": float(self.couple_max_nm_calcule),
                "tension_bus_v": self.tension_bus_v,
                "courant_max_a": self.courant_max_a,
                "rendement_moteur": self.rendement_moteur,
            },
            "coherence_electrique": self.verifie_coherence_electrique(),
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }
        pieces_rapport: Dict[str, Any] = {}
        rotor_piece = self.piece_rotor or RotorMoteurElectrique(moteur=self)
        stator_piece = self.piece_stator or StatorMoteurElectrique(moteur=self)
        for nom, piece in (("rotor", rotor_piece), ("stator", stator_piece)):
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces_rapport[nom] = piece.analyser()
                except Exception as exc:
                    pieces_rapport[nom] = {"erreur": str(exc)}
        if pieces_rapport:
            rapport["pieces"] = pieces_rapport
        if self.tension_bus_v is None:
            _push_inc(rapport, "partielles", "tension_bus_v", "Necessaire pour caracteriser le bus DC et le stator.")
        if self.courant_max_a is None:
            _push_inc(rapport, "partielles", "courant_max_a", "Necessaire pour qualifier le niveau de courant du moteur.")
        _dedup_inconnues(rapport)
        return rapport

    def analyser(
        self,
        *,
        puissance_elec_dispo_w: Optional[float] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if puissance_elec_dispo_w is None or config is None:
            return self.analyser_definition()
        return AnalyseDepuisPuissance(tension_systeme_v=self.tension_bus_v).analyser(
            puissance_elec_dispo_w=puissance_elec_dispo_w,
            config=dict(config),
        )


# =============================================================================
# Demande moteur à partir d'un état véhicule (modules routiers)
# =============================================================================

def calcul_demande_moteur_depuis_vehicule(
    *,
    masse_kg: float,
    vitesse_ms: float,
    acceleration_ms2: float,
    angle_pente: float,
    angle_unite: AngleUnit,
    coef_roulement: float,
    coef_trainee_aero_cda: float,
    densite_air: float,       # PAS de défaut: pas d'invention
    gravite: float = _G0,     # constante physique standard
    rayon_roue_m: float,
    rapport_reduction_global: float,
    rendement_transmission: float,
    nb_roues_motrices: int = 2,
    pertes_fixes_w: float = 0.0,
    couple_pertes_nm: float = 0.0,
) -> Dict[str, float]:
    m = _req_pos("masse_kg", masse_kg, strict=True)
    v = _req_finite("vitesse_ms", vitesse_ms)
    a = _req_finite("acceleration_ms2", acceleration_ms2)

    rho = _req_pos("densite_air", densite_air, strict=True)
    g = _req_pos("gravite", gravite, strict=True)

    R = _req_pos("rayon_roue_m", rayon_roue_m, strict=True)
    G = _req_pos("rapport_reduction_global", rapport_reduction_global, strict=True)
    eta_trans = _req_ratio_0_1("rendement_transmission", rendement_transmission, strict_min=True)

    if not isinstance(nb_roues_motrices, int) or nb_roues_motrices < 1:
        raise ValueError("nb_roues_motrices doit être un entier >= 1.")

    fres = calcul_force_resistance_totale(
        masse_kg=m,
        vitesse_ms=v,
        angle_pente=angle_pente,
        coef_roulement=coef_roulement,
        coef_trainee_aero_cda=coef_trainee_aero_cda,
        densite_air=rho,
        gravite=g,
        angle_unite=angle_unite,
        oppose_mouvement=True,
        use_speed_sign=True,
        return_details=False,
    )
    F_res_tot = float(fres["F_totale"])
    F_inertie = float(m * a)
    F_req = float(F_inertie + F_res_tot)

    P_roue = float(
        calcul_puissance_roue(
            force_requise_n=F_req,
            vitesse_ms=v,
            use_abs_speed=False,
            clamp_non_negative=False,
        )
    )
    T_roue_total = float(calcul_couple_roue_total(force_requise_n=F_req, rayon_roue_m=R, clamp_non_negative=False))
    T_par_roue = float(
        calcul_couple_par_roue(
            couple_roue_total_nm=T_roue_total,
            nb_roues_motrices=nb_roues_motrices,
            repartition="egal",
        )
    )

    P_moteur = float(
        calcul_puissance_moteur_electrique(
            puissance_roue_w=P_roue,
            rendement_transmission=eta_trans,
            pertes_fixes_w=pertes_fixes_w,
            clamp_non_negative=False,
        )
    )
    T_moteur = float(
        calcul_couple_moteur(
            couple_roue_nm=T_roue_total,
            rapport_reduction_global=G,
            rendement_transmission=eta_trans,
            couple_pertes_nm=couple_pertes_nm,
            clamp_non_negative=False,
        )
    )

    omega_roue = 0.0 if R == 0 else (v / R)
    omega_moteur = omega_roue * G

    return {
        "F_res_totale_N": F_res_tot,
        "F_inertie_N": F_inertie,
        "F_requise_N": F_req,
        "P_roue_W": P_roue,
        "T_roue_total_Nm": T_roue_total,
        "T_par_roue_Nm": T_par_roue,
        "P_moteur_W": P_moteur,
        "T_moteur_Nm": T_moteur,
        "rpm_roue": rad_s_to_rpm(omega_roue),
        "rpm_moteur": rad_s_to_rpm(omega_moteur),
        "omega_roue_rad_s": omega_roue,
        "omega_moteur_rad_s": omega_moteur,
    }


def verifie_moteur_sur_demande(
    moteur: MoteurElectrique,
    demande: Dict[str, float],
    *,
    marge_puissance: float = 0.0,
    marge_couple: float = 0.0,
) -> Dict[str, float]:
    if not isinstance(moteur, MoteurElectrique):
        raise ValueError("moteur doit être une instance de MoteurElectrique.")

    rpm = _req_finite("demande['rpm_moteur']", demande.get("rpm_moteur", float("nan")))
    P_req = _req_finite("demande['P_moteur_W']", demande.get("P_moteur_W", float("nan")))
    T_req = _req_finite("demande['T_moteur_Nm']", demande.get("T_moteur_Nm", float("nan")))

    P_cap = moteur.puissance_mecanique_disponible_w(rpm)
    T_cap = moteur.couple_disponible_nm(rpm)

    P_need = P_req * (1.0 + _req_finite("marge_puissance", marge_puissance))
    T_need = T_req * (1.0 + _req_finite("marge_couple", marge_couple))

    return {
        "rpm": float(rpm),
        "P_req_W": float(P_req),
        "T_req_Nm": float(T_req),
        "P_cap_W": float(P_cap),
        "T_cap_Nm": float(T_cap),
        "P_ok": 1.0 if P_cap >= P_need else 0.0,
        "T_ok": 1.0 if T_cap >= T_need else 0.0,
        "P_ratio_cap_req": (P_cap / P_req) if abs(P_req) > 1e-9 else float("inf"),
        "T_ratio_cap_req": (T_cap / T_req) if abs(T_req) > 1e-9 else float("inf"),
        "P_marge_W": float(P_cap - P_need),
        "T_marge_Nm": float(T_cap - T_need),
    }


def acceleration_max_par_adherence(
    *,
    mu_adherence: float,
    masse_kg: float,
    hauteur_cg_m: float,
    empattement_m: float,
    charge_essieu_moteur_n: float,
    force_resistance_n: float,
    type_milieu: str,
    include_transfert: bool = False,
    clamp_non_negative: bool = True,
) -> float:
    return float(
        calcul_acceleration_max(
            mu_adherence=mu_adherence,
            charge_essieu_moteur_n=charge_essieu_moteur_n,
            force_resistance_n=force_resistance_n,
            masse_kg=masse_kg,
            hauteur_cg_m=hauteur_cg_m,
            empattement_m=empattement_m,
            type_milieu=type_milieu,
            include_transfert=include_transfert,
            clamp_non_negative=clamp_non_negative,
        )
    )


# =============================================================================
# Analyse "depuis puissance" (fusion du 2e script) : pas d'invention
# =============================================================================

@dataclass(frozen=True)
class AnalyseDepuisPuissance:
    """
    L'utilisateur fournit UNIQUEMENT:
      - puissance_elec_dispo_w

    Le reste est calculé SI et seulement SI les paramètres nécessaires sont fournis
    dans 'config'. Sinon -> 'inconnues'.

    config["domaine"] : "routier" | "nautique" | "aerien" | "ferroviaire"
    """

    tension_systeme_v: Optional[float] = None

    def analyser(self, *, puissance_elec_dispo_w: float, config: Dict[str, Any]) -> Dict[str, Any]:
        Pdispo = _req_pos("puissance_elec_dispo_w", puissance_elec_dispo_w, strict=False)

        rapport: Dict[str, Any] = {
            "entree": {
                "puissance_elec_dispo_w": float(Pdispo),
                "tension_systeme_v": self.tension_systeme_v,
                "domaine": str(config.get("domaine", "")),
            },
            "resultats": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes": [],
        }

        # courant si tension connue
        if self.tension_systeme_v is not None:
            V = _req_pos("tension_systeme_v", self.tension_systeme_v, strict=True)
            rapport["resultats"]["courant_estime_A"] = 0.0 if Pdispo == 0.0 else float(Pdispo / V)
        else:
            _push_inc(rapport, "partielles", "courant_estime_A", "Calculable si tension_systeme_v est fournie.")

        domaine = str(config.get("domaine", "")).strip().lower()
        if domaine not in ("routier", "nautique", "aerien", "ferroviaire"):
            raise ValueError("config['domaine'] doit être: routier | nautique | aerien | ferroviaire")

        # ---------------------------------------------------------------------
        # ROUTIER : on inverse P_elec(v) via tes modules
        # ---------------------------------------------------------------------
        if domaine == "routier":
            req = [
                "masse_kg",
                "angle_pente",
                "angle_unite",
                "coef_roulement",
                "cda",
                "densite_air",
                "eta_transmission",
                "eta_moteur",
                "v_max_recherche_ms",
            ]
            missing = [k for k in req if k not in config]
            if missing:
                _push_inc(rapport, "impossibles", "vitesse_max_routier", f"Paramètres manquants: {missing}")
            else:
                m = _req_pos("masse_kg", config["masse_kg"], strict=True)
                angle_pente = _req_finite("angle_pente", config["angle_pente"])
                angle_unite: AngleUnit = str(config["angle_unite"])
                cr = _req_pos("coef_roulement", config["coef_roulement"], strict=False)
                cda = _req_pos("cda", config["cda"], strict=False)
                rho_air = _req_pos("densite_air", config["densite_air"], strict=True)
                eta_trans = _req_ratio_0_1("eta_transmission", config["eta_transmission"], strict_min=True)
                eta_mot = _req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True)

                pertes_meca = _req_pos("pertes_meca_fixes_w", config.get("pertes_meca_fixes_w", 0.0), strict=False)
                pertes_elec = _req_pos("pertes_elec_fixes_w", config.get("pertes_elec_fixes_w", 0.0), strict=False)

                vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                def p_elec_requise(v: float) -> float:
                    forces = calcul_force_resistance_totale(
                        masse_kg=m,
                        vitesse_ms=v,
                        angle_pente=angle_pente,
                        coef_roulement=cr,
                        coef_trainee_aero_cda=cda,
                        densite_air=rho_air,
                        gravite=_G0,
                        angle_unite=angle_unite,
                        oppose_mouvement=True,
                        use_speed_sign=False,
                        return_details=False,
                    )
                    F_tot = float(forces["F_totale"])
                    P_roue = float(calcul_puissance_roue(F_tot, v, use_abs_speed=True, clamp_non_negative=True))
                    P_meca_moteur = float(
                        calcul_puissance_moteur_electrique(
                            puissance_roue_w=P_roue,
                            rendement_transmission=eta_trans,
                            pertes_fixes_w=pertes_meca,
                            clamp_non_negative=True,
                        )
                    )
                    P_elec = 0.0 if P_meca_moteur == 0.0 else (P_meca_moteur / eta_mot)
                    P_elec += pertes_elec
                    return float(P_elec)

                v_sol = _bisect_monotone(p_elec_requise, Pdispo, 0.0, vmax)
                forces_sol = calcul_force_resistance_totale(
                    masse_kg=m,
                    vitesse_ms=v_sol,
                    angle_pente=angle_pente,
                    coef_roulement=cr,
                    coef_trainee_aero_cda=cda,
                    densite_air=rho_air,
                    gravite=_G0,
                    angle_unite=angle_unite,
                    oppose_mouvement=True,
                    use_speed_sign=False,
                    return_details=False,
                )
                F_tot = float(forces_sol["F_totale"])
                P_roue = float(calcul_puissance_roue(F_tot, v_sol, use_abs_speed=True, clamp_non_negative=True))
                P_meca_moteur = float(
                    calcul_puissance_moteur_electrique(
                        puissance_roue_w=P_roue,
                        rendement_transmission=eta_trans,
                        pertes_fixes_w=pertes_meca,
                        clamp_non_negative=True,
                    )
                )

                out: Dict[str, Any] = {
                    "vitesse_ms": float(v_sol),
                    "vitesse_kmh": float(v_sol * 3.6),
                    "F_totale_N": float(F_tot),
                    "F_roulement_N": float(forces_sol["F_roulement"]),
                    "F_aero_N": float(forces_sol["F_aero"]),
                    "F_pente_N": float(forces_sol["F_pente"]),
                    "P_roue_W": float(P_roue),
                    "P_moteur_meca_W": float(P_meca_moteur),
                    "P_elec_W": float(p_elec_requise(v_sol)),
                    "conso_Wh_km": float(_wh_per_km_from_p_v(p_elec_requise(v_sol), v_sol)) if v_sol > 0 else 0.0,
                }

                # Couples si rayon roue fourni
                if "rayon_roue_m" in config:
                    R = _req_pos("rayon_roue_m", config["rayon_roue_m"], strict=True)
                    T_roue_total = float(calcul_couple_roue_total(F_tot, R, clamp_non_negative=True))
                    out["couple_roue_total_Nm"] = T_roue_total

                    if "nb_roues_motrices" in config:
                        n = int(config["nb_roues_motrices"])
                        out["couple_par_roue_Nm"] = float(calcul_couple_par_roue(T_roue_total, n))
                    else:
                        _push_inc(rapport, "partielles", "couple_par_roue_Nm", "Calculable si nb_roues_motrices est fourni.")

                    if "rapport_reduction_global" in config:
                        G = _req_pos("rapport_reduction_global", config["rapport_reduction_global"], strict=True)
                        out["rpm_roue"] = float(rad_s_to_rpm(v_sol / R))
                        out["rpm_moteur"] = float(rad_s_to_rpm((v_sol / R) * G))
                        out["couple_moteur_Nm_estime"] = float(
                            calcul_couple_moteur(
                                couple_roue_nm=T_roue_total,
                                rapport_reduction_global=G,
                                rendement_transmission=eta_trans,
                                couple_pertes_nm=_req_pos("couple_pertes_nm", config.get("couple_pertes_nm", 0.0), strict=False),
                                clamp_non_negative=True,
                            )
                        )
                    else:
                        _push_inc(rapport, "partielles", "rpm/couple_moteur", "Calculables si rapport_reduction_global est fourni.")
                else:
                    _push_inc(rapport, "partielles", "couples", "Calculables si rayon_roue_m est fourni.")

                rapport["resultats"]["routier"] = out

            # Accélération max par adhérence (si params complets)
            req_acc = ["mu_adherence", "hauteur_cg_m", "empattement_m", "lr_m", "lf_m", "type_milieu"]
            miss_acc = [k for k in req_acc if k not in config]
            if miss_acc:
                _push_inc(rapport, "partielles", "acceleration_max_adhérence", f"Calculable si config contient: {miss_acc}")
            else:
                m = _req_pos("masse_kg", config["masse_kg"], strict=True)

                # Fres(v=0) : utile pour a_max au démarrage
                forces0 = calcul_force_resistance_totale(
                    masse_kg=m,
                    vitesse_ms=0.0,
                    angle_pente=_req_finite("angle_pente", config["angle_pente"]),
                    coef_roulement=_req_pos("coef_roulement", config["coef_roulement"], strict=False),
                    coef_trainee_aero_cda=_req_pos("cda", config["cda"], strict=False),
                    densite_air=_req_pos("densite_air", config["densite_air"], strict=True),
                    gravite=_G0,
                    angle_unite=str(config["angle_unite"]),
                    oppose_mouvement=True,
                    use_speed_sign=False,
                    return_details=False,
                )
                Fres0 = float(forces0["F_totale"])

                h = _req_pos("hauteur_cg_m", config["hauteur_cg_m"], strict=False)
                L = _req_pos("empattement_m", config["empattement_m"], strict=True)
                lr = _req_pos("lr_m", config["lr_m"], strict=False)
                lf = _req_pos("lf_m", config["lf_m"], strict=False)

                charges = calcul_charges_essieux(
                    masse_kg=m,
                    acceleration_ms2=0.0,
                    angle_pente=_req_finite("angle_pente", config["angle_pente"]),
                    empattement_l_m=L,
                    dist_cg_arriere_lr_m=lr,
                    dist_cg_avant_lf_m=lf,
                    hauteur_cg_h_m=h,
                    angle_unite=str(config["angle_unite"]),
                    clamp_non_negative=True,
                    check_consistance=True,
                    return_details=False,
                )
                N_av = float(charges["N_avant"])
                N_ar = float(charges["N_arriere"])

                mode = str(config["type_milieu"]).strip().lower()
                if mode in ("fwd", "avant", "front"):
                    N_drive = N_av
                    mode_norm = "FWD"
                elif mode in ("rwd", "arriere", "arrière", "rear"):
                    N_drive = N_ar
                    mode_norm = "RWD"
                elif mode in ("awd", "4wd", "4x4", "integral", "intégral"):
                    N_drive = N_av + N_ar
                    mode_norm = "AWD"
                else:
                    raise ValueError("type_milieu invalide (fwd/rwd/awd).")

                a_max = float(
                    calcul_acceleration_max(
                        mu_adherence=_req_pos("mu_adherence", config["mu_adherence"], strict=False),
                        charge_essieu_moteur_n=N_drive,
                        force_resistance_n=Fres0,
                        masse_kg=m,
                        hauteur_cg_m=h,
                        empattement_m=L,
                        type_milieu=mode_norm,
                        include_transfert=True,
                        clamp_non_negative=True,
                    )
                )
                rapport["resultats"]["routier_accel_adh"] = {
                    "F_resistance_v0_N": Fres0,
                    "N_avant_N": N_av,
                    "N_arriere_N": N_ar,
                    "N_drive_N": N_drive,
                    "a_max_ms2": a_max,
                    "F_traction_max_N": (m * a_max + Fres0),
                }

        # ---------------------------------------------------------------------
        # MULTI-DOMAINES : inversion vitesse depuis puissance (si modules présents)
        # Aucun coefficient "typique" : tout vient du config.
        # ---------------------------------------------------------------------
        if domaine in ("nautique", "aerien", "ferroviaire"):
            if domaine == "nautique":
                if _md_nautique is None:
                    _push_inc(rapport, "impossibles", "nautique", "Module calcul_multi_domaine (nautique) absent.")
                else:
                    req = ["surface_mouillee_m2", "cw_coque", "rho_eau_kg_m3", "eta_helice", "eta_moteur", "v_max_recherche_ms"]
                    miss = [k for k in req if k not in config]
                    if miss:
                        _push_inc(rapport, "impossibles", "nautique", f"Paramètres manquants: {miss}")
                    else:
                        vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                        def p_elec(v: float) -> float:
                            r = _md_nautique(
                                vitesse_ms=v,
                                surface_mouillee_m2=_req_pos("surface_mouillee_m2", config["surface_mouillee_m2"], strict=False),
                                cw_coque=_req_pos("cw_coque", config["cw_coque"], strict=False),
                                rho_eau_kg_m3=_req_pos("rho_eau_kg_m3", config["rho_eau_kg_m3"], strict=True),
                                eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                                eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                            )
                            return float(r["puissance_elec_W"])

                        v_sol = _bisect_monotone(p_elec, Pdispo, 0.0, vmax)
                        rsol = _md_nautique(
                            vitesse_ms=v_sol,
                            surface_mouillee_m2=_req_pos("surface_mouillee_m2", config["surface_mouillee_m2"], strict=False),
                            cw_coque=_req_pos("cw_coque", config["cw_coque"], strict=False),
                            rho_eau_kg_m3=_req_pos("rho_eau_kg_m3", config["rho_eau_kg_m3"], strict=True),
                            eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                            eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                            eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                        )
                        rapport["resultats"]["nautique"] = {
                            "vitesse_ms": float(v_sol),
                            "vitesse_kmh": float(v_sol * 3.6),
                            "force_N": float(rsol["force_N"]),
                            "puissance_meca_W": float(rsol["puissance_meca_W"]),
                            "puissance_elec_W": float(rsol["puissance_elec_W"]),
                            "conso_Wh_km": float(_wh_per_km_from_p_v(float(rsol["puissance_elec_W"]), v_sol)) if v_sol > 0 else 0.0,
                        }

            if domaine == "aerien":
                if _md_aerien_rho is None:
                    _push_inc(rapport, "impossibles", "aerien", "Module calcul_multi_domaine (aérien) absent.")
                else:
                    # rho_air peut venir directement, ou via pression+température si module dispo
                    req_base = ["s_cx_cellule_m2", "eta_helice", "eta_moteur", "v_max_recherche_ms"]
                    miss_base = [k for k in req_base if k not in config]
                    if miss_base:
                        _push_inc(rapport, "impossibles", "aerien", f"Paramètres manquants: {miss_base}")
                    else:
                        vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                        if "rho_air_kg_m3" in config:
                            rho_air = _req_pos("rho_air_kg_m3", config["rho_air_kg_m3"], strict=True)
                        else:
                            if _md_rho_air_sec is None:
                                _push_inc(
                                    rapport,
                                    "impossibles",
                                    "rho_air_kg_m3",
                                    "Fournir rho_air_kg_m3, ou fournir (pression_pa, temperature_c) + module calcul_densite_air_sec.",
                                )
                                rho_air = None
                            else:
                                if "pression_pa" not in config or "temperature_c" not in config:
                                    _push_inc(
                                        rapport,
                                        "impossibles",
                                        "rho_air_kg_m3",
                                        "Fournir rho_air_kg_m3, ou fournir pression_pa ET temperature_c.",
                                    )
                                    rho_air = None
                                else:
                                    rho_air = float(
                                        _md_rho_air_sec(
                                            pression_pa=_req_pos("pression_pa", config["pression_pa"], strict=True),
                                            temperature_c=_req_finite("temperature_c", config["temperature_c"]),
                                        )
                                    )

                        if rho_air is not None:
                            def p_elec(v: float) -> float:
                                r = _md_aerien_rho(
                                    vitesse_ms=v,
                                    rho_air_kg_m3=rho_air,
                                    s_cx_cellule_m2=_req_pos("s_cx_cellule_m2", config["s_cx_cellule_m2"], strict=False),
                                    eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                                    eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                    eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                                )
                                return float(r["puissance_elec_W"])

                            v_sol = _bisect_monotone(p_elec, Pdispo, 0.0, vmax)
                            rsol = _md_aerien_rho(
                                vitesse_ms=v_sol,
                                rho_air_kg_m3=rho_air,
                                s_cx_cellule_m2=_req_pos("s_cx_cellule_m2", config["s_cx_cellule_m2"], strict=False),
                                eta_helice=_req_ratio_0_1("eta_helice", config["eta_helice"], strict_min=True),
                                eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                eta_transmission=_req_ratio_0_1("eta_transmission", config.get("eta_transmission", 1.0), strict_min=True),
                            )
                            rapport["resultats"]["aerien"] = {
                                "densite_air": float(rsol["densite_air"]),
                                "vitesse_ms": float(v_sol),
                                "vitesse_kmh": float(v_sol * 3.6),
                                "force_N": float(rsol["force_N"]),
                                "puissance_meca_W": float(rsol["puissance_meca_W"]),
                                "puissance_elec_W": float(rsol["puissance_elec_W"]),
                                "conso_Wh_km": float(_wh_per_km_from_p_v(float(rsol["puissance_elec_W"]), v_sol)) if v_sol > 0 else 0.0,
                            }

            if domaine == "ferroviaire":
                if _md_ferro_davis is None:
                    _push_inc(rapport, "impossibles", "ferroviaire", "Module calcul_multi_domaine (ferroviaire) absent.")
                else:
                    req = ["masse_kg", "davis_A_N", "davis_B_N_s_m", "davis_C_N_s2_m2", "eta_moteur", "eta_transmission", "v_max_recherche_ms"]
                    miss = [k for k in req if k not in config]
                    if miss:
                        _push_inc(rapport, "impossibles", "ferroviaire", f"Paramètres manquants: {miss}")
                    else:
                        vmax = _req_pos("v_max_recherche_ms", config["v_max_recherche_ms"], strict=True)

                        def p_elec(v: float) -> float:
                            r = _md_ferro_davis(
                                vitesse_ms=v,
                                masse_kg=_req_pos("masse_kg", config["masse_kg"], strict=True),
                                acceleration_ms2=0.0,
                                davis_A_N=_req_pos("davis_A_N", config["davis_A_N"], strict=False),
                                davis_B_N_s_m=_req_pos("davis_B_N_s_m", config["davis_B_N_s_m"], strict=False),
                                davis_C_N_s2_m2=_req_pos("davis_C_N_s2_m2", config["davis_C_N_s2_m2"], strict=False),
                                eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                                eta_transmission=_req_ratio_0_1("eta_transmission", config["eta_transmission"], strict_min=True),
                            )
                            return float(r["puissance_elec_W"])

                        v_sol = _bisect_monotone(p_elec, Pdispo, 0.0, vmax)
                        rsol = _md_ferro_davis(
                            vitesse_ms=v_sol,
                            masse_kg=_req_pos("masse_kg", config["masse_kg"], strict=True),
                            acceleration_ms2=0.0,
                            davis_A_N=_req_pos("davis_A_N", config["davis_A_N"], strict=False),
                            davis_B_N_s_m=_req_pos("davis_B_N_s_m", config["davis_B_N_s_m"], strict=False),
                            davis_C_N_s2_m2=_req_pos("davis_C_N_s2_m2", config["davis_C_N_s2_m2"], strict=False),
                            eta_moteur=_req_ratio_0_1("eta_moteur", config["eta_moteur"], strict_min=True),
                            eta_transmission=_req_ratio_0_1("eta_transmission", config["eta_transmission"], strict_min=True),
                        )
                        rapport["resultats"]["ferroviaire"] = {
                            "vitesse_ms": float(v_sol),
                            "vitesse_kmh": float(v_sol * 3.6),
                            "force_N": float(rsol["force_N"]),
                            "puissance_meca_W": float(rsol["puissance_meca_W"]),
                            "puissance_elec_W": float(rsol["puissance_elec_W"]),
                            "conso_Wh_km": float(_wh_per_km_from_p_v(float(rsol["puissance_elec_W"]), v_sol)) if v_sol > 0 else 0.0,
                        }

        _dedup_inconnues(rapport)
        return rapport


# =============================================================================
# Convenience: une fonction simple
# =============================================================================

def analyser_depuis_puissance(
    *,
    puissance_elec_dispo_w: float,
    config: Dict[str, Any],
    tension_systeme_v: Optional[float] = None,
) -> Dict[str, Any]:
    return AnalyseDepuisPuissance(tension_systeme_v=tension_systeme_v).analyser(
        puissance_elec_dispo_w=puissance_elec_dispo_w,
        config=config,
    )



# =============================================================================
# Orchestrateur haut niveau du composant moteur électrique
# =============================================================================

def _to_jsonable(value: Any, *, depth: int = 0, max_depth: int = 8) -> Any:
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
            return {"type": type(value).__name__}
    if hasattr(value, "en_dict") and callable(getattr(value, "en_dict")):
        try:
            return _to_jsonable(value.en_dict(), depth=depth + 1, max_depth=max_depth)
        except Exception:
            return {"type": type(value).__name__}
    if hasattr(value, "__dict__"):
        try:
            raw = {k: v for k, v in vars(value).items() if not k.startswith("_") and not callable(v)}
            return {"type": type(value).__name__, "attributs": _to_jsonable(raw, depth=depth + 1, max_depth=max_depth)}
        except Exception:
            pass
    return {"type": type(value).__name__}


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dedup_report(rapport: Dict[str, Any]) -> None:
    inc = rapport.setdefault("inconnues", {})
    for cat in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        out: List[Dict[str, str]] = []
        for item in list(inc.get(cat, []) or []):
            if not isinstance(item, dict):
                continue
            key = (str(item.get("nom", "")), str(item.get("raison", "")))
            if key in seen:
                continue
            seen.add(key)
            out.append({"nom": key[0], "raison": key[1]})
        inc[cat] = out


def _make_piece(cls: Any, payload: Any, moteur: Any, *, nom: str, rapport: Dict[str, Any]) -> Any:
    if payload is None:
        try:
            return cls(moteur=moteur)
        except Exception:
            return None
    if isinstance(payload, cls):
        return payload
    if isinstance(payload, dict):
        data = dict(payload)
        data.setdefault("moteur", moteur)
        try:
            return cls(**data)
        except Exception as exc:
            _push_inc(rapport, "partielles", f"piece_{nom}", f"Instantiation impossible : {exc}")
            return None
    return payload


def construire_moteur_electrique(config: Mapping[str, Any]) -> MoteurElectrique:
    """
    Construit MoteurElectrique depuis un dictionnaire.

    Le dictionnaire peut être directement le bloc moteur, ou contenir :
      - config["moteur_electrique"]
      - config["moteur"]

    Aucune donnée n'est inventée : les champs obligatoires du dataclass restent obligatoires.
    """
    source = _safe_dict(config.get("moteur_electrique")) or _safe_dict(config.get("moteur")) or dict(config)
    allowed = {
        "puissance_max_w",
        "regime_max_rpm",
        "couple_max_nm",
        "regime_base_rpm",
        "rendement_moteur",
        "rendement_transmission",
        "tension_bus_v",
        "courant_max_a",
        "pertes_fixes_w",
    }
    kwargs = {k: source[k] for k in allowed if k in source}
    moteur = MoteurElectrique(**kwargs)

    # Pièces optionnelles : on les rattache après construction du moteur.
    piece_report: Dict[str, Any] = {"inconnues": {"impossibles": [], "partielles": []}}
    rotor_payload = source.get("piece_rotor", source.get("rotor"))
    stator_payload = source.get("piece_stator", source.get("stator"))
    rotor = _make_piece(RotorMoteurElectrique, rotor_payload, moteur, nom="rotor", rapport=piece_report)
    stator = _make_piece(StatorMoteurElectrique, stator_payload, moteur, nom="stator", rapport=piece_report)
    try:
        moteur = replace(moteur, piece_rotor=rotor, piece_stator=stator)
    except Exception:
        pass
    return moteur


def concevoir_moteur_electrique(
    config: Mapping[str, Any],
    *,
    export_json_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """
    Orchestrateur complet du composant moteur électrique.

    Sections reconnues dans config :
      - moteur_electrique / moteur : définition du moteur ;
      - vehicule : point routier à analyser ;
      - verification_demande : marges puissance/couple ;
      - analyse_depuis_puissance : inversion puissance -> vitesse selon domaine ;
      - puissance_elec_dispo_w + config_domaine : variante directe ;
      - adherence : analyse d'accélération max si les paramètres sont fournis.
    """
    rapport: Dict[str, Any] = {
        "composant": "moteur_electrique",
        "imports": _to_jsonable(IMPORT_STATUS),
        "definition": {},
        "analyses": {},
        "synthese": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [
            "Composant calcul-only : aucune valeur véhicule, rendement ou coefficient aérodynamique n'est inventé.",
            "Les calculs routiers et multi-domaines délèguent aux modules spécialisés fournis.",
        ],
    }

    try:
        moteur = construire_moteur_electrique(config)
    except Exception as exc:
        _push_inc(rapport, "impossibles", "construction_moteur_electrique", str(exc))
        _dedup_report(rapport)
        if export_json_path is not None:
            Path(export_json_path).write_text(json.dumps(_to_jsonable(rapport), ensure_ascii=False, indent=2), encoding="utf-8")
        return rapport

    rapport["definition"] = moteur.analyser_definition()
    rapport["synthese"].update(
        {
            "puissance_max_w": moteur.puissance_max_w,
            "puissance_max_kw": moteur.puissance_max_w / 1000.0,
            "regime_max_rpm": moteur.regime_max_rpm,
            "regime_base_rpm": moteur.regime_base_rpm_calcule,
            "couple_max_nm": moteur.couple_max_nm_calcule,
            "tension_bus_v": moteur.tension_bus_v,
            "courant_max_a": moteur.courant_max_a,
            "rendement_moteur": moteur.rendement_moteur,
            "rendement_transmission": moteur.rendement_transmission,
        }
    )

    vehicule = _safe_dict(config.get("vehicule"))
    if vehicule:
        try:
            demande = calcul_demande_moteur_depuis_vehicule(**vehicule)
            rapport["analyses"]["demande_vehicule"] = demande
            verification = _safe_dict(config.get("verification_demande"))
            rapport["analyses"]["verification_moteur_sur_demande"] = verifie_moteur_sur_demande(
                moteur,
                demande,
                marge_puissance=float(verification.get("marge_puissance", 0.0)),
                marge_couple=float(verification.get("marge_couple", 0.0)),
            )
        except Exception as exc:
            _push_inc(rapport, "partielles", "analyse_vehicule", str(exc))
    else:
        _push_inc(rapport, "partielles", "analyse_vehicule", "Fournir config['vehicule'] pour calculer demande roue/moteur.")

    analyse_puissance = _safe_dict(config.get("analyse_depuis_puissance"))
    if not analyse_puissance and "puissance_elec_dispo_w" in config and "config_domaine" in config:
        analyse_puissance = {
            "puissance_elec_dispo_w": config.get("puissance_elec_dispo_w"),
            "config": config.get("config_domaine"),
            "tension_systeme_v": config.get("tension_systeme_v", moteur.tension_bus_v),
        }
    if analyse_puissance:
        try:
            tension = analyse_puissance.get("tension_systeme_v", moteur.tension_bus_v)
            rapport["analyses"]["depuis_puissance"] = analyser_depuis_puissance(
                puissance_elec_dispo_w=analyse_puissance["puissance_elec_dispo_w"],
                config=dict(analyse_puissance.get("config", {})),
                tension_systeme_v=tension,
            )
        except Exception as exc:
            _push_inc(rapport, "partielles", "analyse_depuis_puissance", str(exc))

    adherence = _safe_dict(config.get("adherence"))
    if adherence:
        try:
            rapport["analyses"]["acceleration_max_adherence"] = {
                "a_max_ms2": acceleration_max_par_adherence(**adherence)
            }
        except Exception as exc:
            _push_inc(rapport, "partielles", "acceleration_max_adherence", str(exc))

    # Propagation des inconnues de sous-rapports
    for bloc_name in ("definition",):
        bloc = rapport.get(bloc_name)
        if isinstance(bloc, dict):
            inc = _safe_dict(bloc.get("inconnues"))
            for cat in ("impossibles", "partielles"):
                for item in list(inc.get(cat, []) or []):
                    _push_inc(rapport, cat, f"{bloc_name}::{item.get('nom', '')}", str(item.get("raison", "")))
    for name, bloc in list(_safe_dict(rapport.get("analyses")).items()):
        if isinstance(bloc, dict):
            inc = _safe_dict(bloc.get("inconnues"))
            for cat in ("impossibles", "partielles"):
                for item in list(inc.get(cat, []) or []):
                    _push_inc(rapport, cat, f"{name}::{item.get('nom', '')}", str(item.get("raison", "")))

    _dedup_report(rapport)
    rapport_jsonable = _to_jsonable(rapport)
    if export_json_path is not None:
        Path(export_json_path).write_text(json.dumps(rapport_jsonable, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapport_jsonable


def exporter_rapport_json(rapport: Mapping[str, Any], chemin: str | Path) -> Path:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_jsonable(dict(rapport)), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def en_dict_moteur(moteur: MoteurElectrique) -> Dict[str, Any]:
    return _to_jsonable(moteur)


__all__ = [
    "MoteurElectrique",
    "AnalyseDepuisPuissance",
    "calcul_demande_moteur_depuis_vehicule",
    "verifie_moteur_sur_demande",
    "acceleration_max_par_adherence",
    "analyser_depuis_puissance",
    "construire_moteur_electrique",
    "concevoir_moteur_electrique",
    "exporter_rapport_json",
    "en_dict_moteur",
    "rpm_to_rad_s",
    "rad_s_to_rpm",
]
