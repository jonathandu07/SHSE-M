Je peux te donner un **jeu d’équations de dimensionnement** (cylindre, pistons/déplaceur, bielle, vilebrequin, paliers, joints, couvercle, vis), mais il faut être clair : **il n’existe pas une seule équation qui “sort toutes les pièces”**. On fait un **enchaînement** :

1. objectif énergie/puissance → 2) cycle thermo/pression → 3) efforts → 4) sections/épaisseurs (résistance, fatigue) → 5) frottement/usure/état de surface → 6) étanchéité (joints/segments) → 7) assemblages (vis/couvercles).

Ce qui suit est un **cadre calculatoire complet** (sans boîte à crabots ni alternateur, comme demandé).

---

## 0) Entrées minimales (sinon impossible de chiffrer)

* Puissance électrique cible (P_e) (kW) et régime (n) (tr/min)
* Rendement global visé (\eta_{glob}) (combustion→mécanique→alternateur exclu si tu veux)
* Pression max admissible (p_{max}) (Pa) et température max (T_{max}) (K)
* Rapport course/alésage visé (S/B) (ou plage)
* Matériau cylindre : limite d’élasticité (R_e), limite fatigue (\sigma_D), (E), (\nu)
* Coefficient de frottement (\mu_f) (ordre de grandeur) et cible de durée de vie (N) (cycles)

---

## 1) Thermo simplifiée → pression et travail par cycle

### 1.1 Gaz (approximation)

[
pV = mRT
]

Si tu “chauffes” à volume quasi constant côté chaud (modèle grossier mais utile) :
[
\frac{p_2}{p_1} = \frac{T_2}{T_1}
]

### 1.2 Travail indiqué (par cycle)

Approche “pression moyenne effective” (PME / IMEP), robuste pour dimensionner :
[
W_i = p_{mi},V_d
]

* (W_i) : travail indiqué par cycle (J)
* (p_{mi}) : pression moyenne indiquée (Pa)
* (V_d) : cylindrée (m³)

Puissance indiquée :

* 2 temps : cycles/s (= n/60)
* 4 temps : cycles/s (= n/120)

[
P_i = W_i \cdot \text{cycles/s}
= p_{mi}V_d \cdot \text{cycles/s}
]

Puissance utile mécanique (P_b) via rendement mécanique (\eta_m) :
[
P_b = \eta_m,P_i
]

Si tu pars de la puissance électrique et que tu exclus l’alternateur, prends :
[
P_b \approx \frac{P_e}{\eta_{transmission}} \quad (\text{ou } P_b=P_{méc} \text{ cible})
]

Tu peux en déduire la cylindrée :
[
V_d = \frac{P_b}{\eta_m,p_{mi},\text{cycles/s}}
]

---

## 2) Géométrie cylindre / pistons

### 2.1 Cylindrée

[
V_d = \frac{\pi}{4}B^2S
]

* (B) alésage, (S) course

Choix pratique : fixer (S/B) (ex. 0,8 à 1,2) puis résoudre.

### 2.2 Vitesse moyenne piston (contrainte)

[
U_p = 2S\cdot \frac{n}{60}
]
Limiter (U_p) (durabilité, frottements). C’est une contrainte structurante.

---

## 3) Efforts → dimensionnement bielle, piston, vilebrequin

### 3.1 Force gaz sur piston “de puissance”

[
F_g(\theta) = p(\theta),A_p
\quad \text{avec}\quad A_p=\frac{\pi}{4}B^2
]

Si tu n’as pas (p(\theta)), borne max :
[
F_{g,max} = p_{max},A_p
]

### 3.2 Inertie alternative (piston + axe + 1/3 bielle)

[
F_i(\theta) \approx m_{eq},r,\omega^2\left(\cos\theta + \frac{r}{l}\cos2\theta\right)
]

* (r=S/2), (l)=longueur bielle, (\omega=2\pi n/60)

Force axiale totale sur bielle (simplifiée) :
[
F_{rod}(\theta) \approx F_g(\theta) - F_i(\theta)
]

### 3.3 Couple vilebrequin (ordre 1)

[
T(\theta) \approx F_{rod}(\theta),r,\sin\theta
]
Couple moyen :
[
\bar T = \frac{P_b}{\omega}
]

---

## 4) Épaisseur de paroi du cylindre (pression)

