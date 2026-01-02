Différence traction (FWD) vs propulsion (RWD) : **la limite n’est pas la puissance moteur**, mais **l’adhérence disponible sur l’essieu moteur**, qui dépend des **transferts de charge** (accélération, pente, freinage). Donc il faut donner les formules **d’effort transmissible** et en déduire **couple** et **puissance**.

---

## 1) Notations

* (m) : masse véhicule (kg)
* (g) : 9,81 m/s²
* (L) : empattement (m)
* (h) : hauteur du centre de gravité (m)
* (a) : accélération longitudinale (m/s²), positive en accélération
* (\theta) : angle de pente (rad) ; pente 10% ⇒ (\tan\theta \approx 0{,}10)
* (\mu) : coefficient d’adhérence pneu/sol
* (C_{rr}) : coefficient de roulement
* (\rho) : densité air (≈1,2 kg/m³)
* (C_dA) : traînée équivalente (m²)
* (v) : vitesse (m/s)
* (R) : rayon dynamique roue (m)
* (T_w) : couple à la roue (N·m)
* (\eta_{trans}) : rendement transmission (roue)
* (\eta_{drv}) : rendement batterie→moteur→roue (si besoin)

Distances CG :

* (l_f) : distance CG → essieu **avant** (m)
* (l_r) : distance CG → essieu **arrière** (m)
* (L=l_f+l_r)

---

## 2) Forces résistantes (valables traction/propu)

Force de résistance totale :
[
F_{res}(v,\theta)=F_{rr}+F_{aero}+F_{grade}
]
avec
[
F_{rr}=mg,C_{rr}\cos\theta
]
[
F_{aero}=\frac12\rho C_dA,v^2
]
[
F_{grade}=mg\sin\theta
]

Force de traction nécessaire pour une accélération (a) :
[
F_{req}=m,a+F_{res}(v,\theta)
]

Puissance aux roues correspondante :
[
P_{wheel}=F_{req},v
]

Couple total aux roues :
[
T_{w,total}=F_{req},R
]

---

## 3) Charges normales avant/arrière (formules “précises”)

En dynamique longitudinale sur pente, les charges normales (réaction sol) sont :

[
N_f=\frac{mg\cos\theta;l_r - m a,h - mg\sin\theta;h}{L}
]
[
N_r=\frac{mg\cos\theta;l_f + m a,h + mg\sin\theta;h}{L}
]

Vérification : (N_f+N_r=mg\cos\theta).

* Le terme (m a h/L) = **transfert de charge dû à l’accélération** (vers l’arrière si (a>0)).
* Le terme (mg\sin\theta,h/L) = **transfert dû à la pente** (en montée, charge vers l’arrière).

---

## 4) Limite d’adhérence selon traction / propulsion

### Traction (FWD)

L’essieu moteur est l’avant, donc effort transmissible max :
[
F_{\max,FWD}=\mu,N_f
]

### Propulsion (RWD)

Essieu moteur arrière :
[
F_{\max,RWD}=\mu,N_r
]

### AWD (4 roues motrices) (pour compléter)

Idéalement (si répartition parfaite) :
[
F_{\max,AWD}=\mu,(N_f+N_r)=\mu,mg\cos\theta
]
(en pratique limité par stratégie de répartition, différentiels, pneus, etc.)

---

## 5) Condition de faisabilité (clé)

Pour atteindre une demande (F_{req}), il faut :

* **Traction (FWD)** :
  [
  F_{req}\le \mu,N_f
  ]
* **Propulsion (RWD)** :
  [
  F_{req}\le \mu,N_r
  ]

Sinon, tu patines : la puissance moteur supplémentaire n’aide pas.

---

## 6) Déduire accélération max possible (très utile)

### Traction (FWD)

On impose (F_{req}=F_{\max,FWD}) :

[
m a + F_{res} = \mu N_f
]
avec (N_f=\frac{mg\cos\theta,l_r - m a h - mg\sin\theta,h}{L})

On obtient directement :
[
a_{\max,FWD}=
\frac{\mu\left(\frac{g\cos\theta,l_r - g\sin\theta,h}{L}\right)-\frac{F_{res}}{m}}
{1+\mu\frac{h}{L}}
]

### Propulsion (RWD)

[
m a + F_{res} = \mu N_r
]
avec (N_r=\frac{mg\cos\theta,l_f + m a h + mg\sin\theta,h}{L})

[
a_{\max,RWD}=
\frac{\mu\left(\frac{g\cos\theta,l_f + g\sin\theta,h}{L}\right)-\frac{F_{res}}{m}}
{1-\mu\frac{h}{L}}
]

Observation importante :

