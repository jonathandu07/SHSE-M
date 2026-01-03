
# GLOBAL PARAMETRIC MODEL
**Target:** 40 kWe | **RPM:** 1000 | **P_mean:** 20 bar

## 1. System Inputs & Hypotheses
*   **Beale Number (Bn):** 0.15 (Robust Air)
*   **Electrical Efficiency:** 90.0%
*   **Required Mech Power:** 44.44 kW
*   **Safety Pressure:** 30.0 bar

## 2. Calculated Dimensions
*   **Total Displacement:** 8.89 L
*   **Cylinders:** 4
*   **Unit Displacement:** 2.22 L
*   **Bore:** 141.4 mm  |  **Stroke:** 141.4 mm
*   **Piston Speed:** 4.71 m/s
*   **Mean Torque:** 424.4 Nm
*   **Max Gas Force (Rod load):** 40850 N

---

## FICHE PIÈCE : Bielle de Puissance (MEC-001)

### 1. Données d'Entrée
*   **Effort Max (Gaz):** 40850 N (4164 kgf)
*   **Longueur (L):** 311.2 mm (Ratio L/C = 2.2)
*   **Matériau:** 42CrMo4 (Acier Trempé Revenu)

### 2. Croquis Headworks (ASCII)
```text
      ( o )  <-- Pied de bielle (D_axe = 35.4 H7)
        |
        |    Section Corps (I-Beam ou Rect)
        |    Épaisseur: 10.3 mm
        |    Largeur:   20.7 mm
        |
      ( O )  <-- Tête de bielle (D_maneton = 84.9)
```

### 3. Calculs de Validation (Détails)
**A. Flambage (Buckling - Euler)**
*   Hypothèse : Bi-articulée (k=1), Section rectangulaire pleine.
*   Charge Critique Visée (SF=4.0) : 163401 N
*   Inertie Requise I : 7.63e-09 m4
*   **Résultat :** Section 10.3 x 20.7 valide.

**B. Contrainte en Compression**
*   $\sigma = F / S$
*   $\sigma = 40850 / (10.3 \times 20.7)$
*   **$\sigma$ = 190.9 MPa**
*   Limite Elastique Re = 900 MPa
*   **Marge Sécurité (Re/sigma) :** 4.7

---

## FICHE PIÈCE : Carter Sous Pression (CAR-001)

### 1. Données d'Entrée
*   **Pression Design:** 30.0 bar (Sécurité incluse)
*   **Dimensions Globales:** 849 x 252 x 354 mm
*   **Matériau:** Fonte GL (Grey Cast Iron)

### 2. Croquis Headworks (ASCII)
```text
   _______________________
  /                       \  <-- Parois Épaisseur Min: 6.0 mm
 |   ( Cy1 )   ( Cy2 )    |
 |                        |
 |      CRANK SPACE       |  <-- Volume interne P = 20 bar
 |________________________|
```

### 3. Calculs (RDM)
**A. Résistance Pression (Hoop Stress)**
*   Formule Cylindre Mince : $\sigma = rac{P \cdot D}{2 \cdot t}$
*   $P = 3.0 MPa$, $D = 212.2 mm$, $t = 6.0 mm$
*   **Contrainte $\sigma$ :** 53.0 MPa
*   **Limite Élastique (Fonte) :** ~250 MPa
*   **Facteur Sécurité :** 4.7 (> 3.0 OK)

---

## FICHE PIÈCE : Vilebrequin (MEC-002)

### 1. Données d'Entrée
*   **Diamètre Portée (Tourillon):** 91.9 mm
*   **Diamètre Maneton:** 84.9 mm
*   **Couple Crête:** 1061 Nm

### 2. Croquis Headworks (ASCII)
```text
      |       |
  (===|   M   |===)  <-- Maneton Ø84.9
      |   |   |
      |===J===|      <-- Tourillon Ø91.9
```

### 3. Calculs (RDM)
**A. Torsion**
*   $	au = \frac{16 \cdot T}{\pi \cdot d^3}$
*   $	au = 7.0$ MPa
*   Limite Elastique (Cisaillement $pprox 0.58 \cdot Re$) : 522 MPa
*   **Facteur Sécurité:** 75.1

---

## FICHE PIÈCE : Piston De Puissance (MEC-010)

### 1. Données d'Entrée
*   **Diamètre:** 141.4 mm (-0.05 / -0.10 pour dilatation)
*   **Axe Piston:** Ø35.4 mm
*   **Pression Spécifique Axe:** 21.8 MPa (Max admissible bague bronze ~30-50 MPa)

### 2. Croquis
```text
      ___________  <-- Tête Plate
     |   =====   | <-- Gorges Segments (3x)
     |           |
     |  ( O )    | <-- Alésage Axe Ø35.4
     |___________|
```

---

## FICHE PIÈCE : Échangeur Chaud (Heater Head) (THE-001)

### 1. Données
*   **Température:** 650°C
*   **Pression:** 30.0 bar
*   **Matériau:** Inox 310S (Réfractaire)

### 2. Dimensionnement Tubes
*   Tube Ø12.0 mm x 1.50 mm
*   Critère Rupture (Creep): 40 MPa
