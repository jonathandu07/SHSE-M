def evaluer_architecture(type_arch: str, nb_cylindres: int, longueur_dispo_m: float, largeur_dispo_m: float) -> tuple[float, bool]:
    """
    Évalue une architecture (L, V, W) selon l'encombrement et la complexité.
    
    Retourne (Score_Cout, Est_Valide).
    """
    # Paramètres géométriques approximatifs
    pas_cylindre = 0.15 # 150mm
    largeur_base = 0.4
    
    L_pkg = 0.0
    W_pkg = 0.0
    complexite = 1.0 # Base
    
    if type_arch == "L": # En Ligne
        L_pkg = nb_cylindres * pas_cylindre
        W_pkg = largeur_base
        complexite = 1.0
        
    elif type_arch == "V": # En V
        L_pkg = (nb_cylindres / 2) * pas_cylindre
        W_pkg = largeur_base * 1.5
        complexite = 1.3
        
    elif type_arch == "W": # En W (3 bancs)
        L_pkg = (nb_cylindres / 3) * pas_cylindre
        W_pkg = largeur_base * 2.0
        complexite = 1.8
        
    elif type_arch == "Etoile": # Radial
        L_pkg = pas_cylindre * 1.5 # Court
        W_pkg = largeur_base * 2.5 # Large
        complexite = 2.0
    
    else:
        return 9999.0, False

    # Vérification Contraintes
    valide = (L_pkg <= longueur_dispo_m) and (W_pkg <= largeur_dispo_m)
    
    # Fonction Coût Simplifiée J = w1*L + w2*W + w5*Complex
    score = (1.0 * (L_pkg/longueur_dispo_m)) + (1.0 * (W_pkg/largeur_dispo_m)) + (0.5 * complexite)
    
    if not valide:
        score += 1000.0 # Pénalité
        
    return score, valide

def choix_architecture_optimale(nb_cylindres: int, L_max: float, W_max: float) -> str:
    """
    Sélectionne la meilleure architecture pour un nombre de cylindres donné.
    """
    options = ["L", "V", "W", "Etoile"]
    if nb_cylindres % 2 != 0: options.remove("V")
    if nb_cylindres % 3 != 0 and nb_cylindres % 4 != 0: 
        if "W" in options: 
             if nb_cylindres < 3: options.remove("W") # W needs min 3
    
    best_arch = "Inconnue"
    best_score = 99999.0
    
    for arch in options:
        score, valide = evaluer_architecture(arch, nb_cylindres, L_max, W_max)
        if valide and score < best_score:
            best_score = score
            best_arch = arch
            
    return best_arch
