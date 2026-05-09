# backend/ensemble/carburant.py
# Données & calculs "Carburant" pour moteurs à combustion interne
#
# Objectif :
# - Centraliser les propriétés physico-chimiques des carburants (SI).
# - Fournir les constantes de combustion (PCI, AFR_st, etc.).
# - Supporter les carburants liquides (essence, diesel, alcools) et gazeux (CH4, H2, NH3).
# - Permettre la gestion de mélanges (ex: E85) et l'analyse du "pire cas" multi-carburant.

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union, Any, Iterable
import math

# =============================================================================
# Constantes et Conversions
# =============================================================================
O2_MASS_FRACTION_AIR = 0.232  # Fraction massique d'O2 dans l'air standard (approx)
N2_O2_MOLAR_RATIO = 3.76      # Rapport molaire N2/O2 dans l'air
MJ_KG_TO_J_KG = 1e6

# =============================================================================
# Classe Carburant
# =============================================================================

@dataclass(frozen=True)
class Carburant:
    """
    Représente un carburant pur ou un mélange stabilisé.
    Toutes les unités sont en SI (kg, m, J, K, Pa) sauf mention contraire.
    """
    cle: str
    nom: str
    formule_chimique: str
    etat_standard: str  # "liquide" | "gaz"
    
    # Propriétés physiques
    densite_kg_m3: float  # à 15°C / 1 atm (liquide) ou STP (gaz)
    masse_molaire_kg_mol: float
    
    # Propriétés énergétiques
    pci_mj_kg: float  # Lower Heating Value (MJ/kg)
    
    # Combustion
    afr_stoechiometrique: float  # Air/Fuel Ratio massique (stoechiométrique)
    
    # Champs optionnels avec défauts
    pcs_mj_kg: Optional[float] = None  # Higher Heating Value (MJ/kg)
    
    # Performance moteur
    indice_octane_ron: Optional[float] = None
    indice_cetane: Optional[float] = None
    temperature_auto_inflammation_c: Optional[float] = None
    vitesse_flamme_laminaire_ms: Optional[float] = None
    
    # Composition élémentaire (massique 0..1)
    fraction_carbone: float = 0.0
    fraction_hydrogene: float = 0.0
    fraction_oxygene: float = 0.0
    fraction_azote: float = 0.0
    
    notes: str = ""

    def __post_init__(self):
        # Vérification sommaire de la cohérence de la fraction massique si renseignée
        somme = self.fraction_carbone + self.fraction_hydrogene + self.fraction_oxygene + self.fraction_azote
        if somme > 0 and abs(somme - 1.0) > 0.05:
             # On ne lève pas d'erreur car certaines impuretés peuvent exister, 
             # mais on pourrait logger un avertissement.
             pass

    @property
    def pci_j_kg(self) -> float:
        return self.pci_mj_kg * MJ_KG_TO_J_KG

    @property
    def pcs_j_kg(self) -> Optional[float]:
        return self.pcs_mj_kg * MJ_KG_TO_J_KG if self.pcs_mj_kg is not None else None

    @property
    def rapport_air_carburant_stoech_massique(self) -> float:
        return self.afr_stoechiometrique

    def pci_volumique_mj_m3(self) -> float:
        """Energie par unité de volume de carburant pur."""
        return self.pci_mj_kg * self.densite_kg_m3

    def energie_melange_stoechio_mj_kg(self) -> float:
        """
        Energie libérée par kg de mélange AIR + CARBURANT à la stoechiométrie.
        C'est un indicateur clé de la puissance spécifique potentielle.
        """
        return self.pci_mj_kg / (1.0 + self.afr_stoechiometrique)

    def densite_energie_melange_mj_m3(self, densite_air_kg_m3: float = 1.225) -> float:
        """
        Densité d'énergie du mélange gazeux (air+vapeur/gaz fuel) à l'admission.
        Utile pour comparer le remplissage cylindre.
        """
        # Masse de mélange pour 1kg de fuel = (1 + AFR)
        # Volume de ce mélange = Vol_air + Vol_fuel
        # Approx simple : le volume est dominé par l'air (sauf pour H2)
        masse_air = self.afr_stoechiometrique
        vol_air = masse_air / densite_air_kg_m3
        return self.pci_mj_kg / vol_air

    def resume(self) -> Dict[str, Any]:
        return {
            "cle": self.cle,
            "nom": self.nom,
            "etat": self.etat_standard,
            "pci_mj_kg": self.pci_mj_kg,
            "afr_st": self.afr_stoechiometrique,
            "energie_melange_mj_kg": self.energie_melange_stoechio_mj_kg(),
            "indice_octane": self.indice_octane_ron,
            "densite_kg_m3": self.densite_kg_m3
        }

