# backend\ensemble\calcul_stho_me.py
# -*- coding: utf-8 -*-
"""
calcul_stho_me.py
=========================================================
STHO-ME — Vivier central de calculs physiques
=========================================================

Principe :
- regrouper toutes les formules fondamentales
- aucune valeur inventée
- aucune hypothèse implicite
- chaque formule reste strictement traçable

Toutes les unités doivent être SI :
- m
- kg
- s
- Pa
- W
- J
- V
- A
- K
"""

from __future__ import annotations

import math


# ==========================================================
# OUTILS DE BASE
# ==========================================================

def verifier_positif(**kwargs):
    """
    Vérifie que toutes les valeurs sont strictement positives.
    """
    for nom, valeur in kwargs.items():
        if valeur <= 0:
            raise ValueError(f"{nom} doit être > 0 (valeur reçue : {valeur})")


# ==========================================================
# BLOC THERMIQUE
# ==========================================================

def flux_combustion(m_dot_f: float, pci: float) -> float:
    """
    Q_comb = m_dot_f * PCI
    """
    verifier_positif(m_dot_f=m_dot_f, pci=pci)
    return m_dot_f * pci


def flux_echappement(m_dot_gaz: float, cp: float, t_in: float, t_out: float, epsilon: float) -> float:
    """
    Q_ech = m_dot_gaz * cp * (T_in - T_out) * epsilon
    """
    verifier_positif(m_dot_gaz=m_dot_gaz, cp=cp, epsilon=epsilon)
    return m_dot_gaz * cp * (t_in - t_out) * epsilon


def flux_total(q_comb: float, q_ech: float, q_comp: float) -> float:
    """
    Q_total = combustion + échappement + composants
    """
    return q_comb + q_ech + q_comp


def rendement_carnot(th: float, tc: float) -> float:
    """
    eta = 1 - Tc / Th
    """
    verifier_positif(th=th, tc=tc)
    return 1 - (tc / th)


# ==========================================================
# BLOC GÉOMÉTRIE MOTEUR
# ==========================================================

def surface_piston(bore: float) -> float:
    """
    A = pi * B² / 4
    """
    verifier_positif(bore=bore)
    return math.pi * bore**2 / 4


def volume_balayage(bore: float, stroke: float) -> float:
    """
    Vb = A * S
    """
    verifier_positif(bore=bore, stroke=stroke)
    return surface_piston(bore) * stroke


def volume_total(vb: float, vm: float) -> float:
    """
    Vt = Vb + Vm
    """
    verifier_positif(vb=vb, vm=vm)
    return vb + vm


def rapport_volumetrique(vt: float, vm: float) -> float:
    """
    rv = Vt / Vm
    """
    verifier_positif(vt=vt, vm=vm)
    return vt / vm


# ==========================================================
# BLOC PRESSION
# ==========================================================

def force_pression(p: float, surface: float) -> float:
    """
    F = p * A
    """
    verifier_positif(p=p, surface=surface)
    return p * surface


def force_maximale(pmax: float, surface: float) -> float:
    """
    Fmax = pmax * A
    """
    verifier_positif(pmax=pmax, surface=surface)
    return pmax * surface


# ==========================================================
# CINÉMATIQUE
# ==========================================================

def frequence(n_rpm: float) -> float:
    """
    f = N / 60
    """
    verifier_positif(n_rpm=n_rpm)
    return n_rpm / 60


def pulsation(n_rpm: float) -> float:
    """
    omega = 2*pi*N/60
    """
    verifier_positif(n_rpm=n_rpm)
    return 2 * math.pi * n_rpm / 60


def vitesse_piston(stroke: float, n_rpm: float) -> float:
    """
    Up = 2*S*N/60
    """
    verifier_positif(stroke=stroke, n_rpm=n_rpm)
    return 2 * stroke * n_rpm / 60


def acceleration_piston(stroke: float, n_rpm: float) -> float:
    """
    a = omega² * r
    """
    r = stroke / 2
    return pulsation(n_rpm)**2 * r


