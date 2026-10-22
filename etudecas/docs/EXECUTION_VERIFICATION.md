# Exécution physique et vérification des livraisons

## Règles d'exécution

L'utilisateur a confirmé le 18 septembre 2026 : les stocks et mouvements
physiques en UN sont entiers ; les prévisions peuvent être fractionnaires.
Le moteur exécute la partie entière disponible du besoin et conserve le reste
dans le reliquat prévisionnel. Quatre demandes de 0,5 pièce, avec du stock,
produisent les services 0, 1, 0, 1 : aucune demande ne disparaît.

Les réceptions calculées, pertes simulées et stocks hypothétiques issus d'une
sensibilité sont quantifiés avant de modifier simultanément stock et registre.
L'arrondi physique est inférieur ; il ne s'applique pas aux masses/longueurs.
Le stock initial source doit déjà être entier en UN : une fraction est refusée.
Un transit hypothétique de dix pièces sur trois jours est réparti 3, 3, 4.
Les prévisions et cibles de planification ne deviennent pas des stocks physiques.
Le registre refuse une fraction en UN plutôt que l'arrondir indépendamment.

Les stocks de fin de journée sont exportés après production, service,
expéditions et pertes. Ils se rapprochent des mouvements du registre.
Une demande d'achat non exécutée faute de capacité reste un besoin ; ce n'est
pas une destruction de matière. Les rejets qualité sont séparés et les pertes
sont publiées par site, article et unité dans `physical_losses_by_item_uom`.
Les anciens totaux arithmétiques de pertes restent des champs de compatibilité
à unités hétérogènes, inutilisables comme quantités de produit fini.

## Contrat de la carte

Chaque lot sélectionnable possède un modèle de sélection causale calculé par
le même code Python. Le HTML autonome partage les lignes de généalogie entre
les modèles pour limiter la taille. Il ne reconstruit pas l'historique complet
d'un stock partagé lorsqu'un modèle manque.

Une consommation d'une autre campagne n'est pas un événement causal du lot
sélectionné. Un lot produit sorti de l'usine reste « produit » ; l'absence de
stock usine ne démontre ni livraison client ni pénurie d'intrants. Les difficultés
historiques de la campagne conservent leur champ séparé. Les libellés trop longs
ont un détail au survol ; la vue complète peut être ajustée à la largeur.

## Choisir les contrôles autorisés

Appliquer [TEST_VALIDATION.md](TEST_VALIDATION.md) avant toute exécution : relire
les cas exacts et leurs fixtures, puis sélectionner seulement les contrôles
compatibles avec les restrictions Sophos. Les anciennes prescriptions de modules
pytest entiers et du runner `adversarial_review` sont historiques ; elles ne sont
pas une autorisation de les relancer. Aucun test volontaire d'altération, de
restauration de dates, de disparition simulée ou d'écritures factices répétées
n'est autorisé ; `check_source_revision.py` et ses variantes restent exclus.

Les commandes de qualification CSV, de documentation et de navigateur sont
décrites dans [la toolbox](MULTI_AGENT_OPERATIONNEL.md). Désigner les chemins
réels du calcul et de la carte, annoncer le périmètre et garder les manifestes.
Une alerte ou un refus d'écriture impose l'arrêt des exécutions concernées et
un diagnostic en lecture seule, sans nouvelle sonde ni contournement.

Le contrôle des CSV n'importe ni le moteur, ni les payloads, ni leurs validateurs.
Il recalcule conservation de demande, stocks, mouvements, coûts et identités.
Les fixtures historiques comportent des résultats calculables à la main et des
corruptions volontaires ; les cas interdits restent exclus, même s'ils figurent
dans une ancienne preuve. Privilégier un oracle en mémoire et la comparaison en
lecture seule des résultats existants.
La qualification refuse les preuves manquantes et les invariants incorrects.
La livraison du diagnostic appelle ce contrôle avant de publier ses résultats.
Le navigateur hors ligne vérifie plusieurs lots, les compteurs, les campagnes
causales, les dates de création des ancêtres et les débordements de texte.
Les rapports conservent les empreintes des fichiers effectivement examinés.
Le premier `--run` doit correspondre au HTML transmis. Le lot PBATCH de
régression est rapproché des CSV de cette exécution, par lots parents/enfants,
expédition et quantité reçue dans l'horizon. Une découpe historique n'est pas
une constante valable après changement de demande ou de calendrier. Un solde
non reçu à la fin de l'horizon reste distinct des réceptions chez le client.

Les caches d'actions vérifient calendrier, CSV, résumés et sources applicatives.
Les reprises Monte Carlo incluent les modules frères du moteur. Un cache ancien
incomplet ou une modification des sources impose une nouvelle exécution ; aucune
signature scientifique historique n'est réacceptée automatiquement.

Ces contrôles ne certifient pas la vérité des données sources, les distributions
de risque, les prix, ni une recommandation industrielle. Une carte non examinée
reste explicitement non vérifiée. La référence historique est conservée ; les
corrections sont recalculées dans un autre dossier. Le 20 septembre, l'utilisateur
a confirmé le calendrier de sécurité lundi-vendredi et l'application intégrale
des jours sources au dépôt (coefficient 1). La convention de planification
`tau_process` est conservée et son sens physique reste à confirmer.
