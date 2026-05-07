Je te propose une **version dossier technique de niveau pré-industrialisation**, structurée comme un véritable **cahier des charges technique + fonctionnel exploitable pour R&D, calcul, CAO, simulation et validation prototype**.

Tu peux le reprendre tel quel comme base de `README.md`, ou mieux : en faire un document séparé `DOSSIER_TECHNIQUE_STHO_ME.md`.

# SHSE-M / STHO-ME

Outil Python de pre-dimensionnement pour un systeme thermo-hybride avec backend de calcul, inventaire pieces, esquisses 2D/3D et interface Kivy.

## Demarrage rapide

```powershell
python -m pip install -r requirements.txt
python frontend/gui/main.py
```

## Tests

```powershell
python -m pytest
```

## Points d'entree utiles

- Interface graphique : `frontend/gui/main.py`
- Orchestrateur strict : `backend/main.py::dimensionner_systeme_shsem`
- Analyse stricte depuis une puissance seule : `backend/main.py::analyser_systeme_depuis_puissance`
- Optimisation stricte depuis une puissance : `backend/main.py::optimiser_systeme_depuis_puissance`
- Mode simple GUI : `backend/main.py::dimensionner_systeme_shsem_simple`
- Base locale chiffree : `backend/modules/systeme/database.py`
- Generation puissance -> JSON + BDD : `backend/main.py::generer_rapport_puissance_json_bdd`
- Script range : `backend/scripts/generer_rapport_puissance.py`

Le mode `analyser_systeme_depuis_puissance` accepte une puissance en `W`, `kW`, `ch`, `cv` ou `hp` et ne cree aucune geometrie par defaut. Le mode `optimiser_systeme_depuis_puissance` cherche les meilleurs candidats uniquement dans les regimes, tensions, rendements, PME, rapports ou contraintes fournis. Aucun espace de recherche n'est invente. Le mode strict complet attend un scenario complet. L'interface utilise le mode simple pour produire un premier dimensionnement coherent a partir d'une puissance cible.

Exemple strict avec stockage :

```powershell
python backend/scripts/generer_rapport_puissance.py 150 --unite kw --search-json '{\"rpm_sortie\":[1000,2000],\"tension_dc_v\":[400,800]}'
```

Sans `--search-json`, le rapport est quand meme ecrit, mais il indique les donnees manquantes au lieu de choisir un "meilleur" couple ou courant.

Les fichiers generes (`__pycache__`, logs, base SQLite locale, cle locale, sorties PDF) sont ignores via `.gitignore`; s'ils sont deja presents dans le dossier, ils peuvent rester localement mais ne devraient pas etre ajoutes aux prochains commits.

---

# DOSSIER TECHNIQUE COMPLET

# STHO-ME — Système Thermo-Hybride Oscillatoire Multi-Énergies

---

# 1. Objet du dossier

Le présent dossier définit :

* l’architecture fonctionnelle complète,
* les exigences techniques détaillées,
* les équations de dimensionnement,
* les contraintes physiques,
* les interfaces mécaniques,
* les critères de validation,
* les hypothèses de calcul,
* les limites expérimentales.

Ce document constitue la base :

* de conception mécanique,
* de simulation multiphysique,
* de prototypage,
* de validation industrielle.

---

# 2. Définition du système

Le STHO-ME est un système thermo-mécanique oscillatoire hybride destiné à convertir :

[
E_{chimique} \rightarrow E_{thermique} \rightarrow E_{mécanique} \rightarrow E_{électrique}
]

par l’intermédiaire :

* d’une chambre chaude semi-ouverte,
* d’un déplaceur séparateur,
* d’une chambre froide compressible,
* d’un piston moteur,
* d’une transmission mécanique,
* d’un alternateur.

---

# 3. Architecture physique générale

---

# 3.1 Sous-ensemble thermique principal

Constituants :

* cylindre principal 
* chambre chaude
* chambre froide
* échangeur thermique
* soupape purge
* soupape sécurité

---

# 3.2 Sous-ensemble mobile oscillatoire

Constituants :

* piston moteur 
* déplaceur 
* joints
* arbre piston
* coussinet 

---

# 3.3 Sous-ensemble transformation rotation

Constituants :

* bielle
* vilebrequin
* arbre vilebrequin 
* arbre sortie 
* clavette 
* roulements aiguilles 

---

# 3.4 Sous-ensemble électrique

Constituants :

* alternateur triphasé
* redresseur
* bus continu
* batterie
* BMS

---

# 4. Fonctionnement thermodynamique détaillé

---

# 4.1 Combustion intermittente

La combustion fournit :

[
Q_{comb} = \dot{m_f} \cdot PCI
]

avec :

* (\dot{m_f}) : débit massique carburant
* (PCI) : pouvoir calorifique inférieur

---

# 4.2 Élévation pression chambre chaude

Approximation gaz parfait :

[
pV = mRT
]

Évolution :

[
\frac{p_2}{p_1} = \frac{T_2}{T_1}
]

si volume quasi constant.

---

# 4.3 Effort appliqué au déplaceur

Surface active :

[
A = \frac{\pi B^2}{4}
]

Force :

[
F = p \cdot A
]

---

# 4.4 Chambre froide ressort pneumatique

Gaz captif :

[
pV^\gamma = constante
]

avec :

* (\gamma \approx 1.4)

Rigidité pneumatique :

[
k = \gamma \frac{p_0 A^2}{V_0}
]

---

# 5. Fonctionnement mécanique détaillé

---

# 5.1 Travail indiqué

[
W_i = p_{me} \cdot V_d
]

---

# 5.2 Puissance indiquée

[
P_i = p_{me} \cdot V_d \cdot N \cdot \frac{1}{60}
]

---

# 5.3 Puissance arbre

[
P_{shaft} = \eta_m \cdot P_i
]

---

# 5.4 Couple vilebrequin

[
T = \frac{P_{shaft}}{\omega}
]

avec :

[
\omega = \frac{2\pi N}{60}
]

---

# 5.5 Effort bielle

[
F_t = \frac{T}{r}
]

---

# 5.6 Force maximale piston

[
F_{max} = p_{max} \cdot A
]

---

# 6. Dimensionnement cylindre

---

# 6.1 Cylindrée

[
V_d = \frac{\pi}{4} B^2 S
]

avec :

* (B) = alésage
* (S) = course

---

# 6.2 Cylindrée totale

[
V_{tot} = N_{cyl} \cdot V_d
]

---

# 6.3 Vitesse moyenne piston

[
U_p = 2SN/60
]

Condition :

[
U_p \le 8 , m/s
]

(valeur prudente prototype durable)

---

# 6.4 Épaisseur cylindre

Contrainte circonférentielle :

[
\sigma_\theta = \frac{p_{max}B}{2t}
]

Donc :

[
t \ge \frac{p_{max}B}{2\sigma_{adm}}
]

---

# 6.5 Vérification Von Mises

[
\sigma_{VM} = \sqrt{\sigma_\theta^2 + \sigma_z^2 - \sigma_\theta \sigma_z}
]

---

# 7. Dimensionnement piston

Module actuel très avancé : 

---

# 7.1 Jeux thermiques

[
J = D_{cylindre} - D_{piston}
]

---

# 7.2 Dilatation thermique

[
\Delta D = \alpha D \Delta T
]

---

# 7.3 Force frottement segment

[
P_f = F_n \cdot v \cdot \mu
]

---

# 7.4 Fuite annulaire

[
Q = \frac{\pi r h^3 \Delta p}{6 \mu L}
]

---

# 8. Déplaceur

Module actuel : 

---

# 8.1 Flambage Euler

[
F_{crit} = \frac{\pi^2 E I}{(KL)^2}
]

Condition :

[
F_{max} < \frac{F_{crit}}{FS}
]

---

# 8.2 Inertie tubulaire

[
I = \frac{\pi}{64}(D_e^4 - D_i^4)
]

---

# 9. Bielle

---

# 9.1 Compression

[
\sigma = \frac{F}{A}
]

---

# 9.2 Flambage

[
F_{crit} = \frac{\pi^2 E I}{(KL)^2}
]

---

# 10. Vilebrequin

Module actuel : 

---

# 10.1 Torsion

[
\tau = \frac{16T}{\pi d^3}
]

---

# 10.2 Flexion

[
\sigma = \frac{32M}{\pi d^3}
]

---

# 10.3 Von Mises

[
\sigma_{VM} = \sqrt{\sigma^2 + 3\tau^2}
]

---

# 11. Roulements aiguilles

Module actuel : 

---

# 11.1 Charge ISO 281

[
L_{10} = \left(\frac{C}{P}\right)^p
]

---

# 11.2 Pression projetée

[
p = \frac{F}{d \cdot B}
]

---

# 11.3 Charge aiguille

[
F_{aiguille} = \frac{F}{z}
]

---

# 12. Arbre transmission

Module : 

---

# 12.1 Torsion arbre

[
\tau = \frac{16T}{\pi d^3}
]

---

# 12.2 Clavette DIN

Module : 

Force tangentielle :

[
F_t = \frac{2T}{d}
]

---

# 13. Volant inertie

---

# 13.1 Énergie stockée

[
E = \frac12 J \omega^2
]

---

# 13.2 Inertie minimale

[
J \ge \frac{\Delta E}{\omega^2 \epsilon}
]

---

# 14. Purge gaz

---

# 14.1 Débit compressible

[
\dot m = C_d A p \sqrt{\frac{\gamma}{RT}}
]

---

# 14.2 Condition purge

Fenêtre angulaire stricte :

[
\theta_{purge}
]

---

# 15. Récupération thermique

---

# 15.1 Gaz purge

[
Q = \dot m c_p (T_{in} - T_{out}) \epsilon
]

---

# 15.2 Sources secondaires

* alternateur
* redresseur
* batterie

---

# 16. Chaîne électrique

---

# 16.1 Puissance alternateur

[
P = \eta_{gen} T \omega
]

---

# 16.2 Rendement global

[
\eta_{global} =
\eta_{th}
\eta_m
\eta_{gen}
\eta_{elec}
\eta_{charge}
]

---

# 17. Mode secours pneumatique

---

# 17.1 Énergie stockée

[
E = \frac{pV}{\gamma-1}\left[1-\left(\frac{p_{atm}}{p}\right)^{\frac{\gamma-1}{\gamma}}\right]
]

---

# 18. Contraintes validation

Validation obligatoire :

* simulation thermique
* simulation mécanique
* simulation fatigue
* prototype instrumenté
* mesure rendement réel

---

# 19. Données minimales obligatoires avant prototype réel

Il manque obligatoirement :

## thermique réel :

* température chambre chaude réelle
* cinétique combustion réelle
* temps purge réel

## mécanique réelle :

* profil exact efforts alternatifs
* vibrations

## rendement réel :

* pertes mesurées

---

# 20. Ce qu’il faut maintenant pour passer niveau industriel réel

Je recommande de produire ensuite :

## Dossier V2 :

* matrice dimensionnement complète pièce par pièce
* plages réalistes pression / température
* rendement physiquement plausible
* zones de danger mécanique
* architecture prototype V1 industrialisable

