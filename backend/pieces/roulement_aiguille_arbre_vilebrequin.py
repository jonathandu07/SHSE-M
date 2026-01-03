# backend/pieces/roulement_aiguille_arbre_vilebrequin.py
# =============================================================================
# ROULEMENT À AIGUILLES — ARBRE / VILEBREQUIN (côté maneton / grande tête)
# =============================================================================
# Objectif :
# - Tu vas choisir une pièce du commerce (référence de roulement à aiguilles).
# - Ce module :
#   (1) récupère les efforts et la géométrie côté grande tête (bielle) si disponibles,
#   (2) calcule les EXIGENCES minimales (C, C0, largeur, vitesses, pression moyenne),
#   (3) vérifie une référence commerciale (d, D, B, C, C0, vitesse_limite) si fournie,
#   (4) en déduit les dimensions à respecter côté bielle (alésage / largeur / maneton),
#       sans jamais “inventer” un standard de roulement.
#
# IMPORTANT ("rien inventer") :
# - Sans référence commerciale, on ne donne PAS d(diamètre intérieur), D(diamètre extérieur), B(largeur).
#   On donne des exigences (min) et des inconnues.
# - Les hypothèses de modèle (ex : charge radiale P ~= effort bielle max) sont explicitement notées.
#
# Références de calcul :
# - Durée de vie ISO 281 : L10 = (C/P)^p * 1e6 tours, p = 10/3 pour roulements à rouleaux.
#   -> C_min = P * (L10/1e6)^(1/p)
# - Charge statique : vérification C0 (modèle simple si facteur fourni)
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
# Modèles de calcul roulement
# =============================================================================

def _L10_million_rev(vie_heures: float, rpm: float) -> float:
    # tours = rpm * 60 * heures ; L10 en millions de tours
    tours = rpm * 60.0 * vie_heures
    return tours / 1e6

def _C_requis_iso281(P_N: float, L10_million: float, p_exposant: float) -> float:
    # C = P * (L10)^(1/p)
    return P_N * (L10_million ** (1.0 / p_exposant))

def _pression_moyenne_proj(F_N: float, d_m: float, B_m: float) -> float:
    # pression moyenne projetée p = F / (d*B) (modèle simplifié "journal/needle")
    return abs(F_N) / (d_m * B_m)


# =============================================================================
# Pièce : RoulementAiguilleArbreVilebrequin
# =============================================================================

