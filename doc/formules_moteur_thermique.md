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


Oui — avec ce cadre, tu peux **déduire les dimensions de l’arbre**, mais pas “magiquement” : tu dois passer par **le couple à transmettre**, puis vérifier **torsion + fatigue + flexion + rigidité + vitesse critique + clavette/cannelures + paliers**. Le cadre que tu as recopié te donne déjà ce qu’il faut pour obtenir le couple (via (P_b) et (n)), donc tu peux enchaîner vers l’arbre.

Voici les **formules** (arbre de sortie vilebrequin et/ou arbre vers boîte à crabots) en version dimensionnement.

---

## 1) Couple à transmettre (point de départ)

À partir de la puissance mécanique disponible (P_b) et du régime (n) :

[
\omega = \frac{2\pi n}{60}
\qquad
T = \frac{P_b}{\omega}
]

Pour le dimensionnement, utilise un couple de calcul :

[
T_d = K_s , T
]

* (K_s) = facteur de service (à-coups/irrégularités). Si engagement crabot, (K_s) doit être **plus élevé** qu’une transmission lisse.

---

## 2) Diamètre en torsion (arbre plein)

Contrainte de cisaillement max en torsion :

[
\tau_{max} = \frac{16T_d}{\pi d^3}
]

Imposer :

[
\tau_{max} \le \tau_{adm}
\quad\Rightarrow\quad
d \ge \left(\frac{16T_d}{\pi \tau_{adm}}\right)^{1/3}
]

C’est la **première** formule qui donne un diamètre minimal.

---

## 3) Si arbre creux (souvent intéressant masse/rigidité)

Pour un arbre creux de diamètre extérieur (D) et intérieur (d_i) :

[
\tau_{max}=\frac{16T_d}{\pi D^3\left(1-\left(\frac{d_i}{D}\right)^4\right)}
]

Imposer (\tau_{max}\le\tau_{adm}) pour dimensionner (D) (ou le ratio (d_i/D)).

---

## 4) Flexion (efforts radiaux : pignons, crabots, poulies, désalignement)

Même si tu transmets “que du couple”, en pratique tu as des forces radiales (pignons, embrayage/crabot, courroie, etc.). Tu dois vérifier la flexion.

Moment fléchissant max (M) (selon schéma de paliers / porte-à-faux). Formule de contrainte de flexion :

[
\sigma_b=\frac{32M}{\pi d^3}
]

---

## 5) Combinaison torsion + flexion (critère de Von Mises)

Contrainte équivalente :

[
\sigma_{eq}=\sqrt{\sigma_b^2+3\tau_{max}^2}
]

Imposer :

[
\sigma_{eq} \le \sigma_{adm}
]

C’est la formule propre quand ton arbre voit à la fois couple et flexion.

---

## 6) Fatigue (indispensable si cycles élevés)

Tu as un arbre qui tourne en continu → fatigue.

Tu prends les composantes alternées et moyennes :

* flexion rotative : (\sigma_a \approx \sigma_b), (\sigma_m \approx 0) (souvent)
* torsion fluctuante : (\tau_a), (\tau_m) selon ton profil de charge

Critère Goodman (ou Soderberg) en équivalent :

[
\frac{\sigma_{a,eq}}{\sigma_D}+\frac{\sigma_{m,eq}}{R_u}\le 1
]

avec :

[
\sigma_{a,eq}=\sqrt{\sigma_a^2+3\tau_a^2}
\quad,\quad
\sigma_{m,eq}=\sqrt{\sigma_m^2+3\tau_m^2}
]

---

## 7) Rigidité torsionnelle (limiter l’angle et les chocs crabots)

Angle de torsion sur une longueur (L) :

[
\theta = \frac{T_d L}{GJ}
]

* (G) module de cisaillement
* (J=\frac{\pi d^4}{32}) (arbre plein)

Pour protéger un crabot, tu fixes une limite (\theta \le \theta_{max}) et tu en déduis (d).

---

## 8) Vitesse critique (vibrations / flambage dynamique)

Vérifier que la vitesse de rotation est suffisamment loin de la 1ère vitesse critique (simplifié type Jeffcott) :

[
\omega_c \approx \sqrt{\frac{k}{m}}
]

où (k) dépend de la rigidité en flexion (fonction de (EI) et des appuis).
Sans modèle de paliers et de porte-à-faux, tu ne peux pas chiffrer correctement, mais la vérification est obligatoire si arbre long/fin.

---

## 9) Liaison arbre–moyeu : clavette ou cannelures (souvent dimensionnante)

### 9.1 Clavette (ordre 1)

Force tangentielle à rayon (r=d/2) :

[
F_t=\frac{T_d}{r}=\frac{2T_d}{d}
]

Cisaillement clavette (section (b_k L_k)) :

[
\tau_k=\frac{F_t}{b_k L_k}
]

Écrasement (portée (h_k L_k)) :

[
\sigma_{bear}=\frac{F_t}{h_k L_k}
]

Imposer (\tau_k\le\tau_{adm}) et (\sigma_{bear}\le\sigma_{adm}).

### 9.2 Cannelures

Même logique mais meilleure répartition. On impose une pression de contact admissible.

---

## Conclusion nette

* **Oui**, avec ton cadre tu peux déduire l’arbre, parce que tu obtiens (P_b) et (n) → donc (T).
* Ensuite, l’arbre se dimensionne par :

  1. torsion (diamètre mini)
  2. flexion + torsion (von Mises)
  3. fatigue (Goodman)
  4. rigidité (angle)
  5. liaison (clavette/cannelures)
  6. vitesse critique (si nécessaire)

