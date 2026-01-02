def calcul_couple_transmissible_crabot(nombre_dents: int, pression_admissible: float, hauteur_dent: float, largeur_dent: float, rayon_moyen: float) -> float:
    """
    Calcule le couple maximum transmissible par un crabot avant plastification/écrasement.

    Formule : T_cap = N_d * p_adm * h * b_d * r_m
    (Aire de contact A_d = h * b_d)

    Args:
        nombre_dents (int): Nombre de dents du crabot (N_d).
        pression_admissible (float): Pression de contact admissible (Pa).
        hauteur_dent (float): Hauteur utile de contact (h) en m.
        largeur_dent (float): Largeur de la dent (b_d) en m.
        rayon_moyen (float): Rayon moyen d'implantation des dents (r_m) en m.

    Returns:
        float: Couple capacitaire (N.m).
    """
    aire_contact = hauteur_dent * largeur_dent
    return nombre_dents * pression_admissible * aire_contact * rayon_moyen

def calcul_pression_contact_crabot(couple_nm: float, nombre_dents: int, hauteur_dent: float, largeur_dent: float, rayon_moyen: float) -> float:
    """
    Vérifie la pression de contact réelle sur les dents du crabot.

    Formule : p = F / A_d avec F = T / (N_d * r_m)
    """
    if nombre_dents <= 0 or rayon_moyen <= 0:
        raise ValueError("Paramètres géométriques invalides.")
        
    force_par_dent = couple_nm / (nombre_dents * rayon_moyen)
    aire_contact = hauteur_dent * largeur_dent
    
    if aire_contact <= 0:
        raise ValueError("Aire de contact nulle.")
        
    return force_par_dent / aire_contact
