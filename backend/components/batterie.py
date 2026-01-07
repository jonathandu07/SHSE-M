# backend/components/batterie.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math


# ============================================================
# Imports des modules batterie (robustes)
# ============================================================

# calcul_dimensionnement_batterie.py
try:
    from backend.modules.batterie.calcul_dimensionnement_batterie import (
        calcul_capacite_totale_batterie,
        calcul_poids_batterie,
    )
except Exception:
    from backend.modules.batterie.calcul_dimensionnement_batterie import (  # type: ignore
        calcul_capacite_totale_batterie,
        calcul_poids_batterie,
    )

# calcul_energie_utile.py
try:
    from backend.modules.batterie.calcul_energie_utile import (
        calcul_energie_utile_cible,
        calcul_energie_utile_trajet,
        calcul_energie_utile_pic,
        choisir_energie_utile_finale,
    )
except Exception:
    from backend.modules.batterie.calcul_energie_utile import (  # type: ignore
        calcul_energie_utile_cible,
        calcul_energie_utile_trajet,
        calcul_energie_utile_pic,
        choisir_energie_utile_finale,
    )

# calcul_temps_charge.py
try:
    from backend.modules.batterie.calcul_temps_charge import calcul_temps_charge
except Exception:
    from backend.modules.batterie.calcul_temps_charge import calcul_temps_charge  # type: ignore

# calcul_electrique_pack.py
try:
    from backend.modules.batterie.calcul_electrique_pack import (
        calcul_conso_kwh_km_depuis_puissance_vitesse,
        calcul_ah_depuis_kwh_tension,
        calcul_courant_depuis_kw_tension,
        calcul_c_rate_depuis_kw_kwh,
        calcul_puissance_effective_stockee,
        calcul_puissance_charge_requise,
    )
except Exception:
    from backend.modules.batterie.calcul_electrique_pack import (  # type: ignore
        calcul_conso_kwh_km_depuis_puissance_vitesse,
        calcul_ah_depuis_kwh_tension,
        calcul_courant_depuis_kw_tension,
        calcul_c_rate_depuis_kw_kwh,
        calcul_puissance_effective_stockee,
        calcul_puissance_charge_requise,
    )

# electrolyte_solide.py (NOUVEAU)
try:
    from backend.modules.batterie.electrolyte_solide import (
        ElectrolyteSolide,
        CelluleSolide,
        PackSolide,
        Options as OptionsElectrolyte,
        evaluer_electrolyte_solide,
        RapportElectrolyteSolide,
    )
except Exception:
    from backend.modules.batterie.electrolyte_solide import (  # type: ignore
        ElectrolyteSolide,
        CelluleSolide,
        PackSolide,
        Options as OptionsElectrolyte,
        evaluer_electrolyte_solide,
        RapportElectrolyteSolide,
    )


# ============================================================
# Helpers (robustesse + inconnues) — sans formules métier
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


def _require_ratio_0_1(name: str, x: Any) -> float:
    v = _require_positive(name, x, strict=True)
    if v > 1.0:
        raise ValueError(f"{name} doit être <= 1.0 (reçu: {v}).")
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


# ============================================================
# Config : Électrolyte solide (SSB)
# ============================================================

@dataclass(frozen=True)
class ConfigElectrolyteSolide:
    """
    Configuration minimale pour l'analyse "électrolyte solide" sans invention :
    - si un champ manque -> le module renvoie des inconnues.
    """
    # Électrolyte
    conductivite_ionique_s_m: Optional[float] = None
    epaisseur_m: Optional[float] = None
    resistance_interface_ohm: Optional[float] = None  # optionnel

    # Cellule
    surface_active_m2: Optional[float] = None
    tension_cell_v: Optional[float] = None
    capacite_cell_ah: Optional[float] = None
    courant_cell_max_a: Optional[float] = None  # optionnel

    # Pack
    nb_series: Optional[int] = None
    nb_parallele: Optional[int] = None

    # Optionnel : rendement chaîne (si la puissance passée n’est pas déjà "électrique pack")
    rendement_chaine: Optional[float] = None


# ============================================================
# Composant Batterie
# ============================================================

