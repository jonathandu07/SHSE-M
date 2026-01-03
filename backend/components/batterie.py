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


# ============================================================
# Helpers (robustesse + inconnues)
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: Any, *, strict: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


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


def _kwh_from_kw_h(p_kw: float, t_h: float) -> float:
    # énergie (kWh) = puissance (kW) * temps (h)
    return float(p_kw) * float(t_h)


def _conso_kwh_km_from_p_v(puissance_moyenne_kw: float, vitesse_moyenne_kmh: float) -> float:
    # conso (kWh/km) = P(kW) / v(km/h)
    v = _require_positive("vitesse_moyenne_kmh", vitesse_moyenne_kmh, strict=True)
    p = _require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False)
    if p == 0.0:
        return 0.0
    return p / v


def _ah_from_kwh_and_v(capacite_kwh: float, tension_v: float) -> float:
    # Ah = Wh / V = (kWh*1000) / V
    E_wh = _require_positive("capacite_kwh", capacite_kwh, strict=False) * 1000.0
    V = _require_positive("tension_v", tension_v, strict=True)
    if E_wh == 0.0:
        return 0.0
    return E_wh / V


def _courant_a_from_kw_and_v(puissance_kw: float, tension_v: float) -> float:
    # I = P/V ; P(kW)->W
    P_w = _require_positive("puissance_kw", puissance_kw, strict=False) * 1000.0
    V = _require_positive("tension_v", tension_v, strict=True)
    if P_w == 0.0:
        return 0.0
    return P_w / V


def _crate_from_kw_and_kwh(puissance_kw: float, capacite_kwh: float) -> float:
    # C-rate approx = P(kW)/E(kWh) (à tension quasi constante)
    E = _require_positive("capacite_kwh", capacite_kwh, strict=False)
    P = _require_positive("puissance_kw", puissance_kw, strict=False)
    if E == 0.0:
        return 0.0
    return P / E


# ============================================================
# Composant Batterie
# ============================================================