def effort_inertiel(masse: float, acceleration: float) -> float:
    """
    Fi = m * a
    """
    verifier_positif(masse=masse)
    return masse * acceleration


# ==========================================================
# THERMO-MÉCANIQUE PISTON
# ==========================================================

def dilatation_lineaire(longueur_ref: float, alpha: float, delta_t: float) -> float:
    """
    dL = L0 * alpha * dT
    """
    verifier_positif(longueur_ref=longueur_ref, alpha=alpha)
    return longueur_ref * alpha * delta_t


def diametre_chaud(diametre_ref: float, alpha: float, delta_t: float) -> float:
    """
    D_hot = D_ref * (1 + alpha*dT)
    """
    verifier_positif(diametre_ref=diametre_ref, alpha=alpha)
    return diametre_ref * (1 + alpha * delta_t)


def jeu_fonctionnel_reel(
    diametre_cylindre_ref: float,
    alpha_cylindre: float,
    delta_t_cylindre: float,
    diametre_piston_ref: float,
    alpha_piston: float,
    delta_t_piston: float,
) -> float:
    """
    J = D_cyl_hot - D_piston_hot
    """
    verifier_positif(diametre_cylindre_ref=diametre_cylindre_ref, alpha_cylindre=alpha_cylindre, diametre_piston_ref=diametre_piston_ref, alpha_piston=alpha_piston)
    d_cyl_hot = diametre_chaud(diametre_cylindre_ref, alpha_cylindre, delta_t_cylindre)
    d_pis_hot = diametre_chaud(diametre_piston_ref, alpha_piston, delta_t_piston)
    return d_cyl_hot - d_pis_hot


def conicite_theorique(diametre_haut_hot: float, diametre_bas_hot: float) -> float:
    """
    C = D_haut_hot - D_bas_hot
    """
    verifier_positif(diametre_haut_hot=diametre_haut_hot, diametre_bas_hot=diametre_bas_hot)
    return diametre_haut_hot - diametre_bas_hot


def ovalisation_theorique(diametre_poussee_hot: float, diametre_contre_hot: float) -> float:
    """
    O = D_poussee_hot - D_contre_hot
    """
    verifier_positif(diametre_poussee_hot=diametre_poussee_hot, diametre_contre_hot=diametre_contre_hot)
    return diametre_poussee_hot - diametre_contre_hot


def angle_bielle(rayon_manivelle: float, longueur_bielle: float, theta_rad: float) -> float:
    """
    beta = asin((r/l) * sin(theta))
    """
    verifier_positif(rayon_manivelle=rayon_manivelle, longueur_bielle=longueur_bielle)
    arg = (rayon_manivelle / longueur_bielle) * math.sin(theta_rad)
    arg = max(-1.0, min(1.0, arg))
    return math.asin(arg)


def force_laterale_piston(force_axiale: float, rayon_manivelle: float, longueur_bielle: float, theta_rad: float) -> float:
    """
    Fl = Fax * tan(beta)
    """
    verifier_positif(rayon_manivelle=rayon_manivelle, longueur_bielle=longueur_bielle)
    beta = angle_bielle(rayon_manivelle, longueur_bielle, theta_rad)
    return force_axiale * math.tan(beta)


def pression_jupe(force_laterale: float, aire_contact: float) -> float:
    """
    p = F / A
    """
    verifier_positif(aire_contact=aire_contact)
    return force_laterale / aire_contact


def gradient_thermique(delta_t: float, epaisseur: float) -> float:
    """
    gradT = dT / e
    """
    verifier_positif(epaisseur=epaisseur)
    return delta_t / epaisseur


def contrainte_thermique_bloquee(e_module: float, alpha: float, delta_t: float, poisson: float, facteur_contrainte: float = 1.0) -> float:
    """
    sigma_th = k * E * alpha * dT / (1 - nu)
    """
    verifier_positif(e_module=e_module, alpha=alpha)
    if poisson == 1.0:
        raise ValueError("poisson ne doit pas être égal à 1")
    return facteur_contrainte * e_module * alpha * delta_t / (1 - poisson)


