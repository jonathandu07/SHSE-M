# backend/modules/batterie/electrolyte_solide.py
from __future__ import annotations

"""
Module complémentaire "électrolyte solide" (solid-state).
Objectif : calculer un maximum de paramètres DÉDUCTIBLES (sans valeurs implicites)
en s’appuyant sur tes modules batterie existants (pack électrique / énergie / charge).

Ce module ne “devine” rien :
- aucune constante cachée
- si une donnée manque -> elle est listée dans `inconnues` (ou exception si strict=True)

Principes physiques utilisés (généraux, valables électrolyte solide) :
- Résistance ionique de l’électrolyte : R = t / (k * A)
  où t = épaisseur (m), k = conductivité ionique (S/m), A = surface active (m²)
- Résistance surfacique (ASR) : ASR = t / k  (Ω·m²)
- Chute ohmique : ΔV = I * R
- Pertes Joule : P_pertes = I² * R
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import math

# --- import robuste de tes utilitaires pack électrique (courant, etc.) ---
# Compatible avec plusieurs arborescences :
# - backend.components.batterie.modules.*
# - backend.components.batterie.modules.*
# - fichiers posés dans le même dossier
try:  # arborescence initialement utilisée dans certains fichiers
    from backend.components.batterie.modules.calcul_electrique_pack import (
        calcul_courant_depuis_kw_tension,
    )
except Exception:  # fallback projet classique
    try:
        from backend.components.batterie.modules.calcul_electrique_pack import (
            calcul_courant_depuis_kw_tension,
        )
    except Exception:  # fallback local / tests unitaires
        from calcul_electrique_pack import calcul_courant_depuis_kw_tension

# =============================================================================
# Validation robuste
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))

def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)

def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v

def _req_ratio_0_1(name: str, x: Any) -> float:
    v = _req_finite(name, x)
    if v <= 0.0 or v > 1.0:
        raise ValueError(f"{name} doit être dans (0,1] (reçu: {v}).")
    return v

def _add_unknown(unk: List[str], key: str) -> None:
    if key not in unk:
        unk.append(key)

def _need(
    unk: List[str],
    key: str,
    val: Optional[float],
    *,
    validate,
    strict: bool,
) -> Optional[float]:
    if val is None:
        _add_unknown(unk, key)
        if strict:
            raise ValueError(f"Valeur manquante requise: {key}")
        return None
    return validate(key, val)

# =============================================================================
# Données d'entrée
# =============================================================================

@dataclass(frozen=True)
class ElectrolyteSolide:
    """
    Données matérielles / géométriques liées à l’électrolyte solide.
    Aucun défaut : None => inconnu.
    """
    conductivite_ionique_s_m: Optional[float] = None  # k (S/m)
    epaisseur_m: Optional[float] = None               # t (m)

    # Optionnel : si tu veux ajouter une résistance d’interface (contacts, joints, couches interfaciales)
    resistance_interface_ohm: Optional[float] = None  # R_int (Ω) équivalente par cellule

@dataclass(frozen=True)
class CelluleSolide:
    """
    Paramètres cellule nécessaires pour relier électrolyte -> résistance -> pertes.
    """
    surface_active_m2: Optional[float] = None         # A (m²), surface effective de transport ionique
    tension_nominale_v: Optional[float] = None        # V_cell (V)
    capacite_ah: Optional[float] = None               # Ah_cell (Ah)

    # Optionnel : limitation empirique ou issue d’un autre calcul
    courant_max_a: Optional[float] = None             # Imax_cell (A) si connu

@dataclass(frozen=True)
class PackSolide:
    """
    Paramètres pack pour calculer courants / puissances.
    """
    nb_series: Optional[int] = None                   # Ns
    nb_parallele: Optional[int] = None                # Np
    puissance_continue_kw: Optional[float] = None     # P_cont (kW)
    puissance_pic_kw: Optional[float] = None          # P_pic (kW)

    # Optionnel : rendement global d’électronique de puissance/liaisons (si tu veux passer de P mécanique -> P électrique)
    rendement_chaine: Optional[float] = None          # (0,1]

@dataclass(frozen=True)
class Options:
    strict: bool = False

# =============================================================================
# Résultats
# =============================================================================

@dataclass
class RapportElectrolyteSolide:
    # --- géométrie/transport ---
    resistance_electrolyte_ohm_par_cell: Optional[float] = None
    asr_ohm_m2: Optional[float] = None  # résistance surfacique (Ω·m²)
    resistance_totale_ohm_par_cell: Optional[float] = None  # électrolyte + interface

    # --- pack (tension, capacité) ---
    tension_pack_v: Optional[float] = None
    capacite_pack_ah: Optional[float] = None

    # --- courants demandés ---
    courant_pack_continu_a: Optional[float] = None
    courant_pack_pic_a: Optional[float] = None
    courant_cell_continu_a: Optional[float] = None
    courant_cell_pic_a: Optional[float] = None

    # --- chutes de tension / pertes ---
    chute_tension_cell_continu_v: Optional[float] = None
    chute_tension_cell_pic_v: Optional[float] = None
    pertes_joule_cell_continu_w: Optional[float] = None
    pertes_joule_cell_pic_w: Optional[float] = None

    pertes_joule_pack_continu_w: Optional[float] = None
    pertes_joule_pack_pic_w: Optional[float] = None

    # --- contraintes de courant (si limites connues) ---
    depassement_courant_max_continu: Optional[bool] = None
    depassement_courant_max_pic: Optional[bool] = None

    inconnues: Optional[List[str]] = None


# =============================================================================
# Calcul principal
# =============================================================================

def evaluer_electrolyte_solide(
    elec: ElectrolyteSolide,
    cell: CelluleSolide,
    pack: PackSolide,
    opts: Options = Options(),
) -> RapportElectrolyteSolide:
    """
    Calcule ce qui est calculable :
    - R électrolyte (cellule) via t, k, A
    - R totale (ajout interface optionnelle)
    - Vpack, Ah pack si Ns/Np + Vcell/Ah_cell
    - I pack demandé depuis P (via tes formules) et Vpack
    - I cellule (division par Np)
    - ΔV et pertes Joule au niveau cellule et pack

    IMPORTANT :
    - si rendement_chaine fourni, P électrique = P / eta (hypothèse explicite).
      Si absent, on considère que P_*_kw fournie est déjà la puissance électrique pack.
    """
    strict = bool(opts.strict)
    unk: List[str] = []

    # ---- paramètres électrolyte -> R ----
    k = _need(unk, "elec.conductivite_ionique_s_m", elec.conductivite_ionique_s_m, validate=_req_pos, strict=strict)
    t = _need(unk, "elec.epaisseur_m", elec.epaisseur_m, validate=_req_pos, strict=strict)
    A = _need(unk, "cell.surface_active_m2", cell.surface_active_m2, validate=_req_pos, strict=strict)

    R_elec = None
    ASR = None
    if k is not None and t is not None:
        ASR = t / k  # Ω·m²
        if A is not None:
            R_elec = ASR / A  # Ω

    R_int = elec.resistance_interface_ohm
    if R_int is not None:
        R_int = _req_pos("elec.resistance_interface_ohm", R_int, strict=False)  # peut être 0 si tu veux
    else:
        # pas “inconnu” obligatoire, c'est juste optionnel
        pass

    R_tot = None
    if R_elec is not None:
        R_tot = R_elec + (R_int if R_int is not None else 0.0)
    else:
        # si R_elec est inconnu, R_tot aussi
        if R_int is not None:
            _add_unknown(unk, "resistance_electrolyte_ohm_par_cell (pour resistance_totale)")
        else:
            _add_unknown(unk, "resistance_electrolyte_ohm_par_cell (pour resistance_totale)")

    # ---- pack tension/capacité ----
    Ns = pack.nb_series
    Np = pack.nb_parallele
    if Ns is not None:
        if not isinstance(Ns, int) or Ns <= 0:
            raise ValueError(f"pack.nb_series doit être un entier > 0 (reçu: {Ns!r}).")
    else:
        _add_unknown(unk, "pack.nb_series")

    if Np is not None:
        if not isinstance(Np, int) or Np <= 0:
            raise ValueError(f"pack.nb_parallele doit être un entier > 0 (reçu: {Np!r}).")
    else:
        _add_unknown(unk, "pack.nb_parallele")

    Vcell = _need(unk, "cell.tension_nominale_v", cell.tension_nominale_v, validate=_req_pos, strict=strict)
    Ah_cell = cell.capacite_ah
    if Ah_cell is not None:
        Ah_cell = _req_pos("cell.capacite_ah", Ah_cell, strict=False)
    else:
        _add_unknown(unk, "cell.capacite_ah")

    Vpack = None
    Ah_pack = None
    if Ns is not None and Vcell is not None:
        Vpack = float(Ns) * Vcell
    if Np is not None and Ah_cell is not None:
        Ah_pack = float(Np) * Ah_cell

    # ---- courants demandés depuis puissances ----
    eta = pack.rendement_chaine
    if eta is not None:
        eta = _req_ratio_0_1("pack.rendement_chaine", eta)

    def _puissance_electrique_kw(P_kw: Optional[float], label: str) -> Optional[float]:
        if P_kw is None:
            _add_unknown(unk, label)
            return None
        P = _req_pos(label, P_kw, strict=False)
        if eta is None:
            return P  # P déjà électrique pack
        if eta == 0:
            raise ValueError("pack.rendement_chaine ne peut pas être 0.")
        return P / eta  # hypothèse explicite : P_elec = P / eta

    P_cont_elec = _puissance_electrique_kw(pack.puissance_continue_kw, "pack.puissance_continue_kw")
    P_pic_elec = _puissance_electrique_kw(pack.puissance_pic_kw, "pack.puissance_pic_kw")

    I_pack_cont = None
    I_pack_pic = None
    if Vpack is None:
        if P_cont_elec is not None:
            _add_unknown(unk, "tension_pack_v (pour courant_pack_continu)")
        if P_pic_elec is not None:
            _add_unknown(unk, "tension_pack_v (pour courant_pack_pic)")
    else:
        if P_cont_elec is not None:
            I_pack_cont = float(calcul_courant_depuis_kw_tension(P_cont_elec, Vpack))
        if P_pic_elec is not None:
            I_pack_pic = float(calcul_courant_depuis_kw_tension(P_pic_elec, Vpack))

    # ---- courants cellule (division par Np) ----
    I_cell_cont = None
    I_cell_pic = None
    if Np is None:
        if I_pack_cont is not None:
            _add_unknown(unk, "pack.nb_parallele (pour courant_cell_continu)")
        if I_pack_pic is not None:
            _add_unknown(unk, "pack.nb_parallele (pour courant_cell_pic)")
    else:
        if I_pack_cont is not None:
            I_cell_cont = I_pack_cont / float(Np)
        if I_pack_pic is not None:
            I_cell_pic = I_pack_pic / float(Np)

    # ---- ΔV et pertes Joule (cellule + pack) ----
    dV_cont = None
    dV_pic = None
    Pj_cell_cont = None
    Pj_cell_pic = None
    Pj_pack_cont = None
    Pj_pack_pic = None

    if R_tot is None:
        if I_cell_cont is not None or I_cell_pic is not None:
            _add_unknown(unk, "resistance_totale_ohm_par_cell (pour chutes/pertes)")
    else:
        if I_cell_cont is not None:
            dV_cont = I_cell_cont * R_tot
            Pj_cell_cont = (I_cell_cont ** 2) * R_tot
        if I_cell_pic is not None:
            dV_pic = I_cell_pic * R_tot
            Pj_cell_pic = (I_cell_pic ** 2) * R_tot

        # pack = somme des cellules (Ns*Np) si pertes par cellule définies
        if Ns is not None and Np is not None:
            n_cells = float(Ns * Np)
            if Pj_cell_cont is not None:
                Pj_pack_cont = Pj_cell_cont * n_cells
            if Pj_cell_pic is not None:
                Pj_pack_pic = Pj_cell_pic * n_cells
        else:
            if Pj_cell_cont is not None:
                _add_unknown(unk, "pack.nb_series et pack.nb_parallele (pour pertes_joule_pack_continu_w)")
            if Pj_cell_pic is not None:
                _add_unknown(unk, "pack.nb_series et pack.nb_parallele (pour pertes_joule_pack_pic_w)")

    # ---- vérif limites de courant cellule (optionnel) ----
    dep_cont = None
    dep_pic = None
    if cell.courant_max_a is not None:
        Imax = _req_pos("cell.courant_max_a", cell.courant_max_a, strict=False)
        if I_cell_cont is not None:
            dep_cont = bool(I_cell_cont > Imax)
        if I_cell_pic is not None:
            dep_pic = bool(I_cell_pic > Imax)
    else:
        # ce n’est pas requis : c’est un contrôle optionnel
        pass

    return RapportElectrolyteSolide(
        resistance_electrolyte_ohm_par_cell=R_elec,
        asr_ohm_m2=ASR,
        resistance_totale_ohm_par_cell=R_tot,
        tension_pack_v=Vpack,
        capacite_pack_ah=Ah_pack,
        courant_pack_continu_a=I_pack_cont,
        courant_pack_pic_a=I_pack_pic,
        courant_cell_continu_a=I_cell_cont,
        courant_cell_pic_a=I_cell_pic,
        chute_tension_cell_continu_v=dV_cont,
        chute_tension_cell_pic_v=dV_pic,
        pertes_joule_cell_continu_w=Pj_cell_cont,
        pertes_joule_cell_pic_w=Pj_cell_pic,
        pertes_joule_pack_continu_w=Pj_pack_cont,
        pertes_joule_pack_pic_w=Pj_pack_pic,
        depassement_courant_max_continu=dep_cont,
        depassement_courant_max_pic=dep_pic,
        inconnues=unk,
    )


# =============================================================================
# Exemple minimal (à retirer en prod)
# =============================================================================
if __name__ == "__main__":
    elec = ElectrolyteSolide(
        conductivite_ionique_s_m=1.0,  # exemple
        epaisseur_m=50e-6,
        resistance_interface_ohm=0.0,
    )
    cell = CelluleSolide(
        surface_active_m2=0.01,
        tension_nominale_v=3.7,
        capacite_ah=5.0,
        courant_max_a=20.0,
    )
    pack = PackSolide(
        nb_series=108,
        nb_parallele=2,
        puissance_continue_kw=40,
        puissance_pic_kw=80,
        rendement_chaine=0.95,
    )
    rep = evaluer_electrolyte_solide(elec, cell, pack)
    print(asdict(rep))
