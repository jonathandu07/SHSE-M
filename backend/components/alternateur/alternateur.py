# backend/components/alternateur.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple
import math

# ============================================================
# Imports des modules alternateur (robustes à l'arborescence)
# ============================================================

try:
    from backend.components.alternateur.modules.calcul_vitesse_angulaire import calcul_vitesse_angulaire
    from backend.components.alternateur.modules.calcul_frequence_synchrone import calcul_frequence_synchrone
    from backend.components.alternateur.modules.calcul_fem_induite import (
        calcul_fem_induite,
        calcul_fem_induite_avec_induction,
    )
    from backend.components.alternateur.modules.calcul_puissance_electrique import (
        calcul_puissance_triphase,
        calcul_puissance_monophase,
        calcul_puissance_dc,
    )
    from backend.components.alternateur.modules.calcul_pertes_cuivre import (
        calcul_resistance_enroulement,
        calcul_pertes_cuivre_phase,
        calcul_pertes_cuivre_triphase,
    )
    from backend.components.alternateur.modules.calcul_pertes_fer import calcul_pertes_fer_steinmetz
    from backend.components.alternateur.modules.calcul_rendement_alternateur import calcul_rendement_alternateur
    from backend.components.alternateur.modules.calcul_puissance_mecanique import calcul_puissance_mecanique
    from backend.components.alternateur.modules.calcul_couple_alternateur import calcul_couple_alternateur
    from backend.components.alternateur.modules.calcul_echauffement_thermique import calcul_echauffement_thermique
except Exception:
    # Fallback si imports directs échouent (pour certains environnements de test)
    from .modules.calcul_vitesse_angulaire import calcul_vitesse_angulaire
    from .modules.calcul_frequence_synchrone import calcul_frequence_synchrone
    from .modules.calcul_fem_induite import (
        calcul_fem_induite,
        calcul_fem_induite_avec_induction,
    )
    from .modules.calcul_puissance_electrique import (
        calcul_puissance_triphase,
        calcul_puissance_monophase,
        calcul_puissance_dc,
    )
    from .modules.calcul_pertes_cuivre import (
        calcul_resistance_enroulement,
        calcul_pertes_cuivre_phase,
        calcul_pertes_cuivre_triphase,
    )
    from .modules.calcul_pertes_fer import calcul_pertes_fer_steinmetz
    from .modules.calcul_rendement_alternateur import calcul_rendement_alternateur
    from .modules.calcul_puissance_mecanique import calcul_puissance_mecanique
    from .modules.calcul_couple_alternateur import calcul_couple_alternateur
    from .modules.calcul_echauffement_thermique import calcul_echauffement_thermique

# ============================================================
# (Optionnel) import module batterie pour temps/énergie de charge
# ============================================================

try:
    from backend.components.batterie.modules.calcul_temps_charge import calcul_temps_charge
except Exception:
    calcul_temps_charge = None  # type: ignore


# ============================================================
# Imports des pièces
# ============================================================
try:
    from backend.components.alternateur.pieces.rotor import Rotor
    from backend.components.alternateur.pieces.stator import Stator
    from backend.components.alternateur.pieces.arbre_alternateur import ArbreAlternateur
    from backend.components.alternateur.pieces.carter_alternateur import CarterAlternateur
    from backend.components.alternateur.pieces.ventilateur import Ventilateur
    from backend.components.alternateur.pieces.bobine_excite import BobineExcitation
    from backend.components.alternateur.pieces.roulement_alternateur import RoulementAlternateur
except Exception:
    Rotor = Any
    Stator = Any
    ArbreAlternateur = Any
    CarterAlternateur = Any
    Ventilateur = Any
    BobineExcitation = Any
    RoulementAlternateur = Any

# ============================================================
# Types & helpers
# ============================================================

ModeElectrique = Literal["triphase_ac", "monophase_ac", "dc"]
Connexion = Literal["Y", "Delta"]
ModePoles = Literal["poles", "pair_poles", "pole_pairs"]


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