def contrainte_tete_piston_plaque(k_sigma: float, pression: float, alesage: float, epaisseur: float) -> float:
    """
    sigma = k * p * (a² / t²) avec a = alesage/2
    """
    verifier_positif(k_sigma=k_sigma, pression=pression, alesage=alesage, epaisseur=epaisseur)
    a = alesage / 2
    return k_sigma * pression * (a**2 / epaisseur**2)


# ==========================================================
# TRAVAIL THERMODYNAMIQUE
# ==========================================================

def travail_indique(pme: float, vb: float) -> float:
    """
    Wi = pme * Vb
    """
    verifier_positif(pme=pme, vb=vb)
    return pme * vb


def puissance_indiquee(pme: float, vb: float, n_rpm: float, n_cyl: int = 1) -> float:
    """
    Pi = Ncyl * pme * Vb * N/60
    """
    verifier_positif(pme=pme, vb=vb, n_rpm=n_rpm)
    return n_cyl * pme * vb * n_rpm / 60


def puissance_arbre(pi: float, eta_m: float) -> float:
    """
    Pshaft = eta_m * Pi
    """
    verifier_positif(pi=pi, eta_m=eta_m)
    return eta_m * pi


def couple_moteur(pshaft: float, omega: float) -> float:
    """
    T = P / omega
    """
    verifier_positif(pshaft=pshaft, omega=omega)
    return pshaft / omega


# ==========================================================
# ARBRE / TORSION
# ==========================================================

def contrainte_torsion(couple: float, diametre: float) -> float:
    """
    tau = 16T / pi d³
    """
    verifier_positif(couple=couple, diametre=diametre)
    return 16 * couple / (math.pi * diametre**3)


def diametre_arbre_torsion(couple: float, tau_adm: float) -> float:
    """
    d = (16T / pi tau)^1/3
    """
    verifier_positif(couple=couple, tau_adm=tau_adm)
    return (16 * couple / (math.pi * tau_adm))**(1/3)


# ==========================================================
# FLEXION
# ==========================================================

def contrainte_flexion(moment: float, diametre: float) -> float:
    """
    sigma = 32M / pi d³
    """
    verifier_positif(moment=moment, diametre=diametre)
    return 32 * moment / (math.pi * diametre**3)


def von_mises(sigma: float, tau: float) -> float:
    """
    sigma_vm = sqrt(sigma² + 3 tau²)
    """
    return math.sqrt(sigma**2 + 3 * tau**2)


# ==========================================================
# BATTERIE
# ==========================================================

def nb_cellules_serie(u_bus: float, u_cell: float) -> float:
    """
    Ns = Ubus / Ucell
    """
    verifier_positif(u_bus=u_bus, u_cell=u_cell)
    return u_bus / u_cell


def nb_cellules_parallele(c_pack: float, c_cell: float) -> float:
    """
    Np = Cpack / Ccell
    """
    verifier_positif(c_pack=c_pack, c_cell=c_cell)
    return c_pack / c_cell


def energie_pack(u_pack: float, c_pack: float) -> float:
    """
    E = U * C
    """
    verifier_positif(u_pack=u_pack, c_pack=c_pack)
    return u_pack * c_pack


def courant_pack(p: float, u: float) -> float:
    """
    I = P / U
    """
    verifier_positif(p=p, u=u)
    return p / u


def pertes_joule(r: float, i: float) -> float:
    """
    PJ = R * I²
    """
    if r < 0: raise ValueError(f"R doit être >= 0 (reçu: {r})")
    return r * i**2


def pertes_joule_interne(i_a: float, r_interne_ohm: float) -> float:
    """
    PJ = R_interne * I^2
    """
    if r_interne_ohm < 0: raise ValueError(f"R_interne doit être >= 0 (reçu: {r_interne_ohm})")
    return pertes_joule(r_interne_ohm, i_a)


def calculer_c_rate(i_charge_a: float, capacite_ah: float) -> float:
    """
    C = I / Cap
    """
    if capacite_ah <= 0: raise ValueError(f"Capacité doit être > 0 (reçu: {capacite_ah})")
    return i_charge_a / capacite_ah


