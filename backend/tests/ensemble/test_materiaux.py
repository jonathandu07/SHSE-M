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
#   https://www.clintonaluminum.com/wp-content/uploads/2014/08/Grade-6061-T6-T651-Text-Data1.pdf
# - Al 7075 : Gabrian "7075 Aluminum Alloy: Properties" (PDF)
#   https://www.gabrian.com/wp-content/uploads/2018/09/7075-Aluminum-Alloy-Properties.pdf
# - 42CrMo4 : Lucefin "42CrMo4 1.7225 – 42CrMoS4 1.7227" (PDF)
#   https://www.lucefin.com/wp-content/files_mf/152353604042CrMo4.pdf
# - 100Cr6 : Lucefin "100Cr6 1.3505" (PDF)
#   (URL variable selon Lucefin; utiliser la source projet si vous l’avez déjà téléchargée)
# - EN-GJL-250 : NORELEM fiche "Cast iron EN-GJL-250" (PDF)
#   https://www.norelem.com/fileadmin/Download/EN/Product_overview_materials/13_Material_overview_Cast_iron_EN-GJL-250_EN.pdf
# - Inox 304 : AZoM "Stainless Steel - Grade 304 (UNS S30400)" (page)
#   https://www.azom.com/article.aspx?ArticleID=965
# - CuSn12 : MakeItFrom "CuSn12 / CW453K" (page)
#   https://www.makeitfrom.com/material-properties/CuSn12-CW453K-Phosphor-Bronze
# - ABS : Xometry "Data Sheet: ABS" (PDF)
#   https://xometry.asia/wp-content/uploads/2021/09/ABS.pdf
# - PTFE : DuPont "Teflon™ PTFE Properties Handbook" (PDF)
#   https://www.crp.co.uk/wp-content/uploads/2020/06/Teflon_PTFE_Properties_Handbook.pdf

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Union
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
    rp02_pa_min: Optional[float] = None  # Limite d'élasticité (0.2%) minimale (Pa)
    rm_pa: Optional[Valeur] = None       # Résistance traction (Pa) (intervalle fréquent)
    a_pct_min: Optional[float] = None    # Allongement min (%)
    kv_j_min: Optional[float] = None     # Résilience Charpy (J), si dispo

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
    limite_elastique_pa: Optional[Valeur] = None    # Rp0.2 / Re (selon fiche)
    resistance_traction_pa: Optional[Valeur] = None # Rm
    limite_fatigue_pa: Optional[Valeur] = None      # si dispo (souvent défini pour un critère précis)

    # Dureté (valeurs typiques / intervalles)
    durete: Dict[str, Valeur] = field(default_factory=dict)  # ex: {"HBW": 95, "HRC": Intervalle(...), "ShoreD": 55}

    # Thermique
    conductivite_thermique_w_mk: Optional[Valeur] = None
    capacite_calorifique_j_kgk: Optional[Valeur] = None
    alpha_dilatation_1_k: Optional[Valeur] = None
    temperature_service_min_c: Optional[float] = None
    temperature_service_max_c: Optional[float] = None
    point_fusion_c: Optional[Valeur] = None

    # Électrique (optionnel)
    resistivite_ohm_m: Optional[Valeur] = None

    # Courbes / tables optionnelles
    resistance_par_section: Tuple[SegmentResistanceSection, ...] = tuple()

    # Notes / sources (humain)
    notes: str = ""

    # -------------------------
    # Propriétés dérivées RDM
    # -------------------------
    def module_cisaillement_pa(self, mode: str = "typique") -> Optional[float]:
        """
        G = E / (2*(1+nu)) (isotrope).
        Si E ou nu absent -> None.
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

    def limite_elastique_effective_pa(
        self,
        mode: str = "min",
        section_mm: Optional[float] = None,
    ) -> Optional[float]:
        """
        Renvoie Rp0.2 (ou Re) en Pa.
        - Si une courbe 'resistance_par_section' existe et section_mm est fourni,
          on privilégie le segment correspondant.
        - Sinon on utilise 'limite_elastique_pa'.
        """
        if section_mm is not None and self.resistance_par_section:
            for seg in self.resistance_par_section:
                if seg.contient(section_mm) and seg.rp02_pa_min is not None:
                    return seg.rp02_pa_min  # déjà "min" (conservateur)
        return valeur(self.limite_elastique_pa, mode=mode)

    def resistance_traction_effective_pa(
        self,
        mode: str = "min",
        section_mm: Optional[float] = None,
    ) -> Optional[float]:
        """
        Renvoie Rm en Pa (souvent intervalle).
        - Si courbe + section_mm: renvoie min/max/typique selon mode.
        - Sinon utilise 'resistance_traction_pa'.
        """
        if section_mm is not None and self.resistance_par_section:
            for seg in self.resistance_par_section:
                if seg.contient(section_mm) and seg.rm_pa is not None:
                    return valeur(seg.rm_pa, mode=mode)
        return valeur(self.resistance_traction_pa, mode=mode)

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
        """
        if coef_securite <= 0:
            raise ValueError("coef_securite doit être > 0")

        if critere == "elasticite":
            base = self.limite_elastique_effective_pa(mode="min", section_mm=section_mm)
        elif critere == "rupture":
            base = self.resistance_traction_effective_pa(mode="min", section_mm=section_mm)
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
    # Source (Clinton Aluminum PDF) :
    # - densité 2.70 g/cc
    # - Rm 310 MPa, Rp0.2 276 MPa
    # - E 68.9 GPa, ν 0.33 (estimé), G 26.0 GPa (estimé)
    # - fatigue 96.5 MPa @ 5e8 cycles (RR Moore, reversed)
    # - k 167 W/mK, cp 0.896 J/gK, alpha 23.6e-6 /K (20-100°C)
    densite_kg_m3=2700.0,
    module_young_pa=68.9 * GPA,
    poisson=0.330,
    limite_elastique_pa=276.0 * MPA,
    resistance_traction_pa=310.0 * MPA,
    limite_fatigue_pa=96.5 * MPA,  # attention: condition de fatigue spécifique (voir fiche)
    durete={"HBW": 95.0},
    conductivite_thermique_w_mk=167.0,
    capacite_calorifique_j_kgk=0.896 * 1000.0,  # J/gK -> J/kgK
    alpha_dilatation_1_k=23.6e-6,
    point_fusion_c=Intervalle(582.0, 651.7),
    # résistivité 0.00000399 ohm-cm -> 3.99e-8 ohm-m
    resistivite_ohm_m=3.99e-8,
    notes="Source principale: Clinton Aluminum Grade 6061-T6/T651 (PDF).",
))

