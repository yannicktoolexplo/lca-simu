# Fixtures PowerShell — 16 septembre 2026

Les tests des wrappers de chaîne V3/V4 et du guardian V1 distinguent désormais
les contrôles autonomes des intégrations figées sur l'ancien environnement.
Dix cas sont marqués `historical` via leur fixture. Sans configuration explicite,
ils sont ignorés ; une configuration incomplète ou relocalisée est refusée.
Les contrôles scientifiques et les chemins imposés par les scripts historiques
ne sont pas assouplis.

Seize tests autonomes supplémentaires appellent les lecteurs de GO V3/V4,
extraits de l'AST PowerShell avec leurs dépendances. Ils utilisent des fichiers
temporaires et fournissent le contexte du chemin du script explicitement.
Ils vérifient une acceptation valide et sept motifs de refus par version.
Le corps d'orchestration des scripts n'est pas exécuté. Les tests existants
d'écriture atomique, de transitions d'état et de tâches simulées sont conservés.

Les deux wrappers courants ont été remis en LF après vérification de leur
identité avec Git et leurs modèles signés. `.gitattributes` conserve cette
représentation. Le wrapper V3 retrouve le SHA-256
`451e3ab5e7a5f737db6d9375242ca88a179aff65aa2db39bd7ced63c217529b6`.
Le wrapper V4 courant retrouve
`b41f5cf62930944076f69865fb0f7dd161bb266ccd593df85da45033ac56b47d`,
déjà déclaré par le modèle V5. Cette version diffère de l'ancienne V4 figée
par le guardian ; aucune substitution d'empreinte historique n'a été faite.

Validation ciblée : **49 tests réussis, 10 intégrations historiques ignorées,
4 sous-tests réussis**, en 47 secondes. Ce périmètre couvre les trois modules
de wrappers, les lecteurs GO autonomes, la politique des fixtures et la
documentation. La collecte avec `-m historical` sélectionne exactement les
10 cas concernés. `git diff --check` passe.

Aucune campagne, tâche réelle ou vérification de l'environnement historique
complet n'a été lancée. Les autres fixtures de prototypes restent hors de
cette qualification. Le [guide des fixtures](../TEST_FIXTURES.md) donne les
conditions d'exécution et les limites.
