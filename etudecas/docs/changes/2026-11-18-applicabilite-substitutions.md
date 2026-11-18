# Contrôle des matières malgré une substitution configurée

Étude du 18 novembre 2026, départ `adf494931`, sur la fenêtre du
1er janvier au 1er juin 2025. La référence `coherent-MRP-20261014` et les
[comparaisons précédentes](2026-11-18-priorite-ordres.md) sont conservées.
L'option `known_dated_substitution_v3` est expérimentale, inactive par défaut.

## Pourquoi le rapprochement reste difficile

Les dernières corrections ont supprimé un blocage du contrôle expérimental,
sans établir une meilleure représentation industrielle de toute la chaîne.
Trois différences restent déterminantes, sans décomposition causale complète :

- **Capacité et calendrier non mesurés.** Du 31 mars au 27 avril, les retraits
  documentés représentent 171 000 unités de 268967. L'hypothèse de 7 700 unités
  par jour sur vingt jours ne permet que 154 000 unités. Changer seulement les
  dates des lots à l'intérieur de ce bloc ne résout pas l'écart. Cela ne prouve
  pas une capacité industrielle de 8 550 unités par jour : les dates de retrait
  et de comptabilisation peuvent différer des dates de fabrication.
- **Prévisions et engagements différents du réalisé.** Sur vingt semaines
  du 6 janvier au 25 mai, la prévision connue au démarrage vaut 890 322 unités,
  contre 610 266 demandées ensuite, soit +45,89 %. Les prévisions sont ensuite
  actualisées ; les engagements figés peuvent survivre à une révision.
  Le calcul initial vérifié ne démontre pas de double comptage.
- **Observations et usages concurrents partiellement reconstruits.** La
  production industrielle comparée est estimée par les retraits d'étuis.
  Treize semaines seulement sont documentées pour 268967 dans cette fenêtre.
  Les usages concurrents historiques sont des résidus qui dépendent aussi de
  la consommation propre simulée : leur variation n'est pas celle d'une liste
  industrielle fixe de commandes.

Les [pistes précédentes](2026-11-17-pistes-production.md) et les
[essais de protection](2026-11-17-essais-protection-lancement.md) donnent les
preuves et leurs périmètres. Le biais de prévision sur vingt semaines ne doit
pas être additionné à l'erreur de production sur treize semaines documentées.
Les stocks de D1920 peuvent absorber une variation de production ; une
amélioration en usine ne démontre pas une amélioration du service client.

## Défaut ciblé et correction

Le quatrième lot de 268967 démarrait le 28 avril, travaillait très peu le
6 mai, puis s'arrêtait les 7 et 8 mai avant de terminer le 20 mai. Une
transition de composant configurée jusqu'au 1er mai contournait le contrôle
de tous les composants. Pourtant le lot n'utilisait finalement que la
référence principale. Ce constat rétrospectif sert au diagnostic, jamais
comme connaissance anticipée de la décision.

La version v3 projette d'abord les références principales concernées sur
toute la campagne, avec les stocks utilisables, réceptions et autres besoins
déjà connus, en conservant les priorités v2. Si elles suffisent, elle vérifie
ensuite tous les composants. Un manque d'un autre composant ne peut donc pas
interrompre trop tôt la preuve sur le principal. Si une substitution peut
être nécessaire, ou si sa politique est inconnue, le parcours natif reste
explicitement non projetable ; ce cas n'est pas une admission validée.

Le calcul manuel, conservant l'état connu le 28 avril, prévoit un manque de
042342 en commençant les 28, 29 ou 30 avril. Un départ le 1er mai permettrait
de travailler jusqu'au 20 mai sans ce manque grâce à une réception déjà
connue, utilisable le 9 mai. Ce petit calcul exclut les autres engagements
non reconstruits : seule l'exécution complète pourra confirmer l'admission.
Aucune date, capacité ou consommation industrielle future n'est imposée.

## Vérifications et comparaison