---

Si tu veux que je te donne une **formule finale “diamètre minimal”** directement exploitable, il me manque uniquement :

* (P_b) (kW) et (n) (tr/min)
* matériau (ou (\sigma_{adm}) / (\tau_{adm}))
* longueur libre (L) et si tu as un porte-à-faux (m)
* type de liaison (clavette/cannelures) et rayon roue/pignon si effort radial

Sans ça, je ne peux pas être “précis” numériquement, mais les équations ci-dessus sont exactement celles qui permettent de le déduire correctement.


Oui, tu peux **déduire le nombre de vis et leurs dimensions** à partir de ce cadre — à condition de connaître (ou de borner) : **pression max**, **surface pressurisée**, **type de joint**, **matériau/classe de vis**, et **marges de sécurité**.

Voici les équations utilisables.

---

## 1) Effort qui “ouvre” le couvercle (séparation)

### 1.1 Force de séparation due à la pression

[
F_{sep}=p_{max},A_{eff}
]

* (A_{eff}) : aire effectivement pressurisée “vue” par le couvercle
  (souvent proche de l’aire intérieure délimitée par le joint)

---

## 2) Précharge totale nécessaire (ne pas ouvrir + étancher)

Tu dois appliquer une précharge totale (F_{pre,tot}) telle que :

[
F_{pre,tot}\ge \gamma_s,F_{sep}+F_{gasket}
]

* (\gamma_s) : facteur de sécurité (ex. 1,2 à 2 selon chocs/vibrations)
* (F_{gasket}) : charge minimale imposée par le joint pour assurer l’étanchéité

### 2.1 Modèle simple de charge joint

Si le fabricant du joint donne une contrainte de serrage (q) (Pa) et une aire de contact (A_g) :
[
F_{gasket}=q,A_g
]
Sinon, on fixe (q) par hypothèse d’ingénierie (mais là ce n’est plus “précis”).

---

## 3) Nombre de vis (N_b) (répartition de la précharge)

Si tu choisis (N_b) vis identiques :
[
F_{pre,bolt}=\frac{F_{pre,tot}}{N_b}
]

Mais (N_b) ne se choisit pas que par la force : il faut aussi respecter l’**étanchéité locale** du plan de joint.

### 3.1 Critère d’espacement pour étanchéité

Le plan de joint ne doit pas “bailler” entre vis. Une règle calculatoire basique :

* effort linéique à tenir sur le pourtour :
  [
  f=\frac{F_{pre,tot}}{P}
  ]
  où (P) est le périmètre du joint.

* si l’espacement entre vis est (s), la charge disponible par tronçon est (f,s).
  On impose un espacement max (s \le s_{max}) (dépend rigidité couvercle/carter/joint).

Sans calcul de plaque (rigidité), on ne peut pas donner (s_{max}) exact, mais tu peux **déduire (N_b)** dès que tu fixes un espacement cible :
[
N_b \approx \left\lceil \frac{P}{s} \right\rceil
]

---

## 4) Dimension d’une vis (résistance en traction)

La contrainte de traction dans la section résistante (A_s) du filetage :

[
\sigma_b=\frac{F_{pre,bolt}}{A_s}\le \sigma_{adm,b}
]

Donc :
[
A_s \ge \frac{F_{pre,bolt}}{\sigma_{adm,b}}
]

Tu choisis ensuite un diamètre normalisé (M6, M8, M10…) dont (A_s) est ≥ au besoin.

**Remarque importante :** la précharge utile est souvent prise comme une fraction de la limite élastique de la vis :
[
F_{pre,bolt} \approx 0{,}7,A_s,R_{p0.2}
]
(donc la vis doit être capable de porter cette précharge sans plastifier)

---

## 5) Couple de serrage (pour atteindre la précharge)

Approximation classique :
[
M \approx K,F_{pre,bolt},d
]

* (d) diamètre nominal
* (K) ~ 0,18–0,25 (selon lubrification/frottements)

---

## 6) Vérifications complémentaires (souvent dimensionnantes)

### 6.1 Écrasement sous tête / rondelle (portée)

[
p_{head}=\frac{F_{pre,bolt}}{A_{bearing}} \le p_{adm}
]

### 6.2 Arrachement du taraudage (si vis dans aluminium / fonte)

Capacité d’arrachement dépend de la longueur d’engagement (L_e) :
[
F_{strip} \propto d,L_e,\tau_{adm,mat}
]
Donc on impose :
[
L_e \ge k,d
]
avec (k) typiquement plus grand dans matériaux faibles (alu).

### 6.3 Flèche du couvercle (rigidité)

Si couvercle trop souple, la pression le bombe et l’étanchéité fuit même si les vis “tiennent”.
Ça se traite par calcul de plaque (au moins une vérification).

---

## Réponse directe

Oui, tu peux déduire :

* **la force totale à reprendre** : (F_{sep})
* **la précharge totale** : (F_{pre,tot})
* **le nombre de vis** via espacement/perimètre : (N_b \approx \lceil P/s\rceil)
* **le diamètre de vis** via (A_s \ge F_{pre,bolt}/\sigma_{adm,b})

Mais pour que ce soit réellement “précis”, il faut au minimum :

