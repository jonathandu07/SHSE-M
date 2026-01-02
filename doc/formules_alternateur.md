## 0) Entrées minimales (alternateur)

* Puissance électrique requise : (P_e) (W)
* Tension/phase : (V) (V), mono/tri, fréquence (f) (Hz) (si AC réseau)
* Vitesse mécanique dispo : (n) (tr/min)
* Rendement visé : (\eta_{alt})
* Limites thermiques : (T_{max}), pertes admissibles
* Si PM (aimants) : (B_g) (T) ordre de grandeur, géométrie rotor/stator
* Si bobiné : courant d’excitation (I_f), tension d’excitation (V_f)

---

## 1) Conversion mécanique → électrique

Vitesse angulaire :
[
\omega=\frac{2\pi n}{60}
]
Couple nécessaire pour fournir (P_e) :
[
T_{alt}=\frac{P_e}{\eta_{alt},\omega}
]
Puissance mécanique requise :
[
P_{mec}=\frac{P_e}{\eta_{alt}}
]

---

## 2) Fréquence – vitesse – nombre de pôles (machines AC)

Relation synchrone (alternateur synchrone) :
[
n_s=\frac{120,f}{P}
]
Donc :
[
f=\frac{n,P}{120}
]
où (P) = nombre de pôles (pair).

Si redressement + DC (charge batterie), la fréquence n’est pas imposée, mais elle impacte les pertes fer/commutation.

---

## 3) Électrique : puissance, courant, facteur de puissance

### 3.1 Triphasé

[
P = \sqrt{3},V_{LL},I_L,\cos\varphi
]
[
S=\sqrt{3},V_{LL},I_L
\qquad,\qquad
Q=\sqrt{S^2-P^2}
]

### 3.2 Monophasé

[
P=V I \cos\varphi
\qquad,\qquad
S=VI
]

### 3.3 DC (après redressement)

[
P_{DC}=V_{DC} I_{DC}
]

---

## 4) Loi fondamentale : f.e.m. induite (base de dimensionnement)

Faraday (par spire) :
[
e(t) = -N\frac{d\Phi(t)}{dt}
]
Pour flux sinusoïdal : (\Phi(t)=\Phi_{max}\sin(\omega_e t))
Valeur efficace (formule classique machines) :
[
E_{ph} = 4.44,f,N,\Phi_{max},k_w
]

* (E_{ph}) : tension efficace par phase (V)
* (N) : spires série/phase
* (\Phi_{max}) : flux max par pôle (Wb)
* (k_w=k_p k_d) : facteur d’enroulement (pas (\times) distribution)

Avec (\Phi_{max}=B_g A_p) (approx) :
[
E_{ph} \approx 4.44,f,N,B_g,A_p,k_w
]
((A_p) : aire efficace sous un pôle).

---

## 5) Dimensionnement “macro” : charge magnétique et électrique

Définitions utiles :

* Charge magnétique moyenne (airgap) :
  [
  B_{av} \approx \frac{\Phi}{A_{gap}}
  ]
* Charge électrique spécifique (courant par périphérie) :
  [
  a_c=\frac{I_{tot}}{\pi D}
  ]
  Pour machines tournantes, un estimateur de puissance (très utilisé en pré-dimensionnement) :
  [
  P \approx C_0,D^2,L,n
  ]
  où (D) = diamètre rotor (m), (L) = longueur active (m), (n) (tr/s) et (C_0) dépend de (B_{av}), (a_c), (k_w), etc. (c’est un **cadre**, pas une constante universelle).

---

## 6) Résistance cuivre, pertes cuivre, section de fil

Résistance d’un enroulement :
[
R = \rho \frac{l}{A}
]
Pertes cuivre :

* par phase :
  [
  P_{cu,ph}=I_{ph}^2 R_{ph}
  ]
* total triphasé :
  [
  P_{cu}=3 I_{ph}^2 R_{ph}
  ]

Densité de courant (critère thermique) :
[
J=\frac{I}{A_{cu}}
\quad\Rightarrow\quad
A_{cu}=\frac{I}{J}
]
((J) typiquement choisi selon refroidissement ; à fixer par hypothèse d’ingénierie).

Variation de résistivité avec température :
[
\rho(T)=\rho_0\left[1+\alpha_{Cu}(T-T_0)\right]
]

---

## 7) Pertes fer (noyau) : hystérésis + Foucault (ordre 1)

Forme classique (Steinmetz + eddy) :
[
P_{fe} \approx k_h,f,B^x + k_e,f^2,B^2
]
(les coefficients dépendent du matériau (tôles) et de l’épaisseur).

---

## 8) Pertes mécaniques (roulements, ventilation)

Ordre 1 :
[
P_{mec}=P_{fr}+P_{vent}
]
Ventilation (approx) :
[
P_{vent}\propto \rho_{air},\omega^3,R^5
]
(utilisé pour comparer des géométries ; le coefficient dépend fortement du design).

---

## 9) Rendement et bilan de pertes

[
\eta_{alt}=\frac{P_{out}}{P_{out}+P_{cu}+P_{fe}+P_{mec}+P_{stray}}
]

---

## 10) Modèle équivalent (alternateur synchrone) : régulation/charge

Tension interne (par phase) :
[
\underline{E}=\underline{V} + (R_s + jX_s),\underline{I}
]

* (R_s) : résistance stator
* (X_s) : réactance synchrone

Chute de tension (approx) :
[
\Delta V \approx R_s I\cos\varphi + X_s I\sin\varphi
]

---

## 11) Alternateur à aimants permanents (PMA) : points spécifiques

Flux par pôle (approx) :
[
\Phi \approx B_g A_p
]
Couple électromagnétique :
[
T_e=\frac{P_e}{\omega}
]
(identité énergétique) et, côté électromagnétique (cadre) :
[
T_e \propto \Phi,I_q
]
(si commande vectorielle / composante quadrature (I_q)).

Tension redressée (approx, dépend du pont et de la forme d’onde) :
[
V_{DC}\approx k_r,V_{LL,rms}
]
((k_r) dépend du redressement et du filtrage ; on l’utilise comme facteur de conversion).

---

## 12) Dimensionnement thermique simplifié (nécessaire)

Élévation de température :
[
\Delta T \approx R_\theta,P_{loss}
]
avec :
[
P_{loss}=P_{cu}+P_{fe}+P_{mec}+P_{stray}
]
et (R_\theta) (K/W) dépend du refroidissement (air, eau, conduction carter).

---

## Checklist “alternateur complet” à joindre à ton cadre

1. (T_{alt}=\dfrac{P_e}{\eta\omega}) (couple requis)
2. (f=\dfrac{nP}{120}) (si AC synchrone)
3. (E_{ph}=4.44 f N \Phi k_w) (f.e.m.)
4. (P_{cu}=3I^2R), (R=\rho l/A) (cuivre)
5. (P_{fe}\approx k_h f B^x + k_e f^2 B^2) (fer)
6. (\eta=\dfrac{P_{out}}{P_{out}+P_{loss}}) (rendement)
7. (\Delta T\approx R_\theta P_{loss}) (thermique)
8. (\underline{E}=\underline{V}+(R_s+jX_s)\underline{I}) (régulation, synchrone)

Si tu précises : **DC (charge batterie) vs AC (réseau)**, **vitesse (n)**, **tension cible**, et **type (aimants permanents vs excitation bobinée)**, je peux te donner un enchaînement “comme ton cadre moteur” qui sort : pôles, spires/phase, section de fil, estimation pertes, couple requis et contraintes thermiques.