# -------------------------
# Aluminium 7075-T6 / T651
# -------------------------
_register(Materiau(
    cle="alu_7075_t6",
    nom="Aluminium 7075-T6 / 7075-T651",
    famille="metal",
    # Source (Gabrian PDF) :
    # - densité 2.81 g/cc
    # - Rm 572 MPa, Rp0.2 503 MPa
    # - E 71.7 GPa
    # - alpha 23.4e-6 /K (20-100°C)
    # - cp 0.960 J/gK (ligne thermique)
    # Remarque: la ligne “conductivité thermique” est ambiguë dans l’extraction texte de certaines colonnes,
    # donc on ne fixe pas k ici (à renseigner si vous avez une fiche plus explicite pour l’état T6).
    densite_kg_m3=2810.0,
    module_young_pa=71.7 * GPA,
    limite_elastique_pa=503.0 * MPA,
    resistance_traction_pa=572.0 * MPA,
    alpha_dilatation_1_k=23.4e-6,
    capacite_calorifique_j_kgk=0.960 * 1000.0,  # J/gK -> J/kgK
    notes="Source principale: Gabrian 7075 Aluminum Alloy Properties (PDF).",
))

# -------------------------
# Acier allié 42CrMo4 (1.7225)
# -------------------------
_register(Materiau(
    cle="acier_42crmo4_qt",
    nom="Acier 42CrMo4 (1.7225) — état trempé + revenu (QT)",
    famille="metal",
    # Source (Lucefin 42CrMo4 PDF) :
    # - Propriétés mécaniques QT dépendantes de la taille (diamètre/épaisseur).
    # Source complémentaire pour E/nu/densité peut être Ovako Steel Navigator (selon disponibilité dans votre projet).
    densite_kg_m3=7800.0,        # valeur courante pour acier; à remplacer par fiche constructeur si besoin
    module_young_pa=210.0 * GPA, # valeur courante acier; idéalement: fiche fabricant (Ovako/SwissSteel/etc.)
    poisson=0.30,                # valeur courante acier
    conductivite_thermique_w_mk=Intervalle(40.0, 46.0),  # ordre de grandeur; à verrouiller si vous avez une fiche (évite d'inventer un point unique)
    capacite_calorifique_j_kgk=Intervalle(460.0, 480.0),
    alpha_dilatation_1_k=12.0e-6,
    # Courbe QT+SH (hot-rolled quenched and tempered + peeled) (Lucefin) :
    # - 16-40 mm : Rm 1000-1200 MPa ; Rp0.2 >= 750 MPa ; A >= 11% ; Kv2 >= 35 J
    # - 40-63 mm : Rm 900-1100 MPa  ; Rp0.2 >= 650 MPa ; A >= 12% ; Kv2 >= 35 J
    # - 63-100mm : idem 40-63
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
    densite_kg_m3=7810.0,      # Lucefin 100Cr6 (table propriétés physiques)
    module_young_pa=210.0 * GPA,
    poisson=0.30,
    conductivite_thermique_w_mk=46.6,   # Lucefin (extraction)
    capacite_calorifique_j_kgk=475.0,   # Lucefin (extraction)
    alpha_dilatation_1_k=12.0e-6,       # ordre de grandeur acier; à verrouiller si votre fiche 100Cr6 la donne explicitement
    # Propriétés mécaniques: fortement dépendantes du traitement thermique.
    # La table de revenu Lucefin donne R et Rp0.2 en fonction de la température de revenu.
    # Ici on ne fixe pas un seul couple (Rm/Rp0.2), car ce serait “inventer” un état unique.
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
    # Source (NORELEM PDF EN-GJL-250) :
    densite_kg_m3=7200.0,
    module_young_pa=Intervalle(103.0 * GPA, 118.0 * GPA),
    # Rp0.1 (pas Rp0.2) : 165-228 MPa, on le stocke comme "limite_elastique" (avec note)
    limite_elastique_pa=Intervalle(165.0 * MPA, 228.0 * MPA),
    resistance_traction_pa=Intervalle(250.0 * MPA, 350.0 * MPA),
    durete={"HBW": Intervalle(190.0, 230.0)},
    # Thermique: souvent variable selon grade/structure; à ajouter si vous avez votre fiche interne.
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
    # Source (AZoM):
    densite_kg_m3=8000.0,
    module_young_pa=193.0 * GPA,
    poisson=0.29,
    limite_elastique_pa=215.0 * MPA,
    resistance_traction_pa=505.0 * MPA,
    conductivite_thermique_w_mk=16.2,
    capacite_calorifique_j_kgk=500.0,
    alpha_dilatation_1_k=17.2e-6,
    point_fusion_c=Intervalle(1400.0, 1450.0),
    notes="Source: AZoM (Grade 304). Valeurs typiques (dépendent de l’état/écrouissage).",
))

