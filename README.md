# Outil de Dimensionnement SHSE-M

Programme de dimensionnement complet pour générateur thermo-pneumatique.

## Interface Moderne (V4)
L'outil dispose d'une interface graphique ergonomique (`shse_m_sizing.gui`) :
- **Onglet Config** : Paramétrage complet.
- **Onglet Données** : Tableau dynamique listant toutes les cotes de toutes les pièces.
- **Onglet Croquis** : Visualisation directe des coupes (Piston, Bielle, Vilebrequin).
- **Onglet Rapport** : Synthèse.

## Fonctionnalités Métier
- Calcul détaillé de la chaîne de cotes moteur (Piston, Bielle, Vilebrequin, Visserie, Parois).
- Vérification automatique des contraintes (Vitesse piston, Pression, Flambage).
- Exports Automatiques : CSV, JSON, Markdown, PNG.

## Installation
1. Python 3.12+ requis.
2. Dépendances :
   ```bash
   pip install matplotlib
   ```
3. Lancer :
   ```bash
   python -m shse_m_sizing.gui
   ```

## Exécutable
Double-cliquez sur `build_exe.bat` pour générer un `.exe` portable (Windows).
