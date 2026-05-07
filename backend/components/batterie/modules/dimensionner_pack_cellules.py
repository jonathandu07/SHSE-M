from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# =============================================================================
# Utilitaires robustesse
# =============================================================================


def _est_fini(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))



def _exiger_fini(nom: str, x: float) -> float:
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)



def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x



def _exiger_ratio_0_1(nom: str, x: float, *, strict_min: bool = False) -> float:
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


# =============================================================================
# Données d'entrée
# =============================================================================


@dataclass(frozen=True)
class PointCellule:
    """
    État caractéristique réel ou mesuré de la cellule.

    Ce point doit correspondre à un état cohérent :
    - soc_min / température basse / courant max décharge -> point défavorable décharge
    - nominal -> point médian représentatif
    - soc_max -> point haut de charge / tension haute

    Aucune loi OCV(SOC,T) n'est inventée dans ce module :
    l'appelant fournit directement les grandeurs à utiliser.
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
        if self.point_max_charge.tension_ocv_v > self.tension_max_v:
            raise ValueError("point_max_charge.tension_ocv_v ne peut pas dépasser tension_max_v.")
        if self.point_min_decharge.tension_ocv_v < self.tension_min_v:
            raise ValueError("point_min_decharge.tension_ocv_v ne peut pas être < tension_min_v.")


@dataclass(frozen=True)
class PertesPassivesPack:
    """
    Contributions hors cellules.

    Les valeurs par défaut à 0 signifient explicitement :
    "non prises en compte" et non une hypothèse métier cachée.
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


# =============================================================================
# Briques de calcul
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

    r_extra = 0.0
    if pertes_passives is not None:
        r_extra = float(pertes_passives.resistance_hors_cellules_ohm)

    return (ns / np_) * r_cell + r_extra