# =============================================================================
# Bibliothèque de Carburants
# =============================================================================

CARBURANTS: Dict[str, Carburant] = {}

def _reg(c: Carburant) -> Carburant:
    CARBURANTS[c.cle] = c
    return c

# --- ESSENCE (Gasoline) ---
_reg(Carburant(
    cle="essence",
    nom="Essence Sans Plomb (95/98)",
    formule_chimique="C8H18 (approx)",
    etat_standard="liquide",
    densite_kg_m3=745.0,
    masse_molaire_kg_mol=0.114,
    pci_mj_kg=44.0,
    afr_stoechiometrique=14.7,
    indice_octane_ron=95.0,
    temperature_auto_inflammation_c=280.0,
    fraction_carbone=0.84,
    fraction_hydrogene=0.16,
    notes="Valeurs moyennes pour l'Europe (EN 228)."
))

# --- DIESEL ---
_reg(Carburant(
    cle="diesel",
    nom="Gazole / Diesel",
    formule_chimique="C12H23 (approx)",
    etat_standard="liquide",
    densite_kg_m3=835.0,
    masse_molaire_kg_mol=0.170,
    pci_mj_kg=42.5,
    afr_stoechiometrique=14.5,
    indice_cetane=51.0,
    temperature_auto_inflammation_c=210.0,
    fraction_carbone=0.86,
    fraction_hydrogene=0.14,
    notes="Valeurs standards (EN 590)."
))

# --- ETHANOL ---
_reg(Carburant(
    cle="ethanol",
    nom="Éthanol Pur (E100)",
    formule_chimique="C2H5OH",
    etat_standard="liquide",
    densite_kg_m3=789.0,
    masse_molaire_kg_mol=0.04607,
    pci_mj_kg=26.8,
    afr_stoechiometrique=9.0,
    indice_octane_ron=108.0,
    temperature_auto_inflammation_c=365.0,
    vitesse_flamme_laminaire_ms=0.40,
    fraction_carbone=0.522,
    fraction_hydrogene=0.131,
    fraction_oxygene=0.347,
    notes="Bioéthanol pur."
))

# --- METHANOL ---
_reg(Carburant(
    cle="methanol",
    nom="Méthanol",
    formule_chimique="CH3OH",
    etat_standard="liquide",
    densite_kg_m3=792.0,
    masse_molaire_kg_mol=0.03204,
    pci_mj_kg=19.9,
    afr_stoechiometrique=6.47,
    indice_octane_ron=109.0,
    temperature_auto_inflammation_c=460.0,
    fraction_carbone=0.375,
    fraction_hydrogene=0.126,
    fraction_oxygene=0.499,
    notes="Utilisé en compétition et marine."
))

# --- METHANE (GNC/GNL) ---
_reg(Carburant(
    cle="methane",
    nom="Méthane / Gaz Naturel",
    formule_chimique="CH4",
    etat_standard="gaz",
    densite_kg_m3=0.68,  # à 15°C, 1 atm
    masse_molaire_kg_mol=0.01604,
    pci_mj_kg=50.0,
    afr_stoechiometrique=17.2,
    indice_octane_ron=120.0,
    temperature_auto_inflammation_c=540.0,
    fraction_carbone=0.75,
    fraction_hydrogene=0.25,
    notes="Composant principal du GNV."
))

# --- HYDROGENE ---
_reg(Carburant(
    cle="hydrogene",
    nom="Hydrogène",
    formule_chimique="H2",
    etat_standard="gaz",
    densite_kg_m3=0.089,  # à STP
    masse_molaire_kg_mol=0.002016,
    pci_mj_kg=120.0,
    afr_stoechiometrique=34.3,
    indice_octane_ron=130.0,
    temperature_auto_inflammation_c=585.0,
    vitesse_flamme_laminaire_ms=2.8,
    fraction_hydrogene=1.0,
    notes="Pouvoir calorifique massique extrême, mais très peu dense."
))

