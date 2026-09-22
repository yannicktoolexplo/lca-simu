# Carte HTML : audit métier et interaction du 20 septembre 2026

Public prioritaire confirmé : **planificateur supply chain / responsable industriel**. Livrable examiné : `supply_graph_corrected_map_20260918_enquetes_20260920.html`, sur le calcul nominal de 1 825 jours et les panneaux comparatifs embarqués. Les captures et valeurs DOM sont dans [les preuves navigateur](../../artifacts/testing/full_audit_20260920/browser/). Le moteur et la carte n'ont pas été modifiés pendant cet audit.

La carte est riche et utile pour investiguer une simulation. Elle n'est pas encore suffisamment fiable dans ses diagnostics, ni suffisamment directe dans sa présentation, pour servir seule de tableau de pilotage industriel. Les principaux obstacles ne sont pas des couleurs : ce sont le périmètre temporel des indicateurs, la qualification des événements, les unités, la visibilité des preuves et la séparation entre estimation et observation.

## Périmètre effectivement parcouru

- Chargement du fichier autonome dans Chromium, réseau désactivé, écran 1 440 × 900 ; premier affichage utilisable en 12,34 secondes sur ce poste pendant l'audit. Ce temps isolé n'est pas un benchmark.
- 70 parcours enregistrés dans `ui-review.json` : 9 ouvertures demandées de panneaux, 32 fiches de nœuds nominaux et 29 fiches d'audit fournisseur. 69 terminent ; le bouton de stress fournisseurs est désactivé faute de campagne disponible. Cet accès absent n'est pas une exception JavaScript.
- 107 états d'écran et leur texte/contrôles/courbes enregistrés ; ce nombre désigne des captures de l'état de l'interface, pas 107 validations numériques indépendantes.
- 24 vérifications complémentaires dans `deep-ui.json` : clic réel sur un marqueur, légende masquant une série, vues KPI/formules/recherche, lissages, quatre cartes KPI, modes de diagnostic, filtres de comparaison et de risques. Deux commandes de debug sont constatées indisponibles, sans forçage.
- Aucune erreur JavaScript remontée dans ces parcours. Le test ne garantit pas l'absence d'erreurs silencieusement absorbées par le code.
- Contrôles de disposition à 1 366 × 768 et 768 × 1 024 ; parcours clavier ciblé du tableau matière.

Pour parcourir tous les nœuds, le script injecte l'événement de sélection Plotly avec l'identité du nœud. Cela teste le gestionnaire applicatif, pas la précision de tous les clics géographiques. Un clic réel de souris a aussi été vérifié séparément. Les combinaisons de tous les onglets, sous-onglets, dates, nœuds et scénarios ne sont pas toutes exercées. La vérification numérique des séries est un travail distinct, détaillé dans [numeric_map.md](numeric_map.md).

## Défauts vérifiés

### UI-01 — Les radars et les critères fournisseurs sont inaccessibles

**Priorité haute.** Le sélecteur fournit 29 fiches. Pour les 29 visites, le panneau ne présente aucun bouton d'onglet accessible. Exemple SDC-VD0914360C : le texte promet trois radars et les critères détaillés « dans les onglets du panneau », alors que la synthèse est seule accessible.

La preuve DOM ciblée contient pourtant six boutons : Synthèse, Contexte public, Radar maturité, Radar criticité, Radar résilience, 28 critères. Leur conteneur `#incomingTabs` est en `display: none`. Les 87 figures de radar embarquées ne deviennent donc pas 87 vues utilisables.

Cause dans `worldmap_html_template.py:13495` et `:13549` : le conteneur est masqué à l'initialisation ; seule une liste externe contenant plusieurs entrées le rend visible. Ici, la liste externe contient une seule entrée « Audit fournisseur » ; sa liste interne contient six entrées, mais l'ajout des boutons internes ne réactive pas l'affichage. La construction de ces listes est dans `risk/supplier_audit.py:1102` et `:1122`.

Correction attendue : afficher les commandes dès qu'une liste interne offre plusieurs choix, puis tester le cas une entrée externe / plusieurs entrées internes avec clics réels sur les six vues. Preuves : `deep-ui.json`, champ `supplier_hidden_tabs`, et [capture fournisseur](../../artifacts/testing/full_audit_20260920/browser/audit-SDC-VD0914360C.png).

### UI-02 — Le diagnostic ne suit pas la fenêtre temporelle des courbes

**Priorité haute.** Dans la fiche M-1810, la fenêtre cinq ans donne une production réelle de **15 955 200 UN**. Après déplacement du curseur Fin sur année 1, les courbes sont bien limitées à cette année et l'indicateur courant passe à **1 656 000 UN**. Mais le bloc « Diagnostic opérationnel / Preuve » conserve **plan lotifié = 15,96 M, produit = 15,96 M**.

