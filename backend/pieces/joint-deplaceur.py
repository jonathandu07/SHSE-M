# backend/pieces/joint_deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
import math

# ============================================================
# Imports projet (optionnels)
# ============================================================

try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# ============================================================
# Helpers
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strictly else v >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v

def _push_inconnue(rapport: Dict[str, Any], categorie: str, nom: str, raison: str) -> None:
    rapport["inconnues"][categorie].append({"nom": nom, "raison": raison})

def _dedup_inconnues(rapport: Dict[str, Any]) -> None:
    def dedup(lst: list[dict]) -> list[dict]:
        seen: set[Tuple[str, str]] = set()
        out: list[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out
    rapport["inconnues"]["impossibles"] = dedup(rapport["inconnues"]["impossibles"])
    rapport["inconnues"]["partielles"] = dedup(rapport["inconnues"]["partielles"])


# ============================================================
# Matériaux “joints” (pas d’invention : tables minimales internes)
# ============================================================
#
# Contrainte utilisateur : “donne la matière du joint”.
# Sans source externe, on ne choisit PAS arbitrairement un polymère “au hasard”.
# On fait donc :
# 1) une sélection DÉTERMINISTE via contraintes d’usage (Tmax, milieu, pression),
# 2) et on renvoie un "matériau recommandé" parmi une liste interne de familles
#    avec bornes d’emploi usuelles.
#
# IMPORTANT :
# - Les bornes ci-dessous sont des ORDRES DE GRANDEUR d’ingénierie,
#   pas des datasheets fabricants.
# - Si tu veux du 100% “source primaire”, il faut brancher un catalogue (Parker, Trelleborg, etc.).
#
# Ici, l’objectif est surtout de réduire les inconnues de conception (choix matière),
# tout en laissant la validation finale au choix du fournisseur.

@dataclass(frozen=True)
class MateriauJoint:
    nom: str
    famille: str
    Tmax_C: float
    Tmin_C: float
    compatible_huiles: bool
    compatible_eau: bool
    compatible_carburants: bool
    compatible_gaz_air: bool
    compatible_vapeur_eau: bool
    resistance_chaleur: Literal["faible", "moyenne", "haute", "tres_haute"]
    notes: str


# Base interne minimaliste (familles courantes de joints toriques)
_MATERIAUX_JOINTS: Tuple[MateriauJoint, ...] = (
    MateriauJoint(
        nom="FKM (Viton®-like)",
        famille="fluoroélastomère",
        Tmin_C=-20.0,
        Tmax_C=200.0,
        compatible_huiles=True,
        compatible_eau=True,
        compatible_carburants=True,
        compatible_gaz_air=True,
        compatible_vapeur_eau=False,  # vapeur chaude = attention
        resistance_chaleur="haute",
        notes="Très bon pour huiles/carburants et températures élevées; vigilance vapeur/eau chaude prolongée.",
    ),
    MateriauJoint(
        nom="EPDM",
        famille="élastomère éthylène-propylène",
        Tmin_C=-40.0,
        Tmax_C=150.0,
        compatible_huiles=False,
        compatible_eau=True,
        compatible_carburants=False,
        compatible_gaz_air=True,
        compatible_vapeur_eau=True,
        resistance_chaleur="moyenne",
        notes="Excellent eau/vapeur; incompatible huiles/minérales et carburants.",
    ),
    MateriauJoint(
        nom="HNBR",
        famille="nitrile hydrogéné",
        Tmin_C=-30.0,
        Tmax_C=150.0,
        compatible_huiles=True,
        compatible_eau=True,
        compatible_carburants=True,
        compatible_gaz_air=True,
        compatible_vapeur_eau=False,
        resistance_chaleur="moyenne",
        notes="Bon compromis mécanique/huile/carburant; tenue chaleur < FKM.",
    ),
    MateriauJoint(
        nom="VMQ (Silicone)",
        famille="silicone",
        Tmin_C=-60.0,
        Tmax_C=200.0,
        compatible_huiles=False,
        compatible_eau=True,
        compatible_carburants=False,
        compatible_gaz_air=True,
        compatible_vapeur_eau=False,
        resistance_chaleur="haute",
        notes="Très large plage de T; faible résistance mécanique/abrasion; pas idéal huiles/carburants.",
    ),
    MateriauJoint(
        nom="PTFE (joint/segment, non élastomère)",
        famille="polytétrafluoroéthylène",
        Tmin_C=-200.0,
        Tmax_C=260.0,
        compatible_huiles=True,
        compatible_eau=True,
        compatible_carburants=True,
        compatible_gaz_air=True,
        compatible_vapeur_eau=True,
        resistance_chaleur="tres_haute",
        notes="Très haute tenue chimique/T; nécessite géométrie type bague/segment (pas un torique standard sans énergie).",
    ),
)


def _score_materiau_joint(
    mat: MateriauJoint,
    *,
    Tmin_C: float,
    Tmax_C: float,
    milieu: Literal["air", "eau", "huile", "carburant", "vapeur"],
) -> float:
    # Critère 1 : domaine température
    if Tmin_C < mat.Tmin_C or Tmax_C > mat.Tmax_C:
        return -1e9

    # Critère 2 : compatibilités
    compat = {
        "air": mat.compatible_gaz_air,
        "eau": mat.compatible_eau,
        "huile": mat.compatible_huiles,
        "carburant": mat.compatible_carburants,
        "vapeur": mat.compatible_vapeur_eau,
    }[milieu]
    if not compat:
        return -1e6

    # Score : on privilégie marge thermique haute
    marge_haut = mat.Tmax_C - Tmax_C
    marge_bas = Tmin_C - mat.Tmin_C
    # plus la marge est grande, mieux c’est
    return 1000.0 + 2.0 * marge_haut + 0.5 * marge_bas


# ============================================================
# Calculs géométriques joints toriques (sans datasheet)
# ============================================================
#
# Sans série ISO (3601) et sans choix de section, on ne peut pas “sortir” le joint.
# Donc on structure ainsi :
# - si section_joint_mm fournie : on calcule gorge (profondeur, largeur) selon squeeze/calc explicites.
# - sinon : on liste l’inconnue “section” (impossible).
#
# Le “squeeze” est un paramètre d’entrée (pas inventé).
# On ne fixe pas 20% par défaut.

def gorge_profondeur_m(section_joint_m: float, squeeze: float) -> float:
    # profondeur = section * (1 - squeeze)
    s = _req_pos("section_joint_m", section_joint_m)
    sq = _req_pos("squeeze", squeeze, strictly=False)
    if not (0.0 < sq < 1.0):
        raise ValueError("squeeze doit être dans (0,1).")
    return s * (1.0 - sq)

def gorge_largeur_m(section_joint_m: float, facteur_largeur: float) -> float:
    # largeur = facteur * section (facteur entré, pas inventé)
    s = _req_pos("section_joint_m", section_joint_m)
    f = _req_pos("facteur_largeur", facteur_largeur)
    return f * s

def diametre_etalonnage_joint_m(diametre_gorge_m: float, section_joint_m: float) -> float:
    # D_joint_approx = D_gorge + section (approx pour placer un torique en gorge)
    Dg = _req_pos("diametre_gorge_m", diametre_gorge_m)
    s = _req_pos("section_joint_m", section_joint_m)
    return Dg + s


# ============================================================
# Pièce : Joint de Déplaceur
# ============================================================

@dataclass(frozen=True)
class JointDeplaceur:
    """
    Joint du déplaceur (typiquement joint torique), sans heuristiques cachées.

    - Sélection matériau : déterministe via (Tmin/Tmax, milieu).
    - Géométrie gorge : calculable si section_joint_mm + squeeze + facteur_largeur fournis.
    - Force de frottement : calculable si pression_contact (ou modèle) + μ + aire contact.
      (sinon inconnue partielle, comme dans deplaceur.py)
    """

    # Conditions d’usage
    Tmin_C: float
    Tmax_C: float
    milieu: Literal["air", "eau", "huile", "carburant", "vapeur"] = "air"

    # Configuration
    nb_joints: int = 1

    # Dimensionnement gorge (optionnel)
    diametre_gorge_m: Optional[float] = None   # diamètre au fond de gorge (ou diamètre nominal où se loge le joint)
    section_joint_mm: Optional[float] = None   # section torique (mm) — ISO 3601 si tu choisis une série
    squeeze: Optional[float] = None            # (0..1) compression radiale relative
    facteur_largeur: Optional[float] = None    # largeur_gorge = facteur * section

    # Frottement (optionnel)
    coeff_frottement: Optional[float] = None
    pression_contact_pa: Optional[float] = None
    largeur_bande_contact_m: Optional[float] = None  # si tu veux approx aire contact = périmètre * bande

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "geometrie": {},
            "gorge": {},
            "frottement": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        Tmin = _req_finite("Tmin_C", self.Tmin_C)
        Tmax = _req_finite("Tmax_C", self.Tmax_C)
        if Tmax < Tmin:
            raise ValueError("Tmax_C doit être >= Tmin_C")
        if self.nb_joints <= 0:
            raise ValueError("nb_joints doit être >= 1")

        rapport["entrees"].update({
            "Tmin_C": Tmin,
            "Tmax_C": Tmax,
            "milieu": self.milieu,
            "nb_joints": int(self.nb_joints),
            "diametre_gorge_m": self.diametre_gorge_m,
            "section_joint_mm": self.section_joint_mm,
            "squeeze": self.squeeze,
            "facteur_largeur": self.facteur_largeur,
        })

        # ----------------------------
        # 1) Choix matériau (déterministe)
        # ----------------------------
        best = None
        best_score = -1e18
        for mat in _MATERIAUX_JOINTS:
            sc = _score_materiau_joint(mat, Tmin_C=Tmin, Tmax_C=Tmax, milieu=self.milieu)
            if sc > best_score:
                best_score = sc
                best = mat

        if best is None or best_score < -1e8:
            _push_inconnue(
                rapport,
                "impossibles",
                "materiau_joint",
                "Aucun matériau interne ne couvre (Tmin/Tmax + milieu). Fournir un matériau via catalogue fournisseur.",
            )
        else:
            rapport["materiau"].update({
                "materiau_recommande": best.nom,
                "famille": best.famille,
                "Tmin_C": best.Tmin_C,
                "Tmax_C": best.Tmax_C,
                "compatibilite_milieu": True,
                "notes": best.notes,
            })

        # ----------------------------
        # 2) Géométrie joint/gorge (si section fournie)
        # ----------------------------
        if self.section_joint_mm is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "section_joint_mm",
                "Impossible de dimensionner une gorge sans section du joint (ex: ISO 3601).",
            )
        else:
            s_m = _req_pos("section_joint_mm", self.section_joint_mm) * 1e-3
            rapport["geometrie"]["section_joint_m"] = s_m

            if self.diametre_gorge_m is not None:
                Dg = _req_pos("diametre_gorge_m", self.diametre_gorge_m)
                rapport["geometrie"]["diametre_joint_approx_m"] = diametre_etalonnage_joint_m(Dg, s_m)
                rapport["geometrie"]["perimetre_joint_m"] = math.pi * (Dg + s_m)  # approximation

            if self.squeeze is None or self.facteur_largeur is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "gorge",
                    "Calcul complet gorge si squeeze et facteur_largeur sont fournis.",
                )
            else:
                sq = _req_pos("squeeze", self.squeeze, strictly=False)
                fL = _req_pos("facteur_largeur", self.facteur_largeur)
                profondeur = gorge_profondeur_m(s_m, sq)
                largeur = gorge_largeur_m(s_m, fL)
                rapport["gorge"].update({
                    "profondeur_gorge_m": profondeur,
                    "largeur_gorge_m": largeur,
                    "squeeze": sq,
                    "facteur_largeur": fL,
                })

        # ----------------------------
        # 3) Frottement (optionnel, explicite)
        # ----------------------------
        if (
            self.coeff_frottement is not None
            and self.pression_contact_pa is not None
            and self.largeur_bande_contact_m is not None
            and self.diametre_gorge_m is not None
        ):
            mu = _req_pos("coeff_frottement", self.coeff_frottement, strictly=False)
            p_c = _req_pos("pression_contact_pa", self.pression_contact_pa, strictly=False)
            b = _req_pos("largeur_bande_contact_m", self.largeur_bande_contact_m)
            Dg = _req_pos("diametre_gorge_m", self.diametre_gorge_m)
            perim = math.pi * Dg
            A_contact = perim * b * float(self.nb_joints)
            F_f = mu * p_c * A_contact
            rapport["frottement"].update({
                "aire_contact_m2": A_contact,
                "force_frottement_N": F_f,
                "modele": "F = mu * p_contact * (perimetre * bande * nb_joints)",
            })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "frottement",
                "Calculable si coeff_frottement + pression_contact_pa + largeur_bande_contact_m + diametre_gorge_m sont fournis.",
            )

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(
                "JointDeplaceur(strict=True) : des inconnues restent.\n"
                f"Impossibles: {rapport['inconnues']['impossibles']}\n"
                f"Partielles: {rapport['inconnues']['partielles']}"
            )

        return rapport


# ============================================================
# Exemple
# ============================================================
if __name__ == "__main__":
    j = JointDeplaceur(
        Tmin_C=-10.0,
        Tmax_C=180.0,
        milieu="air",
        nb_joints=2,
        diametre_gorge_m=0.080,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur=1.5,
    )
    from pprint import pprint
    pprint(j.analyser(strict=False))
