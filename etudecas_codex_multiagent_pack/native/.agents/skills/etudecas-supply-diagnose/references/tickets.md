# Registre léger d'investigation supply chain

Utiliser un seul registre dans le dossier d'investigation ou de preuves existant, par exemple `tickets.json` ou une section structurée du suivi déjà maintenu. Choisir un format unique, sans créer les deux ni un fichier par ticket. Aucun serveur, outil externe ou nouvel automate n'est nécessaire.

Le parent orchestrateur est le seul éditeur du registre. Les agents reçoivent un ID et la question utile, puis retournent les faits, les deltas proposés et les preuves par message. Pour une correction isolée, le parent peut porter le ticket lui-même. Un ticket représente une question vérifiable ; regrouper les symptômes qui dépendent d'une même cause et séparer les sous-questions indépendantes.

## Contenu d'un ticket

- **Identité et périmètre** : ID stable, question, écart mesuré ; article/site/produits concernés, période, unité, conventions de dates ; référence simulée et versions des sources. Ne pas mélanger les formats, sites ou fenêtres.
- **Pilotage** : statut, responsable, dépendances et propriété des fichiers ; priorité justifiée par l'impact observé sur service, stock ou coût. Distinguer coût opérationnel et approvisionnement externe ; ne pas additionner des unités différentes ni convertir un CA perdu en unités sans justification.
- **Faits et inconnues** : observations sources, reconstructions avec équation et résultats simulés séparés ; chemins/cellules/manifestes ; données absentes et résidus. Lier les artefacts, ne pas recopier les gros journaux.
- **Hypothèses** : pour chaque explication concurrente utile, prédiction, test discriminant ou observation à rechercher, résultat et verdict soutenue/réfutée/indécidable. Donner le scénario et les entrées/code pertinents lorsque le test est simulé.
- **Conclusion et suite** : symptôme, contrainte démontrée, cause identifiée ou inconnue, contribution et écart résiduel ; portée, contre-validation et limites ; prochaine action utile ou donnée précisément manquante.

Ces blocs sont un contrat de contenu, pas des champs supplémentaires à injecter dans les JSON de la toolbox. Ne remplir que les informations pertinentes disponibles ; une inconnue reste explicite.

## Statuts et clôture

`à examiner` → `en cours` → `à valider` → `résolu`.

- `données insuffisantes` : les rapprochements accessibles ont été exploités et l'information qui manque est nommée. Le ticket reste rouvrable ; cette conclusion ne prouve aucune cause.
- `réfuté` : la proposition portée par le ticket est contredite dans le périmètre annoncé ; conserver la preuve. Réfuter une hypothèse d'un ticket multicausal ne résout pas automatiquement le problème.
- `résolu` : la question a une réponse vérifiée avec portée et limites. Si elle porte sur une cause, établir le mécanisme, son ordre temporel, sa contribution quantitative et les alternatives examinées. Une correction métier nécessite une validation indépendante et les contrôles applicables ; une courbe localement plus proche ou un test technique réussi ne suffit pas.

Une réponse partielle conserve une prochaine action ou une limite explicite. La résolution du diagnostic ne signifie ni correction déployée ni promotion du nominal. Ne pas confondre ces statuts avec `AgentResult.status` (`complete`, `refused`, `incomplete`) ou avec une qualification technique. Ne pas créer de manifeste factice pour faire passer un handoff exploratoire.

Réouvrir un ticket seulement lorsqu'une nouvelle donnée, un résultat ou un changement pertinent le justifie ; conserver la conclusion antérieure et la raison de réouverture dans une note courte.
