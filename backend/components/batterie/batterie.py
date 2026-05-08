# backend/components/batterie.py
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import math

# ============================================================
# Imports des modules batterie (robustes)
# ============================================================

# calcul_dimensionnement_batterie.py
try:
    from backend.components.batterie.modules.calcul_dimensionnement_batterie import (
        calcul_capacite_totale_batterie,
        calcul_poids_batterie,
    )
except Exception:
    from backend.components.batterie.modules.calcul_dimensionnement_batterie import (  # type: ignore
        calcul_capacite_totale_batterie,
        calcul_poids_batterie,
    )

# calcul_energie_utile.py
try:
    from backend.components.batterie.modules.calcul_energie_utile import (
        calcul_energie_utile_cible,
        calcul_energie_utile_trajet,
        calcul_energie_utile_pic,
        choisir_energie_utile_finale,
    )
except Exception:
    from backend.components.batterie.modules.calcul_energie_utile import (  # type: ignore
        calcul_energie_utile_cible,
        calcul_energie_utile_trajet,
        calcul_energie_utile_pic,
        choisir_energie_utile_finale,
    )

# calcul_temps_charge.py
try:
    from backend.components.batterie.modules.calcul_temps_charge import calcul_temps_charge
except Exception:
    from backend.components.batterie.modules.calcul_temps_charge import calcul_temps_charge  # type: ignore

# calcul_electrique_pack.py
try:
    from backend.components.batterie.modules.calcul_electrique_pack import (
        calcul_conso_kwh_km_depuis_puissance_vitesse,
        calcul_ah_depuis_kwh_tension,
        calcul_courant_depuis_kw_tension,
        calcul_c_rate_depuis_kw_kwh,
        calcul_puissance_effective_stockee,
        calcul_puissance_charge_requise,
    )
except Exception:
    from backend.components.batterie.modules.calcul_electrique_pack import (  # type: ignore
        calcul_conso_kwh_km_depuis_puissance_vitesse,
        calcul_ah_depuis_kwh_tension,
        calcul_courant_depuis_kw_tension,
        calcul_c_rate_depuis_kw_kwh,
        calcul_puissance_effective_stockee,
        calcul_puissance_charge_requise,
    )

# electrolyte_solide.py
try:
    from backend.components.batterie.modules.electrolyte_solide import (
        ElectrolyteSolide,
        CelluleSolide,
        PackSolide,
        Options as ElectrolyteOptions,
        evaluer_electrolyte_solide,
    )
except Exception:
    from backend.components.batterie.modules.electrolyte_solide import (  # type: ignore
        ElectrolyteSolide,
        CelluleSolide,
        PackSolide,
        Options as ElectrolyteOptions,
        evaluer_electrolyte_solide,
    )

# dimensionner_pack_cellules.py
try:
    from backend.components.batterie.modules.dimensionner_pack_cellules import (
        Cellule as CellulePack,
        PertesPassivesPack,
        ModeleThermiquePack,
        ContraintesPack,
        DimensionnementPack,
        dimensionner_pack_cellules,
    )
except Exception:
    from backend.components.batterie.modules.dimensionner_pack_cellules import (  # type: ignore
        Cellule as CellulePack,
        PertesPassivesPack,
        ModeleThermiquePack,
        ContraintesPack,
        DimensionnementPack,
        dimensionner_pack_cellules,
    )

# scraping_cellules_batterie.py
try:
    from backend.components.batterie.modules.scraping_cellules_batterie import (
        CelluleCommerciale,
        collecter_catalogue_cellules,
        classer_candidats_pre_dimensionnement,
        exigences_pour_cellule_complete,
        cellule_vers_dict,
    )

    from backend.components.batterie.pieces.pack_batterie import PackBatterie
    from backend.components.batterie.pieces.busbars_batterie import BusbarsBatterie
    from backend.components.batterie.pieces.boitier_batterie import BoitierBatterie
    from backend.components.batterie.pieces.bms_batterie import BMSBatterie
    from backend.components.batterie.pieces.tms_batterie import TMSBatterie
except Exception:
    from backend.components.batterie.modules.scraping_cellules_batterie import (  # type: ignore
        CelluleCommerciale,
        collecter_catalogue_cellules,
        classer_candidats_pre_dimensionnement,
        exigences_pour_cellule_complete,
        cellule_vers_dict,
    )
    from backend.components.batterie.pieces.pack_batterie import PackBatterie  # type: ignore
    from backend.components.batterie.pieces.busbars_batterie import BusbarsBatterie  # type: ignore
    from backend.components.batterie.pieces.boitier_batterie import BoitierBatterie  # type: ignore
    from backend.components.batterie.pieces.bms_batterie import BMSBatterie  # type: ignore
    from backend.components.batterie.pieces.tms_batterie import TMSBatterie  # type: ignore


