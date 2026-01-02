def calcul_rendement_alternateur(puissance_utile_out: float, somme_pertes: float = 0, liste_pertes: list[float] = None) -> float:
    """
    Calcule le rendement de l'alternateur.

    Formule : eta = P_out / (P_out + Pertes)

    Args:
        puissance_utile_out (float): Puissance électrique de sortie utile (W).
        somme_pertes (float): Somme des pertes (cuivre, fer, méca...) en Watts. Optionnel si liste_pertes fournie.
        liste_pertes (list[float]): Liste des différentes pertes individuelles (W). Si fournie, somme_pertes est ignoré.

    Returns:
        float: Rendement (entre 0 et 1).
    """
    loss_total = somme_pertes
    if liste_pertes:
        loss_total = sum(liste_pertes)
        
    puissance_input = puissance_utile_out + loss_total
    
    if puissance_input == 0:
        return 0.0
        
    return puissance_utile_out / puissance_input