@dataclass(frozen=True)
class Batterie:
    """
    Dimensionnement "pack batterie" avec un maximum de calculs,
    et des inconnues uniquement quand elles dépendent de choix techno/données externes.

    Les sorties restent du "pré-dimensionnement" : pas de modèle CC/CV complet, pas de thermique pack,
    pas de vieillissement électrochimique détaillé.
    """

    # Fenêtre SOC utilisable (ex: 0.6, 0.8)
    fenetre_soc: float = 0.8

    # Densité énergétique (kWh/kg) au niveau pack (pas cellule)
    densite_energetique_kwh_kg: Optional[float] = None

    # Charge (si tu connais ton chargeur / alternateur)
    rendement_charge: float = 0.90
    puissance_charge_kw: Optional[float] = None

    # Électrique pack (optionnel, utile pour I, Ah, C-rate)
    tension_nominale_v: Optional[float] = None
    tension_charge_v: Optional[float] = None  # tension approx côté pack pendant charge (si connue)

    clamp_non_negative: bool = True

    def analyser_dimensionnement(
        self,
        *,
        # 1) Critère autonomie (trajet)
        distance_km: Optional[float] = None,
        conso_kwh_km: Optional[float] = None,

        # 2) Alternative : conso dérivée de puissance+vitesse moyenne
        puissance_moyenne_kw: Optional[float] = None,
        vitesse_moyenne_kmh: Optional[float] = None,

        # 3) Critère recharge (énergie dimensionnée par temps cible)
        temps_charge_cible_h: Optional[float] = None,

        # 4) Critère pic (tampon)
        puissance_pic_kw: Optional[float] = None,
        duree_pic_s: Optional[float] = None,

        # 5) Si tu as déjà une énergie utile imposée
        energie_utile_imposee_kwh: Optional[float] = None,

        # 6) Si tu veux une charge "à la demande" : calcul de P requise si non fournie
        #    (utile si tu donnes temps_charge_cible_h mais pas puissance_charge_kw)
        calculer_puissance_charge_requise: bool = True,
    ) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "energies_utiles": {},
            "dimensionnement": {},
            "charge": {},
            "electrique": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # Entrées
        # ------------------------------------------------------------
        rapport["entrees"] = {
            "fenetre_soc": self.fenetre_soc,
            "densite_energetique_kwh_kg": self.densite_energetique_kwh_kg,
            "rendement_charge": self.rendement_charge,
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
            "calculer_puissance_charge_requise": calculer_puissance_charge_requise,
        }

        # ------------------------------------------------------------
        # 1) Énergie utile trajets (directe ou dérivée)
        # ------------------------------------------------------------
        E_trajet: Optional[float] = None
        conso_derivee: Optional[float] = None

        if distance_km is not None:
            d = _require_positive("distance_km", distance_km, strict=False)
            if conso_kwh_km is not None:
                c = _require_positive("conso_kwh_km", conso_kwh_km, strict=False)
                E_trajet = float(calcul_energie_utile_trajet(d, c))
            else:
                # Tentative : déduire conso depuis puissance+vitesse
                if puissance_moyenne_kw is not None and vitesse_moyenne_kmh is not None:
                    conso_derivee = _conso_kwh_km_from_p_v(puissance_moyenne_kw, vitesse_moyenne_kmh)
                    E_trajet = float(calcul_energie_utile_trajet(d, conso_derivee))
                    rapport["notes_modele"].append("conso_kwh_km déduite via P_moy/v_moy (approx).")
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "énergie utile trajet",
                        "Calculable si conso_kwh_km est fournie, ou si (puissance_moyenne_kw et vitesse_moyenne_kmh) sont fournis.",
                    )

        rapport["energies_utiles"]["conso_kwh_km_derivee"] = conso_derivee
        rapport["energies_utiles"]["E_trajet_kwh"] = E_trajet

        # ------------------------------------------------------------
        # 2) Énergie utile contrainte de recharge (si temps cible)
        #    E_u = eta * P * t
        # ------------------------------------------------------------
        E_charge_cible: Optional[float] = None
        P_charge_requise: Optional[float] = None

        if temps_charge_cible_h is not None:
            t = _require_positive("temps_charge_cible_h", temps_charge_cible_h, strict=False)
            eta = _require_positive("rendement_charge", self.rendement_charge, strict=True)
            if eta > 1.0:
                raise ValueError("rendement_charge doit être <= 1.0")

            if self.puissance_charge_kw is not None:
                Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False)
                E_charge_cible = float(calcul_energie_utile_cible(t, Pchg, eta))
            else:
                # si l'utilisateur impose déjà E_u (trajet ou imposée), on peut inverser et obtenir P requise
                if calculer_puissance_charge_requise:
                    # on attend d'avoir E_u_final (plus bas), mais on peut déjà calculer une requête "symbolique"
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "puissance de charge requise",
                        "Calculable si une énergie utile à recharger (E_u_final) est déterminée et si temps_charge_cible_h est fourni.",
                    )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "énergie utile via contrainte de charge",
                        "Calculable si puissance_charge_kw est fournie (ou activer calculer_puissance_charge_requise avec E_u_final).",
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
                "énergie utile pic",
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
        # 5) Choix de l’énergie utile finale (max des contraintes)
        # ------------------------------------------------------------
        energies_candidates: List[float] = []
        for v in (E_trajet, E_charge_cible, E_pic, E_imposee):
            if v is not None:
                energies_candidates.append(float(v))

        if len(energies_candidates) > 0:
            E_u_final = float(choisir_energie_utile_finale(*energies_candidates))
        else:
            E_u_final = None
            _push_inconnue(
                rapport,
                "impossibles",
                "énergie utile finale",
                "Impossible sans au moins un critère (trajet, charge cible, pic, ou énergie imposée).",
            )

        rapport["dimensionnement"]["E_utile_finale_kwh"] = E_u_final

        # ------------------------------------------------------------
        # 6) Dimensionnement capacité totale + masse pack
        # ------------------------------------------------------------
        E_batt_tot: Optional[float] = None
        m_batt: Optional[float] = None

        if E_u_final is not None:
            w = _require_positive("fenetre_soc", self.fenetre_soc, strict=True)
            if w > 1.0:
                raise ValueError("fenetre_soc doit être <= 1.0")

            E_batt_tot = float(calcul_capacite_totale_batterie(E_u_final, w))

            if self.densite_energetique_kwh_kg is not None:
                rho = _require_positive("densite_energetique_kwh_kg", self.densite_energetique_kwh_kg, strict=True)
                m_batt = float(calcul_poids_batterie(E_batt_tot, rho))
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "masse batterie",
                    "Calculable si densite_energetique_kwh_kg (au niveau pack) est fournie.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "capacité totale batterie",
                "Calculable si l'énergie utile finale (E_u_final) est déterminée.",
            )

        rapport["dimensionnement"]["capacite_totale_kwh"] = E_batt_tot
        rapport["dimensionnement"]["masse_batterie_kg"] = m_batt

        # ------------------------------------------------------------
        # 7) Charge : temps de charge, puissance requise, courant estimé
        # ------------------------------------------------------------
        t_charge: Optional[float] = None
        P_eff_kw: Optional[float] = None

        if E_u_final is not None:
            eta = _require_positive("rendement_charge", self.rendement_charge, strict=True)
            if eta > 1.0:
                raise ValueError("rendement_charge doit être <= 1.0")

            # 7.1 Temps de charge si Pcharge connue
            if self.puissance_charge_kw is not None:
                Pchg = _require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=True)
                t_charge = float(calcul_temps_charge(E_u_final, Pchg, eta))
                P_eff_kw = Pchg * eta
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "temps de charge",
                    "Calculable si puissance_charge_kw est fournie (et rendement_charge).",
                )

            # 7.2 Puissance de charge requise si temps cible fourni (inversion)
            if temps_charge_cible_h is not None and calculer_puissance_charge_requise:
                t = _require_positive("temps_charge_cible_h", temps_charge_cible_h, strict=True)
                # E_u = eta * P * t => P = E_u / (eta * t)
                if eta * t > 0.0:
                    P_charge_requise = E_u_final / (eta * t)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "charge",
                "Calculable si E_u_final est déterminée et si (Pcharge ou temps cible) est fourni.",
            )

        rapport["charge"]["temps_charge_h"] = t_charge
        rapport["charge"]["puissance_charge_requise_kw"] = P_charge_requise
        rapport["charge"]["puissance_effective_stockee_kw"] = P_eff_kw

        # Courant de charge approximatif si tension charge connue
        I_charge_a: Optional[float] = None
        if P_eff_kw is not None:
            Vchg = self.tension_charge_v or self.tension_nominale_v
            if Vchg is not None:
                I_charge_a = _courant_a_from_kw_and_v(P_eff_kw, Vchg)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "courant de charge",
                    "Calculable si tension_charge_v (ou tension_nominale_v) est fournie.",
                )
        rapport["charge"]["courant_charge_A"] = I_charge_a

        # ------------------------------------------------------------
        # 8) Électrique pack : Ah, courants, C-rates (si tension dispo)
        # ------------------------------------------------------------
        capacite_ah: Optional[float] = None
        I_decharge_a: Optional[float] = None
        C_decharge: Optional[float] = None
        C_charge: Optional[float] = None

        if E_batt_tot is not None and self.tension_nominale_v is not None:
            capacite_ah = _ah_from_kwh_and_v(E_batt_tot, self.tension_nominale_v)
        elif E_batt_tot is not None and self.tension_nominale_v is None:
            _push_inconnue(
                rapport,
                "partielles",
                "capacité Ah",
                "Calculable si tension_nominale_v est fournie (Ah = kWh*1000 / V).",
            )

        # Décharge : courant et C-rate depuis puissance moyenne
        if puissance_moyenne_kw is not None and E_batt_tot is not None:
            if self.tension_nominale_v is not None:
                I_decharge_a = _courant_a_from_kw_and_v(_require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False), self.tension_nominale_v)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "courant de décharge",
                    "Calculable si tension_nominale_v est fournie.",
                )
            C_decharge = _crate_from_kw_and_kwh(_require_positive("puissance_moyenne_kw", puissance_moyenne_kw, strict=False), E_batt_tot)
        elif puissance_moyenne_kw is not None and E_batt_tot is None:
            _push_inconnue(
                rapport,
                "partielles",
                "C-rate décharge",
                "Calculable si capacite_totale_kwh est déterminée.",
            )

        # Charge : C-rate charge depuis puissance charge
        if self.puissance_charge_kw is not None and E_batt_tot is not None:
            C_charge = _crate_from_kw_and_kwh(_require_positive("puissance_charge_kw", self.puissance_charge_kw, strict=False), E_batt_tot)
        elif self.puissance_charge_kw is not None and E_batt_tot is None:
            _push_inconnue(
                rapport,
                "partielles",
                "C-rate charge",
                "Calculable si capacite_totale_kwh est déterminée.",
            )

        rapport["electrique"]["capacite_Ah_estimee"] = capacite_ah
        rapport["electrique"]["courant_decharge_A_estime"] = I_decharge_a
        rapport["electrique"]["C_rate_decharge_estime"] = C_decharge
        rapport["electrique"]["C_rate_charge_estime"] = C_charge

        # ------------------------------------------------------------
        # 9) Inconnues réellement impossibles (sans techno/mesures)
        # ------------------------------------------------------------
        _push_inconnue(
            rapport,
            "impossibles",
            "vieillissement / durée de vie",
            "Impossible sans modèle de vieillissement (cycles, DoD, C-rate, température, chimie) et données fabricant.",
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
