# backend/modules/moteur_thermique/calcul_cylindree.py
from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, TypedDict, Union

import numpy as np

Number = Union[int, float]
ArrayLike = Union[Sequence[float], np.ndarray]


# =============================================================================
# Validation (unique, robuste) + utilitaires géométriques
# =============================================================================

def _is_finite_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite_number(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_int_ge(name: str, x: Any, min_value: int = 1) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return x


def _as_1d_float_array(name: str, values: ArrayLike, *, allow_empty: bool = False) -> np.ndarray:
    arr = np.asarray(values, dtype=float).reshape(-1)
    if not allow_empty and arr.size == 0:
        raise ValueError(f"{name} ne peut pas être vide.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} doit contenir uniquement des valeurs finies.")
    return arr


def aire_disque_depuis_diametre(diametre_m: Number, *, allow_zero: bool = False) -> float:
    D = _req_pos("diametre_m", diametre_m, strictly=not allow_zero)
    return (math.pi * (D ** 2)) / 4.0


def rayon_depuis_diametre(diametre_m: Number, *, allow_zero: bool = False) -> float:
    D = _req_pos("diametre_m", diametre_m, strictly=not allow_zero)
    return 0.5 * D


def verifier_hypothese_paroi_mince(
    epaisseur_m: Number,
    rayon_interne_m: Number,
    *,
    ratio_max: float = 0.1,
) -> Dict[str, float]:
    t = _req_pos("epaisseur_m", epaisseur_m, strictly=False)
    ri = _req_pos("rayon_interne_m", rayon_interne_m, strictly=True)
    rmax = _req_pos("ratio_max", ratio_max, strictly=True)
    ratio = t / ri
    return {
        "t_over_ri": ratio,
        "ratio_max": rmax,
        "is_thin_wall": 1.0 if ratio <= rmax else 0.0,
    }


# =============================================================================
# Cylindrée + volumes + ratios
# =============================================================================

def calcul_cylindree_unitaire(
    alesage_m: Number,
    course_m: Number,
    *,
    allow_zero: bool = False,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    B = _req_pos("alesage_m", alesage_m, strictly=not allow_zero)
    S = _req_pos("course_m", course_m, strictly=not allow_zero)

    aire_section = (math.pi * (B ** 2)) / 4.0
    Vd = aire_section * S

    if return_details:
        return {
            "V_d": Vd,
            "alesage_m": B,
            "course_m": S,
            "aire_section_m2": aire_section,
        }
    return Vd


def calcul_cylindree_totale(
    cylindree_unitaire_m3: Number,
    nombre_cylindres: int,
    *,
    allow_zero_cylindres: bool = False,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    V_unit = _req_finite("cylindree_unitaire_m3", cylindree_unitaire_m3)
    N = _req_int_ge("nombre_cylindres", nombre_cylindres, 0 if allow_zero_cylindres else 1)

    V_tot = V_unit * float(N)

    if return_details:
        return {
            "V_tot": V_tot,
            "cylindree_unitaire_m3": V_unit,
            "nombre_cylindres": float(N),
        }
    return V_tot


def calcul_volume_mort(cylindree_unitaire_m3: Number, taux_compression: Number) -> float:
    Vd = _req_pos("cylindree_unitaire_m3", cylindree_unitaire_m3, strictly=True)
    CR = _req_finite("taux_compression", taux_compression)
    if CR <= 1.0:
        raise ValueError(f"taux_compression doit être > 1.0 (reçu: {CR}).")
    return Vd / (CR - 1.0)


def calcul_taux_compression(cylindree_unitaire_m3: Number, volume_mort_m3: Number) -> float:
    Vd = _req_pos("cylindree_unitaire_m3", cylindree_unitaire_m3, strictly=False)
    Vc = _req_pos("volume_mort_m3", volume_mort_m3, strictly=True)
    return (Vd + Vc) / Vc


def calcul_ratio_alesage_course(
    alesage_m: Number,
    course_m: Number,
    return_details: bool = False,
    *,
    tol_carre: float = 0.01,
) -> Union[float, Dict[str, float]]:
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    tol = _req_pos("tol_carre", tol_carre, strictly=True)

    ratio = B / S

    if return_details:
        if abs(ratio - 1.0) < tol:
            arch = 0.0
        elif ratio < 1.0:
            arch = -1.0
        else:
            arch = 1.0

        return {
            "ratio": ratio,
            "architecture_code": arch,
            "alesage_m": B,
            "course_m": S,
            "tol_carre": tol,
        }

    return ratio


# =============================================================================
# Volume cylindre vs angle (utile pour p(theta), PMI, travail)
# =============================================================================

def calcul_volume_cylindre_vs_angle(
    theta_deg: ArrayLike,
    alesage_m: Number,
    course_m: Number,
    *,
    taux_compression: Number,
    longueur_bielle_m: Optional[Number] = None,
    axe_decale_m: Number = 0.0,
    return_details: bool = False,
) -> Union[np.ndarray, Dict[str, Any]]:
    """
    Volume cylindre instantané V(theta).

    - Si longueur_bielle_m est fournie : géométrie exacte bielle-manivelle
    - Sinon : approximation harmonique simple

    Convention :
    - theta = 0° au PMH
    - cycle mécanique 0..360° pour la géométrie pure
    """
    arr_theta_deg = _as_1d_float_array("theta_deg", theta_deg)
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    CR = _req_finite("taux_compression", taux_compression)
    if CR <= 1.0:
        raise ValueError("taux_compression doit être > 1.")

    A = aire_disque_depuis_diametre(B)
    Vd = A * S
    Vc = Vd / (CR - 1.0)
    r = 0.5 * S

    theta_mech_deg = np.mod(arr_theta_deg, 360.0)
    theta_rad = np.deg2rad(theta_mech_deg)

    model_name = "harmonique"
    if longueur_bielle_m is not None:
        L = _req_pos("longueur_bielle_m", longueur_bielle_m, strictly=True)
        e = _req_finite("axe_decale_m", axe_decale_m)
        if abs(e) >= L:
            raise ValueError("abs(axe_decale_m) doit être < longueur_bielle_m.")
        if r + abs(e) >= L:
            raise ValueError("géométrie impossible : r + |axe_decale_m| doit être < L.")

        s = r * np.sin(theta_rad) - e
        g2 = np.clip(L ** 2 - s ** 2, 1e-18, None)
        g = np.sqrt(g2)
        y = r * np.cos(theta_rad) + g
        y_tdc = r + math.sqrt(max(L ** 2 - e ** 2, 1e-18))
        x = y_tdc - y
        model_name = "bielle_manivelle_exact"
    else:
        x = 0.5 * S * (1.0 - np.cos(theta_rad))

    V = Vc + A * x

    if return_details:
        return {
            "theta_deg": arr_theta_deg.copy(),
            "volume_m3": V,
            "deplacement_piston_m": x,
            "alesage_m": B,
            "course_m": S,
            "aire_piston_m2": A,
            "cylindree_unitaire_m3": Vd,
            "volume_mort_m3": Vc,
            "modele_volume": model_name,
        }
    return V


# =============================================================================
# Force gaz sur piston
# =============================================================================

def calcul_force_gaz(
    pression_pa: Number,
    alesage_m: Number,
    *,
    allow_negative_pression: bool = True,
    allow_zero_alesage: bool = False,
    clamp_non_negative: bool = False,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    p = _req_finite("pression_pa", pression_pa)
    if (not allow_negative_pression) and p < 0.0:
        raise ValueError("pression_pa ne peut pas être négative (allow_negative_pression=False).")

    B = _req_pos("alesage_m", alesage_m, strictly=not allow_zero_alesage)

    aire_piston = (math.pi * (B ** 2)) / 4.0
    F = p * aire_piston

    if clamp_non_negative:
        F = max(0.0, F)

    if return_details:
        return {
            "F_g": F,
            "pression_pa": p,
            "alesage_m": B,
            "aire_piston_m2": aire_piston,
        }
    return F


def calcul_force_gaz_vs_angle(
    pression_pa: ArrayLike,
    alesage_m: Number,
    *,
    return_details: bool = False,
) -> Union[np.ndarray, Dict[str, Any]]:
    p = _as_1d_float_array("pression_pa", pression_pa)
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    A = aire_disque_depuis_diametre(B)
    F = p * A

    if return_details:
        return {
            "force_gaz_n": F,
            "pression_pa": p.copy(),
            "aire_piston_m2": A,
            "alesage_m": B,
        }
    return F


# =============================================================================
# Épaisseur paroi cylindre (mince / Lamé)
# =============================================================================

def calcul_epaisseur_cylindre_mince(
    pression_pa: Number,
    rayon_interne_m: Number,
    contrainte_admissible_pa: Number,
    *,
    include_longitudinale: bool = False,
    facteur_securite: Number = 1.0,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    p = _req_pos("pression_pa", pression_pa, strictly=False)
    ri = _req_pos("rayon_interne_m", rayon_interne_m, strictly=True)
    sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _req_pos("facteur_securite", facteur_securite, strictly=True)

    sigma_eff = sigma_adm / fs

    t_hoop = (p * ri) / sigma_eff if sigma_eff > 0 else float("inf")
    t_long = (p * ri) / (2.0 * sigma_eff) if sigma_eff > 0 else float("inf")

    t_req = max(t_hoop, t_long) if include_longitudinale else t_hoop
    if clamp_non_negative:
        t_req = max(0.0, t_req)

    if return_details:
        return {
            "t": t_req,
            "t_hoop": t_hoop,
            "t_long": t_long,
            "p": p,
            "ri": ri,
            "sigma_adm": sigma_adm,
            "facteur_securite": fs,
            "sigma_eff": sigma_eff,
            "include_longitudinale": 1.0 if include_longitudinale else 0.0,
        }
    return t_req


def calcul_epaisseur_cylindre_lame(
    pression_interne_pa: Number,
    rayon_interne_m: Number,
    contrainte_admissible_pa: Number,
    *,
    facteur_securite: Number = 1.0,
    epsilon: Number = 1e-12,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    p = _req_pos("pression_interne_pa", pression_interne_pa, strictly=False)
    ri = _req_pos("rayon_interne_m", rayon_interne_m, strictly=True)
    sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _req_pos("facteur_securite", facteur_securite, strictly=True)
    eps = _req_pos("epsilon", epsilon, strictly=True)

    sigma_eff = sigma_adm / fs

    if sigma_eff <= p + eps:
        raise ValueError(
            "Dimensionnement impossible/instable: il faut sigma_adm/FS > p (avec marge). "
            f"(sigma_eff={sigma_eff}, p={p})"
        )

    ratio = (sigma_eff + p) / (sigma_eff - p)
    if ratio < 1.0:
        raise ValueError("Ratio Lamé inattendu (<1). Vérifie les paramètres.")

    ro = ri * math.sqrt(ratio)
    t = ro - ri

    if clamp_non_negative:
        t = max(0.0, t)

    if return_details:
        return {
            "t": t,
            "ri": ri,
            "ro": ro,
            "p": p,
            "sigma_adm": sigma_adm,
            "facteur_securite": fs,
            "sigma_eff": sigma_eff,
            "ratio": ratio,
        }
    return t


ModeleParoi = Literal["mince", "lame", "auto", "both"]


def calcul_epaisseur_paroi_depuis_alesage(
    pression_pa: Number,
    alesage_m: Number,
    contrainte_admissible_pa: Number,
    *,
    modele: ModeleParoi = "auto",
    facteur_securite: Number = 1.0,
    include_longitudinale: bool = False,
    epsilon: Number = 1e-12,
    ratio_mince_max: float = 0.1,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    p = _req_pos("pression_pa", pression_pa, strictly=False)
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
    fs = _req_pos("facteur_securite", facteur_securite, strictly=True)
    rmax = _req_pos("ratio_mince_max", ratio_mince_max, strictly=True)

    ri = 0.5 * B

    d_mince = calcul_epaisseur_cylindre_mince(
        p,
        ri,
        sigma_adm,
        include_longitudinale=include_longitudinale,
        facteur_securite=fs,
        return_details=True,
    )
    assert isinstance(d_mince, dict)
    t_mince = float(d_mince["t"])
    t_over_ri = (t_mince / ri) if ri > 0 else float("inf")

    out: Dict[str, float] = {
        "alesage_m": B,
        "rayon_interne_m": ri,
        "pression_pa": p,
        "contrainte_admissible_pa": sigma_adm,
        "facteur_securite": float(fs),
        "t_mince_m": t_mince,
        "t_over_ri_mince": t_over_ri,
        "ratio_mince_max": float(rmax),
    }

    t_lame: Optional[float] = None
    try:
        tmp = calcul_epaisseur_cylindre_lame(
            p,
            ri,
            sigma_adm,
            facteur_securite=fs,
            epsilon=epsilon,
            return_details=True,
        )
        assert isinstance(tmp, dict)
        t_lame = float(tmp["t"])
        out.update(
            {
                "t_lame_m": t_lame,
                "ro_lame_m": float(tmp["ro"]),
                "ratio_lame": float(tmp["ratio"]),
            }
        )
    except ValueError:
        pass

    if modele == "mince":
        return out if return_details else t_mince

    if modele == "lame":
        if t_lame is None:
            raise ValueError("Calcul Lamé impossible avec ces paramètres (sigma_eff <= p).")
        return out if return_details else t_lame

    if modele == "both":
        if t_lame is None:
            out["t_lame_m"] = float("nan")
        return out

    if t_over_ri <= rmax:
        out["modele_auto"] = 0.0
        return out if return_details else t_mince

    if t_lame is None:
        raise ValueError("Auto: paroi mince non valide (t/ri trop grand) et Lamé impossible (sigma_eff <= p).")
    out["modele_auto"] = 1.0
    return out if return_details else t_lame


# =============================================================================
# Vrai modèle de pression cylindre
# =============================================================================

ModelePression = Literal["csv", "wiebe", "enveloppe", "tableau"]


@dataclass(frozen=True)
class CourbePressionMesuree:
    theta_deg: np.ndarray
    pression_pa: np.ndarray
    source: str = ""

    def __post_init__(self) -> None:
        theta = _as_1d_float_array("theta_deg", self.theta_deg)
        pression = _as_1d_float_array("pression_pa", self.pression_pa)
        if theta.size != pression.size:
            raise ValueError("theta_deg et pression_pa doivent avoir la même taille.")
        if theta.size < 2:
            raise ValueError("Une courbe mesurée doit contenir au moins 2 points.")
        if np.any(np.diff(theta) <= 0.0):
            raise ValueError("theta_deg doit être strictement croissant.")
        object.__setattr__(self, "theta_deg", theta)
        object.__setattr__(self, "pression_pa", pression)


@dataclass(frozen=True)
class ParametresWiebe:
    pression_admission_pa: float
    pression_echappement_pa: float
    taux_compression: float

    n_compression: float = 1.32
    n_detente: float = 1.25

    theta_admission_ouvre_deg: float = 360.0
    theta_admission_ferme_deg: float = 540.0
    theta_echappement_ouvre_deg: float = 180.0
    theta_echappement_ferme_deg: float = 360.0

    theta_combustion_debut_deg: float = 700.0
    duree_combustion_deg: float = 40.0

    wiebe_a: float = 5.0
    wiebe_m: float = 2.0

    pression_pic_pa: Optional[float] = None
    facteur_pic_sur_motored: Optional[float] = None

    def __post_init__(self) -> None:
        _req_pos("pression_admission_pa", self.pression_admission_pa, strictly=False)
        _req_pos("pression_echappement_pa", self.pression_echappement_pa, strictly=False)
        cr = _req_finite("taux_compression", self.taux_compression)
        if cr <= 1.0:
            raise ValueError("taux_compression doit être > 1.")
        _req_pos("n_compression", self.n_compression, strictly=True)
        _req_pos("n_detente", self.n_detente, strictly=True)
        _req_pos("duree_combustion_deg", self.duree_combustion_deg, strictly=True)
        _req_pos("wiebe_a", self.wiebe_a, strictly=True)
        _req_pos("wiebe_m", self.wiebe_m, strictly=True)
        if self.pression_pic_pa is None and self.facteur_pic_sur_motored is None:
            raise ValueError(
                "Il faut fournir soit pression_pic_pa, soit facteur_pic_sur_motored "
                "pour le modèle Wiebe."
            )
        if self.pression_pic_pa is not None:
            _req_pos("pression_pic_pa", self.pression_pic_pa, strictly=True)
        if self.facteur_pic_sur_motored is not None:
            _req_pos("facteur_pic_sur_motored", self.facteur_pic_sur_motored, strictly=True)


@dataclass(frozen=True)
class CasChargePression:
    nom: str
    regime_tr_min: float
    temperature_gaz_k: Optional[float] = None
    facteur_fatigue: Optional[float] = None
    facteur_thermique: Optional[float] = None
    commentaire: str = ""

    mode: ModelePression = "enveloppe"

    # csv / tableau
    courbe_mesuree: Optional[CourbePressionMesuree] = None
    theta_deg: Optional[ArrayLike] = None
    pression_pa: Optional[ArrayLike] = None

    # wiebe
    modele_wiebe: Optional[ParametresWiebe] = None

    # enveloppe conservatrice
    pression_constante_pa: Optional[float] = None
    pression_max_pa: Optional[float] = None
    angle_pic_deg: float = 5.0
    largeur_pic_deg: float = 18.0
    pression_admission_pa: float = 101325.0
    pression_echappement_pa: float = 101325.0
    forme_pic: Literal["gaussienne", "triangle"] = "gaussienne"

    def __post_init__(self) -> None:
        _req_pos("regime_tr_min", self.regime_tr_min, strictly=True)
        if self.temperature_gaz_k is not None:
            _req_pos("temperature_gaz_k", self.temperature_gaz_k, strictly=True)
        if self.facteur_fatigue is not None:
            _req_pos("facteur_fatigue", self.facteur_fatigue, strictly=True)
        if self.facteur_thermique is not None:
            _req_pos("facteur_thermique", self.facteur_thermique, strictly=True)

        if self.mode == "csv":
            if self.courbe_mesuree is None:
                raise ValueError("mode='csv' requiert courbe_mesuree.")
        elif self.mode == "tableau":
            if self.theta_deg is None or self.pression_pa is None:
                raise ValueError("mode='tableau' requiert theta_deg et pression_pa.")
        elif self.mode == "wiebe":
            if self.modele_wiebe is None:
                raise ValueError("mode='wiebe' requiert modele_wiebe.")
        elif self.mode == "enveloppe":
            if self.pression_constante_pa is None and self.pression_max_pa is None:
                raise ValueError(
                    "mode='enveloppe' requiert pression_constante_pa ou pression_max_pa."
                )
            if self.pression_constante_pa is not None:
                _req_pos("pression_constante_pa", self.pression_constante_pa, strictly=False)
            if self.pression_max_pa is not None:
                _req_pos("pression_max_pa", self.pression_max_pa, strictly=False)
            _req_pos("largeur_pic_deg", self.largeur_pic_deg, strictly=True)
            _req_pos("pression_admission_pa", self.pression_admission_pa, strictly=False)
            _req_pos("pression_echappement_pa", self.pression_echappement_pa, strictly=False)
        else:
            raise ValueError(f"mode de pression inconnu: {self.mode!r}")


class ResultatPressionCase(TypedDict, total=False):
    nom: str
    modele_pression: str
    regime_tr_min: float
    temperature_gaz_k: float
    facteur_fatigue: float
    facteur_thermique: float
    theta_deg: List[float]
    pression_cylindre_pa: List[float]
    volume_cylindre_m3: List[float]
    force_gaz_n: List[float]
    pression_min_pa: float
    pression_max_pa: float
    pression_moyenne_pa: float
    force_gaz_max_n: float
    force_gaz_min_n: float
    force_gaz_moyenne_n: float
    travail_indique_cycle_j: float
    pmi_pa: float
    cas_dimensionnant_pression: float
    cas_dimensionnant_force: float
    commentaire: str


def charger_courbe_pression_csv(
    chemin_csv: Union[str, Path],
    *,
    colonne_angle: str = "angle_deg",
    colonne_pression: str = "pression_pa",
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> CourbePressionMesuree:
    path = Path(chemin_csv)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")

    theta: List[float] = []
    pression: List[float] = []

    with path.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("CSV sans en-tête.")
        if colonne_angle not in reader.fieldnames or colonne_pression not in reader.fieldnames:
            raise ValueError(
                f"Le CSV doit contenir les colonnes {colonne_angle!r} et {colonne_pression!r}."
            )
        for idx, row in enumerate(reader, start=2):
            try:
                a = float(row[colonne_angle])
                p = float(row[colonne_pression])
            except Exception as exc:
                raise ValueError(f"Ligne {idx}: angle/pression illisible.") from exc
            if not math.isfinite(a) or not math.isfinite(p):
                raise ValueError(f"Ligne {idx}: angle/pression non finis.")
            theta.append(a)
            pression.append(p)

    return CourbePressionMesuree(
        theta_deg=np.asarray(theta, dtype=float),
        pression_pa=np.asarray(pression, dtype=float),
        source=str(path),
    )


def _interpoler_courbe_pression(
    theta_deg: np.ndarray,
    courbe: CourbePressionMesuree,
) -> np.ndarray:
    theta_query = np.asarray(theta_deg, dtype=float).reshape(-1)
    theta_src = courbe.theta_deg
    p_src = courbe.pression_pa

    x_min = float(theta_src[0])
    x_max = float(theta_src[-1])

    if x_max <= x_min:
        raise ValueError("Courbe mesurée invalide: angle non croissant.")

    period = x_max - x_min
    if period <= 0.0:
        raise ValueError("Période de courbe mesurée invalide.")

    # Repli périodique dans [x_min, x_max]
    x = ((theta_query - x_min) % period) + x_min
    return np.interp(x, theta_src, p_src)


def _wiebe_fraction_brulee(
    theta_deg: np.ndarray,
    *,
    theta0_deg: float,
    delta_deg: float,
    a: float,
    m: float,
) -> np.ndarray:
    x = np.zeros_like(theta_deg, dtype=float)
    end = theta0_deg + delta_deg

    mask_mid = (theta_deg >= theta0_deg) & (theta_deg <= end)
    mask_high = theta_deg > end

    tau = np.zeros_like(theta_deg, dtype=float)
    tau[mask_mid] = (theta_deg[mask_mid] - theta0_deg) / delta_deg
    x[mask_mid] = 1.0 - np.exp(-a * (tau[mask_mid] ** (m + 1.0)))
    x[mask_high] = 1.0
    return np.clip(x, 0.0, 1.0)


def calcul_pression_cylindre_modele_wiebe(
    theta_deg: ArrayLike,
    alesage_m: Number,
    course_m: Number,
    *,
    parametres: ParametresWiebe,
    longueur_bielle_m: Optional[Number] = None,
    axe_decale_m: Number = 0.0,
    return_details: bool = False,
) -> Union[np.ndarray, Dict[str, Any]]:
    """
    Modèle semi-physique explicite :
    - admission simplifiée
    - compression polytropique
    - combustion Wiebe explicite
    - détente polytropique
    - échappement simplifié

    Important :
    - theta_combustion_debut_deg est exprimé sur le cycle 0..720°
    - la combustion peut traverser 720° / 0°
    - pression_pic_pa représente ici la pression cible maximale pendant la combustion
      si elle est fournie explicitement
    """
    arr_theta_deg = _as_1d_float_array("theta_deg", theta_deg)

    vol_details = calcul_volume_cylindre_vs_angle(
        arr_theta_deg,
        alesage_m,
        course_m,
        taux_compression=parametres.taux_compression,
        longueur_bielle_m=longueur_bielle_m,
        axe_decale_m=axe_decale_m,
        return_details=True,
    )
    assert isinstance(vol_details, dict)
    V = np.asarray(vol_details["volume_m3"], dtype=float)

    A = aire_disque_depuis_diametre(_req_pos("alesage_m", alesage_m, strictly=True))
    S = _req_pos("course_m", course_m, strictly=True)
    Vd = A * S
    Vc = Vd / (parametres.taux_compression - 1.0)
    Vbdc = Vc + Vd

    theta = np.mod(arr_theta_deg, 720.0)
    p = np.empty_like(theta, dtype=float)

    mask_ech = (theta >= 180.0) & (theta < 360.0)
    mask_adm = (theta >= 360.0) & (theta < 540.0)

    # Dépliage du cycle pour gérer correctement une combustion qui traverse 720/0
    theta0 = float(parametres.theta_combustion_debut_deg)
    theta_end = theta0 + float(parametres.duree_combustion_deg)

    theta_u = theta.copy()
    wrap_limit = theta0 % 720.0
    theta_u[theta < wrap_limit] += 720.0

    # Pression motored compression
    p_motored = np.full_like(theta, parametres.pression_admission_pa, dtype=float)
    mask_comp_or_comb = (theta_u >= 540.0) & (theta_u <= theta_end)
    p_motored[mask_comp_or_comb] = (
        parametres.pression_admission_pa * (Vbdc / V[mask_comp_or_comb]) ** parametres.n_compression
    )

    p_tdc_motored = float(parametres.pression_admission_pa * (Vbdc / Vc) ** parametres.n_compression)

    if parametres.pression_pic_pa is not None:
        p_peak_target = float(parametres.pression_pic_pa)
    else:
        p_peak_target = float(p_tdc_motored * float(parametres.facteur_pic_sur_motored))

    xb = _wiebe_fraction_brulee(
        theta_deg=theta_u,
        theta0_deg=theta0,
        delta_deg=parametres.duree_combustion_deg,
        a=parametres.wiebe_a,
        m=parametres.wiebe_m,
    )

    mask_comb = (theta_u >= theta0) & (theta_u <= theta_end)
    mask_post_comb_exp = (theta_u > theta_end) & (theta_u < 900.0)

    # Base par défaut
    p[mask_ech] = parametres.pression_echappement_pa
    p[mask_adm] = parametres.pression_admission_pa

    # Compression avant combustion
    mask_pre_comb = (theta_u >= 540.0) & (theta_u < theta0)
    p[mask_pre_comb] = p_motored[mask_pre_comb]

    # Combustion explicite Wiebe, pression plafonnée par p_peak_target
    p_comb = p_motored + xb * (p_peak_target - p_motored)
    p[mask_comb] = np.minimum(p_comb[mask_comb], p_peak_target)

    # Référence de détente à la fin de combustion
    V_end = float(
        calcul_volume_cylindre_vs_angle(
            [theta_end],
            alesage_m,
            course_m,
            taux_compression=parametres.taux_compression,
            longueur_bielle_m=longueur_bielle_m,
            axe_decale_m=axe_decale_m,
            return_details=False,
        )[0]
    )
    xb_end = float(1.0 - math.exp(-parametres.wiebe_a * (1.0 ** (parametres.wiebe_m + 1.0))))
    p_motored_end = float(parametres.pression_admission_pa * (Vbdc / V_end) ** parametres.n_compression)
    p_end = min(p_motored_end + xb_end * (p_peak_target - p_motored_end), p_peak_target)

    p[mask_post_comb_exp] = p_end * (V_end / V[mask_post_comb_exp]) ** parametres.n_detente

    # Sécurité logique sur zones non couvertes
    mask_unset = ~(mask_ech | mask_adm | mask_pre_comb | mask_comb | mask_post_comb_exp)
    p[mask_unset] = parametres.pression_admission_pa

    if return_details:
        return {
            "theta_deg": arr_theta_deg.copy(),
            "pression_pa": p,
            "volume_m3": V,
            "fraction_brulee": xb,
            "pression_tdc_motored_pa": p_tdc_motored,
            "pression_pic_cible_pa": p_peak_target,
            "pression_fin_combustion_pa": p_end,
            "theta_combustion_debut_deg": theta0,
            "theta_combustion_fin_deg": theta_end,
            "modele_volume": vol_details["modele_volume"],
        }
    return p


def calcul_pression_cylindre_enveloppe(
    theta_deg: ArrayLike,
    *,
    pression_constante_pa: Optional[Number] = None,
    pression_max_pa: Optional[Number] = None,
    angle_pic_deg: Number = 5.0,
    largeur_pic_deg: Number = 18.0,
    pression_admission_pa: Number = 101325.0,
    pression_echappement_pa: Number = 101325.0,
    forme_pic: Literal["gaussienne", "triangle"] = "gaussienne",
    return_details: bool = False,
) -> Union[np.ndarray, Dict[str, Any]]:
    theta = np.mod(_as_1d_float_array("theta_deg", theta_deg), 720.0)
    p_adm = _req_pos("pression_admission_pa", pression_admission_pa, strictly=False)
    p_ech = _req_pos("pression_echappement_pa", pression_echappement_pa, strictly=False)
    width = _req_pos("largeur_pic_deg", largeur_pic_deg, strictly=True)
    angle_peak = _req_finite("angle_pic_deg", angle_pic_deg)

    p = np.empty_like(theta, dtype=float)

    mask_det = (theta >= 0.0) & (theta < 180.0)
    mask_ech = (theta >= 180.0) & (theta < 360.0)
    mask_adm = (theta >= 360.0) & (theta < 540.0)
    mask_comp = (theta >= 540.0) & (theta <= 720.0)

    if pression_constante_pa is not None:
        p_const = _req_pos("pression_constante_pa", pression_constante_pa, strictly=False)
        p[:] = p_const
    else:
        if pression_max_pa is None:
            raise ValueError("pression_max_pa requis si pression_constante_pa est absente.")
        pmax = _req_pos("pression_max_pa", pression_max_pa, strictly=False)

        p[mask_ech] = p_ech
        p[mask_adm] = p_adm
        p[mask_comp] = np.linspace(p_adm, pmax, int(mask_comp.sum()), endpoint=True)

        if forme_pic == "gaussienne":
            sigma = width / max(2.355, 1e-12)
            p_det = p_adm + (pmax - p_adm) * np.exp(-0.5 * ((theta[mask_det] - angle_peak) / sigma) ** 2)
        elif forme_pic == "triangle":
            dist = np.abs(theta[mask_det] - angle_peak)
            p_det = p_adm + (pmax - p_adm) * np.clip(1.0 - dist / width, 0.0, 1.0)
        else:
            raise ValueError(f"forme_pic inconnue: {forme_pic!r}")
        p[mask_det] = np.maximum(p_det, p_adm)

    if return_details:
        return {
            "theta_deg": theta.copy(),
            "pression_pa": p,
            "mode": "enveloppe",
        }
    return p


def construire_pression_cylindre(
    theta_deg: ArrayLike,
    *,
    mode: ModelePression,
    alesage_m: Optional[Number] = None,
    course_m: Optional[Number] = None,
    longueur_bielle_m: Optional[Number] = None,
    axe_decale_m: Number = 0.0,
    courbe_mesuree: Optional[CourbePressionMesuree] = None,
    theta_tableau_deg: Optional[ArrayLike] = None,
    pression_tableau_pa: Optional[ArrayLike] = None,
    parametres_wiebe: Optional[ParametresWiebe] = None,
    pression_constante_pa: Optional[Number] = None,
    pression_max_pa: Optional[Number] = None,
    angle_pic_deg: Number = 5.0,
    largeur_pic_deg: Number = 18.0,
    pression_admission_pa: Number = 101325.0,
    pression_echappement_pa: Number = 101325.0,
    forme_pic: Literal["gaussienne", "triangle"] = "gaussienne",
    return_details: bool = False,
) -> Union[np.ndarray, Dict[str, Any]]:
    arr_theta_deg = _as_1d_float_array("theta_deg", theta_deg)

    if mode == "csv":
        if courbe_mesuree is None:
            raise ValueError("mode='csv' requiert courbe_mesuree.")
        p = _interpoler_courbe_pression(arr_theta_deg, courbe_mesuree)
        if return_details:
            return {
                "theta_deg": arr_theta_deg.copy(),
                "pression_pa": p,
                "mode": "csv",
                "source": courbe_mesuree.source,
            }
        return p

    if mode == "tableau":
        if theta_tableau_deg is None or pression_tableau_pa is None:
            raise ValueError("mode='tableau' requiert theta_tableau_deg et pression_tableau_pa.")
        courbe = CourbePressionMesuree(
            theta_deg=_as_1d_float_array("theta_tableau_deg", theta_tableau_deg),
            pression_pa=_as_1d_float_array("pression_tableau_pa", pression_tableau_pa),
            source="tableau_interne",
        )
        p = _interpoler_courbe_pression(arr_theta_deg, courbe)
        if return_details:
            return {
                "theta_deg": arr_theta_deg.copy(),
                "pression_pa": p,
                "mode": "tableau",
            }
        return p

    if mode == "wiebe":
        if parametres_wiebe is None:
            raise ValueError("mode='wiebe' requiert parametres_wiebe.")
        if alesage_m is None or course_m is None:
            raise ValueError("mode='wiebe' requiert alesage_m et course_m.")
        return calcul_pression_cylindre_modele_wiebe(
            arr_theta_deg,
            alesage_m,
            course_m,
            parametres=parametres_wiebe,
            longueur_bielle_m=longueur_bielle_m,
            axe_decale_m=axe_decale_m,
            return_details=return_details,
        )

    if mode == "enveloppe":
        return calcul_pression_cylindre_enveloppe(
            arr_theta_deg,
            pression_constante_pa=pression_constante_pa,
            pression_max_pa=pression_max_pa,
            angle_pic_deg=angle_pic_deg,
            largeur_pic_deg=largeur_pic_deg,
            pression_admission_pa=pression_admission_pa,
            pression_echappement_pa=pression_echappement_pa,
            forme_pic=forme_pic,
            return_details=return_details,
        )

    raise ValueError(f"mode de pression inconnu: {mode!r}")


# =============================================================================
# Cas de charge
# =============================================================================

def _theta_cycle_720(pas_angle_deg: Number) -> np.ndarray:
    step = _req_pos("pas_angle_deg", pas_angle_deg, strictly=True)
    n = int(round(720.0 / step))
    return np.linspace(0.0, 720.0, n + 1)


def evaluer_cas_charge_cylindre(
    *,
    alesage_m: Number,
    course_m: Number,
    taux_compression: Number,
    cas: CasChargePression,
    pas_angle_deg: Number = 0.5,
    longueur_bielle_m: Optional[Number] = None,
    axe_decale_m: Number = 0.0,
) -> ResultatPressionCase:
    B = _req_pos("alesage_m", alesage_m, strictly=True)
    S = _req_pos("course_m", course_m, strictly=True)
    CR = _req_finite("taux_compression", taux_compression)
    if CR <= 1.0:
        raise ValueError("taux_compression doit être > 1.")

    theta_deg = _theta_cycle_720(pas_angle_deg)

    volume_details = calcul_volume_cylindre_vs_angle(
        theta_deg,
        B,
        S,
        taux_compression=CR,
        longueur_bielle_m=longueur_bielle_m,
        axe_decale_m=axe_decale_m,
        return_details=True,
    )
    assert isinstance(volume_details, dict)
    volume_m3 = np.asarray(volume_details["volume_m3"], dtype=float)

    if cas.mode == "csv":
        assert cas.courbe_mesuree is not None
        p = construire_pression_cylindre(
            theta_deg,
            mode="csv",
            courbe_mesuree=cas.courbe_mesuree,
            return_details=False,
        )
        modele = f"csv:{cas.courbe_mesuree.source or 'courbe_mesuree'}"

    elif cas.mode == "tableau":
        assert cas.theta_deg is not None and cas.pression_pa is not None
        p = construire_pression_cylindre(
            theta_deg,
            mode="tableau",
            theta_tableau_deg=cas.theta_deg,
            pression_tableau_pa=cas.pression_pa,
            return_details=False,
        )
        modele = "tableau"

    elif cas.mode == "wiebe":
        if cas.modele_wiebe is None:
            raise ValueError("cas.mode='wiebe' mais modele_wiebe absent.")
        if not math.isclose(cas.modele_wiebe.taux_compression, CR, rel_tol=1e-12, abs_tol=0.0):
            raise ValueError(
                "Le taux de compression du cas Wiebe doit être cohérent avec celui du cylindre."
            )
        p = construire_pression_cylindre(
            theta_deg,
            mode="wiebe",
            alesage_m=B,
            course_m=S,
            longueur_bielle_m=longueur_bielle_m,
            axe_decale_m=axe_decale_m,
            parametres_wiebe=cas.modele_wiebe,
            return_details=False,
        )
        modele = "wiebe"

    elif cas.mode == "enveloppe":
        p = construire_pression_cylindre(
            theta_deg,
            mode="enveloppe",
            pression_constante_pa=cas.pression_constante_pa,
            pression_max_pa=cas.pression_max_pa,
            angle_pic_deg=cas.angle_pic_deg,
            largeur_pic_deg=cas.largeur_pic_deg,
            pression_admission_pa=cas.pression_admission_pa,
            pression_echappement_pa=cas.pression_echappement_pa,
            forme_pic=cas.forme_pic,
            return_details=False,
        )
        modele = "enveloppe"

    else:
        raise ValueError(f"mode de cas de charge inconnu: {cas.mode!r}")

    p = np.asarray(p, dtype=float)
    F = calcul_force_gaz_vs_angle(p, B, return_details=False)
    F = np.asarray(F, dtype=float)

    # Travail indiqué sur cycle
    travail_j = float(np.trapz(p, volume_m3))
    Vd = calcul_cylindree_unitaire(B, S, allow_zero=False, return_details=False)
    assert isinstance(Vd, float)
    pmi_pa = travail_j / Vd if Vd > 0.0 else float("nan")

    out: ResultatPressionCase = {
        "nom": cas.nom,
        "modele_pression": modele,
        "regime_tr_min": float(cas.regime_tr_min),
        "theta_deg": theta_deg.tolist(),
        "pression_cylindre_pa": p.tolist(),
        "volume_cylindre_m3": volume_m3.tolist(),
        "force_gaz_n": F.tolist(),
        "pression_min_pa": float(np.min(p)),
        "pression_max_pa": float(np.max(p)),
        "pression_moyenne_pa": float(np.mean(p)),
        "force_gaz_max_n": float(np.max(F)),
        "force_gaz_min_n": float(np.min(F)),
        "force_gaz_moyenne_n": float(np.mean(F)),
        "travail_indique_cycle_j": travail_j,
        "pmi_pa": float(pmi_pa),
        "cas_dimensionnant_pression": float(np.max(p)),
        "cas_dimensionnant_force": float(np.max(np.abs(F))),
        "commentaire": cas.commentaire,
    }

    if cas.temperature_gaz_k is not None:
        out["temperature_gaz_k"] = float(cas.temperature_gaz_k)
    if cas.facteur_fatigue is not None:
        out["facteur_fatigue"] = float(cas.facteur_fatigue)
    if cas.facteur_thermique is not None:
        out["facteur_thermique"] = float(cas.facteur_thermique)

    return out


def evaluer_plusieurs_cas_charge_cylindre(
    *,
    alesage_m: Number,
    course_m: Number,
    taux_compression: Number,
    cas_de_charge: Sequence[CasChargePression],
    pas_angle_deg: Number = 0.5,
    longueur_bielle_m: Optional[Number] = None,
    axe_decale_m: Number = 0.0,
) -> Dict[str, Any]:
    if not cas_de_charge:
        raise ValueError("cas_de_charge ne peut pas être vide.")

    results: Dict[str, ResultatPressionCase] = {}
    max_pressure = -float("inf")
    max_force_abs = -float("inf")
    worst_pressure_case = ""
    worst_force_case = ""

    for case in cas_de_charge:
        res = evaluer_cas_charge_cylindre(
            alesage_m=alesage_m,
            course_m=course_m,
            taux_compression=taux_compression,
            cas=case,
            pas_angle_deg=pas_angle_deg,
            longueur_bielle_m=longueur_bielle_m,
            axe_decale_m=axe_decale_m,
        )
        results[case.nom] = res

        pmax = float(res["pression_max_pa"])
        fmax = float(res["cas_dimensionnant_force"])

        if pmax > max_pressure:
            max_pressure = pmax
            worst_pressure_case = case.nom
        if fmax > max_force_abs:
            max_force_abs = fmax
            worst_force_case = case.nom

    return {
        "cas": results,
        "cas_dimensionnant_pression": worst_pressure_case,
        "pression_dimensionnante_pa": max_pressure,
        "cas_dimensionnant_force_gaz": worst_force_case,
        "force_gaz_dimensionnante_n": max_force_abs,
    }


# =============================================================================
# Agrégateur : calcule tout ce qui est calculable avec les entrées disponibles
# =============================================================================

class ResultatCylindre(TypedDict, total=False):
    alesage_m: float
    course_m: float
    nombre_cylindres: float
    aire_section_m2: float
    rayon_interne_m: float

    cylindree_unitaire_m3: float
    cylindree_totale_m3: float
    cylindree_unitaire_l: float
    cylindree_totale_l: float
    cylindree_unitaire_cm3: float
    cylindree_totale_cm3: float

    taux_compression: float
    volume_mort_m3: float
    volume_mort_cm3: float

    ratio_alesage_course: float
    architecture_code: float

    pression_pa: float
    force_gaz_n: float
    aire_piston_m2: float

    contrainte_admissible_pa: float
    facteur_securite: float
    epaisseur_mince_m: float
    epaisseur_lame_m: float
    epaisseur_auto_m: float
    t_over_ri_mince: float
    ratio_mince_max: float

    modele_pression_defaut: str
    pression_cylindre_max_pa: float
    pression_cylindre_moyenne_pa: float
    force_gaz_max_n: float
    travail_indique_cycle_j: float
    pmi_pa: float

    evaluation_cas_charge: Dict[str, Any]

    inconnues: str


def calculer_cylindre_complet(
    *,
    alesage_m: Optional[Number] = None,
    course_m: Optional[Number] = None,
    nombre_cylindres: Optional[int] = None,
    taux_compression: Optional[Number] = None,
    volume_mort_m3: Optional[Number] = None,
    pression_pa: Optional[Number] = None,
    contrainte_admissible_pa: Optional[Number] = None,
    modele_paroi: ModeleParoi = "auto",
    facteur_securite: Number = 1.0,
    include_longitudinale: bool = False,
    ratio_mince_max: float = 0.1,
    epsilon: Number = 1e-12,
    # Nouveau bloc pression
    mode_pression: Optional[ModelePression] = None,
    pas_angle_deg: Number = 0.5,
    longueur_bielle_m: Optional[Number] = None,
    axe_decale_m: Number = 0.0,
    courbe_mesuree: Optional[CourbePressionMesuree] = None,
    theta_tableau_deg: Optional[ArrayLike] = None,
    pression_tableau_pa: Optional[ArrayLike] = None,
    parametres_wiebe: Optional[ParametresWiebe] = None,
    pression_constante_pa: Optional[Number] = None,
    pression_max_pa: Optional[Number] = None,
    angle_pic_deg: Number = 5.0,
    largeur_pic_deg: Number = 18.0,
    pression_admission_pa: Number = 101325.0,
    pression_echappement_pa: Number = 101325.0,
    forme_pic: Literal["gaussienne", "triangle"] = "gaussienne",
    cas_de_charge: Optional[Sequence[CasChargePression]] = None,
) -> ResultatCylindre:
    res: ResultatCylindre = {}
    inconnues: List[str] = []

    B: Optional[float] = None
    S: Optional[float] = None
    N: Optional[int] = None

    if alesage_m is not None:
        B = _req_pos("alesage_m", alesage_m, strictly=True)
        res["alesage_m"] = B
        res["rayon_interne_m"] = 0.5 * B
    else:
        inconnues.append("alesage_m")

    if course_m is not None:
        S = _req_pos("course_m", course_m, strictly=True)
        res["course_m"] = S
    else:
        inconnues.append("course_m")

    if nombre_cylindres is not None:
        N = _req_int_ge("nombre_cylindres", nombre_cylindres, 1)
        res["nombre_cylindres"] = float(N)
    else:
        inconnues.append("nombre_cylindres")

    Vd_unit: Optional[float] = None
    if B is not None:
        aire = (math.pi * (B ** 2)) / 4.0
        res["aire_section_m2"] = aire
        res["aire_piston_m2"] = aire
        if S is not None:
            Vd_unit = aire * S
            res["cylindree_unitaire_m3"] = Vd_unit
            res["cylindree_unitaire_l"] = Vd_unit * 1000.0
            res["cylindree_unitaire_cm3"] = Vd_unit * 1_000_000.0
        else:
            inconnues.append("cylindree_unitaire_m3 (course manquante)")
    else:
        inconnues.append("aire_section_m2 / aire_piston_m2")

    if Vd_unit is not None and N is not None:
        Vtot = Vd_unit * float(N)
        res["cylindree_totale_m3"] = Vtot
        res["cylindree_totale_l"] = Vtot * 1000.0
        res["cylindree_totale_cm3"] = Vtot * 1_000_000.0
    elif Vd_unit is None:
        inconnues.append("cylindree_totale_m3 (cylindree_unitaire manquante)")
    elif N is None:
        inconnues.append("cylindree_totale_m3 (nombre_cylindres manquant)")

    if B is not None and S is not None:
        details = calcul_ratio_alesage_course(B, S, return_details=True)
        assert isinstance(details, dict)
        res["ratio_alesage_course"] = float(details["ratio"])
        res["architecture_code"] = float(details["architecture_code"])
    else:
        inconnues.append("ratio_alesage_course / architecture_code")

    CR: Optional[float] = None
    Vc: Optional[float] = None

    if taux_compression is not None:
        CR = _req_finite("taux_compression", taux_compression)
        if CR <= 1.0:
            raise ValueError(f"taux_compression doit être > 1.0 (reçu: {CR}).")
        res["taux_compression"] = CR

    if volume_mort_m3 is not None:
        Vc = _req_pos("volume_mort_m3", volume_mort_m3, strictly=True)
        res["volume_mort_m3"] = Vc
        res["volume_mort_cm3"] = Vc * 1_000_000.0

    if Vd_unit is not None and CR is not None and Vc is None:
        Vc = Vd_unit / (CR - 1.0)
        res["volume_mort_m3"] = Vc
        res["volume_mort_cm3"] = Vc * 1_000_000.0
    elif Vd_unit is not None and Vc is not None and CR is None:
        CR = (Vd_unit + Vc) / Vc
        res["taux_compression"] = CR
    elif Vd_unit is None and (CR is not None or Vc is not None):
        inconnues.append("compression (cylindree_unitaire requise)")

    if Vd_unit is not None and CR is not None and Vc is not None:
        CR2 = (Vd_unit + Vc) / Vc
        rel = abs(CR2 - CR) / max(abs(CR), 1e-12)
        if rel > 1e-9:
            raise ValueError(f"Incohérence CR/Vc : CR fourni={CR}, CR recalculé={CR2} (rel={rel}).")

    if pression_pa is not None:
        p = _req_finite("pression_pa", pression_pa)
        res["pression_pa"] = p
        if B is not None:
            res["force_gaz_n"] = p * float(res["aire_piston_m2"])
        else:
            inconnues.append("force_gaz_n (alesage manquant)")
    else:
        inconnues.append("pression_pa / force_gaz_n")

    if contrainte_admissible_pa is not None:
        sigma_adm = _req_pos("contrainte_admissible_pa", contrainte_admissible_pa, strictly=True)
        fs = _req_pos("facteur_securite", facteur_securite, strictly=True)
        res["contrainte_admissible_pa"] = sigma_adm
        res["facteur_securite"] = float(fs)

        if pression_pa is not None and B is not None:
            d = calcul_epaisseur_paroi_depuis_alesage(
                pression_pa=res["pression_pa"],
                alesage_m=B,
                contrainte_admissible_pa=sigma_adm,
                modele="both",
                facteur_securite=fs,
                include_longitudinale=include_longitudinale,
                ratio_mince_max=ratio_mince_max,
                epsilon=epsilon,
                return_details=True,
            )
            assert isinstance(d, dict)
            res["epaisseur_mince_m"] = float(d["t_mince_m"])
            res["t_over_ri_mince"] = float(d["t_over_ri_mince"])
            res["ratio_mince_max"] = float(d["ratio_mince_max"])

            if "t_lame_m" in d:
                res["epaisseur_lame_m"] = float(d["t_lame_m"])

            t_auto = calcul_epaisseur_paroi_depuis_alesage(
                pression_pa=res["pression_pa"],
                alesage_m=B,
                contrainte_admissible_pa=sigma_adm,
                modele=modele_paroi,
                facteur_securite=fs,
                include_longitudinale=include_longitudinale,
                ratio_mince_max=ratio_mince_max,
                epsilon=epsilon,
                return_details=False,
            )
            res["epaisseur_auto_m"] = float(t_auto)
        else:
            inconnues.append("epaisseur_paroi (pression/alesage requis)")
    else:
        inconnues.append("contrainte_admissible_pa / epaisseur_paroi")

    # Nouveau bloc pression détaillée
    if mode_pression is not None:
        if B is None or S is None:
            inconnues.append("mode_pression (alesage_m et course_m requis)")
        elif CR is None:
            inconnues.append("mode_pression (taux_compression ou volume_mort requis)")
        else:
            theta_deg = _theta_cycle_720(pas_angle_deg)
            p_details = construire_pression_cylindre(
                theta_deg,
                mode=mode_pression,
                alesage_m=B,
                course_m=S,
                longueur_bielle_m=longueur_bielle_m,
                axe_decale_m=axe_decale_m,
                courbe_mesuree=courbe_mesuree,
                theta_tableau_deg=theta_tableau_deg,
                pression_tableau_pa=pression_tableau_pa,
                parametres_wiebe=parametres_wiebe,
                pression_constante_pa=pression_constante_pa,
                pression_max_pa=pression_max_pa,
                angle_pic_deg=angle_pic_deg,
                largeur_pic_deg=largeur_pic_deg,
                pression_admission_pa=pression_admission_pa,
                pression_echappement_pa=pression_echappement_pa,
                forme_pic=forme_pic,
                return_details=True,
            )
            assert isinstance(p_details, dict)

            vol_details = calcul_volume_cylindre_vs_angle(
                theta_deg,
                B,
                S,
                taux_compression=CR,
                longueur_bielle_m=longueur_bielle_m,
                axe_decale_m=axe_decale_m,
                return_details=True,
            )
            assert isinstance(vol_details, dict)

            p_curve = np.asarray(p_details["pression_pa"], dtype=float)
            v_curve = np.asarray(vol_details["volume_m3"], dtype=float)
            f_curve = calcul_force_gaz_vs_angle(p_curve, B, return_details=False)
            f_curve = np.asarray(f_curve, dtype=float)

            travail_j = float(np.trapz(p_curve, v_curve))
            pmi_pa = travail_j / Vd_unit if Vd_unit and Vd_unit > 0.0 else float("nan")

            res["modele_pression_defaut"] = str(p_details["mode"])
            res["pression_cylindre_max_pa"] = float(np.max(p_curve))
            res["pression_cylindre_moyenne_pa"] = float(np.mean(p_curve))
            res["force_gaz_max_n"] = float(np.max(np.abs(f_curve)))
            res["travail_indique_cycle_j"] = travail_j
            res["pmi_pa"] = float(pmi_pa)

    if cas_de_charge is not None:
        if B is None or S is None:
            inconnues.append("cas_de_charge (alesage_m et course_m requis)")
        elif CR is None:
            inconnues.append("cas_de_charge (taux_compression ou volume_mort requis)")
        else:
            res["evaluation_cas_charge"] = evaluer_plusieurs_cas_charge_cylindre(
                alesage_m=B,
                course_m=S,
                taux_compression=CR,
                cas_de_charge=cas_de_charge,
                pas_angle_deg=pas_angle_deg,
                longueur_bielle_m=longueur_bielle_m,
                axe_decale_m=axe_decale_m,
            )

    res["inconnues"] = "; ".join(inconnues) if inconnues else ""
    return res


__all__ = [
    "CourbePressionMesuree",
    "ParametresWiebe",
    "CasChargePression",
    "aire_disque_depuis_diametre",
    "rayon_depuis_diametre",
    "verifier_hypothese_paroi_mince",
    "calcul_cylindree_unitaire",
    "calcul_cylindree_totale",
    "calcul_volume_mort",
    "calcul_taux_compression",
    "calcul_ratio_alesage_course",
    "calcul_volume_cylindre_vs_angle",
    "calcul_force_gaz",
    "calcul_force_gaz_vs_angle",
    "calcul_epaisseur_cylindre_mince",
    "calcul_epaisseur_cylindre_lame",
    "calcul_epaisseur_paroi_depuis_alesage",
    "charger_courbe_pression_csv",
    "calcul_pression_cylindre_modele_wiebe",
    "calcul_pression_cylindre_enveloppe",
    "construire_pression_cylindre",
    "ResultatPressionCase",
    "ResultatCylindre",
    "evaluer_cas_charge_cylindre",
    "evaluer_plusieurs_cas_charge_cylindre",
    "calculer_cylindre_complet",
]
