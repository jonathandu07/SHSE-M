# backend/pieces/deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
import math

# ============================================================
# Imports projet (avec fallbacks)
# ============================================================

# --- Matériaux ---
try:
    from backend.ensemble.materiaux import get_materiau, valeur
except Exception:  # pragma: no cover
    get_materiau = None  # type: ignore

    def valeur(prop: Any, mode: str = "typique") -> Optional[float]:  # type: ignore
        return float(prop) if prop is not None else None

# --- Air ---
try:
    from backend.ensemble.air import air_state, isa_dry_temperature_pressure
except Exception:  # pragma: no cover
    air_state = None  # type: ignore
    isa_dry_temperature_pressure = None  # type: ignore

# --- Cylindre ---
try:
    from backend.components.moteur_thermique.pieces.cylindre import Cylindre
except Exception:  # pragma: no cover
    try:
        from pieces.cylindre import Cylindre  # type: ignore
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


def _req_int_pos(name: str, x: Any, *, allow_zero: bool = False) -> int:
    if not isinstance(x, int) or isinstance(x, bool):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if allow_zero:
        if x < 0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {x}).")
    else:
        if x <= 0:
            raise ValueError(f"{name} doit être > 0 (reçu: {x}).")
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
# Modèles physiques stricts
# ============================================================

def aire_disque(diametre_m: float) -> float:
    d = _req_pos("diametre_m", diametre_m)
    r = 0.5 * d
    return math.pi * r * r


def aire_annulaire(diametre_ext_m: float, diametre_int_m: float) -> float:
    de = _req_pos("diametre_ext_m", diametre_ext_m)
    di = _req_pos("diametre_int_m", diametre_int_m, strictly=False)
    if di >= de:
        raise ValueError("diametre_int_m doit être < diametre_ext_m.")
    return aire_disque(de) - aire_disque(di)


