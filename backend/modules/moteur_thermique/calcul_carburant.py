# backend/modules/moteur_thermique/calcul_carburant.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

Number = Union[int, float]

# ============================================================
# Import robuste depuis le module air déjà existant
# ============================================================

try:
    from backend.ensemble.air import oxygen_mass_fraction_in_dry_air
except Exception:
    try:
        from air import oxygen_mass_fraction_in_dry_air  # type: ignore
    except Exception:
        def oxygen_mass_fraction_in_dry_air(co2_ppm: float = 420.0) -> float:
            """
            Fallback minimal si le module air n'est pas disponible.
            Valeur typique de la fraction massique d'O2 dans l'air sec.
            """
            return 0.2329


# ============================================================
# Constantes molaires utiles
# ============================================================

M_C = 0.012011       # kg/mol
M_H = 0.001008       # kg/mol
M_O = 0.015999       # kg/mol
M_N = 0.014007       # kg/mol
M_S = 0.032065       # kg/mol

M_O2 = 0.0319988     # kg/mol
M_CO2 = 0.0440095    # kg/mol
M_H2O = 0.01801528   # kg/mol
M_SO2 = 0.064066     # kg/mol


# ============================================================
# Validation / robustesse
# ============================================================

def _is_finite_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite_number(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_nonneg(name: str, x: Any) -> float:
    v = _req_finite(name, x)
    if v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    if strict:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


# ============================================================
# Composition élémentaire du combustible
# ============================================================

@dataclass(frozen=True)
class CompositionElementaireCombustible:
    """
    Composition élémentaire molaire simplifiée du combustible :
      C_x H_y O_z S_s N_n

    Exemple méthane CH4 :
      carbone_mol=1, hydrogene_mol=4

    Exemple éthanol C2H6O :
      carbone_mol=2, hydrogene_mol=6, oxygene_mol=1
    """
    carbone_mol: float
    hydrogene_mol: float
    oxygene_mol: float = 0.0
    soufre_mol: float = 0.0
    azote_mol: float = 0.0

    def __post_init__(self) -> None:
        c = _req_nonneg("carbone_mol", self.carbone_mol)
        h = _req_nonneg("hydrogene_mol", self.hydrogene_mol)
        o = _req_nonneg("oxygene_mol", self.oxygene_mol)
        s = _req_nonneg("soufre_mol", self.soufre_mol)
        n = _req_nonneg("azote_mol", self.azote_mol)

        if c <= 0.0 and h <= 0.0 and s <= 0.0:
            raise ValueError("Le combustible doit contenir au moins du C, H ou S.")

        object.__setattr__(self, "carbone_mol", c)
        object.__setattr__(self, "hydrogene_mol", h)
        object.__setattr__(self, "oxygene_mol", o)
        object.__setattr__(self, "soufre_mol", s)
        object.__setattr__(self, "azote_mol", n)

    @property
    def masse_molaire_kg_mol(self) -> float:
        return (
            self.carbone_mol * M_C
            + self.hydrogene_mol * M_H
            + self.oxygene_mol * M_O
            + self.soufre_mol * M_S
            + self.azote_mol * M_N
        )

    @property
    def besoin_o2_stoech_mol_par_mol(self) -> float:
        """
        Besoin stœchiométrique en O2 pour combustion complète :
          ν_O2 = x + y/4 + s - z/2
        pour C_x H_y O_z S_s N_n
        """
        nu = (
            self.carbone_mol
            + 0.25 * self.hydrogene_mol
            + self.soufre_mol
            - 0.5 * self.oxygene_mol
        )
        if nu < -1e-12:
            raise ValueError(
                "La composition donne un besoin théorique en O2 négatif ; "
                "vérifie la formule élémentaire."
            )
        return max(0.0, nu)


# ============================================================
# Définition explicite d'un carburant
# ============================================================

@dataclass(frozen=True)
class Carburant:
    """
    Carburant pour calculs de pré-dimensionnement.

    Principe :
    - aucune donnée n'est inventée ;
    - soit tu fournis la composition pour déduire la stœchiométrie,
    - soit tu fournis directement les rapports stœchiométriques massiques.
    """
    nom: str
    pci_j_kg: float
    densite_kg_m3: Optional[float] = None
    pcs_j_kg: Optional[float] = None

    composition: Optional[CompositionElementaireCombustible] = None

    rapport_air_carburant_stoech_massique: Optional[float] = None
    rapport_oxygene_carburant_stoech_massique: Optional[float] = None

    temperature_eclair_c: Optional[float] = None
    temperature_auto_inflammation_c: Optional[float] = None
    temperature_min_service_c: Optional[float] = None
    temperature_max_service_c: Optional[float] = None

    commentaire: str = ""

    def __post_init__(self) -> None:
        _req_pos("pci_j_kg", self.pci_j_kg, strict=True)

        if self.densite_kg_m3 is not None:
            _req_pos("densite_kg_m3", self.densite_kg_m3, strict=True)

        if self.pcs_j_kg is not None:
            pcs = _req_pos("pcs_j_kg", self.pcs_j_kg, strict=True)
            if pcs < self.pci_j_kg:
                raise ValueError("pcs_j_kg doit être >= pci_j_kg.")

        if self.rapport_air_carburant_stoech_massique is not None:
            _req_pos(
                "rapport_air_carburant_stoech_massique",
                self.rapport_air_carburant_stoech_massique,
                strict=True,
            )

        if self.rapport_oxygene_carburant_stoech_massique is not None:
            _req_pos(
                "rapport_oxygene_carburant_stoech_massique",
                self.rapport_oxygene_carburant_stoech_massique,
                strict=True,
            )

    def rapport_oxygene_stoech_massique(self) -> float:
        if self.rapport_oxygene_carburant_stoech_massique is not None:
            return float(self.rapport_oxygene_carburant_stoech_massique)

        if self.composition is None:
            raise ValueError(
                "rapport_oxygene_carburant_stoech_massique inconnu : "
                "fournis soit la composition, soit le rapport explicite."
            )

        return calcul_rapport_oxygene_carburant_stoechiometrique_massique(self.composition)

    def rapport_air_stoech_massique(self, *, co2_ppm_air: float = 420.0) -> float:
        if self.rapport_air_carburant_stoech_massique is not None:
            return float(self.rapport_air_carburant_stoech_massique)

        return calcul_rapport_air_carburant_stoechiometrique_massique(
            self.composition,
            co2_ppm_air=co2_ppm_air,
        )

    def densite_energetique_volumique_j_m3(self) -> float:
        if self.densite_kg_m3 is None:
            raise ValueError("densite_kg_m3 inconnue.")
        return self.pci_j_kg * self.densite_kg_m3


# ============================================================
# Énergie / débits carburant
# ============================================================

def calcul_puissance_chimique_combustion(
    debit_massique_carburant_kg_s: Number,
    pci_j_kg: Number,
) -> float:
    """
    Q_comb = m_dot_f * PCI
    """
    mdot = _req_nonneg("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s)
    pci = _req_pos("pci_j_kg", pci_j_kg, strict=True)
    return mdot * pci


def calcul_puissance_thermique_utile_combustion(
    debit_massique_carburant_kg_s: Number,
    pci_j_kg: Number,
    rendement_combustion: Number,
) -> float:
    """
    Flux utile si une partie seulement de la puissance chimique
    est effectivement transmise / exploitée.
    """
    qchim = calcul_puissance_chimique_combustion(
        debit_massique_carburant_kg_s=debit_massique_carburant_kg_s,
        pci_j_kg=pci_j_kg,
    )
    eta = _req_pos("rendement_combustion", rendement_combustion, strict=True)
    if eta > 1.0:
        raise ValueError("rendement_combustion doit être <= 1.")
    return qchim * eta


def calcul_debit_massique_carburant_depuis_puissance_chimique(
    puissance_chimique_w: Number,
    pci_j_kg: Number,
) -> float:
    qchim = _req_nonneg("puissance_chimique_w", puissance_chimique_w)
    pci = _req_pos("pci_j_kg", pci_j_kg, strict=True)
    return qchim / pci


def calcul_debit_massique_carburant_depuis_puissance_utile(
    puissance_utile_w: Number,
    pci_j_kg: Number,
    rendement_global: Number,
) -> float:
    """
    m_dot_f = P_utile / (eta_global * PCI)
    """
    p = _req_nonneg("puissance_utile_w", puissance_utile_w)
    pci = _req_pos("pci_j_kg", pci_j_kg, strict=True)
    eta = _req_pos("rendement_global", rendement_global, strict=True)
    if eta > 1.0:
        raise ValueError("rendement_global doit être <= 1.")
    return p / (eta * pci)


def calcul_debit_volumique_carburant(
    debit_massique_carburant_kg_s: Number,
    densite_kg_m3: Number,
) -> float:
    mdot = _req_nonneg("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s)
    rho = _req_pos("densite_kg_m3", densite_kg_m3, strict=True)
    return mdot / rho


def calcul_masse_depuis_volume_carburant(
    volume_m3: Number,
    densite_kg_m3: Number,
) -> float:
    V = _req_nonneg("volume_m3", volume_m3)
    rho = _req_pos("densite_kg_m3", densite_kg_m3, strict=True)
    return V * rho


def calcul_volume_depuis_masse_carburant(
    masse_kg: Number,
    densite_kg_m3: Number,
) -> float:
    m = _req_nonneg("masse_kg", masse_kg)
    rho = _req_pos("densite_kg_m3", densite_kg_m3, strict=True)
    return m / rho


def calcul_energie_chimique_depuis_masse(
    masse_carburant_kg: Number,
    pci_j_kg: Number,
) -> float:
    m = _req_nonneg("masse_carburant_kg", masse_carburant_kg)
    pci = _req_pos("pci_j_kg", pci_j_kg, strict=True)
    return m * pci


def calcul_energie_chimique_depuis_volume(
    volume_carburant_m3: Number,
    pci_j_kg: Number,
    densite_kg_m3: Number,
) -> float:
    m = calcul_masse_depuis_volume_carburant(volume_carburant_m3, densite_kg_m3)
    return calcul_energie_chimique_depuis_masse(m, pci_j_kg)


# ============================================================
# Stœchiométrie
# ============================================================

def calcul_besoin_o2_stoechiometrique_mol_par_mol_combustible(
    composition: CompositionElementaireCombustible,
) -> float:
    if not isinstance(composition, CompositionElementaireCombustible):
        raise ValueError("composition doit être une CompositionElementaireCombustible.")
    return composition.besoin_o2_stoech_mol_par_mol


def calcul_rapport_oxygene_carburant_stoechiometrique_massique(
    composition: CompositionElementaireCombustible,
) -> float:
    """
    OFR_st = m_O2 / m_fuel
    """
    nu_o2 = calcul_besoin_o2_stoechiometrique_mol_par_mol_combustible(composition)
    m_o2 = nu_o2 * M_O2
    m_f = composition.masse_molaire_kg_mol

    if m_f <= 0.0:
        raise ValueError("masse molaire combustible invalide.")

    return m_o2 / m_f


def calcul_rapport_air_carburant_stoechiometrique_massique(
    composition: Optional[CompositionElementaireCombustible],
    *,
    co2_ppm_air: Number = 420.0,
    fraction_massique_o2_air: Optional[Number] = None,
) -> float:
    """
    AFR_st = OFR_st / y_O2_air

    Si fraction_massique_o2_air est fournie, elle est utilisée directement.
    Sinon, elle est récupérée depuis le module air.
    """
    if composition is None:
        raise ValueError("composition inconnue : impossible de déduire AFR_stoech.")

    if fraction_massique_o2_air is None:
        y_o2 = float(oxygen_mass_fraction_in_dry_air(co2_ppm=float(co2_ppm_air)))
    else:
        y_o2 = _req_pos("fraction_massique_o2_air", fraction_massique_o2_air, strict=True)

    if y_o2 <= 0.0 or y_o2 >= 1.0:
        raise ValueError("fraction_massique_o2_air doit être dans ]0,1[.")

    ofr = calcul_rapport_oxygene_carburant_stoechiometrique_massique(composition)
    return ofr / y_o2


def calcul_debit_massique_air_stoechiometrique(
    debit_massique_carburant_kg_s: Number,
    rapport_air_carburant_stoech_massique: Number,
) -> float:
    mdot_f = _req_nonneg("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s)
    afr = _req_pos(
        "rapport_air_carburant_stoech_massique",
        rapport_air_carburant_stoech_massique,
        strict=True,
    )
    return mdot_f * afr


def calcul_debit_massique_air_reel(
    debit_massique_carburant_kg_s: Number,
    rapport_air_carburant_stoech_massique: Number,
    lambda_exces_air: Number,
) -> float:
    mdot_air_st = calcul_debit_massique_air_stoechiometrique(
        debit_massique_carburant_kg_s=debit_massique_carburant_kg_s,
        rapport_air_carburant_stoech_massique=rapport_air_carburant_stoech_massique,
    )
    lamb = _req_pos("lambda_exces_air", lambda_exces_air, strict=True)
    return lamb * mdot_air_st


def calcul_lambda_depuis_debits_massiques(
    debit_massique_air_reel_kg_s: Number,
    debit_massique_carburant_kg_s: Number,
    rapport_air_carburant_stoech_massique: Number,
) -> float:
    mdot_air = _req_nonneg("debit_massique_air_reel_kg_s", debit_massique_air_reel_kg_s)
    mdot_f = _req_pos("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s, strict=True)
    afr_st = _req_pos(
        "rapport_air_carburant_stoech_massique",
        rapport_air_carburant_stoech_massique,
        strict=True,
    )
    return mdot_air / (mdot_f * afr_st)


def calcul_phi_depuis_lambda(lambda_exces_air: Number) -> float:
    lamb = _req_pos("lambda_exces_air", lambda_exces_air, strict=True)
    return 1.0 / lamb


# ============================================================
# Produits / échappement (niveau pré-dimensionnement)
# ============================================================

def calcul_debit_massique_gaz_echappement(
    debit_massique_air_kg_s: Number,
    debit_massique_carburant_kg_s: Number,
) -> float:
    """
    Approximation de premier niveau :
      m_dot_gaz ≈ m_dot_air + m_dot_fuel
    """
    mdot_air = _req_nonneg("debit_massique_air_kg_s", debit_massique_air_kg_s)
    mdot_f = _req_nonneg("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s)
    return mdot_air + mdot_f


def calcul_debit_massique_co2_theorique(
    debit_massique_carburant_kg_s: Number,
    composition: CompositionElementaireCombustible,
) -> float:
    """
    Débit théorique de CO2 si combustion complète.
    """
    mdot_f = _req_nonneg("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s)
    M_f = composition.masse_molaire_kg_mol

    if M_f <= 0.0:
        raise ValueError("masse molaire combustible invalide.")

    n_f = mdot_f / M_f
    return n_f * composition.carbone_mol * M_CO2


def calcul_debit_massique_h2o_theorique(
    debit_massique_carburant_kg_s: Number,
    composition: CompositionElementaireCombustible,
) -> float:
    """
    Débit théorique d'eau formée si combustion complète.
    """
    mdot_f = _req_nonneg("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s)
    M_f = composition.masse_molaire_kg_mol

    if M_f <= 0.0:
        raise ValueError("masse molaire combustible invalide.")

    n_f = mdot_f / M_f
    return n_f * (0.5 * composition.hydrogene_mol) * M_H2O


def calcul_flux_thermique_echappement_recuperable(
    debit_massique_gaz_kg_s: Number,
    cp_gaz_j_kg_k: Number,
    temperature_gaz_in_k: Number,
    temperature_gaz_out_k: Number,
    efficacite_echangeur: Number = 1.0,
) -> float:
    """
    Q = m_dot * cp * (T_in - T_out) * epsilon
    """
    mdot = _req_nonneg("debit_massique_gaz_kg_s", debit_massique_gaz_kg_s)
    cp = _req_pos("cp_gaz_j_kg_k", cp_gaz_j_kg_k, strict=True)
    Tin = _req_pos("temperature_gaz_in_k", temperature_gaz_in_k, strict=True)
    Tout = _req_pos("temperature_gaz_out_k", temperature_gaz_out_k, strict=True)
    eps = _req_pos("efficacite_echangeur", efficacite_echangeur, strict=True)

    if eps > 1.0:
        raise ValueError("efficacite_echangeur doit être <= 1.")
    if Tin < Tout:
        raise ValueError("temperature_gaz_in_k doit être >= temperature_gaz_out_k.")

    return mdot * cp * (Tin - Tout) * eps


def calcul_flux_thermique_total_utile(
    flux_combustion_w: Number,
    flux_echappement_recupere_w: Number = 0.0,
    flux_composants_recupere_w: Number = 0.0,
) -> float:
    q_comb = _req_nonneg("flux_combustion_w", flux_combustion_w)
    q_ech = _req_nonneg("flux_echappement_recupere_w", flux_echappement_recupere_w)
    q_comp = _req_nonneg("flux_composants_recupere_w", flux_composants_recupere_w)
    return q_comb + q_ech + q_comp


# ============================================================
# Bilan synthétique
# ============================================================

def calcul_bilan_carburant_simple(
    carburant: Carburant,
    debit_massique_carburant_kg_s: Number,
    *,
    lambda_exces_air: Number = 1.0,
    co2_ppm_air: Number = 420.0,
    cp_gaz_j_kg_k: Optional[Number] = None,
    temperature_gaz_in_k: Optional[Number] = None,
    temperature_gaz_out_k: Optional[Number] = None,
    efficacite_echangeur: Number = 1.0,
) -> Dict[str, float]:
    """
    Rapport synthétique de premier niveau.

    Ce bilan reste un pré-dimensionnement :
    - combustion complète supposée pour CO2/H2O théoriques ;
    - pas de cinétique réelle ;
    - pas de NOx/CO/imbrûlés ;
    - gaz d'échappement estimés par bilan massique simple.
    """
    mdot_f = _req_nonneg("debit_massique_carburant_kg_s", debit_massique_carburant_kg_s)
    lamb = _req_pos("lambda_exces_air", lambda_exces_air, strict=True)

    afr_st = carburant.rapport_air_stoech_massique(co2_ppm_air=float(co2_ppm_air))
    mdot_air_st = calcul_debit_massique_air_stoechiometrique(mdot_f, afr_st)
    mdot_air = calcul_debit_massique_air_reel(mdot_f, afr_st, lamb)
    mdot_gaz = calcul_debit_massique_gaz_echappement(mdot_air, mdot_f)

    out: Dict[str, float] = {
        "debit_massique_carburant_kg_s": mdot_f,
        "pci_j_kg": carburant.pci_j_kg,
        "puissance_chimique_w": calcul_puissance_chimique_combustion(mdot_f, carburant.pci_j_kg),
        "rapport_air_carburant_stoech_massique": afr_st,
        "lambda_exces_air": lamb,
        "phi_equivalence": calcul_phi_depuis_lambda(lamb),
        "debit_massique_air_stoech_kg_s": mdot_air_st,
        "debit_massique_air_reel_kg_s": mdot_air,
        "debit_massique_gaz_echappement_kg_s": mdot_gaz,
    }

    if carburant.densite_kg_m3 is not None:
        out["debit_volumique_carburant_m3_s"] = calcul_debit_volumique_carburant(
            mdot_f,
            carburant.densite_kg_m3,
        )
        out["densite_energetique_volumique_j_m3"] = carburant.densite_energetique_volumique_j_m3()

    if carburant.composition is not None:
        out["rapport_oxygene_carburant_stoech_massique"] = carburant.rapport_oxygene_stoech_massique()
        out["debit_massique_co2_theorique_kg_s"] = calcul_debit_massique_co2_theorique(
            mdot_f,
            carburant.composition,
        )
        out["debit_massique_h2o_theorique_kg_s"] = calcul_debit_massique_h2o_theorique(
            mdot_f,
            carburant.composition,
        )

    if (
        cp_gaz_j_kg_k is not None
        and temperature_gaz_in_k is not None
        and temperature_gaz_out_k is not None
    ):
        out["flux_thermique_echappement_recuperable_w"] = calcul_flux_thermique_echappement_recuperable(
            debit_massique_gaz_kg_s=mdot_gaz,
            cp_gaz_j_kg_k=cp_gaz_j_kg_k,
            temperature_gaz_in_k=temperature_gaz_in_k,
            temperature_gaz_out_k=temperature_gaz_out_k,
            efficacite_echangeur=efficacite_echangeur,
        )

    return out


__all__ = [
    "CompositionElementaireCombustible",
    "Carburant",
    "calcul_puissance_chimique_combustion",
    "calcul_puissance_thermique_utile_combustion",
    "calcul_debit_massique_carburant_depuis_puissance_chimique",
    "calcul_debit_massique_carburant_depuis_puissance_utile",
    "calcul_debit_volumique_carburant",
    "calcul_masse_depuis_volume_carburant",
    "calcul_volume_depuis_masse_carburant",
    "calcul_energie_chimique_depuis_masse",
    "calcul_energie_chimique_depuis_volume",
    "calcul_besoin_o2_stoechiometrique_mol_par_mol_combustible",
    "calcul_rapport_oxygene_carburant_stoechiometrique_massique",
    "calcul_rapport_air_carburant_stoechiometrique_massique",
    "calcul_debit_massique_air_stoechiometrique",
    "calcul_debit_massique_air_reel",
    "calcul_lambda_depuis_debits_massiques",
    "calcul_phi_depuis_lambda",
    "calcul_debit_massique_gaz_echappement",
    "calcul_debit_massique_co2_theorique",
    "calcul_debit_massique_h2o_theorique",
    "calcul_flux_thermique_echappement_recuperable",
    "calcul_flux_thermique_total_utile",
    "calcul_bilan_carburant_simple",
]