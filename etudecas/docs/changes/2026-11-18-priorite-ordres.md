# Correction de la priorité des ordres : essai sur 2025

Étude du 18 novembre 2026, code de départ `17c196f51`, sur 152 jours à
partir du 1er janvier 2025. Référence `coherent-MRP-20261014` conservée.
La nouvelle option `known_dated_priority_v2` reste désactivée par défaut.
Les [essais précédents](2026-11-17-essais-protection-lancement.md) sont conservés.

## Défaut corrigé et limites de la règle

L'admission précédente réservait la machine et les composants à tous les
autres ordres avant de vérifier le premier. Le même ordre de 268091 était
refusé pendant 98 jours, empêchant tout nouveau lot. C'était un défaut du
contrôle expérimental, pas une panne industrielle.

La correction conserve la priorité native : date de lancement prévue
d'origine, puis date de création, puis identifiant. Elle ne remplace pas les
dates des ordres en retard par aujourd'hui pour les départager. La machine
et les composants suivent désormais cette même priorité.

Les ordres suivants du même site et du même produit gardent leur quantité et
leur date prévue, mais leur **date physique projetée** peut être retardée.
Une nouvelle campagne ne démarre pas le jour où la précédente se termine :
c'est la convention d'exécution actuelle, non une règle industrielle confirmée.
Les ordres initiaux, les travaux engagés, les besoins d'autres produits et
les dettes des autres usages restent protégés. Un manque de composants
ne disparaît pas : il reste chiffré dans les traces.

Le calcul exige un candidat identifié dans le carnet figé. Il n'invente pas
une priorité quand ses métadonnées manquent. Les cas non projetables, dont
certaines substitutions, gardent leur parcours natif et ne démontrent pas
une continuité apportée par le nouveau contrôle.

## Vérification avant les calculs complets

Avec deux lots de huit unités et dix unités de capacité quotidienne, la
correction permet le premier lot aujourd'hui, puis le second demain. Avec
seulement douze composants, les quatre manquants pour le second lot restent
signalés ; ils ne bloquent pas rétrospectivement le premier.

Les **44 tests ciblés** sont passés sans cas ignoré. L'oracle indépendant
compte 116 contrôles de préparation. Sur les anciens états de 268091,
le conflit artificiel de machine disparaît, mais 001893 manque encore du
24 février au 5 mars. Une réception déjà connue devient utilisable le
6 mars. Ces anciens états ne prédisent pas la trajectoire corrigée : ils
permettent seulement de vérifier la décision à informations identiques.

Le témoin recalculé reproduit exactement ses **57 CSV antérieurs**. Son
contrôle indépendant rapproche les généalogies et les engagements :
10 164 vérifications sans erreur. La demande prévisionnelle, la connaissance
hebdomadaire du réel, les horizons figés de quatre/huit semaines, les stocks
initiaux, les lots, les sécurités et les capacités sont conservés.

## Résultats appariés

**Le blocage est corrigé, sans amélioration globale du rapprochement au réel.**
Les 34 nouveaux lots de 268091 sont fabriqués, soit 1 152 000 unités : c'est
la quantité du témoin conservé, retrouvée après l'échec de l'admission v1.
Le total avec les ordres initiaux reste de 3 097 715 unités. Les deux essais
commencent et terminent leur premier lot le **6 mars** ; le 24 février est
sa date prévue au carnet, pas un début de fabrication physique constaté.

| Critère, en unités sauf précision | Témoin | Priorité corrigée |
|---|---:|---:|
| 268091 : erreur hebdomadaire moyenne de production | 82 128,33 | 84 871,19 |
| 268091 : erreur moyenne du stock de Muret | 292 144,86 | 289 163,27 |
| 268967 : erreur hebdomadaire moyenne de production | 29 319,62 | 29 319,62 |
| 268967 : erreur moyenne du stock de Muret | 82 525,32 | 82 525,32 |
| 268967 : produits finis terminés | 431 200 | 431 200 |
| 268967 : travail exécuté dans le lot encore inachevé | 61 600 | 61 600 |

Pour 268091, l'erreur hebdomadaire augmente de **3,34 %**, tandis que l'erreur
de stock diminue de **1,02 %**. Une quantité de 28 800 unités passe de la
semaine du 21 avril, déjà sous la production observée, à celle du 28 avril,
déjà au-dessus. Les écarts absolus supplémentaires représentent
57 600 / 21 = **2 742,86 unités par semaine**. La somme fabriquée est identique ;
les trajectoires ne le sont pas.

Ce déplacement vient d'un arbitrage matière identifié : le 22 avril, le
composant 029313 offre 2,277363 kg utilisables, mais le contrôle protège
d'abord 2,146308 kg d'autres besoins dus. Le lot requiert 1,16928 kg et
doit attendre la réception de 300 kg utilisable le 28 avril. Le témoin
exécutait ce lot avant ces autres usages. La correction de capacité est
juste ; cette priorité matière conservatrice reste une **hypothèse de
gestion**, non une priorité industrielle établie.

