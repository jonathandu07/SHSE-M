D’accord. Avec ton cadre, on peut formaliser une **procédure calculable** qui sort :

1. **la cylindrée totale requise**,
2. **un nombre minimal de cylindres** (ou de “modules” SHSE-M),
3. puis **l’architecture** (ligne / V / W / étoile) comme un **problème d’encombrement + vibrations + complexité**.

Je te donne ci-dessous une formulation “fermée” (avec équations) qui reste fidèle à ton enchaînement (pas de magie, pas de valeurs inventées).

---

## 1) Cylindrée totale requise → (V_{d,tot})

On part de la puissance mécanique à fournir au vilebrequin (P_b) (si tu pars de (P_e), tu remontes avec les rendements comme tu l’as écrit).

Nombre de cycles/s :

* 2T : (f=\dfrac{n}{60})
* 4T : (f=\dfrac{n}{120})

Avec une pression moyenne indiquée (p_{mi}) :

[
P_i = p_{mi},V_{d,tot},f
\quad\Rightarrow\quad
V_{d,tot} = \frac{P_i}{p_{mi},f}
]

et avec rendement mécanique (\eta_m) :
[
P_b=\eta_m P_i
\Rightarrow
V_{d,tot}=\frac{P_b}{\eta_m,p_{mi},f}
]

---

## 2) Cylindrée admissible par cylindre → contrainte vitesse piston + alésage

Tu imposes une vitesse piston maximale (U_{p,max}) (durabilité) :

[
U_p = 2S\frac{n}{60}
\Rightarrow
S_{max}=\frac{30,U_{p,max}}{n}
]

Tu imposes une borne d’alésage (B\le B_{max}) (thermique/masse/efforts), et un ratio (r=S/B\in[r_{min},r_{max}]).

Alors :

[
S = rB \le S_{max}
\Rightarrow
B \le \frac{S_{max}}{r}
]

La cylindrée par cylindre :

[
V_{d,cyl}=\frac{\pi}{4}B^2S=\frac{\pi}{4}B^3r
]

Donc la **cylindrée max admissible par cylindre** (borne supérieure simple) :

[
B^*=\min!\left(B_{max},\frac{S_{max}}{r_{max}}\right)
\qquad
V_{d,cyl,max}\approx \frac{\pi}{4}(B^*)^3,r_{max}
]

---

## 3) Nombre minimal de cylindres

[
\boxed{
N_{cyl}=\left\lceil \frac{V_{d,tot}}{V_{d,cyl,max}}\right\rceil
}
]

Ensuite tu peux contraindre (N_{cyl}) à des valeurs “mécaniquement propres” (ordre d’allumage/équilibrage, selon ton vilebrequin) via un ensemble admissible (N\in\mathcal{N}) (ex. ({1,2,3,4,6,8,12,\dots})) :

[
N_{cyl}=\min{N\in\mathcal{N};|;N\ge V_{d,tot}/V_{d,cyl,max}}
]

---

## 4) Choix d’architecture = minimisation sous contraintes d’encombrement

Tu définis tes limites d’intégration :

* (L_{max},W_{max},H_{max}) (longueur/largeur/hauteur disponibles)
* éventuellement aire frontale max (A_{front,max}) (important si aéronautique)
* pénalités : vibration/irrégularité, complexité, masse.

On définit une fonction coût :

[
\boxed{
\text{Arch}^*=\arg\min_{\text{Arch}\in{\text{L},\text{V},\text{W},\text{étoile}}}
J(\text{Arch},N_{cyl})
}
]

avec contraintes :

[
L_{pkg}(\text{Arch},N_{cyl})\le L_{max},;
W_{pkg}\le W_{max},;
H_{pkg}\le H_{max}
]

et un coût typique :

[
J=
w_1\frac{L_{pkg}}{L_{max}}
+w_2\frac{W_{pkg}}{W_{max}}
+w_3\frac{H_{pkg}}{H_{max}}
+w_4,\text{VibIndex}(\text{Arch},N_{cyl})
+w_5,\text{Complex}(\text{Arch})
+w_6\frac{M_{est}}{M_{max}}
]

### Modèles d’encombrement (premier ordre, géométriques)

Si tu notes :

* (p_{cyl}) = pas entre cylindres (incluant parois + passages + paliers)
* (B) = alésage, (S) = course
* (H_{stack}\approx S + marges) (cylindre + culasse/couvercle + carter)

Alors :

**En ligne (L)**
[
L_{pkg}\approx N_{cyl},p_{cyl}
\quad;\quad
W_{pkg}\approx W_0
\quad;\quad
H_{pkg}\approx H_{stack}
]

**En V (angle (\alpha), (N) pair)**
[
L_{pkg}\approx \frac{N_{cyl}}{2},p_{cyl}
\quad;\quad
W_{pkg}\approx W_0 + 2,R\sin(\alpha/2)
\quad;\quad
H_{pkg}\approx H_0 + R\cos(\alpha/2)
]

