# backend/components/architecture.py
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple
import math


# ============================================================
# Types / profils d'usage + mobilité
# ============================================================

UsageType = Literal[
    "routier", "voiture", "moto", "quad", "buggy", "utilitaire",
    "nautique", "bateau", "drone_marin",
    "aerien", "aérien", "avion", "drone", "aeronef", "aéronef",
    "ferroviaire", "stationnaire", "autre",
]
DomaineMobiliteType = Literal["routier", "nautique", "aerien", "ferroviaire", "stationnaire", "autre"]
ModeTransmissionType = Literal["traction", "propulsion", "integrale", "inconnue"]
ArchitectureType = Literal["L", "V", "W", "Etoile", "Boxer"]


@dataclass(frozen=True)
class ProfilUsageMoteur:
    """
    Profil d'usage moteur + mobilité.

    Ce profil ne force pas une architecture : il transporte les contraintes qui
    permettent de la calculer.

    Deux modes restent possibles :
    - mode simple : puissance + régime + PME + vitesse piston + gabarit ;
    - mode fin multi-cas : cas_de_charge + taux_compression ;
    - mode mobilité : domaine/type/transmission + demande_mobilite permettant de
      déduire la puissance cible si elle n'est pas fournie directement.
    """
    longueur_dispo_m: float
    largeur_dispo_m: float
    usage: UsageType = "autre"
    hauteur_dispo_m: Optional[float] = None
    horizon_usage_h: float = 20000.0
    vitesse_piston_max_ms: Optional[float] = None
    taux_compression: Optional[float] = None

    # Couche mobilité / vecteur.
    domaine_mobilite: Optional[str] = None
    type_vehicule: Optional[str] = None
    mode_transmission: Optional[str] = None
    demande_mobilite: Optional[Mapping[str, Any]] = None

    # cas de charge explicites (mode fin)
    cas_de_charge: Optional[Tuple[Any, ...]] = None
    ordre_allumage_map: Optional[Mapping[int, Sequence[int] | str]] = None
    ponderations_cas: Optional[Mapping[str, float]] = None

    # pondérations explicites
    poids_maintenance: float = 1.0
    poids_masse: float = 1.0
    poids_cout_matiere: float = 1.0
    poids_compacite: float = 1.0
    poids_fiabilite: float = 1.0
    poids_rendement: float = 1.0

    # contraintes / préférences
    architectures_autorisees: Optional[Tuple[ArchitectureType, ...]] = None
    architecture_forcee: Optional[ArchitectureType] = None

    commentaire: str = ""


# ============================================================
# Normalisation mobilité
# ============================================================