@dataclass
class RoulementAiguilleArbreVilebrequin:
    """
    Cible : roulement à aiguilles au niveau du maneton (grande tête de bielle).

    Le module sait :
    - Déduire les efforts P à partir de la bielle (si disponible),
    - Déduire la vitesse (rpm vilebrequin) si fournie,
    - Calculer C_min (dynamique) pour une vie cible,
    - Vérifier une référence commerciale si ses caractéristiques sont fournies.
    """

    # -------------------------------------------------------------------------
    # Liens vers autres pièces
    # -------------------------------------------------------------------------
    corps_bielle: Optional[Any] = None   # backend.pieces.corps_bielle.CorpsBielle (idéalement)

    # -------------------------------------------------------------------------
    # Cinématique / durée de vie
    # -------------------------------------------------------------------------
    rpm_vilebrequin: Optional[float] = None
    vie_cible_heures: Optional[float] = None

    # Roulements à rouleaux/aiguilles : p = 10/3
    exposant_p_iso281: float = 10.0 / 3.0

    # Facteurs d'application (si tu veux être conservatif, tu les fournis)
    # Sans ces facteurs, on calcule "au nominal" sans inventer.
    facteur_application_Ka: Optional[float] = None   # chocs / service
    facteur_fiablete_a1: Optional[float] = None      # ISO (optionnel)
    facteur_contamination_a23: Optional[float] = None  # ISO (optionnel)

    # -------------------------------------------------------------------------
    # Efforts : si non déductibles
    # -------------------------------------------------------------------------
    # Charge équivalente dynamique P (radiale) en N : si tu la fournis, on l'utilise.
    # Sinon, on tente de la déduire depuis la bielle.
    charge_equivalente_P_N: Optional[float] = None

    # Charge statique équivalente P0 (si tu veux vérifier C0) :
    charge_statique_P0_N: Optional[float] = None
    facteur_securite_stat: Optional[float] = None  # ex: 1.5..3 selon cahier des charges, à fournir

    # -------------------------------------------------------------------------
    # Géométrie interface (déductible partiellement depuis bielle)
    # -------------------------------------------------------------------------
    # Maneton (diamètre) et largeur de portée (côté grande tête).
    # Si non fournis, on tente depuis CorpsBielle.
    diametre_maneton_m: Optional[float] = None
    largeur_portee_grande_tete_m: Optional[float] = None

    # -------------------------------------------------------------------------
    # Référence commerciale (si choisie) — à renseigner quand tu as une pièce catalogue
    # -------------------------------------------------------------------------
    # Dimensions
    d_interieur_m: Optional[float] = None   # d
    D_exterieur_m: Optional[float] = None   # D
    B_largeur_m: Optional[float] = None     # B

    # Capacités
    C_dynamique_N: Optional[float] = None
    C0_statique_N: Optional[float] = None

    # Vitesse limite (si fournie par le fabricant)
    vitesse_limite_rpm: Optional[float] = None

    # Vérifs "contact" si tu fournis une pression admissible (sinon inconnue)
    pression_admissible_pa: Optional[float] = None

    # -------------------------------------------------------------------------
    # Extraction inter-pièces (bielle)
    # -------------------------------------------------------------------------
    def _extraire_depuis_bielle(self, rapport: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Extrait :
        - Fmax ~ effort axial max dans la bielle (utilisé comme charge radiale conservatrice)
        - d_maneton, L_portee_grande
        """
        out = {"Fmax_N": None, "d_maneton_m": None, "L_portee_m": None}

        rb = _try_call_report(self.corps_bielle)
        if not isinstance(rb, dict):
            _push_inconnue(rapport, "partielles", "bielle", "Impossible de lire corps_bielle (pas de dict retourné).")
            return out

        # Force max bielle
        out["Fmax_N"] = _first_numeric_from_dict(
            rb,
            [
                ("efforts", "force_axiale_max_N"),
                ("resultats", "force_axiale_max_N"),
                ("force_axiale_max_N",),
            ],
        )

        # Géométrie grande tête : diametre maneton
        out["d_maneton_m"] = _first_numeric_from_dict(
            rb,
            [
                ("geometrie", "grande_tete", "diametre_maneton_m"),
                ("entrees", "diametre_maneton_m"),
                ("diametre_maneton_m",),
            ],
        )

        # Longueur de portée grande tête
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
    # Calcul principal
    # -------------------------------------------------------------------------
    def calculer(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "piece": "roulement_aiguille_arbre_vilebrequin",
            "entrees": {},
            "donnees_bielle": {},
            "charges": {},
            "exigences": {},
            "verification_reference": {},
            "interface_bielle": {},
            "notes_modele": [],
            "inconnues": {"impossibles": [], "partielles": []},
        }

        # 1) Déductions depuis bielle
        b = {"Fmax_N": None, "d_maneton_m": None, "L_portee_m": None}
        if self.corps_bielle is not None:
            b = self._extraire_depuis_bielle(rapport)
        rapport["donnees_bielle"] = b

        # 2) Géométrie interface : maneton + largeur portée
        d_maneton = self.diametre_maneton_m if self.diametre_maneton_m is not None else b["d_maneton_m"]
        L_portee = self.largeur_portee_grande_tete_m if self.largeur_portee_grande_tete_m is not None else b["L_portee_m"]

        if d_maneton is not None:
            d_maneton = _req_pos("diametre_maneton_m", d_maneton)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "diametre_maneton_m",
                "Requis pour vérifier cohérence d_interieur (roulement) et calculer pression projetée.",
            )

        if L_portee is not None:
            L_portee = _req_pos("largeur_portee_grande_tete_m", L_portee)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "largeur_portee_grande_tete_m",
                "Requis pour comparer à B du roulement et calculer pression projetée.",
            )

        # 3) Charges équivalentes P / P0
        # P : si fourni, on l'utilise. Sinon on déduit via effort bielle max.
        P = self.charge_equivalente_P_N
        if P is None and b["Fmax_N"] is not None:
            # Hypothèse conservatrice : charge radiale roulement ~= effort axial max bielle.
            P = abs(float(b["Fmax_N"]))
            rapport["notes_modele"].append(
                "Hypothèse conservatrice : P (charge radiale équivalente roulement) ≈ |force_axiale_max_bielle|. "
                "Si tu veux un modèle plus fidèle, fournis la loi en fonction de l'angle vilebrequin/rapport L/R."
            )
        if P is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "charge_equivalente_P_N",
                "Indispensable pour dimensionner C (ISO 281). Fournir P ou rendre Fmax déductible depuis bielle.",
            )

        # P0 : si fourni, sinon on peut (au mieux) réutiliser P comme approximation statique si tu le demandes explicitement.
        P0 = self.charge_statique_P0_N
        if P0 is None:
            _push_inconnue(
                rapport,
                "partielles",
                "charge_statique_P0_N",
                "Requis pour vérifier C0. Sinon, on ne peut pas valider la statique.",
            )

        rapport["charges"] = {
            "charge_equivalente_P_N": P,
            "charge_statique_P0_N": P0,
        }

        # 4) Vie / vitesse
        rpm = self.rpm_vilebrequin
        vie_h = self.vie_cible_heures

        if rpm is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "rpm_vilebrequin",
                "Nécessaire pour convertir une vie en heures vers L10 (millions de tours).",
            )
        else:
            rpm = _req_pos("rpm_vilebrequin", rpm)

        if vie_h is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "vie_cible_heures",
                "Nécessaire pour dimensionner C (ISO 281).",
            )
        else:
            vie_h = _req_pos("vie_cible_heures", vie_h)

        # 5) Exigences dynamiques C_min (ISO 281)
        # Facteurs : si tu ne les fournis pas, on ne les invente pas.
        if P is not None and rpm is not None and vie_h is not None:
            Ka = self.facteur_application_Ka
            a1 = self.facteur_fiablete_a1
            a23 = self.facteur_contamination_a23

            P_eff = float(P)
            if Ka is not None:
                Ka = _req_pos("facteur_application_Ka", Ka)
                P_eff *= Ka
                rapport["notes_modele"].append("P_eff = P * Ka (facteur application).")

            # ISO 281 modifiée (a1, a23) : selon approche, on agit sur vie corrigée.
            # Ici : on ne force pas une convention si tu ne fournis pas comment les appliquer.
            # On reporte simplement les facteurs si donnés, sans inventer leur emploi.
            if a1 is not None or a23 is not None:
                rapport["notes_modele"].append(
                    "Facteurs a1/a23 fournis : leur usage dépend de ta convention ISO (vie corrigée). "
                    "Par défaut ici : NON appliqués (pas d'invention)."
                )

            L10_m = _L10_million_rev(float(vie_h), float(rpm))
            pexp = _req_pos("exposant_p_iso281", self.exposant_p_iso281)
            C_min = _C_requis_iso281(P_eff, L10_m, pexp)

            rapport["exigences"]["L10_millions_tours"] = L10_m
            rapport["exigences"]["P_eff_N"] = P_eff
            rapport["exigences"]["C_dynamique_min_N"] = C_min
            rapport["exigences"]["exposant_p"] = pexp

        # 6) Exigences statiques C0_min (si facteur fourni)
        if P0 is not None and self.facteur_securite_stat is not None:
            fs0 = _req_pos("facteur_securite_stat", self.facteur_securite_stat)
            C0_min = abs(float(P0)) * fs0
            rapport["exigences"]["C0_statique_min_N"] = C0_min
            rapport["exigences"]["facteur_securite_stat"] = fs0
        elif P0 is not None and self.facteur_securite_stat is None:
            _push_inconnue(
                rapport,
                "partielles",
                "C0_statique_min_N",
                "Calculable si facteur_securite_stat est fourni.",
            )

        # 7) Vérification d'une référence commerciale (si renseignée)
        verif: Dict[str, Any] = {"ok": None, "details": {}, "dimensions": {}}

        if self.d_interieur_m is not None:
            d = _req_pos("d_interieur_m", self.d_interieur_m)
            verif["dimensions"]["d_interieur_m"] = d
            # cohérence avec maneton : sans jeu/fits définis, on ne peut pas conclure, mais on peut comparer nominal.
            if d_maneton is not None:
                verif["details"]["coherence_maneton_nominale"] = {"d_interieur_m": d, "diametre_maneton_m": d_maneton, "ecart_m": d - d_maneton}
                rapport["notes_modele"].append(
                    "Comparaison nominale d_interieur vs maneton faite. Les ajustements (jeu/serrage) dépendent des fits fabricant/ISO : non inventés."
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "d_interieur_m",
                "Requis pour valider l'interface maneton.",
            )

        if self.D_exterieur_m is not None:
            D = _req_pos("D_exterieur_m", self.D_exterieur_m)
            verif["dimensions"]["D_exterieur_m"] = D
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "D_exterieur_m",
                "Requis pour définir l'alésage de la grande tête (logement roulement).",
            )

        if self.B_largeur_m is not None:
            B = _req_pos("B_largeur_m", self.B_largeur_m)
            verif["dimensions"]["B_largeur_m"] = B
            if L_portee is not None:
                verif["details"]["coherence_largeur_portee"] = {"B_largeur_m": B, "largeur_portee_m": L_portee, "marge_m": L_portee - B}
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "B_largeur_m",
                "Requis pour vérifier la largeur disponible dans la grande tête.",
            )

        # Vérif dynamique C
        if self.C_dynamique_N is not None and "C_dynamique_min_N" in rapport["exigences"]:
            C = _req_pos("C_dynamique_N", self.C_dynamique_N)
            Cmin = float(rapport["exigences"]["C_dynamique_min_N"])
            verif["details"]["dynamique"] = {"C_N": C, "C_min_N": Cmin, "ok": C >= Cmin, "marge": (C / Cmin) if Cmin > 0 else None}
        elif self.C_dynamique_N is None and "C_dynamique_min_N" in rapport["exigences"]:
            _push_inconnue(
                rapport,
                "partielles",
                "verification_C",
                "Fournir C_dynamique_N du roulement (catalogue) pour vérifier.",
            )

        # Vérif statique C0
        if self.C0_statique_N is not None and "C0_statique_min_N" in rapport["exigences"]:
            C0 = _req_pos("C0_statique_N", self.C0_statique_N)
            C0min = float(rapport["exigences"]["C0_statique_min_N"])
            verif["details"]["statique"] = {"C0_N": C0, "C0_min_N": C0min, "ok": C0 >= C0min, "marge": (C0 / C0min) if C0min > 0 else None}
        elif self.C0_statique_N is None and "C0_statique_min_N" in rapport["exigences"]:
            _push_inconnue(
                rapport,
                "partielles",
                "verification_C0",
                "Fournir C0_statique_N du roulement (catalogue) pour vérifier.",
            )

        # Vérif vitesse
        if self.vitesse_limite_rpm is not None and rpm is not None:
            vmax = _req_pos("vitesse_limite_rpm", self.vitesse_limite_rpm)
            verif["details"]["vitesse"] = {"rpm_service": rpm, "rpm_limite": vmax, "ok": rpm <= vmax, "marge": (vmax / rpm) if rpm > 0 else None}
        elif self.vitesse_limite_rpm is None and rpm is not None:
            _push_inconnue(
                rapport,
                "partielles",
                "vitesse_limite_rpm",
                "Fournir la vitesse limite fabricant pour valider.",
            )

        # Vérif pression moyenne projetée (si d et B connus)
        if P is not None and self.d_interieur_m is not None and self.B_largeur_m is not None:
            p_proj = _pression_moyenne_proj(float(P), float(_req_pos("d_interieur_m", self.d_interieur_m)), float(_req_pos("B_largeur_m", self.B_largeur_m)))
            verif["details"]["pression_proj"] = {"pression_moyenne_pa": p_proj, "pression_admissible_pa": self.pression_admissible_pa}
            if self.pression_admissible_pa is not None:
                padm = _req_pos("pression_admissible_pa", self.pression_admissible_pa)
                verif["details"]["pression_proj"]["ok"] = p_proj <= padm
                verif["details"]["pression_proj"]["marge"] = (padm / p_proj) if p_proj > 0 else None
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "pression_admissible_pa",
                    "Fournir une pression admissible (fabricant / conception) si tu veux conclure sur la pression.",
                )

        # Déterminer ok global si assez d'infos
        # (On ne force pas : si manque des blocs -> ok reste None)
        oks = []
        for k in ("dynamique", "statique", "vitesse"):
            if k in verif["details"] and isinstance(verif["details"][k], dict) and "ok" in verif["details"][k]:
                oks.append(bool(verif["details"][k]["ok"]))
        if oks:
            verif["ok"] = all(oks)

        rapport["verification_reference"] = verif

        # 8) Interface bielle : ce que la bielle doit accepter (adaptation au commerce)
        # - alésage logement ~ D
        # - largeur dispo >= B
        # - maneton nominal ~ d
        rapport["interface_bielle"] = {
            "diametre_maneton_m": d_maneton,
            "largeur_portee_grande_tete_m": L_portee,
            "si_reference_choisie": {
                "d_interieur_m": self.d_interieur_m,
                "D_exterieur_m": self.D_exterieur_m,
                "B_largeur_m": self.B_largeur_m,
                "implications": [
                    "Maneton nominal ≈ d_interieur (ajustements non calculés sans fits/jeux).",
                    "Alésage grande tête (logement) ≈ D_exterieur (ajustements non calculés sans fits/serrages).",
                    "Largeur grande tête disponible >= B (sinon, géométrie bielle à revoir).",
                ],
            },
        }

        # 9) Trace entrées
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


# =============================================================================
# Exemple d'usage (à supprimer en prod)
# =============================================================================
if __name__ == "__main__":
    # Exemple : on se branche sur une bielle si disponible
    try:
        from backend.pieces.corps_bielle import CorpsBielle  # type: ignore
        bielle = CorpsBielle(
            # Si ton CorpsBielle sait déduire Fmax depuis piston, tu peux juste lui passer piston.
            force_axiale_max_N=12000.0,  # sinon, fournir directement
            diametre_maneton_m=0.03,
            longueur_portee_grande_tete_m=0.02,
        )
    except Exception:
        bielle = None

    r = RoulementAiguilleArbreVilebrequin(
        corps_bielle=bielle,
        rpm_vilebrequin=3000.0,
        vie_cible_heures=1000.0,
        facteur_application_Ka=1.2,

        # Quand tu auras ta pièce du commerce, tu rempliras ça :
        # d_interieur_m=0.03,
        # D_exterieur_m=0.037,
        # B_largeur_m=0.02,
        # C_dynamique_N=28000.0,
        # C0_statique_N=45000.0,
        # vitesse_limite_rpm=9000.0,
    )

    from pprint import pprint
    pprint(r.calculer(strict=False))