---

## Très important

Aujourd’hui ton code mécanique est déjà très sérieux :

* cylindre : robuste 
* piston : excellent niveau 
* déplaceur : propre 
* vilebrequin : solide 

Mais ton dossier système doit encore verrouiller :

## combustion réelle

## échange thermique réel

## cycle réel complet


---

# 11. VARIABLES D’ENTRÉE STRUCTURÉES ET HIÉRARCHISÉES DU PROGRAMME

Le programme ne doit jamais accepter des variables isolées sans hiérarchie physique.

Chaque variable doit appartenir à une famille de calcul.

---

# 11.1 Bloc thermique primaire

## Température côté chaud

[
T_h
]

avec :

[
T_h > T_c
]

et :

[
T_h < T_{limite\ matériau}
]

---

## Température côté froid

[
T_c
]

---

## Gradient thermique disponible

\Delta T = T_h - T_c

Condition minimale d’exploitation :

[
\Delta T > 40K
]

Sous ce seuil :

rendement fortement dégradé.

---

## Flux thermique incident

[
\dot Q_{in}
]

---

## Flux thermique récupérable sur échappement

[
\dot Q_{ech} = \dot m_{gaz} \times C_p \times (T_{gaz}-T_h)
]

avec :

[
C_p \approx 1000\ J/kg.K
]

---

## Flux thermique récupérable sur composants internes

[
\dot Q_{comp}
]

issus :

* alternateur,
* électronique,
* frottements,
* boîte mécanique.

---

## Flux total utile

[
\dot Q_{utile} = \dot Q_{comb} + \dot Q_{ech} + \dot Q_{comp}
]

---

---

# 11.2 Bloc géométrique moteur complet

---

## Diamètre piston

[
D
]

---

## Rayon piston

[
R = \frac{D}{2}
]

---

## Surface utile piston

S = \frac{\pi D^2}{4}

---

## Course utile

[
C
]

---

## Volume balayé exact

V_b = S \times C

---

## Volume mort

[
V_m
]

Obligatoire :

[
V_m > 0
]

---

## Cylindrée réelle

[
V_t = V_b + V_m
]

---

## Rapport volumétrique réel

[
r_v = \frac{V_t}{V_m}
]

---

---

# 11.3 Bloc pression interne réelle

---

## Pression minimale

[
P_{min}
]

---

## Pression maximale

[
P_{max}
]

---

## Pression moyenne effective

[
P_{me}
]

avec :

[
P_{min} < P_{me} < P_{max}
]

---

## Rapport de pression

[
r_p = \frac{P_{max}}{P_{min}}
]

---

## Force instantanée piston

[
F = P \times S
]

---

## Force maximale réelle

[
F_{max} = P_{max} \times S
]

---

---

# 12. CINÉMATIQUE COMPLÈTE RÉELLE

---

## Régime moteur

[
N
]

---

## Fréquence réelle

[
f = \frac{N}{60}
]

---

## Pulsation réelle

\omega = \frac{2\pi N}{60}

---

## Vitesse linéaire piston

[
V_p = 2 \times C \times f
]

---

## Accélération piston max

[
a = \omega^2 \times R
]

---

## Effort inertiel

[
F_i = m \times a
]

---

## Effort total bielle

[
F_t = F + F_i
]

---

---

# 13. TRAVAIL THERMODYNAMIQUE RÉEL

---

## Travail élémentaire cycle

[
W = \int P dV
]

---

## Approximation industrielle

[
W = P_{me} \times V_b
]

---

## Puissance mécanique instantanée

[
P_m = W \times f
]

---

## Couple moteur réel

[
C_m = \frac{P_m}{\omega}
]

---

---

# 14. DIMENSIONNEMENT STRUCTUREL DURCI

---

# Arbre

---

## Contrainte torsion

[
\tau = \frac{16C}{\pi d^3}
]

---

## Diamètre arbre corrigé sécurité

[
d = \left(\frac{16C \times K_s}{\pi \tau_{adm}}\right)^{1/3}
]

avec :

[
K_s = 2\ à\ 3
]

---

---

# Flexion combinée

[
\sigma = \frac{32M}{\pi d^3}
]

---

## Von Mises réel

[
\sigma_{vm} = \sqrt{\sigma^2 + 3\tau^2}
]

Condition :

[
\sigma_{vm} < \sigma_{adm}
]

---

---

# 15. BIELLE — VERSION INDUSTRIELLE

---

## Compression réelle

[
\sigma = \frac{F_t}{A}
]

---

## Flambage Euler réel

[
F_{cr} = \frac{\pi^2 E I}{(K L)^2}
]

---

Condition :

[
F_t < \frac{F_{cr}}{2}
]

---

---

# 16. BATTERIE — INTÉGRATION SYSTÈME COMPLÈTE

Puisque cellules commerce :

on dimensionne uniquement architecture.

---

## Tension bus

[
U_{bus}
]

---

## Nombre série

[
N_s = \frac{U_{bus}}{U_{cell}}
]

---

## Nombre parallèle

[
N_p = \frac{C_{tot}}{C_{cell}}
]

---

## Énergie batterie

[
E = U_{bus} \times C_{tot}
]

---

## Courant instantané max

[
I = \frac{P}{U}
]

---

## Vérification thermique batterie

[
P_{joule} = R I^2
]

---

---

# 17. CONTRAINTE MAJEURE DE TON CONCEPT HYBRIDE

Puisque moteur fonctionne 50% du temps :

---

## Puissance instantanée imposée

P_{instant} = 2(P_{traction}+P_{recharge})

---

C’est la formule fondamentale de ton architecture.

Elle gouverne :

* dimension moteur,
* alternateur,
* refroidissement,
* section arbre.

---

---

# 18. REFROIDISSEMENT INDUSTRIEL RÉEL

---

## Puissance perdue

[
P_{pertes} = P_{entrée} - P_{utile}
]

---

## Surface échange thermique

[
A = \frac{Q}{h \Delta T}
]

---

## Si refroidissement forcé :

[
h = 50\ à\ 300
]

---

## Si convection naturelle :

[
h = 5\ à\ 15
]

---

---

# 19. RENDEMENT GLOBAL RÉALISTE

---

## Rendement thermique théorique plafond

[
\eta = 1 - \frac{T_c}{T_h}
]

---

## Rendement réel machine

[
\eta_{réel} = \eta_{Carnot} \times \eta_{mécanique} \times \eta_{alternateur}
]

---

Ton système réel doit viser :

---

## réaliste :

[
25% à 35%
]

---

## très ambitieux :

[
35% à 42%
]

---

Au-delà :

il faut validation expérimentale lourde.

---

---

# 20. TABLEAU DES COEFFICIENTS OBLIGATOIRES

Toujours imposer :

---

## sécurité mécanique

[
K_s = 2\ à\ 3
]

---

## sécurité thermique

[
K_t = 1.3
]

---

## sécurité électrique

[
K_e = 1.25
]

---

---

Voici une **suite harmonisée, densifiée et renumérotée proprement** pour s’enchaîner avec ton dossier sans casser la logique.
J’ai aussi corrigé plusieurs points implicites :

* suppression du doublon de numérotation à partir du second “11” ;
* homogénéisation des notations ;
* distinction plus claire entre **grandeurs d’entrée**, **grandeurs calculées**, **contraintes de vérification** ;
* ajout des **plages de validité**, **marges de sécurité**, **hypothèses physiques** et **critères de conception système**.

Tu peux donc ajouter cette suite **après ta section 20 actuelle**, en remplaçant le bloc doublonné.

---

# 21. Variables d’entrée structurées et hiérarchisées du programme

Le programme de conception ne doit jamais manipuler des variables isolées sans rattachement à un sous-système physique identifié.
Chaque variable d’entrée doit appartenir à une famille de calcul cohérente :

* thermique ;
* géométrique ;
* pressive ;
* cinématique ;
* mécanique ;
* électrique ;
* énergétique ;
* matériaux ;
* contrôle.

Toutes les entrées doivent être contrôlées avant calcul par :

* test de positivité ;
* test de cohérence dimensionnelle ;
* test de domaine physique ;
* test de compatibilité inter-variables.

---

## 21.1 Bloc thermique primaire

### Température côté chaud

$$
T_h
$$

Condition :

$$
T_h > T_c
$$

et :

$$
T_h < T_{\text{limite matériau}}
$$

### Température côté froid

$$
T_c
$$

### Gradient thermique disponible

$$
\Delta T = T_h - T_c
$$

Condition minimale d’exploitation recommandée :

$$
\Delta T > 40\ \text{K}
$$

Sous ce seuil, le fonctionnement devient peu pertinent du point de vue énergétique, sauf architecture très spécialisée.

### Flux thermique de combustion

$$
\dot Q_{\text{comb}} = \dot m_f \cdot PCI
$$

avec :

* $\dot m_f$ : débit massique carburant ;
* $PCI$ : pouvoir calorifique inférieur.

### Flux thermique récupérable sur les gaz d’échappement

$$
\dot Q_{\text{éch}} = \dot m_{\text{gaz}} \cdot c_p \cdot (T_{\text{gaz,in}} - T_{\text{gaz,out}})\cdot \varepsilon_{\text{hx}}
$$

avec :

* $\dot m_{\text{gaz}}$ : débit massique des gaz ;
* $c_p$ : chaleur massique ;
* $\varepsilon_{\text{hx}}$ : efficacité de l’échangeur.

### Flux thermique récupérable sur composants internes

$$
\dot Q_{\text{comp}}
$$

Il regroupe, selon conception :

* pertes Joule alternateur ;
* pertes électroniques ;
* pertes de conversion ;
* pertes de frottement ;
* chaleur des pièces proches thermiquement couplées.

### Flux thermique utile total

$$
\dot Q_{\text{utile}} = \dot Q_{\text{comb}} + \dot Q_{\text{éch}} + \dot Q_{\text{comp}}
$$

---

## 21.2 Bloc géométrique moteur complet

### Alésage

$$
B
$$

### Rayon piston

$$
R = \frac{B}{2}
$$

### Surface utile du piston

$$
A = \frac{\pi B^2}{4}
$$

### Course utile

$$
S
$$

### Volume balayé unitaire

$$
V_b = A \cdot S
$$

### Volume mort

$$
V_m
$$

Condition :

$$
V_m > 0
$$

### Volume total chambre

$$
V_t = V_b + V_m
$$

### Rapport volumétrique

$$
r_v = \frac{V_t}{V_m}
$$

---

## 21.3 Bloc pression interne réelle

### Pression minimale cycle

$$
p_{\min}
$$

### Pression maximale cycle

$$
p_{\max}
$$

### Pression moyenne effective

$$
p_{me}
$$

Condition :

$$
p_{\min} < p_{me} < p_{\max}
$$

### Rapport de pression

$$
r_p = \frac{p_{\max}}{p_{\min}}
$$

### Force instantanée appliquée au piston

$$
F = p \cdot A
$$

### Force maximale réelle

