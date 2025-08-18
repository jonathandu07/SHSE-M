# SHSE-M — Assistant
Ce dépôt contient l'assistant de dimensionnement et d'intégration (Stirling / SHSE-M).
Arborescence générée automatiquement.

Voici, pour un Stirling **β** (déplaceur et piston dans le même cylindre, haut chaud / bas froid), les **pièces directement impactées par l’alésage B et la course S du cylindre** — avec, pour chacune, ce qui change et pourquoi.

\#1. Organe moteur (piston de puissance & guidage)

* **Piston de puissance**

  * Ø piston = **B** (jeu de fonctionnement inclus) → surface $A=\pi B^2/4$ ⇒ force gaz $F \approx p\,A$ (charges mécaniques).
  * **Segments/joints** : diamètre, circonférence, épaisseur, nombre (friction, étanchéité) dimensionnés sur B et la pression/force.
  * **Axe de piston (goujon)** : diamètre et portée dictés par $F$ et le moment sur l’axe (donc par B et S via l’inertie).
* **Bielle (pied & tête)**

  * Longueur **L\_bielle** souvent choisie en ratio de la course (p.ex. $L \approx 3\!-\!4 \, (S/2)$) pour limiter l’angle de bielle.
  * Sections et coussinets dimensionnés pour la charge $F \propto B^2$ et la vitesse de glissement (donc S et régime).
* **Vilebrequin / maneton**

  * **Rayon de manivelle** $r = S/2$.
  * Diamètre de maneton et contrepoids dimensionnés sur les efforts alternatifs $\propto B^2$ et l’inertie (fonction de S et du régime).
* **Paliers**

  * Diamètre/largeur en fonction des charges transmises (croissent avec $B^2$) et de la cinématique (S, n).

\#2. Chemise & enceintes gaz

* **Chemise de cylindre / revêtement**

  * Ø intérieur = **B** (choix du jeu), **épaisseur** liée à la pression interne et au diamètre (contrainte cerclage).
* **Têtes/culasses chaude & froide**

  * Surfaces d’échange et rigidité → tailles géométriques liées à **B** (périmètre, surface disponible).
  * Choix des motifs d’ailettes/canaux proportionnés au débit gazeux (lié au **volume balayé $V_s=(\pi/4)B^2 S$**).

\#3. Déplaceur et guidage

* **Déplaceur (piston “fou”)**

  * **Ø déplaceur** ≈ B (moins le jeu annulaire). Masse ∝ volume ⇒ inertie augmente avec B et longueur utile.
  * **Course déplaceur** (souvent proche de S selon la phase choisie) ⇒ définit enveloppe et butées.
* **Tige & guide de déplaceur / joint traversant**

  * Diamètres et paliers dimensionnés sur la force fluide (fonction de B) et sur la course (S) → étanchéité dynamique.

\#4. Régénérateur & canaux (section de passage liée à B)

* **Canal annulaire autour du déplaceur** (β)

  * **Section hydraulique** $A_{\text{ann}} \approx \pi B \, e$ (e = jeu annulaire). Si B ↑, le périmètre ↑ ⇒ pertes de charge varient, et le jeu e doit rester dans une plage (≈ 0,5–1,5 mm typ.) : impact direct sur **pertes** et **NTU** global.
* **Régénérateur (matrice)**

  * **Section** à faire correspondre au débit oscillant $\dot m \propto V_s \cdot n$ ⇒ dépend de $B^2S$.
  * **Longueur** et **maille** (diamètre de fil/maillage) fixées par le critère d’efficacité (NTU) et perte de charge → l’augmentation de B/S modifie l’optimisation (plus de débit ⇒ section ou longueur ↑).
* **Échangeurs chaud & froid**

  * **Surface mouillée** et **section de passage** à dimensionner pour le flux thermique proportionnel au **débit massique** (donc à $B^2 S$) et au ΔT.

\#5. Volant d’inertie & équilibrage

* **Volant d’inertie**

  * Lissage du couple dépend de l’**ondulation de couple** liée à $p\,A$ (donc $B^2$) et à la cinématique (S, phase). Inertie requise $J$ augmente avec $V_s$ et le régime.
* **Contrepoids / équilibrage**

  * Masses d’équilibrage (piston, déplaceur, bielles) croissent avec B et S (masses & bras de levier).

\#6. Étanchéités & interfaces

* **Joints dynamiques** (piston, tige de déplaceur) : Ø des lèvres **= B** (ou Ø tige), vitesse périphérique $\propto r\,\omega \propto S\,n$ ⇒ échauffement/usure.
* **Joints statiques** (culasses, échangeurs) : périmètre d’appui $\propto B$ (longueur de joint ↑ avec B) ⇒ effort de serrage.

\#7. Circuit thermique & auxiliaires (dimensionnés par $B^2 S$)

* **Refroidisseur (eau/air) & pompe/ventilateur**

  * Débit et surface nécessaires suivent la puissance thermique à extraire, donc **dimensionnement dicté par le déplacement** $V_s$ (∝ $B^2 S$).
* **Chauffeur / brûleur**

  * Surface d’absorption et distribution de flamme/flux alignées sur la surface disponible (∝ B) et le flux requis (lié à $V_s$).

---

## Raccourcis utiles (pour ton script)

* **Déplacement/cylindre** : $V_s = (\pi/4) B^2 S$ → pilote **tous** les organes liés au **débit oscillant** (régénérateur, canaux, échangeurs, pompe).
* **Rayon de manivelle** : $r = S/2$ → pilote vilebrequin, bielle, paliers, enveloppe.
* **Efforts gaz** : $F \approx p_{\text{eff}} \, (\pi/4) B^2$ → pilote tailles d’axe, maneton, coussinets, épaisseurs, volant.
* **Vitesse piston** : $U_p = 2 S n/60$ → pilote choix de segments, lubrification, pertes par friction et échauffement joints.

Si tu veux, je peux te **lister ces pièces en objets** (dict/dataclass) pour alimenter `page_pieces.py` et générer automatiquement la BOM avec les champs dimensionnés par $B$ et $S$ (avec formules attachées).