* En FWD, (a_{\max}) est pénalisé par (1+\mu h/L) (transfert vers l’arrière qui **décharge l’avant**).
* En RWD, le dénominateur (1-\mu h/L) montre que le transfert **aide** l’arrière (jusqu’à des limites).

---

## 7) Dimensionnement puissance/couple moteur selon traction/propu

### 7.1 Couple total requis aux roues

[
T_{w,total}=F_{req},R
]

### 7.2 Répartition du couple selon architecture

* FWD : couple transmis à l’avant
  [
  T_{w,front}=T_{w,total}
  ]
* RWD :
  [
  T_{w,rear}=T_{w,total}
  ]
* AWD : (\alpha) vers l’avant, (1-\alpha) vers l’arrière
  [
  T_{w,front}=\alpha,T_{w,total},\quad T_{w,rear}=(1-\alpha),T_{w,total}
  ]

### 7.3 Limite couple roue par adhérence (le “couple max utilisable”)

* FWD :
  [
  T_{w,\max,FWD} = (\mu N_f),R
  ]
* RWD :
  [
  T_{w,\max,RWD} = (\mu N_r),R
  ]

### 7.4 Couple moteur (si rapport total (G) et rendement (\eta_{trans}))

[
T_{motor}=\frac{T_w}{G,\eta_{trans}}
]

### 7.5 Puissance moteur demandée

[
P_{motor} \approx \frac{P_{wheel}}{\eta_{trans}}
= \frac{F_{req},v}{\eta_{trans}}
]

**Mais** le dimensionnement “crête” doit respecter :
[
F_{req}\le F_{\max,(FWD/RWD)}
\Rightarrow
P_{wheel}\le F_{\max,(FWD/RWD)},v
]

Donc puissance “utilisable” limitée par adhérence :

* FWD :
  [
  P_{\max,util,FWD}(v)=\mu N_f,v
  ]
* RWD :
  [
  P_{\max,util,RWD}(v)=\mu N_r,v
  ]

---

## 8) Lien direct avec ton dimensionnement batterie (rappel compact)

* Batterie → puissance crête alimentable :
  [
  P_{motor,peak}\le \eta_{drv},C_{\max},E_b
  ]

Dimensionnement final “propre” :
[
P_{motor,peak} \le \min\big(\eta_{drv}C_{\max}E_b,; \frac{P_{\max,util}(v)}{\eta_{trans}}\big)
]
avec (P_{\max,util}(v)) choisi selon FWD/RWD.

---

Si tu me donnes (m, L, h, l_f) (ou répartition statique), (R), (\mu), et 2 cas d’usage (ex : 0–50 km/h, et montée 6% à 110), je te fournis une fiche chiffrée traction vs propulsion : **accélération max, couple roue max, puissance utile max**, et donc la puissance moteur “cohérente” avec ta batterie.


## 9) Ajouts utiles pour rendre le cadre “complet” (FWD/RWD/AWD)

### 9.1 Répartition statique des charges (si tu n’as pas (l_f,l_r))

Charge normale **statique** (route plane, (a=0), (\theta=0)) :
[
N_{f0}=mg\frac{l_r}{L}
\qquad
N_{r0}=mg\frac{l_f}{L}
]
Donc si tu connais la répartition de masse statique avant ( \lambda_f ) (ex. 0,60) :
[
\lambda_f=\frac{N_{f0}}{mg}=\frac{l_r}{L}
\Rightarrow
l_r=\lambda_f L
\qquad
l_f=(1-\lambda_f)L
]

---

### 9.2 Limite “power-limited” vs “traction-limited”

Force réellement disponible à la roue (si moteur limité en puissance/couple) :

* **limite puissance** :
  [
  F_{pow}(v)=\frac{P_{wheel,max}}{v}
  ]
* **limite couple roue** (moteur + rapport) :
  [
  F_{tor}=\frac{T_{w,max,drivetrain}}{R}
  ]
* **limite adhérence** :
  [
  F_{\mu}=
  \begin{cases}
  \mu N_f & \text{FWD}\
  \mu N_r & \text{RWD}\
  \mu(N_f+N_r) & \text{AWD (idéal)}
  \end{cases}
  ]

Force de traction effective :
[
F_{drive}(v)=\min\big(F_{pow}(v),;F_{tor},;F_{\mu}\big)
]

Accélération réellement obtenue :
[
a(v)=\frac{F_{drive}(v)-F_{res}(v,\theta)}{m}
]

Vitesse à partir de laquelle tu deviens “power-limited” (si tu étais traction-limited avant) :
[
v^* \approx \frac{P_{wheel,max}}{F_{\mu}}
]
(en prenant (F_{\mu}) à (a) faible ou avec une itération si besoin).

