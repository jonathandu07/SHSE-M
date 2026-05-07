from __future__ import annotations

"""
Dimensionnement d'un pack batterie série/parallèle.

Version corrigée pour intégrer proprement la Samsung INR18650-25R :
- données cellule centralisées ;
- nombre de cellules variable ;
- dimensionnement automatique S/P ou configuration forcée ;
- calcul tension, capacité, énergie, masse, volume, pertes Joule ;
- charge standard / charge rapide / charge choisie ;
- recommandations BMS, fusible, contacteurs, précharge, section cuivre ;
- alertes haute tension et thermique.

Ce module ne remplace pas une conception HV certifiée. À partir de 60 V DC, et
a fortiori au voisinage de 400 V, la batterie devient dangereuse : contacteurs,
précharge, fusibles DC, isolation, arrêt d'urgence, détection d'isolement et
procédures de test sont indispensables.
"""

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Utilitaires robustesse
# =============================================================================


def _est_fini(x: object) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))



def _exiger_fini(nom: str, x: object) -> float:
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)



def _exiger_positif(nom: str, x: object, *, strict: bool = True) -> float:
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x



def _exiger_ratio_0_1(nom: str, x: object, *, strict_min: bool = False) -> float:
    x = _exiger_fini(nom, x)
    if strict_min:
        ok = 0.0 < x <= 1.0
        borne = "0 < x <= 1"
    else:
        ok = 0.0 <= x <= 1.0
        borne = "0 <= x <= 1"
    if not ok:
        raise ValueError(f"{nom} doit vérifier {borne} (reçu: {x}).")
    return x



def _ceil_div_pos(a: float, b: float) -> int:
    a = _exiger_positif("a", a, strict=False)
    b = _exiger_positif("b", b, strict=True)
    if a == 0.0:
        return 0
    return int(math.ceil(a / b))



def _round(x: Optional[float], ndigits: int = 4) -> Optional[float]:
    if x is None:
        return None
    if math.isinf(x) or math.isnan(x):
        return x
    return round(float(x), ndigits)



def _ajouter_unique(messages: List[str], msg: str) -> None:
    if msg not in messages:
        messages.append(msg)


# =============================================================================
# Données d'entrée
# =============================================================================


@dataclass(frozen=True)
class PointCellule:
    """
    Point caractéristique réel ou conservateur d'une cellule.

    - tension_ocv_v : tension de cellule au point considéré.
    - resistance_interne_ohm : résistance interne utilisée pour la chute de tension
      et les pertes Joule.
    - courant_decharge_max_a : limite de décharge par cellule au point considéré.
    - courant_charge_max_a : limite de charge par cellule au point considéré.
    """

    soc: float
    tension_ocv_v: float
    resistance_interne_ohm: float
    courant_decharge_max_a: float
    courant_charge_max_a: Optional[float] = None

    def __post_init__(self) -> None:
        _exiger_ratio_0_1("soc", self.soc, strict_min=False)
        _exiger_positif("tension_ocv_v", self.tension_ocv_v, strict=True)
        _exiger_positif("resistance_interne_ohm", self.resistance_interne_ohm, strict=False)
        _exiger_positif("courant_decharge_max_a", self.courant_decharge_max_a, strict=True)
        if self.courant_charge_max_a is not None:
            _exiger_positif("courant_charge_max_a", self.courant_charge_max_a, strict=True)


@dataclass(frozen=True)
class Cellule:
    reference: str
    capacite_nominale_ah: float
    tension_nominale_v: float
    tension_max_v: float
    tension_min_v: float
    masse_kg: float
    volume_m3: Optional[float]
    point_min_decharge: PointCellule
    point_nominal: PointCellule
    point_max_charge: PointCellule

    # Champs additionnels optionnels, utiles pour une vraie fiche cellule.
    fabricant: Optional[str] = None
    format_cellule: Optional[str] = None
    chimie: Optional[str] = None
    protegee_individuellement: bool = False
    diametre_mm: Optional[float] = None
    hauteur_mm: Optional[float] = None
    masse_typique_kg: Optional[float] = None

    energie_nominale_wh: Optional[float] = None
    energie_typique_0_2c_wh: Optional[float] = None
    energie_typique_10a_wh: Optional[float] = None
    capacite_min_0_2c_ah: Optional[float] = None
    capacite_min_10a_ah: Optional[float] = None

    courant_decharge_prudent_a: Optional[float] = None
    courant_decharge_performant_a: Optional[float] = None
    courant_decharge_max_continu_a: Optional[float] = None
    courant_impulsion_moins_1s_a: Optional[float] = None

    courant_charge_standard_a: Optional[float] = None
    courant_charge_rapide_a: Optional[float] = None
    courant_charge_defaut_conception_a: Optional[float] = None
    tension_charge_cv_v: Optional[float] = None
    courant_fin_charge_standard_a: Optional[float] = None
    courant_fin_charge_rapide_a: Optional[float] = None

    resistance_ac_typique_ohm: Optional[float] = None
    resistance_ac_max_ohm: Optional[float] = None
    resistance_dc_typique_ohm: Optional[float] = None
    resistance_dc_max_ohm: Optional[float] = None

    table_temperature_decharge_c: Dict[float, float] = field(default_factory=dict)
    remarques: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _exiger_positif("capacite_nominale_ah", self.capacite_nominale_ah, strict=True)
        _exiger_positif("tension_nominale_v", self.tension_nominale_v, strict=True)
        _exiger_positif("tension_max_v", self.tension_max_v, strict=True)
        _exiger_positif("tension_min_v", self.tension_min_v, strict=True)
        _exiger_positif("masse_kg", self.masse_kg, strict=True)
        if self.volume_m3 is not None:
            _exiger_positif("volume_m3", self.volume_m3, strict=True)
        if self.tension_min_v > self.tension_nominale_v:
            raise ValueError("tension_min_v ne peut pas être > tension_nominale_v.")
        if self.tension_nominale_v > self.tension_max_v:
            raise ValueError("tension_nominale_v ne peut pas être > tension_max_v.")
        if self.point_min_decharge.soc > self.point_nominal.soc:
            raise ValueError("point_min_decharge.soc doit être <= point_nominal.soc.")
        if self.point_nominal.soc > self.point_max_charge.soc:
            raise ValueError("point_nominal.soc doit être <= point_max_charge.soc.")
        if self.point_max_charge.tension_ocv_v > self.tension_max_v + 1e-12:
            raise ValueError("point_max_charge.tension_ocv_v ne peut pas dépasser tension_max_v.")
        if self.point_min_decharge.tension_ocv_v < self.tension_min_v - 1e-12:
            raise ValueError("point_min_decharge.tension_ocv_v ne peut pas être < tension_min_v.")


@dataclass(frozen=True)
class PertesPassivesPack:
    """
    Contributions hors cellules.

    Une valeur à 0 signifie explicitement : non prise en compte dans le calcul.
    """

    resistance_hors_cellules_ohm: float = 0.0
    masse_hors_cellules_kg: float = 0.0
    volume_hors_cellules_m3: float = 0.0

    def __post_init__(self) -> None:
        _exiger_positif("resistance_hors_cellules_ohm", self.resistance_hors_cellules_ohm, strict=False)
        _exiger_positif("masse_hors_cellules_kg", self.masse_hors_cellules_kg, strict=False)
        _exiger_positif("volume_hors_cellules_m3", self.volume_hors_cellules_m3, strict=False)


@dataclass(frozen=True)
class ModeleThermiquePack:
    """
    Modèle thermique RC simple pour estimer l'élévation de température du pack.

    Si tu n'as pas mesuré ces paramètres, ne les invente pas : laisse le modèle
    thermique à None et utilise seulement les alertes thermiques par cellule.
    """

    resistance_thermique_k_par_w: float
    capacite_thermique_j_par_k: float
    temperature_refroidissement_c: float

    def __post_init__(self) -> None:
        _exiger_positif("resistance_thermique_k_par_w", self.resistance_thermique_k_par_w, strict=True)
        _exiger_positif("capacite_thermique_j_par_k", self.capacite_thermique_j_par_k, strict=True)
        _exiger_fini("temperature_refroidissement_c", self.temperature_refroidissement_c)