$$
F_{\max} = p_{\max}\cdot A
$$

---

## 21.4 Bloc matériaux

Le programme doit permettre de renseigner ou récupérer depuis une base matériaux :

* densité $\rho$ ;
* module de Young $E$ ;
* coefficient de Poisson $\nu$ ;
* limite élastique $R_e$ ;
* résistance à traction $R_m$ ;
* conductivité thermique $\lambda$ ;
* coefficient de dilatation $\alpha$ ;
* température maximale de service ;
* limite de fatigue si disponible.

Le programme ne doit jamais inventer une propriété absente ; il doit la marquer comme inconnue bloquante ou partielle.

---

## 21.5 Bloc électrique système

### Tension bus DC

$$
U_{\text{bus}}
$$

### Tension nominale cellule

$$
U_{\text{cell}}
$$

### Capacité unitaire cellule

$$
C_{\text{cell}}
$$

### Puissance électrique cible

$$
P_{\text{elec}}
$$

### Rendement chaîne électrique

$$
\eta_{\text{elec}}
$$

---

# 22. Cinématique complète réelle

## 22.1 Régime moteur

$$
N
$$

en tr/min.

## 22.2 Fréquence mécanique

$$
f = \frac{N}{60}
$$

## 22.3 Pulsation

$$
\omega = \frac{2\pi N}{60}
$$

## 22.4 Vitesse moyenne piston

$$
U_p = \frac{2SN}{60}
$$

Condition prudente prototype durable :

$$
U_p \leq U_{p,\max}
$$

avec typiquement :

$$
U_{p,\max} \approx 8\ \text{m/s}
$$

à affiner selon matériaux, lubrification, guidage et durée de vie visée.

## 22.5 Accélération maximale du piston

Approximation premier ordre :

$$
a_{\max} \approx \omega^2 \cdot r
$$

avec :

$$
r = \frac{S}{2}
$$

## 22.6 Effort inertiel alternatif

$$
F_i = m_{\text{alt}} \cdot a
$$

où $m_{\text{alt}}$ est la masse alternative équivalente.

## 22.7 Effort total transmis à la bielle

En première approche :

$$
F_{\text{bielle}} = F_{\text{gaz}} + F_i
$$

avec :

$$
F_{\text{gaz}} = p \cdot A
$$

---

# 23. Travail thermodynamique réel

## 23.1 Travail élémentaire du cycle

Expression générale :

$$
W = \oint p,dV
$$

## 23.2 Approximation de dimensionnement

Pour pré-dimensionnement :

$$
W_i = p_{me}\cdot V_b
$$

## 23.3 Puissance indiquée

$$
P_i = W_i \cdot f
$$

ou encore :

$$
P_i = p_{me}\cdot V_b \cdot \frac{N}{60}
$$

Pour $N_{cyl}$ cylindres :

$$
P_{i,\text{tot}} = N_{cyl}\cdot p_{me}\cdot V_b \cdot \frac{N}{60}
$$

## 23.4 Puissance mécanique arbre

$$
P_{\text{shaft}} = \eta_m \cdot P_i
$$

avec $\eta_m$ rendement mécanique interne.

## 23.5 Couple réel

$$
T = \frac{P_{\text{shaft}}}{\omega}
$$

---

# 24. Dimensionnement structurel durci

# 24.1 Arbres en torsion

Contrainte de cisaillement maximale pour arbre plein :

$$
\tau = \frac{16T}{\pi d^3}
$$

Diamètre minimal en torsion :

$$
d_{\min,\text{tors}} = \left(\frac{16T}{\pi \tau_{\text{adm}}}\right)^{1/3}
$$

avec :

$$
\tau_{\text{adm}} = \frac{R_e}{K_s \sqrt{3}}
$$

si critère de Von Mises.

---

## 24.2 Arbres en flexion

Contrainte de flexion :

$$
\sigma = \frac{32M}{\pi d^3}
$$

Diamètre minimal en flexion :

$$
d_{\min,\text{flex}} = \left(\frac{32M}{\pi \sigma_{\text{adm}}}\right)^{1/3}
$$

avec :

$$
\sigma_{\text{adm}} = \frac{R_e}{K_s}
$$

---

## 24.3 Vérification combinée Von Mises

$$
\sigma_{VM} = \sqrt{\sigma^2 + 3\tau^2}
$$

Condition :

$$
\sigma_{VM} < \sigma_{\text{adm}}
$$

---

## 24.4 Coefficient de sécurité mécanique

Le coefficient de sécurité global doit être choisi selon le niveau de maturité :

* calcul préliminaire : $K_s = 2$ ;
* prototype critique : $K_s = 2.5$ à $3$ ;
* pièce très sollicitée avec incertitudes : $K_s > 3$.

---

# 25. Bielle — version industrielle

## 25.1 Contrainte axiale

$$
\sigma = \frac{F_{\text{bielle}}}{A}
$$

## 25.2 Vérification flambage Euler

$$
F_{cr} = \frac{\pi^2 E I}{(K L)^2}
$$

Condition minimale :

$$
F_{\text{bielle}} < \frac{F_{cr}}{K_{fl}}
$$

avec $K_{fl}$ marge de sécurité en flambage.

## 25.3 Condition pratique de robustesse

À défaut de calcul plus fin :

$$
F_{\text{bielle}} < \frac{F_{cr}}{2}
$$

constitue une base prudente.

## 25.4 Vérification petite et grande tête

La pression projetée sur portées doit respecter :

$$
p = \frac{F}{d\cdot L}
$$

Condition :

$$
p < p_{\text{adm}}
$$

---

# 26. Batterie — intégration système complète

La batterie n’est pas conçue électrochimiquement par le programme.
Le programme doit seulement dimensionner **l’assemblage système** à partir de cellules du commerce.

## 26.1 Nombre de cellules en série

$$
N_s = \frac{U_{\text{bus}}}{U_{\text{cell}}}
$$

En pratique, il faut ensuite arrondir à un entier compatible avec la tension maximale et minimale du pack.

## 26.2 Nombre de cellules en parallèle

$$
N_p = \frac{C_{\text{tot}}}{C_{\text{cell}}}
$$

## 26.3 Nombre total de cellules

$$
N_{\text{cell,tot}} = N_s \cdot N_p
$$

## 26.4 Énergie pack

$$
E_{\text{pack}} = U_{\text{bus}}\cdot C_{\text{tot}}
$$

ou :

$$
E_{\text{pack}} = N_{\text{cell,tot}} \cdot E_{\text{cell}}
$$

## 26.5 Courant instantané maximal

$$
I_{\max} = \frac{P}{U}
$$

## 26.6 Vérification thermique pack

Pertes Joule :

$$
P_J = R_{\text{int}} I^2
$$

Le système doit vérifier :

* courant continu admissible ;
* courant de pointe admissible ;
* compatibilité BMS ;
* compatibilité refroidissement ;
* compatibilité tension alternateur / tension charge.

---

# 27. Contrainte majeure de l’architecture hybride

Si le moteur thermique de génération ne fonctionne que sur une fraction du temps total, la puissance instantanée demandée à la chaîne thermique augmente.

Si le moteur fonctionne sur une fraction $\beta$ du temps :

$$
0 < \beta \le 1
$$

alors la puissance instantanée nécessaire devient :

$$
P_{\text{inst}} = \frac{P_{\text{traction}} + P_{\text{recharge}}}{\beta}
$$

Cas particulier fondamental de ton architecture avec fonctionnement à 50 % du temps :

$$
\beta = 0.5
$$

donc :

$$
P_{\text{inst}} = 2,(P_{\text{traction}} + P_{\text{recharge}})
$$

Cette équation gouverne directement :

* la puissance thermique à produire ;
* le couple disponible ;
* le dimensionnement alternateur ;
* le refroidissement ;
* la section des arbres ;
* la tenue des roulements ;
* le pilotage énergétique.

---

# 28. Refroidissement industriel réel

## 28.1 Puissance thermique perdue

$$
P_{\text{pertes}} = P_{\text{entrée}} - P_{\text{utile}}
$$

## 28.2 Surface minimale d’échange

$$
A_{\text{éch}} = \frac{\dot Q}{h \Delta T}
$$

avec :

* $h$ : coefficient d’échange convectif ;
* $\Delta T$ : écart thermique moyen.

## 28.3 Ordres de grandeur usuels

Convection naturelle :

$$
h \approx 5\ \text{à}\ 15\ \text{W/m}^2\text{/K}
$$

Convection forcée air :

$$
h \approx 20\ \text{à}\ 300\ \text{W/m}^2\text{/K}
$$

Liquide forcé :

$$
h \gg 300\ \text{W/m}^2\text{/K}
$$

selon géométrie et débit.

## 28.4 Vérification thermique matériau

Condition générale :

$$
T_{\max,\text{pièce}} < T_{\text{service,max matériau}}
$$

---

# 29. Rendement global réaliste

## 29.1 Rendement thermique plafond théorique

$$
\eta_{\text{Carnot}} = 1 - \frac{T_c}{T_h}
$$

Ce rendement constitue uniquement une borne supérieure idéale.

## 29.2 Rendement réel système

$$
\eta_{\text{global}} = \eta_{th}\cdot \eta_m \cdot \eta_{gen}\cdot \eta_{elec}\cdot \eta_{charge}
$$

avec :

* $\eta_{th}$ : rendement thermo-mécanique ;
* $\eta_m$ : rendement mécanique ;
* $\eta_{gen}$ : rendement alternateur ;
* $\eta_{elec}$ : rendement électronique ;
* $\eta_{charge}$ : rendement charge batterie.

## 29.3 Domaine réaliste

Pour une architecture innovante mais encore non validée expérimentalement, il est rigoureux de considérer :

* plausible prudent : 20 % à 30 % ;
* ambitieux crédible : 30 % à 40 % ;
* au-delà : validation expérimentale forte indispensable.

Toute affirmation supérieure doit être prouvée par :

* banc instrumenté ;
* cartographie de rendement ;
* bilans thermiques ;
* mesures carburant ;
* mesures électriques stabilisées.

---

# 30. Tableau des coefficients obligatoires

Le programme doit intégrer des coefficients de sécurité ou de marge explicitement paramétrables.

## 30.1 Sécurité mécanique

$$
K_s = 2 \text{ à } 3
$$

## 30.2 Sécurité thermique

$$
K_t \approx 1.2 \text{ à } 1.5
$$

## 30.3 Sécurité électrique

$$
K_e \approx 1.1 \text{ à } 1.25
$$

## 30.4 Sécurité pression

$$
K_p \ge 1.5
$$

pour les éléments soumis à surpression, à compléter selon réglementation visée.

---

# 31. Contraintes de pilotage et de contrôle

Le programme et l’architecture système doivent intégrer un séquencement strict des états.

## 31.1 États minimaux

* purge ;
* fermé / stabilisation ;
* chauffe ;
* mode secours pneumatique ;
* production nominale ;
* arrêt contrôlé ;
* défaut sécurité.

## 31.2 Règles d’interdiction logique

Le système doit interdire :