### 4.1 Cylindre mince (si (t \le 0{,}1,r_i))

[
\sigma_\theta \approx \frac{p,r_i}{t}
\quad\Rightarrow\quad
t \ge \frac{p,r_i}{\sigma_{adm}}
]
avec (\sigma_{adm} = \frac{R_e}{\gamma}) (coef sécurité (\gamma)).

### 4.2 Cylindre épais (Lamé) — recommandé si pression élevée

Rayons (r_i) (interne) et (r_o) (externe), pression interne (p_i), externe (p_o\approx 0).
Contrainte cerclage max à (r=r_i) :
[
\sigma_{\theta}(r_i)=
p_i;\frac{r_o^2+r_i^2}{r_o^2-r_i^2}
]
Imposer :
[
\sigma_{\theta}(r_i)\le \sigma_{adm}
]
Tu résous pour (r_o) donc (t=r_o-r_i).

### 4.3 Fatigue (si cycles importants)

Vérifier alternance de contrainte (Goodman simplifié) :
[
\frac{\sigma_a}{\sigma_D}+\frac{\sigma_m}{R_u}\le 1
]
((R_u) résistance ultime).

---

## 5) Couvercle/culasse, joints statiques, vis

### 5.1 Effort de séparation sur couvercle

[
F_{sep} = p_{max},A_{eff}
]
(A_{eff}) = surface pressurisée “vue” par le couvercle.

### 5.2 Précharge totale vis (anti-ouverture + étanchéité)

[
F_{preload,tot} \ge \gamma_s,F_{sep} + F_{gasket}
]

* (\gamma_s) : marge (ex. 1,2–2 selon exigence)
* (F_{gasket}) dépend du joint (contrainte de serrage requise)

Si (N_b) vis identiques :
[
F_{preload,bolt} = \frac{F_{preload,tot}}{N_b}
]

### 5.3 Dimension vis (traction)

[
\sigma_b=\frac{F_{preload,bolt}}{A_s}\le \sigma_{adm,b}
]
(A_s) section résistante filetage.

Couple de serrage (approximation) :
[
M \approx K,F_{preload,bolt},d
]
((K) facteur d’assemblage ~0,18–0,25 suivant frottements).

---

## 6) Piston “de puissance” : épaisseurs, axe, segments/joints

### 6.1 Épaisseur calotte piston (ordre de grandeur mécanique)

Pour une calotte assimilée à plaque circulaire encastrée (approx) :
[
t_{crown} \gtrsim \sqrt{\frac{p_{max},B^2}{k,\sigma_{adm}}}
]
(k) dépend du modèle (support/encastrement). On l’utilise pour donner une **borne**, puis on valide en calcul/FEA.

### 6.2 Axe de piston (cisaillement + flexion simplifié)

Charge max (\approx F_{g,max}). Vérifier pression de palier et flexion de l’axe :

* pression de contact (pied de bielle / bossages) :
  [
  p_{bearing}=\frac{F}{d_{pin},b_{bearing}} \le p_{adm}
  ]

### 6.3 Segments / joints sur piston à bielle

On ne “calcule” pas un nombre par une équation unique ; on dimensionne par **fuite admissible** + **frottement**.

* Fuite à travers un jeu annulaire (laminaire, ordre 1) :
  [
  \dot m \propto \frac{\Delta p,h^3}{\mu,L}
  ]
  (h) jeu radial, (L) longueur de fuite, (\mu) viscosité.
  Plus de segments augmente (L) effectif mais augmente frottements.

**Règle d’ingénierie** (piston puissance) :

* 2 segments compression + 1 racleur (si huile)
* ou 2 segments si lubrification minimale et exigences modérées
  Tu fixes ensuite :
* jeu d’extrémité, tension radiale, rugosité et traitement pour tenir l’usure.

---

## 7) Déplaceur / piston libre : guidage, joints, stabilité

Ton “déplaceur” subit surtout :

* effort différentiel de pression
* frottements de guidage
* risques de basculement / grippage

### 7.1 Force sur déplaceur

[
F_d = \Delta p , A_d
]

### 7.2 Guidage (éviter flambage/basculement)

On vise un rapport longueur guidée / diamètre suffisant et une ovalisation faible.
Le calcul direct dépend de la géométrie de guidage (coulisse, tiges, bagues).

### 7.3 Nombre de joints déplaceur