**En W (3 bancs, (N) multiple de 3 ou 4 selon config)**
[
L_{pkg}\approx \frac{N_{cyl}}{3},p_{cyl}
\quad;\quad
W_{pkg},H_{pkg} \text{ augmentent (fortement) }
]
Pénalité complexité élevée.

**Étoile (radial)**
Très court en longueur, grand diamètre frontal :
[
L_{pkg}\approx L_0
\quad;\quad
A_{front}\approx \pi R^2
]
Souvent défavorable si contrainte d’aire frontale/traînée.

---

## 5) Règles de sélection (décision rapide dérivée de (J))

Une version “si/alors” (équivalente à une minimisation avec poids) :

* **Si** (L_{pkg}(\text{ligne})\le L_{max}) **et** simplicité prioritaire → **ligne**.
* **Sinon si** (N_{cyl}) est pair **et** (L_{pkg}(\text{V})\le L_{max}) → **V** (meilleur compromis compacité/complexité).
* **Sinon si** (N_{cyl}\ge 12) **et** longueur très contrainte → **W** (si tu acceptes la complexité).
* **Sinon si** longueur ultra-contrainte **et** aire frontale non critique → **étoile**.

---

## 6) Comment ton “déplaceur galet” s’insère dans ce choix

Ton déplaceur est un **galet** qui translate la paroi en maintenant l’étanchéité (sans tige). Ça impacte surtout :

* le **diamètre minimal** et la **largeur** du module (il faut de la place pour le guidage et la longueur de fuite/labyrinthe),
* le **pas (p_{cyl})** (donc (L_{pkg})),
* la **pénalité de complexité** (guidage/étanchéité) mais souvent **meilleure compacité axiale** qu’un déplaceur à tige longue.

Donc, dans la formulation ci-dessus :

* tu augmentes (p_{cyl}) et/ou (W_0) selon ton guidage,
* et tu ajustes (\text{Complex}(\cdot)).

---

## Formule finale compacte (ce que tu cherchais)

1. **Nombre de cylindres** :
   [
   \boxed{
   N_{cyl}=\left\lceil
   \frac{\frac{P_b}{\eta_m p_{mi} f}}
   {\frac{\pi}{4}(B^*)^3 r_{max}}
   \right\rceil,
   \quad
   B^*=\min!\left(B_{max},\frac{30U_{p,max}}{n,r_{max}}\right)
   }
   ]

2. **Architecture** :
   [
   \boxed{
   \text{Arch}^*=\arg\min_{\text{Arch}}
   \left[
   w_1\frac{L_{pkg}}{L_{max}}
   +w_2\frac{W_{pkg}}{W_{max}}
   +w_3\frac{H_{pkg}}{H_{max}}
   +w_4,\text{VibIndex}
   +w_5,\text{Complex}
   \right]
   ;;\text{sous};;
   L_{pkg}\le L_{max}, W_{pkg}\le W_{max}, H_{pkg}\le H_{max}
   }
   ]

---

Si tu me donnes **juste** : (P_b) (ou (P_e) + rendements), (n), (p_{mi}), (\eta_m), (U_{p,max}), (B_{max}), ([r_{min},r_{max}]), et tes limites (L_{max},W_{max},H_{max}), je peux te sortir **un résultat chiffré** : (V_{d,tot}), (N_{cyl}) minimal, puis l’architecture gagnante (avec classement ligne/V/W/étoile).


Ajouter un critère “usure/maintenance” revient à faire dépendre l’architecture non seulement de l’encombrement et des vibrations, mais aussi du **coût d’usure** (fréquence de remplacement des joints/pièces) et du **risque d’arrêt**. Cela pousse souvent vers **plus de cylindres** (donc charges unitaires plus faibles) si l’étanchéité est le point faible.

---

## 1) Introduire un critère d’usure/maintenance dans le choix

On ajoute au coût :

[
J ;=; \dots ;+; w_7,\text{MaintCost}(\text{Arch},N_{cyl})
;+; w_8,\text{DowntimeRisk}(\text{Arch},N_{cyl})
]

### 1.1 Coût de maintenance attendu

Définis :

* (N_{seal}(\text{Arch},N_{cyl})) : nombre total d’éléments d’étanchéité (segments/joints) dans le moteur,
* (L_{seal}) : durée de vie attendue d’un joint (en heures ou cycles),
* (C_{seal}) : coût joint + main-d’œuvre associée,
* (C_{stop}) : coût d’immobilisation par intervention,
* (T) : horizon d’usage (heures).

Nombre d’interventions attendues sur l’horizon :

[
N_{int}\approx \frac{T}{L_{seal}}
]

Coût :

[
\text{MaintCost}\approx N_{int}\left(N_{seal},C_{seal}+C_{stop}\right)
]

Cette formule fait apparaître un point clé : si tu augmentes (N_{cyl}), **(N_{seal}) augmente**, mais **l’usure par joint peut diminuer** si la charge unitaire et les pertes par fuite diminuent.