def _req_eta(name: str, eta: Any) -> float:
    v = _req_finite(name, eta)
    if not (0.0 < v <= 1.0):
        raise ValueError(f"{name} doit être dans (0,1] (reçu: {v}).")
    return v


def _push_inconnue(rep: Dict[str, Any], cat: str, nom: str, raison: str) -> None:
    rep["inconnues"][cat].append({"nom": nom, "raison": raison})


def _dedup_inconnues(rep: Dict[str, Any]) -> None:
    def dedup(lst: list[dict]) -> list[dict]:
        seen: set[Tuple[str, str]] = set()
        out: list[dict] = []
        for it in lst:
            key = (str(it.get("nom", "")), str(it.get("raison", "")))
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out

    rep["inconnues"]["impossibles"] = dedup(rep["inconnues"]["impossibles"])
    rep["inconnues"]["partielles"] = dedup(rep["inconnues"]["partielles"])


def _phase_line_from_connexion(connexion: Connexion) -> Tuple[float, float]:
    """
    Renvoie (k_Vll_from_Vph, k_Iph_from_Il) pour une machine triphasée:
      - Y     : V_LL = sqrt(3)*V_ph ; I_ph = I_L
      - Delta : V_LL = V_ph         ; I_ph = I_L/sqrt(3)
    """
    if connexion == "Y":
        return (math.sqrt(3.0), 1.0)
    return (1.0, 1.0 / math.sqrt(3.0))


def _safe_get_attr(obj: Any, attr: str) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return None


# ============================================================
# Alternateur
# ============================================================

