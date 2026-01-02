Il n’existe pas une “formule magique” qui dit *directement* “ce sera en ligne / V / W / étoile”. En revanche, on peut écrire une **formule de décision** (optimisation) basée sur :

1. la **cylindrée totale requise** (donc le **nombre de cylindres** minimal),
2. des **contraintes d’encombrement** (longueur/largeur/hauteur),
3. des **contraintes mécaniques/thermiques** (vitesse piston, force max, pertes),
4. un **objectif** (masse, compacité, vibration, simplicité).

Ci-dessous, une version exploitable (cadre “ingénierie” propre) adaptée à ton approche SHSE-M : dimensionnement par puissance → IMEP → cylindrée → nombre de cylindres → architecture.

---

## 1) Cylindrée totale requise (ce qui fixe *d’abord* N)

### 1.1 Puissance mécanique cible

Si tu vises une puissance électrique (P_e) et un rendement alternateur/transmission (\eta_{alt}) :

[
P_b=\frac{P_e}{\eta_{alt}}
]

### 1.2 Puissance indiquée et IMEP

Avec rendement mécanique (\eta_m) :

[
P_i=\frac{P_b}{\eta_m}
]

Avec IMEP (p_{mi}) (pression moyenne indiquée), cylindrée totale (V_{d,tot}), et nombre de cycles/s :

* 2 temps : (\text{cycles/s}=\frac{n}{60})
* 4 temps : (\text{cycles/s}=\frac{n}{120})

[
P_i=p_{mi},V_{d,tot},\text{cycles/s}
\quad\Rightarrow\quad
V_{d,tot}=\frac{P_i}{p_{mi},\text{cycles/s}}
]

Donc :

* **2T** :
  [
  V_{d,tot}=\frac{P_i}{p_{mi}}\cdot\frac{60}{n}
  ]
* **4T** :
  [
  V_{d,tot}=\frac{P_i}{p_{mi}}\cdot\frac{120}{n}
  ]

---

## 2) Cylindrée max “acceptable” par cylindre (limites mécaniques)

Tu fixes des bornes réalistes (durabilité) :

* vitesse moyenne piston max (U_{p,max})
* alésage max (B_{max}) (thermique/masse/contraintes)
* ratio (S/B) dans une plage ([r_{min},r_{max}])

### 2.1 Course max via vitesse piston

[
U_p=2S\frac{n}{60}
\quad\Rightarrow\quad
S_{max}=\frac{U_{p,max}}{2}\cdot\frac{60}{n}
=\frac{30,U_{p,max}}{n}
]

### 2.2 Choix du couple ((B,S)) admissible

Avec (S=rB) (où (r\in[r_{min},r_{max}])) et (B\le B_{max}) et (S\le S_{max}).

La cylindrée **par cylindre** :
[
V_{d,cyl}=\frac{\pi}{4}B^2S=\frac{\pi}{4}B^3r
]

Donc la cylindrée **max par cylindre** admissible est :

[
V_{d,cyl,max}=\max_{\substack{B\le B_{max}\ r\in[r_{min},r_{max}]\ rB\le S_{max}}}
\left(\frac{\pi}{4}B^3r\right)
]

En pratique, ça revient à prendre :
[
B^*=\min\left(B_{max},\frac{S_{max}}{r_{max}}\right),
\quad r^*=r_{max}
]
et
[
V_{d,cyl,max}\approx \frac{\pi}{4}(B^*)^3r^*
]

---

## 3) Nombre minimal de cylindres

[
N_{cyl}=\left\lceil \frac{V_{d,tot}}{V_{d,cyl,max}} \right\rceil
]

C’est la formule la plus directe/robuste pour “combien de cylindres” (tant que tes hypothèses (p_{mi},U_{p,max},B_{max},r) sont cohérentes).

---

## 4) “Formule” de choix d’architecture (ligne / V / W / étoile)

Une architecture se choisit en minimisant une fonction coût sous contraintes d’encombrement et d’équilibrage. La forme la plus propre est :

[
\boxed{
\text{Arch}^*=\arg\min_{\text{Arch}\in{\text{L},\text{V},\text{W},\text{étoile}}}
J(\text{Arch},N_{cyl})
}
]

avec une fonction coût (exemple) :

[
J=w_L,\frac{L_{pkg}}{L_{max}}
+w_W,\frac{W_{pkg}}{W_{max}}
+w_H,\frac{H_{pkg}}{H_{max}}
+w_M,\frac{M_{est}}{M_{max}}
+w_V,\text{VibIndex}(\text{Arch},N_{cyl})
+w_C,\text{Complex}(\text{Arch})
]

* (L_{pkg},W_{pkg},H_{pkg}) : encombrements estimés de l’architecture
* (\text{VibIndex}) : pénalité vibration/irrégularité (fonction du nombre de bancs, ordre d’allumage, symétrie)
* (\text{Complex}) : pénalité complexité (vilebrequin, distribution, carters, refroidissement)

### Règles de décision (à brancher dans (J) ou comme contraintes)

Pour éviter d’“inventer” des constants, on utilise des règles qualitatives standard :

* **En ligne (L)** : meilleur si longueur disponible et simplicité prioritaire
  [
  \text{si } N_{cyl}\le 6 \text{ (souvent)} \ \land\ L_{pkg}\le L_{max}\Rightarrow \text{favoriser L}
  ]

* **En V** : meilleur si la longueur est limitée mais la largeur acceptable
  [
  \text{si } N_{cyl}\ge 6 \ \land\ L_{pkg}(\text{L})>L_{max}\Rightarrow \text{favoriser V}
  ]

* **En W** : compacité longitudinale pour (N) élevé, mais complexité forte
  [
  \text{si } N_{cyl}\ge 12 \ \land\ (L_{pkg}(\text{V})>L_{max})\Rightarrow \text{envisager W}
  ]

* **Étoile (radial)** : très compact en longueur, bon refroidissement air, mais diamètre frontal élevé et architecture spécifique
  [
  \text{si } L_{max}\ \text{très contraignant} \ \land\ W_{max}\ \text{large OK} \Rightarrow \text{envisager étoile}
  ]

---

## 5) Résumé “une ligne” (ce que tu demandais)

### Nombre de cylindres

[
\boxed{
N_{cyl}=\left\lceil
\frac{
\frac{1}{p_{mi}}\cdot\frac{P_e}{\eta_{alt}\eta_m}\cdot\frac{k}{n}
}{
\max\limits_{B\le B_{max},,r\in[r_{min},r_{max}],,rB\le \frac{30U_{p,max}}{n}}
\left(\frac{\pi}{4}B^3r\right)
}
\right\rceil
}
]
où (k=60) (2T) ou (k=120) (4T).

### Architecture

[
\boxed{
\text{Arch}^*=\arg\min_{\text{Arch}\in{\text{L},\text{V},\text{W},\text{étoile}}}
\left[
w_L\frac{L_{pkg}}{L_{max}}+
w_W\frac{W_{pkg}}{W_{max}}+
w_H\frac{H_{pkg}}{H_{max}}+
w_V\text{VibIndex}+
w_C\text{Complex}
\right]
}
]

---

Si tu me donnes juste ces 8 valeurs (même grossières) : (P_e, n, p_{mi}, \eta_m, \eta_{alt}, U_{p,max}, B_{max}, [r_{min},r_{max}]) + tes limites d’encombrement ((L_{max},W_{max},H_{max})), je peux te sortir **un résultat chiffré** : (V_{d,tot}), (N_{cyl}) minimal, puis l’architecture gagnante via (J) (avec un classement L/V/W/étoile).