# -------------------------
# Bronze CuSn12 (phosphore)
# -------------------------
_register(Materiau(
    cle="bronze_cusn12",
    nom="Bronze CuSn12 (CW453K) — bronze phosphoreux",
    famille="metal",
    # Source (MakeItFrom CuSn12):
    densite_kg_m3=8.69 * 1000.0,  # g/cm³ -> kg/m³
    module_young_pa=110.0 * GPA,
    poisson=0.34,
    limite_elastique_pa=170.0 * MPA,
    resistance_traction_pa=310.0 * MPA,
    conductivite_thermique_w_mk=54.4,
    capacite_calorifique_j_kgk=376.0,
    alpha_dilatation_1_k=18.0e-6,
    notes="Source: MakeItFrom CuSn12/CW453K. Peut varier selon état (écroui/recuit).",
))

# -------------------------
# ABS (thermoplastique)
# -------------------------
_register(Materiau(
    cle="abs",
    nom="ABS (Acrylonitrile Butadiene Styrene)",
    famille="polymere",
    # Source (Xometry ABS.pdf):
    densite_kg_m3=1.06 * 1000.0,
    module_young_pa=Intervalle(2.0 * GPA, 2.6 * GPA),
    resistance_traction_pa=Intervalle(42.5 * MPA, 44.8 * MPA),
    conductivite_thermique_w_mk=0.1,
    capacite_calorifique_j_kgk=900.0,
    alpha_dilatation_1_k=120e-6,
    temperature_service_max_c=89.0,  # heat deflection ~ 88-89°C (Xometry)
    notes="Source: Xometry ABS datasheet. Les polymères varient beaucoup selon grade/process.",
))

# -------------------------
# PTFE (Teflon)
# -------------------------
_register(Materiau(
    cle="ptfe",
    nom="PTFE (Polytetrafluoroethylene, Teflon™)",
    famille="polymere",
    # Source (DuPont PTFE Properties Handbook):
    # - k ≈ 0.25 W/mK
    # - Shore D typique ~55 (50-65)
    # - coefficient dilatation linéaire ~1e-4 /K (ordre de grandeur)
    # Pour densité / E / résistance traction, les fiches varient fortement selon grade (vierge, chargé, etc.).
    densite_kg_m3=2200.0,  # valeur usuelle PTFE vierge (à verrouiller via votre grade exact)
    module_young_pa=Intervalle(0.4 * GPA, 0.6 * GPA),  # ordre de grandeur courant PTFE vierge (grade-dépendant)
    resistance_traction_pa=Intervalle(15.0 * MPA, 30.0 * MPA),  # plage typique, grade-dépendant
    conductivite_thermique_w_mk=0.25,
    alpha_dilatation_1_k=1.0e-4,
    durete={"ShoreD": Intervalle(50.0, 65.0)},
    temperature_service_min_c=-200.0,
    temperature_service_max_c=260.0,
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


# =========================
# Import/Export JSON (optionnel)
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
            resistance_par_section=tuple(segs),
            notes=d.get("notes", ""),
        )
    return mats