Les 65 tests de calcul en mémoire passent, sans cas ignoré. La préparation
indépendante compte 72 contrôles, avec un oracle arithmétique séparé de
50 vérifications. Les sources du moteur sont gelées avant les calculs.

Le [protocole initial](../../artifacts/testing/applicabilite_substitutions_20261118/protocol.json)
prévoyait deux recalculs sur 152 jours. Le témoin v2 a été arrêté à sa limite
de 1 200 secondes, après avoir atteint le jour 120. Le nettoyage porte le
temps enregistré à 1 210,36 secondes. Cet essai reste en échec ; ses sorties
partielles ne sont ni qualifiées ni présentées comme des courbes complètes.

La [révision du protocole](../../artifacts/testing/applicabilite_substitutions_20261118/protocol_after_time_stop.json)
conserve le témoin v2 antérieur et réserve le calcul à v3, avec une limite
fixée avant lancement de 2 400 secondes. La
[preuve de compatibilité](../../artifacts/testing/applicabilite_substitutions_20261118/validator/control_compatibility_review.json)
compte 792 contrôles sans erreur : mêmes onze entrées métier et paramètres,
code v2 structurellement identique hors branches v3 inactives, rattachement
aux octets historiques et 378 223 lignes de plans MRP identiques. La dernière
décision partielle est exclue. Aucun export physique courant n'était disponible
avant l'arrêt : cette preuve ne constitue pas une nouvelle exécution complète
du témoin. Son manifeste et sa qualification historiques restent distincts.

Le candidat conserve données, calendriers, lots, sécurités et horizons figés.
La seule intervention porte sur l'applicabilité du contrôle matière.

Le candidat termine en **1 675,95 secondes**, avec 1,09 Go de mémoire maximale
mesurée en octets décimaux. Il passe la qualification native et la revue
indépendante : 439 035 contrôles, sans erreur. Le témoin historique est relu
sur 419 410 contrôles ; la comparaison finale en compte 3 711.

## Résultat : un lot continu, un rapprochement encore partiel

Le défaut ciblé est corrigé. Pour 268967, les quatre contournements disparaissent.
Les cinq lots reçoivent une admission explicite ; les trois premiers conservent
leur trajectoire. Le quatrième est refusé les 28, 29 et 30 avril, puis autorisé
le **1er mai**, avec uniquement les informations déjà connues. Son manque
prévu de 042342 est de 435 368 unités : 464 633 nécessaires pour la journée
contre 29 265 disponibles après les obligations connues.

Ce quatrième lot travaille désormais sans les deux arrêts des **7 et 8 mai**.
Il termine toujours le **20 mai** : l'attente a lieu avant le démarrage plutôt
qu'au milieu de la fabrication. Le 1er mai est déclaré ouvré dans l'hypothèse
lundi–vendredi utilisée ici ; ce n'est pas un calendrier industriel confirmé.
Aucune fermeture pour jour férié n'a été ajoutée arbitrairement à cet essai.

| Indicateur, en unités sauf précision | Témoin v2 conservé | Essai v3 |
|---|---:|---:|
| 268967 : erreur hebdomadaire moyenne, 13 semaines documentées | 29 319,62 | 27 595,38 |
| 268967 : production sur ces mêmes semaines | 438 415 | 415 800 |
| 268967 : écart aux 402 500 unités estimées sur ces semaines | +35 915 | +13 300 |
| 268967 : travail total exécuté sur 152 jours | 492 800 | 492 800 |
| 268967 : produits finis terminés | 431 200 | 431 200 |
| 268967 : travail exécuté dans le lot encore inachevé | 61 600 | 61 600 |
| 268967 : erreur moyenne de stock à D1920 | 82 525,32 | 82 525,32 |
| 268091 : erreur hebdomadaire moyenne, 21 semaines documentées | 84 871,19 | 84 871,19 |
| 268091 : erreur moyenne de stock à D1920 | 289 163,27 | 289 163,27 |