* combustion pendant purge normale ;
* injection pneumatique hors fenêtre prévue ;
* recharge batterie hors limite BMS ;
* montée en température sans contrôle pression ;
* fonctionnement alternateur hors vitesse admissible.

## 31.3 Variables surveillées

* température chambre chaude ;
* température chambre froide ;
* pression chambre chaude ;
* pression chambre froide ;
* vitesse rotation ;
* courant charge ;
* tension bus ;
* température alternateur ;
* température électronique ;
* état soupapes.

---

# 32. Sorties obligatoires du programme

Le logiciel doit générer automatiquement un rapport de synthèse contenant au minimum :

## 32.1 Sorties géométriques

* alésage ;
* course ;
* cylindrée ;
* épaisseurs minimales ;
* diamètres d’arbres ;
* sections minimales ;
* volumes internes ;
* dimensions de portées.

## 32.2 Sorties mécaniques

* couple nominal ;
* couple maximal ;
* efforts sur piston ;
* efforts sur bielle ;
* contraintes arbre ;
* contraintes vilebrequin ;
* pression sur roulements ;
* pression sur coussinets.

## 32.3 Sorties thermiques

* flux thermique entrant ;
* flux récupérable ;
* pertes ;
* surface minimale d’échange ;
* température maximale estimée.

## 32.4 Sorties électriques

* puissance générée ;
* puissance utile ;
* courant bus ;
* tension bus ;
* architecture batterie série/parallèle ;
* compatibilité alternateur / batterie.

## 32.5 Sorties de validation

* marges de sécurité ;
* inconnues bloquantes ;
* inconnues partielles ;
* avertissements de cohérence ;
* niveau de validité du calcul.

---

# 33. Critères d’acceptation technique

Le système ne peut être considéré comme techniquement acceptable que si toutes les vérifications critiques sont satisfaites.

## 33.1 Critère mécanique

$$
\sigma_{VM} < \sigma_{\text{adm}}
$$

## 33.2 Critère flambage

$$
F_{\text{service}} < \frac{F_{cr}}{K_{fl}}
$$

## 33.3 Critère thermique

$$
T_{\max} < T_{\text{limite matériau}}
$$

## 33.4 Critère pression

$$
p_{\max} < p_{\text{admissible système}}
$$

## 33.5 Critère électrique

$$
I_{\text{charge}} < I_{\text{admissible BMS}}
$$

et :

$$
U_{\text{charge}} \in \text{plage admissible batterie}
$$

---

# 34. Données encore absentes d’un dossier industriel complet

Le dossier reste incomplet tant que les points suivants ne sont pas renseignés ou validés :

* loi réelle de combustion ;
* cinétique thermique transitoire ;
* coefficient réel d’échange côté chaud ;
* pertes réelles de purge ;
* rendement réel alternateur à la vitesse visée ;
* spectre vibratoire ;
* fatigue haut nombre de cycles ;
* tolérances de fabrication ;
* jeux fonctionnels chaud / froid ;
* états de surface ;
* stabilité du contrôle.

---

# 35. Contenu attendu d’un dossier V2 réellement industrialisable

La version suivante du dossier devra comprendre :

## 35.1 Partie mécanique détaillée

* chaînes de cotes ;
* tolérances ISO ;
* états de surface ;
* matériaux candidats comparés ;
* tableau des masses ;
* inerties tournantes ;
* cartes de contraintes.

## 35.2 Partie thermique détaillée

* bilans stationnaires ;
* bilans transitoires ;
* échangeur gaz / masse chaude ;
* temps de montée en température ;
* refroidissement alternateur et électronique.

## 35.3 Partie électrique détaillée

* cartes alternateur ;
* rendement charge ;
* limite courant ;
* stratégie recharge ;
* architecture bus ;
* protections.

## 35.4 Partie commande

* logique d’état ;
* capteurs ;
* actionneurs ;
* modes dégradés ;
* repli sécurité ;
* arrêt d’urgence.

## 35.5 Partie validation expérimentale

* plan d’essais ;
* instrumentation ;
* protocole d’acquisition ;
* critères succès / échec ;
* corrélation calcul / essai.


---

# 37. Batterie de traction et de stockage — intégration système complète

Dans le cadre du système STHO-ME, la batterie n’est pas conçue au niveau électrochimique interne.
Le programme ne dimensionne pas la chimie de l’accumulateur, mais il doit dimensionner **son intégration système**, à partir de cellules lithium-ion du commerce.

La batterie constitue :

* une réserve d’énergie ;
* un tampon de puissance ;
* un organe d’absorption des transitoires ;
* un élément de stabilisation du fonctionnement global ;
* un sous-système critique pour la sûreté électrique et thermique.

Le programme doit donc calculer :

* l’énergie utile à embarquer ;
* la puissance instantanée à fournir et à absorber ;
* la tension bus visée ;
* le nombre de cellules en série ;
* le nombre de cellules en parallèle ;
* la masse batterie ;
* le volume batterie ;
* les courants maximaux ;
* les pertes Joule ;
* les contraintes thermiques ;
* la compatibilité avec BMS, alternateur et électronique de puissance.

---

## 37.1 Rôle fonctionnel de la batterie dans l’architecture STHO-ME

La batterie ne doit pas être considérée comme un simple réservoir d’énergie, mais comme un organe actif du fonctionnement hybride.

Ses fonctions principales sont :

### FB1 — Fournir l’énergie de traction ou d’usage

La batterie doit pouvoir alimenter les charges lorsque le générateur thermo-hybride n’est pas en fonctionnement ou lorsque la demande instantanée dépasse la puissance générée.

### FB2 — Absorber les variations rapides de puissance

La batterie doit amortir les appels de courant transitoires, les crêtes de puissance et les variations de charge.

### FB3 — Permettre le fonctionnement intermittent du générateur

Le STHO-ME pouvant fonctionner par séquences plutôt qu’en continu, la batterie doit assurer la continuité énergétique entre les phases de production.

### FB4 — Recevoir l’énergie de recharge

La batterie doit accepter une recharge pilotée par l’alternateur dans les limites imposées par la chimie, le BMS, la température et la stratégie énergétique.

### FB5 — Participer à la sûreté du système

La batterie, via son BMS et son architecture physique, doit contribuer à la limitation des risques :

* surtension ;
* sous-tension ;
* surintensité ;
* surcharge ;
* surchauffe ;
* emballement thermique.

---

# 38. Grandeurs de base à définir pour la batterie

Le programme doit exiger ou calculer les grandeurs suivantes.

## 38.1 Tension nominale cellule

$$
U_{\text{cell,nom}}
$$

## 38.2 Tension maximale cellule

$$
U_{\text{cell,max}}
$$

## 38.3 Tension minimale cellule

$$
U_{\text{cell,min}}
$$

## 38.4 Capacité unitaire cellule

$$
C_{\text{cell}}
$$

en Ah.

## 38.5 Énergie unitaire cellule

$$
E_{\text{cell}} = U_{\text{cell,nom}} \cdot C_{\text{cell}}
$$

## 38.6 Masse unitaire cellule

$$
m_{\text{cell}}
$$

## 38.7 Résistance interne unitaire cellule

$$
R_{\text{cell}}
$$

## 38.8 Courant continu maximal cellule

$$
I_{\text{cell,max,cont}}
$$

## 38.9 Courant de pointe maximal cellule

$$
I_{\text{cell,max,peak}}
$$

## 38.10 Température minimale de fonctionnement

$$
T_{\text{cell,min}}
$$

## 38.11 Température maximale de fonctionnement

$$
T_{\text{cell,max}}
$$

---

# 39. Dimensionnement tension du pack

Le choix de la tension bus est structurant car il conditionne :

* le courant ;
* la section des câbles ;
* les pertes Joule ;
* la compatibilité alternateur ;
* la compatibilité électronique de puissance ;
* la sécurité électrique.

## 39.1 Tension nominale du pack

$$
U_{\text{pack,nom}} = N_s \cdot U_{\text{cell,nom}}
$$

où :

* $N_s$ = nombre de cellules en série.

## 39.2 Tension maximale du pack

$$
U_{\text{pack,max}} = N_s \cdot U_{\text{cell,max}}
$$

## 39.3 Tension minimale du pack

$$
U_{\text{pack,min}} = N_s \cdot U_{\text{cell,min}}
$$

## 39.4 Nombre de cellules en série

À partir d’une tension bus cible :

$$
N_s = \frac{U_{\text{bus,cible}}}{U_{\text{cell,nom}}}
$$

En pratique :

$$
N_s = \text{arrondi entier compatible}
$$

avec vérification sur la plage réelle :

$$
U_{\text{pack,min}} \le U_{\text{bus,fonctionnel}} \le U_{\text{pack,max}}
$$

---

# 40. Dimensionnement capacité et énergie du pack

## 40.1 Capacité totale du pack

Pour des branches parallèles :

$$
C_{\text{pack}} = N_p \cdot C_{\text{cell}}
$$

où :

* $N_p$ = nombre de cellules en parallèle.

## 40.2 Énergie nominale du pack

$$
E_{\text{pack}} = U_{\text{pack,nom}} \cdot C_{\text{pack}}
$$

## 40.3 Énergie utile réellement exploitable

Le pack ne doit pas être utilisé sur 100 % de sa capacité théorique.
On introduit une profondeur de décharge admissible :

$$
DoD
$$

Alors :

$$
E_{\text{utile}} = E_{\text{pack}} \cdot DoD
$$

avec en pratique :

* usage conservateur : $DoD = 0.7$ à $0.8$ ;
* usage plus agressif : à valider selon cellules choisies.

## 40.4 Nombre de cellules en parallèle

$$
N_p = \frac{C_{\text{pack}}}{C_{\text{cell}}}
$$

ou encore, à partir d’une énergie cible :

$$
N_p = \frac{E_{\text{utile,cible}}}{N_s \cdot U_{\text{cell,nom}} \cdot C_{\text{cell}} \cdot DoD}
$$

---

# 41. Nombre total de cellules, masse et volume batterie

## 41.1 Nombre total de cellules

$$
N_{\text{tot}} = N_s \cdot N_p
$$

## 41.2 Masse brute des cellules

$$
m_{\text{cellules}} = N_{\text{tot}} \cdot m_{\text{cell}}
$$

## 41.3 Masse pack estimée

La masse totale batterie n’est pas limitée à la masse des cellules.
Il faut intégrer :

* interconnexions ;
* structure ;
* enveloppe ;
* refroidissement ;
* capteurs ;
* BMS ;
* protections.

On introduit un coefficient d’intégration :

$$
K_{m,\text{pack}} > 1
$$

Alors :

$$
m_{\text{pack}} = K_{m,\text{pack}} \cdot m_{\text{cellules}}
$$

## 41.4 Volume pack estimé

De même :

$$
V_{\text{pack}} = K_{V,\text{pack}} \cdot N_{\text{tot}} \cdot V_{\text{cell}}
$$

où $K_{V,\text{pack}}$ tient compte de l’intégration réelle.

---

# 42. Courants et puissances batterie

## 42.1 Courant demandé par la charge