@dataclass(frozen=True)
class ContraintesPack:
    energie_nominale_cible_kwh: float
    tension_bus_min_v: float
    tension_bus_max_v: float
    puissance_continue_kw: float
    puissance_pic_kw: float
    tension_nominale_cible_v: Optional[float] = None
    duree_regime_continu_s: Optional[float] = None
    duree_pic_s: Optional[float] = None

    def __post_init__(self) -> None:
        _exiger_positif("energie_nominale_cible_kwh", self.energie_nominale_cible_kwh, strict=False)
        _exiger_positif("tension_bus_min_v", self.tension_bus_min_v, strict=True)
        _exiger_positif("tension_bus_max_v", self.tension_bus_max_v, strict=True)
        _exiger_positif("puissance_continue_kw", self.puissance_continue_kw, strict=False)
        _exiger_positif("puissance_pic_kw", self.puissance_pic_kw, strict=False)
        if self.tension_bus_max_v < self.tension_bus_min_v:
            raise ValueError("tension_bus_max_v doit être >= tension_bus_min_v.")
        if self.tension_nominale_cible_v is not None:
            _exiger_positif("tension_nominale_cible_v", self.tension_nominale_cible_v, strict=True)
        if self.duree_regime_continu_s is not None:
            _exiger_positif("duree_regime_continu_s", self.duree_regime_continu_s, strict=True)
        if self.duree_pic_s is not None:
            _exiger_positif("duree_pic_s", self.duree_pic_s, strict=True)


# =============================================================================
# Sorties structurées
# =============================================================================


@dataclass(frozen=True)
class RapportRegime:
    nom: str
    point_utilise: str
    puissance_demande_kw: float
    puissance_max_theorique_kw: float
    puissance_max_limitee_courant_kw: float
    tension_ocv_pack_v: float
    tension_charge_pack_v: Optional[float]
    courant_pack_a: Optional[float]
    courant_cellule_a: Optional[float]
    resistance_pack_ohm: float
    pertes_joule_w: Optional[float]
    respecte_puissance: bool
    respecte_tension_bus: bool
    respecte_courant_cellule: bool
    messages: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RapportThermique:
    nom: str
    pertes_w: float
    temperature_refroidissement_c: float
    elevation_steady_state_k: float
    temperature_steady_state_c: float
    duree_s: Optional[float]
    elevation_apres_duree_k: Optional[float]
    temperature_apres_duree_c: Optional[float]
    constante_de_temps_s: float


@dataclass(frozen=True)
class RapportCharge:
    courant_charge_cellule_a: float
    courant_charge_pack_a: float
    puissance_charge_nominale_kw: float
    puissance_charge_pleine_tension_kw: float
    courant_charge_standard_pack_a: Optional[float]
    puissance_charge_standard_nominale_kw: Optional[float]
    courant_charge_rapide_pack_a: Optional[float]
    puissance_charge_rapide_nominale_kw: Optional[float]
    temps_charge_0_100_h: Optional[float]
    temps_charge_10_80_h: Optional[float]
    methode: str
    messages: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RapportSecuritePack:
    haute_tension: bool
    tres_haute_tension: bool
    echelle_automobile_ou_stationnaire: bool
    bms_recommande: str
    courant_bms_decharge_min_a: float
    courant_bms_charge_min_a: float
    courant_equilibrage_recommande_a: float
    fusible_principal_estime_a: float
    section_cuivre_3a_mm2: float
    section_cuivre_5a_mm2: float
    elements_recommandes: List[str]
    alertes: List[str]


@dataclass(frozen=True)
class DimensionnementPack:
    cellule_reference: str
    nb_series: int
    nb_parallele: int
    nb_cellules_total: int
    capacite_pack_ah: float
    energie_nominale_pack_kwh: float
    tension_nominale_pack_v: float
    tension_max_pack_v: float
    fenetre_soc_modelee: float
    energie_approx_entre_soc_min_et_max_kwh: float
    masse_cellules_kg: float
    masse_totale_pack_kg: float
    volume_cellules_m3: Optional[float]
    volume_total_pack_m3: Optional[float]
    resistance_pack_min_ohm: float
    resistance_pack_nominale_ohm: float
    rapports_regimes: Dict[str, RapportRegime]
    rapports_thermiques: Dict[str, RapportThermique]
    marge_energie_kwh: float
    score_selection: Dict[str, float]
    avertissements: List[str]
    rapports_charge: Optional[RapportCharge] = None
    securite: Optional[RapportSecuritePack] = None
    cellule_spec: Optional[Dict[str, Any]] = None
    cellules_non_utilisees: int = 0

    def en_dict(self) -> Dict[str, Any]:
        def _convert(obj: Any) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _convert(v) for k, v in asdict(obj).items()}
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_convert(v) for v in obj]
            return obj
        return _convert(self)

    def en_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.en_dict(), ensure_ascii=False, indent=indent)


# =============================================================================
# Données Samsung INR18650-25R
# =============================================================================


def volume_cylindre_m3(diametre_mm: float, hauteur_mm: float) -> float:
    d = _exiger_positif("diametre_mm", diametre_mm, strict=True) / 1000.0
    h = _exiger_positif("hauteur_mm", hauteur_mm, strict=True) / 1000.0
    r = d / 2.0
    return math.pi * r * r * h



def creer_cellule_samsung_25r(
    *,
    courant_decharge_conception_a: float = 10.0,
    utiliser_resistance_max: bool = False,
) -> Cellule:
    """
    Fabrique une cellule Samsung INR18650-25R avec paramètres conservateurs.

    Valeurs intégrées :
    - 18650 NCA ;
    - 2,5 Ah minimum ;
    - 3,6 V nominal ; 4,2 V pleine charge ; 2,5 V fin de décharge ;
    - 20 A max continu ; 100 A impulsion < 1 s ;
    - charge standard 1,25 A ; charge rapide 4 A ;
    - masse max 45 g ; typique 43,8 g ;
    - AC-IR typ. 13,20 mΩ / max 18 mΩ ;
    - DC-IR typ. 22,15 mΩ / max 30 mΩ ;
    - table thermique indicative à 5/10/15/20/25 A.

    `courant_decharge_conception_a` permet de volontairement brider le calcul
    à 10 A ou 15 A/cellule au lieu d'utiliser directement 20 A.
    """
    I_design = _exiger_positif("courant_decharge_conception_a", courant_decharge_conception_a, strict=True)
    if I_design > 20.0:
        raise ValueError("Pour la Samsung 25R, courant_decharge_conception_a ne doit pas dépasser 20 A.")

    r_dc = 0.030 if utiliser_resistance_max else 0.02215
    r_min = 0.030 if utiliser_resistance_max else 0.030
    r_ac = 0.018 if utiliser_resistance_max else 0.01320

    return Cellule(
        reference="Samsung INR18650-25R",
        fabricant="Samsung SDI",
        format_cellule="18650",
        chimie="Li-ion INR / NCA haute puissance",
        protegee_individuellement=False,
        capacite_nominale_ah=2.5,
        tension_nominale_v=3.6,
        tension_max_v=4.2,
        tension_min_v=2.5,
        masse_kg=0.045,
        masse_typique_kg=0.0438,
        diametre_mm=18.33,
        hauteur_mm=64.85,
        volume_m3=volume_cylindre_m3(18.33, 64.85),
        point_min_decharge=PointCellule(
            soc=0.0,
            tension_ocv_v=2.5,
            resistance_interne_ohm=r_min,
            courant_decharge_max_a=I_design,
            courant_charge_max_a=4.0,
        ),
        point_nominal=PointCellule(
            soc=0.5,
            tension_ocv_v=3.6,
            resistance_interne_ohm=r_dc,
            courant_decharge_max_a=I_design,
            courant_charge_max_a=4.0,
        ),
        point_max_charge=PointCellule(
            soc=1.0,
            tension_ocv_v=4.2,
            resistance_interne_ohm=r_ac,
            courant_decharge_max_a=I_design,
            courant_charge_max_a=4.0,
        ),
        energie_nominale_wh=9.0,
        energie_typique_0_2c_wh=9.38,
        energie_typique_10a_wh=8.74,
        capacite_min_0_2c_ah=2.5,
        capacite_min_10a_ah=2.45,
        courant_decharge_prudent_a=10.0,
        courant_decharge_performant_a=15.0,
        courant_decharge_max_continu_a=20.0,
        courant_impulsion_moins_1s_a=100.0,
        courant_charge_standard_a=1.25,
        courant_charge_rapide_a=4.0,
        courant_charge_defaut_conception_a=2.0,
        tension_charge_cv_v=4.2,
        courant_fin_charge_standard_a=0.125,
        courant_fin_charge_rapide_a=0.100,
        resistance_ac_typique_ohm=0.01320,
        resistance_ac_max_ohm=0.018,
        resistance_dc_typique_ohm=0.02215,
        resistance_dc_max_ohm=0.030,
        table_temperature_decharge_c={
            5.0: 41.2,
            10.0: 60.6,
            15.0: 78.4,
            20.0: 95.2,
            25.0: 106.8,
        },
        remarques=[
            "Cellule non protégée individuellement : BMS obligatoire.",
            "Charge CC-CV 4,2 V par cellule.",
            "Pour préserver la durée de vie, dimensionner de préférence à 10–15 A/cellule plutôt qu'à 20 A continu.",
            "La table thermique est indicative et ne remplace pas un essai dans le pack réel.",
        ],
    )


