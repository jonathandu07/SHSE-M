# Outil de Dimensionnement SHSE-M

Programme de dimensionnement pour générateur thermo-pneumatique hybride SHSE-M.
Développé en Python, avec une interface graphique simple et des exports complets.

## Fonctionnalités
- **Calculs thermodynamiques** : Puissance nécessaire, cylindrée.
- **Dimensionnement mécanique** : Alésage, course, bielle, vilebrequin, piston, volant d'inertie.
- **Vérifications de sécurité** : Vitesse piston, flambage, contraintes matériaux.
- **Rapports** : Génération de fichiers Markdown, CSV (Nomenclature) et JSON.

## Installation

### Option 1 : Utiliser l'exécutable (Windows)
1. Allez dans le dossier `dist/` (s'il est fourni) ou téléchargez la dernière release.
2. Lancez `SHSE_Dimensionnement.exe`.
3. Pas besoin de Python installé.

### Option 2 : Depuis les sources (Développeurs)
1. Installez Python 3.12+.
2. Clonez ce dépôt.
3. (Optionnel) Créez un environnement virtuel.
4. Lancez l'interface graphique :
   ```bash
   python -m shse_m_sizing.gui
   ```

## Utilisation

1. **Remplir les champs** dans l'interface :
   - Cibles : Puissance Batterie, Régime, Pression.
   - Rendements : Chaîne complète du thermique à la batterie.
   - Contraintes : Limites matériaux et sécurité.
2. Cliquez sur **LANCER LE CALCUL**.
3. Le rapport s'affiche à droite.
4. Cliquez sur **Ouvrir le dossier de sortie** pour voir les fichiers Excel (CSV) et PDF (Markdown converti).

## Compilation (Créer l'.exe)
Pour créer votre propre exécutable à un seul fichier :
1. Double-cliquez sur `build_exe.bat`.
2. Attendez la fin de la compilation.
3. L'application sera dans le dossier `dist/`.

## Auteurs
Conçu pour le projet SHSE-M.
