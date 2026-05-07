# Analyse du dimensionnement depuis une puissance de sortie

## Objectif

Le besoin cible est le suivant : fournir une puissance de sortie `X`, en `W`,
`kW`, `ch`, `cv` ou `hp`, puis definir par le calcul le maximum de pieces et
composants sans inventer les donnees manquantes.

Conclusion importante : une puissance seule ne suffit pas a definir un systeme
physique complet. Elle permet de fixer une cible energetique, mais pas une
geometrie, un couple, un regime, une autonomie, un alternateur, une batterie ou
une cinematique de pieces. Le programme doit donc calculer ce qui est ferme et
declarer explicitement le reste comme inconnue.

## Ce qui est calculable depuis la puissance seule

- Conversion d'unites : `W`, `kW`, `hp`, `cv/ch`.
- Energie equivalente si la puissance est maintenue pendant 1 heure.
- Puissance nominale cible d'un composant, uniquement comme exigence.

## Ce qui exige au moins une donnee en plus

- Couple de sortie : puissance + regime de sortie.
- Courant DC : puissance + tension DC.
- Courant triphase : puissance + tension ligne + facteur de puissance.
- Energie batterie : puissance + duree, ou distance + consommation.
- Puissance amont : puissance sortie + rendement de chaine.
- Couple moteur thermique : puissance moteur + regime moteur.
- Cylindree moteur : puissance moteur + type de puissance + rendement mecanique
  si puissance frein + regime + PME + temps moteur.
- Alesage/course : cylindree + nombre de cylindres + ratio course/alesage, ou
  cylindree + regime + vitesse piston max + ratio limite.
- Epaisseur cylindre : alesage + pression max + contrainte admissible +
  facteur de securite.

## Etat actuel du projet

Points forts :

- Les modules de pieces et composants savent deja remonter des `inconnues`.
- Le moteur thermique contient une methode de definition stricte depuis des
  exigences.
- Batterie, alternateur, boite et systeme complet ont beaucoup de calculs
  unitaires utiles.
- Les tests couvrent deja beaucoup de modules.

Points faibles :

- `dimensionner_systeme_shsem` annonce un mode strict mais construit encore des
  composants de compatibilite quand rien n'est fourni.
- Le mode simple GUI utilise volontairement des valeurs de premier passage
  (`1000 rpm`, `20 bar`, `4 cylindres`, rendements, bus, batterie). C'est utile
  pour afficher quelque chose, mais ce n'est pas un calcul strict.
- `SystemeComplet.analyser` contient encore des valeurs par defaut physiques ou
  systeme (`densite_air`, `gravite`, `nb_roues_motrices`, `puissance_auxiliaire`,
  etc.). Certaines sont des constantes de contexte acceptables, d'autres doivent
  etre declarees comme hypotheses utilisateur.
- Les fichiers locaux generes, logs, base SQLite et cle locale existent dans le
  dossier. Ils doivent rester hors commits.

## Nouveau point d'entree ajoute

`backend.power_definition.analyser_puissance_sortie`

Expose aussi via :

`backend.main.analyser_systeme_depuis_puissance`

Ce point d'entree :

- accepte une puissance en `W`, `kW`, `ch`, `cv`, `hp`;
- ne cree aucun moteur, aucune batterie, aucun alternateur par defaut;
- calcule uniquement ce qui est determine par les donnees fournies;
- retourne les inconnues qui bloquent ou limitent la suite;
- indique si le projet est pret ou non pour dimensionner les pieces.

## Jeu minimal de donnees pour commencer un moteur thermique

Pour passer de la puissance a la cylindree :

- `puissance` et unite;
- `rendement_sortie_depuis_moteur` ou `puissance_moteur_requise_w`;
- `type_puissance_moteur` : `frein` ou `indiquee`;
- `rendement_mecanique` si la puissance est de type `frein`;
- `rpm_moteur`;
- `pme_pa`;
- `temps_moteur` : `2` ou `4`.

Pour passer a l'alesage/course :

- soit `nombre_cylindres` + `ratio_course_alesage_cible`;
- soit `vitesse_piston_max_ms` + `ratio_course_alesage_max`, pour calculer un
  nombre de cylindres minimal aux limites.

Pour commencer les pieces :

- `pression_max_pa`;
- `contrainte_admissible_pa`;
- `facteur_securite_cylindre`;
- materiaux et densites pour les masses;
- charges ou donnees permettant de calculer les forces.

## Suite recommandee

1. Garder le mode GUI simple comme mode demonstrateur.
2. Faire de `analyser_systeme_depuis_puissance` le vrai point d'entree strict.
3. Ajouter un formulaire ou JSON qui affiche d'abord les inconnues, puis debloque
   les composants au fur et a mesure que l'utilisateur fournit les donnees.
4. Nettoyer progressivement les valeurs par defaut de `dimensionner_systeme_shsem`
   ou les marquer explicitement comme hypotheses.
5. Ajouter une CI pour garantir que le mode strict ne recommence pas a inventer
   des valeurs silencieusement.