# =============================================================================
# Calculs pack
# =============================================================================


def calcul_resistance_pack(
    *,
    nb_series: int,
    nb_parallele: int,
    resistance_cellule_ohm: float,
    pertes_passives: Optional[PertesPassivesPack] = None,
) -> float:
    """
    R_pack = (Ns / Np) * R_cell + R_hors_cellules
    """
    ns = int(_exiger_positif("nb_series", nb_series, strict=True))
    np_ = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
    r_cell = _exiger_positif("resistance_cellule_ohm", resistance_cellule_ohm, strict=False)
    r_extra = 0.0 if pertes_passives is None else float(pertes_passives.resistance_hors_cellules_ohm)
    return (ns / np_) * r_cell + r_extra



def calcul_puissance_max_pack(
    *,
    tension_ocv_pack_v: float,
    resistance_pack_ohm: float,
    courant_pack_limite_a: Optional[float] = None,
) -> float:
    """
    Puissance maximale soutenable sur modèle simple :
        V = Voc - I*R ; P = V*I

    Sans limite courant : maximum pour I = Voc / (2R).
    Avec limite courant : maximum sur [0, I_lim].
    """
    voc = _exiger_positif("tension_ocv_pack_v", tension_ocv_pack_v, strict=True)
    r = _exiger_positif("resistance_pack_ohm", resistance_pack_ohm, strict=False)
    i_lim = None if courant_pack_limite_a is None else _exiger_positif("courant_pack_limite_a", courant_pack_limite_a, strict=True)

    if r == 0.0:
        if i_lim is None:
            return math.inf
        return voc * i_lim / 1000.0

    i_opt = voc / (2.0 * r)
    i_use = i_opt if i_lim is None else min(i_opt, i_lim)
    p_w = (voc - i_use * r) * i_use
    return max(0.0, p_w) / 1000.0



