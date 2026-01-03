# backend/pieces/roulement_aiguille_arbre_vilebrequin.py
# =============================================================================
# ROULEMENT À AIGUILLES — ARBRE / VILEBREQUIN (côté maneton / grande tête)
# =============================================================================
# - Pièce du commerce.
# - Sans référence : on ne "donne" pas (d, D, B). On calcule des EXIGENCES.
# - Pour permettre le dimensionnement du vilebrequin :
#   -> on fournit d_interieur_requis_m (= diamètre maneton nominal) si calculable.
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, List
import math


# =============================================================================
# Utilitaires
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if x is None or not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly and v <= 0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if (not strictly) and v < 0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v

def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport.setdefault("inconnues", {}).setdefault(categorie, []).append({"nom": nom, "raison": raison})

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

def _deep_get(d: Any, path: Tuple[str, ...]) -> Any:
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        if k not in cur:
            return None
        cur = cur[k]
    return cur

def _first_numeric_from_dict(d: Dict[str, Any], candidates: List[Tuple[str, ...]]) -> Optional[float]:
    for path in candidates:
        v = _deep_get(d, path)
        if _is_finite(v):
            return float(v)
    return None

def _try_call_report(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    for m in ("calculer", "analyser"):
        try:
            if hasattr(obj, m) and callable(getattr(obj, m)):
                r = getattr(obj, m)()
                if isinstance(r, dict):
                    return r
        except Exception:
            continue
    return None


# =============================================================================
# Modèles de calcul roulement (exigences)
# =============================================================================

def _L10_million_rev(vie_heures: float, rpm: float) -> float:
    tours = rpm * 60.0 * vie_heures
    return tours / 1e6

def _C_requis_iso281(P_N: float, L10_million: float, p_exposant: float) -> float:
    return P_N * (L10_million ** (1.0 / p_exposant))

def _pression_moyenne_proj(F_N: float, d_m: float, B_m: float) -> float:
    return abs(F_N) / (d_m * B_m)


# =============================================================================
# Pièce
# =============================================================================

@dataclass
class RoulementAiguilleArbreVilebrequin:
    """
    Roulement à aiguilles au niveau du maneton (grande tête).

    Sorties utiles pour l'arbre de vilebrequin :
    - d_interieur_requis_m : diamètre intérieur requis (nominal) = diamètre maneton
    - dimensions_reference (si référence choisie) : d, D, B (catalogue)
    """

    # Liens
    corps_bielle: Optional[Any] = None

    # Cinématique / durée de vie
    rpm_vilebrequin: Optional[float] = None
    vie_cible_heures: Optional[float] = None
    exposant_p_iso281: float = 10.0 / 3.0

    # Facteurs (optionnels)
    facteur_application_Ka: Optional[float] = None
    facteur_fiablete_a1: Optional[float] = None
    facteur_contamination_a23: Optional[float] = None

    # Charges
    charge_equivalente_P_N: Optional[float] = None
    charge_statique_P0_N: Optional[float] = None
    facteur_securite_stat: Optional[float] = None

    # Interface (déductible depuis bielle)
    diametre_maneton_m: Optional[float] = None
    largeur_portee_grande_tete_m: Optional[float] = None

    # Référence commerciale (si choisie)
    d_interieur_m: Optional[float] = None   # d
    D_exterieur_m: Optional[float] = None   # D
    B_largeur_m: Optional[float] = None     # B
    C_dynamique_N: Optional[float] = None
    C0_statique_N: Optional[float] = None
    vitesse_limite_rpm: Optional[float] = None
    pression_admissible_pa: Optional[float] = None

    # -------------------------------------------------------------------------
    # Extraction bielle
    # -------------------------------------------------------------------------
    def _extraire_depuis_bielle(self, rapport: Dict[str, Any]) -> Dict[str, Optional[float]]:
        out = {"Fmax_N": None, "d_maneton_m": None, "L_portee_m": None}
        rb = _try_call_report(self.corps_bielle)
        if not isinstance(rb, dict):
            _push_inconnue(rapport, "partielles", "bielle", "Impossible de lire corps_bielle (pas de dict retourné).")
            return out

        out["Fmax_N"] = _first_numeric_from_dict(
            rb,
            [
                ("efforts", "force_axiale_max_N"),
                ("resultats", "force_axiale_max_N"),
                ("force_axiale_max_N",),
            ],
        )

        out["d_maneton_m"] = _first_numeric_from_dict(
            rb,
            [
                ("geometrie", "grande_tete", "diametre_maneton_m"),
                ("entrees", "diametre_maneton_m"),
                ("diametre_maneton_m",),
            ],
        )

        out["L_portee_m"] = _first_numeric_from_dict(
            rb,
            [
                ("contacts_tetes", "grande_tete", "longueur_portee_m"),
                ("entrees", "longueur_portee_grande_tete_m"),
                ("geometrie", "grande_tete", "longueur_portee_grande_tete_m"),
            ],
        )

        return out

    # -------------------------------------------------------------------------
    # Calcul
    # -------------------------------------------------------------------------
    def calculer(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "roulement_aiguille_arbre_vilebrequin",
            "entrees": {},
            "donnees_bielle": {},
            "charges": {},
            "exigences": {},
            "dimensions_requises": {},
            "dimensions_reference": {},
            "verification_reference": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # 1) Déductions bielle
        b = {"Fmax_N": None, "d_maneton_m": None, "L_portee_m": None}
        if self.corps_bielle is not None:
            b = self._extraire_depuis_bielle(rapport)
        rapport["donnees_bielle"] = b

        # 2) Maneton + largeur portée
        d_maneton = self.diametre_maneton_m if self.diametre_maneton_m is not None else b["d_maneton_m"]
        L_portee = self.largeur_portee_grande_tete_m if self.largeur_portee_grande_tete_m is not None else b["L_portee_m"]

        if d_maneton is not None:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)
            # >>> DIAMÈTRE INTERIEUR REQUIS (pour l'arbre / maneton)
            rapport["dimensions_requises"]["d_interieur_requis_m"] = d_maneton
            rapport["notes_modele"].append(
                "d_interieur_requis_m fixé = diamètre maneton nominal. Les ajustements (jeu/serrage) dépendent du fabricant/ISO et ne sont pas inventés."
            )
        else:
            _push_inconnue(
                rapport,
                "impossibles",
                "diametre_maneton_m",
                "Indispensable : impose d_interieur_requis_m (donc la portée de l'arbre). Déductible via CorpsBielle ou à fournir.",
            )

        if L_portee is not None:
            L_portee = _req_pos("largeur_portee_grande_tete_m", L_portee)
            rapport["dimensions_requises"]["B_min_requis_m"] = L_portee
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_portee_grande_tete_m",
                "Utile pour comparer à B (largeur) du roulement choisi.",
            )

        # 3) Charge P
        P = self.charge_equivalente_P_N
        if P is None and b["Fmax_N"] is not None:
            P = abs(float(b["Fmax_N"]))
            rapport["notes_modele"].append(
                "Hypothèse conservatrice : P ≈ |force_axiale_max_bielle| (charge radiale équivalente)."
            )
        if P is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "charge_equivalente_P_N",
                "Indispensable pour C_min (ISO 281). Fournir P ou rendre Fmax déductible depuis bielle.",
            )

        P0 = self.charge_statique_P0_N
        if P0 is None:
            _push_inconnue(
                rapport,
                "partielles",
                "charge_statique_P0_N",
                "Requis pour vérifier C0 statique.",
            )

        rapport["charges"] = {"charge_equivalente_P_N": P, "charge_statique_P0_N": P0}

        # 4) Vie / vitesse
        rpm = self.rpm_vilebrequin
        vie_h = self.vie_cible_heures

        if rpm is None:
            _push_inconnue(rapport, "impossibles", "rpm_vilebrequin", "Nécessaire pour L10.")
        else:
            rpm = _req_pos("rpm_vilebrequin", rpm)

        if vie_h is None:
            _push_inconnue(rapport, "impossibles", "vie_cible_heures", "Nécessaire pour L10.")
        else:
            vie_h = _req_pos("vie_cible_heures", vie_h)

        # 5) Exigences C_min
        if P is not None and rpm is not None and vie_h is not None:
            P_eff = float(P)
            if self.facteur_application_Ka is not None:
                Ka = _req_pos("facteur_application_Ka", self.facteur_application_Ka)
                P_eff *= Ka
                rapport["notes_modele"].append("P_eff = P * Ka.")

            if self.facteur_fiablete_a1 is not None or self.facteur_contamination_a23 is not None:
                rapport["notes_modele"].append(
                    "a1/a23 fournis mais non appliqués par défaut (convention ISO à préciser, non inventée)."
                )

            L10_m = _L10_million_rev(float(vie_h), float(rpm))
            pexp = _req_pos("exposant_p_iso281", self.exposant_p_iso281)
            C_min = _C_requis_iso281(P_eff, L10_m, pexp)

            rapport["exigences"].update({
                "L10_millions_tours": L10_m,
                "P_eff_N": P_eff,
                "C_dynamique_min_N": C_min,
                "exposant_p": pexp,
            })

        # 6) C0_min
        if P0 is not None and self.facteur_securite_stat is not None:
            fs0 = _req_pos("facteur_securite_stat", self.facteur_securite_stat)
            rapport["exigences"]["C0_statique_min_N"] = abs(float(P0)) * fs0
            rapport["exigences"]["facteur_securite_stat"] = fs0
        elif P0 is not None and self.facteur_securite_stat is None:
            _push_inconnue(rapport, "partielles", "facteur_securite_stat", "Requis pour C0_statique_min_N.")

        # 7) Dimensions de référence (si roulement choisi)
        # >>> C'est ici qu'on a d / D / B réels.
        if self.d_interieur_m is not None:
            d_ref = _req_pos("d_interieur_m", self.d_interieur_m)
            rapport["dimensions_reference"]["d_interieur_m"] = d_ref
            if d_maneton is not None:
                rapport["verification_reference"].setdefault("interface", {})
                rapport["verification_reference"]["interface"]["d_vs_maneton_nominal"] = {
                    "d_interieur_m": d_ref,
                    "diametre_maneton_m": d_maneton,
                    "ecart_m": d_ref - d_maneton,
                }
        else:
            # Sans référence, impossible de fixer la portée finale si tu refuses d'utiliser d_requis=maneton.
            _push_inconnue(
                rapport,
                "partielles",
                "d_interieur_m (reference)",
                "Sera connu quand tu choisis la référence. En attendant, d_interieur_requis_m = diametre_maneton_m sert de contrainte.",
            )

        if self.D_exterieur_m is not None:
            D_ref = _req_pos("D_exterieur_m", self.D_exterieur_m)
            rapport["dimensions_reference"]["D_exterieur_m"] = D_ref
            # >>> logement bielle requis
            rapport["dimensions_requises"]["D_exterieur_requis_m"] = D_ref
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "D_exterieur_m (reference)",
                "Indispensable pour dimensionner l'alésage logement dans la grande tête. Connu uniquement après choix du roulement.",
            )

        if self.B_largeur_m is not None:
            B_ref = _req_pos("B_largeur_m", self.B_largeur_m)
            rapport["dimensions_reference"]["B_largeur_m"] = B_ref
            if L_portee is not None:
                rapport["verification_reference"].setdefault("interface", {})
                rapport["verification_reference"]["interface"]["B_vs_portee"] = {
                    "B_largeur_m": B_ref,
                    "largeur_portee_m": L_portee,
                    "marge_m": L_portee - B_ref,
                    "ok": (L_portee >= B_ref),
                }
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "B_largeur_m (reference)",
                "Indispensable pour valider l'encombrement axial. Connu uniquement après choix du roulement.",
            )

        # 8) Vérifs capacités catalogue (si fournies)
        if self.C_dynamique_N is not None and "C_dynamique_min_N" in rapport["exigences"]:
            C = _req_pos("C_dynamique_N", self.C_dynamique_N)
            Cmin = float(rapport["exigences"]["C_dynamique_min_N"])
            rapport["verification_reference"]["C"] = {"C_N": C, "C_min_N": Cmin, "ok": C >= Cmin, "marge": (C / Cmin) if Cmin > 0 else None}
        elif "C_dynamique_min_N" in rapport["exigences"]:
            _push_inconnue(rapport, "partielles", "C_dynamique_N", "Fournir C catalogue pour valider.")

        if self.C0_statique_N is not None and "C0_statique_min_N" in rapport["exigences"]:
            C0 = _req_pos("C0_statique_N", self.C0_statique_N)
            C0min = float(rapport["exigences"]["C0_statique_min_N"])
            rapport["verification_reference"]["C0"] = {"C0_N": C0, "C0_min_N": C0min, "ok": C0 >= C0min, "marge": (C0 / C0min) if C0min > 0 else None}
        elif "C0_statique_min_N" in rapport["exigences"]:
            _push_inconnue(rapport, "partielles", "C0_statique_N", "Fournir C0 catalogue pour valider.")

        if self.vitesse_limite_rpm is not None and rpm is not None:
            vmax = _req_pos("vitesse_limite_rpm", self.vitesse_limite_rpm)
            rapport["verification_reference"]["vitesse"] = {"rpm_service": rpm, "rpm_limite": vmax, "ok": rpm <= vmax, "marge": (vmax / rpm) if rpm > 0 else None}
        elif rpm is not None:
            _push_inconnue(rapport, "partielles", "vitesse_limite_rpm", "Fournir vitesse limite fabricant pour valider.")

        # pression projetée si d et B connus
        if P is not None and self.d_interieur_m is not None and self.B_largeur_m is not None:
            p_proj = _pression_moyenne_proj(float(P), float(_req_pos("d_interieur_m", self.d_interieur_m)), float(_req_pos("B_largeur_m", self.B_largeur_m)))
            rapport["verification_reference"]["pression_proj"] = {"pression_moyenne_pa": p_proj, "pression_admissible_pa": self.pression_admissible_pa}
            if self.pression_admissible_pa is not None:
                padm = _req_pos("pression_admissible_pa", self.pression_admissible_pa)
                rapport["verification_reference"]["pression_proj"]["ok"] = (p_proj <= padm)
                rapport["verification_reference"]["pression_proj"]["marge"] = (padm / p_proj) if p_proj > 0 else None
            else:
                _push_inconnue(rapport, "partielles", "pression_admissible_pa", "Fournir une pression admissible si tu veux conclure.")

        # 9) Entrées
        rapport["entrees"] = {
            "rpm_vilebrequin": self.rpm_vilebrequin,
            "vie_cible_heures": self.vie_cible_heures,
            "exposant_p_iso281": self.exposant_p_iso281,
            "facteur_application_Ka": self.facteur_application_Ka,
            "facteur_fiablete_a1": self.facteur_fiablete_a1,
            "facteur_contamination_a23": self.facteur_contamination_a23,
            "charge_equivalente_P_N": self.charge_equivalente_P_N,
            "charge_statique_P0_N": self.charge_statique_P0_N,
            "facteur_securite_stat": self.facteur_securite_stat,
            "diametre_maneton_m": self.diametre_maneton_m,
            "largeur_portee_grande_tete_m": self.largeur_portee_grande_tete_m,
            "d_interieur_m": self.d_interieur_m,
            "D_exterieur_m": self.D_exterieur_m,
            "B_largeur_m": self.B_largeur_m,
            "C_dynamique_N": self.C_dynamique_N,
            "C0_statique_N": self.C0_statique_N,
            "vitesse_limite_rpm": self.vitesse_limite_rpm,
            "pression_admissible_pa": self.pression_admissible_pa,
        }

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "RoulementAiguilleArbreVilebrequin(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )
        return rapport
