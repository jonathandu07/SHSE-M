Je te propose une **version dossier technique de niveau pré-industrialisation**, structurée comme un véritable **cahier des charges technique + fonctionnel exploitable pour R&D, calcul, CAO, simulation et validation prototype**.

Tu peux le reprendre tel quel comme base de `README.md`, ou mieux : en faire un document séparé `DOSSIER_TECHNIQUE_STHO_ME.md`.

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

# 21. CE QU’UN DOSSIER INDUSTRIEL DOIT AJOUTER ENSUITE

Encore absent :

---

* fatigue Wöhler,
* dilatations différentielles,
* jeux piston/cylindre,
* rugosité,
* rendement roulements,
* pertes segmentation,
* inerties tournantes complètes,
* spectre vibratoire.

---