Les livraisons simulées et les attentes quotidiennes sont identiques pour les
deux produits. Le stock physique cumulé de 268091 à Muret diminue de
451 170 unités-jours, mais les stocks finaux restent identiques. Le coût
d'immobilisation connu du réseau augmente de **35,12**, de 679 081,40 à
679 116,52 unités monétaires du modèle ; les achats externes connus restent
identiques. Ce sous-total exclut notamment la valorisation des produits finis
de Muret : il ne mesure pas le coût industriel complet.

Les [courbes comparatives](../../resultats/priorite_ordres_20261118.html)
présentent les deux produits et les effets opposés sur production et stocks.

## Ce qui reste à corriger pour 268967

Le nouveau contrôle autorise 34 lots de 268091 et refuse 16 tentatives pour
manque de matière, sans conflit artificiel de capacité. Pour 268967, il
n'autorise explicitement que le cinquième lot. Les quatre précédents passent
par le chemin natif réservé aux substitutions non projetables.

Le quatrième lot de 268967 travaille faiblement le 6 mai, puis s'arrête les
**7 et 8 mai**, avant de terminer le 20 mai. La correction de priorité ne
supprime donc pas cette interruption. Le cinquième lot suit sa trajectoire
prévue jusqu'au 1er juin, mais sa fin projetée est le 9 juin, hors fenêtre :
sa continuité complète n'est pas encore observée.

La piste suivante est précise : la transition `EX-344135 → 344135` fait
contourner le contrôle alors que, pour le quatrième lot, 156 600 unités de
la référence principale sont utilisables au lancement pour un besoin de
107 800. La référence ancienne n'est pas éligible ce jour et n'est finalement
pas consommée par ce lot. Ce dernier constat est rétrospectif : il ne doit
pas être injecté dans la décision de lancement.

Le prochain petit test devra projeter les références principales avec les
obligations déjà connues, puis déterminer si la substitution peut réellement
intervenir. Une transition sans effet sur cette projection ne devrait pas
désactiver le contrôle des autres composants. Cette piste n'est **pas encore
implémentée ni simulée** ; aucune nouvelle hypothèse de format ou de
nomenclature n'est introduite.

## Périmètre de preuve

Les comparaisons utilisent les mêmes observations : 13 semaines de production
documentées pour 268967, 21 pour 268091 et 22 photographies de stock par produit.
La production observée est estimée par les retraits d'étuis ; une semaine
non renseignée n'est pas remplacée par zéro. Les stocks comparés incluent
le contrôle qualité et sont rapprochés de la clôture simulée précédente.

Ce diagnostic historique conserve les besoins des autres usages reconstruits
depuis les mouvements. Leur total peut dépendre de la consommation propre
simulée : ce n'est pas une comparaison à demande concurrente fixe. Les attentes
clients simulées incluent le transport normal ; elles ne sont pas des retards
contractuels identifiés. Les coûts connus ne valorisent pas tous les stocks,
notamment les produits finis de Muret.

Le [protocole](../../artifacts/testing/priorite_ordres_20261118/protocol.json)
fixe deux calculs de 152 jours, avec contrôle des ressources et arrêt sur échec.
Les [règles détaillées](../REGLES_MRP.md) précisent le domaine de l'option.
Les deux calculs natifs sont qualifiés sur les mêmes sources gelées. Les
contre-revues natives comptent 10 164 et 419 562 contrôles, sans erreur ;
la comparaison indépendante en compte 2 987. Les 35 autorisations positives
correspondent au travail projeté sur les jours effectivement observés, sans
extrapoler la fin du dernier lot. Le
[détail des trajectoires](../../artifacts/testing/priorite_ordres_20261118/validator/launch_trajectory_detail.json)
distingue autorisation, travail et interruptions.

Un premier comparateur a refusé les deux fichiers de paramètres propres aux
essais, volontairement différents. Le contrôle corrigé vérifie explicitement
leurs paramètres puis l'identité des onze sources métier ; l'échec initial
est conservé et exclu des réussites. Le contrôle documentaire global reste
refusé sur cinq domaines générés déjà périmés. Le contrôle final réussi est
limité à l'environnement, aux tests ciblés et aux deux qualifications.

Le [manifeste final](../../artifacts/testing/priorite_ordres_20261118/final_manifest.json)
relie les preuves sur l'état final. Aucun test d'altération volontaire de
fichiers, aucune suite globale ni vérification navigateur n'a été exécuté.
Le HTML est vérifié statiquement et son image est relue.

**Décision : conserver le témoin et ne pas promouvoir l'admission corrigée.**
Le défaut de priorité du contrôle est résolu ; le bénéfice industriel global
n'est pas démontré. L'applicabilité du contrôle pendant les substitutions
est la prochaine question discriminante, avant toute simulation plus longue.
