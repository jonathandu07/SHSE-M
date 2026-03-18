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