1. (p_{max})
2. (A_{eff}) et le périmètre (P) du joint
3. type de joint (donc (q) ou une exigence d’écrasement)
4. matériau et classe des vis (pour (\sigma_{adm,b}))
5. rigidité couvercle/carter (ou un espacement cible (s))

Si tu me donnes (p_{max}), le diamètre intérieur du joint (ou (A_{eff})) et le type de joint (torique, papier, métal…), je peux te sortir une méthode complète “choix (N_b) + choix Mx” en équations + un exemple chiffré.


Oui, tu peux **déduire la forme et les dimensions minimales du couvercle**, mais là encore ce n’est pas une seule formule : c’est un dimensionnement **par rigidité + contrainte + étanchéité**. La pression tend à **bombé** le couvercle, ce qui fait fuir le joint même si les vis tiennent. Donc on dimensionne surtout :

1. **géométrie (forme)** pour être rigide,
2. **épaisseur** pour limiter flèche et contraintes,
3. **répartition vis/joint**.

Je te donne les équations utiles.

---

## 1) Effort et charge sur le couvercle

Pression interne (p), surface pressurisée (A_{eff}).
Force globale :

[
F_{sep}=p,A_{eff}
]

Pour le calcul de plaque, on utilise directement la **charge uniforme** :

[
q=p \quad (\text{Pa} = \text{N/m}^2)
]

---

## 2) Choisir la forme (ce que tu peux “déduire”)

Sous pression, la rigidité augmente très fortement si tu passes d’une plaque plane à :

* **couvercle bombé (dôme)**
* ou **couvercle nervuré (raidisseurs)**
* ou **couvercle épaissi en couronne** autour du joint/vis

Critère : minimiser la flèche au niveau du joint.

Donc la “forme” se déduit d’un objectif mécanique :

[
w_{max} \le w_{adm}
]

où (w_{adm}) est la flèche admissible pour garder l’écrasement du joint.

---

## 3) Épaisseur par calcul de plaque (couvercle circulaire)

Cas fréquent : couvercle circulaire de rayon (a), épaisseur (t), pression uniforme (p).
Rigidité de plaque :

[
D=\frac{E t^3}{12(1-\nu^2)}
]

### 3.1 Flèche maximale (ordre de grandeur)

Pour une plaque circulaire **encastrée** (cas assez proche si serrage rigide) :

[
w_{max} \approx C_w \frac{p a^4}{D}
]

où (C_w) est une constante dépendant des appuis (encastré/posé).
L’important : (w_{max} \propto \frac{p a^4}{t^3}).

Donc, en isolant (t) :

[
t \ge \left(\frac{C_w,p,a^4}{w_{adm}}\cdot\frac{12(1-\nu^2)}{E}\right)^{1/3}
]

C’est la formule de base “anti-fuite par bombement”.

### 3.2 Contrainte de flexion max

Toujours en plaque circulaire :

[
\sigma_{max} \approx C_\sigma \frac{p a^2}{t^2}
]

Imposer :

[
\sigma_{max}\le \sigma_{adm}
\quad\Rightarrow\quad
t \ge \sqrt{\frac{C_\sigma,p,a^2}{\sigma_{adm}}}
]

Tu prends ensuite le (t) le plus grand entre la condition flèche et la condition contrainte.

---

## 4) Cas couvercle rectangulaire (si ta forme est plutôt “carter”)

Même logique :

[
w_{max} \propto \frac{p,L^4}{E t^3}
\quad,\quad
\sigma_{max}\propto \frac{p,L^2}{t^2}
]

avec (L) la dimension caractéristique (souvent le plus grand côté).

---

## 5) Dimensionnement du bourrelet / portée de joint

Le joint demande une pression de contact minimale (p_{seal}).
Si l’aire de portée du joint est (A_g) :

[
F_{gasket}=p_{seal},A_g
]

Tu dois garantir que la pression de contact reste ≥ (p_{seal}) partout, donc :

[
\Delta w_{joint} \le \Delta w_{adm}
]

où (\Delta w_{joint}) est la variation de flèche sur la zone du joint (ce qui crée des zones “décompressées”).

C’est pour ça que :

* on épaissit une **couronne** autour du joint,
* on met des **nervures**,
* on met les **vis proches** du joint.

---

## 6) Vis : influence directe sur la forme du couvercle

Les vis imposent :

* une “ligne d’appui” (encastrement plus ou moins vrai),
* une contrainte locale sous tête,
* des risques de flambement local / ovalisation.

Tu choisis la géométrie autour de chaque vis pour que :

[
p_{head}=\frac{F_{pre,bolt}}{A_{bearing}} \le p_{adm}
]

D’où :

* bossage autour de vis,
* rondelles larges,
* épaisseur locale suffisante.

---

## 7) En résumé (réponse directe)

Oui, tu peux déduire :

* **forme minimale** : circulaire/rectangulaire, plane ou bombée/nervurée, en fonction de l’objectif (w_{max}) (étanchéité).
* **épaisseur** par :

  * flèche (t \propto (p a^4 / w_{adm})^{1/3})
  * contrainte (t \propto \sqrt{p a^2 / \sigma_{adm}})
* **géométrie de portée** du joint et des bossages de vis via pression de contact.

---

## Ce qu’il me faut pour te donner une formule “précise” pour TON couvercle

1. forme (cercle/rectangle) et dimension intérieure pressurisée (rayon (a) ou côtés)
2. (p_{max})
3. matériau du couvercle : (E), (\nu), (\sigma_{adm})
4. type de joint et tolérance de flèche admissible (w_{adm}) (ou compression joint)
5. position/nb de vis (ou espacement cible)