$$
I = \frac{P}{U}
$$

En régime pack :

$$
I_{\text{pack}} = \frac{P_{\text{pack}}}{U_{\text{pack}}}
$$

## 42.2 Courant par cellule

Dans une architecture parallèle idéale :

$$
I_{\text{cell}} = \frac{I_{\text{pack}}}{N_p}
$$

## 42.3 Condition de tenue en courant continu

$$
I_{\text{cell}} \le I_{\text{cell,max,cont}}
$$

## 42.4 Condition de tenue en pointe

$$
I_{\text{cell,peak}} \le I_{\text{cell,max,peak}}
$$

## 42.5 Puissance maximale délivrable par le pack

$$
P_{\text{pack,max}} = U_{\text{pack}} \cdot I_{\text{pack,max}}
$$

avec :

$$
I_{\text{pack,max}} = N_p \cdot I_{\text{cell,max}}
$$

---

# 43. Contraintes spécifiques de l’architecture hybride STHO-ME

Dans ton architecture, le générateur peut ne fonctionner qu’une fraction du temps total.
La batterie doit donc couvrir :

* les phases sans génération ;
* les transitoires ;
* les appels de puissance ;
* les écarts entre production moyenne et demande instantanée.

## 43.1 Puissance instantanée à fournir ou absorber

Si le générateur fonctionne sur une fraction $\beta$ du temps :

$$
P_{\text{gén,inst}} = \frac{P_{\text{usage}} + P_{\text{recharge}}}{\beta}
$$

Pour $\beta = 0.5$ :

$$
P_{\text{gén,inst}} = 2,(P_{\text{usage}} + P_{\text{recharge}})
$$

La batterie doit alors être dimensionnée pour :

* accepter cette recharge instantanée quand le générateur fonctionne ;
* fournir seule les besoins hors phase de génération.

## 43.2 Énergie minimale tampon

Si la batterie doit tenir une durée autonome sans génération :

$$
t_{\text{aut}}
$$

alors :

$$
E_{\text{tampon}} = P_{\text{usage,moy}} \cdot t_{\text{aut}}
$$

En tenant compte du rendement électrique global :

$$
E_{\text{tampon,réel}} = \frac{P_{\text{usage,moy}} \cdot t_{\text{aut}}}{\eta_{\text{elec}}}
$$

---

# 44. Pertes Joule et échauffement batterie

## 44.1 Résistance interne équivalente du pack

Pour une architecture simple avec $N_s$ séries et $N_p$ parallèles :

$$
R_{\text{pack}} = N_s \cdot \frac{R_{\text{cell}}}{N_p}
$$

## 44.2 Pertes Joule du pack

$$
P_J = R_{\text{pack}} \cdot I_{\text{pack}}^2
$$

## 44.3 Pertes Joule par cellule

$$
P_{J,\text{cell}} = R_{\text{cell}} \cdot I_{\text{cell}}^2
$$

## 44.4 Condition thermique générale

La température du pack doit vérifier :

$$
T_{\text{pack}} < T_{\text{cell,max}}
$$

et :

$$
T_{\text{pack}} > T_{\text{cell,min}}
$$

en fonctionnement utile.

## 44.5 Besoin de refroidissement batterie

Si les pertes sont significatives :

$$
\dot Q_{\text{batt}} \approx P_J
$$

et la surface ou le circuit de refroidissement doit satisfaire :

$$
A_{\text{éch,batt}} \ge \frac{\dot Q_{\text{batt}}}{h \Delta T}
$$

---

# 45. Rendement batterie et rendement de charge

## 45.1 Rendement de décharge

$$
\eta_{\text{décharge}} = \frac{E_{\text{utile,délivrée}}}{E_{\text{extraite chimiquement}}}
$$

## 45.2 Rendement de charge

$$
\eta_{\text{charge}} = \frac{E_{\text{stockée}}}{E_{\text{reçue}}}
$$

## 45.3 Rendement aller-retour

$$
\eta_{\text{RT}} = \eta_{\text{charge}} \cdot \eta_{\text{décharge}}
$$

Le programme doit intégrer ce rendement dans les bilans énergétiques complets.

---

# 46. État de charge, fenêtre utile et stratégie d’exploitation

La batterie ne doit pas être exploitée entre 0 % et 100 % de SOC en usage normal, sauf justification explicite.

## 46.1 État de charge

$$
SOC = \frac{Q_{\text{restante}}}{Q_{\text{nominale}}}
$$

## 46.2 Fenêtre utile recommandée

Le programme doit permettre de définir :

* $SOC_{\min}$ ;
* $SOC_{\max}$.

L’énergie utile devient alors :

$$
E_{\text{utile}} = E_{\text{pack}} \cdot (SOC_{\max} - SOC_{\min})
$$

## 46.3 Conséquence système

Plus la fenêtre SOC utile est réduite :

* meilleure durée de vie ;
* meilleure sécurité ;
* mais énergie réellement disponible plus faible.

---

# 47. BMS — fonctions minimales obligatoires

Le BMS doit être traité comme un organe obligatoire du système.

## 47.1 Fonctions minimales

Le BMS doit assurer :

* mesure tension cellule ou groupe ;
* mesure courant pack ;
* estimation SOC ;
* protection surtension ;
* protection sous-tension ;
* protection surintensité ;
* protection température ;
* équilibrage ;
* coupure sécurité.

## 47.2 Condition de compatibilité système

Le programme doit vérifier :

$$
I_{\text{charge}} < I_{\text{BMS,max,charge}}
$$

$$
I_{\text{décharge}} < I_{\text{BMS,max,décharge}}
$$

$$
U_{\text{pack,max}} < U_{\text{BMS,max}}
$$

---

# 48. Compatibilité batterie / alternateur / électronique de puissance

Le dimensionnement batterie ne peut pas être isolé du reste du système.

## 48.1 Compatibilité tension de charge

La tension de sortie régulée doit vérifier :

$$
U_{\text{charge}} \le U_{\text{pack,max autorisé}}
$$

## 48.2 Compatibilité courant de charge

$$
I_{\text{charge}} \le I_{\text{charge,max pack}}
$$

## 48.3 Compatibilité puissance instantanée

$$
P_{\text{charge}} = U_{\text{pack}} \cdot I_{\text{charge}}
$$

Le système générateur ne doit pas imposer à la batterie une puissance de charge supérieure à ce qu’elle peut absorber durablement.

---

# 49. Contraintes de sécurité batterie

## 49.1 Contraintes électriques

Le système doit éviter :

* court-circuit ;
* inversion polarité ;
* surtension ;
* sous-tension ;
* surintensité.

## 49.2 Contraintes thermiques

Le système doit éviter :

* points chauds locaux ;
* gradient thermique excessif ;
* absence de dissipation ;
* recharge à température inadaptée.

## 49.3 Contraintes mécaniques

Le pack doit résister :

* aux vibrations ;
* aux chocs ;
* aux efforts inertiels ;
* aux efforts de montage ;
* à la dilatation différentielle.

## 49.4 Contraintes d’intégration

Le pack doit rester compatible avec :

* volume disponible ;
* masse admissible ;
* refroidissement disponible ;
* accessibilité maintenance ;
* protection incendie / isolement.

---

# 50. Critères d’acceptation technique de la batterie intégrée

La batterie intégrée au système ne peut être considérée conforme que si :

## 50.1 Critère énergétique

$$
E_{\text{utile}} \ge E_{\text{besoin mission}}
$$

## 50.2 Critère puissance

$$
P_{\text{pack,max}} \ge P_{\text{appel,max}}
$$

## 50.3 Critère courant cellule

$$
I_{\text{cell}} \le I_{\text{cell,max admissible}}
$$

## 50.4 Critère thermique

$$
T_{\text{pack,max}} < T_{\text{cell,max}}
$$

## 50.5 Critère tension

$$
U_{\text{pack,min}} \le U_{\text{système requis}} \le U_{\text{pack,max}}
$$

## 50.6 Critère masse

$$
m_{\text{pack}} \le m_{\text{pack,max admissible}}
$$

---

# 51. Sorties minimales du programme sur la batterie

Le logiciel doit fournir automatiquement :

* type de cellule utilisé en entrée ;
* nombre de cellules en série ;
* nombre de cellules en parallèle ;
* nombre total de cellules ;
* tension nominale pack ;
* tension max pack ;
* tension min pack ;
* capacité pack ;
* énergie pack ;
* énergie utile ;
* courant max demandé ;
* courant par cellule ;
* pertes Joule ;
* masse estimée pack ;
* volume estimé pack ;
* avertissements BMS ;
* avertissements thermiques ;
* avertissements de compatibilité charge.

---

# 52. Hypothèses et limites de validité de cette modélisation batterie

Cette modélisation est valide pour un **pré-dimensionnement système**.
Elle ne remplace pas :

* une modélisation électrochimique fine ;
* une modélisation thermique 3D du pack ;
* une étude détaillée d’équilibrage ;
* une étude de sûreté batterie complète ;
* une validation expérimentale sur cellules réelles.

Le programme doit donc explicitement distinguer :

* les calculs fermes ;
* les estimations ;
* les inconnues bloquantes ;
* les inconnues à valider par essais.



---

# 53. Alternateur — intégration système complète

Dans le cadre du système STHO-ME, l’alternateur est l’organe de conversion entre la puissance mécanique fournie par la chaîne thermo-oscillatoire et la puissance électrique utile au bus continu, à la batterie et aux auxiliaires.

L’alternateur ne doit pas être considéré comme un composant isolé, mais comme un sous-système couplé :

* à la cinématique du vilebrequin ;
* au régime réel de fonctionnement ;
* au couple disponible ;
* à la stratégie de recharge ;
* à la batterie ;
* à l’électronique de conversion ;
* au refroidissement ;
* au pilotage énergétique global.

Le programme doit donc dimensionner ou vérifier :

* la puissance électrique utile ;
* la puissance mécanique à fournir ;
* le couple résistant induit ;
* la vitesse de rotation de fonctionnement ;
* la plage de rendement ;
* les pertes ;
* les contraintes thermiques ;
* la compatibilité avec le bus DC et la batterie ;
* la compatibilité avec le mode de fonctionnement intermittent du STHO-ME.

---

# 54. Rôle fonctionnel de l’alternateur dans l’architecture STHO-ME

## FA1 — Convertir la puissance mécanique en puissance électrique

L’alternateur doit convertir une puissance mécanique issue de l’arbre en puissance électrique exploitable.

## FA2 — Alimenter le bus électrique

L’alternateur doit permettre l’alimentation du bus continu ou du système de conversion.

## FA3 — Recharger la batterie

L’alternateur doit fournir une puissance suffisante pour assurer la recharge dans les limites imposées par la batterie et le BMS.

## FA4 — Stabiliser la chaîne énergétique

Par l’intermédiaire de l’électronique de puissance, l’alternateur doit permettre une gestion stable de la puissance électrique malgré les variations mécaniques.

## FA5 — Limiter les pertes et l’échauffement

