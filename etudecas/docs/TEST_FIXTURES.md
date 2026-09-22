# Fixtures autonomes et livraisons historiques

Une fixture autonome prépare des données synthétiques dans la mémoire du test
ou dans `tmp_path`, nettoyé par pytest. Elle permet de vérifier un comportement
sans dépendre des résultats présents sur le poste. Une fixture historique
consomme au contraire une livraison réelle et vérifie ses résultats ou sa
provenance ; elle ne doit pas être remplacée par des données inventées lorsque
cette identité historique est précisément l'objet du test.

## Périmètre migré

Les modules `test_nominal_run_curves.py`,
`test_supplier_v8_stage3_dashboard.py` et
`test_supplier_operating_point_full_campaign_v8.py`, dans
`etudecas/prototypes/scan_2027_risk_control/tests`, utilisent désormais une
fixture commune `historical_artifact` pour leurs entrées historiques directes.
Ils ne recherchent plus spontanément ces entrées sous `C:\dev`.

Le lecteur du dashboard V8 dispose d'une matrice synthétique complète :
18 voies × 3 états × 30 graines, soit 1 620 cellules. Son calcul des médianes,
le rejet d'un alias de graine de conception, le rejet d'une fenêtre incohérente
et l'incompatibilité avec le lecteur V4 sont vérifiés sans livraison externe.
Cette matrice teste le lecteur ; elle ne simule pas et ne remplace pas les
preuves scientifiques du registre historique.

Le test de répertoire du lanceur borné vérifie désormais la vraie racine du
dépôt, sans imposer que le dossier s'appelle `lca-simu-pr40`.

## Exécution

La fixture commune ajoute le marqueur `historical` aux tests qui en dépendent,
y compris indirectement. Sans option, ces intégrations sont ignorées avec un
motif explicite. Pour les exclure à la collecte :

```powershell
python -m pytest etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_dashboard.py -m "not historical" -q
```

Pour demander une vérification historique :

```powershell
python -m pytest etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v8_stage3_dashboard.py -m historical --historical-artifacts "D:/livraisons-auditees" -q
```

Le dossier fourni doit contenir les sous-dossiers des campagnes attendues.
Un dossier explicitement demandé mais absent, ou un artefact requis manquant,
fait **échouer** la vérification : il n'est pas transformé en test ignoré.
Les lecteurs conservent leurs contrôles de contenu et de signature.

## Scripts PowerShell

Les tests des wrappers de chaîne V3/V4 et du guardian V1 distinguent maintenant
les vérifications locales des intégrations figées. Les tests de syntaxe,
d'écriture JSON atomique, de transitions d'état et d'appels simulés au
planificateur restent autonomes. Les tests exécutant Windows PowerShell sont
ignorés avec un motif explicite lorsque son exécutable est absent.

Seize cas supplémentaires vérifient les lecteurs de GO V3/V4 avec des JSON
temporaires : accord valide, mauvaise empreinte d'inventaire ou de script,
chemin incompatible, approbateur absent, date invalide, décision d'attente et
liaison absente. Ils extraient les cinq fonctions nécessaires depuis l'AST
PowerShell ; le corps d'orchestration n'est pas exécuté. Le contexte
`$PSCommandPath` est fourni explicitement par le harnais de test, en pointant
sur le vrai script dont l'empreinte est vérifiée. Aucun accord n'est publié
dans les dossiers de campagne et aucune tâche réelle n'est lancée.

Les dix cas d'intégration figée requièrent `--historical-artifacts` **et**
`--historical-wrapper-repo`. Ces scripts vérifient leurs anciens chemins ;
la fixture refuse une relocalisation, au lieu d'affaiblir ces vérifications.
Le dépôt historique attendu est `C:/dev/lca-simu-pr40` et le dossier de
livraisons est `C:/dev/lca-simu-pr40-validation-artifacts-20260726`.
Fournir ces options n'autorise que les tests en mode `ValidateOnly` et les
lectures d'artefacts ; cela ne déclenche pas une campagne.

Le guardian fige une ancienne version V4. Le wrapper V4 courant est associé
au modèle d'accord V5, qui possède une autre empreinte : ces versions ne sont
pas interchangeables. Le test historique lit les scripts dans le checkout
historique explicitement fourni ; les tests locaux vérifient la version
courante et son propre modèle. Aucune empreinte figée n'est remplacée.

## Limites

Cette migration n'est pas un isolement de toute la suite des prototypes.
Les autres fixtures de livraisons restent à traiter.
Le runner de calibration dispose aussi d'un plan synthétique temporaire, construit
par le vrai générateur puis contrôlé par les vrais validateurs. Seule l'empreinte
autorisée du plan est substituée pendant ces tests ; la valeur de production est
restaurée ensuite et son refus du plan synthétique est testé séparément. Le test
du plan V2 historique exige `--historical-artifacts` et conserve ses empreintes
originales. Voir le [bilan de calibration](changes/2026-09-17-calibration-fixtures.md).

Les tests de besoins dynamiques reconstruisent leur audit depuis les mêmes copies
temporaires du graphe et des profils que le protocole. Deux CSV conservés dans le
dépôt remplacent les lectures des exports externes ; leurs empreintes sont vérifiées.
Voir le [bilan graphe/audit](changes/2026-09-17-dynamic-capacity-fixtures.md), qui
précise aussi la limite du checkpoint V3 simplifié dans les tests du runner.

Les tests de raffinement V3 construisent une chaîne V1/V2 temporaire avec des
résultats synthétiques et un refus V2 calculé par les vrais validateurs. Le test
historique correspondant exige `--historical-artifacts`. Voir le
[bilan des signatures V2](changes/2026-09-17-v2-plan-signatures.md).

Le marqueur `historical` ne couvre que les dépendances migrées : lancer toute
la suite avec `-m "not historical"` ne garantit pas encore son autonomie.

Les validations complètes des wrappers de clôture V8, de livraison finale V4
et du checkpoint op100 exigent désormais `--historical-artifacts` et
`--historical-wrapper-repo`, comme les autres wrappers figés. Leurs tests de
syntaxe, de statut et de décision isolée restent exécutables sans campagne
externe. L'intégration d'inventaire Stage3 exige les artefacts historiques et
vérifie toujours le checkout courant : fournir les artefacts seuls ne rend pas
ce checkout compatible avec leur signature. Les tests autonomes vérifient
séparément le périmètre explicite des sources et le refus d'un prédécesseur différent.
Certains manifestes historiques contiennent eux-mêmes des chemins absolus,
et le chargement V8 utilise encore une référence de voies configurée dans le
producteur. L'option change les entrées directes des fixtures, sans promettre
la transportabilité de toute la chaîne historique.

Les sources scientifiques et leurs empreintes attendues ne sont pas remplacées
par des stubs dans ces intégrations. Un test de provenance du lanceur V8 a
révélé une différence CRLF/LF : sa copie locale a été remise en LF après
vérification de l'identité avec Git et l'empreinte attendue, puis protégée
par `.gitattributes`. Aucune empreinte scientifique n'a été réacceptée.