---

## 2) Lien direct entre “plus de cylindres” et usure des joints

L’idée physique : à puissance égale, plus de cylindres ⇒ moins de travail/couple/force par cylindre ⇒ **moins de pression/effort sur les étanchéités**, donc **moins de frottement**, donc **plus de durée de vie**.

### 2.1 Force max sur piston (ordre 1)

À pression max donnée (p_{max}) :

[
F_{g,max}=p_{max}A_p
\quad\text{avec}\quad
A_p=\frac{\pi}{4}B^2
]

Si tu gardes (B) identique et que tu répartis la puissance sur (N_{cyl}), en pratique tu peux viser une baisse de (p_{mi}) et/ou de (p_{max}) par cylindre (ou fonctionner à charge partielle plus souvent). Modèle simple :

[
p_{mi,cyl}\approx \frac{p_{mi,tot}}{N_{cyl}}
\quad(\text{approx si même }V_{d,cyl})
]

### 2.2 Usure (Archard) appliquée aux joints/segments

Avec la loi d’Archard :

[
V_w = k \frac{W,L_s}{H}
]

* (W) : charge normale (liée à la pression gaz + tension segment),
* (L_s) : distance de glissement cumulée (\approx 2S,N_{cycles}).

Si l’architecture / le dimensionnement permet de réduire la charge normale (W) (via baisse pression effective par cylindre), alors :

[
V_w \propto W
\Rightarrow
\text{usure} \downarrow \Rightarrow L_{seal} \uparrow
]

On peut modéliser la durée de vie joint comme inversement proportionnelle à la charge (modèle d’ingénierie) :

[
L_{seal}(N_{cyl}) \approx L_{seal,0}\left(\frac{W_0}{W(N_{cyl})}\right)^\beta
\quad (\beta>0)
]

Donc le coût maintenance devient :

[
\text{MaintCost}(N_{cyl})
\approx
\frac{T}{L_{seal,0}}\left(\frac{W(N_{cyl})}{W_0}\right)^\beta
\left(N_{seal}(N_{cyl})C_{seal}+C_{stop}\right)
]

Ce terme crée exactement le compromis que tu décris :

* (N_{cyl}) ↑ ⇒ (N_{seal}) ↑ (plus de joints),
* mais (W) ↓ ⇒ (L_{seal}) ↑ (joints plus durables),
* et au final, il existe un **optimum** de (N_{cyl}) qui minimise le coût.

---

## 3) Formulation pratique : choisir (N_{cyl}) non seulement par performance mais par usure

Au lieu de prendre seulement :

[
N_{cyl}=\left\lceil \frac{V_{d,tot}}{V_{d,cyl,max}}\right\rceil
]

tu choisis :

[
\boxed{
N_{cyl}^*=\arg\min_{N\in\mathcal{N}}
\Big(
J_{packaging}(N)+J_{vib}(N)+J_{complex}(N)+w_7,\text{MaintCost}(N)
\Big)
}
]

avec (N\ge N_{min}) (le minimum volumétrique imposé par la cylindrée admissible).

---

## 4) Règle de décision explicite (maintenance dominante)

Si tu constates (ou prévois) que :

* les joints sont la pièce limitante,
* il faut ouvrir souvent,
* et que l’arrêt coûte cher,

alors tu privilégies (N_{cyl}) plus élevé si et seulement si :

[
\boxed{
\frac{\Delta L_{seal}}{L_{seal}} ;>;
\frac{\Delta N_{seal}}{N_{seal}}
\quad \text{(gain de durée de vie relatif > surcoût joints relatif)}
}
]

Interprétation :

* si doubler le nombre de joints augmente leur nombre de 100%, mais multiplie leur durée de vie par >2, alors l’opération est gagnante (moins d’interventions).

---

## 5) Impact sur le choix d’architecture (ligne/V/W/étoile)

Le critère “usure” pousse aussi à préférer l’architecture qui :

* facilite l’accès et le remplacement des joints,
* limite les démontages lourds,
* réduit les risques de désalignement lors remontage (qui accélère l’usure).

Donc, à coût et encombrement comparables, tu ajoutes une pénalité :

[
\text{Serviceability}(\text{Arch}) \in [0,1]
]
et
[
\text{MaintCost}\leftarrow \frac{\text{MaintCost}}{\text{Serviceability}}
]
(plus c’est maintenable, plus le coût effectif baisse).

---

### Ajout final synthétique à ton texte (en une phrase “ingénierie”)

Le choix d’architecture doit être fait en minimisant un coût total intégrant **performance + encombrement + vibrations + complexité + maintenance**, et si l’étanchéité est limitante, il peut être optimal d’augmenter le nombre de cylindres pour réduire la charge et l’usure par cylindre, même si cela augmente le nombre total de joints, car la fréquence d’intervention peut chuter.

Si tu veux, je peux te donner une version “prête à coller” dans ton document (avec notations homogènes et une section dédiée “dimensionnement par coût d’usure”).