Avec ces 5 éléments, je peux te sortir un dimensionnement complet : **épaisseur mini**, **besoin de nervures/dôme**, **dimensions de la couronne du joint**, et **bossages vis**.


Oui, on peut **déduire une sélection de matériaux plausibles** à partir de tes contraintes **thermiques** (conduction, gradient, tenue à chaud, oxydation) et **mécaniques** (pression, fatigue, fluage), mais pas un “unique matériau certain” : on obtient un **classement** et des **choix recommandés** par zone (côté chaud / côté froid / tuyaux hélicoïdaux / interfaces).

Je te donne une méthode **calculable** (indices + contraintes) puis des familles matériaux typiques.

---

## 1) Ton architecture implique 3 zones matériaux

1. **Zone chaude** (gaz d’échappement + combustion interne, gradients forts)
2. **Zone froide** (refroidissement eau, température plus basse, corrosion eau)
3. **Tuyaux hélicoïdaux / échangeurs** (fort flux thermique + pression interne + cycles thermiques)

Donc, en pratique : **matériaux différents** ou au minimum **chemise/insert**.

---

## 2) Les contraintes physiques qui gouvernent le choix

### 2.1 Thermique : conduction + résistance aux chocs thermiques

* Conduction : (k) (W/m·K)
* Dilatation : (\alpha) (1/K)
* Module : (E) (Pa)
* Résistance : (\sigma_f) (Pa) (ou limite élastique à la température considérée)
* Tenue au choc thermique (indice utile) :

[
R_{TS} \propto \frac{\sigma_f , k}{E ,\alpha}
]

Plus (R_{TS}) est grand, plus le matériau encaisse les gradients sans fissurer.

### 2.2 Mécanique à chaud : fluage (le vrai tueur côté chaud)

À haute température, la limite élastique “à froid” ne suffit plus : il faut une contrainte admissible **au temps**.

Tu raisonnes sur une contrainte admissible (\sigma_{adm}(T, t)) fournie par les courbes matériau (fluage/rupture). Conceptuellement :

[
\sigma_{service} \le \sigma_{adm}(T, t_{life})
]

Sans courbes, on ne peut pas “calculer”, mais on peut **déduire la famille** (aciers inox réfractaires / superalliages) si (T) est élevé.

### 2.3 Corrosion/oxydation

* côté échappement : oxydation chaude + suies + condensation acide possible (selon carburant)
* côté eau : corrosion + cavitation (pompe) + dépôts

---

## 3) Ce que tu peux “déduire” comme familles matériaux (logique de sélection)

### A) Tuyaux hélicoïdaux côté échappement (chaud)

Objectif : **tenir à chaud + oxydation** + cycles thermiques.

* Si (T_{paroi}) modéré (typiquement “échappement chaud mais pas rouge”) :

  * **inox austénitique** : 304L/316L (résistance corrosion, mais tenue à chaud limitée)
  * mieux : **321 / 347** (stabilisés, meilleure tenue à chaud)

* Si (T_{paroi}) élevé (échappement très chaud, gradients, cycles) :

  * **inox réfractaires** type 309 / 310 (plus de Cr/Ni, meilleure oxydation à chaud)
  * si très sévère : **Inconel 625/718** (superalliage Ni) — excellent à chaud mais coûteux

**Déduction** : plus tu montes en température paroi, plus tu dois aller vers **309/310** puis **superalliage**.

### B) Tuyaux hélicoïdaux côté eau (froid/tiède)

Objectif : **conductivité correcte + corrosion eau + coût**.

* **Cuivre** : très bon (k), mais tenue mécanique/temperature limitée, sensible à certains environnements (et brasage).
* **Cupronickel** : meilleur en eau, bon échange, plus robuste.
* **Inox 316L** : très bon contre corrosion, mais (k) faible → échange moins bon, compenser par surface.
* **Aluminium** : très bon (k), léger, mais corrosion eau / couples galvaniques à gérer.

**Déduction** : si tu veux compacité échangeur → cuivre/cupronickel ; si tu veux robustesse/corrosion → 316L.

### C) Cylindre / chambre (pièce critique pression + thermique)

Ici le besoin est paradoxal : tu veux **bon échange thermique** mais aussi **résistance/fatigue** et tenue au chaud.

En moteurs thermiques, le classique est :

* **côté structure** : acier/alloy ou fonte (résistance, stabilité dimensionnelle)
* **côté échange** : inserts / chemise / traitements

Familles plausibles :

* **Fonte alliée** (stabilité, usure, bon amortissement, mais (k) moyen)
* **Aciers alliés** (résistance, mais gestion usure/traitement nécessaire)
* **Inox réfractaire / Ni** si la zone chaude est très haute température (mais usinage/coût)

**Déduction** :

* Si la chambre “voit” la flamme et donc un (T) local élevé + cycles : il faut une famille **tenue à chaud** (inox réfractaire ou superalliage) au moins en **insert**.
* Pour la zone de glissement (piston/cylindre), on privilégie un matériau avec **bon comportement tribologique** (fonte/chemise dédiée + traitement).

---

## 4) Méthode formelle (pour choisir sans “inventer”)

Tu fais une sélection par contraintes :

### Étape 1 — Température de paroi (ordre de grandeur)

Échange convection + conduction :