Même logique : fuite admissible vs frottement.

* Si le déplaceur doit “isoler” zones chaud/froid fortement, on augmente la longueur de fuite et/ou le nombre de lèvres/segments.
* Si l’objectif est rendement et faible usure, on minimise le frottement → moins de joints + meilleure géométrie de labyrinthe.

Formule directrice : tu imposes une fuite max (\dot m_{max}), tu modélises (\dot m) (fonction du jeu, longueur, pression), puis tu choisis longueur/joints pour que :
[
\dot m \le \dot m_{max}
]

---

## 8) État de surface, frottement, usure (formules)

### 8.1 Rugosité (objectif)

On la relie à l’usure et à l’étanchéité, mais elle dépend surtout du couple matériau/traitement/lubrification.
La partie “calcul” est plutôt indirecte via la loi d’usure.

### 8.2 Loi d’Archard (usure)

Volume usé :
[
V_w = k \frac{W,L_s}{H}
]

* (k) coefficient d’usure (sans dimension)
* (W) charge normale
* (L_s) distance de glissement cumulée
* (H) dureté

Distance de glissement (piston/cylindre) sur (N) cycles :
[
L_s \approx 2S \cdot N
]

Perte de matière moyenne (si surface (A)) :
[
\Delta h \approx \frac{V_w}{A}
]

Tu peux ainsi dimensionner **durée de vie** en imposant (\Delta h \le \Delta h_{max}).

---

## 9) Bielle : longueur, section, flambage, paliers

### 9.1 Rapport (l/r) (cinématique + efforts)

[
\lambda=\frac{l}{r}
]
Plus (\lambda) est grand, moins il y a d’efforts secondaires, mais bielle plus lourde.

### 9.2 Contrainte axiale

[
\sigma = \frac{F_{max}}{A} \le \sigma_{adm}
]

### 9.3 Flambage (Euler) si compression dominante

[
F_{cr} = \frac{\pi^2 E I}{(K L)^2}
]
Imposer (F_{cr} \ge \gamma,F_{comp,max}).

### 9.4 Pression de palier (pied et tête de bielle)

[
p_{bearing}=\frac{F}{d,b} \le p_{adm}
]

---

## 10) “Compter tout” : liste complète des sous-ensembles (hors crabots/alternateur)

### Pièces principales

* Cylindre (chemise) + éventuellement enveloppe externe / isolation
* Chambre chaude : injecteur/arrivée air+carburant, zone de flamme, bougie/ignition (si applicable)
* Déplaceur (piston libre) + guidage (bague(s), tige(s), butées)
* Piston de puissance + axe + circlips
* Segments/joints piston (et déplaceur)
* Bielle (corps) + coussinets / bagues
* Vilebrequin + maneton + paliers principaux
* Carter / bâti
* Couvercle(s) (avant/arrière/culasse)
* Joints statiques (plan de joint), joints tournants (si arbre sort)
* Visserie : vis, rondelles, écrous (si non taraudé), goupilles, clavettes (si arbre)
* Entretoises, brides, supports, butées axiales, lubrification (si présente)

Chaque groupe ci-dessus se dimensionne avec les équations des sections 3–6 + assemblage section 5 + usure section 8.

---

## Ce que je te propose pour produire “les équations + dimensionnement de toutes les pièces” proprement

Si tu me donnes ces valeurs (même approximatives), je peux te rendre une **fiche de calcul complète** (type rapport, comme ton SHSE-M) avec toutes les dimensions symboliques + exemples numériques :

1. (P_b) cible et (n)
2. (p_{max}), (p_{mi}) visé, (T_{max})
3. (S/B) visé ou contrainte (U_p) max
4. (L, h, matériaux (cylindre/piston/bielle)) ou au minimum (R_e), (E)
5. Hypothèse lubrification (huile / sèche / mixte)
6. Durée de vie (N) cycles et (\Delta h_{max}) (usure tolérée)

Sans ces entrées, je peux uniquement donner le **cadre** (ci-dessus), mais pas “la taille précise” de chaque pièce.

Si tu enchaînes avec tes valeurs (même grossières), je te sors : (B), (S), (t_{cyl}) (Lamé), calotte piston, axe, bielle (l, section, flambage), diamètre maneton, paliers, force de serrage et diamètre/quantité minimale de vis, et un tableau BOM.
