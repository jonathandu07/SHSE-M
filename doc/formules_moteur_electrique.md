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
