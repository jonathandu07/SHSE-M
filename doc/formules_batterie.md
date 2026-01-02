Définition d’un dimensionnement “intelligent” = choisir **la capacité utile** de batterie pour que :

1. elle couvre un objectif d’énergie “tampon” (phases EV, transitoires, récupération),
2. elle soit rechargeable vite (moteur/générateur peu sollicité),
3. son **poids** ne dégrade pas plus qu’elle n’apporte.

Je te donne un cadre de calcul exploitable.

---

## 1) Notations

* (E_b) : énergie **totale** batterie (kWh)
* (E_u) : énergie **utile** (kWh) (fenêtre SOC)
* (w) : fenêtre SOC exploitable (ex. 0,6 si 80→20%)
  (\Rightarrow E_u = w,E_b)
* (P_{chg}) : puissance de charge électrique disponible (kW) (générateur → batterie, net)
* (t_{chg}) : temps cible pour “refaire” le tampon (h)
* (\eta_{chg}) : rendement charge global (générateur/électronique/batterie), typ. 0,75–0,9
* (\rho_E) : densité énergétique pack (kWh/kg), typ. 0,12–0,18 selon chimie/pack
* (m_b) : masse batterie (kg), (m_b = \dfrac{E_b}{\rho_E})
* (c_m) : surconsommation énergétique par kg (kWh/km/kg) (dépend du véhicule)

---

## 2) Contrainte “ratio recharge / capacité” (ton idée)

Tu fixes un objectif : la batterie doit pouvoir être “remise à niveau” rapidement.

**Formule simple :**
[
t_{chg} = \frac{E_u}{\eta_{chg},P_{chg}}
]
Donc :
[
E_u = \eta_{chg},P_{chg},t_{chg}
\quad\Rightarrow\quad
E_b = \frac{\eta_{chg},P_{chg},t_{chg}}{w}
]

C’est la première loi : **la capacité utile se dimensionne par un temps de recharge interne cible**.

---

## 3) Contrainte “usage” (tampon nécessaire)

Tu dois aussi dimensionner le tampon pour ce que tu veux absorber :

### a) Phase EV (optionnel, mais fréquent)

Si tu veux (d_{EV}) km en électrique (urbain), avec une conso électrique (e_{EV}) (kWh/km) :
[
E_{u,EV} = d_{EV},e_{EV}
]

### b) Transitoires / puissance

Si tu veux pouvoir fournir une puissance (P_{peak}) pendant (\Delta t) :
[
E_{u,peak} = \frac{P_{peak},\Delta t}{3600}
\quad (\text{kWh, si } \Delta t \text{ en secondes})
]

Tu prends le plus structurant (ou tu additionnes si tu veux couvrir les deux) :
[
E_u \ge E_{u,EV} + E_{u,peak}
]

---

## 4) Contrainte poids (coût énergétique de la batterie)

La batterie ajoute une pénalité d’énergie à déplacer sur la durée. Une approximation propre :

* Sur une mission typique (D) (km), la pénalité :
  [
  E_{pen} = c_m,m_b,D
  ]
  avec (m_b=\dfrac{E_b}{\rho_E}), donc :
  [
  E_{pen} = c_m,D,\frac{E_b}{\rho_E}
  ]

**Condition de cohérence “ça vaut le coup” :**
l’énergie que la batterie te permet d’économiser ou de récupérer sur la mission doit dépasser cette pénalité.

Sans modèle complet du véhicule, on peut au moins poser une borne simple :

### a) Si ton intérêt principal est la récupération au freinage

Soit (E_{rec}) l’énergie récupérable sur (D) km (kWh). Alors il faut :
[
E_u \lesssim E_{rec}
]
Sinon tu portes une capacité qui ne se remplit jamais.

### b) Si ton intérêt principal est de décaler le thermique vers son rendement optimal

Tu cherches un tampon suffisant pour lisser la demande, mais pas trop grand : typiquement tu choisis (E_u) pour que le thermique tourne par “sessions” courtes.

---

## 5) Formule de dimensionnement pratique (en 3 étapes)

### Étape A — Fixer une cible de temps de recharge interne

Choisis (t_{chg}) (ex. 6–15 minutes = 0,10–0,25 h)

[
E_{u,ratio}=\eta_{chg},P_{chg},t_{chg}
]

### Étape B — Fixer l’énergie utile minimale “usage”

[
E_{u,usage}= \max\left(E_{u,EV},;E_{u,peak},;E_{rec}\ \text{(si connu)}\right)
]

### Étape C — Choisir l’énergie utile finale

[
E_u = \max\left(E_{u,ratio},;E_{u,usage}\right)
]
Puis :
[
E_b=\frac{E_u}{w},\qquad
m_b=\frac{E_b}{\rho_E}
]

Et tu vérifies que le poids reste acceptable via (E_{pen}).

---

## 6) Raccourci utile : “capacité optimale” par compromis recharge/poids

Si tu veux une règle unique à optimiser, tu peux minimiser un coût simple :

[
J(E_b)=\alpha,t_{chg}(E_b)+\beta,m_b(E_b)
]
avec
[
t_{chg}=\frac{wE_b}{\eta_{chg}P_{chg}},\quad m_b=\frac{E_b}{\rho_E}
]

Ça montre un fait important : **si tu ne mets que “temps de recharge” et “poids”, la solution tend vers “batterie la plus petite possible”**.
Donc il faut **forcément** ajouter une contrainte d’usage (EV, transitoires, récupération) pour éviter une batterie ridicule.

---

## 7) Exemple numérique (pour voir la mécanique)

Hypothèses :

* (P_{chg}=25) kW net
* (\eta_{chg}=0,85)
* (t_{chg}=0,20) h (12 min)
* (w=0,6)
* (\rho_E=0,15) kWh/kg

Alors :
[
E_{u,ratio}=0,85\times 25\times 0,20=4,25\ \text{kWh}
]
[
E_b=\frac{4,25}{0,6}=7,08\ \text{kWh}
]
[
m_b=\frac{7,08}{0,15}\approx 47\ \text{kg}
]

Donc tu obtiens une batterie **modérée**, rechargeable rapidement, pas trop lourde.

---

## Ce qu’il te manque pour rendre ça “très précis”

Si tu me donnes ces 6 paramètres, je te sors une formule “finale” adaptée au cas, avec chiffres :

1. (P_{chg}) (kW) disponible (ou puissance moteur + rendement générateur)
2. (t_{chg}) cible (minutes)
3. fenêtre SOC (w) (ex. 60%)
4. densité pack (\rho_E) (ou chimie + masse pack estimée)
5. objectif EV : (d_{EV}) et (e_{EV}) (ou conso électrique estimée)
6. masse véhicule / segment (pour estimer (c_m) et (E_{rec}))

Sans ça, les équations ci-dessus restent le bon cadre : **tu dimensionnes par (usage) + (temps de recharge interne), puis tu vérifies que le poids ne ruine pas l’intérêt.**