L’alternateur doit fonctionner dans une plage de vitesse et de charge compatible avec son rendement et sa tenue thermique.

---

# 55. Grandeurs fondamentales de l’alternateur

Le programme doit permettre d’entrer, d’estimer ou de vérifier les grandeurs suivantes.

## 55.1 Puissance électrique nominale utile

$$
P_{\text{elec,nom}}
$$

## 55.2 Puissance électrique maximale

$$
P_{\text{elec,max}}
$$

## 55.3 Tension de sortie nominale

$$
U_{\text{alt}}
$$

## 55.4 Courant nominal

$$
I_{\text{alt,nom}}
$$

## 55.5 Courant maximal

$$
I_{\text{alt,max}}
$$

## 55.6 Rendement alternateur

$$
\eta_{\text{gen}}
$$

## 55.7 Vitesse de rotation nominale

$$
N_{\text{alt,nom}}
$$

## 55.8 Vitesse de rotation minimale utile

$$
N_{\text{alt,min}}
$$

## 55.9 Vitesse de rotation maximale admissible

$$
N_{\text{alt,max}}
$$

## 55.10 Couple résistant alternateur

$$
T_{\text{alt}}
$$

## 55.11 Température maximale admissible alternateur

$$
T_{\text{alt,max}}
$$

---

# 56. Chaîne de conversion énergétique de l’alternateur

La chaîne de conversion complète s’écrit :

$$
P_{\text{méc,entrée}} \rightarrow P_{\text{elec,brute}} \rightarrow P_{\text{elec,convertie}} \rightarrow P_{\text{bus}} \rightarrow P_{\text{charge}}
$$

avec des pertes à chaque étage.

## 56.1 Puissance électrique brute générée

$$
P_{\text{elec,brute}} = \eta_{\text{gen}} \cdot P_{\text{méc,entrée}}
$$

## 56.2 Puissance disponible après conversion électronique

Si l’électronique de redressement et de conversion a un rendement $\eta_{\text{conv}}$ :

$$
P_{\text{bus}} = \eta_{\text{conv}} \cdot P_{\text{elec,brute}}
$$

## 56.3 Puissance utile réellement disponible pour la batterie ou les charges

$$
P_{\text{utile}} = \eta_{\text{charge}} \cdot P_{\text{bus}}
$$

Donc :

$$
P_{\text{utile}} = \eta_{\text{gen}} \cdot \eta_{\text{conv}} \cdot \eta_{\text{charge}} \cdot P_{\text{méc,entrée}}
$$

---

# 57. Puissance mécanique requise à l’arbre

L’alternateur impose une puissance mécanique minimale à fournir.

## 57.1 Cas général

$$
P_{\text{méc,req}} = \frac{P_{\text{utile}}}{\eta_{\text{gen}} \cdot \eta_{\text{conv}} \cdot \eta_{\text{charge}}}
$$

## 57.2 Cas de simple alimentation électrique sans charge batterie

$$
P_{\text{méc,req}} = \frac{P_{\text{bus}}}{\eta_{\text{gen}} \cdot \eta_{\text{conv}}}
$$

## 57.3 Cas nominal du STHO-ME

Si l’alternateur doit à la fois :

* alimenter la charge utile ;
* et recharger la batterie ;

alors :

$$
P_{\text{utile,total}} = P_{\text{usage}} + P_{\text{recharge}}
$$

et donc :

$$
P_{\text{méc,req}} = \frac{P_{\text{usage}} + P_{\text{recharge}}}{\eta_{\text{gen}} \cdot \eta_{\text{conv}} \cdot \eta_{\text{charge}}}
$$

---

# 58. Couple résistant imposé par l’alternateur

Le couple résistant est une grandeur essentielle car il charge directement le vilebrequin, l’arbre et la chaîne mécanique.

## 58.1 Vitesse angulaire

$$
\omega_{\text{alt}} = \frac{2\pi N_{\text{alt}}}{60}
$$

## 58.2 Couple résistant alternateur

$$
T_{\text{alt}} = \frac{P_{\text{méc,req}}}{\omega_{\text{alt}}}
$$

## 58.3 Influence directe sur la mécanique système

Plus $N_{\text{alt}}$ est faible, plus le couple résistant demandé est élevé à puissance constante.
Cette relation est fondamentale dans le choix :

* du rapport de transmission ;
* du régime moteur ;
* de la géométrie arbre / clavette / roulements ;
* de l’inertie nécessaire au lissage.

---

# 59. Compatibilité vitesse entre alternateur et moteur

L’alternateur n’est généralement pas libre de fonctionner à n’importe quelle vitesse.
Le programme doit donc vérifier la compatibilité entre :

* le régime du moteur thermo-hybride ;
* le régime de l’arbre ;
* le régime optimal de l’alternateur ;
* le rapport de transmission éventuel.

## 59.1 Cas entraînement direct

Si l’alternateur est directement accouplé à l’arbre :

$$
N_{\text{alt}} = N_{\text{arbre}}
$$

## 59.2 Cas entraînement par rapport mécanique

Si un rapport mécanique $i$ est utilisé :

$$
N_{\text{alt}} = i \cdot N_{\text{arbre}}
$$

## 59.3 Condition de fonctionnement utile

$$
N_{\text{alt,min}} \le N_{\text{alt}} \le N_{\text{alt,max}}
$$

## 59.4 Condition de fonctionnement nominal optimisé

L’idéal est que le point nominal de fonctionnement du STHO-ME amène l’alternateur dans une zone où :

* le rendement est élevé ;
* la tension régulée est stable ;
* l’échauffement reste maîtrisé.

---

# 60. Tension, courant et puissance électrique de sortie

## 60.1 Relation de base

$$
P_{\text{elec}} = U_{\text{alt}} \cdot I_{\text{alt}}
$$

Pour un système alternatif triphasé, cette expression doit être adaptée à la topologie réelle, mais le programme peut travailler à ce niveau en puissance équivalente utile.

## 60.2 Courant nominal

$$
I_{\text{alt,nom}} = \frac{P_{\text{elec,nom}}}{U_{\text{alt}}}
$$

## 60.3 Courant maximal

$$
I_{\text{alt,max}} = \frac{P_{\text{elec,max}}}{U_{\text{alt}}}
$$

## 60.4 Vérification de compatibilité conversion

Le système doit vérifier :

$$
U_{\text{alt}} \rightarrow U_{\text{bus}}
$$

via l’électronique de redressement et de régulation, avec maintien d’une plage exploitable pour la charge batterie et les auxiliaires.

---

# 61. Pertes alternateur

L’alternateur dissipe une partie de la puissance mécanique en pertes thermiques.

## 61.1 Pertes globales

$$
P_{\text{pertes,alt}} = P_{\text{méc,entrée}} - P_{\text{elec,brute}}
$$

ou encore :

$$
P_{\text{pertes,alt}} = P_{\text{méc,entrée}} \cdot (1-\eta_{\text{gen}})
$$

## 61.2 Origine physique des pertes

Les pertes peuvent être décomposées en :

* pertes cuivre ;
* pertes fer ;
* pertes mécaniques ;
* pertes ventilation ;
* pertes électroniques internes éventuelles.

## 61.3 Modèle simplifié exploitable par le programme

À défaut de modèle détaillé :

$$
P_{\text{pertes,alt}} = P_{\text{fixes}} + P_{\text{variables}}
$$

avec :

$$
P_{\text{variables}} \propto I^2
$$

si on veut intégrer une première dépendance au courant.

---

# 62. Contraintes thermiques alternateur

## 62.1 Bilan thermique simplifié

En première approche, la puissance thermique à dissiper vaut :

$$
\dot Q_{\text{alt}} \approx P_{\text{pertes,alt}}
$$

## 62.2 Surface d’échange minimale

$$
A_{\text{éch,alt}} \ge \frac{\dot Q_{\text{alt}}}{h \Delta T}
$$

## 62.3 Condition thermique générale

$$
T_{\text{alt}} < T_{\text{alt,max}}
$$

## 62.4 Refroidissement

Le programme doit permettre de distinguer :

* convection naturelle ;
* convection forcée air ;
* refroidissement liquide ;
* couplage thermique avec masse métallique du système.

## 62.5 Impact sur le rendement

L’échauffement excessif peut entraîner :

* baisse du rendement ;
* dégradation isolation ;
* dérive électrique ;
* réduction durée de vie.

---

# 63. Compatibilité alternateur / batterie / BMS

L’alternateur ne doit jamais être dimensionné indépendamment de la batterie et du système de charge.

## 63.1 Compatibilité de tension

La tension de sortie régulée du système doit satisfaire :

$$
U_{\text{charge}} \le U_{\text{pack,max admissible}}
$$

et :

$$
U_{\text{charge}} \ge U_{\text{niveau requis pour recharge}}
$$

## 63.2 Compatibilité de courant

$$
I_{\text{charge}} \le I_{\text{pack,max,charge}}
$$

et :

$$
I_{\text{charge}} \le I_{\text{BMS,max,charge}}
$$

## 63.3 Compatibilité de puissance

$$
P_{\text{charge}} = U_{\text{pack}} \cdot I_{\text{charge}}
$$

L’alternateur ne doit pas imposer un régime de charge impossible à absorber thermiquement ou électriquement par la batterie.

---

# 64. Cas particulier du fonctionnement intermittent du STHO-ME

Dans l’architecture STHO-ME, le générateur peut ne pas fonctionner en permanence.
Cela modifie fortement la contrainte alternateur.

## 64.1 Puissance électrique instantanée imposée

Si le générateur ne fonctionne que sur une fraction $\beta$ du temps :

$$
P_{\text{alt,inst}} = \frac{P_{\text{usage}} + P_{\text{recharge}}}{\beta}
$$

Cas particulier pour :

$$
\beta = 0.5
$$

alors :

$$
P_{\text{alt,inst}} = 2,(P_{\text{usage}} + P_{\text{recharge}})
$$

## 64.2 Conséquences directes

L’alternateur doit alors être vérifié sur :

* puissance de pointe ;
* courant de pointe ;
* couple résistant de pointe ;
* échauffement de pointe ;
* vitesse nécessaire ;
* compatibilité avec la chaîne mécanique.

---

# 65. Stratégie de dimensionnement de l’alternateur

Le programme doit permettre deux approches.

## 65.1 Approche par puissance cible

Entrée :

$$
P_{\text{elec,cible}}
$$

Le programme calcule :

* puissance mécanique requise ;
* couple résistant ;
* courant nominal ;
* compatibilité thermique.

## 65.2 Approche par alternateur existant

Entrées :

* puissance nominale ;
* rendement ;
* plage de vitesse ;
* tension ;
* courant ;
* masse.

Le programme vérifie :

* compatibilité avec le moteur ;
* compatibilité avec le bus ;
* compatibilité avec la batterie ;
* compatibilité avec le refroidissement.

---

# 66. Masse et intégration physique de l’alternateur

Le programme doit intégrer l’effet de l’alternateur sur :

* masse totale système ;
* encombrement ;
* inertie tournante éventuelle ;
* porte-à-faux ;
* montage mécanique ;
* refroidissement ;
* maintenance.

