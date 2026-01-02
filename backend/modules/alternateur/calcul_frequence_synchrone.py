def calcul_frequence_synchrone(vitesse_rotation_tr_min: float, nombre_poles: int) -> float:
    """
    Calcule la fréquence électrique synchrone.

    Formule : f = (n * P) / 120

    Args:
        vitesse_rotation_tr_min (float): Vitesse de rotation (n) en tours par minute (tr/min).
        nombre_poles (int): Nombre de pôles magnétiques (P), doit être un nombre pair.

    Returns:
        float: Fréquence en Hertz (Hz).
    """
    if nombre_poles <= 0 or nombre_poles % 2 != 0:
        raise ValueError("Le nombre de pôles doit être un entier pair positif.")
    if vitesse_rotation_tr_min < 0:
         raise ValueError("La vitesse de rotation ne peut pas être négative.")

    return (vitesse_rotation_tr_min * nombre_poles) / 120
