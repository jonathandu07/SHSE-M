# backend/components/moteur_thermique/pieces/roulement_aiguille_arbre.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Literal

from backend.modules.systeme.dossier_definition import ajouter_dossier_definition_solidworks
import math


# =============================================================================
# Utilitaires (validation + extraction robuste)
# =============================================================================


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))



def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)



def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v



def _get(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        for n in names:
            if n in obj:
                return obj.get(n)
        return None
    for n in names:
        if hasattr(obj, n):
            try:
                return getattr(obj, n)
            except Exception:
                pass
    return None



def _dig(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur



def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    """
    Tente .analyser(strict=False), puis .calculer(), puis .analyser().
    """
    if obj is None:
        return None

    for name in ("analyser", "calculer"):
        fn = getattr(obj, name, None)
        if callable(fn):
            try:
                if name == "analyser":
                    out = fn(strict=False)
                else:
                    out = fn()
                return out if isinstance(out, dict) else None
            except TypeError:
                try:
                    out = fn()
                    return out if isinstance(out, dict) else None
                except Exception:
                    continue
            except Exception:
                continue
    return None



def _push_inconnue(rapport: Dict[str, Any], kind: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(kind, []).append({"nom": nom, "raison": raison})



def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    for k in ("impossibles", "partielles"):
        seen: set[tuple[str, str]] = set()
        out: List[dict] = []
        for it in list(rapport.get("inconnues", {}).get(k, []) or []):
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        rapport.setdefault("inconnues", {})[k] = out


# =============================================================================
# Formules roulements (standard ISO "générique" - sans données constructeur)
# =============================================================================


def _L10_rev_from_C_P(C_N: float, P_N: float, *, p: float) -> float:
    """
    Durée de vie nominale L10 en nombre de tours.
    L10 (10^6 tours) = (C/P)^p  => L10_rev = 1e6 * (C/P)^p
    """
    C = _req_pos("C_N", C_N, strictly=True)
    P = _req_pos("P_N", P_N, strictly=True)
    return 1e6 * (C / P) ** p



def _L10_h_from_C_P(C_N: float, P_N: float, n_rpm: float, *, p: float) -> float:
    """
    L10h = L10_rev / (60*n)
    """
    n = _req_pos("n_rpm", n_rpm, strictly=True)
    L10_rev = _L10_rev_from_C_P(C_N, P_N, p=p)
    return L10_rev / (60.0 * n)



def _C_required_from_P_L10h(P_N: float, n_rpm: float, L10_h: float, *, p: float) -> float:
    """
    Inversion de L10h pour obtenir C requis.
    L10_rev = 60*n*L10h
    L10_rev = 1e6*(C/P)^p => C = P*(L10_rev/1e6)^(1/p)
    """
    P = _req_pos("P_N", P_N, strictly=True)
    n = _req_pos("n_rpm", n_rpm, strictly=True)
    Lh = _req_pos("L10_h", L10_h, strictly=True)
    Lrev = 60.0 * n * Lh
    return P * (Lrev / 1e6) ** (1.0 / p)



def _force_tangentielle_depuis_couple(T_Nm: float, r_m: float) -> float:
    """
    Force tangente équivalente au rayon r : F = T/r
    (utile comme borne calculable si T et r sont connus)
    """
    T = _req_finite("couple_max_Nm", T_Nm)
    r = _req_pos("rayon_manivelle_m", r_m, strictly=True)
    return abs(T) / r if r > 0 else float("nan")



def _dmin_torsion_vonmises(T_Nm: float, Re_pa: float, FS: float) -> float:
    """
    Torsion pure, critère von Mises :
    τ = 16T/(π d^3)
    σ_eq = sqrt(3)*τ <= Re/FS
    """
    T = _req_finite("couple_max_Nm", T_Nm)
    Re = _req_pos("limite_elastique_pa", Re_pa, strictly=True)
    FS = _req_pos("facteur_securite", FS, strictly=True)
    tau_adm = Re / (FS * math.sqrt(3.0))
    if tau_adm <= 0:
        raise ValueError("tau_adm <= 0")
    return (16.0 * abs(T) / (math.pi * tau_adm)) ** (1.0 / 3.0)



def _charge_resultante(Fr_N: float, Fa_N: float) -> float:
    Fr = _req_pos("Fr_N", Fr_N, strictly=False)
    Fa = _req_pos("Fa_N", Fa_N, strictly=False)
    return math.hypot(Fr, Fa)



def _charge_equivalente_cycle(points: List[float], weights: List[float], *, p: float) -> Optional[float]:
    if not points or not weights or len(points) != len(weights):
        return None
    sw = 0.0
    acc = 0.0
    for x, w in zip(points, weights):
        if not _is_finite(x) or not _is_finite(w):
            return None
        xv = abs(float(x))
        wv = float(w)
        if wv < 0.0:
            return None
        acc += wv * (xv ** p)
        sw += wv
    if sw <= 0.0:
        return None
    return (acc / sw) ** (1.0 / p)



def _mean(xs: List[float], ws: List[float]) -> Optional[float]:
    if not xs or not ws or len(xs) != len(ws):
        return None
    sw = sum(float(w) for w in ws)
    if sw <= 0.0:
        return None
    return sum(float(x) * float(w) for x, w in zip(xs, ws)) / sw



def _amplitude_from_extrema(xmin: float, xmax: float) -> float:
    return 0.5 * (float(xmax) - float(xmin))



def _mean_from_extrema(xmin: float, xmax: float) -> float:
    return 0.5 * (float(xmax) + float(xmin))



def _sommerfeld_number(eta_Pa_s: float, rpm: float, d_m: float, L_m: float, jeu_radial_m: float, p_proj_pa: float) -> float:
    eta = _req_pos("eta_Pa_s", eta_Pa_s)
    n = _req_pos("rpm", rpm, strictly=False) / 60.0
    d = _req_pos("d_m", d_m)
    L = _req_pos("L_m", L_m)
    c = _req_pos("jeu_radial_m", jeu_radial_m)
    p = _req_pos("p_proj_pa", p_proj_pa)
    r = 0.5 * d
    return (eta * n * (r / c) ** 2 / p) * (L / d)



def _hydrodynamic_shear_torque(eta_Pa_s: float, rpm: float, d_m: float, L_m: float, jeu_radial_m: float) -> float:
    """
    Modèle concentrique Couette simplifié pour palier lisse.
    T = 2π η ω L r^3 / c
    """
    eta = _req_pos("eta_Pa_s", eta_Pa_s)
    n = _req_pos("rpm", rpm, strictly=False)
    d = _req_pos("d_m", d_m)
    L = _req_pos("L_m", L_m)
    c = _req_pos("jeu_radial_m", jeu_radial_m)
    r = 0.5 * d
    omega = 2.0 * math.pi * n / 60.0
    return 2.0 * math.pi * eta * omega * L * (r ** 3) / c



def _lambda_ratio(h_min_m: float, rq1_m: float, rq2_m: float) -> float:
    h = _req_pos("h_min_m", h_min_m, strictly=False)
    rq1 = _req_pos("rq1_m", rq1_m, strictly=False)
    rq2 = _req_pos("rq2_m", rq2_m, strictly=False)
    denom = math.sqrt(rq1 * rq1 + rq2 * rq2)
    if denom <= 0.0:
        raise ValueError("La rugosité combinée doit être > 0 pour calculer lambda.")
    return h / denom


# =============================================================================
# Données d'entrée avancées
# =============================================================================


@dataclass
class ReferenceRoulementAiguille:
    """
    Données fournisseur/constructeur (si tu as déjà une référence en tête).
    Tu peux laisser None si tu n'as pas ces infos (le module ne les invente pas).
    """
    designation: Optional[str] = None

    d_interieur_m: Optional[float] = None   # alésage / arbre (ID)
    D_exterieur_m: Optional[float] = None   # logement (OD)
    B_largeur_m: Optional[float] = None     # largeur (B)

    C_dynamique_N: Optional[float] = None   # capacité dynamique (catalogue)
    C0_statique_N: Optional[float] = None   # capacité statique (catalogue)

    n_lim_rpm: Optional[float] = None       # vitesse limite catalogue (si fournie)
    rayon_appui_max_m: Optional[float] = None
    rugosite_arbre_max_Ra_m: Optional[float] = None
    rugosite_logement_max_Ra_m: Optional[float] = None
    faux_rond_max_m: Optional[float] = None
    coaxialite_max_m: Optional[float] = None


@dataclass
class PointChargeRoulement:
    angle_deg: float
    force_radiale_N: float
    force_axiale_N: float = 0.0
    poids: float = 1.0
    etiquette: Optional[str] = None


@dataclass
class CycleChargeRoulement:
    points: List[PointChargeRoulement] = field(default_factory=list)
    nom: Optional[str] = None


@dataclass
class FacteursVieRoulement:
    """
    Facteurs multiplicatifs explicites pour la vie ajustée.
    Aucune table ISO n'est inventée ici : les facteurs doivent être fournis.
    """
    a1_fiabilite: Optional[float] = None
    a_contamination: Optional[float] = None
    a_lubrification: Optional[float] = None
    a_temperature: Optional[float] = None
    aISO_global: Optional[float] = None

    def facteur_global(self) -> Optional[float]:
        if self.aISO_global is not None:
            return _req_pos("aISO_global", self.aISO_global, strictly=False)
        vals: List[float] = []
        for name, v in (
            ("a_contamination", self.a_contamination),
            ("a_lubrification", self.a_lubrification),
            ("a_temperature", self.a_temperature),
        ):
            if v is not None:
                vals.append(_req_pos(name, v, strictly=False))
        if not vals:
            return None
        prod = 1.0
        for v in vals:
            prod *= v
        return prod


@dataclass
class ContraintesMontageRoulement:
    ajustement_arbre: Optional[str] = None
    ajustement_logement: Optional[str] = None

    rugosite_arbre_Ra_m: Optional[float] = None
    rugosite_logement_Ra_m: Optional[float] = None

    rugosite_arbre_Rq_m: Optional[float] = None
    rugosite_palier_Rq_m: Optional[float] = None

    faux_rond_mesure_m: Optional[float] = None
    faux_rond_admissible_m: Optional[float] = None

    coaxialite_mesure_m: Optional[float] = None
    coaxialite_admissible_m: Optional[float] = None

    epaulement_disponible_m: Optional[float] = None
    epaulement_min_m: Optional[float] = None

    rayon_conge_arbre_m: Optional[float] = None
    rayon_conge_logement_m: Optional[float] = None
    rayon_appui_max_m: Optional[float] = None


@dataclass
class HydrodynamiquePalierLisse:
    viscosite_Pa_s: Optional[float] = None
    jeu_radial_m: Optional[float] = None
    eccentricite_relative: Optional[float] = None
    lambda_min_admissible: Optional[float] = None


# =============================================================================
# Pièce : Roulement à aiguilles (arbre / vilebrequin)
# =============================================================================


@dataclass
class RoulementAiguilleArbre:
    """
    Roulement à aiguilles "issu du commerce".
    Objectif : sortir un maximum d'informations calculées pour choisir une référence catalogue,
    SANS RIEN INVENTER.

    Dépendances (recommandées) :
    - vilbrequin (backend/components/moteur_thermique/pieces/vilbrequin.py) : rpm, couple, diamètres/largeurs des portées.
    - bielle / piston : si ces modules fournissent une force max, on peut l'utiliser comme charge radiale candidate.
    - coussinet/palier lisse : si une zone n'est pas un roulement à aiguilles, ce module peut aussi exposer
      un bloc hydrodynamique de premier niveau ou relayer un vrai module coussinet.

    Remarque :
    - Un roulement à aiguilles standard est principalement radial.
      Si tu as une charge axiale (thrust), il faut une autre solution (butée) :
      le module ne déduit pas une butée sans données explicites.
    """

    # Dépendances
    vilbrequin: Optional[Any] = None
    arbre_vilbrequin: Optional[Any] = None
    bielle: Optional[Any] = None
    piston: Optional[Any] = None
    cylindre: Optional[Any] = None
    palier_lisse: Optional[Any] = None

    # Sélection / position (si tu veux forcer une seule portée)
    # None => calcule et rapporte "journal principal" ET "maneton" si disponibles.
    type_portee: Optional[str] = None  # "journal" | "maneton" | None
    mode_support: Literal["roulement_aiguille", "coussinet"] = "roulement_aiguille"

    # Entrées explicites (si non déductibles)
    rpm: Optional[float] = None
    couple_max_Nm: Optional[float] = None
    rayon_manivelle_m: Optional[float] = None

    # Charges explicites
    force_radiale_equivalente_N: Optional[float] = None
    force_axiale_N: Optional[float] = None
    force_radiale_statique_extreme_N: Optional[float] = None
    force_radiale_fatigue_N: Optional[float] = None

    # Spectre / cycle de charge
    cycle_charge: Optional[CycleChargeRoulement] = None

    # Critère de vie (si tu veux dimensionner C requis)
    duree_vie_cible_h: Optional[float] = None

    # Exposant p (roulements à rouleaux/à aiguilles ~ 10/3) :
    # si tu ne veux rien supposer, laisse None -> pas de calcul de durée de vie.
    exposant_vie_p: Optional[float] = None

    # Facteurs de vie ajustée (fiabilité / contamination / lubrification / température)
    facteurs_vie: Optional[FacteursVieRoulement] = None

    # Critères statiques / projetés
    pression_projetee_admissible_pa: Optional[float] = None
    securite_statique_cible: Optional[float] = None

    # Contraintes arbre (si diamètres inconnus et si on veut calculer un d_min)
    limite_elastique_pa: Optional[float] = None
    facteur_securite: float = 2.0

    # Limites de montage explicites
    contraintes_montage: Optional[ContraintesMontageRoulement] = None

    # Bloc hydrodynamique si la zone est en coussinet ou si l'on veut comparer
    hydrodynamique_palier: Optional[HydrodynamiquePalierLisse] = None

    # Référence commerce (facultatif) + vérification
    reference: Optional[ReferenceRoulementAiguille] = None

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "roulement_aiguille_arbre",
            "entrees": {},
            "recuperations": {},
            "roulement": {},
            "dimensions_requises": {},
            "dimensions_reference": {},
            "charges": {},
            "cycle_charge": {},
            "vie": {},
            "montage": {},
            "palier_lisse": {},
            "verifications_reference": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ---------------------------------------------------------------------
        # 1) Récupérer rapports dépendances
        # ---------------------------------------------------------------------
        rep_vb = _try_call_report(self.vilbrequin)
        rep_av = _try_call_report(self.arbre_vilbrequin)
        rep_b = _try_call_report(self.bielle)
        rep_p = _try_call_report(self.piston)
        rep_c = _try_call_report(self.cylindre)
        rep_pl = _try_call_report(self.palier_lisse)

        rapport["recuperations"] = {
            "vilbrequin": bool(rep_vb),
            "arbre_vilbrequin": bool(rep_av),
            "bielle": bool(rep_b),
            "piston": bool(rep_p),
            "cylindre": bool(rep_c),
            "palier_lisse": bool(rep_pl),
        }

        # ---------------------------------------------------------------------
        # 2) Cinématique : rpm / couple / rayon
        # ---------------------------------------------------------------------
        rpm = self.rpm
        if rpm is None:
            rpm = _dig(rep_vb, "cinematique", "rpm")
            if rpm is None:
                rpm = _dig(rep_av, "recuperations", "rpm") or _dig(rep_av, "cinematique", "rpm")
            if rpm is None:
                rpm = _get(self.vilbrequin, "rpm") or _get(self.arbre_vilbrequin, "rpm")
        if rpm is not None:
            rpm = _req_pos("rpm", rpm, strictly=False)
            rapport["roulement"]["rpm"] = rpm
        else:
            _push_inconnue(rapport, "partielles", "rpm", "Requis pour vérifier vitesse et calculer une durée de vie en heures.")

        T = self.couple_max_Nm
        if T is None:
            T = _dig(rep_vb, "cinematique", "couple_max_Nm")
            if T is None:
                T = _dig(rep_av, "entrees", "couple_max_Nm")
            if T is None:
                T = _get(self.vilbrequin, "couple_max_Nm") or _get(self.arbre_vilbrequin, "couple_max_Nm")
        if T is not None:
            T = _req_pos("couple_max_Nm", T, strictly=False)
            rapport["roulement"]["couple_max_Nm"] = T
        else:
            _push_inconnue(rapport, "partielles", "couple_max_Nm", "Utile pour force tangente équivalente (F=T/r) si r est connu.")

        r = self.rayon_manivelle_m
        if r is None:
            r = _dig(rep_vb, "cinematique", "rayon_manivelle_m")
            if r is None:
                r = _dig(rep_av, "cinematique", "rayon_manivelle_m")
        if r is not None:
            r = _req_pos("rayon_manivelle_m", r)
            rapport["roulement"]["rayon_manivelle_m"] = r
        else:
            _push_inconnue(rapport, "partielles", "rayon_manivelle_m", "Requis pour F=T/r (force tangente équivalente).")

        # ---------------------------------------------------------------------
        # 3) Géométrie portée : (journal, maneton) depuis vilbrequin/arbre_vilbrequin
        # ---------------------------------------------------------------------
        def lire_portee(kind: str) -> Dict[str, Optional[float]]:
            if kind == "journal":
                d = (
                    _dig(rep_vb, "geometrie", "diametre_journal_principal_m")
                    or _dig(rep_av, "journal", "diametre_m")
                    or _dig(rep_av, "geometrie", "diametre_journal_principal_m")
                    or _get(self.vilbrequin, "diametre_journal_principal_m")
                    or _get(self.arbre_vilbrequin, "diametre_journal_principal_m")
                )
                B = (
                    _dig(rep_vb, "geometrie", "largeur_portee_journal_m")
                    or _dig(rep_av, "geometrie", "largeur_portee_journal_m")
                    or _get(self.vilbrequin, "largeur_portee_journal_m")
                    or _get(self.arbre_vilbrequin, "largeur_portee_journal_m")
                )
            else:
                d = (
                    _dig(rep_vb, "geometrie", "diametre_maneton_m")
                    or _dig(rep_av, "geometrie", "diametre_maneton_m")
                    or _get(self.vilbrequin, "diametre_maneton_m")
                    or _get(self.arbre_vilbrequin, "diametre_maneton_m")
                )
                B = (
                    _dig(rep_vb, "geometrie", "largeur_portee_maneton_m")
                    or _dig(rep_av, "geometrie", "largeur_portee_maneton_m")
                    or _get(self.vilbrequin, "largeur_portee_maneton_m")
                    or _get(self.arbre_vilbrequin, "largeur_portee_maneton_m")
                )
                if B is None:
                    B = _dig(rep_b, "geometrie", "grande_tete", "longueur_portee_grande_tete_m") or _get(self.bielle, "longueur_portee_grande_tete_m")
            out: Dict[str, Optional[float]] = {"d_m": None, "B_m": None}
            if d is not None and _is_finite(d):
                out["d_m"] = _req_pos(f"diametre_{kind}_m", d)
            if B is not None and _is_finite(B):
                out["B_m"] = _req_pos(f"largeur_portee_{kind}_m", B)
            return out

        portee_j = lire_portee("journal")
        portee_m = lire_portee("maneton")

        rapport["dimensions_requises"]["journal"] = {
            "d_interieur_requis_m": portee_j["d_m"],
            "B_largeur_requise_m": portee_j["B_m"],
        }
        rapport["dimensions_requises"]["maneton"] = {
            "d_interieur_requis_m": portee_m["d_m"],
            "B_largeur_requise_m": portee_m["B_m"],
        }

        if portee_j["d_m"] is None:
            _push_inconnue(rapport, "partielles", "diametre_journal_principal_m", "Requis pour choisir l'alésage (d) du roulement côté journal.")
        if portee_m["d_m"] is None:
            _push_inconnue(rapport, "partielles", "diametre_maneton_m", "Requis pour choisir l'alésage (d) du roulement côté maneton.")
        if portee_j["B_m"] is None:
            _push_inconnue(rapport, "partielles", "largeur_portee_journal_m", "Requise pour choisir la largeur (B) du roulement côté journal.")
        if portee_m["B_m"] is None:
            _push_inconnue(rapport, "partielles", "largeur_portee_maneton_m", "Requise pour choisir la largeur (B) du roulement côté maneton.")

        type_portee = self.type_portee
        if type_portee is not None and type_portee not in ("journal", "maneton"):
            raise ValueError("type_portee doit être 'journal', 'maneton' ou None.")

        # ---------------------------------------------------------------------
        # 4) Charges : candidates calculables + cycle variable
        # ---------------------------------------------------------------------
        Fr_user = self.force_radiale_equivalente_N
        if Fr_user is not None:
            Fr_user = _req_pos("force_radiale_equivalente_N", Fr_user, strictly=False)
            rapport["charges"]["force_radiale_equivalente_N"] = Fr_user

        Fax = self.force_axiale_N
        if Fax is not None:
            Fax = _req_pos("force_axiale_N", Fax, strictly=False)
            rapport["charges"]["force_axiale_N"] = Fax
            rapport["notes_modele"].append(
                "Charge axiale fournie. Un roulement à aiguilles standard est principalement radial : vérifier la nécessité d'une butée."
            )

        Fr_static_user = self.force_radiale_statique_extreme_N
        if Fr_static_user is not None:
            Fr_static_user = _req_pos("force_radiale_statique_extreme_N", Fr_static_user, strictly=False)
            rapport["charges"]["force_radiale_statique_extreme_N"] = Fr_static_user

        Fr_fatigue_user = self.force_radiale_fatigue_N
        if Fr_fatigue_user is not None:
            Fr_fatigue_user = _req_pos("force_radiale_fatigue_N", Fr_fatigue_user, strictly=False)
            rapport["charges"]["force_radiale_fatigue_N"] = Fr_fatigue_user

        F_tan = None
        if T is not None and r is not None and r > 0:
            F_tan = _force_tangentielle_depuis_couple(T, r)
            rapport["charges"]["force_tangente_equivalente_N"] = F_tan
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "force_tangente_equivalente_N",
                "Calculable si couple_max_Nm et rayon_manivelle_m sont connus (F=T/r).",
            )

        F_bielle_max = None
        v = _dig(rep_b, "efforts", "force_axiale_max_N")
        if _is_finite(v):
            F_bielle_max = abs(float(v))
            rapport["charges"]["force_max_depuis_bielle_N"] = F_bielle_max

        F_gaz = None
        v = _dig(rep_p, "resultats", "force_gaz_N")
        if not _is_finite(v):
            v = _dig(rep_p, "charges", "force_gaz_N")
        if _is_finite(v):
            F_gaz = abs(float(v))
            rapport["charges"]["force_gaz_depuis_piston_N"] = F_gaz

        candidates: List[float] = []
        for val in (F_tan, F_bielle_max, F_gaz):
            if val is not None and _is_finite(val) and val >= 0:
                candidates.append(float(val))

        # -------- Cycle variable / angle --------
        p_cycle = self.exposant_vie_p if self.exposant_vie_p is not None else None
        cycle = self.cycle_charge
        P_cycle_eq = None
        P_cycle_eq_res = None
        P_cycle_static = None
        P_cycle_static_res = None
        P_cycle_fatigue = None

        if cycle is not None:
            if not cycle.points:
                _push_inconnue(rapport, "partielles", "cycle_charge.points", "Le cycle de charge est fourni mais vide.")
            else:
                Frs: List[float] = []
                Fas: List[float] = []
                Rs: List[float] = []
                ws: List[float] = []
                for i, pt in enumerate(cycle.points):
                    ang = _req_finite(f"cycle_charge.points[{i}].angle_deg", pt.angle_deg)
                    Fr_i = _req_pos(f"cycle_charge.points[{i}].force_radiale_N", pt.force_radiale_N, strictly=False)
                    Fa_i = _req_pos(f"cycle_charge.points[{i}].force_axiale_N", pt.force_axiale_N, strictly=False)
                    w_i = _req_pos(f"cycle_charge.points[{i}].poids", pt.poids, strictly=False)
                    Frs.append(Fr_i)
                    Fas.append(Fa_i)
                    Rs.append(_charge_resultante(Fr_i, Fa_i))
                    ws.append(w_i)
                    if Fa_i > 0.0:
                        rapport["notes_modele"].append(
                            "Le cycle de charge contient une composante axiale ; elle est rapportée à part et n'est pas convertie en P ISO sans facteur constructeur explicite."
                        )
                rapport["cycle_charge"] = {
                    "nom": cycle.nom,
                    "nombre_points": len(cycle.points),
                    "angle_min_deg": min(float(pt.angle_deg) for pt in cycle.points),
                    "angle_max_deg": max(float(pt.angle_deg) for pt in cycle.points),
                    "force_radiale_min_N": min(Frs),
                    "force_radiale_max_N": max(Frs),
                    "force_radiale_moyenne_N": _mean(Frs, ws),
                    "force_radiale_amplitude_N": _amplitude_from_extrema(min(Frs), max(Frs)),
                    "force_axiale_min_N": min(Fas),
                    "force_axiale_max_N": max(Fas),
                    "force_resultante_max_N": max(Rs),
                }
                if min(Frs) > 0.0:
                    rapport["cycle_charge"]["rapport_R_radial"] = min(Frs) / max(Frs)
                elif max(Frs) == 0.0:
                    rapport["cycle_charge"]["rapport_R_radial"] = None
                else:
                    rapport["cycle_charge"]["rapport_R_radial"] = float("inf")

                if p_cycle is not None:
                    p_cycle = _req_pos("exposant_vie_p", p_cycle)
                    P_cycle_eq = _charge_equivalente_cycle(Frs, ws, p=p_cycle)
                    P_cycle_eq_res = _charge_equivalente_cycle(Rs, ws, p=p_cycle)
                    P_cycle_fatigue = P_cycle_eq
                    rapport["cycle_charge"]["P_equivalente_cycle_radiale_N"] = P_cycle_eq
                    rapport["cycle_charge"]["P_equivalente_cycle_resultante_N"] = P_cycle_eq_res
                    rapport["cycle_charge"]["exposant_p_utilise"] = p_cycle
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "cycle_charge.P_equivalente_cycle_N",
                        "Calculable si exposant_vie_p est fourni pour pondérer les charges du cycle.",
                    )

                P_cycle_static = max(Frs)
                P_cycle_static_res = max(Rs)
                rapport["cycle_charge"]["cas_statique_extreme_radial_N"] = P_cycle_static
                rapport["cycle_charge"]["cas_statique_extreme_resultant_N"] = P_cycle_static_res
                rapport["cycle_charge"]["cas_fatigue_radial_moyen_N"] = _mean_from_extrema(min(Frs), max(Frs))
                rapport["cycle_charge"]["cas_fatigue_radial_alterne_N"] = _amplitude_from_extrema(min(Frs), max(Frs))

        # Sélection de P dynamique
        if Fr_user is not None:
            P_dyn = Fr_user
            rapport["charges"]["P_equivalente_N"] = P_dyn
            rapport["charges"]["P_source"] = "force_radiale_equivalente_N (entrée utilisateur)"
        elif P_cycle_eq is not None:
            P_dyn = P_cycle_eq
            rapport["charges"]["P_equivalente_N"] = P_dyn
            rapport["charges"]["P_source"] = "cycle_charge.P_equivalente_cycle_radiale_N"
        else:
            P_dyn = None
            if candidates:
                rapport["charges"]["P_min_calculable_N"] = min(candidates)
                rapport["charges"]["P_max_calculable_N"] = max(candidates)
                rapport["charges"]["P_sources_disponibles"] = [
                    "force_tangente_equivalente_N" if F_tan is not None else None,
                    "force_max_depuis_bielle_N" if F_bielle_max is not None else None,
                    "force_gaz_depuis_piston_N" if F_gaz is not None else None,
                ]
                rapport["charges"]["P_sources_disponibles"] = [s for s in rapport["charges"]["P_sources_disponibles"] if s]
                _push_inconnue(
                    rapport,
                    "partielles",
                    "P_equivalente_N",
                    "Pour dimensionner un roulement catalogue, il faut une charge radiale équivalente P. "
                    "Tu peux la fournir directement, ou fournir un modèle de charges (cycle/angles/appuis).",
                )
            else:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "P_equivalente_N",
                    "Aucune charge calculable : fournir force_radiale_equivalente_N ou rendre déductible via bielle/piston/cycle.",
                )

        # Sélection de P0 statique
        if Fr_static_user is not None:
            P0 = Fr_static_user
            rapport["charges"]["P0_statique_N"] = P0
            rapport["charges"]["P0_source"] = "force_radiale_statique_extreme_N (entrée utilisateur)"
        elif P_cycle_static is not None:
            P0 = P_cycle_static
            rapport["charges"]["P0_statique_N"] = P0
            rapport["charges"]["P0_source"] = "cycle_charge.cas_statique_extreme_radial_N"
            if P_cycle_static_res is not None and Fax is not None:
                rapport["charges"]["P0_resultant_N"] = P_cycle_static_res
        elif candidates:
            P0 = max(candidates)
            rapport["charges"]["P0_statique_N"] = P0
            rapport["charges"]["P0_source"] = "max(candidats_calculables)"
        else:
            P0 = None
            _push_inconnue(
                rapport,
                "partielles",
                "P0_statique_N",
                "Requis pour vérifier C0 et la sécurité statique ; fournir force_radiale_statique_extreme_N ou un cycle de charge.",
            )

        # Cas fatigue
        if Fr_fatigue_user is not None:
            P_fatigue = Fr_fatigue_user
            rapport["charges"]["P_fatigue_N"] = P_fatigue
            rapport["charges"]["P_fatigue_source"] = "force_radiale_fatigue_N (entrée utilisateur)"
        elif P_cycle_fatigue is not None:
            P_fatigue = P_cycle_fatigue
            rapport["charges"]["P_fatigue_N"] = P_fatigue
            rapport["charges"]["P_fatigue_source"] = "cycle_charge.P_equivalente_cycle_radiale_N"
        else:
            P_fatigue = None
            _push_inconnue(
                rapport,
                "partielles",
                "P_fatigue_N",
                "Requis pour un cas fatigue dédié ; calculable via cycle_charge ou à fournir explicitement.",
            )

        # ---------------------------------------------------------------------
        # 5) Pression projetée (optionnel) : p = Fr/(d*B)
        # ---------------------------------------------------------------------
        p_adm = self.pression_projetee_admissible_pa
        if p_adm is not None:
            p_adm = _req_pos("pression_projetee_admissible_pa", p_adm, strictly=True)
            rapport["roulement"]["pression_projetee_admissible_pa"] = p_adm

        def pression_projetee(Fr: float, d: float, B: float) -> Optional[float]:
            if Fr is None or d is None or B is None:
                return None
            if d <= 0 or B <= 0:
                return None
            return Fr / (d * B)

        Fr_for_pressure = None
        if P0 is not None:
            Fr_for_pressure = P0
        elif P_dyn is not None:
            Fr_for_pressure = P_dyn

        if Fr_for_pressure is not None:
            pj = None
            pm = None
            if portee_j["d_m"] is not None and portee_j["B_m"] is not None:
                pj = pression_projetee(Fr_for_pressure, portee_j["d_m"], portee_j["B_m"])
            if portee_m["d_m"] is not None and portee_m["B_m"] is not None:
                pm = pression_projetee(Fr_for_pressure, portee_m["d_m"], portee_m["B_m"])
            rapport["charges"]["pression_projetee_journal_pa"] = pj
            rapport["charges"]["pression_projetee_maneton_pa"] = pm
            rapport["charges"]["pression_projetee_source"] = "P0_statique_N" if P0 is not None else "P_equivalente_N"

            if p_adm is not None:
                rapport["charges"]["ok_p_proj_journal"] = (pj is not None and pj <= p_adm)
                rapport["charges"]["ok_p_proj_maneton"] = (pm is not None and pm <= p_adm)

        # ---------------------------------------------------------------------
        # 6) Dimensionnement vie : C requis, C0 requis, vie ajustée
        # ---------------------------------------------------------------------
        p = self.exposant_vie_p
        if p is not None:
            p = _req_pos("exposant_vie_p", p, strictly=True)
            rapport["vie"]["exposant_p"] = p
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "exposant_vie_p",
                "Requis pour calculer L10 / C requis (catalogue). Pour un roulement à rouleaux, p est généralement > 1 (à confirmer).",
            )

        Lh = self.duree_vie_cible_h
        if Lh is not None:
            Lh = _req_pos("duree_vie_cible_h", Lh, strictly=True)
            rapport["vie"]["duree_vie_cible_h"] = Lh
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "duree_vie_cible_h",
                "Requise pour calculer C requis (sinon impossible de dimensionner la capacité dynamique).",
            )

        a1 = None
        aISO = None
        if self.facteurs_vie is not None:
            fv = self.facteurs_vie
            if fv.a1_fiabilite is not None:
                a1 = _req_pos("a1_fiabilite", fv.a1_fiabilite, strictly=False)
                rapport["vie"]["a1_fiabilite"] = a1
            if fv.a_contamination is not None:
                rapport["vie"]["a_contamination"] = _req_pos("a_contamination", fv.a_contamination, strictly=False)
            if fv.a_lubrification is not None:
                rapport["vie"]["a_lubrification"] = _req_pos("a_lubrification", fv.a_lubrification, strictly=False)
            if fv.a_temperature is not None:
                rapport["vie"]["a_temperature"] = _req_pos("a_temperature", fv.a_temperature, strictly=False)
            aISO = fv.facteur_global()
            if aISO is not None:
                rapport["vie"]["aISO_global"] = aISO
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "facteurs_vie",
                "Optionnel : fournir a1/aISO ou des facteurs explicites de contamination, lubrification et température pour la vie ajustée.",
            )

        if p is not None and Lh is not None and rpm is not None and P_dyn is not None:
            C_req = _C_required_from_P_L10h(P_dyn, rpm, Lh, p=p)
            rapport["vie"]["C_dynamique_requis_N"] = C_req
            rapport["vie"]["P_utilisee_N"] = P_dyn
            rapport["vie"]["P_source"] = rapport["charges"].get("P_source")
            if a1 is not None or aISO is not None:
                facteur_vie = (a1 if a1 is not None else 1.0) * (aISO if aISO is not None else 1.0)
                rapport["vie"]["facteur_vie_ajustee"] = facteur_vie
                rapport["vie"]["C_dynamique_requis_N_note"] = (
                    "C_dynamique_requis_N reste basé sur L10. La vie ajustée est rapportée séparément via le facteur multiplicatif explicite fourni."
                )
        else:
            if P_dyn is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "C_dynamique_requis_N",
                    "Calculable si (P_equivalente_N, rpm, duree_vie_cible_h, exposant_vie_p) sont fournis.",
                )

        s0_target = self.securite_statique_cible
        if s0_target is not None:
            s0_target = _req_pos("securite_statique_cible", s0_target)
            rapport["vie"]["securite_statique_cible"] = s0_target
            if P0 is not None:
                rapport["vie"]["C0_statique_requis_N"] = s0_target * P0
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "C0_statique_requis_N",
                    "Calculable si securite_statique_cible et P0_statique_N sont connus.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "securite_statique_cible",
                "Optionnel : fournir un coefficient de sécurité statique cible pour dimensionner C0.",
            )

        # ---------------------------------------------------------------------
        # 7) d_min (arbre) : uniquement si on manque de diamètre et si Re + T sont connus
        # ---------------------------------------------------------------------
        Re = self.limite_elastique_pa
        if Re is None:
            Re = _dig(rep_vb, "materiau", "limite_elastique_pa")
            if Re is None:
                Re = _dig(rep_av, "materiau", "limite_elastique_pa")
        if Re is not None:
            Re = _req_pos("limite_elastique_pa", Re, strictly=True)
            rapport["roulement"]["limite_elastique_pa"] = Re

        FS = _req_pos("facteur_securite", self.facteur_securite, strictly=True)
        rapport["roulement"]["facteur_securite"] = FS

        if T is not None and Re is not None:
            try:
                dmin = _dmin_torsion_vonmises(T, Re, FS)
                rapport["dimensions_requises"]["d_min_torsion_vonmises_m"] = dmin
                if portee_j["d_m"] is None:
                    rapport["dimensions_requises"]["journal"]["d_interieur_requis_m"] = dmin
                    rapport["notes_modele"].append("Journal : d_interieur_requis_m fixé par d_min (torsion von Mises) faute de diamètre connu.")
                if portee_m["d_m"] is None:
                    rapport["dimensions_requises"]["maneton"]["d_interieur_requis_m"] = dmin
                    rapport["notes_modele"].append("Maneton : d_interieur_requis_m fixé par d_min (torsion von Mises) faute de diamètre connu.")
            except Exception as e:
                _push_inconnue(rapport, "partielles", "d_min_torsion_vonmises_m", f"Erreur calcul d_min torsion : {e!r}")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "d_min_torsion_vonmises_m",
                "Calculable si couple_max_Nm et limite_elastique_pa sont connus (avec facteur_securite).",
            )

        # ---------------------------------------------------------------------
        # 8) Montage / géométrie d'interface
        # ---------------------------------------------------------------------
        montage: Dict[str, Any] = {}
        cm = self.contraintes_montage
        ref = self.reference

        if cm is not None:
            montage["ajustement_arbre"] = cm.ajustement_arbre
            montage["ajustement_logement"] = cm.ajustement_logement

            if cm.rugosite_arbre_Ra_m is not None:
                montage["rugosite_arbre_Ra_m"] = _req_pos("rugosite_arbre_Ra_m", cm.rugosite_arbre_Ra_m, strictly=False)
            if cm.rugosite_logement_Ra_m is not None:
                montage["rugosite_logement_Ra_m"] = _req_pos("rugosite_logement_Ra_m", cm.rugosite_logement_Ra_m, strictly=False)

            if cm.faux_rond_mesure_m is not None:
                montage["faux_rond_mesure_m"] = _req_pos("faux_rond_mesure_m", cm.faux_rond_mesure_m, strictly=False)
            if cm.faux_rond_admissible_m is not None:
                montage["faux_rond_admissible_m"] = _req_pos("faux_rond_admissible_m", cm.faux_rond_admissible_m, strictly=False)
            if cm.coaxialite_mesure_m is not None:
                montage["coaxialite_mesure_m"] = _req_pos("coaxialite_mesure_m", cm.coaxialite_mesure_m, strictly=False)
            if cm.coaxialite_admissible_m is not None:
                montage["coaxialite_admissible_m"] = _req_pos("coaxialite_admissible_m", cm.coaxialite_admissible_m, strictly=False)
            if cm.epaulement_disponible_m is not None:
                montage["epaulement_disponible_m"] = _req_pos("epaulement_disponible_m", cm.epaulement_disponible_m, strictly=False)
            if cm.epaulement_min_m is not None:
                montage["epaulement_min_m"] = _req_pos("epaulement_min_m", cm.epaulement_min_m, strictly=False)
            if cm.rayon_conge_arbre_m is not None:
                montage["rayon_conge_arbre_m"] = _req_pos("rayon_conge_arbre_m", cm.rayon_conge_arbre_m, strictly=False)
            if cm.rayon_conge_logement_m is not None:
                montage["rayon_conge_logement_m"] = _req_pos("rayon_conge_logement_m", cm.rayon_conge_logement_m, strictly=False)

            rayon_appui_max = None
            if cm.rayon_appui_max_m is not None:
                rayon_appui_max = _req_pos("rayon_appui_max_m", cm.rayon_appui_max_m, strictly=False)
            elif ref is not None and ref.rayon_appui_max_m is not None:
                rayon_appui_max = _req_pos("reference.rayon_appui_max_m", ref.rayon_appui_max_m, strictly=False)
            if rayon_appui_max is not None:
                montage["rayon_appui_max_m"] = rayon_appui_max

            if "faux_rond_mesure_m" in montage and "faux_rond_admissible_m" in montage:
                montage["faux_rond_ok"] = montage["faux_rond_mesure_m"] <= montage["faux_rond_admissible_m"]
            elif "faux_rond_mesure_m" in montage and ref is not None and ref.faux_rond_max_m is not None:
                faux_ref = _req_pos("reference.faux_rond_max_m", ref.faux_rond_max_m, strictly=False)
                montage["faux_rond_admissible_m"] = faux_ref
                montage["faux_rond_ok"] = montage["faux_rond_mesure_m"] <= faux_ref

            if "coaxialite_mesure_m" in montage and "coaxialite_admissible_m" in montage:
                montage["coaxialite_ok"] = montage["coaxialite_mesure_m"] <= montage["coaxialite_admissible_m"]
            elif "coaxialite_mesure_m" in montage and ref is not None and ref.coaxialite_max_m is not None:
                coax_ref = _req_pos("reference.coaxialite_max_m", ref.coaxialite_max_m, strictly=False)
                montage["coaxialite_admissible_m"] = coax_ref
                montage["coaxialite_ok"] = montage["coaxialite_mesure_m"] <= coax_ref

            if "epaulement_disponible_m" in montage and "epaulement_min_m" in montage:
                montage["epaulement_ok"] = montage["epaulement_disponible_m"] >= montage["epaulement_min_m"]

            if rayon_appui_max is not None and "rayon_conge_arbre_m" in montage:
                montage["rayon_appui_arbre_ok"] = montage["rayon_conge_arbre_m"] <= rayon_appui_max
            if rayon_appui_max is not None and "rayon_conge_logement_m" in montage:
                montage["rayon_appui_logement_ok"] = montage["rayon_conge_logement_m"] <= rayon_appui_max

            if "rugosite_arbre_Ra_m" in montage:
                if ref is not None and ref.rugosite_arbre_max_Ra_m is not None:
                    ref_ra = _req_pos("reference.rugosite_arbre_max_Ra_m", ref.rugosite_arbre_max_Ra_m, strictly=False)
                    montage["rugosite_arbre_max_Ra_m"] = ref_ra
                    montage["rugosite_arbre_ok"] = montage["rugosite_arbre_Ra_m"] <= ref_ra
            else:
                _push_inconnue(rapport, "partielles", "rugosite_arbre_Ra_m", "Optionnel : utile pour qualifier le montage du roulement.")

            if "rugosite_logement_Ra_m" in montage:
                if ref is not None and ref.rugosite_logement_max_Ra_m is not None:
                    ref_ra = _req_pos("reference.rugosite_logement_max_Ra_m", ref.rugosite_logement_max_Ra_m, strictly=False)
                    montage["rugosite_logement_max_Ra_m"] = ref_ra
                    montage["rugosite_logement_ok"] = montage["rugosite_logement_Ra_m"] <= ref_ra
            else:
                _push_inconnue(rapport, "partielles", "rugosite_logement_Ra_m", "Optionnel : utile pour qualifier le montage du roulement.")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "contraintes_montage",
                "Optionnel : fournir ajustements, rugosités, faux-rond, coaxialité, épaulements et rayons d'appui pour une vérification fine du montage.",
            )

        rapport["montage"] = montage

        # ---------------------------------------------------------------------
        # 9) Bloc palier lisse / hydrodynamique (si certaines zones ne sont pas à aiguilles)
        # ---------------------------------------------------------------------
        palier_bloc: Dict[str, Any] = {"mode_support": self.mode_support}

        if rep_pl is not None:
            palier_bloc["source"] = "module_palier_lisse"
            palier_bloc["rapport_source"] = {
                "pression_projetee": _dig(rep_pl, "pression_projetee"),
                "pv": _dig(rep_pl, "pv"),
                "frottement": _dig(rep_pl, "frottement"),
                "hydrodynamique": _dig(rep_pl, "hydrodynamique"),
                "thermique": _dig(rep_pl, "thermique"),
            }
        elif self.hydrodynamique_palier is not None or self.mode_support == "coussinet":
            hydro = self.hydrodynamique_palier or HydrodynamiquePalierLisse()
            palier_bloc["source"] = "calcul_interne_simplifie"

            if type_portee == "journal":
                d_h = portee_j["d_m"]
                L_h = portee_j["B_m"]
            elif type_portee == "maneton":
                d_h = portee_m["d_m"]
                L_h = portee_m["B_m"]
            else:
                d_h = portee_m["d_m"] or portee_j["d_m"]
                L_h = portee_m["B_m"] or portee_j["B_m"]

            W = P_dyn if P_dyn is not None else P0
            eta = hydro.viscosite_Pa_s
            c = hydro.jeu_radial_m

            if W is not None and d_h is not None and L_h is not None:
                p_proj_palier = W / (d_h * L_h)
                palier_bloc["pression_projetee_pa"] = p_proj_palier
            else:
                p_proj_palier = None
                _push_inconnue(
                    rapport,
                    "partielles",
                    "palier_lisse.pression_projetee_pa",
                    "Calculable si charge, diamètre et largeur de palier sont connus.",
                )

            if eta is not None and c is not None and rpm is not None and d_h is not None and L_h is not None and p_proj_palier is not None:
                eta_v = _req_pos("viscosite_Pa_s", eta)
                c_v = _req_pos("jeu_radial_m", c)
                S = _sommerfeld_number(eta_v, rpm, d_h, L_h, c_v, p_proj_palier)
                T_shear = _hydrodynamic_shear_torque(eta_v, rpm, d_h, L_h, c_v)
                omega = 2.0 * math.pi * rpm / 60.0
                P_shear = T_shear * omega
                palier_bloc["hydrodynamique"] = {
                    "sommerfeld_S": S,
                    "viscosite_Pa_s": eta_v,
                    "jeu_radial_m": c_v,
                    "couple_cisaillement_hydrodynamique_Nm": T_shear,
                    "puissance_cisaillement_hydrodynamique_W": P_shear,
                }

                if hydro.eccentricite_relative is not None:
                    eps = _req_pos("eccentricite_relative", hydro.eccentricite_relative, strictly=False)
                    if eps > 1.0:
                        raise ValueError("eccentricite_relative doit être <= 1.")
                    h_min = c_v * (1.0 - eps)
                    palier_bloc["hydrodynamique"]["eccentricite_relative"] = eps
                    palier_bloc["hydrodynamique"]["epaisseur_minimale_film_m"] = h_min

                    rq1 = None
                    rq2 = None
                    if self.contraintes_montage is not None:
                        rq1 = self.contraintes_montage.rugosite_arbre_Rq_m
                        rq2 = self.contraintes_montage.rugosite_palier_Rq_m
                    if rq1 is not None and rq2 is not None:
                        rq1_v = _req_pos("rugosite_arbre_Rq_m", rq1, strictly=False)
                        rq2_v = _req_pos("rugosite_palier_Rq_m", rq2, strictly=False)
                        lam = _lambda_ratio(h_min, rq1_v, rq2_v)
                        palier_bloc["hydrodynamique"]["lambda_film"] = lam
                        if hydro.lambda_min_admissible is not None:
                            lam_min = _req_pos("lambda_min_admissible", hydro.lambda_min_admissible, strictly=False)
                            palier_bloc["hydrodynamique"]["lambda_min_admissible"] = lam_min
                            palier_bloc["hydrodynamique"]["securite_contact_mixte_ok"] = lam >= lam_min
                    else:
                        _push_inconnue(
                            rapport,
                            "partielles",
                            "palier_lisse.lambda_film",
                            "Calculable si epaisseur_minimale_film_m et rugosités Rq arbre/palier sont connues.",
                        )
                else:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "palier_lisse.epaisseur_minimale_film_m",
                        "Calculable si eccentricite_relative est fournie en plus du jeu radial.",
                    )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "palier_lisse.sommerfeld_S",
                    "Calculable si viscosite_Pa_s, jeu_radial_m, rpm, charge et géométrie sont connus.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "palier_lisse",
                "Optionnel : fournir un module coussinet/palier_lisse ou hydrodynamique_palier si certaines zones ne sont pas des roulements à aiguilles.",
            )

        rapport["palier_lisse"] = palier_bloc

        # ---------------------------------------------------------------------
        # 10) Référence commerce : copier + vérifier si possible
        # ---------------------------------------------------------------------
        if ref is not None:
            dims_ref: Dict[str, Any] = {"designation": ref.designation}

            if ref.d_interieur_m is not None:
                dims_ref["d_interieur_m"] = _req_pos("reference.d_interieur_m", ref.d_interieur_m)
            if ref.D_exterieur_m is not None:
                dims_ref["D_exterieur_m"] = _req_pos("reference.D_exterieur_m", ref.D_exterieur_m)
            if ref.B_largeur_m is not None:
                dims_ref["B_largeur_m"] = _req_pos("reference.B_largeur_m", ref.B_largeur_m)

            if ref.C_dynamique_N is not None:
                dims_ref["C_dynamique_N"] = _req_pos("reference.C_dynamique_N", ref.C_dynamique_N)
            if ref.C0_statique_N is not None:
                dims_ref["C0_statique_N"] = _req_pos("reference.C0_statique_N", ref.C0_statique_N)
            if ref.n_lim_rpm is not None:
                dims_ref["n_lim_rpm"] = _req_pos("reference.n_lim_rpm", ref.n_lim_rpm, strictly=False)
            if ref.rayon_appui_max_m is not None:
                dims_ref["rayon_appui_max_m"] = _req_pos("reference.rayon_appui_max_m", ref.rayon_appui_max_m, strictly=False)

            rapport["dimensions_reference"] = dims_ref
            rapport["roulement"].update({
                k: dims_ref[k] for k in ("d_interieur_m", "D_exterieur_m", "B_largeur_m") if k in dims_ref
            })

            def check_dims_for(kind: str) -> Dict[str, Any]:
                out: Dict[str, Any] = {}
                d_req = _dig(rapport, "dimensions_requises", kind, "d_interieur_requis_m")
                B_req = _dig(rapport, "dimensions_requises", kind, "B_largeur_requise_m")
                d_ref = dims_ref.get("d_interieur_m")
                B_ref = dims_ref.get("B_largeur_m")

                out["d_ok"] = (d_req is not None and d_ref is not None and abs(d_ref - d_req) < 1e-12)
                out["B_ok"] = (B_req is not None and B_ref is not None and B_ref >= B_req)
                out["d_requis_m"] = d_req
                out["d_ref_m"] = d_ref
                out["B_requise_m"] = B_req
                out["B_ref_m"] = B_ref
                return out

            if type_portee is None:
                rapport["verifications_reference"]["journal"] = check_dims_for("journal")
                rapport["verifications_reference"]["maneton"] = check_dims_for("maneton")
            else:
                rapport["verifications_reference"][type_portee] = check_dims_for(type_portee)

            if rpm is not None and ref.n_lim_rpm is not None:
                rapport["verifications_reference"]["vitesse_ok"] = rpm <= float(ref.n_lim_rpm)

            if p is not None and rpm is not None and P_dyn is not None and ref.C_dynamique_N is not None:
                L10h = _L10_h_from_C_P(float(ref.C_dynamique_N), float(P_dyn), float(rpm), p=p)
                rapport["verifications_reference"]["L10h_calculee_h"] = L10h
                if a1 is not None or aISO is not None:
                    rapport["verifications_reference"]["Lna_h"] = L10h * (a1 if a1 is not None else 1.0) * (aISO if aISO is not None else 1.0)
                if Lh is not None:
                    rapport["verifications_reference"]["L10h_ok"] = L10h >= float(Lh)
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "verification_L10h_reference",
                    "Calculable si (reference.C_dynamique_N, P_equivalente_N, rpm, exposant_vie_p) sont fournis.",
                )

            if P0 is not None and ref.C0_statique_N is not None:
                s0_ref = float(ref.C0_statique_N) / float(P0) if P0 > 0.0 else None
                rapport["verifications_reference"]["securite_statique_s0"] = s0_ref
                if s0_target is not None and s0_ref is not None:
                    rapport["verifications_reference"]["C0_ok"] = s0_ref >= s0_target
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "verification_C0_reference",
                    "Calculable si (reference.C0_statique_N, P0_statique_N) sont fournis.",
                )

            if cm is not None and ref.rayon_appui_max_m is not None:
                if cm.rayon_conge_arbre_m is not None:
                    rapport["verifications_reference"]["rayon_appui_arbre_ok"] = float(cm.rayon_conge_arbre_m) <= float(ref.rayon_appui_max_m)
                if cm.rayon_conge_logement_m is not None:
                    rapport["verifications_reference"]["rayon_appui_logement_ok"] = float(cm.rayon_conge_logement_m) <= float(ref.rayon_appui_max_m)

        else:
            _push_inconnue(
                rapport,
                "partielles",
                "reference_roulement",
                "Optionnel : si tu donnes une référence (d/D/B/C/C0/n_lim), le module peut la vérifier (dimensions, vitesse, vie, statique, montage).",
            )

        # ---------------------------------------------------------------------
        # 11) Format attendu par ArbreVilbrequin / Arbre (compat)
        # ---------------------------------------------------------------------
        if type_portee is None:
            rapport["dimensions_requises"]["d_interieur_requis_m"] = None
            _push_inconnue(
                rapport,
                "partielles",
                "dimensions_requises.d_interieur_requis_m",
                "Ambigu : préciser type_portee ('journal' ou 'maneton') si tu veux fournir un seul d_interieur_requis_m au module ArbreVilbrequin.",
            )
            rapport["dimensions_requises"]["B_largeur_requise_m"] = None
        else:
            rapport["dimensions_requises"]["d_interieur_requis_m"] = _dig(rapport, "dimensions_requises", type_portee, "d_interieur_requis_m")
            rapport["dimensions_requises"]["B_largeur_requise_m"] = _dig(rapport, "dimensions_requises", type_portee, "B_largeur_requise_m")

        # ---------------------------------------------------------------------
        # Entrées (traçabilité)
        # ---------------------------------------------------------------------
        rapport["entrees"] = {
            "type_portee": self.type_portee,
            "mode_support": self.mode_support,
            "rpm": self.rpm,
            "couple_max_Nm": self.couple_max_Nm,
            "rayon_manivelle_m": self.rayon_manivelle_m,
            "force_radiale_equivalente_N": self.force_radiale_equivalente_N,
            "force_axiale_N": self.force_axiale_N,
            "force_radiale_statique_extreme_N": self.force_radiale_statique_extreme_N,
            "force_radiale_fatigue_N": self.force_radiale_fatigue_N,
            "duree_vie_cible_h": self.duree_vie_cible_h,
            "exposant_vie_p": self.exposant_vie_p,
            "pression_projetee_admissible_pa": self.pression_projetee_admissible_pa,
            "securite_statique_cible": self.securite_statique_cible,
            "limite_elastique_pa": self.limite_elastique_pa,
            "facteur_securite": self.facteur_securite,
            "reference": (self.reference.designation if self.reference else None),
            "cycle_charge": (self.cycle_charge.nom if self.cycle_charge else None),
        }

        _dedup_inconnues(rapport)

        if strict:
            if type_portee is None:
                raise ValueError("strict=True : type_portee doit être 'journal' ou 'maneton'.")
            d_req = _dig(rapport, "dimensions_requises", type_portee, "d_interieur_requis_m")
            B_req = _dig(rapport, "dimensions_requises", type_portee, "B_largeur_requise_m")
            if d_req is None or B_req is None:
                raise ValueError("strict=True : d_interieur_requis_m et B_largeur_requise_m doivent être connus pour la portée choisie.")
            if rpm is None:
                raise ValueError("strict=True : rpm requis.")
            if P_dyn is None:
                raise ValueError("strict=True : une charge dynamique P_equivalente_N doit être connue (entrée directe ou cycle).")
            if self.mode_support == "roulement_aiguille" and self.reference is None:
                rapport["notes_modele"].append("strict=True sans référence : la géométrie requise est validée mais la vérification catalogue reste incomplète.")

        ajouter_dossier_definition_solidworks(rapport, "roulement_aiguille_arbre")
        return rapport


if __name__ == "__main__":  # pragma: no cover
    from pprint import pprint

    cycle = CycleChargeRoulement(
        nom="cycle_demo",
        points=[
            PointChargeRoulement(angle_deg=0.0, force_radiale_N=1200.0, force_axiale_N=0.0),
            PointChargeRoulement(angle_deg=90.0, force_radiale_N=1800.0, force_axiale_N=150.0),
            PointChargeRoulement(angle_deg=180.0, force_radiale_N=800.0, force_axiale_N=0.0),
        ],
    )

    r = RoulementAiguilleArbre(
        type_portee="maneton",
        rpm=1800.0,
        couple_max_Nm=45.0,
        rayon_manivelle_m=0.02,
        cycle_charge=cycle,
        exposant_vie_p=10.0 / 3.0,
        duree_vie_cible_h=20000.0,
        securite_statique_cible=1.5,
    ).analyser(strict=False)
    pprint(r)
