# backend/ensemble/materiaux.py
# Ensemble de matériaux pour les composants du système
# Données orientées RDM (SI) + quelques propriétés thermiques/électriques utiles.
#
# IMPORTANT (RDM) :
# - Les propriétés dépendent fortement de l'état métallurgique (T6, recuit, QT, trempe+revenu, etc.),
#   de la forme (barre/forgé/laminé), et parfois de la dimension (effets de trempabilité).
# - Ce module stocke donc soit des VALEURS typiques, soit des INTERVALLES, soit des COURBES
#   (ex : résistance en fonction du diamètre/épaisseur, ou du revenu).
#
# SOURCES PRINCIPALES (références dans les commentaires de chaque matériau) :
# - Al 6061-T6 : Clinton Aluminum "Grade 6061-T6 / 6061-T651 Text Data" (PDF)
# - Al 7075 : Gabrian "7075 Aluminum Alloy: Properties" (PDF)
# - 42CrMo4 : Lucefin "42CrMo4 1.7225 – 42CrMoS4 1.7227" (PDF)
# - 100Cr6 : Lucefin "100Cr6 1.3505"
# - EN-GJL-250 : NORELEM fiche "Cast iron EN-GJL-250" (PDF)
# - Inox 304 : AZoM "Stainless Steel - Grade 304 (UNS S30400)"
# - CuSn12 : MakeItFrom "CuSn12 / CW453K"
# - ABS : Xometry "Data Sheet: ABS"
# - PTFE : DuPont "Teflon™ PTFE Properties Handbook"

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Union, Any
import json
from pathlib import Path
import math

# =========================
# Unités SI (conventions)
# =========================
MPA = 1e6
GPA = 1e9


# =========================
# Types utilitaires
# =========================
@dataclass(frozen=True)
class Intervalle:
    """Intervalle [min, max] en unités SI."""
    mini: float
    maxi: float

    def typique(self) -> float:
        return 0.5 * (self.mini + self.maxi)

    def verifier(self) -> None:
        if self.mini > self.maxi:
            raise ValueError(f"Intervalle invalide: {self.mini} > {self.maxi}")


Valeur = Union[float, Intervalle]


def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def valeur(prop: Optional[Valeur], mode: str = "typique") -> Optional[float]:
    """
    Convertit une propriété (float ou Intervalle) en float selon mode.
    mode:
      - "typique" (par défaut)
      - "min"
      - "max"
    """
    if prop is None:
        return None
    if isinstance(prop, Intervalle):
        prop.verifier()
        if mode == "min":
            return prop.mini
        if mode == "max":
            return prop.maxi
        if mode == "typique":
            return prop.typique()
        raise ValueError(f"mode inconnu: {mode}")
    return float(prop)


@dataclass(frozen=True)
class SegmentResistanceSection:
    """
    Propriétés mécaniques dépendant d'une dimension de section (diamètre/épaisseur).
    Les valeurs sont conservatrices si vous utilisez mode="min" pour la résistance.
    """
    section_min_mm: float
    section_max_mm: float
    rp02_pa_min: Optional[float] = None
    rm_pa: Optional[Valeur] = None
    a_pct_min: Optional[float] = None
    kv_j_min: Optional[float] = None

    def contient(self, section_mm: float) -> bool:
        return self.section_min_mm <= section_mm <= self.section_max_mm


