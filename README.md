# Outil de Dimensionnement SHSE-M

Programme de dimensionnement pour générateur thermo-pneumatique hybride SHSE-M.
Version Complète : Calcul détaillé des pièces + Génération de croquis.

## Fonctionnalités
- **Calculs thermodynamiques** : Puissance, Cylindrée.
- **Mécanique Détaillée** : 
  - Piston (Jupe, Segments, Axe).
  - Bielle (Corps en I, Tête, Pied, Boulons).
  - Vilebrequin (Manetons, Tourillons, Bras).
  - Volant, Parois, Culasse.
- **Croquis Automatiques** : Génération de schémas techniques (SVG/PNG) inclus dans le rapport.
- **Rapports** : Markdown (avec images), CSV (Nomenclature complète), JSON.

## Installation & Utilisation

### Via Exécutable (Windows)
1. Double-cliquez sur `SHSE_Dimensionnement.exe` (généré via `build_exe.bat`).
2. Remplissez les paramètres.
3. Lancez le calcul.
4. Consultez le rapport et les images dans le dossier `output_shse_m`.

### Via Python
1. Installez les dépendances :
   ```bash
   pip install matplotlib
   ```
2. Lancez l'interface :
   ```bash
   python -m shse_m_sizing.gui
   ```

## Auteurs
Projet SHSE-M.
