"""
Template radar universel pour les pièces mécaniques SHSE-M.
Ce module génère un graphique radar basé sur les métriques disponibles dans l'objet pièce.
"""
import math
import numpy as np


def _safe_float(obj, *keys):
    """Tente de récupérer un float depuis un objet ou dict, via une liste de clés candidates."""
    for k in keys:
        try:
            v = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
            if v is not None:
                return float(v)
        except Exception:
            pass
    return None


def _norm(val, vmin, vmax):
    """Normalise une valeur entre 0 et 1."""
    if vmin == vmax:
        return 0.5
    return max(0.0, min(1.0, (val - vmin) / (vmax - vmin)))


def plot_data(ax, piece):
    """
    Trace un radar chart avec les métriques physiques disponibles dans `piece`.
    `piece` est un objet ou dict retourné par la BDD.
    """
    # On tente d'extraire les métriques clés communes à toutes les pièces
    metrics = {}

    # Masse
    m = _safe_float(piece, "masse_kg", "masse_estimee_kg", "masse")
    if m is not None and m > 0:
        metrics["Masse\n(kg)"] = _norm(m, 0.1, 50.0)

    # Volume / géométrie caractéristique
    d = _safe_float(piece, "diametre_m", "diametre_primitif_m", "alesage_m", "diametre_arbre_m")
    if d is not None and d > 0:
        metrics["Diam.\n(mm)"] = _norm(d * 1000, 10, 200)

    # Contrainte admissible
    sigma = _safe_float(piece, "contrainte_admissible_pa", "contrainte_max_pa", "pression_max_pa")
    if sigma is not None and sigma > 0:
        metrics["Résist.\n(MPa)"] = _norm(sigma / 1e6, 50, 500)

    # Facteur de sécurité
    fs = _safe_float(piece, "facteur_securite", "facteur_securite_estime", "facteur_securite_cylindre")
    if fs is not None:
        metrics["Sécu."] = _norm(fs, 1.0, 4.0)

    # Coût matière
    c = _safe_float(piece, "cout_matiere_estime_eur", "cout_matiere_eur_kg")
    if c is not None and c > 0:
        metrics["Coût\n(€)"] = 1.0 - _norm(c, 0, 500)  # inversé: moins cher = mieux

    # Longueur / course
    l = _safe_float(piece, "longueur_m", "longueur_bielle_m", "course_m", "hauteur_totale_m")
    if l is not None and l > 0:
        metrics["Long.\n(mm)"] = _norm(l * 1000, 5, 500)

    # Si on n'a rien, on met des valeurs fictives avec un avertissement
    if not metrics:
        metrics = {
            "Masse": 0.5,
            "Résist.": 0.6,
            "Sécu.": 0.7,
            "Coût": 0.5,
            "Géom.": 0.4,
        }
        ax.set_title("Données insuffisantes\n(valeurs indicatives)", fontsize=8, color="gray")

    labels = list(metrics.keys())
    values = list(metrics.values())
    N = len(labels)

    # Angles du radar
    angles = [n / float(N) * 2 * math.pi for n in range(N)]
    angles += angles[:1]  # fermeture du polygone
    values += values[:1]

    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=6, color="gray")

    ax.plot(angles, values, linewidth=2, linestyle="solid", color="#091226")
    ax.fill(angles, values, alpha=0.25, color="#3E5349")

    # Nom de la pièce
    nom = getattr(piece, "nom", None) or (piece.get("nom") if isinstance(piece, dict) else None) or "Pièce"
    if not ax.get_title():
        ax.set_title(str(nom).replace("_", " ").title(), fontsize=10, fontweight="bold", pad=15, color="#091226")