def resoudre_point_puissance(
    *,
    tension_ocv_pack_v: float,
    resistance_pack_ohm: float,
    puissance_demande_kw: float,
    courant_pack_limite_a: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    """
    Résout le point de fonctionnement :
        P = (Voc - I*R) * I
    soit :
        R*I² - Voc*I + P = 0

    On retient la petite racine positive, qui correspond au courant minimal.
    """
    voc = _exiger_positif("tension_ocv_pack_v", tension_ocv_pack_v, strict=True)
    r = _exiger_positif("resistance_pack_ohm", resistance_pack_ohm, strict=False)
    p_kw = _exiger_positif("puissance_demande_kw", puissance_demande_kw, strict=False)
    i_lim = None if courant_pack_limite_a is None else _exiger_positif("courant_pack_limite_a", courant_pack_limite_a, strict=True)

    if p_kw == 0.0:
        return {
            "faisable": True,
            "courant_pack_a": 0.0,
            "tension_charge_pack_v": voc,
            "pertes_joule_w": 0.0,
            "puissance_max_theorique_kw": calcul_puissance_max_pack(
                tension_ocv_pack_v=voc,
                resistance_pack_ohm=r,
                courant_pack_limite_a=None,
            ),
            "puissance_max_limitee_courant_kw": calcul_puissance_max_pack(
                tension_ocv_pack_v=voc,
                resistance_pack_ohm=r,
                courant_pack_limite_a=i_lim,
            ),
        }

    p_w = p_kw * 1000.0

    p_max_theorique = calcul_puissance_max_pack(
        tension_ocv_pack_v=voc,
        resistance_pack_ohm=r,
        courant_pack_limite_a=None,
    )
    p_max_lim = calcul_puissance_max_pack(
        tension_ocv_pack_v=voc,
        resistance_pack_ohm=r,
        courant_pack_limite_a=i_lim,
    )

    if p_kw > p_max_lim + 1e-12:
        return {
            "faisable": False,
            "courant_pack_a": None,
            "tension_charge_pack_v": None,
            "pertes_joule_w": None,
            "puissance_max_theorique_kw": p_max_theorique,
            "puissance_max_limitee_courant_kw": p_max_lim,
        }

    if r == 0.0:
        i = p_w / voc
        if i_lim is not None and i > i_lim + 1e-12:
            return {
                "faisable": False,
                "courant_pack_a": None,
                "tension_charge_pack_v": None,
                "pertes_joule_w": None,
                "puissance_max_theorique_kw": p_max_theorique,
                "puissance_max_limitee_courant_kw": p_max_lim,
            }
        return {
            "faisable": True,
            "courant_pack_a": i,
            "tension_charge_pack_v": voc,
            "pertes_joule_w": 0.0,
            "puissance_max_theorique_kw": p_max_theorique,
            "puissance_max_limitee_courant_kw": p_max_lim,
        }

    discriminant = voc * voc - 4.0 * r * p_w
    if discriminant < -1e-9:
        return {
            "faisable": False,
            "courant_pack_a": None,
            "tension_charge_pack_v": None,
            "pertes_joule_w": None,
            "puissance_max_theorique_kw": p_max_theorique,
            "puissance_max_limitee_courant_kw": p_max_lim,
        }
    discriminant = max(0.0, discriminant)

    i = (voc - math.sqrt(discriminant)) / (2.0 * r)
    if i_lim is not None and i > i_lim + 1e-12:
        return {
            "faisable": False,
            "courant_pack_a": None,
            "tension_charge_pack_v": None,
            "pertes_joule_w": None,
            "puissance_max_theorique_kw": p_max_theorique,
            "puissance_max_limitee_courant_kw": p_max_lim,
        }

    v_load = voc - i * r
    losses = i * i * r
    return {
        "faisable": True,
        "courant_pack_a": i,
        "tension_charge_pack_v": v_load,
        "pertes_joule_w": losses,
        "puissance_max_theorique_kw": p_max_theorique,
        "puissance_max_limitee_courant_kw": p_max_lim,
    }



def _evaluer_regime(
    *,
    nom: str,
    point_nom: str,
    point_cellule: PointCellule,
    nb_series: int,
    nb_parallele: int,
    puissance_demande_kw: float,
    tension_bus_min_v: float,
    pertes_passives: PertesPassivesPack,
) -> RapportRegime:
    ns = int(_exiger_positif("nb_series", nb_series, strict=True))
    np_ = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
    p_kw = _exiger_positif("puissance_demande_kw", puissance_demande_kw, strict=False)
    v_min = _exiger_positif("tension_bus_min_v", tension_bus_min_v, strict=True)

    voc_pack = ns * point_cellule.tension_ocv_v
    r_pack = calcul_resistance_pack(
        nb_series=ns,
        nb_parallele=np_,
        resistance_cellule_ohm=point_cellule.resistance_interne_ohm,
        pertes_passives=pertes_passives,
    )
    i_lim_pack = np_ * point_cellule.courant_decharge_max_a
    sol = resoudre_point_puissance(
        tension_ocv_pack_v=voc_pack,
        resistance_pack_ohm=r_pack,
        puissance_demande_kw=p_kw,
        courant_pack_limite_a=i_lim_pack,
    )

    i_pack = sol["courant_pack_a"]
    v_load = sol["tension_charge_pack_v"]
    i_cell = None if i_pack is None else i_pack / np_

    respecte_puissance = bool(sol["faisable"])
    respecte_tension = v_load is not None and v_load >= v_min - 1e-12
    respecte_courant = i_cell is None or i_cell <= point_cellule.courant_decharge_max_a + 1e-12

    messages: List[str] = []
    if not respecte_puissance:
        messages.append(
            f"Puissance demandée non atteignable ({p_kw:.3f} kW > {sol['puissance_max_limitee_courant_kw']:.3f} kW limité courant)."
        )
    if v_load is not None and not respecte_tension:
        messages.append(
            f"Tension pack sous charge inférieure au bus minimum ({v_load:.3f} V < {v_min:.3f} V)."
        )
    if i_cell is not None and not respecte_courant:
        messages.append(
            f"Courant cellule au-dessus de la limite ({i_cell:.3f} A > {point_cellule.courant_decharge_max_a:.3f} A)."
        )

    return RapportRegime(
        nom=nom,
        point_utilise=point_nom,
        puissance_demande_kw=float(p_kw),
        puissance_max_theorique_kw=float(sol["puissance_max_theorique_kw"]),
        puissance_max_limitee_courant_kw=float(sol["puissance_max_limitee_courant_kw"]),
        tension_ocv_pack_v=float(voc_pack),
        tension_charge_pack_v=None if v_load is None else float(v_load),
        courant_pack_a=None if i_pack is None else float(i_pack),
        courant_cellule_a=None if i_cell is None else float(i_cell),
        resistance_pack_ohm=float(r_pack),
        pertes_joule_w=None if sol["pertes_joule_w"] is None else float(sol["pertes_joule_w"]),
        respecte_puissance=respecte_puissance,
        respecte_tension_bus=respecte_tension,
        respecte_courant_cellule=respecte_courant,
        messages=messages,
    )



def evaluer_thermique_pack(
    *,
    nom: str,
    pertes_w: float,
    modele: ModeleThermiquePack,
    duree_s: Optional[float] = None,
) -> RapportThermique:
    p = _exiger_positif("pertes_w", pertes_w, strict=False)
    rth = modele.resistance_thermique_k_par_w
    cth = modele.capacite_thermique_j_par_k
    t_cool = modele.temperature_refroidissement_c

    delta_ss = p * rth
    t_ss = t_cool + delta_ss
    tau_s = rth * cth

    if duree_s is None:
        delta_t = None
        t_duree = None
    else:
        t = _exiger_positif("duree_s", duree_s, strict=True)
        facteur = 1.0 - math.exp(-t / tau_s)
        delta_t = delta_ss * facteur
        t_duree = t_cool + delta_t

    return RapportThermique(
        nom=nom,
        pertes_w=float(p),
        temperature_refroidissement_c=float(t_cool),
        elevation_steady_state_k=float(delta_ss),
        temperature_steady_state_c=float(t_ss),
        duree_s=None if duree_s is None else float(duree_s),
        elevation_apres_duree_k=None if delta_t is None else float(delta_t),
        temperature_apres_duree_c=None if t_duree is None else float(t_duree),
        constante_de_temps_s=float(tau_s),
    )



def temperature_cellule_estimee(cellule: Cellule, courant_cellule_a: float) -> Optional[float]:
    """
    Interpolation linéaire sur la table thermique cellule, si disponible.
    """
    I = _exiger_positif("courant_cellule_a", courant_cellule_a, strict=False)
    if not cellule.table_temperature_decharge_c:
        return None
    points = sorted((float(k), float(v)) for k, v in cellule.table_temperature_decharge_c.items())
    if I <= points[0][0]:
        return points[0][1]
    if I >= points[-1][0]:
        x0, y0 = points[-2]
        x1, y1 = points[-1]
        pente = (y1 - y0) / (x1 - x0)
        return y1 + pente * (I - x1)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= I <= x1:
            ratio = (I - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return None


# =============================================================================
# Charge / sécurité
# =============================================================================


def calculer_rapport_charge(
    *,
    cellule: Cellule,
    nb_series: int,
    nb_parallele: int,
    energie_nominale_pack_kwh: float,
    courant_charge_cellule_a: Optional[float] = None,
    rendement_charge: float = 0.92,
) -> RapportCharge:
    ns = int(_exiger_positif("nb_series", nb_series, strict=True))
    np_ = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
    E = _exiger_positif("energie_nominale_pack_kwh", energie_nominale_pack_kwh, strict=False)
    eta = _exiger_ratio_0_1("rendement_charge", rendement_charge, strict_min=True)

    if courant_charge_cellule_a is None:
        if cellule.courant_charge_defaut_conception_a is not None:
            courant_charge_cellule_a = cellule.courant_charge_defaut_conception_a
        elif cellule.courant_charge_standard_a is not None:
            courant_charge_cellule_a = cellule.courant_charge_standard_a
        else:
            courant_charge_cellule_a = 1.0

    I_cell = _exiger_positif("courant_charge_cellule_a", courant_charge_cellule_a, strict=False)
    I_pack = np_ * I_cell
    V_nom = ns * cellule.tension_nominale_v
    V_full = ns * cellule.tension_max_v
    P_nom = V_nom * I_pack / 1000.0
    P_full = V_full * I_pack / 1000.0

    messages: List[str] = []
    if cellule.courant_charge_rapide_a is not None and I_cell > cellule.courant_charge_rapide_a + 1e-12:
        messages.append(
            f"Charge demandée {I_cell:.3f} A/cellule > charge rapide max {cellule.courant_charge_rapide_a:.3f} A/cellule."
        )
    elif cellule.courant_charge_rapide_a is not None and I_cell > 0.5 * cellule.courant_charge_rapide_a:
        messages.append("Charge rapide agressive : refroidissement et surveillance thermique recommandés.")

    if P_nom > 0.0:
        t_0_100 = E / (P_nom * eta)
        t_10_80 = E * 0.70 / (P_nom * eta)
    else:
        t_0_100 = None
        t_10_80 = None

    I_std_pack = None
    P_std = None
    if cellule.courant_charge_standard_a is not None:
        I_std_pack = np_ * cellule.courant_charge_standard_a
        P_std = V_nom * I_std_pack / 1000.0

    I_fast_pack = None
    P_fast = None
    if cellule.courant_charge_rapide_a is not None:
        I_fast_pack = np_ * cellule.courant_charge_rapide_a
        P_fast = V_nom * I_fast_pack / 1000.0

    return RapportCharge(
        courant_charge_cellule_a=float(I_cell),
        courant_charge_pack_a=float(I_pack),
        puissance_charge_nominale_kw=float(P_nom),
        puissance_charge_pleine_tension_kw=float(P_full),
        courant_charge_standard_pack_a=None if I_std_pack is None else float(I_std_pack),
        puissance_charge_standard_nominale_kw=None if P_std is None else float(P_std),
        courant_charge_rapide_pack_a=None if I_fast_pack is None else float(I_fast_pack),
        puissance_charge_rapide_nominale_kw=None if P_fast is None else float(P_fast),
        temps_charge_0_100_h=None if t_0_100 is None else float(t_0_100),
        temps_charge_10_80_h=None if t_10_80 is None else float(t_10_80),
        methode=f"CC-CV {cellule.tension_max_v:.2f} V/cellule",
        messages=messages,
    )



def _courant_equilibrage_recommande(nb_parallele: int) -> float:
    p = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
    if p <= 4:
        return 0.05
    if p <= 10:
        return 0.10
    if p <= 30:
        return 0.20
    return 0.50



def calculer_rapport_securite(
    *,
    cellule: Cellule,
    nb_series: int,
    nb_parallele: int,
    tension_max_pack_v: float,
    energie_nominale_pack_kwh: float,
    courant_decharge_pack_a: float,
    courant_charge_pack_a: float,
) -> RapportSecuritePack:
    ns = int(_exiger_positif("nb_series", nb_series, strict=True))
    np_ = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
    Vmax = _exiger_positif("tension_max_pack_v", tension_max_pack_v, strict=True)
    E = _exiger_positif("energie_nominale_pack_kwh", energie_nominale_pack_kwh, strict=False)
    I_dis = _exiger_positif("courant_decharge_pack_a", courant_decharge_pack_a, strict=False)
    I_chg = _exiger_positif("courant_charge_pack_a", courant_charge_pack_a, strict=False)

    hv = Vmax > 60.0
    vhv = Vmax > 120.0
    auto = E >= 5.0

    bms_dis = I_dis * 1.25
    bms_chg = I_chg * 1.25
    fuse = I_dis * 1.15
    section_3a = I_dis / 3.0 if I_dis > 0 else 0.0
    section_5a = I_dis / 5.0 if I_dis > 0 else 0.0

    elements = [
        f"BMS {ns}S Li-ion obligatoire",
        f"courant BMS décharge recommandé ≥ {bms_dis:.0f} A",
        f"courant BMS charge recommandé ≥ {bms_chg:.0f} A",
        f"équilibrage recommandé ≥ {_courant_equilibrage_recommande(np_):.2f} A par groupe série",
        f"fusible principal DC autour de {fuse:.0f} A à valider par étude",
        "sondes thermiques réparties dans le pack",
        f"coupure surcharge à {cellule.tension_max_v:.2f} V/cellule",
        f"coupure décharge avant {cellule.tension_min_v:.2f} V/cellule",
        "soudure par points ou procédé industriel adapté, pas de soudure directe au fer",
        "isolation entre groupes, entre busbars et contre le boîtier",
        "boîtier résistant aux chocs, vibrations et échauffements",
    ]
    alertes: List[str] = []

    if not cellule.protegee_individuellement:
        alertes.append("Cellule non protégée individuellement : BMS obligatoire.")
    if hv:
        alertes.append(
            f"Pack haute tension : {Vmax:.1f} V pleine charge. Contacteurs, précharge, fusible DC et isolation indispensables."
        )
        elements.extend([
            "contacteur positif haute tension",
            "contacteur négatif haute tension",
            "résistance + relais de précharge",
            "connecteurs haute tension verrouillables",
            "arrêt d'urgence / HV interlock",
        ])
    if vhv:
        alertes.append("Niveau de tension potentiellement mortel : ne pas assembler ni tester sans compétence HV.")
        elements.append("détection d'isolement haute tension")
    if auto:
        alertes.append(
            "Échelle automobile ou stationnaire lourde : refroidissement, anti-écrasement et conformité réglementaire à prévoir."
        )
    if ns * np_ >= 500:
        alertes.append(
            "Grand nombre de cellules : tri capacité/IR, traçabilité et équilibrage initial indispensables."
        )

    return RapportSecuritePack(
        haute_tension=hv,
        tres_haute_tension=vhv,
        echelle_automobile_ou_stationnaire=auto,
        bms_recommande=f"{ns}S Li-ion",
        courant_bms_decharge_min_a=float(bms_dis),
        courant_bms_charge_min_a=float(bms_chg),
        courant_equilibrage_recommande_a=float(_courant_equilibrage_recommande(np_)),
        fusible_principal_estime_a=float(fuse),
        section_cuivre_3a_mm2=float(section_3a),
        section_cuivre_5a_mm2=float(section_5a),
        elements_recommandes=elements,
        alertes=alertes,
    )


# =============================================================================
# Création d'un rapport pour une configuration fixe
# =============================================================================


def evaluer_configuration_pack_cellules(
    *,
    cellule: Cellule,
    nb_series: int,
    nb_parallele: int,
    contraintes: Optional[ContraintesPack] = None,
    pertes_passives: Optional[PertesPassivesPack] = None,
    modele_thermique: Optional[ModeleThermiquePack] = None,
    courant_charge_cellule_a: Optional[float] = None,
    rendement_charge: float = 0.92,
    cellules_non_utilisees: int = 0,
) -> DimensionnementPack:
    if pertes_passives is None:
        pertes_passives = PertesPassivesPack()

    ns = int(_exiger_positif("nb_series", nb_series, strict=True))
    np_ = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
    n = ns * np_

    capacite_pack_ah = np_ * cellule.capacite_nominale_ah
    e_nom_pack_kwh = n * cellule.capacite_nominale_ah * cellule.tension_nominale_v / 1000.0
    tension_nom_pack = ns * cellule.tension_nominale_v
    tension_max_pack = ns * cellule.tension_max_v
    tension_min_pack = ns * cellule.tension_min_v

    if contraintes is None:
        contraintes = ContraintesPack(
            energie_nominale_cible_kwh=e_nom_pack_kwh,
            tension_bus_min_v=tension_min_pack,
            tension_bus_max_v=tension_max_pack,
            puissance_continue_kw=0.0,
            puissance_pic_kw=0.0,
            tension_nominale_cible_v=tension_nom_pack,
        )

    fenetre_soc = cellule.point_max_charge.soc - cellule.point_min_decharge.soc
    e_approx_fenetre = e_nom_pack_kwh * fenetre_soc
    marge_energie = e_nom_pack_kwh - contraintes.energie_nominale_cible_kwh
    masse_cellules = n * cellule.masse_kg
    masse_totale = masse_cellules + pertes_passives.masse_hors_cellules_kg

    if cellule.volume_m3 is None:
        volume_cellules = None
        volume_total = None if pertes_passives.volume_hors_cellules_m3 == 0.0 else pertes_passives.volume_hors_cellules_m3
    else:
        volume_cellules = n * cellule.volume_m3
        volume_total = volume_cellules + pertes_passives.volume_hors_cellules_m3

    rapport_cont_min = _evaluer_regime(
        nom="continu_min",
        point_nom="point_min_decharge",
        point_cellule=cellule.point_min_decharge,
        nb_series=ns,
        nb_parallele=np_,
        puissance_demande_kw=contraintes.puissance_continue_kw,
        tension_bus_min_v=contraintes.tension_bus_min_v,
        pertes_passives=pertes_passives,
    )
    rapport_pic_min = _evaluer_regime(
        nom="pic_min",
        point_nom="point_min_decharge",
        point_cellule=cellule.point_min_decharge,
        nb_series=ns,
        nb_parallele=np_,
        puissance_demande_kw=contraintes.puissance_pic_kw,
        tension_bus_min_v=contraintes.tension_bus_min_v,
        pertes_passives=pertes_passives,
    )
    rapport_cont_nom = _evaluer_regime(
        nom="continu_nominal",
        point_nom="point_nominal",
        point_cellule=cellule.point_nominal,
        nb_series=ns,
        nb_parallele=np_,
        puissance_demande_kw=contraintes.puissance_continue_kw,
        tension_bus_min_v=contraintes.tension_bus_min_v,
        pertes_passives=pertes_passives,
    )

    r_pack_min = calcul_resistance_pack(
        nb_series=ns,
        nb_parallele=np_,
        resistance_cellule_ohm=cellule.point_min_decharge.resistance_interne_ohm,
        pertes_passives=pertes_passives,
    )
    r_pack_nom = calcul_resistance_pack(
        nb_series=ns,
        nb_parallele=np_,
        resistance_cellule_ohm=cellule.point_nominal.resistance_interne_ohm,
        pertes_passives=pertes_passives,
    )

    rapports_regimes = {
        "continu_min": rapport_cont_min,
        "pic_min": rapport_pic_min,
        "continu_nominal": rapport_cont_nom,
    }

    rapports_thermiques: Dict[str, RapportThermique] = {}
    avertissements: List[str] = []

    if cellule.volume_m3 is None:
        avertissements.append("volume_m3 cellule non fourni : volume pack non calculé complètement.")
    if tension_max_pack > contraintes.tension_bus_max_v + 1e-12:
        avertissements.append(
            f"Tension pleine charge {tension_max_pack:.3f} V > tension_bus_max_v {contraintes.tension_bus_max_v:.3f} V."
        )
    for cle, rapport in rapports_regimes.items():
        for msg in rapport.messages:
            avertissements.append(f"{cle}: {msg}")

    if modele_thermique is None:
        avertissements.append("ModeleThermiquePack non fourni : thermique pack RC non évaluée.")
    else:
        for cle, rapport in rapports_regimes.items():
            if rapport.pertes_joule_w is None:
                continue
            duree = contraintes.duree_pic_s if cle == "pic_min" else contraintes.duree_regime_continu_s
            rapports_thermiques[cle] = evaluer_thermique_pack(
                nom=cle,
                pertes_w=rapport.pertes_joule_w,
                modele=modele_thermique,
                duree_s=duree,
            )

    # Alertes thermiques par cellule, même sans modèle RC pack.
    for cle, rapport in rapports_regimes.items():
        if rapport.courant_cellule_a is None:
            continue
        t_est = temperature_cellule_estimee(cellule, rapport.courant_cellule_a)
        if t_est is not None:
            if t_est >= 80.0:
                avertissements.append(f"{cle}: température cellule indicative très élevée ≈ {t_est:.1f} °C.")
            elif t_est >= 65.0:
                avertissements.append(f"{cle}: température cellule indicative sévère ≈ {t_est:.1f} °C.")
            elif t_est >= 50.0:
                avertissements.append(f"{cle}: température cellule indicative modérée/forte ≈ {t_est:.1f} °C.")

    rapport_charge = calculer_rapport_charge(
        cellule=cellule,
        nb_series=ns,
        nb_parallele=np_,
        energie_nominale_pack_kwh=e_nom_pack_kwh,
        courant_charge_cellule_a=courant_charge_cellule_a,
        rendement_charge=rendement_charge,
    )
    for msg in rapport_charge.messages:
        avertissements.append(f"charge: {msg}")

    # Courant de référence sécurité : le plus fort courant pack réellement calculé.
    courants_pack = [r.courant_pack_a for r in rapports_regimes.values() if r.courant_pack_a is not None]
    courant_decharge_pack_ref = max(courants_pack) if courants_pack else 0.0
    if courant_decharge_pack_ref <= 0.0:
        courant_ref_cellule = (
            cellule.courant_decharge_prudent_a
            or cellule.courant_decharge_performant_a
            or cellule.courant_decharge_max_continu_a
            or cellule.point_nominal.courant_decharge_max_a
        )
        courant_decharge_pack_ref = np_ * courant_ref_cellule

    securite = calculer_rapport_securite(
        cellule=cellule,
        nb_series=ns,
        nb_parallele=np_,
        tension_max_pack_v=tension_max_pack,
        energie_nominale_pack_kwh=e_nom_pack_kwh,
        courant_decharge_pack_a=courant_decharge_pack_ref,
        courant_charge_pack_a=rapport_charge.courant_charge_pack_a,
    )
    avertissements.extend(securite.alertes)

    if contraintes.tension_nominale_cible_v is not None:
        delta_v_nom = abs(tension_nom_pack - contraintes.tension_nominale_cible_v)
    else:
        delta_v_nom = 0.0

    score = {
        "nb_cellules_total": float(n),
        "surenergie_kwh": float(marge_energie),
        "ecart_tension_nominale_v": float(delta_v_nom),
        "masse_totale_pack_kg": float(masse_totale),
    }

    spec = {
        "reference": cellule.reference,
        "fabricant": cellule.fabricant,
        "format_cellule": cellule.format_cellule,
        "chimie": cellule.chimie,
        "protegee_individuellement": cellule.protegee_individuellement,
        "capacite_nominale_ah": cellule.capacite_nominale_ah,
        "tension_nominale_v": cellule.tension_nominale_v,
        "tension_max_v": cellule.tension_max_v,
        "tension_min_v": cellule.tension_min_v,
        "masse_kg": cellule.masse_kg,
        "diametre_mm": cellule.diametre_mm,
        "hauteur_mm": cellule.hauteur_mm,
        "energie_nominale_wh": cellule.energie_nominale_wh,
        "energie_typique_0_2c_wh": cellule.energie_typique_0_2c_wh,
        "energie_typique_10a_wh": cellule.energie_typique_10a_wh,
        "courant_decharge_prudent_a": cellule.courant_decharge_prudent_a,
        "courant_decharge_performant_a": cellule.courant_decharge_performant_a,
        "courant_decharge_max_continu_a": cellule.courant_decharge_max_continu_a,
        "courant_charge_standard_a": cellule.courant_charge_standard_a,
        "courant_charge_rapide_a": cellule.courant_charge_rapide_a,
        "resistance_dc_typique_ohm": cellule.resistance_dc_typique_ohm,
        "resistance_dc_max_ohm": cellule.resistance_dc_max_ohm,
        "table_temperature_decharge_c": cellule.table_temperature_decharge_c,
        "remarques": cellule.remarques,
    }

    return DimensionnementPack(
        cellule_reference=cellule.reference,
        nb_series=ns,
        nb_parallele=np_,
        nb_cellules_total=n,
        capacite_pack_ah=float(capacite_pack_ah),
        energie_nominale_pack_kwh=float(e_nom_pack_kwh),
        tension_nominale_pack_v=float(tension_nom_pack),
        tension_max_pack_v=float(tension_max_pack),
        fenetre_soc_modelee=float(fenetre_soc),
        energie_approx_entre_soc_min_et_max_kwh=float(e_approx_fenetre),
        masse_cellules_kg=float(masse_cellules),
        masse_totale_pack_kg=float(masse_totale),
        volume_cellules_m3=None if volume_cellules is None else float(volume_cellules),
        volume_total_pack_m3=None if volume_total is None else float(volume_total),
        resistance_pack_min_ohm=float(r_pack_min),
        resistance_pack_nominale_ohm=float(r_pack_nom),
        rapports_regimes=rapports_regimes,
        rapports_thermiques=rapports_thermiques,
        marge_energie_kwh=float(marge_energie),
        score_selection=score,
        avertissements=avertissements,
        rapports_charge=rapport_charge,
        securite=securite,
        cellule_spec=spec,
        cellules_non_utilisees=int(cellules_non_utilisees),
    )


# =============================================================================
# Dimensionnement principal automatique
# =============================================================================


def dimensionner_pack_cellules(
    *,
    cellule: Cellule,
    contraintes: ContraintesPack,
    pertes_passives: Optional[PertesPassivesPack] = None,
    modele_thermique: Optional[ModeleThermiquePack] = None,
    nb_series_min: Optional[int] = None,
    nb_series_max: Optional[int] = None,
    courant_charge_cellule_a: Optional[float] = None,
    rendement_charge: float = 0.92,
) -> DimensionnementPack:
    """
    Dimensionne automatiquement un pack S/P.

    Le moteur de recherche :
    - calcule un domaine Ns admissible avec tension min/max ;
    - dimensionne Np depuis l'énergie nominale cible ;
    - augmente Np jusqu'à respecter puissance, tension sous charge et courant cellule ;
    - choisit la configuration avec le moins de cellules, puis le moins de surénergie,
      puis l'écart de tension nominale le plus faible.
    """
    if pertes_passives is None:
        pertes_passives = PertesPassivesPack()

    e_target_kwh = contraintes.energie_nominale_cible_kwh
    e_cell_kwh_ref = (cellule.capacite_nominale_ah * cellule.tension_nominale_v) / 1000.0
    if e_cell_kwh_ref <= 0.0:
        raise ValueError("Énergie nominale par cellule non positive.")

    ns_min_auto = max(1, int(math.ceil(contraintes.tension_bus_min_v / cellule.point_min_decharge.tension_ocv_v)))
    ns_max_auto = int(math.floor(contraintes.tension_bus_max_v / cellule.tension_max_v))
    if ns_max_auto < 1:
        raise ValueError("Aucune valeur de Ns possible : tension_bus_max_v trop faible par rapport à tension_max_v cellule.")

    ns_min = ns_min_auto if nb_series_min is None else max(ns_min_auto, int(_exiger_positif("nb_series_min", nb_series_min, strict=True)))
    ns_max = ns_max_auto if nb_series_max is None else min(ns_max_auto, int(_exiger_positif("nb_series_max", nb_series_max, strict=True)))

    if ns_max < ns_min:
        raise ValueError(
            "Aucun Ns admissible après application des bornes. "
            f"Domaine auto=[{ns_min_auto}, {ns_max_auto}], domaine final=[{ns_min}, {ns_max}]."
        )

    meilleur: Optional[DimensionnementPack] = None
    meilleur_score: Optional[Dict[str, float]] = None
    erreurs_globales: List[str] = []

    for ns in range(ns_min, ns_max + 1):
        e_string_kwh = ns * e_cell_kwh_ref
        np_energy = max(1, _ceil_div_pos(e_target_kwh, e_string_kwh))
        np_ = np_energy
        trouve = False

        while np_ <= 1_000_000:
            candidat = evaluer_configuration_pack_cellules(
                cellule=cellule,
                nb_series=ns,
                nb_parallele=np_,
                contraintes=contraintes,
                pertes_passives=pertes_passives,
                modele_thermique=modele_thermique,
                courant_charge_cellule_a=courant_charge_cellule_a,
                rendement_charge=rendement_charge,
            )
            ok = True
            if candidat.tension_max_pack_v > contraintes.tension_bus_max_v + 1e-12:
                erreurs_globales.append(
                    f"Ns={ns}: tension max pack {candidat.tension_max_pack_v:.3f} V > tension bus max {contraintes.tension_bus_max_v:.3f} V."
                )
                break
            for r in candidat.rapports_regimes.values():
                if not (r.respecte_puissance and r.respecte_tension_bus and r.respecte_courant_cellule):
                    ok = False
                    break
            if ok:
                trouve = True
                break
            np_ += 1

        if not trouve:
            continue

        assert candidat is not None
        score = candidat.score_selection
        if meilleur is None:
            meilleur = candidat
            meilleur_score = score
            continue

        assert meilleur_score is not None
        score_tuple = (
            score["nb_cellules_total"],
            score["surenergie_kwh"],
            score["ecart_tension_nominale_v"],
            score["masse_totale_pack_kg"],
        )
        best_tuple = (
            meilleur_score["nb_cellules_total"],
            meilleur_score["surenergie_kwh"],
            meilleur_score["ecart_tension_nominale_v"],
            meilleur_score["masse_totale_pack_kg"],
        )
        if score_tuple < best_tuple:
            meilleur = candidat
            meilleur_score = score

    if meilleur is None:
        detail = "\n".join(erreurs_globales[:20])
        raise ValueError(
            "Aucune configuration (Ns, Np) n'a satisfait simultanément les contraintes."
            + ("\nDétails:\n" + detail if detail else "")
        )

    return meilleur


# =============================================================================
# Fonctions haut niveau Samsung 25R
# =============================================================================


def choisir_configuration_depuis_cellules(
    *,
    nb_cellules_total: Optional[int] = None,
    nb_series: Optional[int] = None,
    nb_parallele: Optional[int] = None,
    tension_nominale_cible_v: Optional[float] = None,
    energie_nominale_cible_kwh: Optional[float] = None,
    cellule: Optional[Cellule] = None,
) -> Tuple[int, int, int]:
    """
    Choisit une configuration S/P.

    Priorité :
    1. nb_series + nb_parallele imposés ;
    2. énergie cible + tension cible ;
    3. nombre total + tension cible ;
    4. nombre total seul : 14S par défaut si possible.
    """
    if cellule is None:
        cellule = creer_cellule_samsung_25r()

    if nb_series is not None and nb_parallele is not None:
        ns = int(_exiger_positif("nb_series", nb_series, strict=True))
        np_ = int(_exiger_positif("nb_parallele", nb_parallele, strict=True))
        return ns, np_, ns * np_

    if energie_nominale_cible_kwh is not None and tension_nominale_cible_v is not None:
        E = _exiger_positif("energie_nominale_cible_kwh", energie_nominale_cible_kwh, strict=True)
        V = _exiger_positif("tension_nominale_cible_v", tension_nominale_cible_v, strict=True)
        ns = max(1, int(round(V / cellule.tension_nominale_v)))
        e_string = ns * cellule.capacite_nominale_ah * cellule.tension_nominale_v / 1000.0
        np_ = max(1, _ceil_div_pos(E, e_string))
        return ns, np_, ns * np_

    if nb_cellules_total is not None and tension_nominale_cible_v is not None:
        n_req = int(_exiger_positif("nb_cellules_total", nb_cellules_total, strict=True))
        V = _exiger_positif("tension_nominale_cible_v", tension_nominale_cible_v, strict=True)
        ns = max(1, int(round(V / cellule.tension_nominale_v)))
        if n_req < ns:
            raise ValueError(f"Nombre de cellules insuffisant : {n_req} cellules pour {ns}S.")
        np_ = max(1, n_req // ns)
        return ns, np_, ns * np_

    if nb_cellules_total is not None:
        n_req = int(_exiger_positif("nb_cellules_total", nb_cellules_total, strict=True))
        ns = min(14, n_req)
        np_ = max(1, n_req // ns)
        return ns, np_, ns * np_

    raise ValueError(
        "Fournir soit nb_series+nb_parallele, soit energie_nominale_cible_kwh+tension_nominale_cible_v, "
        "soit nb_cellules_total."
    )



def definir_batterie_samsung_25r(
    *,
    nb_cellules_total: Optional[int] = None,
    nb_series: Optional[int] = None,
    nb_parallele: Optional[int] = None,
    tension_nominale_cible_v: Optional[float] = None,
    energie_nominale_cible_kwh: Optional[float] = None,
    puissance_continue_kw: float = 0.0,
    puissance_pic_kw: float = 0.0,
    courant_decharge_cellule_conception_a: float = 10.0,
    courant_charge_cellule_a: float = 2.0,
    rendement_charge: float = 0.92,
    reserve_soc: float = 0.10,
    masse_hors_cellules_kg: Optional[float] = None,
    volume_hors_cellules_m3: float = 0.0,
    resistance_hors_cellules_ohm: float = 0.0,
    utiliser_resistance_max: bool = False,
) -> DimensionnementPack:
    """
    Fonction la plus simple pour ton usage.

    Elle accepte un nombre de cellules variable ou une cible énergie/tension,
    construit la cellule Samsung 25R, choisit S/P, puis renvoie un rapport complet.
    """
    _exiger_ratio_0_1("reserve_soc", reserve_soc, strict_min=False)
    cellule = creer_cellule_samsung_25r(
        courant_decharge_conception_a=courant_decharge_cellule_conception_a,
        utiliser_resistance_max=utiliser_resistance_max,
    )
    ns, np_, n_used = choisir_configuration_depuis_cellules(
        nb_cellules_total=nb_cellules_total,
        nb_series=nb_series,
        nb_parallele=nb_parallele,
        tension_nominale_cible_v=tension_nominale_cible_v,
        energie_nominale_cible_kwh=energie_nominale_cible_kwh,
        cellule=cellule,
    )

    e_nom = n_used * cellule.capacite_nominale_ah * cellule.tension_nominale_v / 1000.0
    if energie_nominale_cible_kwh is None:
        energie_nominale_cible_kwh = e_nom

    # Si l'appelant ne donne pas de masse hors cellules, on ajoute une surmasse
    # indicative de 35% pour boîtier, busbars, BMS, câbles, isolants, fixations.
    if masse_hors_cellules_kg is None:
        masse_hors_cellules_kg = n_used * cellule.masse_kg * 0.35

    pertes_passives = PertesPassivesPack(
        resistance_hors_cellules_ohm=resistance_hors_cellules_ohm,
        masse_hors_cellules_kg=masse_hors_cellules_kg,
        volume_hors_cellules_m3=volume_hors_cellules_m3,
    )

    contraintes = ContraintesPack(
        energie_nominale_cible_kwh=float(energie_nominale_cible_kwh),
        tension_bus_min_v=ns * cellule.tension_min_v,
        tension_bus_max_v=ns * cellule.tension_max_v,
        puissance_continue_kw=puissance_continue_kw,
        puissance_pic_kw=puissance_pic_kw,
        tension_nominale_cible_v=tension_nominale_cible_v or ns * cellule.tension_nominale_v,
    )

    cellules_non_utilisees = 0
    if nb_cellules_total is not None:
        cellules_non_utilisees = int(nb_cellules_total) - n_used

    rapport = evaluer_configuration_pack_cellules(
        cellule=cellule,
        nb_series=ns,
        nb_parallele=np_,
        contraintes=contraintes,
        pertes_passives=pertes_passives,
        modele_thermique=None,
        courant_charge_cellule_a=courant_charge_cellule_a,
        rendement_charge=rendement_charge,
        cellules_non_utilisees=cellules_non_utilisees,
    )

    avertissements = list(rapport.avertissements)
    energie_utile = rapport.energie_nominale_pack_kwh * (1.0 - reserve_soc)
    avertissements.append(
        f"Énergie utile indicative avec réserve SOC {reserve_soc:.0%}: {energie_utile:.3f} kWh."
    )

    # Recréation avec avertissement enrichi, dataclass frozen.
    return DimensionnementPack(
        **{k: v for k, v in rapport.en_dict().items() if k not in {"avertissements", "rapports_regimes", "rapports_thermiques", "rapports_charge", "securite"}},
        rapports_regimes=rapport.rapports_regimes,
        rapports_thermiques=rapport.rapports_thermiques,
        rapports_charge=rapport.rapports_charge,
        securite=rapport.securite,
        avertissements=avertissements,
    )



def dimensionner_pack_samsung_25r_equivalent_twingo(
    *,
    puissance_continue_kw: float = 0.0,
    puissance_pic_kw: float = 0.0,
    courant_decharge_cellule_conception_a: float = 10.0,
    courant_charge_cellule_a: float = 2.0,
) -> DimensionnementPack:
    """
    Cas pratique proche d'une batterie 22 kWh / environ 345,6 V nominal.
    La configuration attendue est généralement 96S26P = 2496 cellules.

    Par défaut, aucune puissance moteur n'est imposée : la fonction définit la
    batterie. Donne puissance_continue_kw et puissance_pic_kw si tu veux aussi
    valider la décharge sous charge.
    """
    return definir_batterie_samsung_25r(
        energie_nominale_cible_kwh=22.0,
        tension_nominale_cible_v=345.6,
        puissance_continue_kw=puissance_continue_kw,
        puissance_pic_kw=puissance_pic_kw,
        courant_decharge_cellule_conception_a=courant_decharge_cellule_conception_a,
        courant_charge_cellule_a=courant_charge_cellule_a,
    )


# =============================================================================
# Affichage texte
# =============================================================================


def formatter_rapport_pack(rapport: DimensionnementPack) -> str:
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append(f"RAPPORT PACK — {rapport.cellule_reference}")
    lines.append("=" * 78)
    lines.append("\n[Configuration]")
    lines.append(f"- Série / parallèle : {rapport.nb_series}S{rapport.nb_parallele}P")
    lines.append(f"- Cellules utilisées : {rapport.nb_cellules_total}")
    if rapport.cellules_non_utilisees:
        lines.append(f"- Cellules non utilisées : {rapport.cellules_non_utilisees}")
    lines.append(f"- Tension nominale : {rapport.tension_nominale_pack_v:.2f} V")
    lines.append(f"- Tension pleine charge : {rapport.tension_max_pack_v:.2f} V")
    lines.append(f"- Capacité : {rapport.capacite_pack_ah:.2f} Ah")
    lines.append(f"- Énergie nominale : {rapport.energie_nominale_pack_kwh:.3f} kWh")
    lines.append(f"- Énergie fenêtre SOC modélisée : {rapport.energie_approx_entre_soc_min_et_max_kwh:.3f} kWh")

    lines.append("\n[Masse / volume]")
    lines.append(f"- Masse cellules : {rapport.masse_cellules_kg:.2f} kg")
    lines.append(f"- Masse pack estimée : {rapport.masse_totale_pack_kg:.2f} kg")
    if rapport.volume_total_pack_m3 is not None:
        lines.append(f"- Volume total estimé : {rapport.volume_total_pack_m3:.4f} m³")

    lines.append("\n[Décharge]")
    for cle, r in rapport.rapports_regimes.items():
        lines.append(
            f"- {cle}: {r.puissance_demande_kw:.2f} kW | "
            f"Ipack={_round(r.courant_pack_a, 2)} A | "
            f"Icell={_round(r.courant_cellule_a, 2)} A | "
            f"Vcharge={_round(r.tension_charge_pack_v, 2)} V | "
            f"pertes={_round(None if r.pertes_joule_w is None else r.pertes_joule_w / 1000.0, 3)} kW"
        )

    if rapport.rapports_charge is not None:
        c = rapport.rapports_charge
        lines.append("\n[Charge]")
        lines.append(f"- Courant charge cellule : {c.courant_charge_cellule_a:.2f} A")
        lines.append(f"- Courant charge pack : {c.courant_charge_pack_a:.2f} A")
        lines.append(f"- Puissance charge nominale : {c.puissance_charge_nominale_kw:.2f} kW")
        lines.append(f"- Puissance charge pleine tension : {c.puissance_charge_pleine_tension_kw:.2f} kW")
        lines.append(f"- Temps 0–100% approx. : {_round(c.temps_charge_0_100_h, 2)} h")
        lines.append(f"- Temps 10–80% approx. : {_round(c.temps_charge_10_80_h, 2)} h")

    if rapport.securite is not None:
        s = rapport.securite
        lines.append("\n[Sécurité]")
        lines.append(f"- BMS recommandé : {s.bms_recommande}")
        lines.append(f"- Courant BMS décharge min : {s.courant_bms_decharge_min_a:.0f} A")
        lines.append(f"- Courant BMS charge min : {s.courant_bms_charge_min_a:.0f} A")
        lines.append(f"- Fusible principal estimatif : {s.fusible_principal_estime_a:.0f} A")
        lines.append(f"- Haute tension : {'oui' if s.haute_tension else 'non'}")
        lines.append(f"- Très haute tension : {'oui' if s.tres_haute_tension else 'non'}")

    if rapport.avertissements:
        lines.append("\n[Avertissements]")
        for msg in rapport.avertissements:
            lines.append(f"! {msg}")

    lines.append("\n" + "=" * 78)
    return "\n".join(lines)


__all__ = [
    "PointCellule",
    "Cellule",
    "PertesPassivesPack",
    "ModeleThermiquePack",
    "ContraintesPack",
    "RapportRegime",
    "RapportThermique",
    "RapportCharge",
    "RapportSecuritePack",
    "DimensionnementPack",
    "volume_cylindre_m3",
    "creer_cellule_samsung_25r",
    "calcul_resistance_pack",
    "calcul_puissance_max_pack",
    "resoudre_point_puissance",
    "evaluer_thermique_pack",
    "temperature_cellule_estimee",
    "calculer_rapport_charge",
    "calculer_rapport_securite",
    "evaluer_configuration_pack_cellules",
    "dimensionner_pack_cellules",
    "choisir_configuration_depuis_cellules",
    "definir_batterie_samsung_25r",
    "dimensionner_pack_samsung_25r_equivalent_twingo",
    "formatter_rapport_pack",
]


if __name__ == "__main__":
    rep = dimensionner_pack_samsung_25r_equivalent_twingo()
    print(formatter_rapport_pack(rep))
