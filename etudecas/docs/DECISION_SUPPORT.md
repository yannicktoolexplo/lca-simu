# Diagnostic métier et comparaison exploratoire d'actions

## Référence et sensibilités : distinction à conserver

La simulation nominale conserve les données et hypothèses du cas, notamment les
cibles de sécurité réelles. Le scénario risqué conserve ces cibles et ajoute
des hypothèses de stress. Les essais `safety_150` et `expedite_50` sont des
**analyses de sensibilité séparées**, pas des corrections de la base ni des
recommandations de modifier les données réelles.

Décisions confirmées le 20 septembre 2026 : appliquer intégralement les jours
sources au dépôt (coefficient 1), avec un calendrier de sécurité lundi-vendredi
pour tous les sites. Les calculs historiques à 0,75 restent conservés. Le délai
`tau_process` reste une convention de planification à confirmer, sans ajout
silencieux d'un délai physique de fabrication.

Le ×1,5 agit sur la cible de réapprovisionnement quotidienne des composants
730384 (mètres) et 344135 (unités) à M-1430 ; il n'ajoute pas de stock initial.
Le stock explicite et la cible calculée à partir du besoin et du temps de
sécurité interviennent dans le calcul du moteur : la cible finale ne se réduit
pas à la quantité fixe du fichier source. Au premier jour de cet essai, les
cibles passaient respectivement de 326 480 à 489 720 et de 1 540 000 à 2 310 000
dans la livraison historique du 18 septembre ; ces montants ne sont pas les
cibles des calculs corrigés du calendrier.
Ces valeurs d'essai ne remplacent jamais les cibles de la référence.

La livraison assemble un tableau de bord local, les CSV justificatifs, les
empreintes des sources sélectionnées, les packages de résultats et la carte.
La carte comporte un lien « Diagnostic métier et actions » ; le tableau de
bord permet de revenir à la carte. Conserver le dossier du run pour que les
liens relatifs continuent à fonctionner hors ligne.

## Score et pertes

`score_breakdown` expose les trois termes comparables du score : service,
reliquat et surcoût. Si la valorisation est incomplète ou non documentée, le
surcoût est exclu et affiché indisponible, sans le transformer en effet nul.
Les pertes matière et reports sans unité commune sont
exclus ; leurs anciens ratios ne sont pas réinterprétés comme des zéros. La somme doit retrouver le score observé. `audit_losses` rapproche
les quantités prélevées moins expédiées du résumé, uniquement pour les départs
`0 <= day < horizon`. Les lignes hors horizon sont rapportées séparément.
Les pertes sont détaillées par fournisseur, article et unité ; un total
arithmétique de composants n'est pas une quantité équivalente de produits finis.
L'audit compte les doublons exacts de lignes à perte positive et les identifiants
d'expédition non vides répétés. Un identifiant vide n'est pas une preuve de doublon.

## Retards reconstruits

`fifo_delay` constitue des cohortes de demande journalière par client et produit.
FIFO sert la plus ancienne demande d'abord. Les journées doivent couvrir tout
l'horizon sans doublon ; les quantités sont finies et positives ou nulles ; le
bilan quotidien doit fermer à 0,02 unité près. Un reliquat initial d'âge inconnu
est refusé au lieu de lui inventer une date.

Le service le jour de la demande est borné par deux allocations possibles :
FIFO donne la borne basse, servir le jour courant d'abord donne la borne haute.
Il ne s'agit pas d'OTIF observé : les dates promises des commandes sont absentes.
Les retards moyen et maximum FIFO concernent les quantités effectivement servies.
Les demandes ouvertes sont censurées : leur âge est publié séparément. Le cumul
des reliquats en fin de journée est exprimé en unités·jours. Les petits résidus
d'arrondi sont tolérés ; le démarrage est inclus.

## Blocages et traçabilité

`bottlenecks` sélectionne les contraintes de production avec déficit supérieur
à 0,001 et conserve l'usine, le produit, le composant limitant, les journées et
les numéros de lignes source. Les fournisseurs proviennent des liaisons du
graphe vers cette usine pour ce composant. Les liens événements–lots exportés
ont un `causal_root_id` explicite. Ce contexte amont ne permet pas d'attribuer
quantitativement le retard client à un fournisseur. Des déficits répétés d'une
même campagne ne sont pas des pertes physiques distinctes.

## Analyses de sensibilité

Les deux composants limitants les plus fréquents dans le run risqué déterminent
les cibles. Il s'agit d'une sélection rétrospective exploratoire, pas d'une
politique prédictive validée. `execute_action` reprend les arguments du moteur
de référence, conserve le graphe et les risques configurés, change le dossier
de sortie et ajoute un calendrier quotidien de contrôle :

- `safety_150` : multiplicateur de cible de stock de sécurité 1,5 à l'usine ;
- `expedite_50` : niveau d'accélération 0,5 sur les liaisons des fournisseurs.

La graine de référence et les autres paramètres sont conservés. Dans la
livraison initiale, la graine par défaut enregistrée est 42 et les nombres
aléatoires communs sont désactivés. Les événements dépendants de l'état et
l'ordre des tirages peuvent donc différer entre actions. Ce n'est pas une
comparaison Monte Carlo appariée. Les commandes non neutres et leur statut sont
comptés dans le journal d'actions : une ligne demandée n'est pas nécessairement
une action exécutée.

Le tableau distingue coût opérationnel, approvisionnement externe et exposition
économique (leur somme). Une couverture de valorisation incomplète donne des
sous-totaux connus : leurs différences ne démontrent pas d'économie globale.
Une couverture complète signifie que les taux configurés sont renseignés,
sans certifier leur calibration industrielle. Les coûts de mise en œuvre non
modélisés sont exclus. Le délai moyen
des quantités servies compare des populations différentes si une action permet
de servir des demandes qui seraient restées ouvertes.

Le cache exige la même commande, le même graphe, la même source principale du
moteur, le même manifeste de référence, le même calendrier et le même résumé.
Ce contrôle n'est pas un inventaire transitif de toutes les dépendances. Une
sortie existante non conforme est refusée : utiliser un nouveau dossier, sans
écraser les campagnes historiques. Les CSV et les packages sont ensuite validés.

## Livraison en une commande

Sur le run livré :

```powershell
python -m etudecas.decision_support --run etudecas/simulation/result/_reruns/reviewed_map_20260918 --execute-actions --render-map --browser
```

Pour créer les runs nominal et risqué dans un **nouveau dossier** avant les
analyses, ajouter `--rebuild`. L'horizon est alors 1 825 jours, avec le
portefeuille de risques complet et sans nouveau Monte Carlo. `--rebuild`
refuse un dossier existant. Les autres options permettent de relivrer les runs
existants ; les actions valides sont réutilisées.

La commande recalcule le diagnostic, exécute ou vérifie les actions, génère le
tableau de bord, actualise le lien dans la carte, exporte les packages, rapproche
les données et lance `build-all` puis `check-all`. `--browser` nécessite Playwright
et Chromium. Le bilan `decision_support/delivery.json` passe par l'état `running`
et ne déclare `ok` qu'après les contrôles ; une exception de livraison écrit un
état `failed`. Sans `--browser`, le bilan indique explicitement que la revue
navigateur n'a pas été demandée.

Les [règles générées](generated/decision_support/index.md) suivent les fonctions
et les tests de ce huitième domaine. Les tests d'exécution utilisent un moteur
simulé pour vérifier l'isolation et le cache ; les essais de la livraison ont
été calculés par le moteur réel sur cinq ans.