[
q = h_{gas}(T_{gas}-T_{w,hot})
]
[
q = \frac{k}{t}(T_{w,hot}-T_{w,cold})
]
[
q = h_{water}(T_{w,cold}-T_{water})
]

Cela te permet d’estimer (T_{w,hot}) (température paroi chaude). C’est le paramètre qui fait basculer inox ↔ réfractaire ↔ superalliage.

### Étape 2 — Contraintes mécaniques

Cylindre sous pression : Lamé ou mince :
[
\sigma_\theta(r_i) \le \sigma_{adm}(T)
]
et pour la durée :
[
\sigma_{service} \le \sigma_{adm}(T,t_{life})
]

### Étape 3 — Choc thermique

Indice de tenue :
[
R_{TS} \propto \frac{\sigma_f k}{E\alpha}
]
Tu compares les familles.

---

## 5) Conclusion pratique (ce que je “déduis” de ta description)

* Tes **tuyaux échappement** doivent probablement être en **inox stabilisé/haute température** (321/347, ou 309/310 si très chaud).
* La partie très exposée au chaud dans le cylindre/chambre devrait être au minimum un **insert** en matériau **tenue à chaud / oxydation** si la paroi voit directement la flamme.
* Le côté eau peut être en **316L** si tu privilégies la corrosion, ou en **cuivre/cupronickel** si tu veux maximiser le transfert thermique (au prix d’une conception anti-corrosion galvanique).

---

## Point bloquant (à ne pas masquer)

Pour “déduire” précisément (et pas seulement choisir une famille), il manque une donnée déterminante : **la température de paroi attendue** (ou à défaut (T_{gas}), (T_{water}), (h_{gas}), (h_{water}), épaisseurs). Sans ça, on ne sait pas si tu es en régime “inox standard” ou “réfractaire/superalliage”.

Si tu donnes :

* (T_{gas}) (échappement), (T_{water}),
* épaisseur paroi (t) visée,
* pression (p_{max}),
* durée de vie cible,
  je peux te rendre un tableau “zone → famille matériau → justification par indices (fluage / choc thermique / corrosion)”.


Je donne ci-dessous un **jeu de formules** couvrant les 6 blocs manquants (thermique, p–V/p(θ), fuites/étanchéité, lubrification/frottements, paliers, vibrations/équilibrage). Ce sont des **relations de dimensionnement** (1er ordre) : ensuite, on affine par corrélations/FEA/essais selon ton niveau d’exigence.

---

## A) Bilan thermique complet (gaz ↔ paroi ↔ eau)

### A.1 Puissance thermique échangée (fluide)

Gaz :
[
\dot Q_{gaz}= \dot m_{gaz},c_{p,g},(T_{gaz,in}-T_{gaz,out})
]
Eau :
[
\dot Q_{eau}= \dot m_{eau},c_{p,e},(T_{eau,out}-T_{eau,in})
]

### A.2 Échangeur : méthode LMTD

Différence moyenne logarithmique :
[
\Delta T_{lm}=\frac{\Delta T_1-\Delta T_2}{\ln(\Delta T_1/\Delta T_2)}
]
avec (contre-courant typique) :
[
\Delta T_1=T_{gaz,in}-T_{eau,out},\quad \Delta T_2=T_{gaz,out}-T_{eau,in}
]
Puissance :
[
\dot Q = U,A,\Delta T_{lm}
]

### A.3 Coefficient global (U) (résistances en série)

[
\frac{1}{U A}=\frac{1}{h_{gaz}A}+\frac{t}{kA}+\frac{1}{h_{eau}A}+R_{fouling}
]
où (t) = épaisseur paroi, (k)=conductivité, (R_{fouling})=encrassement.

### A.4 Convection : Nusselt (corrélations de base)

Définition :
[
Nu=\frac{hD_h}{k_f}
]
Nombre de Reynolds :
[
Re=\frac{\rho v D_h}{\mu}
]
Prandtl :
[
Pr=\frac{c_p\mu}{k_f}
]
Turbulent (Dittus-Boelter, ordre 1) :
[
Nu=0.023,Re^{0.8},Pr^{n}\quad(n\approx 0.4 \text{ chauffage},,0.3 \text{ refroidissement})
]
Donc :
[
h=\frac{Nu,k_f}{D_h}
]

### A.5 Températures de paroi (avec flux (q''))

Flux surfacique :
[
q''=\frac{\dot Q}{A}
]
Sauts de température :
[
T_{w,hot}=T_{gaz}-\frac{q''}{h_{gaz}}
]
[
T_{w,cold}=T_{eau}+\frac{q''}{h_{eau}}
]
Conduction paroi :
[
T_{w,hot}-T_{w,cold}=q'',\frac{t}{k}
]

### A.6 Contraintes thermiques (pièce bridée)

[
\sigma_{th}\approx \frac{E\alpha,\Delta T}{1-\nu}
]
((\Delta T) = gradient pertinent, (\alpha)=dilatation).

### A.7 Fatigue thermique (contrainte alternée)

Si (\Delta T) cyclique :
[
\sigma_{a,th}\approx \frac{E\alpha,\Delta T_a}{1-\nu}
]
Puis critère fatigue (Goodman) :
[
\frac{\sigma_a}{\sigma_D}+\frac{\sigma_m}{R_u}\le 1
]

---

## B) Modèle cycle : volumes, pression, (p(\theta)), travail

