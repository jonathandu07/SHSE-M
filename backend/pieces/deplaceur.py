# backend/pieces/deplaceur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal
import math

# ============================================================
# Imports projet (avec fallbacks) — réduction des inconnues
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
    from backend.ensemble.air import air_state
except Exception:  # pragma: no cover
    air_state = None  # type: ignore


# ============================================================
# Helpers robustes
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
# Modèles physiques stricts
# ============================================================

def aire_disque(diametre_m: float) -> float:
    d = _req_pos("diametre_m", diametre_m)
    r = 0.5 * d
    return math.pi * r * r


def inertie_section_circulaire_pleine(diametre_m: float) -> float:
    D = _req_pos("diametre_m", diametre_m)
    return (math.pi / 64.0) * (D ** 4)


def flambe_euler(
    *, E_pa: float, I_m4: float, longueur_libre_m: float, coeff_k: float = 1.0
) -> float:
    E = _req_pos("E_pa", E_pa)
    I = _req_pos("I_m4", I_m4)
    L = _req_pos("longueur_libre_m", longueur_libre_m)
    K = _req_pos("coeff_k", coeff_k)
    return (math.pi ** 2) * E * I / ((K * L) ** 2)


def perte_charge_orifice(
    *, rho_kg_m3: float, debit_m3_s: float, aire_orifice_m2: float, coeff_decharge: float
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
        return 1.1 * self.section_m

    def profondeur_rainure_m(self, taux_compression: float) -> float:
        if not (0.0 < taux_compression < 1.0):
            raise ValueError("taux_compression_joint ∈ (0,1)")
        return self.section_m * (1.0 - taux_compression)

    def taux_remplissage_max(self) -> float:
        return 0.85


# ============================================================
# Déplaceur (piston libre)
# ============================================================

@dataclass(frozen=True)
class Deplaceur:
    # --- Géométrie ---
    diametre_exterieur_m: float
    longueur_totale_m: float
    course_disponible_m: float
    jeu_radial_m: float

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

    # --- Joints ---
    standard_joint: Optional[Literal["ISO_3601"]] = None
    section_joint_mm: Optional[float] = None
    taux_compression_joint: Optional[float] = None

    # --- Modèle orifice optionnel ---
    orifice_aire_m2: Optional[float] = None
    orifice_coeff_decharge: Optional[float] = None
    debit_gaz_m3_s: Optional[float] = None
    rho_gaz_kg_m3: Optional[float] = None
    temperature_gaz_C: Optional[float] = None
    pression_gaz_ref_pa: Optional[float] = None

    # --- Flambage ---
    longueur_libre_flambe_m: Optional[float] = None
    coeff_k_flambe: float = 1.0

    # ========================================================
    # Analyse complète
    # ========================================================

    def analyser(self, *, strict: bool = False) -> Dict[str, Any]:
        rapport: Dict[str, Any] = {
            "entrees": {},
            "materiau": {},
            "geometrie": {},
            "pressions": {},
            "efforts": {},
            "etancheite": {},
            "thermique": {},
            "contraintes": {},
            "verifications": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # ----------------------------------------------------
        # Géométrie
        # ----------------------------------------------------
        D = _req_pos("diametre_exterieur_m", self.diametre_exterieur_m)
        L = _req_pos("longueur_totale_m", self.longueur_totale_m)
        jeu = _req_pos("jeu_radial_m", self.jeu_radial_m, strictly=False)

        A = aire_disque(D)
        perimetre = math.pi * D

        rapport["geometrie"].update({
            "diametre_exterieur_m": D,
            "longueur_totale_m": L,
            "aire_face_m2": A,
            "perimetre_m": perimetre,
            "volume_plein_m3": A * L,
        })

        # ----------------------------------------------------
        # Matériau
        # ----------------------------------------------------
        rho = self.densite_kg_m3
        E = self.module_young_pa
        alpha = self.alpha_dilatation_1_k
        Re = self.limite_elastique_pa

        if self.materiau_cle and get_materiau:
            mat = get_materiau(self.materiau_cle)
            if mat:
                rho = rho or valeur(getattr(mat, "densite_kg_m3", None), self.mode_materiau)
                E = E or valeur(getattr(mat, "module_young_pa", None), self.mode_materiau)
                alpha = alpha or valeur(getattr(mat, "alpha_dilatation_1_k", None), self.mode_materiau)
                Re = Re or valeur(getattr(mat, "limite_elastique_pa", None), self.mode_materiau)

                rapport["materiau"].update({
                    "materiau": self.materiau_cle,
                    "densite_kg_m3": rho,
                    "module_young_pa": E,
                    "alpha_dilatation_1_k": alpha,
                    "limite_elastique_pa": Re,
                })

        if rho:
            rapport["geometrie"]["masse_kg"] = rho * A * L

        # ----------------------------------------------------
        # Pression Δp
        # ----------------------------------------------------
        delta_p = self.delta_p_chaud_froid_pa
        if delta_p is None and self.pression_chaud_pa and self.pression_froid_pa:
            delta_p = self.pression_chaud_pa - self.pression_froid_pa

        if delta_p is None:
            _push_inconnue(
                rapport,
                "impossibles",
                "delta_p",
                "Δp non déterminable sans pression ou modèle explicite.",
            )
        else:
            rapport["pressions"]["delta_p_Pa"] = delta_p
            F = delta_p * A
            rapport["efforts"]["force_axiale_N"] = F

        # ----------------------------------------------------
        # Joints toriques ISO 3601
        # ----------------------------------------------------
        if self.standard_joint == "ISO_3601" and self.section_joint_mm:
            jt = JointToriqueISO3601(self.section_joint_mm)
            largeur = jt.largeur_rainure_m()

            rapport["etancheite"].update({
                "standard": "ISO_3601",
                "section_joint_mm": self.section_joint_mm,
                "largeur_rainure_m": largeur,
            })

            if self.taux_compression_joint:
                profondeur = jt.profondeur_rainure_m(self.taux_compression_joint)
                rapport["etancheite"].update({
                    "taux_compression": self.taux_compression_joint,
                    "profondeur_rainure_m": profondeur,
                    "diametre_fond_rainure_m": D - 2 * profondeur,
                })
        else:
            _push_inconnue(
                rapport,
                "partielles",
                "joints toriques",
                "ISO_3601 calculable si section_joint_mm et taux_compression_joint fournis.",
            )

        # ----------------------------------------------------
        # Élasticité
        # ----------------------------------------------------
        if delta_p is not None and E:
            epsilon = delta_p / E
            dL = epsilon * L
            dR = epsilon * (D / 2.0)

            rapport["contraintes"].update({
                "deformation_axiale": epsilon,
                "allongement_m": dL,
                "augmentation_rayon_m": dR,
            })

            rapport["verifications"]["jeu_residuel_m"] = jeu - dR

        # ----------------------------------------------------
        # Flambage
        # ----------------------------------------------------
        if self.longueur_libre_flambe_m and E:
            I = inertie_section_circulaire_pleine(D)
            Pcr = flambe_euler(
                E_pa=E,
                I_m4=I,
                longueur_libre_m=self.longueur_libre_flambe_m,
                coeff_k=self.coeff_k_flambe,
            )
            rapport["verifications"]["flambage_euler_N"] = Pcr

        _dedup_inconnues(rapport)
        if strict and (rapport["inconnues"]["impossibles"] or rapport["inconnues"]["partielles"]):
            raise ValueError(f"Inconnues restantes: {rapport['inconnues']}")

        return rapport
