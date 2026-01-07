import json
import os
import re

def get_latest_system_analysis(log_path):
    """
    Extrait le dernier bloc JSON valide de test_systeme_complet.log
    """
    if not os.path.exists(log_path):
        return None
        
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # On cherche les blocs JSON entre les marqueurs ou via regex
    # Dans le log on voit : "REPONSE DETAILLEE DU SYSTEME CLASSIQUE:\n{"
    matches = re.findall(r"REPONSE DETAILLEE DU SYSTEME CLASSIQUE:\s*(\{.*?\})\s*(?=\d{4}-\d{2}-\d{2}|$)", content, re.DOTALL)
    
    if not matches:
        return None
        
    try:
        # On prend le dernier bloc trouvé
        return json.loads(matches[-1])
    except Exception:
        return None

def flatten_dict(d, parent_key='', sep='_'):
    """Aplatit récursivement un dictionnaire."""
    items = []
    for k, v in d.items():
        if isinstance(v, dict):
            # On ajoute les éléments du sous-dictionnaire au niveau actuel
            # On garde aussi la structure originale si besoin, mais ici on veut surtout aplatir
            items.extend(flatten_dict(v, parent_key, sep=sep).items())
        else:
            items.append((k, v))
    return dict(items)

class PieceMock:
    """Mock objet simulant une pièce du backend avec les attributs du JSON aplati"""
    def __init__(self, data_dict):
        # On aplatit pour que p.alesage_m soit accessible directement
        flat_data = flatten_dict(data_dict)
        for k, v in flat_data.items():
            setattr(self, k, v)
        # On garde l'original aussi au cas où
        self._raw_data = data_dict

def get_piece_data(full_analysis, piece_key):
    """
    Extrait les données d'une pièce spécifique de l'analyse complète.
    Exemple piece_key: 'moteur_thermique'
    """
    if not full_analysis or "sous_systemes" not in full_analysis:
        return None
        
    ss = full_analysis["sous_systemes"]
    if piece_key in ss:
        return PieceMock(ss[piece_key])
    return None
