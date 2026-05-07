# backend/pieces/joint_deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
import math

# ============================================================
# Imports projet (optionnels) — cohérence avec autres pièces
# ============================================================

# Matériaux génériques projet
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None


# Déplaceur
try:
    from backend.components.moteur_thermique.pieces.deplaceur import Deplaceur  # type: ignore
except Exception:  # pragma: no cover
    Deplaceur = None  # type: ignore


# Cylindre
try:
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre  # type: ignore
except Exception:  # pragma: no cover
    Cylindre = None  # type: ignore


# ============================================================
# Helpers robustes
# ============================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


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


def _req_int_ge(name: str, x: Any, *, min_value: int = 0) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return int(x)


def _borne(x: float, xmin: float, xmax: float) -> float:
    return max(float(xmin), min(float(xmax), float(x)))


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
# Géométrie : modèles explicites
# ============================================================

OrientationJointDeplaceur = Literal["gorge_externe_sur_deplaceur"]


def perimetre_cercle(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return math.pi * D


def aire_disque(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    r = 0.5 * D
    return math.pi * r * r


def aire_section_joint_torique(section_joint_m: float) -> float:
    d = _req_pos("section_joint_m", section_joint_m)
    return math.pi * (0.5 * d) ** 2


def volume_joint_torique_approx(
    *,
    diametre_centreline_m: float,
    section_joint_m: float,
) -> float:
    Dc = _req_pos("diametre_centreline_m", diametre_centreline_m)
    A = aire_section_joint_torique(section_joint_m)
    return A * perimetre_cercle(Dc)


def profondeur_gorge_depuis_squeeze(section_joint_m: float, squeeze: float) -> float:
    s = _req_pos("section_joint_m", section_joint_m)
    sq = _req_pos("squeeze", squeeze, strictly=False)
    if not (0.0 < sq < 1.0):
        raise ValueError("squeeze doit être dans (0,1).")
    return s * (1.0 - sq)


def largeur_gorge_depuis_facteur(section_joint_m: float, facteur_largeur: float) -> float:
    s = _req_pos("section_joint_m", section_joint_m)
    f = _req_pos("facteur_largeur", facteur_largeur)
    return f * s


def volume_gorge_annulaire_rect(
    *,
    diametre_fond_gorge_m: float,
    largeur_gorge_m: float,
    profondeur_gorge_m: float,
) -> float:
    Df = _req_pos("diametre_fond_gorge_m", diametre_fond_gorge_m)
    w = _req_pos("largeur_gorge_m", largeur_gorge_m)
    t = _req_pos("profondeur_gorge_m", profondeur_gorge_m)
    return perimetre_cercle(Df) * w * t


def jeu_radial_depuis_alesage_et_deplaceur(alesage_m: float, diametre_deplaceur_m: float) -> float:
    Dc = _req_pos("alesage_m", alesage_m)
    Dd = _req_pos("diametre_deplaceur_m", diametre_deplaceur_m)
    return 0.5 * (Dc - Dd)


def _calcul_positions_rainures(
    *,
    longueur_deplaceur_m: float,
    nb_joints: int,
    largeur_rainure_m: float,
    marge_extremite_m: float,
    entraxe_min_m: float,
) -> List[float]:
    L = _req_pos("longueur_deplaceur_m", longueur_deplaceur_m)
    n = _req_int_ge("nb_joints", nb_joints, min_value=1)
    w = _req_pos("largeur_rainure_m", largeur_rainure_m)
    m = _req_pos("marge_extremite_m", marge_extremite_m, strictly=False)
    e = _req_pos("entraxe_min_m", entraxe_min_m, strictly=False)

    if (2.0 * m + n * w) > L:
        raise ValueError("Longueur insuffisante pour placer les rainures avec les marges imposées.")

    if n == 1:
        return [0.5 * L]

    x1 = m + 0.5 * w
    x2 = L - m - 0.5 * w

    if n == 2:
        if (x2 - x1) < max(e, w):
            raise ValueError("Longueur insuffisante pour placer 2 rainures avec la marge/entraxe imposés.")
        return [x1, x2]

    pas = (x2 - x1) / (n - 1)
    if pas < max(e, w):
        raise ValueError("Entraxe insuffisant entre rainures.")
    return [x1 + i * pas for i in range(n)]


# ============================================================
# Extraction depuis pièces projet
# ============================================================

def _extraire_rapport_piece(obj: Any) -> Optional[Dict[str, Any]]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "analyser") and callable(getattr(obj, "analyser")):
        try:
            rep = obj.analyser(strict=False)  # type: ignore[call-arg]
            return rep if isinstance(rep, dict) else None
        except Exception:
            return None
    return None


def _extraire_depuis_deplaceur(deplaceur: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "diametre_exterieur_m": None,
        "longueur_totale_m": None,
        "nb_joints": None,
        "section_joint_mm": None,
        "squeeze": None,
        "pression_chaud_pa": None,
        "pression_froid_pa": None,
        "delta_p_chaud_froid_pa": None,
        "pression_service_pa": None,
        "positions_axiales_rainures_m": None,
        "largeur_rainure_m": None,
        "profondeur_rainure_m": None,
        "diametre_fond_rainure_m": None,
        "rayon_fond_rainure_m": None,
    }

    if deplaceur is None:
        return out

    # attributs directs
    for attr_src, attr_dst in (
        ("diametre_exterieur_m", "diametre_exterieur_m"),
        ("longueur_totale_m", "longueur_totale_m"),
        ("nb_joints", "nb_joints"),
        ("section_joint_mm", "section_joint_mm"),
        ("taux_compression_joint", "squeeze"),
        ("pression_chaud_pa", "pression_chaud_pa"),
        ("pression_froid_pa", "pression_froid_pa"),
        ("delta_p_chaud_froid_pa", "delta_p_chaud_froid_pa"),
    ):
        if hasattr(deplaceur, attr_src):
            v = getattr(deplaceur, attr_src)
            if v is not None:
                out[attr_dst] = v

    rep = _extraire_rapport_piece(deplaceur)
    if isinstance(rep, dict):
        press = rep.get("pressions", {}) if isinstance(rep.get("pressions", {}), dict) else {}
        etan = rep.get("etancheite", {}) if isinstance(rep.get("etancheite", {}), dict) else {}
        geo = rep.get("geometrie", {}) if isinstance(rep.get("geometrie", {}), dict) else {}
        cao = geo.get("cao", {}) if isinstance(geo.get("cao", {}), dict) else {}
        rain = cao.get("rainures_joints", {}) if isinstance(cao.get("rainures_joints", {}), dict) else {}

        for k_src, k_dst in (
            ("pression_chaud_pa", "pression_chaud_pa"),
            ("pression_froid_pa", "pression_froid_pa"),
            ("delta_p_chaud_froid_pa", "delta_p_chaud_froid_pa"),
        ):
            if out[k_dst] is None and press.get(k_src) is not None:
                out[k_dst] = press[k_src]

        if out["section_joint_mm"] is None and etan.get("section_joint_mm") is not None:
            out["section_joint_mm"] = etan["section_joint_mm"]
        if out["squeeze"] is None and etan.get("taux_compression") is not None:
            out["squeeze"] = etan["taux_compression"]
        if out["nb_joints"] is None and etan.get("nb_joints") is not None:
            out["nb_joints"] = etan["nb_joints"]

        for k in (
            "positions_axiales_rainures_m",
            "largeur_rainure_m",
            "profondeur_rainure_m",
            "diametre_fond_rainure_m",
            "rayon_fond_rainure_m",
        ):
            if rain.get(k) is not None:
                out[k] = rain[k]
            elif etan.get(k) is not None:
                out[k] = etan[k]

        # pression_service de repli
        candidates: List[float] = []
        for k in ("pression_chaud_pa", "pression_froid_pa"):
            v = out.get(k)
            if _is_finite(v):
                candidates.append(abs(float(v)))
        if candidates:
            out["pression_service_pa"] = max(candidates)
        elif _is_finite(out.get("delta_p_chaud_froid_pa")):
            out["pression_service_pa"] = abs(float(out["delta_p_chaud_froid_pa"]))

    return out


def _extraire_depuis_cylindre(cylindre: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "alesage_m": None,
        "pression_service_pa": None,
        "pression_max_pa": None,
    }
    if cylindre is None:
        return out

    if hasattr(cylindre, "alesage_m"):
        v = getattr(cylindre, "alesage_m")
        if v is not None:
            out["alesage_m"] = v
    for attr in ("pression_service_pa", "pression_max_pa"):
        if hasattr(cylindre, attr):
            v = getattr(cylindre, attr)
            if v is not None:
                out[attr] = v

    rep = _extraire_rapport_piece(cylindre)
    if isinstance(rep, dict):
        ent = rep.get("entrees", {}) if isinstance(rep.get("entrees", {}), dict) else {}
        if out["alesage_m"] is None and ent.get("alesage_m") is not None:
            out["alesage_m"] = ent["alesage_m"]
        if out["pression_service_pa"] is None and ent.get("pression_service_pa") is not None:
            out["pression_service_pa"] = ent["pression_service_pa"]
        if out["pression_max_pa"] is None and ent.get("pression_max_pa") is not None:
            out["pression_max_pa"] = ent["pression_max_pa"]

    return out


# ============================================================
# Règles explicites rainures / frottement
# ============================================================

@dataclass(frozen=True)
class ReglesRainuresJointDeplaceur:
    marge_extremite_m: float = 0.004
    entraxe_min_m: float = 0.006
    coefficient_rayon_fond: float = 0.15


# ============================================================
# Pièce : Joint torique du Déplaceur
# ============================================================

@dataclass(frozen=True)
class JointDeplaceur:
    """
    Joint(s) toriques du déplaceur.

    Le module peut :
    - récupérer les données depuis un Deplaceur mis à jour,
    - recalculer la section de rainure,
    - définir les positions axiales des rainures,
    - sortir un bloc CAO exploitable.
    """

    # --- Références (optionnelles) ---
    deplaceur: Optional[Any] = None
    cylindre: Optional[Any] = None

    # --- Données minimales (si pas d'objets) ---
    diametre_deplaceur_m: Optional[float] = None
    longueur_deplaceur_m: Optional[float] = None
    alesage_cylindre_m: Optional[float] = None
    jeu_radial_m: Optional[float] = None

    # --- Nombre de joints ---
    nb_joints: Optional[int] = None

    # --- Données joint ---
    section_joint_mm: Optional[float] = None
    squeeze: Optional[float] = None
    facteur_largeur: Optional[float] = None

    # --- Orientation du montage ---
    orientation: OrientationJointDeplaceur = "gorge_externe_sur_deplaceur"

    # --- Pression de service ---
    pression_service_pa: Optional[float] = None

    # --- Matériau joint (optionnel) ---
    materiau_joint_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"
    module_elastomere_pa: Optional[float] = None

    # --- Frottement (optionnel) ---
    coeff_frottement: Optional[float] = None
    largeur_bande_contact_m: Optional[float] = None

    # --- Règles rainures ---
    regles_rainures: ReglesRainuresJointDeplaceur = ReglesRainuresJointDeplaceur()

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "liaisons_pieces": {},
            "geometrie": {},
            "gorge": {},
            "service": {},
            "materiau": {},
            "elasticite": {},
            "frottement": {},
            "cao": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ------------------------------------------------------------
        # 1) Collecte depuis pièces
        # ------------------------------------------------------------
        dep = _extraire_depuis_deplaceur(self.deplaceur)
        cyl = _extraire_depuis_cylindre(self.cylindre)

        D_dep = self.diametre_deplaceur_m
        if D_dep is None and dep["diametre_exterieur_m"] is not None:
            D_dep = dep["diametre_exterieur_m"]

        L_dep = self.longueur_deplaceur_m
        if L_dep is None and dep["longueur_totale_m"] is not None:
            L_dep = dep["longueur_totale_m"]

        Dcyl = self.alesage_cylindre_m
        if Dcyl is None and cyl["alesage_m"] is not None:
            Dcyl = cyl["alesage_m"]

        jeu = self.jeu_radial_m
        if jeu is None and (Dcyl is not None) and (D_dep is not None):
            jeu = jeu_radial_depuis_alesage_et_deplaceur(Dcyl, D_dep)

        nb_j = self.nb_joints
        if nb_j is None and dep["nb_joints"] is not None:
            nb_j = dep["nb_joints"]

        sec_mm = self.section_joint_mm
        if sec_mm is None and dep["section_joint_mm"] is not None:
            sec_mm = dep["section_joint_mm"]

        sq = self.squeeze
        if sq is None and dep["squeeze"] is not None:
            sq = dep["squeeze"]

        p_service = self.pression_service_pa
        if p_service is None and dep["pression_service_pa"] is not None:
            p_service = dep["pression_service_pa"]
            rapport["notes_modele"].append("pression_service_pa déduite depuis le déplaceur.")
        if p_service is None and cyl["pression_service_pa"] is not None:
            p_service = cyl["pression_service_pa"]
            rapport["notes_modele"].append("pression_service_pa déduite depuis le cylindre (pression_service_pa).")
        if p_service is None and cyl["pression_max_pa"] is not None:
            p_service = cyl["pression_max_pa"]
            rapport["notes_modele"].append("pression_service_pa déduite depuis le cylindre (pression_max_pa).")

        rapport["liaisons_pieces"]["deplaceur"] = dep
        rapport["liaisons_pieces"]["cylindre"] = cyl

        # ------------------------------------------------------------
        # 2) Validation minimale
        # ------------------------------------------------------------
        if D_dep is None:
            _push_inconnue(rapport, "impossibles", "diametre_deplaceur_m", "Fournir diametre_deplaceur_m ou un Deplaceur exploitable.")
        else:
            D_dep = _req_pos("diametre_deplaceur_m", D_dep)

        if L_dep is None:
            _push_inconnue(rapport, "partielles", "longueur_deplaceur_m", "Nécessaire pour placer axialement les rainures.")
        else:
            L_dep = _req_pos("longueur_deplaceur_m", L_dep)

        if Dcyl is not None:
            Dcyl = _req_pos("alesage_cylindre_m", Dcyl)

        if jeu is not None:
            jeu = _req_pos("jeu_radial_m", jeu, strictly=False)

        if nb_j is None:
            _push_inconnue(rapport, "impossibles", "nb_joints", "Fournir nb_joints ou un Deplaceur.nb_joints.")
        else:
            nb_j = _req_int_ge("nb_joints", nb_j, min_value=0)

        rapport["entrees"].update({
            "diametre_deplaceur_m": D_dep,
            "longueur_deplaceur_m": L_dep,
            "alesage_cylindre_m": Dcyl,
            "jeu_radial_m": jeu,
            "nb_joints": nb_j,
            "section_joint_mm": sec_mm,
            "squeeze": sq,
            "facteur_largeur": self.facteur_largeur,
            "orientation": self.orientation,
            "pression_service_pa": p_service,
            "materiau_joint_cle": self.materiau_joint_cle,
            "mode_materiau": self.mode_materiau,
            "module_elastomere_pa": self.module_elastomere_pa,
            "coeff_frottement": self.coeff_frottement,
            "largeur_bande_contact_m": self.largeur_bande_contact_m,
        })

        # géométrie globale
        if D_dep is not None:
            rapport["geometrie"].update({
                "perimetre_sur_diametre_deplaceur_m": perimetre_cercle(D_dep),
                "aire_face_deplaceur_m2": aire_disque(D_dep),
                "rayon_deplaceur_m": 0.5 * D_dep,
            })

        if (Dcyl is not None) and (D_dep is not None):
            rapport["verifications"]["compatibilite_cylindre_deplaceur"] = {
                "alesage_cylindre_m": Dcyl,
                "diametre_deplaceur_m": D_dep,
                "jeu_radial_calcule_m": 0.5 * (Dcyl - D_dep),
                "ok_si_alesage_superieur": (Dcyl >= D_dep),
            }

        # ------------------------------------------------------------
        # 3) Section joint / squeeze / largeur gorge
        # ------------------------------------------------------------
        section_m: Optional[float] = None
        if sec_mm is None:
            _push_inconnue(rapport, "impossibles", "section_joint_mm", "Non déductible sans donnée explicite ou Deplaceur.section_joint_mm.")
        else:
            section_m = _req_pos("section_joint_mm", sec_mm) * 1e-3
            rapport["geometrie"]["section_joint_m"] = section_m
            rapport["geometrie"]["aire_section_joint_m2"] = aire_section_joint_torique(section_m)

        if sq is None:
            _push_inconnue(rapport, "impossibles", "squeeze", "Fournir squeeze ou Deplaceur.taux_compression_joint.")
        else:
            sq = _req_pos("squeeze", sq, strictly=False)
            if not (0.0 < sq < 1.0):
                _push_inconnue(rapport, "impossibles", "squeeze", "Doit être dans (0,1).")

        fL = self.facteur_largeur
        if fL is None:
            _push_inconnue(rapport, "partielles", "facteur_largeur", "Nécessaire pour calculer largeur_gorge.")
        else:
            fL = _req_pos("facteur_largeur", fL)

        # ------------------------------------------------------------
        # 4) Gorge : profondeur / largeur / protrusion / D fond
        # ------------------------------------------------------------
        profondeur: Optional[float] = None
        largeur: Optional[float] = None
        protrusion: Optional[float] = None
        D_fond: Optional[float] = None
        rayon_fond: Optional[float] = None
        D_centreline: Optional[float] = None

        if (section_m is not None) and (sq is not None) and (0.0 < sq < 1.0):
            profondeur = profondeur_gorge_depuis_squeeze(section_m, sq)
            protrusion = section_m - profondeur
            rayon_fond = self.regles_rainures.coefficient_rayon_fond * profondeur

            rapport["gorge"].update({
                "profondeur_gorge_radiale_m": profondeur,
                "protrusion_radiale_theorique_m": protrusion,
                "rayon_fond_gorge_m": rayon_fond,
                "definition": "profondeur = section*(1-squeeze), protrusion = section - profondeur",
            })
        else:
            _push_inconnue(rapport, "impossibles", "profondeur_gorge", "Impossible sans section_joint et squeeze valides.")

        if (section_m is not None) and (fL is not None):
            largeur = largeur_gorge_depuis_facteur(section_m, fL)
            rapport["gorge"]["largeur_gorge_axiale_m"] = largeur
        else:
            _push_inconnue(rapport, "partielles", "largeur_gorge_m", "Calculable si section_joint et facteur_largeur sont fournis.")

        if self.orientation == "gorge_externe_sur_deplaceur":
            if (D_dep is not None) and (profondeur is not None):
                D_fond = D_dep - 2.0 * profondeur
                if D_fond <= 0:
                    _push_inconnue(rapport, "impossibles", "diametre_fond_gorge_m", "D_fond <= 0 (géométrie impossible).")
                else:
                    D_centreline = D_fond + section_m if section_m is not None else None
                    rapport["gorge"]["diametre_fond_gorge_m"] = D_fond
                    if D_centreline is not None:
                        rapport["gorge"]["diametre_centreline_joint_m"] = D_centreline
                    rapport["notes_modele"].append(
                        "D_fond déduit avec hypothèse: gorge externe sur OD du déplaceur (D_fond = D_dep - 2*profondeur)."
                    )
            else:
                _push_inconnue(rapport, "partielles", "diametre_fond_gorge_m", "Calculable si D_dep et profondeur_gorge connus.")
        else:
            _push_inconnue(rapport, "impossibles", "orientation", "Orientation non supportée.")

        # ------------------------------------------------------------
        # 5) Position axiale des rainures
        # ------------------------------------------------------------
        positions_rainures = dep.get("positions_axiales_rainures_m")
        if positions_rainures is None and (L_dep is not None) and (largeur is not None) and (nb_j is not None) and (nb_j > 0):
            try:
                positions_rainures = _calcul_positions_rainures(
                    longueur_deplaceur_m=L_dep,
                    nb_joints=nb_j,
                    largeur_rainure_m=largeur,
                    marge_extremite_m=self.regles_rainures.marge_extremite_m,
                    entraxe_min_m=self.regles_rainures.entraxe_min_m,
                )
                rapport["notes_modele"].append("Positions axiales des rainures calculées automatiquement sur la longueur du déplaceur.")
            except Exception as e:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "positions_axiales_rainures_m",
                    f"Impossible de placer axialement les rainures: {e!r}",
                )

        if positions_rainures is not None:
            rapport["gorge"]["positions_axiales_rainures_m"] = positions_rainures

        # ------------------------------------------------------------
        # 6) Vérification radiale avec cylindre
        # ------------------------------------------------------------
        if (Dcyl is not None) and (D_dep is not None) and (protrusion is not None):
            clearance = 0.5 * (Dcyl - D_dep)
            rapport["verifications"]["jeu_radial_m"] = clearance
            rapport["verifications"]["protrusion_radiale_m"] = protrusion
            rapport["verifications"]["protrusion_compatible_avec_jeu"] = (protrusion <= clearance)
            rapport["verifications"]["gap_radial_residuel_apres_contact_m"] = max(0.0, clearance - protrusion)
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "verification_radiale",
                "Vérif protrusion<=jeu calculable si alésage cylindre + D_dep + profondeur sont disponibles.",
            )

        # ------------------------------------------------------------
        # 7) Volumes : gorge vs joint
        # ------------------------------------------------------------
        if (nb_j is not None) and (nb_j > 0):
            if (D_fond is not None) and (largeur is not None) and (profondeur is not None) and (section_m is not None) and (D_centreline is not None):
                V_gorge_1 = volume_gorge_annulaire_rect(
                    diametre_fond_gorge_m=D_fond,
                    largeur_gorge_m=largeur,
                    profondeur_gorge_m=profondeur,
                )
                V_joint_1 = volume_joint_torique_approx(
                    diametre_centreline_m=D_centreline,
                    section_joint_m=section_m,
                )
                taux_remplissage = (V_joint_1 / V_gorge_1) if V_gorge_1 > 0 else None

                rapport["geometrie"].update({
                    "volume_gorge_unitaire_m3": V_gorge_1,
                    "volume_gorges_total_m3": V_gorge_1 * nb_j,
                    "diametre_centreline_joint_m": D_centreline,
                    "volume_joint_unitaire_approx_m3": V_joint_1,
                    "volume_joints_total_approx_m3": V_joint_1 * nb_j,
                    "taux_remplissage_gorge_approx": taux_remplissage,
                    "note_volume_joint": "Volume joint: tore parfait (sans aplatissement). Volume gorge: rectangle annulaire.",
                })

                rapport["verifications"]["taux_remplissage_gorge_acceptable"] = (
                    (taux_remplissage <= 0.85) if taux_remplissage is not None else None
                )
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "volumes_gorge_joint",
                    "Calculables si D_fond + largeur + profondeur + section sont disponibles.",
                )

        # ------------------------------------------------------------
        # 8) Contraintes mécaniques => exigences matériau
        # ------------------------------------------------------------
        if p_service is None:
            _push_inconnue(
                rapport,
                "partielles",
                "pression_service_pa",
                "Requise pour calculer les exigences mécaniques du matériau.",
            )
        else:
            p_service = _req_pos("pression_service_pa", p_service, strictly=False)
            rapport["service"]["pression_service_pa"] = p_service

            if (sq is not None) and (0.0 < sq < 1.0):
                E_min = p_service / sq
                rapport["elasticite"]["module_min_pour_p_contact_ge_p_service_pa"] = E_min
                rapport["notes_modele"].append("Exigence module (simplifiée): p_contact ≈ E*squeeze => E_min = p_service/squeeze.")
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "module_min",
                    "Calculable si squeeze est fourni et valide.",
                )

        # Module réel du matériau
        E_elast = self.module_elastomere_pa
        if (E_elast is None) and self.materiau_joint_cle and (get_materiau is not None):
            try:
                mat = get_materiau(self.materiau_joint_cle)
                if mat is None:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "materiau_joint_cle",
                        f"Matériau '{self.materiau_joint_cle}' introuvable dans backend.ensemble.materiaux.",
                    )
                else:
                    E_elast = valeur(getattr(mat, "module_young_pa", None), mode=self.mode_materiau)
                    rapport["materiau"]["materiau_joint_nom"] = getattr(mat, "nom", self.materiau_joint_cle)
                    rapport["materiau"]["module_young_pa"] = E_elast
            except Exception as e:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "materiau_joint_cle",
                    f"Impossible d'exploiter materiau_joint_cle={self.materiau_joint_cle!r}: {e!r}",
                )

        if E_elast is not None:
            E_elast = _req_pos("module_elastomere_pa", E_elast)
            rapport["elasticite"]["module_elastomere_pa"] = E_elast
            if (sq is not None) and (0.0 < sq < 1.0):
                p_contact_est = E_elast * sq
                rapport["elasticite"]["pression_contact_estimee_pa"] = p_contact_est
                if p_service is not None:
                    rapport["elasticite"]["marge_p_contact_vs_service"] = (p_contact_est / p_service) if p_service > 0 else None
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "pression_contact_estimee",
                    "Calculable si squeeze est fourni et valide.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "module_elastomere_pa",
                "Fournir module_elastomere_pa ou un materiau_joint_cle exploitable pour estimer p_contact.",
            )

        # ------------------------------------------------------------
        # 9) Frottement
        # ------------------------------------------------------------
        if (nb_j is not None) and (nb_j > 0) and (D_dep is not None):
            p_contact = rapport["elasticite"].get("pression_contact_estimee_pa", None)
            if p_contact is None:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "frottement",
                    "Nécessite pression_contact_estimee_pa.",
                )
            else:
                if self.coeff_frottement is None or self.largeur_bande_contact_m is None:
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "frottement",
                        "Calculable si coeff_frottement et largeur_bande_contact_m sont fournis.",
                    )
                else:
                    mu = _req_pos("coeff_frottement", self.coeff_frottement, strictly=False)
                    b = _req_pos("largeur_bande_contact_m", self.largeur_bande_contact_m)
                    perim = perimetre_cercle(D_dep)
                    A_contact = perim * b * nb_j
                    Ff = mu * float(p_contact) * A_contact
                    rapport["frottement"].update({
                        "perimetre_contact_m": perim,
                        "aire_contact_m2": A_contact,
                        "force_frottement_N": Ff,
                        "modele": "F = mu * p_contact * (perimetre * bande * nb_joints)",
                    })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "frottement",
                "Calculable si nb_joints, D_dep, et pression_contact estimée sont disponibles.",
            )

        # ------------------------------------------------------------
        # 10) Bloc CAO
        # ------------------------------------------------------------
        rapport["cao"] = {
            "orientation": self.orientation,
            "diametre_deplaceur_m": D_dep,
            "longueur_deplaceur_m": L_dep,
            "nb_joints": nb_j,
            "section_joint_mm": sec_mm,
            "section_joint_m": section_m,
            "squeeze": sq,
            "largeur_gorge_m": largeur,
            "profondeur_gorge_m": profondeur,
            "diametre_fond_gorge_m": D_fond,
            "rayon_fond_gorge_m": rayon_fond,
            "diametre_centreline_joint_m": D_centreline,
            "positions_axiales_rainures_m": positions_rainures,
            "marge_extremite_m": self.regles_rainures.marge_extremite_m,
            "entraxe_min_m": self.regles_rainures.entraxe_min_m,
        }

        # ------------------------------------------------------------
        # 11) Mode strict
        # ------------------------------------------------------------
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
        diametre_deplaceur_m=0.080,
        longueur_deplaceur_m=0.120,
        alesage_cylindre_m=0.0804,   # => jeu 0.2 mm
        nb_joints=2,
        section_joint_mm=3.0,
        squeeze=0.20,
        facteur_largeur=1.5,
        pression_service_pa=150_000.0,
        module_elastomere_pa=7e6,
        coeff_frottement=0.15,
        largeur_bande_contact_m=0.003,
    )

    from pprint import pprint
    pprint(j.analyser(strict=False))