Tu as un mécanisme “déplaceur + piston puissance”. Sans modèle exact, on fait un **modèle paramétré**.

### B.1 Cinématique piston puissance (bielle-manivelle)

Avec (r=S/2), (l)=bielle, (\omega=2\pi n/60).
Position piston (approx classique) :
[
x(\theta)=r(1-\cos\theta)+\frac{r^2}{4l}(1-\cos2\theta)
]
Volume côté piston :
[
V(\theta)=V_c + A_p,x(\theta)
]

### B.2 Déplaceur (phasage)

Si le déplaceur est sinusoïdal (approx) avec avance (\phi) :
[
x_d(\theta)=x_{d0}+X_d\cos(\theta+\phi)
]
Tu en déduis les volumes “chaud” et “froid” (modèle géométrique) :
[
V_h(\theta)=V_{h0}+f_h(x_d(\theta))
]
[
V_c(\theta)=V_{c0}+f_c(x_d(\theta))+A_p,x(\theta)
]
(les fonctions (f_h,f_c) dépendent de ta géométrie interne : c’est ici que tu “définis” ton architecture.)

### B.3 Pression : modèle isotherme multi-zones (ordre 1)

Si tu assumes deux zones à températures quasi constantes (T_h) et (T_c) (très simplifié) et masse totale (m) :
[
p(\theta)=\frac{mR}{\frac{V_h(\theta)}{T_h}+\frac{V_c(\theta)}{T_c}}
]
C’est une formule clé : elle te donne (p(\theta)) dès que tu fixes (V_h,V_c,T_h,T_c,m).

### B.4 Travail indiqué et puissance

Travail par cycle :
[
W_i=\oint p,dV
]
Discrétisé :
[
W_i\approx \sum_k p(\theta_k),[V(\theta_{k+1})-V(\theta_k)]
]
Puissance indiquée :
[
P_i=W_i\cdot \text{cycles/s}
]
Couple moyen :
[
\bar T=\frac{P_b}{\omega}
]

---

## C) Étanchéité / fuites / “nombre de joints”

Le “nombre de joints” se déduit en imposant une **fuite max admissible** et en comparant la fuite calculée à celle admissible, en incluant le frottement induit.

### C.1 Fuite dans un jeu annulaire (Poiseuille, ordre 1)

Pour un anneau (jeu radial (h\ll r)), longueur de fuite (L), viscosité (\mu), rayon moyen (r) :
[
Q \approx \frac{\pi r,h^3}{6\mu L},\Delta p
]
Débit massique :
[
\dot m=\rho,Q
]
(Plus (L) est grand, plus la fuite diminue. Ajouter des segments/joints augmente (L_{eff}) et/ou réduit (h).)

### C.2 Fuite compressible (approx) — si (\Delta p) grand

On utilise souvent une loi “orifice” (majorante) :
[
\dot m \approx C_d A \sqrt{2\rho,\Delta p}
]
utile pour borner si tu suspectes turbulence/local.

### C.3 Critère de choix (fuite vs frottement)

Imposer :
[
\dot m \le \dot m_{max}
]
et minimiser la puissance perdue par frottement des joints :
[
P_f \approx F_f,v
]

### C.4 Frottement d’un joint/segment (modèle simple)

Force normale d’appui (N) (tension segment + pression gaz) :
[
F_f=\mu_f,N
]
Vitesse de glissement moyenne (piston) :
[
v_{moy}=2S\frac{n}{60}
]
Puissance frottement (ordre 1) :
[
P_f \approx F_f,v_{moy}
]
Donc tu choisis le **nombre minimal** de joints tel que (\dot m) soit OK tout en gardant (P_f) faible.

---

## D) Lubrification / frottements / usure

### D.1 Film d’huile : nombre de Sommerfeld (palier lisse)

Pour un palier lisse (diamètre (d), longueur (L), jeu radial (c), vitesse (\omega), viscosité (\mu), charge (W)) :
[
S=\frac{\mu,\omega}{p}\left(\frac{r}{c}\right)^2,\quad p=\frac{W}{Ld}
]
(S) gouverne le régime (hydrodynamique vs mixte). (Les abaques donnent excentricité, épaisseur de film min.)

### D.2 Puissance perdue par frottement (palier lisse, ordre 1)

[
P_{f,bear}\approx f,W,v
]
où (f) est un coefficient (fonction de (S)), (v=\omega r).

### D.3 Usure (Archard)

[
V_w=k,\frac{W,L_s}{H}
]
Distance de glissement cumulée :
[
L_s \approx 2S,N_{cycles}
]
Perte d’épaisseur moyenne :
[
\Delta h\approx \frac{V_w}{A}
]
Critère durée de vie :
[
\Delta h \le \Delta h_{max}
]

---

## E) Paliers (roulements ou paliers lisses)

### E.1 Charges : à partir des efforts (déjà dans ton cadre)

Charge radiale/axiale vient de :

* force gaz/inertie via bielle/vilebrequin,
* efforts transmission (pignons/courroies),
* précharges.

### E.2 Roulements : durée de vie (L_{10})

Charge dynamique équivalente :
[
P=X F_r + Y F_a
]
Vie en millions de tours :
[
L_{10}=\left(\frac{C}{P}\right)^p
]
avec (p=3) (billes) ; (p=10/3) (rouleaux).
Heures de vie :
[
L_{10h}=\frac{10^6,L_{10}}{60n}
]

### E.3 Paliers lisses : critère (p)–(v) et température