---

### 9.3 Modèle (\mu) réaliste (dépendant de la charge) – optionnel mais utile

Sur pneus réels, (\mu) diminue quand la charge augmente (sensibilité charge). Un modèle simple :
[
\mu(N)=\mu_0\left(\frac{N}{N_0}\right)^{-k}
\quad (k>0)
]
Alors la force max n’est plus exactement (\mu N) avec (\mu) constant, mais :
[
F_{\max}=\mu(N),N
]
(utile si tu compares FWD/RWD sur gros transferts de charge).

---

### 9.4 Cas multi-essieux moteurs : limite par essieu et somme

Si AWD non idéal (répartition (\alpha) au train avant) :
[
F_{front}\le \mu N_f,\quad F_{rear}\le \mu N_r
]
[
F_{\max,AWD}(\alpha)=\min(\alpha F_{req},\mu N_f)+\min((1-\alpha)F_{req},\mu N_r)
]
En pratique, pour maximiser :
[
\alpha^* \approx \frac{N_f}{N_f+N_r}
]
(répartition proportionnelle aux charges, si (\mu) identique).

---

### 9.5 Limite par **capacité de traction du groupe motopropulseur** (rapport + couple moteur)

Si rapport total (G) et couple moteur max (T_{m,max}(\omega)) :
[
T_{w,max,drivetrain}=T_{m,max}(\omega),G,\eta_{trans}
]
[
F_{tor}=\frac{T_{m,max}(\omega),G,\eta_{trans}}{R}
]
Lien vitesse ↔ régime moteur (1 rapport fixe ou rapport engagé (G_k)) :
[
\omega_m=\frac{v}{R},G
\qquad
n_m=\omega_m\frac{60}{2\pi}
]

---

### 9.6 Condition de **décollage en côte** (très parlant)

À vitesse quasi nulle ((v\to 0), donc pas d’aéro) :
[
F_{res}\approx mg,C_{rr}\cos\theta + mg\sin\theta
]
Condition “je démarre sans patiner” :
[
F_{drive}\ge F_{res}
\quad\text{avec}\quad
F_{drive}\le F_{\mu}
]
Donc pente maximale “adhérence” (ordre 1) :

* FWD :
  [
  \mu N_f \ge mg(C_{rr}\cos\theta+\sin\theta)
  ]
* RWD :
  [
  \mu N_r \ge mg(C_{rr}\cos\theta+\sin\theta)
  ]

---

### 9.7 Freinage (transfert de charge inverse) – utile si tu compares architecture

En freinage (a<0), les signes s’inversent dans (N_f,N_r).
Sur route plane ((\theta=0)) :
[
N_f=\frac{mg,l_r - m a,h}{L}
\qquad
N_r=\frac{mg,l_f + m a,h}{L}
]
Si (a<0) (freinage), ( -ma h/L ) devient **+** : l’avant se charge fortement.

---

### 9.8 Contrôle traction / limite par glissement (si tu veux coller à la réalité)

On peut poser un ratio de glissement (\kappa) :
[
\kappa=\frac{\omega_w R - v}{\max(v,\epsilon)}
]
et une loi pneu simplifiée :
[
F_x(\kappa)=\mu_{peak}N;\frac{\kappa}{\kappa_{peak}+\kappa}
]
Ça sert à relier “commande” (couple) → “force” sans supposer tout-ou-rien.

---

## 10) Check-list “ce qui manquait” (si tu veux un document robuste)

1. **Force réelle dispo** : (F_{drive}=\min(F_{pow},F_{tor},F_\mu))
2. **Vitesse de bascule** traction-limited → power-limited : (v^*\approx P/F_\mu)
3. **Répartition statique** si (l_f,l_r) inconnus : (l_r=\lambda_f L)
4. **AWD non idéal** : optimum (\alpha^*\approx N_f/(N_f+N_r))
5. **Démarrage en côte** (v→0) : comparaison directe (F_\mu) vs (mg\sin\theta)
6. Option pneus : (\mu(N)) ou (F_x(\kappa)) (pour éviter (\mu) constant)

---

## 11) Petite correction de forme (mineure mais importante)

Dans tes équations de charges normales, écris clairement les produits (évite les “;”) :

[
N_f=\frac{mg\cos\theta;l_r - ma,h - mg\sin\theta;h}{L}
]
[
N_r=\frac{mg\cos\theta;l_f + ma,h + mg\sin\theta;h}{L}
]

(Le reste est cohérent.)

---

Si tu veux, je peux aussi te donner une version “prête à coller” où j’intègre ces ajouts directement dans ton texte, sans changer ta structure.