def _norm_token(x: Any) -> str:
    s = "" if x is None else str(x)
    s = s.strip().lower()
    table = str.maketrans({
        "à": "a", "â": "a", "ä": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "î": "i", "ï": "i",
        "ô": "o", "ö": "o",
        "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
    })
    s = s.translate(table)
    for ch in (" ", "-", "/", "\\"):
        s = s.replace(ch, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s


def normaliser_domaine_mobilite(
    domaine_mobilite: Optional[str] = None,
    *,
    type_vehicule: Optional[str] = None,
    usage: Optional[str] = None,
) -> str:
    """
    Normalise le domaine d'application.

    Exemples :
    - voiture/moto/quad/buggy/utilitaire -> routier
    - bateau/drone marin -> nautique
    - avion/drone/aéronef -> aerien
    - train/rail -> ferroviaire
    """
    raw = _norm_token(domaine_mobilite) or _norm_token(type_vehicule) or _norm_token(usage)
    aliases = {
        "route": "routier",
        "routier": "routier",
        "road": "routier",
        "voiture": "routier",
        "auto": "routier",
        "automobile": "routier",
        "vehicule": "routier",
        "vehicule_routier": "routier",
        "moto": "routier",
        "quad": "routier",
        "buggy": "routier",
        "utilitaire": "routier",
        "camion": "routier",

        "nautique": "nautique",
        "marin": "nautique",
        "marine": "nautique",
        "bateau": "nautique",
        "navire": "nautique",
        "drone_marin": "nautique",
        "surface": "nautique",

        "aerien": "aerien",
        "aerial": "aerien",
        "air": "aerien",
        "avion": "aerien",
        "aeronef": "aerien",
        "drone": "aerien",
        "uav": "aerien",

        "ferroviaire": "ferroviaire",
        "rail": "ferroviaire",
        "train": "ferroviaire",

        "stationnaire": "stationnaire",
        "fixe": "stationnaire",
        "generateur": "stationnaire",
        "groupe_electrogene": "stationnaire",

        "autre": "autre",
        "": "autre",
    }
    return aliases.get(raw, "autre")


def normaliser_type_vehicule(type_vehicule: Optional[str] = None, *, usage: Optional[str] = None) -> str:
    raw = _norm_token(type_vehicule) or _norm_token(usage)
    aliases = {
        "auto": "voiture",
        "automobile": "voiture",
        "car": "voiture",
        "voiture": "voiture",
        "moto": "moto",
        "motorcycle": "moto",
        "quad": "quad",
        "buggy": "buggy",
        "utilitaire": "utilitaire",
        "van": "utilitaire",
        "bateau": "bateau",
        "navire": "bateau",
        "drone_marin": "drone_marin",
        "avion": "avion",
        "aeronef": "aeronef",
        "drone": "drone",
        "train": "train",
        "stationnaire": "stationnaire",
        "generateur": "stationnaire",
        "": "autre",
    }
    return aliases.get(raw, raw or "autre")


def normaliser_mode_transmission(
    mode_transmission: Optional[str] = None,
    *,
    domaine_mobilite: Optional[str] = None,
    type_vehicule: Optional[str] = None,
) -> str:
    """
    Normalise la motricité / propulsion.

    Corrections volontaires :
    - propultion -> propulsion
    - intégrale / integral / AWD / 4x4 -> integrale

    Sens :
    - routier : traction = essieu avant moteur ; propulsion = essieu arrière moteur ;
      integrale = plusieurs essieux moteurs.
    - aérien : traction = hélice/réacteur tracteur ; propulsion = poussée arrière.
    - nautique : propulsion = cas normal.
    """
    raw = _norm_token(mode_transmission)
    aliases = {
        "traction": "traction",
        "fwd": "traction",
        "avant": "traction",
        "essieu_avant": "traction",
        "front": "traction",
        "front_wheel_drive": "traction",
        "helice_tractrice": "traction",
        "tracteur": "traction",

        "propulsion": "propulsion",
        "propultion": "propulsion",  # faute fréquente explicitement corrigée
        "rwd": "propulsion",
        "arriere": "propulsion",
        "essieu_arriere": "propulsion",
        "rear": "propulsion",
        "rear_wheel_drive": "propulsion",
        "pusher": "propulsion",
        "poussee": "propulsion",
        "helice_propulsive": "propulsion",

        "integrale": "integrale",
        "integral": "integrale",
        "intégrale": "integrale",
        "awd": "integrale",
        "4x4": "integrale",
        "4wd": "integrale",
        "toutes_roues_motrices": "integrale",
        "quatre_roues_motrices": "integrale",

        "inconnue": "inconnue",
        "": "inconnue",
    }
    if raw in aliases:
        return aliases[raw]

    domaine = normaliser_domaine_mobilite(domaine_mobilite, type_vehicule=type_vehicule)
    if not raw:
        # Pas d'hypothèse métier forte : on signale l'inconnue dans le rapport.
        return "inconnue"
    if domaine == "nautique" and raw in ("helice", "jet", "waterjet"):
        return "propulsion"
    return "inconnue"


def _mobilite_get(cfg: Optional[Mapping[str, Any]], *names: str, default: Any = None) -> Any:
    if not isinstance(cfg, Mapping):
        return default
    for name in names:
        if name in cfg:
            return cfg[name]
    return default


def calculer_demande_mobilite(
    demande: Optional[Mapping[str, Any]] = None,
    *,
    domaine_mobilite: Optional[str] = None,
    type_vehicule: Optional[str] = None,
    usage: Optional[str] = None,
    mode_transmission: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calcule la demande mécanique minimale du vecteur quand les données sont fournies.

    Cette fonction ne remplace pas une simulation véhicule complète : elle produit un
    pré-dimensionnement transparent, avec inconnues explicites.

    Sortie centrale :
    - puissance_mecanique_requise_w : valeur utilisable comme puissance_cible_w
      pour l'architecture thermique, si l'utilisateur ne l'a pas fournie.
    """
    cfg: Mapping[str, Any] = demande or {}
    domaine = normaliser_domaine_mobilite(domaine_mobilite, type_vehicule=type_vehicule, usage=usage)
    vehicule = normaliser_type_vehicule(type_vehicule, usage=usage)
    transmission = normaliser_mode_transmission(
        mode_transmission or _mobilite_get(cfg, "mode_transmission", "transmission", "motricite"),
        domaine_mobilite=domaine,
        type_vehicule=vehicule,
    )

    rapport: Dict[str, Any] = {
        "domaine_mobilite": domaine,
        "type_vehicule": vehicule,
        "mode_transmission": transmission,
        "resultats": {},
        "inconnues": {"impossibles": [], "partielles": []},
        "notes_modele": [],
    }

    def miss(cat: str, nom: str, raison: str) -> None:
        rapport["inconnues"][cat].append({"nom": nom, "raison": raison})

    # Entrées directes : priorité absolue, aucune recomposition.
    p_direct = _mobilite_get(
        cfg,
        "puissance_mecanique_requise_w",
        "puissance_cible_w",
        "puissance_thermique_mecanique_w",
        default=None,
    )
    if p_direct is not None:
        P = _require_positive("puissance_mecanique_requise_w", p_direct, strict=False)
        rapport["resultats"]["puissance_mecanique_requise_w"] = P
        rapport["resultats"]["puissance_mecanique_requise_kw"] = P / 1000.0
        rapport["notes_modele"].append("Puissance mécanique requise fournie directement : aucun modèle de mobilité appliqué.")
        return rapport

    p_kw_direct = _mobilite_get(cfg, "puissance_mecanique_requise_kw", "puissance_cible_kw", default=None)
    if p_kw_direct is not None:
        P = 1000.0 * _require_positive("puissance_mecanique_requise_kw", p_kw_direct, strict=False)
        rapport["resultats"]["puissance_mecanique_requise_w"] = P
        rapport["resultats"]["puissance_mecanique_requise_kw"] = P / 1000.0
        rapport["notes_modele"].append("Puissance mécanique requise fournie directement en kW.")
        return rapport

    eta = _mobilite_get(cfg, "rendement_chaine", "rendement_transmission", "rendement_propulsif_global", default=1.0)
    eta = _require_positive("rendement_chaine", eta, strict=True)
    if eta > 1.0:
        raise ValueError("rendement_chaine doit être <= 1.0.")

    # ------------------------------------------------------------
    # Routier / ferroviaire : roulement + aéro + pente + accélération.
    # ------------------------------------------------------------
    if domaine in ("routier", "ferroviaire"):
        vitesse_ms = _mobilite_get(cfg, "vitesse_ms", default=None)
        if vitesse_ms is None:
            vitesse_kmh = _mobilite_get(cfg, "vitesse_kmh", "vitesse_moyenne_kmh", default=None)
            if vitesse_kmh is not None:
                vitesse_ms = _require_positive("vitesse_kmh", vitesse_kmh, strict=False) / 3.6

        masse = _mobilite_get(cfg, "masse_totale_kg", "masse_kg", default=None)
        if vitesse_ms is None:
            miss("impossibles", "vitesse_ms|vitesse_kmh", "Requis pour calculer la puissance du vecteur routier/ferroviaire.")
        if masse is None:
            miss("impossibles", "masse_totale_kg", "Requise pour calculer roulement, pente et accélération.")

        if vitesse_ms is not None and masse is not None:
            v = _require_positive("vitesse_ms", vitesse_ms, strict=False)
            m = _require_positive("masse_totale_kg", masse, strict=True)
            g = _require_positive("g_ms2", _mobilite_get(cfg, "g_ms2", default=9.80665), strict=True)
            crr = _require_positive("crr", _mobilite_get(cfg, "crr", default=0.0), strict=False)
            pente = _require_finite("pente", _mobilite_get(cfg, "pente", "pente_ratio", default=0.0))
            acceleration = _require_finite("acceleration_ms2", _mobilite_get(cfg, "acceleration_ms2", default=0.0))
            rho = _require_positive("rho_air_kg_m3", _mobilite_get(cfg, "rho_air_kg_m3", default=1.225), strict=True)
            cda = _require_positive("cda_m2", _mobilite_get(cfg, "cda_m2", "cx_s_m2", default=0.0), strict=False)

            f_roulement = m * g * crr
            f_pente = m * g * pente
            f_accel = m * acceleration
            f_aero = 0.5 * rho * cda * v * v
            f_total = f_roulement + f_pente + f_accel + f_aero
            p_roues_w = max(0.0, f_total * v)
            p_meca_w = p_roues_w / eta if eta > 0.0 else float("inf")

            rapport["resultats"].update({
                "vitesse_ms": v,
                "masse_totale_kg": m,
                "force_roulement_n": f_roulement,
                "force_pente_n": f_pente,
                "force_acceleration_n": f_accel,
                "force_aerodynamique_n": f_aero,
                "force_totale_n": f_total,
                "puissance_aux_roues_w": p_roues_w,
                "puissance_mecanique_requise_w": p_meca_w,
                "puissance_mecanique_requise_kw": p_meca_w / 1000.0,
                "consommation_mecanique_kwh_km": (p_meca_w / 1000.0) / (v * 3.6) if v > 0.0 else None,
            })

            # Vérification motricité si les données d'adhérence sont fournies.
            mu = _mobilite_get(cfg, "coefficient_adherence", "mu", default=None)
            rep_av = _mobilite_get(cfg, "repartition_masse_avant", default=None)
            emp = _mobilite_get(cfg, "empattement_m", default=None)
            hcg = _mobilite_get(cfg, "hauteur_cg_m", default=None)
            if mu is not None and rep_av is not None:
                mu = _require_positive("coefficient_adherence", mu, strict=False)
                rep_av = _require_finite("repartition_masse_avant", rep_av)
                if not (0.0 <= rep_av <= 1.0):
                    raise ValueError("repartition_masse_avant doit être dans [0,1].")
                transfert_n = 0.0
                if emp is not None and hcg is not None:
                    emp = _require_positive("empattement_m", emp, strict=True)
                    hcg = _require_positive("hauteur_cg_m", hcg, strict=False)
                    transfert_n = m * acceleration * hcg / emp

                normal_av = m * g * rep_av - transfert_n
                normal_ar = m * g * (1.0 - rep_av) + transfert_n
                if transmission == "traction":
                    f_motrice_max = mu * max(0.0, normal_av)
                elif transmission == "propulsion":
                    f_motrice_max = mu * max(0.0, normal_ar)
                elif transmission == "integrale":
                    f_motrice_max = mu * max(0.0, normal_av + normal_ar)
                else:
                    f_motrice_max = None

                rapport["resultats"]["motricite"] = {
                    "normal_avant_n": normal_av,
                    "normal_arriere_n": normal_ar,
                    "transfert_charge_n": transfert_n,
                    "force_motrice_max_n": f_motrice_max,
                    "force_demandee_n": f_total,
                    "respecte_adherence": None if f_motrice_max is None else f_total <= f_motrice_max + 1e-12,
                }
            else:
                miss("partielles", "adhérence/motricité", "Fournir coefficient_adherence et repartition_masse_avant pour vérifier traction/propulsion/intégrale.")

        if transmission == "inconnue":
            miss("partielles", "mode_transmission", "Traction/propulsion/intégrale non fourni ; l'énergie reste calculable mais pas la motricité.")

    # ------------------------------------------------------------
    # Nautique : résistance imposée ou traînée quadratique.
    # ------------------------------------------------------------
    elif domaine == "nautique":
        vitesse_ms = _mobilite_get(cfg, "vitesse_ms", default=None)
        if vitesse_ms is None:
            vitesse_kmh = _mobilite_get(cfg, "vitesse_kmh", default=None)
            if vitesse_kmh is not None:
                vitesse_ms = _require_positive("vitesse_kmh", vitesse_kmh, strict=False) / 3.6
        force_res = _mobilite_get(cfg, "force_resistance_n", "resistance_hydrodynamique_n", default=None)

        if vitesse_ms is None:
            miss("impossibles", "vitesse_ms|vitesse_kmh", "Requis pour calculer la puissance nautique.")
        if force_res is None:
            rho = _mobilite_get(cfg, "rho_fluide_kg_m3", default=None)
            cd = _mobilite_get(cfg, "coefficient_trainee", "cd", default=None)
            surface = _mobilite_get(cfg, "surface_mouillee_equivalente_m2", "surface_frontale_m2", "surface_m2", default=None)
            if rho is not None and cd is not None and surface is not None and vitesse_ms is not None:
                v = _require_positive("vitesse_ms", vitesse_ms, strict=False)
                force_res = 0.5 * _require_positive("rho_fluide_kg_m3", rho, strict=True) * _require_positive("coefficient_trainee", cd, strict=False) * _require_positive("surface_m2", surface, strict=False) * v * v
                rapport["notes_modele"].append("Résistance nautique estimée par traînée quadratique simplifiée.")
            else:
                miss("impossibles", "force_resistance_n", "Fournir force_resistance_n ou rho_fluide_kg_m3 + coefficient_trainee + surface_m2.")

        if vitesse_ms is not None and force_res is not None:
            v = _require_positive("vitesse_ms", vitesse_ms, strict=False)
            F = _require_positive("force_resistance_n", force_res, strict=False)
            p_prop_w = F * v
            p_meca_w = p_prop_w / eta if eta > 0.0 else float("inf")
            rapport["resultats"].update({
                "vitesse_ms": v,
                "force_resistance_n": F,
                "puissance_propulsive_w": p_prop_w,
                "puissance_mecanique_requise_w": p_meca_w,
                "puissance_mecanique_requise_kw": p_meca_w / 1000.0,
            })
        if transmission == "inconnue":
            rapport["mode_transmission"] = "propulsion"
            rapport["notes_modele"].append("Nautique : sans précision contraire, le terme fonctionnel est propulsion.")

    # ------------------------------------------------------------
    # Aérien : traînée + montée.
    # ------------------------------------------------------------
    elif domaine == "aerien":
        vitesse_ms = _mobilite_get(cfg, "vitesse_ms", default=None)
        if vitesse_ms is None:
            vitesse_kmh = _mobilite_get(cfg, "vitesse_kmh", default=None)
            if vitesse_kmh is not None:
                vitesse_ms = _require_positive("vitesse_kmh", vitesse_kmh, strict=False) / 3.6
        if vitesse_ms is None:
            miss("impossibles", "vitesse_ms|vitesse_kmh", "Requis pour calculer la puissance aérienne.")
        else:
            v = _require_positive("vitesse_ms", vitesse_ms, strict=False)
            rho = _require_positive("rho_air_kg_m3", _mobilite_get(cfg, "rho_air_kg_m3", default=1.225), strict=True)
            cda = _mobilite_get(cfg, "cda_m2", "cx_s_m2", default=None)
            force_trainee = _mobilite_get(cfg, "force_trainee_n", default=None)
            if force_trainee is None:
                if cda is None:
                    miss("impossibles", "cda_m2|force_trainee_n", "Fournir CdA ou force de traînée pour le domaine aérien.")
                    force_trainee = None
                else:
                    force_trainee = 0.5 * rho * _require_positive("cda_m2", cda, strict=False) * v * v

            masse = _mobilite_get(cfg, "masse_totale_kg", "masse_kg", default=None)
            taux_montee = _require_finite("taux_montee_ms", _mobilite_get(cfg, "taux_montee_ms", default=0.0))
            p_montee_w = 0.0
            if masse is not None and taux_montee > 0.0:
                p_montee_w = _require_positive("masse_totale_kg", masse, strict=True) * 9.80665 * taux_montee
            elif taux_montee > 0.0:
                miss("partielles", "masse_totale_kg", "Requise pour calculer la puissance de montée.")

            if force_trainee is not None:
                Fd = _require_positive("force_trainee_n", force_trainee, strict=False)
                p_trainee_w = Fd * v
                p_meca_w = (p_trainee_w + p_montee_w) / eta if eta > 0.0 else float("inf")
                rapport["resultats"].update({
                    "vitesse_ms": v,
                    "force_trainee_n": Fd,
                    "puissance_trainee_w": p_trainee_w,
                    "puissance_montee_w": p_montee_w,
                    "puissance_mecanique_requise_w": p_meca_w,
                    "puissance_mecanique_requise_kw": p_meca_w / 1000.0,
                })

        if transmission == "inconnue":
            miss("partielles", "mode_transmission", "Préciser traction ou propulsion pour localiser l'hélice/réacteur, même si la puissance reste calculable.")

    # ------------------------------------------------------------
    # Stationnaire / autre : puissance directe requise.
    # ------------------------------------------------------------
    else:
        miss("impossibles", "puissance_mecanique_requise_w", "Pour stationnaire/autre, fournir directement la puissance mécanique cible.")

    # Déduplication locale.
    for cat in ("impossibles", "partielles"):
        seen: set[Tuple[str, str]] = set()
        dedup: List[Dict[str, str]] = []
        for it in rapport["inconnues"][cat]:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                dedup.append(dict(it))
        rapport["inconnues"][cat] = dedup

    return rapport

def estimer_pme_depuis_couple_et_cylindree(
    couple_nm: float,
    cylindree_totale_m3: float,
    *,
    temps_moteur: int = 4,
) -> float:
    """
    Estime la PME (BMEP) à partir du couple et de la cylindrée totale.

      - 4T : BMEP = 4π T / Vd
      - 2T : BMEP = 2π T / Vd
    """
    T = _require_finite("couple_nm", couple_nm)
    Vd = _require_positive("cylindree_totale_m3", cylindree_totale_m3, strict=True)
    if temps_moteur == 4:
        return float((4.0 * math.pi * T) / Vd)
    if temps_moteur == 2:
        return float((2.0 * math.pi * T) / Vd)
    raise ValueError("temps_moteur doit être 2 ou 4.")


def estimer_pme_depuis_puissance_et_cylindree(
    puissance_mecanique_w: float,
    cylindree_totale_m3: float,
    regime_tr_min: float,
    *,
    temps_moteur: int = 4,
    rendement_mecanique: float = 1.0,
) -> float:
    """
    Estime la PME (BMEP) à partir de P, Vd, régime et rendement.

      PME = P / (Vd * f * eta_m)
    """
    P = _require_positive("puissance_mecanique_w", puissance_mecanique_w, strict=False)
    Vd = _require_positive("cylindree_totale_m3", cylindree_totale_m3, strict=True)
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    eta = _require_positive("rendement_mecanique", rendement_mecanique, strict=True)

    if temps_moteur == 4:
        f = n / 120.0
    elif temps_moteur == 2:
        f = n / 60.0
    else:
        raise ValueError("temps_moteur doit être 2 ou 4.")

    if Vd * f * eta <= 0.0:
        return 0.0
    return float(P / (Vd * f * eta))


# ============================================================
# Imports des modules architecture (robustes)
# ============================================================

import importlib
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))


def _import_attr(candidates: Sequence[str], attr: str, *, required: bool = True) -> Any:
    """
    Importe un attribut depuis plusieurs chemins possibles.

    Chemins supportés :
    - backend.components.architecture.modules.*
    - backend.components.architechture.modules.*  # compatibilité avec l'ancien nom fautif
    - backend.modules.architecture.*
    - module local dans le même dossier
    """
    errors: list[str] = []
    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
            return getattr(module, attr)
        except Exception as exc:
            errors.append(f"{module_name}.{attr}: {exc}")
    if required:
        raise ImportError("Impossible d'importer " + attr + " depuis: " + " | ".join(errors))
    return None


def _module_candidates(name: str) -> list[str]:
    return [
        f"backend.components.architecture.modules.{name}",
        f"backend.components.architechture.modules.{name}",
        f"backend.modules.architecture.{name}",
        name,
    ]


def _piece_candidates(name: str) -> list[str]:
    return [
        f"backend.components.architecture.pieces.{name}",
        f"backend.components.architechture.pieces.{name}",
        f"backend.modules.architecture.pieces.{name}",
        name,
    ]


# Modules principaux — si un module manque, on installe un fallback mathématique explicite.
try:
    calcul_cout_maintenance_estime = _import_attr(
        _module_candidates("calcul_cout_maintenance_archard"), "calcul_cout_maintenance_estime"
    )
    calcul_cout_maintenance_estime_auto_prix = _import_attr(
        _module_candidates("calcul_cout_maintenance_archard"), "calcul_cout_maintenance_estime_auto_prix", required=False
    )
except Exception:
    def calcul_cout_maintenance_estime(
        duree_usage_h: float,
        duree_vie_joint_base_h: float,
        charge_nominale_n: float,
        charge_actuelle_n: float,
        nb_joints_base: int,
        nb_joints_actuel: int,
        cout_inter_eur: float,
    ) -> float:
        beta = 1.5
        if charge_actuelle_n <= 0:
            return 0.0
        duree_vie_estimee = float(duree_vie_joint_base_h) * ((float(charge_nominale_n) / float(charge_actuelle_n)) ** beta)
        if duree_vie_estimee <= 0.0 or not math.isfinite(duree_vie_estimee):
            raise ValueError("Durée de vie estimée non valide.")
        return (float(duree_usage_h) / duree_vie_estimee) * float(cout_inter_eur) * (int(nb_joints_actuel) / max(1, int(nb_joints_base)))

    def calcul_cout_maintenance_estime_auto_prix(*args: Any, **kwargs: Any) -> float:
        kwargs.pop("activer_scraping", None)
        kwargs.pop("urls_prix_joints", None)
        kwargs.pop("urls_main_oeuvre", None)
        kwargs.pop("cache_path", None)
        kwargs.pop("cache_ttl_h", None)
        kwargs.pop("timeout_s", None)
        kwargs.pop("temps_intervention_h", None)
        kwargs.pop("cout_arret_eur", None)
        kwargs.pop("cout_consommables_eur", None)
        kwargs.pop("strict_scraping", None)
        return calcul_cout_maintenance_estime(*args, **kwargs)

try:
    calcul_bore_max_admissible = _import_attr(
        _module_candidates("calcul_cylindree_admissible"), "calcul_bore_max_admissible"
    )
    calcul_cylindree_unit_max = _import_attr(
        _module_candidates("calcul_cylindree_admissible"), "calcul_cylindree_unit_max"
    )
except Exception:
    def calcul_bore_max_admissible(vitesse_piston_max_ms: float, regime_tr_min: float, ratio_course_alesage_max: float) -> float:
        n = float(regime_tr_min)
        if n == 0.0:
            return 0.0
        return (30.0 * float(vitesse_piston_max_ms) / n) / float(ratio_course_alesage_max)

    def calcul_cylindree_unit_max(bore_max_m: float, ratio_course_alesage_max: float) -> float:
        return (math.pi / 4.0) * (float(bore_max_m) ** 3) * float(ratio_course_alesage_max)

try:
    calcul_cylindree_totale_requise = _import_attr(
        _module_candidates("calcul_cylindree_totale"), "calcul_cylindree_totale_requise"
    )
except Exception:
    def calcul_cylindree_totale_requise(
        puissance_mecanique_h: float,
        pme_pa: float,
        frequence_cycles_hz: float,
        rendement_mecanique: float = 1.0,
    ) -> float:
        return float(puissance_mecanique_h) / (float(rendement_mecanique) * float(pme_pa) * float(frequence_cycles_hz))

try:
    calcul_nombre_cylindres_min = _import_attr(
        _module_candidates("calcul_nombre_cylindres_min"), "calcul_nombre_cylindres_min"
    )
except Exception:
    def calcul_nombre_cylindres_min(cylindree_totale_m3: float, cylindree_unitaire_max_m3: float) -> int:
        if cylindree_unitaire_max_m3 <= 0.0:
            return 999
        return int(math.ceil(float(cylindree_totale_m3) / float(cylindree_unitaire_max_m3)))

try:
    choix_architecture_optimale = _import_attr(
        _module_candidates("choix_architecture_optimale"), "choix_architecture_optimale"
    )
    evaluer_architecture = _import_attr(
        _module_candidates("choix_architecture_optimale"), "evaluer_architecture"
    )
except Exception:
    def _architecture_possible_fallback(type_arch: str, nb_cylindres: int) -> bool:
        if type_arch == "L":
            return True
        if type_arch in ("V", "Boxer"):
            return nb_cylindres % 2 == 0
        if type_arch == "W":
            return nb_cylindres >= 6 and (nb_cylindres % 3 == 0 or nb_cylindres % 4 == 0)
        if type_arch == "Etoile":
            return nb_cylindres >= 3
        return False

    def evaluer_architecture(
        type_arch: str,
        nb_cylindres: int,
        longueur_dispo_m: float,
        largeur_dispo_m: float,
        cout_maintenance_estime: float = 0.0,
    ) -> tuple[float, bool]:
        if not _architecture_possible_fallback(type_arch, int(nb_cylindres)):
            return 9999.0, False
        L_pkg, W_pkg = _estimer_packaging_simple(type_arch, int(nb_cylindres), pas_cylindre_m=0.15, largeur_base_m=0.40)
        valide = L_pkg <= float(longueur_dispo_m) and W_pkg <= float(largeur_dispo_m)
        complexite = _architecture_complexity_factor(type_arch)
        score = (L_pkg / float(longueur_dispo_m)) + (W_pkg / float(largeur_dispo_m)) + 0.5 * complexite + float(cout_maintenance_estime) / 1000.0
        if not valide:
            score += 1000.0
        return float(score), bool(valide)

    def choix_architecture_optimale(nb_cylindres: int, L_max: float, W_max: float, cout_maintenance_estime: float = 0.0) -> str:
        best_arch = "Inconnue"
        best_score = float("inf")
        for arch in ("L", "V", "W", "Etoile", "Boxer"):
            score, ok = evaluer_architecture(arch, nb_cylindres, L_max, W_max, cout_maintenance_estime)
            if ok and score < best_score:
                best_score = score
                best_arch = arch
        return best_arch

try:
    resoudre_architecture_globale = _import_attr(
        _module_candidates("resolution_globale_architecture"), "resoudre_architecture_globale"
    )
except Exception:
    def resoudre_architecture_globale(
        puissance_cible_w: float,
        regime_tr_min: float,
        pme_pa: float,
        vitesse_piston_max_ms: float,
        L_max_m: float,
        W_max_m: float,
        horizon_usage_h: float = 20000.0,
    ) -> dict[str, Any]:
        arch = Architecture()
        rep = arch.analyser(
            puissance_cible_w=puissance_cible_w,
            regime_tr_min=regime_tr_min,
            pme_pa=pme_pa,
            vitesse_piston_max_ms=vitesse_piston_max_ms,
            longueur_dispo_m=L_max_m,
            largeur_dispo_m=W_max_m,
            horizon_usage_h=horizon_usage_h,
        )
        best = rep.get("meilleur") or {}
        return {
            "N_cyl": best.get("N_cyl"),
            "Architecture": best.get("architecture"),
            "Score": best.get("score_global"),
            "Cout_Maint_Estime": best.get("cout_maintenance_eur"),
            "Bore_mm": best.get("bore_mm"),
            "Course_mm": best.get("course_mm"),
            "Ratio_Sur_B": best.get("ratio_S_B"),
        }


# Pièces architecture : import réel si disponible, sinon classes minimales non bloquantes.
try:
    VilebrequinArch = _import_attr(_piece_candidates("vilebrequin_arch"), "VilebrequinArch")
except Exception:
    @dataclass
    class VilebrequinArch:  # type: ignore[no-redef]
        architecture: str = "L"
        nb_cylindres: int = 4
        pas_cylindre_m: float = 0.15
        diametre_journal_m: float = 0.05

        def analyser(self) -> Dict[str, Any]:
            f = {"L": 1.0, "V": 0.55, "W": 0.35, "Etoile": 0.2, "Boxer": 0.6}.get(self.architecture, 1.0)
            if self.architecture == "V":
                nb_manetons = math.ceil(self.nb_cylindres / 2)
            elif self.architecture == "W":
                nb_manetons = math.ceil(self.nb_cylindres / 3)
            elif self.architecture == "Etoile":
                nb_manetons = 1
            else:
                nb_manetons = self.nb_cylindres
            return {
                "piece": "vilebrequin_arch",
                "resultats": {
                    "longueur_vilebrequin_m": self.nb_cylindres * self.pas_cylindre_m * f,
                    "nb_manetons_estimes": nb_manetons,
                    "nb_paliers_estimes": nb_manetons + 1,
                    "complexite_usinage": "Haute" if self.architecture in ["V", "W", "Etoile"] else "Standard",
                },
                "inconnues": {"impossibles": [], "partielles": []},
            }

try:
    BlocMoteurArch = _import_attr(_piece_candidates("bloc_moteur_arch"), "BlocMoteurArch")
except Exception:
    @dataclass
    class BlocMoteurArch:  # type: ignore[no-redef]
        architecture: str = "L"
        nb_cylindres: int = 4
        alesage_m: float = 0.1
        course_m: float = 0.1

        def analyser(self) -> Dict[str, Any]:
            f_m = {"L": 1.0, "V": 1.25, "W": 1.5, "Etoile": 1.1, "Boxer": 1.3}.get(self.architecture, 1.0)
            f_w = {"L": 1.0, "V": 1.8, "W": 2.2, "Etoile": 2.5, "Boxer": 2.0}.get(self.architecture, 1.0)
            f_h = {"L": 1.0, "V": 0.8, "W": 0.75, "Etoile": 2.5, "Boxer": 0.5}.get(self.architecture, 1.0)
            return {
                "piece": "bloc_moteur_arch",
                "resultats": {
                    "masse_bloc_estimee_kg": self.nb_cylindres * 10.0 * f_m,
                    "largeur_hors_tout_m": 0.4 * f_w,
                    "hauteur_hors_tout_m": 0.5 * f_h,
                    "nb_plans_de_joint_culasse": 1 if self.architecture == "L" else (2 if self.architecture in ["V", "Boxer"] else 3),
                },
                "inconnues": {"impossibles": [], "partielles": []},
            }

try:
    CulasseArch = _import_attr(_piece_candidates("culasse_arch"), "CulasseArch")
except Exception:
    @dataclass
    class CulasseArch:  # type: ignore[no-redef]
        architecture: str = "L"
        nb_cylindres: int = 4
        nb_soupapes_par_cyl: int = 4

        def analyser(self) -> Dict[str, Any]:
            if self.architecture in ["V", "Boxer"]:
                nb_bancs = 2
            elif self.architecture == "W":
                nb_bancs = 3
            elif self.architecture == "Etoile":
                nb_bancs = self.nb_cylindres
            else:
                nb_bancs = 1
            nb_aac = 2 if self.architecture == "L" else (4 if self.architecture in ["V", "Boxer"] else 6)
            return {
                "piece": "culasse_arch",
                "resultats": {
                    "nb_culasses": nb_bancs,
                    "nb_arbres_a_cames_totaux": nb_aac,
                    "complexite_distribution": "Elevée" if nb_bancs > 1 else "Standard",
                    "nb_soupapes_totales": self.nb_cylindres * self.nb_soupapes_par_cyl,
                },
                "inconnues": {"impossibles": [], "partielles": []},
            }


# Solveur fin multi-cas : optionnel, car il dépend des modules moteur_thermique/cycle pression.
resoudre_architecture_fine_multicas = _import_attr(
    _module_candidates("architecture_fine_multicas"), "resoudre_architecture_fine_multicas", required=False
)
ParametresPackagingArchitecture = _import_attr(
    _module_candidates("architecture_fine_multicas"), "ParametresPackagingArchitecture", required=False
)
ParametresMasseArchitecture = _import_attr(
    _module_candidates("architecture_fine_multicas"), "ParametresMasseArchitecture", required=False
)
ParametresPertesArchitecture = _import_attr(
    _module_candidates("architecture_fine_multicas"), "ParametresPertesArchitecture", required=False
)
ParametresFiabiliteArchitecture = _import_attr(
    _module_candidates("architecture_fine_multicas"), "ParametresFiabiliteArchitecture", required=False
)
ParametresScoreArchitecture = _import_attr(
    _module_candidates("architecture_fine_multicas"), "ParametresScoreArchitecture", required=False
)
OptionsExplorationArchitecture = _import_attr(
    _module_candidates("architecture_fine_multicas"), "OptionsExplorationArchitecture", required=False
)


# ============================================================
# Helpers robustesse + gestion des inconnues
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


def _require_int_positive(name: str, x: Any, *, strict: bool = True) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    ok = x > 0 if strict else x >= 0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return int(x)


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


def _hz_cycles(regime_tr_min: float, temps_moteur: int) -> float:
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    if temps_moteur == 4:
        return n / 120.0
    if temps_moteur == 2:
        return n / 60.0
    raise ValueError("temps_moteur doit être 2 ou 4.")


def _course_max_depuis_vitesse_piston(vitesse_piston_max_ms: float, regime_tr_min: float) -> float:
    U = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    n = _require_positive("regime_tr_min", regime_tr_min, strict=True)
    if n == 0.0:
        return 0.0
    return (30.0 * U) / n


def _bore_et_course_depuis_volume_et_ratio(volume_unitaire_m3: float, ratio_s_b: float) -> Tuple[float, float]:
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    r = _require_positive("ratio_s_b", ratio_s_b, strict=True)
    if V == 0.0:
        return 0.0, 0.0
    B = ((4.0 * V) / (math.pi * r)) ** (1.0 / 3.0)
    S = r * B
    return float(B), float(S)


def _ratio_max_compatible_vitesse_piston(volume_unitaire_m3: float, course_max_m: float) -> float:
    V = _require_positive("volume_unitaire_m3", volume_unitaire_m3, strict=False)
    S_max = _require_positive("course_max_m", course_max_m, strict=False)
    if V == 0.0:
        return float("inf")
    K = (4.0 * V / math.pi) ** (1.0 / 3.0)
    if K <= 0.0:
        return 0.0
    return float((S_max / K) ** 1.5)


def _surface_piston_m2(bore_m: float) -> float:
    B = _require_positive("bore_m", bore_m, strict=False)
    if B == 0.0:
        return 0.0
    return float(math.pi * (B**2) / 4.0)


def _estimer_packaging_simple(
    architecture: str,
    nb_cyl: int,
    *,
    pas_cylindre_m: float,
    largeur_base_m: float,
) -> Tuple[float, float]:
    nb = _require_int_positive("nb_cyl", nb_cyl, strict=True)
    pas = _require_positive("pas_cylindre_m", pas_cylindre_m, strict=True)
    w0 = _require_positive("largeur_base_m", largeur_base_m, strict=True)

    arch = str(architecture)
    if arch == "L":
        return nb * pas, w0
    if arch == "V":
        return (nb / 2.0) * pas, 1.5 * w0
    if arch == "W":
        return (nb / 3.0) * pas, 2.0 * w0
    if arch == "Etoile":
        return 1.5 * pas, 2.5 * w0
    if arch == "Boxer":
        return (nb / 2.0) * pas, 2.1 * w0
    return float("nan"), float("nan")


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    if not _is_finite(a) or not _is_finite(b):
        return None
    if float(b) == 0.0:
        return None
    return float(a) / float(b)


def _architecture_complexity_factor(arch: str) -> float:
    mapping = {
        "L": 1.00,
        "V": 1.10,
        "W": 1.25,
        "Etoile": 1.35,
        "Boxer": 1.08,
    }
    return float(mapping.get(str(arch), 1.50))


def _appeler_choix_architecture_optimale(
    nb_cyl: int,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    cout_maintenance_score: Optional[float],
) -> str:
    last_err: Optional[Exception] = None
    essais = [
        (nb_cyl, longueur_dispo_m, largeur_dispo_m, cout_maintenance_score),
        (nb_cyl, longueur_dispo_m, largeur_dispo_m),
    ]
    for args in essais:
        try:
            return str(choix_architecture_optimale(*args))
        except TypeError as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return "Inconnue"


def _appeler_evaluer_architecture(
    arch: str,
    nb_cyl: int,
    longueur_dispo_m: float,
    largeur_dispo_m: float,
    cout_maintenance_score: Optional[float],
) -> Tuple[float, bool]:
    last_err: Optional[Exception] = None
    essais = [
        (arch, nb_cyl, longueur_dispo_m, largeur_dispo_m, cout_maintenance_score),
        (arch, nb_cyl, longueur_dispo_m, largeur_dispo_m),
    ]
    for args in essais:
        try:
            out = evaluer_architecture(*args)
            if isinstance(out, tuple) and len(out) >= 2:
                return float(out[0]), bool(out[1])
            if isinstance(out, (int, float)):
                return float(out), True
        except TypeError as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return float("inf"), False


def _estimer_indice_maintenance(*, nb_cyl: int, architecture: str) -> float:
    return float(nb_cyl) * _architecture_complexity_factor(architecture)


def _estimer_masse_relative(*, nb_cyl: int, bore_m: float, course_m: float, architecture: str) -> float:
    volume_geom = float(nb_cyl) * max(0.0, float(bore_m)) ** 2 * max(0.0, float(course_m))
    f_arch = _architecture_complexity_factor(architecture)
    return float(volume_geom * f_arch)


def _estimer_cout_matiere_relatif(*, masse_relative: float, architecture: str) -> float:
    return float(masse_relative * _architecture_complexity_factor(architecture))


def _estimer_indice_fiabilite(
    *,
    nb_cyl: int,
    architecture: str,
    ratio_s_b: float,
    charge_moy_piston_n: float,
    charge_ref_n: float,
) -> float:
    charge_ratio = _safe_div(charge_moy_piston_n, charge_ref_n)
    charge_ratio = 1.0 if charge_ratio is None else max(0.0, charge_ratio)
    return float(
        _architecture_complexity_factor(architecture)
        * (1.0 + 0.10 * max(0.0, nb_cyl - 1))
        * (1.0 + 0.25 * max(0.0, ratio_s_b - 1.0))
        * charge_ratio
    )


def _estimer_indice_rendement_relatif(*, nb_cyl: int, architecture: str, ratio_s_b: float) -> float:
    return float(
        1.0
        + 0.06 * max(0.0, nb_cyl - 1)
        + 0.15 * max(0.0, ratio_s_b - 1.0)
        + 0.10 * (_architecture_complexity_factor(architecture) - 1.0)
    )


def _normaliser_sur_candidats(lignes: List[Dict[str, Any]], champ: str, *, sens: str = "min") -> None:
    valeurs: List[float] = []
    for row in lignes:
        v = row.get(champ)
        if _is_finite(v):
            valeurs.append(float(v))
    if not valeurs:
        for row in lignes:
            row[f"{champ}_norm"] = None
        return

    vmin = min(valeurs)
    vmax = max(valeurs)
    if abs(vmax - vmin) <= 1e-15:
        for row in lignes:
            row[f"{champ}_norm"] = 0.0
        return

    for row in lignes:
        v = row.get(champ)
        if not _is_finite(v):
            row[f"{champ}_norm"] = None
            continue
        x = (float(v) - vmin) / (vmax - vmin)
        if sens == "max":
            x = 1.0 - x
        row[f"{champ}_norm"] = float(max(0.0, min(1.0, x)))


def _score_multi_criteres(
    row: Dict[str, Any],
    *,
    poids_maintenance: float,
    poids_masse: float,
    poids_cout_matiere: float,
    poids_compacite: float,
    poids_fiabilite: float,
    poids_rendement: float,
) -> float:
    def g(name: str) -> float:
        v = row.get(name)
        if v is None or not _is_finite(v):
            return 1.0
        return float(v)

    score = 0.0
    score += float(poids_maintenance) * g("cout_maintenance_score_eur_norm")
    score += float(poids_masse) * g("masse_relative_norm")
    score += float(poids_cout_matiere) * g("cout_matiere_relatif_norm")
    score += float(poids_compacite) * g("compacite_score_norm")
    score += float(poids_fiabilite) * g("fiabilite_indice_norm")
    score += float(poids_rendement) * g("rendement_indice_norm")
    return float(score)


def _make_fine_options(
    base: Optional[Any],
    *,
    architectures_autorisees: Optional[List[ArchitectureType]],
    architecture_forcee: Optional[ArchitectureType],
    delta_exploration: int,
    n_max_absolu: int,
) -> Optional[Any]:
    if OptionsExplorationArchitecture is None:
        return None

    archs: Tuple[str, ...]
    if architecture_forcee is not None:
        archs = (str(architecture_forcee),)
    elif architectures_autorisees:
        archs = tuple(str(a) for a in architectures_autorisees)
    else:
        archs = getattr(base, "architectures", ("L", "V", "W", "Etoile", "Boxer")) if base is not None else (
            "L", "V", "W", "Etoile", "Boxer"
        )

    if base is not None:
        return replace(
            base,
            architectures=archs,
            delta_cylindres=int(delta_exploration),
            n_max_absolu=int(n_max_absolu),
        )

    return OptionsExplorationArchitecture(
        architectures=archs,
        delta_cylindres=int(delta_exploration),
        n_max_absolu=int(n_max_absolu),
    )


def _convertir_solution_fine_vers_rapport(
    solution: Dict[str, Any],
    rapport: Dict[str, Any],
    *,
    poids_maintenance: float,
    poids_masse: float,
    poids_cout_matiere: float,
    poids_compacite: float,
    poids_fiabilite: float,
    poids_rendement: float,
) -> Dict[str, Any]:
    hypo = solution.get("hypotheses", {})
    rapport["mode_analyse"] = "fine_multicas"
    rapport["solution_fine_multicas"] = solution
    rapport["cylindree"]["cylindree_totale_m3"] = hypo.get("cylindree_totale_requise_m3")
    rapport["cylindree"]["cylindree_totale_cc"] = hypo.get("cylindree_totale_requise_cm3")
    rapport["cylindree"]["N_min"] = hypo.get("n_min")
    rapport["contraintes_admissibles"]["course_max_m"] = hypo.get("course_max_m")
    rapport["contraintes_admissibles"]["rpm_max_considere"] = hypo.get("rpm_max_considere")

    candidats = solution.get("candidats_tries", []) or []
    converted: List[Dict[str, Any]] = []
    best_by_arch: Dict[str, Dict[str, Any]] = {}

    for cand in candidats:
        gabarit = cand.get("gabarit", {}) or {}
        masse = cand.get("masse", {}) or {}
        perf = cand.get("performance_moyenne", {}) or {}
        fiab = cand.get("fiabilite_globale", {}) or {}
        maint = cand.get("maintenance", {}) or {}
        row = {
            "N_cyl": int(cand.get("nb_cylindres", 0)),
            "architecture": str(cand.get("architecture", "Inconnue")),
            "score_global": float(cand.get("score", float("inf"))),
            "score_multi_criteres": float(cand.get("score", float("inf"))),
            "score_module_externe": None,
            "valide": bool(cand.get("valide_packaging", False)),
            "cout_maintenance_eur": float(maint.get("cout_max_estime_eur", 0.0)),
            "cout_maintenance_score_eur": float(maint.get("cout_max_estime_eur", 0.0)),
            "maintenance_indice": float(maint.get("cout_max_estime_eur", 0.0)),
            "masse_relative": float(masse.get("masse_totale_estimee_kg", float("nan"))),
            "cout_matiere_relatif": float(masse.get("masse_totale_estimee_kg", float("nan"))),
            "fiabilite_indice": float(fiab.get("severite_dimensionnante", float("nan"))),
            "rendement_indice": 1.0 - float(perf.get("eta_globale_proxy_moyenne", 0.0)),
            "compacite_score": max(
                float(gabarit.get("longueur_m", 0.0)),
                float(gabarit.get("largeur_m", 0.0)),
                float(gabarit.get("hauteur_m", 0.0)),
            ),
            "cylindree_tot_cc": float(cand.get("cylindree_totale_cm3", 0.0)),
            "cylindree_unit_cc": float(cand.get("cylindree_unitaire_cm3", 0.0)),
            "bore_mm": float(cand.get("alesage_m", 0.0)) * 1000.0,
            "course_mm": float(cand.get("course_m", 0.0)) * 1000.0,
            "ratio_S_B": float(cand.get("ratio_course_alesage", float("nan"))),
            "charge_moy_piston_N": float(cand.get("pression_dimensionnante_pa", 0.0)) * _surface_piston_m2(float(cand.get("alesage_m", 0.0))),
            "L_pkg_m_estimee": float(gabarit.get("longueur_m", float("nan"))),
            "W_pkg_m_estimee": float(gabarit.get("largeur_m", float("nan"))),
            "H_pkg_m_estimee": float(gabarit.get("hauteur_m", float("nan"))),
            "masse_estimee_kg": float(masse.get("masse_totale_estimee_kg", float("nan"))),
            "eta_globale_proxy": float(perf.get("eta_globale_proxy_moyenne", float("nan"))),
            "cas_dimensionnant": fiab.get("cas_dimensionnant"),
            "organe_dimensionnant": fiab.get("organe_dimensionnant"),
            "pression_dimensionnante_pa": float(cand.get("pression_dimensionnante_pa", float("nan"))),
            "torque_max_global_nm": float(cand.get("torque_max_global_nm", float("nan"))),
            "details_fins": cand,
        }
        converted.append(row)
        arch = row["architecture"]
        if arch not in best_by_arch or float(row["score_global"]) < float(best_by_arch[arch]["score_global"]):
            best_by_arch[arch] = row

    rapport["exploration"] = converted
    rapport["meilleurs_par_architecture"] = best_by_arch

    best = solution.get("meilleur_candidat")
    if isinstance(best, dict):
        best_arch = str(best.get("architecture", ""))
        rapport["meilleur"] = best_by_arch.get(best_arch)

    rapport["criteres_conception"] = {
        "poids_maintenance": poids_maintenance,
        "poids_masse": poids_masse,
        "poids_cout_matiere": poids_cout_matiere,
        "poids_compacite": poids_compacite,
        "poids_fiabilite": poids_fiabilite,
        "poids_rendement": poids_rendement,
    }

    rapport["notes_modele"].append(
        "Mode fin multi-cas actif : la solution tient compte de cas de charge explicites, d'un cycle mécanique et d'indices de masse/rendement/fiabilité plus riches."
    )
    rapport["notes_modele"].append(
        "En mode fin, le poids 'coût matière' est replié sur la masse estimée faute de modèle industriel séparé dans le solveur multi-cas."
    )
    attention = hypo.get("attention")
    if attention:
        rapport["notes_modele"].append(str(attention))
    return rapport


# ============================================================
# Composant Architecture
# ============================================================

@dataclass(frozen=True)
class Architecture:
    """
    Analyse et pré-dimensionnement architecture moteur.

    Deux niveaux d'analyse :
    - simple historique : rapide, conservatif, compatible avec les appels existants ;
    - fin multi-cas : activé si cas_de_charge + taux_compression sont fournis.
    """

    # cycle moteur : 4T ou 2T
    temps_moteur: int = 4

    # rendement mécanique
    rendement_mecanique: float = 0.85

    # contrainte géométrique S/B max
    ratio_course_alesage_max: float = 1.2

    # maintenance (modèle joints)
    duree_vie_joint_base_h: float = 5000.0
    joints_par_cyl: int = 3
    cout_intervention_base_eur: float = 2000.0
    beta_wear_model: str = "1.5 (dans le module)"

    # exploration N
    delta_exploration: int = 6
    min_exploration: int = 16
    n_max_absolu: int = 24

    # packaging "informatif"
    pas_cylindre_m: float = 0.15
    largeur_base_m: float = 0.40

    # scraping optionnel
    activer_scraping_prix: bool = False
    urls_prix_joints: Optional[List[str]] = None
    urls_main_oeuvre: Optional[List[str]] = None
    cache_path_prix: str = "backend/.cache/prix_maintenance.json"
    cache_ttl_h: float = 168.0
    timeout_scraping_s: float = 6.0
    temps_intervention_h: float = 1.0
    cout_arret_eur: float = 0.0
    cout_consommables_eur: float = 0.0
    strict_scraping: bool = False

    # solveur fin (paramètres avancés optionnels)
    params_packaging_fins: Optional[Any] = None
    params_masse_fins: Optional[Any] = None
    params_pertes_fins: Optional[Any] = None
    params_fiabilite_fins: Optional[Any] = None
    options_fines: Optional[Any] = None

    # Pieces optionnelles
    piece_vilebrequin: Optional[VilebrequinArch] = None
    piece_bloc: Optional[BlocMoteurArch] = None
    piece_culasse: Optional[CulasseArch] = None

    # ------------------------------------------------------------
    # Wrapper : usage/profil -> appel analyser()
    # ------------------------------------------------------------
    def recommander_pour_profil(
        self,
        profil: ProfilUsageMoteur,
        *,
        puissance_cible_w: Optional[float] = None,
        regime_tr_min: Optional[float] = None,
        pme_pa: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not isinstance(profil, ProfilUsageMoteur):
            raise ValueError("profil doit être une instance de ProfilUsageMoteur.")
        return self.analyser(
            puissance_cible_w=puissance_cible_w,
            regime_tr_min=regime_tr_min,
            pme_pa=pme_pa,
            vitesse_piston_max_ms=profil.vitesse_piston_max_ms,
            longueur_dispo_m=profil.longueur_dispo_m,
            largeur_dispo_m=profil.largeur_dispo_m,
            hauteur_dispo_m=profil.hauteur_dispo_m,
            horizon_usage_h=profil.horizon_usage_h,
            taux_compression=profil.taux_compression,
            cas_de_charge=list(profil.cas_de_charge) if profil.cas_de_charge else None,
            ordre_allumage_map=dict(profil.ordre_allumage_map) if profil.ordre_allumage_map else None,
            ponderations_cas=dict(profil.ponderations_cas) if profil.ponderations_cas else None,
            domaine_mobilite=profil.domaine_mobilite,
            type_vehicule=profil.type_vehicule,
            mode_transmission=profil.mode_transmission,
            demande_mobilite=dict(profil.demande_mobilite) if profil.demande_mobilite else None,
            architectures_autorisees=list(profil.architectures_autorisees) if profil.architectures_autorisees else None,
            architecture_forcee=profil.architecture_forcee,
            poids_maintenance=profil.poids_maintenance,
            poids_masse=profil.poids_masse,
            poids_cout_matiere=profil.poids_cout_matiere,
            poids_compacite=profil.poids_compacite,
            poids_fiabilite=profil.poids_fiabilite,
            poids_rendement=profil.poids_rendement,
            usage=profil.usage,
            commentaire_usage=profil.commentaire,
        )

    def analyser(
        self,
        *,
        puissance_cible_w: Optional[float] = None,
        regime_tr_min: Optional[float] = None,
        pme_pa: Optional[float] = None,
        vitesse_piston_max_ms: Optional[float] = None,
        longueur_dispo_m: Optional[float] = None,
        largeur_dispo_m: Optional[float] = None,
        hauteur_dispo_m: Optional[float] = None,
        horizon_usage_h: float = 20000.0,
        taux_compression: Optional[float] = None,
        cas_de_charge: Optional[List[Any]] = None,
        ordre_allumage_map: Optional[Mapping[int, Sequence[int] | str]] = None,
        ponderations_cas: Optional[Mapping[str, float]] = None,
        activer_mode_fine: bool = True,

        # Couche mobilité / vecteur : si puissance_cible_w est absente,
        # le script peut la déduire d'une demande routière/nautique/aérienne.
        domaine_mobilite: Optional[str] = None,
        type_vehicule: Optional[str] = None,
        mode_transmission: Optional[str] = None,
        demande_mobilite: Optional[Mapping[str, Any]] = None,

        # contraintes / préférences architecture
        architectures_autorisees: Optional[List[ArchitectureType]] = None,
        architecture_forcee: Optional[ArchitectureType] = None,

        # pondérations explicites
        poids_maintenance: float = 1.0,
        poids_masse: float = 1.0,
        poids_cout_matiere: float = 1.0,
        poids_compacite: float = 1.0,
        poids_fiabilite: float = 1.0,
        poids_rendement: float = 1.0,

        # métadonnées
        usage: Optional[UsageType] = None,
        commentaire_usage: str = "",
    ) -> Dict[str, Any]:

        for nom, val in {
            "poids_maintenance": poids_maintenance,
            "poids_masse": poids_masse,
            "poids_cout_matiere": poids_cout_matiere,
            "poids_compacite": poids_compacite,
            "poids_fiabilite": poids_fiabilite,
            "poids_rendement": poids_rendement,
        }.items():
            if not _is_finite(val) or float(val) < 0.0:
                raise ValueError(f"{nom} doit être un nombre fini >= 0.")

        rapport: Dict[str, Any] = {
            "mode_analyse": "simple",
            "entrees": {},
            "cycles": {},
            "cylindree": {},
            "contraintes_admissibles": {},
            "maintenance": {},
            "criteres_conception": {},
            "exploration": [],
            "meilleur": None,
            "meilleurs_par_architecture": {},
            "solution_module_globale": None,
            "solution_fine_multicas": None,
            "mobilite": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # Couche mobilité : normalisation domaine/type/transmission et
        # dérivation éventuelle de la puissance cible.
        # ------------------------------------------------------------
        rapport_mobilite: Optional[Dict[str, Any]] = None
        if (
            demande_mobilite is not None
            or domaine_mobilite is not None
            or type_vehicule is not None
            or mode_transmission is not None
            or usage is not None
        ):
            try:
                rapport_mobilite = calculer_demande_mobilite(
                    demande_mobilite,
                    domaine_mobilite=domaine_mobilite,
                    type_vehicule=type_vehicule,
                    usage=usage,
                    mode_transmission=mode_transmission,
                )
                rapport["mobilite"] = rapport_mobilite
                p_mob = rapport_mobilite.get("resultats", {}).get("puissance_mecanique_requise_w")
                if puissance_cible_w is None and _is_finite(p_mob):
                    puissance_cible_w = float(p_mob)
                    rapport["notes_modele"].append(
                        "puissance_cible_w déduite automatiquement depuis la demande de mobilité normalisée."
                    )
                for cat in ("impossibles", "partielles"):
                    for inc in rapport_mobilite.get("inconnues", {}).get(cat, []) or []:
                        _push_inconnue(
                            rapport,
                            cat,
                            f"mobilite.{inc.get('nom')}",
                            str(inc.get("raison")),
                        )
            except Exception as exc:
                rapport["mobilite"] = {
                    "erreur": str(exc),
                    "domaine_mobilite": domaine_mobilite,
                    "type_vehicule": type_vehicule,
                    "mode_transmission": mode_transmission,
                }
                _push_inconnue(
                    rapport,
                    "partielles",
                    "mobilite",
                    f"Demande de mobilité non calculable ({exc}).",
                )

        rapport["entrees"] = {
            "usage": usage,
            "commentaire_usage": commentaire_usage,
            "domaine_mobilite": normaliser_domaine_mobilite(domaine_mobilite, type_vehicule=type_vehicule, usage=usage),
            "type_vehicule": normaliser_type_vehicule(type_vehicule, usage=usage),
            "mode_transmission": normaliser_mode_transmission(mode_transmission, domaine_mobilite=domaine_mobilite, type_vehicule=type_vehicule),
            "demande_mobilite_fournie": demande_mobilite is not None,
            "puissance_cible_w": puissance_cible_w,
            "regime_tr_min": regime_tr_min,
            "pme_pa": pme_pa,
            "vitesse_piston_max_ms": vitesse_piston_max_ms,
            "longueur_dispo_m": longueur_dispo_m,
            "largeur_dispo_m": largeur_dispo_m,
            "hauteur_dispo_m": hauteur_dispo_m,
            "horizon_usage_h": horizon_usage_h,
            "temps_moteur": self.temps_moteur,
            "rendement_mecanique": self.rendement_mecanique,
            "ratio_course_alesage_max": self.ratio_course_alesage_max,
            "joints_par_cyl": self.joints_par_cyl,
            "duree_vie_joint_base_h": self.duree_vie_joint_base_h,
            "cout_intervention_base_eur": self.cout_intervention_base_eur,
            "architectures_autorisees": architectures_autorisees,
            "architecture_forcee": architecture_forcee,
            "taux_compression": taux_compression,
            "nb_cas_de_charge": len(cas_de_charge) if cas_de_charge else 0,
            "activer_mode_fine": bool(activer_mode_fine),
        }

        rapport["criteres_conception"] = {
            "poids_maintenance": poids_maintenance,
            "poids_masse": poids_masse,
            "poids_cout_matiere": poids_cout_matiere,
            "poids_compacite": poids_compacite,
            "poids_fiabilite": poids_fiabilite,
            "poids_rendement": poids_rendement,
        }

        if puissance_cible_w is None:
            _push_inconnue(rapport, "impossibles", "puissance_cible_w", "Nécessaire pour calculer la cylindrée totale requise.")
        if regime_tr_min is None:
            _push_inconnue(rapport, "impossibles", "regime_tr_min", "Nécessaire pour f(cycles/s), vitesse piston, et cylindrée.")
        if pme_pa is None:
            _push_inconnue(rapport, "impossibles", "pme_pa", "Nécessaire pour relier puissance et cylindrée (PME).")

        if longueur_dispo_m is None or largeur_dispo_m is None:
            _push_inconnue(rapport, "partielles", "gabarit (L/W)", "Nécessaire pour valider le packaging et choisir l'architecture optimale.")

        if vitesse_piston_max_ms is None:
            _push_inconnue(rapport, "partielles", "vitesse_piston_max_ms", "Nécessaire pour borner l'alésage et la cylindrée unitaire admissible.")

        if puissance_cible_w is None or regime_tr_min is None or pme_pa is None:
            _dedup_inconnues(rapport)
            return rapport

        # ------------------------------------------------------------
        # Mode fin multi-cas : privilégié si les entrées sont présentes
        # ------------------------------------------------------------
        if (
            bool(activer_mode_fine)
            and resoudre_architecture_fine_multicas is not None
            and cas_de_charge
            and taux_compression is not None
            and longueur_dispo_m is not None
            and largeur_dispo_m is not None
            and vitesse_piston_max_ms is not None
        ):
            try:
                options_fines = _make_fine_options(
                    self.options_fines,
                    architectures_autorisees=architectures_autorisees,
                    architecture_forcee=architecture_forcee,
                    delta_exploration=self.delta_exploration,
                    n_max_absolu=self.n_max_absolu,
                )

                poids_masse_fins = float(poids_masse) + 0.60 * float(poids_cout_matiere)
                params_score = self.params_packaging_fins  # dummy to keep linter silent pattern-free
                _ = params_score
                if ParametresScoreArchitecture is not None:
                    params_score = ParametresScoreArchitecture(
                        poids_masse=poids_masse_fins,
                        poids_rendement=float(poids_rendement),
                        poids_fiabilite=float(poids_fiabilite),
                        poids_packaging=float(poids_compacite),
                        poids_maintenance=float(poids_maintenance),
                    )
                else:
                    params_score = None

                solution_fine = resoudre_architecture_fine_multicas(
                    puissance_cible_w=_require_positive("puissance_cible_w", puissance_cible_w, strict=False),
                    regime_nominal_tr_min=_require_positive("regime_tr_min", regime_tr_min, strict=True),
                    pme_nominale_pa=_require_positive("pme_pa", pme_pa, strict=True),
                    vitesse_piston_max_ms=_require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False),
                    L_max_m=_require_positive("longueur_dispo_m", longueur_dispo_m, strict=True),
                    W_max_m=_require_positive("largeur_dispo_m", largeur_dispo_m, strict=True),
                    H_max_m=_require_positive("hauteur_dispo_m", hauteur_dispo_m, strict=True) if hauteur_dispo_m is not None else None,
                    taux_compression=_require_positive("taux_compression", taux_compression, strict=True),
                    cas_de_charge=cas_de_charge,
                    horizon_usage_h=_require_positive("horizon_usage_h", horizon_usage_h, strict=False),
                    ordre_allumage_map=ordre_allumage_map,
                    params_packaging=self.params_packaging_fins if self.params_packaging_fins is not None else ParametresPackagingArchitecture(),
                    params_masse=self.params_masse_fins if self.params_masse_fins is not None else ParametresMasseArchitecture(),
                    params_pertes=self.params_pertes_fins if self.params_pertes_fins is not None else ParametresPertesArchitecture(),
                    params_fiabilite=self.params_fiabilite_fins if self.params_fiabilite_fins is not None else ParametresFiabiliteArchitecture(),
                    params_score=params_score if params_score is not None else ParametresScoreArchitecture(),
                    options=options_fines if options_fines is not None else OptionsExplorationArchitecture(),
                    ponderations_cas=ponderations_cas,
                )

                rapport = _convertir_solution_fine_vers_rapport(
                    solution_fine,
                    rapport,
                    poids_maintenance=poids_maintenance,
                    poids_masse=poids_masse,
                    poids_cout_matiere=poids_cout_matiere,
                    poids_compacite=poids_compacite,
                    poids_fiabilite=poids_fiabilite,
                    poids_rendement=poids_rendement,
                )

                rapport["notes_modele"].append(
                    "Le solveur fin est utilisé car cas_de_charge et taux_compression ont été fournis."
                )
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "coût industriel réel",
                    "Le solveur fin estime masse, rendement et fiabilité, mais pas le coût industriel exact sans procédés, volumes et temps d'usinage.",
                )
                _dedup_inconnues(rapport)
                return rapport
            except Exception as exc:
                rapport["notes_modele"].append(
                    f"Mode fin indisponible ou échec solveur multi-cas ({exc}). Repli sur le mode simple historique."
                )

        else:
            if activer_mode_fine and cas_de_charge and taux_compression is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "taux_compression",
                    "Requis pour activer le solveur fin multi-cas avec les cas de charge fournis.",
                )
            elif activer_mode_fine and cas_de_charge and resoudre_architecture_fine_multicas is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "solveur fin multi-cas",
                    "Module architecture_fine_multicas introuvable ; analyse simple utilisée.",
                )

        # ------------------------------------------------------------
        # Mode simple historique
        # ------------------------------------------------------------
        P = _require_positive("puissance_cible_w", puissance_cible_w, strict=False)
        n_rpm = _require_positive("regime_tr_min", regime_tr_min, strict=True)
        PME = _require_positive("pme_pa", pme_pa, strict=True)
        T_usage = _require_positive("horizon_usage_h", horizon_usage_h, strict=False)

        f_hz = _hz_cycles(n_rpm, self.temps_moteur)
        rapport["cycles"] = {"temps_moteur": self.temps_moteur, "frequence_cycles_hz": f_hz}

        eta_m = _require_positive("rendement_mecanique", self.rendement_mecanique, strict=True)
        V_tot_m3 = float(calcul_cylindree_totale_requise(P, PME, f_hz, eta_m))
        rapport["cylindree"]["cylindree_totale_m3"] = V_tot_m3
        rapport["cylindree"]["cylindree_totale_cc"] = V_tot_m3 * 1e6

        if V_tot_m3 <= 0.0:
            rapport["notes_modele"].append("Puissance cible nulle => cylindrée totale nulle.")
            _dedup_inconnues(rapport)
            return rapport

        bore_max_m: Optional[float] = None
        V_unit_max_m3: Optional[float] = None
        course_max_m: Optional[float] = None

        if vitesse_piston_max_ms is not None:
            Up_max = _require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
            r_max = _require_positive("ratio_course_alesage_max", self.ratio_course_alesage_max, strict=True)

            bore_max_m = float(calcul_bore_max_admissible(Up_max, n_rpm, r_max))
            V_unit_max_m3 = float(calcul_cylindree_unit_max(bore_max_m, r_max))
            course_max_m = float(_course_max_depuis_vitesse_piston(Up_max, n_rpm))

            rapport["contraintes_admissibles"] = {
                "Up_max_ms": Up_max,
                "ratio_S_B_max": r_max,
                "bore_max_m": bore_max_m,
                "bore_max_mm": bore_max_m * 1000.0,
                "cylindree_unitaire_max_m3": V_unit_max_m3,
                "cylindree_unitaire_max_cc": V_unit_max_m3 * 1e6,
                "course_max_m": course_max_m,
                "course_max_mm": course_max_m * 1000.0,
            }
        else:
            rapport["contraintes_admissibles"] = {"Up_max_ms": None}

        n_min: Optional[int] = None
        if V_unit_max_m3 is not None:
            n_min_calc = int(calcul_nombre_cylindres_min(V_tot_m3, V_unit_max_m3))
            if n_min_calc >= 999:
                _push_inconnue(rapport, "impossibles", "N_min", "Cylindrée unitaire max invalide (paramètres incohérents).")
            else:
                n_min = n_min_calc
        else:
            _push_inconnue(rapport, "partielles", "N_min", "Calculable si vitesse_piston_max_ms est fournie.")
        rapport["cylindree"]["N_min"] = n_min

        if n_min is None:
            _dedup_inconnues(rapport)
            return rapport

        if n_min > self.n_max_absolu:
            _push_inconnue(rapport, "impossibles", "N_min", f"N_min={n_min} > n_max_absolu={self.n_max_absolu}.")
            _dedup_inconnues(rapport)
            return rapport

        cout_inter_base = _require_positive("cout_intervention_base_eur", self.cout_intervention_base_eur, strict=False)
        if self.activer_scraping_prix:
            try:
                _ = calcul_cout_maintenance_estime_auto_prix(
                    duree_usage_h=1.0,
                    duree_vie_joint_base_h=self.duree_vie_joint_base_h,
                    charge_nominale_n=1.0,
                    charge_actuelle_n=1.0,
                    nb_joints_base=max(1, n_min * self.joints_par_cyl),
                    nb_joints_actuel=max(1, n_min * self.joints_par_cyl),
                    cout_inter_eur=cout_inter_base,
                    activer_scraping=True,
                    urls_prix_joints=self.urls_prix_joints,
                    urls_main_oeuvre=self.urls_main_oeuvre,
                    cache_path=self.cache_path_prix,
                    cache_ttl_h=self.cache_ttl_h,
                    timeout_s=self.timeout_scraping_s,
                    temps_intervention_h=self.temps_intervention_h,
                    cout_arret_eur=self.cout_arret_eur,
                    cout_consommables_eur=self.cout_consommables_eur,
                    strict_scraping=self.strict_scraping,
                )
                rapport["notes_modele"].append("Scraping activé : le module sait estimer des prix ; calibrer cout_intervention_base_eur si besoin.")
            except Exception:
                rapport["notes_modele"].append("Scraping activé mais estimation prix indisponible (fallback sur cout_intervention_base_eur).")

        rapport["maintenance"]["cout_intervention_base_eur"] = cout_inter_base
        rapport["maintenance"]["duree_vie_joint_base_h"] = self.duree_vie_joint_base_h
        rapport["maintenance"]["joints_par_cyl"] = self.joints_par_cyl

        if longueur_dispo_m is None or largeur_dispo_m is None:
            _dedup_inconnues(rapport)
            return rapport

        L_max = _require_positive("longueur_dispo_m", longueur_dispo_m, strict=True)
        W_max = _require_positive("largeur_dispo_m", largeur_dispo_m, strict=True)

        n_max_explore = max(self.min_exploration, n_min + self.delta_exploration)
        n_max_explore = min(self.n_max_absolu, n_max_explore)

        V_u_ref = V_tot_m3 / n_min
        ratio_ref = self.ratio_course_alesage_max
        if course_max_m is not None:
            r_lim = _ratio_max_compatible_vitesse_piston(V_u_ref, course_max_m)
            if math.isfinite(r_lim):
                ratio_ref = min(self.ratio_course_alesage_max, r_lim)
        ratio_ref = max(1e-6, ratio_ref)
        bore_ref, _ = _bore_et_course_depuis_volume_et_ratio(V_u_ref, ratio_ref)
        charge_ref_n = PME * _surface_piston_m2(bore_ref)

        allowed_set: Optional[set[str]] = None
        if architectures_autorisees:
            allowed_set = set(map(str, architectures_autorisees))

        for N in range(n_min, n_max_explore + 1):
            V_u = V_tot_m3 / N

            ratio_ret = self.ratio_course_alesage_max
            if course_max_m is not None:
                r_lim = _ratio_max_compatible_vitesse_piston(V_u, course_max_m)
                if math.isfinite(r_lim):
                    ratio_ret = min(self.ratio_course_alesage_max, r_lim)
            ratio_ret = max(1e-6, ratio_ret)

            bore_m, course_m = _bore_et_course_depuis_volume_et_ratio(V_u, ratio_ret)

            if bore_max_m is not None and bore_m > bore_max_m + 1e-12:
                continue
            if course_max_m is not None and course_m > course_max_m + 1e-12:
                continue

            charge_moy_n = PME * _surface_piston_m2(bore_m)

            cout_maint_raw = float(
                calcul_cout_maintenance_estime(
                    duree_usage_h=T_usage,
                    duree_vie_joint_base_h=self.duree_vie_joint_base_h,
                    charge_nominale_n=charge_ref_n,
                    charge_actuelle_n=charge_moy_n,
                    nb_joints_base=max(1, n_min * self.joints_par_cyl),
                    nb_joints_actuel=max(1, N * self.joints_par_cyl),
                    cout_inter_eur=cout_inter_base,
                )
            )
            cout_maint_score = float(cout_maint_raw * float(poids_maintenance))

            if architecture_forcee is not None:
                arch = str(architecture_forcee)
            else:
                arch = _appeler_choix_architecture_optimale(N, L_max, W_max, cout_maint_score)

            if arch == "Inconnue":
                continue
            if allowed_set is not None and arch not in allowed_set:
                continue

            score_module, valide = _appeler_evaluer_architecture(arch, N, L_max, W_max, cout_maint_score)
            if not bool(valide):
                continue

            L_pkg, W_pkg = _estimer_packaging_simple(arch, N, pas_cylindre_m=self.pas_cylindre_m, largeur_base_m=self.largeur_base_m)

            compacite_score = None
            if _is_finite(L_pkg) and _is_finite(W_pkg):
                compacite_score = _safe_div((L_pkg / L_max) + (W_pkg / W_max), 2.0)

            maintenance_indice = _estimer_indice_maintenance(nb_cyl=N, architecture=arch)
            masse_relative = _estimer_masse_relative(nb_cyl=N, bore_m=bore_m, course_m=course_m, architecture=arch)
            cout_matiere_relatif = _estimer_cout_matiere_relatif(masse_relative=masse_relative, architecture=arch)
            fiabilite_indice = _estimer_indice_fiabilite(
                nb_cyl=N,
                architecture=arch,
                ratio_s_b=ratio_ret,
                charge_moy_piston_n=charge_moy_n,
                charge_ref_n=charge_ref_n,
            )
            rendement_indice = _estimer_indice_rendement_relatif(nb_cyl=N, architecture=arch, ratio_s_b=ratio_ret)

            row = {
                "N_cyl": N,
                "architecture": arch,
                "score_module_externe": float(score_module),
                "valide": bool(valide),
                "cout_maintenance_eur": float(cout_maint_raw),
                "cout_maintenance_score_eur": float(cout_maint_score),
                "maintenance_indice": float(maintenance_indice),
                "masse_relative": float(masse_relative),
                "cout_matiere_relatif": float(cout_matiere_relatif),
                "fiabilite_indice": float(fiabilite_indice),
                "rendement_indice": float(rendement_indice),
                "compacite_score": float(compacite_score) if compacite_score is not None else None,
                "cylindree_tot_cc": float(V_tot_m3 * 1e6),
                "cylindree_unit_cc": float(V_u * 1e6),
                "bore_mm": float(bore_m * 1000.0),
                "course_mm": float(course_m * 1000.0),
                "ratio_S_B": float(ratio_ret),
                "charge_moy_piston_N": float(charge_moy_n),
                "L_pkg_m_estimee": float(L_pkg),
                "W_pkg_m_estimee": float(W_pkg),
            }
            rapport["exploration"].append(row)

        if not rapport["exploration"]:
            _push_inconnue(
                rapport,
                "impossibles",
                "solution",
                "Aucune configuration (N, architecture) valide dans le gabarit et sous contraintes admissibles.",
            )
            _dedup_inconnues(rapport)
            return rapport

        _normaliser_sur_candidats(rapport["exploration"], "cout_maintenance_score_eur", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "masse_relative", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "cout_matiere_relatif", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "compacite_score", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "fiabilite_indice", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "rendement_indice", sens="min")
        _normaliser_sur_candidats(rapport["exploration"], "score_module_externe", sens="min")

        best_score = float("inf")
        best_row: Optional[Dict[str, Any]] = None

        for row in rapport["exploration"]:
            score_multi = _score_multi_criteres(
                row,
                poids_maintenance=poids_maintenance,
                poids_masse=poids_masse,
                poids_cout_matiere=poids_cout_matiere,
                poids_compacite=poids_compacite,
                poids_fiabilite=poids_fiabilite,
                poids_rendement=poids_rendement,
            )
            score_global = float(score_multi + 0.20 * float(row.get("score_module_externe_norm") or 0.0))
            row["score_multi_criteres"] = float(score_multi)
            row["score_global"] = float(score_global)
            if score_global < best_score:
                best_score = score_global
                best_row = row

        rapport["meilleur"] = best_row

        best_by_arch: Dict[str, Dict[str, Any]] = {}
        for row in rapport["exploration"]:
            a = str(row["architecture"])
            if a not in best_by_arch or float(row["score_global"]) < float(best_by_arch[a]["score_global"]):
                best_by_arch[a] = row
        rapport["meilleurs_par_architecture"] = best_by_arch

        if vitesse_piston_max_ms is not None:
            try:
                rapport["solution_module_globale"] = resoudre_architecture_globale(
                    puissance_cible_w=P,
                    regime_tr_min=n_rpm,
                    pme_pa=PME,
                    vitesse_piston_max_ms=_require_positive("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False),
                    L_max_m=L_max,
                    W_max_m=W_max,
                    horizon_usage_h=T_usage,
                )
            except Exception:
                rapport["solution_module_globale"] = None
                rapport["notes_modele"].append("Échec appel resoudre_architecture_globale (paramètres / contraintes).")

        rapport["notes_modele"].append(
            "Les critères masse/coût matière/fiabilité/rendement sont ici des indices RELATIFS d'arbitrage, pas des valeurs industrielles absolues."
        )
        rapport["notes_modele"].append(
            "Le score global combine explicitement maintenance, masse, coût matière, compacité, fiabilité relative et rendement relatif."
        )

        _push_inconnue(rapport, "impossibles", "PME réelle (carte + pertes + transitoires)", "PME est une entrée modèle. Impossible de la déduire sans cycle thermo/mesures.")
        _push_inconnue(rapport, "impossibles", "vibrations / NVH / équilibrage", "Nécessite un modèle dynamique complet.")
        _push_inconnue(rapport, "impossibles", "refroidissement & gradients thermiques", "Nécessite architecture thermique, matériaux, échanges, conditions d'usage.")
        _push_inconnue(rapport, "impossibles", "coût industriel réel", "Le coût matière/usinage réel nécessite procédés, temps de fabrication, tolérances, outillages et volumes de série.")
        _push_inconnue(rapport, "impossibles", "masse réelle moteur complet", "Une masse réelle exige ensuite le détail des pièces, matériaux, épaisseurs et accessoires.")

        _dedup_inconnues(rapport)

        # ------------------------------------------------------------
        # Analyse des conséquences physiques (Pièces)
        # ------------------------------------------------------------
        pieces_rapport: Dict[str, Any] = {}
        best = rapport.get("meilleur")
        arch_choisie = str(best.get("architecture", "L")) if best else "L"
        nb_cyl_choisi = int(best.get("N_cyl", 4)) if best else 4
        
        vilebrequin_p = self.piece_vilebrequin or VilebrequinArch(architecture=arch_choisie, nb_cylindres=nb_cyl_choisi)
        bloc_p = self.piece_bloc or BlocMoteurArch(architecture=arch_choisie, nb_cylindres=nb_cyl_choisi)
        culasse_p = self.piece_culasse or CulasseArch(architecture=arch_choisie, nb_cylindres=nb_cyl_choisi)
        
        for nom, piece in (
            ("vilebrequin", vilebrequin_p),
            ("bloc", bloc_p),
            ("culasse", culasse_p),
        ):
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces_rapport[nom] = piece.analyser()
                except Exception as exc:
                    pieces_rapport[nom] = {"erreur": str(exc)}
        
        if pieces_rapport:
            rapport["pieces"] = pieces_rapport

        return rapport



# ============================================================
# Orchestration haut niveau / export JSON
# ============================================================

def _to_plain_data(obj: Any) -> Any:
    """Convertit récursivement dataclasses, numpy scalaires/tableaux et objets divers en JSON-safe."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_plain_data(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_plain_data(v) for v in obj]
    if is_dataclass(obj):
        return _to_plain_data(asdict(obj))
    # Compatibilité numpy sans dépendance obligatoire.
    if hasattr(obj, "tolist"):
        try:
            return _to_plain_data(obj.tolist())
        except Exception:
            pass
    if hasattr(obj, "item"):
        try:
            return _to_plain_data(obj.item())
        except Exception:
            pass
    return str(obj)


def exporter_rapport_json(rapport: Dict[str, Any], chemin: str | Path, *, indent: int = 2) -> str:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_plain_data(rapport), ensure_ascii=False, indent=indent), encoding="utf-8")
    return str(path)


