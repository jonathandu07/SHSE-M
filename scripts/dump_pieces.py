import sys
import os
import pprint

sys.path.append(os.path.abspath('d:\\Documents\\GitHub\\SHSE-M'))
from backend.main import dimensionner_systeme_shsem

rep = dimensionner_systeme_shsem(
    puissance_traction_kw=40.0,
    charger_batterie=True,
    temps_charge_cible_h=1.0,
    vitesse_moteur_thermique_rpm=3000.0,
    rapport_vitesse_alt_sur_moteur=2.0,
    pme_pa=8.0e5,
    vitesse_piston_max_ms=10.0,
    longueur_dispo_m=1.2,
    largeur_dispo_m=0.8,
    pression_max_pa=3.0e6,
    contrainte_admissible_pa=1.2e8,
    densite_materiau_kg_m3=7800.0,
    cout_matiere_eur_kg=2.0,
    rendement_mecanique_cible_min=0.80,
)

pieces_data = {}
for name, piece_obj in rep.get('pieces', {}).items():
    if piece_obj is None:
        pieces_data[name] = None
    elif hasattr(piece_obj, 'analyser'):
        try:
            pieces_data[name] = piece_obj.analyser(strict=False)
        except Exception as e:
            pieces_data[name] = {'error': str(e)}
    else:
        pieces_data[name] = 'Object has no analyser method'

with open('pieces_output.txt', 'w', encoding='utf-8') as f:
    pprint.pprint(pieces_data, stream=f, indent=2, width=120)
print('Done. Saved to pieces_output.txt')