# --- AMMONIAC ---
_reg(Carburant(
    cle="ammoniac",
    nom="Ammoniac (NH3)",
    formule_chimique="NH3",
    etat_standard="gaz",
    densite_kg_m3=0.73,  # gaz @ 15°C
    masse_molaire_kg_mol=0.01703,
    pci_mj_kg=18.6,
    afr_stoechiometrique=6.05,
    indice_octane_ron=120.0,
    temperature_auto_inflammation_c=650.0,
    vitesse_flamme_laminaire_ms=0.07,
    fraction_hydrogene=0.177,
    fraction_azote=0.823,
    notes="Vecteur d'hydrogène décarboné, combustion lente."
))

# =============================================================================
# Logique de Mélange et Optimisation
# =============================================================================

def creer_melange(composants: Dict[str, float], nom: str = "Melange Personnalise") -> Carburant:
    """
    Crée un Carburant virtuel à partir d'un mélange de carburants existants.
    composants: Dict { cle_carburant: fraction_massique }
    """
    if abs(sum(composants.values()) - 1.0) > 1e-6:
        raise ValueError("La somme des fractions massiques doit être égale à 1.0")

    pci = 0.0
    afr = 0.0
    densite = 0.0
    m_mol = 0.0
    fc = 0.0
    fh = 0.0
    fo = 0.0
    fn = 0.0
    etat = "liquide"
    
    for cle, frac in composants.items():
        c = get_carburant(cle)
        pci += c.pci_mj_kg * frac
        afr += c.afr_stoechiometrique * frac
        densite += c.densite_kg_m3 * frac # Approximation linéaire massique
        m_mol += c.masse_molaire_kg_mol * frac
        fc += c.fraction_carbone * frac
        fh += c.fraction_hydrogene * frac
        fo += c.fraction_oxygene * frac
        fn += c.fraction_azote * frac
        if c.etat_standard == "gaz":
            etat = "gaz"

    return Carburant(
        cle=f"melange_{nom.lower().replace(' ', '_')}",
        nom=nom,
        formule_chimique="Mixed",
        etat_standard=etat,
        densite_kg_m3=densite,
        masse_molaire_kg_mol=m_mol,
        pci_mj_kg=pci,
        afr_stoechiometrique=afr,
        fraction_carbone=fc,
        fraction_hydrogene=fh,
        fraction_oxygene=fo,
        fraction_azote=fn,
        notes=f"Mélange calculé : {composants}"
    )

def get_carburant(cle: str) -> Carburant:
    if cle not in CARBURANTS:
        raise KeyError(f"Carburant inconnu : {cle}. Disponibles : {list(CARBURANTS.keys())}")
    return CARBURANTS[cle]

def get_pire_carburant(cles: Optional[Iterable[str]] = None, objectif: str = "puissance") -> Carburant:
    """
    Renvoie le carburant le plus 'pénalisant' parmi une liste pour un objectif donné.
    Si cles est None, utilise toute la bibliothèque.
    
    Objectifs :
    - 'puissance' : celui avec la plus faible énergie par kg de mélange (énergie_melange_stoechio_mj_kg).
    - 'autonomie' : celui avec le plus faible PCI volumique.
    - 'cliquetis' : celui avec le plus faible indice d'octane.
    - 'froid' : celui avec la plus haute température d'auto-inflammation (plus dur à démarrer).
    """
    targets = [CARBURANTS[k] for k in cles] if cles else list(CARBURANTS.values())
    
    if objectif == "puissance":
        # On veut minimiser l'énergie du mélange
        return min(targets, key=lambda c: c.energie_melange_stoechio_mj_kg())
    elif objectif == "autonomie":
        return min(targets, key=lambda c: c.pci_volumique_mj_m3())
    elif objectif == "cliquetis":
        # On filtre ceux qui ont un indice d'octane défini
        with_octane = [c for c in targets if c.indice_octane_ron is not None]
        if not with_octane: return targets[0]
        return min(with_octane, key=lambda c: c.indice_octane_ron)
    elif objectif == "froid":
        with_temp = [c for c in targets if c.temperature_auto_inflammation_c is not None]
        if not with_temp: return targets[0]
        return max(with_temp, key=lambda c: c.temperature_auto_inflammation_c)
    
    return targets[0]

def lister_carburants() -> List[Dict[str, Any]]:
    return [c.resume() for c in CARBURANTS.values()]

__all__ = [
    "Carburant",
    "CARBURANTS",
    "get_carburant",
    "creer_melange",
    "get_pire_carburant",
    "lister_carburants"
]
