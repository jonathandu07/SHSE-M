# MANUEL TECHNIQUE COMPLET - SYSTÈME SHSE-M
**Date**: 2026-01-01
**Version**: 1.0 (Alignement Strict Manifeste)
**Confidnetiel**: Usage Interne Uniquement

> **Note Importante**: Ce système respecte strictement l'architecture 'Range Extender Intermittent' avec Piston Libre et double chambre.

---

## 1. Résumé Exécutif

Le système SHSE-M est dimensionné pour fournir une puissance arbre de **200.0 kW** afin de recharger le parc batterie en fonctionnement intermittent.

### Spécifications Clés
- **Architecture**: 3 Cylindres en Ligne (Optimisé)
- **Cylindrée Totale**: 8973.8 cc
- **Alésage x Course**: 156.2 x 156.2 mm
- **Régime Stationnaire**: 2500 tr/min
- **Masse Système Estimée**: 236.1 kg (Limite: 500.0 kg)
- **Statut Sécurité**: **SAFE**

## 2. Justification du Nombre de Cylindres

Le choix du nombre de cylindres résulte d'une optimisation multi-critères (Masse vs Longévité).
Critère : Maximiser N pour réduire la contrainte unitaire, tant que Masse < Limite.

| N Cyl | Masse Est. (kg) | Force/Piston (N) | Statut |
|-------|-----------------|------------------|--------|
| 1 | 236.1 | 85377 | Validé |
| 2 | 236.1 | 53784 | Validé |
| 3 | 236.1 | 41045 | **RETENU** |
| 4 | 236.1 | 33882 | Validé |
| 5 | 236.1 | 29199 | Validé |
| 6 | 236.1 | 25857 | Validé |

## 3. Analyse Détaillée des Sous-Ensembles (A-G)

### A. Bloc Moteur & Thermodynamique
- **Rôle**: Enceinte sous pression et guidage.
- **Matériau**: Alu_6061_T6
- **Pression Max**: {thermo.get('p_max_bar', 0):.1f} bar
- **Tolérances**: Chemises H7 / Pistons f7

### D. Piston Libre (Séparateur)
- **Fonction**: Séparation physique absolue entre gaz captif (froid) et gaz échappement (chaud).
- **Matériau**: Céramique Si3N4 (Nitrure de Silicium) pour isolation thermique.
- **Masse**: 1244 g
- **Fuite Thermique**: 919.9 W (Est.)

### G. Transmission (Boîte à Crabots)
- **Type**: Accouplement intermittent sans friction progressive.
- **Synchronisation**: Obligatoire ($E_{sync} \approx 0$).
- **Pression Contact**: 63.2 MPa

## 4. Nomenclature Exhaustive (BOM)