# ============================================================
# Helpers (robustesse + inconnues) — sans hypothèses implicites
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


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


def _require_ratio_0_1_closed_open(name: str, x: Any, *, allow_zero: bool = False) -> float:
    """
    Exige :
      - allow_zero=False : 0 < x <= 1
      - allow_zero=True  : 0 <= x <= 1
    """
    v = _require_finite(name, x)
    if allow_zero:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"{name} doit être dans [0,1] (reçu: {v}).")
    else:
        if v <= 0.0 or v > 1.0:
            raise ValueError(f"{name} doit être dans (0,1] (reçu: {v}).")
    return v


def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})


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


def _require_int_pos(name: str, x: Any) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un int (reçu: {x!r}).")
    if x <= 0:
        raise ValueError(f"{name} doit être > 0 (reçu: {x}).")
    return x


def _serialize_obj(x: Any) -> Any:
    if x is None:
        return None
    if hasattr(x, "en_dict") and callable(x.en_dict):
        return x.en_dict()
    if is_dataclass(x):
        return asdict(x)
    if isinstance(x, dict):
        return {k: _serialize_obj(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_serialize_obj(v) for v in x]
    return x


# ============================================================
# Composant Batterie
# ============================================================

@dataclass(frozen=True)
class Batterie:
    """
    Dimensionnement "pack batterie" basé sur tes modules.

    Règles :
      - on ne calcule que si les entrées nécessaires existent ;
      - sinon : inconnue (partielle ou impossible) avec justification ;
      - aucune valeur implicite : pas de constante métier cachée ;
      - le catalogue commercial sert au pré-dimensionnement ;
      - le dimensionnement fin strict exige une `CellulePack` complète.
    """

    # Fenêtre SOC utilisable (0 < w <= 1)
    fenetre_soc: float = 0.8

    # Densité énergétique au niveau pack (kWh/kg)
    densite_energetique_kwh_kg: Optional[float] = None

    # Charge
    rendement_charge: float = 0.90
    puissance_charge_kw: Optional[float] = None

    # Électrique pack
    tension_nominale_v: Optional[float] = None
    tension_charge_v: Optional[float] = None

    # Pieces optionnelles
    piece_pack: Optional[PackBatterie] = None
    piece_busbars: Optional[BusbarsBatterie] = None
    piece_boitier: Optional[BoitierBatterie] = None
    piece_bms: Optional[BMSBatterie] = None
    piece_tms: Optional[TMSBatterie] = None

    def analyser_dimensionnement(
        self,
        *,
        # 1) Critère autonomie (trajet)
        distance_km: Optional[float] = None,
        conso_kwh_km: Optional[float] = None,

        # 2) Alternative : conso dérivée de puissance+vitesse moyenne
        puissance_moyenne_kw: Optional[float] = None,
        vitesse_moyenne_kmh: Optional[float] = None,

        # 3) Critère recharge (temps cible)
        temps_charge_cible_h: Optional[float] = None,

        # 4) Critère pic (tampon énergie)
        puissance_pic_kw: Optional[float] = None,
        duree_pic_s: Optional[float] = None,

        # 5) Si tu as déjà une énergie utile imposée
        energie_utile_imposee_kwh: Optional[float] = None,

        # 6) Agrégation des contraintes d'énergie utile :
        #    - "max" : même logique que choisir_energie_utile_finale
        #    - "somme" : additionne les contraintes disponibles
        mode_aggregation_energie: str = "max",

        # 7) Si temps cible fourni mais pas puissance_charge_kw : calculer la puissance requise
        calculer_puissance_charge_requise: bool = True,

        # 8) Analyse électrolyte solide (optionnelle)
        activer_electrolyte_solide: bool = False,

        # (Pack) topologie pack
        nb_series: Optional[int] = None,
        nb_parallele: Optional[int] = None,

        # (Cellule) paramètres requis pour relier pack->cellule (modèle simple électrolyte)
        tension_cellule_v: Optional[float] = None,
        capacite_cellule_ah: Optional[float] = None,
        courant_cellule_max_a: Optional[float] = None,

        # (Électrolyte solide) paramètres géométriques/matériaux
        conductivite_ionique_s_m: Optional[float] = None,
        epaisseur_electrolyte_m: Optional[float] = None,
        surface_active_m2: Optional[float] = None,
        resistance_interface_ohm: Optional[float] = None,

        # (Pack) puissances pour l'analyse electrolyte / dimensionnement fin
        puissance_pack_continue_kw: Optional[float] = None,
        puissance_pack_pic_kw: Optional[float] = None,
        rendement_chaine: Optional[float] = None,

        # (Options) electrolyte_solide
        electrolyte_strict: bool = False,

        # 9) Catalogue cellules commerciales / pré-dimensionnement
        activer_catalogue_cellules: bool = False,
        catalogue_cellules: Optional[Sequence[CelluleCommerciale]] = None,
        catalogue_top_n: int = 5,
        catalogue_sleep_s: float = 0.0,

        # 10) Dimensionnement fin strict
        activer_dimensionnement_fin: bool = False,
        cellule_pack: Optional[CellulePack] = None,
        energie_nominale_cible_pack_kwh: Optional[float] = None,
        tension_bus_min_v: Optional[float] = None,
        tension_bus_max_v: Optional[float] = None,
        tension_nominale_cible_pack_v: Optional[float] = None,
        pertes_passives_pack: Optional[PertesPassivesPack] = None,
        modele_thermique_pack: Optional[ModeleThermiquePack] = None,
        nb_series_min_dim: Optional[int] = None,
        nb_series_max_dim: Optional[int] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "energies_utiles": {},
            "dimensionnement": {},
            "charge": {},
            "electrique": {},
            "electrolyte_solide": {},
            "catalogue_cellules": {},
            "dimensionnement_fin": {},
            "hypotheses": [],
            "unites": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # ------------------------------------------------------------
        # Validations structurelles
        # ------------------------------------------------------------
        w = _require_ratio_0_1_closed_open("fenetre_soc", self.fenetre_soc, allow_zero=False)
        eta_charge = _require_ratio_0_1_closed_open("rendement_charge", self.rendement_charge, allow_zero=False)

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
            "calculer_puissance_charge_requise": calculer_puissance_charge_requise,
            # electrolyte
            "activer_electrolyte_solide": activer_electrolyte_solide,
            "nb_series": nb_series,
            "nb_parallele": nb_parallele,
            "tension_cellule_v": tension_cellule_v,
            "capacite_cellule_ah": capacite_cellule_ah,
            "courant_cellule_max_a": courant_cellule_max_a,
            "conductivite_ionique_s_m": conductivite_ionique_s_m,
            "epaisseur_electrolyte_m": epaisseur_electrolyte_m,
            "surface_active_m2": surface_active_m2,
            "resistance_interface_ohm": resistance_interface_ohm,
            "puissance_pack_continue_kw": puissance_pack_continue_kw,
            "puissance_pack_pic_kw": puissance_pack_pic_kw,
            "rendement_chaine": rendement_chaine,
            "electrolyte_strict": electrolyte_strict,
            # catalogue
            "activer_catalogue_cellules": activer_catalogue_cellules,
            "catalogue_top_n": catalogue_top_n,
            "catalogue_sleep_s": catalogue_sleep_s,
            # dimensionnement fin
            "activer_dimensionnement_fin": activer_dimensionnement_fin,
            "cellule_pack": None if cellule_pack is None else getattr(cellule_pack, "reference", "CellulePack"),
            "energie_nominale_cible_pack_kwh": energie_nominale_cible_pack_kwh,
            "tension_bus_min_v": tension_bus_min_v,
            "tension_bus_max_v": tension_bus_max_v,
            "tension_nominale_cible_pack_v": tension_nominale_cible_pack_v,
            "pertes_passives_pack": _serialize_obj(pertes_passives_pack),
            "modele_thermique_pack": _serialize_obj(modele_thermique_pack),
            "nb_series_min_dim": nb_series_min_dim,
            "nb_series_max_dim": nb_series_max_dim,
        }

        rapport["unites"] = {
            "E_*": "kWh",
            "capacite_totale": "kWh",
            "masse_batterie": "kg",
            "temps_charge": "h",
            "puissance_*": "kW",
            "tension_*": "V",
            "courant_*": "A",
            "capacite_Ah": "Ah",
            "C_rate_*": "h^-1",
            "asr": "ohm*m^2",
            "R_cell": "ohm",
            "P_pertes": "W",
            "dV_cell": "V",
        }

        # ------------------------------------------------------------
        # 1) Énergie utile trajet (directe ou déduite)
        # ------------------------------------------------------------
        E_trajet: Optional[float] = None
        conso_derivee: Optional[float] = None

        if distance_km is not None:
            d = _require_positive("distance_km", distance_km, strict=False)

            if conso_kwh_km is not None:
                c = _require_positive("conso_kwh_km", conso_kwh_km, strict=False)
                E_trajet = float(calcul_energie_utile_trajet(d, c))
            else:
                if puissance_moyenne_kw is not None and vitesse_moyenne_kmh is not None:
                    Pm = _require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
                    vm = _require_positive("vitesse_moyenne_kmh", vitesse_moyenne_kmh, strict=True)
                    conso_derivee = float(calcul_conso_kwh_km_depuis_puissance_vitesse(Pm, vm))
                    E_trajet = float(calcul_energie_utile_trajet(d, conso_derivee))
                    rapport["hypotheses"].append(
                        "conso_kwh_km dérivée via P_moy/v_moy (valable si puissance_moyenne_kw représente bien la puissance électrique pack sur la phase considérée)."
                    )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "E_trajet_kwh",
                        "Calculable si conso_kwh_km est fournie, ou si (puissance_moyenne_kw et vitesse_moyenne_kmh) sont fournis.",
                    )

        rapport["energies_utiles"]["conso_kwh_km_derivee"] = conso_derivee
        rapport["energies_utiles"]["E_trajet_kwh"] = E_trajet

        # ------------------------------------------------------------
        # 2) Énergie utile contrainte de recharge (si Pcharge connue)
        # ------------------------------------------------------------
        E_charge_cible: Optional[float] = None
        if temps_charge_cible_h is not None:
            t = _require_positive("temps_charge_cible_h", temps_charge_cible_h, strict=False)
            if self.puissance_charge_kw is not None:
                Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False)
                E_charge_cible = float(calcul_energie_utile_cible(t, Pchg, eta_charge))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "E_charge_cible_kwh",
                    "Calculable si puissance_charge_kw est fournie (ou indirectement si E_utile_finale est connue et qu'on calcule puissance_charge_requise_kw).",
                )
        rapport["energies_utiles"]["E_charge_cible_kwh"] = E_charge_cible

        # ------------------------------------------------------------
        # 3) Énergie utile pic (tampon)
        # ------------------------------------------------------------
        E_pic: Optional[float] = None
        if puissance_pic_kw is not None and duree_pic_s is not None:
            Pp = _require_positive("puissance_pic_kw", puissance_pic_kw, strict=False)
            ts = _require_positive("duree_pic_s", duree_pic_s, strict=False)
            E_pic = float(calcul_energie_utile_pic(Pp, ts))
        elif puissance_pic_kw is not None or duree_pic_s is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "E_pic_kwh",
                "Calculable si puissance_pic_kw ET duree_pic_s sont fournis.",
            )
        rapport["energies_utiles"]["E_pic_kwh"] = E_pic

        # ------------------------------------------------------------
        # 4) Énergie utile imposée
        # ------------------------------------------------------------
        E_imposee: Optional[float] = None
        if energie_utile_imposee_kwh is not None:
            E_imposee = _require_positive("energie_utile_imposee_kwh", energie_utile_imposee_kwh, strict=False)
        rapport["energies_utiles"]["E_imposee_kwh"] = E_imposee

        # ------------------------------------------------------------
        # 5) Agrégation énergie utile finale
        # ------------------------------------------------------------
        energies_candidates: List[float] = [v for v in (E_trajet, E_charge_cible, E_pic, E_imposee) if v is not None]
        E_u_final: Optional[float] = None

        if energies_candidates:
            if mode_aggregation_energie == "max":
                E_u_final = float(choisir_energie_utile_finale(*energies_candidates))
            else:
                E_u_final = float(sum(energies_candidates))
                rapport["hypotheses"].append(
                    "E_utile_finale obtenue par SOMME des contraintes disponibles (choix explicite de dimensionnement)."
                )
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "E_utile_finale_kwh",
                "Impossible sans au moins un critère (trajet, charge cible, pic, ou énergie imposée).",
            )

        rapport["dimensionnement"]["E_utile_finale_kwh"] = E_u_final

        # ------------------------------------------------------------
        # 6) Dimensionnement capacité totale + masse pack
        # ------------------------------------------------------------
        E_batt_tot: Optional[float] = None
        m_batt: Optional[float] = None

        if E_u_final is not None:
            E_batt_tot = float(calcul_capacite_totale_batterie(E_u_final, w))

            if self.densite_energetique_kwh_kg is not None:
                rho = _require_positive("densite_energetique_kwh_kg", self.densite_energetique_kwh_kg, strict=True)
                m_batt = float(calcul_poids_batterie(E_batt_tot, rho))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "masse_batterie_kg",
                    "Calculable si densite_energetique_kwh_kg (au niveau pack) est fournie.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "capacite_totale_kwh",
                "Calculable si E_utile_finale_kwh est déterminée.",
            )

        rapport["dimensionnement"]["capacite_totale_kwh"] = E_batt_tot
        rapport["dimensionnement"]["masse_batterie_kg"] = m_batt

        # ------------------------------------------------------------
        # 7) Charge : temps de charge, puissance requise, courant estimé
        # ------------------------------------------------------------
        t_charge: Optional[float] = None
        P_eff_kw: Optional[float] = None
        P_charge_requise_kw: Optional[float] = None
        I_charge_a: Optional[float] = None

        if E_u_final is not None:
            if self.puissance_charge_kw is not None:
                Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=True)
                t_charge = float(calcul_temps_charge(E_u_final, Pchg, eta_charge))
                P_eff_kw = float(calcul_puissance_effective_stockee(Pchg, eta_charge))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "temps_charge_h",
                    "Calculable si puissance_charge_kw est fournie.",
                )

            if temps_charge_cible_h is not None and calculer_puissance_charge_requise:
                t = _require_positive("temps_charge_cible_h", temps_charge_cible_h, strict=True)
                P_charge_requise_kw = float(calcul_puissance_charge_requise(E_u_final, t, eta_charge))
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "charge",
                "Calculable si E_utile_finale_kwh est déterminée et si (puissance_charge_kw ou temps_charge_cible_h) est fourni.",
            )

        if P_eff_kw is not None:
            Vchg = self.tension_charge_v if self.tension_charge_v is not None else self.tension_nominale_v
            if Vchg is not None:
                V = _require_positive("tension_charge_v|tension_nominale_v", Vchg, strict=True)
                I_charge_a = float(calcul_courant_depuis_kw_tension(P_eff_kw, V))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "courant_charge_A",
                    "Calculable si tension_charge_v (ou tension_nominale_v) est fournie.",
                )

        rapport["charge"]["temps_charge_h"] = t_charge
        rapport["charge"]["puissance_effective_stockee_kw"] = P_eff_kw
        rapport["charge"]["puissance_charge_requise_kw"] = P_charge_requise_kw
        rapport["charge"]["courant_charge_A"] = I_charge_a

        # ------------------------------------------------------------
        # 8) Électrique pack : Ah, courant décharge, C-rates
        # ------------------------------------------------------------
        capacite_ah: Optional[float] = None
        I_decharge_a: Optional[float] = None
        C_decharge: Optional[float] = None
        C_charge: Optional[float] = None

        if E_batt_tot is not None and self.tension_nominale_v is not None:
            Vn = _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)
            capacite_ah = float(calcul_ah_depuis_kwh_tension(E_batt_tot, Vn))
        elif E_batt_tot is not None and self.tension_nominale_v is None:
            _push_inconnue(
                rapport,
                "partielles",
                "capacite_Ah_estimee",
                "Calculable si tension_nominale_v est fournie (Ah = kWh*1000 / V).",
            )

        if puissance_moyenne_kw is not None and E_batt_tot is not None:
            Pm = _require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
            C_decharge = float(calcul_c_rate_depuis_kw_kwh(Pm, E_batt_tot))

            if self.tension_nominale_v is not None:
                Vn = _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)
                I_decharge_a = float(calcul_courant_depuis_kw_tension(Pm, Vn))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "courant_decharge_A_estime",
                    "Calculable si tension_nominale_v est fournie.",
                )
        elif puissance_moyenne_kw is not None and E_batt_tot is None:
            _push_inconnue(
                rapport,
                "partielles",
                "C_rate_decharge_estime",
                "Calculable si capacite_totale_kwh est déterminée.",
            )

        if self.puissance_charge_kw is not None and E_batt_tot is not None:
            Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False)
            C_charge = float(calcul_c_rate_depuis_kw_kwh(Pchg, E_batt_tot))
        elif self.puissance_charge_kw is not None and E_batt_tot is None:
            _push_inconnue(
                rapport,
                "partielles",
                "C_rate_charge_estime",
                "Calculable si capacite_totale_kwh est déterminée.",
            )

        rapport["electrique"]["capacite_Ah_estimee"] = capacite_ah
        rapport["electrique"]["courant_decharge_A_estime"] = I_decharge_a
        rapport["electrique"]["C_rate_decharge_estime"] = C_decharge
        rapport["electrique"]["C_rate_charge_estime"] = C_charge

        # ------------------------------------------------------------
        # 9) Électrolyte solide : exploiter au max ce qui est fourni
        # ------------------------------------------------------------
        if activer_electrolyte_solide:
            P_cont_kw = puissance_pack_continue_kw if puissance_pack_continue_kw is not None else puissance_moyenne_kw
            P_pic_kw = puissance_pack_pic_kw if puissance_pack_pic_kw is not None else puissance_pic_kw

            elec = ElectrolyteSolide(
                conductivite_ionique_s_m=conductivite_ionique_s_m,
                epaisseur_m=epaisseur_electrolyte_m,
                resistance_interface_ohm=resistance_interface_ohm,
            )
            cell = CelluleSolide(
                surface_active_m2=surface_active_m2,
                tension_nominale_v=tension_cellule_v,
                capacite_ah=capacite_cellule_ah,
                courant_max_a=courant_cellule_max_a,
            )
            pack_obj = PackSolide(
                nb_series=nb_series,
                nb_parallele=nb_parallele,
                puissance_continue_kw=P_cont_kw,
                puissance_pic_kw=P_pic_kw,
                rendement_chaine=rendement_chaine,
            )
            opts = ElectrolyteOptions(strict=bool(electrolyte_strict))

            try:
                rep = evaluer_electrolyte_solide(elec, cell, pack_obj, opts=opts)
                rapport["electrolyte_solide"] = {
                    "active": True,
                    "rapport": _serialize_obj(rep),
                }
            except Exception as e:
                rapport["electrolyte_solide"] = {"active": True, "erreur": str(e)}
                _push_inconnue(
                    rapport,
                    "partielles",
                    "electrolyte_solide",
                    f"Échec du calcul electrolyte_solide: {e}",
                )
        else:
            rapport["electrolyte_solide"] = {"active": False}

        # ------------------------------------------------------------
        # 10) Catalogue cellules commerciales : pré-dimensionnement
        # ------------------------------------------------------------
        if activer_catalogue_cellules:
            e_nom_cible_catalogue = (
                _require_positive("energie_nominale_cible_pack_kwh", energie_nominale_cible_pack_kwh, strict=False)
                if energie_nominale_cible_pack_kwh is not None
                else E_batt_tot
            )

            v_nom_cible_catalogue = (
                _require_positive("tension_nominale_cible_pack_v", tension_nominale_cible_pack_v, strict=True)
                if tension_nominale_cible_pack_v is not None
                else (
                    _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)
                    if self.tension_nominale_v is not None
                    else None
                )
            )

            if e_nom_cible_catalogue is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "catalogue_cellules",
                    "Pré-dimensionnement catalogue calculable si energie_nominale_cible_pack_kwh est fournie, ou si capacite_totale_kwh a été déterminée.",
                )
                rapport["catalogue_cellules"] = {"active": True, "candidats": []}
            elif v_nom_cible_catalogue is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "catalogue_cellules",
                    "Pré-dimensionnement catalogue calculable si tension_nominale_cible_pack_v est fournie, ou si Batterie.tension_nominale_v est connue.",
                )
                rapport["catalogue_cellules"] = {"active": True, "candidats": []}
            else:
                try:
                    cells: Sequence[CelluleCommerciale]
                    if catalogue_cellules is not None:
                        cells = catalogue_cellules
                        rapport["hypotheses"].append("Catalogue cellules fourni par l'appelant : aucune collecte HTTP déclenchée.")
                    else:
                        cells = collecter_catalogue_cellules(sleep_s=float(catalogue_sleep_s))
                        rapport["hypotheses"].append(
                            "Catalogue cellules collecté via les URLs explicites du module de scraping ; seules des valeurs publiées ou directement déductibles sont retenues."
                        )

                    candidats = classer_candidats_pre_dimensionnement(
                        cellules=cells,
                        energie_nominale_cible_kwh=e_nom_cible_catalogue,
                        tension_pack_nominale_cible_v=v_nom_cible_catalogue,
                        puissance_continue_kw=puissance_pack_continue_kw if puissance_pack_continue_kw is not None else puissance_moyenne_kw,
                        puissance_pic_kw=puissance_pack_pic_kw if puissance_pack_pic_kw is not None else puissance_pic_kw,
                    )

                    top = candidats[:catalogue_top_n]
                    top_serialized: List[Dict[str, Any]] = []
                    for predim in top:
                        src = next((c for c in cells if c.specs.reference == predim.reference), None)
                        besoins = [] if src is None else exigences_pour_cellule_complete(src.specs)
                        top_serialized.append(
                            {
                                "pre_dimensionnement": _serialize_obj(predim),
                                "cellule_catalogue": None if src is None else cellule_vers_dict(src),
                                "besoins_dimensionnement_fin": besoins,
                            }
                        )

                    rapport["catalogue_cellules"] = {
                        "active": True,
                        "energie_nominale_cible_pack_kwh": e_nom_cible_catalogue,
                        "tension_nominale_cible_pack_v": v_nom_cible_catalogue,
                        "nb_candidats": len(candidats),
                        "candidats": top_serialized,
                    }

                    if len(top) == 0:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "catalogue_cellules",
                            "Aucun candidat commercial n'a pu être pré-dimensionné avec les données actuellement extraites.",
                        )
                except Exception as e:
                    rapport["catalogue_cellules"] = {"active": True, "erreur": str(e), "candidats": []}
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "catalogue_cellules",
                        f"Échec de la collecte / du pré-dimensionnement catalogue: {e}",
                    )
        else:
            rapport["catalogue_cellules"] = {"active": False}

        # ------------------------------------------------------------
        # 11) Dimensionnement fin strict : Ns/Np, tension sous charge, pertes Joule
        # ------------------------------------------------------------
        if activer_dimensionnement_fin:
            e_nom_cible_fin = (
                _require_positive("energie_nominale_cible_pack_kwh", energie_nominale_cible_pack_kwh, strict=False)
                if energie_nominale_cible_pack_kwh is not None
                else E_batt_tot
            )

            P_cont_fin = puissance_pack_continue_kw if puissance_pack_continue_kw is not None else puissance_moyenne_kw
            P_pic_fin = puissance_pack_pic_kw if puissance_pack_pic_kw is not None else puissance_pic_kw

            if cellule_pack is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "dimensionnement_fin",
                    "Le dimensionnement fin strict exige une `CellulePack` complète (points OCV/résistance/courants fournis explicitement).",
                )
                rapport["dimensionnement_fin"] = {"active": True, "erreur": "cellule_pack manquante"}
            elif e_nom_cible_fin is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "dimensionnement_fin",
                    "Calculable si energie_nominale_cible_pack_kwh est fournie, ou si capacite_totale_kwh a été déterminée.",
                )
                rapport["dimensionnement_fin"] = {"active": True, "erreur": "energie_nominale_cible_pack_kwh manquante"}
            elif tension_bus_min_v is None or tension_bus_max_v is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "dimensionnement_fin",
                    "Calculable si tension_bus_min_v et tension_bus_max_v sont fournis explicitement.",
                )
                rapport["dimensionnement_fin"] = {"active": True, "erreur": "tension_bus_min_v/tension_bus_max_v manquantes"}
            elif P_cont_fin is None or P_pic_fin is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "dimensionnement_fin",
                    "Calculable si puissance continue et puissance de pic pack sont fournies (directement ou via puissance_moyenne_kw/puissance_pic_kw).",
                )
                rapport["dimensionnement_fin"] = {"active": True, "erreur": "puissances pack manquantes"}
            else:
                try:
                    contraintes = ContraintesPack(
                        energie_nominale_cible_kwh=float(e_nom_cible_fin),
                        tension_bus_min_v=_require_positive("tension_bus_min_v", tension_bus_min_v, strict=True),
                        tension_bus_max_v=_require_positive("tension_bus_max_v", tension_bus_max_v, strict=True),
                        puissance_continue_kw=_require_positive("puissance_continue_pack_kw", P_cont_fin, strict=False),
                        puissance_pic_kw=_require_positive("puissance_pic_pack_kw", P_pic_fin, strict=False),
                        tension_nominale_cible_v=(
                            _require_positive("tension_nominale_cible_pack_v", tension_nominale_cible_pack_v, strict=True)
                            if tension_nominale_cible_pack_v is not None
                            else (
                                _require_positive("tension_nominale_v", self.tension_nominale_v, strict=True)
                                if self.tension_nominale_v is not None
                                else None
                            )
                        ),
                        duree_regime_continu_s=None,
                        duree_pic_s=duree_pic_s if duree_pic_s is None else _require_positive("duree_pic_s", duree_pic_s, strict=True),
                    )

                    dim = dimensionner_pack_cellules(
                        cellule=cellule_pack,
                        contraintes=contraintes,
                        pertes_passives=pertes_passives_pack,
                        modele_thermique=modele_thermique_pack,
                        nb_series_min=nb_series_min_dim,
                        nb_series_max=nb_series_max_dim,
                    )
                    dim_dict = dim.en_dict()
                    rapport["dimensionnement_fin"] = {
                        "active": True,
                        "rapport": dim_dict,
                    }

                    # Si le dimensionnement fin a réussi, on peut enrichir le résumé synthétique.
                    rapport["dimensionnement"]["capacite_totale_kwh_dimensionnement_fin"] = dim_dict.get("energie_nominale_pack_kwh")
                    rapport["dimensionnement"]["masse_batterie_kg_dimensionnement_fin"] = dim_dict.get("masse_totale_pack_kg")
                except Exception as e:
                    rapport["dimensionnement_fin"] = {"active": True, "erreur": str(e)}
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "dimensionnement_fin",
                        f"Échec du dimensionnement fin strict: {e}",
                    )
        else:
            rapport["dimensionnement_fin"] = {"active": False}

        # ------------------------------------------------------------
        # 12) Inconnues réellement impossibles sans techno/mesures
        # ------------------------------------------------------------
        _push_inconnue(
            rapport,
            "impossibles",
            "vieillissement / durée de vie",
            "Impossible sans modèle de vieillissement (cycles, DoD, C-rate, température, chimie) + données fabricant.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "courbe CC/CV et taper fin de charge",
            "Le calcul de temps de charge reste un modèle à puissance constante.",
        )

        # Le thermique pack est impossible au niveau global si on n'a pas de modèle fin.
        if modele_thermique_pack is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "thermique pack (refroidissement)",
                "Impossible sans architecture pack, résistances internes, modèle thermique, conditions ambiantes et profils charge/décharge.",
            )

        pieces_rapport: Dict[str, Any] = {}
        pack_piece = self.piece_pack or PackBatterie(batterie=self, rapport_batterie=rapport)
        busbars_piece = self.piece_busbars or BusbarsBatterie(batterie=self, rapport_batterie=rapport)
        boitier_piece = self.piece_boitier or BoitierBatterie(batterie=self, rapport_batterie=rapport)
        bms_piece = self.piece_bms or BMSBatterie(batterie=self, rapport_batterie=rapport)
        tms_piece = self.piece_tms or TMSBatterie(batterie=self, rapport_batterie=rapport)
        for nom, piece in (
            ("pack", pack_piece),
            ("busbars", busbars_piece),
            ("boitier", boitier_piece),
            ("bms", bms_piece),
            ("tms", tms_piece),
        ):
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces_rapport[nom] = piece.analyser()
                except Exception as exc:
                    pieces_rapport[nom] = {"erreur": str(exc)}
        if pieces_rapport:
            rapport["pieces"] = pieces_rapport

        _dedup_inconnues(rapport)
        return rapport

    # ------------------------------------------------------------
    # Analyse de l'intégration avec les autres composants (Alternateur, Moteur)
    # ------------------------------------------------------------
    def analyser_recharge_systeme(
        self,
        *,
        rapport_alternateur: Optional[Dict[str, Any]] = None,
        rapport_moteur_elec: Optional[Dict[str, Any]] = None,
        soc_actuel: float = 0.5,
        temperature_pack_c: float = 25.0
    ) -> Dict[str, Any]:
        """
        Analyse la recharge en tenant compte de la puissance disponible de l'alternateur
        et de la consommation éventuelle du moteur électrique.
        
        Objectif : Recharger le plus vite possible sans dégrader les cellules.
        """
        rep: Dict[str, Any] = {
            "flux_energie_kw": {},
            "securite_cellules": {},
            "optimisation": {},
            "inconnues": {"impossibles": [], "partielles": []}
        }
        
        # 1. Puissance disponible (Source)
        P_alternateur = 0.0
        if rapport_alternateur:
            # On cherche la puissance de sortie du bus DC de l'alternateur
            P_alternateur = rapport_alternateur.get("bus_dc", {}).get("puissance_bus_dc_W", 0.0) / 1000.0
        
        # 2. Consommation moteur (Charge)
        P_moteur = 0.0
        if rapport_moteur_elec:
            P_moteur = rapport_moteur_elec.get("electrique", {}).get("puissance_absorbee_kw", 0.0)
            
        P_dispo_recharge = P_alternateur - P_moteur
        rep["flux_energie_kw"]["alternateur_prod"] = P_alternateur
        rep["flux_energie_kw"]["moteur_conso"] = P_moteur
        rep["flux_energie_kw"]["bilan_disponible"] = P_dispo_recharge
        
        # 3. Calcul de la charge optimale sécurisée via le BMS
        # On simule un appel au BMS interne
        if self.piece_bms:
            # On configure temporairement le BMS pour l'état actuel
            self.piece_bms.soc = soc_actuel
            self.piece_bms.temperature_cellules_c = temperature_pack_c
            bms_rep = self.piece_bms.analyser()
            
            P_max_safe = bms_rep.get("resultats", {}).get("puissance_charge_max_securisee_kw")
            rep["securite_cellules"]["puissance_charge_max_autorisee_kw"] = P_max_safe
            
            if P_max_safe is not None:
                P_recharge_finale = min(P_dispo_recharge, P_max_safe)
                rep["optimisation"]["puissance_charge_reelle_kw"] = max(0.0, P_recharge_finale)
                rep["optimisation"]["limitee_par"] = "BMS (Cellules)" if P_max_safe < P_dispo_recharge else "Source (Alternateur)"
                
                if P_dispo_recharge < 0:
                    rep["optimisation"]["etat"] = "Decharge (Moteur > Alternateur)"
                else:
                    rep["optimisation"]["etat"] = "Recharge en cours"
        else:
            rep["inconnues"]["impossibles"].append({"nom": "optimisation_recharge", "reason": "BMS non configure pour l'analyse dynamique."})
            
        return rep