Ces deux nombres peuvent être corrects sur leurs périmètres respectifs ; l'interface ne rend pas cette différence suffisamment explicite. Un utilisateur croit filtrer sa fiche et peut justifier une décision annuelle avec un diagnostic cinq ans. Les fonctions `renderBusinessSummary`, `renderPanelMeta` et leurs consommateurs de `simulation_diagnostics` doivent porter un contrat de fenêtre commun, ou annoncer clairement « diagnostic sur l'horizon complet ».

Preuve : états `factory-full-horizon` / `factory-year-one` dans `deep-ui.json` et [capture année 1](../../artifacts/testing/full_audit_20260920/browser/factory-year-one.png). Critère de correction : chaque total affiché doit être soit recalculé sur la fenêtre, soit explicitement étiqueté comme total de l'horizon.

### UI-03 — Des alertes rouges amplifient des reliquats prévisionnels

**Priorité haute.** La fiche client nominale affiche « Critique disponibilité », 1 825 jours avec backlog et une action de réapprovisionnement prioritaire, tout en affichant une disponibilité cumulée de 100,00 %. Le dernier jour montre demande 3 825,3, servi 3 825 et backlog environ 1 en cumul d'articles.

Le rapprochement indépendant distingue la demande fractionnaire des mouvements physiques entiers : après l'amorçage, les reliquats sont essentiellement inférieurs à une unité par article. Un test `backlog > 0` suffit pourtant à entretenir une alerte sur tout l'horizon. Cela ne justifie ni de supprimer les reliquats ni de changer les demandes réelles. Il faut séparer « reliquat de calcul », « quantité physiquement servable en attente » et « retard au-delà de l'échéance », puis définir les seuils métier. Détail chiffré dans l'audit numérique.

Preuve : [fiche client](../../artifacts/testing/full_audit_20260920/browser/node-C-XXXXX.png). Autre signal à clarifier : « Adhérence lignes mensuelle 52,6 % » mesure autre chose que le respect du plan lotifié, qui peut être 100 %. Le libellé actuel fait facilement croire à des ordres non exécutés.

### UI-04 — La promesse de la navigation dépasse les données disponibles

**Priorité moyenne.** La livraison examinée présente les modes Sensibilité et Incertitude. Le panneau Priorités KPI indique qu'aucune priorité de sensibilité n'est disponible ; Courbes globales Monte Carlo n'a aucune trajectoire. Les stress tests sont désactivés. Structurel et RESILIENCE-SCAN sont absents de la navigation utilisable. Les sensibilités séparées du diagnostic existent ailleurs, mais ne deviennent pas automatiquement les courbes de ce mode.

Ces états vides sont correctement annoncés : il ne s'agit pas d'une courbe à zéro. Toutefois le planificateur découvre leur absence après avoir ouvert le panneau. Préférer un statut visible « données non chargées », un lien vers les résultats disponibles et le périmètre exact des campagnes. Ne pas afficher de faux seuils ou de bande d'incertitude pour remplir le vide.

### UI-05 — Des recommandations apparaissent avec une preuve insuffisante

**Priorité haute, défaut de sens plutôt que de rendu.** Le panneau des cascades affiche « cause », « propagation aval », « client atteint » et « action recommandée ». La contre-revue a reproduit un cas où un risque non appliqué est classé « client atteint » parce qu'un backlog existe dans la même période. Voir [contre-revue R2](review.md).

Il faut afficher séparément : incident configuré ; effet local enregistré ; lots exposés ; retard concomitant ; écart attribuable par rejeu comparatif. La couleur et l'action doivent dépendre du niveau de preuve. Le parcours de lot sait déjà distinguer exposition et effet physique ; cette discipline doit être commune à toute la carte.

### UI-06 — Lisibilité des graphiques et de l'écran d'entrée

**Priorité moyenne.** À l'ouverture, un lot est déjà sélectionné et sa fiche occupe une grande partie droite de la carte, sans que l'utilisateur ait formulé de recherche. La barre du haut comporte simultanément modes, commandes métier, identités techniques, période et filtres anglais. La carte géographique prend beaucoup de place alors que l'investigation demande souvent une relation article → ordre → transport → client.

Dans la fiche M-1810, l'annotation explicative de la courbe se superpose au titre et déborde horizontalement. La courbe client ajoute aussi une annotation de lot près du titre. Des textes métier longs sont injectés dans les annotations Plotly alors qu'ils devraient se trouver dans un paragraphe voisin ou une aide dépliable. Source : `buildPlotlyFigure`, notes à `worldmap_html_template.py:12973` ; captures [usine](../../artifacts/testing/full_audit_20260920/browser/node-M-1810.png) et [client](../../artifacts/testing/full_audit_20260920/browser/node-C-XXXXX.png).

À 768 px de large, la barre atteint 298 px de haut ; le graphe conserve une hauteur de 960 px. Le site ne déborde pas horizontalement, mais demande beaucoup de défilement et une fiche masque le contexte. La priorité reste le poste de travail industriel ; une adaptation tablette est ensuite souhaitable.

### UI-07 — Navigation clavier inégale

