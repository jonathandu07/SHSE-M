# SHSE-M Sizing Tool

Programme de dimensionnement pour générateur thermo-pneumatique hybride SHSE-M.

## Fonctionnalités
- Calcul des besoins en puissance (Arbre, Indiquée) à partir de la cible Batterie.
- Dimensionnement géométrique (Alésage, Course, Cylindrée).
- Dimensionnement préliminaire des composants (Bielle, Vilebrequin, Volant, Parois).
- Vérifications des contraintes (Vitesse piston, Pression, Flambage).
- Génération de rapports (Markdown), BOM (CSV) et paramètres (JSON).

## Installation
Ce programme est écrit en Python 3.12 et n'utilise que la librairie standard.

## Utilisation

### Ligne de commande
```bash
python -m shse_m_sizing.main --P_batt 10 --N 3000 --p_me 6
```

Ou via un fichier de configuration :
```bash
python -m shse_m_sizing.main --json test_case.json
```

### Paramètres
Voir `test_case.json` pour un exemple complet de tous les paramètres configurables.

## Architecture
- `config.py` : Définitions des données.
- `thermodynamics.py` : Chaîne de puissance et cycle.
- `mechanical.py` : Géométrie et RDM.
- `check.py` : Validation.
- `report.py` : Export.