def facteur_usure_arrhenius(t_k: float, ea_j_mol: float, r_gaz_j_mol_k: float) -> float:
    """
    k = exp(-Ea / (R * T))
    Formule brute d'activation thermique.
    """
    verifier_positif(t_k=t_k, ea_j_mol=ea_j_mol, r_gaz_j_mol_k=r_gaz_j_mol_k)
    return math.exp(-ea_j_mol / (r_gaz_j_mol_k * t_k))


def facteur_usure_relatif(t_k: float, t_ref_k: float, ea_j_mol: float, r_gaz_j_mol_k: float) -> float:
    """
    k_rel = exp( (Ea/R) * (1/T_ref - 1/T) )
    Accélération de la dégradation par rapport à une température de référence.
    """
    verifier_positif(t_k=t_k, t_ref_k=t_ref_k, ea_j_mol=ea_j_mol, r_gaz_j_mol_k=r_gaz_j_mol_k)
    return math.exp((ea_j_mol / r_gaz_j_mol_k) * (1 / t_ref_k - 1 / t_k))


def facteur_vieillissement_arrhenius(
    *,
    t_k: float,
    ea_j_mol: float,
    r_gaz_j_mol_k: float,
    t_ref_k: float | None = None,
) -> float:
    """
    Renvoie soit le facteur brut de type Arrhenius, soit un facteur relatif
    si une température de référence explicite est fournie.
    """
    if t_ref_k is None:
        return facteur_usure_arrhenius(t_k=t_k, ea_j_mol=ea_j_mol, r_gaz_j_mol_k=r_gaz_j_mol_k)
    return facteur_usure_relatif(
        t_k=t_k,
        t_ref_k=t_ref_k,
        ea_j_mol=ea_j_mol,
        r_gaz_j_mol_k=r_gaz_j_mol_k,
    )


# ==========================================================
# ALTERNATEUR
# ==========================================================

def puissance_mecanique_requise(p_utile: float, eta_gen: float, eta_conv: float, eta_charge: float) -> float:
    """
    Pmec = Putile / (eta_gen * eta_conv * eta_charge)
    """
    verifier_positif(p_utile=p_utile, eta_gen=eta_gen, eta_conv=eta_conv, eta_charge=eta_charge)
    return p_utile / (eta_gen * eta_conv * eta_charge)


def couple_alternateur(p_mec: float, n_alt: float) -> float:
    """
    Talt = P / omega
    """
    omega = pulsation(n_alt)
    return p_mec / omega


# ==========================================================
# REFROIDISSEMENT
# ==========================================================

def surface_echange(q: float, h: float, delta_t: float) -> float:
    """
    A = Q / (h * deltaT)
    """
    verifier_positif(q=q, h=h, delta_t=delta_t)
    return q / (h * delta_t)


def constante_temps_thermique(r_th_k_w: float, c_th_j_k: float) -> float:
    """
    tau = Rth * Cth
    """
    verifier_positif(r_th_k_w=r_th_k_w, c_th_j_k=c_th_j_k)
    return r_th_k_w * c_th_j_k


def reponse_transitoire_premier_ordre(val_init: float, val_cible: float, t_s: float, tau_s: float) -> float:
    """
    y(t) = val_init + (val_cible - val_init) * (1 - exp(-t / tau))
    """
    verifier_positif(tau_s=tau_s)
    if t_s < 0:
        raise ValueError(f"Le temps t_s doit être positif (reçu: {t_s}).")
    return val_init + (val_cible - val_init) * (1 - math.exp(-t_s / tau_s))


# ==========================================================
# ARCHITECTURE HYBRIDE
# ==========================================================

def puissance_instantanee(p_traction: float, p_recharge: float, beta: float) -> float:
    """
    Pinst = (Ptraction + Precharge) / beta
    """
    verifier_positif(p_traction=p_traction, p_recharge=p_recharge, beta=beta)
    return (p_traction + p_recharge) / beta