**Priorité moyenne.** Le nouvel explorateur ouvre son bouton Fermer au clavier et répond à Échap. Parmi les huit autres ouvertures demandées, les sept panneaux ouverts laissent le focus sur le bouton de la page sous-jacente et Échap ne les ferme pas. Le tableau matière laisse sortir le focus de sa fenêtre : au deuxième Tab après son bouton Fermer, le lien Diagnostic de la page est atteint.

Les neuf fenêtres anciennes inventoriées n'ont pas `role=dialog`, `aria-modal` ni titre relié par `aria-labelledby`. Le nouvel explorateur possède ces trois attributs. Uniformiser fermeture, entrée/sortie du focus, ordre de tabulation, retour au déclencheur et nom accessible. La présence d'attributs seule ne suffit pas : vérifier réellement ces déplacements.

### UI-08 — Précision apparente et vocabulaire trop techniques

**Priorité moyenne à haute selon l'indicateur.** Le tableau matière affiche trois décimales pour presque toutes les quantités, y compris UN ; certaines lignes appelées « consommé simulé » sont en réalité une estimation BOM. Le fournisseur estimé SDC-VD0914360C affiche une confiance de 97,0 % et une résilience de 49,2 semaines. L'état « estimation proxy » est bien indiqué, mais ces chiffres ne sont ni une probabilité validée de fiabilité ni un engagement industriel de délai.

« Run nominal », « nodes », « Supplier DC », « Physics of Decision », « state-dependent », « backlog », « driver », « occurrence », « consigne physique » et « score / indice » n'ont pas tous une lecture opérationnelle directe. Le vocabulaire doit rester précis sans tout traduire artificiellement : conserver MRP/BOM si un glossaire les définit, et présenter les identifiants techniques en second niveau.

| Libellé actuel | Libellé ou précision proposée |
|---|---|
| Run nominal | Simulation de référence |
| Nodes / flux | Sites / liaisons, avec nombre non localisé |
| Supplier DC | Site fournisseur, selon sa fonction réelle |
| Backlog | Demande restant à servir ; préciser échéance et unité |
| Disponibilité produit cumulée | Part de la demande servie sur la période, rattrapages inclus |
| Coût total | Coût opérationnel simulé ; exceptionnel et périmètre séparés |
| Consommé simulé | Consommation physique enregistrée ; besoin théorique dans une autre colonne |
| Client atteint | Retard client concomitant, ou impact attribué si sa preuve existe |
| Confiance estimation 97 % | Complétude/qualité des données du proxy, selon la formule ; pas probabilité de justesse |
| Physics of Decision | Indice exploratoire de dérive et ses hypothèses |
| Stock physique | Stock présent, disponible, réservé et en transit distingués |

## Ce qui fonctionne bien et doit être conservé

Le fichier est consultable hors ligne. Les courbes restent interactives ; un clic de légende masque bien la série, les fenêtres annuelles changent les séries, les filtres de scénario et de cascade répondent. Les fiches séparent déjà de nombreuses courbes par unité G/KG/UN. Les vues de calcul et les formules sont accessibles. La comparaison explique explicitement que son enveloppe de scénarios n'est pas un intervalle de confiance Monte Carlo et que le service cumulé ne mesure pas la ponctualité.

Le nouveau parcours des lots est séparé du suivi détaillé historique, conformément à la demande utilisateur. Recherche, graphe orienté, fiche latérale, date de lecture, états inconnus, quantités bornées après mélange, chargement des expéditions et sauvegarde des enquêtes constituent une base utile. Les preuves de sa livraison précédente sont conservées ; elles ne doivent pas être présentées comme nouvel audit exhaustif de toutes ses combinaisons.

## Organisation recommandée pour le métier

Conserver l'accès aux vues existantes, puis construire une entrée « À traiter » centrée sur une période en jours/semaines, un article et un site. Chaque ligne d'alerte doit contenir quantité/unité, date du besoin, date prévue, écart, commande ou production concernée, statut de preuve et lien vers son détail. La carte géographique devient une vue de contexte accessible depuis cette ligne.

Une fiche article-site devrait proposer dans cet ordre : situation au jour choisi ; demande et échéances ; stock disponible/réservé/en transit ; ordres et dates ; lots et transports ; hypothèses. Un clic sur un retard doit ouvrir le même objet dans le parcours de lots, avec scénario et date conservés. Un bouton « Origine de ce chiffre » doit exposer colonne source, formule, unité, fenêtre, données manquantes et version du calcul.

Les comparaisons doivent partager un sélecteur explicite de scénario de référence et de variante. Le nominal, les risques et les sensibilités conservent des identités distinctes. Présenter d'abord deux trajectoires et leurs écarts ; réserver enveloppes, indices pondérés et décompositions à une vue Recherche. Une comparaison de deux scénarios ne devient pas une mesure probabiliste de risque.

Critère métier de réussite : en moins de quelques interactions, le planificateur peut partir d'un article en retard, identifier les ordres et lots concernés, retrouver un départ prévu ou effectué, remonter aux composants, puis retrouver la preuve du diagnostic. Le temps réel de ce parcours devra être mesuré avec un utilisateur ; il n'est pas démontré par les tests de DOM de cet audit.
