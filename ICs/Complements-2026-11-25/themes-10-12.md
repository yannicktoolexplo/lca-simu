# Qualité et environnement

Complément du 25 novembre 2026. Origine : lecture des cahiers publics au commit `REV-0415`, veille de sources primaires et calculs pédagogiques exécutés pour préparer la supervision. Ces calculs ne sont attribués à aucun intervenant. Les références de lignes portent sur cette version de `ICs/Cahiers-metier.md`.

## 10 Le magasin permet il de constituer un jeu complet

**Question à trancher.** Combien de jeux peut-on réellement engager aux dates de consommation, après exclusion des quantités bloquées et déjà réservées ?

**Acquis exact.** Le cahier, section « Le magasin a-t-il de quoi constituer un jeu complet pour le montage ? », lignes 67 à 71, rapporte quatre variantes et un bilan séparé sur 163 composants. Dans la variante modérée, un décalage de disponibilité d'un mois laisse 115,12 kg bloqués et réduit les jeux livrés d'une unité. Il établit déjà pourquoi le stock total en kilogrammes ne suffit pas. Aucun détail de nomenclature ou de lot permettant de reproduire ces chiffres n'est public. La priorité est une vue des composants utilisables, plutôt qu'une nouvelle simulation.

**Veille métier puis méthode utile.** Microsoft décrit dans [Inventory blocking](https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/inventory-blocking), mise à jour du **14 août 2025**, la distinction entre stock reçu, stock bloqué et réception attendue après inspection. La quantité à contrôler n'est pas nécessairement la quantité immobilisée. En réunion magasin, demander donc « combien est bloqué pour cet ordre ? », pas seulement « combien a été échantillonné ? ». Vérifier aussi les doubles comptages lorsque plusieurs mécanismes de blocage coexistent.