Pression moyenne :
[
p=\frac{W}{Ld}
]
Vitesse de glissement :
[
v=\omega r
]
Critère industriel :
[
p,v \le (p,v)_{adm}
]

---

## F) Vibrations, équilibrage, volant d’inertie, torsion dynamique

### F.1 Couple ondulant : composante variable

Tu peux obtenir un couple instantané avec :
[
T(\theta)\approx F_{rod}(\theta),r,\sin\theta
]
Puis ondulation :
[
\Delta T(\theta)=T(\theta)-\bar T
]

### F.2 Énergie fluctuante et volant d’inertie

Variation d’énergie cinétique admissible liée au coefficient d’irrégularité (C_s) :
[
C_s=\frac{\omega_{max}-\omega_{min}}{\omega}
]
Volant d’inertie requis (ordre 1) :
[
J \ge \frac{\Delta E}{\omega^2,C_s}
]
où (\Delta E) est l’amplitude de l’énergie fluctuante sur un cycle (issue de l’intégrale du couple excédentaire).

### F.3 Vitesse critique (Jeffcott, 1er mode, arbre + disque)

[
\omega_c\approx \sqrt{\frac{k}{m}}
]
Rigidité en flexion (exemple poutre simplement appuyée, charge au centre) :
[
k \approx \frac{48EI}{L^3}
]
avec (I=\frac{\pi d^4}{64}) (arbre plein).

### F.4 Torsion dynamique (fréquence propre torsionnelle)

Raideur torsionnelle d’un arbre :
[
k_t=\frac{GJ}{L},\quad J=\frac{\pi d^4}{32}
]
Fréquence propre (disque inertie (J_d)) :
[
\omega_{t}\approx \sqrt{\frac{k_t}{J_d}}
]
Condition d’évitement résonance :
[
\omega \not\approx \omega_t \quad (\text{et harmoniques})
]

### F.5 Équilibrage masse alternative (ordre 1)

Force d’inertie principale (tu l’avais) :
[
F_i(\theta)\approx m_{eq}r\omega^2\cos\theta
]
Contrepoids : choix masse (m_c) à rayon (r_c) :
[
m_c r_c \approx \beta, m_{eq} r
]
((\beta) = fraction équilibrée ; 100% crée d’autres composantes, donc on choisit souvent partiel.)

---

# Comment utiliser ces formules (chaîne “fermée”)

1. Tu fixes (T_{gaz}), (T_{eau}), débits → tu calcules (U), (q''), (T_{paroi}).
2. Tu fixes (V_h(\theta)), (V_c(\theta)), (T_h,T_c,m) → tu obtiens (p(\theta)).
3. (p(\theta)) → efforts (F(\theta)) → arbre/bielle/vilebrequin/paliers.
4. Tu imposes (\dot m_{max}) → tu dimensionnes jeux/joints (et tu comptes les pertes (P_f)).
5. Tu dimensionnes paliers (PV ou (L_{10})).
6. Tu dimensionnes volant/inerties + vérifs (\omega_c,\omega_t).

---

## Limite explicite (important)

Ces formules te donnent un **dimensionnement de principe**. Pour être “ingénierie finale”, il faut au moins :

* corrélations Nusselt adaptées à **ton** régime (hélicoïde, gaz échappement),
* propriétés matériau **à la température** (fluage),
* un modèle géométrique concret pour (V_h(\theta),V_c(\theta)).

Si tu veux, je peux te restructurer tout ça en **fiche de calcul** (entrées → sorties) comme ton rapport SHSE-M, mais sans inventer de valeurs.


Oui. Ton cadre est solide, mais il manque plusieurs **blocs dimensionnants** (souvent ceux qui font “basculer” un design en vrai produit). Voici ce que j’ajouterais, avec les **formules minimales** à mettre dans le document.

---

## 0bis) Entrées minimales à ajouter (vraiment déterminantes)

### Fluide / cycle

* Gaz de travail (air, He, N₂…) : (R,,c_p,,c_v,,\gamma,,\mu(T),,k_f(T))
* Masse de gaz (m) ou pression de charge (p_0) + volumes morts
* Températures côté chaud/froid : (T_h,,T_c) **(températures de paroi et de fluide)**

### Thermique

* Débits : (\dot m_{gaz},,\dot m_{eau})
* Échange : (h_{gaz},,h_{eau}) ou géométrie + corrélations
* Encrassement : (R_{fouling})

### Mécanique

* Facteurs de service / chocs : (K_s) (crabot, pulsations)
* Critères de flèche admissible joint : (w_{adm})
* Tolérances/jeux : (h) (jeu radial), ovalisation admissible, conicité

---

## 1bis) Thermique “réelle” (au lieu de thermo simplifiée)

### 1.3 Puissance thermique échangée

[
\dot Q_{gaz}= \dot m_{gaz},c_{p,g},(T_{gaz,in}-T_{gaz,out})
\qquad
\dot Q_{eau}= \dot m_{eau},c_{p,e},(T_{eau,out}-T_{eau,in})
]

### 1.4 Échangeur (LMTD) + coefficient global

[
\dot Q=U,A,\Delta T_{lm}
]
[
\Delta T_{lm}=\frac{\Delta T_1-\Delta T_2}{\ln(\Delta T_1/\Delta T_2)}
]
[
\frac{1}{UA}=\frac{1}{h_{gaz}A}+\frac{t}{kA}+\frac{1}{h_{eau}A}+R_{fouling}
]