def inertie_section_circulaire_pleine(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return (math.pi / 64.0) * (D ** 4)


def inertie_section_annulaire(diametre_ext_m: float, diametre_int_m: float) -> float:
    De = _req_pos("diametre_ext_m", diametre_ext_m)
    Di = _req_pos("diametre_int_m", diametre_int_m, strictly=False)
    if Di >= De:
        raise ValueError("diametre_int_m doit être < diametre_ext_m.")
    return (math.pi / 64.0) * (De ** 4 - Di ** 4)


def flambe_euler(
    *,
    E_pa: float,
    I_m4: float,
    longueur_libre_m: float,
    coeff_k: float = 1.0,
) -> float:
    E = _req_pos("E_pa", E_pa)
    I = _req_pos("I_m4", I_m4)
    L = _req_pos("longueur_libre_m", longueur_libre_m)
    K = _req_pos("coeff_k", coeff_k)
    return (math.pi ** 2) * E * I / ((K * L) ** 2)


def perte_charge_orifice(
    *,
    rho_kg_m3: float,
    debit_m3_s: float,
    aire_orifice_m2: float,
    coeff_decharge: float,
) -> float:
    rho = _req_pos("rho_kg_m3", rho_kg_m3)
    Q = _req_pos("debit_m3_s", debit_m3_s, strictly=False)
    A = _req_pos("aire_orifice_m2", aire_orifice_m2)
    Cd = _req_pos("coeff_decharge", coeff_decharge)
    v = Q / (Cd * A)
    return 0.5 * rho * v * v


# ============================================================
# Norme ISO 3601 — joint torique statique radial
# ============================================================

@dataclass(frozen=True)
class JointToriqueISO3601:
    section_mm: float

    @property
    def section_m(self) -> float:
        return self.section_mm * 1e-3

    def largeur_rainure_m(self) -> float:
        return 1.10 * self.section_m

    def profondeur_rainure_m(self, taux_compression: float) -> float:
        if not (0.0 < taux_compression < 1.0):
            raise ValueError("taux_compression_joint ∈ (0,1)")
        return self.section_m * (1.0 - taux_compression)

    def taux_remplissage_max(self) -> float:
        return 0.85


# ============================================================
# Règles explicites de conception du déplaceur
# ============================================================

TypeDeplaceur = Literal["plein", "tubulaire"]
ModePosition = Literal["centre", "cote_chaud", "cote_froid", "manuel"]


@dataclass(frozen=True)
class ReglesFabricationDeplaceur:
    type_deplaceur: TypeDeplaceur = "tubulaire"

    # évidement si tubulaire
    ratio_diametre_interieur_sur_exterieur: float = 0.70
    epaisseur_min_paroi_m: float = 0.0015

    # butées / marges
    marge_butee_chaud_m: float = 0.002
    marge_butee_froid_m: float = 0.002

    # détails CAO
    chanfrein_min_m: float = 0.0005
    chanfrein_max_m: float = 0.0025
    ratio_chanfrein_sur_jeu: float = 8.0

    conge_min_m: float = 0.0005
    conge_max_m: float = 0.003
    ratio_conge_sur_paroi: float = 0.30

    rugosite_exterieure_ra_um: float = 0.8
    rugosite_faces_ra_um: float = 1.6
    tolerance_diametre_exterieur_m: float = 0.00003
    tolerance_longueur_m: float = 0.00010
    tolerance_position_m: float = 0.00010


@dataclass(frozen=True)
class ReglesRainuresJointsDeplaceur:
    marge_extremite_m: float = 0.004
    entraxe_min_m: float = 0.006
    coefficient_rayon_fond: float = 0.15


# ============================================================
# Résolution depuis cylindre
# ============================================================

def _resoudre_cylindre_associe(cylindre: Optional[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "rapport": None,
        "alesage_m": None,
        "longueur_utile_m": None,
        "diametre_interieur_m": None,
        "diametre_exterieur_m": None,
        "pression_service_pa": None,
        "pression_max_pa": None,
        "temperature_service_C": None,
        "geo_cao": None,
    }

    if cylindre is None:
        return out

    rep: Optional[Dict[str, Any]] = None
    if hasattr(cylindre, "analyser") and callable(getattr(cylindre, "analyser")):
        rep = cylindre.analyser(strict=False)  # type: ignore[call-arg]
    elif isinstance(cylindre, dict):
        rep = cylindre

    if not isinstance(rep, dict):
        return out

    out["rapport"] = rep
    ent = rep.get("entrees", {}) if isinstance(rep.get("entrees", {}), dict) else {}
    geo = rep.get("geometrie", {}) if isinstance(rep.get("geometrie", {}), dict) else {}
    cao = geo.get("cao", {}) if isinstance(geo.get("cao", {}), dict) else {}

    out["geo_cao"] = cao if cao else None
    out["alesage_m"] = ent.get("alesage_m")
    out["longueur_utile_m"] = ent.get("longueur_utile_m")
    out["pression_service_pa"] = ent.get("pression_service_pa")
    out["pression_max_pa"] = ent.get("pression_max_pa")
    out["temperature_service_C"] = ent.get("temperature_service_C")

    if cao:
        out["diametre_interieur_m"] = cao.get("diametre_interieur_nominal_m")
        out["diametre_exterieur_m"] = cao.get("diametre_exterieur_nominal_m")
    else:
        out["diametre_interieur_m"] = geo.get("diametre_interne_m")
        out["diametre_exterieur_m"] = geo.get("diametre_externe_m")

    if out["diametre_interieur_m"] is None and out["alesage_m"] is not None:
        out["diametre_interieur_m"] = out["alesage_m"]

    return out


# ============================================================
# Placement axial des rainures
# ============================================================

def _calcul_positions_rainures(
    *,
    longueur_deplaceur_m: float,
    nb_joints: int,
    largeur_rainure_m: float,
    marge_extremite_m: float,
    entraxe_min_m: float,
) -> List[float]:
    L = _req_pos("longueur_deplaceur_m", longueur_deplaceur_m)
    n = _req_int_pos("nb_joints", nb_joints)
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
# Déplaceur (piston libre séparateur chaud/froid)
# ============================================================

@dataclass(frozen=True)
class Deplaceur:
    # Référence pièce associée
    cylindre: Optional[Any] = None  # attendu: Cylindre ou dict rapport

    # --- Géométrie principale ---
    diametre_exterieur_m: Optional[float] = None
    longueur_totale_m: Optional[float] = None
    course_disponible_m: Optional[float] = None
    jeu_radial_m: float = 0.0

    # Position du déplaceur dans le cylindre
    mode_position: ModePosition = "centre"
    position_axiale_centre_m: Optional[float] = None  # requis si mode_position="manuel"

    # Distances mortes / volumes morts
    volume_mort_chaud_m3: float = 0.0
    volume_mort_froid_m3: float = 0.0

    # --- Pressions ---
    pression_chaud_pa: Optional[float] = None
    pression_froid_pa: Optional[float] = None
    delta_p_chaud_froid_pa: Optional[float] = None

    # --- Thermique ---
    temperature_chaud_C: Optional[float] = None
    temperature_froid_C: Optional[float] = None

    # --- Matériau ---
    materiau_cle: Optional[str] = None
    mode_materiau: Literal["min", "typique", "max"] = "typique"

    densite_kg_m3: Optional[float] = None
    module_young_pa: Optional[float] = None
    poisson: Optional[float] = None
    alpha_dilatation_1_k: Optional[float] = None
    limite_elastique_pa: Optional[float] = None

    # --- Type géométrique ---
    type_deplaceur: TypeDeplaceur = "tubulaire"
    diametre_interieur_m: Optional[float] = None

    # --- Joints ---
    standard_joint: Optional[Literal["ISO_3601"]] = None
    section_joint_mm: Optional[float] = None
    taux_compression_joint: Optional[float] = None
    nb_joints: int = 2

    # --- Orifice / passage gaz optionnel ---
    orifice_aire_m2: Optional[float] = None
    orifice_coeff_decharge: Optional[float] = None
    debit_gaz_m3_s: Optional[float] = None
    rho_gaz_kg_m3: Optional[float] = None
    temperature_gaz_C: Optional[float] = None
    pression_gaz_ref_pa: Optional[float] = None

    # --- Flambage ---
    longueur_libre_flambe_m: Optional[float] = None
    coeff_k_flambe: float = 1.0

    # --- Règles CAO / fabrication ---
    regles_fabrication: ReglesFabricationDeplaceur = ReglesFabricationDeplaceur()
    regles_rainures: ReglesRainuresJointsDeplaceur = ReglesRainuresJointsDeplaceur()

    # ========================================================
    # Analyse complète
    # ========================================================

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "cylindre_associe": {},
            "materiau": {},
            "geometrie": {},
            "volumes": {},
            "positions": {},
            "pressions": {},
            "efforts": {},
            "etancheite": {},
            "thermique": {},
            "contraintes": {},
            "fabrication": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ----------------------------------------------------
        # 0) Résolution cylindre
        # ----------------------------------------------------
        cyl = _resoudre_cylindre_associe(self.cylindre)
        rapport["cylindre_associe"].update({
            "cylindre_fournit": self.cylindre is not None,
            "alesage_m": cyl["alesage_m"],
            "longueur_utile_m": cyl["longueur_utile_m"],
            "diametre_interieur_m": cyl["diametre_interieur_m"],
            "diametre_exterieur_m": cyl["diametre_exterieur_m"],
            "pression_service_pa": cyl["pression_service_pa"],
            "pression_max_pa": cyl["pression_max_pa"],
            "temperature_service_C": cyl["temperature_service_C"],
        })

        # ----------------------------------------------------
        # 1) Géométrie primaire déduite du cylindre
        # ----------------------------------------------------
        D_cyl_int = cyl["diametre_interieur_m"]
        L_cyl = cyl["longueur_utile_m"]

        jeu = _req_pos("jeu_radial_m", self.jeu_radial_m, strictly=False)

        D_dep = self.diametre_exterieur_m
        if D_dep is None:
            if D_cyl_int is not None:
                D_dep = float(D_cyl_int) - 2.0 * jeu
            else:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "diametre_exterieur_m",
                    "Donner diametre_exterieur_m ou fournir un cylindre avec diamètre intérieur exploitable.",
                )

        if D_dep is None:
            D_dep = float("nan")
        else:
            D_dep = _req_pos("diametre_exterieur_m", D_dep)

        if self.longueur_totale_m is not None:
            L_dep = _req_pos("longueur_totale_m", self.longueur_totale_m)
        elif cyl.get("longueur_utile_m") is not None:
            L_dep = _req_pos("longueur_totale_m", cyl["longueur_utile_m"])
        else:
            _push_inconnue(rapport, "impossibles", "longueur_totale_m", "Longueur totale non fournie et cylindre absent.")
            L_dep = float("nan")
        course = self.course_disponible_m
        if course is None and L_cyl is not None:
            course = max(
                0.0,
                float(L_cyl)
                - L_dep
                - self.regles_fabrication.marge_butee_chaud_m
                - self.regles_fabrication.marge_butee_froid_m,
            )
        elif course is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "course_disponible_m",
                "Donner course_disponible_m ou fournir un cylindre avec longueur utile exploitable.",
            )

        if course is None:
            course = float("nan")
        else:
            course = _req_pos("course_disponible_m", course, strictly=False)

        # diamètre intérieur du déplaceur
        D_int_dep = self.diametre_interieur_m
        if self.type_deplaceur == "plein":
            D_int_dep = 0.0
        else:
            if D_int_dep is None:
                D_int_dep = self.regles_fabrication.ratio_diametre_interieur_sur_exterieur * D_dep
            D_int_dep = _req_pos("diametre_interieur_m", D_int_dep, strictly=False)
            if D_int_dep >= D_dep:
                raise ValueError("diametre_interieur_m du déplaceur doit être < diametre_exterieur_m.")

            ep_paroi = 0.5 * (D_dep - D_int_dep)
            if ep_paroi < self.regles_fabrication.epaisseur_min_paroi_m:
                D_int_dep = D_dep - 2.0 * self.regles_fabrication.epaisseur_min_paroi_m
                if D_int_dep < 0:
                    D_int_dep = 0.0

        A_face = aire_disque(D_dep)
        A_section_matiere = aire_annulaire(D_dep, D_int_dep) if D_int_dep > 0 else A_face
        perimetre = math.pi * D_dep
        ep_paroi_finale = 0.5 * (D_dep - D_int_dep)

        rapport["entrees"].update({
            "diametre_exterieur_m": self.diametre_exterieur_m,
            "longueur_totale_m": self.longueur_totale_m,
            "course_disponible_m": self.course_disponible_m,
            "jeu_radial_m": self.jeu_radial_m,
            "mode_position": self.mode_position,
            "position_axiale_centre_m": self.position_axiale_centre_m,
            "type_deplaceur": self.type_deplaceur,
            "diametre_interieur_m": self.diametre_interieur_m,
            "cylindre_associe": self.cylindre is not None,
        })

        rapport["geometrie"].update({
            "diametre_exterieur_m": D_dep,
            "diametre_interieur_m": D_int_dep,
            "longueur_totale_m": L_dep,
            "course_disponible_m": course,
            "aire_face_m2": A_face,
            "section_matiere_m2": A_section_matiere,
            "perimetre_m": perimetre,
            "volume_matiere_m3": A_section_matiere * L_dep,
            "volume_enveloppe_m3": A_face * L_dep,
            "epaisseur_paroi_m": ep_paroi_finale,
        })

        # ----------------------------------------------------
        # 2) Matériau
        # ----------------------------------------------------
        rho = self.densite_kg_m3
        E = self.module_young_pa
        alpha = self.alpha_dilatation_1_k
        Re = self.limite_elastique_pa
        nu = self.poisson

        if self.materiau_cle and get_materiau is not None:
            try:
                mat = get_materiau(self.materiau_cle)
                if mat:
                    rho = rho if rho is not None else valeur(getattr(mat, "densite_kg_m3", None), self.mode_materiau)
                    E = E if E is not None else valeur(getattr(mat, "module_young_pa", None), self.mode_materiau)
                    alpha = alpha if alpha is not None else valeur(getattr(mat, "alpha_dilatation_1_k", None), self.mode_materiau)
                    Re = Re if Re is not None else valeur(getattr(mat, "limite_elastique_pa", None), self.mode_materiau)
                    nu = nu if nu is not None else valeur(getattr(mat, "poisson", None), self.mode_materiau)

                    rapport["materiau"].update({
                        "materiau": self.materiau_cle,
                        "densite_kg_m3": rho,
                        "module_young_pa": E,
                        "alpha_dilatation_1_k": alpha,
                        "limite_elastique_pa": Re,
                        "poisson": nu,
                    })
            except Exception as e:
                _push_inconnue(rapport, "partielles", "materiau_cle", f"Impossible d'exploiter materiau_cle={self.materiau_cle!r}: {e!r}")

        if rho is not None:
            rapport["geometrie"]["masse_kg"] = _req_pos("densite_kg_m3", rho) * A_section_matiere * L_dep

        # ----------------------------------------------------
        # 3) Pressions et températures
        # ----------------------------------------------------
        p_chaud = self.pression_chaud_pa
        p_froid = self.pression_froid_pa

        if p_chaud is None and cyl["pression_max_pa"] is not None:
            p_chaud = float(cyl["pression_max_pa"])
        if p_froid is None and cyl["pression_service_pa"] is not None:
            p_froid = float(cyl["pression_service_pa"])

        delta_p = self.delta_p_chaud_froid_pa
        if delta_p is None and (p_chaud is not None) and (p_froid is not None):
            delta_p = float(p_chaud) - float(p_froid)

        T_chaud = self.temperature_chaud_C
        T_froid = self.temperature_froid_C

        if T_chaud is None and cyl["temperature_service_C"] is not None:
            T_chaud = float(cyl["temperature_service_C"])

        rapport["pressions"].update({
            "pression_chaud_pa": p_chaud,
            "pression_froid_pa": p_froid,
            "delta_p_chaud_froid_pa": delta_p,
        })
        rapport["thermique"].update({
            "temperature_chaud_C": T_chaud,
            "temperature_froid_C": T_froid,
        })

        if delta_p is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "delta_p_chaud_froid_pa",
                "Δp non déterminable sans pression chaude et froide ou delta_p_chaud_froid_pa.",
            )

        # ----------------------------------------------------
        # 4) Position du déplaceur dans le cylindre
        # ----------------------------------------------------
        x_centre = self.position_axiale_centre_m
        x_min_centre = None
        x_max_centre = None

        if L_cyl is not None:
            L_cyl_v = _req_pos("longueur_utile_m(cylindre)", L_cyl)
            x_min_centre = self.regles_fabrication.marge_butee_froid_m + 0.5 * L_dep
            x_max_centre = L_cyl_v - self.regles_fabrication.marge_butee_chaud_m - 0.5 * L_dep

            if x_max_centre < x_min_centre:
                _push_inconnue(
                    rapport,
                    "impossibles",
                    "position_axiale_centre_m",
                    "Le déplaceur est trop long pour rentrer dans le cylindre avec les marges de butée.",
                )
            else:
                if self.mode_position == "centre":
                    x_centre = 0.5 * (x_min_centre + x_max_centre)
                elif self.mode_position == "cote_chaud":
                    x_centre = x_max_centre
                elif self.mode_position == "cote_froid":
                    x_centre = x_min_centre
                elif self.mode_position == "manuel":
                    if x_centre is None:
                        _push_inconnue(
                            rapport,
                            "impossibles",
                            "position_axiale_centre_m",
                            "mode_position='manuel' nécessite position_axiale_centre_m.",
                        )
                    else:
                        x_centre = _req_pos("position_axiale_centre_m", x_centre, strictly=False)
                else:
                    _push_inconnue(rapport, "impossibles", "mode_position", f"mode_position inconnu: {self.mode_position!r}")
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "position dans le cylindre",
                "Position axiale pleinement calculable si la longueur utile du cylindre est connue.",
            )

        if x_centre is not None and _is_finite(x_centre):
            x_centre = float(x_centre)
            x_face_froid = x_centre - 0.5 * L_dep
            x_face_chaud = x_centre + 0.5 * L_dep

            rapport["positions"].update({
                "position_axiale_centre_m": x_centre,
                "position_face_froid_m": x_face_froid,
                "position_face_chaud_m": x_face_chaud,
                "position_centre_normalisee_sur_course": (
                    (x_centre - x_min_centre) / (x_max_centre - x_min_centre)
                    if (x_min_centre is not None and x_max_centre is not None and x_max_centre > x_min_centre)
                    else None
                ),
                "position_min_centre_m": x_min_centre,
                "position_max_centre_m": x_max_centre,
            })

            if x_min_centre is not None and x_max_centre is not None:
                rapport["verifications"]["position_axiale_dans_course"] = (x_min_centre <= x_centre <= x_max_centre)
        else:
            x_face_froid = None
            x_face_chaud = None

        # ----------------------------------------------------
        # 5) Volumes chaud / froid séparés par le déplaceur
        # ----------------------------------------------------
        if (L_cyl is not None) and (x_face_froid is not None) and (x_face_chaud is not None) and (D_cyl_int is not None):
            D_ci = _req_pos("diametre_interieur_cylindre_m", D_cyl_int)
            A_cyl = aire_disque(D_ci)
            L_cyl_v = _req_pos("longueur_utile_m", L_cyl)

            L_froid = _borne(x_face_froid, 0.0, L_cyl_v)
            L_chaud = _borne(L_cyl_v - x_face_chaud, 0.0, L_cyl_v)

            V_froid = A_cyl * L_froid + _req_pos("volume_mort_froid_m3", self.volume_mort_froid_m3, strictly=False)
            V_chaud = A_cyl * L_chaud + _req_pos("volume_mort_chaud_m3", self.volume_mort_chaud_m3, strictly=False)

            V_occupe = A_face * L_dep
            V_total_interne = A_cyl * L_cyl_v

            rapport["volumes"].update({
                "aire_section_interne_cylindre_m2": A_cyl,
                "longueur_zone_froide_m": L_froid,
                "longueur_zone_chaude_m": L_chaud,
                "volume_zone_froide_m3": V_froid,
                "volume_zone_chaude_m3": V_chaud,
                "volume_total_interne_cylindre_m3": V_total_interne,
                "volume_occupe_par_deplaceur_m3": V_occupe,
                "volume_libre_total_hors_deplaceur_m3": V_froid + V_chaud,
            })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "volumes chaud/froid",
                "Calculables si la géométrie interne du cylindre et la position du déplaceur sont connues.",
            )

        # ----------------------------------------------------
        # 6) Efforts axiaux
        # ----------------------------------------------------
        if delta_p is not None:
            F = float(delta_p) * A_face
            rapport["efforts"]["force_axiale_N"] = F
            rapport["efforts"]["surface_effective_m2"] = A_face
        else:
            _push_inconnue(rapport, "impossibles", "force_axiale_N", "Impossible sans Δp.")

        # ----------------------------------------------------
        # 7) Joints toriques ISO 3601 + rainures complètes
        # ----------------------------------------------------
        rainures_cao: Dict[str, Any] = {}

        if self.standard_joint == "ISO_3601" and self.section_joint_mm:
            jt = JointToriqueISO3601(self.section_joint_mm)
            largeur = jt.largeur_rainure_m()

            rapport["etancheite"].update({
                "standard": "ISO_3601",
                "nb_joints": _req_int_pos("nb_joints", self.nb_joints),
                "section_joint_mm": self.section_joint_mm,
                "largeur_rainure_m": largeur,
            })

            if self.taux_compression_joint is not None:
                profondeur = jt.profondeur_rainure_m(self.taux_compression_joint)
                rayon_fond = self.regles_rainures.coefficient_rayon_fond * profondeur
                diam_fond = D_dep - 2.0 * profondeur

                try:
                    positions_rainures = _calcul_positions_rainures(
                        longueur_deplaceur_m=L_dep,
                        nb_joints=self.nb_joints,
                        largeur_rainure_m=largeur,
                        marge_extremite_m=self.regles_rainures.marge_extremite_m,
                        entraxe_min_m=self.regles_rainures.entraxe_min_m,
                    )
                except Exception as e:
                    positions_rainures = None
                    _push_inconnue(
                        rapport,
                        "partielles",
                        "positions_axiales_rainures_m",
                        f"Impossible de placer les rainures: {e!r}",
                    )

                rapport["etancheite"].update({
                    "taux_compression": self.taux_compression_joint,
                    "profondeur_rainure_m": profondeur,
                    "diametre_fond_rainure_m": diam_fond,
                    "rayon_fond_rainure_m": rayon_fond,
                    "positions_axiales_rainures_m": positions_rainures,
                    "taux_remplissage_max": jt.taux_remplissage_max(),
                })

                rainures_cao = {
                    "nb_joints": self.nb_joints,
                    "largeur_rainure_m": largeur,
                    "profondeur_rainure_m": profondeur,
                    "diametre_fond_rainure_m": diam_fond,
                    "rayon_fond_rainure_m": rayon_fond,
                    "positions_axiales_rainures_m": positions_rainures,
                    "marge_extremite_m": self.regles_rainures.marge_extremite_m,
                    "entraxe_min_m": self.regles_rainures.entraxe_min_m,
                }
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "profondeur_rainure_m",
                    "Calculable si taux_compression_joint est fourni.",
                )
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "joints toriques",
                "ISO_3601 calculable si standard_joint='ISO_3601', section_joint_mm et taux_compression_joint sont fournis.",
            )

        # ----------------------------------------------------
        # 8) Élasticité / jeu résiduel
        # ----------------------------------------------------
        if (delta_p is not None) and (E is not None):
            E2 = _req_pos("module_young_pa", E)
            epsilon = float(delta_p) / E2
            dL = epsilon * L_dep
            dR = epsilon * (D_dep / 2.0)

            rapport["contraintes"].update({
                "deformation_axiale": epsilon,
                "allongement_m": dL,
                "augmentation_rayon_m": dR,
            })

            rapport["verifications"]["jeu_residuel_m"] = jeu - dR
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "deformations",
                "Calculables si delta_p_chaud_froid_pa et module_young_pa sont connus.",
            )

        # ----------------------------------------------------
        # 9) Flambage
        # ----------------------------------------------------
        if self.longueur_libre_flambe_m is not None and E is not None:
            if self.type_deplaceur == "plein":
                I = inertie_section_circulaire_pleine(D_dep)
            else:
                I = inertie_section_annulaire(D_dep, D_int_dep)

            Pcr = flambe_euler(
                E_pa=E,
                I_m4=I,
                longueur_libre_m=self.longueur_libre_flambe_m,
                coeff_k=self.coeff_k_flambe,
            )
            rapport["verifications"]["flambage_euler_N"] = Pcr

            if "force_axiale_N" in rapport["efforts"]:
                F_ax = abs(float(rapport["efforts"]["force_axiale_N"]))
                rapport["verifications"]["marge_flambage"] = (Pcr / F_ax) if F_ax > 0 else None

        # ----------------------------------------------------
        # 10) Orifice / pertes de charge
        # ----------------------------------------------------
        if (
            self.orifice_aire_m2 is not None
            and self.orifice_coeff_decharge is not None
            and self.debit_gaz_m3_s is not None
        ):
            rho_gaz = self.rho_gaz_kg_m3

            if rho_gaz is None and self.temperature_gaz_C is not None and self.pression_gaz_ref_pa is not None:
                if air_state is not None and isa_dry_temperature_pressure is not None:
                    try:
                        T_K = float(self.temperature_gaz_C) + 273.15
                        T_isa, _ = isa_dry_temperature_pressure(altitude_m=0.0)
                        st = air_state(
                            altitude_m=0.0,
                            temperature_offset_K=(T_K - float(T_isa)),
                            RH=0.0,
                            co2_ppm=420.0,
                        )
                        rho_gaz = float(st.rho_kg_m3)
                    except Exception:
                        rho_gaz = None

            if rho_gaz is not None:
                dp_orifice = perte_charge_orifice(
                    rho_kg_m3=rho_gaz,
                    debit_m3_s=self.debit_gaz_m3_s,
                    aire_orifice_m2=self.orifice_aire_m2,
                    coeff_decharge=self.orifice_coeff_decharge,
                )
                rapport["thermique"]["perte_charge_orifice_pa"] = dp_orifice
                rapport["thermique"]["rho_gaz_utilise_kg_m3"] = rho_gaz
            else:
                _push_inconnue(
                    rapport,
                    "partielles",
                    "perte_charge_orifice",
                    "Calculable si rho_gaz_kg_m3 est fourni ou déductible.",
                )

        # ----------------------------------------------------
        # 11) Fabrication / CAO
        # ----------------------------------------------------
        chanfrein = _borne(
            self.regles_fabrication.ratio_chanfrein_sur_jeu * max(jeu, 1e-6),
            self.regles_fabrication.chanfrein_min_m,
            self.regles_fabrication.chanfrein_max_m,
        )
        conge = _borne(
            self.regles_fabrication.ratio_conge_sur_paroi * max(ep_paroi_finale, 1e-6),
            self.regles_fabrication.conge_min_m,
            self.regles_fabrication.conge_max_m,
        )

        rapport["fabrication"].update({
            "chanfrein_extremites_m": chanfrein,
            "rayon_conge_m": conge,
            "rugosite_exterieure_ra_um": self.regles_fabrication.rugosite_exterieure_ra_um,
            "rugosite_faces_ra_um": self.regles_fabrication.rugosite_faces_ra_um,
            "tolerance_diametre_exterieur_m": self.regles_fabrication.tolerance_diametre_exterieur_m,
            "tolerance_longueur_m": self.regles_fabrication.tolerance_longueur_m,
            "tolerance_position_m": self.regles_fabrication.tolerance_position_m,
        })

        rapport["geometrie"]["cao"] = {
            "type_deplaceur": self.type_deplaceur,
            "diametre_exterieur_m": D_dep,
            "diametre_interieur_m": D_int_dep,
            "longueur_totale_m": L_dep,
            "chanfrein_extremites_m": chanfrein,
            "rayon_conge_m": conge,
            "position_axiale_centre_m": rapport["positions"].get("position_axiale_centre_m"),
            "position_face_froid_m": rapport["positions"].get("position_face_froid_m"),
            "position_face_chaud_m": rapport["positions"].get("position_face_chaud_m"),
            "section_matiere_m2": A_section_matiere,
            "volume_matiere_m3": A_section_matiere * L_dep,
            "rainures_joints": rainures_cao if rainures_cao else None,
        }

        # ----------------------------------------------------
        # 12) Vérifications de cohérence avec cylindre
        # ----------------------------------------------------
        if D_cyl_int is not None:
            rapport["verifications"]["diametre_deplaceur_compatible_alésage"] = (
                D_dep + 2.0 * jeu <= float(D_cyl_int) + 1e-12
            )

        if L_cyl is not None:
            rapport["verifications"]["longueur_deplaceur_compatible_cylindre"] = (
                L_dep
                + self.regles_fabrication.marge_butee_chaud_m
                + self.regles_fabrication.marge_butee_froid_m
                <= float(L_cyl) + 1e-12
            )

        if x_min_centre is not None and x_max_centre is not None:
            rapport["verifications"]["course_geometrique_max_m"] = max(0.0, x_max_centre - x_min_centre)

        rapport["notes_modele"].append(
            "Le déplaceur est traité comme séparateur mobile entre zone froide et zone chaude dans le même cylindre."
        )
        rapport["notes_modele"].append(
            "Les volumes chaud/froid sont calculés à partir de la position axiale du déplaceur dans la longueur utile du cylindre."
        )
        rapport["notes_modele"].append(
            "La force axiale est calculée sur la face pleine externe du déplaceur ; les pertes par fuite et échanges dynamiques ne sont pas encore couplés au cycle complet."
        )
        rapport["notes_modele"].append(
            "Les rainures de joints toriques incluent largeur, profondeur, diamètre de fond et positions axiales quand les données ISO 3601 sont fournies."
        )

        # ----------------------------------------------------
        # 13) Mode strict
        # ----------------------------------------------------
        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(f"Inconnues restantes: {rapport['inconnues']}")

        return rapport