Le standard [GS1 EPCIS 2.0](https://ref.gs1.org/standards/epcis/), **juin 2022**, notamment section 7.3.6.2, permet de relier un événement daté à un objet, un lieu et un état métier. Son apport pratique est un journal réception–blocage–libération relié au lot ; il ne dispense pas de la nomenclature et des réservations. Pour commencer, un export Excel des mêmes champs suffit. L'[annonce ISO du 16 septembre 2026](https://www.iso.org/news/2026/09/ISO9001-2026) confirme la publication d'ISO 9001:2026 : vérifier l'édition appliquée dans l'entreprise et le responsable de la libération, sans déduire du communiqué le contenu détaillé des clauses.

**Petit essai exécuté, données entièrement pédagogiques.** Tous les composants sont requis au même instant ; aucun remplacement de référence n'est autorisé. Les blocages et réservations du tableau portent sur des pièces distinctes.

| Référence | Pièces par jeu | Stock physique en pièces | Bloquées | Réservées ailleurs | Utilisables | Jeux permis |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 2 | 20 | 0 | 4 | 16 | 8 |
| B | 1 | 12 | 5 | 1 | 6 | 6 |
| C | 3 | 30 | 0 | 3 | 27 | 9 |

Le témoin naïf annonce `min(20/2, 12/1, 30/3) = 10` jeux. Le calcul utile donne `min(⌊16/2⌋, ⌊6/1⌋, ⌊27/3⌋) = 6`. Si les cinq B sont libérés avant consommation, on passe à **8 jeux**, A devenant limitant. Le résultat qui changerait la décision de libération d'un ordre de huit jeux est donc la disponibilité effective de B avant son poste. Une libération seulement espérée reste une hypothèse de planning.

**À demander et livrable.** Une ligne par ordre–référence–lot–site : version de nomenclature, quantité par jeu, stock physique, statut qualité, identifiant de blocage, quantité réservée à chaque ordre, date prévue et effective de libération, date de consommation au poste et date de connaissance de ces informations. Couvrir tous les composants de l'ordre, y compris les petits composants limitants. Livrable conseillé : tableur de disponibilité avec une ligne par composant ; aucune publication de recherche n'est nécessaire pour ce premier contrôle.

## 11 Combien de pièces acceptées justifient une retouche

**Question à trancher.** Quel nombre de pièces acceptées rend la retouche moins émettrice que le remplacement, et cette réussite est-elle plausible avant de lancer l'opération ?

**Acquis exact.** Le cahier, section « Combien de pièces doivent passer le recontrôle pour justifier une retouche ? », lignes 73 à 77, donne le seuil de trois acceptations sur six avec navette existante et celui de quatre avec tournée dédiée de 12 kg CO₂e. Les inventaires de fabrication, retouche et rebut ne sont pas fournis ; ces deux seuils ne permettent pas de reconstituer ces inventaires. La distinction entre transport déjà prévu et transport déclenché est déjà acquise.

**Veille métier.** Le [GHG Protocol Product Standard](https://ghgprotocol.org/sites/default/files/standards/Product-Life-Cycle-Accounting-Reporting-Standard_041613.pdf), **2011**, chapitres 6 à 10 et annexe A, donne un cadre de périmètre, données et allocation. Il sert à documenter l'inventaire ; il ne constitue pas à lui seul une méthode de crédit d'émissions évitées. Dans la revue retouche, comparer un même service et expliciter séparément les émissions que chaque option déclenche. La [page de suivi du standard](https://ghgprotocol.org/product-standard) annonce, au **9 février 2026**, le groupe de travail conjoint avec ISO ; cette annonce n'est pas une nouvelle méthode finale à appliquer.

**Ouverture recherche proportionnée.** Järnefelt, Ashouri et Behm, [Does repair improve environmental performance?](https://doi.org/10.1016/j.jclepro.2026.149164), **20 septembre 2026**, examinent batterie, écran et carte de téléphone. Le [résumé primaire des auteurs sur VTT](https://cris.vtt.fi/en/publications/does-repair-improve-environmental-performance-integrating-tempora/) indique que le choix dépend du composant, de la date de panne et de l'impact considéré. Lecture limitée au résumé primaire, le texte éditeur n'ayant pas été accessible. Conséquence pour le terrain : vérifier la durée de service restante et les autres impacts avant d'étendre un seuil carbone ; aucun pourcentage de cette étude n'est transféré au lot industriel.

**Essai exécuté, exemple pédagogique distinct du lot de six.** Besoin identique : huit pièces conformes de durée de service équivalente. Remplacer les huit émet 72 kg CO₂e, soit 9 kg par pièce. Retoucher le lot émet 25 kg CO₂e, essais et traitements supplémentaires compris ; chaque échec impose encore une pièce neuve. Ces valeurs sont des hypothèses de démonstration, pas des facteurs du cahier.

`Écart retouche − remplacement = 25 + transport supplémentaire − 9 × pièces acceptées`.

| Option | Acceptées après retouche | Total en kg CO₂e | Écart au remplacement |
| --- | ---: | ---: | ---: |
| Navette existante, effet marginal supposé nul | 3 | 70 | −2 |
| Tournée dédiée de 12 kg CO₂e | 4 | 73 | +1 |
| Tournée dédiée de 12 kg CO₂e | 5 | 64 | −8 |

Le seuil strict est ici **3 acceptations**, puis **5** avec tournée dédiée. Avant décision, le nombre réellement accepté est inconnu : employer une estimation justifiée par type de défaut et tester sa borne basse. Une navette existante peut avoir une émission attribuée au lot dans un inventaire ; « marginal nul » désigne seulement l'hypothèse de cette comparaison de décisions. Charge supplémentaire, détour ou véhicule additionnel imposent un recalcul.

**À demander et livrable.** Registre de lots comparables : défaut, pièces tentées et acceptées, consommation de retouche/recontrôle, rebuts, pièces neuves réellement évitées, durée/fonction garanties, dates, trajet existant ou ajouté, kilomètres, chargement et méthode des facteurs d'émission. Livrable : fiche de calcul du seuil et questions au responsable qualité et au transporteur.

## 12 Le choix de conception résiste il à la pondération

**Question à trancher.** Peut-on retenir une variante pour toutes les préférences jugées acceptables, ou faut-il expliciter l'impact environnemental qui prime ?

**Acquis exact.** Le cahier, section « Le choix de conception résiste-t-il à une autre pondération ? », lignes 79 à 83, rapporte huit indicateurs améliorés et huit dégradés, à masse identique sur production et livraison. Il situe une inversion à **7,294 %** pour l'eutrophisation des eaux douces, les autres poids variant proportionnellement. Les valeurs des seize indicateurs, facteurs de normalisation et poids initiaux ne sont pas publics. Le seuil est donc un résultat documenté, pas recalculé ici. Une masse identique ne prouve pas une fonction ou une durée de service identique.

**Veille métier et actualisation.** La [recommandation européenne sur l'empreinte environnementale](https://environment.ec.europa.eu/publications/recommendation-use-environmental-footprint-methods_en), publiée le **16 décembre 2021**, [annexe I](https://environment.ec.europa.eu/document/download/680503dc-5a19-4f6a-bb92-84d9bfc8f312_en?filename=Annexes+1+to+2.pdf), sections 3.2, 5.2 et 6.2, sépare unité fonctionnelle, caractérisation, normalisation, pondération et robustesse. En revue, demander le tableau des impacts dans leurs unités, puis les valeurs normalisées et la règle d'agrégation. Ne pas additionner directement des kg CO₂e et des kg équivalent phosphore. Une pondération propre à l'entreprise doit être présentée comme une préférence de décision ; elle ne remplace pas librement les poids prescrits dans un résultat revendiqué conforme à la méthode PEF.

Le [rapport JRC sur EF 3.1](https://op.europa.eu/en/publication-detail/-/publication/145f8401-a82a-11ed-b508-01aa75ed71a1), publié le **8 février 2023**, décrit des modifications de caractérisation pour six catégories et de normalisation pour huit. Il compare 2 752 jeux de données et 49 produits représentatifs. Cela justifie de figer la version avant de comparer les variantes, sans supposer que le seuil public resterait identique avec d'autres facteurs. La [page JRC de transition](https://knowledge-for-policy.ec.europa.eu/environmental-footprint-transition-phase_en), mise à jour le **4 novembre 2026**, répertorie encore le package EF 3.1 de juillet 2022 ; sa date de mise à jour ne signifie pas publication d'une méthode EF nouvelle.

**Essai de revue exécuté, sans inventer les seize impacts.** On propose à la supervision une plage de poids de **5 à 10 %**, uniquement pour illustrer la question à poser. Vérification numérique : `5 % < 7,294 % < 10 %`. Les distances au seuil sont 2,294 et 2,706 points de pourcentage. Cette plage traverse donc une inversion déjà documentée : aucun choix unique n'est robuste sur toute cette plage, sous la même trajectoire proportionnelle des quinze autres poids. Le cahier ne donne pas le sens de préférence de chaque côté ; aucune variante n'est déclarée gagnante ici. La plage acceptable doit être décidée avant d'observer le classement.

**À demander et livrable.** Pour chacune des deux variantes : fonction rendue, durée de service, quantité de référence, étapes incluses/exclues, seize résultats caractérisés, facteurs et version de normalisation, poids et somme des poids, incertitudes, règle des autres poids et plages acceptées. Recalculer ensuite les deux extrémités, puis les incertitudes d'inventaire si elles peuvent inverser le résultat. Livrable conseillé : note courte avec tableau des impacts opposés et plage de bascule. Le seuil public suffit à préparer la discussion ; une optimisation supplémentaire n'apporterait rien avant ces données.

Toutes les sources ci-dessus ont été ouvertes et consultées le **25 novembre 2026**. Les sources documentent des pratiques, standards ou résultats publiés ; les exemples chiffrés nouveaux servent uniquement à expliquer la décision.