def _prendre(d: Mapping[str, Any], *cles: str, default: Any = None) -> Any:
    for cle in cles:
        if cle in d:
            return d[cle]
    return default


def _filtrer_kwargs(cls: Any, valeurs: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        champs = set(getattr(cls, "__dataclass_fields__", {}).keys())
    except Exception:
        champs = set()
    if not champs:
        return dict(valeurs)
    return {k: v for k, v in valeurs.items() if k in champs}


def construire_architecture(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Architecture:
    """
    Construit le composant Architecture depuis un dictionnaire.

    Le dictionnaire peut contenir :
    - les champs directs de Architecture ;
    - un sous-dictionnaire `architecture` ;
    - un sous-dictionnaire `pieces` avec `vilebrequin`, `bloc`, `culasse`.
    """
    cfg: Dict[str, Any] = dict(config or {})
    cfg.update(overrides)
    arch_cfg: Dict[str, Any] = dict(cfg.get("architecture", {}))
    for k, v in cfg.items():
        if k not in {"architecture", "analyse", "profil", "pieces"}:
            arch_cfg.setdefault(k, v)

    pieces_cfg = cfg.get("pieces") or arch_cfg.get("pieces") or {}
    if isinstance(pieces_cfg, Mapping):
        if "vilebrequin" in pieces_cfg and pieces_cfg["vilebrequin"] is not None:
            arch_cfg["piece_vilebrequin"] = VilebrequinArch(**_filtrer_kwargs(VilebrequinArch, dict(pieces_cfg["vilebrequin"])))
        if "bloc" in pieces_cfg and pieces_cfg["bloc"] is not None:
            arch_cfg["piece_bloc"] = BlocMoteurArch(**_filtrer_kwargs(BlocMoteurArch, dict(pieces_cfg["bloc"])))
        if "culasse" in pieces_cfg and pieces_cfg["culasse"] is not None:
            arch_cfg["piece_culasse"] = CulasseArch(**_filtrer_kwargs(CulasseArch, dict(pieces_cfg["culasse"])))

    return Architecture(**_filtrer_kwargs(Architecture, arch_cfg))


def concevoir_architecture(config: Optional[Mapping[str, Any]] = None, **overrides: Any) -> Dict[str, Any]:
    """
    Orchestrateur complet du composant Architecture.

    Exemples acceptés :
    - concevoir_architecture({"puissance_cible_w": ..., "regime_tr_min": ...})
    - concevoir_architecture({"architecture": {...}, "analyse": {...}})
    - concevoir_architecture({"profil": {...}, "analyse": {...}})
    """
    cfg: Dict[str, Any] = dict(config or {})
    cfg.update(overrides)

    composant = construire_architecture(cfg)
    analyse_cfg: Dict[str, Any] = dict(cfg.get("analyse", {}))
    for k, v in cfg.items():
        if k not in {"architecture", "analyse", "profil", "pieces"}:
            analyse_cfg.setdefault(k, v)

    # Autorise une configuration plate : les paramètres physiques de mobilité
    # peuvent être fournis au niveau racine au lieu d'être rangés dans
    # `demande_mobilite`.
    mobility_flat_keys = {
        "masse_totale_kg", "masse_kg",
        "vitesse_ms", "vitesse_kmh", "vitesse_moyenne_kmh",
        "crr", "cda_m2", "cx_s_m2", "rho_air_kg_m3", "pente", "pente_ratio",
        "acceleration_ms2", "coefficient_adherence", "mu",
        "repartition_masse_avant", "empattement_m", "hauteur_cg_m",
        "rendement_chaine", "rendement_transmission", "rendement_propulsif_global",
        "force_resistance_n", "resistance_hydrodynamique_n",
        "rho_fluide_kg_m3", "coefficient_trainee", "cd",
        "surface_mouillee_equivalente_m2", "surface_frontale_m2", "surface_m2",
        "force_trainee_n", "taux_montee_ms",
        "puissance_mecanique_requise_w", "puissance_cible_kw",
        "puissance_mecanique_requise_kw", "puissance_thermique_mecanique_w",
    }
    if "demande_mobilite" not in analyse_cfg:
        flat_demande = {k: cfg[k] for k in mobility_flat_keys if k in cfg}
        if flat_demande:
            analyse_cfg["demande_mobilite"] = flat_demande

    profil_cfg = cfg.get("profil")
    if isinstance(profil_cfg, Mapping):
        profil = ProfilUsageMoteur(**_filtrer_kwargs(ProfilUsageMoteur, dict(profil_cfg)))
        rapport = composant.recommander_pour_profil(
            profil,
            puissance_cible_w=analyse_cfg.get("puissance_cible_w"),
            regime_tr_min=analyse_cfg.get("regime_tr_min"),
            pme_pa=analyse_cfg.get("pme_pa"),
        )
    else:
        # Ne transmet que les arguments de Architecture.analyser.
        allowed = {
            "puissance_cible_w",
            "regime_tr_min",
            "pme_pa",
            "vitesse_piston_max_ms",
            "longueur_dispo_m",
            "largeur_dispo_m",
            "hauteur_dispo_m",
            "horizon_usage_h",
            "taux_compression",
            "cas_de_charge",
            "ordre_allumage_map",
            "ponderations_cas",
            "activer_mode_fine",
            "domaine_mobilite",
            "type_vehicule",
            "mode_transmission",
            "demande_mobilite",
            "architectures_autorisees",
            "architecture_forcee",
            "poids_maintenance",
            "poids_masse",
            "poids_cout_matiere",
            "poids_compacite",
            "poids_fiabilite",
            "poids_rendement",
            "usage",
            "commentaire_usage",
        }
        rapport = composant.analyser(**{k: v for k, v in analyse_cfg.items() if k in allowed})

    rapport.setdefault("orchestrateur", {})
    rapport["orchestrateur"].update(
        {
            "composant": "architecture",
            "imports": {
                "solveur_fine_multicas_disponible": bool(resoudre_architecture_fine_multicas is not None),
                "pieces_disponibles": {
                    "vilebrequin": bool(VilebrequinArch is not None),
                    "bloc": bool(BlocMoteurArch is not None),
                    "culasse": bool(CulasseArch is not None),
                },
            },
        }
    )
    return rapport


__all__ = [
    "UsageType",
    "ArchitectureType",
    "ProfilUsageMoteur",
    "normaliser_domaine_mobilite",
    "normaliser_type_vehicule",
    "normaliser_mode_transmission",
    "calculer_demande_mobilite",
    "estimer_pme_depuis_couple_et_cylindree",
    "estimer_pme_depuis_puissance_et_cylindree",
    "Architecture",
    "construire_architecture",
    "concevoir_architecture",
    "exporter_rapport_json",
]


if __name__ == "__main__":
    exemple = {
        "puissance_cible_w": 150_000.0,
        "regime_tr_min": 4500.0,
        "pme_pa": 1.2e6,
        "vitesse_piston_max_ms": 25.0,
        "longueur_dispo_m": 1.2,
        "largeur_dispo_m": 0.8,
        "hauteur_dispo_m": 0.7,
        "domaine_mobilite": "routier",
        "type_vehicule": "buggy",
        "mode_transmission": "propultion",
        "demande_mobilite": {
            "masse_totale_kg": 850.0,
            "vitesse_kmh": 110.0,
            "crr": 0.018,
            "cda_m2": 0.75,
            "rho_air_kg_m3": 1.225,
            "pente": 0.0,
            "rendement_chaine": 0.90,
            "coefficient_adherence": 0.85,
            "repartition_masse_avant": 0.42,
            "empattement_m": 2.35,
            "hauteur_cg_m": 0.55,
        },
    }
    rapport = concevoir_architecture(exemple)
    print(json.dumps(_to_plain_data({
        "mode_analyse": rapport.get("mode_analyse"),
        "meilleur": rapport.get("meilleur"),
        "inconnues": rapport.get("inconnues"),
    }), ensure_ascii=False, indent=2))