### 1.5 Températures de paroi (clé pour matériaux/fluage)

Avec (q''=\dot Q/A) :
[
T_{w,hot}=T_{gaz}-\frac{q''}{h_{gaz}},
\quad
T_{w,cold}=T_{eau}+\frac{q''}{h_{eau}},
\quad
T_{w,hot}-T_{w,cold}=q''\frac{t}{k}
]

### 1.6 Contrainte thermique (pièce bridée)

[
\sigma_{th}\approx \frac{E\alpha\Delta T}{1-\nu}
]

---

## 1ter) Pression (p(\theta)) (au lieu de “si pas de (p(\theta))”)

Si tu prends un modèle 2-zones isothermes (ordre 1) :
[
p(\theta)=\frac{mR}{\frac{V_h(\theta)}{T_h}+\frac{V_c(\theta)}{T_c}}
]
et le travail :
[
W_i=\oint p,dV \approx \sum_k p(\theta_k),[V(\theta_{k+1})-V(\theta_k)]
]

---

## 3bis) Vérifs vilebrequin/arbre : torsion + flexion combinées (tu l’as dit ailleurs, mais pas ici)

Couple :
[
\omega=\frac{2\pi n}{60},\quad T=\frac{P_b}{\omega},\quad T_d=K_sT
]

Torsion :
[
\tau_{max}=\frac{16T_d}{\pi d^3}\le \tau_{adm}
\Rightarrow
d\ge\left(\frac{16T_d}{\pi\tau_{adm}}\right)^{1/3}
]

Flexion :
[
\sigma_b=\frac{32M}{\pi d^3}
]

Von Mises :
[
\sigma_{eq}=\sqrt{\sigma_b^2+3\tau_{max}^2}\le\sigma_{adm}
]

Rigidité torsionnelle (important pour crabot) :
[
\theta=\frac{T_dL}{GJ},\quad J=\frac{\pi d^4}{32}
]

---

## 4bis) Fluage à chaud (incontournable si côté chaud élevé)

Il te faut une contrainte admissible dépendante de (T) et du temps :
[
\sigma_{service}\le \sigma_{adm}(T,t_{life})
]
(En pratique, (\sigma_{adm}) vient de courbes matériau fluage/rupture. Sans ces courbes, tu ne peux pas conclure “acier vs réfractaire vs superalliage”.)

---

## 5bis) Assemblages : arrachement taraudage + pression sous tête

Pression sous tête / rondelle :
[
p_{head}=\frac{F_{pre,bolt}}{A_{bearing}}\le p_{adm}
]

Arrachement filetage (ordre 1) :
[
F_{strip}\approx \pi,d_{moy},L_e,\tau_{adm,mat}
]
[
F_{strip}\ge \gamma,F_{pre,bolt}
\Rightarrow
L_e\ge \frac{\gamma F_{pre,bolt}}{\pi d_{moy}\tau_{adm,mat}}
]

---

## 6bis) Étanchéité : fuite “calculable” (pas seulement proportionnelle)

Fuite laminaire dans jeu annulaire ((h\ll r)) :
[
Q \approx \frac{\pi r,h^3}{6\mu L},\Delta p
\quad,\quad
\dot m=\rho Q
]
Critère :
[
\dot m\le \dot m_{max}
]

---

## 8bis) Lubrification / paliers (actuellement trop peu)

### Palier lisse : critère (p\cdot v)

[
p=\frac{W}{Ld},\quad v=\omega r,\quad p,v\le (pv)_{adm}
]

### Roulements : durée de vie (L_{10})

[
P=X F_r+Y F_a
\quad,\quad
L_{10}=\left(\frac{C}{P}\right)^p
\quad (p=3\ \text{billes},\ 10/3\ \text{rouleaux})
]
[
L_{10h}=\frac{10^6L_{10}}{60n}
]

---

## 10bis) Dynamiques : volant d’inertie + vitesses critiques

### Volant (régularité de rotation)

[
C_s=\frac{\omega_{max}-\omega_{min}}{\omega}
\quad,\quad
J\ge \frac{\Delta E}{\omega^2 C_s}
]

### Vitesse critique (Jeffcott, ordre 1)

[
\omega_c\approx \sqrt{\frac{k}{m}}
]
(avec (k) issu de la rigidité en flexion selon ton schéma d’appuis.)

---

## 11) Fabrication / tolérances / montage (souvent oublié mais dimensionnant)

* Condition cylindre mince vs épais :
  [
  \frac{t}{r_i}\le 0.1 \Rightarrow \text{mince, sinon Lamé}
  ]
* Jeux fonctionnels : (h) (guidage), ovalisation admissible, rugosité cible (imposée par étanchéité et usure)
* Dilatations différentielles :
  [
  \Delta L=\alpha L\Delta T
  ]
  À intégrer dans les jeux et le serrage.

---

### Synthèse : ce qui manque le plus

1. **Thermique réelle** (U, LMTD, (T_{paroi}))
2. **Modèle (p(\theta))** (même simplifié)
3. **Paliers / lubrification** (pv ou (L_{10}))
4. **Fluage** si zone chaude élevée
5. **Dynamiques** (volant, vitesses critiques)
6. **Filetages/arrachement + pression sous tête**
7. **Tolérances + dilatations** (sinon les joints/jeux sont “théoriques”)

Si tu intègres ces blocs, ton “cadre calculatoire complet” devient réellement complet au sens ingénierie.