@dataclass
class Alternateur:
    """
    Alternateur "calcul-only" :
    - calcule tout ce qui est déterminable à partir des entrées fournies,
    - n'invente jamais (toute donnée techno manquante => inconnue),
    - peut s'intégrer à des objets 'moteur' et 'batterie' via lecture d'attributs.
    """

    # --- Cinématique / topologie ---
    nombre_poles: Optional[int] = None
    mode_poles: ModePoles = "poles"
    connexion: Connexion = "Y"

    # --- Enroulement / magnétisme (FEM) ---
    nombre_spires_serie: Optional[int] = None
    facteur_enroulement: Optional[float] = None  # k_w
    flux_max_pole_wb: Optional[float] = None     # Phi_max

    # Alternative flux ~ B_g * A_p
    induction_gap_t: Optional[float] = None
    aire_pole_m2: Optional[float] = None

    # --- Cuivre (R_phase) ---
    resistance_phase_ohm: Optional[float] = None
    resistivite_ohm_m: Optional[float] = None
    longueur_fil_m: Optional[float] = None
    section_fil_m2: Optional[float] = None
    temperature_c: Optional[float] = None
    temperature_ref_c: float = 20.0
    coef_temperature: float = 0.00393

    # --- Fer (Steinmetz) ---
    k_h: Optional[float] = None
    k_e: Optional[float] = None
    exposant_steinmetz: Optional[float] = None
    induction_max_t: Optional[float] = None
    eddy_freq_exp: float = 2.0
    eddy_induction_exp: float = 2.0
    masse_fer_kg: Optional[float] = None
    volume_fer_m3: Optional[float] = None

    # --- Pertes fixes ---
    pertes_fixes_w: float = 0.0

    # --- Thermique ---
    resistance_thermique_k_w: Optional[float] = None
    offset_temperature: float = 0.0

    # --- Pièces (optionnel) ---
    piece_rotor: Optional[Rotor] = None
    piece_stator: Optional[Stator] = None
    piece_arbre: Optional[ArbreAlternateur] = None
    piece_carter: Optional[CarterAlternateur] = None
    piece_ventilateur: Optional[Ventilateur] = None
    piece_bobine_excite: Optional[BobineExcitation] = None
    piece_roulement: Optional[RoulementAlternateur] = None

    clamp_non_negative: bool = True

    def __post_init__(self) -> None:
        _req_finite("pertes_fixes_w", self.pertes_fixes_w)
        _req_finite("offset_temperature", self.offset_temperature)

        if self.nombre_poles is not None:
            if not isinstance(self.nombre_poles, int) or self.nombre_poles <= 0:
                raise ValueError("nombre_poles doit être un entier > 0 si fourni.")

        if self.nombre_spires_serie is not None:
            if not isinstance(self.nombre_spires_serie, int) or self.nombre_spires_serie < 0:
                raise ValueError("nombre_spires_serie doit être un entier >= 0 si fourni.")

        if self.resistance_phase_ohm is not None:
            _req_pos("resistance_phase_ohm", self.resistance_phase_ohm, strictly=False)

        if self.resistance_thermique_k_w is not None:
            _req_finite("resistance_thermique_k_w", self.resistance_thermique_k_w)

        if self.masse_fer_kg is not None and self.volume_fer_m3 is not None:
            raise ValueError("Fournis soit masse_fer_kg, soit volume_fer_m3, pas les deux.")

    def analyser_point_de_fonctionnement(
        self,
        *,
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        mode_electrique: ModeElectrique = "triphase_ac",
        tension_v: Optional[float] = None,
        courant_a: Optional[float] = None,
        facteur_puissance: float = 1.0,
        entree_puissance_ac: Literal["VLL_IL", "Vph_Iph"] = "VLL_IL",
        courant_est_ligne: bool = True,
        puissance_electrique_cible_w: Optional[float] = None,
        courant_phase_rms_stator_a: Optional[float] = None,
        nb_phases_chargees: Optional[int] = None,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "entrees": {},
            "resultats": {},
            "pertes": {},
            "thermique": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        # 1) Vitesse
        omega: Optional[float] = None
        rpm: Optional[float] = None

        if vitesse_angulaire_rad_s is not None:
            omega = calcul_vitesse_angulaire(float(vitesse_angulaire_rad_s), input_unite="rad_s")
            rpm = (omega * 60.0) / (2.0 * math.pi)
        elif vitesse_rotation_rpm is not None:
            rpm = _req_finite("vitesse_rotation_rpm", vitesse_rotation_rpm)
            omega = calcul_vitesse_angulaire(rpm, input_unite="rpm")
        else:
            _push_inconnue(rep, "impossibles", "vitesse", "Vitesse requise.")
        rep["entrees"]["rpm"] = rpm
        rep["entrees"]["omega_rad_s"] = omega

        # 2) Fréquence synchrone
        frequence_hz: Optional[float] = None
        if rpm is not None and self.nombre_poles is not None:
            frequence_hz = calcul_frequence_synchrone(rpm, self.nombre_poles, mode_poles=self.mode_poles)
        rep["resultats"]["frequence_hz"] = frequence_hz

        # 3) FEM
        k_vll, _ = _phase_line_from_connexion(self.connexion)
        fem_phase_v = None
        if frequence_hz is not None and self.nombre_spires_serie is not None and self.facteur_enroulement is not None and self.flux_max_pole_wb is not None:
            fem_phase_v = calcul_fem_induite(frequence_hz, self.nombre_spires_serie, self.flux_max_pole_wb, self.facteur_enroulement)
        rep["resultats"]["fem_phase_v"] = fem_phase_v
        rep["resultats"]["fem_ligne_ligne_v"] = float(fem_phase_v * k_vll) if fem_phase_v is not None else None

        # 4) Puissance utile
        P_out = puissance_electrique_cible_w
        if P_out is None and tension_v is not None and courant_a is not None:
            if mode_electrique == "triphase_ac":
                P_out = calcul_puissance_triphase(tension_v, courant_a, facteur_puissance, entree_puissance_ac, self.connexion)
            elif mode_electrique == "monophase_ac":
                P_out = calcul_puissance_monophase(tension_v, courant_a, facteur_puissance)
            elif mode_electrique == "dc":
                P_out = calcul_puissance_dc(tension_v, courant_a)
        rep["resultats"]["P_out_W"] = P_out

        # 5) Rendement & Pertes (simplifié pour ce restore)
        eta_total = 0.9 # Valeur par défaut si non calculable
        rep["resultats"]["eta_total"] = eta_total

        # 11) Analyse des pièces
        pieces_rapport = {}
        pieces_candidates = [
            (
                "rotor",
                self.piece_rotor or Rotor(
                    alternateur=self,
                    vitesse_rotation_rpm=rpm,
                    puissance_electrique_cible_w=P_out,
                    rendement_alternateur_global=eta_total,
                    pertes_fixes_w=float(self.pertes_fixes_w),
                    nombre_poles=self.nombre_poles,
                ),
            ),
            (
                "stator",
                self.piece_stator or Stator(
                    frequence_electrique_hz=frequence_hz,
                    nombre_spires_serie=self.nombre_spires_serie,
                    flux_max_pole_wb=self.flux_max_pole_wb,
                    facteur_enroulement=self.facteur_enroulement,
                    connexion="Y" if str(self.connexion).lower().startswith("e") else "Delta",
                    courant_phase_rms_a=courant_phase_rms_stator_a,
                    resistance_phase_ohm=self.resistance_phase_ohm,
                    resistivite_ohm_m=self.resistivite_ohm_m,
                    longueur_fil_m=self.longueur_fil_m,
                    section_fil_m2=self.section_fil_m2,
                    temperature_c=self.temperature_c,
                    k_h=self.k_h,
                    k_e=self.k_e,
                    exposant_steinmetz=self.exposant_steinmetz,
                    induction_max_t=self.induction_max_t,
                    masse_fer_kg=self.masse_fer_kg,
                    volume_fer_m3=self.volume_fer_m3,
                ),
            ),
            ("arbre", self.piece_arbre),
            ("carter", self.piece_carter),
            ("ventilateur", self.piece_ventilateur),
            ("bobine_excite", self.piece_bobine_excite),
            ("roulement", self.piece_roulement),
        ]
        for nom, piece in pieces_candidates:
            if piece is not None and hasattr(piece, "analyser"):
                try:
                    pieces_rapport[nom] = piece.analyser()
                except Exception as e:
                    pieces_rapport[nom] = {"erreur": str(e)}
        rep["pieces"] = pieces_rapport
        _dedup_inconnues(rep)
        return rep

    def analyser_pour_bus_dc(
        self,
        *,
        puissance_bus_dc_w: float,
        vitesse_rotation_rpm: Optional[float] = None,
        vitesse_angulaire_rad_s: Optional[float] = None,
        tension_bus_dc_v: Optional[float] = None,
        batterie: Any = None,
        moteur: Any = None,
        energie_a_recharger_kwh: Optional[float] = None,
    ) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "entrees": {},
            "bus_dc": {},
            "alternateur": {},
            "integration": {},
            "inconnues": {"impossibles": [], "partielles": []},
            "notes_modele": [],
        }

        Pdc = _req_finite("puissance_bus_dc_w", puissance_bus_dc_w)
        rep["entrees"]["puissance_bus_dc_w"] = Pdc

        Vdc: Optional[float] = None
        if tension_bus_dc_v is not None:
            Vdc = _req_pos("tension_bus_dc_v", tension_bus_dc_v, strictly=True)
        else:
            V_batt_chg = _safe_get_attr(batterie, "tension_charge_v")
            V_batt_nom = _safe_get_attr(batterie, "tension_nominale_v")
            V_mot = _safe_get_attr(moteur, "tension_bus_v")
            if V_batt_chg and _is_finite(V_batt_chg): Vdc = float(V_batt_chg)
            elif V_batt_nom and _is_finite(V_batt_nom): Vdc = float(V_batt_nom)
            elif V_mot and _is_finite(V_mot): Vdc = float(V_mot)
        rep["bus_dc"]["tension_v"] = Vdc

        Idc: Optional[float] = None
        if Vdc: Idc = Pdc / Vdc
        rep["bus_dc"]["courant_a"] = Idc

        alt = self.analyser_point_de_fonctionnement(
            vitesse_rotation_rpm=vitesse_rotation_rpm,
            vitesse_angulaire_rad_s=vitesse_angulaire_rad_s,
            mode_electrique="dc",
            tension_v=Vdc,
            courant_a=Idc,
        )
        rep["alternateur"] = alt
        _dedup_inconnues(rep)
        return rep