## 66.1 Masse alternateur

$$
m_{\text{alt}}
$$

## 66.2 Densité de puissance massique

$$
\rho_{P,m} = \frac{P_{\text{elec,nom}}}{m_{\text{alt}}}
$$

## 66.3 Densité de puissance volumique

$$
\rho_{P,V} = \frac{P_{\text{elec,nom}}}{V_{\text{alt}}}
$$

Ces ratios sont utiles pour comparer plusieurs solutions.

---

# 67. Contraintes mécaniques induites par l’alternateur

## 67.1 Effort tangent équivalent sur arbre

Si le couple est transmis sur un rayon effectif $r$ :

$$
F_t = \frac{T_{\text{alt}}}{r}
$$

## 67.2 Vérification clavette / accouplement

L’organe de transmission entre arbre et alternateur doit vérifier :

* cisaillement ;
* pression de contact ;
* tenue fatigue ;
* absence de glissement.

## 67.3 Vérification roulements support alternateur

Les roulements supportant l’alternateur ou l’arbre associé doivent être vérifiés en charge radiale et éventuellement axiale selon l’architecture.

---

# 68. Rendement réel de la chaîne alternateur

Le rendement global de conversion côté génération doit être traité comme un produit de rendements.

## 68.1 Rendement partiel

$$
\eta_{\text{génération}} = \eta_{\text{gen}} \cdot \eta_{\text{conv}}
$$

## 68.2 Rendement jusqu’à la batterie

$$
\eta_{\text{gén}\rightarrow \text{pack}} = \eta_{\text{gen}} \cdot \eta_{\text{conv}} \cdot \eta_{\text{charge}}
$$

## 68.3 Conséquence de calcul

Pour délivrer une puissance utile donnée, la chaîne mécanique doit toujours fournir davantage :

$$
P_{\text{méc,req}} > P_{\text{utile}}
$$

Cette différence doit être comptabilisée dans le bilan carburant, le bilan thermique et le dimensionnement mécanique.

---

# 69. Critères d’acceptation technique de l’alternateur intégré

L’alternateur ne peut être considéré comme conforme que si tous les critères suivants sont satisfaits.

## 69.1 Critère puissance

$$
P_{\text{elec,max}} \ge P_{\text{usage}} + P_{\text{recharge}}
$$

ou, en fonctionnement intermittent, sur la puissance instantanée imposée.

## 69.2 Critère couple

$$
T_{\text{moteur disponible}} \ge T_{\text{alt}} + T_{\text{autres charges}}
$$

## 69.3 Critère vitesse

$$
N_{\text{alt,min}} \le N_{\text{alt,fonctionnement}} \le N_{\text{alt,max}}
$$

## 69.4 Critère thermique

$$
T_{\text{alt}} < T_{\text{alt,max}}
$$

## 69.5 Critère électrique

$$
U_{\text{sortie}} \in \text{plage compatible bus et batterie}
$$

et :

$$
I_{\text{sortie}} \le I_{\text{alt,max}}
$$

## 69.6 Critère rendement

Le point de fonctionnement retenu doit se situer dans une zone de rendement acceptable par rapport à l’objectif système.

---

# 70. Sorties minimales du programme sur l’alternateur

Le logiciel doit générer automatiquement :

* puissance utile requise ;
* puissance mécanique requise ;
* vitesse alternateur ;
* couple résistant alternateur ;
* courant nominal ;
* courant maximal ;
* tension de sortie ;
* rendement alternateur ;
* rendement chaîne génération ;
* pertes thermiques ;
* puissance à dissiper ;
* avertissements de compatibilité vitesse ;
* avertissements de compatibilité batterie ;
* avertissements de compatibilité BMS ;
* avertissements thermiques ;
* niveau de validité du calcul.

---

# 71. Hypothèses et limites de validité de cette modélisation alternateur

La présente modélisation est valable pour un pré-dimensionnement système.
Elle ne remplace pas :

* les courbes constructeur ;
* les cartes rendement / vitesse / charge ;
* la modélisation électromagnétique détaillée ;
* l’étude d’isolation ;
* l’étude vibratoire rotor ;
* la validation thermique réelle.

Le programme doit distinguer explicitement :

* les calculs fermes ;
* les estimations de pré-dimensionnement ;
* les données imposées par constructeur ;
* les inconnues bloquantes ;
* les inconnues nécessitant essais.


---

# 72. Électronique de puissance, redressement et bus continu — intégration système complète

Dans l’architecture STHO-ME, l’électronique de puissance constitue le sous-système d’interface entre :

* l’alternateur ;
* le bus continu ;
* la batterie ;
* les charges auxiliaires ;
* les éventuels convertisseurs secondaires.

Elle ne doit pas être considérée comme un simple accessoire électrique, mais comme un organe structurant du système énergétique, car elle conditionne :

* la stabilité de la tension ;
* la qualité de conversion ;
* la recharge batterie ;
* la protection des composants ;
* le rendement électrique global ;
* le comportement transitoire du système.

Le programme doit donc permettre de **dimensionner ou vérifier** :

* la tension du bus continu ;
* le courant du bus ;
* la puissance traversant les étages de conversion ;
* les pertes de conversion ;
* les besoins de filtrage ;
* les contraintes thermiques ;
* la compatibilité tension/courant avec la batterie et l’alternateur ;
* les limites de fonctionnement des semi-conducteurs ;
* la logique de protection.

---

# 73. Rôle fonctionnel de l’électronique de puissance dans le STHO-ME

## FE1 — Redresser la puissance issue de l’alternateur

Si l’alternateur fournit une tension alternative, l’électronique doit convertir cette tension en tension continue exploitable.

## FE2 — Stabiliser le bus continu

Le bus DC doit rester dans une plage admissible malgré :

* les variations de régime alternateur ;
* les variations de charge ;
* les séquences intermittentes de production ;
* les transitoires batterie.

## FE3 — Adapter la puissance à la batterie

Le système doit convertir la puissance disponible sur le bus en une puissance de charge compatible avec :

* la tension batterie ;
* le courant admissible ;
* le BMS ;
* la stratégie énergétique.

## FE4 — Alimenter les auxiliaires

L’électronique doit permettre l’alimentation des charges annexes à partir du bus continu ou via convertisseurs dédiés.

## FE5 — Assurer la protection électrique

L’électronique doit protéger le système contre :

* surtension ;
* sous-tension ;
* surintensité ;
* surchauffe ;
* inversion ;
* court-circuit ;
* transitoires destructeurs.

---

# 74. Architecture fonctionnelle minimale du sous-système électrique

Le programme doit pouvoir représenter, à minima, la chaîne suivante :

$$
\text{Alternateur} \rightarrow \text{Redressement} \rightarrow \text{Filtrage} \rightarrow \text{Bus DC} \rightarrow \text{Conversion / régulation} \rightarrow \text{Batterie + Charges}
$$

Selon l’architecture réelle, il peut s’agir :

* d’un simple redresseur + filtrage ;
* d’un redresseur + convertisseur DC/DC ;
* d’un ensemble à conversion pilotée ;
* d’un système multi-bus avec conversions secondaires.

Le programme ne doit pas imposer une topologie non définie ; il doit seulement calculer ce qui est déductible de la topologie explicitement choisie.

---

# 75. Grandeurs fondamentales du bus continu

Le bus continu est la grandeur centrale de l’architecture électrique.

## 75.1 Tension nominale du bus

$$
U_{\text{bus,nom}}
$$

## 75.2 Tension minimale admissible du bus

$$
U_{\text{bus,min}}
$$

## 75.3 Tension maximale admissible du bus

$$
U_{\text{bus,max}}
$$

## 75.4 Courant nominal du bus

$$
I_{\text{bus,nom}}
$$

## 75.5 Courant maximal du bus

$$
I_{\text{bus,max}}
$$

## 75.6 Puissance nominale transitant sur le bus

$$
P_{\text{bus,nom}} = U_{\text{bus,nom}} \cdot I_{\text{bus,nom}}
$$

## 75.7 Puissance maximale transitant sur le bus

$$
P_{\text{bus,max}} = U_{\text{bus}} \cdot I_{\text{bus,max}}
$$

Le programme doit vérifier la cohérence entre :

* la puissance fournie par l’alternateur ;
* la puissance appelée par les charges ;
* la puissance absorbée par la batterie ;
* la capacité thermique et électrique des composants du bus.

---

# 76. Redressement de la tension issue de l’alternateur

Le redressement ne doit pas être traité comme idéal si des pertes doivent être prises en compte.

## 76.1 Puissance d’entrée du redresseur

$$
P_{\text{red,in}}
$$

## 76.2 Rendement du redresseur

$$
\eta_{\text{red}}
$$

## 76.3 Puissance de sortie du redresseur

$$
P_{\text{red,out}} = \eta_{\text{red}} \cdot P_{\text{red,in}}
$$

## 76.4 Pertes du redresseur

$$
P_{\text{red,pertes}} = P_{\text{red,in}} - P_{\text{red,out}}
$$

ou encore :

$$
P_{\text{red,pertes}} = P_{\text{red,in}}\cdot (1-\eta_{\text{red}})
$$

## 76.5 Condition de compatibilité du redressement

La tension redressée disponible doit être compatible avec la suite de la chaîne :

$$
U_{\text{red,out}} \in \text{plage exploitable par le bus ou le convertisseur aval}
$$

Le programme ne doit pas inventer la forme exacte d’onde ou la loi précise de redressement si la topologie n’est pas imposée.

---

# 77. Filtrage du bus continu

Après redressement, la tension du bus peut nécessiter un filtrage pour limiter l’ondulation.

## 77.1 Tension moyenne bus

$$
U_{\text{bus,moy}}
$$

## 77.2 Ondulation admissible du bus

$$
\Delta U_{\text{bus}}
$$

## 77.3 Taux d’ondulation relatif

$$
\delta_U = \frac{\Delta U_{\text{bus}}}{U_{\text{bus,moy}}}
$$

Le taux d’ondulation admissible doit être défini comme entrée de conception ou comme exigence système.

## 77.4 Capacité de filtrage

Si la topologie impose un condensateur de lissage, la valeur de capacité nécessaire dépend :

* du courant ;
* de la fréquence d’ondulation ;
* de l’ondulation admissible ;
* de la topologie de redressement.

En pré-dimensionnement, le programme ne doit calculer une capacité de filtrage que si les variables suivantes sont connues :

* courant de bus ;
* fréquence d’ondulation ;
* ondulation admissible ;
* topologie de filtrage.

Sans ces données, il doit signaler l’inconnue sans inventer.

---

# 78. Convertisseur DC/DC — rôle et modélisation

Si la tension issue du redressement n’est pas directement compatible avec la batterie ou les charges, un convertisseur DC/DC est requis.

## 78.1 Puissance d’entrée du convertisseur

$$
P_{\text{conv,in}}
$$

## 78.2 Rendement du convertisseur

$$
\eta_{\text{conv}}
$$

## 78.3 Puissance de sortie du convertisseur