L'erreur mesurée de 268967 baisse de **1 724,23 unités par semaine, soit 5,88 %**.
Le détail explique et borne ce gain :

| Semaine du | Réel estimé | Témoin | Essai |
|---|---:|---:|---:|
| 28 avril | 15 500 | 38 500 | 15 400 |
| 5 mai | inconnu | 15 885 | 38 500 |
| 19 mai | 24 500 | 38 015 | 38 500 |

La semaine du 12 mai est également inconnue, mais sa production ne change
pas. Une partie du travail se déplace donc vers une semaine non observée :
la meilleure erreur sur les semaines renseignées ne démontre pas que tout
le mois de mai est mieux reproduit. La prédiction arithmétique faite avant
le candidat est confirmée, sans être utilisée pour fixer ses décisions.

Les **stocks quotidiens de D1920, réceptions de produits finis et livraisons
clients sont identiques**. Les trajectoires de 268091 restent inchangées.
Les 39 lots admis des deux produits respectent le travail projeté pendant
les jours observés ; la fin du dernier lot de 268967, projetée au 9 juin,
reste hors de cette fenêtre. Elle n'est pas annoncée comme vérifiée.

Le coût d'immobilisation connu passe de 679 116,5248 à 679 148,4928, soit
**+31,9680** unités monétaires du modèle. Les achats externes connus passent
de 8 040 455,5287 à 8 040 455,1861, soit −0,3426. Ces sous-totaux ne
valorisent pas tous les stocks et ne constituent pas une comparaison de
coût industriel complet.

## Prochaine cible : rendre les autres besoins indépendants de l'essai

Le besoin reconstruit des autres usages de 042342 passe de **124 217 724 à
122 823 824 unités**, soit **1 393 900 de moins**. Sa consommation diminue
du même montant ; l'attente reste nulle. Ce n'est pas la preuve qu'un besoin
industriel a disparu : le calcul historique du résidu dépend de notre propre
consommation simulée et réagit au déplacement de la fabrication.

Avant de comparer d'autres arbitrages matière, le prochain essai utile doit
conserver **le même profil déclaré de besoins concurrents dans les deux
variantes**, avec leurs dates de connaissance. Il faudra séparer le mécanisme
de lancement de cet effet de reconstruction. Le calendrier et la capacité
effective de 1430 restent ensuite à départager des dates de comptabilisation
des retraits ; aucun taux machine n'est ajusté pour rejoindre les pics.

Les [courbes et chiffres détaillés](../../resultats/applicabilite_substitutions_20261118_final.html)
montrent les deux produits, avec ce gain local et les écarts persistants.
Le [manifeste final](../../artifacts/testing/applicabilite_substitutions_20261118/final_manifest.json)
relie les preuves et distingue le témoin historique du candidat courant.

## Limites maintenues

Le contrôle est conditionnel aux capacités et obligations connues. Il ne
projette pas les futurs incidents inconnus ni une consommation de substitut.
Les deux suivis de lots, les quantités entières et les engagements restent
conservés. Le nominal ne change pas et aucune référence n'est promue.

Le contrôle documentaire global reste refusé sur cinq domaines générés
déjà périmés ; il est séparé de la qualification ciblée. Aucun navigateur,
Node, test global ou test d'altération de fichiers n'est exécuté.

Un premier comparateur a refusé des chemins de sources absolus Windows face
à des chemins relatifs. Le lecteur corrigé normalise les deux listes, rejette
les collisions et conserve la vérification de toutes les empreintes. Cet
échec, l'arrêt du recalcul témoin et les notes intermédiaires corrigées sont
conservés séparément des contrôles réussis. Le HTML final est contrôlé
statiquement, puis son image est relue ; aucune validation navigateur
n'est revendiquée.

**Décision : conserver v3 comme option expérimentale, sans promotion du
nominal.** L'applicabilité du contrôle est corrigée et l'interruption ciblée
supprimée. La fidélité industrielle globale reste non démontrée.