@dataclass(frozen=True)
class Batterie:
    """
    Dimensionnement "pack batterie" basé sur tes modules robustes.

    Règle :
        - on ne calcule que si les entrées nécessaires existent.
        - sinon : inconnue (partielle ou impossible) avec justification.
    """

    # Fenêtre SOC utilisable (0 < w <= 1)
    fenetre_soc: float = 0.8

    # Densité énergétique (kWh/kg) au niveau pack (pas cellule)
    densite_energetique_kwh_kg: Optional[float] = None

    # Charge (si tu connais ton chargeur / alternateur)
    rendement_charge: float = 0.90
    puissance_charge_kw: Optional[float] = None

    # Électrique pack (optionnel, utile pour I, Ah, C-rate)
    tension_nominale_v: Optional[float] = None
    tension_charge_v: Optional[float] = None  # tension approx côté pack pendant charge (si connue)

    def analyser_dimensionnement(
        self,
        *,
        # 1) Critère autonomie (trajet)
        distance_km: Optional[float] = None,
        conso_kwh_km: Optional[float] = None,

        # 2) Alternative : conso dérivée de puissance+vitesse moyenne (si dispo)
        puissance_moyenne_kw: Optional[float] = None,
        vitesse_moyenne_kmh: Optional[float] = None,

        # 3) Critère recharge (temps cible)
        temps_charge_cible_h: Optional[float] = None,

        # 4) Critère pic (tampon)
        puissance_pic_kw: Optional[float] = None,
        duree_pic_s: Optional[float] = None,

        # 5) Si tu as déjà une énergie utile imposée
        energie_utile_imposee_kwh: Optional[float] = None,

        # 6) Agrégation des contraintes d'énergie utile :
        #    - "max" : même logique que choisir_energie_utile_finale (module)
        #    - "somme" : additionne les contraintes disponibles (utile si tu veux cumuler autonomie + tampon pic)
        mode_aggregation_energie: str = "max",

        # 7) Si temps cible fourni mais pas puissance_charge_kw : tenter de calculer la puissance requise
        calculer_puissance_charge_requise: bool = True,

        # 8bis) Électrolyte solide (SSB)
        ssb: Optional[ConfigElectrolyteSolide] = None,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "energies_utiles": {},
            "dimensionnement": {},
            "charge": {},
            "electrique": {},
            "electrolyte_solide": {},
            "hypotheses": [],
            "unites": {},
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # ------------------------------------------------------------
        # Validations "structurelles" (pas de calcul métier ici)
        # ------------------------------------------------------------
        w = _require_ratio_0_1("fenetre_soc", self.fenetre_soc)
        eta = _require_ratio_0_1("rendement_charge", self.rendement_charge)

        rapport["entrees"] = {
            "fenetre_soc": w,
            "densite_energetique_kwh_kg": self.densite_energetique_kwh_kg,
            "rendement_charge": eta,
            "puissance_charge_kw": self.puissance_charge_kw,
            "tension_nominale_v": self.tension_nominale_v,
            "tension_charge_v": self.tension_charge_v,
            "distance_km": distance_km,
            "conso_kwh_km": conso_kwh_k_toggle := conso_kwh_km,  # kept for debug; value identical
            "puissance_moyenne_kw": puissance_moyenne_kw,
            "vitesse_moyenne_kmh": vitesse_moyenne_kmh,
            "temps_charge_cible_h": temps_charge_cible_h,
            "puissance_pic_kw": puissance_pic_kw,
            "duree_pic_s": duree_pic_s,
            "energie_utile_imposee_kwh": energie_utile_imposee_kwh,
            "mode_aggregation_energie": mode_aggregation_energie,
            "calculer_puissance_charge_requise": calculer_puissance_charge_requise,
            "ssb": ssb,
        }
        # NOTE: the walrus above is safe but unnecessary; if you prefer, delete it and keep only conso_kwh_km.

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
            "R_*": "ohm",
            "ASR_*": "ohm·m²",
            "pertes_joule_*": "W",
        }

        # ------------------------------------------------------------
        # 1) Énergie utile trajet (directe ou déduite via module)
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
                        "conso_kwh_km dérivée via P_moy/v_moy (nécessite que puissance_moyenne_kw soit cohérente avec la phase et la chaîne considérées)."
                    )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "E_trajet_kwh",
                        "Calculable si (conso_kwh_km) est fournie, ou si (puissance_moyenne_kw et vitesse_moyenne_kmh) sont fournis.",
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
                E_charge_cible = float(calcul_energie_utile_cible(t, Pchg, eta))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "E_charge_cible_kwh",
                    "Calculable si puissance_charge_kw est fournie (ou via puissance requise si E_utile_finale est déterminée).",
                )

        rapport["energies_utiles"]["E_charge_cible_kwh"] = E_charge_cible

        # ------------------------------------------------------------
        # 3) Énergie utile tampon pic
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
        energies_candidates: List[float] = []
        for v in (E_trajet, E_charge_cible, E_pic, E_imposee):
            if v is not None:
                energies_candidates.append(float(v))

        E_u_final: Optional[float] = None
        if energies_candidates:
            if mode_aggregation_energie == "max":
                E_u_final = float(choisir_energie_utile_finale(*energies_candidates))
            elif mode_aggregation_energie == "somme":
                E_u_final = float(sum(energies_candidates))
                rapport["hypotheses"].append(
                    "E_utile_finale obtenue par SOMME des contraintes disponibles (choix de dimensionnement)."
                )
            else:
                raise ValueError("mode_aggregation_energie doit être 'max' ou 'somme'.")
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
                "Calculable si l'énergie utile finale (E_utile_finale_kwh) est déterminée.",
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
            # Temps de charge si puissance de charge connue
            if self.puissance_charge_kw is not None:
                Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=True)
                t_charge = float(calcul_temps_charge(E_u_final, Pchg, eta))
                P_eff_kw = float(calcul_puissance_effective_stockee(Pchg, eta))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "temps_charge_h",
                    "Calculable si puissance_charge_kw est fournie (et rendement_charge).",
                )

            # Puissance requise si temps cible fourni
            if temps_charge_cible_h is not None and calculer_puissance_charge_requise:
                t = _require_positive("temps_charge_cible_h", temps_charge_cible_h, strict=True)
                P_charge_requise_kw = float(calcul_puissance_charge_requise(E_u_final, t, eta))
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "charge",
                "Calculable si E_utile_finale_kwh est déterminée et si (puissance_charge_kw ou temps_charge_cible_h) est fourni.",
            )

        # Courant de charge si tension connue (tension de charge ou nominale)
        if P_eff_kw is not None:
            Vchg = self.tension_charge_v or self.tension_nominale_v
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

        # Décharge : courant et C-rate depuis puissance moyenne
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

        # Charge : C-rate charge depuis puissance charge
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
        # 8bis) Électrolyte solide (SSB) : calculs ohmiques si données disponibles
        # ------------------------------------------------------------
        rapport["electrolyte_solide"] = {
            "entrees_ssb": None,
            "rapport_ssb": None,
            "inconnues_ssb": None,
        }

        if ssb is not None:
            rapport["electrolyte_solide"]["entrees_ssb"] = {
                "conductivite_ionique_s_m": ssb.conductivite_ionique_s_m,
                "epaisseur_m": ssb.epaisseur_m,
                "resistance_interface_ohm": ssb.resistance_interface_ohm,
                "surface_active_m2": ssb.surface_active_m2,
                "tension_cell_v": ssb.tension_cell_v,
                "capacite_cell_ah": ssb.capacite_cell_ah,
                "courant_cell_max_a": ssb.courant_cell_max_a,
                "nb_series": ssb.nb_series,
                "nb_parallele": ssb.nb_parallele,
                "rendement_chaine": ssb.rendement_chaine,
            }

            # Puissance continue "pour laquelle on évalue les pertes".
            # On n'invente pas : il faut une source.
            P_cont_kw: Optional[float] = None
            if puissance_moyenne_kw is not None:
                P_cont_kw = _require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
            elif self.puissance_charge_kw is not None:
                P_cont_kw = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False)
                rapport["hypotheses"].append(
                    "SSB: puissance_continue_kw prise = puissance_charge_kw (puissance chargeur), "
                    "ce qui ne correspond pas nécessairement à la puissance réellement stockée."
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "SSB.puissance_continue_kw",
                    "Calculable si puissance_moyenne_kw (décharge) ou puissance_charge_kw (charge) est fournie.",
                )

            P_pic_kw: Optional[float] = None
            if puissance_pic_kw is not None:
                P_pic_kw = _require_positive("puissance_pic_kw", puissance_pic_kw, strict=False)

            elec = ElectrolyteSolide(
                conductivite_ionique_s_m=ssb.conductivite_ionique_s_m,
                epaisseur_m=ssb.epaisseur_m,
                resistance_interface_ohm=ssb.resistance_interface_ohm,
            )
            cell = CelluleSolide(
                surface_active_m2=ssb.surface_active_m2,
                tension_nominale_v=ssb.tension_cell_v,
                capacite_ah=ssb.capacite_cell_ah,
                courant_max_a=ssb.courant_cell_max_a,
            )
            pack_ssb = PackSolide(
                nb_series=ssb.nb_series,
                nb_parallele=ssb.nb_parallele,
                puissance_continue_kw=P_cont_kw,
                puissance_pic_kw=P_pic_kw,
                rendement_chaine=ssb.rendement_chaine,
            )

            rep_ssb: RapportElectrolyteSolide = evaluer_electrolyte_solide(
                elec, cell, pack_ssb, OptionsElectrolyte(strict=False)
            )
            rapport["electrolyte_solide"]["rapport_ssb"] = rep_ssb
            rapport["electrolyte_solide"]["inconnues_ssb"] = rep_ssb.inconnues

        # ------------------------------------------------------------
        # 9) Inconnues réellement impossibles sans techno/mesures
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
            "thermique pack (refroidissement)",
            "Impossible sans architecture pack, résistances internes, conditions ambiantes, profils charge/décharge.",
        )
        _push_inconnue(
            rapport,
            "impossibles",
            "courbe CC/CV et taper fin de charge",
            "Le calcul de temps de charge est à puissance constante (modèle simple).",
        )

        _dedup_inconnues(rapport)
        return rapport