def calcul_puissance_max_pack(
    *,
    tension_ocv_pack_v: float,
    resistance_pack_ohm: float,
    courant_pack_limite_a: Optional[float] = None,
) -> float:
    """
    Puissance maximale soutenable sur une charge résistive simple :
        P(I) = (Voc - I*R) * I

    Sans limite courant : maximum pour I = Voc / (2R)
    Avec limite courant : maximum sur [0, I_lim].
    """
    voc = _exiger_positif("tension_ocv_pack_v", tension_ocv_pack_v, strict=True)
    r = _exiger_positif("resistance_pack_ohm", resistance_pack_ohm, strict=False)

    if courant_pack_limite_a is not None:
        i_lim = _exiger_positif("courant_pack_limite_a", courant_pack_limite_a, strict=True)
    else:
        i_lim = None

    if r == 0.0:
        if i_lim is None:
            return math.inf
        return voc * i_lim / 1000.0

    i_opt = voc / (2.0 * r)
    if i_lim is None:
        i_use = i_opt
    else:
        i_use = min(i_opt, i_lim)

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
    Résout le point de fonctionnement pour une puissance demandée P :

        V = Voc - I*R
        P = V*I

    Soit : R*I^2 - Voc*I + P = 0

    On retient la petite racine positive (régime stable côté courant minimal).
    """
    voc = _exiger_positif("tension_ocv_pack_v", tension_ocv_pack_v, strict=True)
    r = _exiger_positif("resistance_pack_ohm", resistance_pack_ohm, strict=False)
    p_kw = _exiger_positif("puissance_demande_kw", puissance_demande_kw, strict=False)

    if courant_pack_limite_a is not None:
        i_lim = _exiger_positif("courant_pack_limite_a", courant_pack_limite_a, strict=True)
    else:
        i_lim = None

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
            "message": None,
        }

    if r == 0.0:
        i = (p_kw * 1000.0) / voc
        if i_lim is not None and i > i_lim:
            return {
                "faisable": False,
                "courant_pack_a": None,
                "tension_charge_pack_v": None,
                "pertes_joule_w": None,
                "puissance_max_theorique_kw": math.inf,
                "puissance_max_limitee_courant_kw": calcul_puissance_max_pack(
                    tension_ocv_pack_v=voc,
                    resistance_pack_ohm=r,
                    courant_pack_limite_a=i_lim,
                ),
                "message": "Puissance demandée incompatible avec la limite de courant pack.",
            }
        return {
            "faisable": True,
            "courant_pack_a": i,
            "tension_charge_pack_v": voc,
            "pertes_joule_w": 0.0,
            "puissance_max_theorique_kw": math.inf,
            "puissance_max_limitee_courant_kw": calcul_puissance_max_pack(
                tension_ocv_pack_v=voc,
                resistance_pack_ohm=r,
                courant_pack_limite_a=i_lim,
            ),
            "message": None,
        }

    p_w = p_kw * 1000.0
    discr = voc * voc - 4.0 * r * p_w

    if discr < 0.0:
        return {
            "faisable": False,
            "courant_pack_a": None,
            "tension_charge_pack_v": None,
            "pertes_joule_w": None,
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
            "message": "Puissance demandée supérieure au maximum théorique imposé par Voc et R.",
        }

    rac = math.sqrt(discr)
    i = (voc - rac) / (2.0 * r)

    if i <= 0.0:
        return {
            "faisable": False,
            "courant_pack_a": None,
            "tension_charge_pack_v": None,
            "pertes_joule_w": None,
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
            "message": "Résolution quadratique non physique (courant <= 0).",
        }

    if i_lim is not None and i > i_lim:
        return {
            "faisable": False,
            "courant_pack_a": i,
            "tension_charge_pack_v": None,
            "pertes_joule_w": None,
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
            "message": "Puissance demandée incompatible avec la limite de courant pack.",
        }

    v_charge = voc - i * r
    p_loss = (i * i) * r

    return {
        "faisable": True,
        "courant_pack_a": i,
        "tension_charge_pack_v": v_charge,
        "pertes_joule_w": p_loss,
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
        "message": None,
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
    pertes_passives: Optional[PertesPassivesPack],
) -> RapportRegime:
    r_pack = calcul_resistance_pack(
        nb_series=nb_series,
        nb_parallele=nb_parallele,
        resistance_cellule_ohm=point_cellule.resistance_interne_ohm,
        pertes_passives=pertes_passives,
    )
    voc_pack = nb_series * point_cellule.tension_ocv_v
    i_lim_pack = nb_parallele * point_cellule.courant_decharge_max_a

    messages: List[str] = []
    sol = resoudre_point_puissance(
        tension_ocv_pack_v=voc_pack,
        resistance_pack_ohm=r_pack,
        puissance_demande_kw=puissance_demande_kw,
        courant_pack_limite_a=i_lim_pack,
    )

    respecte_puissance = bool(sol["faisable"])
    respecte_tension = False
    respecte_courant = False
    i_cell = None

    if sol["courant_pack_a"] is not None:
        i_cell = float(sol["courant_pack_a"]) / nb_parallele
        respecte_courant = i_cell <= point_cellule.courant_decharge_max_a + 1e-12
    if sol["tension_charge_pack_v"] is not None:
        respecte_tension = float(sol["tension_charge_pack_v"]) >= tension_bus_min_v - 1e-12

    if sol["message"]:
        messages.append(str(sol["message"]))
    if sol["tension_charge_pack_v"] is not None and not respecte_tension:
        messages.append(
            f"Tension pack sous charge inférieure à la tension bus minimale ({sol['tension_charge_pack_v']:.3f} V < {tension_bus_min_v:.3f} V)."
        )
    if i_cell is not None and not respecte_courant:
        messages.append(
            f"Courant cellule au-dessus de la limite ({i_cell:.3f} A > {point_cellule.courant_decharge_max_a:.3f} A)."
        )

    return RapportRegime(
        nom=nom,
        point_utilise=point_nom,
        puissance_demande_kw=float(puissance_demande_kw),
        puissance_max_theorique_kw=float(sol["puissance_max_theorique_kw"]),
        puissance_max_limitee_courant_kw=float(sol["puissance_max_limitee_courant_kw"]),
        tension_ocv_pack_v=float(voc_pack),
        tension_charge_pack_v=None if sol["tension_charge_pack_v"] is None else float(sol["tension_charge_pack_v"]),
        courant_pack_a=None if sol["courant_pack_a"] is None else float(sol["courant_pack_a"]),
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


# =============================================================================
# Dimensionnement principal
# =============================================================================


def dimensionner_pack_cellules(
    *,
    cellule: Cellule,
    contraintes: ContraintesPack,
    pertes_passives: Optional[PertesPassivesPack] = None,
    modele_thermique: Optional[ModeleThermiquePack] = None,
    nb_series_min: Optional[int] = None,
    nb_series_max: Optional[int] = None,
) -> DimensionnementPack:
    """
    Dimensionne un pack série/parallèle sans hypothèse métier implicite.

    Ce que fait le module :
    - dimensionne Np sur l'énergie nominale cible,
    - balaye Ns dans un domaine physiquement admissible,
    - vérifie tension max, tension sous charge, courant cellule, puissance continue et pic,
    - calcule masse, volume, résistances, pertes Joule,
    - produit un rapport détaillé.

    Ce que le module ne fait pas :
    - n'invente pas de courbe OCV(SOC,T),
    - n'invente pas de résistance vs température,
    - n'invente pas de rendement de refroidissement,
    - n'invente pas de vieillissement.

    L'appelant doit fournir les points de cellule pertinents.
    """
    if pertes_passives is None:
        pertes_passives = PertesPassivesPack()

    e_target_kwh = contraintes.energie_nominale_cible_kwh
    e_string_kwh_ref = (cellule.capacite_nominale_ah * cellule.tension_nominale_v) / 1000.0
    if e_string_kwh_ref <= 0.0:
        raise ValueError("Énergie nominale par cellule non positive.")

    # Domaine Ns imposé par la tension minimale à vide et la tension max de charge.
    ns_min_auto = max(1, _ceil_div_pos(contraintes.tension_bus_min_v, cellule.point_min_decharge.tension_ocv_v))
    ns_max_auto = int(math.floor(contraintes.tension_bus_max_v / cellule.tension_max_v))

    if ns_max_auto < 1:
        raise ValueError("Aucune valeur de Ns possible : tension_bus_max_v trop faible par rapport à la tension max cellule.")

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
        e_string_kwh = ns * e_string_kwh_ref
        np_energy = max(1, _ceil_div_pos(e_target_kwh, e_string_kwh))

        # Démarrage sur le plancher énergétique; on augmente Np jusqu'à satisfaction des contraintes.
        np_ = np_energy
        trouve = False

        while np_ <= 1_000_000:
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

            tension_max_pack = ns * cellule.tension_max_v
            respecte_tension_haute = tension_max_pack <= contraintes.tension_bus_max_v + 1e-12

            if not respecte_tension_haute:
                erreurs_globales.append(
                    f"Ns={ns}: tension max pack {tension_max_pack:.3f} V > tension bus max {contraintes.tension_bus_max_v:.3f} V."
                )
                break

            ok = all([
                rapport_cont_min.respecte_puissance,
                rapport_cont_min.respecte_tension_bus,
                rapport_cont_min.respecte_courant_cellule,
                rapport_pic_min.respecte_puissance,
                rapport_pic_min.respecte_tension_bus,
                rapport_pic_min.respecte_courant_cellule,
                rapport_cont_nom.respecte_puissance,
                rapport_cont_nom.respecte_tension_bus,
                rapport_cont_nom.respecte_courant_cellule,
            ])

            if ok:
                trouve = True
                break

            np_ += 1

        if not trouve:
            continue

        nb_total = ns * np_
        capacite_pack_ah = np_ * cellule.capacite_nominale_ah
        e_nom_pack_kwh = nb_total * cellule.capacite_nominale_ah * cellule.tension_nominale_v / 1000.0
        tension_nom_pack = ns * cellule.tension_nominale_v
        fenetre_soc = cellule.point_max_charge.soc - cellule.point_min_decharge.soc
        e_approx_fenetre = e_nom_pack_kwh * fenetre_soc
        marge_energie = e_nom_pack_kwh - e_target_kwh

        masse_cellules = nb_total * cellule.masse_kg
        masse_totale = masse_cellules + pertes_passives.masse_hors_cellules_kg

        if cellule.volume_m3 is None:
            volume_cellules = None
            volume_total = None if pertes_passives.volume_hors_cellules_m3 == 0.0 else pertes_passives.volume_hors_cellules_m3
        else:
            volume_cellules = nb_total * cellule.volume_m3
            volume_total = volume_cellules + pertes_passives.volume_hors_cellules_m3

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

        rapports_regimes: Dict[str, RapportRegime] = {
            "continu_min": rapport_cont_min,
            "pic_min": rapport_pic_min,
            "continu_nominal": rapport_cont_nom,
        }

        rapports_thermiques: Dict[str, RapportThermique] = {}
        avertissements: List[str] = []

        if cellule.volume_m3 is None:
            avertissements.append("volume_m3 cellule non fourni : volume pack non calculé complètement.")
        if modele_thermique is None:
            avertissements.append("ModeleThermiquePack non fourni : thermique pack non évaluée.")
        else:
            if rapport_cont_min.pertes_joule_w is not None:
                rapports_thermiques["continu_min"] = evaluer_thermique_pack(
                    nom="continu_min",
                    pertes_w=rapport_cont_min.pertes_joule_w,
                    modele=modele_thermique,
                    duree_s=contraintes.duree_regime_continu_s,
                )
            if rapport_pic_min.pertes_joule_w is not None:
                rapports_thermiques["pic_min"] = evaluer_thermique_pack(
                    nom="pic_min",
                    pertes_w=rapport_pic_min.pertes_joule_w,
                    modele=modele_thermique,
                    duree_s=contraintes.duree_pic_s,
                )
            if rapport_cont_nom.pertes_joule_w is not None:
                rapports_thermiques["continu_nominal"] = evaluer_thermique_pack(
                    nom="continu_nominal",
                    pertes_w=rapport_cont_nom.pertes_joule_w,
                    modele=modele_thermique,
                    duree_s=contraintes.duree_regime_continu_s,
                )

        for cle, rapport in rapports_regimes.items():
            for msg in rapport.messages:
                avertissements.append(f"{cle}: {msg}")

        delta_v_nom = 0.0
        if contraintes.tension_nominale_cible_v is not None:
            delta_v_nom = abs(tension_nom_pack - contraintes.tension_nominale_cible_v)

        score = {
            "nb_cellules_total": float(nb_total),
            "surenergie_kwh": float(marge_energie),
            "ecart_tension_nominale_v": float(delta_v_nom),
            "masse_totale_pack_kg": float(masse_totale),
        }

        candidat = DimensionnementPack(
            cellule_reference=cellule.reference,
            nb_series=ns,
            nb_parallele=np_,
            nb_cellules_total=nb_total,
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
        )

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


__all__ = [
    "PointCellule",
    "Cellule",
    "PertesPassivesPack",
    "ModeleThermiquePack",
    "ContraintesPack",
    "RapportRegime",
    "RapportThermique",
    "DimensionnementPack",
    "calcul_resistance_pack",
    "calcul_puissance_max_pack",
    "resoudre_point_puissance",
    "evaluer_thermique_pack",
    "dimensionner_pack_cellules",
]