$$
P_{\text{conv,out}} = \eta_{\text{conv}} \cdot P_{\text{conv,in}}
$$

## 78.4 Pertes du convertisseur

$$
P_{\text{conv,pertes}} = P_{\text{conv,in}} - P_{\text{conv,out}}
$$

## 78.5 Compatibilité tension

Le convertisseur doit assurer :

$$
U_{\text{sortie conv}} \in \text{plage admissible du sous-système alimenté}
$$

## 78.6 Compatibilité courant

Le convertisseur doit satisfaire :

$$
I_{\text{sortie conv}} \le I_{\text{conv,max}}
$$

## 78.7 Nature du convertisseur

Le programme doit pouvoir accepter explicitement, selon architecture choisie :

* abaisseur ;
* élévateur ;
* abaisseur-élévateur ;
* bidirectionnel.

Il ne doit pas choisir automatiquement une topologie si l’utilisateur ne l’a pas définie.

---

# 79. Compatibilité entre bus continu et batterie

La batterie ne doit jamais être reliée au bus sans vérification stricte des grandeurs électriques.

## 79.1 Condition de tension de charge

La tension appliquée à la batterie doit respecter :

$$
U_{\text{charge}} \le U_{\text{pack,max admissible}}
$$

et :

$$
U_{\text{charge}} \ge U_{\text{seuil minimal de charge}}
$$

## 79.2 Condition de courant de charge

$$
I_{\text{charge}} \le I_{\text{pack,max,charge}}
$$

et :

$$
I_{\text{charge}} \le I_{\text{BMS,max,charge}}
$$

## 79.3 Condition de puissance de charge

$$
P_{\text{charge}} = U_{\text{pack}} \cdot I_{\text{charge}}
$$

Le programme doit vérifier que la chaîne alternateur → redressement → conversion peut fournir cette puissance sans dépasser les limites thermiques et électriques.

---

# 80. Compatibilité entre bus continu et charges auxiliaires

Les charges auxiliaires ne doivent pas être modélisées comme une grandeur abstraite unique si le détail est disponible.

Le programme doit pouvoir distinguer :

* charges permanentes ;
* charges intermittentes ;
* charges critiques ;
* charges secondaires.

## 80.1 Puissance auxiliaire totale

$$
P_{\text{aux,tot}} = \sum_i P_{\text{aux},i}
$$

## 80.2 Courant auxiliaire total

$$
I_{\text{aux,tot}} = \frac{P_{\text{aux,tot}}}{U_{\text{bus}}}
$$

## 80.3 Condition de disponibilité de puissance

Le système doit vérifier :

$$
P_{\text{bus,disponible}} \ge P_{\text{aux,tot}} + P_{\text{charge batterie}} + P_{\text{autres usages}}
$$

---

# 81. Bilan de puissance de la chaîne électronique

La chaîne complète doit satisfaire un bilan énergétique cohérent.

## 81.1 Puissance mécanique fournie à l’alternateur

$$
P_{\text{méc}}
$$

## 81.2 Puissance électrique brute générée

$$
P_{\text{gen}} = \eta_{\text{gen}} \cdot P_{\text{méc}}
$$

## 81.3 Puissance après redressement

$$
P_{\text{red}} = \eta_{\text{red}} \cdot P_{\text{gen}}
$$

## 81.4 Puissance après conversion DC/DC éventuelle

$$
P_{\text{dc}} = \eta_{\text{conv}} \cdot P_{\text{red}}
$$

## 81.5 Puissance réellement injectée vers la batterie

$$
P_{\text{pack,in}} = \eta_{\text{charge}} \cdot P_{\text{dc}}
$$

## 81.6 Rendement global de la chaîne électrique

$$
\eta_{\text{chaine elec}} = \eta_{\text{gen}} \cdot \eta_{\text{red}} \cdot \eta_{\text{conv}} \cdot \eta_{\text{charge}}
$$

Si un étage n’existe pas dans l’architecture retenue, son rendement n’est pas pris en compte.

---

# 82. Courants de bus et sections conductrices

Le bus continu et ses interconnexions doivent être dimensionnés à partir des courants réels.

## 82.1 Courant bus

$$
I_{\text{bus}} = \frac{P_{\text{bus}}}{U_{\text{bus}}}
$$

## 82.2 Condition de vérification

Le programme doit comparer :

* courant nominal ;
* courant maximal ;
* courant transitoire ;
* courant de défaut si défini.

## 82.3 Conducteurs et barres de bus

Le programme peut vérifier la densité de courant uniquement si les données suivantes sont fournies :

* section conductrice ;
* matériau conducteur ;
* mode de refroidissement ;
* température admissible.

Sans ces données, il doit signaler que la vérification thermique des conducteurs reste partielle.

---

# 83. Pertes Joule dans le bus et les liaisons

## 83.1 Résistance équivalente d’une liaison

$$
R_{\text{liaison}}
$$

## 83.2 Pertes Joule

$$
P_J = R_{\text{liaison}} \cdot I^2
$$

## 83.3 Chute de tension

$$
\Delta U = R_{\text{liaison}} \cdot I
$$

## 83.4 Condition de compatibilité

La chute de tension totale du bus doit rester compatible avec :

* la plage de fonctionnement des convertisseurs ;
* la tension minimale batterie ;
* la stabilité du bus ;
* les exigences des charges alimentées.

---

# 84. Contraintes thermiques de l’électronique de puissance

Les composants de puissance dissipent une partie de l’énergie sous forme thermique.

## 84.1 Puissance thermique à dissiper

Pour chaque étage :

$$
\dot Q \approx P_{\text{pertes}}
$$

## 84.2 Condition thermique composant

$$
T_{\text{jonction}} < T_{\text{jonction,max}}
$$

## 84.3 Condition thermique boîtier

$$
T_{\text{boîtier}} < T_{\text{boîtier,max}}
$$

## 84.4 Condition thermique environnement

$$
T_{\text{amb}} < T_{\text{amb,max admissible}}
$$

## 84.5 Besoin de refroidissement

Le système de dissipation doit être vérifié à partir :

* des pertes ;
* de la résistance thermique composant-radiateur ;
* de la résistance thermique radiateur-air ou radiateur-liquide ;
* de la température ambiante ;
* de la température maximale admissible.

Le programme ne doit pas inventer un dissipateur ni une résistance thermique si elles ne sont pas données ou déductibles.

---

# 85. Protections électriques minimales obligatoires

Le sous-système électronique doit être conçu avec une logique de protection explicite.

## 85.1 Protection surtension

Condition de déclenchement si :

$$
U_{\text{bus}} > U_{\text{bus,max}}
$$

## 85.2 Protection sous-tension

Condition de déclenchement si :

$$
U_{\text{bus}} < U_{\text{bus,min}}
$$

## 85.3 Protection surintensité

Condition de déclenchement si :

$$
I > I_{\text{max admissible}}
$$

## 85.4 Protection thermique

Condition de déclenchement si :

$$
T > T_{\text{max admissible}}
$$

## 85.5 Protection court-circuit

Le système doit prévoir une stratégie de coupure ou d’isolement en cas de défaut brutal.

Le programme peut seulement vérifier cette fonction si l’architecture de protection a été explicitement définie.

---

# 86. Compatibilité avec le fonctionnement intermittent du STHO-ME

Le caractère intermittent de la génération impose des contraintes particulières à l’électronique de puissance.

## 86.1 Variation temporelle de la puissance disponible

Le programme doit pouvoir traiter une puissance alternateur non constante :

$$
P_{\text{gen}} = P_{\text{gen}}(t)
$$

## 86.2 Conséquence sur le bus

Le bus continu doit rester stable malgré :

* démarrage génération ;
* arrêt génération ;
* variations de régime ;
* variation de couple ;
* bascule charge / recharge.

## 86.3 Condition d’absorption transitoire

La combinaison bus + batterie + conversion doit pouvoir absorber les écarts temporaires entre :

$$
P_{\text{disponible}}(t)
$$

et

$$
P_{\text{demandée}}(t)
$$

sans sortir des plages de sécurité.

---

# 87. Stratégie de dimensionnement du sous-système électronique

Le programme doit permettre deux approches.

## 87.1 Approche par besoin système

Entrées :

* tension bus cible ;
* puissance charge ;
* puissance recharge ;
* plage tension batterie ;
* caractéristiques alternateur ;
* rendements.

Sorties :

* puissance par étage ;
* courants ;
* pertes ;
* contraintes thermiques ;
* compatibilité globale.

## 87.2 Approche par composants existants

Entrées :

* redresseur défini ;
* convertisseur défini ;
* limites tension/courant ;
* rendement ;
* température ;
* résistance thermique.

Sorties :

* conformité ou non-conformité ;
* marges ;
* points bloquants ;
* besoins de refroidissement.

---

# 88. Critères d’acceptation technique du sous-système électronique

L’électronique de puissance intégrée au STHO-ME ne peut être considérée conforme que si les conditions suivantes sont satisfaites.

## 88.1 Critère tension bus

$$
U_{\text{bus,min}} \le U_{\text{bus,fonctionnement}} \le U_{\text{bus,max}}
$$

## 88.2 Critère courant

$$
I_{\text{fonctionnement}} \le I_{\text{max composant}}
$$

## 88.3 Critère puissance

$$
P_{\text{transit}} \le P_{\text{max admissible étage}}
$$

## 88.4 Critère thermique

$$
T_{\text{fonctionnement}} < T_{\text{max admissible}}
$$

## 88.5 Critère batterie

La puissance délivrée à la batterie doit être compatible avec :

* tension pack ;
* courant de charge ;
* BMS ;
* température.

## 88.6 Critère rendement

Le rendement global de la chaîne électrique doit rester compatible avec l’objectif énergétique du système.

---

# 89. Sorties minimales du programme sur l’électronique de puissance

Le logiciel doit fournir automatiquement :

* tension nominale bus ;
* tension min bus ;
* tension max bus ;
* courant nominal bus ;
* courant max bus ;
* puissance par étage ;
* rendement par étage ;
* rendement global chaîne électrique ;
* pertes redressement ;
* pertes conversion ;
* pertes liaisons ;
* chute de tension bus ;
* puissance dissipée totale ;
* avertissements thermiques ;
* avertissements tension ;
* avertissements courant ;
* avertissements compatibilité batterie ;
* avertissements compatibilité alternateur ;
* niveau de validité du calcul.

---

# 90. Hypothèses et limites de validité de cette modélisation

La présente modélisation est valable pour du **pré-dimensionnement système** et de la **vérification d’architecture**.

Elle ne remplace pas :

* le dimensionnement détaillé des semi-conducteurs ;
* la simulation SPICE ;
* la modélisation CEM ;
* l’étude des commandes PWM ;
* l’étude détaillée des filtres ;
* la validation thermique composants ;
* la qualification des protections.

Le programme doit distinguer explicitement :

* les calculs fermes ;
* les calculs conditionnels ;
* les estimations dépendantes de composants non définis ;
* les inconnues bloquantes ;
* les vérifications à reporter sur prototype ou sur composants réels.

---