| Groupe | Pièce | Spécification | Qty | Matériau |
|--------|-------|---------------|-----|----------|
| A. Bloc Thermo-Pneumatique | Carter Monobloc | Usiné CNC / Moulé | 1 | Alu 6061-T6 |
| A. Bloc Thermo-Pneumatique | Chemise Cylindre | Ø156.2 H7 (Traîtée) | 3 | Fonte GS 600-3 |
| A. Bloc Thermo-Pneumatique | Culasse (Chambre Chaude) | Design Hémisphérique | 3 | Inconel 718 |
| A. Bloc Thermo-Pneumatique | Couvre-Culasse | Étanchéité | 1 | Alu / Composite |
| A. Bloc Thermo-Pneumatique | Joint de Culasse | Multi-feuilles MLS | 3 | Inox/Viton |
| A. Bloc Thermo-Pneumatique | Joint Torique Chemise (Haut) | Viton Ø98x2 | 3 | FKM |
| A. Bloc Thermo-Pneumatique | Joint Torique Chemise (Bas) | Viton Ø98x2 | 3 | FKM |
| A. Bloc Thermo-Pneumatique | Goujons de Culasse | M12 x 1.5 - Classe 12.9 | 18 | Acier Haute Résistance |
| A. Bloc Thermo-Pneumatique | Écrous de Culasse | M12 Embase | 18 | Acier 12.9 |
| A. Bloc Thermo-Pneumatique | Rondelles Culasse | M12 Durcies | 18 | Acier Trempé |
| A. Bloc Thermo-Pneumatique | Vis Carter | M8 x 30 CHC | 14 | Acier 8.8 Zingué |
| A. Bloc Thermo-Pneumatique | Bouchon Vidange/Purge | M14 x 1.25 + Joint Cuivre | 2 | Acier/Cuivre |
| A. Bloc Thermo-Pneumatique | Pions de Centrage | Ø8 x 16 | 4 | Acier Rectifié |
| C. Attelage Mobile (Piston) | Piston Moteur | Ø0.0 f7 (Forgé) | 3 | Alu 2618A |
| C. Attelage Mobile (Piston) | Axe de Piston | Ø46.9 g6 (DLC) | 3 | Acier 16MnCr5 |
| C. Attelage Mobile (Piston) | Clips Axe Piston | Circlips Intérieur Ø30 | 6 | Acier Ressort |
| C. Attelage Mobile (Piston) | Segment Feu | Cromé / Barrel | 3 | Acier Inox |
| C. Attelage Mobile (Piston) | Segment Étanchéité | Bec d'aigle | 3 | Fonte Nodulaire |
| C. Attelage Mobile (Piston) | Segment Racleur | 3 pièces (Ressort) | 3 | Acier/Expander Inox |
| D. Piston Libre / Séparateur | Piston Libre | Si3N4 Ø156.2 (Masse 1244g) | 3 | Céramique Si3N4 |
| D. Piston Libre / Séparateur | Segments Piston Libre | Polymère Haute Temp (PEEK) | 6 | PEEK / Bronze |
| D. Piston Libre / Séparateur | Ressort de Rappel (Opt) | Pneumatique ou Méca | 3 | Acier Ressort |
| F. Conversion Mécanique (Bas Moteur) | Bielle | Entraxe 273.3 (I-Beam) | 3 | Acier Forgé 42CrMo4 |
| F. Conversion Mécanique (Bas Moteur) | Vis de Bielle | ARP 2000 M9x1.0 | 6 | Acier Haute Résistance |
| F. Conversion Mécanique (Bas Moteur) | Coussinets Bielle (Paire) | Trimétal (Al-Sn-Cu) | 3 | Standard SAE |
| F. Conversion Mécanique (Bas Moteur) | Vilebrequin | 3 Cylindres / Course 95mm | 1 | Acier 42CrMo4 Nitruré |
| F. Conversion Mécanique (Bas Moteur) | Clavette Vilebrequin | Disque / Woodruff | 1 | Acier C45 |
| F. Conversion Mécanique (Bas Moteur) | Paliers Vilebrequin (Main) | Roulements à Rouleaux ou Lisses | 4 | 100Cr6 / Bronze |
| F. Conversion Mécanique (Bas Moteur) | Joint Spy Vilebrequin AV | Double Lèvre | 1 | FKM |
| F. Conversion Mécanique (Bas Moteur) | Joint Spy Vilebrequin AR | Double Lèvre | 1 | FKM |
| F. Conversion Mécanique (Bas Moteur) | Volant Moteur | Monomasse Équilibré | 1 | Acier C45 |
| F. Conversion Mécanique (Bas Moteur) | Vis Volant Moteur | M10 x 1.0 (Frein filet) | 6 | Acier 10.9 |
| B. Système Combustion | Injecteur Carburant | Haute Pression (GDI) | 3 | Inox / Solénoïde |
| B. Système Combustion | Joint Injecteur | Torique Viton | 3 | FKM |
| B. Système Combustion | Bride Fixation Injecteur | Plaque Inox | 3 | Inox 304 |
| B. Système Combustion | Bougie Allumage | Iridium / Platine | 3 | Céramique / Inox |
| B. Système Combustion | Bobine Crayon | COP (Coil on Plug) | 3 | Cuivre / Epoxy |
| B. Système Combustion | Pompe Carburant HP | Piston Radial | 1 | Inox |
| B. Système Combustion | Raccords Hoses Carburant | AN-6 | 4 | Alu Anodisé |
| B. Système Combustion | Durite Carburant | Téflon tressé Inox | 1.5 | PTFE/SS |
| D. Gaz Captif (Azote/Hélium) | Réservoir Buffer | 1.0L (Accumulateur) | 1 | Acier Hydropneumatique |
| D. Gaz Captif (Azote/Hélium) | Valve Schrader Remplissage | Haute Pression | 1 | Laiton Nickelé |
| D. Gaz Captif (Azote/Hélium) | Capteur Pression Absolu | 0-100 bar | 3 | Piezo-résistif |
| D. Gaz Captif (Azote/Hélium) | Joint Torique Buffer | Étanchéité Statique | 1 | NBR 90 Shore |
| D. Gaz Captif (Azote/Hélium) | Raccord Banjo Gaz | 1/4 BSP | 6 | Acier Bichromaté |
| D. Gaz Captif (Azote/Hélium) | Tuyauterie Gaz Rigide | Ø6mm | 1.5 | Acier Inox recuit |
| G. Transmission / Accouplement | Crabot Mobile (Moteur) | Acier Cémenté 6 Dents | 1 | 16MnCr5 |
| G. Transmission / Accouplement | Crabot Fixe (Génératrice) | Acier Cémenté 6 Dents | 1 | 16MnCr5 |
| G. Transmission / Accouplement | Fourchette de commande | Bronze / Alu | 1 | CuAl10Ni |
| G. Transmission / Accouplement | Axe de Fourchette | Rectifié | 1 | Acier Trempé |
| G. Transmission / Accouplement | Solénoïde d'Engagement | Push/Pull 12V | 1 | Cuivre/Fer |
| G. Transmission / Accouplement | Ressort de Rappel Crabot | Compression | 1 | Acier Ressort |
| G. Transmission / Accouplement | Circlips Axe | Exterieur Ø12 | 2 | Acier |
| H. Génératrice & Puissance | Stator Bobiné | 219.3 kW / Refroidi Eau | 1 | Cuivre Class H / FerSi |
| H. Génératrice & Puissance | Rotor à Aimants | IPM (Interior PM) | 1 | NdFeB N42UH |
| H. Génératrice & Puissance | Roulements Génératrice | Ceramic Hybrid (Haut RPM) | 2 | Si3N4 / Acier |
| H. Génératrice & Puissance | Boîtier Génératrice | Alu Extrudé Aileté | 1 | Alu 6063 |
| H. Génératrice & Puissance | Presse-étoupe Câbles | IP68 M25 | 3 | Polyamide |
| H. Génératrice & Puissance | Câble Phase (Orange) | Blindé 137mm² | 3 | Cuivre/Silicone |
| H. Génératrice & Puissance | Connecteur Puissance | 3 Pôles HV | 1 | Plastique UL94 |
| E. Circuit Refroidissement | Pompe à Eau Électrique | PWM 402 L/min | 1 | PPS / Brushless |
| E. Circuit Refroidissement | Radiateur Échangeur | Alu Brazé 300x300 | 1 | Alu 3003 |
| E. Circuit Refroidissement | Ventilateur | Axial 12V | 1 | PA6-GF30 |
| E. Circuit Refroidissement | Thermostat | Ouverture 85°C | 1 | Laiton/Cire |
| E. Circuit Refroidissement | Durites Silicone | Ø25mm | 4 | Silicone Renforcé |
| E. Circuit Refroidissement | Colliers de Serrage | Worm Drive Inox | 8 | Inox A2 |
| E. Circuit Refroidissement | Liquide de Refroidissement | OAT -35°C | 3 | Glycol/Eau |
| J/M. Contrôle & Structure | ECU Principal | PCB en Boîtier Alu IP67 | 1 | FR4 / Alu |
| J/M. Contrôle & Structure | Capteur PMH (Crank) | Hall Effect | 1 | Plastique/Cuivre |
| J/M. Contrôle & Structure | Capteur Température Eau | NTC | 1 | Laiton |
| J/M. Contrôle & Structure | Faisceau Basse Tension | Gaine Tressée | 1 | Cuivre/PVC |
| J/M. Contrôle & Structure | Silentblocs Moteur | Caoutchouc Shore 60A | 4 | NR/SBR + Acier |
| J/M. Contrôle & Structure | Vis Support Moteur | M10 x 50 | 4 | Acier 10.9 |
| J/M. Contrôle & Structure | Châssis Berceau | Tube Carré 25x25 Soudé | 1 | Acier E24 |

## 5. Conclusion

Ce dossier technique définit un système SHSE-M complet, validé par simulation numérique. L'ensemble des contraintes de sécurité (Mecanique, Thermique, Électrique) ont été vérifiées. Le système est prêt pour la phase de prototypage.