@dataclass
class Materiau:
    """
    Matériau isotrope (approx.) avec propriétés SI.
    - module_young_pa : Pa
    - densite_kg_m3 : kg/m³
    - conductivite_thermique_w_mk : W/(m·K)
    - capacite_calorifique_j_kgk : J/(kg·K)
    - alpha_dilatation_1_k : 1/K
    - limites (Pa) : Rp0.2 / Rm / fatigue si dispo
    """

    cle: str
    nom: str
    famille: str  # métal, polymère, élastomère, etc.

    densite_kg_m3: Optional[float] = None
    module_young_pa: Optional[Valeur] = None
    poisson: Optional[Valeur] = None

    # Résistances (Pa)
    limite_elastique_pa: Optional[Valeur] = None
    resistance_traction_pa: Optional[Valeur] = None
    limite_fatigue_pa: Optional[Valeur] = None

    # Dureté (valeurs typiques / intervalles)
    durete: Dict[str, Valeur] = field(default_factory=dict)

    # Thermique
    conductivite_thermique_w_mk: Optional[Valeur] = None
    capacite_calorifique_j_kgk: Optional[Valeur] = None
    alpha_dilatation_1_k: Optional[Valeur] = None
    temperature_service_min_c: Optional[float] = None
    temperature_service_max_c: Optional[float] = None
    point_fusion_c: Optional[Valeur] = None

    # Électrique
    resistivite_ohm_m: Optional[Valeur] = None

    # Économie / industrialisation
    cout_matiere_eur_kg: Optional[Valeur] = None
    usinabilite_indice: Optional[Valeur] = None      # 0..1 (1 = très facile à usiner)
    disponibilite_indice: Optional[Valeur] = None    # 0..1 (1 = très disponible)
    recyclabilite_indice: Optional[Valeur] = None    # 0..1

    # Tribologie / interface
    coefficient_frottement_sec: Optional[Valeur] = None
    coefficient_frottement_lubr: Optional[Valeur] = None

    # Courbes / tables optionnelles
    resistance_par_section: Tuple[SegmentResistanceSection, ...] = tuple()

    # Notes / sources
    notes: str = ""

    # -------------------------
    # Propriétés dérivées RDM
    # -------------------------
    def module_cisaillement_pa(self, mode: str = "typique") -> Optional[float]:
        """
        G = E / (2*(1+nu)) (isotrope).
        """
        E = valeur(self.module_young_pa, mode=mode)
        nu = valeur(self.poisson, mode=mode)
        if E is None or nu is None:
            return None
        if not (-0.99 < nu < 0.5):
            raise ValueError(f"Poisson invalide pour {self.cle}: nu={nu}")
        return E / (2.0 * (1.0 + nu))

    def module_compression_pa(self, mode: str = "typique") -> Optional[float]:
        """
        K = E / (3*(1-2*nu)) (isotrope).
        """
        E = valeur(self.module_young_pa, mode=mode)
        nu = valeur(self.poisson, mode=mode)
        if E is None or nu is None:
            return None
        if not (-0.99 < nu < 0.5):
            raise ValueError(f"Poisson invalide pour {self.cle}: nu={nu}")
        denom = 3.0 * (1.0 - 2.0 * nu)
        if abs(denom) < 1e-12:
            return None
        return E / denom

    def masse_kg(self, volume_m3: float) -> float:
        if self.densite_kg_m3 is None:
            raise ValueError(f"Densité inconnue pour {self.cle}")
        if volume_m3 < 0:
            raise ValueError("volume_m3 doit être >= 0")
        return self.densite_kg_m3 * volume_m3

    def cout_matiere_estime_eur(self, volume_m3: float, mode: str = "typique") -> Optional[float]:
        """
        Coût matière brut = masse * coût/kg
        """
        c = valeur(self.cout_matiere_eur_kg, mode=mode)
        if c is None or self.densite_kg_m3 is None:
            return None
        if volume_m3 < 0.0:
            raise ValueError("volume_m3 doit être >= 0")
        return self.densite_kg_m3 * volume_m3 * c

    def limite_elastique_effective_pa(
        self,
        mode: str = "min",
        section_mm: Optional[float] = None,
    ) -> Optional[float]:
        """
        Renvoie Rp0.2 (ou Re) en Pa.
        """
        if section_mm is not None and self.resistance_par_section:
            for seg in self.resistance_par_section:
                if seg.contient(section_mm) and seg.rp02_pa_min is not None:
                    return seg.rp02_pa_min
        return valeur(self.limite_elastique_pa, mode=mode)

    def resistance_traction_effective_pa(
        self,
        mode: str = "min",
        section_mm: Optional[float] = None,
    ) -> Optional[float]:
        """
        Renvoie Rm en Pa.
        """
        if section_mm is not None and self.resistance_par_section:
            for seg in self.resistance_par_section:
                if seg.contient(section_mm) and seg.rm_pa is not None:
                    return valeur(seg.rm_pa, mode=mode)
        return valeur(self.resistance_traction_pa, mode=mode)

    def limite_fatigue_effective_pa(
        self,
        mode: str = "min",
    ) -> Optional[float]:
        return valeur(self.limite_fatigue_pa, mode=mode)

    def sigma_admissible_pa(
        self,
        coef_securite: float = 1.5,
        section_mm: Optional[float] = None,
        critere: str = "elasticite",
    ) -> float:
        """
        Contrainte admissible (Pa) = résistance / coef_securite.
        critere:
          - "elasticite" -> Rp0.2
          - "rupture"    -> Rm
          - "fatigue"    -> limite_fatigue
        """
        if coef_securite <= 0:
            raise ValueError("coef_securite doit être > 0")

        if critere == "elasticite":
            base = self.limite_elastique_effective_pa(mode="min", section_mm=section_mm)
        elif critere == "rupture":
            base = self.resistance_traction_effective_pa(mode="min", section_mm=section_mm)
        elif critere == "fatigue":
            base = self.limite_fatigue_effective_pa(mode="min")
        else:
            raise ValueError(f"critere inconnu: {critere}")

        if base is None:
            raise ValueError(f"Résistance inconnue pour {self.cle} (critere={critere})")
        return base / coef_securite

    def tau_admissible_pa(
        self,
        coef_securite: float = 1.5,
        section_mm: Optional[float] = None,
        hypothese: str = "von_mises",
    ) -> float:
        """
        Cisaillement admissible (Pa) à partir de Rp0.2.
        - von Mises : tau_y ≈ Rp0.2 / sqrt(3)
        - Tresca    : tau_y ≈ Rp0.2 / 2
        Puis / coef_securite.
        """
        rp = self.limite_elastique_effective_pa(mode="min", section_mm=section_mm)
        if rp is None:
            raise ValueError(f"Limite élastique inconnue pour {self.cle}")
        if hypothese == "von_mises":
            tau_y = rp / math.sqrt(3.0)
        elif hypothese == "tresca":
            tau_y = rp / 2.0
        else:
            raise ValueError(f"hypothese inconnue: {hypothese}")
        if coef_securite <= 0:
            raise ValueError("coef_securite doit être > 0")
        return tau_y / coef_securite

    def coeff_dilatation_lineaire(self, mode: str = "typique") -> Optional[float]:
        return valeur(self.alpha_dilatation_1_k, mode=mode)

    def dilatation_lineaire_m(
        self,
        longueur_m: float,
        delta_temperature_k: float,
        mode: str = "typique",
    ) -> Optional[float]:
        alpha = self.coeff_dilatation_lineaire(mode=mode)
        if alpha is None:
            return None
        if longueur_m < 0:
            raise ValueError("longueur_m doit être >= 0")
        return alpha * longueur_m * delta_temperature_k

    def diffusivite_thermique_m2_s(self, mode: str = "typique") -> Optional[float]:
        """
        a = k / (rho * cp)
        """
        k = valeur(self.conductivite_thermique_w_mk, mode=mode)
        cp = valeur(self.capacite_calorifique_j_kgk, mode=mode)
        rho = self.densite_kg_m3
        if k is None or cp is None or rho is None or rho <= 0.0 or cp <= 0.0:
            return None
        return k / (rho * cp)

    def diffusivite_electrique_s_m(self, mode: str = "typique") -> Optional[float]:
        """
        Sigma = 1 / rho_elec
        """
        rho_elec = valeur(self.resistivite_ohm_m, mode=mode)
        if rho_elec is None or rho_elec <= 0.0:
            return None
        return 1.0 / rho_elec

    def rigidite_specifique(self, mode: str = "typique") -> Optional[float]:
        """
        E / rho
        """
        E = valeur(self.module_young_pa, mode=mode)
        rho = self.densite_kg_m3
        if E is None or rho is None or rho <= 0.0:
            return None
        return E / rho

    def resistance_specifique_elastique(self, mode: str = "min") -> Optional[float]:
        """
        Rp0.2 / rho
        """
        rp = self.limite_elastique_effective_pa(mode=mode)
        rho = self.densite_kg_m3
        if rp is None or rho is None or rho <= 0.0:
            return None
        return rp / rho

    def temperature_service_ok(self, temperature_c: float) -> Optional[bool]:
        tmin = self.temperature_service_min_c
        tmax = self.temperature_service_max_c
        if tmin is None and tmax is None:
            return None
        if tmin is not None and temperature_c < tmin:
            return False
        if tmax is not None and temperature_c > tmax:
            return False
        return True

    def resume_dimensionnement(
        self,
        *,
        mode: str = "typique",
        coef_securite: float = 1.5,
        section_mm: Optional[float] = None,
        temperature_service_c: Optional[float] = None,
        volume_m3: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Résumé directement exploitable par les autres composants.
        """
        out: Dict[str, Any] = {
            "cle": self.cle,
            "nom": self.nom,
            "famille": self.famille,
            "densite_kg_m3": self.densite_kg_m3,
            "module_young_pa": valeur(self.module_young_pa, mode=mode),
            "module_cisaillement_pa": self.module_cisaillement_pa(mode=mode),
            "poisson": valeur(self.poisson, mode=mode),
            "limite_elastique_pa": self.limite_elastique_effective_pa(mode="min", section_mm=section_mm),
            "resistance_traction_pa": self.resistance_traction_effective_pa(mode="min", section_mm=section_mm),
            "limite_fatigue_pa": self.limite_fatigue_effective_pa(mode="min"),
            "sigma_admissible_elastique_pa": None,
            "tau_admissible_von_mises_pa": None,
            "tau_admissible_tresca_pa": None,
            "conductivite_thermique_w_mk": valeur(self.conductivite_thermique_w_mk, mode=mode),
            "capacite_calorifique_j_kgk": valeur(self.capacite_calorifique_j_kgk, mode=mode),
            "alpha_dilatation_1_k": valeur(self.alpha_dilatation_1_k, mode=mode),
            "diffusivite_thermique_m2_s": self.diffusivite_thermique_m2_s(mode=mode),
            "resistivite_ohm_m": valeur(self.resistivite_ohm_m, mode=mode),
            "conductivite_electrique_s_m": self.diffusivite_electrique_s_m(mode=mode),
            "cout_matiere_eur_kg": valeur(self.cout_matiere_eur_kg, mode=mode),
            "usinabilite_indice": valeur(self.usinabilite_indice, mode=mode),
            "disponibilite_indice": valeur(self.disponibilite_indice, mode=mode),
            "recyclabilite_indice": valeur(self.recyclabilite_indice, mode=mode),
            "coefficient_frottement_sec": valeur(self.coefficient_frottement_sec, mode=mode),
            "coefficient_frottement_lubr": valeur(self.coefficient_frottement_lubr, mode=mode),
            "rigidite_specifique": self.rigidite_specifique(mode=mode),
            "resistance_specifique_elastique": self.resistance_specifique_elastique(mode="min"),
            "temperature_service_ok": self.temperature_service_ok(temperature_service_c) if temperature_service_c is not None else None,
            "notes": self.notes,
        }

        try:
            out["sigma_admissible_elastique_pa"] = self.sigma_admissible_pa(
                coef_securite=coef_securite,
                section_mm=section_mm,
                critere="elasticite",
            )
        except Exception:
            out["sigma_admissible_elastique_pa"] = None

        try:
            out["tau_admissible_von_mises_pa"] = self.tau_admissible_pa(
                coef_securite=coef_securite,
                section_mm=section_mm,
                hypothese="von_mises",
            )
        except Exception:
            out["tau_admissible_von_mises_pa"] = None

        try:
            out["tau_admissible_tresca_pa"] = self.tau_admissible_pa(
                coef_securite=coef_securite,
                section_mm=section_mm,
                hypothese="tresca",
            )
        except Exception:
            out["tau_admissible_tresca_pa"] = None

        if volume_m3 is not None:
            try:
                out["masse_kg"] = self.masse_kg(volume_m3)
            except Exception:
                out["masse_kg"] = None
            try:
                out["cout_matiere_estime_eur"] = self.cout_matiere_estime_eur(volume_m3, mode=mode)
            except Exception:
                out["cout_matiere_estime_eur"] = None

        return out


# =========================
# Catalogue matériaux
# =========================

MATERIAUX: Dict[str, Materiau] = {}


def _register(m: Materiau) -> Materiau:
    if m.cle in MATERIAUX:
        raise KeyError(f"Matériau déjà enregistré: {m.cle}")
    MATERIAUX[m.cle] = m
    return m


# -------------------------
# Aluminium 6061-T6 / T651
# -------------------------
_register(Materiau(
    cle="alu_6061_t6",
    nom="Aluminium 6061-T6 / 6061-T651",
    famille="metal",
    densite_kg_m3=2700.0,
    module_young_pa=68.9 * GPA,
    poisson=0.330,
    limite_elastique_pa=276.0 * MPA,
    resistance_traction_pa=310.0 * MPA,
    limite_fatigue_pa=96.5 * MPA,
    durete={"HBW": 95.0},
    conductivite_thermique_w_mk=167.0,
    capacite_calorifique_j_kgk=0.896 * 1000.0,
    alpha_dilatation_1_k=23.6e-6,
    point_fusion_c=Intervalle(582.0, 651.7),
    resistivite_ohm_m=3.99e-8,
    cout_matiere_eur_kg=Intervalle(4.0, 8.0),
    usinabilite_indice=0.85,
    disponibilite_indice=0.90,
    recyclabilite_indice=0.95,
    coefficient_frottement_sec=Intervalle(0.40, 0.60),
    coefficient_frottement_lubr=Intervalle(0.05, 0.12),
    notes="Source principale: Clinton Aluminum Grade 6061-T6/T651 (PDF).",
))

# -------------------------
# Aluminium 7075-T6 / T651
# -------------------------
_register(Materiau(
    cle="alu_7075_t6",
    nom="Aluminium 7075-T6 / 7075-T651",
    famille="metal",
    densite_kg_m3=2810.0,
    module_young_pa=71.7 * GPA,
    limite_elastique_pa=503.0 * MPA,
    resistance_traction_pa=572.0 * MPA,
    alpha_dilatation_1_k=23.4e-6,
    capacite_calorifique_j_kgk=0.960 * 1000.0,
    cout_matiere_eur_kg=Intervalle(8.0, 16.0),
    usinabilite_indice=0.70,
    disponibilite_indice=0.75,
    recyclabilite_indice=0.90,
    coefficient_frottement_sec=Intervalle(0.35, 0.55),
    coefficient_frottement_lubr=Intervalle(0.05, 0.10),
    notes="Source principale: Gabrian 7075 Aluminum Alloy Properties (PDF).",
))

# -------------------------
# Acier allié 42CrMo4 (1.7225)
# -------------------------
_register(Materiau(
    cle="acier_42crmo4_qt",
    nom="Acier 42CrMo4 (1.7225) — état trempé + revenu (QT)",
    famille="metal",
    densite_kg_m3=7800.0,
    module_young_pa=210.0 * GPA,
    poisson=0.30,
    conductivite_thermique_w_mk=Intervalle(40.0, 46.0),
    capacite_calorifique_j_kgk=Intervalle(460.0, 480.0),
    alpha_dilatation_1_k=12.0e-6,
    cout_matiere_eur_kg=Intervalle(2.0, 5.0),
    usinabilite_indice=0.60,
    disponibilite_indice=0.90,
    recyclabilite_indice=0.95,
    coefficient_frottement_sec=Intervalle(0.50, 0.80),
    coefficient_frottement_lubr=Intervalle(0.06, 0.12),
    resistance_par_section=(
        SegmentResistanceSection(16.0, 40.0, rp02_pa_min=750.0 * MPA, rm_pa=Intervalle(1000.0 * MPA, 1200.0 * MPA), a_pct_min=11.0, kv_j_min=35.0),
        SegmentResistanceSection(40.0, 63.0, rp02_pa_min=650.0 * MPA, rm_pa=Intervalle(900.0 * MPA, 1100.0 * MPA), a_pct_min=12.0, kv_j_min=35.0),
        SegmentResistanceSection(63.0, 100.0, rp02_pa_min=650.0 * MPA, rm_pa=Intervalle(900.0 * MPA, 1100.0 * MPA), a_pct_min=12.0, kv_j_min=35.0),
    ),
    notes=(
        "Courbe QT issue de Lucefin (QT+SH). "
        "E, ν, densité/thermique: valeurs génériques acier à verrouiller via votre fiche matière interne."
    ),
))

# -------------------------
# Acier à roulement 100Cr6 (1.3505)
# -------------------------
_register(Materiau(
    cle="acier_100cr6",
    nom="Acier à roulement 100Cr6 (1.3505)",
    famille="metal",
    densite_kg_m3=7810.0,
    module_young_pa=210.0 * GPA,
    poisson=0.30,
    conductivite_thermique_w_mk=46.6,
    capacite_calorifique_j_kgk=475.0,
    alpha_dilatation_1_k=12.0e-6,
    cout_matiere_eur_kg=Intervalle(3.0, 8.0),
    usinabilite_indice=0.45,
    disponibilite_indice=0.85,
    recyclabilite_indice=0.95,
    coefficient_frottement_sec=Intervalle(0.50, 0.80),
    coefficient_frottement_lubr=Intervalle(0.04, 0.10),
    notes=(
        "Propriétés mécaniques très dépendantes du traitement (trempe + revenu). "
        "Ajouter une table dédiée si vous voulez dimensionner selon une température de revenu."
    ),
))

# -------------------------
# Fonte grise EN-GJL-250 (GG25)
# -------------------------
_register(Materiau(
    cle="fonte_en_gjl_250",
    nom="Fonte grise EN-GJL-250 (GG25)",
    famille="metal",
    densite_kg_m3=7200.0,
    module_young_pa=Intervalle(103.0 * GPA, 118.0 * GPA),
    limite_elastique_pa=Intervalle(165.0 * MPA, 228.0 * MPA),
    resistance_traction_pa=Intervalle(250.0 * MPA, 350.0 * MPA),
    durete={"HBW": Intervalle(190.0, 230.0)},
    cout_matiere_eur_kg=Intervalle(1.0, 3.0),
    usinabilite_indice=0.80,
    disponibilite_indice=0.85,
    recyclabilite_indice=0.90,
    coefficient_frottement_sec=Intervalle(0.45, 0.70),
    coefficient_frottement_lubr=Intervalle(0.05, 0.12),
    notes=(
        "Limite élastique donnée Rp0.1 (NORELEM). "
        "Pour calculs RDM fins (fatigue, thermo), compléter avec fiche fabricant."
    ),
))

# -------------------------
# Inox austénitique 304 (UNS S30400)
# -------------------------
_register(Materiau(
    cle="inox_304",
    nom="Inox 304 (UNS S30400)",
    famille="metal",
    densite_kg_m3=8000.0,
    module_young_pa=193.0 * GPA,
    poisson=0.29,
    limite_elastique_pa=215.0 * MPA,
    resistance_traction_pa=505.0 * MPA,
    conductivite_thermique_w_mk=16.2,
    capacite_calorifique_j_kgk=500.0,
    alpha_dilatation_1_k=17.2e-6,
    point_fusion_c=Intervalle(1400.0, 1450.0),
    cout_matiere_eur_kg=Intervalle(3.0, 7.0),
    usinabilite_indice=0.40,
    disponibilite_indice=0.90,
    recyclabilite_indice=0.95,
    coefficient_frottement_sec=Intervalle(0.50, 0.85),
    coefficient_frottement_lubr=Intervalle(0.08, 0.15),
    notes="Source: AZoM (Grade 304). Valeurs typiques (dépendent de l’état/écrouissage).",
))

# -------------------------
# Bronze CuSn12 (phosphore)
# -------------------------
_register(Materiau(
    cle="bronze_cusn12",
    nom="Bronze CuSn12 (CW453K) — bronze phosphoreux",
    famille="metal",
    densite_kg_m3=8.69 * 1000.0,
    module_young_pa=110.0 * GPA,
    poisson=0.34,
    limite_elastique_pa=170.0 * MPA,
    resistance_traction_pa=310.0 * MPA,
    conductivite_thermique_w_mk=54.4,
    capacite_calorifique_j_kgk=376.0,
    alpha_dilatation_1_k=18.0e-6,
    cout_matiere_eur_kg=Intervalle(7.0, 15.0),
    usinabilite_indice=0.65,
    disponibilite_indice=0.70,
    recyclabilite_indice=0.95,
    coefficient_frottement_sec=Intervalle(0.25, 0.45),
    coefficient_frottement_lubr=Intervalle(0.03, 0.08),
    notes="Source: MakeItFrom CuSn12/CW453K. Peut varier selon état (écroui/recuit).",
))

# -------------------------
# ABS (thermoplastique)
# -------------------------
_register(Materiau(
    cle="abs",
    nom="ABS (Acrylonitrile Butadiene Styrene)",
    famille="polymere",
    densite_kg_m3=1.06 * 1000.0,
    module_young_pa=Intervalle(2.0 * GPA, 2.6 * GPA),
    resistance_traction_pa=Intervalle(42.5 * MPA, 44.8 * MPA),
    conductivite_thermique_w_mk=0.1,
    capacite_calorifique_j_kgk=900.0,
    alpha_dilatation_1_k=120e-6,
    temperature_service_max_c=89.0,
    cout_matiere_eur_kg=Intervalle(2.0, 5.0),
    usinabilite_indice=0.75,
    disponibilite_indice=0.95,
    recyclabilite_indice=0.60,
    coefficient_frottement_sec=Intervalle(0.30, 0.50),
    coefficient_frottement_lubr=Intervalle(0.08, 0.16),
    notes="Source: Xometry ABS datasheet. Les polymères varient beaucoup selon grade/process.",
))

# -------------------------
# PTFE (Teflon)
# -------------------------
_register(Materiau(
    cle="ptfe",
    nom="PTFE (Polytetrafluoroethylene, Teflon™)",
    famille="polymere",
    densite_kg_m3=2200.0,
    module_young_pa=Intervalle(0.4 * GPA, 0.6 * GPA),
    resistance_traction_pa=Intervalle(15.0 * MPA, 30.0 * MPA),
    conductivite_thermique_w_mk=0.25,
    alpha_dilatation_1_k=1.0e-4,
    durete={"ShoreD": Intervalle(50.0, 65.0)},
    temperature_service_min_c=-200.0,
    temperature_service_max_c=260.0,
    cout_matiere_eur_kg=Intervalle(8.0, 20.0),
    usinabilite_indice=0.85,
    disponibilite_indice=0.85,
    recyclabilite_indice=0.40,
    coefficient_frottement_sec=Intervalle(0.04, 0.12),
    coefficient_frottement_lubr=Intervalle(0.03, 0.08),
    notes="Source thermique/CTE/dureté: DuPont PTFE Handbook. Les mécaniques sont très grade-dépendantes.",
))


# =========================
# API simple
# =========================
def get_materiau(cle: str) -> Materiau:
    try:
        return MATERIAUX[cle]
    except KeyError as e:
        raise KeyError(f"Matériau inconnu: {cle}. Disponibles: {', '.join(sorted(MATERIAUX))}") from e


def lister_materiaux(famille: Optional[str] = None) -> List[Materiau]:
    mats = list(MATERIAUX.values())
    if famille is None:
        return sorted(mats, key=lambda m: m.cle)
    return sorted([m for m in mats if m.famille == famille], key=lambda m: m.cle)


def existe_materiau(cle: str) -> bool:
    return cle in MATERIAUX


def resume_materiau(
    cle: str,
    *,
    mode: str = "typique",
    coef_securite: float = 1.5,
    section_mm: Optional[float] = None,
    temperature_service_c: Optional[float] = None,
    volume_m3: Optional[float] = None,
) -> Dict[str, Any]:
    return get_materiau(cle).resume_dimensionnement(
        mode=mode,
        coef_securite=coef_securite,
        section_mm=section_mm,
        temperature_service_c=temperature_service_c,
        volume_m3=volume_m3,
    )


def sigma_admissible_materiau(
    cle: str,
    *,
    coef_securite: float = 1.5,
    section_mm: Optional[float] = None,
    critere: str = "elasticite",
) -> float:
    return get_materiau(cle).sigma_admissible_pa(
        coef_securite=coef_securite,
        section_mm=section_mm,
        critere=critere,
    )


def tau_admissible_materiau(
    cle: str,
    *,
    coef_securite: float = 1.5,
    section_mm: Optional[float] = None,
    hypothese: str = "von_mises",
) -> float:
    return get_materiau(cle).tau_admissible_pa(
        coef_securite=coef_securite,
        section_mm=section_mm,
        hypothese=hypothese,
    )


def masse_materiau_kg(cle: str, volume_m3: float) -> float:
    return get_materiau(cle).masse_kg(volume_m3)


def cout_matiere_estime_eur(cle: str, volume_m3: float, *, mode: str = "typique") -> Optional[float]:
    return get_materiau(cle).cout_matiere_estime_eur(volume_m3, mode=mode)


def comparer_materiaux(
    cles: Iterable[str],
    *,
    mode: str = "typique",
    coef_securite: float = 1.5,
    section_mm: Optional[float] = None,
    temperature_service_c: Optional[float] = None,
    volume_m3: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Compare plusieurs matériaux sur une base homogène.
    """
    rows: List[Dict[str, Any]] = []
    for cle in cles:
        m = get_materiau(cle)
        row = m.resume_dimensionnement(
            mode=mode,
            coef_securite=coef_securite,
            section_mm=section_mm,
            temperature_service_c=temperature_service_c,
            volume_m3=volume_m3,
        )
        rows.append(row)
    return rows


def choisir_materiau_par_objectif(
    *,
    famille: Optional[str] = None,
    contrainte_sigma_min_pa: Optional[float] = None,
    contrainte_tau_min_pa: Optional[float] = None,
    temperature_service_c: Optional[float] = None,
    volume_m3: Optional[float] = None,
    max_cout_matiere_eur: Optional[float] = None,
    objectif: str = "leger",
    coef_securite: float = 1.5,
    section_mm: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Sélectionne des matériaux compatibles, puis les trie selon un objectif :
      - "leger"
      - "rigide"
      - "resistant"
      - "economique"
      - "thermique"
      - "electrique"

    Le tri est purement calculatoire sur les données disponibles.
    """
    candidats = lister_materiaux(famille=famille)

    rows: List[Dict[str, Any]] = []
    for m in candidats:
        row = m.resume_dimensionnement(
            mode="typique",
            coef_securite=coef_securite,
            section_mm=section_mm,
            temperature_service_c=temperature_service_c,
            volume_m3=volume_m3,
        )

        sigma_ok = True
        if contrainte_sigma_min_pa is not None:
            sigma_adm = row.get("sigma_admissible_elastique_pa")
            sigma_ok = _is_finite(sigma_adm) and float(sigma_adm) >= float(contrainte_sigma_min_pa)

        tau_ok = True
        if contrainte_tau_min_pa is not None:
            tau_adm = row.get("tau_admissible_von_mises_pa")
            tau_ok = _is_finite(tau_adm) and float(tau_adm) >= float(contrainte_tau_min_pa)

        temp_ok = True
        if temperature_service_c is not None:
            tst = row.get("temperature_service_ok")
            temp_ok = (tst is None) or bool(tst)

        cout_ok = True
        if max_cout_matiere_eur is not None:
            c = row.get("cout_matiere_estime_eur")
            cout_ok = (c is None) or (float(c) <= float(max_cout_matiere_eur))

        if sigma_ok and tau_ok and temp_ok and cout_ok:
            rows.append(row)

    def key_leger(r: Dict[str, Any]) -> Tuple[float, float]:
        masse = r.get("masse_kg")
        rho = r.get("densite_kg_m3")
        return (
            float(masse) if _is_finite(masse) else float("inf"),
            float(rho) if _is_finite(rho) else float("inf"),
        )

    def key_rigide(r: Dict[str, Any]) -> Tuple[float, float]:
        rs = r.get("rigidite_specifique")
        E = r.get("module_young_pa")
        return (
            -float(rs) if _is_finite(rs) else float("inf"),
            -float(E) if _is_finite(E) else float("inf"),
        )

    def key_resistant(r: Dict[str, Any]) -> Tuple[float, float]:
        se = r.get("resistance_specifique_elastique")
        s = r.get("sigma_admissible_elastique_pa")
        return (
            -float(se) if _is_finite(se) else float("inf"),
            -float(s) if _is_finite(s) else float("inf"),
        )

    def key_economique(r: Dict[str, Any]) -> Tuple[float, float]:
        c = r.get("cout_matiere_estime_eur")
        ck = r.get("cout_matiere_eur_kg")
        return (
            float(c) if _is_finite(c) else float("inf"),
            float(ck) if _is_finite(ck) else float("inf"),
        )

    def key_thermique(r: Dict[str, Any]) -> Tuple[float, float]:
        k = r.get("conductivite_thermique_w_mk")
        a = r.get("diffusivite_thermique_m2_s")
        return (
            -float(k) if _is_finite(k) else float("inf"),
            -float(a) if _is_finite(a) else float("inf"),
        )

    def key_electrique(r: Dict[str, Any]) -> Tuple[float, float]:
        sig = r.get("conductivite_electrique_s_m")
        rho = r.get("resistivite_ohm_m")
        return (
            -float(sig) if _is_finite(sig) else float("inf"),
            float(rho) if _is_finite(rho) else float("inf"),
        )

    if objectif == "leger":
        rows.sort(key=key_leger)
    elif objectif == "rigide":
        rows.sort(key=key_rigide)
    elif objectif == "resistant":
        rows.sort(key=key_resistant)
    elif objectif == "economique":
        rows.sort(key=key_economique)
    elif objectif == "thermique":
        rows.sort(key=key_thermique)
    elif objectif == "electrique":
        rows.sort(key=key_electrique)
    else:
        raise ValueError(f"objectif inconnu: {objectif}")

    return rows


# =========================
# Import/Export JSON
# =========================
def exporter_json(path: Union[str, Path]) -> None:
    """
    Exporte le catalogue en JSON (valeurs SI).
    Remarque: Intervalle devient {"min":..., "max":...}
    """
    def ser(v: object) -> object:
        if isinstance(v, Intervalle):
            return {"min": v.mini, "max": v.maxi}
        if isinstance(v, SegmentResistanceSection):
            return {
                "section_min_mm": v.section_min_mm,
                "section_max_mm": v.section_max_mm,
                "rp02_pa_min": v.rp02_pa_min,
                "rm_pa": ser(v.rm_pa) if v.rm_pa is not None else None,
                "a_pct_min": v.a_pct_min,
                "kv_j_min": v.kv_j_min,
            }
        return v

    data = {}
    for k, m in MATERIAUX.items():
        data[k] = {
            "cle": m.cle,
            "nom": m.nom,
            "famille": m.famille,
            "densite_kg_m3": m.densite_kg_m3,
            "module_young_pa": ser(m.module_young_pa),
            "poisson": ser(m.poisson),
            "limite_elastique_pa": ser(m.limite_elastique_pa),
            "resistance_traction_pa": ser(m.resistance_traction_pa),
            "limite_fatigue_pa": ser(m.limite_fatigue_pa),
            "durete": {hk: ser(hv) for hk, hv in m.durete.items()},
            "conductivite_thermique_w_mk": ser(m.conductivite_thermique_w_mk),
            "capacite_calorifique_j_kgk": ser(m.capacite_calorifique_j_kgk),
            "alpha_dilatation_1_k": ser(m.alpha_dilatation_1_k),
            "temperature_service_min_c": m.temperature_service_min_c,
            "temperature_service_max_c": m.temperature_service_max_c,
            "point_fusion_c": ser(m.point_fusion_c),
            "resistivite_ohm_m": ser(m.resistivite_ohm_m),
            "cout_matiere_eur_kg": ser(m.cout_matiere_eur_kg),
            "usinabilite_indice": ser(m.usinabilite_indice),
            "disponibilite_indice": ser(m.disponibilite_indice),
            "recyclabilite_indice": ser(m.recyclabilite_indice),
            "coefficient_frottement_sec": ser(m.coefficient_frottement_sec),
            "coefficient_frottement_lubr": ser(m.coefficient_frottement_lubr),
            "resistance_par_section": [ser(seg) for seg in m.resistance_par_section],
            "notes": m.notes,
        }

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def charger_json(path: Union[str, Path]) -> Dict[str, Materiau]:
    """
    Charge un JSON exporté par exporter_json() (ne remplace pas automatiquement MATERIAUX).
    """
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))

    def deser(v: object) -> object:
        if isinstance(v, dict) and "min" in v and "max" in v:
            return Intervalle(float(v["min"]), float(v["max"]))
        return v

    mats: Dict[str, Materiau] = {}
    for k, d in raw.items():
        segs = []
        for sd in d.get("resistance_par_section", []) or []:
            segs.append(SegmentResistanceSection(
                section_min_mm=float(sd["section_min_mm"]),
                section_max_mm=float(sd["section_max_mm"]),
                rp02_pa_min=sd.get("rp02_pa_min", None),
                rm_pa=deser(sd.get("rm_pa", None)),
                a_pct_min=sd.get("a_pct_min", None),
                kv_j_min=sd.get("kv_j_min", None),
            ))

        mats[k] = Materiau(
            cle=d["cle"],
            nom=d["nom"],
            famille=d["famille"],
            densite_kg_m3=d.get("densite_kg_m3", None),
            module_young_pa=deser(d.get("module_young_pa", None)),
            poisson=deser(d.get("poisson", None)),
            limite_elastique_pa=deser(d.get("limite_elastique_pa", None)),
            resistance_traction_pa=deser(d.get("resistance_traction_pa", None)),
            limite_fatigue_pa=deser(d.get("limite_fatigue_pa", None)),
            durete={hk: deser(hv) for hk, hv in (d.get("durete") or {}).items()},
            conductivite_thermique_w_mk=deser(d.get("conductivite_thermique_w_mk", None)),
            capacite_calorifique_j_kgk=deser(d.get("capacite_calorifique_j_kgk", None)),
            alpha_dilatation_1_k=deser(d.get("alpha_dilatation_1_k", None)),
            temperature_service_min_c=d.get("temperature_service_min_c", None),
            temperature_service_max_c=d.get("temperature_service_max_c", None),
            point_fusion_c=deser(d.get("point_fusion_c", None)),
            resistivite_ohm_m=deser(d.get("resistivite_ohm_m", None)),
            cout_matiere_eur_kg=deser(d.get("cout_matiere_eur_kg", None)),
            usinabilite_indice=deser(d.get("usinabilite_indice", None)),
            disponibilite_indice=deser(d.get("disponibilite_indice", None)),
            recyclabilite_indice=deser(d.get("recyclabilite_indice", None)),
            coefficient_frottement_sec=deser(d.get("coefficient_frottement_sec", None)),
            coefficient_frottement_lubr=deser(d.get("coefficient_frottement_lubr", None)),
            resistance_par_section=tuple(segs),
            notes=d.get("notes", ""),
        )
    return mats